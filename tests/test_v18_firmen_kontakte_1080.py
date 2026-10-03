"""Firmen-Stammsatz (#1080): Kontakte gehören einer oder mehreren Firmen — mit Rolle und Zeitraum (aktuell, früher).

Das Textfeld „Firma“ am Kontakt bleibt, wie es ist. Die Zuordnung ist die bestätigte, strukturierte Fassung; sie ersetzt keinen Text.
Von Stelle, Bewerbung und Kontakt führt ein Aufruf zur Firma. Alle Namen sind Platzhalter. Wegwerf-Datenbank unter tmp_path.
"""
import asyncio
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bewerbungs_assistent.services import firmen_bezuege as fb  # noqa: E402
from bewerbungs_assistent.services import firmen_stamm as fs  # noqa: E402


@pytest.fixture
def db(tmp_db, tmp_path):
    assert str(tmp_path) in str(tmp_db.db_path), f"DB nicht isoliert: {tmp_db.db_path}"
    tmp_db.save_profile({"name": "Erika Beispiel"})
    return tmp_db


@pytest.fixture
def werkzeug(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("firmen-kontakte-test")
    register_all(mcp, db, logging.getLogger("firmen-kontakte-test"))

    def aufruf(werkzeugname, /, **args):
        async def _run():
            tool = await mcp.get_tool(werkzeugname)
            res = await tool.run(args)
            return res.structured_content if hasattr(res, "structured_content") else res
        return asyncio.run(_run())
    return aufruf


def _kontakt(db, name="Kim Beispiel", firma="Alt AG", position="Einkauf"):
    return db.add_contact({"full_name": name, "company": firma, "position": position})


# ── Zuordnen: Rolle und Zeitraum ───────────────────────────────────────────────────────────────

def test_ein_kontakt_wird_einer_firma_zugeordnet_und_der_text_bleibt(db):
    kid = _kontakt(db)
    f = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    r = fs.kontakt_zuordnen(db, f["id"], kid, rolle="recruiter", von="2021")
    assert r["status"] == "zugeordnet" and r["zuordnung"]["zeitraum"] == "seit 2021" and r["zuordnung"]["aktuell"] is True
    assert r["zuordnung"]["id"].startswith("cc_") and r["zuordnung"]["firma"] == "Neu GmbH"
    assert db.get_contact(kid)["company"] == "Alt AG", "das Textfeld Firma am Kontakt bleibt"
    assert [z["kontakt_id"] for z in fs.kontakte_der_firma(db, f["id"])] == [kid]


def test_derselbe_kontakt_gehoert_mehreren_firmen_aktuell_und_frueher(db):
    kid = _kontakt(db)
    neu = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    alt = fs.firma_anlegen(db, "Alt AG")["firma"]
    fs.kontakt_zuordnen(db, alt["id"], kid, rolle="kollege", von="2015", bis="2020")
    fs.kontakt_zuordnen(db, neu["id"], kid, rolle="recruiter", von="2021")
    firmen = fs.firmen_des_kontakts(db, kid)
    assert [(z["firma"], z["zeitraum"], z["aktuell"]) for z in firmen] == [("Neu GmbH", "seit 2021", True), ("Alt AG", "2015 bis 2020", False)]
    assert firmen[0]["rolle"] == "recruiter" and firmen[1]["rolle"] == "kollege", "die Rolle gilt je Firma"


def test_ein_ende_macht_den_kontakt_zum_fruehen_ohne_datum_gilt_er_als_aktuell(db):
    kid = _kontakt(db)
    f = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    assert fs.kontakt_zuordnen(db, f["id"], kid, bis="2019")["zuordnung"]["aktuell"] is False
    z = fs.kontakt_zuordnen(db, f["id"], kid, rolle="mentor")["zuordnung"]
    assert z["aktuell"] is True and z["zeitraum"] == "aktuell"
    fr = fs.kontakt_zuordnen(db, f["id"], kid, rolle="frueher", aktuell=False)["zuordnung"]
    assert fr["aktuell"] is False and fr["zeitraum"] == "früher"


@pytest.mark.parametrize("eingabe,erwartet", [("2021", "2021"), ("2021-03", "2021-03"), ("03.2021", "2021-03"), ("3.2021", "2021-03"),
                                              ("15.03.2021", "2021-03-15"), ("2021-03-05", "2021-03-05"), ("", "")])
def test_zeitangaben_werden_vereinheitlicht(eingabe, erwartet):
    assert fs._zeit(eingabe) == (erwartet, "")


@pytest.mark.parametrize("boese", ["gestern", "2021-13", "31.02.2021", "21", "2021/03", "03-2021"])
def test_falsche_zeitangaben_werden_abgewiesen(boese):
    wert, fehler = fs._zeit(boese)
    assert wert == "" and fehler


def test_ungueltige_angaben_werden_abgewiesen(db):
    kid = _kontakt(db)
    f = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    assert fs.kontakt_zuordnen(db, f["id"], kid, von="gestern")["status"] == "fehler"
    r = fs.kontakt_zuordnen(db, f["id"], kid, von="2022", bis="2020")
    assert r["status"] == "fehler" and "nach dem Ende" in r["text"]
    r = fs.kontakt_zuordnen(db, f["id"], kid, bis="2020", aktuell=True)
    assert r["status"] == "fehler" and "nicht aktuell" in r["text"]
    assert fs.kontakte_der_firma(db, f["id"]) == [], "nichts wurde gespeichert"


def test_doppelt_unbekannt_und_gekuerzte_kennung(db):
    kid = _kontakt(db)
    f = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    assert fs.kontakt_zuordnen(db, f["id"], kid, rolle="recruiter", von="2021")["status"] == "zugeordnet"
    doppelt = fs.kontakt_zuordnen(db, f["id"], kid, rolle="recruiter", von="2021")
    assert doppelt["status"] == "schon_da" and len(fs.kontakte_der_firma(db, f["id"])) == 1
    assert fs.kontakt_zuordnen(db, f["id"], "gibtsnicht")["status"] == "nicht_gefunden"
    assert fs.kontakt_zuordnen(db, "fi_gibtsnicht", kid)["status"] == "nicht_gefunden"
    assert fs.kontakt_zuordnen(db, f["id"], "CON-" + kid, rolle="mit Praefix")["status"] == "zugeordnet"
    assert fs.kontakt_zuordnen(db, f["id"], kid[:4], rolle="gekuerzt")["status"] == "zugeordnet"


def test_ein_fremder_kontakt_laesst_sich_nicht_zuordnen(db):
    f = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    conn = db.connect()
    conn.execute("INSERT INTO contacts (id, profile_id, full_name, created_at) VALUES ('fremd001', 'ein-anderes-profil', 'Fremd Person', '2026-01-01')")
    conn.commit()
    assert fs.kontakt_zuordnen(db, f["id"], "fremd001")["status"] == "nicht_gefunden"


def test_eine_mehrdeutige_kurze_kennung_wird_nicht_geraten(db):
    f = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    conn = db.connect()
    for i in (1, 2):
        conn.execute("INSERT INTO contacts (id, profile_id, full_name, created_at) VALUES (?, ?, ?, '2026-01-01')",
                     (f"abcd000{i}", db.get_active_profile_id(), f"Person {i}"))
    conn.commit()
    assert fs.kontakt_zuordnen(db, f["id"], "abcd")["status"] == "nicht_gefunden"
    assert fs.kontakt_zuordnen(db, f["id"], "abcd0001")["status"] == "zugeordnet"


# ── Ändern, Entfernen, Aufräumen ───────────────────────────────────────────────────────────────

def test_aendern_und_entfernen(db):
    kid = _kontakt(db)
    f = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    zid = fs.kontakt_zuordnen(db, f["id"], kid, rolle="recruiter", von="2021")["zuordnung"]["id"]
    r = fs.zuordnung_aendern(db, zid, bis="2023")
    assert r["status"] == "geaendert" and r["zuordnung"]["aktuell"] is False and r["zuordnung"]["zeitraum"] == "2021 bis 2023", "ein Ende macht ihn zum fruehen"
    r = fs.zuordnung_aendern(db, zid, bis="", aktuell=True, rolle="kollege")
    assert r["zuordnung"]["aktuell"] is True and r["zuordnung"]["rolle"] == "kollege" and r["zuordnung"]["zeitraum"] == "seit 2021"
    assert fs.zuordnung_aendern(db, zid, bis="2020")["status"] == "fehler", "Ende vor Beginn"
    assert fs.zuordnung_aendern(db, zid, farbe="rot")["status"] == "fehler"
    assert fs.zuordnung_aendern(db, "cc_gibtsnicht", rolle="x")["status"] == "nicht_gefunden"
    assert fs.zuordnung_entfernen(db, zid)["status"] == "entfernt"
    assert fs.kontakte_der_firma(db, f["id"]) == [] and db.get_contact(kid) is not None, "der Kontakt bleibt"
    assert fs.zuordnung_entfernen(db, zid)["status"] == "nicht_gefunden"


def test_loeschen_der_firma_nimmt_die_zuordnungen_mit_auch_ohne_fremdschluessel(db):
    kid = _kontakt(db)
    f = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    fs.kontakt_zuordnen(db, f["id"], kid)
    db.connect().execute("PRAGMA foreign_keys=OFF")
    assert fs.firma_loeschen(db, f["id"])["status"] == "geloescht"
    assert db.connect().execute("SELECT COUNT(*) FROM company_contacts").fetchone()[0] == 0
    assert db.get_contact(kid) is not None


def test_zusammenfuehren_nimmt_die_zuordnungen_mit(db):
    kid = _kontakt(db)
    ziel = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    quelle = fs.firma_anlegen(db, "Alt AG")["firma"]
    fs.kontakt_zuordnen(db, quelle["id"], kid, rolle="kollege", von="2015", bis="2020")
    assert fs.zusammenfuehren(db, ziel["id"], quelle["id"])["status"] == "zusammengefuehrt"
    assert [(z["firma"], z["rolle"]) for z in fs.kontakte_der_firma(db, ziel["id"])] == [("Neu GmbH", "kollege")]


def test_wird_der_kontakt_geloescht_gehen_seine_zuordnungen_mit(db):
    kid = _kontakt(db)
    f = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    fs.kontakt_zuordnen(db, f["id"], kid)
    assert db.delete_contact(kid)
    assert fs.kontakte_der_firma(db, f["id"]) == []


# ── firma_kontext: der Kontakt erscheint einmal, mit Zeitraum ──────────────────────────────────

def test_der_kontakt_erscheint_in_der_firma_einmal_mit_zeitraum(db):
    kid = _kontakt(db, firma="Neu GmbH")                       # das Textfeld nennt die Firma ebenfalls
    f = fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])["firma"]
    fs.kontakt_zuordnen(db, f["id"], kid, rolle="recruiter", von="2021")
    erg = fb.bezuege(db, "Neu GmbH")
    kontakte = [b for b in erg["bezuege"] if b["rolle"] == "kontakt"]
    assert len(kontakte) == 1, "nicht zusaetzlich als Namenstreffer"
    k = kontakte[0]
    assert k["abgleich"] == "zuordnung" and k["person"] == "Kim Beispiel" and k["funktion"] == "recruiter" and k["zeitraum"] == "seit 2021"
    assert "seit 2021" in fb.kompakt(k)["kurz"]
    assert "zuordnung" not in erg["schreibweisen"] and all(s in ("Neu GmbH", "Alt AG") for s in erg["schreibweisen"])


