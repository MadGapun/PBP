# -*- coding: utf-8 -*-
"""Paritaets-Guards fuer #896 — Frontend-Drift mechanisch verhindern.

Zwei Quellen-Paare, die beim Anlegen neuer Werte auseinanderliefen
(dieselbe Fehlerklasse wie PAGE_IDS/#846, gleiche Absicherung wie
test_frontend_page_ids_846.py):

1. STATUS_OPTIONS (frontend/src/utils.js) bot mit 'entwurf' und
   'warte_auf_rueckmeldung' Status an, die die Backend-Whitelist
   (tools/bewerbungen.py VALID_STATUSES) ablehnt bzw. still ummappt.
2. Die Einstellungen-Subnavigation (App.jsx) listete 'erweiterungen'
   und 'bewerten' nicht, obwohl die Tabs in SettingsPage.jsx existieren.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend" / "src"


def _status_options_values():
    text = (FRONTEND / "utils.js").read_text(encoding="utf-8")
    m = re.search(r"export const STATUS_OPTIONS = \[(.*?)\n\];", text, re.S)
    assert m, "STATUS_OPTIONS nicht in utils.js gefunden"
    return re.findall(r'value:\s*"([a-z_]+)"', m.group(1))


def _backend_valid_statuses():
    text = (ROOT / "src" / "bewerbungs_assistent" / "tools" /
            "bewerbungen.py").read_text(encoding="utf-8")
    m = re.search(r"VALID_STATUSES = \{(.*?)\}", text, re.S)
    assert m, "VALID_STATUSES nicht in tools/bewerbungen.py gefunden"
    return set(re.findall(r'"([a-z_]+)"', m.group(1)))


def _settings_subnav_ids():
    # 'sidebarSubNavigation' wird je Seite neu zugewiesen (profil, kalender,
    # einstellungen) — die "settings-"-IDs existieren aber nur im
    # Einstellungen-Block, deshalb reicht ein Datei-weites findall.
    text = (FRONTEND / "App.jsx").read_text(encoding="utf-8")
    ids = re.findall(r'id:\s*"settings-([a-z_]+)"', text)
    assert ids, "Einstellungen-Subnavigation nicht in App.jsx gefunden"
    return ids


def _settings_page_tab_ids():
    text = (FRONTEND / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8")
    m = re.search(r"const tabs = \[(.*?)\n\s*\];", text, re.S)
    assert m, "tabs-Liste nicht in SettingsPage.jsx gefunden"
    return re.findall(r'id:\s*"([a-z_]+)"', m.group(1))


def test_status_optionen_sind_backend_gueltig():
    """Kein Dropdown-Wert, den das Backend ablehnt oder still ummappt."""
    frontend = _status_options_values()
    backend = _backend_valid_statuses()
    assert len(backend) >= 10, f"Whitelist unerwartet klein: {backend}"
    tote = [s for s in frontend if s not in backend]
    assert not tote, (
        f"STATUS_OPTIONS enthaelt Backend-unbekannte Status: {tote} — "
        f"aus frontend/src/utils.js entfernen oder Whitelist erweitern"
    )


def test_settings_subnav_deckt_alle_tabs_ab():
    """Jeder Tab der Einstellungen ist ueber die Sidebar erreichbar."""
    subnav = _settings_subnav_ids()
    tabs = _settings_page_tab_ids()
    assert len(tabs) >= 8, f"Tab-Liste unerwartet klein: {tabs}"
    fehlend = [t for t in tabs if t not in subnav]
    assert not fehlend, (
        f"Einstellungen-Tabs ohne Sidebar-Eintrag: {fehlend} — "
        f"in App.jsx (sidebarSubNavigation) nachtragen"
    )
    # Gegenrichtung: kein Sidebar-Eintrag auf einen Tab, den es nicht gibt
    geister = [s for s in subnav if s not in tabs]
    assert not geister, f"Sidebar-Eintraege ohne Tab: {geister}"
