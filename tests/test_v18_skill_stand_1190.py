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
    # 0 heisst „nicht gesetzt“ (Beschreibung von skill_hinzufuegen: „0 = aktuell/unbekannt“), nie „seit dem Jahr 0“ oder „Niveau 0“
    ({"level": 4, "end_year": 0}, 4, 4, False),
    ({"level": 4, "level_current": 0}, 4, 4, False),
    ({"level": 4, "end_year": "0", "level_current": "0"}, 4, 4, False),
])
def test_skill_stand_liest_auch_unsaubere_werte(skill, aktuell, spitze, ruht):
    r = skill_stand(skill)
    assert (r["level_aktuell"], r["level_spitze"], r["ruht"]) == (aktuell, spitze, ruht)


def test_null_ist_kein_jahr_weder_im_ende_noch_im_letzten_einsatz():
    r = skill_stand({"level": 4, "end_year": 0, "last_used_year": 0, "start_year": 0})
    assert r["bis"] is None and r["zuletzt_genutzt"] is None and r["seit"] is None
    assert "ruht" not in r["stand"] and "0" not in r["stand"].replace("Lv.", ""), r["stand"]


# ── #1264: die übrigen Stellen rechnen mit dem heutigen Stand ─────────────────

from bewerbungs_assistent.services.profile_service import stufe_heute  # noqa: E402


@pytest.mark.parametrize("skill, erwartet", [
    ({"level": 5}, 5),                                        # läuft noch: die Spitze ist der Stand
    ({"level": 5, "level_current": 2}, 2),                    # abgesenkt
    ({"level": 5, "end_year": 2004}, 0),                      # ruht, heutiges Niveau unbekannt: zählt nicht
    ({"level": 5, "end_year": 2004, "level_current": 3}, 3),  # ruht, heutiges Niveau eingetragen
    ({}, 0),
])
def test_1264_stufe_heute(skill, erwartet):
    assert stufe_heute(skill) == erwartet


def _ruhend(name):
    return {"name": name, "category": "tool", "level": 5, "end_year": 2004}


def test_1264_lebenslauf_bewertung_zaehlt_ruhende_skills_nicht_als_experte():
    from bewerbungs_assistent.export import analyse_cv_perspectives
    ruhend = {"skills": [_ruhend(f"Altwerkzeug{i}") for i in range(6)]}
    aktiv = {"skills": [{"name": f"Werkzeug{i}", "category": "tool", "level": 5} for i in range(6)]}

    def faktoren(profil):
        erg = analyse_cv_perspectives(profil, "Ingenieur", "Werkzeug")
        return " ".join(str(f) for p in erg["perspektiven"].values() for f in p.get("faktoren", []))

    assert "Expert-Skills" not in faktoren(ruhend)
    assert "Expert-Skills" in faktoren(aktiv)


def test_1264_skill_zeitraeume_nennen_den_heutigen_stand(umgebung):
    db, mcp = umgebung
    sid = _skill(db, "Altwerkzeug", end_year=2004)
    erg = _call(mcp, "skill_zeitraeume_anzeigen", {"skill_id": sid})
    assert erg["ruht"] is True
    assert erg["level_aktuell"] is None and erg["level_spitze"] == 5
    assert "ruht seit 2004" in erg["stand"]


def test_1264_begriffs_vorschlaege_ordnen_nach_dem_heutigen_stand(umgebung, monkeypatch):
    db, mcp = umgebung
    monkeypatch.setattr(type(db), "is_ki_feature_enabled", lambda self, *a, **k: False)
    _skill(db, "Altwerkzeug", end_year=2004)           # Spitze 5, ruht
    _skill(db, "Neuwerkzeug", level=3)                 # heute 3
    erg = _call(mcp, "keyword_vorschlaege")
    plus = erg["profil_vorschlaege"]["plus"]
    assert plus.index("Neuwerkzeug") < plus.index("Altwerkzeug")


def test_1264_keine_stelle_rechnet_mehr_mit_der_spitze():
    """Wächter: Sortieren und „Experte“ über `level` (die Spitze) kommen in den drei Modulen nicht mehr vor."""
    src = _repo() / "src" / "bewerbungs_assistent"
    for rel in ("export.py", "tools/analyse.py"):
        text = (src / rel).read_text(encoding="utf-8")
        assert '-(s.get("level"' not in text, rel
        assert 'get("level") or 0) >= 4' not in text, rel
