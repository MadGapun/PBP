"""Monster.de job scraper via HTML parsing.

Searches monster.de for job listings using httpx + BeautifulSoup.
No login required.
"""

import logging
import time
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.monster")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

FALLBACK_QUERIES = [
    "PLM Consultant",
    "Product Lifecycle Management",
    "PDM Manager",
]


def search_monster(params: dict) -> list:
    """Search Monster Germany for job listings.

    Args:
        params: Search parameters with optional 'keywords' dict
                containing 'monster_queries' list.
    """
    jobs = []

    # Dynamic queries from DB, fallback to hardcoded
    kw_data = params.get("keywords", {})
    queries = kw_data.get("monster_queries", FALLBACK_QUERIES)

    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for query in queries:
            try:
                url = f"https://www.monster.de/jobs/suche/?q={quote(query)}&where=Deutschland"
                resp = client.get(url)
                if resp.status_code != 200:
                    logger.warning("Monster %d for '%s'", resp.status_code, query)
                    continue

                soup = BeautifulSoup(resp.text, "lxml")

                # Monster card selectors
                cards = (
                    soup.select("div[data-testid='svx-job-card']") or
                    soup.select("section.card-content") or
                    soup.select("div.job-search-card") or
                    soup.select("article.job-cardstyle")
                )

                for card in cards:
                    # Title
                    title_el = (
                        card.select_one("[data-testid='svx-job-title'] a") or
                        card.select_one("h3 a") or
                        card.select_one("h2 a") or
                        card.select_one("a.job-cardstyle__title")
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title:
                        continue

                    # Link
                    link = title_el.get("href", "")
                    if link and not link.startswith("http"):
                        link = "https://www.monster.de" + link

                    # Company
                    company_el = (
                        card.select_one("[data-testid='svx-job-company']") or
                        card.select_one(".company") or
                        card.select_one("[class*='company']")
                    )
                    company = company_el.get_text(strip=True) if company_el else "Unbekannt"

                    # Location
                    location_el = (
                        card.select_one("[data-testid='svx-job-location']") or
                        card.select_one(".location") or
                        card.select_one("[class*='location']")
                    )
                    location = location_el.get_text(strip=True) if location_el else ""

                    # Description
                    desc_el = card.select_one("[class*='description']") or card.select_one("p")
                    desc = desc_el.get_text(strip=True) if desc_el else ""

                    job = {
                        "hash": stelle_hash("monster.de", title),
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": link,
                        "source": "monster",
                        "description": desc[:500],
                        "employment_type": "festanstellung",
                        "remote_level": detect_remote_level(f"{title} {location} {desc}"),
                    }
                    jobs.append(job)

                time.sleep(1.5)  # Rate limiting
            except Exception as e:
                logger.error("Monster error for '%s': %s", query, e)

    logger.info("Monster: %d Stellen gefunden", len(jobs))
    return jobs
