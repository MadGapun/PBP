"""Job Scraper Module — Multi-source job search engine.

Provides SOURCE_REGISTRY for all available job sources,
dynamic keyword building from DB criteria, and the run_search orchestrator.
"""

import hashlib
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional
from urllib.parse import quote

logger = logging.getLogger("bewerbungs_assistent.scraper")


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
        # #500: Live-Test 2026-04-25 — alle bekannten URLs liefern HTTP 404.
        # Quelle bleibt im Registry sichtbar, ist aber gesperrt; Reaktivierung
        # nur ueber bewussten "Trotzdem aktivieren"-Klick.
        "defekt": True,
        "defekt_grund": "URL veraltet (HTTP 404 seit 2026-04-25)",
        "manueller_fallback": "https://www.ingenieur.de/jobs (im Browser oder Chrome-Extension oeffnen)",
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
        "methode": "HTML Scraping + JSON-LD",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
        # #500: Live-Test 2026-04-25 — alle bekannten Such-URLs HTTP 404.
        "defekt": True,
        "defekt_grund": "URL veraltet (HTTP 404 seit 2026-04-25, vermutlich SPA-Migration)",
        "manueller_fallback": "https://www.gulp.de/ (im Browser nach IT-Projekten suchen)",
    },
    "solcom": {
        "name": "SOLCOM",
        "beschreibung": "IT + Engineering Projektportal. Personaldienstleister fuer IT-Projekte.",
        "methode": "HTML Scraping + JSON-LD",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
        "defekt": True,
        "defekt_grund": "Anti-Bot-Schutz (HTTP 403 seit 2026-04-25)",
        "manueller_fallback": "https://www.solcom.de/projekte (Browser oder Chrome-Extension)",
    },
    "stellenanzeigen_de": {
        "name": "Stellenanzeigen.de",
        "beschreibung": "Grosses deutsches Jobportal mit 3.2 Mio. Besuchern/Monat.",
        "methode": "HTML Scraping + JSON-LD",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    "jobware": {
        "name": "Jobware",
        "beschreibung": "Premium-Jobportal fuer Spezialisten und Fuehrungskraefte.",
        "methode": "HTML Scraping + JSON-LD",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
    },
    "ferchau": {
        "name": "FERCHAU",
        "beschreibung": "Engineering & IT Personaldienstleister. Grosser Footprint in Engineering.",
        "methode": "HTML Scraping + JSON-LD",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
        "defekt": True,
        "defekt_grund": "URL veraltet (HTTP 404 seit 2026-04-25)",
        "manueller_fallback": "https://www.ferchau.com/de/de (Karriere-Bereich im Browser)",
    },
    "kimeta": {
        "name": "Kimeta",
        "beschreibung": "Deutscher Job-Aggregator. Buendelt Stellen aus vielen Quellen.",
        "methode": "HTML Scraping",
        "login_erforderlich": False,
        "geschwindigkeit": "schnell",
        "defekt": True,
        "defekt_grund": "Such-Endpunkt liefert nur Kategorie-Liste (235 Berufsgruppen-Links), Stellen werden via JavaScript nachgeladen",
        "manueller_fallback": "https://www.kimeta.de/jobs?q=Python&l=Hamburg (im Browser oder Chrome-Extension)",
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
        "geschwindigkeit": "langsam",
        "warnung": "Benoetigt Google Chrome. Kann 30-90 Sekunden dauern. Alternativ: Lass Claude gezielt auf indeed.com suchen.",
    },
    "monster": {
        "name": "Monster",
        "beschreibung": "Internationales Jobportal mit breitem Stellenangebot.",
        "methode": "Playwright (Browser)",
        "login_erforderlich": False,
        "geschwindigkeit": "langsam",
        "warnung": "Benoetigt Google Chrome. Kann 30-90 Sekunden dauern.\nPortal aendert haeufig das Layout — bei Fehlern: Lass Claude gezielt auf monster.de suchen.",
        "beta": True,
        "defekt": True,
        "defekt_grund": "monster.de antwortet nicht (Connect-Timeout 2026-04-25)",
        "manueller_fallback": "https://www.monster.de (im Browser pruefen, ggf. Chrome-Extension)",
    },
    # ── Manuelle Quellen (Claude-in-Chrome, nicht automatisiert) ──
    "linkedin": {
        "name": "LinkedIn",
        "beschreibung": "LinkedIn-Suche via Claude-in-Chrome Extension (manuell, nicht automatisiert).",
        "methode": "Claude-in-Chrome (manuell)",
        "login_erforderlich": True,
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
        "manueller_fallback": True,
        "geschwindigkeit": "manuell",
        "warnung": "Benoetigt einen Google-Account in Chrome mit Claude-in-Chrome-Extension.",
        "hinweis": "Tool jobsuche_starten liefert die Google-Jobs-URL — in Chrome oeffnen "
                    "und Treffer mit stelle_manuell_anlegen() uebernehmen. Kein Login-Click "
                    "im Dashboard noetig.",
        "beta": True,
    },
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
    "kimeta": ("kimeta", "search_kimeta"),
    "jobspy_linkedin": ("jobspy_source", "search_jobspy_linkedin"),
    "jobspy_indeed": ("jobspy_source", "search_jobspy_indeed"),
    "jobspy_glassdoor": ("jobspy_source", "search_jobspy_glassdoor"),
    "jobspy_google": ("jobspy_source", "search_jobspy_google"),
    "arbeitnow": ("arbeitnow", "search_arbeitnow"),
    "greenhouse": ("greenhouse", "search_greenhouse"),
    "google_jobs": ("google_jobs", "search_google_jobs"),
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

        # Skip blacklisted companies (Substring-Match: "CIDEON" matcht "CIDEON Software GmbH")
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
    _deactivated = set()
    try:
        for h in db.get_scraper_health():
            if not h.get("is_active"):
                _deactivated.add(h["scraper_name"])
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
                source_status[quelle] = {"status": "error", "count": 0, "time_s": 0, "detail": str(e)}

        for future in futures:
            quelle, timeout = futures[future]
            elapsed = round(time.time() - _start_times.get(quelle, time.time()), 1)
            try:
                jobs = future.result(timeout=timeout)
                all_jobs.extend(jobs)
                logger.info("%s: %d Stellen gefunden", quelle, len(jobs))
                elapsed = round(time.time() - _start_times.get(quelle, time.time()), 1)
                source_status[quelle] = {"status": "ok", "count": len(jobs), "time_s": elapsed}
            except FuturesTimeoutError:
                logger.warning("%s: Timeout nach %ds — uebersprungen", quelle, timeout)
                skipped_sources.append(quelle)
                source_status[quelle] = {"status": "timeout", "count": 0, "time_s": timeout}
            except Exception as e:
                logger.error("Fehler bei %s: %s", quelle, e, exc_info=True)
                skipped_sources.append(quelle)
                source_status[quelle] = {"status": "error", "count": 0, "time_s": elapsed, "detail": str(e)[:100]}
            completed += 1
            # #316: Fokus-Modus Progress mit Per-Source-Status
            ok_count = sum(1 for s in source_status.values() if s["status"] == "ok")
            db.update_background_job(
                job_id, "running",
                progress=int((completed / total) * 100),
                message=f"{quelle}: {source_status[quelle]['status']} ({source_status[quelle]['count']} Stellen) | {ok_count}/{completed} Quellen OK"
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
                source_status[quelle] = {"status": "timeout", "count": 0, "time_s": timeout}
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
            source_status[quelle] = {"status": "error", "count": 0, "time_s": 0, "detail": str(e)[:100]}
        except Exception as e:
            elapsed = round(time.time() - _start, 1)
            logger.error("Fehler bei %s: %s", quelle, e, exc_info=True)
            skipped_sources.append(quelle)
            source_status[quelle] = {"status": "error", "count": 0, "time_s": elapsed, "detail": str(e)[:100]}

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
    min_score_threshold = criteria.get("min_score_schwelle", 1)
    before = len(unique)
    unique = [j for j in unique if j.get("score", 0) >= min_score_threshold]
    if before > len(unique):
        logger.info("Score-Filter: %d von %d Stellen verworfen (Score < %d)",
                     before - len(unique), before, min_score_threshold)

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
            )
        except Exception as e:
            logger.debug("Scraper health update failed for %s: %s", quelle, e)

    # #432: Auto-deactivate scrapers with 10+ consecutive failures
    try:
        for h in db.get_scraper_health():
            if h.get("consecutive_failures", 0) >= 10 and h.get("is_active"):
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

    db.update_background_job(
        job_id, "fertig", progress=100,
        message=" | ".join(msg_parts),
        result=result_data,
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

    # Detail markers win. We require at least one alphanumeric char after
    # the marker so ".../projekt/" (empty suffix) stays a search-style URL.
    for marker in _DETAIL_URL_PATH_MARKERS:
        idx = u.find(marker)
        if idx < 0:
            continue
        rest = u[idx + len(marker):]
        if re.match(r"[a-z0-9]", rest):
            return False

    # Strip scheme+host to look at path+query only
    try:
        without_scheme = u.split("://", 1)[1]
        path_and_query = "/" + without_scheme.split("/", 1)[1] if "/" in without_scheme else "/"
    except Exception:
        path_and_query = u

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


def fetch_description_from_detail(url: str, client, *, timeout: float = 15) -> str:
    """Fetch job description from a detail page via httpx.

    Tries JSON-LD first, then common HTML content selectors.
    Returns plain text description (max 2000 chars) or empty string.
    """
    try:
        from bs4 import BeautifulSoup
        resp = client.get(url, timeout=timeout)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")

        # Strategy 1: JSON-LD structured data
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else data.get("@graph", [data])
                for item in items:
                    if item.get("@type") == "JobPosting":
                        desc = item.get("description", "")
                        if desc:
                            text = BeautifulSoup(desc, "html.parser").get_text(separator=" ", strip=True)
                            return text[:2000]
            except Exception:
                continue

        # Strategy 2: Common content selectors
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
                    return text[:2000]

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
        "remote": w.get("remote", 2),
        "naehe": w.get("naehe", 2),
        "fern_malus": w.get("fern_malus", 3),
        "gehalt": w.get("gehalt", 1),
    }


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
    "praktikant": ["praktikantin", "praktikanten", "praktikantinnen",
                   "praktikum", "praktikumsplatz", "pflichtpraktikum",
                   "praktikumsstelle", "intern", "internship"],
    "praktikum": ["praktikant", "praktikantin", "praktikanten",
                  "praktikumsplatz", "pflichtpraktikum", "praktikumsstelle",
                  "intern", "internship"],
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
    """
    description = job.get("description", "") or ""
    title = job.get("title", "") or ""
    has_description = len(description.strip()) > 50  # Mindestens 50 Zeichen fuer sinnvollen Match
    text = f"{title} {description}".lower()
    w = _parse_weights(criteria)

    # #180: Markiere Jobs ohne Beschreibung damit Claude/Frontend warnen kann
    if not has_description:
        job["_beschreibung_fehlt"] = True

    # AUSSCHLUSS keywords (check first for early exit)
    ausschluss = criteria.get("keywords_ausschluss", [])
    if any(_fuzzy_keyword_match(kw, text) for kw in ausschluss):
        return 0

    # MUSS keywords — #183: Fuzzy-Matching statt exakter Substring
    muss = criteria.get("keywords_muss", [])
    muss_found = sum(1 for kw in muss if _fuzzy_keyword_match(kw, text))
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
        return 0

    score = muss_found * w["muss"]

    # PLUS keywords — #183: Fuzzy-Matching
    plus = criteria.get("keywords_plus", [])
    score += sum(1 for kw in plus if _fuzzy_keyword_match(kw, text)) * w["plus"]

    # Distance bonus/malus (#60, #112, #166) — typ-abhaengige Entfernung
    dist = job.get("distance_km")
    emp_type = job.get("employment_type", "festanstellung")
    max_dist_map = criteria.get("max_entfernung", {})
    # Defaults: Festanstellung 50km, Freelance 200km, Rest 50km
    _default_max = {"festanstellung": 50, "freelance": 200, "teilzeit": 30, "praktikum": 50, "werkstudent": 50}
    type_max_dist = max_dist_map.get(emp_type) or _default_max.get(emp_type, 50)
    if dist is not None:
        if dist > type_max_dist * 4:
            # Way beyond limit: full penalty
            score -= w["fern_malus"]
        elif dist > type_max_dist * 2:
            # Moderately beyond: slight penalty
            score -= 1
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

    return max(0, score)


def fit_analyse(job: dict, criteria: dict) -> dict:
    """Detailed fit analysis for a job — used by dashboard API.

    Returns dict with total_score, muss_hits, missing_muss, plus_hits,
    factors (breakdown), and risks.
    """
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    w = _parse_weights(criteria)

    muss = criteria.get("keywords_muss", [])
    plus = criteria.get("keywords_plus", [])

    # #183: Fuzzy-Matching auch in der Fit-Analyse
    muss_hits = [kw for kw in muss if _fuzzy_keyword_match(kw, text)]
    missing_muss = [kw for kw in muss if not _fuzzy_keyword_match(kw, text)]
    plus_hits = [kw for kw in plus if _fuzzy_keyword_match(kw, text)]

    factors = {}
    total = 0

    if muss_hits:
        pts = len(muss_hits) * w["muss"]
        factors[f"MUSS-Keywords ({len(muss_hits)} Treffer)"] = pts
        total += pts

    if plus_hits:
        pts = len(plus_hits) * w["plus"]
        factors[f"PLUS-Keywords ({len(plus_hits)} Treffer)"] = pts
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
        if dist > fit_type_max * 4:
            factors[f"Entfernung: {int(dist)} km (Max {fit_emp_type}: {fit_type_max} km)"] = -w["fern_malus"]
            total -= w["fern_malus"]
        elif dist > fit_type_max * 2:
            factors[f"Entfernung: {int(dist)} km (ueber Max {fit_type_max} km)"] = -1
            total -= 1
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
    if salary_min:
        salary_type = job.get("salary_type", "jaehrlich")
        emp_type = job.get("employment_type", "festanstellung")
        if salary_type == "taeglich" or emp_type == "freelance":
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

    # #305: Hochschulabschluss-Erkennung
    desc = job.get("description") or ""
    degree_required = _detect_degree_required(f"{job.get('title', '')} {desc}")
    has_degree = _profile_has_degree(criteria)
    if degree_required and not has_degree:
        risks.insert(0,
            "HOCHSCHULABSCHLUSS GEFORDERT — Stelle fordert formalen Abschluss "
            "(Studium/Bachelor/Master). Dein Profil enthält keinen. "
            "Risiko: Automatische ATS-Aussortierung möglich, "
            "selbst bei passender Berufserfahrung."
        )
        factors["Hochschulabschluss fehlt"] = -2
        total -= 2

    # #180: Warnung bei fehlender Beschreibung
    if len(desc.strip()) < 50:
        risks.insert(0, "BESCHREIBUNG FEHLT — Score ist unzuverlässig! "
                     "Lade die Stellenbeschreibung nach (stelle_manuell_anlegen oder URL öffnen).")

    return {
        "total_score": max(0, total),
        "muss_hits": muss_hits,
        "missing_muss": missing_muss,
        "plus_hits": plus_hits,
        "factors": factors,
        "risks": risks,
        "beschreibung_vorhanden": len(desc.strip()) >= 50,
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
]


def _has_degree_relaxation(text: str) -> bool:
    """True wenn der Text Quereinsteiger-/Abschwaechungs-Klauseln enthaelt (#536)."""
    text_lower = _normalize_for_matching(text)
    return any(pat in text_lower for pat in _DEGREE_RELAXATION_PATTERNS)


def _detect_degree_required(text: str) -> bool:
    """Erkennt ob eine Stellenbeschreibung einen Hochschulabschluss fordert (#305).

    v1.6.4 (#536): Quereinsteiger-Klauseln werden jetzt beruecksichtigt.
    Wenn die Beschreibung explizit Quereinsteiger einlaedt, wird die formale
    Anforderung als nicht-bindend gewertet (False zurueckgegeben).
    """
    text_lower = _normalize_for_matching(text)
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
                    if len(groups) >= 2 and groups[1]:
                        s_min = float(groups[0])
                        s_max = float(groups[1])
                    else:
                        s_min = float(groups[0])
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
