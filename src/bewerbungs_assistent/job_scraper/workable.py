"""Workable — oeffentliche Stellensuche.

v1.7.106 (B53, live gemessen 14.09.2026): Workable betreibt eine
oeffentliche Stellensuche ueber alle Kunden, und die Seite holt ihre
Treffer ueber eine JSON-Schnittstelle::

    GET https://jobs.workable.com/api/v1/jobs
        ?query=<Begriff>&location=Germany[&pageToken=<Token>]

Ohne Anmeldung, 20 Stellen je Seite, voller Anzeigentext samt
Anforderungen, Ort, Arbeitsmodell und `nextPageToken`.

Bis v1.7.105 fragte der Adapter je Firma aus einer festen Liste die
Einbettungs-Schnittstelle ab. Nachgemessen antworteten sechs von acht
Firmen mit einer leeren Liste und zwei mit 404 — die Quelle stand zu
Recht als defekt, nur war der tote Weg der falsche, nicht der einzige.

`workable_firmen` (#811) bleibt wirksam: ein Eintrag wird als weiterer
Suchbegriff abgefragt. Die Region grenzt die Suche nicht ein — die
Entfernung rechnet PBP selbst.
"""

from __future__ import annotations

import html
import logging
import re
import time

import httpx

from . import detect_remote_level, make_session, stelle_hash
from .textgrenzen import fuer_speicher

logger = logging.getLogger("bewerbungs_assistent.scraper.workable")

SUCHE = "https://jobs.workable.com/api/v1/jobs"
LAND = "Germany"
MAX_SEITEN = 3
MAX_BEGRIFFE = 8
PAUSE_S = 0.5

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# Das Arbeitsmodell steht als eigenes Feld in der Antwort — es gewinnt
# vor jeder Vermutung aus dem Text ("Homeoffice" unter den Vorteilen ist
# kein Remote-Arbeitsplatz).
_ARBEITSMODELL = {
    "remote": "remote",
    "hybrid": "hybrid",
    "on_site": "vor_ort",
    "onsite": "vor_ort",
    "on-site": "vor_ort",
}


def _text(roh: str) -> str:
    if not roh:
        return ""
    ohne_tags = re.sub(r"<[^>]+>", " ", roh)
    return re.sub(r"\s+", " ", html.unescape(ohne_tags)).strip()


def stelle_aus(job: dict) -> dict | None:
    """Eine Stelle der Suchantwort auf das PBP-Schema abbilden."""
    titel = _text(job.get("title") or "")
    if not titel:
        return None

    firma = job.get("company")
    firma = (firma.get("title") if isinstance(firma, dict) else firma) or ""

    ort_roh = job.get("location") or {}
    # Nur die Stadt. Ein blosses "Germany" wuerde als Mittelpunkt
    # Deutschlands geocodiert — eine erfundene Entfernung (#989).
    ort = _text(ort_roh.get("city") or "") if isinstance(ort_roh, dict) else _text(str(ort_roh))

    teile = [_text(job.get(feld) or "")
             for feld in ("description", "requirementsSection", "benefitsSection")]
    text = "\n\n".join(t for t in teile if t)

    art = (job.get("employmentType") or "").lower()
    if "intern" in art:
        form = "praktikum"
    elif "contract" in art or "freelance" in art:
        form = "freelance"
    else:
        form = "festanstellung"

    modell = (_ARBEITSMODELL.get((job.get("workplace") or "").lower())
              or detect_remote_level(f"{titel} {ort} {text[:500]}"))

    kennung = job.get("id") or job.get("url") or titel
    stelle = {
        "hash": stelle_hash("workable", str(kennung)),
        "title": titel,
        "company": firma.strip() or "Nicht angegeben",
        "location": ort,
        "url": job.get("url") or "",
        "source": "workable",
        "description": fuer_speicher(text),
        "employment_type": form,
        "remote_level": modell,
    }
    # Anstellungsform und Umfang sind zwei Fragen (#1023).
    if "full" in art:
        stelle["arbeitsumfang"] = "vollzeit"
    elif "part" in art:
        stelle["arbeitsumfang"] = "teilzeit"
    datum = (job.get("created") or "")[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", datum):
        stelle["veroeffentlicht_am"] = datum
    return stelle


def search_workable(params: dict, client=None) -> list[dict]:
    """Stellen je Suchbegriff ueber die oeffentliche Suche holen."""
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        begriffe = list(kw_data.get("general") or [])[:MAX_BEGRIFFE]
        firmen = list(kw_data.get("workable_firmen") or [])
    else:
        begriffe = list(kw_data or [])[:MAX_BEGRIFFE]
        firmen = []
    suchen = [s for s in dict.fromkeys(begriffe + firmen) if s] or [""]

    stellen: list[dict] = []
    gesehen: set = set()

    def _laufen(c) -> None:
        for suche in suchen:
            token = None
            for _seite in range(MAX_SEITEN):
                anfrage = {"query": suche, "location": LAND}
                if token:
                    anfrage["pageToken"] = token
                try:
                    antwort = c.get(SUCHE, params=anfrage)
                except httpx.HTTPError as exc:
                    logger.warning("Workable: Anfrage fuer '%s' fehlgeschlagen: %s", suche, exc)
                    break
                if antwort.status_code != 200:
                    logger.warning("Workable: HTTP %s fuer '%s'", antwort.status_code, suche)
                    break
                try:
                    daten = antwort.json()
                except ValueError:
                    logger.warning("Workable: Antwort fuer '%s' ist kein JSON", suche)
                    break
                jobs = daten.get("jobs") or [] if isinstance(daten, dict) else []
                for job in jobs:
                    schluessel = job.get("id") or job.get("url")
                    if schluessel in gesehen:
                        continue
                    gesehen.add(schluessel)
                    stelle = stelle_aus(job)
                    if stelle:
                        stellen.append(stelle)
                token = daten.get("nextPageToken") if isinstance(daten, dict) else None
                if not jobs or not token:
                    break
                time.sleep(PAUSE_S)

    if client is not None:
        _laufen(client)
    else:
        with make_session(content_type="json", timeout=20, user_agent=_UA) as c:
            _laufen(c)

    logger.info("Workable: %d Stellen aus %d Suchen", len(stellen), len(suchen))
    return stellen
