"""Richtet den Programmordner ein: Versionsordner, Startbaustein, aktuell.txt (Auto-Update, #1093).

Aufruf (vom Installer, `INSTALLIEREN.bat`, mit der Python-Laufzeit des Installers):

    python _programm_einrichten.py <entpackter Ordner> <Programmordner>

Exit 0 = eingerichtet. Exit 1 = es wurde NICHTS veraendert (der Grund steht auf der Ausgabe).

Was hier entsteht (siehe `src/bewerbungs_assistent_boot/__init__.py` fuer das Warum):

    <Programmordner>/
        python/                 (legt der Installer)
        boot/bewerbungs_assistent_boot/   der Startbaustein (hier kopiert, ersetzt eine aeltere Kopie)
        versions/<fassung>/     src/, start_dashboard.py, _selftest.py, manifest.json, .fertig
        start_dashboard.py      der Starter der Verknuepfung (aendert sich nie)
        aktuell.txt             zeigt auf <fassung> — als LETZTES geschrieben

Der alte Aufbau (`<Programmordner>/src`) wird entfernt, nachdem die neue Fassung steht. Die Datenbank wird
hier nicht angefasst; ihre Sicherung vor dem Update macht der Installer vorher, die Umstellung des
Datenstands geschieht beim ersten Start der neuen Fassung.

Nur Standardbibliothek: es laeuft in der Embeddable-Python-Laufzeit, bevor irgendein Paket installiert ist.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

KOPIERT_NICHT = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


class Abbruch(Exception):
    """Der Aufbau konnte nicht eingerichtet werden; nichts wurde umgeschaltet."""


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _version_aus(init: Path) -> str:
    try:
        text = init.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise Abbruch(f"{init} nicht lesbar: {exc}") from exc
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        raise Abbruch(f"In {init} steht keine __version__.")
    return m.group(1)


def _loeschen(pfad: Path) -> None:
    """Ordner oder Datei weg; scheitert es (gesperrt), ist das ein Abbruch statt eines halben Zustands."""
    if not pfad.exists():
        return
    try:
        if pfad.is_dir():
            def _frei(fn, p, _info):
                os.chmod(p, stat.S_IWRITE)
                fn(p)
            shutil.rmtree(pfad, onerror=_frei)
        else:
            pfad.unlink()
    except OSError as exc:
        raise Abbruch(f"{pfad} laesst sich nicht entfernen (gesperrt?): {exc}") from exc
    if pfad.exists():
        raise Abbruch(f"{pfad} laesst sich nicht vollstaendig entfernen (Datei gesperrt?)")


def pth_anpassen(python_ordner: Path) -> bool:
    """`python*._pth`: `../boot` rein, `../src` raus, `import site` aktiv. Gibt True zurueck, wenn sich etwas aenderte.

    Mit einer ._pth-Datei ignoriert die Embeddable-Laufzeit die Umgebungsvariable PYTHONPATH — nur was hier steht,
    findet `python -m bewerbungs_assistent_boot`.
    """
    dateien = sorted(Path(python_ordner).glob("python*._pth"))
    if not dateien:
        return False
    geaendert = False
    for datei in dateien:
        roh = datei.read_bytes()
        crlf = b"\r\n" in roh
        text = roh.decode("utf-8-sig")
        zeilen = text.splitlines()
        neu = []
        for z in zeilen:
            s = z.strip()
            if s in ("../src", "..\\src"):
                continue
            if s == "#import site":
                z = "import site"
            neu.append(z)
        if not any(z.strip() == "../boot" for z in neu):
            neu.append("../boot")
        if not any(z.strip() == "import site" for z in neu):
            neu.append("import site")
        ergebnis = ("\r\n" if crlf else "\n").join(neu) + ("\r\n" if crlf else "\n")
        if ergebnis != text:
            datei.write_bytes(ergebnis.encode("utf-8"))
            geaendert = True
    return geaendert


def einrichten(basis, app) -> dict:
    """Legt die Fassung in `app/versions/<fassung>` an und schaltet `aktuell.txt` um. Wirft `Abbruch`."""
    basis, app = Path(basis), Path(app)
    src = basis / "src"
    if not (src / "bewerbungs_assistent" / "__init__.py").is_file():
        raise Abbruch(f"{src} enthaelt kein Programm (bewerbungs_assistent fehlt).")
    if not (src / "bewerbungs_assistent_boot" / "__init__.py").is_file():
        raise Abbruch(f"{src} enthaelt den Startbaustein nicht (bewerbungs_assistent_boot fehlt).")
    for name in ("start_dashboard.py", "_selftest.py"):
        if not (basis / name).is_file():
            raise Abbruch(f"{basis / name} fehlt.")
    launcher = basis / "installer" / "boot" / "start_dashboard_launcher.py"
    if not launcher.is_file():
        raise Abbruch(f"{launcher} fehlt.")

    sys.path.insert(0, str(src))
    import bewerbungs_assistent_boot as boot

    version = _version_aus(src / "bewerbungs_assistent" / "__init__.py")
    if boot.sortschluessel(version) is None:
        raise Abbruch(f"'{version}' ist keine gueltige Versionsnummer.")

    app.mkdir(parents=True, exist_ok=True)
    versionen = app / boot.VERSIONEN
    versionen.mkdir(exist_ok=True)
    ziel = versionen / version
    neu = versionen / f"{version}.neu"
    bericht = {"version": version}

    try:
        _loeschen(neu)
        shutil.copytree(src, neu / "src", ignore=KOPIERT_NICHT)
        for name in ("start_dashboard.py", "_selftest.py"):
            shutil.copy2(basis / name, neu / name)
        (neu / "manifest.json").write_text(json.dumps({
            "format": 1, "version": version, "installiert_mit": "installer", "erstellt": _jetzt()}, indent=1),
            encoding="utf-8")

        aktuell_vorher = boot.lese_aktuell(app)
        _loeschen(ziel)                       # dieselbe Fassung noch einmal installieren: ersetzen
        os.replace(neu, ziel)
        (ziel / boot.FERTIG).write_text(json.dumps({"version": version, "zeit": _jetzt(), "von": "installer"}), encoding="utf-8")

        # Startbaustein und Starter: eine neuere Kopie ersetzt die aeltere
        boot_ziel = app / "boot" / "bewerbungs_assistent_boot"
        _loeschen(boot_ziel)
        shutil.copytree(src / "bewerbungs_assistent_boot", boot_ziel, ignore=KOPIERT_NICHT)
        shutil.copy2(launcher, app / "start_dashboard.py")

        # Der alte Aufbau: der Code lag in <Programmordner>/src
        _loeschen(app / "src")
        for datei in ("_selftest.py",):       # lag frueher neben dem Starter
            alt = app / datei
            if alt.is_file():
                alt.unlink()
        pth_anpassen(app / "python")

        # Zustand: eine bewusste Installation setzt die Vorgeschichte der Fassung zurueck
        status = boot.lese_status(app)
        bestaetigt = status.get("bestaetigt")
        vorherige = bestaetigt if bestaetigt and bestaetigt != version and boot.fassung_gueltig(app, bestaetigt) else aktuell_vorher
        if vorherige and vorherige != version and boot.fassung_gueltig(app, vorherige):
            status["vorherige"] = vorherige
        status["gescheitert"] = [v for v in status.get("gescheitert", []) if v != version]
        status.pop("rueckgang", None)
        status.pop("start", None)
        status["letzte_installation"] = {"version": version, "zeit": _jetzt(), "von": "installer"}
        boot.schreibe_status(app, status)

        boot.schreibe_atomar(app / boot.AKTUELL, version + "\n")          # als LETZTES
    except BaseException:
        shutil.rmtree(neu, ignore_errors=True)
        raise
    bericht["vorherige"] = vorherige if vorherige and vorherige != version else None
    bericht["aelter_als_vorher"] = bool(aktuell_vorher and boot.sortschluessel(version) < boot.sortschluessel(aktuell_vorher))
    return bericht


def _ausgabe_absichern():
    """Die Ausgabe nennt Pfade, und die tragen den Benutzernamen. Geht sie in eine Datei (Installer-Protokoll), gilt die Zeichentabelle
    des Rechners; ein Zeichen ausserhalb davon (ł, ş, griechisch) darf das Drucken nicht zum Absturz bringen (L44)."""
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(errors="backslashreplace")
        except Exception:
            pass


def main(argv=None) -> int:
    _ausgabe_absichern()
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print("Aufruf: python _programm_einrichten.py <entpackter Ordner> <Programmordner>", file=sys.stderr)
        return 1
    try:
        bericht = einrichten(argv[0], argv[1])
    except Abbruch as exc:
        print(f"[FEHLER] {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[FEHLER] Unerwartet: {type(exc).__name__}: {exc}")
        return 1
    print(f"[OK] Version {bericht['version']} eingerichtet")
    if bericht.get("aelter_als_vorher"):
        print("[INFO] Das ist eine AELTERE Version als die bisher installierte. Die Datenbank kann neuer sein: "
              "dann schreibt PBP vorerst nichts mehr und sagt, was zu tun ist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
