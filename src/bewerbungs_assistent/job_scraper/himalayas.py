"""Himalayas Remote-Jobs (#590 Aufgabe B.5).

Himalayas (https://himalayas.app) listet Remote-Stellen weltweit. Public
JSON-Endpoint, kein Auth.

    GET https://himalayas.app/jobs/api?country=DE

Liefert pro Country-Filter eine Liste von Remote-Jobs. PBP nutzt das fuer
Tech-Junior/Senior-Profile, die zusaetzlich Remote-Optionen sehen wollen.
"""

from __future__ import annotations

import logging
import re

import httpx

from . import detect_remote_level, stelle_hash, make_session

logger = logging.getLogger("bewerbungs_assistent.scraper.himalayas")

_BASE = "https://himalayas.app/jobs/api"
_TIMEOUT = 12
_MAX_PAGES = 3


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2000]


def _matches(title: str, desc: str, keywords: list) -> bool:
    if not keywords:
        return True
    haystack = f"{title} {desc[:1500]}".lower()
    return any(kw.lower().strip() in haystack for kw in keywords)


def _map(job: dict) -> dict | None:
    title = job.get("title") or job.get("name") or ""
    if not title:
        return None
    company = (
        (job.get("companyName") or job.get("company") or "Nicht angegeben")
        if isinstance(job.get("company"), str)
        else (job.get("company") or {}).get("name")
        or job.get("companyName")
        or "Nicht angegeben"
    )
    url = job.get("applicationLink") or job.get("url") or ""
    desc = _strip_html(job.get("description") or "")
    job_id = job.get("guid") or job.get("id") or job.get("slug") or url
    job_type = (job.get("seniority") or job.get("employmentType") or "").lower()
    if "intern" in job_type:
        emp = "praktikum"
    elif "freelance" in job_type or "contract" in job_type:
        emp = "freelance"
    else:
        emp = "festanstellung"
    return {
        "hash": stelle_hash("himalayas", f"{company} {job_id} {title}"),
        "title": title,
        "company": company,
        "location": "Remote",
        "url": url or f"https://himalayas.app/jobs/{job.get('slug', '')}",
        "source": "himalayas",
        "description": desc,
        "employment_type": emp,
        "remote_level": "remote",
    }


def search_himalayas(params: dict) -> list[dict]:
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", [])
    else:
        keywords = kw_data or []

    found: list[dict] = []
    seen: set = set()
    try:
        # v1.7.0-beta.51 (#624 Phase 2): zentraler make_session-Helper
        with make_session(content_type="json", timeout=_TIMEOUT) as client:
            for page in range(1, _MAX_PAGES + 1):
                try:
                    r = client.get(_BASE, params={
                        "country": "DE", "page": page,
                    })
                except Exception as exc:
                    logger.debug("Himalayas page %d Fehler: %s", page, exc)
                    break
                if r.status_code != 200:
                    logger.debug("Himalayas HTTP %d", r.status_code)
                    break
                try:
                    data = r.json()
                except Exception:
                    break
                items = (
                    data.get("jobs")
                    if isinstance(data, dict)
                    else data
                ) or []
                if not items:
                    break
                for raw in items:
                    j = _map(raw)
                    if not j:
                        continue
                    if j["hash"] in seen:
                        continue
                    if not _matches(j["title"], j["description"], keywords):
                        continue
                    seen.add(j["hash"])
                    found.append(j)
                if len(items) < 25:
                    break
    except Exception as exc:
        logger.warning("Himalayas Verbindungsfehler: %s", exc)

    logger.info("Himalayas: %d Stellen gefunden", len(found))
    return found
