"""Tests fuer v1.7.10 — #778 (C29): Scoring-Kalibrierung.

Praxis-Fall 24.07.2026: Nach Keyword-Erweiterung (13 -> 34 MUSS) lieferte
der Automatik-Lauf 220 Stellen zwischen 30 und 60 — haeufige Begriffe
schlugen seltene, Masse schlug Klasse. Kern-Absicherungen hier:

1. kalibrierung_backtest ist eine SCHATTENRECHNUNG — kein Score in der
   jobs-Tabelle aendert sich, egal mit welchen Parametern.
2. Schwellen-Vorschlag = niedrigster Bewerbungs-Score x 0.8.
3. Einzelgewichte pro Keyword ueberschreiben das Kategorie-Gewicht.
4. IDF + Top-5-Deckelung wirken NUR als Opt-in; Default unveraendert.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1710_778_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _result(raw):
    if isinstance(raw, tuple):
        raw = raw[1] if len(raw) > 1 else raw[0]
    if hasattr(raw, "structured_content"):
        raw = raw.structured_content
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    return raw


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


def _job(db, hash_, titel, beschreibung, aktiv=1, dismiss=None):
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, title, company, location, url, source, "
        "description, is_active, dismiss_reason, profile_id, found_at, updated_at, score) "
        "VALUES (?,?,?,?,?,?,?,?,?,?, '2026-07-01','2026-07-01', 10)",
        (hash_, titel, "TestCo", "Hamburg", f"https://example.com/{hash_}",
         "demo", beschreibung, aktiv, dismiss, db.get_active_profile_id()),
    )
    conn.commit()


# ------------------------------------------------------------ Schattenrechnung

def test_778_backtest_persistiert_niemals(setup_env):
    """Kernforderung: kein Score-Overwrite, auch nicht mit dry_run=False."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    db.set_search_criteria("keywords_muss", ["PLM"])
    _job(db, "bt1", "PLM Manager", "PLM Teamcenter Windchill. " * 20)
    _job(db, "bt2", "Koch", "Kueche Restaurant. " * 20, aktiv=0,
         dismiss="falsches_fachgebiet")
    db.add_application({"company": "TestCo", "title": "PLM Manager",
                        "job_hash": "bt1"})

    vorher = {r["hash"]: r["score"] for r in db.connect().execute(
        "SELECT hash, score FROM jobs").fetchall()}
    res = _result(_call(mcp, "kalibrierung_backtest",
                        {"modus": "beide", "dry_run": False}))
    assert res["persistiert"] is False
    nachher = {r["hash"]: r["score"] for r in db.connect().execute(
        "SELECT hash, score FROM jobs").fetchall()}
    assert vorher == nachher, "Backtest hat Scores veraendert — verboten!"


def test_778_schwellen_vorschlag_ist_min_mal_08(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    db.set_search_criteria("keywords_muss", ["PLM"])
    db.set_search_criteria("gewichtung", {"muss": 6})
    _job(db, "s1", "PLM Manager", "PLM PLM. " * 20)
    db.add_application({"company": "TestCo", "title": "PLM Manager",
                        "job_hash": "s1"})
    res = _result(_call(mcp, "kalibrierung_backtest", {}))
    var = res["varianten"]["aktuell"]
    min_pos = var["bewerbungen"]["min"]
    assert var["schwellen_vorschlag"] == int(min_pos * 0.8)


def test_778_warnung_wenn_bewerbung_unter_aktueller_schwelle(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    db.set_search_criteria("keywords_muss", ["PLM"])
    db.set_search_criteria("min_score_schwelle", 90)  # absichtlich absurd hoch
    _job(db, "w1", "PLM Manager", "PLM. " * 20)
    db.add_application({"company": "TestCo", "title": "PLM Manager",
                        "job_hash": "w1"})
    res = _result(_call(mcp, "kalibrierung_backtest", {}))
    var = res["varianten"]["aktuell"]
    assert "warnung_unter_aktueller_schwelle" in var, var
    assert var["warnung_unter_aktueller_schwelle"][0]["firma"] == "TestCo"


# ------------------------------------------------------------ Einzelgewichte

def test_778_einzelgewicht_ueberschreibt_kategorie(setup_env):
    """'Arbeitnehmerueberlassung' soll milder wirken koennen als 'Bauwesen'."""
    db, _ = setup_env
    from bewerbungs_assistent.job_scraper import calculate_score
    db.set_search_criteria("keywords_muss", ["PLM"])
    db.set_search_criteria("keywords_minus", ["Arbeitnehmerueberlassung"])
    db.set_search_criteria("gewichtung", {"muss": 6, "minus": 6})

    job = {"title": "PLM Manager", "company": "X",
           "description": "PLM Rolle in Arbeitnehmerueberlassung. " * 10}
    criteria = db.get_search_criteria()
    score_voll = calculate_score(dict(job), criteria)

    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "suchkriterien_bearbeiten", {
        "kategorie": "minus", "aktion": "gewichten",
        "werte": ["Arbeitnehmerueberlassung"], "gewicht": 2}))
    assert res["status"] == "gewichtet"

    criteria2 = db.get_search_criteria()
    score_mild = calculate_score(dict(job), criteria2)
    assert score_mild == score_voll + 4, (
        f"Malus 6 -> 2 muss den Score um 4 heben: {score_voll} -> {score_mild}")

    # Zuruecksetzen stellt das Kategorie-Gewicht wieder her
    _call(mcp, "suchkriterien_bearbeiten", {
        "kategorie": "minus", "aktion": "gewicht_entfernen",
        "werte": ["Arbeitnehmerueberlassung"]})
    assert calculate_score(dict(job), db.get_search_criteria()) == score_voll


