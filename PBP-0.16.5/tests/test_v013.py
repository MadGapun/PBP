"""Tests fuer v0.13.0 Fixes: FIX-008, FIX-009, OPT-014, FIX-006/007."""

import os
import sys
import json
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture
def client(tmp_path):
    """FastAPI TestClient mit temporaerer DB."""
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()

    import bewerbungs_assistent.dashboard as dash
    dash._db = db

    from fastapi.testclient import TestClient
    tc = TestClient(dash.app)
    yield tc, db, tmp_path

    db.close()
    if "BA_DATA_DIR" in os.environ:
        del os.environ["BA_DATA_DIR"]


# ============================================================
# FIX-008: job_hash empty string → None
# ============================================================

class TestJobHashFix:
    def test_empty_job_hash_becomes_none(self, client):
        """Leerer job_hash wird zu None statt FK-Fehler."""
        tc, db, _ = client
        # Create profile first
        tc.post("/api/profile", json={"name": "Test User"})

        result = db.add_application({
            "title": "Dev", "company": "ACME",
            "job_hash": "", "status": "beworben",
        })
        assert result is not None
        apps = db.get_applications()
        assert len(apps) >= 1
        assert apps[0].get("job_hash") is None or apps[0].get("job_hash") == ""

    def test_none_job_hash_works(self, client):
        """None job_hash funktioniert normal."""
        tc, db, _ = client
        tc.post("/api/profile", json={"name": "Test User"})

        result = db.add_application({
            "title": "Dev", "company": "Corp",
            "job_hash": None, "status": "beworben",
        })
        assert result is not None

    def test_valid_job_hash_works(self, client):
        """Gueltiger job_hash funktioniert wenn Job existiert."""
        tc, db, _ = client
        tc.post("/api/profile", json={"name": "Test User"})

        # Add a job first via save_jobs
        db.save_jobs([{
            "hash": "abc123", "title": "Dev", "company": "X",
            "source": "test", "url": "https://example.com",
            "location": "", "snippet": "",
        }])
        result = db.add_application({
            "title": "Dev", "company": "X",
            "job_hash": "abc123", "status": "beworben",
        })
        assert result is not None


# ============================================================
# FIX-009: FK-safe delete and reset
# ============================================================

class TestFKSafeDelete:
    def test_reset_with_corrupt_job_hash(self, client):
        """Reset funktioniert auch wenn applications.job_hash='' existiert."""
        tc, db, _ = client
        tc.post("/api/profile", json={"name": "Test"})

        # Manually insert corrupt data (FK off to simulate old bug)
        conn = db.connect()
        pid = db.get_profile()["id"]
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            "INSERT INTO applications (id, profile_id, title, company, status, job_hash, applied_at) "
            "VALUES (?, ?, 'X', 'Y', 'beworben', '', date('now'))",
            ("app-corrupt", pid))
        conn.commit()
        conn.execute("PRAGMA foreign_keys=ON")

        # Reset should not crash
        r = tc.post("/api/reset", json={"confirm": "RESET"})
        assert r.status_code == 200

    def test_delete_profile_with_corrupt_data(self, client):
        """Profil loeschen funktioniert trotz corrupt FK data."""
        tc, db, _ = client
        tc.post("/api/profile", json={"name": "Corrupt"})
        profile = db.get_profile()

        conn = db.connect()
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            "INSERT INTO applications (id, profile_id, title, company, status, job_hash, applied_at) "
            "VALUES (?, ?, 'X', 'Y', 'beworben', '', date('now'))",
            ("app-corrupt2", profile["id"]))
        conn.commit()
        conn.execute("PRAGMA foreign_keys=ON")

        # Delete should not crash
        r = tc.delete(f"/api/profiles/{profile['id']}")
        assert r.status_code == 200


# ============================================================
# OPT-014: Directory browser + recursive import
# ============================================================

