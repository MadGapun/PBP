"""Live-Check der 7 defekten Scraper-Quellen (Stand 2026-04-25 in scraper_diagnose).

Was hat sich geaendert? URL noch da? Neue API erkennbar? SPA?
Bot-Block aktiv? Migration?
"""
from __future__ import annotations

import concurrent.futures
import json
import re

import httpx

# Pro Quelle: bekannte Production-URL aus dem PBP-Scraper-Code + ggf.
# Probe-URL die `quellen_health_check` benutzt
TARGETS = [
    # (quelle, beschreibung, urls_die_wir_pruefen)
    ("ferchau", "FERCHAU Engineering Dienstleister", [
        "https://www.ferchau.com/de/de/jobs",
        "https://www.ferchau.com/de/de/karriere",
        "https://karriere.ferchau.com/",
    ]),
    ("gulp", "GULP Freelance/Sales", [
        "https://www.gulp.de/",
        "https://www.gulp.de/projekte",
        "https://www.gulp.de/gulp2/g/projekte",
    ]),
    ("heise_jobs", "Heise Jobs IT/Engineering", [
        "https://jobs.heise.de/",
        "https://jobs.heise.de/jobs",
    ]),
    ("ingenieur_de", "ingenieur.de (VDI)", [
        "https://www.ingenieur.de/jobs/",
        "https://jobboerse.ingenieur.de/",
    ]),
    ("kimeta", "Kimeta DACH-Aggregator", [
        "https://www.kimeta.de/",
        "https://www.kimeta.de/jobs",
    ]),
    ("monster", "Monster international", [
        "https://www.monster.de/",
        "https://www.monster.de/jobs",
    ]),
    ("solcom", "SOLCOM Tech-Dienstleister", [
        "https://www.solcom.de/",
        "https://www.solcom.de/projekte",
    ]),
    # Plus Stepstone — der ist nicht "defekt" aber im Timeout-Loop
    ("stepstone", "Stepstone DACH (Bot-Block)", [
        "https://www.stepstone.de/",
        "https://www.stepstone.de/jobs",
    ]),
]


EXPIRED_MARKERS = [
    re.compile(r"page\s+not\s+found", re.I),
    re.compile(r"seite\s+(nicht|wurde\s+nicht)\s+gefunden", re.I),
    re.compile(r"site\s+moved\s+permanently", re.I),
    re.compile(r"diese\s+seite\s+gibt\s+es\s+nicht\s+mehr", re.I),
]

BOT_MARKERS = [
    re.compile(r"captcha", re.I),
    re.compile(r"cloudflare", re.I),
    re.compile(r"access\s+denied", re.I),
    re.compile(r"please\s+verify\s+you\s+are\s+human", re.I),
    re.compile(r"datadome", re.I),
    re.compile(r"akamai", re.I),
    re.compile(r"perimeterx", re.I),
    re.compile(r"unusual\s+traffic", re.I),
]

SPA_HINTS = [
    re.compile(r'<div\s+id="(?:root|app|__next|__nuxt)"', re.I),
    re.compile(r"react-(?:dom|router)", re.I),
    re.compile(r"vue\.js", re.I),
    re.compile(r"angular", re.I),
    re.compile(r"window\.__INITIAL_STATE__", re.I),
    re.compile(r"window\.__NEXT_DATA__", re.I),
]

API_HINTS = [
    re.compile(r"/api/v\d+/", re.I),
    re.compile(r"/graphql", re.I),
    re.compile(r'"@graph"', re.I),
    re.compile(r"application/ld\+json", re.I),
    re.compile(r"JobPosting", re.I),
]


def probe(url: str) -> dict:
    out = {"url": url}
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=15.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            },
        ) as client:
            r = client.get(url)
            out["http"] = r.status_code
            out["final_url"] = str(r.url)
            out["redirected"] = (url != str(r.url))
            body = r.text or ""
            out["bytes"] = len(body)
            snippet = body[:300_000]
            # Marker
            out["expired"] = any(p.search(snippet) for p in EXPIRED_MARKERS)
            out["bot_block"] = next(
                (p.pattern[:30] for p in BOT_MARKERS if p.search(snippet)),
                None,
            )
            out["spa"] = next(
                (p.pattern[:30] for p in SPA_HINTS if p.search(snippet)),
                None,
            )
            out["api_hints"] = [p.pattern for p in API_HINTS if p.search(snippet)]
            # JSON-LD JobPosting Heuristik
            out["has_jobposting_jsonld"] = '"@type": "JobPosting"' in body or '"@type":"JobPosting"' in body
            # Sitemap?
            out["sitemap_in_robots"] = "/sitemap" in body.lower()[:5000]
    except httpx.TimeoutException:
        out["error"] = "timeout"
    except httpx.RequestError as exc:
        out["error"] = f"{type(exc).__name__}: {str(exc)[:100]}"
    return out


def probe_quelle(target: tuple) -> dict:
    quelle, beschr, urls = target
    return {
        "quelle": quelle,
        "beschreibung": beschr,
        "probes": [probe(u) for u in urls],
    }


def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(probe_quelle, TARGETS))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
