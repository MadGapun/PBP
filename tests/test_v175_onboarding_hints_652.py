"""Tests fuer v1.7.5 — #652 (G11): Onboarding-Hints im Frontend sichtbar.

Backend existierte seit beta.76, war aber nur per MCP erreichbar. Neu:
REST-Endpoints GET /api/onboarding/hints (+tab-Filter) und
DELETE /api/onboarding/hints/{id}, plus der neue G17-Anschluss-Hint
g11_erste_suche_starten (Profil da, aber keine Suchbegriffe).
"""
import os

import pytest


@pytest.fixture
def client(tmp_path):
    """FastAPI TestClient mit temporaerer DB (Muster aus test_dashboard.py)."""
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"

    import bewerbungs_assistent.dashboard as dash
    dash._db = db

    from fastapi.testclient import TestClient
    tc = TestClient(dash.app)
    tc._db = db
    yield tc

    db.close()
    if "BA_DATA_DIR" in os.environ:
        del os.environ["BA_DATA_DIR"]


class TestErsteSucheHint:
    def test_profil_ohne_suchbegriffe_zeigt_hint(self, client):
        client._db.save_profile({"name": "Neuling"})
        r = client.get("/api/onboarding/hints?tab=dashboard")
        assert r.status_code == 200
        hints = r.json()["hints"]
        ids = {h["id"] for h in hints}
        assert "g11_erste_suche_starten" in ids
        hint = next(h for h in hints if h["id"] == "g11_erste_suche_starten")
        # Fuehrung: der Hint sagt konkret, was man Claude sagen soll
        assert "Claude" in hint["body"]
        assert hint["cta_tool"] == "keyword_vorschlaege"

    def test_mit_suchbegriffen_kein_hint(self, client):
        client._db.save_profile({"name": "Fortgeschritten"})
        client._db.set_search_criteria("keywords_muss", ["PLM"])
        r = client.get("/api/onboarding/hints?tab=dashboard")
        ids = {h["id"] for h in r.json()["hints"]}
        assert "g11_erste_suche_starten" not in ids

    def test_ohne_profil_kein_hint(self, client):
        r = client.get("/api/onboarding/hints?tab=dashboard")
        ids = {h["id"] for h in r.json()["hints"]}
        assert "g11_erste_suche_starten" not in ids


class TestRestEndpoints:
    def test_tab_filter(self, client):
        client._db.save_profile({"name": "Test"})
        r = client.get("/api/onboarding/hints?tab=kalender")
        assert r.status_code == 200
        # dashboard-Hint darf im kalender-Tab nicht auftauchen
        assert all(h["tab"] == "kalender" for h in r.json()["hints"])

    def test_ohne_tab_alle(self, client):
        client._db.save_profile({"name": "Test"})
        r = client.get("/api/onboarding/hints")
        assert r.status_code == 200
        assert r.json()["tab"] == "alle"

    def test_dismiss_persistiert(self, client):
        client._db.save_profile({"name": "Test"})
        r = client.get("/api/onboarding/hints?tab=dashboard")
        assert any(h["id"] == "g11_erste_suche_starten" for h in r.json()["hints"])
        d = client.delete("/api/onboarding/hints/g11_erste_suche_starten")
        assert d.status_code == 200
        assert d.json()["dismissed"] is True
        r2 = client.get("/api/onboarding/hints?tab=dashboard")
        assert not any(
            h["id"] == "g11_erste_suche_starten" for h in r2.json()["hints"])

    def test_dismiss_unbekannte_id(self, client):
        d = client.delete("/api/onboarding/hints/gibtsnicht")
        assert d.status_code == 200
        assert "error" in d.json()


class TestMcpParity:
    def test_mcp_tool_sieht_neuen_hint(self, client):
        """Das bestehende MCP-Tool und der neue REST-Endpoint nutzen
        denselben Service — Dismiss wirkt in beide Richtungen."""
        client._db.save_profile({"name": "Test"})
        from bewerbungs_assistent.services.onboarding_hints import (
            dismiss_hint, list_active_hints,
        )
        ids = {h["id"] for h in list_active_hints(client._db)}
        assert "g11_erste_suche_starten" in ids
        dismiss_hint(client._db, "g11_erste_suche_starten")
        r = client.get("/api/onboarding/hints?tab=dashboard")
        assert not any(
            h["id"] == "g11_erste_suche_starten" for h in r.json()["hints"])
