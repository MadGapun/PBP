"""#1407 — Stellen-Tab 52 s: Schwellen-Stufen je Stelle neu gerechnet, Event-Loop blockiert.

Befund (19.11.2026, v1.8.7, 56 aktive und 4.463 aussortierte Stellen): /api/jobs
brauchte 51,8 s. Ursache 1: `get_search_criteria()` -> `schwellen_stufen.wert_fuer`
-> `stufen()` -> `fachwert._fachwerte(beworben=False)` las je Aufruf ALLE
Aussortierten samt Anzeigentexten (`get_dismissed_jobs`); `_mit_scoring_reglern`
rief das je Stelle mehrfach (159 mal je 0,34 s). Ursache 2: 153 lesende Endpunkte
waren `async def` mit synchronem SQLite und hielten den Event-Loop an.

Gemessen auf dem synthetischen Bestand dieser Datei (60 aktiv, 1.500 aussortiert,
2 KB Text, 126 Bewerbungen) steht die Zeit vorher/nachher in der PR-Beschreibung.
Die Grenzwerte hier liegen weit ueber dem Ist-Wert; was zaehlt, sind die Aufruf-
zaehler, die auf jeder Maschine gleich sind.

Gegenprobe: Cache in `stufen` ausbauen (-> Zaehlertest rot), `_fachwerte` auf
`get_dismissed_jobs` zurueckstellen (-> Aufruftest rot), ein lesender Endpunkt
wieder `async def` (-> Waechter und Parallelitaetstest rot).
"""
import ast
import asyncio
import importlib
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

N_AKTIV, N_AUSSORTIERT, N_BEWERBUNGEN = 60, 1500, 126


@pytest.fixture(scope="module")
def bestand():
    tmpdir = tempfile.mkdtemp(prefix="pbp_perf1407_")
    vorher = os.environ.get("BA_DATA_DIR")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Beispiel Person", "city": "Hamburg"})
    text = ("Beispieltext " * 160)[:2048]
    scores = [0, 0, 1, 2, 3, 5, 8, 13, 21, 34]

    def anlegen(n, praefix):
        db.save_jobs([{
            "hash": f"{praefix}{i:05d}", "title": f"Ingenieur {i}",
            "company": f"Firma {i % 300}",
            "url": f"https://example.com/{praefix}/{i}", "source": "bundesagentur",
            "description": text, "score": scores[(i * 7) % len(scores)],
            "found_at": "2026-10-01T00:00:00"} for i in range(n)])

    anlegen(N_AKTIV, "akt")
    anlegen(N_AUSSORTIERT, "aus")
    conn = db.connect()
    conn.execute("UPDATE jobs SET is_active=0, dismiss_reason='falsches_fachgebiet' "
                 "WHERE hash LIKE '%:aus%' OR hash LIKE 'aus%'")
    conn.commit()
    for i in range(N_BEWERBUNGEN):
        db.add_application({"job_hash": f"aus{i:05d}", "title": f"Ingenieur {i}",
                            "company": f"Firma {i}", "status": "beworben"})
    db.set_profile_setting("schwelle_stufe_liste", "ausgewogen")
    db.set_profile_setting("schwelle_stufe_speichern", "locker")
    yield db
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    if vorher is None:
        os.environ.pop("BA_DATA_DIR", None)
    else:
        os.environ["BA_DATA_DIR"] = vorher


# ------------------------------------------------------------- alte Rechnung


def _fachwerte_alt(db, beworben):
    """Die Fassung bis 1.8.7, woertlich (Gegenstueck fuer den Vergleich)."""
    werte = []
    if beworben:
        for bew in db.get_applications() or []:
            hash_ = bew.get("job_hash")
            if not hash_:
                continue
            stelle = db.get_job(hash_)
            if stelle and stelle.get("score") is not None:
                werte.append(float(stelle["score"]))
        return werte
    for stelle in db.get_dismissed_jobs() or []:
        if "bewerbung_erstellt" in str(stelle.get("dismiss_reason") or ""):
            continue
        if stelle.get("score") is not None:
            werte.append(float(stelle["score"]))
    return werte


