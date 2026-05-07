"""Tests fuer v1.7.0-beta.35 — #590 Aufgabe B.1 + B.2 + B.5.

Profile-Detection + Cluster-Definitionen + Tech-Remote-Cluster
(Himalayas/Remotive/RemoteOK).
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta35_")
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


# ============= Profile-Detection ===============

def test_detect_no_profile():
    from bewerbungs_assistent.services.profile_classifier import detect_profile_type
    out = detect_profile_type(None)
    assert out["type"] == "mixed"


def test_detect_student():
    from bewerbungs_assistent.services.profile_classifier import detect_profile_type
    profile = {
        "education": [{"degree": "Bachelor Informatik", "end_year": "2027"}],
        "positions": [],
        "skills": [],
    }
    out = detect_profile_type(profile)
    assert out["type"] == "student"
    assert out["confidence"] >= 0.8


def test_detect_service():
    from bewerbungs_assistent.services.profile_classifier import detect_profile_type
    profile = {
        "positions": [{
            "title": "Verkaeuferin im Einzelhandel",
            "start_date": "2020-01-01",
        }],
        "skills": [{"name": "Kundenservice"}],
    }
    out = detect_profile_type(profile)
    assert out["type"] == "service"


def test_detect_trade():
    from bewerbungs_assistent.services.profile_classifier import detect_profile_type
    profile = {
        "positions": [{
            "title": "Geselle Schreiner",
            "start_date": "2018-06-01",
        }],
        "skills": [],
    }
    out = detect_profile_type(profile)
    assert out["type"] == "trade"


def test_detect_engineering_senior():
    from bewerbungs_assistent.services.profile_classifier import detect_profile_type
    profile = {
        "positions": [{
            "title": "Senior PLM-Architekt",
            "start_date": "2010-01-01",
        }],
        "skills": [{"name": "PLM"}, {"name": "PDM"}, {"name": "CAD"}],
    }
    out = detect_profile_type(profile)
    assert out["type"] == "engineering_senior"


def test_detect_tech_senior():
    from bewerbungs_assistent.services.profile_classifier import detect_profile_type
    profile = {
        "positions": [{
            "title": "Senior Backend Developer",
            "start_date": "2015-01-01",
        }],
        "skills": [{"name": "Python"}, {"name": "FastAPI"}],
    }
    out = detect_profile_type(profile)
    assert out["type"] == "tech_senior"


def test_detect_tech_junior():
    from bewerbungs_assistent.services.profile_classifier import detect_profile_type
    this_year = datetime.now().year
    profile = {
        "positions": [{
            "title": "Junior Frontend Engineer",
            "start_date": f"{this_year - 1}-01-01",
        }],
        "skills": [{"name": "React"}],
    }
    out = detect_profile_type(profile)
    assert out["type"] == "tech_junior"


def test_detect_freelance():
    from bewerbungs_assistent.services.profile_classifier import detect_profile_type
    profile = {
        "positions": [{
            "title": "Freelance Berater",
            "start_date": "2018-01-01",
        }],
        "skills": [],
    }
    out = detect_profile_type(profile)
    assert out["type"] == "freelance"


def test_detect_executive():
    from bewerbungs_assistent.services.profile_classifier import detect_profile_type
    profile = {
        "positions": [{
            "title": "Geschaeftsfuehrer Operations",
            "start_date": "2010-01-01",
        }],
        "skills": [],
    }
    out = detect_profile_type(profile)
    assert out["type"] == "executive"


# ============= recommend_sources ===============

def test_recommend_sources_returns_list():
    from bewerbungs_assistent.services.profile_classifier import recommend_sources
    profile = {"positions": [{"title": "Verkaeuferin", "start_date": "2020-01-01"}]}
    out = recommend_sources(profile)
    assert "recommended" in out
    assert isinstance(out["recommended"], list)
    assert len(out["recommended"]) >= 3
    # Service-Cluster MUSS bundesagentur + meinestadt enthalten
    assert "bundesagentur" in out["recommended"]
    assert "meinestadt" in out["recommended"]


def test_recommend_sources_for_tech_senior_includes_remote_cluster():
    from bewerbungs_assistent.services.profile_classifier import recommend_sources
    profile = {
        "positions": [{
            "title": "Senior Software Architect",
            "start_date": "2010-01-01",
        }],
        "skills": [{"name": "Python"}],
    }
    out = recommend_sources(profile)
    assert "himalayas" in out["recommended"]
    assert "remotive" in out["recommended"]


def test_clusters_only_reference_known_sources():
    """Sicherheits-Test: jeder Cluster-Eintrag muss eine in SOURCE_REGISTRY
    bekannte Quellen-ID sein — sonst kommt der User auf Ghost-Quellen."""
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    from bewerbungs_assistent.services.profile_classifier import (
        PROFILE_TYPE_CLUSTERS
    )
    known = set(SOURCE_REGISTRY.keys())
    for cluster, sources in PROFILE_TYPE_CLUSTERS.items():
        for src in sources:
            assert src in known, f"Cluster {cluster!r} referenziert unbekannte Quelle {src!r}"


# ============= API ===============

def test_api_recommended_sources(setup_env):
    db = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    conn.execute(
        "INSERT INTO positions (profile_id, title, company, start_date) "
        "VALUES (?, ?, ?, ?)",
        (pid, "Senior Backend Developer", "ACME", "2014-01-01")
    )
    conn.commit()
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.get("/api/profile/recommended-sources")
    assert r.status_code == 200
    j = r.json()
    assert j["type"] == "tech_senior"
    assert "recommended" in j
    assert len(j["recommended"]) >= 3


# ============= SOURCE_REGISTRY: 3 neue Tech-Remote-Quellen ===============

def test_source_registry_has_remote_cluster():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY, _SCRAPER_MAP
    for src in ("himalayas", "remotive", "remoteok"):
        assert src in SOURCE_REGISTRY
        assert src in _SCRAPER_MAP


# ============= Himalayas ===============

def test_himalayas_parses_jobs():
    from bewerbungs_assistent.job_scraper.himalayas import search_himalayas
    sample = {
        "jobs": [
            {
                "title": "Senior Backend",
                "companyName": "AcmeCo",
                "applicationLink": "https://example.com/x",
                "description": "Python and FastAPI.",
                "guid": "abc",
            }
        ]
    }
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = sample
    with patch("bewerbungs_assistent.job_scraper.himalayas.httpx.Client") as mock_cls:
        client = MagicMock()
        client.get.return_value = resp
        mock_cls.return_value.__enter__.return_value = client
        jobs = search_himalayas({"keywords": {"general": ["python"]}})
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Senior Backend"
    assert jobs[0]["source"] == "himalayas"
    assert jobs[0]["remote_level"] == "remote"


def test_himalayas_filters_by_keyword():
    from bewerbungs_assistent.job_scraper.himalayas import search_himalayas
    sample = {
        "jobs": [
            {"title": "Java Developer", "companyName": "X",
             "description": "Java enterprise.", "guid": "1"},
            {"title": "Python Developer", "companyName": "Y",
             "description": "Python data pipelines.", "guid": "2"},
        ]
    }
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = sample
    with patch("bewerbungs_assistent.job_scraper.himalayas.httpx.Client") as mock_cls:
        client = MagicMock()
        client.get.return_value = resp
        mock_cls.return_value.__enter__.return_value = client
        jobs = search_himalayas({"keywords": {"general": ["python"]}})
    titles = [j["title"] for j in jobs]
    assert "Python Developer" in titles
    assert "Java Developer" not in titles


# ============= Remotive ===============

def test_remotive_parses_jobs():
    from bewerbungs_assistent.job_scraper.remotive import search_remotive
    sample = {
        "jobs": [
            {
                "title": "Backend Engineer",
                "company_name": "RemoteCo",
                "url": "https://remotive.com/job/1",
                "candidate_required_location": "Worldwide",
                "description": "We build APIs in Go.",
                "id": 1,
                "job_type": "full_time",
            }
        ]
    }
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = sample
    with patch("bewerbungs_assistent.job_scraper.remotive.httpx.Client") as mock_cls:
        client = MagicMock()
        client.get.return_value = resp
        mock_cls.return_value.__enter__.return_value = client
        jobs = search_remotive({"keywords": {"general": []}})
    assert len(jobs) == 1
    assert jobs[0]["source"] == "remotive"
    assert jobs[0]["remote_level"] == "remote"


# ============= RemoteOK ===============

def test_remoteok_skips_first_metadata_element():
    from bewerbungs_assistent.job_scraper.remoteok import search_remoteok
    sample = [
        {"legal": "metadata"},  # erstes Element ist Metadaten
        {
            "position": "Frontend Engineer",
            "company": "RemoteCorp",
            "url": "https://remoteok.com/job/1",
            "description": "React + TypeScript.",
            "id": 1,
            "tags": ["react", "typescript"],
        }
    ]
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = sample
    with patch("bewerbungs_assistent.job_scraper.remoteok.httpx.Client") as mock_cls:
        client = MagicMock()
        client.get.return_value = resp
        mock_cls.return_value.__enter__.return_value = client
        jobs = search_remoteok({"keywords": {"general": ["react"]}})
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Frontend Engineer"
    assert jobs[0]["source"] == "remoteok"


def test_remoteok_filters_by_tag():
    from bewerbungs_assistent.job_scraper.remoteok import search_remoteok
    sample = [
        {"legal": "metadata"},
        {"position": "Backend", "company": "X",
         "description": "Java.", "id": 1, "tags": ["java"]},
        {"position": "Backend", "company": "Y",
         "description": "Pure infrastructure.", "id": 2, "tags": ["python"]},
    ]
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = sample
    with patch("bewerbungs_assistent.job_scraper.remoteok.httpx.Client") as mock_cls:
        client = MagicMock()
        client.get.return_value = resp
        mock_cls.return_value.__enter__.return_value = client
        jobs = search_remoteok({"keywords": {"general": ["python"]}})
    assert len(jobs) == 1
    assert jobs[0]["company"] == "Y"
