"""#1200 A1-A4 — was ein Prompt erarbeitet, kommt in PBP an.

Zweiter Anwender-Review (14.10.2026): bei LinkedIn, „Bewerbung
erstellen“, Absagegrund und einzelnen Dokumenten blieb das Ergebnis im
Chat oder lief auf einem falschen Weg zurueck.

A1  LinkedIn-Anreicherung schrieb ueber `PUT /api/contacts/...` (kein
    Werkzeug) und legte 1,5 KB JavaScript in die Zwischenablage.
A2  Vier Anleitungen fuer „Bewerbung erstellen“ widersprachen sich
    (PDF statt DOCX, Export vor der Bewertung, „Score < 70“, Anlegen
    ohne Dublettenpruefung). Jetzt verweisen drei auf `bewerbung_schreiben`.
A3  Das Coaching speicherte den Absagegrund als Notiz; die Musteranalyse
    liest `rejection_reason`. Fuer eine schon abgelehnte Bewerbung gab
    es keinen Weg dorthin — `bewerbung_bearbeiten(ablehnungsgrund=)`.
A4  Der Einzel-Dokument-Prompt NANNTE die Folgewerkzeuge nur, und ein
    als „absage“ erkanntes Dokument bekam die Fallback-Vorlage.
"""
import asyncio
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_1200_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    _dash_mod._db = db
    yield db, _dash_mod, _srv_mod
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def _registry(db):
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    return _prompt_registry(db)


# ------------------------------------------------------------------ A1

def test_a1_linkedin_prompt_schreibt_ueber_kontakt_bearbeiten(env):
    db, dash, _ = env
    from fastapi.testclient import TestClient
    cid = db.add_contact({"full_name": "Erika Muster",
                          "linkedin_url": "https://www.linkedin.com/in/erika-muster"})
    r = TestClient(dash.app).post("/api/contacts/enrich-from-linkedin", json={"contact_id": cid})
    assert r.status_code == 200
    prompt = r.json()["prompt"]
    kid = f"CON-{cid[:8]}"
    assert f"kontakt_bearbeiten(kontakt_id='{kid}'" in prompt
    assert f"kontakt_anzeigen(kontakt_id='{kid}')" in prompt
    assert "/api/contacts" not in prompt, "REST-Pfad statt Werkzeug"
    assert "querySelector" not in prompt and "(() =>" not in prompt, "Code im Nutzertext"
    assert "full_name" not in prompt, "Feldname der Datenbank statt Werkzeugparameter"
    assert len(prompt) < 1500
    # Das Skript bleibt fuer Aufrufer, die es wollen, im eigenen Feld.
    assert "querySelector" in r.json()["extraction_js"]
    assert "umgeht" not in r.json()["hinweis"]


def test_a1_ohne_kontakt_legt_claude_an_statt_platzhalter(env):
    _, dash, _ = env
    from fastapi.testclient import TestClient
    r = TestClient(dash.app).post("/api/contacts/enrich-from-linkedin",
                                  json={"linkedin_url": "https://linkedin.com/in/neue-person"})
    prompt = r.json()["prompt"]
    assert "kontakt_anlegen(" in prompt
    assert "linkedin_url='https://linkedin.com/in/neue-person'" in prompt
    assert "<contact_id>" not in prompt


def test_a1_dialog_sagt_bei_neuem_kontakt_nicht_speichern():
    src = (ROOT / "frontend" / "src" / "pages" / "ContactsPage.jsx").read_text(encoding="utf-8")
    assert "Diesen Dialog dann ohne Speichern schließen" in src


# ------------------------------------------------------------------ A2

VERWEIS = "workflow_starten(name='bewerbung_schreiben')"


@pytest.mark.parametrize("name", ["bewerbung_vorbereitung", "auto_bewerbung", "jobsuche_workflow"])
def test_a2_bewerbung_erstellen_hat_eine_fassung(env, name):
    db = env[0]
    text = _registry(db)[name]()
    assert VERWEIS in text, f"{name} verweist nicht auf bewerbung_schreiben"
    for alt in ("PDF", "anschreiben_exportieren(", "lebenslauf_exportieren(",
                "lebenslauf_angepasst_exportieren(", "Score < 70", "Score: 78",
                "nicht unnötig fragen"):
        assert alt not in text, f"{name}: {alt!r} steht noch drin"


