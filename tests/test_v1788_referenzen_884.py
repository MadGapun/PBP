"""Tests fuer #884 — Referenzen an Kontakten (D24).

Der Wunsch, woertlich:

    Ich moechte nur irgendwo eintragen koennen, welche Form Referenz
    derjenige war (und wann), damit ich daraus z.B. eine Referenzliste
    generieren kann.

Fuenf Akzeptanzkriterien:

1. Ein Kontakt kann als Referenz markiert werden (Art aus Liste +
   Freitext-Bemerkung + Zeitraum).
2. Optionale Verknuepfung zu Bewerbung und/oder Projekt, nicht erzwungen.
3. Untermenue "Referenzen" zeigt alle markierten Kontakte, filterbar
   nach Art.
4. Aus der (gefilterten) Auswahl eine Referenzliste als DOCX/PDF.
5. Markierung erzeugt keinen doppelten Kontakt.

Testdaten sind fiktiv; die Telefonnummer folgt der 555-Konvention.
"""
import asyncio
import importlib
import logging
import os
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

CONTACTS_PAGE = _repo() / "frontend" / "src" / "pages" / "ContactsPage.jsx"
APP = _repo() / "frontend" / "src" / "App.jsx"


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database(db_path=tmp_path / "test.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    datenbank.switch_profile(datenbank.create_profile("Referenzen"))
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _mcp(db):
    from fastmcp import FastMCP

    from bewerbungs_assistent.tools.kontakte import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))
    return mcp


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(_run())


def _kontakt(db, name="Erika Beispiel", **extra):
    daten = {"full_name": name, "email": "erika@example.com",
             "phone": "+49 40 555 0100", "company": "Musterbetrieb GmbH",
             "position": "Bereichsleitung"}
    daten.update(extra)
    return db.add_contact(daten)


def _docx_text(pfad) -> str:
    from docx import Document
    return "\n".join(p.text for p in Document(str(pfad)).paragraphs)


# ------------------------------------------------------------------ AK 1


def test_ein_kontakt_wird_mit_art_zeitraum_und_bemerkung_markiert(db):
    """AK 1."""
    cid = _kontakt(db)
    erg = _call(_mcp(db), "referenz_markieren", {
        "kontakt_id": cid, "art": "vorgesetzter", "zeitraum": "2020-2024",
        "bemerkung": "kann zur Programmleitung Auskunft geben"})
    assert erg["status"] == "markiert", erg
    refs = db.list_contact_references()
    assert len(refs) == 1
    r = refs[0]
    assert (r["reference_type"], r["period_text"], r["note"]) == (
        "vorgesetzter", "2020-2024", "kann zur Programmleitung Auskunft geben")


def test_die_art_darf_als_klartext_kommen(db):
    """Die Oberflaeche zeigt Klartext; beide Schreibweisen fuehren zum
    selben Schluessel."""
    cid = _kontakt(db)
    db.add_contact_reference(cid, "Kunde / Auftraggeber")
    assert db.list_contact_references()[0]["reference_type"] == "kunde"


def test_eine_unbekannte_art_wird_abgewiesen_statt_umgedeutet(db):
    """Still auf `sonstiges` zu fallen verfaelschte die Filterung (#980)."""
    cid = _kontakt(db)
    erg = _call(_mcp(db), "referenz_markieren",
                {"kontakt_id": cid, "art": "chefin"})
    assert "fehler" in erg
    assert {a["wert"] for a in erg["erlaubte_arten"]} >= {"vorgesetzter",
                                                          "sonstiges"}
    assert db.list_contact_references() == []


def test_ein_unbekannter_kontakt_wird_benannt(db):
    erg = _call(_mcp(db), "referenz_markieren",
                {"kontakt_id": "gibtsnicht", "art": "kunde"})
    assert "fehler" in erg and "Kontakt nicht gefunden" in erg["fehler"]


def test_die_kurze_kontakt_id_genuegt(db):
    """Die Werkzeuge zeigen Kurz-IDs; sie muessen auch zurueck gehen."""
    cid = _kontakt(db)
    erg = _call(_mcp(db), "referenz_markieren",
                {"kontakt_id": cid[:5], "art": "kunde"})
    assert erg["status"] == "markiert", erg


# ------------------------------------------------------------------ AK 5


