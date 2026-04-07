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
    "bundesagentur": {
        "name": "Bundesagentur für Arbeit",
        "beschreibung": "Öffentliche Jobbörse der Arbeitsagentur. Größtes deutsches Stellenportal.",
        "methode": "REST API",
        "login_erforderlich": False,
    },
    "stepstone": {
        "name": "StepStone",
        "beschreibung": "Großes deutsches Jobportal für Fach- und Führungskräfte.",
        "methode": "Playwright (Browser)",
        "login_erforderlich": False,
    },
    "hays": {
        "name": "Hays",
        "beschreibung": "Personaldienstleister mit eigenem Stellenportal. Schwerpunkt Engineering & IT.",
        "methode": "Sitemap + JSON-LD",
        "login_erforderlich": False,
    },
    "freelancermap": {
        "name": "Freelancermap",
        "beschreibung": "Projektbörse für Freelancer und Selbstständige.",
        "methode": "HTML Scraping + Playwright Fallback",
        "login_erforderlich": False,
    },
    "freelance_de": {
        "name": "freelance.de",
        "beschreibung": "Projektbörse für Freelancer und IT-Projekte. Große Auswahl an Projekten in DACH.",
        "methode": "HTML Scraping",
        "login_erforderlich": False,
    },
    "indeed": {
        "name": "Indeed",
        "beschreibung": "Größte Jobsuchmaschine weltweit. Aggregiert Stellen aus vielen Quellen.",
        "methode": "Playwright (Browser)",
        "login_erforderlich": False,
    },
    "monster": {
        "name": "Monster",
        "beschreibung": "Internationales Jobportal mit breitem Stellenangebot.",
        "methode": "Playwright (Browser)",
        "login_erforderlich": False,
    },
    "ingenieur_de": {
        "name": "ingenieur.de (VDI)",
        "beschreibung": "Engineering-Jobboerse des VDI. Spezialisiert auf Ingenieur- und Technik-Stellen.",
        "methode": "HTML Scraping",
        "login_erforderlich": False,
    },
    "heise_jobs": {
        "name": "Heise Jobs",
        "beschreibung": "IT-Stellenmarkt von Heise Verlag. Starke IT/Admin-Community.",
        "methode": "HTML Scraping + JSON-LD",
        "login_erforderlich": False,
    },
    "gulp": {
        "name": "GULP",
        "beschreibung": "Top IT/Engineering Freelance-Projektboerse. Grosse Auswahl an IT-Projekten.",
        "methode": "HTML Scraping + JSON-LD",
        "login_erforderlich": False,
    },
    "solcom": {
        "name": "SOLCOM",
        "beschreibung": "IT + Engineering Projektportal. Personaldienstleister für IT-Projekte.",
        "methode": "HTML Scraping + JSON-LD",
        "login_erforderlich": False,
    },
    "stellenanzeigen_de": {
        "name": "Stellenanzeigen.de",
        "beschreibung": "Großes deutsches Jobportal mit 3.2 Mio. Besuchern/Monat.",
        "methode": "HTML Scraping + JSON-LD",
        "login_erforderlich": False,
    },
    "jobware": {
        "name": "Jobware",
        "beschreibung": "Premium-Jobportal für Spezialisten und Führungskräfte.",
        "methode": "HTML Scraping + JSON-LD",
        "login_erforderlich": False,
    },
    "ferchau": {
        "name": "FERCHAU",
        "beschreibung": "Engineering & IT Personaldienstleister. Grosser Footprint in Engineering.",
        "methode": "HTML Scraping + JSON-LD",
        "login_erforderlich": False,
    },
    "kimeta": {
        "name": "Kimeta",
        "beschreibung": "Deutscher Job-Aggregator. Buendelt Stellen aus vielen Quellen.",
        "methode": "HTML Scraping",
        "login_erforderlich": False,
    },
    # ── Beta-Quellen (inoffiziell, nicht in README beworben) ────
    "linkedin": {
        "name": "LinkedIn",
        "beschreibung": "LinkedIn-Suche via Claude-in-Chrome Extension (manuell, nicht automatisiert).",
        "methode": "Claude-in-Chrome (manuell)",
        "login_erforderlich": True,
        "veraltet": True,
        "beta": True,
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
        "warnung": "Manuell via Claude-in-Chrome. Verbraucht mehr Token als normale Quellen.",
        "hinweis": "Automatische Suche deaktiviert (#107/#159). Nutze Claude-in-Chrome + stelle_manuell_anlegen().",
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

    # General keywords (for API sources)
    general = list(all_kw)

    # StepStone: URL-based search
    stepstone_urls = []
    for kw in all_kw:
        slug = kw.lower().replace(" ", "-").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
        stepstone_urls.append(f"https://www.stepstone.de/jobs/{slug}")

    # Hays: lowercase keywords for sitemap URL matching
    hays_keywords = [kw.lower().replace(" ", "-") for kw in all_kw]

    # Freelancermap: query parameter URLs
    freelancermap_urls = [
        f"https://www.freelancermap.de/projektboerse.html?q={quote(kw)}"
        for kw in all_kw
    ]

    # freelance.de: skill-based URLs (keyword → Skill-Projekte)
    freelance_de_urls = [
        f"https://www.freelance.de/{quote(kw.replace(' ', '-'))}-Projekte"
        for kw in all_kw
    ]

    # Indeed/Monster: full search queries (with region if available)
    queries = list(all_kw)

    return {
        "general": general,
        "stepstone_urls": stepstone_urls,
        "hays_keywords": hays_keywords,
        "freelancermap_urls": freelancermap_urls,
        "freelance_de_urls": freelance_de_urls,
        "indeed_queries": queries,
        "monster_queries": queries,
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

    # Per-source timeout: 90 seconds default, Stepstone 180s (#200, #248, #252)
    _SOURCE_TIMEOUT = 90
    _STEPSTONE_TIMEOUT = 180
    skipped_sources = []

    # #234: Playwright-basierte Scraper sequentiell, httpx-basierte parallel
    _PLAYWRIGHT_SOURCES = {"stepstone", "indeed", "monster", "freelancermap"}

    # #252: Stepstone immer als letztes Portal starten
    if "stepstone" in quellen:
        quellen = [q for q in quellen if q != "stepstone"] + ["stepstone"]

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

    def _load_scraper(quelle):
        """Load scraper function by source name."""
        module_name, func_name = _SCRAPER_MAP[quelle]
        import importlib
        mod = importlib.import_module(f".{module_name}", package=__package__)
        return getattr(mod, func_name)

    # #234: Separate httpx (parallel) and playwright (sequential) sources
    httpx_quellen = []
    sequential_quellen = []
    for quelle in quellen:
        if quelle in _deprecated_sources:
            logger.warning(
                "%s: Automatische Suche deaktiviert. Nutze Claude-in-Chrome + stelle_manuell_anlegen().", quelle)
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
        source_status[q] = {"status": "skipped", "count": 0, "time_s": 0, "detail": "deprecated"}

    # Phase 1: Run httpx-based scrapers in parallel (#234)
    if httpx_quellen:
        db.update_background_job(
            job_id, "running", progress=0,
            message=f"Durchsuche {len(httpx_quellen)} Quellen parallel..."
        )
        parallel_executor = ThreadPoolExecutor(max_workers=min(4, len(httpx_quellen)))
        futures = {}
        _start_times = {}
        for quelle in httpx_quellen:
            try:
                search_func = _load_scraper(quelle)
                timeout = _STEPSTONE_TIMEOUT if quelle == "stepstone" else _SOURCE_TIMEOUT
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
    for quelle in sequential_quellen:
        completed += 1
        db.update_background_job(
            job_id, "running",
            progress=int((completed / total) * 100),
            message=f"Durchsuche {quelle}... ({completed}/{total})"
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

    # #251: Stellenalter automatisch begrenzen (2x Suchintervall, min 7 Tage)
    last_search_at = db.get_profile_setting("last_search_at", None)
    if last_search_at:
        try:
            from datetime import datetime, timedelta
            last_dt = datetime.fromisoformat(last_search_at)
            now_dt = datetime.now()
            interval = (now_dt - last_dt).days
            max_age_days = max(7, interval * 2)
            cutoff_dt = (now_dt - timedelta(days=max_age_days)).isoformat()
            before_age = len(unique)
            unique = [j for j in unique if (j.get("found_at") or j.get("published_at") or "9999") >= cutoff_dt[:10]]
            if before_age > len(unique):
                logger.info("Stellenalter-Filter: %d von %d Stellen aelter als %d Tage",
                            before_age - len(unique), before_age, max_age_days)
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

    db.save_jobs(unique)
    db.set_profile_setting("last_search_at", time.strftime("%Y-%m-%dT%H:%M:%S"))

    result_data = {
        "total": len(unique),
        "quellen": {q: sum(1 for j in unique if j.get("source") == q) for q in quellen},
        "quellen_status": source_status,  # #316: Per-Source Fokus-Modus
    }
    if cleanup["stats"]:
        result_data["bereinigung"] = cleanup["stats"]

    successful_sources = total - len(skipped_sources)
    msg_parts = [f"{len(unique)} Stellen gefunden (aus {successful_sources}/{total} Quellen)"]
    if skipped_sources:
        msg_parts.append(f"Uebersprungen: {', '.join(skipped_sources)}")
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
}


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
    1. Keyword als Substring im Text (exakt)
    2. Normalisiertes Keyword im normalisierten Text (Umlaute)
    3. Einzelne Wörter des Keywords matchen alle (Multi-Word Split)
    4. Ein Synonym des Keywords im Text vorkommt
    """
    kw_lower = keyword.lower().strip()
    text_lower = text.lower()

    # 1. Exakter Substring-Match
    if kw_lower in text_lower:
        return True

    # 2. Umlaut-normalisierter Match
    kw_norm = _normalize_for_matching(kw_lower)
    text_norm = _normalize_for_matching(text_lower)
    if kw_norm in text_norm:
        return True

    # 3. Multi-Word: Alle Einzelwörter müssen im Text vorkommen
    #    z.B. "PLM Projektleiter" matcht "Projektleiter (m/w/d) im Bereich PLM"
    words = re.split(r'[\s\-/]+', kw_lower)
    if len(words) > 1:
        if all(w in text_lower or _normalize_for_matching(w) in text_norm for w in words if len(w) > 1):
            return True

    # 4. Synonym-Match
    for syn_key, synonyms in _SYNONYM_MAP.items():
        if syn_key == kw_lower or kw_lower in synonyms:
            # Prüfe ob das Keyword oder ein Synonym im Text vorkommt
            all_terms = [syn_key] + synonyms
            for term in all_terms:
                if term in text_lower or _normalize_for_matching(term) in text_norm:
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

    # #180: Warnung bei fehlender Beschreibung
    desc = job.get("description") or ""
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
    }


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
