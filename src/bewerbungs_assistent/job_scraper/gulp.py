"""GULP — IT- und Engineering-Projektboerse.

v1.7.106 (B53, live gemessen 14.09.2026): die Projektsuche der Seite ist
eine Angular-App, die ihre Treffer ueber eine offene JSON-Schnittstelle
holt::

    POST https://www.gulp.de/gulp2/rest/internal/projects/search
    {"query": "<Begriff>", "page": <ab 0>}

Ohne Anmeldung und ohne Browser, 20 Projekte je Seite samt
`totalCount`. Bis v1.7.105 fragte der Adapter drei geratene Adressen ab
(alle 404), fiel auf die 9-KB-Huelle der App zurueck und lieferte seit
April 2026 nichts — die Quelle stand als defekt. Die Schnittstelle steht
nicht als Zeichenkette im JavaScript-Bundle; gefunden hat sie erst der
Netzwerk-Mitschnitt eines echten Browsers.

Die Kennung bleibt titelbasiert wie bisher: eine Kennung ist ein Vertrag
mit dem Bestand (B50, #1041).
"""

from __future__ import annotations

import html
import logging
import re
import time

import httpx

from . import detect_remote_level, make_session, stelle_hash
from .textgrenzen import fuer_speicher

logger = logging.getLogger("bewerbungs_assistent.scraper.gulp")

SUCHE = "https://www.gulp.de/gulp2/rest/internal/projects/search"
MAX_SEITEN = 3
MAX_BEGRIFFE = 8
PAUSE_S = 0.5

FALLBACK_QUERIES = [
    "Software Engineer", "Projektmanager", "Data Analyst",
    "DevOps Engineer", "Consultant",
]

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _text(roh: str) -> str:
    """HTML-Reste und Such-Hervorhebungen (`<mark>`) entfernen."""
    if not roh:
        return ""
    ohne_tags = re.sub(r"<[^>]+>", " ", roh)
    return re.sub(r"\s+", " ", html.unescape(ohne_tags)).strip()


def projekt_zu_stelle(projekt: dict) -> dict | None:
    """Ein Projekt der Suchantwort auf das PBP-Schema abbilden."""
    titel = _text(projekt.get("title") or "")
    if not titel:
        return None
    ort = _text(projekt.get("location") or "")
    # #1047: nur die Beschreibung behaelt ihre Gliederung — Titel, Ort und
    # Skills bleiben einzeilig.
    from .html_text import gegliederter_text
    beschreibung = gegliederter_text(projekt.get("description") or "")
    anforderungen = [_text(s) for s in (projekt.get("skills") or []) if s]
    text = "\n\n".join(t for t in (beschreibung, "\n".join(a for a in anforderungen if a)) if t)

    remote = detect_remote_level(f"{titel} {ort} {text[:500]}")
    if remote == "unbekannt" and projekt.get("isRemoteWorkPossible"):
        # "Remote moeglich" heisst nicht "vollstaendig remote" — und
        # "remote" schaltet die Ortspruefung ab (#996).
        remote = "hybrid"

    url = projekt.get("url") or ""
    if not url and projekt.get("id"):
        url = f"https://www.gulp.de/gulp2/g/projekte/{projekt['id']}"

    stelle = {
        "hash": stelle_hash("gulp.de", titel),
        "title": titel,
        # Bei Vermittlungsprojekten (`AGENCY`) nennt GULP keinen
        # Auftraggeber. "GULP" einzusetzen machte alle diese Projekte zu
        # EINER Firma — fuer Wiedergaenger und Blacklist falsch (#1028).
        "company": (projekt.get("companyName") or "").strip() or "Nicht angegeben",
        "location": ort,
        "url": url,
        "source": "gulp",
        "description": fuer_speicher(text),
        "employment_type": "freelance",
        "remote_level": remote,
    }
    datum = (projekt.get("originalPublicationDate") or "")[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", datum):
        stelle["veroeffentlicht_am"] = datum
    return stelle


def _seite(client, begriff: str, seite: int) -> dict | None:
    try:
        antwort = client.post(SUCHE, json={"query": begriff, "page": seite})
    except httpx.HTTPError as exc:
        logger.warning("GULP: Anfrage fuer '%s' Seite %d fehlgeschlagen: %s", begriff, seite, exc)
        return None
    if antwort.status_code != 200:
        logger.warning("GULP: HTTP %s fuer '%s' Seite %d", antwort.status_code, begriff, seite)
        return None
    try:
        daten = antwort.json()
    except ValueError:
        logger.warning("GULP: Antwort fuer '%s' ist kein JSON", begriff)
        return None
    return daten if isinstance(daten, dict) else None


def search_gulp(params: dict, client=None) -> list:
    """Projekte je Suchbegriff ueber die Such-Schnittstelle holen."""
    kw_data = params.get("keywords", {})
    begriffe = kw_data.get("general") if isinstance(kw_data, dict) else kw_data
    begriffe = [b for b in dict.fromkeys(begriffe or FALLBACK_QUERIES) if b][:MAX_BEGRIFFE]

    stellen: list[dict] = []
    gesehen: set = set()

    def _laufen(c) -> None:
        for begriff in begriffe:
            geholt = 0
            for seite in range(MAX_SEITEN):
                daten = _seite(c, begriff, seite)
                if daten is None:
                    break
                projekte = daten.get("projects") or []
                geholt += len(projekte)
                for projekt in projekte:
                    schluessel = projekt.get("id") or projekt.get("url") or projekt.get("title")
                    if schluessel in gesehen:
                        continue
                    gesehen.add(schluessel)
                    stelle = projekt_zu_stelle(projekt)
                    if stelle:
                        stellen.append(stelle)
                if not projekte or geholt >= int(daten.get("totalCount") or 0):
                    break
                time.sleep(PAUSE_S)

    if client is not None:
        _laufen(client)
    else:
        with make_session(content_type="json", timeout=20, user_agent=_UA) as c:
            _laufen(c)

    logger.info("GULP: %d Projekte aus %d Suchbegriffen", len(stellen), len(begriffe))
    return stellen
