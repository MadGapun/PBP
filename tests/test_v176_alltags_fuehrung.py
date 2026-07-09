"""Tests fuer v1.7.6 — Alltags-Fuehrung: #706 (G16), #707 (H15), #689 (F21-Rest).

- G16: /api/workflow-prompt nimmt optionale Query-Args (stelle/firma) und
  befuellt interview_vorbereitung vor; argumentlose Prompts unveraendert.
- H15: Hint g11_notizen_pflegen (Profil da, Notizen leer/kurz) + Prompt-
  Guidance (Erkenntnisse sofort via profil_bearbeiten(notizen) speichern).
- F21-Rest: POST /api/learning/insights/reset loescht das Lernprotokoll.
"""
import os

import pytest


@pytest.fixture
def client(tmp_path):
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


# =====================================================================
# G16 (#706): Workflow-Prompt mit Query-Args
# =====================================================================

class TestWorkflowPromptArgs:
    def test_interview_vorbereitung_vorbefuellt(self, client):
        client._db.save_profile({"name": "Test"})
        r = client.get(
            "/api/workflow-prompt/interview_vorbereitung"
            "?stelle=Senior%20PLM%20Consultant&firma=Musterfirma")
        assert r.status_code == 200
        prompt = r.json()["prompt"]
        assert "Stelle: Senior PLM Consultant" in prompt
        assert "Firma: Musterfirma" in prompt
        assert "NICHT nochmal fragen" in prompt
        # #706: Todo-Anlage gehoert zur Anleitung
        assert "todo_anlegen" in prompt
        assert "Interview-Vorbereitung Musterfirma" in prompt

    def test_interview_vorbereitung_ohne_args_fragt_nach(self, client):
        client._db.save_profile({"name": "Test"})
        r = client.get("/api/workflow-prompt/interview_vorbereitung")
        assert r.status_code == 200
        prompt = r.json()["prompt"]
        assert "Frage nach Stelle und Firma" in prompt
        assert "KONTEXT (vorbefuellt" not in prompt
        assert "todo_anlegen" in prompt

    def test_unbekannte_query_args_werden_ignoriert(self, client):
        """Argumentlose Prompts brechen nicht, wenn jemand Args anhaengt."""
        client._db.save_profile({"name": "Test"})
        r = client.get("/api/workflow-prompt/willkommen?stelle=X&quatsch=1")
        assert r.status_code == 200
        assert "Willkommen" in r.json()["prompt"]

    def test_unbekannter_workflow_404(self, client):
        r = client.get("/api/workflow-prompt/gibtsnicht")
        assert r.status_code == 404


# =====================================================================
# H15 (#707): Notizen-Hint + Prompt-Guidance
# =====================================================================

class TestNotizenPflege:
    def test_hint_bei_leeren_notizen(self, client):
        client._db.save_profile({"name": "Test"})
        r = client.get("/api/onboarding/hints?tab=profil")
        ids = {h["id"] for h in r.json()["hints"]}
        assert "g11_notizen_pflegen" in ids

    def test_kein_hint_bei_gepflegten_notizen(self, client):
        client._db.save_profile({
            "name": "Test",
            "informal_notes": (
                "Bevorzugt Remote, max. 2 Buerotage, keine Zeitarbeit, "
                "Familie in der Naehe, daher Region Nord wichtig."
            ),
        })
        r = client.get("/api/onboarding/hints?tab=profil")
        ids = {h["id"] for h in r.json()["hints"]}
        assert "g11_notizen_pflegen" not in ids

    def test_prompt_guidance_ersterfassung_und_willkommen(self, client):
        from bewerbungs_assistent.prompts import build_kennlerngespraech_prompt
        text = build_kennlerngespraech_prompt(client._db)
        assert "profil_bearbeiten(bereich='notizen'" in text
        # willkommen (mit Profil) enthaelt die Guidance ebenfalls
        client._db.save_profile({"name": "Test"})
        r = client.get("/api/workflow-prompt/willkommen")
        assert "profil_bearbeiten(bereich='notizen'" in r.json()["prompt"]


# =====================================================================
# F21-Rest (#689): Lernprotokoll-Reset
# =====================================================================

def _insight_anlegen(db, title):
    conn = db.connect()
    conn.execute(
        "INSERT INTO learning_insights (profile_id, kind, scope, title, "
        "first_seen_at, last_seen_at) VALUES (?, 'dismiss_pattern', "
        "'global', ?, '2026-07-01T10:00:00', '2026-07-01T10:00:00')",
        (db.get_active_profile_id(), title),
    )
    conn.commit()


class TestLernprotokollReset:
    def test_reset_loescht_alle_insights(self, client):
        client._db.save_profile({"name": "Test"})
        _insight_anlegen(client._db, "Muster A")
        _insight_anlegen(client._db, "Muster B")
        assert len(client._db.list_learning_insights(only_active=False)) == 2

        r = client.post("/api/learning/insights/reset")
        assert r.status_code == 200
        assert r.json()["geloescht"] == 2
        assert client._db.list_learning_insights(only_active=False) == []

    def test_reset_auf_leerem_protokoll(self, client):
        client._db.save_profile({"name": "Test"})
        r = client.post("/api/learning/insights/reset")
        assert r.status_code == 200
        assert r.json()["geloescht"] == 0

    def test_einzel_dismiss_bleibt_funktional(self, client):
        """Regression: der bestehende Dismiss-Endpoint (AdaptiveHintBanner)
        arbeitet weiter — Insight wird stummgeschaltet, nicht geloescht."""
        client._db.save_profile({"name": "Test"})
        _insight_anlegen(client._db, "Muster C")
        item = client._db.list_learning_insights(only_active=False)[0]
        d = client.delete(f"/api/learning/insights/{item['id']}")
        assert d.status_code == 200
        rest = client._db.list_learning_insights(only_active=False)
        assert len(rest) == 1 and not rest[0]["is_active"]
