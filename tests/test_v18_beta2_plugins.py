"""Tests fuer v1.8.0-beta.2 — J1 Ingest-API v1 + Pairing (#504),
C23 Volltext-Snapshot (#687), B24 Snapshot-Backfill (#688).

Ingest-API via FastAPI TestClient (Muster aus test_dashboard.py); alles
lokal, kein Netz.
"""
from __future__ import annotations

import os
import sys
from email.mime.text import MIMEText
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture
def client_db(tmp_path):
    """FastAPI TestClient + isolierte DB (BA_DATA_DIR-Regel beachtet)."""
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Test"})
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"

    import bewerbungs_assistent.dashboard as dash
    dash._db = db

    from fastapi.testclient import TestClient
    tc = TestClient(dash.app)
    yield tc, db

    db.close()
    os.environ.pop("BA_DATA_DIR", None)


MANIFEST = {
    "name": "Test-Zubringer",
    "version": "1.0.0",
    "ingest_api": "^1",
    "capabilities": ["ingest:email", "ingest:job"],
    "beschreibung": "Testplugin",
}


def _pair(client, manifest=None) -> dict:
    resp = client.post("/api/plugins/pair", json={"manifest": manifest or MANIFEST})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Manifest-Validierung ─────────────────────────────────────────────────


def test_manifest_validierung():
    from bewerbungs_assistent.services.plugins import validate_manifest
    fehler, norm = validate_manifest(MANIFEST)
    assert fehler == []
    assert norm["capabilities"] == ["ingest:email", "ingest:job"]

    fehler, _ = validate_manifest({})
    assert any("name" in f for f in fehler)
    assert any("version" in f for f in fehler)
    assert any("ingest_api" in f for f in fehler)
    assert any("capabilities" in f for f in fehler)

    # Falsche Major-Version wird abgelehnt (D4)
    fehler, _ = validate_manifest({**MANIFEST, "ingest_api": "^2"})
    assert any("v2" in f for f in fehler)
    # Unbekannte Capability wird abgelehnt
    fehler, _ = validate_manifest({**MANIFEST, "capabilities": ["ingest:kalender"]})
    assert any("unbekannt" in f for f in fehler)
    # Grosszuegige Semver-Schreibweisen der richtigen Major sind ok
    for spec in ("1", "^1.0", "~1.2", "1.x"):
        fehler, _ = validate_manifest({**MANIFEST, "ingest_api": spec})
        assert fehler == [], spec


# ── Pairing + Key-Lebenszyklus ───────────────────────────────────────────


def test_pairing_key_nur_einmal_und_nur_als_hash(client_db):
    client, db = client_db
    result = _pair(client)
    assert result["status"] == "gekoppelt"
    key = result["api_key"]
    assert key.startswith("pbp_") and len(key) > 40

    # Liste enthaelt weder Klartext-Key noch Hash
    listing = client.get("/api/plugins").json()
    assert len(listing["plugins"]) == 1
    eintrag = listing["plugins"][0]
    assert "api_key" not in eintrag and "api_key_hash" not in eintrag

    # DB haelt nur den Hash
    from bewerbungs_assistent.services.plugins import hash_key
    row = db.get_plugin_by_key_hash(hash_key(key))
    assert row is not None and row["name"] == "Test-Zubringer"


def test_pairing_lehnt_kaputtes_manifest_ab(client_db):
    client, _ = client_db
    resp = client.post("/api/plugins/pair", json={"manifest": {"name": "X"}})
    assert resp.status_code == 400
    assert isinstance(resp.json()["error"], list)


def test_widerruf_macht_key_sofort_tot(client_db):
    client, _ = client_db
    result = _pair(client)
    key = result["api_key"]
    headers = {"X-PBP-API-Key": key}
    assert client.get("/api/v1/ingest/ping", headers=headers).status_code == 200

    resp = client.delete(f"/api/plugins/{result['plugin_id']}")
    assert resp.status_code == 200
    assert client.get("/api/v1/ingest/ping", headers=headers).status_code == 401


# ── Ingest-Auth ──────────────────────────────────────────────────────────


def test_ingest_ohne_key_401(client_db):
    client, _ = client_db
    assert client.get("/api/v1/ingest/ping").status_code == 401
    assert client.post("/api/v1/ingest/job", json={"titel": "x", "firma": "y"}).status_code == 401


