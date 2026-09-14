"""Bestand heilen nach dem Kommentar-Fehler im Kartenleser (#1041, B54).

Von v1.7.104 bis v1.7.107 las `jobboerse_karten` die HTML-Kommentare der
Plattform mit. Gespeichert wurden Jobware- und ingenieur.de-Stellen mit
Resten wie `t=3n <Titel>` und `qv q:s q:key= t=w <Ort> /qv` — und mit einer
Kennung, die aus dem Titel MIT Rest gebildet war. Der korrigierte Leser
allein haette das verschlimmert: ein sauberer Neufund bekommt eine andere
Kennung, und die Duplikat-Erkennung sortiert ihn ueber die gleiche URL als
`duplikat` des verfaelschten Eintrags aus (#951). Genau so hat es der Melder
beobachtet, schon mit dem Leser aus v1.7.104.

Deshalb stellt diese Heilung den Bestand VOR dem Speichern eines Suchlaufs
richtig:

* **Reste entfernen.** Die Kommentar-Reste sind ganze Tokens einer festen
  Form (`t=...`, `qv`, `/qv`, `q:...`). Gemessen am 14.09.2026 an echten
  Ergebnisseiten: der bereinigte verfaelschte Wert war in 36 von 36 Karten
  und allen drei Feldern ZEICHENGLEICH mit dem, was der korrigierte Leser
  liefert.
* **Das alte Format vor v1.7.104** mit: `Job"<Titel>"ansehen` und `inBerlin`.
* **Kennung richtigstellen.** Nur, wenn die gespeicherte Kennung
  nachweislich aus dem gespeicherten Titel gebildet wurde — mit der Formel
  des Adapters. Eine Zeile unbekannter Herkunft behaelt ihre Kennung.
* **Gibt es unter der richtigen Kennung schon eine Zeile**, ist es dieselbe
  Anzeige: die verfaelschte Zeile wird in sie ueberfuehrt. Die bestehende
  Zeile bekommt die sauberen Angaben, soweit ihre eigenen fehlen oder
  kaputt sind, und behaelt ihren Stand (aktiv oder aussortiert); alle
  Verweise (Bewerbungen, Fundstellen, Recherche, Kontakte) wandern mit; die
  Zusatzzeile verschwindet. So bleibt kein aussortierter `duplikat` als
  Altlast liegen.
* **Sonst zieht die Zeile auf die richtige Kennung um**, mit denselben
  Verweisen.
* **Entfernung und Score nachziehen** fuer jede geheilte Zeile.

Die Heilung ist idempotent: ein zweiter Lauf findet nichts mehr.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger("bewerbungs_assistent.karten_heilung")

#: Die beiden Quellen hinter dem gemeinsamen Kartenleser.
QUELLEN = ("jobware", "ingenieur_de")
FELDER = ("title", "company", "location")

_KOMMENTAR_REST = re.compile(r"(?<!\S)(?:/?qv|q:\S*|t=\S*)(?!\S)")
_ALTER_KNOPF = re.compile(r'^Job"(.+)"ansehen$', re.S)
_ALTES_IN = re.compile(r"^in(?=[A-ZÄÖÜ])")
_FIRMEN_PLATZHALTER = {"", "unbekannt", "nicht angegeben"}


def hat_rest(text) -> bool:
    return bool(_KOMMENTAR_REST.search(text or ""))


def bereinigen(text) -> str:
    """Kommentar-Reste entfernen, Leerraum glaetten."""
    return " ".join(_KOMMENTAR_REST.sub(" ", text or "").split())


def saubere_felder(zeile: dict) -> dict:
    """Titel, Firma und Ort ohne Kommentar-Reste und ohne das alte Format."""
    titel = bereinigen(zeile.get("title"))
    knopf = _ALTER_KNOPF.match(titel)
    if knopf:
        titel = " ".join(knopf.group(1).split())
    firma = bereinigen(zeile.get("company"))
    if not firma and (zeile.get("company") or ""):
        firma = "Unbekannt"  # nur Reste — wie der Adapter bei fehlender Firma
    ort = _ALTES_IN.sub("", bereinigen(zeile.get("location")))
    return {"title": titel, "company": firma, "location": ort}


def _teile(gespeichert: str) -> tuple[str, str]:
    """(`profil:`-Praefix, oeffentliche Kennung)."""
    _pid, sep, oeffentlich = (gespeichert or "").rpartition(":")
    return (gespeichert[: len(gespeichert) - len(oeffentlich)] if sep else ""), oeffentlich


def _ziel_kennung(zeile: dict, sauber: dict) -> str | None:
    """Die richtige oeffentliche Kennung — oder None, wenn die gespeicherte
    Kennung nicht nachweislich aus dem gespeicherten Titel stammt."""
    from ..job_scraper import stelle_hash
    from ..job_scraper.jobware import karten_hash

    _praefix, oeffentlich = _teile(zeile["hash"])
    roh = zeile.get("title") or ""
    if zeile.get("source") == "jobware":
        if oeffentlich == karten_hash(roh):  # Kartenweg, Titel mit Rest
            return karten_hash(sauber["title"])
        if oeffentlich == stelle_hash("jobware.de", roh):
            # JSON-LD-Weg, oder das alte Knopf-Format: dessen Kennung ist
            # bereits die des sauberen Titels im Kartenweg.
            if _ALTER_KNOPF.match(bereinigen(roh)):
                return karten_hash(sauber["title"])
            return stelle_hash("jobware.de", sauber["title"])
        return None
    if oeffentlich == stelle_hash("ingenieur.de", roh):
        return stelle_hash("ingenieur.de", sauber["title"])
    return None


def _tabellen_mit_stellenverweis(conn) -> list[str]:
    tabellen = []
    for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        if name == "jobs":
            continue
        if "job_hash" in {r[1] for r in conn.execute(f"PRAGMA table_info({name})")}:
            tabellen.append(name)
    return tabellen


def _verweise_umhaengen(conn, alt: str, neu: str) -> None:
    """Alle Verweise von `alt` auf `neu` — gespeicherte und oeffentliche
    Form, denn aeltere Wege legten die oeffentliche ab (v1.7.56 MERKE 4)."""
    paare = [(alt, neu)]
    alt_oeff, neu_oeff = _teile(alt)[1], _teile(neu)[1]
    if alt_oeff != alt:
        paare.append((alt_oeff, neu_oeff))
    for tabelle in _tabellen_mit_stellenverweis(conn):
        for von, nach in paare:
            if tabelle == "applications":
                # Eine Bewerbung wird nie geloescht, nur umgehaengt — und
                # zwar immer auf die GESPEICHERTE Kennung: `job_hash` hat
                # einen Fremdschluessel auf `jobs.hash`, eine oeffentliche
                # Form als Ziel schluege fehl und rollte die ganze Heilung
                # dieser Stelle zurueck.
                conn.execute("UPDATE applications SET job_hash=? WHERE job_hash=?", (neu, von))
            else:
                conn.execute(f"UPDATE OR IGNORE {tabelle} SET job_hash=? WHERE job_hash=?", (nach, von))
                # Uebrig bleiben nur Zeilen, die es unter `nach` schon gibt.
                conn.execute(f"DELETE FROM {tabelle} WHERE job_hash=?", (von,))
    try:
        for von, nach in paare:
            conn.execute("UPDATE OR IGNORE contact_links SET target_id=? "
                         "WHERE target_kind='job' AND target_id=?", (nach, von))
            conn.execute("DELETE FROM contact_links WHERE target_kind='job' AND target_id=?", (von,))
    except Exception as exc:  # pragma: no cover — Tabelle fehlt in alten Bestaenden
        logger.debug("contact_links nicht umgehaengt: %s", exc)


def _felder_setzen(conn, kennung: str, werte: dict, spalten: set) -> None:
    werte = {k: v for k, v in werte.items() if k in spalten}
    if not werte:
        return
    zuweisung = ", ".join(f"{k}=?" for k in werte)
    conn.execute(f"UPDATE jobs SET {zuweisung} WHERE hash=?", [*werte.values(), kennung])


def _felder_fuer_ziel(bestehend: dict, sauber: dict) -> dict:
    """Die bestehende Zeile behaelt, was sie sauber hat; fehlt es oder ist es
    ein Platzhalter, kommt der saubere Wert der ueberfuehrten Zeile."""
    eigen = saubere_felder(bestehend)
    werte = {}
    for feld in FELDER:
        wert = eigen[feld]
        if not wert or (feld == "company" and wert.lower() in _FIRMEN_PLATZHALTER):
            wert = sauber[feld] or wert
        werte[feld] = wert
    return werte


def heilen(db, *, dry_run: bool = False, koordinaten=None, bewerten=None,
           max_geocode: int = 100) -> dict:
    """Jobware- und ingenieur.de-Stellen richtigstellen.

    Args:
        koordinaten: (lat, lon) des Wohnorts — ohne sie wird keine
            Entfernung nachgezogen.
        bewerten: Funktion Zeile -> Score; ohne sie bleibt der Score.
    Returns:
        Zaehler, ohne Titel, Firmen oder Orte.
    """
    conn = db.connect()
    befund = {"geprueft": 0, "bereinigt": 0, "umgezogen": 0, "zusammengefuehrt": 0,
              "entfernung_nachgezogen": 0, "neu_bewertet": 0, "vorschau": dry_run}
    spalten = {r[1] for r in conn.execute("PRAGMA table_info(jobs)")}
    zeilen = [dict(r) for r in conn.execute(
        "SELECT * FROM jobs WHERE source IN (?, ?)", QUELLEN).fetchall()]
    befund["geprueft"] = len(zeilen)
    vorhanden = {r[0] for r in conn.execute("SELECT hash FROM jobs").fetchall()}
    geheilt: list[str] = []

    for zeile in zeilen:
        if zeile["hash"] not in vorhanden:
            continue  # bereits in eine andere Zeile ueberfuehrt
        sauber = saubere_felder(zeile)
        if all((zeile.get(f) or "") == sauber[f] for f in FELDER):
            continue
        befund["bereinigt"] += 1
        praefix, oeffentlich = _teile(zeile["hash"])
        ziel = praefix + (_ziel_kennung(zeile, sauber) or oeffentlich)

        if ziel == zeile["hash"]:
            if not dry_run:
                with conn:
                    _felder_setzen(conn, ziel, sauber, spalten)
        elif ziel in vorhanden:
            befund["zusammengefuehrt"] += 1
            if not dry_run:
                bestehend = dict(conn.execute("SELECT * FROM jobs WHERE hash=?", (ziel,)).fetchone())
                with conn:
                    _felder_setzen(conn, ziel, _felder_fuer_ziel(bestehend, sauber), spalten)
                    _verweise_umhaengen(conn, zeile["hash"], ziel)
                    conn.execute("DELETE FROM jobs WHERE hash=?", (zeile["hash"],))
            vorhanden.discard(zeile["hash"])
        else:
            befund["umgezogen"] += 1
            if not dry_run:
                reihenfolge = [r[1] for r in conn.execute("PRAGMA table_info(jobs)")]
                auswahl = ", ".join("?" if s == "hash" else s for s in reihenfolge)
                with conn:
                    conn.execute(f"INSERT INTO jobs ({', '.join(reihenfolge)}) "
                                 f"SELECT {auswahl} FROM jobs WHERE hash=?", (ziel, zeile["hash"]))
                    _felder_setzen(conn, ziel, sauber, spalten)
                    _verweise_umhaengen(conn, zeile["hash"], ziel)
                    conn.execute("DELETE FROM jobs WHERE hash=?", (zeile["hash"],))
            vorhanden.discard(zeile["hash"])
            vorhanden.add(ziel)
        geheilt.append(ziel)

    if dry_run:
        return befund
    geheilt = list(dict.fromkeys(geheilt))

    if koordinaten:
        from .geocoding_service import geocode_and_calculate_distance, geocode_location
        for kennung in geheilt[:max_geocode]:
            reihe = conn.execute("SELECT location FROM jobs WHERE hash=?", (kennung,)).fetchone()
            if not reihe or not reihe["location"]:
                continue
            try:
                entfernung = geocode_and_calculate_distance(reihe["location"], koordinaten[0], koordinaten[1])
                if entfernung is None:
                    continue
                koord = geocode_location(reihe["location"]) or (None, None)
                with conn:
                    _felder_setzen(conn, kennung, {"distance_km": entfernung,
                                                   "lat": koord[0], "lon": koord[1]}, spalten)
                befund["entfernung_nachgezogen"] += 1
            except Exception as exc:  # pragma: no cover — Netz darf die Heilung nicht stoppen
                logger.debug("Entfernung nicht nachgezogen: %s", exc)

    if bewerten:
        for kennung in geheilt:
            reihe = conn.execute("SELECT * FROM jobs WHERE hash=?", (kennung,)).fetchone()
            if not reihe:
                continue
            stelle = dict(reihe)
            try:
                score = bewerten(stelle)
            except Exception as exc:  # pragma: no cover
                logger.debug("Score nicht neu berechnet: %s", exc)
                continue
            with conn:
                _felder_setzen(conn, kennung, {"score": score,
                                               "fachscore": stelle.get("_fachscore"),
                                               "rahmenscore": stelle.get("_rahmenscore")}, spalten)
            befund["neu_bewertet"] += 1

    if befund["bereinigt"]:
        logger.info("Kartenleser-Heilung (#1041): %s", befund)
    return befund
