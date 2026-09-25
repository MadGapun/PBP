"""Tests fuer #1039 (B48): defekte Quellen in der Auswahl und in der Liste.

Befund aus dem Melder-Bericht: eine angehakte Quelle, die spaeter als
defekt markiert wurde, blieb in der GESPEICHERTEN Auswahl. Das Dashboard
zeichnete ihren Haken leer und gesperrt, jeder Suchlauf uebersprang sie
erneut, und abwaehlen liess sie sich nicht. Hineingekommen war sie ueber
"Empfohlene Quellen": jeder der 15 Profiltypen empfahl mindestens eine
defekte Quelle, und weder der Knopf noch das Speichern prueften das.

Beim Nachbauen gefunden: der Knopf "N fehlende empfohlene Quellen
aktivieren" speicherte je Quelle einzeln, jedes Mal ausgehend von
derselben alten Auswahl — uebrig blieb nur die zuletzt aktivierte.
"""
import importlib
import os
import re
import shutil
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "bewerbungs_assistent"
FRONTEND = REPO / "frontend" / "src"


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17105_1039_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    instanz = _db_mod.Database()
    instanz.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(instanz.db_path), f"DB nicht isoliert: {instanz.db_path}"
    instanz.save_profile({"name": "Muster Tester"})
    yield instanz
    instanz.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    alt = dash._db
    dash._db = db
    yield TestClient(dash.app)
    dash._db = alt


def _defekte():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    return [k for k, v in SOURCE_REGISTRY.items() if v.get("defekt")]


def test_es_gibt_defekte_quellen_und_die_beispiele_sind_welche():
    """Vorbedingung: ohne defekte Quelle pruefte hier nichts etwas."""
    assert {"heise_jobs", "workday_dax", "meinestadt"} <= set(_defekte())


# ====================================================== gespeicherte Auswahl


def test_ohne_defekte_behaelt_die_reihenfolge():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    from bewerbungs_assistent.services.search_service import ohne_defekte
    assert ohne_defekte(["kimeta", "heise_jobs", "bundesagentur", "workday_dax"],
                        SOURCE_REGISTRY) == ["kimeta", "bundesagentur"]


def test_das_lesen_heilt_die_gespeicherte_auswahl(db):
    from bewerbungs_assistent.services.search_service import aktive_quellen
    db.set_profile_setting("active_sources", ["bundesagentur", "heise_jobs", "workday_dax"])
    assert aktive_quellen(db) == ["bundesagentur"]
    assert db.get_profile_setting("active_sources") == ["bundesagentur"], \
        "die Anzeige zu filtern reicht nicht — der SPEICHER muss es auch sagen"


def test_ohne_gespeicherte_auswahl_bleibt_es_bei_nichts(db):
    from bewerbungs_assistent.services.search_service import aktive_quellen
    assert aktive_quellen(db) is None
    assert db.get_profile_setting("active_sources", None) is None


def test_die_quellenliste_zeigt_und_speichert_dasselbe(client, db):
    db.set_profile_setting("active_sources", ["bundesagentur", "heise_jobs"])
    zeilen = {z["key"]: z for z in client.get("/api/sources").json()}
    assert zeilen["heise_jobs"]["active"] is False
    assert zeilen["bundesagentur"]["active"] is True
    assert db.get_profile_setting("active_sources") == ["bundesagentur"]


def test_das_speichern_nimmt_keine_defekte_quelle_an(client, db):
    antwort = client.post("/api/sources",
                          json={"active_sources": ["bundesagentur", "heise_jobs", "kimeta"]}).json()
    assert antwort["active_sources"] == ["bundesagentur", "kimeta"]
    assert antwort["abgelehnt_defekt"] == ["heise_jobs"]
    assert db.get_profile_setting("active_sources") == ["bundesagentur", "kimeta"]


def test_eine_auswahl_aus_lauter_defekten_ist_keine(db):
    """Der naechste Schritt im Dashboard muss "Quellen aktivieren" nennen —
    sonst steht dort nichts, und jeder Suchlauf ueberspringt alles."""
    db.set_profile_setting("active_sources", ["heise_jobs", "workday_dax"])
    aktionen = [s["aktion"] for s in db.get_next_steps()]
    assert "Jobquellen aktivieren" in aktionen


