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

from pathlib import Path
from urllib.parse import quote_plus

from ..services import quellen_auflagen
from ..services.browser_handoff import REGEL_IM_ZWEIFEL

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
    # #1189: Projektsuche von jobtic, serverseitig geliefert; `q` filtert (live gemessen 10.10.2026).
    "jobtic": "https://jobtic.com/search?type=projects&q={keyword}",
}

# Quellen mit eigenem Auswerte-Skript. Es liest, was die Seite selbst als Liste mitliefert - eine
# Datei im Paket, die ein Test (und die CI) gegen eine nachgebaute Seite ausfuehrt, nicht eine Kopie.
_EXTRAKTION_JE_QUELLE: dict[str, str] = {
    "jobtic": "jobtic_extraction.js",
}

# DOM-agnostische Extraktion: sammelt Links, deren Text wie ein
# Stellentitel aussieht (Laenge, keine Navigations-Floskeln), dedupliziert
# per URL. Funktioniert auf Ergebnisseiten der meisten Boersen und auf
# Karriereseiten (Custom-Quellen) — Qualitaet prueft Claude beim Anlegen.
GENERIC_EXTRACTION_JS = r"""
(() => {
  const stop = /^(mehr|alle|jetzt|hier|login|anmelden|impressum|datenschutz|agb|hilfe|kontakt|karriere|jobs?|stellenangebote|weiter|zurück|zurück|filter|suche|profil|einstellungen|cookie.*)$/i;
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


def extraktions_js(quelle: str) -> str:
    """Das Auswerte-Skript der Quelle, sonst das generische."""
    datei = _EXTRAKTION_JE_QUELLE.get((quelle or "").lower())
    if not datei:
        return GENERIC_EXTRACTION_JS
    return (Path(__file__).parent / datei).read_text(encoding="utf-8").strip()


def build_handoff(quelle: str, keyword: str, ort: str = "",
                  custom_url: str = "") -> dict:
    """Baut das Handoff-Paket fuer eine Quelle (oder Custom-URL)."""
    kw = (keyword or "").strip()
    wirksam = (quelle or "").lower()  # die Quelle, deren Auflagen und Auswerte-Skript gelten
    if custom_url:
        url = custom_url
        quelle_label = quelle or "custom"
        # Eine eigene Quelle auf der Adresse einer bekannten gilt wie diese: sonst waere "custom_quelle_hinzufuegen" der
        # Umweg um die Auflagen einer Quelle (#1189, Befund des unabhaengigen Pruefers).
        from ..services.url_to_source import detect_source_from_url
        erkannt = detect_source_from_url(custom_url)
        if erkannt != "manuell":
            wirksam = erkannt
    else:
        template = HANDOFF_URL_TEMPLATES.get((quelle or "").lower())
        if not template:
            return {
                "status": "kein_template",
                "hinweis": (
                    f"Für '{quelle}' ist keine Handoff-Such-URL hinterlegt. "
                    "Bekannt: " + ", ".join(sorted(HANDOFF_URL_TEMPLATES))
                    + ". Für eigene Karriereseiten: custom_quelle_hinzufuegen."
                ),
            }
        url = template.format(
            keyword=quote_plus(kw) if kw else "",
            keyword_pfad=quote_plus(kw.replace(" ", "-")) if kw else "",
            ort=quote_plus((ort or "").strip()),
        ).rstrip("?&")
        quelle_label = quelle
    # #1189: Auflagen der Quelle (jobtic). Dann ist es auch keine "Session, die Bot-Blocker umgeht": es ist
    # der eigene, angemeldete Browser, von Hand gestartet.
    auflagen = quellen_auflagen.hinweis_fuer_claude(wirksam, url)
    schritt_1 = ("1. URL im eigenen, angemeldeten Chrome mit Claude-in-Chrome öffnen. " if auflagen
                 else "1. URL in Chrome mit Claude-in-Chrome öffnen (eingeloggte "
                      "Session umgeht Bot-Blocker). ")
    anleitung = (
        schritt_1
        + "2. Treffer mit javascript_tool() und `extraction_js` strukturiert aus dem DOM ziehen. "
        "3. Alle Treffer, die fachlich passen oder nahezu passen, mit "
        "stelle_manuell_anlegen(titel, firma, "
        f"url, quelle='{quelle_label}') uebernehmen — Score und "
        "Duplikat-Erkennung laufen automatisch. " + REGEL_IM_ZWEIFEL
    )
    ergebnis = {
        "status": "handoff",
        "quelle": quelle_label,
        "url": url,
        "extraction_js": extraktions_js(wirksam if custom_url else quelle_label),
        "anleitung": anleitung + (" " + auflagen if auflagen else ""),
    }
    if auflagen:
        ergebnis["auflagen"] = auflagen
    return ergebnis
