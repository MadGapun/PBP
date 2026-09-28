"""#1112: die ganze Stellenliste gegen das Profil — ein Prompt, ein Filter.

Der Prompt `stellen_abgleich` entstand aus zwei echten Durchgaengen, in
denen Claude eine harte Entfernungsgrenze aufweichte, Vorgeschichte
uebersah, verborgene Stellen nie las und aus dem Titel urteilte. Die
Regeln gelten nur, wenn die genannten Werkzeuge und Parameter existieren
(#1000) und Slash-Befehl und Dashboard denselben Text liefern (H22).

Alle Firmen sind Platzhalter.
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
import os
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database
    importlib.reload(database)
    d = database.Database(db_path=tmp_path / "abgleich.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.switch_profile(d.create_profile("Erstes"))
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _server(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent import tools
    from bewerbungs_assistent.prompts import register_prompts
    mcp = FastMCP("t")
    tools.register_all(mcp, db, logging.getLogger("t"))
    register_prompts(mcp, db, logging.getLogger("t"))
    return mcp


def _tool(mcp, name, args):
    async def lauf():
        t = await mcp.get_tool(name)
        res = await t.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(lauf())


def _text(db, **kw):
    from bewerbungs_assistent.prompts import build_stellen_abgleich_prompt
    return build_stellen_abgleich_prompt(db, **kw)


# ============================================================ der Prompt


def test_jeder_genannte_aufruf_passt_zur_signatur(db):
    """Werkzeug und Parameter gibt es wirklich (#1000)."""
    mcp = _server(db)
    text = _text(db, gefunden_seit="2026-09-20")

    async def signatur(name):
        t = await mcp.get_tool(name)
        return t

    aufrufe = re.findall(r"\b([a-z_]{4,})\(([^()]*)\)", text)
    geprueft = 0
    for name, args in aufrufe:
        try:
            t = asyncio.run(signatur(name))
        except Exception:
            t = None
        assert t is not None, f"Werkzeug {name} gibt es nicht"
        erlaubt = set((t.parameters or {}).get("properties", {}))
        for param in re.findall(r"\b([a-z_]+)=", args):
            assert param in erlaubt, f"{name}({param}=) gibt es nicht"
        geprueft += 1
    assert geprueft >= 8


def test_slash_und_dashboard_liefern_denselben_text(db):
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    mcp = _server(db)

    async def lauf():
        p = await mcp.get_prompt("stellen_abgleich")
        res = await p.render({"gefunden_seit": "2026-09-20"})
        return res.messages[0].content.text
    assert asyncio.run(lauf()) == _prompt_registry(db)["stellen_abgleich"](gefunden_seit="2026-09-20")


def test_das_datum_steht_im_aufruf(db):
    text = _text(db, gefunden_seit="2026-09-20")
    assert "seit dem 2026-09-20" in text
    assert "gefunden_seit='2026-09-20'" in text


def test_ohne_datum_alle_aktiven(db):
    text = _text(db)
    assert "gefunden_seit" not in text
    assert "aktiven Stellen" in text


def test_ein_unsinniges_datum_wird_nicht_eingesetzt(db):
    text = _text(db, gefunden_seit="letzte Woche")
    assert "letzte Woche" not in text and "gefunden_seit" not in text


def test_die_regeln_aus_dem_issue_stehen_drin(db):
    text = _text(db)
    assert "ohne_schwelle=True ist Pflicht" in text
    assert "heben die Grenze NICHT auf" in text
    assert "Nicht aus dem Titel urteilen" in text
    assert "Geschätzte Werte sind kein Grund" in text
    assert "nichts\n  selbst an den Suchkriterien ändern" in text


def test_katalog_kennt_den_prompt():
    from bewerbungs_assistent.services import prompt_katalog
    namen = {e.get("name") or e.get("kennung") or e.get("id")
             for e in prompt_katalog.KATALOG} if hasattr(prompt_katalog, "KATALOG") else None
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "services" / "prompt_katalog.py").read_text(encoding="utf-8")
    assert "stellen_abgleich" in (namen or set()) or '"stellen_abgleich"' in quelle


# ======================================================= der Datumsfilter


def _stelle(db, h, found_at):
    db.save_jobs([{"hash": h, "title": f"Sachbearbeitung {h}", "company": "Musterbetrieb GmbH",
                   "url": f"https://jobs.example.org/{h}", "score": 5,
                   "description": "Aufgaben: Einkauf und Disposition. " * 5}])
    db.connect().execute("UPDATE jobs SET found_at=? WHERE hash=?",
                         (found_at, db.resolve_job_hash(h)))
    db.connect().commit()


def _hashes(erg):
    return {s.get("hash", "").split(":")[-1] for s in erg.get("stellen", [])}


def test_gefunden_seit_filtert_nach_tag(db):
    _stelle(db, "alt1112", "2026-09-10T08:00:00")
    _stelle(db, "grenze1112", "2026-09-20T23:30:00+00:00")
    _stelle(db, "neu1112", "2026-09-25T08:00:00")
    mcp = _server(db)
    alle = _tool(mcp, "stellen_anzeigen", {"ohne_schwelle": True})
    assert {"alt1112", "grenze1112", "neu1112"} <= _hashes(alle)
    seit = _tool(mcp, "stellen_anzeigen", {"ohne_schwelle": True, "gefunden_seit": "2026-09-20"})
    assert _hashes(seit) >= {"grenze1112", "neu1112"}
    assert "alt1112" not in _hashes(seit)


def test_gefunden_seit_meldet_ein_falsches_datum(db):
    erg = _tool(_server(db), "stellen_anzeigen", {"gefunden_seit": "20.09.2026"})
    assert "fehler" in erg and "YYYY-MM-DD" in erg["fehler"]


# ============================================================ Oberflaeche


def test_knopf_ueber_der_liste_kopiert_den_prompt():
    jsx = (_repo() / "frontend" / "src" / "pages" / "JobsPage.jsx").read_text(encoding="utf-8-sig")
    i = jsx.index("data-stellen-abgleich")
    element = jsx[i:jsx.index("</Button>", i)]
    assert 'copyPrompt("/stellen_abgleich")' in element
    assert "<MitClaude" in element


def test_registry_nimmt_den_parameter():
    from bewerbungs_assistent.tools import workflows
    quelle = inspect.getsource(workflows)
    assert '"stellen_abgleich"' in quelle
