"""v1.7.147 — Tempo: Stellenliste, Stellen-Tab und blockierende Endpunkte (#1143).

Drei Befunde vom 01.10.2026, gemessen auf isolierten Datenbanken:

1. `apply_scoring_adjustments` lud fuer JEDE Stelle alle Bewerbungen neu
   (Beworben-Bonus): 1.200 Stellen und 100 Bewerbungen kosteten 11,6 s je
   Aufruf von `stellen_anzeigen`, 3.973 Stellen 129 s. Mit einmal
   gebildeter Menge: 0,72 s, dieselbe Trefferliste.
2. Der Stellen-Tab zaehlte die Aussortierten mit `len(get_dismissed_jobs())`
   (ein `SELECT *` samt Anzeigentexten) und der 2-Sekunden-Takt fragte
   `MAX(updated_at)` ohne Index.
3. Lange Arbeit lief in `async`-Endpunkten auf der Ereignisschleife und hielt
   das ganze Dashboard an (Modell-Download 8 s -> Zweitanfrage 7,7 s).

Die Messtests haben Grenzwerte mit grossem Abstand und zaehlen zusaetzlich
Aufrufe: ein Zaehler ist auf jeder Maschine gleich, eine Uhr nicht.
Gegenprobe: scratchpad/n144/gegenprobe_1143.py.
"""
import ast
import asyncio
import importlib
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_tempo1143_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv
    importlib.reload(_srv)
    db = _srv.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Beispiel Person", "city": "Hamburg"})
    yield db, _srv.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def _bestand(db, stellen, bewerbungen):
    db.save_jobs([{
        "hash": f"tempo_{i:05d}", "title": f"Sachbearbeiter {i}",
        "company": f"Betrieb {i} GmbH", "url": f"https://example.com/s/{i}",
        "source": "bundesagentur" if i % 2 else "arbeitnow",
        "description": "Beschreibung der Stelle. " * 30, "score": 20 + (i % 40),
        "found_at": "2026-10-01T00:00:00",
    } for i in range(stellen)])
    for i in range(bewerbungen):
        db.add_application({"title": f"Sachbearbeiter {i * 3}",
                            "company": f"Betrieb {i * 3} GmbH", "status": "beworben",
                            "job_hash": f"tempo_{i * 3:05d}"})


def _zaehlen(monkeypatch, db, name):
    zaehler = {"n": 0}
    echt = getattr(type(db), name)

    def zaehlend(self, *a, **k):
        zaehler["n"] += 1
        return echt(self, *a, **k)
    monkeypatch.setattr(type(db), name, zaehlend)
    return zaehler


# ══ 1. Der Beworben-Bonus liest die Bewerbungen einmal ═════════════

def test_beworbene_stellen_sind_ein_select_und_dasselbe_wie_vorher(umgebung):
    db, _mcp = umgebung
    _bestand(db, 40, 8)
    erwartet = {a["job_hash"] for a in db.get_applications() if a.get("job_hash")}
    assert len(erwartet) == 8
    assert db.get_applied_job_hashes() == erwartet


def test_beworbene_stellen_gelten_je_profil(umgebung):
    db, _mcp = umgebung
    _bestand(db, 20, 4)
    erstes = db.get_active_profile_id()
    db.switch_profile(db.create_profile("Zweites"))
    # das zweite Profil sieht die Bewerbungen des ersten nicht
    assert db.get_applied_job_hashes() == {
        a["job_hash"] for a in db.get_applications() if a.get("job_hash")} == set()
    db.switch_profile(erstes)
    assert len(db.get_applied_job_hashes()) == 4


