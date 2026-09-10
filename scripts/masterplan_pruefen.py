"""Prueft die Tabellen des Master-Plans auf kaputte Zeilen.

Der Master-Plan liegt im Wiki (eigenes Git-Repo) und wird regelmaessig
per Skript umgebaut — Status auf ✅ setzen, Ergebnis anhaengen. Genau
das ist dreimal schiefgegangen:

* **v1.7.67**: ein Skript haengte Issue- und Wiki-Spalte ein zweites Mal
  an; sechs Zeilen hatten neun statt sieben Felder und rendern falsch.
* **v1.7.69**: ein Skript schrieb den Status in das Feld NACH dem
  letzten Rohr. Die Zeile behielt ihre Spaltenzahl, die Statuszelle
  blieb auf ⬜ — und das ✅ stand ausserhalb der Tabelle. Der Plan
  meldete "nicht begonnen" fuer eine ausgelieferte Arbeit.

Der zweite Fall ist der lehrreiche: **eine Zaehlung der Spalten haette
ihn nicht gefunden**, und die Gegenprobe von damals hat den Fehler sogar
bestaetigt, weil sie denselben falschen Index gelesen hat, in den das
Skript geschrieben hatte. Deshalb prueft dieses Skript den INHALT der
Statuszelle und den Rest hinter dem letzten Rohr — nicht einen Index,
den sich jemand ausgedacht hat.

Aufruf vor jedem Wiki-Push:

    python scripts/masterplan_pruefen.py D:\\MAD\\Documents\\Entwicklung\\PBP.wiki

Exit 0 = sauber, Exit 1 = Befunde (mit Zeilennummern).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Die Status-Vokabeln des Plans. Mehr gibt es nicht — ein vierter Wert
# waere eine Vokabel ohne Bedeutung (#988).
STATUS = {"⬜", "🟨", "✅"}

TRENNZEILE = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")

# Ein maskiertes Rohr rendert als ZEICHEN und teilt keine Zelle.
# Der erste Entwurf zaehlte es mit und meldete daraufhin die eigene
# korrekte Reparatur als Defekt — ein Pruefer, der bei korrektem
# Ergebnis Alarm gibt, wird nach dem zweiten Mal ignoriert (#929).
#
# Bewusst ein String-Replace und kein Regex: der zweite Entwurf schrieb
# das Muster per Heredoc-Skript, und die Backslashes kamen verstuemmelt
# an — `\\|` heisst "Backslash ODER nichts" und matchte ueberall. Das
# ist die Falle aus v1.7.24 MERKE (4), und sie kostet hier nichts, weil
# ein simples replace dieselbe Arbeit tut.
MASKIERTES_ROHR = chr(92) + "|"
# Eine Positions-Zeile beginnt mit einem Cluster-Kuerzel: | A12 |, | G7 |
POSITION = re.compile(r"^\|\s*[A-J]\d+\s*\|")


def pruefe(pfad: Path) -> list[str]:
    befunde: list[str] = []
    kopf_rohre: int | None = None
    status_spalte: int | None = None

    for nr, zeile in enumerate(pfad.read_text(encoding="utf-8").split("\n"), 1):
        if not zeile.lstrip().startswith("|"):
            kopf_rohre, status_spalte = None, None
            continue
        if TRENNZEILE.match(zeile):
            continue
        zelltrenner = zeile.replace(MASKIERTES_ROHR, "")
        rohre = zelltrenner.count("|")
        if kopf_rohre is None:
            kopf_rohre = rohre
            # Welche Spalte traegt den Status? Die Kopfzeile sagt es —
            # nicht eine Annahme ueber die Reihenfolge.
            spalten = [f.strip().lower() for f in zelltrenner.split("|")]
            status_spalte = next(
                (i for i, s in enumerate(spalten) if s == "status"), None)
            continue

        # (1) Spaltenzahl — der Fall aus v1.7.67.
        if rohre != kopf_rohre:
            befunde.append(
                f"{pfad.name}:{nr}: {rohre} Rohre statt {kopf_rohre} "
                f"— {zeile[:60]}")
            continue

        if not POSITION.match(zeile):
            continue

        felder = zelltrenner.split("|")

        # (2) Nach dem letzten Rohr darf NICHTS mehr stehen — der Fall
        # aus v1.7.69. Was dort landet, ist unsichtbar in der Tabelle.
        if felder[-1].strip():
            befunde.append(
                f"{pfad.name}:{nr}: Text hinter der letzten Spalte "
                f"({felder[-1].strip()[:20]!r}) — {zeile[:40]}")

        # (3) Die Statuszelle muss genau eine Status-Vokabel tragen —
        # aber NUR dort, wo die Kopfzeile ueberhaupt eine Status-Spalte
        # deklariert. Der erste Entwurf nahm "die letzte Zelle" an und
        # meldete daraufhin 21 Fehlalarme auf den Unterseiten, deren
        # letzte Spalte "Ort"/"Datei" heisst. Das ist die Lehre aus
        # #1008/#993: bei einem Paritaets-Guard zuerst klaeren, WELCHE
        # zwei Dinge verglichen werden.
        if status_spalte is None or status_spalte >= len(felder):
            continue
        status = felder[status_spalte].strip()
        if not any(status.startswith(s) for s in STATUS):
            befunde.append(
                f"{pfad.name}:{nr}: Statuszelle ist {status[:25]!r} — "
                f"erwartet eines von {' '.join(sorted(STATUS))}")

    return befunde


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    wiki = Path(argv[1])
    if not wiki.is_dir():
        print(f"Kein Verzeichnis: {wiki}")
        return 2

    dateien = sorted(
        [p for p in [wiki / "Master-Plan.md"] if p.exists()]
        + sorted(wiki.glob("Plan-*.md")))
    if not dateien:
        print(f"Keine Plan-Dateien in {wiki}")
        return 2

    alle: list[str] = []
    for datei in dateien:
        alle.extend(pruefe(datei))

    if alle:
        print(f"{len(alle)} Befund(e):")
        for b in alle:
            print("  " + b)
        return 1
    print(f"{len(dateien)} Plan-Datei(en) geprueft — keine kaputten Zeilen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
