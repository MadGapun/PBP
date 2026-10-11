"""Ingest-API v1: der Vertrag, den 1.8.0 einfriert (Beta-Exit Punkt 2, I27).

„Zwischen Release-Candidate und Stable keine Breaking Changes an `/api/v1/ingest/*` und am Manifest-Schema (`pbp-plugin.json`);
danach nur additive Änderungen oder `/api/v2/` parallel.“ (Master-Plan, Beta-Exit-Kriterium v1.8, Punkt 2)

Dieser Test hält die Oberfläche fest, auf die sich Add-ons verlassen — Thunderbird-Add-on, Beobachtungsordner und alles, was Dritte
schreiben. **Er prüft Obermengen:** eine Antwort darf um Felder wachsen (additiv), aber kein Pfad, keine Methode, kein Pflichtfeld und
kein Antwortfeld darf verschwinden oder die Bedeutung wechseln. Wer hier etwas ändern muss, ändert `/api/v1` NICHT, sondern legt
`/api/v2` daneben und lässt v1 stehen.

Alles lokal über den FastAPI-TestClient, kein Netz, isolierte Datenbank.
"""
from __future__ import annotations

import os
import sys
from email.mime.text import MIMEText
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

PFAD = "/api/v1/ingest"
MANIFEST = {
    "name": "Vertrags-Zubringer",
    "version": "1.0.0",
    "ingest_api": "^1",
    "capabilities": ["ingest:email", "ingest:job"],
    "beschreibung": "Vertragstest",
}


@pytest.fixture
def api(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    from fastapi.testclient import TestClient
    tc = TestClient(dash.app)
    gekoppelt = tc.post("/api/plugins/pair", json={"manifest": MANIFEST})
    assert gekoppelt.status_code == 200, gekoppelt.text
    kopf = {"X-PBP-API-Key": gekoppelt.json()["api_key"]}
    yield tc, kopf, dash
    dash._db = None
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


# ── die Oberfläche: Pfade und Methoden ───────────────────────────────────────────────────────────────────────

def test_v1_pfade_und_methoden_sind_genau_diese(api):
    _tc, _kopf, dash = api
    gefunden = set()
    for route in dash.app.routes:
        pfad = getattr(route, "path", "")
        if pfad.startswith(PFAD):
            for methode in getattr(route, "methods", None) or ():
                if methode not in ("HEAD", "OPTIONS"):
                    gefunden.add((methode, pfad))
    erwartet = {("GET", f"{PFAD}/ping"), ("POST", f"{PFAD}/job"), ("GET", f"{PFAD}/mail-policy"), ("POST", f"{PFAD}/email")}
    fehlt = erwartet - gefunden
    assert not fehlt, f"aus v1 verschwunden (Breaking Change): {sorted(fehlt)}"
    # Was NEU dazukommt, ist additiv erlaubt — aber es muss bewusst im Vertrag stehen, sonst bleibt es unbemerkt.
    neu = gefunden - erwartet
    assert not neu, f"neu in v1: {sorted(neu)} — additiv erlaubt, bitte hier in `erwartet` und in der Plugin-Doku nachtragen"


def test_ohne_schluessel_kein_zugriff_und_die_antwort_nennt_die_api_version(api):
    tc, _kopf, _dash = api
    for methode, pfad in (("get", "ping"), ("get", "mail-policy")):
        r = getattr(tc, methode)(f"{PFAD}/{pfad}")
        assert r.status_code in (401, 403), (pfad, r.status_code)
        assert r.headers.get("X-PBP-Ingest-API") == "1"
        antwort = r.json()
        assert "error" in antwort and "hinweis" in antwort
    r = tc.get(f"{PFAD}/ping", headers={"X-PBP-API-Key": "pbp_gibtesnicht"})
    assert r.status_code in (401, 403)


# ── ping ─────────────────────────────────────────────────────────────────────────────────────────────────────

def test_ping_antwortet_mit_den_vertragsfeldern(api):
    tc, kopf, _dash = api
    r = tc.get(f"{PFAD}/ping", headers=kopf)
    assert r.status_code == 200
    d = r.json()
    assert {"status", "plugin", "capabilities", "ingest_api", "pbp_version"} <= set(d)
    assert d["status"] == "ok" and d["ingest_api"] == 1
    assert d["plugin"] == MANIFEST["name"]
    assert set(d["capabilities"]) == set(MANIFEST["capabilities"])


# ── job ──────────────────────────────────────────────────────────────────────────────────────────────────────

def test_job_pflichtfelder_titel_und_firma(api):
    tc, kopf, _dash = api
    assert tc.post(f"{PFAD}/job", json={"firma": "Beispiel GmbH"}, headers=kopf).status_code == 422
    assert tc.post(f"{PFAD}/job", json={"titel": "Sachbearbeiter"}, headers=kopf).status_code == 422
    assert tc.post(f"{PFAD}/job", json={}, headers=kopf).status_code == 422


def test_job_nimmt_die_vertragsfelder_und_antwortet_mit_den_vertragsfeldern(api):
    tc, kopf, _dash = api
    koerper = {"titel": "Sachbearbeiter Einkauf", "firma": "Beispiel Werke GmbH", "url": "https://beispiel.example/jobs/1",
               "ort": "Hamburg", "beschreibung": "Aufgaben: Bestellungen bearbeiten und Lieferanten betreuen. " * 3,
               "remote": "hybrid", "stellenart": "festanstellung"}
    r = tc.post(f"{PFAD}/job", json=koerper, headers=kopf)
    assert r.status_code == 200, r.text
    d = r.json()
    assert {"status", "job_hash", "score", "duplikate_erkannt"} <= set(d)
    assert d["status"] in {"angelegt", "als_duplikat_markiert"}
    assert isinstance(d["job_hash"], str) and d["job_hash"]
    # zweimal dieselbe Stelle: „bereits_vorhanden“ mit der Kennung
    r2 = tc.post(f"{PFAD}/job", json=koerper, headers=kopf)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["status"] == "bereits_vorhanden" and d2["job_hash"] == d["job_hash"]


def test_job_ohne_job_capability_wird_abgewiesen(api):
    tc, _kopf, _dash = api
    nur_mail = tc.post("/api/plugins/pair", json={"manifest": {**MANIFEST, "name": "Nur-Mail", "capabilities": ["ingest:email"]}})
    assert nur_mail.status_code == 200
    kopf = {"X-PBP-API-Key": nur_mail.json()["api_key"]}
    r = tc.post(f"{PFAD}/job", json={"titel": "X", "firma": "Y"}, headers=kopf)
    assert r.status_code in (401, 403)


# ── mail-policy und email ────────────────────────────────────────────────────────────────────────────────────

def test_mail_policy_hat_die_vertragsfelder_und_ist_vorgabe_aus(api):
    tc, kopf, _dash = api
    r = tc.get(f"{PFAD}/mail-policy", headers=kopf)
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d, dict) and d, "die Richtlinie ist nie leer"
    # Vorgabe aus: ohne Einschalten nichts freigegeben
    assert not d.get("freigaben"), d


