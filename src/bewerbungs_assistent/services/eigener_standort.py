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
* **Entfernungen, die mit einem Zusatz im Ortstext gerechnet wurden,
  werden geheilt** (#1158): "Hamburg (hybrid), remote moeglich" lag bis
  v1.7.149 bei Mainz (410 statt 20 km) und blieb so gespeichert.
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger("bewerbungs_assistent.eigener_standort")

EIGENE = "eigene"
PROFIL = "profil"
NACHHOLEN_JE_LAUF = 40   # verschiedene Orte je Nachhol-Lauf
#: Ab dieser Abweichung (km) ersetzt eine neu gerechnete Entfernung die gespeicherte. Darunter ist es dieselbe
#: Zahl in anderer Rundung - so laeuft die Heilung nie ein zweites Mal ueber dieselbe Stelle.
BEREINIGEN_AB_KM = 1.0
#: Orte, die in DIESEM Prozess schon einmal zur Heilung gefragt wurden. Findet der Dienst einen Ort nicht oder
#: ist er nicht erreichbar, kommt `None` zurueck; ohne diese Merkliste wuerde jeder Suchlauf dieselben Orte
#: erneut anfragen (mit Zeitgrenze je Anfrage), solange das Netz fehlt.
_BEREINIGT_VERSUCHT: set = set()


def _jetzt() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


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
    erg = {
        "ort": k.get("standort_ort") or (profil_ort if quelle == PROFIL else ""),
        "quelle": quelle,
        "aufgeloest": bool(lat and lon),
        "profil_wohnort": profil_ort,
    }
    if not erg["aufgeloest"]:
        # #1235: kennt der Ortsdienst mehrere Orte dieses Namens, ist das der Grund - und der Mensch kann etwas tun
        # (PLZ ergaenzen). Aus dem Gedaechtnis des Dienstes, ohne Netz.
        try:
            from .geocoding_service import mehrdeutigkeit
            kandidaten = mehrdeutigkeit(erg["ort"] or profil_ort)
        except Exception:  # noqa: BLE001 - eine Auskunft darf den Befund nie kippen
            kandidaten = None
        if kandidaten:
            erg["mehrdeutig"] = [k_["name"] for k_ in kandidaten]
    return erg


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
        # #1235: gibt es den Ort mehrfach, sagt der Hinweis das und nennt die Kandidaten.
        from .geocoding_service import mehrdeutigkeit
        kandidaten = mehrdeutigkeit(ort)
        if kandidaten:
            namen = [k_["name"] for k_ in kandidaten]
            return {"status": "nicht_aufgeloest", "ort": ort, "mehrdeutig": namen,
                    "hinweis": (f"„{ort}“ gibt es mehrfach in Deutschland ({'; '.join(namen)}). "
                                f"Nenne die PLZ dazu, etwa „12345 {ort}“.")}
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
    from .geocoding_service import calculate_distance_km, geocode_location, mehrdeutigkeit
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
    # #1118: erst alle Orte aufloesen (eine Netzabfrage je Ort und Sekunde),
    # DANACH in einem kurzen Schreibvorgang speichern. Vorher lief jedes
    # UPDATE in derselben offenen Transaktion wie die Abfragen — bei 753
    # Orten hielt das die Schreibsperre 25 Minuten, und der gleichzeitige
    # Suchlauf starb an "database is locked".
    ziele: dict = {}
    for i, ort in enumerate(orte):
        ziele[ort] = geocode_location(ort)
        if fortschritt and i % 10 == 0:
            try:
                fortschritt(i, len(orte))
            except Exception as exc:  # noqa: BLE001 — Anzeige, nicht der Zweck
                logger.warning("Fortschritt der Entfernungen nicht gespeichert: %s", exc)
    # #1235: ein Ort, den der Dienst mehrfach kennt, hat keine Koordinaten - die Anzeigen seiner Stellen duerfen ihn
    # aber klaeren (PLZ oder Bundesland hinter dem Namen). Auch das ist Netz und kommt VOR dem Schreiben.
    klaerung: dict = {}
    for ort in orte:
        if not ziele[ort] and mehrdeutigkeit(ort):
            klaerung[ort] = _mehrdeutigen_ort_klaeren(con, start, ort, nach_ort[ort])
    gerechnet, unaufloesbar, mehrdeutig = 0, 0, 0
    am = _jetzt()
    for ort in orte:
        ziel = ziele[ort]
        hashes = nach_ort[ort]
        platz = ",".join("?" * len(hashes))
        if not ziel and ort in klaerung:
            geklaert, offen_ = _klaerung_schreiben(con, klaerung[ort], am)
            gerechnet += geklaert
            mehrdeutig += offen_
            continue
        if ziel:
            km = calculate_distance_km(start, ziel)
            con.execute(
                f"UPDATE jobs SET distance_km=?, lat=?, lon=?, entfernung_am=?, "
                f"fahrstrecke_km=NULL, fahrzeit_min=NULL, route_quelle=NULL "
                f"WHERE hash IN ({platz})",
                (km, ziel[0], ziel[1], am, *hashes))
            gerechnet += len(hashes)
        else:
            unaufloesbar += len(hashes)
    con.commit()
    offen = len(nach_ort) - len(orte)
    return {"status": "fertig", "stellen": gerechnet, "orte": len(orte),
            "unaufloesbar": unaufloesbar, "mehrdeutig": mehrdeutig, "orte_offen": offen}


def _mehrdeutigen_ort_klaeren(con, start, ort: str, kennungen: list) -> list:
    """Die Stellen EINES mehrdeutigen Ortes (#1235): was die Anzeige klaert, bekommt eine Entfernung.

    Rueckgabe: [(kennung, genau | None)] - `genau` ist {"km", "koordinaten", "aufgeloest_durch"}, wenn die Anzeige
    PLZ oder Bundesland hinter dem Namen nennt und der Dienst damit EINEN Ort findet. Das ist Netz; geschrieben
    wird erst danach (#1118).
    """
    from .geocoding_service import entfernung_aus_anzeige
    plan = []
    for kennung in kennungen:
        reihe = con.execute("SELECT description FROM jobs WHERE hash=?", (kennung,)).fetchone()
        plan.append((kennung, entfernung_aus_anzeige(ort, start[0], start[1], (reihe[0] if reihe else "") or "")))
    return plan


def _klaerung_schreiben(con, plan: list, am: str) -> tuple:
    """Schreibt, was `_mehrdeutigen_ort_klaeren` vorbereitet hat. (geklaert, auf unbekannt gestellt)

    Eine Stelle, die die Anzeige nicht klaert, verliert ihre Entfernung: eine Zahl, die auf einem Raten beruht,
    ist schlechter als keine (#989) - sie stuende sonst als "nah" in der Liste.
    """
    geklaert = unbekannt = 0
    for kennung, genau in plan:
        if genau:
            con.execute(
                "UPDATE jobs SET distance_km=?, lat=?, lon=?, entfernung_am=?, "
                "fahrstrecke_km=NULL, fahrzeit_min=NULL, route_quelle=NULL WHERE hash=?",
                (genau["km"], genau["koordinaten"][0], genau["koordinaten"][1], am, kennung))
            geklaert += 1
        else:
            cur = con.execute(
                "UPDATE jobs SET distance_km=NULL, lat=NULL, lon=NULL, entfernung_am=?, "
                "fahrstrecke_km=NULL, fahrzeit_min=NULL, route_quelle=NULL "
                "WHERE hash=? AND distance_km IS NOT NULL", (am, kennung))
            unbekannt += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    return geklaert, unbekannt


#: #1235: Orte, die in DIESEM Prozess schon auf Mehrdeutigkeit gefragt wurden (wie `_BEREINIGT_VERSUCHT`): ein
#: ausgefallener Dienst soll nicht in jedem Suchlauf dieselben Orte erneut anfragen.
_MEHRDEUTIG_VERSUCHT: set = set()


def entfernungen_mehrdeutige_pruefen(db, max_orte: int | None = NACHHOLEN_JE_LAUF) -> dict:
    """Heilt gespeicherte Entfernungen zu Orten, die der Dienst mehrfach kennt (#1235).

    Bis v1.7.158 nahm PBP bei einem Namen wie "Rosengarten" den ersten Treffer; die Stellen im Bestand tragen die
    Zahl. Jeder verschiedene Ort ohne Postleitzahl, der nicht zu den grossen Staedten gehoert, wird einmal neu
    gefragt (`max_orte` je Lauf; der Ortsspeicher merkt sich, was geprueft ist). Ist er mehrdeutig, entscheidet die
    Anzeige der Stelle (PLZ oder Bundesland hinter dem Namen), sonst steht die Entfernung auf unbekannt. Findet der
    Dienst nichts oder ist er nicht erreichbar, bleibt die gespeicherte Zahl: das waere ein Urteil, das der Dienst
    nicht gefaellt hat (#950). Von Hand gesetzte Entfernungen bleiben (#1077).
    """
    from .geocoding_service import geocode_ort, mehrdeutigkeit, mehrdeutigkeit_offen, ort_schluessel
    start = _koordinaten(db)
    if not start:
        return {"status": "kein_standort", "geklaert": 0, "unbekannt": 0, "orte": 0}
    pid = db.get_active_profile_id()
    con = db.connect()
    sql = ("SELECT hash, location FROM jobs WHERE (profile_id=? OR profile_id IS NULL) "
           "AND location IS NOT NULL AND TRIM(location) != '' AND distance_km IS NOT NULL "
           "AND COALESCE(entfernung_quelle, '') != 'mensch'")
    nach_ort: dict = {}
    for kennung, ort in con.execute(sql, (pid,)).fetchall():
        if ort_schluessel(ort):
            nach_ort.setdefault(ort.strip(), []).append(kennung)
    offen = [o for o in nach_ort if o not in _MEHRDEUTIG_VERSUCHT and mehrdeutigkeit_offen(o)]
    if max_orte:
        offen = offen[:max_orte]
    for ort in offen:                       # Netz: ein Ort je Sekunde, ausserhalb jeder Schreibsperre
        _MEHRDEUTIG_VERSUCHT.add(ort)
        geocode_ort(ort)
    klaerung = {o: _mehrdeutigen_ort_klaeren(con, start, o, k) for o, k in nach_ort.items() if mehrdeutigkeit(o)}
    geklaert = unbekannt = 0
    am = _jetzt()
    for plan in klaerung.values():
        g, u = _klaerung_schreiben(con, plan, am)
        geklaert += g
        unbekannt += u
    con.commit()
    if geklaert or unbekannt:
        logger.info("Mehrdeutige Orte geprueft (#1235): %d Stellen per Anzeige geklaert, %d auf unbekannt gestellt, "
                    "%d Orte gefragt", geklaert, unbekannt, len(offen))
    return {"status": "fertig", "geklaert": geklaert, "unbekannt": unbekannt, "orte": len(offen)}


def entfernungen_bereinigen(db, max_orte: int | None = NACHHOLEN_JE_LAUF) -> dict:
    """Heilt gespeicherte Entfernungen, die mit einem Zusatz im Ortstext gerechnet wurden (#1158 Punkt 8).

    Bis v1.7.149 ging der Rohtext an den Ortsdienst: "Hamburg (hybrid), remote moeglich" kam mit einem Treffer
    bei Mainz zurueck (410 statt 20 km) und blieb so gespeichert. Den Dienst zu korrigieren heilt nur NEUE
    Rechnungen; die Stellen im Bestand haetten die falsche Zahl behalten, bis jemand den Ort von Hand aendert.

    Angefasst werden nur Stellen, deren Ortstext sich beim Bereinigen aendert, die eine Entfernung tragen und
    deren Entfernung nicht von Hand gesetzt ist (#1077). Ersetzt wird erst ab BEREINIGEN_AB_KM Abweichung.
    Ein Text ohne Ort ("Remote moeglich") hat keine Entfernung: sie wird geleert, das ist eine Feststellung
    ohne Netz. Findet der Dienst den bereinigten Ort NICHT (oder ist er nicht erreichbar), bleibt die
    gespeicherte Zahl stehen - sie zu loeschen waere ein Urteil, das der Dienst nicht gefaellt hat (#950)."""
    from .geocoding_service import (
        calculate_distance_km, geocode_location, nur_land_entfernt, ort_fuer_abfrage, ort_schluessel)
    start = _koordinaten(db)
    if not start:
        return {"status": "kein_standort", "stellen": 0, "geleert": 0, "orte": 0}
    pid = db.get_active_profile_id()
    con = db.connect()
    sql = ("SELECT hash, location, distance_km FROM jobs WHERE (profile_id=? OR profile_id IS NULL) "
           "AND location IS NOT NULL AND TRIM(location) != '' AND distance_km IS NOT NULL "
           "AND COALESCE(entfernung_quelle, '') != 'mensch'")
    nach_ort: dict = {}
    leeren: list = []
    for kennung, ort, km in con.execute(sql, (pid,)).fetchall():
        roh = ort.strip()
        schluessel = ort_schluessel(roh)
        if not schluessel:
            leeren.append(kennung)         # kein Ort gemeint: keine Entfernung
        elif schluessel == roh.lower() or nur_land_entfernt(roh, ort_fuer_abfrage(roh)):
            continue                       # sauber, oder nur ein Land am Ende: die alte Rechnung stimmt
        else:
            nach_ort.setdefault(roh, []).append((kennung, float(km)))
    orte = [o for o in nach_ort if o not in _BEREINIGT_VERSUCHT]
    if max_orte:
        orte = orte[:max_orte]
    # Erst alle Orte aufloesen (eine Netzabfrage je Ort), DANACH kurz schreiben - wie in `entfernungen_nachziehen`
    # (#1118): sonst haelt die Schreibsperre so lange, wie das Netz braucht.
    ziele: dict = {}
    for ort in orte:
        _BEREINIGT_VERSUCHT.add(ort)
        ziele[ort] = geocode_location(ort)
    korrigiert = 0
    am = _jetzt()
    for ort, ziel in ziele.items():
        if not ziel:
            continue
        neu = calculate_distance_km(start, ziel)
        for kennung, alt in nach_ort[ort]:
            if abs(neu - alt) <= BEREINIGEN_AB_KM:
                continue
            con.execute(
                "UPDATE jobs SET distance_km=?, lat=?, lon=?, entfernung_am=?, "
                "fahrstrecke_km=NULL, fahrzeit_min=NULL, route_quelle=NULL WHERE hash=?",
                (neu, ziel[0], ziel[1], am, kennung))
            korrigiert += 1
    for i in range(0, len(leeren), 500):
        teil = leeren[i:i + 500]
        con.execute(
            f"UPDATE jobs SET distance_km=NULL, lat=NULL, lon=NULL, entfernung_am=?, "
            f"fahrstrecke_km=NULL, fahrzeit_min=NULL, route_quelle=NULL "
            f"WHERE hash IN ({','.join('?' * len(teil))})", (am, *teil))
    con.commit()
    if korrigiert or leeren:
        logger.info("Entfernungen bereinigt (#1158): %d korrigiert, %d ohne Ort geleert, %d Orte gefragt",
                    korrigiert, len(leeren), len(orte))
    return {"status": "fertig", "stellen": korrigiert, "geleert": len(leeren), "orte": len(orte)}


def _punkte_neu(db) -> dict:
    from . import scoring_kriterien
    from .neu_bewerten import neu_bewerten
    return neu_bewerten(db, db.get_active_jobs(), scoring_kriterien.fuer_scoring(db))


#: #1118: wie oft die Nachrechnung nachsieht, ob die Jobsuche fertig ist,
#: und wie lange sie hoechstens wartet.
WARTEN_TAKT_SEK = 10
WARTEN_HOECHSTENS_SEK = 45 * 60


def _warten_auf_suche(db, job_id) -> None:
    """Nachrechnung und Suchlauf nicht gleichzeitig (#1118): beim ersten
    Start nach einem Update trafen sie sich zwangsläufig — die Automatik
    war fällig, und die Übernahme des Wohnorts stieß die Nachrechnung an.
    Ein toter Suchlauf hält nicht auf."""
    import time
    from .hintergrund_alter import veraltet
    ende = time.monotonic() + WARTEN_HOECHSTENS_SEK
    while time.monotonic() < ende:
        suche = db.get_running_background_job("jobsuche")
        if not suche or veraltet(suche):
            return
        db.update_background_job(job_id, "pending", progress=0,
                                 message="Wartet, bis die Jobsuche fertig ist …")
        time.sleep(WARTEN_TAKT_SEK)


def neu_rechnen_starten(db, alle: bool = True) -> str | None:
    """Im Hintergrund: Entfernungen und danach die Punkte neu (AK 4, 8).
    Rueckgabe: die Kennung des Hintergrund-Jobs."""
    job_id = db.create_background_job("entfernungen", {"alle": alle})

    def _fortschritt(i, n):
        db.update_background_job(job_id, "running", progress=5 + int(i / max(n, 1) * 80),
                                 message=f"Entfernungen: {i} von {n} Orten aufgelöst …")

    def _lauf():
        try:
            _warten_auf_suche(db, job_id)
            db.update_background_job(job_id, "running", progress=5,
                                     message="Entfernungen werden neu gerechnet …")
            erg = entfernungen_nachziehen(db, alle=alle,
                                          max_orte=None if alle else NACHHOLEN_JE_LAUF,
                                          fortschritt=_fortschritt)
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
    # #1158: Altbestand mit Ortszusatz - eine Heilung darf das Nachholen nie stoppen.
    try:
        heilung = entfernungen_bereinigen(db)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Entfernungen nicht bereinigt: %s", exc)
        heilung = {}
    # #1235: Entfernungen zu Orten, die der Dienst mehrfach kennt - nachrechnen, klaeren oder auf unbekannt stellen.
    try:
        mehrdeutig = entfernungen_mehrdeutige_pruefen(db)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Mehrdeutige Orte nicht geprueft: %s", exc)
        mehrdeutig = {}
    if (erg.get("stellen") or heilung.get("stellen") or heilung.get("geleert")
            or mehrdeutig.get("geklaert") or mehrdeutig.get("unbekannt")):
        _punkte_neu(db)
    erg["bereinigt"] = (heilung.get("stellen", 0) + heilung.get("geleert", 0)
                        + mehrdeutig.get("geklaert", 0) + mehrdeutig.get("unbekannt", 0))
    return erg
