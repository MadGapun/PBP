"""Tests fuer v1.7.17 — #918 Defekt 2: Hochschulabschluss-Erkennung.

Zwei aufeinanderfolgende Bewertungen lagen falsch, mit umgekehrtem
Vorzeichen: eine Anzeige OHNE Abschluss-Anforderung loeste den
ATS-Risiko-Alarm aus (die LinkedIn-Bewerberstatistik im Datensatz redet
ueber ANDERE Bewerber), waehrend "Educational Background: Bachelor's
degree" gar nicht erkannt wurde. Der Nutzer hat keinen Hochschul-
abschluss (staatlich gepruefter Techniker) — beide Richtungen kosten
ihn etwas: der Falsch-Alarm schreckt von passenden Stellen ab, das
Falsch-Negativ verschweigt ein echtes ATS-Risiko.

Fixtures nach den beiden realen Anzeigen (fiktive Firmen, DoD-9).
"""
import pytest

from bewerbungs_assistent.job_scraper import _detect_degree_required, fit_analyse


# Anzeige OHNE Abschluss-Anforderung, ABER mit Bewerberstatistik im
# Datensatz (Sortiertechnik Nord-Fall).
OHNE_ANFORDERUNG = """\
Functional Business Consultant — Engineering and PLM

Your tasks:
- Strong understanding of Engineering / R&D processes
- Support of PLM rollouts in an international environment
- Close cooperation with the business units

Your profile:
- Several years of experience in PLM consulting
- Fluent English

---
Bewerberfeld laut Portal: 21 % haben den Abschluss Master,
17 % Bachelor der Ingenieurswissenschaften, 20 % Berufseinsteiger.
"""

# Anzeige MIT echter Anforderung in englischer Formulierung
# (Hoertechnik Sued-Fall).
MIT_ANFORDERUNG = """\
Transformation Director

Requirements:
- Educational Background: Bachelor's degree in Business, Management,
  Engineering, or a related field. A Master's degree or MBA is preferred.
- Ten years of experience in transformation programs
"""

# Gegenprobe: Anforderung mit Oeffnungsklausel — ein Techniker-Abschluss
# erfuellt sie, also KEIN Risiko.
MIT_OEFFNUNGSKLAUSEL = """\
Projektleiter PLM

Dein Profil:
- Abgeschlossenes Studium im Bereich Maschinenbau oder eine
  vergleichbare Ausbildung mit mehrjaehriger Berufserfahrung
- Erfahrung in der Prozessberatung
"""


def test_918_bewerberstatistik_loest_keinen_alarm_aus():
    """DER Falsch-Positiv-Fall: die Statistik redet ueber ANDERE Bewerber."""
    assert _detect_degree_required(OHNE_ANFORDERUNG) is False


def test_918_englische_anforderung_wird_erkannt():
    """DER Falsch-Negativ-Fall: 'Educational Background: Bachelor's degree'."""
    assert _detect_degree_required(MIT_ANFORDERUNG) is True


def test_918_oeffnungsklausel_entwertet_die_anforderung():
    assert _detect_degree_required(MIT_OEFFNUNGSKLAUSEL) is False


def test_918_deutsche_anforderung_bleibt_erkannt():
    """Regression: die bestehende Erkennung darf nicht schwaecher werden."""
    assert _detect_degree_required(
        "Dein Profil: Abgeschlossenes Studium der Informatik") is True


@pytest.mark.parametrize("text,erwartet", [
    (OHNE_ANFORDERUNG, False),
    (MIT_ANFORDERUNG, True),
    (MIT_OEFFNUNGSKLAUSEL, False),
])
def test_918_fit_analyse_meldet_konsistent(text, erwartet):
    """Das Flag im fit_analyse-Result und der Risiko-Hinweis haengen
    zusammen — kein Alarm ohne Anforderung, kein Schweigen mit."""
    job = {"title": "Consultant", "description": text,
           "employment_type": "festanstellung"}
    criteria = {"keywords_muss": [], "keywords_plus": [],
                "keywords_minus": [], "keywords_ausschluss": [],
                "_profile_skills": []}
    res = fit_analyse(job, criteria)
    assert res["hochschulabschluss_gefordert"] is erwartet, res["factors"]
    alarm = [r for r in res["risks"] if "HOCHSCHULABSCHLUSS" in r]
    assert bool(alarm) is erwartet, res["risks"]
