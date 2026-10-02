"""PreToolUse-Guard: blockiert `gh`-Aufrufe, die PII nach GitHub tragen.

Hintergrund: Die Regel "vor jedem `gh issue create` den Scrubber laufen
lassen" steht seit dem 23.07.2026 in der Definition of Done — und wurde
danach trotzdem dreimal gebrochen (31.07. und 06.08.). Eine Regel, an die
sich jemand erinnern muss, ist keine Kontrolle. Dieser Hook prueft
mechanisch und laesst sich nicht vergessen.

Geprueft wird der Text, der tatsaechlich rausgeht:
  - Inline-Argumente (--body, --notes, --title, --comment, --desc, ...)
  - Dateien hinter --body-file / --notes-file / -F / --input und die
    Dateien eines `gh gist create`
  - Felder von `gh api` (-f, -F, --field, --raw-field, --input)
  - Heredocs im Kommando

Seit v1.7.148 (#1137) liest der Hook die `gh`-Kommandozeile STRUKTURIERT.
Vorher suchte er einen festen Wortlaut ("gh issue create ..."), und jede
Abweichung ging unbemerkt durch: `gh -R <Repo> issue create` (gaengig!),
`gh issue close --comment`, `gh pr review --body`, `gh pr merge --body`,
`gh gist create`, `gh api -F body=...` und `--raw-field`. Jetzt zaehlt jede
Aktion, die nicht ausdruecklich lesend ist (list, view, status, diff, ...),
als schreibend.

Ein Text, der erst zur Laufzeit entsteht (`--body "$(cat datei)"`, eine
Shell-Variable, `--body-file -` aus einer unbekannten Pipe), ist NICHT
pruefbar. Der Hook behandelt ihn als Fund und blockiert, statt ihn zu
ignorieren: ein Schutz, der bei der haeufigsten Schreibweise stillschweigend
nichts pruefen kann, ist keiner. Variablen, die im selben Kommando mit einem
festen Wert gesetzt werden (`S=/pfad && gh ... --body-file "$S/x.md"`),
setzt der Hook selbst ein.

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
import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scrub_pii import find_pii  # noqa: E402

# Kommt `gh` als Wort im Kommando vor? Nur dann lohnt die Zerlegung.
_GH_WORT = re.compile(r"(?<![\w./\\-])gh(?:\.exe)?(?![\w-])")

# Aktionen, die nichts nach GitHub schreiben — `gh issue list` oder
# `gh issue view` duerfen PII sehen, sie tragen ja nichts hinaus.
_LESEND = {"list", "view", "status", "diff", "checks", "checkout", "download",
           "browse", "clone", "watch", "ls", "search", "completion", "help",
           "version", "token", "auth", "config", "alias", "extension", "cache"}

_TEXT_FLAGS = {"--body", "-b", "--title", "-t", "--notes", "-n", "--comment",
               "-c", "--message", "-m", "--subject", "--desc", "--description",
               "-d", "--add-label", "--label"}
_FILE_FLAGS = {"--body-file", "-F", "--notes-file"}
_API_TEXT = {"-f", "--raw-field", "-F", "--field"}
_API_DATEI = {"--input"}

# Ein Token, das wie ein Schalter aussieht ("--body", "-F"), nicht wie Text
# ("- Punkt eins").
_SCHALTER = re.compile(r"^-{1,2}[A-Za-z][\w-]*(?:=.*)?$")
# Wird hier erst zur Laufzeit etwas eingesetzt?
_EINSATZ = re.compile(r"\$[A-Za-z_{(]|`")
_ZUWEISUNG = re.compile(r"^(?:export\s+)?([A-Za-z_]\w*)=(.*)$", re.S)

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


# ── Bash: die gh-Kommandozeile lesen (#1137) ───────────────────────────

_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[ \t]*\n(.*?)\n[ \t]*\2[ \t]*(?=\n|$)", re.S)


def _segmente(command: str) -> list[str]:
    """Teilt eine Kommandozeile an ; & | und Zeilenumbruechen — aber nur
    ausserhalb von Anfuehrungszeichen."""
    segmente, aktuell = [], []
    quote = None
    i = 0
    while i < len(command):
        ch = command[i]
        if quote:
            aktuell.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(command):
                aktuell.append(command[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch == "\\" and i + 1 < len(command):
            aktuell.append(ch)
            aktuell.append(command[i + 1])
            i += 2
            continue
        elif ch in "'\"":
            quote = ch
            aktuell.append(ch)
        elif ch in ";&|\n":
            segmente.append("".join(aktuell))
            aktuell = []
        else:
            aktuell.append(ch)
        i += 1
    segmente.append("".join(aktuell))
    return [s.strip() for s in segmente if s.strip()]


def _msys_pfad(wert: str) -> str:
    """'/c/Temp/x' -> 'C:/Temp/x' (Git-Bash-Schreibweise unter Windows)."""
    m = re.match(r"^/([A-Za-z])/(.*)$", wert)
    return f"{m.group(1).upper()}:/{m.group(2)}" if m and os.name == "nt" else wert


def _datei_lesen(wert: str, basis: Path | None) -> str | None:
    """Der Inhalt der Datei oder None, wenn sie sich nicht finden laesst."""
    kandidaten = [Path(_msys_pfad(wert))]
    if basis is not None and not Path(_msys_pfad(wert)).is_absolute():
        kandidaten.insert(0, basis / wert)
    for p in kandidaten:
        try:
            if p.is_file():
                return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return None


def _einsetzen(wert: str, variablen: dict) -> str:
    """Setzt $NAME und ${NAME} ein, soweit sie im Kommando fest gesetzt sind."""
    def _ersatz(m):
        name = m.group(1) or m.group(2)
        return variablen.get(name, m.group(0))
    return re.sub(r"\$(?:\{(\w+)\}|(\w+))", _ersatz, wert)


def _schalter_wert(tokens: list[str], k: int) -> tuple[str, str | None, int]:
    """(Schalter, Wert oder None, Schrittweite) fuer tokens[k]."""
    tok = tokens[k]
    if tok.startswith("--") and "=" in tok:
        flag, wert = tok.split("=", 1)
        return flag, wert, 1
    if k + 1 < len(tokens) and not _SCHALTER.match(tokens[k + 1]):
        return tok, tokens[k + 1], 2
    return tok, None, 1


def _gh_texte(tokens: list[str], variablen: dict, basis: Path | None,
              stdin_texte: list[tuple[str, str]], hat_heredoc: bool
              ) -> tuple[list[tuple[str, str]], list[str]]:
    """(Herkunft, Text)-Paare und die Gruende, aus denen etwas NICHT pruefbar ist."""
    texte: list[tuple[str, str]] = []
    offen: list[str] = []

    # Globale Schalter vor oder zwischen Gruppe und Aktion entfernen.
    t: list[str] = []
    i = 0
    while i < len(tokens):
        if tokens[i] in ("-R", "--repo", "--hostname") and i + 1 < len(tokens):
            i += 2
            continue
        if tokens[i].startswith(("--repo=", "--hostname=")):
            i += 1
            continue
        t.append(tokens[i])
        i += 1
    worte = [x for x in t if not x.startswith("-")]
    gruppe = worte[0] if worte else ""
    aktion = worte[1] if len(worte) > 1 else ""
    if not gruppe or gruppe in _LESEND:
        return texte, offen
    if gruppe != "api" and aktion in _LESEND:
        return texte, offen

    def _text(herkunft: str, wert: str):
        wert = _einsetzen(wert, variablen)
        if _EINSATZ.search(wert) and not hat_heredoc:
            offen.append(f"{herkunft}: der Text entsteht erst beim Ausfuehren ({wert[:60]!r})")
        texte.append((herkunft, wert))

    def _datei(herkunft: str, wert: str):
        wert = _einsetzen(wert, variablen)
        if wert == "-":
            if stdin_texte:
                texte.extend(stdin_texte)
            elif not hat_heredoc:
                offen.append(f"{herkunft}: der Text kommt von der Standardeingabe, "
                             "und die Quelle (Datei, Heredoc) ist nicht erkennbar")
            return
        if _EINSATZ.search(wert):
            offen.append(f"{herkunft}: der Dateiname entsteht erst beim Ausfuehren ({wert[:60]!r})")
            return
        inhalt = _datei_lesen(wert, basis)
        if inhalt is None:
            offen.append(f"{herkunft}: die Datei {wert!r} laesst sich nicht lesen")
        else:
            texte.append((f"Datei {Path(wert).name}", inhalt))

    k = 0
    while k < len(t):
        tok = t[k]
        if not tok.startswith("-"):
            k += 1
            continue
        flag, wert, schritt = _schalter_wert(t, k)
        k += schritt
        if wert is None:
            continue
        if gruppe == "api":
            if flag in _API_TEXT:
                # key=value; bei -F/--field heisst "@datei": Inhalt aus der Datei.
                schluessel, _, rest = wert.partition("=")
                if flag in ("-F", "--field") and rest.startswith("@"):
                    _datei(f"Feld {schluessel}", rest[1:])
                else:
                    _text(f"Argument {flag} {schluessel}", rest or wert)
            elif flag in _API_DATEI:
                _datei(f"Argument {flag}", wert)
        elif flag in _FILE_FLAGS:
            _datei(f"Argument {flag}", wert)
        elif flag in _TEXT_FLAGS:
            _text(f"Argument {flag}", wert)

    # gh gist create <Dateien>: der Inhalt der Dateien geht hinaus.
    if gruppe == "gist" and aktion in ("create", "edit"):
        for wort in worte[2:]:
            if wort == "-":
                _datei("gist create", "-")
            else:
                _datei("gist create", wort)
    return texte, offen


def _texte_einsammeln(command: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Liefert (Herkunft, Text)-Paare fuer alles, was rausgehen wuerde, und die
    Gruende, aus denen ein Text nicht pruefbar ist."""
    out: list[tuple[str, str]] = []
    offen: list[str] = []

    # Heredocs: <<'EOF' ... EOF — erst herausnehmen, dann zerlegen.
    heredocs = [m.group(3) for m in _HEREDOC.finditer(command)]
    for text in heredocs:
        out.append(("Heredoc", text))
    ohne = _HEREDOC.sub("<<HEREDOC", command)
    hat_heredoc = bool(heredocs)

    variablen: dict[str, str] = {}
    basis: Path | None = None
    vorher: list[str] = []
    for seg in _segmente(ohne):
        try:
            tokens = shlex.split(seg)
        except ValueError:
            if _GH_WORT.search(seg):
                # Nicht parsebar (unbalancierte Quotes) — dann lieber den ganzen
                # Text pruefen, als stillschweigend durchzulassen.
                out.append(("Kommandozeile (nicht parsebar)", seg))
            continue
        if not tokens:
            continue
        # Zuweisungen (auch "export X=..." und "X=... gh ...") merken.
        j = 0
        while j < len(tokens) and (tokens[j] == "export" or _ZUWEISUNG.match(tokens[j])):
            m = _ZUWEISUNG.match(tokens[j])
            if m:
                variablen[m.group(1)] = _einsetzen(m.group(2), variablen)
            j += 1
        tokens = tokens[j:]
        if not tokens:
            vorher.append(seg)
            continue
        if tokens[0] == "cd" and len(tokens) > 1:
            ziel = _einsetzen(tokens[1], variablen)
            p = Path(_msys_pfad(ziel))
            basis = p if p.is_absolute() or basis is None else basis / p
            vorher.append(seg)
            continue
        gh_idx = next((n for n, tk in enumerate(tokens)
                       if Path(tk).name in ("gh", "gh.exe")), None)
        if gh_idx is None:
            vorher.append(seg)
            continue

        # Woher koennte die Standardeingabe kommen? `< datei`, `cat datei |`.
        stdin: list[tuple[str, str]] = []
        for n, tk in enumerate(tokens):
            if tk == "<" and n + 1 < len(tokens):
                inhalt = _datei_lesen(_einsetzen(tokens[n + 1], variablen), basis)
                if inhalt is not None:
                    stdin.append((f"Datei {Path(tokens[n + 1]).name}", inhalt))
        if vorher:
            try:
                vt = shlex.split(vorher[-1])
            except ValueError:
                vt = []
            if vt and vt[0] in ("cat", "type") and len(vt) > 1:
                inhalt = _datei_lesen(_einsetzen(vt[1], variablen), basis)
                if inhalt is not None:
                    stdin.append((f"Datei {Path(vt[1]).name}", inhalt))
            elif vt and vt[0] in ("echo", "printf") and len(vt) > 1:
                stdin.append(("Standardeingabe", " ".join(vt[1:])))
        t, o = _gh_texte(tokens[gh_idx + 1:], variablen, basis, stdin, hat_heredoc)
        out.extend(t)
        offen.extend(o)
        vorher.append(seg)
    return out, offen


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
    offen: list[str] = []

    if werkzeug == "Bash":
        command = eingabe.get("command", "") or ""
        if not _GH_WORT.search(command):
            return 0
        quellen, offen = _texte_einsammeln(command)
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

    if not funde and not offen:
        return 0

    if funde:
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

    print(
        "BLOCKIERT: Der Text dieses gh-Aufrufs laesst sich vorab nicht pruefen "
        "(#1137) — und was sich nicht pruefen laesst, geht nicht ungeprueft "
        "nach GitHub.\n\n"
        + "\n".join(f"  - {o}" for o in sorted(set(offen)))
        + "\n\nVorgehen: den Text in eine Datei schreiben, mit "
        "`python scripts/scrub_pii.py --check < datei.md` pruefen und mit "
        "`--body-file <voller Pfad>` uebergeben — oder den Text direkt als "
        "Argument/Heredoc angeben. Variablen, die im selben Kommando fest "
        "gesetzt werden (`S=/pfad && gh ... --body-file \"$S/x.md\"`), setzt "
        "der Hook selbst ein.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
