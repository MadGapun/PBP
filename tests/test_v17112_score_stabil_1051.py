"""Tests fuer #1051 — ein Urteil gilt nicht im Moment seiner Entstehung als veraltet.

Nutzerbericht vom 15.09.2026: eine heute angelegte Stelle trug in zehn
Minuten vier Score-Werte (gespeichert 0, `fit_analyse` 3.5, "in der
Liste" 13.5, `stellen_anzeigen` 10), und eine eben gespeicherte
Detailanalyse erschien sofort mit `veraltet: true`.

Zwei Ursachen, beide hier festgehalten:

1. Die manuelle Anlage (auch der LinkedIn-Sammelweg) und
   `stelle_bearbeiten` rechneten mit den ROHEN Suchkriterien. Ohne die
   abgeleitete Betriebsart des MUSS-Tors (#968) ergab eine Stelle ohne
   Pflichttreffer 0, die Fit-Analyse ueber das Nadeloehr 3.5.
2. Die Veraltet-Pruefung verglich den roh gespeicherten Score mit dem
   Listen-Score MIT den Scoring-Reglern — zwei Rechenwege. Seit v1.7.112
   haengt "ueberholt" an Profil, Anzeigentext und Suchkriterien.
"""
import ast
import asyncio
import importlib
import logging
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import muss_tor, passung  # noqa: E402

# Der Pflichtbegriff steht bewusst NICHT im Text: gemeldet war eine
# Stelle ohne Pflichttreffer. "Hamburg" als PLUS-Begriff und remote
# bringen Rahmenpunkte — ohne sie ergaeben beide Wege 0, und der Test
# unterschiede sie nicht.
TEXT = ("Die Musterfirma Nord sucht fuer den Standort Hamburg eine "
        "Verstaerkung im Bereich Datenpflege. Sie arbeiten mit Fachbereichen "
        "zusammen und begleiten Einfuehrungen. ") * 8


