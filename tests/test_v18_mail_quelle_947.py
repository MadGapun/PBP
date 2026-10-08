"""Mail-Ordner als Quelle: die Zugangsschicht (#947).

Jede Akzeptanzbedingung des Issues hat hier einen eigenen Test:

  AK 1   Vorgabe AUS                                  → test_im_auslieferungszustand_ist_alles_aus
  AK 2   ohne Aktivierung kein Zugriff                → test_ohne_einschalten_wird_jede_scan_mail_abgewiesen,
                                                         test_pbp_oeffnet_nie_selbst_ein_postfach
  AK 3   aktiv + leere Liste: nichts                  → test_scan_an_aber_liste_leer_liest_nichts
  AK 4   Thread-Nachverfolgung umgeht die Liste nicht → test_eine_antwort_kette_macht_einen_fremden_ordner_nicht_freigegeben
  AK 5   anbieterunabhängig                           → test_die_regel_gilt_fuer_jeden_anbieter_gleich
  AK 6   Zahlen je Ordner                             → test_je_ordner_stehen_letzter_lauf_mails_und_stellen
  AK 7   Abschalten sofort, Hinweis zu den Daten      → test_abschalten_wirkt_sofort_und_nennt_die_importierten_daten
  AK 10  Update ohne Mail-Quelle → bleibt aus         → test_ein_update_von_einer_version_ohne_mail_quelle_laesst_sie_aus
  AK 11  Beta aktiv → stabil nicht still aktiv        → test_eine_in_der_beta_eingeschaltete_quelle_ist_in_stabil_nicht_still_aktiv
  AK 12  nicht übernehmbar → sicherer Zustand + Hinweis → test_eine_nicht_lesbare_einstellung_faellt_auf_den_sicheren_zustand

Kein Test öffnet ein Postfach oder greift auf echte Daten zu: alles läuft gegen eine Wegwerf-Datenbank unter tmp_path.
"""
import json
import os
import re
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bewerbungs_assistent.services import mail_quelle  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent

MANIFEST = {"name": "Mail-Zubringer", "version": "1.0.0", "ingest_api": "^1", "capabilities": ["ingest:email"],
            "beschreibung": "Testplugin"}


@pytest.fixture
def client_db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Test"})
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    from fastapi.testclient import TestClient
    tc = TestClient(dash.app)
    yield tc, db
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture
def schluessel(client_db):
    tc, _ = client_db
    r = tc.post("/api/plugins/pair", json={"manifest": MANIFEST})
    assert r.status_code == 200, r.text
    return {"X-PBP-API-Key": r.json()["api_key"]}


