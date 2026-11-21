"""Zeitraum und Kennzahlen des Bewerbungsberichts (#1337, #1420).

Zwei Aufgaben, je EINE Funktion:

1. `quoten(apps)` rechnet Interview-, Angebots-, Ablehnungs-, Ablauf- und
   Rueckzugsquote. `get_statistics` (Werkzeug, Dashboard), das PDF und das
   Excel-Blatt lesen sie von hier. Davor stand die Angebotsrate dreimal im
   Code (4,0 % gegen 8,0 % im selben Werkzeug, 0,0 % im PDF) und die
   Ablehnungsquote ebenso.
2. `fuer_zeitraum(db, report_data, von, bis)` bringt die Berichtsdaten
   EINMAL auf den Zeitraum. PDF und Excel bekommen danach nur noch Zahlen,
   die zum Zeitraum passen; was sich nicht auf einen Zeitraum rechnen
   laesst (Stellenbestand, Punkte-Verteilung, Quellen-Volumen), steht im
   Zeitraum-Bericht nicht als Zahl, sondern als Hinweis.

Abgrenzung: `services/statistik_erweitert.py` rechnet Dauer, Kanaele und
Ablehnungs-Kategorien; es bekommt von hier die Bewerbungen des Zeitraums.
"""
from __future__ import annotations

from typing import Iterable, Optional

#: Status, die als Angebot zaehlen.
ANGEBOT_STATUS = ("angebot", "angenommen")


def tag(a: dict) -> str:
    """Datum der Bewerbung als JJJJ-MM-TT ('' wenn keines gesetzt)."""
    return (a.get("applied_at") or "")[:10]


def im_zeitraum(a: dict, von: str = "", bis: str = "") -> bool:
    """Liegt die Bewerbung im Zeitraum (beide Grenzen einschliesslich)?

    Ohne Bewerbungsdatum liegt sie in keinem Zeitraum: ein Vorgang ohne
    Datum laesst sich keinem Monat zuordnen (#779).
    """
    t = tag(a)
    if not (von or bis):
        return True
    if not t:
        return False
    return (not von or t >= von[:10]) and (not bis or t <= bis[:10])


def _anteil(n: int, basis: int) -> Optional[float]:
    return round(n / basis * 100, 1) if basis else None


def quoten(apps: Iterable[dict], angebots_ids: frozenset = frozenset()) -> dict:
    """Die Quoten einer Menge von Bewerbungen, aus EINER Funktion.

    Basis ist die Zahl der abgeschickten Bewerbungen (ohne `in_vorbereitung`).
    Ein Vorgang, den der Arbeitgeber nach einem Angebot abbrach
    (`arbeitgeber_ausgefallen` mit frueherem Angebot, `angebots_ids`), zaehlt
    weiter als Angebot (#779/D27). Ohne Basis steht dort `{"basis": 0}`,
    nie eine 0,0.

    `ablehnung_*` meint die mitgeteilte Absage (`abgelehnt`). Ein versandeter
    Vorgang (`abgelaufen`) ist keine Absage (#943) und hat eine eigene Quote.
    """
    apps = [a for a in apps if (a.get("status") or "") != "in_vorbereitung"]
    basis = len(apps)
    if not basis:
        return {"basis": 0}

    def zaehle(pred) -> int:
        return sum(1 for a in apps if pred(a))

    abgelaufen = zaehle(lambda a: a["status"] == "abgelaufen")
    abgelehnt = zaehle(lambda a: a["status"] == "abgelehnt")
    # #779: arbeitgeber_ausgefallen ist KEIN Rueckzug des Bewerbers.
    zurueck = zaehle(lambda a: a["status"] == "zurueckgezogen")
    ausgefallen = zaehle(lambda a: a["status"] == "arbeitgeber_ausgefallen")
    gespraech = zaehle(lambda a: a.get("has_reached_interview") == 1)
    angebot = zaehle(
        lambda a: a["status"] in ANGEBOT_STATUS
        or (a["status"] == "arbeitgeber_ausgefallen"
            and a.get("id") in angebots_ids))
    q = {
        "basis": basis,
        "abgelaufen": abgelaufen, "expired_rate": _anteil(abgelaufen, basis),
        "abgelehnt": abgelehnt, "rejection_rate": _anteil(abgelehnt, basis),
        "zurueckgezogen": zurueck, "withdrawal_rate": _anteil(zurueck, basis),
        "interview": gespraech, "interview_rate": _anteil(gespraech, basis),
        "angebot": angebot, "offer_rate": _anteil(angebot, basis),
    }
    if ausgefallen:
        q["arbeitgeber_ausgefallen"] = ausgefallen
        q["employer_loss_rate"] = _anteil(ausgefallen, basis)
    return q


def angebots_ids(db) -> frozenset:
    """Bewerbungen, die je den Status Angebot erreicht haben (aus dem Verlauf)."""
    rows = db.connect().execute(
        "SELECT DISTINCT application_id FROM application_events "
        "WHERE status IN ('angebot', 'angenommen')").fetchall()
    return frozenset(r["application_id"] for r in rows)


