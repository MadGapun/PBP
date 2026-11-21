"""Die Inhalte des Nachweises der Bewerbungsbemuehungen (#798, Stufe 3).

Der Nachweis geht an Agentur oder Jobcenter. Er enthaelt nur, was der Mensch
getan hat: Liste, Tage, Termine, auf Wunsch Kosten. Keine Punkte, keine
Anteile, keine Gruende einer Absage, nichts zur Stellensuche. Deshalb liest
dieses Modul die Notiz- und Grundfelder gar nicht erst.

Abgrenzung: `bericht_daten` rechnet die Kennzahlen; hier stehen die Zeilen,
die nur der Nachweis braucht (Tabelle, Wochenleiste, "Was an welchem Tag").
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from . import bericht_daten as _kern
from . import bericht_zeitraum as _bz
from .anzeigenamen import bewerbungsart_text, datum_text, quelle_text, status_text
from .bewerbung_status import laeuft

#: Ein Statuswechsel, der vom Arbeitgeber kommt.
RUECKMELDUNG_STATUS = (
    "eingangsbestaetigung", "in_pruefung", "interview", "zweitgespraech", "angebot",
    "abgelehnt", "arbeitgeber_ausgefallen",
)
#: So heisst die Rueckmeldung im Nachweis.
RUECKMELDUNG_TEXT = {
    "eingangsbestaetigung": "Eingang bestätigt",
    "in_pruefung": "Bewerbung wird geprüft",
    "interview": "Einladung zum Gespräch",
    "zweitgespraech": "Einladung zum Zweitgespräch",
    "angebot": "Angebot",
    "abgelehnt": "Absage",
    "arbeitgeber_ausgefallen": "Verfahren vom Arbeitgeber beendet",
}
#: Termine, die nicht stattgefunden haben, zaehlen nicht.
TERMIN_OHNE_GESPRAECH = ("abgesagt", "verschoben")
#: Vertragstermine und Sonstiges sind kein Gespraech mit dem Arbeitgeber.
TERMIN_KEIN_GESPRAECH = ("sonstiges", "vertrag")
TERMIN_TEXT = {
    "interview": "Vorstellungsgespräch", "telefon": "Telefongespräch",
    "video": "Videogespräch", "vor_ort": "Gespräch vor Ort",
    "kennenlernen": "Kennenlerngespräch", "zweitgespraech": "Zweitgespräch",
    "assessment": "Auswahlverfahren", "probearbeiten": "Probearbeiten",
}
#: Mehr Wochen passen nicht als Leiste auf die Seite.
MAX_WOCHEN = 14

_WOCHENTAG = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")


def _firma_stelle(a: dict) -> str:
    return ", ".join(t for t in (a.get("company"), a.get("title")) if t)


def _weg(a: dict) -> str:
    roh = (a.get("source") or a.get("portal_name") or "").strip()
    return quelle_text(roh) if roh else "nicht erfasst"


def _im(tag: str, von: str, bis: str) -> bool:
    return bool(tag) and (not von or tag >= von) and (not bis or tag <= bis)


def _tag_text(tag: str) -> str:
    d = date.fromisoformat(tag)
    return f"{_WOCHENTAG[d.weekday()]} {d.day:02d}.{d.month:02d}."


def _plural(n: int, eins: str, viele: str) -> str:
    return f"{n} {eins if n == 1 else viele}"


def _ereignisse(db, ids: set) -> dict:
    erg: dict = {}
    for r in db.connect().execute(
            "SELECT application_id, status, event_date FROM application_events "
            "ORDER BY event_date").fetchall():
        if r["application_id"] in ids:
            erg.setdefault(r["application_id"], []).append(
                {"status": r["status"] or "", "tag": (r["event_date"] or "")[:10]})
    return erg


def _termine(db, ids: set, von: str, bis: str) -> list:
    rows = db.connect().execute(
        "SELECT application_id, meeting_date, meeting_type, status FROM application_meetings "
        "WHERE (profile_id=? OR profile_id IS NULL) ORDER BY meeting_date",
        (db.get_active_profile_id(),)).fetchall()
    return [{"app": r["application_id"], "tag": (r["meeting_date"] or "")[:10],
             "art": r["meeting_type"] or "interview"}
            for r in rows
            if r["application_id"] in ids
            and (r["status"] or "") not in TERMIN_OHNE_GESPRAECH
            and (r["meeting_type"] or "") not in TERMIN_KEIN_GESPRAECH
            and _im((r["meeting_date"] or "")[:10], von, bis)]


def _nachfassen(db, ids: set, von: str, bis: str) -> list:
    rows = db.connect().execute(
        "SELECT application_id, completed_at FROM follow_ups WHERE status='gesendet'").fetchall()
    return [{"app": r["application_id"], "tag": (r["completed_at"] or "")[:10]}
            for r in rows
            if r["application_id"] in ids and _im((r["completed_at"] or "")[:10], von, bis)]


def _wochen(zeilen: list, von: str, bis: str, stichtag: str) -> list:
    """Je Kalenderwoche, was geschah; eine kuenftige Woche heisst "noch offen"."""
    tage = sorted(z["iso"] for z in zeilen)
    start = von or (tage[0] if tage else "")
    ende = bis or stichtag
    if not start or start > ende:
        return []
    d = date.fromisoformat(start)
    d -= timedelta(days=d.weekday())
    letzte = date.fromisoformat(ende)
    wochen: list = []
    while d <= letzte:
        kw_ende = d + timedelta(days=6)
        drin = [z for z in zeilen if d.isoformat() <= z["iso"] <= kw_ende.isoformat()]
        b = sum(1 for z in drin if z["art"] == "Bewerbung")
        g = sum(1 for z in drin if z["art"] == "Gespräch")
        r = sum(1 for z in drin if z["art"] == "Rückmeldung")
        teile = [t for t, n in (
            (_plural(b, "Bewerbung", "Bewerbungen"), b), (_plural(g, "Gespräch", "Gespräche"), g),
            (_plural(r, "Rückmeldung", "Rückmeldungen"), r)) if n]
        zukunft = d.isoformat() > stichtag
        wochen.append({"kw": f"KW {d.isocalendar()[1]:02d}", "anzahl": b + g + r,
                       "text": "noch offen" if zukunft else (", ".join(teile) or "nichts erfasst")})
        d += timedelta(days=7)
    return wochen if len(wochen) <= MAX_WOCHEN else []


def nachweis_daten(db, von: str = "", bis: str = "", heute: Optional[str] = None,
                   mit_kosten: bool = False) -> dict:
    """Alle Inhalte des Nachweises. Kosten nur, wenn der Mensch das will."""
    von, bis = (von or "")[:10], (bis or "")[:10]
    heute = (heute or date.today().isoformat())[:10]
    kern = _kern.bericht_daten(db, von, bis, heute=heute)
    stichtag = kern["zeitraum"]["stichtag"]

    alle = [a for a in db.get_applications() if (a.get("status") or "") != "in_vorbereitung"]
    nach_id = {a["id"]: a for a in alle}
    ids = set(nach_id)
    apps = sorted((a for a in alle if _bz.im_zeitraum(a, von, bis)),
                  key=lambda a: (_bz.tag(a), a.get("company") or ""))
    ereignisse = _ereignisse(db, ids)
    termine = _termine(db, ids, von, bis or stichtag)

    bewerbungen = []
    for nr, a in enumerate(apps, 1):
        status = a.get("status") or ""
        letzte = [e for e in ereignisse.get(a["id"], []) if e["status"] == status and e["tag"]]
        art = bewerbungsart_text(a.get("bewerbungsart")) if a.get("bewerbungsart") else ""
        bewerbungen.append({
            "nr": nr, "datum": datum_text(_bz.tag(a)),
            "firma": a.get("company") or "", "stelle": a.get("title") or "",
            "weg": ", ".join(t for t in (_weg(a), art) if t),
            "stand": status_text(status),
            "stand_datum": datum_text(letzte[-1]["tag"]) if letzte else "",
        })

    frueher = sorted((a for a in alle if von and laeuft(a.get("status"))
                      and _bz.tag(a) and _bz.tag(a) < von), key=_bz.tag)
    laufende = [{"datum": datum_text(_bz.tag(a)), "firma": a.get("company") or "",
                 "stelle": a.get("title") or "", "stand": status_text(a.get("status"))}
                for a in frueher]

    chronik: list = []

    def eintrag(tag: str, art: str, a: dict, zusatz: str = ""):
        frueher_beworben = _bz.tag(a) and not _im(_bz.tag(a), von, bis)
        hinweis = f" (Bewerbung vom {datum_text(_bz.tag(a))})" if frueher_beworben else ""
        was = ", ".join(t for t in (a.get("company"), zusatz or a.get("title")) if t)
        chronik.append({"iso": tag, "tag": _tag_text(tag), "art": art, "was": was + hinweis})

    for a in apps:
        if _bz.tag(a):
            eintrag(_bz.tag(a), "Bewerbung", a)
    termin_tage = {(t["app"], t["tag"]) for t in termine}
    for t in termine:
        eintrag(t["tag"], "Gespräch", nach_id[t["app"]], TERMIN_TEXT.get(t["art"], "Gespräch"))
    for aid, evs in ereignisse.items():
        gesehen = set()
        for e in evs:
            if e["status"] not in RUECKMELDUNG_STATUS or not _im(e["tag"], von, bis or stichtag):
                continue
            if (aid, e["tag"]) in termin_tage and e["status"] in ("interview", "zweitgespraech"):
                continue            # derselbe Tag steht schon als Gespraech da
            if (e["status"], e["tag"]) in gesehen:
                continue
            gesehen.add((e["status"], e["tag"]))
            eintrag(e["tag"], "Rückmeldung", nach_id[aid], RUECKMELDUNG_TEXT[e["status"]])
    for n in _nachfassen(db, ids, von, bis or stichtag):
        eintrag(n["tag"], "Nachfassen", nach_id[n["app"]], "Nachfrage zur Bewerbung")
    reihenfolge = {"Bewerbung": 0, "Gespräch": 1, "Nachfassen": 2, "Rückmeldung": 3}
    chronik.sort(key=lambda z: (z["iso"], reihenfolge[z["art"]], z["was"]))

    laufend_gesamt = kern["kennzahlen"]["laufen"]["wert"]
    kacheln = [
        {"name": "Bewerbungen", "wert": len(bewerbungen), "hinweis": "im Zeitraum abgeschickt"},
        {"name": "Gespräche", "wert": len(termine), "hinweis": "im Zeitraum geführt"},
        {"name": "Rückmeldungen", "wert": sum(1 for z in chronik if z["art"] == "Rückmeldung"),
         "hinweis": "von Arbeitgebern erhalten"},
        {"name": "Laufende Verfahren", "wert": laufend_gesamt,
         "hinweis": f"am {datum_text(stichtag)}, mit früheren" if laufende
         else f"am {datum_text(stichtag)}"},
    ]
    kosten = None
    if mit_kosten:
        k = _bz.kosten_im_zeitraum(db, von, bis)
        kosten = {"summe_eur": k["summe_eur"], "ohne_datum": k["ohne_datum"], "posten": [
            {"datum": datum_text(p.get("incurred_at")), "kind": p.get("kind") or "sonstiges",
             "was": p.get("description") or "", "betrag": float(p.get("amount") or 0)}
            for p in k["posten"]]}
    return {
        "zeitraum": kern["zeitraum"],
        "stichtag_text": datum_text(stichtag),
        "erstellt_text": datum_text(heute),
        "kacheln": kacheln,
        "wochen": _wochen(chronik, von, bis, stichtag),
        "bewerbungen": bewerbungen,
        "laufende_frueher": laufende,
        "chronik": [{k: z[k] for k in ("tag", "art", "was")} for z in chronik],
        "kosten": kosten,
    }
