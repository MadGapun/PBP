# -*- coding: utf-8 -*-
"""Guard-Test fuer #846: jeder Tab aus TAB_CONFIG muss in PAGE_IDS stehen.

Hintergrund: 'kontakte' (v1.7.0-beta.21) und 'aufgaben' (v1.7.12, #846)
wurden beim Anlegen neuer Tabs in PAGE_IDS vergessen. Folge war jeweils
derselbe 2-Klick-Bug: parsePageFromHash() verwirft den unbekannten Hash,
der hashchange-Listener springt aufs Dashboard zurueck, Deep-Links und
Reloads landen falsch. Dieser Test macht den Fehler beim naechsten neuen
Tab unmoeglich — er liest BEIDE Quelldateien, wie es die #765-Paritaets-
Tests fuer jobLink vormachen.
"""

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "src"


def _tab_config_ids():
    text = (FRONTEND / "App.jsx").read_text(encoding="utf-8")
    m = re.search(r"const TAB_CONFIG = \[(.*?)\n\];", text, re.S)
    assert m, "TAB_CONFIG nicht in App.jsx gefunden"
    return re.findall(r'id:\s*"([a-z_]+)"', m.group(1))


def _page_ids():
    text = (FRONTEND / "utils.js").read_text(encoding="utf-8")
    m = re.search(r"export const PAGE_IDS = \[(.*?)\n\];", text, re.S)
    assert m, "PAGE_IDS nicht in utils.js gefunden"
    return re.findall(r'"([a-z_]+)"', m.group(1))


def test_jeder_tab_ist_in_page_ids():
    tabs = _tab_config_ids()
    pages = _page_ids()
    assert len(tabs) >= 10, f"TAB_CONFIG unerwartet klein: {tabs}"
    fehlend = [t for t in tabs if t not in pages]
    assert not fehlend, (
        f"Tabs ohne PAGE_IDS-Eintrag (2-Klick-Bug, #846): {fehlend} — "
        f"in frontend/src/utils.js nachtragen"
    )


def test_aufgaben_ist_in_page_ids():
    """Der konkrete #846-Fall, explizit festgeschrieben."""
    assert "aufgaben" in _page_ids()
