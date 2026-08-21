"""Remotive Remote-Jobs (#590 Aufgabe B.5).

Remotive bietet eine kuratierte Remote-Job-Liste. Public REST API:

    GET https://remotive.com/api/remote-jobs?search={kw}

Kein Auth. Antwort: {jobs: [{title, company_name, candidate_required_location,
url, description, ...}]}.
"""

from __future__ import annotations

import logging
import re

import httpx

from . import detect_remote_level, stelle_hash, make_session
from .textgrenzen import fuer_speicher

logger = logging.getLogger("bewerbungs_assistent.scraper.remotive")

_BASE = "https://remotive.com/api/remote-jobs"
_TIMEOUT = 12


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return fuer_speicher(text)


def _matches(title: str, location: str, desc: str, keywords: list) -> bool:
    if not keywords:
        return True
    haystack = f"{title} {location} {desc[:1500]}".lower()
    return any(kw.lower().strip() in haystack for kw in keywords)


def _map(job: dict) -> dict | None:
    title = job.get("title") or ""
    if not title:
        return None
    company = job.get("company_name") or "Nicht angegeben"
    url = job.get("url") or ""
    location = job.get("candidate_required_location") or "Remote"
    desc = _strip_html(job.get("description") or "")
    job_id = job.get("id") or url
    job_type = (job.get("job_type") or "").lower()
    if "intern" in job_type:
        emp = "praktikum"
    elif "freelance" in job_type or "contract" in job_type:
        emp = "freelance"
    elif "part" in job_type or "teilzeit" in job_type:
        emp = "teilzeit"
    else:
        emp = "festanstellung"
    return {
        "hash": stelle_hash("remotive", f"{company} {job_id} {title}"),
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "source": "remotive",
        "description": desc,
        "employment_type": emp,
        "remote_level": "remote",
    }


def search_remotive(params: dict) -> list[dict]:
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", [])
    else:
        keywords = kw_data or []

    primary_kw = keywords[0] if keywords else None
    found: list[dict] = []
    try:
        # v1.7.0-beta.51 (#624 Phase 2): zentraler make_session-Helper
        with make_session(content_type="json", timeout=_TIMEOUT) as client:
            params_q = {"search": primary_kw} if primary_kw else {}
            r = client.get(_BASE, params=params_q)
            if r.status_code != 200:
                logger.debug("Remotive HTTP %d", r.status_code)
                return []
            data = r.json()
            items = data.get("jobs") or []
            for raw in items:
                j = _map(raw)
                if not j:
                    continue
                if not _matches(
                    j["title"], j["location"], j["description"], keywords
                ):
                    continue
                found.append(j)
    except Exception as exc:
        logger.warning("Remotive Verbindungsfehler: %s", exc)

    logger.info("Remotive: %d Stellen gefunden", len(found))
    return found
