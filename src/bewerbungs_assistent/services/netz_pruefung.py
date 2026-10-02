"""Ist das Internet erreichbar? (#1141)

Ohne Netz gaben alle 24 getesteten Quellen bei einem Verbindungsfehler eine
leere Liste zurueck. Die Suche konnte „keine Treffer“ nicht von „Netz weg“
unterscheiden und meldete „8 von 8 Quellen ok“ und „Fertig — keine neuen
Stellen“; nach fuenf solchen Laeufen wurden alle Quellen als „still“ pausiert.
Wer kurz offline war (WLAN, VPN, Firmenproxy), bekam den Rat, die
Suchbegriffe zu lockern — der falsche Hebel.

Diese Pruefung fragt ein paar Ziele an, die PBP ohnehin braucht, plus ein
neutrales. **Jede HTTP-Antwort, gleich mit welchem Status, heisst: das Netz
ist da.** Nur wenn KEIN Ziel antwortet, gilt PBP als offline. Sie sitzt an
zwei Stellen: vor dem Start einer Suche (`jobsuche_start.starten`) und nach
einem Lauf, der von allen Quellen nichts bekam (`job_scraper.run_search`).

Ausschalten (zum Beispiel hinter einer Firewall, die alle vier Ziele sperrt):
Umgebungsvariable ``PBP_NETZ_PRUEFUNG=0``. Dann gilt das Netz immer als da,
und die Suche verhaelt sich wie bis v1.7.147.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

#: Ziele, die PBP ohnehin braucht (Update-Pruefung, wichtigste Quelle), dazu
#: zwei neutrale. Mehrere und verschiedene, damit eine einzelne Sperre nicht
#: wie „kein Netz“ aussieht.
ZIELE = (
    "https://api.github.com",
    "https://www.arbeitsagentur.de",
    "https://www.google.com",
    "https://www.cloudflare.com",
)
TIMEOUT_S = 3.0
#: Eine Bejahung gilt so lange; eine Verneinung wird NICHT gemerkt — wer
#: gerade das WLAN wieder verbunden hat, soll nicht 20 Sekunden warten.
MERKEN_S = 20.0

MELDUNG_START = (
    "Keine Verbindung zum Internet — die Jobsuche wurde nicht gestartet. "
    "Prüfe WLAN, VPN oder Proxy und starte sie dann erneut. An deinen "
    "Quellen und Stellen hat sich nichts geändert."
)
MELDUNG_LAUF = (
    "Keine Verbindung zum Internet — die Suche hat nichts abrufen können. "
    "Das heißt nicht, dass es keine neuen Stellen gibt, und an deinen "
    "Suchbegriffen liegt es auch nicht. Prüfe WLAN, VPN oder Proxy und "
    "starte die Suche erneut; deine Quellen bleiben, wie sie waren."
)

_lock = threading.Lock()
_stand: dict = {"zeit": 0.0, "ja": False}


def _aus() -> bool:
    return os.environ.get("PBP_NETZ_PRUEFUNG", "").strip().lower() in ("0", "aus", "false", "nein")


def _anfragen(url: str, timeout: float) -> bool:
    """True, wenn das Ziel mit irgendeiner HTTP-Antwort geantwortet hat."""
    import httpx
    try:
        httpx.head(url, timeout=timeout, follow_redirects=False)
        return True
    except Exception as exc:  # noqa: BLE001 — jeder Fehler heisst "nicht erreicht"
        logger.debug("Netzpruefung: %s nicht erreicht (%s)", url, exc)
        return False


def erreichbar(timeout: float = TIMEOUT_S, ziele=None) -> bool:
    """Antwortet mindestens ein Ziel? Bricht beim ersten Treffer ab."""
    if _aus():
        return True
    jetzt = time.monotonic()
    with _lock:
        if _stand["ja"] and jetzt - _stand["zeit"] < MERKEN_S:
            return True
    ziele = tuple(ziele or ZIELE)
    pool = ThreadPoolExecutor(max_workers=len(ziele), thread_name_prefix="netzpruefung")
    try:
        futures = [pool.submit(_anfragen, z, timeout) for z in ziele]
        for f in as_completed(futures):
            if f.result():
                with _lock:
                    _stand["ja"], _stand["zeit"] = True, time.monotonic()
                return True
    finally:
        # Nicht auf die uebrigen warten: nach dem ersten Treffer ist die
        # Antwort da, und bei „kein Netz“ sind ohnehin alle fertig.
        pool.shutdown(wait=False, cancel_futures=True)
    with _lock:
        _stand["ja"] = False
    logger.warning("Netzpruefung: keines von %d Zielen antwortet — PBP ist offline.", len(ziele))
    return False


def vergessen() -> None:
    """Merkt sich nichts mehr (fuer Tests)."""
    with _lock:
        _stand["ja"], _stand["zeit"] = False, 0.0
