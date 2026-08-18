"""Tests fuer v1.7.17 — #913: Ablehnungsgrund-Vokabular durchsetzen.

Befund: 101 verschiedene Freitext-Gruende in 182 Datensaetzen — die
dokumentierte Whitelist wurde nie durchgesetzt (mehrere Schreibpfade
liefen an der Normalisierung vorbei), die drei haeufigsten Nutzer-
Signale erzeugten NULL Lerneffekt.
"""
import asyncio
import importlib
import json
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1717_913_")
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


def _job(db, h, **extra):
    daten = {"hash": h, "title": f"Stelle {h}", "company": "Testfirma",
             "location": "HH", "url": f"https://e.example/{h}",
             "source": "demo", "description": "Text. " * 30,
             "employment_type": "festanstellung", "score": 20}
    daten.update(extra)
    db.save_jobs([daten])
    return h


# ------------------------------------------------- Normalisierung pur

def test_913_bestandsmapping():
    from bewerbungs_assistent.services.ablehnungsgruende import (
        normalisiere_dismiss_wert)
    faelle = [
        ("Falsches System", "falsches_system", 0),
        ("Falsche Branche", "falsche_branche", 0),
        ("Dublikat", "duplikat", 0),
        ("duplikat_manuell", "duplikat", 0),
        ("ueberqualifiziert", "zu_senior", 0),
        ("Veraltet", "veraltet_url", 0),
        ("Duplikat von e913acc3: 'senior solutions architect'",
         "duplikat", 1),
        ('Zu "Hands-on"', "sonstiges", 1),
    ]
    for raw, erwartet, n_texte in faelle:
        wert, texte = normalisiere_dismiss_wert(raw)
        assert wert == erwartet, (raw, wert)
        assert len(texte) == n_texte, (raw, texte)


def test_913_auto_prefix_wird_getrennt():
    from bewerbungs_assistent.services.ablehnungsgruende import (
        normalisiere_dismiss_wert)
    wert, texte = normalisiere_dismiss_wert(
        "auto:profil_match_negativ:Das Profil passt nicht zur Stelle.")
    assert wert == "profil_match_negativ"
    assert texte == ["Das Profil passt nicht zur Stelle."]


def test_913_json_liste_bleibt_liste():
    from bewerbungs_assistent.services.ablehnungsgruende import (
        normalisiere_dismiss_wert)
    wert, texte = normalisiere_dismiss_wert(
        '["Falsches System", "CDM statt PLM - verwaessert Positionierung"]')
    geparst = json.loads(wert)
    assert geparst == ["falsches_system", "sonstiges"], wert
    assert texte and "CDM statt PLM" in texte[0]


def test_913_custom_gruende_bleiben():
    from bewerbungs_assistent.services.ablehnungsgruende import (
        normalisiere_dismiss_wert)
    wert, texte = normalisiere_dismiss_wert(
        "mein_eigener_grund", custom={"mein_eigener_grund"})
    assert wert == "mein_eigener_grund" and texte == []


# ------------------------------------------- Schreibschutz db.dismiss_job

def test_913_dismiss_job_normalisiert_und_sichert_freitext(setup_env):
    """DER AK-Test: Schreibversuch mit Freitext landet als 'sonstiges'
    + dismiss_note — kein stiller Durchlass mehr."""
    db, _ = setup_env
    h = _job(db, "frei1")
    db.dismiss_job(h, "Der Posten erfordert spezifische Qualifikationen "
                      "im Bereich Qualitaetssicherung")
    job = db.get_job(h)
    assert job["dismiss_reason"] == "sonstiges", job["dismiss_reason"]
    assert "Qualitaetssicherung" in (job.get("dismiss_note") or "")


def test_913_dismiss_job_whitelist_unveraendert(setup_env):
    db, _ = setup_env
    h = _job(db, "wl1")
    db.dismiss_job(h, "zu_weit_entfernt")
    job = db.get_job(h)
    assert job["dismiss_reason"] == "zu_weit_entfernt"
    assert not job.get("dismiss_note")


def test_913_auto_pfad_bleibt_fuer_statistik_erkennbar(setup_env):
    """Der Ollama-Autofilter schrieb 'auto:profil_match_negativ:<text>' —
    nach der Normalisierung muss die Genauigkeits-Statistik die Stelle
    weiterhin als Auto-Entscheidung zaehlen."""
    db, _ = setup_env
    for i in range(5):
        h = _job(db, f"auto{i}")
        db.dismiss_job(h, f"auto:profil_match_negativ:Begruendung {i}")
    job = db.get_job("auto0")
    assert job["dismiss_reason"] == "profil_match_negativ"
    assert "Begruendung 0" in (job.get("dismiss_note") or "")
    stats = db.get_ollama_accuracy_stats()
    assert stats["auto_aussortiert_gesamt"] == 5, stats


# ------------------------------------------------- Bestands-Migration

def test_913_migration_heilt_bestand_und_sichert_original(setup_env):
    db, _ = setup_env
    pid = db.get_active_profile_id()
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, title, company, location, url, source, "
        "description, is_active, dismiss_reason, profile_id, found_at, "
        "updated_at, score) VALUES ('alt913','T','F','HH',"
        "'https://a.example/alt913','demo','Text',0,'Falsche Branche',?,"
        "'2026-06-01','2026-06-01',5)", (pid,))
    conn.execute(
        "INSERT INTO jobs (hash, title, company, location, url, source, "
        "description, is_active, dismiss_reason, profile_id, found_at, "
        "updated_at, score) VALUES ('alt914','T2','F2','HH',"
        "'https://a.example/alt914','demo','Text',0,"
        "'[\"Dublikat\"]',?,'2026-06-01','2026-06-01',5)", (pid,))
    conn.commit()
    db.initialize()
    j1 = db.get_job("alt913")
    assert j1["dismiss_reason"] == "falsche_branche", j1["dismiss_reason"]
    assert "Falsche Branche" in (j1.get("dismiss_note") or ""), \
        "Original muss als Note erhalten bleiben (Migrationsbericht in den Daten)"
    # get_job kann die JSON-Liste deserialisiert zurueckgeben — direkt
    # auf der Spalte pruefen, dass NUR der kanonische Grund drinsteht.
    roh = conn.execute("SELECT dismiss_reason FROM jobs WHERE hash="
                       "'alt914'").fetchone()["dismiss_reason"]
    assert json.loads(roh) == ["duplikat"], roh


def test_913_migration_laesst_konforme_in_ruhe(setup_env):
    db, _ = setup_env
    h = _job(db, "ok913")
    db.dismiss_job(h, '["falsches_fachgebiet"]')
    vorher = db.get_job(h)["dismiss_reason"]
    db.initialize()
    assert db.get_job(h)["dismiss_reason"] == vorher


# --------------------------------------------- Neue regulaere Gruende

def test_913_neue_gruende_sind_regulaer(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    h = _job(db, "neu913")

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

    res = _call("stelle_bewerten", {
        "job_hash": h, "bewertung": "passt_nicht",
        "gruende": ["falsches_system"]})
    job = db.get_job(h)
    assert "falsches_system" in str(job["dismiss_reason"]), (res, job)
    assert "sonstiges" not in str(job["dismiss_reason"]), \
        "falsches_system ist jetzt ein REGULAERER Grund (#913)"
    labels = {r["label"] for r in db.get_dismiss_reasons()}
    assert {"falsches_system", "falsche_branche"} <= labels, \
        "beide neuen Gruende gehoeren in die dismiss_reasons-Seeds"
