"""XING Job-Scraper via Playwright (Browser-Automation).

Uses persistent browser session (user logs in once, session is saved).
Searches XING Jobs with dynamic keyword combinations from profile/criteria.

Features (#48/#50/#73):
- launch_persistent_context for reliable session management
- Dynamic keyword combinations from keywords_muss (smart pairing)
- Configurable DOM selectors (browser_config.py)
- Multi-page pagination (configurable max_pages)
- XING Job-ID based deduplication
- Regional filtering from criteria
- Bot-detection handling
"""

import logging
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from . import stelle_hash, detect_remote_level
from .browser_config import (
    get_selectors,
    build_js_extractor,
    build_keyword_combinations,
)

logger = logging.getLogger("bewerbungs_assistent.scraper.xing")

DEFAULT_SEARCHES = [
    "PLM Consultant",
    "Product Lifecycle Management",
    "PDM Manager",
    "PLM Systemarchitekt",
    "PLM Berater",
]

DEFAULT_MAX_PAGES = 3
DEFAULT_PAGE_DELAY = 3


def get_session_dir() -> Path:
    """Get the persistent browser session directory for XING."""
    from ..database import get_data_dir
    session_dir = get_data_dir() / "xing_session"
    session_dir.mkdir(exist_ok=True)
    return session_dir


def _build_search_queries(params: dict) -> list[str]:
    """Build XING search queries from params.

    Uses smart keyword combinations from keywords_muss if available.
    """
    kw_data = params.get("keywords", {})
    criteria = params.get("criteria", {})

    # Try smart combinations from keywords_muss
    muss = criteria.get("keywords_muss", [])
    if not muss and isinstance(kw_data, dict):
        muss = kw_data.get("keywords_muss", [])

    if muss:
        combos = build_keyword_combinations(muss)
        if combos:
            logger.info("XING Keyword-Kombinationen: %s", combos)
            return combos

    # Fallback: general keywords
    general = kw_data.get("general", []) if isinstance(kw_data, dict) else []
    if general:
        return list(general[:6])

    return DEFAULT_SEARCHES


def _build_location_param(params: dict) -> str:
    """Build XING location parameter from search criteria."""
    kw_data = params.get("keywords", {})
    criteria = params.get("criteria", {})

    regionen = criteria.get("regionen", [])
    if not regionen and isinstance(kw_data, dict):
        regionen = kw_data.get("regionen", [])

    if regionen:
        for r in regionen:
            if r.lower() != "remote":
                return r
    return "Deutschland"


def _build_search_url(query: str, location: str, page: int = 0) -> str:
    """Build a XING Jobs search URL.

    Args:
        query: Search keywords
        location: Location string
        page: Page number (1-based for XING)
    """
    url = (
        f"https://www.xing.com/jobs/search"
        f"?keywords={quote(query)}"
        f"&location={quote(location)}"
        f"&sort=date"
    )
    if page > 0:
        url += f"&page={page + 1}"  # XING uses 1-based pagination
    return url


