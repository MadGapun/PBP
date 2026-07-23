"""Langlebige Such-URL-Muster je Quelle (v1.7.9, #763).

Reine DATEN, kein Feature: `stellen_urls_heilen` braucht sie, um bei einer
Stelle mit leerer URL wenigstens eine gezielte Trefferliste nachzutragen —
statt den Nutzer mit einem leeren Feld stehen zu lassen.

Bewusst nur Query-Parameter-Muster, keine DOM-Wetten: diese URLs ueberleben
Portal-Redesigns. In der v1.8-Linie liegt dieselbe Tabelle in
`job_scraper/handoff.py` (B25/#735) — dort zusammen mit dem
Browser-Handoff-Feature, das in der Stable-Linie NICHT enthalten ist.
Aendert sich hier ein Muster, gehoert es dort nachgezogen.

Platzhalter: {keyword} (URL-kodiert), {keyword_pfad} (Leerzeichen als
Bindestrich, fuer SEO-Pfade) und {ort}.
"""
from __future__ import annotations

HANDOFF_URL_TEMPLATES: dict[str, str] = {
    "gulp": "https://www.gulp.de/gulp2/g/projekte?query={keyword}",
    "kimeta": "https://www.kimeta.de/jobs?q={keyword}&l={ort}",
    "heise_jobs": "https://jobs.heise.de/?keywords={keyword}",
    "stepstone": "https://www.stepstone.de/jobs/{keyword_pfad}",
    "linkedin": "https://www.linkedin.com/jobs/search/?keywords={keyword}&location={ort}",
    "xing": "https://www.xing.com/jobs/search?keywords={keyword}&location={ort}",
    "jobspy_indeed": "https://de.indeed.com/jobs?q={keyword}&l={ort}",
    "indeed": "https://de.indeed.com/jobs?q={keyword}&l={ort}",
}
