"""#1307: eigene Filter benannt speichern - als Ansicht (nur filtern) oder als Regel (neue Treffer aussortieren).

Geprueft: die EINE Filterfunktion (Bulk, Ansicht, Regel, Stellen-Tab) samt Regressionsvergleich mit der alten inneren
Funktion von `stellen_bulk_bewerten`; Anlegen, Anzeigen, Testen, Anwenden, An/Aus, Loeschen; nur erlaubte Gruende; die Regel
sortiert beim Anlegen nichts aus; Schutz (zurueckgeholt, gelesenes Urteil, Bewerbung); unbekannte Sprache wird nie
getroffen; die Regel laeuft nach jedem Suchlauf und nach der Browser-Uebernahme; Protokoll nennt die Regel; Profil-Trennung;
Loeschbereich; die Endpunkte des Dashboards antworten wie das Werkzeug.
"""
from __future__ import annotations

import ast
import asyncio
import importlib
import os
import random
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from bewerbungs_assistent.services import gespeicherte_filter as gf
from bewerbungs_assistent.services import stellen_filter as sf

SRC = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"

EN = ("We are looking for an engineer to join our team in Berlin. You will design and test components, work closely "
      "with colleagues from production, and support our customers. Requirements: a degree in engineering, at least "
      "three years of experience, and strong communication skills. We offer a competitive salary and a modern office.")
DE = ("Wir suchen für unseren Standort in Hamburg eine Ingenieurin oder einen Ingenieur. Deine Aufgaben: du "
      "konstruierst Bauteile, prüfst sie und arbeitest eng mit der Fertigung zusammen. Dein Profil: abgeschlossenes "
      "Studium, mehrere Jahre Erfahrung und gute Kenntnisse in CAD. Wir bieten ein Team, flexible Arbeitszeiten und "
      "Homeoffice.")


# ══ Umgebung ════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v182_1307_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def _stelle(db, kennung, titel, text, quelle="manuell", score=5, firma="Musterfirma GmbH"):
    db.save_jobs([{"hash": kennung, "title": titel, "company": firma, "url": f"https://example.com/{kennung}",
                   "source": quelle, "description": text, "score": score}])
    return kennung


def _bestand(db):
    _stelle(db, "f_en1", "Design Engineer", EN)
    _stelle(db, "f_en2", "Test Engineer", EN + " More text.")
    _stelle(db, "f_de1", "Konstrukteur", DE)
    _stelle(db, "f_kurz", "Engineer", "Short text.")     # Sprache unbekannt


def _aktiv(db):
    return {j["hash"] for j in db.get_active_jobs()}


def _englisch_regel(mcp, name="Englische Anzeigen", gruende=("sonstiges",)):
    return _call(mcp, "stellen_filter_verwalten", {"aktion": "anlegen", "art": "regel", "name": name,
                                                   "sprache": ["en"], "gruende": list(gruende)})


# ══ Eine Frage, eine Funktion ═══════════════════════════════════════════════════════════

def _alte_matches(job, now, max_score=None, min_alter_tage=None, max_alter_tage=None, firma="",
                  titel_enthaelt=None, titel_enthaelt_nicht=None, beschreibung_enthaelt_nicht=None):
    """Die innere Funktion `_matches` aus `stellen_bulk_bewerten` bis v1.8.1, woertlich (Referenz)."""
    firma_lc = (firma or "").lower().strip()
    title_must = [t.lower() for t in (titel_enthaelt or []) if t]
    title_must_not = [t.lower() for t in (titel_enthaelt_nicht or []) if t]
    desc_must_not = [t.lower() for t in (beschreibung_enthaelt_nicht or []) if t]
    score = int(job.get("score") or 0)
    if max_score is not None and score > max_score:
        return False
    found_at = job.get("found_at") or ""
    if min_alter_tage is not None or max_alter_tage is not None:
        if not found_at:
            return False
        try:
            found_dt = datetime.fromisoformat(found_at.replace("Z", "+00:00").split("+")[0])
        except (ValueError, TypeError):
            return False
        age_days = (now - found_dt).days
        if min_alter_tage is not None and age_days < min_alter_tage:
            return False
        if max_alter_tage is not None and age_days > max_alter_tage:
            return False
    if firma_lc and firma_lc not in (job.get("company") or "").lower():
        return False
    title_lc = (job.get("title") or "").lower()
    if title_must and not all(t in title_lc for t in title_must):
        return False
    if title_must_not and any(t in title_lc for t in title_must_not):
        return False
    if desc_must_not:
        desc_lc = (job.get("description") or "").lower()
        if any(t in desc_lc for t in desc_must_not):
            return False
    return True