def test_fachwerte_neu_gleich_alt(bestand):
    from bewerbungs_assistent.services import fachwert
    for beworben in (True, False):
        neu = sorted(fachwert._fachwerte(bestand, beworben=beworben))
        alt = sorted(_fachwerte_alt(bestand, beworben))
        assert neu == alt and len(neu) > 20


def test_fachwerte_gleich_alt_mit_bewerbung_erstellt_und_ohne_score(bestand):
    """Auch die Sonderfaelle: Grund `bewerbung_erstellt` zaehlt nicht, NULL-Score nicht."""
    from bewerbungs_assistent.services import fachwert
    conn = bestand.connect()
    conn.execute("UPDATE jobs SET dismiss_reason='bewerbung_erstellt' WHERE hash LIKE '%:aus0000%' "
                 "OR hash LIKE 'aus0000%'")
    conn.execute("UPDATE jobs SET score=NULL WHERE hash LIKE '%:aus0001%' OR hash LIKE 'aus0001%'")
    conn.commit()
    try:
        assert sorted(fachwert._fachwerte(bestand, beworben=False)) == \
            sorted(_fachwerte_alt(bestand, False))
        assert sorted(fachwert._fachwerte(bestand, beworben=True)) == \
            sorted(_fachwerte_alt(bestand, True))
    finally:
        conn.execute("UPDATE jobs SET dismiss_reason='falsches_fachgebiet' WHERE hash LIKE '%:aus0000%' "
                     "OR hash LIKE 'aus0000%'")
        conn.execute("UPDATE jobs SET score=3 WHERE hash LIKE '%:aus0001%' OR hash LIKE 'aus0001%'")
        conn.commit()


def test_stufenwerte_identisch_zur_alten_rechnung(bestand, monkeypatch):
    """Alle sechs Stufen: Wert, sichtbar, bewerbungen_darunter wie mit der alten Lesart."""
    from bewerbungs_assistent.services import fachwert, schwellen_stufen as st
    neu = st.stufen(bestand)
    monkeypatch.setattr(fachwert, "_fachwerte", lambda db, beworben: _fachwerte_alt(db, beworben))
    alt = st._stufen_rechnen(bestand)
    assert neu == alt
    assert neu["belastbar"] is True
    for bereich in st.BEREICHE:
        assert st.wert_fuer(bestand, bereich) == st.wert_fuer(bestand, bereich) >= 0


# ---------------------------------------------------------------- Zaehler


def test_get_search_criteria_liest_nicht_alle_aussortierten(bestand, monkeypatch):
    def verboten(*a, **k):
        raise AssertionError("get_dismissed_jobs darf hier nicht laufen")
    monkeypatch.setattr(type(bestand), "get_dismissed_jobs", verboten)
    bestand._local.__dict__.pop("stufen_zwischenspeicher", None)
    krit = bestand.get_search_criteria()
    assert krit.get("_schwelle_stufe") == "locker"
    assert bestand.get_scoring_threshold() >= 0


def test_stufen_rechnet_je_datenstand_einmal(bestand, monkeypatch):
    from bewerbungs_assistent.services import schwellen_stufen as st
    st.stufen(bestand)
    aufrufe = []
    original = st._stufen_rechnen
    monkeypatch.setattr(st, "_stufen_rechnen",
                        lambda db: (aufrufe.append(1), original(db))[1])
    for _ in range(50):
        st.wert_fuer(bestand, st.LISTE)
        bestand.get_search_criteria()
    assert aufrufe == []          # Datenstand unveraendert: kein einziges Mal gerechnet


