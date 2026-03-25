"""freelance.de Scraper — Projektboerse für Freelancer und IT-Projekte.

Sucht Projekte auf freelance.de über Skill-basierte URLs.
Kein Login erforderlich für oeffentliche Projektlisten.
Firmennamen und Stundensaetze sind hinter der Paywall (EXPERT-Mitgliedschaft).

HTML-Struktur (Stand 2026-02):
  div.list-item-content
    div.list-item-main
      h3 > a[href="/projekte/projekt-XXXXXX-Titel"]  -> Titel + Link
      ul.icon-list > li > i.fa-map-marker-alt  -> Standort
      ul.icon-list > li > i.fa-laptop-house    -> Remote-Hinweis
      ul.icon-list > li > i.fa-calendar-star   -> Startdatum
      ul.icon-list > li > i.fa-history         -> Veroeffentlichungsdatum
"""

import logging
import re
import time
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level, fetch_description_from_detail

logger = logging.getLogger("bewerbungs_assistent.scraper.freelance_de")

# Default search URLs (skill-based)
SEARCH_URLS = [
    "https://www.freelance.de/Software-Engineering-Projekte",
    "https://www.freelance.de/Projektmanagement-Projekte",
    "https://www.freelance.de/Data-Analytics-Projekte",
    "https://www.freelance.de/DevOps-Projekte",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
}

MAX_PAGES = 3  # Max pages per keyword (20 results per page = 60 max)


def search_freelance_de(params: dict) -> list:
    """Search freelance.de projects via skill-based URLs.

    Args:
        params: Search parameters with optional 'keywords' dict containing
                'freelance_de_urls' for custom search URLs.

    Returns:
        List of job dicts with standard fields.
    """
    jobs = []
    seen_urls = set()

    # Dynamic keywords from DB, fallback to hardcoded
    kw_data = params.get("keywords", {})
    urls = kw_data.get("freelance_de_urls", SEARCH_URLS)

    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        for base_url in urls:
            try:
                page_jobs = _scrape_listing_pages(client, base_url, seen_urls)
                jobs.extend(page_jobs)
                time.sleep(1)  # Rate limiting between keywords
            except Exception as e:
                logger.error("freelance.de error for %s: %s", base_url, e)

    # Fetch descriptions from project detail pages
    if jobs:
        with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as detail_client:
            for job in jobs:
                if len(job.get("description", "") or "") > 200 or not job.get("url"):
                    continue
                desc = fetch_description_from_detail(job["url"], detail_client)
                if desc and len(desc) > len(job.get("description", "") or ""):
                    job["description"] = desc
                    job["remote_level"] = detect_remote_level(
                        f"{job['title']} {job.get('location', '')} {desc}"
                    )
                time.sleep(1)
        fetched = sum(1 for j in jobs if len(j.get("description", "") or "") > 200)
        logger.info("freelance.de: %d/%d Beschreibungen von Detail-Seiten", fetched, len(jobs))

    logger.info("freelance.de: %d Projekte gefunden", len(jobs))
    return jobs


def _scrape_listing_pages(client: httpx.Client, base_url: str, seen_urls: set) -> list:
    """Scrape listing pages with pagination."""
    jobs = []

    for page in range(MAX_PAGES):
        offset = page * 20
        url = base_url if page == 0 else f"{base_url}?_offset={offset}"

        try:
            resp = client.get(url)
            if resp.status_code != 200:
                logger.debug("freelance.de HTTP %d for %s", resp.status_code, url)
                break

            page_jobs = _parse_listing_page(resp.text, seen_urls)

            if not page_jobs:
                break  # No more results

            jobs.extend(page_jobs)

            # Check if there's a next page
            if not _has_next_page(resp.text, offset):
                break

            time.sleep(1)  # Rate limiting between pages
        except Exception as e:
            logger.error("freelance.de page error: %s", e)
            break

    return jobs