def test_regression_dieselben_treffer_wie_die_alte_bulk_funktion():
    rnd = random.Random(1307)
    now = datetime(2026, 11, 7, 12, 0)
    woerter = ["Pflege", "Vertrieb", "Engineer", "Teamcenter", "Senior", "Werkstudent", "SAP"]
    jobs = []
    for i in range(400):
        jobs.append({
            "hash": f"r{i}", "score": rnd.choice([None, -3, 0, 1, 2.5, 4, 7, 12]),
            "found_at": rnd.choice(["", "kaputt", (now - timedelta(days=rnd.randint(0, 60))).isoformat(),
                                    (now - timedelta(days=rnd.randint(0, 60))).isoformat() + "Z"]),
            "company": rnd.choice(["Musterfirma GmbH", "Beispiel AG", "", None]),
            "title": " ".join(rnd.sample(woerter, 2)), "description": " ".join(rnd.sample(woerter, 3)),
        })
    faelle = 0
    for _ in range(300):
        args = {k: v for k, v in {
            "max_score": rnd.choice([None, 0, 3, 8]),
            "min_alter_tage": rnd.choice([None, 5]), "max_alter_tage": rnd.choice([None, 30]),
            "firma": rnd.choice(["", "muster", "Beispiel"]),
            "titel_enthaelt": rnd.choice([None, [], ["engineer"], ["Senior", "SAP"]]),
            "titel_enthaelt_nicht": rnd.choice([None, ["pflege"], ["Vertrieb", "Werkstudent"]]),
            "beschreibung_enthaelt_nicht": rnd.choice([None, ["teamcenter"], ["SAP", "Pflege"]]),
        }.items()}
        b = sf.bedingungen_lesen(args)
        alt = [j["hash"] for j in jobs if _alte_matches(j, now, **args)]
        neu = [j["hash"] for j in sf.filtern(jobs, b, jetzt=now)]
        assert neu == alt, args
        faelle += 1
    assert faelle == 300


def test_bulk_ansicht_regel_und_liste_rufen_dieselbe_funktion():
    baum = ast.parse((SRC / "tools" / "jobs.py").read_text(encoding="utf-8"))
    bulk = next(f for f in ast.walk(baum) if isinstance(f, ast.FunctionDef) and f.name == "stellen_bulk_bewerten")
    innere = [f.name for f in ast.walk(bulk) if isinstance(f, ast.FunctionDef) and f is not bulk]
    assert "_matches" not in innere, "die alte innere Filterfunktion ist zurueck"
    aufrufe = {getattr(c.func, "attr", "") for c in ast.walk(bulk) if isinstance(c, ast.Call)}
    assert {"bedingungen_lesen", "filtern"} <= aufrufe
    for datei in ("services/stellen_liste.py", "services/gespeicherte_filter.py"):
        text = (SRC / datei).read_text(encoding="utf-8")
        assert "_sf.passt(" in text or "_sf.filtern(" in text, datei


def test_unbekannte_bedingung_wird_benannt():
    with pytest.raises(sf.UngueltigeBedingung):
        sf.bedingungen_lesen({"titel_enthielt": ["x"]})
    with pytest.raises(sf.UngueltigeBedingung):
        sf.bedingungen_lesen({"sprache": ["englisch"]})
    with pytest.raises(sf.UngueltigeBedingung):
        sf.bedingungen_lesen({"min_score": "viel"})


def test_beschreibung_enthaelt_verlangt_alle_begriffe():
    job = {"title": "x", "description": "Teamcenter und SAP"}
    assert sf.passt(job, {"beschreibung_enthaelt": ["teamcenter", "sap"]})
    assert not sf.passt(job, {"beschreibung_enthaelt": ["teamcenter", "windchill"]})


