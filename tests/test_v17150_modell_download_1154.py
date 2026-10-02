"""#1154 Punkt 1 — der Modell-Download hat einen Fortschritt und bricht nicht nach zehn Minuten ab.

Befund (01.10.2026): `POST /api/llm/pull` wartete in einem einzigen Aufruf auf das Ende des Downloads
(`stream: false`, Zeitgrenze 600 s). Die Oberfläche zeigte nur „Laedt…“, und bei einem großen Modell
oder einer langsamen Leitung meldete sie nach zehn Minuten „Download fehlgeschlagen“, obwohl Ollama
weiterlud.

Jetzt ist der Download ein Hintergrund-Job (`services/modell_download`): der Aufruf antwortet sofort mit
der Kennung, der Job liest Ollamas Stream (`stream: true`) und schreibt Prozent und einen Satz in
`background_jobs`, und es gibt nur noch eine Stillstandsgrenze statt einer Gesamt-Zeitgrenze.

Die Tests sprechen mit einem kleinen Falsch-Ollama (ein HTTP-Server auf einem freien Port). Kein Test
berührt das echte Ollama oder lädt etwas.
"""
import importlib
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# ══ Das Falsch-Ollama ═════════════════════════════════════════════════════════

class FalschesOllama:
    """Ahmt `POST /api/pull` nach: eine JSON-Zeile je Schritt, ohne Längenangabe."""

    def __init__(self, zeilen, pause=0.0, haengt_danach=0.0):
        self.zeilen, self.pause, self.haengt_danach = zeilen, pause, haengt_danach
        self.anfragen = []
        aussen = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # still
                pass

            def do_POST(self):
                laenge = int(self.headers.get("Content-Length") or 0)
                aussen.anfragen.append((self.path, json.loads(self.rfile.read(laenge) or b"{}")))
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.send_header("Connection", "close")
                self.end_headers()
                for z in aussen.zeilen:
                    # Bytes gehen unveraendert hinaus (fuer Zeilen, die kein JSON sind)
                    roh = z if isinstance(z, bytes) else json.dumps(z).encode("utf-8")
                    self.wfile.write(roh + b"\n")
                    self.wfile.flush()
                    if aussen.pause:
                        time.sleep(aussen.pause)
                if aussen.haengt_danach:
                    time.sleep(aussen.haengt_danach)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def guter_ablauf(gb=4):
    total = gb * 1024 ** 3
    zeilen = [{"status": "pulling manifest"}]
    for anteil in (0.2, 0.5, 0.8, 1.0):
        zeilen.append({"status": "pulling abc123", "digest": "sha256:abc123", "total": total,
                       "completed": int(total * anteil)})
    zeilen += [{"status": "verifying sha256 digest"}, {"status": "writing manifest"}, {"status": "success"}]
    return zeilen


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17150_1154_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    from bewerbungs_assistent.services import modell_download
    yield db, modell_download
    modell_download.warten(30)   # die Threads enden, bevor die Datenbank schliesst
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture
def ollama():
    erzeugt = []

    def bauen(*a, **k):
        o = FalschesOllama(*a, **k)
        erzeugt.append(o)
        return o
    yield bauen
    for o in erzeugt:
        o.stop()


def _job(db, job_id):
    return db.get_background_job(job_id)


def _fertig_warten(modell_download):
    modell_download.warten(30)


# ══ Die Rechnung ══════════════════════════════════════════════════════════════

def test_1154_aus_total_und_completed_wird_prozent_und_ein_satz(umgebung):
    db, md = umgebung
    f = md.Fortschritt()
    f.zeile({"status": "pulling manifest"})
    assert f.prozent == 0 and "Liste der Teile" in f.text
    f.zeile({"status": "pulling a", "digest": "sha256:a", "total": 4 * 1024 ** 3, "completed": 1024 ** 3})
    assert f.prozent == 25
    assert "1.0 von 4.0 GB" in f.text and "25 %" in f.text


