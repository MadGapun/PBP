"""Erweiterte Bewerbungs-Kennzahlen (#781, D29, v1.7.10).

Drei Auswertungen, die bisher in der DB schlummerten:

1. **Zeitliche Kennzahlen** aus `application_events` — Prozessdauer nach
   Ausgang, Reaktionszeiten, Zeit bis Interview/Absage. Median UND
   Mittelwert (Ausreisser verzerren den Mittelwert massiv: Absage nach
   48h vs. Prozess ueber vier Monate).

2. **Kanal-Auswertung** — nicht "wo wurde gefunden", sondern "welcher
   Kanal fuehrt zum Interview".

3. **Ablehnungs-Kategorien** — 63 Freitext-Gruende sind nicht auswertbar.
   Die Heuristik trennt u.a. extern bedingte Faelle (Stelle gestrichen,
   Insolvenz, intern besetzt) heraus, die KEINE Ablehnung des Bewerbers
   sind. Der Freitext bleibt immer erhalten.

Bericht-Designprinzip (v1.6.8) gilt: unklare Faelle werden als solche
ausgewiesen ('unklassifiziert', 'ohne_grund'), nicht in die naechstbeste
Kategorie gedrueckt. Vor-PBP-Zahlen sind eine UNTERGRENZE — rekonstruierte
Altbewerbungen haben typischerweise nur zwei Events.
"""
from __future__ import annotations

import re
import statistics
from datetime import datetime
from typing import Any, Optional

INTERVIEW_STATUS = ("interview", "zweitgespraech", "interview_abgeschlossen")
TERMINAL_STATUS = ("abgelehnt", "angenommen", "abgelaufen",
                   "zurueckgezogen", "arbeitgeber_ausgefallen")

_EXTERN_MUSTER = re.compile(
    r"intern besetzt|intern vergeben|gestrichen|budget|insolven|"
    r"reorganis|einstellungsstopp|besetzungsstopp|projekt (wurde )?"
    r"(gestoppt|eingestellt|abgesagt)|stelle (entfallen|zurueckgezogen|"
    r"zurückgezogen)|hiring freeze|vermittler (hat )?(die firma )?verlassen",
    re.IGNORECASE,
)

_GESPRAECH_MUSTER = re.compile(
    r"gespr(ae|ä)ch|interview|telefonat|kennenlernen|videocall|"
    r"teams-?termin|vorstellungsrunde", re.IGNORECASE)
_DATUM_MUSTER = re.compile(r"\d{1,2}\.\s?\d{1,2}\.(\d{2,4})?|\d{4}-\d{2}-\d{2}")


