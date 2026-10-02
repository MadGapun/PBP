"""Sicherung der PBP-Datenbank vor einem Update (#1149, Punkt 2).

Aufruf (vom Installer):  python _sicherung_vor_update.py <pbp.db> <Sicherungsordner>

Bis v1.7.148 kopierte INSTALLIEREN.bat die Datei `pbp.db` einfach mit `copy`:

  * Die Datenbank läuft im WAL-Modus. Was zuletzt geschrieben wurde, steht in
    `pbp.db-wal`, nicht in `pbp.db`. Bei einem Update laufen meist noch Claude
    und PBP, die Kopie war dann unvollständig (gemessen: bei offener
    Verbindung und 50 Schreibvorgängen hatte sie 4 KB und „no such table“,
    die SQLite-Sicherung alle 50 Zeilen).
  * Die Erfolgsmeldung stand unbedingt da, auch wenn das Kopieren scheiterte.
  * Der Dateiname war fest und wurde bei jedem Update überschrieben — nach dem
    zweiten Update war der Stand vor dem ersten weg.

Jetzt: die SQLite-Sicherungsfunktion (liest einen stimmigen Stand, auch bei
offener Verbindung und mit dem WAL), ein Name mit Zeitstempel (`-vor_update`,
derselbe wie in `database.create_backup`), eine Leseprobe der fertigen
Sicherung und eine ehrliche Meldung. Nur die Standardbibliothek: der
Installer ruft das mit dem mitgelieferten Python auf, bevor Pakete da sind.

Ausgabe: eine Zeile — `OK <Pfad>` oder `FEHLER <Grund>`.
Rückgabewert: 0 = Sicherung geschrieben und gelesen, 2 = keine Datenbank,
3 = Sichern fehlgeschlagen, 4 = Sicherung nicht lesbar, 64 = falscher Aufruf.
"""
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

#: Wie viele Sicherungen vor einem Update bleiben (wie in database.create_backup).
BEHALTEN = 5
_MUSTER = re.compile(r"^pbp-backup-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-vor_update(-\d+)?\.db$")


class _Unlesbar(RuntimeError):
    """Die Sicherung wurde geschrieben, ließ sich aber nicht lesen."""


def sichern(db: Path, ordner: Path, behalten: int = BEHALTEN) -> Path:
    """Schreibt eine Sicherung von `db` nach `ordner` und gibt ihren Pfad zurück.

    Wirft RuntimeError mit einer lesbaren Meldung, wenn etwas schiefgeht.
    """
    if not db.is_file():
        raise FileNotFoundError(f"Keine Datenbank unter {db}")
    ordner.mkdir(parents=True, exist_ok=True)
    stempel = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ziel = ordner / f"pbp-backup-{stempel}-vor_update.db"
    zaehler = 1
    while ziel.exists():  # zwei Sicherungen in derselben Sekunde überschreiben sich nicht
        ziel = ordner / f"pbp-backup-{stempel}-vor_update-{zaehler}.db"
        zaehler += 1
    quelle = sqlite3.connect(str(db), timeout=30)
    try:
        quelle.execute("PRAGMA busy_timeout=30000")
        ziel_verbindung = sqlite3.connect(str(ziel))
        try:
            quelle.backup(ziel_verbindung)
        finally:
            ziel_verbindung.close()
    except sqlite3.Error as exc:
        _loeschen(ziel)
        raise RuntimeError(f"SQLite konnte die Datenbank nicht sichern: {exc}") from exc
    finally:
        quelle.close()
    _leseprobe(ziel)
    _aufraeumen(ordner, behalten, ziel)
    return ziel


def _leseprobe(ziel: Path) -> None:
    """Die Sicherung wird gelesen — eine Datei, die nur existiert, ist noch keine Sicherung."""
    try:
        verbindung = sqlite3.connect(str(ziel))
        try:
            urteil = verbindung.execute("PRAGMA integrity_check").fetchone()[0]
            tabellen = verbindung.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        finally:
            verbindung.close()
    except sqlite3.Error as exc:
        _loeschen(ziel)
        raise _Unlesbar(f"Die Sicherung ließ sich nicht lesen: {exc}") from exc
    if urteil != "ok" or tabellen < 1:
        _loeschen(ziel)
        raise _Unlesbar(f"Die Sicherung ist unvollständig (Prüfung: {urteil}, Tabellen: {tabellen})")


def _aufraeumen(ordner: Path, behalten: int, aktuell: Path) -> None:
    """Behält die neuesten Sicherungen vor einem Update; andere Dateien bleiben unberührt."""
    try:
        alle = sorted((p for p in ordner.iterdir() if _MUSTER.match(p.name)),
                      key=lambda p: p.stat().st_mtime)
        while len(alle) > behalten:
            aelteste = alle.pop(0)
            if aelteste != aktuell:
                aelteste.unlink()
    except OSError:
        pass  # eine alte Sicherung, die sich nicht löschen lässt, ist kein Grund zu scheitern


def _loeschen(pfad: Path) -> None:
    try:
        pfad.unlink()
    except OSError:
        pass



def _ausgabe_absichern():
    """Die Ausgabe nennt Pfade, und die tragen den Benutzernamen. Geht sie in eine Datei (Installer-Protokoll), gilt die Zeichentabelle
    des Rechners; ein Zeichen ausserhalb davon (ł, ş, griechisch) darf das Drucken nicht zum Absturz bringen (L44)."""
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(errors="backslashreplace")
        except Exception:
            pass


def main(argv: list) -> int:
    _ausgabe_absichern()
    if len(argv) != 3:
        print("FEHLER Aufruf: _sicherung_vor_update.py <pbp.db> <Sicherungsordner>")
        return 64
    db, ordner = Path(argv[1]), Path(argv[2])
    try:
        ziel = sichern(db, ordner)
    except FileNotFoundError as exc:
        print(f"FEHLER {exc}")
        return 2
    except _Unlesbar as exc:
        print(f"FEHLER {exc}")
        return 4
    except (RuntimeError, OSError) as exc:
        print(f"FEHLER {exc}")
        return 3
    print(f"OK {ziel}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
