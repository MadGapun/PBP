"""Praxisprobe auf einem frischen Windows (#1294): Installer, Port-Selbsthilfe, Update, Deinstallation.

Laeuft in der CI auf `windows-latest` (Workflow `.github/workflows/windows-probe.yml`), nie auf einem Rechner mit echten
Daten: der Installer schreibt nach `%LOCALAPPDATA%\\BewerbungsAssistent`, der Deinstaller loescht dort ALLES.

Jeder Schritt prueft den INHALT (Antwort von `/api/health`, Dateien, Registry, Prozesse), nie nur eine Erfolgsmeldung (8g).
Nur Standardbibliothek; Ausgaben gehen zusaetzlich nach `--protokolle` (Artefakt des Laufs).

    python scripts/windows_probe.py installieren --ordner <entpackter Stand> [--erwartet 1.8.1]
    python scripts/windows_probe.py haenger
    python scripts/windows_probe.py fremd [--runden 2 --abstand 95]
    python scripts/windows_probe.py update-vorbereiten   # laedt das ZIP der vorigen stabilen Fassung, gibt den Ordner aus
    python scripts/windows_probe.py update --nach <version>
    python scripts/windows_probe.py deinstallieren
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

PORT = 8200
REPO = "MadGapun/PBP"
BASIS = Path(os.environ.get("LOCALAPPDATA", "")) / "BewerbungsAssistent"
APP = BASIS / "app"
DATEN = BASIS / "data"
PROTOKOLLE = Path(os.environ.get("PBP_PROBE_PROTOKOLLE", Path.cwd() / "probe-protokolle"))
KEIN_FENSTER = 0x08000000
UNINSTALL_SCHLUESSEL = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PBP"


class ProbeFehler(Exception):
    pass


def melde(text: str) -> None:
    print(text, flush=True)
    PROTOKOLLE.mkdir(parents=True, exist_ok=True)
    with open(PROTOKOLLE / "probe.txt", "a", encoding="utf-8") as f:
        f.write(text + "\n")


def pruefe(bedingung: bool, text: str) -> None:
    if not bedingung:
        raise ProbeFehler(text)
    melde(f"  [OK] {text}")


def lies(pfad: Path) -> str:
    """Ausgabe von cmd/Python: je nach Umleitung cp1252, cp850 oder UTF-8 - fuer die Suche reicht ein Lesen ohne Abbruch."""
    roh = pfad.read_bytes() if pfad.exists() else b""
    try:
        return roh.decode("utf-8")
    except UnicodeDecodeError:
        return roh.decode("cp1252", errors="replace")


# ── Dashboard und Port ──────────────────────────────────────────────────────────────────

def health(timeout: float = 5.0) -> tuple[str, dict | None]:
    """('pbp', daten) | ('keine_antwort', None) | ('fremd', None) | ('frei', None) - dieselben Faelle wie dashboard_halter."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=timeout) as r:
            daten = json.loads(r.read().decode("utf-8"))
        return ("pbp", daten) if isinstance(daten, dict) and "pbp_version" in daten else ("fremd", None)
    except urllib.error.URLError as e:
        grund = getattr(e, "reason", None)
        if isinstance(grund, TimeoutError):
            return "keine_antwort", None
        if isinstance(grund, ConnectionRefusedError):
            return "frei", None
        return "fremd", None
    except TimeoutError:
        return "keine_antwort", None
    except (ConnectionError, ValueError, OSError):
        return "fremd", None


def warte_auf_pbp(version: str | None, frist_s: float) -> dict:
    ende = time.monotonic() + frist_s
    letzte = ""
    while time.monotonic() < ende:
        art, daten = health(timeout=3)
        letzte = art
        if art == "pbp" and (version is None or daten.get("pbp_version") == version):
            return daten
        time.sleep(2)
    raise ProbeFehler(f"Dashboard antwortet nach {frist_s:.0f} s nicht als PBP {version or ''} (zuletzt: {letzte})")


