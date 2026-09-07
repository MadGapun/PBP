"""Tests fuer v1.7.38 — #991: 962 Zuordnungsvorschlaege statt 8.

Befund vom 07.09.2026: `analyse_plan_erstellen` lieferte im Block
`bewerbungs_zuordnungen` **962 Vorschlaege**. Einer einzigen
abgeschlossenen Bewerbung wurden rund dreissig Dokumente angeboten,
darunter Lebenslaeufe, die erkennbar fuer acht andere Firmen erstellt
worden waren. Dieselben Dokumente tauchten zusaetzlich bei weiteren
Bewerbungen auf.

`dokumente_ohne_bewerbung` (#797) lieferte fuer denselben Bestand **8
Faelle** — jeden mit Verdachtsmoment, Konfidenz und Beleg, und ohne
Vorschlag, wo kein Ziel erkennbar war.

**Zum fuenften Mal dasselbe Muster** (#963 fit_analyse/calculate_score,
#913 dismiss_job, #976 aufgaben_uebersicht, #987 Score-Kriterien): zwei
Wege beantworten dieselbe Frage, und der schwaechere ist ausgerechnet
der, den die Anleitung ZUERST empfiehlt.

Die Ursache im Detail: der Plan suchte den Firmennamen im VOLLTEXT jedes
Dokuments. Ein Firmenname im Fliesstext ist aber kein Verdachtsmoment —
er steht in jeder Absage, jeder Signatur und in jedem Anschreiben, das
die Firma nur adressiert.

**Nicht mitentsorgt wurde der Gruendungsfall von #686:** eine Mail, deren
Dateiname nichts sagt (`Mail_2026-06-08.eml`), deren Text aber die Firma
nennt. Der Volltext bleibt ein Signal — aber nur fuer Korrespondenz-
Typen und nur, wenn er GENAU EINE Firma aus dem Bestand nennt.
"""
import asyncio
import importlib
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1738_991_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    datenbank = _db_mod.Database()
    datenbank.initialize()
    assert str(tmpdir) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    datenbank.save_profile({"name": "Test Person"})
    yield datenbank
    datenbank.close()
    os.environ.pop("BA_DATA_DIR", None)
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _plan(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import dokumente
    mcp = FastMCP("test")
    dokumente.register(mcp, db, logging.getLogger("test"))
    return _call(mcp, "analyse_plan_erstellen", {})


def _dok(db, **felder):
    basis = {"filepath": "/fake/" + felder.get("filename", "x"),
             "doc_type": "email", "extracted_text": ""}
    basis.update(felder)
    return db.add_document(basis)


# ── Der gemeldete Fall ────────────────────────────────────────────────

def test_991_lebenslauf_fuer_fremde_firma_wird_nicht_vorgeschlagen(db):
    """Die Akzeptanzkriterium-Zeile des Issues, woertlich.

    Ein Lebenslauf, der fuer Firma A geschrieben wurde, nennt Firma A im
    Text. Das machte ihn zum Vorschlag fuer die Bewerbung bei A —
    obwohl er kein Schriftwechsel dieses Vorgangs ist, sondern ein
    Dokument, das der Nutzer selbst erstellt hat.
    """
    db.add_application({"title": "Consultant", "company": "Musterfirma GmbH"})
    _dok(db, id="cv-001", filename="Lebenslauf_2026.pdf", doc_type="lebenslauf",
         extracted_text="Angepasster Lebenslauf fuer die Musterfirma GmbH.")
    z = _plan(db)["bewerbungs_zuordnungen"]
    assert not [e for e in z if e["dateiname"] == "Lebenslauf_2026.pdf"], z


def test_991_anschreiben_wird_nicht_vorgeschlagen(db):
    db.add_application({"title": "Consultant", "company": "Musterfirma GmbH"})
    _dok(db, id="ans-001", filename="Anschreiben.docx", doc_type="anschreiben",
         extracted_text="Sehr geehrte Damen und Herren der Musterfirma GmbH,")
    z = _plan(db)["bewerbungs_zuordnungen"]
    assert not [e for e in z if e["dateiname"] == "Anschreiben.docx"], z


def test_991_mehrdeutiger_text_ergibt_keinen_vorschlag(db):
    """Nennt der Text zwei Firmen aus dem Bestand, ist nichts erkennbar.

    Genau daher kam die Beobachtung des Melders, dieselben Dokumente
    tauchten bei mehreren Bewerbungen auf: jede passende Firma bekam
    denselben Beleg.
    """
    db.add_application({"title": "A", "company": "Musterfirma GmbH"})
    db.add_application({"title": "B", "company": "Beispieltech SE"})
    _dok(db, id="mail-amb", filename="Newsletter.eml", doc_type="email",
         extracted_text="Stellen bei Musterfirma GmbH und Beispieltech SE.")
    z = _plan(db)["bewerbungs_zuordnungen"]
    assert not [e for e in z if e["dateiname"] == "Newsletter.eml"], z


def test_991_gruendungsfall_686_funktioniert_weiter(db):
    """Eine Mail ohne sprechenden Dateinamen, Firma nur im Text.

    Das war der Anlass fuer #686. Die Haertung darf ihn nicht mitnehmen.
    """
    db.add_application({"title": "Lead Consultant", "company": "Beispieltech SE"})
    _dok(db, id="mail-686", filename="Mail_2026-06-08.eml", doc_type="email",
         extracted_text="Beispieltech SE freut sich, Sie kennenzulernen.")
    z = _plan(db)["bewerbungs_zuordnungen"]
    treffer = [e for e in z if e["dateiname"] == "Mail_2026-06-08.eml"]
    assert treffer, z
    assert treffer[0]["firma"] == "Beispieltech SE"


# ── AK: Verdachtsmoment, Konfidenz, Beleg ────────────────────────────

def test_991_jeder_vorschlag_traegt_konfidenz_beleg_und_verdacht(db):
    db.add_application({"title": "Consultant", "company": "Musterfirma GmbH"})
    _dok(db, id="m1", filename="Musterfirma_Antwort.eml", doc_type="bewerbungsantwort",
         extracted_text="Vielen Dank fuer Ihre Bewerbung.")
    z = _plan(db)["bewerbungs_zuordnungen"]
    assert z
    for e in z:
        assert e.get("konfidenz") in ("hoch", "mittel", "niedrig"), e
        assert e.get("beleg"), e
        assert e.get("verdacht"), e
        assert e.get("bewerbung_id"), e


def test_991_ohne_erkennbares_ziel_kein_eintrag(db):
    """Ein loses Dokument ohne jeden Bezug taucht nicht als Vorschlag auf."""
    db.add_application({"title": "Consultant", "company": "Musterfirma GmbH"})
    _dok(db, id="egal", filename="Urlaubsfoto.pdf", doc_type="sonstiges",
         extracted_text="Nichts mit Bewerbungen zu tun.")
    z = _plan(db)["bewerbungs_zuordnungen"]
    assert not [e for e in z if e["dateiname"] == "Urlaubsfoto.pdf"], z


# ── AK: Obergrenze ───────────────────────────────────────────────────

def test_991_anzahl_ist_begrenzt_und_die_gesamtzahl_steht_dabei(db):
    """962 Eintraege sind auch als Datenmenge ein Problem (#635)."""
    from bewerbungs_assistent.tools.dokumente import PLAN_ZUORDNUNGEN_MAX
    db.add_application({"title": "Consultant", "company": "Musterfirma GmbH"})
    anzahl = PLAN_ZUORDNUNGEN_MAX + 7
    for i in range(anzahl):
        _dok(db, id=f"m{i}", filename=f"Musterfirma_Antwort_{i}.eml",
             doc_type="bewerbungsantwort", extracted_text="Eingang bestaetigt.")
    plan = _plan(db)
    assert len(plan["bewerbungs_zuordnungen"]) == PLAN_ZUORDNUNGEN_MAX
    assert plan["bewerbungs_zuordnungen_gesamt"] == anzahl
    assert "dokumente_ohne_bewerbung" in plan["empfehlung"]


# ── AK: eine Quelle, kein zweiter Weg ────────────────────────────────

def test_991_plan_baut_die_zuordnung_nicht_mehr_selbst():
    """DoD 8c: das Nadeloehr zaehlt erst, wenn es auch aufgerufen wird.

    Die zweite Fassung suchte per SQL `LIKE` ueber `extracted_text`.
    Dieser Test haelt fest, dass sie nicht zurueckkommt.
    """
    quelle = (Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
              / "tools" / "dokumente.py").read_text(encoding="utf-8")
    code = "\n".join(z for z in quelle.splitlines()
                     if not z.lstrip().startswith("#"))
    assert "finde_lose_dokumente" in code
    assert "LOWER(extracted_text) LIKE" not in code


def test_991_warnung_bei_alter_bewerbung_gilt_fuer_beide_wege(db):
    """Vorher stand sie NUR im Plan — eine Warnung an einem von zwei
    Wegen ist keine Warnung."""
    from bewerbungs_assistent.services.dokument_zuordnung import finde_lose_dokumente
    db.add_application({"title": "Projektleiter", "company": "Musterfirma GmbH",
                        "status": "abgelehnt"})
    _dok(db, id="alt-1", filename="Musterfirma_Neu.eml", doc_type="recruiter_anfrage",
         extracted_text="Neue Position fuer Sie.")

    im_plan = next(e for e in _plan(db)["bewerbungs_zuordnungen"]
                   if e["dateiname"] == "Musterfirma_Neu.eml")
    assert "abgeschlossen" in im_plan.get("achtung", "")

    im_detail = next(t for t in finde_lose_dokumente(db)["treffer"]
                     if t["dateiname"] == "Musterfirma_Neu.eml")
    assert "abgeschlossen" in (im_detail["zuordnungs_vorschlag"] or {}).get("achtung", "")


def test_991_laufende_bewerbung_bekommt_keine_warnung(db):
    db.add_application({"title": "Projektleiter", "company": "Musterfirma GmbH",
                        "status": "beworben"})
    _dok(db, id="neu-1", filename="Musterfirma_Eingang.eml",
         doc_type="bewerbungsantwort", extracted_text="Eingang bestaetigt.")
    eintrag = next(e for e in _plan(db)["bewerbungs_zuordnungen"]
                   if e["dateiname"] == "Musterfirma_Eingang.eml")
    assert "achtung" not in eintrag


def test_991_verknuepfte_dokumente_werden_nicht_vorgeschlagen(db):
    """Ein Dokument, das schon haengt, ist kein loser Fall."""
    app_id = db.add_application({"title": "Consultant", "company": "Musterfirma GmbH"})
    _dok(db, id="schon-dran", filename="Musterfirma_Antwort.eml",
         doc_type="bewerbungsantwort", extracted_text="Eingang bestaetigt.",
         linked_application_id=app_id)
    z = _plan(db)["bewerbungs_zuordnungen"]
    assert not [e for e in z if e["dokument_id"] == "schon-dran"], z
