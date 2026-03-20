"""LinkedIn Job-Scraper via Playwright (Browser-Automation).

Uses persistent browser session (user logs in once, session is saved).
Searches LinkedIn Jobs with dynamic keyword combinations from profile/criteria.

Features (#48/#50/#73):
- launch_persistent_context for reliable session management
- Dynamic keyword combinations from keywords_muss (smart pairing)
- Configurable DOM selectors (browser_config.py)
- Multi-page pagination (configurable max_pages)
- Job description extraction from detail panel
- LinkedIn Job-ID based deduplication
- Remote filter via f_WT parameter
- Regional filtering from criteria
- Bot-detection handling with clear error messages
"""

import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from . import stelle_hash, detect_remote_level
from .browser_config import (
    get_selectors,
    build_js_extractor,
    build_js_description,
    build_keyword_combinations,
)

logger = logging.getLogger("bewerbungs_assistent.scraper.linkedin")

DEFAULT_SEARCHES = [
    "Software Engineer", "Projektmanager",
    "Data Analyst", "Consultant",
]

# Default config
DEFAULT_MAX_PAGES = 3
DEFAULT_PAGE_DELAY = 3  # seconds between page loads
DEFAULT_MAX_AGE_DAYS = 21


def get_session_dir() -> Path:
    """Get the persistent browser session directory."""
    from ..database import get_data_dir
    session_dir = get_data_dir() / "linkedin_session"
    session_dir.mkdir(exist_ok=True)
    return session_dir


def _build_search_queries(params: dict) -> list[str]:
    """Build LinkedIn search queries from params.

    Uses smart keyword combinations from keywords_muss if available,
    falls back to general keywords or DEFAULT_SEARCHES.
    """
    kw_data = params.get("keywords", {})
    criteria = params.get("criteria", {})

    # Try to build smart combinations from keywords_muss
    muss = criteria.get("keywords_muss", [])
    if not muss and isinstance(kw_data, dict):
        muss = kw_data.get("keywords_muss", [])

    if muss:
        combos = build_keyword_combinations(muss)
        if combos:
            logger.info("Keyword-Kombinationen: %s", combos)
            return combos

    # Fallback: use general keywords
    general = kw_data.get("general", []) if isinstance(kw_data, dict) else []
    if general:
        return list(general[:6])

    return DEFAULT_SEARCHES


def _build_location_param(params: dict) -> str:
    """Build LinkedIn location parameter from search criteria."""
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


def _should_filter_remote(params: dict) -> bool:
    """Check if remote filter should be applied (f_WT=2).

    Returns True if homeoffice preference >= 7 in custom_kriterien.
    """
    criteria = params.get("criteria", {})
    custom = criteria.get("custom_kriterien", {})
    if isinstance(custom, str):
        try:
            import json
            custom = json.loads(custom)
        except Exception:
            custom = {}
    return custom.get("homeoffice", 0) >= 7


def _build_search_url(query: str, location: str, remote: bool, page: int = 0) -> str:
    """Build a LinkedIn Jobs search URL.

    Args:
        query: Search keywords (can include Boolean operators)
        location: Location string
        remote: Whether to filter for remote jobs (f_WT=2)
        page: Page number (0-based, each page = 25 results)
    """
    url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={quote(query)}"
        f"&location={quote(location)}"
        f"&sortBy=DD"  # Newest first
    )
    if remote:
        url += "&f_WT=2"  # Remote filter
    if page > 0:
        url += f"&start={page * 25}"
    return url


