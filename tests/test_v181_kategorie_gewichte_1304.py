"""#1304: Die Kategorie-Gewichte lassen sich ueber Claude setzen.

`gewichtung` (muss/plus/minus/remote/naehe/fern_malus/gehalt) wurde von `_parse_weights` gelesen, aber kein Werkzeug schrieb
sie; nur die Regler im Dashboard (Profil > Suchbegriffe) taten es. Gemeldet von einem Nutzer aus 1.8.1: der Umweg ueber
Einzelgewichte wird bei jedem neuen Begriff still falsch, und Tor-Obergrenze und Neigung lesen ohnehin das Kategorie-Gewicht.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest

from bewerbungs_assistent.job_scraper import _parse_weights, calculate_score


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v181_1304_")
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


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def _gewichten(mcp, werte, gewicht):
    return _call(mcp, "suchkriterien_bearbeiten",
                 {"kategorie": "scoring", "aktion": "gewichten", "werte": werte, "gewicht": gewicht})


def _scoring_kriterien(db):
    from bewerbungs_assistent.services.scoring_kriterien import fuer_scoring
    return fuer_scoring(db)


def test_der_gemeldete_fall_muss_1_plus_3(umgebung):
    db, mcp = umgebung
    db.set_search_criteria("gewichtung", {"remote": 5, "firmenabsatz_faktor": 0.5})
    assert "fehler" not in _gewichten(mcp, ["muss"], 1)
    res = _gewichten(mcp, ["plus"], 3)
    assert res["status"] == "kategorie_gewicht_gesetzt", res
    assert res["geaendert"] == {"plus": {"vorher": 1, "nachher": 3.0}}
    w = _parse_weights(_scoring_kriterien(db))
    assert (w["muss"], w["plus"]) == (1.0, 3.0)
    # alles andere in `gewichtung` bleibt stehen, auch was kein Regler zeigt
    assert w["remote"] == 5 and w["firmenabsatz_faktor"] == 0.5
    # dieselbe Form, die das Dashboard schreibt und liest (criteria.gewichtung.muss)
    gespeichert = db.get_search_criteria()["gewichtung"]
    assert isinstance(gespeichert, dict) and gespeichert["muss"] == 1.0


def test_mehrere_kategorien_auf_einmal(umgebung):
    db, mcp = umgebung
    res = _gewichten(mcp, ["Remote", " naehe "], 0)
    assert "fehler" not in res, res
    w = _parse_weights(_scoring_kriterien(db))
    assert (w["remote"], w["naehe"]) == (0.0, 0.0)


def test_plus_bleibt_gedeckelt_und_die_antwort_sagt_es(umgebung):
    """Gemessen beim Bau: PLUS zaehlt hoechstens Deckel x Pflichtpunkte - ohne Hinweis waere PLUS=3 eine stille Wirkungslosigkeit."""
    db, mcp = umgebung
    db.set_search_criteria("keywords_muss", ["Stammdaten"])
    db.set_search_criteria("keywords_plus", ["Lieferantenportal"])
    job = {"title": "Sachbearbeitung", "company": "Musterfirma GmbH",
           "description": "Stammdaten pflegen im Lieferantenportal des Einkaufs."}
    vorher = calculate_score(dict(job), _scoring_kriterien(db))
    res = _gewichten(mcp, ["plus"], 3)
    assert calculate_score(dict(job), _scoring_kriterien(db)) == vorher
    assert "Deckel" in res["hinweis"] and "werte=['rahmen']" in res["hinweis"]
    assert "Deckel" not in _gewichten(mcp, ["muss"], 1)["hinweis"]


def test_das_gewicht_wirkt_auf_die_punkte(umgebung):
    db, mcp = umgebung
    db.set_search_criteria("rahmen_deckel_faktor", 10)      # den Deckel aus dem Weg, hier zaehlt nur das Gewicht
    db.set_search_criteria("keywords_muss", ["Stammdaten"])
    db.set_search_criteria("keywords_plus", ["Lieferantenportal"])
    job = {"title": "Sachbearbeitung", "company": "Musterfirma GmbH",
           "description": "Stammdaten pflegen im Lieferantenportal des Einkaufs."}
    vorher = calculate_score(dict(job), _scoring_kriterien(db))
    _gewichten(mcp, ["plus"], 3)
    nachher = calculate_score(dict(job), _scoring_kriterien(db))
    assert nachher > vorher, (vorher, nachher)


def test_neue_begriffe_folgen_dem_kategorie_gewicht(umgebung):
    """Der Kern der Meldung: ein Einzelgewicht gilt nur fuer seinen Begriff, das Kategorie-Gewicht auch fuer neue."""
    db, mcp = umgebung
    db.set_search_criteria("rahmen_deckel_faktor", 10)
    db.set_search_criteria("keywords_muss", ["Stammdaten"])
    _gewichten(mcp, ["plus"], 3)
    _call(mcp, "suchkriterien_bearbeiten", {"kategorie": "plus", "aktion": "hinzufügen", "werte": ["Lieferantenportal"]})
    job = {"title": "Sachbearbeitung", "company": "Musterfirma GmbH",
           "description": "Stammdaten pflegen im Lieferantenportal des Einkaufs."}
    mit_kategorie = calculate_score(dict(job), _scoring_kriterien(db))
    db.set_search_criteria("gewichtung", {"plus": 1})
    assert mit_kategorie > calculate_score(dict(job), _scoring_kriterien(db))


@pytest.mark.parametrize("werte,gewicht", [
    (["muss"], -1), (["muss"], 10.5), (["seitlich"], 2), ([], 2), (["muss", "ausschluss"], 2)])
def test_unsinniges_wird_abgewiesen_und_nichts_gespeichert(umgebung, werte, gewicht):
    db, mcp = umgebung
    res = _gewichten(mcp, werte, gewicht)
    assert "fehler" in res, res
    assert "gewichtung" not in (db.get_search_criteria() or {})


def test_einzelgewichte_mit_vorrang_werden_genannt(umgebung):
    db, mcp = umgebung
    db.set_search_criteria("keywords_muss", ["Stammdaten", "Migration"])
    _call(mcp, "suchkriterien_bearbeiten",
          {"kategorie": "muss", "aktion": "gewichten", "werte": ["Migration"], "gewicht": 4})
    res = _gewichten(mcp, ["muss"], 1)
    assert res["einzelgewichte_mit_vorrang"] == {"muss": ["Migration"]}
    assert "Vorrang" in res["hinweis"] and "Migration" in res["hinweis"]


def test_einzelgewichte_bleiben_wie_vorher(umgebung):
    """Regression: kategorie='muss' + aktion='gewichten' setzt weiter das Einzelgewicht eines Begriffs."""
    db, mcp = umgebung
    db.set_search_criteria("keywords_muss", ["Stammdaten"])
    res = _call(mcp, "suchkriterien_bearbeiten",
                {"kategorie": "muss", "aktion": "gewichten", "werte": ["Stammdaten"], "gewicht": 2})
    assert res["status"] == "gewichtet", res
    assert db.get_search_criteria()["keyword_gewichte"] == {"stammdaten": 2.0}
    assert "gewichtung" not in db.get_search_criteria()
