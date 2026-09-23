"""#1074 — die Einordnung las nur den Lebenslauf.

Gemeldet am 23.09.2026 mit `profil_einordnung()` aus #1070: 19 Jahre
Einzelhandel, zuletzt Filialleiter, zwei Selbstaendigkeiten bis 2018,
seit 2019 angestellt. Gesucht: Sachbearbeitung im Buero, Praeferenz
Festanstellung. Ergebnis: Feld Handel, Niveau Experte, Form
freiberuflich — die Boersen des Berufs, aus dem der Mensch heraus will,
plus Freelance- und Konzern-Quellen.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import berufsfeld  # noqa: E402
from bewerbungs_assistent.services import profile_classifier as pc  # noqa: E402

ZIEL = ["Sachbearbeiter", "Sachbearbeitung", "Bueromanagement"]


def _quereinsteiger(stellentyp="festanstellung", summary=""):
    return {
        "summary": summary,
        "preferences": {"stellentyp": stellentyp},
        "suggested_job_titles": [],
        "positions": [
            {"title": "Filialleiter Einzelhandel", "start_date": "2019-01-01",
             "employment_type": "festanstellung", "is_current": 1},
            {"title": "Stellvertretender Filialleiter Einzelhandel",
             "start_date": "2018-06-01", "end_date": "2018-12-31",
             "employment_type": "festanstellung"},
            {"title": "Selbstaendiger Dienstleister", "start_date": "2012-01-01",
             "end_date": "2018-05-31", "employment_type": "freelance"},
            {"title": "Selbstaendiger Unternehmer", "start_date": "2008-01-01",
             "end_date": "2011-12-31", "employment_type": "freelance"},
            {"title": "Verkaeufer im Einzelhandel", "start_date": "2007-01-01",
             "end_date": "2007-12-31", "employment_type": "festanstellung"},
        ],
        "skills": [{"name": "Kassenfuehrung"}, {"name": "Warenwirtschaft"}],
        "education": [],
    }


# ===== Form ==============================================================

def test_1074_eine_2018_beendete_selbststaendigkeit_macht_keine_freiberufler():
    ein = berufsfeld.einordnen(_quereinsteiger(stellentyp="beides"), ZIEL)
    assert "freiberuflich" not in ein["formen"]
    assert ein["form"] == "festanstellung"
    assert ein["form_beleg"] == "aktuelle_stationen"


def test_1074_die_praeferenz_geht_vor():
    ein = berufsfeld.einordnen(_quereinsteiger(), ZIEL)
    assert ein["formen"] == ["festanstellung"]
    assert ein["form_beleg"] == "praeferenz"


def test_1074_festanstellung_wird_ueberhaupt_vergeben():
    """`festanstellung` stand in FORM_QUELLEN, vergeben hat es nichts."""
    ein = berufsfeld.einordnen(_quereinsteiger(stellentyp="beides"))
    assert "festanstellung" in ein["formen"]


def test_1074_eine_laufende_selbststaendigkeit_zaehlt_weiter():
    """Die Gegenrichtung (#1070): der freiberufliche Entwickler bleibt es."""
    prof = {"positions": [{"title": "Freelance Senior Software Developer",
                           "start_date": "2012-01-01"}],
            "skills": [{"name": "Python"}]}
    assert "freiberuflich" in berufsfeld.einordnen(prof)["formen"]


def test_1074_praeferenz_freelance_schaltet_die_boersen_dazu():
    ein = berufsfeld.einordnen(_quereinsteiger(stellentyp="freelance"), ZIEL)
    assert ein["formen"] == ["freiberuflich"]


# ===== Feld ==============================================================

def test_1074_das_ziel_bestimmt_das_feld():
    ein = berufsfeld.einordnen(_quereinsteiger(), ZIEL)
    assert ein["feld"] == "verwaltung"
    assert ein["feld_beleg"] == "ziel"
    assert ein["lebenslauf_feld"] == "handel"
    assert ein["quereinstieg"] is True


def test_1074_das_kurzprofil_zaehlt_als_ziel():
    ein = berufsfeld.einordnen(_quereinsteiger(
        summary="Quereinsteiger fuer Sachbearbeitung und Bueromanagement"))
    assert ein["feld"] == "verwaltung"


def test_1074_ohne_ziel_bleibt_es_beim_lebenslauf():
    ein = berufsfeld.einordnen(_quereinsteiger())
    assert ein["feld"] == "handel"
    assert ein["feld_beleg"] == "lebenslauf"
    assert ein["quereinstieg"] is False


def test_1074_kontinuitaet_ist_kein_quereinstieg():
    """Gemessen am 23.09.2026: ein Ziel mit IT-Allerweltswoertern ("Data",
    "Engineer") machte einen PLM-Berater zum Quereinsteiger, solange die
    Mehrheit im Ziel entschied. Kommt das bisherige Feld im Ziel vor,
    bleibt es."""
    prof = {"positions": [{"title": "PLM Consultant Konstruktion",
                           "start_date": "2010-01-01"}],
            "skills": [{"name": "CAD"}, {"name": "PDM"}],
            "summary": "Engineer fuer Data und Architect im PLM-Umfeld"}
    ein = berufsfeld.einordnen(prof, ["PLM", "Data Governance"])
    assert ein["feld"] == "ingenieurwesen"
    assert ein["quereinstieg"] is False


# ===== Niveau ============================================================

def test_1074_quereinstieg_deckelt_die_fuehrungsstufe():
    ein = berufsfeld.einordnen(_quereinsteiger(), ["Bueromanagement"])
    assert ein["niveau"] == "fachkraft"
    assert ein["niveau_beleg"] == "quereinstieg"


def test_1074_eine_stufe_im_ziel_gilt():
    ein = berufsfeld.einordnen(_quereinsteiger(), ["Sachbearbeiter"])
    assert ein["niveau"] == "fachkraft"
    assert ein["niveau_beleg"] == "ziel"


def test_1074_ohne_quereinstieg_bleibt_die_stufe():
    ein = berufsfeld.einordnen(_quereinsteiger())
    assert ein["niveau"] == "experte"


# ===== Wirkung auf die Empfehlung ========================================

def test_1074_die_empfehlung_folgt_dem_ziel():
    out = pc.recommend_sources(_quereinsteiger(), ZIEL)
    q = set(out["recommended"])
    assert "jobware" in q, "Die Quelle des Ziel-Felds fehlt"
    assert not q & {"freelance_de", "freelancermap", "gulp"}
    assert not q & {"workday_dax", "greenhouse"}
    assert out["type"] != "freelance"


def test_1074_der_grund_nennt_den_quereinstieg():
    out = pc.detect_profile_type(_quereinsteiger(), ZIEL)
    assert any("Quereinstieg" in r for r in out["reasons"])
    assert any("Job-Praeferenz" in r for r in out["reasons"])


def test_1074_praeferenz_zaehlt_als_beleg_der_konfidenz():
    """Die Konfidenz kannte nur den Beleg `titel` — eine Form aus der
    Praeferenz galt damit als unbelegt."""
    prof = {"preferences": {"stellentyp": "freelance"},
            "positions": [{"title": "Softwareentwickler", "start_date": "2012-01-01"}],
            "skills": [{"name": "Python"}]}
    out = pc.detect_profile_type(prof)
    assert out["type"] == "freelance"
    assert out["form_beleg"] == "praeferenz"
    assert out["confidence"] >= 0.8
