"""#1390: Profil-Vokabular für den Abgleich - Stationen, Projekte, Abkürzungen."""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest

from bewerbungs_assistent.services.profil_begriffe import Profilbegriffe

PROFIL = {
    "skills": [{"name": "SAP PP"}, {"name": "Make-or-Buy-Analyse"}],
    "positions": [
        {"title": "Produktionsplaner", "tasks": "Kapazitätsplanung, Terminierung",
         "achievements": "Durchlaufzeit um 20 % gesenkt", "technologies": "SAP",
         "projects": [{"name": "SAP-PP-Feinplanung eingeführt",
                       "description": "Einführung der Feinplanung",
                       "result": "Rüstzeiten halbiert"}]},
        {"title": "Fertigungsplaner", "tasks": "Arbeitsvorbereitung und Arbeitspläne",
         "projects": []},
    ],
}


@pytest.fixture
def pb():
    return Profilbegriffe(PROFIL)


def test_begriff_nur_im_projekt(pb):
    assert pb.ist_belegt("feinplanung")


def test_begriff_nur_im_stationstitel(pb):
    assert pb.ist_belegt("fertigungsplaner")


def test_begriff_nur_in_den_aufgaben_mit_umlaut_und_umschrift(pb):
    assert pb.ist_belegt("kapazitätsplanung")
    assert pb.ist_belegt("kapazitaetsplanung")


def test_abkuerzung_in_anzeige_ausgeschrieben_im_profil(pb):
    assert pb.ist_belegt("av")          # Anzeige: AV, Profil: Arbeitsvorbereitung
    assert pb.ist_belegt("AV")


def test_ausgeschrieben_in_anzeige_abkuerzung_im_profil():
    p = Profilbegriffe({"skills": [{"name": "QS"}], "positions": []})
    assert p.ist_belegt("qualitätssicherung")
    assert p.ist_belegt("qualitaetssicherung")


def test_beugungsform_und_gegenrichtung(pb):
    assert pb.ist_belegt("arbeitspläne") or pb.ist_belegt("arbeitsplan")
    # Gegenrichtung: Profil-Kompetenz "SAP PP" steckt im Begriff der Anzeige
    assert pb.ist_belegt("sap pp einführung")


def test_wirklich_fehlendes_bleibt_fehlend(pb):
    assert not pb.ist_belegt("windchill")
    assert not pb.ist_belegt("zerspanung")


def test_wortgrenze_av_steckt_nicht_in_java_und_kein_stamm_zufall():
    p = Profilbegriffe({"skills": [{"name": "Java"}], "positions": []})
    assert not p.ist_belegt("av")
    assert not p.ist_belegt("jav")


def test_zwei_buchstaben_nur_wenn_auf_der_abkuerzungsliste(pb):
    assert not pb.ist_brauchbar("xy")
    assert pb.ist_brauchbar("av")


def test_leeres_profil_belegt_nichts():
    assert not Profilbegriffe(None).ist_belegt("feinplanung")
    assert not Profilbegriffe({}).ist_belegt("av")


# -- das Werkzeug ----------------------------------------------------------

@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_1390_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def test_skill_gap_analyse_meldet_vorhandenes_nicht_als_fehlend(umgebung):
    db, mcp = umgebung
    db.save_profile({"name": "Test Person"})
    db.add_skill({"name": "SAP PP", "category": "Fachlich", "level": 4})
    pid = db.add_position({"company": "Musterbetrieb GmbH", "title": "Fertigungsplaner",
                           "start_date": "2015-01", "tasks": "Arbeitsvorbereitung, Feinplanung"})
    db.add_project(pid, {"name": "SAP-PP-Feinplanung eingeführt",
                    "result": "Rüstzeiten halbiert"})
    db.save_jobs([{"hash": "g1390", "title": "Teamleiter Arbeitsvorbereitung (AV)",
                   "company": "Beispielwerk AG", "url": "https://example.com/g1390",
                   "source": "manuell", "score": 1,
                   "description": ("Aufgaben: Leitung der AV, Feinplanung der Fertigung, "
                                   "Terminierung in SAP PP, Zerspanung und Werkzeugbau. "
                                   "Wir erwarten Erfahrung mit SAP PP und Feinplanung. ") * 3}])
    voll = db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE '%g1390'").fetchone()["hash"]
    erg = _call(mcp, "skill_gap_analyse", {"job_hash": voll.split(":", 1)[-1]})
    fehlend = {g["skill"].lower() for g in erg["fehlende_skills"]}
    assert "feinplanung" not in fehlend, erg
    assert "av" not in fehlend, erg
