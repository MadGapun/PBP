"""Regression #698: Hochschulabschluss-Malus konfigurierbar.

Der frueher hart codierte -2-Malus in fit_analyse ist jetzt ueber
scoring_konfigurieren('hochschulabschluss','fehlt') steuerbar — Default -2,
wert=0 deaktiviert die Punkte, ignorieren=True deaktiviert Malus UND
Risiko-Hinweis komplett.

HARTE ISOLATIONS-REGEL: db.db_path im Temp-Verzeichnis (BA_DATA_DIR).
"""
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_698_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    from bewerbungs_assistent.database import Database
    d = Database()
    d.initialize()
    d.save_profile({"name": "Test"})
    assert str(tmpdir) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    yield d
    d.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


_DEGREE_JOB = {
    "title": "Senior Ingenieur",
    "description": ("Abgeschlossenes Hochschulstudium der Ingenieurwissenschaften "
                    "erforderlich. Mehrjaehrige Berufserfahrung erwuenscht."),
}


# ============= DB-Helfer + Konfig =============

def test_698_default_minus_2_aus_init(db):
    # frische DB legt den Default-Regler an
    assert db.get_hochschulabschluss_malus() == -2
    dims = {(c["dimension"], c["sub_key"]) for c in db.get_scoring_config()}
    assert ("hochschulabschluss", "fehlt") in dims


def test_698_konfigurierbar(db):
    db.set_scoring_config("hochschulabschluss", "fehlt", 0, False)
    assert db.get_hochschulabschluss_malus() == 0
    db.set_scoring_config("hochschulabschluss", "fehlt", -5, False)
    assert db.get_hochschulabschluss_malus() == -5


def test_698_ignorieren_gibt_none(db):
    db.set_scoring_config("hochschulabschluss", "fehlt", -2, True)
    assert db.get_hochschulabschluss_malus() is None


def test_698_get_search_criteria_bleibt_sauber(db):
    # Der Malus ist KEIN Suchkriterium — get_search_criteria darf den
    # computed key NICHT mitliefern (sonst leakt er in /api/search-criteria).
    crit = db.get_search_criteria()
    assert "_hochschulabschluss_malus" not in crit


# ============= fit_analyse-Wirkung =============
# Die Aufrufer (MCP-Tool + Dashboard) injizieren den Malus in criteria —
# hier exakt nachgestellt: criteria + helper, dann fit_analyse.

def _crit_mit_malus(db):
    crit = db.get_search_criteria()
    crit["_hochschulabschluss_malus"] = db.get_hochschulabschluss_malus()
    return crit


def test_698_fit_analyse_default_malus(db):
    from bewerbungs_assistent.job_scraper import fit_analyse
    res = fit_analyse(_DEGREE_JOB, _crit_mit_malus(db))
    assert res["hochschulabschluss_gefordert"] is True
    assert res["factors"].get("Hochschulabschluss fehlt") == -2
    assert any("HOCHSCHULABSCHLUSS" in r for r in res["risks"])


def test_698_fit_analyse_ignoriert_keine_punkte_kein_risiko(db):
    from bewerbungs_assistent.job_scraper import fit_analyse
    db.set_scoring_config("hochschulabschluss", "fehlt", -2, True)  # ignorieren
    res = fit_analyse(_DEGREE_JOB, _crit_mit_malus(db))
    assert "Hochschulabschluss fehlt" not in res["factors"]
    assert not any("HOCHSCHULABSCHLUSS" in r for r in res["risks"])


def test_698_fit_analyse_wert_null_zeigt_risiko_ohne_punkte(db):
    from bewerbungs_assistent.job_scraper import fit_analyse
    db.set_scoring_config("hochschulabschluss", "fehlt", 0, False)
    res = fit_analyse(_DEGREE_JOB, _crit_mit_malus(db))
    assert "Hochschulabschluss fehlt" not in res["factors"]
    # Risiko-Hinweis bleibt informativ
    assert any("HOCHSCHULABSCHLUSS" in r for r in res["risks"])
