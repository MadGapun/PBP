"""Dubletten-Erkennung fuer Termine (#804/D30, v1.7.11).

Termine entstanden urspruenglich nur von Hand — inzwischen kommen sie aus
Mail-Import, ICS, Claude und der Oberflaeche gleichzeitig. Ohne Pruefung
liegt derselbe Termin doppelt im Kalender, und jede Auswertung, die
Termine zaehlt (Aufwand, Interview-Runden, Statistik), zaehlt ihn zweimal.

Belegter Fall: zwei Eintraege fuer denselben Slot, die sich sogar
ergaenzten — einer trug den Teams-Link, der andere den Gespraechskontext.
Keiner allein war vollstaendig. Genau dafuer gibt es hier das
Zusammenfuehren: leere Felder werden gefuellt, gefuellte NIE ueberschrieben.

Bewusst kein stilles Verwerfen: Doppeltermine am selben Tag zu
verschiedenen Uhrzeiten sind legitim (Erst- und Zweitgespraech), deshalb
ein enges Zeitfenster und die Moeglichkeit, bewusst zu uebersteuern.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

# Toleranz um den Startzeitpunkt. Eng genug, dass zwei echte Termine am
# selben Tag nicht kollidieren; weit genug fuer Rundungen und
# Zeitangaben aus verschiedenen Quellen ("16:00" vs "16:00:00").
TOLERANZ_MINUTEN = 30

# Ein abgesagter Termin blockiert keinen neuen — dann wird ja gerade
# umgeplant.
IGNORIERTE_STATUS = {"abgesagt"}


def _parse(wert: str) -> Optional[datetime]:
    if not wert:
        return None
    s = str(wert).strip().replace(" ", "T")
    for laenge in (19, 16, 13, 10):
        try:
            return datetime.fromisoformat(s[:laenge])
        except (ValueError, TypeError):
            continue
    return None


def finde_dublette(db: Any, bewerbung_id: str, datum: str,
                   ausser_id: str = "") -> Optional[dict]:
    """Bestehender, nicht abgesagter Termin derselben Bewerbung im Fenster."""
    neu = _parse(datum)
    if not neu:
        return None
    try:
        kandidaten = db.get_meetings_for_application(bewerbung_id)
    except Exception:
        return None
    fenster = timedelta(minutes=TOLERANZ_MINUTEN)
    for m in kandidaten or []:
        if ausser_id and str(m.get("id")) == str(ausser_id):
            continue
        if (m.get("status") or "").lower() in IGNORIERTE_STATUS:
            continue
        alt = _parse(m.get("meeting_date") or "")
        if alt and abs(alt - neu) <= fenster:
            return dict(m)
    return None


# Felder, die beim Zusammenfuehren uebernommen werden duerfen — und nur,
# wenn sie beim bestehenden Termin leer sind.
_MERGE_FELDER = ("title", "meeting_type", "platform", "location", "notes",
                 "duration_minutes", "meeting_url", "status")


def _ist_leer(wert: Any) -> bool:
    if wert is None:
        return True
    if isinstance(wert, str):
        return not wert.strip()
    if isinstance(wert, (int, float)):
        return wert == 0
    return False


def zusammenfuehren(db: Any, bestehend: dict, neu: dict) -> dict:
    """Fuellt LEERE Felder des bestehenden Termins. Gefuellte bleiben.

    Rueckgabe: {"ergaenzt": [...], "behalten": [...]}. Das Datum wird nie
    ueberschrieben — der bestehende Termin behaelt seinen Zeitpunkt, sonst
    waere es kein Zusammenfuehren, sondern ein Verschieben.
    """
    updates: dict = {}
    ergaenzt: list = []
    behalten: list = []
    for feld in _MERGE_FELDER:
        neuer_wert = neu.get(feld)
        if _ist_leer(neuer_wert):
            continue
        if _ist_leer(bestehend.get(feld)):
            updates[feld] = neuer_wert
            ergaenzt.append(feld)
        elif str(bestehend.get(feld)) != str(neuer_wert):
            behalten.append(feld)
    if updates:
        try:
            db.update_meeting(bestehend.get("id"), updates)
        except Exception as e:  # nicht schweigen, aber auch nicht kippen
            return {"ergaenzt": [], "behalten": behalten,
                    "fehler": f"Update fehlgeschlagen: {e}"}
    return {"ergaenzt": ergaenzt, "behalten": behalten}


def finde_alle_dubletten(db: Any) -> list:
    """Bestands-Report: alle Termin-Paare im selben Zeitfenster.

    Fuer das Aufraeumen bereits entstandener Dubletten — sonst muesste man
    sie im Kalender von Hand suchen.
    """
    conn = db.connect()
    pid = db.get_active_profile_id()
    rows = conn.execute(
        "SELECT m.*, a.company AS firma, a.title AS bewerbung_titel "
        "FROM application_meetings m "
        "LEFT JOIN applications a ON a.id = m.application_id "
        "WHERE (a.profile_id=? OR a.profile_id IS NULL) "
        "ORDER BY m.application_id, m.meeting_date", (pid,)
    ).fetchall()
    fenster = timedelta(minutes=TOLERANZ_MINUTEN)
    paare = []
    nach_app: dict = {}
    for r in rows:
        nach_app.setdefault(r["application_id"], []).append(dict(r))
    for app_id, termine in nach_app.items():
        for i, a in enumerate(termine):
            if (a.get("status") or "").lower() in IGNORIERTE_STATUS:
                continue
            da = _parse(a.get("meeting_date") or "")
            if not da:
                continue
            for b in termine[i + 1:]:
                if (b.get("status") or "").lower() in IGNORIERTE_STATUS:
                    continue
                dbt = _parse(b.get("meeting_date") or "")
                if dbt and abs(dbt - da) <= fenster:
                    # Welcher traegt mehr Information?
                    def _fuelle(m):
                        return sum(1 for f in _MERGE_FELDER
                                   if not _ist_leer(m.get(f)))
                    master, dublette = ((a, b) if _fuelle(a) >= _fuelle(b)
                                        else (b, a))
                    paare.append({
                        "bewerbung_id": app_id,
                        "firma": a.get("firma", ""),
                        "zeitpunkt": a.get("meeting_date"),
                        "master_id": master.get("id"),
                        "master_titel": master.get("title"),
                        "duplikat_id": dublette.get("id"),
                        "duplikat_titel": dublette.get("title"),
                        "ergaenzen_sich": bool(
                            [f for f in _MERGE_FELDER
                             if _ist_leer(master.get(f))
                             and not _ist_leer(dublette.get(f))]),
                    })
    return paare
