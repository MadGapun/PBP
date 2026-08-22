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
    null_abstand = 0

    for a in apps:
        evs = events.get(a["id"], [])
        if len(evs) <= 2:
            wenig_events += 1
        # v1.7.23 (#943): Bei rekonstruierten Altbewerbungen wurden
        # Bewerbungs- und Absagedatum am SELBEN TAG nachgetragen. Die
        # Differenz ist dann null, und der Median aller Vorgaenge lag
        # deshalb bei 0,0 Tagen — ein Artefakt der Erfassung, kein
        # Marktphaenomen. Die Fussnote benannte es zwar, die Zahl wurde
        # aber trotzdem unqualifiziert ausgegeben.
        #
        # Ausgeschlossen wird genau diese Signatur (Abstand 0), NICHT
        # pauschal jeder Vorgang mit wenigen Ereignissen: eine echte
        # Absage nach zwei Tagen ist ein gueltiger Datenpunkt, auch wenn
        # dazwischen nichts protokolliert wurde.
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
                _d = _tage(start, iv_ev["datum"])
                if _d:
                    bis_interview.append(_d)
                elif _d == 0:
                    null_abstand += 1

        if beworben_ev:
            naechster = next(
                (e for e in evs
                 if e["datum"] > beworben_ev["datum"]
                 and e["status"] not in ("beworben", "notiz")), None)
            if naechster:
                _d = _tage(beworben_ev["datum"], naechster["datum"])
                if _d:
                    reaktion.append(_d)
                elif _d == 0:
                    null_abstand += 1

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
                if d2 == 0:
                    null_abstand += 1
                elif d2 is not None:
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
        "zeitkennzahlen_basis": (
            f"Vorgaenge mit Abstand 0 Tage sind ausgeschlossen "
            f"({null_abstand} Faelle): bei rekonstruierten "
            "Altbewerbungen wurden Bewerbungs- und Absagedatum am selben "
            "Tag nachgetragen, was den Median auf 0 gedrueckt hat, ohne "
            "etwas ueber den Markt auszusagen. Eine echte Absage nach "
            "zwei Tagen zaehlt weiterhin mit. `anzahl` nennt je Kennzahl "
            "die Fallzahl."),
        "zeitkennzahlen_ausgeschlossen": null_abstand,
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


# v1.7.23 (#943): Ausdruecklich KEINE Rueckmeldung. Das ist per
# Definition das Gegenteil einer automatischen Ablehnung — es hat sich
# schlicht niemand gemeldet.
_STILLE_MUSTER = re.compile(
    r"keine r(ue|ü)ckmeldung|stille absage|nie (etwas )?geh(oe|ö)rt|"
    r"nichts (mehr )?geh(oe|ö)rt|keine antwort|ohne r(ue|ü)ckmeldung|"
    r"nicht gemeldet|versandet",
    re.IGNORECASE,
)

# Positives Signal fuer eine WIRKLICH automatische Ablehnung. Ohne so
# ein Signal ist eine schnelle Absage nur eine schnelle Absage.
_AUTOMATIK_MUSTER = re.compile(
    r"automatisiert|automatische? absage|ai[- ]screening|"
    r"ki[- ]screening|systemabsender|no[- ]?reply|noreply|"
    r"nicht durch (das )?screening|absage ohne menschlichen kontakt|"
    r"applicant tracking|ats",
    re.IGNORECASE,
)

# v1.7.23 (#943): Vermutung, Fakt oder eigene Zuschreibung? Ohne diese
# Trennung wird eine Vermutung beim spaeteren Auswerten zur Tatsache —
# und aus falschen Befunden folgen falsche Schluesse ueber die eigenen
# Unterlagen.
_VERMUTUNG_MUSTER = re.compile(
    r"vermutlich|vermutet|verm\.|wahrscheinlich|vermutung|"
    r"unklar|k(oe|ö)nnte|scheint",
    re.IGNORECASE,
)
_WERTUNG_MUSTER = re.compile(
    r"gewertet|selbst (auf|als)|eigene einsch(ae|ä)tzung|"
    r"als .{0,20}gewertet|von mir",
    re.IGNORECASE,
)