def test_bulk_kennt_beschreibung_enthaelt(umgebung):
    db, mcp = umgebung
    _bestand(db)
    erg = _call(mcp, "stellen_bulk_bewerten", {"bewertung": "passt_nicht", "gruende": ["sonstiges"],
                                               "beschreibung_enthaelt": ["CAD"], "dry_run": True})
    assert erg["anzahl_treffer"] == 1 and erg["vorschau"][0]["hash"].startswith("f_de1")


def test_bulk_bisherige_aufrufe_unveraendert(umgebung):
    db, mcp = umgebung
    _bestand(db)
    _stelle(db, "f_pflege", "Pflegekraft", DE, score=0)
    erg = _call(mcp, "stellen_bulk_bewerten", {"bewertung": "passt_nicht", "gruende": ["falsches_fachgebiet"],
                                               "titel_enthaelt_nicht": ["engineer"], "dry_run": True})
    assert {v["hash"] for v in erg["vorschau"]} == {"f_de1", "f_pflege"}
    erg = _call(mcp, "stellen_bulk_bewerten", {"bewertung": "passt_nicht", "gruende": ["falsches_fachgebiet"],
                                               "min_score": 1, "quelle": "manu", "dry_run": True})
    assert erg["anzahl_treffer"] == 4, "min_score und quelle wirken wie bisher"
    erg = _call(mcp, "stellen_bulk_bewerten", {"bewertung": "passt_nicht", "gruende": ["falsches_fachgebiet"],
                                               "min_score": 0, "dry_run": True})
    assert erg["anzahl_treffer"] == 5, "min_score=0 begrenzt wie bisher nichts"


# ══ Anlegen, Anzeigen, Testen ═══════════════════════════════════════════════════════════

def test_ansicht_anlegen_und_in_stellen_anzeigen_nutzen(umgebung):
    db, mcp = umgebung
    _bestand(db)
    erg = _call(mcp, "stellen_filter_verwalten", {"aktion": "anlegen", "art": "ansicht", "name": "Nur Engineer",
                                                  "titel_enthaelt": ["engineer"]})
    assert erg["status"] == "angelegt" and erg["anzahl_treffer"] == 3
    assert "stellen_anzeigen(ansicht='Nur Engineer')" in erg["naechster_schritt"]
    liste = _call(mcp, "stellen_anzeigen", {"ansicht": "nur engineer", "ohne_schwelle": True})
    assert {s["hash"] for s in liste["stellen"]} == {"f_en1", "f_en2", "f_kurz"}
    assert liste["ansicht"]["name"] == "Nur Engineer"
    fehlt = _call(mcp, "stellen_anzeigen", {"ansicht": "Gibt es nicht"})
    assert "fehler" in fehlt and fehlt["vorhandene_ansichten"] == ["Nur Engineer"]
    alle = _call(mcp, "stellen_filter_verwalten", {})
    assert [a["name"] for a in alle["ansichten"]] == ["Nur Engineer"] and alle["regeln"] == []


def test_ohne_bedingung_und_doppelter_name_werden_abgelehnt(umgebung):
    db, mcp = umgebung
    leer = _call(mcp, "stellen_filter_verwalten", {"aktion": "anlegen", "art": "ansicht", "name": "Alles"})
    assert "fehler" in leer and "moegliche_bedingungen" in leer
    _call(mcp, "stellen_filter_verwalten", {"aktion": "anlegen", "art": "ansicht", "name": "A", "firma": "x"})
    doppelt = _call(mcp, "stellen_filter_verwalten", {"aktion": "anlegen", "art": "ansicht", "name": "a", "firma": "y"})
    assert "fehler" in doppelt
    falsche_art = _call(mcp, "stellen_filter_verwalten", {"aktion": "anlegen", "art": "liste", "name": "B", "firma": "x"})
    assert "fehler" in falsche_art


