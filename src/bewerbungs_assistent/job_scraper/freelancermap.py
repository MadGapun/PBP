"""Freelancermap scraper via embedded JS state extraction."""

import json
import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.freelancermap")

SEARCH_URLS = [
    "https://www.freelancermap.de/projektboerse.html?q=PLM",
    "https://www.freelancermap.de/projektboerse.html?q=PDM",
    "https://www.freelancermap.de/projektboerse.html?q=Windchill",
    "https://www.freelancermap.de/projektboerse.html?q=Product+Lifecycle",
]


def search_freelancermap(params: dict) -> list:
    """Search Freelancermap by extracting embedded JS project state."""
    jobs = []

    # Dynamic keywords from DB, fallback to hardcoded
    kw_data = params.get("keywords", {})
    urls = kw_data.get("freelancermap_urls", SEARCH_URLS)

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for url in urls:
            try:
                resp = client.get(url)
                if resp.status_code != 200:
                    continue

                projects = _extract_projects_from_js(resp.text)
                for p in projects:
                    title = p.get("title", "")
                    company = p.get("poster", {}).get("company", "Freelancermap")
                    locations = p.get("locations", [])
                    location = locations[0].get("name", "") if locations else ""
                    slug = p.get("slug", "")

                    desc_html = p.get("description", "")
                    desc = BeautifulSoup(desc_html, "lxml").get_text() if desc_html else ""

                    job = {
                        "hash": stelle_hash("freelancermap.de", title),
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": f"https://www.freelancermap.de/projekt/{slug}" if slug else url,
                        "source": "freelancermap",
                        "description": desc[:500],
                        "employment_type": "freelance",
                        "remote_level": detect_remote_level(f"{title} {location} {desc}"),
                    }
                    jobs.append(job)

                time.sleep(1)
            except Exception as e:
                logger.error("Freelancermap error: %s", e)

    logger.info("Freelancermap: %d Projekte gefunden", len(jobs))
    return jobs


def _extract_projects_from_js(html: str) -> list:
    """Extract projectsObject from embedded PHP-inline JavaScript."""
    match = re.search(r'projectsObject\s*=\s*(\[)', html)
    if not match:
        return []

    start = match.start(1)
    depth = 0
    i = start
    while i < len(html):
        if html[i] == '[':
            depth += 1
        elif html[i] == ']':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start:i+1])
                except json.JSONDecodeError:
                    return []
        i += 1
    return []