def test_1154_die_prozentzahl_geht_nie_rueckwaerts(umgebung):
    """Ein weiterer Teil kommt dazu und senkt den Anteil: die Anzeige bleibt stehen, statt zu springen."""
    db, md = umgebung
    f = md.Fortschritt()
    f.zeile({"status": "pulling a", "digest": "sha256:a", "total": 100, "completed": 100})
    assert f.prozent == 99
    vorher = f.prozent
    f.zeile({"status": "pulling b", "digest": "sha256:b", "total": 900, "completed": 0})
    assert f.prozent == vorher


def test_1154_hundert_prozent_erst_bei_success(umgebung):
    db, md = umgebung
    f = md.Fortschritt()
    f.zeile({"status": "pulling a", "digest": "sha256:a", "total": 100, "completed": 100})
    assert f.prozent <= 99, "danach folgen noch Pruefen und Schreiben"
    f.zeile({"status": "verifying sha256 digest"})
    assert f.prozent <= 99 and "Prüfe" in f.text
    f.zeile({"status": "writing manifest"})
    assert "Schreibe" in f.text
    f.zeile({"status": "success"})
    assert f.prozent == 100 and f.text == "Fertig."


def test_1154_eine_zeile_ohne_groesse_aendert_die_prozentzahl_nicht(umgebung):
    db, md = umgebung
    f = md.Fortschritt()
    f.zeile({"status": "irgendwas Neues von Ollama"})
    assert f.prozent == 0 and f.text == "irgendwas Neues von Ollama"


# ══ Der Job ═══════════════════════════════════════════════════════════════════

def test_1154_der_aufruf_antwortet_sofort_und_der_job_laeuft_im_hintergrund(umgebung, ollama):
    db, md = umgebung
    o = ollama(guter_ablauf(), pause=0.15)
    t0 = time.monotonic()
    antwort = md.starten(db, o.url, "beispiel:1b")
    assert time.monotonic() - t0 < 0.5, "der Aufruf wartete auf den Download"
    assert antwort["status"] == "gestartet" and antwort["model"] == "beispiel:1b" and antwort["job_id"]
    assert _job(db, antwort["job_id"])["status"] == "running"
    _fertig_warten(md)
    job = _job(db, antwort["job_id"])
    assert job["status"] == "fertig" and job["progress"] == 100
    assert job["result"] == {"model": "beispiel:1b"}


def test_1154_ollama_bekommt_stream_true(umgebung, ollama):
    """Mit `stream: false` gibt es keinen Fortschritt - das war der Fehler."""
    db, md = umgebung
    o = ollama(guter_ablauf())
    md.starten(db, o.url, "beispiel:1b")
    _fertig_warten(md)
    assert o.anfragen == [("/api/pull", {"name": "beispiel:1b", "stream": True})]


def test_1154_zwischenstaende_landen_im_job(umgebung, ollama, monkeypatch):
    db, md = umgebung
    stand = []
    original = db.update_background_job

    def merken(job_id, status, progress=0, message="", result=None):
        stand.append((status, progress, message))
        return original(job_id, status, progress=progress, message=message, result=result)
    monkeypatch.setattr(db, "update_background_job", merken)
    monkeypatch.setattr(md, "SCHREIB_ABSTAND_S", 0.0)
    o = ollama(guter_ablauf())
    md.starten(db, o.url, "beispiel:1b")
    _fertig_warten(md)
    laufend = [s for s in stand if s[0] == "running"]
    prozente = [p for _, p, _ in laufend]
    assert prozente == sorted(prozente), "Prozentzahl springt zurueck"
    assert any(0 < p < 100 for p in prozente), stand
    assert any("GB" in m for _, _, m in laufend)
    assert stand[-1][0] == "fertig" and stand[-1][1] == 100


def test_1154_ein_gemeldeter_fehler_von_ollama_steht_im_job(umgebung, ollama):
    db, md = umgebung
    o = ollama([{"status": "pulling manifest"}, {"error": "pull model manifest: file does not exist"}])
    a = md.starten(db, o.url, "gibtes:nicht")
    _fertig_warten(md)
    job = _job(db, a["job_id"])
    assert job["status"] == "fehler"
    assert "unter diesem Namen nicht" in job["message"] and "Prüfe den Namen" in job["message"]
    assert md.job_beschreiben(job)["error"] == job["message"]


