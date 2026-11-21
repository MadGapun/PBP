"""Der Datenkern von Nachweis, Auswertung und Statistik-Seite (#798, Stufe 2).

`bericht_daten(db, von, bis)` liefert jede Zahl EINMAL: als Wert mit Anzahl,
Basis, Bezug ("im Zeitraum" oder "am Stichtag"), Zustand und fertigem Text.
Die Dokumente rechnen nichts mehr selbst, sie zeigen `text`.

Regeln (docs/internal/redesign-bericht/AUFTRAG.md):

- Kleine Fallzahlen: unter 10 Faellen "4 von 4" statt Prozent; ein Median erst
  ab 3 Faellen und immer mit Anzahl und Spanne.
- Unbekannt ist ein eigener Zustand: "noch keine Angabe", nie 0,0.
- Zeit vor PBP: Nachgetragene Bewerbungen zaehlen bei Anzahlen mit, bei Dauer
  und Antwortzeit nicht; die Zahl der nachgetragenen steht dabei.
- Datenluecken sind eine eigene Zeile ("Weg nicht erfasst"), kein Rest.
- Stufen ohne belastbare Zahl entfallen und werden genannt.

Abgrenzung: `bericht_zeitraum` rechnet die Quoten und filtert die Daten des
heutigen Berichts und bleibt die eine Quoten-Rechnung; `statistik_erweitert`
rechnet Dauer und Kanaele. Dieses Modul setzt beides zu Kennzahlen zusammen.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

from . import bericht_zeitraum as _bz
from . import statistik_erweitert as _se
from .anzeigenamen import datum_text, followup_text, quelle_text, status_text
from .bewerbung_status import laeuft

IM_ZEITRAUM = "im Zeitraum"
AM_STICHTAG = "am Stichtag"
UNBEKANNT = "noch keine Angabe"

#: Ab dieser Basis steht eine Prozentzahl, darunter "n von m".
MIN_FUER_PROZENT = 10
#: Ab dieser Fallzahl steht ein Median.
MIN_FUER_MEDIAN = 3
#: So viele Zeilen zeigt eine Liste, danach "und N weitere".
MAX_ZEILEN = 7

#: Kanal aus `statistik_erweitert` -> Gruppe im Bericht, in dieser Reihenfolge.
WEG_GRUPPEN = {
    "portal": "Portale",
    "vermittler_recruiter": "Personalvermittler",
    "direktbewerbung": "Direkt beim Arbeitgeber",
    "netzwerk": "Netzwerk und Empfehlung",
}
WEG_LUECKE = "Weg nicht erfasst"
WEG_LUECKE_SATZ = "Das ist eine Lücke in den Daten und kein Ergebnis."

#: Trichter-Stufen, die heute keine belastbare Zahl haben (AUFTRAG, Abschnitt 7).
STUFEN_OHNE_ZAHL = {
    "Antwort erhalten": "Abgelaufene Verfahren lassen sich nicht von Antworten trennen.",
    "Zweitgespräch": "Zweitgespräche werden nicht eigens erfasst.",
}


def _zahl(wert: float) -> str:
    return f"{wert:.1f}".replace(".", ",")


def _tage(wert: float) -> str:
    text = _zahl(wert)
    text = text[:-2] if text.endswith(",0") else text
    return f"{text} {'Tag' if wert == 1 else 'Tage'}"


def _faelle(n: int) -> str:
    return f"{n} {'Fall' if n == 1 else 'Fälle'}"


def anzahl(n: int, bezug: str = IM_ZEITRAUM) -> dict:
    """Eine reine Anzahl. Null ist hier ein Wert, keine Luecke."""
    return {"zustand": "wert", "wert": n, "anzahl": n, "bezug": bezug, "text": str(n)}


def anteil(n: int, basis: int, bezug: str = IM_ZEITRAUM) -> dict:
    """Ein Anteil: unter `MIN_FUER_PROZENT` Faellen als "n von m"."""
    if not basis:
        return {"zustand": "unbekannt", "wert": None, "anzahl": 0, "basis": 0,
                "bezug": bezug, "text": UNBEKANNT}
    prozent = round(n / basis * 100, 1)
    klein = basis < MIN_FUER_PROZENT
    return {
        "zustand": "wert", "wert": None if klein else prozent, "anzahl": n,
        "basis": basis, "bezug": bezug,
        "text": f"{n} von {basis}" if klein else f"{_zahl(prozent)} % ({n} von {basis})",
    }


def dauer(werte: Optional[dict], bezug: str = IM_ZEITRAUM) -> dict:
    """Eine Dauer aus `_median_mittel`: Median ab 3 Faellen, mit Anzahl und Spanne."""
    werte = werte or {}
    n = int(werte.get("anzahl") or 0)
    if n < MIN_FUER_MEDIAN:
        text = UNBEKANNT if not n else f"{UNBEKANNT} (erst {_faelle(n)})"
        return {"zustand": "unbekannt", "wert": None, "anzahl": n, "bezug": bezug, "text": text}
    median, kurz, lang = werte["median_tage"], werte["min_tage"], werte["max_tage"]
    return {
        "zustand": "wert", "wert": median, "anzahl": n, "spanne": [kurz, lang], "bezug": bezug,
        "text": f"{_tage(median)} (Median aus {n} Fällen, {_zahl(kurz)} bis {_tage(lang)})",
    }


def begrenzt(zeilen: list, maximal: int = MAX_ZEILEN) -> dict:
    """Eine Liste mit hoechstens `maximal` Zeilen und dem Rest als Zahl."""
    rest = max(0, len(zeilen) - maximal)
    return {"zeilen": zeilen[:maximal], "weitere": rest,
            "weitere_text": f"und {rest} weitere" if rest else ""}


def _monate(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + b.month - a.month + 1


def _abschnitt(tag: str, art: str) -> str:
    jahr, monat = tag[:4], int(tag[5:7])
    if art == "jahr":
        return jahr
    if art == "quartal":
        return f"{jahr}-Q{(monat - 1) // 3 + 1}"
    return f"{jahr}-{monat:02d}"


def _abschnitt_text(schluessel: str, art: str) -> str:
    if art == "jahr":
        return schluessel
    if art == "quartal":
        return f"{schluessel[6]}. Quartal {schluessel[:4]}"
    return f"{schluessel[5:7]}.{schluessel[:4]}"


def zeitachse(apps: Iterable[dict], von: str, bis: str) -> dict:
    """Bis 12 Monate je Monat, bis 5 Jahre je Quartal, darueber je Jahr.

    Leere Abschnitte bleiben als Luecke stehen. `gespraeche` zaehlt die
    Bewerbungen des Abschnitts, die ein Gespraech erreicht haben; so ergibt
    die Summe dieselbe Zahl wie die Kennzahl "mit Gespräch".
    """
    apps = [a for a in apps if _bz.tag(a)]
    tage = sorted(_bz.tag(a) for a in apps)
    start = von[:10] or (tage[0] if tage else "")
    ende = bis[:10] or (tage[-1] if tage else "")
    if not start or not ende or start > ende:
        return {"art": "monat", "abschnitte": []}
    d1, d2 = date.fromisoformat(start), date.fromisoformat(ende)
    n = _monate(d1, d2)
    art = "monat" if n <= 12 else "quartal" if n <= 60 else "jahr"

    werte: dict = {}
    jahr, monat = d1.year, d1.month
    for _ in range(n):
        werte.setdefault(_abschnitt(f"{jahr}-{monat:02d}-01", art),
                         {"bewerbungen": 0, "gespraeche": 0})
        monat += 1
        if monat > 12:
            jahr, monat = jahr + 1, 1
    for a in apps:
        eintrag = werte.get(_abschnitt(_bz.tag(a), art))
        if eintrag is not None:
            eintrag["bewerbungen"] += 1
            eintrag["gespraeche"] += 1 if a.get("has_reached_interview") == 1 else 0
    return {"art": art, "abschnitte": [
        {"schluessel": k, "text": _abschnitt_text(k, art), **v} for k, v in werte.items()]}


def wege(apps: list) -> dict:
    """Wege als Gruppen; die Datenluecke steht als eigene Zeile am Ende."""
    gruppen: dict = {}
    for a in apps:
        k = _se._kanal(a)
        k = k if k in WEG_GRUPPEN else "unklassifiziert"
        e = gruppen.setdefault(k, {"bewerbungen": 0, "gespraeche": 0})
        e["bewerbungen"] += 1
        e["gespraeche"] += 1 if a.get("has_reached_interview") == 1 else 0

    def zeile(k: str, name: str, luecke: bool = False) -> dict:
        e = gruppen[k]
        return {"weg": name, "bewerbungen": e["bewerbungen"], "luecke": luecke,
                "gespraeche": anteil(e["gespraeche"], e["bewerbungen"])}

    zeilen = [zeile(k, n) for k, n in WEG_GRUPPEN.items() if k in gruppen]
    zeilen.sort(key=lambda z: -z["bewerbungen"])
    if "unklassifiziert" in gruppen:
        zeilen.append(zeile("unklassifiziert", WEG_LUECKE, luecke=True))
    return {**begrenzt(zeilen), "luecke_satz":
            WEG_LUECKE_SATZ if "unklassifiziert" in gruppen else ""}


def quellen(apps: list) -> dict:
    """Die einzelnen Quellen (Folgeseite der Auswertung)."""
    werte: dict = {}
    for a in apps:
        roh = (a.get("source") or a.get("portal_name") or "").strip()
        name = quelle_text(roh) if roh else WEG_LUECKE
        e = werte.setdefault(name, {"quelle": name, "bewerbungen": 0, "gespraeche": 0})
        e["bewerbungen"] += 1
        e["gespraeche"] += 1 if a.get("has_reached_interview") == 1 else 0
    zeilen = sorted(werte.values(), key=lambda e: (e["quelle"] == WEG_LUECKE,
                                                   -e["bewerbungen"], e["quelle"]))
    return begrenzt(zeilen)


def ausgang(apps: list) -> dict:
    """Wie die abgeschlossenen Verfahren endeten."""
    werte: dict = {}
    for a in apps:
        s = a.get("status") or ""
        if not laeuft(s):
            werte[s] = werte.get(s, 0) + 1
    basis = sum(werte.values())
    zeilen = [{"status": s, "text": status_text(s), "anteil": anteil(n, basis)}
              for s, n in sorted(werte.items(), key=lambda kv: (-kv[1], kv[0]))]
    return {"abgeschlossen": anzahl(basis), **begrenzt(zeilen)}


def ansteht(db, heute: str) -> dict:
    """Offene Nachfass-Erinnerungen, die aelteste zuerst (Stand am Stichtag)."""
    offen = sorted(db.get_pending_follow_ups() or [],
                   key=lambda f: f.get("scheduled_date") or "")
    zeilen = [{
        "datum": datum_text(f.get("scheduled_date")),
        "ueberfaellig": bool(f.get("scheduled_date")) and f["scheduled_date"][:10] < heute,
        "was": followup_text(f.get("follow_up_type")),
        "firma": f.get("company") or f.get("application_company") or "",
        "stelle": f.get("title") or f.get("position") or f.get("application_title") or "",
    } for f in offen]
    faellig = sum(1 for z in zeilen if z["ueberfaellig"])
    return {"offen": anzahl(len(zeilen), AM_STICHTAG),
            "faellig": anzahl(faellig, AM_STICHTAG), **begrenzt(zeilen)}


def _monate_zurueck(tag: date, n: int) -> date:
    gesamt = tag.year * 12 + tag.month - 1 - n
    jahr, monat = gesamt // 12, gesamt % 12 + 1
    letzter = (date(jahr + monat // 12, monat % 12 + 1, 1).toordinal() - 1)
    return date(jahr, monat, min(tag.day, date.fromordinal(letzter).day))


def vergleich(apps: list, stichtag: str) -> dict:
    """Die letzten 3 Monate gegen die 3 davor: zwei Zahlen, keine Wertung."""
    ende = date.fromisoformat(stichtag)
    mitte = _monate_zurueck(ende, 3)
    anfang = _monate_zurueck(ende, 6)
    jetzt = sum(1 for a in apps if mitte.isoformat() < _bz.tag(a) <= stichtag)
    davor = sum(1 for a in apps if anfang.isoformat() < _bz.tag(a) <= mitte.isoformat())
    return {"letzte_3_monate": anzahl(jetzt), "3_monate_davor": anzahl(davor)}


def bericht_daten(db, von: str = "", bis: str = "", heute: Optional[str] = None) -> dict:
    """Alle Zahlen fuer Nachweis, Auswertung und Statistik-Seite."""
    von, bis = (von or "")[:10], (bis or "")[:10]
    heute = (heute or date.today().isoformat())[:10]
    stichtag = min(bis, heute) if bis else heute

    alle = [a for a in db.get_applications() if (a.get("status") or "") != "in_vorbereitung"]
    apps = [a for a in alle if _bz.im_zeitraum(a, von, bis)]
    ohne_datum = sum(1 for a in alle if not _bz.tag(a))
    q = _bz.quoten_fuer(db, apps)
    basis = q.get("basis", 0)

    start = db.get_pbp_first_active_at() or ""
    if start:
        seit_pbp = [a for a in apps if _bz.tag(a) >= start[:10]]
    else:
        seit_pbp = list(apps)
    nachgetragen = len(apps) - len(seit_pbp)
    z = _se.zeitliche_kennzahlen(db, apps=seit_pbp)

    laufend = [a for a in alle if laeuft(a.get("status"))
               and (not bis or (_bz.tag(a) and _bz.tag(a) <= bis))]
    laufend_frueher = [a for a in laufend if von and _bz.tag(a) and _bz.tag(a) < von]

    absagen = [a for a in apps if a.get("status") == "abgelehnt"]
    nach_gespraech = sum(1 for a in absagen if a.get("has_reached_interview") == 1)

    kosten = _bz.kosten_im_zeitraum(db, von, bis)
    faellig = ansteht(db, heute)

    return {
        "zeitraum": {
            "von": von, "bis": bis, "aktiv": bool(von or bis), "stichtag": stichtag,
            "text": (f"{datum_text(von) or 'Beginn'} bis {datum_text(bis) or datum_text(heute)}"
                     if von or bis else "gesamter Verlauf"),
            "bewerbungen_ohne_datum": ohne_datum,
        },
        "kennzahlen": {
            "bewerbungen": anzahl(basis),
            "laufen": anzahl(len(laufend), AM_STICHTAG),
            "laufen_aus_frueher": anzahl(len(laufend_frueher), AM_STICHTAG),
            "mit_gespraech": anteil(q.get("interview", 0), basis),
            "angebote": anteil(q.get("angebot", 0), basis),
            "absagen": anteil(q.get("abgelehnt", 0), basis),
            "versandet": anteil(q.get("abgelaufen", 0), basis),
            "zurueckgezogen": anteil(q.get("zurueckgezogen", 0), basis),
            "nachfassen_faellig": faellig["faellig"],
        },
        "trichter": {
            "stufen": [
                {"stufe": "Beworben", "wert": anzahl(basis)},
                {"stufe": "Gespräch", "wert": anteil(q.get("interview", 0), basis)},
                {"stufe": "Angebot", "wert": anteil(q.get("angebot", 0), basis)},
            ],
            "entfallen": [{"stufe": s, "grund": g} for s, g in STUFEN_OHNE_ZAHL.items()],
        },
        "dauer": {
            "bis_antwort": dauer(z.get("zeit_bis_erste_reaktion")),
            "bis_gespraech": dauer(z.get("zeit_bis_interview")),
            "bis_absage_ohne_gespraech": dauer((z.get("zeit_bis_absage") or {}).get("vor_interview")),
            "bis_absage_nach_gespraech": dauer((z.get("zeit_bis_absage") or {}).get("nach_interview")),
            "nachgetragen": anzahl(nachgetragen),
            "nachgetragen_satz": (
                f"{nachgetragen} nachgetragene Bewerbungen aus der Zeit vor PBP zählen "
                "bei den Anzahlen mit, bei Dauer und Antwortzeit nicht."
                if nachgetragen > 1 else
                "1 nachgetragene Bewerbung aus der Zeit vor PBP zählt bei den Anzahlen "
                "mit, bei Dauer und Antwortzeit nicht." if nachgetragen else ""),
        },
        "absagen": {
            "gesamt": anzahl(len(absagen)),
            "nach_gespraech": anteil(nach_gespraech, len(absagen)),
        },
        "zeitachse": zeitachse(apps, von, bis),
        "wege": wege(apps),
        "quellen": quellen(apps),
        "ausgang": ausgang(apps),
        "ansteht": faellig,
        "vergleich": vergleich(alle, stichtag),
        "kosten": {
            "summe_eur": kosten["summe_eur"], "posten": kosten["posten"],
            "ohne_datum": kosten["ohne_datum"],
        },
    }
