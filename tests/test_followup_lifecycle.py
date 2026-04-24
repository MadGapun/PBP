"""Tests fuer Follow-up-Lifecycle (#493, #494, #497 min. Event-System)."""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture
def dash_client(tmp_path):
    """Liefert (TestClient, dashboard_modul) mit temporaerer DB."""
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()

    import bewerbungs_assistent.dashboard as dash
    dash._db = db

    from fastapi.testclient import TestClient
    tc = TestClient(dash.app)
    yield tc, dash

    db.close()
    if "BA_DATA_DIR" in os.environ:
        del os.environ["BA_DATA_DIR"]


def _make_app(db, title="Stelle X", company="Firma X", status="beworben"):
    return db.add_application({"title": title, "company": company, "status": status})


class TestTerminalStatusDismissesFollowups:
    """#493: Wechsel auf terminalen Status setzt offene Follow-ups auf hinfaellig."""

    @pytest.mark.parametrize("terminal_status", ["abgelehnt", "zurueckgezogen", "angenommen", "abgelaufen", "abgesagt"])
    def test_all_terminal_statuses_dismiss_followups(self, tmp_db, terminal_status):
        app_id = _make_app(tmp_db)
        due = (datetime.now() + timedelta(days=3)).date().isoformat()
        fu_id = tmp_db.add_follow_up(app_id, due)

        assert tmp_db.update_application_status(app_id, terminal_status) is True

        pending = [fu for fu in tmp_db.get_pending_follow_ups() if fu["id"] == fu_id]
        assert pending == [], f"Follow-up nach {terminal_status} nicht hinfaellig"
        fu = tmp_db.get_follow_up(fu_id)
        assert fu["status"] == "hinfaellig"

    def test_non_terminal_keeps_followups(self, tmp_db):
        app_id = _make_app(tmp_db)
        due = (datetime.now() + timedelta(days=3)).date().isoformat()
        fu_id = tmp_db.add_follow_up(app_id, due)

        tmp_db.update_application_status(app_id, "interview")

        pending = [fu for fu in tmp_db.get_pending_follow_ups() if fu["id"] == fu_id]
        assert len(pending) == 1


class TestInterviewCompletedAutoFollowup:
    """#494: interview_abgeschlossen markiert alte Follow-ups hinfaellig + legt neues an."""

    def test_interview_abgeschlossen_creates_nachfrage_followup(self, tmp_db):
        app_id = _make_app(tmp_db, status="interview")
        old_due = (datetime.now() + timedelta(days=5)).date().isoformat()
        old_fu = tmp_db.add_follow_up(app_id, old_due)

        tmp_db.update_application_status(app_id, "interview_abgeschlossen")

        # Alter FU hinfaellig
        assert tmp_db.get_follow_up(old_fu)["status"] == "hinfaellig"
        # Neuer FU angelegt
        pending = [fu for fu in tmp_db.get_pending_follow_ups() if fu["application_id"] == app_id]
        assert len(pending) == 1
        expected = (datetime.now() + timedelta(days=14)).date().isoformat()
        assert pending[0]["scheduled_date"] == expected
        assert pending[0]["follow_up_type"] == "nachfass"

    def test_custom_delay_from_setting(self, tmp_db):
        tmp_db.set_setting("followup_interview_delay_days", 21)
        app_id = _make_app(tmp_db, status="interview")

        tmp_db.update_application_status(app_id, "interview_abgeschlossen")

        pending = [fu for fu in tmp_db.get_pending_follow_ups() if fu["application_id"] == app_id]
        expected = (datetime.now() + timedelta(days=21)).date().isoformat()
        assert pending[0]["scheduled_date"] == expected

    def test_delay_zero_disables_auto_followup(self, tmp_db):
        tmp_db.set_setting("followup_interview_delay_days", 0)
        app_id = _make_app(tmp_db, status="interview")

        tmp_db.update_application_status(app_id, "interview_abgeschlossen")

        pending = [fu for fu in tmp_db.get_pending_follow_ups() if fu["application_id"] == app_id]
        assert pending == []


class TestFollowupSettingsEndpoint:
    """HTTP-Endpoint /api/settings/followup."""

    def test_get_defaults(self, dash_client):
        client, _ = dash_client
        r = client.get("/api/settings/followup")
        assert r.status_code == 200
        body = r.json()
        assert body["followup_default_days"] == 7
        assert body["followup_interview_delay_days"] == 14

    def test_put_updates_values(self, dash_client):
        client, _ = dash_client
        r = client.put("/api/settings/followup", json={"followup_interview_delay_days": 21})
        assert r.status_code == 200
        assert r.json()["gespeichert"]["followup_interview_delay_days"] == 21

        r2 = client.get("/api/settings/followup")
        assert r2.json()["followup_interview_delay_days"] == 21

    def test_rejects_out_of_range(self, dash_client):
        client, _ = dash_client
        r = client.put("/api/settings/followup", json={"followup_default_days": 9999})
        assert r.status_code == 400

    def test_rejects_non_number(self, dash_client):
        client, _ = dash_client
        r = client.put("/api/settings/followup", json={"followup_default_days": "abc"})
        assert r.status_code == 400


class TestHttpStatusChangeLifecycle:
    """HTTP PUT /api/applications/{id}/status triggert die gleichen Hooks (#493/#494)."""

    def test_http_reject_dismisses_followups(self, dash_client):
        client, dash = dash_client
        # profil_id Setup
        dash._db.save_profile({"name": "Testuser"})
        app_id = dash._db.add_application({"title": "Job", "company": "Firma", "status": "beworben"})
        due = (datetime.now() + timedelta(days=4)).date().isoformat()
        dash._db.add_follow_up(app_id, due)

        r = client.put(f"/api/applications/{app_id}/status", json={"status": "abgelehnt"})
        assert r.status_code == 200
        body = r.json()
        assert body["lifecycle"]["followups_dismissed"] == 1

        pending = [fu for fu in dash._db.get_pending_follow_ups() if fu["application_id"] == app_id]
        assert pending == []

    def test_http_interview_abgeschlossen_returns_new_followup(self, dash_client):
        client, dash = dash_client
        dash._db.save_profile({"name": "Testuser"})
        app_id = dash._db.add_application({"title": "Job", "company": "Firma", "status": "interview"})

        r = client.put(f"/api/applications/{app_id}/status", json={"status": "interview_abgeschlossen"})
        assert r.status_code == 200
        lifecycle = r.json()["lifecycle"]
        assert lifecycle["new_followup"] is not None
        assert lifecycle["new_followup"]["scheduled_date"] == (
            datetime.now() + timedelta(days=14)
        ).date().isoformat()