def _eml(betreff="Hallo", von="absender@example.com") -> bytes:
    m = MIMEText("Das ist ein Test.", "plain", "utf-8")
    m["Subject"], m["From"], m["To"] = betreff, von, "empfaenger@example.com"
    return m.as_bytes()


def test_email_unbekannter_modus_wird_mit_der_liste_der_erlaubten_abgewiesen(api):
    tc, kopf, _dash = api
    r = tc.post(f"{PFAD}/email", headers=kopf, files={"file": ("m.eml", _eml(), "message/rfc822")}, data={"modus": "irgendwas"})
    assert r.status_code == 400
    assert set(r.json().get("erlaubt", [])) == {"push", "scan"}


def test_email_scan_ohne_freigabe_ist_403_und_nennt_die_richtlinie(api):
    tc, kopf, _dash = api
    r = tc.post(f"{PFAD}/email", headers=kopf, files={"file": ("m.eml", _eml(), "message/rfc822")},
                data={"modus": "scan", "anbieter": "thunderbird", "konto": "a@example.com", "ordner": "Stellen"})
    assert r.status_code == 403
    d = r.json()
    assert d.get("modus") == "scan" and "code" in d and "hinweis" in d


def test_email_push_ohne_zusatzfelder_funktioniert_wie_vor_1_8(api):
    """Das Thunderbird-Add-on von beta.3 sendet nur `file`. Es darf durch die Zugangsschicht (#947) nicht scheitern."""
    tc, kopf, _dash = api
    r = tc.post(f"{PFAD}/email", headers=kopf, files={"file": ("m.eml", _eml("Ihre Bewerbung"), "message/rfc822")})
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), dict)


# ── Manifest ─────────────────────────────────────────────────────────────────────────────────────────────────

def test_manifest_schema_ist_unveraendert():
    from bewerbungs_assistent.services import plugins
    assert plugins.INGEST_API_MAJOR == 1
    # Pflichtfelder: jedes fehlende wird benannt (die Plugins schreiben genau diese)
    fehler, _ = plugins.validate_manifest({})
    for feld in ("name", "version", "ingest_api", "capabilities"):
        assert any(feld in f for f in fehler), (feld, fehler)
    # bekannte Fähigkeiten bleiben bekannt
    assert {"ingest:email", "ingest:job"} <= set(plugins.CAPABILITIES)
    # die Schreibweisen der Version, die Plugins heute benutzen, bleiben gültig
    for spec in ("^1", "1", "^1.0", "~1.2", "1.x"):
        f, _ = plugins.validate_manifest({**MANIFEST, "ingest_api": spec})
        assert f == [], (spec, f)
    f, _ = plugins.validate_manifest({**MANIFEST, "ingest_api": "^2"})
    assert f, "v2 wird von v1 abgelehnt"


def test_die_beiden_mitgelieferten_plugins_bestehen_den_vertrag():
    """Das Thunderbird-Add-on und der Beobachtungsordner liegen im Repo; ihre Manifeste sind die Probe aufs Schema."""
    import json
    from bewerbungs_assistent.services import plugins
    wurzel = Path(__file__).resolve().parents[1] / "plugins"
    gefunden = list(wurzel.glob("*/pbp-plugin.json"))
    assert len(gefunden) >= 2, gefunden
    for datei in gefunden:
        fehler, _ = plugins.validate_manifest(json.loads(datei.read_text(encoding="utf-8")))
        assert fehler == [], (datei.parent.name, fehler)
