"""Firmen-Stammsatz (#1080, Stufe 2): bestätigte Schreibweisen, Mutterfirma, Vorschläge nur nach Bestätigung.

Der Stammsatz ersetzt keine Textfelder: Bewerbungen, Stellen, Kontakte und Lebenslauf behalten ihren Firmennamen. Er wird beim
Lesen aufgelöst. Alle Firmennamen hier sind Platzhalter (QA-Regel). Wegwerf-Datenbank unter tmp_path.
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


def _app(db, firma, titel="Sachbearbeiter", status="beworben", vermittler="", endkunde="", notizen=""):
    aid = db.add_application({"title": titel, "company": firma, "status": status, "endkunde": endkunde, "notes": notizen})
    if vermittler:
        db.update_application(aid, {"vermittler": vermittler})
    return aid


# ── Anlegen, Schreibweisen, Auflösen ───────────────────────────────────────────────────────

def test_eine_firma_mit_schreibweisen_anlegen(db):
    r = fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG", "N-Gruppe"], branche="Maschinenbau")
    assert r["status"] == "angelegt" and r["hinweise"] == []
    f = r["firma"]
    assert f["id"].startswith("fi_") and f["branche"] == "Maschinenbau"
    assert [a["alias"] for a in f["aliase"]] == ["Alt AG", "N-Gruppe"]


def test_ein_name_gehoert_nur_einer_firma(db):
    a = fs.firma_anlegen(db, "Acme Solutions GmbH")["firma"]
    assert fs.firma_anlegen(db, "ACME Solutions")["status"] == "schon_da", "Rechtsform und Schreibweise zaehlen nicht"
    b = fs.firma_anlegen(db, "Beispiel Handel")["firma"]
    r = fs.alias_hinzufuegen(db, b["id"], "Acme Solutions AG")
    assert r["status"] == "gehoert_anderer_firma" and r["firma_id"] == a["id"] and "zusammen" in r["text"]
    assert fs.alias_hinzufuegen(db, a["id"], "acme  solutions")["status"] == "schon_da"
    assert [x["alias"] for x in fs.firma_laden(db, b["id"])["aliase"]] == []


def test_ein_name_nur_aus_rechtsform_oder_leer_wird_abgewiesen(db):
    for boese in ("", "   ", "GmbH", "AG & Co. KG", None):
        assert fs.firma_anlegen(db, boese)["status"] == "fehler", repr(boese)
    f = fs.firma_anlegen(db, "Beispiel")["firma"]
    assert fs.alias_hinzufuegen(db, f["id"], "GmbH")["status"] == "fehler"
    assert fs.alias_hinzufuegen(db, f["id"], "Kurz", art="gibts-nicht")["status"] == "fehler"


def test_aufloesen_exakt_ueber_name_und_schreibweise(db):
    f = fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])["firma"]
    for name in ("Neu GmbH", "neu", "NEU gmbh", "Alt AG", "alt", "Alt-AG"):
        r = fs.aufloesen(db, name)
        assert r["firma"] and r["firma"]["id"] == f["id"], name
    assert fs.aufloesen(db, "Ganz Anders")["firma"] is None
    assert fs.aufloesen(db, "")["firma"] is None and fs.aufloesen(db, "GmbH")["firma"] is None


def test_aufloesen_per_abgleich_nur_wenn_es_genau_eine_firma_ist(db):
    energie = fs.firma_anlegen(db, "Muster Energie GmbH")["firma"]
    fs.firma_anlegen(db, "Muster Medizin GmbH")
    r = fs.aufloesen(db, "Muster")
    assert r["firma"] is None and sorted(r["mehrdeutig"]) == ["Muster Energie GmbH", "Muster Medizin GmbH"], "PBP raet nicht"
    r = fs.aufloesen(db, "Muster Energie Hamburg")
    assert r["firma"] and r["firma"]["id"] == energie["id"] and r["art"] == "abgleich"


def test_gleiche_firma_nach_namensform_oder_stammsatz(db):
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    assert fs.gleiche_firma(db, "Neu GmbH", "neu") is True
    assert fs.gleiche_firma(db, "Alt AG", "Neu GmbH") is True, "ueber den Stammsatz"
    assert fs.gleiche_firma(db, "Alt AG", "Beispiel") is False
    assert fs.gleiche_firma(db, "", "Neu") is False


def test_stammsaetze_gehoeren_zum_profil(db):
    f = fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])["firma"]
    erstes = db.get_active_profile_id()
    db.switch_profile(db.create_profile("Zweites Profil"))
    assert fs.firmen_liste(db) == [] and fs.firma_laden(db, f["id"]) is None
    assert fs.aufloesen(db, "Alt AG")["firma"] is None
    assert fs.firma_anlegen(db, "Neu GmbH")["status"] == "angelegt", "dasselbe in einem anderen Profil ist frei"
    db.switch_profile(erstes)
    assert [x["name"] for x in fs.firmen_liste(db)] == ["Neu GmbH"]
    assert fs.aufloesen(db, "Alt AG")["firma"]["id"] == f["id"]


# ── Pflege ─────────────────────────────────────────────────────────────────────────────────

def test_umbenennen_merkt_den_alten_namen(db):
    f = fs.firma_anlegen(db, "Alt AG")["firma"]
    r = fs.umbenennen(db, f["id"], "Neu GmbH")
    assert r["status"] == "umbenannt" and r["firma"]["name"] == "Neu GmbH"
    assert [(a["alias"], a["art"]) for a in r["firma"]["aliase"]] == [("Alt AG", "frueherer_name")]
    assert fs.aufloesen(db, "Alt AG")["firma"]["id"] == f["id"]
    # zurueck auf einen Namen, der bisher eine Schreibweise war: er wird wieder Name, keine Dublette
    r = fs.umbenennen(db, f["id"], "Alt AG", alten_namen_merken=False)
    assert r["firma"]["name"] == "Alt AG" and [a["alias"] for a in r["firma"]["aliase"]] == []
    # ein Name, den eine andere Firma traegt, geht nicht
    g = fs.firma_anlegen(db, "Beispiel Handel")["firma"]
    assert fs.umbenennen(db, g["id"], "Alt AG")["status"] == "schon_da"


def test_mutterfirma_setzen_loesen_und_keine_kreise(db):
    a = fs.firma_anlegen(db, "Konzern Beispiel")["firma"]
    b = fs.firma_anlegen(db, "Tochter Beispiel", mutterfirma_id=a["id"])["firma"]
    c = fs.firma_anlegen(db, "Enkel Beispiel")["firma"]
    assert fs.firma_laden(db, a["id"])["tochterfirmen"] == [{"id": b["id"], "name": "Tochter Beispiel"}]
    assert fs.mutterfirma_setzen(db, c["id"], b["id"])["status"] == "gesetzt"
    for kreis in ((a["id"], a["id"]), (a["id"], b["id"]), (a["id"], c["id"])):
        r = fs.mutterfirma_setzen(db, *kreis)
        assert r["status"] == "fehler" and "Kreis" in r["text"], kreis
    assert fs.mutterfirma_setzen(db, b["id"], "fi_gibtsnicht")["status"] == "fehler"
    assert fs.mutterfirma_setzen(db, c["id"], "")["firma"]["mutterfirma"] is None
    assert fs.firma_anlegen(db, "Kind", mutterfirma_id="fi_gibtsnicht")["status"] == "fehler"


def test_zusammenfuehren_nimmt_namen_schreibweisen_und_kinder_mit(db):
    ziel = fs.firma_anlegen(db, "Neu GmbH", aliase=["N-Gruppe"])["firma"]
    quelle = fs.firma_anlegen(db, "Alt AG", aliase=["A-Gruppe"])["firma"]
    kind = fs.firma_anlegen(db, "Kind Beispiel", mutterfirma_id=quelle["id"])["firma"]
    r = fs.zusammenfuehren(db, ziel["id"], quelle["id"])
    assert r["status"] == "zusammengefuehrt"
    f = fs.firma_laden(db, ziel["id"])
    assert sorted(a["alias"] for a in f["aliase"]) == ["A-Gruppe", "Alt AG", "N-Gruppe"]
    assert fs.firma_laden(db, quelle["id"]) is None
    assert fs.firma_laden(db, kind["id"])["mutterfirma"]["id"] == ziel["id"]
    assert fs.zusammenfuehren(db, ziel["id"], ziel["id"])["status"] == "fehler"
    assert fs.zusammenfuehren(db, ziel["id"], "fi_gibtsnicht")["status"] == "nicht_gefunden"


def test_zusammenfuehren_von_mutter_und_tochter_hinterlaesst_keinen_kreis(db):
    mutter = fs.firma_anlegen(db, "Mutter Beispiel")["firma"]
    tochter = fs.firma_anlegen(db, "Tochter Beispiel", mutterfirma_id=mutter["id"])["firma"]
    fs.zusammenfuehren(db, mutter["id"], tochter["id"])
    assert fs.firma_laden(db, mutter["id"])["mutterfirma"] is None


def test_loeschen_entfernt_nur_den_stammsatz(db):
    aid = _app(db, "Alt AG")
    f = fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])["firma"]
    kind = fs.firma_anlegen(db, "Kind Beispiel", mutterfirma_id=f["id"])["firma"]
    assert fs.firma_loeschen(db, f["id"])["status"] == "geloescht"
    assert fs.firma_laden(db, f["id"]) is None and fs.aufloesen(db, "Alt AG")["firma"] is None
    assert fs.firma_laden(db, kind["id"])["mutterfirma"] is None
    assert db.get_application(aid)["company"] == "Alt AG", "die Bewerbung ist unberuehrt"
    assert db.connect().execute("SELECT COUNT(*) FROM company_aliases").fetchone()[0] == 0


def test_alias_entfernen_nur_bei_der_richtigen_firma(db):
    a = fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])["firma"]
    b = fs.firma_anlegen(db, "Beispiel Handel")["firma"]
    alias_id = a["aliase"][0]["id"]
    assert fs.alias_entfernen(db, b["id"], alias_id)["status"] == "nicht_gefunden", "nicht ueber die Firma eines anderen"
    assert fs.alias_entfernen(db, a["id"], "x")["status"] == "fehler"
    assert fs.alias_entfernen(db, a["id"], alias_id)["status"] == "entfernt"


def test_felder_setzen_kennt_nur_branche_standorte_notizen(db):
    f = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    r = fs.firma_bearbeiten(db, f["id"], branche="Handel", notizen="Ansprechpartner wechselt oft")
    assert r["firma"]["branche"] == "Handel" and r["firma"]["notizen"].startswith("Ansprechpartner")
    assert fs.firma_bearbeiten(db, f["id"], name="x")["status"] == "fehler", "der Name hat seinen eigenen Weg"
    assert fs.firma_bearbeiten(db, "fi_gibtsnicht", branche="x")["status"] == "nicht_gefunden"


# ── Vorschläge: nur nach Bestätigung ─────────────────────────────────────────────────────────────

def _bestand_mit_schreibweisen(db):
    _app(db, "Acme Solutions GmbH")
    _app(db, "ACME Solutions")
    _app(db, "Acme-Solutions", titel="Zweite")
    db.add_contact({"full_name": "Erika Muster", "company": "Acme Solutions AG"})
    _app(db, "Beispiel Handel")                       # nur eine Schreibweise: kein Vorschlag


def test_vorschlaege_nennen_nur_firmen_mit_mehreren_schreibweisen(db):
    _bestand_mit_schreibweisen(db)
    v = fs.vorschlaege(db)
    assert v["anzahl"] == 1
    e = v["vorschlaege"][0]
    assert e["art"] == "neu" and e["vorschlag_id"].startswith("v_") and e["vorkommen"] == 4
    assert sorted(e["schreibweisen"]) == ["ACME Solutions", "Acme Solutions AG", "Acme Solutions GmbH", "Acme-Solutions"]
    assert e["name"] == "Acme Solutions GmbH" or e["name"] in e["schreibweisen"]
    assert fs.firmen_liste(db) == [], "ein Vorschlag legt nichts an"


def test_die_kennung_eines_vorschlags_ist_stabil(db):
    _bestand_mit_schreibweisen(db)
    a = fs.vorschlaege(db)["vorschlaege"][0]["vorschlag_id"]
    _app(db, "Noch Eine Firma")
    assert fs.vorschlaege(db)["vorschlaege"][0]["vorschlag_id"] == a


def test_ohne_bestaetigung_aendert_das_anwenden_nichts(db):
    _bestand_mit_schreibweisen(db)
    vid = fs.vorschlaege(db)["vorschlaege"][0]["vorschlag_id"]
    r = fs.vorschlaege_anwenden(db, [vid])
    assert r["status"] == "vorschau" and r["anzahl"] == 1 and "Bestätige" in r["text"]
    assert fs.firmen_liste(db) == []
    assert fs.vorschlaege_anwenden(db, [])["status"] == "fehler"
    assert fs.vorschlaege_anwenden(db, ["v_gibtsnicht"])["status"] == "fehler"


def test_mit_bestaetigung_wird_angelegt_und_der_bestand_bleibt_text(db):
    _bestand_mit_schreibweisen(db)
    vorher = sorted(a["company"] for a in db.get_applications())
    vid = fs.vorschlaege(db)["vorschlaege"][0]["vorschlag_id"]
    r = fs.vorschlaege_anwenden(db, [vid], bestaetigt=True)
    assert r["status"] == "angewendet" and len(r["angelegt"]) == 1, r
    liste = fs.firmen_liste(db)
    assert len(liste) == 1 and liste[0]["aliase"] == [], "gleiche Namensformen braucht der Stammsatz nicht einzeln zu speichern"
    assert fs.aufloesen(db, "ACME Solutions")["firma"]["name"] == "Acme Solutions GmbH"
    assert sorted(a["company"] for a in db.get_applications()) == vorher, "Bewerbungen sind unveraendert"
    assert fs.vorschlaege(db)["anzahl"] == 0, "angewendet heisst: kein Vorschlag mehr"
    assert fs.vorschlaege_anwenden(db, [vid], bestaetigt=True)["status"] == "fehler", "zweimal anwenden legt nichts doppelt an"


def test_eine_neue_schreibweise_zu_einer_bekannten_firma_wird_als_ergaenzung_vorgeschlagen(db):
    _bestand_mit_schreibweisen(db)
    fs.vorschlaege_anwenden(db, [fs.vorschlaege(db)["vorschlaege"][0]["vorschlag_id"]], bestaetigt=True)
    _app(db, "Acme Solutions Hamburg")                  # der bekannte Name steht als Wortfolge darin: Vorschlag, nie Zuordnung
    db.add_contact({"full_name": "Max Muster", "company": "Acme.Solutions"})   # dieselbe Namensform ohne Trennzeichen: schon zugeordnet
    v = fs.vorschlaege(db)
    ergaenzungen = [e for e in v["vorschlaege"] if e["art"] == "ergaenzung"]
    assert len(ergaenzungen) == 1 and ergaenzungen[0]["ergaenzt_firma"]["name"] == "Acme Solutions GmbH"
    assert ergaenzungen[0]["neue_schreibweisen"] == ["Acme Solutions Hamburg"] and ergaenzungen[0]["sicherheit"] == "mittel"
    r = fs.vorschlaege_anwenden(db, [ergaenzungen[0]["vorschlag_id"]], bestaetigt=True)
    assert r["status"] == "angewendet" and r["ergaenzt"] == ["Acme Solutions Hamburg"], r
    assert len(fs.firmen_liste(db)) == 1
    assert fs.aufloesen(db, "Acme Solutions Hamburg")["firma"]["name"] == "Acme Solutions GmbH"


# ── Der Stammsatz wirkt auf das Lesen ───────────────────────────────────────────────────────────────

def test_ohne_stammsatz_findet_firma_kontext_einen_frueheren_namen_nicht_mit_stammsatz_schon(db):
    _app(db, "Alt AG", titel="Einkauf")
    assert [b for b in fb.bezuege(db, "Neu GmbH")["bezuege"] if b["quelle"] == "bewerbung"] == []
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    r = fb.bezuege(db, "Neu GmbH")
    treffer = [b for b in r["bezuege"] if b["quelle"] == "bewerbung"]
    assert len(treffer) == 1 and treffer[0]["name"] == "Alt AG" and treffer[0]["via"] == "schreibweise"
    assert r["stammsatz"]["name"] == "Neu GmbH" and "Alt AG" in r["schreibweisen"]
    # und umgekehrt: wer den alten Namen sucht, landet beim Stammsatz
    assert fb.bezuege(db, "Alt AG")["stammsatz"]["name"] == "Neu GmbH"


def test_ein_treffer_unter_dem_eigenen_namen_hat_kein_via(db):
    _app(db, "Neu GmbH")
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    treffer = [b for b in fb.bezuege(db, "Neu GmbH")["bezuege"] if b["quelle"] == "bewerbung"]
    assert len(treffer) == 1 and "via" not in treffer[0]


def test_der_stammsatz_findet_auch_lebenslauf_kontakt_projekt_und_notizen(db):
    db.add_position({"company": "Alt AG", "title": "Sachbearbeiterin", "start_date": "2016-01", "end_date": "2020-01"})
    db.add_contact({"full_name": "Erika Muster", "company": "Alt AG", "position": "Leitung"})
    _app(db, "Beispiel Vermittlung", notizen="Der Kunde ist die Zeta Werke GmbH in Hamburg.")
    fs.firma_anlegen(db, "Zeta Werke GmbH", aliase=["Alt AG"])
    rollen = fb.bezuege(db, "Zeta Werke GmbH")["rollen"]
    assert rollen.get("arbeitgeber_frueher") == 1 and rollen.get("kontakt") == 1 and rollen.get("in_notizen_erwaehnt") == 1


def test_konzern_mutter_und_tochter_werden_gefunden_und_gewarnt_nicht_verschmolzen(db):
    mutter = fs.firma_anlegen(db, "Konzern Beispiel")["firma"]
    fs.firma_anlegen(db, "Tochter Beispiel", mutterfirma_id=mutter["id"])
    _app(db, "Tochter Beispiel", titel="Planer", status="interview")
    r = fb.bezuege(db, "Konzern Beispiel")
    treffer = [b for b in r["bezuege"] if b["quelle"] == "bewerbung"]
    assert len(treffer) == 1 and treffer[0]["via"] == "tochterfirma"
    assert any("Tochterfirma Tochter Beispiel" in w and "derselbe Konzern" in w for w in r["warnungen"]), r["warnungen"]
    # die Tochter sieht die Mutter
    _app(db, "Konzern Beispiel", titel="Leitung", status="beworben")
    r2 = fb.bezuege(db, "Tochter Beispiel")
    assert any("Mutterfirma Konzern Beispiel" in w for w in r2["warnungen"]), r2["warnungen"]
    # sie sind getrennte Firmen: beide Treffer stehen im Bestand, kein Zusammenzaehlen als „mehrere Wege bei derselben Firma“
    assert not any("DOPPELVORSTELLUNG" in w for w in r2["warnungen"])


def test_eine_laufende_bewerbung_ueber_den_frueheren_namen_loest_die_doppelvorstellung_aus(db):
    _app(db, "Beispiel Vermittlung", titel="Planer", status="interview", endkunde="Alt AG", vermittler="Beispiel Vermittlung")
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    r = fb.bezuege(db, "Neu GmbH")
    assert any("Laufende Vorstellung über" in w for w in r["warnungen"]), r["warnungen"]


# ── firma_kontext (das Werkzeug) und die Stammsatz-Werkzeuge ───────────────────────────────────────

@pytest.fixture
def werkzeug(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("firmen-test")
    register_all(mcp, db, logging.getLogger("firmen-test"))

    def aufruf(werkzeugname, /, **args):
        async def _run():
            tool = await mcp.get_tool(werkzeugname)
            res = await tool.run(args)
            return res.structured_content if hasattr(res, "structured_content") else res
        return asyncio.run(_run())
    return aufruf


def test_firma_kontext_zeigt_den_stammsatz_und_findet_ueber_ihn(db, werkzeug):
    _app(db, "Alt AG", titel="Einkauf", status="abgelehnt")
    db.save_jobs([{"hash": "h1", "title": "Planer", "company": "Alt AG", "url": "https://beispiel.example/1", "source": "bundesagentur",
                   "description": "Beschreibung " * 20, "score": 10, "found_at": "2026-10-01T00:00:00"}])
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"], branche="Handel")
    erg = werkzeug("firma_kontext", firmenname="Neu GmbH")
    assert erg["gefunden"] is True
    assert erg["stammsatz"]["name"] == "Neu GmbH" and erg["stammsatz"]["aliase"] == ["Alt AG"] and erg["stammsatz"]["branche"] == "Handel"
    assert [b["via"] for b in erg["bewerbungen"]] == ["schreibweise"]
    assert [s["via"] for s in erg["aktive_stellen"]] == ["schreibweise"]


def test_firma_kontext_nennt_mehrdeutige_firmen_statt_zu_raten(db, werkzeug):
    fs.firma_anlegen(db, "Muster Energie GmbH")
    fs.firma_anlegen(db, "Muster Medizin GmbH")
    _app(db, "Muster Energie GmbH")
    erg = werkzeug("firma_kontext", firmenname="Muster")
    assert "stammsatz" not in erg and sorted(erg["stammsatz_mehrdeutig"]) == ["Muster Energie GmbH", "Muster Medizin GmbH"]
    assert "rät hier nicht" in erg["stammsatz_hinweis"]
    assert erg["gefunden"] is True, "die Stufe-1-Suche laeuft trotzdem"


def test_firma_kontext_ohne_stammsatz_verhaelt_sich_wie_vorher(db, werkzeug):
    _app(db, "Beispiel Handel", status="abgelehnt")
    erg = werkzeug("firma_kontext", firmenname="Beispiel")
    assert erg["gefunden"] is True and "stammsatz" not in erg and "stammsatz_mehrdeutig" not in erg
    assert "via" not in erg["bewerbungen"][0]


def test_stamm_werkzeuge_anzeigen_und_vorschlaege(db, werkzeug):
    _bestand_mit_schreibweisen(db)
    leer = werkzeug("firmen_stamm_anzeigen")
    assert leer["anzahl"] == 0 and leer["offene_vorschlaege"] == 1 and "firmen_vorschlaege_anzeigen" in leer["hinweis"]
    v = werkzeug("firmen_vorschlaege_anzeigen")
    assert v["anzahl"] == 1
    r = werkzeug("firmen_stamm_bearbeiten", aktion="vorschlaege_anwenden", auswahl=[v["vorschlaege"][0]["vorschlag_id"]])
    assert r["status"] == "vorschau"
    r = werkzeug("firmen_stamm_bearbeiten", aktion="vorschlaege_anwenden", auswahl=[v["vorschlaege"][0]["vorschlag_id"]], bestaetigung=True)
    assert r["status"] == "angewendet"
    eine = werkzeug("firmen_stamm_anzeigen", firma="Acme")
    assert eine["status"] == "ok" and eine["firma"]["name"] == "Acme Solutions GmbH" and "firma_kontext" in eine["historie"]
    nach_id = werkzeug("firmen_stamm_anzeigen", firma=eine["firma"]["id"])
    assert nach_id["firma"]["id"] == eine["firma"]["id"]
    assert werkzeug("firmen_stamm_anzeigen", firma="Gibt Es Nicht")["status"] == "nicht_gefunden"


def test_stamm_werkzeug_loeschen_und_zusammenfuehren_brauchen_die_bestaetigung(db, werkzeug):
    a = fs.firma_anlegen(db, "Neu GmbH")["firma"]
    b = fs.firma_anlegen(db, "Alt AG", aliase=["A-Gruppe"])["firma"]
    r = werkzeug("firmen_stamm_bearbeiten", aktion="zusammenfuehren", firma_id=a["id"], quelle_id=b["id"])
    assert r["status"] == "bestaetigung_noetig" and "naechster_schritt" in r and fs.firma_laden(db, b["id"]) is not None
    r = werkzeug("firmen_stamm_bearbeiten", aktion="zusammenfuehren", firma_id=a["id"], quelle_id=b["id"], bestaetigung=True)
    assert r["status"] == "zusammengefuehrt"
    r = werkzeug("firmen_stamm_bearbeiten", aktion="loeschen", firma_id=a["id"])
    assert r["status"] == "bestaetigung_noetig" and fs.firma_laden(db, a["id"]) is not None
    r = werkzeug("firmen_stamm_bearbeiten", aktion="loeschen", firma_id=a["id"], bestaetigung=True)
    assert r["status"] == "geloescht" and fs.firma_laden(db, a["id"]) is None


def test_stamm_werkzeug_pflege_ohne_bestaetigung(db, werkzeug):
    f = werkzeug("firmen_stamm_bearbeiten", aktion="anlegen", name="Neu GmbH", aliase=["Alt AG"], branche="Handel")["firma"]
    assert werkzeug("firmen_stamm_bearbeiten", aktion="alias_hinzufuegen", firma_id=f["id"], alias="N-Gruppe", art="kurzform")["status"] == "hinzugefuegt"
    m = werkzeug("firmen_stamm_bearbeiten", aktion="anlegen", name="Konzern Beispiel")["firma"]
    assert werkzeug("firmen_stamm_bearbeiten", aktion="mutterfirma_setzen", firma_id=f["id"], mutterfirma_id=m["id"])["status"] == "gesetzt"
    assert werkzeug("firmen_stamm_bearbeiten", aktion="felder_setzen", firma_id=f["id"], notizen="Notiz")["firma"]["notizen"] == "Notiz"
    assert werkzeug("firmen_stamm_bearbeiten", aktion="felder_setzen", firma_id=f["id"])["status"] == "fehler"
    assert werkzeug("firmen_stamm_bearbeiten", aktion="umbenennen", firma_id=f["id"], name="Neue GmbH")["status"] == "umbenannt"
    alias = fs.firma_laden(db, f["id"])["aliase"][0]["id"]
    assert werkzeug("firmen_stamm_bearbeiten", aktion="alias_entfernen", firma_id=f["id"], alias_id=alias)["status"] == "entfernt"
    erg = werkzeug("firmen_stamm_bearbeiten", aktion="gibt-es-nicht")
    assert erg["status"] == "fehler" and "zusammenfuehren" in erg["erlaubt"]


def test_die_werkzeuge_sind_eingeordnet(db):
    import inspect
    from bewerbungs_assistent.services import werkzeug_schutz
    from bewerbungs_assistent.tools import firmen_stamm as modul
    assert werkzeug_schutz.ZWEISTUFIG["firmen_stamm_bearbeiten"] == "bestaetigung"
    assert werkzeug_schutz.annotations_fuer("firmen_stamm_anzeigen") == {"readOnlyHint": True}
    assert werkzeug_schutz.annotations_fuer("firmen_vorschlaege_anzeigen") == {"readOnlyHint": True}
    assert "bestaetigung: bool = False" in inspect.getsource(modul)