def test_1154_ein_anderer_fehler_von_ollama_wird_wiedergegeben(umgebung, ollama):
    db, md = umgebung
    o = ollama([{"error": "Platte voll"}])
    a = md.starten(db, o.url, "beispiel:1b")
    _fertig_warten(md)
    job = _job(db, a["job_id"])
    assert job["status"] == "fehler" and "Ollama meldet: Platte voll" in job["message"]


def test_1154_ist_ollama_nicht_da_sagt_der_job_es(umgebung):
    db, md = umgebung
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        frei = s.getsockname()[1]
    a = md.starten(db, f"http://127.0.0.1:{frei}", "beispiel:1b")
    _fertig_warten(md)
    job = _job(db, a["job_id"])
    assert job["status"] == "fehler"
    assert "nicht erreichbar" in job["message"]


def test_1154_ein_ersetztes_urlopen_wird_benutzt_nie_das_echte_ollama(umgebung):
    """`urlopen` wird beim Aufruf nachgeschlagen, nicht als Vorgabewert gebunden. Sonst griffe ein Test, der
    es ersetzt, ins Leere - und auf einem Rechner mit laufendem Ollama würde er ein echtes Modell laden."""
    from unittest.mock import patch
    db, md = umgebung
    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("ollama down")) as falsch:
        a = md.starten(db, "http://127.0.0.1:9", "beispiel:1b")
        _fertig_warten(md)
    assert falsch.call_count == 1
    job = _job(db, a["job_id"])
    assert job["status"] == "fehler" and "nicht erreichbar" in job["message"]


def test_1154_ein_stehender_download_endet_nach_der_stillstandsgrenze(umgebung, ollama):
    """Keine Gesamt-Zeitgrenze mehr, aber wer lange nichts hoert, gibt auf - mit klarem Satz."""
    db, md = umgebung
    o = ollama([{"status": "pulling manifest"}], haengt_danach=6.0)
    t0 = time.monotonic()
    a = md.starten(db, o.url, "beispiel:1b", stillstand_s=1.0)
    _fertig_warten(md)
    assert time.monotonic() - t0 < 5.5
    job = _job(db, a["job_id"])
    assert job["status"] == "fehler"
    assert "keine Daten mehr" in job["message"] and "bleiben erhalten" in job["message"]


def test_1154_ein_langer_download_ohne_unterbrechung_laeuft_ueber_die_stillstandsgrenze_hinaus(umgebung, ollama):
    """Ein Download darf beliebig lange dauern, solange Zeilen kommen."""
    db, md = umgebung
    zeilen = [{"status": "pulling manifest"}] + [
        {"status": "pulling a", "digest": "sha256:a", "total": 1000, "completed": i * 100} for i in range(1, 11)
    ] + [{"status": "success"}]
    o = ollama(zeilen, pause=0.25)          # insgesamt rund 3 s
    a = md.starten(db, o.url, "beispiel:1b", stillstand_s=1.0)
    _fertig_warten(md)
    assert _job(db, a["job_id"])["status"] == "fertig"


def test_1154_endet_der_strom_ohne_success_ist_es_ein_fehler(umgebung, ollama):
    db, md = umgebung
    o = ollama([{"status": "pulling manifest"},
                {"status": "pulling a", "digest": "sha256:a", "total": 100, "completed": 50}])
    a = md.starten(db, o.url, "beispiel:1b")
    _fertig_warten(md)
    job = _job(db, a["job_id"])
    assert job["status"] == "fehler" and "ohne Erfolg zu melden" in job["message"]


def test_1154_unlesbare_zeilen_werden_uebersprungen(umgebung, ollama):
    db, md = umgebung
    o = ollama(guter_ablauf())
    o.zeilen = o.zeilen[:2] + [b"das ist kein JSON", b'"auch kein Objekt"', b"[1, 2]"] + o.zeilen[2:]
    a = md.starten(db, o.url, "beispiel:1b")
    _fertig_warten(md)
    assert _job(db, a["job_id"])["status"] == "fertig"