def test_der_bonus_ist_mit_und_ohne_menge_derselbe(umgebung):
    db, _mcp = umgebung
    db.set_scoring_config("remote", "remote", 5)   # ohne Regler rechnet die Funktion nichts
    _bestand(db, 40, 8)
    from bewerbungs_assistent.services.scoring_service import apply_scoring_adjustments
    beworbene = db.get_applied_job_hashes()
    mit_bonus = 0
    for j in db.get_active_jobs():
        ohne = apply_scoring_adjustments(dict(j), j["score"], db)
        mit = apply_scoring_adjustments(dict(j), j["score"], db, beworbene=beworbene)
        assert mit == ohne, j["hash"]
        if any(a.get("dimension") == "Beworben-Bonus" for a in mit["adjustments"]):
            mit_bonus += 1
            assert j["hash"] in beworbene
    assert mit_bonus == 8


def test_die_stellenliste_in_claude_liest_die_bewerbungen_nicht_je_stelle(umgebung, monkeypatch):
    db, mcp = umgebung
    db.set_scoring_config("remote", "remote", 5)
    _bestand(db, 300, 30)
    zaehler = _zaehlen(monkeypatch, db, "get_applications")
    menge = _zaehlen(monkeypatch, db, "get_applied_job_hashes")
    erg = _call(mcp, "stellen_anzeigen", {"pro_seite": 20, "ohne_schwelle": True})
    assert erg["angezeigt"] == 20, erg.get("hinweis")
    # vorher: einmal je Stelle (300). Jetzt: ein paar feste Stellen im Ablauf.
    assert zaehler["n"] <= 5, zaehler
    assert menge["n"] <= 3, menge


def test_ein_fehler_bei_den_beworbenen_stellen_schaltet_die_regler_nicht_ab(umgebung, monkeypatch):
    """Geht das Lesen der beworbenen Stellen schief, fehlt hoechstens der
    Beworben-Bonus - die Regler (hier: die Score-Schwelle) wirken weiter.
    Vorher haette der aeussere Fangblock der Liste alle Anpassungen
    verworfen, und Stellen unter der Schwelle waeren wieder aufgetaucht."""
    db, mcp = umgebung
    db.set_scoring_config("schwellenwert", "auto_ignore", 40)
    _bestand(db, 40, 3)
    normal = _call(mcp, "stellen_anzeigen", {"pro_seite": 50})
    verborgen = normal.get("durch_schwelle_verborgen") or (40 - normal["anzahl_gesamt"])
    assert verborgen > 0, normal.get("hinweis")

    def kaputt(self):
        raise RuntimeError("Datenbank gesperrt")
    monkeypatch.setattr(type(db), "get_applied_job_hashes", kaputt)
    gestoert = _call(mcp, "stellen_anzeigen", {"pro_seite": 50})
    assert gestoert["anzahl_gesamt"] == normal["anzahl_gesamt"], (
        normal["anzahl_gesamt"], gestoert["anzahl_gesamt"])


def test_der_stellen_tab_liest_die_bewerbungen_nicht_je_stelle(umgebung, monkeypatch):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    db, _mcp = umgebung
    db.set_scoring_config("remote", "remote", 5)
    _bestand(db, 300, 30)
    monkeypatch.setattr(dash, "_db", db)
    zaehler = _zaehlen(monkeypatch, db, "get_applications")
    menge = _zaehlen(monkeypatch, db, "get_applied_job_hashes")
    antwort = TestClient(dash.app).get("/api/jobs?limit=12")
    assert antwort.status_code == 200
    assert zaehler["n"] <= 10, zaehler
    assert menge["n"] <= 3, menge


def test_messtest_stellenliste_mit_grossem_bestand(umgebung):
    """1.200 Stellen und 100 Bewerbungen: vorher 11,6 s (hier gemessen 5,2 s),
    jetzt 0,3 s. Grenzwert 3 s: zehnfacher Abstand zum Messwert, damit eine
    langsame Maschine nicht stoert, und doch unter dem alten Wert."""
    db, mcp = umgebung
    db.set_scoring_config("remote", "remote", 5)
    _bestand(db, 1200, 100)
    t0 = time.perf_counter()
    erg = _call(mcp, "stellen_anzeigen", {"pro_seite": 20, "ohne_schwelle": True})
    dauer = time.perf_counter() - t0
    assert erg["angezeigt"] == 20, erg.get("hinweis")
    assert dauer < 3.0, f"stellen_anzeigen brauchte {dauer:.1f} s"


