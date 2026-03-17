"""Kimeta Scraper — Deutscher Job-Aggregator.

Aggregiert Stellen aus vielen Quellen, gute DE-Abdeckung.
Kein Login erforderlich. HTML-Scraping.
"""

import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.kimeta")

FALLBACK_QUERIES = [
    "PLM Consultant",
    "PLM Systemarchitekt",
    "PDM Manager",
    "Product Lifecycle Management",
    "PLM Projektleiter",
    "Engineering Change Manager",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9",
}


def search_kimeta(params: dict) -> list:
    """Search Kimeta job aggregator via HTML scraping."""
    jobs = []
    kw_data = params.get("keywords", {})
    queries = kw_data.get("general", FALLBACK_QUERIES)[:8]

    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        for query in queries:
            try:
                resp = client.get(
                    "https://www.kimeta.de/jobs",
                    params={"q": query, "l": "Deutschland"},
                )
                if resp.status_code != 200:
                    logger.debug("Kimeta HTTP %d for '%s'", resp.status_code, query)
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # Kimeta cards: article.result, .job-item, li.result, [class*='result-item']
                cards = (
                    soup.select("article.result") or
                    soup.select(".job-item") or
                    soup.select("li.result") or
                    soup.select("[class*='result-item']") or
                    soup.select("[class*='job-card']")
                )

                seen = set()
                for card in cards[:25]:
                    # Title
                    t_el = card.find(["h2", "h3", "h4"]) or card.select_one("a.job-title, a.title")
                    title = t_el.get_text(strip=True) if t_el else ""
                    if not title or len(title) < 5 or title in seen:
                        continue
                    seen.add(title)

                    # Company
                    f_el = (
                        card.select_one(".company, .employer, [class*='company']") or
                        card.select_one("[class*='employer']")
                    )
                    company = f_el.get_text(strip=True) if f_el else "Unbekannt"

                    # Location
                    o_el = card.select_one(".location, [class*='location']")
                    location = o_el.get_text(strip=True) if o_el else "Deutschland"

                    # Link
                    a_el = card.find("a", href=True)
                    if not a_el:
                        continue
                    href = a_el.get("href", "")
                    url = href if href.startswith("http") else f"https://www.kimeta.de{href}"

                    jobs.append({
                        "hash": stelle_hash("kimeta.de", title),
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": url,
                        "source": "kimeta",
                        "description": "",
                        "employment_type": "festanstellung",
                        "remote_level": detect_remote_level(f"{title} {location}"),
                    })

                logger.debug("Kimeta: %d for '%s'", len(cards), query)
                time.sleep(2)
            except Exception as e:
                logger.error("Kimeta error for '%s': %s", query, e)

    logger.info("Kimeta: %d Stellen gefunden", len(jobs))
    return jobs
