"""Tests fuer v1.7.0-beta.50 — Scraper-Helpers (#624 Phase 1).

Pure Unit-Tests gegen make_session() + with_retry(). Keine Live-HTTP-Calls.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest


# ============= make_session() ===============

def test_make_session_default_uses_pbp_user_agent():
    from bewerbungs_assistent.job_scraper import make_session, PBP_USER_AGENT
    with make_session() as client:
        ua = client.headers.get("User-Agent")
    assert ua == PBP_USER_AGENT
    assert "PBP-Bewerbungs-Assistent" in ua
    assert "github.com/MadGapun/PBP" in ua


def test_make_session_default_content_type_json():
    from bewerbungs_assistent.job_scraper import make_session
    with make_session() as client:
        accept = client.headers.get("Accept")
    assert "application/json" in accept


def test_make_session_content_type_rss():
    from bewerbungs_assistent.job_scraper import make_session
    with make_session(content_type="rss") as client:
        accept = client.headers.get("Accept")
    assert "rss" in accept


def test_make_session_content_type_html():
    from bewerbungs_assistent.job_scraper import make_session
    with make_session(content_type="html") as client:
        accept = client.headers.get("Accept")
    assert "text/html" in accept


def test_make_session_extra_headers_merged():
    from bewerbungs_assistent.job_scraper import make_session
    with make_session(extra_headers={"X-PBP-Test": "yes"}) as client:
        assert client.headers.get("X-PBP-Test") == "yes"
        # Standard-Header bleiben
        assert client.headers.get("User-Agent")


def test_make_session_extra_headers_override():
    """Extra-Headers koennen Standards ueberschreiben (z.B. UA fuer
    bundesagentur die einen iOS-App-UA erwartet)."""
    from bewerbungs_assistent.job_scraper import make_session
    custom_ua = "Jobsuche/2.12.0 (de.arbeitsagentur.jobboerse; iOS 16)"
    with make_session(user_agent=custom_ua) as client:
        assert client.headers["User-Agent"] == custom_ua


def test_make_session_custom_timeout():
    from bewerbungs_assistent.job_scraper import make_session
    with make_session(timeout=30.0) as client:
        # httpx Timeout-Repr enthaelt den Wert
        assert client.timeout.read == 30.0


def test_make_session_follow_redirects_default_true():
    from bewerbungs_assistent.job_scraper import make_session
    with make_session() as client:
        assert client.follow_redirects is True


# ============= with_retry() Decorator ===============

def test_with_retry_success_first_try_no_retry():
    from bewerbungs_assistent.job_scraper import with_retry
    calls = []

    @with_retry(max_attempts=3, backoff_base=0.01)
    def fetch():
        calls.append(1)
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        return resp

    result = fetch()
    assert result.status_code == 200
    assert len(calls) == 1


def test_with_retry_retries_on_503_then_success():
    from bewerbungs_assistent.job_scraper import with_retry
    calls = []

    @with_retry(max_attempts=3, backoff_base=0.01)
    def fetch():
        calls.append(1)
        resp = MagicMock(spec=httpx.Response)
        if len(calls) < 3:
            resp.status_code = 503
            resp.headers = {}
        else:
            resp.status_code = 200
        return resp

    result = fetch()
    assert result.status_code == 200
    assert len(calls) == 3


def test_with_retry_gives_up_after_max_attempts():
    from bewerbungs_assistent.job_scraper import with_retry
    calls = []

    @with_retry(max_attempts=2, backoff_base=0.01)
    def fetch():
        calls.append(1)
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 503
        resp.headers = {}
        return resp

    result = fetch()
    # Liefert die letzte Response zurueck (status 503), wirft nicht
    assert result.status_code == 503
    assert len(calls) == 2


def test_with_retry_respects_429_retry_after():
    from bewerbungs_assistent.job_scraper import with_retry
    import time as _time
    calls = []
    delays = []

    @with_retry(max_attempts=2, backoff_base=0.01)
    def fetch():
        calls.append(_time.time())
        resp = MagicMock(spec=httpx.Response)
        if len(calls) == 1:
            resp.status_code = 429
            resp.headers = {"Retry-After": "0.05"}  # Sekunde
        else:
            resp.status_code = 200
        return resp

    fetch()
    if len(calls) == 2:
        delays.append(calls[1] - calls[0])
    # Mindestens 0.05s Pause sollte gewesen sein (war Retry-After)
    assert delays and delays[0] >= 0.04


def test_with_retry_handles_transport_error():
    from bewerbungs_assistent.job_scraper import with_retry
    calls = []

    @with_retry(max_attempts=2, backoff_base=0.01)
    def fetch():
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("simulated network error")
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        return resp

    result = fetch()
    assert result.status_code == 200
    assert len(calls) == 2


def test_with_retry_reraises_after_max_transport_errors():
    from bewerbungs_assistent.job_scraper import with_retry

    @with_retry(max_attempts=2, backoff_base=0.01)
    def fetch():
        raise httpx.ConnectError("permanent network down")

    with pytest.raises(httpx.ConnectError):
        fetch()


# ============= Migration: arbeitnow + remoteok ===============

def test_arbeitnow_uses_make_session():
    """Verifiziere dass die Migration auf make_session greift."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1]
            / "src" / "bewerbungs_assistent" / "job_scraper" / "arbeitnow.py")
    content = src.read_text(encoding="utf-8")
    assert "make_session" in content
    assert "_HEADERS = {" not in content


def test_remoteok_uses_make_session():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1]
            / "src" / "bewerbungs_assistent" / "job_scraper" / "remoteok.py")
    content = src.read_text(encoding="utf-8")
    assert "make_session" in content
    assert "_HEADERS = {" not in content


# ============= Smoke: arbeitnow.search() laeuft mit gemockter API ============

def test_arbeitnow_search_works_with_mocked_response():
    """Mocked-API-Smoke-Test fuer den migrierten Scraper."""
    from bewerbungs_assistent.job_scraper import arbeitnow

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "data": [
            {
                "slug": "test-job-1",
                "title": "Senior Python Developer",
                "company_name": "ACME GmbH",
                "url": "https://www.arbeitnow.com/jobs/test-job-1",
                "tags": ["python", "remote"],
                "description": "Wir suchen einen Senior Python Developer.",
                "remote": True,
                "location": "Remote",
                "created_at": 1704067200,
            }
        ],
        "links": {"next": None},
    }
    fake_response.raise_for_status = MagicMock()

    fake_client = MagicMock()
    fake_client.get.return_value = fake_response
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=None)

    with patch("bewerbungs_assistent.job_scraper.arbeitnow.make_session",
               return_value=fake_client):
        # search_arbeitnow nimmt einen params-dict
        results = arbeitnow.search_arbeitnow({
            "keywords": ["Python"],
            "general": ["Python"],
        })

    assert isinstance(results, list)
    # Smoke ist OK wenn der Aufruf nicht crashed — Filter-Verhalten ist
    # nicht Teil dieses Tests
    fake_client.get.assert_called()