def _mail(betreff="Eingangsbestätigung", html=None, extra_header=None) -> bytes:
    msg = MIMEMultipart("alternative") if html else MIMEText("Hallo, wir haben deine Bewerbung erhalten.", "plain", "utf-8")
    if html:
        msg.attach(MIMEText("Neue Jobs", "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
    msg["Subject"] = betreff
    msg["From"] = "jobs@example.com" if not html else "StepStone <noreply@stepstone.de>"
    msg["To"] = "test@example.com"
    for k, v in (extra_header or {}).items():
        msg[k] = v
    return msg.as_bytes()


def _senden(tc, schluessel, eml=None, **felder):
    return tc.post("/api/v1/ingest/email", files={"file": ("mail.eml", eml or _mail(), "message/rfc822")},
                   data=felder, headers=schluessel)


def _dokumente(db) -> int:
    """Wie viele Dokumente gespeichert sind (Zeilen der Tabelle, alle Profile)."""
    return db.connect().execute("SELECT COUNT(*) FROM documents").fetchone()[0]


# ── AK 1, 10: die Vorgabe ──────────────────────────────────────────────────────────────

def test_im_auslieferungszustand_ist_alles_aus(client_db):
    tc, db = client_db
    u = tc.get("/api/mail-quelle").json()
    assert u["scan_aktiv"] is False and u["wirksam"] is False and u["freigaben"] == [] and u["hinweise"] == []
    assert db.get_setting(mail_quelle.SCHLUESSEL, None) is None, "schon das Lesen legt nichts an"
    assert "immer" in u["push"], "die Antwort erklärt, dass Push ohne Schalter geht"


def test_ein_update_von_einer_version_ohne_mail_quelle_laesst_sie_aus(client_db):
    """AK 10: eine Datenbank aus einer Version, die diese Einstellung nie kannte, hat sie nicht. Das heißt AUS."""
    _, db = client_db
    db.set_setting("irgendeine_alte_einstellung", True)
    assert mail_quelle.wirksam(db) is False
    assert mail_quelle.richtlinie(db) == {"ordner_scan": False, "freigaben": [], "modi": ["push", "scan"],
                                          "hinweis": mail_quelle.richtlinie(db)["hinweis"]}
    assert mail_quelle.pruefe_scan(db, "thunderbird", "", "Jobs")["code"] == "scan_aus"


# ── AK 2, 3: kein Zugriff ohne Aktivierung, nichts bei leerer Liste ────────────────────────────

def test_ohne_einschalten_wird_jede_scan_mail_abgewiesen_und_nichts_gespeichert(client_db, schluessel):
    tc, db = client_db
    vorher = _dokumente(db)
    r = _senden(tc, schluessel, modus="scan", anbieter="thunderbird", ordner="Jobs")
    assert r.status_code == 403 and r.json()["code"] == "scan_aus"
    assert _dokumente(db) == vorher, "abgewiesen heißt: nicht einmal als Dokument gespeichert"


def test_scan_an_aber_liste_leer_liest_nichts(client_db, schluessel):
    tc, db = client_db
    assert tc.post("/api/mail-quelle/scan", json={"an": True, "bestaetigt": True}).json()["status"] == "an"
    vorher = _dokumente(db)
    r = _senden(tc, schluessel, modus="scan", anbieter="thunderbird", ordner="Jobs")
    assert r.status_code == 403 and r.json()["code"] == "whitelist_leer"
    assert _dokumente(db) == vorher
    pol = tc.get("/api/v1/ingest/mail-policy", headers=schluessel).json()
    assert pol["ordner_scan"] is True and pol["freigaben"] == [] and "nichts" in pol["hinweis"]


def test_einschalten_verlangt_die_bestaetigung(client_db):
    tc, db = client_db
    r = tc.post("/api/mail-quelle/scan", json={"an": True})
    assert r.status_code == 400 and r.json()["status"] == "bestaetigung_noetig"
    assert "private Korrespondenz" in r.json()["text"]
    assert tc.get("/api/mail-quelle").json()["einschalten_text"] == r.json()["text"], "die Oberfläche zeigt denselben Wortlaut"
    assert tc.post("/api/mail-quelle/scan", json={"an": True, "bestaetigt": "ja"}).status_code == 400, "nur ein echtes true"
    assert mail_quelle.wirksam(db) is False


def test_pbp_oeffnet_nie_selbst_ein_postfach():
    """AK 2, strukturell: in PBP gibt es keinen Code, der eine Mail-Verbindung aufbaut. Es nimmt nur entgegen."""
    muster = re.compile(r"\b(imaplib|poplib|IMAP4|IMAP4_SSL|POP3|POP3_SSL|smtplib)\b")
    treffer = []
    for p in sorted((WURZEL / "src" / "bewerbungs_assistent").rglob("*.py")):
        if "static" in p.parts:
            continue
        text = p.read_text(encoding="utf-8-sig")
        for n, zeile in enumerate(text.splitlines(), 1):
            if muster.search(zeile) and not zeile.lstrip().startswith(("#", '"', "'")):
                treffer.append(f"{p.name}:{n}: {zeile.strip()[:80]}")
    assert not treffer, treffer


# ── Die Liste: genau, ohne Platzhalter, ohne Unterordner ───────────────────────────────────

def _scharf(tc, ordner="Jobs/Portale", anbieter="thunderbird", konto=""):
    assert tc.post("/api/mail-quelle/scan", json={"an": True, "bestaetigt": True}).status_code == 200
    r = tc.post("/api/mail-quelle/freigaben", json={"anbieter": anbieter, "ordner": ordner, "konto": konto})
    assert r.status_code == 200 and r.json()["status"] == "freigegeben", r.text
    return r.json()["freigabe"]


def test_eine_freigegebene_mail_kommt_herein_und_wird_gezaehlt(client_db, schluessel):
    tc, db = client_db
    f = _scharf(tc)
    r = _senden(tc, schluessel, modus="scan", anbieter="Thunderbird", ordner=" Jobs \\ Portale/ ")
    assert r.status_code == 200, r.text
    assert r.json()["quelle"] == {"modus": "scan", "freigabe": f["id"]}, "Schreibweise von Pfad und Anbieter ist egal"
    assert _dokumente(db) == 1


def test_nur_genau_dieser_ordner_nicht_der_eltern_nicht_ein_unterordner(client_db, schluessel):
    tc, db = client_db
    _scharf(tc, ordner="Jobs/Portale")
    for ordner in ("Jobs", "Jobs/Portale/Alt", "Jobs/Portale2", "Jobs/Portale/", "Posteingang", ""):
        r = _senden(tc, schluessel, modus="scan", anbieter="thunderbird", ordner=ordner)
        erwartet = 200 if ordner == "Jobs/Portale/" else 403
        assert r.status_code == erwartet, (ordner, r.status_code, r.text)
    assert _dokumente(db) <= 1


def test_kein_platzhalter_und_keine_steuerzeichen(client_db):
    tc, _ = client_db
    for boese in ("Jobs/*", "*", "Jobs?", "Jobs\x00", "Jo\nbs"):
        r = tc.post("/api/mail-quelle/freigaben", json={"anbieter": "thunderbird", "ordner": boese})
        assert r.status_code == 400, repr(boese)


def test_der_posteingang_braucht_eine_ausdrueckliche_bestaetigung(client_db):
    tc, db = client_db
    for name in ("Posteingang", "INBOX", "inbox", " Eingang "):
        r = tc.post("/api/mail-quelle/freigaben", json={"anbieter": "outlook", "ordner": name})
        assert r.status_code == 200 and r.json()["status"] == "posteingang_warnung", name
        assert "Arztmails" in r.json()["text"]
    assert mail_quelle.lesen(db)["freigaben"] == []
    r = tc.post("/api/mail-quelle/freigaben", json={"anbieter": "outlook", "ordner": "Posteingang", "posteingang_bestaetigt": True})
    assert r.json()["status"] == "freigegeben" and r.json()["freigabe"]["posteingang"] is True
    # ein Unterordner namens Posteingang/Jobs ist kein „ganzer Posteingang“
    r = tc.post("/api/mail-quelle/freigaben", json={"anbieter": "outlook", "ordner": "Posteingang/Jobs"})
    assert r.json()["status"] == "freigegeben" and r.json()["freigabe"]["posteingang"] is False


def test_dieselbe_freigabe_gibt_es_nur_einmal_und_unbekannte_anbieter_nicht(client_db):
    tc, _ = client_db
    ein = {"anbieter": "thunderbird", "ordner": "Jobs", "konto": "Konto A"}
    assert tc.post("/api/mail-quelle/freigaben", json=ein).json()["status"] == "freigegeben"
    assert tc.post("/api/mail-quelle/freigaben", json={**ein, "ordner": " jobs "}).json()["status"] == "schon_da"
    assert tc.post("/api/mail-quelle/freigaben", json={**ein, "konto": "Konto B"}).json()["status"] == "freigegeben"
    r = tc.post("/api/mail-quelle/freigaben", json={"anbieter": "gmail", "ordner": "Jobs"})
    assert r.status_code == 400 and "Unbekanntes Mail-Programm" in r.json()["text"]


def test_das_konto_muss_stimmen(client_db, schluessel):
    tc, _ = client_db
    _scharf(tc, ordner="Jobs", konto="Konto A")
    assert _senden(tc, schluessel, modus="scan", anbieter="thunderbird", konto="Konto B", ordner="Jobs").status_code == 403
    assert _senden(tc, schluessel, modus="scan", anbieter="thunderbird", konto="", ordner="Jobs").status_code == 403
    assert _senden(tc, schluessel, modus="scan", anbieter="thunderbird", konto="Konto A", ordner="Jobs").status_code == 200


# ── AK 4: Thread-Nachverfolgung ───────────────────────────────────────────────────────────

def test_eine_antwort_kette_macht_einen_fremden_ordner_nicht_freigegeben(client_db, schluessel):
    """Eine Mail aus einem NICHT freigegebenen Ordner, die auf eine bereits importierte antwortet, kommt nicht herein."""
    tc, db = client_db
    _scharf(tc, ordner="Jobs")
    erste = _mail("Ihre Bewerbung", extra_header={"Message-ID": "<erste@example.com>"})
    assert _senden(tc, schluessel, eml=erste, modus="scan", anbieter="thunderbird", ordner="Jobs").status_code == 200
    vorher = _dokumente(db)
    antwort = _mail("Re: Ihre Bewerbung", extra_header={"In-Reply-To": "<erste@example.com>", "References": "<erste@example.com>",
                                                        "Message-ID": "<zweite@example.com>"})
    r = _senden(tc, schluessel, eml=antwort, modus="scan", anbieter="thunderbird", ordner="Gesendet")
    assert r.status_code == 403 and r.json()["code"] == "ordner_nicht_freigegeben"
    assert _dokumente(db) == vorher, "auch der Thread holt keine Mail aus einem fremden Ordner herein"
    # und ohne Ordnerangabe erst recht nicht
    r = _senden(tc, schluessel, eml=antwort, modus="scan", anbieter="thunderbird")
    assert r.status_code == 403 and r.json()["code"] == "ordner_fehlt"


# ── AK 5: anbieterunabhängig ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("anbieter", ["thunderbird", "outlook", "sonstige"])
def test_die_regel_gilt_fuer_jeden_anbieter_gleich(client_db, schluessel, anbieter):
    tc, _ = client_db
    _scharf(tc, ordner="Jobs", anbieter=anbieter)
    assert _senden(tc, schluessel, modus="scan", anbieter=anbieter, ordner="Jobs").status_code == 200
    for fremd in {"thunderbird", "outlook", "sonstige"} - {anbieter}:
        assert _senden(tc, schluessel, modus="scan", anbieter=fremd, ordner="Jobs").status_code == 403, fremd


def test_push_bleibt_wie_bisher_ohne_schalter_und_ohne_liste(client_db, schluessel):
    """Wer nur Push will, schaltet den Ordner-Scan nie ein: „An PBP senden“ funktioniert unverändert."""
    tc, db = client_db
    assert mail_quelle.wirksam(db) is False
    r = _senden(tc, schluessel)
    assert r.status_code == 200 and r.json()["status"] == "ok" and "quelle" not in r.json()
    assert _senden(tc, schluessel, modus="push").status_code == 200
    assert _senden(tc, schluessel, modus="egal").status_code == 400


def test_die_richtlinie_ist_nur_mit_gekoppeltem_plugin_lesbar(client_db, schluessel):
    tc, _ = client_db
    assert tc.get("/api/v1/ingest/mail-policy").status_code == 401
    assert tc.get("/api/v1/ingest/mail-policy", headers={"X-PBP-API-Key": "pbp_falsch"}).status_code in (401, 403)
    pol = tc.get("/api/v1/ingest/mail-policy", headers=schluessel).json()
    assert pol["ordner_scan"] is False and pol["freigaben"] == [] and pol["modi"] == ["push", "scan"]


def test_die_richtlinie_nennt_die_freigaben_nur_wenn_der_scan_wirksam_ist(client_db, schluessel):
    tc, _ = client_db
    f = _scharf(tc, ordner="Jobs")
    pol = tc.get("/api/v1/ingest/mail-policy", headers=schluessel).json()
    assert pol["ordner_scan"] is True and [x["ordner"] for x in pol["freigaben"]] == ["Jobs"] and pol["freigaben"][0]["id"] == f["id"]
    tc.post("/api/mail-quelle/scan", json={"an": False})
    pol = tc.get("/api/v1/ingest/mail-policy", headers=schluessel).json()
    assert pol["ordner_scan"] is False and pol["freigaben"] == [], "ausgeschaltet: das Add-on erfährt keinen einzigen Ordner"


# ── AK 6, 7: Zahlen und Abschalten ───────────────────────────────────────────────────────

def test_je_ordner_stehen_letzter_lauf_mails_und_stellen(client_db, schluessel):
    tc, db = client_db
    f1 = _scharf(tc, ordner="Jobs/Portale")
    f2 = tc.post("/api/mail-quelle/freigaben", json={"anbieter": "thunderbird", "ordner": "Jobs/Direkt"}).json()["freigabe"]
    html = ('<html><body><a href="https://www.stepstone.de/stellenangebote--PLM-Berater-Hamburg-Acme-GmbH--9876543-inline.html'
            '?utm_source=email">PLM Berater (m/w/d) bei Acme GmbH</a></body></html>')
    r = _senden(tc, schluessel, eml=_mail("Neue Jobs", html=html), modus="scan", anbieter="thunderbird", ordner="Jobs/Portale")
    assert r.status_code == 200 and r.json().get("newsletter", {}).get("neu", 0) >= 1, r.text
    _senden(tc, schluessel, modus="scan", anbieter="thunderbird", ordner="Jobs/Direkt")
    u = {f["id"]: f for f in tc.get("/api/mail-quelle").json()["freigaben"]}
    assert (u[f1["id"]]["mails"], u[f1["id"]]["stellen"]) == (1, r.json()["newsletter"]["neu"])
    assert (u[f2["id"]]["mails"], u[f2["id"]]["stellen"]) == (1, 0)
    assert u[f1["id"]]["letzter_lauf"] and u[f2["id"]]["letzter_lauf"]
    assert tc.get("/api/mail-quelle").json()["summe"]["mails"] == 2


def test_abschalten_wirkt_sofort_und_nennt_die_importierten_daten(client_db, schluessel):
    tc, db = client_db
    _scharf(tc, ordner="Jobs")
    assert _senden(tc, schluessel, modus="scan", anbieter="thunderbird", ordner="Jobs").status_code == 200
    r = tc.post("/api/mail-quelle/scan", json={"an": False})
    j = r.json()
    assert j["status"] == "aus" and j["importiert"]["mails"] == 1
    for wort in ("bleibt in PBP", "Stellen", "Dokumente", "An PBP senden"):
        assert wort in j["text"], wort
    # sofort: die nächste Mail desselben Ordners kommt nicht mehr herein, die Liste bleibt gespeichert
    vorher = _dokumente(db)
    r = _senden(tc, schluessel, modus="scan", anbieter="thunderbird", ordner="Jobs")
    assert r.status_code == 403 and r.json()["code"] == "scan_aus"
    assert _dokumente(db) == vorher
    assert [f["ordner"] for f in tc.get("/api/mail-quelle").json()["freigaben"]] == ["Jobs"]
    # und Push geht weiter
    assert _senden(tc, schluessel).status_code == 200


def test_eine_freigabe_zurueckzunehmen_wirkt_sofort(client_db, schluessel):
    tc, _ = client_db
    f = _scharf(tc, ordner="Jobs")
    assert tc.delete(f"/api/mail-quelle/freigaben/{f['id']}").json()["status"] == "entfernt"
    r = _senden(tc, schluessel, modus="scan", anbieter="thunderbird", ordner="Jobs")
    assert r.status_code == 403 and r.json()["code"] == "whitelist_leer"
    assert tc.delete("/api/mail-quelle/freigaben/mo_gibtsnicht").status_code == 404


def test_zuruecksetzen_raeumt_schalter_und_liste_auf_die_daten_bleiben(client_db, schluessel):
    tc, db = client_db
    _scharf(tc, ordner="Jobs")
    _senden(tc, schluessel, modus="scan", anbieter="thunderbird", ordner="Jobs")
    j = tc.post("/api/mail-quelle/zuruecksetzen").json()
    assert j["status"] == "zurueckgesetzt" and j["importiert"]["mails"] == 1 and "bleiben" in j["text"]
    u = tc.get("/api/mail-quelle").json()
    assert u["scan_aktiv"] is False and u["freigaben"] == []
    assert _dokumente(db) == 1


# ── AK 11, 12: Updates und unlesbare Einstellungen ─────────────────────────────────────────────

def test_eine_in_der_beta_eingeschaltete_quelle_ist_in_stabil_nicht_still_aktiv(client_db, schluessel, monkeypatch):
    tc, db = client_db
    monkeypatch.setattr(mail_quelle, "_version", lambda: "1.8.0-beta.16")
    _scharf(tc, ordner="Jobs")
    assert mail_quelle.wirksam(db) is True
    # ... Update auf die stabile Fassung: dieselbe Datenbank, andere Version
    monkeypatch.setattr(mail_quelle, "_version", lambda: "1.8.0")
    assert mail_quelle.wirksam(db) is False
    r = _senden(tc, schluessel, modus="scan", anbieter="thunderbird", ordner="Jobs")
    assert r.status_code == 403 and r.json()["code"] == "neu_bestaetigen"
    u = tc.get("/api/mail-quelle").json()
    assert u["neu_bestaetigen"] is True and u["wirksam"] is False and "erneut bestätigst" in u["hinweise"][0]
    assert tc.get("/api/v1/ingest/mail-policy", headers=schluessel).json()["freigaben"] == []
    # erst die erneute Bestätigung macht sie in der stabilen Version wieder wirksam
    assert tc.post("/api/mail-quelle/scan", json={"an": True, "bestaetigt": True}).status_code == 200
    assert mail_quelle.wirksam(db) is True
    assert _senden(tc, schluessel, modus="scan", anbieter="thunderbird", ordner="Jobs").status_code == 200


def test_eine_in_der_stabilen_version_eingeschaltete_quelle_bleibt_an(client_db, monkeypatch):
    tc, db = client_db
    monkeypatch.setattr(mail_quelle, "_version", lambda: "1.8.0")
    _scharf(tc, ordner="Jobs")
    monkeypatch.setattr(mail_quelle, "_version", lambda: "1.8.1")
    assert mail_quelle.wirksam(db) is True, "nur der Weg von Beta zu stabil verlangt die Bestätigung"


@pytest.mark.parametrize("kaputt", [
    "kein dict", 42, [],
    {"format": 2, "scan_aktiv": True, "freigaben": []},                                   # neueres Format
    {"format": 1, "scan_aktiv": "ja", "freigaben": []},                                   # falscher Typ
    {"format": 1, "scan_aktiv": True, "freigaben": "Jobs"},                               # Liste fehlt
    {"format": 1, "scan_aktiv": True, "freigaben": [{"id": "x", "anbieter": "gmail", "konto": "", "ordner": "Jobs"}]},
    {"format": 1, "scan_aktiv": True, "freigaben": [{"id": "x", "anbieter": "outlook", "konto": "", "ordner": "  "}]},
    {"format": 1, "scan_aktiv": True, "freigaben": [{"id": 5, "anbieter": "outlook", "konto": "", "ordner": "Jobs"}]},
])
def test_eine_nicht_lesbare_einstellung_faellt_auf_den_sicheren_zustand(client_db, schluessel, kaputt):
    """AK 12 und die Vorgabe „im Zweifel restriktiv“: aus, leere Liste, ein Hinweis, nie mehr Zugriff."""
    tc, db = client_db
    db.set_setting(mail_quelle.SCHLUESSEL, kaputt)
    u = tc.get("/api/mail-quelle").json()
    assert u["unlesbar"] is True and u["scan_aktiv"] is False and u["wirksam"] is False and u["freigaben"] == []
    assert "neu ein" in u["hinweise"][0] or "Richte ihn" in u["hinweise"][0]
    r = _senden(tc, schluessel, modus="scan", anbieter="outlook", ordner="Jobs")
    assert r.status_code == 403 and r.json()["code"] == "einstellung_unlesbar"
    assert db.get_setting(mail_quelle.SCHLUESSEL) == kaputt, "gelesen wird nur; überschrieben wird erst durch eine Handlung des Menschen"
    # die Handlung des Menschen stellt einen sauberen Zustand her
    assert tc.post("/api/mail-quelle/zuruecksetzen").status_code == 200
    assert tc.get("/api/mail-quelle").json()["unlesbar"] is False


# ── Claude ───────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def werkzeug(client_db):
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    _, db = client_db
    mcp = FastMCP("mail-test")
    register_all(mcp, db, logging.getLogger("mail-test"))

    def aufruf(name, **args):
        async def _run():
            tool = await mcp.get_tool(name)
            res = await tool.run(args)
            return res.structured_content if hasattr(res, "structured_content") else res
        return asyncio.run(_run())
    return aufruf


def test_claude_braucht_fuer_einschalten_und_posteingang_die_bestaetigung(client_db, werkzeug):
    _, db = client_db
    erg = werkzeug("mail_quelle_einstellen", aktion="scan_einschalten")
    assert erg["status"] == "bestaetigung_noetig" and "naechster_schritt" in erg and mail_quelle.wirksam(db) is False
    erg = werkzeug("mail_quelle_einstellen", aktion="scan_einschalten", bestaetigt=True)
    assert erg["status"] == "an" and erg["stand"]["wirksam"] is True
    erg = werkzeug("mail_quelle_einstellen", aktion="freigabe_hinzufuegen", anbieter="outlook", ordner="Posteingang")
    assert erg["status"] == "posteingang_warnung" and mail_quelle.lesen(db)["freigaben"] == []
    erg = werkzeug("mail_quelle_einstellen", aktion="freigabe_hinzufuegen", anbieter="outlook", ordner="Jobs")
    assert erg["status"] == "freigegeben"
    fid = erg["freigabe"]["id"]
    assert werkzeug("mail_quelle_anzeigen")["freigaben"][0]["ordner"] == "Jobs"
    assert werkzeug("mail_quelle_einstellen", aktion="freigabe_entfernen", freigabe_id=fid)["status"] == "entfernt"
    assert werkzeug("mail_quelle_einstellen", aktion="scan_ausschalten")["status"] == "aus"
    erg = werkzeug("mail_quelle_einstellen", aktion="gibt-es-nicht")
    assert erg["status"] == "fehler" and "scan_einschalten" in erg["erlaubt"]


def test_die_werkzeuge_sind_eingeordnet(client_db):
    from bewerbungs_assistent.services import werkzeug_katalog, werkzeug_schutz
    assert {"mail_quelle_anzeigen", "mail_quelle_einstellen"} <= werkzeug_katalog.EINSTELLUNG
    assert werkzeug_schutz.annotations_fuer("mail_quelle_anzeigen") == {"readOnlyHint": True}
    assert werkzeug_schutz.annotations_fuer("mail_quelle_einstellen") == {}