def test_cache_wird_bei_jedem_schreibweg_ungueltig(bestand):
    """Score, Aktiv-Flag, Bewerbung und Stufen-Einstellung: der Cache folgt, ohne Liste von Schreibstellen."""
    from bewerbungs_assistent.services import schwellen_stufen as st

    def stimmt():
        return st.stufen(bestand) == st._stufen_rechnen(bestand)

    assert stimmt()
    conn = bestand.connect()
    # 1. jobs.score einer aktiven Stelle
    conn.execute("UPDATE jobs SET score=99 WHERE hash LIKE '%:akt00001' OR hash='akt00001'")
    conn.commit()
    assert stimmt()
    assert st.stufen(bestand)["stufen"][0]["sichtbar"] == st._stufen_rechnen(bestand)["stufen"][0]["sichtbar"]
    # 2. jobs.is_active (Aussortieren ueber das Nadeloehr)
    bestand.dismiss_job("akt00002", "zu_senior")
    assert stimmt()
    gesamt = st.stufen(bestand)["gesamt_aktiv"]
    assert gesamt == N_AKTIV - 1
    # 3. applications
    vorher = st.stufen(bestand)["bewerbungen_bewertbar"]
    bestand.add_application({"job_hash": "aus01000", "title": "X", "company": "Y", "status": "beworben"})
    assert stimmt()
    assert st.stufen(bestand)["bewerbungen_bewertbar"] == vorher + 1
    # 4. Stufen-Einstellung
    w1 = st.wert_fuer(bestand, st.LISTE)
    bestand.set_profile_setting("schwelle_stufe_liste", "offensichtliches_aus")
    assert st.wert_fuer(bestand, st.LISTE) != w1 or w1 == 0.0
    assert stimmt()
    bestand.set_profile_setting("schwelle_stufe_liste", "ausgewogen")
    assert st.wert_fuer(bestand, st.LISTE) == w1


def test_cache_sieht_schreibzugriff_einer_anderen_connection(bestand):
    """Ein zweiter Thread (eigene Connection) schreibt: der erste sieht es sofort."""
    import threading
    from bewerbungs_assistent.services import schwellen_stufen as st
    st.stufen(bestand)
    vorher = st.stufen(bestand)["aussortierte"]

    def schreiben():
        c = bestand.connect()
        c.execute("UPDATE jobs SET is_active=0, dismiss_reason='zu_junior' "
                  "WHERE hash LIKE '%:akt00003' OR hash='akt00003'")
        c.commit()
    t = threading.Thread(target=schreiben)
    t.start()
    t.join()
    assert st.stufen(bestand)["aussortierte"] == vorher + 1
    assert st.stufen(bestand) == st._stufen_rechnen(bestand)


def test_in_offener_transaktion_wird_nicht_zwischengespeichert(bestand):
    from bewerbungs_assistent.services import schwellen_stufen as st
    conn = bestand.connect()
    st.stufen(bestand)
    conn.execute("UPDATE jobs SET score=77 WHERE hash LIKE '%:akt00004' OR hash='akt00004'")
    assert conn.in_transaction
    assert st._daten_stand(bestand) is None
    mitten = st.stufen(bestand)
    conn.rollback()
    nach = st.stufen(bestand)
    assert nach == st._stufen_rechnen(bestand)
    assert mitten["gesamt_aktiv"] == nach["gesamt_aktiv"]


# ----------------------------------------------------------- Messtests


def test_get_search_criteria_unter_50_ms(bestand):
    bestand.get_search_criteria()
    t0 = time.perf_counter()
    for _ in range(10):
        bestand.get_search_criteria()
    ms = (time.perf_counter() - t0) / 10 * 1000
    assert ms < 50, f"get_search_criteria {ms:.1f} ms"


def test_get_search_criteria_ungecacht_unter_150_ms(bestand):
    """Auch der erste Aufruf nach einer Aenderung: vorher 0,3 s, jetzt zwei SQL-Abfragen."""
    ms_liste = []
    for _ in range(5):
        bestand._local.__dict__.pop("stufen_zwischenspeicher", None)
        t0 = time.perf_counter()
        bestand.get_search_criteria()
        ms_liste.append((time.perf_counter() - t0) * 1000)
    assert min(ms_liste) < 150, ms_liste


@pytest.fixture
def client(bestand):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    vorher = dash._db
    dash._db = bestand
    try:
        yield TestClient(dash.app), dash
    finally:
        dash._db = vorher


