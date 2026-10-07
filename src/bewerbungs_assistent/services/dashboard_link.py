"""Der Weg zurueck ins Dashboard (H31, #1087 G13).

Kein Werkzeug lieferte einen Link auf die Stelle, Bewerbung oder Aufgabe,
ueber die es gerade sprach; `localhost:8200` stand an acht Stellen fest
und ignorierte `BA_DASHBOARD_PORT`, und der Kalender-Export verlinkte
`/bewerbungen?id=`, eine Route, die es nicht gibt.

Das Dashboard liest den Reiter aus dem Hash (`#bewerbungen`) und seit H31
eine Kennung dahinter (`#bewerbungen/<id>`, `#stellen/<hash>`). Dieses
Modul baut beides aus einer Quelle; die Reiternamen sind die echten
Seiten-IDs aus `frontend/src/utils.js` (ein Test haelt beide gleich).
"""
from __future__ import annotations

import os
from urllib.parse import quote

REITER = ("dashboard", "profil", "suche", "dokumente", "stellen", "bewerbungen",
          "kontakte", "aufgaben", "kalender", "statistiken", "einstellungen")


def port() -> int:
    try:
        return int(os.environ.get("BA_DASHBOARD_PORT", "8200"))
    except ValueError:
        return 8200


def basis() -> str:
    return f"http://localhost:{port()}"


def hash_ziel(reiter: str, kennung: str = "") -> str:
    """Der Hash-Teil eines Links (`#bewerbungen/<id>`, `#stellen/<hash>`) — OHNE Rechner und Port.

    Das ist die EINE Form, die das Dashboard liest (`parseHashZiel` in `frontend/src/utils.js`). Sie gilt fuer Links, die
    Claude nennt (`dashboard_link`), und fuer die Treffer der Suche im Dashboard (#1177): die Suche lieferte bis v1.7.154 die
    Form `#bewerbungen?id=<id>`, die nie jemand las — ein Klick auf einen Treffer tat nichts.
    """
    if reiter not in REITER:
        raise ValueError(f"Unbekannter Reiter: {reiter}")
    ziel = f"#{reiter}"
    if kennung:
        # Eine gespeicherte Stellenkennung traegt das Profil als Praefix
        # (`<profil>:<hash>`); das Dashboard kennt die oeffentliche Form.
        kennung = str(kennung).split(":", 1)[-1]
        ziel += "/" + quote(kennung, safe="")
    return ziel


def dashboard_link(reiter: str = "dashboard", kennung: str = "") -> str:
    """Link auf einen Reiter, optional mit Kennung (Bewerbung, Stelle)."""
    return basis() + "/" + hash_ziel(reiter, kennung)


def firma_link(name_oder_id: str) -> str:
    """Link auf die Firmen-Ansicht (Kontakte > Firmen, #1080): mit der Kennung eines Firmen-Eintrags (fi_...) oder einem Namen.

    Ein Name steht hinter `firma:`; die Kennung traegt das Dashboard sonst als Profil-Praefix (`<profil>:<hash>`) ab, deshalb
    wird dieser Link nicht ueber `dashboard_link` gebaut.
    """
    wert = str(name_oder_id or "").strip()
    if not wert:
        return basis() + "/#kontakte"
    ziel = wert if wert.startswith("fi_") else "firma:" + wert
    return basis() + "/#kontakte/" + quote(ziel, safe="")
