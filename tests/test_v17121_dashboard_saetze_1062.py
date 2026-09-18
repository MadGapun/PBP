"""#1062 — ein Satz aus dem Dashboard fuehrte Claude zum falschen Werkzeug.

Der Hinweis zu #1054 endete mit `Sag Claude: „Vorschlaege ansehen"`. Im
Chat kommt der Satz ohne den Hinweis darueber an, und "Vorschlag" steht in
drei anderen Werkzeugnamen, im gemeinten nicht. Claude rief
`stellen_anzeigen` auf. Dasselbe gilt fuer "Neuen Schwellenwert vorschlagen
lassen" -> `kalibrierung_backtest`: kein "Schwell" im Namen.

Die Regel fuer JEDEN Satz: er beginnt mit "PBP:", sein Werkzeug existiert,
und er traegt einen Wortstamm aus dem Werkzeugnamen.
"""
import asyncio
import importlib
import logging
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _norm(text: str) -> str:
    text = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9]+", " ", text)


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17121_1062_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP Test")
    register_all(mcp, db, logging.getLogger("t"))
    yield db, mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _werkzeuge(mcp) -> dict:
    async def _t():
        if hasattr(mcp, "list_tools"):
            return {t.name: t for t in await mcp.list_tools()}
        return dict(await mcp.get_tools())
    return asyncio.run(_t())


def _rufe(mcp, name, args=None):
    async def _r():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    return asyncio.run(_r())


def test_jeder_satz_fuehrt_zu_einem_vorhandenen_werkzeug_und_traegt_seinen_namen(umgebung):
    from bewerbungs_assistent.services.onboarding_hints import HINT_DEFINITIONS
    _, mcp = umgebung
    vorhanden = set(_werkzeuge(mcp))
    assert len(HINT_DEFINITIONS) >= 9
    fehler = []
    for h in HINT_DEFINITIONS:
        satz, tool = h.get("cta_label", ""), h.get("cta_tool", "")
        if not tool:
            fehler.append((h["id"], "kein Zielwerkzeug"))
            continue
        if tool not in vorhanden:
            fehler.append((h["id"], f"{tool} ist nicht registriert"))
        if not satz.startswith("PBP:"):
            fehler.append((h["id"], "beginnt nicht mit 'PBP:'"))
        stamm = [t for t in tool.split("_") if len(t) >= 4]
        if not any(s in _norm(satz) for s in stamm):
            fehler.append((h["id"], f"kein Wortstamm aus {tool} in {satz!r}"))
    assert not fehler, fehler


def test_die_zwei_gemeldeten_saetze():
    from bewerbungs_assistent.services.onboarding_hints import HINT_DEFINITIONS
    nach_id = {h["id"]: h for h in HINT_DEFINITIONS}
    c87 = nach_id["c87_suchbegriffe_gegen_profil"]
    assert c87["cta_tool"] == "profil_suchbegriffe_abgleichen"
    assert "abgleich" in _norm(c87["cta_label"]) and "vorschlaege ansehen" not in _norm(c87["cta_label"])
    c83 = nach_id["c83_schwelle_nach_score_trennung"]
    assert c83["cta_tool"] == "kalibrierung_backtest"
    assert "kalibrierung" in _norm(c83["cta_label"])


def test_saetze_im_hinweistext_folgen_derselben_regel():
    """Ein zweiter Satz steckte im TEXT eines Hinweises ("Sag Claude
    einfach: ...") — der Guard ueber `cta_label` allein haette ihn nie
    gesehen."""
    from bewerbungs_assistent.services.onboarding_hints import HINT_DEFINITIONS
    for h in HINT_DEFINITIONS:
        for m in re.finditer(r'Sag Claude[^"„]*["„]([^"“]+)', h.get("body", "")):
            assert m.group(1).startswith("PBP:"), (h["id"], m.group(1))


def test_capabilities_liefert_die_zuordnung(umgebung):
    from bewerbungs_assistent.services.onboarding_hints import HINT_DEFINITIONS
    _, mcp = umgebung
    res = _rufe(mcp, "pbp_capabilities")
    saetze = {s["satz"]: s["werkzeug"] for s in res["dashboard_saetze"]}
    assert len(saetze) == len([h for h in HINT_DEFINITIONS if h.get("cta_tool")])
    assert saetze["PBP: Suchbegriffe mit meinem Profil abgleichen"] == "profil_suchbegriffe_abgleichen"


def test_jedes_zielwerkzeug_steht_in_einer_kategorie(umgebung):
    """Der Abgleich stand in keiner Kategorie; in `analyse` stand dafuer
    `keyword_vorschlaege`, der falsche Nachbar."""
    from bewerbungs_assistent.services.onboarding_hints import HINT_DEFINITIONS
    _, mcp = umgebung
    kategorien = _rufe(mcp, "pbp_capabilities")["kategorien"]
    text = ""
    for k in kategorien:
        text += " ".join(_rufe(mcp, "pbp_capabilities", {"kategorie": k})["tools"])
    fehlt = sorted({h["cta_tool"] for h in HINT_DEFINITIONS if h.get("cta_tool")}
                   - set(re.findall(r"[a-z_]+", text)))
    assert not fehlt, f"In keiner Kategorie: {fehlt}"


def test_die_elwosa_tipps_nennen_kein_werkzeug_das_es_nicht_gibt(umgebung):
    """`Wochenrueckblick` war ein Satz ohne Werkzeug."""
    from bewerbungs_assistent.services.elwosa_lines import TIP_LINES
    _, mcp = umgebung
    vorhanden = set(_werkzeuge(mcp))
    for zeile in TIP_LINES:
        for m in re.finditer(r"Sag Claude[^`]*`(?:PBP: )?([a-z_]+)", zeile, flags=re.I):
            wort = m.group(1)
            if "_" in wort:
                assert wort in vorhanden, (wort, zeile)
        assert "Wochenrueckblick" not in zeile
