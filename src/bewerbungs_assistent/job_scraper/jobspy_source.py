"""JobSpy-basierte Quellen: LinkedIn + Indeed.de (#490).

Wrapper um die MIT-lizenzierte Open-Source-Bibliothek `python-jobspy`
(speedyapply/JobSpy). Deckt LinkedIn und Indeed in einem Aufruf ab,
ohne eigenen Scraper-Code fuer diese Portale zu schreiben oder zu warten.

Hinweise:
    - `python-jobspy` ist eine Opt-In-Dependency im Extra `scraper`.
      Ist das Package nicht installiert, liefert die Suche 0 Treffer mit
      einer deutlichen Log-Meldung statt mit einem Crash.
    - LinkedIn rate-limitet ab ca. Seite 10 pro IP (HTTP 429). Wir
      halten `results_wanted` niedrig und fangen 429 ueber `try/except`
      ab — in dem Fall macht der Aufrufer einfach ohne LinkedIn-Treffer
      weiter, andere Adapter laufen nicht mit rein.
    - Fuer LinkedIn wird bei englischen Keywords ein deutsches Aequivalent
      mitgeschickt — LinkedIn filtert auf DE nur sauber, wenn der Begriff
      ebenfalls deutsch ist (Issue-Hinweis).

Lizenz-Attribution: python-jobspy ist MIT, upstream
https://github.com/speedyapply/JobSpy — in der README verlinkt.
"""

from __future__ import annotations

import logging
from typing import Any

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.jobspy")

# Englische Begriffe, die LinkedIn fuer DE-Treffer zusaetzlich als
# deutsche Query braucht. Konservativ gehalten — es geht um haeufige
# „false friends", nicht um vollstaendige Lokalisierung.
_DE_EQUIVALENTS = {
    "project manager": "Projektleiter",
    "software engineer": "Softwareentwickler",
    "data analyst": "Datenanalyst",
    "product manager": "Produktmanager",
    "devops engineer": "DevOps Ingenieur",
    "consultant": "Berater",
    "plm manager": "PLM Projektleiter",
    "plm": "PLM",
}


def _ensure_jobspy():
    """Import jobspy lazily. None if package fehlt."""
    try:
        from jobspy import scrape_jobs  # type: ignore
        return scrape_jobs
    except ImportError:
        logger.info(
            "python-jobspy nicht installiert — LinkedIn/Indeed via JobSpy "
            "werden uebersprungen. Install: pip install python-jobspy"
        )
        return None


def _expand_keywords_for_linkedin(keywords: list[str]) -> list[str]:
    """Ergaenzt englische Begriffe um deutsche Aequivalente (#490)."""
    out: list[str] = []
    for kw in keywords:
        out.append(kw)
        eq = _DE_EQUIVALENTS.get(kw.lower().strip())
        if eq and eq not in out:
            out.append(eq)
    return out


def _map_row(row: Any, site: str) -> dict:
    """Mappt eine JobSpy-DataFrame-Zeile auf das PBP-Schema."""
    def _g(name: str, default: str = "") -> str:
        val = row.get(name, default) if hasattr(row, "get") else default
        if val is None:
            return default
        return str(val)

    title = _g("title")
    company = _g("company", "Nicht angegeben")
    location = _g("location")
    description = _g("description")
    url = _g("job_url_direct") or _g("job_url")
    source_key = f"jobspy_{site}"
    remote_flag = row.get("is_remote") if hasattr(row, "get") else None
    job_type = _g("job_type")

    if remote_flag is True:
        remote = "remote"
    elif remote_flag is False:
        remote = "vor_ort"
    else:
        remote = detect_remote_level(f"{title} {location} {description[:500]}")

    salary_min = row.get("min_amount") if hasattr(row, "get") else None
    salary_max = row.get("max_amount") if hasattr(row, "get") else None

    return {
        "hash": stelle_hash(source_key, f"{company} {title}"),
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "source": source_key,
        "description": description[:2000],
        "employment_type": _normalize_job_type(job_type),
        "remote_level": remote,
        "salary_min": _to_int_or_none(salary_min),
        "salary_max": _to_int_or_none(salary_max),
    }


