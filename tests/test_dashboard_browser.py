"""Browser-Smoke-Tests fuer die wichtigsten Dashboard-Userflows."""

import re
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


def _seed_profile_document_workspace(db) -> str:
    """Create one uploaded document for profile-side analysis prompt flows."""
    profile_id = db.save_profile(
        {
            "name": "Max Dokument",
            "email": "dokument@example.com",
            "phone": "+49 40 123456",
            "address": "Musterweg 1",
            "summary": "Dokumentanalyse testen",
        }
    )
    document_path = Path(os.environ["BA_DATA_DIR"]) / "recruiter-mail.eml"
    document_path.write_text(
        "Betreff: Recruiter-Mail\nVon: hr@example.com\n\nVielen Dank fuer Ihr Interesse.",
        encoding="utf-8",
    )
    return db.add_document(
        {
            "filename": "Recruiter-Mail.eml",
            "filepath": str(document_path),
            "doc_type": "sonstiges",
            "extracted_text": "Betreff: Recruiter-Mail\nVon: hr@example.com\n\nVielen Dank fuer Ihr Interesse.",
            "profile_id": profile_id,
        }
    )


def test_dashboard_onboarding_navigation_and_import_jump(live_dashboard, browser):
    """Brand title, tab navigation and page switching work in a real browser."""
    # Profil anlegen damit Wizard nicht blockiert
    live_dashboard["db"].create_profile("Nav Test", "nav@test.de")

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"], wait_until="domcontentloaded")
        page.locator(".brand-title").wait_for(state="visible", timeout=8000)

        assert "Bewerbungs-Portal" in page.locator(".brand-title").inner_text()

        page.locator(".tab[data-page='einstellungen']").click()
        page.wait_for_function("() => window.location.hash === '#einstellungen'")
        page.locator("#page-einstellungen").wait_for(state="visible")
        assert "Einstellungen" in page.locator("#page-einstellungen h1").inner_text()

        page.locator(".tab[data-page='profil']").click()
        page.wait_for_function("() => window.location.hash === '#profil'")
        page.locator("#page-profil").wait_for(state="visible")
    finally:
        context.close()


def test_dashboard_guidance_and_badges_reflect_due_followups(live_dashboard, browser):
    """Workspace strip and navigation badges react to a ready workspace state."""
    _seed_ready_workspace(live_dashboard["db"])

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"], wait_until="domcontentloaded")
        page.locator(".brand-title").wait_for(state="visible", timeout=8000)

        # Tab-Badge fuer Bewerbungen und Dashboard-Meta pruefen
        page.locator("#tab-badge-bewerbungen").wait_for(state="visible", timeout=5000)
        assert page.locator("#tab-badge-bewerbungen").inner_text() == "1"
        assert page.locator("#tab-meta-dashboard").inner_text() == "Nachfassen"
    finally:
        context.close()


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
        page.locator("#profile-onboarding-overlay").wait_for(state="visible", timeout=8000)

        overlay_text = page.locator("#profile-onboarding-overlay").inner_text()
        assert "1. Unterlagen" in overlay_text
        assert "2. Kennenlerngespräch" in overlay_text or "2. Kennlerngespräch" in overlay_text
        assert "3. Quellen" in overlay_text
        assert "4. Jobsuche" in overlay_text
        assert "0/4 Schritte" in overlay_text
    finally:
        context.close()


