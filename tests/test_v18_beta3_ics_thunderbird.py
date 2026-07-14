"""Tests fuer v1.8.0-beta.3 — J4.1 ics-Export gehaertet (#481) +
J2 Thunderbird-Add-on-Paket (#478).

Das Add-on selbst ist JavaScript (nicht hier ausfuehrbar) — getestet wird
die VERTRAGS-Seite: beide Plugin-Manifeste (`pbp-plugin.json`) muessen
gegen die PBP-Manifest-Validierung bestehen, das TB-Manifest muss valides
JSON mit den noetigen Permissions sein, und der ics-Kern muss RFC-5545-
fest sein (Escaping, Folding, CRLF).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def tmp_db(tmp_path):
    from bewerbungs_assistent.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Test"})
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db
    db.close()


# ── ics: Escaping + Folding ──────────────────────────────────────────────


def test_ics_escape():
    from bewerbungs_assistent.services.ics_service import ics_escape
    assert ics_escape("Interview, 2. Runde; vor Ort") == \
        "Interview\\, 2. Runde\\; vor Ort"
    assert ics_escape("Zeile1\nZeile2\r\nZeile3") == "Zeile1\\nZeile2\\nZeile3"
    assert ics_escape("Back\\slash") == "Back\\\\slash"
    assert ics_escape(None) == ""


def test_ics_fold_75_oktette():
    from bewerbungs_assistent.services.ics_service import ics_fold
    kurz = "SUMMARY:kurz"
    assert ics_fold(kurz) == kurz
    lang = "SUMMARY:" + "x" * 200
    gefaltet = ics_fold(lang)
    zeilen = gefaltet.split("\r\n")
    assert len(zeilen) > 1
    assert all(len(z.encode("utf-8")) <= 75 for z in zeilen)
    assert all(z.startswith(" ") for z in zeilen[1:])  # Fortsetzung mit Space
    # Unfold ergibt das Original
    assert "".join([zeilen[0]] + [z[1:] for z in zeilen[1:]]) == lang
    # Multibyte (Umlaute) werden nicht zerschnitten
    umlaute = "SUMMARY:" + "ä" * 100
    for z in ics_fold(umlaute).split("\r\n"):
        z.encode("utf-8")  # wuerde bei zerschnittenem Zeichen nicht decodierbar sein
        assert len(z.encode("utf-8")) <= 75


def test_build_meetings_ics_escaped_und_vollstaendig(tmp_db):
    from bewerbungs_assistent.services.ics_service import build_meetings_ics
    app_id = tmp_db.add_application({
        "title": "PLM Consultant", "company": "Acme Solutions GmbH",
        "status": "interview",
    })
    tmp_db.add_meeting({
        "application_id": app_id,
        "title": "Interview, 2. Runde; Technik",
        "meeting_date": "2026-08-01T10:00:00",
        "meeting_end": "2026-08-01T11:30:00",
        "location": "Hamburg, Speicherstadt 1",
        "meeting_type": "interview",
        "notes": "Mitbringen:\nZeugnisse und Referenzen",
    })

    content, anzahl = build_meetings_ics(tmp_db)
    assert anzahl == 1
    assert content.startswith("BEGIN:VCALENDAR")
    assert "\r\n" in content and content.endswith("\r\n")
    assert "BEGIN:VEVENT" in content
    assert "DTSTART:20260801T100000" in content
    assert "DTEND:20260801T113000" in content
    # Escaping: Kommas/Semikolons/Notiz-Zeilenumbruch
    assert "SUMMARY:Interview\\, 2. Runde\\; Technik" in content
    assert "LOCATION:Hamburg\\, Speicherstadt 1" in content
    assert "Mitbringen:\\nZeugnisse" in content.replace("\r\n ", "")  # ueber Folding hinweg
    # Alle Zeilen <= 75 Oktette (Folding greift)
    for zeile in content.split("\r\n"):
        assert len(zeile.encode("utf-8")) <= 75


def test_build_meetings_ics_leer(tmp_db):
    from bewerbungs_assistent.services.ics_service import build_meetings_ics
    content, anzahl = build_meetings_ics(tmp_db)
    assert anzahl == 0
    assert "BEGIN:VEVENT" not in content
    assert content.startswith("BEGIN:VCALENDAR")


def test_endpoint_export_ics(tmp_db):
    import bewerbungs_assistent.dashboard as dash
    dash._db = tmp_db
    from fastapi.testclient import TestClient
    client = TestClient(dash.app)
    app_id = tmp_db.add_application({
        "title": "X", "company": "Y", "status": "interview"})
    tmp_db.add_meeting({
        "application_id": app_id, "title": "Kennenlernen",
        "meeting_date": "2026-08-02T09:00:00", "meeting_type": "interview",
    })
    resp = client.get("/api/meetings/export.ics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/calendar")
    assert "attachment" in resp.headers["content-disposition"]
    assert "BEGIN:VEVENT" in resp.text


def test_tool_termine_ics_exportieren(tmp_db, tmp_path, monkeypatch):
    import logging

    class FakeMCP:
        def __init__(self):
            self.tools = {}

        def tool(self):
            def deco(fn):
                self.tools[fn.__name__] = fn
                return fn
            return deco

    monkeypatch.setenv("BA_DATA_DIR", str(tmp_path))
    from bewerbungs_assistent.tools import export_tools
    mcp = FakeMCP()
    export_tools.register(mcp, tmp_db, logging.getLogger("test"))

    # Leerer Bestand -> ehrlicher Hinweis
    result = mcp.tools["termine_ics_exportieren"]()
    assert result["status"] == "leer"

    app_id = tmp_db.add_application({
        "title": "X", "company": "Y", "status": "interview"})
    tmp_db.add_meeting({
        "application_id": app_id, "title": "Zweitgespraech",
        "meeting_date": "2026-08-03T14:00:00", "meeting_type": "interview",
    })
    result = mcp.tools["termine_ics_exportieren"]()
    assert result["status"] == "exportiert"
    assert result["termine"] == 1
    datei = Path(result["datei"])
    assert datei.is_file()
    inhalt = datei.read_bytes().decode("utf-8")
    assert "Zweitgespraech" in inhalt
    assert "\r\n" in inhalt  # CRLF ueberlebt das Schreiben (newline='')


# ── Thunderbird-Add-on: Vertragsseite ────────────────────────────────────


def test_addon_manifest_valide():
    manifest = json.loads(
        (REPO / "plugins/thunderbird-pbp/manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 2
    perms = manifest["permissions"]
    for benoetigt in ("messagesRead", "menus", "storage", "notifications"):
        assert benoetigt in perms, benoetigt
    assert any(p.startswith("http://127.0.0.1") for p in perms)
    assert manifest["browser_specific_settings"]["gecko"]["strict_min_version"]
    # Referenzierte Dateien existieren
    ordner = REPO / "plugins/thunderbird-pbp"
    for f in ("background.js", "options.html", "options.js",
              "icon-32.png", "icon-64.png", "pbp-plugin.json", "README.md"):
        assert (ordner / f).is_file(), f


def test_beide_plugin_manifeste_bestehen_pbp_validierung():
    """Die pbp-plugin.json beider Referenz-Plugins muessen gegen die echte
    Pairing-Validierung bestehen — sonst scheitert Schritt 1 im README."""
    from bewerbungs_assistent.services.plugins import validate_manifest
    for pfad in ("plugins/watch-folder/pbp-plugin.json",
                 "plugins/thunderbird-pbp/pbp-plugin.json"):
        manifest = json.loads((REPO / pfad).read_text(encoding="utf-8"))
        fehler, norm = validate_manifest(manifest)
        assert fehler == [], f"{pfad}: {fehler}"
        assert "ingest:email" in norm["capabilities"]


def test_addon_background_nutzt_ingest_api():
    """Leichter Drift-Schutz: das Add-on spricht die richtigen Endpunkte."""
    bg = (REPO / "plugins/thunderbird-pbp/background.js").read_text(encoding="utf-8")
    assert "/api/v1/ingest/email" in bg
    assert "X-PBP-API-Key" in bg
    opts = (REPO / "plugins/thunderbird-pbp/options.js").read_text(encoding="utf-8")
    assert "/api/v1/ingest/ping" in opts
