"""Meinestadt.de Jobs RSS (#590 Aufgabe A.4).

meinestadt.de ist eine regionale DACH-Stellenseite mit Schwerpunkt
**Service-, Trade- und Pflege-Berufe** (Kassierer, Hotel, Gastro,
Pflege, Handwerk). Diese Stellen sind bei JobSpy/LinkedIn massiv
unterrepraesentiert — meinestadt.de schliesst die Luecke.

User-Vorgabe (#590): „PBP wird nicht nur fuer mich gebaut, sondern
auch fuer Studenten, Kassiererinnen oder Pfleger".

API:
    GET https://www.meinestadt.de/{stadt}/jobs/rss?w={keyword}

Liefert RSS 2.0 mit den letzten Stellen pro Stadt. Kein Auth.

Strategie:
    - Region aus den Suchkriterien lesen, in eine Stadt mappen
    - Mit erstem Keyword RSS holen, fallback ohne Keyword
    - Kein Multi-Threading noetig — eine Region pro Lauf
"""

from __future__ import annotations

import logging
import re
from xml.etree import ElementTree as ET

import httpx

from . import detect_remote_level, stelle_hash
from .textgrenzen import fuer_speicher

logger = logging.getLogger("bewerbungs_assistent.scraper.meinestadt")

_BASE_TPL = "https://www.meinestadt.de/{stadt}/jobs/rss"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PBP-Bewerbungs-Assistent)",
    "Accept": "application/rss+xml, application/xml",
}
_TIMEOUT = 12

# Region-zu-Slug-Mapping fuer die haeufigsten DACH-Staedte. URL-Slug
# muss exakt dem Stadtnamen auf meinestadt.de entsprechen.
_REGION_SLUGS = {
    "berlin": "berlin",
    "hamburg": "hamburg",
    "muenchen": "muenchen",
    "münchen": "muenchen",
    "munich": "muenchen",
    "koeln": "koeln",
    "köln": "koeln",
    "cologne": "koeln",
    "frankfurt": "frankfurt-am-main",
    "stuttgart": "stuttgart",
    "duesseldorf": "duesseldorf",
    "düsseldorf": "duesseldorf",
    "dortmund": "dortmund",
    "essen": "essen",
    "leipzig": "leipzig",
    "bremen": "bremen",
    "dresden": "dresden",
    "hannover": "hannover",
    "nuernberg": "nuernberg",
    "nürnberg": "nuernberg",
    "duisburg": "duisburg",
    "bochum": "bochum",
}


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return fuer_speicher(text)


def _resolve_stadt(region: str | None) -> str | None:
    if not region:
        return None
    slug = _REGION_SLUGS.get(region.lower().strip())
    return slug


def _matches_keywords(title: str, desc: str, keywords: list) -> bool:
    if not keywords:
        return True
    haystack = f"{title} {desc[:1500]}".lower()
    return any(kw.lower().strip() in haystack for kw in keywords)


def _parse_item(item: ET.Element, stadt: str) -> dict | None:
    def _text(name: str) -> str:
        el = item.find(name)
        return (el.text or "").strip() if el is not None and el.text else ""

    title = _text("title")
    if not title:
        return None
    link = _text("link")
    desc = _strip_html(_text("description"))
    pub_date = _text("pubDate")
    return {
        "hash": stelle_hash("meinestadt", f"{stadt} {link} {title}"),
        "title": title,
        "company": "Nicht angegeben",  # RSS gibt keine separaten Firmenfelder
        "location": stadt.replace("-", " ").title(),
        "url": link,
        "source": "meinestadt",
        "description": desc,
        "employment_type": "festanstellung",  # Default — RSS gibt keinen Typ
        "remote_level": detect_remote_level(f"{title} {desc[:500]}"),
        "_pub_date": pub_date,
    }


def search_meinestadt(params: dict) -> list[dict]:
    """Sucht Stellen via meinestadt.de-RSS-Feed der gewaehlten Region."""
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", [])
        regionen = kw_data.get("regionen", [])
    else:
        keywords = kw_data or []
        regionen = []

    region = regionen[0] if regionen else None
    stadt = _resolve_stadt(region)
    if not stadt:
        logger.info(
            "Meinestadt: keine bekannte Stadt fuer Region '%s' — "
            "uebersprungen (unterstuetzt: %s)",
            region, ", ".join(sorted(set(_REGION_SLUGS.values())))
        )
        return []

    url = _BASE_TPL.format(stadt=stadt)
    primary_kw = keywords[0] if keywords else None
    found: list[dict] = []

    try:
        with httpx.Client(timeout=_TIMEOUT, headers=_HEADERS,
                          follow_redirects=True) as client:
            params_q = {"w": primary_kw} if primary_kw else {}
            r = client.get(url, params=params_q)
            if r.status_code != 200:
                logger.warning("Meinestadt HTTP %s fuer %s", r.status_code, stadt)
                return []
            try:
                root = ET.fromstring(r.content)
            except ET.ParseError as exc:
                logger.warning("Meinestadt Parse-Fehler: %s", exc)
                return []
            for item in root.findall(".//item"):
                j = _parse_item(item, stadt)
                if not j:
                    continue
                if not _matches_keywords(j["title"], j["description"], keywords):
                    continue
                j.pop("_pub_date", None)
                found.append(j)
    except Exception as exc:
        logger.warning("Meinestadt Verbindungsfehler: %s", exc)
        return []

    logger.info("Meinestadt %s: %d Stellen gefunden", stadt, len(found))
    return found
