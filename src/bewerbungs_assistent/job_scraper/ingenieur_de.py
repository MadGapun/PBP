"""ingenieur.de (VDI) Job-Scraper — Engineering-Jobboerse des VDI.

Spezialisiert auf Ingenieur- und Technik-Stellen.
Kein Login erforderlich. HTML-Scraping via requests.
"""

import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level, fetch_description_from_detail

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

    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        for query in queries:
            try:
                # v1.7.19 (#927): Der Pfad ist /jobs, NICHT /suche —
                # /suche antwortet mit HTTP 404 (live geprueft 18.08.2026,
                # alle Varianten). Die Subdomain-Umstellung aus #653 war
                # halb erledigt: der Host stimmte, der Pfad nicht. Der
                # Guard-Test dazu prueft nur, ob "jobs.ingenieur.de" im
                # Code steht — Domain gruen, Feature tot.
                resp = client.get(
                    "https://jobs.ingenieur.de/jobs",
                    params={"q": query},
                )
                if resp.status_code != 200:
                    logger.debug("ingenieur.de HTTP %d for '%s'", resp.status_code, query)
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # Job cards: article elements or list items with job links
                cards = soup.select("article, .job-item, .search-result, [class*='job-card']")
                if not cards:
                    # v1.7.19 (#927): Detailseiten liegen unter /job/
                    # (Einzahl); '/jobs/' traf nur die Kategorie-Links.
                    cards = soup.select("a[href*='/job/']")

                for card in cards[:25]:
                    try:
                        job = _parse_card(card)
                        if job:
                            jobs.append(job)
                    except Exception as e:
                        logger.debug("ingenieur.de card error: %s", e)

                logger.debug("ingenieur.de: %d cards for '%s'", len(cards), query)
                time.sleep(1.5)
            except Exception as e:
                logger.error("ingenieur.de error for '%s': %s", query, e)

    # Fetch descriptions from detail pages
    if jobs:
        with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as detail_client:
            for job in jobs:
                if job.get("description") or not job.get("url"):
                    continue
                desc = fetch_description_from_detail(job["url"], detail_client)
                if desc:
                    job["description"] = desc
                    job["remote_level"] = detect_remote_level(
                        f"{job['title']} {job.get('location', '')} {desc}"
                    )
                time.sleep(1)
        fetched = sum(1 for j in jobs if j.get("description"))
        logger.info("ingenieur.de: %d/%d Beschreibungen von Detail-Seiten", fetched, len(jobs))

    logger.info("ingenieur.de: %d Stellen gefunden", len(jobs))
    return jobs


def _parse_card(card) -> dict | None:
    """Parse a job card or link element."""
    # Try to get title from link
    # v1.7.19 (#927): Detailseiten liegen unter /job/ (Einzahl) —
    # der alte Ausdruck traf nur Kategorie-Links unter /jobs/.
    link_el = card.find("a", href=re.compile(r"/job/")) if card.name != "a" else card
    if not link_el:
        return None

    title = link_el.get_text(strip=True)
    if not title or len(title) < 5:
        return None

    href = link_el.get("href", "")
    if not href:
        return None
    # #653 (B12, beta.77): URL-Migration zu jobs.ingenieur.de Subdomain.
    # Relative Links koennen entweder auf jobs.ingenieur.de zeigen
    # (neuer Pfad) oder auf den alten www.ingenieur.de — wir muessen
    # darauf vertrauen dass der relativen href schon korrekt rendert.
    if href.startswith("http"):
        url = href
    elif href.startswith("/job/") or href.startswith("/jobs"):
        url = f"https://jobs.ingenieur.de{href}"
    else:
        url = f"https://www.ingenieur.de{href}"

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