def test_regel_nur_mit_gruenden_aus_der_liste(umgebung):
    db, mcp = umgebung
    ohne = _call(mcp, "stellen_filter_verwalten", {"aktion": "anlegen", "art": "regel", "name": "R", "sprache": ["en"]})
    assert "fehler" in ohne and "sonstiges" in ohne["verfuegbare_gruende"]
    assert "ablehnungsgrund_anlegen" in ohne["naechster_schritt"]
    erfunden = _englisch_regel(mcp, gruende=["englisch"])
    assert "fehler" in erfunden and "englisch" in erfunden["fehler"]
    assert gf.alle(db) == [], "ein abgelehnter Grund legt nichts an"
    _call(mcp, "ablehnungsgrund_anlegen", {"label": "englischsprachig"})
    ok = _englisch_regel(mcp, gruende=["Englischsprachig"])
    assert ok["status"] == "angelegt" and ok["filter"]["gruende"] == ["englischsprachig"]


def test_regel_sortiert_beim_anlegen_nichts_aus(umgebung):
    db, mcp = umgebung
    _bestand(db)
    erg = _englisch_regel(mcp)
    assert erg["status"] == "angelegt" and erg["wuerde_aussortieren"] == 2
    assert erg["sprache_unbekannt"] == 1, "die Stelle ohne Text wird benannt, nicht getroffen"
    assert "aktion='anwenden'" in erg["naechster_schritt"]
    assert _aktiv(db) == {"f_en1", "f_en2", "f_de1", "f_kurz"}


def test_testen_schreibt_nichts(umgebung):
    db, mcp = umgebung
    _bestand(db)
    _englisch_regel(mcp)
    erg = _call(mcp, "stellen_filter_verwalten", {"aktion": "testen", "name": "Englische Anzeigen"})
    assert erg["status"] == "vorschau" and erg["wuerde_aussortieren"] == 2
    assert {b["sprache"] for b in erg["beispiele"]} == {"en"}
    assert len(_aktiv(db)) == 4


# ══ Anwenden, Schutz, Protokoll ═════════════════════════════════════════════════════════

def test_anwenden_erst_vorschau_dann_aussortieren_mit_regelname(umgebung):
    db, mcp = umgebung
    _bestand(db)
    _englisch_regel(mcp)
    vor = _call(mcp, "stellen_filter_verwalten", {"aktion": "anwenden", "name": "Englische Anzeigen"})
    assert vor["dry_run"] is True and len(_aktiv(db)) == 4
    echt = _call(mcp, "stellen_filter_verwalten", {"aktion": "anwenden", "name": "Englische Anzeigen",
                                                   "dry_run": False})
    assert echt["status"] == "angewendet" and echt["aussortiert"] == 2
    assert _aktiv(db) == {"f_de1", "f_kurz"}, "unbekannte Sprache bleibt stehen"
    protokoll = _call(mcp, "aussortier_protokoll", {"zeitfenster": "alle"})
    zeilen = {z["hash"]: z for z in protokoll["eintraege"]}
    assert zeilen["f_en1"]["herkunft"] == "automatik"
    assert "Regel „Englische Anzeigen“" in zeilen["f_en1"]["notiz"]
    assert echt["filter"]["treffer_gesamt"] == 2 and echt["filter"]["zuletzt_angewendet"]


def test_schutz_zurueckgeholt_urteil_und_bewerbung(umgebung):
    db, mcp = umgebung
    _bestand(db)
    _stelle(db, "f_en3", "Field Engineer", EN + " Travel.")
    db.dismiss_job("f_en1", "sonstiges")
    db.restore_job("f_en1")                                    # vom Menschen zurueckgeholt
    db.set_job_analysis("f_en2", "EMPFOHLEN", "passt", "detailanalyse")
    db.add_application({"title": "Field Engineer", "company": "Musterfirma GmbH", "job_hash": "f_en3",
                        "status": "beworben"})
    erg = _englisch_regel(mcp)
    assert erg["wuerde_aussortieren"] == 0 and erg["geschuetzt"] == 2 and erg["mit_bewerbung"] == 1
    echt = _call(mcp, "stellen_filter_verwalten", {"aktion": "anwenden", "name": "Englische Anzeigen",
                                                   "dry_run": False})
    assert echt["aussortiert"] == 0
    assert {"f_en1", "f_en2", "f_en3"} <= _aktiv(db)


