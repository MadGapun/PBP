"""Greenhouse Job Board API (#500).

Greenhouse ist eines der groessten Applicant-Tracking-Systeme. Tausende
Firmen — viele in DACH-Ansiedlung — exponieren ihre Stellen ueber die
oeffentliche Job-Board-API:

    GET https://boards-api.greenhouse.io/v1/boards/{company-slug}/jobs

Kein Auth, kein API-Key, keine Rate-Limit-Header. Antwort ist eine JSON-
Struktur mit ``jobs: [{id, title, location:{name}, absolute_url, content,
updated_at, departments, offices}]``.

Strategie:
    - Eine kuratierte Default-Liste von DACH-relevanten Firmen wird
      jedes Mal abgefragt.
    - Der User kann ueber das Suchkriterium ``greenhouse_companies``
      eigene Slugs hinterlegen.
    - Filter auf Keywords (Titel + Department + content) und Region
      (location.name oder Office-Land/Stadt).

Live-Probe 2026-04-25: 10/36 getesteter Firmen lieferten zusammen
2535 Stellen. Selbst nach Region-Filter "Hamburg" ergibt das oft 5-30
zusaetzliche Treffer pro Lauf — ohne Login, ohne Cookies, ohne Browser.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from . import detect_remote_level, stelle_hash

logger = logging.getLogger("bewerbungs_assistent.scraper.greenhouse")

_BASE_TPL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PBP-Bewerbungs-Assistent)",
    "Accept": "application/json",
}

# Kuratierte Default-Liste, alle live geprueft 2026-04-25.
# Schwerpunkt DACH-Tech-Unternehmen; ergaenzt um internationale, die in
# DE rekrutieren (Datadog/Elastic/Cloudflare/MongoDB/GitLab/Twilio).
DEFAULT_COMPANIES = [
    "n26",
    "celonis",
    "hellofresh",
    "getyourguide",
    "datadog",
    "elastic",
    "cloudflare",
    "mongodb",
    "gitlab",
    "twilio",
]

_MAX_WORKERS = 5
_TIMEOUT = 12


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _location_text(job: dict) -> str:
    parts = []
    loc = job.get("location") or {}
    if isinstance(loc, dict) and loc.get("name"):
        parts.append(loc["name"])
    for office in job.get("offices") or []:
        if isinstance(office, dict):
            for k in ("name", "location"):
                if office.get(k):
                    parts.append(str(office[k]))
    return ", ".join(parts)


def _department_text(job: dict) -> str:
    deps = []
    for d in job.get("departments") or []:
        if isinstance(d, dict) and d.get("name"):
            deps.append(d["name"])
    return ", ".join(deps)


_DACH_CITIES = {
    "hamburg", "berlin", "muenchen", "munich", "frankfurt", "koeln", "cologne",
    "duesseldorf", "duesseldorf", "stuttgart", "leipzig", "hannover", "bremen",
    "nuernberg", "nuremberg", "dortmund", "essen", "dresden",
    "wien", "vienna", "graz", "linz",
    "zuerich", "zurich", "basel", "bern", "geneva",
}
_DACH_BROADER = {
    "germany", "deutschland", "austria", "oesterreich", "switzerland", "schweiz",
    "europe", "european", "eu", "emea", "dach",
}
_REMOTE_TOKENS = ("remote", "anywhere", "worldwide", "global")


def _matches(job: dict, location_text: str, dept_text: str,
             desc_text: str, keywords: list[str], region: str | None) -> bool:
    title = (job.get("title") or "").lower()
    haystack = f"{title} {dept_text.lower()} {desc_text.lower()[:1500]}"

    if keywords:
        if not any(kw.lower().strip() in haystack for kw in keywords):
            return False

    if region:
        loc_l = location_text.lower()
        reg_l = region.lower().strip()
        # Exakter Match (Hamburg in "Hamburg, DE")
        if reg_l in loc_l:
            return True
        # Wenn die Wunschregion eine DACH-Stadt ist, akzeptieren wir auch
        # uebergeordnete Lagen (Germany / Europe / EMEA) und Remote-Stellen.
        if reg_l in _DACH_CITIES:
            if any(tok in loc_l for tok in _DACH_BROADER):
                return True
            if any(tok in loc_l for tok in _REMOTE_TOKENS):
                return True
            if any(tok in title for tok in _REMOTE_TOKENS):
                return True
            return False
        # Sonst nur ueber direkte Treffer
        return False
    return True


def _map(job: dict, slug: str, location_text: str, desc_text: str) -> dict:
    title = job.get("title") or ""
    company = slug.replace("-", " ").title()  # Slug -> lesbarer Firmenname als Fallback
    url = job.get("absolute_url") or ""

    remote = detect_remote_level(f"{title} {location_text} {desc_text[:500]}")

    return {
        "hash": stelle_hash("greenhouse", f"{slug} {job.get('id', '')} {title}"),
        "title": title,
        "company": company,
        "location": location_text,
        "url": url,
        "source": "greenhouse",
        "description": desc_text[:2000],
        "employment_type": "festanstellung",
        "remote_level": remote,
    }


def _fetch_company(client: httpx.Client, slug: str) -> list[dict]:
    """Holt alle Jobs einer Firma. Gibt Roh-Antwort als Liste zurueck."""
    try:
        r = client.get(_BASE_TPL.format(slug=slug))
        if r.status_code != 200:
            logger.debug("Greenhouse %s HTTP %d", slug, r.status_code)
            return []
        return list(r.json().get("jobs") or [])
    except Exception as exc:
        logger.debug("Greenhouse %s Fehler: %s", slug, exc)
        return []


def search_greenhouse(params: dict) -> list[dict]:
    """Sucht Stellen ueber Greenhouse-Job-Boards der konfigurierten Firmen."""
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", [])
        regionen = kw_data.get("regionen", [])
        custom_companies = kw_data.get("greenhouse_companies", [])
    else:
        keywords = kw_data or []
        regionen = []
        custom_companies = []

    region = regionen[0] if regionen else None
    companies = list(dict.fromkeys(custom_companies + DEFAULT_COMPANIES))

    found: list[dict] = []
    with httpx.Client(timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            futures = {pool.submit(_fetch_company, client, c): c for c in companies}
            for fut in as_completed(futures):
                slug = futures[fut]
                jobs = fut.result()
                if not jobs:
                    continue
                for job in jobs:
                    loc_text = _location_text(job)
                    dept_text = _department_text(job)
                    desc_text = _strip_html(job.get("content") or "")
                    if not _matches(job, loc_text, dept_text, desc_text, keywords, region):
                        continue
                    found.append(_map(job, slug, loc_text, desc_text))

    logger.info("Greenhouse: %d Stellen aus %d Firmen gefunden", len(found), len(companies))
    return found
