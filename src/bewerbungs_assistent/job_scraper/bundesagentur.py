"""Bundesagentur für Arbeit REST API scraper.

Uses the public REST API (no authentication needed).
Reliable, no anti-bot measures.

#489 (seit v1.6.0-beta.2):
    Retry-Logik mit exponential backoff bei 503/transienten Fehlern (in
    ~30% der Faelle wirft die API ein „DNS cache overflow"-503, das auf
    Wiederholung ohne Aenderung verschwindet), plus Umkreis-Parameter
    und iOS-App User-Agent fuer stabile Ergebnisse.
"""

import logging
import time

import httpx

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.bundesagentur")

API_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
API_KEY = "jobboerse-jobsuche"  # Public key, no registration needed

# iOS-App User-Agent laut bundesAPI/jobsuche-api — die API mag dort einen
# Client-Kontext sehen statt leerem/python-UA (#489).
USER_AGENT = "Jobsuche/2.12.0 (de.arbeitsagentur.jobboerse; build:1081; iOS 16.0) Alamofire/5.6.2"

# Retry-Konfiguration (#489)
_RETRY_STATUS = {500, 502, 503, 504}
_RETRY_MAX = 3
_RETRY_BACKOFF_BASE = 2.0  # 2s, 4s, 8s

DEFAULT_KEYWORDS = [
    "Software Engineer", "Projektmanager", "Data Analyst",
    "DevOps Engineer", "Consultant", "Product Manager",
]

# #500: Limit fuer Detail-API-Calls pro Keyword. Vorher wurde fuer JEDE
# der bis zu 100 Stellen pro Keyword die Detail-API aufgerufen — das macht
# bei 6 Keywords 600 sequentielle Calls, also 5+ Minuten allein fuer BA.
# Wir holen Detail-Beschreibungen jetzt nur fuer die ersten N Treffer pro
# Keyword; fuer den Rest bleibt der `beruf`-String als Kurzbeschreibung.
# Das beschleunigt BA um Faktor ~4 ohne Volumenverlust.
_DETAIL_FETCH_LIMIT_PER_KW = 20


def _request_with_retry(client: httpx.Client, url: str, params: dict | None = None) -> httpx.Response | None:
    """GET mit Retry+Backoff fuer transiente Fehler (#489).

    Liefert None bei permanenten Fehlern oder nach erschoepften Retries,
    damit der Caller einfach `continue`-en kann.
    """
    headers = {"X-API-Key": API_KEY, "User-Agent": USER_AGENT}
    last_exc: Exception | None = None
    for attempt in range(1, _RETRY_MAX + 1):
        try:
            resp = client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                return resp
            if resp.status_code in _RETRY_STATUS and attempt < _RETRY_MAX:
                wait = _RETRY_BACKOFF_BASE ** attempt
                logger.info("BA %d (%s) — retry %d/%d in %.1fs",
                            resp.status_code, url.split("/")[-1][:40], attempt, _RETRY_MAX, wait)
                time.sleep(wait)
                continue
            # Permanente Fehler (4xx ausser Retry-Liste) oder letzter Versuch
            logger.warning("BA API %d nach Versuch %d fuer %s", resp.status_code, attempt, params)
            return None
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_exc = e
            if attempt < _RETRY_MAX:
                wait = _RETRY_BACKOFF_BASE ** attempt
                logger.info("BA Transport-Fehler (%s) — retry %d/%d in %.1fs",
                            type(e).__name__, attempt, _RETRY_MAX, wait)
                time.sleep(wait)
                continue
            logger.error("BA Transport-Fehler nach %d Versuchen: %s", attempt, e)
            return None
    if last_exc:
        logger.error("BA: alle Retries erschoepft (%s)", last_exc)
    return None


