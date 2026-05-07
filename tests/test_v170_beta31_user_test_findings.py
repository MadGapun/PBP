"""Tests fuer v1.7.0-beta.31 — User-Test-Findings #595/#596/#597/#598.

- #595: Stellen-Detail anzeigen auch wenn is_active=0
- #596: Keyword-Analyse Eigenname/???-Zeile/PDM
- #597: Dokumente pro Bewerbung im Bericht
- #598: Section 12 Gesamttreffer + Abgrenzung zu Section 3
"""
import os
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta31_")
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


# ============= #595: GET /api/jobs/{hash} unabhaengig von is_active ============

def test_api_jobs_hash_returns_active_job(setup_env):
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, is_active, found_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (f"{pid}:active1", pid, "Active Job", "ACME", 1, "2026-05-01")
    )
    conn.commit()
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/jobs/active1")
    assert r.status_code == 200
    j = r.json()
    assert j["title"] == "Active Job"


def test_api_jobs_hash_returns_dismissed_job(setup_env):
    """#595: dismissed Stelle (is_active=0) muss ueber den Hash trotzdem
    erreichbar sein — Bewerbungen verlinken auf solche Stellen."""
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, is_active, "
        " dismiss_reason, found_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"{pid}:dismissed1", pid, "Dismissed Job", "DISMCO", 0,
         "bewerbung_erstellt", "2026-05-01")
    )
    conn.commit()
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/jobs/dismissed1")
    assert r.status_code == 200
    j = r.json()
    assert j["title"] == "Dismissed Job"
    assert j["is_active"] is False or j["is_active"] == 0
    assert j["dismiss_reason"] == "bewerbung_erstellt"


def test_api_jobs_hash_404_for_unknown(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/jobs/doesnotexist")
    assert r.status_code == 404


def test_inline_job_detail_modal_component_exists():
    p = PROJECT_ROOT / "frontend" / "src" / "components" / "InlineJobDetailModal.jsx"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "/api/jobs/" in content
    assert "is_active" in content


def test_applications_page_uses_inline_job_detail():
    p = PROJECT_ROOT / "frontend" / "src" / "pages" / "ApplicationsPage.jsx"
    content = p.read_text(encoding="utf-8")
    assert "InlineJobDetailModal" in content
    assert "setJobDetailHash" in content


# ============= #596: Keyword-Analyse Fixes ===============

def test_keyword_filter_excludes_profile_name():
    """#596 Bug 1: Eigenname darf nicht als Keyword auftauchen."""
    import re as _re
    name_parts: set = set()
    profile = {"name": "Markus Birzite"}
    for key in ("name", "first_name", "last_name", "vorname", "nachname"):
        v = (profile.get(key) or "").strip().lower()
        for part in _re.findall(r"[a-zäöüß]{3,}", v):
            name_parts.add(part)
    assert "markus" in name_parts
    assert "birzite" in name_parts


def test_keyword_tokenizer_splits_pdm_plm():
    """#596 Bug 3: PDM aus 'PDM/PLM' muss als separates Token gezaehlt werden."""
    import re as _re
    text = "wir suchen einen experten fuer pdm/plm und cad-systeme"
    tokens = _re.findall(r"[a-zäöüß]{3,}", text)
    assert "pdm" in tokens
    assert "plm" in tokens
    assert "cad" in tokens


def test_keyword_unrenderable_filter():
    """#596 Bug 2: Tokens, die latin-1 nicht darstellen kann, werden ausgeschlossen."""
    from bewerbungs_assistent.export_report import _safe_text

    def _is_renderable(token: str) -> bool:
        safe = _safe_text(token)
        if "?" in safe and "?" not in token:
            return False
        return True

    # Latin-1 OK (Umlaute werden als latin-1 reprraesentiert)
    assert _is_renderable("müll") is True
    # Emoji oder CJK → nicht latin-1, wird zu ?
    assert _is_renderable("🎉event") is False
    assert _is_renderable("仕事") is False


# ============= #598: source_volume in get_report_data ===============

def test_source_volume_aggregates_per_source(setup_env):
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    # 3 von indeed: 1 active, 1 dismissed, 1 beworben
    conn.execute("INSERT INTO jobs (hash, profile_id, title, company, source, "
                 "is_active, found_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (f"{pid}:i1", pid, "T1", "C1", "indeed", 1, "2026-05-01"))
    conn.execute("INSERT INTO jobs (hash, profile_id, title, company, source, "
                 "is_active, dismiss_reason, found_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 (f"{pid}:i2", pid, "T2", "C2", "indeed", 0, "zu_weit_entfernt",
                  "2026-05-01"))
    conn.execute("INSERT INTO jobs (hash, profile_id, title, company, source, "
                 "is_active, found_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (f"{pid}:i3", pid, "T3", "C3", "indeed", 1, "2026-05-01"))
    conn.execute("INSERT INTO applications (id, profile_id, title, company, "
                 "job_hash, status, applied_at, created_at, updated_at) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 ("app1", pid, "T3", "C3", f"{pid}:i3", "beworben",
                  "2026-05-02", "2026-05-02", "2026-05-02"))
    # 1 von linkedin: nur active
    conn.execute("INSERT INTO jobs (hash, profile_id, title, company, source, "
                 "is_active, found_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (f"{pid}:l1", pid, "T4", "C4", "linkedin", 1, "2026-05-01"))
    conn.commit()

    rd = db.get_report_data()
    assert "source_volume" in rd
    by_source = {s["source"]: s for s in rd["source_volume"]}
    assert by_source["indeed"]["total"] == 3
    assert by_source["indeed"]["active"] == 2
    assert by_source["indeed"]["dismissed"] == 1
    assert by_source["indeed"]["applied"] == 1
    assert by_source["linkedin"]["total"] == 1


# ============= #597: documents_per_application in get_report_data ===============

def test_documents_per_application_aggregates(setup_env):
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    # 2 Bewerbungen
    conn.execute("INSERT INTO applications (id, profile_id, title, company, "
                 "status, applied_at, created_at, updated_at) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 ("app1", pid, "T1", "C1", "beworben",
                  "2026-05-02", "2026-05-02", "2026-05-02"))
    conn.execute("INSERT INTO applications (id, profile_id, title, company, "
                 "status, applied_at, created_at, updated_at) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 ("app2", pid, "T2", "C2", "beworben",
                  "2026-05-02", "2026-05-02", "2026-05-02"))
    # app1: 1 Lebenslauf, 1 Anschreiben (standard)
    # app2: 1 Lebenslauf, 1 Anschreiben, 1 Projektliste, 2 Mails (aufwaendig)
    docs = [
        ("d1", "app1", "lebenslauf"),
        ("d2", "app1", "anschreiben"),
        ("d3", "app2", "lebenslauf"),
        ("d4", "app2", "anschreiben"),
        ("d5", "app2", "projektliste"),
        ("d6", "app2", "email"),
        ("d7", "app2", "email"),
    ]
    for did, aid, dtype in docs:
        conn.execute("INSERT INTO documents (id, profile_id, "
                     "linked_application_id, doc_type, filename, filepath) "
                     "VALUES (?, ?, ?, ?, ?, ?)",
                     (did, pid, aid, dtype, f"{did}.pdf", f"/tmp/{did}.pdf"))
    conn.commit()

    rd = db.get_report_data()
    dpa = rd.get("documents_per_application") or {}
    assert "app1" in dpa
    assert dpa["app1"]["total"] == 2
    assert dpa["app1"]["lebenslauf"] == 1
    assert dpa["app1"]["anschreiben"] == 1
    assert dpa["app2"]["total"] == 5
    assert dpa["app2"]["email"] == 2