def search_linkedin(params: dict, progress_callback=None) -> list:
    """Search LinkedIn Jobs via Playwright with persistent session.

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
        msg = ("Playwright nicht installiert. "
               "Bitte: pip install playwright && python -m playwright install chromium")
        logger.error(msg)
        if progress_callback:
            progress_callback(f"LinkedIn FEHLER: {msg}")
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
    remote_filter = params.get("nur_remote", False) or _should_filter_remote(params)
    max_pages = params.get("max_pages", DEFAULT_MAX_PAGES)
    max_age_days = params.get("max_age_days", DEFAULT_MAX_AGE_DAYS)
    grenze = datetime.now() - timedelta(days=max_age_days)

    stellen = []
    seen_job_ids = set()  # LinkedIn Job-ID deduplication
    session_dir = get_session_dir()

    with sync_playwright() as pw:
        session_exists = (session_dir / "Default").exists()
        headless = session_exists

        if not session_exists:
            logger.info("LinkedIn Erst-Login: Browser wird sichtbar geöffnet.")
            if progress_callback:
                progress_callback(
                    "LinkedIn: Browser wird geöffnet für Erst-Login. "
                    "Bitte bei LinkedIn anmelden. Die Session wird gespeichert."
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
            logger.info("Pruefe LinkedIn-Login...")
            page.goto(
                "https://www.linkedin.com/jobs/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            time.sleep(2)

            if _is_login_page(page):
                logger.info("LinkedIn Login erforderlich...")
                if progress_callback:
                    progress_callback(
                        "LinkedIn: Bitte im geöffneten Browser einloggen. "
                        "Warte max. 3 Minuten..."
                    )
                logged_in = False
                for _ in range(180):
                    time.sleep(1)
                    url = page.url
                    if ("feed" in url or "jobs" in url) and "login" not in url:
                        logged_in = True
                        logger.info("LinkedIn Login erfolgreich!")
                        break

                if not logged_in:
                    logger.warning("LinkedIn Login Timeout. Abbruch.")
                    browser.close()
                    return []

            # Bot-detection check
            if _is_bot_blocked(page):
                msg = (
                    "LinkedIn Bot-Detection aktiv. Optionen: "
                    "1) Warte einige Minuten und versuche erneut. "
                    "2) Nutze 'Claude in Chrome' Browser-Extension für direkte Suche."
                )
                logger.warning(msg)
                if progress_callback:
                    progress_callback(f"LinkedIn WARNUNG: {msg}")
                browser.close()
                return []

            logger.info(
                "LinkedIn eingeloggt. Starte %d Suchen (Region: %s, Remote: %s, Max Pages: %d)...",
                len(searches), location, remote_filter, max_pages,
            )

            # === Job Search with Pagination ===
            js_extractor = build_js_extractor("linkedin")

            for idx, suchbegriff in enumerate(searches):
                if progress_callback:
                    progress_callback(
                        f"LinkedIn: Suche '{suchbegriff}' ({idx+1}/{len(searches)})"
                    )

                for page_num in range(max_pages):
                    try:
                        url = _build_search_url(
                            suchbegriff, location, remote_filter, page_num
                        )
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        time.sleep(DEFAULT_PAGE_DELAY)

                        # Scroll to load lazy-loaded results
                        for _ in range(3):
                            page.keyboard.press("End")
                            time.sleep(1)

                        # Extract job cards via JavaScript
                        raw_jobs = page.evaluate(js_extractor)
                        logger.info(
                            "LinkedIn '%s' Seite %d: %d Karten",
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
                            job = _process_raw_job(raw, grenze, seen_job_ids)
                            if job:
                                stellen.append(job)
                                page_stellen += 1

                        # Update progress with page info
                        if progress_callback and page_num > 0:
                            progress_callback(
                                f"LinkedIn: '{suchbegriff}' Seite {page_num+1}/{max_pages} "
                                f"({page_stellen} neue Stellen)"
                            )

                        # Stop pagination if fewer than expected results
                        if len(raw_jobs) < 15:
                            break

                    except PWTimeout:
                        logger.warning(
                            "LinkedIn Timeout für '%s' Seite %d",
                            suchbegriff, page_num + 1,
                        )
                        break
                    except Exception as e:
                        logger.error(
                            "LinkedIn Fehler bei '%s' Seite %d: %s",
                            suchbegriff, page_num + 1, e,
                        )
                        break

                    # Rate limiting between pages
                    if page_num < max_pages - 1:
                        time.sleep(2)

                # Rate limiting between searches
                time.sleep(2)

            # === Optional: Extract descriptions for top results ===
            _extract_descriptions(page, stellen[:20], progress_callback)

        except Exception as e:
            logger.error("LinkedIn Session-Fehler: %s", e, exc_info=True)
            if progress_callback:
                progress_callback(f"LinkedIn FEHLER: {e}")
        finally:
            browser.close()

    # Final dedup by hash
    seen = set()
    unique = []
    for s in stellen:
        if s["hash"] not in seen:
            seen.add(s["hash"])
            unique.append(s)

    logger.info("LinkedIn: %d einzigartige Stellen gefunden", len(unique))
    return unique


def _process_raw_job(
    raw: dict, grenze: datetime, seen_job_ids: set
) -> dict | None:
    """Process a raw JS-extracted job into a job dict.

    Handles LinkedIn Job-ID deduplication.
    """
    title = _clean(raw.get("title", ""))
    if not title:
        return None

    # Deduplicate by LinkedIn Job-ID
    job_id = raw.get("jobId", "")
    if job_id:
        if job_id in seen_job_ids:
            return None
        seen_job_ids.add(job_id)

    link = raw.get("link", "")
    company = _clean(raw.get("company", "")) or "k.A."
    location = _clean(raw.get("location", ""))

    # Date filtering
    datum = _parse_linkedin_date(raw.get("dateRaw", ""))
    if datum < grenze:
        return None

    volltext = f"{title} {company} {location}"
    employment = (
        "freelance"
        if ("interim" in title.lower() or "freelance" in title.lower())
        else "festanstellung"
    )

    # Use LinkedIn Job-ID in hash for better deduplication
    hash_key = f"linkedin.com/jobs/view/{job_id}" if job_id else f"linkedin.com|{title}"

    return {
        "hash": stelle_hash("linkedin.com", hash_key if job_id else title),
        "title": title,
        "company": company,
        "location": location,
        "url": link,
        "source": "linkedin",
        "description": "",
        "employment_type": employment,
        "remote_level": detect_remote_level(volltext),
        "found_at": datetime.now().isoformat(),
        "linkedin_job_id": job_id,
    }


def _extract_descriptions(page, stellen: list, progress_callback=None) -> None:
    """Try to extract descriptions by clicking on job cards.

    Only extracts for jobs that don't already have descriptions.
    Fails silently on errors (descriptions are optional).
    """
    js_desc = build_js_description("linkedin")
    extracted = 0

    for job in stellen:
        if job.get("description") or not job.get("url"):
            continue
        try:
            page.goto(job["url"], wait_until="domcontentloaded", timeout=15000)
            time.sleep(1.5)
            desc = page.evaluate(js_desc)
            if desc and len(desc) > 50:
                job["description"] = desc.strip()
                extracted += 1
        except Exception as e:
            logger.debug("Beschreibung nicht extrahiert für %s: %s", job["url"], e)
        # Rate limit
        time.sleep(1)

        # Limit description extraction to avoid rate-limiting
        if extracted >= 10:
            break

    if extracted:
        logger.info("LinkedIn: %d Stellenbeschreibungen extrahiert", extracted)


def ensure_linkedin_session(progress_callback=None) -> bool:
    """Ensure a valid LinkedIn session exists (login if needed).

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
                "LinkedIn: Browser wird geöffnet für Erst-Login. "
                "Bitte bei LinkedIn anmelden."
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
                "https://www.linkedin.com/jobs/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            time.sleep(2)

            if _is_login_page(page):
                if progress_callback:
                    progress_callback("LinkedIn: Bitte im Browser einloggen...")
                for _ in range(180):
                    time.sleep(1)
                    url = page.url
                    if ("feed" in url or "jobs" in url) and "login" not in url:
                        logger.info("LinkedIn Login erfolgreich!")
                        browser.close()
                        return True
                logger.warning("LinkedIn Login Timeout.")
                browser.close()
                return False

            logger.info("LinkedIn Session ist gueltig.")
            browser.close()
            return True
        except Exception as exc:
            logger.error("LinkedIn Session-Check fehlgeschlagen: %s", exc)
            try:
                browser.close()
            except Exception:
                pass
            return False


