"""Kimeta Scraper — Deutscher Job-Aggregator.

Aggregiert Stellen aus vielen Quellen, gute DE-Abdeckung.
Kein Login erforderlich. HTML-Scraping.

Fix #236: Erweiterte CSS-Selektoren, URL-Fallbacks, JSON-LD-Fallback.
"""

import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level, fetch_description_from_detail

logger = logging.getLogger("bewerbungs_assistent.scraper.kimeta")

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

# URL-Varianten (#236)
_SEARCH_URLS = [
    "https://www.kimeta.de/jobs",
    "https://www.kimeta.de/stellenangebote",
    "https://www.kimeta.de/suche",
]


def search_kimeta(params: dict) -> list:
    """Search Kimeta job aggregator via HTML scraping."""
    jobs = []
    kw_data = params.get("keywords", {})
    queries = kw_data.get("general", FALLBACK_QUERIES)[:8]

    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
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
                        logger.warning("Kimeta: Keine funktionierende URL gefunden (#236)")
                        return jobs
                else:
                    resp = client.get(
                        working_url,
                        params={"q": query, "l": "Deutschland"},
                    )
                    if resp.status_code != 200:
                        logger.debug("Kimeta HTTP %d for '%s'", resp.status_code, query)
                        continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # Extended selectors (#236): Kimeta aendert CSS-Klassen regelmaessig
                cards = (
                    soup.select("article.result") or
                    soup.select(".job-item") or
                    soup.select("li.result") or
                    soup.select("[class*='result-item']") or
                    soup.select("[class*='job-card']") or
                    soup.select("[class*='search-result']") or
                    soup.select("[class*='stellenangebot']") or
                    soup.select("div[data-job]") or
                    soup.select("a[href*='/stellenangebot/']")
                )

                # JSON-LD Fallback (#236): Falls Kimeta JSON-LD hinzugefuegt hat
                if not cards:
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
                                    "hash": stelle_hash("kimeta.de", title),
                                    "title": title,
                                    "company": company,
                                    "location": location,
                                    "url": item.get("url", ""),
                                    "source": "kimeta",
                                    "description": (item.get("description", "") or "")[:2000],
                                    "employment_type": "festanstellung",
                                    "remote_level": detect_remote_level(
                                        f"{title} {location} {item.get('description', '')}"
                                    ),
                                })
                        except Exception:
                            continue

                seen = set()
                for card in cards[:25]:
                    # Title: extended heading + link selectors (#236)
                    t_el = (
                        card.find(["h2", "h3", "h4"]) or
                        card.select_one("a.job-title, a.title") or
                        card.select_one("[class*='title']") or
                        card.select_one("a[href*='/stellenangebot/']")
                    )
                    title = t_el.get_text(strip=True) if t_el else ""
                    if not title or len(title) < 5 or title in seen:
                        continue
                    seen.add(title)

                    # Company: extended selectors (#236)
                    f_el = (
                        card.select_one(".company, .employer, [class*='company']") or
                        card.select_one("[class*='employer']") or
                        card.select_one("[class*='firma']") or
                        card.select_one("[class*='arbeitgeber']")
                    )
                    company = f_el.get_text(strip=True) if f_el else "Unbekannt"

                    # Location: extended selectors (#236)
                    o_el = (
                        card.select_one(".location, [class*='location']") or
                        card.select_one("[class*='ort']") or
                        card.select_one("[class*='standort']")
                    )
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

    # Fetch descriptions from detail pages
    if jobs:
        with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as detail_client:
            for job in jobs:
                if job.get("description") or not job.get("url"):
                    continue
                desc = fetch_description_from_detail(job["url"], detail_client)
                if desc:
                    job["description"] = desc
                    job["remote_level"] = detect_remote_level(
                        f"{job['title']} {job.get('location', '')} {desc}"
                    )
                time.sleep(1)
        fetched = sum(1 for j in jobs if j.get("description"))
        logger.info("Kimeta: %d/%d Beschreibungen von Detail-Seiten", fetched, len(jobs))

    logger.info("Kimeta: %d Stellen gefunden", len(jobs))
    return jobs
