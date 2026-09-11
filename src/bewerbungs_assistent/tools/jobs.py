"""Jobsuche und Stellenverwaltung — 9 Tools (#446: stelle_bearbeiten, #432: scraper_diagnose)."""

import re
import threading
from collections import Counter
from typing import Optional
from urllib.parse import quote_plus
from ..services import anzeigenalter as _anzeigenalter
from ..services import entfernung as _entfernung
from ..services.nutzerfuehrung import leer


from ..services import passung


def _build_empfehlung(fit_result: dict, job_dict: dict,
                      gespeicherte_analyse=None,
                      profil_kompetenzen: int = 0) -> dict:
    """v1.7.0-beta.81 (#662): Klare 3-Stufen-Empfehlung im fit_analyse-Result.

    Soll Claude vor diplomatischen Weichspuelern bewahren ("Trefferchance
    nicht hoch, aber realistisch vorhanden"). Stattdessen liefert die
    Heuristik einen eindeutigen Verdict, den Claude direkt zitieren kann:

    - EMPFOHLEN: passt, Bewerbung sinnvoll
    - BEDINGT: Methodenluecke ueberbrueckbar, aber transparent adressieren
    - NICHT_EMPFOHLEN: fachlicher Gap zu gross oder k.o.-Kriterium fehlt

    Drei k.o.-Kriterien:
    1. Stellenbeschreibung fehlt komplett -> Score ist unzuverlaessig
    2. Hochschulabschluss gefordert, fehlt im Profil -> ATS-Risiko
    3. MUSS-Keywords komplett verfehlt -> kein fachlicher Anker

    Sonst Score-ANTEIL am erreichbaren Hoechstwert (#999):
    - >= 75 %: EMPFOHLEN
    - 50-74 %: BEDINGT
    - <  50 %: NICHT_EMPFOHLEN

    **Bis v1.7.48 standen hier feste Zahlen gegen `total_score`** — und
    der ist keine Prozentzahl, sondern eine ungedeckelte Punktsumme,
    deren Obergrenze aus der Laenge der MUSS-Liste folgt. Gemeldet
    (08.09.2026): eine Stelle, die ALLE MUSS-Begriffe trifft, remote
    ist, 3 km entfernt liegt und ueber Wunsch zahlt, bekam
    *"Score 15.0/100 — fachlicher Gap zu gross"*. Mit fuenf bis zehn
    Pflichtbegriffen — dem Normalfall — war `EMPFOHLEN` strukturell
    unerreichbar, und jede Stelle bekam denselben Satz.

    Der Satz des Melders: *"Der Gap ist die Skala."*
    """
    score = fit_result.get("total_score", 0) or 0
    # Der erreichbare Hoechstwert kommt aus derselben Rechnung wie der
    # Score. Ist er unbekannt (0), wird KEIN Anteil gebildet — lieber
    # keine Einordnung als eine erfundene (#989).
    maximum = float(fit_result.get("total_score_max") or 0)
    anteil = (score / maximum) if maximum > 0 else None

    def _skala() -> str:
        """Wie die Zahl genannt wird — nie als Prozent von 100."""
        if anteil is None:
            return f"Score {score}"
        return f"Score {score} von erreichbaren {maximum:g} ({anteil:.0%})"
    risks = fit_result.get("risks") or []
    muss_hits = fit_result.get("muss_hits") or []
    missing_muss = fit_result.get("missing_muss") or []
    desc_ok = fit_result.get("beschreibung_vorhanden", True)
    # v1.7.0-beta.86 (#671 Ebene 2): Wiedergaenger als k.o.-Signal — aber NUR
    # bei fachlichen Gruenden (falsches_fachgebiet etc.). Gehalt/Entfernung
    # koennen sich aendern, taugen nicht als k.o.
    wiedergaenger = fit_result.get("wiedergaenger") or {}
    _FACHLICHE_KO_GRUENDE = {
        "falsches_fachgebiet", "zu_junior", "zu_senior",
        "kein_hochschulabschluss", "unpassendes_arbeitsmodell",
    }

    ko_gruende: list[str] = []
    if (wiedergaenger and wiedergaenger.get("anzahl", 0) >= 2
            and wiedergaenger.get("top_grund") in _FACHLICHE_KO_GRUENDE):
        ko_gruende.append(
            f"Wiedergaenger: Firma '{wiedergaenger.get('firma')}' wurde "
            f"bereits {wiedergaenger['anzahl']}x mit fachlichem k.o.-Grund "
            f"'{wiedergaenger['top_grund']}' aussortiert — sehr wahrscheinlich "
            "erneut nicht passend."
        )
    if not desc_ok:
        ko_gruende.append(
            "Stellenbeschreibung fehlt — keine fachliche Bewertung moeglich. "
            "Beschreibung nachladen vor Empfehlung."
        )
    elif fit_result.get("beschreibung_kurz"):
        # #762: Beschreibung existiert, ist aber nur eine Kurznotiz (typisch
        # nach stelle_manuell_anlegen). Dann matchen kaum MUSS-Keywords und der
        # Score ist kuenstlich niedrig — das ist KEINE fachliche Absage, sondern
        # fehlende Datengrundlage. Ehrlich als "nicht beurteilbar" ausweisen,
        # statt eine passende Rolle faelschlich als Gap abzuurteilen.
        ko_gruende.append(
            "Beschreibung ist nur ein Kurztext, keine vollstaendige Anzeige — "
            "der Score ist dadurch NICHT belastbar und dies ist ausdruecklich "
            "keine fachliche Absage. Anzeigen-Volltext nachladen "
            "(stellenbeschreibung_nachladen) oder einfuegen, dann neu bewerten."
        )
    # v1.7.35 (#972): der Hochschulabschluss-k.o. ist entfernt. Er
    # stuetzte sich auf ein Merkmal, dessen Profilseite nie modelliert
    # wurde — ein Staatlich gepruefter Techniker (DQR 6, wie Bachelor)
    # galt als "kein Abschluss". Der WAEHLBARE Ablehnungsgrund
    # `kein_hochschulabschluss` bleibt: das entscheidet der Mensch.
    if not muss_hits and missing_muss:
        ko_gruende.append(
            f"Kein einziges MUSS-Keyword im Profil belegt "
            f"({len(missing_muss)} fehlen) — kein fachlicher Anker."
        )

    # #1003: ab hier entscheidet NICHT mehr der Score.
    #
    # Bis v1.7.60 stand hier `anteil >= 0.75 -> EMPFOHLEN` usw. In den
    # Score gehen Keyword-Treffer, Gehalt, Entfernung und Remote-Grad
    # ein — der LEBENSLAUF geht nicht ein. Der Score beantwortet "steht
    # in dieser Anzeige, wonach ich gesucht habe"; der Verdict behauptete
    # "passt dieser Mensch auf diese Stelle". Zwei Fragen, eine Antwort.
    #
    # Die Schwellen sind ersatzlos weg statt gegen einen besseren
    # Massstab getauscht (Verteilung, bisheriger Bestwert): das haette
    # denselben Fehler nur sauberer gemacht.
    befund = passung.urteil(
        ko_gruende=ko_gruende,
        beschreibung_vorhanden=bool(
            desc_ok and not fit_result.get("beschreibung_kurz")),
        profil_kompetenzen=profil_kompetenzen,
        gespeicherte_analyse=gespeicherte_analyse,
    )
    # Der Score kommt weiter mit — als das, was er ist.
    befund["score"] = score
    if maximum:
        befund["score_maximum"] = maximum
    befund["score_bedeutung"] = (
        f"{_skala()}. Diese Zahl misst, wie gut die Anzeige deine "
        "SUCHBEGRIFFE trifft — sie ist ein Indikator fuer die Suche und "
        "keine Aussage darueber, ob du auf die Stelle passt.")
    befund["score_zuverlaessig"] = bool(
        desc_ok and not fit_result.get("beschreibung_kurz"))
    if muss_hits or missing_muss:
        befund["muss_treffer"] = len(muss_hits)
        befund["muss_gesamt"] = len(muss_hits) + len(missing_muss)
    return befund


def _aehnliche_outcome_pattern(
    db, target_job: dict, *, schwellwert: int = 3, max_check: int = 15,
) -> Optional[dict]:
    """#648 (C17): Outcome-Pattern-Erkennung fuer fit_analyse.

    Pruefe ob >= `schwellwert` aehnliche Stellen aus dem **gleichen** Grund
    aussortiert wurden. Wenn ja: liefere strukturierten Warning-Eintrag.

    Args:
        db: Database-Instanz.
        target_job: Job-Dict mit `hash`, `title`, `description`.
        schwellwert: Mindestanzahl gleichgesinnter Aussortierungen (Default 3).
        max_check: Max Anzahl aehnlicher zu pruefen (Performance-Cap).

    Returns:
        None wenn kein Pattern, sonst dict mit:
        - risk_text: kurzer Risiko-Hinweis fuer den risks-Block
        - top_grund: der dominante dismiss_reason
        - anzahl: wie viele aussortierte Aehnliche
        - beispiele: bis zu 3 (hash, title, company) als Referenz

    Idempotent + read-only. Pure-Helper, kein State.
    """
    STOPS = {
        "und", "der", "die", "das", "ein", "eine", "fuer", "im", "mit",
        "bei", "von", "zu", "in", "an", "the", "and", "for", "with",
        "stelle", "position", "rolle", "team", "wir", "sie",
    }

    def _tokens(text):
        return set(re.findall(r"[a-zäöüß0-9]+", (text or "").lower())) - STOPS

    target_tokens = _tokens(
        (target_job.get("title", "") or "") + " "
        + ((target_job.get("description") or "")[:1500])
    )
    if not target_tokens:
        return None

    target_hash = target_job.get("hash")
    try:
        dismissed = db.get_dismissed_jobs()
    except Exception:
        return None

    # Aehnlichkeit nach Jaccard, gleicher Filter wie aehnliche_stellen_finden
    scored = []
    for j in dismissed:
        if j.get("hash") == target_hash:
            continue
        if not j.get("dismiss_reason"):
            continue
        jt = _tokens(
            (j.get("title", "") or "") + " "
            + ((j.get("description") or "")[:1500])
        )
        if not jt:
            continue
        inter = target_tokens & jt
        union = target_tokens | jt
        jaccard = len(inter) / len(union) if union else 0
        if jaccard < 0.10:  # haerterer Schwellwert als aehnliche_stellen_finden,
            continue        # wir wollen nur klar aehnliche im Pattern-Check
        scored.append((jaccard, j))

    scored.sort(key=lambda x: -x[0])
    top = scored[:max_check]
    if len(top) < schwellwert:
        return None

    # Gruende zaehlen — `dismiss_reason` kann Plain-String oder JSON-Liste sein
    # (Database._serialize_job_row normalisiert das schon)
    reason_counter: Counter = Counter()
    by_reason: dict[str, list] = {}
    for _sim, j in top:
        reasons = j.get("dismiss_reasons") or []
        if not reasons and j.get("dismiss_reason"):
            reasons = [j["dismiss_reason"]]
        for r in reasons:
            r_clean = str(r).strip()
            if not r_clean:
                continue
            reason_counter[r_clean] += 1
            by_reason.setdefault(r_clean, []).append(j)

    if not reason_counter:
        return None

    top_reason, count = reason_counter.most_common(1)[0]
    if count < schwellwert:
        return None

    beispiele = [
        {
            "hash": (j.get("hash") or "")[-12:],
            "title": (j.get("title") or "")[:80],
            "company": (j.get("company") or "")[:60],
        }
        for j in by_reason[top_reason][:3]
    ]
    # #1004 AK 2: den Alttitel NENNEN. Er stand bisher nur unter
    # `beispiele`; gelesen wird zuerst dieser Satz — und ein Fehlalarm
    # faellt nur auf, wenn dabeisteht, worauf er sich stuetzt.
    _beleg = beispiele[0]["title"] if beispiele and beispiele[0].get("title") else ""
    risk_text = (
        f"Aufmerksamkeit: {count} aehnliche Stellen wurden wegen "
        f"'{top_reason}' aussortiert"
        + (f" (zuletzt: \"{_beleg}\")" if _beleg else "")
        + ". Pruefe ob das hier auch zutrifft."
    )
    return {
        "risk_text": risk_text,
        "top_grund": top_reason,
        "anzahl": count,
        "beispiele": beispiele,
    }




# #488: Quellen, die NICHT automatisch laufen — Claude soll den User
# VOR dem Start darueber informieren, damit er nicht 10 Minuten auf
# stumme Timeouts wartet. Begruendung siehe SOURCE_REGISTRY (veraltet/
# langsam/Claude-in-Chrome).
_MANUAL_SOURCES = {
    "linkedin": "LinkedIn (automatisch deaktiviert, #159) — nutze jobspy_linkedin oder Claude-in-Chrome",
    "xing": "XING (automatisch deaktiviert, #107) — nutze Claude-in-Chrome",
    "stepstone": "StepStone (Bot-Detection, #315) — nutze google_jobs_url oder Claude-in-Chrome",
    "indeed": "Indeed (haeufig Timeout) — nutze jobspy_indeed",
    "monster": "Monster (instabil) — nutze Claude-in-Chrome",
    "google_jobs": "Google Jobs (#501) — google_jobs_url aufrufen und in Chrome-Extension oeffnen",
}

# G17 (#744, v1.7.4): Bewaehrter Starter-Satz fuer den allerersten Suchlauf —
# schnell, zuverlaessig, ohne Login/Browser. Wird in der Ersterfassung
# (Wizard-Phase 5) und in der "keine_quellen"-Antwort empfohlen.
_SMART_DEFAULT_QUELLEN = ("bundesagentur", "arbeitnow", "jobspy_indeed")


def _maybe_auto_dismiss_after_search(db, job_id: str) -> None:
    """v1.7.0-beta.63 (#638 Stufe 1): Auto-Aussortierung nach Jobsuche.

    Bedingungen:
    - Lokale-KI aktiv (Ollama erreichbar + user_state='active')
    - Setting `auto_dismiss_after_search` ist True (Default True wenn KI aktiv)
    - Der Such-Job war erfolgreich (Status 'erledigt')

    Laeuft synchron im Background-Thread des Such-Jobs (nicht in einem
    neuen Thread), damit der `mit Ollama analysiert`-Schritt im jobsuche-
    Job sichtbar ist und User nicht parallel klicken kann was sich
    inkonsistent verhaelt.
    """
    import logging as _log
    log = _log.getLogger("bewerbungs_assistent.tools.jobs")
    try:
        # Setting pruefen
        setting = db.get_profile_setting("auto_dismiss_after_search", "true")
        if str(setting).lower() in ("false", "0", "no", "off"):
            log.info("auto_dismiss_after_search ist OFF — uebersprungen")
            return

        # Ollama-Status pruefen
        from ..services.llm_service import get_llm_service
        svc = get_llm_service(db)
        s = svc.get_status(force_refresh=False)
        if not s.ollama_available or s.user_state != "active":
            log.info(
                "auto_dismiss: Ollama nicht aktiv (avail=%s, state=%s) — uebersprungen",
                s.ollama_available, s.user_state,
            )
            return

        # Such-Job-Status pruefen.
        # v1.7.0-beta.65 (#638): run_search setzt status='fertig', NICHT
        # 'erledigt'. Der beta.63-Check auf 'erledigt' war falsch — der Hook
        # sprang IMMER raus und lief nie. Beide Werte akzeptieren.
        job = db.get_background_job(job_id)
        if not job or job.get("status") not in ("fertig", "erledigt"):
            log.info("auto_dismiss: Such-Job nicht fertig (status=%s) — uebersprungen",
                     job.get("status") if job else None)
            return

        # Erst die Stellen pruefen, dann auto-dismiss aufrufen
        active_jobs = db.get_active_jobs()
        if not active_jobs:
            log.info("auto_dismiss: keine aktiven Stellen — uebersprungen")
            return

        log.info(
            "auto_dismiss: starte stellen_auto_aussortieren nach Job %s (%d aktive Stellen)",
            job_id, len(active_jobs),
        )

        # Direkt die DB-/LLM-Logik aufrufen statt das MCP-Tool durchzugehen
        # (waere Wrapper-on-Wrapper). Wir nutzen den selben Code-Pfad via
        # Direktimport, ohne MCP-Decorator-Overhead.
        from ..services.llm_service import TaskKind, Backend
        # Limit auf 30 Stellen pro Auto-Run damit es nicht 10 Min Modell-RAM blockt
        max_pro_run = 30
        profile = db.get_profile() or {}
        profile_skills = [
            sk.get("name", "") for sk in (profile.get("skills") or [])[:15]
        ]
        positions = profile.get("positions") or []
        profile_position = positions[0].get("title", "") if positions else ""
        # #638 Stufe 3: Lernkontext einmal pro Auto-Run laden (statt pro Stelle)
        try:
            dismiss_reasons_raw = db.get_dismiss_reasons() or []
            # Top-3 nach usage_count
            dismiss_top = [
                {"reason": r.get("label"), "count": r.get("usage_count", 0)}
                for r in dismiss_reasons_raw[:3]
                if r.get("usage_count", 0) > 0
            ]
        except Exception:
            dismiss_top = []
        try:
            recent_dismissals = db.get_recent_user_dismissals(limit=10)
        except Exception:
            recent_dismissals = []
        bewertet = 0
        aussortiert = 0
        angereichert = 0
        try:
            for jobitem in active_jobs[:max_pro_run]:
                if jobitem.get("score") is not None and jobitem.get("score", 0) < 0:
                    continue
                # Skip wenn schon eine Bewerbung dazu existiert
                job_hash = jobitem.get("hash", "")
                try:
                    has_app = db.connect().execute(
                        "SELECT 1 FROM applications WHERE job_hash=? LIMIT 1",
                        (job_hash,)
                    ).fetchone()
                except Exception:
                    has_app = None
                if has_app:
                    continue
                desc = (jobitem.get("description") or "").strip()
                payload = {
                    "job_title": jobitem.get("title", ""),
                    "job_company": jobitem.get("company", ""),
                    "job_description": desc[:1500],
                    "profile_position": profile_position,
                    "profile_skills": profile_skills,
                    # #638 Stufe 3: Few-Shot-Lernschleife
                    "dismiss_reasons_top": dismiss_top,
                    "recent_dismissals": recent_dismissals,
                }
                try:
                    # v1.7.0-beta.65 (#638): FIX — Methode heisst run() nicht
                    # run_task(); Parser liefert 'decision' nicht 'verdict'.
                    # In beta.63 lief der Hook deshalb nie durch (AttributeError
                    # wurde verschluckt). Jetzt korrekt.
                    result = svc.run(TaskKind.MATCH_JOB_TO_SKILLS, payload)
                except Exception:
                    continue
                bewertet += 1
                if not result.success or not result.payload:
                    continue
                decision = (result.payload.get("decision") or "").upper()
                reason = result.payload.get("reason", "") or ""
                if decision == "PASST_NICHT":
                    try:
                        db.dismiss_job(
                            jobitem.get("hash", ""),
                            reason=f"auto:profil_match_negativ:{reason[:120]}",
                            # #1010: Herkunft explizit. Das `auto:`-Praefix
                            # ueberlebt die Normalisierung aus #913 NICHT —
                            # aus dem gespeicherten Grund waere die
                            # Automatik danach nicht mehr erkennbar.
                            herkunft="automatik",
                        )
                        aussortiert += 1
                    except Exception:
                        pass
                elif decision == "PASST":
                    # v1.7.0-beta.65 (#638 Stufe 2): Score-Anreicherung.
                    # Stellen ohne (oder mit duenner) Beschreibung haben oft
                    # Score 0 und versacken unten in der Liste — obwohl Ollama
                    # sie als passend einstuft. Wir heben sie auf einen
                    # moderaten Score damit sie sichtbar werden. Nur wenn
                    # noch nicht hoeher bewertet + nicht gepinnt.
                    cur_score = jobitem.get("score") or 0
                    thin_desc = len(desc) < 120
                    if thin_desc and cur_score < 35 and not jobitem.get("is_pinned"):
                        try:
                            db.update_job(jobitem.get("hash", ""),
                                          {"score": 35})
                            angereichert += 1
                        except Exception:
                            pass
        except Exception as exc:
            log.warning("auto_dismiss-Schleife abgebrochen: %s", exc)

        # Ergebnis im Background-Job vermerken.
        # v1.7.0-beta.65 (#638): Feld heisst 'result' (nicht 'ergebnis'),
        # update_background_job-kwarg ebenfalls 'result='. Status 'fertig'
        # erhalten (nicht auf 'erledigt' umbiegen). beta.63 nutzte falsche
        # Namen -> TypeError verschluckt -> nichts gespeichert.
        try:
            job = db.get_background_job(job_id)
            result_data = job.get("result") or {}
            if not isinstance(result_data, dict):
                result_data = {}
            result_data["auto_aussortiert"] = {
                "bewertet": bewertet,
                "aussortiert": aussortiert,
                "score_angereichert": angereichert,
                "von_aktiven": len(active_jobs),
            }
            db.update_background_job(
                job_id, job.get("status", "fertig"),
                progress=job.get("progress", 100),
                message=job.get("message", ""),
                result=result_data,
            )
        except Exception as exc:
            log.warning("auto_dismiss: Ergebnis-Speicherung fehlgeschlagen: %s", exc)

        log.info(
            "auto_dismiss: fertig — %d/%d bewertet, %d aussortiert, %d angereichert",
            bewertet, max_pro_run, aussortiert, angereichert,
        )

    except Exception as exc:
        # Nicht-fatal — Auto-Dismiss ist optional, Suche selbst war OK
        log.warning("auto_dismiss-Hook fehlgeschlagen (ignoriert): %s", exc)


