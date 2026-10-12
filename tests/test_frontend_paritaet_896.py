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
    # #1103: die Liste steht in services/bewerbung_status.py; gelesen wird
    # der Wert, nicht die Schreibweise im Quelltext.
    from bewerbungs_assistent.tools.bewerbungen import VALID_STATUSES
    assert VALID_STATUSES, "VALID_STATUSES leer"
    return set(VALID_STATUSES)


def _reiter_ids():
    text = (FRONTEND / "lib" / "einstellungenReiter.js").read_text(encoding="utf-8")
    return re.findall(r'id:\s*"([a-z_]+)"', text)


def _settings_reiterleiste_ids():
    # #1170 U17: die Einstellungen haben EINE Navigation - die Reiter der Seite (G70: Grundlagen und Erweitert, beide aus
    # lib/einstellungenReiter.js). Dieselben 16 Namen noch einmal in der Seitenleiste verdraengten den Elwosa-Chat.
    seite = (FRONTEND / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8")
    assert 'tabs.filter((r) => r.gruppe === "grundlagen")' in seite
    assert 'tabs.filter((r) => r.gruppe === "erweitert")' in seite
    app = (FRONTEND / "App.jsx").read_text(encoding="utf-8")
    assert "items: SETTINGS_REITER.map" not in app, "die Seitenleiste fuehrt wieder eine zweite Navigation (#1170 U17)"
    return _reiter_ids()


def _settings_page_tab_ids():
    text = (FRONTEND / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8")
    assert "const tabs = SETTINGS_REITER;" in text, "SettingsPage liest die Liste nicht"
    return _reiter_ids()


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


def test_settings_reiterleiste_deckt_alle_tabs_ab():
    """Jeder Tab der Einstellungen ist ueber die Reiterleiste der Seite erreichbar - und jeder Reiter hat Inhalt."""
    leiste = _settings_reiterleiste_ids()
    tabs = _settings_page_tab_ids()
    assert len(tabs) >= 8, f"Tab-Liste unerwartet klein: {tabs}"
    assert set(leiste) == set(tabs)
    seite = (FRONTEND / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8")
    inhalte = set(re.findall(r'settingsTab === "([a-z_]+)"', seite))
    assert set(tabs) == inhalte, f"Reiter ohne Inhalt oder Inhalt ohne Reiter: {set(tabs) ^ inhalte}"
