"""beta.93: MCP-Tools fuer Telemetrie-Sharing (Recovery + alles-als-MCP).

Hintergrund: ein White-Screen-Bug (undefinierte SelectInput-Komponente im
Datenschutz-Tab) hat User ausgesperrt, sobald sie Telemetrie aktiviert
hatten — sie kamen nicht mehr an den Toggle. Diese MCP-Tools geben Claude
einen Weg, den Stand zu lesen und das Sharing wieder abzuschalten, auch
wenn das Dashboard gerade nicht erreichbar ist.
"""
from __future__ import annotations

import logging


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _register_analyse(tmp_db):
    from bewerbungs_assistent.tools.analyse import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


def test_telemetrie_status_default_aus(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_analyse(tmp_db)
    status = mcp.tools["telemetrie_status"]()
    assert status["aktiv"] is False
    assert status["intervall_tage"] == 7


def test_telemetrie_setzen_an_und_aus(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_analyse(tmp_db)
    setzen = mcp.tools["telemetrie_setzen"]
    status = mcp.tools["telemetrie_status"]

    an = setzen(aktiv=True)
    assert an["status"] == "gespeichert"
    assert an["aktiv"] is True
    assert status()["aktiv"] is True

    # Recovery-Pfad: wieder abschalten
    aus = setzen(aktiv=False)
    assert aus["aktiv"] is False
    assert status()["aktiv"] is False


def test_telemetrie_setzen_intervall(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_analyse(tmp_db)
    setzen = mcp.tools["telemetrie_setzen"]

    r = setzen(intervall_tage=14)
    assert r["intervall_tage"] == 14
    # 0 = nie automatisch (valide explizite Wahl)
    r0 = setzen(intervall_tage=0)
    assert r0["intervall_tage"] == 0


def test_telemetrie_setzen_ungueltiges_intervall(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_analyse(tmp_db)
    r = mcp.tools["telemetrie_setzen"](intervall_tage=3)
    assert "fehler" in r


def test_telemetrie_setzen_ohne_args(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_analyse(tmp_db)
    r = mcp.tools["telemetrie_setzen"]()
    assert "fehler" in r
