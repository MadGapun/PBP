"""Tests fuer v1.7.0-beta.36 — #590 Aufgabe B.3 + B.4.

Workday-DAX-Cluster + Student-Cluster (Praktikum.de, StudentJob, Berufsstart)
+ Frontend Recommendations-Card.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ============= SOURCE_REGISTRY ===============

def test_source_registry_has_new_clusters():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY, _SCRAPER_MAP
    for src in ("praktikum_de", "studentjob", "berufsstart", "workday_dax"):
        assert src in SOURCE_REGISTRY
        assert src in _SCRAPER_MAP


def test_clusters_use_new_sources():
    from bewerbungs_assistent.services.profile_classifier import (
        PROFILE_TYPE_CLUSTERS
    )
    assert "praktikum_de" in PROFILE_TYPE_CLUSTERS["student"]
    assert "studentjob" in PROFILE_TYPE_CLUSTERS["student"]
    assert "berufsstart" in PROFILE_TYPE_CLUSTERS["student"]
    assert "workday_dax" in PROFILE_TYPE_CLUSTERS["tech_senior"]
    assert "workday_dax" in PROFILE_TYPE_CLUSTERS["engineering_senior"]
    assert "workday_dax" in PROFILE_TYPE_CLUSTERS["executive"]


def test_clusters_only_known_sources():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    from bewerbungs_assistent.services.profile_classifier import (
        PROFILE_TYPE_CLUSTERS
    )
    known = set(SOURCE_REGISTRY.keys())
    for cluster, sources in PROFILE_TYPE_CLUSTERS.items():
        for src in sources:
            assert src in known, f"Cluster {cluster} -> Ghost-Source {src}"


# ============= Praktikum.de RSS ===============

PRAKTIKUM_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Praktikum.de</title>
  <item>
    <title>Werkstudent Marketing (m/w/d)</title>
    <link>https://www.praktikum.de/p/123</link>
    <description>Wir suchen Werkstudent Marketing in Hamburg.</description>
  </item>
  <item>
    <title>Praktikum Software-Entwicklung</title>
    <link>https://www.praktikum.de/p/456</link>
    <description>Praktikum Backend Python.</description>
  </item>
</channel>
</rss>
"""


def test_praktikum_de_parses_rss():
    from bewerbungs_assistent.job_scraper.praktikum_de import search_praktikum_de
    resp = MagicMock()
    resp.status_code = 200
    resp.content = PRAKTIKUM_RSS
    with patch("bewerbungs_assistent.job_scraper.praktikum_de.httpx.Client") as mock_cls:
        client = MagicMock()
        client.get.return_value = resp
        mock_cls.return_value.__enter__.return_value = client
        jobs = search_praktikum_de({"keywords": {"general": []}})
    assert len(jobs) == 2
    assert all(j["employment_type"] == "praktikum" for j in jobs)
    assert all(j["source"] == "praktikum_de" for j in jobs)


def test_praktikum_de_keyword_filter():
    from bewerbungs_assistent.job_scraper.praktikum_de import search_praktikum_de
    resp = MagicMock()
    resp.status_code = 200
    resp.content = PRAKTIKUM_RSS
    with patch("bewerbungs_assistent.job_scraper.praktikum_de.httpx.Client") as mock_cls:
        client = MagicMock()
        client.get.return_value = resp
        mock_cls.return_value.__enter__.return_value = client
        jobs = search_praktikum_de({"keywords": {"general": ["python"]}})
    titles = [j["title"] for j in jobs]
    assert "Praktikum Software-Entwicklung" in titles
    assert "Werkstudent Marketing (m/w/d)" not in titles


# ============= StudentJob ===============

STUDENTJOB_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <item>
    <title>Aushilfe Logistik</title>
    <link>https://www.studentjob.de/j/1</link>
    <description>Aushilfe in Bremen.</description>
  </item>
