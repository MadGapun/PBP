"""Regressionstests fuer #645 — leere jobs.url-Felder bei XING/Stepstone/Email.

Hintergrund: Bei der Durchsicht am 29.05.2026 waren bei 7 von 8 Stellen
die url-Felder leer. Ursache war eine Mischung aus:
  - Stepstone/XING-Scraper haben den extrahierten Link ungeprueft
    durchgereicht (kein Such-URL-Fallback wie in monster.py/freelancermap.py).
  - update_job-Whitelist enthielt url nicht — selbst der Workaround
    "manuell per stelle_bearbeiten nachpflegen" hat stillschweigend
    nichts gemacht.
  - stelle_bearbeiten akzeptierte gar keinen url-Parameter.

Die Tests hier sind fixture-frei und decken die Pure-Logik ab:
  - URL-Fallback-Kaskade pro Scraper (_process_raw_job fuer XING,
    Job-Dict-Bau fuer Stepstone)
  - DB-Update via update_job + stelle_bearbeiten + stellenbeschreibung_nachladen
"""

from __future__ import annotations

import logging


class FakeMCP:
    """Minimal MCP registry — wie in test_v032_regressions.py."""

    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


# ── #645 / Scraper-URL-Fallback ──────────────────────────────────────


def test_xing_process_raw_job_uses_detail_link_when_present():
    """XING-Karte mit Detail-Link -> URL unveraendert, is_search_url=False."""
    from bewerbungs_assistent.job_scraper.xing import _process_raw_job

    job = _process_raw_job(
        {
            "title": "Head of Master Data Management",
            "link": "https://www.xing.com/jobs/head-of-mdm-12345",
            "jobId": "12345",
            "company": "TestFirma-A",
            "location": "Hamburg",
            "desc": "MDM-Leitung",
        },
        seen_job_ids=set(),
        search_url="https://www.xing.com/jobs/search?keywords=mdm",
    )
    assert job is not None
    assert job["url"] == "https://www.xing.com/jobs/head-of-mdm-12345"
    assert job["is_search_url"] is False


def test_xing_process_raw_job_reconstructs_url_from_jobid():
    """#645: Wenn link leer aber jobId da, Detail-URL aus jobId bauen."""
    from bewerbungs_assistent.job_scraper.xing import _process_raw_job

    job = _process_raw_job(
        {
            "title": "Senior PLM Consultant",
            "link": "",
            "jobId": "999888",
            "company": "TestFirma-B",
            "location": "Muenchen",
            "desc": "",
        },
        seen_job_ids=set(),
        search_url="https://www.xing.com/jobs/search?keywords=plm",
    )
    assert job is not None
    assert job["url"] == "https://www.xing.com/jobs/999888"
    assert job["is_search_url"] is False


def test_xing_process_raw_job_falls_back_to_search_url():
    """#645: Kein link und kein jobId -> Such-URL als Fallback + Flag."""
    from bewerbungs_assistent.job_scraper.xing import _process_raw_job

    search_url = "https://www.xing.com/jobs/search?keywords=plm&location=Hamburg"
    job = _process_raw_job(
        {
            "title": "Interim IT-PM Integration",
            "link": "",
            "jobId": "",
            "company": "Beratungshaus",
            "location": "Hamburg",
            "desc": "",
        },
        seen_job_ids=set(),
        search_url=search_url,
    )
    assert job is not None
    assert job["url"] == search_url
    assert job["is_search_url"] is True


def test_xing_process_raw_job_absolutizes_relative_link():
    """Relative Links bekommen den XING-Host vorgeklebt."""
    from bewerbungs_assistent.job_scraper.xing import _process_raw_job

    job = _process_raw_job(
        {
            "title": "Cloud Architekt",
            "link": "/jobs/cloud-architekt-77777",
            "jobId": "77777",
            "company": "Cloud Inc.",
            "location": "Remote",
            "desc": "",
        },
        seen_job_ids=set(),
        search_url="",
    )
    assert job is not None
    assert job["url"] == "https://www.xing.com/jobs/cloud-architekt-77777"
    assert job["is_search_url"] is False


# ── #645 / DB-Schicht ────────────────────────────────────────────────


def test_save_jobs_warns_on_empty_url_from_scraper_source(tmp_db, caplog):
    """#645 Hard-Guard: leere URL aus bekannter Scraper-Quelle wird
    gewarnt + auto-is_search_url=True markiert."""
    tmp_db.create_profile("Test User", "test@example.com")
    with caplog.at_level(logging.WARNING, logger="bewerbungs_assistent.database"):
        res = tmp_db.save_jobs([
            {
                "hash": "guard-stepstone-empty",
                "title": "Senior Architekt",
                "company": "TestFirma-A",
                "source": "stepstone",
                "url": "",
                "description": "",
                "score": 5,
                "employment_type": "festanstellung",
            },
        ])
    # Quellen-Counter im Result-Dict
    assert "leere_url_warnungen" in res
    assert res["leere_url_warnungen"] == {"stepstone": 1}
    # WARN-Log mit Quelle + Issue-Verweis
    assert any("stepstone" in r.message and "#645" in r.message
               for r in caplog.records)
    # Defensiv-Markierung is_search_url=1 wurde gesetzt
    job = tmp_db.get_job("guard-stepstone-empty")
    assert int(job.get("is_search_url") or 0) == 1