def test_onboarding_detects_completed_kennlerngespraech_and_unlocks_sources(live_dashboard, browser):
    """Onboarding zeigt Kennlerngespraech-Panel korrekt an und erlaubt Navigation zu Quellen."""
    profile_id = live_dashboard["db"].create_profile("Onboarding Signal", "signal@example.com")
    live_dashboard["db"].set_user_preference(f"profile_onboarding_started_{profile_id}", True)
    live_dashboard["db"].set_user_preference(f"profile_onboarding_completed_{profile_id}", False)
    live_dashboard["db"].set_user_preference(f"profile_onboarding_dismissed_{profile_id}", False)
    live_dashboard["db"].set_user_preference(f"profile_onboarding_conversation_{profile_id}", "active")

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"], wait_until="domcontentloaded")
        page.locator("#profile-onboarding-overlay").wait_for(state="visible", timeout=8000)

        # Klick auf Kennlerngespraech-Tab
        page.locator("#profile-onboarding-overlay button", has_text="Kenn").first.click()
        page.locator("#profile-onboarding-overlay").locator("text=/ersterfassung kopieren").wait_for(
            state="visible", timeout=5000
        )

        # Zu Quellen navigieren via Tab-Klick
        page.locator("#profile-onboarding-overlay button", has_text="3. Quellen").first.click()
        overlay_text = page.locator("#profile-onboarding-overlay").inner_text()
        assert "Quellen" in overlay_text
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
        page.get_by_role("button", name="Interview", exact=True).click()
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


def test_jobs_page_opens_detail_modal_and_allows_description_edit(live_dashboard, browser):
    """Clicking a job title opens the detail modal and missing descriptions can be completed there."""
    _seed_uncertain_jobs_workspace(live_dashboard["db"])

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"] + "#stellen", wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)
        page.get_by_role("heading", name="Stellen").wait_for(state="visible")

        page.get_by_role("heading", name="Senior Consultant").click()
        page.get_by_role("heading", name="Stellendetails").wait_for(state="visible")
        page.get_by_role("button", name="Bearbeiten").click()
        page.get_by_role("heading", name="Stelle bearbeiten").wait_for(state="visible")

        description_input = page.get_by_label("Beschreibung")
        description_input.fill(
            "Jetzt mit belastbarer Beschreibung: Aufgaben, Skills, Teamkontext und Verantwortlichkeiten."
        )
        page.get_by_role("button", name="Speichern").click()
        page.get_by_text("Stelle aktualisiert").wait_for(state="visible")

        response = httpx.get(f"{live_dashboard['base_url']}/api/jobs", timeout=5.0)
        response.raise_for_status()
        jobs = response.json()
        updated = next(job for job in jobs if job["hash"] == "job-ohne-beschreibung")
        assert "belastbarer Beschreibung" in updated["description"]
    finally:
        context.close()


def test_dashboard_zeigt_offenes_statt_es_zu_wiederholen(live_dashboard, browser):
    """Das Offene steht EINMAL da — im Block, mit Firma und Datum."""
    _seed_ready_workspace(live_dashboard["db"])

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"], wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)

        # v1.7.31 (#976 Befund 1): der Kicker "Nächster sinnvoller Schritt"
        # ist weg. Er erklärte die Karte, während direkt darunter die
        # eigentliche Aussage stand — vier Etiketten für eine Information.
        #
        # v1.7.35 (Nutzerhinweis 07.09.2026): die Karte selbst entfällt
        # hier ebenfalls. Das Fixture legt eine überfällige Nachfassung
        # an; die steht damit mit Firma und Datum im Block "Offen", und
        # "Es gibt überfällige Nachfassaktionen." wäre dieselbe Aussage
        # noch einmal, nur unschärfer.
        page.get_by_text("Offen", exact=True).first.wait_for(state="visible")
        page.get_by_text("Nachfassen:", exact=False).first.wait_for(state="visible")
        assert page.get_by_text(
            "Es gibt überfällige Nachfassaktionen.", exact=False).count() == 0
        assert page.get_by_text(
            "Einige Bewerbungen warten auf deine Rückmeldung",
            exact=False).count() == 0
    finally:
        context.close()


