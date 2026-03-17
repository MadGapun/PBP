"""Indeed job scraper via Playwright.

Uses headless Chromium to handle JavaScript-rendered search results.
No login required. Multi-strategy extraction for robustness.
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
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="de-DE",
        )
        page = context.new_page()

        for query in queries:
            try:
                url = f"https://de.indeed.com/jobs?q={quote(query)}&l=Deutschland"
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(3, 5))

                # Dismiss cookie banner
                _dismiss_cookie_banner(page)

                # Wait for any job content
                try:
                    page.wait_for_selector(
                        ".job_seen_beacon, [data-jk], .resultContent, .jobsearch-ResultsList, "
                        "a[data-jk], div[class*='cardOutline'], div[class*='job_seen']",
                        timeout=10000,
                    )
                except PWTimeout:
                    logger.debug("Indeed: Keine Job-Cards fuer '%s'", query)
                    continue

                # Multi-strategy extraction
                raw_jobs = page.evaluate("""() => {
                    const results = [];
                    const seen = new Set();

                    // Strategy 1: job_seen_beacon containers (current Indeed layout)
                    for (const card of document.querySelectorAll(
                        'div.job_seen_beacon, div[data-jk], td.resultContent, li[data-jk]'
                    )) {
                        const titleEl = card.querySelector(
                            'h2.jobTitle a, h2 a, a.jcs-JobTitle, ' +
                            'a[data-jk], span[id^="jobTitle"] a, a[class*="Title"]'
                        );
                        // Fallback: check span inside h2
                        const titleSpan = !titleEl ? card.querySelector(
                            'h2.jobTitle span, h2 span[title]'
                        ) : null;

                        const title = titleEl?.textContent?.trim() ||
                                     titleSpan?.textContent?.trim() || '';
                        if (!title || title.length < 5 || seen.has(title)) continue;
                        seen.add(title);

                        // Build link
                        let link = '';
                        const jk = card.getAttribute('data-jk') ||
                                  titleEl?.getAttribute('data-jk') ||
                                  titleEl?.closest('[data-jk]')?.getAttribute('data-jk');
                        if (jk) {
                            link = 'https://de.indeed.com/viewjob?jk=' + jk;
                        } else if (titleEl?.href) {
                            link = titleEl.href.startsWith('http') ? titleEl.href
                                : 'https://de.indeed.com' + titleEl.href;
                        }

                        const companyEl = card.querySelector(
                            "[data-testid='company-name'], .companyName, " +
                            ".company_location .companyName, span[class*='company' i]"
                        );
                        const locationEl = card.querySelector(
                            "[data-testid='text-location'], .companyLocation, " +
                            ".company_location .companyLocation, div[class*='location' i]"
                        );
                        const descEl = card.querySelector(
                            '.job-snippet, .underShelfFooter, [class*="snippet" i]'
                        );
                        const salaryEl = card.querySelector(
                            "[data-testid='attribute_snippet_testid'], " +
                            ".salary-snippet-container, .estimated-salary, " +
                            "[class*='salary' i], .metadata .attribute_snippet"
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

                    // Strategy 2: Fallback — find all links to /viewjob or /rc/clk
                    if (results.length === 0) {
                        for (const a of document.querySelectorAll(
                            'a[href*="/viewjob"], a[href*="/rc/clk"], a[href*="/pagead/clk"]'
                        )) {
                            const title = a.textContent?.trim() || '';
                            if (!title || title.length < 5 || seen.has(title)) continue;
                            seen.add(title);
                            let link = a.href || '';

                            let card = a.closest('div, li, td');
                            const companyEl = card?.querySelector('[class*="company" i]');
                            const locationEl = card?.querySelector('[class*="location" i]');

                            results.push({
                                title,
                                link,
                                company: companyEl?.textContent?.trim() || 'Unbekannt',
                                location: locationEl?.textContent?.trim() || '',
                                desc: '',
                                salary: '',
                            });
                        }
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

                logger.debug("Indeed: %d Stellen fuer '%s'", len(raw_jobs), query)
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.error("Indeed error for '%s': %s", query, e)

        browser.close()

    logger.info("Indeed: %d Stellen gefunden", len(jobs))
    return jobs


def _dismiss_cookie_banner(page):
    """Try to dismiss cookie consent banners."""
    try:
        for selector in [
            "#onetrust-accept-btn-handler",
            "button[id*='accept' i]", "button[id*='consent' i]",
            "button:has-text('Alle akzeptieren')",
            "button:has-text('Accept')",
        ]:
            btn = page.locator(selector).first
            if btn.count() > 0 and btn.is_visible():
                btn.click(timeout=2000)
                time.sleep(0.5)
                return
    except Exception:
        pass
