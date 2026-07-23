"""Regression #766: Anker-Pflicht — keine Stelle ohne URL, Dokument oder Kontakt.

Praxis-Fall 23.07.2026: Von acht aktiven Stellen hatte keine einen
nachvollziehbaren Weg zur Original-Ausschreibung. Mehrere davon waren per
`stelle_manuell_anlegen` mit einer zusammenfassenden Claude-NOTIZ statt der
echten Anzeige angelegt worden — ohne URL, ohne Kontakt. Folge: kein
Nachladen moeglich, Score kuenstlich niedrig, Bewerbung nur gegen eine
Zusammenfassung formulierbar.

Kern der Absicherung: die Stelle wird weiter angelegt (die Eingaben zu
verwerfen waere schlimmer), aber der Zustand wird hart benannt — im Tool-
Result, in der Liste und am Uebergang zur Bewerbung.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v179_766_")
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


# ------------------------------------------------------------- anker_status

def test_766_detail_url_ist_anker(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.stellen_anker import anker_status
    st = anker_status(db, {"hash": "x", "url": "https://careers.example.com/job/1234"})
    assert st["hat_anker"] is True
    assert st["anker"] == ["url_detail"]


def test_766_such_url_ist_kein_anker(setup_env):
    """Kernunterscheidung: eine Ergebnisliste ist keine Anzeige."""
    db, _ = setup_env
    from bewerbungs_assistent.services.stellen_anker import anker_status
    st = anker_status(db, {"hash": "x",
                           "url": "https://www.stepstone.de/jobs/plm-manager/in-hamburg"})
    assert st["hat_anker"] is False
    assert st["url_art"] == "suche"
    assert "hinweis_such_url" in st


def test_766_lange_beschreibung_ist_kein_anker(setup_env):
    """Genau der Issue-Fall: die Claude-Notiz liest sich wie eine Anzeige."""
    db, _ = setup_env
    from bewerbungs_assistent.services.stellen_anker import anker_status
    notiz = ("Manager PLM Strategy, vermittelt ueber einen Personalvermittler "
             "(Hamburg). Ueber Google Jobs gefunden. PLM-Strategie ist das "
             "Kernthema. Endkunde unbekannt, im Detail pruefen. ") * 3
    st = anker_status(db, {"hash": "x", "url": "", "description": notiz})
    assert st["hat_anker"] is False, "eine Zusammenfassung darf nie als Anker zaehlen"


# ------------------------------------------- stelle_manuell_anlegen

def test_766_ohne_anker_wird_gewarnt(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "Manager PLM Strategy", "firma": "Nordlicht Recruiting",
        "beschreibung": "Ueber Google Jobs gefunden, Endkunde unbekannt.",
        "quelle": "google_jobs",
    }))
    assert res["status"] == "angelegt", "die Stelle soll trotzdem angelegt werden"
    assert "anker_warnung" in res, res
    assert "OHNE ANKER" in res["nachricht"]


def test_766_kontakt_zaehlt_als_anker(setup_env):
    """Vermittler-Stelle ohne URL: der Recruiter-Kontakt rettet sie."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "INTERIM PLM Projektleiter", "firma": "Brueckenbau Personal",
        "quelle": "xing",
        "kontakt_name": "A. Beispiel", "kontakt_email": "a.beispiel@example.com",
    }))
    assert "anker_warnung" not in res, res
    assert res["anker"] == ["kontakt"]
    # Der Kontakt muss auch wirklich an der Stelle haengen. link_contact
    # speichert den profil-praefixierten Hash — deshalb hier aufloesen.
    assert db.get_contacts_for_target("job", db.resolve_job_hash(res["hash"]))


def test_766_detail_url_braucht_keine_warnung(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "IT Business Partner", "firma": "Beispiel AG",
        "url": "https://careers.beispiel-ag.example/job/Beispielstadt-IT-Partner/12345",
        "quelle": "firmenwebsite",
    }))
    assert "anker_warnung" not in res, res
    assert res["anker"] == ["url_detail"]