def pid_am_port() -> int | None:
    r = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, timeout=30, creationflags=KEIN_FENSTER)
    for zeile in r.stdout.decode("cp850", errors="replace").splitlines():
        teile = zeile.split()
        if len(teile) >= 5 and teile[1].endswith(f":{PORT}") and teile[3].upper() in ("LISTENING", "ABHÖREN"):
            return int(teile[4])
    return None


def lebt(pid: int) -> bool:
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    h = k.OpenProcess(0x1000, False, int(pid))          # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        k.GetExitCodeProcess(h, ctypes.byref(code))
        return code.value == 259                           # STILL_ACTIVE
    finally:
        k.CloseHandle(h)


def kommandozeile(pid: int) -> str:
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
                       capture_output=True, timeout=60, creationflags=KEIN_FENSTER)
    return r.stdout.decode("utf-8", errors="replace").strip()


def anhalten(pid: int) -> None:
    """Haelt alle Threads an (NtSuspendProcess): der Prozess haelt den Port, nimmt Verbindungen an und antwortet nie."""
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    h = k.OpenProcess(0x0800, False, int(pid))          # PROCESS_SUSPEND_RESUME
    if not h:
        raise ProbeFehler(f"Prozess {pid} laesst sich nicht oeffnen")
    try:
        status = ctypes.WinDLL("ntdll").NtSuspendProcess(h)
        if status != 0:
            raise ProbeFehler(f"NtSuspendProcess({pid}) = {status:#x}")
    finally:
        k.CloseHandle(h)


def hart_beenden(pid: int) -> None:
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=30, creationflags=KEIN_FENSTER)


def dashboard_beenden() -> None:
    """Beendet, was am Port lauscht, und wartet, bis er frei ist."""
    for _ in range(3):
        pid = pid_am_port()
        if pid is None:
            break
        hart_beenden(pid)
        for _ in range(30):
            if pid_am_port() is None:
                break
            time.sleep(1)
    pruefe(pid_am_port() is None, f"Port {PORT} ist frei")


def dashboard_starten(name: str) -> tuple[subprocess.Popen, Path]:
    """Wie die Desktop-Verknuepfung: `Dashboard starten.bat` im Programmordner, ohne Eingabe, Ausgabe in eine Datei."""
    ausgabe = PROTOKOLLE / f"dashboard-{name}.txt"
    PROTOKOLLE.mkdir(parents=True, exist_ok=True)
    # Ungepuffert: in eine Datei umgeleitet puffert Python `print` blockweise, und ein laufendes Dashboard leert den Puffer nie.
    env = {**os.environ, "PBP_KEIN_BROWSER": "1", "PYTHONUNBUFFERED": "1"}
    # Eine DATEI, keine Leitung: ein Enkelprozess mit geerbtem Ende haelt sonst den Aufrufer fest (#1281).
    with open(ausgabe, "wb") as f:
        proc = subprocess.Popen(["cmd", "/c", str(APP / "Dashboard starten.bat")], cwd=str(APP), env=env,
                                stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT,
                                creationflags=KEIN_FENSTER | subprocess.CREATE_NEW_PROCESS_GROUP)
    return proc, ausgabe


def aktuell() -> str:
    pfad = APP / "aktuell.txt"
    return pfad.read_text(encoding="utf-8").strip() if pfad.exists() else ""


def log_tail(n: int = 60) -> str:
    pfad = DATEN / "logs" / "pbp.log"
    return "\n".join(lies(pfad).splitlines()[-n:])


# ── Installieren ────────────────────────────────────────────────────────────────────────

def _registry_version() -> str | None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_SCHLUESSEL) as s:
            return str(winreg.QueryValueEx(s, "DisplayVersion")[0])
    except OSError:
        return None


def _desktop() -> Path:
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                       capture_output=True, timeout=60, creationflags=KEIN_FENSTER)
    return Path(r.stdout.decode("utf-8", errors="replace").strip())


