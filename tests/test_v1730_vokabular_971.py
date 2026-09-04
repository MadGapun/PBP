"""Tests fuer v1.7.30 — #971: Kompetenzen aus dem Bestand statt aus einer Liste.

Die Skill-Extraktion wurde in v1.7.24 (#963) von "jedes
grossgeschriebene Wort" auf eine Positivliste umgestellt. Das war die
richtige Richtung — die hinterlegte Liste deckt aber nur ein Berufsfeld
ab. Gemessen an sechs Lebenslaeufen erkannte sie fuer Pflege, Erziehung
und Grafik NULL Begriffe; die drei Treffer bei den uebrigen fielen
durch die Abkuerzungs-Regel an, nicht durch die Liste.

Dieselbe Umkehr wie bei `issue_text_pruefen` (#946) und bei den
Berufsbezeichnungen (#969): nicht gegen eine gepflegte Liste pruefen,
sondern gegen den vorhandenen Bestand. Eine Liste ist immer nur so gut
wie ihre letzte Pflege; ein Bestand waechst von allein, und zwar in
genau dem Feld, in dem gesucht wird.
"""
import pytest

from bewerbungs_assistent.services.stellen_skills import (
    MAX_ANTEIL,
    MIN_ANZEIGEN,
    aus_profil,
    extrahiere_skills,
    lerne_aus_bestand,
    vokabular,
)

# Acht Pflege-Anzeigen, wie sie im Bestand stehen wuerden. Fiktive
# Arbeitgeber, echte Fachsprache.
PFLEGE = [
    ("Pflegefachkraft Intensivstation",
     "Grund- und Behandlungspflege, Beatmung, Vitalparameter, "
     "Dokumentation nach Pflegestandards. Schichtdienst, "
     "Fachweiterbildung Intensivpflege. Motiviertes Team, Fortbildungen."),
    ("Pflegefachkraft Anaesthesie",
     "Ueberwachung der Vitalparameter, Beatmung, Assistenz bei Narkosen, "
     "Dokumentation. Schichtdienst. Unser Team freut sich."),
    ("Gesundheits- und Krankenpflegerin",
     "Behandlungspflege, Wundmanagement, Dokumentation, Betreuung der "
     "Patienten. Schichtdienst. Fortbildungen."),
    ("Altenpflegerin Wohnbereich",
     "Grundpflege und Behandlungspflege, Pflegeplanung, Dokumentation, "
     "Angehoerigenarbeit. Fortbildungen."),
    ("Pflegefachkraft ambulant",
     "Grundpflege, Wundmanagement, Medikamentengabe, Dokumentation. "
     "Fuehrerschein. Team."),
    ("Intensivpflegekraft",
     "Beatmung, Monitoring, Vitalparameter, Notfallmanagement, "
     "Dokumentation. Schichtdienst."),
    ("Pflegedienstleitung",
     "Dienstplanung, Pflegeplanung, Qualitaetsmanagement, Fuehrung, "
     "Dokumentation."),
    ("Praxisanleiterin Pflege",
     "Anleitung von Auszubildenden, Pflegeplanung, Dokumentation, "
     "Fortbildungen. Team."),
]


@pytest.fixture
def bestand(tmp_db):
    tmp_db.create_profile("Nutzerin", "n@example.com")
    tmp_db.save_jobs([
        {"hash": f"v971_{i}", "title": t, "company": "Musterklinik",
         "url": f"https://example.com/{i}", "source": "manuell",
         "description": d}
        for i, (t, d) in enumerate(PFLEGE)
    ])
    return tmp_db


# ── Aus dem Bestand lernen ───────────────────────────────────────────

def test_971_fachbegriffe_werden_gelernt(bestand):
    """Der Kern: ein Berufsfeld, das die kuratierte Liste nicht kennt."""
    gelernt = lerne_aus_bestand(bestand)
    for pflicht in ("beatmung", "vitalparameter", "behandlungspflege",
                    "pflegeplanung"):
        assert pflicht in gelernt, sorted(gelernt)


def test_971_floskeln_werden_nicht_gelernt(bestand):
    """"Team" und "Fortbildungen" stehen in jeder zweiten Anzeige — das
    ist die Textsorte, nicht das Berufsfeld."""
    gelernt = lerne_aus_bestand(bestand)
    for floskel in ("team", "fortbildungen", "erfahrung", "kenntnisse",
                    "aufgaben", "unternehmen"):
        assert floskel not in gelernt, floskel


