"""SOLCOM Scraper — IT + Engineering Projektportal.

SOLCOM ist ein IT-Personaldienstleister mit eigenem Projektportal.
Kein Login erforderlich. HTML-Scraping mit JSON-LD Fallback.
"""

import logging
import re
import json

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level
from .async_http_helper import fetch_all_parallel

logger = logging.getLogger("bewerbungs_assistent.scraper.solcom")

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


def search_solcom(params: dict) -> list:
    """Search SOLCOM project portal via HTML scraping."""
    jobs = []
    kw_data = params.get("keywords", {})
    queries = kw_data.get("general", FALLBACK_QUERIES)[:8]

    requests_list = [
        {"url": "https://www.solcom.de/de/projektportal.aspx", "params": {"search": q}}
        for q in queries
    ]
    all_responses = fetch_all_parallel(requests_list, headers=HEADERS, delay_between_batches=0.5)

    for _url, params, html in all_responses:
        if not html:
            continue
        query = (params or {}).get("search", "")
        try:
            soup = BeautifulSoup(html, "html.parser")

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
                        company = org.get("name", "SOLCOM") if isinstance(org, dict) else "SOLCOM"
                        loc = item.get("jobLocation", {})
                        if isinstance(loc, list):
                            loc = loc[0] if loc else {}
                        location = ""
                        if isinstance(loc, dict):
                            addr = loc.get("address", {})
                            location = addr.get("addressLocality", "") if isinstance(addr, dict) else ""

                        jobs.append({
                            "hash": stelle_hash("solcom.de", title),
                            "title": title,
                            "company": company,
                            "location": location,
                            "url": item.get("url", ""),
                            "source": "solcom",
                            "description": (item.get("description", "") or "")[:500],
                            "employment_type": "freelance",
                            "remote_level": detect_remote_level(
                                f"{title} {location} {item.get('description', '')}"
                            ),
                        })
                except Exception:
                    continue

            # Fallback: HTML extraction
            if not any(j["source"] == "solcom" for j in jobs):
                cards = soup.select(
                    ".project-item, article, [class*='project'], "
                    "[class*='result-item'], tr[class*='project']"
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
                    url = href if href.startswith("http") else f"https://www.solcom.de{href}"

                    loc_el = card.find(class_=re.compile(r"location|ort|standort", re.I))
                    location = loc_el.get_text(strip=True) if loc_el else ""

                    jobs.append({
                        "hash": stelle_hash("solcom.de", title),
                        "title": title,
                        "company": "SOLCOM",
                        "location": location,
                        "url": url,
                        "source": "solcom",
                        "description": "",
                        "employment_type": "freelance",
                        "remote_level": detect_remote_level(f"{title} {location}"),
                    })

            logger.debug("SOLCOM: %d for '%s'", len(jobs), query)
        except Exception as e:
            logger.error("SOLCOM error for '%s': %s", query, e)

    logger.info("SOLCOM: %d Projekte gefunden", len(jobs))
    return jobs
