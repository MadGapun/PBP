"""Tests fuer v1.7.49 — #999: feste Schwellen gegen eine Skala ohne 100.

Gemeldet am 08.09.2026. Eine Stelle, die **alle** MUSS-Keywords trifft,
remote ist, 3 km entfernt liegt und ueber der Gehaltsvorstellung zahlt:

    Score 15.0/100 — fachlicher Gap zu gross.
    kategorie: NICHT_EMPFOHLEN

Die Begruendung nennt einen fachlichen Gap, den es nicht gibt.

**Der Gap ist die Skala.** `total_score` ist keine Prozentzahl, sondern
eine ungedeckelte Punktsumme; der erreichbare Hoechstwert folgt aus der
LAENGE der MUSS-Liste. Die Messreihe des Melders, hier nachgestellt:

    5 Begriffe -> 15 Punkte      30 Begriffe -> 66 Punkte
    10 Begriffe -> 26 Punkte     40 Begriffe -> 86 Punkte

`EMPFOHLEN` (>= 75) beginnt damit bei rund 37 gleichzeitig getroffenen
Pflichtbegriffen. Mit einer realistisch gepflegten Liste von fuenf bis
zehn ist die Kategorie unerreichbar, und **jede** Stelle faellt in
denselben Satz.

Der Hoechstwert wird jetzt aus denselben Kriterien berechnet, mit denen
gescort wird, und die Schwellen greifen auf den ANTEIL. Der Score selbst
bleibt unangetastet — er misst, was in der Anzeige steht; das ist eine
Messung, und die Einordnung ist eine Darstellung (#989).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.job_scraper import (  # noqa: E402
    calculate_score, fit_analyse, score_maximum,
)
from bewerbungs_assistent.tools.jobs import _build_empfehlung  # noqa: E402

# Fuelltext, damit die Anzeige nicht als "Kurztext" gilt — sonst greift
# ein anderes, korrektes k.o. und der Test misst etwas anderes.
FUELLTEXT = ("Wir bieten ein modernes Arbeitsumfeld mit flachen Hierarchien "
             "und viel Gestaltungsspielraum in einem wachsenden Team. ") * 6


def _volltreffer(n: int):
    """Eine Anzeige, die ALLE n MUSS-Begriffe traegt, remote und nah."""
    kws = [f"kw{i}" for i in range(n)]
    job = {
        "title": " ".join(kws[:5]),
        "description": (" ".join(kws) + " 100% remote. Gehalt 80.000 "
                        "EUR/Jahr. ") * 6 + FUELLTEXT,
        "distance_km": 3.0, "employment_type": "festanstellung",
        "remote_level": "remote", "salary_min": 80000,
        "salary_type": "jaehrlich", "location": "Hamburg",
    }
    kriterien = {"keywords_muss": kws, "min_gehalt": 60000,
                 "max_entfernung": {"festanstellung": 15}}
    return job, kriterien


# ── Der erreichbare Hoechstwert ───────────────────────────────────────

def test_999_volltreffer_erreicht_das_maximum_bei_jeder_listenlaenge():
    """Die staerkste Probe auf die Formel.

    Wer alles trifft, muss den Hoechstwert erreichen — egal ob die
    MUSS-Liste fuenf oder vierzig Begriffe hat. Weicht das ab, ist die
    Berechnung des Maximums falsch und nicht die Einordnung.
    """
    for n in (1, 3, 5, 10, 20, 40):
        job, kriterien = _volltreffer(n)
        assert fit_analyse(dict(job), kriterien)["total_score"] == \
            score_maximum(kriterien), f"{n} MUSS-Begriffe"


def test_999_das_maximum_waechst_mit_der_liste():
    """Genau das ist die Ursache: die Skala haengt an der Konfiguration.
    Der Test haelt sie fest, statt sie wegzudefinieren."""
    laengen = [score_maximum({"keywords_muss": [f"kw{i}" for i in range(n)]})
               for n in (5, 10, 20, 40)]
    assert laengen == sorted(laengen)
    assert laengen[0] < 30 < laengen[-1]


def test_999_ohne_muss_liste_traegt_der_rahmen():
    """Ohne MUSS-Begriffe gibt es keinen Fachscore, an dem sich etwas
    relativieren liesse — dann IST der Rahmen die Bewertung. Ohne diese
    Ausnahme wuerde durch Null geteilt, und zwar ausgerechnet bei einem
    frischen Profil (dieselbe Ueberlegung wie in `calculate_score`)."""
    assert score_maximum({"keywords_muss": []}) > 0
    assert score_maximum({}) > 0


def test_999_maximum_stuerzt_bei_muell_nicht_ab():
    """Es laeuft bei jeder Fit-Analyse mit — ein Absturz waere teurer
    als eine fehlende Einordnung."""
    for kriterien in (None, "kaputt", {"keywords_muss": None},
                      {"gewichtung": "kein json"},
                      {"keywords_muss": ["a"], "keyword_gewichte": None}):
        assert isinstance(score_maximum(kriterien), float)


# ── Die Einordnung ────────────────────────────────────────────────────

def test_999_die_einstufung_kam_aus_dem_score_und_tut_es_nicht_mehr():
    """Nachtrag zu #999 aus #1003 — die Skala war nur die halbe Miete.

    v1.7.49 hat den Massstab ehrlich gemacht: `score_maximum` folgt
    derselben Rechnung wie der Score, und die Einstufung nahm den
    ANTEIL statt einer erfundenen 100er-Skala.

    Der Nutzer hat danach den tieferliegenden Fehler benannt: in den
    Score gehen Keyword-Treffer, Gehalt, Entfernung und Remote-Grad ein
    — **der Lebenslauf nicht.** Ein Massstab fuer die falsche Zahl
    bleibt der falsche Massstab.

    Die Maximum-Formel bleibt (sie wird ausgewiesen und ist richtig),
    die Einstufung daraus ist weg. Dieser Test haelt genau das fest.
    """
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    for laenge in (5, 10, 20, 40):
        muss = [f"begriff{i}" for i in range(laenge)]
        v = _build_empfehlung(
            {"total_score": 100, "total_score_max": 100,
             "muss_hits": muss, "missing_muss": [], "risks": [],
             "beschreibung_vorhanden": True},
            {}, profil_kompetenzen=20)
        assert v["kategorie"] == "NICHT_BEURTEILBAR", f"{laenge} Begriffe"
        assert v["grundlage"] == "keine_grundlage"



def test_999_kein_ausgabetext_behauptet_eine_100er_skala():
    """"/100" nur schreiben, wenn 100 auch erreichbar ist. Solange die
    Zahl roh bleibt, ist der Satz falsch, nicht nur ungenau."""
    job, kriterien = _volltreffer(5)
    fit = fit_analyse(dict(job), kriterien)
    empfehlung = _build_empfehlung(fit, job)
    text = " ".join(str(v) for v in empfehlung.values())
    assert "/100" not in text
    assert "von erreichbaren" in text
    assert empfehlung["score_maximum"] == fit["total_score_max"]


def test_999_das_maximum_steht_weiter_in_der_antwort():
    """Es wird ausgewiesen, nur nicht mehr zum Urteil gemacht.

    Ohne die Zahl liesse sich der Score gar nicht einordnen — "Score 84"
    allein sagt nichts. Sie gehoert also weiter dazu, mit dem Satz, was
    sie misst.
    """
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    v = _build_empfehlung(
        {"total_score": 84, "total_score_max": 388.5, "muss_hits": ["x"],
         "missing_muss": ["y"], "risks": [], "beschreibung_vorhanden": True},
        {}, profil_kompetenzen=20)
    assert v["score"] == 84
    assert v["score_maximum"] == 388.5
    assert "SUCHBEGRIFFE" in v["score_bedeutung"]
    assert "84" in v["score_bedeutung"]



def test_999_ohne_bekanntes_maximum_wird_nichts_erfunden():
    """Lieber "nicht beurteilbar" als eine erfundene Einordnung — 0
    heisst unbekannt, nicht "nichts erreichbar" (#989)."""
    fit = {"total_score": 12, "total_score_max": 0, "muss_hits": ["a"]}
    empfehlung = _build_empfehlung(fit, {})
    assert empfehlung["kategorie"] == "NICHT_BEURTEILBAR"
    assert "/100" not in empfehlung["begruendung"]


# ── Die k.o.-Zweige bleiben, wie sie waren ────────────────────────────

def test_999_ko_zweige_unveraendert():
    """Der Melder grenzt das ausdruecklich ab: der k.o.-Zweig arbeitet
    mit Kriterien statt mit der Punktzahl und trifft die richtige
    Aussage. Er darf vom Fix nicht beruehrt werden."""
    fit = {"total_score": 0, "total_score_max": 20, "muss_hits": [],
           "missing_muss": ["plm", "cad"], "beschreibung_vorhanden": True}
    empfehlung = _build_empfehlung(fit, {})
    assert empfehlung["kategorie"] == "NICHT_EMPFOHLEN"
    assert "kein fachlicher Anker" in empfehlung["ko_gruende"][0]

    fehlt = _build_empfehlung(
        {"total_score": 3, "total_score_max": 20, "muss_hits": ["plm"],
         "beschreibung_vorhanden": False}, {})
    assert fehlt["kategorie"] == "NICHT_EMPFOHLEN"
    assert fehlt["score_zuverlaessig"] is False


# ── Der Score selbst bleibt unangetastet ──────────────────────────────

def test_999_der_score_wurde_nicht_umgerechnet():
    """#989 MERKE (3): der Score misst, was in der Anzeige steht — das
    ist eine Messung. Die Einordnung ist eine Darstellung und zieht dort
    die Konsequenz. Gespeicherte Zahlen still umzuschreiben waere
    derselbe Fehler wie #987, nur diesmal absichtlich."""
    job, kriterien = _volltreffer(5)
    assert calculate_score(dict(job), kriterien) == 15.0
    assert fit_analyse(dict(job), kriterien)["total_score"] == 15.0


def test_999_beide_rechenwege_kennen_dasselbe_maximum():
    """Die Lehre aus #963/#987, hier vorbeugend: das Maximum kommt aus
    EINER Funktion, die beide Wege dieselben Kriterien fragen laesst."""
    for n in (5, 20):
        job, kriterien = _volltreffer(n)
        aus_fit = fit_analyse(dict(job), kriterien)["total_score_max"]
        assert aus_fit == score_maximum(kriterien)
        assert calculate_score(dict(job), kriterien) <= aus_fit
