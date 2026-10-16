"""Das Inventar der MCP-Werkzeuge: Zahlen zur LAUFZEIT, nicht aus der Erinnerung (#1148 Punkt 4).

Die Zahl der Werkzeuge stand in Dokumenten, Docstrings und im Wiki mit 47 bis 281 — jede eine Momentaufnahme. Hier entsteht die eine
richtige: das Programm wird so aufgebaut, wie Claude es sieht, und gezählt.

Aufruf (ohne Argumente: das Inventar):

    python scripts/werkzeug_inventar.py
    python scripts/werkzeug_inventar.py --wiki D:/pfad/zum/PBP.wiki        # prueft MCP-Tools.md gegen das Inventar
    python scripts/werkzeug_inventar.py --json                              # maschinenlesbar

Mit `--wiki` pruefen zwei Dinge (Exit 1 bei einem Befund): jedes registrierte Werkzeug steht in der Seite `MCP-Tools.md` (als `name`
in Backticks), und die dort genannten Summen (`Die N Werkzeuge`, `= N`) stimmen mit der Laufzeitzahl. Die Seite muss VOR jedem
Wiki-Push gruen sein (Teil der Session-Abschluss-Runde, CLAUDE.md).

Das Programm schreibt nichts: die Datenbank liegt in einem Wegwerf-Ordner.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "src"))


def _kurz(name: str, doc: str, maximal: int = 150) -> str:
    """Der erste Satz der kuratierten Beschreibung (ohne Entwicklungsgeschichte), fuer eine Tabellenzeile."""
    try:
        from bewerbungs_assistent.services import werkzeug_katalog
        text = werkzeug_katalog.beschreibung(name, doc)
    except Exception:  # noqa: BLE001
        text = doc
    text = re.sub(r"\s+", " ", text or "").strip()
    satz = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    satz = satz.replace("|", "/")
    return satz if len(satz) <= maximal else satz[: maximal - 1].rsplit(" ", 1)[0] + "…"


def inventar() -> dict:
    """{'namen': {name: modul}, 'module': {modul: [namen]}, 'gesamt': n} aus dem aufgebauten Server."""
    ordner = Path(tempfile.mkdtemp(prefix="pbp_inventar_"))
    os.environ["BA_DATA_DIR"] = str(ordner)
    from fastmcp import FastMCP

    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent.tools import register_all

    db = Database(db_path=ordner / "inventar.db")
    assert str(ordner) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.initialize()
    mcp = FastMCP("PBP Inventar")
    register_all(mcp, db, logging.getLogger("inventar"))

    async def _tools():
        lokal = getattr(mcp, "local_provider", None)
        if lokal is not None:
            return await lokal.list_tools()
        return list((await mcp.get_tools()).values())

    tools = asyncio.run(_tools())
    namen: dict = {}
    beschreibungen: dict = {}
    for t in tools:
        fn = getattr(t, "fn", None)
        modul = (getattr(fn, "__module__", "") or "").rsplit(".", 1)[-1] or "?"
        namen[t.name] = modul
        beschreibungen[t.name] = _kurz(t.name, getattr(t, "description", "") or "")
    module: dict = defaultdict(list)
    for name, modul in namen.items():
        module[modul].append(name)
    db.close()
    return {"namen": namen, "module": {m: sorted(v) for m, v in sorted(module.items())}, "gesamt": len(namen),
            "beschreibungen": beschreibungen}


def wiki_pruefen(inv: dict, ordner: Path) -> list:
    """Befunde der Seite MCP-Tools.md gegen das Inventar (leere Liste = in Ordnung)."""
    seite = Path(ordner) / "MCP-Tools.md"
    if not seite.is_file():
        return [f"{seite} fehlt"]
    text = seite.read_text(encoding="utf-8-sig")
    befunde = []
    genannt = set(re.findall(r"`([a-z][a-z0-9_]+)`", text))
    fehlt = sorted(n for n in inv["namen"] if n not in genannt)
    if fehlt:
        befunde.append(f"{len(fehlt)} Werkzeuge stehen nicht in MCP-Tools.md: {', '.join(fehlt)}")
    # Zahlen: eine dreistellige Zahl vor "Werkzeuge"/"Tools" oder hinter "= **" ist eine Aussage ueber die Gesamtzahl
    zahlen = {int(z) for z in re.findall(r"\b([0-9]{3})\b\*{0,2}\s+(?:MCP-)?(?:Werkzeuge|Tools)", text)}
    zahlen |= {int(z) for z in re.findall(r"=\s*\*\*([0-9]{3})\*\*", text)}
    falsch = sorted(z for z in zahlen if z != inv["gesamt"])
    if falsch:
        befunde.append(f"MCP-Tools.md nennt die Zahl(en) {falsch}, das Programm hat {inv['gesamt']} Werkzeuge")
    return befunde


MARKE_START = "<!-- inventar:start (aus dem Programm erzeugt, nicht von Hand aendern: scripts/werkzeug_inventar.py --wiki-ergaenzen) -->"
MARKE_ENDE = "<!-- inventar:ende -->"


def wiki_ergaenzen(inv: dict, ordner: Path) -> dict:
    """Schreibt in MCP-Tools.md einen erzeugten Abschnitt mit den Werkzeugen, die sonst nirgends auf der Seite stehen.

    Idempotent: der Abschnitt steht zwischen Marken und wird bei jedem Lauf neu berechnet (`genannt` zaehlt nur, was AUSSERHALB
    der Marken steht). Setzt ausserdem die Gesamtzahl in den Zaehlstellen der Seite auf die Laufzeitzahl.
    """
    seite = Path(ordner) / "MCP-Tools.md"
    text = seite.read_text(encoding="utf-8-sig")
    a = text.find(MARKE_START)
    e = text.find(MARKE_ENDE)
    aussen = text if a < 0 or e < 0 else text[:a] + text[e + len(MARKE_ENDE):]
    genannt = set(re.findall(r"`([a-z][a-z0-9_]+)`", aussen))
    fehlt: dict = defaultdict(list)
    for name, modul in sorted(inv["namen"].items()):
        if name not in genannt:
            fehlt[modul].append(name)
    zeilen = [MARKE_START, "", "## Weitere Werkzeuge (Inventar, aus dem Programm erzeugt)", "",
              f"Das Programm hat zur Laufzeit **{inv['gesamt']}** Werkzeuge in {len(inv['module'])} Modulen. Hier stehen die, die oben "
              "nicht einzeln erklaert sind, mit dem ersten Satz ihrer Beschreibung.", ""]
    for modul in sorted(fehlt):
        zeilen += [f"### {modul} ({len(fehlt[modul])})", "", "| Werkzeug | Wofuer |", "|---|---|"]
        zeilen += [f"| `{n}` | {inv['beschreibungen'].get(n, '')} |" for n in fehlt[modul]]
        zeilen.append("")
    zeilen.append(MARKE_ENDE)
    block = "\n".join(zeilen) + "\n"
    if a >= 0 and e >= 0:
        neu = text[:a] + block + text[e + len(MARKE_ENDE):].lstrip("\n")
    else:
        neu = text.rstrip("\n") + "\n\n" + block
    # die Zaehlstellen der Seite auf die Laufzeitzahl
    gesamt = str(inv["gesamt"])
    neu = re.sub(r"\b[0-9]{3}\b(?=\*{0,2}\s+(?:MCP-)?(?:Werkzeuge|Tools))", gesamt, neu)
    neu = re.sub(r"(=\s*\*\*)[0-9]{3}(\*\*)", lambda m: m.group(1) + gesamt + m.group(2), neu)
    if neu != text:
        seite.write_text(neu, encoding="utf-8")
    return {"ergaenzt": sum(len(v) for v in fehlt.values()), "geaendert": neu != text}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--wiki", help="Ordner eines Wiki-Klons: MCP-Tools.md wird gegen das Inventar geprueft")
    p.add_argument("--json", action="store_true", help="maschinenlesbar")
    p.add_argument("--wiki-ergaenzen", metavar="ORDNER", help="MCP-Tools.md um die fehlenden Werkzeuge ergaenzen (erzeugter Abschnitt)")
    a = p.parse_args(argv)
    inv = inventar()
    if a.json:
        print(json.dumps(inv, ensure_ascii=False, indent=1))
    else:
        print(f"{inv['gesamt']} Werkzeuge in {len(inv['module'])} Modulen:")
        for modul, namen in inv["module"].items():
            print(f"  {modul:16s} {len(namen):3d}")
    if a.wiki_ergaenzen:
        print(wiki_ergaenzen(inv, Path(a.wiki_ergaenzen)))
    if a.wiki:
        befunde = wiki_pruefen(inv, Path(a.wiki))
        for b in befunde:
            print("BEFUND:", b)
        return 1 if befunde else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
