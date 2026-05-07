"""Berufsstart.de RSS (#590 Aufgabe B.4).

berufsstart.de bedient den Karriere-Einstieg fuer Studenten und
Absolventen. Public RSS-Feeds:

    GET https://www.berufsstart.de/jobs/rss

Filterung clientseitig nach Keyword + Region.
"""

from __future__ import annotations

import logging
import re
from xml.etree import ElementTree as ET

import httpx

from . import detect_remote_level, stelle_hash

logger = logging.getLogger("bewerbungs_assistent.scraper.berufsstart")

_BASE = "https://www.berufsstart.de/jobs/rss"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PBP-Bewerbungs-Assistent)",
    "Accept": "application/rss+xml, application/xml",
}
_TIMEOUT = 12


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2000]


def _matches(title: str, desc: str, keywords: list,
              region: str | None) -> bool:
    haystack = f"{title} {desc[:1500]}".lower()
    if keywords:
        if not any(kw.lower().strip() in haystack for kw in keywords):
            return False
    if region:
        if region.lower() in haystack:
            return True
        return False
    return True


def _parse_item(item: ET.Element) -> dict | None:
    def _t(name: str) -> str:
        el = item.find(name)
        return (el.text or "").strip() if el is not None and el.text else ""

    title = _t("title")
    if not title:
        return None
    link = _t("link")
    desc = _strip_html(_t("description"))
    return {
        "hash": stelle_hash("berufsstart", f"{link} {title}"),
        "title": title,
        "company": "Nicht angegeben",
        "location": "",
        "url": link,
        "source": "berufsstart",
        "description": desc,
        # Berufsstart deckt Trainee/Junior-Tier ab
        "employment_type": "festanstellung",
        "remote_level": detect_remote_level(f"{title} {desc[:500]}"),
    }


def search_berufsstart(params: dict) -> list[dict]:
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", [])
        regionen = kw_data.get("regionen", [])
    else:
        keywords = kw_data or []
        regionen = []
    region = regionen[0] if regionen else None

    found: list[dict] = []
    try:
        with httpx.Client(timeout=_TIMEOUT, headers=_HEADERS,
                          follow_redirects=True) as client:
            r = client.get(_BASE)
            if r.status_code != 200:
                logger.debug("Berufsstart HTTP %d", r.status_code)
                return []
            try:
                root = ET.fromstring(r.content)
            except ET.ParseError as exc:
                logger.warning("Berufsstart Parse-Fehler: %s", exc)
                return []
            for item in root.findall(".//item"):
                j = _parse_item(item)
                if not j:
                    continue
                if not _matches(j["title"], j["description"], keywords, region):
                    continue
                found.append(j)
    except Exception as exc:
        logger.warning("Berufsstart Verbindungsfehler: %s", exc)

    logger.info("Berufsstart: %d Stellen gefunden", len(found))
    return found