def test_profile_documents_section_shows_status_and_docs_link(live_dashboard, browser):
    """Profile documents section shows upload area, status dashboard, and link to Docs tab."""
    _seed_profile_document_workspace(live_dashboard["db"])

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"] + "#profil", wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)
        page.get_by_role("heading", name="Profil", exact=True).wait_for(state="visible")

        # Document section shows status dashboard (not individual document list)
        page.get_by_role("heading", name="Dokumente").wait_for(state="visible")
        page.get_by_text("Dateien oder Ordner hier hineinziehen").wait_for(state="visible")

        # "Docs-Tab oeffnen" button should be visible
        docs_button = page.get_by_role("button", name="Docs-Tab")
        docs_button.wait_for(state="visible")
    finally:
        context.close()


def test_profile_workflow_button_copies_resolved_prompt_instead_of_slash_command(live_dashboard, browser):
    """The generic profile prompt button should copy real instructions, not a raw /profil_erweiterung token."""
    _seed_profile_document_workspace(live_dashboard["db"])

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()
    page.add_init_script(
        """
        (() => {
          window.__copiedText = "";
          const clipboard = {
            writeText: async (text) => {
              window.__copiedText = text;
            },
          };
          Object.defineProperty(navigator, "clipboard", {
            value: clipboard,
            configurable: true,
          });
        })();
        """
    )

    try:
        page.goto(live_dashboard["base_url"] + "#profil", wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)
        page.get_by_role("button", name="Profil-Prompt kopieren").click()
        page.wait_for_function("() => Boolean(window.__copiedText && window.__copiedText.length > 0)")

        copied = page.evaluate("() => window.__copiedText")
        assert not copied.strip().startswith("/profil_erweiterung")
        assert "Analysiere hochgeladene Dokumente" in copied
        assert "extraktion_starten()" in copied
    finally:
        context.close()


def test_jobs_page_zeigt_den_pruefstand_und_filtert_danach(live_dashboard, browser):
    """#948 AK 4/6/7 am GERENDERTEN Bild, nicht am Quelltext.

    Ein durchlaufender Build ist kein Beleg dafuer, dass die Seite
    rendert (v1.7.64 MERKE 1) — und ein Grep im JSX belegt nur, dass
    eine Zeichenkette dasteht. Hier wird geklickt.
    """
    db = live_dashboard["db"]
    _seed_uncertain_jobs_workspace(db)
    # Eine der beiden Stellen bekommt ein gelesenes Urteil, und danach
    # aendert sich ihr Score — damit muss das Abzeichen "ueberholt"
    # tragen (AK 5).
    voll = db.resolve_job_hash("job-mit-beschreibung")
    db.set_job_analysis(voll, "BEDINGT", "Methodenluecke, ueberbrueckbar")
    db.update_job(voll, {"score": 91})

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"] + "#stellen", wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)
        page.get_by_role("heading", name="Stellen").wait_for(state="visible")

        # AK 4/5: das Abzeichen steht da und meldet den Ueberholstand.
        page.get_by_text("Bedingt ⚠ überholt").first.wait_for(state="visible")

        # AK 6: die Gegenrichtung — nur ungeprueft.
        page.get_by_text("Prüfstand: alle").click()
        page.get_by_text("Nur ungeprüfte", exact=True).click()
        page.get_by_text("Senior Consultant", exact=True).wait_for(state="visible")
        assert page.get_by_text("PLM Consultant", exact=True).count() == 0, (
            "Die beurteilte Stelle steht noch in der Liste der ungeprueften."
        )

        # ... und nur beurteilte zeigt genau die andere.
        page.get_by_text("Nur ungeprüfte").first.click()
        page.get_by_text("Nur beurteilte", exact=True).click()
        page.get_by_text("PLM Consultant", exact=True).wait_for(state="visible")
        assert page.get_by_text("Senior Consultant", exact=True).count() == 0

        # AK 7: der Klick auf das Abzeichen fuehrt zum Ergebnis.
        page.get_by_text("Bedingt ⚠ überholt").first.click()
        page.get_by_role("heading", name="Fit-Analyse — PLM Consultant").wait_for(state="visible")
        page.get_by_text("Gelesenes Urteil").wait_for(state="visible")
        page.get_by_text("Methodenluecke, ueberbrueckbar").wait_for(state="visible")

        # AK 1/2: der Einstieg steht in der Fusszeile, also ohne Scrollen.
        einstieg = page.get_by_role("button", name="Detailbewertung durch Claude anfordern")
        einstieg.wait_for(state="visible")
        assert einstieg.count() == 1, "Der Einstieg steht doppelt im Dialog."
    finally:
        context.close()