# ══ 2. Der Stellen-Tab: zaehlen statt laden, Index statt Durchsuchen ═

def test_aussortierte_werden_gezaehlt_nicht_geladen(umgebung, monkeypatch):
    import bewerbungs_assistent.dashboard as dash
    db, _mcp = umgebung
    _bestand(db, 30, 0)
    for i in range(12):
        db.dismiss_job(f"tempo_{i:05d}", reason="sonstiges")
    assert db.count_dismissed_jobs() == len(db.get_dismissed_jobs()) == 12
    monkeypatch.setattr(dash, "_db", db)

    def verboten(self):
        raise AssertionError("get_dismissed_jobs darf fuer die Zahl nicht laufen")
    monkeypatch.setattr(type(db), "get_dismissed_jobs", verboten)
    assert dash._aussortiert_zaehlen() == 12


def test_aussortierte_zaehlt_je_profil(umgebung):
    db, _mcp = umgebung
    _bestand(db, 10, 0)
    db.dismiss_job("tempo_00001", reason="sonstiges")
    erstes = db.get_active_profile_id()
    db.switch_profile(db.create_profile("Zweites"))
    assert db.count_dismissed_jobs() == 0
    db.switch_profile(erstes)
    assert db.count_dismissed_jobs() == 1


def test_der_zeitstempel_der_stellen_hat_einen_index(umgebung):
    db, _mcp = umgebung
    con = db.connect()
    namen = {r["name"] for r in con.execute("PRAGMA index_list(jobs)")}
    assert "idx_jobs_updated_at" in namen
    plan = " ".join(str(tuple(r)) for r in con.execute(
        "EXPLAIN QUERY PLAN SELECT COALESCE(MAX(updated_at), '') FROM jobs"))
    assert "idx_jobs_updated_at" in plan, plan


def test_der_index_kommt_auch_in_bestehende_datenbanken(umgebung):
    db, _mcp = umgebung
    con = db.connect()
    con.execute("DROP INDEX IF EXISTS idx_jobs_updated_at")
    con.commit()
    db.initialize()
    namen = {r["name"] for r in db.connect().execute("PRAGMA index_list(jobs)")}
    assert "idx_jobs_updated_at" in namen


# ══ 3. Lange Arbeit haelt das Dashboard nicht an ═══════════════════

DAUER = 1.5          # so lange arbeitet der langsame Aufruf
SCHNELL = 0.7        # so schnell muss die Zweitanfrage trotzdem antworten


async def _zweitanfrage(app, langsam):
    """Startet `langsam(client)` und fragt 0,15 s spaeter den Token ab.
    Liefert (Dauer der Zweitanfrage, Dauer des langsamen Aufrufs)."""
    import httpx
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://testserver") as c:
        t0 = time.perf_counter()

        async def lang():
            await langsam(c)
            return time.perf_counter() - t0

        async def schnell():
            await asyncio.sleep(0.15)
            t1 = time.perf_counter()
            antwort = await c.get("/api/live-update-token")
            assert antwort.status_code == 200
            return time.perf_counter() - t1
        t_lang, t_schnell = await asyncio.gather(lang(), schnell())
    return t_schnell, t_lang


def _schlafen(*_a, **_k):
    time.sleep(DAUER)


@pytest.fixture
def dash_app(umgebung, monkeypatch):
    import bewerbungs_assistent.dashboard as dash
    db, _mcp = umgebung
    monkeypatch.setattr(dash, "_db", db)
    return dash, db