def test_die_automatik_startet_keine_suche_nur_mit_defekten(db):
    from bewerbungs_assistent.services import automatik_scheduler
    db.set_profile_setting("active_sources", ["heise_jobs", "workday_dax"])
    assert automatik_scheduler.run_jobsuche_now(db) == {"status": "keine_internen_quellen"}


def test_jeder_leseweg_geht_ueber_die_bereinigung():
    """Guard: ein neuer Leser, der die rohe Einstellung liest, braechte den
    Widerspruch zurueck. Erlaubt sind nur die Bereinigung selbst, die
    Leer-Pruefung vor der Erstuebernahme und der Rueckfall der
    Datenbank-Hilfe, falls der Import scheitert."""
    erlaubt = {
        ("search_service.py", 'gespeichert = db.get_profile_setting("active_sources", None)'),
        ("jobs.py", 'if not db.get_profile_setting("active_sources", []):'),
        ("database.py", 'active_sources = self.get_profile_setting("active_sources", [])'),
    }
    gefunden = set()
    for datei in SRC.rglob("*.py"):
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            if re.search(r'get_profile_setting\(\s*["\']active_sources', zeile):
                gefunden.add((datei.name, zeile.strip()))
    assert gefunden <= erlaubt, gefunden - erlaubt


def test_jeder_schreibweg_filtert():
    erlaubt = {
        ("search_service.py", 'db.set_profile_setting("active_sources", bereinigt)'),
        ("dashboard.py", '_db.set_profile_setting("active_sources", active)'),
        ("jobs.py", 'db.set_profile_setting("active_sources", _uebernahme)'),
    }
    gefunden = set()
    for datei in SRC.rglob("*.py"):
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            if re.search(r'set_profile_setting\(\s*["\']active_sources', zeile):
                gefunden.add((datei.name, zeile.strip()))
    assert gefunden <= erlaubt, gefunden - erlaubt
    post = (SRC / "dashboard.py").read_text(encoding="utf-8")
    block = post[post.index("async def api_set_sources"):post.index("@app.post(\"/api/sources/{source_key}/login\")")]
    assert "ohne_defekte(" in block
    # Erstuebernahme in jobsuche_starten (G17/#744): gefiltert wird VOR dem
    # Schreiben, nicht erst beim naechsten Lesen.
    assert "_uebernahme = ohne_defekte(quellen, _registry)" in (
        SRC / "tools" / "jobs.py").read_text(encoding="utf-8")


# ====================================================== Empfehlungen


def test_keine_empfehlung_nennt_eine_defekte_quelle():
    from bewerbungs_assistent.services import berufsfeld
    from bewerbungs_assistent.services import profile_classifier as pc
    defekt = set(_defekte())
    # #1070: gegangen wird jeder Weg ueber ein echtes Profil. Ein
    # Testdoppel auf `detect_profile_type` wuerde die Empfehlung
    # ueberspringen, die es zu pruefen gilt — sie entsteht seither aus
    # Feld, Form und Niveau.
    beispiele = {
        "gesundheit": "Pflegefachkraft Intensivstation",
        "bildung": "Erzieherin", "handwerk": "Geselle Schreiner",
        "produktion": "Produktionsmitarbeiter", "landwirtschaft": "Landwirt",
        "it": "Senior Softwareentwickler", "ingenieurwesen": "Konstrukteur",
        "wissenschaft": "Wissenschaftliche Mitarbeiterin",
        "logistik": "Lagerist", "sicherheit": "Sicherheitsmitarbeiter",
        "handel": "Verkaeuferin", "gastgewerbe": "Hotelfachfrau",
        "verwaltung": "Finanzbuchhalterin", "recht": "Rechtsanwalt",
        "medien": "Mediengestalterin", "dienstleistung": "Hausmeister",
    }
    assert set(beispiele) == set(berufsfeld.FELDER), "Ein Feld ohne Beispiel"
    for feld, titel in beispiele.items():
        erg = pc.recommend_sources({
            "positions": [{"title": titel, "start_date": "2015-01-01"}],
            "skills": [], "education": [],
        })
        assert erg["feld"] == feld, (titel, erg["feld"])
        assert not defekt & set(erg["recommended"]), (feld, erg["recommended"])
        assert erg["recommended"], f"{feld}: nach dem Filter bleibt keine Quelle"
        assert str(len(erg["recommended"])) in erg["rationale"]
    # Und die Gegenprobe: eine defekte Quelle wird BENANNT, nicht
    # verschwiegen (#1039). `meinestadt` steht in den Grundquellen.
    erg = pc.recommend_sources({
        "positions": [{"title": "Verkaeuferin", "start_date": "2015-01-01"}],
        "skills": [], "education": [],
    })
    assert set(erg["ausgelassen_defekt"]) == defekt & set(
        berufsfeld.FELD_QUELLEN["handel"])


