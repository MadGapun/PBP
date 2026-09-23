"""#1073 — Skill-Anlage verwarf legitime Namen und meldete trotzdem Erfolg.

Gemeldet am 23.09.2026: drei von zwoelf `skill_hinzufuegen`-Aufrufen kamen
mit `{"status": "gespeichert", "skill_id": ""}` zurueck, der Skill fehlte.
Zwei Fehler, die sich gegenseitig verstecken: die Satzfragment-Heuristik
der Dokumentenextraktion (#43, #129, #681) lief auf JEDEM Anlageweg, und
drei Aufrufer werteten die leere ID nicht aus. Folgeschaden:
`skills_bereinigen` loeschte dieselben Skills im Altbestand.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest

AUFZAEHLUNG = "Programmierung (Perl, C++, COBOL, Java, PHP, C#)"
PRAEZISIERUNG = ("Mechanische Konstruktion und Anlagenplanung "
                 "(Maschinen-, Anlagen-, Apparatebau)")


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17126_1073_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


def _namen(db):
    return {s["name"] for s in db._get_skills()}


# ===== Die Regeln ========================================================

@pytest.mark.parametrize("name", ["C++", "C/C++", "C#", "F#", ".NET", "R",
                                  "C#/F#", "Sehr gute Englischkenntnisse",
                                  AUFZAEHLUNG, PRAEZISIERUNG])
def test_1073_legitime_namen_gelten_als_eingabe(name):
    from bewerbungs_assistent.database import Database
    assert Database.skill_ablehnungsgrund(name, quelle="eingabe") is None


@pytest.mark.parametrize("name", ["C++", "C/C++", "C++/CLI", "R",
                                  AUFZAEHLUNG, PRAEZISIERUNG])
def test_1073_und_ueberleben_auch_die_extraktion(name):
    """`C++` darf auch aus einem Lebenslauf nicht verschwinden."""
    from bewerbungs_assistent.database import Database
    assert Database.skill_ablehnungsgrund(name, quelle="extraktion") is None


@pytest.mark.parametrize("name", [
    "", "---", "12345", "https://example.com", "+++", "## Kenntnisse"])
def test_1073_harte_regeln_gelten_auch_fuer_eingaben(name):
    from bewerbungs_assistent.database import Database
    assert Database.skill_ablehnungsgrund(name, quelle="eingabe")


@pytest.mark.parametrize("name", [
    "in Systemen wie Creo", "Programmierung in CATIA.",
    "SAP oder vergleichbar)",
    "wir suchen einen engagierten Kollegen fuer unser Team"])
def test_1073_satzfragmente_fallen_weiter_aus_der_extraktion(name):
    """Die Gegenrichtung: der Schutz vor Extraktions-Muell bleibt (#681)."""
    from bewerbungs_assistent.database import Database
    assert Database.skill_ablehnungsgrund(name, quelle="extraktion")


def test_1073_der_grund_nennt_die_regel_die_gegriffen_hat():
    from bewerbungs_assistent.database import Database
    grund = Database.skill_ablehnungsgrund("in Systemen wie Creo")
    assert "Funktionswort" in grund
    assert "Satzzeichen" not in grund


def test_1073_klammerinhalt_zaehlt_nicht_als_satz():
    from bewerbungs_assistent.database import Database
    assert Database._ohne_klammerinhalt("A (b, c, d) E") == "A  E"
    # Ohne Klammer bleibt die Regel scharf.
    assert Database.skill_ablehnungsgrund(
        "Programmierung Perl C++ COBOL Java PHP und C#")


# ===== Die Werkzeuge =====================================================

@pytest.mark.parametrize("name", ["C++", AUFZAEHLUNG, PRAEZISIERUNG])
def test_1073_skill_hinzufuegen_legt_an(setup_env, name):
    db, mcp = setup_env
    res = _call(mcp, "skill_hinzufuegen", {"name": name})
    assert res["status"] == "gespeichert"
    assert res["skill_id"]
    assert name in _namen(db)


def test_1073_eine_eingabe_ist_kein_extraktionsfragment(setup_env):
    """"Sehr gute ..." beginnt mit einem Funktionswort — aus einem Dokument
    waere das ein Satzfragment, als Eingabe ist es eine Kompetenz."""
    db, mcp = setup_env
    res = _call(mcp, "skill_hinzufuegen", {"name": "Sehr gute Englischkenntnisse"})
    assert res["status"] == "gespeichert"
    from bewerbungs_assistent.database import Database
    assert Database.skill_ablehnungsgrund("Sehr gute Englischkenntnisse")


def test_1073_skill_hinzufuegen_meldet_keinen_erfolg_ohne_id(setup_env):
    db, mcp = setup_env
    res = _call(mcp, "skill_hinzufuegen", {"name": "---"})
    assert res["status"] == "nicht_angelegt"
    assert res["skill_id"] == ""
    assert "Formatierung" in res["grund"]


def test_1073_profil_bearbeiten_nennt_den_echten_grund(setup_env):
    db, mcp = setup_env
    ok = _call(mcp, "profil_bearbeiten", {
        "bereich": "skill", "aktion": "hinzufuegen", "daten": {"name": "C++"}})
    assert ok["status"] == "hinzugefuegt"
    nein = _call(mcp, "profil_bearbeiten", {
        "bereich": "skill", "aktion": "hinzufuegen", "daten": {"name": "12345"}})
    assert nein["status"] == "nicht_angelegt"
    assert "Ziffern" in nein["grund"]


def test_1073_bulk_zaehlt_angelegt_und_verworfen_getrennt(setup_env):
    db, mcp = setup_env
    res = _call(mcp, "profil_bearbeiten", {
        "bereich": "skill", "aktion": "hinzufuegen_bulk",
        "daten": [{"name": "C++"}, {"name": "---"}, {"name": "Python"}]})
    assert res["anzahl"] == 2
    assert all(res["ids"])
    assert [v["name"] for v in res["verworfen"]] == ["---"]
    assert res["verworfen"][0]["grund"]


def test_1073_rest_weg_meldet_die_abweisung(setup_env):
    db, _ = setup_env
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    alt = dash._db
    dash._db = db
    try:
        c = TestClient(dash.app)
        ok = c.post("/api/skill", json={"name": "C/C++"})
        assert ok.status_code == 200 and ok.json()["id"]
        nein = c.post("/api/skill", json={"name": "+++"})
        assert nein.status_code == 422
        assert nein.json()["grund"]
    finally:
        dash._db = alt


# ===== Der Folgeschaden ==================================================

def test_1073_skills_bereinigen_loescht_keine_echten_skills(setup_env):
    """Altbestand ueber `update_skill` umbenannt (prueft keine Heuristik)."""
    db, mcp = setup_env
    sid = db.add_skill({"name": "Platzhalter"}, quelle="eingabe")
    db.update_skill(sid, {"name": "C++"})
    db.add_skill({"name": PRAEZISIERUNG}, quelle="eingabe")
    vorschau = _call(mcp, "skills_bereinigen", {})
    assert vorschau["anzahl"] == 0, vorschau
    _call(mcp, "skills_bereinigen", {"anwenden": True})
    assert {"C++", PRAEZISIERUNG} <= _namen(db)


def test_1073_bereinigen_nennt_je_kandidat_die_regel(setup_env):
    db, mcp = setup_env
    sid = db.add_skill({"name": "Platzhalter"}, quelle="eingabe")
    db.update_skill(sid, {"name": "in Systemen wie Creo"})
    vorschau = _call(mcp, "skills_bereinigen", {})
    assert vorschau["kandidaten"][0]["name"] == "in Systemen wie Creo"
    assert "Funktionswort" in vorschau["kandidaten"][0]["grund"]


def test_1073_extraktionspfad_bleibt_streng(setup_env):
    """Ohne `quelle` gilt der Extraktionspfad — der alte Aufrufer bleibt."""
    db, _ = setup_env
    assert db.add_skill({"name": "in Systemen wie Creo"}) == ""
    assert db.add_skill({"name": "C++"})
