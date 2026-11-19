"""#1412: Mail-Eingang behaelt Termin, Status und Dokumenttyp (Hotfix 1.8.8).

Alle Daten sind erfunden; jede Probe laeuft auf einer isolierten Datenbank.
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Mail Eingang", "email": "bewerber@example.com"})
    import bewerbungs_assistent.dashboard as dash
    dash._db = d
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _client():
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    return TestClient(dash.app)


def eml(betreff, text, absender="Erika Beispiel <erika@personal.example.org>",
        roh=False, anhang_ics=None):
    """Baut eine .eml. roh=True: Kopfzeilen als unkodiertes UTF-8 (wie manche
    Programme sie speichern), sonst RFC-2047-kodiert."""
    kopf = [f"From: {absender}", "To: bewerber@example.com",
            "Date: Mon, 16 Nov 2026 09:00:00 +0100"]
    if roh:
        kopf.append(f"Subject: {betreff}")
    else:
        import email.header
        kopf.append("Subject: " + email.header.Header(betreff, "utf-8").encode())
    kopf += ["MIME-Version: 1.0", "Content-Type: text/plain; charset=utf-8",
             "Content-Transfer-Encoding: 8bit"]
    return ("\r\n".join(kopf) + "\r\n\r\n" + text + "\r\n").encode("utf-8")


EINLADUNG = ("Guten Tag,\n\nwir laden Sie herzlich zum Vorstellungsgespräch "
             "am 01.12.2099 um 10:00 Uhr per Videocall ein.\n\nMit freundlichen Grüßen")
ABSAGE = ("Guten Tag,\n\nleider müssen wir Ihnen mitteilen, dass wir uns für "
          "andere Bewerber entschieden haben. Wir bedauern, Ihnen eine Absage erteilen zu müssen.")


ABSAGE_KNAPP = ("Guten Tag,"+chr(10)*2+"die Stelle wurde besetzt, wir können Sie "
                "nicht weiter berücksichtigen. Alles Gute.")


def _bewerbung(db, titel="Fachkraft Lagerlogistik", firma="Musterbau GmbH", **extra):
    return db.add_application({"title": titel, "company": firma,
                               "status": "beworben", **extra})


def _hochladen(client, inhalt, name="mail.eml"):
    r = client.post("/api/emails/upload", files={"file": (name, inhalt, "message/rfc822")})
    return r


# ── D3: Roh-UTF-8 in Kopfzeilen ────────────────────────────────────────

@pytest.mark.parametrize("roh", [True, False])
def test_d3_kopfzeilen_roh_und_kodiert(db, roh):
    r = _hochladen(_client(), eml("Ihre Bewerbung als Fachkraft für Lagerlogistik",
                                  EINLADUNG, roh=roh))
    assert r.status_code == 200, r.text
    assert "Lagerlogistik" in r.json()["parsed"]["subject"]
    assert "für" in r.json()["parsed"]["subject"]


def test_d3_unbekannter_zeichensatz_stuerzt_nicht_ab():
    from bewerbungs_assistent.services.email_service import _decode_header
    import email.header
    # unbekannter Zeichensatz in einem kodierten Wort
    assert "abc" in _decode_header("=?x-gibtesnicht?q?abc?=")
    assert "Gespräch" in _decode_header("Gespräch")


# ── D1: Termin geht bei spaeter Zuordnung nicht verloren ────────────────

def test_d1_termin_nach_spaeter_zuordnung(db):
    app_id = _bewerbung(db)
    r = _hochladen(_client(), eml("Einladung zum Gespräch", EINLADUNG))
    assert r.status_code == 200
    j = r.json()
    assert j["match"]["application"] is None, "Testvoraussetzung: keine Zuordnung"
    assert db.get_meetings_for_application(app_id) == []
    c = _client().post(f"/api/emails/{j['email_id']}/confirm-match",
                       json={"application_id": app_id})
    assert c.status_code == 200
    termine = db.get_meetings_for_application(app_id)
    assert len(termine) == 1, termine
    assert "2099-12-01" in str(termine[0]["meeting_date"])


def test_d1_zweite_zuordnung_legt_keinen_zweiten_termin_an(db):
    app_id = _bewerbung(db)
    j = _hochladen(_client(), eml("Einladung zum Gespräch", EINLADUNG)).json()
    for _ in range(2):
        _client().post(f"/api/emails/{j['email_id']}/confirm-match",
                       json={"application_id": app_id})
    termine = db.get_meetings_for_application(app_id)
    assert len(termine) == 1


# ── D4: Dokumenttyp aus Inhalt, nicht aus dem Namen ─────────────────────

def _dokument_hochladen(client, inhalt, name, app_id=None):
    data = {"link_application_id": app_id} if app_id else {}
    return client.post("/api/documents/upload", data=data,
                       files={"file": (name, inhalt, "message/rfc822")})


def test_d4_absage_mit_irrefuehrendem_namen_ist_absage(db):
    r = _dokument_hochladen(_client(), eml("Ihre Bewerbung als Fachkraft", ABSAGE_KNAPP),
                            "Ihre Bewerbung als Fachkraft Lagerlogistik.eml")
    assert r.status_code == 200, r.text
    assert r.json()["doc_type"] == "absage"


def test_d4_einladung_ohne_das_wort_im_namen(db):
    r = _dokument_hochladen(_client(), eml("Ihre Bewerbung", EINLADUNG), "Nachricht.eml")
    assert r.json()["doc_type"] == "interview_einladung"


def test_d4_unklarer_inhalt_ist_sonstiges_nicht_anschreiben(db):
    r = _dokument_hochladen(_client(), eml("Hallo", "Kurze Frage zum Wetter."),
                            "Anschreiben Lagerlogistik.eml")
    assert r.json()["doc_type"] == "sonstiges"
    assert r.json()["mail_erkannt"]["dokumenttyp_sicher"] is False


# ── D5: Meldung nennt Termin und Status, Status nur auf Bestaetigung ────

def test_d5_absage_im_dialog_wird_angeboten_nicht_gesetzt(db):
    app_id = _bewerbung(db)
    r = _dokument_hochladen(_client(), eml("Ihre Bewerbung als Fachkraft", ABSAGE),
                            "mail.eml", app_id=app_id)
    j = r.json()
    assert j["mail_erkannt"]["angebot"] == {"status": "abgelehnt", "name": "Absage"}
    assert db.get_application(app_id)["status"] == "beworben", "nie still gesetzt"
    # erst auf Bestaetigung (der Dialog ruft den Status-Weg)
    s = _client().put(f"/api/applications/{app_id}/status", json={"status": "abgelehnt"})
    assert s.status_code == 200
    assert db.get_application(app_id)["status"] == "abgelehnt"


def test_d5_einladung_nennt_den_angelegten_termin(db):
    app_id = _bewerbung(db)
    j = _dokument_hochladen(_client(), eml("Einladung", EINLADUNG), "mail.eml",
                            app_id=app_id).json()
    assert j["mail_erkannt"]["termine"] == 1
    assert j["mail_erkannt"]["angebot"]["status"] == "interview"
    assert len(db.get_meetings_for_application(app_id)) == 1


def test_d5_gleicher_status_wird_nicht_angeboten(db):
    app_id = _bewerbung(db)
    assert _client().put(f"/api/applications/{app_id}/status",
                         json={"status": "interview"}).status_code == 200
    j = _dokument_hochladen(_client(), eml("Einladung", EINLADUNG), "mail.eml",
                            app_id=app_id).json()
    assert db.get_application(app_id)["status"] == "interview"
    assert j["mail_erkannt"]["angebot"] is None


# ── D7: ein Parametername fuer die Aufgaben-ID ──────────────────────────

def _tasks(db):
    import logging
    from bewerbungs_assistent.tools.tasks import register

    class FakeMCP:
        def __init__(self):
            self.tools = {}

        def tool(self, name=None, **_kw):
            def deko(fn):
                self.tools[name or fn.__name__] = fn
                return fn
            return deko
    m = FakeMCP()
    register(m, db, logging.getLogger("test"))
    return m.tools


def test_d7_hinweis_nennt_einen_echten_parameter(db):
    import inspect
    import re
    t = _tasks(db)
    antwort = t["todo_anlegen"](titel="Unterlagen prüfen")
    param = re.search(r"todo_erledigen\((\w+)", antwort["hinweis"]).group(1)
    assert param in inspect.signature(t["todo_erledigen"]).parameters
    assert antwort[param]


def test_d7_task_id_wird_als_alias_angenommen(db):
    t = _tasks(db)
    tid = t["todo_anlegen"](titel="Rückruf")["todo_id"]
    erg = t["todo_erledigen"](task_id=tid, notiz="erledigt")
    assert erg["status"] == "erledigt"


def test_d7_ohne_id_kommt_eine_klare_meldung(db):
    assert "todo_id" in _tasks(db)["todo_erledigen"]()["fehler"]


# ── D2: Zuordnung ueber Stellentitel und Firmenname ─────────────────────

BETREFF = "Ihre Bewerbung als Fachkraft Lagerlogistik bei Musterbau"


def test_d2_titel_und_firma_im_betreff_ordnen_zu(db):
    app_id = _bewerbung(db)
    _bewerbung(db, titel="Buchhalter", firma="Andere AG")
    j = _hochladen(_client(), eml(BETREFF, EINLADUNG)).json()
    assert j["match"]["application"]["id"] == app_id
    assert len(db.get_meetings_for_application(app_id)) == 1


def test_d2_mehrere_passende_sind_mehrdeutig_und_werden_genannt(db):
    a1 = _bewerbung(db)
    a2 = _bewerbung(db)  # zweite Bewerbung auf dieselbe Stelle
    j = _hochladen(_client(), eml(BETREFF, EINLADUNG)).json()
    assert j["match"]["application"] is None
    assert j["match"]["mehrdeutig"] is True
    assert set(j["match"]["kandidaten"]) == {a1, a2}
    liste = _client().get("/api/emails").json()["emails"]
    assert set(liste[0]["kandidaten"]) == {a1, a2}


def test_d2_nur_titel_ohne_firma_ordnet_nicht_zu(db):
    _bewerbung(db)
    j = _hochladen(_client(), eml("Ihre Bewerbung als Fachkraft Lagerlogistik",
                                  EINLADUNG, absender="X <x@personal.example.org>")).json()
    assert j["match"]["application"] is None
    assert j["match"]["kandidaten"] == []


def test_d2_bestaetigte_schreibweise_aus_dem_firmenstamm(db):
    from bewerbungs_assistent.services import firmen_stamm
    app_id = _bewerbung(db, firma="Musterbau GmbH")
    fid = firmen_stamm.firma_anlegen(db, "Musterbau GmbH")
    fid = fid.get("id") or fid.get("firma", {}).get("id")
    firmen_stamm.alias_hinzufuegen(db, fid, "Baufix")
    j = _hochladen(_client(), eml("Ihre Bewerbung als Fachkraft Lagerlogistik bei Baufix",
                                  EINLADUNG)).json()
    assert j["match"]["application"]["id"] == app_id


def test_d2_archivierte_bewerbung_zaehlt_nicht(db):
    app_id = _bewerbung(db)
    db.update_application_status(app_id, "abgelehnt") if hasattr(db, "update_application_status") else None
    from bewerbungs_assistent.services.email_service import titel_firma_kandidaten
    app = db.get_application(app_id)
    app["status"] = "abgelehnt"
    assert titel_firma_kandidaten({"subject": BETREFF, "sender": ""}, [app]) == []
