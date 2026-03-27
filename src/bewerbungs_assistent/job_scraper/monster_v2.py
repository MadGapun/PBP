"""Monster.de job scraper via async Playwright - OPTIMIZED VERSION.

Kernverbesserungen:
- asyncio + playwright.async_api statt sync_playwright
- Alle Queries PARALLEL (MAX_PARALLEL_PAGES gleichzeitig)
- Kuerzere Sleeps (1-2s statt 2-4s)
- Timeout 15s statt 30s
- Laufzeit: ~10-15s statt ~35-60s
"""

import asyncio
import logging
import random
from urllib.parse import quote

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.monster")

FALLBACK_QUERIES = [
    "Software Engineer", "Projektmanager", "Data Analyst",
    "DevOps Engineer", "Consultant",
]

MAX_PARALLEL_PAGES = 3

JS_EXTRACT_MONSTER = """() => {
    const results = [];
    const seen = new Set();
    for (const card of document.querySelectorAll(
        'article, [data-testid*="job-card"], div[class*="JobCard" i], div[class*="job-card" i]'
    )) {
        const titleEl = card.querySelector(
            'a[href*="/job-openings/"], a[href*="/stelle/"], h2 a, h3 a, a[class*="title" i]'
        );
        if (!titleEl) continue;
        const title = titleEl.textContent?.trim() || '';
        if (!title || title.length < 5 || seen.has(title)) continue;
        seen.add(title);
        let link = titleEl.getAttribute('href') || '';
        if (link && !link.startsWith('http')) link = 'https://www.monster.de' + link;
        const companyEl = card.querySelector('[class*="company" i], [data-testid*="company"]');
        const locationEl = card.querySelector('[class*="location" i], [data-testid*="location"]');
        const descEl = card.querySelector('[class*="description" i], [class*="snippet" i], p');
        results.push({
            title, link,
            company: companyEl?.textContent?.trim() || 'Unbekannt',
            location: locationEl?.textContent?.trim() || '',
            desc: (descEl?.textContent?.trim() || '').substring(0, 500),
        });
    }
    if (results.length === 0) {
        for (const a of document.querySelectorAll('a[href*="/job-openings/"], a[href*="/stelle/"]')) {
            const title = a.textContent?.trim() || '';
            if (!title || title.length < 5 || seen.has(title)) continue;
            seen.add(title);
            let card = a.closest('article, div, li');
            results.push({
                title, link: a.href || '',
                company: card?.querySelector('[class*="company" i]')?.textContent?.trim() || 'Unbekannt',
                location: card?.querySelector('[class*="location" i]')?.textContent?.trim() || '',
                desc: '',
            });
        }
    }
    if (results.length === 0) {
        for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
            try {
                const data = JSON.parse(script.textContent);
                const items = Array.isArray(data) ? data : [data];
                for (const item of items) {
                    if (item['@type'] !== 'JobPosting') continue;
                    const title = item.title || '';
                    if (!title || seen.has(title)) continue;
                    seen.add(title);
                    results.push({
                        title, link: item.url || '',
                        company: item.hiringOrganization?.name || 'Unbekannt',
                        location: item.jobLocation?.address?.addressLocality || '',
                        desc: (item.description || '').substring(0, 500),
                    });
                }
            } catch (e) {}
        }
    }
    return results;
}"""


async def _scrape_query_monster_async(page, query: str, cookie_accepted: asyncio.Event) -> list:
    try:
        from playwright.async_api import TimeoutError as PWTimeout
        url = f"https://www.monster.de/jobs/suche?q={quote(query)}&where=Deutschland"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(random.uniform(1.0, 2.0))
        if not cookie_accepted.is_set():
            for sel in ["#onetrust-accept-btn-handler", "button[id*='accept' i]",
                        "button:has-text('Alle akzeptieren')"]:
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
                "article, [data-testid*='job'], [class*='JobCard' i], a[href*='/job-openings/']",
                timeout=8000,
            )
        except PWTimeout:
            logger.debug("Monster: Keine Cards fuer '%s'", query)
            return []
        raw = await page.evaluate(JS_EXTRACT_MONSTER)
        logger.debug("Monster: %d Stellen fuer '%s'", len(raw), query)
        return raw
    except Exception as e:
        logger.error("Monster error for '%s': %s", query, e)
        return []


async def _search_monster_async(queries: list) -> list:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("Playwright nicht installiert -- Monster uebersprungen")
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
            tasks = [_scrape_query_monster_async(pages[j], batch[j], cookie_accepted)
                     for j in range(len(batch))]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    all_raw.extend(r)
            for p in pages:
                await p.close()
        await browser.close()
    return all_raw


def search_monster(params: dict) -> list:
    kw_data = params.get("keywords", {})
    queries = kw_data.get("monster_queries", FALLBACK_QUERIES)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _search_monster_async(queries))
                all_raw = future.result(timeout=120)
        else:
            all_raw = loop.run_until_complete(_search_monster_async(queries))
    except Exception:
        all_raw = asyncio.run(_search_monster_async(queries))

    jobs = []
    seen_hashes = set()
    for raw in all_raw:
        h = stelle_hash("monster.de", raw["title"])
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        jobs.append({
            "hash": h,
            "title": raw["title"],
            "company": raw["company"],
            "location": raw["location"],
            "url": raw["link"],
            "source": "monster",
            "description": raw.get("desc", ""),
            "employment_type": "festanstellung",
            "remote_level": detect_remote_level(
                f"{raw['title']} {raw['location']} {raw.get('desc', '')}"
            ),
        })
    logger.info("Monster (async): %d Stellen gefunden", len(jobs))
    return jobs