def _pruefen(dash, langsam):
    t_schnell, t_lang = asyncio.run(_zweitanfrage(dash.app, langsam))
    assert t_lang >= DAUER - 0.1, f"der langsame Aufruf lief gar nicht ({t_lang:.2f} s)"
    assert t_schnell < SCHNELL, (
        f"die Zweitanfrage wartete {t_schnell:.2f} s - die Ereignisschleife war blockiert")


def test_standort_setzen_haelt_das_dashboard_nicht_an(dash_app, monkeypatch):
    dash, _db = dash_app
    from bewerbungs_assistent.services import eigener_standort
    monkeypatch.setattr(eigener_standort, "eigenen_setzen",
                        lambda db, ort: (_schlafen(), {"status": "ok"})[1])
    monkeypatch.setattr(eigener_standort, "befund", lambda db: {})

    async def langsam(c):
        r = await c.put("/api/standort", json={"ort": "Hamburg"})
        assert r.status_code == 200, r.text
    _pruefen(dash, langsam)


def test_modell_download_haelt_das_dashboard_nicht_an(dash_app, monkeypatch):
    dash, _db = dash_app
    from bewerbungs_assistent.services import llm_service

    class Falsch:
        def start_pull_job(self, modell):
            _schlafen()
            return {"job_id": "x", "status": "gestartet", "model": modell}

        def get_status(self, force_refresh=False):
            return {}
    monkeypatch.setattr(llm_service, "get_llm_service", lambda db: Falsch())

    async def langsam(c):
        r = await c.post("/api/llm/pull", json={"model": "beispiel:1b"})
        assert r.status_code == 202, r.text
    _pruefen(dash, langsam)


def test_warmup_haelt_das_dashboard_nicht_an(dash_app, monkeypatch):
    dash, _db = dash_app
    from bewerbungs_assistent.services import llm_service

    class Falsch:
        def warmup(self):
            _schlafen()
            return {"status": "ok"}
    monkeypatch.setattr(llm_service, "get_llm_service", lambda db: Falsch())

    async def langsam(c):
        r = await c.post("/api/llm/warmup")
        assert r.status_code == 200, r.text
    _pruefen(dash, langsam)


def test_auto_engine_haelt_das_dashboard_nicht_an(dash_app, monkeypatch):
    dash, _db = dash_app
    monkeypatch.setattr(dash, "_run_auto_actions_inner",
                        lambda now: (_schlafen(), {"status": "ok"})[1])

    async def langsam(c):
        r = await c.post("/api/auto-actions/run")
        assert r.status_code == 200, r.text
    _pruefen(dash, langsam)


def test_beschreibung_nachladen_haelt_das_dashboard_nicht_an(dash_app, monkeypatch):
    dash, db = dash_app
    db.save_jobs([{"hash": "nachladen_1143", "title": "Planer", "company": "Betrieb GmbH",
                   "url": "https://example.com/stelle", "source": "manuell",
                   "description": "", "score": 10, "found_at": "2026-10-01T00:00:00"}])
    from bewerbungs_assistent.services import nachladen

    def langsam_holen(*a, **k):
        _schlafen()
        raise RuntimeError("Netz weg")
    monkeypatch.setattr(nachladen, "beschreibung_holen", langsam_holen)

    async def langsam(c):
        r = await c.post("/api/jobs/nachladen_1143/refetch-description")
        assert r.status_code == 502, r.text
    _pruefen(dash, langsam)


def test_ordner_import_haelt_das_dashboard_nicht_an(dash_app, monkeypatch, tmp_path):
    dash, _db = dash_app
    ordner = tmp_path / "unterlagen"
    ordner.mkdir()
    (ordner / "notiz.txt").write_text("Ein Text, der lang genug ist, um etwas zu sein. " * 3,
                                      encoding="utf-8")
    echt = dash._extract_document_text

    def langsam_lesen(pfad, *a, **k):
        _schlafen()
        return echt(pfad, *a, **k)
    monkeypatch.setattr(dash, "_extract_document_text", langsam_lesen)

    async def langsam(c):
        r = await c.post("/api/documents/import-folder",
                         json={"folder_path": str(ordner), "import_applications": False})
        assert r.status_code == 200, r.text
    _pruefen(dash, langsam)


