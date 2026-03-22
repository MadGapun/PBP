"""Job Scraper Module — Multi-source job search engine.

Provides SOURCE_REGISTRY for all available job sources,
dynamic keyword building from DB criteria, and the run_search orchestrator.
"""

import hashlib
import json
import logging
import re
import time
from typing import Optional
from urllib.parse import quote

logger = logging.getLogger("bewerbungs_assistent.scraper")


# ── Source Registry ─────────────────────────────────────────────
# Describes all available sources. active_sources in settings DB
# controls which ones are actually used (default: none).

SOURCE_REGISTRY = {
    "bundesagentur": {
        "name": "Bundesagentur für Arbeit",
        "beschreibung": "Oeffentliche Jobboerse der Arbeitsagentur. Groesstes deutsches Stellenportal.",
        "methode": "REST API",
        "login_erforderlich": False,
    },
    "stepstone": {
        "name": "StepStone",
        "beschreibung": "Grosses deutsches Jobportal für Fach- und Führungskräfte.",
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
        "beschreibung": "Projektboerse für Freelancer und Selbstaendige.",
        "methode": "HTML Scraping + Playwright Fallback",
        "login_erforderlich": False,
    },
    "freelance_de": {
        "name": "freelance.de",
        "beschreibung": "Projektboerse für Freelancer und IT-Projekte. Grosse Auswahl an Projekten in DACH.",
        "methode": "HTML Scraping",
        "login_erforderlich": False,
    },
    "linkedin": {
        "name": "LinkedIn",
        "beschreibung": "LinkedIn-Suche funktioniert nur via Claude-in-Chrome Extension (nicht automatisiert). "
                        "Nutze die Chrome-Extension um Stellen zu finden und uebertrage sie mit stelle_manuell_anlegen().",
        "methode": "Claude-in-Chrome (manuell)",
        "login_erforderlich": True,
        "veraltet": True,
        "hinweis": "Automatische Suche via Playwright deaktiviert (#159). Nutze Claude-in-Chrome + stelle_manuell_anlegen().",
    },
    "indeed": {
        "name": "Indeed",
        "beschreibung": "Groesste Jobsuchmaschine weltweit. Aggregiert Stellen aus vielen Quellen.",
        "methode": "Playwright (Browser)",
        "login_erforderlich": False,
    },
    "xing": {
        "name": "XING",
        "beschreibung": "XING blockiert automatisierte Zugriffe. "
                        "Nutze die Chrome-Extension um Stellen zu finden und uebertrage sie mit stelle_manuell_anlegen().",
        "methode": "Claude-in-Chrome (manuell)",
        "login_erforderlich": True,
        "veraltet": True,
        "hinweis": "Automatische Suche via Playwright deaktiviert (#107/#159). Nutze Claude-in-Chrome + stelle_manuell_anlegen().",
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
        "beschreibung": "Grosses deutsches Jobportal mit 3.2 Mio. Besuchern/Monat.",
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

        # Skip blacklisted companies
        if company in bl_firms:
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

    for i, quelle in enumerate(quellen):
        db.update_background_job(
            job_id, "running",
            progress=int((i / total) * 100),
            message=f"Durchsuche {quelle}... ({i+1}/{total})"
        )
        try:
            # Skip deprecated Playwright-based sources (#159)
            if quelle in _deprecated_sources:
                logger.warning(
                    "%s: Automatische Suche deaktiviert. Nutze Claude-in-Chrome + stelle_manuell_anlegen().", quelle)
                continue

            if quelle not in _SCRAPER_MAP:
                logger.warning("Unbekannte Quelle: %s", quelle)
                continue

            module_name, func_name = _SCRAPER_MAP[quelle]
            import importlib
            mod = importlib.import_module(f".{module_name}", package=__package__)
            search_func = getattr(mod, func_name)

            if False:  # Legacy Playwright path — kept for reference
                # Playwright-based scrapers: pass criteria + progress callback
                pass
            else:
                jobs = search_func(params)

            all_jobs.extend(jobs)
            logger.info("%s: %d Stellen gefunden", quelle, len(jobs))
        except ImportError as e:
            logger.warning("Scraper %s nicht verfügbar: %s", quelle, e)
        except Exception as e:
            logger.error("Fehler bei %s: %s", quelle, e, exc_info=True)

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
            if a.get("title") and a.get("status") not in ("abgelehnt", "zurückgezogen")
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

    # Heuristik: employment_type aus Titel/Beschreibung erkennen (#151)
    _freelance_keywords = {"freelance", "freiberuflich", "freiberufler", "kontingent",
                           "projektbasiert", "auf projektbasis"}
    for job in unique:
        if job.get("employment_type", "festanstellung") == "festanstellung":
            haystack = f"{job.get('title', '')} {job.get('description', '')[:500]}".lower()
            if any(kw in haystack for kw in _freelance_keywords):
                job["employment_type"] = "freelance"

    # Geocoding: calculate distance for jobs with location (#167)
    try:
        from ..services.geocoding_service import get_user_coordinates, geocode_and_calculate_distance
        user_coords = get_user_coordinates(db)
        if user_coords:
            geocoded_count = 0
            for job in unique:
                loc = job.get("location", "")
                if loc and not job.get("distance_km"):
                    dist = geocode_and_calculate_distance(loc, user_coords[0], user_coords[1])
                    if dist is not None:
                        job["distance_km"] = dist
                        geocoded_count += 1
            if geocoded_count:
                logger.info("Geocoding: %d Stellen mit Entfernung berechnet", geocoded_count)
    except Exception as e:
        logger.debug("Geocoding in Pipeline fehlgeschlagen (nicht kritisch): %s", e)

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
    }
    if cleanup["stats"]:
        result_data["bereinigung"] = cleanup["stats"]

    msg_parts = [f"{len(unique)} Stellen gefunden (aus {total} Quellen)"]
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


def calculate_score(job: dict, criteria: dict) -> int:
    """Calculate relevance score for a job listing.

    Uses configurable weights from criteria['gewichtung']:
      muss: points per MUSS keyword hit (default 2)
      plus: points per PLUS keyword hit (default 1)
      remote: bonus for remote/hybrid (default 2)
      naehe: bonus for <30km distance (default 2)
      fern_malus: penalty for >200km distance (default 3)
    """
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    w = _parse_weights(criteria)

    # AUSSCHLUSS keywords (check first for early exit)
    ausschluss = criteria.get("keywords_ausschluss", [])
    if any(kw.lower() in text for kw in ausschluss):
        return 0

    # MUSS keywords
    muss = criteria.get("keywords_muss", [])
    muss_found = sum(1 for kw in muss if kw.lower() in text)
    if muss and muss_found == 0:
        return 0

    score = muss_found * w["muss"]

    # PLUS keywords
    plus = criteria.get("keywords_plus", [])
    score += sum(1 for kw in plus if kw.lower() in text) * w["plus"]

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

    muss_hits = [kw for kw in muss if kw.lower() in text]
    missing_muss = [kw for kw in muss if kw.lower() not in text]
    plus_hits = [kw for kw in plus if kw.lower() in text]

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

    return {
        "total_score": max(0, total),
        "muss_hits": muss_hits,
        "missing_muss": missing_muss,
        "plus_hits": plus_hits,
        "factors": factors,
        "risks": risks,
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
