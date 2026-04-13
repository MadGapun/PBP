"""Regression tests for recent v0.32.x issue fixes."""

import logging


class FakeMCP:
    """Minimal MCP registry for tool-level unit tests."""

    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


def test_add_application_copies_source_from_linked_job(tmp_db):
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs(
        [
            {
                "hash": "job-source-1",
                "title": "Senior PLM Consultant",
                "company": "ACME",
                "source": "stepstone",
                "score": 7,
            }
        ]
    )

    app_id = tmp_db.add_application(
        {
            "title": "Senior PLM Consultant",
            "company": "ACME",
            "job_hash": "job-source-1",
            "status": "beworben",
        }
    )

    app = tmp_db.get_application(app_id)
    assert app["source"] == "stepstone"


def test_get_score_stats_prefers_application_source_over_manual_job_source(tmp_db):
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs(
        [
            {
                "hash": "job-source-2",
                "title": "PLM Freelance Projekt",
                "company": "Bridge GmbH",
                "source": "manuell",
                "score": 6,
            }
        ]
    )
    tmp_db.add_application(
        {
            "title": "PLM Freelance Projekt",
            "company": "Bridge GmbH",
            "job_hash": "job-source-2",
            "status": "beworben",
            "source": "freelance_de",
        }
    )

    stats = tmp_db.get_score_stats()
    by_name = {entry["name"]: entry["count"] for entry in stats["application_sources"]}

    assert by_name["freelance_de"] == 1
    assert by_name.get("manuell", 0) == 0


def test_report_data_uses_historical_score_distribution(tmp_db):
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs(
        [
            {
                "hash": "job-active-1",
                "title": "Hoher Score",
                "company": "A",
                "source": "stepstone",
                "score": 8,
                "is_active": 1,
            },
            {
                "hash": "job-dismissed-1",
                "title": "Niedriger Score",
                "company": "B",
                "source": "indeed",
                "score": 2,
                "is_active": 0,
            },
        ]
    )

    report = tmp_db.get_report_data()

    assert report["score_distribution"]["7-9"] == 1
    assert report["score_distribution"]["1-3"] == 1


def test_export_tool_prefers_application_source_for_report(tmp_db, monkeypatch):
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs(
        [
            {
                "hash": "job-export-1",
                "title": "PLM Projekt",
                "company": "Export GmbH",
                "source": "manuell",
                "score": 5,
            }
        ]
    )
    tmp_db.add_application(
        {
            "title": "PLM Projekt",
            "company": "Export GmbH",
            "job_hash": "job-export-1",
            "status": "beworben",
            "source": "freelance_de",
        }
    )

    captured = {}

    def fake_generate_application_report(report_data, profile, path, **kwargs):
        captured["report_data"] = report_data
        path.write_bytes(b"stub")
        return path

    from bewerbungs_assistent import export_report
    from bewerbungs_assistent.tools import export_tools

    monkeypatch.setattr(export_report, "generate_application_report", fake_generate_application_report)

    fake_mcp = FakeMCP()
    export_tools.register(fake_mcp, tmp_db, logging.getLogger("test"))

    result = fake_mcp.tools["bewerbungsbericht_exportieren"]()

    assert result["status"] == "erstellt"
    assert captured["report_data"]["applications"][0]["job_source"] == "freelance_de"


def test_stellen_anzeigen_emoji_marker(tmp_db):
    """#435: stellen_anzeigen setzt Emoji-Marker nach employment_type."""
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs([
        {
            "hash": "emoji-freelance-1",
            "title": "Cloud Architekt Projekt",
            "company": "FreeCorp",
            "source": "manuell",
            "description": "Ein Freelance-Projekt fuer Cloud-Architektur mit vielen Details",
            "score": 8,
            "employment_type": "freelance",
        },
        {
            "hash": "emoji-fest-1",
            "title": "Java Entwickler",
            "company": "FestCorp",
            "source": "manuell",
            "description": "Eine Festanstellung als Java-Entwickler mit vielen Aufgaben",
            "score": 7,
            "employment_type": "festanstellung",
        },
        {
            "hash": "emoji-other-1",
            "title": "Zeitarbeit Data Science",
            "company": "OtherCorp",
            "source": "manuell",
            "description": "Eine Zeitarbeit im Bereich Data Science mit spannenden Themen",
            "score": 6,
            "employment_type": "zeitarbeit",
        },
        {
            "hash": "emoji-empty-1",
            "title": "Unbekannter Typ",
            "company": "EmptyCorp",
            "source": "manuell",
            "description": "Eine Stelle ohne angegebenen Typ und vielen weiteren Details",
            "score": 5,
        },
    ])

    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import jobs as jobs_mod
    jobs_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    result = fake_mcp.tools["stellen_anzeigen"]()
    # Index by original title (without emoji prefix)
    stellen = {}
    for s in result["stellen"]:
        # Strip emoji prefix to map back to original title
        for prefix in ("🟢 ", "🔵 ", "⚪ "):
            if s["titel"].startswith(prefix):
                stellen[s["titel"][len(prefix):]] = s
                break

    # Freelance → 🟢
    fl = stellen["Cloud Architekt Projekt"]
    assert fl["titel"].startswith("🟢")
    assert fl["typ_label"] == "🟢 Freelance"
    assert fl["typ"] == "freelance"

    # Festanstellung → 🔵
    fe = stellen["Java Entwickler"]
    assert fe["titel"].startswith("🔵")
    assert fe["typ_label"] == "🔵 Festanstellung"
    assert fe["typ"] == "festanstellung"

    # Zeitarbeit (sonstige) → ⚪
    za = stellen["Zeitarbeit Data Science"]
    assert za["titel"].startswith("⚪")
    assert za["typ_label"] == "⚪ Sonstige"

    # Kein employment_type → default 'festanstellung' from DB → 🔵
    em = stellen["Unbekannter Typ"]
    assert em["titel"].startswith("🔵")
    assert em["typ_label"] == "🔵 Festanstellung"
