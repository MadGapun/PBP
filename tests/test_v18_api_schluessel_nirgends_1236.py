"""#1236 Abnahmekriterium 4 -- der Schluessel taucht nirgends auf.

*Nicht in `pbp.db`, Sicherung, Export, Log, Telemetrie, Fehlermeldung oder Testausgabe. Ein Test prueft alle Ausgabewege;
Gegenprobe: den Schluessel absichtlich ins Log schreiben, der Test muss rot werden.*

Der Test faehrt einen ganzen Weg durch den API-Weg, mit einem Schluessel in der Umgebung und einem Testdoppel, das sich so
schlecht benimmt wie moeglich: es wiederholt den Schluessel in Fehlermeldungen der API, in der Meldung einer Netzstoerung und
im Inhalt einer unlesbaren Antwort. Danach liest er jeden Kanal, ueber den etwas aus PBP hinauskommt, und sucht den
Schluessel -- ganz und in Stuecken (ein Teil eines Schluessels ist fuer einen Angreifer oft genug).

Die Gegenprobe steht gleich daneben: fuer JEDEN Kanal schreibt ein Test den Schluessel absichtlich hinein und verlangt, dass die
Suche anschlaegt. Ein Pruefer, der in einem Kanal nichts findet, weil er ihn gar nicht liest, waere ein Alibi.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import api_probe  # noqa: E402
from _api_hilfen import FakeTransport, TESTSCHLUESSEL, antwort, fehlerantwort  # noqa: E402
from fastmcp import FastMCP  # noqa: E402

from bewerbungs_assistent.database import Database  # noqa: E402
from bewerbungs_assistent.services import api_backend, sicherung  # noqa: E402
from bewerbungs_assistent.services.llm_service import LLMService, TaskKind  # noqa: E402
from bewerbungs_assistent.tools import get_recent_tool_calls, record_tool_call, register_all  # noqa: E402

FENSTER = 16  # Zeichen: ein Schluessel in Stuecken ab dieser Laenge gilt als gefunden


def _stuecke(schluessel: str) -> list[bytes]:
    roh = schluessel.encode("utf-8")
    return [roh[i:i + FENSTER] for i in range(0, len(roh) - FENSTER + 1)]


def finde_schluessel(kanaele: dict) -> list[str]:
    """Die Kanaele, in denen der Schluessel steht -- ganz oder ab FENSTER Zeichen am Stueck."""
    stuecke = _stuecke(TESTSCHLUESSEL)
    gefunden = []
    for name, inhalt in kanaele.items():
        daten = inhalt if isinstance(inhalt, (bytes, bytearray)) else str(inhalt).encode("utf-8", "replace")
        if TESTSCHLUESSEL.encode() in daten or any(s in daten for s in stuecke):
            gefunden.append(name)
    return gefunden


class Kanaele:
    """Alle Wege, auf denen etwas aus PBP herauskommt."""

    def __init__(self, db, daten_ordner: Path, caplog, capfd):
        self.db, self.ordner, self.caplog, self.capfd = db, Path(daten_ordner), caplog, capfd
        self.ausgaben: list = []
        self.konsole = ""

    def merke(self, was):
        self.ausgaben.append(json.dumps(was, ensure_ascii=False, default=str))
        return was

    def sammeln(self) -> dict:
        # Datenbank, WAL-Datei, Sicherungen, Logdateien: alles, was unter dem Datenordner liegt
        dateien = b""
        for f in sorted(self.ordner.rglob("*")):
            if not f.is_file():
                continue
            dateien += f.read_bytes()
            if f.suffix == ".zip":
                with zipfile.ZipFile(f) as z:
                    for n in z.namelist():
                        dateien += z.read(n)
        sicherung.sichern(self.db, anlass="manuell", mit_dokumenten=False)
        for f in sorted((self.ordner / sicherung.ORDNER).rglob("*")):
            if f.is_file():
                dateien += f.read_bytes()
        out, err = self.capfd.readouterr()
        self.konsole += out + err
        return {
            "dateien im Datenordner (Datenbank, Sicherung, Log)": dateien,
            "profil-export": json.dumps(self.db.export_profile_json() or {}, ensure_ascii=False, default=str),
            "log": self.caplog.text,
            "telemetrie (Tool-Aufrufe)": json.dumps(get_recent_tool_calls(200), ensure_ascii=False, default=str),
            "ausgaben (Antworten, Fehler, Metriken, Berichte)": "\n".join(self.ausgaben),
            "konsole": self.konsole,
        }


@pytest.fixture
def umgebung(tmp_path, monkeypatch, caplog, capfd):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    db = Database(db_path=tmp_path / "pbp.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    monkeypatch.setenv(api_backend.ENV_SCHLUESSEL, TESTSCHLUESSEL)
    caplog.set_level(logging.DEBUG)
    yield db, Kanaele(db, tmp_path, caplog, capfd)
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


# ============================================================ Der ganze Weg, so schlecht wie moeglich

def _boesartiges_doppel():
    """Jede Antwort wiederholt den Schluessel: im Fehlertext der API, in einer Netzstoerung, in einer unlesbaren Antwort."""
    echo = f"x-api-key {TESTSCHLUESSEL}"
    verhalten = [
        antwort(), antwort(),
        fehlerantwort(401, "authentication_error", f"invalid x-api-key: {TESTSCHLUESSEL}"),
        fehlerantwort(402, "billing_error", echo),
        fehlerantwort(429, "rate_limit_error", echo), fehlerantwort(429, "rate_limit_error", echo),
        fehlerantwort(500, "api_error", echo), fehlerantwort(529, "overloaded_error", echo),
        fehlerantwort(400, "invalid_request_error", f"Authorization failed for {TESTSCHLUESSEL}"),
        OSError(f"Verbindung abgebrochen, Kopf: x-api-key: {TESTSCHLUESSEL}"),
        TimeoutError(f"Zeitüberschreitung bei {TESTSCHLUESSEL}"),
        (200, {"request-id": f"req_{TESTSCHLUESSEL}"}, f"<html>{TESTSCHLUESSEL}</html>".encode()),
        antwort(f"PASST | der Schlüssel ist {TESTSCHLUESSEL}"),  # ein Modell, das ihn nicht hergeben duerfte
    ]
    zaehler = {"n": 0}

    def entscheider(aufruf):
        i = min(zaehler["n"], len(verhalten) - 1)
        zaehler["n"] += 1
        return verhalten[i]

    return FakeTransport(entscheider=entscheider)


def _durchlaufen(db, kanaele: Kanaele, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash

    transport = _boesartiges_doppel()
    api_backend.transport_setzen(transport)
    monkeypatch.setattr(dash, "_db", db)
    client = TestClient(dash.app)
    mcp = FastMCP("PBP Test")
    register_all(mcp, db, logging.getLogger("test.schluessel"))

    async def werkzeug(name, args=None):
        t = await mcp.get_tool(name)
        r = await t.run(args or {})
        return getattr(r, "structured_content", r)

    import asyncio

    def tool(name, args=None):
        return kanaele.merke(asyncio.run(werkzeug(name, args)))

    # Einstellen, anzeigen, pruefen -- ueber Chat und Dashboard
    tool("api_weg_anzeigen")
    tool("api_weg_einstellen", {"aufgaben": ["match_job_to_skills", "validate_job_quality"], "budget_usd": 1, "bestaetigt": True})
    kanaele.merke(client.get("/api/api-weg").json())
    kanaele.merke(client.put("/api/api-weg", json={"modelle": {"match_job_to_skills": "claude-sonnet-5-5"}}).json())
    kanaele.merke(client.get("/api/privacy-info").json())
    kanaele.merke(client.get("/api/telemetry/preview").json())
    kanaele.merke(client.post("/api/api-weg/pruefen", json={"bestaetigt": True}).json())
    # jeder Fehlerfall im Betrieb: derselbe Aufruf, dreizehn Antworten
    svc = LLMService(db)
    svc._status.last_check_at = 9999999999
    payload = {"profile_skills": ["Konstruktion"], "profile_position": "Konstrukteur", "profile_seniority": "Senior",
               "job_title": "Konstrukteur", "job_company": "Beispiel AG", "job_description": "Text. " * 30,
               "dismiss_reasons_top": [], "recent_dismissals": []}
    for _ in range(14):
        api_backend.pause_aufheben()
        erg = svc.run(TaskKind.MATCH_JOB_TO_SKILLS, payload)
        kanaele.merke({"backend": erg.backend.value, "ok": erg.success, "payload": erg.payload,
                       "meldung": erg.fallback_message, "metriken": erg.metrics})
        record_tool_call("api_weg_test", 0.01, "ok" if erg.success else "fehler", "", str(erg.fallback_message or ""))
        api_backend.pause_aufheben()
        validierung = svc.run(TaskKind.VALIDATE_JOB_QUALITY, {"title": "t", "description": "d" * 80})
        kanaele.merke({"ok": validierung.success, "meldung": validierung.fallback_message, "metriken": validierung.metrics})
    api_backend.pause_aufheben()
    kanaele.merke(api_backend.schluessel_pruefen(db))
    kanaele.merke(api_backend.uebersicht(db))
    tool("api_weg_pruefen", {"bestaetigt": True})
    tool("api_weg_anzeigen")
    # die Messprobe: Bericht, JSON-Datei, Konsole
    bericht = tmp_path / "probe.json"
    api_probe_ausgabe: list = []
    api_probe.main(["--demo", "--anzahl", "10"], ausgabe=api_probe_ausgabe.append)
    kanaele.merke(api_probe_ausgabe)
    transport_probe = _boesartiges_doppel()
    quelle = api_probe.demo_datenbank(tmp_path / "probe-quelle")
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    echte_ausgabe: list = []
    api_probe.main(["--quelle", str(quelle), "--anzahl", "10", "--senden", "--budget-usd", "1", "--ausgabe", str(bericht)],
                   ausgabe=echte_ausgabe.append, transport=transport_probe)
    kanaele.merke(echte_ausgabe)
    if bericht.exists():
        kanaele.merke(bericht.read_text(encoding="utf-8"))
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    return transport


def test_der_schluessel_taucht_auf_keinem_ausgabeweg_auf(umgebung, monkeypatch, tmp_path):
    db, kanaele = umgebung
    transport = _durchlaufen(db, kanaele, monkeypatch, tmp_path)
    assert transport.anzahl >= 14, "Der Weg ist wirklich gelaufen, mit den boesartigen Antworten"
    treffer = finde_schluessel(kanaele.sammeln())
    assert not treffer, f"Der Schluessel steht in: {treffer}"


def test_auch_die_pruefung_und_die_zaehler_in_der_datenbank_enthalten_ihn_nicht(umgebung):
    db, kanaele = umgebung
    api_backend.transport_setzen(FakeTransport(antwort("ok")))
    api_backend.einstellungen_setzen(db, aufgaben=["match_job_to_skills"], budget_usd=1, bestaetigt=True)
    api_backend.schluessel_pruefen(db)
    zeilen = db.connect().execute("SELECT key, value FROM settings WHERE key LIKE '%api%'").fetchall()
    assert zeilen, "Die Einstellungen des API-Wegs stehen in der Datenbank"
    assert not finde_schluessel({"settings": json.dumps([tuple(z) for z in zeilen])})


def test_in_der_datenbank_steht_nur_ein_fingerabdruck_der_pruefung(umgebung):
    db, _ = umgebung
    api_backend.schluessel_pruefen(db, transport=FakeTransport(antwort("ok")))
    gespeichert = db.get_setting(api_backend.S_PRUEFUNG)
    assert set(gespeichert) == {"ergebnis", "code", "zeit", "kennung"}
    assert len(gespeichert["kennung"]) == 12 and gespeichert["kennung"] not in TESTSCHLUESSEL


# ============================================================ Gegenprobe: der Pruefer schlaegt in JEDEM Kanal an

@pytest.mark.parametrize("kanal", ["datenbank", "sicherung", "export", "log", "telemetrie", "ausgaben", "konsole"])
def test_die_gegenprobe_der_schluessel_in_diesem_kanal_wird_gefunden(umgebung, kanal, capfd):
    db, kanaele = umgebung
    if kanal in ("datenbank", "sicherung"):
        db.set_setting("irgendwas", TESTSCHLUESSEL)
    elif kanal == "export":
        db.save_profile({"name": TESTSCHLUESSEL})
    elif kanal == "log":
        logging.getLogger("bewerbungs_assistent.api_backend").info("API-Weg: Schlüssel %s", TESTSCHLUESSEL)
    elif kanal == "telemetrie":
        record_tool_call("api_weg_test", 0.1, "fehler", "", f"Fehler mit {TESTSCHLUESSEL}")
    elif kanal == "ausgaben":
        kanaele.merke({"fehler": f"abgelehnt mit {TESTSCHLUESSEL}"})
    elif kanal == "konsole":
        print(f"Schlüssel: {TESTSCHLUESSEL}")
    treffer = finde_schluessel(kanaele.sammeln())
    assert treffer, f"Der Pruefer hat den Schluessel im Kanal {kanal} NICHT gefunden: ein Alibi"
    erwartet = {"datenbank": "dateien", "sicherung": "dateien", "export": "profil-export", "log": "log",
                "telemetrie": "telemetrie", "ausgaben": "ausgaben", "konsole": "konsole"}[kanal]
    assert any(erwartet in t for t in treffer), (kanal, treffer)


def test_die_gegenprobe_findet_auch_ein_stueck_des_schluessels():
    stueck = TESTSCHLUESSEL[10:40]
    assert finde_schluessel({"log": f"nur ein Teil: {stueck}"}) == ["log"]
    assert finde_schluessel({"log": TESTSCHLUESSEL[:10]}) == [], "Zehn Zeichen sind noch kein Schluessel (FENSTER = 16)"
    assert finde_schluessel({"datei": b"\x00" + TESTSCHLUESSEL.encode() + b"\x00"}) == ["datei"]
    assert finde_schluessel({"log": "alles harmlos"}) == []


def test_der_pruefer_liest_wirklich_den_ganzen_datenordner(umgebung, tmp_path):
    db, kanaele = umgebung
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "pbp.log").write_text(f"2026 INFO: {TESTSCHLUESSEL}\n", encoding="utf-8")
    assert "dateien im Datenordner (Datenbank, Sicherung, Log)" in finde_schluessel(kanaele.sammeln())
    with zipfile.ZipFile(tmp_path / "x.zip", "w") as z:
        z.writestr("innen.txt", TESTSCHLUESSEL)
    (tmp_path / "logs" / "pbp.log").unlink()
    assert "dateien im Datenordner (Datenbank, Sicherung, Log)" in finde_schluessel(kanaele.sammeln()), "auch in einem ZIP"
