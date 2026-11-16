"""Der aktuelle Stand einer Bewerbung auf einen Blick (#1153, v1.7.146).

Abgrenzung: `bewerbung_status` hält die Status-Listen, `bewerbung_lebenszyklus`
die Regeln beim Anlegen und beim Statuswechsel (SCHREIBEN). Dieses Modul
LIEST: es baut den Block, mit dem `bewerbung_details` beginnt, und ordnet
Termine und Verlauf so, dass das Neueste zuerst steht.

Der Anlass (01.10.2026, Praxisfall): `bewerbung_details` begann mit den
ältesten Notizen, die Timeline lief aufsteigend (der neueste Eintrag stand
nach rund zehn langen als Letzter), Termine kamen gar nicht vor, und
`nächste_aktionen` sagte bei Status "Interview": "Du hattest ein Interview!",
auch wenn der Termin noch in der Zukunft lag. Wer die Ausgabe von oben las,
übersah eine Terminverschiebung und eine längst gegebene Zusage und schrieb
drei falsche Aussagen über dieselbe Bewerbung. Der Zustand ändert sich, der
Altstand bleibt sichtbar und wird weitergelesen (Ursachenklasse #1081).

Jetzt steht oben, was gilt: der nächste Termin mit seinem Status, der letzte
Eintrag, die offenen Aufgaben und Nachfassungen. Notizen und ältere
Einträge folgen und sagen, dass sie älter sein können.
"""
from __future__ import annotations

import re

from . import termin_zeit, uhr

#: Einträge im Verlauf, die ein Termin erzeugt (siehe `termin_folgen`).
TERMIN_EREIGNISSE = ("termin_verschoben", "termin_bestaetigt", "termin_abgesagt")

#: Status, in denen "Gespräch" gemeint ist.
GESPRAECHS_STATUS = ("interview", "zweitgespraech")

#: Wörter, mit denen ein älterer Eintrag etwas als OFFEN schildert.
_OFFEN = re.compile(r"offene aufgabe|aussteht|noch offen|offen und dringend", re.IGNORECASE)

LIES_ZUERST = (
    "Maßgeblich sind der nächste Termin mit seinem Status, der letzte Eintrag "
    "und die offenen Aufgaben. Notizen und ältere Einträge unten können "
    "überholt sein; ein Termin im Kalender geht einer älteren Notiz vor.")


def kurz(text, n: int = 300) -> str:
    sauber = " ".join(str(text or "").split())
    return sauber if len(sauber) <= n else sauber[: n - 1].rstrip() + "…"


def _termin_eintrag(m: dict) -> dict:
    beginn = str(m.get("meeting_date") or "")
    return {
        "id": m.get("id"),
        "beginn": beginn,
        "beginn_lesbar": termin_zeit.lesbar(beginn),
        "ende": m.get("meeting_end") or "",
        "titel": m.get("title") or "Termin",
        "art": m.get("meeting_type") or "",
        "status": m.get("status") or "geplant",
        "ort": m.get("location") or "",
        "notiz": kurz(m.get("notes"), 160),
    }


def termine_einteilen(termine: list, jetzt: str | None = None) -> dict:
    """{"kommend": aufsteigend, "vergangen": neueste zuerst}; abgesagte
    stehen mit ihrem Status dabei, zählen aber nirgends als Termin."""
    jetzt = jetzt or termin_zeit.jetzt_lokal()
    heute = jetzt[:10]
    kommend, vergangen = [], []
    for m in termine or []:
        e = _termin_eintrag(m)
        beginn = e["beginn"]
        ganztaegig_heute_oder_spaeter = len(beginn) == 10 and beginn >= heute
        (kommend if (beginn >= jetzt or ganztaegig_heute_oder_spaeter) else vergangen).append(e)
    kommend.sort(key=lambda x: x["beginn"])
    vergangen.sort(key=lambda x: x["beginn"], reverse=True)
    return {"kommend": kommend, "vergangen": vergangen}


def _erster_echter(eintraege: list) -> dict | None:
    return next((e for e in eintraege if e["status"] != "abgesagt"), None)


