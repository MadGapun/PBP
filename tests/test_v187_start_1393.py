"""#1393: Startschritte messbar, "gestartet" erst nach /api/health, Verknuepfung endet nicht stumm.

Gemessen (isolierte Datenbank, 223 nicht aufloesbare Dokumentpfade): die Pfadpruefung
kostet 0,05 s, der ganze Start der Datenbank 0,15 s, der Import des Servers ~4 s.
Die Pfadpruefung ist NICHT die Ursache der Minuten; belegbar wird der Rest erst durch
Zeiten im Log.
"""
import logging
import os
import tempfile

import pytest


@pytest.fixture
def server():
    """Der Server-Import oeffnet eine Datenbank: nie ohne BA_DATA_DIR (QA-Isolation)."""
    import importlib
    tmpdir = tempfile.mkdtemp(prefix="pbp_start1393_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv
    importlib.reload(_srv)
    assert str(tmpdir) in str(_srv.db.db_path), f"DB nicht isoliert: {_srv.db.db_path}"
    yield _srv
    _srv.db.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture
def db_mit_kaputten_pfaden(tmp_path, monkeypatch):
    monkeypatch.setenv("BA_DATA_DIR", str(tmp_path))
    from bewerbungs_assistent import database
    db = database.Database()
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    conn = db.connect()
    pid = conn.execute("SELECT id FROM profile LIMIT 1").fetchone()
    pid = pid[0] if pid else "p1"
    for i in range(5):
        conn.execute(
            "INSERT INTO documents (id, profile_id, filename, filepath, doc_type) VALUES (?,?,?,?,?)",
            (f"d{i}", pid, f"a{i}.pdf", rf"C:\nicht\da\a{i}.pdf", "anschreiben"))
    conn.commit()
    yield db


def test_pfadpruefung_loggt_dauer_und_zahlen(db_mit_kaputten_pfaden, caplog):
    with caplog.at_level(logging.INFO, logger="bewerbungs_assistent.database"):
        db_mit_kaputten_pfaden._repair_document_paths()
    zeilen = [r.getMessage() for r in caplog.records if "Startschritt Dokumentpfade" in r.getMessage()]
    assert zeilen, caplog.text
    assert "5 nicht auffindbar" in zeilen[0] and " s" in zeilen[0]


def test_datenbankstart_loggt_dauer(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("BA_DATA_DIR", str(tmp_path))
    from bewerbungs_assistent import database
    db = database.Database()
    assert str(tmp_path) in str(db.db_path)
    with caplog.at_level(logging.INFO, logger="bewerbungs_assistent.database"):
        db.initialize()
    assert any("Startschritt Datenbank" in r.getMessage() for r in caplog.records)


def test_gestartet_erst_nach_antwort_von_health(server, caplog):
    with caplog.at_level(logging.INFO, logger=server.logger.name):
        assert server.dashboard_bereit_melden(8299, warte=lambda port, frist: True) is True
    texte = [r.getMessage() for r in caplog.records]
    assert any("Web Dashboard gestartet" in t and "antwortet" in t for t in texte)


def test_haengender_webteil_wird_selbst_gemeldet(server, caplog):
    with caplog.at_level(logging.INFO, logger=server.logger.name):
        assert server.dashboard_bereit_melden(8299, warte=lambda port, frist: False) is False
    texte = [r.getMessage() for r in caplog.records]
    assert not any("Web Dashboard gestartet" in t for t in texte)
    assert any(r.levelno == logging.WARNING and "antwortet nach" in r.getMessage() and "nicht" in r.getMessage()
               for r in caplog.records)


def test_startweg_loggt_nicht_mehr_vor_der_antwort(server):
    import inspect
    q = inspect.getsource(server.dashboard_im_hintergrund_starten)
    assert 'logger.info("Web Dashboard gestartet' not in q
    assert "dashboard_bereit_melden" in q or "_bereit_melden_starten" in q


def test_verknuepfung_meldet_ende_im_log_und_sichtbar(caplog):
    from bewerbungs_assistent.services import start_meldung
    gezeigt = []
    with caplog.at_level(logging.WARNING):
        start_meldung.start_endet(8200, "belegt", ist_terminal=False, plattform="win32",
                                  box=lambda titel, text: gezeigt.append((titel, text)),
                                  env={})
    assert any("Start endet" in r.getMessage() and "8200" in r.getMessage() for r in caplog.records)
    assert gezeigt and "8200" in gezeigt[0][1]


def test_im_terminal_keine_box_und_in_proben_auch_nicht():
    from bewerbungs_assistent.services import start_meldung
    gezeigt = []
    box = lambda t, x: gezeigt.append(x)
    start_meldung.start_endet(8200, "belegt", ist_terminal=True, plattform="win32", box=box, env={})
    start_meldung.start_endet(8200, "belegt", ist_terminal=False, plattform="win32", box=box,
                              env={"PBP_KEIN_BROWSER": "1"})
    start_meldung.start_endet(8200, "belegt", ist_terminal=False, plattform="linux", box=box, env={})
    assert gezeigt == []


def test_start_dashboard_ruft_die_meldung():
    quelle = open(os.path.join(os.path.dirname(__file__), "..", "start_dashboard.py"),
                  encoding="utf-8").read()
    assert "start_endet(" in quelle
