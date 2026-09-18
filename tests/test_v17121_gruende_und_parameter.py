"""v1.7.121 — zwei Befunde aus einem Versuch, den Schwellenwert-Vorschlag
zu bekommen (Nutzerbericht 18.09.2026).

1. Ein Werkzeug-Parameter hiess `angepasst_für`. Die Anthropic-API nimmt
   als Parameternamen nur `[a-zA-Z0-9_.-]{1,64}` — ein Umlaut macht das
   Schema ungueltig; Claude Code laesst genau dieses Werkzeug weg. Der
   Name stand seit v0.30.0 da. Ob er auch die abgeschnittene Werkzeugliste
   in Claude Desktop erklaert (alles ab `fit_analyse` fehlte), ist NICHT
   belegt — ein ungueltiges Schema ist es in jedem Fall.

2. Aussortier-Gruende liegen in zwei Formen im selben Feld: ein Grund
   als String, mehrere als JSON-Liste. Drei Leser zaehlten mit
   `GROUP BY dismiss_reason` und meldeten `["falsches_fachgebiet"]` und
   `falsches_fachgebiet` als zwei Muster (32,1 % und 31,3 % statt eines
   mit 63,4 %).
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

API_NAME = re.compile(r"[a-zA-Z0-9_.-]{1,64}")


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17121_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    d = _db_mod.Database()
    d.initialize()
    assert str(tmpdir) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test"})
    yield d
    d.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


# ══ 1. Parameternamen ═══════════════════════════════════════════════

def test_jeder_parametername_ist_fuer_die_api_gueltig(db):
    """Gegen die echten Schemas, nicht gegen den Quelltext: ein Name, den
    die API ablehnt, laesst das Werkzeug verschwinden, ohne dass PBP es
    merkt."""
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP Test")
    register_all(mcp, db, logging.getLogger("t"))

    async def _tools():
        if hasattr(mcp, "list_tools"):
            return await mcp.list_tools()
        return list((await mcp.get_tools()).values())

    tools = asyncio.run(_tools())
    assert len(tools) > 200
    schlecht = []
    for t in tools:
        if not API_NAME.fullmatch(t.name):
            schlecht.append((t.name, "<name>"))
        for p in (t.parameters or {}).get("properties", {}):
            if not API_NAME.fullmatch(p):
                schlecht.append((t.name, p))
    assert not schlecht, f"Von der API abgelehnt: {schlecht}"


def test_lebenslauf_export_heisst_angepasst_fuer():
    quelle = (ROOT / "src/bewerbungs_assistent/tools/export_tools.py").read_text(encoding="utf-8")
    assert "angepasst_für" not in quelle
    assert "angepasst_fuer: str" in quelle


# ══ 2. Gruende in zwei Formen ═══════════════════════════════════════

def test_beide_speicherformen_ergeben_dieselben_gruende():
    from bewerbungs_assistent.services.ablehnungsgruende import gruende_aus_wert
    assert gruende_aus_wert("falsches_fachgebiet") == ["falsches_fachgebiet"]
    assert gruende_aus_wert('["falsches_fachgebiet"]') == ["falsches_fachgebiet"]
    assert gruende_aus_wert('["zu_junior", "befristet"]') == ["zu_junior", "befristet"]
    assert gruende_aus_wert("Duplikat: abc123") == ["duplikat"]
    assert gruende_aus_wert("") == [] and gruende_aus_wert(None) == []


def _aussortiert(db, n, wert, start=0):
    stellen = [{"hash": f"k17121{wert[:6]}{start + i}", "title": f"Stelle {wert} {i}",
                "company": f"Musterfirma {start + i}", "url": f"https://example.com/{wert}/{start + i}",
                "source": "manuell", "description": "x" * 80}
               for i in range(n)]
    db.save_jobs(stellen)
    conn = db.connect()
    for s in stellen:
        # Der Rohwert wird gesetzt, wie ihn Altbestand und Listenform tragen.
        conn.execute("UPDATE jobs SET is_active=0, dismiss_reason=? WHERE hash LIKE ?",
                     (wert, f"%{s['hash']}"))
    conn.commit()


def _bestand(db):
    _aussortiert(db, 6, '["falsches_fachgebiet"]', 0)
    _aussortiert(db, 5, "falsches_fachgebiet", 100)
    _aussortiert(db, 2, '["falsches_fachgebiet", "befristet"]', 200)
    _aussortiert(db, 3, "zu_junior", 300)
    _aussortiert(db, 4, "bewerbung_erstellt", 400)


def test_gruende_zaehlen_fasst_beide_formen_zusammen(db):
    from bewerbungs_assistent.services.ablehnungsgruende import gruende_zaehlen
    _bestand(db)
    liste, gesamt = gruende_zaehlen(db.connect(), db.get_active_profile_id())
    zahl = dict(liste)
    assert zahl["falsches_fachgebiet"] == 13
    assert zahl["befristet"] == 2 and zahl["zu_junior"] == 3
    assert "bewerbung_erstellt" not in zahl
    # Eine Stelle mit zwei Gruenden zaehlt im Gesamtwert einmal.
    assert gesamt == 16
    assert liste[0][0] == "falsches_fachgebiet"


def test_die_erkenntnis_nennt_einen_grund_statt_zwei(db):
    from bewerbungs_assistent.services.lerninsights import _regel_aussortier_muster
    _bestand(db)
    muster = _regel_aussortier_muster(db)
    gruende = [m["evidenz"]["grund"] for m in muster]
    assert gruende[0] == "falsches_fachgebiet"
    assert '["falsches_fachgebiet"]' not in gruende
    assert muster[0]["evidenz"]["anzahl"] == 13
    assert muster[0]["evidenz"]["gesamt_aussortiert"] == 16


def test_statistik_und_lernkarte_zaehlen_gleich(db):
    import bewerbungs_assistent.dashboard as dash
    _bestand(db)
    stats = db.get_extended_stats()
    aus_stats = dict(stats["dismiss_reasons"]) if isinstance(stats.get("dismiss_reasons"), list) \
        else stats["dismiss_reasons"]
    assert aus_stats["falsches_fachgebiet"] == 13
    out: dict = {}
    dash._fill_dismiss_reasons(out, db.connect(), db.get_active_profile_id())
    top = {e["reason"]: e["count"] for e in out["dismiss_reasons_top"]}
    assert top["falsches_fachgebiet"] == 13
    assert '["falsches_fachgebiet"]' not in top


def test_niemand_zaehlt_mehr_ueber_den_rohwert():
    """Der Guard, der gefehlt hat: `GROUP BY dismiss_reason` ausserhalb des
    Zaehlers fuehrt die zwei Formen wieder als zwei Gruende."""
    treffer = []
    for f in (ROOT / "src" / "bewerbungs_assistent").rglob("*.py"):
        if f.name == "ablehnungsgruende.py":
            continue
        text = f.read_text(encoding="utf-8-sig")
        if re.search(r"GROUP BY\s+(\w+\.)?dismiss_reason", text):
            treffer.append(str(f.relative_to(ROOT)))
    assert not treffer, treffer
