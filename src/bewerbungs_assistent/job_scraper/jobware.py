"""Jobware Scraper — Premium-Jobportal für Spezialisten und Führungskräfte.

Gute Abdeckung für Senior-Positionen und Fachkräfte.
Kein Login erforderlich. HTML-Scraping mit JSON-LD Fallback.

Fix #235: Mehrere URL-Varianten, erweiterte Selektoren, SPA-Erkennung.

v1.7.104 (#1041): die Karten liest `jobboerse_karten` (dieselbe Plattform
wie ingenieur.de). Bis v1.7.103 kam je Suchlauf 1-2 Stellen an: die
Auswahl traf die Bestandteile der Karten statt der Karten, der Titel kam
aus dem Knopf "Job ansehen", Firma und Ort aus Klassennamen, die es nicht
gibt, und der Kartenweg lief nur fuer den ersten Suchbegriff.
"""

import json
import logging
import time

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level
from .jobboerse_karten import karten_aus_html
from .textgrenzen import fuer_speicher

logger = logging.getLogger("bewerbungs_assistent.scraper.jobware")

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

BASIS_URL = "https://www.jobware.de"

# URL-Varianten: Jobware hat URLs in der Vergangenheit geaendert (#235, #500).
# 2026-04-25: /suche/ und /stellenangebote/ liefern HTTP 404; /jobs ist die
# aktuelle Such-URL.
_SEARCH_URLS = [
    "https://www.jobware.de/jobs",
    "https://www.jobware.de/suche/",
    "https://www.jobware.de/stellenangebote/",
    "https://www.jobware.de/jobs/",
]


def karten_hash(titel: str) -> str:
    """Die Kennung einer Karten-Stelle — aus DEMSELBEN Text wie bis v1.7.103.

    Der alte Kartenweg las den Titel aus dem Knopf "Job ansehen" und bekam
    `Job"<Titel>"ansehen`. Mit dem richtigen Titel als Eingabe haette jede
    bereits gespeicherte Stelle eine neue Kennung bekommen: der Neufund
    waere ueber die gleiche URL als Duplikat des kaputten Eintrags
    aussortiert worden, und der kaputte bliebe aktiv (Hinweis des Melders,
    #1041). Mit derselben Eingabe landet der Wiederfund auf seiner Zeile,
    und Titel, Firma und Ort werden dort korrigiert.
    """
    return stelle_hash("jobware.de", f'Job"{titel}"ansehen')


def _stelle(titel, firma, ort, url, beschreibung="", kennung=None) -> dict:
    return {
        "hash": kennung or stelle_hash("jobware.de", titel),
        "title": titel,
        # "Unbekannt" nur, wenn die Karte wirklich keinen Arbeitgeber nennt —
        # seit #1028 gilt der Platzhalter nicht als Firma.
        "company": firma or "Unbekannt",
        "location": ort,
        "url": url,
        "source": "jobware",
        "description": beschreibung or fuer_speicher(""),
        "employment_type": "festanstellung",
        "remote_level": detect_remote_level(f"{titel} {ort} {beschreibung}"),
    }


def _aus_json_ld(soup) -> list[dict]:
    stellen = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data])
        for item in items:
            if not isinstance(item, dict) or item.get("@type") != "JobPosting":
                continue
            title = item.get("title", "")
            if not title:
                continue
            org = item.get("hiringOrganization", {})
            company = org.get("name", "") if isinstance(org, dict) else ""
            loc = item.get("jobLocation", {})
            if isinstance(loc, list):
                loc = loc[0] if loc else {}
            location = ""
            if isinstance(loc, dict):
                addr = loc.get("address", {})
                location = addr.get("addressLocality", "") if isinstance(addr, dict) else ""
            stellen.append(_stelle(title, company, location, item.get("url", ""),
                                   item.get("description", "") or ""))
    return stellen


def _region(params: dict) -> str:
    """Die erste Region aus den Suchkriterien — oder leer (#1041 Punkt 4)."""
    regionen = (params.get("keywords") or {}).get("regionen") or []
    region = str(regionen[0]).strip() if regionen else ""
    return "" if region.lower() in ("", "deutschland", "germany") else region


def search_jobware(params: dict) -> list:
    """Search Jobware via HTML scraping."""
    jobs = []
    gesehen: set = set()
    kw_data = params.get("keywords", {})
    queries = kw_data.get("general", FALLBACK_QUERIES)[:8]

    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        # Find working URL on first query
        working_url = None
        # v1.7.128 (#1041 Punkt 4): erst die eigene Region, dann bundesweit.
        # Gemessen 25.09.2026: mit `l=<Stadt>` liegen 15 von 20 Treffern dort,
        # bundesweit 2 von 20, und beide Seiten teilen nur 1-2 Stellen. Die
        # bundesweite Abfrage bleibt, damit Remote- und Fernstellen nicht
        # verloren gehen (Recall vor Praezision, #910).
        region = _region(params)
        orte = ([region] if region else []) + ["Deutschland"]
        for query in queries:
            for ort in orte:
                try:
                    resp = None
                    if not working_url:
                        for url_candidate in _SEARCH_URLS:
                            try:
                                antwort = client.get(
                                    url_candidate,
                                    params={"q": query, "l": ort},
                                )
                                if antwort.status_code == 200 and len(antwort.text) > 5000:
                                    working_url = url_candidate
                                    resp = antwort
                                    break
                            except Exception:
                                continue
                        if not working_url:
                            logger.warning("Jobware: Keine funktionierende URL gefunden (#235)")
                            return jobs
                    else:
                        resp = client.get(
                            working_url,
                            params={"q": query, "l": ort},
                        )
                        if resp.status_code != 200:
                            logger.debug("Jobware HTTP %d for '%s'", resp.status_code, query)
                            continue

                    soup = BeautifulSoup(resp.text, "html.parser")

                    # SPA-Erkennung: Wenn Seite < 10KB und kein Job-Content, ist Scraping sinnlos (#235)
                    if len(resp.text) < 10000 and not soup.find("script", type="application/ld+json"):
                        logger.warning("Jobware: Seite hat nur %d Bytes — moeglicherweise SPA (#235)",
                                       len(resp.text))
                        continue

                    vorher = len(jobs)
                    for stelle in _aus_json_ld(soup):
                        schluessel = stelle["url"] or stelle["title"]
                        if schluessel in gesehen:
                            continue
                        gesehen.add(schluessel)
                        jobs.append(stelle)

                    # v1.7.104 (#1041): Karten fuer JEDEN Suchbegriff, nicht nur
                    # solange die Sammelliste leer ist.
                    for k in karten_aus_html(resp.text, BASIS_URL):
                        if k["url"] in gesehen:
                            continue
                        gesehen.add(k["url"])
                        jobs.append(_stelle(k["titel"], k["firma"], k["ort"], k["url"],
                                            kennung=karten_hash(k["titel"])))

                    logger.debug("Jobware: %d neu fuer '%s'", len(jobs) - vorher, query)
                    time.sleep(1.5)
                except Exception as e:
                    logger.error("Jobware error for '%s' (%s): %s", query, ort, e)

    logger.info("Jobware: %d Stellen gefunden", len(jobs))
    return jobs
