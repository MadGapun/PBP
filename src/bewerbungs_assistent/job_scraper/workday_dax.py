"""Workday-DAX-Cluster (#590 Aufgabe B.3).

Viele DAX/MDAX-Konzerne nutzen Workday als ATS. Public-JSON-Endpoint
pro Tenant:

    POST https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs

Body: `{"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}`
liefert die ersten 20 Stellen pro Career-Site.

PBP haelt eine kuratierte Liste typischer Konzern-Tenants. Jeder Eintrag:
    (firma, tenant, wd-host, site)

Die Konzern-Liste ist absichtlich begrenzt — nicht jede Firma ist auf
Workday und nicht jeder Tenant nutzt das gleiche Schema. Der User kann
ueber `workday_firmen` eigene Eintraege anhaengen
(Format: 'firma|tenant|wd|site').
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from . import detect_remote_level, stelle_hash

logger = logging.getLogger("bewerbungs_assistent.scraper.workday_dax")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PBP-Bewerbungs-Assistent)",
    "Accept": "application/json",
    "Content-Type": "application/json",
}
_MAX_WORKERS = 5
_TIMEOUT = 15
_PAGE_SIZE = 20

# Kuratierte Default-Liste DACH-Konzerne mit Workday-ATS.
# Tupel: (firma, tenant, wd-host, site).  Live-Probe-Hinweise
# unter "notiz". Der User kann das ueber `workday_firmen` erweitern.
DEFAULT_FIRMEN: list[tuple[str, str, str, str]] = [
    ("Siemens", "siemens", "wd5", "siemens"),
    ("SAP", "sap", "wd3", "SAPCareers"),
    ("Bosch", "bosch", "wd1", "BoschGroup"),
    ("Vitesco", "vitesco", "wd3", "Vitesco_External_Career_Site"),
    ("Continental", "continental", "wd3", "Conti_External_Career_Site"),
    ("Knorr-Bremse", "knorr-bremse", "wd3", "knorr-bremse"),
    ("Heidelberger Druckmaschinen", "heidelberg",
     "wd3", "HeidelbergCareers"),
    ("KraussMaffei", "kraussmaffei", "wd3", "krauss-maffei"),
    ("ZF", "zf", "wd3", "ZF_Friedrichshafen_AG"),
    ("Schaeffler", "schaeffler", "wd3", "Schaeffler"),
]


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2000]


def _build_url(tenant: str, wd: str, site: str) -> str:
    return (
        f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/"
        f"{tenant}/{site}/jobs"
    )


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
        return False
    return True


def _parse_postings(data: dict, firma: str, tenant: str,
                     wd: str, site: str) -> list[dict]:
    """Maps Workday-Antwort auf das PBP-Schema."""
    out: list[dict] = []
    for p in data.get("jobPostings") or []:
        title = p.get("title") or ""
        if not title:
            continue
        ext_path = p.get("externalPath") or ""
        url = (
            f"https://{tenant}.{wd}.myworkdayjobs.com/{site}{ext_path}"
            if ext_path else
            f"https://{tenant}.{wd}.myworkdayjobs.com/{site}"
        )
        location_text = p.get("locationsText") or p.get("location") or ""
        # bulletField → kann u.a. "Posted X days ago" sein (uninteressant)
        desc = ""  # Workday liefert in der Listenansicht keine Beschreibung
        out.append({
            "hash": stelle_hash("workday_dax",
                                f"{tenant} {ext_path or title}"),
            "title": title,
            "company": firma,
            "location": location_text,
            "url": url,
            "source": "workday_dax",
            "description": desc,
            "employment_type": "festanstellung",
            "remote_level": detect_remote_level(f"{title} {location_text}"),
        })
    return out


def _fetch_firma(client: httpx.Client,
                 firma: str, tenant: str, wd: str, site: str,
                 search_text: str) -> list[dict]:
    url = _build_url(tenant, wd, site)
    body = {
        "appliedFacets": {},
        "limit": _PAGE_SIZE,
        "offset": 0,
        "searchText": search_text or "",
    }
    try:
        r = client.post(url, json=body)
        if r.status_code != 200:
            logger.debug("Workday %s HTTP %d", tenant, r.status_code)
            return []
        try:
            data = r.json()
        except Exception:
            logger.debug("Workday %s JSON-Fehler", tenant)
            return []
    except Exception as exc:
        logger.debug("Workday %s Fehler: %s", tenant, exc)
        return []
    return _parse_postings(data, firma, tenant, wd, site)


def _parse_user_entry(s: str) -> tuple[str, str, str, str] | None:
    """Erwartet 'firma|tenant|wd|site'."""
    parts = s.split("|")
    if len(parts) != 4:
        return None
    firma, tenant, wd, site = (p.strip() for p in parts)
    if not (tenant and wd and site):
        return None
    return (firma or tenant.title(), tenant, wd, site)


def search_workday_dax(params: dict) -> list[dict]:
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", [])
        regionen = kw_data.get("regionen", [])
        custom_raw = kw_data.get("workday_firmen", [])
    else:
        keywords = kw_data or []
        regionen = []
        custom_raw = []

    region = regionen[0] if regionen else None
    primary_kw = keywords[0] if keywords else ""

    custom: list[tuple[str, str, str, str]] = []
    for s in custom_raw or []:
        parsed = _parse_user_entry(s)
        if parsed:
            custom.append(parsed)

    firmen: list[tuple[str, str, str, str]] = list(
        dict.fromkeys(custom + DEFAULT_FIRMEN)
    )

    found: list[dict] = []
    with httpx.Client(timeout=_TIMEOUT, headers=_HEADERS,
                       follow_redirects=True) as client:
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            futures = {
                pool.submit(_fetch_firma, client, *f, primary_kw): f
                for f in firmen
            }
            for fut in as_completed(futures):
                jobs = fut.result()
                for j in jobs:
                    if not _matches(
                        j["title"], j["location"], j["description"],
                        keywords, region
                    ):
                        continue
                    found.append(j)

    logger.info("Workday-DAX: %d Stellen aus %d Firmen gefunden",
                len(found), len(firmen))
    return found