def search_xing(params: dict, progress_callback=None) -> list:
    """Search XING Jobs via Playwright with persistent session.

    The first time this runs, a visible browser opens so the user can log in.
    After that, the session is saved and reused (headless mode).

    Args:
        params: Search parameters with optional 'keywords' dict and 'criteria'
        progress_callback: Optional callback(message) for progress updates

    Returns:
        List of job dicts
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        msg = (
            "Playwright nicht installiert. "
            "Bitte: pip install playwright && python -m playwright install chromium"
        )
        logger.error(msg)
        if progress_callback:
            progress_callback(f"XING FEHLER: {msg}")
        return []

    # Load criteria from DB if not in params
    if "criteria" not in params:
        try:
            from ..database import Database
            db = Database()
            params["criteria"] = db.get_search_criteria()
        except Exception:
            params["criteria"] = {}

    searches = _build_search_queries(params)
    location = _build_location_param(params)
    max_pages = params.get("max_pages", DEFAULT_MAX_PAGES)

    stellen = []
    seen_job_ids = set()
    session_dir = get_session_dir()

    with sync_playwright() as pw:
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

            if _is_login_page(page):
                logger.info("XING Login erforderlich...")
                if progress_callback:
                    progress_callback(
                        "XING: Bitte im geoeffneten Browser einloggen. "
                        "Warte max. 3 Minuten..."
                    )
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

            # Bot-detection check
            if _is_bot_blocked(page):
                msg = (
                    "XING Bot-Detection aktiv. Optionen: "
                    "1) Warte einige Minuten und versuche erneut. "
                    "2) Nutze 'Claude in Chrome' Browser-Extension fuer direkte Suche."
                )
                logger.warning(msg)
                if progress_callback:
                    progress_callback(f"XING WARNUNG: {msg}")
                browser.close()
                return []

            logger.info(
                "XING eingeloggt. Starte %d Suchen (Region: %s, Max Pages: %d)...",
                len(searches), location, max_pages,
            )

            # === Job Search with Pagination ===
            js_extractor = build_js_extractor("xing")

            for idx, suchbegriff in enumerate(searches):
                if progress_callback:
                    progress_callback(
                        f"XING: Suche '{suchbegriff}' ({idx+1}/{len(searches)})"
                    )

                for page_num in range(max_pages):
                    try:
                        url = _build_search_url(suchbegriff, location, page_num)
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        time.sleep(DEFAULT_PAGE_DELAY)

                        # Scroll to load results
                        for _ in range(3):
                            page.evaluate("window.scrollBy(0, 800)")
                            time.sleep(0.5)

                        # Extract job cards via JavaScript
                        raw_jobs = page.evaluate(js_extractor)
                        logger.info(
                            "XING '%s' Seite %d: %d Karten",
                            suchbegriff, page_num + 1, len(raw_jobs),
                        )

                        if not raw_jobs:
                            logger.info(
                                "Keine Ergebnisse auf Seite %d, beende Paginierung.",
                                page_num + 1,
                            )
                            break

                        page_stellen = 0
                        for raw in raw_jobs:
                            job = _process_raw_job(raw, seen_job_ids)
                            if job:
                                stellen.append(job)
                                page_stellen += 1

                        if progress_callback and page_num > 0:
                            progress_callback(
                                f"XING: '{suchbegriff}' Seite {page_num+1}/{max_pages} "
                                f"({page_stellen} neue Stellen)"
                            )

                        # Stop if fewer than expected results
                        if len(raw_jobs) < 10:
                            break

                    except PWTimeout:
                        logger.warning(
                            "XING Timeout fuer '%s' Seite %d",
                            suchbegriff, page_num + 1,
                        )
                        break
                    except Exception as e:
                        logger.error(
                            "XING Fehler bei '%s' Seite %d: %s",
                            suchbegriff, page_num + 1, e,
                        )
                        break

                    # Rate limiting between pages
                    if page_num < max_pages - 1:
                        time.sleep(2)

                # Rate limiting between searches
                time.sleep(2)

        except Exception as e:
            logger.error("XING Session-Fehler: %s", e, exc_info=True)
            if progress_callback:
                progress_callback(f"XING FEHLER: {e}")
        finally:
            browser.close()

    # Final dedup by hash
    seen = set()
    unique = []
    for s in stellen:
        if s["hash"] not in seen:
            seen.add(s["hash"])
            unique.append(s)

    logger.info("XING: %d einzigartige Stellen gefunden", len(unique))
    return unique


def ensure_xing_session(progress_callback=None) -> bool:
    """Ensure a valid XING session exists (login if needed).

    Opens a visible browser for first-time login.  Returns True when the
    user is logged in and the session is persisted, False otherwise.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright nicht installiert.")
        return False

    session_dir = get_session_dir()

    with sync_playwright() as pw:
        session_exists = (session_dir / "Default").exists()
        headless = session_exists

        if not session_exists and progress_callback:
            progress_callback(
                "XING: Browser wird geoeffnet fuer Erst-Login. "
                "Bitte bei XING anmelden."
            )

        browser = pw.chromium.launch_persistent_context(
            user_data_dir=str(session_dir),
            headless=headless,
            slow_mo=300 if not headless else 0,
            viewport={"width": 1280, "height": 900},
            locale="de-DE",
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        page = browser.pages[0] if browser.pages else browser.new_page()

        try:
            page.goto(
                "https://www.xing.com/jobs/search",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            time.sleep(2)

            if _is_login_page(page):
                if progress_callback:
                    progress_callback("XING: Bitte im Browser einloggen...")
                for _ in range(180):
                    time.sleep(1)
                    url = page.url
                    if "jobs" in url and "login" not in url and "auth" not in url:
                        logger.info("XING Login erfolgreich!")
                        break
                else:
                    logger.warning("XING Login Timeout.")
                    return False
            else:
                logger.info("XING Session bereits aktiv.")

            return True
        except Exception as e:
            logger.error("XING Session-Fehler: %s", e)
            return False
        finally:
            browser.close()


def _process_raw_job(raw: dict, seen_job_ids: set) -> dict | None:
    """Process a raw JS-extracted XING job into a job dict."""
    title = _clean(raw.get("title", ""))
    if not title or len(title) < 5:
        return None

    # Deduplicate by XING Job-ID
    job_id = raw.get("jobId", "")
    if job_id:
        if job_id in seen_job_ids:
            return None
        seen_job_ids.add(job_id)

    link = raw.get("link", "")
    company = _clean(raw.get("company", "")) or "Unbekannt"
    location = _clean(raw.get("location", ""))
    desc = raw.get("desc", "")

    volltext = f"{title} {company} {location} {desc}"
    employment = (
        "freelance"
        if ("interim" in title.lower() or "freelance" in title.lower())
        else "festanstellung"
    )

    # Use XING Job-ID in hash for better deduplication
    hash_input = f"xing.com/jobs/{job_id}" if job_id else title

    return {
        "hash": stelle_hash("xing.com", hash_input if job_id else title),
        "title": title,
        "company": company,
        "location": location,
        "url": link,
        "source": "xing",
        "description": desc,
        "employment_type": employment,
        "remote_level": detect_remote_level(volltext),
        "found_at": datetime.now().isoformat(),
        "xing_job_id": job_id,
    }


def _is_login_page(page) -> bool:
    """Detect if we're on a XING login/auth page."""
    sel = get_selectors("xing")
    url = page.url.lower()

    for pattern in sel.get("login_url_patterns", ["login", "auth"]):
        if pattern in url:
            return True

    # Check for login form elements
    indicators = sel.get("login_indicators", "input[type='email']")
    login_els = page.query_selector_all(indicators)
    return len(login_els) >= 1


def _is_bot_blocked(page) -> bool:
    """Check if XING has triggered bot detection."""
    url = page.url.lower()
    if "captcha" in url or "challenge" in url or "blocked" in url:
        return True
    if page.locator("iframe[src*='captcha'], #captcha").count() > 0:
        return True
    return False


def _clean(text) -> str:
    """Clean whitespace from text."""
    return re.sub(r"\s+", " ", str(text or "")).strip()
