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



# ── Readiness-Stufen (#984 G32) ──────────────────────────────────────
#
# Vorher standen die sieben Stufen als Wortblöcke mitten in der
# Verzweigung von `build_workspace_summary`. Sie hier zu sammeln macht
# zweierlei möglich: der Wächter-Test kann jede Stufe einzeln prüfen,
# ohne den Zustand einer Datenbank nachzustellen, und eine Textregel
# ändert man an einer Stelle statt an sieben.
#
# Die Reihenfolge der Auswahl steckt weiterhin in der Funktion — sie
# hängt vom Zustand ab, nicht vom Text.
READINESS_STUFEN: dict[str, dict] = {
    "onboarding": {
        "stage": "onboarding",
        "label": "Startklar machen",
        "tone": "blue",
        "headline": "Lass uns starten — erzähl Claude kurz von dir.",
        "description": "Im ersten Schritt lernst du Claude kennen. Er fragt dich Schritt für Schritt nach deinen Daten. Du musst nichts vorbereiten.",
        "next_page": "dashboard",
        "action_label": "Profil starten",
        "action_type": "prompt",
        "action_target": "/ersterfassung",
    },
    "im_fluss": {
        "stage": "im_fluss",
        "label": "Im Fluss",
        "tone": "green",
        "headline": "Alles bereit — du kannst loslegen.",
        "description": "Schau dir neue Stellen an, bewirb dich oder frag Claude nach Tipps für deine nächsten Schritte.",
        "next_page": "dashboard",
        "action_label": "Dashboard ansehen",
        "action_type": "page",
        "action_target": "dashboard",
    },
    "profil_aufbauen": {
        "stage": "profil_aufbauen",
        "label": "Profil ausbauen",
        "tone": "yellow",
        "headline": "Dein Profil ist noch nicht vollständig.",
        "description": "Je mehr Claude über dich weiß, desto bessere Anschreiben und Stellenvorschläge bekommst du.",
        "next_page": "profil",
        "action_label": "Profil vervollständigen",
        "action_type": "page",
        "action_target": "profil",
    },
    "quellen_aktivieren": {
        "stage": "quellen_aktivieren",
        "label": "Quellen aktivieren",
        "tone": "yellow",
        "headline": "Die Jobsuche ist noch nicht startbereit.",
        "description": "Wähle aus, auf welchen Jobbörsen PBP nach Stellen für dich suchen soll.",
        "next_page": "einstellungen",
        "action_label": "Quellen einrichten",
        "action_type": "page",
        "action_target": "einstellungen",
    },
    "jobsuche_erneuern": {
        "stage": "jobsuche_erneuern",
        "label": "Jobsuche erneuern",
        "tone": "yellow",
        "headline": "Es ist Zeit für eine frische Jobsuche.",
        "description": "Starte eine neue Suche, damit du keine passenden Stellen verpasst.",
        "next_page": "dashboard",
        # v1.7.114 (#1049): ein Prompt an Claude, kein interner Lauf.
        "action_label": "Jobsuche mit Claude",
        "action_type": "prompt",
        "action_target": "/jobsuche_workflow",
    },
    "bewerben": {
        "stage": "bewerben",
        "label": "Jetzt bewerben",
        "tone": "green",
        "headline": "Du hast passende Stellen, aber noch keine Bewerbungen erfasst.",
        "description": "Schau dir die Stellen an und entscheide, wo du dich bewerben möchtest.",
        "next_page": "stellen",
        "action_label": "Stellen prüfen",
        "action_type": "page",
        "action_target": "stellen",
    },
    "nachfassen": {
        "stage": "nachfassen",
        "label": "Nachfassen",
        "tone": "red",
        "headline": "Es gibt überfällige Nachfassaktionen.",
        "description": "Einige Bewerbungen warten auf deine Rückmeldung — schau kurz rein.",
        "next_page": "bewerbungen",
        "action_label": "Bewerbungen prüfen",
        "action_type": "page",
        "action_target": "bewerbungen",
    },
}