def test_971_einzelner_treffer_ist_zufall(bestand):
    """Ein Begriff aus genau einer Anzeige sagt nichts."""
    gelernt = lerne_aus_bestand(bestand)
    assert "narkosen" not in gelernt
    assert "fuehrerschein" not in gelernt


def test_971_zu_kleiner_bestand_lernt_nichts(tmp_db):
    """Aus zwei Anzeigen laesst sich keine Haeufigkeit ableiten — dann
    lieber nichts als Rauschen."""
    tmp_db.create_profile("Nutzerin", "n@example.com")
    tmp_db.save_jobs([
        {"hash": "klein1", "title": "Pflegefachkraft",
         "company": "Musterklinik", "url": "https://example.com/1",
         "source": "manuell", "description": "Beatmung und Dokumentation."},
    ])
    assert lerne_aus_bestand(tmp_db) == set()


def test_971_leerer_bestand_bricht_nicht(tmp_db):
    tmp_db.create_profile("Nutzerin", "n@example.com")
    assert lerne_aus_bestand(tmp_db) == set()


def test_971_schwellen_sind_benannt():
    assert MIN_ANZEIGEN >= 2, "Einmal ist Zufall"
    assert 0 < MAX_ANTEIL < 1, "Was ueberall steht, ist Floskel"


# ── Aus dem Profil ───────────────────────────────────────────────────

def test_971_profilbegriffe_zaehlen():
    """Die verlaesslichste Quelle: was der Mensch selbst aufgeschrieben
    hat — und die einzige, die auf gar kein Feld kalibriert ist."""
    begriffe = aus_profil({
        "skills": [{"name": "Intensivpflege"}, {"name": "Beatmung"}],
        "positions": [{"title": "Pflegefachkraft"}],
    })
    assert "intensivpflege" in begriffe
    assert "pflegefachkraft" in begriffe


def test_971_leeres_profil_ergibt_nichts():
    assert aus_profil({}) == set()
    assert aus_profil(None) == set()


# ── Die Wirkung ──────────────────────────────────────────────────────

ANZEIGE = ("Pflegefachkraft (m/w/d) Intensivstation. Aufgaben: Beatmung, "
           "Monitoring der Vitalparameter, Behandlungspflege und "
           "Dokumentation. Wir bieten Fortbildungen und ein Team.")


def test_971_ohne_vokabular_wie_bisher():
    """Die Ausgangslage, die das Issue beschreibt."""
    assert extrahiere_skills(ANZEIGE) == []


def test_971_mit_vokabular_kommen_echte_begriffe(bestand):
    erg = extrahiere_skills(ANZEIGE, vokabular(db=bestand))
    assert len(erg) >= 4, erg
    for pflicht in ("beatmung", "vitalparameter", "behandlungspflege"):
        assert pflicht in [x.lower() for x in erg], erg


def test_971_floskeln_bleiben_auch_dann_draussen(bestand):
    erg = [x.lower() for x in extrahiere_skills(ANZEIGE, vokabular(db=bestand))]
    assert "team" not in erg
    assert "fortbildungen" not in erg
    assert "aufgaben" not in erg


def test_971_kuratierte_liste_bleibt_startwert():
    """Sie ist fuer ihr Feld richtig und kostet nichts — sie ist nur
    nicht mehr die Grenze."""
    v = vokabular()
    assert "teamcenter" in v and "python" in v
    assert "systems engineering" in v


def test_971_technisches_feld_bleibt_unveraendert():
    """Gegenprobe: die Erweiterung darf das Feld nicht kaputtmachen, fuer
    das die Liste gebaut wurde."""
    text = ("Senior PLM Consultant. Teamcenter Customizing, Requirements "
            "Engineering, Python-Skripte, IEC 62304.")
    erg = [x.lower() for x in extrahiere_skills(text)]
    for pflicht in ("teamcenter", "requirements engineering", "python"):
        assert pflicht in erg, erg


def test_971_gap_analyse_nutzt_das_vokabular():
    """Der beste Baustein nuetzt nichts, wenn ihn niemand aufruft
    (DoD 8c)."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "tools" / "analyse.py").read_text(encoding="utf-8")
    assert "vokabular(db=db, profil=profile)" in quelle
    assert "extrahiere_skills(_txt, _vok)" in quelle
