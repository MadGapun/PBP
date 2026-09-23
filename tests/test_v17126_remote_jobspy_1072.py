"""#1072 — JobSpy uebernahm `is_remote` ungeprueft.

JobSpy setzt `is_remote=True`, sobald "remote" irgendwo im Text steht,
und `False` in jedem anderen Fall. PBP machte daraus "vollstaendig
remote" bzw. "vor Ort". Belegter Fall vom 22.09.2026: "Hybrides
Arbeitsmodell mit bis zu 50 % remote work im Monat" als remote gefuehrt,
die Entfernung fiel weg.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest  # noqa: E402

from bewerbungs_assistent.job_scraper import detect_remote_level  # noqa: E402
from bewerbungs_assistent.services import remote_jobspy  # noqa: E402

BELEG = ("Wir bieten ein Hybrides Arbeitsmodell mit bis zu 50 % remote work "
         "im Monat und ein Team in Hamburg.")


def test_1072_der_belegfall_ist_hybrid():
    assert remote_jobspy.bestimmen("Expert HR Business Partnering", "Hamburg",
                                   BELEG, is_remote=True) == "hybrid"


@pytest.mark.parametrize("text", [
    "bis zu 50 % remote", "40% Homeoffice moeglich",
    "2 Tage Homeoffice pro Woche", "3 Tage pro Woche im Homeoffice",
    "1-2 Tage mobil arbeiten"])
def test_1072_ein_anteil_unter_hundert_ist_hybrid(text):
    assert detect_remote_level(text) == "hybrid"


@pytest.mark.parametrize("text", ["100% remote", "vollstaendig remote",
                                  "Full remote, deutschlandweit"])
def test_1072_vollstaendig_remote_bleibt_remote(text):
    """Die Gegenrichtung: der Anteil-Filter darf 100 % nicht treffen."""
    assert detect_remote_level(text) == "remote"


def test_1072_false_heisst_unbekannt_nicht_vor_ort():
    assert remote_jobspy.bestimmen("Sachbearbeitung", "Hamburg",
                                   "Ein Text ohne Aussage zum Ort.",
                                   is_remote=False) == "unbekannt"


def test_1072_ein_hinweis_ohne_textbeleg_wird_hybrid():
    """Indeeds Attribut "Hybrid remote" setzt ebenfalls `is_remote=True`."""
    assert remote_jobspy.bestimmen("Entwickler", "Deutschland",
                                   "Ein Text ohne Aussage.",
                                   is_remote=True) == "hybrid"


def test_1072_ein_starkes_wort_im_text_bleibt_remote():
    assert remote_jobspy.bestimmen("Entwickler", "Deutschland",
                                   "Remote-first team, work from home.",
                                   is_remote=True) == "remote"


def test_1072_der_ganze_text_zaehlt_nicht_nur_die_ersten_500_zeichen():
    lang = "Einleitung. " * 80 + "Hybrides Arbeiten ist moeglich."
    assert len(lang) > 500
    # Ohne JobSpy-Hinweis: sonst ergaebe schon die Rueckfallregel "hybrid",
    # und der Test pruefte sie statt des Textes (Gegenprobe v1.7.126).
    assert remote_jobspy.bestimmen("x", "Hamburg", lang,
                                   is_remote=None) == "hybrid"


def test_1072_der_adapter_nutzt_die_neue_regel():
    from bewerbungs_assistent.job_scraper import jobspy_source
    zeile = {"title": "Expert HR Business Partnering", "company": "Muster AG",
             "location": "Hamburg", "description": BELEG,
             "job_url": "https://example.com/1", "is_remote": True}
    job = jobspy_source._map_row(zeile, "indeed")
    assert job["remote_level"] == "hybrid"


def test_1072_bestand_wird_einmal_nachgezogen(tmp_db):
    db = tmp_db
    db.save_profile({"name": "Test"})
    db.save_jobs([
        {"hash": "r1072a", "title": "Expert HR", "company": "Muster AG",
         "location": "Hamburg", "url": "https://example.com/a",
         "source": "jobspy_indeed", "description": BELEG,
         "remote_level": "remote"},
        {"hash": "r1072b", "title": "Sachbearbeitung", "company": "Muster AG",
         "location": "Hamburg", "url": "https://example.com/b",
         "source": "jobspy_indeed", "description": "Kein Wort zum Ort.",
         "remote_level": "vor_ort"},
        {"hash": "r1072c", "title": "Andere Quelle", "company": "Muster AG",
         "location": "Hamburg", "url": "https://example.com/c",
         "source": "bundesagentur", "description": BELEG,
         "remote_level": "remote"},
    ])
    db.set_setting(remote_jobspy.MARKER, "")
    erg = remote_jobspy.bestand_nachziehen(db)
    assert erg["geaendert"] == {"remote->hybrid": 1, "vor_ort->unbekannt": 1}

    def stufe(h):
        return db.get_job(db.resolve_job_hash(h))["remote_level"]
    assert stufe("r1072a") == "hybrid"
    assert stufe("r1072b") == "unbekannt"
    assert stufe("r1072c") == "remote", "andere Quellen bleiben unberuehrt"
    assert remote_jobspy.bestand_nachziehen(db)["status"] == "schon_erledigt"
