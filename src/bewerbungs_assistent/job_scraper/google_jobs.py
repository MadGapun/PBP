"""Google Jobs via Chrome-Extension (#501).

Google Jobs ist der groesste Aggregator im DACH-Raum und indexiert u.a.
StepStone-, Jobware- und Stellenanzeigen.de-Inhalte. Ein direkter
HTTP-Scraper ist von Google zuverlaessig blockiert — der Weg ueber die
Claude-in-Chrome-Extension funktioniert aber stabil, weil dort ein
eingeloggter Browser die Anfrage stellt (Live-Test 2026-04-24).

Dieses Modul liefert deshalb KEINEN automatischen Scraper, sondern
nur:
    - einen URL-Builder (`build_google_jobs_url`), damit das MCP-Tool
      und die Dashboard-UX exakt dieselben Parameter erzeugen,
    - eine Stub-Search-Funktion (`search_google_jobs`), die 0 Treffer
      mit einer klaren Hinweis-Meldung zurueckgibt — der
      Scraper-Dispatcher soll die Quelle anbieten, auch wenn er sie
      nicht automatisch abrufen kann.

Der tatsaechliche Ingest laeuft ueber `stelle_manuell_anlegen()` —
analog zum LinkedIn-Flow (#159).
"""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

logger = logging.getLogger("bewerbungs_assistent.scraper.google_jobs")

# `udm=8` schaltet die Google-Jobs-Sicht frei, `tbs=qdr:...` filtert
# nach Zeitraum (d=Tag, w=Woche, m=Monat).
GOOGLE_JOBS_BASE = "https://www.google.com/search"

_QDR_MAP = {
    "tag": "qdr:d",
    "woche": "qdr:w",
    "monat": "qdr:m",
}


def build_google_jobs_url(keyword: str, zeitraum: str = "woche",
                          ort: str | None = None) -> str:
    """Baut eine Google-Jobs-URL fuer Chrome-in-Claude (#501).

    Args:
        keyword: Suchbegriff (z.B. "PLM Projektleiter").
        zeitraum: 'tag' | 'woche' | 'monat'. Andere Werte → kein qdr-Filter.
        ort: Optionaler Ort. Wird als zusaetzliches Token an den Begriff
             gehaengt — Google interpretiert das wie im Browser.

    Die URL ist stabil dokumentiert im Live-Test (2026-04-24) und laeuft
    gegen `google.com/search?udm=8&...`.
    """
    q = keyword.strip()
    if ort:
        q = f"{q} {ort.strip()}".strip()
    params = [f"q={quote_plus(q)}", "udm=8"]
    qdr = _QDR_MAP.get(zeitraum.lower().strip())
    if qdr:
        params.append(f"tbs={qdr}")
    return f"{GOOGLE_JOBS_BASE}?{'&'.join(params)}"


def search_google_jobs(params: dict) -> list[dict]:
    """Stub — Google Jobs laeuft manuell ueber Chrome-Extension.

    Liefert immer eine leere Liste, loggt aber die aufzurufenden URLs,
    damit die Dashboard-UX dem User zeigen kann, welche Google-Jobs-
    Seiten er in Chrome oeffnen soll. Das eigentliche Anlegen passiert
    ueber `stelle_manuell_anlegen()`.
    """
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", [])
        regionen = kw_data.get("regionen", [])
    else:
        keywords = kw_data or []
        regionen = []
    ort = regionen[0] if regionen else None

    if not keywords:
        logger.info("Google Jobs: keine Keywords, nichts zu oeffnen.")
        return []

    urls = [build_google_jobs_url(kw, zeitraum="woche", ort=ort) for kw in keywords]
    logger.info(
        "Google Jobs (#501): Oeffne in Chrome-Extension:\n  %s",
        "\n  ".join(urls),
    )
    return []
