"""Adzuna Job-Scraper — REST-API mit deutschen Stellen (B17, #654).

Adzuna bietet eine kostenlose REST-API mit Job-Listings aus 19 Laendern
inkl. Deutschland. Free Tier nach Registrierung auf developer.adzuna.com.

Voraussetzung: User registriert sich, traegt `adzuna_app_id` + `adzuna_app_key`
in den profile_settings ein. Ohne diese Keys: schneller Skip mit klarer
Meldung.

Endpoint: GET https://api.adzuna.com/v1/api/jobs/de/search/<page>
Docs:     https://developer.adzuna.com/docs/search

Eingesetzt als Ersatz fuer die deprecated/blockierten Quellen monster, solcom,
stepstone — und als zweite Bundesagentur-aehnliche Generalquelle.
"""
from __future__ import annotations

import logging
import time
from typing import Optional
from urllib.parse import quote

import httpx

from . import stelle_hash, detect_remote_level
from .textgrenzen import fuer_speicher

logger = logging.getLogger("bewerbungs_assistent.scraper.adzuna")

ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs/de/search"
DEFAULT_PAGES = 2
DEFAULT_RESULTS_PER_PAGE = 50  # Adzuna-Max ist 50

FALLBACK_QUERIES = [
    "Software Engineer", "Projektmanager", "Data Analyst",
    "Consultant", "DevOps Engineer",
]


def _get_credentials(params: dict) -> Optional[tuple[str, str]]:
    """Liest app_id + app_key aus params oder fallback auf DB-Settings.

    Reihenfolge:
    1. params["adzuna_app_id"] + params["adzuna_app_key"] (Tests)
    2. DB-Setting `adzuna_app_id` + `adzuna_app_key`
    3. None (Skip)
    """
    app_id = (params or {}).get("adzuna_app_id")
    app_key = (params or {}).get("adzuna_app_key")
    if app_id and app_key:
        return app_id, app_key
    # DB-Fallback (live im Production-Pfad)
    try:
        from ..database import Database
        db = Database()
        app_id = db.get_setting("adzuna_app_id", "") or ""
        app_key = db.get_setting("adzuna_app_key", "") or ""
        if app_id and app_key:
            return app_id, app_key
    except Exception as exc:
        logger.debug("Adzuna: DB-Settings nicht lesbar (%s)", exc)
    return None


def search_adzuna(params: dict) -> list[dict]:
    """Hauptfunktion — von _SCRAPER_MAP registriert.

    Args:
        params: Such-Params (keywords, criteria, max_pages, ...)
            Plus Adzuna-spezifisch:
            - adzuna_app_id, adzuna_app_key (optional, sonst DB-Fallback)

    Returns:
        Liste von Job-Dicts kompatibel mit `save_jobs`.
    """
    creds = _get_credentials(params)
    if not creds:
        logger.info(
            "Adzuna: keine Credentials gefunden — Skip. "
            "User soll adzuna_app_id + adzuna_app_key in den Settings "
            "eintragen (kostenlose Registrierung auf developer.adzuna.com)."
        )
        return []
    app_id, app_key = creds

    kw_data = params.get("keywords", {}) or {}
    criteria = params.get("criteria", {}) or {}
    queries = (
        kw_data.get("adzuna_queries")
        or kw_data.get("general")
        or FALLBACK_QUERIES
    )[:6]
    regions = criteria.get("regionen") or kw_data.get("regionen") or []
    primary_region = next(
        (r for r in regions if r.lower() not in ("remote", "deutschland", "dach")),
        None,
    )
    max_pages = int(params.get("max_pages", DEFAULT_PAGES))
    max_pages = max(1, min(max_pages, 5))

    jobs: list[dict] = []
    seen_hashes: set[str] = set()

    headers = {
        "User-Agent": "PBP/1.7 (+github.com/MadGapun/PBP)",
        "Accept": "application/json",
    }

    with httpx.Client(timeout=20, headers=headers) as client:
        for query in queries:
            for page in range(1, max_pages + 1):
                url = f"{ADZUNA_BASE}/{page}"
                api_params = {
                    "app_id": app_id,
                    "app_key": app_key,
                    "results_per_page": DEFAULT_RESULTS_PER_PAGE,
                    "what": query,
                    "content-type": "application/json",
                }
                if primary_region:
                    api_params["where"] = primary_region
                try:
                    r = client.get(url, params=api_params)
                except httpx.RequestError as exc:
                    logger.warning(
                        "Adzuna request error: %s", str(exc)[:200]
                    )
                    break
                if r.status_code == 401:
                    logger.warning(
                        "Adzuna 401 — app_id/app_key ungueltig"
                    )
                    return jobs
                if r.status_code == 403:
                    logger.warning(
                        "Adzuna 403 — Quota erschoepft fuer heute"
                    )
                    return jobs
                if r.status_code >= 400:
                    logger.debug(
                        "Adzuna HTTP %d for '%s' page=%d",
                        r.status_code, query, page,
                    )
                    break
                try:
                    data = r.json()
                except ValueError:
                    logger.debug("Adzuna: JSON-Parse-Fehler")
                    break
                results = data.get("results") or []
                if not results:
                    break
                for raw in results:
                    job = _process_raw_job(raw)
                    if job and job["hash"] not in seen_hashes:
                        seen_hashes.add(job["hash"])
                        jobs.append(job)
                # Rate-Limit-Respekt — kleines Sleep zwischen Pages
                time.sleep(0.5)

    logger.info("Adzuna: %d Stellen ueber %d Queries", len(jobs), len(queries))
    return jobs


def _process_raw_job(raw: dict) -> Optional[dict]:
    """Mappt eine Adzuna-API-Response auf das PBP-Job-Dict.

    Adzuna-Felder (relevante):
        id, title, description, location.display_name, company.display_name,
        salary_min, salary_max, salary_is_predicted, redirect_url, created
    """
    title = (raw.get("title") or "").strip()
    if not title or len(title) < 5:
        return None
    company = ""
    company_obj = raw.get("company") or {}
    if isinstance(company_obj, dict):
        company = company_obj.get("display_name", "") or ""
    location = ""
    loc_obj = raw.get("location") or {}
    if isinstance(loc_obj, dict):
        location = loc_obj.get("display_name", "") or ""
    url = (raw.get("redirect_url") or "").strip()
    description = (raw.get("description") or fuer_speicher(""))

    # Gehalt — Adzuna liefert Jahres-Brutto wenn vorhanden
    salary_min = raw.get("salary_min")
    salary_max = raw.get("salary_max")
    salary_predicted = bool(raw.get("salary_is_predicted") in (1, "1", True))

    # Job-Hash — Adzuna-ID ist eindeutig
    adzuna_id = str(raw.get("id") or "")
    hash_input = f"adzuna/{adzuna_id}" if adzuna_id else title

    return {
        "hash": stelle_hash("adzuna", hash_input),
        "title": title,
        "company": company or "Unbekannt",
        "location": location,
        "url": url,
        "source": "adzuna",
        "description": description,
        "employment_type": "festanstellung",
        "remote_level": detect_remote_level(f"{title} {location} {description}"),
        "salary_min": int(salary_min) if salary_min is not None else None,
        "salary_max": int(salary_max) if salary_max is not None else None,
        "salary_type": "jaehrlich" if salary_min else None,
        "salary_estimated": 1 if salary_predicted else 0,
        "adzuna_id": adzuna_id,
    }
