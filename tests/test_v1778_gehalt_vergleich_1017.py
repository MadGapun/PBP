"""Tests fuer #1017 — ein Jahresaequivalent, zwei Rechenwege.

Gemeldet am 11.09.2026 mit fertiger Gegenprobe: gleiche Stelle, nur
`salary_estimated` gedreht, ergab `calculate_score` 3.0 gegen 3.0 und
`fit_analyse` 3.0 gegen 2.0.

Am hiesigen Bestand nachgemessen (2.535 Stellen, Kopie):

    geschaetztes Gehalt   2406
    echte Angabe            60
    ohne Angabe             69
    salary_type stuendlich  12

    Score-Aenderung durch die Neutralisierung: 479 Stellen (18,9 %),
    Abzug median 3,5 / max 8,0, davon 230 auf 0.

**Von den 230, die auf 0 fallen, haben 213 keine Beschreibung.** Sie
tragen danach den `unbewertet`-Marker aus #756 — und das ist richtig
so: ihre Punkte stammten aus einer erfundenen Gehaltszahl plus einem
Titeltreffer, bewertet war daran nichts. Der Fix macht sie ehrlich,
statt sie zu verstecken.

## Was die Gegenprobe ueber diese Tests sagt

Mit abgeschalteter Neutralisierung wurden **nur 2 der 17 Tests rot** —
und der Gleichheits-Test, also das woertliche Akzeptanzkriterium des
Melders, blieb GRUEN. Das ist kein Mangel, sondern die Folge des
Nadeloehrs: beide Wege fragen dieselbe Funktion und sind sich deshalb
auch dann einig, wenn sie gemeinsam falsch liegen.

Die Gleichheit belegt also die AUFLOESUNG der Divergenz, nicht die
Richtigkeit der Regel. Dafuer stehen die Einzelfaelle daneben. Das ist
#931 MERKE 3 an einer neuen Stelle: **ein Test, der ein Kriterium
woertlich nachbaut, prueft nicht automatisch die Sache dahinter.**
"""
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.job_scraper import calculate_score, fit_analyse  # noqa: E402
from bewerbungs_assistent.services import gehalt_vergleich as gv  # noqa: E402


KRITERIEN = {
    "keywords_muss": ["plm"], "keywords_kann": [], "keywords_ausschluss": [],
    "min_gehalt": 40000, "min_tagessatz": 500, "min_stundensatz": 20,
    "gewichtung": {"gehalt": 1},
}


def _stelle(**extra) -> dict:
    basis = {
        "title": "PLM Engineer", "company": "Beispiel GmbH",
        "description": "PLM " * 40, "location": "Hamburg",
        "employment_type": "festanstellung", "salary_type": "jaehrlich",
        "salary_estimated": False,
    }
    basis.update(extra)
    return basis


def _gehalts_faktor(job: dict) -> dict:
    erg = fit_analyse(job, KRITERIEN)
    return {k: v for k, v in erg["factors"].items() if "ehalt" in k}


# ------------------------------------------------ Das Akzeptanzkriterium


@pytest.mark.parametrize("art,betrag", [
    ("jaehrlich", 50000),
    ("taeglich", 600),
    ("stuendlich", 25),
])
@pytest.mark.parametrize("geschaetzt", [False, True])
def test_1017_beide_rechenwege_sind_sich_einig(art, betrag, geschaetzt):
    """Sechs Kombinationen, zwei Wege, dieselbe Zahl.

    Das ist woertlich das dritte Akzeptanzkriterium des Melders. Es
    prueft NICHT eine erwartete Punktzahl, sondern die Gleichheit — eine
    Liste erwarteter Zahlen wuerde beim naechsten Gewichtungs-Umbau
    falsch, die Gleichheit bleibt richtig.
    """
    job = _stelle(salary_min=betrag, salary_type=art,
                  salary_estimated=geschaetzt)
    assert calculate_score(job, KRITERIEN) == fit_analyse(
        job, KRITERIEN)["total_score"]


