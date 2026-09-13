"""ingenieur.de (VDI) Job-Scraper — Engineering-Jobboerse des VDI.

Spezialisiert auf Ingenieur- und Technik-Stellen.
Kein Login erforderlich. HTML-Scraping via requests.

v1.7.104 (#1042): die Karten liest `jobboerse_karten` (dieselbe Plattform
wie Jobware). Bis v1.7.103 traf die Auswahl auch jeden Bestandteil einer
Karte (173 Treffer bei 15 Karten); jede Stelle stand 2-4-mal in der Liste,
fuer jede Kopie wurde die Detailseite erneut geholt, und die Firma war der
"erste beliebige Text" der Karte — ein HTML-Kommentar.
"""

import logging
import time

import httpx

from . import stelle_hash, detect_remote_level, fetch_description_from_detail
from .jobboerse_karten import karten_aus_html

logger = logging.getLogger("bewerbungs_assistent.scraper.ingenieur_de")

FALLBACK_QUERIES = [
    "Software Engineer", "Projektmanager", "Data Analyst",
    "DevOps Engineer", "Consultant",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9",
}

BASIS_URL = "https://jobs.ingenieur.de"


def _stelle(titel: str, firma: str, ort: str, url: str) -> dict:
    return {
        # Der Titel stimmte schon bis v1.7.103 — die Kennung bleibt, und ein
        # Wiederfund fuellt Firma und Ort der gespeicherten Zeile.
        "hash": stelle_hash("ingenieur.de", titel),
        "title": titel,
        "company": firma or "Unbekannt",
        "location": ort,
        "url": url,
        "source": "ingenieur_de",
        "description": "",
        "employment_type": "festanstellung",
        "remote_level": detect_remote_level(f"{titel} {ort}"),
    }


def search_ingenieur_de(params: dict) -> list:
    """Search ingenieur.de jobs via HTML scraping."""
    jobs = []
    gesehen: set = set()
    kw_data = params.get("keywords", {})
    queries = kw_data.get("general", FALLBACK_QUERIES)[:8]

    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        for query in queries:
            try:
                # v1.7.19 (#927): Der Pfad ist /jobs, NICHT /suche —
                # /suche antwortet mit HTTP 404 (live geprueft 18.08.2026,
                # alle Varianten).
                resp = client.get(
                    f"{BASIS_URL}/jobs",
                    params={"q": query},
                )
                if resp.status_code != 200:
                    logger.debug("ingenieur.de HTTP %d for '%s'", resp.status_code, query)
                    continue

                vorher = len(jobs)
                for k in karten_aus_html(resp.text, BASIS_URL):
                    # Jede Anzeige genau einmal — auch ueber Suchbegriffe
                    # hinweg. Bis v1.7.103 zaehlte das Log die Kopien mit.
                    if k["url"] in gesehen:
                        continue
                    gesehen.add(k["url"])
                    jobs.append(_stelle(k["titel"], k["firma"], k["ort"], k["url"]))

                logger.debug("ingenieur.de: %d neu fuer '%s'", len(jobs) - vorher, query)
                time.sleep(1.5)
            except Exception as e:
                logger.error("ingenieur.de error for '%s': %s", query, e)

    # Beschreibungen von den Detailseiten — einmal je Anzeige.
    if jobs:
        with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as detail_client:
            for job in jobs:
                if job.get("description") or not job.get("url"):
                    continue
                desc = fetch_description_from_detail(job["url"], detail_client)
                if desc:
                    job["description"] = desc
                    job["remote_level"] = detect_remote_level(
                        f"{job['title']} {job.get('location', '')} {desc}"
                    )
                time.sleep(1)
        fetched = sum(1 for j in jobs if j.get("description"))
        logger.info("ingenieur.de: %d/%d Beschreibungen von Detail-Seiten", fetched, len(jobs))

    logger.info("ingenieur.de: %d Stellen gefunden", len(jobs))
    return jobs