def test_ingest_capability_403(client_db):
    client, _ = client_db
    nur_email = {**MANIFEST, "name": "Nur-Mail", "capabilities": ["ingest:email"]}
    key = _pair(client, nur_email)["api_key"]
    resp = client.post("/api/v1/ingest/job", json={"titel": "x", "firma": "y"},
                       headers={"X-PBP-API-Key": key})
    assert resp.status_code == 403
    assert "Capability" in resp.json()["error"]


# ── Ingest: Job ──────────────────────────────────────────────────────────


def test_ingest_job_legt_stelle_an(client_db):
    client, db = client_db
    key = _pair(client)["api_key"]
    resp = client.post(
        "/api/v1/ingest/job",
        json={"titel": "PLM Consultant", "firma": "Acme Solutions GmbH",
              "url": "https://example.com/job/1",
              "beschreibung": "Teamcenter-Rollout und Prozessdesign. " * 5},
        headers={"X-PBP-API-Key": key},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "angelegt"

    jobs = db.get_active_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job["source"] == "plugin:Test-Zubringer"
    # C23: Snapshot wurde beim Anlegen gefuellt
    assert (job.get("description_snapshot") or "").startswith("Teamcenter")
    assert job.get("snapshot_source") == "anlage"
    # Plugin-Buchfuehrung
    plugin = db.get_plugins()[0]
    assert plugin["last_ingest_at"]
    assert "PLM Consultant" in plugin["last_ingest_info"]

    # Idempotent: gleicher Titel+Firma vom selben Plugin -> bereits_vorhanden
    resp2 = client.post(
        "/api/v1/ingest/job",
        json={"titel": "PLM Consultant", "firma": "Acme Solutions GmbH"},
        headers={"X-PBP-API-Key": key},
    )
    assert resp2.json()["status"] == "bereits_vorhanden"
    assert len(db.get_active_jobs()) == 1


def test_ingest_job_pflichtfelder_und_blacklist(client_db):
    client, db = client_db
    key = _pair(client)["api_key"]
    headers = {"X-PBP-API-Key": key}
    assert client.post("/api/v1/ingest/job", json={"titel": "x"},
                       headers=headers).status_code == 422
    db.add_to_blacklist("firma", "Sperrfirma GmbH", "test")
    resp = client.post("/api/v1/ingest/job",
                       json={"titel": "Beliebig", "firma": "Sperrfirma GmbH"},
                       headers=headers)
    assert resp.status_code == 409
    assert "Blacklist" in resp.json()["error"]


def test_ingest_job_blockt_bei_laufender_bewerbung(client_db):
    client, db = client_db
    key = _pair(client)["api_key"]
    db.add_application({"title": "Senior PLM Consultant",
                        "company": "Acme Solutions GmbH", "status": "beworben"})
    resp = client.post(
        "/api/v1/ingest/job",
        json={"titel": "Senior PLM Consultant (m/w/d)",
              "firma": "Acme Solutions GmbH"},
        headers={"X-PBP-API-Key": key},
    )
    assert resp.status_code == 409
    assert resp.json()["duplikat"]["titel"] == "Senior PLM Consultant"
    assert db.get_active_jobs() == []


# ── Ingest: E-Mail (volle Upload-Pipeline) ───────────────────────────────


def test_ingest_email_laeuft_durch_upload_pipeline(client_db, tmp_path):
    client, db = client_db
    nur_email = {**MANIFEST, "name": "Mail-Zubringer",
                 "capabilities": ["ingest:email"]}
    key = _pair(client, nur_email)["api_key"]

    msg = MIMEText("Sehr geehrte Damen und Herren, vielen Dank fuer Ihre "
                   "Bewerbung. Wir melden uns.")
    msg["From"] = "hr@example.com"
    msg["To"] = "kandidat@example.com"
    msg["Subject"] = "Eingangsbestaetigung Ihrer Bewerbung"
    eml = msg.as_bytes()

    resp = client.post(
        "/api/v1/ingest/email",
        files={"file": ("bestaetigung.eml", eml, "message/rfc822")},
        headers={"X-PBP-API-Key": key},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    doc = db.get_document(data["id"])
    assert doc is not None
    assert "Eingangsbestaetigung" in (doc.get("extracted_text") or "")

    plugin = [p for p in db.get_plugins() if p["name"] == "Mail-Zubringer"][0]
    assert "bestaetigung.eml" in plugin["last_ingest_info"]


# ── C23/B24: Snapshot ────────────────────────────────────────────────────


@pytest.fixture
def tmp_db(tmp_path):
    from bewerbungs_assistent.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Test"})
    assert str(tmp_path) in str(db.db_path)
    yield db
    db.close()


def test_snapshot_wird_beim_anlegen_gefuellt_und_nie_ueberschrieben(tmp_db):
    pid = tmp_db.get_active_profile_id() or ""
    h = f"{pid}:snap1"
    lang = "Original-Beschreibung mit ausreichend Inhalt. " * 3
    tmp_db.save_jobs([{"hash": h, "title": "T", "company": "F",
                       "source": "manuell", "score": 10, "description": lang}])
    job = tmp_db.get_job(h)
    assert job["description_snapshot"] == lang
    assert job["snapshot_source"] == "anlage"
    erstes_at = job["snapshot_at"]

    # Re-Ingest mit ANDERER Beschreibung: description folgt, Snapshot nicht
    neu = "Voellig andere, spaetere Beschreibung nach Re-Scrape. " * 3
    tmp_db.save_jobs([{"hash": h, "title": "T", "company": "F",
                       "source": "manuell", "score": 10, "description": neu}])
    job = tmp_db.get_job(h)
    assert job["description"] == neu
    assert job["description_snapshot"] == lang  # unveraendert (C23)
    assert job["snapshot_at"] == erstes_at

    # Auch der explizite Helper ueberschreibt nie
    assert tmp_db.set_description_snapshot_if_empty(h, neu, "nachladen") is False
    assert tmp_db.get_job(h)["description_snapshot"] == lang


def test_snapshot_kurze_beschreibung_fuellt_nicht(tmp_db):
    pid = tmp_db.get_active_profile_id() or ""
    h = f"{pid}:snap2"
    tmp_db.save_jobs([{"hash": h, "title": "T", "company": "F",
                       "source": "manuell", "score": 10, "description": "kurz"}])
    job = tmp_db.get_job(h)
    assert not job["description_snapshot"]
    # Nachladen liefert spaeter Volltext -> Helper fuellt genau einmal
    lang = "Nachgeladener Volltext der Anzeige. " * 3
    assert tmp_db.set_description_snapshot_if_empty(h, lang, "nachladen") is True
    job = tmp_db.get_job(h)
    assert job["description_snapshot"] == lang
    assert job["snapshot_source"] == "nachladen"


def test_fit_analyse_faellt_auf_snapshot_zurueck(tmp_db):
    import logging

    class FakeMCP:
        def __init__(self):
            self.tools = {}

        def tool(self):
            def deco(fn):
                self.tools[fn.__name__] = fn
                return fn
            return deco

    from bewerbungs_assistent.tools.jobs import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))

    pid = tmp_db.get_active_profile_id() or ""
    h = f"{pid}:snap3"
    lang = "PLM Teamcenter Rollout Beschreibung mit vielen Details. " * 4
    tmp_db.save_jobs([{"hash": h, "title": "PLM Consultant", "company": "F",
                       "source": "manuell", "score": 10, "description": lang}])
    # Live-Beschreibung bricht weg (z.B. kaputter Refetch)
    tmp_db.update_job(h, {"description": ""})

    result = mcp.tools["fit_analyse"](job_hash=h)
    assert "beschreibung_aus_snapshot" in result
    assert result.get("beschreibung_vorhanden", False) is True