def test_api_jobs_unter_1_s(client):
    c, _dash = client
    c.get("/api/jobs?active=true")
    t0 = time.perf_counter()
    r = c.get("/api/jobs?active=true")
    s = time.perf_counter() - t0
    assert r.status_code == 200
    assert s < 1.0, f"/api/jobs {s:.2f} s"


def test_stellenliste_wertet_stufen_hoechstens_einmal_aus(bestand, monkeypatch):
    from bewerbungs_assistent.services import schwellen_stufen as st
    bestand._local.__dict__.pop("stufen_zwischenspeicher", None)
    zaehler = []
    original = st._stufen_rechnen
    monkeypatch.setattr(st, "_stufen_rechnen",
                        lambda db: (zaehler.append(1), original(db))[1])
    bestand._mit_scoring_reglern(bestand.get_active_jobs(), sortieren=False)
    assert len(zaehler) <= 1, f"{len(zaehler)} Stufenrechnungen fuer eine Liste"


# ------------------------------------------------------------- Event-Loop


def _lesende_async_endpunkte():
    quelle = (ROOT / "src/bewerbungs_assistent/dashboard.py").read_text(encoding="utf-8-sig")
    baum = ast.parse(quelle)
    gefunden = []
    for n in baum.body:
        if not isinstance(n, ast.AsyncFunctionDef):
            continue
        get = any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                  and isinstance(d.func.value, ast.Name) and d.func.value.id == "app"
                  and d.func.attr == "get" for d in n.decorator_list)
        if not get:
            continue
        stapel, wartet = list(n.body), False
        while stapel:
            k = stapel.pop()
            if isinstance(k, (ast.Await, ast.AsyncFor, ast.AsyncWith)):
                wartet = True
                break
            if not isinstance(k, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                stapel.extend(ast.iter_child_nodes(k))
        if not wartet:
            gefunden.append(n.name)
    return gefunden


def test_kein_lesender_endpunkt_blockiert_den_event_loop():
    """Ein `async def` ohne `await` ist ein blockierender Endpunkt im Loop (#1407)."""
    assert _lesende_async_endpunkte() == []


def test_die_schweren_endpunkte_laufen_im_threadpool():
    import bewerbungs_assistent.dashboard as dash
    for name in ("api_jobs", "api_statistics", "api_jobsuche_last"):
        assert not asyncio.iscoroutinefunction(getattr(dash, name)), name
    quelle = (ROOT / "src/bewerbungs_assistent/dashboard.py").read_text(encoding="utf-8-sig")
    for pfad in ("/api/stats/extended", "/api/stats/style", "/api/stats/timeline"):
        i = quelle.index(f'@app.get("{pfad}")')
        assert quelle[i:i + 200].split("\n")[1].startswith("def "), pfad


def test_langsame_anfrage_blockiert_andere_nicht(client, monkeypatch):
    """Parallele Messung: /api/jobs haengt 1,5 s, /api/jobsuche/last kommt trotzdem sofort."""
    import httpx
    _c, dash = client
    monkeypatch.setattr(type(dash._db), "_mit_scoring_reglern",
                        lambda self, jobs, sortieren=True: (time.sleep(1.5), jobs)[1])

    async def lauf():
        transport = httpx.ASGITransport(app=dash.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8200") as ac:
            async def langsam():
                t0 = time.perf_counter()
                await ac.get("/api/jobs?active=true")
                return time.perf_counter() - t0

            async def schnell():
                await asyncio.sleep(0.2)          # erst NACHDEM die langsame laeuft
                t0 = time.perf_counter()
                r = await ac.get("/api/jobsuche/last")
                return r.status_code, time.perf_counter() - t0
            return await asyncio.gather(langsam(), schnell())
    lang, (status, kurz) = asyncio.run(lauf())
    assert status == 200
    assert lang >= 1.4
    assert kurz < 0.9, f"/api/jobsuche/last wartete {kurz:.2f} s auf die langsame Anfrage"
