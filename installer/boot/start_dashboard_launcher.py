"""PBP Dashboard-Starter — ändert sich nie (Auto-Update, #1093).

Diese Datei liegt als `start_dashboard.py` im Programmordner (neben `python`, `boot` und `versions`).
Sie macht nichts weiter, als den Startbaustein zu laden; der waehlt die aktuelle Fassung und startet deren
`start_dashboard.py`. So bleibt die Verknuepfung auf dem Desktop (`Dashboard starten.bat`) fuer immer
gueltig, auch wenn Updates neue Fassungen in neue Ordner legen.

Fehler dieser Datei ausschliesslich hier suchen, wenn das Dashboard gar nicht startet: alles andere
steht in der Fassung (`versions/<fassung>/start_dashboard.py`) und im Log (`data/logs/pbp.log`).
"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("PBP_APP_DIR", HIER)
sys.path.insert(0, os.path.join(HIER, "boot"))

from bewerbungs_assistent_boot import starte  # noqa: E402

starte("dashboard")
