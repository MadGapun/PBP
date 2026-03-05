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
        "name": "Bundesagentur fuer Arbeit",
        "beschreibung": "Oeffentliche Jobboerse der Arbeitsagentur. Groesstes deutsches Stellenportal.",
        "methode": "REST API",
        "login_erforderlich": False,
    },
    "stepstone": {
        "name": "StepStone",
        "beschreibung": "Grosses deutsches Jobportal fuer Fach- und Fuehrungskraefte.",
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
        "beschreibung": "Projektboerse fuer Freelancer und Selbstaendige.",
        "methode": "HTML Scraping + Playwright Fallback",
        "login_erforderlich": False,
    },
    "freelance_de": {
        "name": "freelance.de",
        "beschreibung": "Projektboerse fuer Freelancer und IT-Projekte. Grosse Auswahl an Projekten in DACH.",
        "methode": "HTML Scraping",
        "login_erforderlich": False,
    },
    "linkedin": {
        "name": "LinkedIn",
        "beschreibung": "Internationales Business-Netzwerk. Beim ersten Start oeffnet sich ein Browser zur Anmeldung.",
        "methode": "Playwright (Browser)",
        "login_erforderlich": True,
    },
    "indeed": {
        "name": "Indeed",
        "beschreibung": "Groesste Jobsuchmaschine weltweit. Aggregiert Stellen aus vielen Quellen.",
        "methode": "Playwright (Browser)",
        "login_erforderlich": False,
    },
    "xing": {
        "name": "XING",
        "beschreibung": "Deutsches Business-Netzwerk. Beim ersten Start oeffnet sich ein Browser zur Anmeldung.",
        "methode": "Playwright (Browser)",
        "login_erforderlich": True,
    },
    "monster": {
        "name": "Monster",
        "beschreibung": "Internationales Jobportal mit breitem Stellenangebot.",
        "methode": "Playwright (Browser)",
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
}


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

    for i, quelle in enumerate(quellen):
        db.update_background_job(
            job_id, "running",
            progress=int((i / total) * 100),
            message=f"Durchsuche {quelle}... ({i+1}/{total})"
        )
        try:
            if quelle not in _SCRAPER_MAP:
                logger.warning("Unbekannte Quelle: %s", quelle)
                continue

            module_name, func_name = _SCRAPER_MAP[quelle]
            import importlib
            mod = importlib.import_module(f".{module_name}", package=__package__)
            search_func = getattr(mod, func_name)

            # Playwright-based scrapers may use progress callback
            if quelle in ("linkedin", "xing"):
                def _progress(msg, _jid=job_id):
                    db.update_background_job(_jid, "running", message=msg)
                jobs = search_func(params, progress_callback=_progress)
            else:
                jobs = search_func(params)

            all_jobs.extend(jobs)
            logger.info("%s: %d Stellen gefunden", quelle, len(jobs))
        except ImportError as e:
            logger.warning("Scraper %s nicht verfuegbar: %s", quelle, e)
        except Exception as e:
            logger.error("Fehler bei %s: %s", quelle, e, exc_info=True)

    # Deduplicate
    seen = set()
    unique = []
    for job in all_jobs:
        if job["hash"] not in seen:
            seen.add(job["hash"])
            unique.append(job)

    # Score, extract/estimate salary, and save
    criteria = db.get_search_criteria()
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

    db.save_jobs(unique)
    db.set_setting("last_search_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
    db.update_background_job(
        job_id, "fertig", progress=100,
        message=f"{len(unique)} Stellen gefunden (aus {total} Quellen)",
        result={"total": len(unique), "quellen": {q: sum(1 for j in unique if j.get("source") == q) for q in quellen}}
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
    }


def calculate_score(job: dict, criteria: dict) -> int:
    """Calculate relevance score for a job listing.

    Uses configurable weights from criteria['gewichtung']:
      muss: points per MUSS keyword hit (default 2)
      plus: points per PLUS keyword hit (default 1)
      remote: bonus for remote/hybrid (default 2)
      naehe: bonus for <80km distance (default 2)
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

    # Distance bonus/malus
    dist = job.get("distance_km")
    if dist is not None:
        if dist > 200:
            score -= w["fern_malus"]
        elif dist < 80:
            score += w["naehe"]

    # Remote bonus
    remote = job.get("remote_level", "unbekannt")
    if remote in ("remote", "hybrid"):
        score += w["remote"]

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
    if dist is not None:
        if dist > 200:
            factors[f"Entfernung: {int(dist)} km"] = -w["fern_malus"]
            total -= w["fern_malus"]
        elif dist < 80:
            factors[f"Naehe: {int(dist)} km"] = w["naehe"]
            total += w["naehe"]

    risks = []
    if missing_muss:
        risks.append(f"{len(missing_muss)} MUSS-Keywords nicht gefunden")
    if not job.get("url"):
        risks.append("Kein Link zur Stellenanzeige vorhanden")
    if job.get("employment_type") == "freelance" and not job.get("salary_info"):
        risks.append("Freelance ohne Tagessatz-Angabe")

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
