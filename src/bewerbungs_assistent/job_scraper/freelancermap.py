"""Freelancermap scraper via embedded JS state extraction."""

import json
import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level


def _extract_publish_date(project: dict) -> str | None:
    """Extract publication date from freelancermap project data.

    Tries multiple field names that freelancermap may use.
    Returns ISO date string or None.
    """
    for key in ("publishedAt", "published_at", "createdAt", "created_at",
                "created", "startDate", "start_date", "start"):
        val = project.get(key)
        if val and isinstance(val, str) and len(val) >= 10:
            return val[:10]  # YYYY-MM-DD
    return None

logger = logging.getLogger("bewerbungs_assistent.scraper.freelancermap")

SEARCH_URLS = [
    "Software-Engineer", "Projektmanager",
    "Data-Analyst", "Consultant",
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
                        "description": desc[:2000],
                        "employment_type": "freelance",
                        "remote_level": detect_remote_level(f"{title} {location} {desc}"),
                    }
                    pub_date = _extract_publish_date(p)
                    if pub_date:
                        job["veroeffentlicht_am"] = pub_date
                    jobs.append(job)

                time.sleep(1)
            except Exception as e:
                logger.error("Freelancermap error: %s", e)

    # Fallback to Playwright if httpx returned nothing
    if not jobs:
        logger.info("Freelancermap: httpx lieferte 0 Ergebnisse, versuche Playwright-Fallback...")
        jobs = _playwright_fallback(urls)

    logger.info("Freelancermap: %d Projekte gefunden", len(jobs))
    return jobs


def _playwright_fallback(urls: list) -> list:
    """Fallback: Use Playwright to render JS and extract projects."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.debug("Playwright nicht verfügbar für Freelancermap-Fallback")
        return []

    jobs = []
    import random
    import time as _time

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        for url in urls:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                _time.sleep(random.uniform(2, 3))

                # Try JS extraction from rendered page
                html = page.content()
                projects = _extract_projects_from_js(html)
                if projects:
                    for p in projects:
                        title = p.get("title", "")
                        company = p.get("poster", {}).get("company", "Freelancermap")
                        locations = p.get("locations", [])
                        location = locations[0].get("name", "") if locations else ""
                        slug = p.get("slug", "")

                        from bs4 import BeautifulSoup
                        desc_html = p.get("description", "")
                        desc = BeautifulSoup(desc_html, "lxml").get_text() if desc_html else ""

                        pw_job = {
                            "hash": stelle_hash("freelancermap.de", title),
                            "title": title,
                            "company": company,
                            "location": location,
                            "url": f"https://www.freelancermap.de/projekt/{slug}" if slug else url,
                            "source": "freelancermap",
                            "description": desc[:2000],
                            "employment_type": "freelance",
                            "remote_level": detect_remote_level(f"{title} {location} {desc}"),
                        }
                        pub_date = _extract_publish_date(p)
                        if pub_date:
                            pw_job["veroeffentlicht_am"] = pub_date
                        jobs.append(pw_job)
                    continue

                # If JS extraction still fails, try DOM extraction
                raw_jobs = page.evaluate("""() => {
                    const results = [];
                    const cards = document.querySelectorAll('.project-card, .list-item-content, article');
                    for (const card of cards) {
                        const titleEl = card.querySelector('h3 a, h2 a, a[class*="title"]');
                        if (!titleEl) continue;
                        const title = titleEl.textContent?.trim() || '';
                        if (!title) continue;
                        let link = titleEl.getAttribute('href') || '';
                        if (link && !link.startsWith('http')) link = 'https://www.freelancermap.de' + link;
                        const locEl = card.querySelector('[class*="location"], .fa-map-marker-alt');
                        const descEl = card.querySelector('[class*="description"], p');
                        results.push({
                            title,
                            link,
                            location: locEl?.parentElement?.textContent?.trim() || locEl?.textContent?.trim() || '',
                            desc: (descEl?.textContent?.trim() || '').substring(0, 2000),
                        });
                    }
                    return results;
                }""")
                for raw in raw_jobs:
                    jobs.append({
                        "hash": stelle_hash("freelancermap.de", raw["title"]),
                        "title": raw["title"],
                        "company": "Freelancermap",
                        "location": raw["location"],
                        "url": raw["link"],
                        "source": "freelancermap",
                        "description": raw["desc"],
                        "employment_type": "freelance",
                        "remote_level": detect_remote_level(f"{raw['title']} {raw['location']} {raw['desc']}"),
                    })

            except Exception as e:
                logger.error("Freelancermap Playwright fallback error: %s", e)
        browser.close()

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
