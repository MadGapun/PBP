"""Einstellungen, Verlauf und Statusdatei des Auto-Updates (#1093).

Drei Orte, je einer fuer eine Art von Wissen:

* **Einstellungen und Verlauf** — in der Datenbank (`settings`): sie gehoeren dem Menschen und
  ueberstehen eine Neuinstallation des Programmordners. Der Verlauf ist das Protokoll aus der
  Verbesserung 5 in #1093: jede Installation mit Version, Quelle, Pruefsumme und Ergebnis.
* **Statusdatei** (`update_status.json` im Programmordner) — Wissen, das der Startbaustein VOR der
  Datenbank braucht: welcher Start ist bestaetigt, welche Fassung war die vorige, was ist
  zurueckgenommen worden. Das Lesen und Schreiben kommt vom Startbaustein selbst (eine Frage,
  eine Funktion).

Die vier Stufen (Entscheidung des Nutzers vom 02.10.2026):

    aus           nur der Hinweis „Neue Version verfügbar“ mit Link (heutiger Stand)
    hinweis       der Hinweis startet das Update mit EINEM Klick, nichts von Hand laden
    auto_meldung  PBP laedt und installiert selbst und meldet es danach
    auto_still    wie zuvor, aber still

Die Vorgabe ist **aus**. Eine unbekannte oder kaputte Einstellung gilt ebenfalls als **aus**:
bei einer Funktion, die Code ohne Rueckfrage ausfuehrt, ist der sichere Zustand der
restriktive (wie in #947: im Zweifel nie in Richtung "mehr Zugriff").
"""
from __future__ import annotations

from datetime import datetime, timezone

import bewerbungs_assistent_boot as _boot

from . import fassung as _fassung
from . import layout

STUFEN = ("aus", "hinweis", "auto_meldung", "auto_still")
VORGABE_STUFE = "aus"
AUTOMATISCHE_STUFEN = ("auto_meldung", "auto_still")

VORGAENGER_MIN, VORGAENGER_MAX, VORGAENGER_VORGABE = 1, 10, 3
INSTALLER_AUFRAEUMEN = ("fragen", "immer", "nie")
VERLAUF_MAX = 50

K_STUFE = "auto_update_stufe"
K_VORGAENGER = "auto_update_vorgaenger_behalten"
K_INSTALLER = "installer_aufraeumen"
K_GEFRAGT = "auto_update_gefragt"
K_VERLAUF = "auto_update_verlauf"


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── Einstellungen ──────────────────────────────────────────────────────────────────────

def stufe(db) -> str:
    wert = db.get_setting(K_STUFE, VORGABE_STUFE)
    return wert if wert in STUFEN else VORGABE_STUFE


def stufe_setzen(db, wert: str) -> str:
    if wert not in STUFEN:
        raise ValueError(f"Unbekannte Stufe: {wert!r}. Erlaubt: {', '.join(STUFEN)}")
    db.set_setting(K_STUFE, wert)
    return wert


def vorgaenger_behalten(db) -> int:
    zahl = db.get_setting_zahl(K_VORGAENGER, VORGAENGER_VORGABE)
    return min(max(zahl, VORGAENGER_MIN), VORGAENGER_MAX)


def vorgaenger_setzen(db, zahl) -> int:
    try:
        n = int(zahl)
    except (TypeError, ValueError) as exc:
        raise ValueError("Die Zahl der behaltenen Fassungen muss eine ganze Zahl sein.") from exc
    if isinstance(zahl, bool) or not VORGAENGER_MIN <= n <= VORGAENGER_MAX:
        raise ValueError(f"Erlaubt sind {VORGAENGER_MIN} bis {VORGAENGER_MAX} Fassungen.")
    db.set_setting(K_VORGAENGER, n)
    return n


def installer_aufraeumen(db) -> str:
    wert = db.get_setting(K_INSTALLER, "fragen")
    return wert if wert in INSTALLER_AUFRAEUMEN else "fragen"


def installer_aufraeumen_setzen(db, wert: str) -> str:
    if wert not in INSTALLER_AUFRAEUMEN:
        raise ValueError(f"Unbekannte Auswahl: {wert!r}. Erlaubt: {', '.join(INSTALLER_AUFRAEUMEN)}")
    db.set_setting(K_INSTALLER, wert)
    return wert


