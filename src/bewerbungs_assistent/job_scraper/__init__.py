"""Job Scraper Module — Multi-source job search engine.

Provides SOURCE_REGISTRY for all available job sources,
dynamic keyword building from DB criteria, and the run_search orchestrator.

v1.7.0-beta.50 (#624 Phase 1): Zentrale HTTP-Helper. Bisher hat jeder
Scraper sein eigenes _HEADERS-Dict + Timeout + httpx-Setup definiert
(5 verschiedene User-Agent-Strings, Timeouts 12-30s, kein einheitliches
Retry-Pattern). Neue Helpers:

- PBP_USER_AGENT — einheitlicher UA mit Kontakt-URL
- make_session(content_type, timeout, ...) — vorkonfigurierter httpx.Client
- with_retry(...) — Decorator fuer transient-error-Retry mit exponential backoff

Migration in einzelnen Scrapern erfolgt schrittweise (siehe #624 Phase 1).
"""

import functools
import hashlib
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from typing import Callable, Optional
from urllib.parse import quote

import httpx

from ..services.scraper_classifier import (
    classify_scraper_error,
    ERROR_CLASS_SERVER_WEG,
    ERROR_CLASS_KAPUTT,
)

logger = logging.getLogger("bewerbungs_assistent.scraper")


# === Zentrale HTTP-Konstanten + Helpers (#624 Phase 1) ============

PBP_VERSION = "1.7"  # Major.Minor — bei jedem Major-Bump anpassen
PBP_USER_AGENT = (
    f"PBP-Bewerbungs-Assistent/{PBP_VERSION} "
    "(+https://github.com/MadGapun/PBP)"
)

_ACCEPT_HEADERS = {
    "json": "application/json",
    "rss": "application/rss+xml, application/xml;q=0.9",
    "xml": "application/xml, text/xml;q=0.9",
    "html": "text/html,application/xhtml+xml",
    "any": "*/*",
}

DEFAULT_TIMEOUT = 15.0


def make_session(
    content_type: str = "json",
    timeout: float = DEFAULT_TIMEOUT,
    extra_headers: Optional[dict] = None,
    user_agent: Optional[str] = None,
    follow_redirects: bool = True,
) -> httpx.Client:
    """Liefert einen vorkonfigurierten httpx.Client mit PBP-Standards.

    Verwendung:
        with make_session(content_type="json") as client:
            r = client.get(url)

    Args:
        content_type: 'json' (Default), 'rss', 'xml', 'html', 'any'
        timeout: Request-Timeout in Sekunden (Default 15)
        extra_headers: zusaetzliche/ueberschreibende Header
        user_agent: Override fuer User-Agent (sonst PBP_USER_AGENT)
        follow_redirects: Default True (httpx ist sonst False)
    """
    headers = {
        "User-Agent": user_agent or PBP_USER_AGENT,
        "Accept": _ACCEPT_HEADERS.get(content_type, _ACCEPT_HEADERS["any"]),
    }
    if extra_headers:
        headers.update(extra_headers)
    return httpx.Client(
        headers=headers,
        timeout=timeout,
        follow_redirects=follow_redirects,
    )


# Status-Codes die als transient gelten und Retry rechtfertigen
_RETRY_STATUS_CODES = frozenset({500, 502, 503, 504, 429})


def with_retry(
    max_attempts: int = 3,
    backoff_base: float = 2.0,
    retry_status: frozenset = _RETRY_STATUS_CODES,
):
    """Decorator: wiederholt eine HTTP-Funktion bei transienten Fehlern.

    Erkennt:
    - HTTP-Status in retry_status (Default 500/502/503/504/429)
    - httpx.TransportError (Connection-Probleme)
    - httpx.TimeoutException

    Backoff: exponential. Bei 429 mit Retry-After-Header wird der hoehere
    Wert genommen.

    Die dekorierte Funktion muss eine httpx.Response zurueckgeben.
    """
    def deco(fn: Callable):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    resp = fn(*args, **kwargs)
                    if (isinstance(resp, httpx.Response)
                            and resp.status_code in retry_status):
                        wait = backoff_base * (2 ** attempt)
                        if resp.status_code == 429:
                            ra = resp.headers.get("Retry-After")
                            try:
                                wait = max(wait, float(ra)) if ra else wait
                            except (TypeError, ValueError):
                                pass
                        if attempt < max_attempts - 1:
                            logger.debug(
                                "Retry %d/%d nach Status %d (wait %.1fs)",
                                attempt + 1, max_attempts, resp.status_code, wait
                            )
                            time.sleep(wait)
                            continue
                    return resp
                except (httpx.TransportError, httpx.TimeoutException) as exc:
                    last_exc = exc
                    if attempt < max_attempts - 1:
                        wait = backoff_base * (2 ** attempt)
                        logger.debug(
                            "Retry %d/%d nach %s (wait %.1fs)",
                            attempt + 1, max_attempts, type(exc).__name__, wait
                        )
                        time.sleep(wait)
                        continue
                    raise
            if last_exc:
                raise last_exc
            return None
        return wrapper
    return deco


# ── Source Registry ─────────────────────────────────────────────
# Describes all available sources. active_sources in settings DB
# controls which ones are actually used (default: none).