# ══ 4. Der Guard: kein blockierender Aufruf direkt in einem async-Endpunkt ═

BLOCKIEREND = re.compile(
    r"^(httpx\.(Client|get|post|put|delete)|urllib\.request\.urlopen|time\.sleep|_time\.sleep"
    r"|subprocess\.\w+|shutil\.(copy2|copytree|rmtree|make_archive)"
    r"|svc\.(start_pull_job|warmup|run|get_status)|ollama_start\.\w+|_extract_document_text"
    r"|eigener_standort\.(eigenen_setzen|befund)|_run_auto_actions_inner"
    r"|_run_analyze_user_patterns|_import_folder|_refresh_freelancermap_descriptions|_laden)$")


def _eigene_aufrufe(knoten):
    """Die Aufrufe eines Endpunkts - ohne die Rumpfe verschachtelter Funktionen
    (die laufen woanders, etwa als Argument von run_in_threadpool)."""
    stapel = list(ast.iter_child_nodes(knoten))
    while stapel:
        k = stapel.pop()
        if isinstance(k, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(k, ast.Call):
            yield k
        stapel.extend(ast.iter_child_nodes(k))


def _blockierende_endpunkte(quelle: str):
    befunde = []
    for n in ast.parse(quelle).body:
        if not isinstance(n, ast.AsyncFunctionDef):
            continue
        if not any(ast.unparse(d).startswith("app.") for d in n.decorator_list):
            continue
        for k in _eigene_aufrufe(n):
            name = ast.unparse(k.func)
            if BLOCKIEREND.match(name):
                befunde.append((n.name, name, k.lineno))
    return befunde


def test_kein_async_endpunkt_ruft_blockierende_arbeit_direkt_auf():
    """Ein Aufruf, der auf Netz, Platte oder die lokale KI wartet, gehoert
    nicht auf die Ereignisschleife: `def` statt `async def`, oder
    `await run_in_threadpool(...)`. Neue Endpunkte fallen hier auf."""
    quelle = (ROOT / "src" / "bewerbungs_assistent" / "dashboard.py").read_text(encoding="utf-8-sig")
    befunde = _blockierende_endpunkte(quelle)
    assert not befunde, befunde


def test_der_guard_sieht_etwas():
    schlecht = (
        "@app.post('/x')\n"
        "async def x(request):\n"
        "    data = await request.json()\n"
        "    with httpx.Client() as c:\n"
        "        c.get('u')\n"
        "@app.post('/y')\n"
        "async def y():\n"
        "    return await run_in_threadpool(svc.start_pull_job, 'm')\n"
        "@app.post('/z')\n"
        "def z():\n"
        "    time.sleep(1)\n"
    )
    assert _blockierende_endpunkte(schlecht) == [("x", "httpx.Client", 4)]


def test_lern_analyse_gibt_die_werte_weiter_und_antwortet(dash_app, monkeypatch):
    """Der Endpunkt hatte keinen Test; er laeuft jetzt im Thread-Pool."""
    from fastapi.testclient import TestClient
    dash, _db = dash_app
    gesehen = {}

    def falsch(jetzt, days=0, min_events=0):
        gesehen.update(days=days, min_events=min_events, jetzt=jetzt)
        return {"status": "ok", "tage": days}
    monkeypatch.setattr(dash, "_run_analyze_user_patterns", falsch)
    r = TestClient(dash.app).post("/api/learning/analyze", json={"days": 7, "min_events": 5})
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "ok", "tage": 7}
    assert gesehen["days"] == 7 and gesehen["min_events"] == 5 and gesehen["jetzt"]
    # ohne Koerper: die Vorgaben
    r = TestClient(dash.app).post("/api/learning/analyze")
    assert r.status_code == 200 and gesehen["days"] == 30 and gesehen["min_events"] == 50