def cmd_installieren(a) -> None:
    ordner = Path(a.ordner).resolve()
    init = (ordner / "src" / "bewerbungs_assistent" / "__init__.py").read_text(encoding="utf-8")
    version = a.erwartet or re.search(r'__version__\s*=\s*"([^"]+)"', init).group(1)
    melde(f"== Installieren: {version} aus {ordner}")
    ausgabe = PROTOKOLLE / f"installer-{version}.txt"
    PROTOKOLLE.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    with open(ausgabe, "wb") as f:
        # Eingabe aus NUL: jede Frage nimmt die Vorgabe, jedes `pause` endet sofort (wie ein Mensch, der Enter drueckt).
        r = subprocess.run(["cmd", "/c", "INSTALLIEREN.bat"], cwd=str(ordner), stdin=subprocess.DEVNULL, stdout=f,
                           stderr=subprocess.STDOUT, timeout=a.frist, creationflags=KEIN_FENSTER)
    melde(f"  Installer endete nach {time.monotonic() - t0:.0f} s mit {r.returncode}")
    text = lies(ausgabe)
    log = ordner / "install_log.txt"
    if log.exists():
        shutil.copy(log, PROTOKOLLE / f"install_log-{version}.txt")
    pruefe(r.returncode == 0, "Installer endet mit 0")
    pruefe("[OK] Funktionstest bestanden" in text, "Funktionstest im Installer bestanden")
    pruefe(aktuell() == version, f"aktuell.txt nennt {version} (gelesen: {aktuell()!r})")
    pruefe((APP / "versions" / version / ".fertig").exists(), f"Fassungsordner {version} ist fertig markiert")
    pruefe(_registry_version() == version, f"Apps-Eintrag nennt {version} (gelesen: {_registry_version()!r})")
    pruefe((_desktop() / "PBP Bewerbungs-Portal.lnk").exists(), "Desktop-Verknuepfung liegt")
    daten = warte_auf_pbp(version, 90)
    pruefe(daten.get("pbp_version") == version, f"/api/health meldet {version}")
    pruefe((DATEN / "pbp.db").exists(), "Datenbank liegt im Datenordner")


# ── Port: haengendes eigenes Dashboard, fremdes Programm ────────────────────────────────

def cmd_haenger(a) -> None:
    melde("== Haengendes eigenes Dashboard am Port (#1290)")
    version = aktuell()
    pid = pid_am_port()
    pruefe(pid is not None, f"am Port {PORT} lauscht ein Prozess ({pid})")
    zeile = kommandozeile(pid)
    melde(f"  Kommandozeile: {zeile}")
    pruefe(str(APP).casefold() in zeile.casefold(), "der Prozess stammt aus dem Programmordner")
    anhalten(pid)
    art, _ = health(timeout=6)
    pruefe(art == "keine_antwort", f"angehaltenes Dashboard antwortet nicht (gelesen: {art})")
    pruefe(pid_am_port() == pid, f"und haelt den Port weiter ({pid})")
    proc, ausgabe = dashboard_starten("nach-haenger")
    try:
        warte_auf_pbp(version, 120)
    finally:
        melde(lies(ausgabe)[-3000:])
    pruefe(not lebt(pid), f"der haengende Prozess {pid} ist beendet")
    neu = pid_am_port()
    pruefe(neu is not None and neu != pid, f"ein neuer Prozess haelt den Port ({neu})")
    text = lies(ausgabe)
    pruefe("noch einmal" in text, "der Start prueft ein zweites Mal, bevor er beendet")
    pruefe("beendet ihn jetzt" in text, "der Start sagt, dass er den Prozess beendet")
    pruefe("Haengender PBP-Prozess" in log_tail(200), "das Protokoll nennt den beendeten Prozess")
    pruefe(proc.poll() is None, "das neue Dashboard laeuft weiter")


_FREMD = """
import socket, sys, time
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("127.0.0.1", int(sys.argv[1])))
s.listen(64)
while True:          # nimmt Verbindungen nie an: der Port ist belegt und antwortet nicht
    time.sleep(3600)
"""


