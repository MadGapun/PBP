"""Browser-Smoke-Tests fuer die wichtigsten Dashboard-Userflows."""

import os
import socket
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
import uvicorn

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

pw = pytest.importorskip("playwright")  # noqa: E402
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def _free_port() -> int:
    """Reserve an ephemeral local port for the live dashboard server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_server(base_url: str, timeout: float = 10.0) -> None:
    """Wait until the FastAPI dashboard answers HTTP requests."""
    deadline = time.time() + timeout
    last_error = None

    while time.time() < deadline:
        try:
            response = httpx.get(base_url, timeout=1.0)
            if response.status_code < 500:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(0.1)

    raise RuntimeError(f"Dashboard unter {base_url} wurde nicht rechtzeitig bereit: {last_error}")


def _dismiss_setup_overlay(page) -> None:
    """Close the first-run setup overlay when it is visible."""
    later_button = page.get_by_role("button", name="Später")
    if later_button.count():
        try:
            later_button.first.wait_for(state="visible", timeout=1500)
            later_button.first.click()
        except PlaywrightError:
            pass


@pytest.fixture
def live_dashboard(tmp_path):
    """Start a live dashboard server with a temporary SQLite database."""
    os.environ["BA_DATA_DIR"] = str(tmp_path)

    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    dash._db = db

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    config = uvicorn.Config(dash.app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # Avoid signal setup in thread.
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_for_server(base_url)

    yield {"base_url": base_url, "db": db}

    server.should_exit = True
    thread.join(timeout=10)
    dash._db = None
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture(scope="module")
def browser():
    """Reusable Chromium instance for smoke tests."""
    try:
        with sync_playwright() as playwright:
            instance = playwright.chromium.launch(headless=True)
            yield instance
            instance.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright/Chromium nicht verfuegbar: {exc}")


def _seed_ready_workspace(db) -> None:
    """Create a realistic profile/search/applications setup for guidance tests."""
    db.save_profile(
        {
            "name": "Max Tester",
            "email": "max@example.com",
            "phone": "+49 40 123456",
            "address": "Musterweg 1",
            "summary": "Erfahrener PLM-Berater",
            "preferences": {"stellentyp": "festanstellung"},
        }
    )
    position_id = db.add_position(
        {
            "company": "ACME",
            "title": "Consultant",
            "start_date": "2022-01",
        }
    )
    db.add_project(
        position_id,
        {
            "name": "PLM Rollout",
            "situation": "Internationale Einfuehrung",
            "task": "Konzept und Umsetzung",
            "action": "Architektur definiert",
            "result": "Go-live erreicht",
        },
    )
    db.add_education({"institution": "FH Hamburg", "degree": "Bachelor"})
    db.add_skill({"name": "Python", "category": "tool"})
    db.set_profile_setting("active_sources", ["bundesagentur", "stepstone"])
    db.set_profile_setting("last_search_at", datetime.now().isoformat())
    app_id = db.add_application(
        {
            "title": "Senior Consultant",
            "company": "ACME",
            "status": "beworben",
            "applied_at": datetime.now().date().isoformat(),
        }
    )
    db.add_follow_up(app_id, (datetime.now().date() - timedelta(days=1)).isoformat())


def _seed_timeline_workspace(db) -> str:
    """Create a profile with one linked job/application for timeline regressions."""
    profile_id = db.save_profile(
        {
            "name": "Max Timeline",
            "email": "timeline@example.com",
            "phone": "+49 40 123456",
            "address": "Musterweg 1",
            "city": "Hamburg",
            "plz": "20095",
            "summary": "PLM-Berater mit Fokus auf Modernisierung",
            "preferences": {"stellentyp": "festanstellung"},
        }
    )
    db.add_skill({"name": "React", "category": "tool", "level": 4, "profile_id": profile_id})
    db.set_profile_setting("active_sources", ["bundesagentur", "stepstone"])
    db.set_profile_setting("last_search_at", datetime.now().isoformat())

    now = datetime.now().isoformat()
    conn = db.connect()
    conn.execute(
        """
        INSERT OR REPLACE INTO jobs (
            hash, title, company, location, url, source, description, score,
            remote_level, salary_min, salary_max, salary_type, employment_type,
            is_active, is_pinned, profile_id, found_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?)
        """,
        (
            "timeline-job-1",
            "Senior PLM Consultant",
            "ACME GmbH",
            "Hamburg",
            "https://example.com/jobs/1",
            "stepstone",
            "Lange Stellenbeschreibung fuer die Timeline.",
            88,
            "hybrid",
            85000,
            92000,
            "jahr",
            "festanstellung",
            profile_id,
            now,
            now,
        ),
    )
    conn.commit()

    app_id = db.add_application(
        {
            "job_hash": "timeline-job-1",
            "title": "Senior PLM Consultant",
            "company": "ACME GmbH",
            "url": "https://example.com/jobs/1",
            "status": "beworben",
            "applied_at": datetime.now().date().isoformat(),
            "notes": "Erstkontakt lief positiv.",
            "ansprechpartner": "Julia Beispiel",
            "kontakt_email": "julia@example.com",
            "portal_name": "StepStone",
        }
    )
    db.add_application_note(app_id, "Telefonat geführt")
    return app_id


def _seed_archive_workspace(db) -> None:
    """Create active and archived applications for the archive toggle flow."""
    db.save_profile(
        {
            "name": "Max Archiv",
            "email": "archiv@example.com",
            "phone": "+49 40 123456",
            "address": "Musterweg 1",
            "summary": "Bewerbungsmanagement testen",
        }
    )
    db.add_application(
        {
            "title": "Aktive Bewerbung",
            "company": "ACME Aktiv",
            "status": "beworben",
            "applied_at": datetime.now().date().isoformat(),
        }
    )
    db.add_application(
        {
            "title": "Archivierte Bewerbung",
            "company": "ACME Archiv",
            "status": "abgelehnt",
            "applied_at": (datetime.now().date() - timedelta(days=14)).isoformat(),
        }
    )


def _seed_uncertain_jobs_workspace(db) -> None:
    """Create jobs with missing descriptions to validate guidance and warning badges."""
    profile_id = db.save_profile(
        {
            "name": "Max Stellen",
            "email": "stellen@example.com",
            "phone": "+49 40 123456",
            "address": "Musterweg 1",
            "summary": "Berater fuer Produkt- und Prozessarbeit",
        }
    )
    db.set_profile_setting("active_sources", ["stepstone"])
    db.set_profile_setting("last_search_at", datetime.now().isoformat())
    db.save_jobs(
        [
            {
                "hash": "job-ohne-beschreibung",
                "title": "Senior Consultant",
                "company": "ACME GmbH",
                "location": "Hamburg",
                "url": "https://example.com/job-ohne-beschreibung",
                "source": "stepstone",
                "description": "Kurztext",
                "score": 74,
                "employment_type": "festanstellung",
                "profile_id": profile_id,
            },
            {
                "hash": "job-mit-beschreibung",
                "title": "PLM Consultant",
                "company": "Beta GmbH",
                "location": "Hamburg",
                "url": "https://example.com/job-mit-beschreibung",
                "source": "stepstone",
                "description": "Ausfuehrliche Stellenbeschreibung mit Aufgaben, Skills, Verantwortlichkeiten und Rahmenbedingungen fuer eine belastbare Bewertung.",
                "score": 82,
                "employment_type": "festanstellung",
                "profile_id": profile_id,
            },
        ]
    )


@pytest.mark.skip(reason="Tests reference old Vanilla-JS dashboard — React-Frontend seit v0.23.0")
def test_dashboard_onboarding_navigation_and_import_jump(live_dashboard, browser):
    """Welcome flow, tab navigation and document jump work in a real browser."""
    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"], wait_until="domcontentloaded")
        page.locator("#welcome-screen").wait_for(state="visible")
        page.locator("#workspace-strip.active").wait_for(state="visible")
        page.locator("#wizard-overlay.show").wait_for(state="visible")
        page.locator("#wizard-overlay button", has_text="Spaeter").click()
        page.locator("#wizard-overlay").wait_for(state="hidden")

        assert page.locator(".brand-title").inner_text() == "Persoenliches Bewerbungs-Portal"
        assert page.locator("#welcome-screen").inner_text().find("Willkommen beim Bewerbungs-Assistent") >= 0

        page.locator("#welcome-screen button", has_text="Ordner importieren").click()
        page.locator("#page-profil.active").wait_for(state="visible")

        page.locator(".tab[data-page='einstellungen']").click()
        page.wait_for_function("() => window.location.hash === '#einstellungen'")
        page.locator("#page-einstellungen.active").wait_for(state="visible")
        assert page.locator("#page-einstellungen h1").inner_text() == "Einstellungen"
    finally:
        context.close()


@pytest.mark.skip(reason="Tests reference old Vanilla-JS dashboard — React-Frontend seit v0.23.0")
def test_dashboard_guidance_and_badges_reflect_due_followups(live_dashboard, browser):
    """Workspace strip and navigation badges react to a ready workspace state."""
    _seed_ready_workspace(live_dashboard["db"])

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"], wait_until="domcontentloaded")
        page.locator("#dashboard-content").wait_for(state="visible")
        page.locator("#workspace-strip.active").wait_for(state="visible")

        workspace_text = page.locator("#workspace-strip").inner_text()
        assert "Es gibt ueberfaellige Nachfassaktionen." in workspace_text
        assert "Max Tester" in workspace_text
        assert "2/17" in workspace_text

        page.locator("#tab-badge-bewerbungen").wait_for(state="visible")
        assert page.locator("#tab-badge-bewerbungen").inner_text() == "1"
        assert page.locator("#tab-meta-dashboard").inner_text() == "Nachfassen"
    finally:
        context.close()


@pytest.mark.skip(reason="Tests reference old Vanilla-JS onboarding overlay — React-Frontend seit v0.23.0")
def test_new_profile_starts_with_profile_onboarding_overlay(live_dashboard, browser):
    """A newly prepared profile opens the four-step onboarding before regular work starts."""
    profile_id = live_dashboard["db"].create_profile("Neues Profil", "neu@example.com")
    live_dashboard["db"].set_user_preference(f"profile_onboarding_started_{profile_id}", True)
    live_dashboard["db"].set_user_preference(f"profile_onboarding_completed_{profile_id}", False)
    live_dashboard["db"].set_user_preference(f"profile_onboarding_dismissed_{profile_id}", False)

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"], wait_until="domcontentloaded")
        page.locator("#profile-onboarding-overlay").wait_for(state="visible")

        overlay_text = page.locator("#profile-onboarding-overlay").inner_text()
        assert "1. Unterlagen" in overlay_text
        assert "2. Kennlerngespraech" in overlay_text
        assert "3. Quellen" in overlay_text
        assert "4. Jobsuche" in overlay_text
        assert "0/4 Schritte" in overlay_text
    finally:
        context.close()


@pytest.mark.skip(reason="Tests reference old Vanilla-JS onboarding overlay — React-Frontend seit v0.23.0")
def test_onboarding_detects_completed_kennlerngespraech_and_unlocks_sources(live_dashboard, browser):
    """Wenn Claude das Kennlerngespraech abschliesst, schaltet die UI zu Quellen frei."""
    profile_id = live_dashboard["db"].create_profile("Onboarding Signal", "signal@example.com")
    live_dashboard["db"].set_user_preference(f"profile_onboarding_started_{profile_id}", True)
    live_dashboard["db"].set_user_preference(f"profile_onboarding_completed_{profile_id}", False)
    live_dashboard["db"].set_user_preference(f"profile_onboarding_dismissed_{profile_id}", False)
    live_dashboard["db"].set_user_preference(f"profile_onboarding_conversation_{profile_id}", "active")

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"], wait_until="domcontentloaded")
        page.locator("#profile-onboarding-overlay").wait_for(state="visible")

        page.locator("#profile-onboarding-overlay button", has_text="2. Kennlerngespraech").first.click()
        page.locator("#profile-onboarding-overlay").locator("text=/ersterfassung kopieren").wait_for(state="visible")
        page.locator("#profile-onboarding-overlay").get_by_text("Laeuft", exact=True).first.wait_for(
            state="visible"
        )

        live_dashboard["db"].set_user_preference(f"profile_onboarding_conversation_{profile_id}", "complete")

        page.locator("#profile-onboarding-overlay").locator("text=Abgeschlossen").wait_for(
            state="visible", timeout=7000
        )

        page.locator("#profile-onboarding-overlay button", has_text="3. Quellen").first.click()
        assert "Waehle die passenden Quellen" in page.locator("#profile-onboarding-overlay").inner_text()
    finally:
        context.close()


def test_dashboard_mobile_layout_has_no_horizontal_overflow(live_dashboard, browser):
    """Mobile viewport keeps React app inside the viewport width without horizontal scroll."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        is_mobile=True,
        has_touch=True,
    )
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"] + "#einstellungen", wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")

        layout = page.evaluate(
            """() => ({
                clientWidth: document.documentElement.clientWidth,
                scrollWidth: document.documentElement.scrollWidth,
                bodyScrollWidth: document.body.scrollWidth,
                rootPresent: !!document.getElementById('root'),
            })"""
        )

        assert layout["rootPresent"]
        assert layout["scrollWidth"] <= layout["clientWidth"] + 1
        assert layout["bodyScrollWidth"] <= layout["clientWidth"] + 1
    finally:
        context.close()


