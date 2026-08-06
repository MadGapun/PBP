"""Tests fuer v1.7.11 — #799 (F35): Lernmodus liefert wieder etwas.

Drei Befunde aus dem Praxis-Fall 25.07.2026:
1. `erkenntnisse_ableiten()` lief in den 4-Minuten-Timeout und nahm den
   ganzen MCP-Server mit (alle Threads teilen EINE SQLite-Connection).
2. Zwei Tabellen mit fast gleichem Namen — `learned_insights` (aus #784,
   0 Zeilen) neben `learning_insights` (#594, 4 Zeilen). Die UI las die
   eine, die Logik schrieb in die andere.
3. Die vorhandenen Erkenntnisse waren ueberwiegend Bedienstatistik
   ("12 Klicks pro Besuch") statt Aussagen ueber die Bewerbungsstrategie —
   und lagen doppelt drin.
"""
import asyncio
import importlib
import os
import shutil
import sqlite3
import tempfile
import time

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1711_799_")
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
    yield db, tmpdir
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _result(raw):
    if isinstance(raw, tuple):
        raw = raw[1] if len(raw) > 1 else raw[0]
    if hasattr(raw, "structured_content"):
        raw = raw.structured_content
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    return raw


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


def _bestand(db, n_jobs=300, n_apps=40):
    """Realistischer Bestand: viele Aussortierungen, Bewerbungen mit
    Events ueber mehrere Monate, Kanal-Unterschied."""
    conn = db.connect()
    pid = db.get_active_profile_id()
    for i in range(n_jobs):
        aktiv = 1 if i < 40 else 0
        grund = None if aktiv else ("falsches_fachgebiet" if i % 4 else "zeitarbeit")
        conn.execute(
            "INSERT INTO jobs (hash, title, company, location, url, source, "
            "description, is_active, dismiss_reason, profile_id, found_at, "
            "updated_at, score) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"j{i}", f"Rolle {i}", f"Firma {i % 30}", "Hamburg",
             f"https://x.example/{i}", ["stepstone", "xing"][i % 2],
             "Text. " * 30, aktiv, grund, pid, "2026-06-01", "2026-06-01",
             (i % 120)))
    for i in range(n_apps):
        aid = db.add_application({
            "company": f"Firma {i % 30}", "title": f"Rolle {i}",
            "job_hash": f"j{i}", "status": ["abgelehnt", "abgelaufen"][i % 2],
            "applied_at": f"2026-0{(i % 5) + 1}-10"})
        # Kanal: jede dritte ueber Netzwerk (mit Interview), Rest Portal
        if i % 3 == 0:
            db.update_application(aid, {"source": "netzwerk"})
            conn.execute("UPDATE applications SET has_reached_interview=1 "
                         "WHERE id=?", (aid,))
        else:
            db.update_application(aid, {"source": "stepstone"})
        conn.execute(
            "INSERT INTO application_events (application_id, status, event_date, notes) "
            "VALUES (?,'beworben',?,'')", (aid, f"2026-0{(i % 5) + 1}-10T09:00:00"))
        conn.execute(
            "INSERT INTO application_events (application_id, status, event_date, notes) "
            "VALUES (?,'eingangsbestaetigung',?,'')",
            (aid, f"2026-0{(i % 5) + 1}-{15 + (i % 10):02d}T09:00:00"))
    conn.commit()


# ------------------------------------------------- Befund 1: Blockade

def test_799_ableiten_blockiert_nicht(setup_env):
    """Regressionstest: der Aufruf muss schnell zurueckkommen."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _bestand(db)
    start = time.time()
    res = _result(_call(mcp, "erkenntnisse_ableiten", {}))
    dauer = time.time() - start
    assert dauer < 20, f"Ableitung dauerte {dauer:.1f}s — Blockade-Gefahr"
    assert res["status"] == "vorschau"
    assert "dauer_ms" in res


def test_799_budget_liefert_teilergebnis_statt_zu_haengen(setup_env):
    """Bei Budget 0 werden Regeln uebersprungen — aber es kommt ein
    schemakonformes Ergebnis zurueck, kein Timeout."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _bestand(db)
    res = _result(_call(mcp, "erkenntnisse_ableiten", {"budget_sekunden": 0}))
    assert res["status"] == "vorschau"
    assert res.get("abgebrochen") is True
    assert res["regeln_uebersprungen"], res
    assert "hinweis_budget" in res


def test_799_kaputte_regel_kippt_den_lauf_nicht(setup_env):
    """Eine fehlerhafte Regel darf die anderen Erkenntnisse nicht mitnehmen."""
    db, _ = setup_env
    from bewerbungs_assistent.services import lerninsights as li
    _bestand(db)

    def _kaputt(_db):
        raise RuntimeError("absichtlich kaputt")

    orig = li._REGELN
    try:
        li._REGELN = [("kaputt", _kaputt)] + list(orig)
        lauf = li.kandidaten_ableiten(db)
        assert lauf["kandidaten"], "andere Regeln muessen trotzdem liefern"
        assert "kaputt" in lauf["regel_fehler"]
    finally:
        li._REGELN = orig


