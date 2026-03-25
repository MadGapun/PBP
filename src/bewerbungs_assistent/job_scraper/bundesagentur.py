"""Bundesagentur für Arbeit REST API scraper.

Uses the public REST API (no authentication needed).
Reliable, no anti-bot measures.
"""

import logging
import time

import httpx

from . import stelle_hash, detect_remote_level

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

    with httpx.Client(timeout=30) as client:
        for kw in keywords:
            try:
                resp = client.get(
                    API_URL,
                    params={"was": kw, "size": 25, "page": 1},
                    headers={"X-API-Key": API_KEY}
                )
                if resp.status_code != 200:
                    logger.warning("BA API %d for '%s'", resp.status_code, kw)
                    continue

                data = resp.json()
                stellenangebote = data.get("stellenangebote", [])

                for s in stellenangebote:
                    title = s.get("titel", "")
                    company = s.get("arbeitgeber", "Nicht angegeben")
                    location = s.get("arbeitsort", {}).get("ort", "")
                    ref_nr = s.get("refnr", "")

                    # Fetch full description from detail API
                    description = s.get("beruf", "")
                    if ref_nr:
                        description = _fetch_ba_detail(client, ref_nr) or description

                    job = {
                        "hash": stelle_hash("arbeitsagentur.de", title),
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": f"https://www.arbeitsagentur.de/jobsuche/suche?id={ref_nr}",
                        "source": "bundesagentur",
                        "description": description[:2000],
                        "employment_type": "festanstellung",
                        "remote_level": detect_remote_level(f"{title} {location} {description}"),
                    }
                    jobs.append(job)

                time.sleep(0.5)  # Be polite
            except Exception as e:
                logger.error("BA search error for '%s': %s", kw, e)

    logger.info("Bundesagentur: %d Stellen gefunden", len(jobs))
    return jobs


DETAIL_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs/{refnr}"


def _fetch_ba_detail(client: httpx.Client, ref_nr: str) -> str:
    """Fetch full job description from BA detail API."""
    try:
        resp = client.get(
            DETAIL_URL.format(refnr=ref_nr),
            headers={"X-API-Key": API_KEY},
        )
        if resp.status_code != 200:
            return ""
        data = resp.json()
        parts = []
        for field in ("stellenbeschreibung", "beruf", "branche", "taetigkeit"):
            val = data.get(field, "")
            if val and isinstance(val, str):
                parts.append(val)
        # Also check nested arbeitgeberdarstellung
        ag = data.get("arbeitgeberdarstellung", "")
        if ag:
            parts.append(ag)
        return " | ".join(parts) if parts else ""
    except Exception as e:
        logger.debug("BA detail error for %s: %s", ref_nr, e)
        return ""