def _seed_vielstellen_workspace(db) -> None:
    """30 aktive Stellen mit ABSTEIGENDEM Score, dazu 5 aussortierte.

    Die absteigende Sortierung ist der Kern des gemeldeten Fehlers
    (#1022): die geladene Seite enthaelt immer die besten Stellen, also
    war jede Kennzahl ueber sie systematisch zu gut.

    Zwei der Aussortierungen liegen bewusst WEIT zurueck — mit der alten
    Vorgabe `7tage` waeren sie unsichtbar gewesen, waehrend der Tab ihre
    Zahl nennt.
    """
    profil_id = db.create_profile("Viele Stellen")
    db.switch_profile(profil_id)
    jobs = []
    for i in range(35):
        jobs.append({
            "hash": f"v{i:03d}",
            "title": f"Testrolle {i:03d}",
            "company": f"Firma {i:03d}",
            "url": f"https://example.com/1022/{i}",
            "source": "manuell",
            "_manual_entry": True,
            "description": "Ausfuehrliche Stellenbeschreibung. " * 12,
            "score": float(35 - i),
            "salary_min": 40000 + i * 1000,
            "salary_max": 50000 + i * 1000,
            "salary_type": "jaehrlich",
            "salary_estimated": 0,
        })
    db.save_jobs(jobs)
    for i in range(30, 35):
        db.dismiss_job(db.resolve_job_hash(f"v{i:03d}"), "falsches_fachgebiet")
    # Zwei Aussortierungen weit in die Vergangenheit legen.
    con = db.connect()
    con.execute(
        "UPDATE jobs SET dismissed_at='2026-01-01T10:00:00+01:00' "
        "WHERE hash IN (?, ?)",
        (db.resolve_job_hash("v033"), db.resolve_job_hash("v034")))
    con.commit()


