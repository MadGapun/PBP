"""Tests fuer die beta.108-Bugfix-Welle.

Abgedeckt:
- #732  Geo-Filter: klar nicht-DACH Stellen werden beim Scrapen aussortiert
        (is_non_dach_location + save_jobs), manuelle/Email-Adds bleiben aktiv.
- #731  Folgt aus #732 (der Brazil-Fall der LawnStarter-Stellen wird vom
        Geo-Filter geblockt) — gemeinsam mit #732 geprueft.
- #733  stelle_manuell_anlegen: Hinweis wenn quelle='manuell' bleibt,
        kein Hinweis wenn aus URL abgeleitet.
- #734  Export -> Stilarchiv Auto-Save (anschreiben_exportieren) +
        upsert_document_version ('letzte Version gewinnt').
"""
import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_b108_test_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel: hart asserten, dass die DB im Temp-Verzeichnis
    # liegt (NIE die echte AppData-DB anfassen).
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    import shutil
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


# ===================== #732 — is_non_dach_location (pure) ================

@pytest.mark.parametrize("ort,erwartet", [
    ("Brazil", True),
    ("brasil", True),
    ("Remote (Florianópolis)", True),
    ("USA", True),
    ("US", True),
    ("Remote, US", True),
    ("London, UK", True),
    ("Bangalore, India", True),
    ("Paris, France", True),
    # DACH gewinnt immer
    ("Hamburg", False),
    ("Berlin", False),
    ("München", False),
    ("Wien, Österreich", False),
    ("Zürich, Schweiz", False),
    ("Wedel", False),
    ("Hamburg (Team in Brazil)", False),  # DACH-Marker schlaegt Auslands-Marker
    # Unsicher / leer / reines Remote -> NICHT filtern
    ("", False),
    ("Remote", False),
    ("Deutschlandweit", False),
    ("Worldwide", False),
    ("Europa", False),
])
def test_732_is_non_dach_location(ort, erwartet):
    from bewerbungs_assistent.services.geocoding_service import is_non_dach_location
    assert is_non_dach_location(ort) is erwartet, f"{ort!r} -> {erwartet}"


# ===================== #732 — save_jobs Geo-Filter =======================

def _job(hash_, title, source, location, url="https://example.com/x"):
    return {
        "hash": hash_, "title": title, "company": "TestCo",
        "source": source, "location": location, "url": url,
        "employment_type": "festanstellung", "score": 10,
    }


def _job_row(db, title):
    row = db.connect().execute(
        "SELECT is_active, dismiss_reason FROM jobs WHERE title=?", (title,)
    ).fetchone()
    return dict(row) if row else None


def test_732_scraper_nicht_dach_wird_aussortiert(setup_env):
    db, _ = setup_env
    res = db.save_jobs([_job("h1", "Job Brazil", "remotive", "Brazil")])
    assert res.get("ausland_erkannt") == 1
    row = _job_row(db, "Job Brazil")
    assert row["is_active"] == 0
    assert row["dismiss_reason"] == "zu_weit_entfernt"


def test_732_dach_bleibt_aktiv(setup_env):
    db, _ = setup_env
    res = db.save_jobs([_job("h2", "Job Hamburg", "remotive", "Hamburg")])
    assert res.get("ausland_erkannt") == 0
    assert _job_row(db, "Job Hamburg")["is_active"] == 1


def test_732_manuelle_quelle_ist_ausgenommen(setup_env):
    db, _ = setup_env
    # source 'manuell' steht in _URL_OPTIONAL_SOURCES -> nicht geo-gefiltert
    db.save_jobs([_job("h3", "Job Manuell Brazil", "manuell", "Brazil")])
    assert _job_row(db, "Job Manuell Brazil")["is_active"] == 1


def test_732_manual_entry_flag_schuetzt(setup_env):
    db, _ = setup_env
    j = _job("h4", "Job Flag Brazil", "linkedin", "Brazil")
    j["_manual_entry"] = True
    db.save_jobs([j])
    assert _job_row(db, "Job Flag Brazil")["is_active"] == 1


# ===================== #733 — stelle_manuell_anlegen Hinweis =============

def test_733_hinweis_bei_quelle_manuell(setup_env):
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "PLM Architekt Manuell", "firma": "ManuellCo",
    }))
    assert res.get("status") == "angelegt"
    assert "hinweis" in res
    assert "quelle" in res["hinweis"].lower()


def test_733_kein_hinweis_wenn_aus_url_abgeleitet(setup_env):
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "PLM Architekt LinkedIn", "firma": "LinkedInCo",
        "url": "https://www.linkedin.com/jobs/view/1234567890",
    }))
    assert res.get("status") == "angelegt"
    assert "hinweis" not in res, f"unerwarteter Hinweis: {res.get('hinweis')}"
    assert "linkedin" in res.get("nachricht", "").lower()


# ===================== #734 — upsert_document_version ====================

def test_734_upsert_letzte_version_gewinnt_application_id(setup_env):
    db, _ = setup_env
    db.upsert_document_version({"kind": "cover_letter", "title": "T1",
                                "content": "v1", "application_id": "app-xyz"})
    db.upsert_document_version({"kind": "cover_letter", "title": "T2",
                                "content": "v2", "application_id": "app-xyz"})
    versions = db.get_recent_document_versions("cover_letter")
    assert len(versions) == 1
    assert versions[0]["content"] == "v2"