def test_freelancer_bekommen_die_zwei_defekten_nicht_mehr_angeboten():
    """Der Meldefall: freelance.de und GULP kamen genau so in die Auswahl.
    GULP liefert seit v1.7.106 wieder, freelance.de seit v1.7.107 (B53) —
    beide werden deshalb empfohlen."""
    from bewerbungs_assistent.services import profile_classifier as pc
    # #1070: das Testdoppel auf `detect_profile_type` ist weg. Die
    # Empfehlung kommt nicht mehr aus dem Schluessel, sondern aus Feld,
    # Form und Niveau — ein Doppel, das nur `type` liefert, prueft
    # seither den Weg nicht mehr, den der Nutzer geht.
    erg = pc.recommend_sources({
        "positions": [{"title": "Freiberuflicher Berater",
                       "start_date": "2018-01-01"}],
        "skills": [], "education": [],
    })
    for quelle in ("freelance_de", "freelancermap", "gulp", "solcom",
                   "hays"):
        assert quelle in erg["recommended"], quelle
    assert erg["quellen_herkunft"]["form"], "Die Form bringt die Boersen"
    # Die ABSICHT: keine der fuenf Freelance-Boersen wird als defekt
    # ausgelassen. `ausgelassen_defekt` ist seit #1070 nicht mehr leer —
    # ohne erkennbares Fachfeld kommt der breite Grundstock dazu, und
    # der enthaelt eine defekte Quelle, die BENANNT wird (#1039).
    assert not set(erg["ausgelassen_defekt"]) & {
        "freelance_de", "freelancermap", "gulp", "solcom", "hays"}


# ====================================================== Frontend-Guards


def _quelle(name: str) -> str:
    return (FRONTEND / name).read_text(encoding="utf-8")


def test_das_erste_etikett_folgt_dem_haken():
    # v1.7.120 (#1059): die Etiketten entstehen in lib/quellenBadges. Die
    # Absicht dieses Tests gilt unveraendert — das ERSTE Etikett folgt dem
    # Haken, "Wartet auf dich" (#906) steht als Hinweis daneben —, sie wird
    # nur dort geprueft, wo die Regel jetzt wohnt. Reihenfolge und "kein
    # Text doppelt" prueft der Node-Test am Verhalten.
    src = _quelle("components/SourceSelectionList.jsx")
    assert "quellenBadges(source" in src
    lib = _quelle("lib/quellenBadges.js")
    assert 'q.active ? "Aktiv" : "Inaktiv"' in lib
    assert lib.index('q.active ? "Aktiv"') < lib.index('text: "Wartet auf dich"')


def test_die_liste_hat_filter_und_eine_eigene_ansicht_fuer_defekte():
    src = _quelle("components/SourceSelectionList.jsx")
    assert "Defekte Quellen ({anzahl.defekt})" in src
    assert "{label} ({anzahl[id]})" in src
    assert "localeCompare" in src, "die Sortierung bleibt A-Z"
    assert "filterbar" in _quelle("pages/SettingsPage.jsx")


def test_der_empfehlungsknopf_speichert_in_einem_schritt():
    src = _quelle("pages/SettingsPage.jsx")
    karte = src[src.index("function RecommendedSourcesCard"):src.index("function ScraperHealthCard")]
    # G70 (#1087): die Karte hat jetzt einen Haken je Quelle (ein Klick,
    # ein Speichervorgang). Der Knopf fuer ALLE fehlenden darf ihn nicht
    # in einer Schleife rufen.
    alle = karte[karte.index("async function activateAll()"):karte.index("return (", karte.index("async function activateAll()"))]
    assert "onToggle" not in alle, "je Quelle ein eigener Speichervorgang verliert alle bis auf eine"
    assert "onActivateMany(missing)" in karte
    assert "!sourceByKey.get(id).defekt" in karte
