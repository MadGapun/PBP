"""StepStone job scraper via Playwright.

Uses headless Chromium to render JavaScript-heavy search pages.
No login required.
"""

import logging
import random
import time

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.stepstone")

SEARCH_URLS = [
    "https://www.stepstone.de/jobs/plm-consultant",
    "https://www.stepstone.de/jobs/plm-systemarchitekt",
    "https://www.stepstone.de/jobs/pdm-manager",
    "https://www.stepstone.de/jobs/product-lifecycle-management",
    "https://www.stepstone.de/jobs/plm-projektleiter",
    "https://www.stepstone.de/jobs/engineering-process-manager",
    "https://www.stepstone.de/jobs/plm-berater",
]


def search_stepstone(params: dict) -> list:
    """Search StepStone via Playwright headless browser."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.warning("Playwright nicht installiert — StepStone uebersprungen")
        return []

    jobs = []
    kw_data = params.get("keywords", {})
    urls = kw_data.get("stepstone_urls", SEARCH_URLS)

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

        for url in urls:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(2, 4))

                # Wait for job listings to appear
                try:
                    page.wait_for_selector("article, [data-testid*='job'], [class*='JobCard']", timeout=10000)
                except PWTimeout:
                    logger.debug("StepStone: Keine Job-Cards auf %s", url)
                    continue

                # Extract job cards via JavaScript
                raw_jobs = page.evaluate("""() => {
                    const results = [];
                    const cards = document.querySelectorAll(
                        'article[data-testid], article, [data-at="job-item"]'
                    );
                    for (const card of cards) {
                        const titleEl = card.querySelector(
                            'h2 a, h3 a, [data-testid="job-item-title"] a, a[class*="JobTitle"]'
                        );
                        if (!titleEl) continue;
                        const title = titleEl.textContent?.trim() || '';
                        if (!title) continue;

                        let link = titleEl.getAttribute('href') || '';
                        if (link && !link.startsWith('http')) {
                            link = 'https://www.stepstone.de' + link;
                        }

                        const companyEl = card.querySelector(
                            '[data-testid="job-item-company"], [class*="company"], [data-at="job-item-company-name"]'
                        );
                        const locationEl = card.querySelector(
                            '[data-testid="job-item-location"], [class*="location"], [data-at="job-item-location"]'
                        );

                        results.push({
                            title,
                            link,
                            company: companyEl?.textContent?.trim() || 'Unbekannt',
                            location: locationEl?.textContent?.trim() || '',
                        });
                    }
                    return results;
                }""")

                for raw in raw_jobs:
                    job = {
                        "hash": stelle_hash("stepstone.de", raw["title"]),
                        "title": raw["title"],
                        "company": raw["company"],
                        "location": raw["location"],
                        "url": raw["link"],
                        "source": "stepstone",
                        "description": "",
                        "employment_type": "festanstellung",
                        "remote_level": detect_remote_level(f"{raw['title']} {raw['location']}"),
                    }
                    jobs.append(job)

                time.sleep(random.uniform(1, 2))
            except Exception as e:
                logger.error("StepStone error for %s: %s", url, e)

        browser.close()

    logger.info("StepStone: %d Stellen gefunden", len(jobs))
    return jobs
