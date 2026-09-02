"""Der PII-Guard deckt auch den MCP-Weg ab (v1.7.24).

Vorgeschichte: die Regel "vor jedem `gh issue create` den Scrubber
laufen lassen" steht seit dem 23.07.2026 in der Definition of Done. Sie
wurde danach gebrochen, deshalb kam am 07.08. der PreToolUse-Hook dazu
— mit einer ausdruecklich notierten Grenze: er sieht nur den Bash-Weg.

Am 02.09.2026 ist genau diese Grenze eingetreten. Fuenf Issues vom
21./25.08. trugen reale Firmennamen, obwohl alle seit dem 10.05. in der
Erkennungsliste stehen. Der Pruefer haette sie gefunden; er wurde nur
nie aufgerufen, weil die Issues ueber den GitHub-MCP entstanden.

MERKE: eine dokumentierte Luecke ist keine Warnung, sondern eine
Vorhersage.

Zur Testgestaltung: hier stehen bewusst KEINE realen Firmennamen. Die
Namenserkennung selbst hat ihre Tests in `test_scrub_pii_erkennung.py`;
geprueft wird hier die Verdrahtung — erreichen MCP-Eingaben den Pruefer
ueberhaupt, und wird Lesen nicht faelschlich blockiert. Als Ausloeser
genuegt dafuer eine generische Fundstelle (Telefonnummer).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[1] / "scripts" / "gh_pii_guard.py"

# Generische PII, die der Pruefer unabhaengig von jeder Firmenliste
# findet — damit dieser Test keine realen Namen ins Repo traegt.
MIT_PII = "Rueckfragen bitte an +49 40 123456789."
OHNE_PII = "Die Musterfirma GmbH dient hier als Platzhalter."


def _guard(payload: dict) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(GUARD)],
                       input=json.dumps(payload).encode("utf-8"),
                       capture_output=True)
    return r.returncode, r.stderr.decode("utf-8", "replace")


def test_guard_findet_pii_generell():
    """Absicherung des Tests selbst: schlaegt der Ausloeser ueberhaupt an?

    Ohne diese Gegenprobe koennten alle folgenden Tests gruen sein, weil
    nichts erkannt wird — derselbe Fehlertyp, den der Guard verhindern
    soll.
    """
    sys.path.insert(0, str(GUARD.parent))
    from scrub_pii import find_pii
    assert find_pii(MIT_PII), "Testausloeser wird nicht erkannt"
    assert not find_pii(OHNE_PII)


# ── Der Weg, der bisher fehlte ───────────────────────────────────────

@pytest.mark.parametrize("werkzeug", [
    "mcp__github__issue_write",
    "mcp__github__add_issue_comment",
    "mcp__github__create_pull_request",
    "mcp__github__add_reply_to_pull_request_comment",
])
def test_mcp_schreibzugriff_wird_geprueft(werkzeug):
    code, meldung = _guard({
        "tool_name": werkzeug,
        "tool_input": {"owner": "MadGapun", "repo": "PBP",
                       "title": "Beliebig", "body": MIT_PII},
    })
    assert code == 2, f"{werkzeug} wurde nicht geprueft"
    assert "BLOCKIERT" in meldung


def test_mcp_mit_uuid_servername_wird_erfasst():
    """Manche Server tragen eine UUID im Toolnamen — der Guard darf
    nicht am Servernamen haengen."""
    code, _ = _guard({
        "tool_name": "mcp__8d01a609-b0bd-4a29-baca-2e00e7280b03__create_issue",
        "tool_input": {"slug": "beispiel", "title": "X", "body": MIT_PII},
    })
    assert code == 2


def test_verschachtelte_felder_werden_erreicht():
    """Bodies koennen in Listen oder Unterobjekten stecken."""
    code, _ = _guard({
        "tool_name": "mcp__github__push_files",
        "tool_input": {"owner": "MadGapun", "repo": "PBP",
                       "files": [{"path": "a.md", "content": MIT_PII}]},
    })
    assert code == 2


# ── Die Gegenrichtung: nicht ueberschiessen ──────────────────────────

@pytest.mark.parametrize("werkzeug", [
    "mcp__github__issue_read",
    "mcp__github__list_issues",
    "mcp__github__get_issue",
    "mcp__github__search_issues",
])
def test_mcp_lesezugriff_wird_nicht_blockiert(werkzeug):
    """Ein Guard, der das Nachschlagen blockiert, wird abgeschaltet."""
    code, _ = _guard({
        "tool_name": werkzeug,
        "tool_input": {"owner": "MadGapun", "repo": "PBP", "query": MIT_PII},
    })
    assert code == 0, f"{werkzeug} wurde faelschlich blockiert"


def test_sauberer_mcp_aufruf_geht_durch():
    code, _ = _guard({
        "tool_name": "mcp__github__issue_write",
        "tool_input": {"method": "create", "owner": "MadGapun", "repo": "PBP",
                       "title": "Scoring dokumentieren", "body": OHNE_PII},
    })
    assert code == 0


def test_technische_felder_erzeugen_keinen_fehlalarm():
    """Slugs, Hashes und Repo-Namen sind kein Fliesstext. Ein Guard, der
    dort anschlaegt, wird nach dem zweiten Mal ignoriert."""
    code, meldung = _guard({
        "tool_name": "mcp__github__issue_write",
        "tool_input": {"method": "update", "owner": "MadGapun", "repo": "PBP",
                       "issue_number": 42, "state": "closed",
                       "sha": "aa8946fcbe6c8bb977797c", "branch": "main",
                       "title": "Aufraeumen", "body": OHNE_PII},
    })
    assert code == 0, meldung


def test_fremdes_werkzeug_wird_durchgelassen():
    code, _ = _guard({"tool_name": "Read",
                      "tool_input": {"file_path": "/tmp/beliebig.md"}})
    assert code == 0


# ── Der Bash-Weg bleibt unveraendert ─────────────────────────────────

def test_bash_weg_blockiert_weiterhin():
    code, _ = _guard({
        "tool_name": "Bash",
        "tool_input": {"command": f'gh issue create --title "X" --body "{MIT_PII}"'},
    })
    assert code == 2


def test_bash_lesen_bleibt_frei():
    code, _ = _guard({
        "tool_name": "Bash",
        "tool_input": {"command": "gh issue list --state open"},
    })
    assert code == 0


# ── Die Verdrahtung selbst ───────────────────────────────────────────

def test_hook_ist_fuer_mcp_registriert():
    """Der beste Guard nuetzt nichts, wenn ihn niemand aufruft — genau
    das war der Fehler."""
    conf = json.loads(
        (Path(__file__).resolve().parents[1] / ".claude" / "settings.json")
        .read_text(encoding="utf-8"))
    matcher = [e.get("matcher", "")
               for e in conf["hooks"]["PreToolUse"]]
    assert any("mcp" in m.lower() for m in matcher), (
        f"Kein PreToolUse-Matcher fuer MCP-Werkzeuge: {matcher}")
    assert any(m == "Bash" for m in matcher), "Bash-Weg verlorengegangen"
