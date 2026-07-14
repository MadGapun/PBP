"""Tests fuer services.url_health (#645 Auto-Aging).

Mock-basiert — wir bauen einen Fake-httpx-Client der pro URL eine
vordefinierte Response liefert. So testen wir die Routing-Logik
(Workday-API vs. statisches HTML, Title-Token-Match, Marker-Erkennung)
ohne echtes Netz.
"""
from __future__ import annotations

import pytest

from bewerbungs_assistent.services.url_health import (
    HealthStatus,
    check_job_url_health,
    title_tokens,
    _workday_api_url,
)


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "", url: str = ""):
        self.status_code = status_code
        self.text = text
        self.url = url


class _FakeClient:
    """Mock-Client mit per-URL-Response-Mapping."""

    def __init__(self, mapping: dict[str, _FakeResponse]):
        self.mapping = mapping
        self.requests: list[str] = []

    def get(self, url: str, *args, **kwargs):
        self.requests.append(url)
        r = self.mapping.get(url)
        if r is None:
            # Default fallback fuer nicht-gemockte URLs
            return _FakeResponse(404, "", url)
        if not r.url:
            r.url = url
        return r


# ── title_tokens ──────────────────────────────────────────────────────


def test_title_tokens_extracts_signaltragende_woerter():
    """Stoppwoerter (und/der/...) und kurze Tokens fliegen raus."""
    out = title_tokens("Senior Business Process Manager Digital Transformation")
    assert "senior" in out
    assert "business" in out
    assert "process" in out
    assert "manager" in out
    assert "digital" in out
    assert "transformation" in out
    # Stoppwoerter / kurze
    assert "and" not in out
    assert "der" not in out


def test_title_tokens_handles_special_chars_and_genders():
    """Genders-Marker und Sonderzeichen sauber tokenisiert."""
    out = title_tokens("Manager:in - IT-Transformation Public Sector (m/w/d)")
    # 'manager' und 'transformation' und 'public' und 'sector' kommen vor
    assert "manager" in out  # 'Manager' aus 'Manager:in'
    assert "transformation" in out
    assert "public" in out
    assert "sector" in out
    # m/w/d ist als Stopword/short tokens raus
    assert "m" not in out


def test_title_tokens_empty_or_none():
    assert title_tokens("") == set()
    assert title_tokens(None) == set()  # type: ignore


# ── _workday_api_url ───────────────────────────────────────────────────


def test_workday_api_url_airbus():
    url = "https://ag.wd3.myworkdayjobs.com/en-US/Airbus/job/Hamburg-Area/Senior-Business-Analyst---Physical-Design--d-f-m-_JR10395055"
    api = _workday_api_url(url)
    assert api is not None
    assert "wday/cxs/ag/Airbus/job/" in api
    assert "Hamburg-Area" in api


def test_workday_api_url_tenant():
    url = "https://examplecorp.wd3.myworkdayjobs.com/en-US/careers/job/Hamburg/Head-of-Sourcing--m-f-d----Front-End-BOM_R-20014600"
    api = _workday_api_url(url)
    assert api is not None
    assert "wday/cxs/examplecorp/careers/job/Hamburg/" in api


def test_workday_api_url_non_workday_returns_none():
    assert _workday_api_url("https://www.stepstone.de/foo/bar.html") is None
    assert _workday_api_url("https://example.com") is None


# ── check_job_url_health ───────────────────────────────────────────────


def test_check_url_leer():
    res = check_job_url_health("", "Senior Manager")
    assert res.status == HealthStatus.LEER
    assert res.should_dismiss is False  # leer != aussortieren


def test_check_url_404():
    url = "https://example.com/dead-job"
    client = _FakeClient({url: _FakeResponse(404, "Not found", url)})
    res = check_job_url_health(url, "Senior Manager", client=client)
    assert res.status == HealthStatus.HTTP_404
    assert res.http_code == 404
    assert res.should_dismiss is True


def test_check_url_410_treated_as_404():
    url = "https://example.com/gone"
    client = _FakeClient({url: _FakeResponse(410, "Gone", url)})
    res = check_job_url_health(url, "Senior Manager", client=client)
    assert res.status == HealthStatus.HTTP_404
    assert res.should_dismiss is True


def test_check_url_500_treated_as_http_error_not_dismiss():
    """5xx ist meist transient — nicht aussortieren."""
    url = "https://example.com/server-err"
    client = _FakeClient({url: _FakeResponse(500, "Server error", url)})
    res = check_job_url_health(url, "Senior Manager", client=client)
    assert res.status == HealthStatus.HTTP_ERROR
    assert res.should_dismiss is False


