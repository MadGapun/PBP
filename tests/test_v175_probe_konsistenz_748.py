"""Tests fuer v1.7.5 — #748 (B13.4): Probes adapter-konsistent.

Mehrere Probes meldeten 403/404, obwohl die Production-Scraper liefen —
weil Probe-Request und Adapter-Request auseinandergedriftet waren.
Prinzip jetzt: Probe == Adapter (URL, Header, Firma). Kein Live-HTTP.
"""
from unittest.mock import MagicMock, patch

import pytest

import httpx

from bewerbungs_assistent.job_scraper import health
from bewerbungs_assistent.job_scraper.health import _PROBE_EXTRA_HEADERS, _PROBES


class TestAdapterKonsistenz:
    def test_bundesagentur_probe_traegt_adapter_header(self):
        """403-Ursache: der Adapter sendet X-API-Key + speziellen UA,
        die Probe tat es nicht."""
        from bewerbungs_assistent.job_scraper.bundesagentur import API_KEY, USER_AGENT
        headers = _PROBE_EXTRA_HEADERS["bundesagentur"]
        assert headers["X-API-Key"] == API_KEY
        assert headers["User-Agent"] == USER_AGENT

    def test_workable_probe_nutzt_adapter_api_und_firma(self):
        """404-Ursache: Probe nutzte die v3-API, der Adapter die v1-Widget-API.

        v1.7.19 (#927): Die Quelle ist inzwischen als `defekt` markiert
        (oeffentliche Suche liefert keine Stellen mehr) und hat deshalb
        KEINE Probe mehr — eine Probe auf eine defekte Quelle meldet
        faelschlich 'gruen'. Der Konsistenz-Vertrag gilt nur, solange
        eine Probe existiert.
        """
        if "workable" not in _PROBES:
            pytest.skip("als defekt markiert — Probe bewusst entfernt (#927)")
        from bewerbungs_assistent.job_scraper.workable import _BASE_TPL, DEFAULT_COMPANIES
        _, url, _, _ = _PROBES["workable"]
        assert url == _BASE_TPL.format(firma=DEFAULT_COMPANIES[0])

    def test_personio_probe_nutzt_adapter_firma(self):
        """404-Ursache: Probe-Firma war nicht in der Adapter-Firmenliste."""
        from bewerbungs_assistent.job_scraper.personio import _BASE_TPL, DEFAULT_COMPANIES
        _, url, _, _ = _PROBES["personio"]
        assert url == _BASE_TPL.format(firma=DEFAULT_COMPANIES[0])

    def test_rss_probes_identisch_zum_adapter(self):
        """RSS-Quellen: Probe == Adapter-Basis-URL — wenn die Probe hier
        rot ist, ist es der Adapter auch (gewollt).

        v1.7.19 (#927): Quellen, die als `defekt` markiert wurden, haben
        keine Probe mehr und fallen aus dem Vertrag. Geprueft wird, was
        noch eine Probe hat.
        """
        from bewerbungs_assistent.job_scraper.berufsstart import _BASE as b
        from bewerbungs_assistent.job_scraper.studentjob import _BASE as s
        paare = [("berufsstart", b), ("studentjob", s)]
        try:
            from bewerbungs_assistent.job_scraper.praktikum_de import _BASE as p
            paare.append(("praktikum_de", p))
        except ImportError:  # pragma: no cover
            pass
        geprueft = 0
        for key, basis in paare:
            if key not in _PROBES:
                continue  # als defekt markiert, Probe bewusst entfernt
            assert _PROBES[key][1].startswith(basis), key
            geprueft += 1
        assert geprueft, "mindestens eine RSS-Probe sollte bestehen bleiben"

    def test_extra_headers_nur_fuer_bekannte_quellen(self):
        unbekannt = [k for k in _PROBE_EXTRA_HEADERS if k not in _PROBES]
        assert not unbekannt, f"Header ohne Probe-Definition: {unbekannt}"


class TestHeaderDurchreichung:
    def test_check_source_reicht_extra_headers_an_session(self):
        fake_resp = MagicMock(spec=httpx.Response)
        fake_resp.status_code = 200
        fake_client = MagicMock()
        fake_client.get.return_value = fake_resp
        fake_client.__enter__ = MagicMock(return_value=fake_client)
        fake_client.__exit__ = MagicMock(return_value=None)

        with patch("bewerbungs_assistent.job_scraper.health.make_session",
                   return_value=fake_client) as ms:
            r = health.check_source("bundesagentur")
        assert r["reachable"] is True
        _, kwargs = ms.call_args
        assert kwargs["extra_headers"]["X-API-Key"] == "jobboerse-jobsuche"

    def test_quellen_ohne_header_bekommen_none(self):
        fake_resp = MagicMock(spec=httpx.Response)
        fake_resp.status_code = 200
        fake_client = MagicMock()
        fake_client.get.return_value = fake_resp
        fake_client.__enter__ = MagicMock(return_value=fake_client)
        fake_client.__exit__ = MagicMock(return_value=None)

        with patch("bewerbungs_assistent.job_scraper.health.make_session",
                   return_value=fake_client) as ms:
            health.check_source("arbeitnow")
        _, kwargs = ms.call_args
        assert kwargs["extra_headers"] is None