def _is_login_page(page) -> bool:
    """Check if we're on a LinkedIn login/auth page."""
    sel = get_selectors("linkedin")
    url = page.url.lower()

    for pattern in sel.get("login_url_patterns", ["login", "authwall"]):
        if pattern in url:
            return True

    indicators = sel.get("login_indicators", "input#username")
    if page.locator(indicators).count() > 0:
        return True

    return False


def _is_bot_blocked(page) -> bool:
    """Check if LinkedIn has triggered bot detection."""
    url = page.url.lower()
    if "challenge" in url or "captcha" in url:
        return True
    # Check for CAPTCHA elements
    if page.locator("iframe[src*='captcha'], #captcha, .challenge-dialog").count() > 0:
        return True
    return False


def _clean(text) -> str:
    """Clean whitespace from text."""
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _parse_linkedin_date(text: str) -> datetime:
    """Parse LinkedIn relative date: '2 Stunden', '3 Tage', ISO, etc."""
    if not text:
        return datetime.now()
    t = text.lower().strip()

    if "minute" in t or "sekunde" in t or "second" in t:
        return datetime.now()
    if "stunde" in t or "hour" in t:
        m = re.search(r"(\d+)", t)
        return datetime.now() - timedelta(hours=int(m.group(1)) if m else 1)
    if "tag" in t or "day" in t:
        m = re.search(r"(\d+)", t)
        return datetime.now() - timedelta(days=int(m.group(1)) if m else 1)
    if "woche" in t or "week" in t:
        m = re.search(r"(\d+)", t)
        return datetime.now() - timedelta(weeks=int(m.group(1)) if m else 1)
    if "monat" in t or "month" in t:
        m = re.search(r"(\d+)", t)
        return datetime.now() - timedelta(days=30 * (int(m.group(1)) if m else 1))

    # Try ISO date formats
    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
        try:
            return datetime.strptime(text[: len(fmt.replace("%", "X"))], fmt)
        except (ValueError, TypeError):
            continue

    return datetime.now()