def test_check_url_expired_marker_german():
    """Body mit deutschem 'Stelle vergeben'-Marker -> expired."""
    url = "https://remotely.de/job/foo"
    body = "<html><body>Diese Stelle ist bereits vergeben. Deine naechste Chance wartet.</body></html>"
    client = _FakeClient({url: _FakeResponse(200, body, url)})
    res = check_job_url_health(url, "Systems Engineer Senior", client=client)
    assert res.status == HealthStatus.EXPIRED
    assert res.marker is not None
    assert "bereits vergeben" in res.marker.lower()
    assert res.should_dismiss is True


def test_check_url_expired_marker_english():
    """Body mit englischem 'no longer available'-Marker -> expired."""
    url = "https://example.com/old-job"
    body = "<html><body>This job is no longer accepting applications.</body></html>"
    client = _FakeClient({url: _FakeResponse(200, body, url)})
    res = check_job_url_health(url, "Senior Manager Foo", client=client)
    assert res.status == HealthStatus.EXPIRED
    assert res.should_dismiss is True


def test_check_url_title_mismatch_treated_as_expired():
    """Server liefert 200 mit Generic-Content statt Job-Detail -> expired."""
    url = "https://example.com/generic-404"
    # Body enthaelt nichts vom Titel — Server hat eine generische
    # "Job not found"-Seite ohne expliziten Marker geliefert.
    body = "<html><body>Welcome to our careers page. Browse all openings.</body></html>"
    client = _FakeClient({url: _FakeResponse(200, body, url)})
    res = check_job_url_health(url, "Senior PLM Berater Datenmanagement", client=client)
    assert res.status == HealthStatus.EXPIRED
    assert res.marker == "title tokens not found in body"
    assert res.should_dismiss is True


def test_check_url_title_match_ok():
    """Body enthaelt Titel-Tokens -> ok."""
    url = "https://example.com/real-job"
    body = "<html><body>Senior PLM Berater wanted! Datenmanagement skills required.</body></html>"
    client = _FakeClient({url: _FakeResponse(200, body, url)})
    res = check_job_url_health(url, "Senior PLM Berater Datenmanagement", client=client)
    assert res.status == HealthStatus.OK
    assert res.should_dismiss is False
    assert res.title_token_hits is not None


def test_check_url_no_title_skips_match():
    """Ohne Titel-Argument kein Match-Check (z.B. fuer Generic-Health)."""
    url = "https://example.com/any"
    body = "<html><body>some content</body></html>"
    client = _FakeClient({url: _FakeResponse(200, body, url)})
    res = check_job_url_health(url, None, client=client)
    assert res.status == HealthStatus.OK
    assert res.title_token_hits is None


def test_check_url_workday_api_404_overrides_html_200():
    """Workday-HTML liefert 200 (Skeleton), aber API liefert 404 -> expired."""
    html_url = "https://ag.wd3.myworkdayjobs.com/en-US/Airbus/job/Hamburg-Area/Old-Job_JR9999"
    api_url = _workday_api_url(html_url)
    assert api_url is not None
    body = "<html><body><div id='wd-root'></div></body></html>"
    client = _FakeClient({
        html_url: _FakeResponse(200, body, html_url),
        api_url: _FakeResponse(404, "Not found", api_url),
    })
    res = check_job_url_health(html_url, "Old Job Senior", client=client)
    assert res.status == HealthStatus.EXPIRED
    assert res.workday_api_status == 404
    assert res.should_dismiss is True


def test_check_url_workday_api_200_confirms_active():
    """Workday-API 200 mit Title-Match -> ok."""
    html_url = "https://examplecorp.wd3.myworkdayjobs.com/en-US/careers/job/Hamburg/Head-of-Sourcing-BOM_R20014600"
    api_url = _workday_api_url(html_url)
    assert api_url is not None
    html_body = "<html><body><div id='wd-root'></div></body></html>"
    # Workday-API liefert JSON mit Titel
    api_body = '{"jobPostingInfo": {"title": "Head of Sourcing - Front End BOM"}}'
    client = _FakeClient({
        html_url: _FakeResponse(200, html_body, html_url),
        api_url: _FakeResponse(200, api_body, api_url),
    })
    res = check_job_url_health(
        html_url, "Head of Sourcing Front End BOM", client=client,
    )
    assert res.status == HealthStatus.OK
    assert res.workday_api_status == 200
    assert res.should_dismiss is False


def test_check_url_blocked_marker():
    """Cloudflare/Captcha-Marker -> blocked (kein dismiss)."""
    url = "https://example.com/bot-blocked"
    body = "<html><body>Please verify you are human. Cloudflare protection.</body></html>"
    client = _FakeClient({url: _FakeResponse(200, body, url)})
    res = check_job_url_health(url, "Senior Manager", client=client)
    assert res.status == HealthStatus.BLOCKED
    assert res.should_dismiss is False  # bot-block ist kein aussortier-Grund
