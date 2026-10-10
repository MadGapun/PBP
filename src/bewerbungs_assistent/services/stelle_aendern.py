"""Eine Stelle bearbeiten — mit Neuberechnung, an EINER Stelle (#1095).

`stelle_bearbeiten` rechnete nach einer geaenderten Beschreibung oder
einem geaenderten Titel neu (#535); `PUT /api/jobs/{hash}` schrieb nur die
Felder. Wer im Dashboard eine Beschreibung korrigierte, behielt die alten
Punkte und Faktoren, und ein neuer Ort behielt die Entfernung des alten.

Ein geaenderter Ort rechnet die Entfernung neu, wenn sie nicht von Hand
gesetzt ist: ueber die gemerkten Orte (#1090), sonst "unbekannt" — die
Entfernung des alten Ortes stehen zu lassen waere eine falsche Angabe.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Was der Mensch an einer Stelle aendern darf.
FELDER = ("title", "company", "location", "description", "url")


def _neue_entfernung(db, job_hash: str) -> float | None:
    """Rechnet die Entfernung zum neuen Ort — oder setzt sie auf unbekannt."""
    from . import eigener_standort
    from .geocoding_service import calculate_distance_km, geocode_location
    job = db.get_job(job_hash) or {}
    start = eigener_standort._koordinaten(db)
    ziel = geocode_location(job.get("location") or "") if start else None
    if not ziel:
        db.set_job_entfernung(job_hash, None)
        return None
    km = calculate_distance_km(start, ziel)
    con = db.connect()
    con.execute(
        "UPDATE jobs SET distance_km=?, lat=?, lon=?, entfernung_am=?, entfernung_quelle=NULL, "
        "fahrstrecke_km=NULL, fahrzeit_min=NULL, route_quelle=NULL WHERE hash=?",
        (km, ziel[0], ziel[1], eigener_standort._jetzt(), db.resolve_job_hash(job_hash)))
    con.commit()
    return km


def _vorbehalt_aufheben(db, job_hash: str, vorher: dict) -> dict | None:
    """Das Original einer Google-Stelle liegt jetzt vor (#1184): Arbeitsmodell und Entfernung nachholen.

    Vorher standen beide unter Googles Vorbehalt (`google_angaben`): `unbekannt` und keine Entfernung. Jetzt
    entscheidet der Text, und der Ort zaehlt. Es wird nur nachgeholt, was fehlt: ein Wert, den der Text nicht
    bestimmt, bleibt wie er ist, und eine von Hand gesetzte Entfernung bleibt.
    """
    from . import google_angaben, remote_jobspy
    if not google_angaben.unter_vorbehalt(vorher.get("source"), vorher.get("url"), vorher.get("description")):
        return None
    jetzt = db.get_job(job_hash) or {}
    if google_angaben.unter_vorbehalt(jetzt.get("source"), jetzt.get("url"), jetzt.get("description")):
        return None
    ergebnis: dict = {}
    stufe = remote_jobspy.bestimmen(jetzt.get("title"), jetzt.get("location"), jetzt.get("description"))
    bisher = jetzt.get("remote_level") or "unbekannt"
    if stufe != "unbekannt" and stufe != bisher and db.set_job_remote_level(job_hash, stufe):
        ergebnis["remote"] = {"vorher": bisher, "jetzt": stufe}
    if jetzt.get("distance_km") is None and str(jetzt.get("location") or "").strip():
        km = _neue_entfernung(db, job_hash)
        ergebnis["entfernung_km"] = km
    ergebnis["hinweis"] = ("Das Original liegt vor: Arbeitsmodell und Entfernung gelten jetzt nach Text und Ort der "
                           "Anzeige, nicht mehr nach Googles Karte.")
    return ergebnis


def _luftlinie(km) -> str:
    """Nie die blosse Zahl — sie wird als Wegstrecke gelesen (#950)."""
    from .entfernung import beschriftung
    return beschriftung(km) or f"{km} km"


def aendern(db, job_hash: str, felder: dict, entfernung_km=None,
            entfernung_zuruecksetzen: bool = False) -> dict:
    """Aendert eine Stelle und rechnet nach. `felder` traegt Schluessel aus
    FELDER; leere und unveraenderte Werte bleiben unberuehrt."""
    resolved = db.resolve_job_hash(job_hash)
    job = db.get_job(resolved) if resolved else None
    if not job:
        return {"ok": False, "grund": "nicht_gefunden",
                "fehler": "Stelle nicht gefunden. Prüfe den Hash mit stellen_anzeigen()."}
    if entfernung_km is not None and entfernung_zuruecksetzen:
        return {"ok": False, "grund": "eingabe",
                "fehler": "entfernung_km und entfernung_zuruecksetzen schliessen sich aus."}
    if entfernung_km is not None and entfernung_km < 0:
        return {"ok": False, "grund": "eingabe",
                "fehler": ("entfernung_km darf nicht negativ sein. Zum "
                           "Zurücksetzen entfernung_zuruecksetzen=True.")}

    updates = {}
    for k in FELDER:
        wert = (felder or {}).get(k)
        if isinstance(wert, str) and wert.strip() and wert != (job.get(k) or ""):
            updates[k] = wert
    if "url" in updates:
        from ..job_scraper import is_search_result_url
        updates["is_search_url"] = is_search_result_url(updates["url"])
    entfernung_geaendert = entfernung_km is not None or entfernung_zuruecksetzen
    if not updates and not entfernung_geaendert:
        return {"ok": False, "grund": "leer", "fehler": "Keine Änderungen angegeben."}

    if updates:
        db.update_job(resolved, updates)
    ergebnis = {"ok": True, "job": job, "updates": updates}
    if entfernung_geaendert:
        db.set_job_entfernung(resolved, None if entfernung_zuruecksetzen else entfernung_km)
    elif "location" in updates:
        alt_km = job.get("distance_km")
        if job.get("entfernung_quelle") == "mensch":
            # Von Hand gesetzt: bleibt, aber gesagt wird es.
            ergebnis["entfernung_text"] = (
                f"Deine eingetragene Entfernung ({alt_km} km) bleibt.")
            ergebnis["entfernung_hinweis"] = (
                f"Die von dir gesetzte Entfernung ({alt_km} km) bleibt. Gilt sie "
                "für den neuen Ort nicht mehr: entfernung_km setzen oder "
                "entfernung_zuruecksetzen=True.")
        else:
            neu = _neue_entfernung(db, resolved)
            entfernung_geaendert = True
            vorher = f" (vorher {alt_km} km zum bisherigen Ort)" if alt_km is not None else ""
            ergebnis["entfernung_neu_km"] = neu
            ergebnis["entfernung_text"] = (
                f"Entfernung zum neuen Ort: {_luftlinie(neu)}." if neu is not None else
                "Den neuen Ort kennt PBP noch nicht — die Entfernung steht auf unbekannt.")
            ergebnis["entfernung_hinweis"] = (
                f"Entfernung zum neuen Ort: {_luftlinie(neu)}{vorher}." if neu is not None else
                f"Den neuen Ort kennt PBP noch nicht — die Entfernung steht jetzt "
                f"auf unbekannt{vorher}. Wenn du sie weißt: entfernung_km setzen.")

    # #1184: das Original einer Google-Stelle ist jetzt da - Arbeitsmodell und Entfernung nachholen.
    nachgeholt = _vorbehalt_aufheben(db, resolved, job) if updates else None
    if nachgeholt:
        ergebnis["google_vorbehalt_aufgehoben"] = nachgeholt
        entfernung_geaendert = entfernung_geaendert or "entfernung_km" in nachgeholt

    if "description" in updates or "title" in updates or entfernung_geaendert or nachgeholt:
        try:
            from ..job_scraper import calculate_score
            from . import scoring_kriterien
            criteria = scoring_kriterien.fuer_scoring(db)  # #987, #1051
            frisch = db.get_job(resolved) or {}
            neu = calculate_score(frisch, criteria)
            if neu is not None:
                db.update_job(resolved, {"score": neu,
                                         "fachscore": frisch.get("_fachscore"),
                                         "rahmenscore": frisch.get("_rahmenscore")})
                neu_info = {"alter_score": job.get("score"), "neuer_score": neu}
                if neu == 0 and frisch.get("_ko_ausschluss"):
                    neu_info["grund"] = (
                        f"Ausschluss-Keyword '{frisch['_ko_ausschluss']}' kommt im neuen "
                        "Text vor — das setzt den Score hart auf 0. Wenn das ein "
                        "Fehltreffer ist, das Keyword in den Suchkriterien schärfen "
                        "(suchkriterien_anzeigen).")
                elif neu == 0 and frisch.get("_ko_kein_muss"):
                    neu_info["grund"] = (
                        "Kein MUSS-Keyword im neuen Text gefunden — das setzt den Score "
                        "auf 0. Prüfe die MUSS-Keywords (suchkriterien_anzeigen) oder "
                        "ob der Text vollständig ist.")
                ergebnis["score_neu_berechnet"] = neu_info
        except Exception as exc:  # noqa: BLE001
            logger.warning("Score-Neuberechnung fuer %s fehlgeschlagen: %s", resolved, exc)
    ergebnis["entfernung_geaendert"] = entfernung_geaendert
    return ergebnis
