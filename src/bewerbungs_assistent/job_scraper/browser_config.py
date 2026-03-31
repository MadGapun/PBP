"""Konfigurierbare DOM-Selektoren für Browser-basierte Job-Scraper.

LinkedIn und XING ändern regelmäßig ihre DOM-Struktur.
Alle Selektoren sind hier zentralisiert, damit Updates einfach sind.

Usage:
    from .browser_config import SELECTORS, get_selectors, update_selector
    sel = get_selectors("linkedin")
    cards = page.query_selector_all(sel["job_card"])
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger("bewerbungs_assistent.scraper.browser_config")

# Default DOM selectors — updated 2026-03-16
SELECTORS = {
    "linkedin": {
        # Job list page
        "job_card": ".job-card-container, .jobs-search-results__list-item, .scaffold-layout__list-item, [data-job-id]",
        "title_link": 'a[href*="/jobs/view/"]',
        "title_text": ".job-card-list__title, .job-card-container__link, a[class*='job-card'] span, strong",
        "company": ".job-card-container__company-name, .artdeco-entity-lockup__subtitle span, span[class*='company']",
        "location": ".job-card-container__metadata-item, .artdeco-entity-lockup__caption span, span[class*='location']",
        "date": "time, .job-card-container__listdate, span[class*='time']",
        "total_results": ".jobs-search-results-list__subtitle, .jobs-search-results-list__title-heading",
        # Job detail panel (right side or overlay)
        "description": ".jobs-description__content, .jobs-box__html-content, .jobs-description-content__text",
        "detail_tags": ".job-details-jobs-unified-top-card__job-insight span",
        # Navigation
        "next_button": 'button[aria-label*="Weiter"], button[aria-label*="Next"]',
        # Login detection
        "login_indicators": "input#username, input[name='session_key']",
        "login_url_patterns": ["login", "authwall", "checkpoint"],
    },
    "xing": {
        # Job list page
        "job_card": '[data-testid="search-result"], article[class*="job"], li[class*="job"], div[class*="jobResult"]',
        "title_link": 'a[href*="/jobs/"]',
        "company": '[data-testid*="company"], [class*="company" i], span[class*="employer"]',
        "location": '[data-testid*="location"], [class*="location" i], span[class*="city"]',
        "description": '[class*="description" i], [class*="snippet" i], [class*="teaser" i]',
        # Navigation
        "next_button": 'button[aria-label*="Weiter"], a[aria-label*="Weiter"], [data-testid="pagination-next"]',
        # Login detection
        "login_indicators": "input[type='email'], input[name='login_form']",
        "login_url_patterns": ["login", "auth", "signin", "anmelden"],
    },
}

# JS extraction scripts for complex DOM parsing
JS_EXTRACT_LINKEDIN = """() => {
    const results = [];
    const cardSelectors = %(job_card)s;
    const cards = document.querySelectorAll(cardSelectors);

    for (const card of cards) {
        try {
            // Title + Link
            const titleLink = card.querySelector(%(title_link)s);
            if (!titleLink) continue;
            const href = titleLink.getAttribute('href') || '';
            const titleEl = card.querySelector(%(title_text)s);
            const title = (titleEl?.textContent || titleLink.textContent || '').trim();
            if (!title || title.length < 3) continue;

            // Extract Job ID from URL
            const jobIdMatch = href.match(/\\/jobs\\/view\\/(\\d+)/);
            const jobId = jobIdMatch ? jobIdMatch[1] : '';

            // Company
            const companyEl = card.querySelector(%(company)s);
            const company = companyEl?.textContent?.trim() || '';

            // Location
            const locationEl = card.querySelector(%(location)s);
            const location = locationEl?.textContent?.trim() || '';

            // Date
            const dateEl = card.querySelector(%(date)s);
            const dateRaw = dateEl ? (dateEl.getAttribute('datetime') || dateEl.textContent?.trim() || '') : '';

            let fullLink = href.split('?')[0];
            if (fullLink && !fullLink.startsWith('http')) {
                fullLink = 'https://www.linkedin.com' + fullLink;
            }

            // Skip company page links
            if (fullLink.includes('/company/') && !fullLink.includes('/jobs/view/')) continue;

            results.push({title, company, location, link: fullLink, jobId, dateRaw});
        } catch(e) { continue; }
    }
    return results;
}"""

JS_EXTRACT_XING = """() => {
    const results = [];
    const allLinks = document.querySelectorAll(%(title_link)s);
    const seen = new Set();

    for (const link of allLinks) {
        try {
            const href = link.getAttribute('href') || '';
            // Only job detail links
            if (!href.match(/\\/jobs\\/[a-z0-9-]+\\./i) &&
                !href.match(/\\/jobs\\/\\d+/)) continue;
            const title = link.textContent?.trim() || '';
            if (!title || title.length < 5 || seen.has(title)) continue;
            seen.add(title);

            // Walk up to find card container
            let card = link.closest('article, [data-testid], li, div[class*="card"]');
            if (!card) card = link.parentElement?.parentElement || link.parentElement;

            const companyEl = card?.querySelector(%(company)s);
            const locationEl = card?.querySelector(%(location)s);
            const descEl = card?.querySelector(%(description)s);

            let fullLink = href;
            if (fullLink && !fullLink.startsWith('http')) {
                fullLink = 'https://www.xing.com' + fullLink;
            }

            // Extract XING Job-ID from URL
            const idMatch = href.match(/\\/(\\d+)(?:\\?|$|\\.|\\/)/) ||
                           href.match(/jobs\\/([a-z0-9-]+)\\./) ||
                           href.match(/jobs\\/([^?\\/]+)/);
            const jobId = idMatch ? idMatch[1] : '';

            results.push({
                title,
                link: fullLink,
                jobId,
                company: companyEl?.textContent?.trim() || '',
                location: locationEl?.textContent?.trim() || '',
                desc: (descEl?.textContent?.trim() || '').substring(0, 500),
            });
        } catch(e) { continue; }
    }
    return results;
}"""

JS_EXTRACT_DESCRIPTION = """() => {
    const selectors = %(description)s;
    const el = document.querySelector(selectors);
    return el ? el.innerText.substring(0, 5000) : '';
}"""


def get_selectors(source: str) -> dict:
    """Get DOM selectors for a source, with DB override support.

    First checks for user-customized selectors in the data directory,
    then falls back to built-in defaults.
    """
    # Try loading custom overrides from config file
    try:
        from ..database import get_data_dir
        config_file = get_data_dir() / "browser_selectors.json"
        if config_file.exists():
            custom = json.loads(config_file.read_text())
            if source in custom:
                # Merge: custom overrides defaults
                merged = dict(SELECTORS.get(source, {}))
                merged.update(custom[source])
                return merged
    except Exception as e:
        logger.debug("Config-Datei nicht geladen: %s", e)

    return dict(SELECTORS.get(source, {}))


def update_selector(source: str, key: str, value: str) -> None:
    """Update a single selector for a source (persisted to config file).

    Args:
        source: 'linkedin' or 'xing'
        key: Selector key (e.g. 'job_card', 'title_link')
        value: New CSS selector string
    """
    from ..database import get_data_dir
    config_file = get_data_dir() / "browser_selectors.json"

    custom = {}
    if config_file.exists():
        custom = json.loads(config_file.read_text())

    if source not in custom:
        custom[source] = {}
    custom[source][key] = value

    config_file.write_text(json.dumps(custom, indent=2, ensure_ascii=False))
    logger.info("Selektor aktualisiert: %s.%s = %s", source, key, value)


def build_js_extractor(source: str) -> str:
    """Build a JavaScript extraction function with current selectors.

    Returns ready-to-execute JS string for page.evaluate().
    """
    sel = get_selectors(source)

    def _quote(s):
        return json.dumps(s)

    if source == "linkedin":
        return JS_EXTRACT_LINKEDIN % {
            "job_card": _quote(sel.get("job_card", "")),
            "title_link": _quote(sel.get("title_link", "")),
            "title_text": _quote(sel.get("title_text", "")),
            "company": _quote(sel.get("company", "")),
            "location": _quote(sel.get("location", "")),
            "date": _quote(sel.get("date", "")),
        }
    elif source == "xing":
        return JS_EXTRACT_XING % {
            "title_link": _quote(sel.get("title_link", "")),
            "company": _quote(sel.get("company", "")),
            "location": _quote(sel.get("location", "")),
            "description": _quote(sel.get("description", "")),
        }
    return ""


def build_js_description(source: str) -> str:
    """Build JS to extract job description from detail view."""
    sel = get_selectors(source)
    return JS_EXTRACT_DESCRIPTION % {
        "description": json.dumps(sel.get("description", "")),
    }


def build_keyword_combinations(keywords_muss: list[str]) -> list[str]:
    """Build smart keyword combinations for LinkedIn/XING search.

    Takes keywords_muss and creates targeted search combinations
    instead of searching each keyword individually.

    Strategy:
    - Pairs core keywords for specificity
    - Groups related keywords (Engineering tools, Enterprise tools, etc.)
    - Uses Boolean OR for niche keywords
    - Limits to max 6 queries to avoid rate-limiting

    Args:
        keywords_muss: List of must-have keywords from search criteria

    Returns:
        List of search query strings (max 6)
    """
    if not keywords_muss:
        return []

    # Categorize keywords for smart pairing
    core_kw = []      # High-level terms: broad domain keywords
    tech_kw = []      # Specific tech stacks and tools
    role_kw = []      # Role terms: Consultant, Architekt, Manager, etc.
    niche_kw = []     # Niche/specialized terms

    CORE_TERMS = {"plm", "pdm", "sap", "cad", "erp", "mes", "alm", "bom"}
    ROLE_TERMS = {
        "consultant", "berater", "architekt", "architect", "manager",
        "projektleiter", "projektmanager", "entwickler", "developer",
        "lead", "engineer", "ingenieur", "administrator", "admin",
        "koordinator", "spezialist", "experte", "programm",
    }

    for kw in keywords_muss:
        kw_lower = kw.lower().strip()
        if kw_lower in CORE_TERMS:
            core_kw.append(kw)
        elif kw_lower in ROLE_TERMS:
            role_kw.append(kw)
        elif len(kw) <= 4 or kw_lower in CORE_TERMS:
            core_kw.append(kw)
        elif any(t in kw_lower for t in ["teamcenter", "windchill", "enovia", "aras", "pro.file", "procad"]):
            tech_kw.append(kw)
        else:
            # Check if it looks like a product/tech name (capitalized, short)
            if kw[0].isupper() and len(kw.split()) <= 2:
                tech_kw.append(kw)
            else:
                niche_kw.append(kw)

    queries = []

    # Strategy 1: Core + Tech combinations (most specific)
    for core in core_kw[:3]:
        for tech in tech_kw[:2]:
            q = f'"{core}" "{tech}"'
            if q not in queries:
                queries.append(q)

    # Strategy 2: Core + Role combinations
    for core in core_kw[:2]:
        for role in role_kw[:2]:
            q = f'"{core}" "{role}"'
            if q not in queries:
                queries.append(q)

    # Strategy 3: Core + Core pairs (broader)
    if len(core_kw) >= 2:
        for i in range(min(len(core_kw) - 1, 2)):
            q = f'"{core_kw[i]}" "{core_kw[i+1]}"'
            if q not in queries:
                queries.append(q)

    # Strategy 4: Niche keywords paired with core (#253: kein OR, zu unspezifisch)
    if niche_kw and core_kw:
        for niche in niche_kw[:2]:
            q = f'"{core_kw[0]}" "{niche}"'
            if q not in queries:
                queries.append(q)
    elif niche_kw:
        for niche in niche_kw[:2]:
            if f'"{niche}"' not in queries:
                queries.append(f'"{niche}"')

    # Strategy 5: Tech keywords paired (AND statt OR, #253)
    if len(tech_kw) >= 2:
        q = f'"{tech_kw[0]}" "{tech_kw[1]}"'
        if q not in queries:
            queries.append(q)

    # Fallback: if few combinations, add individual core keywords
    if len(queries) < 2:
        for kw in keywords_muss[:4]:
            if kw not in queries:
                queries.append(kw)

    # Limit to 6 queries
    return queries[:6]
