"""Was PBP ueber eine Stelle WEISS — und was es nur annimmt (#989).

Der Nutzer hat vier voneinander unabhaengige Fehler an einem Tag
gemeldet und ihre gemeinsame Wurzel benannt:

> Wo eine Information fehlt, setzt PBP einen neutralen Wert ein und
> rechnet weiter. Neutral heisst in einem Punktesystem aber nicht
> "unbekannt", sondern "kostet nichts". Und was nichts kostet, steigt
> in der Sortierung.

Gemessen am 07.09.2026: eine Stelle mit vollstaendiger, fachlich
passender Beschreibung bekam 32 Punkte, ein inhaltsleerer Titel 101.
Die Rangfolge stand systematisch auf dem Kopf — oben das Unbekannte,
darunter das Geprueftte mit seinen ehrlichen Abzuegen.

**Die Bausteine gab es schon.** `entfernungs_guete` (#965) kennt
"unbekannt", `score_status` (#756) kennt "unbewertet", `grund_guete`
(#966) kennt "schwach". Alle drei standen in Tool-Antworten — und in
der Liste, die der Mensch tatsaechlich ansieht, kam nichts davon an.
Dieses Modul sammelt sie an EINER Stelle und beantwortet je Stelle
dieselbe Frage in derselben Sprache.

**Drei Zustaende statt zwei.** Eine Dimension ist

* ``geprueft``   — es gibt Daten, und das Kriterium ist erfuellt
* ``verletzt``   — es gibt Daten, und das Kriterium ist NICHT erfuellt
* ``ungeprueft`` — es gibt keine Daten

`verletzt` und `ungeprueft` sehen im Score gleich aus (beide bringen
keine Punkte) und bedeuten das Gegenteil voneinander. Genau diese
Verwechslung ist der Befund.

**Was dieses Modul BEWUSST nicht tut: den Score veraendern.** Der Score
misst, was in der Anzeige steht; das ist eine Messung und bleibt eine.
Die Rangfolge dagegen ist eine Darstellung, und dort gehoert die
Unterscheidung hin. Wer es anders will, stellt es um — siehe
`UMGANG_MIT_UNBEKANNT`.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Ab dieser Laenge traegt ein Anzeigentext eine Bewertung. Der Wert lag
# als nackte 50 an sieben Stellen im Code (jobs.py gleich viermal,
# analyse.py, workspace_service.py, database.py) — dieselbe Zahl, jedes
# Mal neu hingeschrieben. Hier ist sie einmal.
MIN_BESCHREIBUNG = 50

GEPRUEFT = "geprueft"
VERLETZT = "verletzt"
UNGEPRUEFT = "ungeprueft"
ZUSTAENDE = (GEPRUEFT, VERLETZT, UNGEPRUEFT)

# Wie soll PBP mit ungeprueften Dimensionen umgehen? Nutzerentscheidung
# (#989, Vorschlag 4): "Fuer einen Nutzer, dessen Kriterium 'nur remote
# oder im Nahbereich' lautet, ist eine Stelle mit unbekanntem Ort im
# Zweifel keine Nahstelle. Fuer andere kann das anders sein."
EINSTELLUNG = "umgang_mit_unbekannt"
MITMISCHEN = "mitmischen"
NACHRANGIG = "nachrangig"
STRENG = "streng"
UMGANG_MIT_UNBEKANNT = {
    MITMISCHEN: (
        "Ungeprueftes mischt sich unter das Geprueftte — der Stand bis "
        "v1.7.38. Ehrlich nur, wenn man weiss, dass Score 0 kein Urteil "
        "ist."),
    NACHRANGIG: (
        "Vorgabe. Der Score bleibt unveraendert, aber eine Stelle ohne "
        "Bewertungsgrundlage steht nie ueber einer, die eine hat."),
    STRENG: (
        "Zusaetzlich zaehlt eine unbekannte Entfernung wie eine zu "
        "grosse. Fuer alle, deren Kriterium 'nur in der Naehe' lautet."),
}

# Die Dimensionen, aus denen sich ein Score zusammensetzt. `traegt`
# sagt, was an dieser Dimension haengt — ohne das ist "ungeprueft" nur
# eine Vokabel.
DIMENSIONEN: tuple[dict, ...] = (
    {"id": "beschreibung", "titel": "Anzeigentext",
     "traegt": "Keyword-Treffer, MUSS-Tor und Fit-Analyse — also fast "
               "der ganze Score",
     "tragend": True},
    {"id": "entfernung", "titel": "Entfernung",
     "traegt": "Naehe-Bonus und Fern-Malus"},
    {"id": "gehalt", "titel": "Gehalt",
     "traegt": "die Dimension mit dem hoechsten Gewicht"},
    {"id": "remote", "titel": "Remote-Anteil",
     "traegt": "Remote-Bonus"},
    {"id": "stellenart", "titel": "Stellenart",
     "traegt": "Zu-/Abschlag je Art (Festanstellung, Freelance, ...)"},
)


def umgang(db) -> str:
    """Wie der Nutzer es eingestellt hat — Vorgabe `nachrangig`."""
    try:
        wert = db.get_profile_setting(EINSTELLUNG, None)
    except Exception as exc:  # pragma: no cover — nie eine Liste stoppen
        logger.debug("Umgang mit Unbekanntem nicht lesbar: %s", exc)
        return NACHRANGIG
    return wert if wert in UMGANG_MIT_UNBEKANNT else NACHRANGIG


def umgang_setzen(db, wert: str) -> dict:
    """Setzt die Einstellung; unbekannte Werte werden abgewiesen."""
    if wert not in UMGANG_MIT_UNBEKANNT:
        return {"fehler": f"'{wert}' ist keine Einstellung. Moeglich: "
                          + ", ".join(sorted(UMGANG_MIT_UNBEKANNT))}
    db.set_profile_setting(EINSTELLUNG, wert)
    return {"status": "gesetzt", "umgang": wert,
            "bedeutet": UMGANG_MIT_UNBEKANNT[wert],
            "hinweis": "Wirkt auf die Reihenfolge der Trefferliste. Der "
                       "gespeicherte Score aendert sich dadurch nicht — "
                       "ausser bei 'streng', dort zaehlt eine unbekannte "
                       "Entfernung wie eine zu grosse: dann einmal "
                       "scores_neu_berechnen() laufen lassen."}


def hat_beschreibung(job: dict) -> bool:
    """Traegt der Anzeigentext eine Bewertung?"""
    return len((job.get("description") or "").strip()) >= MIN_BESCHREIBUNG


def _entfernung(job: dict, criteria: dict) -> tuple[str, str]:
    from ..job_scraper import entfernungs_guete
    guete, grund = entfernungs_guete(job)
    if guete == "unbekannt":
        return UNGEPRUEFT, grund
    if guete == "entfaellt":
        return GEPRUEFT, "Vollstaendig remote — Entfernung ohne Belang."
    dist = job.get("distance_km")
    art = job.get("employment_type") or "festanstellung"
    karte = criteria.get("max_entfernung") or {}
    wunsch = karte.get(art)
    if wunsch and dist is not None and dist > wunsch:
        return VERLETZT, f"{dist:.0f} km — ueber deinem Wunschwert von {wunsch} km."
    return GEPRUEFT, ""


def _gehalt(job: dict, criteria: dict) -> tuple[str, str]:
    # #827: eine Schaetzung ist keine Angabe. Sie zaehlt im Score gar
    # nicht — und damit ist die Dimension ungeprueft, nicht erfuellt.
    if job.get("salary_estimated"):
        return UNGEPRUEFT, ("Nur eine Schaetzung, keine Angabe aus der "
                            "Anzeige — zaehlt im Score nicht (#827).")
    betrag = job.get("salary_min")
    if not betrag:
        return UNGEPRUEFT, "Die Anzeige nennt kein Gehalt."
    wunsch = criteria.get("min_gehalt") or 0
    if wunsch and job.get("salary_type", "jaehrlich") == "jaehrlich" and betrag < wunsch:
        return VERLETZT, f"{int(betrag)} unter deinem Wunsch von {int(wunsch)}."
    return GEPRUEFT, ""


def _remote(job: dict, criteria: dict) -> tuple[str, str]:
    stufe = (job.get("remote_level") or "unbekannt").lower()
    if stufe in ("", "unbekannt"):
        return UNGEPRUEFT, "Die Anzeige sagt nichts zum Remote-Anteil."
    return GEPRUEFT, ""


def _stellenart(job: dict, criteria: dict) -> tuple[str, str]:
    art = (job.get("employment_type") or "").strip().lower()
    if not art or art == "unbekannt":
        return UNGEPRUEFT, "Die Anzeige sagt nichts zur Stellenart."
    gewuenscht = [str(t).lower() for t in (criteria.get("stellentypen") or [])]
    if gewuenscht and art not in gewuenscht:
        return VERLETZT, f"'{art}' steht nicht in deinen Stellentypen."
    return GEPRUEFT, ""


def _beschreibung(job: dict, criteria: dict) -> tuple[str, str]:
    if hat_beschreibung(job):
        return GEPRUEFT, ""
    laenge = len((job.get("description") or "").strip())
    return UNGEPRUEFT, (
        f"Nur {laenge} Zeichen Anzeigentext — zu wenig, um Fachgebiet, "
        "System oder Senioritaet zu beurteilen. Der Score beruht damit "
        "allein auf dem Titel.")


_PRUEFER = {
    "beschreibung": _beschreibung,
    "entfernung": _entfernung,
    "gehalt": _gehalt,
    "remote": _remote,
    "stellenart": _stellenart,
}


def befund(job: dict, criteria: dict | None = None) -> dict[str, dict]:
    """Je Dimension: geprueft, verletzt oder ungeprueft — mit Grund."""
    krit = criteria or {}
    ergebnis: dict[str, dict] = {}
    for dim in DIMENSIONEN:
        try:
            zustand, grund = _PRUEFER[dim["id"]](job, krit)
        except Exception as exc:  # pragma: no cover — nie eine Liste stoppen
            logger.debug("Datenguete %s fehlgeschlagen: %s", dim["id"], exc)
            zustand, grund = UNGEPRUEFT, "nicht bestimmbar"
        eintrag = {"zustand": zustand, "titel": dim["titel"]}
        if grund:
            eintrag["grund"] = grund
        if zustand == UNGEPRUEFT:
            eintrag["traegt"] = dim["traegt"]
        ergebnis[dim["id"]] = eintrag
    return ergebnis


def vollstaendigkeit(job: dict, criteria: dict | None = None) -> dict:
    """Wie viel des Scores auf echten Daten beruht.

    "Ein Score aus einem Titel ist etwas anderes als ein Score aus einer
    vollstaendigen Anzeige, und der Unterschied gehoert sichtbar."
    """
    b = befund(job, criteria)
    belegt = [k for k, v in b.items() if v["zustand"] != UNGEPRUEFT]
    offen = [k for k, v in b.items() if v["zustand"] == UNGEPRUEFT]
    gesamt = len(DIMENSIONEN)
    return {
        "belegt": len(belegt),
        "gesamt": gesamt,
        "anteil": round(len(belegt) / gesamt, 2) if gesamt else 0.0,
        "ungeprueft": offen,
        "bewertungsgrundlage": hat_beschreibung(job),
        "dimensionen": b,
    }


def rang(job: dict, criteria: dict | None = None) -> int:
    """0 = mit Bewertungsgrundlage, 1 = ohne. Kleiner steht weiter oben.

    BEWUSST nur die Beschreibung und nicht die Zahl der ungeprueften
    Dimensionen: der Anzeigentext traegt fast den ganzen Score, die
    anderen Dimensionen sind einzelne Zu- und Abschlaege. Eine Stelle
    ohne bekannte Entfernung ist ungenau bewertet; eine ohne Text ist
    GAR nicht bewertet. Nur das rechtfertigt eine eigene Gruppe — sonst
    landet fast alles in Gruppe 1 und die Trennung sagt nichts mehr.
    """
    return 0 if hat_beschreibung(job) else 1


def sortierschluessel(job: dict, umgang_wert: str = NACHRANGIG,
                      criteria: dict | None = None) -> int:
    """Der Rang, wie ihn die Liste anwendet — abhaengig von der Einstellung."""
    if umgang_wert == MITMISCHEN:
        return 0
    return rang(job, criteria)


def kurzmarke(job: dict, criteria: dict | None = None) -> dict | None:
    """Was an der Zeile steht — oder None, wenn alles belegt ist.

    AK 2 des Issues: "Die Trefferliste weist ungeprueft sichtbar aus,
    nicht nur die Tool-Antwort."
    """
    v = vollstaendigkeit(job, criteria)
    if not v["ungeprueft"]:
        return None
    titel = [v["dimensionen"][k]["titel"] for k in v["ungeprueft"]]
    return {
        "ungeprueft": v["ungeprueft"],
        "text": "Ungeprueft: " + ", ".join(titel),
        "belegt": v["belegt"],
        "gesamt": v["gesamt"],
        "ohne_bewertungsgrundlage": not v["bewertungsgrundlage"],
    }