def test_die_markierung_erzeugt_keinen_zweiten_kontakt(db):
    """AK 5 — und ein Kontakt darf in mehreren Rollen Referenz sein."""
    cid = _kontakt(db)
    con = db.connect()
    vorher = con.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    db.add_contact_reference(cid, "vorgesetzter", "2018-2020")
    db.add_contact_reference(cid, "kunde", "2021-2024")
    assert con.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == vorher
    assert len(db.list_contact_references(contact_id=cid)) == 2


def test_das_etikett_referenz_kommt_dazu_und_bleibt_beim_entfernen(db):
    """Tabelle ist die Quelle, die Kategorie ein Etikett.

    Beim Entfernen bleibt das Etikett — es kann von Hand gesetzt worden
    sein, und ein Aufraeumen, das eine Eingabe still loescht, waere #988.
    """
    cid = _kontakt(db, tags=["recruiter"])
    erg = db.add_contact_reference(cid, "kunde")
    assert erg["etikett_ergaenzt"] is True
    assert "referenz" in db.get_contact(cid)["tags"]
    assert "recruiter" in db.get_contact(cid)["tags"]
    zweit = db.add_contact_reference(cid, "kollege")
    assert zweit["etikett_ergaenzt"] is False, "Etikett doppelt gesetzt"

    assert db.delete_contact_reference(erg["id"]) is True
    assert db.get_contact(cid) is not None, "Kontakt mitgeloescht"
    assert "referenz" in db.get_contact(cid)["tags"]


# ------------------------------------------------------------------ AK 2


def test_eine_referenz_ohne_bezug_ist_der_normalfall(db):
    """AK 2, erste Haelfte: nicht erzwungen."""
    cid = _kontakt(db)
    db.add_contact_reference(cid, "kunde")
    r = db.list_contact_references()[0]
    assert r["application_id"] is None and r["project_id"] is None


def test_bezug_zu_bewerbung_und_projekt_ist_moeglich(db):
    """AK 2, zweite Haelfte: beides zugleich erlaubt."""
    cid = _kontakt(db)
    app_id = db.add_application({"title": "Senior Consultant",
                                 "company": "Musterbetrieb GmbH",
                                 "status": "beworben"})
    pos = db.add_position({"company": "Musterbetrieb GmbH",
                           "title": "Consultant", "start_date": "2022-01"})
    db.add_project(pos, {"name": "Rollout Nord"})
    proj_id = db.connect().execute(
        "SELECT id FROM projects WHERE name='Rollout Nord'").fetchone()[0]

    erg = _call(_mcp(db), "referenz_markieren", {
        "kontakt_id": cid, "art": "kunde",
        "bewerbung_id": app_id, "projekt_id": proj_id})
    assert erg["status"] == "markiert", erg
    r = db.list_contact_references()[0]
    assert r["bewerbung_titel"] == "Senior Consultant"
    assert r["projekt_name"] == "Rollout Nord"
    assert len(db.list_contact_references(application_id=app_id)) == 1
    assert len(db.list_contact_references(project_id=proj_id)) == 1


def test_ein_bezug_ins_leere_wird_abgewiesen(db):
    """Sonst stuende eine Referenz mit einem Bezug da, den es nicht gibt
    (#997: eine Erfolgsmeldung ueber nichts)."""
    cid = _kontakt(db)
    for feld, text in (("bewerbung_id", "Bewerbung nicht gefunden"),
                       ("projekt_id", "Projekt nicht gefunden")):
        erg = _call(_mcp(db), "referenz_markieren",
                    {"kontakt_id": cid, "art": "kunde", feld: "zzzzzzzz"})
        assert "fehler" in erg and text in erg["fehler"], erg
    assert db.list_contact_references() == []


def test_bearbeiten_none_laesst_stehen_leer_loescht(db):
    """Sonst liesse sich ein Zeitraum nie wieder entfernen."""
    cid = _kontakt(db)
    rid = db.add_contact_reference(cid, "kunde", "2020", "Notiz")["id"]
    mcp = _mcp(db)
    _call(mcp, "referenz_bearbeiten", {"referenz_id": rid, "bemerkung": "neu"})
    r = db.list_contact_references()[0]
    assert (r["period_text"], r["note"]) == ("2020", "neu")
    _call(mcp, "referenz_bearbeiten", {"referenz_id": rid, "zeitraum": ""})
    assert db.list_contact_references()[0]["period_text"] is None
    leer = _call(mcp, "referenz_bearbeiten", {"referenz_id": rid})
    assert leer["status"] == "unveraendert"


