"""Stellenanzeigen.de Scraper — Grosses deutsches Jobportal.

3.2 Mio. Besucher/Monat, breites Stellenangebot.
Kein Login erforderlich. HTML-Scraping mit JSON-LD Fallback.
"""

import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.stellenanzeigen_de")

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


def search_stellenanzeigen_de(params: dict) -> list:
    """Search Stellenanzeigen.de via HTML scraping."""
    jobs = []
    kw_data = params.get("keywords", {})
    queries = kw_data.get("general", FALLBACK_QUERIES)[:8]

    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        for query in queries:
            try:
                resp = client.get(
                    "https://www.stellenanzeigen.de/stellenangebote/",
                    params={"q": query, "wo": "Deutschland"},
                )
                if resp.status_code != 200:
                    logger.debug("Stellenanzeigen.de HTTP %d for '%s'", resp.status_code, query)
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # JSON-LD structured data (preferred)
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
                            company = org.get("name", "Unbekannt") if isinstance(org, dict) else "Unbekannt"
                            loc = item.get("jobLocation", {})
                            if isinstance(loc, list):
                                loc = loc[0] if loc else {}
                            location = ""
                            if isinstance(loc, dict):
                                addr = loc.get("address", {})
                                location = addr.get("addressLocality", "") if isinstance(addr, dict) else ""

                            jobs.append({
                                "hash": stelle_hash("stellenanzeigen.de", title),
                                "title": title,
                                "company": company,
                                "location": location,
                                "url": item.get("url", ""),
                                "source": "stellenanzeigen_de",
                                "description": (item.get("description", "") or "")[:2000],
                                "employment_type": "festanstellung",
                                "remote_level": detect_remote_level(
                                    f"{title} {location} {item.get('description', '')}"
                                ),
                            })
                    except Exception:
                        continue

                # Fallback: HTML card extraction
                if not any(j["source"] == "stellenanzeigen_de" for j in jobs):
                    cards = soup.select(
                        "article, .job-item, [class*='stellenangebot'], "
                        "[class*='job-card'], .search-result-item"
                    )
                    seen = set()
                    for card in cards[:25]:
                        link_el = card.find("a", href=True)
                        if not link_el:
                            continue
                        title = link_el.get_text(strip=True)
                        if not title or len(title) < 5 or title in seen:
                            continue
                        seen.add(title)

                        href = link_el.get("href", "")
                        url = href if href.startswith("http") else f"https://www.stellenanzeigen.de{href}"
                        if "/stellenangebote/" in url and "?" in url:
                            continue  # search page link, not a job

                        comp_el = card.find(class_=re.compile(r"company|firma|arbeitgeber", re.I))
                        loc_el = card.find(class_=re.compile(r"location|ort|standort", re.I))

                        jobs.append({
                            "hash": stelle_hash("stellenanzeigen.de", title),
                            "title": title,
                            "company": comp_el.get_text(strip=True) if comp_el else "Unbekannt",
                            "location": loc_el.get_text(strip=True) if loc_el else "",
                            "url": url,
                            "source": "stellenanzeigen_de",
                            "description": "",
                            "employment_type": "festanstellung",
                            "remote_level": detect_remote_level(f"{title}"),
                        })

                logger.debug("Stellenanzeigen.de: %d for '%s'", len(jobs), query)
                time.sleep(1.5)
            except Exception as e:
                logger.error("Stellenanzeigen.de error for '%s': %s", query, e)

    logger.info("Stellenanzeigen.de: %d Stellen gefunden", len(jobs))
    return jobs
