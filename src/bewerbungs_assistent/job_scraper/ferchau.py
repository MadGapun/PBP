"""FERCHAU Scraper — Engineering & IT Personaldienstleister.

Grosser Footprint in Engineering-Dienstleistungen.
Kein Login erforderlich. HTML-Scraping mit JSON-LD Fallback.
"""

import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.ferchau")

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


def search_ferchau(params: dict) -> list:
    """Search FERCHAU jobs via HTML scraping."""
    jobs = []
    kw_data = params.get("keywords", {})
    queries = kw_data.get("general", FALLBACK_QUERIES)[:8]

    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        for query in queries:
            try:
                resp = client.get(
                    "https://www.ferchau.com/de/de/jobs",
                    params={"search": query},
                )
                if resp.status_code != 200:
                    logger.debug("FERCHAU HTTP %d for '%s'", resp.status_code, query)
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # JSON-LD (preferred)
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        import json
                        data = json.loads(script.string or "")
                        items = data if isinstance(data, list) else data.get("@graph", [data])
                        for item in items:
                            if item.get("@type") != "JobPosting":
                                continue
                            title = item.get("title", "")
                            if not title:
                                continue
                            org = item.get("hiringOrganization", {})
                            company = org.get("name", "FERCHAU") if isinstance(org, dict) else "FERCHAU"
                            loc = item.get("jobLocation", {})
                            if isinstance(loc, list):
                                loc = loc[0] if loc else {}
                            location = ""
                            if isinstance(loc, dict):
                                addr = loc.get("address", {})
                                location = addr.get("addressLocality", "") if isinstance(addr, dict) else ""

                            jobs.append({
                                "hash": stelle_hash("ferchau.com", title),
                                "title": title,
                                "company": company,
                                "location": location,
                                "url": item.get("url", ""),
                                "source": "ferchau",
                                "description": (item.get("description", "") or "")[:2000],
                                "employment_type": "festanstellung",
                                "remote_level": detect_remote_level(
                                    f"{title} {location} {item.get('description', '')}"
                                ),
                            })
                    except Exception:
                        continue

                # Fallback: HTML card extraction
                if not any(j["source"] == "ferchau" for j in jobs):
                    cards = soup.select(
                        "article, .job-item, [class*='job-card'], "
                        "[class*='job-listing'], a[href*='/jobs/']"
                    )
                    seen = set()
                    for card in cards[:25]:
                        link_el = card.find("a", href=re.compile(r"/jobs/")) if card.name != "a" else card
                        if not link_el:
                            continue
                        title = link_el.get_text(strip=True)
                        if not title or len(title) < 5 or title in seen:
                            continue
                        seen.add(title)

                        href = link_el.get("href", "")
                        url = href if href.startswith("http") else f"https://www.ferchau.com{href}"
                        if "/jobs?" in url:
                            continue  # search page link

                        comp_el = card.find(class_=re.compile(r"company|firma", re.I)) if card.name != "a" else None
                        loc_el = card.find(class_=re.compile(r"location|ort|standort", re.I)) if card.name != "a" else None

                        jobs.append({
                            "hash": stelle_hash("ferchau.com", title),
                            "title": title,
                            "company": comp_el.get_text(strip=True) if comp_el else "FERCHAU",
                            "location": loc_el.get_text(strip=True) if loc_el else "",
                            "url": url,
                            "source": "ferchau",
                            "description": "",
                            "employment_type": "festanstellung",
                            "remote_level": detect_remote_level(f"{title}"),
                        })

                logger.debug("FERCHAU: %d for '%s'", len(jobs), query)
                time.sleep(1.5)
            except Exception as e:
                logger.error("FERCHAU error for '%s': %s", query, e)

    logger.info("FERCHAU: %d Stellen gefunden", len(jobs))
    return jobs