def test_snapshot_backfill_step(client_db):
    client, db = client_db
    import bewerbungs_assistent.dashboard as dash
    pid = db.get_active_profile_id() or ""
    lang = "Bestands-Beschreibung vor Einfuehrung des Snapshots. " * 3
    conn = db.connect()
    # Bestand OHNE Snapshot simulieren (direktes INSERT wie Alt-Datenbestand)
    conn.execute(
        "INSERT INTO jobs (hash, title, company, source, description, "
        "is_active, profile_id, score) VALUES (?,?,?,?,?,1,?,10)",
        (f"{pid}:alt1", "Alt", "F", "manuell", lang, pid))
    conn.commit()

    result = dash._run_snapshot_backfill("2026-07-14T12:00:00")
    assert result["status"] == "ok"
    assert result["nachgezogen"] == 1
    job = db.get_job(f"{pid}:alt1")
    assert job["description_snapshot"] == lang
    assert job["snapshot_source"] == "nachhol"
    # Idempotent
    assert dash._run_snapshot_backfill("2026-07-14T12:01:00")["nachgezogen"] == 0

    # Flag deaktiviert den Step
    db.set_setting("auto_snapshot_backfill", "0")
    assert dash._run_snapshot_backfill("2026-07-14T12:02:00")["status"] == "deaktiviert"
