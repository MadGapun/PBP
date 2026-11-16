"""#1387: Nächste Schritte kennen den Stand (Bewertung, Unterlagen, Nachfass)."""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_1387_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test Person"})
    yield db, _srv_mod.mcp, tmpdir
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def _tools(aktionen):
    return [a.get("tool") for a in aktionen["aktionen"]]


def _stelle(db):
    db.save_jobs([{"hash": "k1387", "title": "Planer", "company": "Musterbetrieb GmbH",
                   "url": "https://example.com/k1387", "source": "manuell",
                   "description": "Planung Einkauf " * 40, "score": 3}])
    return db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE '%k1387'").fetchone()["hash"]


def test_ohne_stand_bleibt_alles_stehen(umgebung):
    db, mcp, tmp = umgebung
    erg = _call(mcp, "bewerbung_erstellen", {
        "company": "Musterbetrieb GmbH", "title": "Planer", "status": "in_vorbereitung"})
    t = _tools(erg["nächste_schritte"])
    assert "fit_analyse" in t and "lebenslauf_angepasst_exportieren" in t
    assert "schon_erledigt" not in erg["nächste_schritte"]


def test_bewertung_streicht_fit_analyse_in_allen_drei_wegen(umgebung):
    db, mcp, tmp = umgebung
    voll = _stelle(db)
    _call(mcp, "stelle_urteil_speichern", {
        "job_hash": voll.split(":", 1)[-1], "urteil": "BEDINGT", "begruendung": "Lücke im Bereich X"})
    erg = _call(mcp, "bewerbung_erstellen", {
        "company": "Musterbetrieb GmbH", "title": "Planer", "status": "in_vorbereitung",
        "job_hash": voll.split(":", 1)[-1]})
    assert "fit_analyse" not in _tools(erg["nächste_schritte"]), erg["nächste_schritte"]
    assert any("bewertet" in s for s in erg["nächste_schritte"]["schon_erledigt"])
    aid = erg["bewerbung_id_voll"]
    det = _call(mcp, "bewerbung_details", {"bewerbung_id": aid})
    assert "fit_analyse" not in _tools(det["nächste_aktionen"]), det["nächste_aktionen"]
    # Statuswechsel zurück/hin: in_vorbereitung ist ein Wechsel-Ziel
    _call(mcp, "bewerbung_status_aendern", {"bewerbung_id": aid, "neuer_status": "offen"})
    st = _call(mcp, "bewerbung_status_aendern", {"bewerbung_id": aid, "neuer_status": "in_vorbereitung"})
    assert "fit_analyse" not in _tools(st["nächste_aktionen"])


def test_unterlagen_streichen_lebenslauf_und_anschreiben(umgebung):
    db, mcp, tmp = umgebung
    erg = _call(mcp, "bewerbung_erstellen", {
        "company": "Musterbetrieb GmbH", "title": "Planer", "status": "in_vorbereitung"})
    aid = erg["bewerbung_id_voll"]
    cv = os.path.join(tmp, "cv.docx"); open(cv, "wb").write(b"x")
    al = os.path.join(tmp, "al.docx"); open(al, "wb").write(b"x")
    _call(mcp, "bewerbung_bearbeiten", {"bewerbung_id": aid, "cv_path": cv, "cover_letter_path": al})
    det = _call(mcp, "bewerbung_details", {"bewerbung_id": aid})
    t = _tools(det["nächste_aktionen"])
    assert "lebenslauf_angepasst_exportieren" not in t
    assert "anschreiben_exportieren" not in t
    assert "firmen_recherche" in t, "Unerledigtes bleibt"


def test_nachfass_nach_beworben_wird_nicht_nochmal_vorgeschlagen(umgebung):
    db, mcp, tmp = umgebung
    erg = _call(mcp, "bewerbung_erstellen", {
        "company": "Musterbetrieb GmbH", "title": "Planer", "status": "in_vorbereitung"})
    aid = erg["bewerbung_id_voll"]
    st = _call(mcp, "bewerbung_status_aendern", {"bewerbung_id": aid, "neuer_status": "beworben"})
    assert st.get("auto_follow_up"), "Voraussetzung: automatische Erinnerung"
    assert "nachfass_planen" not in _tools(st["nächste_aktionen"])
    assert any("Nachfass" in s for s in st["nächste_aktionen"]["schon_erledigt"])
