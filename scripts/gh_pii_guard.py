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

Seit dem 02.09.2026 deckt der Hook AUCH den MCP-Weg ab. Vorher war das
seine bekannte Grenze — und genau dort ist sie ein zweites Mal
eingetreten: fuenf Issues vom 21. und 25.08. trugen reale Firmennamen,
obwohl alle fuenf seit dem 10.05. in der Erkennungsliste stehen. Der
Pruefer haette sie gefunden; er wurde nur nie aufgerufen, weil die
Issues ueber den GitHub-MCP entstanden und nicht ueber `gh`.

MERKE daraus: eine dokumentierte Luecke ist keine Warnung, sondern eine
Vorhersage. Sie wird eintreten, und zwar an genau der Stelle, an der sie
notiert ist.
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

# MCP-Werkzeuge, die Text nach draussen tragen. Der Servername steht im
# Toolnamen und ist bei manchen Servern eine UUID — deshalb wird nur der
# hintere Teil geprueft.
_MCP_SCHREIBT = re.compile(
    r"(?:^|__)(?:create|add|update|write|post|append|edit|reply|comment|push)"
    r"[a-z_]*(?:issue|comment|story|note|release|pull_request|wiki|"
    r"discussion|page|epic|goal|plan|decision|file)"
    r"|(?:issue|comment|story|note|release|pull_request|wiki|discussion|"
    r"page|epic|goal|plan|decision|file)[a-z_]*_"
    r"(?:create|add|update|write|post|append|edit|reply|push)",
    re.IGNORECASE,
)

# Felder, die bei MCP-Aufrufen nie Fliesstext tragen — sie zu pruefen
# erzeugt nur Fehlalarme (ein Slug wie `bw-papersystems` ist kein Satz,
# und ein Repo-Name gehoert dorthin).
_MCP_IGNORIEREN = {
    "owner", "repo", "slug", "url", "state", "method", "sha", "branch",
    "ref", "commit_id", "path", "side", "subject_type", "issue_number",
    "pull_number", "number", "id", "labels", "assignees", "milestone",
}


def _mcp_texte(wert, pfad: str = "") -> list[tuple[str, str]]:
    """Alle Zeichenketten aus einem MCP-tool_input, mit Herkunftspfad.

    Rekursiv, weil Bodies verschachtelt sein koennen (z.B. `writes`-
    Listen oder `fields`-Objekte).
    """
    out: list[tuple[str, str]] = []
    if isinstance(wert, str):
        if len(wert) >= 3:
            out.append((f"Feld {pfad or '?'}", wert))
    elif isinstance(wert, dict):
        for k, v in wert.items():
            if k in _MCP_IGNORIEREN:
                continue
            out.extend(_mcp_texte(v, f"{pfad}.{k}" if pfad else k))
    elif isinstance(wert, list):
        for i, v in enumerate(wert):
            out.extend(_mcp_texte(v, f"{pfad}[{i}]"))
    return out


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
        # Wie in scrub_pii: sys.stdin dekodiert unter Windows mit
        # cp1252 und zerstoert Umlaute im Kommandotext — der Guard
        # wuerde einen Firmennamen mit Umlaut dann NICHT erkennen.
        daten = json.loads(
            sys.stdin.buffer.read().decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, ValueError):
        return 0  # Kein verwertbarer Input -> nicht blockieren

    werkzeug = daten.get("tool_name") or ""
    eingabe = daten.get("tool_input") or {}

    if werkzeug == "Bash":
        command = eingabe.get("command", "") or ""
        if not _RISKANT.search(command):
            return 0
        quellen = _texte_einsammeln(command)
    elif werkzeug.startswith("mcp__"):
        # Lesende Werkzeuge tragen nichts hinaus und werden nicht
        # geprueft — sonst blockiert der Guard das Nachschlagen.
        if not _MCP_SCHREIBT.search(werkzeug):
            return 0
        quellen = _mcp_texte(eingabe)
    else:
        return 0

    funde: list[str] = []
    for herkunft, text in quellen:
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
