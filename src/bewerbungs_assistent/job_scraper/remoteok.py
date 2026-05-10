"""RemoteOK Remote-Jobs (#590 Aufgabe B.5).

RemoteOK liefert seine kompletten Stellen als JSON-Feed:

    GET https://remoteok.com/api

Erstes Element ist Metadaten, ab Index 1 kommen Job-Eintraege.
Kein Auth-Header noetig — aber User-Agent wird streng geprueft.
"""

from __future__ import annotations

import logging
import re

from . import make_session, stelle_hash

logger = logging.getLogger("bewerbungs_assistent.scraper.remoteok")

_BASE = "https://remoteok.com/api"
# RemoteOK blockiert leere/anonyme UAs — der zentrale PBP_USER_AGENT
# enthaelt schon den Kontakt-Hinweis (Best Practice).
_TIMEOUT = 12


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2000]


def _matches(title: str, tags: str, desc: str, keywords: list) -> bool:
    if not keywords:
        return True
    haystack = f"{title} {tags} {desc[:1500]}".lower()
    return any(kw.lower().strip() in haystack for kw in keywords)


def _map(job: dict) -> dict | None:
    title = job.get("position") or job.get("title") or ""
    if not title:
        return None
    company = job.get("company") or "Nicht angegeben"
    url = job.get("url") or job.get("apply_url") or ""
    location = job.get("location") or "Remote"
    desc = _strip_html(job.get("description") or "")
    job_id = job.get("id") or job.get("slug") or url
    return {
        "hash": stelle_hash("remoteok", f"{company} {job_id} {title}"),
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "source": "remoteok",
        "description": desc,
        "employment_type": "festanstellung",
        "remote_level": "remote",
    }


def search_remoteok(params: dict) -> list[dict]:
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", [])
    else:
        keywords = kw_data or []

    found: list[dict] = []
    try:
        # v1.7.0-beta.50 (#624): zentraler make_session-Helper
        with make_session(content_type="json", timeout=_TIMEOUT) as client:
            r = client.get(_BASE)
            if r.status_code != 200:
                logger.debug("RemoteOK HTTP %d", r.status_code)
                return []
            try:
                data = r.json()
            except Exception:
                return []
            # Erstes Element ist Metadaten
            items = data[1:] if isinstance(data, list) and len(data) > 0 else []
            for raw in items:
                j = _map(raw)
                if not j:
                    continue
                tags_str = " ".join(raw.get("tags") or [])
                if not _matches(j["title"], tags_str, j["description"], keywords):
                    continue
                found.append(j)
    except Exception as exc:
        logger.warning("RemoteOK Verbindungsfehler: %s", exc)

    logger.info("RemoteOK: %d Stellen gefunden", len(found))
    return found
