"""freelance.de — Projektboerse fuer Freelancer.

v1.7.107 (B53, gemessen 14.09.2026): die Projektsuche der Seite ist eine
App-Huelle ohne Treffer. Die Stichwort-Seiten dagegen liefern die Karten
im HTML::

    GET https://www.freelance.de/<Begriff>-Projekte[?_offset=20]

20 Projekte je Seite, mit Firma, Ort, Start, Remote-Hinweis und
Veroeffentlichungsdatum; ein unbekannter Begriff antwortet mit 410.

Warum der Adapter bis v1.7.105 nichts lieferte:

* Ohne `freelance_de_urls` fiel er auf vier Kategorieseiten zurueck, die
  nur je zwei Karten tragen.
* Fuer JEDES Projekt holte er die Detailseite mit einer Sekunde Pause.
  Bei drei Seiten je Begriff lief der Suchlauf in die Zeitgrenze, und das
  Ergebnis war null statt "weniger".

Jetzt: Stichwort-Seiten, Anzeigentext nur fuer die ersten `MAX_DETAILS`
Projekte (den Rest holt das Nachladen), und die Firma aus der Karte statt
"freelance.de" — sonst galten alle Projekte als dieselbe Firma (#1028).
Die Kennung bleibt titelbasiert (B50). Gemessen mit zwei Begriffen: 120
Projekte in rund 20 Sekunden, davon die Haelfte Pausen.
"""

import logging
import re
import time
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from . import detect_remote_level, fetch_description_from_detail, make_session, stelle_hash
from .textgrenzen import fuer_speicher

logger = logging.getLogger("bewerbungs_assistent.scraper.freelance_de")

BASIS = "https://www.freelance.de"
FALLBACK_BEGRIFFE = ["IT", "SAP", "Projektmanagement", "Python"]
MAX_SEITEN = 3
SEITENGROESSE = 20
MAX_BEGRIFFE = 8
MAX_DETAILS = 15
PAUSE_S = 0.5

# Gemessen: "D-Remote" steht im Ortsfeld. Das ist ein Arbeitsmodell, kein
# Ort — geocodet ergaebe es nichts, und ein falscher Ort ist schlimmer als
# ein fehlender (#989).
_REMOTE_ORT = re.compile(r"(?i)^(?:[a-z]{1,3}-)?remote$")

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def begriff_url(begriff: str) -> str:
    """Die Stichwort-Seite zu einem Suchbegriff."""
    return f"{BASIS}/{quote(begriff.strip().replace(' ', '-'))}-Projekte"


def _li_text(karte, icon_teil: str) -> str:
    for li in karte.select("ul.icon-list li"):
        icon = li.find("i")
        if icon and any(icon_teil in klasse for klasse in icon.get("class", [])):
            return li.get_text(" ", strip=True)
    return ""


def _iso_datum(text: str) -> str:
    treffer = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text or "")
    return f"{treffer.group(3)}-{treffer.group(2)}-{treffer.group(1)}" if treffer else ""


def _remote(titel: str, ort: str, hinweis: str, remote_ort: bool = False) -> str:
    aus_titel = detect_remote_level(f"{titel} {ort}")
    if aus_titel != "unbekannt":
        return aus_titel
    if remote_ort:
        return "remote"
    if not hinweis:
        return "unbekannt"
    aus_hinweis = detect_remote_level(hinweis)
    # Die Karte markiert mit dem blossen Wort "Remote", dass Remote-Arbeit
    # moeglich ist — nicht, dass sie vollstaendig remote ist. "remote"
    # schaltet die Ortspruefung ab (#996).
    if aus_hinweis == "remote" and hinweis.strip().lower() == "remote":
        return "hybrid"
    return aus_hinweis