</channel>
</rss>
"""


def test_studentjob_parses_rss():
    from bewerbungs_assistent.job_scraper.studentjob import search_studentjob
    resp = MagicMock()
    resp.status_code = 200
    resp.content = STUDENTJOB_RSS
    with patch("bewerbungs_assistent.job_scraper.studentjob.httpx.Client") as mock_cls:
        client = MagicMock()
        client.get.return_value = resp
        mock_cls.return_value.__enter__.return_value = client
        jobs = search_studentjob({"keywords": {"general": []}})
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Aushilfe Logistik"
    assert jobs[0]["employment_type"] == "werkstudent"


# ============= Berufsstart ===============

BERUFSSTART_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <item>
    <title>Trainee-Programm Finance</title>
    <link>https://www.berufsstart.de/j/1</link>
    <description>Trainee-Programm in Frankfurt.</description>
  </item>
</channel>
</rss>
"""


def test_berufsstart_parses_rss():
    from bewerbungs_assistent.job_scraper.berufsstart import search_berufsstart
    resp = MagicMock()
    resp.status_code = 200
    resp.content = BERUFSSTART_RSS
    with patch("bewerbungs_assistent.job_scraper.berufsstart.httpx.Client") as mock_cls:
        client = MagicMock()
        client.get.return_value = resp
        mock_cls.return_value.__enter__.return_value = client
        jobs = search_berufsstart({"keywords": {"general": []}})
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Trainee-Programm Finance"


# ============= Workday-DAX ===============

WORKDAY_JSON = {
    "jobPostings": [
        {
            "title": "Senior Software Engineer",
            "externalPath": "/job/Munich/Software-Engineer_R-12345",
            "locationsText": "Munich, Germany",
        },
        {
            "title": "Werkstudent IT",
            "externalPath": "/job/Berlin/Werkstudent-IT_R-67890",
            "locationsText": "Berlin",
        },
    ]
}


def test_workday_dax_parses_json():
    from bewerbungs_assistent.job_scraper.workday_dax import search_workday_dax
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = WORKDAY_JSON
    with patch("bewerbungs_assistent.job_scraper.workday_dax.httpx.Client") as mock_cls:
        client = MagicMock()
        client.post.return_value = resp
        mock_cls.return_value.__enter__.return_value = client
        jobs = search_workday_dax({"keywords": {"general": []}})
    # 10 default firmen, jede liefert 2 Stellen via Mock
    assert len(jobs) >= 2
    assert all(j["source"] == "workday_dax" for j in jobs)


def test_workday_dax_keyword_filter():
    from bewerbungs_assistent.job_scraper.workday_dax import search_workday_dax
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = WORKDAY_JSON
    with patch("bewerbungs_assistent.job_scraper.workday_dax.httpx.Client") as mock_cls:
        client = MagicMock()
        client.post.return_value = resp
        mock_cls.return_value.__enter__.return_value = client
        jobs = search_workday_dax({
            "keywords": {"general": ["senior"], "regionen": []}
        })
    # Senior matched titles only
    assert all("senior" in j["title"].lower() for j in jobs)


def test_workday_dax_user_entry_parsing():
    from bewerbungs_assistent.job_scraper.workday_dax import _parse_user_entry
    parsed = _parse_user_entry("BMW|bmw|wd1|external")
    assert parsed == ("BMW", "bmw", "wd1", "external")
    invalid = _parse_user_entry("incomplete")
    assert invalid is None


def test_workday_dax_default_firmen():
    from bewerbungs_assistent.job_scraper.workday_dax import DEFAULT_FIRMEN
    firmen_namen = {f[0] for f in DEFAULT_FIRMEN}
    assert "Siemens" in firmen_namen
    assert "SAP" in firmen_namen
    assert "Bosch" in firmen_namen


def test_workday_dax_url_pattern():
    from bewerbungs_assistent.job_scraper.workday_dax import _build_url
    url = _build_url("siemens", "wd5", "siemens")
    assert url == "https://siemens.wd5.myworkdayjobs.com/wday/cxs/siemens/siemens/jobs"


# ============= Frontend Component ===============

def test_recommended_sources_card_in_settings():
    p = PROJECT_ROOT / "frontend" / "src" / "pages" / "SettingsPage.jsx"
    content = p.read_text(encoding="utf-8")
    assert "RecommendedSourcesCard" in content
    assert "/api/profile/recommended-sources" in content
    assert "fehlende empfohlene Quelle" in content
