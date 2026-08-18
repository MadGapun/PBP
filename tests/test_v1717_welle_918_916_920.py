"""Tests fuer v1.7.17 — #918 (Schaetz-Gehalt in fit_analyse), #916
(Merge-Datenverlust), #920 (EUR/hour).

#918: Der #827-Fix sass nur in scoring_service — fit_analyse vergab
weiter +8 fuer eine Zahl, die es nicht gibt (18 % des Gesamtscores).
#916: termin_dubletten_bereinigen verwarf beim Merge den Duplikat-Titel
— dort standen die einzigen Gespraechspartner-Namen.
#920: "Rate: 100 EUR/hour" wurde als 100 EUR/TAG gelesen (Faktor 8 zu
niedrig) und min_stundensatz nie ausgewertet — passende Freelance-
Stellen verschwanden lautlos.
"""
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1717_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


# ------------------------------------------------------------- #920

def test_920_eur_hour_wird_als_stundensatz_erkannt():
    from bewerbungs_assistent.job_scraper import extract_salary_from_text
    s_min, s_max, typ = extract_salary_from_text(
        "- Rate: 100 EUR/hour (negotiable)\n- Hours: 51,5 hours per week")
    assert typ == "stuendlich", (s_min, s_max, typ)
    assert s_min == 100


def test_920_varianten():
    from bewerbungs_assistent.job_scraper import extract_salary_from_text
    for text, erwartet in [
        ("85-95 EUR/h remote", (85, "stuendlich")),
        ("€90 per hour", (90, "stuendlich")),
        ("Stundensatz: 65€", (65, "stuendlich")),
        ("Tagessatz: 900€", (900, "taeglich")),
    ]:
        s_min, _, typ = extract_salary_from_text(text)
        assert (s_min, typ) == erwartet, (text, s_min, typ)


def test_920_fit_analyse_vergleicht_gegen_min_stundensatz():
    from bewerbungs_assistent.job_scraper import fit_analyse
    job = {"title": "PLM Administrator", "description": "PLM Aufgaben. " * 20,
           "employment_type": "freelance", "salary_min": 100,
           "salary_type": "stuendlich", "salary_estimated": False}
    criteria = {"keywords_muss": ["PLM"], "keywords_plus": [],
                "keywords_minus": [], "keywords_ausschluss": [],
                "min_stundensatz": 100, "min_tagessatz": 1080}
    res = fit_analyse(job, criteria)
    # 100 EUR/h trifft min_stundensatz exakt -> Bonus, KEIN Unter-Risiko
    assert "Gehalt passt zu Erwartung" in res["factors"], res["factors"]
    assert not any("unter Mindestvorstellung" in r for r in res["risks"]), \
        res["risks"]


def test_920_stundensatz_unter_wunsch_wird_korrekt_gemeldet():
    from bewerbungs_assistent.job_scraper import fit_analyse
    job = {"title": "PLM Administrator", "description": "PLM. " * 30,
           "employment_type": "freelance", "salary_min": 60,
           "salary_type": "stuendlich", "salary_estimated": False}
    criteria = {"keywords_muss": ["PLM"], "keywords_plus": [],
                "keywords_minus": [], "keywords_ausschluss": [],
                "min_stundensatz": 100}
    res = fit_analyse(job, criteria)
    risiken = [r for r in res["risks"] if "Mindestvorstellung" in r]
    assert risiken and "EUR/Stunde" in risiken[0], res["risks"]


# ------------------------------------------------------------- #918

def test_918_fit_analyse_schaetzung_ist_neutral():
    """DER Belegfall: +8 fuer eine Anzeige OHNE Gehaltsangabe."""
    from bewerbungs_assistent.job_scraper import fit_analyse
    job = {"title": "Transformation Director",
           "description": "PLM Transformation. " * 20,
           "employment_type": "festanstellung",
           "salary_min": 108000, "salary_max": 162000,
           "salary_estimated": True}
    criteria = {"keywords_muss": ["PLM"], "keywords_plus": [],
                "keywords_minus": [], "keywords_ausschluss": [],
                "min_gehalt": 80000, "gewichtung": {"gehalt": 8}}
    res = fit_analyse(job, criteria)
    assert "Gehalt passt zu Erwartung" not in res["factors"], \
        "Schaetzung darf keinen Bonus geben (#827/#918)"
    neutral = [k for k in res["factors"] if "Schaetzung" in k]
    assert neutral and res["factors"][neutral[0]] == 0, \
        "transparenter 0-Eintrag muss die leere Dimension erklaeren"