# ------------------------------------------------------------ IDF-Opt-in

def _korpus_aufbauen(db, n_gesamt=60, n_mit_haeufig=30, n_mit_selten=2):
    """Korpus: 'Digital Transformation' in der Haelfte, 'PRO.FILE' fast nie."""
    for i in range(n_gesamt):
        teile = ["Software Rolle."]
        if i < n_mit_haeufig:
            teile.append("Digital Transformation ist uns wichtig.")
        if i < n_mit_selten:
            teile.append("PRO.FILE Administration.")
        _job(db, f"k{i}", f"Rolle {i}", " ".join(teile) * 5)


def test_778_default_verhalten_unveraendert(setup_env):
    """Ohne Opt-in: haeufig == selten, exakt wie vor v1.7.10."""
    db, _ = setup_env
    from bewerbungs_assistent.job_scraper import calculate_score
    _korpus_aufbauen(db)
    db.set_search_criteria("keywords_muss", ["Digital Transformation", "PRO.FILE"])
    db.set_search_criteria("gewichtung", {"muss": 6})
    criteria = db.get_search_criteria()
    assert "_idf_faktoren" not in criteria

    j_haeufig = {"title": "X", "description": "Digital Transformation. " * 10}
    j_selten = {"title": "X", "description": "PRO.FILE Rollout. " * 10}
    assert calculate_score(dict(j_haeufig), criteria) == calculate_score(
        dict(j_selten), criteria), "Default darf sich nicht aendern"


def test_778_idf_wertet_haeufige_begriffe_ab(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    from bewerbungs_assistent.job_scraper import calculate_score
    _korpus_aufbauen(db)
    db.set_search_criteria("keywords_muss", ["Digital Transformation", "PRO.FILE"])
    db.set_search_criteria("gewichtung", {"muss": 6})

    res = _result(_call(mcp, "suchkriterien_bearbeiten", {
        "kategorie": "scoring", "aktion": "idf", "werte": ["an"]}))
    assert res["status"] == "idf_aktiviert"

    criteria = db.get_search_criteria()
    assert criteria.get("_idf_faktoren"), "Opt-in muss Faktoren injizieren"

    j_haeufig = {"title": "X", "description": "Digital Transformation. " * 10}
    j_selten = {"title": "X", "description": "PRO.FILE Rollout. " * 10}
    s_h = calculate_score(dict(j_haeufig), criteria)
    s_s = calculate_score(dict(j_selten), criteria)
    assert s_s > s_h, (
        f"Seltenes Keyword muss mehr zaehlen: selten={s_s}, haeufig={s_h}")


def test_778_idf_top5_deckelung(setup_env):
    """7 MUSS-Treffer zaehlen im IDF-Modus wie die 5 staerksten."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    from bewerbungs_assistent.job_scraper import calculate_score
    _korpus_aufbauen(db)
    kws = [f"Spezialbegriff{i}" for i in range(7)]
    db.set_search_criteria("keywords_muss", kws)
    db.set_search_criteria("gewichtung", {"muss": 6})
    _call(mcp, "suchkriterien_bearbeiten", {
        "kategorie": "scoring", "aktion": "idf", "werte": ["an"]})
    criteria = db.get_search_criteria()

    text = " ".join(kws) + ". " + "Fuelltext. " * 10
    job = {"title": "X", "description": text * 3}
    score = calculate_score(dict(job), criteria)
    # Alle 7 Begriffe kommen im Korpus nicht vor -> Faktor 1.0, Basis 6.
    # Ohne Deckelung waeren es 42 Punkte, mit Top-5 sind es 30.
    assert score <= 30 + 1, f"Top-5-Deckelung greift nicht: {score}"
    assert score >= 30, f"Deckelung zu aggressiv: {score}"


def test_778_backtest_vergleicht_beide_modi(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _korpus_aufbauen(db)
    db.set_search_criteria("keywords_muss", ["Digital Transformation", "PRO.FILE"])
    _job(db, "pos1", "PRO.FILE Admin", "PRO.FILE Administration. " * 20)
    db.add_application({"company": "TestCo", "title": "PRO.FILE Admin",
                        "job_hash": "pos1"})
    res = _result(_call(mcp, "kalibrierung_backtest", {"modus": "beide"}))
    assert "aktuell" in res["varianten"] and "idf" in res["varianten"]
    assert "vergleich" in res


# ------------------------------------------------------------ DE/EN-Paare

def test_778_ausschluss_hinweis_auf_englisches_pendant(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "suchkriterien_bearbeiten", {
        "kategorie": "ausschluss", "aktion": "hinzufuegen",
        "werte": ["Werkstudent"]}))
    assert "hinweis_sprachpaare" in res, res
    assert "Working Student" in res["hinweis_sprachpaare"]

    # Ist das Pendant schon drin, kommt kein Hinweis
    res2 = _result(_call(mcp, "suchkriterien_bearbeiten", {
        "kategorie": "ausschluss", "aktion": "hinzufuegen",
        "werte": ["Working Student", "Praktikant"]}))
    hint = res2.get("hinweis_sprachpaare", "")
    assert "Working Student" not in hint
    assert "Intern" in hint  # Praktikant -> Intern fehlt noch