def _dt(wert: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat((wert or "")[:19])
    except (ValueError, TypeError):
        return None


def _tage(von: str, bis: str) -> Optional[float]:
    d1, d2 = _dt(von), _dt(bis)
    if not d1 or not d2:
        return None
    delta = (d2 - d1).total_seconds() / 86400
    return round(delta, 1) if delta >= 0 else None


def _median_mittel(werte: list) -> dict:
    werte = [w for w in werte if w is not None]
    if not werte:
        return {"anzahl": 0}
    return {
        "anzahl": len(werte),
        "median_tage": round(statistics.median(werte), 1),
        "mittel_tage": round(sum(werte) / len(werte), 1),
        "min_tage": round(min(werte), 1),
        "max_tage": round(max(werte), 1),
    }


def _lade_events(db: Any) -> dict:
    conn = db.connect()
    rows = conn.execute(
        "SELECT application_id, status, event_date FROM application_events "
        "ORDER BY event_date"
    ).fetchall()
    per_app: dict = {}
    for r in rows:
        per_app.setdefault(r["application_id"], []).append(
            {"status": r["status"] or "", "datum": r["event_date"] or ""})
    return per_app


def zeitliche_kennzahlen(db: Any) -> dict:
    apps = db.get_applications()
    events = _lade_events(db)

    dauer_nach_ausgang: dict = {s: [] for s in TERMINAL_STATUS}
    reaktion: list = []
    bis_interview: list = []
    absage_vor_iv: list = []
    absage_nach_iv: list = []
    laufende: list = []
    pro_monat: dict = {}
    interviews_pro_monat: dict = {}
    wenig_events = 0

    for a in apps:
        evs = events.get(a["id"], [])
        if len(evs) <= 2:
            wenig_events += 1
        status = a.get("status") or ""

        applied = (a.get("applied_at") or "")[:7]
        if applied and status != "in_vorbereitung":
            pro_monat[applied] = pro_monat.get(applied, 0) + 1

        beworben_ev = next((e for e in evs if e["status"] == "beworben"), None)
        start = beworben_ev["datum"] if beworben_ev else (
            evs[0]["datum"] if evs else a.get("applied_at") or "")

        iv_ev = next((e for e in evs if e["status"] in INTERVIEW_STATUS), None)
        if iv_ev:
            monat = iv_ev["datum"][:7]
            if monat:
                interviews_pro_monat[monat] = (
                    interviews_pro_monat.get(monat, 0) + 1)
            if start:
                bis_interview.append(_tage(start, iv_ev["datum"]))

        if beworben_ev:
            naechster = next(
                (e for e in evs
                 if e["datum"] > beworben_ev["datum"]
                 and e["status"] not in ("beworben", "notiz")), None)
            if naechster:
                reaktion.append(_tage(beworben_ev["datum"], naechster["datum"]))

        if status in TERMINAL_STATUS:
            end_ev = next((e for e in reversed(evs)
                           if e["status"] == status), None)
            ende = end_ev["datum"] if end_ev else (a.get("updated_at") or "")
            erster = evs[0]["datum"] if evs else (a.get("applied_at") or "")
            d = _tage(erster, ende)
            if d is not None:
                dauer_nach_ausgang[status].append(d)
            if status == "abgelehnt" and start and ende:
                d2 = _tage(start, ende)
                if d2 is not None:
                    if a.get("has_reached_interview") == 1:
                        absage_nach_iv.append(d2)
                    else:
                        absage_vor_iv.append(d2)
        elif status not in ("in_vorbereitung",):
            letzter = evs[-1]["datum"] if evs else (
                a.get("applied_at") or a.get("created_at") or "")
            stillstand = _tage(letzter, datetime.now().isoformat())
            if stillstand is not None:
                laufende.append({
                    "id": a["id"][:8], "firma": a.get("company", ""),
                    "titel": a.get("title", ""), "status": status,
                    "tage_ohne_bewegung": int(stillstand),
                })

    laufende.sort(key=lambda x: -x["tage_ohne_bewegung"])
    return {
        "prozessdauer_nach_ausgang": {
            s: _median_mittel(v) for s, v in dauer_nach_ausgang.items()
            if v
        },
        "zeit_bis_erste_reaktion": _median_mittel(reaktion),
        "zeit_bis_interview": _median_mittel(bis_interview),
        "zeit_bis_absage": {
            "vor_interview": _median_mittel(absage_vor_iv),
            "nach_interview": _median_mittel(absage_nach_iv),
        },
        "laengste_laufende_prozesse": laufende[:8],
        "bewerbungen_pro_monat": dict(sorted(pro_monat.items())),
        "interviews_pro_monat": dict(sorted(interviews_pro_monat.items())),
        "datenqualitaet": {
            "bewerbungen_mit_max_2_events": wenig_events,
            "hinweis": (
                "Rekonstruierte Altbewerbungen haben typischerweise nur "
                "1-2 Events — Zeitkennzahlen und Interview-Zahlen aus der "
                "Zeit vor der PBP-Nutzung sind eine UNTERGRENZE, keine "
                "Wahrheit."
            ) if wenig_events else "",
        },
    }


def _kanal(a: dict) -> str:
    source = (a.get("source") or "").strip().lower()
    if a.get("vermittler") or a.get("endkunde"):
        return "vermittler_recruiter"
    if source in ("netzwerk", "kontakt", "empfehlung", "persoenlich"):
        return "netzwerk"
    if (a.get("portal_name") or "").strip() or \
            (a.get("bewerbungsart") or "") == "ueber_portal":
        return "portal"
    if source and source not in ("manuell", "direkt", "firmenwebsite",
                                 "initiativ", "email"):
        # Scraper-Quelle (stepstone, bundesagentur, ...) = Portal-Fund
        return "portal"
    if source in ("firmenwebsite", "direkt", "initiativ"):
        return "direktbewerbung"
    return "unklassifiziert"


def kanal_auswertung(db: Any) -> dict:
    apps = [a for a in db.get_applications()
            if (a.get("status") or "") != "in_vorbereitung"]
    kanaele: dict = {}
    for a in apps:
        k = _kanal(a)
        eintrag = kanaele.setdefault(k, {
            "bewerbungen": 0, "interviews": 0, "angebote": 0})
        eintrag["bewerbungen"] += 1
        if a.get("has_reached_interview") == 1:
            eintrag["interviews"] += 1
        if a.get("status") in ("angebot", "angenommen"):
            eintrag["angebote"] += 1
    for k, e in kanaele.items():
        e["interview_quote"] = (
            round(e["interviews"] / e["bewerbungen"] * 100, 1)
            if e["bewerbungen"] else 0)
    ranking = sorted(kanaele.items(),
                     key=lambda kv: -kv[1]["interview_quote"])
    return {
        "kanaele": kanaele,
        "ranking_nach_interview_quote": [k for k, _ in ranking],
        "hinweis": (
            "'unklassifiziert' heisst: weder Vermittler- noch Portal- noch "
            "Netzwerk-Signal in den Daten — ehrlich benannt statt geraten "
            "(Bericht-Designprinzip v1.6.8)."
        ) if "unklassifiziert" in kanaele else "",
    }


def _ablehnungs_kategorie(a: dict, events: list) -> str:
    grund = f"{a.get('rejection_reason') or ''} {a.get('notes') or ''}"
    status = a.get("status") or ""
    if status == "arbeitgeber_ausgefallen" or _EXTERN_MUSTER.search(grund):
        return "extern_bedingt"
    if a.get("has_reached_interview") == 1:
        return "nach_interview"
    if status == "abgelaufen":
        return "stille_absage"
    if status == "abgelehnt":
        beworben = next((e for e in events if e["status"] == "beworben"), None)
        abgesagt = next((e for e in reversed(events)
                         if e["status"] == "abgelehnt"), None)
        if beworben and abgesagt:
            d = _tage(beworben["datum"], abgesagt["datum"])
            if d is not None and d <= 3:
                return "automatische_ablehnung"
        if a.get("vermittler"):
            return "vermittler_reject"
        if not (a.get("rejection_reason") or "").strip():
            return "ohne_grund"
        return "sonstige_absage"
    return "sonstige_absage"


def ablehnungs_kategorien(db: Any) -> dict:
    events = _lade_events(db)
    relevant = [a for a in db.get_applications()
                if (a.get("status") or "") in
                ("abgelehnt", "abgelaufen", "arbeitgeber_ausgefallen")]
    kategorien: dict = {}
    for a in relevant:
        kat = _ablehnungs_kategorie(a, events.get(a["id"], []))
        kategorien.setdefault(kat, []).append({
            "id": a["id"][:8],
            "firma": a.get("company", ""),
            "status": a.get("status", ""),
            "grund_freitext": (a.get("rejection_reason") or "")[:160],
        })

    gesamt = len(relevant)
    extern = len(kategorien.get("extern_bedingt", []))
    submitted = sum(1 for a in db.get_applications()
                    if (a.get("status") or "") != "in_vorbereitung")
    result = {
        "basis": gesamt,
        "kategorien": {
            k: {"anzahl": len(v), "faelle": v}
            for k, v in sorted(kategorien.items(),
                               key=lambda kv: -len(kv[1]))
        },
    }
    if submitted:
        echte_absagen = sum(
            len(v) for k, v in kategorien.items() if k != "extern_bedingt")
        result["ablehnungsquote_roh"] = round(gesamt / submitted * 100, 1)
        result["ablehnungsquote_bereinigt"] = round(
            echte_absagen / submitted * 100, 1)
        if extern:
            result["hinweis_bereinigung"] = (
                f"{extern} Fall/Faelle sind extern bedingt (Stelle "
                "gestrichen, intern besetzt, Insolvenz, ...) — das ist "
                "keine Ablehnung des Bewerbers. Die bereinigte Quote "
                "rechnet sie heraus."
            )
    return result


def notizen_gespraeche_check(db: Any) -> list:
    """#781 Punkt 6: Gespraeche, die nur im Notizfeld stehen.

    Findet Bewerbungen, deren Notizen nach stattgefundenen Gespraechen
    klingen (Muster + Datumsangabe), obwohl weder ein Interview-Event noch
    ein Meeting existiert. NUR eine pruefbare Liste — nichts wird angelegt.
    """
    events = _lade_events(db)
    conn = db.connect()
    treffer = []
    for a in db.get_applications():
        notiz = a.get("notes") or ""
        if not notiz or len(notiz) < 30:
            continue
        if not (_GESPRAECH_MUSTER.search(notiz)
                and _DATUM_MUSTER.search(notiz)):
            continue
        evs = events.get(a["id"], [])
        hat_iv_event = any(e["status"] in INTERVIEW_STATUS for e in evs)
        try:
            meetings = conn.execute(
                "SELECT COUNT(*) AS n FROM meetings WHERE application_id=?",
                (a["id"],),
            ).fetchone()["n"]
        except Exception:
            meetings = 0
        if not hat_iv_event and not meetings:
            treffer.append({
                "id": a["id"][:8],
                "firma": a.get("company", ""),
                "status": a.get("status", ""),
                "notiz_auszug": notiz[:180],
            })
    return treffer
