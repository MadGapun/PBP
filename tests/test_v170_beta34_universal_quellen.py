"""Tests fuer v1.7.0-beta.34 — #590 Aufgabe A: Universelle Quellen.

3 neue Adapter (Personio, Workable, Meinestadt) — Tests laufen ohne
echte HTTP-Calls (httpx wird gemockt) damit kein Netz-Zugriff noetig ist.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


# ============= SOURCE_REGISTRY ===============

def test_source_registry_lists_new_sources():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    assert "personio" in SOURCE_REGISTRY
    assert "workable" in SOURCE_REGISTRY
    assert "meinestadt" in SOURCE_REGISTRY


def test_dispatcher_dispatches_new_sources():
    from bewerbungs_assistent.job_scraper import _SCRAPER_MAP
    assert _SCRAPER_MAP["personio"] == ("personio", "search_personio")
    assert _SCRAPER_MAP["workable"] == ("workable", "search_workable")
    assert _SCRAPER_MAP["meinestadt"] == ("meinestadt", "search_meinestadt")


# ============= Personio ===============

PERSONIO_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<workzag-jobs>
  <position>
    <id>123</id>
    <name>Senior Python Developer</name>
    <office>Hamburg</office>
    <department>Engineering</department>
    <employmentType>permanent</employmentType>
    <schedule>full-time</schedule>
    <description>Wir suchen einen Python Experten fuer unser Team.</description>
  </position>
  <position>
    <id>456</id>
    <name>Werkstudent Marketing</name>
    <office>Berlin</office>
    <employmentType>intern</employmentType>
    <schedule>part-time</schedule>
    <description>Werkstudenten-Stelle im Marketing.</description>
  </position>
</workzag-jobs>
"""


def _mock_response(content: bytes, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    return resp


def test_personio_parses_xml_and_filters():
    from bewerbungs_assistent.job_scraper.personio import search_personio

    def fake_get(url, **kwargs):
        return _mock_response(PERSONIO_XML)

    with patch("bewerbungs_assistent.job_scraper.personio.httpx.Client") as mock_cls:
        client = MagicMock()
        client.get.side_effect = fake_get
        mock_cls.return_value.__enter__.return_value = client

        jobs = search_personio({
            "keywords": {"general": ["python"], "regionen": []}
        })
    titles = [j["title"] for j in jobs]
    assert "Senior Python Developer" in titles
    assert "Werkstudent Marketing" not in titles


def test_personio_filters_by_region():
    from bewerbungs_assistent.job_scraper.personio import search_personio

    def fake_get(url, **kwargs):
        return _mock_response(PERSONIO_XML)

    with patch("bewerbungs_assistent.job_scraper.personio.httpx.Client") as mock_cls:
        client = MagicMock()
        client.get.side_effect = fake_get
        mock_cls.return_value.__enter__.return_value = client

        jobs = search_personio({
            "keywords": {"general": [], "regionen": ["Hamburg"]}
        })
    titles = [j["title"] for j in jobs]
    assert "Senior Python Developer" in titles
    assert "Werkstudent Marketing" not in titles  # Berlin


def test_personio_employment_types_mapped():
    from bewerbungs_assistent.job_scraper.personio import search_personio

    def fake_get(url, **kwargs):
        return _mock_response(PERSONIO_XML)

    with patch("bewerbungs_assistent.job_scraper.personio.httpx.Client") as mock_cls:
        client = MagicMock()
        client.get.side_effect = fake_get
        mock_cls.return_value.__enter__.return_value = client

        jobs = search_personio({"keywords": {"general": [], "regionen": []}})
    by_title = {j["title"]: j for j in jobs}
    assert by_title["Werkstudent Marketing"]["employment_type"] == "praktikum"
    assert by_title["Senior Python Developer"]["employment_type"] == "festanstellung"


def test_personio_has_default_companies():
    from bewerbungs_assistent.job_scraper.personio import DEFAULT_COMPANIES
    assert len(DEFAULT_COMPANIES) >= 5


# ============= Workable ===============
# v1.7.106 (B53): die Widget-API je Firma ist tot (leer oder 404, gemessen
# 14.09.2026). Der Adapter nutzt die oeffentliche Stellensuche; die Faelle
# dazu stehen in test_v17106_quellen_b53.py. Hier bleibt der Vertrag des
# Dispatchers (oben) und dass der Adapter die tote API nicht mehr anspricht.


def test_workable_spricht_die_tote_widget_api_nicht_mehr_an():
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
              / "job_scraper" / "workable.py").read_text(encoding="utf-8")
    assert "widget/accounts" not in quelle


# ============= Meinestadt ===============

MEINESTADT_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>meinestadt.de Jobs Hamburg</title>
  <item>
    <title>Verkaeuferin (m/w/d) bei REWE</title>
    <link>https://www.meinestadt.de/hamburg/jobs/123</link>
    <description>Verkaeuferin gesucht in Hamburg-Altona.</description>
    <pubDate>Mon, 06 May 2026 10:00:00 +0200</pubDate>
  </item>
  <item>
    <title>Pflegekraft</title>
    <link>https://www.meinestadt.de/hamburg/jobs/456</link>
    <description>Examinierte Pflegekraft fuer Senioreneinrichtung.</description>
    <pubDate>Mon, 06 May 2026 09:00:00 +0200</pubDate>
  </item>
</channel>
</rss>
"""


def test_meinestadt_resolves_known_city():
    from bewerbungs_assistent.job_scraper.meinestadt import _resolve_stadt
    assert _resolve_stadt("Hamburg") == "hamburg"
    assert _resolve_stadt("München") == "muenchen"
    assert _resolve_stadt("Köln") == "koeln"
    assert _resolve_stadt("KleineDorfX") is None


def test_meinestadt_skips_when_no_known_region():
    from bewerbungs_assistent.job_scraper.meinestadt import search_meinestadt
    jobs = search_meinestadt({
        "keywords": {"general": [], "regionen": ["Kleinkleckersdorf"]}
    })
    assert jobs == []


def test_meinestadt_parses_rss():
    from bewerbungs_assistent.job_scraper.meinestadt import search_meinestadt

    resp = MagicMock()
    resp.status_code = 200
    resp.content = MEINESTADT_RSS

    with patch("bewerbungs_assistent.job_scraper.meinestadt.httpx.Client") as mock_cls:
        client = MagicMock()
        client.get.return_value = resp
        mock_cls.return_value.__enter__.return_value = client

        jobs = search_meinestadt({
            "keywords": {"general": [], "regionen": ["Hamburg"]}
        })
    titles = [j["title"] for j in jobs]
    assert "Verkaeuferin (m/w/d) bei REWE" in titles
    assert "Pflegekraft" in titles
    # Source-Marker
    assert all(j["source"] == "meinestadt" for j in jobs)


def test_meinestadt_filters_by_keyword():
    from bewerbungs_assistent.job_scraper.meinestadt import search_meinestadt

    resp = MagicMock()
    resp.status_code = 200
    resp.content = MEINESTADT_RSS

    with patch("bewerbungs_assistent.job_scraper.meinestadt.httpx.Client") as mock_cls:
        client = MagicMock()
        client.get.return_value = resp
        mock_cls.return_value.__enter__.return_value = client

        jobs = search_meinestadt({
            "keywords": {"general": ["pflege"], "regionen": ["Hamburg"]}
        })
    titles = [j["title"] for j in jobs]
    assert "Pflegekraft" in titles
    assert "Verkaeuferin (m/w/d) bei REWE" not in titles
