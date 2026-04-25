"""StepStone job scraper via Playwright.

Uses headless Chromium to render JavaScript-heavy search pages.
No login required. Multi-strategy extraction for robustness.
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
        logger.warning("Playwright nicht installiert — StepStone übersprungen")
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
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="de-DE",
        )
        page = context.new_page()

        for url in urls:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(2, 4))

                # Accept cookies if present
                _dismiss_cookie_banner(page)

                # Wait for any content to load
                try:
                    page.wait_for_selector(
                        "article, [data-testid], [class*='job'], a[href*='/stellenangebot']",
                        timeout=10000,
                    )
                except PWTimeout:
                    logger.debug("StepStone: Keine Job-Cards auf %s", url)
                    continue

                # Multi-strategy extraction. Reihenfolge nach Reliability:
                #   1. JSON-LD JobPosting (strukturiert, autoritativ)
                #   2. <article> mit gefiltertem Titel (UI-Chips ausgeschlossen)
                #   3. Anchors als Fallback
                # #500: Vorher liefen die Strategien in umgekehrter Reihenfolge
                # — Strategy 1 schnappte UI-Filter-Chips ("Neuer als 24h",
                # "Teilweise Home-Office") und blockierte Strategy 3 vom
                # Laufen. Jetzt erst JSON-LD, dann Articles mit Filter.
                raw_jobs = page.evaluate("""() => {
                    const results = [];
                    const seen = new Set();
                    const UI_NOISE = /^(neuer als|teilweise|nur |auf unternehmenswebsite|filter|sortieren|merken|ergebnisse|ansicht|jetzt suchen|vor \\d|gestern|heute|abos)/i;

                    // Strategy 1: JSON-LD JobPosting (zuverlaessig)
                    for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
                        try {
                            const data = JSON.parse(script.textContent || '');
                            const items = data['@graph'] || (Array.isArray(data) ? data : [data]);
                            for (const item of items) {
                                if (!item || item['@type'] !== 'JobPosting') continue;
                                const title = (item.title || '').trim();
                                if (!title || seen.has(title)) continue;
                                seen.add(title);
                                let location = '';
                                const jl = item.jobLocation;
                                if (Array.isArray(jl)) {
                                    location = jl.map(x => x?.address?.addressLocality).filter(Boolean).join(', ');
                                } else if (jl) {
                                    location = jl.address?.addressLocality || '';
                                }
                                results.push({
                                    title,
                                    link: item.url || '',
                                    company: item.hiringOrganization?.name || 'Unbekannt',
                                    location,
                                });
                            }
                        } catch (e) {}
                    }

                    // Strategy 2: article elements — nur wenn das Title-Anchor
                    // tatsaechlich auf eine Stellenangebot-Seite zeigt UND der
                    // Titel kein UI-Filter-String ist.
                    if (results.length < 5) {
                        for (const card of document.querySelectorAll('article')) {
                            const titleEl = card.querySelector('a[href*="/stellenangebot"]');
                            if (!titleEl) continue;
                            const link = titleEl.getAttribute('href') || '';
                            if (!link || !/\\/stellenangebot/.test(link)) continue;
                            const title = (titleEl.textContent || '').trim();
                            if (!title || title.length < 8 || seen.has(title)) continue;
                            if (UI_NOISE.test(title)) continue;
                            seen.add(title);
                            const fullLink = link.startsWith('http') ? link : 'https://www.stepstone.de' + link;

                            const companyEl = card.querySelector(
                                '[data-at="job-item-company-name"], ' +
                                '[class*="company" i], [class*="Company" i], ' +
                                'span[class*="subtitle"]'
                            );
                            const locationEl = card.querySelector(
                                '[data-at="job-item-location"], ' +
                                '[class*="location" i], [class*="Location" i]'
                            );

                            results.push({
                                title,
                                link: fullLink,
                                company: companyEl?.textContent?.trim() || 'Unbekannt',
                                location: locationEl?.textContent?.trim() || '',
                            });
                        }
                    }

                    // Strategy 3: Pure anchor-Fallback (selten noetig)
                    if (results.length === 0) {
                        for (const a of document.querySelectorAll('a[href*="/stellenangebot"]')) {
                            const title = (a.textContent || '').trim();
                            if (!title || title.length < 8 || seen.has(title)) continue;
                            if (UI_NOISE.test(title)) continue;
                            seen.add(title);
                            let link = a.getAttribute('href') || '';
                            if (link && !link.startsWith('http')) link = 'https://www.stepstone.de' + link;

                            let card = a.closest('article, li, div[class*="card" i], div[class*="Card" i]');
                            if (!card) card = a.parentElement?.parentElement || a.parentElement;

                            const companyEl = card?.querySelector('[class*="company" i]');
                            const locationEl = card?.querySelector('[class*="location" i]');

                            results.push({
                                title,
                                link,
                                company: companyEl?.textContent?.trim() || 'Unbekannt',
                                location: locationEl?.textContent?.trim() || '',
                            });
                        }
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

                logger.debug("StepStone: %d Stellen von %s", len(raw_jobs), url)
                time.sleep(random.uniform(1, 2))
            except Exception as e:
                logger.error("StepStone error for %s: %s", url, e)

        # Fetch descriptions from detail pages
        _fetch_detail_descriptions(page, jobs)

        browser.close()

    logger.info("StepStone: %d Stellen gefunden", len(jobs))
    return jobs


def _fetch_detail_descriptions(page, jobs):
    """Navigate to each job's detail page and extract description."""
    for job in jobs:
        if job.get("description") or not job.get("url"):
            continue
        try:
            page.goto(job["url"], wait_until="domcontentloaded", timeout=20000)
            time.sleep(random.uniform(1, 2))

            desc = page.evaluate("""() => {
                // JSON-LD first
                for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
                    try {
                        const data = JSON.parse(script.textContent);
                        const items = data['@graph'] || (Array.isArray(data) ? data : [data]);
                        for (const item of items) {
                            if (item['@type'] === 'JobPosting' && item.description) {
                                const div = document.createElement('div');
                                div.innerHTML = item.description;
                                return div.textContent?.trim()?.substring(0, 2000) || '';
                            }
                        }
                    } catch (e) {}
                }
                // HTML content selectors
                for (const sel of [
                    '[class*="job-ad-display"]', '[class*="listing-content"]',
                    '[class*="JobAdContent"]', '[data-testid="job-ad-content"]',
                    '[class*="description"]', 'article',
                ]) {
                    const el = document.querySelector(sel);
                    if (el && el.textContent?.trim().length > 100) {
                        return el.textContent.trim().substring(0, 2000);
                    }
                }
                return '';
            }""")

            if desc:
                job["description"] = desc
                job["remote_level"] = detect_remote_level(
                    f"{job['title']} {job.get('location', '')} {desc}"
                )
                logger.debug("StepStone detail: got %d chars for '%s'", len(desc), job["title"])
        except Exception as e:
            logger.debug("StepStone detail error for '%s': %s", job.get("title", "?"), e)

    fetched = sum(1 for j in jobs if j.get("description"))
    logger.info("StepStone: %d/%d Beschreibungen von Detail-Seiten geladen", fetched, len(jobs))


def _dismiss_cookie_banner(page):
    """Try to dismiss cookie consent banners."""
    try:
        for selector in [
            "button[id*='accept' i]", "button[id*='consent' i]",
            "button[class*='accept' i]", "button[class*='consent' i]",
            "#onetrust-accept-btn-handler",
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
