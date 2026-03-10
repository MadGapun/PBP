"""Unit-Tests fuer den kleinen Profil-Service-Layer."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bewerbungs_assistent.services.profile_service import (  # noqa: E402
    get_profile_completeness,
    get_profile_completeness_labels,
    get_profile_preferences,
    get_profile_status_payload,
    summarize_profile,
)


def test_profile_status_without_profile():
    """Ohne Profil gibt der Service die Erststart-Payload zurueck."""
    data = get_profile_status_payload(None)
    assert data["status"] == "kein_profil"
    assert "profil_erstellen" in data["nachricht"]
    assert data["dashboard_url"] == "http://localhost:8200"


def test_profile_status_with_counts():
    """Mit Profil werden die wichtigsten Mengen konsistent zusammengefasst."""
    profile = {
        "name": "Max Mustermann",
        "positions": [{}, {}],
        "skills": [{}, {}, {}],
        "documents": [{}],
    }

    summary = summarize_profile(profile)
    status = get_profile_status_payload(profile)

    assert summary == {
        "name": "Max Mustermann",
        "positionen": 2,
        "skills": 3,
        "dokumente": 1,
    }
    assert status["status"] == "vorhanden"
    assert status["name"] == "Max Mustermann"
    assert status["positionen"] == 2
    assert status["skills"] == 3
    assert status["dokumente"] == 1


def test_profile_completeness_supports_string_preferences_and_address():
    """String-Praeferenzen und reine Adresse werden korrekt ausgewertet."""
    profile = {
        "name": "Test",
        "email": "test@example.com",
        "address": "Musterstrasse 1",
        "summary": "Kurzprofil",
        "positions": [{"projects": [{"name": "Projekt A"}]}],
        "education": [{"institution": "FH Hamburg"}],
        "skills": [{"name": "Python"}],
        "preferences": '{"stellentyp": "festanstellung"}',
    }

    data = get_profile_completeness(profile)

    assert data["complete"] == 9
    assert data["completeness"] == 100
    assert data["checks"]["adresse"] is True
    assert data["checks"]["praeferenzen"] is True


def test_profile_completeness_labels_match_public_wording():
    """Die Nutzer-Labels bleiben stabil fuer Summary und Dashboard-Text."""
    labels = get_profile_completeness_labels({"name": "Test"})
    assert list(labels) == [
        "Name",
        "Kontaktdaten (E-Mail/Telefon)",
        "Adresse",
        "Kurzprofil/Summary",
        "Berufserfahrung",
        "Projekte (STAR)",
        "Ausbildung",
        "Skills",
        "Job-Praeferenzen",
    ]
    assert labels["Name"] is True
    assert labels["Adresse"] is False


def test_profile_preferences_invalid_json_returns_empty_dict():
    """Ungueltige Preferences aus Importen sollen nicht mehr abstuerzen."""
    prefs = get_profile_preferences({"preferences": "{ungueltig"})
    assert prefs == {}