def test_react_frontend_smoke(live_dashboard, browser):
    """React frontend loads, hash navigation works, and API responds."""
    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        # 1) Page loads with div#root
        page.goto(live_dashboard["base_url"], wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        assert page.locator("div#root").is_visible()

        # 2) Hash navigation works for key routes
        for fragment in ("dashboard", "profil", "einstellungen"):
            page.goto(f"{live_dashboard['base_url']}#{fragment}", wait_until="domcontentloaded")
            actual_hash = page.evaluate("() => window.location.hash")
            assert actual_hash == f"#{fragment}", f"Expected #{fragment}, got {actual_hash}"

        # 3) API endpoint responds
        response = httpx.get(f"{live_dashboard['base_url']}/api/workspace-summary", timeout=5.0)
        assert response.status_code == 200
    finally:
        context.close()


def test_daily_impulse_visible_and_toggleable(live_dashboard, browser):
    """Daily impulse card is visible on dashboard and can be toggled off (#163)."""
    import httpx

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        # API returns a valid impulse
        response = httpx.get(f"{live_dashboard['base_url']}/api/daily-impulse", timeout=5.0)
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["impulse"] is not None
        assert "text" in data["impulse"]

        # Toggle off
        toggle = httpx.post(f"{live_dashboard['base_url']}/api/daily-impulse/toggle", timeout=5.0)
        assert toggle.status_code == 200
        assert toggle.json()["enabled"] is False

        # Verify disabled
        response2 = httpx.get(f"{live_dashboard['base_url']}/api/daily-impulse", timeout=5.0)
        assert response2.json()["enabled"] is False
        assert response2.json()["impulse"] is None

        # Toggle back on
        httpx.post(f"{live_dashboard['base_url']}/api/daily-impulse/toggle", timeout=5.0)
    finally:
        context.close()


def test_help_button_opens_support_modal(live_dashboard, browser):
    """The help button opens the support modal with issue/report actions."""
    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"], wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)

        page.get_by_title("Hilfe & Support").click()
        page.get_by_role("heading", name="Hilfe & Support").wait_for(state="visible")
        page.get_by_role("button", name="Bug melden").click()

        issue_link = page.get_by_role("link", name="Bug auf GitHub melden")
        issue_link.wait_for(state="visible")
        href = issue_link.get_attribute("href") or ""
        assert "github.com/MadGapun/PBP/issues/new" in href
        assert "labels=bug" in href
    finally:
        context.close()


def test_application_timeline_supports_note_and_status_changes(live_dashboard, browser):
    """Timeline modal supports adding notes and changing status directly."""
    _seed_timeline_workspace(live_dashboard["db"])

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"] + "#bewerbungen", wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)
        page.locator("h1").filter(has_text="Bewerbungen").wait_for(state="visible")

        page.get_by_role("heading", name="Senior PLM Consultant").click()
        page.get_by_text("Neue Notiz").wait_for(state="visible")

        note_input = page.get_by_placeholder("Notiz hinzufügen...")
        note_input.fill("Browser-Regression: Timeline-Notiz")
        page.get_by_role("button", name="Hinzufügen", exact=True).click()
        page.get_by_text("Notiz hinzugefügt.").wait_for(state="visible")
        page.get_by_text("Browser-Regression: Timeline-Notiz", exact=True).wait_for(state="visible")

        timeline_status = page.get_by_label("Status direkt ändern")
        timeline_status.click()
        page.get_by_role("button", name="Interview").click()
        page.get_by_text("Status aktualisiert.").wait_for(state="visible")
        page.wait_for_function(
            """() => Array.from(document.querySelectorAll('label'))
                .some((label) => label.textContent?.includes('Status direkt ändern') && label.textContent?.includes('Interview'))""",
            timeout=5000,
        )

        response = httpx.get(
            f"{live_dashboard['base_url']}/api/applications",
            timeout=5.0,
        )
        response.raise_for_status()
        applications = response.json()["applications"]
        assert applications[0]["status"] == "interview"

        timeline = httpx.get(
            f"{live_dashboard['base_url']}/api/application/{applications[0]['id']}/timeline",
            timeout=5.0,
        )
        timeline.raise_for_status()
        payload = timeline.json()
        notes = [event for event in payload["events"] if event["status"] == "notiz"]
        assert any("Browser-Regression: Timeline-Notiz" in (event.get("notes") or "") for event in notes)
        assert any(event["status"] == "interview" for event in payload["events"])
    finally:
        context.close()


def test_applications_archive_toggle_reveals_archived_entries(live_dashboard, browser):
    """Applications page hides archived entries by default and reveals them on demand."""
    _seed_archive_workspace(live_dashboard["db"])

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"] + "#bewerbungen", wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)
        page.locator("h1").filter(has_text="Bewerbungen").wait_for(state="visible")

        page.get_by_role("heading", name="Aktive Bewerbung").wait_for(state="visible")
        assert page.get_by_text("Archivierte Bewerbung", exact=True).count() == 0

        page.get_by_role("button", name="Archivierte anzeigen").click()
        page.get_by_text("Archivierte Bewerbung", exact=True).wait_for(state="visible")
    finally:
        context.close()


def test_jobs_page_marks_uncertain_scores_and_supports_gap_filter(live_dashboard, browser):
    """Jobs page highlights incomplete descriptions and offers a focused filter."""
    _seed_uncertain_jobs_workspace(live_dashboard["db"])

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"] + "#stellen", wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)
        page.get_by_role("heading", name="Stellen").wait_for(state="visible")

        page.get_by_text("Score unsicher").first.wait_for(state="visible")
        page.get_by_text("Senior Consultant", exact=True).wait_for(state="visible")

        page.get_by_role("button", name="Nur ohne Beschreibung").click()
        page.get_by_text("Senior Consultant", exact=True).wait_for(state="visible")
        assert page.get_by_text("PLM Consultant", exact=True).count() == 0
    finally:
        context.close()


def test_jobs_detail_modal_opens_and_allows_description_edit(live_dashboard, browser):
    """Job detail modal opens and can persist a description edit from the UI."""
    _seed_uncertain_jobs_workspace(live_dashboard["db"])

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"] + "#stellen", wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)
        page.get_by_role("heading", name="Stellen").wait_for(state="visible")

        page.locator('[title="Details anzeigen"]').filter(has_text="Senior Consultant").click()
        modal = page.locator(".glass-overlay").filter(has_text="Senior Consultant").first
        modal.get_by_role("heading", name="Senior Consultant").first.wait_for(state="visible")
        modal.get_by_role("button", name="Bearbeiten").click()
        page.get_by_role("heading", name="Stelle bearbeiten").wait_for(state="visible")
        page.locator("textarea").last.fill(
            "Ergaenzte Browser-Beschreibung mit Aufgaben, Skills und Rahmenbedingungen."
        )
        page.get_by_role("button", name="Speichern").click()
        page.get_by_text("Stelle aktualisiert").wait_for(state="visible")

        jobs = httpx.get(f"{live_dashboard['base_url']}/api/jobs", timeout=5.0)
        jobs.raise_for_status()
        payload = jobs.json()
        job_rows = payload["jobs"] if isinstance(payload, dict) and "jobs" in payload else payload
        updated = next(job for job in job_rows if job["hash"] == "job-ohne-beschreibung")
        assert "Ergaenzte Browser-Beschreibung" in updated["description"]
    finally:
        context.close()


def test_application_timeline_can_change_employment_type(live_dashboard, browser):
    """Timeline edit form persists employment type changes and shows the new value."""
    app_id = _seed_timeline_workspace(live_dashboard["db"])

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"] + "#bewerbungen", wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)
        page.locator("h1").filter(has_text="Bewerbungen").wait_for(state="visible")

        page.get_by_role("heading", name="Senior PLM Consultant").click()
        modal = page.locator(".glass-overlay").filter(has_text="Bewerbung bearbeiten").first
        modal.get_by_text("Bewerbung bearbeiten").wait_for(state="visible")
        modal.get_by_text("Bewerbung bearbeiten").click()

        employment = modal.get_by_label("Stellenart")
        employment.click()
        page.get_by_role("button", name="Freelance").click()
        page.get_by_text("Stellenart aktualisiert.").wait_for(state="visible")
        page.wait_for_function(
            """() => Array.from(document.querySelectorAll('label'))
                .some((label) => label.textContent?.includes('Stellenart') && label.textContent?.includes('Freelance'))""",
            timeout=5000,
        )

        timeline = httpx.get(
            f"{live_dashboard['base_url']}/api/application/{app_id}/timeline",
            timeout=5.0,
        )
        timeline.raise_for_status()
        data = timeline.json()
        assert data["application"]["employment_type"] == "freelance"
        assert data["application"]["job_employment_type"] == "freelance"
        assert data["job"]["employment_type"] == "festanstellung"
    finally:
        context.close()


def test_dashboard_shows_workspace_next_step_card(live_dashboard, browser):
    """Dashboard surfaces the workspace readiness as a clear next-step card."""
    _seed_ready_workspace(live_dashboard["db"])

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"], wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)

        page.get_by_text("Nächster sinnvoller Schritt", exact=True).wait_for(state="visible")
        page.get_by_text("Es gibt überfällige Nachfassaktionen.").wait_for(state="visible")
    finally:
        context.close()