def _to_int_or_none(val) -> int | None:
    try:
        if val is None:
            return None
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _normalize_job_type(job_type: str) -> str:
    """JobSpy liefert 'fulltime', 'parttime', 'contract' etc. → PBP-Taxonomy."""
    t = (job_type or "").lower()
    if "contract" in t or "freelance" in t:
        return "freelance"
    if "intern" in t or "praktik" in t:
        return "praktikum"
    if "student" in t or "werk" in t:
        return "werkstudent"
    return "festanstellung"


def _search_site(site: str, keywords: list[str], location: str,
                  max_results: int = 25, hours_old: int = 168,
                  google_search_term: str | None = None) -> list[dict]:
    """Einmaliger Aufruf gegen eine einzelne JobSpy-Site.

    `country_indeed` wird IMMER auf "Germany" gesetzt — JobSpy crasht
    intern, wenn None uebergeben wird (Country.from_string ruft .strip()
    auf). Fuer Sites, die das Argument ignorieren (linkedin, glassdoor,
    google), ist das harmlos.
    """
    scrape = _ensure_jobspy()
    if scrape is None:
        return []
    if not keywords:
        return []

    if site == "linkedin":
        keywords = _expand_keywords_for_linkedin(keywords)

    jobs: list[dict] = []
    for kw in keywords:
        try:
            kwargs = dict(
                site_name=[site],
                search_term=kw,
                location=location or "Germany",
                country_indeed="Germany",  # #500: NIE None — crasht
                results_wanted=max_results,
                hours_old=hours_old,
                verbose=0,
            )
            if site == "google":
                # Google-Jobs nutzt `google_search_term` zusaetzlich,
                # damit Google die Anfrage als Job-Suche erkennt.
                kwargs["google_search_term"] = (
                    google_search_term or f"{kw} jobs near {location or 'Germany'}"
                )
            df = scrape(**kwargs)
        except Exception as exc:  # jobspy wirft RateLimitException u.a.
            name = type(exc).__name__
            if "429" in str(exc) or "RateLimit" in name:
                logger.warning("JobSpy %s rate-limited (%s) bei '%s' — ueberspringe Site",
                               site, name, kw)
                break
            logger.warning("JobSpy %s Fehler bei '%s': %s", site, kw, exc)
            continue

        if df is None or getattr(df, "empty", True):
            continue
        for _, row in df.iterrows():
            jobs.append(_map_row(row, site))
    return jobs


def _extract_kw_region(params: dict) -> tuple[list[str], str]:
    """Helper: extrahiert keywords + erste Region aus PBP-params."""
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", [])
        regionen = kw_data.get("regionen", [])
    else:
        keywords = kw_data or []
        regionen = []
    location = regionen[0] if regionen else "Germany"
    return keywords, location


def search_jobspy_linkedin(params: dict) -> list[dict]:
    """LinkedIn via python-jobspy (#490)."""
    keywords, location = _extract_kw_region(params)
    jobs = _search_site("linkedin", keywords, location, max_results=25)
    logger.info("JobSpy/LinkedIn: %d Stellen gefunden", len(jobs))
    return jobs


def search_jobspy_indeed(params: dict) -> list[dict]:
    """Indeed.de via python-jobspy (#490)."""
    keywords, location = _extract_kw_region(params)
    jobs = _search_site("indeed", keywords, location, max_results=50)
    logger.info("JobSpy/Indeed: %d Stellen gefunden", len(jobs))
    return jobs


def search_jobspy_glassdoor(params: dict) -> list[dict]:
    """Glassdoor.de via python-jobspy (#500)."""
    keywords, location = _extract_kw_region(params)
    jobs = _search_site("glassdoor", keywords, location, max_results=30)
    logger.info("JobSpy/Glassdoor: %d Stellen gefunden", len(jobs))
    return jobs


def search_jobspy_google(params: dict) -> list[dict]:
    """Google Jobs via python-jobspy (#500).

    Massiver Aggregator — Google Jobs indexiert StepStone, Indeed,
    LinkedIn, Stellenanzeigen.de und Dutzende weitere Boards. Per
    JobSpy laeuft die Anfrage automatisiert (im Gegensatz zur
    Chrome-Extension-Variante in google_jobs.py / #501).
    """
    keywords, location = _extract_kw_region(params)
    jobs = _search_site("google", keywords, location, max_results=50)
    logger.info("JobSpy/Google: %d Stellen gefunden", len(jobs))
    return jobs
