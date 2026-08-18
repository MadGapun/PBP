"""Tests fuer v1.7.17 — #917 (Defekte A+B): scoring_konfigurieren.

Belegt: 'setzen' legte neben der Seed-Zeile (profile_id='') eine
Profil-Dublette an — die Altzeile mit ignore_flag=1 blieb ueber MCP
unerreichbar, vier Stellenarten waren still ausgeblendet und nicht
zuruecknehmbar.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1717_917_")
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


def _seed_zeile(db, dimension, sub_key, wert, ignore=0):
    """Simuliert eine Seed-/Auto-Zeile mit profile_id='' (der Alt-Zustand).

    OR REPLACE, weil die Migration die Dimension-Defaults bereits mit
    profile_id='' seedet — genau diese Zeilen sind im Feld die
    unerreichbaren Traeger des ignore_flags.
    """
    conn = db.connect()
    conn.execute(
        "INSERT OR REPLACE INTO scoring_config (profile_id, dimension, "
        "sub_key, value, ignore_flag, created_at) "
        "VALUES ('', ?, ?, ?, ?, '2026-01-01')",
        (dimension, sub_key, wert, ignore))
    conn.commit()


def _zeilen(db, dimension, sub_key):
    return db.connect().execute(
        "SELECT profile_id, value, ignore_flag FROM scoring_config "
        "WHERE dimension=? AND sub_key=?", (dimension, sub_key)).fetchall()


def test_917_setzen_ersetzt_seed_zeile_statt_dublette(setup_env):
    """DER Belegfall: Seed mit ignore_flag=1, 'setzen' soll sie ERSETZEN."""
    db, _ = setup_env
    _seed_zeile(db, "stellentyp", "befristet", -2, ignore=1)
    db.set_scoring_config("stellentyp", "befristet", -3, ignore_flag=False)
    rows = _zeilen(db, "stellentyp", "befristet")
    assert len(rows) == 1, f"Dublette entstanden: {[dict(r) for r in rows]}"
    assert rows[0]["value"] == -3
    assert rows[0]["ignore_flag"] == 0, \
        "das alte Ignorieren-Flag muss mit dem Ersetzen verschwinden"


def test_917_loeschen_entfernt_auch_seed_variante(setup_env):
    db, _ = setup_env
    _seed_zeile(db, "stellentyp", "zeitarbeit", -2, ignore=1)
    db.set_scoring_config("stellentyp", "zeitarbeit", -4)
    n = db.delete_scoring_config("stellentyp", "zeitarbeit")
    assert n >= 1
    assert _zeilen(db, "stellentyp", "zeitarbeit") == [], \
        "loeschen muss BEIDE Varianten wegraeumen (Rueckfall auf Default)"


def test_917_tie_break_profilzeile_gewinnt(setup_env):
    """Defekt B: bei Alt-Dubletten muss deterministisch die Profil-Zeile
    gelten (last wins im Consumer)."""
    db, _ = setup_env
    pid = db.get_active_profile_id()
    _seed_zeile(db, "stellentyp", "praktikum", -1, ignore=1)
    conn = db.connect()
    conn.execute(
        "INSERT INTO scoring_config (profile_id, dimension, sub_key, value, "
        "ignore_flag, created_at) VALUES (?, 'stellentyp', 'praktikum', -5, "
        "0, '2026-06-01')", (pid,))
    conn.commit()
    config = db.get_scoring_config()
    relevant = [c for c in config
                if c["dimension"] == "stellentyp"
                and c["sub_key"] == "praktikum"]
    assert len(relevant) == 2
    assert relevant[-1]["profile_id"] == pid, \
        "Profil-Zeile muss ZULETZT kommen (Consumer arbeitet last-wins)"


def test_917_tool_loeschen(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _seed_zeile(db, "stellentyp", "werkstudent", -2, ignore=1)

    def _call(name, args):
        async def _run():
            tool = await mcp.get_tool(name)
            res = await tool.run(args)
            return res.structured_content if hasattr(
                res, "structured_content") else res
        raw = asyncio.run(_run())
        if isinstance(raw, tuple):
            raw = raw[1] if len(raw) > 1 else raw[0]
        if isinstance(raw, list):
            raw = raw[0] if raw else {}
        return raw

    res = _call("scoring_konfigurieren", {
        "aktion": "loeschen", "dimension": "stellentyp",
        "sub_key": "werkstudent"})
    assert res["status"] == "geloescht", res
    assert _zeilen(db, "stellentyp", "werkstudent") == []

    leer = _call("scoring_konfigurieren", {
        "aktion": "loeschen", "dimension": "stellentyp",
        "sub_key": "gibtsnicht"})
    assert leer["status"] == "nicht_gefunden"


# ------------------------------------------------- Migration (Defekt C)

def test_917_migration_km_zeile_wandert_in_stufe_999(setup_env):
    """Der '50km'-Lern-Malus traf Stellen BIS 50 km (invertierter
    Lerneffekt). Die Migration ueberfuehrt ihn in die Stufe 999."""
    db, _ = setup_env
    conn = db.connect()
    conn.execute(
        "INSERT OR REPLACE INTO scoring_config (profile_id, dimension, "
        "sub_key, value, ignore_flag, created_at) "
        "VALUES ('', 'entfernung_fest', '50km', -10, 0, '2026-01-01')")
    conn.commit()
    db.initialize()  # Safety-Nets sind idempotent
    assert _zeilen(db, "entfernung_fest", "50km") == [], \
        "die fehl-adressierte km-Zeile muss verschwinden"
    ziel = _zeilen(db, "entfernung_fest", "999")
    assert ziel and ziel[0]["value"] == -10, \
        "der gelernte Malus muss in der Stufe 999 landen (tiefer gewinnt)"
    nah = _zeilen(db, "entfernung_fest", "50")
    assert nah and nah[0]["value"] == -2, \
        "die 30-50km-Stufe behaelt ihren Seed-Wert"


def test_917_migration_fuehrt_dubletten_zusammen(setup_env):
    db, _ = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    conn.execute(
        "INSERT OR REPLACE INTO scoring_config (profile_id, dimension, "
        "sub_key, value, ignore_flag, created_at) "
        "VALUES (?, 'stellentyp', 'befristet', -3, 0, '2026-06-01')", (pid,))
    conn.commit()
    rows = _zeilen(db, "stellentyp", "befristet")
    assert len(rows) == 2  # Seed ('') + Profil-Zeile
    db.initialize()
    rows = _zeilen(db, "stellentyp", "befristet")
    assert len(rows) == 1 and rows[0]["profile_id"] == pid, \
        "profilspezifische Zeile gewinnt, Seed-Dublette faellt weg"


# ------------------------- Automatik vs. Nutzer (Live-Repro aus dem Issue)

def _dismiss_job(db, mcp_obj, h, gruende):
    db.save_jobs([{
        "hash": h, "title": f"Stelle {h}", "company": "Testfirma GmbH",
        "location": "HH", "url": f"https://e.example/{h}", "source": "demo",
        "description": "Beschreibung. " * 20,
        "employment_type": "festanstellung", "score": 30}])

    def _call(name, args):
        async def _run():
            tool = await mcp_obj.get_tool(name)
            res = await tool.run(args)
            return res.structured_content if hasattr(
                res, "structured_content") else res
        raw = asyncio.run(_run())
        if isinstance(raw, tuple):
            raw = raw[1] if len(raw) > 1 else raw[0]
        if isinstance(raw, list):
            raw = raw[0] if raw else {}
        return raw

    return _call("stelle_bewerten", {
        "job_hash": h, "bewertung": "passt_nicht", "gruende": gruende})


def test_917_automatik_respektiert_nutzer_regler(setup_env):
    """DIE Live-Repro: Nutzer schaltet Ignorieren ab, naechstes
    Aussortieren mit demselben Grund (Zaehler >> Schwelle) darf die
    Entscheidung nicht wieder umkehren."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    db.set_scoring_config("stellentyp", "praktikum", -8, ignore_flag=False)
    db.set_setting("dismiss_counts", {"zu_junior": 70})
    _dismiss_job(db, mcp, "auto1", ["zu_junior"])
    rows = _zeilen(db, "stellentyp", "praktikum")
    assert len(rows) == 1
    assert rows[0]["ignore_flag"] == 0, \
        "Automatik darf die explizite Nutzer-Entscheidung nicht umkehren"
    assert rows[0]["value"] == -8, \
        "auch der Nutzer-Wert bleibt unangetastet"


