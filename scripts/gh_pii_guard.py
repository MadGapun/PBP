"""PreToolUse-Guard: blockiert `gh`-Aufrufe, die PII nach GitHub tragen.

Hintergrund: Die Regel "vor jedem `gh issue create` den Scrubber laufen
lassen" steht seit dem 23.07.2026 in der Definition of Done — und wurde
danach trotzdem dreimal gebrochen (31.07. und 06.08.). Eine Regel, an die
sich jemand erinnern muss, ist keine Kontrolle. Dieser Hook prueft
mechanisch und laesst sich nicht vergessen.

Geprueft wird der Text, der tatsaechlich rausgeht:
  - Inline-Argumente (--body, --notes, --title, --comment, -m)
  - Dateien hinter --body-file / --notes-file
  - Heredocs im Kommando

Betroffene Kommandos: gh issue create/comment/edit, gh release create/edit,
gh pr create/comment/edit, gh api mit Body.

Rueckgabe an Claude Code:
  exit 0  -> durchlassen
  exit 2  -> blockieren, stderr geht als Begruendung an das Modell

Grenze, die man kennen muss: Dieser Hook sieht nur den Bash-Weg. Wird ein
Issue ueber den GitHub-MCP angelegt (Claude Desktop), greift er NICHT.
Dafuer ist der wiederkehrende Sweep (scripts/gh_pii_sweep.py) da.
"""
from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scrub_pii import find_pii  # noqa: E402

# Nur schreibende Kommandos — `gh issue list` oder `gh issue view` duerfen
# PII sehen, sie tragen ja nichts hinaus.
_RISKANT = re.compile(
    r"\bgh\s+(?:issue|pr)\s+(?:create|comment|edit)\b"
    r"|\bgh\s+release\s+(?:create|edit)\b"
    r"|\bgh\s+api\b(?=.*(?:-f|--field|--input)\b)"
)

_TEXT_FLAGS = {"--body", "-b", "--title", "-t", "--notes", "--comment",
               "-m", "--message", "--add-label"}
_FILE_FLAGS = {"--body-file", "-F", "--notes-file", "--input"}


def _texte_einsammeln(command: str) -> list[tuple[str, str]]:
    """Liefert (Herkunft, Text)-Paare fuer alles, was rausgehen wuerde."""
    out: list[tuple[str, str]] = []

    # Heredocs: <<'EOF' ... EOF
    for m in re.finditer(r"<<-?\s*'?(\w+)'?\n(.*?)\n\1", command, re.S):
        out.append(("Heredoc", m.group(2)))

    try:
        tokens = shlex.split(command)
    except ValueError:
        # Nicht parsebar (unbalancierte Quotes) — dann lieber den ganzen
        # Befehlstext pruefen, als stillschweigend durchzulassen.
        return out + [("Kommandozeile (nicht parsebar)", command)]

    for i, tok in enumerate(tokens):
        if i + 1 >= len(tokens):
            break
        wert = tokens[i + 1]
        if tok in _TEXT_FLAGS:
            out.append((f"Argument {tok}", wert))
        elif tok in _FILE_FLAGS:
            p = Path(wert)
            if p.is_file():
                try:
                    out.append((f"Datei {p.name}", p.read_text(
                        encoding="utf-8", errors="replace")))
                except OSError:
                    pass
    return out


def main() -> int:
    try:
        daten = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # Kein verwertbarer Input -> nicht blockieren

    if daten.get("tool_name") != "Bash":
        return 0
    command = (daten.get("tool_input") or {}).get("command", "") or ""
    if not _RISKANT.search(command):
        return 0

    funde: list[str] = []
    for herkunft, text in _texte_einsammeln(command):
        for treffer in find_pii(text):
            funde.append(f"  [{herkunft}] {treffer}")

    if not funde:
        return 0

    eindeutig = sorted(set(funde))
    print(
        "BLOCKIERT: Dieser gh-Aufruf wuerde personenbezogene Daten auf "
        "GitHub veroeffentlichen.\n\n"
        + "\n".join(eindeutig)
        + "\n\nGitHub-Issues sind oeffentlich, und die Edit-Historie bleibt "
        "auch nach einer Korrektur einsehbar — nachtraeglich anonymisieren "
        "hilft also nicht.\n"
        "Vorgehen: Firmen durch fiktive Platzhalter ersetzen (Liste "
        "FIKTIVE_FIRMEN in scripts/scrub_pii.py), Personen durch <PERSON>, "
        "Kontaktdaten weglassen. Danach erneut ausfuehren.\n"
        "Pruefen mit: python scripts/scrub_pii.py --check < datei.md",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
