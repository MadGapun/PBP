"""URL-Health-Check fuer Stellen (#645 Auto-Aging).

Wiederverwendbare Pure-Funktion `check_job_url_health(url, title)` die
- HTTP-Status holt
- bekannte "Stelle vergeben"-Marker im Body sucht
- bei Workday-URLs ueber die JSON-API gegenchecked
- bei statischem HTML einen Title-Token-Match macht (signaltragende
  Tokens des Job-Titels muessen im Body vorkommen)

Ergebnis:
    HealthStatus.OK            — Stelle existiert, Body matcht Titel
    HealthStatus.EXPIRED       — Stelle weg (Workday-API 404, "vergeben"-
                                 Marker, oder Title-Tokens fehlen im Body)
    HealthStatus.HTTP_404      — Hard 404
    HealthStatus.HTTP_ERROR    — andere HTTP-Fehler 4xx/5xx
    HealthStatus.TIMEOUT       — kein Response
    HealthStatus.BLOCKED       — Bot-Detection-Verdacht
    HealthStatus.UNKNOWN       — sonstige Probleme

Genutzt von:
    - `tools/analyse.py` -> `stellen_qualitaet_pruefen` (Manuell-Tool)
    - `dashboard.py` -> `_run_url_aging_check` (Auto-Engine-Step)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger("bewerbungs_assistent.url_health")


class HealthStatus(str, Enum):
    OK = "ok"
    EXPIRED = "expired"
    HTTP_404 = "http_404"
    HTTP_ERROR = "http_error"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"
    LEER = "leer"  # URL leer/fehlt


@dataclass
class HealthResult:
    status: HealthStatus
    http_code: Optional[int] = None
    final_url: Optional[str] = None
    marker: Optional[str] = None
    title_token_hits: Optional[str] = None  # "n/m"
    body_bytes: Optional[int] = None
    workday_api_status: Optional[int] = None
    note: Optional[str] = None

    def to_dict(self) -> dict:
        out = {"status": self.status.value}
        for k in ("http_code", "final_url", "marker", "title_token_hits",
                  "body_bytes", "workday_api_status", "note"):
            v = getattr(self, k)
            if v is not None:
                out[k] = v
        return out

    @property
    def should_dismiss(self) -> bool:
        """True wenn die Stelle als 'veraltet' aussortiert werden sollte."""
        return self.status in (HealthStatus.EXPIRED, HealthStatus.HTTP_404)


# Bekannte "Stelle nicht mehr verfuegbar"-Marker (case-insensitive)
EXPIRED_MARKERS = [
    re.compile(r"stelle\s+(ist\s+)?bereits\s+vergeben", re.I),
    re.compile(r"diese\s+stelle\s+ist\s+nicht\s+(mehr\s+)?(verf[uü]gbar|aktiv)", re.I),
    re.compile(r"position\s+(is\s+)?(no\s+longer\s+)?(available|filled)", re.I),
    re.compile(r"job\s+(is\s+)?(no\s+longer\s+)?(available|active|posted)", re.I),
    re.compile(r"opportunity\s+no\s+longer\s+available", re.I),
    re.compile(r"stellenangebot\s+ist\s+nicht\s+mehr\s+verf[uü]gbar", re.I),
    re.compile(r"this\s+job\s+(has\s+been\s+)?(filled|closed|removed|expired)", re.I),
    re.compile(r"vacancy\s+(is\s+)?(closed|expired|filled|removed)", re.I),
    re.compile(r"die\s+ausschreibung\s+(ist|wurde)\s+beendet", re.I),
    re.compile(r"stelle\s+(wurde\s+)?besetzt", re.I),
    re.compile(r"diese\s+stelle\s+(wurde|ist)\s+(geschlossen|nicht\s+mehr\s+verf[uü]gbar)", re.I),
    re.compile(r"the\s+job\s+you\s+are\s+looking\s+for\s+is\s+not\s+available", re.I),
    re.compile(r"this\s+job\s+is\s+no\s+longer\s+accepting\s+applications", re.I),
    re.compile(r"die\s+stellenanzeige\s+ist\s+nicht\s+mehr\s+verf[uü]gbar", re.I),
    re.compile(r"keine\s+stellenanzeige\s+gefunden", re.I),
]

# Bot-Detection-Marker (separater Status, kein "expired")
BLOCKED_MARKERS = [
    re.compile(r"captcha", re.I),
    re.compile(r"cloudflare", re.I),
    re.compile(r"access\s+denied", re.I),
    re.compile(r"please\s+verify\s+you\s+are\s+human", re.I),
    re.compile(r"unusual\s+traffic", re.I),
]


def title_tokens(title: str) -> set[str]:
    """Signaltragende Tokens aus dem Titel (>=4 Zeichen, lowercase).

    Stoppwoerter raus, Praefix-Emojis raus (durch [A-Za-zAEOEUEaeoeuess0-9]+
    Match natuerlich gefiltert).
    """
    if not title:
        return set()
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß0-9]+", title.lower())
    stop = {"the", "and", "for", "all", "die", "der", "das", "ein", "und",
            "mit", "von", "zur", "zum", "auf", "des", "bei", "m/w/d",
            "f/m/d", "d/f/m", "all", "genders", "alle", "gender"}
    return {t for t in tokens if len(t) >= 4 and t not in stop}


def _workday_api_url(html_url: str) -> Optional[str]:
    """Workday-HTML-URL -> JSON-API-URL.

    Workday rendert per JS, das HTML ist nur ein Skeleton. Die Stellen-
    Existenz ist nur ueber `wday/cxs/{tenant}/{site}/job/{path}` testbar.
    None wenn URL kein Workday-Format.
    """
    m = re.match(
        r"^(https://([^/]+\.)?wd\d+\.myworkdayjobs\.com)/(?:[A-Za-z\-]+/)?([^/]+)/job/(.+?)/?$",
        html_url,
    )
    if not m:
        return None
    base, _, site, path = m.groups()
    tenant = base.split("//", 1)[1].split(".")[0]
    return f"{base}/wday/cxs/{tenant}/{site}/job/{path}"


def check_job_url_health(
    url: Optional[str],
    title: Optional[str] = None,
    *,
    client=None,
    timeout: float = 15.0,
) -> HealthResult:
    """Pruefe ob eine Job-URL noch eine aktive Stelle ausliefert.

    Args:
        url: Die zu pruefende URL (kann leer/None sein -> LEER)
        title: Der Stellentitel fuer den Title-Token-Cross-Check.
            Wenn None: nur HTTP-Status + Marker werden gepruet.
        client: Optionaler httpx.Client (fuer Test-Mocks).
            Wenn None: pro Aufruf ein eigener Client.
        timeout: Sekunden Pro-Request-Timeout.

    Returns:
        HealthResult mit Status und Detail-Feldern.
    """
    if not url or not url.strip():
        return HealthResult(status=HealthStatus.LEER)

    url = url.strip()

    try:
        import httpx
    except ImportError:
        return HealthResult(status=HealthStatus.UNKNOWN, note="httpx fehlt")

    own_client = client is None
    if own_client:
        client = httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/131.0.0.0 Safari/537.36",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            },
        )

    try:
        try:
            r = client.get(url)
        except httpx.TimeoutException:
            return HealthResult(status=HealthStatus.TIMEOUT)
        except httpx.RequestError as exc:
            return HealthResult(
                status=HealthStatus.UNKNOWN,
                note=f"{type(exc).__name__}: {str(exc)[:200]}",
            )

        result = HealthResult(
            status=HealthStatus.OK,
            http_code=r.status_code,
            final_url=str(r.url),
        )

        if r.status_code == 404 or r.status_code == 410:
            result.status = HealthStatus.HTTP_404
            return result
        if r.status_code >= 400:
            result.status = HealthStatus.HTTP_ERROR
            return result

        body = r.text or ""
        result.body_bytes = len(body)
        snippet = body[:200_000]

        # Bot-Detection check
        for pat in BLOCKED_MARKERS:
            if pat.search(snippet):
                result.status = HealthStatus.BLOCKED
                result.marker = pat.pattern[:80]
                return result

        # Expired-Marker check
        for pat in EXPIRED_MARKERS:
            m = pat.search(snippet)
            if m:
                result.status = HealthStatus.EXPIRED
                result.marker = m.group(0)[:80]
                return result

        # Title-Token-Match auf HTML-Body
        body_hit_ok = True
        if title:
            tokens = title_tokens(title)
            if tokens:
                snippet_l = snippet.lower()
                hits = sum(1 for t in tokens if t in snippet_l)
                result.title_token_hits = f"{hits}/{len(tokens)}"
                body_hit_ok = hits >= max(1, len(tokens) // 3)

        # Workday-Sonderfall: SPA, HTML-Body ist nur Skeleton.
        # API-Endpoint gegenchecken.
        api = _workday_api_url(url)
        if api:
            try:
                r2 = client.get(api, headers={"Accept": "application/json"})
                result.workday_api_status = r2.status_code
                if r2.status_code == 404:
                    result.status = HealthStatus.EXPIRED
                    result.marker = "workday api 404"
                    return result
                if r2.status_code >= 400:
                    result.status = HealthStatus.EXPIRED
                    result.marker = f"workday api http {r2.status_code}"
                    return result
                # API-200 = Stelle existiert. Title-Cross-Check zur Sicherheit.
                if title:
                    tokens = title_tokens(title)
                    if tokens:
                        text2 = (r2.text or "").lower()
                        hits = sum(1 for t in tokens if t in text2)
                        result.title_token_hits = f"{hits}/{len(tokens)} (api)"
                        if hits < max(1, len(tokens) // 3):
                            result.status = HealthStatus.EXPIRED
                            result.marker = "workday api title mismatch"
                            return result
                return result
            except httpx.RequestError as exc:
                # API-Fehler -> wir vertrauen dem HTML-Status, nicht expired
                result.note = f"workday api err: {type(exc).__name__}"
                return result

        # Non-Workday: HTML-Title-Match ist autoritativ
        if not body_hit_ok:
            result.status = HealthStatus.EXPIRED
            result.marker = "title tokens not found in body"
            return result

        return result
    finally:
        if own_client:
            client.close()