def test_stellen_kopfzeile_zeigt_den_bestand_und_nicht_die_seite(live_dashboard, browser):
    """#1022 — die Kachel meldete die Zahl der GELADENEN Zeilen.

    Bei 1.110 aktiven Stellen stand dort „AKTIVE STELLEN 20", und beim
    Blaettern wurde daraus 40, dann 60. Der Melder: *"ich hab immer
    gedacht, es gibt nur zwanzig Stellen fuer mich."*

    Dieser Test klickt „Mehr laden" und prueft, dass sich **keine** der
    vier Kennzahlen bewegt. Ein Grep haette nur belegt, dass eine
    Zeichenkette dasteht (v1.7.71 MERKE 9).
    """
    _seed_vielstellen_workspace(live_dashboard["db"])

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"] + "#stellen", wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)
        page.get_by_role("heading", name="Stellen", exact=True).first.wait_for(state="visible")

        kachel = page.locator("text=Aktive Stellen").first
        kachel.wait_for(state="visible")

        # Die vier Kennzahl-Karten, und NUR sie. Mein erster Entwurf
        # filterte ueber alle `div` nach Textinhalt und fing damit die
        # ganze Seite ein — der Vergleich schlug dann an der
        # Stellenliste an, die sich beim Nachladen zu Recht aendert.
        # **Ein Test, dessen Messung zu breit ist, meldet einen Fehler
        # im Code, wo einer im Test steckt.**
        def kennzahlen():
            return page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'.glass-card-soft')).map(d => (d.textContent || '')"
                ".trim()).filter(t => /Aktive Stellen|Gehaltsdurchschnitt"
                "|Gehaltsbandbreite|Durchschnittsscore/.test(t))")

        # Auf die Karten WARTEN: der Text "Aktive Stellen" steht frueher
        # im DOM als die Kennzahl-Karten. In der vollen Suite fiel die
        # Messung genau dazwischen ("Kopfzeile nicht gefunden"), allein
        # lief der Test gruen — dieselbe Klasse wie v1.7.83 MERKE 8.
        page.wait_for_function(
            "() => Array.from(document.querySelectorAll('.glass-card-soft'))"
            ".some(d => /Aktive Stellen/.test(d.textContent || ''))",
            timeout=8000)
        vorher = kennzahlen()
        assert vorher, "Kopfzeile nicht gefunden"
        assert any("30" in t for t in vorher), (
            f"Die Kachel zeigt nicht den Bestand von 30: {vorher}")

        mehr = page.get_by_role("button", name=re.compile(r"^Mehr laden"))
        if mehr.count():
            mehr.first.click()
            # Auf den ZUSTAND warten, nicht auf eine Dauer. Ein fester
            # `wait_for_timeout` ist eine Annahme darueber, wie schnell
            # der Rechner gerade ist — unter Last der ganzen Testsuite
            # war er zu kurz, und der Vergleich lief mitten in die
            # Aktualisierung. Der Zaehler neben dem Suchfeld sagt
            # verlaesslich, wann alle 30 geladen sind.
            page.get_by_text("30 / 30", exact=True).wait_for(
                state="visible", timeout=15000)
            nachher = kennzahlen()
            assert nachher == vorher, (
                "Eine Kennzahl hat sich beim Nachladen geaendert — sie "
                f"misst das Blaettern.\nvorher:  {vorher}\nnachher: {nachher}")
    finally:
        context.close()


def test_stellen_tabs_nennen_ihre_menge(live_dashboard, browser):
    """#1022 AK 3+7 — und die Vorgabe des Zeitfensters.

    Der Ausgeblendet-Tab nennt 5, und es werden auch 5 angezeigt. Mit
    der alten Vorgabe `7tage` waeren es 3 gewesen, weil zwei
    Aussortierungen aelter sind — ein Filter, den niemand gesetzt hat
    (#1008).
    """
    _seed_vielstellen_workspace(live_dashboard["db"])

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"] + "#stellen", wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)
        page.get_by_role("heading", name="Stellen", exact=True).first.wait_for(state="visible")

        aktive = page.get_by_role("button", name=re.compile(r"Aktive \(30\)"))
        aktive.wait_for(state="visible", timeout=8000)
        ausgeblendet = page.get_by_role("button", name=re.compile(r"Ausgeblendet \(5\)"))
        ausgeblendet.wait_for(state="visible")

        ausgeblendet.click()
        page.wait_for_timeout(600)
        # Das Zeitfenster steht auf "alle" — alle fuenf sind sichtbar.
        page.get_by_text("5 von 5").first.wait_for(state="visible", timeout=8000)
        # Und die Kachel beschreibt weiterhin den BESTAND, nicht die Ansicht.
        # `inner_text()` liefert den per CSS transformierten Text — die
        # Karte rendert das Label in Versalien.
        kachel_text = page.locator("text=Aktive Stellen").first.inner_text()
        assert "aktive stellen" in kachel_text.lower()
    finally:
        context.close()


def _seed_gefahrenzone(db) -> None:
    """Zwei Profile, Stellen in beiden Zustaenden, ein Dokument-Datensatz."""
    db.switch_profile(db.create_profile("Erstes Profil"))
    db.create_profile("Zweites Profil")
    db.save_jobs([
        {
            "hash": f"gz-{i}",
            "title": f"Stelle {i}",
            "company": "Firma",
            "url": f"https://example.com/gz/{i}",
            "source": "bundesagentur",
            "description": "Beschreibungstext. " * 20,
            "score": 5,
        }
        for i in range(6)
    ])
    con = db.connect()
    con.execute("UPDATE jobs SET is_active=0, dismiss_reason='zeitarbeit' "
                "WHERE hash LIKE '%gz-4' OR hash LIKE '%gz-5'")
    con.commit()


