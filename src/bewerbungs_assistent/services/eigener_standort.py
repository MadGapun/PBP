"""Von wo aus PBP Entfernungen rechnet (#1090).

Bis v1.7.139 rechnete PBP eine Entfernung nur, wenn in den Suchkriterien
Koordinaten standen — gesetzt allein von `suchkriterien_setzen(standort=…)`.
Im Dashboard gab es kein Feld dafuer, keine Anleitung fragte danach, und
der Wohnort aus dem Profil (PLZ, Ort, Adresse) zaehlte nicht. Wer PBP ueber
das Dashboard einrichtete, hatte an keiner Stelle eine Entfernung, und der
Suchlauf uebersprang sie still.

Die Regeln:

* **Ein ausdruecklich gesetzter Standort gewinnt** (`quelle = "eigene"`).
  Sonst gilt der Wohnort aus dem Profil (`quelle = "profil"`).
* **Aufgeloest wird beim Speichern, nie beim Lesen.** Ein Score darf nicht
  am Netz haengen (v1.7.36 MERKE 3). Die Kriterien tragen danach Ort,
  Quelle und Koordinaten; gelesen wird nur das.
* **Aendert sich der Standort, werden die gespeicherten Entfernungen
  neu gerechnet** — im Hintergrund, mit Eintrag in `background_jobs`,
  einer Anfrage je VERSCHIEDENEM Ort (#1057). Von Hand gesetzte
  Entfernungen bleiben (#1077). Fahrstrecken zum alten Ort sind danach
  falsch und werden verworfen (#950).
* **Fehlende Entfernungen werden nachgeholt**, begrenzt je Lauf. Ein Ort,
  den der Dienst nicht kennt, steht im dauerhaften Speicher und wird
  nicht jedes Mal neu gefragt; ein Ausfall des Dienstes zaehlt nicht als
  Befund (#950, #811).
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger("bewerbungs_assistent.eigener_standort")

EIGENE = "eigene"
PROFIL = "profil"
NACHHOLEN_JE_LAUF = 40   # verschiedene Orte je Nachhol-Lauf


def wohnort_aus_profil(profil: dict | None) -> str:
    """"PLZ Ort", sonst Ort, sonst Adresse."""
    if not profil:
        return ""
    plz = str(profil.get("plz") or "").strip()
    ort = str(profil.get("city") or "").strip()
    if ort:
        return f"{plz} {ort}".strip()
    return str(profil.get("address") or "").strip()


def befund(db) -> dict:
    """Welcher Ort gilt, woher er kommt, ob er aufgeloest ist. Liest nur."""
    k = db.get_search_criteria() or {}
    lat, lon = k.get("standort_lat"), k.get("standort_lon")
    quelle = k.get("standort_quelle") or (EIGENE if lat and lon else None)
    try:
        profil_ort = wohnort_aus_profil(db.get_profile())
    except Exception:
        profil_ort = ""
    if not quelle and profil_ort:
        # Wohnort steht im Profil, ist aber (noch) nicht aufgeloest.
        quelle = PROFIL
    return {
        "ort": k.get("standort_ort") or (profil_ort if quelle == PROFIL else ""),
        "quelle": quelle,
        "aufgeloest": bool(lat and lon),
        "profil_wohnort": profil_ort,
    }


def _setzen(db, ort: str, quelle: str, coords) -> None:
    db.set_search_criteria("standort_ort", ort)
    db.set_search_criteria("standort_quelle", quelle)
    db.set_search_criteria("standort_lat", coords[0] if coords else None)
    db.set_search_criteria("standort_lon", coords[1] if coords else None)


def _koordinaten(db):
    k = db.get_search_criteria() or {}
    lat, lon = k.get("standort_lat"), k.get("standort_lon")
    return (float(lat), float(lon)) if lat and lon else None


def aus_profil_uebernehmen(db, neu_rechnen: bool = True) -> dict:
    """Den Wohnort aus dem Profil als Standort nehmen — nur wenn keiner
    ausdruecklich gesetzt ist. Aufzurufen beim SPEICHERN des Profils und
    vor einem Suchlauf; darf ins Netz."""
    from .geocoding_service import geocode_location
    b = befund(db)
    if b["quelle"] == EIGENE:
        return {"geaendert": False, "grund": "eigener Standort gesetzt"}
    ort = b["profil_wohnort"]
    if not ort:
        return {"geaendert": False, "grund": "kein Wohnort im Profil"}
    vorher = _koordinaten(db)
    if b["quelle"] == PROFIL and (db.get_search_criteria() or {}).get("standort_ort") == ort and vorher:
        return {"geaendert": False, "grund": "unverändert"}
    coords = geocode_location(ort)
    if not coords:
        # Nicht aufgeloest: nichts schreiben. Ein Standort ohne Koordinaten
        # rechnet nichts, und leere Kriterien sollen leer bleiben (#927).
        # Der Befund nennt den Wohnort trotzdem als "nicht aufgeloest".
        return {"geaendert": False, "aufgeloest": False, "ort": ort}
    _setzen(db, ort, PROFIL, coords)
    geaendert = coords != vorher
    if geaendert and coords and neu_rechnen:
        neu_rechnen_starten(db, alle=True)
    return {"geaendert": geaendert, "aufgeloest": bool(coords), "ort": ort}


def _zu_tun_nach_profil(db) -> bool:
    b = befund(db)
    if b["quelle"] == EIGENE or not b["profil_wohnort"]:
        return False
    k = db.get_search_criteria() or {}
    return not (k.get("standort_ort") == b["profil_wohnort"] and b["aufgeloest"])


def nach_profil_speichern(db):
    """Aus `Database.save_profile`: den Wohnort als Standort nehmen, wenn
    sich etwas geaendert hat. Ins Netz geht das nur im Hintergrund, damit
    Speichern nicht auf einen fremden Dienst wartet. Ohne Netz (Test-Suite)
    laeuft es sofort und gibt das Ergebnis zurueck."""
    from .geocoding_service import geocoding_aktiv
    if not _zu_tun_nach_profil(db):
        return None
    if not geocoding_aktiv():
        return aus_profil_uebernehmen(db)

    def _lauf():
        try:
            aus_profil_uebernehmen(db)
        except Exception as exc:
            logger.warning("Wohnort nicht als Standort uebernommen: %s", exc)

    threading.Thread(target=_lauf, daemon=True, name="pbp-standort").start()
    return {"gestartet": True}


def eigenen_setzen(db, ort: str, neu_rechnen: bool = True) -> dict:
    """Einen Standort ausdruecklich setzen. Leer heisst: zurueck zum
    Wohnort aus dem Profil. Ein Ort, den der Dienst nicht aufloest, wird
    NICHT gespeichert — sonst stuende ein Standort da, der nichts rechnet."""
    from .geocoding_service import geocode_location
    ort = (ort or "").strip()
    if not ort:
        db.set_search_criteria("standort_quelle", PROFIL)
        db.set_search_criteria("standort_ort", "")
        return {"status": "profil", **aus_profil_uebernehmen(db, neu_rechnen)}
    vorher = _koordinaten(db)
    coords = geocode_location(ort)
    if not coords:
        return {"status": "nicht_aufgeloest", "ort": ort,
                "hinweis": f"„{ort}“ ließ sich nicht auflösen. Versuche PLZ und Ort."}
    _setzen(db, ort, EIGENE, coords)
    if coords != vorher and neu_rechnen:
        neu_rechnen_starten(db, alle=True)
    return {"status": "gesetzt", "ort": ort, "koordinaten": list(coords)}


# -- Entfernungen des Bestands ----------------------------------------

def entfernungen_nachziehen(db, alle: bool = False,
                            max_orte: int | None = NACHHOLEN_JE_LAUF,
                            fortschritt=None) -> dict:
    """Rechnet Entfernungen des Bestands.

    `alle=True`: jede Stelle mit Ort neu (nach einem neuen Standort);
    `alle=False`: nur Stellen mit Ort und ohne Entfernung (Nachholen).
    Von Hand gesetzte Entfernungen bleiben. Je VERSCHIEDENEM Ort eine
    Anfrage; `max_orte` begrenzt einen Lauf."""
    from .geocoding_service import calculate_distance_km, geocode_location
    start = _koordinaten(db)
    if not start:
        return {"status": "kein_standort", "stellen": 0, "orte": 0}
    pid = db.get_active_profile_id()
    con = db.connect()
    sql = ("SELECT hash, location FROM jobs WHERE (profile_id=? OR profile_id IS NULL) "
           "AND location IS NOT NULL AND TRIM(location) != '' "
           "AND COALESCE(entfernung_quelle, '') != 'mensch'")
    if not alle:
        sql += " AND distance_km IS NULL"
    nach_ort: dict = {}
    for r in con.execute(sql, (pid,)).fetchall():
        nach_ort.setdefault(r[1].strip(), []).append(r[0])
    orte = list(nach_ort)
    if max_orte:
        orte = orte[:max_orte]
    gerechnet, unaufloesbar = 0, 0
    for i, ort in enumerate(orte):
        ziel = geocode_location(ort)
        hashes = nach_ort[ort]
        platz = ",".join("?" * len(hashes))
        if ziel:
            km = calculate_distance_km(start, ziel)
            con.execute(
                f"UPDATE jobs SET distance_km=?, lat=?, lon=?, "
                f"fahrstrecke_km=NULL, fahrzeit_min=NULL, route_quelle=NULL "
                f"WHERE hash IN ({platz})",
                (km, ziel[0], ziel[1], *hashes))
            gerechnet += len(hashes)
        else:
            unaufloesbar += len(hashes)
        if fortschritt and i % 10 == 0:
            fortschritt(i, len(orte))
    con.commit()
    offen = len(nach_ort) - len(orte)
    return {"status": "fertig", "stellen": gerechnet, "orte": len(orte),
            "unaufloesbar": unaufloesbar, "orte_offen": offen}


def _punkte_neu(db) -> dict:
    from . import scoring_kriterien
    from .neu_bewerten import neu_bewerten
    return neu_bewerten(db, db.get_active_jobs(), scoring_kriterien.fuer_scoring(db))


def neu_rechnen_starten(db, alle: bool = True) -> str | None:
    """Im Hintergrund: Entfernungen und danach die Punkte neu (AK 4, 8).
    Rueckgabe: die Kennung des Hintergrund-Jobs."""
    job_id = db.create_background_job("entfernungen", {"alle": alle})

    def _lauf():
        try:
            db.update_background_job(job_id, "running", progress=5,
                                     message="Entfernungen werden neu gerechnet …")
            erg = entfernungen_nachziehen(db, alle=alle, max_orte=None if alle else NACHHOLEN_JE_LAUF)
            punkte = _punkte_neu(db)
            db.update_background_job(
                job_id, "fertig", progress=100,
                message=(f"{erg.get('stellen', 0)} Entfernungen neu gerechnet. "
                         f"Die Nähe-Punkte haben sich geändert: "
                         f"{punkte.get('geaendert', 0)} Stellen mit neuen Punkten."),
                result={"entfernungen": erg, "punkte": punkte})
        except Exception as exc:
            logger.warning("Entfernungen neu rechnen fehlgeschlagen: %s", exc)
            db.update_background_job(job_id, "fehler", message=str(exc))

    # "pbp-" im Namen: die Test-Suite joint diese Threads vor dem
    # Schliessen der Datenbank (A22/#759), und die DSGVO-Loeschung wartet
    # auf sie (#1097).
    threading.Thread(target=_lauf, daemon=True, name=f"pbp-entfernungen-{job_id[:8]}").start()
    return job_id


def nachholen(db) -> dict:
    """Nach einem Suchlauf: fehlende Entfernungen nachholen (AK 5),
    begrenzt je Lauf, danach die Punkte der betroffenen Stellen neu."""
    erg = entfernungen_nachziehen(db, alle=False)
    if erg.get("stellen"):
        _punkte_neu(db)
    return erg