def aktueller_stand(db, app: dict, termine: dict | None = None) -> dict:
    """Der Block, mit dem `bewerbung_details` beginnt."""
    t = termine if termine is not None else termine_einteilen(
        db.get_meetings_for_application(app["id"]))
    # #1386: nach Zeitpunkt (UTC mit Zone und Ortszeit ohne Zone gemischt)
    events = uhr.nach_zeit(app.get("events") or [])
    letzter_eintrag = None
    if events:
        e = events[-1]
        letzter_eintrag = {"datum": (e.get("event_date") or "")[:10],
                           "status": e.get("status") or "",
                           "notiz": kurz(e.get("notes"))}
    aufgaben = [{"id": a.get("id"), "titel": a.get("titel") or "",
                 "faellig_am": (a.get("faellig_am") or "")[:10]}
                for a in db.list_tasks(application_id=app["id"], nur_offen=True)][:10]
    nachfassungen = [{"id": f.get("id"), "geplant_fuer": (f.get("scheduled_date") or "")[:10]}
                     for f in db.get_pending_follow_ups()
                     if f.get("application_id") == app["id"]][:10]
    return {
        "status": app.get("status") or "",
        "naechster_termin": _erster_echter(t["kommend"]),
        "letzter_termin": _erster_echter(t["vergangen"]),
        "letzter_eintrag": letzter_eintrag,
        "offene_aufgaben": aufgaben,
        "offene_nachfassungen": nachfassungen,
        "lies_zuerst": LIES_ZUERST,
    }


def timeline_aufbereiten(events: list) -> list:
    """Neueste zuerst. Ein älterer Eintrag, der etwas als OFFEN schildert
    (offene Aufgabe, Zusage steht aus), bekommt einen Hinweis, wenn danach ein
    Termin verschoben, bestätigt oder abgesagt wurde — der Text bleibt
    unverändert, nur der Hinweis kommt dazu."""
    sortiert = sorted(events or [],
                      key=lambda e: (e.get("event_date") or "", e.get("id") or 0),
                      reverse=True)
    letzte_aenderung = next(
        (e for e in sortiert if (e.get("status") or "") in TERMIN_EREIGNISSE), None)
    ergebnis = []
    for e in sortiert:
        eintrag = {
            # Ohne die ID liess sich ein Datum nicht korrigieren
            # (bewerbung_event_datum_setzen verweist hierher).
            "event_id": e.get("id"),
            "datum": e.get("event_date", ""),
            "status": e.get("status", ""),
            "notiz": e.get("notes", ""),
        }
        if (letzte_aenderung is not None and e is not letzte_aenderung
                and (e.get("event_date") or "") < (letzte_aenderung.get("event_date") or "")
                and (e.get("status") or "") not in TERMIN_EREIGNISSE
                and _OFFEN.search(e.get("notes") or "")):
            eintrag["hinweis"] = (
                "Möglicherweise überholt: danach wurde ein Termin geändert "
                f"(Eintrag vom {(letzte_aenderung.get('event_date') or '')[:10]}: "
                f"{kurz(letzte_aenderung.get('notes'), 120)}).")
        ergebnis.append(eintrag)
    return ergebnis


