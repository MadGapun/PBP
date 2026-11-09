"""Freelancermap: Projektsuche ueber die eingebettete Ergebnisliste der Suchseite.

#1302 (gemessen 08.11.2026, wenige Abrufe gegen die echte Seite):

* `/projekte?query=<Begriff>` antwortet in 0,2 bis 0,6 s mit HTTP 200, ohne Sperre oder Captcha-Seite
  (das Wort "captcha" steht nur in den Formular-Texten). robots.txt erlaubt `User-agent: *` alles;
  die AGB verbieten keinen automatischen Abruf, verlangen aber, die Dienste nicht zu stoeren -
  deshalb eine Seite je Begriff, eine Pause dazwischen, keine Detailabrufe.
* Die Seite traegt ihre Ergebnisliste vollstaendig als JSON
  (`<script type="application/json" data-component-name="ProjectSearch">`,
  `initialState.result.projects`, rund 20 Projekte je Begriff, neueste zuerst): Titel, Beschreibung,
  Firma, Orte, Remote-Anteil, Datum, Adresse. Detailseiten braucht es nicht.
* Die URSACHE des 90-s-Abbruchs: das alte Einbettungsformat (`projectsObject`) gibt es nicht mehr. Der
  Scraper fiel deshalb fuer JEDEN Begriff auf "Anker sammeln + jede Detailseite abrufen" (bis zu 75 je
  Begriff, 0,3 s Pause je Abruf) - bei 22 Ankern je Seite rund 10 s je Begriff, bei zehn und mehr
  Begriffen weit ueber der Zeitgrenze. Der Lauf brach ab und verwarf alles bis dahin Gefundene.
* Die Schlagwort-Seiten (`/projekte/<slug>`) sind enger als die Suche: `/projekte/sap-mdm` lieferte 2
  Projekte, `?query=SAP MDM` 16 - das gesuchte Projekt stand nur in der Suche. Der Hinweis vom
  18.08.2026 ("der Query-Parameter wird ignoriert") gilt nicht mehr.
* Offizielle Schnittstelle: keine oeffentliche API (`/api` antwortet 403), der im Seitenkopf verlinkte
  RSS-Feed (`/feeds/projekte/int-international.xml`) antwortet 404.

Personendaten des Projektanbieters (Vor- und Nachname im JSON) werden nie uebernommen, nur die Firma.
"""

import json
import logging
import re
import time
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level
from .textgrenzen import fuer_speicher


def _extract_publish_date(project: dict) -> str | None:
    """Extract publication date from freelancermap project data.

    Tries multiple field names that freelancermap may use.
    Returns ISO date string or None.
    """
    for key in ("publishedAt", "published_at", "createdAt", "created_at",
                "created", "startDate", "start_date", "start"):
        val = project.get(key)
        if val and isinstance(val, str) and len(val) >= 10:
            return val[:10]  # YYYY-MM-DD
    return None

logger = logging.getLogger("bewerbungs_assistent.scraper.freelancermap")

_BASIS = "https://www.freelancermap.de"
#: Die Suchadresse (#1302) - EINE Fassung fuer Suchlauf, Health-Check und Browser-Handoff.
SUCH_URL = _BASIS + "/projekte?query={begriff}"


def such_url(begriff: str) -> str:
    """Die Suchadresse fuer einen Begriff."""
    return SUCH_URL.format(begriff=quote_plus((begriff or "").strip()))


# v1.7.19 (#926): Fallback, wenn keine Suchkriterien gesetzt sind (build_search_keywords baut sonst
# `freelancermap_urls`). Absolute Adressen, keine Fragmente.
SEARCH_URLS = [such_url(b) for b in ("Software Engineer", "Projektmanagement", "Konstruktion", "Consultant")]

#: #1302: so lange darf ein Lauf hoechstens dauern. Liegt unter der Zeitgrenze des Suchlaufs (120 s),
#: damit der Lauf mit dem endet, was er hat, statt abgebrochen und verworfen zu werden.
ZEITBUDGET_S = 75.0
#: Pause zwischen zwei Suchseiten (Schonung der Seite, AGB).
PAUSE_S = 0.8
#: Nur fuer den Notweg ohne eingebettete Liste: so viele Detailseiten je Begriff hoechstens.
DETAIL_FETCH_LIMIT = 5
#: Nach so vielen gesperrten Antworten (403/429) in Folge hoert der Lauf auf, statt weiter anzuklopfen.
SPERREN_BIS_ABBRUCH = 2

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9",
}


