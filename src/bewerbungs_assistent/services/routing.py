"""Echte Fahrstrecke und Fahrzeit (#950, AK 3 bis 6).

## Warum es das gibt

Bis hierher rechnete PBP mit der Luftlinie. Seit v1.7.50 steht sie als
solche beschriftet da, dazu eine geschaetzte Fahrstrecke (Faktor 1,4).
Der Melder hat den Kern benannt: **fuer die Frage, ob eine Stelle
pendelbar ist, sagt "vier Stunden je Richtung" mehr als jede
Kilometerzahl** — und seit #910 wird die Entfernung gegen das Gehalt
verrechnet, also ist sie keine Anzeige, sondern eine Rechengroesse.

## Anbieter

OpenRouteService (Heidelberg), Matrix-Schnittstelle: eine Anfrage fuer
viele Ziele. Der kostenlose Zugang braucht einen eigenen Schluessel, den
der Mensch selbst anlegt — PBP legt kein Konto an und traegt keinen
Schluessel ein, den es nicht bekommen hat.

## Was bewusst so ist

- **Ohne Schluessel aendert sich nichts.** Die Luftlinie bleibt, wie sie
  war, beschriftet als solche (AK 5).
- **Fehlschlaege werden benannt, nicht geraten.** Ein abgelehnter
  Schluessel, ein erschoepftes Kontingent und ein nicht erreichbarer
  Dienst sind drei verschiedene Befunde (#1014: aus 410 Gone wurde
  einmal "vermutlich Bot-Block").
- **Zwischengespeichert je Ortspaar** (AK 4). Die Stellenorte wiederholen
  sich stark; die meisten Suchlaeufe brauchen keine einzige Anfrage.
- **Ein Tageszaehler haelt das Kontingent ein.** Das Freikontingent der
  Matrix-Schnittstelle liegt bei 500 Anfragen am Tag; PBP hoert vorher
  auf, statt einen Tag lang Fehlermeldungen zu sammeln.
- **Der Schluessel verlaesst dieses Modul nie.** Kein Status, kein Log,
  keine Antwort nennt ihn — `status()` sagt nur, ob einer gesetzt ist.
- **Datenweitergabe:** an den Dienst gehen Koordinaten, keine Namen —
  der eigene Standort und die Orte der Stellen. Das steht in der
  Oberflaeche, bevor der Schluessel gespeichert wird.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Iterable, Optional

logger = logging.getLogger("bewerbungs_assistent.routing")

ANBIETER = "openrouteservice"
MATRIX_URL = "https://api.openrouteservice.org/v2/matrix/driving-car"
REGISTRIERUNG_URL = "https://openrouteservice.org/dev/#/signup"

EINSTELLUNG_SCHLUESSEL = "ors_api_key"
EINSTELLUNG_ZAEHLER = "ors_anfragen"

#: Freikontingent der Matrix-Schnittstelle: 500 Anfragen am Tag. PBP hoert
#: mit Puffer vorher auf — andere Werkzeuge desselben Schluessels zaehlen
#: beim Anbieter mit.
TAGESGRENZE = 450
#: Ziele je Anfrage. Die Schnittstelle erlaubt deutlich mehr; kleinere
#: Pakete halten eine einzelne Fehlantwort billig.
ZIELE_JE_ANFRAGE = 50
#: Nachkommastellen der Koordinaten im Zwischenspeicher (~11 m). Zwei
#: Stellen im selben Gewerbegebiet teilen sich damit eine Route.
RUNDUNG = 4
TIMEOUT_S = 20

OK = "ok"
KEIN_SCHLUESSEL = "kein_schluessel"
SCHLUESSEL_ABGELEHNT = "schluessel_abgelehnt"
KONTINGENT = "kontingent_erschoepft"
NICHT_ERREICHBAR = "nicht_erreichbar"
KEIN_STANDORT = "kein_standort"

BEFUND_TEXT = {
    OK: "Fahrstrecke und Fahrzeit berechnet.",
    KEIN_SCHLUESSEL: ("Kein Routing-Schluessel eingerichtet — PBP rechnet "
                      "mit der Luftlinie."),
    SCHLUESSEL_ABGELEHNT: ("Der Routing-Dienst lehnt den Schluessel ab. "
                           "Bitte in den Einstellungen prüfen."),
    KONTINGENT: ("Das Tageskontingent des Routing-Dienstes ist erreicht. "
                 "Die übrigen Stellen behalten die Luftlinie und werden "
                 "beim nächsten Lauf nachgezogen."),
    NICHT_ERREICHBAR: ("Der Routing-Dienst war nicht erreichbar — die "
                       "Stellen behalten die Luftlinie."),
    KEIN_STANDORT: ("Kein Wohnort hinterlegt — ohne Startpunkt gibt es "
                    "keine Route."),
}


# ------------------------------------------------------------ Schluessel


def schluessel(db) -> str:
    try:
        return str(db.get_setting(EINSTELLUNG_SCHLUESSEL, "") or "").strip()
    except Exception:  # pragma: no cover — nie eine Liste stoppen
        return ""


def konfiguriert(db) -> bool:
    return bool(schluessel(db))


def _heute() -> str:
    return date.today().isoformat()


def anfragen_heute(db) -> int:
    try:
        stand = db.get_setting(EINSTELLUNG_ZAEHLER, {}) or {}
    except Exception:  # pragma: no cover
        return 0
    if not isinstance(stand, dict) or stand.get("datum") != _heute():
        return 0
    try:
        return int(stand.get("anzahl") or 0)
    except (TypeError, ValueError):
        return 0


def _zaehlen(db) -> None:
    db.set_setting(EINSTELLUNG_ZAEHLER,
                   {"datum": _heute(), "anzahl": anfragen_heute(db) + 1})


# ---------------------------------------------------- Zwischenspeicher


def tabelle_anlegen(db) -> None:
    """Defensiv — `Database.initialize` legt die Tabelle ebenfalls an."""
    db.connect().execute("""
        CREATE TABLE IF NOT EXISTS routen_cache (
            start_lat REAL NOT NULL,
            start_lon REAL NOT NULL,
            ziel_lat REAL NOT NULL,
            ziel_lon REAL NOT NULL,
            km REAL,
            minuten REAL,
            anbieter TEXT,
            abgerufen_am TEXT,
            PRIMARY KEY (start_lat, start_lon, ziel_lat, ziel_lon)
        )
    """)


def _punkt(lat, lon) -> Optional[tuple]:
    try:
        return (round(float(lat), RUNDUNG), round(float(lon), RUNDUNG))
    except (TypeError, ValueError):
        return None


def _aus_cache(db, start: tuple, ziel: tuple) -> Optional[dict]:
    zeile = db.connect().execute(
        "SELECT km, minuten FROM routen_cache WHERE start_lat=? AND "
        "start_lon=? AND ziel_lat=? AND ziel_lon=?",
        (start[0], start[1], ziel[0], ziel[1])).fetchone()
    if zeile is None:
        return None
    return {"km": zeile[0], "minuten": zeile[1]}


def _in_cache(db, start: tuple, ziel: tuple, km, minuten) -> None:
    db.connect().execute(
        "INSERT OR REPLACE INTO routen_cache (start_lat, start_lon, "
        "ziel_lat, ziel_lon, km, minuten, anbieter, abgerufen_am) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (start[0], start[1], ziel[0], ziel[1], km, minuten, ANBIETER,
         datetime.now(timezone.utc).isoformat(timespec="seconds")))


def zwischengespeichert(db) -> int:
    try:
        tabelle_anlegen(db)
        return int(db.connect().execute(
            "SELECT COUNT(*) FROM routen_cache").fetchone()[0])
    except Exception:  # pragma: no cover
        return 0


# ------------------------------------------------------------- Abruf


def _abrufen(key: str, start: tuple, ziele: list, client=None) -> tuple:
    """Eine Matrix-Anfrage. Liefert (ergebnisse, befund).

    `ergebnisse` ist je Ziel ein dict mit km/minuten — oder None, wenn
    der Dienst fuer dieses Ziel keine Route kennt.
    """
    koordinaten = [[start[1], start[0]]] + [[z[1], z[0]] for z in ziele]
    koerper = {
        "locations": koordinaten,
        "sources": [0],
        "destinations": list(range(1, len(koordinaten))),
        "metrics": ["distance", "duration"],
        "units": "km",
    }
    kopf = {"Authorization": key, "Content-Type": "application/json",
            "Accept": "application/json"}
    try:
        if client is None:
            import httpx
            with httpx.Client(timeout=TIMEOUT_S) as eigen:
                antwort = eigen.post(MATRIX_URL, json=koerper, headers=kopf)
        else:
            antwort = client.post(MATRIX_URL, json=koerper, headers=kopf)
    except Exception as exc:
        # Bewusst ohne den Schluessel im Log — `exc` enthaelt ihn nicht,
        # die Anfrage-Kopfzeilen werden nicht ausgegeben.
        logger.info("Routing nicht erreichbar: %s", type(exc).__name__)
        return [], NICHT_ERREICHBAR
    status = getattr(antwort, "status_code", 0)
    if status in (401, 403):
        return [], SCHLUESSEL_ABGELEHNT
    if status == 429:
        return [], KONTINGENT
    if status != 200:
        logger.info("Routing antwortet mit HTTP %s", status)
        return [], NICHT_ERREICHBAR
    try:
        daten = antwort.json() or {}
        strecken = (daten.get("distances") or [[]])[0]
        zeiten = (daten.get("durations") or [[]])[0]
    except Exception:
        return [], NICHT_ERREICHBAR
    ergebnisse = []
    for i in range(len(ziele)):
        km = strecken[i] if i < len(strecken) else None
        sek = zeiten[i] if i < len(zeiten) else None
        if km is None or sek is None:
            ergebnisse.append(None)
        else:
            ergebnisse.append({"km": round(float(km), 1),
                               "minuten": round(float(sek) / 60)})
    return ergebnisse, OK


def routen(db, start, ziele: Iterable, *, client=None) -> tuple:
    """Fahrstrecken von `start` zu allen `ziele` — Zwischenspeicher zuerst.

    Returns:
        `(ergebnis, befund)`. `ergebnis` bildet jeden gerundeten Zielpunkt
        auf `{"km", "minuten"}` oder `None` (keine Route) ab; Ziele, die
        nicht abgefragt werden konnten, fehlen darin. Der Befund nennt,
        warum etwas fehlt.
    """
    key = schluessel(db)
    if not key:
        return {}, KEIN_SCHLUESSEL
    s = _punkt(*start) if start else None
    if s is None:
        return {}, KEIN_STANDORT
    tabelle_anlegen(db)

    ergebnis: dict = {}
    offen: list = []
    for ziel in ziele:
        z = _punkt(*ziel) if ziel else None
        if z is None or z in ergebnis or z in offen:
            continue
        treffer = _aus_cache(db, s, z)
        if treffer is not None:
            ergebnis[z] = treffer if treffer.get("km") is not None else None
        else:
            offen.append(z)

    befund = OK
    for i in range(0, len(offen), ZIELE_JE_ANFRAGE):
        if anfragen_heute(db) >= TAGESGRENZE:
            befund = KONTINGENT
            break
        paket = offen[i:i + ZIELE_JE_ANFRAGE]
        antworten, befund = _abrufen(key, s, paket, client=client)
        _zaehlen(db)
        if befund != OK:
            break
        for z, wert in zip(paket, antworten):
            ergebnis[z] = wert
            _in_cache(db, s, z, (wert or {}).get("km"),
                      (wert or {}).get("minuten"))
        db.connect().commit()
    return ergebnis, befund


def fuer_stellen(db, jobs: list, start, *, client=None) -> dict:
    """Setzt `fahrstrecke_km`, `fahrzeit_min` und `route_quelle` an Stellen.

    Beruehrt nur Stellen mit Koordinaten; alle anderen behalten, was sie
    haben. Schreibt nichts in die Datenbank ausser dem Zwischenspeicher —
    das Speichern der Stelle macht der Aufrufer.
    """
    mit_ort = [j for j in (jobs or [])
               if _punkt(j.get("lat"), j.get("lon")) is not None]
    if not mit_ort:
        return {"berechnet": 0, "ohne_route": 0,
                "befund": OK if konfiguriert(db) else KEIN_SCHLUESSEL}
    ergebnis, befund = routen(
        db, start, [(j.get("lat"), j.get("lon")) for j in mit_ort],
        client=client)
    berechnet = ohne_route = 0
    for job in mit_ort:
        z = _punkt(job.get("lat"), job.get("lon"))
        if z not in ergebnis:
            continue
        wert = ergebnis[z]
        if wert is None:
            ohne_route += 1
            continue
        job["fahrstrecke_km"] = wert["km"]
        job["fahrzeit_min"] = wert["minuten"]
        job["route_quelle"] = ANBIETER
        berechnet += 1
    return {"berechnet": berechnet, "ohne_route": ohne_route,
            "befund": befund}


# ------------------------------------------------------- Verwaltung


def schluessel_pruefen(key: str, *, client=None) -> str:
    """Eine Probeanfrage mit zwei nahen Punkten — nichts wird gespeichert."""
    _, befund = _abrufen(key, (53.5511, 9.9937), [(53.5530, 9.9920)],
                         client=client)
    return befund


def schluessel_setzen(db, key: str, *, client=None) -> dict:
    """Erst pruefen, dann speichern — ein kaputter Schluessel soll nicht als
    eingerichtet gelten (dasselbe Vorgehen wie bei Adzuna, #809)."""
    key = (key or "").strip()
    if not key:
        return {"fehler": "Kein Schluessel übergeben."}
    if any(c.isspace() for c in key) or len(key) < 20:
        return {"fehler": ("Das sieht nicht nach einem Schluessel von "
                           "OpenRouteService aus — bitte vollständig "
                           "kopieren.")}
    befund = schluessel_pruefen(key, client=client)
    if befund != OK:
        return {"fehler": BEFUND_TEXT.get(befund, befund), "befund": befund}
    db.set_setting(EINSTELLUNG_SCHLUESSEL, key)
    return {"status": "eingerichtet", "befund": OK}


def schluessel_entfernen(db) -> dict:
    db.set_setting(EINSTELLUNG_SCHLUESSEL, "")
    return {"status": "entfernt",
            "hinweis": ("Ohne Schluessel rechnet PBP wieder mit der "
                        "Luftlinie — auch für Stellen, an denen schon eine "
                        "Fahrstrecke steht. Die gespeicherten Scores zieht "
                        "scores_neu_berechnen() nach.")}


def status(db) -> dict:
    """Was die Oberflaeche zeigt — nie den Schluessel selbst."""
    return {
        "konfiguriert": konfiguriert(db),
        "anbieter": ANBIETER,
        "anfragen_heute": anfragen_heute(db),
        "tagesgrenze": TAGESGRENZE,
        "zwischengespeichert": zwischengespeichert(db),
        "registrierungs_url": REGISTRIERUNG_URL,
        "datenweitergabe": ("An OpenRouteService gehen Koordinaten: dein "
                            "Wohnort und die Orte der Stellen. Keine "
                            "Namen, keine Firmen, keine Stellentexte."),
    }
