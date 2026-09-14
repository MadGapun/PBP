"""Ergebniskarten der Jobboersen-Plattform hinter Jobware und ingenieur.de.

v1.7.104 (#1041, #1042): beide Boersen laufen auf derselben Plattform und
hatten zwei eigene Fassungen desselben Fehlers.

* **Zu breite Auswahl.** `[class*='job-card']` trifft nicht nur die Karte,
  sondern auch jeden ihrer Bestandteile (`job-card__top-row`,
  `job-card__location` ...). Gemessen am 14.09.2026: 173 Treffer bei 15
  Karten, `cards[:25]` waren Teile der ersten Karten.
* **Titel aus dem falschen Link.** Der erste Link einer Jobware-Karte ist
  der Knopf "Job ansehen" mit dem Titel als verstecktem Text:
  `Job"<Titel>"ansehen`. Der Titel steht in `h2.headline`.
* **Firma und Ort ueber Klassennamen, die es nicht gibt.** Die Firma steht
  bei Jobware in `job-card__advertiser-name`, bei ingenieur.de im ersten
  `text-body-medium` der Karte. Der Ort traegt ein nur fuer Screenreader
  gedachtes "in" — `get_text(strip=True)` machte daraus `inBerlin`, und
  dafuer findet PBP keine Koordinaten.

Hier steht die Karte EINMAL: eine Karte ist ein Element mit der Klasse
`job-card` selbst, nicht ein Element, dessen Klasse das Wort enthaelt.

v1.7.108 (#1041 Nachtrag, B54): die Plattform setzt vor fast jeden Text
HTML-Kommentare (`<!--t=g-->`, `<!--qv q:key=...-->`, `<!--/qv-->`). In
BeautifulSoup ist ein Kommentar ebenfalls ein Textknoten, und die eigene
Schleife nahm ihn mit: gemessen am 14.09.2026 trugen 20 von 20 Jobware- und
16 von 16 ingenieur.de-Karten Reste in Titel, Firma und Ort. Die Fixtures aus
v1.7.104 enthielten keine Kommentare — deshalb blieb der Fehler im Test
unsichtbar. Den Bestand heilt `services/karten_heilung`.
"""
from __future__ import annotations

from bs4 import BeautifulSoup
from bs4.element import NavigableString, PreformattedString

#: Klasse der Karte selbst — nicht `[class*='job-card']`.
KARTEN_KLASSE = "job-card"
_VERSTECKT = "visually-hidden"


def _versteckt(element) -> bool:
    return any(_VERSTECKT in k for k in (element.get("class") or []))


def _ist_inhalt(knoten) -> bool:
    """Ein Textknoten, der Inhalt ist — kein Kommentar, keine CDATA-,
    Doctype- oder Verarbeitungsanweisung (alle `PreformattedString`)."""
    return isinstance(knoten, NavigableString) and not isinstance(knoten, PreformattedString)


def _sichtbarer_text(element) -> str:
    """Text ohne die fuer Screenreader versteckten Teile und ohne Kommentare."""
    if element is None:
        return ""
    teile = []
    for knoten in element.descendants:
        if _ist_inhalt(knoten):
            eltern = knoten.parent
            if eltern is not None and any(_versteckt(e) for e in [eltern, *eltern.parents]
                                          if getattr(e, "get", None)):
                continue
            teile.append(knoten)
    return " ".join(" ".join(teile).split())


def _ort(karte) -> str:
    """Der Ort: bei Jobware ein eigenes Element, bei ingenieur.de ein
    Element ohne Klasse, das neben dem versteckten "in" steht."""
    element = karte.select_one(".job-card__location")
    if element is None:
        for versteckt in karte.select(f"[class*='{_VERSTECKT}']"):
            if versteckt.get_text(strip=True) == "in" and versteckt.parent is not None:
                element = versteckt.parent
                break
    return _sichtbarer_text(element)


def _firma(karte) -> str:
    element = karte.select_one(".job-card__advertiser-name")
    if element is None:
        element = karte.select_one(".text-body-medium")
    return _sichtbarer_text(element)


def karten_aus_html(html: str, basis_url: str) -> list[dict]:
    """Alle Karten einer Ergebnisseite als {titel, firma, ort, url}.

    Eine Karte ohne Titel oder ohne Link zur Anzeige wird uebersprungen;
    jede Anzeige kommt einmal vor, auch wenn die Seite sie doppelt fuehrt.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    gesehen: set = set()
    karten: list[dict] = []
    # `class_=` vergleicht je KLASSE, nicht als Teilstring: `job-card__top-row`
    # trifft das nicht. Bestandteile innerhalb einer Karte faengt ausserdem
    # der URL-Abgleich unten ab — entscheidend ist die Auswahl fuer Elemente
    # AUSSERHALB einer Karte (etwa ein Teaser `job-card__...` mit Link).
    for karte in soup.find_all(class_=KARTEN_KLASSE):
        titel_el = karte.select_one("h2.headline") or karte.find("h2")
        titel = _sichtbarer_text(titel_el)
        link = karte.select_one("a[href*='/job/'], a[href*='/stellenangebot/']")
        href = (link.get("href") or "").strip() if link else ""
        if not titel or not href:
            continue
        url = href if href.startswith("http") else f"{basis_url.rstrip('/')}{href}"
        if url in gesehen:
            continue
        gesehen.add(url)
        karten.append({"titel": titel, "firma": _firma(karte), "ort": _ort(karte), "url": url})
    return karten
