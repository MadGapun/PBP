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
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", DEFAULT_KEYWORDS)
        regionen = kw_data.get("regionen", [])
    else:
        keywords = kw_data or DEFAULT_KEYWORDS
        regionen = []
    criteria = params.get("criteria", {})
    jobs = []

    with httpx.Client(timeout=30) as client:
        for kw in keywords:
            try:
                api_params = {"was": kw, "size": 25, "page": 1}
                if regionen:
                    api_params["wo"] = regionen[0]
                resp = client.get(
                    API_URL,
                    params=api_params,
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


def _extract_text(data: dict, path: str) -> str:
    """Extract string value from nested dict using dot-notation path."""
    current = data
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key, "")
        else:
            return ""
    return current if isinstance(current, str) else ""


def _fetch_ba_detail(client: httpx.Client, ref_nr: str) -> str:
    """Fetch full job description from BA detail API.

    #387: The BA API v4 nests description fields in various locations.
    We check multiple paths to handle both old and new response formats.
    """
    try:
        resp = client.get(
            DETAIL_URL.format(refnr=ref_nr),
            headers={"X-API-Key": API_KEY},
        )
        if resp.status_code != 200:
            return ""
        data = resp.json()
        parts = []

        # Primary description fields (various nesting levels)
        _fields = [
            "stellenbeschreibung",
            "stellenangebotsbeschreibung",
            "stellenangebotsinhalte.stellenbeschreibung",
            "stellenangebotsinhalte.beschreibung",
            "beruf",
            "branche",
            "taetigkeit",
            "arbeitgeberdarstellung",
            "arbeitgeberdarstellungUrl",
        ]
        for path in _fields:
            val = _extract_text(data, path)
            if val and val not in parts:
                parts.append(val)

        # Also check freieBezeichnung and details from top-level dict values
        for key in ("freieBezeichnung", "externeUrl", "beschreibung"):
            val = data.get(key, "")
            if val and isinstance(val, str) and val not in parts:
                parts.append(val)

        desc = " | ".join(parts) if parts else ""
        if not desc:
            logger.debug("BA detail for %s: no description fields found in keys %s",
                         ref_nr, list(data.keys()))
        return desc
    except Exception as e:
        logger.debug("BA detail error for %s: %s", ref_nr, e)
        return ""
