"""Tests fuer v1.7.10 — #784 (F28) learned_insights + #774 (F29) Elwosa-Dialog.

Grundsatz aus dem Auftrag: KEINE Erkenntnis wird ohne Nutzerbestaetigung
wirksam — ableiten und anzeigen ja, automatisch anwenden nein. Und die
learned_insights-Tabelle kommt BEWUSST ohne Schema-Bump (v49 ist in der
1.8-Linie fuer `components` reserviert — Kollisionsgefahr im Upgrade-Pfad).
"""
import asyncio
import importlib
import os
import shutil
import tempfile
from unittest.mock import patch

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1710_784_")
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
    yield db, tmpdir
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _result(raw):
    if isinstance(raw, tuple):
        raw = raw[1] if len(raw) > 1 else raw[0]
    if hasattr(raw, "structured_content"):
        raw = raw.structured_content
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    return raw


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


def _korpus(db):
    conn = db.connect()
    pid = db.get_active_profile_id()
    for i in range(15):
        conn.execute(
            "INSERT INTO jobs (hash, title, company, location, url, source, "
            "description, is_active, dismiss_reason, profile_id, found_at, updated_at, score) "
            "VALUES (?,?,?,?,?,?,?,0,'falsches_fachgebiet',?,'2026-06-01','2026-06-01', 5)",
            (f"ff{i}", f"Fremdrolle {i}", "X", "HH", f"https://a.example/{i}",
             "demo", "Text. " * 20, pid))
    for i in range(6):
        conn.execute(
            "INSERT INTO jobs (hash, title, company, location, url, source, "
            "description, is_active, dismiss_reason, profile_id, found_at, updated_at, score) "
            "VALUES (?,?,?,?,?,?,?,0,'zeitarbeit',?,'2026-06-01','2026-06-01', 5)",
            (f"za{i}", f"ANUE-Rolle {i}", "Y", "HH", f"https://b.example/{i}",
             "demo", "Text. " * 20, pid))
    conn.commit()


# ------------------------------------------------------------------ #784

def test_784_tabelle_existiert_ohne_schema_bump(setup_env):
    db, _ = setup_env
    conn = db.connect()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name='learned_insights'").fetchone()
    assert row, "learned_insights muss ueber das Safety-Net existieren"
    # Kein Schema-Bump fuer learned_insights: 1.7-Linie bleibt 48, die
    # 1.8-Linie 52 (dort kam v49 fuer `components` — genau die Kollision,
    # die das Safety-Net vermeidet). Ein NEUER Bump in beiden Linien
    # waere ein Regressionszeichen.
    from bewerbungs_assistent.database import SCHEMA_VERSION
    assert SCHEMA_VERSION in (48, 52), (
        f"Unerwarteter Schema-Bump durch learned_insights: {SCHEMA_VERSION}")