def _badge_titel(stellen: int, faellig: int, quellen: dict, suche: dict,
                 fehlend: list) -> dict:
    """Was die Zahl in der Seitenleiste bedeutet (G61, #1087 B6)."""
    titel = {}
    if stellen:
        titel["stellen"] = (f"{stellen} Stelle wartet" if stellen == 1
                            else f"{stellen} Stellen warten") + " auf deine Entscheidung"
    if faellig:
        titel["bewerbungen"] = (f"{faellig} Nachfassung ist" if faellig == 1
                                else f"{faellig} Nachfassungen sind") + " fällig"
    einstellungen = []
    if quellen.get("active", 0) == 0:
        einstellungen.append("keine Jobbörse ausgewählt")
    elif suche.get("status") in {"nie", "dringend"}:
        einstellungen.append("noch keine Suche" if suche.get("status") == "nie"
                             else "letzte Suche liegt lange zurück")
    if einstellungen:
        satz = "; ".join(einstellungen)
        titel["einstellungen"] = satz[:1].upper() + satz[1:]
    if fehlend:
        titel["profil"] = "Im Profil fehlt noch: " + ", ".join(fehlend)
    return titel


def readiness_stufe(stage: str, **ueberschreibungen) -> dict:
    """Eine Readiness-Stufe als frische Kopie, optional mit Abweichungen."""
    stufe = dict(READINESS_STUFEN[stage])
    stufe.update(ueberschreibungen)
    return stufe


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
    archive_statuses = {"abgelehnt", "zurueckgezogen", "abgelaufen"}
    active_applications = [a for a in applications if a.get("status") not in archive_statuses]
    profile_summary = summarize_profile(profile)
    completeness = get_profile_completeness(profile)

    missing_areas = []
    if profile:
        missing_areas = [
            label for label, ok in get_profile_completeness_labels(profile).items() if not ok
        ]

    readiness = readiness_stufe("onboarding")

    if profile:
        readiness = readiness_stufe("im_fluss")

        if completeness["completeness"] < 60:
            readiness = readiness_stufe("profil_aufbauen")
        elif source_summary["active"] == 0:
            readiness = readiness_stufe("quellen_aktivieren")
        elif search_status["status"] in {"nie", "veraltet", "dringend"}:
            readiness = readiness_stufe(
                "jobsuche_erneuern",
                tone="blue" if search_status["status"] == "nie" else "yellow",
            )
        elif jobs and not applications:
            readiness = readiness_stufe("bewerben")
        elif follow_up_summary["due"] > 0:
            readiness = readiness_stufe("nachfassen")

    # #397: Inactivity detection — check when user last took meaningful action
    from datetime import datetime, timedelta
    inactivity_days = None
    inactivity_hint = None
    if applications:
        last_dates = []
        for a in applications:
            for field in ("applied_at", "updated_at", "created_at"):
                d = a.get(field)
                if d:
                    last_dates.append(d[:10])
                    break
        if last_dates:
            try:
                last_activity = max(last_dates)
                days_since = (datetime.now() - datetime.strptime(last_activity, "%Y-%m-%d")).days
                if days_since >= 7:
                    inactivity_days = days_since
                    if days_since >= 21:
                        inactivity_hint = f"Seit {days_since} Tagen keine Aktivität — brauchst du Hilfe beim Wiedereinstieg?"
                    elif days_since >= 14:
                        inactivity_hint = f"Seit {days_since} Tagen nichts passiert — schau mal nach deinen offenen Bewerbungen."
                    else:
                        inactivity_hint = f"Letzte Aktivität vor {days_since} Tagen. Bleib dran!"
            except (ValueError, TypeError):
                pass

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
            "active": len(active_applications),
            "archived": len(applications) - len(active_applications),
            "follow_ups_total": follow_up_summary["total"],
            "follow_ups_due": follow_up_summary["due"],
        },
        "inactivity": {
            "days": inactivity_days,
            "hint": inactivity_hint,
        } if inactivity_days else None,
        "readiness": readiness,
        # G61 (#1087 B6): eine Zahl in der Seitenleiste heisst "hier
        # braucht etwas Aufmerksamkeit", und ihr Titel sagt was. Bis
        # v1.7.135 zaehlte die Bewerbungen-Zahl alle laufenden
        # Bewerbungen — eine Zahl, bei der nichts zu tun ist.
        "navigation": {
            "jobs_badge": format_nav_badge(len(jobs)),
            "applications_badge": format_nav_badge(follow_up_summary["due"]),
            "settings_badge": format_nav_badge(
                (1 if source_summary["active"] == 0 else 0)
                + (1 if source_summary["active"] > 0
                   and search_status["status"] in {"nie", "dringend"} else 0)
            ),
            "profile_badge": format_nav_badge(len(missing_areas)),
            "titel": _badge_titel(len(jobs), follow_up_summary["due"],
                                  source_summary, search_status, missing_areas),
        },
    }


