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
    db.set_setting("active_sources", ["bundesagentur", "stepstone"])
    db.set_setting("last_search_at", datetime.now().isoformat())
    app_id = db.add_application(
        {
            "title": "Senior Consultant",
            "company": "ACME",
            "status": "beworben",
            "applied_at": datetime.now().date().isoformat(),
        }
    )
    db.add_follow_up(app_id, (datetime.now().date() - timedelta(days=1)).isoformat())


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
        assert page.locator("#page-einstellungen h2").inner_text() == "Einstellungen"
    finally:
        context.close()


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


def test_dashboard_mobile_layout_has_no_horizontal_overflow(live_dashboard, browser):
    """Mobile viewport keeps navigation and settings page inside the viewport width."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        is_mobile=True,
        has_touch=True,
    )
    page = context.new_page()

    try:
        page.goto(live_dashboard["base_url"] + "#einstellungen", wait_until="domcontentloaded")
        page.locator("#page-einstellungen.active").wait_for(state="visible")

        layout = page.evaluate(
            """() => ({
                clientWidth: document.documentElement.clientWidth,
                scrollWidth: document.documentElement.scrollWidth,
                bodyScrollWidth: document.body.scrollWidth,
                tabCount: document.querySelectorAll('.tab').length,
            })"""
        )

        assert layout["tabCount"] == 5
        assert layout["scrollWidth"] <= layout["clientWidth"] + 1
        assert layout["bodyScrollWidth"] <= layout["clientWidth"] + 1
        assert page.locator(".app-topbar").is_visible()
    finally:
        context.close()