def cmd_fremd(a) -> None:
    melde(f"== Fremdes Programm am Port ({a.runden} Start(s), Abstand {a.abstand} s)")
    version_vorher = aktuell()
    dashboard_beenden()
    skript = PROTOKOLLE / "fremd_lauscher.py"
    skript.write_text(_FREMD, encoding="utf-8")
    fremd = subprocess.Popen([sys.executable, str(skript), str(PORT)], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=KEIN_FENSTER)
    try:
        for _ in range(50):
            if pid_am_port() == fremd.pid:
                break
            time.sleep(0.2)
        pruefe(pid_am_port() == fremd.pid, f"das fremde Programm ({fremd.pid}) haelt den Port")
        for runde in range(1, a.runden + 1):
            if runde > 1:
                melde(f"  warte {a.abstand} s (ein unbestaetigter Start zaehlt erst nach 90 s)")
                time.sleep(a.abstand)
            proc, ausgabe = dashboard_starten(f"fremd-{runde}")
            try:
                code = proc.wait(timeout=180)
            except subprocess.TimeoutExpired:
                proc.kill()
                raise ProbeFehler(f"Start {runde} endet am belegten Port nicht von selbst")
            text = lies(ausgabe)
            melde(text[-2500:])
            # Die .bat endet mit dem Code von `pause` (0); massgeblich ist, was sie meldet.
            pruefe("Fehlercode 1" in text, f"Start {runde} endet mit Fehlercode 1, statt zu laufen (Exit der .bat: {code})")
            pruefe(fremd.poll() is None, f"Start {runde}: das fremde Programm lebt noch (nie beendet)")
            pruefe(str(fremd.pid) in text, f"Start {runde}: die Meldung nennt die Kennung {fremd.pid}")
            pruefe(health(timeout=6)[0] != "pbp", f"Start {runde}: am Port antwortet kein PBP")
    finally:
        fremd.kill()
        fremd.wait(timeout=30)
    pruefe(aktuell() == version_vorher, f"aktuell.txt unveraendert ({version_vorher}): kein Rueckfall")
    proc, ausgabe = dashboard_starten("nach-fremd")
    try:
        daten = warte_auf_pbp(version_vorher, 120)
    finally:
        melde(lies(ausgabe)[-1500:])
    pruefe(daten.get("pbp_version") == version_vorher, f"der naechste Start laeuft mit {version_vorher}")
    status = APP / "update_status.json"
    if status.exists():
        inhalt = json.loads(status.read_text(encoding="utf-8") or "{}")
        pruefe(not inhalt.get("rueckgang"), "update_status.json meldet keinen Rueckgang")


# ── Update zwischen zwei Veroeffentlichungen ────────────────────────────────────────────

