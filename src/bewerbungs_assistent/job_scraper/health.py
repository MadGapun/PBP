"""Health-Check fuer Job-Quellen (#624 Phase 2).

Pingt API-/Feed-Endpoints minimal an (1 Stelle, keine Filter), um zu
unterscheiden ob „0 Treffer heute" an unserer Suche oder an einer
toten/blockierten Quelle liegt.

Ergaenzt die existierende `scraper_health`-Logik (#590) die nur
ueber Liefer-Statistiken die Quelle einschaetzt — health_check() macht
einen aktiven Probe-Request OHNE Suche. Wert: schnellere Diagnose,
gerade wenn der User selbst „warum kommt nichts mehr von X?" fragt.

Verwendung:
    from .health import check_source, check_all_sources
    result = check_source("arbeitnow")
    # → {source, reachable, http_status, latency_ms, error?, ...}

    all_results = check_all_sources()
    # → list[dict]

User-Vorgabe „keine Live-HTTP-Calls in Tests" wird respektiert: Die
Funktionen werden in Tests via Mock von httpx aufgerufen.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from . import SOURCE_REGISTRY, make_session

logger = logging.getLogger("bewerbungs_assistent.scraper.health")


# Pro Quelle: (HTTP-Methode, URL, Content-Type, optionaler Request-Body)
# Das sind minimale Probe-Requests — eine Stelle, keine Filter.
_PROBES: dict[str, tuple[str, str, str, Optional[dict]]] = {
    # === Offizielle JSON-APIs ===
    "bundesagentur": (
        "GET",
        # v1.7.11 (#807/B29): v6 — v4/v5 liefern seit Sommer 2026 HTTP 404.
        # Muss mit dem Adapter-Endpunkt uebereinstimmen, sonst prueft der
        # Health-Check etwas anderes als die Suche tatsaechlich nutzt.
        "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
        "?was=test&size=1",
        "json",
        None,
    ),
    # HINWEIS zu bundesagentur: braucht die Adapter-Header (X-API-Key + UA),
    # sonst 403 — siehe _PROBE_EXTRA_HEADERS unten (B13.4, #748).
    "arbeitnow": (
        "GET",
        "https://www.arbeitnow.com/api/job-board-api?page=1",
        "json",
        None,
    ),
    "greenhouse": (
        "GET",
        "https://boards-api.greenhouse.io/v1/boards/airbnb/jobs",
        "json",
        None,
    ),
    "remoteok": (
        "GET",
        "https://remoteok.com/api",
        "json",
        None,
    ),
    "remotive": (
        "GET",
        "https://remotive.com/api/remote-jobs?limit=1",
        "json",
        None,
    ),
    "himalayas": (
        "GET",
        "https://himalayas.app/jobs/api?country=DE",
        "json",
        None,
    ),
    "workable": (
        "GET",
        # B13.4 (#748): v3-Pfad war 404 — der Adapter (workable.py) nutzt die
        # v1-Widget-API; Probe-Firma = erste DEFAULT_COMPANIES ("workable").
        "https://apply.workable.com/api/v1/widget/accounts/workable",
        "json",
        None,
    ),
    "workday_dax": (
        "POST",
        "https://wd3.myworkdayjobs.com/wday/cxs/sap/SAPCareers/jobs",
        "json",
        {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""},
    ),
    # === RSS / XML ===
    "berufsstart": (
        "GET",
        "https://www.berufsstart.de/jobs/rss",
        "rss",
        None,
    ),
    "studentjob": (
        "GET",
        "https://www.studentjob.de/rss/jobs",
        "rss",
        None,
    ),
    "praktikum_de": (
        "GET",
        "https://www.praktikum.de/rss.xml",
        "rss",
        None,
    ),
    "personio": (
        "GET",
        # B13.4 (#748): hellofresh war 404 (nicht in der Adapter-Liste) —
        # Probe-Firma = erste DEFAULT_COMPANIES aus personio.py
        # ("personio", Personio selbst; stabilste Wahl).
        "https://personio.jobs.personio.de/xml",
        "xml",
        None,
    ),
    # === HTML-Quellen nach URL-Migration #653 (B13/#747) ===
    # Probe-URLs entsprechen exakt den Request-URLs der Adapter
    # (ingenieur_de.py bzw. ferchau.py) — damit prueft der Health-Check
    # denselben Endpunkt, den auch die echte Suche trifft.
    "ingenieur_de": (
        "GET",
        "https://jobs.ingenieur.de/suche?q=test&sort=date",
        "html",
        None,
    ),
    "ferchau": (
        "GET",
        "https://touch.ferchau.com/de/de"
        "?search=test&type=3&sortingType=actuality&sortingDirection=DESC",
        "html",
        None,
    ),
}

# B13.4 (#748): Quellen, deren Production-Adapter besondere Header senden,
# brauchen dieselben Header auch in der Probe — sonst meldet der Health-Check
# falsch-rot (bundesagentur: 403 ohne X-API-Key). Header stammen 1:1 aus dem
# jeweiligen Adapter-Modul.
_PROBE_EXTRA_HEADERS: dict[str, dict] = {
    "bundesagentur": {
        "X-API-Key": "jobboerse-jobsuche",  # bundesagentur.py:API_KEY (public)
        "User-Agent": (
            "Jobsuche/2.12.0 (de.arbeitsagentur.jobboerse; build:1081; "
            "iOS 16.0) Alamofire/5.6.2"
        ),
    },
}

_TIMEOUT = 10.0  # Health-Check ist nur Ping — keine 30s-Wartezeit


def check_source(source_key: str, timeout: float = _TIMEOUT) -> dict[str, Any]:
    """Probet eine einzelne Quelle. Liefert ein strukturiertes Result-Dict.

    Result-Schema:
        source: str           — Source-Key
        reachable: bool       — True bei HTTP 2xx
        http_status: int|None — Status-Code, None bei Connection-Fehler
        latency_ms: int|None  — Round-Trip in ms
        method: str           — GET/POST
        url: str              — Probe-URL
        error: str|None       — Bei Connection-Fehler / Timeout / unbekannter Quelle
        notes: str|None       — Optional, z.B. „returned 0 jobs" wenn Schema OK aber leer
    """
    if source_key not in SOURCE_REGISTRY:
        return {
            "source": source_key,
            "reachable": False,
            "http_status": None,
            "latency_ms": None,
            "method": "",
            "url": "",
            "error": "unknown_source",
        }
    if source_key not in _PROBES:
        return {
            "source": source_key,
            "reachable": False,
            "http_status": None,
            "latency_ms": None,
            "method": "",
            "url": "",
            "error": "no_probe_defined",
            "notes": "Quelle hat keine API/Feed (z.B. Browser-/JobSpy-basiert)",
        }
    method, url, content_type, body = _PROBES[source_key]
    extra_headers = _PROBE_EXTRA_HEADERS.get(source_key)
    start = time.perf_counter()
    try:
        with make_session(content_type=content_type, timeout=timeout,
                          extra_headers=extra_headers) as client:
            if method == "GET":
                resp = client.get(url)
            elif method == "POST":
                resp = client.post(url, json=body or {})
            else:
                return {
                    "source": source_key, "reachable": False,
                    "http_status": None, "latency_ms": None,
                    "method": method, "url": url,
                    "error": f"unsupported_method:{method}",
                }
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "source": source_key,
            "reachable": 200 <= resp.status_code < 300,
            "http_status": resp.status_code,
            "latency_ms": latency_ms,
            "method": method,
            "url": url,
            "error": None,
        }
    except httpx.TimeoutException:
        return {
            "source": source_key, "reachable": False,
            "http_status": None,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "method": method, "url": url,
            "error": "timeout",
        }
    except httpx.TransportError as exc:
        return {
            "source": source_key, "reachable": False,
            "http_status": None,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "method": method, "url": url,
            "error": f"transport:{type(exc).__name__}",
        }
    except Exception as exc:
        logger.warning("health_check unerwartet fehlgeschlagen fuer %s: %s",
                        source_key, exc)
        return {
            "source": source_key, "reachable": False,
            "http_status": None,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "method": method, "url": url,
            "error": f"exception:{type(exc).__name__}:{str(exc)[:80]}",
        }


def check_all_sources(timeout: float = _TIMEOUT) -> list[dict[str, Any]]:
    """Probet alle Quellen mit Probe-Definition. Liefert Liste aller Results.

    Reihenfolge entspricht dem Eintrag in _PROBES. Pro Quelle ein
    HTTP-Request — bei 12 Quellen ca. 12s im worst case (sequenziell).
    Fuer parallele Ausfuehrung muss der Aufrufer ThreadPoolExecutor nutzen.
    """
    return [check_source(k, timeout=timeout) for k in _PROBES.keys()]


def get_probable_sources() -> list[str]:
    """Liste aller Source-Keys fuer die ein Probe definiert ist."""
    return list(_PROBES.keys())