def aktionen_zeitbewusst(aktionen: dict, status: str, naechster: dict | None,
                         letzter: dict | None) -> dict:
    """Die Vorschläge bei "Interview" und "Zweitgespräch" passen zur Zeit:
    liegt der Termin vor uns, geht es um die Vorbereitung — nicht um die
    Nachbereitung eines Gesprächs, das noch nicht war."""
    if status not in GESPRAECHS_STATUS:
        return aktionen
    nachbereitung = "Gesprächsnotizen erfassen"
    rest = [dict(a) for a in aktionen.get("aktionen", [])]
    aus = dict(aktionen)
    if naechster:
        zusatz = " (zugesagt)" if naechster["status"] == "bestaetigt" else ""
        aus["beschreibung"] = (
            f"Dein nächstes Gespräch ist am {naechster['beginn_lesbar']}{zusatz}. "
            "Es hat noch nicht stattgefunden: jetzt geht es um die Vorbereitung, "
            "nicht um die Nachbereitung.")
        aus["motivation"] = "Gut vorbereitet gehst du entspannter ins Gespräch."
        neu = [
            {"label": "Gespräch vorbereiten", "tool": "workflow_starten",
             "workflow": "interview_vorbereitung"},
            {"label": "Termin ansehen oder ändern", "tool": "meetings_anzeigen"},
        ] + [a for a in rest if a.get("label") != nachbereitung]
    elif letzter:
        aus["beschreibung"] = (
            f"Dein letztes Gespräch war am {letzter['beginn_lesbar']}. Dokumentiere "
            "deine Eindrücke und Erkenntnisse, solange sie frisch sind.")
        neu = rest
    else:
        aus["beschreibung"] = (
            "Der Status steht auf Gespräch, aber es ist kein Termin hinterlegt. "
            "Trage den Termin ein, damit Kalender und Erinnerungen stimmen.")
        neu = [{"label": "Termin eintragen", "tool": "meeting_hinzufuegen"}] + [
            a for a in rest if a.get("label") != nachbereitung]
    for i, a in enumerate(neu, start=1):
        a["prioritaet"] = i
    aus["aktionen"] = neu
    return aus


def aktionen_zum_status(db, app_id: str, status: str, aktionen: dict,
                        termine: dict | None = None) -> dict:
    """Die Vorschläge zu einem Status, passend zu Zeit (#1342) und Stand (#1387).

    Die Antwort gilt für ALLE drei Wege (Anlegen, Details, Statuswechsel):
    erst die Zeit, dann das Erledigte (`erledigtes_streichen`).
    """
    return erledigtes_streichen(
        db, app_id, _aktionen_zeitbewusst_zum_status(
            db, app_id, status, aktionen, termine))


def _aktionen_zeitbewusst_zum_status(db, app_id: str, status: str, aktionen: dict,
                                     termine: dict | None = None) -> dict:
    """Die Vorschläge zu einem Status, passend zur Zeit (#1342).

    EINE Stelle für beide Wege, auf denen Claude die Vorschläge bekommt:
    `bewerbung_details` und die Antwort von `bewerbung_status_aendern`. Bei
    der Status-Antwort stand bisher der feste Text "Du hattest ein
    Interview!", auch wenn die Einladung gerade erst kam und der Termin vor
    uns lag. `termine` kann übergeben werden, wenn der Aufrufer sie schon
    eingeteilt hat.

    Lassen sich die Termine nicht lesen, wird das gesagt: weder "es gab ein
    Gespräch" noch "es ist keines eingetragen" ist dann belegt.
    """
    if status not in GESPRAECHS_STATUS:
        return aktionen
    try:
        t = termine if termine is not None else termine_einteilen(
            db.get_meetings_for_application(app_id))
    except Exception:
        neutral = dict(aktionen)
        neutral["beschreibung"] = (
            "Die Termine dieser Bewerbung konnten nicht gelesen werden. Prüfe sie "
            "mit meetings_anzeigen, bevor du von einem Gespräch sprichst, das war "
            "oder noch kommt.")
        neutral["aktionen"] = [
            {"label": "Termine ansehen", "tool": "meetings_anzeigen", "prioritaet": 1}
        ] + [dict(a, prioritaet=i) for i, a in enumerate(
            (a for a in aktionen.get("aktionen", [])
             if a.get("label") != "Gesprächsnotizen erfassen"), start=2)]
        return neutral
    return aktionen_zeitbewusst(aktionen, status, _erster_echter(t["kommend"]),
                                _erster_echter(t["vergangen"]))


# -- Was schon erledigt ist (#1387) ------------------------------------------
#
# `STATUS_ACTIONS` ist eine feste Liste je Status. Sie kannte nur den Status,
# nicht den Stand: "Fit-Analyse durchführen" stand als Schritt 1, obwohl die
# Bewertung an der Stelle hing; "Lebenslauf anpassen", obwohl die Unterlagen
# da waren; "Nachfass-Erinnerung planen" direkt neben der automatisch
# gesetzten. Claude folgt den Vorschlägen und fragt dann nach Dingen, die
# längst getan sind.

