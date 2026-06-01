"""Onboarding-Hints fuer ungenutzte Features (#652, G11, beta.76).

Hint-System fuer Features die im Code da sind, vom User aber kaum
genutzt werden. Reality-Check 2026-06-01 hat 3 Faelle aufgedeckt:

- 0 Suchprofile bei 4+ Bewerbungen
- 0 Reisekosten/Vorbereitungszeit-Eintraege bei vielen Terminen
- 0 Interview-Reflexionen bei mehreren Interview-Status

Frontend-Komponente kommt separat. Backend liefert:
- `list_active_hints(db)` — alle Hints mit erfuellter Bedingung + nicht
  dismissed
- `dismiss_hint(db, hint_id)` — persistiert die Wegklick-Entscheidung

Hints werden ueber `HINT_DEFINITIONS` deklariert. Pro Hint:
- `id`: stabiler String, persistiert
- `tab`: Wo der Hint sinnvoll waere (frontend-Routing-Hilfe)
- `title`: 1-Zeiler fuer die Card
- `body`: kurzer Text mit konkretem Vorschlag
- `cta_label`: Button-Text
- `cta_tool`: MCP-Tool-Vorschlag (Claude-Hint), oder leer
- `condition(db)`: liefert True wenn der Hint erscheinen soll
"""
from __future__ import annotations

import json
from typing import Callable


# Setting-Key fuer dismissed Hints (JSON-Liste)
_DISMISSED_KEY = "onboarding_hints_dismissed"


def _get_dismissed(db) -> list[str]:
    """Liest die Liste der bisher dismissten Hint-IDs aus profile_settings."""
    try:
        raw = db.get_setting(_DISMISSED_KEY, "") or ""
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data]
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return []


def _set_dismissed(db, hint_ids: list[str]) -> None:
    """Schreibt die Liste der dismissten Hint-IDs zurueck."""
    try:
        db.set_setting(_DISMISSED_KEY, json.dumps(sorted(set(hint_ids))))
    except Exception:
        pass


# ── Condition-Helper ────────────────────────────────────────────────


def _condition_keine_suchprofile_aber_bewerbungen(db) -> bool:
    """Hint sinnvoll wenn: 0 Suchprofile + >=3 Bewerbungen."""
    try:
        profile_rows = db.connect().execute(
            "SELECT COUNT(*) AS n FROM portal_search_profiles WHERE "
            "(profile_id=? OR profile_id IS NULL)",
            (db.get_active_profile_id(),)
        ).fetchone()
        if not profile_rows or (profile_rows["n"] or 0) > 0:
            return False
        apps = db.get_applications(limit=0)
        return len(apps) >= 3
    except Exception:
        return False