def test_1154_ein_zweiter_start_waehrend_des_laufs_startet_keinen_zweiten_download(umgebung, ollama):
    db, md = umgebung
    o = ollama(guter_ablauf(), pause=0.2)
    a = md.starten(db, o.url, "beispiel:1b")
    b = md.starten(db, o.url, "beispiel:1b")
    c = md.starten(db, o.url, "anderes:7b")
    assert b["status"] == "laeuft_schon" and b["job_id"] == a["job_id"] and b["gleiches_modell"] is True
    assert c["status"] == "laeuft_schon" and c["job_id"] == a["job_id"] and c["gleiches_modell"] is False
    assert c["model"] == "beispiel:1b"
    _fertig_warten(md)
    assert len(o.anfragen) == 1, "Ollama bekam mehrere Downloads"


def test_1154_nach_dem_ende_kann_ein_neuer_download_starten(umgebung, ollama):
    db, md = umgebung
    o = ollama(guter_ablauf())
    a = md.starten(db, o.url, "beispiel:1b")
    _fertig_warten(md)
    b = md.starten(db, o.url, "beispiel:1b")
    assert b["status"] == "gestartet" and b["job_id"] != a["job_id"]
    _fertig_warten(md)


def test_1154_nach_dem_erfolg_wird_der_status_neu_gelesen(umgebung, ollama):
    db, md = umgebung
    gerufen = []
    o = ollama(guter_ablauf())
    md.starten(db, o.url, "beispiel:1b", nach_erfolg=lambda: gerufen.append(1))
    _fertig_warten(md)
    assert gerufen == [1]


def test_1154_nach_einem_fehler_wird_nichts_neu_gelesen(umgebung, ollama):
    db, md = umgebung
    gerufen = []
    o = ollama([{"error": "kaputt"}])
    md.starten(db, o.url, "beispiel:1b", nach_erfolg=lambda: gerufen.append(1))
    _fertig_warten(md)
    assert gerufen == []


def test_1154_ein_fehler_im_nachlauf_macht_den_gelungenen_download_nicht_zum_fehler(umgebung, ollama):
    db, md = umgebung

    def kaputt():
        raise RuntimeError("Status nicht lesbar")
    o = ollama(guter_ablauf())
    a = md.starten(db, o.url, "beispiel:1b", nach_erfolg=kaputt)
    _fertig_warten(md)
    assert _job(db, a["job_id"])["status"] == "fertig"


def test_1154_die_beschreibung_fuer_die_oberflaeche(umgebung, ollama):
    db, md = umgebung
    assert md.job_beschreiben(None) is None
    o = ollama(guter_ablauf())
    a = md.starten(db, o.url, "beispiel:1b")
    _fertig_warten(md)
    b = md.job_beschreiben(_job(db, a["job_id"]))
    assert b == {"job_id": a["job_id"], "model": "beispiel:1b", "status": "fertig", "progress": 100,
                 "message": "Fertig.", "error": None}


# ══ Die Endpunkte ═════════════════════════════════════════════════════════════

