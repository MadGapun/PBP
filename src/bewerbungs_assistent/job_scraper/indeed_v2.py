"""Indeed job scraper via async Playwright - OPTIMIZED VERSION.

Kernverbesserungen:
- asyncio + playwright.async_api statt sync_playwright
- Alle Queries PARALLEL laden (MAX_PARALLEL_PAGES gleichzeitig)
- Kuerzere Sleeps (1.5-2.5s statt 3-5s)
- Timeout 15s statt 30s
- Laufzeit: ~12-20s statt ~40-65s
"""

import asyncio
import logging
import random
from urllib.parse import quote

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.indeed")

FALLBACK_QUERIES = [
    "Software Engineer", "Projektmanager", "Data Analyst",
    "DevOps Engineer", "Consultant",
]

MAX_PARALLEL_PAGES = 3

JS_EXTRACT_INDEED = """() => {
    const results = [];
    const seen = new Set();
    for (const card of document.querySelectorAll(
        'div.job_seen_beacon, div[data-jk], td.resultContent, li[data-jk]'
    )) {
        const titleEl = card.querySelector(
            'h2.jobTitle a, h2 a, a.jcs-JobTitle, a[data-jk], span[id^="jobTitle"] a, a[class*="Title"]'
        );
        const titleSpan = !titleEl ? card.querySelector('h2.jobTitle span, h2 span[title]') : null;
        const title = titleEl?.textContent?.trim() || titleSpan?.textContent?.trim() || '';
        if (!title || title.length < 5 || seen.has(title)) continue;
        seen.add(title);
        let link = '';
        const jk = card.getAttribute('data-jk') || titleEl?.getAttribute('data-jk') ||
                   titleEl?.closest('[data-jk]')?.getAttribute('data-jk');
        if (jk) link = 'https://de.indeed.com/viewjob?jk=' + jk;
        else if (titleEl?.href) link = titleEl.href.startsWith('http') ? titleEl.href : 'https://de.indeed.com' + titleEl.href;
        const companyEl = card.querySelector("[data-testid='company-name'], .companyName, span[class*='company' i]");
        const locationEl = card.querySelector("[data-testid='text-location'], .companyLocation, div[class*='location' i]");
        const descEl = card.querySelector('.job-snippet, [class*="snippet" i]');
        results.push({
            title, link,
            company: companyEl?.textContent?.trim() || 'Unbekannt',
            location: locationEl?.textContent?.trim() || '',
            desc: (descEl?.textContent?.trim() || '').substring(0, 500),
        });
    }
    if (results.length === 0) {
        for (const a of document.querySelectorAll('a[href*="/viewjob"], a[href*="/rc/clk"]')) {
            const title = a.textContent?.trim() || '';
            if (!title || title.length < 5 || seen.has(title)) continue;
            seen.add(title);
            let card = a.closest('div, li, td');
            results.push({
                title, link: a.href || '',
                company: card?.querySelector('[class*="company" i]')?.textContent?.trim() || 'Unbekannt',
                location: card?.querySelector('[class*="location" i]')?.textContent?.trim() || '',
                desc: '',
            });
        }
    }
    return results;
}"""


async def _scrape_query_indeed_async(page, query: str, cookie_accepted: asyncio.Event) -> list:
    try:
        from playwright.async_api import TimeoutError as PWTimeout
        url = f"https://de.indeed.com/jobs?q={quote(query)}&l=Deutschland"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(random.uniform(1.5, 2.5))
        if not cookie_accepted.is_set():
            for sel in ["#onetrust-accept-btn-handler", "button[id*='accept' i]"]:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click(timeout=2000)
                        await asyncio.sleep(0.3)
                        break
                except Exception:
                    pass
            cookie_accepted.set()
        try:
            await page.wait_for_selector(
                ".job_seen_beacon, [data-jk], .resultContent, div[class*='cardOutline']",
                timeout=8000,
            )
        except PWTimeout:
            logger.debug("Indeed: Keine Cards fuer '%s'", query)
            return []
        raw = await page.evaluate(JS_EXTRACT_INDEED)
        logger.debug("Indeed: %d Stellen fuer '%s'", len(raw), query)
        return raw
    except Exception as e:
        logger.error("Indeed error for '%s': %s", query, e)
        return []


async def _search_indeed_async(queries: list) -> list:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("Playwright nicht installiert -- Indeed uebersprungen")
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
        for i in range(0, len(queries), MAX_PARALLEL_PAGES):
            batch = queries[i : i + MAX_PARALLEL_PAGES]
            pages = [await context.new_page() for _ in batch]
            tasks = [_scrape_query_indeed_async(pages[j], batch[j], cookie_accepted)
                     for j in range(len(batch))]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    all_raw.extend(r)
            for p in pages:
                await p.close()
        await browser.close()
    return all_raw


def search_indeed(params: dict) -> list:
    kw_data = params.get("keywords", {})
    queries = kw_data.get("indeed_queries", FALLBACK_QUERIES)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _search_indeed_async(queries))
                all_raw = future.result(timeout=120)
        else:
            all_raw = loop.run_until_complete(_search_indeed_async(queries))
    except Exception:
        all_raw = asyncio.run(_search_indeed_async(queries))

    jobs = []
    seen_hashes = set()
    for raw in all_raw:
        h = stelle_hash("indeed.de", raw["title"])
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        jobs.append({
            "hash": h,
            "title": raw["title"],
            "company": raw["company"],
            "location": raw["location"],
            "url": raw["link"],
            "source": "indeed",
            "description": raw.get("desc", ""),
            "employment_type": "festanstellung",
            "remote_level": detect_remote_level(
                f"{raw['title']} {raw['location']} {raw.get('desc', '')}"
            ),
        })
    logger.info("Indeed (async): %d Stellen gefunden", len(jobs))
    return jobs
