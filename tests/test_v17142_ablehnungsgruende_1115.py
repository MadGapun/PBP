"""#1115 — die Liste der Ablehnungsgruende stand viermal im Code, dreimal veraltet.

`services/ablehnungsgruende.STANDARD_GRUENDE` fuehrt seit v1.7.17 fuenfzehn
Gruende, darunter `falsches_system` und `falsche_branche`. Die Beschreibung
von `stelle_einordnen`, `gruende_schreibweise.WHITELIST` und der Block in
CLAUDE.md fuehrten noch die dreizehn Werte von vor #913. Eine KI las "nur
diese, nichts anderes!" und konnte die zwei Gruende nicht benutzen.
Ausserdem spaltete der Seed den Bestand: ein eigener Eintrag
"falsches system" blieb neben dem neuen Standardgrund stehen.
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

from bewerbungs_assistent.services.ablehnungsgruende import STANDARD_GRUENDE  # noqa: E402


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_1115_")
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


def _tool(db, name):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import jobs, mit_katalog
    mcp = FastMCP("test")
    jobs.register(mit_katalog(mcp, db), db, logging.getLogger("test"))
    return asyncio.run(mcp.get_tool(name))


# ══ Die Kopien folgen der Quelle ═════════════════════════════════════

def test_1115_die_beschreibung_von_stelle_einordnen_nennt_jeden_standardgrund(db):
    t = _tool(db, "stelle_einordnen")
    text = t.parameters["properties"]["gruende"].get("description", "")
    fehlt = [g for g in STANDARD_GRUENDE if g not in text]
    assert not fehlt, f"in der Parameterbeschreibung fehlen: {fehlt}"
    assert "{ERLAUBTE_GRUENDE}" not in text
    assert "falsches_system" in text and "falsche_branche" in text


def test_1115_die_beschreibung_nennt_nichts_ausserhalb_der_quelle(db):
    """Die Gegenrichtung: kein veralteter oder erfundener Wert."""
    t = _tool(db, "stelle_einordnen")
    text = t.parameters["properties"]["gruende"].get("description", "")
    liste = text.split("NUR diese Werte:", 1)[1]
    kandidaten = set(re.findall(r"[a-z]+(?:_[a-z]+)*", liste))
    assert kandidaten == set(STANDARD_GRUENDE), kandidaten ^ set(STANDARD_GRUENDE)


def test_1115_die_schreibweisen_whitelist_ist_die_quelle():
    from bewerbungs_assistent.services import gruende_schreibweise as gs
    assert gs.WHITELIST == frozenset(STANDARD_GRUENDE)
    assert {"falsches_system", "falsche_branche"} <= gs.WHITELIST


def test_1115_claude_md_haelt_den_block_gegen_die_quelle():
    """Der Kommentar "Erweiterung NUR hier" beschrieb die Regel, aber nichts
    setzte sie durch."""
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    i = text.index("zu_weit_entfernt")
    # Der umgebende Zaun: zwischen dem letzten ``` davor und dem ersten danach.
    liste = text[text.rfind("```", 0, i) + 3:text.find("```", i)]
    assert set(liste.split()) == set(STANDARD_GRUENDE), (
        set(liste.split()) ^ set(STANDARD_GRUENDE))


def test_1115_werkzeugantwort_und_quelle_sind_dieselbe_liste(db):
    """`verfuegbare_gruende` kam schon vorher aus der Quelle — das bleibt so."""
    from bewerbungs_assistent.job_scraper import stelle_hash
    db.save_jobs([{"hash": stelle_hash("test", "a"), "title": "PLM Engineer",
                   "company": "Musterfirma", "location": "Hamburg",
                   "url": "https://example.com/a", "source": "test",
                   "description": "x", "score": 1}])
    job = db.get_active_jobs()[0]
    t = _tool(db, "stelle_einordnen")
    res = asyncio.run(t.run({"job_hash": job["hash"], "bewertung": "passt_nicht",
                             "gruende": ["falsches_system"]}))
    res = getattr(res, "structured_content", res)
    res = res.get("result", res) if set(res) == {"result"} else res
    assert res["gruende"] == ["falsches_system"]
    assert res["verfuegbare_gruende"] == STANDARD_GRUENDE


# ══ Der Seed spaltet nicht mehr ══════════════════════════════════════

def _gruende(db):
    return {r["label"]: r for r in db.get_dismiss_reasons()}


def test_1115_ein_eigener_eintrag_wird_in_den_standardgrund_gefuehrt(db):
    """Die Lage vom 29.09.2026: eigener Eintrag mit Leerzeichen, viele
    Verwendungen, daneben der Standardgrund."""
    db.add_dismiss_reason("falsches system")
    conn = db.connect()
    conn.execute("UPDATE dismiss_reasons SET usage_count=59 WHERE label=?",
                 ("falsches system",))
    conn.execute("UPDATE dismiss_reasons SET usage_count=8 WHERE label=?",
                 ("falsches_system",))
    conn.commit()
    assert {"falsches system", "falsches_system"} <= set(_gruende(db))

    db.initialize()  # der Start, der den Bestand heilt

    gruende = _gruende(db)
    assert "falsches system" not in gruende
    assert gruende["falsches_system"]["usage_count"] == 67
    assert sum(1 for l in gruende if l.startswith("falsches")) == 2  # + fachgebiet


def test_1115_stellen_mit_der_alten_schreibweise_wandern_mit(db):
    from bewerbungs_assistent.job_scraper import stelle_hash
    db.save_jobs([{"hash": stelle_hash("test", "b"), "title": "PLM Engineer",
                   "company": "Musterfirma", "location": "Hamburg",
                   "url": "https://example.com/b", "source": "test",
                   "description": "x", "score": 1}])
    h = db.resolve_job_hash(db.get_active_jobs()[0]["hash"])
    db.add_dismiss_reason("Falsche Branche")
    conn = db.connect()
    conn.execute("UPDATE jobs SET is_active=0, dismiss_reason=? WHERE hash=?",
                 ('["falsche branche"]', h))
    conn.commit()

    db.initialize()

    roh = db.connect().execute(
        "SELECT dismiss_reason FROM jobs WHERE hash=?", (h,)).fetchone()[0]
    assert "falsche_branche" in roh and "falsche branche" not in roh


def test_1115_ein_fehlender_standardgrund_wird_angelegt_und_zusammengefuehrt(db):
    """Reihenfolge wie in der Praxis: erst der eigene Eintrag, dann der Seed."""
    conn = db.connect()
    conn.execute("DELETE FROM dismiss_reasons WHERE label='falsche_branche'")
    conn.commit()
    db.add_dismiss_reason("falsche branche")

    db.initialize()

    gruende = _gruende(db)
    assert "falsche branche" not in gruende
    assert "falsche_branche" in gruende


def test_1115_ein_anderer_eigener_grund_bleibt_unberuehrt(db):
    db.add_dismiss_reason("falsches system fuer uns")
    db.add_dismiss_reason("zu_hands_on")
    db.initialize()
    gruende = _gruende(db)
    assert "falsches system fuer uns" in gruende
    assert "zu_hands_on" in gruende


def test_1115_zweimal_starten_aendert_nichts(db):
    db.add_dismiss_reason("falsches system")
    db.initialize()
    vorher = {l: r["usage_count"] for l, r in _gruende(db).items()}
    db.initialize()
    assert {l: r["usage_count"] for l, r in _gruende(db).items()} == vorher


# ══ Befund 3: das Werkzeug ist da — im Expertenmodus ═════════════════

def _server(monkeypatch, experten: bool):
    """Der Server, wie er startet — der Expertenmodus gilt beim Start."""
    if experten:
        monkeypatch.setenv("BA_EXPERTENMODUS", "1")
    else:
        monkeypatch.delenv("BA_EXPERTENMODUS", raising=False)
    tmpdir = tempfile.mkdtemp(prefix="pbp_1115s_")
    monkeypatch.setenv("BA_DATA_DIR", tmpdir)
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    assert str(tmpdir) in str(_srv_mod.db.db_path), "DB nicht isoliert"
    return _srv_mod, tmpdir


def test_1115_vereinheitlichen_ist_ein_wartungswerkzeug(monkeypatch):
    """Kein Registrierungsdefekt: das Werkzeug steht in `WARTUNG` und ist
    ohne Expertenmodus bewusst ausgeblendet; mit ihm ist es aufrufbar."""
    from bewerbungs_assistent.services import werkzeug_katalog as k
    assert "ablehnungsgruende_vereinheitlichen" in k.WARTUNG
    for experten in (False, True):
        srv, tmpdir = _server(monkeypatch, experten)
        try:
            tool = asyncio.run(srv.mcp.get_tool("ablehnungsgruende_vereinheitlichen"))
            assert (tool is not None) is experten, experten
        finally:
            srv.db.close()
            shutil.rmtree(tmpdir, ignore_errors=True)
