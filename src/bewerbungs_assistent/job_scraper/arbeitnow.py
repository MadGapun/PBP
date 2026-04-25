"""Arbeitnow Job Board API (#500).

Arbeitnow.com ist ein freier deutscher Job-Aggregator mit offener REST-API
(``https://www.arbeitnow.com/api/job-board-api``). Kein API-Key, keine
Authentifizierung, kein Rate-Limit-Header dokumentiert. Liefert pro Seite
100 Stellen mit ``next``-Link fuer Paginierung.

Felder pro Stelle:
    slug, company_name, title, description (HTML), remote (bool),
    url, tags, job_types, location, created_at (unix timestamp).

Das Modul filtert die Treffer nach den vom User konfigurierten Keywords
und Regionen — die API selbst kennt keinen serverseitigen Filter ausser
``search``. Wir nutzen ``search`` mit dem ersten Keyword, ziehen 1-3
Seiten und prufen die Stellen-Strings clientseitig gegen die volle
Keyword-Liste plus die Wunsch-Region.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote_plus

import httpx

from . import detect_remote_level, stelle_hash

logger = logging.getLogger("bewerbungs_assistent.scraper.arbeitnow")

_BASE = "https://www.arbeitnow.com/api/job-board-api"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PBP-Bewerbungs-Assistent)",
    "Accept": "application/json",
}
_MAX_PAGES = 3  # 100 jobs/page → bis zu 300 Stellen pro Lauf


def _clean_html(html: str) -> str:
    """Reduziert das Description-HTML auf reinen Text fuer die DB."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2000]


def _matches(job: dict, keywords: list[str], region: str | None) -> bool:
    """Prueft, ob die Stelle zu den Suchkriterien passt.

    Region-Match ist tolerant: wenn die Region leer ist, akzeptieren wir
    alles. Sonst muss sie in ``location``, ``description`` oder ``tags``
    vorkommen — Arbeitnow taggt Remote-Stellen oft ohne Stadt.
    """
    title = (job.get("title") or "").lower()
    company = (job.get("company_name") or "").lower()
    desc = (job.get("description") or "").lower()
    tags = " ".join(job.get("tags") or []).lower()
    haystack = f"{title} {company} {desc} {tags}"

    if keywords:
        if not any(kw.lower().strip() in haystack for kw in keywords):
            return False

    if region:
        location = (job.get("location") or "").lower()
        if region.lower() in location:
            return True
        if job.get("remote"):
            return True  # Remote-Stellen sind ortsunabhaengig
        # akzeptiere auch wenn Region in tags steht
        if region.lower() in tags:
            return True
        return False

    return True


def _map(job: dict) -> dict:
    """Mappt eine Arbeitnow-Antwort auf das PBP-Job-Schema."""
    title = job.get("title") or ""
    company = job.get("company_name") or "Nicht angegeben"
    location = job.get("location") or ""
    url = job.get("url") or ""
    desc_text = _clean_html(job.get("description") or "")

    if job.get("remote"):
        remote = "remote"
    else:
        remote = detect_remote_level(f"{title} {location} {desc_text[:500]}")

    job_types = job.get("job_types") or []
    if any("contract" in t.lower() or "freelance" in t.lower() for t in job_types):
        employment = "freelance"
    elif any("intern" in t.lower() or "praktik" in t.lower() for t in job_types):
        employment = "praktikum"
    else:
        employment = "festanstellung"

    return {
        "hash": stelle_hash("arbeitnow", f"{company} {title} {url}"),
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "source": "arbeitnow",
        "description": desc_text,
        "employment_type": employment,
        "remote_level": remote,
    }


def _fetch_page(client: httpx.Client, search: str | None, page: int) -> dict[str, Any]:
    """Holt eine einzelne Seite vom Arbeitnow-API."""
    params = {"page": page}
    if search:
        params["search"] = search
    r = client.get(_BASE, params=params)
    r.raise_for_status()
    return r.json()


def search_arbeitnow(params: dict) -> list[dict]:
    """Sucht Stellen ueber arbeitnow.com.

    Strategie:
        1. Erstes Keyword als ``search``-Parameter an die API geben.
        2. Bis zu ``_MAX_PAGES`` Seiten ziehen.
        3. Clientseitig nach allen Keywords und der ersten Wunschregion
           filtern.
    """
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", [])
        regionen = kw_data.get("regionen", [])
    else:
        keywords = kw_data or []
        regionen = []

    region = regionen[0] if regionen else None
    primary = keywords[0] if keywords else None

    jobs: list[dict] = []
    seen_slugs: set[str] = set()

    try:
        with httpx.Client(timeout=15, headers=_HEADERS, follow_redirects=True) as client:
            for page in range(1, _MAX_PAGES + 1):
                try:
                    data = _fetch_page(client, primary, page)
                except httpx.HTTPStatusError as exc:
                    logger.warning("Arbeitnow HTTP %s auf Seite %d", exc.response.status_code, page)
                    break
                except Exception as exc:
                    logger.warning("Arbeitnow Fehler auf Seite %d: %s", page, exc)
                    break

                items = data.get("data") or []
                if not items:
                    break

                for raw in items:
                    slug = raw.get("slug")
                    if slug and slug in seen_slugs:
                        continue
                    if slug:
                        seen_slugs.add(slug)
                    if not _matches(raw, keywords, region):
                        continue
                    jobs.append(_map(raw))

                links = data.get("links") or {}
                if not links.get("next"):
                    break

    except Exception as exc:
        logger.warning("Arbeitnow Verbindungsfehler: %s", exc)

    logger.info("Arbeitnow: %d Stellen gefunden", len(jobs))
    return jobs
