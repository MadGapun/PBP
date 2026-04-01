"""GULP Scraper — Top IT/Engineering Freelance-Plattform.

GULP ist eine der groessten Freelance-Projektboersen in Deutschland.
Projektliste ist ohne Login einsehbar (Details teils eingeschraenkt).

Fix #237: SPA-Erkennung + API-Fallback. GULP liefert per httpx nur eine
9KB-Shell ohne Jobdaten. Versucht zuerst die interne JSON-API, dann
HTML-Scraping mit JSON-LD, dann Playwright-Fallback.
"""

import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.gulp")

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

# GULP API-Endpunkte (#237): SPA laedt Daten per JSON-API
_API_URLS = [
    "https://www.gulp.de/gulp2/api/projekte",
    "https://www.gulp.de/api/projekte",
    "https://api.gulp.de/projekte",
]

API_HEADERS = {
    **HEADERS,
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
}


def _try_api_search(client: httpx.Client, query: str) -> list:
    """Try GULP JSON API endpoints (#237)."""
    jobs = []
    for api_url in _API_URLS:
        try:
            resp = client.get(
                api_url,
                params={"query": query, "page": "1"},
                headers=API_HEADERS,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            # Try common API response formats
            items = (
                data.get("results", []) or
                data.get("projekte", []) or
                data.get("items", []) or
                data.get("data", []) or
                (data if isinstance(data, list) else [])
            )
            for item in items:
                title = item.get("title", "") or item.get("name", "") or item.get("projektname", "")
                if not title:
                    continue
                company = item.get("company", "") or item.get("firma", "") or "GULP"
                location = item.get("location", "") or item.get("ort", "") or item.get("einsatzort", "") or ""
                url = item.get("url", "") or item.get("link", "")
                if not url and item.get("id"):
                    url = f"https://www.gulp.de/gulp2/g/projekte/{item['id']}"
                desc = item.get("description", "") or item.get("beschreibung", "") or ""

                jobs.append({
                    "hash": stelle_hash("gulp.de", title),
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": url,
                    "source": "gulp",
                    "description": desc[:2000],
                    "employment_type": "freelance",
                    "remote_level": detect_remote_level(f"{title} {location} {desc}"),
                })
            if jobs:
                logger.info("GULP API (%s): %d Projekte fuer '%s'", api_url, len(jobs), query)
                return jobs
        except Exception as e:
            logger.debug("GULP API %s fehlgeschlagen: %s", api_url, e)
            continue
    return jobs


def _try_playwright_search(query: str) -> list:
    """Playwright-Fallback fuer GULP SPA (#237)."""
    jobs = []
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.debug("GULP: Playwright nicht verfuegbar fuer SPA-Fallback")
        return jobs

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            context = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="de-DE",
            )
            page = context.new_page()
            page.goto(
                f"https://www.gulp.de/gulp2/g/projekte?query={query}",
                wait_until="networkidle",
                timeout=30000,
            )
            page.wait_for_timeout(3000)

            # Extract from rendered page
            soup = BeautifulSoup(page.content(), "html.parser")
            browser.close()

            # JSON-LD from rendered page
            import json
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "")
                    items = data if isinstance(data, list) else data.get("@graph", [data])
                    for item in items:
                        if item.get("@type") != "JobPosting":
                            continue
                        title = item.get("title", "")
                        if not title:
                            continue
                        org = item.get("hiringOrganization", {})
                        company = org.get("name", "GULP") if isinstance(org, dict) else "GULP"
                        loc = item.get("jobLocation", {})
                        if isinstance(loc, list):
                            loc = loc[0] if loc else {}
                        location = ""
                        if isinstance(loc, dict):
                            addr = loc.get("address", {})
                            location = addr.get("addressLocality", "") if isinstance(addr, dict) else ""

                        jobs.append({
                            "hash": stelle_hash("gulp.de", title),
                            "title": title,
                            "company": company,
                            "location": location,
                            "url": item.get("url", ""),
                            "source": "gulp",
                            "description": (item.get("description", "") or "")[:2000],
                            "employment_type": "freelance",
                            "remote_level": detect_remote_level(
                                f"{title} {location} {item.get('description', '')}"
                            ),
                        })
                except Exception:
                    continue

            # HTML cards from rendered page
            if not jobs:
                cards = soup.select(
                    "article, .project-card, [class*='project-item'], "
                    "[class*='search-result'], [class*='result-item'], "
                    "a[href*='/projekt/']"
                )
                seen = set()
                for card in cards[:25]:
                    link_el = card.find("a", href=re.compile(r"/projekt/")) if card.name != "a" else card
                    if not link_el:
                        continue
                    title = link_el.get_text(strip=True)
                    if not title or len(title) < 5 or title in seen:
                        continue
                    seen.add(title)
                    href = link_el.get("href", "")
                    url = href if href.startswith("http") else f"https://www.gulp.de{href}"
                    jobs.append({
                        "hash": stelle_hash("gulp.de", title),
                        "title": title,
                        "company": "GULP",
                        "location": "",
                        "url": url,
                        "source": "gulp",
                        "description": "",
                        "employment_type": "freelance",
                        "remote_level": detect_remote_level(f"{title}"),
                    })
    except Exception as e:
        logger.warning("GULP Playwright-Fallback fehlgeschlagen: %s", e)
    return jobs


