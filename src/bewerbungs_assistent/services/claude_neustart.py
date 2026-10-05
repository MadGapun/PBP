"""Claude Desktop neu starten, damit es PBP als Werkzeug-Server lädt (#1149 Punkt 10).

`start_dashboard.py` (die Desktop-Verknüpfung) fragte bei laufendem Claude Desktop
„Claude jetzt neu starten? [J/n]“ — mit Vorgabe JA — und beendete Claude danach mit
`taskkill /F`. Drei Dinge daran waren falsch:

* Ein bloßes Enter beendete eine fremde Anwendung gewaltsam: noch nicht abgeschickter Text geht
  verloren, eine laufende Antwort bricht ab. Die Vorgabe ist jetzt NEIN, und die Frage sagt, was
  verloren geht.
* Die Prüfung `"Claude.exe" in stdout` unterschied Groß- und Kleinschreibung; `tasklist` schreibt
  den Namen, wie die Datei heißt. Wo er anders geschrieben war, kam die Frage nie.
* Neu gestartet wurde nur aus zwei festen Pfaden, sonst schweigend gar nicht: Claude war beendet,
  und niemand sagte, dass man es selbst wieder öffnen muss. Jetzt gelten dieselben Pfade wie im
  Installer, dazu die Store-Fassung (über das Windows-Paketsystem); gelingt der Start trotzdem
  nicht, steht es im Fenster.

Alles, was die Außenwelt berührt, wird hereingereicht (Befehle, Eingabe, Ausgabe, Dateiprüfung),
damit die Tests ohne ein echtes Claude laufen.
"""
from __future__ import annotations

import logging
import ntpath
import os
import subprocess
import sys
import threading
import time

logger = logging.getLogger(__name__)

_OHNE_FENSTER = 0x08000000      # CREATE_NO_WINDOW
_ABGELOEST = 0x00000008         # DETACHED_PROCESS

#: Wo Claude Desktop unter Windows liegen kann (dieselben Orte wie in INSTALLIEREN.bat).
WINDOWS_ORTE = (
    ("LOCALAPPDATA", "Programs", "claude-desktop", "Claude.exe"),
    ("LOCALAPPDATA", "AnthropicClaude", "Claude.exe"),
    ("LOCALAPPDATA", "Programs", "Claude", "Claude.exe"),
    ("LOCALAPPDATA", "anthropic-claude", "Claude.exe"),
    ("PROGRAMFILES", "Claude", "Claude.exe"),
    ("PROGRAMFILES(X86)", "Claude", "Claude.exe"),
)

#: Die Store-Fassung liegt in einem geschützten Ordner und wird über das Paketsystem gestartet
#: (dieselbe Abfrage wie `:start_claude_appx` im Installer; sie meldet „ok“, wenn sie etwas startete).
STORE_START = (
    "$p = @(Get-AppxPackage -Name '*Claude*' -ErrorAction SilentlyContinue)[0]; "
    "if ($p) { $id = @((Get-AppxPackageManifest $p).Package.Applications.Application.Id)[0]; "
    "if ($id) { Start-Process ('shell:AppsFolder\\' + $p.PackageFamilyName + '!' + $id); 'ok' } }"
)

JA = ("j", "ja", "y", "yes")