def sicherheitsgrad(a: dict) -> str:
    """belegt | vermutet | eigene_wertung — ohne Schemaaenderung.

    Minimalloesung aus dem Issue: Signalwoerter im Freitext erkennen,
    statt den Fall als Befund zu behandeln. Ein Vorgang, den der Nutzer
    selbst auf 'abgelehnt' gesetzt hat, obwohl nie eine Absage kam, ist
    keine Ablehnung des Arbeitgebers — er treibt die Quote aber genauso.
    """
    text = f"{a.get('rejection_reason') or ''} {a.get('notes') or ''}"
    if _WERTUNG_MUSTER.search(text):
        return "eigene_wertung"
    if _VERMUTUNG_MUSTER.search(text):
        return "vermutet"
    return "belegt"


def _ablehnungs_kategorie(a: dict, events: list) -> str:
    grund = f"{a.get('rejection_reason') or ''} {a.get('notes') or ''}"
    status = a.get("status") or ""
    if status == "arbeitgeber_ausgefallen" or _EXTERN_MUSTER.search(grund):
        return "extern_bedingt"
    if a.get("has_reached_interview") == 1:
        return "nach_interview"
    if status == "abgelaufen":
        return "stille_absage"
    # v1.7.23 (#943): "Keine Rueckmeldung" ist eine stille Absage —
    # unabhaengig vom Status und von den Datumsabstaenden. Vorher landeten
    # 13 solcher Faelle in `automatische_ablehnung`, weil bei
    # rekonstruierten Altbewerbungen Bewerbungs- und Absagedatum am
    # selben Tag nachgetragen wurden und die Differenz damit 0 war.
    if _STILLE_MUSTER.search(grund):
        return "stille_absage"

    if status == "abgelehnt":
        beworben = next((e for e in events if e["status"] == "beworben"), None)
        abgesagt = next((e for e in reversed(events)
                         if e["status"] == "abgelehnt"), None)
        # Eine automatische Ablehnung braucht ein POSITIVES Signal.
        # Der blosse Zeitabstand genuegt nicht: die Kategorien fuehren zu
        # entgegengesetzten Handlungen (Unterlagen pruefen gegen frueher
        # nachfassen), und wer auf eine falsch befuellte Zahl schaut,
        # optimiert am eigentlichen Problem vorbei.
        if _AUTOMATIK_MUSTER.search(grund):
            return "automatische_ablehnung"
        if beworben and abgesagt:
            d = _tage(beworben["datum"], abgesagt["datum"])
            # Sehr schnelle Absage ist ein gueltiges Signal (Issue:
            # "innerhalb von 48 Stunden ohne menschlichen Kontakt").
            #
            # ABER NULL Tage zaehlt nicht: bei rekonstruierten
            # Altbewerbungen wurden Bewerbungs- und Absagedatum am selben
            # Tag nachgetragen: die Differenz ist dann ein Artefakt der
            # Erfassung, keine Aussage ueber den Arbeitgeber. Genau diese
            # Faelle hatten die Kategorie geflutet.
            # Grenze 72 Stunden — so heisst die Kategorie auch im
            # Bericht ("Automatische Ablehnung (< 72h)"). Der Beleg aus
            # dem Issue liegt bei rund 50 Stunden (Freitagabend
            # eingereicht, Sonntagabend abgesagt).
            if d is not None and 0 < d < 3:
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
            # #943: Vermutung, Fakt oder eigene Zuschreibung.
            "sicherheit": sicherheitsgrad(a),
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
    # v1.7.23 (#943): Abgelaufen ist KEINE Ablehnung. Ein versandeter
    # Vorgang heisst, dass nichts mehr passiert ist — haeufig, weil auf
    # keiner Seite nachgefasst wurde. Anderes Problem, andere
    # Konsequenz, und anders als eine Absage teilweise im eigenen
    # Einflussbereich.
    abgelehnt = sum(1 for a in relevant if (a.get("status") or "") == "abgelehnt")
    versandet = sum(1 for a in relevant if (a.get("status") or "") == "abgelaufen")
    nach_sicherheit: dict = {}
    for eintraege in kategorien.values():
        for f in eintraege:
            nach_sicherheit[f["sicherheit"]] = (
                nach_sicherheit.get(f["sicherheit"], 0) + 1)
    result["sicherheit"] = nach_sicherheit
    if nach_sicherheit.get("vermutet") or nach_sicherheit.get("eigene_wertung"):
        result["sicherheit_hinweis"] = (
            f"{nach_sicherheit.get('vermutet', 0)} Vorgaenge tragen eine "
            f"Vermutung als Grund, {nach_sicherheit.get('eigene_wertung', 0)} "
            "eine eigene Zuschreibung ('als stille Absage gewertet'). Diese "
            "Faelle sind KEINE mitgeteilten Absagen — sie zaehlen in der "
            "Quote mit, taugen aber nicht als Befund ueber die eigenen "
            "Unterlagen.")

    if submitted:
        echte_absagen = sum(
            len(v) for k, v in kategorien.items() if k != "extern_bedingt")
        result["abgelehnt_quote"] = round(abgelehnt / submitted * 100, 1)
        result["versandet_quote"] = round(versandet / submitted * 100, 1)
        result["abgelehnt_vs_versandet"] = (
            f"{result['abgelehnt_quote']} % abgelehnt, "
            f"{result['versandet_quote']} % versandet")
        result["ablehnungsquote_roh"] = round(gesamt / submitted * 100, 1)
        result["ablehnungsquote_hinweis"] = (
            "ablehnungsquote_roh enthaelt abgelaufene Vorgaenge. Fuer die "
            "Frage 'wie oft wurde ich abgelehnt' ist abgelehnt_quote der "
            "richtige Wert.")
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