def test_734_upsert_letzte_version_gewinnt_title(setup_env):
    db, _ = setup_env
    db.upsert_document_version({"kind": "cover_letter", "title": "FirmaX — Stelle",
                                "content": "alt"})
    db.upsert_document_version({"kind": "cover_letter", "title": "FirmaX — Stelle",
                                "content": "neu"})
    versions = db.get_recent_document_versions("cover_letter")
    assert len(versions) == 1 and versions[0]["content"] == "neu"


def test_734_add_document_version_bleibt_additiv(setup_env):
    db, _ = setup_env
    db.add_document_version({"kind": "cv", "title": "X", "content": "a"})
    db.add_document_version({"kind": "cv", "title": "X", "content": "b"})
    assert len(db.get_recent_document_versions("cv")) == 2


def test_734_upsert_kollidiert_nicht_ueber_kind(setup_env):
    db, _ = setup_env
    db.upsert_document_version({"kind": "cover_letter", "title": "T", "content": "cl"})
    db.upsert_document_version({"kind": "cv", "title": "T", "content": "cv"})
    assert len(db.get_recent_document_versions("cover_letter")) == 1
    assert len(db.get_recent_document_versions("cv")) == 1


# ===================== #734 — _auto_save_stilarchiv Helper ===============

def test_734_auto_save_helper_dedup(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.tools.export_tools import _auto_save_stilarchiv
    v1 = _auto_save_stilarchiv(db, "cover_letter", "Text A", "FirmaX", "StelleY")
    v2 = _auto_save_stilarchiv(db, "cover_letter", "Text B", "FirmaX", "StelleY")
    assert v1 and v2 and v1 != v2
    versions = db.get_recent_document_versions("cover_letter")
    assert len(versions) == 1
    assert versions[0]["content"] == "Text B"


def test_734_auto_save_helper_leerer_text(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.tools.export_tools import _auto_save_stilarchiv
    assert _auto_save_stilarchiv(db, "cover_letter", "   ", "F", "S") is None
    assert len(db.get_recent_document_versions("cover_letter")) == 0


# ===================== #734 — anschreiben_exportieren End-to-End =========

def test_734_anschreiben_export_archiviert(setup_env):
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "anschreiben_exportieren", {
        "text": "Sehr geehrte Damen und Herren, hiermit bewerbe ich mich.",
        "stelle": "Senior Dev", "firma": "AcmeGmbH", "format": "txt",
    }))
    assert "ki_blockiert" not in res, f"KI-Gate blockierte: {res}"
    assert res.get("status") == "erstellt"
    assert res.get("stilarchiv_version_id")
    # Gegenprobe ueber denselben (Server-)DB-Pfad
    kontext = _result(_call(mcp, "stilarchiv_kontext", {"kind": "cover_letter"}))
    assert kontext.get("anzahl", 0) >= 1


# ===================== #736 — stil_auswertung Interview-Quote ============

def _setup_stil_app(db, app_id, status, style, *, interview_event=False,
                    has_reached=0):
    conn = db.connect()
    conn.execute(
        "INSERT INTO applications (id, title, company, status, "
        "has_reached_interview, profile_id) VALUES (?, ?, ?, ?, ?, ?)",
        (app_id, f"Title {app_id}", f"Co {app_id}", status, has_reached,
         db.get_active_profile_id()),
    )
    conn.execute(
        "INSERT INTO application_events (application_id, status, event_date, notes) "
        "VALUES (?, 'stil_tracking', ?, ?)",
        (app_id, "2026-06-15T10:00:00+00:00", f"Anschreiben-Stil: {style}"),
    )
    if interview_event:
        conn.execute(
            "INSERT INTO application_events (application_id, status, event_date, notes) "
            "VALUES (?, 'interview', ?, '')",
            (app_id, "2026-06-14T10:00:00+00:00"),
        )
    conn.commit()


def test_736_interview_via_timeline_und_flag(setup_env):
    """Verlauf interview -> abgelehnt zaehlt als Interview-Treffer (#736)."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    # D1: final abgelehnt, aber Interview-EVENT vorhanden (Flag bewusst 0)
    _setup_stil_app(db, "d1", "abgelehnt", "direkt", interview_event=True, has_reached=0)
    # D2: final abgelehnt, nie ein Interview
    _setup_stil_app(db, "d2", "abgelehnt", "direkt")
    # D3: final abgelehnt, aber kanonisches Flag gesetzt (kein Event)
    _setup_stil_app(db, "d3", "abgelehnt", "direkt", has_reached=1)

    res = _result(_call(mcp, "stil_auswertung", {}))
    assert res.get("status") == "ok", res
    direkt = res["stile"]["direkt"]
    assert direkt["anzahl"] == 3
    assert direkt["interviews"] == 2, direkt          # D1 (Event) + D3 (Flag)
    assert direkt["absagen"] == 3
    assert direkt["absage_nach_interview"] == 2
    assert direkt["absage_ohne_interview"] == 1
    assert direkt["interview_quote"] == 66.7
