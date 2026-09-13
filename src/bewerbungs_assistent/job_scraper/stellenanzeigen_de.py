"""Stellenanzeigen.de Scraper — Grosses deutsches Jobportal.

3.2 Mio. Besucher/Monat, breites Stellenangebot.
Kein Login erforderlich. HTML-Scraping mit JSON-LD Fallback.

v1.7.101 (#1040): die Ergebnisseite traegt kein `JobPosting`-JSON-LD mehr
und nutzt generierte Klassennamen. Der Kartenweg liest Firma und Ort jetzt
aus der REIHENFOLGE des Kartentexts statt aus Klassennamen, und er laeuft
fuer JEDEN Suchbegriff — bis v1.7.100 nur fuer den ersten.
"""

import json
import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from . import stelle_hash, detect_remote_level
from .textgrenzen import fuer_speicher

logger = logging.getLogger("bewerbungs_assistent.scraper.stellenanzeigen_de")

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

BASIS_URL = "https://www.stellenanzeigen.de"

#: Angaben, die in der Karte nach dem Arbeitgeber stehen koennen, aber kein
#: Ort sind. Fehlt der Ort, steht an seiner Stelle eine davon — und die
#: gehoert nicht ins Ortsfeld, sonst geocodet PBP "Vollzeit".
_KEIN_ORT = frozenset({
    "vollzeit", "teilzeit", "minijob", "homeoffice", "home office", "remote",
    "ausbildung", "praktikum", "werkstudent", "befristet", "unbefristet",
    "festanstellung", "zeitarbeit", "freie mitarbeit",
})
_DATUM = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{4}$")


def _keine_angabe(text: str) -> bool:
    wert = (text or "").strip()
    return not wert or wert.lower() in _KEIN_ORT or bool(_DATUM.match(wert))


def _karte(anker, href: str):
    """Der groesste Vorfahr des Titel-Ankers, der keine FREMDE Anzeige
    enthaelt — also die Karte dieser Stelle, und nur dieser.

    Gemessen am 13.09.2026: so steht in 25 von 25 Karten Firma und Ort
    direkt hinter dem Titel. Die erste Fassung nahm den naechsten Vorfahr
    mit etwas Text und schnitt in 11 von 25 Karten den Ort ab.
    """
    karte = anker
    while karte.parent is not None:
        fremd = [x for x in karte.parent.select('a[href^="/job/"]')
                 if (x.get("href") or "").strip() != href]
        if fremd:
            break
        karte = karte.parent
    return karte


def karten_aus_html(html: str) -> list[dict]:
    """Alle Anzeigen einer Ergebnisseite ueber ihre `/job/`-Links.

    Firma und Ort kommen aus der Reihenfolge des Kartentexts: Titel,
    Arbeitgeber, Ort, dann Arbeitszeit, Zusatzleistungen und Datum. Vor dem
    Titel koennen Hinweise stehen ("Schnellbewerbung", "Top Job") — gesucht
    wird deshalb die Position des Titels, nicht die erste Zeile.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    gesehen: set = set()
    karten: list[dict] = []
    for anker in soup.select('a[href^="/job/"]'):
        href = (anker.get("href") or "").strip()
        titel = anker.get_text(strip=True)
        # Es gibt Wrapper-Links ohne Text; den nehmen wir nicht.
        if not href or href in gesehen or not titel or len(titel) < 8:
            continue
        gesehen.add(href)
        teile = list(_karte(anker, href).stripped_strings)
        rest = teile[teile.index(titel) + 1:] if titel in teile else []
        firma = rest[0] if rest and not _keine_angabe(rest[0]) else ""
        ort = rest[1] if firma and len(rest) > 1 and not _keine_angabe(rest[1]) else ""
        karten.append({
            "titel": titel,
            "firma": firma,
            "ort": ort,
            "url": href if href.startswith("http") else f"{BASIS_URL}{href}",
        })
    return karten


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
            stellen.append({
                "titel": title, "firma": company, "ort": location,
                "url": item.get("url", ""),
                "beschreibung": item.get("description", "") or "",
            })
    return stellen


def _stelle(titel: str, firma: str, ort: str, url: str, beschreibung: str = "") -> dict:
    return {
        "hash": stelle_hash("stellenanzeigen.de", titel),
        "title": titel,
        # "Unbekannt" nur, wenn die Karte wirklich keinen Arbeitgeber
        # nennt — seit #1028 gilt der Platzhalter nicht als Firma.
        "company": firma or "Unbekannt",
        "location": ort,
        "url": url,
        "source": "stellenanzeigen_de",
        "description": beschreibung or fuer_speicher(""),
        "employment_type": "festanstellung",
        "remote_level": detect_remote_level(f"{titel} {ort} {beschreibung}"),
    }


def search_stellenanzeigen_de(params: dict) -> list:
    """Search Stellenanzeigen.de via HTML scraping."""
    jobs = []
    gesehen_urls: set = set()
    kw_data = params.get("keywords", {})
    queries = kw_data.get("general", FALLBACK_QUERIES)[:8]

    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        for query in queries:
            try:
                # Die Region wird bewusst nicht uebergeben: gemessen am
                # 13.09.2026 bringt `wo=Hamburg` statt `Deutschland` 3 statt
                # 2 Hamburger Stellen — der Parameter wirkt praktisch nicht
                # (#1040). Die Entfernung regelt der Score.
                resp = client.get(
                    f"{BASIS_URL}/stellenangebote/",
                    params={"q": query, "wo": "Deutschland"},
                )
                if resp.status_code != 200:
                    logger.debug("Stellenanzeigen.de HTTP %d for '%s'", resp.status_code, query)
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                vorher = len(jobs)

                # JSON-LD structured data (preferred, falls die Seite es wieder traegt)
                for s in _aus_json_ld(soup):
                    schluessel = s["url"] or s["titel"]
                    if schluessel in gesehen_urls:
                        continue
                    gesehen_urls.add(schluessel)
                    jobs.append(_stelle(s["titel"], s["firma"], s["ort"], s["url"],
                                        s["beschreibung"]))

                # Kartenweg (#500, #1040): fuer JEDEN Suchbegriff. Bis
                # v1.7.100 lief er nur, solange die Sammelliste leer war —
                # also nur beim ersten Begriff; die uebrigen Seiten wurden
                # abgerufen und verworfen.
                for k in karten_aus_html(resp.text):
                    if k["url"] in gesehen_urls:
                        continue
                    gesehen_urls.add(k["url"])
                    jobs.append(_stelle(k["titel"], k["firma"], k["ort"], k["url"]))

                logger.debug("Stellenanzeigen.de: %d neu fuer '%s'", len(jobs) - vorher, query)
                time.sleep(1.5)
            except Exception as e:
                logger.error("Stellenanzeigen.de error for '%s': %s", query, e)

    logger.info("Stellenanzeigen.de: %d Stellen gefunden", len(jobs))
    return jobs
