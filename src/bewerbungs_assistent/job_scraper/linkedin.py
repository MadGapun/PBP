"""LinkedIn Job-Scraper via Playwright.

Uses persistent browser session (user logs in once, session is saved).
Searches LinkedIn Jobs with dynamic keywords from profile/criteria.

Features (#48/#50):
- launch_persistent_context for reliable session management
- Dynamic keywords from profile skills and search criteria
- Regional filtering (location parameter from criteria)
- Date filter (last 7 days)
"""

import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.linkedin")

DEFAULT_SEARCHES = [
    "PLM Consultant",
    "PDM Solution Architect",
    "PLM Projektleiter",
    "Product Lifecycle Management",
]


def get_session_dir() -> Path:
    """Get the persistent browser session directory."""
    from ..database import get_data_dir
    session_dir = get_data_dir() / "linkedin_session"
    session_dir.mkdir(exist_ok=True)
    return session_dir


def _build_search_queries(params: dict) -> list[str]:
    """Build LinkedIn search queries from params.

    Uses profile keywords if available, falls back to DEFAULT_SEARCHES.
    Combines MUSS-Keywords into meaningful search pairs for better results (#50).
    """
    kw_data = params.get("keywords", {})

    # If explicit keywords provided, use them
    general = kw_data.get("general", [])
    if general:
        # Build targeted search queries: combine pairs for specificity
        queries = []
        for kw in general[:6]:
            queries.append(kw)
        return queries if queries else DEFAULT_SEARCHES

    return DEFAULT_SEARCHES


def _build_location_param(params: dict) -> str:
    """Build LinkedIn location parameter from search criteria (#50).

    Uses region from criteria for targeted results instead of broad 'Deutschland'.
    """
    kw_data = params.get("keywords", {})
    criteria = params.get("criteria", {})

    # Check for regions in criteria
    regionen = criteria.get("regionen", [])
    if not regionen and kw_data:
        # Check if regions were passed through keywords
        regionen = kw_data.get("regionen", [])

    if regionen:
        # Use first region for location filter, prefer city names over "Remote"
        for r in regionen:
            if r.lower() != "remote":
                return r
    return "Deutschland"


def search_linkedin(params: dict, progress_callback=None) -> list:
    """Search LinkedIn Jobs via Playwright with persistent session.

    The first time this runs, a visible browser opens so the user can log in.
    After that, the session is saved and reused (headless mode).

    Args:
        params: Search parameters with optional 'keywords' dict
        progress_callback: Optional callback(message) for progress updates

    Returns:
        List of job dicts
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.error("Playwright nicht installiert. Bitte: pip install playwright && python -m playwright install chromium")
        return []

    searches = _build_search_queries(params)
    location = _build_location_param(params)
    max_age_days = 21
    grenze = datetime.now() - timedelta(days=max_age_days)
    stellen = []

    session_dir = get_session_dir()

    with sync_playwright() as pw:
        # Check if session already exists (login saved)
        session_exists = (session_dir / "Default" / "Cookies").exists() or \
                        (session_dir / "Default").exists()
        headless = session_exists

        if not session_exists:
            logger.info("LinkedIn Erst-Login: Browser wird sichtbar geoeffnet.")
            if progress_callback:
                progress_callback(
                    "LinkedIn: Browser wird geoeffnet fuer Erst-Login. "
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
                timeout=30000
            )
            time.sleep(2)

            # Detect login page
            if _is_login_page(page):
                logger.info("LinkedIn Login erforderlich...")
                if progress_callback:
                    progress_callback(
                        "LinkedIn: Bitte im geoeffneten Browser einloggen. "
                        "Warte max. 3 Minuten..."
                    )
                # Wait for user to log in (max 3 minutes)
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

            logger.info("LinkedIn eingeloggt. Starte %d Suchen (Region: %s)...",
                        len(searches), location)

            # === Job Search ===
            for idx, suchbegriff in enumerate(searches):
                if progress_callback:
                    progress_callback(f"LinkedIn: Suche '{suchbegriff}' ({idx+1}/{len(searches)})")

                try:
                    url = (
                        f"https://www.linkedin.com/jobs/search/"
                        f"?keywords={quote(suchbegriff)}"
                        f"&location={quote(location)}"
                        f"&f_TPR=r604800"   # Last 7 days
                        f"&sortBy=DD"       # Newest first
                    )
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(3)

                    # Scroll to load more results
                    for _ in range(3):
                        page.keyboard.press("End")
                        time.sleep(1.5)

                    # Collect job cards
                    karten = page.locator(
                        ".job-card-container, .jobs-search-results__list-item, "
                        "[data-job-id], .scaffold-layout__list-item"
                    ).all()
                    logger.info("LinkedIn '%s': %d Karten", suchbegriff, len(karten))

                    for karte in karten[:25]:
                        try:
                            job = _parse_job_card(karte, grenze)
                            if job:
                                stellen.append(job)
                        except Exception as e:
                            logger.debug("Karte-Fehler: %s", e)
                            continue

                except PWTimeout:
                    logger.warning("LinkedIn Timeout fuer '%s'", suchbegriff)
                except Exception as e:
                    logger.error("LinkedIn Fehler bei '%s': %s", suchbegriff, e)

                time.sleep(2)  # Rate limiting between searches

        finally:
            browser.close()

    # Deduplicate
    seen = set()
    unique = []
    for s in stellen:
        if s["hash"] not in seen:
            seen.add(s["hash"])
            unique.append(s)

    logger.info("LinkedIn: %d einzigartige Stellen gefunden", len(unique))
    return unique


def _is_login_page(page) -> bool:
    """Check if we're on a LinkedIn login/auth page."""
    url = page.url.lower()
    if "login" in url or "authwall" in url or "checkpoint" in url:
        return True
    if page.locator("input#username").count() > 0:
        return True
    return False


