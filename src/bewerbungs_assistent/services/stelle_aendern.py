"""Eine Stelle bearbeiten — mit Neuberechnung, an EINER Stelle (#1095).

`stelle_bearbeiten` rechnete nach einer geaenderten Beschreibung oder
einem geaenderten Titel neu (#535); `PUT /api/jobs/{hash}` schrieb nur die
Felder. Wer im Dashboard eine Beschreibung korrigierte, behielt die alten
Punkte und Faktoren, und ein neuer Ort behielt die Entfernung des alten.

Ein geaenderter Ort rechnet die Entfernung neu, wenn sie nicht von Hand
gesetzt ist: ueber die gemerkten Orte (#1090), sonst "unbekannt" — die
Entfernung des alten Ortes stehen zu lassen waere eine falsche Angabe.

#1299: auch Anstellungsform (`employment_type`), Umfang (`arbeitsumfang`) und
Remote-Stufe (`remote_level`) sind aenderbar — jeweils gegen ihr Vokabular
geprueft (`stellenart.form_pruefen`, `stellenart.umfang_pruefen`,
`remote_jobspy.normalisieren`), Ungueltiges wird abgelehnt. Ein so gesetzter
Wert gilt dauerhaft (`<merkmal>_quelle = 'mensch'`, wie die Entfernung):
kein Suchlauf und kein Nachzieh-Lauf ueberschreibt ihn. "unbekannt" bei
Remote oder Umfang gibt das Merkmal an die Automatik zurueck. Danach werden
Punkte und Rahmenzahl neu gerechnet; der Rahmendaumen (Grenze, Gehalt,
Farbe) liest die Merkmale ohnehin beim Anzeigen.

Ein geaenderter Titel, Ort oder Text fuellt eine unbekannte Remote-Stufe
("100 % remote" im Ort -> `remote`) und ersetzt einen Wert ausserhalb des
Vokabulars; eine gueltige Angabe der Quelle bleibt (#1184).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Was der Mensch an einer Stelle aendern darf.
FELDER = ("title", "company", "location", "description", "url",
          "employment_type", "arbeitsumfang", "remote_level")

#: #1299: die Merkmale unter FELDER — geprueft, nicht frei.
MERKMALE = ("employment_type", "arbeitsumfang", "remote_level")


def merkmal_pruefen(feld: str, wert) -> tuple[str, str | None]:
    """`(wert, fehler)` — der Wert im Vokabular, oder ein Fehlertext fuer den Menschen."""
    from . import remote_jobspy, stellenart
    if feld == "employment_type":
        form, hinweis = stellenart.form_pruefen(wert)
        return (form, None) if form else ("", hinweis or "Anstellungsform fehlt.")
    if feld == "arbeitsumfang":
        umfang, hinweis = stellenart.umfang_pruefen(wert)
        return (umfang, None) if umfang else ("", hinweis or "Umfang fehlt.")
    if feld == "remote_level":
        stufe, hinweis = remote_jobspy.normalisieren(wert)
        if hinweis:
            return "", (f"„{str(wert)[:60]}“ ist keine Remote-Angabe. Gültig sind: "
                        f"{', '.join(remote_jobspy.STUFEN)}.")
        return stufe, None
    return "", f"{feld} ist kein Merkmal."


def _score_neu(db, resolved: str, criteria=None) -> tuple:
    """Punkte und Rahmenzahl einer Stelle neu: `(neu, frisch)` — `neu` None, wenn nichts gerechnet wurde."""
    from ..job_scraper import calculate_score
    from . import scoring_kriterien
    if criteria is None:
        criteria = scoring_kriterien.fuer_scoring(db)  # #987, #1051
    frisch = db.get_job(resolved) or {}
    if not frisch:
        return None, frisch
    neu = calculate_score(frisch, criteria)
    if neu is not None:
        db.update_job(resolved, {"score": neu,
                                 "fachscore": frisch.get("_fachscore"),
                                 "rahmenscore": frisch.get("_rahmenscore")})
    return neu, frisch


def neu_bewerten(db, hashes) -> int:
    """Punkte mehrerer Stellen neu (#1298/#1299) — die Kriterien einmal je Aufruf. Liefert die Anzahl."""
    from . import scoring_kriterien
    hashes = [h for h in (hashes or []) if h]
    if not hashes:
        return 0
    criteria = scoring_kriterien.fuer_scoring(db)
    n = 0
    for h in hashes:
        try:
            neu, _ = _score_neu(db, h, criteria)
            n += neu is not None
        except Exception as exc:  # noqa: BLE001 - eine Stelle kippt nicht die anderen
            logger.warning("Neubewertung fuer %s fehlgeschlagen: %s", h, exc)
    return n


def _remote_neu(db, resolved: str) -> dict | None:
    """Nach einer Text- oder Ortsaenderung die Remote-Stufe neu bestimmen (#1299 Punkt 6).

    Nur, wenn sie nicht von Hand gesetzt ist, und nur als LUECKE: steht `unbekannt` da, fuellt der Text sie;
    steht ein Wert ausserhalb des Vokabulars da ("True" aus #1298), wird er immer ersetzt. Eine gueltige
    Angabe der Quelle bleibt (#1184: "nur Google-Stellen holen das Arbeitsmodell nach") — wer sie aendern
    will, setzt `remote` ausdruecklich, und dann gilt sie als Handkorrektur.
    """
    from . import remote_jobspy
    jetzt = db.get_job(resolved) or {}
    if jetzt.get("remote_quelle") == "mensch":
        return None
    bisher = jetzt.get("remote_level") or "unbekannt"
    stufe = remote_jobspy.bestimmen(jetzt.get("title"), jetzt.get("location"), jetzt.get("description"))
    ungueltig = bisher not in remote_jobspy.STUFEN
    if not (ungueltig or bisher == "unbekannt"):
        return None
    if (stufe != "unbekannt" or ungueltig) and stufe != bisher:
        if db.set_job_remote_level(resolved, stufe):
            return {"vorher": bisher, "jetzt": stufe}
    return None


def _neue_entfernung(db, job_hash: str) -> float | None:
    """Rechnet die Entfernung zum neuen Ort — oder setzt sie auf unbekannt."""
    from . import eigener_standort
    from .geocoding_service import calculate_distance_km, geocode_location
    job = db.get_job(job_hash) or {}
    start = eigener_standort._koordinaten(db)
    ziel = geocode_location(job.get("location") or "") if start else None
    if start and not ziel:
        # #1235: ein mehrdeutiger Ort wird mit PLZ oder Bundesland aus dem Anzeigentext noch einmal gefragt.
        from .geocoding_service import entfernung_aus_anzeige
        genau = entfernung_aus_anzeige(
            job.get("location") or "", start[0], start[1], job.get("description") or "")
        ziel = genau["koordinaten"] if genau else None
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
    merkmale: dict = {}
    for k in FELDER:
        wert = (felder or {}).get(k)
        if k in MERKMALE:
            # #1299: geprueft gegen das Vokabular; True/False fuer Remote zaehlen als Angabe.
            if wert is None or (isinstance(wert, str) and not wert.strip()):
                continue
            gueltig, fehler = merkmal_pruefen(k, wert)
            if fehler:
                return {"ok": False, "grund": "eingabe", "fehler": fehler}
            freigeben = k != "employment_type" and gueltig == "unbekannt"
            schon_so = gueltig == (job.get(k) or "") and (
                (job.get(db.MERKMAL_QUELLE[k]) == "mensch") != freigeben)
            if not schon_so:
                merkmale[k] = (gueltig, freigeben)
            continue
        if isinstance(wert, str) and wert.strip() and wert != (job.get(k) or ""):
            updates[k] = wert
    if "url" in updates:
        from ..job_scraper import is_search_result_url
        updates["is_search_url"] = is_search_result_url(updates["url"])
    entfernung_geaendert = entfernung_km is not None or entfernung_zuruecksetzen
    if not updates and not entfernung_geaendert and not merkmale:
        return {"ok": False, "grund": "leer", "fehler": "Keine Änderungen angegeben."}

    if updates:
        db.update_job(resolved, updates)
    for k, (wert, freigeben) in merkmale.items():
        db.set_job_merkmal_hand(resolved, k, wert, freigeben=freigeben)
        updates[k] = wert
    ergebnis = {"ok": True, "job": job, "updates": updates}
    if merkmale:
        ergebnis["merkmale"] = {
            k: {"vorher": job.get(k), "jetzt": w,
                "quelle": "automatik" if frei else "mensch"}
            for k, (w, frei) in merkmale.items()}
        if any(not frei for _, frei in merkmale.values()):
            ergebnis["merkmale_hinweis"] = (
                "Von Hand gesetzt — kein Suchlauf überschreibt diesen Wert. Mit „unbekannt“ "
                "(Remote, Umfang) gibst du ihn an die Automatik zurück.")
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

    # #1299: neuer Titel, Ort oder Text -> Remote-Stufe neu, solange sie nicht von Hand gesetzt ist.
    remote_neu = None
    if ({"title", "location", "description"} & set(updates)) and "remote_level" not in merkmale \
            and not (nachgeholt and "remote" in nachgeholt):
        remote_neu = _remote_neu(db, resolved)
        if remote_neu:
            ergebnis["remote_neu"] = remote_neu

    if ("description" in updates or "title" in updates or entfernung_geaendert or nachgeholt
            or merkmale or remote_neu):
        try:
            neu, frisch = _score_neu(db, resolved)
            if neu is not None:
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
