"""Hays job scraper via sitemap + JSON-LD extraction."""

import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.hays")

SITEMAP_URL = "https://www.hays.de/o/sitemaps/de/job-sitemap.xml"

KEYWORDS = [
    "software-engineer", "projektmanager", "data-analyst",
    "devops", "consultant",
]


def search_hays(params: dict) -> list:
    """Search Hays via sitemap URL filtering + detail page scraping."""
    jobs = []

    # Dynamic keywords from DB, fallback to hardcoded
    kw_data = params.get("keywords", {})
    keywords = kw_data.get("hays_keywords", KEYWORDS)

    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            # Load sitemap
            resp = client.get(SITEMAP_URL)
            if resp.status_code != 200:
                logger.warning("Hays sitemap returned %d", resp.status_code)
                return []

            # Extract relevant URLs
            urls = re.findall(r'<loc>(https://www\.hays\.de/[^<]*)</loc>', resp.text)
            relevant = [u for u in urls if any(kw in u.lower() for kw in keywords)]
            logger.info("Hays: %d relevante URLs aus %d Sitemap-Eintraegen", len(relevant), len(urls))

            # Scrape detail pages
            for url in relevant[:50]:  # Limit to prevent overload
                try:
                    detail = client.get(url)
                    if detail.status_code != 200:
                        continue
                    soup = BeautifulSoup(detail.text, "lxml")

                    # Try JSON-LD
                    ld = soup.find("script", type="application/ld+json")
                    if ld:
                        import json
                        data = json.loads(ld.string)
                        if isinstance(data, list):
                            data = data[0]
                        if data.get("@type") == "JobPosting":
                            title = data.get("title", "")
                            company = data.get("hiringOrganization", {}).get("name", "Hays")
                            location = ""
                            jl = data.get("jobLocation", {})
                            if isinstance(jl, dict):
                                addr = jl.get("address", {})
                                location = addr.get("addressLocality", "")

                            job = {
                                "hash": stelle_hash("hays.de", title),
                                "title": title,
                                "company": company,
                                "location": location,
                                "url": url,
                                "source": "hays",
                                "description": data.get("description", "")[:500],
                                "employment_type": "festanstellung",
                                "remote_level": detect_remote_level(data.get("description", "")),
                            }
                            jobs.append(job)

                    time.sleep(0.5)
                except Exception as e:
                    logger.debug("Hays detail error: %s", e)

    except Exception as e:
        logger.error("Hays search error: %s", e)

    logger.info("Hays: %d Stellen gefunden", len(jobs))
    return jobs