# --------------------------------------- Befund 2: Tabellen-Kollision

def test_799_nur_noch_eine_lern_tabelle(setup_env):
    db, _ = setup_env
    conn = db.connect()
    namen = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name LIKE 'learn%insights'").fetchall()}
    assert "learning_insights" in namen
    assert "learned_insights" not in namen, (
        "Die Doppel-Tabelle aus #784 muss entfernt sein")


def test_799_migration_uebernimmt_bestand_und_entfernt_alt(setup_env, tmp_path):
    """Alt-DB mit learned_insights-Zeilen: Inhalte kommen mit, Tabelle geht."""
    db, tmpdir = setup_env
    conn = db.connect()
    # Zustand vor der Migration kuenstlich herstellen
    conn.execute("""
        CREATE TABLE IF NOT EXISTS learned_insights (
            id TEXT PRIMARY KEY, profile_id TEXT, kategorie TEXT NOT NULL,
            aussage TEXT NOT NULL, evidenz_json TEXT, konfidenz REAL,
            belegt_durch_n INTEGER, erstellt_am TEXT, aktualisiert_am TEXT,
            bestaetigt_vom_user INTEGER DEFAULT 0)""")
    conn.execute(
        "INSERT INTO learned_insights (id, profile_id, kategorie, aussage, "
        "evidenz_json, konfidenz, belegt_durch_n, erstellt_am, "
        "bestaetigt_vom_user) VALUES "
        "('a1', ?, 'stellentyp', 'Zeitarbeit wird abgelehnt', "
        "'{\"n\": 29}', 0.74, 29, '2026-07-24', 1)",
        (db.get_active_profile_id(),))
    conn.commit()

    db.initialize()  # Migration laeuft idempotent beim Start
    namen = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "learned_insights" not in namen
    row = conn.execute(
        "SELECT title, score, bestaetigt_vom_user FROM learning_insights "
        "WHERE title='Zeitarbeit wird abgelehnt'").fetchone()
    assert row is not None, "Inhalt muss uebernommen sein"
    assert row["bestaetigt_vom_user"] == 1, "Kuratier-Status bleibt erhalten"

    db.initialize()  # zweiter Lauf darf nichts kaputt machen
    n = conn.execute("SELECT COUNT(*) FROM learning_insights "
                     "WHERE title='Zeitarbeit wird abgelehnt'").fetchone()[0]
    assert n == 1, "idempotent — kein Duplikat beim zweiten Lauf"


def test_799_duplikat_schutz_bei_wechselnder_zahl(setup_env):
    """Der belegte Duplikat-Fall: dieselbe Aussage, andere Prozentzahl."""
    db, _ = setup_env
    db.upsert_learning_insight({
        "kind": "dismiss_pattern",
        "title": "85 % der Aussortierungen entfallen auf einen Grund",
        "details": {}, "score": 0.7})
    db.upsert_learning_insight({
        "kind": "dismiss_pattern",
        "title": "86 % der Aussortierungen entfallen auf einen Grund",
        "details": {}, "score": 0.7})
    rows = db.connect().execute(
        "SELECT title, observed_count FROM learning_insights "
        "WHERE kind='dismiss_pattern'").fetchall()
    assert len(rows) == 1, f"Duplikat trotz Zahl-Aenderung: {[r['title'] for r in rows]}"
    assert rows[0]["title"].startswith("86"), "Titel wird aufgefrischt"
    assert rows[0]["observed_count"] == 2


def test_799_widersprochenes_wird_nicht_wiederbelebt(setup_env):
    db, _ = setup_env
    iid = db.upsert_learning_insight({
        "kind": "dismiss_pattern", "title": "Aussage X mit 5 Faellen",
        "details": {}, "score": 0.5})
    db.connect().execute(
        "UPDATE learning_insights SET bestaetigt_vom_user=-1 WHERE id=?", (iid,))
    db.connect().commit()
    db.upsert_learning_insight({
        "kind": "dismiss_pattern", "title": "Aussage X mit 9 Faellen",
        "details": {}, "score": 0.6})
    row = db.connect().execute(
        "SELECT observed_count, bestaetigt_vom_user FROM learning_insights "
        "WHERE id=?", (iid,)).fetchone()
    assert row["bestaetigt_vom_user"] == -1
    assert row["observed_count"] == 1, "widersprochen = nicht auffrischen"


# ------------------------- Befund 3: Strategie statt Bedienstatistik

