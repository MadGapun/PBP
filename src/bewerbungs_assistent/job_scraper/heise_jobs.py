"""Heise Jobs Scraper — IT-Stellenmarkt von Heise Verlag.

Starke IT/Admin-Community, gute Abdeckung für IT-Stellen.
Kein Login erforderlich. HTML-Scraping via requests.
"""

import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.heise_jobs")

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


def search_heise_jobs(params: dict) -> list:
    """Search Heise Jobs via HTML scraping."""
    jobs = []
    kw_data = params.get("keywords", {})
    queries = kw_data.get("general", FALLBACK_QUERIES)[:8]

    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        for query in queries:
            try:
                resp = client.get(
                    "https://www.heise.de/jobs/suche/",
                    params={"q": query},
                )
                if resp.status_code != 200:
                    logger.debug("Heise Jobs HTTP %d for '%s'", resp.status_code, query)
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # Try JSON-LD first (most reliable)
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        import json
                        data = json.loads(script.string or "")
                        items = data if isinstance(data, list) else [data]
                        for item in items:
                            if item.get("@type") != "JobPosting":
                                continue
                            title = item.get("title", "")
                            if not title:
                                continue
                            org = item.get("hiringOrganization", {})
                            company = org.get("name", "Unbekannt") if isinstance(org, dict) else "Unbekannt"
                            loc = item.get("jobLocation", {})
                            if isinstance(loc, list):
                                loc = loc[0] if loc else {}
                            location = ""
                            if isinstance(loc, dict):
                                addr = loc.get("address", {})
                                location = addr.get("addressLocality", "") if isinstance(addr, dict) else ""

                            jobs.append({
                                "hash": stelle_hash("heise.de", title),
                                "title": title,
                                "company": company,
                                "location": location,
                                "url": item.get("url", ""),
                                "source": "heise_jobs",
                                "description": (item.get("description", "") or "")[:2000],
                                "employment_type": "festanstellung",
                                "remote_level": detect_remote_level(
                                    f"{title} {location} {item.get('description', '')}"
                                ),
                            })
                    except Exception:
                        continue

                # Fallback: HTML cards
                if not jobs:
                    cards = soup.select(
                        "article, .job-item, [class*='job-card'], "
                        ".search-result, a[href*='/jobs/']"
                    )
                    for card in cards[:25]:
                        link_el = card.find("a", href=True) if card.name != "a" else card
                        if not link_el:
                            continue
                        title = link_el.get_text(strip=True)
                        if not title or len(title) < 10:
                            continue
                        href = link_el.get("href", "")
                        if not href or "/jobs/suche" in href:
                            continue
                        # Skip generic category/overview pages (#338)
                        if re.match(r"^Jobs\s+\w+$", title):
                            continue
                        # Only accept URLs that point to actual job postings (with numeric ID)
                        if "/jobs/" in href and not re.search(r"/jobs/\d+", href):
                            continue
                        url = href if href.startswith("http") else f"https://www.heise.de{href}"

                        jobs.append({
                            "hash": stelle_hash("heise.de", title),
                            "title": title,
                            "company": "Unbekannt",
                            "location": "",
                            "url": url,
                            "source": "heise_jobs",
                            "description": "",
                            "employment_type": "festanstellung",
                            "remote_level": detect_remote_level(title),
                        })

                logger.debug("Heise Jobs: %d for '%s'", len(jobs), query)
                time.sleep(1.5)
            except Exception as e:
                logger.error("Heise Jobs error for '%s': %s", query, e)

    logger.info("Heise Jobs: %d Stellen gefunden", len(jobs))
    return jobs