# ─────────────────────────────────────────────────────────────────────
# v1.7.23 (#943): Auswertungen, die aus dem vorhandenen Bestand ohne
# Zusatzerfassung berechenbar waren und trotzdem fehlten.
# ─────────────────────────────────────────────────────────────────────

def erfolg_nach_score_band(db: Any) -> dict:
    """Fuehren hoch bewertete Stellen zu mehr Interviews?

    Die einzige Moeglichkeit, das Scoring gegen die Realitaet zu pruefen:
    ohne diese Auswertung ist jede Kalibrierung eine Behauptung.
    """
    baender = [(0, 24), (25, 49), (50, 74), (75, 1000)]
    ergebnis: dict = {}
    for unten, oben in baender:
        label = f"{unten}-{oben}" if oben < 1000 else f"{unten}+"
        ergebnis[label] = {"bewerbungen": 0, "interviews": 0, "angebote": 0}

    def _band(score) -> str:
        for unten, oben in baender:
            if unten <= (score or 0) <= oben:
                return f"{unten}-{oben}" if oben < 1000 else f"{unten}+"
        return "0-24"

    ohne_score = 0
    for a in db.get_applications():
        if (a.get("status") or "") == "in_vorbereitung":
            continue
        job = None
        try:
            verknuepft = db.get_jobs_for_application(a.get("id"))
            job = verknuepft[0] if verknuepft else None
        except Exception:
            job = None
        if job is None and a.get("job_hash"):
            job = db.get_job(a["job_hash"])
        if not job or not job.get("score"):
            ohne_score += 1
            continue
        b = ergebnis[_band(job.get("score"))]
        b["bewerbungen"] += 1
        if a.get("has_reached_interview") == 1:
            b["interviews"] += 1
        if (a.get("status") or "") in ("angebot", "zugesagt"):
            b["angebote"] += 1

    for b in ergebnis.values():
        b["interview_quote"] = (
            round(b["interviews"] / b["bewerbungen"] * 100, 1)
            if b["bewerbungen"] else None)

    return {
        "baender": ergebnis,
        "ohne_verknuepfte_stelle": ohne_score,
        "hinweis": (
            "Bewerbungen ohne verknuepfte Stelle (Direkteintrag, "
            "Vermittler-Anfrage) koennen hier nicht zugeordnet werden — "
            f"das sind {ohne_score}. Bei kleinen Fallzahlen je Band ist "
            "die Quote ein Hinweis, kein Beleg."),
    }


