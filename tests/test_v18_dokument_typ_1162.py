"""#1162: Der Typ eines einzelnen Dokuments lässt sich von Hand ändern — Dashboard und Werkzeug, EIN Dienst.

Vorher: `PUT /api/document/{id}/doc-type` existierte, wurde aber von keiner Oberfläche aufgerufen (und nahm jeden Text als Typ);
im Chat gab es nur die Sammelkorrektur `dokument_typen_nachziehen`. Ein falsch erkanntes Dokument ließ sich nicht richtigstellen,
obwohl der Typ entscheidet, wohin es gehört und ob es in der Historie einer Firma auftaucht.

Hier: der Dienst (`document_handlers.typ_setzen`), die Endpunkte (Auswahl und Setzen), das Werkzeug und der Praxisfall aus dem
Issue — „sonstiges“ nach „absage“, danach steht das Dokument in der Historie der Firma (#1080).
"""
import logging
import os

import pytest

from bewerbungs_assistent.services import document_handlers as dh


@pytest.fixture
def db(tmp_path):
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "typ.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Erika Musterfrau"})
    yield d
    d.close()


def _dok(db, name="schreiben.pdf", typ="sonstiges", text="", app=None):
    return db.add_document({"filename": name, "doc_type": typ, "extracted_text": text, "linked_application_id": app})


# ══ Der Dienst ═══════════════════════════════════════════════════════════════════════════

def test_die_auswahl_nennt_jeden_erlaubten_typ_mit_namen_und_beschreibung():
    auswahl = dh.typen_fuer_auswahl()
    typen = [z["typ"] for z in auswahl]
    assert typen == dh.erlaubte_typen() and len(set(typen)) == len(typen)
    assert set(dh.KNOWN_TYPES) <= set(typen) and {"lebenslauf_vorlage", "anschreiben_vorlage"} <= set(typen)
    for zeile in auswahl:
        assert zeile["name"] and "_" not in zeile["name"], zeile
        assert isinstance(zeile["beschreibung"], str)


def test_jeder_bekannte_typ_hat_einen_deutschen_namen():
    """Sonst stuende in der Auswahl der rohe Schluessel (`vermittler_korrespondenz`)."""
    assert set(dh.TYP_NAMEN) == set(dh.KNOWN_TYPES)
    assert all(n and "_" not in n for n in dh.TYP_NAMEN.values())
    assert dh.typ_name("absage") == "Absage" and dh.typ_name(None) == "Dokument" and dh.typ_name("etwas_altes") == "etwas_altes"


def test_der_typ_wird_gesetzt_und_nur_er(db):
    bew = db.add_application({"company": "Musterfirma GmbH", "title": "Planer", "status": "beworben"})
    did = _dok(db, text="Leider müssen wir Ihnen absagen.", app=bew)
    erg = dh.typ_setzen(db, did, "absage", profile_id=db.get_active_profile_id())
    assert erg["status"] == "geaendert" and (erg["typ_alt"], erg["typ_neu"], erg["typ_name"]) == ("sonstiges", "absage", "Absage")
    assert erg["verknuepft_mit_bewerbung"] is True
    doc = db.get_document(did)
    assert doc["doc_type"] == "absage"
    assert doc["linked_application_id"] == bew, "die Verknuepfung mit der Bewerbung bleibt"
    assert doc["extracted_text"] == "Leider müssen wir Ihnen absagen.", "der Text bleibt"
    assert doc["filename"] == "schreiben.pdf"


def test_der_dienst_gibt_das_profil_an_beide_datenbankaufrufe_weiter(db):
    """Jede Schicht fuer sich: sowohl das Lesen als auch das Schreiben tragen das Profil (eine faengt die andere sonst ab)."""
    aufrufe = []

    class Spion:
        def __init__(self, echt):
            self.echt = echt

        def get_document(self, *a, **kw):
            aufrufe.append(("lesen", kw.get("profile_id")))
            return self.echt.get_document(*a, **kw)

        def update_document_type(self, *a, **kw):
            aufrufe.append(("schreiben", kw.get("profile_id")))
            return self.echt.update_document_type(*a, **kw)

    did = _dok(db)
    pid = db.get_active_profile_id()
    assert dh.typ_setzen(Spion(db), did, "absage", profile_id=pid)["status"] == "geaendert"
    assert aufrufe == [("lesen", pid), ("schreiben", pid)]


def test_derselbe_typ_aendert_nichts(db):
    did = _dok(db, typ="absage")
    erg = dh.typ_setzen(db, did, "absage")
    assert erg["status"] == "unveraendert" and erg["typ_alt"] == erg["typ_neu"] == "absage"


@pytest.mark.parametrize("typ", ["", "   ", "Absage", "absagen", "sonstiges ' OR 1=1 --", "../etc", None, "x" * 500])
def test_ein_unbekannter_typ_wird_abgelehnt_und_nennt_die_erlaubten(db, typ):
    did = _dok(db, typ="sonstiges")
    erg = dh.typ_setzen(db, did, typ)
    assert erg["status"] == "unbekannter_typ" and "fehler" in erg
    assert erg["erlaubte_typen"] == dh.erlaubte_typen()
    assert db.get_document(did)["doc_type"] == "sonstiges", "ein Tippfehler legt keinen neuen Typ an"


def test_ein_unbekanntes_dokument_ist_nicht_gefunden(db):
    erg = dh.typ_setzen(db, "gibt-es-nicht", "absage")
    assert erg["status"] == "nicht_gefunden"


