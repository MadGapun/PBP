"""Ein Update-Archiv sicher entpacken (#1093).

Das Archiv ist geprueft (Prüfsumme, Signatur), und trotzdem wird es behandelt, als koennte es
boesartig sein: eine Pruefung, die nur EINE Schutzschicht kennt, faellt mit ihr. Deshalb
schreibt dieses Modul jede Datei selbst, statt `ZipFile.extract` zu vertrauen, und lehnt
das ganze Archiv ab, sobald EIN Eintrag nicht passt.

Abgewiesen wird:

* Pfade ausserhalb des Zielordners (`..`, absolute Pfade, Laufwerksbuchstaben, UNC, `\\`),
  Windows-Besonderheiten (Datenstroeme mit `:`, Geraetenamen wie `CON`/`NUL`, Namen, die auf
  Punkt oder Leerzeichen enden) und Eintraege, die sich nur in der Gross-/Kleinschreibung
  unterscheiden (unter Windows dieselbe Datei),
* Verknuepfungen,
* ausfuehrbare Dateien (`.exe`, `.dll`, `.pyd`, `.bat`, `.ps1`, ...): ein Update bringt Quelltext
  und keine Programme mit (weniger Angriffsflaeche, weniger Fehlalarme von Virenscannern),
* alles ausser `manifest.json`, `start_dashboard.py`, `_selftest.py` und `src/...` an der Wurzel,
* zu viele, zu grosse oder verdaechtig stark gepackte Dateien (Zip-Bombe).
"""
from __future__ import annotations

import errno
import os
import stat
import zipfile
import zlib
from pathlib import Path, PurePosixPath

from .fehler import UpdateFehler

ERLAUBTE_WURZELDATEIEN = frozenset({"manifest.json", "start_dashboard.py", "_selftest.py"})
ERLAUBTER_WURZELORDNER = "src"

