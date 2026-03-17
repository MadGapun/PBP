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

                    # Extract job cards via JavaScript (more reliable than query_selector_all)
                    raw_jobs = page.evaluate("""() => {
                        const results = [];
                        // XING job cards: look for links to /jobs/ detail pages
                        const allLinks = document.querySelectorAll('a[href*="/jobs/"]');
                        const seen = new Set();
                        for (const link of allLinks) {
                            const href = link.getAttribute('href') || '';
                            // Only job detail links (not search/filter links)
                            if (!href.match(/\\/jobs\\/[a-z0-9-]+\\./i) &&
                                !href.match(/\\/jobs\\/\\d+/)) continue;
                            const title = link.textContent?.trim() || '';
                            if (!title || title.length < 5 || seen.has(title)) continue;
                            seen.add(title);

                            // Walk up to find the card container
                            let card = link.closest('article, [data-testid], li, div[class*="card"]');
                            if (!card) card = link.parentElement?.parentElement || link.parentElement;

                            const companyEl = card?.querySelector(
                                '[data-testid*="company"], [class*="company" i]'
                            );
                            const locationEl = card?.querySelector(
                                '[data-testid*="location"], [class*="location" i]'
                            );
                            const descEl = card?.querySelector(
                                '[class*="description" i], [class*="snippet" i]'
                            );

                            let fullLink = href;
                            if (fullLink && !fullLink.startsWith('http')) {
                                fullLink = 'https://www.xing.com' + fullLink;
                            }

                            results.push({
                                title,
                                link: fullLink,
                                company: companyEl?.textContent?.trim() || 'Unbekannt',
                                location: locationEl?.textContent?.trim() || '',
                                desc: (descEl?.textContent?.trim() || '').substring(0, 500),
                            });
                        }
                        return results;
                    }""")

                    for raw in raw_jobs:
                        job = {
                            "hash": stelle_hash("xing.com", raw["title"]),
                            "title": raw["title"],
                            "company": raw["company"],
                            "location": raw["location"],
                            "url": raw["link"],
                            "source": "xing",
                            "description": raw["desc"],
                            "employment_type": "festanstellung",
                            "remote_level": detect_remote_level(
                                f"{raw['title']} {raw['location']} {raw['desc']}"
                            ),
                        }
                        stellen.append(job)

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
