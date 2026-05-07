"""StudentJob.de RSS (#590 Aufgabe B.4).

StudentJob.de listet Studenten- und Werkstudenten-Stellen. Public RSS:

    GET https://www.studentjob.de/rss/jobs

Liefert juengste Stellen. Filterung clientseitig.
"""

from __future__ import annotations

import logging
import re
from xml.etree import ElementTree as ET

import httpx

from . import detect_remote_level, stelle_hash

logger = logging.getLogger("bewerbungs_assistent.scraper.studentjob")

_BASE = "https://www.studentjob.de/rss/jobs"
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
        "hash": stelle_hash("studentjob", f"{link} {title}"),
        "title": title,
        "company": "Nicht angegeben",
        "location": "",
        "url": link,
        "source": "studentjob",
        "description": desc,
        "employment_type": "werkstudent",
        "remote_level": detect_remote_level(f"{title} {desc[:500]}"),
    }


def search_studentjob(params: dict) -> list[dict]:
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
                logger.debug("StudentJob HTTP %d", r.status_code)
                return []
            try:
                root = ET.fromstring(r.content)
            except ET.ParseError as exc:
                logger.warning("StudentJob Parse-Fehler: %s", exc)
                return []
            for item in root.findall(".//item"):
                j = _parse_item(item)
                if not j:
                    continue
                if not _matches(j["title"], j["description"], keywords, region):
                    continue
                found.append(j)
    except Exception as exc:
        logger.warning("StudentJob Verbindungsfehler: %s", exc)

    logger.info("StudentJob: %d Stellen gefunden", len(found))
    return found
