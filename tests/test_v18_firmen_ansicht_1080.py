"""Firmen-Ansicht im Dashboard (#1080): alles zu einer Firma als Zeitleiste, bedienbar wie über MCP.

Die Ansicht liest über dieselbe Funktion wie das Werkzeug `firma_kontext` (kein zweiter Weg zur Wahrheit). Alle Namen sind Platzhalter.
Wegwerf-Datenbank unter tmp_path; der Dashboard-Zugriff läuft über den TestClient gegen genau diese Datenbank.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bewerbungs_assistent.services import firmen_ansicht as fa  # noqa: E402
from bewerbungs_assistent.services import firmen_stamm as fs  # noqa: E402


@pytest.fixture
def db(tmp_db, tmp_path):
    assert str(tmp_path) in str(tmp_db.db_path), f"DB nicht isoliert: {tmp_db.db_path}"
    tmp_db.save_profile({"name": "Erika Beispiel"})
    return tmp_db


@pytest.fixture
def client(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    dash._db = db
    return TestClient(dash.app)


def _bestand(db):
    """Eine Firma mit allem, was PBP zu ihr wissen kann."""
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"], branche="Handel")
    a1 = db.add_application({"title": "Einkaufsleiter", "company": "Alt AG", "status": "abgelehnt", "applied_at": "2025-03-01"})
    a2 = db.add_application({"title": "Beschaffer", "company": "Vermittler Beispiel", "status": "interview", "endkunde": "Neu GmbH",
                             "applied_at": "2026-09-10"})
    db.update_application(a2, {"vermittler": "Vermittler Beispiel"})
    db.save_jobs([{"hash": "stelle1", "title": "Teamleiter Einkauf", "company": "Neu GmbH", "url": "https://stepstone.example/s/1",
                   "source": "stepstone", "description": "Aufgabe " * 30, "score": 12.5, "found_at": "2026-09-20T08:00:00"}])
    kid = db.add_contact({"full_name": "Kim Beispiel", "company": "Alt AG", "position": "Einkauf"})
    fs.kontakt_zuordnen(db, fs.aufloesen(db, "Neu GmbH")["firma"]["id"], kid, rolle="recruiter", von="2021")
    db.add_position({"company": "Alt AG", "title": "Planer", "start_date": "2015-01", "end_date": "2019-06"})
    db.add_document({"filename": "absage.pdf", "filepath": "x", "doc_type": "absage", "extracted_text": "Leider nicht.",
                     "linked_application_id": a2})
    db.add_research_note("firmenrecherche", "Neu GmbH: Familienbetrieb", bewerbung_id=a2)
    db.add_to_blacklist("firma", "Neu GmbH", reason="Gespraech 2019")
    return {"a1": a1, "a2": a2, "kontakt": kid}


def test_die_ansicht_zeigt_alles_zur_firma_in_einer_zeitleiste(db):
    ids = _bestand(db)
    erg = fa.ansicht(db, name="Neu GmbH")
    assert erg["status"] == "ok" and erg["gefunden"] and erg["name"] == "Neu GmbH"
    assert erg["stammsatz"]["name"] == "Neu GmbH" and [a["alias"] for a in erg["stammsatz"]["aliase"]] == ["Alt AG"]
    arten = {e["art"] for e in erg["zeitleiste"]}
    assert {"bewerbung", "stelle", "kontakt", "lebenslauf", "korrespondenz", "recherche", "blacklist"} <= arten, arten
    z = erg["zaehlung"]
    assert z["bewerbung"] == 2 and z["stelle"] == 1 and z["kontakt"] == 1 and z["lebenslauf"] == 1 and z["korrespondenz"] == 1
    # neueste zuerst, ohne Datum ans Ende
    daten = [e["datum"] for e in erg["zeitleiste"]]
    mit = [d for d in daten if d]
    assert mit == sorted(mit, reverse=True) and daten[: len(mit)] == mit
    assert erg["dashboard_link"].endswith("/#kontakte/" + erg["stammsatz"]["id"])


def test_jeder_eintrag_fuehrt_dorthin_wo_er_steht(db):
    ids = _bestand(db)
    nach_art = {}
    for e in fa.ansicht(db, name="Neu GmbH")["zeitleiste"]:
        nach_art.setdefault(e["art"], []).append(e)
    assert {e["ziel"]["bewerbung_id"] for e in nach_art["bewerbung"]} == {ids["a1"], ids["a2"]}
    assert nach_art["stelle"][0]["ziel"]["seite"] == "stellen" and nach_art["stelle"][0]["ziel"]["job_hash"]
    assert nach_art["kontakt"][0]["ziel"] == {"seite": "kontakte", "suche": "Kim Beispiel"}
    assert nach_art["kontakt"][0]["ref"]["kontakt_id"] == ids["kontakt"] and nach_art["kontakt"][0]["ref"]["zuordnung_id"].startswith("cc_")
    assert nach_art["lebenslauf"][0]["ziel"]["seite"] == "profil"
    assert nach_art["korrespondenz"][0]["ziel"]["seite"] == "dokumente" and nach_art["korrespondenz"][0]["titel"] == "Absage"
    assert nach_art["recherche"][0]["ziel"]["bewerbung_id"] == ids["a2"]
    assert nach_art["blacklist"][0]["ziel"]["seite"] == "suche" and "2019" in nach_art["blacklist"][0]["text"]


def test_die_rollen_sind_fuer_menschen_beschrieben(db):
    _bestand(db)
    bewerbungen = [e for e in fa.ansicht(db, name="Neu GmbH")["zeitleiste"] if e["art"] == "bewerbung"]
    nach_status = {e["status"]: e for e in bewerbungen}
    assert nach_status["interview"]["rolle_text"] == "Als Endkunde" and "läuft über Vermittler Beispiel" in nach_status["interview"]["text"]
    assert nach_status["abgelehnt"]["via"] == "schreibweise" and nach_status["abgelehnt"]["gefunden_als"] == "Alt AG"
    assert nach_status["abgelehnt"]["via_text"] == "unter anderer Schreibweise"


def test_eine_firma_ohne_eintrag_hat_trotzdem_eine_ansicht(db):
    db.add_application({"title": "Einkauf", "company": "Ohne Eintrag GmbH", "status": "beworben", "applied_at": "2026-01-05"})
    erg = fa.ansicht(db, name="Ohne Eintrag")
    assert erg["status"] == "ok" and erg["gefunden"] and erg["stammsatz"] is None
    assert erg["zaehlung"]["bewerbung"] == 1 and erg["dashboard_link"].endswith("/#kontakte/firma%3AOhne%20Eintrag")


def test_eine_unbekannte_firma_ist_gefunden_false_mit_aehnlichen_namen(db):
    db.add_application({"title": "Einkauf", "company": "Personalservice Beispiel", "status": "beworben"})
    erg = fa.ansicht(db, name="Personal")
    assert erg["status"] == "ok" and erg["gefunden"] is False and erg["zeitleiste"] == []
    assert erg["aehnliche"] == ["Personalservice Beispiel"]


def test_ueber_die_kennung_und_fehlerfaelle(db):
    f = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    assert fa.ansicht(db, firma_id=f["id"])["name"] == "Neu GmbH"
    assert fa.ansicht(db, firma_id="fi_gibtsnicht")["status"] == "nicht_gefunden"
    assert fa.ansicht(db)["status"] == "fehler"


def test_mehrdeutige_namen_werden_genannt_nicht_geraten(db):
    fs.firma_anlegen(db, "Muster Energie GmbH")
    fs.firma_anlegen(db, "Muster Medizin GmbH")
    erg = fa.ansicht(db, name="Muster")
    assert erg["stammsatz"] is None and sorted(erg["mehrdeutig"]) == ["Muster Energie GmbH", "Muster Medizin GmbH"]


def test_die_ansicht_schreibt_nichts(db):
    _bestand(db)
    zeilen = lambda: [db.connect().execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # noqa: E731
                      for t in ("companies", "company_aliases", "company_contacts", "applications", "jobs", "contacts")]
    vorher = zeilen()
    fa.ansicht(db, name="Neu GmbH")
    assert zeilen() == vorher


def test_das_werkzeug_und_die_ansicht_lesen_dieselbe_quelle(db):
    import logging
    from bewerbungs_assistent.tools.bewerbungen import firma_kontext_daten
    _bestand(db)
    daten = firma_kontext_daten(db, "Neu GmbH", logging.getLogger("t"))
    assert "_roh_bezuege" not in daten, "die Rohdaten sind nie Teil der Werkzeug-Antwort"
    assert daten["dashboard_link"].endswith("/#kontakte/fi_" + daten["stammsatz"]["id"][3:])
    roh = firma_kontext_daten(db, "Neu GmbH", logging.getLogger("t"), roh=True)
    assert roh["_roh_bezuege"] and {k: v for k, v in roh.items() if k != "_roh_bezuege"} == daten


# ── Die Endpunkte ──────────────────────────────────────────────────────────────────────────────

def test_die_endpunkte_lesen(db, client):
    _bestand(db)
    liste = client.get("/api/firmen").json()
    assert liste["anzahl"] == 1 and liste["firmen"][0]["name"] == "Neu GmbH" and liste["firmen"][0]["aliase"] == ["Alt AG"]
    assert client.get("/api/firmen", params={"suche": "Alt"}).json()["anzahl"] == 1
    assert client.get("/api/firmen", params={"suche": "Ganz Anders"}).json()["anzahl"] == 0
    assert client.get("/api/firmen/ansicht", params={"name": "Neu GmbH"}).json()["zaehlung"]["bewerbung"] == 2
    assert client.get("/api/firmen/ansicht", params={"id": "fi_gibtsnicht"}).status_code == 404
    assert client.get("/api/firmen/ansicht").status_code == 400


def test_anlegen_pflegen_zuordnen_ueber_die_endpunkte(db, client):
    kid = db.add_contact({"full_name": "Kim Beispiel", "company": "Alt AG"})
    r = client.post("/api/firmen", json={"name": "Neu GmbH", "aliase": ["Alt AG"], "branche": "Handel"})
    assert r.status_code == 200 and r.json()["status"] == "angelegt"
    fid = r.json()["firma"]["id"]
    assert client.post("/api/firmen", json={"name": "neu gmbh"}).status_code == 409, "derselbe Name ist keine zweite Firma"
    assert client.post(f"/api/firmen/{fid}/aliase", json={"alias": "N-Gruppe", "art": "kurzform"}).json()["status"] == "hinzugefuegt"
    doppelt = client.post(f"/api/firmen/{fid}/aliase", json={"alias": "Alt AG"})
    assert doppelt.status_code == 409 and doppelt.json()["status"] == "schon_da"
    fremd = client.post("/api/firmen", json={"name": "Beispiel Handel"}).json()["firma"]["id"]
    r = client.post(f"/api/firmen/{fremd}/aliase", json={"alias": "N-Gruppe"})
    assert r.status_code == 409 and r.json()["status"] == "gehoert_anderer_firma" and "error" in r.json()
    alias_id = next(a["id"] for a in fs.firma_laden(db, fid)["aliase"] if a["alias"] == "N-Gruppe")
    assert client.delete(f"/api/firmen/{fid}/aliase/{alias_id}").json()["status"] == "entfernt"
    assert client.patch(f"/api/firmen/{fid}", json={"branche": "Logistik", "notizen": "Familienbetrieb"}).json()["firma"]["branche"] == "Logistik"
    assert client.patch(f"/api/firmen/{fid}", json={"mutterfirma_id": fremd}).json()["firma"]["mutterfirma"]["id"] == fremd
    kreis = client.patch(f"/api/firmen/{fremd}", json={"mutterfirma_id": fid})
    assert kreis.status_code == 400 and "Kreis" in kreis.json()["error"]
    assert client.patch(f"/api/firmen/{fid}", json={"name": "Neuer Name GmbH"}).json()["status"] == "umbenannt"
    assert client.patch(f"/api/firmen/{fid}", json={}).status_code == 400
    z = client.post(f"/api/firmen/{fid}/kontakte", json={"kontakt_id": kid, "rolle": "recruiter", "von": "03.2021"})
    assert z.status_code == 200 and z.json()["zuordnung"]["zeitraum"] == "seit 2021-03"
    zid = z.json()["zuordnung"]["id"]
    assert client.post(f"/api/firmen/{fid}/kontakte", json={"kontakt_id": kid, "von": "gestern"}).status_code == 400
    assert client.get(f"/api/contacts/{kid}/firmen").json()["firmen"][0]["firma"] == "Neuer Name GmbH"
    r = client.patch(f"/api/firmen/zuordnungen/{zid}", json={"bis": "2023"})
    assert r.json()["zuordnung"]["aktuell"] is False and r.json()["zuordnung"]["zeitraum"] == "2021-03 bis 2023"
    assert client.patch(f"/api/firmen/zuordnungen/{zid}", json={}).status_code == 400
    assert client.delete(f"/api/firmen/zuordnungen/{zid}").json()["status"] == "entfernt"
    assert client.delete(f"/api/firmen/zuordnungen/{zid}").status_code == 404


def test_zusammenfuehren_und_loeschen_verlangen_die_bestaetigung(db, client):
    ziel = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    quelle = fs.firma_anlegen(db, "Alt AG")["firma"]
    r = client.post(f"/api/firmen/{ziel['id']}/zusammenfuehren", json={"quelle_id": quelle["id"]})
    assert r.status_code == 400 and r.json()["status"] == "bestaetigung_noetig"
    assert fs.firma_laden(db, quelle["id"]) is not None, "ohne Bestaetigung bleibt alles"
    r = client.post(f"/api/firmen/{ziel['id']}/zusammenfuehren", json={"quelle_id": quelle["id"], "bestaetigt": True})
    assert r.status_code == 200 and r.json()["status"] == "zusammengefuehrt" and fs.firma_laden(db, quelle["id"]) is None
    r = client.delete(f"/api/firmen/{ziel['id']}")
    assert r.status_code == 400 and fs.firma_laden(db, ziel["id"]) is not None
    r = client.delete(f"/api/firmen/{ziel['id']}", params={"bestaetigt": "true"})
    assert r.status_code == 200 and fs.firma_laden(db, ziel["id"]) is None
    assert client.delete("/api/firmen/fi_gibtsnicht", params={"bestaetigt": "true"}).status_code == 404
    assert client.post("/api/firmen/fi_x/zusammenfuehren", json={"quelle_id": "fi_y", "bestaetigt": True}).status_code == 404


def test_vorschlaege_erst_zeigen_dann_mit_bestaetigung_anlegen(db, client):
    db.add_application({"title": "A", "company": "Beispielwerk Maschinen GmbH", "status": "beworben"})
    db.add_application({"title": "B", "company": "Beispielwerk-Maschinen", "status": "beworben"})
    liste = client.get("/api/firmen/vorschlaege").json()
    assert liste["anzahl"] == 1
    kennung = liste["vorschlaege"][0]["vorschlag_id"]
    vorschau = client.post("/api/firmen/vorschlaege/anwenden", json={"auswahl": [kennung]}).json()
    assert vorschau["status"] == "vorschau" and client.get("/api/firmen").json()["anzahl"] == 0, "ohne Bestaetigung wird nichts angelegt"
    angewendet = client.post("/api/firmen/vorschlaege/anwenden", json={"auswahl": [kennung], "bestaetigt": True}).json()
    assert angewendet["status"] == "angewendet" and client.get("/api/firmen").json()["anzahl"] == 1
    assert client.post("/api/firmen/vorschlaege/anwenden", json={"auswahl": ["v_gibtsnicht"], "bestaetigt": True}).status_code == 400
    assert client.post("/api/firmen/vorschlaege/anwenden", json={"auswahl": [], "bestaetigt": True}).status_code == 400
