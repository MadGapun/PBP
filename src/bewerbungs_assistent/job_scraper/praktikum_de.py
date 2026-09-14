"""Praktikum.de — Praktika und Werkstudentenstellen.

v1.7.107 (B53, gemessen 14.09.2026): der RSS-Feed ist entfernt (404). Die
Suche laeuft ueber ein Formular, und das Ergebnis liegt in der Sitzung::

    POST /detailsuche/ergebnisse,seite-1.html   stichwort=... schnellsuche=1
    GET  /detailsuche/ergebnisse,seite-2.html   (im selben Client)

Ein GET ohne vorheriges Formular liefert eine Seite ohne Treffer — genau
daran war die erste Messung gescheitert, bis derselbe Client zuerst das
Formular abgeschickt hatte.

Gefragt wird die ganze Boerse, nicht je Suchbegriff. Gemessen: sie traegt
24 Angebote auf drei Seiten. Das Stichwort filtert nur innerhalb dieser
Menge ("IT" lieferte alle 24, "Informatik" keines), ein Lauf je Begriff
fragte also dieselben Seiten mehrfach ab — und die Seite antwortete nach
etwa fuenfzehn Anfragen mit HTTP 429. Ueber die Passung entscheidet der
zentrale Filter, wie bei jedem Adapter ohne eigenen Filter (#995).

Die Karte traegt Titel, Branche, Ort, Beginn und einen Anrisstext; eine
Firma nennt sie nicht (das Gebaeude-Symbol steht fuer die Branche). Die
Detailseite traegt Firma, Adresse, Anzeigentext und Datum als
schema.org-Microdata (JobPosting) — gelesen fuer die ersten `MAX_DETAILS`.
"""

from __future__ import annotations

import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from . import detect_remote_level, make_session, stelle_hash
from .textgrenzen import fuer_speicher

logger = logging.getLogger("bewerbungs_assistent.scraper.praktikum_de")

BASIS = "https://www.praktikum.de"
SUCHE = BASIS + "/detailsuche/ergebnisse,seite-{seite}.html"
# Die Felder des Formulars auf der Startseite, wie der Browser sie schickt.
FORMULAR = {"stichwort": "", "branche": "0", "ort": "", "land": "0",
            "schnellsuche": "1", "suchen": "Search"}
MAX_SEITEN = 6
MAX_DETAILS = 10
PAUSE_S = 0.5

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _feld(karte, icon: str) -> str:
    symbol = karte.find("i", class_=icon)
    if not symbol or not symbol.parent:
        return ""
    wert = symbol.parent.find("a")
    return wert.get_text(" ", strip=True) if wert else ""


def karten_aus_html(html: str) -> list[dict]:
    """Alle Angebote einer Ergebnisseite."""
    soup = BeautifulSoup(html, "html.parser")
    stellen: list[dict] = []
    gesehen: set = set()
    for link in soup.select("h5 > a[href^='/angebote/']"):
        href = link["href"]
        if href in gesehen:
            continue
        gesehen.add(href)
        titel = link.get_text(" ", strip=True)
        if not titel:
            continue
        karte = link.find_parent("div", class_="col-md-9") or link.find_parent("div") or link
        branche = _feld(karte, "fa-building-o")
        ort = _feld(karte, "fa-map-marker")
        beginn = _feld(karte, "fa-clock-o")
        anriss = ""
        for block in karte.find_all("div", class_="margin-top-1rem"):
            if not block.find("button"):
                anriss = block.get_text(" ", strip=True)
                break
        text = "\n".join(t for t in (
            anriss,
            f"Branche: {branche}" if branche else "",
            f"Beginn: {beginn}" if beginn else "",
        ) if t)
        url = f"{BASIS}{href}"
        stellen.append({
            "hash": stelle_hash("praktikum_de", f"{url} {titel}"),
            "title": titel,
            "company": "Nicht angegeben",
            "location": ort,
            "url": url,
            "source": "praktikum_de",
            "description": fuer_speicher(text),
            "employment_type": "werkstudent" if re.search(r"werkstudent", titel, re.I) else "praktikum",
            "remote_level": detect_remote_level(f"{titel} {ort} {anriss[:500]}"),
        })
    return stellen


