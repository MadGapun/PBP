"""Der Installer räumt sich selbst auf: entpackter Ordner und ZIP (Auto-Update, #1093, Anforderung 14).

Wer von Hand aktualisiert (ZIP laden, entpacken, `INSTALLIEREN.bat`), hinterlässt bisher beides: das ZIP im
Downloads-Ordner und den entpackten Ordner. Am Ende bietet der Installer an, beides zu löschen; ob er fragt, es
immer tut oder nie, steht in den Einstellungen (`installer_aufraeumen`: fragen, immer, nie; Vorgabe fragen).

Aufruf aus `INSTALLIEREN.bat`:

    python _installer_aufraeumen.py einstellung <Datenordner>        gibt fragen | immer | nie aus
    python _installer_aufraeumen.py plan <Installationsordner> <Fassung> <Programmordner> <Datenordner>
                                                                     zeigt, was geloescht wuerde (loescht nichts)
    python _installer_aufraeumen.py loeschen <Installationsordner> <Fassung> <Programmordner> <Datenordner>
                                                                     startet das Loeschen im Hintergrund

**Was gelöscht wird, ist eng gefasst** — ein Fehltreffer hier loescht Dateien des Menschen:

* der Installationsordner nur, wenn er wirklich ein entpackter Installer ist (`INSTALLIEREN.bat`,
  `_programm_einrichten.py` und `src/bewerbungs_assistent/__init__.py` liegen darin), kein Git-Arbeitsordner ist
  (`.git`), nicht der Programm- oder Datenordner ist, keinen davon enthaelt, nicht in einem davon liegt und
  nicht das Home- oder Laufwerks-Wurzelverzeichnis ist;
* ZIP-Dateien nur mit dem Namen `PBP-<Fassung>.zip` (Gross-/Kleinschreibung egal), im Ordner NEBEN dem
  Installationsordner oder in `Downloads`, und nur, wenn in ihnen `INSTALLIEREN.bat` steht.

Das Loeschen laeuft in einem eigenen Prozess, der wiederholt versucht: solange das Fenster des Installers offen
ist, ist sein Ordner gesperrt. Es gibt nach zehn Minuten auf und merkt sich nichts.

Nur Standardbibliothek: es laeuft in der Embeddable-Python-Laufzeit des Installers.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
import zipfile
from pathlib import Path

EINSTELLUNGEN = ("fragen", "immer", "nie")
ERKENNUNGSDATEIEN = ("INSTALLIEREN.bat", "_programm_einrichten.py", "src/bewerbungs_assistent/__init__.py")
VERSUCHE = 200
PAUSE_S = 3.0


def einstellung(daten_ordner) -> str:
    """Die Einstellung `installer_aufraeumen` aus der Datenbank (nur lesend); bei jedem Zweifel `fragen`."""
    db = Path(daten_ordner) / "pbp.db"
    if not db.is_file():
        return "fragen"
    try:
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=3)
        try:
            zeile = conn.execute("SELECT value FROM settings WHERE key='installer_aufraeumen'").fetchone()
        finally:
            conn.close()
        wert = json.loads(zeile[0]) if zeile else "fragen"
    except Exception:  # noqa: BLE001 — gesperrt, kaputt, fremd: dann fragen, nie ungefragt loeschen
        return "fragen"
    return wert if wert in EINSTELLUNGEN else "fragen"


def _gleich_oder_darin(a: Path, b: Path) -> bool:
    """Ist a gleich b oder liegt a in b?"""
    try:
        a.resolve().relative_to(b.resolve())
        return True
    except (ValueError, OSError):
        return False


def installationsordner_pruefen(basis, programm, daten):
    """(True, "") oder (False, Grund): ist `basis` ein entpackter Installer, den man loeschen darf?"""
    basis, programm, daten = Path(basis), Path(programm), Path(daten)
    try:
        if not basis.is_dir():
            return False, "Der Installationsordner existiert nicht."
        for name in ERKENNUNGSDATEIEN:
            if not (basis / name).is_file():
                return False, f"{name} fehlt: das ist kein entpackter Installer."
        if (basis / ".git").exists():
            return False, "Das ist ein Git-Arbeitsordner (Entwicklung), kein entpackter Installer."
        for tabu, name in ((programm, "der Programmordner"), (daten, "der Datenordner")):
            if _gleich_oder_darin(basis, tabu) or _gleich_oder_darin(tabu, basis):
                return False, f"Der Installationsordner ist oder enthaelt {name}."
        if _gleich_oder_darin(Path.home(), basis):       # der Ordner IST das Benutzerverzeichnis oder enthaelt es
            return False, "Der Installationsordner ist oder enthaelt das Benutzerverzeichnis."
        if basis.resolve().parent == basis.resolve():
            return False, "Das ist die Wurzel eines Laufwerks."
    except OSError as exc:
        return False, f"Nicht pruefbar: {exc}"
    return True, ""


def zip_kandidaten(basis, fassung: str) -> list:
    """ZIP-Dateien `PBP-<fassung>.zip` neben dem Installationsordner und in Downloads, die den Installer enthalten."""
    basis = Path(basis)
    ordner = [basis.resolve().parent, Path.home() / "Downloads"]
    soll = f"pbp-{fassung}.zip".lower()
    gefunden = []
    for o in ordner:
        try:
            for p in o.iterdir():
                if p.is_file() and p.name.lower() == soll and p not in gefunden:
                    try:
                        with zipfile.ZipFile(p) as zf:
                            if any(n.replace("\\", "/").rstrip("/").endswith("INSTALLIEREN.bat") for n in zf.namelist()):
                                gefunden.append(p)
                    except (zipfile.BadZipFile, OSError):
                        continue
        except OSError:
            continue
    return gefunden


def plan(basis, fassung: str, programm, daten) -> dict:
    ok, grund = installationsordner_pruefen(basis, programm, daten)
    return {"ordner": str(Path(basis)) if ok else None, "grund": grund,
            "zips": [str(p) for p in zip_kandidaten(basis, fassung)] if ok else []}


def _freigeben(fn, pfad, _info):
    os.chmod(pfad, stat.S_IWRITE)
    fn(pfad)


def _loeschen_versuchen(ordner, zips) -> bool:
    """Ein Durchgang; True, wenn alles weg ist."""
    for z in zips:
        try:
            Path(z).unlink(missing_ok=True)
        except OSError:
            pass
    if ordner and Path(ordner).exists():
        shutil.rmtree(ordner, onerror=_freigeben)
    return not (ordner and Path(ordner).exists()) and not any(Path(z).exists() for z in zips)


def lauf(ordner, zips, *, versuche: int = VERSUCHE, pause: float = PAUSE_S) -> bool:
    """Wiederholt, bis der Ordner weg ist (das Fenster des Installers sperrt ihn, bis es zu ist)."""
    for i in range(versuche):
        if _loeschen_versuchen(ordner, zips):
            return True
        time.sleep(pause)
    return False


def loeschen_starten(basis, fassung: str, programm, daten) -> dict:
    """Prueft, plant und startet das Loeschen in einem abgetrennten Prozess. Gibt den Plan zurueck."""
    p = plan(basis, fassung, programm, daten)
    if not p["ordner"]:
        return p
    nutzlast = json.dumps({"ordner": p["ordner"], "zips": p["zips"]})
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000008 | 0x08000000 | 0x00000200  # DETACHED | NO_WINDOW | NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    # Der Helfer laeuft NICHT aus dem Ordner, den er loescht: eine Kopie dieser Datei im Temp-Ordner.
    import tempfile
    kopie = Path(tempfile.gettempdir()) / "pbp_installer_aufraeumen.py"
    shutil.copy2(__file__, kopie)
    subprocess.Popen([sys.executable, str(kopie), "lauf", nutzlast], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, cwd=tempfile.gettempdir(), **kwargs)
    return p


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) == 2 and a[0] == "einstellung":
        print(einstellung(a[1]))
        return 0
    if len(a) == 5 and a[0] in ("plan", "loeschen"):
        p = plan(a[1], a[2], a[3], a[4]) if a[0] == "plan" else loeschen_starten(a[1], a[2], a[3], a[4])
        print(json.dumps(p, ensure_ascii=False))
        return 0 if p["ordner"] else 1
    if len(a) == 2 and a[0] == "lauf":
        nutz = json.loads(a[1])
        return 0 if lauf(nutz["ordner"], nutz["zips"]) else 1
    print("Aufruf: siehe Kopf dieser Datei.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