def claude_laeuft(plattform: str, run=subprocess.run) -> bool:
    """Läuft Claude Desktop gerade? (Windows und macOS; sonst nein.)"""
    if plattform == "win32":
        r = run(["tasklist", "/FI", "IMAGENAME eq Claude.exe", "/NH"],
                capture_output=True, text=True, timeout=5, creationflags=_OHNE_FENSTER)
        return "claude.exe" in (r.stdout or "").lower()
    if plattform == "darwin":
        r = run(["pgrep", "-x", "Claude"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    return False


def windows_pfad(umgebung, ist_datei=os.path.isfile) -> str | None:
    """Der erste Ort, an dem eine `Claude.exe` liegt.

    Es sind Windows-Pfade, also mit `ntpath` zusammengesetzt: auf Windows ist das dasselbe wie `os.path`,
    auf einem anderen System (die CI laeuft unter Linux) entstuende sonst "C:\\...\\Local/Programs/...".
    """
    for teile in WINDOWS_ORTE:
        wurzel = umgebung.get(teile[0], "")
        if not wurzel:
            continue
        pfad = ntpath.join(wurzel, *teile[1:])
        if ist_datei(pfad):
            return pfad
    return None


def neustart_anbieten(plattform: str | None = None, *, frage=input, ausgabe=print,
                      run=subprocess.run, start=subprocess.Popen, pause=time.sleep,
                      umgebung=None, ist_datei=os.path.isfile, ist_ordner=os.path.isdir) -> str:
    """Fragt, ob Claude Desktop neu gestartet werden soll, und tut es nur auf ein ausdrückliches Ja.

    Rückgabe (für Tests und Protokoll): `laeuft_nicht`, `abgelehnt`, `beendet_und_gestartet`,
    `beendet_ohne_start`.
    """
    plattform = plattform or sys.platform
    umgebung = os.environ if umgebung is None else umgebung
    if not claude_laeuft(plattform, run):
        return "laeuft_nicht"

    ausgabe()
    ausgabe("  Claude Desktop läuft bereits.")
    ausgabe("  Damit Claude PBP als Werkzeug lädt, muss es einmal neu gestartet werden.")
    ausgabe("  ACHTUNG: Dabei geht Text verloren, den du in Claude noch nicht abgeschickt hast,")
    ausgabe("  und eine laufende Antwort wird abgebrochen.")
    ausgabe()
    antwort = frage("  Claude jetzt neu starten? [j/N]: ").strip().lower()
    if antwort not in JA:
        ausgabe("  Gut, Claude bleibt offen. Das Dashboard läuft trotzdem.")
        ausgabe("  Zum Verbinden später Claude selbst beenden und wieder öffnen.")
        return "abgelehnt"

    if plattform == "win32":
        run(["taskkill", "/IM", "Claude.exe", "/F"], capture_output=True, timeout=10, creationflags=_OHNE_FENSTER)
        pause(2)
        exe = windows_pfad(umgebung, ist_datei)
        if exe:
            start([exe], start_new_session=True, creationflags=_ABGELOEST)
            ausgabe("  Claude Desktop wird gestartet...")
            pause(3)
            return "beendet_und_gestartet"
        try:
            r = run(["powershell", "-NoProfile", "-Command", STORE_START],
                    capture_output=True, text=True, timeout=30, creationflags=_OHNE_FENSTER)
            if "ok" in (r.stdout or ""):
                ausgabe("  Claude Desktop wird gestartet...")
                pause(3)
                return "beendet_und_gestartet"
        except Exception:  # noqa: BLE001 — der Hinweis unten sagt, was zu tun ist
            pass
    elif plattform == "darwin":
        run(["pkill", "-x", "Claude"], capture_output=True, timeout=5)
        pause(2)
        app = "/Applications/Claude.app"
        if ist_ordner(app):
            start(["open", app], start_new_session=True)
            ausgabe("  Claude Desktop wird gestartet...")
            pause(3)
            return "beendet_und_gestartet"

    ausgabe("  Claude Desktop wurde beendet, ließ sich aber nicht automatisch starten.")
    ausgabe("  Bitte öffne es jetzt selbst wieder (Startmenü beziehungsweise Programme).")
    return "beendet_ohne_start"


def neustart_im_hintergrund(*, warte: float = 4.0, ist_konsole=None, **kwargs) -> threading.Thread | None:
    """Stellt die Frage aus `neustart_anbieten` in einem eigenen Thread — der Server startet, ohne auf die Antwort zu warten.

    Vorher stand `input()` VOR dem Start des Servers. Das Fenster liegt hinter anderen, niemand antwortet, der Server läuft
    nicht, der Installer wartet 60 Sekunden und öffnet eine Seite „Verbindung verweigert“ (Praxisprobe 1.8, 05.10.2026,
    frischer Windows-11-Rechner mit laufendem Claude Desktop — der Normalfall). Jetzt kommt die Frage erst, wenn das
    Dashboard läuft; die Vorgabe bleibt NEIN, und die Oberfläche führt ohnehin durch die Schritte.

    Ohne Konsole (kein Fenster, in dem man antworten könnte) wird gar nicht erst gefragt. Rückgabe: der Thread oder None.
    """
    if ist_konsole is None:
        def ist_konsole() -> bool:
            return sys.stdin is not None and sys.stdin.isatty()
    if not ist_konsole():
        return None
    pause = kwargs.get("pause", time.sleep)

    def _lauf() -> None:
        try:
            pause(warte)
            neustart_anbieten(**kwargs)
        except Exception as exc:  # noqa: BLE001 — eine verpasste Frage darf den Server nie stören
            logger.warning("Claude-Check fehlgeschlagen: %s", exc)

    faden = threading.Thread(target=_lauf, name="claude-neustart-frage", daemon=True)
    faden.start()
    return faden