def test_der_firmentext_eines_zugeordneten_kontakts_wird_keine_schreibweise(db):
    kid = _kontakt(db, firma="Ganz Andere Firma")
    f = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    fs.kontakt_zuordnen(db, f["id"], kid, rolle="recruiter")
    erg = fb.bezuege(db, "Neu GmbH")
    assert any(b["rolle"] == "kontakt" for b in erg["bezuege"])
    assert "Ganz Andere Firma" not in erg["schreibweisen"], "der Text am Kontakt sagt nichts ueber die Schreibweisen der Firma"


def test_ein_kontakt_ohne_zuordnung_bleibt_ein_namenstreffer(db):
    _kontakt(db, firma="Neu GmbH")
    fs.firma_anlegen(db, "Neu GmbH")
    kontakte = [b for b in fb.bezuege(db, "Neu GmbH")["bezuege"] if b["rolle"] == "kontakt"]
    assert len(kontakte) == 1 and kontakte[0]["abgleich"] != "zuordnung"


def test_die_fruehere_firma_nennt_den_kontakt_als_frueher(db):
    kid = _kontakt(db, firma="Neu GmbH")
    neu = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    alt = fs.firma_anlegen(db, "Alt AG")["firma"]
    fs.kontakt_zuordnen(db, alt["id"], kid, rolle="kollege", von="2015", bis="2020")
    fs.kontakt_zuordnen(db, neu["id"], kid, rolle="recruiter", von="2021")
    frueher = [b for b in fb.bezuege(db, "Alt AG")["bezuege"] if b["rolle"] == "kontakt"]
    assert len(frueher) == 1 and frueher[0]["aktuell"] is False and frueher[0]["zeitraum"] == "2015 bis 2020"


