"""ingenieur.de (VDI) Job-Scraper — Engineering-Jobboerse des VDI.

Spezialisiert auf Ingenieur- und Technik-Stellen.
Kein Login erforderlich. HTML-Scraping via requests.
"""

import logging
import re

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level
from .async_http_helper import fetch_all_parallel

logger = logging.getLogger("bewerbungs_assistent.scraper.ingenieur_de")

FALLBACK_QUERIES = [
    "Software Engineer", "Projektmanager", "Data Analyst",
    "DevOps Engineer", "Consultant",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9",
}


def search_ingenieur_de(params: dict) -> list:
    """Search ingenieur.de jobs via HTML scraping."""
    jobs = []
    kw_data = params.get("keywords", {})
    queries = kw_data.get("general", FALLBACK_QUERIES)[:8]

    requests_list = [
        {"url": "https://www.ingenieur.de/jobs/suche/", "params": {"q": q, "sort": "date"}}
        for q in queries
    ]
    all_responses = fetch_all_parallel(requests_list, headers=HEADERS, delay_between_batches=0.5)

    for _url, params, html in all_responses:
        if not html:
            continue
        query = (params or {}).get("q", "")
        try:
            soup = BeautifulSoup(html, "html.parser")

            cards = soup.select("article, .job-item, .search-result, [class*='job-card']")
            if not cards:
                cards = soup.select("a[href*='/jobs/']")

                for card in cards[:25]:
                    try:
                        job = _parse_card(card)
                        if job:
                            jobs.append(job)
                    except Exception as e:
                        logger.debug("ingenieur.de card error: %s", e)

            logger.debug("ingenieur.de: %d cards for '%s'", len(cards), query)
        except Exception as e:
            logger.error("ingenieur.de error for '%s': %s", query, e)

    logger.info("ingenieur.de: %d Stellen gefunden", len(jobs))
    return jobs


def _parse_card(card) -> dict | None:
    """Parse a job card or link element."""
    # Try to get title from link
    link_el = card.find("a", href=re.compile(r"/jobs/")) if card.name != "a" else card
    if not link_el:
        return None

    title = link_el.get_text(strip=True)
    if not title or len(title) < 5:
        return None

    href = link_el.get("href", "")
    if not href:
        return None
    url = href if href.startswith("http") else f"https://www.ingenieur.de{href}"

    # Skip non-job links (categories, etc.)
    if "/jobs/suche" in url or "/jobs/tag/" in url:
        return None

    # Try to find company and location from parent card
    parent = card if card.name in ("article", "div", "li") else card.parent
    if parent:
        company_el = parent.find(string=re.compile(r".*")) if not parent.find(
            class_=re.compile(r"company|firma|arbeitgeber", re.I)
        ) else parent.find(class_=re.compile(r"company|firma|arbeitgeber", re.I))
        location_el = parent.find(class_=re.compile(r"location|ort|standort", re.I))
    else:
        company_el = location_el = None

    company = company_el.get_text(strip=True) if company_el else "Unbekannt"
    location = location_el.get_text(strip=True) if location_el else ""

    return {
        "hash": stelle_hash("ingenieur.de", title),
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "source": "ingenieur_de",
        "description": "",
        "employment_type": "festanstellung",
        "remote_level": detect_remote_level(f"{title} {location}"),
    }