def projekte_aus_suchseite(html: str) -> list | None:
    """Die eingebettete Ergebnisliste einer Suchseite.

    Rueckgabe: Liste der Projekte (auch leer, wenn die Suche nichts fand) - oder None, wenn die Seite den
    Datenblock nicht traegt (Aufbau geaendert, Sperrseite). Den Unterschied braucht der Health-Check:
    "nichts gefunden" ist keine Stoerung, "kein Datenblock" schon.
    """
    if not html or "ProjectSearch" not in html:
        return None
    soup = BeautifulSoup(html, "lxml")
    for script in soup.find_all("script", attrs={"type": "application/json"}):
        if script.get("data-component-name") != "ProjectSearch":
            continue
        try:
            daten = json.loads(script.get_text() or "")
        except (json.JSONDecodeError, TypeError):
            return None
        ergebnis = ((daten.get("initialState") or {}).get("result") or {})
        projekte = ergebnis.get("projects")
        if projekte is None:
            projekte = daten.get("initialResults")
        return list(projekte) if isinstance(projekte, list) else None
    return None


def _remote_stufe(projekt: dict, text: str) -> str:
    """Der Remote-Anteil, den das Portal selbst nennt - sonst aus dem Text."""
    anteil = (projekt.get("projectContractType") or {}).get("remoteInPercent")
    if isinstance(anteil, (int, float)):
        if anteil >= 100:
            return "remote"
        if anteil > 0:
            return "hybrid"
    return detect_remote_level(text)


def job_aus_projekt(projekt: dict, quelle_url: str = "") -> dict | None:
    """Ein Projekt der eingebetteten Liste als Stelle - ohne Namen von Personen."""
    titel = str(projekt.get("title") or "").strip()
    if not titel:
        return None
    from .html_text import gegliederter_text
    beschreibung = gegliederter_text(projekt.get("description") or "")
    firma = str(projekt.get("company") or (projekt.get("poster") or {}).get("company") or "").strip()
    orte = projekt.get("locations") or []
    ort = str((orte[0] or {}).get("name") or "") if orte else ""
    ort = ort or str(projekt.get("city") or "")
    pfad = (projekt.get("links") or {}).get("project") or ""
    slug = projekt.get("slug") or ""
    if pfad:
        url = pfad if pfad.startswith("http") else _BASIS + pfad
    elif slug:
        url = f"{_BASIS}/projekt/{slug}"
    else:
        url = quelle_url
    job = {
        "hash": stelle_hash("freelancermap.de", titel),
        "title": titel,
        "company": firma or "Freelancermap",
        "location": ort,
        "url": url,
        "is_search_url": not (pfad or slug),
        "source": "freelancermap",
        "description": fuer_speicher(beschreibung),
        "employment_type": "freelance",
        "remote_level": _remote_stufe(projekt, f"{titel} {ort} {beschreibung}"),
    }
    datum = _extract_publish_date(projekt)
    if datum:
        job["veroeffentlicht_am"] = datum
    return job