# ── Die MCP-Wege ───────────────────────────────────────────────────────────────────────────────

def test_kontakt_verknuepfen_mit_firma_ordnet_der_firma_zu(db, werkzeug):
    kid = _kontakt(db)
    f = fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])["firma"]
    erg = werkzeug("kontakt_verknuepfen", kontakt_id=kid, ziel_typ="firma", ziel_id=f["id"], rolle="recruiter", von="2021")
    assert erg["status"] == "verknuepft" and erg["zuordnung"]["zeitraum"] == "seit 2021", erg
    erg = werkzeug("kontakt_verknuepfen", kontakt_id=kid, ziel_typ="firma", ziel_id="Alt AG", rolle="kollege", von="2015", bis="2020")
    assert erg["status"] == "verknuepft" and erg["zuordnung"]["firma"] == "Neu GmbH", "der frühere Name führt zur selben Firma"
    assert len(fs.firmen_des_kontakts(db, kid)) == 2


def test_kontakt_verknuepfen_mit_unbekannter_firma_nennt_den_naechsten_schritt(db, werkzeug):
    kid = _kontakt(db)
    erg = werkzeug("kontakt_verknuepfen", kontakt_id=kid, ziel_typ="firma", ziel_id="Ganz Neu GmbH")
    assert "fehler" in erg and "anlegen" in erg["naechster_schritt"]
    assert db.get_contact_links(kid) == [], "kein stiller Eintrag ins Leere"