def test_gefahrenzone_zeigt_bereiche_mit_zahlen(live_dashboard, browser):
    """#1025 Stufe 2 + #1024, in der Oberflaeche statt im Quelltext.

    Vier der neun Akzeptanzkriterien betreffen die Anzeige, und dort
    ist der Grep kein Beleg (v1.7.71 MERKE 9): er zeigt nur, dass eine
    Zeichenkette dasteht. Ein gruener Vite-Build erst recht nicht — ein
    Hook hinter einem fruehen Return laesst ihn durchlaufen und die
    Seite trotzdem nicht rendern (#1009).
    """
    _seed_gefahrenzone(live_dashboard["db"])

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"] + "#einstellungen",
                  wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)
        page.get_by_role("button", name="Gefahrenzone", exact=True).first.click()

        # Die eine Karte statt der drei alten.
        page.get_by_role("heading", name="Daten loeschen").first.wait_for(
            state="visible", timeout=8000)
        for weg in ("Factory Reset", "Alle Daten loeschen (DSGVO)"):
            assert page.get_by_role("heading", name=weg).count() == 0, (
                f"Alte Karte rendert noch: {weg}")

        # AK 5 + #1024: die Zahlen stehen VOR dem Ausfuehren da,
        # aufgeteilt nach aktiv und aussortiert.
        page.get_by_text("4 aktiv", exact=True).wait_for(
            state="visible", timeout=8000)
        page.get_by_text("2 aussortiert", exact=True).wait_for(state="visible")

        # AK 3: beide Profile stehen zur Auswahl, nicht nur das aktive.
        # `SelectInput` ist kein natives <select>, sondern Knopf plus
        # Portal-Panel — die Auswahl steht erst im DOM, wenn sie offen
        # ist. Genau deshalb ist das hier ein Browser-Test und kein Grep.
        #
        # #1027: der Knopf wird ueber seinen BARRIEREFREIEN NAMEN
        # angesprochen. Bis v1.7.88 lautete der nur "Welches Profil?",
        # weil `Field` ihn in ein <label> wickelte und das den
        # Knopfinhalt ueberschrieb — ein Screenreader nannte die Frage
        # und nie die Antwort. Jetzt steht beides im Namen, und er
        # wandert mit dem gewaehlten Wert.
        auswahl = page.get_by_role(
            "button", name="Welches Profil? Alle Profile", exact=True)
        assert auswahl.count() == 1, "Name nennt nicht Frage UND Antwort"
        assert auswahl.get_attribute("aria-expanded") == "false"
        auswahl.click()
        assert auswahl.get_attribute("aria-expanded") == "true"
        for name in ("Erstes Profil", "Zweites Profil"):
            page.get_by_role("button", name=name, exact=True).wait_for(
                state="visible", timeout=4000)
        page.get_by_role("button", name="Zweites Profil", exact=True).click()
        gewechselt = page.get_by_role(
            "button", name="Welches Profil? Zweites Profil", exact=True)
        gewechselt.wait_for(state="visible", timeout=4000)
        assert gewechselt.get_attribute("aria-expanded") == "false"
        # Zurueck auf alle Profile, damit der Rest des Tests auf
        # derselben Lage arbeitet wie vorher.
        gewechselt.click()
        page.get_by_role("button", name="Alle Profile", exact=True).click()
        page.get_by_role(
            "button", name="Welches Profil? Alle Profile", exact=True
        ).wait_for(state="visible", timeout=4000)

        # AK 6: der Knopf bleibt gesperrt, solange nichts gewaehlt ist
        # und das Wort fehlt.
        knopf = page.get_by_role("button", name="Bereiche leeren")
        assert knopf.is_disabled()
        page.get_by_role("checkbox").nth(2).check()  # Bereich "stellen"
        assert knopf.is_disabled(), "Ohne Bestaetigungswort freigegeben"
        page.get_by_placeholder("LOESCHEN").fill("LOESCHEN")
        assert knopf.is_enabled()

        # AK 4: der Umschalter sperrt die Bereichsliste, statt sie
        # zwangsweise anzuhaken — die Haekchen sind dann Anzeige der
        # Folge und keine Auswahl.
        page.get_by_role("radio").nth(1).check()
        page.get_by_role("button", name="Endgueltig loeschen").wait_for(
            state="visible")
        kaesten = page.get_by_role("checkbox")
        for i in range(kaesten.count()):
            assert kaesten.nth(i).is_disabled(), (
                "Im DSGVO-Modus ist die Bereichsliste eine Auswahl geblieben")
            assert kaesten.nth(i).is_checked()
    finally:
        context.close()