def _jobs_aus_ankern(client, html: str, seen_urls: set, deadline: float) -> list:
    """Notweg ohne eingebettete Liste: Projekt-Anker, wenige Detailseiten, nie ueber das Zeitbudget."""
    jobs = []
    soup = BeautifulSoup(html, "lxml")
    fetched = 0
    for a in soup.select('a[href*="/projekt/"]'):
        href = a.get("href", "").strip()
        title = a.get_text(strip=True)
        if not href or not title or len(title) < 8:
            continue
        full_url = href if href.startswith("http") else f"{_BASIS}{href}"
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        description = ""
        if fetched < DETAIL_FETCH_LIMIT and time.monotonic() < deadline:
            fetched += 1
            try:
                d_resp = client.get(full_url, timeout=10.0)
                if d_resp.status_code == 200:
                    d_soup = BeautifulSoup(d_resp.text, "lxml")
                    for sel in ("[class*='project-description']", "[class*='description']", "main", "article"):
                        el = d_soup.select_one(sel)
                        if el:
                            # #1047: mit Absaetzen und Listen.
                            from .html_text import gegliederter_text
                            txt = gegliederter_text(str(el))
                            if len(txt) > 100:
                                description = fuer_speicher(txt)
                                break
                time.sleep(0.3)
            except Exception:
                pass
        jobs.append({
            "hash": stelle_hash("freelancermap.de", title),
            "title": title,
            "company": "Freelancermap",
            "location": "",
            "url": full_url,
            "source": "freelancermap",
            "description": description,
            "employment_type": "freelance",
            "remote_level": detect_remote_level(f"{title} {description[:200]}"),
        })
    return jobs


def search_freelancermap(params: dict) -> list:
    """Sucht Projekte - eine Suchseite je Begriff, die Liste aus dem eingebetteten JSON (#1302).

    `params["_fortschritt"]` (optional, ein dict) haelt fest, wie weit der Lauf kam: Begriffe, fertig,
    langsamste Antwort, gesperrte Antworten, Seiten ohne Datenblock, Abbruch und Grund. Der Suchlauf
    liest daraus den Grund, den die Quellen-Diagnose nennt (`scraper_classifier.lauf_grund`).
    """
    jobs: list = []
    seen_urls: set[str] = set()
    fortschritt = params.get("_fortschritt")
    if not isinstance(fortschritt, dict):
        fortschritt = {}

    kw_data = params.get("keywords", {}) or {}
    urls = list(kw_data.get("freelancermap_urls") or SEARCH_URLS)
    budget = float(params.get("_zeitbudget_s") or ZEITBUDGET_S)
    start = time.monotonic()
    deadline = start + budget
    fortschritt.update({"begriffe": len(urls), "fertig": 0, "langsamste_s": 0.0, "gesperrt": 0,
                        "ohne_daten": 0, "fehler": 0, "abgebrochen": False, "grund": ""})
    gesperrt_in_folge = 0
    mit_daten = 0

    with httpx.Client(timeout=20, follow_redirects=True, headers=_HEADERS) as client:
        for nummer, url in enumerate(urls):
            if time.monotonic() >= deadline:
                fortschritt["abgebrochen"] = True
                fortschritt["grund"] = "zeitbudget"
                logger.info("Freelancermap: Zeitbudget %ss erreicht nach %d von %d Begriffen",
                            int(budget), nummer, len(urls))
                break
            try:
                t0 = time.monotonic()
                resp = client.get(url)
                dauer = round(time.monotonic() - t0, 2)
                fortschritt["langsamste_s"] = max(fortschritt["langsamste_s"], dauer)
                fortschritt["letzter_http"] = resp.status_code
                if resp.status_code in (403, 429):
                    fortschritt["gesperrt"] += 1
                    gesperrt_in_folge += 1
                    if gesperrt_in_folge >= SPERREN_BIS_ABBRUCH:
                        fortschritt["abgebrochen"] = True
                        fortschritt["grund"] = "gesperrt"
                        logger.warning("Freelancermap: %d gesperrte Antworten in Folge (HTTP %s) - Lauf beendet",
                                       gesperrt_in_folge, resp.status_code)
                        break
                    continue
                gesperrt_in_folge = 0
                if resp.status_code != 200:
                    fortschritt["fehler"] += 1
                    continue

                projekte = projekte_aus_suchseite(resp.text)
                if projekte is not None:
                    mit_daten += 1
                    for p in projekte:
                        job = job_aus_projekt(p, url)
                        if not job or job["url"] in seen_urls:
                            continue
                        seen_urls.add(job["url"])
                        jobs.append(job)
                else:
                    # Altformat (bis 2026): `projectsObject` im Seitenquelltext.
                    alt = _extract_projects_from_js(resp.text)
                    if alt:
                        mit_daten += 1
                        for p in alt:
                            job = job_aus_projekt(p, url)
                            if not job or job["url"] in seen_urls:
                                continue
                            seen_urls.add(job["url"])
                            jobs.append(job)
                    else:
                        fortschritt["ohne_daten"] += 1
                        jobs.extend(_jobs_aus_ankern(client, resp.text, seen_urls, deadline))
                fortschritt["fertig"] += 1
                if nummer < len(urls) - 1:
                    time.sleep(PAUSE_S)
            except Exception as e:
                fortschritt["fehler"] += 1
                logger.error("Freelancermap error: %s", e)

    # Playwright nur, wenn KEINE Seite die Liste trug und nichts gesperrt war - und nur mit dem Rest des Budgets.
    # Vorher startete der Browser auch dann, wenn die Suche schlicht nichts fand, und lief 30 s je Begriff.
    if not jobs and not mit_daten and not fortschritt["gesperrt"] and fortschritt["fertig"]:
        rest = deadline - time.monotonic()
        if rest > 20:
            logger.info("Freelancermap: keine Ergebnisliste auf der Seite, versuche Playwright-Fallback...")
            jobs = _playwright_fallback(urls[:2], deadline=deadline)

    fortschritt["dauer_s"] = round(time.monotonic() - start, 1)
    logger.info("Freelancermap: %d Projekte gefunden (%d von %d Begriffen, %.1fs)",
                len(jobs), fortschritt["fertig"], len(urls), fortschritt["dauer_s"])
    return jobs


