"""CLAUDE.md bleibt schlank, ihr Wissen bleibt erreichbar (H34).

CLAUDE.md wird in jede Sitzung geladen. Bis v1.7.139 war sie auf rund
505 KB gewachsen, weil jeder Release einen Stand-Block anhaengte. Seitdem
steht die Geschichte woertlich im Archiv und die Lehren verdichtet in
`docs/internal/lehren.md`; CLAUDE.md traegt nur den aktuellen Stand und
die harten Regeln.

Diese Tests halten die Groesse, pruefen, dass beide Nachschlagewerke da
sind, und dass keine harte Regel beim naechsten Kuerzen verloren geht.
Pfade relativ zu dieser Datei (DoD 8c): gruen auch aus einem fremden
Arbeitsverzeichnis.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLAUDE_MD = REPO / "CLAUDE.md"
ARCHIV = REPO / "docs" / "internal" / "claude-md-archiv.md"
LEHREN = REPO / "docs" / "internal" / "lehren.md"

# Ziel sind 30 KB; die Grenze laesst Luft fuer den aktuellen Stand.
GRENZE_BYTES = 35 * 1024


def _claude_md() -> str:
    return CLAUDE_MD.read_text(encoding="utf-8")


def test_claude_md_bleibt_unter_der_grenze():
    groesse = CLAUDE_MD.stat().st_size
    assert groesse <= GRENZE_BYTES, (
        f"CLAUDE.md hat {groesse} Bytes, erlaubt sind {GRENZE_BYTES}. "
        "Stand-Bloecke gehoeren in CHANGELOG.md bzw. docs/internal/lehren.md, "
        "nicht in CLAUDE.md.")


def test_archiv_existiert_mit_kopfzeile_und_vollem_inhalt():
    text = ARCHIV.read_text(encoding="utf-8")
    kopf = text.split("\n", 1)[0]
    assert kopf.startswith("Archiv der CLAUDE.md bis v1.7.139"), kopf
    # Das Archiv ist die alte Datei woertlich, nicht versehentlich gekuerzt:
    # juengster und aeltester Stand-Block und der letzte Abschnitt stehen drin.
    assert len(text.encode("utf-8")) > 400_000
    for marke in ("## Stand 2026-09-26 (v1.7.139 Stable)",
                  "## Stand 2026-08-25 (v1.7.23 Stable)",
                  "## Test-Helper fuer FastMCP 2.12+"):
        assert marke in text, f"Archiv unvollstaendig, es fehlt: {marke}"


def test_lehren_existieren_lueckenlos_nummeriert():
    text = LEHREN.read_text(encoding="utf-8")
    nummern = [int(n) for n in re.findall(r"^\*\*L(\d+)\.", text, re.M)]
    assert len(nummern) >= 25, f"nur {len(nummern)} Lehren in lehren.md"
    # CLAUDE.md verweist auf L-Nummern; sie muessen eindeutig sein.
    assert nummern == list(range(1, len(nummern) + 1)), nummern


def test_verweise_auf_lehren_zeigen_auf_vorhandene_regeln():
    vorhanden = set(re.findall(r"^\*\*(L\d+)\.",
                               LEHREN.read_text(encoding="utf-8"), re.M))
    verwiesen = set()
    for von, bis in re.findall(r"\bL(\d+)(?:–L(\d+))?\b", _claude_md()):
        verwiesen.update(f"L{n}" for n in range(int(von), int(bis or von) + 1))
    assert verwiesen, "CLAUDE.md verweist auf keine Lehre"
    assert verwiesen <= vorhanden, sorted(verwiesen - vorhanden)


# Je harte Regel eine Marke, an der sie in CLAUDE.md zu erkennen ist. Die
# Marken stehen je genau einmal in der Datei: eine Marke, die auch
# anderswo steht, bleibt gruen, wenn die Regel selbst verschwindet.
HARTE_REGELN = {
    "QA-Isolation": "assert str(tmpdir) in str(db.db_path)",
    "Master-Plan zuerst": "https://github.com/MadGapun/PBP/wiki/Master-Plan",
    "Master-Plan-First": "Master-Plan-First",
    "Wiki-Clone und Guards": "scripts/masterplan_pruefen.py",
    "Wiki-Kette ohne Pipe": "Reihenfolge ohne Pipe",
    "DoD / #675": "Session-Abschluss-Checkliste (DoD) — Dauer-Issue #675",
    "DoD 8a": "8a. **",
    "DoD 8b": "8b. **",
    "DoD 8c": "8c. **",
    "DoD 8d": "8d. **",
    "DoD 8e": "8e. **",
    "DoD 9 Firmennamen-Sweep": "9. **Firmennamen-Sweep",
    "issue_text_pruefen": "issue_text_pruefen(text=...)",
    "DSGVO-Pflicht": "## Issue-Erstellung — DSGVO-Pflicht",
    "DSGVO-Pruefer": "python scripts/scrub_pii.py --check < issue_body.md",
    "Release-Workflow": "## Release-Workflow",
    "Pre-Release-Issue-Check": "Pre-Release-Issue-Check",
    "Tag erst nach gruener CI": "Tag erst NACH gruener CI",
    "Installationsblock": "Doppelklick auf **`INSTALLIEREN.bat`**",
    "Token-Falle": "**Token-Falle:**",
    "Tag-Lock": "Nie `git push --tags`",
    "Bericht-Designprinzip": "## Bericht-Designprinzip",
    "Anti-DB-Bypass": "## Anti-DB-Bypass",
    "Firmen-Status": "firma_kontext(firmenname)",
    "Ablehnungsgruende": "## STRENG: keine eigenen Ablehnungsgruende",
    "Fit-Analyse-Verdict": "## Fit-Analyse-Verdict scharf zitieren",
    "Verdict nicht aus dem Score": "Der Verdict kommt NICHT aus dem Score",
    "Score keine Prozentzahl": "Der Score ist keine Prozentzahl",
    "Kritische DB-Helfer": "resolve_job_hash",
    "Mojibake-Repair": "s.encode('latin-1').decode('utf-8')",
    "Elwosa-Pflege": "test_all_pool_lines_pass_validator",
    "Umlaut-Regel": "geschuetzte_werte()",
    "Stand-Bloecke nicht hier": "Stand-Bloecke fuer neue Releases",
    "Zehn wichtigste Lehren": "## Die 10 wichtigsten Lehren",
}


def test_jede_harte_regel_steht_in_claude_md():
    text = _claude_md()
    fehlt = [name for name, marke in HARTE_REGELN.items() if marke not in text]
    assert not fehlt, f"harte Regeln fehlen in CLAUDE.md: {fehlt}"


def test_ablehnungsgruende_in_claude_md_entsprechen_dem_code():
    """Die Liste in CLAUDE.md ist die, die Claude befolgt; sie darf nicht
    hinter dem Code zurueckbleiben (bis v1.7.139 fehlten zwei Gruende)."""
    from bewerbungs_assistent.services.ablehnungsgruende import STANDARD_GRUENDE

    text = _claude_md()
    abschnitt = text.split("## STRENG: keine eigenen Ablehnungsgruende", 1)[1]
    block = abschnitt.split("```", 2)[1]
    in_doku = set(block.split())
    assert in_doku == set(STANDARD_GRUENDE), (
        f"nur in CLAUDE.md: {sorted(in_doku - set(STANDARD_GRUENDE))}, "
        f"nur im Code: {sorted(set(STANDARD_GRUENDE) - in_doku)}")
