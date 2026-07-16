"""Claude-Handoff fuer blockierte/SPA-tote Quellen — B25 (#735, v1.8.0-beta.5).

Verallgemeinert das erprobte `google_jobs_url`-Muster (#573): Wenn eine
Quelle per HTTP nicht scrapbar ist (Bot-Block, SPA-Shell, tot), liefert
PBP eine **Browser-Such-URL** plus ein **generisches Extraktions-JS** —
Claude oeffnet die Seite (Claude-in-Chrome), zieht strukturierte Treffer
aus dem DOM und legt sie via `stelle_manuell_anlegen` an.

Bewusste Design-Grenze (Master-Plan-Optimierung, B18-Zurueckstellung):
KEINE portalspezifischen DOM-Selektoren ohne Live-Inspection — die
Such-URLs unten sind langlebig, das Extraktions-JS ist DOM-agnostisch
(Anker-Heuristik wie beim Newsletter-Ingest).
"""
from __future__ import annotations

from urllib.parse import quote_plus

# Langlebige Such-URL-Muster (Query-Parameter, keine DOM-Wetten).
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

# DOM-agnostische Extraktion: sammelt Links, deren Text wie ein
# Stellentitel aussieht (Laenge, keine Navigations-Floskeln), dedupliziert
# per URL. Funktioniert auf Ergebnisseiten der meisten Boersen und auf
# Karriereseiten (Custom-Quellen) — Qualitaet prueft Claude beim Anlegen.
GENERIC_EXTRACTION_JS = r"""
(() => {
  const stop = /^(mehr|alle|jetzt|hier|login|anmelden|impressum|datenschutz|agb|hilfe|kontakt|karriere|jobs?|stellenangebote|weiter|zurueck|zurück|filter|suche|profil|einstellungen|cookie.*)$/i;
  const seen = new Set();
  const jobs = [];
  for (const a of document.querySelectorAll('a[href]')) {
    const text = (a.innerText || '').replace(/\s+/g, ' ').trim();
    const href = a.href || '';
    if (!href.startsWith('http')) continue;
    if (text.length < 8 || text.length > 140) continue;
    if (stop.test(text)) continue;
    if (!/[A-Za-zÄÖÜäöüß]{3}/.test(text)) continue;
    const key = href.split('?')[0];
    if (seen.has(key)) continue;
    seen.add(key);
    jobs.push({ titel: text, link: href });
    if (jobs.length >= 40) break;
  }
  return { count: jobs.length, jobs };
})()
""".strip()


def build_handoff(quelle: str, keyword: str, ort: str = "",
                  custom_url: str = "") -> dict:
    """Baut das Handoff-Paket fuer eine Quelle (oder Custom-URL)."""
    kw = (keyword or "").strip()
    if custom_url:
        url = custom_url
        quelle_label = quelle or "custom"
    else:
        template = HANDOFF_URL_TEMPLATES.get((quelle or "").lower())
        if not template:
            return {
                "status": "kein_template",
                "hinweis": (
                    f"Fuer '{quelle}' ist keine Handoff-Such-URL hinterlegt. "
                    "Bekannt: " + ", ".join(sorted(HANDOFF_URL_TEMPLATES))
                    + ". Fuer eigene Karriereseiten: custom_quelle_hinzufuegen."
                ),
            }
        url = template.format(
            keyword=quote_plus(kw) if kw else "",
            keyword_pfad=quote_plus(kw.replace(" ", "-")) if kw else "",
            ort=quote_plus((ort or "").strip()),
        ).rstrip("?&")
        quelle_label = quelle
    return {
        "status": "handoff",
        "quelle": quelle_label,
        "url": url,
        "extraction_js": GENERIC_EXTRACTION_JS,
        "anleitung": (
            "1. URL in Chrome mit Claude-in-Chrome oeffnen (eingeloggte "
            "Session umgeht Bot-Blocker). 2. Treffer mit javascript_tool() "
            "und `extraction_js` strukturiert aus dem DOM ziehen. "
            "3. Passende Stellen mit stelle_manuell_anlegen(titel, firma, "
            f"url, quelle='{quelle_label}') uebernehmen — Score und "
            "Duplikat-Erkennung laufen automatisch."
        ),
    }
