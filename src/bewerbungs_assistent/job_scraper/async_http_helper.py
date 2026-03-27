"""Async HTTP Helper fuer PBP-Scraper.

Ersetzt serielle httpx-Schleifen mit parallelen Requests via asyncio.
Alle httpx-basierten Scraper koennen diesen Helper nutzen.

Nutzung:
    from .async_http_helper import fetch_all_parallel

    results = fetch_all_parallel([
        {"url": "https://example.com/jobs", "params": {"q": "PLM"}},
        {"url": "https://example.com/jobs", "params": {"q": "CAD"}},
    ], headers=MY_HEADERS, delay_between_batches=0.5)
    # results: list of (url, response_text | None)

Vorteile:
- N serielle Requests a 1.5s Sleep -> 1 Batch-Request + 0.5s
- Bei 8 Keywords: 12s -> ~2s (6x schneller)
- Rate-Limiting bleibt via delay_between_batches erhalten
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("bewerbungs_assistent.async_http_helper")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9",
}

MAX_PARALLEL = 5  # Max gleichzeitige HTTP-Requests


async def _fetch_one(client, url: str, params: dict = None, method: str = "GET") -> tuple:
    """Einen einzelnen Request asynchron ausfuehren."""
    try:
        if method == "GET":
            resp = await client.get(url, params=params or {})
        else:
            resp = await client.post(url, json=params or {})
        if resp.status_code == 200:
            return (url, params, resp.text)
        else:
            logger.debug("HTTP %d for %s", resp.status_code, url)
            return (url, params, None)
    except Exception as e:
        logger.error("Fetch error for %s: %s", url, e)
        return (url, params, None)


async def _fetch_all_async(
    requests: list,
    headers: dict = None,
    timeout: int = 20,
    delay_between_batches: float = 0.5,
) -> list:
    """Alle Requests in Batches parallel ausfuehren."""
    try:
        import httpx
    except ImportError:
        logger.error("httpx nicht installiert")
        return []

    h = {**DEFAULT_HEADERS, **(headers or {})}
    results = []

    async with httpx.AsyncClient(
        headers=h, timeout=timeout, follow_redirects=True
    ) as client:
        for i in range(0, len(requests), MAX_PARALLEL):
            batch = requests[i : i + MAX_PARALLEL]
            tasks = [_fetch_one(client, r["url"], r.get("params"), r.get("method", "GET"))
                     for r in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in batch_results:
                if isinstance(r, tuple):
                    results.append(r)
            if i + MAX_PARALLEL < len(requests):
                await asyncio.sleep(delay_between_batches)

    return results


def fetch_all_parallel(
    requests: list,
    headers: dict = None,
    timeout: int = 20,
    delay_between_batches: float = 0.5,
) -> list:
    """Synchroner Wrapper fuer parallele HTTP-Requests.

    Args:
        requests: Liste von {"url": str, "params": dict, "method": str}
        headers: Zusaetzliche HTTP-Header
        timeout: Request-Timeout in Sekunden
        delay_between_batches: Wartezeit zwischen Batches (Rate-Limiting)

    Returns:
        Liste von (url, params, response_text | None)
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    _fetch_all_async(requests, headers, timeout, delay_between_batches)
                )
                return future.result(timeout=timeout * len(requests) + 30)
        else:
            return loop.run_until_complete(
                _fetch_all_async(requests, headers, timeout, delay_between_batches)
            )
    except Exception:
        return asyncio.run(
            _fetch_all_async(requests, headers, timeout, delay_between_batches)
        )
