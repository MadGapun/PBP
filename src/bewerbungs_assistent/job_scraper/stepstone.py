"""Stepstone HTML scraper.

Scrapes search result pages for job listings.
"""

import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.stepstone")

SEARCH_URLS = [
    "https://www.stepstone.de/jobs/plm-consultant",
    "https://www.stepstone.de/jobs/plm-systemarchitekt",
    "https://www.stepstone.de/jobs/pdm-manager",
    "https://www.stepstone.de/jobs/product-lifecycle-management",
    "https://www.stepstone.de/jobs/plm-projektleiter",
    "https://www.stepstone.de/jobs/engineering-process-manager",
    "https://www.stepstone.de/jobs/plm-berater",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "de-DE,de;q=0.9",
}


def search_stepstone(params: dict) -> list:
    """Search Stepstone via HTML scraping."""
    jobs = []

    # Dynamic keywords from DB, fallback to hardcoded
    kw_data = params.get("keywords", {})
    urls = kw_data.get("stepstone_urls", SEARCH_URLS)

    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for url in urls:
            try:
                resp = client.get(url)
                if resp.status_code != 200:
                    logger.warning("Stepstone %d for %s", resp.status_code, url)
                    continue

                soup = BeautifulSoup(resp.text, "lxml")

                # Try common Stepstone article selectors
                articles = soup.select("article[data-testid]") or soup.select("article")
                for art in articles:
                    title_el = art.select_one("h2 a, h3 a, [data-testid='job-item-title'] a")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    link = title_el.get("href", "")
                    if link and not link.startswith("http"):
                        link = "https://www.stepstone.de" + link

                    company_el = art.select_one("[data-testid='job-item-company'], .job-element__body__company")
                    company = company_el.get_text(strip=True) if company_el else "Unbekannt"

                    location_el = art.select_one("[data-testid='job-item-location'], .job-element__body__location")
                    location = location_el.get_text(strip=True) if location_el else ""

                    job = {
                        "hash": stelle_hash("stepstone.de", title),
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": link,
                        "source": "stepstone",
                        "description": "",
                        "employment_type": "festanstellung",
                        "remote_level": detect_remote_level(f"{title} {location}"),
                    }
                    jobs.append(job)

                time.sleep(1)  # Rate limiting
            except Exception as e:
                logger.error("Stepstone error for %s: %s", url, e)

    logger.info("Stepstone: %d Stellen gefunden", len(jobs))
    return jobs