def test_917_automatik_setzt_kein_ignore_mehr(setup_env):
    """#908: 'schaerfer statt aus' — die Automatik vertieft den Malus,
    blendet aber nichts mehr aus."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    db.set_setting("dismiss_counts", {"zeitarbeit": 10})
    res = _dismiss_job(db, mcp, "auto2", ["zeitarbeit"])
    rows = _zeilen(db, "stellentyp", "zeitarbeit")
    assert len(rows) == 1
    assert rows[0]["ignore_flag"] == 0, \
        f"kein automatisches Ignorieren mehr: {dict(rows[0])} / {res}"
    assert rows[0]["value"] <= -4, \
        "stattdessen wird der Malus vertieft"


def test_917_entfernung_lernt_in_stufe_999(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    db.set_setting("dismiss_counts", {"zu_weit_entfernt": 20})
    _dismiss_job(db, mcp, "auto3", ["zu_weit_entfernt"])
    assert _zeilen(db, "entfernung_fest", "50km") == [], \
        "der falsche '50km'-Schluessel darf nie wieder entstehen"
    ziel = _zeilen(db, "entfernung_fest", "999")
    assert ziel and ziel[0]["value"] == -10, \
        "der Lern-Malus gehoert in die Stufe jenseits aller Grenzen"
    nah = _zeilen(db, "entfernung_fest", "50")
    assert nah and nah[0]["value"] == -2, "30-50 km bleiben unangetastet"


# --------------------------------------- Defekt D: Ausschluss-Paritaet

_AUSSCHLUSS_CRITERIA = {
    "keywords_muss": ["PLM"],
    "keywords_plus": ["Consulting"],
    "keywords_minus": [],
    "keywords_ausschluss": ["Berufseinsteiger"],
}

_ANZEIGE = (
    "Functional Business Consultant Engineering and PLM. "
    "PLM Prozesse harmonisieren und Consulting fuer Fachbereiche. " * 5
)

_NOTIZ = ("Bewerberfeld: 68 % Berufserfahrene, 20 % Berufseinsteiger, "
          "5 % Manager")


def test_917_fit_analyse_wendet_ausschluss_an():
    """Der Belegfall: dieselbe Stelle hatte Score 0 (Liste) und 88
    (Fit-Analyse), je nachdem welcher Pfad zuletzt schrieb."""
    from bewerbungs_assistent.job_scraper import calculate_score, fit_analyse
    job = {"title": "Consultant PLM",
           "description": _ANZEIGE + "\n" + _NOTIZ,
           "employment_type": "festanstellung"}
    assert calculate_score(dict(job), _AUSSCHLUSS_CRITERIA) == 0
    res = fit_analyse(dict(job), _AUSSCHLUSS_CRITERIA)
    assert res["total_score"] == 0, \
        "fit_analyse muss den harten K.o. genauso anwenden"
    assert res.get("ko_ausschluss") == "Berufseinsteiger"
    assert any("Berufseinsteiger" in r for r in res["risks"])


def test_917_notiz_hinter_trenner_zaehlt_nicht():
    """Regressionstest aus dem AK: Ausschluss-Keyword NACH '---' ist
    in BEIDEN Pfaden wirkungslos (#603-Konvention)."""
    from bewerbungs_assistent.job_scraper import calculate_score, fit_analyse
    job = {"title": "Consultant PLM",
           "description": _ANZEIGE + "\n---\n" + _NOTIZ,
           "employment_type": "festanstellung"}
    s = calculate_score(dict(job), _AUSSCHLUSS_CRITERIA)
    assert s > 0, "Notiz hinter dem Trenner darf nicht k.o. schlagen"
    res = fit_analyse(dict(job), _AUSSCHLUSS_CRITERIA)
    assert res["total_score"] > 0
    assert "ko_ausschluss" not in res


def test_917_scores_neu_berechnen_nennt_grund(setup_env):
    """Der Batch nullte still (83 -> 0); jetzt liefert er den Grund."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    db.set_search_criteria("keywords_muss", ["PLM"])
    db.set_search_criteria("keywords_ausschluss", ["Berufseinsteiger"])
    db.save_jobs([{
        "hash": "ko917", "title": "Consultant PLM",
        "company": "Sortiertechnik Nord GmbH", "location": "HH",
        "url": "https://e.example/ko917", "source": "demo",
        "description": _ANZEIGE + "\n" + _NOTIZ,
        "employment_type": "festanstellung", "score": 83}])
    db.update_job("ko917", {"score": 83})

    def _call(name, args):
        async def _run():
            tool = await mcp.get_tool(name)
            res = await tool.run(args)
            return res.structured_content if hasattr(
                res, "structured_content") else res
        raw = asyncio.run(_run())
        if isinstance(raw, tuple):
            raw = raw[1] if len(raw) > 1 else raw[0]
        if isinstance(raw, list):
            raw = raw[0] if raw else {}
        return raw

    res = _call("scores_neu_berechnen", {})
    assert res["status"] == "fertig"
    auff = res.get("auffaellige_aenderungen") or []
    treffer = [a for a in auff if a.get("hash", "").endswith("ko917")
               or a.get("hash") == "ko917"]
    assert treffer, f"harte Nullung muss im Report stehen: {res}"
    assert "Ausschluss-Keyword" in treffer[0]["grund"]


def test_917_stelle_bearbeiten_warnt_bei_notiz_ohne_trenner(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    db.save_jobs([{
        "hash": "warn917", "title": "Consultant PLM",
        "company": "Papiertechnik West AG", "location": "HH",
        "url": "https://e.example/warn917", "source": "demo",
        "description": "Kurztext. " * 10,
        "employment_type": "festanstellung", "score": 40}])

    def _call(name, args):
        async def _run():
            tool = await mcp.get_tool(name)
            res = await tool.run(args)
            return res.structured_content if hasattr(
                res, "structured_content") else res
        raw = asyncio.run(_run())
        if isinstance(raw, tuple):
            raw = raw[1] if len(raw) > 1 else raw[0]
        if isinstance(raw, list):
            raw = raw[0] if raw else {}
        return raw

    ohne = _call("stelle_bearbeiten", {
        "job_hash": "warn917",
        "beschreibung": _ANZEIGE + "\n" + _NOTIZ})
    assert "notizen_warnung" in ohne, ohne

    mit = _call("stelle_bearbeiten", {
        "job_hash": "warn917",
        "beschreibung": _ANZEIGE + "\n---\n" + _NOTIZ})
    assert "notizen_warnung" not in mit, mit