def _extract_project_from_card(karte, seen_urls: set) -> dict | None:
    h3 = karte.find("h3")
    link = h3.find("a", href=True) if h3 else None
    if not link or "/projekte/" not in link["href"]:
        return None
    href = link["href"]
    url = href if href.startswith("http") else f"{BASIS}{href}"
    if url in seen_urls:
        return None
    seen_urls.add(url)

    titel = link.get_text(" ", strip=True)
    if not titel:
        return None

    firma = ""
    feld = karte.find("span", class_="company-name")
    if feld:
        firmen_link = feld.find("a")
        firma = (firmen_link.get_text(" ", strip=True) if firmen_link
                 else feld.get_text(" ", strip=True).replace("Firmenname:", "").strip())

    ort = _li_text(karte, "map-marker")
    remote_ort = bool(_REMOTE_ORT.match(ort))
    if remote_ort:
        ort = ""
    hinweis = _li_text(karte, "laptop-house")
    start = _li_text(karte, "calendar")
    veroeffentlicht = _li_text(karte, "history")
    schlagworte = [t.get_text(" ", strip=True) for t in karte.select("ul.tags li")
                   if t.get_text(strip=True)]

    teile = []
    if start:
        teile.append(f"Start: {start}")
    if ort:
        teile.append(f"Ort: {ort}")
    if hinweis:
        teile.append(f"Arbeitsmodell: {hinweis}")
    elif remote_ort:
        teile.append("Arbeitsmodell: remote")
    if schlagworte:
        teile.append(f"Skills: {', '.join(schlagworte)}")

    stelle = {
        "hash": stelle_hash("freelance.de", titel),
        "title": titel,
        "company": firma or "Nicht angegeben",
        "location": ort,
        "url": url,
        "source": "freelance_de",
        "description": fuer_speicher(" | ".join(teile) if teile else titel),
        "employment_type": "freelance",
        "remote_level": _remote(titel, ort, hinweis, remote_ort),
    }
    datum = _iso_datum(veroeffentlicht)
    if datum:
        stelle["veroeffentlicht_am"] = datum
    return stelle


def _parse_listing_page(html: str, seen_urls: set) -> list:
    """Alle Projektkarten einer Stichwort-Seite."""
    soup = BeautifulSoup(html, "html.parser")
    stellen = []
    for karte in soup.find_all("div", class_="list-item-content"):
        try:
            stelle = _extract_project_from_card(karte, seen_urls)
        except Exception as exc:  # eine kaputte Karte kostet eine Karte
            logger.debug("freelance.de: Karte nicht lesbar: %s", exc)
            continue
        if stelle:
            stellen.append(stelle)
    return stellen


def _has_next_page(html: str, current_offset: int) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    if soup.find("a", href=re.compile(rf"_offset={current_offset + SEITENGROESSE}\b")):
        return True
    nav = soup.find(["nav", "div", "ul"], class_=re.compile(r"paginat"))
    if nav and nav.find("a", string=re.compile(r"(Weiter|Next|>>|›)", re.IGNORECASE)):
        return True
    return False


def search_freelance_de(params: dict, client=None) -> list:
    """Projekte ueber die Stichwort-Seiten holen."""
    kw_data = params.get("keywords", {})
    kw_data = kw_data if isinstance(kw_data, dict) else {"general": list(kw_data or [])}
    urls = list(kw_data.get("freelance_de_urls") or [])
    if not urls:
        urls = [begriff_url(b) for b in (kw_data.get("general") or FALLBACK_BEGRIFFE) if b]
    urls = list(dict.fromkeys(urls))[:MAX_BEGRIFFE]

    stellen: list[dict] = []
    gesehen: set = set()

    def _laufen(c) -> None:
        for basis in urls:
            for seite in range(MAX_SEITEN):
                offset = seite * SEITENGROESSE
                url = basis if seite == 0 else f"{basis}?_offset={offset}"
                try:
                    antwort = c.get(url)
                except httpx.HTTPError as exc:
                    logger.warning("freelance.de: %s nicht erreichbar: %s", url, exc)
                    break
                if antwort.status_code == 410:
                    logger.info("freelance.de: keine Stichwort-Seite fuer %s", basis)
                    break
                if antwort.status_code != 200:
                    logger.warning("freelance.de: HTTP %s fuer %s", antwort.status_code, url)
                    break
                neu = _parse_listing_page(antwort.text, gesehen)
                stellen.extend(neu)
                if not neu or not _has_next_page(antwort.text, offset):
                    break
                time.sleep(PAUSE_S)

        for stelle in stellen[:MAX_DETAILS]:
            try:
                text = fetch_description_from_detail(stelle["url"], c)
            except Exception as exc:  # Detailseite ist Zugabe, kein Muss
                logger.debug("freelance.de: Detailseite nicht lesbar: %s", exc)
                text = ""
            if text and len(text) > len(stelle["description"]):
                stelle["description"] = fuer_speicher(f"{stelle['description']}\n\n{text}")
            time.sleep(PAUSE_S)

    if client is not None:
        _laufen(client)
    else:
        with make_session(content_type="html", timeout=20, user_agent=_UA) as c:
            _laufen(c)

    logger.info("freelance.de: %d Projekte aus %d Stichwort-Seiten", len(stellen), len(urls))
    return stellen