def search_gulp(params: dict) -> list:
    """Search GULP projects: API -> HTML -> Playwright fallback (#237)."""
    jobs = []
    kw_data = params.get("keywords", {})
    queries = kw_data.get("general", FALLBACK_QUERIES)[:8]

    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        for query in queries:
            try:
                # Strategy 1: Try JSON API (#237)
                api_jobs = _try_api_search(client, query)
                if api_jobs:
                    jobs.extend(api_jobs)
                    time.sleep(1.5)
                    continue

                # Strategy 2: HTML scraping (original approach)
                resp = client.get(
                    "https://www.gulp.de/gulp2/g/projekte",
                    params={"query": query},
                )
                if resp.status_code != 200:
                    logger.debug("GULP HTTP %d for '%s'", resp.status_code, query)
                    continue

                # SPA-Erkennung (#237): < 15KB = nur Shell
                if len(resp.text) < 15000:
                    logger.info("GULP: Nur %d Bytes — SPA erkannt, versuche Playwright (#237)",
                                len(resp.text))
                    pw_jobs = _try_playwright_search(query)
                    if pw_jobs:
                        jobs.extend(pw_jobs)
                    time.sleep(1.5)
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # JSON-LD extraction (preferred)
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
                            company = org.get("name", "GULP") if isinstance(org, dict) else "GULP"
                            loc = item.get("jobLocation", {})
                            if isinstance(loc, list):
                                loc = loc[0] if loc else {}
                            location = ""
                            if isinstance(loc, dict):
                                addr = loc.get("address", {})
                                location = addr.get("addressLocality", "") if isinstance(addr, dict) else ""

                            jobs.append({
                                "hash": stelle_hash("gulp.de", title),
                                "title": title,
                                "company": company,
                                "location": location,
                                "url": item.get("url", ""),
                                "source": "gulp",
                                "description": (item.get("description", "") or "")[:2000],
                                "employment_type": "freelance",
                                "remote_level": detect_remote_level(
                                    f"{title} {location} {item.get('description', '')}"
                                ),
                            })
                    except Exception:
                        continue

                # Fallback: HTML card extraction
                if not any(j["source"] == "gulp" for j in jobs):
                    cards = soup.select(
                        "article, .project-card, [class*='project-item'], "
                        "[class*='search-result'], a[href*='/projekt/']"
                    )
                    seen = set()
                    for card in cards[:25]:
                        link_el = card.find("a", href=re.compile(r"/projekt/")) if card.name != "a" else card
                        if not link_el:
                            continue
                        title = link_el.get_text(strip=True)
                        if not title or len(title) < 5 or title in seen:
                            continue
                        seen.add(title)

                        href = link_el.get("href", "")
                        url = href if href.startswith("http") else f"https://www.gulp.de{href}"

                        parent = card if card.name in ("article", "div", "li") else card.parent
                        loc_el = parent.find(class_=re.compile(r"location|ort", re.I)) if parent else None
                        comp_el = parent.find(class_=re.compile(r"company|firma", re.I)) if parent else None

                        jobs.append({
                            "hash": stelle_hash("gulp.de", title),
                            "title": title,
                            "company": comp_el.get_text(strip=True) if comp_el else "GULP",
                            "location": loc_el.get_text(strip=True) if loc_el else "",
                            "url": url,
                            "source": "gulp",
                            "description": "",
                            "employment_type": "freelance",
                            "remote_level": detect_remote_level(f"{title}"),
                        })

                logger.debug("GULP: %d for '%s'", len(jobs), query)
                time.sleep(1.5)
            except Exception as e:
                logger.error("GULP error for '%s': %s", query, e)

    logger.info("GULP: %d Projekte gefunden", len(jobs))
    return jobs