def test_918_echte_angabe_wirkt_weiter():
    from bewerbungs_assistent.job_scraper import fit_analyse
    job = {"title": "PLM Lead", "description": "PLM. " * 30,
           "employment_type": "festanstellung",
           "salary_min": 95000, "salary_estimated": False}
    criteria = {"keywords_muss": ["PLM"], "keywords_plus": [],
                "keywords_minus": [], "keywords_ausschluss": [],
                "min_gehalt": 80000}
    res = fit_analyse(job, criteria)
    assert "Gehalt passt zu Erwartung" in res["factors"]


# ------------------------------------------------------------- #916

def _termin(db, aid, titel, notes="", platform="", created="2026-06-01"):
    return db.add_meeting({
        "application_id": aid, "meeting_date": "2026-06-02T10:00:00",
        "title": titel, "notes": notes, "platform": platform,
        "meeting_type": "interview"})


def test_916_abweichender_titel_wandert_in_notizen(setup_env):
    """Regressionstest aus dem Issue: der Personenname bleibt auffindbar."""
    db, _ = setup_env
    from bewerbungs_assistent.services.termin_dubletten import (
        finde_alle_dubletten, zusammenfuehren)
    aid = db.add_application({"company": "PLM-Haus Sued AG",
                              "title": "Lead", "status": "interview"})
    _termin(db, aid, "Kennenlernen — PLM-Haus Sued AG")
    _termin(db, aid, "Erstgespraech mit Erika Musterfrau")

    paare = finde_alle_dubletten(db)
    assert len(paare) == 1
    paar = paare[0]
    # Master-Wahl nach Informationsgehalt: der Titel MIT Namen gewinnt
    assert "Erika Musterfrau" in paar["master_titel"], paar
    assert "verlust_ohne_uebernahme" in paar
    assert "title" in paar["verlust_ohne_uebernahme"]

    master = next(m for m in db.get_meetings_for_application(aid)
                  if str(m["id"]) == str(paar["master_id"]))
    dublette = next(m for m in db.get_meetings_for_application(aid)
                    if str(m["id"]) == str(paar["duplikat_id"]))
    res = zusammenfuehren(db, master, dublette)
    assert "title" in res["texte_uebernommen"], res
    neu = next(m for m in db.get_meetings_for_application(aid)
               if str(m["id"]) == str(paar["master_id"]))
    assert "Erika Musterfrau" in (neu.get("title") or ""), "Master-Titel bleibt"
    assert "Kennenlernen" in (neu.get("notes") or ""), \
        "abweichender Duplikat-Titel muss in den Notizen stehen"
    assert "Alternative Bezeichnung" in (neu.get("notes") or "")


def test_916_gleiche_texte_erzeugen_keinen_anhang(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.termin_dubletten import (
        zusammenfuehren)
    aid = db.add_application({"company": "F", "title": "T",
                              "status": "interview"})
    m1 = _termin(db, aid, "Interview Runde 1")
    m2 = _termin(db, aid, "Interview Runde 1")
    a = next(m for m in db.get_meetings_for_application(aid)
             if str(m["id"]) == str(m1))
    b = next(m for m in db.get_meetings_for_application(aid)
             if str(m["id"]) == str(m2))
    res = zusammenfuehren(db, a, b)
    assert res["texte_uebernommen"] == []
    neu = next(m for m in db.get_meetings_for_application(aid)
               if str(m["id"]) == str(m1))
    assert "Alternative Bezeichnung" not in (neu.get("notes") or "")


def test_916_vorhandene_notizen_bleiben(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.termin_dubletten import (
        zusammenfuehren)
    aid = db.add_application({"company": "F", "title": "T",
                              "status": "interview"})
    m1 = _termin(db, aid, "Interview", notes="Wichtiger Kontext.")
    m2 = _termin(db, aid, "HR-Gespraech mit Erika Musterfrau")
    a = next(m for m in db.get_meetings_for_application(aid)
             if str(m["id"]) == str(m1))
    b = next(m for m in db.get_meetings_for_application(aid)
             if str(m["id"]) == str(m2))
    zusammenfuehren(db, a, b)
    neu = next(m for m in db.get_meetings_for_application(aid)
               if str(m["id"]) == str(m1))
    assert "Wichtiger Kontext." in neu["notes"], "Notizen nie ueberschreiben"
    assert "Erika Musterfrau" in neu["notes"]
