"""Test fixtures for Bewerbungs-Assistent."""

import sys
import os
import tempfile
import pytest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture
def tmp_db(tmp_path):
    """Create a fresh temporary database."""
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    yield db
    db.close()
    if "BA_DATA_DIR" in os.environ:
        del os.environ["BA_DATA_DIR"]


@pytest.fixture
def sample_profile():
    """Sample profile data for testing."""
    return {
        "name": "Max Mustermann",
        "email": "max@example.com",
        "phone": "+49 171 1234567",
        "address": "Musterstrasse 42",
        "city": "Hamburg",
        "plz": "20095",
        "country": "Deutschland",
        "birthday": "1985-03-15",
        "nationality": "Deutsch",
        "summary": "Erfahrener IT-Consultant mit 10 Jahren Expertise in PLM.",
        "informal_notes": "Suche neue Herausforderung, gerne hybrid.",
        "preferences": {
            "stellentyp": "beides",
            "arbeitsmodell": "hybrid",
            "min_gehalt": 70000,
            "ziel_gehalt": 85000,
            "min_tagessatz": 700,
            "ziel_tagessatz": 900,
            "reisebereitschaft": "mittel",
            "umzug_moeglich": False,
        },
    }


@pytest.fixture
def sample_position():
    """Sample position data."""
    return {
        "company": "Tech GmbH",
        "title": "Senior PLM Consultant",
        "location": "Hamburg",
        "start_date": "2018-01",
        "end_date": "",
        "is_current": True,
        "employment_type": "festanstellung",
        "industry": "IT-Beratung",
        "description": "PLM-Einfuehrung und -Optimierung.",
        "tasks": "Kundenberatung, Systemkonfiguration, Schulungen",
        "achievements": "15 erfolgreiche PLM-Projekte, 30% Effizienzsteigerung",
        "technologies": "Windchill, SAP, Python",
    }


@pytest.fixture
def sample_project():
    """Sample STAR project data."""
    return {
        "name": "PLM-Migration Automotive",
        "description": "Migration von Legacy-System zu Windchill 12",
        "role": "Projektleiter",
        "situation": "Veraltetes PDM-System mit 500.000 Dokumenten",
        "task": "Migration auf Windchill 12 ohne Produktionsstillstand",
        "action": "Phasenweise Migration mit automatisierter Datenpruefung",
        "result": "100% Datenmigration, 0 Tage Ausfall, 20% schnellere Suchanfragen",
        "technologies": "Windchill 12, Python, REST API",
        "duration": "12 Monate",
    }


@pytest.fixture
def sample_jobs():
    """Sample job listings for testing."""
    return [
        {
            "hash": "abc123456789",
            "title": "PLM Consultant (m/w/d)",
            "company": "Siemens",
            "location": "Hamburg",
            "url": "https://example.com/job1",
            "source": "stepstone",
            "description": "PLM Consultant fuer Teamcenter Einfuehrung",
            "score": 8,
            "remote_level": "hybrid",
            "employment_type": "festanstellung",
        },
        {
            "hash": "def123456789",
            "title": "Junior Java Developer",
            "company": "StartupXY",
            "location": "Berlin",
            "url": "https://example.com/job2",
            "source": "indeed",
            "description": "Java Entwickler fuer Backend",
            "score": 2,
            "remote_level": "unbekannt",
            "employment_type": "festanstellung",
        },
    ]
