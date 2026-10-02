"""Jobsuche und Stellenverwaltung — 9 Tools (#446: stelle_bearbeiten, #432: scraper_diagnose)."""

import re
from ..services.typed_ids import kurz_job_kennung as _kurz
from ..services.dashboard_link import dashboard_link as _dashboard_link
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

    k.o.-Kriterien (Stand v1.7.147, #1146):
    1. Wiedergaenger: die Firma wurde mehrfach aus fachlichem Grund aussortiert
    2. MUSS-Keywords komplett verfehlt -> kein fachlicher Anker (nur auf
       einer lesbaren Anzeige)

    Eine FEHLENDE oder KURZE Beschreibung ist KEIN k.o.: Unbekannt ist ein
    eigener Zustand. Das Urteil ist dann NICHT_BEURTEILBAR, mit dem
    `datenlage_hinweis` (Volltext nachladen), nie "nicht empfohlen".

    Sonst entscheidet NICHT der Score (#1003): eine gelesene, gespeicherte
    Analyse, andernfalls NICHT_BEURTEILBAR.

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
        """Wie die Zahl genannt wird — nie als Prozent (H24, #1087 G4)."""
        from ..services.punkte import text as _punkte_text
        return _punkte_text(score, maximum if anteil is not None else None)
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
    # v1.7.147 (#1146): Eine fehlende oder kurze Beschreibung ist KEIN k.o.,
    # sondern eine fehlende Datengrundlage: "unbekannt" ist ein eigener
    # Zustand (NICHT_BEURTEILBAR), keine Absage. Bis v1.7.146 landeten beide
    # Faelle in `ko_gruende` und machten aus einer Anzeige ohne Text ein
    # "NICHT_EMPFOHLEN" — der Zweig `keine_beschreibung` in `passung.urteil`
    # war damit unerreichbar, und die Begruendung widersprach sich selbst
    # ("ausdruecklich keine fachliche Absage" unter einer Absage).
    datenlage_hinweis = ""
    if not desc_ok:
        datenlage_hinweis = (
            "Stellenbeschreibung fehlt — ohne sie ist keine fachliche "
            "Bewertung möglich. Beschreibung nachladen "
            "(stellenbeschreibung_nachladen), dann neu bewerten."
        )
    elif fit_result.get("beschreibung_kurz"):
        # #762: Beschreibung existiert, ist aber nur eine Kurznotiz (typisch
        # nach stelle_manuell_anlegen). Dann matchen kaum MUSS-Keywords und der
        # Score ist kuenstlich niedrig — das ist KEINE fachliche Absage.
        datenlage_hinweis = (
            "Beschreibung ist nur ein Kurztext, keine vollständige Anzeige — "
            "der Score ist dadurch NICHT belastbar und dies ist ausdrücklich "
            "keine fachliche Absage. Anzeigen-Volltext nachladen "
            "(stellenbeschreibung_nachladen) oder einfügen, dann neu bewerten."
        )
    beschreibung_nutzbar = not datenlage_hinweis
    # v1.7.35 (#972): der Hochschulabschluss-k.o. ist entfernt. Er
    # stuetzte sich auf ein Merkmal, dessen Profilseite nie modelliert
    # wurde — ein Staatlich gepruefter Techniker (DQR 6, wie Bachelor)
    # galt als "kein Abschluss". Der WAEHLBARE Ablehnungsgrund
    # `kein_hochschulabschluss` bleibt: das entscheidet der Mensch.
    # Nur auf einer Anzeige, die man lesen kann: ohne Text (oder mit einem
    # Kurztext) findet sich kein MUSS-Begriff, und das waere derselbe Fehler
    # ueber den Umweg (#1146).
    if beschreibung_nutzbar and not muss_hits and missing_muss:
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
    if datenlage_hinweis:
        befund["datenlage_hinweis"] = datenlage_hinweis
    # Der Score kommt weiter mit — als das, was er ist.
    befund["score"] = score
    if maximum:
        befund["score_maximum"] = maximum
    # H24 (#1087 G4): derselbe Satz an jedem Ort.
    from ..services.punkte import SCORE_BEDEUTUNG as _BEDEUTUNG
    befund["punkte_text"] = _skala()
    befund["score_bedeutung"] = _BEDEUTUNG
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
        f"Aufmerksamkeit: {count} ähnliche Stellen wurden wegen "
        f"'{top_reason}' aussortiert"
        + (f" (zuletzt: \"{_beleg}\")" if _beleg else "")
        + ". Prüfe ob das hier auch zutrifft."
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
    "indeed": "Indeed (häufig Timeout) — nutze jobspy_indeed",
    "google_jobs": "Google Jobs (#501) — google_jobs_url aufrufen und in Chrome-Extension öffnen",
}

# G17 (#744, v1.7.4): Bewaehrter Starter-Satz fuer den allerersten Suchlauf —
# schnell, zuverlaessig, ohne Login/Browser. Wird in der Ersterfassung
# (Wizard-Phase 5) und in der "keine_quellen"-Antwort empfohlen.
_SMART_DEFAULT_QUELLEN = ("bundesagentur", "arbeitnow", "jobspy_indeed")

# v1.7.127 (#1082): was die Score-Schwelle vergleicht. Steht an beiden
# Hinweisen der Liste, weil genau diese Frage der Anlass des Issues war —
# eine Stelle in 450 km verschwand, und niemand konnte sehen, warum.
_SCHWELLE_VERGLEICHT = (
    "Die Score-Schwelle vergleicht den FACHWERT. Entfernung, Remote-Anteil "
    "und Gehalt blenden keine Stelle aus — sie stehen im Rahmendaumen und "
    "wirken nur auf die Reihenfolge.")


def _maybe_auto_dismiss_after_search(db, job_id: str) -> None:
    """Nach der Suche aussortieren — seit #1092 nur noch ein Aufruf des
    gemeinsamen Dienstes, mit Schalter (Vorgabe aus)."""
    try:
        from ..services import auto_aussortierung
        auto_aussortierung.nach_suche(db, job_id)
    except Exception as exc:  # nicht fatal — die Suche selbst war gut
        import logging as _log
        _log.getLogger("bewerbungs_assistent.tools.jobs").warning(
            "Auto-Aussortierung nach der Suche fehlgeschlagen: %s", exc)


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
        1. Mindestens eine Quelle muss aktiviert sein (Einstellungen › Quellen)
        2. Suchkriterien sollten gesetzt sein (suchkriterien_setzen)

        Die Suche dauert 5-10 Minuten. Prüfe den Fortschritt mit jobsuche_status().
        Ergebnisse danach mit stellen_anzeigen() ansehen.

        HINWEIS #488: Wenn aktive Quellen dabei sind, die nur über die
        Claude-Erweiterung im Browser laufen (LinkedIn, StepStone, XING,
        Indeed, Google Jobs), meldet dieses Tool sie im Feld
        `manuelle_quellen` zurück UND überspringt sie im
        Hintergrund-Job — statt auf stumme Timeouts zu laufen. Claude
        soll den User vor dem Start über diese Quellen informieren und
        ihm empfehlen, sie via Chrome-Extension anzusteuern.

        ENTFERNUNG UND REMOTE (#1000, v1.7.48): dieses Tool hatte bis
        v1.7.47 die Parameter `nur_remote` und `max_entfernung_km`. Beide
        wurden entgegengenommen und von niemandem gelesen. Sie sind
        ersatzlos entfallen, weil ein Parameter ohne Wirkung schlechter
        ist als keiner. Was stattdessen wirkt:

        * Entfernung: `suchkriterien_setzen(max_entfernung_km=30)` —
          gilt dauerhaft und für jeden Lauf. Entfernung ist dabei ein
          PREIS im Score, kein Ausschluss (#910/#988): eine weite Stelle
          rutscht nach unten, statt zu verschwinden.
        * Remote: "Remote" gehört in `regionen`, und das Gewicht dafür
          steht in `gewichtung.remote`. Ein harter Remote-Filter wäre
          gefährlich, weil sehr viele Anzeigen gar keine Angabe zum
          Arbeitsmodell machen — er würde vor allem Unbekanntes
          wegwerfen (#989).

        Args:
            keywords: Suchbegriffe (Standard: aus Profil)
            quellen: Welche Portale durchsuchen (Standard: alle aktiven)
        """

        # #1096: derselbe Startweg wie Dashboard-Knopf und Automatik —
        # Quellen, Suchbegriffe, Browser-Quellen, #906-Pruefung, Watchdog
        # und Nachlauf stehen in services/jobsuche_start.
        from ..services import jobsuche_start
        erg = jobsuche_start.starten(db, quellen=quellen, keywords=keywords,
                                     herkunft="claude")
        status = erg["status"]
        if status == "keine_quellen":
            return {
                "status": "keine_quellen",
                # G17 (#744, v1.7.4): Einsteiger nicht in den Einstellungs-
                # Tab schicken, sondern den bewaehrten Starter-Satz anbieten.
                "empfohlene_start_quellen": list(_SMART_DEFAULT_QUELLEN),
                "nachricht": (
                    "Keine Job-Quellen aktiviert. Empfehlung für den "
                    "ersten Lauf: jobsuche_starten(quellen="
                    f"{list(_SMART_DEFAULT_QUELLEN)}) — schnelle, "
                    "zuverlässige Quellen ohne Login. Sie werden dabei "
                    "als aktive Quellen übernommen. Weitere Quellen: "
                    "Einstellungen › Quellen."
                ),
            }
        if status == "keine_suchbegriffe":
            return {
                "status": "keine_suchbegriffe",
                "nachricht": (
                    "Noch keine Suchkriterien gesetzt. Lege sie mit "
                    "suchkriterien_setzen() fest oder nutze "
                    "workflow_starten('jobsuche_workflow') — sonst würde "
                    "PBP mit generischen Begriffen suchen."
                ),
            }
        if status == "nur_manuelle_quellen":
            return {
                "status": "nur_manuelle_quellen",
                "manuelle_quellen": erg["manuelle_quellen"],
                "nachricht": (
                    "Alle ausgewählten Quellen laufen nur über Claude-in-Chrome "
                    "oder sind deprecated — es gibt nichts zu automatisieren. "
                    "Siehe manuelle_quellen für den jeweiligen Ersatzweg."
                ),
            }
        if status == "laeuft_bereits":
            return {
                "status": "laeuft_bereits",
                "job_id": erg["job_id"],
                "nachricht": "Eine Jobsuche läuft bereits. "
                            f"Prüfe den Fortschritt mit jobsuche_status('{erg['job_id']}')."
            }
        if status == "kein_netz":
            # v1.7.148 (#1141): offline ist kein Grund, an den Suchbegriffen zu drehen.
            return {
                "status": "kein_netz",
                "nachricht": erg["nachricht"],
                "naechster_schritt": (
                    "Verbindung prüfen (WLAN, VPN, Proxy), dann "
                    "jobsuche_starten() erneut. An Quellen und Suchbegriffen "
                    "ist nichts zu ändern."),
            }
        job_id = erg["job_id"]
        result = {
            "job_id": job_id,
            "status": "gestartet",
            "nachricht": (
                f"Jobsuche läuft im Hintergrund auf {len(erg['quellen'])} Portalen. "
                f"Das dauert 5-10 Minuten — du musst jetzt NICHT warten. "
                f"Die Status-Badge in der Sidebar zeigt den Fortschritt. "
                f"Wenn du später prüft willst: jobsuche_status('{job_id}'). "
                f"Wenn fertig: stellen_anzeigen()."
            ),
        }
        if erg["quellen_uebernommen"]:
            result["quellen_als_aktiv_uebernommen"] = erg["quellen"]
        if erg["manuelle_quellen"]:
            result["manuelle_quellen"] = erg["manuelle_quellen"]
            result["hinweis"] = (
                "Zusätzlich müsstest du für folgende manuelle Quellen "
                "Claude-in-Chrome oder die jeweiligen Ersatzwerkzeuge nutzen — "
                "sie sind im Hintergrund-Job NICHT enthalten."
            )
        # v1.7.17 (#906 Befund 2): totes Suchkriterium benennen.
        for befund in erg["stellentyp_ohne_quelle"]:
            result.setdefault("stellentyp_ohne_quelle", []).append({
                **befund,
                "warnung": (
                    f"Für '{befund['stellentyp']}' läuft in dieser Suche KEINE "
                    f"Quelle ({', '.join(befund['quellen_dafuer'])} alle "
                    "inaktiv/defekt). Die zugehörigen Kriterien "
                    "werden nicht ausgewertet. Alternativen: "
                    "quelle_handoff() für die Browser-Recherche "
                    "oder scraper_diagnose(aktion='reaktivieren')."
                ),
            })
        return result

    @mcp.tool()
    def jobsuche_status(job_id: str = "") -> dict:
        """Prüft den Fortschritt einer Jobsuche.

        Args:
            job_id: Job-ID von jobsuche_starten(). Leer: die laufende oder
                zuletzt beendete Suche.
        """
        # H32 (#1087 G14): mit Pflicht-ID endete die Frage "wie laeuft meine
        # Suche?" in einem neuen Gespraech in "Unbekannte Job-ID" — die ID
        # stand nur im alten Chat.
        if job_id:
            job = db.get_background_job(job_id)
            if job is None:
                return {"fehler": "Unbekannte Job-ID",
                        "hinweis": "Ohne job_id zeigt jobsuche_status() die letzte Suche."}
        else:
            job = db.get_running_background_job("jobsuche")
            # #1118: ein toter Lauf wird beim Nachsehen abgeschlossen,
            # statt fuer immer als "laeuft" dazustehen.
            from ..services.hintergrund_alter import abschliessen, veraltet
            if veraltet(job) and abschliessen(db, job):
                job = None
            job = job or db.get_last_finished_background_job("jobsuche")
            if job is None:
                return leer({"status": "keine_suche"},
                            "Es lief noch keine Jobsuche.",
                            "Starte sie mit jobsuche_starten().")
            job_id = job["id"]
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
            "job_id": job_id,
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

    def _mit_erlaubten_gruenden(fn):
        """Setzt die erlaubten Gruende aus der Quelle in den Docstring (#1115).

        Der Platzhalter `{ERLAUBTE_GRUENDE}` im Args-Block wird beim
        Registrieren ersetzt. Claude liest genau diesen Text als
        Parameterbeschreibung — eine abgeschriebene Liste war seit #913
        um zwei Gruende zu kurz, und "nur diese, nichts anderes" hat die
        Aufrufer daran gehindert, sie zu benutzen.
        """
        fn.__doc__ = (fn.__doc__ or "").replace(
            "{ERLAUBTE_GRUENDE}", ", ".join(ABLEHNUNGSGRUENDE))
        return fn

    def _detect_duplicate(job_hash: str) -> dict | None:
        """#1095: die Regel steht in services/aussortieren.duplikat_finden."""
        from ..services import aussortieren as _aus
        return _aus.duplikat_finden(db, job_hash)

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
        """#1095: der Lerneffekt steht in services/aussortieren.regler_anpassen."""
        from ..services import aussortieren as _aus
        return _aus.regler_anpassen(db_ref, reason, count)

    def _apply_dismiss_with_lifecycle(job_hash: str, reason_list: list[str],
                                       collect_hints: bool = True,
                                       skip_auto_adjust: bool = False) -> dict:
        """#1095: Zaehler, Lerneffekt und Hinweise stehen im Dienst
        services/aussortieren — derselbe Weg wie das Dashboard."""
        from ..services import aussortieren as _aus
        return _aus.aussortieren(db, job_hash, reason_list,
                                 collect_hints=collect_hints,
                                 skip_auto_adjust=skip_auto_adjust)

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
    @time_tool(logger, "stelle_einordnen")
    @_mit_erlaubten_gruenden
    def stelle_einordnen(job_hash: str, bewertung: str, grund: str = "",
                        gruende: list[str] = None) -> dict:
        """Bewertet eine gefundene Stelle.

        Bei 'passt_nicht' wird der Grund gespeichert und für künftige Suchen gelernt.
        Häufig genutzte Gründe führen automatisch zu Gewichtungsanpassungen.

        STRENG VERBOTEN: Die KI darf KEINE eigenen Ablehnungsgründe erfinden,
        generieren oder formulieren! Auch keine "intelligenten" Gruende wie
        "Duplikat — bereits als Bewerbung xyz erfasst". AUSSCHLIESSLICH die
        vordefinierten Gruende aus der Liste unten verwenden. Bei Unsicherheit
        den Nutzer fragen oder 'sonstiges' wählen. Jeder nicht-vordefinierte
        Grund wird automatisch auf 'sonstiges' normalisiert.

        FUER MEHRERE STELLEN AUF EINMAL: Nutze 'stellen_bulk_bewerten' mit
        Filtern wie min_score, titel_enthaelt_nicht, beschreibung_enthaelt_nicht.
        Spart Tokens und respektiert die PBP-Lifecycle-Logik (#514).

        Args:
            job_hash: Hash der Stelle
            bewertung: 'passt' oder 'passt_nicht'
            grund: Einzelner Grund bei passt_nicht (Legacy, nutze besser gruende)
            gruende: Gründe bei passt_nicht, NUR diese Werte:
                {ERLAUBTE_GRUENDE}
        """
        # #695: Existenz-Guard — vorher meldete das Tool bei unbekanntem Hash
        # "aussortiert"/"als_passend_markiert" und zaehlte sogar die
        # Ablehnungs-Statistik hoch (Phantom-Eintraege im Lerneffekt).
        if not db.get_job(job_hash):
            return {"fehler": "Stelle nicht gefunden. "
                              "Prüfe den Hash mit stellen_anzeigen()."}

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

    # H29 (#1087 G11): alter Name, einen Release lang erreichbar.
    from . import veralteter_name as _veraltet
    _veraltet(mcp, "stelle_bewerten", stelle_einordnen, "stelle_einordnen")

    @mcp.tool()
    def stelle_urteil_speichern(job_hash: str, urteil: str,
                                 begruendung: str = "",
                                 grundlage: str = "detailanalyse") -> dict:
        """Legt das Ergebnis einer Detailanalyse AN DER STELLE ab (#1007).

        Args:
            job_hash: Hash der Stelle.
            urteil: EMPFOHLEN | BEDINGT | NICHT_EMPFOHLEN |
                NICHT_BEURTEILBAR.
            begruendung: warum — in einem oder zwei Sätzen, so wie du
                es dem Menschen sagen würdest.
            grundlage: woher das Urteil stammt. Vorgabe
                'detailanalyse' (du hast Anzeige und Profil gelesen).

        **Wofür das da ist.** Bis v1.7.60 kam die Empfehlung aus dem
        Suchbegriff-Score — in den geht der Lebenslauf nicht ein. Seit
        #1003 sagt PBP ohne gelesene Analyse ehrlich
        `NICHT_BEURTEILBAR`. Dein Urteil hier ist das, was diese Lücke
        schliesst: es hängt danach an der Stelle, steht in der
        Trefferliste und überlebt das Gespräch.

        **Voraussetzung: du hast die Anzeige WIRKLICH gegen das Profil
        gelesen.** Ein Urteil, das aus dem Score abgeleitet ist, wäre
        genau der Fehler, den #1003 behebt — nur diesmal von Hand.
        Nutze `fit_analyse` für die Fakten und `projekte_anzeigen` /
        `profil_zusammenfassung` für das Profil.

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
                "hinweis": "Prüfe den Hash mit stellen_anzeigen().",
            }
        antwort = {
            "status": "gespeichert",
            "urteil": urteil.strip().upper(),
            "grundlage": grundlage or "detailanalyse",
            "hinweis": ("Der Befund hängt jetzt an der Stelle und "
                        "erscheint in der Trefferliste. Ändert sich dein "
                        "Profil, wird er als möglicherweise überholt "
                        "gekennzeichnet — nicht gelöscht."),
        }
        # v1.7.122 (#1064): passt der Anzeigentext nicht in EINE Antwort,
        # kann das Urteil ihn nicht ganz gesehen haben. Der Fall ist nach
        # der Messung selten (keine der 2.271 Anzeigen erreicht die
        # Notbremse) — aber genau dann ist der Hinweis das Einzige, was
        # zwischen "gelesen" und "halb gelesen" unterscheidet.
        try:
            from ..job_scraper.textgrenzen import AUSGABE_NOTBREMSE
            _job = db.get_job(job_hash) or {}
            _laenge = len((_job.get("description") or ""))
            if _laenge > AUSGABE_NOTBREMSE:
                antwort["warnung_beschreibung"] = (
                    f"Der Anzeigentext ist {_laenge} Zeichen lang und "
                    f"passt nicht in eine Antwort (Grenze "
                    f"{AUSGABE_NOTBREMSE}). Falls du ihn nur bis dahin "
                    "gelesen hast: den Rest mit "
                    "fit_analyse(hash, beschreibung_ab=...) holen und das "
                    "Urteil danach erneut speichern.")
        except Exception as exc:  # pragma: no cover — nie das Urteil kippen
            logger.debug("Laengenhinweis (#1064) fehlgeschlagen: %s", exc)
        return antwort

    # H29 (#1087 G11): alter Name, einen Release lang erreichbar.
    from . import veralteter_name as _veraltet
    _veraltet(mcp, "stelle_analyse_speichern", stelle_urteil_speichern, "stelle_urteil_speichern")

    @mcp.tool()
    def stelle_analyse_loeschen(job_hash: str) -> dict:
        """Entfernt den gespeicherten Analyse-Befund einer Stelle (#1007).

        Für den Fall, dass das Urteil falsch war. Danach steht die
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

        Der Rückholweg für einen Verklicker. Rückholen ging schon
        immer (`stelle_reaktivieren`, Filter "Ausgeblendet") — was
        fehlte, war das WIEDERFINDEN: es gab keinen Zeitpunkt der
        Aussortierung, und `updated_at` taugt nicht dafür (die Spalte
        fasst jede Score-Neuberechnung an).

        Manuelle und automatische Aussortierungen stehen bewusst in
        EINER Liste — so hat der Nutzer es verlangt —, aber mit
        ausgewiesener Herkunft.

        Args:
            zeitfenster: 'heute', '7tage' (Standard), '30tage' oder 'alle'.
            limit: höchstens so viele Zeilen (Standard 50).
            herkunft: '' für beide, 'ich' oder 'automatik'.

        Stellen aus der Zeit vor v1.7.64 tragen keinen Zeitpunkt. Sie
        werden als solche ausgewiesen und erscheinen nur bei
        zeitfenster='alle' — `updated_at` als Ersatz einzusetzen wäre
        eine erfundene Angabe (#987).
        """
        from ..services import aussortier_protokoll as _protokoll
        befund = _protokoll.eintraege(db, zeitfenster=zeitfenster,
                                      limit=limit, herkunft_filter=herkunft)
        if "fehler" not in befund:
            befund["naechster_schritt"] = (
                "Zurückholen mit stelle_reaktivieren(job_hash).")
        return befund

    @mcp.tool()
    def stelle_reaktivieren(job_hash: str, grund: str = "") -> dict:
        """Reaktiviert eine zuvor aussortierte Stelle (#664).

        Setzt `is_active=1` und löscht `dismiss_reason`. Gegenstück zu
        `stelle_einordnen('passt_nicht')` — analog zu `dokument_reaktivieren()`
        für Dokumente. Notwendig wenn Claude oder der User eine Stelle
        irrtümlich aussortiert hat und sie wieder in der aktiven Liste
        haben möchte, ohne über den DB-Bypass zu gehen (#514).

        Args:
            job_hash: Hash der Stelle (8-Zeichen-Kurzform oder voll).
            grund: Optionaler Hinweis warum reaktiviert wird (z.B.
                "Irrtum — Firma nicht auf Blacklist"). Wird im Result
                zurückgegeben, nicht persistiert.
        """
        from ..services.typed_ids import strip_prefix
        h = strip_prefix(job_hash)
        target_hash = db.resolve_job_hash(h)
        if not target_hash:
            return {
                "fehler": "Stelle nicht gefunden. Prüfe den Hash mit stellen_anzeigen()."
            }
        job_before = db.get_job(target_hash)
        if not job_before:
            return {"fehler": "Stelle nicht gefunden."}

        war_aktiv = bool(job_before.get("is_active"))
        alter_grund = job_before.get("dismiss_reason") or ""

        if war_aktiv and not alter_grund:
            return {
                "status": "bereits_aktiv",
                "job_hash": _kurz(target_hash),
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
                    "entity_id": db._public_job_hash(target_hash),
                    "action": "reaktivieren",
                    "metadata": {"dismiss_reason": alter_grund,
                                 "titel": (job_before.get("title") or "")[:80],
                                 "nutzer_grund": grund or ""},
                })
            except Exception:
                logger.debug("Lernsignal fuer %s nicht protokolliert",
                             _kurz(target_hash))

        return {
            "status": "reaktiviert",
            "war_automatisch_aussortiert": war_automatik,
            "lernhinweis": (
                "Diese Stelle hatte die Automatik aussortiert. Die "
                "Rücknahme ist protokolliert — häuft sich das, steht "
                "die Regel zu scharf."
            ) if war_automatik else None,
            "job_hash": _kurz(target_hash),
            "titel": job_before.get("title", ""),
            "firma": job_before.get("company", ""),
            "vorheriger_dismiss_reason": alter_grund or None,
            "grund": grund or None,
            "hinweis": (
                "Stelle ist wieder aktiv und erscheint in stellen_anzeigen() "
                "+ fit_analyse(). Bei Bedarf erneut mit stelle_einordnen() "
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
        """Prüft ob eine Stelle ein "Wiedergaenger" ist (#671, Ebene 0, KI-frei).

        Ein Wiedergänger ist eine Stelle, die inhaltlich derselben Firma +
        Domäne entspricht, die bereits früher mehrfach mit demselben Grund
        aussortiert wurde — taucht aber unter neuem Hash (anderer Scrape/Quelle)
        wieder als "frischer Fund" auf. Beispiel: Firma X + Domäne "PLM" wurde
        schon 2x als `falsches_fachgebiet` verworfen.

        **Rein deterministisch (Ebene 0) — keine lokale KI nötig.** Das Feature
        funktioniert vollständig auch in Installationen ohne Ollama. Eine
        optionale Ollama-Verfeinerung (Ebene 1) und der Claude-Kontext in
        `fit_analyse` (Ebene 2) bauen darauf auf, sind aber nicht erforderlich.

        Args:
            job_hash: Optional. Hash der zu prüfenden Stelle — Firma/Titel
                werden daraus gelesen. Überschreibt firma/titel.
            firma: Firmenname (wenn kein job_hash gegeben).
            titel: Stellentitel (wenn kein job_hash gegeben).
            schwellwert: Ab wie vielen früheren Aussortierungen mit gleichem
                Grund als Wiedergänger gilt (Default 2).
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
                return {"fehler": "Stelle nicht gefunden. Prüfe Hash mit stellen_anzeigen()."}
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
                    "Keine ausreichende Aussortier-Historie für diese "
                    "Firma+Domäne/Rolle gefunden — als Neufund behandeln."
                ),
            }
            # v1.7.7 (#754/#757): Gibt es Historie zu ANDEREN Rollen der
            # Firma, kommt sie als neutrale Einordnung mit — kein k.o.
            from ..services.wiedergaenger import firmen_historie
            fh = firmen_historie(db, firma, target_hash=resolved_hash)
            if fh:
                antwort["firmen_historie"] = fh
                antwort["hinweis"] = (
                    "Kein Wiedergänger — die früheren Aussortierungen "
                    "dieser Firma betrafen andere Rollen/Domänen. "
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
                "Firma+Domäne. Wahrscheinlich erneut nicht passend — prüfen "
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

        ANTI-DB-BYPASS: Nutze dieses Tool für das Aussortieren grosser Mengen
        von Stellen. NIEMALS direkt in die SQLite-Datei schreiben — die
        PBP-Logik (Audit-Log, Lerneffekte, Auto-Adjust-Scoring,
        dismiss_reasons-Statistik) wird hier durchlaufen, bei direkten
        DB-Writes nicht.

        SICHERHEITS-DEFAULT: dry_run=True. Erst Vorschau (Anzahl Treffer +
        erste 10 Beispiele), dann mit dry_run=False ausführen. Das ist
        bewusst nicht verhandelbar — der Filter trifft sonst zu viel.

        REAL-CASE: Bei einer Suche kommen 500 Stellen, davon 200 falsches
        Fachgebiet. Anstatt 200 Einzelaufrufe von stelle_einordnen:

            stellen_bulk_bewerten(
                bewertung='passt_nicht',
                gruende=['falsches_fachgebiet'],
                titel_enthaelt_nicht=['Pflege', 'Vertrieb'],
                dry_run=True  # erst prüfen!
            )

        Args:
            bewertung: 'passt' oder 'passt_nicht'
            grund / gruende: wie bei stelle_einordnen. ABLEHNUNGSGRUENDE-Liste
                gilt analog. KI darf KEINE eigenen Gruende erfinden.
            dry_run: bei True (Default) wird NICHTS verändert, nur Preview.
                Bei False: alle Treffer werden tatsächlich bewertet.
            min_score / max_score: Score-Bereich (None = unbegrenzt)
            min_alter_tage / max_alter_tage: relativ zu found_at
            quelle: Quelle als String (z.B. 'bundesagentur')
            firma: Firmenname (case-insensitive Substring-Match)
            titel_enthaelt: AND-Liste — Titel muss ALLE Begriffe enthalten
            titel_enthaelt_nicht: NOR-Liste — Titel darf KEINEN davon enthalten
            beschreibung_enthaelt_nicht: NOR-Liste für Beschreibung —
                Hauptwerkzeug für Fachgebiets-Aussortierung
            max_treffer: harter Cap auf die Anzahl Treffer (0 = kein Limit).
                Sinnvoll wenn man nicht sicher ist wie weit der Filter trifft.

        v1.7.0-beta.74 (#646): Wall-Clock-Budget von 90 Sekunden. Falls
        ein Lauf länger braucht (z.B. weil _run_auto_refetch_descriptions
        parallel die DB sperrt), wird mit `status='timeout'` abgebrochen
        statt stumm zu hängen. Reduziere max_treffer oder warte bis der
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
                    "um stilles Hängen zu vermeiden."
                ),
            }

        # 1) Bewertung validieren
        if bewertung not in ("passt", "passt_nicht"):
            return {"fehler": "Ungültige Bewertung. Nutze 'passt' oder 'passt_nicht'."}

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
                    f"{len(matched)} Stellen würden bewertet werden. "
                    "Prüfe die Vorschau und rufe das Tool erneut mit dry_run=False auf, "
                    "um die Änderung tatsächlich anzuwenden."
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
                        f"Zeit-Budget ({_BULK_BUDGET_SEK}s) während Bulk-Apply "
                        f"erreicht. {bearbeitet} Stellen bearbeitet, "
                        f"{len(matched) - bearbeitet} unverarbeitet. Bei den "
                        "verbleibenden kann der nächste Aufruf weitermachen."
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
                "ist das die Folge der Scoring-Anpassung — für einen "
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
        nur_beurteilt: bool = False,
        ohne_schwelle: bool = False,
        gefunden_seit: str = ""
    ) -> dict:
        """Zeigt gefundene Stellenangebote an.

        Gibt die Liste der Stellen zurück, sortiert nach Score — Stellen
        mit fachlichem k.o. (Wiedergänger-Muster, #671) sinken dabei ans
        Ende, egal wie hoch ihr Score ist (v1.7.12, #827/C32): der Score
        misst Begriffe, das k.o.-Muster misst deine dokumentierten
        Entscheidungen. Nutze stelle_einordnen() um einzelne Stellen zu
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
                sehen will, soll sie nicht suchen müssen.
            ohne_schwelle: True zeigt für DIESEN Aufruf auch die Stellen
                unter deiner Score-Schwelle (#1082); sie tragen dann
                `unter_schwelle: true`. Die Einstellung selbst bleibt
                unverändert. Die Schwelle vergleicht den Fachwert —
                Entfernung, Remote und Gehalt blenden nie etwas aus.
            gefunden_seit: Datum YYYY-MM-DD — nur Stellen, die PBP an
                diesem Tag oder später gefunden hat (#1112, z. B. für
                einen Abgleich nur der neuen Stellen). Leer = alle.
        """
        # #1148: Seitenwerte unter 1 (oder keine Zahl) gaben eine rohe
        # Python-Meldung zurueck ("integer division or modulo by zero" bei
        # pro_seite=0). Jetzt eine brauchbare Seite — und die Korrektur steht
        # in der Antwort.
        _eingabe_korrigiert = []
        try:
            seite = int(seite)
        except (TypeError, ValueError):
            seite = 0
        if seite < 1:
            _eingabe_korrigiert.append(f"seite={seite} ist keine Seite — es gilt seite=1")
            seite = 1
        try:
            pro_seite = int(pro_seite)
        except (TypeError, ValueError):
            pro_seite = 0
        if pro_seite < 1:
            _eingabe_korrigiert.append(
                f"pro_seite={pro_seite} ist keine Anzahl — es gilt pro_seite=20")
            pro_seite = 20
        elif pro_seite > 50:
            _eingabe_korrigiert.append(f"pro_seite={pro_seite} ist zu gross — es gilt pro_seite=50")
            pro_seite = 50

        # #1112: das Funddatum als Filter. Verglichen wird der Tag, weil
        # found_at je nach Quelle mit oder ohne Zeitzone gespeichert ist.
        seit = (gefunden_seit or "").strip()
        if seit:
            from datetime import date as _date
            try:
                seit = _date.fromisoformat(seit[:10]).isoformat()
            except ValueError:
                return {"fehler": (f"gefunden_seit '{gefunden_seit}' ist kein Datum. "
                                   "Erwartet: YYYY-MM-DD, z. B. 2026-09-20.")}
        # v1.7.39 (#989): Datenguete einmal je Aufruf vorbereiten — die
        # Kriterien und die Nutzereinstellung sind fuer alle Zeilen
        # dieselben, und eine Netz- oder DB-Abfrage je Stelle waere
        # unbrauchbar (dasselbe Muster wie die Synonyme in #987).
        from ..services import datenguete as _dg
        _profil_fuer_analyse = db.get_profile()
        # v1.7.112 (#1051): die rohen Kriterien, gegen die der Stand eines
        # Urteils beim Speichern gebildet wird.
        _krit_fuer_stand = db.get_search_criteria()
        from ..services import scoring_kriterien as _skrit
        try:
            _guete_krit = _skrit.fuer_scoring(db)
            _guete_umgang = _dg.umgang(db)
        except Exception as exc:  # pragma: no cover — nie eine Liste stoppen
            logger.debug("Datenguete-Vorbereitung fehlgeschlagen: %s", exc)
            _guete_krit, _guete_umgang = {}, _dg.NACHRANGIG

        def _guete_rang(j):
            return _dg.sortierschluessel(j, _guete_umgang, _guete_krit)

        # v1.7.117 (#1052): die beiden Daumen, EINMAL vorbereitet. Der
        # Kontext traegt die Schwellen aus der eigenen Bewerbungs-
        # historie; je Zeile neu gerechnet waere das ein Bestandsscan
        # pro Stelle (dieselbe Bauform wie die Datenguete darueber).
        from ..services import indikatoren as _ind
        try:
            _daumen_ktx = _ind.kontext(db, _guete_krit)
        except Exception as exc:  # pragma: no cover — nie eine Liste stoppen
            logger.debug("Daumen-Kontext fehlgeschlagen (#1052): %s", exc)
            _daumen_ktx = {}

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
        if seit:
            jobs = [j for j in jobs if (j.get("found_at") or "")[:10] >= seit]

        # Apply scoring adjustments (#169)
        durch_schwelle_verborgen = 0
        # #1082 AK 4: Stellen, die die alte Regel (Schwelle gegen den
        # Wert samt Entfernung/Remote/Gehalt) verborgen haette.
        nur_durch_rahmen = 0
        if filter != "aussortiert":
            try:
                from ..services.scoring_service import apply_scoring_adjustments
                auto_ignored = 0
                scored_jobs = []
                # v1.7.147 (#1143): einmal lesen, nicht je Stelle — vorher
                # 11,6 s bei 1.200 Stellen und 100 Bewerbungen, auch mit
                # pro_seite=20, weil die Schleife vor dem Blaettern lief.
                try:
                    beworbene = db.get_applied_job_hashes()
                except Exception:
                    beworbene = None   # dann liest jede Stelle selbst nach
                for j in jobs:
                    result = apply_scoring_adjustments(
                        j, j.get("score", 0), db, beworbene=beworbene)
                    j["score"] = result["final_score"]
                    # v1.7.127 (#1082): der Fachwert ohne Rahmen-Regler —
                    # gegen ihn vergleichen Schwelle und Fachdaumen.
                    j["fach_score"] = result.get("fach_score", j["score"])
                    if result.get("nur_durch_rahmen_unter_schwelle"):
                        nur_durch_rahmen += 1
                    if result.get("ignored"):
                        # Nur die Schwelle darf fuer einen Aufruf
                        # aufgehoben werden; ein ausdrueckliches
                        # "ignorieren" an einem Regler gilt weiter.
                        if ohne_schwelle and result.get("unter_schwelle"):
                            j["unter_schwelle"] = True
                            scored_jobs.append(j)
                            continue
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
                from ..services.wiedergaenger import (
                    aussortierte_laden, find_wiedergaenger_pattern)
                # #1154: ohne Anzeigentexte; die Pruefung braucht nur deren Laenge.
                _dismissed_pool = aussortierte_laden(db)
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
                        "Ergebnis mit stelle_urteil_speichern an der Stelle "
                        "ablegen — oder ruf stellen_anzeigen() ohne "
                        "nur_beurteilt auf."),
                }
            if durch_schwelle_verborgen:
                # Es GIBT Stellen — sie liegen nur unter der Schwelle.
                # Eine Suche zu empfehlen waere der falsche Schritt.
                return {
                    "anzahl": 0,
                    "durch_schwelle_verborgen": durch_schwelle_verborgen,
                    "davon_allein_durch_rahmen": 0,
                    "nachricht": (
                        f"Keine Stelle über deiner Score-Schwelle — aber "
                        f"{durch_schwelle_verborgen} aktive Stelle(n) liegen "
                        "darunter und werden deshalb nicht angezeigt. Das ist "
                        "ein Filter, kein leerer Markt."),
                    "naechster_schritt": (
                        "Für diesen Aufruf alle zeigen: stellen_anzeigen("
                        "ohne_schwelle=True). Die Schwelle dauerhaft "
                        "aendern: schwelle_stufe_setzen(bereich='liste', "
                        "stufe=...). Über stellen_anzeigen(min_score=0) "
                        "kommen sie NICHT zurück — die Schwelle wirkt davor."),
                    "schwelle_vergleicht": _SCHWELLE_VERGLEICHT,
                }
            # v1.7.147 (#1146): War ein Filter gesetzt, ist "Keine Stellen
            # gefunden. Starte eine Jobsuche" falsch und schickt den Menschen
            # in die falsche Richtung. Es GIBT Stellen, nur keine fuer diesen
            # Filter. Dieselbe Haltung wie bei Schwelle und Urteil darueber.
            _filter_woerter = []
            if quelle:
                _filter_woerter.append(f"Quelle „{quelle}“")
            if min_score > 0:
                _filter_woerter.append(f"mindestens {min_score} Punkte")
            if max_alter_tage > 0:
                _filter_woerter.append(f"nicht älter als {max_alter_tage} Tage")
            if seit:
                _filter_woerter.append(f"gefunden seit {seit}")
            if nur_nicht_beworben:
                _filter_woerter.append("nur noch nicht beworben")
            if nur_empfohlen:
                _filter_woerter.append("ohne Stellen mit k.o.-Muster")
            if _filter_woerter and filter != "aussortiert":
                _aktive = db.get_active_jobs(exclude_blacklisted=True)
                if _aktive:
                    _quellen = sorted({(j.get("source") or "unbekannt") for j in _aktive})
                    return {
                        "anzahl": 0,
                        "aktive_stellen_gesamt": len(_aktive),
                        "quellen_im_bestand": _quellen,
                        "nachricht": (
                            f"Keine Stelle für diesen Filter ({', '.join(_filter_woerter)}) — "
                            f"ohne Filter gibt es {len(_aktive)} aktive Stelle(n). "
                            "Das ist ein Filter, kein leerer Bestand."),
                        "naechster_schritt": (
                            "Filter lockern oder weglassen: stellen_anzeigen() "
                            "zeigt alle aktiven Stellen; bei „quelle“ gelten die "
                            "Namen aus quellen_im_bestand."),
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
        # C96 (#1087 C1): dieselben Punkte wie Stellen-Tab, Dashboard,
        # Timeline und Fit-Dialog. `score` traegt denselben Wert, damit
        # Claude nicht zwei Zahlen fuer eine Stelle nennt; die Reihenfolge
        # richtet sich weiter nach dem Wert samt Rahmen (#1082).
        from ..services import punkte as _punkte
        _punkte.anreichern(db, page_jobs)
        for j in page_jobs:
            entry = {
                "id": _kurz(j["hash"]),  # #171: Kurz-ID fuer schnelle Referenz
                "hash": j["hash"],
                # H31 (#1087 G13): der Weg zurueck ins Dashboard.
                "dashboard_link": _dashboard_link("stellen", j["hash"]),
                "titel": j.get("title", ""),
                "firma": j.get("company", ""),
                "ort": j.get("location", ""),
                "score": j.get("punkte", j.get("score", 0)),
                "punkte": j.get("punkte", 0),
                "punkte_text": _punkte.text(j.get("punkte", 0), j.get("punkte_max")),
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
                # gelesen und ist eine Luftlinie. Seit v1.7.94 kennt der
                # Befund auch die Fahrstrecke, deshalb die ganze Stelle.
                entry.update(_entfernung.befund(j, _krit_fuer_stand))
            # v1.7.140 (#954): woher die Werte kommen — eine Zeile, nur
            # was nicht belegt ist. Die volle Aufstellung hat fit_analyse.
            try:
                from ..services import wahrheit as _wahrheit
                entry["herkunft"] = _wahrheit.kurz(
                    _wahrheit.felder(j, _krit_fuer_stand))
            except Exception:  # pragma: no cover — nie eine Liste stoppen
                pass
            # v1.7.22 (#942): Fach- und Rahmenanteil getrennt ausweisen.
            # "Score 31" allein verraet nicht, ob die Punkte fachlich
            # sind oder aus Rahmenbegriffen (Senior, Remote, Hamburg)
            # stammen. Mit der Aufteilung ist ein Fehlgriff auf einen
            # Blick erkennbar.
            if j.get("fachscore") is not None:
                entry["fachscore"] = j.get("fachscore")
                entry["rahmenscore"] = j.get("rahmenscore")
            # v1.7.117 (#1052): Fachwert und Rahmen als zwei Daumen mit
            # Richtung und Farbe. Es gibt KEINE Summe aus beiden — sie
            # beantworten verschiedene Fragen, und die Zusammenfassung
            # in eine Zahl war der Anlass des Issues.
            _marken = _ind.fuer_stelle(j, _daumen_ktx)
            if _marken.get("fach"):
                entry["fach_daumen"] = _marken["fach"]
            if _marken.get("rahmen"):
                entry["rahmen_daumen"] = _marken["rahmen"]
            if _marken.get("fach_maximum"):
                entry["fach_maximum"] = _marken["fach_maximum"]
            # v1.7.127 (#1082): der Wert, gegen den die Schwelle haelt,
            # und ob die Stelle darunter liegt (nur mit ohne_schwelle).
            if j.get("fach_score") is not None:
                entry["fach_score"] = j["fach_score"]
            if j.get("unter_schwelle"):
                entry["unter_schwelle"] = True
            # v1.7.127 (#1084): ein Wiederfund steht am Master.
            try:
                from ..services import stellen_grabstein as _grab
                _wieder = _grab.erneut_gesehen(
                    db, db.resolve_job_hash(j["hash"]) or j["hash"])
                if _wieder:
                    entry["erneut_gesehen"] = _wieder
            except Exception as _e:  # pragma: no cover
                logger.debug("Wiederfund (#1084): %s", _e)
            try:
                from ..services import standorte as _standorte
                _weiterer = _standorte.naechster(
                    j, _daumen_ktx.get("kriterien") or {})
                if _weiterer:
                    entry["naechster_standort"] = _weiterer
            except Exception as _e:  # pragma: no cover
                logger.debug("Standorte (#1082): %s", _e)
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
            _befund = passung.analyse_lesen(
                j, _profil_fuer_analyse, _krit_fuer_stand)
            if _befund:
                entry["analyse"] = _befund
            # #948 (G42): der Pruefstand ist eine ANDERE Auskunft als das
            # Urteil. Er steht auch dann da, wenn kein Urteil vorliegt —
            # "angesehen, aber nicht beurteilt" ist der Zustand, in dem
            # Arbeit verlorenging.
            entry["pruefstand"] = passung.zustand(
                j, _profil_fuer_analyse, _krit_fuer_stand)
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
                        f"('{_kurz(j['hash'])}'), dann entscheiden."
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
                # v1.7.143 (#1126): dieselbe Frage wie im Dashboard - ueber
                # EINE Funktion, samt Vermittler-Bewerbungen (#1076).
                from ..services import bewerbungs_hinweis as _bh
                _repost = _bh.fuer_stelle(j, _alle_bewerbungen, db=db)
                if _repost:
                    entry.update(_bh.als_felder(_repost))

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
                    "Ansprechpartner. So ist keine Bewerbung möglich."
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
        if _eingabe_korrigiert:
            result["eingabe_korrigiert"] = _eingabe_korrigiert
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
                "dieser Liste. Sie sind nicht aussortiert — nur gefiltert. "
                "Alle zeigen: stellen_anzeigen(ohne_schwelle=True).")
            # v1.7.127 (#1082) AK 4: wie viele davon liegen allein durch
            # den Rahmen darunter? Seit dieser Version keine — und das
            # gehoert gesagt, denn genau so war die Vermutung.
            result["davon_allein_durch_rahmen"] = 0
            result["schwelle_vergleicht"] = _SCHWELLE_VERGLEICHT
        if nur_durch_rahmen:
            # Die Gegenrichtung: sichtbar, obwohl der Wert samt Rahmen
            # unter der Schwelle liegt. Bis v1.7.126 fehlten genau diese.
            result["durch_rahmen_nicht_mehr_verborgen"] = nur_durch_rahmen
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
                "Bestand heilen (Expertenmodus): stellen_urls_heilen(dry_run=True) trägt "
                "wo möglich eine Such-URL nach; den Rest per "
                "stelle_bearbeiten(url=...) oder Kontakt ergänzen."
            )
        if filter == "aktiv":
            result["hinweis"] = (
                "Nutze stelle_einordnen(hash, 'passt') oder stelle_einordnen(hash, 'passt_nicht', 'Grund') "
                "um Stellen zu bewerten. Für Details: fit_analyse(hash). "
                f"Nächste Seite: stellen_anzeigen(seite={seite+1})" if seite * pro_seite < total else
                "Nutze stelle_einordnen(hash, 'passt') oder stelle_einordnen(hash, 'passt_nicht', 'Grund') "
                "um Stellen zu bewerten. Für Details: fit_analyse(hash)."
            )
        return result

    @mcp.tool()
    def google_jobs_url(
        keyword: str,
        zeitraum: str = "woche",
        ort: str = "",
    ) -> dict:
        """Baut eine Google-Jobs-URL für Chrome-in-Claude (#501, #573).

        Google Jobs (`udm=8`) ist der grösste Aggregator in DE und
        indexiert u.a. StepStone-Stellen. Ein direkter HTTP-Abruf wird
        von Google zuverlässig blockiert, ein eingeloggter Chrome-Tab
        mit Claude-in-Chrome funktioniert aber stabil.

        Workflow (v1.7.0-beta.14, #573):
        1. `google_jobs_url(keyword="PLM", ort="Hamburg")` aufrufen
        2. URL im Browser mit der Claude-Erweiterung öffnen
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
        # v1.7.122 (#1067): das Auswerte-Skript ist am sichtbaren TEXT
        # verankert, nicht an Klassennamen. Die alte Fassung (Stand Mai
        # 2026) traf am 21.09.2026 nur noch die Suchreiter und lieferte
        # 13 "Stellen" namens KI-Modus, Bilder, News — ohne Fehler.
        from ..job_scraper.google_jobs import extraction_js as _extraction
        from ..services.weiterverbreiter import WEITERVERBREITER
        extraction_js = _extraction()
        return {
            "url": url,
            "extraction_js": extraction_js,
            # #1120: dieselbe Liste wie beim Alert-Import. Ein Treffer
            # "über" eine dieser Seiten ist eine Kopie.
            "weiterverbreiter": sorted(WEITERVERBREITER),
            "weiterverbreiter_hinweis": (
                "Steht `portal` in `weiterverbreiter` (Groß- und Kleinschreibung "
                "egal), ist der Treffer eine "
                "Kopie: das Datum ist nicht das Veröffentlichungsdatum, und "
                "Ort oder Titel können abweichen. Das Original beim "
                "Arbeitgeber suchen und das übernehmen."
            ),
            "hinweis": (
                "Öffne diese URL im Browser mit der Claude-Erweiterung und "
                "führe `extraction_js` mit javascript_tool() aus. Pro "
                "Treffer kommen titel, firma, ort, portal und (wenn "
                "auffindbar) link — `portal` sagt, über welche Quelle die "
                "Stelle läuft, und taugt für den Dublettenabgleich. "
                "Meldet das Skript ein `fehler`-Feld, NICHT die Liste "
                "uebernehmen: dann hat sich die Seitenstruktur geaendert, "
                "und das gehört als Issue gemeldet. Google lädt weitere "
                "Karten erst beim Scrollen nach."
            ),
        }

    @mcp.tool()
    def umgang_mit_unbekannt_setzen(modus: str = "") -> dict:
        """Wie soll PBP mit UNGEPRUEFTEN Angaben umgehen? (#989)

        Wo eine Information fehlt, setzt ein Punktesystem einen neutralen
        Wert ein — und neutral heisst dort nicht "unbekannt", sondern
        "kostet nichts". Was nichts kostet, steigt in der Sortierung. Am
        07.09.2026 stand deshalb ein inhaltsleerer Titel mit 101 Punkten
        über einer vollständig beschriebenen, fachlich passenden Stelle
        mit 32.

        Ob das ein Problem ist, hängt vom eigenen Kriterium ab — wer
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

        Das MUSS-Tor entscheidet, ob eine Anzeige überhaupt in Frage
        kommt. Trifft kein einziger Pflichtbegriff, wird sie bisher
        verworfen — sie wird gar nicht erst gespeichert. Im
        dokumentierten Lauf aus #813 starben so 312 von 389
        Rohtreffern, bevor ein Mensch sie gesehen hat.

        Ob das richtig ist, hängt daran, WAS deine Pflichtbegriffe
        nennen:

        * **Techniken** ("PLM", "SAP", "Python") — ihr Fehlen ist ein
          echter Beleg: die Anzeige gehört in ein anderes Fachgebiet.
          Dafür ist `hart` richtig.
        * **einen Beruf** ("Pflegefachkraft", "Erzieherin") — ihr
          Fehlen sagt wenig, weil derselbe Beruf in vielen Anzeigen
          anders heisst. Dafür ist `gewichtet` richtig.

        **Du musst hier nichts einstellen.** In der Vorgabe
        `automatisch` entscheidet PBP anhand deiner Pflichtbegriffe
        selbst — an derselben gemessenen Schwelle, die seit v1.7.36 die
        Alternativbezeichnungen absichert. Dieses Werkzeug zeigt die
        Entscheidung samt Begruendung und lässt sie überstimmen.

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
                    "('hart'); zurück zur Ableitung mit "
                    "('automatisch'). Betroffene Stellen tragen in "
                    "stellen_anzeigen die Marke 'muss_tor'."),
            }
        return mt.modus_setzen(db, betriebsart.strip().lower())

    @mcp.tool()
    def scores_neu_berechnen(
        nur_aktive: bool = True,
        max_stellen: int = 0,
    ) -> dict:
        """Rechnet die Punkte aller (aktiven) Stellen neu (#554, v1.6.9).

        Sinnvoll nach Änderungen an:
        - Suchkriterien (`suchkriterien_setzen`/`suchkriterien_bearbeiten`)
        - Profil (relevante Skills, Wunsch-Gehalt, Standort)
        - Scoring-Regler (`scoring_konfigurieren`)
        - Geocoding-Cache (Standort-Änderungen)

        Geht jede Stelle einmal durch `calculate_score()` und persistiert
        den neuen Wert via `db.update_job(hash, {"score": ...})`. Auto-
        Adjust-Hooks werden NICHT getriggert — das ist ein reiner Recompute.

        Args:
            nur_aktive: True (Standard) = nur is_active=1; False = auch aussortierte.
            max_stellen: 0 = unbegrenzt, sonst harter Cap (sinnvoll für Tests).
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

        from ..services.neu_bewerten import neu_bewerten
        return neu_bewerten(db, jobs, criteria)

    @mcp.tool()
    def suchperformance_auswerten() -> dict:
        """Welche Quelle führt tatsächlich zu Bewerbungen? (#783/B28, v1.7.10)

        Wertet die KOMPLETTE Kette rückwirkend aus Bestandsdaten aus:
        gefunden -> aussortiert (mit Top-Gründen) -> beworben -> Interview/
        Angebot, je Quelle. Die eigentliche Kennzahl ist die BEWERBUNGSQUOTE
        pro Quelle, nicht die Trefferzahl — eine Quelle mit 7 Treffern und
        2 Bewerbungen schlägt eine mit 100 Treffern und 0.

        Ehrliche Grenze (v1.7): Auswertung auf QUELLEN-Ebene. Die Ebene
        einzelner Such-Queries braucht eine Lauf-Protokollierung
        (search_runs) — das ist der v1.8-Teil von #783; die Beta-Linie
        führt mit `scraper_runs` (B25/#735) bereits eine Lauf-Historie.
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
                "für die Deaktivierung — aber Vorschlag, keine Automatik: "
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

        Auch findbar als: Schwellenwert vorschlagen, neuen Schwellenwert
        vorschlagen lassen (Dashboard-Hinweis), Score-Schwelle kalibrieren.

        Prüft, wie die AKTUELLEN Kriterien die Vergangenheit bewertet
        haetten: Score-Verteilung der Stellen, auf die tatsächlich beworben
        wurde (positive Labels), gegen eine Zufallsstichprobe der
        Aussortierten (negative Labels). Liefert einen Schwellen-Vorschlag
        (niedrigster Bewerbungs-Score x 0,8) und warnt, wenn historische
        Bewerbungen unter der aktuellen `min_score_schwelle` lägen.

        ⛔ GARANTIE: Reine SCHATTENRECHNUNG. Dieses Tool ruft NIEMALS
        scores_neu_berechnen auf und schreibt keinen einzigen Score in die
        jobs-Tabelle — egal welche Parameter. Der dry_run-Parameter
        existiert nur der Konvention wegen; es gibt keinen Schreibmodus.

        Nutzung nach jeder Kriterienaenderung: erst Backtest ansehen,
        dann entscheiden, dann (separat) scores_neu_berechnen().

        Args:
            stichprobe_dismissed: Grösse der Zufallsstichprobe aussortierter
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
        # v1.7.117 (#1052): steht noch eine Schwelle aus der Zeit vor der
        # Trennung? Dann gehoert die Einordnung genau hierher — das ist
        # der Knopf, auf den der Hinweis zeigt. Gerechnet wird der Lauf
        # von oben weiter, nicht ein zweiter.
        from ..services import schwellen_umstellung as _su
        if (_su.offen(db).get("betroffen")
                and "aktuell" in (result.get("varianten") or {})):
            result["schwelle_nach_umstellung"] = _su.vorschlag(
                db, ergebnis=result)
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

        LinkedIn blockiert automatisierte Zugriffe zuverlässig.
        Nutze stattdessen Claude-in-Chrome Extension:
        1. Öffne LinkedIn im Chrome-Browser mit Claude-in-Chrome
        2. Suche manuell nach Stellen
        3. Übertrage gefundene Stellen mit stelle_manuell_anlegen()

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
                "LinkedIn blockiert automatisierte Zugriffe zuverlässig. "
                "Nutze stattdessen: 1) Claude-in-Chrome Extension öffnen, "
                "2) LinkedIn manuell durchsuchen, "
                "3) Stellen mit stelle_manuell_anlegen() übertragen."
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
            "Die Beschreibung enthält vermutlich redaktionelle Notizen "
            f"(erkannt an: {', '.join(sorted(treffer)[:3])}), die NICHT "
            "durch eine '---'-Zeile vom Anzeigentext getrennt sind. "
            "Solche Notizen zählen dann ins Scoring — ein Ausschluss-"
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

        Der Weg für alles, was PBP nicht selbst gefunden hat: eine Stelle
        aus dem Browser, aus einer Mail, aus einem Gespräch. Prüft
        Blacklist (#729/#790/#992), Duplikate (#317/#567/#670) und den
        Anker (#766), berechnet den Score und legt an.

        Args:
            titel: Stellentitel (Pflicht).
            firma: Firmenname (Pflicht).
            url: Link zur ORIGINAL-Ausschreibung (Detailseite, keine
                Suchergebnis-URL — #645/#763).
            ort: Arbeitsort.
            beschreibung: Anzeigentext. Je vollständiger, desto
                belastbarer der Score; unter 50 Zeichen gilt die Stelle
                als unbewertet (#756/#989).
            quelle: Herkunft ('linkedin', 'xing', 'firmenwebsite', ...).
            remote: 'remote' | 'hybrid' | 'vor_ort' | 'unbekannt'.
            stellenart: 'festanstellung' | 'freelance' | 'praktikum' |
                'werkstudent'.
            force: True = erkanntes Duplikat/Blacklist ignorieren (#670).
            kontakt_name: Ansprechpartner — wird als Kontakt angelegt und
                mit der Stelle verknüpft (Anker #766).
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
                    "Wenn diese Firma grundsätzlich unerwünscht ist, aber "
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
            # v1.7.111 (#1046): mit dem Zustand der vorhandenen Stelle. Bis
            # hierher stand hier nur "existiert bereits (Hash: ...)", und
            # im belegten Lauf wurde daraus vorgeschlagen, zwei Stellen
            # auszusortieren, die laengst aussortiert waren. Aktiv,
            # aussortiert und beworben verlangen drei verschiedene Schritte.
            from ..services import stellen_zustand as _zustand
            _block = _zustand.zustand(db, existing_job)
            return {
                "warnung": _zustand.schluessel(_block),
                "duplikat": _zustand.schluessel(_block),
                "status": "bereits_vorhanden",
                "grund": "gleiche_kennung",
                "nachricht": _zustand.nachricht(_block),
                "existing_hash": _block["hash"],
                "vorhandene_stelle": _block,
            }

        # Duplikat-Pruefung (#317 + #471 + v1.6.9 #567: zweistufig)
        # Stufe A: laufende Bewerbung mit Titel-Match → blocken
        # Stufe B: identische AKTIVE Stelle → idempotent vorhandenen Hash zurueck
        # Stufe C: aussortierte/abgelehnte Eintraege blocken NICHT mehr
        from ..duplicate_detection import find_duplicate_job

        # v1.6.9 (#567): nur LAUFENDE Bewerbungen blocken — abgeschlossene
        # (abgelehnt/abgelaufen/zurueckgezogen/angenommen) sind kein Hindernis
        # fuer eine neue Bewerbung bei der gleichen Firma auf eine andere Stelle.
        # #1103: aus der gemeinsamen Quelle (auch `arbeitgeber_ausgefallen`).
        from ..services.bewerbung_status import laeuft as _laeuft
        all_apps = db.get_applications()
        running_apps = [a for a in all_apps if _laeuft(a.get("status"))]

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
            from ..services import stellen_zustand as _zustand
            return {
                "warnung": "duplikat_bewerbung",
                # #1046: derselbe Zustandsblock wie bei gleicher Kennung.
                "duplikat": "duplikat_beworben",
                "vorhandene_stelle": {
                    "titel": app.get("title") or "",
                    "firma": app.get("company") or "",
                    **_zustand.aus_bewerbung(app)},
                "grund": app_hit["grund"],
                "nachricht": (
                    f"Mögliches Duplikat: laufende Bewerbung {app['id'][:8]} bei "
                    f"{app.get('company')} (Status: {app.get('status', 'unbekannt')}, "
                    f"Titel: '{app.get('title')}'). "
                    f"Match-Grund: {app_hit['grund']}"
                    + (f", gemeinsame Tokens: {app_hit.get('shared_tokens')}"
                       if app_hit.get("shared_tokens") else "")
                    + ". Die Stelle wurde NICHT angelegt. "
                    "Falls es sich tatsächlich um eine andere Stelle handelt, "
                    "ergänze den Titel eindeutig (z.B. Projekt- oder Team-Name) "
                    "oder nutze stelle_mergen(), falls eine früher angelegte "
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
            # #1046: auch hier der Zustand — die aktive Liste traegt
            # beworbene Stellen mit (`exclude_applied=False`), und eine
            # Bewerbung verlangt eine Warnung, keinen Hinweis.
            from ..services import stellen_zustand as _zustand
            _block = _zustand.zustand(db, existing)
            return {
                "warnung": "duplikat_aktive_stelle",
                "duplikat": _zustand.schluessel(_block),
                "vorhandene_stelle": _block,
                "naechster_schritt": _zustand.nachricht(_block),
                "status": "bereits_vorhanden",
                "grund": active_hit["grund"],
                "nachricht": (
                    f"Identische aktive Stelle existiert bereits: "
                    f"'{existing.get('title')}' bei {existing.get('company')} "
                    f"(Quelle: {existing.get('source', 'unbekannt')}, "
                    f"Hash: {existing['hash']}). Es wird der vorhandene Hash "
                    "zurückgegeben — kein Duplikat in der DB."
                ),
                "hash": existing["hash"],
                "existing_hash": existing["hash"],
                "shared_tokens": active_hit.get("shared_tokens"),
            }
        # Stufe A2 — ABGESCHLOSSENE Bewerbung auf dieselbe Stelle (#1065).
        #
        # #567 hat abgeschlossene Bewerbungen bewusst aus Stufe A genommen,
        # damit eine ANDERE Stelle bei derselben Firma nicht blockiert wird.
        # Richtig — nur fand fuer sie danach gar keine Pruefung mehr statt,
        # auch bei identischem Titel. Gemeldet mit zwei Faellen: Stellen zu
        # abgelehnten Bewerbungen wurden ohne jeden Hinweis als neu angelegt,
        # und erst das Aussortieren meldete das Duplikat.
        #
        # Es wird NICHT geblockt (das waere #567 rueckwaerts) und keine
        # vierte Regel gebaut: `find_repost_of_application` (#782) stellt
        # genau diese Frage schon, mit derselben Regel wie Stufe A, und
        # `stellen_anzeigen` und `fit_analyse` zeigen ihr Ergebnis laengst.
        # Die Anlage hat sie nur nie gefragt — dieselbe Bauform wie #994.
        wiedergaenger_bewerbung = None
        try:
            from ..duplicate_detection import find_repost_of_application
            # v1.7.143 (#1117): MIT der URL. Eine zeichengleiche Adresse zu
            # einer abgelehnten Bewerbung ist derselbe Beleg, der beim
            # Aussortieren laengst greift (`grund: url_match`) - nur wurde
            # er hier nie gefragt, weil die Erkennung ohne URL aufgerufen
            # wurde. Dieselbe Funktion, kein Nachbau; ein Repost mit neuer
            # URL wird weiter ueber Firma und Titel erkannt.
            wiedergaenger_bewerbung = find_repost_of_application(
                {"hash": job_hash, "title": titel, "company": firma,
                 "url": url},
                [a for a in all_apps if not _laeuft(a.get("status"))], db=db)
        except Exception as exc:  # pragma: no cover — nie die Anlage kippen
            # Sichtbar statt debug: hier verschwand ein NameError still,
            # und mit ihm der Hinweis auf eine abgelehnte Bewerbung.
            logger.warning("Wiedergaenger-Pruefung (#1065) fehlgeschlagen: %s", exc)

        # Stufe D — v1.7.126 (#1076): dieselbe Vakanz auf zwei Wegen, die
        # A und B nicht sehen. Ein Repost unter NEUEM Titel (verglichen wird
        # der Anzeigentext ohne Firmen-Textbausteine) und eine laufende
        # Bewerbung ueber einen Vermittler, bei der diese Firma der
        # Endkunde ist. Beides wird gemeldet, nicht geblockt.
        repost_verdacht = None
        vermittler_bewerbung = None
        laufende_bewerbung_verdacht = None
        try:
            from ..duplicate_detection import (
                find_inhalt_repost, find_vermittler_bewerbung)
            # Kandidaten ueber das erste Wort des Namens holen: `LIKE
            # %firma%` faende "Muster AG" nicht unter "Muster AG & Co. KG".
            # Den genauen Vergleich macht die Normalisierung.
            _kern = next((w for w in re.split(r"[\s,(]+", firma or "")
                          if len(w) >= 4), firma)
            _treffer = find_inhalt_repost(
                firma, titel, beschreibung, db.get_company_jobs(_kern),
                own_hash=job_hash)
            if _treffer:
                _alt = _treffer["job"]
                repost_verdacht = {
                    "hash": _alt.get("hash"),
                    "titel": _alt.get("title") or "",
                    "aktiv": bool(_alt.get("is_active")),
                    "aehnlichkeit_text": _treffer["aehnlichkeit"],
                    "hinweis": (
                        f"Möglicher Repost von '{_alt.get('title')}' "
                        f"({(_alt.get('hash') or '').split(':')[-1][:12]}): "
                        "Titel geaendert, Anzeigentext weitgehend gleich. "
                        "Gleiche Vakanz? Dann stelle_mergen()."),
                }
            # Zweiter Fall aus #1076: Stufe A vergleicht MIT URL, und bei
            # abweichender URL gilt die strenge Schwelle aus #670. Die
            # Repost-Erkennung in `fit_analyse` vergleicht ohne URL — und
            # meldete deshalb gleich danach, was die Anlage uebersah.
            # Dieselbe Frage, dieselbe Regel: hier als Hinweis, denn
            # Stufe A blockt, und das soll sie nur bei der strengen Regel.
            if not uebersteuerter_verdacht:
                _lb = find_duplicate_job(firma, titel, "", running_apps)
                if _lb:
                    _app = _lb["job"]
                    laufende_bewerbung_verdacht = {
                        "bewerbung_id": (_app.get("id") or "")[:8],
                        "titel": _app.get("title") or "",
                        "firma": _app.get("company") or "",
                        "status": _app.get("status") or "",
                        "grund": _lb["grund"],
                        "hinweis": (
                            f"Laufende Bewerbung {(_app.get('id') or '')[:8]} "
                            f"('{_app.get('title')}') passt zu dieser Stelle. "
                            "Gleiche Vakanz, neu ausgeschrieben? Dann "
                            "stelle_mergen() statt einer zweiten Stelle."),
                    }
            _vb = find_vermittler_bewerbung(firma, running_apps)
            if _vb:
                vermittler_bewerbung = {
                    "bewerbung_id": (_vb.get("id") or "")[:8],
                    "firma_der_bewerbung": _vb.get("company") or "",
                    "titel": _vb.get("title") or "",
                    "status": _vb.get("status") or "",
                    "hinweis": (
                        f"Laufende Bewerbung {(_vb.get('id') or '')[:8]} ueber "
                        f"'{_vb.get('company')}' nennt {firma} als Endkunden. "
                        "Prüfen, ob dies dieselbe Stelle ist — sonst landet "
                        "eine zweite Bewerbung am Vermittler vorbei beim "
                        "selben Arbeitgeber."),
                }
        except Exception as exc:  # pragma: no cover — nie die Anlage kippen
            logger.debug("Repost-/Vermittler-Pruefung (#1076): %s", exc)

        # Stufe C: alles andere (auch aussortierte Stellen bei gleicher Firma)
        # darf durchgehen.

        # v1.7.112 (#1051): dasselbe Nadeloehr wie Suchlauf, Neuberechnung
        # und `fit_analyse`. Mit den rohen Kriterien fehlte die abgeleitete
        # Betriebsart des MUSS-Tors (#968) — eine Stelle ohne Pflichttreffer
        # wurde hier mit 0 gespeichert, und `fit_analyse` rechnete gleich
        # danach 3.5. Der Docstring von `fuer_scoring` nannte die manuelle
        # Anlage laengst als Aufrufer; sie war es nicht.
        from ..services import scoring_kriterien as _skrit_anlage
        criteria = _skrit_anlage.fuer_scoring(db)
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

        # Score: erst unmittelbar vor dem Speichern (v1.7.94, #1034) — er liest
        # Gehalt und Entfernung, und beide entstehen erst darunter.

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
                        # v1.7.94 (#950): Koordinaten und, mit
                        # Routing-Schluessel, die echte Fahrstrecke —
                        # derselbe Weg wie im Suchlauf.
                        from ..services.geocoding_service import geocode_location
                        from ..services import routing as _routing
                        _koord = geocode_location(ort)
                        if _koord:
                            job["lat"], job["lon"] = _koord
                            if _routing.aktiv(db):
                                _routing.fuer_stellen(db, [job], user_coords)
            except Exception:
                pass

        job["score"] = calculate_score(job, criteria)
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
            "id": _kurz(job_hash),
            "hash": job_hash,
            "score": job["score"],
            "nachricht": f"Stelle '{titel}' bei {firma} angelegt (Score: {job['score']}, Quelle: {quelle}). "
                         f"Bewerte mit stelle_einordnen('{_kurz(job_hash)}', 'passt'/'passt_nicht').",
        }
        if job.get("distance_km"):
            result.update(_entfernung.befund(job, criteria))
        # v1.7.140 (#954): was an der neuen Stelle belegt ist und was nicht.
        try:
            from ..services import wahrheit as _wahrheit
            _gespeichert = db.get_job(job_hash) or job
            result["herkunft"] = _wahrheit.felder(_gespeichert, db.get_search_criteria())
            result["herkunft_kurz"] = _wahrheit.kurz(result["herkunft"])
        except Exception:  # pragma: no cover
            pass
        # #1065: angelegt, aber benannt. Eine erneut ausgeschriebene, schon
        # abgesagte Stelle ist ein anderer Fall als ein frischer Treffer —
        # und wer es nicht beim Anlegen erfaehrt, erfaehrt es gar nicht.
        if wiedergaenger_bewerbung:
            result["warnung"] = "wiedergaenger_bewerbung"
            result["bewerbung_vorher"] = wiedergaenger_bewerbung
        # #1076: eigene Felder, damit keine Warnung eine andere verdeckt.
        if repost_verdacht:
            result["repost_verdacht"] = repost_verdacht
            result.setdefault("warnung", "repost_verdacht")
        if vermittler_bewerbung:
            result["vermittler_bewerbung"] = vermittler_bewerbung
            result.setdefault("warnung", "vermittler_bewerbung")
        if laufende_bewerbung_verdacht:
            result["laufende_bewerbung_verdacht"] = laufende_bewerbung_verdacht
            result.setdefault("warnung", "laufende_bewerbung_verdacht")
        # #733: Wenn die Quelle 'manuell' geblieben ist (keine erkannte URL),
        # den Aufrufer aktiv erinnern, die echte Herkunft zu setzen — sonst
        # verfaelschen KI-gesteuerte Chrome-Adds die Quellenstatistik
        # ("18 Stellen manuell", obwohl keine von Hand angelegt wurde).
        if quelle == "manuell":
            result["hinweis"] = (
                "quelle='manuell' gesetzt. Wenn die echte Herkunft bekannt "
                "ist (z.B. 'linkedin', 'xing', 'firmenwebsite'), bitte den "
                "Parameter quelle entsprechend setzen — sonst zählt die "
                "Stelle fälschlich als manuell angelegt. Bei bekannter URL "
                "wird die Quelle automatisch abgeleitet (#613/#733)."
            )
        # v1.7.0-beta.87 (#670): wenn ein Duplikat-Verdacht via force=True
        # uebersteuert wurde, transparent im Result melden.
        if uebersteuerter_verdacht:
            result["duplikat_uebersteuert"] = uebersteuerter_verdacht
            result["nachricht"] += (
                " HINWEIS: Es bestand ein Duplikat-Verdacht "
                f"({uebersteuerter_verdacht['grund']}), der per force=True "
                "übersteuert wurde."
            )
        # #762: Ohne Detail-URL ist stellenbeschreibung_nachladen blockiert
        # ("Stelle hat keine URL") — und genau das Nachladen macht aus dem
        # schwachen Kurztext-Score erst einen belastbaren. Aktiv darauf hinweisen.
        if not url:
            result["url_hinweis"] = (
                "Keine URL angegeben — stellenbeschreibung_nachladen() kann die "
                "Anzeige später nicht holen. Wenn die Detail-URL der Anzeige "
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
                "einfügen) wird er aussagekräftig."
            )
        # #436: Warnung wenn URL auf Suchergebnis-Seite zeigt
        from ..job_scraper import is_search_result_url
        if url and is_search_result_url(url):
            result["url_warnung"] = (
                "Die angegebene URL zeigt auf eine Suchergebnis-Seite, nicht auf die "
                "konkrete Stellenanzeige. Die Stelle wurde trotzdem angelegt, aber der "
                "Link wird zur Such-Seite zurückführen. Falls möglich die Detail-URL "
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
                    f"Firma steht auf der Blacklist, der Titel enthält aber "
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
        """Der erprobte LinkedIn-Weg als ausführbarer Plan (#919).

        Der Playwright-Adapter für LinkedIn liefert seit April 2026 nichts
        mehr. Die jobspy-Variante (`jobspy_linkedin`) LIEFERT — sie braucht
        nur lange (rund 12 s je Suchbegriff) und hat seit v1.7.120 ein
        eigenes Zeitbudget (#1038); ihre Treffer kommen OHNE Anzeigentext,
        PBP lädt ihn nach dem Suchlauf im Hintergrund nach — für die
        Treffer, die den Filter passiert haben, höchstens 60 je Lauf, der
        Rest mit der Automatik. Die Zahl steht im Lauf-Hinweis. Dieser
        Weg hier liefert den Volltext sofort: HTTP von aussen
        blockt LinkedIn zuverlässig, Requests aus dem EINGELOGGTEN
        Chrome-Tab laufen dagegen durch. Am 17.08.2026 wurde
        dieser Weg vollständig durchgespielt: 22 Suchbegriffe, 511
        deduplizierte Rohtreffer, 59 Volltexte, 3 übernommene Stellen.

        Dieses Werkzeug liefert den Plan samt fertiger Browser-Skripte;
        Claude führt ihn in einem Tab auf linkedin.com aus, und
        `linkedin_treffer_uebernehmen` schreibt das Ergebnis nach PBP.

        **Der Volltext ist Pflicht, nicht Kür.** Von 59 Titeln, die den
        Vorfilter passiert hatten, blieben nach dem Lesen der Volltexte 3
        übrig — der beste Titel-Treffer des Laufs verlangte im Fliesstext
        ein System von der harten Ausschlussliste. Wer nur Titel und
        Kurzbeschreibung übernimmt, liefert genau die falschen Stellen
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
                "3_volltexte": ("Vorlage — <IDS> durch die ausgewählten "
                                "Job-IDs ersetzen (JSON-Liste): "
                                + lv.JS_VOLLTEXTE.replace("__IDS__", "<IDS>")
                                  .replace("__CFG__", "CFG_PLATZHALTER")),
                "4_ausgabe": lv.JS_AUSGABE,
            },
            "js_volltexte_konfig": cfg,
            "ablauf": [
                "Tab auf die LinkedIn-Jobsuche öffnen (eingeloggt).",
                "Skript 1 ausführen — es läuft als async IIFE weiter, "
                "auch wenn der Aufruf sofort zurückkommt.",
                "Skript 2 wiederholt aufrufen, bis 'fertig' true ist.",
                "Titel sichten und die Job-IDs wählen, deren Volltext "
                "geholt werden soll (der Vorfilter).",
                "Skript 3 mit diesen IDs starten, danach wieder Skript 2.",
                "Skript 4 rendert das Ergebnis in die Seite; mit "
                "get_page_text abholen — javascript_tool kappt bei rund "
                "1000 Zeichen.",
                "linkedin_treffer_uebernehmen(treffer=[...]) aufrufen.",
            ],
            "stolpersteine": [
                "Navigation löscht window.__pbp_ln — der ganze Lauf muss "
                "auf EINEM Tab ohne Seitenwechsel passieren.",
                "javascript_tool bricht nach rund 45 s ab. Deshalb laufen "
                "die Schleifen als async IIFE und der Fortschritt wird "
                "abgefragt statt abgewartet.",
                "javascript_tool kappt die Rückgabe bei rund 1000 "
                "Zeichen. Anzeigentexte deshalb NIE zurückgeben, sondern "
                "über Skript 4 rendern und mit get_page_text holen.",
                "URLs mit Query-String in einer Rückgabe lösen einen "
                "Block aus. Die Skripte bauen ihre URLs deshalb selbst und "
                "geben nur Zahlen zurück.",
                f"{lv.PAUSE_MS} ms zwischen den Requests — damit liefen "
                "511 Trefferzeilen plus 59 Volltexte ohne Drosselung durch.",
            ],
            "fehlerdeutung": lv.FEHLER_TEXTE,
            "hinweis": (
                "Ohne eingeloggten Chrome bricht der Lauf ab: "
                "linkedin_treffer_uebernehmen(login_fehlt=True) meldet das "
                "als 'wartet_auf_login'. Das ist KEIN Befund über den "
                "Stellenmarkt — die Quelle bleibt aktiv und wird nicht "
                "automatisch deaktiviert (#906)."
            ),
        }

    @mcp.tool()
    def stellen_entfernen_nach_quelle(quelle: str, dry_run: bool = True) -> dict:
        """Entfernt die Stellen einer Quelle ENDGUELTIG aus dem Bestand (#1075).

        Für den Fall, dass eine Quelle abgewählt wurde und ihre Treffer
        nicht mehr im Bestand stehen sollen — auch nicht aussortiert, weil
        aussortierte Stellen weiter in Statistik, Ablehnungsmustern und den
        Schwellen-Stufen (#1063) zählen. Aussortieren ist
        `stellen_bulk_bewerten`; das hier löscht.

        Geschützt bleiben Stellen mit Bewerbung und Stellen, die eine
        GEWAEHLTE Quelle ebenfalls gefunden hat. Fundstellen, Verknüpfungen
        und Kontakt-Verweise gehen mit; Kontakte selbst bleiben.

        Args:
            quelle: Quellen-Schluessel, z.B. 'hays' oder 'freelance_de'.
            dry_run: Vorgabe True — zeigt nur, was entfernt würde.
        """
        if not (quelle or "").strip():
            return {"fehler": "quelle ist Pflicht (z.B. 'hays')."}
        from ..services import stellen_nach_quelle
        erg = stellen_nach_quelle.entfernen(db, quelle, dry_run=dry_run)
        if not erg["gefunden"]:
            erg["nachricht"] = (f"Keine Stellen der Quelle '{quelle}' im "
                                "Bestand.")
        return erg

    @mcp.tool()
    def linkedin_treffer_uebernehmen(treffer: list = None,
                                     dry_run: bool = True,
                                     login_fehlt: bool = False,
                                     rohtreffer: int = 0,
                                     volltexte_gelesen: int = 0,
                                     nach_lesen_verworfen: int = 0) -> dict:
        """Übernimmt die geernteten LinkedIn-Stellen nach PBP (#919).

        Erwartet je Eintrag mindestens `job_id`, `titel`, `firma` und
        `beschreibung` (Volltext). Optional `ort`, `remote`,
        `anstellungsart` — und seit v1.7.67 (#1011) `kontakt_name`,
        `kontakt_email`, `kontakt_telefon`. Steht in der Anzeige eine
        Ansprechpartnerin namentlich, gehört sie hier hinein: bisher
        hing es am Anlageweg, ob ein Kontakt entsteht.

        Schreibt über denselben Weg wie `stelle_manuell_anlegen` —
        Blacklist, Duplikat-Stufen, Anker-Pflicht und Scoring gelten
        unverändert. Eine zweite Fassung dieser Regeln wäre genau der
        Fehler, der PBP in #963, #987, #991 und #992 je einmal gekostet
        hat.

        **Ohne Volltext keine Anlage.** Einträge unter
        `linkedin_voyager.MIN_BESCHREIBUNG` Zeichen werden uebersprungen
        und gezählt, statt mit halbem Text angelegt zu werden.

        Args:
            treffer: die geernteten Stellen.
            dry_run: True (Vorgabe) zeigt nur, was passieren würde.
            login_fehlt: True meldet den Lauf als 'wartet_auf_login' —
                kein Befund über den Markt, keine Auto-Deaktivierung.
            rohtreffer: Trefferzahl VOR dem Vorfilter. Ohne sie ist
                "3 angelegt" nicht einzuordnen (#813/#989).
            volltexte_gelesen: wie viele Volltexte im Browser gelesen
                wurden (#1076) — auch die, die danach nicht übergeben
                wurden.
            nach_lesen_verworfen: wie viele davon nach dem Lesen
                verworfen wurden.
        """
        from ..job_scraper import linkedin_voyager as lv

        if login_fehlt:
            return {
                "status": "wartet_auf_login",
                "quelle": "linkedin",
                "nachricht": lv.FEHLER_TEXTE["nicht_eingeloggt"],
                "hinweis": (
                    "Die Quelle bleibt aktiv und wird NICHT automatisch "
                    "deaktiviert — ein fehlender Login sagt nichts über "
                    "den Stellenmarkt aus (#906)."
                ),
            }

        eintraege = [e for e in (treffer or []) if isinstance(e, dict)]
        trichter = lv.trichter_leer()
        if not eintraege:
            return leer(
                {"status": "leer", "trichter": trichter},
                "Keine Treffer übergeben.",
                "Erst linkedin_lauf_plan() ausführen und die Ernte hier "
                "übergeben.")

        trichter["rohtreffer"] = max(int(rohtreffer or 0), len(eintraege))
        trichter["nach_vorfilter"] = len(eintraege)
        if volltexte_gelesen:
            trichter["volltexte_gelesen"] = int(volltexte_gelesen)
            trichter["nach_lesen_verworfen"] = int(nach_lesen_verworfen or 0)

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
                      f"{len(beschreibung)} Zeichen, nötig sind "
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
            # v1.7.126 (#1076): angelegt ist, was angelegt wurde — auch
            # mit Warnung. Bis hierher zaehlte jede Antwort mit `warnung`
            # als uebersprungen, seit #1065 also auch eine angelegte Stelle
            # zu einer frueheren Bewerbung: sie stand im Bestand und im
            # Trichter als verworfen.
            if res.get("status") == "angelegt" or (
                    res.get("hash") and not res.get("warnung")):
                trichter["angelegt"] += 1
                _eintrag = {"job_id": job_id, "titel": titel,
                            "firma": firma, "hash": res["hash"],
                            "score": res.get("score")}
                if res.get("kontakt"):
                    _eintrag["kontakt"] = res["kontakt"]
                    trichter["kontakte"] = trichter.get("kontakte", 0) + 1
                for _schl, _feld in (
                        ("repost_verdacht", "repost_verdacht"),
                        ("vermittler_bewerbung", "vermittler_bewerbung"),
                        ("laufende_bewerbung_verdacht",
                         "laufende_bewerbung_verdacht"),
                        ("wiedergaenger_bewerbung", "bewerbung_vorher")):
                    if res.get(_feld):
                        _eintrag[_schl] = res[_feld]
                        trichter[_schl] = trichter.get(_schl, 0) + 1
                angelegt.append(_eintrag)
            elif res.get("warnung"):
                # #1046: der Zustand der vorhandenen Stelle statt der Stufe,
                # die ihn gefunden hat — aktiv, aussortiert und beworben
                # verlangen verschiedene naechste Schritte.
                _skip(e, res.get("duplikat") or res["warnung"],
                      res.get("nachricht") or res.get("grund", ""))
                if res.get("vorhandene_stelle"):
                    uebersprungen[-1]["vorhandene_stelle"] = res["vorhandene_stelle"]
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
        """Verknüpft eine Bewerbung mit einer (zusätzlichen) Stelle (#472).

        Use-Case: Eine Bewerbung kann sich auf MEHRERE Stellen-Versionen
        beziehen — z.B. wenn eine Firma die Stelle re-postet, oder wenn
        man sich gleichzeitig auf zwei verwandte Stellen bewirbt
        (Vermittler + Endkunde, oder Senior + Lead Variante).

        Args:
            bewerbung_id: ID der Bewerbung (mit oder ohne APP-Präfix).
            stellen_hash: Hash der Stelle (mit oder ohne JOB-Präfix).
            version_label: Optionale Bezeichnung (z.B. 'Senior-Variante',
                'Repost vom 15.05.', 'Endkunde-Sicht').
            ist_primaer: Wenn True, wird diese Verknüpfung als primär
                gesetzt (alle anderen werden auf nicht-primär gesetzt).
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
            return {"fehler": f"Verknüpfung fehlgeschlagen: {e}"}
        return {
            "status": "verknuepft",
            "link_id": link_id,
            "bewerbung_id": bewerbung_id,
            "stellen_hash": stellen_hash,
        }

    @mcp.tool()
    def bewerbung_stelle_entknuepfen(bewerbung_id: str, stellen_hash: str) -> dict:
        """Entfernt eine Stellen-Verknüpfung von einer Bewerbung."""
        from ..services.typed_ids import strip_prefix
        bid = strip_prefix(bewerbung_id)
        jhash = strip_prefix(stellen_hash)
        ok = db.unlink_application_job(bid, jhash)
        return {"status": "entfernt" if ok else "nicht_gefunden"}

    @mcp.tool()
    def bewerbung_stellen_anzeigen(bewerbung_id: str) -> dict:
        """Listet alle Stellen, die mit einer Bewerbung verknüpft sind (#472).

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

        Wenn der Score einer Stelle unzuverlässig wirkt weil die
        Beschreibung leer oder zu kurz ist, ruft dieses Tool die URL
        auf, parsed sie und schreibt die Beschreibung zurück in die DB.

        Eine HTTP-GET pro Aufruf — bewusst nicht für Massen-Crawl
        gedacht. Für Bulk-Refetch nutzt PBP den Auto-Engine-Step
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
        from ..job_scraper.textgrenzen import SPEICHER_MAX, kappungs_grenze
        vorher = job.get("description") or ""
        quelle = job.get("source")
        # #1048: Text, Snapshot (C23/#687), Gehalt, Umfang und Score an
        # EINER Stelle — vorher schrieb dieser Weg nur den Text, und der
        # Score blieb der aus dem abgeschnittenen.
        # #952: Das ist der VOLLE Text — vorher wurde ein gekappter Text
        # als unveraenderlicher Snapshot festgeschrieben.
        nachgezogen = nachladen.text_uebernehmen(db, h, text, kopf=befund.kopf)
        antwort = {"status": "ok", "chars": len(text), "preview": text[:200],
                   "neu_ausgewertet": nachgezogen}
        # #952: Der Fehler war stumm — "status: ok" bei halbem Text.
        # Jetzt sagt die Antwort, wenn eine Grenze erreicht wurde.
        if len(text) >= SPEICHER_MAX:
            antwort["grenze_erreicht"] = True
            antwort["hinweis"] = (
                f"Der Text erreicht die Speicher-Notbremse von "
                f"{SPEICHER_MAX} Zeichen und könnte abgeschnitten sein.")
        elif kappungs_grenze(text, quelle):
            antwort["grenze_erreicht"] = True
            antwort["hinweis"] = (
                f"Der geholte Text ist exakt {kappungs_grenze(text, quelle)} "
                "Zeichen lang — die Quelle selbst kappt hier möglicherweise.")
        if kappungs_grenze(vorher, quelle) and len(text) > len(vorher):
            antwort["gekappten_text_geheilt"] = True
            antwort["hinweis"] = (
                f"Vorher {len(vorher)} Zeichen (abgeschnitten), jetzt "
                f"{len(text)}. Der Anforderungsteil steht meist am Ende "
                "und war bisher nicht bewertbar.")
        return antwort

    # v1.7.87 (#1016): "fehlend" ist die Vorgabe, nicht "gekappt".
    # Der Melder hat den Grund geliefert: sein Bestand meldete
    # `geprueft: 984, betroffen: 0` — waehrend 370 Stellen OHNE jeden
    # Text danebenstanden. Das Werkzeug traegt den Namen fuer den
    # Mengenweg und beantwortete nur den Altfall aus #952.
    # v1.7.110 (#1047): `flach` — lange Texte ganz ohne Zeilenumbruch, die
    # Spur des alten Lesers. `beide` bleibt, was es war: fehlend + gekappt.
    UMFAENGE = ("fehlend", "gekappt", "flach", "beide", "ohne_firma_ort",
                "linkedin_kasten")

    @mcp.tool()
    def beschreibungen_nachladen_bestand(max_stellen: int = 25,
                                         nur_zaehlen: bool = True,
                                         umfang: str = "fehlend") -> dict:
        """Lädt fehlende oder abgeschnittene Anzeigentexte nach (#1016).

        Zwei verschiedene Schäden, ein Werkzeug:

        * **fehlend** (Vorgabe) — die Stelle hat gar keinen brauchbaren
          Text. Häufigster Fall: die BA-Suche legt ab Treffer 21 je
          Suchbegriff Stellen ohne Volltext an (#500) und setzt voraus,
          dass Nachladen funktioniert.
        * **gekappt** — der Altbestand aus #952: bis v1.7.22 kappte
          jeder Adapter bei exakt 2000 Zeichen, und weil der Refetch
          selbst kappte, half auch wiederholtes Nachladen nicht.
        * **beide** — beides in einem Lauf.

        Bis v1.7.86 gab es nur den zweiten Fall, und zwar als einzige
        Auswahlregel. Eine Stelle ganz ohne Text hat `len 0` und fiel
        damit durch das Raster — das Werkzeug meldete "nichts zu tun"
        für genau den Bestand, wegen dem man es aufruft.

        Der Lauf geht durch `services/nachladen` (#1014) und liefert
        dessen vier Befunde in der Bilanz. Eine Stelle, deren Anzeige
        der Server ausdrücklich als entfernt meldet (404/410), wird
        AUSSORTIERT statt beim nächsten Lauf erneut versucht.

        Args:
            max_stellen: Obergrenze pro Lauf. Jede Stelle ist ein
                HTTP-Aufruf, deshalb bewusst klein.
            nur_zaehlen: Vorgabe True — meldet nur, wie viele betroffen
                sind, ohne etwas zu holen.
            umfang: `fehlend` (Vorgabe), `gekappt`, `flach` oder `beide`.
                `flach` (#1047) sind Texte ab 500 Zeichen ganz ohne
                Zeilenumbruch — der alte Leser machte aus jeder Anzeige
                einen Absatz. Quellen, deren Text schon an der Quelle
                ungegliedert ist, bleiben aussen vor.
                `ohne_firma_ort` (#1040, #1042) sind Stellen mit
                "Unbekannt" als Firma oder leerem Ort: Firma und Ort
                kommen aus dem JobPosting der Detailseite, samt
                Entfernung und neuem Score. Der Text bleibt, wenn er
                schon vollständig ist.
                `linkedin_kasten` (#1085) sind LinkedIn-Stellen, deren
                Text nur der Gehaltskasten ist oder mit dem Kasten zur
                Ansprechperson beginnt. Hier ersetzt der neue Text den
                alten auch dann, wenn er kürzer ist — der Kasten fällt weg.
        """
        import httpx

        from ..job_scraper.textgrenzen import ist_gekappt
        from ..services import nachladen
        from ..services.datenguete import MIN_BESCHREIBUNG

        gewaehlt = (umfang or "fehlend").strip().lower()
        if gewaehlt not in UMFAENGE:
            # Still auf die Vorgabe zu fallen waere #988: eine Auswahl,
            # der man glaubt, die aber etwas anderes tut.
            return {
                "status": "fehler",
                "grund": (f"Unbekannter Umfang '{umfang}'. Erlaubt: "
                          f"{', '.join(UMFAENGE)}."),
            }

        def _fehlt(job) -> bool:
            # Die Bedingung stammt aus dem Auto-Refetch (#1014) und ist
            # damit dieselbe, nach der PBP im Hintergrund ohnehin
            # nachlaedt. Gemessen am Bestand: von 1.198 textlosen
            # Stellen sind nur 549 wirklich NULL — die uebrigen 649
            # tragen einen Stummel von 13 bis 46 Zeichen. Eine Pruefung
            # auf NULL allein haette mehr als die Haelfte uebersehen.
            return len((job.get("description") or "").strip()) < MIN_BESCHREIBUNG

        aktive = db.get_active_jobs() or []
        fehlend = [j for j in aktive if _fehlt(j)]
        # `ist_gekappt` und `_fehlt` schliessen einander aus (2000 gegen
        # unter 50), eine Dublettenpruefung waere also Zierrat — der
        # Test haelt das fest, damit es beim naechsten Schwellenwert
        # auffaellt.
        # #1048: mit Quelle — `hays` kappte bei 500 Zeichen, und diese
        # Stellen fielen durch beide Raster.
        gekappt = [j for j in aktive
                   if ist_gekappt(j.get("description"), j.get("source"))]
        # #1047: der dritte Schaden — Text da, aber ohne jede Gliederung.
        # Gekappte Texte zaehlen nicht doppelt, und Quellen, deren Text
        # schon an der Quelle ungegliedert ist, gewinnen durch Nachladen
        # nichts.
        from ..job_scraper.html_text import QUELLEN_OHNE_GLIEDERUNG, ist_flach
        flach = [j for j in aktive
                 if ist_flach(j.get("description"))
                 and not ist_gekappt(j.get("description"), j.get("source"))
                 and (j.get("source") or "").strip().lower()
                 not in QUELLEN_OHNE_GLIEDERUNG]
        # v1.7.128 (#1040 Punkt 5): Firma oder Ort fehlen. Nur mit URL —
        # ohne Detailseite gibt es nichts nachzuziehen.
        ohne_kopf = [j for j in aktive
                     if nachladen.fehlender_kopf(j)
                     and (j.get("url") or "").strip()
                     and not j.get("is_search_url")]
        # #1085: LinkedIn-Text, der nur der Gehaltskasten ist oder den
        # Kasten zur Ansprechperson traegt. Die Auswahl liest den Text —
        # geschnitten wird er hier nicht, sondern neu geladen.
        from ..job_scraper.linkedin_seite import nur_gehaltskasten, traegt_ansprechkasten
        li_kasten = [j for j in aktive
                     if "linkedin" in (j.get("source") or "").lower()
                     and (j.get("url") or "").strip()
                     and (nur_gehaltskasten(j.get("description"))
                          or traegt_ansprechkasten(j.get("description")))]
        auswahl = {"fehlend": fehlend, "gekappt": gekappt, "flach": flach,
                   "beide": fehlend + gekappt,
                   "ohne_firma_ort": ohne_kopf,
                   "linkedin_kasten": li_kasten}[gewaehlt]

        zaehlung = {"ohne_text": len(fehlend), "gekappt": len(gekappt),
                    "flach": len(flach), "ohne_firma_ort": len(ohne_kopf),
                    "linkedin_kasten": len(li_kasten)}
        if not auswahl:
            return {
                "status": "nichts_zu_tun",
                "umfang": gewaehlt,
                "geprueft": len(aktive),
                "gefunden": zaehlung,
                "hinweis": _nichts_zu_tun_hinweis(gewaehlt, zaehlung),
            }
        if nur_zaehlen:
            return {
                "status": "vorschau",
                "umfang": gewaehlt,
                "betroffen": len(auswahl),
                "von": len(aktive),
                "gefunden": zaehlung,
                "beispiele": [
                    {"hash": (j.get("hash") or "")[-8:],
                     "titel": (j.get("title") or "")[:60],
                     "zeichen": len(j.get("description") or "")}
                    for j in auswahl[:5]
                ],
                "hinweis": (
                    f"{len(auswahl)} Stellen betroffen. Mit "
                    "nur_zaehlen=False werden bis zu max_stellen davon "
                    "nachgeladen (je ein HTTP-Aufruf)."),
            }

        bilanz = {befund: 0 for befund in nachladen.BEFUNDE}
        ohne_url, aussortiert = 0, 0
        gewachsen: list[dict] = []
        kopf_ergaenzt: list[dict] = []
        with httpx.Client(
                follow_redirects=True, timeout=15,
                headers={"User-Agent":
                         "PBP/1.7 (+github.com/MadGapun/PBP)"}) as client:
            for job in auswahl[:max(1, int(max_stellen or 25))]:
                url = (job.get("url") or "").strip()
                if not url or job.get("is_search_url"):
                    ohne_url += 1
                    continue
                try:
                    befund = nachladen.beschreibung_holen(
                        url, client, timeout=15)
                except Exception as exc:
                    bilanz[nachladen.FEHLER] += 1
                    logger.debug("Nachladen von %s: %s", url, exc)
                    continue
                bilanz[befund.status] = bilanz.get(befund.status, 0) + 1

                if befund.soll_aussortiert_werden:
                    # Genau wie im Einzelweg: eine Anzeige, die der
                    # Server als entfernt meldet, gehoert aussortiert.
                    # Sie beim naechsten Lauf erneut zu versuchen kostet
                    # einen HTTP-Aufruf und aendert nichts.
                    try:
                        db.dismiss_job(job.get("hash"), reason="veraltet_url",
                                       herkunft="automatik",
                                       notiz=befund.klartext())
                        aussortiert += 1
                    except Exception as exc:      # pragma: no cover
                        logger.debug("Aussortieren (#1016): %s", exc)
                    continue

                text = befund.text or ""
                alt_laenge = len((job.get("description") or "").strip())
                # #1047: ein gegliederter Text ersetzt einen flachen auch
                # ohne zu wachsen — aus Leerzeichen werden Umbrueche, die
                # Laenge bleibt fast gleich. Unter 90 % bleibt er aussen
                # vor: dann fehlt Inhalt, nicht nur Leerraum.
                from ..job_scraper.html_text import ist_flach as _ist_flach
                gegliedert = (_ist_flach(job.get("description"))
                              and "\n" in text
                              and len(text) >= 0.9 * alt_laenge)
                if (len(text) <= alt_laenge and not gegliedert
                        and gewaehlt != "linkedin_kasten"):
                    # v1.7.128 (#1040 Punkt 5): der Text ist schon da, aber
                    # Firma oder Ort fehlen — dann nur den Kopf nachziehen.
                    if (befund.kopf
                            and nachladen.fehlender_kopf(job)):
                        _k = nachladen.kopf_nachziehen(
                            db, job.get("hash"), befund.kopf)
                        if _k.get("kopf"):
                            kopf_ergaenzt.append({
                                "hash": (job.get("hash") or "")[-8:],
                                "ergaenzt": _k["kopf"]})
                    continue
                # #1048: Text, Snapshot, Gehalt, Umfang und Score an EINER
                # Stelle. Bis v1.7.108 stand hier nur der Text, und die
                # Antwort bat darum, danach den ganzen Bestand neu zu
                # berechnen — der Score blieb bis dahin der aus dem
                # abgeschnittenen Text.
                nachgezogen = nachladen.text_uebernehmen(
                    db, job.get("hash"), text, kopf=befund.kopf)
                if nachgezogen.get("kopf"):
                    kopf_ergaenzt.append({
                        "hash": (job.get("hash") or "")[-8:],
                        "ergaenzt": nachgezogen["kopf"]})
                gewachsen.append({
                    "hash": (job.get("hash") or "")[-8:],
                    "vorher": alt_laenge, "nachher": len(text),
                    "score": nachgezogen.get("score"),
                })

        # #1040: eine Stelle, die nur Firma und Ort bekam, ist ebenfalls
        # geheilt — sonst meldete der Umfang `ohne_firma_ort` stets 0.
        geheilt = len({g["hash"] for g in gewachsen}
                      | {k["hash"] for k in kopf_ergaenzt})
        return {
            "status": "fertig",
            "umfang": gewaehlt,
            "geheilt": geheilt,
            "aussortiert": aussortiert,
            "ohne_brauchbare_url": ohne_url,
            "befunde": {k: v for k, v in bilanz.items() if v},
            "befunde_klartext": {
                k: nachladen.KLARTEXT.get(k, "") for k, v in bilanz.items() if v},
            "verbleibend": max(0, len(auswahl) - geheilt - aussortiert),
            "gewachsen": gewachsen[:10],
            # v1.7.128 (#1040, #1042): Firma und Ort aus der Detailseite.
            "kopf_ergaenzt": len(kopf_ergaenzt),
            "kopf_beispiele": kopf_ergaenzt[:10],
            "hinweis": (
                # #1048: bis v1.7.108 stand hier die Bitte, danach den
                # ganzen Bestand neu zu berechnen. Jetzt bewertet
                # `text_uebernehmen` jede geheilte Stelle selbst.
                "Die nachgeladenen Stellen sind neu ausgewertet — Gehalt, "
                "Umfang, Entfernung und Score beruhen jetzt auf dem vollen "
                "Text und der Detailseite; `gewachsen` nennt je Stelle den "
                "Score vorher und nachher, `kopf_beispiele` ergänzte Firma "
                "und Ort."
                if geheilt else
                # Der Klartext je Befund steht in `befunde_klartext` und
                # kommt aus `services/nachladen` — ihn hier zu
                # wiederholen war die Bauform, die dieses Projekt
                # siebzehnmal gekostet hat, und der #1014-Guard hat sie
                # beim ersten Lauf gefangen.
                "Nichts geheilt. `befunde_klartext` sagt je Befund, "
                "woran es lag und was der nächste Schritt ist."),
        }

    def _nichts_zu_tun_hinweis(umfang: str, zaehlung: dict) -> str:
        """Sagt, was der ANDERE Umfang noch faende.

        Bis v1.7.86 stand hier "es sieht nichts nach der alten Kappung
        aus" — richtig und trotzdem irrefuehrend, weil daneben 370
        Stellen ohne jeden Text lagen. Eine Entwarnung, die nur fuer
        einen Teil gilt, muss sagen fuer welchen.
        """
        rest = {"fehlend": ("gekappt", zaehlung["gekappt"]),
                "gekappt": ("fehlend", zaehlung["ohne_text"]),
                "flach": ("fehlend", zaehlung["ohne_text"])}.get(umfang)
        satz = {
            "fehlend": "Jede aktive Stelle traegt einen brauchbaren Text.",
            # #1048: nicht mehr nur 2000 — `hays` kappte bei 500.
            "gekappt": ("Kein aktiver Anzeigentext trifft eine bekannte "
                        "Kappungsgrenze (2000 Zeichen, bei der Quelle hays "
                        "500) — es "
                        "sieht nichts nach einer Kappung aus."),
            # #1047
            "flach": ("Kein aktiver Anzeigentext ab 500 Zeichen ist ohne "
                      "Gliederung — es sieht nichts nach dem alten Leser aus."),
            "beide": ("Weder fehlende noch abgeschnittene Texte im aktiven "
                      "Bestand."),
            # #1040
            "ohne_firma_ort": ("Jede aktive Stelle mit Detailseite traegt "
                               "Firma und Ort."),
            "linkedin_kasten": ("Keine LinkedIn-Stelle traegt den Gehaltskasten "
                                "oder den Kasten zur Ansprechperson als Text."),
        }[umfang]
        if rest and rest[1]:
            satz += (f" Im Umfang '{rest[0]}' waeren es {rest[1]} — "
                     f"umfang='{rest[0]}' oder umfang='beide'.")
        return satz

    def _ist_gekappt(text, quelle=None) -> bool:
        from ..job_scraper.textgrenzen import ist_gekappt
        # #1048: die Quelle entscheidet mit — `hays` kappte bei 500.
        return ist_gekappt(text, quelle)

    @mcp.tool()
    def stellen_qualitaet_pruefen(
        max_stellen: int = 50,
        nur_problematische: bool = True,
        auto_aussortieren: bool = False,
        mit_ollama_validierung: bool = False,
    ) -> dict:
        """Prüft URL-Health + Beschreibungs-Vollständigkeit aktiver Stellen (#645).

        Geht pro aktiver Stelle durch:
        1. URL-Reachability (HTTP-Status + Bot-Block-Erkennung)
        2. Body-Marker "Stelle vergeben/expired"
        3. Workday-API-Cross-Check für Workday-SPAs
        4. Title-Token-Match Body vs. Titel (hat Server-Replacement geliefert?)
        5. Beschreibungs-Länge (>= 50 Zeichen)

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
            url_nicht_erreichbar — die Adresse ließ sich nicht erreichen
                              (kein Netz, Namensfehler; KEIN Aussortier-
                              Grund) — zählt NICHT als ok (#1148)
            beschreibung_fehlt — URL ok, aber description leer/zu kurz
            search_url      — URL ist nur Such-URL (is_search_url=1)

        Args:
            max_stellen: Maximum aktiver Stellen pro Lauf (Schutz gegen
                lange Token-Runs).
            nur_problematische: Default True — nur Stellen mit Befund
                zurückliefern, nicht die OK-Stellen einzeln auflisten.
            auto_aussortieren: Default False (Vorschau). Bei True werden
                Stellen mit url_404 oder url_expired sofort via
                dismiss_job(reason='veraltet_url') ausgemustert.
            mit_ollama_validierung: Default False. Bei True wird zusätzlich
                Ollama (lokale AI) genutzt um pro Stelle die Beschreibungs-
                Vollständigkeit zu bewerten — liefert pro Stelle einen
                "ollama"-Block mit {vollständig, score, vorhanden, fehlt,
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
                    elif health.status == HealthStatus.UNKNOWN:
                        # #1148: eine Adresse, die sich nicht erreichen liess
                        # (kein Netz, Namensfehler), fiel durch alle Zweige
                        # und zaehlte als "ok" — ohne Netz: "geprueft 5, ok 1".
                        kategorie.append("url_nicht_erreichbar")
                    detail["health"] = health.to_dict()

                if not desc or len(desc) < 50:
                    kategorie.append("beschreibung_fehlt")
                # #952: bisher kannte die Pruefung nur die UNTERGRENZE.
                # Ein bei exakt 2000 Zeichen abgeschnittener Text galt als
                # tadellos, obwohl der Anforderungsteil fehlte — und ohne
                # diese Kategorie war die Tragweite nur per Direkt-SQL
                # messbar, was nach #514 unterbleiben soll.
                elif _ist_gekappt(desc, source):
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
            _gekappt = sum(1 for j in _alle
                           if _ist_gekappt(j.get("description"), j.get("source")))
            if _gekappt:
                _quote = round(100.0 * _gekappt / max(1, len(_alle)), 1)
                result["beschreibung_gekappt_gesamt"] = {
                    "anzahl": _gekappt,
                    "von": len(_alle),
                    "anteil_prozent": _quote,
                    "hinweis": (
                        f"{_gekappt} von {len(_alle)} aktiven Stellen "
                        f"({_quote} %) tragen einen abgeschnittenen "
                        "Anzeigentext (Altbestand vor v1.7.23, bei der "
                        "Quelle hays bis v1.7.108). Der "
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
                        "oder auf Basis eines geschätzten Gehalts "
                        "getroffen. Sie zählen im "
                        "Wiedergänger-Mechanismus nur halb. Zum "
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
                        "aufgelöste Entfernung. Ihr Entfernungs-Malus "
                        "entfällt — sie stehen dadurch zu weit oben. "
                        "Ort prüfen mit stelle_bearbeiten(), danach "
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

        Liefert eine Gegenüberstellung von Skills (gemeinsam / nur A /
        nur B), Gehalt, Standort, Stellenart, Score und
        Beschreibungs-Länge. Sehr hilfreich um zu erkennen ob zwei
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
        """Findet ähnliche Stellen zu einer gegebenen Stelle (#580).

        Algorithmus: Token-Overlap zwischen Title+Description. Bewerbungen
        und Stellen mit gleichem Hash werden ausgeschlossen. Liefert
        zusätzlich den Outcome-Status (erfolgreich/abgelehnt/aussortiert)
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
            return {"hinweis": "Stelle hat zu wenig Text für Ähnlichkeits-Berechnung."}

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
        """Führt zwei doppelt angelegte Stellen zusammen (#470).

        Typischer Flow:
        1. Erst ``dry_run=True`` (Default) aufrufen -> Vorschau mit Feld-
           Entscheidungen, Konflikten und welche Bewerbungen umgehängt werden.
        2. Output prüfen, bei Konflikten ggf. ``feld_strategie`` mitgeben.
        3. Mit ``dry_run=False`` finalisieren.

        Args:
            master_hash: Stelle, die erhalten bleibt.
            duplikat_hash: Stelle, die aufgelöst (gelöscht) wird.
            feld_strategie: Optional dict pro Feld: 'master' | 'duplikat' |
                'merge' (letzteres nur für 'description' sinnvoll).
                Felder die nur im Duplikat gefüllt sind, werden automatisch
                uebernommen — ausser die Strategie nennt 'master' (#1077),
                dann bleibt das Feld leer. Die Vorschau nennt diese Felder
                unter 'ohne_rueckfrage_uebernommen'. Entfernung und
                Koordinaten folgen dem Ort: kommt 'location' vom Master,
                kommen auch sie vom Master. Felder die nur im Master
                gefüllt sind, bleiben.
            dry_run: Default True. Bei True wird nichts geschrieben.

        Returns:
            dict mit 'status' ('vorschau'/'ok'), 'feld_entscheidungen',
            'konflikte' (Liste Felder mit abweichenden Werten),
            'umgehaengte_bewerbungen'.
        """
        if not master_hash or not duplikat_hash:
            return {"fehler": "master_hash und duplikat_hash sind Pflicht"}
        sicherung_name = None
        if not dry_run:
            # #1098: das Zusammenfuehren loescht die Dublette — vorher eine
            # Sicherung (nur die Datenbank; Dateien fasst es nicht an).
            from ..services import sicherung as _sicherung
            _s = _sicherung.sichern(db, anlass="vor_zusammenfuehren",
                                    mit_dokumenten=False)
            if _s["status"] != "gesichert":
                return {"fehler": ("Vor dem Zusammenführen ließ sich keine "
                                   "Sicherung anlegen — es wurde nichts "
                                   "geändert. " + (_s.get("fehler") or ""))}
            sicherung_name = _s["name"]
        result = db.merge_jobs(
            master_hash=master_hash,
            duplicate_hash=duplikat_hash,
            field_strategy=feld_strategie,
            dry_run=dry_run,
        )
        if dry_run and "fehler" not in result:
            result["hinweis"] = (
                "Vorschau. Mit dry_run=False ausführen. "
                "Bei Konflikten feld_strategie mitgeben "
                "(z.B. {'description': 'merge', 'url': 'duplikat'})."
            )
        if sicherung_name:
            result["sicherung"] = sicherung_name
        return result

    @mcp.tool()
    def fit_analyse(job_hash: str, score_uebernehmen: bool = False,
                    beschreibung_ab: int = 0) -> dict:
        """Detaillierte Passungsanalyse für eine bestimmte Stelle.

        Zeigt welche Keywords matchen, was fehlt, und gibt eine Risikobewertung.

        Liefert den Anzeigentext VOLLSTAENDIG (`stellenbeschreibung`).
        `beschreibung_ausgabe` sagt, was davon in dieser Antwort steckt —
        bei einer entarteten Seite greift eine Notbremse, und dann steht
        dort, wie der Rest zu holen ist.

        Reines LESEWERKZEUG (seit v1.7.24, #963): der Aufruf verändert
        die Stelle nicht mehr. Bis v1.7.23 schrieb er den errechneten
        Wert still in `jobs.score` — wer sich eine Stelle nur genauer
        ansah, verschob damit ihre Position in der Trefferliste.

        Args:
            job_hash: Hash der Stelle (von stellen_anzeigen)
            score_uebernehmen: True = den errechneten Wert ausdrücklich
                als neuen Score speichern. Standard False.
            beschreibung_ab: Ab welchem Zeichen der Anzeigentext
                geliefert wird. Nur nötig, wenn `beschreibung_ausgabe`
                ein `weiter_ab_zeichen` nennt.
        """
        from ..job_scraper import fit_analyse as _fit_analyse
        job_dict = db.get_job(job_hash)
        if not job_dict:
            return {"fehler": "Stelle nicht gefunden. Prüfe den Hash mit stellen_anzeigen()."}
        # C23 (#687): Ist die Live-Beschreibung weggebrochen (URL offline,
        # spaeterer Refetch lieferte Muell), traegt der unveraenderliche
        # Snapshot die Analyse — mit sichtbarem Hinweis.
        beschreibung_aus_snapshot = False
        if (len((job_dict.get("description") or "").strip()) < 50
                and len((job_dict.get("description_snapshot") or "").strip()) >= 50):
            job_dict = dict(job_dict)
            job_dict["description"] = job_dict["description_snapshot"]
            beschreibung_aus_snapshot = True
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
            # v1.7.118 (#1055): hier stand eine UEBERSCHREIBUNG. Die
            # Kriterien kamen durch das Nadeloehr aus #987 — und danach
            # setzte diese Zeile `min_gehalt` aus den Job-Praeferenzen
            # darueber. Gemessen: Liste rechnete mit 75.000, die
            # Detailansicht mit 80.000, und beide Zahlen hiessen "dein
            # Minimum". Es gilt die Einstellungsseite; die Kriterien
            # tragen den Wert bereits.
        # v1.7.62 (#1008 Befund 3): der Hochschulabschluss-Malus ist
        # entfallen. Er wurde hier in die Kriterien geschrieben und von
        # KEINEM Rechenweg gelesen — die Pruefung dahinter ist seit
        # v1.7.35 (#972) entfernt. Ein Wert ohne Leser ist keine
        # Einstellung (#993, #1000).
        result = _fit_analyse(job_dict, criteria)
        # v1.7.127 (#1082 AK 3): nennt die Anzeige einen naeheren
        # Standort, rechnet die Entfernung mit ihm — und sagt es.
        try:
            from ..services import standorte as _standorte
            _weiterer = _standorte.naechster(job_dict, criteria)
            if _weiterer:
                result["naechster_standort"] = _weiterer
            # #1084: laeuft die Anzeige weiter? Ein Wiederfund sagt es.
            from ..services import stellen_grabstein as _grab
            _wieder = _grab.erneut_gesehen(
                db, db.resolve_job_hash(job_dict.get("hash") or "") or "")
            if _wieder:
                result["erneut_gesehen"] = _wieder
        except Exception as e:  # pragma: no cover
            logger.debug("Standorte (#1082): %s", e)

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
            # C96 (#1087 C1): statt einer zweiten Zahl ("score_in_liste")
            # dieselben Punkte wie Liste, Dashboard und Timeline — mit
            # Faktoren, die sich genau zu ihnen addieren.
            from ..services import punkte as _punkte
            result.update(_punkte.fuer_frisch(db, job_dict, result))
            # v1.7.127 (#1082): die Schwelle vergleicht den Fachwert
            # (ohne Entfernung/Remote/Gehalt). Ob die Stelle in der Liste
            # steht, sagt diese Antwort ausdruecklich.
            if _regler.get("unter_schwelle"):
                result["unter_schwelle"] = True
                result["schwellen_hinweis"] = (
                    "Diese Stelle steht nicht in der Stellenliste: ihr "
                    f"Fachwert ({_regler.get('fach_score')}) liegt unter "
                    "deiner Score-Schwelle. " + _SCHWELLE_VERGLEICHT)
        except Exception as e:
            logger.debug("Regler-Abgleich (#1008): %s", e)

        if beschreibung_aus_snapshot:
            result["beschreibung_aus_snapshot"] = {
                "snapshot_at": job_dict.get("snapshot_at", ""),
                "hinweis": (
                    "Live-Beschreibung fehlt/zu kurz — Analyse lief auf dem "
                    "unveränderlichen Volltext-Snapshot vom Anlage-Zeitpunkt "
                    "(#687). Die Anzeige könnte offline sein."
                ),
            }

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
                        "Meist ist der gespeicherte Wert älter als die "
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
                        # v1.7.95 (#1035): mit Nachkommastelle, wie
                        # calculate_score ihn liefert — nicht abgeschnitten.
                        db.update_job(job_hash, {"score": round(float(new_score), 1)})
                        result["score_aktualisiert"] = {
                            "alter_score": old_score,
                            "neuer_score": round(float(new_score), 1),
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
        #
        # v1.7.122 (#1064): der Text geht VOLLSTAENDIG hinaus. Bis
        # v1.7.121 kappte die Ausgabe bei 2000 Zeichen — stumm, und bei
        # 29,5 % der langen Anzeigen begann der Anforderungsteil erst
        # dahinter. Seit #1003/#1007 ist diese Antwort die Grundlage des
        # gespeicherten Urteils; eine Kuerzung ist hier nicht vertretbar.
        # Greift die Notbremse doch (entartete Seite), sagt es `ausgabe`.
        if job_dict.get("description"):
            from ..job_scraper.textgrenzen import ausgabe, kappungs_hinweis
            _text, _befund = ausgabe(job_dict["description"],
                                     ab=beschreibung_ab)
            result["stellenbeschreibung"] = _text
            result["beschreibung_ausgabe"] = _befund
            # Zwei verschiedene Fragen, deshalb zwei Felder (#1064
            # Angrenzend 1): `beschreibung_ausgabe` beschreibt DIESE
            # Antwort, `beschreibung_unvollstaendig` den GESPEICHERTEN
            # Text — der kann an der Quelle gekappt worden sein.
            _kappung = kappungs_hinweis(job_dict["description"],
                                        job_dict.get("source"))
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
        # v1.7.140 (#954): je Feld belegt / geschätzt / unbekannt, mit
        # Methode und Zeitpunkt. Claude soll einen geschaetzten Wert nicht
        # wie einen belegten weitergeben.
        try:
            from ..services import wahrheit as _wahrheit
            result["herkunft"] = _wahrheit.felder(job_dict, db.get_search_criteria())
            result["herkunft_kurz"] = _wahrheit.kurz(result["herkunft"])
        except Exception:  # pragma: no cover
            pass
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
            from ..services import bewerbungs_hinweis as _bh
            _repost = _bh.fuer_stelle(job_dict, db.get_applications(), db=db)
            if _repost:
                result.update(_bh.als_felder(_repost))
        except Exception as _e:
            logger.debug("Repost-Check in fit_analyse: %s", _e)

        # #1003/#1007: der Verdict kommt aus dem gespeicherten Befund der
        # Detailanalyse — nicht aus dem Suchbegriff-Score. Liegt keiner
        # vor, sagt PBP das, statt zu raten.
        # v1.7.112 (#1051): gegen die rohen Kriterien, wie beim Speichern.
        _gespeichert = passung.analyse_lesen(
            job_dict, profile, db.get_search_criteria())
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
        entfernung_km: float | None = None,
        entfernung_zuruecksetzen: bool = False,
    ) -> dict:
        """Aktualisiert Felder einer bestehenden Stelle (#446, #645).

        Nutze dies, um eine gescrapte oder manuell angelegte Stelle
        nachträglich zu korrigieren oder zu verfeinern — z.B. wenn aus einer
        E-Mail eine ausführlichere Beschreibung hervorgeht oder die
        Ortsangabe prezisiert werden muss.

        Nur angegebene Felder werden geaendert. Leere Strings bleiben unverändert.

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
                Recherche-Ergebnisse oder Bewerberstatistiken gehören
                HINTER eine Zeile mit '---' (erst Original-Anzeigentext,
                dann '---', dann Notizen). Alles vor der Trennzeile
                zählt ins Scoring — ein Ausschluss-Keyword in einer
                Notiz setzt den Score sonst hart auf 0 (belegter Fall:
                eine LinkedIn-Bewerberstatistik mit '20 % Berufseinsteiger'
                nullte eine passende Stelle).
            url: Neue Stellen-URL. Wird auch genutzt um nach #645 leere
                URL-Felder bei XING/Stepstone/Email-Stellen nachzupflegen.
            entfernung_km: Entfernung von Hand setzen (#1077), auch 0 für
                "am Wohnort antretbar". Gilt ab dann dauerhaft — kein
                Suchlauf überschreibt sie. Für den Fall, dass die Anzeige
                einen anderen Ort nennt als den, an dem man antritt.
            entfernung_zuruecksetzen: True = Entfernung auf "unbekannt"
                setzen und für die Automatik freigeben.
        """
        # v1.7.0-beta.46 (#618): Kurze IDs (8 Zeichen) wurden vorher
        # nicht akzeptiert — andere Tools (fit_analyse, scoring_vorschau)
        # tun das aber. Konsistenz: resolve_job_hash erlaubt beides.
        from ..services.typed_ids import strip_prefix
        h = strip_prefix(job_hash)
        resolved = db.resolve_job_hash(h)
        if not resolved:
            return {"fehler": "Stelle nicht gefunden. Prüfe den Hash mit stellen_anzeigen()."}
        job = db.get_job(resolved)
        if not job:
            return {"fehler": "Stelle nicht gefunden. Prüfe den Hash mit stellen_anzeigen()."}
        # Ab hier den vollen aufgeloesten Hash verwenden
        job_hash = resolved

        # #1095: Aenderung und Neuberechnung (#535, #987) stehen im Dienst
        # services/stelle_aendern — derselbe Weg wie der Bearbeiten-Dialog
        # im Dashboard. Ein neuer Ort rechnet die Entfernung neu.
        from ..services import stelle_aendern as _aendern
        erg = _aendern.aendern(
            db, job_hash, {"title": titel, "company": firma, "location": ort,
                           "description": beschreibung, "url": url},
            entfernung_km=entfernung_km,
            entfernung_zuruecksetzen=entfernung_zuruecksetzen)
        if not erg["ok"]:
            return {"fehler": erg["fehler"]}
        updates = erg["updates"]
        entfernung_geaendert = entfernung_km is not None or entfernung_zuruecksetzen

        result = {
            "status": "aktualisiert",
            "job_hash": job_hash,
            "geaenderte_felder": list(updates.keys()),
            "nachricht": (
                f"Stelle '{updates.get('title') or job.get('title', '')}' "
                f"bei {updates.get('company') or job.get('company', '')} aktualisiert."
            ),
        }
        if erg.get("score_neu_berechnet"):
            result["score_neu_berechnet"] = erg["score_neu_berechnet"]
        if entfernung_geaendert:
            result["entfernung"] = (
                {"wert_km": None, "quelle": "unbekannt",
                 "hinweis": "Entfernung zurückgesetzt; die Automatik darf "
                            "sie wieder berechnen."}
                if entfernung_zuruecksetzen else
                {"wert_km": float(entfernung_km), "quelle": "mensch",
                 "hinweis": "Von Hand gesetzt — kein Suchlauf "
                            "überschreibt diesen Wert."})
        elif erg.get("entfernung_hinweis"):
            result["entfernung_hinweis"] = erg["entfernung_hinweis"]
        # #645: Wenn die neue URL eine Such-URL ist, das wie bei
        # stelle_manuell_anlegen transparent zurueckmelden — sonst denkt
        # der User der Link sei voll funktionsfaehig.
        if "url" in updates and updates.get("is_search_url"):
            result["url_warnung"] = (
                "Die übergebene URL zeigt auf eine Suchergebnis-Seite, nicht auf die "
                "konkrete Stellenanzeige. Sie wurde trotzdem gespeichert. "
                "stellenbeschreibung_nachladen wird damit voraussichtlich nichts "
                "Brauchbares zurückliefern — für das Nachladen die Detail-URL nachreichen."
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
        funktioniert für Senior-PLM genauso wie für Studenten oder
        Service-Berufe.

        Pro Stelle (max_stellen, sortiert nach Score absteigend):
        - LLM-Anfrage `match_job_to_skills` mit Profil-Kontext + Stelle
        - PASST_NICHT → dismiss_job mit Grund 'profil_match_negativ' und
          LLM-Begruendung in research_notes
        - UNSICHER → unangetastet (User entscheidet manuell)
        - PASST → unangetastet

        Voraussetzung: Lokale AI aktiv (Ollama läuft, Modell installiert).
        Fallback: ohne Lokale AI gibt es eine ehrliche Meldung — keine
        Heuristik-Raterei.

        v1.7.0-beta.74 (#646): Hard-Cap auf max_stellen=10 (vorher 50) +
        Wall-Clock-Budget max_dauer_sek=50s (#691, bewusst unter dem ~60s-
        MCP-Client-Timeout). Bei Erreichen des Budgets wird mit
        `status='teilweise'` und allen bis dahin verarbeiteten Stellen
        zurückgegeben — kein stilles Timeout, kein Schema-Validierungsfehler.
        Idempotent fortsetzbar: ein erneuter Aufruf bearbeitet die nicht
        verarbeiteten Reste.

        Args:
            max_stellen: Maximum Stellen pro Lauf (Default 10, war 50 vor
                         beta.74). Schutz gegen MCP-Timeout. Bei mehr
                         Stellen mehrere Läufe machen.
            min_score: Mindest-Score-Schwelle. Stellen darunter werden gar
                       nicht erst der LLM vorgelegt (Default 0 = alle).
            dry_run: Wenn True, nur Vorschau ohne dismiss-Aktionen.
            max_dauer_sek: Wall-Clock-Budget in Sekunden (Default 50, cap 90;
                bewusst unter dem ~60s-MCP-Client-Timeout, #691). Bei
                Erreichen wird mit schemakonformem Teil-Ergebnis abgebrochen.

        Idempotent: bewertet keine Stelle erneut die schon `passt_nicht`
        oder eine Bewerbung hat.
        """
        from ..services import auto_aussortierung
        return auto_aussortierung.aussortieren(
            db, max_stellen=max_stellen, min_score=min_score,
            dry_run=dry_run, max_dauer_sek=max_dauer_sek)

    @mcp.tool()
    def ats_firmen_verwalten(aktion: str = "status", firmen: list[str] = None,
                             dry_run: bool = True, max_firmen: int = 30) -> dict:
        """Welche Firmen fragen Personio und Greenhouse ab? (#811)

        Diese Quellen suchen nicht, sie lesen die Stellenliste EINER Firma.
        Bis v1.7.95 stand dafür eine feste Liste fremder Arbeitgeber im
        Code. Jetzt kommen die Firmen aus deinem Bestand — Bewerbungen,
        Kontakte, gefundene Stellen — und jede wird geprüft, bevor sie
        zaehlt: ein erfundener Name leitet bei Personio auf die Seite des
        Anbieters um und sieht sonst wie ein Treffer aus.

        Args:
            aktion: 'status' (wie viele Firmen je System abgefragt werden),
                'ermitteln' (Bestand prüfen, erst als Vorschau),
                'hinzufuegen' (Wunscharbeitgeber: Firmennamen oder
                Karriere-URLs in `firmen`), 'entfernen' (Slugs in `firmen`).
            firmen: für 'hinzufuegen' und 'entfernen'.
            dry_run: Vorgabe True — 'ermitteln' fragt dann nichts ab.
            max_firmen: wie viele Firmennamen ein Lauf höchstens prüft.
        """
        from ..services import ats_firmen as _ats

        aktion = (aktion or "status").strip().lower()
        if aktion == "status":
            stand = _ats.status(db)
            antwort = {"systeme": stand}
            leer = [s for s, w in stand.items() if not w["eigene_gueltig"]]
            if leer:
                antwort["hinweis"] = (
                    f"Fuer {', '.join(leer)} fragt PBP nur die Beispielliste ab — "
                    "keine Firma aus deinem Bestand. "
                    "ats_firmen_verwalten('ermitteln') prüft deine Bewerbungen, "
                    "Kontakte und Stellen.")
            return antwort

        if aktion == "ermitteln":
            if dry_run:
                kand = _ats.kandidaten(db, max_firmen)
                je_system = {s: sum(1 for k in kand if k["system"] == s)
                             for s in _ats.SYSTEME}
                return {
                    "status": "vorschau",
                    "anfragen": len(kand),
                    "je_system": je_system,
                    "aus_stellen_urls": sum(1 for k in kand
                                            if k["quelle"] == _ats.QUELLE_URL),
                    "firmen": list(dict.fromkeys(
                        k["firma"] for k in kand if k.get("firma")))[:15],
                    "hinweis": (
                        "Vorschau — nichts wurde abgefragt. Jede Firma wird je "
                        "System mit höchstens zwei Schreibweisen geprüft; "
                        "schon geprüfte fallen heraus. Mit dry_run=False "
                        "geht es los."),
                }
            ergebnis = _ats.ermitteln(db, max_namen=max_firmen)
            ergebnis["systeme"] = _ats.status(db)
            if ergebnis["gefunden"]:
                ergebnis["naechster_schritt"] = (
                    "Der nächste Suchlauf fragt diese Firmen direkt ab "
                    "(Quellen personio bzw. greenhouse müssen aktiv sein).")
            if ergebnis["nicht_erreichbar"]:
                ergebnis["hinweis_nicht_erreichbar"] = (
                    "Einige Abfragen kamen nicht durch. Sie sind nicht als "
                    "ungültig gespeichert und werden beim nächsten Lauf "
                    "erneut geprüft.")
            return ergebnis

        if aktion == "hinzufuegen":
            if not firmen:
                return {"fehler": "firmen=[...] mit Namen oder Karriere-URLs angeben."}
            aufgenommen, nicht_gefunden = [], []
            for eintrag in firmen:
                treffer = _ats.slug_aus_url(eintrag)
                paare = ([treffer] if treffer else
                         [(s, slug) for s in _ats.SYSTEME
                          for slug in _ats.slug_kandidaten(eintrag)])
                gefunden = False
                for system, slug in paare:
                    befund, stellen = _ats.pruefen(system, slug)
                    if befund == _ats.GUELTIG:
                        _ats.speichern(db, system, slug, eintrag,
                                       _ats.QUELLE_WUNSCH, befund, stellen)
                        aufgenommen.append({"firma": eintrag, "system": system,
                                            "slug": slug, "stellen": stellen})
                        gefunden = True
                        break
                if not gefunden:
                    nicht_gefunden.append(eintrag)
            antwort = {"aufgenommen": aufgenommen, "nicht_gefunden": nicht_gefunden}
            if nicht_gefunden:
                antwort["hinweis"] = (
                    "Für diese Firmen fand PBP weder bei Personio noch bei "
                    "Greenhouse eine Stellenliste. Mit der URL der "
                    "Karriereseite geht es genauer, falls die Firma eines der "
                    "beiden Systeme nutzt.")
            return antwort

        if aktion == "entfernen":
            if not firmen:
                return {"fehler": "firmen=[...] mit den Slugs angeben (siehe 'status')."}
            _ats.tabelle_anlegen(db)
            conn = db.connect()
            weg = 0
            for slug in firmen:
                weg += conn.execute(
                    "DELETE FROM ats_firmen WHERE profile_id=? AND slug=?",
                    (db.get_active_profile_id() or "", slug)).rowcount or 0
            conn.commit()
            return {"entfernt": weg, "systeme": _ats.status(db)}

        return {"fehler": f"Unbekannte Aktion '{aktion}'.",
                "moegliche_aktionen": ["status", "ermitteln", "hinzufuegen", "entfernen"]}

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
                "nachricht": f"Scraper '{scraper_name}' wurde reaktiviert und wird bei der nächsten Suche wieder verwendet."
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
        # v1.7.96 (#811 AK 5): Personio und Greenhouse fragen einzelne
        # Firmen ab. Ob darunter eine aus dem eigenen Bestand ist, sah man
        # bisher nirgends — 0 eigene Firmen ist ein Zustand, kein stiller.
        try:
            from ..services import ats_firmen as _ats
            result["ats_firmen"] = _ats.status(db)
        except Exception:  # pragma: no cover — die Diagnose laeuft trotzdem
            pass
        if defekte:
            result["defekte_quellen"] = defekte
            result["hinweis_defekt"] = (
                f"{len(defekte)} Quelle(n) sind aktuell als defekt markiert "
                "(URL veraltet, Bot-Schutz oder Timeout). Sie werden nicht "
                "automatisch durchsucht. Workaround: Chrome-Extension öffnen "
                "und Stellen via stelle_manuell_anlegen nach PBP uebernehmen."
            )
        if ohne_passung:
            result["quellen_ohne_passung"] = ohne_passung
            result["hinweis_ohne_passung"] = (
                f"{len(ohne_passung)} Quelle(n) liefern Stellen, aber keine, "
                "die zu deinen Suchbegriffen passt. Das ist KEIN Defekt und "
                "führt nicht zur Abschaltung — die Quelle arbeitet, sie ist "
                "nur die falsche für dieses Profil. Bei globalem Fokus "
                "(regionen_fokus) lohnt es sich zu prüfen, ob sie "
                "eingeschaltet bleiben soll."
            )
        if stumme:
            result["stumme_quellen"] = stumme
            result["hinweis_stumm"] = (
                f"{len(stumme)} Quelle(n) liefern seit mehreren Läufen 0 Treffer. "
                "Prüfe, ob Selektoren veraltet sind oder die Quelle den Standort nicht abdeckt."
            )
        if deaktiviert_auto:
            result["auto_deaktiviert"] = deaktiviert_auto
            result["hinweis_reaktivierung"] = (
                "Diese Quellen wurden nach 5+ stillen Läufen automatisch deaktiviert. "
                "Reaktivierung via scraper_diagnose(scraper_name=..., aktion='reaktivieren')."
            )
        return result

    @mcp.tool()
    def quelle_handoff(quelle: str, keyword: str, ort: str = "") -> dict:
        """Browser-Handoff für blockierte/SPA-tote Quellen (B25/#735).

        Wenn eine Quelle per HTTP nicht scrapbar ist (Bot-Block, SPA-Shell,
        tot), liefert dieses Tool die Such-URL + ein generisches
        Extraktions-JS — Workflow wie bei `google_jobs_url` (#573):
        URL in Chrome mit Claude-in-Chrome öffnen, Treffer per
        javascript_tool() ziehen, mit stelle_manuell_anlegen uebernehmen.

        Für eigene Karriereseiten: erst `custom_quelle_hinzufuegen`,
        dann kommt der Handoff aus `custom_quellen_anzeigen`.

        Args:
            quelle: Quellen-Name (z.B. 'gulp', 'kimeta', 'heise_jobs',
                'stepstone', 'linkedin', 'xing', 'indeed').
            keyword: Suchbegriff.
            ort: Optionaler Ort.
        """
        from ..job_scraper.handoff import build_handoff
        return build_handoff(quelle, keyword, ort)

    @mcp.tool()
    def quellen_langzeit_auswertung(tage: int = 30) -> dict:
        """Langzeit-Auswertung der Job-Quellen (B25/#735, v1.8.0-beta.5).

        Wertet die Lauf-Historie (`scraper_runs`, seit beta.5 automatisch
        mitgeschrieben) pro Quelle aus: Läufe, Treffer, NEUE Stellen,
        Fehlerklassen, Trend (zweite Hälfte vs. erste) und eine klare
        Empfehlung (behalten / beobachten / deaktivieren+Handoff).

        Ergänzt `scraper_diagnose` (aktueller Zustand) um die Zeitachse:
        „Welche Quelle bringt mir seit Wochen nichts mehr?"

        Args:
            tage: Auswertungszeitraum in Tagen (Default 30).
        """
        from datetime import datetime, timedelta
        tage = max(1, min(int(tage or 30), 365))
        seit = (datetime.now() - timedelta(days=tage)).isoformat()
        runs = db.get_scraper_runs(seit_iso=seit)
        if not runs:
            return {
                "status": "keine_daten",
                "hinweis": (
                    "Noch keine Lauf-Historie — sie entsteht ab v1.8.0-beta.5 "
                    "automatisch mit jeder Jobsuche. Nach ein paar Läufen "
                    "erneut aufrufen."
                ),
            }
        per_quelle: dict[str, list] = {}
        for r in runs:
            per_quelle.setdefault(r["scraper_name"], []).append(r)

        auswertung = []
        for name, eintraege in sorted(per_quelle.items()):
            eintraege.sort(key=lambda r: r["run_at"])  # alt -> neu
            n = len(eintraege)
            neu_gesamt = sum(int(r.get("new_count") or 0) for r in eintraege)
            treffer_gesamt = sum(int(r.get("count") or 0) for r in eintraege)
            fehler = [r for r in eintraege if r.get("state") == "fail"]
            klassen: dict[str, int] = {}
            for r in fehler:
                k = r.get("error_class") or "unklassifiziert"
                klassen[k] = klassen.get(k, 0) + 1
            halb = n // 2
            neu_frueh = sum(int(r.get("new_count") or 0) for r in eintraege[:halb]) if halb else 0
            neu_spaet = sum(int(r.get("new_count") or 0) for r in eintraege[halb:])
            if n >= 4 and neu_frueh > 0 and neu_spaet == 0:
                trend = "versiegt"
            elif n >= 4 and neu_spaet > neu_frueh:
                trend = "steigend"
            elif n >= 4:
                trend = "stabil"
            else:
                trend = "zu_wenig_laeufe"
            fehlerquote = round(len(fehler) / n, 2)
            if fehlerquote >= 0.8 and n >= 3:
                empfehlung = ("deaktivieren — dauerhaft fehlerhaft; für "
                              "Einzelrecherchen quelle_handoff nutzen")
            elif neu_gesamt == 0 and n >= 5:
                empfehlung = "beobachten — liefert seit längerem nichts Neues"
            else:
                empfehlung = "behalten"
            auswertung.append({
                "quelle": name,
                "laeufe": n,
                "treffer": treffer_gesamt,
                "neu": neu_gesamt,
                "neu_pro_lauf": round(neu_gesamt / n, 2),
                "fehlerquote": fehlerquote,
                "fehlerklassen": klassen,
                "trend": trend,
                "empfehlung": empfehlung,
            })
        auswertung.sort(key=lambda a: -a["neu"])
        return {
            "zeitraum_tage": tage,
            "quellen": auswertung,
            "hinweis": (
                "Deaktivieren: scraper_diagnose(scraper_name=..., "
                "aktion='deaktivieren'); Browser-Recherche für blockierte "
                "Quellen: quelle_handoff(quelle, keyword)."
            ),
        }

    @mcp.tool()
    def custom_quelle_hinzufuegen(name: str, url: str) -> dict:
        """Eigene Karriereseiten-URL als Handoff-Quelle anlegen (B16/#627).

        BEWUSST kein Auto-Scraping: Karriereseiten sind zu verschieden für
        stabile automatische Extraktion (Master-Plan-Optimierung, B18-
        Begruendung). Stattdessen: PBP prüft die Erreichbarkeit im
        quellen_health_check mit und liefert jederzeit den Browser-Handoff
        (URL + Extraktions-JS) — Claude zieht die Stellen strukturiert und
        legt sie mit stelle_manuell_anlegen an.

        Args:
            name: Sprechender Name (z.B. 'Acme Karriere').
            url: URL der Stellen-/Karriereseite.
        """
        name = (name or "").strip()
        url = (url or "").strip()
        if not name or not url.lower().startswith(("http://", "https://")):
            return {"fehler": "name und eine http(s)-URL sind Pflicht."}
        if any(c["url"].rstrip("/") == url.rstrip("/")
               for c in db.get_custom_sources()):
            return {"fehler": "Diese URL ist bereits als Custom-Quelle angelegt."}
        sid = db.add_custom_source(name, url)
        return {
            "status": "angelegt",
            "quelle_id": sid,
            "name": name,
            "url": url,
            "hinweis": (
                "Recherche starten: custom_quellen_anzeigen() liefert pro "
                "Quelle den Browser-Handoff. Erreichbarkeit wird beim "
                "quellen_health_check mitgeprüft."
            ),
        }

    @mcp.tool()
    def custom_quellen_anzeigen() -> dict:
        """Zeigt eigene Karriereseiten-Quellen inkl. Browser-Handoff (B16/#627)."""
        from ..job_scraper.handoff import build_handoff
        eintraege = db.get_custom_sources()
        quellen = []
        for c in eintraege:
            handoff = build_handoff(c["name"], "", custom_url=c["url"])
            quellen.append({
                "quelle_id": c["id"],
                "name": c["name"],
                "url": c["url"],
                "letzter_check": c.get("last_check_at") or "nie",
                "letzter_status": c.get("last_status") or "",
                "handoff": {k: handoff[k] for k in ("url", "extraction_js", "anleitung")},
            })
        return {
            "anzahl": len(quellen),
            "quellen": quellen,
            "hinweis": (
                "Neue Quelle: custom_quelle_hinzufuegen(name, url); "
                "entfernen: custom_quelle_loeschen(quelle_id)."
            ) if quellen else (
                "Noch keine Custom-Quellen. Anlegen: "
                "custom_quelle_hinzufuegen(name, url)."
            ),
        }

    @mcp.tool()
    def custom_quelle_loeschen(quelle_id: str) -> dict:
        """Entfernt eine Custom-Quelle (B16/#627)."""
        if not db.delete_custom_source(quelle_id):
            return {"fehler": "Custom-Quelle nicht gefunden — IDs zeigt "
                              "custom_quellen_anzeigen()."}
        return {"status": "geloescht", "quelle_id": quelle_id}

    @mcp.tool()
    def quellen_health_check(quellen: list[str] = [], parallel: bool = True,
                             budget_sekunden: int = 90) -> dict:
        """v1.7.0-beta.51 (#624 Phase 2): Aktiver Probe-Check für Job-Quellen.

        Macht pro Quelle einen minimalen HTTP-Request (1 Stelle, keine
        Filter) um zu prüfen ob die API/Feed-Endpoint erreichbar ist.
        Ergänzt scraper_diagnose (das auf Liefer-Statistiken basiert) —
        hier kommt die Info „API selbst erreichbar JA/NEIN" aus einem
        echten Request.

        Args:
            quellen: Liste der zu prüfenden Source-Keys. Wenn leer:
                alle mit definiertem Probe (~12 Quellen).
            parallel: Wenn True (Default), Probes parallel via Threads.
            budget_sekunden: Hartes Wall-Clock-Budget (Default 90s, min 10s).
                Bei Überschreitung kommt ein TEILERGEBNIS zurück
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

        # B16 (#627, v1.8.0-beta.5): Custom-Quellen mit pingen (einfacher
        # HTTP-Erreichbarkeits-Check; Status wird an der Quelle vermerkt).
        custom_results = []
        try:
            custom = db.get_custom_sources()
            if custom:
                import httpx
                for c in custom:
                    # #762: auch die Custom-Pings ans Budget haengen
                    if _time.monotonic() - _start > budget:
                        budget_gerissen = True
                        nicht_geprueft.append(f"custom:{c['name']}")
                        continue
                    eintrag = {"quelle": f"custom:{c['name']}", "url": c["url"]}
                    try:
                        with httpx.Client(timeout=10, follow_redirects=True) as cl:
                            resp = cl.get(c["url"], headers={
                                "User-Agent": "Mozilla/5.0 (PBP Health-Check)"})
                        eintrag["http_status"] = resp.status_code
                        eintrag["reachable"] = resp.status_code < 400
                        status = f"HTTP {resp.status_code}"
                    except Exception as exc:
                        eintrag["reachable"] = False
                        eintrag["error"] = str(exc)[:120]
                        status = f"fehler: {str(exc)[:80]}"
                    db.update_custom_source_status(c["id"], status)
                    custom_results.append(eintrag)
        except Exception as exc:
            logger.debug("Custom-Quellen-Ping uebersprungen: %s", exc)

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
                   "Quelle(n) haben gar keinen Probe — über sie sagt "
                   "dieser Check NICHTS, weder gut noch schlecht. "
                   if any(r.get("error") == "no_probe_defined" for r in results)
                   else "")
                + "Ergänzend zur Liefer-Statistik in scraper_diagnose; "
                "Zeitachse: quellen_langzeit_auswertung(). Blockierte/tote "
                "Quellen per Browser recherchieren: quelle_handoff(quelle, "
                "keyword)."
            ),
        }
        if auffaellig:
            antwort["antwortet_ohne_stellen"] = auffaellig
            antwort["warnung"] = (
                f"{len(auffaellig)} Quelle(n) antworten mit HTTP 200, "
                "liefern aber nichts Verwertbares. Das ist der Fall, den "
                "eine reine Statusprüfung nicht sieht — meist ein "
                "veralteter Endpunkt oder ein falscher Firmen-Slug, keine "
                "Störung. Details je Quelle unter 'antwortet_ohne_stellen'.")
        if custom_results:
            antwort["custom_quellen"] = custom_results
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
                f"{len(nicht_geprueft)} Quelle(n) wurden nicht geprüft "
                f"({', '.join(nicht_geprueft[:8])}"
                f"{' ...' if len(nicht_geprueft) > 8 else ''}). "
                "Die restlichen Ergebnisse sind gültig. Für die offenen "
                "Quellen gezielt nachfassen: quellen_health_check(quellen=[...]) "
                "oder budget_sekunden erhöhen."
            )
        return antwort

    @mcp.tool()
    def quellen_aus_urls_korrigieren(dry_run: bool = True) -> dict:
        """v1.7.0-beta.47 (#613): Korrigiert source='manuell' anhand der job-URL.

        Geht durch alle Stellen mit source='manuell' (egal ob aktiv oder
        aussortiert) und prüft die URL. Wenn die URL einer bekannten
        Quelle zugeordnet werden kann (LinkedIn, StepStone, Indeed, ...),
        wird source umgesetzt.

        Args:
            dry_run: Wenn True (Default), nur Vorschau ohne Änderung.
                     Mit dry_run=False wird tatsächlich geschrieben.

        Returns:
            count_total, count_changed, changes (Liste der geplanten
            oder durchgeführten Änderungen pro Stelle).

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
                "dry_run=False aufrufen um die Änderungen zu speichern."
                if dry_run else
                f"{applied} Stellen umgestellt. Konversion in der Quellen-"
                "Statistik des Bewerbungsbericht jetzt korrekter."
            ),
        }

    @mcp.tool()
    def bewerbungs_stellen_abgleichen(dry_run: bool = True) -> dict:
        """v1.7.9 (#764): Gleicht `applications.job_hash` und `application_jobs` ab.

        Hintergrund: Die Junction-Tabelle aus #472 wurde bei der Migration v34
        EINMALIG befüllt. Seitdem lief beides auseinander — die UI liest
        `applications.job_hash`, `bewerbung_stellen_anzeigen` liest die
        Junction. Folge: nach dem Umhängen einer Bewerbung auf einen Repost
        zeigte die Oberfläche weiter die alte Version mit totem Link.

        Führend ist `application_jobs`. Geheilt werden vier Faelle:

        1. `job_hash` gesetzt, kein Junction-Eintrag -> Eintrag (is_primary=1)
           nachtragen.
        2. Junction vorhanden, `job_hash` leer -> aus der primären
           Verknüpfung zurückschreiben.
        3. Beide gesetzt, aber verschieden -> Junction gewinnt, `job_hash`
           wird darauf gezogen.
        4. Kein oder mehrere `is_primary` pro Bewerbung -> auf genau einen
           normalisieren (jüngste Verknüpfung gewinnt).

        Zusätzlich werden verwaiste Junction-Zeilen gemeldet (Bewerbung oder
        Stelle existiert nicht mehr) — gelöscht werden sie nur mit
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
                                "hinweis": "Junction ist führend"})
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

        Der Bestand ist gewachsen, bevor es die quellenübergreifende
        Erkennung gab. Dieser Lauf gruppiert ihn nachträglich —
        **er schreibt nichts und führt nichts zusammen.**

        Gruppiert wird nur nach nachrechenbaren Merkmalen: identische
        Anzeigen-URL (ohne Tracking-Parameter) oder identischer
        normalisierter Titel bei gleicher Firma. Eine
        Ähnlichkeitsrechnung würde hier schätzen, und die
        Nutzervorgabe lautet Recall vor Praezision: zwei getrennte
        Einträge sind ärgerlich, eine falsch verschmolzene Stelle ist
        schlimmer.

        Für einen bestätigten Fall ist `stelle_mergen` der Weg (#470).

        Args:
            max_stellen: 0 = der ganze Bestand.
        """
        from ..services import stellen_dublette
        ergebnis = stellen_dublette.bestand_pruefen(db, max_stellen=max_stellen)
        # v1.7.127 (#1084 AK 4): zusammengefuehrte Stellen, die wieder
        # aktiv im Bestand stehen. Nur lesend, ohne Auto-Fix.
        try:
            from ..services import stellen_grabstein
            ergebnis["wiedergekehrte_zusammenfuehrungen"] = (
                stellen_grabstein.bericht(db))
        except Exception as e:  # pragma: no cover
            logger.debug("Grabstein-Bericht (#1084): %s", e)
        return ergebnis

    @mcp.tool()
    def stellen_urls_heilen(dry_run: bool = True, nur_aktive: bool = True) -> dict:
        """v1.7.9 (#763): Heilt URL-Qualität im BESTAND (Datenmigration).

        Hintergrund: Der Scraper-Fix aus #645 wirkte nur auf NEUE Läufe —
        das damals angekündigte Akzeptanzkriterium AK5 (Bestands-Heilung)
        wurde nie umgesetzt. Alle vor beta.71 angelegten Stellen tragen die
        Regression bis heute mit (leere URL bzw. Such-URL ohne Markierung).

        Zwei Heilungen, beide ohne Netzzugriff:

        1. **Reklassifizierung** (verlustfrei): `is_search_url` wird aus der
           gespeicherten URL neu bestimmt. Heilt BEIDE Richtungen — Alt-Stellen
           mit Such-URL und Flag=0 werden markiert, und Stellen, die der
           save_jobs-Guard defensiv auf 1 setzte, obwohl inzwischen eine echte
           Detail-URL nachgepflegt wurde, werden wieder freigegeben (das
           entsperrt stellenbeschreibung_nachladen).
        2. **Such-URL nachtragen** bei komplett leerer URL, sofern für die
           Quelle ein Handoff-Template existiert. Ergebnis wird IMMER als
           `is_search_url=1` markiert — nie als Detail-URL ausgegeben.

        EHRLICHE GRENZE: Eine echte Detail-URL lässt sich NICHT rekonstruieren.
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
                "aufrufen, um die Änderungen zu speichern."
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

        Bewerbungen können einen `job_hash` referenzieren, dessen Stelle
        nicht (mehr) in der `jobs`-Tabelle existiert. Folge: stelle_bearbeiten
        scheitert, fit_analyse hat keinen Kontext, kontakt_verknuepfen
        bricht ab (#615).

        Args:
            strategie: 'report' (Default) — nur auflisten ohne Änderung.
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
                                    "rekonstruiert weil die ursprüngliche "
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
        """Wertet gespeicherte Gehälter mit der heutigen Erkennung neu aus
        (#1018).

        Ein besserer Leser hilft nur neuen Stellen — der Bestand behält
        seine Fehltreffer und sieht dabei unauffällig aus. Das ist die
        Lehre aus #998, und sie gilt hier genauso: bis v1.7.78 landete
        "Teilzeit: 30-35 Stunden pro Woche" als Stundensatz von 30 bis 35
        Euro in der Datenbank, **mit `salary_estimated = 0`**, also als
        BELEGT. Seit v1.7.78 zählen belegte Gehälter im Score und
        geschätzte nicht — der falsche Wert ist damit der teurere.

        Am Bestand gemessen: von 12 `stuendlich`-Treffern waren **10 in
        Wahrheit Arbeitszeiten**.

        Angefasst werden nur Stellen mit Anzeigentext. Findet die neue
        Erkennung nichts, wird der alte Wert GELOESCHT statt durch eine
        Schätzung ersetzt — eine Anzeige, die kein Gehalt nennt, hat
        keins, und eine Lücke gehört benannt und nicht gefüllt (#989).

        Args:
            dry_run: Vorgabe True — es wird nichts geschrieben.
            max_stellen: 0 = alle.
        """
        from ..services import gehalt_extraktion as _ge

        conn = db.connect()
        zeilen = conn.execute(
            "SELECT hash, title, description, salary_min, salary_max, "
            "salary_type, salary_estimated FROM jobs "
            "WHERE description IS NOT NULL AND LENGTH(description) > 50 "
            # #1106: nur das aktive Profil — ein echter Lauf aenderte
            # sonst Gehaltsfelder fremder Profile.
            "AND (profile_id=? OR profile_id IS NULL)",
            (db.get_active_profile_id(),)
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
                "job_hash": _kurz(h),
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
                "nennt, wird der alte Wert gelöscht statt geschätzt."
                if dry_run else
                f"{len(aenderungen)} Stelle(n) neu ausgewertet, davon "
                f"{geloescht} ohne Gehaltsangabe in der Anzeige."
            ),
        }

    @mcp.tool()
    def automatik_uebertragungen_pruefen(dry_run: bool = True,
                                         max_stellen: int = 0) -> dict:
        """Findet Stellen, die über ein FREMDES Titel-Muster
        aussortiert wurden (#1020).

        Bis v1.7.79 übertrug die Automatik den häufigsten
        Ablehnungsgrund firmenübergreifend über gemeinsame
        Titel-Tokens — auch `zu_weit_entfernt`, `gehalt_zu_niedrig` und
        `firma_uninteressant`. Das sind Eigenschaften der EINZELNEN
        Anzeige: zwei Stellen mit identischem Titel können 5 km und
        500 km entfernt liegen.

        Gemeldet wurde eine Stelle in **9,2 km**, die als "zu weit
        entfernt" aussortiert wurde — bei einem Wunschwert von 20 km,
        und die Zahl stand in derselben Datenbankzeile wie das Urteil.

        Am hiesigen Bestand gemessen: 245 Zeilen tragen einen
        Wiedergänger-Vermerk, 83 davon (34 %) mit einem Grund, der
        nichts über die Art der Stelle sagt.

        Jede automatisch entfernte Stelle zählte beim nächsten Lauf
        als weiterer Beleg für dasselbe Muster — die Regel konnte nur
        schärfer werden, nie milder. Deshalb ist die Rücknahme mehr
        als Kosmetik: sie nimmt die Belege wieder aus der Grundlage.

        Seit v1.7.92 (#1028) findet der Lauf zwei weitere Fälle, jeder
        mit seinem `befund`:

        * `nur_fuellwoerter` — das Titel-Muster trug allein auf "für",
          "als", "zum" oder einem Datum. Die Stoppwortliste stand in
          Umschrift ("fuer") und griff bei echten Titeln nie.
        * `firmen_platzhalter` — "dieselbe Firma" war ein Platzhalter
          wie "Nicht angegeben". Alle Stellen ohne Firmenangabe galten
          quer über alle Quellen als ein Arbeitgeber.

        Der #1020-Fall heisst `grund_nicht_uebertragbar`.

        Args:
            dry_run: Vorgabe True — es wird nichts geschrieben.
            max_stellen: 0 = alle.
        """
        from ..services import stellen_automatik as _sa
        from ..services import wiedergaenger as _wg

        def _befund(kern: str, firma: str, note: str) -> str:
            """Warum diese Uebertragung nicht haette stattfinden duerfen."""
            if "Fachgebiet" not in note:
                # Stufe 1 "dieselbe Firma" (#1028): mit einem
                # Platzhalter gab es keine Firma, also keinen Bezug.
                return ("firmen_platzhalter"
                        if _wg.ist_firmen_platzhalter(firma) else "")
            if kern not in _sa.UEBERTRAGBARE_GRUENDE:
                return "grund_nicht_uebertragbar"  # #1020
            # #1028: das Muster trug nur auf Fuellwoertern. Die Notiz
            # zeigt hoechstens vier gemeinsame Tokens — bei vier
            # gezeigten koennte ein fuenftes, echtes dahinter stehen,
            # also wird dann NICHT zurueckgeholt.
            m = re.search(r"gemeinsam:\s*([^)]*)\)", note)
            if not m:
                return ""
            gezeigt = [t.strip() for t in m.group(1).split(",") if t.strip()]
            if (gezeigt and len(gezeigt) < 4
                    and not _wg._domain_tokens(" ".join(gezeigt))):
                return "nur_fuellwoerter"
            return ""

        conn = db.connect()
        zeilen = conn.execute(
            "SELECT hash, title, company, dismiss_reason, dismiss_note, "
            "distance_km, salary_min, salary_max, salary_type, "
            "salary_estimated, employment_type FROM jobs "
            "WHERE is_active=0 AND dismiss_note IS NOT NULL "
            "AND (dismiss_note LIKE '%iedergaenger nach Fachgebiet%' "
            "     OR dismiss_note LIKE '%iedergänger nach Fachgebiet%' "
            "     OR dismiss_note LIKE '%iedergaenger: dieselbe Firma%' "
            "     OR dismiss_note LIKE '%iedergänger: dieselbe Firma%') "
            # #1106: nur das aktive Profil.
            "AND (profile_id=? OR profile_id IS NULL)",
            (db.get_active_profile_id(),)
        ).fetchall()

        betroffen, zurueckgeholt = [], 0
        for row in zeilen:
            (h, titel, firma, grund, note, dist, smin, smax, styp,
             sest, emp) = row
            kern = (grund or "").replace("auto:", "").split(":")[0].lower()
            befund = _befund(kern, firma or "", note or "")
            if not befund:
                continue
            job = {"distance_km": dist, "salary_min": smin,
                   "salary_max": smax, "salary_type": styp,
                   "salary_estimated": sest, "employment_type": emp}
            eintrag = {
                "job_hash": _kurz(h),
                "titel": (titel or "")[:60],
                "firma": (firma or "")[:40],
                "grund": kern,
                "befund": befund,
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
                "wurden über ein Titel-Muster einer FREMDEN Firma "
                "aussortiert, auf einem Grund, der nichts über die Art "
                "der Stelle sagt. Mit dry_run=False kommen sie zurück."
                if dry_run else
                f"{zurueckgeholt} Stelle(n) zurückgeholt. Sie zählen "
                "damit auch nicht mehr als Beleg für dasselbe Muster."
            ),
        }

    @mcp.tool()
    def fahrstrecken_verwalten(aktion: str = "status", dry_run: bool = True,
                               max_stellen: int = 0) -> dict:
        """Echte Fahrstrecke und Fahrzeit statt Luftlinie (#950).

        Bis v1.7.93 rechnete PBP nur mit der Luftlinie — beschriftet, aber
        für eine Stelle in 270 km Luftlinie waren es rund 390 km und vier
        Stunden je Richtung. **Für die Frage, ob eine Stelle pendelbar
        ist, sagt die Fahrzeit mehr als jede Kilometerzahl.**

        Mit einem Routing-Schluessel (OpenRouteService, kostenlos) UND
        gesetztem Haken „Echte Fahrstrecke und Fahrzeit verwenden (nur
        Auto)“ berechnet PBP Fahrstrecke und Fahrzeit; Score und
        Gehaltsverrechnung (#910) nehmen dann die Fahrstrecke. **Die
        Berechnung gilt nur fürs Auto**, nicht für Bus und Bahn — sag das
        dazu, wenn du eine Fahrzeit nennst (#1037).

        **Den Schluessel richtest du im Dashboard ein** (Einstellungen › Quellen im Detail, Karte Fahrstrecke), nicht hier: ein Schluessel, der durch den
        Chat geht, stünde danach im Gesprächsverlauf.

        Args:
            aktion: 'status' (Stand, Kontingent, offene Stellen),
                'nachziehen' (Fahrstrecken für vorhandene Stellen),
                'einschalten' oder 'ausschalten' (der Haken; nur auf
                ausdrücklichen Wunsch des Menschen).
            dry_run: Vorgabe True — zeigt nur, was abgefragt würde.
            max_stellen: 0 = alle offenen.
        """
        from ..services import routing as _routing
        from ..services.geocoding_service import (
            geocode_location, get_user_coordinates)

        conn = db.connect()
        pid = db.get_active_profile_id()
        zeilen = [dict(z) for z in conn.execute(
            "SELECT hash, location, lat, lon, distance_km, fahrstrecke_km "
            "FROM jobs WHERE is_active=1 AND (profile_id=? OR profile_id "
            "IS NULL) AND distance_km IS NOT NULL", (pid,)).fetchall()]
        offen = [z for z in zeilen if z["fahrstrecke_km"] is None]
        ohne_koordinaten = sum(1 for z in offen
                               if z["lat"] is None or z["lon"] is None)
        stand = {
            **_routing.status(db),
            "aktive_mit_entfernung": len(zeilen),
            "davon_mit_fahrstrecke": len(zeilen) - len(offen),
            "offen": len(offen),
            "offen_ohne_koordinaten": ohne_koordinaten,
        }
        kein_schluessel = (
            "Im Dashboard unter Einstellungen › Quellen im Detail (Karte Fahrstrecke) "
            "einen kostenlosen Schluessel von OpenRouteService eintragen.")

        aktion = (aktion or "status").strip().lower()
        if aktion in ("einschalten", "ausschalten"):
            ergebnis = _routing.haken_setzen(db, aktion == "einschalten")
            if ergebnis.get("fehler"):
                return {**stand, **ergebnis,
                        "naechster_schritt": kein_schluessel}
            return {**_routing.status(db), **ergebnis}
        if aktion == "status":
            if not stand["konfiguriert"]:
                stand["naechster_schritt"] = kein_schluessel
            elif not stand["haken"]:
                stand["naechster_schritt"] = (
                    f"Schlüssel ist da, der Haken \"{_routing.HAKEN_TEXT}\" "
                    f"aber nicht gesetzt ({_routing.ORT_HAKEN}). Ohne ihn "
                    "rechnet PBP mit der Luftlinie. Auf Wunsch: "
                    "fahrstrecken_verwalten('einschalten').")
            elif offen:
                stand["naechster_schritt"] = (
                    "fahrstrecken_verwalten('nachziehen') — erst die "
                    "Vorschau, dann mit dry_run=False.")
            return stand
        if aktion != "nachziehen":
            return {"fehler": f"Unbekannte Aktion '{aktion}'.",
                    "moegliche_aktionen": ["status", "nachziehen",
                                           "einschalten", "ausschalten"]}
        if not stand["konfiguriert"]:
            return {**stand,
                    "fehler": _routing.BEFUND_TEXT[_routing.KEIN_SCHLUESSEL],
                    "naechster_schritt": kein_schluessel}
        if not stand["aktiv"]:
            return {**stand,
                    "fehler": ("Der Haken für die Fahrstrecke ist nicht "
                               "gesetzt — ohne ihn fragt PBP keine Routen "
                               "ab (#1037)."),
                    "naechster_schritt": (
                        f"Unter {_routing.ORT_HAKEN} den Haken setzen, oder "
                        "auf Wunsch fahrstrecken_verwalten('einschalten').")}
        start = get_user_coordinates(db)
        if not start:
            return {**stand,
                    "fehler": _routing.BEFUND_TEXT[_routing.KEIN_STANDORT],
                    "naechster_schritt": (
                        "suchkriterien_setzen(standort='<Wohnort>') "
                        "hinterlegt den Startpunkt.")}
        if max_stellen and int(max_stellen) > 0:
            offen = offen[:int(max_stellen)]

        if dry_run:
            orte = {(round(z["lat"], 4), round(z["lon"], 4)) for z in offen
                    if z["lat"] is not None and z["lon"] is not None}
            return {
                **stand,
                "status": "vorschau",
                "wuerde_berechnen": len(offen),
                "eindeutige_zielorte": len(orte),
                "davon_erst_geocoden": sum(
                    1 for z in offen if z["lat"] is None or z["lon"] is None),
                "hinweis": (
                    "Vorschau — es wurde nichts abgefragt. Bereits "
                    "zwischengespeicherte Orte kosten keine Anfrage. Stellen "
                    "ohne Koordinaten werden vorher über OpenStreetMap "
                    "aufgelöst (eine Sekunde je Ort). Mit dry_run=False "
                    "geht es los."),
            }

        nachgeholt = 0
        for z in offen:
            if (z["lat"] is None or z["lon"] is None) and z.get("location"):
                koord = geocode_location(z["location"])
                if koord:
                    z["lat"], z["lon"] = koord
                    nachgeholt += 1
        ergebnis = _routing.fuer_stellen(db, offen, start)
        berechnet = 0
        for z in offen:
            if z.get("fahrstrecke_km") is not None:
                berechnet += 1
            db.set_fahrstrecke(z["hash"], z.get("fahrstrecke_km"),
                               z.get("fahrzeit_min"), z.get("route_quelle"),
                               lat=z.get("lat"), lon=z.get("lon"))
        antwort = {
            "status": "nachgezogen",
            "berechnet": berechnet,
            "koordinaten_nachgeholt": nachgeholt,
            "ohne_route": ergebnis["ohne_route"],
            "befund": ergebnis["befund"],
            "befund_text": _routing.BEFUND_TEXT.get(ergebnis["befund"], ""),
            "anfragen_heute": _routing.anfragen_heute(db),
            "tagesgrenze": _routing.TAGESGRENZE,
        }
        if berechnet:
            antwort["naechster_schritt"] = (
                "scores_neu_berechnen() — die Scores nehmen die "
                "Fahrstrecke erst nach einer Neuberechnung.")
        return antwort

    @mcp.tool()
    def stellen_merkmale_nachziehen(dry_run: bool = True,
                                    max_stellen: int = 0) -> dict:
        """Trägt Anstellungsform und Umfang im Altbestand nach (#1023).

        Bis v1.7.83 gab es nur EIN Feld für beides, und der Adapter
        musste sich entscheiden — er wählte die Vertragsart, der Umfang
        fiel weg. Gemessen hat der Melder **0 von 1.282 Stellen mit
        `teilzeit`**, während 103 aktive Titel es nennen.

        Der Lauf liest jede Stelle erneut mit der Erkennung aus
        `services/stellenart.py` und schreibt beide Merkmale. Er ändert
        **nichts an aktiv/ausgeblendet** — eine Stelle, die heute in der
        Liste steht, bleibt dort. Wer seine Auswahl danach anwenden
        will, hat mit den nachgetragenen Merkmalen erst die Grundlage
        dafür.

        Args:
            dry_run: Vorgabe True — zeigt nur, was sich ändern würde.
            max_stellen: 0 = alle.
        """
        from ..services import stellenart as art

        con = db.connect()
        pid = db.get_active_profile_id()
        zeilen = con.execute(
            "SELECT hash, title, description, employment_type, "
            "arbeitsumfang, befristet FROM jobs WHERE profile_id=?",
            (pid,)).fetchall()
        if max_stellen and max_stellen > 0:
            zeilen = zeilen[:max_stellen]

        aenderungen, unveraendert = [], 0
        formen_neu, umfaenge_neu = {}, {}
        for r in zeilen:
            job = {"title": r["title"], "description": r["description"],
                   "employment_type": r["employment_type"],
                   "arbeitsumfang": r["arbeitsumfang"],
                   "befristet": r["befristet"]}
            m = art.merkmale(job)
            alt = (r["employment_type"], r["arbeitsumfang"],
                   1 if r["befristet"] else 0)
            neu = (m["form"], m["umfang"], 1 if m["befristet"] else 0)
            if alt == neu:
                unveraendert += 1
                continue
            if m["form"] != r["employment_type"]:
                formen_neu[m["form"]] = formen_neu.get(m["form"], 0) + 1
            if m["umfang"] != (r["arbeitsumfang"] or ""):
                umfaenge_neu[m["umfang"]] = umfaenge_neu.get(m["umfang"], 0) + 1
            aenderungen.append({
                "hash": db._public_job_hash(r["hash"]),
                "titel": (r["title"] or "")[:60],
                "vorher": {"form": r["employment_type"],
                           "umfang": r["arbeitsumfang"]},
                "nachher": {"form": m["form"], "umfang": m["umfang"],
                            "befristet": m["befristet"]},
                "beleg": m["umfang_beleg"] or m["form_beleg"],
            })
            if not dry_run:
                con.execute(
                    "UPDATE jobs SET employment_type=?, arbeitsumfang=?, "
                    "befristet=? WHERE hash=?",
                    (m["form"], m["umfang"], 1 if m["befristet"] else 0,
                     r["hash"]))
        if not dry_run:
            con.commit()

        return {
            "status": "vorschau" if dry_run else "nachgetragen",
            "geprueft": len(zeilen),
            "geaendert": len(aenderungen),
            "unveraendert": unveraendert,
            "neue_formen": dict(sorted(formen_neu.items(),
                                       key=lambda p: -p[1])),
            "neue_umfaenge": dict(sorted(umfaenge_neu.items(),
                                         key=lambda p: -p[1])),
            "stichprobe": aenderungen[:15],
            "hinweis": (
                "Vorschau — es wurde nichts geschrieben. Mit "
                "dry_run=False werden beide Merkmale nachgetragen; "
                "aktiv/ausgeblendet bleibt unangetastet."
                if dry_run else
                f"{len(aenderungen)} Stelle(n) nachgetragen. Der Umfang "
                "sortiert nichts aus — er wird angezeigt und ist "
                "filterbar."
            ),
        }
