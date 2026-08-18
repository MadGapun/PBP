"""Tests fuer Issue #670 (beta.87) — Duplikat-Erkennung verfeinert + force-Override.

Auf Tool-Ebene (stelle_manuell_anlegen):
- Verschiedene Stellen derselben Firma (nur geteiltes Domain-Keyword) werden
  NICHT mehr als Duplikat blockiert.
- force=True legt trotz Duplikat-Verdacht an und meldet `duplikat_uebersteuert`.
- Echte Duplikate (gleiche URL / sehr aehnlicher Titel) werden weiter erkannt.
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


def _register_jobs(tmp_db):
    from bewerbungs_assistent.tools.jobs import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


def test_konsumgueter_zweite_stelle_wird_angelegt(tmp_db):
    """#670-Kernfall: PLM Project Manager + PLM Product Owner bei derselben
    Firma sind verschiedene Stellen — beide muessen anlegbar sein."""
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_manuell_anlegen"]

    r1 = fn(titel="PLM Project Manager (m/w/d)", firma="Konsumgueter GmbH",
            url="https://konsumgueter.example/jobs/pm", ort="Hamburg")
    assert r1["status"] == "angelegt"

    r2 = fn(titel="PLM Product Owner (m/w/d)", firma="Konsumgueter GmbH",
            url="https://konsumgueter.example/jobs/po", ort="Hamburg")
    assert r2["status"] == "angelegt", f"Zweite Stelle muss anlegbar sein: {r2}"


def test_zeitnaehe_ohne_titelmatch_kein_block(tmp_db):
    """#670: gleiche Firma + zeitnah, aber komplett anderer Titel -> kein Block."""
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_manuell_anlegen"]

    fn(titel="Frontend Developer React", firma="Foo GmbH",
       url="https://foo.example/fe")
    r2 = fn(titel="Marketing Manager B2B", firma="Foo GmbH",
            url="https://foo.example/mkt")
    assert r2["status"] == "angelegt"


def test_gleiche_url_wird_als_duplikat_erkannt(tmp_db):
    """Echte Duplikate (identische URL) werden weiter geblockt/idempotent."""
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_manuell_anlegen"]

    fn(titel="PLM Consultant", firma="Acme AG",
       url="https://acme.example/jobs/plm-1")
    r2 = fn(titel="PLM Berater (m/w/d)", firma="Acme AG",
            url="https://acme.example/jobs/plm-1")
    # Gleiche URL -> als vorhandene aktive Stelle erkannt
    assert r2.get("warnung") == "duplikat_aktive_stelle" or r2.get("status") == "bereits_vorhanden"


def test_force_uebersteuert_duplikat(tmp_db):
    """force=True legt trotz Duplikat-Verdacht an und meldet es transparent."""
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_manuell_anlegen"]

    # Erste Stelle
    fn(titel="PLM Architect Senior", firma="Beta GmbH",
       url="https://beta.example/a")
    # Sehr aehnlicher Titel + gleiche URL -> waere Duplikat
    r2 = fn(titel="PLM Architect Senior", firma="Beta GmbH",
            url="https://beta.example/a", force=True)
    # Mit force trotzdem angelegt ODER (bei exakt gleichem Hash) bereits da.
    # Wenn der Hash kollidiert, ist es eh dieselbe — wir testen mit
    # anderer Quelle um einen neuen Hash zu erzwingen:
    r3 = fn(titel="PLM Architect Senior", firma="Beta GmbH",
            url="https://beta.example/a", quelle="xing", force=True)
    assert r3["status"] == "angelegt"
    assert "duplikat_uebersteuert" in r3


def test_ohne_force_wird_geblockt(tmp_db):
    """Gegentest: ohne force wird das echte Duplikat (gleiche URL) geblockt."""
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_manuell_anlegen"]

    fn(titel="Data Engineer", firma="Gamma GmbH",
       url="https://gamma.example/de", quelle="linkedin")
    r2 = fn(titel="Data Engineer", firma="Gamma GmbH",
            url="https://gamma.example/de", quelle="xing")
    # Gleiche URL -> erkannt, NICHT mit force -> kein neuer Anlege-Status
    assert r2.get("status") != "angelegt"
