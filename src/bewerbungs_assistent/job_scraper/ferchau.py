"""FERCHAU Scraper — Engineering & IT Personaldienstleister.

Grosser Footprint in Engineering-Dienstleistungen.
Kein Login erforderlich. HTML-Scraping mit JSON-LD Fallback.
"""

import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level
from .hydration import (jsonld_aus_hydration, liste_aus_hydration,
                        entweiche_trennzeichen)
from .textgrenzen import fuer_speicher

logger = logging.getLogger("bewerbungs_assistent.scraper.ferchau")

FALLBACK_QUERIES = [
    "Software Engineer", "Projektmanager", "Data Analyst",
    "DevOps Engineer", "Consultant",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9",
}


def _passt_zu_keywords(text: str, keywords: list) -> bool:
    """Clientseitiger Filter (#925).

    Der `search`-Parameter der Plattform wird serverseitig nicht mehr
    ausgewertet — drei verschiedene Suchbegriffe lieferten am 18.08.2026
    exakt dieselben 25 Stellen. Also einmal die neuesten Stellen holen
    und hier filtern, statt acht identische Abrufe zu machen.
    Ohne Suchbegriffe passiert alles (der Score filtert danach ohnehin).
    """
    if not keywords:
        return True
    low = (text or "").lower()
    return any(str(k).lower() in low for k in keywords if k)


def _aus_offers(html: str, keywords: list) -> list:
    """Stellen aus dem plattform-eigenen Offers-Array (#925).

    Reichhaltiger als der schema.org-Auszug: Detail-Slug (Anker-Pflicht
    #766), ECHTE Gehaltsspanne (kein Schaetzwert, vgl. #827/#918),
    Arbeitsort und Arbeitsmodell stehen nur hier.
    """
    treffer = []
    for o in liste_aus_hydration(html, "Offers"):
        if not isinstance(o, dict):
            continue
        title = entweiche_trennzeichen(o.get("title") or "").strip()
        if not title:
            continue
        ort = entweiche_trennzeichen(o.get("locationCity") or "")
        intro = entweiche_trennzeichen(o.get("intro") or "")
        beschreibung = re.sub(r"<[^>]+>", " ", intro)
        beschreibung = re.sub(r"\s+", " ", fuer_speicher(beschreibung).strip())
        if not _passt_zu_keywords(f"{title} {beschreibung}", keywords):
            continue

        slug = o.get("slug") or ""
        url = f"https://touch.ferchau.com{slug}" if slug.startswith("/") else slug

        stelle = {
            "hash": stelle_hash("ferchau.com", title),
            "title": title,
            "company": entweiche_trennzeichen(
                o.get("companyName") or "FERCHAU"),
            "location": ort,
            "url": url,
            "source": "ferchau",
            "description": beschreibung,
            "employment_type": "festanstellung",
            "remote_level": detect_remote_level(
                f"{title} {o.get('workplaceTypeName', '')} {beschreibung}"),
        }
        # Echte Gehaltsangaben der Plattform — NICHT geschaetzt (#827).
        smin = o.get("annualSalaryMinimum")
        smax = o.get("annualSalaryMaximum")
        if isinstance(smin, (int, float)) and smin > 0:
            stelle["salary_min"] = float(smin)
            stelle["salary_type"] = "jaehrlich"
            stelle["salary_estimated"] = False
            if isinstance(smax, (int, float)) and smax > 0:
                stelle["salary_max"] = float(smax)
        treffer.append(stelle)
    return treffer


def _aus_hydration(html: str, keywords: list) -> list:
    """Fallback: schema.org-JobPosting aus dem Payload (ohne Detail-URL)."""
    treffer = []
    for item in jsonld_aus_hydration(html, typ="JobPosting"):
        title = entweiche_trennzeichen(item.get("title") or "").strip()
        if not title:
            continue
        org = item.get("hiringOrganization") or {}
        company = org.get("name", "FERCHAU") if isinstance(org, dict) else "FERCHAU"
        loc = item.get("jobLocation") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        adr = (loc.get("address") or {}) if isinstance(loc, dict) else {}
        location = entweiche_trennzeichen(
            adr.get("addressLocality", "") if isinstance(adr, dict) else "")
        beschreibung = entweiche_trennzeichen(item.get("description") or fuer_speicher(""))
        if not _passt_zu_keywords(f"{title} {beschreibung}", keywords):
            continue
        treffer.append({
            "hash": stelle_hash("ferchau.com", title),
            "title": title,
            "company": entweiche_trennzeichen(company),
            "location": location,
            "url": item.get("url", ""),
            "source": "ferchau",
            "description": beschreibung,
            "employment_type": "festanstellung",
            "remote_level": detect_remote_level(
                f"{title} {location} {beschreibung}"),
        })
    return treffer


