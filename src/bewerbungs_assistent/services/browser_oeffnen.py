"""Den Browser erst öffnen, wenn das Dashboard antwortet (Praxisprobe 1.8, PP15).

`start_dashboard.py` (die Desktop-Verknüpfung und das Fenster, das der Installer öffnet) rief den Browser auf, BEVOR der Server lauschte.
Auf einem frischen Rechner braucht der erste Start länger (Virenscanner prüft die frisch kopierten Dateien, die Datenbank wird
angelegt): Chrome kam zuerst an und zeigte „Verbindung verweigert“ — bis jemand neu lud. Dazu öffnete der Installer, sobald das
Dashboard lief, den Standardbrowser noch einmal, ein zweiter Tab (und je nach Rechner ein zweiter Browser).

Jetzt wartet ein Hintergrund-Thread, bis das Dashboard auf `/api/health` als PBP antwortet, und öffnet erst dann.

Abgrenzung: `dashboard_halter` hält fest, WER das Dashboard hat, und kann prüfen, ob an einem Port ein PBP antwortet (`ist_pbp`); dieses
Modul benutzt nur diese Prüfung. `browser_handoff` ist die Brücke zu Quellen, die nur im Browser liefern, und hat damit nichts zu tun.

Alles, was die Außenwelt berührt, wird hereingereicht (Probe, Uhr, Pause, Öffner), damit die Tests ohne Server und ohne Browser laufen.
"""
from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

#: So lange darf ein erster Start dauern, bevor trotzdem geöffnet wird (der Mensch sieht dann wenigstens, dass etwas fehlt).
FRIST_S = 90.0
#: Pause zwischen zwei Proben. Unter Windows meldet ein geschlossener Port „abgelehnt“ erst nach rund einer Sekunde; die Pause kommt dazu.
TAKT_S = 0.3


def _antwortet(port: int) -> bool:
    from .dashboard_halter import ist_pbp
    return ist_pbp(port, timeout=1.0)


def warte_bis_bereit(port: int, *, frist: float = FRIST_S, takt: float = TAKT_S, probe=None,
                     uhr=time.monotonic, pause=time.sleep) -> bool:
    """True, sobald auf dem Port ein PBP antwortet; False, wenn `frist` Sekunden vergehen."""
    probe = probe or _antwortet
    ende = uhr() + frist
    while True:
        try:
            if probe(port):
                return True
        except Exception:  # noqa: BLE001 — eine fehlgeschlagene Probe heißt nur: noch nicht
            pass
        if uhr() >= ende:
            return False
        pause(takt)


def oeffnen_sobald_bereit(url: str, port: int, oeffnen, *, frist: float = FRIST_S, **kwargs) -> threading.Thread:
    """Startet einen Daemon-Thread, der `oeffnen(url)` ruft, sobald das Dashboard antwortet. Rückgabe: der Thread.

    Antwortet es innerhalb der Frist nicht, wird trotzdem geöffnet (und gewarnt): ein Mensch, der nichts sieht, ist schlimmer dran
    als einer, der neu laden muss. Ein Fehler beim Öffnen stört den Server nie. Der Thread ist ein Daemon: Beendet sich der Prozess
    vorher (Startfehler), ist auch das Warten vorbei und es öffnet sich nichts.
    """
    def _lauf() -> None:
        try:
            if not warte_bis_bereit(port, frist=frist, **kwargs):
                logger.warning("Das Dashboard antwortet nach %.0f Sekunden noch nicht - der Browser wird trotzdem geoeffnet", frist)
            oeffnen(url)
        except Exception as exc:  # noqa: BLE001 — ein nicht geöffneter Browser darf den Server nie stören
            logger.warning("Der Browser liess sich nicht oeffnen: %s", exc)

    # Bewusst kein "pbp-"-Name: die Teardown-Prüfung der Suite wartet auf jeden Thread mit diesem Anfang bis zu 15 Sekunden.
    faden = threading.Thread(target=_lauf, name="browser-oeffnen-wartet", daemon=True)
    faden.start()
    return faden
