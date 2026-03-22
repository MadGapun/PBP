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
        "headline": "Lege dein Profil an oder importiere vorhandene Unterlagen.",
        "description": "Ohne Profil kann PBP noch nicht für Jobsuche, Export oder Bewerbungen arbeiten.",
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
            "headline": "Dein Setup ist arbeitsfähig.",
            "description": "Prüfe neue Stellen, halte Bewerbungen aktuell und nutze Claude für die nächsten Schritte.",
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
                "headline": "Dein Profil braucht noch mehr Substanz.",
                "description": "Je vollständiger dein Profil, desto besser funktionieren Matching, Anschreiben und Exporte.",
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
                "description": "Aktiviere mindestens eine Quelle, damit Claude oder das Dashboard Stellen finden können.",
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
                "description": "Regelmäßige Suchen halten deine Treffer aktuell und vermeiden alte Stellenlisten.",
                "next_page": "dashboard",
                "action_label": "/jobsuche_workflow kopieren",
                "action_type": "prompt",
                "action_target": "/jobsuche_workflow",
            }
        elif jobs and not applications:
            readiness = {
                "stage": "bewerben",
                "label": "Jetzt bewerben",
                "tone": "green",
                "headline": "Du hast passende Stellen, aber noch keine Bewerbungen erfasst.",
                "description": "Nutze die Stellenkarten oder den Bewerbungs-Wizard, um Momentum aufzubauen.",
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
                "description": "Aktualisiere den Bewerbungsstatus oder plane ein Follow-up, damit nichts liegen bleibt.",
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