def search_ferchau(params: dict) -> list:
    """Search FERCHAU jobs via HTML scraping.

    v1.7.18 (#925): Die JobPosting-Daten stehen NICHT als ld+json im DOM
    (dort liegt nur ein Organization-Block), sondern escaped im
    SSR-Hydration-Payload. Der DOM-Pfad fand deshalb monatelang nichts,
    obwohl die Seite 25 Stellen pro Abruf ausliefert. Reihenfolge jetzt:
    Hydration-Payload -> ld+json im DOM -> HTML-Karten.
    """
    jobs = []
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", []) or []
    else:
        keywords = list(kw_data or [])
    queries = (keywords or FALLBACK_QUERIES)[:8]

    # #925: ein Abruf reicht — der search-Parameter wirkt nicht mehr.
    try:
        with httpx.Client(timeout=30, follow_redirects=True,
                          headers=HEADERS) as client:
            resp = client.get(
                "https://touch.ferchau.com/de/de",
                params={"type": 3, "sortingType": "actuality",
                        "sortingDirection": "DESC"},
            )
        if resp.status_code == 200:
            jobs = _aus_offers(resp.text, keywords)
            if jobs:
                logger.info("FERCHAU: %d Stellen aus dem Offers-Payload",
                            len(jobs))
                return jobs
            jobs = _aus_hydration(resp.text, keywords)
            if jobs:
                logger.info("FERCHAU: %d Stellen aus dem JSON-LD-Payload",
                            len(jobs))
                return jobs
    except Exception as exc:  # noqa: BLE001
        logger.debug("FERCHAU Hydration-Pfad fehlgeschlagen: %s", exc)

    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        for query in queries:
            try:
                # #653 (B12, beta.77): URL-Migration zu touch.ferchau.com
                # neue Karriere-Plattform. Alte /de/de/jobs ist seit
                # 2026-04-25 dauerhaft 404. Neue Plattform ist vermutlich
                # SPA, JSON-LD koennte aber im SSR-HTML stehen.
                resp = client.get(
                    "https://touch.ferchau.com/de/de",
                    params={
                        "search": query,
                        "type": 3,  # type=3 ist Festanstellung/Direktanstellung
                        "sortingType": "actuality",
                        "sortingDirection": "DESC",
                    },
                )
                if resp.status_code != 200:
                    logger.debug("FERCHAU HTTP %d for '%s'", resp.status_code, query)
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # JSON-LD (preferred)
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        import json
                        data = json.loads(script.string or "")
                        items = data if isinstance(data, list) else data.get("@graph", [data])
                        for item in items:
                            if item.get("@type") != "JobPosting":
                                continue
                            title = item.get("title", "")
                            if not title:
                                continue
                            org = item.get("hiringOrganization", {})
                            company = org.get("name", "FERCHAU") if isinstance(org, dict) else "FERCHAU"
                            loc = item.get("jobLocation", {})
                            if isinstance(loc, list):
                                loc = loc[0] if loc else {}
                            location = ""
                            if isinstance(loc, dict):
                                addr = loc.get("address", {})
                                location = addr.get("addressLocality", "") if isinstance(addr, dict) else ""

                            jobs.append({
                                "hash": stelle_hash("ferchau.com", title),
                                "title": title,
                                "company": company,
                                "location": location,
                                "url": item.get("url", ""),
                                "source": "ferchau",
                                "description": (item.get("description", "") or fuer_speicher("")),
                                "employment_type": "festanstellung",
                                "remote_level": detect_remote_level(
                                    f"{title} {location} {item.get('description', '')}"
                                ),
                            })
                    except Exception:
                        continue

                # Fallback: HTML card extraction
                if not any(j["source"] == "ferchau" for j in jobs):
                    cards = soup.select(
                        "article, .job-item, [class*='job-card'], "
                        "[class*='job-listing'], a[href*='/jobs/']"
                    )
                    seen = set()
                    for card in cards[:25]:
                        link_el = card.find("a", href=re.compile(r"/jobs/")) if card.name != "a" else card
                        if not link_el:
                            continue
                        title = link_el.get_text(strip=True)
                        if not title or len(title) < 5 or title in seen:
                            continue
                        seen.add(title)

                        href = link_el.get("href", "")
                        # #653: bei der neuen touch.ferchau.com-Plattform
                        # kommen relative Links wie /de/de/...; auch alte
                        # ferchau.com-Links bleiben fuer historische
                        # Backward-Compat funktional.
                        if href.startswith("http"):
                            url = href
                        elif href.startswith("/de/"):
                            url = f"https://touch.ferchau.com{href}"
                        else:
                            url = f"https://www.ferchau.com{href}"
                        if "/jobs?" in url:
                            continue  # search page link

                        comp_el = card.find(class_=re.compile(r"company|firma", re.I)) if card.name != "a" else None
                        loc_el = card.find(class_=re.compile(r"location|ort|standort", re.I)) if card.name != "a" else None

                        jobs.append({
                            "hash": stelle_hash("ferchau.com", title),
                            "title": title,
                            "company": comp_el.get_text(strip=True) if comp_el else "FERCHAU",
                            "location": loc_el.get_text(strip=True) if loc_el else "",
                            "url": url,
                            "source": "ferchau",
                            "description": "",
                            "employment_type": "festanstellung",
                            "remote_level": detect_remote_level(f"{title}"),
                        })

                logger.debug("FERCHAU: %d for '%s'", len(jobs), query)
                time.sleep(1.5)
            except Exception as e:
                logger.error("FERCHAU error for '%s': %s", query, e)

    logger.info("FERCHAU: %d Stellen gefunden", len(jobs))
    return jobs
