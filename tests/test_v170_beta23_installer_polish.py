"""Tests fuer v1.7.0-beta.23 — Installer-Polish nach User-Test in beta.22.

Findings:
- Nach Installation startet PBP nicht automatisch (oder User merkt es nicht).
- Keine eindeutige Erfolgsmeldung am Ende — User unsicher ob fertig.

Fix:
- Health-Check auf http://localhost:8200/ nach Dashboard-Start (max 30s).
- Browser explizit oeffnen wenn Health gruen.
- Erfolgsmeldung NACH dem Auto-Start, nicht davor — mit klarer
  Status-Anzeige ("LAEUFT" vs. "PRUEFEN").
- Dashboard starten.bat bleibt bei Fehler offen, schliesst nicht stumm.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_installer_has_health_check():
    """Installer prueft Port 8200 mit PowerShell + Invoke-WebRequest."""
    bat = (PROJECT_ROOT / "INSTALLIEREN.bat").read_text(encoding="cp1252", errors="replace")
    assert "Invoke-WebRequest" in bat
    assert "localhost:8200" in bat
    assert "DASH_OK" in bat


def test_installer_opens_browser_explicitly():
    """Wenn Dashboard laeuft, wird der Browser explizit geoeffnet."""
    bat = (PROJECT_ROOT / "INSTALLIEREN.bat").read_text(encoding="cp1252", errors="replace")
    assert 'start "" "http://localhost:8200/"' in bat


def test_installer_success_box_after_autostart():
    """Erfolgs-Box steht NACH dem Auto-Start (Zeilen-Reihenfolge)."""
    bat = (PROJECT_ROOT / "INSTALLIEREN.bat").read_text(encoding="cp1252", errors="replace")
    autostart_pos = bat.find("Starte PBP automatisch")
    success_pos = bat.find("E R F O L G R E I C H")
    assert autostart_pos > 0 and success_pos > 0
    assert autostart_pos < success_pos, (
        "Auto-Start muss VOR der Erfolgs-Box stehen — sonst sieht der User "
        "die Erfolgs-Box bevor klar ist ob das Dashboard wirklich laeuft."
    )


def test_installer_shows_dashboard_status_in_success():
    """Erfolgs-Box zeigt klar ob Dashboard laeuft oder geprueft werden muss."""
    bat = (PROJECT_ROOT / "INSTALLIEREN.bat").read_text(encoding="cp1252", errors="replace")
    assert "[LAEUFT]" in bat
    assert "[PRUEFEN" in bat or "[!!]" in bat


def test_dashboard_starten_bat_keeps_window_open_on_error():
    """Dashboard starten.bat schliesst nicht stumm bei Python-Fehler."""
    bat = (PROJECT_ROOT / "Dashboard starten.bat").read_text(encoding="cp1252", errors="replace")
    assert "EnableDelayedExpansion" in bat
    assert "errorlevel! neq 0" in bat or "errorlevel% neq 0" in bat
    # pause-Aufruf nach dem Python-Aufruf
    py_pos = bat.find("start_dashboard.py")
    pause_pos = bat.rfind("pause")
    assert py_pos > 0 and pause_pos > py_pos


def test_dashboard_starten_bat_validates_python_path():
    """Dashboard starten.bat checkt vorab ob python.exe existiert."""
    bat = (PROJECT_ROOT / "Dashboard starten.bat").read_text(encoding="cp1252", errors="replace")
    assert 'if not exist "%PYTHON%"' in bat
    assert 'INSTALLIEREN.bat' in bat  # Hinweis im Fehler-Pfad