def register(mcp, db, logger):
    """Registriert Jobsuche-Tools."""
    from . import ki_gate, time_tool

    @mcp.tool()
    def jobsuche_starten(
        keywords: list[str] = None,
        quellen: list[str] = None,
    ) -> dict:
        """Startet eine Jobsuche im Hintergrund auf allen konfigurierten Portalen.

        VORAUSSETZUNGEN:
        1. Mindestens eine Quelle muss aktiviert sein (Dashboard → Einstellungen → Job-Quellen)
        2. Suchkriterien sollten gesetzt sein (suchkriterien_setzen)

        Die Suche dauert 5-10 Minuten. Prüfe den Fortschritt mit jobsuche_status().
        Ergebnisse danach mit stellen_anzeigen() ansehen.

        HINWEIS #488: Wenn aktive Quellen dabei sind, die nur ueber
        Claude-in-Chrome laufen (LinkedIn, StepStone, XING, Indeed,
        Monster, Google Jobs), meldet dieses Tool sie im Feld
        `manuelle_quellen` zurueck UND ueberspringt sie im
        Hintergrund-Job — statt auf stumme Timeouts zu laufen. Claude
        soll den User vor dem Start ueber diese Quellen informieren und
        ihm empfehlen, sie via Chrome-Extension anzusteuern.

        ENTFERNUNG UND REMOTE (#1000, v1.7.48): dieses Tool hatte bis
        v1.7.47 die Parameter `nur_remote` und `max_entfernung_km`. Beide
        wurden entgegengenommen und von niemandem gelesen. Sie sind
        ersatzlos entfallen, weil ein Parameter ohne Wirkung schlechter
        ist als keiner. Was stattdessen wirkt:

        * Entfernung: `suchkriterien_setzen(max_entfernung_km=30)` —
          gilt dauerhaft und fuer jeden Lauf. Entfernung ist dabei ein
          PREIS im Score, kein Ausschluss (#910/#988): eine weite Stelle
          rutscht nach unten, statt zu verschwinden.
        * Remote: "Remote" gehoert in `regionen`, und das Gewicht dafuer
          steht in `gewichtung.remote`. Ein harter Remote-Filter waere
          gefaehrlich, weil sehr viele Anzeigen gar keine Angabe zum
          Arbeitsmodell machen — er wuerde vor allem Unbekanntes
          wegwerfen (#989).

        Args:
            keywords: Suchbegriffe (Standard: aus Profil)
            quellen: Welche Portale durchsuchen (Standard: alle aktiven)
        """
        # #425: KI-Gate. Dashboard-Button bleibt unabhaengig nutzbar.
        gate = ki_gate(db, "jobsuche")
        if gate is not None:
            gate["alternative"] = (
                "Dashboard -> Stellen -> 'Jetzt suchen' laeuft unabhaengig "
                "vom KI-Toggle und nutzt deine aktiven Quellen."
            )
            return gate

        # Default sources from DB settings (all disabled by default)
        if not quellen:
            quellen = db.get_profile_setting("active_sources", [])
            if not quellen:
                return {
                    "status": "keine_quellen",
                    # G17 (#744, v1.7.4): Einsteiger nicht in den Einstellungs-
                    # Tab schicken, sondern den bewaehrten Starter-Satz anbieten
                    # (schnell, zuverlaessig, ohne Login).
                    "empfohlene_start_quellen": list(_SMART_DEFAULT_QUELLEN),
                    "nachricht": (
                        "Keine Job-Quellen aktiviert. Empfehlung fuer den "
                        "ersten Lauf: jobsuche_starten(quellen="
                        f"{list(_SMART_DEFAULT_QUELLEN)}) — schnelle, "
                        "zuverlaessige Quellen ohne Login. Sie werden dabei "
                        "als aktive Quellen uebernommen. Weitere Quellen: "
                        "Dashboard → Einstellungen → Job-Quellen."
                    ),
                }

        # #695: Ohne Suchbegriffe nicht starten — sonst faellt z.B. der
        # Bundesagentur-Adapter still auf generische DEFAULT_KEYWORDS zurueck
        # und flutet die Stellen-Liste eines Neulings mit profil-fremden Jobs.
        if not keywords:
            crit = db.get_search_criteria()
            if not (crit.get("keywords_muss") or crit.get("keywords_plus")):
                return {
                    "status": "keine_suchbegriffe",
                    "nachricht": (
                        "Noch keine Suchkriterien gesetzt. Lege sie mit "
                        "suchkriterien_setzen() fest oder nutze "
                        "workflow_starten('jobsuche_workflow') — sonst wuerde "
                        "PBP mit generischen Begriffen suchen."
                    ),
                }

        # #488: Manuelle/deprecated Quellen rausfiltern und separat melden.
        manuelle = [q for q in quellen if q in _MANUAL_SOURCES]
        auto_quellen = [q for q in quellen if q not in _MANUAL_SOURCES]
        manuelle_info = {q: _MANUAL_SOURCES[q] for q in manuelle}

        if not auto_quellen:
            return {
                "status": "nur_manuelle_quellen",
                "manuelle_quellen": manuelle_info,
                "nachricht": (
                    "Alle ausgewaehlten Quellen laufen nur ueber Claude-in-Chrome "
                    "oder sind deprecated — es gibt nichts zu automatisieren. "
                    "Siehe manuelle_quellen fuer den jeweiligen Ersatzweg."
                ),
            }
        quellen = auto_quellen

        # G17 (#744, v1.7.4): Erster Lauf mit explizit uebergebenen Quellen
        # (z.B. Smart-Defaults aus der Ersterfassung, nach User-Ok) — als
        # aktive Quellen uebernehmen, damit Dashboard-Button ("Jetzt suchen")
        # und Tagesroutine dieselben Quellen nutzen. Nur wenn noch KEINE
        # gesetzt sind; bestehende Konfiguration wird nie ueberschrieben.
        quellen_uebernommen = False
        try:
            if not db.get_profile_setting("active_sources", []):
                db.set_profile_setting("active_sources", quellen)
                quellen_uebernommen = True
        except Exception as e:
            logger.debug("active_sources-Uebernahme fehlgeschlagen: %s", e)

        # Prevent duplicate concurrent searches (#265)
        existing = db.get_running_background_job("jobsuche")
        if existing:
            return {
                "status": "laeuft_bereits",
                "job_id": existing["id"],
                "nachricht": "Eine Jobsuche läuft bereits. "
                            f"Prüfe den Fortschritt mit jobsuche_status('{existing['id']}')."
            }

        params = {
            "keywords": keywords,
            "quellen": quellen,
        }
        job_id = db.create_background_job("jobsuche", params)

        # Start background search with timeout
        def _run_search():
            # v1.7.17 (#915): im DB-freien Register anmelden, damit ein
            # Budget-Timeout anderer Tools den Sperrhalter benennen kann.
            from ..services.hintergrund_status import laufender_task
            try:
                with laufender_task(f"jobsuche:{job_id[:8]}"):
                    from ..job_scraper import run_search
                    run_search(db, job_id, params)
                    # v1.7.0-beta.63 (#638 Stufe 1): Auto-Aussortierung nach
                    # erfolgreicher Suche — laeuft im selben Background-Thread
                    # damit User keine extra Aktion machen muss.
                    _maybe_auto_dismiss_after_search(db, job_id)
            except Exception as e:
                logger.error("Jobsuche fehlgeschlagen: %s", e, exc_info=True)
                db.update_background_job(job_id, "fehler", message=str(e))

        thread = threading.Thread(target=_run_search, daemon=True)
        thread.start()

        # Timeout watchdog: mark as failed if still running after 10 minutes
        def _timeout_watchdog():
            thread.join(timeout=600)
            if thread.is_alive():
                logger.warning("Jobsuche Timeout nach 10 Minuten (Job %s)", job_id)
                db.update_background_job(job_id, "fehler", message="Timeout nach 10 Minuten")

        threading.Thread(target=_timeout_watchdog, daemon=True).start()

        nachricht = (
            f"Jobsuche laeuft im Hintergrund auf {len(params['quellen'])} Portalen. "
            f"Das dauert 5-10 Minuten — du musst jetzt NICHT warten. "
            f"Die Status-Badge in der Sidebar zeigt den Fortschritt. "
            f"Wenn du spaeter prueft willst: jobsuche_status('{job_id}'). "
            f"Wenn fertig: stellen_anzeigen()."
        )
        result = {
            "job_id": job_id,
            "status": "gestartet",
            "nachricht": nachricht,
        }
        if quellen_uebernommen:
            result["quellen_als_aktiv_uebernommen"] = quellen
        if manuelle_info:
            result["manuelle_quellen"] = manuelle_info
            result["hinweis"] = (
                "Zusaetzlich muesstest du fuer folgende manuelle Quellen "
                "Claude-in-Chrome oder die jeweiligen Ersatzwerkzeuge nutzen — "
                "sie sind im Hintergrund-Job NICHT enthalten."
            )
        # v1.7.17 (#906 Befund 2): totes Suchkriterium benennen. Der
        # Nutzer suchte monatelang nur Festanstellung, obwohl sein Profil
        # auch freelance sagte — ALLE Freelance-Quellen waren aus, und
        # nichts wies darauf hin. Ein Kriterium, das niemand auswertet,
        # ist schlimmer als ein fehlendes: es erzeugt falsche Sicherheit.
        try:
            from ..job_scraper import STELLENTYP_QUELLEN
            _typen = db.get_search_criteria().get("stellentypen") or []
            _laufende = set(params.get("quellen") or [])
            for _typ in _typen:
                _noetig = STELLENTYP_QUELLEN.get(_typ)
                if _noetig and not (_noetig & _laufende):
                    result.setdefault("stellentyp_ohne_quelle", []).append({
                        "stellentyp": _typ,
                        "quellen_dafuer": sorted(_noetig),
                        "warnung": (
                            f"Fuer '{_typ}' laeuft in dieser Suche KEINE "
                            f"Quelle ({', '.join(sorted(_noetig))} alle "
                            "inaktiv/defekt). Die zugehoerigen Kriterien "
                            "werden nicht ausgewertet. Alternativen: "
                            "die Quellen-Seite im Browser oeffnen "
                            "oder scraper_diagnose(aktion='reaktivieren')."
                        ),
                    })
        except Exception as exc:
            logger.debug("Stellentyp-Warnung (#906) uebersprungen: %s", exc)
        return result

    @mcp.tool()
    def jobsuche_status(job_id: str) -> dict:
        """Prüft den Fortschritt einer laufenden Jobsuche.

        Args:
            job_id: Job-ID von jobsuche_starten()
        """
        job = db.get_background_job(job_id)
        if job is None:
            return {"fehler": "Unbekannte Job-ID"}
        # v1.6.5 (#549): bereinigung wurde sowohl in `ergebnis.bereinigung`
        # als auch top-level zurueckgegeben — doppelt. Wir extrahieren sie
        # einmalig auf top-level und entfernen sie aus `ergebnis`.
        ergebnis = None
        bereinigung = None
        if job["status"] == "fertig" and isinstance(job.get("result"), dict):
            ergebnis = dict(job["result"])
            bereinigung = ergebnis.pop("bereinigung", None)
        elif job["status"] == "fertig":
            ergebnis = job["result"]
        result = {
            "status": job["status"],
            "fortschritt": f"{job['progress']}%",
            "nachricht": job["message"],
            "ergebnis": ergebnis,
        }
        if bereinigung:
            result["bereinigung"] = bereinigung
        return result

    # Standard rejection reasons for learning (#66).
    # v1.7.17 (#913): das Vokabular lebt jetzt zentral in
    # services/ablehnungsgruende.py — inkl. der neuen regulaeren Gruende
    # falsches_system (Fachgebiet stimmt, Plattform nicht) und
    # falsche_branche (Rolle stimmt, Branche nicht). Alle Schreibpfade
    # auf jobs.dismiss_reason laufen durch dieselbe Normalisierung
    # (verdrahtet in db.dismiss_job); Freitext landet in dismiss_note.
    from ..services.ablehnungsgruende import STANDARD_GRUENDE
    ABLEHNUNGSGRUENDE = list(STANDARD_GRUENDE)

    def _detect_duplicate(job_hash: str) -> dict | None:
        """Duplikat-Erkennung (#168): Prüft ob eine ähnliche Stelle existiert."""
        job = db.get_job(job_hash)
        if not job:
            return None
        title = (job.get("title") or "").lower()
        company = (job.get("company") or "").lower()
        if not title or not company:
            return None

        # Check existing applications
        apps = db.get_applications()
        for app in apps:
            app_title = (app.get("title") or "").lower()
            app_company = (app.get("company") or "").lower()
            if company in app_company or app_company in company:
                # Company match — check title similarity
                title_words = set(title.split())
                app_words = set(app_title.split())
                overlap = title_words & app_words
                if len(overlap) >= min(2, len(title_words)):
                    return {
                        "typ": "bewerbung",
                        "id": app["id"][:8],
                        "titel": app.get("title"),
                        "firma": app.get("company"),
                        "status": app.get("status"),
                    }

        # Check existing dismissed jobs with same company
        dismissed = db.get_dismissed_jobs()
        for dj in dismissed:
            dj_company = (dj.get("company") or "").lower()
            dj_title = (dj.get("title") or "").lower()
            if company in dj_company or dj_company in company:
                title_words = set(title.split())
                dj_words = set(dj_title.split())
                overlap = title_words & dj_words
                if len(overlap) >= min(2, len(title_words)):
                    return {
                        "typ": "aussortierte_stelle",
                        "hash": dj["hash"][:8],
                        "titel": dj.get("title"),
                        "firma": dj.get("company"),
                        "grund": dj.get("dismiss_reason"),
                    }
        return None

    def _normalize_dismiss_reason(reason: str) -> str:
        """Normalisiere Freitext-Ablehnungsgründe auf Standard-Keywords (#158).

        v1.7.17 (#913): delegiert an die EINE zentrale Normalisierung —
        vorher gab es hier eine eigene, unvollstaendige Musterliste,
        waehrend andere Schreibpfade komplett daran vorbeischrieben.
        """
        from ..services.ablehnungsgruende import _kanonisch_einzeln
        erlaubt = set(ABLEHNUNGSGRUENDE) | _get_active_custom_reasons_lower()
        grund, _freitext = _kanonisch_einzeln(reason, erlaubt)
        return grund

    def _get_active_custom_reasons_lower() -> set:
        try:
            rows = db.get_dismiss_reasons() or []
            return {r["label"].lower() for r in rows
                    if r.get("is_custom") and r.get("is_active", 1)}
        except Exception:
            return set()

    def _auto_adjust_scoring(db_ref, reason: str, count: int) -> str | None:
        """#110: Automatische Scoring-Anpassung bei wiederholten Ablehnungsmustern.

        Bug #269: Seed-Daten haben profile_id='', daher muss mit
        (profile_id=? OR profile_id='') gesucht werden.
        """
        # v1.7.17 (#917/#908): Die Automatik setzt KEIN ignore_flag mehr —
        # "schaerfer statt aus". Der Nutzer wollte Stellenarten abgewertet,
        # nicht ausgeblendet (Recall vor Praezision); die Flags waren zudem
        # ueber MCP nicht zuruecknehmbar (#917 Defekt A). Jeder Grund traegt
        # (dimension, sub_key, start_malus, max_malus).
        #
        # Entfernung (#917 Defekt C): Ziel-Stufe ist '999' — die Brackets
        # sind OBERGRENZEN ("Malus fuer Stellen BIS X km"). Der alte
        # Schluessel '50km' landete via Ziffern-Extraktion im Bracket 50
        # und bestrafte damit Stellen ZWISCHEN 30 und 50 km — genau den
        # Bereich, den der Nutzer will. Der Lerneffekt war invertiert.
        #
        # zu_junior ist BEWUSST raus (#908 Befund 4): es mappte auf
        # stellentyp/praktikum — ausgeloest aber von Festanstellungen
        # ("mind. 2 Jahre Erfahrung"), die der Hebel nie erreicht.
        # Senioritaet ist keine Stellenart; der Weg sind MINUS-Keywords
        # (Hint unten in _apply_dismiss_with_lifecycle).
        LEARN_MAP = {
            "zu_weit_entfernt": ("entfernung_fest", "999", -2, -10),
            "zeitarbeit": ("stellentyp", "zeitarbeit", -2, -8),
            "befristet": ("stellentyp", "befristet", -2, -6),
        }
        if reason not in LEARN_MAP:
            return None
        dim, sub, start_malus, max_malus = LEARN_MAP[reason]
        conn = db_ref.connect()
        pid = db_ref.get_active_profile_id() or ""
        # #269: Seed-Daten haben profile_id='' — beides prüfen
        existing = conn.execute(
            "SELECT id, value, ignore_flag, profile_id, set_by_user "
            "FROM scoring_config "
            "WHERE (profile_id=? OR profile_id='') AND dimension=? AND sub_key=? "
            "ORDER BY CASE WHEN profile_id=? THEN 0 ELSE 1 END LIMIT 1",
            (pid, dim, sub, pid)
        ).fetchone()
        # v1.7.17 (#917): explizite Nutzer-Entscheidung ist unantastbar.
        # Belegt: Nutzer schaltete das Ignorieren ab, die naechste
        # Aussortierung mit demselben Grund (Zaehler 71, Schwelle 5)
        # kehrte sie kommentarlos wieder um.
        if existing and existing["set_by_user"]:
            return None
        # #908 Befund 5: die alte Formel (count-5)*0.5 erreichte den
        # Deckel schon bei ~13 Nennungen — faktisch ein Zweistufen-
        # Schalter. Jetzt linear ueber den realen Nennungsbereich:
        # Schwelle 5 = start_malus, ab 155 Nennungen = max_malus,
        # dazwischen gleichmaessig (halbe Punkte, monoton).
        fortschritt = min(1.0, max(0.0, (count - 5) / 150.0))
        new_val = start_malus + (max_malus - start_malus) * fortschritt
        new_val = round(new_val * 2) / 2
        alt_val = existing["value"] if existing else None
        if existing:
            if existing["value"] <= new_val:
                return None  # already penalized enough
            conn.execute(
                "UPDATE scoring_config SET value=? WHERE id=?",
                (new_val, existing["id"])
            )
        else:
            conn.execute(
                "INSERT INTO scoring_config (profile_id, dimension, sub_key, value, ignore_flag, created_at) "
                "VALUES (?, ?, ?, ?, 0, ?)",
                (pid, dim, sub, new_val, __import__("datetime").datetime.now().isoformat())
            )
        conn.commit()
        # #908 Punkt 6: alt->neu benennen und den Rueckweg gleich mitgeben
        # — eine Automatik, die den Bestand umgewichtet, muss revidierbar
        # sein. Landet via auto_adjustments/hints beim Nutzer UND im Log.
        logger.info("Auto-Scoring (#908): '%s' -> %s/%s Malus %s -> %s "
                    "(Nennungen: %d)", reason, dim, sub, alt_val, new_val,
                    count)
        return (f"'{reason}' → {dim}/{sub} Malus "
                f"{alt_val if alt_val is not None else 'Default'} → {new_val} "
                f"(zuruecknehmbar via scoring_konfigurieren('setzen'/"
                f"'loeschen', '{dim}', '{sub}'))")

    def _apply_dismiss_with_lifecycle(job_hash: str, reason_list: list[str],
                                       collect_hints: bool = True,
                                       skip_auto_adjust: bool = False) -> dict:
        """Wendet 'aussortieren' auf eine Stelle an mit voller PBP-Lifecycle-Logik.

        Geht durch alle Hooks: dismiss_counts, blacklist-hint, auto-adjust-scoring,
        dismiss_reasons-Statistik. Wird von stelle_bewerten UND von
        stellen_bulk_bewerten aufgerufen, damit Audit/Lerneffekt/Statistik in
        beiden Wegen identisch durchlaufen (#514: Anti-DB-Bypass-Pattern).

        Args:
            job_hash: Hash der Stelle
            reason_list: bereits validierte/normalisierte Gruende
            collect_hints: bei Bulk auf False setzen — Tipps werden dann nur
                in der Aggregat-Antwort summiert, nicht pro Einzelaufruf
            skip_auto_adjust: v1.6.5 (#558) — Bulk-Path uebernimmt den
                Auto-Adjust selbst (einmalig am Ende). Verhindert dass jeder
                der 100 Einzelaufrufe das Scoring weiter eskaliert (Drift).
        """
        import json as _json
        reason_str = _json.dumps(reason_list, ensure_ascii=False) if len(reason_list) > 1 else reason_list[0]

        # #168: Duplikat-Erkennung
        dup_info = None
        if "duplikat" in reason_list:
            dup_info = _detect_duplicate(job_hash)

        db.dismiss_job(job_hash, reason_str)

        # Track rejection counts for learning (#66)
        counts = db.get_setting("dismiss_counts", {})
        hints = []
        for g in reason_list:
            normalized = g.lower().strip()
            counts[normalized] = counts.get(normalized, 0) + 1

            # Suggest scoring adjustments (#169) when patterns are strong
            # v1.7.17 (#908): kein Vorschlag lautet mehr "Komplett
            # Ignorieren" — ein wiederholt genutzter Grund ist ein
            # RELEVANTER Grund und gehoert verschaerft, nicht
            # abgeschaltet. ignore_flag setzt nur noch der Nutzer selbst.
            if collect_hints and counts.get(normalized, 0) >= 3:
                if normalized == "zu_weit_entfernt":
                    hints.append("Tipp: Passe den Entfernungs-Malus im Scoring-Regler an (scoring_konfigurieren, Stufe '999' = jenseits aller Grenzen).")
                elif normalized == "gehalt_zu_niedrig":
                    hints.append("Tipp: Passe den Gehalts-Regler im Scoring an (scoring_konfigurieren).")
                elif normalized in ("zeitarbeit", "befristet"):
                    hints.append(
                        f"Tipp: Der Malus fuer '{g}' eskaliert automatisch mit. "
                        f"Noch schaerfer: scoring_konfigurieren('setzen', 'stellentyp', '{normalized}', wert=-8). "
                        "Komplett ausblenden nur bewusst mit ignorieren=True."
                    )
                elif normalized == "zu_junior" and counts.get(normalized, 0) % 10 == 3:
                    # #908 Befund 4: Senioritaet ist keine Stellenart —
                    # der wirksame Hebel sind MINUS-Keywords, die auch
                    # Festanstellungen erreichen. Vorschlag statt
                    # Automatik; gedrosselt (jede 10. Nennung).
                    hints.append(
                        "Tipp: 'zu_junior' lernt ueber MINUS-Keywords, nicht ueber die Stellenart. "
                        "Kandidaten: suchkriterien_bearbeiten(aktion='hinzufuegen', kategorie='minus', "
                        "werte=['Junior', 'Berufseinsteiger', 'Entry Level', 'Trainee']) — "
                        "Gewicht schaerfen via kategorie='gewichten' (#778). Keine Duplikate anlegen."
                    )
                elif normalized == "falsches_fachgebiet" and counts.get(normalized, 0) % 25 == 0:
                    # #908 Befund 3: das staerkste Signal (1200+ Nennungen)
                    # erzeugte NULL Lerneffekt. Der Lerneffekt liegt in den
                    # Begriffen — keyword_vorschlaege rechnet die
                    # MINUS-Kandidaten mit Belegen vor, der Nutzer
                    # entscheidet. Stark gedrosselt (jede 25. Nennung).
                    hints.append(
                        f"Hinweis: '{normalized}' wurde inzwischen {counts[normalized]}x genutzt. "
                        "keyword_vorschlaege() schlaegt daraus MINUS-Kandidaten mit Trefferzahlen "
                        "und Beispielstellen vor — so lernt der Score aus dem haeufigsten Grund."
                    )
                elif normalized == "firma_uninteressant":
                    job = db.get_job(job_hash)
                    company = (job or {}).get("company", "")
                    # #729: Hinweis nur wenn die Firma noch NICHT auf der
                    # Blacklist steht — sonst schlaegt PBP etwas vor, das schon
                    # erledigt ist.
                    if company and not db.is_company_blacklisted(company):
                        hints.append(
                            f"Tipp: Moechtest du '{company}' auf die Blacklist setzen? "
                            f"Nutze blacklist_verwalten('hinzufuegen', 'firma', '{company}')."
                        )

        db.set_setting("dismiss_counts", counts)
        db.increment_dismiss_reason_usage(reason_list)

        # #110: Lernender Score — automatische Scoring-Anpassungen bei starken Mustern.
        # v1.6.5 (#558): Bei Bulk wird das einmalig am Ende ausgefuehrt, nicht
        # pro Einzelaufruf. Sonst eskaliert (count-5)*0.5 mit jedem Job und
        # treibt den Score-Malus immer weiter ins Negative ("Score-Drift").
        auto_adjustments = []
        if not skip_auto_adjust:
            for g in reason_list:
                normalized = g.lower().strip()
                cnt = counts.get(normalized, 0)
                if cnt >= 5:
                    _auto = _auto_adjust_scoring(db, normalized, cnt)
                    if _auto:
                        auto_adjustments.append(_auto)
            if collect_hints and auto_adjustments:
                hints.append("Scoring wurde automatisch angepasst: " + "; ".join(auto_adjustments))

        return {
            "counts": counts,
            "hints": hints,
            "auto_adjustments": auto_adjustments,
            "duplikat_info": dup_info,
        }

    def _get_active_custom_reasons() -> set:
        """v45 (#663 C20, beta.85): Zusaetzlich erlaubte Custom-Gruende
        aus der DB. is_custom=1 AND is_active=1. Kann fehlschlagen wenn
        is_active-Spalte (noch) nicht da ist — dann leerer Set."""
        try:
            rows = db.get_dismiss_reasons() or []
            return {
                r["label"] for r in rows
                if r.get("is_custom") and r.get("is_active", 1)
            }
        except Exception:
            return set()

    def _normalize_reason_list(grund: str = "", gruende: list[str] = None) -> list[str]:
        """Normalisiert Eingabe-Gruende auf erlaubte Werte (#302).

        v45 (#663 C20, beta.85): Custom-Gruende des Users (aus
        dismiss_reasons-Tabelle, is_custom=1, is_active=1) sind
        zusaetzlich zur ABLEHNUNGSGRUENDE-Whitelist erlaubt — der
        User hat sie explizit angelegt.
        """
        custom_allowed = _get_active_custom_reasons()
        allowed = set(ABLEHNUNGSGRUENDE) | custom_allowed
        raw_reasons = [_normalize_dismiss_reason(r) for r in (gruende or ([grund] if grund else []))]
        return list(dict.fromkeys(
            r if r in allowed else "sonstiges" for r in raw_reasons
        ))

    @mcp.tool()
    @time_tool(logger, "stelle_bewerten")
    def stelle_bewerten(job_hash: str, bewertung: str, grund: str = "",
                        gruende: list[str] = None) -> dict:
        """Bewertet eine gefundene Stelle.

        Bei 'passt_nicht' wird der Grund gespeichert und für künftige Suchen gelernt.
        Häufig genutzte Gründe führen automatisch zu Gewichtungsanpassungen.

        STRENG VERBOTEN: Die KI darf KEINE eigenen Ablehnungsgruende erfinden,
        generieren oder formulieren! Auch keine "intelligenten" Gruende wie
        "Duplikat — bereits als Bewerbung xyz erfasst". AUSSCHLIESSLICH die
        vordefinierten Gruende aus der Liste unten verwenden. Bei Unsicherheit
        den Nutzer fragen oder 'sonstiges' waehlen. Jeder nicht-vordefinierte
        Grund wird automatisch auf 'sonstiges' normalisiert.

        FUER MEHRERE STELLEN AUF EINMAL: Nutze 'stellen_bulk_bewerten' mit
        Filtern wie min_score, titel_enthaelt_nicht, beschreibung_enthaelt_nicht.
        Spart Tokens und respektiert die PBP-Lifecycle-Logik (#514).

        Args:
            job_hash: Hash der Stelle
            bewertung: 'passt' oder 'passt_nicht'
            grund: Einzelner Grund bei passt_nicht (Legacy, nutze besser gruende)
            gruende: Liste von Gruenden bei passt_nicht (Multi-Select, #108).
                ERLAUBTE WERTE (nur diese, nichts anderes!):
                zu_weit_entfernt, gehalt_zu_niedrig, falsches_fachgebiet,
                zu_junior, zu_senior, unpassendes_arbeitsmodell,
                firma_uninteressant, zeitarbeit, befristet, bereits_beworben,
                duplikat, kein_hochschulabschluss, sonstiges
        """
        # #695: Existenz-Guard — vorher meldete das Tool bei unbekanntem Hash
        # "aussortiert"/"als_passend_markiert" und zaehlte sogar die
        # Ablehnungs-Statistik hoch (Phantom-Eintraege im Lerneffekt).
        if not db.get_job(job_hash):
            return {"fehler": "Stelle nicht gefunden. "
                              "Pruefe den Hash mit stellen_anzeigen()."}

        if bewertung == "passt_nicht":
            reason_list = _normalize_reason_list(grund, gruende)
            if not reason_list:
                return {
                    "fehler": "Mindestens ein Ablehnungsgrund ist erforderlich.",
                    "verfuegbare_gruende": ABLEHNUNGSGRUENDE,
                }

            ctx = _apply_dismiss_with_lifecycle(job_hash, reason_list, collect_hints=True)
            counts = ctx["counts"]
            hints = ctx["hints"]
            dup_info = ctx["duplikat_info"]

            result = {
                "status": "aussortiert",
                "gruende": reason_list,
                "ablehnungs_statistik": {k: v for k, v in sorted(counts.items(), key=lambda x: -x[1])[:5]},
                "hinweise": hints if hints else None,
                "verfuegbare_gruende": ABLEHNUNGSGRUENDE,
            }
            if dup_info:
                result["duplikat_erkannt"] = dup_info
            return result
        elif bewertung == "passt":
            # v1.7.0-beta.28 (#594 Stufe 3): LLM-Correction-Loop. Wenn die
            # Stelle vorher von der LLM via Auto-Aussortierung weggeraeumt
            # wurde (`dismiss_reason='profil_match_negativ'`), dann ist das
            # eine Korrektur durch den User — Trainingsmaterial fuer die
            # adaptive Prompts.
            try:
                from ..tools.jobs import _resolve  # type: ignore
            except Exception:
                _resolve = None
            try:
                conn = db.connect()
                resolved_hash = db.resolve_job_hash(job_hash)
                if resolved_hash:
                    row = conn.execute(
                        "SELECT title, company, dismiss_reason FROM jobs "
                        "WHERE hash=?", (resolved_hash,)
                    ).fetchone()
                    if row and (row["dismiss_reason"] or "") == "profil_match_negativ":
                        # User korrigiert die LLM-Entscheidung
                        try:
                            db.add_activity_event({
                                "event_type": "llm_correction",
                                "entity_type": "job",
                                "entity_id": resolved_hash,
                                "page": "stellen",
                                "action": "user_overrides_dismiss",
                                "metadata": {
                                    "title": row["title"],
                                    "company": row["company"],
                                    "previous_dismiss_reason":
                                        row["dismiss_reason"],
                                },
                                "learning_enabled":
                                    db.is_learning_enabled(),
                            })
                        except Exception:
                            pass
            except Exception:
                pass
            db.restore_job(job_hash)
            return {"status": "als_passend_markiert"}
        return {"fehler": "Ungültige Bewertung. Nutze 'passt' oder 'passt_nicht'."}

    @mcp.tool()
    def stelle_analyse_speichern(job_hash: str, urteil: str,
                                 begruendung: str = "",
                                 grundlage: str = "detailanalyse") -> dict:
        """Legt das Ergebnis einer Detailanalyse AN DER STELLE ab (#1007).

        Args:
            job_hash: Hash der Stelle.
            urteil: EMPFOHLEN | BEDINGT | NICHT_EMPFOHLEN |
                NICHT_BEURTEILBAR.
            begruendung: warum — in einem oder zwei Saetzen, so wie du
                es dem Menschen sagen wuerdest.
            grundlage: woher das Urteil stammt. Vorgabe
                'detailanalyse' (du hast Anzeige und Profil gelesen).

        **Wofuer das da ist.** Bis v1.7.60 kam die Empfehlung aus dem
        Suchbegriff-Score — in den geht der Lebenslauf nicht ein. Seit
        #1003 sagt PBP ohne gelesene Analyse ehrlich
        `NICHT_BEURTEILBAR`. Dein Urteil hier ist das, was diese Luecke
        schliesst: es haengt danach an der Stelle, steht in der
        Trefferliste und ueberlebt das Gespraech.

        **Voraussetzung: du hast die Anzeige WIRKLICH gegen das Profil
        gelesen.** Ein Urteil, das aus dem Score abgeleitet ist, waere
        genau der Fehler, den #1003 behebt — nur diesmal von Hand.
        Nutze `fit_analyse` fuer die Fakten und `projekte_anzeigen` /
        `profil_zusammenfassung` fuer das Profil.

        Ein Urteil ausserhalb der vier Kategorien wird abgewiesen, nicht
        stillschweigend umgedeutet.
        """
        try:
            geschrieben = db.set_job_analysis(
                job_hash, urteil, begruendung, grundlage)
        except ValueError as exc:
            return {"fehler": str(exc)}
        if not geschrieben:
            return {
                "fehler": "Stelle nicht gefunden.",
                "hinweis": "Pruefe den Hash mit stellen_anzeigen().",
            }
        return {
            "status": "gespeichert",
            "urteil": urteil.strip().upper(),
            "grundlage": grundlage or "detailanalyse",
            "hinweis": ("Der Befund haengt jetzt an der Stelle und "
                        "erscheint in der Trefferliste. Aendert sich dein "
                        "Profil, wird er als moeglicherweise ueberholt "
                        "gekennzeichnet — nicht geloescht."),
        }

    @mcp.tool()
    def stelle_analyse_loeschen(job_hash: str) -> dict:
        """Entfernt den gespeicherten Analyse-Befund einer Stelle (#1007).

        Fuer den Fall, dass das Urteil falsch war. Danach steht die
        Stelle wieder auf `NICHT_BEURTEILBAR` — also auf "noch nicht
        gelesen", was ehrlicher ist als ein Urteil, dem niemand traut.
        """
        if not db.clear_job_analysis(job_hash):
            return {"fehler": "Stelle nicht gefunden oder kein Befund "
                              "gespeichert."}
        return {"status": "geloescht",
                "hinweis": "Die Stelle gilt wieder als nicht beurteilt."}

    @mcp.tool()
    def aussortier_protokoll(zeitfenster: str = "7tage", limit: int = 50,
                             herkunft: str = "") -> dict:
        """Was wurde wann und von wem aussortiert (#1010).

        Der Rueckholweg fuer einen Verklicker. Rueckholen ging schon
        immer (`stelle_reaktivieren`, Filter "Ausgeblendet") — was
        fehlte, war das WIEDERFINDEN: es gab keinen Zeitpunkt der
        Aussortierung, und `updated_at` taugt nicht dafuer (die Spalte
        fasst jede Score-Neuberechnung an).

        Manuelle und automatische Aussortierungen stehen bewusst in
        EINER Liste — so hat der Nutzer es verlangt —, aber mit
        ausgewiesener Herkunft.

        Args:
            zeitfenster: 'heute', '7tage' (Standard), '30tage' oder 'alle'.
            limit: hoechstens so viele Zeilen (Standard 50).
            herkunft: '' fuer beide, 'ich' oder 'automatik'.

        Stellen aus der Zeit vor v1.7.64 tragen keinen Zeitpunkt. Sie
        werden als solche ausgewiesen und erscheinen nur bei
        zeitfenster='alle' — `updated_at` als Ersatz einzusetzen waere
        eine erfundene Angabe (#987).
        """
        from ..services import aussortier_protokoll as _protokoll
        befund = _protokoll.eintraege(db, zeitfenster=zeitfenster,
                                      limit=limit, herkunft_filter=herkunft)
        if "fehler" not in befund:
            befund["naechster_schritt"] = (
                "Zurueckholen mit stelle_reaktivieren(job_hash).")
        return befund

    @mcp.tool()
    def stelle_reaktivieren(job_hash: str, grund: str = "") -> dict:
        """Reaktiviert eine zuvor aussortierte Stelle (#664).

        Setzt `is_active=1` und loescht `dismiss_reason`. Gegenstueck zu
        `stelle_bewerten('passt_nicht')` — analog zu `dokument_reaktivieren()`
        fuer Dokumente. Notwendig wenn Claude oder der User eine Stelle
        irrtuemlich aussortiert hat und sie wieder in der aktiven Liste
        haben moechte, ohne ueber den DB-Bypass zu gehen (#514).

        Args:
            job_hash: Hash der Stelle (8-Zeichen-Kurzform oder voll).
            grund: Optionaler Hinweis warum reaktiviert wird (z.B.
                "Irrtum — Firma nicht auf Blacklist"). Wird im Result
                zurueckgegeben, nicht persistiert.
        """
        from ..services.typed_ids import strip_prefix
        h = strip_prefix(job_hash)
        target_hash = db.resolve_job_hash(h)
        if not target_hash:
            return {
                "fehler": "Stelle nicht gefunden. Pruefe den Hash mit stellen_anzeigen()."
            }
        job_before = db.get_job(target_hash)
        if not job_before:
            return {"fehler": "Stelle nicht gefunden."}

        war_aktiv = bool(job_before.get("is_active"))
        alter_grund = job_before.get("dismiss_reason") or ""

        if war_aktiv and not alter_grund:
            return {
                "status": "bereits_aktiv",
                "job_hash": target_hash[:8],
                "titel": job_before.get("title", ""),
                "firma": job_before.get("company", ""),
                "hinweis": "Stelle war bereits aktiv — nichts zu tun.",
            }

        db.restore_job(target_hash)

        # v1.7.22 (#941): Reaktivierung ist ein LERNSIGNAL. Automatisches
        # Aussortieren ohne Rueckfrage hat den Preis, dass eine zu
        # scharfe Regel niemandem auffaellt — ausser der Nutzer holt die
        # Stelle zurueck. Genau dann gehoert es protokolliert.
        war_automatik = alter_grund.startswith("auto:")
        if war_automatik:
            try:
                db.add_activity_event({
                    "event_type": "auto_dismiss_zurueckgeholt",
                    "entity_type": "job",
                    "entity_id": target_hash[:8],
                    "action": "reaktivieren",
                    "metadata": {"dismiss_reason": alter_grund,
                                 "titel": (job_before.get("title") or "")[:80],
                                 "nutzer_grund": grund or ""},
                })
            except Exception:
                logger.debug("Lernsignal fuer %s nicht protokolliert",
                             target_hash[:8])

        return {
            "status": "reaktiviert",
            "war_automatisch_aussortiert": war_automatik,
            "lernhinweis": (
                "Diese Stelle hatte die Automatik aussortiert. Die "
                "Ruecknahme ist protokolliert — haeuft sich das, steht "
                "die Regel zu scharf."
            ) if war_automatik else None,
            "job_hash": target_hash[:8],
            "titel": job_before.get("title", ""),
            "firma": job_before.get("company", ""),
            "vorheriger_dismiss_reason": alter_grund or None,
            "grund": grund or None,
            "hinweis": (
                "Stelle ist wieder aktiv und erscheint in stellen_anzeigen() "
                "+ fit_analyse(). Bei Bedarf erneut mit stelle_bewerten() "
                "aussortieren."
            ),
        }

    @mcp.tool()
    def stelle_wiedergaenger_pruefen(
        job_hash: str = "",
        firma: str = "",
        titel: str = "",
        schwellwert: int = 2,
        auto_aussortieren: bool = False,
    ) -> dict:
        """Prueft ob eine Stelle ein "Wiedergaenger" ist (#671, Ebene 0, KI-frei).

        Ein Wiedergaenger ist eine Stelle, die inhaltlich derselben Firma +
        Domaene entspricht, die bereits frueher mehrfach mit demselben Grund
        aussortiert wurde — taucht aber unter neuem Hash (anderer Scrape/Quelle)
        wieder als "frischer Fund" auf. Beispiel: Firma X + Domaene "PLM" wurde
        schon 2x als `falsches_fachgebiet` verworfen.

        **Rein deterministisch (Ebene 0) — keine lokale KI noetig.** Das Feature
        funktioniert vollstaendig auch in Installationen ohne Ollama. Eine
        optionale Ollama-Verfeinerung (Ebene 1) und der Claude-Kontext in
        `fit_analyse` (Ebene 2) bauen darauf auf, sind aber nicht erforderlich.

        Args:
            job_hash: Optional. Hash der zu pruefenden Stelle — Firma/Titel
                werden daraus gelesen. Ueberschreibt firma/titel.
            firma: Firmenname (wenn kein job_hash gegeben).
            titel: Stellentitel (wenn kein job_hash gegeben).
            schwellwert: Ab wie vielen frueheren Aussortierungen mit gleichem
                Grund als Wiedergaenger gilt (Default 2).
            auto_aussortieren: Wenn True UND ein job_hash gegeben UND ein klares
                Muster: die Stelle direkt mit dem Top-Grund aussortieren
                (dismiss_reason = 'wiedergaenger:<grund>'). Default False
                (nur melden).
        """
        from ..services.wiedergaenger import find_wiedergaenger_pattern

        resolved_hash = None
        if job_hash:
            from ..services.typed_ids import strip_prefix
            resolved_hash = db.resolve_job_hash(strip_prefix(job_hash))
            if not resolved_hash:
                return {"fehler": "Stelle nicht gefunden. Pruefe Hash mit stellen_anzeigen()."}
            job = db.get_job(resolved_hash)
            if not job:
                return {"fehler": "Stelle nicht gefunden."}
            firma = job.get("company", "") or firma
            titel = job.get("title", "") or titel

        if not (firma or "").strip():
            return {"fehler": "firma (oder job_hash) ist Pflicht."}

        pattern = find_wiedergaenger_pattern(
            db, firma, titel,
            schwellwert=max(1, int(schwellwert or 2)),
            target_hash=resolved_hash,
        )

        if not pattern:
            antwort = {
                "status": "kein_wiedergaenger",
                "firma": firma,
                "titel": titel,
                "hinweis": (
                    "Keine ausreichende Aussortier-Historie fuer diese "
                    "Firma+Domaene/Rolle gefunden — als Neufund behandeln."
                ),
            }
            # v1.7.7 (#754/#757): Gibt es Historie zu ANDEREN Rollen der
            # Firma, kommt sie als neutrale Einordnung mit — kein k.o.
            from ..services.wiedergaenger import firmen_historie
            fh = firmen_historie(db, firma, target_hash=resolved_hash)
            if fh:
                antwort["firmen_historie"] = fh
                antwort["hinweis"] = (
                    "Kein Wiedergaenger — die frueheren Aussortierungen "
                    "dieser Firma betrafen andere Rollen/Domaenen. "
                    "Als Neufund bewerten (Gruende gelten je Stelle, #757)."
                )
            return antwort

        result = {
            "status": "wiedergaenger",
            "firma": firma,
            "titel": titel,
            "top_grund": pattern["top_grund"],
            "anzahl_frueher_aussortiert": pattern["anzahl"],
            "domain_tokens": pattern["domain_tokens"],
            "alle_gruende": pattern["alle_gruende"],
            "beispiele": pattern["beispiele"],
            "empfehlung": (
                f"Diese Stelle gleicht {pattern['anzahl']} frueher als "
                f"'{pattern['top_grund']}' aussortierten Stellen derselben "
                "Firma+Domaene. Wahrscheinlich erneut nicht passend — pruefen "
                "ob sich etwas geaendert hat, sonst aussortieren."
            ),
        }

        # Auto-Aussortieren nur bei explizitem Flag + vorhandenem Hash
        if auto_aussortieren and resolved_hash:
            try:
                db.dismiss_job(resolved_hash,
                               f"wiedergaenger:{pattern['top_grund']}",
                               herkunft="automatik")
                result["aktion"] = "auto_aussortiert"
                result["dismiss_reason"] = f"wiedergaenger:{pattern['top_grund']}"
            except Exception as exc:  # noqa: BLE001
                logger.warning("Wiedergaenger-Auto-Aussortieren fehlgeschlagen: %s", exc)
                result["aktion"] = "aussortieren_fehlgeschlagen"
        else:
            result["aktion"] = "nur_gemeldet"

        return result

    @mcp.tool()
    @time_tool(logger, "stellen_bulk_bewerten")
    def stellen_bulk_bewerten(
        bewertung: str,
        grund: str = "",
        gruende: list[str] = None,
        dry_run: bool = True,
        # Filter (alle optional, kombinierbar mit AND-Logik)
        min_score: int = None,
        max_score: int = None,
        min_alter_tage: int = None,
        max_alter_tage: int = None,
        quelle: str = "",
        firma: str = "",
        titel_enthaelt: list[str] = None,
        titel_enthaelt_nicht: list[str] = None,
        beschreibung_enthaelt_nicht: list[str] = None,
        max_treffer: int = 0,
    ) -> dict:
        """Bewertet mehrere aktive Stellen auf einmal anhand von Filtern (#514).

        ANTI-DB-BYPASS: Nutze dieses Tool fuer das Aussortieren grosser Mengen
        von Stellen. NIEMALS direkt in die SQLite-Datei schreiben — die
        PBP-Logik (Audit-Log, Lerneffekte, Auto-Adjust-Scoring,
        dismiss_reasons-Statistik) wird hier durchlaufen, bei direkten
        DB-Writes nicht.

        SICHERHEITS-DEFAULT: dry_run=True. Erst Vorschau (Anzahl Treffer +
        erste 10 Beispiele), dann mit dry_run=False ausfuehren. Das ist
        bewusst nicht verhandelbar — der Filter trifft sonst zu viel.

        REAL-CASE: Bei einer Suche kommen 500 Stellen, davon 200 falsches
        Fachgebiet. Anstatt 200 Einzelaufrufe von stelle_bewerten:

            stellen_bulk_bewerten(
                bewertung='passt_nicht',
                gruende=['falsches_fachgebiet'],
                titel_enthaelt_nicht=['Pflege', 'Vertrieb'],
                dry_run=True  # erst pruefen!
            )

        Args:
            bewertung: 'passt' oder 'passt_nicht'
            grund / gruende: wie bei stelle_bewerten. ABLEHNUNGSGRUENDE-Liste
                gilt analog. KI darf KEINE eigenen Gruende erfinden.
            dry_run: bei True (Default) wird NICHTS veraendert, nur Preview.
                Bei False: alle Treffer werden tatsaechlich bewertet.
            min_score / max_score: Score-Bereich (None = unbegrenzt)
            min_alter_tage / max_alter_tage: relativ zu found_at
            quelle: Quelle als String (z.B. 'bundesagentur')
            firma: Firmenname (case-insensitive Substring-Match)
            titel_enthaelt: AND-Liste — Titel muss ALLE Begriffe enthalten
            titel_enthaelt_nicht: NOR-Liste — Titel darf KEINEN davon enthalten
            beschreibung_enthaelt_nicht: NOR-Liste fuer Beschreibung —
                Hauptwerkzeug fuer Fachgebiets-Aussortierung
            max_treffer: harter Cap auf die Anzahl Treffer (0 = kein Limit).
                Sinnvoll wenn man nicht sicher ist wie weit der Filter trifft.

        v1.7.0-beta.74 (#646): Wall-Clock-Budget von 90 Sekunden. Falls
        ein Lauf laenger braucht (z.B. weil _run_auto_refetch_descriptions
        parallel die DB sperrt), wird mit `status='timeout'` abgebrochen
        statt stumm zu haengen. Reduziere max_treffer oder warte bis der
        Auto-Engine-Step durch ist.

        Returns:
            dry_run=True:
                {"dry_run": True, "anzahl_treffer": N, "vorschau": [...10 Stellen...]}
            dry_run=False:
                {"dry_run": False, "bearbeitet": N, "ablehnungs_statistik": {...},
                 "hinweise": [...], "stichprobe_bearbeitet": [...erste 5...]}
        """
        from datetime import datetime, timedelta
        import time as _time

        # #646: Wall-Clock-Budget — Schutz gegen DB-Lock-Konflikt mit
        # _run_auto_refetch_descriptions (das pro Stelle 15s httpx-Timeout
        # hat und dabei die DB-Connection halten kann).
        _BULK_BUDGET_SEK = 90
        _bulk_started_at = _time.monotonic()

        def _budget_left() -> float:
            return _BULK_BUDGET_SEK - (_time.monotonic() - _bulk_started_at)

        def _timeout_result(stage: str, processed: int = 0) -> dict:
            return {
                "status": "timeout",
                "fehler": (
                    f"Zeit-Budget ({_BULK_BUDGET_SEK}s) waehrend '{stage}' "
                    "erreicht. Mehrere Aufrufe mit engeren Filtern (max_treffer, "
                    "min_score) probieren — oder kurz warten bis "
                    "auto_refetch_descriptions durch ist."
                ),
                "dauer_sek": round(_time.monotonic() - _bulk_started_at, 1),
                "verarbeitet": processed,
                "hinweis": (
                    "#646: stellen_bulk_bewerten hat ein Sicherheits-Budget "
                    "um stilles Haengen zu vermeiden."
                ),
            }

        # 1) Bewertung validieren
        if bewertung not in ("passt", "passt_nicht"):
            return {"fehler": "Ungueltige Bewertung. Nutze 'passt' oder 'passt_nicht'."}

        reason_list: list[str] = []
        if bewertung == "passt_nicht":
            reason_list = _normalize_reason_list(grund, gruende)
            if not reason_list:
                return {
                    "fehler": "Mindestens ein Ablehnungsgrund ist erforderlich.",
                    "verfuegbare_gruende": ABLEHNUNGSGRUENDE,
                }

        # 2) Kandidaten laden — semantisch unterschiedlicher Pool je Aktion:
        #    - 'passt_nicht' (Aussortieren) wirkt auf aktuell aktive Stellen
        #    - 'passt' (Restore) wirkt auf bereits dismissed Stellen
        if bewertung == "passt":
            candidates = db.get_dismissed_jobs()
            # Anschliessend manuell auf min_score / quelle filtern
            # v1.6.5 (#557): Partial-Match analog get_active_jobs
            if quelle:
                q_lc = quelle.lower()
                if "_" in quelle or quelle in ("manuell", "google_jobs"):
                    candidates = [j for j in candidates
                                  if (j.get("source") or "").lower() == q_lc]
                else:
                    candidates = [j for j in candidates
                                  if q_lc in (j.get("source") or "").lower()]
            if min_score is not None and min_score > 0:
                candidates = [j for j in candidates if int(j.get("score") or 0) >= min_score]
        else:
            db_filters = {}
            if quelle:
                db_filters["source"] = quelle
            if min_score is not None and min_score > 0:
                db_filters["min_score"] = min_score
            # v1.6.5 (#556): Gleiche aktiv-Definition wie stellen_anzeigen —
            # Blacklist-gefilterte Stellen sollen nicht doppelt von einer
            # Bulk-Aussortierung beruehrt werden.
            candidates = db.get_active_jobs(
                filters=db_filters or None,
                exclude_blacklisted=True,
            )

        # 3) In-Memory-Filter fuer alles was die DB-API nicht direkt anbietet
        now = datetime.now()
        firma_lc = (firma or "").lower().strip()
        title_must = [t.lower() for t in (titel_enthaelt or []) if t]
        title_must_not = [t.lower() for t in (titel_enthaelt_nicht or []) if t]
        desc_must_not = [t.lower() for t in (beschreibung_enthaelt_nicht or []) if t]

        def _matches(job: dict) -> bool:
            score = int(job.get("score") or 0)
            if max_score is not None and score > max_score:
                return False
            # Alter
            found_at = job.get("found_at") or ""
            if min_alter_tage is not None or max_alter_tage is not None:
                if not found_at:
                    return False
                try:
                    found_dt = datetime.fromisoformat(found_at.replace("Z", "+00:00").split("+")[0])
                except (ValueError, TypeError):
                    return False
                age_days = (now - found_dt).days
                if min_alter_tage is not None and age_days < min_alter_tage:
                    return False
                if max_alter_tage is not None and age_days > max_alter_tage:
                    return False
            # Firma
            if firma_lc and firma_lc not in (job.get("company") or "").lower():
                return False
            # Titel-Filter
            title_lc = (job.get("title") or "").lower()
            if title_must and not all(t in title_lc for t in title_must):
                return False
            if title_must_not and any(t in title_lc for t in title_must_not):
                return False
            # Beschreibung
            if desc_must_not:
                desc_lc = (job.get("description") or "").lower()
                if any(t in desc_lc for t in desc_must_not):
                    return False
            return True

        # #646: Nach DB-Load Budget pruefen — wenn schon abgelaufen ist es
        # ein DB-Lock-Verdacht (auto_refetch_descriptions oder anderes hat
        # die Connection geblockt).
        if _budget_left() <= 0:
            return _timeout_result("db_load")

        matched = [j for j in candidates if _matches(j)]
        if max_treffer and max_treffer > 0:
            matched = matched[:max_treffer]

        # 4) Dry-Run: nur Vorschau zurueck
        if dry_run:
            preview = [
                {
                    "hash": (j.get("hash") or "")[:12],
                    "title": j.get("title"),
                    "company": j.get("company"),
                    "score": j.get("score"),
                    "source": j.get("source"),
                    "found_at": (j.get("found_at") or "")[:10],
                }
                for j in matched[:10]
            ]
            return {
                "dry_run": True,
                "bewertung": bewertung,
                "gruende": reason_list if bewertung == "passt_nicht" else None,
                "anzahl_treffer": len(matched),
                "vorschau": preview,
                "hinweis": (
                    f"{len(matched)} Stellen wuerden bewertet werden. "
                    "Pruefe die Vorschau und rufe das Tool erneut mit dry_run=False auf, "
                    "um die Aenderung tatsaechlich anzuwenden."
                ),
            }

        # 5) Tatsaechliche Anwendung — durch die echte Lifecycle-Logik
        if not matched:
            return {
                "dry_run": False,
                "bearbeitet": 0,
                "hinweis": "Kein Treffer mit den gegebenen Filtern.",
            }

        bearbeitet = 0
        last_counts: dict = {}
        bulk_auto_adjustments: list[str] = []
        sample_processed: list[dict] = []
        for j in matched:
            # #646: Budget-Check pro Stelle. Bei DB-Lock-Verdacht (jeder
            # dismiss_job kann blocken) brechen wir mit Teil-Ergebnis ab.
            if _budget_left() <= 0:
                return {
                    "status": "timeout",
                    "dry_run": False,
                    "bearbeitet": bearbeitet,
                    "verbleibend": len(matched) - bearbeitet,
                    "fehler": (
                        f"Zeit-Budget ({_BULK_BUDGET_SEK}s) waehrend Bulk-Apply "
                        f"erreicht. {bearbeitet} Stellen bearbeitet, "
                        f"{len(matched) - bearbeitet} unverarbeitet. Bei den "
                        "verbleibenden kann der naechste Aufruf weitermachen."
                    ),
                    "dauer_sek": round(_time.monotonic() - _bulk_started_at, 1),
                    "stichprobe_bearbeitet": sample_processed,
                }
            job_hash = j.get("hash")
            if not job_hash:
                continue
            try:
                if bewertung == "passt_nicht":
                    # v1.6.5 (#558): skip_auto_adjust=True — wir triggern den
                    # Lerneffekt nur einmal am Ende, mit dem Final-Count.
                    ctx = _apply_dismiss_with_lifecycle(
                        job_hash, reason_list,
                        collect_hints=False,
                        skip_auto_adjust=True,
                    )
                    last_counts = ctx["counts"]
                else:  # passt
                    db.restore_job(job_hash)
                bearbeitet += 1
                if len(sample_processed) < 5:
                    sample_processed.append({
                        "hash": (job_hash or "")[:12],
                        "title": j.get("title"),
                        "company": j.get("company"),
                    })
            except Exception as exc:
                logger.warning("Bulk-Bewertung fuer %s fehlgeschlagen: %s", job_hash, exc)

        # v1.6.5 (#558): EINMALIG nach der Bulk-Schleife den Auto-Adjust ausloesen.
        # Verhindert Score-Drift (s. _apply_dismiss_with_lifecycle Doc).
        if bewertung == "passt_nicht" and bearbeitet > 0:
            for g in reason_list:
                normalized = g.lower().strip()
                cnt = last_counts.get(normalized, 0)
                if cnt >= 5:
                    _auto = _auto_adjust_scoring(db, normalized, cnt)
                    if _auto:
                        bulk_auto_adjustments.append(_auto)

        # Aggregierte Hinweise — nur einmal, nicht pro Eintrag
        hinweise = []
        if bulk_auto_adjustments:
            unique_adj = list(dict.fromkeys(bulk_auto_adjustments))
            hinweise.append(
                f"Scoring wurde automatisch angepasst "
                f"({len(unique_adj)} Aenderung(en)): " + "; ".join(unique_adj[:5])
            )
            # v1.6.5 (#558): Klare Drift-Warnung mit Hinweis auf
            # Score-Recompute — sonst wundert man sich ueber niedrige Scores.
            hinweise.append(
                "Hinweis: Bestehende Stellen-Scores wurden nicht neu berechnet. "
                "Falls Du danach in stellen_anzeigen niedrigere Scores siehst, "
                "ist das die Folge der Scoring-Anpassung — fuer einen "
                "konsistenten Stand 'fit_analyse' auf einzelne Stellen neu laufen lassen."
            )

        result = {
            "dry_run": False,
            "bewertung": bewertung,
            "gruende": reason_list if bewertung == "passt_nicht" else None,
            "bearbeitet": bearbeitet,
            "stichprobe_bearbeitet": sample_processed,
        }
        if last_counts:
            result["ablehnungs_statistik"] = {
                k: v for k, v in sorted(last_counts.items(), key=lambda x: -x[1])[:5]
            }
        if hinweise:
            result["hinweise"] = hinweise
        return result

    @mcp.tool()
    def stellen_anzeigen(
        filter: str = "aktiv",
        min_score: int = 0,
        quelle: str = "",
        seite: int = 1,
        pro_seite: int = 20,
        max_alter_tage: int = 0,
        nur_nicht_beworben: bool = False,
        nur_empfohlen: bool = False,
        nur_beurteilt: bool = False
    ) -> dict:
        """Zeigt gefundene Stellenangebote an.

        Gibt die Liste der Stellen zurück, sortiert nach Score — Stellen
        mit fachlichem k.o. (Wiedergaenger-Muster, #671) sinken dabei ans
        Ende, egal wie hoch ihr Score ist (v1.7.12, #827/C32): der Score
        misst Begriffe, das k.o.-Muster misst deine dokumentierten
        Entscheidungen. Nutze stelle_bewerten() um einzelne Stellen zu
        bewerten.

        Args:
            filter: 'aktiv' (Standard), 'aussortiert', oder 'alle'
            min_score: Nur Stellen mit mindestens diesem Score anzeigen (Tipp: 1 = mindestens ein Keyword-Treffer)
            quelle: Optional: Nur Stellen von dieser Quelle (z.B. 'stepstone', 'indeed', 'manuell')
            seite: Seitennummer für Paginierung (Standard: 1)
            pro_seite: Anzahl Stellen pro Seite (Standard: 20, max: 50)
            max_alter_tage: Nur Stellen die nicht älter als X Tage sind (0 = kein Limit)
            nur_nicht_beworben: Nur Stellen anzeigen auf die noch nicht beworben wurde
            nur_empfohlen: True blendet Stellen mit k.o.-Muster ganz aus
            nur_beurteilt: True zeigt nur Stellen, die gegen dein Profil
                gelesen wurden (#1007). Ohne gespeicherte Detailanalyse
                gilt eine Stelle als NICHT_BEURTEILBAR — das ist etwas
                anderes als "passt nicht", und wer die beurteilten
                sehen will, soll sie nicht suchen muessen.
        """
        # v1.7.39 (#989): Datenguete einmal je Aufruf vorbereiten — die
        # Kriterien und die Nutzereinstellung sind fuer alle Zeilen
        # dieselben, und eine Netz- oder DB-Abfrage je Stelle waere
        # unbrauchbar (dasselbe Muster wie die Synonyme in #987).
        from ..services import datenguete as _dg
        _profil_fuer_analyse = db.get_profile()
        from ..services import scoring_kriterien as _skrit
        try:
            _guete_krit = _skrit.fuer_scoring(db)
            _guete_umgang = _dg.umgang(db)
        except Exception as exc:  # pragma: no cover — nie eine Liste stoppen
            logger.debug("Datenguete-Vorbereitung fehlgeschlagen: %s", exc)
            _guete_krit, _guete_umgang = {}, _dg.NACHRANGIG

        def _guete_rang(j):
            return _dg.sortierschluessel(j, _guete_umgang, _guete_krit)

        # v1.7.68 (#968) AK 4: eine Stelle ohne Pflichttreffer steht
        # NIE ueber einer mit. Das steht bewusst in der Sortierung und
        # nicht im Score — eine Stelle mit Pflichttreffer, die ein Malus
        # nach unten gezogen hat, soll abstuerzen duerfen (#942); sie
        # darf dabei nur nicht unter eine rutschen, ueber deren Fach
        # nichts bekannt ist. Dieselbe Bauform wie der Guete-Rang.
        from ..services import muss_tor as _tor

        def _tor_rang(j):
            return _tor.sortierschluessel(j, _guete_krit)

        if filter == "aussortiert":
            jobs = db.get_dismissed_jobs()
        else:
            filters = {}
            if min_score > 0:
                filters["min_score"] = min_score
            if quelle:
                filters["source"] = quelle
            jobs = db.get_active_jobs(
                filters if filters else None,
                exclude_blacklisted=True,
                exclude_applied=nur_nicht_beworben,
            )

        # Age filter (#52)
        if max_alter_tage > 0:
            from datetime import datetime, timedelta
            cutoff = (datetime.now() - timedelta(days=max_alter_tage)).isoformat()
            jobs = [j for j in jobs if (j.get("found_at") or "") >= cutoff]

        # Apply scoring adjustments (#169)
        durch_schwelle_verborgen = 0
        if filter != "aussortiert":
            try:
                from ..services.scoring_service import apply_scoring_adjustments
                auto_ignored = 0
                scored_jobs = []
                for j in jobs:
                    result = apply_scoring_adjustments(j, j.get("score", 0), db)
                    j["score"] = result["final_score"]
                    if result.get("ignored"):
                        auto_ignored += 1
                        continue
                    scored_jobs.append(j)
                if auto_ignored:
                    logger.info("Scoring-Regler: %d Stellen auto-ignoriert",
                                auto_ignored)
                # #1008 (G37): die Zahl gehoert in die ANTWORT, nicht ins
                # Log. Bis v1.7.61 verschwanden die Stellen still, und die
                # leere Liste meldete "Keine Stellen gefunden. Starte eine
                # Jobsuche" — waehrend `pbp_diagnose` dieselben Stellen als
                # aktiv fuehrte. PBP widersprach sich in sich selbst, und
                # der genannte naechste Schritt war der falsche. Das ist
                # #813 an der Trefferliste statt am Suchlauf.
                durch_schwelle_verborgen = auto_ignored
                jobs = scored_jobs
                # Re-sort by new score
                # v1.7.39 (#989): der Datenguete-Rang steht VOR dem Score.
                # Eine Stelle ohne Anzeigentext ist nicht schlecht bewertet,
                # sie ist GAR nicht bewertet — und was nichts kostet, stand
                # bisher oben. Der Score selbst bleibt unveraendert: er misst,
                # was in der Anzeige steht, und das ist eine Messung. Die
                # Reihenfolge ist eine Darstellung, und dort gehoert die
                # Unterscheidung hin.
                jobs.sort(key=lambda j: (-j.get("is_pinned", 0),
                                         _tor_rang(j),
                                         _guete_rang(j),
                                         -j.get("score", 0)))
            except Exception as e:
                logger.debug("Scoring adjustments fehlgeschlagen: %s", e)

            # v1.7.12 (#827, C32): Empfehlungslage VOR der Paginierung.
            # Das Wiedergaenger-Muster (#671) ist rein regelbasiert und
            # wird compute-on-read ausgewertet — damit zaehlt die Historie
            # zum LESEzeitpunkt, nicht der Stand beim ersten Speichern der
            # Stelle. Der Bestand wird EINMAL geladen (Preload), sonst
            # wuerde jede Stelle der Liste den vollen Scan wiederholen.
            try:
                from ..services.wiedergaenger import find_wiedergaenger_pattern
                _dismissed_pool = db.get_dismissed_jobs()
                for j in jobs:
                    muster = find_wiedergaenger_pattern(
                        db, j.get("company", ""), j.get("title", ""),
                        target_hash=j.get("hash"),
                        dismissed=_dismissed_pool)
                    if muster:
                        j["_ko_muster"] = muster
                if nur_empfohlen:
                    jobs = [j for j in jobs if not j.get("_ko_muster")]
                # NICHT_EMPFOHLEN sinkt unter alle Empfohlenen — der Fall
                # aus #827: fachfremde Rolle mit Boilerplate-Score stand
                # auf Platz 9, waehrend das System ihr k.o. laengst kannte.
                jobs.sort(key=lambda j: (-j.get("is_pinned", 0),
                                         1 if j.get("_ko_muster") else 0,
                                         _tor_rang(j),
                                         _guete_rang(j),
                                         -j.get("score", 0)))
            except Exception as e:
                logger.debug("Empfehlungs-Anreicherung fehlgeschlagen: %s", e)

        # v1.7.63 (#1007, letztes Akzeptanzkriterium): nach dem Urteil
        # filtern. Wie jeder Filter, der etwas unterdrueckt, nennt er die
        # Zahl der ausgeblendeten Stellen — die Lehre aus #1008 gilt fuer
        # den neuen Filter genauso wie fuer die alten.
        ohne_urteil_verborgen = 0
        if nur_beurteilt:
            vorher = len(jobs)
            jobs = [j for j in jobs if (j.get("analyse_urteil") or "").strip()]
            ohne_urteil_verborgen = vorher - len(jobs)

        if not jobs:
            if ohne_urteil_verborgen:
                return {
                    "anzahl": 0,
                    "ohne_urteil_verborgen": ohne_urteil_verborgen,
                    "nachricht": (
                        f"Keine beurteilte Stelle — {ohne_urteil_verborgen} "
                        "aktive Stelle(n) wurden noch nicht gegen dein Profil "
                        "gelesen. Das ist ein Filter, kein leerer Bestand."),
                    "naechster_schritt": (
                        "Lass Claude eine Detailanalyse machen und das "
                        "Ergebnis mit stelle_analyse_speichern an der Stelle "
                        "ablegen — oder ruf stellen_anzeigen() ohne "
                        "nur_beurteilt auf."),
                }
            if durch_schwelle_verborgen:
                # Es GIBT Stellen — sie liegen nur unter der Schwelle.
                # Eine Suche zu empfehlen waere der falsche Schritt.
                return {
                    "anzahl": 0,
                    "durch_schwelle_verborgen": durch_schwelle_verborgen,
                    "nachricht": (
                        f"Keine Stelle ueber deiner Score-Schwelle — aber "
                        f"{durch_schwelle_verborgen} aktive Stelle(n) liegen "
                        "darunter und werden deshalb nicht angezeigt. Das ist "
                        "ein Filter, kein leerer Markt."),
                    "naechster_schritt": (
                        "Schwelle ansehen: scoring_konfigurieren('anzeigen'). "
                        "Senken oder abschalten: scoring_konfigurieren("
                        "aktion='setzen', dimension='schwellenwert', "
                        "sub_key='auto_ignore', wert=0). Ueber "
                        "stellen_anzeigen(min_score=0) kommen sie NICHT "
                        "zurueck — die Schwelle wirkt davor."),
                }
            return {
                "anzahl": 0,
                "nachricht": "Keine Stellen gefunden. "
                             "Starte eine Jobsuche mit jobsuche_starten() oder "
                             "aktiviere Quellen im Dashboard unter Einstellungen."
            }

        # Count per source for overview
        source_counts = {}
        for j in jobs:
            src = j.get("source", "unbekannt")
            source_counts[src] = source_counts.get(src, 0) + 1

        # Check which jobs have been applied to (#65)
        # v1.7.10 (#782/C30): volle Bewerbungsliste einmal laden — die
        # Repost-Pruefung braucht Firma/Titel/Status, nicht nur Hashes.
        _alle_bewerbungen = db.get_applications()
        applied_hashes_all = {
            r["job_hash"] for r in _alle_bewerbungen
            if r.get("job_hash")
        } if not nur_nicht_beworben else set()

        # Pagination (#58)
        pro_seite = min(pro_seite, 50)
        total = len(jobs)
        start = (seite - 1) * pro_seite
        end = start + pro_seite
        page_jobs = jobs[start:end]

        # Format for Claude readability
        formatted = []
        for j in page_jobs:
            entry = {
                "id": j["hash"][:8],  # #171: Kurz-ID fuer schnelle Referenz
                "hash": j["hash"],
                "titel": j.get("title", ""),
                "firma": j.get("company", ""),
                "ort": j.get("location", ""),
                "score": j.get("score", 0),
                "quelle": j.get("source", ""),
                "remote": j.get("remote_level", "unbekannt"),
                "url": j.get("url", ""),
                "gefunden_am": (j.get("found_at") or "")[:10],
            }
            # v1.7.26 (#949 Befund 2): das Datum allein sagt wenig —
            # die LAUFZEIT ist das Signal. Eine seit Monaten laufende
            # Anzeige sah bisher taufrisch aus, weil nur `found_at`
            # sichtbar war.
            if j.get("veroeffentlicht_am"):
                entry["veroeffentlicht_am"] = j["veroeffentlicht_am"]
                _alter = _anzeigenalter.einordnung(j)
                if _alter.get("anzeigenalter_tage") is not None:
                    entry["anzeigenalter_tage"] = _alter["anzeigenalter_tage"]
                if _alter.get("hinweis"):
                    entry["anzeigenalter_hinweis"] = _alter["hinweis"]
            emp_type = j.get("employment_type") or ""
            if emp_type == "freelance":
                typ_emoji = "🟢"
                typ_label = "🟢 Freelance"
            elif emp_type == "festanstellung":
                typ_emoji = "🔵"
                typ_label = "🔵 Festanstellung"
            else:
                typ_emoji = "⚪"
                typ_label = "⚪ Sonstige"
            entry["titel"] = f"{typ_emoji} {entry['titel']}"
            entry["typ_label"] = typ_label
            if emp_type:
                entry["typ"] = emp_type
            if j.get("salary_min"):
                entry["gehalt_min"] = j["salary_min"]
                entry["gehalt_max"] = j.get("salary_max")
                entry["gehalt_typ"] = j.get("salary_type", "jaehrlich")
                if j.get("salary_estimated"):
                    entry["gehalt_geschaetzt"] = True
            if j.get("distance_km"):
                # #950: nie die blosse Zahl — sie wird als Wegstrecke
                # gelesen und ist eine Luftlinie.
                entry.update(_entfernung.befund(j["distance_km"]))
            # v1.7.22 (#942): Fach- und Rahmenanteil getrennt ausweisen.
            # "Score 31" allein verraet nicht, ob die Punkte fachlich
            # sind oder aus Rahmenbegriffen (Senior, Remote, Hamburg)
            # stammen. Mit der Aufteilung ist ein Fehlgriff auf einen
            # Blick erkennbar.
            if j.get("fachscore") is not None:
                entry["fachscore"] = j.get("fachscore")
                entry["rahmenscore"] = j.get("rahmenscore")
            if j.get("dismiss_reason"):
                entry["aussortiert_grund"] = j["dismiss_reason"]
            if j["hash"] in applied_hashes_all:
                entry["bereits_beworben"] = True
            # v1.7.39 (#989): Datenguete an JEDER Zeile — was ist belegt,
            # was ist nur angenommen. Bisher stand das in drei getrennten
            # Feldern verteilt (`score_status`, `entfernung_guete`,
            # `grund_guete`), jedes in einer anderen Tool-Antwort, und in
            # der Liste kam nichts davon an.
            _marke = _dg.kurzmarke(j, _guete_krit)
            if _marke:
                entry["datenguete"] = _marke

            # v1.7.68 (#968) AK 3: warum diese Zeile unten steht. Eine
            # Stelle, die ohne erkennbaren Grund hinten liegt, sieht aus
            # wie ein Fehler — und ein Befund, den nur ein Werkzeug
            # kennt, ist kein Befund (#989).
            _tor_marke = _tor.marke(j, _guete_krit)
            if _tor_marke:
                entry["muss_tor"] = _tor_marke

            # #1007 (G36): der Analyse-Befund haengt an der Stelle und
            # gehoert in die Liste. Bis v1.7.60 entstand der Verdict bei
            # jedem Aufruf neu und verschwand mit der Antwort — die
            # Liste konnte ihn gar nicht zeigen. Ohne Befund steht hier
            # NICHTS: "noch nicht gelesen" ist kein Urteil (#989).
            _befund = passung.analyse_lesen(j, _profil_fuer_analyse)
            if _befund:
                entry["analyse"] = _befund
            # #948 (G42): der Pruefstand ist eine ANDERE Auskunft als das
            # Urteil. Er steht auch dann da, wenn kein Urteil vorliegt —
            # "angesehen, aber nicht beurteilt" ist der Zustand, in dem
            # Arbeit verlorenging.
            entry["pruefstand"] = passung.zustand(j, _profil_fuer_analyse)
            # #951 (AK 6): wo ueberall diese Stelle ausgeschrieben ist.
            # Steht nur da, wenn es MEHR als eine Fundstelle gibt — sonst
            # waere es die Wiederholung des `source`-Feldes.
            from ..services import stellen_quellen as _sq
            _quellen = _sq.uebersicht(db, j)
            if _quellen:
                entry["quellen"] = _quellen

            # #180: Warnung wenn Beschreibung fehlt (Score unsicher)
            desc = j.get("description") or ""
            if len(desc.strip()) < _dg.MIN_BESCHREIBUNG:
                entry["beschreibung_fehlt"] = True
                if (j.get("score") or 0) <= 0:
                    # v1.7.7 (#756): Score 0 ohne Beschreibung ist KEIN
                    # Urteil — die Stelle wurde schlicht nicht bewertet.
                    entry["score_status"] = "unbewertet"
                    entry["score_hinweis"] = (
                        "Score 0 ist KEIN Urteil — ohne Beschreibung wurde "
                        "nicht bewertet. Erst stellenbeschreibung_nachladen"
                        f"('{j['hash'][:8]}'), dann entscheiden."
                    )
                else:
                    entry["score_hinweis"] = "Score basiert nur auf dem Titel — Beschreibung fehlt"
            # #436: Warnung wenn URL auf Suchergebnis-Seite zeigt statt auf Detail-Anzeige
            if j.get("is_search_url"):
                entry["url_warnung"] = (
                    "Diese URL zeigt auf eine Suchergebnis-Seite, nicht auf die konkrete "
                    "Stellenanzeige. Die Detail-URL konnte vom Scraper nicht extrahiert "
                    "werden — suche die Stelle manuell auf dem Portal."
                )
            elif j.get("url"):
                from ..job_scraper import is_search_result_url
                if is_search_result_url(j["url"]):
                    entry["url_warnung"] = (
                        "Diese URL zeigt auf eine Suchergebnis-Seite, nicht auf die konkrete "
                        "Stellenanzeige. Suche die Stelle manuell auf dem Portal."
                    )
            # v1.7.10 (#782/C30): Repost-Erkennung — entspricht die Stelle
            # einer FRUEHEREN Bewerbung? Warnung, keine Entscheidung. Nur
            # wenn nicht ohnehin als bereits_beworben markiert (gleicher Hash).
            if j["hash"] not in applied_hashes_all:
                from ..duplicate_detection import find_repost_of_application
                _repost = find_repost_of_application(j, _alle_bewerbungen)
                if _repost:
                    entry["repost_warnung"] = _repost["warnung"]
                    entry["repost_details"] = {
                        k: v for k, v in _repost.items() if k != "warnung"}

            # v1.7.12 (#827): Empfehlungslage sichtbar in der Liste — der
            # Nutzer soll nicht fuer jede Stelle fit_analyse aufrufen
            # muessen, um zu erfahren, dass PBP laengst abgeraten hat.
            if j.get("_ko_muster"):
                _m = j["_ko_muster"]
                entry["empfehlung"] = {
                    "kategorie": "NICHT_EMPFOHLEN",
                    "ko_grund": (
                        f"Wiedergaenger: Firma wurde bereits {_m['anzahl']}x "
                        f"mit Grund '{_m['top_grund']}' aussortiert"
                    ),
                }
            # #766: Stellen ohne jeden Anker (URL/Dokument/Kontakt) sichtbar
            # markieren, statt sie wie normale Treffer darzustellen.
            from ..services.stellen_anker import anker_status as _anker_status
            _a = _anker_status(db, j)
            if not _a["hat_anker"]:
                entry["ohne_anker"] = True
                entry["anker_hinweis"] = (
                    "Nicht verfolgbar: keine Detail-URL, kein Dokument, kein "
                    "Ansprechpartner. So ist keine Bewerbung moeglich."
                )
            elif _a["anker"] != ["url_detail"]:
                entry["anker"] = _a["anker"]
            formatted.append(entry)

        result = {
            "anzahl_gesamt": total,
            "seite": seite,
            "pro_seite": pro_seite,
            "seiten_gesamt": (total + pro_seite - 1) // pro_seite,
            "angezeigt": len(formatted),
            "quellen_uebersicht": source_counts,
            "stellen": formatted,
        }
        if ohne_urteil_verborgen:
            result["ohne_urteil_verborgen"] = ohne_urteil_verborgen
            result["urteils_hinweis"] = (
                f"{ohne_urteil_verborgen} weitere aktive Stelle(n) wurden noch "
                "nicht gegen dein Profil gelesen und stehen deshalb nicht in "
                "dieser Liste. Sie sind nicht aussortiert — nur ungeprueft.")
        if durch_schwelle_verborgen:
            # #1008: sonst sieht eine gefilterte Liste aus wie die ganze.
            result["durch_schwelle_verborgen"] = durch_schwelle_verborgen
            result["schwellen_hinweis"] = (
                f"{durch_schwelle_verborgen} weitere aktive Stelle(n) liegen "
                "unter deiner Score-Schwelle und stehen deshalb nicht in "
                "dieser Liste. Sie sind nicht aussortiert — nur gefiltert.")
        # v1.7.7 (#756): unbewertete Stellen (Score 0 + keine Beschreibung)
        # ueber die GANZE Liste ausweisen — Score 0 darf nicht wie ein
        # fachliches Urteil wirken.
        unbewertet_gesamt = sum(
            1 for j in jobs
            if (j.get("score") or 0) <= 0
            and len((j.get("description") or "").strip()) < 50
        )
        if unbewertet_gesamt and filter != "aussortiert":
            result["unbewertet_anzahl"] = unbewertet_gesamt
            result["unbewertet_hinweis"] = (
                f"{unbewertet_gesamt} Stellen haben Score 0 nur weil die "
                "Beschreibung fehlt — das ist KEIN Urteil. Vor dem "
                "Aussortieren: stellenbeschreibung_nachladen(hash)."
            )

        # v1.7.39 (#989): die Lage der Datenguete ueber die ganze Liste.
        # Ohne diese Zeile sieht man je Stelle eine Marke, aber nicht,
        # dass die halbe Liste auf Titeln beruht.
        ohne_grundlage = sum(1 for j in jobs if not _dg.hat_beschreibung(j))
        if ohne_grundlage and filter != "aussortiert":
            result["datenguete"] = {
                "ohne_bewertungsgrundlage": ohne_grundlage,
                "von": len(jobs),
                "umgang_mit_unbekannt": _guete_umgang,
                "hinweis": (
                    f"{ohne_grundlage} von {len(jobs)} Stellen haben keinen "
                    "Anzeigentext — ihr Score beruht allein auf dem Titel. "
                    + ("Sie stehen deshalb hinter den bewerteten Stellen."
                       if _guete_umgang != _dg.MITMISCHEN else
                       "Sie mischen sich unter die bewerteten Stellen "
                       "(Einstellung 'mitmischen').")
                    + " Umstellen: umgang_mit_unbekannt_setzen()."
                ),
            }
        # #766: Anker-Lage ueber die angezeigte Seite zusammenfassen.
        ohne_anker = sum(1 for e in formatted if e.get("ohne_anker"))
        if ohne_anker and filter != "aussortiert":
            result["ohne_anker_anzahl"] = ohne_anker
            result["ohne_anker_hinweis"] = (
                f"{ohne_anker} der angezeigten Stellen sind nicht verfolgbar "
                "(keine Detail-URL, kein Dokument, kein Ansprechpartner). "
                "Bestand heilen: stellen_urls_heilen(dry_run=True) traegt "
                "wo moeglich eine Such-URL nach; den Rest per "
                "stelle_bearbeiten(url=...) oder Kontakt ergaenzen."
            )
        if filter == "aktiv":
            result["hinweis"] = (
                "Nutze stelle_bewerten(hash, 'passt') oder stelle_bewerten(hash, 'passt_nicht', 'Grund') "
                "um Stellen zu bewerten. Für Details: fit_analyse(hash). "
                f"Nächste Seite: stellen_anzeigen(seite={seite+1})" if seite * pro_seite < total else
                "Nutze stelle_bewerten(hash, 'passt') oder stelle_bewerten(hash, 'passt_nicht', 'Grund') "
                "um Stellen zu bewerten. Für Details: fit_analyse(hash)."
            )
        return result

    @mcp.tool()
    def google_jobs_url(
        keyword: str,
        zeitraum: str = "woche",
        ort: str = "",
    ) -> dict:
        """Baut eine Google-Jobs-URL fuer Chrome-in-Claude (#501, #573).

        Google Jobs (`udm=8`) ist der groesste Aggregator in DE und
        indexiert u.a. StepStone-Stellen. Ein direkter HTTP-Abruf wird
        von Google zuverlaessig blockiert, ein eingeloggter Chrome-Tab
        mit Claude-in-Chrome funktioniert aber stabil.

        Workflow (v1.7.0-beta.14, #573):
        1. `google_jobs_url(keyword="PLM", ort="Hamburg")` aufrufen
        2. URL in Chrome mit Claude-in-Chrome oeffnen
        3. Mit dem mitgelieferten `extraction_js` strukturierte Job-Daten
           via `javascript_tool()` aus dem DOM ziehen (statt Rohtext-Parsing)
        4. Gefundene Stellen mit `stelle_manuell_anlegen()` uebernehmen

        Args:
            keyword: Suchbegriff (z.B. 'PLM Projektleiter').
            zeitraum: 'tag' | 'woche' | 'monat'. Default 'woche'.
            ort: Optionaler Ort (z.B. 'Hamburg'). Leer = Google nimmt
                 den Standort aus dem eingeloggten Google-Account.
        """
        if not keyword:
            return {"fehler": "keyword ist Pflichtfeld."}
        from ..job_scraper.google_jobs import build_google_jobs_url
        url = build_google_jobs_url(keyword, zeitraum=zeitraum, ort=ort or None)
        # v1.7.0-beta.14 (#573): JS-Snippet fuer DOM-Extraktion mitliefern.
        # Mehrere Selektor-Pfade probieren, weil Google die Klassen-Hashes
        # haeufig rotiert. Wenn keiner matcht, faellt der Aufrufer auf
        # get_page_text() + manuelles Parsen zurueck.
        extraction_js = """
(() => {
  // Google Jobs (udm=8) — DOM-Selektoren (Stand Mai 2026).
  // Klassen rotieren, daher mehrere Strategien.
  const cards = Array.from(document.querySelectorAll(
    '[data-ved][role="listitem"], li[data-ved], div.PwjeAc'
  ));
  const getText = (el, sel) => {
    if (!el) return '';
    const node = sel ? el.querySelector(sel) : el;
    return (node?.innerText || node?.textContent || '').trim();
  };
  const results = cards.slice(0, 30).map((el, idx) => {
    const titel = getText(el, '.PUpOsf, .BjJfJf, [role="heading"]');
    const firma = getText(el, '.a3jPc, .vNEEBe, .nJlQNd');
    const ort   = getText(el, '.tJ9zfc, .Qk80Jf');
    const link = el.querySelector('a[href]')?.href || '';
    return {
      idx, titel, firma, ort, link,
      _raw: el.innerText?.slice(0, 200),
    };
  }).filter((r) => r.titel || r.firma);
  return { count: results.length, jobs: results };
})()
""".strip()
        return {
            "url": url,
            "extraction_js": extraction_js,
            "hinweis": (
                "Oeffne diese URL in Chrome mit Claude-in-Chrome. Nutze dann "
                "javascript_tool() mit `extraction_js` um strukturierte "
                "Job-Daten direkt aus dem DOM zu ziehen — vermeidet "
                "Rohtext-Parsing. Pro Treffer: titel, firma, ort, link. "
                "Falls keine Treffer: Selektoren wurden von Google rotiert, "
                "Fallback ueber get_page_text()."
            ),
        }

    @mcp.tool()
    def umgang_mit_unbekannt_setzen(modus: str = "") -> dict:
        """Wie soll PBP mit UNGEPRUEFTEN Angaben umgehen? (#989)

        Wo eine Information fehlt, setzt ein Punktesystem einen neutralen
        Wert ein — und neutral heisst dort nicht "unbekannt", sondern
        "kostet nichts". Was nichts kostet, steigt in der Sortierung. Am
        07.09.2026 stand deshalb ein inhaltsleerer Titel mit 101 Punkten
        ueber einer vollstaendig beschriebenen, fachlich passenden Stelle
        mit 32.

        Ob das ein Problem ist, haengt vom eigenen Kriterium ab — wer
        "nur remote oder im Nahbereich" sucht, will eine Stelle mit
        unbekanntem Ort im Zweifel NICHT als Nahstelle behandelt sehen.
        Deshalb ist es eine Einstellung und keine feste Regel.

        Args:
            modus: leer = aktuellen Stand anzeigen. Sonst 'nachrangig'
                (Vorgabe), 'mitmischen' oder 'streng'.
        """
        from ..services import datenguete as dg
        if not (modus or "").strip():
            jetzt = dg.umgang(db)
            return {
                "umgang": jetzt,
                "bedeutet": dg.UMGANG_MIT_UNBEKANNT[jetzt],
                "moeglich": dg.UMGANG_MIT_UNBEKANNT,
                "hinweis": ("Aendern: umgang_mit_unbekannt_setzen('streng'). "
                            "Die Dimensionen je Stelle stehen in "
                            "stellen_anzeigen unter 'datenguete'."),
            }
        ergebnis = dg.umgang_setzen(db, modus.strip().lower())
        return ergebnis

    @mcp.tool()
    def muss_tor_setzen(betriebsart: str = "") -> dict:
        """Ohne Pflichttreffer: verwerfen oder weit unten zeigen? (#968)

        Das MUSS-Tor entscheidet, ob eine Anzeige ueberhaupt in Frage
        kommt. Trifft kein einziger Pflichtbegriff, wird sie bisher
        verworfen — sie wird gar nicht erst gespeichert. Im
        dokumentierten Lauf aus #813 starben so 312 von 389
        Rohtreffern, bevor ein Mensch sie gesehen hat.

        Ob das richtig ist, haengt daran, WAS deine Pflichtbegriffe
        nennen:

        * **Techniken** ("PLM", "SAP", "Python") — ihr Fehlen ist ein
          echter Beleg: die Anzeige gehoert in ein anderes Fachgebiet.
          Dafuer ist `hart` richtig.
        * **einen Beruf** ("Pflegefachkraft", "Erzieherin") — ihr
          Fehlen sagt wenig, weil derselbe Beruf in vielen Anzeigen
          anders heisst. Dafuer ist `gewichtet` richtig.

        **Du musst hier nichts einstellen.** In der Vorgabe
        `automatisch` entscheidet PBP anhand deiner Pflichtbegriffe
        selbst — an derselben gemessenen Schwelle, die seit v1.7.36 die
        Alternativbezeichnungen absichert. Dieses Werkzeug zeigt die
        Entscheidung samt Begruendung und laesst sie ueberstimmen.

        Args:
            betriebsart: leer = aktuellen Stand anzeigen. Sonst
                'automatisch' (Vorgabe), 'hart' oder 'gewichtet'.
        """
        from ..services import muss_tor as mt
        from ..services import scoring_kriterien as _sk
        if not (betriebsart or "").strip():
            _muss = [k for k in ((db.get_search_criteria() or {}).get(
                "keywords_muss") or []) if str(k).strip()]
            _arten = _sk.gespeicherte_arten(db, _muss)
            _ableitung, _warum = mt.abgeleitet(_arten)
            jetzt = mt.modus(db)
            _gesetzt = db.get_profile_setting(mt.EINSTELLUNG, None)
            return {
                "muss_tor": jetzt,
                "bedeutet": mt.MODI[jetzt],
                "quelle": ("ausdruecklich eingestellt"
                           if _gesetzt in (mt.HART, mt.GEWICHTET)
                           else "abgeleitet aus deinen Pflichtbegriffen"),
                "begruendung": _warum,
                "begriffsart": _arten,
                "moeglich": mt.MODI,
                "pflichtbegriffe": len(_muss),
                # Ohne Pflichtbegriffe gibt es nichts zu verfehlen —
                # dann waere die Einstellung eine Vokabel ohne Wirkung
                # (#988), und das gehoert gesagt statt verschwiegen.
                "hinweis": (
                    "Ohne MUSS-Begriffe wirkt diese Einstellung nicht — "
                    "dann sortiert die Schwelle ohnehin nur (#967)."
                    if not _muss else
                    "Ueberstimmen: muss_tor_setzen('gewichtet') oder "
                    "('hart'); zurueck zur Ableitung mit "
                    "('automatisch'). Betroffene Stellen tragen in "
                    "stellen_anzeigen die Marke 'muss_tor'."),
            }
        return mt.modus_setzen(db, betriebsart.strip().lower())

    @mcp.tool()
    def scores_neu_berechnen(
        nur_aktive: bool = True,
        max_stellen: int = 0,
    ) -> dict:
        """Rechnet die Fit-Scores aller (aktiven) Stellen neu (#554, v1.6.9).

        Sinnvoll nach Aenderungen an:
        - Suchkriterien (`suchkriterien_setzen`/`suchkriterien_bearbeiten`)
        - Profil (relevante Skills, Wunsch-Gehalt, Standort)
        - Scoring-Regler (`scoring_konfigurieren`)
        - Geocoding-Cache (Standort-Aenderungen)

        Geht jede Stelle einmal durch `calculate_score()` und persistiert
        den neuen Wert via `db.update_job(hash, {"score": ...})`. Auto-
        Adjust-Hooks werden NICHT getriggert — das ist ein reiner Recompute.

        Args:
            nur_aktive: True (Standard) = nur is_active=1; False = auch aussortierte.
            max_stellen: 0 = unbegrenzt, sonst harter Cap (sinnvoll fuer Tests).
        """
        from ..job_scraper import calculate_score
        from ..services import scoring_kriterien
        # v1.7.36 (#987): dieselben Kriterien wie der Suchlauf. Vorher
        # rechnete dieser Lauf ohne die Anreicherung und "korrigierte"
        # damit 86 von 86 Stellen — die Korrektur war richtig, aber die
        # Abweichung haette es nie geben duerfen.
        #
        # Die Regel dahinter: **wer schreibt, frischt auf; wer liest,
        # nimmt den abgelegten Stand.** Eine Neuberechnung ist eine
        # bewusste Ansage des Nutzers und darf dafuer ins Netz;
        # `fit_analyse` ist ein Lesewerkzeug und darf es nicht (#963).
        scoring_kriterien.synonyme_auffrischen(db)
        criteria = scoring_kriterien.fuer_scoring(db)
        if nur_aktive:
            jobs = db.get_active_jobs()
        else:
            conn = db.connect()
            pid = db.get_active_profile_id()
            rows = conn.execute(
                "SELECT * FROM jobs WHERE (profile_id=? OR profile_id IS NULL)",
                (pid,)
            ).fetchall()
            jobs = [db._serialize_job_row(r) for r in rows]

        if max_stellen and max_stellen > 0:
            jobs = jobs[:max_stellen]

        recomputed = 0
        unchanged = 0
        deltas: list[int] = []
        # v1.7.17 (#917 Defekt D): der Batch setzte Scores STUMM auf 0 —
        # eine gute Stelle rutschte von 83 auf 0 (Ausschluss-Keyword in
        # einer redaktionellen Notiz) und niemand erfuhr warum, waehrend
        # stelle_bearbeiten denselben Fall sauber begruendet. Jetzt
        # liefert der Lauf fuer harte Nullungen und grosse Ruecklaeufe
        # den Grund mit.
        auffaellig: list[dict] = []
        for j in jobs:
            old_score = int(j.get("score") or 0)
            try:
                new_score = int(calculate_score(j, criteria))
            except Exception as e:
                logger.warning("Score-Recompute fuer %s fehlgeschlagen: %s",
                               j.get("hash"), e)
                continue
            # v1.7.22 (#942): Teilscores immer nachziehen, auch wenn die
            # Summe gleich bleibt — der Bestand hat sie noch gar nicht,
            # und ohne sie zeigt die Liste weiter nur eine nackte Zahl.
            _teile = {}
            if j.get("_fachscore") is not None:
                _teile = {"fachscore": j.get("_fachscore"),
                          "rahmenscore": j.get("_rahmenscore")}
            if new_score == old_score and _teile:
                try:
                    db.update_job(j.get("hash"), _teile)
                except Exception:
                    pass
            if new_score != old_score:
                try:
                    db.update_job(j.get("hash"), {"score": new_score, **_teile})
                    recomputed += 1
                    deltas.append(new_score - old_score)
                except Exception as e:
                    logger.warning("update_job fuer %s fehlgeschlagen: %s",
                                   j.get("hash"), e)
                    continue
                if new_score == 0 and j.get("_ko_ausschluss"):
                    auffaellig.append({
                        "hash": j.get("hash"),
                        "titel": j.get("title"),
                        "alt": old_score, "neu": 0,
                        "grund": (f"Ausschluss-Keyword "
                                  f"'{j['_ko_ausschluss']}' im Text — "
                                  "harter K.o. Steht der Begriff in einer "
                                  "redaktionellen Notiz, gehoert sie "
                                  "hinter eine '---'-Trennzeile (#603)."),
                    })
                elif new_score - old_score <= -20:
                    auffaellig.append({
                        "hash": j.get("hash"),
                        "titel": j.get("title"),
                        "alt": old_score, "neu": new_score,
                        "grund": "starker Rueckgang — Kriterien/Regler "
                                 "pruefen (scoring_vorschau zeigt die "
                                 "Rechnung im Detail)",
                    })
            else:
                unchanged += 1

        avg_delta = sum(deltas) / len(deltas) if deltas else 0
        result = {
            "status": "fertig",
            "verarbeitet": len(jobs),
            "geaendert": recomputed,
            "unveraendert": unchanged,
            "durchschnittliche_aenderung": round(avg_delta, 1),
            "max_anstieg": max(deltas) if deltas else 0,
            "max_rueckgang": min(deltas) if deltas else 0,
        }
        if auffaellig:
            result["auffaellige_aenderungen"] = auffaellig[:20]
            if len(auffaellig) > 20:
                result["auffaellige_aenderungen_gesamt"] = len(auffaellig)
        return result

    @mcp.tool()
    def suchperformance_auswerten() -> dict:
        """Welche Quelle fuehrt tatsaechlich zu Bewerbungen? (#783/B28, v1.7.10)

        Wertet die KOMPLETTE Kette rueckwirkend aus Bestandsdaten aus:
        gefunden -> aussortiert (mit Top-Gruenden) -> beworben -> Interview/
        Angebot, je Quelle. Die eigentliche Kennzahl ist die BEWERBUNGSQUOTE
        pro Quelle, nicht die Trefferzahl — eine Quelle mit 7 Treffern und
        2 Bewerbungen schlaegt eine mit 100 Treffern und 0.

        Ehrliche Grenze (v1.7): Auswertung auf QUELLEN-Ebene. Die Ebene
        einzelner Such-Queries braucht eine Lauf-Protokollierung
        (search_runs) — das ist der v1.8-Teil von #783; die Beta-Linie
        fuehrt mit `scraper_runs` (B25/#735) bereits eine Lauf-Historie.
        """
        conn = db.connect()
        pid = db.get_active_profile_id()

        quellen: dict = {}
        for r in conn.execute(
            "SELECT source, COUNT(*) AS n, "
            "SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) AS aktiv "
            "FROM jobs WHERE (profile_id=? OR profile_id IS NULL) "
            "GROUP BY source", (pid,)
        ).fetchall():
            src = r["source"] or "unbekannt"
            quellen[src] = {
                "gefunden": r["n"],
                "aktiv": r["aktiv"] or 0,
                "aussortiert": r["n"] - (r["aktiv"] or 0),
                "top_aussortier_gruende": {},
                "beworben": 0, "interviews": 0, "angebote": 0,
            }

        # Top-Aussortier-Gruende je Quelle (Mehrfach-Gruende als JSON-Liste
        # werden als Rohstring gezaehlt — fuer das Ranking reicht das)
        for r in conn.execute(
            "SELECT source, dismiss_reason, COUNT(*) AS n FROM jobs "
            "WHERE is_active=0 AND (profile_id=? OR profile_id IS NULL) "
            "AND COALESCE(dismiss_reason,'') != '' "
            "GROUP BY source, dismiss_reason", (pid,)
        ).fetchall():
            src = r["source"] or "unbekannt"
            if src in quellen:
                quellen[src]["top_aussortier_gruende"][r["dismiss_reason"]] = r["n"]
        for q in quellen.values():
            q["top_aussortier_gruende"] = dict(sorted(
                q["top_aussortier_gruende"].items(),
                key=lambda kv: -kv[1])[:3])

        # Erfolgs-Kette: Bewerbung -> Interview -> Angebot je Quelle.
        # Verknuepfung ueber jobs.hash (seit #764 mit application_jobs
        # synchron); Fallback auf applications.source fuer Bewerbungen
        # ohne verknuepfte Stelle.
        beworben_ids = set()
        for r in conn.execute(
            "SELECT j.source AS source, a.id AS aid, "
            "       a.has_reached_interview AS iv, a.status AS status "
            "FROM applications a JOIN jobs j ON j.hash = a.job_hash "
            "WHERE (a.profile_id=? OR a.profile_id IS NULL) "
            "AND a.status != 'in_vorbereitung'", (pid,)
        ).fetchall():
            src = r["source"] or "unbekannt"
            q = quellen.setdefault(src, {
                "gefunden": 0, "aktiv": 0, "aussortiert": 0,
                "top_aussortier_gruende": {},
                "beworben": 0, "interviews": 0, "angebote": 0})
            q["beworben"] += 1
            beworben_ids.add(r["aid"])
            if r["iv"] == 1:
                q["interviews"] += 1
            if r["status"] in ("angebot", "angenommen"):
                q["angebote"] += 1
        ohne_stelle = 0
        for r in conn.execute(
            "SELECT id, source, has_reached_interview AS iv, status "
            "FROM applications WHERE (profile_id=? OR profile_id IS NULL) "
            "AND status != 'in_vorbereitung'", (pid,)
        ).fetchall():
            if r["id"] in beworben_ids:
                continue
            src = (r["source"] or "").strip()
            if not src:
                ohne_stelle += 1
                continue
            q = quellen.setdefault(src, {
                "gefunden": 0, "aktiv": 0, "aussortiert": 0,
                "top_aussortier_gruende": {},
                "beworben": 0, "interviews": 0, "angebote": 0})
            q["beworben"] += 1
            if r["iv"] == 1:
                q["interviews"] += 1
            if r["status"] in ("angebot", "angenommen"):
                q["angebote"] += 1

        for q in quellen.values():
            basis = q["gefunden"] or q["beworben"]
            q["bewerbungsquote_prozent"] = (
                round(q["beworben"] / basis * 100, 1) if basis else 0)
            q["interview_quote_prozent"] = (
                round(q["interviews"] / q["beworben"] * 100, 1)
                if q["beworben"] else 0)

        ranking = sorted(
            (s for s, q in quellen.items() if q["beworben"] > 0),
            key=lambda s: -quellen[s]["bewerbungsquote_prozent"])
        trocken = sorted(
            s for s, q in quellen.items()
            if q["beworben"] == 0 and q["gefunden"] >= 10)

        result = {
            "status": "ok",
            "quellen": quellen,
            "ranking_nach_bewerbungsquote": ranking,
            "quellen_ohne_einzige_bewerbung": trocken,
            "hinweis_trocken": (
                "Quellen ohne Bewerbung trotz >=10 Funden sind KANDIDATEN "
                "fuer die Deaktivierung — aber Vorschlag, keine Automatik: "
                "eine Quelle kann drei Monate trocken laufen und dann die "
                "passende Stelle liefern."
            ) if trocken else "",
            "grenze": (
                "Auswertung auf Quellen-Ebene aus Bestandsdaten. Einzelne "
                "Such-Queries sind erst mit der Lauf-Protokollierung "
                "(v1.8-Teil von #783) zuordenbar."
            ),
        }
        if ohne_stelle:
            result["bewerbungen_ohne_quelle"] = ohne_stelle
        return result

    @mcp.tool()
    def kalibrierung_backtest(
        stichprobe_dismissed: int = 200,
        modus: str = "aktuell",
        dry_run: bool = True,
    ) -> dict:
        """Backtest der Suchkriterien gegen die eigene Bewerbungshistorie (#778/C29).

        Prueft, wie die AKTUELLEN Kriterien die Vergangenheit bewertet
        haetten: Score-Verteilung der Stellen, auf die tatsaechlich beworben
        wurde (positive Labels), gegen eine Zufallsstichprobe der
        Aussortierten (negative Labels). Liefert einen Schwellen-Vorschlag
        (niedrigster Bewerbungs-Score x 0,8) und warnt, wenn historische
        Bewerbungen unter der aktuellen `min_score_schwelle` laegen.

        ⛔ GARANTIE: Reine SCHATTENRECHNUNG. Dieses Tool ruft NIEMALS
        scores_neu_berechnen auf und schreibt keinen einzigen Score in die
        jobs-Tabelle — egal welche Parameter. Der dry_run-Parameter
        existiert nur der Konvention wegen; es gibt keinen Schreibmodus.

        Nutzung nach jeder Kriterienaenderung: erst Backtest ansehen,
        dann entscheiden, dann (separat) scores_neu_berechnen().

        Args:
            stichprobe_dismissed: Groesse der Zufallsstichprobe aussortierter
                Stellen (Default 200).
            modus: 'aktuell' = Kriterien wie konfiguriert; 'idf' = mit
                Seltenheitsgewichtung + Top-5-Deckelung; 'beide' = Vergleich
                der beiden Varianten (zum Entscheiden, ob sich das
                IDF-Opt-in lohnt).
            dry_run: ohne Funktion — der Backtest persistiert nie.
        """
        from ..services.kalibrierung import backtest as _backtest
        if modus not in ("aktuell", "idf", "beide"):
            return {"fehler": "modus muss 'aktuell', 'idf' oder 'beide' sein."}
        result = _backtest(db, stichprobe_dismissed=stichprobe_dismissed,
                           modus=modus)
        if not dry_run:
            result["hinweis_dry_run"] = (
                "dry_run=False hat keine Wirkung — der Backtest ist per "
                "Design eine Schattenrechnung und persistiert nie."
            )
        return result

    @mcp.tool()
    def linkedin_browser_search(
        keywords: list[str] = None,
        location: str = "Deutschland",
        remote_only: bool = False,
        max_pages: int = 3
    ) -> dict:
        """VERALTET: LinkedIn Browser-Suche ist deaktiviert (#159).

        LinkedIn blockiert automatisierte Zugriffe zuverlaessig.
        Nutze stattdessen Claude-in-Chrome Extension:
        1. Oeffne LinkedIn im Chrome-Browser mit Claude-in-Chrome
        2. Suche manuell nach Stellen
        3. Uebertrage gefundene Stellen mit stelle_manuell_anlegen()

        Args:
            keywords: (ignoriert)
            location: (ignoriert)
            remote_only: (ignoriert)
            max_pages: (ignoriert)
        """
        return {
            "status": "veraltet",
            "nachricht": (
                "Die automatische LinkedIn-Suche via Playwright ist deaktiviert (#159). "
                "LinkedIn blockiert automatisierte Zugriffe zuverlaessig. "
                "Nutze stattdessen: 1) Claude-in-Chrome Extension oeffnen, "
                "2) LinkedIn manuell durchsuchen, "
                "3) Stellen mit stelle_manuell_anlegen() uebertragen."
            ),
        }

    # v1.7.17 (#917 Defekt D): redaktionelle Notizen im Beschreibungsfeld
    # erkennen, die NICHT hinter der '---'-Trennzeile (#603) stehen.
    # Belegter Fall: eine Notiz mit der LinkedIn-Bewerberstatistik
    # ("20 % Berufseinsteiger") stand im Anzeigentext-Teil — das
    # Ausschluss-Keyword feuerte und setzte eine 49er-Stelle hart auf 0.
    # Die Konvention existierte seit #603, war aber in keiner
    # Tool-Beschreibung erwaehnt — ein Agent traf sie nur zufaellig.
    _EDITORIAL_MARKER = (
        "pbp-", "erfasst", "hinweis:", "bewerberlage", "bewerberfeld",
        "notiz:", "auffaellig", "gehaltsschaetzung", "quelle:",
        "recherche:", "einschaetzung:",
    )

    def _editorial_ohne_trenner(beschreibung: str) -> str | None:
        """Warntext, wenn Notiz-Marker VOR der '---'-Trennzeile stehen."""
        if not beschreibung:
            return None
        anzeigenteil = beschreibung.split("\n---", 1)[0].lower()
        treffer = [m for m in _EDITORIAL_MARKER if m in anzeigenteil]
        if not treffer:
            return None
        return (
            "Die Beschreibung enthaelt vermutlich redaktionelle Notizen "
            f"(erkannt an: {', '.join(sorted(treffer)[:3])}), die NICHT "
            "durch eine '---'-Zeile vom Anzeigentext getrennt sind. "
            "Solche Notizen zaehlen dann ins Scoring — ein Ausschluss-"
            "Keyword darin setzt den Score hart auf 0 (#603/#917). "
            "Konvention: erst der Original-Anzeigentext, dann eine Zeile "
            "mit '---', dann die Notizen."
        )

    # v1.7.42 (#919): `stelle_manuell_anlegen` ist der EINZIGE Schreibweg
    # fuer eine von aussen gefundene Stelle — mit Blacklist-Pruefung,
    # Duplikat-Stufen, Anker-Pflicht und Scoring. Der LinkedIn-Import
    # ruft dieselbe Funktion auf, statt eine zweite Fassung zu bauen
    # (das Muster aus #963/#987/#991/#992, siebenmal dieselbe Lehre).
    # Deshalb steht der Rumpf jetzt in `_stelle_uebernehmen`; das Tool
    # ist die Huelle darum.
    @mcp.tool()
    def stelle_manuell_anlegen(
        titel: str,
        firma: str,
        url: str = "",
        ort: str = "",
        beschreibung: str = "",
        quelle: str = "manuell",
        remote: str = "unbekannt",
        stellenart: str = "festanstellung",
        force: bool = False,
        kontakt_name: str = "",
        kontakt_email: str = "",
        kontakt_telefon: str = "",
    ) -> dict:
        """Legt eine Stelle manuell an (z.B. von LinkedIn/XING via Claude-in-Chrome) (#160).

        Der Weg fuer alles, was PBP nicht selbst gefunden hat: eine Stelle
        aus dem Browser, aus einer Mail, aus einem Gespraech. Prueft
        Blacklist (#729/#790/#992), Duplikate (#317/#567/#670) und den
        Anker (#766), berechnet den Score und legt an.

        Args:
            titel: Stellentitel (Pflicht).
            firma: Firmenname (Pflicht).
            url: Link zur ORIGINAL-Ausschreibung (Detailseite, keine
                Suchergebnis-URL — #645/#763).
            ort: Arbeitsort.
            beschreibung: Anzeigentext. Je vollstaendiger, desto
                belastbarer der Score; unter 50 Zeichen gilt die Stelle
                als unbewertet (#756/#989).
            quelle: Herkunft ('linkedin', 'xing', 'firmenwebsite', ...).
            remote: 'remote' | 'hybrid' | 'vor_ort' | 'unbekannt'.
            stellenart: 'festanstellung' | 'freelance' | 'praktikum' |
                'werkstudent'.
            force: True = erkanntes Duplikat/Blacklist ignorieren (#670).
            kontakt_name: Ansprechpartner — wird als Kontakt angelegt und
                mit der Stelle verknuepft (Anker #766).
            kontakt_email: E-Mail des Ansprechpartners.
            kontakt_telefon: Telefonnummer des Ansprechpartners.
        """
        return _stelle_uebernehmen(
            titel=titel, firma=firma, url=url, ort=ort,
            beschreibung=beschreibung, quelle=quelle, remote=remote,
            stellenart=stellenart, force=force, kontakt_name=kontakt_name,
            kontakt_email=kontakt_email, kontakt_telefon=kontakt_telefon)

    def _stelle_uebernehmen(
        titel: str,
        firma: str,
        url: str = "",
        ort: str = "",
        beschreibung: str = "",
        quelle: str = "manuell",
        remote: str = "unbekannt",
        stellenart: str = "festanstellung",
        force: bool = False,
        kontakt_name: str = "",
        kontakt_email: str = "",
        kontakt_telefon: str = "",
    ) -> dict:
        """Der EINE Schreibweg fuer eine von aussen gefundene Stelle (#160).

        Rumpf von `stelle_manuell_anlegen` und zugleich der Aufruf, den der
        LinkedIn-Import (#919) benutzt — damit es keine zweite Fassung
        dieser Regeln gibt. Die Stelle wird geprueft, bewertet und
        erscheint danach in stellen_anzeigen().

        ⛔ ANKER-PFLICHT (#766) — VOR dem Aufruf beachten:
        Jede Stelle braucht mindestens EINEN dieser drei Anker, sonst ist sie
        fuer den Nutzer wertlos (er kann sich nicht bewerben und die Anzeige
        nicht nachladen):

          1. `url` — die DETAIL-URL der Anzeige (nicht die Suchergebnis-Seite)
          2. `kontakt_name`/`kontakt_email`/`kontakt_telefon` — der
             Ansprechpartner. Bei Vermittler-Stellen mit unbekanntem
             Endkunden ist der Recruiter-Kontakt oft das Einzige, was es gibt.
          3. Die Anzeige als Dokument hochladen (nach dem Anlegen).

        Eine zusammenfassende NOTIZ ist KEIN gueltiger Ersatz fuer die
        Beschreibung. Wenn beim Scrapen oder in der Browser-Recherche keine
        Detail-URL greifbar ist, dann stattdessen den ANZEIGENTEXT vollstaendig
        uebernehmen UND den Kontakt festhalten. Ohne Anker wird die Stelle zwar
        angelegt, aber im Result steht eine `anker_warnung` — die gehoert
        ungefiltert an den Nutzer weitergegeben.

        WICHTIG: Vor dem Anlegen wird automatisch geprueft ob bereits eine
        Bewerbung mit aehnlicher Firma+Titel existiert (#317). Bei klarem
        Duplikat-Verdacht wird eine Warnung zurueckgegeben und die Stelle
        NICHT angelegt — es sei denn `force=True`.

        v1.7.0-beta.87 (#670): Die Duplikat-Erkennung ist verschaerft. Ein
        einzelnes geteiltes Domain-Keyword (z.B. "PLM") oder bloße Zeitnaehe
        bei gleicher Firma blockt NICHT mehr — nur noch eine hinreichend hohe
        Titel-Aehnlichkeit. Unterschiedliche URLs gelten als starkes
        "verschiedene Stellen"-Signal. Mit `force=True` kann ein erkanntes
        Duplikat dennoch angelegt werden (die Warnung wird im Result als
        `duplikat_uebersteuert` mitgeliefert).

        Args:
            titel: Stellentitel (z.B. 'Senior Projektmanager PLM')
            firma: Firmenname
            url: Link zur Stellenanzeige
            ort: Arbeitsort (z.B. 'Hamburg', 'Remote')
            beschreibung: Stellenbeschreibung (so ausfuehrlich wie moeglich).
                NOTIZEN-KONVENTION (#603/#917): eigene Anmerkungen,
                Recherche-Ergebnisse oder Bewerberstatistiken gehoeren
                HINTER eine Zeile mit '---' (erst Original-Anzeigentext,
                dann '---', dann Notizen). Alles vor der Trennzeile
                zaehlt ins Scoring — ein Ausschluss-Keyword in einer
                Notiz setzt den Score sonst hart auf 0.
            quelle: Herkunft der Stelle (z.B. 'linkedin', 'xing', 'firmenwebsite', 'manuell')
            remote: Remote-Level ('remote', 'hybrid', 'vor_ort', 'unbekannt')
            stellenart: Art der Stelle ('festanstellung', 'freelance', 'praktikum', 'werkstudent')
            force: True = erkanntes Duplikat ignorieren und trotzdem anlegen (#670).
            kontakt_name: Ansprechpartner/Recruiter — wird als Kontakt angelegt
                und mit der Stelle verknuepft (Anker #766).
            kontakt_email: E-Mail des Ansprechpartners.
            kontakt_telefon: Telefonnummer des Ansprechpartners.
        """
        if not titel or not firma:
            return {"fehler": "Titel und Firma sind Pflichtfelder."}

        # #729: Blacklist-Check auf die Firma VOR dem Anlegen. Vorher wurde eine
        # Stelle einer geblacklisteten Firma kommentarlos angelegt (z.B. via
        # Claude-in-Chrome). force=True ueberbrueckt den Block bewusst.
        # v1.7.11 (#790/C31): Der Titel entscheidet mit — ein Firmen-Block
        # mit gesetzter Ausnahme laesst fachlich passende Rollen durch.
        _bl_hit = db.is_company_blacklisted(firma, titel)
        _bl_ausnahme = db.blacklist_ausnahme_treffer(firma, titel)
        if _bl_hit and not force:
            grund = _bl_hit.get("reason") or "ohne Begruendung"
            # #992: auch die Abweisung von Hand gehoert ins Protokoll —
            # sonst zaehlt nur, was der Suchlauf verwirft, und genau die
            # Stellen, die der Mensch selbst gefunden hat, fehlen.
            db.record_blacklist_block(
                {"title": titel, "company": firma, "url": url,
                 "source": quelle},
                {"typ": "firma", "wert": _bl_hit.get("value"),
                 "eintrag_id": _bl_hit.get("id"),
                 "grund": _bl_hit.get("reason") or ""},
                kontext="manuell_abgewiesen")
            return {
                "fehler": (
                    f"Firma '{firma}' steht auf der Blacklist ({grund}). "
                    "Stelle nicht angelegt."
                ),
                "blacklist_treffer": _bl_hit.get("value"),
                "hinweis": "Mit force=True kann die Stelle dennoch angelegt werden.",
                "hinweis_ausnahme": (
                    "Wenn diese Firma grundsaetzlich unerwuenscht ist, aber "
                    "einzelne Fachrollen passen (typisch bei Personal"
                    "dienstleistern), setze eine Ausnahme statt force: "
                    "blacklist_verwalten('hinzufuegen', 'firma', "
                    f"'{_bl_hit.get('value')}', "
                    "ausser_wenn_titel_enthaelt=['PLM', 'PDM'])."
                ),
            }

        from ..job_scraper import stelle_hash, calculate_score, extract_salary_from_text, estimate_salary

        # v1.7.0-beta.47 (#613): Wenn quelle="manuell" der Default ist
        # aber die URL klar auf eine bekannte Quelle zeigt, wird das
        # uebersteuert. Explizit gesetzte quelle bleibt unveraendert.
        if quelle == "manuell" and url:
            from ..services.url_to_source import detect_source_from_url
            detected = detect_source_from_url(url)
            if detected != "manuell":
                quelle = detected

        job_hash = stelle_hash(quelle, f"{firma} {titel}")

        # Check for duplicates (#219: nur echte DB-Treffer, nicht scope-Prefix)
        existing_job = db.get_job(job_hash)
        if existing_job:
            return {"fehler": f"Diese Stelle existiert bereits (Hash: {existing_job['hash']})."}

        # Duplikat-Pruefung (#317 + #471 + v1.6.9 #567: zweistufig)
        # Stufe A: laufende Bewerbung mit Titel-Match → blocken
        # Stufe B: identische AKTIVE Stelle → idempotent vorhandenen Hash zurueck
        # Stufe C: aussortierte/abgelehnte Eintraege blocken NICHT mehr
        from ..duplicate_detection import find_duplicate_job

        # v1.6.9 (#567): nur LAUFENDE Bewerbungen blocken — abgeschlossene
        # (abgelehnt/abgelaufen/zurueckgezogen/angenommen) sind kein Hindernis
        # fuer eine neue Bewerbung bei der gleichen Firma auf eine andere Stelle.
        TERMINAL_STATUSES = ("abgelehnt", "abgelaufen", "zurueckgezogen", "angenommen")
        all_apps = db.get_applications()
        running_apps = [a for a in all_apps
                        if (a.get("status") or "") not in TERMINAL_STATUSES]

        # v1.7.0-beta.87 (#670): force=True ueberspringt den Duplikat-Block.
        # Der Verdacht wird aber gesammelt und im Erfolgs-Result transparent
        # gemacht (`duplikat_uebersteuert`).
        uebersteuerter_verdacht = None

        # Stufe A — laufende Bewerbung mit Titel-Match?
        app_hit = find_duplicate_job(firma, titel, url, running_apps)
        if app_hit and force:
            uebersteuerter_verdacht = {
                "stufe": "laufende_bewerbung",
                "grund": app_hit["grund"],
                "shared_tokens": app_hit.get("shared_tokens"),
                "existing_application_id": app_hit["job"].get("id", "")[:8],
            }
            app_hit = None
        if app_hit:
            app = app_hit["job"]
            return {
                "warnung": "duplikat_bewerbung",
                "grund": app_hit["grund"],
                "nachricht": (
                    f"Moegliches Duplikat: laufende Bewerbung {app['id'][:8]} bei "
                    f"{app.get('company')} (Status: {app.get('status', 'unbekannt')}, "
                    f"Titel: '{app.get('title')}'). "
                    f"Match-Grund: {app_hit['grund']}"
                    + (f", gemeinsame Tokens: {app_hit.get('shared_tokens')}"
                       if app_hit.get("shared_tokens") else "")
                    + ". Die Stelle wurde NICHT angelegt. "
                    "Falls es sich tatsaechlich um eine andere Stelle handelt, "
                    "ergaenze den Titel eindeutig (z.B. Projekt- oder Team-Name) "
                    "oder nutze stelle_mergen(), falls eine frueher angelegte "
                    "Stelle die zweite Variante ersetzt."
                ),
                "existing_application_id": app["id"][:8],
                "shared_tokens": app_hit.get("shared_tokens"),
                "trotzdem_anlegen": False,
            }

        # Stufe B — identische AKTIVE Stelle (is_active=1) → idempotent
        # vorhandenen Hash zurueckgeben statt blocken. Aussortierte Stellen
        # blocken NICHT, weil sie schon mal aktiv abgelehnt wurden.
        active_jobs = db.get_active_jobs(exclude_applied=False)
        active_hit = find_duplicate_job(firma, titel, url, active_jobs)
        if (active_hit and force
                and active_hit["job"].get("hash") != job_hash):
            uebersteuerter_verdacht = uebersteuerter_verdacht or {
                "stufe": "aktive_stelle",
                "grund": active_hit["grund"],
                "shared_tokens": active_hit.get("shared_tokens"),
                "existing_hash": active_hit["job"].get("hash"),
            }
            active_hit = None
        if active_hit and active_hit["job"].get("hash") != job_hash:
            existing = active_hit["job"]
            return {
                "warnung": "duplikat_aktive_stelle",
                "status": "bereits_vorhanden",
                "grund": active_hit["grund"],
                "nachricht": (
                    f"Identische aktive Stelle existiert bereits: "
                    f"'{existing.get('title')}' bei {existing.get('company')} "
                    f"(Quelle: {existing.get('source', 'unbekannt')}, "
                    f"Hash: {existing['hash']}). Es wird der vorhandene Hash "
                    "zurueckgegeben — kein Duplikat in der DB."
                ),
                "hash": existing["hash"],
                "existing_hash": existing["hash"],
                "shared_tokens": active_hit.get("shared_tokens"),
            }
        # Stufe C: alles andere (auch aussortierte Stellen bei gleicher Firma)
        # darf durchgehen.

        criteria = db.get_search_criteria()
        job = {
            "hash": job_hash,
            "title": titel,
            "company": firma,
            "url": url,
            "location": ort,
            "description": beschreibung,
            "source": quelle,
            "remote_level": remote,
            "employment_type": stellenart,
            # #732/#733: bewusste User-Aktion — nicht dem automatischen
            # Geo-Aussortierer (save_jobs) zum Opfer fallen lassen.
            "_manual_entry": True,
        }

        # Score
        job["score"] = calculate_score(job, criteria)

        # Extract/estimate salary
        text = f"{beschreibung} {titel}"
        s_min, s_max, s_type = extract_salary_from_text(text)
        if s_min:
            job["salary_min"] = s_min
            job["salary_max"] = s_max
            job["salary_type"] = s_type
            job["salary_estimated"] = 0
        else:
            s_min, s_max, s_type = estimate_salary(titel, stellenart, ort)
            job["salary_min"] = s_min
            job["salary_max"] = s_max
            job["salary_type"] = s_type
            job["salary_estimated"] = 1

        # Geocoding (#167): Entfernung berechnen wenn Standort bekannt
        if ort:
            try:
                from ..services.geocoding_service import get_user_coordinates, geocode_and_calculate_distance
                user_coords = get_user_coordinates(db)
                if user_coords:
                    dist = geocode_and_calculate_distance(ort, user_coords[0], user_coords[1])
                    if dist is not None:
                        job["distance_km"] = dist
            except Exception:
                pass

        db.save_jobs([job])

        # #766: Kontakt als Anker. Wird VOR der Anker-Pruefung angelegt, damit
        # eine Stelle mit Recruiter-Kontakt (Vermittler ohne bekannten
        # Endkunden!) nicht faelschlich als ankerlos gemeldet wird.
        # v1.7.67 (#1011): die Anlage laeuft ueber `kontakt_pflicht` —
        # dieselbe Stelle, an der jetzt auch die Bewerbung und die
        # Sammeluebernahme haengen. Vorher stand sie inline HIER, und
        # genau deshalb entstand bei der Sammeluebernahme kein Kontakt:
        # ob einer entsteht, hing am Anlageweg. Neu ist ausserdem die
        # Wiedererkennung — vorher legte jeder Aufruf blind an.
        from ..services import kontakt_pflicht as _kp
        _befund = _kp.sicherstellen(
            db, name=kontakt_name, email=kontakt_email,
            telefon=kontakt_telefon, firma=firma,
            ziel_art="job", ziel_id=job_hash,
            tags=["recruiter"] if quelle != "firmenwebsite" else [])
        kontakt_angelegt = (None if _befund.get("status") == "uebersprungen"
                            else _befund)

        result = {
            "status": "angelegt",
            "id": job_hash[:8],
            "hash": job_hash,
            "score": job["score"],
            "nachricht": f"Stelle '{titel}' bei {firma} angelegt (Score: {job['score']}, Quelle: {quelle}). "
                         f"Bewerte mit stelle_bewerten('{job_hash[:8]}', 'passt'/'passt_nicht').",
        }
        if job.get("distance_km"):
            result.update(_entfernung.befund(job["distance_km"]))
        # #733: Wenn die Quelle 'manuell' geblieben ist (keine erkannte URL),
        # den Aufrufer aktiv erinnern, die echte Herkunft zu setzen — sonst
        # verfaelschen KI-gesteuerte Chrome-Adds die Quellenstatistik
        # ("18 Stellen manuell", obwohl keine von Hand angelegt wurde).
        if quelle == "manuell":
            result["hinweis"] = (
                "quelle='manuell' gesetzt. Wenn die echte Herkunft bekannt "
                "ist (z.B. 'linkedin', 'xing', 'firmenwebsite'), bitte den "
                "Parameter quelle entsprechend setzen — sonst zaehlt die "
                "Stelle faelschlich als manuell angelegt. Bei bekannter URL "
                "wird die Quelle automatisch abgeleitet (#613/#733)."
            )
        # v1.7.0-beta.87 (#670): wenn ein Duplikat-Verdacht via force=True
        # uebersteuert wurde, transparent im Result melden.
        if uebersteuerter_verdacht:
            result["duplikat_uebersteuert"] = uebersteuerter_verdacht
            result["nachricht"] += (
                " HINWEIS: Es bestand ein Duplikat-Verdacht "
                f"({uebersteuerter_verdacht['grund']}), der per force=True "
                "uebersteuert wurde."
            )
        # #762: Ohne Detail-URL ist stellenbeschreibung_nachladen blockiert
        # ("Stelle hat keine URL") — und genau das Nachladen macht aus dem
        # schwachen Kurztext-Score erst einen belastbaren. Aktiv darauf hinweisen.
        if not url:
            result["url_hinweis"] = (
                "Keine URL angegeben — stellenbeschreibung_nachladen() kann die "
                "Anzeige spaeter nicht holen. Wenn die Detail-URL der Anzeige "
                "vorliegt, gleich beim Anlegen mitgeben oder per "
                "stelle_bearbeiten(url=...) nachreichen."
            )
        # #762: Kurztext -> Score ist nicht belastbar (es koennen kaum
        # MUSS-Keywords matchen). Ehrlich kennzeichnen, statt einen niedrigen
        # Score wie ein fachliches Urteil wirken zu lassen.
        if len((beschreibung or "").strip()) < 50:
            result["score_hinweis"] = (
                "Die Beschreibung ist sehr kurz — der Score ist damit NICHT "
                "belastbar. Erst mit dem Anzeigen-Volltext (nachladen oder "
                "einfuegen) wird er aussagekraeftig."
            )
        # #436: Warnung wenn URL auf Suchergebnis-Seite zeigt
        from ..job_scraper import is_search_result_url
        if url and is_search_result_url(url):
            result["url_warnung"] = (
                "Die angegebene URL zeigt auf eine Suchergebnis-Seite, nicht auf die "
                "konkrete Stellenanzeige. Die Stelle wurde trotzdem angelegt, aber der "
                "Link wird zur Such-Seite zurueckfuehren. Falls moeglich die Detail-URL "
                "der Stellenanzeige statt der Suchergebnis-URL nutzen."
            )
        # #766: Anker-Pflicht. Die Stelle wird bewusst NICHT abgelehnt (das
        # wuerde bestehende Flows brechen und die schon eingegebenen Daten
        # verwerfen) — aber der Zustand wird hart benannt statt still
        # hingenommen.
        if kontakt_angelegt and "id" in kontakt_angelegt:
            result["kontakt"] = kontakt_angelegt
        if _bl_ausnahme:
            # #790: transparent machen, WARUM die Stelle trotz Blacklist kam
            result["blacklist_ausnahme"] = {
                "eintrag": _bl_ausnahme["eintrag"],
                "begriff": _bl_ausnahme["begriff"],
                "hinweis": (
                    f"Firma steht auf der Blacklist, der Titel enthaelt aber "
                    f"'{_bl_ausnahme['begriff']}' — die hinterlegte Ausnahme "
                    "greift, die Stelle wurde angelegt."
                ),
            }
        from ..services.stellen_anker import anker_status
        _anker = anker_status(db, job)
        result["anker"] = _anker["anker"]
        if not _anker["hat_anker"]:
            result["anker_warnung"] = _anker["warnung"]
            if _anker.get("hinweis_such_url"):
                result["anker_warnung"] += " " + _anker["hinweis_such_url"]
            result["nachricht"] += (
                " ⚠ OHNE ANKER — diese Stelle ist so nicht verfolgbar "
                "(siehe anker_warnung)."
            )
        _notiz_warnung = _editorial_ohne_trenner(beschreibung)
        if _notiz_warnung:
            result["notizen_warnung"] = _notiz_warnung
        return result

    # === LinkedIn ueber die Voyager-API (#919, B36) =====================

    @mcp.tool()
    def linkedin_lauf_plan(max_begriffe: int = 12, seit: str = "",
                           geo_id: str = "", seiten: int = 2) -> dict:
        """Der erprobte LinkedIn-Weg als ausfuehrbarer Plan (#919).

        LinkedIn liefert seit April 2026 nichts mehr: der Playwright-Adapter
        steht auf Erfolgsrate 0 %, die jobspy-Variante ist deprecated. HTTP
        von aussen blockt LinkedIn zuverlaessig — Requests aus dem
        EINGELOGGTEN Chrome-Tab laufen dagegen durch. Am 17.08.2026 wurde
        dieser Weg vollstaendig durchgespielt: 22 Suchbegriffe, 511
        deduplizierte Rohtreffer, 59 Volltexte, 3 uebernommene Stellen.

        Dieses Werkzeug liefert den Plan samt fertiger Browser-Skripte;
        Claude fuehrt ihn in einem Tab auf linkedin.com aus, und
        `linkedin_treffer_uebernehmen` schreibt das Ergebnis nach PBP.

        **Der Volltext ist Pflicht, nicht Kuer.** Von 59 Titeln, die den
        Vorfilter passiert hatten, blieben nach dem Lesen der Volltexte 3
        uebrig — der beste Titel-Treffer des Laufs verlangte im Fliesstext
        ein System von der harten Ausschlussliste. Wer nur Titel und
        Kurzbeschreibung uebernimmt, liefert genau die falschen Stellen
        mit hohem Score ein.

        Args:
            max_begriffe: wie viele Suchbegriffe der Lauf umfasst. Jeder
                Begriff kostet `seiten` Requests.
            seit: ISO-Datum des letzten Laufs — daraus wird das
                Zeitfenster abgeleitet, statt fix eine Woche zu nehmen.
            geo_id: LinkedIn-Region (Vorgabe: Deutschland).
            seiten: Ergebnisseiten je Begriff (25 Treffer je Seite).
        """
        from ..job_scraper import linkedin_voyager as lv

        try:
            portal = db.get_portal_search_profile("linkedin") or {}
        except Exception:
            portal = {}
        kriterien = db.get_search_criteria() or {}
        begriffe = lv.begriffe(portal, kriterien, max_begriffe)
        if not begriffe:
            return leer(
                {"status": "leer", "begriffe": []},
                "Keine Suchbegriffe vorhanden — ohne sie hat der Lauf kein Ziel.",
                "MUSS-Begriffe setzen: suchkriterien_setzen(keywords_muss=[...]) "
                "— oder das LinkedIn-Suchprofil pflegen: "
                "suchprofil_aktualisieren('linkedin', ...).")

        fenster = lv.zeitfenster(seit)
        cfg = lv.konfig(begriffe, fenster, (geo_id or "").strip() or lv.GEO_ID_DE,
                        seiten)
        return {
            "status": "bereit",
            "quelle": "linkedin",
            "begriffe": begriffe,
            "begriffe_quelle": ("suchprofil_linkedin" if portal.get("primaere_suchen")
                                else "keywords_muss"),
            "zeitfenster": fenster,
            "requests_gesamt": len(begriffe) * cfg["seiten"],
            "konfiguration": cfg,
            "js": {
                "1_ernte": lv.js_mit_konfig(lv.JS_ERNTE, cfg),
                "2_status": lv.JS_STATUS,
                "3_volltexte": ("Vorlage — <IDS> durch die ausgewaehlten "
                                "Job-IDs ersetzen (JSON-Liste): "
                                + lv.JS_VOLLTEXTE.replace("__IDS__", "<IDS>")
                                  .replace("__CFG__", "CFG_PLATZHALTER")),
                "4_ausgabe": lv.JS_AUSGABE,
            },
            "js_volltexte_konfig": cfg,
            "ablauf": [
                "Tab auf die LinkedIn-Jobsuche oeffnen (eingeloggt).",
                "Skript 1 ausfuehren — es laeuft als async IIFE weiter, "
                "auch wenn der Aufruf sofort zurueckkommt.",
                "Skript 2 wiederholt aufrufen, bis 'fertig' true ist.",
                "Titel sichten und die Job-IDs waehlen, deren Volltext "
                "geholt werden soll (der Vorfilter).",
                "Skript 3 mit diesen IDs starten, danach wieder Skript 2.",
                "Skript 4 rendert das Ergebnis in die Seite; mit "
                "get_page_text abholen — javascript_tool kappt bei rund "
                "1000 Zeichen.",
                "linkedin_treffer_uebernehmen(treffer=[...]) aufrufen.",
            ],
            "stolpersteine": [
                "Navigation loescht window.__pbp_ln — der ganze Lauf muss "
                "auf EINEM Tab ohne Seitenwechsel passieren.",
                "javascript_tool bricht nach rund 45 s ab. Deshalb laufen "
                "die Schleifen als async IIFE und der Fortschritt wird "
                "abgefragt statt abgewartet.",
                "javascript_tool kappt die Rueckgabe bei rund 1000 "
                "Zeichen. Anzeigentexte deshalb NIE zurueckgeben, sondern "
                "ueber Skript 4 rendern und mit get_page_text holen.",
                "URLs mit Query-String in einer Rueckgabe loesen einen "
                "Block aus. Die Skripte bauen ihre URLs deshalb selbst und "
                "geben nur Zahlen zurueck.",
                f"{lv.PAUSE_MS} ms zwischen den Requests — damit liefen "
                "511 Trefferzeilen plus 59 Volltexte ohne Drosselung durch.",
            ],
            "fehlerdeutung": lv.FEHLER_TEXTE,
            "hinweis": (
                "Ohne eingeloggten Chrome bricht der Lauf ab: "
                "linkedin_treffer_uebernehmen(login_fehlt=True) meldet das "
                "als 'wartet_auf_login'. Das ist KEIN Befund ueber den "
                "Stellenmarkt — die Quelle bleibt aktiv und wird nicht "
                "automatisch deaktiviert (#906)."
            ),
        }

    @mcp.tool()
    def linkedin_treffer_uebernehmen(treffer: list = None,
                                     dry_run: bool = True,
                                     login_fehlt: bool = False,
                                     rohtreffer: int = 0) -> dict:
        """Uebernimmt die geernteten LinkedIn-Stellen nach PBP (#919).

        Erwartet je Eintrag mindestens `job_id`, `titel`, `firma` und
        `beschreibung` (Volltext). Optional `ort`, `remote`,
        `anstellungsart` — und seit v1.7.67 (#1011) `kontakt_name`,
        `kontakt_email`, `kontakt_telefon`. Steht in der Anzeige eine
        Ansprechpartnerin namentlich, gehoert sie hier hinein: bisher
        hing es am Anlageweg, ob ein Kontakt entsteht.

        Schreibt ueber denselben Weg wie `stelle_manuell_anlegen` —
        Blacklist, Duplikat-Stufen, Anker-Pflicht und Scoring gelten
        unveraendert. Eine zweite Fassung dieser Regeln waere genau der
        Fehler, der PBP in #963, #987, #991 und #992 je einmal gekostet
        hat.

        **Ohne Volltext keine Anlage.** Eintraege unter
        `linkedin_voyager.MIN_BESCHREIBUNG` Zeichen werden uebersprungen
        und gezaehlt, statt mit halbem Text angelegt zu werden.

        Args:
            treffer: die geernteten Stellen.
            dry_run: True (Vorgabe) zeigt nur, was passieren wuerde.
            login_fehlt: True meldet den Lauf als 'wartet_auf_login' —
                kein Befund ueber den Markt, keine Auto-Deaktivierung.
            rohtreffer: Trefferzahl VOR dem Vorfilter. Ohne sie ist
                "3 angelegt" nicht einzuordnen (#813/#989).
        """
        from ..job_scraper import linkedin_voyager as lv

        if login_fehlt:
            return {
                "status": "wartet_auf_login",
                "quelle": "linkedin",
                "nachricht": lv.FEHLER_TEXTE["nicht_eingeloggt"],
                "hinweis": (
                    "Die Quelle bleibt aktiv und wird NICHT automatisch "
                    "deaktiviert — ein fehlender Login sagt nichts ueber "
                    "den Stellenmarkt aus (#906)."
                ),
            }

        eintraege = [e for e in (treffer or []) if isinstance(e, dict)]
        trichter = lv.trichter_leer()
        if not eintraege:
            return leer(
                {"status": "leer", "trichter": trichter},
                "Keine Treffer uebergeben.",
                "Erst linkedin_lauf_plan() ausfuehren und die Ernte hier "
                "uebergeben.")

        trichter["rohtreffer"] = max(int(rohtreffer or 0), len(eintraege))
        trichter["nach_vorfilter"] = len(eintraege)

        angelegt, uebersprungen = [], []

        def _skip(eintrag, grund, detail=""):
            trichter["uebersprungen"] += 1
            trichter["gruende"][grund] = trichter["gruende"].get(grund, 0) + 1
            uebersprungen.append({
                "job_id": eintrag.get("job_id"),
                "titel": eintrag.get("titel"),
                "firma": eintrag.get("firma"),
                "grund": grund, "detail": detail})

        for e in eintraege:
            titel = str(e.get("titel") or "").strip()
            firma = str(e.get("firma") or "").strip()
            job_id = str(e.get("job_id") or "").strip()
            beschreibung = str(e.get("beschreibung") or "").strip()

            if not titel or not firma:
                _skip(e, "titel_oder_firma_fehlt")
                continue
            if not job_id:
                # Ohne ID kein Anker — und ohne Anker ist die Stelle fuer
                # den Nutzer wertlos (#766).
                _skip(e, "kein_anker")
                continue
            if len(beschreibung) < lv.MIN_BESCHREIBUNG:
                _skip(e, "volltext_fehlt",
                      f"{len(beschreibung)} Zeichen, noetig sind "
                      f"{lv.MIN_BESCHREIBUNG}")
                continue
            trichter["volltexte"] += 1

            if dry_run:
                trichter["angelegt"] += 1
                angelegt.append({"job_id": job_id, "titel": titel,
                                 "firma": firma,
                                 "beschreibung_zeichen": len(beschreibung)})
                continue

            # v1.7.67 (#1011) AK 3: die Sammeluebernahme nimmt jetzt
            # Kontaktdaten entgegen. Sie hatte keine — und deshalb
            # entstand bei 11 von 14 Stellen eines Arbeitstags kein
            # einziger Ansprechpartner, obwohl in mindestens einem
            # Anzeigentext eine namentlich stand. Ob ein Kontakt
            # entsteht, darf nicht am Anlageweg haengen.
            res = _stelle_uebernehmen(
                titel=titel, firma=firma, url=lv.anzeige_url(job_id),
                ort=str(e.get("ort") or "").strip(),
                beschreibung=beschreibung, quelle="linkedin",
                remote=str(e.get("remote") or "unbekannt"),
                stellenart=str(e.get("anstellungsart") or "festanstellung"),
                kontakt_name=str(e.get("kontakt_name") or "").strip(),
                kontakt_email=str(e.get("kontakt_email") or "").strip(),
                kontakt_telefon=str(e.get("kontakt_telefon") or "").strip())
            if res.get("hash") and not res.get("warnung"):
                trichter["angelegt"] += 1
                _eintrag = {"job_id": job_id, "titel": titel,
                            "firma": firma, "hash": res["hash"],
                            "score": res.get("score")}
                if res.get("kontakt"):
                    _eintrag["kontakt"] = res["kontakt"]
                    trichter["kontakte"] = trichter.get("kontakte", 0) + 1
                angelegt.append(_eintrag)
            elif res.get("warnung"):
                _skip(e, res["warnung"], res.get("grund", ""))
            elif res.get("fehler"):
                grund = ("blacklist" if "Blacklist" in res["fehler"]
                         else "abgewiesen")
                _skip(e, grund, res["fehler"])
            else:
                _skip(e, "unbekannt", str(res)[:120])

        ergebnis = {
            "status": "vorschau" if dry_run else "uebernommen",
            "quelle": "linkedin",
            "dry_run": dry_run,
            "trichter": trichter,
            "trichter_text": lv.trichter_text(trichter),
            "angelegt": angelegt[:25],
            "uebersprungen": uebersprungen[:25],
        }
        if dry_run:
            ergebnis["hinweis"] = (
                "Vorschau. Erneut mit dry_run=False aufrufen, um die "
                "Stellen anzulegen.")
        elif not trichter["angelegt"] and trichter["uebersprungen"]:
            # Ehrliche Null: nichts angelegt heisst hier NICHT nichts
            # gefunden (#813).
            ergebnis["hinweis"] = (
                f"Keine Stelle angelegt — alle {trichter['uebersprungen']} "
                "wurden aussortiert. Die Gruende stehen im Trichter; das "
                "ist ein Ergebnis, kein Ausfall.")
        return ergebnis

    # === v1.7.0-beta.5: n:m + Stellen-Vergleich (#472, #580) ===

    @mcp.tool()
    def bewerbung_stelle_verknuepfen(
        bewerbung_id: str,
        stellen_hash: str,
        version_label: str = "",
        ist_primaer: bool = False,
    ) -> dict:
        """Verknuepft eine Bewerbung mit einer (zusaetzlichen) Stelle (#472).

        Use-Case: Eine Bewerbung kann sich auf MEHRERE Stellen-Versionen
        beziehen — z.B. wenn eine Firma die Stelle re-postet, oder wenn
        man sich gleichzeitig auf zwei verwandte Stellen bewirbt
        (Vermittler + Endkunde, oder Senior + Lead Variante).

        Args:
            bewerbung_id: ID der Bewerbung (mit oder ohne APP-Praefix).
            stellen_hash: Hash der Stelle (mit oder ohne JOB-Praefix).
            version_label: Optionale Bezeichnung (z.B. 'Senior-Variante',
                'Repost vom 15.05.', 'Endkunde-Sicht').
            ist_primaer: Wenn True, wird diese Verknuepfung als primaer
                gesetzt (alle anderen werden auf nicht-primaer gesetzt).
        """
        from ..services.typed_ids import strip_prefix
        bid = strip_prefix(bewerbung_id)
        jhash = strip_prefix(stellen_hash)
        try:
            link_id = db.link_application_to_job(
                bid, jhash, version_label=version_label,
                is_primary=ist_primaer
            )
        except Exception as e:
            return {"fehler": f"Verknuepfung fehlgeschlagen: {e}"}
        return {
            "status": "verknuepft",
            "link_id": link_id,
            "bewerbung_id": bewerbung_id,
            "stellen_hash": stellen_hash,
        }

    @mcp.tool()
    def bewerbung_stelle_entknuepfen(bewerbung_id: str, stellen_hash: str) -> dict:
        """Entfernt eine Stellen-Verknuepfung von einer Bewerbung."""
        from ..services.typed_ids import strip_prefix
        bid = strip_prefix(bewerbung_id)
        jhash = strip_prefix(stellen_hash)
        ok = db.unlink_application_job(bid, jhash)
        return {"status": "entfernt" if ok else "nicht_gefunden"}

    @mcp.tool()
    def bewerbung_stellen_anzeigen(bewerbung_id: str) -> dict:
        """Listet alle Stellen, die mit einer Bewerbung verknuepft sind (#472).

        Wenn die Bewerbung ein klassisches `applications.job_hash` hat,
        ist es als is_primary=True hier mit drin (durch Migration).
        """
        from ..services.typed_ids import strip_prefix
        bid = strip_prefix(bewerbung_id)
        jobs = db.get_jobs_for_application(bid)
        return {
            "bewerbung_id": bewerbung_id,
            "anzahl": len(jobs),
            "stellen": jobs,
        }

    @mcp.tool()
    def stellenbeschreibung_nachladen(stellen_hash: str) -> dict:
        """Holt die Beschreibung einer Stelle aus ihrer URL nach (v1.7.0-beta.44, #622).

        Wenn der Score einer Stelle unzuverlaessig wirkt weil die
        Beschreibung leer oder zu kurz ist, ruft dieses Tool die URL
        auf, parsed sie und schreibt die Beschreibung zurueck in die DB.

        Eine HTTP-GET pro Aufruf — bewusst nicht fuer Massen-Crawl
        gedacht. Fuer Bulk-Refetch nutzt PBP den Auto-Engine-Step
        `_run_auto_refetch_descriptions` (max 8 Stellen pro Lauf).

        Liefert {status, chars, preview} bei Erfolg, sonst
        {status: "fehler", grund}.
        """
        from ..services.typed_ids import strip_prefix
        from ..job_scraper import fetch_description_from_detail
        import httpx
        h = strip_prefix(stellen_hash)
        job = db.get_job(h)
        if not job:
            return {"status": "fehler", "grund": "Stelle nicht gefunden",
                    "stellen_hash": stellen_hash}
        url = (job.get("url") or "").strip()
        if not url:
            return {
                "status": "fehler",
                "grund": (
                    "Stelle hat keine URL — Detail-URL der Anzeige nachpflegen via "
                    f"stelle_bearbeiten('{stellen_hash}', url='https://...') "
                    "und dann erneut versuchen."
                ),
                "vorschlag_tool": "stelle_bearbeiten",
                "vorschlag_aufruf": f"stelle_bearbeiten('{stellen_hash}', url='https://...')",
            }
        if job.get("is_search_url"):
            return {
                "status": "fehler",
                "grund": (
                    "Stelle hat nur eine Such-URL gespeichert (Quelle hat die "
                    "Detail-URL nicht ausgeliefert, #645-Fallback). "
                    f"Detail-URL nachreichen via stelle_bearbeiten('{stellen_hash}', url='https://...')."
                ),
                "url": url,
                "vorschlag_tool": "stelle_bearbeiten",
                "vorschlag_aufruf": f"stelle_bearbeiten('{stellen_hash}', url='https://...')",
            }
        try:
            from ..services import nachladen
            with httpx.Client(follow_redirects=True, timeout=15,
                              headers={"User-Agent": "PBP/1.7 (+github.com/MadGapun/PBP)"}) as client:
                befund = nachladen.beschreibung_holen(url, client, timeout=15)
                text = befund.text
        except Exception as exc:
            return {"status": "fehler", "grund": f"HTTP-Fehler: {exc}"}
        if not text or len(text) < 50:
            # v1.7.70 (#1014): der Grund kommt jetzt vom Server, nicht
            # aus einer Vermutung. "Login-Wall oder Bot-Block" steht nur
            # noch dort, wo die Anzeige wirklich lebt und trotzdem
            # nichts hergibt.
            antwort = {"status": "fehler", "grund": befund.klartext(),
                       "url": url, "got_chars": len(text or "")}
            antwort.update(befund.als_dict())
            if befund.soll_aussortiert_werden:
                # Die Mechanik gibt es im Aging-Check laengst — eine
                # Stelle, deren Anzeige der Server ausdruecklich als
                # entfernt meldet, bleibt sonst aktiv ohne Beschreibung
                # stehen und erzeugt eine Aufgabe, die niemand
                # abarbeiten kann.
                try:
                    db.dismiss_job(h, reason="veraltet_url",
                                   herkunft="automatik",
                                   notiz=befund.klartext())
                    antwort["aussortiert"] = "veraltet_url"
                except Exception as exc:      # pragma: no cover
                    antwort["aussortieren_fehlgeschlagen"] = str(exc)[:200]
            return antwort
        from ..job_scraper.textgrenzen import (ALTE_KAPPUNG, SPEICHER_MAX,
                                               ist_gekappt)
        vorher = job.get("description") or ""
        db.update_job(h, {"description": text})
        antwort = {"status": "ok", "chars": len(text), "preview": text[:200]}
        # #952: Der Fehler war stumm — "status: ok" bei halbem Text.
        # Jetzt sagt die Antwort, wenn eine Grenze erreicht wurde.
        if len(text) >= SPEICHER_MAX:
            antwort["grenze_erreicht"] = True
            antwort["hinweis"] = (
                f"Der Text erreicht die Speicher-Notbremse von "
                f"{SPEICHER_MAX} Zeichen und koennte abgeschnitten sein.")
        elif ist_gekappt(text):
            antwort["grenze_erreicht"] = True
            antwort["hinweis"] = (
                f"Der geholte Text ist exakt {ALTE_KAPPUNG} Zeichen lang — "
                "die Quelle selbst kappt hier moeglicherweise.")
        if ist_gekappt(vorher) and len(text) > len(vorher):
            antwort["gekappten_text_geheilt"] = True
            antwort["hinweis"] = (
                f"Vorher {len(vorher)} Zeichen (abgeschnitten), jetzt "
                f"{len(text)}. Der Anforderungsteil steht meist am Ende "
                "und war bisher nicht bewertbar.")
        return antwort

    @mcp.tool()
    def beschreibungen_nachladen_bestand(max_stellen: int = 25,
                                         nur_zaehlen: bool = True) -> dict:
        """Laedt abgeschnittene Anzeigentexte im Bestand nach (#952).

        Bis v1.7.22 kappte jeder Quellen-Adapter den Text bei exakt 2000
        Zeichen, bevor er gespeichert wurde. Betroffen ist damit der
        gesamte Altbestand — und weil der Refetch selbst kappte, half
        auch wiederholtes Nachladen nicht.

        Sinnvoll erst NACH v1.7.23: vorher holt der Lauf denselben halben
        Text zurueck.

        Args:
            max_stellen: Obergrenze pro Lauf. Jede Stelle ist ein
                HTTP-Aufruf, deshalb bewusst klein.
            nur_zaehlen: Default True — meldet nur, wie viele betroffen
                sind, ohne etwas zu holen.
        """
        import httpx

        from ..job_scraper import fetch_description_from_detail
        from ..job_scraper.textgrenzen import ist_gekappt

        aktive = db.get_active_jobs() or []
        betroffen = [j for j in aktive if ist_gekappt(j.get("description"))]
        if not betroffen:
            return {
                "status": "nichts_zu_tun",
                "geprueft": len(aktive),
                "hinweis": ("Kein aktiver Anzeigentext ist exakt 2000 "
                            "Zeichen lang — es sieht nichts nach der alten "
                            "Kappung aus."),
            }
        if nur_zaehlen:
            return {
                "status": "vorschau",
                "betroffen": len(betroffen),
                "von": len(aktive),
                "beispiele": [
                    {"hash": (j.get("hash") or "")[-8:],
                     "titel": (j.get("title") or "")[:60]}
                    for j in betroffen[:5]
                ],
                "hinweis": (f"{len(betroffen)} Stellen tragen einen "
                            "abgeschnittenen Text. Mit nur_zaehlen=False "
                            "werden bis zu max_stellen davon nachgeladen "
                            "(je ein HTTP-Aufruf)."),
            }

        geheilt, ohne_url, fehler = 0, 0, 0
        gewachsen = []
        with httpx.Client(follow_redirects=True, timeout=15,
                          headers={"User-Agent": "PBP/1.7 (+github.com/MadGapun/PBP)"}) as client:
            for job in betroffen[:max(1, int(max_stellen or 25))]:
                url = job.get("url") or ""
                if not url or job.get("is_search_url"):
                    ohne_url += 1
                    continue
                try:
                    from ..services import nachladen as _nachladen
                    text = _nachladen.beschreibung_holen(
                        url, client, timeout=15).text
                except Exception:
                    fehler += 1
                    continue
                alt_laenge = len(job.get("description") or "")
                if not text or len(text) <= alt_laenge:
                    continue
                db.update_job(job.get("hash"), {"description": text})
                geheilt += 1
                gewachsen.append({
                    "hash": (job.get("hash") or "")[-8:],
                    "vorher": alt_laenge, "nachher": len(text),
                })

        return {
            "status": "fertig",
            "geheilt": geheilt,
            "ohne_brauchbare_url": ohne_url,
            "fehler": fehler,
            "verbleibend": max(0, len(betroffen) - geheilt),
            "gewachsen": gewachsen[:10],
            "hinweis": (
                "Nachgeladene Stellen sollten neu bewertet werden — der "
                "Anforderungsteil war bisher nicht Teil des Scores: "
                "scores_neu_berechnen()."
                if geheilt else
                "Nichts geheilt. Moeglich: die Quelle kappt selbst, oder "
                "die Detailseite ist nicht mehr erreichbar."),
        }

    def _ist_gekappt(text) -> bool:
        from ..job_scraper.textgrenzen import ist_gekappt
        return ist_gekappt(text)

    @mcp.tool()
    def stellen_qualitaet_pruefen(
        max_stellen: int = 50,
        nur_problematische: bool = True,
        auto_aussortieren: bool = False,
        mit_ollama_validierung: bool = False,
    ) -> dict:
        """Prueft URL-Health + Beschreibungs-Vollstaendigkeit aktiver Stellen (#645).

        Geht pro aktiver Stelle durch:
        1. URL-Reachability (HTTP-Status + Bot-Block-Erkennung)
        2. Body-Marker "Stelle vergeben/expired"
        3. Workday-API-Cross-Check fuer Workday-SPAs
        4. Title-Token-Match Body vs. Titel (hat Server-Replacement geliefert?)
        5. Beschreibungs-Laenge (>= 50 Zeichen)

        Kategorisiert in:
            ok              — alles fein
            url_leer        — kein URL gespeichert (manuell/email-Quellen
                              ausser sie sollten eine URL haben)
            url_404         — Hard 404
            url_expired     — Marker oder Workday-API sagt: weg
            url_blocked     — Bot-Block (URL ok, aber Server blockt — kein
                              Aussortier-Grund)
            url_timeout     — kein Response (KEIN Aussortier-Grund, kann
                              transient sein)
            beschreibung_fehlt — URL ok, aber description leer/zu kurz
            search_url      — URL ist nur Such-URL (is_search_url=1)

        Args:
            max_stellen: Maximum aktiver Stellen pro Lauf (Schutz gegen
                lange Token-Runs).
            nur_problematische: Default True — nur Stellen mit Befund
                zurueckliefern, nicht die OK-Stellen einzeln auflisten.
            auto_aussortieren: Default False (Vorschau). Bei True werden
                Stellen mit url_404 oder url_expired sofort via
                dismiss_job(reason='veraltet_url') ausgemustert.
            mit_ollama_validierung: Default False. Bei True wird zusaetzlich
                Ollama (lokale AI) genutzt um pro Stelle die Beschreibungs-
                Vollstaendigkeit zu bewerten — liefert pro Stelle einen
                "ollama"-Block mit {vollstaendig, score, vorhanden, fehlt,
                begruendung, claude_action}. Nur sinnvoll wenn lokale AI
                aktiv ist; sonst kostet jeder Stelle einen Claude-Pending-
                Call. Empfohlene Reihenfolge: erst URL-Health, dann
                gezielt Ollama-Validierung.

        Liefert:
            {
                "geprueft": N,
                "befunde": {kategorie: count},
                "details": [...],  # immer alle Probleme, OK nur wenn !nur_problematische
                "aussortiert": M,  # nur wenn auto_aussortieren=True
                "ollama": {used, model, ...}  # nur wenn mit_ollama_validierung
            }
        """
        from ..services.url_health import (
            check_job_url_health, HealthStatus,
        )
        active = db.get_active_jobs()[:max_stellen]
        befunde: dict[str, int] = {}
        details: list[dict] = []
        aussortiert = 0

        # httpx-Client einmal teilen ueber alle Checks
        import httpx
        with httpx.Client(
            follow_redirects=True,
            timeout=15.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/131.0.0.0 Safari/537.36",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            },
        ) as client:
            for job in active:
                h = job.get("hash")
                pub_h = h.split(":", 1)[-1][:8] if h else "?"
                url = (job.get("url") or "").strip()
                title = job.get("title") or ""
                source = (job.get("source") or "").strip()
                desc = job.get("description") or ""
                is_search = bool(job.get("is_search_url"))

                kategorie: list[str] = []
                detail = {
                    "hash": pub_h,
                    "title": title[:80],
                    "company": (job.get("company") or "")[:60],
                    "source": source,
                    "url": url,
                }

                if is_search:
                    kategorie.append("search_url")

                if not url:
                    # Email/manuell ohne URL ist OK, andere Quellen sind ein
                    # Indiz auf #645-Regression — aber bereits durch save_jobs
                    # geguarded; hier nur fuer Reporting.
                    if source not in ("manuell", "email", "recruiter_inbound"):
                        kategorie.append("url_leer")
                    health = None
                else:
                    health = check_job_url_health(url, title, client=client)
                    if health.status == HealthStatus.HTTP_404:
                        kategorie.append("url_404")
                    elif health.status == HealthStatus.EXPIRED:
                        kategorie.append("url_expired")
                    elif health.status == HealthStatus.TIMEOUT:
                        kategorie.append("url_timeout")
                    elif health.status == HealthStatus.BLOCKED:
                        kategorie.append("url_blocked")
                    elif health.status == HealthStatus.HTTP_ERROR:
                        kategorie.append("url_http_error")
                    detail["health"] = health.to_dict()

                if not desc or len(desc) < 50:
                    kategorie.append("beschreibung_fehlt")
                # #952: bisher kannte die Pruefung nur die UNTERGRENZE.
                # Ein bei exakt 2000 Zeichen abgeschnittener Text galt als
                # tadellos, obwohl der Anforderungsteil fehlte — und ohne
                # diese Kategorie war die Tragweite nur per Direkt-SQL
                # messbar, was nach #514 unterbleiben soll.
                elif _ist_gekappt(desc):
                    kategorie.append("beschreibung_gekappt")
                    detail["beschreibung_zeichen"] = len(desc)

                # #965: eine unaufgeloeste Entfernung kostet nichts und
                # sieht deshalb aus wie Naehe. Sie gehoert in dieselbe
                # Qualitaetspruefung wie ein gekappter Text.
                from ..job_scraper import entfernungs_guete
                _eg, _egrund = entfernungs_guete(job)
                if _eg == "unbekannt" and (job.get("location") or "").strip():
                    kategorie.append("entfernung_unbekannt")
                    detail["ort_unaufloesbar"] = job.get("location")

                # Auto-aussortieren
                if auto_aussortieren and health and health.should_dismiss:
                    try:
                        db.dismiss_job(h, "veraltet_url")
                        aussortiert += 1
                        detail["aussortiert"] = True
                    except Exception as exc:
                        detail["aussortier_fehler"] = str(exc)[:200]

                # Optional: Ollama-Validierung der Beschreibung
                if mit_ollama_validierung:
                    try:
                        from ..services.llm_service import (
                            get_llm_service, TaskKind, Backend,
                        )
                        svc = get_llm_service(db)
                        r = svc.run(TaskKind.VALIDATE_JOB_QUALITY, {
                            "title": job.get("title") or "",
                            "company": job.get("company") or "",
                            "location": job.get("location") or "",
                            "description": desc,
                            "url": url,
                            "source": source,
                        })
                        if r.backend == Backend.LOCAL and r.success:
                            detail["ollama"] = r.payload
                            if r.payload.get("claude_action") == "nachladen":
                                if "ollama_action_nachladen" not in kategorie:
                                    kategorie.append("ollama_action_nachladen")
                            elif r.payload.get("claude_action") == "manuell_ergaenzen":
                                if "ollama_action_manuell" not in kategorie:
                                    kategorie.append("ollama_action_manuell")
                    except Exception as exc:
                        detail["ollama_fehler"] = str(exc)[:200]

                if not kategorie:
                    kategorie.append("ok")

                for k in kategorie:
                    befunde[k] = befunde.get(k, 0) + 1
                detail["kategorien"] = kategorie

                if (not nur_problematische) or kategorie != ["ok"]:
                    details.append(detail)

        result = {
            "geprueft": len(active),
            "befunde": befunde,
            "details": details,
        }
        # #952: Anteil am GESAMTEN Bestand nennen, nicht nur an der
        # geprueften Stichprobe — sonst bleibt die Tragweite unklar.
        try:
            _alle = db.get_active_jobs() or []
            _gekappt = sum(1 for j in _alle if _ist_gekappt(j.get("description")))
            if _gekappt:
                _quote = round(100.0 * _gekappt / max(1, len(_alle)), 1)
                result["beschreibung_gekappt_gesamt"] = {
                    "anzahl": _gekappt,
                    "von": len(_alle),
                    "anteil_prozent": _quote,
                    "hinweis": (
                        f"{_gekappt} von {len(_alle)} aktiven Stellen "
                        f"({_quote} %) tragen einen abgeschnittenen "
                        "Anzeigentext (Altbestand vor v1.7.23). Der "
                        "Anforderungsteil steht meist am Ende und fehlt "
                        "dort. Nachladen mit "
                        "beschreibungen_nachladen_bestand()."),
                }
        except Exception:
            pass

        # #966: Wie viele Aussortier-Urteile stehen auf duennem Grund?
        # Das ist der Altlast-Umfang UND zugleich die Kandidatenliste
        # fuer eine Neubewertung. Bewusst nur ein Bericht — alte Urteile
        # werden nicht stillschweigend geloescht.
        try:
            from ..services.wiedergaenger import (
                MINDESTLAENGE_BELASTBAR, grund_guete,
            )
            _verworfen = db.get_dismissed_jobs() or []
            _schwach = [j for j in _verworfen
                        if grund_guete(j)[0] == "schwach"]
            if _schwach:
                _q3 = round(100.0 * len(_schwach) / max(1, len(_verworfen)), 1)
                result["schwache_aussortier_urteile"] = {
                    "anzahl": len(_schwach),
                    "von": len(_verworfen),
                    "anteil_prozent": _q3,
                    "mindestlaenge": MINDESTLAENGE_BELASTBAR,
                    "beispiele": [
                        {"hash": (j.get("hash") or "")[-12:],
                         "titel": (j.get("title") or "")[:60],
                         "grund": grund_guete(j)[1]}
                        for j in _schwach[:5]
                    ],
                    "hinweis": (
                        f"{len(_schwach)} von {len(_verworfen)} "
                        f"Aussortierungen ({_q3} %) wurden an einer "
                        f"Anzeige unter {MINDESTLAENGE_BELASTBAR} Zeichen "
                        "oder auf Basis eines geschaetzten Gehalts "
                        "getroffen. Sie zaehlen im "
                        "Wiedergaenger-Mechanismus nur halb. Zum "
                        "Zurueckholen: stelle_reaktivieren(hash)."),
                }
        except Exception:
            pass

        # #965: Umfang der Luecke ueber den ganzen Bestand. Ohne diese
        # Zahl ist nicht zu erkennen, ob es ein Einzelfall ist oder ob
        # die Rangfolge der Trefferliste systematisch schieflaeuft.
        try:
            from ..job_scraper import entfernungs_guete
            _alle2 = db.get_active_jobs() or []
            _ohne = [j for j in _alle2
                     if (j.get("location") or "").strip()
                     and entfernungs_guete(j)[0] == "unbekannt"]
            if _ohne:
                _q2 = round(100.0 * len(_ohne) / max(1, len(_alle2)), 1)
                result["entfernung_unbekannt_gesamt"] = {
                    "anzahl": len(_ohne),
                    "von": len(_alle2),
                    "anteil_prozent": _q2,
                    "beispiel_orte": sorted({
                        (j.get("location") or "")[:60] for j in _ohne})[:5],
                    "hinweis": (
                        f"{len(_ohne)} von {len(_alle2)} aktiven Stellen "
                        f"({_q2} %) haben einen Ort, aber keine "
                        "aufgeloeste Entfernung. Ihr Entfernungs-Malus "
                        "entfaellt — sie stehen dadurch zu weit oben. "
                        "Ort pruefen mit stelle_bearbeiten(), danach "
                        "scores_neu_berechnen()."),
                }
        except Exception:
            pass
        if auto_aussortieren:
            result["aussortiert"] = aussortiert
        else:
            zum_aussortieren = sum(
                befunde.get(k, 0) for k in ("url_404", "url_expired")
            )
            if zum_aussortieren > 0:
                result["hinweis"] = (
                    f"{zum_aussortieren} Stellen mit veralteter URL gefunden. "
                    "Erneut mit auto_aussortieren=True aufrufen um sie als "
                    "'veraltet_url' zu dismissen."
                )
        return result

    @mcp.tool()
    def stelle_vergleichen(hash_a: str, hash_b: str) -> dict:
        """Vergleicht zwei Stellen strukturiert (#580).

        Liefert eine Gegenueberstellung von Skills (gemeinsam / nur A /
        nur B), Gehalt, Standort, Stellenart, Score und
        Beschreibungs-Laenge. Sehr hilfreich um zu erkennen ob zwei
        Stellen wirklich verschieden sind oder nur Schreibvarianten.
        """
        from ..services.typed_ids import strip_prefix
        ha = strip_prefix(hash_a)
        hb = strip_prefix(hash_b)
        ja = db.get_job(ha)
        jb = db.get_job(hb)
        if not ja or not jb:
            return {"fehler": "Mindestens eine der Stellen wurde nicht gefunden."}

        def _tokens(text):
            import re
            return set(re.findall(r"[a-zäöüß0-9]+", (text or "").lower())) - {
                "und", "der", "die", "das", "ein", "eine", "fuer", "im", "mit",
                "bei", "von", "zu", "in", "an", "the", "and", "for", "with",
            }

        title_a = _tokens(ja.get("title", ""))
        title_b = _tokens(jb.get("title", ""))
        desc_a = _tokens(ja.get("description", ""))
        desc_b = _tokens(jb.get("description", ""))

        common_title = title_a & title_b
        only_a_title = title_a - title_b
        only_b_title = title_b - title_a

        return {
            "stelle_a": {
                "hash": ja.get("hash"),
                "title": ja.get("title"),
                "company": ja.get("company"),
                "score": ja.get("score"),
                "source": ja.get("source"),
                "salary_min": ja.get("salary_min"),
                "salary_max": ja.get("salary_max"),
                "location": ja.get("location"),
                "remote_level": ja.get("remote_level"),
                "employment_type": ja.get("employment_type"),
                "is_active": bool(ja.get("is_active")),
                "description_length": len((ja.get("description") or "")),
            },
            "stelle_b": {
                "hash": jb.get("hash"),
                "title": jb.get("title"),
                "company": jb.get("company"),
                "score": jb.get("score"),
                "source": jb.get("source"),
                "salary_min": jb.get("salary_min"),
                "salary_max": jb.get("salary_max"),
                "location": jb.get("location"),
                "remote_level": jb.get("remote_level"),
                "employment_type": jb.get("employment_type"),
                "is_active": bool(jb.get("is_active")),
                "description_length": len((jb.get("description") or "")),
            },
            "vergleich": {
                "titel_gemeinsam": sorted(common_title),
                "titel_nur_a": sorted(only_a_title),
                "titel_nur_b": sorted(only_b_title),
                "beschreibung_overlap_pct": (
                    round(len(desc_a & desc_b) / max(len(desc_a | desc_b), 1) * 100, 1)
                    if (desc_a or desc_b) else 0
                ),
                "score_diff": (ja.get("score") or 0) - (jb.get("score") or 0),
                "gleiche_firma": (ja.get("company") or "").lower().strip() == (jb.get("company") or "").lower().strip(),
            },
        }

    @mcp.tool()
    def aehnliche_stellen_finden(stellen_hash: str, max_treffer: int = 5) -> dict:
        """Findet aehnliche Stellen zu einer gegebenen Stelle (#580).

        Algorithmus: Token-Overlap zwischen Title+Description. Bewerbungen
        und Stellen mit gleichem Hash werden ausgeschlossen. Liefert
        zusaetzlich den Outcome-Status (erfolgreich/abgelehnt/aussortiert)
        wenn vorhanden — als Lern-Signal.
        """
        from ..services.typed_ids import strip_prefix
        h = strip_prefix(stellen_hash)
        target = db.get_job(h)
        if not target:
            return {"fehler": "Stelle nicht gefunden."}

        import re
        def _tokens(text):
            return set(re.findall(r"[a-zäöüß0-9]+", (text or "").lower())) - {
                "und", "der", "die", "das", "ein", "eine", "fuer", "im", "mit",
                "bei", "von", "zu", "in", "an", "the", "and", "for", "with",
                "stelle", "position", "rolle", "team", "wir", "sie",
            }
        target_tokens = _tokens(target.get("title", "") + " " + (target.get("description") or "")[:1500])
        if not target_tokens:
            return {"hinweis": "Stelle hat zu wenig Text fuer Aehnlichkeits-Berechnung."}

        # Alle anderen Stellen durchgehen
        all_jobs = db.get_active_jobs() + db.get_dismissed_jobs()
        scored = []
        for j in all_jobs:
            if j.get("hash") == target.get("hash"):
                continue
            jt = _tokens(j.get("title", "") + " " + (j.get("description") or "")[:1500])
            if not jt:
                continue
            inter = target_tokens & jt
            union = target_tokens | jt
            jaccard = len(inter) / len(union) if union else 0
            if jaccard < 0.05:
                continue
            scored.append((jaccard, j))

        # Top N
        scored.sort(key=lambda x: -x[0])
        top = scored[:max_treffer]

        # Bewerbungen pruefen — gibt's zu der Stelle eine?
        results = []
        for sim, j in top:
            apps = db.get_applications_for_job(j.get("hash"))
            outcome = None
            if apps:
                statuses = [a.get("status") for a in apps]
                if any(s in ("interview", "zweitgespraech",
                            "interview_abgeschlossen", "angebot",
                            "angenommen") for s in statuses):
                    outcome = "interview_erreicht"
                elif "abgelehnt" in statuses:
                    outcome = "abgelehnt"
                else:
                    outcome = f"status:{statuses[0]}" if statuses else None
            elif not j.get("is_active"):
                outcome = f"aussortiert:{j.get('dismiss_reason') or 'unbekannt'}"
            results.append({
                "hash": j.get("hash"),
                "title": j.get("title"),
                "company": j.get("company"),
                "similarity": round(sim, 2),
                "outcome": outcome,
            })

        return {
            "vergleichsstelle": {
                "hash": target.get("hash"),
                "title": target.get("title"),
                "company": target.get("company"),
            },
            "anzahl": len(results),
            "aehnliche": results,
        }

    @mcp.tool()
    def stelle_mergen(
        master_hash: str,
        duplikat_hash: str,
        feld_strategie: dict | None = None,
        dry_run: bool = True,
    ) -> dict:
        """Fuehrt zwei doppelt angelegte Stellen zusammen (#470).

        Typischer Flow:
        1. Erst ``dry_run=True`` (Default) aufrufen -> Vorschau mit Feld-
           Entscheidungen, Konflikten und welche Bewerbungen umgehaengt werden.
        2. Output pruefen, bei Konflikten ggf. ``feld_strategie`` mitgeben.
        3. Mit ``dry_run=False`` finalisieren.

        Args:
            master_hash: Stelle, die erhalten bleibt.
            duplikat_hash: Stelle, die aufgeloest (geloescht) wird.
            feld_strategie: Optional dict pro Feld: 'master' | 'duplikat' |
                'merge' (letzteres nur fuer 'description' sinnvoll).
                Felder die nur im Duplikat gefuellt sind, werden IMMER automatisch
                uebernommen; Felder die nur im Master gefuellt sind, bleiben.
            dry_run: Default True. Bei True wird nichts geschrieben.

        Returns:
            dict mit 'status' ('vorschau'/'ok'), 'feld_entscheidungen',
            'konflikte' (Liste Felder mit abweichenden Werten),
            'umgehaengte_bewerbungen'.
        """
        if not master_hash or not duplikat_hash:
            return {"fehler": "master_hash und duplikat_hash sind Pflicht"}
        result = db.merge_jobs(
            master_hash=master_hash,
            duplicate_hash=duplikat_hash,
            field_strategy=feld_strategie,
            dry_run=dry_run,
        )
        if dry_run and "fehler" not in result:
            result["hinweis"] = (
                "Vorschau. Mit dry_run=False ausfuehren. "
                "Bei Konflikten feld_strategie mitgeben "
                "(z.B. {'description': 'merge', 'url': 'duplikat'})."
            )
        return result

    @mcp.tool()
    def fit_analyse(job_hash: str, score_uebernehmen: bool = False) -> dict:
        """Detaillierte Passungsanalyse für eine bestimmte Stelle.

        Zeigt welche Keywords matchen, was fehlt, und gibt eine Risikobewertung.

        Reines LESEWERKZEUG (seit v1.7.24, #963): der Aufruf veraendert
        die Stelle nicht mehr. Bis v1.7.23 schrieb er den errechneten
        Wert still in `jobs.score` — wer sich eine Stelle nur genauer
        ansah, verschob damit ihre Position in der Trefferliste.

        Args:
            job_hash: Hash der Stelle (von stellen_anzeigen)
            score_uebernehmen: True = den errechneten Wert ausdruecklich
                als neuen Score speichern. Standard False.
        """
        gate = ki_gate(db, "stellenanalyse")
        if gate is not None:
            return gate
        from ..job_scraper import fit_analyse as _fit_analyse
        job_dict = db.get_job(job_hash)
        if not job_dict:
            return {"fehler": "Stelle nicht gefunden. Prüfe den Hash mit stellen_anzeigen()."}
        # v1.7.36 (#987): dieselbe Basis wie Suchlauf und Neuberechnung.
        # Die Profil-Anreicherung darunter kommt OBENDRAUF — sie ist
        # fit-spezifisch, die Basis ist es nicht.
        from ..services import scoring_kriterien
        criteria = scoring_kriterien.fuer_scoring(db)
        # Enrich criteria with profile skills and salary preferences for better fit analysis
        profile = db.get_profile()
        if profile:
            skills = profile.get("skills", [])
            criteria["_profile_skills"] = [s.get("name", "").lower() for s in skills if s.get("name")]
            # #305: Education für Hochschulabschluss-Erkennung
            criteria["_profile_education"] = profile.get("education", [])
            prefs = profile.get("preferences", {})
            if prefs.get("min_gehalt"):
                criteria["min_gehalt"] = prefs["min_gehalt"]
            if prefs.get("min_tagessatz"):
                criteria["min_tagessatz"] = prefs["min_tagessatz"]
        # v1.7.62 (#1008 Befund 3): der Hochschulabschluss-Malus ist
        # entfallen. Er wurde hier in die Kriterien geschrieben und von
        # KEINEM Rechenweg gelesen — die Pruefung dahinter ist seit
        # v1.7.35 (#972) entfernt. Ein Wert ohne Leser ist keine
        # Einstellung (#993, #1000).
        result = _fit_analyse(job_dict, criteria)

        # v1.7.62 (#1008 Befund 2): die Liste zeigt den Wert MIT den
        # gesetzten Scoring-Reglern, die Fit-Analyse rechnet den
        # Fachwert. Das sind zwei verschiedene Groessen, und bisher
        # hiessen beide "Score" — der Melder sah dieselbe Stelle mit
        # vier Zahlen. Beide anzugleichen ginge NICHT: `total_score`
        # wird gegen `total_score_max` gehalten, und in diesem
        # Hoechstwert kommen die Regler nicht vor. Eine Stelle, die
        # alles trifft, muss weiterhin exakt 100 % ergeben (#999).
        # Also werden sie BENANNT statt gleichgemacht — eine Luecke
        # gehoert erklaert, nicht zugerechnet (#989).
        try:
            from ..services.scoring_service import apply_scoring_adjustments
            _regler = apply_scoring_adjustments(
                job_dict, result.get("total_score", 0), db)
            _in_liste = _regler.get("final_score", result.get("total_score", 0))
            if abs(_in_liste - result.get("total_score", 0)) > 0.05:
                result["score_in_liste"] = _in_liste
                result["score_hinweis"] = (
                    f"In der Stellenliste steht {_in_liste} — das ist dieser "
                    f"Fachwert ({result.get('total_score')}) plus deine "
                    "gesetzten Scoring-Regler. Verglichen wird gegen den "
                    "Hoechstwert der Fachwert, weil die Regler dort nicht "
                    "vorkommen.")
        except Exception as e:
            logger.debug("Regler-Abgleich (#1008): %s", e)


        # v1.6.5 (#539, Folge von #535): Fit-Score zurueck in jobs.score
        # persistieren. Vorher rechnete fit_analyse on-demand mit Profile-
        # Daten + Risk-Faktoren (z.B. -2 fuer Hochschulabschluss), aber
        # jobs.score blieb auf dem reinen Scrape-Wert haengen — Listen
        # zeigten alten Wert, fit_analyse einen anderen.
        # Der Fit-Score ist „mehr wert" weil er Profile + Risiken
        # beruecksichtigt; daher ueberschreibt er den Scrape-Score.
        # v1.7.24 (#963): AK 2 und AK 3. Die alte Fassung (#539) hat die
        # Divergenz zweier Rechenwege dadurch "geloest", dass der zuletzt
        # laufende gewinnt. Damit war der Score in stellen_anzeigen nicht
        # reproduzierbar, und ein Lesewerkzeug hatte eine Nebenwirkung.
        #
        # Jetzt: die Abweichung wird BENANNT statt still ueberschrieben.
        # Seit beide Wege dasselbe Tor und denselben Deckel kennen,
        # sollte sie ohnehin nur noch bei veraltetem Bestand auftreten —
        # und dann ist sie ein Befund, keine Nebensache.
        new_score = result.get("total_score")
        if new_score is not None and isinstance(new_score, (int, float)):
            old_score = job_dict.get("score")
            if old_score != new_score:
                # v1.7.36 (#987): der alte Hinweis nannte nur EINE
                # Erklaerung ("der Wert ist aelter als die Kriterien") und
                # hat damit den echten Fehler verdeckt: die Stelle war am
                # SELBEN TAG angelegt worden, die Kriterien lagen
                # unveraendert, und trotzdem stand 105 gegen 0. Ein
                # Hinweis, der die Ursache ausschliesst, ist schlimmer als
                # keiner. Jetzt wird der Fall benannt statt weggeredet.
                from datetime import date as _date
                _gefunden = str(job_dict.get("found_at") or "")[:10]
                _frisch = bool(_gefunden) and _gefunden == _date.today().isoformat()
                _hinweis = (
                    f"Der gespeicherte Score ({old_score}) weicht vom "
                    f"jetzt berechneten ({round(new_score, 1)}) ab. ")
                if _frisch:
                    _hinweis += (
                        "Die Stelle wurde HEUTE angelegt — der gespeicherte "
                        "Wert kann also nicht veraltet sein. Dann ist die "
                        "Abweichung ein Befund und kein Alterungseffekt: "
                        "bitte melden (pbp_grenze_melden oder ein Issue).")
                else:
                    _hinweis += (
                        "Meist ist der gespeicherte Wert aelter als die "
                        "aktuellen Suchkriterien. Wurde seither nichts "
                        "geaendert, ist die Abweichung ein Befund.")
                result["score_abweichung"] = {
                    "gespeichert": old_score,
                    "neu_berechnet": round(new_score, 1),
                    "am_selben_tag_angelegt": _frisch,
                    "hinweis": _hinweis,
                    "naechster_schritt": (
                        "scores_neu_berechnen() zieht den ganzen Bestand "
                        "nach; fit_analyse(job_hash, score_uebernehmen=True) "
                        "nur diese eine Stelle."),
                }
                if score_uebernehmen:
                    try:
                        db.update_job(job_hash, {"score": int(new_score)})
                        result["score_aktualisiert"] = {
                            "alter_score": old_score,
                            "neuer_score": int(new_score),
                        }
                    except Exception as exc:
                        logger.warning(
                            "Score-Persistierung nach fit_analyse "
                            "fehlgeschlagen: %s", exc)
                        result["score_aktualisiert"] = {"fehler": str(exc)[:200]}

        # #948 (G42): die Sichtung hinterlaesst eine Spur. Bis hierher
        # war der teuerste Arbeitsschritt der fluechtigste — wer eine
        # Stelle vertieft ansah und kein Urteil zurueckschrieb, fand sie
        # beim naechsten Sichten wieder als ungeprueft vor.
        #
        # Der Vermerk fasst weder Score noch Urteil an: `fit_analyse`
        # ist seit #963 ein reines Lesewerkzeug, weil ein stiller
        # Score-Write die Rangfolge verschob. Geschrieben werden genau
        # zwei Felder, die in keine Sortierung eingehen — und der
        # Zustand heisst `gesichtet`, nicht `beurteilt` (#989).
        try:
            db.mark_job_sighted(job_hash)
        except Exception as exc:  # pragma: no cover — nie die Analyse kippen
            logger.debug("Sichtungs-Vermerk (#948) fehlgeschlagen: %s", exc)

        # Include job description in result (#55) so Claude can use it for analysis
        if job_dict.get("description"):
            from ..job_scraper.textgrenzen import (fuer_ausgabe,
                                                   kappungs_hinweis)
            result["stellenbeschreibung"] = fuer_ausgabe(job_dict["description"])
            _kappung = kappungs_hinweis(job_dict["description"])
            if _kappung:
                result["beschreibung_unvollstaendig"] = True
                result["beschreibung_hinweis"] = _kappung
        result["url"] = job_dict.get("url", "")
        # #436: Warne wenn URL nur auf Suchergebnis-Seite zeigt
        if job_dict.get("is_search_url"):
            result["url_warnung"] = (
                "URL zeigt auf eine Suchergebnis-Seite, nicht auf die konkrete "
                "Stellenanzeige. Die Stelle muss manuell auf dem Portal gesucht werden."
            )
        elif result["url"]:
            from ..job_scraper import is_search_result_url
            if is_search_result_url(result["url"]):
                result["url_warnung"] = (
                    "URL zeigt auf eine Suchergebnis-Seite. "
                    "Stelle manuell auf dem Portal suchen."
                )
        # v1.7.26 (#949 Befund 2): Laufzeit und Einordnung. Bewusst ein
        # HINWEIS, kein Score-Malus — eine lang laufende Anzeige kann
        # eine schwer besetzbare Spezialistenrolle sein, und die
        # Leitlinie lautet Recall vor Praezision.
        _alter = _anzeigenalter.einordnung(job_dict)
        result["anzeigenalter"] = _alter
        if job_dict.get("veroeffentlicht_am"):
            result["veroeffentlicht_am"] = job_dict["veroeffentlicht_am"]

        # #648 (C17, beta.75): Outcome-Pattern-Signal aus aehnlichen Stellen.
        # Wenn drei oder mehr aehnliche Stellen aus dem gleichen Grund
        # aussortiert wurden, ist das ein starkes Lern-Signal — Risk-
        # Eintrag mit Top-Grund und Beispiel-Refs.
        try:
            outcome_warning = _aehnliche_outcome_pattern(
                db, job_dict, schwellwert=3, max_check=15,
            )
            if outcome_warning:
                if "risks" not in result or not isinstance(result["risks"], list):
                    result["risks"] = []
                result["risks"].append(outcome_warning["risk_text"])
                result["outcome_pattern"] = outcome_warning
        except Exception as exc:
            logger.warning("Outcome-Pattern-Check fuer %s fehlgeschlagen: %s",
                           job_hash, exc)

        # v1.7.0-beta.86 (#671 Ebene 2): Wiedergaenger-Kontext. Firma-
        # verankert (im Gegensatz zum token-Jaccard outcome_pattern oben,
        # das ueber alle Firmen geht). Liefert "Firma X + Domaene Y schon
        # N-mal als Z verworfen" — als starkes Signal in die Empfehlung.
        # KI-frei (Ebene 0 traegt das), greift auch ohne Ollama.
        try:
            from ..services.wiedergaenger import (
                find_wiedergaenger_pattern, firmen_historie)
            wg = find_wiedergaenger_pattern(
                db,
                job_dict.get("company", ""),
                job_dict.get("title", ""),
                schwellwert=2,
                target_hash=job_dict.get("hash"),
            )
            if wg:
                if "risks" not in result or not isinstance(result["risks"], list):
                    result["risks"] = []
                result["risks"].append(
                    f"WIEDERGAENGER: {wg['hinweis']} "
                    "Wahrscheinlich erneut nicht passend."
                )
                result["wiedergaenger"] = wg
            else:
                # v1.7.7 (#754/#757): Kein Wiedergaenger (andere Rolle oder
                # Domaene) — die Firmen-Historie kommt trotzdem als NEUTRALE
                # Einordnung mit. Bewusst kein risks-Eintrag und kein
                # k.o.-Einfluss: Aussortier-Gruende gelten je Stelle.
                fh = firmen_historie(
                    db, job_dict.get("company", ""),
                    target_hash=job_dict.get("hash"),
                )
                if fh:
                    result["firmen_historie"] = fh
        except Exception as exc:
            logger.warning("Wiedergaenger-Check fuer %s fehlgeschlagen: %s",
                           job_hash, exc)

        # v1.7.0-beta.81 (#662): Klare 3-Stufen-Empfehlung im Result.
        # Soll Claude davon abhalten, in Weichspueler-Sprache zu verfallen
        # ("Trefferchance nicht hoch, aber realistisch vorhanden") — statt-
        # dessen liefert die Heuristik eine eindeutige Aussage, die Claude
        # direkt zitieren kann.
        # v1.7.10 (#782/C30): Repost-Warnung prominent in der Fit-Analyse —
        # bevor Unterlagen erstellt werden, muss klar sein, dass es diese
        # Stelle als Bewerbung schon einmal gab.
        try:
            from ..duplicate_detection import find_repost_of_application
            _repost = find_repost_of_application(
                job_dict, db.get_applications())
            if _repost:
                result["repost_warnung"] = _repost["warnung"]
                result["repost_details"] = {
                    k: v for k, v in _repost.items() if k != "warnung"}
        except Exception as _e:
            logger.debug("Repost-Check in fit_analyse: %s", _e)

        # #1003/#1007: der Verdict kommt aus dem gespeicherten Befund der
        # Detailanalyse — nicht aus dem Suchbegriff-Score. Liegt keiner
        # vor, sagt PBP das, statt zu raten.
        _gespeichert = passung.analyse_lesen(job_dict, profile)
        _kompetenzen = len((profile or {}).get("skills") or [])
        result["empfehlung"] = _build_empfehlung(
            result, job_dict,
            gespeicherte_analyse=_gespeichert,
            profil_kompetenzen=_kompetenzen)
        if _gespeichert:
            result["gespeicherte_analyse"] = _gespeichert

        return result

    @mcp.tool()
    def stelle_bearbeiten(
        job_hash: str,
        titel: str = "",
        firma: str = "",
        ort: str = "",
        beschreibung: str = "",
        url: str = "",
    ) -> dict:
        """Aktualisiert Felder einer bestehenden Stelle (#446, #645).

        Nutze dies, um eine gescrapte oder manuell angelegte Stelle
        nachtraeglich zu korrigieren oder zu verfeinern — z.B. wenn aus einer
        E-Mail eine ausfuehrlichere Beschreibung hervorgeht oder die
        Ortsangabe prezisiert werden muss.

        Nur angegebene Felder werden geaendert. Leere Strings bleiben unveraendert.

        v1.7.0-beta.71 (#645): `url` ist jetzt setzbar. Bei URL-Update wird
        `is_search_url` automatisch aus der URL bestimmt (Detail- vs.
        Such-URL), damit stellenbeschreibung_nachladen die Stelle wieder
        nachladen kann.

        Args:
            job_hash: Hash der Stelle (aus stellen_anzeigen)
            titel: Neuer Stellentitel
            firma: Neuer Firmenname
            ort: Neuer Arbeitsort
            beschreibung: Neue Stellenbeschreibung.
                NOTIZEN-KONVENTION (#603/#917): eigene Anmerkungen,
                Recherche-Ergebnisse oder Bewerberstatistiken gehoeren
                HINTER eine Zeile mit '---' (erst Original-Anzeigentext,
                dann '---', dann Notizen). Alles vor der Trennzeile
                zaehlt ins Scoring — ein Ausschluss-Keyword in einer
                Notiz setzt den Score sonst hart auf 0 (belegter Fall:
                eine LinkedIn-Bewerberstatistik mit '20 % Berufseinsteiger'
                nullte eine passende Stelle).
            url: Neue Stellen-URL. Wird auch genutzt um nach #645 leere
                URL-Felder bei XING/Stepstone/Email-Stellen nachzupflegen.
        """
        # v1.7.0-beta.46 (#618): Kurze IDs (8 Zeichen) wurden vorher
        # nicht akzeptiert — andere Tools (fit_analyse, scoring_vorschau)
        # tun das aber. Konsistenz: resolve_job_hash erlaubt beides.
        from ..services.typed_ids import strip_prefix
        h = strip_prefix(job_hash)
        resolved = db.resolve_job_hash(h)
        if not resolved:
            return {"fehler": "Stelle nicht gefunden. Pruefe den Hash mit stellen_anzeigen()."}
        job = db.get_job(resolved)
        if not job:
            return {"fehler": "Stelle nicht gefunden. Pruefe den Hash mit stellen_anzeigen()."}
        # Ab hier den vollen aufgeloesten Hash verwenden
        job_hash = resolved

        updates: dict = {}
        if titel:
            updates["title"] = titel
        if firma:
            updates["company"] = firma
        if ort:
            updates["location"] = ort
        if beschreibung:
            updates["description"] = beschreibung
        if url:
            from ..job_scraper import is_search_result_url
            updates["url"] = url
            updates["is_search_url"] = is_search_result_url(url)

        if not updates:
            return {"fehler": "Keine Aenderungen angegeben."}

        db.update_job(job_hash, updates)

        # #535 v1.6.4: Score nach Beschreibungs-/Titel-Update neu berechnen.
        # Vorher blieb der persistente score-Wert in jobs.score auf dem Stand
        # der initialen Scrape-Beschreibung — fit_analyse rechnete live mit
        # der neuen Beschreibung, stellen_anzeigen mit dem alten score.
        # Drei verschiedene Werte fuer dieselbe Stelle waren die Folge.
        score_recomputed = None
        if "description" in updates or "title" in updates:
            try:
                from ..job_scraper import calculate_score
                criteria = db.get_search_criteria()
                fresh_job = db.get_job(job_hash) or {}
                new_score = calculate_score(fresh_job, criteria)
                if new_score is not None:
                    db.update_job(job_hash, {"score": new_score})
                    score_recomputed = {
                        "alter_score": job.get("score"),
                        "neuer_score": new_score,
                    }
                    # #762: Faellt der Score auf 0, den GRUND nennen. Sonst
                    # wirkt das Nachpflegen eines echten Volltexts wie ein
                    # Bug ("Score war 45, jetzt 0") — der haeufigste Fall ist
                    # ein Ausschluss-Keyword, das erst im laengeren Text steht.
                    if new_score == 0:
                        _ko_kw = fresh_job.get("_ko_ausschluss")
                        if _ko_kw:
                            score_recomputed["grund"] = (
                                f"Ausschluss-Keyword '{_ko_kw}' kommt im neuen Text "
                                "vor — das setzt den Score hart auf 0. Wenn das ein "
                                "Fehltreffer ist, das Keyword in den Suchkriterien "
                                "schaerfen (suchkriterien_anzeigen)."
                            )
                        elif fresh_job.get("_ko_kein_muss"):
                            score_recomputed["grund"] = (
                                "Kein MUSS-Keyword im neuen Text gefunden — das setzt "
                                "den Score auf 0. Pruefe die MUSS-Keywords "
                                "(suchkriterien_anzeigen) oder ob der Text vollstaendig ist."
                            )
            except Exception as exc:
                logger.warning("Score-Recompute fuer %s fehlgeschlagen: %s", job_hash, exc)

        result = {
            "status": "aktualisiert",
            "job_hash": job_hash,
            "geaenderte_felder": list(updates.keys()),
            "nachricht": (
                f"Stelle '{updates.get('title') or job.get('title', '')}' "
                f"bei {updates.get('company') or job.get('company', '')} aktualisiert."
            ),
        }
        if score_recomputed:
            result["score_neu_berechnet"] = score_recomputed
        # #645: Wenn die neue URL eine Such-URL ist, das wie bei
        # stelle_manuell_anlegen transparent zurueckmelden — sonst denkt
        # der User der Link sei voll funktionsfaehig.
        if "url" in updates and updates.get("is_search_url"):
            result["url_warnung"] = (
                "Die uebergebene URL zeigt auf eine Suchergebnis-Seite, nicht auf die "
                "konkrete Stellenanzeige. Sie wurde trotzdem gespeichert. "
                "stellenbeschreibung_nachladen wird damit voraussichtlich nichts "
                "Brauchbares zurueckliefern — fuer das Nachladen die Detail-URL nachreichen."
            )
        # v1.7.17 (#917): Notizen ohne '---'-Trenner erkennen und warnen
        # — die #603-Konvention war unsichtbar, redaktionelle Texte
        # sabotierten das Scoring.
        if beschreibung:
            _notiz_warnung = _editorial_ohne_trenner(beschreibung)
            if _notiz_warnung:
                result["notizen_warnung"] = _notiz_warnung
        return result

    @mcp.tool()
    def stellen_auto_aussortieren(
        max_stellen: int = 10,
        min_score: int = 0,
        dry_run: bool = False,
        max_dauer_sek: int = 50,
    ) -> dict:
        """Profil-basiertes Auto-Aussortieren via lokaler AI (#586, #646).

        Statt Filter-Listen zu pflegen entscheidet die lokale AI pro Stelle,
        ob sie zum Profil passt. Skaliert mit beliebigen Berufsfeldern —
        funktioniert fuer Senior-PLM genauso wie fuer Studenten oder
        Service-Berufe.

        Pro Stelle (max_stellen, sortiert nach Score absteigend):
        - LLM-Anfrage `match_job_to_skills` mit Profil-Kontext + Stelle
        - PASST_NICHT → dismiss_job mit Grund 'profil_match_negativ' und
          LLM-Begruendung in research_notes
        - UNSICHER → unangetastet (User entscheidet manuell)
        - PASST → unangetastet

        Voraussetzung: Lokale AI aktiv (Ollama laeuft, Modell installiert).
        Fallback: ohne Lokale AI gibt es eine ehrliche Meldung — keine
        Heuristik-Raterei.

        v1.7.0-beta.74 (#646): Hard-Cap auf max_stellen=10 (vorher 50) +
        Wall-Clock-Budget max_dauer_sek=50s (#691, bewusst unter dem ~60s-
        MCP-Client-Timeout). Bei Erreichen des Budgets wird mit
        `status='teilweise'` und allen bis dahin verarbeiteten Stellen
        zurueckgegeben — kein stilles Timeout, kein Schema-Validierungsfehler.
        Idempotent fortsetzbar: ein erneuter Aufruf bearbeitet die nicht
        verarbeiteten Reste.

        Args:
            max_stellen: Maximum Stellen pro Lauf (Default 10, war 50 vor
                         beta.74). Schutz gegen MCP-Timeout. Bei mehr
                         Stellen mehrere Laeufe machen.
            min_score: Mindest-Score-Schwelle. Stellen darunter werden gar
                       nicht erst der LLM vorgelegt (Default 0 = alle).
            dry_run: Wenn True, nur Vorschau ohne dismiss-Aktionen.
            max_dauer_sek: Wall-Clock-Budget in Sekunden (Default 50, cap 90;
                bewusst unter dem ~60s-MCP-Client-Timeout, #691). Bei
                Erreichen wird mit schemakonformem Teil-Ergebnis abgebrochen.

        Idempotent: bewertet keine Stelle erneut die schon `passt_nicht`
        oder eine Bewerbung hat.
        """
        import time as _time
        run_started_at = _time.monotonic()
        # Defensive Caps (#646, #691): Der MCP-Client (Claude Desktop) bricht
        # einen Tool-Call schon nach ~60s ab. Ein laengerer Lauf wird dann
        # gecancelt und FastMCP 3.x liefert "outputSchema defined but no
        # structured output returned" statt eines sauberen Teil-Ergebnisses.
        # Darum Budget-Default 50s (cap 90s); der Wall-Clock-Check unten gibt
        # VOR dem Client-Timeout ein schemakonformes status='teilweise' zurueck.
        max_stellen = max(1, min(int(max_stellen or 10), 30))
        max_dauer_sek = max(20, min(int(max_dauer_sek or 50), 90))
        # v1.7.0-beta.46 (#610): Try/except um den ganzen Body, alle
        # Returns mit uniformem Schema. Vorher: outputSchema-Validierungs-
        # fehler weil error-Pfade andere Keys hatten als Success-Pfade.
        def _err(msg: str, **extra) -> dict:
            base = {
                "status": "fehler",
                "fehler": msg,
                "geprueft": 0, "passt_nicht": 0, "unsicher": 0, "passt": 0,
                "errors_count": 0,
                "passt_nicht_details": [], "unsicher_details": [],
                "passt_details": [], "errors": [],
                "modell": "",
            }
            base.update(extra)
            return base

        try:
            from ..services.llm_service import get_llm_service, TaskKind, Backend

            svc = get_llm_service(db)
            status = svc.get_status(force_refresh=True)
            if not status.ollama_available or not status.available_models:
                return _err(
                    "Lokale AI nicht verfuegbar.",
                    hinweis="Stellen_auto_aussortieren braucht Ollama + ein installiertes Modell. Pruefe Einstellungen -> Lokale KI.",
                )
            if status.user_state != "active":
                return _err(
                    f"Lokale AI ist im State '{status.user_state}'.",
                    hinweis="Setze State auf 'active' in Einstellungen -> Lokale KI.",
                )
            # v1.7.0-beta.62 (#638): Pre-Warmup damit der erste Modell-Call
            # nicht 50-60s Cold-Load + MCP-Timeout ausloest. Warmup ist
            # idempotent — bei warmem Modell Millisekunden, bei kaltem max 90s.
            try:
                warmup_result = svc.warmup()
                if warmup_result.get("status") == "warm":
                    logger.info(
                        "Ollama-Warmup vor stellen_auto_aussortieren: %.2fs",
                        warmup_result.get("duration_sec", 0),
                    )
            except Exception as warmup_exc:
                # Warmup-Fehler nicht fatal — falls Bulk-Call durchgeht, ok
                logger.warning("Warmup-Fehler (ignoriert): %s", warmup_exc)
        except Exception as exc:
            return _err(f"unerwarteter_fehler: {str(exc)[:200]}")

        # Profil-Kontext sammeln
        try:
            profile = db.get_profile() or {}
        except Exception as exc:  # #691: schemakonformer Fehler statt Crash
            return _err(f"profil_lesen_fehlgeschlagen: {str(exc)[:150]}")
        profile_skills = [
            s.get("name", "") for s in (profile.get("skills") or [])[:15]
        ]
        positions = profile.get("positions") or []
        latest_pos = positions[0] if positions else {}
        profile_position = latest_pos.get("title", "")
        # Heuristik: Karriere-Stufe aus aktueller Position + Jahren ableiten
        years = 0
        for p in positions:
            try:
                start = int((p.get("start_date") or "0000")[:4])
                end_raw = (p.get("end_date") or "")[:4]
                end = int(end_raw) if end_raw.isdigit() else 2026
                if start > 1900:
                    years += max(0, end - start)
            except Exception:
                pass
        if years >= 10:
            profile_seniority = f"Senior ({years} Jahre Erfahrung)"
        elif years >= 5:
            profile_seniority = f"Mid-Level ({years} Jahre Erfahrung)"
        elif years >= 1:
            profile_seniority = f"Junior ({years} Jahre Erfahrung)"
        else:
            profile_seniority = "Berufseinsteiger / Berufsanfaenger"

        # Kandidaten holen — aktive, noch nicht bewertete Stellen
        try:
            all_active = db.get_active_jobs()
        except Exception as exc:  # #691: schemakonformer Fehler statt Crash
            return _err(f"stellen_lesen_fehlgeschlagen: {str(exc)[:150]}")
        # Filter: keine Bewerbung, kein dismiss-Reason
        candidates = [
            j for j in all_active
            if not j.get("dismiss_reason")
            and (j.get("score") or 0) >= min_score
        ]
        # v1.7.7 (#756): Beschreibung-zuerst — ohne Stellentext gibt es kein
        # fachliches Urteil. Die lokale KI wuerde sonst auf Titel+Firma raten
        # (Praxis-Fund 13.07.: passende Stellen flogen mangels Beschreibung
        # raus). Schwelle 50 Zeichen, konsistent mit fit_analyse (#180).
        ohne_beschreibung = [
            j for j in candidates
            if len((j.get("description") or "").strip()) < 50
        ]
        candidates = [
            j for j in candidates
            if len((j.get("description") or "").strip()) >= 50
        ]
        candidates.sort(key=lambda j: -(j.get("score") or 0))
        candidates = candidates[:max_stellen]
        uebersprungen_details = [
            {
                "hash": j["hash"], "title": j.get("title"),
                "company": j.get("company"), "score": j.get("score"),
            }
            for j in ohne_beschreibung[:10]
        ]

        # v1.7.0-beta.28 (#594 Stufe 3): adaptive Prompt-Anreicherung —
        # Top-3 dismiss_reasons des Users bekommt die LLM mit, damit sie
        # bekannte Anti-Muster wiedererkennen kann.
        dismiss_reasons_top: list[dict] = []
        try:
            conn = db.connect()
            pid = db.get_active_profile_id()
            rows = conn.execute(
                "SELECT dismiss_reason, COUNT(*) AS n FROM jobs "
                "WHERE dismiss_reason IS NOT NULL AND dismiss_reason != '' "
                "AND is_active=0 AND (profile_id=? OR profile_id IS NULL) "
                "GROUP BY dismiss_reason ORDER BY n DESC LIMIT 3",
                (pid,)
            ).fetchall()
            dismiss_reasons_top = [
                {"reason": r["dismiss_reason"], "count": r["n"]}
                for r in rows
            ]
        except Exception:
            pass

        # v1.7.0-beta.63 (#638 Stufe 3): konkrete Few-Shot-Beispiele
        try:
            recent_dismissals_fewshot = db.get_recent_user_dismissals(limit=10)
        except Exception:
            recent_dismissals_fewshot = []

        if not candidates:
            if ohne_beschreibung:
                return _err(
                    "Keine bewertbaren Stellen — alle Kandidaten haben "
                    "keine Stellenbeschreibung.",
                    status="leer",
                    uebersprungen_ohne_beschreibung=len(ohne_beschreibung),
                    uebersprungen_details=uebersprungen_details,
                    hinweis=(
                        "Ohne Beschreibung kein fachliches Urteil (#756). "
                        "Erst stellenbeschreibung_nachladen(hash) fuer die "
                        "uebersprungenen Stellen, dann erneut aufrufen."
                    ),
                )
            return _err(
                "Keine ungerateten Stellen oberhalb min_score.",
                status="leer",
            )

        passt_nicht_results = []
        unsicher_results = []
        passt_results = []
        errors = []
        budget_erschoepft = False  # #646
        unverarbeitet = 0  # #646

        for idx, job in enumerate(candidates):
            # #646: Wall-Clock-Budget-Check vor jedem Ollama-Call.
            # Verhindert das stille 4-Min-Timeout.
            elapsed = _time.monotonic() - run_started_at
            if elapsed >= max_dauer_sek:
                budget_erschoepft = True
                unverarbeitet = len(candidates) - idx
                logger.info(
                    "stellen_auto_aussortieren: Budget %ds erschoepft nach %d/%d Stellen",
                    max_dauer_sek, idx, len(candidates),
                )
                break
            try:
                payload = {
                    "profile_skills": profile_skills,
                    "profile_position": profile_position,
                    "profile_seniority": profile_seniority,
                    "job_title": job.get("title") or "",
                    "job_company": job.get("company") or "",
                    "job_description": (job.get("description") or "")[:1500],
                    "dismiss_reasons_top": dismiss_reasons_top,
                    # v1.7.0-beta.63 (#638 Stufe 3): Few-Shot-Beispiele
                    "recent_dismissals": recent_dismissals_fewshot,
                }
                result = svc.run(TaskKind.MATCH_JOB_TO_SKILLS, payload)
                if not result.success:
                    errors.append({
                        "hash": job["hash"],
                        "title": job.get("title"),
                        "error": result.fallback_message or "unknown",
                    })
                    continue
                decision = (result.payload or {}).get("decision", "UNSICHER")
                # #691: leere/Platzhalter-Begruendung nicht roh durchreichen
                reason = ((result.payload or {}).get("reason") or "").strip()
                if not reason:
                    reason = "(lokale KI lieferte keine Begruendung)"
                entry = {
                    "hash": job["hash"],
                    "title": job.get("title"),
                    "company": job.get("company"),
                    "score": job.get("score"),
                    "reason": reason,
                }
                if decision == "PASST_NICHT":
                    if not dry_run:
                        # v1.7.70 (#956): der Vermerk gehoert nach
                        # `dismiss_note`, nicht in den Firmen-Recherche-
                        # Notizblock. Gemessen: 30 der 143 gefuellten
                        # Spalten trugen genau dieses Protokoll.
                        try:
                            db.dismiss_job(
                                job["hash"], reason="profil_match_negativ",
                                notiz=f"[Auto-Aussortierung] {reason}")
                        except Exception as exc:
                            errors.append({
                                "hash": job["hash"], "error": str(exc)[:200],
                            })
                    passt_nicht_results.append(entry)
                elif decision == "PASST":
                    passt_results.append(entry)
                else:
                    unsicher_results.append(entry)
            except Exception as exc:
                errors.append({
                    "hash": job.get("hash"), "error": str(exc)[:200],
                })

        try:
            modell_name = status.selected_model or ""
        except Exception:
            modell_name = ""
        # #646: Status differenziert nach Budget-Erschoepfung
        verarbeitet = (
            len(passt_nicht_results) + len(unsicher_results)
            + len(passt_results) + len(errors)
        )
        run_status = "teilweise" if budget_erschoepft else "ok"
        result_payload = {
            "status": run_status,
            "dry_run": dry_run,
            "fehler": "",
            "geprueft": verarbeitet,
            "kandidaten_gesamt": len(candidates),
            "passt_nicht": len(passt_nicht_results),
            "unsicher": len(unsicher_results),
            "passt": len(passt_results),
            "errors_count": len(errors),
            "passt_nicht_details": passt_nicht_results[:20],
            "unsicher_details": unsicher_results[:10],
            "passt_details": passt_results[:10],
            "errors": errors[:5],
            "modell": modell_name,
            "dauer_sek": round(_time.monotonic() - run_started_at, 1),
        }
        if budget_erschoepft:
            result_payload["unverarbeitet"] = unverarbeitet
            result_payload["hinweis"] = (
                f"Zeit-Budget von {max_dauer_sek}s erreicht — {unverarbeitet} "
                "Stellen unverarbeitet. Erneut aufrufen um die Reste zu "
                "bearbeiten (idempotent — bereits aussortierte werden "
                "uebersprungen)."
            )
        if ohne_beschreibung:
            result_payload["uebersprungen_ohne_beschreibung"] = len(ohne_beschreibung)
            result_payload["uebersprungen_details"] = uebersprungen_details
            result_payload["uebersprungen_hinweis"] = (
                f"{len(ohne_beschreibung)} Stellen ohne Beschreibung wurden "
                "NICHT bewertet (#756) — ohne Stellentext kein fachliches "
                "Urteil. Naechster Schritt: stellenbeschreibung_nachladen(hash)."
            )
        return result_payload

    @mcp.tool()
    def scraper_diagnose(
        scraper_name: str = "",
        aktion: str = "status"
    ) -> dict:
        """Zeigt den Gesundheitszustand aller Scraper oder reaktiviert einen deaktivierten Scraper (#432).

        Args:
            scraper_name: Name eines bestimmten Scrapers (z.B. 'stepstone', 'indeed'). Leer = alle anzeigen.
            aktion: 'status' = Gesundheitsdaten anzeigen, 'reaktivieren' = deaktivierten Scraper wieder aktivieren.
        """
        from ..job_scraper import zugriffsart_von as _zugriffsart
        from ..job_scraper import SOURCE_REGISTRY as _quellen_katalog

        def _quellen_registry():
            return _quellen_katalog

        health = db.get_scraper_health()
        if not health:
            return {
                "status": "leer",
                "nachricht": "Keine Scraper-Daten vorhanden. Starte zuerst eine Jobsuche."
            }

        if aktion == "reaktivieren" and scraper_name:
            entry = next((h for h in health if h["scraper_name"] == scraper_name), None)
            if not entry:
                return {"fehler": f"Scraper '{scraper_name}' nicht gefunden."}
            db.toggle_scraper(scraper_name, True)
            return {
                "status": "reaktiviert",
                "scraper": scraper_name,
                "nachricht": f"Scraper '{scraper_name}' wurde reaktiviert und wird bei der naechsten Suche wieder verwendet."
            }

        if scraper_name:
            health = [h for h in health if h["scraper_name"] == scraper_name]
            if not health:
                return {"fehler": f"Scraper '{scraper_name}' nicht gefunden."}

        # #500: Defekt-Quellen aus SOURCE_REGISTRY anreichern
        from ..job_scraper import SOURCE_REGISTRY
        defekte = []
        for key, info in SOURCE_REGISTRY.items():
            if info.get("defekt"):
                defekte.append({
                    "name": key,
                    "anzeigename": info.get("name", key),
                    "grund": info.get("defekt_grund"),
                    "manueller_fallback": info.get("manueller_fallback"),
                })

        scrapers = []
        stumme = []
        ohne_passung = []
        deaktiviert_auto = []
        for h in health:
            success_rate = round(h["total_successes"] / h["total_runs"] * 100) if h["total_runs"] else 0
            consec_silent = h.get("consecutive_silent") or 0
            last_count = h.get("last_count") or 0
            entry = {
                "name": h["scraper_name"],
                "aktiv": bool(h["is_active"]),
                "letzter_lauf": h.get("last_run"),
                "letzter_erfolg": h.get("last_success"),
                "fehler_serie": h["consecutive_failures"],
                "stille_serie": consec_silent,
                # v1.6.5 (#553): drei klare Felder statt einem ambigen "letzte_treffer".
                # letzte_rohtreffer = was der Scraper geliefert hat,
                # letzte_gefilterte_treffer = nach MUSS/AUSSCHLUSS/Score-Filter,
                # letzte_neue_treffer = wirklich neu in der DB (Duplikate raus).
                "letzte_rohtreffer": last_count,
                # #995 (08.09.2026): `letzte_rohtreffer` hiess nicht
                # ueberall dasselbe — zehn Adapter filtern INTERN nach
                # Suchbegriffen, bevor sie zurueckgeben. Bei ihnen war
                # die "Roh"-Zahl bereits das Ergebnis des Filters, und
                # "liefert nichts" sah aus wie "liefert nichts
                # Passendes". `gesehen` ist, was die Quelle wirklich
                # geliefert hat; None heisst "der Adapter meldet es
                # nicht", nicht "null".
                "gesehen": h.get("last_seen_count"),
                "letzte_gefilterte_treffer": h.get("last_filtered_count") or 0,
                "letzte_neue_treffer": h.get("last_new_count") or 0,
                # Backward-compat-Alias (Frontend/Notes nutzen evtl. noch den alten Namen)
                "letzte_treffer": last_count,
                "letzter_status_detail": h.get("last_status_detail"),
                "erfolgsrate": f"{success_rate}%",
                "laeufe_gesamt": h["total_runs"],
                "durchschn_zeit_s": round(h["avg_time_s"], 1),
                "letzter_fehler": h.get("last_error"),
                # v1.7.17 (#906): Deaktivierung nachvollziehbar als eigene
                # Felder — 'deprecated' (bewusst, Registry) und
                # auto-deaktiviert (Automatik) sind zwei verschiedene
                # Dinge; die Probe zeigt, ob die API ueberhaupt tot ist.
                "zugriffsart": _zugriffsart(h["scraper_name"]),
                # #996 (08.09.2026): eine Quelle mit globalem Fokus ist
                # nicht kaputt, wenn sie fuer eine DACH-Suche nichts
                # bringt — sie ist die falsche Quelle. Ohne dieses Feld
                # sieht beides gleich aus, und genau daran hing die
                # Frage des Nutzers ("Was habe ich mit US zu tun?").
                "regionen_fokus": (
                    _quellen_registry().get(h["scraper_name"]) or {}
                ).get("regionen_fokus", "dach"),
                "regionen_befund": (
                    _quellen_registry().get(h["scraper_name"]) or {}
                ).get("regionen_befund"),
                "deaktiviert_am": h.get("deaktiviert_am"),
                "deaktiviert_grund": h.get("deaktiviert_grund"),
                "letzte_probe_am": h.get("letzte_probe_am"),
                "letzte_probe_status": h.get("letzte_probe_status"),
            }
            scrapers.append(entry)
            # #995 AK 4: eine Quelle, die liefert, aber nichts Passendes,
            # wird BENANNT statt unter "stumm" gefuehrt. Sie arbeitet
            # einwandfrei — sie ist nur die falsche Quelle fuer dieses
            # Profil (#996 MERKE 5).
            _gesehen = h.get("last_seen_count")
            if _gesehen and last_count <= 0:
                ohne_passung.append({
                    "name": entry["name"], "gesehen": _gesehen,
                    "regionen_fokus": entry["regionen_fokus"],
                })
            elif consec_silent >= 3 and h["is_active"]:
                stumme.append(entry["name"])
            if not h["is_active"] and consec_silent >= 5:
                deaktiviert_auto.append(entry["name"])

        result = {
            "status": "ok",
            "scraper_anzahl": len(scrapers),
            "scrapers": scrapers,
        }
        if defekte:
            result["defekte_quellen"] = defekte
            result["hinweis_defekt"] = (
                f"{len(defekte)} Quelle(n) sind aktuell als defekt markiert "
                "(URL veraltet, Bot-Schutz oder Timeout). Sie werden nicht "
                "automatisch durchsucht. Workaround: Chrome-Extension oeffnen "
                "und Stellen via stelle_manuell_anlegen nach PBP uebernehmen."
            )
        if ohne_passung:
            result["quellen_ohne_passung"] = ohne_passung
            result["hinweis_ohne_passung"] = (
                f"{len(ohne_passung)} Quelle(n) liefern Stellen, aber keine, "
                "die zu deinen Suchbegriffen passt. Das ist KEIN Defekt und "
                "fuehrt nicht zur Abschaltung — die Quelle arbeitet, sie ist "
                "nur die falsche fuer dieses Profil. Bei globalem Fokus "
                "(regionen_fokus) lohnt es sich zu pruefen, ob sie "
                "eingeschaltet bleiben soll."
            )
        if stumme:
            result["stumme_quellen"] = stumme
            result["hinweis_stumm"] = (
                f"{len(stumme)} Quelle(n) liefern seit mehreren Laeufen 0 Treffer. "
                "Pruefe, ob Selektoren veraltet sind oder die Quelle den Standort nicht abdeckt."
            )
        if deaktiviert_auto:
            result["auto_deaktiviert"] = deaktiviert_auto
            result["hinweis_reaktivierung"] = (
                "Diese Quellen wurden nach 5+ stillen Laeufen automatisch deaktiviert. "
                "Reaktivierung via scraper_diagnose(scraper_name=..., aktion='reaktivieren')."
            )
        return result

    @mcp.tool()
    def quellen_health_check(quellen: list[str] = [], parallel: bool = True,
                             budget_sekunden: int = 90) -> dict:
        """v1.7.0-beta.51 (#624 Phase 2): Aktiver Probe-Check fuer Job-Quellen.

        Macht pro Quelle einen minimalen HTTP-Request (1 Stelle, keine
        Filter) um zu pruefen ob die API/Feed-Endpoint erreichbar ist.
        Ergaenzt scraper_diagnose (das auf Liefer-Statistiken basiert) —
        hier kommt die Info „API selbst erreichbar JA/NEIN" aus einem
        echten Request.

        Args:
            quellen: Liste der zu pruefenden Source-Keys. Wenn leer:
                alle mit definiertem Probe (~12 Quellen).
            parallel: Wenn True (Default), Probes parallel via Threads.
            budget_sekunden: Hartes Wall-Clock-Budget (Default 90s, min 5s).
                Bei Ueberschreitung kommt ein TEILERGEBNIS zurueck
                (`abgebrochen=True` + `nicht_geprueft`), statt in den
                4-Minuten-MCP-Timeout zu laufen (#762/#761).

        Returns:
            count_total, count_reachable, results (Liste pro Quelle).
            Pro Quelle: source, reachable, http_status, latency_ms, error.

        Use Case:
            User: „Warum kommen von <Quelle> seit Tagen keine Treffer?"
            Claude: ruft quellen_health_check mit dieser Quelle, sagt:
            „API liefert 503 seit 3 Sekunden — ist temporär weg."
            ODER „API liefert 200 — die Suche selbst ist das Problem,
            evtl. liegt's an deinen Suchbegriffen."
        """
        from ..job_scraper.health import check_source, get_probable_sources
        from concurrent.futures import (
            ThreadPoolExecutor, as_completed, TimeoutError as _FuturesTimeout,
        )
        import time as _time

        targets = quellen if quellen else get_probable_sources()
        # #762/#761: Hartes Wall-Clock-Budget mit Teilergebnis. Vorher wartete
        # pool.map() auf ALLE Probes — bei haengenden Quellen lief der Aufruf in
        # den 4-Minuten-MCP-Timeout ("No result received / server unresponsive")
        # und lieferte gar nichts. Analog zu den Budget-Caps bei
        # stellen_auto_aussortieren / stellen_bulk_bewerten.
        budget = max(5, int(budget_sekunden or 90))
        _start = _time.monotonic()
        results: list = []
        nicht_geprueft: list[str] = []
        budget_gerissen = False

        if parallel and len(targets) > 1:
            pool = ThreadPoolExecutor(max_workers=8)
            futures = {pool.submit(check_source, s): s for s in targets}
            try:
                for fut in as_completed(futures, timeout=budget):
                    try:
                        results.append(fut.result())
                    except Exception as exc:
                        results.append({
                            "source": futures[fut], "reachable": False,
                            "error": str(exc)[:120],
                        })
            except _FuturesTimeout:
                budget_gerissen = True
                nicht_geprueft = [s for f, s in futures.items() if not f.done()]
            finally:
                # NICHT auf haengende Probes warten — sonst reissen wir den
                # Client-Timeout trotz Budget.
                pool.shutdown(wait=False, cancel_futures=True)
        else:
            for s in targets:
                if _time.monotonic() - _start > budget:
                    budget_gerissen = True
                    nicht_geprueft.append(s)
                    continue
                results.append(check_source(s))

        reachable = sum(1 for r in results if r.get("reachable"))
        # v1.7.23 (#808): "antwortet" und "liefert Stellen" sind zwei
        # verschiedene Fragen. Vorher zaehlte nur die erste — und
        # scraper_diagnose meldete 93-98 % Erfolg fuer Quellen, die seit
        # Wochen nichts lieferten.
        liefert = sum(1 for r in results
                      if r.get("reachable") and r.get("inhalt") == "ok")
        auffaellig = [
            {"quelle": r.get("source"),
             "inhalt": r.get("inhalt"),
             "hinweis": r.get("inhalt_hinweis") or "",
             "treffer": r.get("treffer")}
            for r in results
            if r.get("reachable") and r.get("inhalt") in ("leer", "verdaechtig")
        ]

        # v1.7.17 (#906): Probe-Ergebnis an der Quelle PERSISTIEREN und
        # den sich selbst bestaetigenden 'deprecated'-Zustand aufbrechen:
        # eine auto-deaktivierte Quelle laeuft nie wieder, also wird ihr
        # Status nie widerlegt. Antwortet die API jetzt mit HTTP 200,
        # wird sie als 'pruefen' gemeldet — NICHT als tot. (Bewusst im
        # Registry deprecated markierte Quellen bleiben deprecated.)
        wieder_erreichbar: list = []
        try:
            from ..job_scraper import SOURCE_REGISTRY as _REG
            conn = db.connect()
            _jetzt = __import__("datetime").datetime.now().isoformat()
            for r in results:
                src = r.get("source")
                if not src:
                    continue
                _probe_status = (f"HTTP {r['http_status']}"
                                 if r.get("http_status")
                                 else (r.get("error") or "unbekannt")[:80])
                # #808: Der gespeicherte Status soll die WAHRHEIT tragen,
                # nicht nur die HTTP-Zahl. "HTTP 200" neben einer Quelle,
                # die nichts liefert, ist genau die irrefuehrende Angabe,
                # um die es in diesem Issue geht.
                if r.get("inhalt") in ("leer", "verdaechtig"):
                    _probe_status = f"{_probe_status} / {r['inhalt']}"
                conn.execute(
                    "UPDATE scraper_health SET letzte_probe_am=?, "
                    "letzte_probe_status=? WHERE scraper_name=?",
                    (_jetzt, _probe_status, src))
                if not r.get("reachable"):
                    continue
                # #808: Nur wer auch INHALT liefert, gilt als
                # wiederbelebt. Sonst meldet der Check eine Quelle als
                # "pruefen", die nachweislich nichts zurueckgibt.
                if r.get("inhalt") in ("leer", "verdaechtig"):
                    continue
                if (_REG.get(src) or {}).get("deprecated"):
                    continue
                row = conn.execute(
                    "SELECT is_active, deaktiviert_grund FROM scraper_health "
                    "WHERE scraper_name=?", (src,)).fetchone()
                if row and not row["is_active"]:
                    conn.execute(
                        "UPDATE scraper_health SET last_status_detail=? "
                        "WHERE scraper_name=?",
                        ("pruefen: API erreichbar, Parser/Abfrage liefert "
                         "nichts (#906)", src))
                    wieder_erreichbar.append({
                        "quelle": src,
                        "deaktiviert_grund": row["deaktiviert_grund"],
                        "probe": _probe_status,
                    })
            conn.commit()
        except Exception as exc:
            logger.debug("Probe-Vermerk (#906) uebersprungen: %s", exc)

        # (Linien-Unterschied: der Custom-Quellen-Ping (B16/#627) existiert nur
        # in der 1.8-Linie.)
        antwort = {
            "count_total": len(results),
            "count_reachable": reachable,
            "count_liefert_stellen": liefert,
            # #813 (08.09.2026): "nicht pruefbar" ist nicht "nicht
            # erreichbar". Fuenf der sieben abgeschalteten Quellen haben
            # gar keinen Probe (`no_probe_defined`) und wurden trotzdem
            # als unerreichbar gezaehlt — "5 von 7 nicht erreichbar" hiess
            # in Wahrheit "5 nicht pruefbar". Dieselbe Verwechslung wie
            # #989: eine fehlende Information sah aus wie eine negative.
            "count_unreachable": len([
                r for r in results
                if not r.get("reachable")
                and r.get("error") != "no_probe_defined"]),
            "count_nicht_pruefbar": len([
                r for r in results if r.get("error") == "no_probe_defined"]),
            "results": results,
            "hinweis": (
                f"{reachable} von {len(results)} Quellen antworten, "
                f"{liefert} davon liefern auch Stellen. "
                + (f"{len([r for r in results if r.get('error') == 'no_probe_defined'])} "
                   "Quelle(n) haben gar keinen Probe — ueber sie sagt "
                   "dieser Check NICHTS, weder gut noch schlecht. "
                   if any(r.get("error") == "no_probe_defined" for r in results)
                   else "")
                + "Ergaenzend zur Liefer-Statistik in scraper_diagnose."
            ),
        }
        if auffaellig:
            antwort["antwortet_ohne_stellen"] = auffaellig
            antwort["warnung"] = (
                f"{len(auffaellig)} Quelle(n) antworten mit HTTP 200, "
                "liefern aber nichts Verwertbares. Das ist der Fall, den "
                "eine reine Statuspruefung nicht sieht — meist ein "
                "veralteter Endpunkt oder ein falscher Firmen-Slug, keine "
                "Stoerung. Details je Quelle unter 'antwortet_ohne_stellen'.")
        if wieder_erreichbar:
            antwort["wieder_erreichbar"] = wieder_erreichbar
            antwort["hinweis"] += (
                f" | {len(wieder_erreichbar)} auto-deaktivierte Quelle(n) "
                "antworten wieder (Status 'pruefen' gesetzt) — das Problem "
                "liegt dann am Parser/an der Abfrage, nicht an der API (#906)."
            )
        # #762/#761: Teilergebnis transparent machen statt still zu kuerzen.
        if budget_gerissen:
            antwort["abgebrochen"] = True
            antwort["nicht_geprueft"] = nicht_geprueft
            antwort["hinweis"] = (
                f"TEILERGEBNIS: Budget von {budget}s erreicht — "
                f"{len(nicht_geprueft)} Quelle(n) wurden nicht geprueft "
                f"({', '.join(nicht_geprueft[:8])}"
                f"{' ...' if len(nicht_geprueft) > 8 else ''}). "
                "Die restlichen Ergebnisse sind gueltig. Fuer die offenen "
                "Quellen gezielt nachfassen: quellen_health_check(quellen=[...]) "
                "oder budget_sekunden erhoehen."
            )
        return antwort

    @mcp.tool()
    def quellen_aus_urls_korrigieren(dry_run: bool = True) -> dict:
        """v1.7.0-beta.47 (#613): Korrigiert source='manuell' anhand der job-URL.

        Geht durch alle Stellen mit source='manuell' (egal ob aktiv oder
        aussortiert) und prueft die URL. Wenn die URL einer bekannten
        Quelle zugeordnet werden kann (LinkedIn, StepStone, Indeed, ...),
        wird source umgesetzt.

        Args:
            dry_run: Wenn True (Default), nur Vorschau ohne Aenderung.
                     Mit dry_run=False wird tatsaechlich geschrieben.

        Returns:
            count_total, count_changed, changes (Liste der geplanten
            oder durchgefuehrten Aenderungen pro Stelle).

        Idempotent: ein zweiter Lauf nach Erfolg findet 0 Kandidaten.
        """
        from ..services.url_to_source import detect_source_from_url
        conn = db.connect()
        pid = db.get_active_profile_id()
        rows = conn.execute(
            "SELECT hash, title, company, url, source FROM jobs "
            "WHERE source='manuell' AND url IS NOT NULL AND url != '' "
            "AND (profile_id=? OR profile_id IS NULL)",
            (pid,)
        ).fetchall()
        changes = []
        applied = 0
        for r in rows:
            new_source = detect_source_from_url(r["url"])
            if new_source != "manuell":
                changes.append({
                    "hash": r["hash"],
                    "title": (r["title"] or "")[:60],
                    "company": (r["company"] or "")[:40],
                    "url": (r["url"] or "")[:80],
                    "source_alt": "manuell",
                    "source_neu": new_source,
                })
                if not dry_run:
                    try:
                        conn.execute(
                            "UPDATE jobs SET source=? WHERE hash=?",
                            (new_source, r["hash"])
                        )
                        applied += 1
                    except Exception as exc:
                        changes[-1]["fehler"] = str(exc)[:200]
        if not dry_run:
            conn.commit()
        return {
            "status": "vorschau" if dry_run else "ausgefuehrt",
            "count_total": len(rows),
            "count_changed": len(changes),
            "count_applied": applied,
            "changes": changes[:50],
            "hinweis": (
                "dry_run=True — kein Schreibvorgang. Nochmal mit "
                "dry_run=False aufrufen um die Aenderungen zu speichern."
                if dry_run else
                f"{applied} Stellen umgestellt. Konversion in der Quellen-"
                "Statistik des Bewerbungsbericht jetzt korrekter."
            ),
        }

    @mcp.tool()
    def bewerbungs_stellen_abgleichen(dry_run: bool = True) -> dict:
        """v1.7.9 (#764): Gleicht `applications.job_hash` und `application_jobs` ab.

        Hintergrund: Die Junction-Tabelle aus #472 wurde bei der Migration v34
        EINMALIG befuellt. Seitdem lief beides auseinander — die UI liest
        `applications.job_hash`, `bewerbung_stellen_anzeigen` liest die
        Junction. Folge: nach dem Umhaengen einer Bewerbung auf einen Repost
        zeigte die Oberflaeche weiter die alte Version mit totem Link.

        Fuehrend ist `application_jobs`. Geheilt werden vier Faelle:

        1. `job_hash` gesetzt, kein Junction-Eintrag -> Eintrag (is_primary=1)
           nachtragen.
        2. Junction vorhanden, `job_hash` leer -> aus der primaeren
           Verknuepfung zurueckschreiben.
        3. Beide gesetzt, aber verschieden -> Junction gewinnt, `job_hash`
           wird darauf gezogen.
        4. Kein oder mehrere `is_primary` pro Bewerbung -> auf genau einen
           normalisieren (juengste Verknuepfung gewinnt).

        Zusaetzlich werden verwaiste Junction-Zeilen gemeldet (Bewerbung oder
        Stelle existiert nicht mehr) — geloescht werden sie nur mit
        dry_run=False.

        Args:
            dry_run: True (Default) = nur Vorschau, kein Schreibvorgang.

        Idempotent: ein zweiter Lauf findet 0 Abweichungen.
        """
        from ..database import _gen_id
        conn = db.connect()
        pid = db.get_active_profile_id()
        apps = conn.execute(
            "SELECT id, job_hash, company, title FROM applications "
            "WHERE (profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchall()

        changes: list[dict] = []
        applied = 0

        def _apply(sql: str, params: tuple) -> None:
            nonlocal applied
            if not dry_run:
                conn.execute(sql, params)
                applied += 1

        for a in apps:
            aid = a["id"]
            jh = (a["job_hash"] or "").strip()
            links = conn.execute(
                "SELECT job_hash, is_primary FROM application_jobs "
                "WHERE application_id=? ORDER BY is_primary DESC, added_at DESC",
                (aid,)
            ).fetchall()
            basis = {"bewerbung": aid[:8],
                     "firma": (a["company"] or "")[:40],
                     "titel": (a["title"] or "")[:50]}

            if jh and not links:
                changes.append({**basis, "fall": "junction_fehlt",
                                "job_hash": jh[-12:]})
                _apply("INSERT OR IGNORE INTO application_jobs "
                       "(id, application_id, job_hash, is_primary, added_at) "
                       "VALUES (?, ?, ?, 1, datetime('now'))",
                       (_gen_id(), aid, jh))
                continue

            if not links:
                continue

            primaer = next((l["job_hash"] for l in links if l["is_primary"]),
                           links[0]["job_hash"])

            if not jh:
                changes.append({**basis, "fall": "job_hash_leer",
                                "job_hash_neu": primaer[-12:]})
                _apply("UPDATE applications SET job_hash=?, updated_at=datetime('now') "
                       "WHERE id=?", (primaer, aid))
            elif jh != primaer:
                changes.append({**basis, "fall": "divergenz",
                                "job_hash_alt": jh[-12:],
                                "job_hash_neu": primaer[-12:],
                                "hinweis": "Junction ist fuehrend"})
                _apply("UPDATE applications SET job_hash=?, updated_at=datetime('now') "
                       "WHERE id=?", (primaer, aid))

            # Genau EIN is_primary erzwingen
            anzahl_primaer = sum(1 for l in links if l["is_primary"])
            if anzahl_primaer != 1:
                changes.append({**basis, "fall": "primary_normalisiert",
                                "anzahl_primaer_alt": anzahl_primaer})
                if not dry_run:
                    conn.execute("UPDATE application_jobs SET is_primary=0 "
                                 "WHERE application_id=?", (aid,))
                    conn.execute("UPDATE application_jobs SET is_primary=1 "
                                 "WHERE application_id=? AND job_hash=?",
                                 (aid, primaer))
                    applied += 1

        # Verwaiste Junction-Zeilen
        waisen = conn.execute(
            "SELECT aj.id, aj.application_id, aj.job_hash FROM application_jobs aj "
            "LEFT JOIN applications a ON a.id = aj.application_id "
            "LEFT JOIN jobs j ON j.hash = aj.job_hash "
            "WHERE a.id IS NULL OR j.hash IS NULL"
        ).fetchall()
        for w in waisen:
            changes.append({"fall": "verwaiste_verknuepfung",
                            "bewerbung": (w["application_id"] or "")[:8],
                            "job_hash": (w["job_hash"] or "")[-12:]})
            _apply("DELETE FROM application_jobs WHERE id=?", (w["id"],))

        if not dry_run:
            conn.commit()

        return {
            "status": "vorschau" if dry_run else "ausgefuehrt",
            "count_bewerbungen": len(apps),
            "count_abweichungen": len(changes),
            "count_applied": applied,
            "changes": changes[:50],
            "hinweis": (
                "dry_run=True — kein Schreibvorgang. Nochmal mit dry_run=False "
                "aufrufen, um den Abgleich zu speichern."
                if dry_run else
                f"{applied} Korrekturen geschrieben. UI und "
                "bewerbung_stellen_anzeigen zeigen jetzt dieselbe Stelle."
            ),
        }

    @mcp.tool()
    def stellen_dubletten_pruefen(max_stellen: int = 0) -> dict:
        """Findet Stellen, die mehrfach im Bestand liegen (#951).

        Der Bestand ist gewachsen, bevor es die quellenuebergreifende
        Erkennung gab. Dieser Lauf gruppiert ihn nachtraeglich —
        **er schreibt nichts und fuehrt nichts zusammen.**

        Gruppiert wird nur nach nachrechenbaren Merkmalen: identische
        Anzeigen-URL (ohne Tracking-Parameter) oder identischer
        normalisierter Titel bei gleicher Firma. Eine
        Aehnlichkeitsrechnung wuerde hier schaetzen, und die
        Nutzervorgabe lautet Recall vor Praezision: zwei getrennte
        Eintraege sind aergerlich, eine falsch verschmolzene Stelle ist
        schlimmer.

        Fuer einen bestaetigten Fall ist `stelle_mergen` der Weg (#470).

        Args:
            max_stellen: 0 = der ganze Bestand.
        """
        from ..services import stellen_dublette
        return stellen_dublette.bestand_pruefen(db, max_stellen=max_stellen)

    @mcp.tool()
    def stellen_urls_heilen(dry_run: bool = True, nur_aktive: bool = True) -> dict:
        """v1.7.9 (#763): Heilt URL-Qualitaet im BESTAND (Datenmigration).

        Hintergrund: Der Scraper-Fix aus #645 wirkte nur auf NEUE Laeufe —
        das damals angekuendigte Akzeptanzkriterium AK5 (Bestands-Heilung)
        wurde nie umgesetzt. Alle vor beta.71 angelegten Stellen tragen die
        Regression bis heute mit (leere URL bzw. Such-URL ohne Markierung).

        Zwei Heilungen, beide ohne Netzzugriff:

        1. **Reklassifizierung** (verlustfrei): `is_search_url` wird aus der
           gespeicherten URL neu bestimmt. Heilt BEIDE Richtungen — Alt-Stellen
           mit Such-URL und Flag=0 werden markiert, und Stellen, die der
           save_jobs-Guard defensiv auf 1 setzte, obwohl inzwischen eine echte
           Detail-URL nachgepflegt wurde, werden wieder freigegeben (das
           entsperrt stellenbeschreibung_nachladen).
        2. **Such-URL nachtragen** bei komplett leerer URL, sofern fuer die
           Quelle ein Handoff-Template existiert. Ergebnis wird IMMER als
           `is_search_url=1` markiert — nie als Detail-URL ausgegeben.

        EHRLICHE GRENZE: Eine echte Detail-URL laesst sich NICHT rekonstruieren.
        Die Portal-IDs (xing_job_id/linkedin_job_id) werden von den Scrapern
        zwar ins Job-Dict gelegt, aber nie in die DB geschrieben, und der
        stelle_hash ist Einweg-MD5 ohne ID-Anteil. Was hier entsteht, ist eine
        gezielte SUCH-URL — klickbar und ehrlich markiert, damit der Nutzer die
        Anzeige selbst findet, statt vor einem leeren Feld zu stehen.

        Args:
            dry_run: True (Default) = nur Vorschau, kein Schreibvorgang.
            nur_aktive: True (Default) = nur is_active=1; False = auch
                aussortierte Stellen mitheilen.

        Returns:
            status, count_total, count_changed, count_applied, changes,
            nicht_heilbar (Stellen ohne URL und ohne Handoff-Template).

        Idempotent: ein zweiter Lauf findet 0 Kandidaten.
        """
        from ..job_scraper import is_search_result_url
        # v1.7.9: reine Daten-Tabelle. In der v1.8-Linie liegt dieselbe
        # Tabelle in job_scraper/handoff.py (B25/#735) — der Import faellt
        # deshalb der Reihe nach durch, ohne dass eine Linie das Feature der
        # anderen mitschleppen muss.
        try:
            from ..job_scraper.such_urls import HANDOFF_URL_TEMPLATES
        except Exception:
            try:
                from ..job_scraper.handoff import HANDOFF_URL_TEMPLATES
            except Exception:
                HANDOFF_URL_TEMPLATES = {}

        conn = db.connect()
        pid = db.get_active_profile_id()
        sql = ("SELECT hash, title, company, location, url, source, is_search_url, "
               "is_active FROM jobs WHERE (profile_id=? OR profile_id IS NULL)")
        if nur_aktive:
            sql += " AND is_active=1"
        rows = conn.execute(sql, (pid,)).fetchall()

        changes: list[dict] = []
        nicht_heilbar: list[dict] = []
        applied = 0

        def _such_url(source: str, titel: str, ort: str) -> str:
            """Baut eine gezielte Such-URL — identische Formel wie build_handoff."""
            tpl = HANDOFF_URL_TEMPLATES.get((source or "").lower())
            if not tpl:
                return ""
            kw = (titel or "").strip()
            if not kw:
                return ""
            try:
                return tpl.format(
                    keyword=quote_plus(kw),
                    keyword_pfad=quote_plus(kw.replace(" ", "-")),
                    ort=quote_plus((ort or "").strip()),
                )
            except Exception:
                return ""

        for r in rows:
            url = (r["url"] or "").strip()
            alt_flag = 1 if r["is_search_url"] else 0
            eintrag = {
                "hash": r["hash"], "title": (r["title"] or "")[:60],
                "company": (r["company"] or "")[:40], "source": r["source"],
            }

            if url:
                # Fall 1: Flag gegen die tatsaechliche URL neu bestimmen
                neu_flag = 1 if is_search_result_url(url) else 0
                if neu_flag != alt_flag:
                    eintrag.update({
                        "aktion": "reklassifiziert", "url": url[:80],
                        "is_search_url_alt": alt_flag, "is_search_url_neu": neu_flag,
                    })
                    changes.append(eintrag)
                    if not dry_run:
                        try:
                            conn.execute("UPDATE jobs SET is_search_url=? WHERE hash=?",
                                         (neu_flag, r["hash"]))
                            applied += 1
                        except Exception as exc:
                            eintrag["fehler"] = str(exc)[:200]
                continue

            # Fall 2: URL komplett leer -> gezielte Such-URL nachtragen
            such = _such_url(r["source"] or "", r["title"] or "", r["location"] or "")
            if such:
                eintrag.update({
                    "aktion": "such_url_nachgetragen", "url_neu": such[:100],
                    "is_search_url_neu": 1,
                    "hinweis": "Such-URL, KEINE Detail-URL — Anzeige selbst heraussuchen.",
                })
                changes.append(eintrag)
                if not dry_run:
                    try:
                        conn.execute(
                            "UPDATE jobs SET url=?, is_search_url=1 WHERE hash=?",
                            (such, r["hash"]))
                        applied += 1
                    except Exception as exc:
                        eintrag["fehler"] = str(exc)[:200]
            else:
                eintrag["grund"] = (
                    f"Quelle '{r['source']}' hat kein Handoff-Template — "
                    "Anzeige nur manuell auffindbar."
                )
                nicht_heilbar.append(eintrag)

        if not dry_run:
            conn.commit()

        return {
            "status": "vorschau" if dry_run else "ausgefuehrt",
            "count_total": len(rows),
            "count_changed": len(changes),
            "count_applied": applied,
            "count_nicht_heilbar": len(nicht_heilbar),
            "changes": changes[:50],
            "nicht_heilbar": nicht_heilbar[:20],
            "hinweis": (
                "dry_run=True — kein Schreibvorgang. Nochmal mit dry_run=False "
                "aufrufen, um die Aenderungen zu speichern."
                if dry_run else
                f"{applied} Stellen geheilt. WICHTIG: nachgetragene URLs sind "
                "SUCH-URLs (is_search_url=1), keine Detail-Links — echte "
                "Detail-URLs sind aus dem Bestand nicht rekonstruierbar."
            ),
        }

    @mcp.tool()
    def verwaiste_stellenrefs_bereinigen(
        strategie: str = "report",
        dry_run: bool = True,
    ) -> dict:
        """v1.7.0-beta.47 (#616): Findet/bereinigt verwaiste job_hash-Refs in Bewerbungen.

        Bewerbungen koennen einen `job_hash` referenzieren, dessen Stelle
        nicht (mehr) in der `jobs`-Tabelle existiert. Folge: stelle_bearbeiten
        scheitert, fit_analyse hat keinen Kontext, kontakt_verknuepfen
        bricht ab (#615).

        Args:
            strategie: 'report' (Default) — nur auflisten ohne Aenderung.
                       'rekonstruieren' — eine Platzhalter-Stelle anlegen aus
                         title/company/url der Bewerbung.
                       'leeren' — job_hash der Bewerbung auf '' setzen.
            dry_run: Bei 'rekonstruieren'/'leeren' Vorschau ohne Schreibvorgang.

        Returns:
            count_total, count_orphaned, list von Bewerbungen mit Detail.
        """
        if strategie not in ("report", "rekonstruieren", "leeren"):
            return {"fehler": "strategie muss 'report', 'rekonstruieren' "
                              "oder 'leeren' sein."}
        conn = db.connect()
        pid = db.get_active_profile_id()
        # Alle Bewerbungen mit nicht-leerem job_hash
        apps = conn.execute(
            "SELECT id, job_hash, title, company, url, status FROM applications "
            "WHERE job_hash IS NOT NULL AND job_hash != '' "
            "AND (profile_id=? OR profile_id IS NULL)",
            (pid,)
        ).fetchall()
        orphans = []
        for a in apps:
            jh = a["job_hash"]
            # Existiert die Stelle? db.get_job liest die jobs-Tabelle —
            # resolve_job_hash hier nicht nutzbar weil das nur den Hash
            # transformiert, nicht die Existenz prueft.
            if db.get_job(jh) is None:
                orphans.append({
                    "application_id": a["id"][:8],
                    "_full_id": a["id"],  # intern fuer cleanup
                    "title": (a["title"] or "")[:60],
                    "company": (a["company"] or "")[:40],
                    "url": (a["url"] or "")[:80],
                    "status": a["status"],
                    "missing_job_hash": jh,
                })
        applied = 0
        actions: list[dict] = []
        if strategie != "report" and not dry_run:
            from datetime import datetime as _dt
            from ..job_scraper import stelle_hash as _stelle_hash
            for o in orphans:
                aid_short = o["application_id"]
                full_app_id = o["_full_id"]
                if strategie == "leeren":
                    try:
                        # NULL statt '' — '' wuerde FK-Constraint verletzen
                        # weil hash='' nicht in jobs existiert.
                        conn.execute(
                            "UPDATE applications SET job_hash=NULL WHERE id=?",
                            (full_app_id,)
                        )
                        applied += 1
                        actions.append({"application_id": aid_short,
                                        "aktion": "job_hash auf NULL gesetzt"})
                    except Exception as exc:
                        actions.append({"application_id": aid_short,
                                        "fehler": str(exc)[:200]})
                elif strategie == "rekonstruieren":
                    try:
                        # Platzhalter-Stelle anlegen mit denselben Daten
                        company = o["company"] or "Unbekannt"
                        title = o["title"] or "Unbekannte Stelle"
                        url = o["url"] or ""
                        from ..services.url_to_source import detect_source_from_url
                        source = detect_source_from_url(url) if url else "manuell"
                        new_hash = _stelle_hash(source, f"{company} {title}")
                        existing = db.get_job(new_hash)
                        if not existing:
                            db.save_jobs([{
                                "hash": new_hash,
                                "title": title,
                                "company": company,
                                "location": "",
                                "url": url,
                                "source": source,
                                "description": (
                                    "[Rekonstruiert v1.7.0-beta.47 (#616)] "
                                    "Diese Stelle wurde aus einer Bewerbung "
                                    "rekonstruiert weil die urspruengliche "
                                    "Stelle nicht mehr in der jobs-Tabelle "
                                    "existierte."
                                ),
                                "score": 0,
                                "is_pinned": False,
                                "remote_level": "unbekannt",
                                "employment_type": "festanstellung",
                                "found_at": _dt.now().isoformat(),
                            }])
                            # save_jobs setzt is_active immer auf 1 —
                            # Platzhalter sollen nicht im aktiven Pool sein
                            scoped_for_active = db._scope_job_hash(new_hash)
                            conn.execute(
                                "UPDATE jobs SET is_active=0, "
                                "dismiss_reason='rekonstruiert_orphan_616' "
                                "WHERE hash=?",
                                (scoped_for_active,)
                            )
                        # Bewerbung auf den neuen Hash umstellen
                        scoped_hash = db._scope_job_hash(new_hash)
                        conn.execute(
                            "UPDATE applications SET job_hash=? WHERE id=?",
                            (scoped_hash, full_app_id)
                        )
                        applied += 1
                        actions.append({"application_id": aid_short,
                                        "aktion": f"rekonstruiert als {new_hash[:12]}"})
                    except Exception as exc:
                        actions.append({"application_id": aid_short,
                                        "fehler": str(exc)[:200]})
            conn.commit()
        return {
            "status": "vorschau" if (strategie == "report" or dry_run) else "ausgefuehrt",
            "strategie": strategie,
            "dry_run": dry_run,
            "count_total_apps": len(apps),
            "count_orphaned": len(orphans),
            "count_applied": applied,
            "orphans": orphans[:50],
            "actions": actions[:50],
            "hinweis": (
                "Strategie 'report' = nur auflisten. 'rekonstruieren' "
                "legt eine Platzhalter-Stelle an (is_active=0). 'leeren' "
                "setzt job_hash der Bewerbung auf ''."
                if strategie == "report" or dry_run else
                f"{applied} Bewerbung(en) bereinigt mit Strategie '{strategie}'."
            ),
        }

    @mcp.tool()
    def gehaelter_neu_auswerten(dry_run: bool = True,
                                max_stellen: int = 0) -> dict:
        """Wertet gespeicherte Gehaelter mit der heutigen Erkennung neu aus
        (#1018).

        Ein besserer Leser hilft nur neuen Stellen — der Bestand behaelt
        seine Fehltreffer und sieht dabei unauffaellig aus. Das ist die
        Lehre aus #998, und sie gilt hier genauso: bis v1.7.78 landete
        "Teilzeit: 30-35 Stunden pro Woche" als Stundensatz von 30 bis 35
        Euro in der Datenbank, **mit `salary_estimated = 0`**, also als
        BELEGT. Seit v1.7.78 zaehlen belegte Gehaelter im Score und
        geschaetzte nicht — der falsche Wert ist damit der teurere.

        Am Bestand gemessen: von 12 `stuendlich`-Treffern waren **10 in
        Wahrheit Arbeitszeiten**.

        Angefasst werden nur Stellen mit Anzeigentext. Findet die neue
        Erkennung nichts, wird der alte Wert GELOESCHT statt durch eine
        Schaetzung ersetzt — eine Anzeige, die kein Gehalt nennt, hat
        keins, und eine Luecke gehoert benannt und nicht gefuellt (#989).

        Args:
            dry_run: Vorgabe True — es wird nichts geschrieben.
            max_stellen: 0 = alle.
        """
        from ..services import gehalt_extraktion as _ge

        conn = db.connect()
        zeilen = conn.execute(
            "SELECT hash, title, description, salary_min, salary_max, "
            "salary_type, salary_estimated FROM jobs "
            "WHERE description IS NOT NULL AND LENGTH(description) > 50"
        ).fetchall()

        aenderungen, geloescht, unveraendert = [], 0, 0
        von_hand = 0
        for h, titel, besch, alt_min, alt_max, alt_typ, alt_est in zeilen:
            if max_stellen and len(aenderungen) >= max_stellen:
                break
            neu = _ge.extrahieren(besch or "")
            # Eine Schaetzung wird nur ersetzt, wenn es jetzt etwas
            # Belegtes gibt. Sie zu loeschen brauchte niemand.
            if alt_est and not neu["art"]:
                unveraendert += 1
                continue
            gleich = (alt_typ == neu["art"]
                      and (alt_min or 0) == (neu["min"] or 0)
                      and (alt_max or 0) == (neu["max"] or 0))
            if gleich:
                unveraendert += 1
                continue
            eintrag = {
                "job_hash": h[:8] if h else "",
                "titel": (titel or "")[:60],
                "vorher": {"min": alt_min, "max": alt_max, "typ": alt_typ,
                           "geschaetzt": bool(alt_est)},
                "nachher": {"min": neu["min"], "max": neu["max"],
                            "typ": neu["art"],
                            "monat_erkannt": neu["monat_erkannt"]},
                "beleg": neu["fundstelle"] or neu["grund"],
            }
            if not neu["art"]:
                geloescht += 1
            if not dry_run:
                # v1.7.82 (#1026): der Rueckgabewert wird gelesen. Ein
                # von Hand gesetztes Gehalt weist den Lauf ab, und dann
                # gehoert die Stelle NICHT in die Aenderungsliste —
                # sonst meldet der Lauf eine Aenderung, die nicht
                # stattgefunden hat (#994/#997).
                if not db.save_salary_data(
                        h, neu["min"], neu["max"], neu["art"],
                        salary_estimated=0):
                    von_hand += 1
                    if not neu["art"]:
                        geloescht -= 1
                    continue
            aenderungen.append(eintrag)
        if not dry_run:
            conn.commit()

        return {
            "status": "vorschau" if dry_run else "ausgewertet",
            "geprueft": len(zeilen),
            "geaendert": len(aenderungen),
            "davon_geloescht": geloescht,
            "von_hand_gesetzt_uebersprungen": von_hand,
            "unveraendert": unveraendert,
            "stichprobe": aenderungen[:15],
            "hinweis": (
                "Vorschau — es wurde nichts geschrieben. Mit dry_run=False "
                "werden die Werte ersetzt; wo die Anzeige kein Gehalt "
                "nennt, wird der alte Wert geloescht statt geschaetzt."
                if dry_run else
                f"{len(aenderungen)} Stelle(n) neu ausgewertet, davon "
                f"{geloescht} ohne Gehaltsangabe in der Anzeige."
            ),
        }

    @mcp.tool()
    def automatik_uebertragungen_pruefen(dry_run: bool = True,
                                         max_stellen: int = 0) -> dict:
        """Findet Stellen, die ueber ein FREMDES Titel-Muster
        aussortiert wurden (#1020).

        Bis v1.7.79 uebertrug die Automatik den haeufigsten
        Ablehnungsgrund firmenuebergreifend ueber gemeinsame
        Titel-Tokens — auch `zu_weit_entfernt`, `gehalt_zu_niedrig` und
        `firma_uninteressant`. Das sind Eigenschaften der EINZELNEN
        Anzeige: zwei Stellen mit identischem Titel koennen 5 km und
        500 km entfernt liegen.

        Gemeldet wurde eine Stelle in **9,2 km**, die als "zu weit
        entfernt" aussortiert wurde — bei einem Wunschwert von 20 km,
        und die Zahl stand in derselben Datenbankzeile wie das Urteil.

        Am hiesigen Bestand gemessen: 245 Zeilen tragen einen
        Wiedergaenger-Vermerk, 83 davon (34 %) mit einem Grund, der
        nichts ueber die Art der Stelle sagt.

        Jede automatisch entfernte Stelle zaehlte beim naechsten Lauf
        als weiterer Beleg fuer dasselbe Muster — die Regel konnte nur
        schaerfer werden, nie milder. Deshalb ist die Ruecknahme mehr
        als Kosmetik: sie nimmt die Belege wieder aus der Grundlage.

        Args:
            dry_run: Vorgabe True — es wird nichts geschrieben.
            max_stellen: 0 = alle.
        """
        from ..services import stellen_automatik as _sa

        conn = db.connect()
        zeilen = conn.execute(
            "SELECT hash, title, company, dismiss_reason, dismiss_note, "
            "distance_km, salary_min, salary_max, salary_type, "
            "salary_estimated, employment_type FROM jobs "
            "WHERE is_active=0 AND dismiss_note IS NOT NULL "
            "AND (dismiss_note LIKE '%iedergaenger nach Fachgebiet%' "
            "     OR dismiss_note LIKE '%iedergänger nach Fachgebiet%')"
        ).fetchall()

        betroffen, zurueckgeholt = [], 0
        for row in zeilen:
            (h, titel, firma, grund, note, dist, smin, smax, styp,
             sest, emp) = row
            kern = (grund or "").replace("auto:", "").split(":")[0].lower()
            if kern in _sa.UEBERTRAGBARE_GRUENDE:
                continue
            job = {"distance_km": dist, "salary_min": smin,
                   "salary_max": smax, "salary_type": styp,
                   "salary_estimated": sest, "employment_type": emp}
            eintrag = {
                "job_hash": (h or "")[:8],
                "titel": (titel or "")[:60],
                "firma": (firma or "")[:40],
                "grund": kern,
                "entfernung_km": dist,
                "widerspruch": _sa._zahl_widerspricht(db, job, kern),
                "beleg": (note or "")[:120],
            }
            betroffen.append(eintrag)
            if max_stellen and len(betroffen) >= max_stellen:
                break

        if not dry_run:
            for e in betroffen:
                voll = db.resolve_job_hash(e["job_hash"])
                if voll:
                    db.restore_job(voll)
                    zurueckgeholt += 1

        mit_zahl = sum(1 for e in betroffen if e["widerspruch"])
        return {
            "status": "vorschau" if dry_run else "zurueckgeholt",
            "geprueft": len(zeilen),
            "betroffen": len(betroffen),
            "davon_durch_zahl_widerlegt": mit_zahl,
            "zurueckgeholt": zurueckgeholt,
            "stichprobe": betroffen[:20],
            "hinweis": (
                "Vorschau — es wurde nichts geschrieben. Diese Stellen "
                "wurden ueber ein Titel-Muster einer FREMDEN Firma "
                "aussortiert, auf einem Grund, der nichts ueber die Art "
                "der Stelle sagt. Mit dry_run=False kommen sie zurueck."
                if dry_run else
                f"{zurueckgeholt} Stelle(n) zurueckgeholt. Sie zaehlen "
                "damit auch nicht mehr als Beleg fuer dasselbe Muster."
            ),
        }
