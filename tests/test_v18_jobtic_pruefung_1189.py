"""#1189 (B78) - Funde des unabhaengigen Pruefers am Release-Kandidaten (11.10.2026).

Die Auflagen der Quelle waren an sechs Stellen kontrolliert und an fuenf weiteren umgehbar:

1. Der Text einer Anlage oder Bearbeitung trug den Ansprechpartner trotz `keine_kontaktdaten`.
2. Eine eigene Quelle (`custom_quelle_hinzufuegen`) auf einer jobtic-Adresse wurde im Gesundheitslauf angefragt und
   ohne Auflagen ausgeliefert.
3. Die Anleitung des Suchlaufs sagte "ARBEITE DIESE QUELLEN SELBST AB - ohne Nachfrage" auch fuer eine Quelle, die nur
   auf ausdruecklichen Wunsch laeuft.
5. Der Platzhalter "Nicht angegeben" liess zwei verschiedene Projekte als dieselbe Stelle gelten.
7. Der Bestandsnachzug fuellte `max_stellen` mit Stellen, die er nie abrufen darf.
8. Der Dashboard-Knopf "Beschreibung nachladen" zaehlte das Abrufverbot als Fehlversuch.
R. `jobtic.com:443` und `nutzer@jobtic.com` wurden der Quelle nicht zugeordnet.

Alle Firmen, Personen und Adressen in diesen Tests sind erfunden.
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

PROJEKT = "https://jobtic.com/project/pruefung0001"
TEXT = ("Aufgaben: Betrieb und Weiterentwicklung der Identitaetsplattform, Anbindung von Anwendungen, Betrieb im "
        "Rechenzentrum. Profil: mehrjaehrige Erfahrung mit Keycloak, Java und Linux, sicherer Umgang mit Protokollen. ") * 3
MIT_KONTAKT = (TEXT + "Ansprechpartnerin: Erika Beispiel, erika.beispiel@example.com, Tel.: 0211 1234567, "
               "mobil +49 171 1234567. Tagessatz 700-900 EUR, Laufzeit 2026-2027.")


@pytest.fixture
def env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v18_jobtic_pruefung_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    db.set_search_criteria("keywords_muss", ["Keycloak", "IAM"])
    yield db, _srv_mod.mcp
    db.close()
    os.environ.pop("BA_DATA_DIR", None)
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


def _anlegen(mcp, **kw):
    args = {"titel": "Keycloak Consultant (m/w/d) Remote / ZXXX1", "firma": "Nicht angegeben", "ort": "Hannover",
            "quelle": "jobtic", "url": PROJEKT, "beschreibung": TEXT, "remote": "remote"}
    args.update(kw)
    return _call(mcp, "stelle_manuell_anlegen", args)


# ══ 1  Kontaktdaten im Text ═══════════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("text", [
    "Ansprechpartner: Max Beispiel, max.beispiel@example.com",
    "Tel.: 0211 123456",
    "Telefon +49 (0) 211 1234567",
    "Rufen Sie an: +49 211 1234567",
    "0171-1234567 oder 0211 / 123456",
    "Fax 0211/123456",
    "mobil: 0171 12 34 567",
])
def test_mailadressen_und_rufnummern_werden_erkannt(text):
    from bewerbungs_assistent.services.quellen_auflagen import kontaktdaten_entfernen
    bereinigt, anzahl = kontaktdaten_entfernen(text)
    assert anzahl >= 1, text
    assert "[Kontaktangabe entfernt]" in bereinigt
    assert "@" not in bereinigt and "1234567" not in bereinigt and "123456" not in bereinigt


@pytest.mark.parametrize("text", [
    "Zeitraum 01.11.2026 - 31.12.2026",
    "Tagessatz 700-900 EUR",
    "Laufzeit 2025-2026, Start 2026-01-12",
    "80.000 - 100.000 EUR p.a.",
    "Projekt 2024-0815, Auslastung 80-100 %",
    "Mobile Entwicklung und Handy-Apps seit 2019",
    "SAP S/4HANA 2022 - 2024, Version 1809",
    "Remote / ZXXX1, 5 Tage vor Ort",
    "Telefoninterview in KW 45",
    "Dauer: 6-12 Monate; Beginn ab 03.11.",
])
def test_zahlenfolgen_die_keine_nummern_sind_bleiben(text):
    """Die Telefon-Erkennung las einmal die Jahresspanne 2020-2024 als Rufnummer (16 von 60 Treffern Fehlalarm)."""
    from bewerbungs_assistent.services.quellen_auflagen import kontaktdaten_entfernen
    bereinigt, anzahl = kontaktdaten_entfernen(text)
    assert anzahl == 0 and bereinigt == text, (text, bereinigt)


def test_die_anlage_streicht_kontaktdaten_aus_dem_text_und_sagt_es(env):
    db, mcp = env
    res = _anlegen(mcp, beschreibung=MIT_KONTAKT)
    assert res["status"] == "angelegt", res
    text = db.get_job(res["hash"])["description"]
    for spur in ("erika.beispiel@example.com", "0211 1234567", "+49 171 1234567"):
        assert spur not in text, f"{spur} steht noch in der Beschreibung"
    assert "Tagessatz 700-900 EUR, Laufzeit 2026-2027" in text, "Zahlen, die keine Nummern sind, bleiben"
    assert "Keycloak" in text
    assert "entfernt" in res["kontakt_nicht_uebernommen"]


def test_jede_andere_quelle_behaelt_ihren_text(env):
    """Gegenprobe: die Auflage gilt jobtic, nicht dem Werkzeug."""
    db, mcp = env
    res = _anlegen(mcp, quelle="linkedin", url="https://www.linkedin.com/jobs/view/4711/",
                   titel="Identity Engineer (m/w/d) Musterstadt", beschreibung=MIT_KONTAKT)
    assert res["status"] == "angelegt", res
    assert "erika.beispiel@example.com" in db.get_job(res["hash"])["description"]
    assert "kontakt_nicht_uebernommen" not in res


def test_stelle_bearbeiten_streicht_kontaktdaten_bei_einer_jobtic_stelle(env):
    db, mcp = env
    res = _anlegen(mcp)
    assert res["status"] == "angelegt", res
    erg = _call(mcp, "stelle_bearbeiten", {"job_hash": res["hash"], "beschreibung": MIT_KONTAKT})
    assert erg["status"] == "aktualisiert", erg
    assert "erika.beispiel@example.com" not in db.get_job(res["hash"])["description"]
    assert "entfernt" in erg["kontakt_nicht_uebernommen"]


def test_stelle_bearbeiten_laesst_andere_quellen_unberuehrt(env):
    db, mcp = env
    res = _anlegen(mcp, quelle="linkedin", url="https://www.linkedin.com/jobs/view/4712/",
                   titel="Identity Engineer (m/w/d) Musterstadt")
    erg = _call(mcp, "stelle_bearbeiten", {"job_hash": res["hash"], "beschreibung": MIT_KONTAKT})
    assert erg["status"] == "aktualisiert", erg
    assert "erika.beispiel@example.com" in db.get_job(res["hash"])["description"]
    assert "kontakt_nicht_uebernommen" not in erg


# ══ 2  eigene Quelle auf einer jobtic-Adresse ═════════════════════════════════════════════════════════════════

def test_eine_eigene_quelle_auf_jobtic_hat_dieselben_auflagen_im_handoff(env):
    _, mcp = env
    from bewerbungs_assistent.job_scraper.handoff import build_handoff, extraktions_js
    h = build_handoff("custom:jobtic", "", custom_url="https://jobtic.com/search?q=keycloak")
    assert h["auflagen"], "die Auflagen der Quelle fehlen"
    assert "ausdrücklichen Wunsch" in h["auflagen"]
    assert "Session umgeht Bot-Blocker" not in h["anleitung"], "kein Bot-Blocker-Umweg mit eigener Quelle"
    assert h["extraction_js"] == extraktions_js("jobtic"), "das Skript der Quelle, nicht das allgemeine"


def test_eine_unbekannte_eigene_quelle_bleibt_wie_sie_war(env):
    _, mcp = env
    from bewerbungs_assistent.job_scraper.handoff import GENERIC_EXTRACTION_JS, build_handoff
    h = build_handoff("Acme Karriere", "", custom_url="https://karriere.example.com/jobs")
    assert "auflagen" not in h
    assert h["extraction_js"] == GENERIC_EXTRACTION_JS


def test_custom_quelle_hinzufuegen_nennt_die_auflagen_der_adresse(env):
    _, mcp = env
    res = _call(mcp, "custom_quelle_hinzufuegen", {"name": "Meine Projekte", "url": "https://jobtic.com/search?q=iam"})
    assert res["status"] == "angelegt", res
    assert res["auflagen"] and "nie selbst ab" in res["hinweis"]
    andere = _call(mcp, "custom_quelle_hinzufuegen", {"name": "Acme", "url": "https://karriere.example.com/jobs"})
    assert "auflagen" not in andere


def test_der_gesundheitslauf_fragt_eine_eigene_jobtic_quelle_nicht_an(env, monkeypatch):
    db, mcp = env
    import httpx
    angefragt = []

    def verboten(self, url, *a, **kw):
        angefragt.append(str(url))
        raise AssertionError("PBP hat eine Seite mit Auflage selbst abgerufen")

    _call(mcp, "custom_quelle_hinzufuegen", {"name": "Meine Projekte", "url": "https://jobtic.com/search?q=iam"})
    monkeypatch.setattr(httpx.Client, "get", verboten)
    res = _call(mcp, "quellen_health_check", {"quellen": ["jobtic"], "parallel": False, "budget_sekunden": 20})
    assert not [u for u in angefragt if "jobtic.com" in u], angefragt
    eintrag = [c for c in res.get("custom_quellen", []) if "jobtic.com" in c["url"]]
    assert eintrag and eintrag[0]["reachable"] is None and "Auflage" in eintrag[0]["hinweis"], res


# ══ 3  "nur auf Wunsch" ═══════════════════════════════════════════════════════════════════════════════════════

def test_die_auflage_nur_auf_wunsch_ist_strukturiert_lesbar():
    from bewerbungs_assistent.services import quellen_auflagen as a
    assert a.nur_auf_wunsch("jobtic") is True
    assert a.nur_auf_wunsch("", "https://jobtic.com/project/abc") is True
    assert a.nur_auf_wunsch("xing") is False and a.nur_auf_wunsch("bundesagentur") is False


def test_der_suchstart_nennt_nur_auf_wunsch_getrennt(env, monkeypatch):
    db, mcp = env
    from bewerbungs_assistent.services import jobsuche_start as js, netz_pruefung

    class _Faden:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def join(self, timeout=None): pass
        def is_alive(self): return False

    monkeypatch.setattr(js.threading, "Thread", _Faden)
    monkeypatch.setattr(netz_pruefung, "erreichbar", lambda: True)
    erg = js.starten(db, quellen=["jobtic", "arbeitnow"], keywords=["Keycloak"])
    assert erg["status"] == "gestartet", erg
    assert erg["nur_auf_wunsch"] == ["jobtic"]
    assert "jobtic" in erg["manuelle_quellen"] and "arbeitnow" not in erg["manuelle_quellen"]
    alleine = js.starten(db, quellen=["jobtic"], keywords=["Keycloak"])
    assert alleine["status"] == "nur_manuelle_quellen" and alleine["nur_auf_wunsch"] == ["jobtic"]


def test_das_werkzeug_sagt_claude_was_nicht_von_selbst_laeuft(env, monkeypatch):
    db, mcp = env
    from bewerbungs_assistent.services import jobsuche_start as js, netz_pruefung

    class _Faden:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def join(self, timeout=None): pass
        def is_alive(self): return False

    monkeypatch.setattr(js.threading, "Thread", _Faden)
    monkeypatch.setattr(netz_pruefung, "erreichbar", lambda: True)
    res = _call(mcp, "jobsuche_starten", {"quellen": ["jobtic", "arbeitnow"], "keywords": ["Keycloak"]})
    assert res["status"] == "gestartet", res
    assert res["nur_auf_wunsch"] == ["jobtic"]
    assert "AUSGENOMMEN" in res["hinweis"] and "jobtic" in res["hinweis"]
    alleine = _call(mcp, "jobsuche_starten", {"quellen": ["jobtic"], "keywords": ["Keycloak"]})
    assert alleine["status"] == "nur_manuelle_quellen" and alleine["nur_auf_wunsch"] == ["jobtic"]
    assert "nicht von selbst" in alleine["nachricht"]


def test_die_anleitung_des_workflows_nimmt_die_quelle_aus():
    quelle = (ROOT / "src" / "bewerbungs_assistent" / "prompts.py").read_text(encoding="utf-8-sig")
    assert "ARBEITE DIESE QUELLEN SELBST AB" in quelle
    assert "Steht eine Quelle zusätzlich im Feld `nur_auf_wunsch`" in quelle
    assert "arbeitest du sie NICHT von selbst ab" in quelle


def test_der_text_der_quelle_in_der_liste_sagt_nicht_von_selbst():
    from bewerbungs_assistent.tools.jobs import _MANUAL_SOURCES
    assert "NICHT von selbst abarbeiten" in _MANUAL_SOURCES["jobtic"]
    assert "ausdrücklichen Wunsch" in _MANUAL_SOURCES["jobtic"]


# ══ 5  Platzhalter-Firma ══════════════════════════════════════════════════════════════════════════════════════

def test_zwei_projekte_gleichen_titels_ohne_genannten_auftraggeber_bleiben_zwei(env):
    db, mcp = env
    a = _anlegen(mcp, titel="SAP Berater (m/w/d) Remote", url="https://jobtic.com/project/aaaaa00001")
    b = _anlegen(mcp, titel="SAP Berater (m/w/d) Remote", url="https://jobtic.com/project/bbbbb00002")
    assert a["status"] == "angelegt", a
    assert b["status"] == "angelegt", b
    assert a["hash"] != b["hash"]


def test_dieselbe_adresse_bleibt_dieselbe_stelle(env):
    db, mcp = env
    a = _anlegen(mcp, titel="SAP Berater (m/w/d) Remote", url="https://jobtic.com/project/aaaaa00001")
    b = _anlegen(mcp, titel="SAP Berater (m/w/d) Remote", url="https://jobtic.com/project/aaaaa00001")
    assert a["status"] == "angelegt", a
    assert b["status"] == "bereits_vorhanden", b
    assert b["existing_hash"] == a["hash"] or b.get("grund")


def test_aehnliche_titel_ohne_firma_gelten_nicht_als_dublette(env):
    db, mcp = env
    a = _anlegen(mcp, titel="Senior DevOps Engineer (m/w/d) Remote", url="https://jobtic.com/project/ccccc00003")
    b = _anlegen(mcp, titel="DevOps Engineer (m/w/d) Remote", url="https://jobtic.com/project/ddddd00004")
    assert a["status"] == "angelegt", a
    assert b["status"] == "angelegt", b


def test_eine_genannte_firma_bleibt_ein_dublettenhinweis(env):
    """Gegenprobe: nur der Platzhalter wird nicht als Firma gelesen, ein echter Name schon."""
    db, mcp = env
    a = _anlegen(mcp, firma="Beispielwerk GmbH", titel="Keycloak Consultant (m/w/d)", quelle="manuell",
                 url="https://karriere.example.com/jobs/1")
    b = _anlegen(mcp, firma="Beispielwerk GmbH", titel="Keycloak Consultant (m/w/d)", quelle="manuell",
                 url="https://karriere.example.com/jobs/2")
    assert a["status"] == "angelegt", a
    assert b["status"] != "angelegt", "gleiche Firma, gleicher Titel: ein Hinweis, wie bisher"


def test_benennt_arbeitgeber_kennt_die_platzhalter():
    from bewerbungs_assistent.duplicate_detection import benennt_arbeitgeber
    for platzhalter in ("Nicht angegeben", "nicht angegeben", "Unbekannt", "", None, "  "):
        assert benennt_arbeitgeber(platzhalter) is False, platzhalter
    for name in ("Beispielwerk GmbH", "Unbekannt Software GmbH"):
        assert benennt_arbeitgeber(name) is True, name


# ══ 7  Bestandsnachzug ════════════════════════════════════════════════════════════════════════════════════════

def test_der_bestandsnachzug_zaehlt_jobtic_nicht_in_die_auswahl(env):
    db, mcp = env
    stellen = [{"hash": f"jt{i:02d}", "title": f"Projekt {i}", "company": "Nicht angegeben", "score": 10,
                "url": f"https://jobtic.com/project/zzzzzzzz{i:02d}", "source": "jobtic", "description": ""}
               for i in range(30)]
    stellen += [{"hash": f"an{i}", "title": f"Anderes Projekt {i}", "company": "Beispielwerk GmbH", "score": 1,
                 "url": f"https://karriere.example.com/jobs/{i}", "source": "manuell", "description": ""}
                for i in range(5)]
    db.save_jobs(stellen)
    res = _call(mcp, "beschreibungen_nachladen_bestand", {"max_stellen": 25, "nur_zaehlen": True, "umfang": "fehlend"})
    assert res["status"] == "vorschau", res
    assert res["betroffen"] == 5, res
    assert res["gefunden"]["nicht_automatisch"] == 30, res


# ══ 8  Dashboard-Knopf ════════════════════════════════════════════════════════════════════════════════════════

def test_der_dashboard_knopf_bucht_das_abrufverbot_nicht_als_fehlversuch(env, monkeypatch):
    db, mcp = env
    import httpx
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    res = _anlegen(mcp)
    assert res["status"] == "angelegt", res

    def verboten(self, url, *a, **kw):
        raise AssertionError("PBP hat eine Seite mit Auflage selbst abgerufen")

    monkeypatch.setattr(httpx.Client, "get", verboten)
    antwort = TestClient(dash.app).post(f"/api/jobs/{res['hash']}/refetch-description")
    assert antwort.status_code == 409, antwort.text
    assert antwort.json()["befund"] == "nicht_automatisch"
    assert "Nutzungsbedingungen" in antwort.json()["error"]
    from bewerbungs_assistent.services import text_nachzug
    assert text_nachzug._fehlversuche(db, res["hash"]) == 0, "das Abrufverbot ist kein Fehlversuch"


# ══ Randbefund: Adresse mit Port, Zugangsdaten, Schlusspunkt ══════════════════════════════════════════════════

@pytest.mark.parametrize("url", [
    "https://jobtic.com:443/project/abc",
    "https://nutzer@jobtic.com/project/abc",
    "https://www.jobtic.com./project/abc",
    "HTTPS://JOBTIC.COM/project/abc",
    "jobtic.com/project/abc",
])
def test_die_adresse_gehoert_zur_quelle_auch_mit_port_und_zugangsdaten(url):
    from bewerbungs_assistent.services.url_to_source import detect_source_from_url
    from bewerbungs_assistent.services import quellen_auflagen as a
    assert detect_source_from_url(url) == "jobtic", url
    assert a.kein_automatischer_abruf(url=url) is True, url


def test_eine_fremde_adresse_mit_jobtic_im_pfad_ist_nicht_jobtic():
    from bewerbungs_assistent.services.url_to_source import detect_source_from_url
    assert detect_source_from_url("https://example.com/jobtic.com/project/abc") == "manuell"
    assert detect_source_from_url("https://jobtic.com.example.com/project/abc") == "manuell"
