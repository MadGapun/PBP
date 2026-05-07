"""Tests fuer v1.7.0-beta.37 — Elwosa (#599)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta37_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    _dash_mod._db = db
    yield db
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============= Schema v41 ===============

def test_schema_v41_tables_exist(setup_env):
    db = setup_env
    conn = db.connect()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "elwosa_messages" in tables
    assert "elwosa_pending_lines" in tables


# ============= Sprach-DNA-Validator ===============

def test_validator_rejects_exclamation():
    from bewerbungs_assistent.services.elwosa import (
        TonfallError, validate_tonfall,
    )
    with pytest.raises(TonfallError) as exc:
        validate_tonfall("Hallo!")
    assert "Ausrufezeichen" in str(exc.value)


def test_validator_rejects_emoji():
    from bewerbungs_assistent.services.elwosa import (
        TonfallError, validate_tonfall,
    )
    with pytest.raises(TonfallError) as exc:
        validate_tonfall("Hallo 🤖")
    assert "Emoji" in str(exc.value)


def test_validator_rejects_hoeflichkeits_anrede():
    """'Sie' alleine ist mehrdeutig (3. Person Plural fuer Firmen/Recruiter)
    und wird nicht verboten. Aber die eindeutigen Hoeflichkeits-Formen
    'Ihre' / 'Ihnen' duerfen nicht vorkommen."""
    from bewerbungs_assistent.services.elwosa import (
        TonfallError, validate_tonfall,
    )
    with pytest.raises(TonfallError):
        validate_tonfall("Ich finde Ihre Bewerbung gut.")
    with pytest.raises(TonfallError):
        validate_tonfall("Ich gratuliere Ihnen.")
    # 'Sie' als Subjekt-Pronomen (Firma) muss erlaubt sein
    validate_tonfall("Sie wollen einen Kassierer? Akzeptabel.")


def test_validator_rejects_too_long():
    from bewerbungs_assistent.services.elwosa import (
        TonfallError, validate_tonfall,
    )
    with pytest.raises(TonfallError) as exc:
        validate_tonfall("a" * 281)
    assert "zu lang" in str(exc.value)


def test_validator_rejects_empty():
    from bewerbungs_assistent.services.elwosa import (
        TonfallError, validate_tonfall,
    )
    with pytest.raises(TonfallError):
        validate_tonfall("")
    with pytest.raises(TonfallError):
        validate_tonfall("   ")


def test_validator_accepts_valid_line():
    from bewerbungs_assistent.services.elwosa import validate_tonfall
    validate_tonfall("Drei Stellen aussortiert. Saubere Quote heute.")
    validate_tonfall("Du musst dir das ansehen. Markiert.")


# ============= Linien-Pool: Tonfall-Waechter ===============

def test_all_pool_lines_pass_validator():
    """Wichtigster Test: KEINE Linie im Pool darf gegen Sprach-DNA verstossen."""
    from bewerbungs_assistent.services.elwosa import validate_tonfall
    from bewerbungs_assistent.services import elwosa_lines as L

    pools_to_check = []
    for cluster, lines in L.CLUSTER_LINES.items():
        for line in lines:
            pools_to_check.append((f"cluster:{cluster}", line))
    for kind, lines in L.STATUS_LINES.items():
        for line in lines:
            pools_to_check.append((f"status:{kind}", line))
    for line in L.IDLE_LINES:
        pools_to_check.append(("idle", line))
    for kind, lines in L.WORLD_LINES.items():
        for line in lines:
            pools_to_check.append((f"world:{kind}", line))
    for kind, lines in L.STATUS_CHANGE_LINES.items():
        for line in lines:
            pools_to_check.append((f"status_change:{kind}", line))
    for line in L.TIP_LINES:
        pools_to_check.append(("tip", line))
    for egg_id, line in L.EASTER_EGGS.items():
        pools_to_check.append((f"egg:{egg_id}", line))

    failures = []
    for label, line in pools_to_check:
        # Variablen einsetzen mit dummy-Werten
        try:
            filled = line.format(
                firma="ACME", count=3, title="X", score=80, percent=20,
                days=5, tool="x", wochentag="Montag",
            )
        except (KeyError, ValueError):
            filled = line
        try:
            validate_tonfall(filled)
        except Exception as e:
            failures.append(f"{label}: {e} — {filled[:60]}")
    assert not failures, "Tonfall-Verstoesse:\n" + "\n".join(failures)


def test_all_clusters_have_lines():
    from bewerbungs_assistent.services.elwosa_lines import CLUSTER_LINES
    for cluster in (
        "student", "service", "trade", "tech_junior", "tech_senior",
        "engineering_senior", "freelance", "executive", "mixed",
    ):
        assert len(CLUSTER_LINES.get(cluster, [])) >= 5, (
            f"Cluster '{cluster}' hat zu wenig Linien"
        )


# ============= speak() Master-Funktion ===============

def test_speak_writes_message(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True)
    from bewerbungs_assistent.services import elwosa
    msg_id = elwosa.speak(db, "morning", ctx={"count": 5}, cluster="tech_senior")
    assert msg_id is not None
    msgs = db.get_elwosa_messages()
    assert len(msgs) == 1


def test_speak_respects_disabled(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=False)
    from bewerbungs_assistent.services import elwosa
    msg_id = elwosa.speak(db, "morning", ctx={}, cluster="mixed")
    assert msg_id is None


def test_speak_respects_cooldown(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True)
    from bewerbungs_assistent.services import elwosa
    first = elwosa.speak(db, "morning", ctx={}, cluster="tech_senior")
    assert first is not None
    second = elwosa.speak(db, "morning", ctx={}, cluster="tech_senior")
    # Cooldown verhindert sofortigen 2. Post
    assert second is None


def test_speak_status_trigger_bypasses_freq_limit(setup_env):
    """Status-Trigger sind UNBEGRENZT, auch bei 'ruhig'."""
    db = setup_env
    db.set_elwosa_settings(enabled=True, frequency="ruhig")
    from bewerbungs_assistent.services import elwosa
    # Cooldown umgehen indem wir direkt add_elwosa_message aufrufen
    # und dann pruefen ob can_post_class trotz frequency='ruhig' True
    # zurueckgibt fuer Status-Klassen
    settings = db.get_elwosa_settings()
    assert elwosa.can_post_class(db, "mail_received", settings) is True
    assert elwosa.can_post_class(db, "auto_dismiss_ran", settings) is True
    assert elwosa.can_post_class(db, "status_change", settings) is True


def test_speak_idle_respects_freq_limit(setup_env):
    """Idle-Trigger werden gedrosselt — bei 'ruhig' nur 2/Tag."""
    db = setup_env
    db.set_elwosa_settings(enabled=True, frequency="ruhig")
    from bewerbungs_assistent.services import elwosa
    # Mock 2 idle-Messages heute
    db.add_elwosa_message("a", trigger_kind="idle")
    db.add_elwosa_message("b", trigger_kind="idle")
    settings = db.get_elwosa_settings()
    assert elwosa.can_post_class(db, "idle", settings) is False


def test_speak_pause_until_blocks(setup_env):
    db = setup_env
    from datetime import datetime, timedelta
    future = (datetime.now() + timedelta(hours=1)).isoformat()
    db.set_elwosa_settings(enabled=True, paused_until=future)
    from bewerbungs_assistent.services import elwosa
    msg_id = elwosa.speak(db, "morning", ctx={}, cluster="mixed")
    assert msg_id is None


# ============= speak_raw (Claude → Elwosa) ===============

def test_speak_raw_validates(setup_env):
    db = setup_env
    from bewerbungs_assistent.services import elwosa
    # Gueltige Linie
    msg_id = elwosa.speak_raw(db, "Vermerkt. Bleibe dran.")
    assert msg_id > 0


def test_speak_raw_rejects_invalid(setup_env):
    db = setup_env
    from bewerbungs_assistent.services import elwosa
    with pytest.raises(elwosa.TonfallError):
        elwosa.speak_raw(db, "Hallo!")


# ============= API ===============

def test_api_elwosa_messages_empty(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/elwosa/messages")
    assert r.status_code == 200
    assert r.json() == {"messages": [], "count": 0}


def test_api_elwosa_settings_default(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/elwosa/settings")
    j = r.json()
    assert j["enabled"] is True
    assert j["frequency"] == "standard"
    assert j["tonfall_modus"] == "standard"


def test_api_elwosa_settings_invalid_frequency(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.put("/api/elwosa/settings", json={"frequency": "absurd"})
    assert r.status_code == 400


def test_api_elwosa_pause(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/elwosa/pause", json={"minuten": 30})
    assert r.status_code == 200
    assert "paused_until" in r.json()


def test_api_elwosa_pending_empty(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/elwosa/pending-lines")
    assert r.json() == {"pending": [], "count": 0}


# ============= MCP-Tool Integration ===============

def test_mcp_tool_elwosa_lesen(setup_env):
    db = setup_env
    db.add_elwosa_message("Test-Linie 1.")
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.elwosa import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("elwosa_lesen")
        res = await tool.run({"limit": 5})
        return res.structured_content if hasattr(res, "structured_content") else res

    out = asyncio.run(_run())
    assert out["count"] >= 1


def test_mcp_tool_elwosa_schreiben_validates(setup_env):
    db = setup_env
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.elwosa import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run(args):
        tool = await mcp.get_tool("elwosa_schreiben")
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res

    # Gueltige Linie
    ok = asyncio.run(_run({"content": "Vermerkt. Bleibe dran."}))
    assert ok.get("status") == "gepostet"

    # Linie mit Ausrufezeichen → Fehler
    bad = asyncio.run(_run({"content": "Hallo!"}))
    assert "fehler" in bad


def test_mcp_tool_elwosa_pause(setup_env):
    db = setup_env
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.elwosa import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("elwosa_pause")
        res = await tool.run({"minuten": 30})
        return res.structured_content if hasattr(res, "structured_content") else res

    out = asyncio.run(_run())
    assert out["status"] == "pausiert"
    assert out["minuten"] == 30


def test_mcp_tool_elwosa_linie_vorschlagen(setup_env):
    db = setup_env
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.elwosa import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run(args):
        tool = await mcp.get_tool("elwosa_linie_vorschlagen")
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res

    out = asyncio.run(_run({
        "cluster": "tech_senior",
        "trigger_kind": "idle",
        "content": "Diese Linie wurde von Claude vorgeschlagen. Vermerkt.",
    }))
    assert out["status"] == "vorgeschlagen"
    pending = db.get_elwosa_pending_lines()
    assert len(pending) == 1


# ============= Frontend-Component existiert ==============

def test_elwosa_sidebar_chat_exists():
    p = PROJECT_ROOT / "frontend" / "src" / "components" / "ElwosaSidebarChat.jsx"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "/api/elwosa/messages" in content
    assert "/api/elwosa/status" in content


def test_elwosa_settings_section_in_localai_tab():
    p = PROJECT_ROOT / "frontend" / "src" / "pages" / "SettingsPage.jsx"
    content = p.read_text(encoding="utf-8")
    assert "ElwosaSettingsSection" in content
    assert "/api/elwosa/settings" in content


def test_sidebar_subnav_includes_lokale_ki():
    p = PROJECT_ROOT / "frontend" / "src" / "App.jsx"
    content = p.read_text(encoding="utf-8")
    assert "settings-ai" in content
    assert "settings-automatik" in content


# ============= Auto-Engine ============

def test_auto_engine_includes_elwosa(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/auto-actions/run")
    j = r.json()
    assert "elwosa" in j


# ============= Welcome-Linie ============

def test_welcome_message_passes_validator():
    from bewerbungs_assistent.services.elwosa import validate_tonfall
    from bewerbungs_assistent.services.elwosa_lines import WELCOME_MESSAGE
    validate_tonfall(WELCOME_MESSAGE)