def _eigenes(scope, name: str):
    """Das `itemprop`-Element, das direkt zu diesem Bereich gehoert — nicht
    das gleichnamige einer eingebetteten Firma (sie hat eine eigene
    `description`)."""
    for element in scope.find_all(attrs={"itemprop": name}):
        if element.find_parent(attrs={"itemscope": True}) is scope:
            return element
    return None


def _wert(element) -> str:
    if element is None:
        return ""
    return (element.get("content") or element.get("datetime")
            or element.get_text(" ", strip=True) or "").strip()


def detail_aus_html(html: str) -> dict:
    """Firma, Ort, Text und Datum aus der JobPosting-Microdata."""
    soup = BeautifulSoup(html, "html.parser")
    posting = soup.find(attrs={"itemtype": re.compile(r"JobPosting", re.I)})
    if posting is None:
        return {}
    firma = _eigenes(posting, "hiringOrganization")
    ort = _eigenes(posting, "jobLocation")
    adresse = _eigenes(ort, "address") if ort is not None else None
    return {
        "firma": _wert(_eigenes(firma, "name")) if firma is not None else "",
        "ort": _wert(_eigenes(adresse, "addressLocality")) if adresse is not None else "",
        "beschreibung": _wert(_eigenes(posting, "description")),
        "datum": _wert(_eigenes(posting, "datePosted"))[:10],
    }


def search_praktikum_de(params: dict, client=None) -> list[dict]:
    """Alle Angebote der Boerse ueber das Suchformular holen.

    `params` bleibt Teil der Signatur wie bei jedem Adapter; die Suchbegriffe
    wirken im zentralen Filter (siehe Modulkopf).
    """
    stellen: list[dict] = []
    gesehen: set = set()

    def _laufen(c) -> None:
        try:
            c.get(f"{BASIS}/")  # legt die Sitzung an
        except httpx.HTTPError:
            pass
        for seite in range(1, MAX_SEITEN + 1):
            try:
                if seite == 1:
                    antwort = c.post(SUCHE.format(seite=1), data=FORMULAR)
                else:
                    antwort = c.get(SUCHE.format(seite=seite))
            except httpx.HTTPError as exc:
                logger.warning("Praktikum.de: Seite %d nicht erreichbar: %s", seite, exc)
                return
            if antwort.status_code == 429:
                logger.warning("Praktikum.de: Anfragegrenze erreicht (HTTP 429) auf Seite %d — "
                               "Lauf endet mit %d Angeboten", seite, len(stellen))
                return
            if antwort.status_code != 200:
                logger.warning("Praktikum.de: HTTP %s auf Seite %d", antwort.status_code, seite)
                break
            karten = karten_aus_html(antwort.text)
            for stelle in karten:
                if stelle["url"] not in gesehen:
                    gesehen.add(stelle["url"])
                    stellen.append(stelle)
            if not karten or f"ergebnisse,seite-{seite + 1}.html" not in antwort.text:
                break
            if seite == MAX_SEITEN:
                logger.info("Praktikum.de: nach %d Seiten abgebrochen, die Boerse hat mehr", seite)
            time.sleep(PAUSE_S)

        for stelle in stellen[:MAX_DETAILS]:
            try:
                antwort = c.get(stelle["url"])
            except httpx.HTTPError:
                continue
            if antwort.status_code == 429:
                logger.warning("Praktikum.de: Anfragegrenze bei den Detailseiten erreicht")
                return
            if antwort.status_code != 200:
                continue
            detail = detail_aus_html(antwort.text)
            if detail.get("firma"):
                stelle["company"] = detail["firma"]
            if detail.get("ort"):
                stelle["location"] = detail["ort"]
            if len(detail.get("beschreibung") or "") > len(stelle["description"]):
                stelle["description"] = fuer_speicher(detail["beschreibung"])
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", detail.get("datum") or ""):
                stelle["veroeffentlicht_am"] = detail["datum"]
            time.sleep(PAUSE_S)

    if client is not None:
        _laufen(client)
    else:
        with make_session(content_type="html", timeout=20, user_agent=_UA) as c:
            _laufen(c)

    logger.info("Praktikum.de: %d Angebote", len(stellen))
    return stellen
