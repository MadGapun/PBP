"""StepStone job scraper via async Playwright - OPTIMIZED VERSION.

Kernverbesserungen gegenueber v1:
- asyncio + playwright.async_api statt sync_playwright
- Alle URLs werden PARALLEL geladen (nicht seriell)
- Ein Browser-Context, mehrere Pages gleichzeitig
- Kuerzere Sleeps (1-2s statt 2-4s)
- Timeout 15s statt 30s (schneller fail)
- Cookie-Banner nur 1x pruefen
- Laufzeit: ~8-15s statt ~35-90s
"""

import asyncio
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

MAX_PARALLEL_PAGES = 3  # Max gleichzeitige Pages (Bot-Erkennung vermeiden)


JS_EXTRACT = """() => {
    const results = [];
    const seen = new Set();

    // Strategy 1: article elements (classic StepStone)
    for (const card of document.querySelectorAll('article')) {
        const titleEl = card.querySelector('a[href*="/stellenangebot"]') ||
                       card.querySelector('h2 a, h3 a') ||
                       card.querySelector('a[href*="/jobs/"]');
        if (!titleEl) continue;
        const title = titleEl.textContent?.trim() || '';
        if (!title || title.length < 5 || seen.has(title)) continue;
        seen.add(title);
        let link = titleEl.getAttribute('href') || '';
        if (link && !link.startsWith('http')) link = 'https://www.stepstone.de' + link;
        const companyEl = card.querySelector(
            '[class*="company" i],[class*="Company" i],[data-at="job-item-company-name"],span[class*="subtitle"]'
        );
        const locationEl = card.querySelector(
            '[class*="location" i],[class*="Location" i],[data-at="job-item-location"]'
        );
        results.push({
            title, link,
            company: companyEl?.textContent?.trim() || 'Unbekannt',
            location: locationEl?.textContent?.trim() || '',
        });
    }

    // Strategy 2: Links to /stellenangebot/ (fallback)
    if (results.length === 0) {
        for (const a of document.querySelectorAll('a[href*="/stellenangebot"]')) {
            const title = a.textContent?.trim() || '';
            if (!title || title.length < 5 || seen.has(title)) continue;
            seen.add(title);
            let link = a.getAttribute('href') || '';
            if (link && !link.startsWith('http')) link = 'https://www.stepstone.de' + link;
            let card = a.closest('article, li, div[class*="card" i], div[class*="Card" i]');
            if (!card) card = a.parentElement?.parentElement || a.parentElement;
            const companyEl = card?.querySelector('[class*="company" i]');
            const locationEl = card?.querySelector('[class*="location" i]');
            results.push({
                title, link,
                company: companyEl?.textContent?.trim() || 'Unbekannt',
                location: locationEl?.textContent?.trim() || '',
            });
        }
    }

    // Strategy 3: JSON-LD structured data
    if (results.length === 0) {
        for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
            try {
                const data = JSON.parse(script.textContent);
                const items = data['@graph'] || (Array.isArray(data) ? data : [data]);
                for (const item of items) {
                    if (item['@type'] !== 'JobPosting') continue;
                    const title = item.title || '';
                    if (!title || seen.has(title)) continue;
                    seen.add(title);
                    results.push({
                        title, link: item.url || '',
                        company: item.hiringOrganization?.name || 'Unbekannt',
                        location: item.jobLocation?.address?.addressLocality || '',
                    });
                }
            } catch (e) {}
        }
    }
    return results;
}"""


async def _scrape_url_async(page, url: str, cookie_accepted: asyncio.Event) -> list:
    """Scrapt eine einzelne StepStone-URL asynchron."""
    try:
        from playwright.async_api import TimeoutError as PWTimeout
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(random.uniform(1.0, 2.0))  # Kuerzerer Sleep

        # Cookie-Banner: nur 1x pro Session akzeptieren
        if not cookie_accepted.is_set():
            await _dismiss_cookie_banner_async(page)
            cookie_accepted.set()

        # Warte auf Content
        try:
            await page.wait_for_selector(
                "article, [data-testid], [class*='job'], a[href*='/stellenangebot']",
                timeout=8000,
            )
        except PWTimeout:
            logger.debug("StepStone: Keine Job-Cards auf %s", url)
            return []

        raw_jobs = await page.evaluate(JS_EXTRACT)
        logger.debug("StepStone: %d Stellen von %s", len(raw_jobs), url)
        return raw_jobs

    except Exception as e:
        logger.error("StepStone error for %s: %s", url, e)
        return []


async def _dismiss_cookie_banner_async(page):
    """Cookie-Banner async wegklicken."""
    try:
        for selector in [
            "button[id*='accept' i]", "button[id*='consent' i]",
            "button[class*='accept' i]", "#onetrust-accept-btn-handler",
        ]:
            btn = page.locator(selector).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click(timeout=2000)
                await asyncio.sleep(0.3)
                return
    except Exception:
        pass


async def _search_stepstone_async(urls: list) -> list:
    """Kern-Async-Funktion: Playwright-Browser starten, URLs parallel scrapen."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("Playwright nicht installiert -- StepStone uebersprungen")
        return []

    all_raw = []
    cookie_accepted = asyncio.Event()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="de-DE",
        )

        # Verarbeite URLs in Batches (MAX_PARALLEL_PAGES gleichzeitig)
        for i in range(0, len(urls), MAX_PARALLEL_PAGES):
            batch = urls[i : i + MAX_PARALLEL_PAGES]
            pages = [await context.new_page() for _ in batch]
            tasks = [_scrape_url_async(pages[j], batch[j], cookie_accepted)
                     for j in range(len(batch))]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    all_raw.extend(r)
            for p in pages:
                await p.close()

        await browser.close()

    return all_raw


def search_stepstone(params: dict) -> list:
    """Search StepStone via async Playwright - public entry point (sync wrapper)."""
    kw_data = params.get("keywords", {})
    urls = kw_data.get("stepstone_urls", SEARCH_URLS)

    # asyncio.run() oder in laufenden Loop einhaengen
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _search_stepstone_async(urls))
                all_raw = future.result(timeout=120)
        else:
            all_raw = loop.run_until_complete(_search_stepstone_async(urls))
    except Exception:
        all_raw = asyncio.run(_search_stepstone_async(urls))

    jobs = []
    seen_hashes = set()
    for raw in all_raw:
        h = stelle_hash("stepstone.de", raw["title"])
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        jobs.append({
            "hash": h,
            "title": raw["title"],
            "company": raw["company"],
            "location": raw["location"],
            "url": raw["link"],
            "source": "stepstone",
            "description": "",
            "employment_type": "festanstellung",
            "remote_level": detect_remote_level(f"{raw['title']} {raw['location']}"),
        })

    logger.info("StepStone (async): %d Stellen gefunden", len(jobs))
    return jobs