def test_save_jobs_silent_for_manuell_or_email_without_url(tmp_db, caplog):
    """#645: manuell + email sind erlaubte Quellen ohne URL — keine Warnung."""
    tmp_db.create_profile("Test User", "test@example.com")
    with caplog.at_level(logging.WARNING, logger="bewerbungs_assistent.database"):
        res = tmp_db.save_jobs([
            {
                "hash": "guard-manuell-empty",
                "title": "Hand-eingetragene Stelle",
                "company": "TestFirma-B",
                "source": "manuell",
                "url": "",
                "score": 5,
                "employment_type": "festanstellung",
            },
            {
                "hash": "guard-email-empty",
                "title": "Recruiter-Mail-Stelle",
                "company": "TestFirma-C",
                "source": "email",
                "url": "",
                "score": 5,
                "employment_type": "festanstellung",
            },
        ])
    assert "leere_url_warnungen" not in res
    assert not any("#645" in r.message for r in caplog.records)


def test_update_job_persists_url(tmp_db):
    """#645: update_job darf url schreiben (vorher Whitelist-Drop)."""
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs([
        {
            "hash": "url-update-1",
            "title": "Manager IT-Transformation",
            "company": "TestFirma-C",
            "source": "xing",
            "url": "",  # genau der Zustand aus #645
            "is_search_url": True,
            "description": "",
            "score": 5,
            "employment_type": "festanstellung",
        },
    ])

    tmp_db.update_job(
        "url-update-1",
        {
            "url": "https://www.xing.com/jobs/manager-it-trafo-42",
            "is_search_url": False,
        },
    )

    job = tmp_db.get_job("url-update-1")
    assert job["url"] == "https://www.xing.com/jobs/manager-it-trafo-42"
    assert int(job.get("is_search_url") or 0) == 0


# ── #645 / Tool-Schicht ──────────────────────────────────────────────


def test_stelle_bearbeiten_accepts_url_and_flags_search_url(tmp_db):
    """#645: stelle_bearbeiten kann jetzt URLs nachreichen + erkennt Such-URLs."""
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs([
        {
            "hash": "edit-url-1",
            "title": "Lead Consultant PLM",
            "company": "Beispieltech",
            "source": "stepstone",
            "url": "",
            "is_search_url": True,
            "description": "",
            "score": 5,
            "employment_type": "festanstellung",
        },
    ])

    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import jobs as jobs_mod
    jobs_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    # Echte Detail-URL nachpflegen -> kein url_warnung, is_search_url=0
    result = fake_mcp.tools["stelle_bearbeiten"](
        "edit-url-1",
        url="https://www.stepstone.de/stellenangebote--lead-consultant-plm-hamburg--12345-inline.html",
    )
    assert result["status"] == "aktualisiert"
    assert "url" in result["geaenderte_felder"]
    assert "is_search_url" in result["geaenderte_felder"]
    assert "url_warnung" not in result

    job = tmp_db.get_job("edit-url-1")
    assert job["url"].startswith("https://www.stepstone.de/stellenangebote--")
    assert int(job.get("is_search_url") or 0) == 0


def test_stelle_bearbeiten_warns_on_search_url(tmp_db):
    """#645: Wenn doch nur eine Such-URL nachgereicht wird, url_warnung."""
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs([
        {
            "hash": "edit-search-url-1",
            "title": "Transformation Lead",
            "company": "Kabs",
            "source": "stepstone",
            "url": "",
            "is_search_url": True,
            "description": "",
            "score": 5,
            "employment_type": "festanstellung",
        },
    ])

    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import jobs as jobs_mod
    jobs_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    result = fake_mcp.tools["stelle_bearbeiten"](
        "edit-search-url-1",
        url="https://www.stepstone.de/stellenangebote?what=transformation&where=hamburg",
    )
    assert result["status"] == "aktualisiert"
    assert "url_warnung" in result

    job = tmp_db.get_job("edit-search-url-1")
    assert int(job.get("is_search_url") or 0) == 1


def test_stellenbeschreibung_nachladen_hint_points_to_stelle_bearbeiten(tmp_db):
    """#645: Fehler-Meldung verweist auf den jetzt funktionierenden Workflow."""
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs([
        {
            "hash": "no-url-1",
            "title": "Head of MDM",
            "company": "Pharma",
            "source": "xing",
            "url": "",
            "description": "",
            "score": 5,
            "employment_type": "festanstellung",
        },
    ])

    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import jobs as jobs_mod
    jobs_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    result = fake_mcp.tools["stellenbeschreibung_nachladen"]("no-url-1")
    assert result["status"] == "fehler"
    assert "stelle_bearbeiten" in result.get("grund", "")
    assert "url=" in result.get("grund", "")
    assert result.get("vorschlag_tool") == "stelle_bearbeiten"


def test_stellenbeschreibung_nachladen_rejects_search_url(tmp_db):
    """#645: Wenn die gespeicherte URL eine Such-URL ist, kein HTTP-Fetch."""
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs([
        {
            "hash": "search-url-1",
            "title": "Programm Mgmt IT",
            "company": "mgm",
            "source": "stepstone",
            "url": "https://www.stepstone.de/jobs/plm/in-hamburg",
            "is_search_url": True,
            "description": "",
            "score": 5,
            "employment_type": "festanstellung",
        },
    ])

    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import jobs as jobs_mod
    jobs_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    result = fake_mcp.tools["stellenbeschreibung_nachladen"]("search-url-1")
    assert result["status"] == "fehler"
    assert "Such-URL" in result.get("grund", "") or "#645" in result.get("grund", "")
    assert result.get("vorschlag_tool") == "stelle_bearbeiten"
