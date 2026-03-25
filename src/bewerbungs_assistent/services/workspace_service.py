"""Gemeinsame Workspace-Logik für Dashboard-Navigation und Guidance."""

from datetime import date

from .profile_service import (
    get_profile_completeness,
    get_profile_completeness_labels,
    summarize_profile,
)


def summarize_follow_ups(follow_ups, today: str | None = None) -> dict:
    """Summarize follow-up totals and due count."""
    items = list(follow_ups or [])
    today_iso = today or date.today().isoformat()
    due = sum(1 for item in items if item.get("scheduled_date", "") <= today_iso)
    return {"total": len(items), "due": due}


def format_nav_badge(count: int) -> str | None:
    """Compact count label for badges in the dashboard navigation."""
    if count <= 0:
        return None
    return "99+" if count > 99 else str(count)


def build_workspace_summary(
    profile: dict | None,
    jobs,
    applications,
    source_summary: dict,
    search_status: dict,
    follow_up_summary: dict,
) -> dict:
    """Aggregate the workspace state for top-level guidance."""
    jobs = list(jobs or [])
    applications = list(applications or [])
    profile_summary = summarize_profile(profile)
    completeness = get_profile_completeness(profile)

    missing_areas = []
    if profile:
        missing_areas = [
            label for label, ok in get_profile_completeness_labels(profile).items() if not ok
        ]

    readiness = {
        "stage": "onboarding",
        "label": "Startklar machen",
        "tone": "blue",
        "headline": "Lass uns starten \u2014 erz\u00e4hl Claude kurz von dir.",
        "description": "Im ersten Schritt lernst du Claude kennen. Er fragt dich Schritt f\u00fcr Schritt nach deinen Daten. Du musst nichts vorbereiten.",
        "next_page": "dashboard",
        "action_label": "Profil starten",
        "action_type": "prompt",
        "action_target": "/ersterfassung",
    }

    if profile:
        readiness = {
            "stage": "im_fluss",
            "label": "Im Fluss",
            "tone": "green",
            "headline": "Alles bereit \u2014 du kannst loslegen.",
            "description": "Schau dir neue Stellen an, bewirb dich oder frag Claude nach Tipps f\u00fcr deine n\u00e4chsten Schritte.",
            "next_page": "dashboard",
            "action_label": "Dashboard ansehen",
            "action_type": "page",
            "action_target": "dashboard",
        }

        if completeness["completeness"] < 60:
            readiness = {
                "stage": "profil_aufbauen",
                "label": "Profil ausbauen",
                "tone": "yellow",
                "headline": "Dein Profil ist noch nicht vollständig.",
                "description": "Je mehr Claude über dich weiß, desto bessere Anschreiben und Stellenvorschläge bekommst du.",
                "next_page": "profil",
                "action_label": "Profil vervollständigen",
                "action_type": "page",
                "action_target": "profil",
            }
        elif source_summary["active"] == 0:
            readiness = {
                "stage": "quellen_aktivieren",
                "label": "Quellen aktivieren",
                "tone": "yellow",
                "headline": "Die Jobsuche ist noch nicht startbereit.",
                "description": "Wähle aus, auf welchen Jobbörsen PBP nach Stellen für dich suchen soll.",
                "next_page": "einstellungen",
                "action_label": "Quellen einrichten",
                "action_type": "page",
                "action_target": "einstellungen",
            }
        elif search_status["status"] in {"nie", "veraltet", "dringend"}:
            readiness = {
                "stage": "jobsuche_erneuern",
                "label": "Jobsuche erneuern",
                "tone": "blue" if search_status["status"] == "nie" else "yellow",
                "headline": "Es ist Zeit für eine frische Jobsuche.",
                "description": "Starte eine neue Suche, damit du keine passenden Stellen verpasst.",
                "next_page": "dashboard",
                "action_label": "Jobsuche starten",
                "action_type": "prompt",
                "action_target": "/jobsuche_workflow",
            }
        elif jobs and not applications:
            readiness = {
                "stage": "bewerben",
                "label": "Jetzt bewerben",
                "tone": "green",
                "headline": "Du hast passende Stellen, aber noch keine Bewerbungen erfasst.",
                "description": "Schau dir die Stellen an und entscheide, wo du dich bewerben möchtest.",
                "next_page": "stellen",
                "action_label": "Stellen prüfen",
                "action_type": "page",
                "action_target": "stellen",
            }
        elif follow_up_summary["due"] > 0:
            readiness = {
                "stage": "nachfassen",
                "label": "Nachfassen",
                "tone": "red",
                "headline": "Es gibt überfällige Nachfassaktionen.",
                "description": "Einige Bewerbungen warten auf deine Rückmeldung — schau kurz rein.",
                "next_page": "bewerbungen",
                "action_label": "Bewerbungen prüfen",
                "action_type": "page",
                "action_target": "bewerbungen",
            }

    # #180: Zähle aktive Jobs ohne Beschreibung — Dashboard-Hinweis
    jobs_ohne_beschreibung = sum(
        1 for j in jobs
        if len((j.get("description") or "").strip()) < 50 and j.get("score", 0) > 0
    )

    # Aufgaben/Todos für das Dashboard (#180, #182)
    todos = []
    if jobs_ohne_beschreibung > 0:
        todos.append({
            "typ": "beschreibung_nachladen",
            "prioritaet": "hoch",
            "text": f"{jobs_ohne_beschreibung} Stellen ohne Beschreibung — Score ist unzuverlässig. "
                    "Öffne die Stellen und lade die Beschreibung nach.",
            "aktion": "stellen_anzeigen(beschreibung_fehlt=True)",
        })

    return {
        "has_profile": profile is not None,
        "profile_name": profile_summary["name"],
        "profile": {
            "completeness": completeness["completeness"],
            "complete": completeness["complete"],
            "total": completeness["total"],
            "missing_areas": missing_areas,
            "positionen": profile_summary["positionen"],
            "skills": profile_summary["skills"],
            "dokumente": profile_summary["dokumente"],
        },
        "sources": source_summary,
        "search": search_status,
        "jobs": {"active": len(jobs), "ohne_beschreibung": jobs_ohne_beschreibung},
        "todos": todos,
        "applications": {
            "total": len(applications),
            "follow_ups_total": follow_up_summary["total"],
            "follow_ups_due": follow_up_summary["due"],
        },
        "readiness": readiness,
        "navigation": {
            "jobs_badge": format_nav_badge(len(jobs)),
            "applications_badge": format_nav_badge(len(applications)),
            "settings_badge": format_nav_badge(
                (1 if source_summary["active"] == 0 else 0)
                + (1 if source_summary["active"] > 0
                   and search_status["status"] in {"nie", "dringend"} else 0)
            ),
            "profile_badge": format_nav_badge(len(missing_areas)),
        },
    }