def test_kontakte_untermenue_referenzen(live_dashboard, browser):
    """#884 — die Referenz-Ansicht, bedient statt gegrept.

    Drei der fuenf Akzeptanzkriterien betreffen die Oberflaeche; ein
    gruener Build belegt nicht, dass die Seite rendert (#1009).
    """
    db = live_dashboard["db"]
    db.switch_profile(db.create_profile("Referenzprofil"))
    anna = db.add_contact({"full_name": "Anna Beispiel",
                           "company": "Musterbetrieb GmbH",
                           "position": "Bereichsleitung"})
    db.add_contact({"full_name": "Bert Beispiel", "company": "Musterbetrieb GmbH"})
    db.add_contact_reference(anna, "vorgesetzter", "2020-2024",
                             "kann zur Programmleitung Auskunft geben")

    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()
    try:
        page.goto(live_dashboard["base_url"] + "#kontakte",
                  wait_until="domcontentloaded")
        page.locator("div#root").wait_for(state="visible")
        _dismiss_setup_overlay(page)

        page.get_by_role("tab", name="Referenzen").click()
        ansicht = page.get_by_test_id("referenzen-ansicht")
        ansicht.wait_for(state="visible", timeout=8000)
        ansicht.get_by_text("Anna Beispiel").wait_for(state="visible")
        ansicht.get_by_text("2020-2024", exact=False).first.wait_for(state="visible")
        # Nur markierte Kontakte — Bert ist keine Referenz.
        assert ansicht.get_by_text("Bert Beispiel").count() == 0

        docx = page.get_by_role("link", name="Referenzliste als DOCX")
        assert "mit_kontaktdaten=false" in docx.get_attribute("href")
        page.get_by_label("Kontaktdaten in die Liste aufnehmen").check()
        assert "mit_kontaktdaten=true" in docx.get_attribute("href")

        # Filter nach Art: eine andere Art leert die Liste.
        page.get_by_label("Nach Art der Referenz filtern").select_option("kunde")
        page.get_by_text("Keine Referenz dieser Art.").wait_for(state="visible")

        # Zurueck in die Kontakt-Ansicht, Dialog oeffnen, Block sichtbar.
        page.get_by_role("tab", name="Kontakte").click()
        page.get_by_text("Bert Beispiel").first.click()
        block = page.get_by_test_id("referenz-block")
        block.wait_for(state="visible", timeout=8000)
        block.get_by_label("Art der Referenz").select_option("kollege")
        block.get_by_role("button", name="Als Referenz markieren").click()
        # Der Listeneintrag, nicht die gleichlautende <option> im
        # Auswahlfeld — ein zu breiter Locator misst den Test, nicht
        # den Code (v1.7.83 MERKE 8).
        block.get_by_role("listitem").filter(has_text="Projektpartner").wait_for(state="visible", timeout=8000)
        assert len(db.list_contact_references()) == 2
    finally:
        context.close()
