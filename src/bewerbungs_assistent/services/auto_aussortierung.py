"""Die Auto-Aussortierung durch die lokale KI — EIN Weg (#1092).

Bis v1.7.139 gab es zwei Fassungen: das Werkzeug
`stellen_auto_aussortieren` und eine aeltere Schleife, die nach jeder
Jobsuche ueber Claude lief (`_maybe_auto_dismiss_after_search`). Das
Werkzeug wurde seit beta.63 nachgezogen, die Schleife nicht:

* sie beurteilte Stellen OHNE Anzeigentext — die KI riet auf den Titel
  (#756 hatte genau das im Werkzeug abgestellt);
* sie setzte bei "PASST" und duennem Text den Score fest auf 35 — eine
  Zahl ohne Bezug zur Punkteskala (#999), die `fach_score` nicht
  mitnahm und eine Stelle ohne Beschreibung ueber fachlich passende hob
  (#989, C96);
* sie lief ohne Schalter (Vorgabe "an") und nur auf einem Startweg.

Jetzt ruft der Weg nach der Suche genau `aussortieren` auf, und der
Schalter steht unter Einstellungen › Automatik, Vorgabe AUS.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("bewerbungs_assistent.auto_aussortierung")

SCHALTER = "auto_dismiss_after_search"


def schalter_an(db) -> bool:
    """Nur ein ausdruecklich gesetztes "an" zaehlt (#1092 AK 4)."""
    wert = db.get_profile_setting(SCHALTER, None)
    return str(wert).lower() in ("true", "1", "yes", "on", "an")


def schalter_gesetzt(db) -> bool:
    return db.get_profile_setting(SCHALTER, None) is not None


def profil_kontext(profile: dict) -> dict:
    """Skills, Position und Karrierestufe, so wie sie in den Prompt gehen.

    EINE Quelle fuer den Lauf (`aussortieren`) und die Messprobe (`scripts/api_probe.py`, #1236): ein zweiter
    Rechenweg fuer "dasselbe" haette die Probe etwas anderes messen lassen als den echten Lauf.
    """
    profile = profile or {}
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
        profile_seniority = "Berufseinsteiger / Berufsanfänger"
    return {"profile_skills": profile_skills, "profile_position": profile_position,
            "profile_seniority": profile_seniority}


def gruende_top(db) -> list[dict]:
    """Die drei haeufigsten Aussortier-Gruende fuer den Prompt (v1.7.0-beta.28, #594 Stufe 3). Leer bei jedem Fehler."""
    try:
        conn = db.connect()
        pid = db.get_active_profile_id()
        from .ablehnungsgruende import gruende_zaehlen
        liste, _ = gruende_zaehlen(conn, pid, ausser=())
        return [{"reason": g, "count": n} for g, n in liste[:3]]
    except Exception:
        return []


def _api_weg_nutzbar(db) -> bool:
    """#1236: darf diese Aufgabe gerade ueber die freigegebene Anthropic-API laufen? Sonst nichts Neues."""
    try:
        from . import api_backend
        return api_backend.zustand(db, "match_job_to_skills").erlaubt
    except Exception:  # noqa: BLE001 -- ohne Auskunft gilt der bisherige Weg
        return False


def aussortieren(db, max_stellen: int = 10, min_score: int = 0,
                 dry_run: bool = False, max_dauer_sek: int = 50,
                 obergrenze_stellen: int = 30,
                 obergrenze_dauer: int = 90) -> dict:
    """Profil-basiertes Aussortieren via lokaler KI. Schema wie beim
    Werkzeug `stellen_auto_aussortieren`, das hierher weiterreicht."""
    import time as _time
    run_started_at = _time.monotonic()
    # Defensive Caps (#646, #691): Der MCP-Client (Claude Desktop) bricht
    # einen Tool-Call schon nach ~60s ab. Ein laengerer Lauf wird dann
    # gecancelt und FastMCP 3.x liefert "outputSchema defined but no
    # structured output returned" statt eines sauberen Teil-Ergebnisses.
    # Darum Budget-Default 50s (cap 90s); der Wall-Clock-Check unten gibt
    # VOR dem Client-Timeout ein schemakonformes status='teilweise' zurueck.
    max_stellen = max(1, min(int(max_stellen or 10), obergrenze_stellen))
    max_dauer_sek = max(20, min(int(max_dauer_sek or 50), obergrenze_dauer))
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
        from .llm_service import get_llm_service, TaskKind, Backend

        svc = get_llm_service(db)
        # #1236: hat der Mensch diese Aufgabe fuer die API freigegeben und ist der Weg nutzbar
        # (Schluessel, KI-Schalter, Budget), braucht der Lauf kein Ollama. Sonst gilt alles wie bisher.
        api_weg = _api_weg_nutzbar(db)
        status = svc.get_status(force_refresh=not api_weg)
        if not api_weg:
            if not status.ollama_available or not status.available_models:
                return _err(
                    "Lokale AI nicht verfügbar.",
                    hinweis="stellen_auto_aussortieren braucht Ollama + ein installiertes Modell. Prüfe Einstellungen › Lokale KI.",
                )
            if status.user_state != "active":
                return _err(
                    f"Lokale AI ist im State '{status.user_state}'.",
                    hinweis="Setze State auf 'active' in Einstellungen › Lokale KI.",
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
    kontext = profil_kontext(profile)
    profile_skills = kontext["profile_skills"]
    profile_position = kontext["profile_position"]
    profile_seniority = kontext["profile_seniority"]

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
    dismiss_reasons_top = gruende_top(db)

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
                    "Erst stellenbeschreibung_nachladen(hash) für die "
                    "übersprungenen Stellen, dann erneut aufrufen."
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
    # #1236: was der API-Weg in diesem Lauf getan hat (Testdoppel ohne backend/metrics bleiben moeglich)
    api_aufrufe = 0
    sonst_aufrufe = 0
    api_mikro = 0
    api_modell = ""
    api_hinweis = None

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
            metriken = getattr(result, "metrics", None) or {}
            ueber_api = getattr(result, "backend", None) == Backend.API
            if ueber_api:
                api_aufrufe += 1
                api_mikro += int(metriken.get("kosten_mikro_usd") or 0)
                api_modell = metriken.get("model") or api_modell
            elif result.success:
                sonst_aufrufe += 1
            if api_hinweis is None and metriken.get("api_grund"):
                api_hinweis = metriken["api_grund"]
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
                reason = ("(die API lieferte keine Begruendung)" if ueber_api
                          else "(lokale KI lieferte keine Begruendung)")
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
                            notiz=f"[Auto-Aussortierung] {reason}",
                            # #1092: das Urteil ist das der lokalen KI,
                            # nicht des Menschen (#1010). Vorher trug
                            # dieser Weg die Vorgabe "ich".
                            herkunft="automatik")
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
    if api_aufrufe or api_hinweis:
        # Nur wenn der API-Weg im Spiel war; ohne ihn bleibt die Antwort, wie sie war.
        from . import api_backend
        # "keiner": die API war freigegeben, hat aber nichts geliefert, und nichts anderes sprang ein
        result_payload["ki_weg"] = (("api" if not sonst_aufrufe else "gemischt") if api_aufrufe
                                    else ("lokal" if sonst_aufrufe else "keiner"))
        if api_aufrufe:
            result_payload["modell"] = api_modell or modell_name
            result_payload["api"] = {"aufrufe": api_aufrufe, "kosten": api_backend.usd_text(api_mikro),
                                     "modell": api_modell}
        if api_hinweis:
            result_payload["api_hinweis"] = api_hinweis
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
            "Urteil. Nächster Schritt: stellenbeschreibung_nachladen(hash)."
        )
    return result_payload