@pytest.fixture
def dashboard(umgebung, ollama):
    db, md = umgebung
    import bewerbungs_assistent.services.llm_service as _llm_mod
    importlib.reload(_llm_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    _dash_mod._db = db
    from fastapi.testclient import TestClient
    o = ollama(guter_ablauf(), pause=0.1)
    svc = _llm_mod.get_llm_service(db)
    svc._status.ollama_endpoint = o.url
    yield TestClient(_dash_mod.app), md, db, o


def test_1154_post_antwortet_mit_202_und_der_kennung(dashboard):
    client, md, db, o = dashboard
    r = client.post("/api/llm/pull", json={"model": "beispiel:1b"})
    assert r.status_code == 202
    j = r.json()
    assert j["status"] == "gestartet" and j["model"] == "beispiel:1b" and j["job_id"]
    md.warten(30)


def test_1154_nach_dem_download_ueber_den_endpunkt_wird_der_status_neu_gelesen(dashboard):
    """Das neue Modell muss in der Oberflaeche erscheinen, ohne dass jemand die Seite neu laedt."""
    client, md, db, o = dashboard
    import bewerbungs_assistent.services.llm_service as _llm_mod
    svc = _llm_mod.get_llm_service(db)
    gerufen = []
    original = svc.get_status
    svc.get_status = lambda force_refresh=False: (gerufen.append(force_refresh), original(force_refresh))[1]
    client.post("/api/llm/pull", json={"model": "beispiel:1b"})
    md.warten(30)
    assert True in gerufen, "der Status wurde nach dem Download nicht neu gelesen"


def test_1154_get_nennt_den_laufenden_download_und_danach_keinen(dashboard):
    client, md, db, o = dashboard
    assert client.get("/api/llm/pull").json() == {"job": None}
    a = client.post("/api/llm/pull", json={"model": "beispiel:1b"}).json()
    laufend = client.get("/api/llm/pull").json()["job"]
    assert laufend["job_id"] == a["job_id"] and laufend["status"] == "running"
    md.warten(30)
    assert client.get("/api/llm/pull").json() == {"job": None}


def test_1154_der_stand_eines_jobs_ist_abrufbar(dashboard):
    client, md, db, o = dashboard
    a = client.post("/api/llm/pull", json={"model": "beispiel:1b"}).json()
    md.warten(30)
    s = client.get(f"/api/llm/pull/{a['job_id']}").json()
    assert s["status"] == "fertig" and s["progress"] == 100 and s["model"] == "beispiel:1b"


def test_1154_ein_unbekannter_job_ist_404(dashboard):
    client, md, db, o = dashboard
    assert client.get("/api/llm/pull/gibtesnicht").status_code == 404


def test_1154_ein_job_anderer_art_wird_nicht_ausgeliefert(dashboard):
    client, md, db, o = dashboard
    fremd = db.create_background_job("jobsuche", {"x": 1})
    assert client.get(f"/api/llm/pull/{fremd}").status_code == 404


def test_1154_ohne_modellnamen_ist_400(dashboard):
    client, md, db, o = dashboard
    assert client.post("/api/llm/pull", json={}).status_code == 400
    assert client.post("/api/llm/pull", json={"model": "  "}).status_code == 400


def test_1154_der_alte_synchrone_weg_ist_weg():
    from bewerbungs_assistent.services.llm_service import LLMService
    assert not hasattr(LLMService, "trigger_pull")
    assert hasattr(LLMService, "start_pull_job")


# ══ Die Oberfläche ════════════════════════════════════════════════════════════

WURZEL = Path(__file__).resolve().parents[1]


def test_1154_der_node_test_der_oberflaeche_laeuft_in_der_ci():
    ci = (WURZEL / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "node frontend/src/lib/modellDownload.test.mjs" in ci


def test_1154_die_einstellungsseite_fragt_den_job_ab_und_wartet_nicht_auf_das_ende():
    quelle = (WURZEL / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    assert "downloadVerfolgen" in quelle and "/api/llm/pull/${id}" in quelle
    assert "<ModellFortschritt" in quelle
    assert "das kann einige Minuten dauern" not in quelle
    assert 'result?.status === "error"' not in quelle, "der POST ist nicht mehr das Ergebnis des Downloads"
    # Beim Laden der Seite wird ein laufender Download wieder aufgenommen.
    assert 'api("/api/llm/pull")' in quelle


def test_1154_die_gebaute_oberflaeche_gehoert_zum_quelltext():
    assets = list((WURZEL / "src" / "bewerbungs_assistent" / "static" / "dashboard" / "assets").glob("index-*.js"))
    assert assets, "keine gebaute Oberflaeche"
    assert any("modell-fortschritt" in a.read_text(encoding="utf-8") for a in assets), \
        "die Oberflaeche wurde nach der Aenderung nicht neu gebaut (pnpm exec vite build)"
