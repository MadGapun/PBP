"""Ein Start, der am belegten Port endet, ist kein Fehlstart der Fassung (#1290).

Der Startbaustein zaehlt jeden Start, der nie `start_bestaetigen()` ruft, als "Start ohne Bestaetigung" und schaltet nach
`MAX_UNBESTAETIGT` solchen Starts auf die vorige Fassung zurueck (`waehle_fassung`). Am 30.10.2026 hielt ein haengender
eigener Prozess den Port 8200; zwei Starts ueber die Desktop-Verknuepfung endeten dort, PBP lief nie an, und der dritte
Start stufte 1.8.0 auf 1.8.0-rc.4 zurueck, obwohl die Fassung in Ordnung war.

`start_ohne_schuld()` nimmt diesen Start aus der Zaehlung: der Zaehler `start.versuche` dieser Fassung geht auf hoechstens 1.
Es bestaetigt NIE (`bestaetigt` bleibt, wie es ist): die Fassung ist hier nicht bewiesen gut, nur nicht schuld.

Der Startbaustein bleibt unveraendert (FORMAT = 1); dieses Modul benutzt nur seine oeffentlichen Funktionen. Es wirkt nur bei
einem Start ueber den Startbaustein (`PBP_APP_DIR` und `PBP_FASSUNG` gesetzt).
"""
from __future__ import annotations

from datetime import datetime, timezone

import bewerbungs_assistent_boot as _boot

from . import layout


def start_ohne_schuld(grund: str = "") -> bool:
    """Setzt den Startzaehler dieser Fassung auf hoechstens 1. True, wenn er geaendert wurde.

    Fehler (kein Programmordner, Statusdatei nicht beschreibbar) ergeben False und nie eine Ausnahme: ein Start, der am Port
    endet, soll an der Zaehlung nicht auch noch scheitern.
    """
    try:
        app, fassung = layout.programmordner(), layout.laufende_fassung()
        if app is None or fassung is None:
            return False
        status = _boot.lese_status(app)
        start = status.get("start") if isinstance(status.get("start"), dict) else {}
        if start.get("version") != fassung:
            return False
        try:
            versuche = int(start.get("versuche") or 1)
        except (TypeError, ValueError):
            versuche = 1
        if versuche <= 1:
            return False
        start["versuche"] = 1
        start["ohne_schuld"] = {"grund": str(grund)[:200], "zeit": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        status["start"] = start
        _boot.schreibe_status(app, status)
        return True
    except Exception:  # noqa: BLE001
        return False