_SCHRITT_BEWERTUNG = "fit_analyse"
_SCHRITT_LEBENSLAUF = "lebenslauf_angepasst_exportieren"
_SCHRITT_ANSCHREIBEN = "anschreiben_exportieren"
_SCHRITT_NACHFASS = "nachfass_planen"


def stand_erledigt(db, app_id: str) -> dict:
    """Was zu dieser Bewerbung schon da ist: Bewertung, Unterlagen, Nachfass.

    Nie eine Ausnahme: kann etwas nicht gelesen werden, gilt es als NICHT
    erledigt (der Vorschlag bleibt stehen - lieber einer zu viel).
    """
    erg: dict = {"bewertung": None, "lebenslauf": False, "anschreiben": False,
                 "nachfass": None}
    try:
        app = db.get_application(app_id) or {}
    except Exception:
        return erg
    try:
        if app.get("job_hash"):
            from . import passung
            job = db.get_job(app["job_hash"])
            befund = passung.analyse_lesen(
                job, db.get_profile(), db.get_search_criteria()) if job else None
            if befund:
                erg["bewertung"] = {"kategorie": befund.get("urteil", ""),
                                    "veraltet": bool(befund.get("veraltet"))}
    except Exception:
        pass
    try:
        typen = {d.get("doc_type") for d in db.get_documents_for_application(app_id)}
        erg["lebenslauf"] = bool(app.get("cv_path")) or "lebenslauf" in typen
        erg["anschreiben"] = bool(app.get("cover_letter_path")) or "anschreiben" in typen
    except Exception:
        pass
    try:
        offen = [f for f in db.get_pending_follow_ups()
                 if str(f.get("application_id")) == str(app_id)]
        if offen:
            erg["nachfass"] = min(
                str(f.get("scheduled_date") or "")[:10] for f in offen)
    except Exception:
        pass
    return erg


def erledigtes_streichen(db, app_id: str, aktionen: dict) -> dict:
    """Streicht Vorschläge, deren Ergebnis schon da ist, und sagt es offen.

    `schon_erledigt` nennt, was gestrichen wurde und warum: der Mensch (und
    Claude) sehen, dass PBP den Stand kennt, statt einen Schritt stillschweigend
    zu verlieren. Eine veraltete Bewertung bleibt als Schritt stehen, mit
    ehrlichem Namen.
    """
    stand = stand_erledigt(db, app_id)
    aus = dict(aktionen)
    erledigt: list[str] = []
    neu: list[dict] = []
    for a in aktionen.get("aktionen", []):
        a = dict(a)
        tool = a.get("tool")
        if tool == _SCHRITT_BEWERTUNG and stand["bewertung"]:
            if stand["bewertung"]["veraltet"]:
                a["label"] = "Bewertung der Stelle auffrischen (Profil oder Anzeige haben sich geändert)"
            else:
                erledigt.append(
                    "Stelle bewertet (" + (stand["bewertung"]["kategorie"] or "gespeichert") + ")")
                continue
        elif tool == _SCHRITT_LEBENSLAUF and stand["lebenslauf"]:
            erledigt.append("Lebenslauf liegt bei der Bewerbung")
            continue
        elif tool == _SCHRITT_ANSCHREIBEN and stand["anschreiben"]:
            erledigt.append("Anschreiben liegt bei der Bewerbung")
            continue
        elif tool == _SCHRITT_NACHFASS and stand["nachfass"]:
            erledigt.append("Nachfass-Erinnerung gesetzt (am " + stand["nachfass"] + ")")
            continue
        neu.append(a)
    if erledigt:
        for i, a in enumerate(neu, start=1):
            if a.get("prioritaet", 0) < 9:
                a["prioritaet"] = i
        aus["aktionen"] = neu
        aus["schon_erledigt"] = erledigt
    return aus