def quoten_fuer(db, apps: Iterable[dict]) -> dict:
    """`quoten` mit den Angeboten aus dem Verlauf der Datenbank."""
    return quoten(apps, angebots_ids(db))


def _statistik_fuer(db, apps: list, stats: dict) -> dict:
    """Die Statistik-Kennzahlen, die sich auf Bewerbungen beziehen, fuer `apps`.

    Zahlen zum Stellenbestand (aktive, aussortierte, Punkte, Quellen) fehlen
    mit Absicht: sie haengen nicht am Zeitraum (siehe `fuer_zeitraum`).
    """
    nach_status: dict = {}
    for a in apps:
        s = a.get("status") or "offen"
        nach_status[s] = nach_status.get(s, 0) + 1
    q = quoten_fuer(db, apps)
    erg = {
        "total_applications": len(apps),
        "applications_by_status": nach_status,
        "quoten": {"gesamt": q},
    }
    if q.get("basis"):
        erg["interview_rate"] = q["interview_rate"]
        erg["offer_rate"] = q["offer_rate"]
        erg["rejection_rate"] = q["rejection_rate"]
    return erg


def kosten_im_zeitraum(db, von: str = "", bis: str = "") -> dict:
    """Kostenposten und Reisekosten im Zeitraum.

    Posten ohne Datum lassen sich keinem Zeitraum zuordnen; sie werden
    gezaehlt (`ohne_datum`), damit der Bericht es sagen kann, und stehen
    nicht in der Summe des Zeitraums.
    """
    posten = db.list_application_costs()
    mit_datum, ohne_datum = [], 0
    for p in posten:
        d = (p.get("incurred_at") or "")[:10]
        if not d:
            ohne_datum += 1
            if not (von or bis):
                mit_datum.append(p)
            continue
        if (not von or d >= von[:10]) and (not bis or d <= bis[:10]):
            mit_datum.append(p)
    mit_datum.sort(key=lambda p: ((p.get("incurred_at") or "")[:10],
                                  p.get("created_at") or ""))
    summe = round(sum(float(p.get("amount") or 0) for p in mit_datum), 2)
    return {"posten": mit_datum, "summe_eur": summe, "ohne_datum": ohne_datum}


def fuer_zeitraum(db, report_data: dict, von: str = "", bis: str = "") -> dict:
    """Die Berichtsdaten fuer einen Zeitraum; ohne Zeitraum unveraendert.

    Rechnet jede Kennzahl aus den Bewerbungen im Zeitraum neu. Setzt
    `report_data["zeitraum"]` (von, bis, aktiv) und entfernt die Zahlen, die
    sich nicht auf einen Zeitraum rechnen lassen.
    """
    if not (von or bis):
        report_data["zeitraum"] = {"von": "", "bis": "", "aktiv": False}
        return report_data
    from . import statistik_erweitert as _se

    alle = report_data.get("applications", [])
    apps = [a for a in alle if im_zeitraum(a, von, bis)]
    ids = {a.get("id") for a in apps}
    erg = dict(report_data)
    erg["applications"] = apps
    erg["zeitraum"] = {"von": von, "bis": bis, "aktiv": True,
                       "bewerbungen_gesamt": len(alle)}
    erg["statistics"] = _statistik_fuer(db, apps, report_data.get("statistics") or {})
    erg["bewerbungsart"] = {}
    for a in apps:
        art = (a.get("bewerbungsart") or "unbekannt").strip() or "unbekannt"
        erg["bewerbungsart"][art] = erg["bewerbungsart"].get(art, 0) + 1
    erg["documents_per_application"] = {
        k: v for k, v in (report_data.get("documents_per_application") or {}).items()
        if k in ids}
    erg["rejection_patterns"] = db.get_rejection_patterns(app_ids=ids)
    try:
        erg["prozess_kennzahlen"] = _se.zeitliche_kennzahlen(db, apps=apps)
        erg["kanal_auswertung"] = _se.kanal_auswertung(db, apps=apps)
        erg["ablehnungs_kategorien"] = _se.ablehnungs_kategorien(db, apps=apps)
    except Exception:  # eine fehlende Erweiterung verhindert den Bericht nie
        for k in ("prozess_kennzahlen", "kanal_auswertung",
                  "ablehnungs_kategorien"):
            erg.pop(k, None)
    erg["kosten"] = kosten_im_zeitraum(db, von, bis)
    erg["aufwand"] = db.get_aufwand_summary(von=von, bis=bis)
    # Nicht auf einen Zeitraum rechenbar: Stellenbestand und alles, was an
    # Stellen statt an Bewerbungen haengt. Der Bericht nennt es als Hinweis.
    erg["score_distribution"] = {}
    erg["score_distribution_ordered"] = []
    erg["unapplied_high_score"] = []
    erg["stellen_aussortiert"] = {}
    erg["source_volume"] = []
    erg["scraper_health"] = []
    erg["interviews_historisch_total"] = None
    return erg
