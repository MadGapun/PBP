"""Workable Public Postings (#590 Aufgabe A.2).

Workable ist internationaler ATS, viele KMUs nutzen ihn fuer
Public-Postings:

    GET https://apply.workable.com/api/v1/widget/accounts/{firma}

Public Widget API, kein Auth. Antwort enthaelt `jobs: [{title, location:
{city, country}, url, full_title, shortcode, ...}]`.

Strategie:
    - Kuratierte Default-Liste DACH-Workable-Kunden
    - User kann ueber `workable_firmen`-Suchkriterium eigene Slugs
      hinterlegen
    - Pro Firma alle Stellen ziehen, dann clientseitig nach Keywords
      + Region filtern
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from . import detect_remote_level, stelle_hash, make_session

logger = logging.getLogger("bewerbungs_assistent.scraper.workable")

_BASE_TPL = "https://apply.workable.com/api/v1/widget/accounts/{firma}"
_MAX_WORKERS = 5
_TIMEOUT = 12

# Kuratierte Default-Liste — Workable-Kunden mit Aktivitaet im DACH-Markt.
DEFAULT_COMPANIES = [
    "workable",
    "tier",
    "delivery-hero",
    "blinkist",
    "kontist",
    "tomorrow",
    "shore",
    "celonis-tech",
]


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2000]


def _matches(title: str, location: str, desc: str,
             keywords: list, region: str | None) -> bool:
    haystack = f"{title} {location} {desc[:1500]}".lower()
    if keywords:
        if not any(kw.lower().strip() in haystack for kw in keywords):
            return False
    if region:
        if region.lower() in (location or "").lower():
            return True
        if region.lower() in haystack:
            return True
        if any(tok in haystack for tok in ("remote", "homeoffice", "anywhere")):
            return True
        return False
    return True


def _location_text(job: dict) -> str:
    loc = job.get("location") or {}
    if isinstance(loc, dict):
        parts = [loc.get("city"), loc.get("region"), loc.get("country")]
        return ", ".join(p for p in parts if p)
    if isinstance(loc, str):
        return loc
    return ""


def _map(job: dict, firma: str) -> dict | None:
    title = job.get("title") or job.get("full_title") or ""
    if not title:
        return None
    location = _location_text(job)
    shortcode = job.get("shortcode") or job.get("id") or ""
    url = (
        job.get("url")
        or f"https://apply.workable.com/{firma}/j/{shortcode}/"
    )
    desc = _strip_html(job.get("description") or job.get("requirements") or "")
    job_type = (job.get("type") or "").lower()
    if "intern" in job_type or "praktik" in job_type:
        emp = "praktikum"
    elif "freelance" in job_type or "contract" in job_type:
        emp = "freelance"
    elif "part" in job_type or "teilzeit" in job_type:
        emp = "teilzeit"
    else:
        emp = "festanstellung"
    return {
        "hash": stelle_hash("workable", f"{firma} {shortcode} {title}"),
        "title": title,
        "company": firma.replace("-", " ").title(),
        "location": location,
        "url": url,
        "source": "workable",
        "description": desc,
        "employment_type": emp,
        "remote_level": detect_remote_level(
            f"{title} {location} {desc[:500]}"
        ),
    }


def _fetch_firma(client: httpx.Client, firma: str) -> list[dict]:
    try:
        r = client.get(_BASE_TPL.format(firma=firma))
        if r.status_code != 200:
            logger.debug("Workable %s HTTP %d", firma, r.status_code)
            return []
        data = r.json()
        # Workable Widget API liefert {jobs: [...]} oder {accounts: [...]}
        jobs = data.get("jobs") or []
        if not jobs and isinstance(data, dict):
            # manchmal verschachtelt unter `accounts[].jobs`
            for acc in data.get("accounts") or []:
                if isinstance(acc, dict):
                    jobs.extend(acc.get("jobs") or [])
        return jobs
    except Exception as exc:
        logger.debug("Workable %s Fehler: %s", firma, exc)
        return []


def search_workable(params: dict) -> list[dict]:
    """Sucht Stellen ueber Workable-Public-Postings der konfigurierten Firmen."""
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", [])
        regionen = kw_data.get("regionen", [])
        custom = kw_data.get("workable_firmen", [])
    else:
        keywords = kw_data or []
        regionen = []
        custom = []

    region = regionen[0] if regionen else None
    firmen = list(dict.fromkeys(custom + DEFAULT_COMPANIES))

    found: list[dict] = []
    # v1.7.0-beta.51 (#624 Phase 2): zentraler make_session-Helper
    with make_session(content_type="json", timeout=_TIMEOUT) as client:
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            futures = {pool.submit(_fetch_firma, client, f): f for f in firmen}
            for fut in as_completed(futures):
                firma = futures[fut]
                jobs = fut.result()
                for raw in jobs:
                    j = _map(raw, firma)
                    if not j:
                        continue
                    if not _matches(
                        j["title"], j["location"], j["description"],
                        keywords, region
                    ):
                        continue
                    found.append(j)

    logger.info("Workable: %d Stellen aus %d Firmen gefunden",
                len(found), len(firmen))
    return found
