"""Fixture-based scraper tests for the most stable parser paths."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bewerbungs_assistent.job_scraper import freelance_de, freelancermap, hays  # noqa: E402


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "scrapers"


def _fixture_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data

    def json(self):
        return self._json_data


class _FakeClient:
    def __init__(self, mapping: dict[str, _FakeResponse], requests: list[str]):
        self._mapping = mapping
        self._requests = requests

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url, *args, **kwargs):
        self._requests.append(url)
        return self._mapping.get(url, _FakeResponse(404, ""))


def test_hays_search_parses_relevant_sitemap_and_json_ld(monkeypatch):
    """Hays nutzt Fixture-Sitemap und JSON-LD-Detailseite stabil."""
    requests = []
    mapping = {
        hays.SITEMAP_URL: _FakeResponse(200, _fixture_text("hays_sitemap.xml")),
        "https://www.hays.de/jobsuche/stellenangebote-jobs-detail-windchill-berater-hamburg-12345": _FakeResponse(
            200, _fixture_text("hays_job_detail.html")
        ),
    }

    monkeypatch.setattr(
        hays.httpx,
        "Client",
        lambda *args, **kwargs: _FakeClient(mapping, requests),
    )
    monkeypatch.setattr(hays.time, "sleep", lambda *_args, **_kwargs: None)

    jobs = hays.search_hays({"keywords": {"hays_keywords": ["windchill"]}})

    assert len(jobs) == 1
    assert jobs[0]["title"] == "Senior Windchill Berater"
    assert jobs[0]["company"] == "Hays"
    assert jobs[0]["location"] == "Hamburg"
    assert jobs[0]["source"] == "hays"
    assert jobs[0]["remote_level"] == "hybrid"
    assert requests == [
        hays.SITEMAP_URL,
        "https://www.hays.de/jobsuche/stellenangebote-jobs-detail-windchill-berater-hamburg-12345",
    ]


def test_freelance_de_listing_fixture_parses_cards_and_pagination():
    """freelance.de Fixture deckt Kartenparser und Weiterseiten-Erkennung ab."""
    html = _fixture_text("freelance_de_listing.html")

    seen_urls = set()
    jobs = freelance_de._parse_listing_page(html, seen_urls)

    assert len(jobs) == 2
    assert jobs[0]["title"] == "Remote PLM Migration"
    assert jobs[0]["company"] == "freelance.de"
    assert jobs[0]["location"] == "Hamburg"
    assert jobs[0]["employment_type"] == "freelance"
    assert jobs[0]["remote_level"] == "remote"
    assert "Windchill" in jobs[0]["description"]
    assert jobs[1]["remote_level"] == "hybrid"
    assert freelance_de._has_next_page(html, 0) is True

    duplicate_jobs = freelance_de._parse_listing_page(html, seen_urls)
    assert duplicate_jobs == []


def test_freelancermap_search_extracts_projects_from_js_fixture(monkeypatch):
    """Freelancermap parst eingebetteten JS-State ohne Playwright-Fallback."""
    requests = []
    html = _fixture_text("freelancermap_projects.html")
    mapping = {
        "https://www.freelancermap.de/projektboerse.html?q=PLM": _FakeResponse(200, html),
    }
    fallback_called = {"value": False}

    monkeypatch.setattr(
        freelancermap.httpx,
        "Client",
        lambda *args, **kwargs: _FakeClient(mapping, requests),
    )
    monkeypatch.setattr(freelancermap.time, "sleep", lambda *_args, **_kwargs: None)

    def _fake_fallback(_urls):
        fallback_called["value"] = True
        return []

    monkeypatch.setattr(freelancermap, "_playwright_fallback", _fake_fallback)

    jobs = freelancermap.search_freelancermap(
        {"keywords": {"freelancermap_urls": ["https://www.freelancermap.de/projektboerse.html?q=PLM"]}}
    )

    assert len(jobs) == 1
    assert jobs[0]["title"] == "PLM Solution Architect"
    assert jobs[0]["company"] == "ACME Projects"
    assert jobs[0]["location"] == "Frankfurt"
    assert jobs[0]["source"] == "freelancermap"
    assert jobs[0]["employment_type"] == "freelance"
    assert jobs[0]["remote_level"] == "remote"
    assert "PLM Architektur" in jobs[0]["description"]
    assert fallback_called["value"] is False
    assert requests == ["https://www.freelancermap.de/projektboerse.html?q=PLM"]