def test_das_nadeloehr_haelt_auch_ohne_vorpruefung(umgebung):
    """Doppelter Boden: auch wenn die Vorpruefung fehlte, weist dismiss_job eine geschuetzte Stelle ab."""
    db, mcp = umgebung
    _bestand(db)
    db.dismiss_job("f_en1", "sonstiges")
    db.restore_job("f_en1")
    f = gf.anlegen(db, "R", "regel", {"sprache": ["en"]}, ["sonstiges"])
    assert gf._aussortieren(db, f, [db.get_job("f_en1")]) == 0
    assert "f_en1" in _aktiv(db)


def test_ansicht_sortiert_nie_aus(umgebung):
    db, mcp = umgebung
    _bestand(db)
    _call(mcp, "stellen_filter_verwalten", {"aktion": "anlegen", "art": "ansicht", "name": "V", "sprache": ["en"]})
    erg = _call(mcp, "stellen_filter_verwalten", {"aktion": "anwenden", "name": "V", "dry_run": False})
    assert "fehler" in erg and len(_aktiv(db)) == 4
    assert gf.nach_treffern(db, ["f_en1", "f_en2"]) is None


# ══ Neue Treffer: nach der Suche und nach der Uebernahme ════════════════════════════════

def _suchlauf(db, neue):
    job_id = db.create_background_job("jobsuche", {})
    db.update_background_job(job_id, "fertig", progress=100, message="ok", result={"neue_treffer": neue})
    return job_id


def test_regel_laeuft_nach_dem_suchlauf(umgebung):
    db, mcp = umgebung
    _englisch_regel(mcp)
    _bestand(db)
    job_id = _suchlauf(db, ["f_en1", "f_de1", "f_kurz"])
    erg = gf.nach_suche(db, job_id)
    assert erg["aussortiert"] == 1 and erg["je_regel"] == {"Englische Anzeigen": 1}
    assert _aktiv(db) == {"f_en2", "f_de1", "f_kurz"}, "nur NEUE Treffer, der Bestand bleibt"
    assert db.get_background_job(job_id)["result"]["eigene_regeln"]["aussortiert"] == 1


def test_eine_ruhende_regel_tut_nichts(umgebung):
    db, mcp = umgebung
    _englisch_regel(mcp)
    aus = _call(mcp, "stellen_filter_verwalten", {"aktion": "deaktivieren", "name": "Englische Anzeigen"})
    assert aus["filter"]["aktiv"] is False
    _bestand(db)
    assert gf.nach_suche(db, _suchlauf(db, ["f_en1", "f_en2"])) is None
    assert len(_aktiv(db)) == 4
    an = _call(mcp, "stellen_filter_verwalten", {"aktion": "aktivieren", "name": "Englische Anzeigen"})
    assert an["filter"]["aktiv"] is True
    ansicht = _call(mcp, "stellen_filter_verwalten", {"aktion": "anlegen", "art": "ansicht", "name": "V", "firma": "x"})
    assert ansicht["status"] == "angelegt"
    assert "fehler" in _call(mcp, "stellen_filter_verwalten", {"aktion": "deaktivieren", "name": "V"})


def _ruft_vor(datei: Path, funktion: str, erst: str, dann: str) -> bool:
    """Ruft `funktion` erst `<erst>.nach_suche` und danach `<dann>.nach_suche` (und den Text-Nachzug davor)?"""
    baum = ast.parse(datei.read_text(encoding="utf-8-sig"))
    f = next((x for x in ast.walk(baum) if isinstance(x, ast.FunctionDef) and x.name == funktion), None)
    if f is None:
        return False
    zeilen = {}
    for c in ast.walk(f):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "nach_suche":
            zeilen.setdefault(getattr(c.func.value, "id", ""), c.lineno)
    if erst not in zeilen or dann not in zeilen or zeilen[erst] > zeilen[dann]:
        return False
    return zeilen.get("text_nachzug", 0) < zeilen[erst]