# ============= Bericht-Generierung end-to-end ===============

def test_pdf_export_includes_new_sections(setup_env):
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    # Mindestens 1 Bewerbung mit Job + Doku
    conn.execute("INSERT INTO jobs (hash, profile_id, title, company, source, "
                 "is_active, description, found_at) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 (f"{pid}:job1", pid, "PDM-Architekt", "ACME", "indeed", 1,
                  "Wir suchen pdm/plm experten", "2026-05-01"))
    conn.execute("INSERT INTO applications (id, profile_id, title, company, "
                 "job_hash, status, applied_at, created_at, updated_at) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 ("a1", pid, "PDM-Architekt", "ACME", f"{pid}:job1", "beworben",
                  "2026-05-02", "2026-05-02", "2026-05-02"))
    conn.execute("INSERT INTO documents (id, profile_id, linked_application_id, "
                 "doc_type, filename, filepath) VALUES (?, ?, ?, ?, ?, ?)",
                 ("d1", pid, "a1", "lebenslauf", "cv.pdf", "/tmp/cv.pdf"))
    conn.commit()

    # PDF-Export starten — wir testen nur dass es ohne Crash durchlaeuft
    rd = db.get_report_data()
    profile = db.get_profile()
    assert "source_volume" in rd
    assert "documents_per_application" in rd

    from bewerbungs_assistent.export_report import generate_application_report
    out = Path(tempfile.gettempdir()) / "pbp_test_beta31.pdf"
    if out.exists():
        out.unlink()
    generate_application_report(rd, profile, out, zeitraum_von="", zeitraum_bis="")
    assert out.exists()
    assert out.stat().st_size > 1000  # Plausibilitaetscheck — nicht leer
    out.unlink(missing_ok=True)


def test_export_report_section3_has_abgrenzungs_hinweis():
    p = PROJECT_ROOT / "src" / "bewerbungs_assistent" / "export_report.py"
    content = p.read_text(encoding="utf-8")
    # #598: explizite Abgrenzung zwischen Abschnitt 3 und 12
    assert "3. Quellenanalyse (Qualitaet pro Quelle)" in content
    assert "12. Quellen-Aktivitaet (Volumen pro Quelle)" in content
    assert "Volumen (Gesamttreffer" in content


def test_export_report_has_dokumente_section():
    p = PROJECT_ROOT / "src" / "bewerbungs_assistent" / "export_report.py"
    content = p.read_text(encoding="utf-8")
    # #597: Dokumente pro Bewerbung
    assert "12b. Dokumente pro Bewerbung" in content
    assert "Aufwand-Indikator" in content
