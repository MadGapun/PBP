"""#720: Klassifiziert Scraper-Fehler, damit die Reaktion zur Fehlerart passt.

Bisher behandelte das System jeden Fehler gleich hart (deaktivieren). Eine
oft nur temporaere Stoerung (Timeout, 5xx, Verbindung weg) bekam damit die
haerteste, dauerhafteste Behandlung — verkehrt. Diese Klassifikation trennt:

- ``tot``        — HTTP 404/410. Endpoint/Seite dauerhaft weg.
- ``blockiert``  — HTTP 403/429. Meist temporaer, oft mit Retry-After.
- ``server_weg`` — Timeout, HTTP 5xx, ConnectionError, DNS. Sehr wahrscheinlich
                   temporaer.
- ``kaputt``     — Parser-Crash, unerwartete Exception, ImportError. Dauerhaft
                   bis zum Code-Fix.
- ``leer``       — HTTP 200 aber 0 Treffer. Das ist der bestehende
                   silent-Zustand und wird NICHT hier, sondern in
                   update_scraper_health behandelt (nur zur Vollstaendigkeit).

Reine Klassifikation, KEIN Verhaltenswechsel — den steuert #721 anhand der
hier abgeleiteten Klasse.
"""
from __future__ import annotations

from typing import Optional

ERROR_CLASS_TOT = "tot"
ERROR_CLASS_BLOCKIERT = "blockiert"
ERROR_CLASS_SERVER_WEG = "server_weg"
ERROR_CLASS_KAPUTT = "kaputt"
ERROR_CLASS_LEER = "leer"

# Temporaer: Probe-Run lohnt, NICHT hart deaktivieren.
TEMPORARY_CLASSES = (ERROR_CLASS_SERVER_WEG, ERROR_CLASS_BLOCKIERT)
# Dauerhaft: kommen nicht von selbst zurueck, hart deaktivieren ist korrekt.
PERMANENT_CLASSES = (ERROR_CLASS_TOT, ERROR_CLASS_KAPUTT)


def _http_status(exc) -> Optional[int]:
    """Zieht einen HTTP-Statuscode aus der Exception, falls vorhanden.

    Deckt httpx.HTTPStatusError (``exc.response.status_code``) und Adapter ab,
    die einen eigenen Fehler mit ``.status_code`` werfen.
    """
    resp = getattr(exc, "response", None)
    code = getattr(resp, "status_code", None)
    if isinstance(code, int):
        return code
    code = getattr(exc, "status_code", None)
    return code if isinstance(code, int) else None


def classify_scraper_error(exc) -> str:
    """Leitet aus einer Exception eine Scraper-Fehlerklasse ab.

    Defensiv: Netzwerk-/HTTP-Signale werden gezielt erkannt, alles andere gilt
    als ``kaputt`` (ein echter, nicht eingeordneter Fehler liegt am
    wahrscheinlichsten am Adapter/Code).
    """
    if exc is None:
        return ERROR_CLASS_KAPUTT

    name = type(exc).__name__.lower()
    module = (type(exc).__module__ or "").lower()

    # Timeouts (concurrent.futures.TimeoutError, httpx.*Timeout, socket.timeout)
    if "timeout" in name:
        return ERROR_CLASS_SERVER_WEG

    # HTTP-Status auswerten
    code = _http_status(exc)
    if code is not None:
        if code in (404, 410):
            return ERROR_CLASS_TOT
        if code in (403, 429):
            return ERROR_CLASS_BLOCKIERT
        if 500 <= code < 600:
            return ERROR_CLASS_SERVER_WEG
        if 400 <= code < 500:
            # 400/401/422 ... deuten auf ein Request-/Adapter-Problem
            return ERROR_CLASS_KAPUTT

    # Verbindungs-/Netzwerk-/DNS-Fehler
    if any(tok in name for tok in (
        "connect", "transport", "network", "dns", "resolve",
        "socket", "ssl", "remotedisconnect", "remoteprotocol",
    )):
        return ERROR_CLASS_SERVER_WEG

    # httpx-Fehler ohne Status (RequestError-Basis) sind Transport-/Netzfehler
    if "httpx" in module:
        return ERROR_CLASS_SERVER_WEG

    # Fehlender/kaputter Adapter
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return ERROR_CLASS_KAPUTT

    # Default: unerwartete Exception = Parser/Code kaputt
    return ERROR_CLASS_KAPUTT


def classify_from_status(status: str, exc=None) -> Optional[str]:
    """Mappt den groben ``source_status['status']`` (+ optional Exception) auf
    eine Fehlerklasse. ``ok``/``skipped`` -> None, ``timeout`` -> server_weg,
    Fehler werden ueber die Exception klassifiziert. Defensiv fuer Altdaten:
    fehlt die Exception bei status='error', wird None geliefert (Altverhalten).
    """
    if status in ("ok", "skipped"):
        return None
    if status == "timeout":
        return ERROR_CLASS_SERVER_WEG
    if status in ("error", "fail"):
        return classify_scraper_error(exc) if exc is not None else None
    return None