def nach_suche(db, job_id: str) -> dict | None:
    """Nach einer erfolgreichen Suche — beide Startwege (#1092 AK 5).

    Laeuft nur mit eingeschaltetem Schalter, aktiver lokaler KI und
    fertigem Suchlauf. Das Ergebnis steht danach im Such-Job unter
    `auto_aussortiert`, damit der Lauf-Hinweis es nennen kann."""
    if not schalter_an(db):
        logger.info("Auto-Aussortierung nach der Suche: Schalter aus")
        return None
    job = db.get_background_job(job_id)
    if not job or job.get("status") not in ("fertig", "erledigt"):
        return None
    # Im Hintergrund gibt es kein MCP-Zeitlimit — groesseres Budget.
    erg = aussortieren(db, max_stellen=30, dry_run=False,
                       max_dauer_sek=300, obergrenze_dauer=300)
    try:
        job = db.get_background_job(job_id) or {}
        result = job.get("result") if isinstance(job.get("result"), dict) else {}
        result["auto_aussortiert"] = {
            "status": erg.get("status"),
            "geprueft": erg.get("geprueft", 0),
            "aussortiert": erg.get("passt_nicht", 0),
            "ohne_beschreibung": erg.get("uebersprungen_ohne_beschreibung", 0),
        }
        db.update_background_job(job_id, job.get("status", "fertig"),
                                 progress=job.get("progress", 100),
                                 message=job.get("message", ""), result=result)
    except Exception as exc:
        logger.warning("Auto-Aussortierung: Ergebnis nicht gespeichert: %s", exc)
    return erg
