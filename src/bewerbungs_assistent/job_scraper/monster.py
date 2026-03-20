"""Monster.de job scraper via Playwright.

Uses headless Chromium to handle JavaScript-rendered search results.
No login required. Multi-strategy extraction for robustness.
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
        logger.warning("Playwright nicht installiert — Monster übersprungen")
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
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="de-DE",
        )
        page = context.new_page()

        for query in queries:
            try:
                # Monster.de uses different URL patterns — try current one
                url = f"https://www.monster.de/jobs/suche?q={quote(query)}&where=Deutschland"
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(2, 4))

                # Dismiss cookie banner
                _dismiss_cookie_banner(page)

                # Wait for any content
                try:
                    page.wait_for_selector(
                        "article, [data-testid*='job'], [class*='JobCard' i], "
                        "[class*='job-card' i], a[href*='/job-openings/']",
                        timeout=10000,
                    )
                except PWTimeout:
                    logger.debug("Monster: Keine Job-Cards für '%s'", query)
                    continue

                # Multi-strategy extraction
                raw_jobs = page.evaluate("""() => {
                    const results = [];
                    const seen = new Set();

                    // Strategy 1: Job cards with data-testid or article elements
                    for (const card of document.querySelectorAll(
                        'article, [data-testid*="job-card"], div[class*="JobCard" i], ' +
                        'div[class*="job-card" i], div[class*="card-content"]'
                    )) {
                        const titleEl = card.querySelector(
                            'a[href*="/job-openings/"], a[href*="/stelle/"], ' +
                            'h2 a, h3 a, a[class*="title" i]'
                        );
                        if (!titleEl) continue;
                        const title = titleEl.textContent?.trim() || '';
                        if (!title || title.length < 5 || seen.has(title)) continue;
                        seen.add(title);

                        let link = titleEl.getAttribute('href') || '';
                        if (link && !link.startsWith('http')) {
                            link = 'https://www.monster.de' + link;
                        }

                        const companyEl = card.querySelector(
                            '[class*="company" i], [data-testid*="company"]'
                        );
                        const locationEl = card.querySelector(
                            '[class*="location" i], [data-testid*="location"]'
                        );
                        const descEl = card.querySelector(
                            '[class*="description" i], [class*="snippet" i], p'
                        );

                        results.push({
                            title,
                            link,
                            company: companyEl?.textContent?.trim() || 'Unbekannt',
                            location: locationEl?.textContent?.trim() || '',
                            desc: (descEl?.textContent?.trim() || '').substring(0, 500),
                        });
                    }

                    // Strategy 2: Link-based fallback
                    if (results.length === 0) {
                        for (const a of document.querySelectorAll(
                            'a[href*="/job-openings/"], a[href*="/stelle/"]'
                        )) {
                            const title = a.textContent?.trim() || '';
                            if (!title || title.length < 5 || seen.has(title)) continue;
                            seen.add(title);
                            let link = a.href || '';

                            let card = a.closest('article, div, li');
                            const companyEl = card?.querySelector('[class*="company" i]');
                            const locationEl = card?.querySelector('[class*="location" i]');

                            results.push({
                                title,
                                link,
                                company: companyEl?.textContent?.trim() || 'Unbekannt',
                                location: locationEl?.textContent?.trim() || '',
                                desc: '',
                            });
                        }
                    }

                    // Strategy 3: JSON-LD structured data
                    if (results.length === 0) {
                        for (const script of document.querySelectorAll(
                            'script[type="application/ld+json"]'
                        )) {
                            try {
                                const data = JSON.parse(script.textContent);
                                const items = Array.isArray(data) ? data : [data];
                                for (const item of items) {
                                    if (item['@type'] !== 'JobPosting') continue;
                                    const title = item.title || '';
                                    if (!title || seen.has(title)) continue;
                                    seen.add(title);
                                    results.push({
                                        title,
                                        link: item.url || '',
                                        company: item.hiringOrganization?.name || 'Unbekannt',
                                        location: item.jobLocation?.address?.addressLocality || '',
                                        desc: (item.description || '').substring(0, 500),
                                    });
                                }
                            } catch (e) {}
                        }
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

                logger.debug("Monster: %d Stellen für '%s'", len(raw_jobs), query)
                time.sleep(random.uniform(1.5, 3))
            except Exception as e:
                logger.error("Monster error for '%s': %s", query, e)

        browser.close()

    logger.info("Monster: %d Stellen gefunden", len(jobs))
    return jobs


def _dismiss_cookie_banner(page):
    """Try to dismiss cookie consent banners."""
    try:
        for selector in [
            "#onetrust-accept-btn-handler",
            "button[id*='accept' i]", "button[id*='consent' i]",
            "button:has-text('Alle akzeptieren')",
            "button:has-text('Akzeptieren')",
        ]:
            btn = page.locator(selector).first
            if btn.count() > 0 and btn.is_visible():
                btn.click(timeout=2000)
                time.sleep(0.5)
                return
    except Exception:
        pass
