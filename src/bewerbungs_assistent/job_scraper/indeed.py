"""Indeed job scraper via Playwright.

Uses headless Chromium to handle JavaScript-rendered search results.
No login required. Anti-bot measures: random delays, viewport variation.
"""

import logging
import random
import time
from urllib.parse import quote

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.indeed")

FALLBACK_QUERIES = [
    "PLM Consultant",
    "Product Lifecycle Management",
    "PDM Manager",
]


def search_indeed(params: dict) -> list:
    """Search Indeed Germany via Playwright headless browser."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.warning("Playwright nicht installiert — Indeed uebersprungen")
        return []

    jobs = []
    kw_data = params.get("keywords", {})
    queries = kw_data.get("indeed_queries", FALLBACK_QUERIES)

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
                url = f"https://de.indeed.com/jobs?q={quote(query)}&l=Deutschland"
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(3, 5))

                # Wait for job cards
                try:
                    page.wait_for_selector(
                        ".job_seen_beacon, .jobsearch-ResultsList, [data-jk], .cardOutline",
                        timeout=10000,
                    )
                except PWTimeout:
                    logger.debug("Indeed: Keine Job-Cards fuer '%s'", query)
                    continue

                # Extract via JavaScript
                raw_jobs = page.evaluate("""() => {
                    const results = [];
                    const cards = document.querySelectorAll(
                        'div.job_seen_beacon, div[data-jk], li div.cardOutline, .jobsearch-SerpJobCard'
                    );
                    for (const card of cards) {
                        const titleEl = card.querySelector(
                            'h2.jobTitle a, a[data-jk], h2 a, .jobTitle a'
                        );
                        if (!titleEl) continue;
                        const title = titleEl.textContent?.trim() || '';
                        if (!title) continue;

                        // Build link from data-jk attribute
                        let link = '';
                        const jk = card.getAttribute('data-jk') || titleEl.getAttribute('data-jk');
                        if (jk) {
                            link = 'https://de.indeed.com/viewjob?jk=' + jk;
                        } else if (titleEl.href) {
                            link = titleEl.href.startsWith('http') ? titleEl.href
                                : 'https://de.indeed.com' + titleEl.href;
                        }

                        const companyEl = card.querySelector(
                            "[data-testid='company-name'], .companyName, .company"
                        );
                        const locationEl = card.querySelector(
                            "[data-testid='text-location'], .companyLocation, .location"
                        );
                        const descEl = card.querySelector(
                            '.job-snippet, [class*="snippet"], .summary'
                        );
                        const salaryEl = card.querySelector(
                            "[data-testid='attribute_snippet_testid'], .salary-snippet-container, .estimated-salary"
                        );

                        results.push({
                            title,
                            link,
                            company: companyEl?.textContent?.trim() || 'Unbekannt',
                            location: locationEl?.textContent?.trim() || '',
                            desc: (descEl?.textContent?.trim() || '').substring(0, 500),
                            salary: salaryEl?.textContent?.trim() || '',
                        });
                    }
                    return results;
                }""")

                for raw in raw_jobs:
                    job = {
                        "hash": stelle_hash("indeed.de", raw["title"]),
                        "title": raw["title"],
                        "company": raw["company"],
                        "location": raw["location"],
                        "url": raw["link"],
                        "source": "indeed",
                        "description": raw["desc"],
                        "employment_type": "festanstellung",
                        "remote_level": detect_remote_level(
                            f"{raw['title']} {raw['location']} {raw['desc']}"
                        ),
                        "salary_info": raw["salary"] if raw["salary"] else None,
                    }
                    jobs.append(job)

                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.error("Indeed error for '%s': %s", query, e)

        browser.close()

    logger.info("Indeed: %d Stellen gefunden", len(jobs))
    return jobs