def test_ein_dokument_eines_anderen_profils_bleibt_unberuehrt(db):
    erstes = db.get_active_profile_id()
    did = _dok(db)
    zweites = db.create_profile("Zweites Profil")
    assert zweites != erstes
    erg = dh.typ_setzen(db, did, "absage", profile_id=zweites)
    assert erg["status"] == "nicht_gefunden"
    assert db.get_document(did)["doc_type"] == "sonstiges"
    # und im eigenen Profil geht es
    assert dh.typ_setzen(db, did, "absage", profile_id=erstes)["status"] == "geaendert"


def test_der_praxisfall_aus_dem_issue_die_historie_der_firma_stimmt_danach(db):
    """„sonstiges“ nach „absage“: vorher steht das Dokument nicht in der Historie der Firma, danach schon (#1080)."""
    from bewerbungs_assistent.services import firmen_bezuege
    bew = db.add_application({"company": "Musterfirma GmbH", "title": "Planer", "status": "beworben"})
    did = _dok(db, name="antwort.pdf", text="Sehr geehrte Frau Musterfrau, die Musterfirma GmbH sagt ab.", app=bew)

    def dokumente():
        return [b for b in firmen_bezuege.bezuege(db, "Musterfirma GmbH")["bezuege"] if b.get("quelle") == "dokument"]

    assert dokumente() == [], "ein Dokument vom Typ „sonstiges“ steht in keiner Firmen-Historie"
    assert dh.typ_setzen(db, did, "absage")["status"] == "geaendert"
    treffer = dokumente()
    assert len(treffer) == 1 and treffer[0]["dokument_id"] == did and treffer[0]["typ"] == "absage"
    # und zurueck: wieder draussen
    assert dh.typ_setzen(db, did, "sonstiges")["status"] == "geaendert"
    assert dokumente() == []


# ══ Dashboard ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def client(db):
    import bewerbungs_assistent.dashboard as dash
    alt = dash._db
    dash._db = db
    from fastapi.testclient import TestClient
    yield TestClient(dash.app)
    dash._db = alt


def test_die_auswahl_kommt_vom_server_mit_namen(client):
    j = client.get("/api/document-types").json()
    typen = {z["typ"]: z for z in j["typen"]}
    assert typen["absage"]["name"] == "Absage" and typen["sonstiges"]["name"] == "Sonstiges"
    assert "lebenslauf_vorlage" in typen
    assert list(typen) == dh.erlaubte_typen()


def test_der_endpunkt_stellt_den_typ_um(client, db):
    did = _dok(db)
    r = client.put(f"/api/document/{did}/doc-type", json={"doc_type": "absage"})
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok" and j["doc_type"] == "absage" and j["typ_name"] == "Absage" and j["ergebnis"] == "geaendert"
    assert db.get_document(did)["doc_type"] == "absage"


def test_der_endpunkt_nimmt_keinen_unbekannten_typ_mehr(client, db):
    """Vorher nahm er jeden Text als Typ (und `{}` hiess still „sonstiges“)."""
    did = _dok(db, typ="anschreiben")
    r = client.put(f"/api/document/{did}/doc-type", json={"doc_type": "erfunden"})
    assert r.status_code == 400 and r.json()["erlaubte_typen"] == dh.erlaubte_typen()
    assert client.put(f"/api/document/{did}/doc-type", json={}).status_code == 400
    assert db.get_document(did)["doc_type"] == "anschreiben"


def test_der_endpunkt_kennt_ein_unbekanntes_dokument_nicht(client):
    assert client.put("/api/document/gibt-es-nicht/doc-type", json={"doc_type": "absage"}).status_code == 404


# ══ Werkzeug ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def werkzeuge(db):
    from bewerbungs_assistent.tools import dokumente
    gesammelt = {}

    class _Mcp:
        def tool(self, *a, **k):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

    dokumente.register(_Mcp(), db, logging.getLogger("test"))
    return gesammelt


def test_das_werkzeug_nutzt_denselben_dienst(werkzeuge, db):
    did = _dok(db)
    erg = werkzeuge["dokument_typ_setzen"](did, "zeugnis")
    assert erg["status"] == "geaendert" and erg["typ_neu"] == "zeugnis" and "Verknüpfung" in erg["hinweis"]
    assert db.get_document(did)["doc_type"] == "zeugnis"


def test_das_werkzeug_nennt_bei_einem_unbekannten_typ_die_erlaubten(werkzeuge, db):
    did = _dok(db)
    erg = werkzeuge["dokument_typ_setzen"](did, "bescheinigung")
    assert "fehler" in erg and "status" not in erg and "absage" in erg["erlaubte_typen"]
    assert db.get_document(did)["doc_type"] == "sonstiges"


def test_das_werkzeug_meldet_ein_fehlendes_dokument(werkzeuge):
    erg = werkzeuge["dokument_typ_setzen"]("gibt-es-nicht", "absage")
    assert erg == {"fehler": "Dokument nicht gefunden."}


def test_die_typen_uebersicht_verweist_auf_das_werkzeug_statt_zu_verneinen(werkzeuge, db):
    erg = werkzeuge["dokument_typen_anzeigen"]()
    assert "dokument_typ_setzen" in erg["hinweis"] and "nicht von Hand" not in erg["hinweis"]
    zeilen = {t["typ"]: t for t in erg["typen"]}
    assert zeilen["absage"]["name"] == "Absage"


def test_das_werkzeug_steht_im_echten_server(tmp_path):
    """Ein Schutz zaehlt erst, wenn er aufgerufen wird: das Werkzeug ist wirklich registriert (nicht nur im Test-Doppel)."""
    import test_mcp_registry as reg

    mcp, d = reg._build_test_server(tmp_path)
    try:
        tools, _, _ = reg._collect_names(mcp)
        assert "dokument_typ_setzen" in tools
    finally:
        d.close()
        os.environ.pop("BA_DATA_DIR", None)