def test_1017_geschaetztes_gehalt_bringt_im_basis_score_nichts():
    """Der gemeldete Defekt, als Einzelfall festgehalten.

    Ohne diesen Test bliebe die Gleichheit oben auch dann gruen, wenn
    BEIDE Wege den Bonus wieder vergeben.
    """
    echt = _stelle(salary_min=50000, salary_estimated=False)
    geschaetzt = _stelle(salary_min=50000, salary_estimated=True)
    assert calculate_score(echt, KRITERIEN) > calculate_score(
        geschaetzt, KRITERIEN), (
        "Eine geschaetzte Zahl bringt denselben Bonus wie eine echte.")
    assert _gehalts_faktor(geschaetzt) == {
        "Gehalt: nur Schaetzung — neutral (#827)": 0}


def test_1017_stundensatz_wird_gegen_den_stundensatz_verglichen():
    """25 EUR/Stunde gegen min_stundensatz 20 — nicht gegen 40.000."""
    job = _stelle(salary_min=25, salary_type="stuendlich")
    assert _gehalts_faktor(job) == {"Gehalt passt zu Erwartung": 1}
    knapp = _stelle(salary_min=12, salary_type="stuendlich")
    assert "Gehalt passt zu Erwartung" not in _gehalts_faktor(knapp)


def test_1017_ohne_gehaltsangabe_gibt_es_keinen_befund():
    """Kein Gehalt ist kein Risiko und kein Bonus, sondern eine Luecke."""
    assert _gehalts_faktor(_stelle(salary_min=None)) == {}


# ------------------------------------- Drei Zustaende, nicht zwei (#989)


def test_1017_geschaetzt_ist_nicht_ohne_angabe():
    """Der Kern von #989 an dieser Dimension.

    Beide bringen null Punkte und bedeuten das Gegenteil voneinander:
    einmal steht eine Zahl da, der man nicht trauen kann, einmal steht
    gar keine. Ein Aufrufer, der das nicht unterscheiden kann, baut die
    naechste stille Null.
    """
    geschaetzt = gv.vergleich(_stelle(salary_min=50000,
                                      salary_estimated=True), KRITERIEN)
    ohne = gv.vergleich(_stelle(salary_min=None), KRITERIEN)
    assert geschaetzt["stand"] == gv.GESCHAETZT
    assert ohne["stand"] == gv.OHNE_ANGABE
    assert geschaetzt["stand"] != ohne["stand"]
    assert geschaetzt["grund"] and ohne["grund"]


def test_1017_ohne_wunschwert_ist_ein_eigener_zustand():
    """Wer keinen Wunsch gesetzt hat, verdient nicht "zu wenig"."""
    erg = gv.vergleich(_stelle(salary_min=50000),
                       {"gewichtung": {"gehalt": 1}})
    assert erg["stand"] == gv.OHNE_WUNSCH
    assert erg["erfuellt"] is False
    assert erg["deutlich_darunter"] is False


def test_1017_vergleich_liefert_immer_ein_dict():
    """Nie None — sonst prueft der naechste Aufrufer auf None und
    vergisst einen Zweig."""
    for job in (_stelle(salary_min=None), _stelle(salary_min=0),
                _stelle(salary_min="kaputt"), {}):
        erg = gv.vergleich(job, KRITERIEN)
        assert isinstance(erg, dict) and erg["stand"] in (
            gv.VERGLEICHBAR, gv.GESCHAETZT, gv.OHNE_ANGABE, gv.OHNE_WUNSCH)


def test_1017_rueckfallkette_beim_stundensatz():
    """Ohne min_stundensatz gilt der Tagessatz, dann das Jahresgehalt.

    Die Kette gibt es seit #920 in `fit_analyse`; die meisten Profile
    pflegen keinen Stundensatz, ohne sie waere der Zweig fuer fast alle
    wirkungslos.
    """
    job = _stelle(salary_min=100, salary_type="stuendlich")
    nur_tag = gv.vergleich(job, {"min_tagessatz": 500,
                                 "gewichtung": {"gehalt": 1}})
    assert nur_tag["wunsch_jahr"] == 500 * gv.TAGE_PRO_JAHR
    nur_jahr = gv.vergleich(job, {"min_gehalt": 40000,
                                  "gewichtung": {"gehalt": 1}})
    assert nur_jahr["wunsch_jahr"] == 40000


