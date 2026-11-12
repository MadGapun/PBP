"""#1382: von Claude erzeugte Unterlagen erscheinen unter Dokumente und im ZIP."""
import asyncio
import importlib
import io
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_1382_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db, _srv_mod.mcp, Path(tmpdir)
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def _bewerbung(db, tmp):
    db.save_profile({"name": "Test Person"})
    aid = db.add_application({"title": "Planer", "company": "Musterbetrieb GmbH",
                              "status": "in_vorbereitung"})
    cv = tmp / "lebenslauf_test.docx"
    cv.write_bytes(b"PK-cv")
    anschr = tmp / "anschreiben_test.docx"
    anschr.write_bytes(b"PK-anschreiben")
    return aid, cv, anschr


def _zip(db, aid):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    dash._db = db
    r = TestClient(dash.app).get(f"/api/application/{aid}/export.zip?dokumente=1")
    assert r.status_code == 200
    return zipfile.ZipFile(io.BytesIO(r.content))


def test_werkzeugweg_legt_dokumente_an_und_zip_enthaelt_sie(umgebung):
    db, mcp, tmp = umgebung
    aid, cv, anschr = _bewerbung(db, tmp)
    erg = _call(mcp, "bewerbung_bearbeiten", {
        "bewerbung_id": aid, "cv_path": str(cv), "cover_letter_path": str(anschr)})
    assert erg["status"] == "aktualisiert"
    docs = db.get_documents_for_application(aid)
    assert {d["doc_type"] for d in docs} == {"lebenslauf", "anschreiben"}
    namen = zipfile.ZipFile.namelist(_zip(db, aid))
    assert "dokumente/lebenslauf_test.docx" in namen
    assert "dokumente/anschreiben_test.docx" in namen


def test_zweiter_aufruf_macht_keine_dublette(umgebung):
    db, mcp, tmp = umgebung
    aid, cv, anschr = _bewerbung(db, tmp)
    for _ in range(2):
        _call(mcp, "bewerbung_bearbeiten", {"bewerbung_id": aid, "cv_path": str(cv)})
    assert len(db.get_documents_for_application(aid)) == 1


def test_fehlende_datei_wird_gemeldet_nicht_eingetragen(umgebung):
    db, mcp, tmp = umgebung
    aid, cv, _ = _bewerbung(db, tmp)
    erg = _call(mcp, "bewerbung_bearbeiten", {
        "bewerbung_id": aid, "cv_path": str(tmp / "gibt_es_nicht.docx")})
    assert db.get_documents_for_application(aid) == []
    assert "unterlagen" in erg and "nicht_gefunden" in str(erg["unterlagen"])


def test_altbestand_wird_einmal_nachgezogen(umgebung):
    db, mcp, tmp = umgebung
    aid, cv, anschr = _bewerbung(db, tmp)
    # Altbestand: Pfade stehen an der Bewerbung, kein Dokument
    db.update_application(aid, {"cv_path": str(cv), "cover_letter_path": str(anschr)})
    assert db.get_documents_for_application(aid) == []
    from bewerbungs_assistent.services import unterlagen
    assert unterlagen.altbestand_nachziehen(db) == 2
    assert unterlagen.altbestand_nachziehen(db) == 0
    assert len(db.get_documents_for_application(aid)) == 2


def test_hochgeladene_datei_gleichen_pfads_wird_nicht_verdoppelt(umgebung):
    db, mcp, tmp = umgebung
    aid, cv, _ = _bewerbung(db, tmp)
    db.add_document({"filename": cv.name, "filepath": str(cv), "doc_type": "lebenslauf",
                     "linked_application_id": aid})
    _call(mcp, "bewerbung_bearbeiten", {"bewerbung_id": aid, "cv_path": str(cv)})
    assert len(db.get_documents_for_application(aid)) == 1


def test_initialize_zieht_altbestand_nach(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "t.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path)
    db.save_profile({"name": "Test Person"})
    aid = db.add_application({"title": "A", "company": "Musterbetrieb GmbH", "status": "beworben"})
    f = tmp_path / "cv.docx"
    f.write_bytes(b"x")
    db.update_application(aid, {"cv_path": str(f)})
    db.close()
    db2 = Database(db_path=tmp_path / "t.db")
    db2.initialize()
    assert len(db2.get_documents_for_application(aid)) == 1
    db2.close()
    os.environ.pop("BA_DATA_DIR", None)