@pytest.fixture
def umgebung(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    db = database.Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.switch_profile(db.create_profile("Muster"))
    db.set_search_criteria("keywords_muss", ["Stoffstrombilanzierung"])
    db.set_search_criteria("keywords_plus", ["Hamburg"])
    muss_tor.modus_setzen(db, muss_tor.GEWICHTET)

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP Test 1051")
    register_all(mcp, db, logging.getLogger("test.1051"))

    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    from fastapi.testclient import TestClient
    try:
        yield db, mcp, TestClient(dash.app)
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(_run())


def _anlegen(mcp, kennung="a", remote="remote"):
    erg = _call(mcp, "stelle_manuell_anlegen", {
        "titel": f"Sachbearbeitung Datenpflege {kennung}",
        "firma": "Musterfirma Nord",
        "url": f"https://example.com/1051/{kennung}",
        "beschreibung": TEXT, "remote": remote})
    assert erg.get("status") == "angelegt", erg
    return erg["hash"]


# ------------------------------------------ Ursache 1: dieselbe Rechnung


def test_die_anlage_speichert_denselben_score_wie_die_fit_analyse(umgebung):
    db, mcp, _ = umgebung
    h = _anlegen(mcp)
    gespeichert = db.get_job(h)["score"]
    fit = _call(mcp, "fit_analyse", {"job_hash": h})
    assert gespeichert > 0, (
        "Der Fall unterscheidet die Wege nicht — ohne Rahmenpunkte ist "
        "auch der rohe Weg 0.")
    assert gespeichert == pytest.approx(fit["total_score"])
    assert "score_abweichung" not in fit, fit.get("score_abweichung")


def test_der_linkedin_sammelweg_speichert_denselben_score(umgebung):
    db, mcp, _ = umgebung
    erg = _call(mcp, "linkedin_treffer_uebernehmen", {
        "treffer": [{"job_id": "105101", "titel": "Datenpflege Fachbereich",
                     "firma": "Musterfirma Nord", "beschreibung": TEXT}],
        "dry_run": False})
    assert erg["trichter"]["angelegt"] == 1, erg["trichter"]
    h = erg["angelegt"][0]["hash"]
    fit = _call(mcp, "fit_analyse", {"job_hash": h})
    assert db.get_job(h)["score"] == pytest.approx(fit["total_score"])
    assert "score_abweichung" not in fit


def test_stelle_bearbeiten_rechnet_ueber_das_nadeloehr(umgebung):
    db, mcp, _ = umgebung
    h = _anlegen(mcp, "bearb")
    neu = TEXT + " Erfahrung mit Hamburg-weiten Projekten ist erwuenscht."
    _call(mcp, "stelle_bearbeiten", {"job_hash": h, "beschreibung": neu})
    fit = _call(mcp, "fit_analyse", {"job_hash": h})
    assert db.get_job(h)["score"] == pytest.approx(fit["total_score"])
    assert "score_abweichung" not in fit


_FUNKTIONEN = (ast.FunctionDef, ast.AsyncFunctionDef)


def _eigene_zuweisungen(funktion, name):
    """Zuweisungen an `name` im Rumpf dieser Funktion — ohne die
    Rumpfe verschachtelter Funktionen."""
    treffer, offen = [], list(ast.iter_child_nodes(funktion))
    while offen:
        knoten = offen.pop()
        if isinstance(knoten, _FUNKTIONEN + (ast.Lambda,)):
            continue
        if (isinstance(knoten, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name
                        for t in knoten.targets)):
            treffer.append(knoten)
        offen.extend(ast.iter_child_nodes(knoten))
    return treffer


def _nadeloehr_ok(knoten, eltern) -> bool:
    """Kommen die Kriterien dieses Aufrufs aus `fuer_scoring`?

    Massgeblich ist die INNERSTE Funktion, die den Namen bindet. Die
    erste Fassung durchsuchte jede umgebende Funktion ganz — und fand
    fuer `_stelle_uebernehmen` die Zuweisung eines ANDEREN Werkzeugs in
    `register`. Die Gegenprobe mit rohen Kriterien blieb dadurch stumm.
    """
    arg = knoten.args[1] if len(knoten.args) > 1 else None
    if arg is None:
        return False
    if not isinstance(arg, ast.Name):
        return "fuer_scoring" in ast.unparse(arg)
    umgebend = eltern.get(knoten)
    while umgebend is not None:
        if isinstance(umgebend, _FUNKTIONEN):
            if arg.id in {a.arg for a in umgebend.args.args}:
                return True
            eigene = _eigene_zuweisungen(umgebend, arg.id)
            if eigene:
                return all("fuer_scoring" in ast.unparse(z.value)
                           for z in eigene)
        umgebend = eltern.get(umgebend)
    return False


def test_jeder_score_schreiber_nimmt_das_nadeloehr():
    """Kein `calculate_score` mit selbst geholten Kriterien.

    Der Guard aus #987 pruefte, dass niemand die Anreicherung NACHBAUT —
    nicht, dass jeder Aufrufer sie ueberhaupt bekommt. Die manuelle Anlage
    stand damit neun Versionen lang mit rohen Kriterien da, waehrend der
    Docstring von `fuer_scoring` sie als Aufrufer nannte.
    """
    wurzel = _repo() / "src" / "bewerbungs_assistent"
    verstoesse = []
    for datei in wurzel.rglob("*.py"):
        baum = ast.parse(datei.read_text(encoding="utf-8-sig"))
        eltern = {kind: knoten for knoten in ast.walk(baum)
                  for kind in ast.iter_child_nodes(knoten)}
        for knoten in ast.walk(baum):
            if (isinstance(knoten, ast.Call)
                    and getattr(knoten.func, "id", None) == "calculate_score"
                    and not _nadeloehr_ok(knoten, eltern)):
                verstoesse.append(f"{datei.name}:{knoten.lineno}")
    assert not verstoesse, (
        "calculate_score mit Kriterien, die nicht aus fuer_scoring stammen: "
        + ", ".join(verstoesse))


# ------------------------------------ Ursache 2: veraltet ohne Anlass


def _mit_regler(db):
    # Der gemeldete Fall: ein Remote-Regler von +10 hebt die Liste.
    db.set_scoring_config("remote", "remote", 10)


def test_ein_urteil_ist_mit_reglern_nicht_sofort_veraltet(umgebung):
    db, mcp, tc = umgebung
    _mit_regler(db)
    h = _anlegen(mcp, "urteil")
    assert db.set_job_analysis(h, "BEDINGT", "gelesen") is True

    liste = tc.get("/api/jobs?limit=50").json().get("jobs", [])
    zeile = next(j for j in liste if j["hash"] == db.get_job(h)["hash"])
    assert zeile["score"] > db.get_job(h)["score"], (
        "Der Regler greift nicht — dann prueft der Test den Fall nicht.")
    assert zeile["analyse"].get("veraltet") is None, zeile["analyse"]
    assert "ueberholt" not in zeile["pruefstand"]

    stellen = _call(mcp, "stellen_anzeigen", {}).get("stellen", [])
    eintrag = next(e for e in stellen if "Datenpflege urteil" in e["titel"])
    assert eintrag["analyse"].get("veraltet") is None, eintrag["analyse"]

    fit = _call(mcp, "fit_analyse", {"job_hash": h})
    assert fit["gespeicherte_analyse"].get("veraltet") is None
    assert not fit["empfehlung"].get("veraltet")


def test_eine_sichtung_ist_mit_reglern_nicht_sofort_ueberholt(umgebung):
    db, mcp, tc = umgebung
    _mit_regler(db)
    h = _anlegen(mcp, "sicht")
    db.mark_job_sighted(h)
    liste = tc.get("/api/jobs?limit=50").json().get("jobs", [])
    zeile = next(j for j in liste if j["hash"] == db.get_job(h)["hash"])
    assert zeile["pruefstand"]["art"] == passung.GESICHTET
    assert "ueberholt" not in zeile["pruefstand"]


def test_neu_gegliederter_text_macht_nichts_ueberholt(umgebung):
    """v1.7.110 hat Texte neu gegliedert, ohne ein Wort zu aendern."""
    db, mcp, _ = umgebung
    h = _anlegen(mcp, "format")
    db.set_job_analysis(h, "EMPFOHLEN", "passt")
    db.update_job(h, {"description": TEXT.replace(". ", ".\n\n")})
    job = db.get_job(h)
    assert passung.zustand(job, db.get_profile(),
                           db.get_search_criteria()).get("ueberholt") is None


def test_geaenderte_suchkriterien_machen_ueberholt(umgebung):
    db, mcp, _ = umgebung
    h = _anlegen(mcp, "krit")
    db.set_job_analysis(h, "EMPFOHLEN", "passt")
    db.set_search_criteria("keywords_plus", ["Hamburg", "Bremen"])
    alt = passung.zustand(db.get_job(h), db.get_profile(),
                          db.get_search_criteria())["ueberholt"]
    assert alt["grund"] == "kriterien"
    assert alt["gruende_text"] == [passung.GRUND_TEXT["kriterien"]]


def test_geaenderte_kriterien_kommen_auf_allen_vier_wegen_an(umgebung):
    """Liste (REST und MCP), Fit-Analyse und Fit-Dialog nennen den Grund.

    Jeder Weg muss die Kriterien selbst hereinreichen — ohne sie wird
    diese Grundlage still nicht verglichen.
    """
    db, mcp, tc = umgebung
    h = _anlegen(mcp, "wege")
    db.set_job_analysis(h, "EMPFOHLEN", "passt")
    db.set_search_criteria("keywords_plus", ["Hamburg", "Bremen"])
    gespeichert_hash = db.get_job(h)["hash"]

    liste = tc.get("/api/jobs?limit=50").json().get("jobs", [])
    zeile = next(j for j in liste if j["hash"] == gespeichert_hash)
    assert zeile["analyse"]["veraltet_grund"] == "kriterien"
    assert zeile["pruefstand"]["ueberholt"]["grund"] == "kriterien"

    stellen = _call(mcp, "stellen_anzeigen", {}).get("stellen", [])
    eintrag = next(e for e in stellen if "Datenpflege wege" in e["titel"])
    assert eintrag["analyse"]["veraltet_grund"] == "kriterien"
    assert eintrag["pruefstand"]["ueberholt"]["grund"] == "kriterien"

    fit = _call(mcp, "fit_analyse", {"job_hash": h})
    assert fit["gespeicherte_analyse"]["veraltet_grund"] == "kriterien"
    # Die Empfehlung selbst nimmt hier den k.o.-Zweig (kein Pflichttreffer
    # schlaegt ein Urteil, #671) — der Grund steht deshalb am Befund.
    assert fit["gespeicherte_analyse"]["veraltet_text"] == [
        passung.GRUND_TEXT["kriterien"]]

    dialog = tc.get(f"/api/jobs/{gespeichert_hash}/fit-analyse").json()
    assert dialog["analyse"]["veraltet_grund"] == "kriterien"
    assert dialog["pruefstand"]["ueberholt"]["grund"] == "kriterien"


def test_ein_weggebrochener_text_macht_nichts_ueberholt(umgebung):
    """Das Urteil hat gelesen, was damals dastand (Snapshot, C23)."""
    db, mcp, _ = umgebung
    h = _anlegen(mcp, "leer")
    db.set_job_analysis(h, "BEDINGT", "gelesen")
    db.update_job(h, {"description": ""})
    assert passung.zustand(db.get_job(h), db.get_profile(),
                           db.get_search_criteria()).get("ueberholt") is None


def test_ein_nennwert_fuers_gespraech_macht_nichts_ueberholt(umgebung):
    """#931: der Wunschwert geht in keine Pruefung ein."""
    db, mcp, _ = umgebung
    h = _anlegen(mcp, "nenn")
    db.set_job_analysis(h, "EMPFOHLEN", "passt")
    db.set_search_criteria("wunsch_gehalt", 90000)
    assert passung.zustand(db.get_job(h), db.get_profile(),
                           db.get_search_criteria()).get("ueberholt") is None


def test_laufzeit_eintraege_zaehlen_nicht_zu_den_kriterien():
    """Die beworbenen Titel aendern sich mit jeder Bewerbung."""
    assert (passung.kriterien_stand({"keywords_plus": ["a"]})
            == passung.kriterien_stand({"keywords_plus": ["a"],
                                        "_applied_titles": ["x"]}))


def test_ein_urteil_von_vor_v17112_wird_nur_am_profil_gemessen():
    profil = {"skills": [{"name": "a"}], "positions": [],
              "updated_at": "2026-09-01T10:00:00"}
    job = {"analyse_urteil": "BEDINGT", "analyse_score": 0.0, "score": 10.0,
           "analyse_profil_stand": passung.profil_stand(profil),
           "description": "irgendein Text"}
    assert passung.ueberholt(job, profil, {"keywords_plus": ["b"]}) is None
    anders = dict(profil, updated_at="2026-09-15T10:00:00")
    assert passung.ueberholt(job, anders)["grund"] == "profil"


def test_der_stand_ueberlebt_einen_erneuten_suchlauf(umgebung):
    db, mcp, _ = umgebung
    h = _anlegen(mcp, "lauf")
    db.set_job_analysis(h, "BEDINGT", "gelesen")
    db.mark_job_sighted(h)
    job = db.get_job(h)
    stand, sicht = job["analyse_stand"], job["gesichtet_stand"]
    assert stand and sicht
    db.save_jobs([dict(job, _manual_entry=True)])
    nach = db.get_job(h)
    assert nach["analyse_stand"] == stand
    assert nach["gesichtet_stand"] == sicht


def test_loeschen_des_befunds_leert_den_stand(umgebung):
    db, mcp, _ = umgebung
    h = _anlegen(mcp, "weg")
    db.set_job_analysis(h, "BEDINGT", "gelesen")
    assert db.clear_job_analysis(h) is True
    assert not db.get_job(h).get("analyse_stand")


def test_der_hinweis_nennt_den_tatsaechlichen_grund():
    verdikt = passung.urteil(profil_kompetenzen=3, gespeicherte_analyse={
        "urteil": "BEDINGT", "veraltet": True,
        "veraltet_text": [passung.GRUND_TEXT["anzeigentext"]]})
    assert "Anzeigentext" in verdikt["hinweis"]
    assert "Profil" not in verdikt["hinweis"]


def test_eine_sichtung_wird_an_ihrer_grundlage_gemessen(umgebung):
    """Nicht nur das Urteil — auch die Sichtung traegt ihren Stand."""
    db, mcp, _ = umgebung
    h = _anlegen(mcp, "sichtneu")
    db.mark_job_sighted(h)
    db.update_job(h, {"description": TEXT + " Neuer Absatz mit Inhalt."})
    alt = passung.zustand(db.get_job(h), db.get_profile(),
                          db.get_search_criteria())["ueberholt"]
    assert alt["grund"] == "anzeigentext"


def test_die_oberflaeche_liest_die_gruende_vom_server():
    """Abzeichen UND Fit-Dialog — je ein eigener Ausdruck, nicht gezaehlt."""
    seite = (_repo() / "frontend" / "src" / "pages"
             / "JobsPage.jsx").read_text(encoding="utf-8")
    assert "score_jetzt" not in seite
    assert "teile.push(...alt.gruende_text)" in seite, "Abzeichen"
    assert 'ueberholt.gruende_text.join("; ")' in seite, "Fit-Dialog"
