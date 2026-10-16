"""#1148 Punkt 4: Zählerstände. Die Zahl der Werkzeuge stand mit 47 bis 281 in Dokumenten, Docstrings und im Wiki — jede eine
Momentaufnahme, keine mit dem Programm verbunden.

Jetzt: gezählt wird zur Laufzeit (`scripts/werkzeug_inventar.py`, `pbp_capabilities`); Dokumente, die eine Zahl nennen müssen, tragen
genau diese (README und CLAUDE.md je Release); alle anderen tragen keine. Das Wiki prüft das Skript gegen eine Klon-Kopie
(`--wiki`), und `--wiki-ergaenzen` schreibt die fehlenden Werkzeuge in einen erzeugten Abschnitt.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import werkzeug_inventar as inv  # noqa: E402


@pytest.fixture(scope="module")
def inventar():
    return inv.inventar()


def _lies(*teile):
    return ROOT.joinpath(*teile).read_text(encoding="utf-8-sig")


# ── das Inventar selbst ────────────────────────────────────────────────────────────────

def test_das_inventar_zaehlt_dasselbe_wie_die_registrierung(inventar, tmp_path):
    import test_mcp_registry as reg
    mcp, db = reg._build_test_server(tmp_path)
    try:
        namen, _, _ = reg._collect_names(mcp)
    finally:
        db.close()
    assert set(inventar["namen"]) == namen and inventar["gesamt"] == len(namen)


def test_jedes_werkzeug_hat_ein_modul_und_eine_beschreibung(inventar):
    assert all(m and m != "?" for m in inventar["namen"].values())
    assert sum(len(v) for v in inventar["module"].values()) == inventar["gesamt"]
    leer = [n for n, b in inventar["beschreibungen"].items() if not b.strip()]
    assert not leer, leer


# ── Dokumente im Repo ──────────────────────────────────────────────────────────────────

ZAHL = re.compile(r"\b([0-9]{2,3})\s+(?:MCP-)?(?:Werkzeuge|Tools)\b")


def test_readme_und_claude_md_nennen_die_laufzeitzahl(inventar):
    n = inventar["gesamt"]
    for datei in ("README.md", "CLAUDE.md"):
        for treffer in ZAHL.findall(_lies(datei)):
            assert int(treffer) == n, f"{datei} nennt {treffer} Werkzeuge, das Programm hat {n}"


def test_der_neueste_changelog_eintrag_nennt_die_laufzeitzahl(inventar):
    text = _lies("CHANGELOG.md")
    kopf = re.search(r"^## \[", text, re.M)
    naechster = re.search(r"^## \[", text[kopf.end():], re.M)
    eintrag = text[kopf.start(): kopf.end() + naechster.start()]
    zahlen = [int(z) for z in ZAHL.findall(eintrag)]
    assert zahlen, "der Eintrag nennt keine Werkzeugzahl (der Fuss gehoert zur Vorlage)"
    assert all(z == inventar["gesamt"] for z in zahlen), (zahlen, inventar["gesamt"])


@pytest.mark.parametrize("datei", ["AGENTS.md", "CONTRIBUTING.md", "docs/architecture.md",
                                   "src/bewerbungs_assistent/tools/__init__.py", "src/bewerbungs_assistent/tools/analyse.py",
                                   "src/bewerbungs_assistent/tools/bewerbungen.py", "src/bewerbungs_assistent/tools/profil.py",
                                   "docs/wiki-snippets/global-mcp-tools.md"])
def test_alle_anderen_dokumente_nennen_keine_zahl(datei):
    """Eine Zahl, die nicht jede Woche neu geschrieben wird, ist nach der ersten Woche falsch."""
    kopf = "\n".join(_lies(datei).splitlines()[:60])
    assert not ZAHL.search(kopf), f"{datei}: {ZAHL.search(kopf).group(0)}"


# ── das Wiki-Werkzeug ──────────────────────────────────────────────────────────────────

def _seite(tmp_path, namen, zahl):
    zeilen = [f"# MCP-Tools — Die {zahl} Werkzeuge von PBP", ""] + [f"- `{n}`" for n in namen]
    (tmp_path / "MCP-Tools.md").write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return tmp_path


def test_die_pruefung_findet_fehlende_werkzeuge_und_eine_falsche_zahl(inventar, tmp_path):
    namen = sorted(inventar["namen"])
    ordner = _seite(tmp_path, namen[:-2], inventar["gesamt"] + 2)
    befunde = inv.wiki_pruefen(inventar, ordner)
    assert any("stehen nicht in MCP-Tools.md" in b and namen[-1] in b for b in befunde), befunde
    assert any(str(inventar["gesamt"] + 2) in b for b in befunde), befunde


def test_eine_vollstaendige_seite_ist_in_ordnung(inventar, tmp_path):
    ordner = _seite(tmp_path, sorted(inventar["namen"]), inventar["gesamt"])
    assert inv.wiki_pruefen(inventar, ordner) == []


def test_das_ergaenzen_schliesst_die_luecke_und_ist_idempotent(inventar, tmp_path):
    namen = sorted(inventar["namen"])
    ordner = _seite(tmp_path, namen[:-5], inventar["gesamt"] + 7)
    erg = inv.wiki_ergaenzen(inventar, ordner)
    assert erg["ergaenzt"] == 5 and erg["geaendert"] is True
    assert inv.wiki_pruefen(inventar, ordner) == []
    erster = (ordner / "MCP-Tools.md").read_text(encoding="utf-8")
    erg2 = inv.wiki_ergaenzen(inventar, ordner)
    assert erg2["ergaenzt"] == 5 and erg2["geaendert"] is False
    assert (ordner / "MCP-Tools.md").read_text(encoding="utf-8") == erster
    assert erster.count(inv.MARKE_START) == 1 and erster.count(inv.MARKE_ENDE) == 1


def test_das_ergaenzen_zaehlt_nur_ausserhalb_der_marken(inventar, tmp_path):
    """Ein Werkzeug, das nur im erzeugten Abschnitt steht, bleibt dort (sonst verschwaende es beim zweiten Lauf)."""
    namen = sorted(inventar["namen"])
    ordner = _seite(tmp_path, namen[:-1], inventar["gesamt"])
    inv.wiki_ergaenzen(inventar, ordner)
    inv.wiki_ergaenzen(inventar, ordner)
    assert f"`{namen[-1]}`" in (ordner / "MCP-Tools.md").read_text(encoding="utf-8")