SOURCE_REGISTRY = {
    # ── Schnelle Quellen (HTTP/API, parallel, < 10s) ──────────────
    "bundesagentur": {
        "name": "Bundesagentur fuer Arbeit",
        "beschreibung": "Oeffentliche Jobboerse der Arbeitsagentur. Groesstes deutsches Stellenportal.",
        "methode": "REST API",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    "hays": {
        "name": "Hays",
        "beschreibung": "Personaldienstleister mit eigenem Stellenportal. Schwerpunkt Engineering & IT.",
        "methode": "Sitemap + JSON-LD",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    "freelance_de": {
        # v1.7.19 (#927): live geprueft, kein automatischer Weg.
        "defekt": True,
        "defekt_grund": "Projektsuche liefert nur eine SPA-Huelle (25 KB ohne Inhalt), die JSON-API antwortet mit HTTP 403 (18.08.2026). Seit Bestehen kein einziger erfolgreicher Lauf.",
        "manueller_fallback": "quelle_handoff('freelance_de') — Projektsuche im Browser oeffnen; Alternative mit denselben Projekttypen: die zweite Projektboerse laeuft seit v1.7.19 wieder",
        "name": "freelance.de",
        "beschreibung": "Projektboerse fuer Freelancer und IT-Projekte. Grosse Auswahl an Projekten in DACH.",
        "methode": "HTML Scraping",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    "ingenieur_de": {
        "name": "ingenieur.de (VDI)",
        "beschreibung": "Engineering-Jobboerse des VDI. Spezialisiert auf Ingenieur- und Technik-Stellen.",
        "methode": "HTML Scraping",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
        # #653 (B12, beta.77): URL-Migration — neue Job-Subdomain jobs.ingenieur.de.
        # Alte URL `/jobs/` ist seit 2026-04-25 dauerhaft 404. Scraper-Code in
        # `ingenieur_de.py` muss auf die neue Subdomain umgestellt werden.
        "url_aktualisiert_am": "2026-06-01 (Issue #653)",
        "manueller_fallback": "https://jobs.ingenieur.de/ (im Browser oder Chrome-Extension oeffnen)",
    },
    "heise_jobs": {
        "name": "Heise Jobs",
        "beschreibung": "IT-Stellenmarkt von Heise Verlag. Starke IT/Admin-Community.",
        "methode": "HTML Scraping + JSON-LD",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
        # #500: SSR-HTML enthaelt nur Kategorie-Links, keine Stellen.
        # Vermutlich SPA-rendered. Browser-Tab via Chrome-Extension noetig.
        "defekt": True,
        "defekt_grund": "SSR-HTML zeigt nur Kategorien (Jobs Informatik/Softwareentwickler/...) — Stellen werden client-seitig nachgeladen",
        "manueller_fallback": "https://jobs.heise.de/?keywords=Python (im Browser oder Chrome-Extension)",
    },
    "gulp": {
        "name": "GULP",
        "beschreibung": "Top IT/Engineering Freelance-Projektboerse. Grosse Auswahl an IT-Projekten.",
        "methode": "Handoff (Browser)",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
        # #500: Live-Test 2026-04-25 — alle bekannten Such-URLs HTTP 404.
        # v1.7.12 (#812/B34, live 11.08.): Projektliste liefert 200 mit
        # 9-KB-SPA-Huelle (Projekte laden erst im Browser), die im Adapter
        # hinterlegte JSON-API antwortet 404. Ein Playwright-Umbau waere
        # eine kurzlebige DOM-Wette (B18-Lehre) fuer eine einzelne
        # Freelance-Boerse — der Handoff ist der ehrliche Weg.
        "defekt": True,
        "defekt_grund": "SPA ohne erreichbare JSON-API (Suche 200/leer, API 404 — 11.08.2026)",
        "handoff_verfuegbar": True,
        "manueller_fallback": "quelle_handoff('gulp') — oeffnet die Projektsuche im Browser",
    },
    "solcom": {
        "name": "SOLCOM",
        "beschreibung": "IT + Engineering Projektportal. Personaldienstleister fuer IT-Projekte.",
        "methode": "Chrome-Extension only",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
        # #653 (B12, beta.77): Cloudflare Bot-Block seit 2026-04-25
        # dauerhaft aktiv (auch mit User-Agent-Spoofing 403). Quelle nur
        # noch via Chrome-Extension nutzbar. Aus Auto-Scraper-Liste raus.
        "deprecated": True,
        "deprecated_grund": "Cloudflare-Bot-Block dauerhaft aktiv — nur Chrome-Extension",
        "manueller_fallback": "https://www.solcom.de/projekte (Browser oder Chrome-Extension)",
    },
    "stellenanzeigen_de": {
        "name": "Stellenanzeigen.de",
        "beschreibung": "Grosses deutsches Jobportal mit 3.2 Mio. Besuchern/Monat.",
        "methode": "HTML Scraping + JSON-LD",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    "adzuna": {
        "name": "Adzuna",
        "beschreibung": (
            "Aggregator-Jobsuche mit 19-Laender-Abdeckung. REST-API, "
            "deutsche Stellen, kostenlose Registrierung auf developer.adzuna.com. "
            "Liefert Aggregations-Coverage aehnlich Bundesagentur."
        ),
        "methode": "REST-API (JSON)",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
        # #654 (B17, beta.77): User muss app_id + app_key in Settings tragen.
        "api_key_erforderlich": True,
        "api_key_settings": ["adzuna_app_id", "adzuna_app_key"],
        "registrierungs_url": "https://developer.adzuna.com/",
    },
    "jobware": {
        "name": "Jobware",
        "beschreibung": "Premium-Jobportal fuer Spezialisten und Fuehrungskraefte.",
        "methode": "HTML Scraping + JSON-LD",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    "ferchau": {
        # v1.7.19 (#925): wiederhergestellt — der Adapter suchte JSON-LD
        # im DOM, die Stellendaten liegen im SSR-Hydration-Payload.
        # Liefert wieder 25 Stellen je Abruf, alle mit Detail-URL und
        # echter Gehaltsspanne (live verifiziert 18.08.2026). War im
        # Registry nie deprecated, aber in der DB auto-deaktiviert.
        "name": "FERCHAU",
        "beschreibung": "Engineering & IT Personaldienstleister. Grosser Footprint in Engineering.",
        "methode": "HTML Scraping + JSON-LD",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
        # #653 (B12, beta.77): URL-Migration zu touch.ferchau.com Karriere-
        # Plattform. Vermutlich SPA mit eigenem JSON-Endpoint. Erstmal HTML-
        # Scraping versuchen, ggf. Playwright-Update in B18.
        "url_aktualisiert_am": "2026-06-01 (Issue #653)",
        "manueller_fallback": "https://touch.ferchau.com/de/de?type=3 (im Browser oder Chrome-Extension)",
    },
    "kimeta": {
        "name": "Kimeta",
        "beschreibung": "Deutscher Job-Aggregator. Buendelt Stellen aus vielen Quellen.",
        "methode": "Handoff (Browser)",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
        # v1.7.12 (#810/B32): SCRAPING EINGESTELLT — robots.txt untersagt
        # es fuer alle Bots ausser namentlich gelisteten Suchmaschinen
        # ('User-agent: *' -> 'Disallow: /', geprueft 11.08.2026). Kein
        # Defekt, keine Reparatur: die Quelle bleibt ueber den Handoff
        # nutzbar (quelle_handoff oeffnet die Suche im Browser).
        "deprecated": True,
        "deprecated_grund": "robots.txt untersagt automatisierten Abruf — Handoff statt Scraping",
        "handoff_verfuegbar": True,
        "manueller_fallback": "quelle_handoff('kimeta') — oeffnet https://www.kimeta.de/jobs im Browser",
    },
    # ── JobSpy-basierte Quellen (#490, schnell, API-Scrapes via python-jobspy) ──
    "jobspy_linkedin": {
        "name": "LinkedIn (via JobSpy)",
        "beschreibung": "LinkedIn-Stellen ueber die Open-Source-Bibliothek python-jobspy (MIT). "
                         "Kein Login, keine API-Keys, kein Chrome noetig.",
        "methode": "python-jobspy",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
        "warnung": "LinkedIn rate-limitet ab ca. Seite 10 pro IP — bei 429 wird die Site uebersprungen.",
        "beta": True,
    },
    "jobspy_indeed": {
        "name": "Indeed.de (via JobSpy)",
        "beschreibung": "Indeed-Stellen ueber die Open-Source-Bibliothek python-jobspy (MIT). "
                         "Deckt Indeed DE/EU stabil ab, inkl. Volltext.",
        "methode": "python-jobspy",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
        "beta": True,
    },
    "jobspy_glassdoor": {
        "name": "Glassdoor (via JobSpy)",
        "beschreibung": "Glassdoor-Stellen ueber python-jobspy (MIT). Liefert oft 0 — "
                         "Glassdoor blockiert API-Zugriffe haeufig. Wird trotzdem mitversucht.",
        "methode": "python-jobspy",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
        "beta": True,
        "warnung": "Glassdoor blockiert API-Zugriffe haeufig — niedrige Trefferquote erwartet.",
    },
    # ── Freie Aggregatoren ohne API-Key (#500) ──
    "arbeitnow": {
        "name": "Arbeitnow",
        "beschreibung": "Freier deutscher Job-Aggregator mit offener REST-API. "
                         "Schwerpunkt Tech/Remote, kein API-Key, 100 Stellen pro Seite.",
        "methode": "REST API",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    # ── #590 Aufgabe A: Universelle Quellen fuer ALLE Profil-Typen ──
    "personio": {
        "name": "Personio (DACH-Mittelstand)",
        "beschreibung": "Personio ist DACH-spezifischer ATS, im KMU sehr verbreitet. "
                         "Stellen quer durch alle Branchen + Skill-Level (Azubi bis "
                         "Geschaeftsfuehrer). Fuer Service/Pflege/Hotel/Einzelhandel "
                         "oft die einzige zentrale Quelle.",
        "methode": "Public XML-Feed (jobs.personio.de/xml)",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    "workable": {
        # v1.7.19 (#927): live geprueft, kein automatischer Weg.
        "defekt": True,
        "defekt_grund": "Oeffentliche Suche liefert keine Stellenlinks mehr (200, aber 0 Treffer im HTML — 18.08.2026). Der Anbieter ist ein Bewerbermanagement-System; oeffentlich durchsuchbar sind nur die Job-Boards einzelner Firmen.",
        "manueller_fallback": "Firmen-Jobboard direkt als Custom-Quelle hinterlegen",
        "name": "Workable (Public Postings)",
        "beschreibung": "Internationaler ATS, viele KMU-Kunden. Public Widget API "
                         "pro Firma. Mid-Level breit gestreut, auch nicht-Tech.",
        "methode": "Public Widget API",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    "meinestadt": {
        # v1.7.19 (#927): live geprueft, kein automatischer Weg.
        "defekt": True,
        "defekt_grund": "Bot-Block: HTTP 403 auf die Suchseite (18.08.2026). Ein automatischer Abruf ist nicht moeglich.",
        "manueller_fallback": "Im Browser oder ueber die Chrome-Extension suchen und Treffer mit stelle_manuell_anlegen uebernehmen",
        "name": "meinestadt.de (Regional)",
        "beschreibung": "Regionale DACH-Stellenseite mit Schwerpunkt Service-, Trade- "
                         "und Pflege-Berufe (Kassierer, Hotel, Gastro, Handwerk). "
                         "Schliesst die Luecke zu JobSpy/LinkedIn fuer nicht-Tech.",
        "methode": "RSS-Feed pro Stadt",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    # ── #590 Aufgabe B.5: Tech-Remote-Cluster ──
    "himalayas": {
        "name": "Himalayas (Remote)",
        "beschreibung": "Remote-only Job-Aggregator mit Schwerpunkt Tech. "
                         "Public JSON-API, kein Auth, gute DACH-Abdeckung "
                         "ueber country=DE-Filter.",
        "methode": "REST API",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    "remotive": {
        "name": "Remotive (Remote)",
        "beschreibung": "Kuratierter Remote-Job-Aggregator. Public REST API "
                         "mit Suchstring-Parameter.",
        "methode": "REST API",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    "remoteok": {
        "name": "RemoteOK",
        "beschreibung": "Remote-only Aggregator (englischsprachig). Liefert komplette "
                         "Stellenliste als JSON-Feed. Schwerpunkt Tech/Marketing.",
        "methode": "REST API (JSON-Feed)",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    # ── #590 Aufgabe B.4: Student-Cluster ──
    "praktikum_de": {
        # v1.7.19 (#927): live geprueft, kein automatischer Weg.
        "defekt": True,
        "defekt_grund": "Suchseite antwortet mit HTTP 404 (18.08.2026). Fuer Senior-Profile ohnehin ohne Treffer-Erwartung.",
        "name": "Praktikum.de",
        "beschreibung": "Groesste DACH-Plattform fuer Praktika und Werkstudenten-"
                         "Stellen. RSS-Feed mit Suchwort-Parameter.",
        "methode": "RSS",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    "studentjob": {
        "name": "StudentJob.de",
        "beschreibung": "Studentenjobs und Werkstudentenstellen in DACH. "
                         "Public RSS-Feed.",
        "methode": "RSS",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    "berufsstart": {
        "name": "Berufsstart.de",
        "beschreibung": "Karriere-Einstieg fuer Studenten und Absolventen "
                         "(Trainee, Junior, Praktika, Direkteinstieg).",
        "methode": "RSS",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    # ── #590 Aufgabe B.3: Workday-DAX-Cluster ──
    "workday_dax": {
        # v1.7.19 (#927): live geprueft, kein automatischer Weg.
        "defekt": True,
        "defekt_grund": "Host nicht mehr aufloesbar (DNS-Fehler, 18.08.2026) — die Sammel-Domain fuer Workday-Karriereseiten existiert so nicht mehr. Einzelne Firmen-Instanzen haben eigene Adressen.",
        "manueller_fallback": "Karriereseite der jeweiligen Firma direkt aufrufen; als Custom-Quelle hinterlegen (custom_quelle_hinzufuegen)",
        "name": "Workday-DAX-Cluster",
        "beschreibung": "Public Workday-Career-Sites grosser DACH-Konzerne "
                         "(Siemens, SAP, Bosch, Continental, ZF, Schaeffler, "
                         "Knorr-Bremse, KraussMaffei, Heidelberg, Vitesco). "
                         "Erweiterbar via workday_firmen-Suchkriterium.",
        "methode": "Workday wd/cxs JSON-API",
        "login_erforderlich": False,
        "geschwindigkeit": "mittel",
    },
    "greenhouse": {
        "name": "Greenhouse Boards",
        "beschreibung": "Greenhouse-Karriereseiten mehrerer DACH-relevanter Firmen "
                         "(N26, Celonis, HelloFresh, GetYourGuide, Datadog, Elastic, Cloudflare, "
                         "MongoDB, GitLab, Twilio). Kein API-Key noetig.",
        "methode": "Public Job-Board-API",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    "jobspy_google": {
        "name": "Google Jobs (via JobSpy)",
        "beschreibung": "Google-Jobs-Aggregator ueber python-jobspy (MIT). Indiziert StepStone, "
                         "Indeed, LinkedIn und Dutzende DACH-Boards in einer Anfrage.",
        "methode": "python-jobspy",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
        "beta": True,
        "warnung": "Google blockiert automatisierte Jobsuche oft — wenn 0 Treffer, "
                    "ueber Google-Jobs-Karte in der Chrome-Extension manuell suchen.",
    },
    # ── Langsame Quellen (Browser/Playwright, sequentiell, 30-180s) ──
    "stepstone": {
        "name": "StepStone",
        "beschreibung": "Grosses deutsches Jobportal fuer Fach- und Fuehrungskraefte.",
        "methode": "Playwright (Browser)",
        "login_erforderlich": False,
        # v1.7.17 (#906): laeuft faktisch nur ueber Claude-in-Chrome mit
        # eingeloggtem Konto — als aktive Hintergrund-Quelle sah sie nur so aus.
        "zugriffsart": "browser_login",
        "konto_url": "https://www.stepstone.de/registrieren",
        "login_hinweis": "StepStone-Konto empfohlen; die Suche laeuft ueber die Chrome-Extension in deinem Browser, Treffer via stelle_manuell_anlegen().",
        "geschwindigkeit": "langsam",
        "warnung": "Benoetigt Google Chrome. Kann 1-3 Minuten dauern. Alternativ: Lass Claude gezielt auf stepstone.de suchen.",
    },
    "freelancermap": {
        "name": "Freelancermap",
        "beschreibung": "Projektboerse fuer Freelancer und Selbststaendige.",
        "methode": "HTML Scraping + Playwright Fallback",
        "login_erforderlich": False,
        "geschwindigkeit": "langsam",
        "warnung": "Nutzt bei Bedarf einen Browser als Fallback. Kann 30-60 Sekunden dauern.\nBei haeufigen Timeouts: Lass Claude direkt auf freelancermap.de suchen.",
        "beta": True,
    },
    "indeed": {
        "name": "Indeed",
        "beschreibung": "Groesste Jobsuchmaschine weltweit. Aggregiert Stellen aus vielen Quellen.",
        "methode": "Playwright (Browser)",
        "login_erforderlich": False,
        "zugriffsart": "browser_login",
        "konto_url": "https://secure.indeed.com/account/register",
        "login_hinweis": "Laeuft ueber die Chrome-Extension in deinem Browser; ein Indeed-Konto verbessert die Treffer (Standort/Praeferenzen).",
        "geschwindigkeit": "langsam",
        "warnung": "Benoetigt Google Chrome. Kann 30-90 Sekunden dauern. Alternativ: Lass Claude gezielt auf indeed.com suchen.",
    },
    "monster": {
        "name": "Monster",
        "beschreibung": "Internationales Jobportal mit breitem Stellenangebot.",
        "methode": "Playwright (Browser)",
        "login_erforderlich": False,
        "zugriffsart": "browser_login",
        "konto_url": "https://www.monster.de/",
        "login_hinweis": "De facto tot (deprecated) — falls ueberhaupt, nur ueber die Chrome-Extension.",
        "geschwindigkeit": "langsam",
        "warnung": "Benoetigt Google Chrome. Kann 30-90 Sekunden dauern.\nPortal aendert haeufig das Layout — bei Fehlern: Lass Claude gezielt auf monster.de suchen.",
        "beta": True,
        # #653 (B12, beta.77): Monster Europe transitioning seit 08/2025.
        # monster.de leitet auf monster.com/de/ um, dort gibt es aber nur
        # noch CV-Development-Services, keine Job-Listings mehr. Quelle
        # ist de facto tot — als deprecated markieren, aus Auto-Scraper-
        # Liste raus.
        "deprecated": True,
        "deprecated_grund": "Monster Europe Domain transitioning seit 08/2025 — keine deutschen Job-Listings mehr (siehe aimgroup.com 08/2025)",
        "manueller_fallback": "https://www.indeed.com/de/ als Alternative — Monster Germany hat keine Stellen mehr",
    },
    # ── Manuelle Quellen (Claude-in-Chrome, nicht automatisiert) ──
    "linkedin": {
        "name": "LinkedIn",
        "beschreibung": "LinkedIn-Suche via Claude-in-Chrome Extension (manuell, nicht automatisiert).",
        "methode": "Claude-in-Chrome (manuell)",
        "login_erforderlich": True,
        "zugriffsart": "browser_login",
        "konto_url": "https://www.linkedin.com/signup",
        "login_hinweis": "LinkedIn-Konto noetig und im Chrome eingeloggt; Easy-Apply-Stellen sind nur eingeloggt sichtbar.",
        "veraltet": True,
        "beta": True,
        "geschwindigkeit": "manuell",
        "warnung": "Manuell via Claude-in-Chrome. Verbraucht mehr Token als normale Quellen.",
        "hinweis": "Automatische Suche deaktiviert (#159). Nutze Claude-in-Chrome + stelle_manuell_anlegen().",
    },
    "xing": {
        "name": "XING",
        "beschreibung": "XING-Suche via Claude-in-Chrome Extension (manuell, nicht automatisiert).",
        "methode": "Claude-in-Chrome (manuell)",
        "login_erforderlich": True,
        "zugriffsart": "browser_login",
        "konto_url": "https://www.xing.com/signup",
        "login_hinweis": "XING-Konto noetig und im Chrome eingeloggt — sonst sind Suchergebnisse stark beschnitten.",
        "veraltet": True,
        "beta": True,
        "geschwindigkeit": "manuell",
        "warnung": "Manuell via Claude-in-Chrome. Verbraucht mehr Token als normale Quellen.",
        "hinweis": "Automatische Suche deaktiviert (#107/#159). Nutze Claude-in-Chrome + stelle_manuell_anlegen().",
    },
    "google_jobs": {
        "name": "Google Jobs (via Chrome)",
        "beschreibung": "Groesster Aggregator fuer DE-Stellen — aggregiert StepStone, Jobware, "
                         "Stellenanzeigen.de und Firmenwebseiten. Laeuft manuell ueber den "
                         "eingeloggten Chrome-Browser (keine Bot-Detection). #501",
        "methode": "Claude-in-Chrome (manuell)",
        # v1.6.5 (#541): kein klassischer Login-Flow noetig — aktivieren reicht.
        # Vorher loeste der Login-Button einen Backend-Fehler aus, weil
        # api_start_source_login keinen google_jobs-Branch hatte.
        "login_erforderlich": False,
        "zugriffsart": "browser_login",
        "konto_url": "https://accounts.google.com/signup",
        "login_hinweis": "Eingeloggtes Google-Konto in Chrome noetig — die Standortableitung der Jobsuche (udm=8) haengt daran.",
        "manueller_fallback": True,
        "geschwindigkeit": "manuell",
        "warnung": "Benoetigt einen Google-Account in Chrome mit Claude-in-Chrome-Extension.",
        "hinweis": "Tool jobsuche_starten liefert die Google-Jobs-URL — in Chrome oeffnen "
                    "und Treffer mit stelle_manuell_anlegen() uebernehmen. Kein Login-Click "
                    "im Dashboard noetig.",
        "beta": True,
    },
}


def zugriffsart_von(source_id: str) -> str:
    """v1.7.17 (#906): Zugriffsart einer Quelle — 'api' (laeuft
    automatisch), 'browser' (nur via Claude-in-Chrome) oder
    'browser_login' (Chrome UND eingeloggtes Konto noetig).

    Explizites Registry-Feld gewinnt; sonst Ableitung aus der Methode.
    Hintergrund: linkedin/xing/stepstone & Co. standen als 'aktiv' im
    Profil, liefen aber nie automatisch — nichts sagte dem Nutzer, dass
    (und welches) Konto noetig ist.
    """
    meta = SOURCE_REGISTRY.get(source_id) or {}
    if meta.get("zugriffsart"):
        return meta["zugriffsart"]
    methode = str(meta.get("methode", ""))
    if methode.startswith("Claude-in-Chrome"):
        return "browser_login" if meta.get("login_erforderlich") else "browser"
    return "api"


# v1.7.17 (#906 Befund 2): welche Quellen einen Stellentyp ueberhaupt
# bedienen. Sind ALLE Quellen eines konfigurierten Typs inaktiv, wird
# das Kriterium still nie ausgewertet — der Nutzer suchte monatelang
# nur Festanstellung, obwohl sein Profil beides sagte.
STELLENTYP_QUELLEN = {
    "freelance": {"freelance_de", "freelancermap", "gulp", "solcom"},
}


def build_search_keywords(db) -> dict:
    """Build source-specific search keywords from DB criteria.

    Returns dict with:
        general: list[str] — for API-based sources (bundesagentur, linkedin)
        stepstone_urls: list[str] — constructed StepStone search URLs
        hays_keywords: list[str] — lowercase keywords for sitemap filtering
        freelancermap_urls: list[str] — constructed Freelancermap URLs
        freelance_de_urls: list[str] — constructed freelance.de skill URLs
        indeed_queries: list[str] — search queries for Indeed
        monster_queries: list[str] — search queries for Monster
    """
    criteria = db.get_search_criteria()
    muss = criteria.get("keywords_muss", [])
    plus = criteria.get("keywords_plus", [])
    regionen = criteria.get("regionen", [])

    all_kw = muss + plus
    if not all_kw:
        return {}

    # First region or empty (used for location-aware URL building)
    region = regionen[0] if regionen else ""

    # General keywords (for API sources)
    general = list(all_kw)

    # StepStone: URL-based search (with region parameter if available)
    stepstone_urls = []
    for kw in all_kw:
        slug = kw.lower().replace(" ", "-").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
        base = f"https://www.stepstone.de/jobs/{slug}"
        if region:
            base += f"?where={quote(region)}"
        stepstone_urls.append(base)

    # Hays: lowercase keywords for sitemap URL matching
    hays_keywords = [kw.lower().replace(" ", "-") for kw in all_kw]

    # Freelancermap: slug-basierte URLs (#500). Die alte
    # /projektboerse.html?q=... Endpunkt leitet jetzt 301 auf /projekte
    # ohne Query-Parameter um. Das neue Schema ist /projekte/<keyword-slug>.
    freelancermap_urls = []
    for kw in all_kw:
        slug = kw.lower().strip().replace(" ", "-").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
        freelancermap_urls.append(f"https://www.freelancermap.de/projekte/{slug}")

    # freelance.de: skill-based URLs (keyword → Skill-Projekte)
    freelance_de_urls = [
        f"https://www.freelance.de/{quote(kw.replace(' ', '-'))}-Projekte"
        for kw in all_kw
    ]

    # Indeed/Monster: full search queries (with region if available)
    queries = list(all_kw)

    # #500: greenhouse_companies aus criteria durchschleusen, damit der User
    # eigene Greenhouse-Slugs (zusaetzlich zu DEFAULT_COMPANIES) konfigurieren
    # kann. Beispiel-Eintrag in search_criteria:
    #   {"greenhouse_companies": ["mein-arbeitgeber", "noch-einer"]}
    greenhouse_companies = criteria.get("greenhouse_companies", []) or []

    return {
        "general": general,
        "regionen": regionen,
        # linkedin/xing werten muss/plus separat aus, deshalb Original-Liste
        # unbearbeitet weiterreichen.
        "keywords_muss": list(muss),
        "keywords_plus": list(plus),
        "stepstone_urls": stepstone_urls,
        "hays_keywords": hays_keywords,
        "freelancermap_urls": freelancermap_urls,
        "freelance_de_urls": freelance_de_urls,
        "indeed_queries": queries,
        "monster_queries": queries,
        "greenhouse_companies": greenhouse_companies,
    }


# ── Scraper Dispatch ────────────────────────────────────────────

_SCRAPER_MAP = {
    "bundesagentur": ("bundesagentur", "search_bundesagentur"),
    "stepstone": ("stepstone", "search_stepstone"),
    "hays": ("hays", "search_hays"),
    "freelancermap": ("freelancermap", "search_freelancermap"),
    "freelance_de": ("freelance_de", "search_freelance_de"),
    "linkedin": ("linkedin", "search_linkedin"),
    "indeed": ("indeed", "search_indeed"),
    "xing": ("xing", "search_xing"),
    "monster": ("monster", "search_monster"),
    "ingenieur_de": ("ingenieur_de", "search_ingenieur_de"),
    "heise_jobs": ("heise_jobs", "search_heise_jobs"),
    "gulp": ("gulp", "search_gulp"),
    "solcom": ("solcom", "search_solcom"),
    "stellenanzeigen_de": ("stellenanzeigen_de", "search_stellenanzeigen_de"),
    "jobware": ("jobware", "search_jobware"),
    "ferchau": ("ferchau", "search_ferchau"),
    "adzuna": ("adzuna", "search_adzuna"),
    "kimeta": ("kimeta", "search_kimeta"),
    "jobspy_linkedin": ("jobspy_source", "search_jobspy_linkedin"),
    "jobspy_indeed": ("jobspy_source", "search_jobspy_indeed"),
    "jobspy_glassdoor": ("jobspy_source", "search_jobspy_glassdoor"),
    "jobspy_google": ("jobspy_source", "search_jobspy_google"),
    "arbeitnow": ("arbeitnow", "search_arbeitnow"),
    "greenhouse": ("greenhouse", "search_greenhouse"),
    "google_jobs": ("google_jobs", "search_google_jobs"),
    # v1.7.0-beta.34 (#590 Aufgabe A): Universelle Quellen
    "personio": ("personio", "search_personio"),
    "workable": ("workable", "search_workable"),
    "meinestadt": ("meinestadt", "search_meinestadt"),
    # v1.7.0-beta.35 (#590 Aufgabe B.5): Tech-Remote-Cluster
    "himalayas": ("himalayas", "search_himalayas"),
    "remotive": ("remotive", "search_remotive"),
    "remoteok": ("remoteok", "search_remoteok"),
    # v1.7.0-beta.36 (#590 Aufgabe B.3+B.4): Student- + Workday-Cluster
    "praktikum_de": ("praktikum_de", "search_praktikum_de"),
    "studentjob": ("studentjob", "search_studentjob"),
    "berufsstart": ("berufsstart", "search_berufsstart"),
    "workday_dax": ("workday_dax", "search_workday_dax"),
}


def _token_overlap(a: str, b: str) -> float:
    """Calculate token overlap ratio between two strings (#154)."""
    tokens_a = set(re.sub(r'[^a-zäöüß0-9\s]', '', a.lower()).split())
    tokens_b = set(re.sub(r'[^a-zäöüß0-9\s]', '', b.lower()).split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    return len(intersection) / min(len(tokens_a), len(tokens_b))


def _post_search_cleanup(db, jobs: list) -> dict:
    """Post-search cleanup: remove duplicates, blacklist, dismissed, mark applied (#153, #154).

    Returns dict with 'jobs' (cleaned list) and 'stats' (cleanup counters).
    """
    stats = {"duplikate_db": 0, "blacklist": 0, "bereits_bewertet": 0, "bereits_beworben": 0}

    # 1. Get existing job hashes from DB to skip already-known jobs
    try:
        existing_dismissed = {j["hash"] for j in db.get_dismissed_jobs()}
    except Exception:
        existing_dismissed = set()

    # 2. Get blacklist entries
    try:
        bl_entries = db.get_blacklist()
        bl_firms = {e["value"].lower() for e in bl_entries if e.get("type") == "firma"}
        bl_keywords = {e["value"].lower() for e in bl_entries if e.get("type") == "keyword"}
    except Exception:
        bl_firms, bl_keywords = set(), set()

    # 3. Get existing applications for fuzzy matching
    try:
        applications = db.get_applications()
        app_keys = []
        for a in applications:
            title = (a.get("title") or "").strip()
            company = (a.get("company") or "").strip()
            if title:
                app_keys.append({
                    "title": title, "company": company,
                    "id": a.get("id"), "status": a.get("status"),
                })
    except Exception:
        app_keys = []

    # 4. Get existing active job hashes to detect DB duplicates
    try:
        existing_active = {j["hash"] for j in db.get_active_jobs()}
    except Exception:
        existing_active = set()

    cleaned = []
    for job in jobs:
        h = job.get("hash", "")
        company = (job.get("company") or "").lower()
        title = (job.get("title") or "").lower()

        # Skip already-dismissed (previously rated as passt_nicht)
        if h in existing_dismissed:
            stats["bereits_bewertet"] += 1
            continue

        # Skip DB duplicates (already in active jobs)
        if h in existing_active:
            stats["duplikate_db"] += 1
            continue

        # Skip blacklisted companies (Substring-Match: "Musterfirma" matcht "Musterfirma Software GmbH")
        if any(firm in company or company in firm for firm in bl_firms):
            stats["blacklist"] += 1
            continue

        # Skip blacklisted keywords in title/company
        if bl_keywords and any(kw in title or kw in company for kw in bl_keywords):
            stats["blacklist"] += 1
            continue

        # Fuzzy match against existing applications (#154)
        matched_app = None
        for ak in app_keys:
            # Exact company match + title token overlap > 70%
            if ak["company"] and company and ak["company"].lower() == company:
                overlap = _token_overlap(ak["title"], job.get("title", ""))
                if overlap >= 0.7:
                    matched_app = ak
                    break
            # No company but high title overlap
            elif not ak["company"] and _token_overlap(ak["title"], job.get("title", "")) >= 0.85:
                matched_app = ak
                break

        if matched_app:
            stats["bereits_beworben"] += 1
            # Mark but don't remove — add application info to job
            job["_matched_application"] = {
                "id": matched_app["id"],
                "status": matched_app["status"],
            }

        cleaned.append(job)

    total_removed = stats["duplikate_db"] + stats["blacklist"] + stats["bereits_bewertet"]
    if total_removed or stats["bereits_beworben"]:
        logger.info(
            "Post-Search Cleanup: %d entfernt (DB-Duplikate: %d, Blacklist: %d, "
            "bereits bewertet: %d), %d als bereits beworben markiert",
            total_removed, stats["duplikate_db"], stats["blacklist"],
            stats["bereits_bewertet"], stats["bereits_beworben"],
        )

    return {"jobs": cleaned, "stats": stats}


def run_search(db, job_id: str, params: dict):
    """Run a background job search across configured sources.

    Args:
        db: Database instance
        job_id: Background job ID for progress reporting
        params: Search parameters (keywords, quellen, etc.)
    """
    quellen = params.get("quellen", [])
    total = len(quellen)
    all_jobs = []

    # Build dynamic keywords from DB if not explicitly provided
    if not params.get("keywords"):
        params["keywords"] = build_search_keywords(db)

    # Deprecated sources (#159): skip with warning
    _deprecated_sources = {"linkedin", "xing"}

    # Per-source timeout (#500 / Real-Run-Bilanz 2026-04-25): pauschale
    # 90s sind fuer mehrere Quellen zu kurz, wenn der User viele Keywords
    # konfiguriert hat. Quellen die regelmaessig durchliefen aber knapp am
    # Limit waren bekommen jetzt einen erhoehten Timeout. Stepstone bleibt
    # bei 180s Sonderbehandlung, alle anderen aus der Map werden hier
    # nachgeschlagen.
    _SOURCE_TIMEOUT = 90
    _STEPSTONE_TIMEOUT = 180
    _SOURCE_TIMEOUT_MAP = {
        "stepstone": 180,
        "bundesagentur": 180,    # Detail-API-Calls fuer 1980+ Treffer
        "freelance_de": 180,     # ~40 Keywords x Detail-Page
        "jobspy_indeed": 150,    # Lief in Real-Run 114s — knapp am 90s-Limit
        "jobspy_linkedin": 120,  # LinkedIn-Rate-Limit pro Page
        "freelancermap": 120,    # Slug-URL pro Keyword
        "indeed": 120,           # Playwright + Anti-Bot
        "monster": 120,          # Playwright + Anti-Bot
        # Schnelle API-Quellen behalten 90s (default):
        # arbeitnow, greenhouse, hays, jobspy_glassdoor, jobspy_google,
        # stellenanzeigen_de, jobware, kimeta, heise_jobs, ferchau, gulp,
        # solcom, ingenieur_de, google_jobs, linkedin, xing
    }

    def _timeout_for(quelle: str) -> int:
        return _SOURCE_TIMEOUT_MAP.get(quelle, _SOURCE_TIMEOUT)

    skipped_sources = []

    # #234: Playwright-basierte Scraper sequentiell, httpx-basierte parallel
    _PLAYWRIGHT_SOURCES = {"stepstone", "indeed", "monster", "freelancermap"}

    # #402: Sort sources by reliability (fast API sources first, beta/unreliable last)
    _SOURCE_PRIORITY = {
        "bundesagentur": 1, "hays": 2, "freelance_de": 3, "ingenieur_de": 4,
        "stepstone": 10, "indeed": 11, "freelancermap": 12, "monster": 13,
    }
    quellen = sorted(quellen, key=lambda q: _SOURCE_PRIORITY.get(q, 9))
    # #252: Stepstone immer als letztes Portal starten (already handled by priority above)

    def _run_with_loop(fn, p):
        """Run scraper in thread with fresh asyncio event loop (#238)."""
        import asyncio
        import sys
        try:
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            asyncio.set_event_loop(asyncio.new_event_loop())
        except Exception:
            pass
        return fn(p)

    # #499 Beta.12: Feature-Flag flip — wenn aktiv, Suche ueber Adapter-Pfad
    from ..feature_flags import is_enabled as _flag_enabled
    _use_adapters = _flag_enabled("scraper_adapter_v2")

    def _load_scraper(quelle):
        """Load scraper function by source name.

        Mit Flag `scraper_adapter_v2` laueft die Suche ueber den
        registrierten Adapter (Fehler-Isolation, typisierte Rueckgabe).
        Ohne Flag laeuft der alte direkte Aufruf unveraendert weiter.
        """
        if _use_adapters:
            from .adapters import get_adapter
            adapter = get_adapter(quelle)
            if adapter is None:
                raise ImportError(f"Kein Adapter registriert: {quelle}")

            def _adapter_call(p):
                result = adapter.search(p)
                # Legacy-Pipeline erwartet list[dict] — Adapter liefert
                # typisierte JobPostings. Status-Fehler werden als Exception
                # propagiert, damit das bestehende Error-Handling greift.
                from .adapters import AdapterStatus
                if result.status in (AdapterStatus.ERROR, AdapterStatus.NOT_CONFIGURED):
                    raise RuntimeError(result.message or result.status.value)
                return [posting.to_job_dict() for posting in result.postings]

            return _adapter_call

        module_name, func_name = _SCRAPER_MAP[quelle]
        import importlib
        mod = importlib.import_module(f".{module_name}", package=__package__)
        return getattr(mod, func_name)

    # #432: Filter out auto-deactivated scrapers
    # #668 (B21, beta.85): ZUSAETZLICH zu is_active=0 jetzt auch
    # consecutive_failures>=5 als "dauerhaft defekt" behandeln. Hintergrund:
    # ferchau/gulp/heise_jobs/kimeta/solcom standen mit 8 Fehlern in
    # Serie weiter auf is_active=1 (Auto-Deaktivierung griff nicht) und
    # blockierten den Gesamt-Job bis zum 10-Min-Timeout. Hard-Skip-Schwelle
    # = 5: kompromiss zwischen Toleranz und Selbstschutz.
    _deactivated = set()
    _broken_skipped: dict[str, int] = {}
    try:
        for h in db.get_scraper_health():
            name = h.get("scraper_name")
            if not name:
                continue
            if not h.get("is_active"):
                _deactivated.add(name)
                continue
            # #668: dauerhaft defekt obwohl is_active=1
            failures = h.get("consecutive_failures") or 0
            if failures >= 5:
                _deactivated.add(name)
                _broken_skipped[name] = failures
    except Exception:
        pass

    # #234: Separate httpx (parallel) and playwright (sequential) sources
    # #500: Defekt-Flag in SOURCE_REGISTRY blockiert die Quelle automatisch.
    httpx_quellen = []
    sequential_quellen = []
    defekt_skipped = {}
    for quelle in quellen:
        info = SOURCE_REGISTRY.get(quelle, {})
        if info.get("defekt"):
            grund = info.get("defekt_grund") or "Quelle als defekt markiert"
            logger.warning("%s: defekt — %s. Manuell ueber Chrome-Extension nutzen.", quelle, grund)
            skipped_sources.append(quelle)
            defekt_skipped[quelle] = grund
        elif quelle in _deprecated_sources:
            logger.warning(
                "%s: Automatische Suche deaktiviert. Nutze Claude-in-Chrome + stelle_manuell_anlegen().", quelle)
            skipped_sources.append(quelle)
        elif quelle in _deactivated:
            broken_n = _broken_skipped.get(quelle)
            if broken_n:
                # #668: dauerhaft-defekt-Skip (consecutive_failures >= 5)
                logger.warning(
                    "%s: Auto-skip — %d Fehler in Serie. Reaktivierung "
                    "via scraper_diagnose().",
                    quelle, broken_n,
                )
            else:
                logger.info("%s: Auto-deaktiviert (zu viele Fehler). Reaktivierung via scraper_diagnose().", quelle)
            skipped_sources.append(quelle)
        elif quelle not in _SCRAPER_MAP:
            logger.warning("Unbekannte Quelle: %s", quelle)
            skipped_sources.append(quelle)
        elif quelle in _PLAYWRIGHT_SOURCES:
            sequential_quellen.append(quelle)
        else:
            httpx_quellen.append(quelle)

    completed = 0

    # #316: Per-Source Status-Tracking (Fokus-Modus)
    source_status = {}  # quelle -> {"status": ok|timeout|error|skipped, "count": N, "time_s": N}

    for q in skipped_sources:
        if q in defekt_skipped:
            source_status[q] = {
                "status": "skipped",
                "count": 0,
                "time_s": 0,
                "detail": f"defekt: {defekt_skipped[q]}",
            }
        elif q in _broken_skipped:
            # #668: dauerhaft defekt, automatisch geskippt
            source_status[q] = {
                "status": "skipped",
                "count": 0,
                "time_s": 0,
                "detail": (
                    f"auto-skip: {_broken_skipped[q]} Fehler in Serie. "
                    "scraper_diagnose() zum Reaktivieren."
                ),
            }
        else:
            source_status[q] = {"status": "skipped", "count": 0, "time_s": 0, "detail": "deprecated"}

    # Phase 1: Run httpx-based scrapers in parallel (#234)
    if httpx_quellen:
        # v1.6.9 (#551): Initialisierungs-Phase explizit signalisieren —
        # vorher zeigte die UI 60-90s lang "0%" mit statischem Text und
        # sprang dann auf 11% → User dachte das System haengt. Jetzt 5%
        # mit klarem "Initialisiere..."-Label.
        db.update_background_job(
            job_id, "running", progress=5,
            message=f"Initialisiere {len(httpx_quellen)} Quellen..."
        )
        parallel_executor = ThreadPoolExecutor(max_workers=min(4, len(httpx_quellen)))
        futures = {}
        _start_times = {}
        for quelle in httpx_quellen:
            try:
                search_func = _load_scraper(quelle)
                timeout = _timeout_for(quelle)
                _start_times[quelle] = time.time()
                futures[parallel_executor.submit(_run_with_loop, search_func, params)] = (quelle, timeout)
            except ImportError as e:
                logger.warning("Scraper %s nicht verfügbar: %s", quelle, e)
                skipped_sources.append(quelle)
                source_status[quelle] = {"status": "error", "count": 0, "time_s": 0,
                                         "detail": str(e), "error_class": ERROR_CLASS_KAPUTT}

        # #668: Ergebnisse in FERTIGSTELLUNGS-Reihenfolge einsammeln (nicht in
        # Submit-Reihenfolge). Vorher blockierte EIN langsamer, zuerst
        # submitteter Scraper die Fortschrittsanzeige aller schnellen — die UI
        # stand bis zu 90-180s bei 5% ("laeuft komplett in Timeout / 0%").
        # Zusaetzlich ein globales Phasen-Budget: nach max(Quellen-Timeout)+15s
        # werden alle noch haengenden Scraper gemeinsam als timeout markiert,
        # statt seriell auf jeden einzeln bis zu seinem Timeout zu warten.
        phase_budget = max((t for _, t in futures.values()), default=_SOURCE_TIMEOUT) + 15
        pending = dict(futures)  # future -> (quelle, timeout)
        phase_start = time.time()
        try:
            for future in as_completed(futures, timeout=phase_budget):
                quelle, timeout = pending.pop(future)
                elapsed = round(time.time() - _start_times.get(quelle, phase_start), 1)
                try:
                    jobs = future.result()
                    all_jobs.extend(jobs)
                    logger.info("%s: %d Stellen gefunden", quelle, len(jobs))
                    source_status[quelle] = {"status": "ok", "count": len(jobs), "time_s": elapsed}
                except Exception as e:
                    logger.error("Fehler bei %s: %s", quelle, e, exc_info=True)
                    skipped_sources.append(quelle)
                    source_status[quelle] = {"status": "error", "count": 0, "time_s": elapsed,
                                             "detail": str(e)[:100],
                                             "error_class": classify_scraper_error(e)}
                completed += 1
                # #316: Fokus-Modus Progress mit Per-Source-Status
                ok_count = sum(1 for s in source_status.values() if s["status"] == "ok")
                db.update_background_job(
                    job_id, "running",
                    progress=int((completed / total) * 100),
                    message=f"{quelle}: {source_status[quelle]['status']} ({source_status[quelle]['count']} Stellen) | {ok_count}/{completed} Quellen OK"
                )
        except FuturesTimeoutError:
            # #668: globales Phasen-Budget erreicht — die restlichen Scraper
            # haengen. Gemeinsam als timeout markieren statt den Gesamt-Job
            # weiter zu blockieren. Die Threads laufen im Hintergrund aus
            # (shutdown wait=False), ihre Ergebnisse werden verworfen.
            for _f, (quelle, timeout) in pending.items():
                logger.warning("%s: Phasen-Budget %ds erreicht — uebersprungen", quelle, phase_budget)
                skipped_sources.append(quelle)
                source_status[quelle] = {"status": "timeout", "count": 0, "time_s": phase_budget,
                                         "error_class": ERROR_CLASS_SERVER_WEG}
                completed += 1
            ok_count = sum(1 for s in source_status.values() if s["status"] == "ok")
            db.update_background_job(
                job_id, "running",
                progress=int((completed / total) * 100),
                message=f"{len(pending)} Quelle(n) im Timeout uebersprungen | {ok_count} OK"
            )
        parallel_executor.shutdown(wait=False)

    # Phase 2: Run playwright-based scrapers sequentially (#234)
    if sequential_quellen:
        est_time = len(sequential_quellen) * 60  # ~60s pro Browser-Quelle
        source_names = ", ".join(
            SOURCE_REGISTRY.get(q, {}).get("name", q) for q in sequential_quellen
        )
        db.update_background_job(
            job_id, "running",
            progress=int((completed / total) * 100),
            message=f"Browser-Quellen starten ({source_names}) — kann {est_time // 60}-{est_time * 2 // 60} Min dauern..."
        )

    for quelle in sequential_quellen:
        completed += 1
        quelle_name = SOURCE_REGISTRY.get(quelle, {}).get("name", quelle)
        db.update_background_job(
            job_id, "running",
            progress=int((completed / total) * 100),
            message=f"Durchsuche {quelle_name}... ({completed}/{total}, Browser-Quelle)"
        )
        _start = time.time()
        try:
            search_func = _load_scraper(quelle)
            timeout = _STEPSTONE_TIMEOUT if quelle == "stepstone" else _SOURCE_TIMEOUT

            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(_run_with_loop, search_func, params)
            try:
                jobs = future.result(timeout=timeout)
            except FuturesTimeoutError:
                logger.warning("%s: Timeout nach %ds — uebersprungen", quelle, timeout)
                executor.shutdown(wait=False, cancel_futures=True)
                skipped_sources.append(quelle)
                source_status[quelle] = {"status": "timeout", "count": 0, "time_s": timeout,
                                         "error_class": ERROR_CLASS_SERVER_WEG}
                continue
            finally:
                executor.shutdown(wait=False)

            elapsed = round(time.time() - _start, 1)
            all_jobs.extend(jobs)
            logger.info("%s: %d Stellen gefunden", quelle, len(jobs))
            source_status[quelle] = {"status": "ok", "count": len(jobs), "time_s": elapsed}
        except ImportError as e:
            logger.warning("Scraper %s nicht verfügbar: %s", quelle, e)
            skipped_sources.append(quelle)
            source_status[quelle] = {"status": "error", "count": 0, "time_s": 0,
                                     "detail": str(e)[:100], "error_class": ERROR_CLASS_KAPUTT}
        except Exception as e:
            elapsed = round(time.time() - _start, 1)
            logger.error("Fehler bei %s: %s", quelle, e, exc_info=True)
            skipped_sources.append(quelle)
            source_status[quelle] = {"status": "error", "count": 0, "time_s": elapsed,
                                     "detail": str(e)[:100],
                                     "error_class": classify_scraper_error(e)}

    # v1.6.5 (#550): Defensiv NaN-Strings ("nan", "none", "<NA>") aus
    # Firmenname filtern, falls ein Scraper sie versehentlich durchlaesst.
    _nan_strings = {"nan", "none", "null", "<na>", "n/a"}
    for job in all_jobs:
        company = job.get("company")
        if isinstance(company, str) and company.strip().lower() in _nan_strings:
            job["company"] = "Nicht angegeben"
        elif company is None:
            job["company"] = "Nicht angegeben"

    # Deduplicate — first by hash, then cross-source by normalized title+company (#59)
    seen_hashes = set()
    seen_titles = {}  # normalized_key -> first job
    unique = []
    duplicates_merged = 0
    for job in all_jobs:
        if job["hash"] in seen_hashes:
            continue
        seen_hashes.add(job["hash"])

        # Cross-source dedup: normalize title + company
        norm_key = re.sub(r'[^a-z0-9]', '', f"{job.get('company','')}{job.get('title','')}".lower())
        if norm_key in seen_titles:
            # Keep the one with more description text
            existing = seen_titles[norm_key]
            if len(job.get("description", "") or "") > len(existing.get("description", "") or ""):
                unique.remove(existing)
                unique.append(job)
                seen_titles[norm_key] = job
            duplicates_merged += 1
            continue
        seen_titles[norm_key] = job
        unique.append(job)

    if duplicates_merged:
        logger.info("Cross-Source Duplikate entfernt: %d", duplicates_merged)

    # Score, extract/estimate salary, and save
    criteria = db.get_search_criteria()

    # Enrich with application signals (#68)
    try:
        apps = db.get_applications()
        criteria["_applied_titles"] = [
            a.get("title", "").lower() for a in apps
            if a.get("title") and a.get("status") not in ("abgelehnt", "zurueckgezogen")
        ]
    except Exception:
        criteria["_applied_titles"] = []
    # v1.7.22 (#940): Filterkaskade mitzaehlen. Ohne diese Zahlen sieht
    # der Nutzer nur "7.100 Rohtreffer -> 15 Stellen" und kann nicht
    # beurteilen, ob die Suche zu streng oder die Quelle schlecht war.
    filterstufen: dict[str, int] = {}

    for job in unique:
        job["score"] = calculate_score(job, criteria)

        # Auto-extract salary from description/salary_info
        if not job.get("salary_min"):
            text = f"{job.get('description', '')} {job.get('salary_info', '')} {job.get('title', '')}"
            s_min, s_max, s_type = extract_salary_from_text(text)
            if s_min:
                job["salary_min"] = s_min
                job["salary_max"] = s_max
                job["salary_type"] = s_type
                job["salary_estimated"] = 0

        # Estimate if still no salary found
        if not job.get("salary_min"):
            s_min, s_max, s_type = estimate_salary(
                job.get("title", ""), job.get("employment_type", ""), job.get("location", "")
            )
            job["salary_min"] = s_min
            job["salary_max"] = s_max
            job["salary_type"] = s_type
            job["salary_estimated"] = 1

    # Heuristik: employment_type aus Quelle/Titel/Beschreibung erkennen (#151, #201)
    _freelance_sources = {"freelance_de", "freelancermap", "gulp", "solcom"}
    _freelance_keywords = {"freelance", "freiberuflich", "freiberufler", "kontingent",
                           "projektbasiert", "auf projektbasis", "interim",
                           "interims", "interimsmanag"}
    for job in unique:
        if job.get("employment_type", "festanstellung") == "festanstellung":
            # Source-based detection (#201)
            if job.get("source") in _freelance_sources:
                job["employment_type"] = "freelance"
                continue
            # Hays with hourly rate → freelance (#201)
            if job.get("source") == "hays" and job.get("salary_type") == "hourly":
                job["employment_type"] = "freelance"
                continue
            # Keyword-based detection in title and description
            haystack = f"{job.get('title', '')} {job.get('description', '')[:500]}".lower()
            if any(kw in haystack for kw in _freelance_keywords):
                job["employment_type"] = "freelance"

    # Geocoding: calculate distance for jobs with location (#167)
    try:
        from ..services.geocoding_service import get_user_coordinates, geocode_and_calculate_distance
        user_coords = get_user_coordinates(db)
        if user_coords:
            geocoded_count = 0
            needs_geocoding = [j for j in unique if j.get("location") and not j.get("distance_km")]
            total_geocode = len(needs_geocoding)
            if total_geocode > 50:
                # #215: Warnung bei vielen Geocoding-Requests
                est_seconds = total_geocode * 1  # 1 req/sec
                db.update_background_job(
                    job_id, "running",
                    progress=int(90),
                    message=f"Geocoding: {total_geocode} Standorte berechnen (~{est_seconds // 60} Min)..."
                )
                logger.info("Geocoding: %d Standorte zu berechnen (~%d Sek bei 1 Req/Sek) (#215)",
                            total_geocode, est_seconds)
            for i, job in enumerate(needs_geocoding):
                loc = job.get("location", "")
                dist = geocode_and_calculate_distance(loc, user_coords[0], user_coords[1])
                if dist is not None:
                    job["distance_km"] = dist
                    geocoded_count += 1
                # Update progress periodically during geocoding (#215)
                if total_geocode > 20 and i > 0 and i % 20 == 0:
                    db.update_background_job(
                        job_id, "running",
                        progress=int(90 + (i / total_geocode) * 9),
                        message=f"Geocoding: {i}/{total_geocode} Standorte..."
                    )
            if geocoded_count:
                logger.info("Geocoding: %d Stellen mit Entfernung berechnet", geocoded_count)
    except Exception as e:
        logger.debug("Geocoding in Pipeline fehlgeschlagen (nicht kritisch): %s", e)

    # #251 / beta.26: Stellenalter automatisch begrenzen
    # Strategie:
    #   - Wenn last_search_at existiert: max_age = max(7, intervall*2)
    #     Beispiel: vor 3 Tagen gesucht -> max_age 7 Tage (eng)
    #     Beispiel: vor 14 Tagen gesucht -> max_age 28 Tage (offen)
    #   - Ohne last_search_at (frische Installation / neue Quelle):
    #     Default 21 Tage. User soll nicht mit jahrealten Stellen
    #     erschlagen werden, auch wenn er das erste Mal sucht.
    #   - Stellen ohne Datum (weder found_at noch veroeffentlicht_am):
    #     bleiben drin (defensiv — wir wissen nicht ob sie alt sind).
    # Bug-Fix (User-Feedback beta.25): Vorher wurde `published_at`
    # gepruft, das DB-Feld heisst aber `veroeffentlicht_am` -> Filter
    # griff bei fast keiner Stelle.
    try:
        from datetime import datetime, timedelta
        now_dt = datetime.now()
        last_search_at = db.get_profile_setting("last_search_at", None)
        if last_search_at:
            last_dt = datetime.fromisoformat(last_search_at)
            interval = (now_dt - last_dt).days
            max_age_days = max(7, interval * 2)
            reason = f"intervall*2 seit letzter Suche ({interval}d)"
        else:
            max_age_days = 21
            reason = "Default fuer frische Installation/neue Quelle"
        cutoff_dt = (now_dt - timedelta(days=max_age_days)).isoformat()
        cutoff_date = cutoff_dt[:10]
        before_age = len(unique)
        unique = [
            j for j in unique
            if (j.get("found_at") or j.get("veroeffentlicht_am") or "9999")[:10] >= cutoff_date
        ]
        if before_age > len(unique):
            logger.info(
                "Stellenalter-Filter: %d von %d Stellen aelter als %d Tage entfernt (%s)",
                before_age - len(unique), before_age, max_age_days, reason
            )
    except Exception as e:
        logger.debug("Stellenalter-Filter fehlgeschlagen: %s", e)

    # Filter out zero-score jobs (#53) — no keyword match = irrelevant
    # v1.7.22 (#940): Stufe 0 der Filterkaskade. Die Zaehler wandern ins
    # Ergebnis, nicht nur ins Log — ohne sie sieht der Nutzer nur, dass
    # von 7.100 Rohtreffern 15 uebrig blieben, aber nicht warum.
    min_score_threshold = criteria.get("min_score_schwelle", 1)
    before = len(unique)
    ohne_muss = sum(1 for j in unique if j.get("_ko_kein_muss"))
    unique, verworfen_schwelle = _filter_nach_schwelle(unique, min_score_threshold)
    filterstufen["kein_muss_keyword"] = ohne_muss
    filterstufen["unter_schwelle"] = max(0, verworfen_schwelle - ohne_muss)
    if before > len(unique):
        logger.info("Score-Filter: %d von %d Stellen verworfen (Score < %d, "
                    "davon %d ohne MUSS-Keyword)",
                    before - len(unique), before, min_score_threshold, ohne_muss)

    # === Post-Search Cleanup (#153, #154) ===
    cleanup = _post_search_cleanup(db, unique)
    unique = cleanup["jobs"]

    save_stats = db.save_jobs(unique) or {}
    new_per_source = save_stats.get("new_per_source", {}) if isinstance(save_stats, dict) else {}
    db.set_profile_setting("last_search_at", time.strftime("%Y-%m-%dT%H:%M:%S"))

    # v1.6.5 (#553): pro Quelle ermitteln, wie viele Stellen nach Filtering
    # uebrig geblieben sind (= in `unique` enthalten).
    filtered_per_source: dict[str, int] = {}
    for j in unique:
        s = j.get("source") or "unbekannt"
        filtered_per_source[s] = filtered_per_source.get(s, 0) + 1

    # #432: Persist scraper health after each search
    for quelle, status_info in source_status.items():
        try:
            db.update_scraper_health(
                quelle, status_info["status"],
                status_info.get("count", 0),
                status_info.get("time_s", 0),
                status_info.get("detail"),
                filtered_count=filtered_per_source.get(quelle, 0),
                new_count=new_per_source.get(quelle, 0),
                error_class=status_info.get("error_class"),  # #720
            )
        except Exception as e:
            logger.debug("Scraper health update failed for %s: %s", quelle, e)

    # #432: Auto-deactivate scrapers with 10+ consecutive failures.
    # #721: Backstop nur noch fuer Quellen OHNE Fehlerklasse (Altdaten) bzw.
    # ohne geplanten Probe-Run. Klassifizierte Fehler werden bereits in
    # update_scraper_health differenziert behandelt (server_weg/blockiert ->
    # pausiert-mit-Probe, tot/kaputt -> hart). Eine pausierte Quelle
    # (reactivate_at gesetzt) wird hier NICHT hart abgeschaltet.
    try:
        for h in db.get_scraper_health():
            if (h.get("consecutive_failures", 0) >= 10 and h.get("is_active")
                    and not h.get("reactivate_at")):
                db.toggle_scraper(h["scraper_name"], False)
                logger.info("Scraper '%s' nach %d Fehlern auto-deaktiviert",
                            h["scraper_name"], h["consecutive_failures"])
    except Exception as e:
        logger.debug("Scraper auto-deactivation check failed: %s", e)

    result_data = {
        "total": len(unique),
        "quellen": {q: sum(1 for j in unique if j.get("source") == q) for q in quellen},
        "quellen_status": source_status,  # #316: Per-Source Fokus-Modus
        "adapter_pfad": "v2" if _use_adapters else "legacy",  # #499 Beta.12
    }
    if cleanup["stats"]:
        result_data["bereinigung"] = cleanup["stats"]
    if any(filterstufen.values()):
        result_data["filterstufen"] = dict(filterstufen)

    # v1.6.9 (#548): Counter konsequent aus source_status ableiten — sonst
    # kommen Diskrepanzen zwischen `total` (Eingangs-Liste) und `source_status`
    # (tatsaechlich gelaufene Quellen) zustande, die in "10/18" enden ohne
    # dass sich die Mathematik nachvollziehen laesst.
    ok_count = sum(1 for s in source_status.values() if s.get("status") == "ok")
    skipped_count = sum(1 for s in source_status.values() if s.get("status") == "skipped")
    timeout_count = sum(1 for s in source_status.values() if s.get("status") == "timeout")
    error_count = sum(1 for s in source_status.values() if s.get("status") == "error")
    sources_total = len(source_status)
    successful_sources = ok_count
    msg_parts = [
        f"{len(unique)} Stellen gefunden ({ok_count} von {sources_total} Quellen ok"
        + (f", {skipped_count} uebersprungen" if skipped_count else "")
        + (f", {timeout_count} Timeout" if timeout_count else "")
        + (f", {error_count} Fehler" if error_count else "")
        + ")"
    ]
    # #337: Nutzerfreundliche Meldungen bei Timeout/Fehler
    timeout_sources = [q for q, s in source_status.items() if s.get("status") == "timeout"]
    error_sources = [q for q, s in source_status.items() if s.get("status") == "error"]
    if timeout_sources:
        names = ", ".join(SOURCE_REGISTRY.get(q, {}).get("name", q) for q in timeout_sources)
        msg_parts.append(f"Timeout: {names} (Tipp: Lass Claude gezielt auf diesen Portalen suchen)")
    if error_sources:
        names = ", ".join(SOURCE_REGISTRY.get(q, {}).get("name", q) for q in error_sources)
        msg_parts.append(f"Fehler: {names}")
    other_skipped = [q for q in skipped_sources if q not in timeout_sources and q not in error_sources]
    if other_skipped:
        msg_parts.append(f"Uebersprungen: {', '.join(other_skipped)}")
    stats = cleanup["stats"]
    if stats.get("duplikate_db") or stats.get("blacklist") or stats.get("bereits_bewertet") or stats.get("bereits_beworben"):
        details = []
        if stats.get("duplikate_db"):
            details.append(f"{stats['duplikate_db']} bereits bekannt")
        if stats.get("blacklist"):
            details.append(f"{stats['blacklist']} Blacklist")
        if stats.get("bereits_bewertet"):
            details.append(f"{stats['bereits_bewertet']} bereits bewertet")
        if stats.get("bereits_beworben"):
            details.append(f"{stats['bereits_beworben']} bereits beworben")
        msg_parts.append(f"Bereinigt: {', '.join(details)}")

    # G17 (#744, v1.7.4): 0-Treffer-Diagnostik — sagen WARUM nichts kam,
    # statt einen Einsteiger mit "0 Stellen gefunden" raten zu lassen.
    if not unique:
        diagnose = zero_treffer_diagnose(
            stats, source_status, ok_count, error_count, timeout_count)
        result_data["diagnose"] = diagnose
        msg_parts.append(diagnose)

    db.update_background_job(
        job_id, "fertig", progress=100,
        message=" | ".join(msg_parts),
        result=result_data,
    )


def zero_treffer_diagnose(stats, source_status, ok_count, error_count,
                          timeout_count) -> str:
    """G17 (#744, v1.7.4): Erklaert, warum eine Suche 0 NEUE Stellen brachte.

    Prioritaet: (1) alles bereinigt/bekannt, (2) gar keine Quelle gelaufen,
    (3) alle Quellen mit Fehler/Timeout, (4) alle uebersprungen,
    (5) Quellen ok, aber Suchbegriffe treffen nichts.
    """
    entfernt = sum(
        (stats or {}).get(k, 0)
        for k in ("duplikate_db", "blacklist", "bereits_bewertet", "bereits_beworben")
    )
    if entfernt:
        return (
            f"Die Quellen lieferten Treffer, aber alle {entfernt} waren "
            "schon bekannt, bewertet oder geblacklistet — es gibt gerade "
            "nichts Neues. Bei haeufigen Suchen ist das normal."
        )
    if not source_status:
        return (
            "Keine Quelle wurde tatsaechlich durchsucht — alle "
            "ausgewaehlten Quellen wurden vorab uebersprungen "
            "(defekt, deaktiviert oder nur manuell nutzbar). "
            "Pruefe quellen_health_check() oder aktiviere andere Quellen."
        )
    if ok_count == 0 and (error_count or timeout_count):
        return (
            f"Keine Quelle hat geliefert ({error_count} Fehler, "
            f"{timeout_count} Timeout). Vermutlich Netzwerk- oder "
            "Portal-Problem — pruefe quellen_health_check() und "
            "versuche es spaeter erneut."
        )
    if ok_count == 0:
        return (
            "Alle Quellen wurden uebersprungen (defekt oder deaktiviert). "
            "Aktiviere andere Quellen (Dashboard → Einstellungen → "
            "Job-Quellen) oder pruefe quellen_health_check()."
        )
    return (
        f"{ok_count} Quelle(n) liefen fehlerfrei, fanden aber nichts "
        "zu deinen Suchbegriffen. Versuche breitere Keywords "
        "(weniger MUSS-Begriffe), pruefe Region/Entfernung oder "
        "nimm weitere Quellen dazu (keyword_vorschlaege() hilft)."
    )


def stelle_hash(domain: str, title: str) -> str:
    """Create a deterministic hash for deduplication.

    Uses domain + normalized title to prevent duplicates from URL changes.
    """
    normalized = re.sub(r'[^a-z0-9]', '', title.lower())
    raw = f"{domain}|{normalized}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# Heuristik fuer "URL zeigt auf Suchergebnis-Seite statt konkrete Stellenanzeige" (#436).
# Wenn eine Stellen-URL auf eine generische Suchseite zeigt, kann der User sie nicht
# direkt oeffnen — der Scraper hat keine Detail-URL extrahiert, nur die Such-URL.
_SEARCH_URL_PATH_PATTERNS = (
    "/jobs/search",           # linkedin.com/jobs/search/?keywords=...
    "/projekte?",             # freelancermap.de/projekte?query=, freelance.de/projekte?skills=
    "/projekte/",             # Liste/Kategorie-Seiten ohne Detail-Slug
    "/projects/search",
    "/search/project",        # freelance.de/search/project.php
    "/stellenangebote?",      # stepstone /stellenangebote?where=...
    "/jobs?",                 # indeed.de/jobs?q=
    "/jobs/suche",            # xing.com/jobs/suche?...
    "/suche?",                # generic /suche?q=
    "/jobsuche/suche",        # arbeitsagentur.de/jobsuche/suche (auch ohne ?)
)
# v1.7.9 (#763): Pfade, die als GANZER Pfad (Portal-Wurzel, ohne weiteren
# Slug-Anteil) eine Suchseite sind — z.B. indeed.de/jobs, xing.com/jobs,
# arbeitsagentur.de/jobsuche. Bewusst NUR als exakter Pfad: "/jobs/12345"
# ist eine echte XING-Detail-URL und darf NICHT als Suche gelten, sonst
# blockieren wir stellenbeschreibung_nachladen (Regression).
_SEARCH_URL_BARE_PATHS = (
    "/jobs", "/jobsuche", "/stellenangebote", "/stellenmarkt",
    "/suche", "/projekte", "/jobboerse",
)
_SEARCH_URL_QUERY_KEYS = (
    "query=", "keywords=", "q=", "skills=", "search=",
    "searchterm=", "what=", "suchbegriff=",
)
# Konkrete Detail-URL-Marker — gewinnen gegenueber generischen Such-Pattern.
_DETAIL_URL_PATH_MARKERS = (
    "/jobs/view/",            # linkedin.com/jobs/view/1234
    "/projekt/",              # freelancermap.de/projekt/titel-id
    "/project/",
    "/stellenanzeige",        # stepstone konkrete Anzeige
    "/stellenangebote--",     # stepstone slug-artige Detail-URLs (SEO-Format mit --)
    "/job/view",
    "/viewjob",               # indeed.com/viewjob?jk=...
    "/stelle/",
    "/position/",
)


def is_search_result_url(url: str) -> bool:
    """Return True if *url* looks like a generic search result page rather
    than a concrete job listing (#436).

    Best-effort heuristic: concrete detail-URL markers (``/jobs/view/``,
    ``/projekt/<slug>``, ``/viewjob?jk=``, ...) outrank the generic search
    patterns, so detail URLs that happen to contain a query string are
    still classified as details. URLs that match known search paths or
    that carry typical search query parameters (``?keywords=``, ``?q=``,
    ...) are classified as search URLs.

    Empty/missing URLs return False — callers handle missing URLs separately.
    """
    if not url or not isinstance(url, str):
        return False
    u = url.lower().strip()
    if not u.startswith(("http://", "https://")):
        return False

    # Strip scheme+host to look at path+query only
    try:
        without_scheme = u.split("://", 1)[1]
        host = without_scheme.split("/", 1)[0]
        path_and_query = "/" + without_scheme.split("/", 1)[1] if "/" in without_scheme else "/"
    except Exception:
        host = ""
        path_and_query = u
    path_only = path_and_query.split("?", 1)[0].split("#", 1)[0]

    # Detail markers win. We require at least one alphanumeric char after
    # the marker so ".../projekt/" (empty suffix) stays a search-style URL.
    # v1.7.9 (#763): nur gegen den PFAD pruefen — sonst wuerde eine Such-URL
    # mit "?ref=/jobs/view/123" faelschlich als Detail-URL durchgehen.
    for marker in _DETAIL_URL_PATH_MARKERS:
        idx = path_only.find(marker)
        if idx < 0:
            continue
        rest = path_only[idx + len(marker):]
        if re.match(r"[a-z0-9]", rest):
            return False

    # v1.7.9 (#763): Portal-Wurzel als GANZER Pfad = Suchseite
    # (indeed.de/jobs, xing.com/jobs, arbeitsagentur.de/jobsuche).
    if path_only.rstrip("/") in _SEARCH_URL_BARE_PATHS:
        return True

    # v1.7.9 (#763): stepstone-SEO-Suchpfade. PBP baut diese Form in
    # handoff.py SELBST ("/jobs/{keyword_pfad}"), erkannte sie aber nicht.
    # Detail-URLs von stepstone tragen "--" im Slug (_DETAIL_URL_PATH_MARKERS
    # "/stellenangebote--"), Suchpfade nicht.
    if "stepstone." in host and "--" not in path_only:
        if path_only.startswith(("/jobs/", "/stellenangebote/")):
            return True

    for pat in _SEARCH_URL_PATH_PATTERNS:
        if pat in path_and_query:
            return True

    # Query-param based matches (e.g. ...?keywords=plm&...)
    if "?" in path_and_query:
        query = path_and_query.split("?", 1)[1]
        for key in _SEARCH_URL_QUERY_KEYS:
            if key in query:
                return True

    return False


def extract_jobposting_jsonld(html: str, max_chars: int = 2000) -> dict:
    """Extrahiert JobPosting-Daten aus JSON-LD-Script-Tags.

    v1.7.0-beta.52 (#624 Phase 3): aus fetch_description_from_detail
    extrahiert, damit jeder HTML-Scraper strukturierte Daten lesen
    kann (statt eigene Parser zu schreiben).

    Liefert ein dict mit den Standard-JobPosting-Feldern (siehe
    schema.org/JobPosting):

        title, description, datePosted, validThrough,
        employmentType, hiringOrganization (dict), jobLocation (dict),
        baseSalary (dict), industry, qualifications, ...

    Description ist plain-text (HTML gestripped, max max_chars Zeichen).

    Liefert {} wenn keine JobPosting-JSON-LD im HTML.
    """
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else data.get("@graph", [data])
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if item.get("@type") != "JobPosting":
                        continue
                    result = dict(item)
                    desc = item.get("description", "")
                    if desc:
                        text = BeautifulSoup(desc, "html.parser").get_text(
                            separator=" ", strip=True
                        )
                        result["description"] = text[:max_chars]
                    return result
            except Exception:
                continue
        return {}
    except Exception:
        return {}


def fetch_description_from_detail(url: str, client, *, timeout: float = 15,
                                  max_chars: int = 2000) -> str:
    """Fetch job description from a detail page via httpx.

    Tries JSON-LD first (via extract_jobposting_jsonld), then common
    HTML content selectors. Returns plain text description (max
    ``max_chars`` chars) or empty string.

    #690: Beim expliziten Nachladen einer einzelnen Stelle
    (stellenbeschreibung_nachladen) wird ein grosszuegiges max_chars
    uebergeben, damit lange Beschreibungen nicht bei 2000 Zeichen
    abgeschnitten werden. Bulk-Scraper nutzen weiter den 2000er-Default.
    """
    try:
        from bs4 import BeautifulSoup
        resp = client.get(url, timeout=timeout)
        if resp.status_code != 200:
            return ""

        # Strategy 1: JSON-LD structured data — uses zentralen Helper
        jp = extract_jobposting_jsonld(resp.text, max_chars=max_chars)
        if jp.get("description"):
            return jp["description"]

        # Strategy 2: Common content selectors als Fallback
        soup = BeautifulSoup(resp.text, "html.parser")
        for selector in [
            "[class*='job-description']", "[class*='jobDescription']",
            "[class*='stellenbeschreibung']", "[class*='description']",
            "[class*='detail-content']", "[class*='job-detail']",
            "article .content", "article", ".content-area",
            "[itemprop='description']", "main",
        ]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(separator=" ", strip=True)
                if len(text) > 100:
                    return text[:max_chars]

        return ""
    except Exception as e:
        logger.debug("Detail-fetch failed for %s: %s", url, e)
        return ""


def _parse_weights(criteria: dict) -> dict:
    """Parse and normalize scoring weights from criteria dict."""
    w = criteria.get("gewichtung", {})
    if isinstance(w, str):
        try:
            import json
            w = json.loads(w)
        except Exception:
            w = {}
    return {
        "muss": w.get("muss", 2),
        "plus": w.get("plus", 1),
        # #667 (B19, beta.84): Minus-Keywords als Gegenstueck zu Plus.
        # Weicher Malus pro Treffer — Default 1, analog zu plus.
        "minus": w.get("minus", 1),
        "remote": w.get("remote", 2),
        "naehe": w.get("naehe", 2),
        "fern_malus": w.get("fern_malus", 3),
        "gehalt": w.get("gehalt", 1),
        # v1.7.12 (#827, C32): Treffer, die NUR im Firmen-Werbeabsatz
        # stehen, zaehlen mit diesem Faktor. 0 wuerde falsche Ausschluesse
        # produzieren, 1 waere der alte Fehler — 0.25 laesst die Stelle
        # sichtbar, ohne dass Portfolio-Prosa Fach-Rollen ueberholt.
        "firmenabsatz_faktor": float(w.get("firmenabsatz_faktor", 0.25)),
    }


# v1.7.12 (#827, C32): Ueberschriften, mit denen Anzeigen den Aufgaben-
# oder Anforderungsteil einleiten. Bewusst breit — die Formulierungen
# variieren stark ("In deiner Mission bluehst du auf", "Dein Spielfeld").
# Alles VOR der ersten dieser Ueberschriften ist typischerweise die
# Firmen-Selbstdarstellung, deren Portfolio-Aufzaehlung ("allen voran PLM
# und ERP") sonst fachfremde Stellen nach oben spuelt.
_AUFGABEN_MARKER = (
    "aufgaben", "taetigkeiten", "tätigkeiten", "mission",
    "das erwartet dich", "was dich erwartet", "das erwartet sie",
    "deine rolle", "ihre rolle", "die rolle", "dein spielfeld",
    "das machst du", "das bewegst du", "was du bei uns",
    "your tasks", "your role", "responsibilities", "what you",
    "dein aufgabengebiet", "ihr aufgabengebiet", "der job",
    "das bringst du mit", "dein profil", "ihr profil",
    "anforderungen", "qualifikation",
)

_WIR_SIGNALE = ("wir sind", "wir gestalten", "wir zaehlen", "wir zählen",
                "unsere", "unseren", "unserem", "als einer der",
                "als eines der", "fuehrende", "führende", "marktfuehrer",
                "marktführer")


def _firmenabsatz_ende(description: str) -> int:
    """Index, an dem die Firmen-Selbstdarstellung endet. 0 = keine erkannt.

    Zwei Stufen: (1) erste Aufgaben-artige Ueberschrift in den vorderen
    60 % des Texts — was davor liegt, ist Intro/Firmenzone. (2) Ohne
    Ueberschrift zaehlt nur der ERSTE Absatz als Firmenzone, und auch nur,
    wenn er nach Wir-Prosa aussieht (>= 2 Signale). Konservativ: im
    Zweifel 0, denn ein zu grosser Schnitt wuerde echte Aufgaben-Treffer
    abwerten — der teurere Fehler.
    """
    if not description:
        return 0
    d_lc = description.lower()
    # Untergrenze 80: steht die Ueberschrift praktisch am Textanfang,
    # BEGINNT die Anzeige mit den Aufgaben — es gibt keine Firmenzone.
    # Obergrenze 80 %: ein "Profil"-Marker kurz vor Schluss darf nicht
    # fast den ganzen Text zur Firmenzone erklaeren.
    limit = int(len(d_lc) * 0.8)
    kandidaten = [i for m in _AUFGABEN_MARKER
                  if 80 <= (i := d_lc.find(m)) < limit]
    if kandidaten:
        return min(kandidaten)
    erster_absatz = d_lc.split("\n\n", 1)[0]
    if len(erster_absatz) < len(d_lc) * 0.5:
        signale = sum(1 for s in _WIR_SIGNALE if s in erster_absatz)
        if signale >= 2:
            return len(erster_absatz)
    return 0


# Synonym-Map fuer echte Synonyme/Varianten (#183)
# NUR direkte Synonyme — KEINE Technologie-Familien (sonst matcht "Java" auf "Python-Stellen")
_SYNONYM_MAP = {
    "plm": ["teamcenter", "windchill", "enovia", "aras", "product lifecycle"],
    "projektmanager": ["projektleiter", "project manager", "projektleitung"],
    "projektleiter": ["projektmanager", "project manager", "projektleitung"],
    "scrum master": ["agile coach", "scrum"],
    "fullstack": ["full-stack", "full stack"],
    "remote": ["homeoffice", "home office", "home-office", "telearbeit"],
    "freelance": ["freiberuflich", "selbststaendig", "freiberufler"],
    "devops": ["site reliability", "sre", "platform engineer"],
    "maschinenbau": ["mechanical engineering", "maschinenbauingenieur"],
    "vertrieb": ["sales", "account manager", "business development"],
    # v1.6.5 (#545): Gender-/Stem-Varianten — vor allem fuer AUSSCHLUSS-Keywords
    # ("Werkstudent" filtert nicht "Werkstudierende" weg, "Praktikant" nicht
    # "Praktikum"/"Praktikantin"). Bidirektional uebers SYNONYM_MAP geloest.
    "werkstudent": ["werkstudentin", "werkstudenten", "werkstudentinnen",
                    "werkstudierend", "werkstudierende", "werkstudierender",
                    "werkstudierenden", "studentische hilfskraft", "shk"],
    # v1.7.0-beta.46 (#604): "intern" entfernt — false positives auf
    # "internationalen Kunden" / "interne Kommunikation" in deutschen
    # Stellentexten. "internship" bleibt — kommt nur in englischsprachigen
    # Anzeigen vor und ist dort unmissverstaendlich.
    "praktikant": ["praktikantin", "praktikanten", "praktikantinnen",
                   "praktikum", "praktikumsplatz", "pflichtpraktikum",
                   "praktikumsstelle", "internship"],
    "praktikum": ["praktikant", "praktikantin", "praktikanten",
                  "praktikumsplatz", "pflichtpraktikum", "praktikumsstelle",
                  "internship"],
    "azubi": ["auszubildende", "auszubildender", "ausbildung",
              "lehrling", "berufsausbildung"],
    "ausbildung": ["azubi", "auszubildende", "auszubildender",
                   "lehrling", "berufsausbildung"],
    "trainee": ["traineeprogramm", "traineeship", "graduate program"],
    "junior": ["berufseinsteiger", "berufseinsteigerin", "absolvent",
               "absolventin", "einsteiger", "einsteigerin"],
}

# v1.6.5 (#546): Kurz-Keywords ohne Wortgrenze treffen falsch (z.B. "ai" in
# "Mainz", "ml" in "html", "pm" in "compiler"). Fuer Keywords <= 4 Zeichen
# wenden wir Word-Boundary-Match an statt reinem Substring.
_SHORT_KW_BOUNDARY_THRESHOLD = 4


def _word_boundary_match(keyword: str, text: str) -> bool:
    """Match keyword nur an Wortgrenzen (regex \\b). Fuer Kurz-Keywords (#546)."""
    if not keyword:
        return False
    pattern = r"(?<![\w])" + re.escape(keyword) + r"(?![\w])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _strict_keyword_match(keyword: str, text: str) -> bool:
    """v1.7.7 (#755, C25): Praezises Matching fuer MINUS-Keywords.

    MINUS-Keywords BESTRAFEN — anders als beim PLUS-Matching (Recall,
    _fuzzy_keyword_match) zaehlt hier Praezision: 'Product Manager' darf
    nicht feuern, nur weil 'product portfolio' und 'project manager'
    irgendwo im selben Text stehen (Multi-Word-Split war die Ursache der
    -12-Punkte-Fehlabwertung auf Project-Manager-Stellen).

    Regeln: Mehrwort-Keywords matchen nur als ZUSAMMENHAENGENDE Phrase
    (Whitespace/Bindestrich/Slash zwischen den Woertern variabel),
    Einwort-Keywords nur an Wortgrenzen. Umlaut-Normalisierung bleibt,
    Synonym-Expansion bewusst NICHT.
    """
    kw_lower = keyword.lower().strip()
    if not kw_lower:
        return False
    for needle, haystack in (
        (kw_lower, text.lower()),
        (_normalize_for_matching(kw_lower), _normalize_for_matching(text.lower())),
    ):
        parts = [re.escape(p) for p in re.split(r"[\s\-/]+", needle) if p]
        if not parts:
            continue
        pattern = (r"(?<![\w])" + r"[\s\-/]+".join(parts) + r"(?![\w])")
        if re.search(pattern, haystack):
            return True
    return False


def _normalize_for_matching(text: str) -> str:
    """Normalisiere Text fuer Matching: Umlaute, Bindestriche, Gross/Klein (#183)."""
    text = text.lower()
    # Umlaute normalisieren (bidirektional: ue->ü UND ü->ue)
    replacements = [
        ("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
    ]
    # Erst die echten Umlaute im Suchtext durch ae/oe/ue ersetzen
    normalized = text
    for uml, repl in replacements:
        normalized = normalized.replace(uml, repl)
    return normalized


def _filter_nach_schwelle(stellen, schwelle):
    """v1.7.22 (#940): Schwellenfilter als eigene Funktion.

    Vorher stand die Bedingung inline im Suchlauf — testbar war sie
    damit nur ueber einen kompletten Durchlauf, und die Zahl der
    verworfenen Treffer landete ausschliesslich im Log, nicht im
    Ergebnis. Beides braucht die Filterkaskade.
    """
    behalten = [j for j in stellen if (j.get("score") or 0) >= schwelle]
    return behalten, len(stellen) - len(behalten)


def _muss_tor_match(keyword: str, text: str) -> bool:
    """v1.7.22 (#940): Tor-Entscheidung fuer MUSS-Keywords.

    MUSS beantwortet die Frage *kommt die Stelle ueberhaupt in Frage*.
    Dafuer zaehlt Praezision, nicht Recall — genau umgekehrt zu PLUS.
    `_fuzzy_keyword_match` wurde fuer Recall gebaut und war trotzdem als
    Torwaechter im Einsatz; zwei seiner Regeln qualifizieren dabei
    fachfremde Stellen:

    * **Mehrwort-Split** — alle Einzelwoerter irgendwo im Text, in
      beliebiger Reihenfolge und Entfernung. "Engineering Data
      Management" passte damit auf jede Anzeige, in der die drei Woerter
      einzeln vorkamen (gemessen: Data Analytics, Data Science, Physics
      of CT). Dieselbe Regel war in der Gegenrichtung schon einmal die
      Ursache falscher MINUS-Abzuege, siehe #755/C25.
    * **generische Synonym-Phrasen** — `PLM` traegt das Synonym
      "product lifecycle"; die Wendung "manage product lifecycles" in
      einer Produktmanager-Anzeige machte daraus eine PLM-Stelle,
      obwohl das Kuerzel PLM dort null Mal vorkam.

    Deshalb hier: zusammenhaengende Phrase beziehungsweise Wortgrenze
    fuer das Keyword selbst (wie bei MINUS), Synonym-Expansion NUR fuer
    eindeutige Ein-Wort-Produktnamen. Die muessen bleiben — eine
    Teamcenter-Stelle IST eine PLM-Stelle, auch ohne das Kuerzel im
    Text.
    """
    if _strict_keyword_match(keyword, text):
        return True

    kw_lower = keyword.lower().strip()
    for syn_key, synonyme in _SYNONYM_MAP.items():
        if syn_key != kw_lower and kw_lower not in synonyme:
            continue
        for begriff in [syn_key] + list(synonyme):
            # Nur Ein-Wort-Synonyme: Produktnamen sind eindeutig,
            # Mehrwort-Phrasen sind es nicht.
            if " " in begriff or "-" in begriff:
                continue
            if begriff == kw_lower:
                continue
            if _strict_keyword_match(begriff, text):
                return True
    return False


def _fuzzy_keyword_match(keyword: str, text: str) -> bool:
    """Fuzzy-Keyword-Matching: Substring + Synonyme + Umlaut-Normalisierung (#183).

    Matcht wenn:
    1. Keyword als Substring im Text (exakt) — bei Kurz-Keywords (<=4 Zeichen)
       mit Word-Boundary-Regex (#546).
    2. Normalisiertes Keyword im normalisierten Text (Umlaute)
    3. Einzelne Wörter des Keywords matchen alle (Multi-Word Split)
    4. Ein Synonym des Keywords im Text vorkommt
    """
    kw_lower = keyword.lower().strip()
    text_lower = text.lower()

    # v1.6.5 (#546): Kurz-Keywords brauchen Word-Boundary-Match —
    # sonst matcht "AI" in "Mainz", "ML" in "HTML", "PM" in "compiler".
    is_short = len(kw_lower) <= _SHORT_KW_BOUNDARY_THRESHOLD and " " not in kw_lower

    # 1. Exakter Substring-Match (mit Word-Boundary fuer Kurz-Keywords)
    if is_short:
        if _word_boundary_match(kw_lower, text_lower):
            return True
    else:
        if kw_lower in text_lower:
            return True

    # 2. Umlaut-normalisierter Match
    kw_norm = _normalize_for_matching(kw_lower)
    text_norm = _normalize_for_matching(text_lower)
    if is_short:
        if _word_boundary_match(kw_norm, text_norm):
            return True
    else:
        if kw_norm in text_norm:
            return True

    # 3. Multi-Word: Alle Einzelwörter müssen im Text vorkommen
    #    z.B. "PLM Projektleiter" matcht "Projektleiter (m/w/d) im Bereich PLM"
    words = re.split(r'[\s\-/]+', kw_lower)
    if len(words) > 1:
        def _word_in(w: str) -> bool:
            if len(w) <= 1:
                return True
            if len(w) <= _SHORT_KW_BOUNDARY_THRESHOLD:
                return (_word_boundary_match(w, text_lower) or
                        _word_boundary_match(_normalize_for_matching(w), text_norm))
            return w in text_lower or _normalize_for_matching(w) in text_norm
        if all(_word_in(w) for w in words):
            return True

    # 4. Synonym-Match (inkl. Genderform-Stems aus #545)
    for syn_key, synonyms in _SYNONYM_MAP.items():
        if syn_key == kw_lower or kw_lower in synonyms:
            # Prüfe ob das Keyword oder ein Synonym im Text vorkommt
            all_terms = [syn_key] + synonyms
            for term in all_terms:
                term_norm = _normalize_for_matching(term)
                if len(term) <= _SHORT_KW_BOUNDARY_THRESHOLD and " " not in term:
                    if (_word_boundary_match(term, text_lower) or
                            _word_boundary_match(term_norm, text_norm)):
                        return True
                else:
                    if term in text_lower or term_norm in text_norm:
                        return True

    return False


# v1.7.0-beta.46 (#603): PBP-Notizen-Trenner. Wenn Claude (oder ein
# anderer Agent) redaktionelle Analyse in jobs.description schreibt,
# soll das Scoring nur den Original-Text bewerten, nicht Notizen mit
# Ausschluss-Keywords drin (z.B. "Hands-on" als Teil einer Analyse).
# Konvention: Ein '---' am Zeilenanfang oder eine '## Auffaelliges:'-
# Zeile markiert den Beginn der Notizen.
import re as _re_pbpnotes

_PBP_NOTES_RE = _re_pbpnotes.compile(
    r"(\n[ \t]*-{3,}[ \t]*\n)"           # ---
    r"|(\n[ \t]*##\s*(Auffaelliges|Auffälliges|PBP-Notizen|Analyse)\b)"
    r"|(\n[ \t]*Gehaltsschaetzung lt\. PBP:)"
    r"|(\n[ \t]*PBP-Notiz:)",
    _re_pbpnotes.IGNORECASE,
)


def _strip_pbp_notes(description: str) -> str:
    """Schneidet alles ab dem ersten PBP-Notizen-Trenner ab."""
    if not description:
        return ""
    m = _PBP_NOTES_RE.search(description)
    if m:
        return description[:m.start()].strip()
    return description


def _keyword_gewichte(criteria: dict) -> dict:
    """Einzelgewicht-Overrides pro Keyword (#778/C29, v1.7.10).

    criteria['keyword_gewichte'] = {"<keyword lower>": punkte}. Default
    bleibt das Kategorie-Gewicht — ein Override macht z.B. den Minus-Begriff
    'Arbeitnehmerueberlassung' milder als 'Bauwesen', ohne die ganze
    Kategorie umzustellen.
    """
    kg = criteria.get("keyword_gewichte") or {}
    if isinstance(kg, str):
        try:
            import json as _json
            kg = _json.loads(kg)
        except Exception:
            kg = {}
    return {str(k).lower(): v for k, v in kg.items()} if isinstance(kg, dict) else {}


def _punkte_pro_treffer(kw: str, kategorie_gewicht: float,
                        overrides: dict, idf: dict) -> float:
    """Punkte fuer EINEN Keyword-Treffer: Override vor Kategorie-Gewicht,
    multipliziert mit dem IDF-Seltenheitsfaktor (nur wenn Faktoren
    injiziert sind — sonst neutral 1.0)."""
    basis = overrides.get(kw.lower(), kategorie_gewicht)
    try:
        basis = float(basis)
    except (TypeError, ValueError):
        basis = kategorie_gewicht
    if idf:
        basis *= idf.get(kw.lower(), 1.0)
    return basis


def entfernungs_kompensationsgrad(job: dict, criteria: dict) -> float:
    """#910 (v1.7.17): km sind ein PREIS, kein Ausschluss — 0.0 bis 1.0.

    Nutzer-Formulierung: "km sind ein Malus, der durch Verdienst behoben
    werden kann." Liegt das ECHTE Gehalt ueber dem Wunsch, reduziert der
    Grad den Entfernungs-Malus anteilig (linear ueber die konfigurierte
    Spanne). Belegt: Rollen in mehreren hundert km Entfernung wurden
    ernsthaft verfolgt, weil die Konditionen stimmten — der harte Malus
    arbeitete gegen Recall-vor-Praezision.

    Aktivierung: scoring_konfigurieren('setzen',
    'entfernung_gehalt_kompensation', 'spanne', wert=30000).
    spanne=0 (Default) = aus, exakt heutiges Verhalten. Geschaetzte
    Gehaelter kompensieren NIE (#827) — sonst bezahlt eine erfundene
    Zahl einen echten Malus.
    """
    try:
        spanne = float(criteria.get("_entfernung_gehalt_spanne") or 0)
    except (TypeError, ValueError):
        return 0.0
    if spanne <= 0:
        return 0.0
    if job.get("salary_estimated"):
        return 0.0
    salary_min = job.get("salary_min")
    if not salary_min:
        return 0.0
    styp = job.get("salary_type", "jaehrlich")
    emp = job.get("employment_type", "festanstellung")
    if styp == "stuendlich":
        job_jahr = salary_min * 8 * 220
    elif styp == "taeglich" or emp == "freelance":
        job_jahr = salary_min * 220
    else:
        job_jahr = salary_min
    wunsch = criteria.get("min_gehalt", 0) or 0
    if emp == "freelance":
        _tag = criteria.get("min_tagessatz", 0) or 0
        if _tag:
            wunsch = _tag * 220
    if not wunsch:
        return 0.0
    return min(1.0, max(0.0, (job_jahr - wunsch) / spanne))


def calculate_score(job: dict, criteria: dict) -> int:
    """Calculate relevance score for a job listing.

    Uses configurable weights from criteria['gewichtung']:
      muss: points per MUSS keyword hit (default 2)
      plus: points per PLUS keyword hit (default 1)
      remote: bonus for remote/hybrid (default 2)
      naehe: bonus for <30km distance (default 2)
      fern_malus: penalty for >200km distance (default 3)

    #180: Bei fehlender Beschreibung wird nur der Titel gematcht.
    Das Scoring laeuft trotzdem, aber der Score wird als "unsicher" markiert
    (via _description_missing Flag am Job).

    v1.7.10 (#778/C29): Einzelgewichte pro Keyword
    (criteria['keyword_gewichte'], wirkt immer) und optional
    IDF-Seltenheitsgewichtung + Top-5-Deckelung der MUSS-Summe — beides
    NUR aktiv, wenn criteria['_idf_faktoren'] injiziert ist (Opt-in via
    Suchkriterium 'scoring_idf'; get_search_criteria uebernimmt die
    Injektion). Ohne Opt-in ist das Verhalten unveraendert.
    """
    description = job.get("description", "") or ""
    title = job.get("title", "") or ""
    has_description = len(description.strip()) > 50  # Mindestens 50 Zeichen fuer sinnvollen Match

    # v1.7.0-beta.46 (#603): PBP-Notizen aus der Beschreibung
    # ausblenden bevor wir matchen. Claude schreibt manchmal redaktionelle
    # Analysen ('Auffaelliges:', 'Gehaltsschaetzung lt. PBP:') in
    # jobs.description — diese koennen Ausschluss-Keywords enthalten und
    # das Scoring sabotieren.
    description_for_score = _strip_pbp_notes(description)
    text = f"{title} {description_for_score}".lower()
    w = _parse_weights(criteria)

    # v1.7.12 (#827, C32): Kern-Text = Titel + Beschreibung OHNE die
    # Firmen-Selbstdarstellung. Treffer dort zaehlen voll; Treffer, die
    # NUR im Firmenabsatz stehen, mit firmenabsatz_faktor. Belegt: eine
    # fachfremde Rolle sammelte 30 von 36 Punkten ausschliesslich aus dem
    # Portfolio-Absatz des Dienstleisters ("allen voran PLM und ERP").
    _grenze = _firmenabsatz_ende(description_for_score)
    if _grenze > 0:
        kern_text = f"{title} {description_for_score[_grenze:]}".lower()
    else:
        kern_text = text

    def _treffer_faktor(kw: str, fuzzy: bool = True) -> float:
        """1.0 = Treffer im Kern, firmenabsatz_faktor = nur im Firmenabsatz."""
        match = _fuzzy_keyword_match if fuzzy else _strict_keyword_match
        if _grenze <= 0 or match(kw, kern_text):
            return 1.0
        return w["firmenabsatz_faktor"]

    # #180: Markiere Jobs ohne Beschreibung damit Claude/Frontend warnen kann
    if not has_description:
        job["_beschreibung_fehlt"] = True

    # AUSSCHLUSS keywords (check first for early exit)
    # v1.7.8 (#762): STRIKTES Matching wie bei MINUS (#755/C25). Der harte
    # K.o. darf nicht durch Fuzzy-/Synonym-/Multi-Word-Split-Treffer ausgeloest
    # werden. Belegt: Ausschluss "Product Manager" feuerte auf einem PLM-
    # Volltext, weil 'product' (in "product lifecycle") und 'manager' (in
    # "manager der fachabteilung") irgendwo im Text standen — Score fiel auf 0,
    # obwohl die Rolle passte. Je LAENGER der Text, desto wahrscheinlicher der
    # Fehlalarm — also genau beim empfohlenen Volltext-Nachpflegen. Der Grund
    # wird am Job markiert, damit Tools erklaeren koennen, warum der Score 0 ist.
    ausschluss = criteria.get("keywords_ausschluss", [])
    for _kw in ausschluss:
        if _strict_keyword_match(_kw, text):
            job["_ko_ausschluss"] = _kw
            return 0

    # v1.7.10 (#778): Einzelgewichte + optionale IDF-Faktoren
    overrides = _keyword_gewichte(criteria)
    idf = criteria.get("_idf_faktoren") or {}
    if not isinstance(idf, dict):
        idf = {}

    # MUSS keywords — #183: Fuzzy-Matching statt exakter Substring
    muss = criteria.get("keywords_muss", [])
    # v1.7.22 (#940): Zwei getrennte Fragen, zwei getrennte Matcher.
    # Das TOR entscheidet praezise, ob die Stelle ueberhaupt in Frage
    # kommt. Die PUNKTE bleiben bewusst auf dem bisherigen (weiteren)
    # Matching — sonst verschieben sich alle Scores und die Wirkung des
    # Tors waere nicht mehr isoliert messbar. Die Neubewertung der
    # Punktevergabe ist #942.
    muss_hits_kws = [kw for kw in muss if _fuzzy_keyword_match(kw, text)]
    muss_tor_kws = [kw for kw in muss if _muss_tor_match(kw, text)]
    muss_found = len(muss_tor_kws)
    if muss and muss_found == 0:
        # #180: Ohne Beschreibung nicht sofort auf 0 setzen, WENN der Titel
        # zumindest Teilworte der MUSS-Keywords enthält (z.B. "PLM" im Titel)
        if not has_description and title.strip():
            title_lower = title.lower()
            # Prüfe ob mindestens ein Einzelwort aus MUSS-Keywords im Titel vorkommt
            has_partial = any(
                w in title_lower
                for kw in muss for w in kw.lower().split() if len(w) > 2
            )
            if has_partial:
                job["_score_unsicher"] = True
                return 1  # Mindest-Score — Beschreibung nachladen!
        # #762: K.o.-Grund markieren (kein MUSS-Keyword getroffen)
        job["_ko_kein_muss"] = True
        return 0

    # v1.7.10 (#778): Punkte pro Treffer statt pauschal Anzahl x Gewicht.
    # Mit IDF-Faktoren zaehlen zusaetzlich nur die MUSS_TOP_N staerksten
    # MUSS-Treffer (Deckelung) — Masse darf Klasse nicht schlagen.
    # v1.7.12 (#827): jeder Treffer traegt seinen Firmenabsatz-Faktor.
    muss_punkte = sorted(
        (_punkte_pro_treffer(kw, w["muss"], overrides, idf)
         * _treffer_faktor(kw)
         for kw in muss_hits_kws),
        reverse=True,
    )
    if idf:
        from ..services.kalibrierung import MUSS_TOP_N
        muss_punkte = muss_punkte[:MUSS_TOP_N]
    score = sum(muss_punkte)

    # v1.7.12 (#827): Flag fuer Tools/Frontend, wenn ALLE MUSS-Treffer
    # nur in der Firmen-Selbstdarstellung sitzen — der Score ist dann
    # niedrig, und der Grund soll erklaerbar sein.
    if _grenze > 0 and muss_hits_kws and all(
            not _fuzzy_keyword_match(kw, kern_text) for kw in muss_hits_kws):
        job["_treffer_nur_firmenabsatz"] = True

    # PLUS keywords — #183: Fuzzy-Matching
    # v1.7.12 (#827): Begriffe, die schon in MUSS stehen, zaehlen hier
    # NICHT nochmal — vorher wurden PLM & Co. doppelt gewertet (einmal
    # als MUSS, einmal als PLUS). Normalisiert verglichen, weil die
    # Listen historisch Schreibvarianten tragen.
    plus = criteria.get("keywords_plus", [])
    _muss_norm = {kw.strip().lower() for kw in muss}
    plus_effektiv = [kw for kw in plus
                     if kw.strip().lower() not in _muss_norm]
    score += sum(
        _punkte_pro_treffer(kw, w["plus"], overrides, idf)
        * _treffer_faktor(kw)
        for kw in plus_effektiv if _fuzzy_keyword_match(kw, text)
    )

    # MINUS keywords (#667, B19, beta.84) — weiche Score-Abwertung als
    # Gegenstueck zu PLUS. Beispiel: kw="Automotive" zieht Punkte ab, schliesst
    # die Stelle aber nicht aus (harter Ausschluss = keywords_ausschluss).
    # #778: Einzelgewicht-Override gilt auch hier; IDF bewusst NICHT —
    # ein Malus soll nicht dadurch schrumpfen, dass der Begriff haeufig ist.
    minus = criteria.get("keywords_minus", [])
    if minus:
        # #755 (C25): strikt statt fuzzy — Malus nur bei echtem Treffer
        score -= sum(
            _punkte_pro_treffer(kw, w["minus"], overrides, {})
            for kw in minus if _strict_keyword_match(kw, text)
        )

    # Distance bonus/malus (#60, #112, #166) — typ-abhaengige Entfernung
    dist = job.get("distance_km")
    emp_type = job.get("employment_type", "festanstellung")
    max_dist_map = criteria.get("max_entfernung", {})
    # Defaults: Festanstellung 50km, Freelance 200km, Rest 50km
    _default_max = {"festanstellung": 50, "freelance": 200, "teilzeit": 30, "praktikum": 50, "werkstudent": 50}
    type_max_dist = max_dist_map.get(emp_type) or _default_max.get(emp_type, 50)
    if dist is not None:
        # #910: echter Verdienst ueber Wunsch reduziert den
        # Entfernungs-Malus anteilig (nur die MALUS-Zweige — Naehe-Boni
        # bleiben unveraendert). Default-aus, siehe
        # entfernungs_kompensationsgrad.
        _komp = entfernungs_kompensationsgrad(job, criteria)
        if dist > type_max_dist * 4:
            # Way beyond limit: full penalty
            score -= w["fern_malus"] * (1 - _komp)
        elif dist > type_max_dist * 2:
            # Moderately beyond: slight penalty
            score -= 1 * (1 - _komp)
        elif dist <= type_max_dist * 0.6:
            # Well within range: bonus
            score += w["naehe"]
        elif dist <= type_max_dist:
            # Within range: smaller bonus
            score += max(1, w["naehe"] - 1)

    # Remote bonus (#60) — differentiate remote vs hybrid
    remote = job.get("remote_level", "unbekannt")
    if remote == "remote":
        score += w["remote"] + 1  # full remote gets extra
    elif remote == "hybrid":
        score += w["remote"]

    # Application signal bonus (#68) — boost similar jobs
    applied_titles = criteria.get("_applied_titles", [])
    if applied_titles:
        job_title = job.get("title", "").lower()
        for at in applied_titles:
            if at in job_title or job_title in at:
                score += 2  # applied for similar = strong signal
                break

    # Salary bonus: reward jobs matching salary expectations
    salary_min = job.get("salary_min")
    if salary_min and w.get("gehalt", 0):
        salary_type = job.get("salary_type", "jaehrlich")
        emp_type = job.get("employment_type", "festanstellung")
        if salary_type == "taeglich" or emp_type == "freelance":
            salary_pref_min = criteria.get("min_tagessatz", 0) or 0
            job_yearly = salary_min * 220
            pref_yearly = salary_pref_min * 220 if salary_pref_min else (criteria.get("min_gehalt", 0) or 0)
        else:
            salary_pref_min = criteria.get("min_gehalt", 0) or 0
            job_yearly = salary_min
            pref_yearly = salary_pref_min
        if pref_yearly and job_yearly >= pref_yearly:
            score += w["gehalt"]

    # #778: Mit Einzelgewichten/IDF kann score ein Float sein — auf eine
    # Nachkommastelle runden; der Default-Pfad (Ints) bleibt unveraendert.
    return max(0, round(score, 1))


def fit_analyse(job: dict, criteria: dict) -> dict:
    """Detailed fit analysis for a job — used by dashboard API.

    Returns dict with total_score, muss_hits, missing_muss, plus_hits,
    factors (breakdown), and risks.
    """
    # v1.7.17 (#917 Defekt D): dieselbe Textbasis wie calculate_score —
    # PBP-Notizen VOR dem Matchen ausblenden. Vorher matchte die
    # Fit-Analyse gegen den vollen Text inkl. redaktioneller Notizen,
    # calculate_score gegen den gestrippten; dieselbe Stelle bekam je
    # nach Pfad verschiedene Scores.
    _desc = _strip_pbp_notes(job.get("description", "") or "")
    text = f"{job.get('title', '')} {_desc}".lower()
    w = _parse_weights(criteria)

    muss = criteria.get("keywords_muss", [])
    plus = criteria.get("keywords_plus", [])
    # #667 (B19, beta.84): Minus-Keywords als weiche Score-Abwertung.
    minus = criteria.get("keywords_minus", [])

    # v1.7.17 (#917 Defekt D): Ausschluss-Keywords gelten in BEIDEN
    # Score-Pfaden. calculate_score setzte hart 0, fit_analyse ignorierte
    # die Liste — dieselbe Stelle hatte gleichzeitig Score 0 und 88, je
    # nachdem welches Tool zuletzt geschrieben hat. Strikt wie in
    # calculate_score (#762): Wortgrenzen, keine Synonym-Expansion.
    _raw_desc = job.get("description", "") or ""
    for _ko_kw in criteria.get("keywords_ausschluss", []):
        if _strict_keyword_match(_ko_kw, text):
            return {
                "total_score": 0,
                "muss_hits": [], "missing_muss": list(muss),
                "plus_hits": [], "minus_hits": [],
                "factors": {f"AUSSCHLUSS-Keyword '{_ko_kw}' — Score hart 0": 0},
                "risks": [
                    f"AUSSCHLUSS-Keyword '{_ko_kw}' kommt im Anzeigentext "
                    "vor — harter K.o. wie in der Stellenliste. Falls der "
                    "Treffer aus einer redaktionellen Notiz stammt: Notizen "
                    "gehoeren hinter eine '---'-Trennzeile (#603), dann "
                    "zaehlen sie nicht."
                ],
                "ko_ausschluss": _ko_kw,
                "beschreibung_vorhanden": len(_raw_desc.strip()) >= 50,
                "beschreibung_kurz": 50 <= len(_raw_desc.strip()) < 400,
                "hochschulabschluss_gefordert": False,
            }

    # v1.7.12 (#827, C32): dieselbe Firmenabsatz-Logik wie calculate_score
    # — sonst erklaert die Fit-Analyse einen anderen Score als die Liste.
    _fa_grenze = _firmenabsatz_ende(_desc)
    if _fa_grenze > 0:
        _kern = f"{job.get('title', '')} {_desc[_fa_grenze:]}".lower()
    else:
        _kern = text

    def _fa_faktor(kw: str) -> float:
        if _fa_grenze <= 0 or _fuzzy_keyword_match(kw, _kern):
            return 1.0
        return w["firmenabsatz_faktor"]

    # #183: Fuzzy-Matching auch in der Fit-Analyse
    # v1.7.12 (#827): PLUS zaehlt Begriffe nicht nochmal, die schon in
    # MUSS stehen — vorher wurden sie doppelt gewertet.
    _muss_norm = {kw.strip().lower() for kw in muss}
    plus_effektiv = [kw for kw in plus
                     if kw.strip().lower() not in _muss_norm]
    muss_hits = [kw for kw in muss if _fuzzy_keyword_match(kw, text)]
    missing_muss = [kw for kw in muss if not _fuzzy_keyword_match(kw, text)]
    plus_hits = [kw for kw in plus_effektiv if _fuzzy_keyword_match(kw, text)]
    # #755 (C25): MINUS strikt (Wortgrenzen + Phrase) statt fuzzy —
    # PLUS belohnt (Recall ok), MINUS bestraft (Praezision Pflicht).
    minus_hits = [kw for kw in minus if _strict_keyword_match(kw, text)]

    factors = {}
    total = 0

    # v1.7.10 (#778): dieselbe Punkte-Logik wie calculate_score —
    # Einzelgewichte immer, IDF + Top-5-Deckelung nur bei injizierten
    # Faktoren. Sonst laufen Listen-Score und Fit-Analyse auseinander.
    _overrides = _keyword_gewichte(criteria)
    _idf = criteria.get("_idf_faktoren") or {}
    if not isinstance(_idf, dict):
        _idf = {}

    _nur_firmenabsatz = (
        _fa_grenze > 0
        and (muss_hits or plus_hits)
        and all(not _fuzzy_keyword_match(kw, _kern)
                for kw in muss_hits + plus_hits)
    )

    if muss_hits:
        _muss_pts = sorted(
            (_punkte_pro_treffer(kw, w["muss"], _overrides, _idf)
             * _fa_faktor(kw)
             for kw in muss_hits),
            reverse=True,
        )
        if _idf:
            from ..services.kalibrierung import MUSS_TOP_N
            _muss_pts = _muss_pts[:MUSS_TOP_N]
        pts = round(sum(_muss_pts), 1)
        _label = f"MUSS-Keywords ({len(muss_hits)} Treffer)"
        if _fa_grenze > 0 and any(_fa_faktor(kw) < 1.0 for kw in muss_hits):
            _label += " — teils nur im Firmenabsatz, abgewertet"
        factors[_label] = pts
        total += pts

    if plus_hits:
        pts = round(sum(
            _punkte_pro_treffer(kw, w["plus"], _overrides, _idf)
            * _fa_faktor(kw)
            for kw in plus_hits), 1)
        _label = f"PLUS-Keywords ({len(plus_hits)} Treffer)"
        if _fa_grenze > 0 and any(_fa_faktor(kw) < 1.0 for kw in plus_hits):
            _label += " — teils nur im Firmenabsatz, abgewertet"
        factors[_label] = pts
        total += pts

    # #667: Minus-Keywords abziehen — analog zu Plus, aber negativ.
    # Beispiel: kw="Automotive" mit Gewicht 1 -> -1 pro Treffer.
    # Bewusst weicher Malus, kein harter Ausschluss (das ist
    # keywords_ausschluss). Stelle bleibt in der Liste, rutscht nur runter.
    # #778: Override gilt, IDF bewusst nicht (wie in calculate_score).
    if minus_hits:
        pts = -round(sum(
            _punkte_pro_treffer(kw, w["minus"], _overrides, {})
            for kw in minus_hits), 1)
        factors[f"MINUS-Keywords ({len(minus_hits)} Treffer)"] = pts
        total += pts

    remote = job.get("remote_level", "unbekannt")
    if remote in ("remote", "hybrid"):
        factors[f"Arbeitsmodell: {remote}"] = w["remote"]
        total += w["remote"]

    dist = job.get("distance_km")
    fit_emp_type = job.get("employment_type", "festanstellung")
    fit_max_dist_map = criteria.get("max_entfernung", {})
    _fit_default_max = {"festanstellung": 50, "freelance": 200, "teilzeit": 30, "praktikum": 50, "werkstudent": 50}
    fit_type_max = fit_max_dist_map.get(fit_emp_type) or _fit_default_max.get(fit_emp_type, 50)
    if dist is not None:
        # #910: identische Kompensations-Logik wie calculate_score —
        # Basis-Malus, Kompensationsgrad und Ergebnis stehen GETRENNT
        # in den factors, damit die Rechnung nachvollziehbar bleibt.
        _fit_komp = entfernungs_kompensationsgrad(job, criteria)
        if dist > fit_type_max * 4:
            _basis = -w["fern_malus"]
            factors[f"Entfernung: {int(dist)} km (Max {fit_emp_type}: {fit_type_max} km)"] = _basis
            total += _basis
            if _fit_komp > 0:
                _gutschrift = round(-_basis * _fit_komp, 1)
                factors[f"Entfernungs-Malus durch Gehalt kompensiert "
                        f"({int(_fit_komp * 100)} %, #910)"] = _gutschrift
                total += _gutschrift
        elif dist > fit_type_max * 2:
            _basis = -1
            factors[f"Entfernung: {int(dist)} km (ueber Max {fit_type_max} km)"] = _basis
            total += _basis
            if _fit_komp > 0:
                _gutschrift = round(-_basis * _fit_komp, 1)
                factors[f"Entfernungs-Malus durch Gehalt kompensiert "
                        f"({int(_fit_komp * 100)} %, #910)"] = _gutschrift
                total += _gutschrift
        elif dist <= fit_type_max * 0.6:
            factors[f"Naehe: {int(dist)} km"] = w["naehe"]
            total += w["naehe"]
        elif dist <= fit_type_max:
            pts = max(1, w["naehe"] - 1)
            factors[f"Naehe: {int(dist)} km (im Rahmen)"] = pts
            total += pts

    risks = []

    # Salary factor — normalize daily rates vs yearly salary
    salary_min = job.get("salary_min")
    # v1.7.17 (#918/#827-Nachzug): Schaetzungen bleiben auch HIER neutral.
    # Der #827-Fix sass nur in scoring_service — dieser Pfad vergab
    # weiter den vollen Bonus fuer eine Zahl, die es nicht gibt (belegt:
    # +8 von 43,8 Gesamtpunkten fuer eine Anzeige ohne Gehaltsangabe).
    if salary_min and job.get("salary_estimated"):
        factors["Gehalt: nur Schaetzung — neutral (#827)"] = 0
        salary_min = None
    if salary_min:
        salary_type = job.get("salary_type", "jaehrlich")
        emp_type = job.get("employment_type", "festanstellung")
        if salary_type == "stuendlich":
            # v1.7.17 (#920): Stundensaetze existierten im Extraktor,
            # dieser Vergleich kannte sie nicht — "100 EUR/hour" wurde
            # als 100 EUR/TAG gelesen (Faktor 8 zu niedrig) und
            # min_stundensatz nie ausgewertet.
            salary_pref = criteria.get("min_stundensatz", 0) or 0
            job_yearly = salary_min * 8 * 220
            if salary_pref:
                pref_yearly = salary_pref * 8 * 220
                pref_label = f"{salary_pref} EUR/Stunde"
            else:
                _tag = criteria.get("min_tagessatz", 0) or 0
                pref_yearly = _tag * 220 if _tag \
                    else (criteria.get("min_gehalt", 0) or 0)
                pref_label = f"{_tag} EUR/Tag" if _tag \
                    else f"{pref_yearly} EUR/Jahr"
            salary_label = (f"{salary_min} EUR/Stunde "
                            f"(~{int(job_yearly)} EUR/Jahr)")
        elif salary_type == "taeglich" or emp_type == "freelance":
            salary_pref = criteria.get("min_tagessatz", 0) or 0
            job_yearly = salary_min * 220
            pref_yearly = salary_pref * 220 if salary_pref else (criteria.get("min_gehalt", 0) or 0)
            salary_label = f"{salary_min} EUR/Tag (~{int(job_yearly)} EUR/Jahr)"
            pref_label = f"{salary_pref} EUR/Tag" if salary_pref else f"{pref_yearly} EUR/Jahr"
        else:
            salary_pref = criteria.get("min_gehalt", 0) or 0
            job_yearly = salary_min
            pref_yearly = salary_pref
            salary_label = f"{salary_min} EUR/Jahr"
            pref_label = f"{salary_pref} EUR/Jahr"
        if pref_yearly and job_yearly >= pref_yearly:
            factors["Gehalt passt zu Erwartung"] = w.get("gehalt", 1)
            total += w.get("gehalt", 1)
        elif pref_yearly and job_yearly < pref_yearly * 0.8:
            risks.append(f"Gehalt ({salary_label}) liegt unter Mindestvorstellung ({pref_label})")
    if missing_muss:
        risks.append(f"{len(missing_muss)} MUSS-Keywords nicht gefunden")
    if not job.get("url"):
        risks.append("Kein Link zur Stellenanzeige vorhanden")
    if job.get("employment_type") == "freelance" and not job.get("salary_info"):
        risks.append("Freelance ohne Tagessatz-Angabe")

    # Skill matching from profile
    profile_skills = criteria.get("_profile_skills", [])
    if profile_skills:
        skill_hits = [s for s in profile_skills if s in text]
        skill_miss = [s for s in profile_skills if s not in text and len(s) > 2]
        if skill_hits:
            factors[f"Kompetenzen-Match ({len(skill_hits)} Skills)"] = len(skill_hits)
            total += len(skill_hits)
        if len(skill_miss) > len(skill_hits) and skill_miss:
            risks.append(f"Wenige deiner Kompetenzen erwaehnt ({len(skill_hits)}/{len(skill_hits)+len(skill_miss)})")

    # #305 / #698: Hochschulabschluss-Erkennung. Der Malus ist ueber
    # scoring_konfigurieren('hochschulabschluss','fehlt') konfigurierbar
    # (Default -2). criteria['_hochschulabschluss_malus'] == None bedeutet
    # "ignorieren" — dann faellt Malus UND Risiko-Hinweis komplett weg.
    desc = job.get("description") or ""
    degree_required = _detect_degree_required(f"{job.get('title', '')} {desc}")
    has_degree = _profile_has_degree(criteria)
    _hs_malus = criteria.get("_hochschulabschluss_malus", -2)
    if degree_required and not has_degree and _hs_malus is not None:
        risks.insert(0,
            "HOCHSCHULABSCHLUSS GEFORDERT — Stelle fordert formalen Abschluss "
            "(Studium/Bachelor/Master). Dein Profil enthält keinen. "
            "Risiko: Automatische ATS-Aussortierung möglich, "
            "selbst bei passender Berufserfahrung."
        )
        if _hs_malus != 0:
            factors["Hochschulabschluss fehlt"] = _hs_malus
            total += _hs_malus

    # #180: Warnung bei fehlender Beschreibung
    if len(desc.strip()) < 50:
        risks.insert(0, "BESCHREIBUNG FEHLT — Score ist unzuverlässig! "
                     "Lade die Stellenbeschreibung nach (stelle_manuell_anlegen oder URL öffnen).")

    # v1.7.12 (#827): ALLE Keyword-Treffer sitzen im Firmen-Werbeabsatz —
    # die Anzeige redet ueber das Portfolio der Firma, nicht ueber die
    # Rolle. Belegter Fall: fachfremde Rolle sammelte 30 Punkte aus dem
    # Selbstdarstellungs-Absatz eines IT-Dienstleisters.
    if _nur_firmenabsatz:
        risks.insert(0,
            "KEYWORD-TREFFER NUR IM FIRMENABSATZ — alle MUSS/PLUS-Treffer "
            "stehen in der Selbstdarstellung der Firma, keiner in der "
            "Aufgabenbeschreibung. Die Punkte sind entsprechend abgewertet; "
            "die Rolle selbst hat mit deinen Suchbegriffen vermutlich "
            "nichts zu tun.")

    # #667: Risk-Hinweis wenn viele Minus-Treffer (weicher als k.o., aber
    # transparent fuer den User wenn die Stelle nicht zuoberst rutscht).
    if minus_hits and len(minus_hits) >= 2:
        risks.append(
            f"{len(minus_hits)} MINUS-Keyword-Treffer "
            f"({', '.join(minus_hits[:3])}{'...' if len(minus_hits) > 3 else ''}) "
            "- weiche Abwertung im Score."
        )

    return {
        "total_score": max(0, total),
        "muss_hits": muss_hits,
        "missing_muss": missing_muss,
        "plus_hits": plus_hits,
        # #667: Minus-Treffer im Result transparent machen — Claude kann
        # sie zitieren ("Stelle hat 'Automotive' und 'SAP' getroffen, das
        # zieht den Score").
        "minus_hits": minus_hits,
        "factors": factors,
        "risks": risks,
        "beschreibung_vorhanden": len(desc.strip()) >= 50,
        # #762: Beschreibung da, aber nur eine Kurznotiz (typisch nach
        # stelle_manuell_anlegen). Dann matchen kaum MUSS-Keywords -> der Score
        # ist kuenstlich niedrig. Das ist KEIN fachliches Urteil, sondern
        # fehlende Datengrundlage. Echte Anzeigen liegen deutlich ueber 400
        # Zeichen; darunter behandeln wir den Score als nicht belastbar.
        "beschreibung_kurz": 50 <= len(desc.strip()) < 400,
        "hochschulabschluss_gefordert": degree_required,
    }


# Hochschulabschluss-Erkennung (#305)
_DEGREE_REQUIRED_PATTERNS = [
    "abgeschlossenes studium",
    "abgeschlossenes hochschulstudium",
    "hochschulabschluss",
    "universitaetsabschluss",
    "universitätsabschluss",
    "studienabschluss",
    "akademischer abschluss",
    "bachelor oder master",
    "bachelor/master",
    "master/bachelor",
    "diplom oder master",
    "diplom/master",
    "bachelor of science",
    "bachelor of engineering",
    "bachelor of arts",
    "master of science",
    "master of engineering",
    "master of arts",
    "university degree",
    "degree required",
    "studium erforderlich",
    "studium vorausgesetzt",
    "studium im bereich",
    "studium der informatik",
    "studium der ingenieurwissenschaft",
    "studium der wirtschaft",
    "studium der betriebswirtschaft",
    "studium des maschinenbau",
    "studium in informatik",
    "erfolgreich abgeschlossenes studium",
    # v1.7.17 (#918 Defekt 2): englische Formulierungen fehlten komplett —
    # "Educational Background: Bachelor's degree in Business ..." wurde
    # NICHT erkannt (Falsch-Negativ: echtes ATS-Risiko verschwiegen).
    "educational background",
    "bachelor's degree",
    "bachelors degree",
    "bachelor degree",
    "master's degree",
    "masters degree",
    "master degree",
    "mba",
    "degree in business",
    "degree in engineering",
    "degree in computer science",
    "academic degree",
    "college degree",
]


# #536 v1.6.4: Quereinsteiger-/Abschwaechungs-Klauseln erkennen.
# Wenn die Stellenbeschreibung explizit Quereinsteiger einlaedt oder die
# formale Anforderung relativiert, soll die Hochschulabschluss-Warnung
# NICHT triggern. Vorher: "Career changers welcome" wurde ignoriert,
# Score wurde zu Unrecht reduziert (-2), User abgeschreckt.
_DEGREE_RELAXATION_PATTERNS = [
    "career changers welcome",
    "career changers are welcome",
    "quereinsteiger willkommen",
    "quereinsteiger sind willkommen",
    "quereinsteiger:innen willkommen",
    "auch quereinsteiger",
    "oder vergleichbare qualifikation",
    "oder vergleichbar",
    "alternativ einschlaegige berufserfahrung",
    "alternativ einschlägige berufserfahrung",
    "auch ohne studium moeglich",
    "auch ohne studium möglich",
    "kein studium erforderlich",
    "kein abschluss erforderlich",
    "abschluss nicht zwingend",
    "no degree required",
    "degree not required",
    "or equivalent experience",
    "or comparable experience",
    "or comparable field",
    "comparable qualification",
    "auch ohne abschluss",
    # v1.7.17 (#918 Defekt 2): Oeffnungsklauseln, die den Abschluss
    # entwerten — ein Techniker-Abschluss erfuellt die Anforderung dann.
    "oder vergleichbare ausbildung",
    "oder eine vergleichbare ausbildung",
    "oder vergleichbare berufsausbildung",
    "vergleichbare qualifikation",
    "or similar education",
    "or similar qualification",
    "or equivalent qualification",
    "or equivalent education",
    "or relevant experience",
    "equivalent practical experience",
    "oder einschlaegige berufserfahrung",
    "oder einschlägige berufserfahrung",
]


def _degree_text(text: str) -> str:
    """Matching-Text fuer die Abschluss-Erkennung (v1.7.17, #918 Defekt 2).

    Zusaetzlich zur Umlaut-Normalisierung wird der Whitespace geglaettet:
    echte Anzeigen brechen Zeilen mitten in der Phrase um ("oder eine" /
    Zeilenumbruch / "vergleichbare Ausbildung"), und die Muster sind zusammenhaengende
    Phrasen — ohne Glaettung greift ausgerechnet die Oeffnungsklausel nicht.
    """
    import re as _re
    return _re.sub(r"\s+", " ", _normalize_for_matching(text or ""))


def _has_degree_relaxation(text: str) -> bool:
    """True wenn der Text Quereinsteiger-/Abschwaechungs-Klauseln enthaelt (#536)."""
    text_lower = _degree_text(text)
    return any(pat in text_lower for pat in _DEGREE_RELAXATION_PATTERNS)


# v1.7.17 (#918 Defekt 2): Zeilen, die ueber ANDERE Bewerber reden statt
# ueber die Anforderung. Belegter Fall: die LinkedIn-Bewerberstatistik
# ("21 % haben den Abschluss Master, 17 % Bachelor der
# Ingenieurswissenschaften") stand im Datensatz und loeste einen
# Falsch-Alarm aus ("HOCHSCHULABSCHLUSS GEFORDERT") bei einer Anzeige,
# die gar keinen Abschluss verlangt.
_DEGREE_STATISTIK_MARKER = (
    "bewerberfeld", "bewerberlage", "bewerberstatistik", "der bewerber",
    "% haben", "prozent haben", "berufserfahrene", "berufseinsteiger",
    "applicant", "applicants have",
)


def _ohne_bewerberstatistik(text: str) -> str:
    """Entfernt Zeilen, die Bewerber-Statistiken statt Anforderungen tragen."""
    zeilen = []
    for zeile in (text or "").splitlines():
        low = zeile.lower()
        if any(m in low for m in _DEGREE_STATISTIK_MARKER):
            continue
        zeilen.append(zeile)
    return chr(10).join(zeilen)


def _detect_degree_required(text: str) -> bool:
    """Erkennt ob eine Stellenbeschreibung einen Hochschulabschluss fordert (#305).

    v1.6.4 (#536): Quereinsteiger-Klauseln werden jetzt beruecksichtigt.
    Wenn die Beschreibung explizit Quereinsteiger einlaedt, wird die formale
    Anforderung als nicht-bindend gewertet (False zurueckgegeben).

    v1.7.17 (#918 Defekt 2): Die Erkennung lief auf dem GESAMTEN Datensatz —
    inklusive redaktioneller PBP-Notizen und Bewerberstatistiken. Jetzt
    zuerst Notizen abschneiden (#603-Trenner) und Statistik-Zeilen
    entfernen; erst dann matchen.
    """
    text = _ohne_bewerberstatistik(_strip_pbp_notes(text or ""))
    text_lower = _degree_text(text)
    if not any(pat in text_lower for pat in _DEGREE_REQUIRED_PATTERNS):
        return False
    # Pattern hat angeschlagen — pruefe ob abgeschwaecht
    if _has_degree_relaxation(text_lower):
        return False
    return True


def _profile_has_degree(criteria: dict) -> bool:
    """Prüft ob das Profil einen Hochschulabschluss enthält (#305)."""
    education = criteria.get("_profile_education", [])
    if not education:
        return False
    degree_keywords = {"bachelor", "master", "diplom", "magister", "doktor", "dr.",
                       "phd", "mba", "staatsexamen", "promotion"}
    for edu in education:
        degree = (edu.get("degree") or "").lower()
        if any(kw in degree for kw in degree_keywords):
            return True
        # Auch Studienfach prüfen — wenn degree leer, aber field_of_study "Informatik" o.ä.
        field = (edu.get("field_of_study") or "").lower()
        if field and ("studium" in degree or "university" in (edu.get("institution") or "").lower()
                      or "hochschule" in (edu.get("institution") or "").lower()
                      or "universität" in (edu.get("institution") or "").lower()):
            return True
    return False


# Remote detection keywords
REMOTE_KEYWORDS = [
    "remote", "homeoffice", "home office", "home-office",
    "mobiles arbeiten", "ortsunabhaengig", "standortunabhaengig",
    "deutschlandweit", "bundesweit", "100% remote",
    "work from home", "working from home", "wfh",
    "hybrid", "hybrides arbeiten", "teilweise remote",
    "flexibler arbeitsort", "flexible arbeitsmodelle",
]


def detect_remote_level(text: str) -> str:
    """Detect remote/hybrid/on-site from job description."""
    text_lower = text.lower()
    if any(kw in text_lower for kw in ["100% remote", "vollstaendig remote", "full remote", "rein remote"]):
        return "remote"
    if any(kw in text_lower for kw in ["hybrid", "teilweise remote", "2-3 tage"]):
        return "hybrid"
    if any(kw in text_lower for kw in REMOTE_KEYWORDS):
        return "remote"
    return "unbekannt"


# ── Salary Extraction & Estimation (PBP v0.10.0) ─────────────

SALARY_PATTERNS = [
    # Annual: 60.000-80.000 EUR, 60.000 - 80.000€, €60.000-€80.000
    re.compile(
        r'(?:€|EUR)?\s*(\d{2,3}(?:[.\s]\d{3}))\s*(?:[-–bis]+)\s*(?:€|EUR)?\s*(\d{2,3}(?:[.\s]\d{3}))\s*(?:€|EUR)?(?:\s*(?:brutto|p\.?\s*a|jahresgehalt|jaehrlich|jährlich|/\s*jahr))?',
        re.IGNORECASE
    ),
    # Annual with k: 60k-80k, 60K - 80K EUR
    re.compile(
        r'(?:€|EUR)?\s*(\d{2,3})\s*[kK]\s*(?:[-–bis]+)\s*(?:€|EUR)?\s*(\d{2,3})\s*[kK]',
        re.IGNORECASE
    ),
    # Annual single: ab 60.000 EUR, bis 80.000€
    re.compile(
        r'(?:ab|bis|ca\.?|circa)?\s*(?:€|EUR)?\s*(\d{2,3}(?:[.\s]\d{3}))\s*(?:€|EUR)\s*(?:brutto|p\.?\s*a|jahresgehalt|jaehrlich|jährlich|/\s*jahr)',
        re.IGNORECASE
    ),
    # Daily rate: 800-1200€/Tag, Tagessatz 900-1100
    re.compile(
        r'(?:tagessatz|tages-?satz)?\s*(?:€|EUR)?\s*(\d{3,4})\s*(?:[-–bis]+)\s*(?:€|EUR)?\s*(\d{3,4})\s*(?:€|EUR)?\s*(?:/?\s*tag|tagessatz|tages-?satz)',
        re.IGNORECASE
    ),
    # Daily single: Tagessatz: 900€, 1000€/Tag
    re.compile(
        r'(?:tagessatz|tages-?satz)[:\s]*(?:€|EUR)?\s*(\d{3,4})\s*(?:€|EUR)?',
        re.IGNORECASE
    ),
    # Hourly: 50-60€/Stunde, Stundensatz 50-60
    re.compile(
        r'(?:stundensatz|stunden-?satz)?\s*(?:€|EUR)?\s*(\d{2,3})\s*(?:[-–bis]+)\s*(?:€|EUR)?\s*(\d{2,3})\s*(?:€|EUR)?\s*(?:/?\s*(?:stunde|std|h)|stundensatz)',
        re.IGNORECASE
    ),
    # Hourly single: Stundensatz: 65€
    re.compile(
        r'(?:stundensatz|stunden-?satz)[:\s]*(?:€|EUR)?\s*(\d{2,3})\s*(?:€|EUR)?',
        re.IGNORECASE
    ),
    # v1.7.17 (#920): englische Stundensaetze — "Rate: 100 EUR/hour",
    # "€85 per hour", "100-120 EUR/h". Vorher fiel genau der Zweig durch,
    # der ohnehin blind ist (Freelance) — und der Fehler unterschaetzte um
    # Faktor 8-10, konnte also nur passende Stellen lautlos abwerten.
    re.compile(
        r'(?:€|EUR)?\s*(\d{2,3})\s*(?:[-–]|bis)\s*(?:€|EUR)?\s*(\d{2,3})\s*'
        r'(?:€|EUR)?\s*(?:/|per\s+)\s*(?:hour|hr|h)\b',
        re.IGNORECASE
    ),
    re.compile(
        r'(?:€|EUR)\s*(\d{2,3})\s*(?:/|per\s+)\s*(?:hour|hr|h)\b'
        r'|(\d{2,3})\s*(?:€|EUR)\s*(?:/|per\s+)\s*(?:hour|hr|h)\b',
        re.IGNORECASE
    ),
]


def _normalize_salary(val: str) -> float:
    """Convert German salary string to float (60.000 → 60000, 60k → 60000)."""
    val = val.strip().replace(" ", "").replace(".", "")
    if val.lower().endswith("k"):
        return float(val[:-1]) * 1000
    return float(val)


def extract_salary_from_text(text: str) -> tuple:
    """Extract salary from job description text.

    Returns (salary_min, salary_max, salary_type) or (None, None, None).
    salary_type: 'jaehrlich', 'taeglich', 'stuendlich'
    """
    if not text:
        return None, None, None

    for i, pattern in enumerate(SALARY_PATTERNS):
        m = pattern.search(text)
        if m:
            groups = m.groups()
            try:
                if i <= 2:  # Annual patterns
                    if len(groups) >= 2 and groups[1]:
                        s_min = _normalize_salary(groups[0])
                        s_max = _normalize_salary(groups[1])
                        # k-notation
                        if i == 1:
                            s_min *= 1000
                            s_max *= 1000
                    else:
                        s_min = _normalize_salary(groups[0])
                        s_max = s_min * 1.15  # ~15% range for single values
                    if 20000 <= s_min <= 300000:
                        return s_min, s_max, "jaehrlich"
                elif i <= 4:  # Daily rate patterns
                    if len(groups) >= 2 and groups[1]:
                        s_min = float(groups[0])
                        s_max = float(groups[1])
                    else:
                        s_min = float(groups[0])
                        s_max = s_min * 1.1
                    if 200 <= s_min <= 5000:
                        return s_min, s_max, "taeglich"
                else:  # Hourly patterns
                    # #920: die EN-Alternation liefert None-Gruppen —
                    # erst auf die tatsaechlich gefuellten reduzieren.
                    werte = [g for g in groups if g]
                    if len(werte) >= 2:
                        s_min = float(werte[0])
                        s_max = float(werte[1])
                    else:
                        s_min = float(werte[0])
                        s_max = s_min * 1.1
                    if 10 <= s_min <= 500:
                        return s_min, s_max, "stuendlich"
            except (ValueError, TypeError):
                continue

    return None, None, None


# Salary estimation lookup tables
_SALARY_TITLE_RANGES = {
    # (min_annual, max_annual) for festanstellung
    "junior": (40000, 55000),
    "trainee": (35000, 45000),
    "werkstudent": (20000, 30000),
    "praktikant": (15000, 25000),
    "senior": (75000, 110000),
    "lead": (85000, 120000),
    "principal": (95000, 130000),
    "head": (90000, 130000),
    "director": (100000, 150000),
    "manager": (80000, 120000),
    "architekt": (75000, 110000),
    "architect": (75000, 110000),
    "consultant": (60000, 90000),
    "berater": (60000, 90000),
    "ingenieur": (55000, 85000),
    "engineer": (55000, 85000),
    "entwickler": (55000, 85000),
    "developer": (55000, 85000),
    "analyst": (50000, 75000),
    "admin": (45000, 65000),
    "administrator": (45000, 65000),
    "sachbearbeiter": (35000, 50000),
    "projektmanager": (65000, 95000),
    "project manager": (65000, 95000),
    "teamlead": (75000, 105000),
    "teamleiter": (75000, 105000),
    "scrum master": (65000, 90000),
    "product owner": (70000, 100000),
    "data scientist": (65000, 95000),
    "devops": (65000, 95000),
    "plm": (60000, 90000),
    "sap": (65000, 100000),
}

_DAILY_RATE_TITLE_RANGES = {
    # (min_daily, max_daily) for freelance
    "junior": (400, 600),
    "senior": (900, 1400),
    "lead": (1000, 1500),
    "architekt": (1000, 1500),
    "architect": (1000, 1500),
    "consultant": (800, 1200),
    "berater": (800, 1200),
    "ingenieur": (700, 1100),
    "engineer": (700, 1100),
    "entwickler": (700, 1100),
    "developer": (700, 1100),
    "projektmanager": (900, 1300),
    "project manager": (900, 1300),
    "scrum master": (800, 1200),
    "plm": (800, 1200),
    "sap": (900, 1400),
}

# Regional adjustment factors
_REGION_FACTORS = {
    "muenchen": 1.15, "münchen": 1.15, "munich": 1.15,
    "frankfurt": 1.10, "stuttgart": 1.10, "hamburg": 1.08,
    "duesseldorf": 1.05, "düsseldorf": 1.05, "koeln": 1.05, "köln": 1.05,
    "berlin": 1.0,
    "leipzig": 0.90, "dresden": 0.90, "chemnitz": 0.88,
    "rostock": 0.88, "magdeburg": 0.88, "erfurt": 0.90,
}


def estimate_salary(title: str, employment_type: str, location: str) -> tuple:
    """Estimate salary based on job title, type, and location.

    Returns (salary_min, salary_max, salary_type).
    """
    title_lower = (title or "").lower()
    location_lower = (location or "").lower()

    if employment_type == "freelance":
        lookup = _DAILY_RATE_TITLE_RANGES
        default_min, default_max = 700, 1100
        salary_type = "taeglich"
    else:
        lookup = _SALARY_TITLE_RANGES
        default_min, default_max = 50000, 70000
        salary_type = "jaehrlich"

    # Find best matching title keyword
    best_min, best_max = default_min, default_max
    for keyword, (s_min, s_max) in lookup.items():
        if keyword in title_lower:
            best_min, best_max = s_min, s_max
            break

    # Regional adjustment
    factor = 1.0
    for city, f in _REGION_FACTORS.items():
        if city in location_lower:
            factor = f
            break

    return round(best_min * factor), round(best_max * factor), salary_type
