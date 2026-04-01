"""Jobware Scraper — Premium-Jobportal für Spezialisten und Führungskräfte.

Gute Abdeckung für Senior-Positionen und Fachkräfte.
Kein Login erforderlich. HTML-Scraping mit JSON-LD Fallback.

Fix #235: Mehrere URL-Varianten, erweiterte Selektoren, SPA-Erkennung.
"""

import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.jobware")

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

# URL-Varianten: Jobware hat URLs in der Vergangenheit geaendert (#235)
_SEARCH_URLS = [
    "https://www.jobware.de/suche/",
    "https://www.jobware.de/stellenangebote/",
    "https://www.jobware.de/jobs/",
]


def search_jobware(params: dict) -> list:
    """Search Jobware via HTML scraping."""
    jobs = []
    kw_data = params.get("keywords", {})
    queries = kw_data.get("general", FALLBACK_QUERIES)[:8]

    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        # Find working URL on first query
        working_url = None
        for query in queries:
            try:
                if not working_url:
                    for url_candidate in _SEARCH_URLS:
                        try:
                            resp = client.get(
                                url_candidate,
                                params={"q": query, "l": "Deutschland"},
                            )
                            if resp.status_code == 200 and len(resp.text) > 5000:
                                working_url = url_candidate
                                break
                        except Exception:
                            continue
                    if not working_url:
                        logger.warning("Jobware: Keine funktionierende URL gefunden (#235)")
                        return jobs
                else:
                    resp = client.get(
                        working_url,
                        params={"q": query, "l": "Deutschland"},
                    )
                    if resp.status_code != 200:
                        logger.debug("Jobware HTTP %d for '%s'", resp.status_code, query)
                        continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # SPA-Erkennung: Wenn Seite < 10KB und kein Job-Content, ist Scraping sinnlos (#235)
                if len(resp.text) < 10000 and not soup.find("script", type="application/ld+json"):
                    logger.warning("Jobware: Seite hat nur %d Bytes — moeglicherweise SPA (#235)",
                                   len(resp.text))
                    continue

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
                            company = org.get("name", "Unbekannt") if isinstance(org, dict) else "Unbekannt"
                            loc = item.get("jobLocation", {})
                            if isinstance(loc, list):
                                loc = loc[0] if loc else {}
                            location = ""
                            if isinstance(loc, dict):
                                addr = loc.get("address", {})
                                location = addr.get("addressLocality", "") if isinstance(addr, dict) else ""

                            jobs.append({
                                "hash": stelle_hash("jobware.de", title),
                                "title": title,
                                "company": company,
                                "location": location,
                                "url": item.get("url", ""),
                                "source": "jobware",
                                "description": (item.get("description", "") or "")[:2000],
                                "employment_type": "festanstellung",
                                "remote_level": detect_remote_level(
                                    f"{title} {location} {item.get('description', '')}"
                                ),
                            })
                    except Exception:
                        continue

                # Fallback: HTML card extraction with extended selectors (#235)
                if not any(j["source"] == "jobware" for j in jobs):
                    cards = soup.select(
                        "article, .job-item, [class*='job-card'], [class*='job-list'], "
                        "[class*='search-result'], [class*='result-item'], "
                        "a[href*='/stellenangebot/'], a[href*='/job/'], "
                        "[data-job], [data-jobid]"
                    )
                    seen = set()
                    for card in cards[:25]:
                        link_el = card.find("a", href=True) if card.name != "a" else card
                        if not link_el:
                            continue
                        title = link_el.get_text(strip=True)
                        if not title or len(title) < 5 or title in seen:
                            continue
                        seen.add(title)

                        href = link_el.get("href", "")
                        url = href if href.startswith("http") else f"https://www.jobware.de{href}"

                        comp_el = card.find(class_=re.compile(r"company|firma|employer|arbeitgeber", re.I)) if card.name != "a" else None
                        loc_el = card.find(class_=re.compile(r"location|ort|standort", re.I)) if card.name != "a" else None

                        jobs.append({
                            "hash": stelle_hash("jobware.de", title),
                            "title": title,
                            "company": comp_el.get_text(strip=True) if comp_el else "Unbekannt",
                            "location": loc_el.get_text(strip=True) if loc_el else "",
                            "url": url,
                            "source": "jobware",
                            "description": "",
                            "employment_type": "festanstellung",
                            "remote_level": detect_remote_level(f"{title}"),
                        })

                logger.debug("Jobware: %d for '%s'", len(jobs), query)
                time.sleep(1.5)
            except Exception as e:
                logger.error("Jobware error for '%s': %s", query, e)

    logger.info("Jobware: %d Stellen gefunden", len(jobs))
    return jobs