VERBOTENE_ENDUNGEN = frozenset({
    ".exe", ".dll", ".pyd", ".so", ".dylib", ".bat", ".cmd", ".com", ".scr", ".msi", ".ps1", ".psm1",
    ".vbs", ".vbe", ".js_exe", ".wsf", ".lnk", ".jar", ".sys", ".cpl", ".hta",
})
GERAETENAMEN = frozenset({"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))})

MAX_DATEIEN = 5000
MAX_GESAMT_BYTES = 400 * 1024 * 1024
MAX_EINZEL_BYTES = 100 * 1024 * 1024
#: Verhaeltnis entpackt/gepackt, ab dem eine Datei (ueber 1 MB) als Zip-Bombe gilt.
MAX_VERHAELTNIS = 200
BLOCK = 256 * 1024


def _unsicher(grund: str, name: str = ""):
    return UpdateFehler("archiv_unsicher", detail=f"{grund}: {name[:120]}" if name else grund)


def _pfad_pruefen(name: str) -> PurePosixPath:
    """Der Eintragsname als sauberer relativer Pfad, sonst Abbruch."""
    if not name or "\x00" in name or "\\" in name or name.startswith("/") or ":" in name:
        raise _unsicher("Pfad nicht erlaubt", name)
    ohne_slash = name.rstrip("/")
    teile = ohne_slash.split("/")
    for teil in teile:
        if teil in ("", ".", "..") or teil != teil.strip() or teil.endswith("."):
            raise _unsicher("Pfadteil nicht erlaubt", name)
        stamm = teil.split(".")[0].upper()
        if stamm in GERAETENAMEN:
            raise _unsicher("Gerätename im Pfad", name)
    p = PurePosixPath(ohne_slash)
    if p.is_absolute():
        raise _unsicher("absoluter Pfad", name)
    return p


def _ist_verknuepfung(info: zipfile.ZipInfo) -> bool:
    modus = info.external_attr >> 16
    return bool(modus) and stat.S_ISLNK(modus)


def entpacken(archiv, ziel) -> dict:
    """Entpackt `archiv` nach `ziel` (muss leer sein oder fehlen). Gibt {'dateien': n, 'bytes': b} zurueck.

    Bei JEDER Auffaelligkeit wird abgebrochen und `ziel` wieder entfernt, soweit es hier entstand.
    """
    archiv, ziel = Path(archiv), Path(ziel)
    if ziel.exists() and any(ziel.iterdir()):
        raise _unsicher("Zielordner ist nicht leer", str(ziel))
    angelegt = not ziel.exists()
    ziel.mkdir(parents=True, exist_ok=True)
    try:
        return _entpacken_pruefend(archiv, ziel.resolve())
    except BaseException as exc:
        _aufraeumen(ziel, ganz=angelegt)
        if isinstance(exc, UpdateFehler) or not isinstance(exc, Exception):
            raise
        if isinstance(exc, OSError) and getattr(exc, "errno", None) == errno.ENOSPC:
            raise UpdateFehler("platz", detail=str(exc)) from exc
        if isinstance(exc, (zipfile.BadZipFile, zlib.error, EOFError)):
            raise _unsicher("Archiv beschädigt", f"{type(exc).__name__}: {exc}") from exc
        raise UpdateFehler("unerwartet", detail=f"{type(exc).__name__}: {exc}") from exc


def _aufraeumen(ziel: Path, *, ganz: bool) -> None:
    import shutil
    try:
        if ganz:
            shutil.rmtree(ziel, ignore_errors=True)
        else:
            for kind in ziel.iterdir():
                shutil.rmtree(kind, ignore_errors=True) if kind.is_dir() else kind.unlink(missing_ok=True)
    except OSError:
        pass


def _entpacken_pruefend(archiv: Path, ziel: Path) -> dict:
    try:
        zf = zipfile.ZipFile(archiv)
    except (zipfile.BadZipFile, OSError) as exc:
        raise _unsicher("kein lesbares ZIP", str(exc)) from exc
    with zf:
        eintraege = zf.infolist()
        if not eintraege:
            raise _unsicher("leeres Archiv")
        if len(eintraege) > MAX_DATEIEN:
            raise _unsicher("zu viele Einträge", str(len(eintraege)))

        # 1. ALLES pruefen, bevor irgendetwas geschrieben wird
        gesehen = set()
        gesamt = 0
        plan = []
        for info in eintraege:
            pfad = _pfad_pruefen(info.filename)
            schluessel = "/".join(pfad.parts).casefold()
            if schluessel in gesehen:
                raise _unsicher("Eintrag doppelt (auch bei anderer Schreibweise)", info.filename)
            gesehen.add(schluessel)
            if _ist_verknuepfung(info):
                raise _unsicher("Verknuepfung", info.filename)
            wurzel = pfad.parts[0]
            ist_ordner = info.is_dir()
            if not ist_ordner:
                if len(pfad.parts) == 1:
                    if wurzel not in ERLAUBTE_WURZELDATEIEN:
                        raise _unsicher("Datei an der Wurzel nicht vorgesehen", info.filename)
                elif wurzel != ERLAUBTER_WURZELORDNER:
                    raise _unsicher("Ordner an der Wurzel nicht vorgesehen", info.filename)
                if pfad.suffix.lower() in VERBOTENE_ENDUNGEN:
                    raise _unsicher("ausführbare Datei", info.filename)
                if info.file_size > MAX_EINZEL_BYTES:
                    raise _unsicher("Datei zu gross", info.filename)
                if info.file_size > 1024 * 1024 and info.compress_size and info.file_size / info.compress_size > MAX_VERHAELTNIS:
                    raise _unsicher("verdaechtig stark gepackt", info.filename)
            elif len(pfad.parts) == 1 and wurzel != ERLAUBTER_WURZELORDNER:
                raise _unsicher("Ordner an der Wurzel nicht vorgesehen", info.filename)
            gesamt += info.file_size
            if gesamt > MAX_GESAMT_BYTES:
                raise _unsicher("insgesamt zu gross")
            plan.append((info, pfad, ist_ordner))
        namen = {"/".join(p.parts) for _, p, o in plan if not o}
        if "manifest.json" not in namen:
            raise _unsicher("manifest.json fehlt")

        # 2. Schreiben — jede Datei selbst, jeder Zielpfad noch einmal gegen den Zielordner geprueft
        geschrieben = 0
        for info, pfad, ist_ordner in plan:
            ziel_pfad = (ziel.joinpath(*pfad.parts)).resolve()
            if ziel != ziel_pfad and ziel not in ziel_pfad.parents:
                raise _unsicher("Zielpfad ausserhalb", info.filename)
            if ist_ordner:
                ziel_pfad.mkdir(parents=True, exist_ok=True)
                continue
            ziel_pfad.parent.mkdir(parents=True, exist_ok=True)
            bytes_ = 0
            with zf.open(info) as quelle, open(ziel_pfad, "wb") as aus:
                while True:
                    stueck = quelle.read(BLOCK)
                    if not stueck:
                        break
                    bytes_ += len(stueck)
                    if bytes_ > info.file_size or bytes_ > MAX_EINZEL_BYTES:
                        raise _unsicher("mehr Daten als angekündigt", info.filename)
                    aus.write(stueck)
            geschrieben += bytes_
        return {"dateien": len(namen), "bytes": geschrieben}
