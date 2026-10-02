"""v1.7.145 — die Protokolldatei nennt keine Arbeitgeber.

Das Fehlerformular bittet um die letzten Zeilen der Protokolldatei, und die
landen in einem OEFFENTLICHEN Issue. Auf INFO stand aber der Firmenname einer
Bewerbung in der Zeile "Auto-linked ... (company: ...)". Ein gut gemeinter
Fehlerbericht haette so einen Arbeitgeber veroeffentlicht.
"""
import logging
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database, get_data_dir
    assert str(tmp_path) in str(get_data_dir()), "Datenordner nicht isoliert"
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Beispiel Person"})
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


class _Sammler(logging.Handler):
    """Eigener Handler: der Logger des Programms leitet nicht an die Wurzel weiter,
    caplog saehe die Zeilen deshalb nicht."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.zeilen = []

    def emit(self, record):
        self.zeilen.append(record.getMessage())


def test_verknuepfen_von_dokumenten_schreibt_keine_firma_ins_protokoll(db):
    firma = "Beispielwerk Quarkhausen"
    # erst das Dokument, dann die Bewerbung: die Anlage verknuepft es selbst
    db.add_document({"filename": f"Anschreiben_{firma}.pdf",
                     "filepath": "", "doc_type": "anschreiben"})
    logger = logging.getLogger("bewerbungs_assistent")
    sammler = _Sammler()
    alter_pegel = logger.level
    logger.addHandler(sammler)
    logger.setLevel(logging.INFO)
    try:
        aid = db.add_application({"company": firma, "title": "Konstrukteur",
                                  "status": "beworben"})
    finally:
        logger.removeHandler(sammler)
        logger.setLevel(alter_pegel)
    zeilen = [z for z in sammler.zeilen if "Auto-linked" in z]
    assert zeilen, "die Verknuepfung wird weiter protokolliert"
    assert all(firma.lower() not in z.lower() for z in zeilen), zeilen
    # und sie hat stattgefunden
    docs = db.connect().execute(
        "SELECT linked_application_id FROM documents").fetchall()
    assert docs and docs[0][0] == aid