def _condition_keine_aufwandskosten_aber_termine(db) -> bool:
    """Hint sinnvoll wenn: >=5 Meetings + 0 Reisekosten/Vorbereitungszeit-Eintraege."""
    try:
        conn = db.connect()
        pid = db.get_active_profile_id()
        meeting_count = conn.execute(
            "SELECT COUNT(*) AS n FROM meetings WHERE "
            "(profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()
        if not meeting_count or (meeting_count["n"] or 0) < 5:
            return False
        kosten_count = conn.execute(
            "SELECT COUNT(*) AS n FROM application_costs WHERE "
            "(profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()
        if kosten_count and (kosten_count["n"] or 0) > 0:
            return False
        # Plus: Vorbereitungszeit pruefen (kommt aus meetings.preparation_minutes)
        prep_count = conn.execute(
            "SELECT COUNT(*) AS n FROM meetings WHERE "
            "(profile_id=? OR profile_id IS NULL) AND preparation_minutes > 0",
            (pid,)
        ).fetchone()
        return not (prep_count and (prep_count["n"] or 0) > 0)
    except Exception:
        return False


def _condition_keine_interview_reflexion_aber_interviews(db) -> bool:
    """Hint sinnvoll wenn: >=2 Bewerbungen mit Interview-Status + 0 Reflexionen."""
    try:
        conn = db.connect()
        pid = db.get_active_profile_id()
        INTERVIEW_STATUSES = (
            "interview", "zweitgespraech", "interview_abgeschlossen",
        )
        placeholders = ",".join("?" for _ in INTERVIEW_STATUSES)
        interview_count = conn.execute(
            f"SELECT COUNT(*) AS n FROM applications WHERE "
            f"(profile_id=? OR profile_id IS NULL) "
            f"AND status IN ({placeholders})",
            (pid, *INTERVIEW_STATUSES)
        ).fetchone()
        if not interview_count or (interview_count["n"] or 0) < 2:
            return False
        reflexion_count = conn.execute(
            "SELECT COUNT(*) AS n FROM interview_reflections WHERE "
            "(profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()
        return not (reflexion_count and (reflexion_count["n"] or 0) > 0)
    except Exception:
        return False


# ── Hint-Definitionen ───────────────────────────────────────────────

HINT_DEFINITIONS: list[dict] = [
    {
        "id": "g11_suchprofile_anlegen",
        "tab": "stellen",
        "title": "Tipp: Suchprofile sparen Zeit",
        "body": (
            "Du hast schon mehrere Bewerbungen — aber noch kein Suchprofil. "
            "Suchprofile speichern deine Kriterien (Region, Gehalt, Stellenart, "
            "Keywords) damit jede neue Jobsuche sie automatisch nutzt."
        ),
        "cta_label": "Suchprofil aus aktuellen Kriterien erstellen",
        "cta_tool": "suchprofil_aktualisieren",
        "condition": _condition_keine_suchprofile_aber_bewerbungen,
    },
    {
        "id": "g11_aufwand_tracken",
        "tab": "kalender",
        "title": "Tipp: Aufwand-Tracking fuer's Arbeitsamt",
        "body": (
            "Du hast schon Termine — aber noch keine Reisekosten oder "
            "Vorbereitungszeit erfasst. Wenige Klicks, dafuer eine saubere "
            "Aufwand-Uebersicht (wichtig fuer Arbeitsamt + steuerliche Geltendmachung)."
        ),
        "cta_label": "Aufwand fuer den naechsten Termin erfassen",
        "cta_tool": "kosten_erfassen",
        "condition": _condition_keine_aufwandskosten_aber_termine,
    },
    {
        "id": "g11_interview_reflexion",
        "tab": "bewerbungen",
        "title": "Tipp: Interview-Reflexionen zahlen sich aus",
        "body": (
            "Du hast schon Interview-Termine — aber noch keine Reflexion "
            "festgehalten. Was lief gut, was wuerdest du anders machen? "
            "Wenige Minuten Aufwand jetzt, viel weniger Gefuehlskram im "
            "naechsten Interview."
        ),
        "cta_label": "Reflexion zum letzten Interview erfassen",
        "cta_tool": "interview_reflexion_speichern",
        "condition": _condition_keine_interview_reflexion_aber_interviews,
    },
]


# ── Public API ──────────────────────────────────────────────────────


def list_active_hints(db) -> list[dict]:
    """Liefert alle Hints deren Condition erfuellt ist UND die nicht
    dismissed sind."""
    dismissed = set(_get_dismissed(db))
    out = []
    for h in HINT_DEFINITIONS:
        if h["id"] in dismissed:
            continue
        try:
            if h["condition"](db):
                out.append({
                    "id": h["id"],
                    "tab": h["tab"],
                    "title": h["title"],
                    "body": h["body"],
                    "cta_label": h["cta_label"],
                    "cta_tool": h["cta_tool"],
                })
        except Exception:
            continue
    return out


def dismiss_hint(db, hint_id: str) -> dict:
    """Markiert einen Hint als dismissed (persistent).

    Liefert {dismissed: True, hint_id, total_dismissed} bei Erfolg,
    {error} bei unbekanntem Hint.
    """
    valid_ids = {h["id"] for h in HINT_DEFINITIONS}
    if hint_id not in valid_ids:
        return {"error": f"Unbekannter Hint: {hint_id}", "bekannte_ids": sorted(valid_ids)}
    current = _get_dismissed(db)
    if hint_id not in current:
        current.append(hint_id)
        _set_dismissed(db, current)
    return {
        "dismissed": True,
        "hint_id": hint_id,
        "total_dismissed": len(current),
    }


def reset_dismissed_hints(db) -> dict:
    """Setzt alle dismissten Hints zurueck — fuer Testing / Settings-Reset."""
    _set_dismissed(db, [])
    return {"reset": True, "total_dismissed": 0}