def _gh(pfad: str):
    kopf = {"Accept": "application/vnd.github+json", "User-Agent": "pbp-windows-probe"}
    if os.environ.get("GITHUB_TOKEN"):
        kopf["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(f"https://api.github.com/{pfad}", headers=kopf), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _schluessel(v: str) -> tuple:
    return tuple(int(x) for x in v.split("."))


def stabile_fassungen() -> list[str]:
    tags = []
    for rel in _gh(f"repos/{REPO}/releases?per_page=50"):
        tag = str(rel.get("tag_name", ""))
        if not rel.get("prerelease") and not rel.get("draft") and re.fullmatch(r"v\d+\.\d+\.\d+", tag):
            tags.append(tag[1:])
    return sorted(set(tags), key=_schluessel)


def cmd_update_vorbereiten(a) -> None:
    fassungen = stabile_fassungen()
    nach = _gh(f"repos/{REPO}/releases/latest")["tag_name"].lstrip("v")
    linie = nach.rsplit(".", 1)[0]
    vorher = [v for v in fassungen if _schluessel(v) < _schluessel(nach) and v.startswith(linie + ".")]
    if a.von:
        von = a.von
    elif vorher:
        von = vorher[-1]
    else:
        raise ProbeFehler(f"keine vorige stabile Fassung der Linie {linie} vor {nach}")
    ziel = Path(a.ziel).resolve()
    ziel.mkdir(parents=True, exist_ok=True)
    zip_pfad = ziel / f"PBP-{von}.zip"
    urllib.request.urlretrieve(f"https://github.com/{REPO}/archive/refs/tags/v{von}.zip", zip_pfad)
    with zipfile.ZipFile(zip_pfad) as z:
        z.extractall(ziel)
    ordner = next(p for p in ziel.iterdir() if p.is_dir() and p.name.startswith("PBP-"))
    melde(f"== Update-Probe: von {von} nach {nach}, entpackt in {ordner}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"von={von}\nnach={nach}\nordner={ordner}\n")


def _rest(methode: str, pfad: str, koerper: dict | None = None, timeout: float = 120):
    daten = json.dumps(koerper or {}).encode("utf-8") if methode == "POST" else None
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{pfad}", data=daten, method=methode,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def cmd_update(a) -> None:
    von = aktuell()
    melde(f"== Update aus dem laufenden Dashboard: {von} -> {a.nach}")
    warte_auf_pbp(von, 60)
    # Die Update-Dateien haengen erst nach dem Tag an der Veroeffentlichung (Release-Ablauf 5a): bis dahin "unvollstaendig".
    ende = time.monotonic() + a.frist_dateien
    while True:
        code, ueb = _rest("POST", "/api/auto-update/pruefen")
        p = (ueb or {}).get("pruefung") or {}
        melde(f"  Pruefung: {code} {p.get('status')} {p.get('version')} {p.get('text', '')}")
        if p.get("status") == "neu" or time.monotonic() > ende:
            break
        time.sleep(60)
    pruefe(p.get("status") == "neu" and p.get("version") == a.nach, f"die Pruefung findet {a.nach} als neue Version")
    code, antwort = _rest("POST", "/api/auto-update/installieren", {"version": a.nach})
    pruefe(code == 200 and antwort.get("status") == "gestartet", f"Installation gestartet ({code} {antwort.get('status')})")
    ende = time.monotonic() + a.frist
    job = {}
    while time.monotonic() < ende:
        _, ueb = _rest("GET", "/api/auto-update")
        job = ueb.get("job") or {}
        melde(f"  {job.get('phase')}: {job.get('text')}")
        if job.get("status") in ("fertig", "fehler"):
            break
        time.sleep(5)
    pruefe(job.get("status") == "fertig", f"der Lauf endet fertig (Stand: {job.get('status')}: {job.get('text')})")
    _, ueb = _rest("GET", "/api/auto-update")
    pruefe(ueb.get("aktuell") == a.nach and aktuell() == a.nach, f"aktuell.txt nennt {a.nach}")
    pruefe(ueb.get("neustart_noetig") is True, "die Anzeige verlangt einen Neustart")
    eintrag = (ueb.get("verlauf") or [{}])[0]
    pruefe(eintrag.get("version") == a.nach and eintrag.get("ergebnis") == "installiert",
           f"der Verlauf nennt {a.nach} als installiert ({eintrag})")
    pruefe((APP / "versions" / a.nach / ".fertig").exists(), f"Fassungsordner {a.nach} ist fertig markiert")
    pruefe((APP / "versions" / von / ".fertig").exists(), f"die vorige Fassung {von} bleibt fuer den Rueckweg")
    dashboard_beenden()
    proc, ausgabe = dashboard_starten("nach-update")
    try:
        daten = warte_auf_pbp(a.nach, 180)
    finally:
        melde(lies(ausgabe)[-2000:])
    pruefe(daten.get("pbp_version") == a.nach, f"nach dem Neustart meldet /api/health {a.nach}")


# ── Deinstallieren ──────────────────────────────────────────────────────────────────────

def cmd_deinstallieren(a) -> None:
    melde("== Deinstallieren (mit Sicherung auf dem Desktop, Daten loeschen)")
    desktop = _desktop()
    vorher = set(desktop.glob("PBP-Backup-*.zip"))
    antworten = PROTOKOLLE / "deinstaller-antworten.txt"
    # Reihenfolge der Fragen: starten? / Sicherung? / LOESCHEN / Zusatzdateien loeschen?
    # Eine DATEI als Eingabe, keine Leitung: `set /p` liest aus einer Leitung beim ersten Mal alles (cmd).
    antworten.write_bytes(b"j\r\nj\r\nLOESCHEN\r\nn\r\n")
    ausgabe = PROTOKOLLE / "deinstaller.txt"
    with open(antworten, "rb") as ein, open(ausgabe, "wb") as aus:
        r = subprocess.run(["cmd", "/c", str(APP / "DEINSTALLIEREN.bat")], cwd=str(APP), stdin=ein, stdout=aus,
                           stderr=subprocess.STDOUT, timeout=a.frist, creationflags=KEIN_FENSTER)
    melde(lies(ausgabe)[-4000:])
    pruefe(r.returncode == 0, f"Deinstaller endet mit 0 ({r.returncode})")
    neu = set(desktop.glob("PBP-Backup-*.zip")) - vorher
    pruefe(len(neu) == 1 and next(iter(neu)).stat().st_size > 0, "eine Sicherung liegt auf dem Desktop")
    with zipfile.ZipFile(next(iter(neu))) as z:
        pruefe(any(n.endswith("pbp.db") for n in z.namelist()), "die Sicherung enthaelt die Datenbank")
    pruefe(_registry_version() is None, "der Apps-Eintrag ist entfernt")
    pruefe(not APP.exists(), f"der Programmordner ist entfernt ({APP})")
    pruefe(not DATEN.exists(), f"der Datenordner ist entfernt ({DATEN})")
    pruefe(not (desktop / "PBP Bewerbungs-Portal.lnk").exists(), "die Desktop-Verknuepfung ist entfernt")
    pruefe(pid_am_port() is None, f"am Port {PORT} lauscht nichts mehr")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="befehl", required=True)
    p = sub.add_parser("installieren")
    p.add_argument("--ordner", required=True)
    p.add_argument("--erwartet")
    p.add_argument("--frist", type=float, default=1800)
    p.set_defaults(f=cmd_installieren)
    p = sub.add_parser("haenger")
    p.set_defaults(f=cmd_haenger)
    p = sub.add_parser("fremd")
    p.add_argument("--runden", type=int, default=1)
    p.add_argument("--abstand", type=float, default=95)
    p.set_defaults(f=cmd_fremd)
    p = sub.add_parser("update-vorbereiten")
    p.add_argument("--ziel", default=str(Path(os.environ.get("RUNNER_TEMP", ".")) / "pbp-vorher"))
    p.add_argument("--von")
    p.set_defaults(f=cmd_update_vorbereiten)
    p = sub.add_parser("update")
    p.add_argument("--nach", required=True)
    p.add_argument("--frist", type=float, default=1200)
    p.add_argument("--frist-dateien", type=float, default=1800)
    p.set_defaults(f=cmd_update)
    p = sub.add_parser("deinstallieren")
    p.add_argument("--frist", type=float, default=900)
    p.set_defaults(f=cmd_deinstallieren)
    a = ap.parse_args(argv)
    if sys.platform != "win32":
        print("Die Probe laeuft nur unter Windows.", file=sys.stderr)
        return 2
    if not os.environ.get("CI") and not os.environ.get("PBP_PROBE_ERLAUBT"):
        # Der Installer schreibt, der Deinstaller loescht unter %LOCALAPPDATA%\BewerbungsAssistent: nie auf einem echten Rechner.
        print("Nur in der CI (oder mit PBP_PROBE_ERLAUBT=1 in einer Wegwerf-Maschine).", file=sys.stderr)
        return 2
    try:
        a.f(a)
    except ProbeFehler as e:
        melde(f"  [FEHLER] {e}")
        melde("--- pbp.log (Ende) ---\n" + log_tail())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