def _parse_listing_page(html: str, seen_urls: set) -> list:
    """Parse a single listing page and extract project cards.

    freelance.de uses div.list-item-content as the card container,
    with div.list-item-main containing the project details.
    """
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # Primary selector: div.list-item-content (confirmed structure)
    cards = soup.find_all("div", class_="list-item-content")

    for card in cards:
        try:
            job = _extract_project_from_card(card, seen_urls)
            if job:
                jobs.append(job)
        except Exception as e:
            logger.debug("freelance.de card parse error: %s", e)

    return jobs


def _extract_project_from_card(card, seen_urls: set) -> dict | None:
    """Extract project info from a single list-item-content card.

    Structure:
      h3 > a[href="/projekte/projekt-XXXXXX-..."]  -> title + URL
      ul.icon-list:
        li > i.fa-map-marker-alt  -> location (text after icon)
        li > i.fa-laptop-house    -> remote indicator
        li > i.fa-calendar-star   -> start date
    """
    # Find project link in h3
    h3 = card.find("h3")
    if not h3:
        return None

    link_el = h3.find("a", href=re.compile(r"/projekte/projekt-\d+"))
    if not link_el:
        return None

    href = link_el.get("href", "")
    if not href:
        return None

    # Build full URL
    project_url = f"https://www.freelance.de{href}" if href.startswith("/") else href

    # Deduplicate
    if project_url in seen_urls:
        return None
    seen_urls.add(project_url)

    # Title
    title = link_el.get_text(strip=True)
    if not title:
        return None

    # Parse icon-list for metadata
    location = ""
    remote_hint = ""
    start_date = ""
    published = ""

    icon_list = card.find("ul", class_="icon-list")
    if icon_list:
        for li in icon_list.find_all("li"):
            icon = li.find("i")
            if not icon:
                continue
            icon_classes = " ".join(icon.get("class", []))
            li_text = li.get_text(strip=True)

            if "map-marker" in icon_classes or "location" in icon_classes:
                location = li_text
            elif "laptop-house" in icon_classes or "home" in icon_classes:
                remote_hint = li_text
            elif "calendar" in icon_classes:
                start_date = li_text
            elif "history" in icon_classes or "clock" in icon_classes:
                published = li_text

    # Company (hidden behind EXPERT paywall)
    company = "freelance.de"

    # Build description from available metadata
    desc_parts = []
    if start_date:
        desc_parts.append(f"Start: {start_date}")
    if location:
        desc_parts.append(f"Ort: {location}")
    if remote_hint:
        desc_parts.append(f"Arbeitsmodell: {remote_hint}")
    if published:
        desc_parts.append(f"Veroeffentlicht: {published}")

    # Try to get any tags/skills
    tags = card.find("ul", class_="tags")
    if tags:
        tag_texts = [t.get_text(strip=True) for t in tags.find_all("li") if t.get_text(strip=True)]
        if tag_texts:
            desc_parts.append(f"Skills: {', '.join(tag_texts)}")

    description = " | ".join(desc_parts) if desc_parts else title

    # Remote detection: use remote_hint + location + title
    remote_text = f"{title} {location} {remote_hint}"

    return {
        "hash": stelle_hash("freelance.de", title),
        "title": title,
        "company": company,
        "location": location,
        "url": project_url,
        "source": "freelance_de",
        "description": description[:2000],
        "employment_type": "freelance",
        "remote_level": detect_remote_level(remote_text),
    }


def _has_next_page(html: str, current_offset: int) -> bool:
    """Check if there's a next page of results."""
    soup = BeautifulSoup(html, "html.parser")
    next_offset = current_offset + 20

    # Look for pagination links with next offset
    next_link = soup.find("a", href=re.compile(rf"_offset={next_offset}"))
    if next_link:
        return True

    # Look for "next" or "weiter" pagination buttons
    nav = soup.find(["nav", "div", "ul"], class_=re.compile(r"paginat"))
    if nav:
        next_btn = nav.find("a", string=re.compile(r"(Weiter|Next|>>|›)", re.IGNORECASE))
        if next_btn:
            return True

    return False
