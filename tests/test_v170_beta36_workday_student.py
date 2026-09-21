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
    """Die Studenten- und Konzern-Quellen sind erreichbar.

    #1070: sie haengen nicht mehr am Schluessel, sondern an der FORM
    (Studium/Praktikum) und am NIVEAU (ab Spezialist). Die ABSICHT ist
    unveraendert — ein Studienprofil bekommt die Praktikums-Boersen,
    ein Senior die Konzern-Quellen.
    """
    from bewerbungs_assistent.services import berufsfeld
    for quelle in ("praktikum_de", "studentjob", "berufsstart"):
        assert quelle in berufsfeld.FORM_QUELLEN["werkstudent"]
        assert quelle in berufsfeld.FORM_QUELLEN["praktikum"]
    assert "workday_dax" in berufsfeld.NIVEAU_QUELLEN["spezialist"]
    assert "workday_dax" in berufsfeld.NIVEAU_QUELLEN["experte"]


def test_clusters_only_known_sources():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    from bewerbungs_assistent.services import berufsfeld
    known = set(SOURCE_REGISTRY.keys())
    tabellen = (("FELD", berufsfeld.FELD_QUELLEN),
                ("FORM", berufsfeld.FORM_QUELLEN),
                ("NIVEAU", berufsfeld.NIVEAU_QUELLEN))
    for name, tabelle in tabellen:
        for schluessel, sources in tabelle.items():
            for src in sources:
                assert src in known, (
                    f"{name}[{schluessel}] -> Ghost-Source {src}")


# ============= Praktikum.de ===============
# v1.7.107 (B53): der RSS-Feed ist entfernt (404, gemessen 14.09.2026). Der
# Adapter sucht ueber das Formular der Seite; die Faelle dazu stehen in
# test_v17107_kartenleser_b53.py.


def test_praktikum_de_fragt_den_toten_feed_nicht_mehr_ab():
    import inspect
    from bewerbungs_assistent.job_scraper import praktikum_de
    assert "rss.xml" not in inspect.getsource(praktikum_de)


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