def test_kontakt_verknuepfen_mit_mehrdeutigem_namen_raet_nicht(db, werkzeug):
    kid = _kontakt(db)
    fs.firma_anlegen(db, "Muster Energie GmbH")
    fs.firma_anlegen(db, "Muster Medizin GmbH")
    erg = werkzeug("kontakt_verknuepfen", kontakt_id=kid, ziel_typ="firma", ziel_id="Muster")
    assert "fehler" in erg and "mehreren Firmen" in erg["fehler"]


def test_kontakt_verknuepfen_mit_bewerbung_bleibt_wie_vorher(db, werkzeug):
    kid = _kontakt(db)
    aid = db.add_application({"title": "Einkauf", "company": "Alt AG", "status": "beworben"})
    erg = werkzeug("kontakt_verknuepfen", kontakt_id=kid, ziel_typ="bewerbung", ziel_id=aid)
    assert erg["status"] == "verknuepft" and "link_id" in erg


def test_das_werkzeug_ordnet_zu_aendert_und_entfernt(db, werkzeug):
    kid = _kontakt(db)
    f = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    erg = werkzeug("firmen_stamm_bearbeiten", aktion="kontakt_zuordnen", firma_id=f["id"], kontakt_id=kid, rolle="recruiter", von="2021")
    assert erg["status"] == "zugeordnet", erg
    zid = erg["zuordnung"]["id"]
    erg = werkzeug("firmen_stamm_bearbeiten", aktion="zuordnung_aendern", zuordnung_id=zid, bis="2023")
    assert erg["status"] == "geaendert" and erg["zuordnung"]["aktuell"] is False
    assert werkzeug("firmen_stamm_bearbeiten", aktion="zuordnung_aendern", zuordnung_id=zid)["status"] == "fehler", "nichts zu aendern"
    anzeige = werkzeug("firmen_stamm_anzeigen", firma=f["id"])
    assert [k["zeitraum"] for k in anzeige["kontakte"]] == ["2021 bis 2023"]
    assert werkzeug("firmen_stamm_bearbeiten", aktion="zuordnung_entfernen", zuordnung_id=zid)["status"] == "entfernt"