def test_beide_suchwege_rufen_die_regeln_vor_der_lokalen_ki():
    assert _ruft_vor(SRC / "services" / "jobsuche_start.py", "_lauf", "gespeicherte_filter", "auto_aussortierung")
    assert _ruft_vor(SRC / "tools" / "jobs.py", "_maybe_auto_dismiss_after_search",
                     "gespeicherte_filter", "auto_aussortierung")


def test_der_suchlauf_merkt_seine_neuen_treffer():
    text = (SRC / "job_scraper" / "__init__.py").read_text(encoding="utf-8")
    assert 'result_data["neue_treffer"]' in text


def test_lauf_ruft_die_regeln_wirklich(umgebung, monkeypatch):
    """Der Thread-Lauf der Suche: nach run_search kommen die Regeln dran (ohne Netz, run_search ersetzt)."""
    db, mcp = umgebung
    _englisch_regel(mcp)
    _bestand(db)
    from bewerbungs_assistent import job_scraper
    from bewerbungs_assistent.services import jobsuche_start, text_nachzug, auto_aussortierung

    def _suche(db_, job_id, params):
        db_.update_background_job(job_id, "fertig", progress=100, message="ok",
                                  result={"neue_treffer": ["f_en1", "f_en2"]})
    monkeypatch.setattr(job_scraper, "run_search", _suche)
    monkeypatch.setattr(text_nachzug, "nach_suche", lambda *a, **k: None)
    monkeypatch.setattr(auto_aussortierung, "nach_suche", lambda *a, **k: None)
    job_id = db.create_background_job("jobsuche", {})
    jobsuche_start._lauf(db, job_id, {"herkunft": "claude"})
    assert _aktiv(db) == {"f_de1", "f_kurz"}


def test_regel_laeuft_nach_der_browser_uebernahme(umgebung):
    db, mcp = umgebung
    _englisch_regel(mcp)
    erg = _call(mcp, "browser_treffer_uebernehmen", {"quelle": "stepstone", "dry_run": False, "treffer": [
        {"titel": "Design Engineer", "firma": "Beispiel AG", "url": "https://example.com/stellen/1", "beschreibung": EN},
        {"titel": "Konstrukteur", "firma": "Musterfirma GmbH", "url": "https://example.com/stellen/2", "beschreibung": DE},
    ]})
    assert erg["trichter"]["angelegt"] == 2, erg
    assert erg["eigene_regeln"]["aussortiert"] == 1
    assert [j["title"] for j in db.get_active_jobs()] == ["Konstrukteur"]
    vorschau = _call(mcp, "browser_treffer_uebernehmen", {"quelle": "stepstone", "dry_run": True, "treffer": [
        {"titel": "Test Engineer", "firma": "Beispiel AG", "url": "https://example.com/stellen/3", "beschreibung": EN}]})
    assert "eigene_regeln" not in vorschau


def test_regel_laeuft_nach_der_linkedin_uebernahme():
    text = (SRC / "tools" / "jobs.py").read_text(encoding="utf-8")
    baum = ast.parse(text)
    for name in ("linkedin_treffer_uebernehmen", "browser_treffer_uebernehmen"):
        f = next(x for x in ast.walk(baum) if isinstance(x, ast.FunctionDef) and x.name == name)
        assert any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "_regeln_nach_uebernahme"
                   for c in ast.walk(f)), name


# ══ Loeschen, Profil, Loeschbereich ═════════════════════════════════════════════════════

def test_loeschen_erst_vorschau_aussortiertes_bleibt(umgebung):
    db, mcp = umgebung
    _bestand(db)
    _englisch_regel(mcp)
    _call(mcp, "stellen_filter_verwalten", {"aktion": "anwenden", "name": "Englische Anzeigen", "dry_run": False})
    vor = _call(mcp, "stellen_filter_verwalten", {"aktion": "loeschen", "name": "Englische Anzeigen"})
    assert vor["status"] == "vorschau" and len(gf.alle(db)) == 1
    weg = _call(mcp, "stellen_filter_verwalten", {"aktion": "loeschen", "name": "Englische Anzeigen", "dry_run": False})
    assert weg["status"] == "geloescht" and gf.alle(db) == []
    assert _aktiv(db) == {"f_de1", "f_kurz"}


