"""Die Inhalte der Auswertung fuer den Bewerber (#798, Stufe 3).

PDF und Statistik-Seite lesen dieselbe Funktion, damit dieselbe Zahl dasteht.
Die Kennzahlen kommen aus `bericht_daten`, die Listen aus `nachweis_daten`;
hier stehen nur die Teile, die allein die Auswertung braucht: Kacheln, Saetze,
Arten der Absage und die Stellensuche.

Saetze stehen nur, wenn die Zahlen sie tragen (feste Regeln, kein freier Text).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from . import bericht_daten as _kern
from . import bericht_zeitraum as _bz
from . import statistik_erweitert as _se
from .ablehnungsgruende import gruende_zaehlen
from .anzeigenamen import grund_text
from .nachweis_daten import nachweis_daten

#: Ab so vielen Absagen traegt ein Satz ueber ihre Verteilung.
MIN_ABSAGEN_FUER_SATZ = 3

ABSAGE_ART = {
    "nach_interview": "Absage nach einem Gespräch",
    "stille_absage": "Keine Rückmeldung",
    "automatische_ablehnung": "Schnelle Absage (unter 3 Tagen)",
    "vermittler_reject": "Absage über Personalvermittler",
    "extern_bedingt": "Stelle entfallen oder Verfahren beendet",
    "ohne_grund": "Absage ohne genannten Grund",
    "sonstige_absage": "Sonstige Absage",
}

SUCHE_NUR_GESAMT = "Die Stellensuche steht nur in der Auswertung für den gesamten Verlauf."


def satz_absagen(gesamt: int, nach_gespraech: int) -> str:
    """Ein Satz nur, wenn genug Absagen da sind und die Mehrheit eindeutig ist."""
    if gesamt < MIN_ABSAGEN_FUER_SATZ or nach_gespraech * 2 <= gesamt:
        return ""
    return f"{nach_gespraech} der {gesamt} Absagen kamen nach einem Gespräch."


def _kacheln(kern: dict) -> list:
    k = kern["kennzahlen"]
    abgeschlossen = kern["ausgang"]["abgeschlossen"]["wert"]
    antwort = kern["dauer"]["bis_antwort"]
    hat_median = antwort["zustand"] == "wert"
    median = (f"{str(antwort['wert']).replace('.', ',').removesuffix(',0')} Tage"
              if hat_median else "–")
    return [
        {"name": "Bewerbungen", "wert": k["bewerbungen"]["text"], "hinweis": k["bewerbungen"]["bezug"] if kern["zeitraum"]["aktiv"] else "insgesamt"},
        {"name": "laufen noch", "wert": k["laufen"]["text"],
         "hinweis": f"{abgeschlossen} abgeschlossen"},
        {"name": "mit Gespräch", "wert": str(k["mit_gespraech"]["anzahl"]),
         "hinweis": f"von {k['bewerbungen']['wert']}"},
        {"name": "Angebote", "wert": str(k["angebote"]["anzahl"]),
         "hinweis": f"von {k['bewerbungen']['wert']}"},
        {"name": "bis zur Antwort", "wert": median,
         "hinweis": f"Median aus {antwort['anzahl']} Fällen" if hat_median else _kern.UNBEKANNT},
        {"name": "Nachfassen", "wert": k["nachfassen_faellig"]["text"], "hinweis": "jetzt fällig"},
    ]


def _absage_arten(db, von: str, bis: str) -> dict:
    apps = [a for a in db.get_applications() if _bz.im_zeitraum(a, von, bis)]
    kat = (_se.ablehnungs_kategorien(db, apps=apps) or {}).get("kategorien", {})
    basis = sum(v["anzahl"] for v in kat.values())
    zeilen = [{"art": ABSAGE_ART.get(k, "Sonstige Absage"), "anzahl": v["anzahl"],
               "anteil": _kern.anteil(v["anzahl"], basis)} for k, v in kat.items()]
    return {"basis": basis, **_kern.begrenzt(zeilen)}


def meine_suche(db, von: str = "", bis: str = "") -> dict:
    """Die Stellensuche. Sie haengt nicht am Zeitraum und entfaellt dort."""
    if von or bis:
        return {"verfuegbar": False, "hinweis": SUCHE_NUR_GESAMT}
    conn = db.connect()
    pid = db.get_active_profile_id()
    gesichtet = conn.execute("SELECT COUNT(*) FROM jobs WHERE (profile_id=? OR profile_id IS NULL)",
                             (pid,)).fetchone()[0]
    aktiv = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1 AND "
                         "(profile_id=? OR profile_id IS NULL)", (pid,)).fetchone()[0]
    gruende, aussortiert = gruende_zaehlen(conn, pid, ausser=("bewerbung_erstellt", "war_nur_anfrage"))
    zeilen = [{"grund": grund_text(g), "anzahl": n} for g, n in gruende]
    return {"verfuegbar": True, "gesichtet": gesichtet, "in_der_liste": aktiv,
            "aussortiert": aussortiert, "gruende": _kern.begrenzt(zeilen)}


def auswertung_daten(db, von: str = "", bis: str = "", heute: Optional[str] = None) -> dict:
    """Alle Inhalte der Auswertung und der Statistik-Seite."""
    von, bis = (von or "")[:10], (bis or "")[:10]
    heute = (heute or date.today().isoformat())[:10]
    kern = _kern.bericht_daten(db, von, bis, heute=heute)
    listen = nachweis_daten(db, von, bis, heute=heute)
    return {
        **kern,
        "erstellt_text": listen["erstellt_text"],
        "kacheln": _kacheln(kern),
        "satz_absagen": satz_absagen(kern["absagen"]["gesamt"]["wert"],
                                     kern["absagen"]["nach_gespraech"]["anzahl"]),
        "absage_arten": _absage_arten(db, von, bis),
        "meine_suche": meine_suche(db, von, bis),
        "bewerbungen": listen["bewerbungen"],
        "chronik": listen["chronik"],
    }
