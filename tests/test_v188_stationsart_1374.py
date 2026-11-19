"""#1374 — Anstellungsart einer Station: Ehrenamt & Co., Unbekanntes wird gemeldet.

Bis v1.8.7 nahm `position_hinzufuegen` jeden Wert ungeprueft an und
beschrieb nur vier. Jetzt gibt es eine Liste (`services/stationsart.py`),
bekannte Schreibweisen werden normalisiert, Unbekanntes bleibt erhalten
UND wird in der Antwort gemeldet. Alle Namen sind Platzhalter.
"""
import asyncio
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import stationsart  # noqa: E402


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v188_1374_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, _srv_mod.mcp
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


def _station(db, pid):
    return next(p for p in db.get_profile()["positions"] if p["id"] == pid)


def test_liste_nennt_ehrenamt_pflege_elternzeit():
    for wert in ("ehrenamt", "pflegezeit", "elternzeit", "weiterbildung"):
        assert wert in stationsart.STATIONSARTEN


def test_bekannte_werte_ohne_hinweis():
    assert stationsart.pruefen("ehrenamt") == ("ehrenamt", "")
    assert stationsart.pruefen("") == ("festanstellung", "")
    assert stationsart.pruefen("  Ehrenamt ") == ("ehrenamt", "")


def test_schreibweise_wird_normalisiert_und_gemeldet():
    wert, hinweis = stationsart.pruefen("Ehrenamtlich")
    assert wert == "ehrenamt" and "ehrenamt" in hinweis


def test_unbekannt_bleibt_erhalten_und_wird_gemeldet():
    wert, hinweis = stationsart.pruefen("Sonderfall X")
    assert wert == "Sonderfall X"
    assert "gehört nicht zur Liste" in hinweis


def test_tool_ehrenamt_ohne_hinweis(umgebung):
    db, mcp = umgebung
    r = _call(mcp, "position_hinzufuegen", {
        "company": "Musterverein", "title": "Betreuerin",
        "start_date": "2019-01", "employment_type": "ehrenamt"})
    assert "hinweis_anstellungsart" not in r
    assert _station(db, r["position_id"])["employment_type"] == "ehrenamt"


def test_tool_unbekannter_wert_gespeichert_mit_hinweis(umgebung):
    db, mcp = umgebung
    r = _call(mcp, "position_hinzufuegen", {
        "company": "Musterverein", "title": "Betreuerin",
        "start_date": "2019-01", "employment_type": "Sonderfall X"})
    assert "Sonderfall X" in r["hinweis_anstellungsart"]
    assert _station(db, r["position_id"])["employment_type"] == "Sonderfall X"


@pytest.mark.parametrize("aktion", ["hinzufuegen", "aendern", "bulk"])
def test_profil_bearbeiten_meldet_unbekanntes(umgebung, aktion):
    db, mcp = umgebung
    basis = {"company": "Musterverein", "title": "Betreuerin", "start_date": "2019-01"}
    if aktion == "hinzufuegen":
        r = _call(mcp, "profil_bearbeiten", {
            "bereich": "position", "aktion": "hinzufuegen",
            "daten": {**basis, "stellenart": "Sonderfall X"}})
    elif aktion == "bulk":
        r = _call(mcp, "profil_bearbeiten", {
            "bereich": "position", "aktion": "hinzufuegen_bulk",
            "daten": [{**basis, "employment_type": "Sonderfall X"}]})
    else:
        pid = _call(mcp, "position_hinzufuegen", basis)["position_id"]
        r = _call(mcp, "profil_bearbeiten", {
            "bereich": "position", "aktion": "aendern", "element_id": pid,
            "daten": {"employment_type": "Sonderfall X"}})
    assert "Sonderfall X" in r["hinweis_anstellungsart"]


def test_export_zeigt_lesbaren_text(umgebung):
    from bewerbungs_assistent import export
    assert export._stationsart_text("ehrenamt") == "Ehrenamt"
    assert export._stationsart_text("festanstellung") == ""
    assert export._stationsart_text("Sonderfall X") == "Sonderfall X"


def test_export_nutzt_den_helfer_an_allen_drei_stellen():
    quelle = (ROOT / "src/bewerbungs_assistent/export.py").read_text(encoding="utf-8")
    assert quelle.count("_stationsart_text(") >= 4  # Definition + drei Stellen


def test_dashboard_liste_deckt_die_werkzeugliste():
    """Dieselbe Liste an beiden Orten: jeder Wert steht in der Auswahl."""
    jsx = (ROOT / "frontend/src/pages/ProfilePage.jsx").read_text(encoding="utf-8")
    for wert in stationsart.STATIONSARTEN:
        if wert == "vollzeit":  # nur Anzeige, nicht in der Auswahl
            continue
        assert f'<option value="{wert}">' in jsx, wert
        assert f'{wert}: "' in jsx, wert


def test_beide_listen_nennen_die_abgrenzung():
    for datei, verweis in (("stationsart.py", "stellenart.py"),
                           ("stellenart.py", "stationsart.py")):
        text = (ROOT / "src/bewerbungs_assistent/services" / datei).read_text(encoding="utf-8")
        assert verweis in text