# ------------------------------------------------------------------ AK 3


def test_die_liste_laesst_sich_nach_art_filtern(db):
    """AK 3 — ueber den MCP."""
    _call_db = _mcp(db)
    for name, art in (("Anna Beispiel", "kunde"), ("Bert Beispiel", "kunde"),
                      ("Cora Beispiel", "vorgesetzter")):
        db.add_contact_reference(_kontakt(db, name=name), art)
    alle = _call(_call_db, "referenzen_anzeigen", {})
    kunden = _call(_call_db, "referenzen_anzeigen", {"art": "kunde"})
    assert alle["anzahl"] == 3
    assert kunden["anzahl"] == 2
    assert {e["name"] for e in kunden["referenzen"]} == {"Anna Beispiel",
                                                         "Bert Beispiel"}


def test_eine_leere_liste_nennt_den_naechsten_schritt(db):
    """Sackgassen-Regel (#927)."""
    erg = _call(_mcp(db), "referenzen_anzeigen", {})
    assert erg["anzahl"] == 0
    assert "referenz_markieren" in erg["hinweis"]


@pytest.fixture
def client(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient

    alt = dash._db
    dash._db = db
    try:
        yield TestClient(dash.app)
    finally:
        dash._db = alt


def test_rest_filter_und_klartext(db, client):
    """AK 3 — ueber den Weg, den die Oberflaeche nimmt."""
    db.add_contact_reference(_kontakt(db, name="Anna Beispiel"), "kunde")
    db.add_contact_reference(_kontakt(db, name="Cora Beispiel"), "akademisch")
    daten = client.get("/api/references?art=akademisch").json()
    assert daten["anzahl"] == 1
    assert daten["referenzen"][0]["art_label"].startswith("Akademisch")
    assert [a["wert"] for a in daten["arten"]][0] == "vorgesetzter"
    assert client.get("/api/references?art=chefin").status_code == 400


def test_rest_anlegen_aendern_entfernen(db, client):
    cid = _kontakt(db)
    neu = client.post("/api/references", json={
        "contact_id": cid, "reference_type": "kollege",
        "period_text": "2019"})
    assert neu.status_code == 200, neu.text
    rid = neu.json()["id"]
    assert client.put(f"/api/references/{rid}",
                      json={"note": "Projekt Nord"}).status_code == 200
    assert db.list_contact_references()[0]["note"] == "Projekt Nord"
    assert client.delete(f"/api/references/{rid}").status_code == 200
    assert client.delete(f"/api/references/{rid}").status_code == 404
    assert client.post("/api/references", json={
        "contact_id": cid, "reference_type": "xx"}).status_code == 400


# ------------------------------------------------------------------ AK 4


def test_die_liste_als_docx_ohne_kontaktdaten(db, tmp_path):
    """AK 4 — und die Vorgabe: Kontaktdaten nur auf Wunsch."""
    db.add_contact_reference(_kontakt(db), "vorgesetzter", "2020-2024",
                             "Programmleitung")
    erg = _call(_mcp(db), "referenzliste_exportieren", {"format": "docx"})
    assert erg["status"] == "exportiert", erg
    pfad = Path(erg["datei"])
    assert pfad.exists() and str(tmp_path) in str(pfad)
    text = _docx_text(pfad)
    for erwartet in ("Erika Beispiel", "Bereichsleitung", "Musterbetrieb GmbH",
                     "Vorgesetzte", "2020-2024", "Programmleitung",
                     "Kontaktdaten auf Anfrage"):
        assert erwartet in text, erwartet
    assert "erika@example.com" not in text
    assert "None" not in text, "None im Dokument (#1006)"


def test_die_liste_mit_kontaktdaten_auf_wunsch(db):
    db.add_contact_reference(_kontakt(db), "kunde")
    erg = _call(_mcp(db), "referenzliste_exportieren",
                {"format": "docx", "mit_kontaktdaten": True})
    text = _docx_text(erg["datei"])
    assert "erika@example.com" in text
    assert "Kontaktdaten auf Anfrage" not in text


def test_die_liste_folgt_dem_filter(db):
    """AK 4: "aus der (gefilterten) Auswahl"."""
    db.add_contact_reference(_kontakt(db, name="Anna Beispiel"), "kunde")
    db.add_contact_reference(_kontakt(db, name="Cora Beispiel"), "akademisch")
    erg = _call(_mcp(db), "referenzliste_exportieren",
                {"format": "docx", "art": "akademisch"})
    text = _docx_text(erg["datei"])
    assert erg["anzahl"] == 1
    assert "Cora Beispiel" in text and "Anna Beispiel" not in text


def test_die_liste_als_pdf(db):
    db.add_contact_reference(_kontakt(db, name="Jörg Müßig"), "kunde",
                             "2020–2024")
    erg = _call(_mcp(db), "referenzliste_exportieren", {"format": "pdf"})
    assert erg["status"] == "exportiert", erg
    kopf = Path(erg["datei"]).read_bytes()[:5]
    assert kopf == b"%PDF-"


def test_ohne_referenzen_entsteht_keine_leere_datei(db):
    erg = _call(_mcp(db), "referenzliste_exportieren", {"format": "docx"})
    assert erg["status"] == "leer"
    assert "referenz_markieren" in erg["hinweis"]


def test_ein_unbekanntes_format_wird_abgewiesen(db):
    db.add_contact_reference(_kontakt(db), "kunde")
    erg = _call(_mcp(db), "referenzliste_exportieren", {"format": "xlsx"})
    assert "fehler" in erg


def test_rest_export_liefert_die_datei(db, client):
    db.add_contact_reference(_kontakt(db), "kunde")
    antwort = client.get("/api/references/export?format=docx")
    assert antwort.status_code == 200
    assert "wordprocessingml" in antwort.headers["content-type"]
    assert antwort.content[:2] == b"PK"
    leer_filter = client.get("/api/references/export?format=pdf&art=akademisch")
    assert leer_filter.status_code == 404


# ---------------------------------------------------- Loeschen und Bestand


def test_die_tabelle_gehoert_zu_einem_loeschbereich():
    """Der Guard aus #1025 haette sie sonst liegen lassen."""
    from bewerbungs_assistent.services import loeschbereiche as lb
    assert "contact_references" in lb.BEREICHE["bewerbungen"]


def test_ein_geloeschter_kontakt_nimmt_seine_referenzen_mit(db):
    """Sonst stuende eine Referenz ohne Person in der Tabelle."""
    cid = _kontakt(db)
    db.add_contact_reference(cid, "kunde")
    assert db.delete_contact(cid) is True
    anzahl = db.connect().execute(
        "SELECT COUNT(*) FROM contact_references").fetchone()[0]
    assert anzahl == 0


def test_ein_geloeschtes_profil_hinterlaesst_keine_referenz(db):
    from bewerbungs_assistent.services import loeschbereiche as lb
    cid = _kontakt(db)
    db.add_contact_reference(cid, "kunde")
    pid = db.get_active_profile_id()
    db.delete_profile(pid)
    assert lb.verwaiste_profilzeilen(db)["zeilen_gesamt"] == 0
    assert db.connect().execute(
        "SELECT COUNT(*) FROM contact_references").fetchone()[0] == 0


# ------------------------------------------------------------ Oberflaeche


def _ohne_kommentare(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(
        z for z in text.split("\n") if not z.lstrip().startswith("//"))


def test_das_untermenue_referenzen_steht_in_der_navigation():
    """AK 3 — Untermenue unter Kontakte."""
    quelle = _ohne_kommentare(APP.read_text(encoding="utf-8"))
    assert '"contacts-view-referenzen"' in quelle
    assert '"contacts-nav"' in quelle


def test_die_seite_hat_ansicht_filter_und_export():
    quelle = _ohne_kommentare(CONTACTS_PAGE.read_text(encoding="utf-8"))
    assert "<ReferencesSection" in quelle
    assert 'addEventListener("contacts-nav"' in quelle
    assert "/api/references/export" in quelle
    assert 'aria-label="Nach Art der Referenz filtern"' in quelle
    assert "Als Referenz markieren" in quelle


def test_die_arten_stehen_nur_im_backend():
    """Eine zweite Liste in der Oberflaeche liefe beim naechsten Eintrag
    auseinander (#979, #981) — die Oberflaeche liest `arten` vom Server."""
    quelle = CONTACTS_PAGE.read_text(encoding="utf-8")
    assert "auftraggeber_freelance" not in quelle
    assert "geschaeftspartner" not in quelle
