"""Monster.de job scraper via Playwright.

Uses headless Chromium to handle JavaScript-rendered search results.
No login required.
"""

import logging
import random
import time
from urllib.parse import quote

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.monster")

FALLBACK_QUERIES = [
    "PLM Consultant",
    "Product Lifecycle Management",
    "PDM Manager",
]


def search_monster(params: dict) -> list:
    """Search Monster Germany via Playwright headless browser."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.warning("Playwright nicht installiert — Monster uebersprungen")
        return []

    jobs = []
    kw_data = params.get("keywords", {})
    queries = kw_data.get("monster_queries", FALLBACK_QUERIES)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = browser.new_context(
            viewport={"width": random.randint(1200, 1400), "height": random.randint(800, 1000)},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="de-DE",
        )
        page = context.new_page()

        for query in queries:
            try:
                url = f"https://www.monster.de/jobs/suche/?q={quote(query)}&where=Deutschland"
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(2, 4))

                # Wait for job cards
                try:
                    page.wait_for_selector(
                        "[data-testid='svx-job-card'], .card-content, .job-search-card, article",
                        timeout=10000,
                    )
                except PWTimeout:
                    logger.debug("Monster: Keine Job-Cards fuer '%s'", query)
                    continue

                # Extract via JavaScript
                raw_jobs = page.evaluate("""() => {
                    const results = [];
                    const cards = document.querySelectorAll(
                        "div[data-testid='svx-job-card'], section.card-content, " +
                        "div.job-search-card, article.job-cardstyle, article[data-testid]"
                    );
                    for (const card of cards) {
                        const titleEl = card.querySelector(
                            "[data-testid='svx-job-title'] a, h3 a, h2 a, a.job-cardstyle__title"
                        );
                        if (!titleEl) continue;
                        const title = titleEl.textContent?.trim() || '';
                        if (!title) continue;

                        let link = titleEl.getAttribute('href') || '';
                        if (link && !link.startsWith('http')) {
                            link = 'https://www.monster.de' + link;
                        }

                        const companyEl = card.querySelector(
                            "[data-testid='svx-job-company'], .company, [class*='company']"
                        );
                        const locationEl = card.querySelector(
                            "[data-testid='svx-job-location'], .location, [class*='location']"
                        );
                        const descEl = card.querySelector("[class*='description'], p");

                        results.push({
                            title,
                            link,
                            company: companyEl?.textContent?.trim() || 'Unbekannt',
                            location: locationEl?.textContent?.trim() || '',
                            desc: (descEl?.textContent?.trim() || '').substring(0, 500),
                        });
                    }
                    return results;
                }""")

                for raw in raw_jobs:
                    job = {
                        "hash": stelle_hash("monster.de", raw["title"]),
                        "title": raw["title"],
                        "company": raw["company"],
                        "location": raw["location"],
                        "url": raw["link"],
                        "source": "monster",
                        "description": raw["desc"],
                        "employment_type": "festanstellung",
                        "remote_level": detect_remote_level(
                            f"{raw['title']} {raw['location']} {raw['desc']}"
                        ),
                    }
                    jobs.append(job)

                time.sleep(random.uniform(1.5, 3))
            except Exception as e:
                logger.error("Monster error for '%s': %s", query, e)

        browser.close()

    logger.info("Monster: %d Stellen gefunden", len(jobs))
    return jobs