def test_filter_gehoeren_zum_profil(umgebung):
    db, mcp = umgebung
    _englisch_regel(mcp)
    erstes = db.get_active_profile_id()
    db.switch_profile(db.create_profile("Zweites"))
    assert gf.alle(db) == []
    assert gf.holen(db, "Englische Anzeigen") is None
    _englisch_regel(mcp)                                       # gleicher Name im anderen Profil ist erlaubt
    db.switch_profile(erstes)
    assert len(gf.alle(db)) == 1


def test_tabelle_hat_einen_loeschbereich(umgebung):
    from bewerbungs_assistent.services import loeschbereiche
    db, _ = umgebung
    assert "stellen_filter" in loeschbereiche.BEREICHE["einstellungen"]
    assert "stellen_filter" not in loeschbereiche.unzugeordnet(db)


def test_werkzeug_ist_als_zweistufig_eingeordnet(umgebung):
    from bewerbungs_assistent.services import werkzeug_schutz, werkzeug_katalog
    assert werkzeug_schutz.ZWEISTUFIG["stellen_filter_verwalten"] == "dry_run"
    assert "stellen_filter_verwalten" in werkzeug_katalog.KURZ


# ══ Dashboard: dieselben Antworten ══════════════════════════════════════════════════════

def test_endpunkte_antworten_wie_das_werkzeug(umgebung):
    db, mcp = umgebung
    _bestand(db)
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    importlib.reload(dash)
    dash._db = db
    client = TestClient(dash.app)
    r = client.post("/api/stellen-filter", json={"name": "Englische Anzeigen", "art": "regel",
                                                 "bedingungen": {"sprache": ["en"]}, "gruende": ["erfunden"]})
    assert r.status_code == 400 and "verfuegbare_gruende" in r.json()
    r = client.post("/api/stellen-filter", json={"name": "Englische Anzeigen", "art": "regel",
                                                 "bedingungen": {"sprache": ["en"]}, "gruende": ["sonstiges"]})
    assert r.status_code == 200 and r.json()["wuerde_aussortieren"] == 2
    fid = r.json()["filter"]["id"]
    liste = client.get("/api/stellen-filter").json()
    assert liste == {**_call(mcp, "stellen_filter_verwalten", {}), "verfuegbare_gruende": liste["verfuegbare_gruende"]}
    assert client.post(f"/api/stellen-filter/{fid}/testen").json()["wuerde_aussortieren"] == 2
    assert client.post(f"/api/stellen-filter/{fid}/anwenden", json={}).json()["dry_run"] is True
    assert len(_aktiv(db)) == 4
    assert client.put(f"/api/stellen-filter/{fid}/aktiv", json={"aktiv": False}).json()["filter"]["aktiv"] is False
    assert client.post(f"/api/stellen-filter/{fid}/anwenden", json={"dry_run": False}).json()["aussortiert"] == 2
    # Stellen-Tab: Sprachfilter, Ansicht und das Merkmal an der Stelle
    _call(mcp, "stellen_filter_verwalten", {"aktion": "anlegen", "art": "ansicht", "name": "Kurz",
                                            "titel_enthaelt": ["engineer"]})
    tab = client.get("/api/jobs?active=true&limit=20&rahmen_ausblenden=false&schwelle_ausblenden=false"
                     "&sprache=de,unbekannt").json()
    assert {j["hash"]: j["sprache"] for j in tab["jobs"]} == {"f_de1": "de", "f_kurz": "unbekannt"}
    tab = client.get("/api/jobs?active=true&limit=20&rahmen_ausblenden=false&schwelle_ausblenden=false"
                     "&ansicht=Kurz").json()
    assert [j["hash"] for j in tab["jobs"]] == ["f_kurz"] and tab["verborgen"]["ansicht"] == 1
    assert client.get("/api/jobs?active=true&limit=20&ansicht=Fehlt").status_code == 400
    assert client.get("/api/jobs?active=true&limit=20&sprache=klingonisch").status_code == 400
    assert client.delete(f"/api/stellen-filter/{fid}").json()["status"] == "geloescht"