def test_784_ableiten_liefert_kandidaten_mit_evidenz(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _korpus(db)
    res = _result(_call(mcp, "erkenntnisse_ableiten", {}))
    assert res["status"] == "vorschau"
    assert res["anzahl"] >= 2
    zeitarbeit = next((k for k in res["kandidaten"]
                       if k["kategorie"] == "stellentyp"), None)
    assert zeitarbeit, res["kandidaten"]
    assert zeitarbeit["belegt_durch_n"] == 6
    assert 0 < zeitarbeit["konfidenz"] < 1
    assert zeitarbeit["evidenz"]["grund"] == "zeitarbeit"
    # dry_run speichert nichts
    n = db.connect().execute(
        "SELECT COUNT(*) FROM learned_insights").fetchone()[0]
    assert n == 0


def test_784_ablegen_bestaetigen_widersprechen(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _korpus(db)
    res = _result(_call(mcp, "erkenntnisse_ableiten", {"dry_run": False}))
    assert res["gespeichert"]["neu"] >= 2

    alle = _result(_call(mcp, "erkenntnisse_anzeigen", {"filter": "offen"}))
    assert alle["anzahl"] >= 2
    erste, zweite = alle["erkenntnisse"][0], alle["erkenntnisse"][1]

    ok = _result(_call(mcp, "erkenntnis_bestaetigen",
                       {"erkenntnis_id": erste["id"], "bestaetigen": True}))
    assert ok["status"] == "bestaetigt"
    nein = _result(_call(mcp, "erkenntnis_bestaetigen",
                         {"erkenntnis_id": zweite["id"], "bestaetigen": False}))
    assert nein["status"] == "widersprochen"

    # Widersprochene werden beim naechsten Lauf NICHT erneut vorgeschlagen
    res2 = _result(_call(mcp, "erkenntnisse_ableiten", {"dry_run": False}))
    g = res2["gespeichert"]
    assert g["uebersprungen_widersprochen"] >= 1, g
    wider = _result(_call(mcp, "erkenntnisse_anzeigen",
                          {"filter": "widersprochen"}))
    assert wider["anzahl"] == 1

    # Nur BESTAETIGTE landen im Ollama-Kontext
    from bewerbungs_assistent.services.lerninsights import (
        bestaetigte_fuer_kontext)
    ctx = bestaetigte_fuer_kontext(db)
    assert len(ctx) == 1
    assert ctx[0]["aussage"] == erste["aussage"]


# ------------------------------------------------------------------ #774

def test_774_fragen_ohne_ollama_ist_ehrlich(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp

    class _Status:
        ollama_available = False
        error = "Verbindung verweigert"

    with patch("bewerbungs_assistent.services.llm_service.LLMService.get_status",
               return_value=_Status()):
        res = _result(_call(mcp, "elwosa_fragen",
                            {"frage": "Was faellt dir auf?"}))
    assert res["status"] == "nicht_erreichbar"
    assert "NICHT stillschweigend" in res["fehler"]


def test_774_fragen_mit_gemockter_ki(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _korpus(db)

    class _Status:
        ollama_available = True
        selected_model = "llama3.2:3b"
        available_models = ["llama3.2:3b"]
        error = ""

    with patch("bewerbungs_assistent.services.llm_service.LLMService.get_status",
               return_value=_Status()), \
         patch("bewerbungs_assistent.services.llm_service.LLMService._ollama_generate",
               return_value="Die meisten Aussortierungen sind fachfremd."):
        res = _result(_call(mcp, "elwosa_fragen",
                            {"frage": "Was faellt dir an den Aussortierungen auf?"}))
    assert res["status"] == "ok"
    assert res["modell"] == "llama3.2:3b"
    assert res["antwort"].startswith("Die meisten")
    assert "einordnung_pflicht" in res, "roh=False verlangt Einordnung"
    assert "Datenpunkten" in res["konfidenz_hinweis"]
    # Dialog wurde protokolliert
    n = db.connect().execute(
        "SELECT COUNT(*) FROM elwosa_messages WHERE cluster='dialog'"
    ).fetchone()[0]
    assert n == 2


def test_774_prompt_kopieren_sendet_nichts(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    with patch("bewerbungs_assistent.services.llm_service.LLMService._ollama_generate") as gen:
        res = _result(_call(mcp, "elwosa_prompt_kopieren",
                            {"zweck": "freie_frage", "frage": "Testfrage?"}))
        gen.assert_not_called()
    assert res["status"] == "ok"
    assert "Testfrage?" in res["prompt"]
    assert "Elwosa" in res["prompt"]

    res2 = _result(_call(mcp, "elwosa_prompt_kopieren",
                         {"zweck": "stellen_auto_aussortieren"}))
    assert res2["status"] == "nicht_verfuegbar"
    assert "v1.8" in res2["hinweis"]


def test_774_bestaetigte_erkenntnisse_landen_im_prompt(setup_env):
    """Die Brücke #784 -> #774: bestaetigte Insights gehen als Kontext mit."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _korpus(db)
    _result(_call(mcp, "erkenntnisse_ableiten", {"dry_run": False}))
    offen = _result(_call(mcp, "erkenntnisse_anzeigen", {"filter": "offen"}))
    _result(_call(mcp, "erkenntnis_bestaetigen",
                  {"erkenntnis_id": offen["erkenntnisse"][0]["id"],
                   "bestaetigen": True}))
    res = _result(_call(mcp, "elwosa_prompt_kopieren",
                        {"zweck": "freie_frage", "frage": "x"}))
    assert "BESTAETIGTE ERKENNTNISSE" in res["prompt"]
