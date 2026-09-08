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
from .satzweise import text_aus, zuordnen
from .textgrenzen import fuer_speicher

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
    return fuer_speicher(text)


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
    befund_gesamt: dict = {}
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
            # #813: satzweise zuordnen. Ein umgebautes Feld in EINEM
            # Datensatz hat bei himalayas die ganze Quelle genullt und
            # nach fuenf stillen Laeufen ihre Abschaltung ausgeloest.
            def _mit_tags(roh):
                stelle = _map(roh)
                if stelle is None:
                    return None
                return stelle, text_aus(roh.get("tags"))

            paare, befund = zuordnen(items, _mit_tags, "remoteok")
            befund_gesamt.update(befund)
            for j, tags_str in paare:
                if not _matches(j["title"], tags_str, j["description"], keywords):
                    continue
                found.append(j)
    except Exception as exc:
        logger.warning("RemoteOK Verbindungsfehler: %s", exc)

    if befund_gesamt.get("verdacht") == "feldumbau":
        logger.warning(
            "RemoteOK: %d Stellen gefunden, aber %d von %d Datensaetzen "
            "waren nicht lesbar — Feldumbau, kein leerer Markt (%s)",
            len(found), befund_gesamt.get("fehlerhaft"),
            befund_gesamt.get("gesamt"), befund_gesamt.get("erster_fehler"))
    else:
        logger.info("RemoteOK: %d Stellen gefunden", len(found))
    return found
