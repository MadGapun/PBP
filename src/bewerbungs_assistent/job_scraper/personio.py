"""Personio Public Job Board (#590 Aufgabe A.1).

Personio ist DACH-spezifischer ATS, sehr verbreitet im KMU-Bereich.
Jede Firma mit Personio-Account exponiert ihre Stellen oeffentlich
ueber:

    GET https://{firma}.jobs.personio.de/xml

Das ist ein RSS/Atom-Feed mit allen aktiven Stellen. Kein Auth, kein
API-Key, kein Rate-Limit dokumentiert.

Strategie:
    - Kuratierte Default-Liste DACH-Mittelstand-Firmen
    - User kann ueber `personio_firmen`-Suchkriterium eigene Firmen
      hinterlegen
    - Pro Firma alle Stellen ziehen, dann clientseitig nach
      Keywords + Region filtern

Live-Probe Anforderung an die Default-Liste: Stellen quer durch alle
Branchen + Skill-Level (vom Azubi bis Geschaeftsfuehrer). Personio ist
fuer Service-/Pflege-/Hotel-/Einzelhandel oft die einzige zentrale
Quelle (User-Vorgabe: PBP nicht nur fuer High-Performer).
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree as ET

import httpx

from . import detect_remote_level, stelle_hash, make_session
from .textgrenzen import fuer_speicher

logger = logging.getLogger("bewerbungs_assistent.scraper.personio")

_BASE_TPL = "https://{firma}.jobs.personio.de/xml"
_MAX_WORKERS = 5
_TIMEOUT = 12

# Kuratierte Default-Liste DACH-Mittelstand. Mischung aus Tech, Service,
# Pflege, Handel — bewusst breit gestreut.
DEFAULT_COMPANIES = [
    "personio",          # Personio selbst
    "scout24",
    "mister-spex",
    "kontist",
    "raisin",
    "depot-online",
    "zalando-x",
    "n26-jobs",
    "doctolib-de",
    "freelancermap",
    "trade-republic",
]


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return fuer_speicher(text)


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
        # Remote-Stellen ortsunabhaengig akzeptieren
        if any(tok in haystack for tok in ("remote", "homeoffice", "anywhere")):
            return True
        return False
    return True


def _parse_position(pos_elem: ET.Element, firma: str) -> dict | None:
    """Parst ein <position>-Element des Personio-XML."""

    def _text(name: str) -> str:
        el = pos_elem.find(name)
        return (el.text or "").strip() if el is not None and el.text else ""

    title = _text("name")
    if not title:
        # Fallback auf <title>
        title = _text("title")
    if not title:
        return None

    description_parts = []
    for desc_tag in ("description", "jobDescriptions"):
        descs = pos_elem.findall(f".//{desc_tag}")
        for d in descs:
            txt = "".join(d.itertext())
            if txt.strip():
                description_parts.append(txt)
    description = _strip_html(" ".join(description_parts))

    location = _text("office") or _text("location")
    department = _text("department")
    schedule = (_text("schedule") or "").lower()
    employment_type = (_text("employmentType") or "").lower()
    pos_id = _text("id") or _text("subcompany") or title

    if "intern" in schedule or "praktik" in schedule \
            or "intern" in employment_type:
        emp = "praktikum"
    elif "freelance" in employment_type or "contract" in employment_type:
        emp = "freelance"
    elif "part" in schedule or "teilzeit" in schedule:
        emp = "teilzeit"
    else:
        emp = "festanstellung"

    url = (
        f"https://{firma}.jobs.personio.de/job/{pos_id}"
        if pos_id else f"https://{firma}.jobs.personio.de/"
    )

    return {
        "hash": stelle_hash("personio", f"{firma} {pos_id} {title}"),
        "title": title,
        "company": firma.replace("-", " ").title(),
        "location": location,
        "url": url,
        "source": "personio",
        "description": description,
        "employment_type": emp,
        "remote_level": detect_remote_level(
            f"{title} {location} {description[:500]}"
        ),
        "_department": department,
    }


def _fetch_firma(client: httpx.Client, firma: str) -> list[dict]:
    try:
        r = client.get(_BASE_TPL.format(firma=firma))
        if r.status_code != 200:
            logger.debug("Personio %s HTTP %d", firma, r.status_code)
            return []
        try:
            tree = ET.fromstring(r.content)
        except ET.ParseError as exc:
            logger.debug("Personio %s Parse-Fehler: %s", firma, exc)
            return []
        return [
            j for p in tree.findall(".//position")
            if (j := _parse_position(p, firma)) is not None
        ]
    except Exception as exc:
        logger.debug("Personio %s Fehler: %s", firma, exc)
        return []


def search_personio(params: dict) -> list[dict]:
    """Sucht Stellen ueber Personio-Job-Boards der konfigurierten Firmen."""
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", [])
        regionen = kw_data.get("regionen", [])
        custom = kw_data.get("personio_firmen", [])
    else:
        keywords = kw_data or []
        regionen = []
        custom = []

    region = regionen[0] if regionen else None
    firmen = list(dict.fromkeys(custom + DEFAULT_COMPANIES))

    found: list[dict] = []
    # v1.7.0-beta.51 (#624 Phase 2): zentraler make_session-Helper
    with make_session(content_type="xml", timeout=_TIMEOUT) as client:
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            futures = {pool.submit(_fetch_firma, client, f): f for f in firmen}
            for fut in as_completed(futures):
                jobs = fut.result()
                for job in jobs:
                    if not _matches(
                        job["title"], job["location"], job["description"],
                        keywords, region
                    ):
                        continue
                    job.pop("_department", None)
                    found.append(job)

    logger.info("Personio: %d Stellen aus %d Firmen gefunden",
                len(found), len(firmen))
    return found
