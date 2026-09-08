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
from .satzweise import text_aus, zuordnen
from .textgrenzen import fuer_speicher

logger = logging.getLogger("bewerbungs_assistent.scraper.himalayas")

_BASE = "https://himalayas.app/jobs/api"
_TIMEOUT = 12
_MAX_PAGES = 3


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return fuer_speicher(text)


def _matches(title: str, desc: str, keywords: list) -> bool:
    if not keywords:
        return True
    haystack = f"{title} {desc[:1500]}".lower()
    return any(kw.lower().strip() in haystack for kw in keywords)


def _map(job: dict) -> dict | None:
    title = text_aus(job.get("title") or job.get("name"))
    if not title:
        return None
    company = (text_aus(job.get("companyName"))
               or text_aus(job.get("company"))
               or "Nicht angegeben")
    url = text_aus(job.get("applicationLink")) or text_aus(job.get("url"))
    desc = _strip_html(text_aus(job.get("description")))
    job_id = (text_aus(job.get("guid")) or text_aus(job.get("id"))
              or text_aus(job.get("slug")) or url)
    # #813 (08.09.2026): `seniority` kommt seit einem Feldumbau als LISTE
    # (`['Senior']`). Das direkte `.lower()` warf einen AttributeError,
    # und weil die Schleife in einem grossen try lag, gab der Adapter
    # eine leere Liste zurueck — 20 gelieferte Stellen wurden zu einer
    # stillen Null, und nach fuenf solchen Laeufen schaltete die
    # Automatik die Quelle ab. `text_aus` liest jedes Feld als Text,
    # egal welche Form die Quelle ihm als naechstes gibt.
    job_type = f"{text_aus(job.get('seniority'))} " \
               f"{text_aus(job.get('employmentType'))}".lower()
    if "intern" in job_type:
        emp = "praktikum"
    elif "freelance" in job_type or "contract" in job_type:
        emp = "freelance"
    else:
        emp = "festanstellung"
    # `country=DE` filtert die Ergebnisse NICHT: gemessen am 08.09. trugen
    # Treffer aus der DE-Abfrage `locationRestrictions: ['United States']`.
    # Der Ort gehoert deshalb an die Stelle, statt pauschal "Remote" zu
    # behaupten — sonst sieht eine US-gebundene Rolle aus wie eine, auf
    # die man sich von Hamburg aus bewerben kann.
    orte = text_aus(job.get("locationRestrictions"))
    return {
        "hash": stelle_hash("himalayas", f"{company} {job_id} {title}"),
        "title": title,
        "company": company,
        "location": f"Remote ({orte})" if orte else "Remote",
        "url": url or f"https://himalayas.app/jobs/{text_aus(job.get('slug'))}",
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
    letzter_befund: dict = {}
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
                # #813: satzweise — ein kaputter Datensatz kostet einen
                # Datensatz, nicht die Quelle.
                gemappt, befund = zuordnen(items, _map, "himalayas")
                if befund.get("verdacht") == "feldumbau":
                    letzter_befund.update(befund)
                for j in gemappt:
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

    if letzter_befund.get("verdacht") == "feldumbau":
        # Der Unterschied, um den es in #813 geht: "nichts gefunden" und
        # "nicht lesen koennen" duerfen nicht gleich aussehen.
        logger.warning(
            "Himalayas: %d Stellen gefunden, aber %d von %d Datensaetzen "
            "waren nicht lesbar — das ist kein leerer Markt, sondern ein "
            "Feldumbau. Erster Fehler: %s",
            len(found), letzter_befund.get("fehlerhaft"),
            letzter_befund.get("gesamt"), letzter_befund.get("erster_fehler"))
    else:
        logger.info("Himalayas: %d Stellen gefunden", len(found))
    return found
