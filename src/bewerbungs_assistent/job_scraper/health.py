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
    # v1.7.19 (#927): Probes fuer workable, workday_dax und praktikum_de
    # entfernt — diese Quellen sind seit dem Live-Check als `defekt`
    # markiert. Eine Probe auf eine defekte Quelle meldet im besten Fall
    # HTTP 200 und damit faelschlich "gruen" (#808-Logik); der Guard-Test
    # aus #747 haelt die beiden Listen deshalb auseinander.
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
# v1.7.23 (#808): Schluessel, unter denen Stellen-Listen in den
# API-Antworten stehen. Bewusst breit — es geht nicht um exakte
# Feldnamen, sondern um die Frage "kommt hier plausibel etwas zurueck".
_LISTEN_SCHLUESSEL = (
    "stellenangebote", "ergebnisliste", "jobs", "data", "results",
    "items", "offers", "positions", "content", "elements", "hits",
    "vacancies", "postings",
)


def _zaehle_treffer(nutzlast) -> Optional[int]:
    """Wie viele Eintraege sieht die Probe? None = nicht bestimmbar."""
    if isinstance(nutzlast, list):
        return len(nutzlast)
    if not isinstance(nutzlast, dict):
        return None
    for schluessel in _LISTEN_SCHLUESSEL:
        wert = nutzlast.get(schluessel)
        if isinstance(wert, list):
            return len(wert)
        if isinstance(wert, dict):
            # Eine Ebene tiefer schauen (haeufig bei ATS-Antworten).
            for unter in _LISTEN_SCHLUESSEL:
                if isinstance(wert.get(unter), list):
                    return len(wert[unter])
    # Manche ATS melden nur eine Gesamtzahl.
    for schluessel in ("totalFound", "total", "totalCount", "count",
                       "maxErgebnisse", "numFound"):
        wert = nutzlast.get(schluessel)
        if isinstance(wert, int):
            return wert
    return None


def bewerte_inhalt(resp, erwarteter_typ: str) -> tuple[str, Optional[int], str]:
    """Liefert die Probe plausibel STELLEN, nicht nur einen Server?

    Drei belegte Muster von falsch-gruen (#808):

    1. Die Probe zeigt auf denselben toten Endpunkt wie der Adapter —
       beide melden konsistent dasselbe Falsche. So blieb der
       Bundesagentur-Ausfall wochenlang unbemerkt.
    2. Eine SPA antwortet auf einen API-Pfad mit HTTP 200 und HTML (die
       Fallback-Route). Der Check sah 200 und meldete "lebt".
    3. Ein falscher Firmen-Slug liefert gueltiges JSON mit
       `totalFound: 0`. Technisch einwandfrei, fachlich tot.

    Rueckgabe: (status, treffer, grund) mit status in
    ok | verdaechtig | leer. `verdaechtig` und `leer` sind bewusst KEIN
    Fehler — eine echte Flaute darf eine Quelle nicht sofort abschalten.
    """
    typ = (resp.headers.get("content-type") or "").lower()
    if erwarteter_typ == "json" and "html" in typ:
        return ("verdaechtig", None,
                "Als JSON-Quelle deklariert, geantwortet wurde HTML — "
                "typisch fuer die Fallback-Route einer Single-Page-App. "
                "Der Endpunkt existiert vermutlich nicht mehr.")
    if erwarteter_typ != "json":
        return ("ok", None, "")
    try:
        nutzlast = resp.json()
    except Exception:
        return ("verdaechtig", None,
                "Antwort ist kein gueltiges JSON, obwohl die Quelle als "
                "JSON-API gefuehrt wird.")
    treffer = _zaehle_treffer(nutzlast)
    if treffer is None:
        return ("ok", None,
                "Antwort ist JSON, eine Ergebnisliste war aber nicht "
                "erkennbar — der Status sagt hier nur, dass der Endpunkt lebt.")
    if treffer <= 0:
        return ("leer", 0,
                "Der Endpunkt antwortet, liefert aber keine Stellen. Bei "
                "firmenbezogenen Quellen ist das meist ein falscher "
                "Firmen-Slug, keine Stoerung.")
    return ("ok", treffer, "")


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
        erreichbar = 200 <= resp.status_code < 300
        # v1.7.23 (#808): HTTP 200 allein beweist nicht, dass eine Quelle
        # Stellen liefert. Solange die Zahl nicht misst, was sie
        # behauptet, ist sie schlimmer als keine Zahl — man verlaesst
        # sich darauf.
        inhalt, treffer, grund = ("ok", None, "")
        if erreichbar:
            try:
                inhalt, treffer, grund = bewerte_inhalt(resp, content_type)
            except Exception:
                inhalt, treffer, grund = ("ok", None, "")
        ergebnis = {
            "source": source_key,
            "reachable": erreichbar,
            "http_status": resp.status_code,
            "latency_ms": latency_ms,
            "method": method,
            "url": url,
            "error": None,
            "inhalt": inhalt if erreichbar else "fehler",
        }
        if treffer is not None:
            ergebnis["treffer"] = treffer
        if grund:
            ergebnis["inhalt_hinweis"] = grund
        return ergebnis
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
