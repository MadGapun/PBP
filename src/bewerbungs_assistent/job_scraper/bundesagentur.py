"""Bundesagentur für Arbeit REST API scraper.

Uses the public REST API (no authentication needed).
Reliable, no anti-bot measures.
"""

import logging
import json

import httpx

from . import stelle_hash, detect_remote_level
from .async_http_helper import fetch_all_parallel

logger = logging.getLogger("bewerbungs_assistent.scraper.bundesagentur")

API_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
API_KEY = "jobboerse-jobsuche"  # Public key, no registration needed

DEFAULT_KEYWORDS = [
    "Software Engineer", "Projektmanager", "Data Analyst",
    "DevOps Engineer", "Consultant", "Product Manager",
]


def search_bundesagentur(params: dict) -> list:
    """Search Bundesagentur für Arbeit job API.

    Args:
        params: Search parameters with optional 'keywords' list

    Returns:
        List of job dicts
    """
    keywords = params.get("keywords") or DEFAULT_KEYWORDS
    criteria = params.get("criteria", {})
    jobs = []

    requests_list = [
        {"url": API_URL, "params": {"was": kw, "size": 25, "page": 1}}
        for kw in keywords
    ]
    all_responses = fetch_all_parallel(
        requests_list,
        headers={"X-API-Key": API_KEY, "Accept": "application/json"},
        delay_between_batches=0.3,
    )

    for _url, params, html in all_responses:
        if not html:
            continue
        kw = (params or {}).get("was", "")
        try:
            data = json.loads(html)
            stellenangebote = data.get("stellenangebote", [])
            for s in stellenangebote:
                title = s.get("titel", "")
                company = s.get("arbeitgeber", "Nicht angegeben")
                location = s.get("arbeitsort", {}).get("ort", "")
                ref_nr = s.get("refnr", "")
                job = {
                    "hash": stelle_hash("arbeitsagentur.de", title),
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": f"https://www.arbeitsagentur.de/jobsuche/suche?id={ref_nr}",
                    "source": "bundesagentur",
                    "description": s.get("beruf", ""),
                    "employment_type": "festanstellung",
                    "remote_level": detect_remote_level(f"{title} {location}"),
                }
                jobs.append(job)
        except Exception as e:
            logger.error("BA parse error for '%s': %s", kw, e)

    logger.info("Bundesagentur: %d Stellen gefunden", len(jobs))
    return jobs
