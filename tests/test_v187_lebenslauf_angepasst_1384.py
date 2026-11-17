"""#1384: Angepasster Lebenslauf - Stationen zeitlich, Etikett "Führung", Prüfskript."""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

PROFIL = {
    "name": "Test Person", "email": "t@example.com", "phone": "1", "city": "Musterstadt",
    "summary": "Planer", "education": [],
    "skills": [{"name": "Teamführung", "category": "fuehrung", "level": 4},
               {"name": "SAP PP", "category": "tool", "level": 4}],
    "positions": [   # neueste zuerst, wie das Profil sie liefert
        {"title": "Fertigungsmeister", "company": "Neuer Betrieb GmbH",
         "start_date": "2019-04", "is_current": 1, "tasks": "Schichtleitung\nBerichte schreiben",
         "achievements": "", "technologies": "", "projects": []},
        {"title": "Planer", "company": "Alter Betrieb AG", "start_date": "2012-01",
         "end_date": "2015-12",
         "tasks": "Feinplanung in SAP PP\nTerminierung SAP PP Feinplanung\nKapazitaetsplanung",
         "achievements": "Feinplanung eingefuehrt", "technologies": "SAP PP", "projects": []},
    ],
}
ANZEIGE = "Feinplanung SAP PP Terminierung Kapazitaetsplanung Make-or-Buy"


def _docx_text(tmp_path):
    from docx import Document
    from bewerbungs_assistent.export import generate_tailored_cv_docx
    ziel = tmp_path / "cv.docx"
    generate_tailored_cv_docx(PROFIL, "Planer", ANZEIGE, ziel)
    return [p.text for p in Document(str(ziel)).paragraphs]


def test_stationen_bleiben_umgekehrt_chronologisch(tmp_path):
    zeilen = _docx_text(tmp_path)
    neu = next(i for i, z in enumerate(zeilen) if "Neuer Betrieb" in z)
    alt = next(i for i, z in enumerate(zeilen) if "Alter Betrieb" in z)
    assert neu < alt, "die aktuelle Station muss vor der älteren stehen (ältere trifft mehr Suchwörter)"


def test_innerhalb_der_station_stehen_treffer_zuerst(tmp_path):
    zeilen = _docx_text(tmp_path)
    alt = next(i for i, z in enumerate(zeilen) if "Alter Betrieb" in z)
    aufgaben = [z for z in zeilen[alt:alt + 8] if "Feinplanung" in z or "Kapazitaets" in z]
    assert aufgaben and "Kapazitaetsplanung" not in aufgaben[0], aufgaben


def test_etikett_fuehrung_mit_umlaut(tmp_path):
    zeilen = _docx_text(tmp_path)
    assert any(z.startswith("Führung:") for z in zeilen), zeilen
    assert not any("Fuehrung:" in z for z in zeilen)


def test_pruefskript_liest_export_py_und_sieht_umschrift():
    spec = importlib.util.spec_from_file_location(
        "ui_texte_pruefen", REPO / "scripts" / "ui_texte_pruefen.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert any(p.name == "export.py" for p in m.BACKEND_DATEIEN)
    assert m.pruefen() == [] or not any("export.py" in str(f) for f in m.pruefen())
