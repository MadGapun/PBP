"""#1224 (dritter Lauf auf dem Werkstatt-PC, 14.10.2026): der Deinstaller endete nach der Backup-Frage.

Ursache: im Block `if /i "!CREATE_BACKUP!"=="j" ( ... )` standen drei Kommentarzeilen (`::`), zwei davon mit Klammern. cmd liest einen
Block beim Einlesen in einem Zug und meldete `"machte" kann syntaktisch an dieser Stelle nicht verarbeitet werden`; der Stapel brach ab,
AUCH bei der Antwort "n" (der Fehler entsteht beim Lesen, nicht beim Ausfuehren). Die Tests prueften Textmuster und die PowerShell-Zeilen,
nie den Stapel als Ganzes, und die Laeufe vom 11.10. waren vor der Aenderung.

Zwei Schutzschichten:
1. statisch: in keiner `.bat` steht in einem Klammerblock ein Kommentar mit Klammer oder eine echo-Zeile mit ungeschuetzter `)`;
2. dynamisch (nur Windows): der Abschnitt "6/7" des Deinstallers laeuft mit echtem `cmd` bis zum Ende, mit den Antworten n und j.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]


def _geschuetzt_entfernt(zeile: str) -> str:
    """Ohne mit ^ maskierte Zeichen und ohne Anfuehrungszeichen-Inhalte: dort zaehlt keine Klammer."""
    s = re.sub(r"\^.", "", zeile)
    return re.sub(r'"[^"]*"', "", s)


def bloecke_verletzungen(text: str) -> list[tuple[int, str, str]]:
    """(Zeile, Art, Text) je Verletzung: Kommentar mit Klammer oder echo mit ungeschuetzter ) innerhalb eines Klammerblocks."""
    funde = []
    tiefe = 0
    for nr, roh in enumerate(text.splitlines(), 1):
        z = roh.strip()
        kommentar = z.startswith("::") or re.match(r"(?i)^rem(\s|$)", z) is not None
        if kommentar:
            if tiefe > 0 and ("(" in z or ")" in z):
                funde.append((nr, "Kommentar mit Klammer im Block", z[:100]))
            continue
        s = _geschuetzt_entfernt(z)
        if re.match(r"(?i)^echo(\s|\.|$)", s):
            rest = re.sub(r"(?i)^echo", "", s, count=1).split(">>")[0].split(">")[0]
            if tiefe > 0 and ")" in rest:
                funde.append((nr, "echo mit ungeschuetzter ) im Block", z[:100]))
            continue
        tiefe = max(tiefe + s.count("(") - s.count(")"), 0)
    return funde


def _bat_dateien() -> list[Path]:
    try:
        roh = subprocess.run(["git", "ls-files", "-z", "--", "*.bat"], cwd=str(WURZEL), capture_output=True, timeout=30).stdout
        namen = [n for n in roh.decode("utf-8", errors="replace").split("\0") if n]
    except (OSError, subprocess.SubprocessError):
        namen = []
    if not namen:
        namen = [str(p.relative_to(WURZEL)) for p in WURZEL.rglob("*.bat")
                 if not {".git", "node_modules", ".venv"} & set(p.parts)]
    return [WURZEL / n for n in sorted(namen)]


# ── 1. statisch ──────────────────────────────────────────────────────────────────────────────

def test_der_waechter_findet_den_fehler_aus_1224():
    """Der Wortlaut, der den Deinstaller beendet hat: sonst bestuende die Pruefung unten leer."""
    schlecht = "\n".join([
        'if /i "!CREATE_BACKUP!"=="j" (',
        "    echo         Erstelle Backup...",
        ":: v1.8.0 (#1149 Punkt 8): die Pfade kommen ueber Umgebungsvariablen (DATA_DIR, BACKUP_ZIP), nicht eingebettet. Ein Apostroph",
        ":: im Benutzernamen (O'Brien) machte aus dem Befehl einen Syntaxfehler",
        "    powershell -NoProfile -Command \"exit 0\"",
        ")",
    ])
    funde = bloecke_verletzungen(schlecht)
    assert [f[0] for f in funde] == [3, 4], funde


def test_der_waechter_laesst_saubere_bloecke_in_ruhe():
    sauber = "\n".join([
        ":: ein Kommentar mit (Klammern) AUSSERHALB eines Blocks ist in Ordnung",
        'if exist "x" (',
        "    :: Kommentar ohne Klammer im Block",
        "    echo Text mit ^(maskierter Klammer^)",
        '    echo "Text (in Anfuehrungszeichen)"',
        ") else (",
        "    echo anderer Zweig",
        ")",
        "echo Text (ausserhalb) eines Blocks",
    ])
    assert bloecke_verletzungen(sauber) == []


def test_eine_ungeschuetzte_klammer_in_einer_echo_zeile_im_block_wird_gefunden():
    schlecht = "\n".join(['if exist "x" (', "    echo Hinweis (siehe oben)", ")"])
    assert [f[1] for f in bloecke_verletzungen(schlecht)] == ["echo mit ungeschuetzter ) im Block"]


@pytest.mark.parametrize("datei", _bat_dateien(), ids=lambda p: p.name)
def test_in_keinem_klammerblock_steht_ein_kommentar_mit_klammer(datei):
    text = datei.read_bytes().decode("cp1252", errors="replace")
    assert bloecke_verletzungen(text) == [], (
        f"{datei.name}: cmd liest einen Block in einem Zug; eine Klammer in einem Kommentar darin beendet ihn und den Stapel (#1224)")


def test_es_gibt_die_beiden_stapel_die_gemeint_sind():
    namen = {p.name for p in _bat_dateien()}
    assert {"INSTALLIEREN.bat", "DEINSTALLIEREN.bat"} <= namen


# ── 2. dynamisch ─────────────────────────────────────────────────────────────────────────────

def _abschnitt_6_von_7() -> list[str]:
    zeilen = (WURZEL / "DEINSTALLIEREN.bat").read_bytes().decode("cp1252", errors="replace").splitlines()
    von = next(i for i, z in enumerate(zeilen) if "[6/7]" in z)
    bis = next(i for i, z in enumerate(zeilen) if "[7/7]" in z)
    # ab dem Kommentar davor: die Zeilen, die direkt vor `set /p` stehen, gehoeren zum Abschnitt
    return zeilen[von:bis]


def _lauf(tmp_path: Path, antwort: str) -> tuple[str, Path, Path]:
    daten = tmp_path / "daten"
    daten.mkdir()
    (daten / "pbp.db").write_bytes(b"SQLite format 3\0" + b"\0" * 64)
    profil = tmp_path / "profil"
    (profil / "Desktop").mkdir(parents=True)
    protokoll = tmp_path / "protokoll.txt"
    kopf = ["@echo off", "setlocal EnableDelayedExpansion", f'set "LOGFILE={protokoll}"', f'set "DATA_DIR={daten}"',
            f'set "USERPROFILE={profil}"', "echo VOR_DEM_ABSCHNITT"]
    bat = tmp_path / "abschnitt.bat"
    bat.write_bytes(("\r\n".join(kopf + _abschnitt_6_von_7() + ["echo NACH_DEM_ABSCHNITT_OK"]) + "\r\n").encode("cp1252", errors="replace"))
    r = subprocess.run(["cmd", "/c", str(bat)], input=(antwort + "\r\n").encode(), capture_output=True, timeout=120,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return (r.stdout + r.stderr).decode("cp850", errors="replace"), profil / "Desktop", protokoll


@pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe gibt es nur unter Windows")
def test_der_backup_abschnitt_laeuft_bei_nein_bis_zum_ende(tmp_path):
    ausgabe, desktop, protokoll = _lauf(tmp_path, "n")
    assert "NACH_DEM_ABSCHNITT_OK" in ausgabe, ausgabe
    assert "kann syntaktisch an dieser Stelle nicht verarbeitet werden" not in ausgabe
    assert list(desktop.glob("PBP-Backup-*.zip")) == []


@pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe gibt es nur unter Windows")
def test_der_backup_abschnitt_legt_bei_ja_die_sicherung_an_und_laeuft_zum_ende(tmp_path):
    ausgabe, desktop, protokoll = _lauf(tmp_path, "j")
    assert "NACH_DEM_ABSCHNITT_OK" in ausgabe, ausgabe
    assert "kann syntaktisch an dieser Stelle nicht verarbeitet werden" not in ausgabe
    zips = list(desktop.glob("PBP-Backup-*.zip"))
    assert len(zips) == 1 and zips[0].stat().st_size > 0, (zips, ausgabe)
    assert "Desktop-Backup erstellt" in protokoll.read_text(encoding="utf-8", errors="replace")