# ── Von jedem Ort zur Firma ────────────────────────────────────────────────────────────────────

def test_oeffnen_aufrufe_nennt_jede_firma_einmal():
    assert fb.oeffnen_aufrufe("Neu GmbH", "neu gmbh", "", None, "Alt AG") == ["firma_kontext('Neu GmbH')", "firma_kontext('Alt AG')"]
    assert fb.oeffnen_aufrufe("O'Brien Handel") == ["firma_kontext('O\\'Brien Handel')"]
    assert fb.oeffnen_aufrufe() == [] and fb.oeffnen_aufrufe("GmbH") == []


def test_kontakt_anzeigen_fuehrt_zu_jeder_firma(db, werkzeug):
    kid = _kontakt(db, firma="Alt AG")
    neu = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    fs.kontakt_zuordnen(db, neu["id"], kid, rolle="recruiter", von="2021")
    erg = werkzeug("kontakt_anzeigen", kontakt_id=kid)
    assert [(f["firma"], f["zeitraum"]) for f in erg["firmen"]] == [("Neu GmbH", "seit 2021")]
    assert erg["firma_oeffnen"] == ["firma_kontext('Neu GmbH')", "firma_kontext('Alt AG')"], "Zuordnung und Textfeld"


def test_bewerbung_details_fuehrt_zu_arbeitgeber_vermittler_und_endkunde(db, werkzeug):
    aid = db.add_application({"title": "Einkauf", "company": "Alt AG", "status": "beworben", "endkunde": "Kunde Beispiel GmbH"})
    db.update_application(aid, {"vermittler": "Vermittler Beispiel"})
    erg = werkzeug("bewerbung_details", bewerbung_id=aid)
    assert erg["firma_oeffnen"] == ["firma_kontext('Alt AG')", "firma_kontext('Vermittler Beispiel')", "firma_kontext('Kunde Beispiel GmbH')"]


def test_fit_analyse_fuehrt_zur_firma_der_stelle(db, werkzeug):
    db.save_jobs([{"hash": "j1", "title": "Einkaufsleiter", "company": "Neu GmbH", "url": "https://stepstone.example/s/1", "source": "stepstone",
                   "description": "Aufgabe " * 30, "score": 10}])
    erg = werkzeug("fit_analyse", job_hash=db.resolve_job_hash("j1"))
    assert erg.get("firma_oeffnen") == ["firma_kontext('Neu GmbH')"], erg.get("fehler") or list(erg)


def test_die_neue_tabelle_ist_ein_loeschbereich(db):
    from bewerbungs_assistent.services import loeschbereiche
    alle = {t for tabellen in loeschbereiche.BEREICHE.values() for t in tabellen}
    assert {"companies", "company_aliases", "company_contacts"} <= alle