def test_a2_auto_bewerbung_legt_nicht_blind_an(env):
    text = _registry(env[0])["auto_bewerbung"]()
    assert "firma_kontext(" in text
    assert "bewerbung_erstellen(" not in text


def test_a2_vorbereitung_legt_keine_zweite_bewerbung_an(env):
    db = env[0]
    app_id = db.add_application({"title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                                 "status": "in_vorbereitung"})
    text = _registry(db)["bewerbung_vorbereitung"](bewerbung_id=app_id)
    assert "KEINE neue Bewerbung" in text
    assert "stelle_urteil_speichern(" in text
    assert "PRUEFEN" not in text and "aehnlich" not in text


def test_a2_die_eine_fassung_bleibt_docx_und_prueft_vorher(env):
    text = _registry(env[0])["bewerbung_schreiben"](stelle="X", firma="Y")
    assert "Immer DOCX" in text
    assert "Analyse VOR dem Export" in text
    assert 'stilarchiv_speichern(kind="cv", content=' in text


def test_a2_willkommen_verspricht_kein_pdf_fuer_bewerbungen(env):
    from bewerbungs_assistent.prompts import build_willkommen_prompt
    db = env[0]
    db.connect().execute("DELETE FROM profile")
    db.connect().commit()
    assert "PDF/DOCX" not in build_willkommen_prompt(db)


# ------------------------------------------------------------------ A3

def test_a3_coaching_schreibt_den_grund_ins_feld(env):
    text = _registry(env[0])["ablehnungs_coaching"]()
    assert "bewerbung_bearbeiten(bewerbung_id, ablehnungsgrund=" in text
    assert "Speichere mit bewerbung_notiz()" not in text


def _abgelehnt(db, srv):
    app_id = db.add_application({"title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                                 "status": "beworben", "applied_at": "2026-09-01"})
    erg = _call(srv.mcp, "bewerbung_status_aendern",
                {"bewerbung_id": app_id, "neuer_status": "abgelehnt"})
    assert erg.get("status") == "aktualisiert", erg
    return app_id


def _events(db, app_id):
    return db.connect().execute(
        "SELECT COUNT(*) FROM application_events WHERE application_id=? AND status='abgelehnt'",
        (app_id,)).fetchone()[0]


def test_a3_grund_nachtragen_landet_in_der_musteranalyse(env):
    db, _, srv = env
    app_id = _abgelehnt(db, srv)
    vorher = _events(db, app_id)
    erg = _call(srv.mcp, "bewerbung_bearbeiten",
                {"bewerbung_id": app_id, "ablehnungsgrund": "Andere Kandidatin mit SAP-Erfahrung"})
    assert erg.get("status") == "aktualisiert", erg
    assert "rejection_reason" in erg["geänderte_felder"]
    assert db.get_application(app_id)["rejection_reason"] == "Andere Kandidatin mit SAP-Erfahrung"
    assert _events(db, app_id) == vorher, "kein zweiter Absage-Eintrag im Verlauf"
    muster = db.get_rejection_patterns()
    assert "Kein Grund angegeben" not in muster["nach_grund"]
    assert sum(muster["nach_grund"].values()) == 1


def test_a3_grund_an_offener_bewerbung_wird_abgewiesen(env):
    db, _, srv = env
    app_id = db.add_application({"title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                                 "status": "beworben"})
    erg = _call(srv.mcp, "bewerbung_bearbeiten",
                {"bewerbung_id": app_id, "ablehnungsgrund": "x", "notes": "bleibt weg"})
    assert "fehler" in erg
    assert "bewerbung_status_aendern(" in erg["hinweis"]
    app = db.get_application(app_id)
    assert not app.get("rejection_reason")
    assert "bleibt weg" not in (app.get("notes") or ""), "nichts geschrieben, auch nichts anderes"


def test_a3_rueckfrage_nennt_den_weg_ins_feld(env):
    db, _, srv = env
    app_id = db.add_application({"title": "S", "company": "Musterbetrieb GmbH", "status": "beworben",
                                 "applied_at": "2026-09-01"})
    erg = _call(srv.mcp, "bewerbung_status_aendern",
                {"bewerbung_id": app_id, "neuer_status": "abgelehnt"})
    assert "bewerbung_bearbeiten(bewerbung_id, ablehnungsgrund=" in erg["rueckfrage_ablehnungsgrund"]
    assert "bewerbung_notiz()" not in erg["rueckfrage_ablehnungsgrund"]


# ------------------------------------------------------------------ A4

@pytest.mark.parametrize("doc_type, vorlage", [
    ("absage", "absage"),
    ("eingangsbestaetigung", "eingangsbestaetigung"),
    ("angebot", "vertrag"),
    ("interview_einladung", "gespraechsnotiz"),
    ("interview_bestaetigung", "gespraechsnotiz"),
    ("stellenbeschreibung", "stellenausschreibung"),
    ("vorbereitung", "gespraechsnotiz"),
    ("lebenslauf", "profil_aufbau"),
])
def test_a4_erkannter_typ_bekommt_seine_vorlage(doc_type, vorlage):
    from bewerbungs_assistent.document_analysis_prompts import select_template_key
    assert select_template_key({"doc_type": doc_type, "filename": "scan_0815.pdf"}) == vorlage


def test_a4_absage_wird_eingetragen_nicht_nur_genannt():
    from bewerbungs_assistent.document_analysis_prompts import build_prompt
    r = build_prompt({"id": "DOC-7", "filename": "scan.pdf", "doc_type": "absage",
                      "extracted_text": "leider", "app_company": "Musterbetrieb GmbH",
                      "app_title": "Einkauf"})
    p = r["prompt"]
    assert r["template"] == "absage"
    assert "bewerbung_status_aendern(bewerbung_id, 'abgelehnt', ablehnungsgrund=" in p
    assert 'dokument_status_setzen(dokument_id="DOC-7", status="angewendet")' in p
    assert "nenne die passenden" not in p


@pytest.mark.parametrize("vorlage", ["absage", "eingangsbestaetigung", "gespraechsnotiz",
                                     "vertrag", "stellenausschreibung", "fallback"])
def test_a4_jede_vorlage_schliesst_das_dokument_ab(vorlage):
    from bewerbungs_assistent.document_analysis_prompts import build_prompt
    for app in ({}, {"app_company": "Musterbetrieb GmbH"}):
        p = build_prompt({"id": "DOC-1", "filename": "x.pdf", "extracted_text": "x", **app},
                         vorlage)["prompt"]
        assert "dokument_status_setzen(" in p
        assert "Liefere das Ergebnis als strukturierte Zusammenfassung" not in p
    ohne = build_prompt({"id": "DOC-1", "filename": "x.pdf", "extracted_text": "x"}, vorlage)["prompt"]
    assert "dokument_verknuepfen(" in ohne, "ohne Bewerbung: zuordnen und verknuepfen"


def test_a4_profil_dokumente_bleiben_beim_extraktionsweg():
    from bewerbungs_assistent.document_analysis_prompts import build_prompt
    p = build_prompt({"id": "DOC-1", "filename": "cv.pdf", "doc_type": "lebenslauf",
                      "extracted_text": "x"})["prompt"]
    assert "extraktion_anwenden(" in p
    assert "bewerbung_status_aendern(" not in p


# ------------------------------------------------------------------ B1

@pytest.mark.parametrize("seite", ["JobsPage.jsx", "DashboardPage.jsx"])
def test_b1_beide_seiten_rechnen_die_gehaltskacheln_gleich(seite):
    """Die Rechnung selbst prueft `gehaltsKennzahl.test.mjs`; hier, dass
    beide Seiten sie nutzen statt einer eigenen Kopie (G61 reparierte nur
    das Dashboard, die Stellen-Seite zeigte weiter "0 EUR")."""
    src = (ROOT / "frontend" / "src" / "pages" / seite).read_text(encoding="utf-8-sig")
    assert "gehaltsKacheln(salaryMetrics" in src
    for feld in ("averageMin", "averageMax", "bandMin", "bandMax"):
        assert f"Number(salaryMetrics.{feld})" not in src, feld
    assert "salaryBandText" not in src