def _playwright_fallback(urls: list, deadline: float | None = None) -> list:
    """Fallback: Use Playwright to render JS and extract projects."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.debug("Playwright nicht verfügbar für Freelancermap-Fallback")
        return []

    jobs = []
    import random
    import time as _time

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        for url in urls:
            if deadline is not None and _time.monotonic() >= deadline:
                break
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                _time.sleep(random.uniform(2, 3))

                html = page.content()
                projects = projekte_aus_suchseite(html) or _extract_projects_from_js(html)
                if projects:
                    for p in projects:
                        job = job_aus_projekt(p, url)
                        if job:
                            jobs.append(job)
                    continue

                # If JS extraction still fails, try DOM extraction
                raw_jobs = page.evaluate("""() => {
                    const results = [];
                    const cards = document.querySelectorAll('.project-card, .list-item-content, article');
                    for (const card of cards) {
                        const titleEl = card.querySelector('h3 a, h2 a, a[class*="title"]');
                        if (!titleEl) continue;
                        const title = titleEl.textContent?.trim() || '';
                        if (!title) continue;
                        let link = titleEl.getAttribute('href') || '';
                        if (link && !link.startsWith('http')) link = 'https://www.freelancermap.de' + link;
                        const locEl = card.querySelector('[class*="location"], .fa-map-marker-alt');
                        const descEl = card.querySelector('[class*="description"], p');
                        results.push({
                            title,
                            link,
                            location: locEl?.parentElement?.textContent?.trim() || locEl?.textContent?.trim() || '',
                            desc: (descEl?.textContent?.trim() || '').substring(0, 200000),
                        });
                    }
                    return results;
                }""")
                for raw in raw_jobs:
                    jobs.append({
                        "hash": stelle_hash("freelancermap.de", raw["title"]),
                        "title": raw["title"],
                        "company": "Freelancermap",
                        "location": raw["location"],
                        "url": raw["link"],
                        "source": "freelancermap",
                        "description": raw["desc"],
                        "employment_type": "freelance",
                        "remote_level": detect_remote_level(f"{raw['title']} {raw['location']} {raw['desc']}"),
                    })

            except Exception as e:
                logger.error("Freelancermap Playwright fallback error: %s", e)
        browser.close()

    return jobs


def _extract_projects_from_js(html: str) -> list:
    """Extract projectsObject from embedded PHP-inline JavaScript (Altformat bis 2026)."""
    match = re.search(r'projectsObject\s*=\s*(\[)', html)
    if not match:
        return []

    start = match.start(1)
    depth = 0
    i = start
    while i < len(html):
        if html[i] == '[':
            depth += 1
        elif html[i] == ']':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start:i+1])
                except json.JSONDecodeError:
                    return []
        i += 1
    return []