def nachfass_wirksamkeit(db: Any) -> dict:
    """Aendert ein Follow-up die Reaktionswahrscheinlichkeit?

    Angesichts der versandeten Vorgaenge die wichtigste offene Frage:
    Nachfassen kostet Ueberwindung, und ohne Zahl dazu bleibt es
    Geschmackssache.
    """
    conn = db.connect()
    mit = {"anzahl": 0, "reaktion": 0}
    ohne = {"anzahl": 0, "reaktion": 0}
    events = _lade_events(db)

    for a in db.get_applications():
        if (a.get("status") or "") == "in_vorbereitung":
            continue
        try:
            n = conn.execute(
                "SELECT COUNT(*) AS n FROM follow_ups "
                "WHERE application_id=? AND status IN ('gesendet','erledigt')",
                (a["id"],)).fetchone()["n"]
        except Exception:
            n = 0
        topf = mit if n else ohne
        topf["anzahl"] += 1
        # Reaktion = irgendein Ereignis nach 'beworben', das nicht nur
        # eine Notiz ist.
        evs = events.get(a["id"], [])
        beworben = next((e for e in evs if e["status"] == "beworben"), None)
        if beworben and any(
                e["datum"] > beworben["datum"]
                and e["status"] not in ("beworben", "notiz") for e in evs):
            topf["reaktion"] += 1

    for topf in (mit, ohne):
        topf["reaktionsquote"] = (
            round(topf["reaktion"] / topf["anzahl"] * 100, 1)
            if topf["anzahl"] else None)

    aussage = ""
    if mit["anzahl"] >= 5 and ohne["anzahl"] >= 5:
        diff = (mit["reaktionsquote"] or 0) - (ohne["reaktionsquote"] or 0)
        if abs(diff) < 5:
            aussage = ("Kein erkennbarer Unterschied — bei diesen "
                       "Fallzahlen aber auch kein Gegenbeweis.")
        elif diff > 0:
            aussage = (f"Mit Nachfassen {diff:.1f} Prozentpunkte mehr "
                       "Reaktionen.")
        else:
            aussage = (f"Ohne Nachfassen {abs(diff):.1f} Prozentpunkte mehr "
                       "Reaktionen — vermutlich ein Auswahleffekt: "
                       "nachgefasst wird dort, wo es ohnehin still blieb.")
    else:
        aussage = ("Zu wenige Faelle je Gruppe fuer eine Aussage "
                   "(mindestens 5 je Seite noetig).")

    return {"mit_nachfassen": mit, "ohne_nachfassen": ohne,
            "aussage": aussage}


def trend_vergleich(db: Any) -> dict:
    """Die aktuellen drei Monate gegen die drei davor."""
    from datetime import date, timedelta

    heute = date.today()
    grenze_1 = (heute - timedelta(days=90)).isoformat()
    grenze_2 = (heute - timedelta(days=180)).isoformat()

    aktuell = {"bewerbungen": 0, "interviews": 0}
    davor = {"bewerbungen": 0, "interviews": 0}
    for a in db.get_applications():
        wann = (a.get("applied_at") or "")[:10]
        if not wann or (a.get("status") or "") == "in_vorbereitung":
            continue
        if wann >= grenze_1:
            topf = aktuell
        elif wann >= grenze_2:
            topf = davor
        else:
            continue
        topf["bewerbungen"] += 1
        if a.get("has_reached_interview") == 1:
            topf["interviews"] += 1

    for topf in (aktuell, davor):
        topf["interview_quote"] = (
            round(topf["interviews"] / topf["bewerbungen"] * 100, 1)
            if topf["bewerbungen"] else None)

    aussage = "Zu wenige Daten fuer einen Vergleich."
    if aktuell["bewerbungen"] and davor["bewerbungen"]:
        d = aktuell["bewerbungen"] - davor["bewerbungen"]
        richtung = "mehr" if d > 0 else ("weniger" if d < 0 else "genauso viele")
        aussage = (f"{abs(d)} {richtung} Bewerbungen als im Vorquartal "
                   f"({davor['bewerbungen']} -> {aktuell['bewerbungen']}).")
        if aktuell["interview_quote"] is not None and davor["interview_quote"] is not None:
            dq = aktuell["interview_quote"] - davor["interview_quote"]
            aussage += (f" Interview-Quote {dq:+.1f} Prozentpunkte "
                        f"({davor['interview_quote']} -> "
                        f"{aktuell['interview_quote']} %).")

    return {"letzte_3_monate": aktuell, "3_monate_davor": davor,
            "aussage": aussage}
