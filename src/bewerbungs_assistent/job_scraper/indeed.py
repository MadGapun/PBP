"""Indeed job scraper via HTML parsing.

Searches de.indeed.com for job listings using httpx + BeautifulSoup.
No login required. Rate limited to 2s between requests.
"""

import logging
import time
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level

logger = logging.getLogger("bewerbungs_assistent.scraper.indeed")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml",
}

FALLBACK_QUERIES = [
    "PLM Consultant",
    "Product Lifecycle Management",
    "PDM Manager",
]


def search_indeed(params: dict) -> list:
    """Search Indeed Germany for job listings.

    Args:
        params: Search parameters with optional 'keywords' dict
                containing 'indeed_queries' list.
    """
    jobs = []

    # Dynamic queries from DB, fallback to hardcoded
    kw_data = params.get("keywords", {})
    queries = kw_data.get("indeed_queries", FALLBACK_QUERIES)

    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for query in queries:
            try:
                url = f"https://de.indeed.com/jobs?q={quote(query)}&l=Deutschland"
                resp = client.get(url)
                if resp.status_code != 200:
                    logger.warning("Indeed %d for '%s'", resp.status_code, query)
                    continue

                soup = BeautifulSoup(resp.text, "lxml")

                # Indeed uses various card structures
                cards = (
                    soup.select("div.job_seen_beacon") or
                    soup.select("div.jobsearch-SerpJobCard") or
                    soup.select("div[data-jk]") or
                    soup.select("li div.cardOutline")
                )

                for card in cards:
                    # Title
                    title_el = (
                        card.select_one("h2.jobTitle a") or
                        card.select_one("a[data-jk]") or
                        card.select_one("h2 a") or
                        card.select_one(".jobTitle")
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title:
                        continue

                    # Link
                    link = ""
                    jk = card.get("data-jk") or (title_el.get("data-jk") if title_el else "")
                    if jk:
                        link = f"https://de.indeed.com/viewjob?jk={jk}"
                    elif title_el and title_el.get("href"):
                        href = title_el["href"]
                        if not href.startswith("http"):
                            href = "https://de.indeed.com" + href
                        link = href

                    # Company
                    company_el = (
                        card.select_one("[data-testid='company-name']") or
                        card.select_one(".companyName") or
                        card.select_one(".company")
                    )
                    company = company_el.get_text(strip=True) if company_el else "Unbekannt"

                    # Location
                    location_el = (
                        card.select_one("[data-testid='text-location']") or
                        card.select_one(".companyLocation") or
                        card.select_one(".location")
                    )
                    location = location_el.get_text(strip=True) if location_el else ""

                    # Description snippet
                    desc_el = (
                        card.select_one(".job-snippet") or
                        card.select_one("[class*='snippet']") or
                        card.select_one(".summary")
                    )
                    desc = desc_el.get_text(strip=True) if desc_el else ""

                    # Salary
                    salary_el = (
                        card.select_one("[data-testid='attribute_snippet_testid']") or
                        card.select_one(".salary-snippet-container") or
                        card.select_one(".estimated-salary")
                    )
                    salary = salary_el.get_text(strip=True) if salary_el else ""

                    job = {
                        "hash": stelle_hash("indeed.de", title),
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": link,
                        "source": "indeed",
                        "description": desc[:500],
                        "employment_type": "festanstellung",
                        "remote_level": detect_remote_level(f"{title} {location} {desc}"),
                        "salary_info": salary if salary else None,
                    }
                    jobs.append(job)

                time.sleep(2)  # Rate limiting
            except Exception as e:
                logger.error("Indeed error for '%s': %s", query, e)

    logger.info("Indeed: %d Stellen gefunden", len(jobs))
    return jobs