def workspace_aus_db(db) -> dict:
    """Der Arbeitsstand aus der Datenbank — fuer Dashboard und Claude (H32).

    Bis v1.7.134 setzte nur das Dashboard ihn zusammen; `profil_status`
    nannte deshalb mit Profil gar keinen naechsten Schritt.
    """
    from datetime import datetime
    from ..job_scraper import SOURCE_REGISTRY
    from .search_service import aktive_quellen, get_search_status, summarize_active_sources

    return build_workspace_summary(
        profile=db.get_profile(),
        jobs=db.get_active_jobs(exclude_applied=True, exclude_blacklisted=True),
        applications=db.get_applications(),
        source_summary=summarize_active_sources(
            aktive_quellen(db, SOURCE_REGISTRY) or [], SOURCE_REGISTRY.keys()),
        search_status=get_search_status(
            db.get_profile_setting("last_search_at"), now=datetime.now()),
        follow_up_summary=summarize_follow_ups(db.get_pending_follow_ups()),
    )


def naechster_schritt(db, summary: dict | None = None) -> dict:
    """Der naechste Schritt als Satz fuer Claude, aus derselben Lage wie
    die Readiness-Stufe im Dashboard (H32, #1087 G14)."""
    from .dashboard_link import dashboard_link
    s = summary or workspace_aus_db(db)
    stufe = (s.get("readiness") or {}).get("stage", "onboarding")
    try:
        kriterien = db.get_search_criteria() or {}
    except Exception:
        kriterien = {}
    profil = s.get("profile") or {}
    if stufe == "profil_aufbauen":
        fehlt = ", ".join(profil.get("missing_areas") or []) or "einige Angaben"
        return {"stufe": stufe, "text": (
            f"Das Profil ist noch unvollständig (es fehlen: {fehlt}). Lebenslauf "
            "hochladen und mit extraktion_starten() übernehmen, oder im Gespräch "
            "ergänzen: workflow_starten(name='profil_ueberpruefen').")}
    if s.get("has_profile") and not kriterien.get("keywords_muss"):
        return {"stufe": "suchbegriffe", "text": (
            "Es gibt noch keine Suchbegriffe. Leite sie aus dem Profil ab "
            "(keyword_vorschlaege()) und setze sie mit suchkriterien_setzen().")}
    if stufe == "quellen_aktivieren":
        return {"stufe": stufe, "text": (
            "Es ist keine Jobbörse ausgewählt. Das geht im Dashboard unter "
            f"Einstellungen › Quellen: {dashboard_link('einstellungen')}")}
    if stufe == "jobsuche_erneuern":
        nie = (s.get("search") or {}).get("status") == "nie"
        return {"stufe": stufe, "text": (
            ("Es lief noch keine Suche. " if nie else "Die letzte Suche ist älter als eine Woche. ")
            + "Starte sie mit jobsuche_starten(); den Stand fragt jobsuche_status().")}
    if stufe == "bewerben":
        return {"stufe": stufe, "text": (
            f"{(s.get('jobs') or {}).get('active', 0)} Stellen warten auf eine Entscheidung: "
            "stellen_anzeigen().")}
    if stufe == "nachfassen":
        return {"stufe": stufe, "text": (
            f"{(s.get('applications') or {}).get('follow_ups_due', 0)} Nachfassungen sind "
            "fällig: aufgaben_uebersicht().")}
    return {"stufe": stufe, "text": (
        "Alles eingerichtet. Offenes zeigt aufgaben_uebersicht(), neue Stellen "
        "stellen_anzeigen().")}