def test_766_such_url_loest_anker_warnung_aus(setup_env):
    """URL vorhanden, aber Suchseite -> trotzdem ohne Anker."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "Head of Systems Architecture", "firma": "Seewind Systeme",
        "url": "https://www.stepstone.de/jobs/architektur/in-hamburg",
    }))
    assert "anker_warnung" in res, res
    assert "Suchergebnis-Seite" in res["anker_warnung"]


# ------------------------------------------------------- stellen_anzeigen

def test_766_liste_markiert_stellen_ohne_anker(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _call(mcp, "stelle_manuell_anlegen", {
        "titel": "Consultant Operations", "firma": "Kranich Consulting", "quelle": "linkedin"})
    _call(mcp, "stelle_manuell_anlegen", {
        "titel": "Solution Architect", "firma": "Lindwurm Software",
        "url": "https://careers.lindwurm-software.example/job/987"})

    res = _result(_call(mcp, "stellen_anzeigen", {}))
    ohne = [s for s in res["stellen"] if s.get("ohne_anker")]
    mit = [s for s in res["stellen"] if not s.get("ohne_anker")]
    assert len(ohne) == 1 and "Consultant" in ohne[0]["titel"]
    assert len(mit) == 1
    assert res["ohne_anker_anzahl"] == 1
    assert "ohne_anker_hinweis" in res


# ------------------------------------------------ Uebergang zur Bewerbung

def test_766_bewerbung_ohne_anker_warnt_vor_unterlagen(setup_env):
    """Die eigentliche Gefahr aus dem Issue: Unterlagen gegen eine
    Zusammenfassung statt gegen die Ausschreibung optimieren."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    angelegt = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "Manager PLM Strategy", "firma": "Nordlicht Recruiting",
        "beschreibung": "Notiz: ueber Google Jobs gefunden.", "quelle": "google_jobs"}))

    res = _result(_call(mcp, "bewerbung_erstellen", {
        "title": "Manager PLM Strategy", "company": "Nordlicht Recruiting",
        "job_hash": angelegt["hash"], "bereits_beworben": False}))
    assert res["status"] == "erstellt"
    assert "anker_warnung" in res, res
    assert "anker_naechster_schritt" in res


def test_766_bewerbung_mit_ansprechpartner_ist_verankert(setup_env):
    """Ansprechpartner auf Bewerbungsebene zaehlt — bei Vermittlern oft alles,
    was es gibt."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    angelegt = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "INTERIM PLM Lead", "firma": "Brueckenbau Personal", "quelle": "xing"}))
    res = _result(_call(mcp, "bewerbung_erstellen", {
        "title": "INTERIM PLM Lead", "company": "Brueckenbau Personal",
        "job_hash": angelegt["hash"], "bereits_beworben": False,
        "ansprechpartner": "B. Muster", "kontakt_email": "b.muster@example.com"}))
    assert "anker_warnung" not in res, res


def test_766_bewerbung_mit_detail_url_ist_verankert(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "bewerbung_erstellen", {
        "title": "IT Business Partner", "company": "Nordwind Pharma",
        "url": "https://careers.nordwind-pharma.example/job/4711", "bereits_beworben": False}))
    assert "anker_warnung" not in res, res
    assert res["anker"] == ["url_detail"]


def test_766_dokument_an_bewerbung_verankert_die_stelle(setup_env):
    """Dritter Anker: die Anzeige liegt als PDF an der Bewerbung."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    from bewerbungs_assistent.services.stellen_anker import anker_status
    angelegt = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "Head of IT", "firma": "Speicherstadt Handel", "quelle": "stepstone"}))
    aid = db.add_application({"company": "Speicherstadt Handel", "title": "Head of IT",
                              "job_hash": angelegt["hash"]})
    assert anker_status(db, db.get_job(angelegt["hash"]))["hat_anker"] is False

    db.add_document({"filename": "anzeige.pdf", "doc_type": "stellenanzeige",
                     "linked_application_id": aid, "extracted_text": "Anzeige"})
    assert anker_status(db, db.get_job(angelegt["hash"]))["hat_anker"] is True