def test_1017_die_einheit_steht_im_text():
    """`job_text` und `wunsch_text` tragen die Einheit — genau die
    Luecke, die Befund 3 im Dashboard meldet."""
    for art, betrag, einheit in (("jaehrlich", 50000, "EUR/Jahr"),
                                 ("taeglich", 600, "EUR/Tag"),
                                 ("stuendlich", 25, "EUR/Stunde")):
        erg = gv.vergleich(_stelle(salary_min=betrag, salary_type=art),
                           KRITERIEN)
        assert einheit in erg["job_text"], erg


# ------------------------------------------------------------ Guards


def test_1017_kein_rechenweg_haelt_eine_eigene_fassung():
    """Der Guard ZAEHLT keine Fundstellen, er verbietet die Bauform.

    Gesucht wird die Rechnung selbst — ein Wunschwert im Rechenweg —
    ausserhalb des Nadeloehrs. Eine Zaehlung haette die naechste Fassung
    durchgelassen (v1.7.59 MERKE 1).
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "job_scraper"
              / "__init__.py").read_text(encoding="utf-8")
    ohne_kommentar = "\n".join(
        z for z in quelle.split("\n") if not z.strip().startswith("#"))
    for verboten in ("min_tagessatz", "min_stundensatz", "pref_yearly"):
        assert verboten not in ohne_kommentar, (
            f"{verboten} steht wieder im Rechenweg statt im Nadeloehr.")


def test_1017_beide_rechenwege_rufen_das_nadeloehr_auf():
    """DoD 8c: geschrieben ist nicht aufgerufen."""
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "job_scraper"
              / "__init__.py").read_text(encoding="utf-8")
    assert quelle.count("gehalt_vergleich") >= 2, (
        "Einer der beiden Rechenwege geht am Nadeloehr vorbei.")


def test_1017_die_drei_minimum_felder_nennen_ihre_einheit():
    """Befund 3: die Einheit stand nur in der MCP-Ebene.

    Geprueft wird die BESCHRIFTUNG, nicht ihre Position — ein Feld, das
    "Min. Gehalt" heisst, laesst offen, ob ein Jahres- oder ein
    Monatsgehalt erwartet wird, und der Wert geht ungeprueft ins
    Scoring.
    """
    jsx = (_repo() / "frontend" / "src" / "pages"
           / "ProfilePage.jsx").read_text(encoding="utf-8")
    for beschriftung in ('label="Min. Gehalt (EUR/Jahr, brutto)"',
                         'label="Min. Tagessatz (EUR/Tag)"',
                         'label="Min. Stundensatz (EUR/Stunde)"'):
        assert beschriftung in jsx, f"{beschriftung} fehlt im Formular."


def test_1017_stundensatz_wird_als_bezahlung_erklaert():
    """"Min. Stundensatz" laesst beides zu — Bezahlung oder Arbeitszeit.

    Ein Feld fuer gewuenschte Wochenstunden gibt es in PBP gar nicht,
    aber das weiss man beim Ausfuellen nicht.
    """
    jsx = (_repo() / "frontend" / "src" / "pages"
           / "ProfilePage.jsx").read_text(encoding="utf-8")
    assert "nicht die Wochenarbeitszeit" in jsx


def test_1017_der_regler_neutralisiert_schaetzungen_weiterhin():
    """Der dritte Rechenweg (#827) behaelt seine Prozent-Logik.

    Er wurde bewusst NICHT umgebaut: er rechnet in Prozentschritten vom
    Wunsch statt mit einer Ja/Nein-Schwelle, und seine Zahlen wuerden
    sich durch eine andere Rueckfallkette verschieben. Geprueft wird
    deshalb nur die Regel, die alle drei teilen muessen.
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "services"
              / "scoring_service.py").read_text(encoding="utf-8")
    assert "salary_estimated" in quelle
