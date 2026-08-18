"""Tests fuer v1.7.17 — #910: Entfernungs-Malus gegen Gehalt verrechnen.

"km sind ein Malus, der durch Verdienst behoben werden kann" — Entfernung
ist ein Preis (Pendeln, Zweitwohnung), kein Fachkriterium. Kompensation
nur mit ECHTEN Gehaltsangaben (#827), Default aus (spanne=0).
"""
import importlib
import os
import shutil
import tempfile

import pytest


CRITERIA_BASIS = {
    "keywords_muss": ["PLM"], "keywords_plus": [], "keywords_minus": [],
    "keywords_ausschluss": [], "min_gehalt": 80000,
    "max_entfernung": {"festanstellung": 50},
}


def _fernjob(gehalt=None, estimated=False):
    job = {"title": "PLM Architekt", "description": "PLM Rollout. " * 30,
           "employment_type": "festanstellung", "distance_km": 620.0}
    if gehalt is not None:
        job["salary_min"] = gehalt
        job["salary_estimated"] = estimated
    return job


def test_910_grad_0_50_100_und_schaetzung():
    from bewerbungs_assistent.job_scraper import entfernungs_kompensationsgrad
    krit = dict(CRITERIA_BASIS, _entfernung_gehalt_spanne=30000)
    assert entfernungs_kompensationsgrad(_fernjob(80000), krit) == 0.0
    assert entfernungs_kompensationsgrad(_fernjob(95000), krit) == 0.5
    assert entfernungs_kompensationsgrad(_fernjob(110000), krit) == 1.0
    assert entfernungs_kompensationsgrad(_fernjob(200000), krit) == 1.0, \
        "Grad ist bei 1.0 gedeckelt"
    assert entfernungs_kompensationsgrad(
        _fernjob(200000, estimated=True), krit) == 0.0, \
        "Schaetzungen kompensieren NIE (#827)"
    assert entfernungs_kompensationsgrad(_fernjob(None), krit) == 0.0


def test_910_spanne_0_reproduziert_heutiges_verhalten():
    from bewerbungs_assistent.job_scraper import calculate_score, fit_analyse
    ohne = dict(CRITERIA_BASIS)
    mit_null = dict(CRITERIA_BASIS, _entfernung_gehalt_spanne=0)
    job = _fernjob(110000)
    assert calculate_score(dict(job), ohne) == calculate_score(
        dict(job), mit_null)
    assert fit_analyse(dict(job), ohne)["total_score"] == fit_analyse(
        dict(job), mit_null)["total_score"]


def test_910_calculate_score_kompensiert():
    from bewerbungs_assistent.job_scraper import calculate_score
    krit = dict(CRITERIA_BASIS, _entfernung_gehalt_spanne=30000)
    # identischer Job, nur das Gehalt unterscheidet sich — der einzige
    # Score-Unterschied neben dem Gehaltsbonus ist der Entfernungs-Malus
    s_niedrig = calculate_score(_fernjob(80000), krit)
    s_hoch = calculate_score(_fernjob(110000), krit)
    ohne_komp = dict(CRITERIA_BASIS)
    s_hoch_ohne = calculate_score(_fernjob(110000), ohne_komp)
    assert s_hoch > s_hoch_ohne, \
        "voll kompensiert muss besser abschneiden als unkompensiert"
    assert s_hoch > s_niedrig


def test_910_fit_analyse_zeigt_basis_grad_ergebnis():
    from bewerbungs_assistent.job_scraper import fit_analyse
    krit = dict(CRITERIA_BASIS, _entfernung_gehalt_spanne=30000)
    res = fit_analyse(_fernjob(95000), krit)
    basis = [k for k in res["factors"] if k.startswith("Entfernung:")]
    komp = [k for k in res["factors"] if "kompensiert" in k]
    assert basis, res["factors"]
    assert komp and "50 %" in komp[0], res["factors"]
    assert res["factors"][komp[0]] == round(
        -res["factors"][basis[0]] * 0.5, 1), \
        "Gutschrift = Basis-Malus * Kompensationsgrad"


def test_910_fit_analyse_ohne_echtes_gehalt_keine_kompensation():
    from bewerbungs_assistent.job_scraper import fit_analyse
    krit = dict(CRITERIA_BASIS, _entfernung_gehalt_spanne=30000)
    res = fit_analyse(_fernjob(110000, estimated=True), krit)
    assert not any("kompensiert" in k for k in res["factors"]), \
        res["factors"]


def test_910_scoring_service_und_injektion():
    """Ende-zu-Ende: Regler setzen -> get_search_criteria injiziert ->
    apply_scoring_adjustments kompensiert den Bracket-Malus."""
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1717_910_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    try:
        db.set_search_criteria("min_gehalt", 80000)
        assert "_entfernung_gehalt_spanne" not in db.get_search_criteria(), \
            "ohne Regler keine Injektion (Opt-in)"
        db.set_scoring_config("entfernung_gehalt_kompensation", "spanne",
                              30000)
        krit = db.get_search_criteria()
        assert krit.get("_entfernung_gehalt_spanne") == 30000

        from bewerbungs_assistent.services.scoring_service import (
            apply_scoring_adjustments)
        job_voll = _fernjob(110000)
        job_ohne = _fernjob(80000)
        res_voll = apply_scoring_adjustments(dict(job_voll), 40, db)
        res_ohne = apply_scoring_adjustments(dict(job_ohne), 40, db)
        ent_voll = [a for a in res_voll["adjustments"]
                    if a["dimension"] == "Entfernung"]
        ent_ohne = [a for a in res_ohne["adjustments"]
                    if a["dimension"] == "Entfernung"]
        assert ent_ohne and ent_ohne[0]["punkte"] < 0
        assert ent_voll and ent_voll[0]["punkte"] == 0, \
            f"voll kompensiert = Malus 0: {ent_voll}"
        assert "kompensiert" in ent_voll[0]["detail"]
    finally:
        db.close()
        shutil.rmtree(tmpdir, ignore_errors=True)