# ── Rueckfrage (Akzeptanzkriterium 10) ─────────────────────────────────────────────────

def gefragt(db) -> dict:
    """{'antwort': 'ja'|'nein'|'spaeter'|None, 'bei_version': str|None}."""
    wert = db.get_setting(K_GEFRAGT, None)
    if not isinstance(wert, dict) or wert.get("antwort") not in ("ja", "nein", "spaeter"):
        return {"antwort": None, "bei_version": None}
    bei = wert.get("bei_version") if _fassung.gueltig(wert.get("bei_version")) else None
    return {"antwort": wert["antwort"], "bei_version": bei}


def antwort_merken(db, antwort: str, bei_version=None) -> dict:
    if antwort not in ("ja", "nein", "spaeter"):
        raise ValueError("Antwort muss ja, nein oder spaeter sein.")
    wert = {"antwort": antwort, "bei_version": bei_version if _fassung.gueltig(bei_version) else None, "zeit": _jetzt()}
    db.set_setting(K_GEFRAGT, wert)
    return gefragt(db)


def frage_faellig(db, neue_version) -> bool:
    """Soll PBP jetzt fragen, ob Updates automatisch installiert werden?

    Nur zusammen mit der Meldung ueber eine neue Version (Nutzerwort 02.10.2026, Frage 4): nie beim
    blossen Start. Ja/Nein sind endgueltig; „Später“ gilt bis eine NEUERE Version als die gemeldet wird.
    """
    if not _fassung.gueltig(neue_version):
        return False
    g = gefragt(db)
    if g["antwort"] in ("ja", "nein"):
        return False
    if g["antwort"] == "spaeter" and g["bei_version"]:
        return _fassung.ist_neuer(neue_version, g["bei_version"])
    return True


# ── Verlauf ─────────────────────────────────────────────────────────────────────────────

def verlauf(db) -> list:
    daten = db.get_setting(K_VERLAUF, [])
    return [e for e in daten if isinstance(e, dict)] if isinstance(daten, list) else []


def verlauf_anhaengen(db, **eintrag) -> dict:
    """Haengt einen Eintrag an (neueste zuletzt, hoechstens `VERLAUF_MAX`)."""
    eintrag = {"zeit": _jetzt(), **eintrag}
    eintraege = verlauf(db) + [eintrag]
    db.set_setting(K_VERLAUF, eintraege[-VERLAUF_MAX:])
    return eintrag


# ── Statusdatei im Programmordner ──────────────────────────────────────────────────────

def start_bestaetigen() -> bool:
    """Server und Dashboard rufen das auf, sobald sie bereit sind. Ohne Programmordner passiert nichts.

    Ohne diese Bestaetigung zaehlt der Start fuer den Startbaustein als nicht gelungen und eine
    neue Fassung wird nach zwei solchen Starts zurueckgenommen (Akzeptanzkriterium 5).
    """
    app, version = layout.programmordner(), layout.laufende_fassung()
    if app is None or version is None:
        return False
    try:
        return _boot.start_bestaetigen(app, version)
    except Exception:
        return False


def status_lesen(app=None) -> dict:
    app = app if app is not None else layout.programmordner()
    return _boot.lese_status(app) if app is not None else {"format": _boot.FORMAT}


def rueckgang_offen(app=None) -> dict | None:
    """Eine Zuruecknahme, die der Mensch noch nicht gesehen hat (sonst None)."""
    r = status_lesen(app).get("rueckgang")
    return r if isinstance(r, dict) and not r.get("gemeldet") else None


def rueckgang_gesehen(app=None) -> bool:
    app = app if app is not None else layout.programmordner()
    if app is None:
        return False
    s = _boot.lese_status(app)
    if isinstance(s.get("rueckgang"), dict):
        s["rueckgang"]["gemeldet"] = True
        _boot.schreibe_status(app, s)
        return True
    return False


def gescheiterte_fassungen(app=None) -> list:
    g = status_lesen(app).get("gescheitert")
    return [v for v in g if isinstance(v, str)] if isinstance(g, list) else []