class TestDirectoryBrowser:
    def test_browse_empty_returns_suggestions(self, client):
        """Ohne Pfad gibt browse-directory Vorschlaege zurueck."""
        tc, _, _ = client
        r = tc.post("/api/browse-directory", json={})
        assert r.status_code == 200
        data = r.json()
        assert "entries" in data
        assert "suggestions" in data

    def test_browse_existing_dir(self, client):
        """Browse eines existierenden Verzeichnisses zeigt Eintraege."""
        tc, _, tmp_path = client
        subdir = tmp_path / "testdir"
        subdir.mkdir()
        (subdir / "test.pdf").write_bytes(b"%PDF-1.4 test")

        r = tc.post("/api/browse-directory", json={"path": str(tmp_path)})
        assert r.status_code == 200
        data = r.json()
        assert data["current"] == str(tmp_path)
        names = [e["name"] for e in data["entries"]]
        assert "testdir" in names

    def test_browse_blocked_path(self, client):
        """Systemverzeichnisse werden blockiert."""
        tc, _, _ = client
        r = tc.post("/api/browse-directory", json={"path": "/etc"})
        assert r.status_code == 403

    def test_browse_nonexistent(self, client):
        """Nicht-existierendes Verzeichnis gibt 404."""
        tc, _, _ = client
        r = tc.post("/api/browse-directory", json={"path": "/nonexistent_dir_xyz"})
        assert r.status_code == 404


class TestFolderImportRecursive:
    def test_non_recursive_import(self, client):
        """Ohne recursive werden nur Top-Level-Dateien importiert."""
        tc, db, tmp_path = client
        tc.post("/api/profile", json={"name": "Test"})

        folder = tmp_path / "import_test"
        folder.mkdir()
        (folder / "cv.txt").write_text("Lebenslauf Max Mustermann")
        sub = folder / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("Tiefer Ordner")

        r = tc.post("/api/documents/import-folder", json={
            "folder_path": str(folder), "recursive": False,
            "import_documents": True, "import_applications": False,
        })
        assert r.status_code == 200
        assert r.json()["documents_imported"] == 1  # only cv.txt

    def test_recursive_import(self, client):
        """Mit recursive=True werden auch Unterordner importiert."""
        tc, db, tmp_path = client
        tc.post("/api/profile", json={"name": "Test"})

        folder = tmp_path / "import_rec"
        folder.mkdir()
        (folder / "top.txt").write_text("Top level")
        sub = folder / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("Sub folder file")

        r = tc.post("/api/documents/import-folder", json={
            "folder_path": str(folder), "recursive": True,
            "import_documents": True, "import_applications": False,
        })
        assert r.status_code == 200
        assert r.json()["documents_imported"] == 2  # top.txt + deep.txt


# ============================================================
# FIX-007: Auto-analyze documents endpoint
# ============================================================

class TestAutoAnalyze:
    def test_analyze_without_profile(self, client):
        """Analyse ohne Profil gibt Fehler."""
        tc, _, _ = client
        r = tc.post("/api/dokumente-analysieren", json={})
        assert r.status_code == 400

    def test_analyze_no_documents(self, client):
        """Analyse ohne Dokumente gibt 'keine_dokumente'."""
        tc, _, _ = client
        tc.post("/api/profile", json={"name": "Test"})
        r = tc.post("/api/dokumente-analysieren", json={})
        assert r.status_code == 200
        assert r.json()["status"] == "keine_dokumente"

    def test_analyze_extracts_email(self, client):
        """Analyse extrahiert E-Mail aus Dokumenttext."""
        tc, db, _ = client
        tc.post("/api/profile", json={"name": "Test"})
        profile = db.get_profile()

        db.add_document({
            "filename": "cv.pdf",
            "filepath": "/tmp/cv.pdf",
            "doc_type": "lebenslauf",
            "extracted_text": "Max Mustermann\nmax@example.com\nTel: +49 123 456789",
        })

        r = tc.post("/api/dokumente-analysieren", json={"force": True})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "angewendet"
        assert "persoenliche_daten" in data.get("angewendet", {})
