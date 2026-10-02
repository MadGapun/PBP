"""Die Firmen-Ansicht im Dashboard: alles, was PBP zu einer Firma weiß, als eine Zeitleiste (#1080, Stufe 2).

Die eine Quelle ist `firma_kontext_daten` (tools/bewerbungen.py) — dieselbe Antwort, die Claude über `firma_kontext` bekommt, damit Dashboard
und Chat nie Verschiedenes über dieselbe Firma sagen. Dieses Modul legt sie für Menschen aus: ein Eintrag je Bewerbung, Stelle, Kontakt,
Station im Lebenslauf, Dokument, Recherche und Blacklist-Eintrag, nach Datum sortiert, mit dem Sprung dorthin (`ziel`). Es liest nur.

Zeitleisten-Eintrag: ``{art, rolle, rolle_text, datum, titel, text, status, gefunden_als, aktuell, ziel, ref}``. `ziel` benennt die Seite
des Dashboards und die Kennung, die dort geöffnet wird (`seite`: bewerbungen | stellen | kontakte | profil | dokumente | suche).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger("bewerbungs_assistent.firmen_ansicht")

ARTEN = {
    "bewerbung": "Bewerbungen",
    "stelle": "Stellen",
    "kontakt": "Kontakte",
    "lebenslauf": "Lebenslauf",
    "korrespondenz": "Korrespondenz",
    "recherche": "Recherchen",
    "blacklist": "Blacklist",
    "erwaehnt": "In Notizen erwähnt",
}

ROLLEN_TEXT = {
    "bewerbungsziel": "Bewerbung",
    "vermittler": "Als Vermittler",
    "endkunde": "Als Endkunde",
    "arbeitgeber_frueher": "Früherer Arbeitgeber",
    "arbeitgeber_aktuell": "Aktueller Arbeitgeber",
    "projektkunde": "Projektkunde",
    "kontakt": "Kontakt",
    "anfrage": "Anfrage",
    "korrespondenz": "Korrespondenz",
    "stellenanzeige": "Stellenanzeige",
    "recherche": "Recherche",
    "blacklist": "Blacklist",
    "in_notizen_erwaehnt": "In Notizen erwähnt",
    "stelle": "Aktive Stelle",
}

DOKUMENT_TEXT = {
    "recruiter_anfrage": "Recruiter-Anfrage", "vermittler_korrespondenz": "Mail vom Vermittler", "email": "E-Mail",
    "absage": "Absage", "gespraechs_feedback": "Gesprächs-Feedback", "interview_einladung": "Einladung zum Gespräch",
    "interview_bestaetigung": "Bestätigung des Gesprächs", "eingangsbestaetigung": "Eingangsbestätigung",
    "bewerbungsantwort": "Antwort auf die Bewerbung", "angebot": "Angebot", "stellenbeschreibung": "Stellenbeschreibung",
    "stellenanzeige": "Stellenanzeige",
}

VIA_TEXT = {"schreibweise": "unter anderer Schreibweise", "mutterfirma": "bei der Mutterfirma", "tochterfirma": "bei einer Tochterfirma"}

_DATUM = re.compile(r"^\d{4}(?:-\d{2}(?:-\d{2})?)?")


def _datum(wert) -> str:
    """Das Datum als 'JJJJ', 'JJJJ-MM' oder 'JJJJ-MM-TT' — oder ''. Zeitstempel werden auf den Tag gekürzt."""
    m = _DATUM.match(str(wert or "").strip())
    return m.group(0) if m else ""


def _eintrag(art: str, rolle: str, titel: str, *, datum="", text="", status="", gefunden_als="", via="", aktuell=None, ziel=None, ref=None) -> dict:
    return {"art": art, "rolle": rolle, "rolle_text": ROLLEN_TEXT.get(rolle, rolle), "datum": _datum(datum), "titel": titel or "",
            "text": text or "", "status": status or "", "gefunden_als": gefunden_als or "", "via": via or "",
            "via_text": VIA_TEXT.get(via or "", ""), "aktuell": aktuell, "ziel": ziel or {}, "ref": ref or {}}


def _aus_bewerbung(b: dict) -> dict:
    rolle = b.get("rolle") or "bewerbungsziel"
    if rolle == "endkunde" and b.get("vermittler"):
        text = f"Endkunde, die Bewerbung läuft über {b['vermittler']}"
    elif rolle == "vermittler" and b.get("endkunde"):
        text = f"Vermittler für {b['endkunde']}"
    elif rolle == "bewerbungsziel" and b.get("vermittler"):
        text = f"über {b['vermittler']}"
    else:
        text = ""
    if b.get("termine"):
        text = (text + ", " if text else "") + f"{b['termine']} Termin" + ("e" if b["termine"] != 1 else "")
    return _eintrag("bewerbung", rolle, b.get("titel"), datum=b.get("beworben_am"), text=text, status=b.get("status"),
                    gefunden_als=b.get("firma") if b.get("via") else "", via=b.get("via"),
                    ziel={"seite": "bewerbungen", "bewerbung_id": b.get("bewerbung_id_voll") or b.get("bewerbung_id")},
                    ref={"bewerbung_id": b.get("bewerbung_id_voll") or b.get("bewerbung_id")})


def _aus_stelle(s: dict) -> dict:
    teile = []
    if s.get("score") not in (None, ""):
        teile.append(f"{s['score']} Punkte")
    if s.get("repost_warnung"):
        teile.append(s.get("repost_details", {}).get("kurz") or "schon einmal beworben")
    return _eintrag("stelle", "stelle", s.get("titel"), datum=s.get("gefunden_am"), text=", ".join(teile), via=s.get("via"),
                    ziel={"seite": "stellen", "job_hash": s.get("hash")}, ref={"job_hash": s.get("hash")})


def _aus_bezug(b: dict) -> Optional[dict]:
    """Ein Bezug aus `firmen_bezuege.bezuege` (nicht die Bewerbungen und Stellen, die kommen aus dem Werkzeug) als Eintrag — oder None."""
    rolle, quelle = b.get("rolle") or "", b.get("quelle") or ""
    via = b.get("via") or ""
    als = b.get("name") if via == "schreibweise" else ""
    if rolle in ("arbeitgeber_frueher", "arbeitgeber_aktuell"):
        von, bis = b.get("von") or "", b.get("bis") or ""
        return _eintrag("lebenslauf", rolle, b.get("titel"), datum=von, text=f"{von or '?'} bis {bis or 'heute'}", gefunden_als=als, via=via,
                        aktuell=rolle == "arbeitgeber_aktuell", ziel={"seite": "profil"}, ref={"position_id": b.get("position_id")})
    if rolle == "projektkunde":
        was = "Vertrauliches Projekt" if b.get("vertraulich") else (b.get("projekt") or "Projekt")
        return _eintrag("lebenslauf", rolle, was, text=f"bei {b.get('bei_arbeitgeber') or '?'}", gefunden_als=als, via=via,
                        ziel={"seite": "profil"}, ref={"projekt_id": b.get("projekt_id")})
    if rolle == "kontakt":
        text = ", ".join(x for x in (b.get("funktion"), b.get("zeitraum")) if x)
        return _eintrag("kontakt", rolle, b.get("person"), datum=b.get("von"), text=text, gefunden_als=als, via=via, aktuell=b.get("aktuell"),
                        ziel={"seite": "kontakte", "suche": b.get("person") or ""},
                        ref={"kontakt_id": b.get("kontakt_id"), "zuordnung_id": b.get("zuordnung_id") or "",
                             "rolle": b.get("rolle_dort") or "", "von": b.get("von") or "", "bis": b.get("bis") or ""})
    if quelle == "dokument":
        return _eintrag("korrespondenz", rolle, DOKUMENT_TEXT.get(b.get("typ") or "", b.get("typ") or "Dokument"), datum=b.get("datum"),
                        text=b.get("name") or "", gefunden_als=als, via=via,
                        ziel={"seite": "dokumente", "dokument_id": b.get("dokument_id")}, ref={"dokument_id": b.get("dokument_id")})
    if rolle == "recherche":
        ziel = {"seite": "bewerbungen", "bewerbung_id": b.get("bewerbung_id")} if b.get("bewerbung_id") else {"seite": "bewerbungen"}
        return _eintrag("recherche", rolle, (b.get("kategorie") or "Recherche").replace("_", " ").capitalize(), datum=b.get("datum"),
                        ziel=ziel, ref={"recherche_id": b.get("recherche_id")})
    if rolle == "blacklist":
        return _eintrag("blacklist", rolle, b.get("name") or "Blacklist", text=b.get("grund") or "ohne Begründung", gefunden_als=als, via=via,
                        ziel={"seite": "suche"})
    if rolle == "in_notizen_erwaehnt":
        text = "in den Notizen" + (f", Bewerbung über {b['ueber_vermittler']}" if b.get("ueber_vermittler") else "")
        return _eintrag("erwaehnt", rolle, b.get("titel"), datum=b.get("datum"), text=text, status=b.get("status"),
                        ziel={"seite": "bewerbungen", "bewerbung_id": b.get("bewerbung_id")}, ref={"bewerbung_id": b.get("bewerbung_id")})
    return None


def _sortiert(eintraege: list) -> list:
    """Neueste zuerst; ohne Datum ans Ende (in der Reihenfolge, in der sie kamen)."""
    mit = sorted((e for e in eintraege if e["datum"]), key=lambda e: e["datum"], reverse=True)
    return mit + [e for e in eintraege if not e["datum"]]


def ansicht(db, *, name: str = "", firma_id: str = "") -> dict:
    """Alles zu einer Firma für das Dashboard. Entweder über die Kennung eines Firmen-Eintrags oder über einen Namen (auch ohne Eintrag)."""
    from ..tools.bewerbungen import firma_kontext_daten
    from . import firmen_stamm as fs
    from .dashboard_link import firma_link

    gesucht = (name or "").strip()
    if firma_id:
        f = fs.firma_laden(db, firma_id)
        if f is None:
            return {"status": "nicht_gefunden", "text": "Diesen Firmen-Eintrag gibt es nicht (mehr)."}
        gesucht = f["name"]
    if not gesucht:
        return {"status": "fehler", "text": "Es fehlt der Name oder die Kennung der Firma."}

    daten = firma_kontext_daten(db, gesucht, logger, roh=True)
    if daten.get("fehler"):
        return {"status": "fehler", "text": daten["fehler"]}
    stamm = None
    if daten.get("stammsatz"):
        stamm = fs.firma_laden(db, daten["stammsatz"]["id"])
    eintraege = [_aus_bewerbung(b) for b in daten.get("bewerbungen", [])]
    eintraege += [_aus_stelle(s) for s in daten.get("aktive_stellen", [])]
    for b in daten.get("_roh_bezuege", []):
        e = _aus_bezug(b)          # Bewerbungen (Ziel, Vermittler, Endkunde) kennt `_aus_bezug` nicht: sie kommen aus dem Werkzeug, mit Terminen
        if e:
            eintraege.append(e)
    zeitleiste = _sortiert([e for e in eintraege if e])

    zaehlung = {art: 0 for art in ARTEN}
    for e in zeitleiste:
        zaehlung[e["art"]] += 1
    gruende = daten.get("aussortiert_gruende") or {}
    return {
        "status": "ok",
        "name": stamm["name"] if stamm else gesucht,
        "gefunden": bool(daten.get("gefunden")),
        "stammsatz": stamm,
        "mehrdeutig": daten.get("stammsatz_mehrdeutig") or [],
        "warnungen": daten.get("warnungen") or [],
        "zaehlung": zaehlung,
        "arten": ARTEN,
        "zeitleiste": zeitleiste,
        "aussortiert": {"anzahl": daten.get("aussortiert_anzahl", 0), "gruende": gruende, "beispiele": daten.get("aussortiert_beispiele") or []},
        "schreibweisen": daten.get("schreibweisen") or [],
        "aehnliche": daten.get("aehnliche_firmen") or [],
        "dashboard_link": firma_link(stamm["id"] if stamm else gesucht),
    }