def search_bundesagentur(params: dict) -> list:
    """Search Bundesagentur für Arbeit job API.

    Args:
        params: Search parameters with optional 'keywords' list

    Returns:
        List of job dicts
    """
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", DEFAULT_KEYWORDS)
        regionen = kw_data.get("regionen", [])
    else:
        keywords = kw_data or DEFAULT_KEYWORDS
        regionen = []
    criteria = params.get("criteria", {}) or {}
    # #489: Umkreis aus Criteria uebernehmen (Dashboard-Einstellung „Umkreis km")
    umkreis = criteria.get("umkreis_km") or params.get("umkreis") or 100
    jobs = []

    with httpx.Client(timeout=30) as client:
        for kw in keywords:
            try:
                api_params = {
                    "was": kw,
                    "size": 100,          # #489: API erlaubt bis 100 pro Seite
                    "page": 1,
                    "pav": "false",       # nur oeffentliche Stellen
                    "angebotsart": 1,     # nur Stellenangebote (kein Ausbildung/Praktikum)
                }
                if regionen:
                    api_params["wo"] = regionen[0]
                    api_params["umkreis"] = umkreis
                resp = _request_with_retry(client, API_URL, params=api_params)
                if resp is None:
                    continue

                data = resp.json()
                stellenangebote = data.get("stellenangebote", [])

                for idx, s in enumerate(stellenangebote):
                    title = s.get("titel", "")
                    company = s.get("arbeitgeber", "Nicht angegeben")
                    location = s.get("arbeitsort", {}).get("ort", "")
                    ref_nr = s.get("refnr", "")

                    # Detail-API nur fuer die ersten N pro Keyword (#500),
                    # sonst beruf-Kurzbeschreibung. Ergebnis: 4x schneller
                    # ohne Volumenverlust.
                    description = s.get("beruf", "")
                    if ref_nr and idx < _DETAIL_FETCH_LIMIT_PER_KW:
                        description = _fetch_ba_detail(client, ref_nr) or description

                    # v1.7.0-beta.7 (#526): Direkte jobdetail-URL statt
                    # jobsuche/suche?id=... — letzteres landet auf der
                    # Suchergebnis-Seite und nicht in der Stellenanzeige.
                    job = {
                        "hash": stelle_hash("arbeitsagentur.de", title),
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref_nr}",
                        "source": "bundesagentur",
                        "description": description[:2000],
                        "employment_type": "festanstellung",
                        "remote_level": detect_remote_level(f"{title} {location} {description}"),
                    }
                    jobs.append(job)

                time.sleep(0.5)  # Be polite
            except Exception as e:
                logger.error("BA search error for '%s': %s", kw, e)

    logger.info("Bundesagentur: %d Stellen gefunden", len(jobs))
    return jobs


# #489: Neue Detail-URL — base64(refnr) statt nacktem refnr, sonst 403.
DETAIL_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/{encoded}"


def _extract_text(data: dict, path: str) -> str:
    """Extract string value from nested dict using dot-notation path."""
    current = data
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key, "")
        else:
            return ""
    return current if isinstance(current, str) else ""


def _fetch_ba_detail(client: httpx.Client, ref_nr: str) -> str:
    """Fetch full job description from BA detail API.

    #387: The BA API v4 nests description fields in various locations.
    We check multiple paths to handle both old and new response formats.
    #489: Retry+Backoff auch hier — die Detail-API hat dasselbe 503-Flackern.
    """
    try:
        import base64
        encoded = base64.b64encode(ref_nr.encode("utf-8")).decode("ascii")
        resp = _request_with_retry(client, DETAIL_URL.format(encoded=encoded))
        if resp is None:
            return ""
        data = resp.json()
        parts = []

        # Primary description fields — API v4 liefert camelCase (#489),
        # die lowercase-Varianten bleiben als Fallback fuer aeltere Responses.
        _fields = [
            "stellenangebotsBeschreibung",     # #489: Hauptfeld der neuen API
            "stellenangebotsTitel",
            "verguetungsangabe",
            "vertragsdauer",
            "arbeitgeberdarstellung",
            "arbeitgeberdarstellungUrl",
            # Legacy / Fallback
            "stellenbeschreibung",
            "stellenangebotsbeschreibung",
            "stellenangebotsinhalte.stellenbeschreibung",
            "stellenangebotsinhalte.beschreibung",
            "beruf",
            "branche",
            "taetigkeit",
        ]
        for path in _fields:
            val = _extract_text(data, path)
            if val and val not in parts:
                parts.append(val)

        # Also check freieBezeichnung and details from top-level dict values
        for key in ("freieBezeichnung", "externeUrl", "beschreibung"):
            val = data.get(key, "")
            if val and isinstance(val, str) and val not in parts:
                parts.append(val)

        desc = " | ".join(parts) if parts else ""
        if not desc:
            logger.debug("BA detail for %s: no description fields found in keys %s",
                         ref_nr, list(data.keys()))
        return desc
    except Exception as e:
        logger.debug("BA detail error for %s: %s", ref_nr, e)
        return ""
