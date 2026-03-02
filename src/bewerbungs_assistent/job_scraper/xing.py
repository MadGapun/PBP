"""XING Job-Scraper via Playwright.

Uses persistent browser session (user logs in once, session is saved).
Searches XING Jobs with configurable keywords.

Based on the LinkedIn scraper pattern — same session management approach.
"""

import logging
import time
from pathlib import Path
from urllib.parse import quote

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.xing")

DEFAULT_SEARCHES = [
    "PLM Consultant",
    "Product Lifecycle Management",
    "PDM Manager",
    "PLM Systemarchitekt",
    "PLM Berater",
]


def get_session_dir() -> Path:
    """Get the persistent browser session directory for XING."""
    from ..database import get_data_dir
    session_dir = get_data_dir() / "xing_session"
    session_dir.mkdir(exist_ok=True)
    return session_dir


def search_xing(params: dict, progress_callback=None) -> list:
    """Search XING Jobs via Playwright with persistent session.

    The first time this runs, a visible browser opens so the user can log in.
    After that, the session is saved and reused (headless mode).

    Args:
        params: Search parameters with optional 'keywords' dict
                containing 'general' keyword list.
        progress_callback: Optional callback(message) for progress updates

    Returns:
        List of job dicts
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.error(
            "Playwright nicht installiert. "
            "Bitte: pip install playwright && python -m playwright install chromium"
        )
        return []

    # Dynamic keywords from DB, fallback to hardcoded
    kw_data = params.get("keywords", {})
    searches = kw_data.get("general", DEFAULT_SEARCHES)
    if not searches:
        searches = DEFAULT_SEARCHES

    stellen = []
    session_dir = get_session_dir()

    with sync_playwright() as pw:
        # Check if session already exists
        session_exists = (session_dir / "Default").exists()
        headless = session_exists

        if not session_exists:
            logger.info("XING Erst-Login: Browser wird sichtbar geoeffnet.")
            if progress_callback:
                progress_callback(
                    "XING: Browser wird geoeffnet fuer Erst-Login. "
                    "Bitte bei XING anmelden. Die Session wird gespeichert."
                )

        browser = pw.chromium.launch_persistent_context(
            user_data_dir=str(session_dir),
            headless=headless,
            slow_mo=300 if not headless else 0,
            viewport={"width": 1280, "height": 900},
            locale="de-DE",
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        page = browser.pages[0] if browser.pages else browser.new_page()

        try:
            # === Login Check ===
            logger.info("Pruefe XING-Login...")
            page.goto(
                "https://www.xing.com/jobs/search",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            time.sleep(2)

            # Detect login page
            if _is_login_page(page):
                logger.info("XING Login erforderlich...")
                if progress_callback:
                    progress_callback(
                        "XING: Bitte im geoeffneten Browser einloggen. "
                        "Warte max. 3 Minuten..."
                    )
                # Wait for user to log in
                logged_in = False
                for _ in range(180):
                    time.sleep(1)
                    url = page.url
                    if "jobs" in url and "login" not in url and "auth" not in url:
                        logged_in = True
                        logger.info("XING Login erfolgreich!")
                        break

                if not logged_in:
                    logger.warning("XING Login Timeout. Abbruch.")
                    browser.close()
                    return []

            logger.info("XING eingeloggt. Starte %d Suchen...", len(searches))

            # === Job Search ===
            for idx, suchbegriff in enumerate(searches):
                if progress_callback:
                    progress_callback(
                        f"XING: Suche '{suchbegriff}' ({idx + 1}/{len(searches)})"
                    )

                try:
                    url = (
                        f"https://www.xing.com/jobs/search"
                        f"?keywords={quote(suchbegriff)}"
                        f"&location=Deutschland"
                    )
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(3)

                    # Scroll to load results
                    for _ in range(3):
                        page.evaluate("window.scrollBy(0, 800)")
                        time.sleep(0.5)

                    # Extract job cards
                    cards = page.query_selector_all(
                        "article, [data-testid*='job'], "
                        "[class*='job-posting'], [class*='JobCard'], "
                        "[class*='serp-result']"
                    )

                    for card in cards:
                        try:
                            # Title
                            title_el = card.query_selector(
                                "h2 a, h3 a, [data-testid*='title'] a, "
                                "[class*='title'] a, a[class*='Title']"
                            )
                            if not title_el:
                                continue
                            title = title_el.inner_text().strip()
                            if not title:
                                continue

                            # Link
                            link = title_el.get_attribute("href") or ""
                            if link and not link.startswith("http"):
                                link = "https://www.xing.com" + link

                            # Company
                            company_el = card.query_selector(
                                "[data-testid*='company'], "
                                "[class*='company'], [class*='Company']"
                            )
                            company = company_el.inner_text().strip() if company_el else "Unbekannt"

                            # Location
                            location_el = card.query_selector(
                                "[data-testid*='location'], "
                                "[class*='location'], [class*='Location']"
                            )
                            location = location_el.inner_text().strip() if location_el else ""

                            # Description snippet
                            desc_el = card.query_selector(
                                "[class*='description'], [class*='snippet'], p"
                            )
                            desc = desc_el.inner_text().strip() if desc_el else ""

                            job = {
                                "hash": stelle_hash("xing.com", title),
                                "title": title,
                                "company": company,
                                "location": location,
                                "url": link,
                                "source": "xing",
                                "description": desc[:500],
                                "employment_type": "festanstellung",
                                "remote_level": detect_remote_level(
                                    f"{title} {location} {desc}"
                                ),
                            }
                            stellen.append(job)

                        except Exception as e:
                            logger.debug("XING card parse error: %s", e)

                    time.sleep(2)  # Rate limiting between searches
                except Exception as e:
                    logger.warning("XING search error for '%s': %s", suchbegriff, e)

        except Exception as e:
            logger.error("XING session error: %s", e)
        finally:
            browser.close()

    logger.info("XING: %d Stellen gefunden", len(stellen))
    return stellen


def _is_login_page(page) -> bool:
    """Detect if we're on a XING login/auth page."""
    url = page.url.lower()
    if any(k in url for k in ["login", "auth", "signin", "anmelden"]):
        return True

    # Check for login form elements
    login_els = page.query_selector_all(
        "input[type='email'], input[type='password'], "
        "input[name='login_form'], form[action*='login']"
    )
    return len(login_els) >= 2
