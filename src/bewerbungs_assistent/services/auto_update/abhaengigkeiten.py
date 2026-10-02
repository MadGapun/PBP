"""Brauchen wir Pakete, die es noch nicht gibt? Dann in den NEUEN Fassungsordner legen (#1093).

Die meisten Updates aendern nur Quelltext. Bringt eine Fassung ein neues Paket oder hebt eine
Untergrenze an (`python-jobspy>=1.2`), muss es vor dem Umschalten da sein, sonst startet die
neue Fassung nicht. Bestehende Pakete der Laufzeit werden NIE angefasst: das waere
"ueber laufende Dateien kopieren". Fehlendes landet in `versions/<fassung>/site` und kommt
dank Startbaustein beim Start der neuen Fassung vor den alten Paketen in `sys.path`.

Pruefen ohne `packaging`: in der Laufzeit des Installers kann es fehlen. Das Manifest
enthaelt nur einfache Angaben (`name>=1.2,<4`); alles, was hier nicht sicher gelesen werden
kann, zaehlt als FEHLEND (sicherer Zustand: es wird versucht zu installieren, und scheitert
das, braucht das Update den Installer).

Installiert wird mit `pip install --target` und `--only-binary=:all:` — fertige Pakete
von PyPI, nichts wird gebaut oder ausgefuehrt, was nicht ohnehin dazugehoert.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from .fehler import UpdateFehler

#: Mehr fehlende Pakete als das: das ist kein Hintergrund-Update mehr, sondern ein Fall fuer den Installer.
MAX_FEHLENDE = 4
#: So viel Platz muss frei sein, bevor pip in den neuen Ordner schreibt.
MIN_FREIER_PLATZ = 600 * 1024 * 1024
PIP_TIMEOUT_S = 1200

_ANGABE = re.compile(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*([^;]*?)\s*(?:;.*)?", re.ASCII)
_TEIL = re.compile(r"\s*(<=|>=|==|!=|~=|<|>)\s*([0-9]+(?:\.[0-9]+)*)(?:\.\*)?\s*", re.ASCII)


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _zahlen(version: str):
    """Die fuehrenden Zahlen einer Versionsangabe: '2.0.0.post1' -> (2, 0, 0); ohne Zahl -> None."""
    teile = []
    for t in str(version).split("."):
        m = re.match(r"[0-9]+", t, re.ASCII)
        if not m:
            break
        teile.append(int(m.group(0)))
        if m.group(0) != t:
            break
    return tuple(teile) or None


def _vergleich(installiert: tuple, op: str, soll: tuple) -> bool:
    n = max(len(installiert), len(soll))
    a = installiert + (0,) * (n - len(installiert))
    b = soll + (0,) * (n - len(soll))
    if op == ">=":
        return a >= b
    if op == "<=":
        return a <= b
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    if op == "<":
        return a < b
    if op == ">":
        return a > b
    if op == "~=":
        if len(soll) < 2:
            return False
        obergrenze = soll[:-2] + (soll[-2] + 1,)
        return _vergleich(installiert, ">=", soll) and _vergleich(installiert, "<", obergrenze)
    return False


def lesen(angabe: str):
    """'fastmcp>=3.0,<4' -> ('fastmcp', [('>=', (3, 0)), ('<', (4,))]); None, wenn nicht sicher lesbar."""
    m = _ANGABE.fullmatch(angabe or "")
    if not m:
        return None
    name, rest = m.group(1), m.group(2)
    teile = []
    if rest:
        for stueck in rest.split(","):
            t = _TEIL.fullmatch(stueck)
            if not t:
                return None
            teile.append((t.group(1), tuple(int(x) for x in t.group(2).split("."))))
    return name, teile


def _installierte_version(name: str):
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None
    except Exception:
        return None


def erfuellt(angabe: str, *, version_von=None) -> bool:
    """Ist das Paket in der verlangten Fassung da? Nicht lesbar oder nicht gefunden: nein."""
    gelesen = lesen(angabe)
    if gelesen is None:
        return False
    name, teile = gelesen
    version = (version_von or _installierte_version)(name)
    if version is None:
        return False
    zahlen = _zahlen(version)
    if zahlen is None:
        return False
    return all(_vergleich(zahlen, op, soll) for op, soll in teile)


def fehlende(requirements, optional=(), *, version_von=None) -> list:
    """Die Angaben, die erst bereitgestellt werden muessen.

    Pflichtpakete: fehlt eines oder passt die Fassung nicht -> in die Liste.
    Optionale Pakete: nur, wenn sie VORHANDEN sind, aber die Untergrenze nicht mehr erfuellen
    (wer sie nie installiert hat, bekommt sie durch ein Update nicht aufgedraengt).
    """
    ergebnis = [r for r in requirements if not erfuellt(r, version_von=version_von)]
    lookup = version_von or _installierte_version
    for r in optional:
        gelesen = lesen(r)
        if gelesen is None:
            continue
        if lookup(gelesen[0]) is not None and not erfuellt(r, version_von=version_von):
            ergebnis.append(r)
    return ergebnis


def bereitstellen(fehlende_angaben, ziel, *, python=None, runner=None, freier_platz=None) -> list:
    """Legt die fehlenden Pakete mit pip nach `ziel` (`versions/<fassung>/site`). Gibt die Angaben zurueck.

    Mehr als `MAX_FEHLENDE`, zu wenig Platz oder ein Fehlschlag von pip: `UpdateFehler`
    (Code `braucht_installer` bzw. `platz`/`abhaengigkeiten`) — nichts bleibt halb im Ordner liegen.
    """
    if not fehlende_angaben:
        return []
    if len(fehlende_angaben) > MAX_FEHLENDE:
        raise UpdateFehler("braucht_installer", "Dieses Update bringt zu viele neue Pakete mit, um sie im Hintergrund "
                           "einzurichten. Es braucht den Installer.", detail=", ".join(fehlende_angaben)[:200])
    for a in fehlende_angaben:
        if lesen(a) is None:
            raise UpdateFehler("manifest", detail=f"Paketangabe nicht lesbar: {a!r}")
    ziel = Path(ziel)
    frei = freier_platz if freier_platz is not None else shutil.disk_usage(ziel.parent).free
    if frei < MIN_FREIER_PLATZ:
        raise UpdateFehler("platz", detail=f"{frei // (1024 * 1024)} MB frei, gebraucht {MIN_FREIER_PLATZ // (1024 * 1024)} MB")
    ziel.mkdir(parents=True, exist_ok=True)
    befehl = [python or sys.executable, "-m", "pip", "install", "--isolated", "--target", str(ziel),
              "--only-binary=:all:", "--no-input", "--disable-pip-version-check", "--no-warn-script-location",
              *fehlende_angaben]
    run = runner or subprocess.run
    umgebung = {**os.environ, "PYTHONIOENCODING": "utf-8"}     # pip nennt den Zielpfad; der Benutzername darin ist nicht immer ASCII
    try:
        r = run(befehl, capture_output=True, encoding="utf-8", errors="replace", timeout=PIP_TIMEOUT_S, env=umgebung,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as exc:
        shutil.rmtree(ziel, ignore_errors=True)
        raise UpdateFehler("abhaengigkeiten", detail="pip: Zeitgrenze") from exc
    except Exception as exc:
        shutil.rmtree(ziel, ignore_errors=True)
        raise UpdateFehler("abhaengigkeiten", detail=f"{type(exc).__name__}: {exc}") from exc
    if getattr(r, "returncode", 1) != 0:
        shutil.rmtree(ziel, ignore_errors=True)
        ende = (getattr(r, "stderr", "") or getattr(r, "stdout", "") or "")[-300:]
        raise UpdateFehler("abhaengigkeiten", detail=ende.strip())
    return list(fehlende_angaben)