def _parse_job_card(karte, grenze: datetime) -> dict | None:
    """Parse a single LinkedIn job card into a job dict."""
    # Title — try multiple selectors for robustness
    titel = ""
    for sel in [
        ".job-card-list__title",
        ".job-card-container__link",
        "a[class*='job-card']",
        "strong",
    ]:
        el = karte.locator(sel).first
        if el.count():
            titel = _clean(el.text_content())
            if titel:
                break
    if not titel:
        return None

    # Company
    firma = "k.A."
    for sel in [
        ".job-card-container__company-name",
        ".artdeco-entity-lockup__subtitle",
        "span[class*='company']",
    ]:
        el = karte.locator(sel).first
        if el.count():
            firma = _clean(el.text_content())
            if firma:
                break

    # Location
    ort = ""
    for sel in [
        ".job-card-container__metadata-item",
        ".artdeco-entity-lockup__caption",
        "span[class*='location']",
    ]:
        el = karte.locator(sel).first
        if el.count():
            ort = _clean(el.text_content())
            if ort:
                break

    # Link — prefer /jobs/view/ URLs, strip tracking parameters
    link_el = karte.locator("a[href*='/jobs/view/']").first
    href = link_el.get_attribute("href") if link_el.count() else ""
    if not href:
        any_link = karte.locator("a[href]").first
        href = any_link.get_attribute("href") if any_link.count() else ""
    link = href.split("?")[0] if href else ""
    if link and not link.startswith("http"):
        link = "https://www.linkedin.com" + link
    # Skip company page links
    if "/company/" in link and "/jobs/view/" not in link:
        return None

    # Date
    datum_el = karte.locator("time, .job-card-container__listdate, span[class*='time']").first
    datum_raw = ""
    if datum_el.count():
        datum_raw = datum_el.get_attribute("datetime") or _clean(datum_el.text_content())
    datum = _parse_linkedin_date(datum_raw)
    if datum < grenze:
        return None

    volltext = f"{titel} {firma} {ort}"
    employment = "freelance" if ("interim" in titel.lower() or "freelance" in titel.lower()) else "festanstellung"

    return {
        "hash": stelle_hash("linkedin.com", titel),
        "title": titel,
        "company": firma,
        "location": ort,
        "url": link,
        "source": "linkedin",
        "description": "",
        "employment_type": employment,
        "remote_level": detect_remote_level(volltext),
        "found_at": datetime.now().isoformat(),
    }


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
            return datetime.strptime(text[:len(fmt.replace("%", "X"))], fmt)
        except (ValueError, TypeError):
            continue

    return datetime.now()
