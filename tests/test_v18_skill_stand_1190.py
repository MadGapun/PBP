"""#1190 — `profil_zusammenfassung`: bei jedem Skill der aktuelle Stand, nicht nur die Spitze.

Am echten Bestand (11.10.2026): `skills_liste` zeigte `level` (die Spitze, 5), die Oberfläche
den aktuellen Stand (1 Punkt, „ruht, Spitze 5/5“). Ein Skill ohne Einsatz seit rund 25 Jahren
ging deshalb als Experte auf eine fremde Plattform. Die Felder `level_current`, `end_year` und
`last_used_year` lagen in der Datenbank, fehlten aber im Werkzeug.

Alle Namen sind Platzhalter.
"""
import asyncio
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services.profile_service import skill_stand  # noqa: E402


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v18_1190_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _skill(db, name, **felder):
    daten = {"name": name, "category": "tool", "level": 5}
    daten.update(felder)
    sid, grund = db.add_skill_mit_befund(daten, quelle="eingabe")
    assert sid, grund
    return sid


def _eintrag(erg, sid):
    return next(s for s in erg["skills_liste"] if s["id"] == sid)


# ── Der Fall aus dem Issue ────────────────────────────────────────────────────

def test_ein_ruhender_skill_nennt_aktuellen_stand_spitze_und_ende(umgebung):
    db, mcp = umgebung
    sid = _skill(db, "AutoZeichner", level=5, level_current=1, start_year=1992, end_year=2003)
    erg = _call(mcp, "profil_zusammenfassung")
    e = _eintrag(erg, sid)
    assert e["level_aktuell"] == 1
    assert e["level_spitze"] == 5
    assert e["ruht"] is True
    assert e["bis"] == 2003 and e["seit"] == 1992
    assert "ruht seit 2003" in e["stand"] and "aktuell Lv.1" in e["stand"] and "Spitze Lv.5" in e["stand"]


def test_das_mehrdeutige_feld_level_gibt_es_in_der_liste_nicht_mehr(umgebung):
    db, mcp = umgebung
    sid = _skill(db, "AutoZeichner", level=5, level_current=1, end_year=2003)
    e = _eintrag(_call(mcp, "profil_zusammenfassung"), sid)
    assert "level" not in e


def test_der_text_der_zusammenfassung_sagt_dasselbe(umgebung):
    db, mcp = umgebung
    sid = _skill(db, "AutoZeichner", level=5, level_current=1, end_year=2003)
    text = _call(mcp, "profil_zusammenfassung")["zusammenfassung"]
    zeile = next(z for z in text.splitlines() if "AutoZeichner" in z)
    assert "aktuell Lv.1" in zeile and "Spitze Lv.5" in zeile and "ruht seit 2003" in zeile
    assert f"[{sid}]" in zeile


# ── Die anderen Fälle ──────────────────────────────────────────────────────────

def test_ein_skill_im_einsatz_zeigt_sein_level_und_ruht_nicht(umgebung):
    db, mcp = umgebung
    sid = _skill(db, "TabellenKalk", level=4)
    e = _eintrag(_call(mcp, "profil_zusammenfassung"), sid)
    assert e["level_aktuell"] == 4 and e["level_spitze"] == 4
    assert e["ruht"] is False and e["bis"] is None
    assert e["stand"] == "Lv.4"


def test_ruht_ohne_eingetragenes_heutiges_niveau_ist_unbekannt_nicht_die_spitze(umgebung):
    """Ende gesetzt, kein aktuelles Niveau: die Spitze darf nicht als Stand von heute durchgehen."""
    db, mcp = umgebung
    sid = _skill(db, "AltSystem", level=5, end_year=2003)
    e = _eintrag(_call(mcp, "profil_zusammenfassung"), sid)
    assert e["level_aktuell"] is None
    assert e["level_spitze"] == 5 and e["ruht"] is True
    assert "heutiges Niveau nicht eingetragen" in e["stand"]


def test_ein_abgesenktes_niveau_ohne_ende_gilt_als_unter_der_spitze(umgebung):
    db, mcp = umgebung
    sid = _skill(db, "SeltenGenutzt", level=5, level_current=3)
    e = _eintrag(_call(mcp, "profil_zusammenfassung"), sid)
    assert e["level_aktuell"] == 3 and e["level_spitze"] == 5
    assert e["ruht"] is True and e["bis"] is None
    assert "ruht seit" not in e["stand"]


def test_der_letzte_einsatz_steht_in_der_liste(umgebung):
    db, mcp = umgebung
    sid = _skill(db, "AltSystem", level=5, level_current=2, end_year=2010, last_used_year=2011)
    e = _eintrag(_call(mcp, "profil_zusammenfassung"), sid)
    assert e["zuletzt_genutzt"] == 2011


def test_erneutes_hinzufuegen_nennt_den_aktuellen_stand_statt_der_spitze(umgebung):
    db, mcp = umgebung
    _skill(db, "AutoZeichner", level=5, level_current=1, end_year=2003)
    erg = _call(mcp, "skill_hinzufuegen", {"name": "autozeichner", "level": 3})
    assert erg["status"] == "bereits_vorhanden"
    v = erg["vorhanden"]
    assert v["level_aktuell"] == 1 and v["level_spitze"] == 5 and v["ruht"] is True and v["bis"] == 2003
    assert "level" not in v


# ── Die Hilfsfunktion selbst ───────────────────────────────────────────────────

@pytest.mark.parametrize("skill, aktuell, spitze, ruht", [
    ({"level": 5, "level_current": 1, "end_year": 2003}, 1, 5, True),
    ({"level": 4}, 4, 4, False),
    ({"level": 5, "end_year": 2003}, None, 5, True),
    ({"level": 5, "level_current": 3}, 3, 5, True),
    ({"level": 3, "level_current": 3}, 3, 3, False),
    ({"level": "4", "level_current": "", "end_year": ""}, 4, 4, False),
    ({}, None, None, False),
    (None, None, None, False),
    ({"level": True}, None, None, False),
])
def test_skill_stand_liest_auch_unsaubere_werte(skill, aktuell, spitze, ruht):
    r = skill_stand(skill)
    assert (r["level_aktuell"], r["level_spitze"], r["ruht"]) == (aktuell, spitze, ruht)
