"""Hays job scraper via sitemap + JSON-LD extraction - OPTIMIZED.

Verbesserungen:
- Sitemap-Fetch unveraendert (einmalig)
- Detail-Pages werden PARALLEL geladen via fetch_all_parallel
  statt seriell mit 0.5s Sleep (50 URLs x 0.5s = 25s -> ~5s)
"""

import json
import logging
import re

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level
from .async_http_helper import fetch_all_parallel

logger = logging.getLogger("bewerbungs_assistent.scraper.hays")

SITEMAP_URL = "https://www.hays.de/o/sitemaps/de/job-sitemap.xml"

KEYWORDS = [
    "software-engineer", "projektmanager", "data-analyst",
    "devops", "consultant",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9",
}

def search_hays(params: dict) -> list:
    """Search Hays via sitemap URL filtering + parallel detail page scraping."""
    jobs = []
    kw_data = params.get("keywords", {})
    keywords = kw_data.get("hays_keywords", KEYWORDS)

    try:
        # Sitemap einmalig laden (schnell, kein Parallelisierungsbedarf)
        with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
            resp = client.get(SITEMAP_URL)
            if resp.status_code != 200:
                logger.warning("Hays sitemap returned %d", resp.status_code)
                return []

        urls = re.findall(r'<loc>(https://www\.hays\.de/[^<]*)</loc>', resp.text)
        relevant = [u for u in urls if any(kw in u.lower() for kw in keywords)]
        logger.info("Hays: %d relevante URLs aus %d Sitemap-Eintraegen", len(relevant), len(urls))

        # Detail-Pages PARALLEL laden (war: 50 x 0.5s = 25s seriell)
        detail_requests = [{"url": u} for u in relevant[:50]]
        all_responses = fetch_all_parallel(
            detail_requests, headers=HEADERS, delay_between_batches=0.3
        )

        for url, _params, html in all_responses:
            if not html:
                continue
            try:
                soup = BeautifulSoup(html, "lxml")
                ld = soup.find("script", type="application/ld+json")
                if not ld:
                    continue
                data = json.loads(ld.string)
                if isinstance(data, list):
                    data = data[0]
                if data.get("@type") != "JobPosting":
                    continue
                title = data.get("title", "")
                company = data.get("hiringOrganization", {}).get("name", "Hays")
                location = ""
                jl = data.get("jobLocation", {})
                if isinstance(jl, dict):
                    addr = jl.get("address", {})
                    location = addr.get("addressLocality", "")
                jobs.append({
                    "hash": stelle_hash("hays.de", title),
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": url,
                    "source": "hays",
                    "description": data.get("description", "")[:500],
                    "employment_type": "festanstellung",
                    "remote_level": detect_remote_level(data.get("description", "")),
                })
            except Exception as e:
                logger.debug("Hays detail error for %s: %s", url, e)

    except Exception as e:
        logger.error("Hays search error: %s", e)

    logger.info("Hays: %d Stellen gefunden", len(jobs))
    return jobs