def test_799_liefert_strategie_erkenntnisse(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _bestand(db)
    res = _result(_call(mcp, "erkenntnisse_ableiten", {}))
    arten = {k["kind"] for k in res["kandidaten"]}
    # Mindestens die belegbaren Arten aus dem Issue
    assert "dismiss_pattern" in arten, arten
    assert "kanal_pattern" in arten, arten
    assert "reaktionszeit" in arten, arten
    assert all(k["scope"] == "strategie" for k in res["strategie"])
    # Jede Aussage traegt Fallzahl und Konfidenz
    for k in res["kandidaten"]:
        assert k["belegt_durch_n"] > 0
        assert 0 < k["konfidenz"] <= 0.95
        assert k["evidenz"], k


def test_799_unsicherheit_steht_in_der_aussage(setup_env):
    """Bei duenner Datenlage kein stiller Fakt, sondern ein Hinweis."""
    db, _ = setup_env
    from bewerbungs_assistent.services.lerninsights import _kandidat
    duenn = _kandidat("x", "strategie", "Aussage.", {}, 3)
    dick = _kandidat("x", "strategie", "Aussage.", {}, 60)
    assert duenn["aussage"].startswith("Erster Hinweis")
    assert dick["aussage"] == "Aussage."


def test_799_ohne_lokale_ki_lauffaehig(setup_env):
    """Kernforderung: die Erkenntnisse entstehen ohne Ollama."""
    db, _ = setup_env
    from unittest.mock import patch
    from bewerbungs_assistent.server import mcp
    _bestand(db)
    with patch("bewerbungs_assistent.services.llm_service.LLMService."
               "_ollama_generate", side_effect=AssertionError("kein Ollama!")):
        res = _result(_call(mcp, "erkenntnisse_ableiten", {"dry_run": False}))
    assert res["anzahl"] > 0
    assert res["gespeichert"]["neu"] > 0


def test_799_speichern_und_kuratieren(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _bestand(db)
    _result(_call(mcp, "erkenntnisse_ableiten", {"dry_run": False}))

    offen = _result(_call(mcp, "erkenntnisse_anzeigen", {"filter": "offen"}))
    assert offen["anzahl"] > 0
    erste = offen["erkenntnisse"][0]
    assert erste["evidenz"], "Evidenz muss aufklappbar mitkommen"
    assert erste["belegt_durch_n"] > 0

    ok = _result(_call(mcp, "erkenntnis_bestaetigen",
                       {"erkenntnis_id": str(erste["id"]), "bestaetigen": True}))
    assert ok["status"] == "bestaetigt"

    # Bestaetigte landen im Ollama-Kontext, offene nicht
    from bewerbungs_assistent.services.lerninsights import bestaetigte_fuer_kontext
    ctx = bestaetigte_fuer_kontext(db, min_konfidenz=0.0)
    assert len(ctx) == 1
    assert ctx[0]["aussage"] == erste["aussage"]


def test_799_bereich_trennt_strategie_von_bedienung(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _bestand(db)
    _result(_call(mcp, "erkenntnisse_ableiten", {"dry_run": False}))
    # Bedien-Erkenntnis wie sie die alte Pattern-Analyse erzeugt
    db.upsert_learning_insight({
        "kind": "ux_friction", "scope": "bedienung",
        "title": "Stellen-Seite hat 12 Klicks pro Besuch",
        "details": {}, "score": 0.4})

    strat = _result(_call(mcp, "erkenntnisse_anzeigen", {"bereich": "strategie"}))
    bedien = _result(_call(mcp, "erkenntnisse_anzeigen", {"bereich": "bedienung"}))
    assert bedien["anzahl"] == 1
    assert all("Klicks" not in e["aussage"] for e in strat["erkenntnisse"])


# ---------------------------------- Automatik hinterlaesst eine Spur

def test_799_lernlauf_erzeugt_background_job(setup_env):
    """Vorher stand in background_jobs ausschliesslich 'jobsuche'."""
    db, _ = setup_env
    from bewerbungs_assistent.services.automatik_scheduler import run_lernen_now
    _bestand(db)
    res = run_lernen_now(db)
    assert res["status"] == "gestartet"
    assert res.get("job_id")

    for _ in range(100):  # auf den Thread warten
        job = db.get_background_job(res["job_id"])
        if job and job.get("status") in ("fertig", "fehler"):
            break
        time.sleep(0.05)
    job = db.get_background_job(res["job_id"])
    assert job is not None, "Lern-Lauf muss eine Spur hinterlassen"
    assert job["status"] in ("fertig", "fehler")
    assert job["job_type"] == "lernen"
    # Regelbasierte Stufe muss gelaufen sein, auch ohne lokale KI
    n = db.connect().execute(
        "SELECT COUNT(*) FROM learning_insights").fetchone()[0]
    assert n > 0, "Der Lauf muss Erkenntnisse hinterlassen haben"
