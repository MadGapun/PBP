"""Gemeinsame Profil-Logik für Dashboard und MCP-Tools."""

import json


PROFILE_COMPLETENESS_CHECKS = (
    ("name", "Name"),
    ("kontakt", "Kontaktdaten (E-Mail/Telefon)"),
    ("adresse", "Adresse"),
    ("zusammenfassung", "Kurzprofil/Summary"),
    ("berufserfahrung", "Berufserfahrung"),
    ("projekte", "Projekte (STAR)"),
    ("ausbildung", "Ausbildung"),
    ("skills", "Skills"),
    ("praeferenzen", "Job-Praeferenzen"),
)


def get_profile_preferences(profile: dict | None) -> dict:
    """Liefert Job-Praeferenzen als robust geparstes Dict."""
    if not profile:
        return {}

    prefs = profile.get("preferences", {})
    if isinstance(prefs, dict):
        return prefs
    if not prefs:
        return {}
    if isinstance(prefs, str):
        try:
            data = json.loads(prefs)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def summarize_profile(profile: dict | None) -> dict:
    """Erzeugt eine kleine gemeinsame Profil-Zusammenfassung."""
    if not profile:
        return {
            "name": None,
            "positionen": 0,
            "skills": 0,
            "dokumente": 0,
        }

    return {
        "name": profile.get("name"),
        "positionen": len(profile.get("positions", [])),
        "skills": len(profile.get("skills", [])),
        "dokumente": len(profile.get("documents", [])),
    }


def get_profile_status_payload(
    profile: dict | None,
    dashboard_url: str = "http://localhost:8200",
) -> dict:
    """Liefert die gemeinsame Payload für den MCP-Profilstatus."""
    if profile is None:
        return {
            "status": "kein_profil",
            "nachricht": "Noch kein Profil vorhanden. Bitte starte die Ersterfassung mit profil_erstellen().",
            "dashboard_url": dashboard_url,
        }

    summary = summarize_profile(profile)
    return {
        "status": "vorhanden",
        "name": summary["name"],
        "positionen": summary["positionen"],
        "skills": summary["skills"],
        "dokumente": summary["dokumente"],
        "dashboard_url": dashboard_url,
    }


def _build_profile_checks(profile: dict | None) -> dict:
    """Berechnet die Roh-Checks für die Profilvollstaendigkeit."""
    if not profile:
        return {}

    positions = profile.get("positions", [])
    education = profile.get("education", [])
    skills = profile.get("skills", [])
    prefs = get_profile_preferences(profile)

    return {
        "name": bool(profile.get("name")),
        "kontakt": bool(profile.get("email") or profile.get("phone")),
        "adresse": bool(profile.get("address") or profile.get("city")),
        "zusammenfassung": bool(profile.get("summary")),
        "berufserfahrung": len(positions) > 0,
        "projekte": any(pos.get("projects") for pos in positions),
        "ausbildung": len(education) > 0,
        "skills": len(skills) > 0,
        "praeferenzen": bool(prefs.get("stellentyp")),
    }


def get_profile_completeness(profile: dict | None) -> dict:
    """Berechnet Profilvollstaendigkeit für Dashboard und Tools."""
    checks = _build_profile_checks(profile)
    total = len(PROFILE_COMPLETENESS_CHECKS)
    if not checks:
        return {"completeness": 0, "complete": 0, "total": total, "checks": {}}

    complete = sum(1 for value in checks.values() if value)
    return {
        "completeness": int(complete / total * 100),
        "complete": complete,
        "total": total,
        "checks": checks,
    }


def get_profile_completeness_labels(profile: dict | None) -> dict:
    """Liefert dieselben Vollstaendigkeitsregeln mit Nutzer-Labels."""
    checks = _build_profile_checks(profile)
    return {
        label: checks.get(key, False)
        for key, label in PROFILE_COMPLETENESS_CHECKS
    }
