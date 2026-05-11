"""Praktikum.de RSS (#590 Aufgabe B.4).

praktikum.de ist die groesste DACH-Plattform fuer Praktika und
Werkstudenten-Stellen. Public RSS pro Kategorie/Suche:

    GET https://www.praktikum.de/rss.xml?suchwort={kw}

Kein Auth. Liefert die juengsten Stellen.
"""

from __future__ import annotations

import logging
import re
from xml.etree import ElementTree as ET

import httpx

from . import detect_remote_level, stelle_hash, make_session

logger = logging.getLogger("bewerbungs_assistent.scraper.praktikum_de")

_BASE = "https://www.praktikum.de/rss.xml"
_TIMEOUT = 12


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2000]


def _matches_keywords(title: str, desc: str, keywords: list) -> bool:
    if not keywords:
        return True
    haystack = f"{title} {desc[:1500]}".lower()
    return any(kw.lower().strip() in haystack for kw in keywords)


def _parse_item(item: ET.Element) -> dict | None:
    def _t(name: str) -> str:
        el = item.find(name)
        return (el.text or "").strip() if el is not None and el.text else ""

    title = _t("title")
    if not title:
        return None
    link = _t("link")
    desc = _strip_html(_t("description"))
    pub = _t("pubDate")
    return {
        "hash": stelle_hash("praktikum_de", f"{link} {title}"),
        "title": title,
        "company": "Nicht angegeben",
        "location": "",  # RSS gibt keinen separaten Ort
        "url": link,
        "source": "praktikum_de",
        "description": desc,
        # Praktikum.de listet hauptsaechlich Praktika/Werkstudent
        "employment_type": "praktikum",
        "remote_level": detect_remote_level(f"{title} {desc[:500]}"),
        "_pub_date": pub,
    }


def search_praktikum_de(params: dict) -> list[dict]:
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", [])
    else:
        keywords = kw_data or []

    primary_kw = keywords[0] if keywords else None
    found: list[dict] = []
    try:
        # v1.7.0-beta.51 (#624 Phase 2): zentraler make_session-Helper
        with make_session(content_type="rss", timeout=_TIMEOUT) as client:
            params_q = {"suchwort": primary_kw} if primary_kw else {}
            r = client.get(_BASE, params=params_q)
            if r.status_code != 200:
                logger.debug("Praktikum.de HTTP %d", r.status_code)
                return []
            try:
                root = ET.fromstring(r.content)
            except ET.ParseError as exc:
                logger.warning("Praktikum.de Parse-Fehler: %s", exc)
                return []
            for item in root.findall(".//item"):
                j = _parse_item(item)
                if not j:
                    continue
                if not _matches_keywords(j["title"], j["description"], keywords):
                    continue
                j.pop("_pub_date", None)
                found.append(j)
    except Exception as exc:
        logger.warning("Praktikum.de Verbindungsfehler: %s", exc)

    logger.info("Praktikum.de: %d Stellen gefunden", len(found))
    return found
