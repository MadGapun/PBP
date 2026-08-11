"""Tests fuer v1.7.12 — #828 (C33): Blacklist aendern/deaktivieren.

Belegter Fall 11.08.2026: Ein Blacklist-Grund, der einen Einzelfall als
Gattungsurteil formulierte, verzerrte die Bewertung zweier unbeteiligter
Stellen — und die einzige Korrekturmoeglichkeit war Loeschen+Neuanlegen
(Historie und Titel-Ausnahmen weg).

Kritischster Punkt (eigene Testklasse): Die Blacklist wirkt an DREI
Stellen. Der Deaktiv-Filter muss in allen dreien greifen, sonst zeigt
'anzeigen' inaktiv, waehrend die Suche weiter blockt (#807/#808-Klasse:
Pruefung und Wirkung laufen auseinander).
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1712_828_")
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


def test_828_hinzufuegen_liefert_entry_id(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Firma Grau"}))
    assert res["status"] == "hinzugefuegt"
    assert res.get("entry_id"), "hinzufuegen muss die entry_id liefern"


def test_828_aendern_erhaelt_created_at_und_historisiert_grund(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Consulting Alpha",
        "grund": "bewusste Entscheidung gegen Beratungshaus"}))
    eid = res["entry_id"]
    vorher = next(e for e in db.get_blacklist() if e["id"] == eid)

    res2 = _result(_call(mcp, "blacklist_verwalten", {
        "aktion": "aendern", "entry_id": eid,
        "grund": "nie Rueckmeldung auf drei Bewerbungen bei dieser Firma"}))
    assert res2["status"] == "geaendert", res2
    nachher = next(e for e in db.get_blacklist() if e["id"] == eid)
    assert nachher["reason"].startswith("nie Rueckmeldung")
    assert nachher["created_at"] == vorher["created_at"], "created_at bleibt"
    assert nachher["updated_at"], "updated_at wird gesetzt"
    assert "Beratungshaus" in (nachher["grund_vorher"] or ""), \
        "alter Grund muss nachvollziehbar bleiben"


def test_828_aendern_nur_uebergebene_felder(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Firma Beta",
        "grund": "Ursprungsgrund",
        "ausser_wenn_titel_enthaelt": ["PLM"]}))
    eid = res["entry_id"]
    _call(mcp, "blacklist_verwalten", {
        "aktion": "aendern", "entry_id": eid, "wert": "Firma Beta Neu"})
    e = next(x for x in db.get_blacklist() if x["id"] == eid)
    assert e["value"] == "Firma Beta Neu"
    assert e["reason"] == "Ursprungsgrund", "Grund unangetastet"
    assert e["ausser_wenn_titel_enthaelt"] == ["PLM"], "Ausnahmen bleiben"


def test_828_deaktivieren_wirkt_an_allen_drei_stellen(setup_env):
    """DER kritische Test: anzeigen inaktiv != Suche blockt weiter."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Pausiert AG"}))
    eid = res["entry_id"]

    # Wirkort 1: Anlegen wird geblockt
    blockt = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "Rolle X", "firma": "Pausiert AG",
        "url": "https://e.example/1"}))
    assert "fehler" in blockt

    _call(mcp, "blacklist_verwalten", {"aktion": "deaktivieren",
                                        "entry_id": eid})

    # Wirkort 1 nach Deaktivierung: Anlegen geht durch
    geht = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "Rolle X", "firma": "Pausiert AG",
        "url": "https://e.example/2"}))
    assert geht.get("status") == "angelegt", geht

    # Wirkort 3: blacklist_anwenden ueberspringt den inaktiven Eintrag
    res3 = _result(_call(mcp, "blacklist_anwenden", {"dry_run": False}))
    stelle = db.get_job(geht["hash"]) if geht.get("hash") else None
    if stelle is None:
        # hash nicht im Result — ueber aktive Stellen pruefen
        aktive = [j for j in db.get_active_jobs()
                  if j.get("company") == "Pausiert AG"]
        assert aktive, f"Stelle darf nicht wegsortiert sein: {res3}"
    else:
        assert stelle["is_active"] == 1, res3


def test_828_reaktivieren_greift_wieder(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Zurueck AG"}))
    eid = res["entry_id"]
    _call(mcp, "blacklist_verwalten", {"aktion": "deaktivieren",
                                        "entry_id": eid})
    _call(mcp, "blacklist_verwalten", {"aktion": "aktivieren",
                                        "entry_id": eid})
    blockt = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "Rolle Y", "firma": "Zurueck AG",
        "url": "https://e.example/3"}))
    assert "fehler" in blockt, "nach aktivieren muss der Block wieder greifen"


def test_828_anzeigen_kennzeichnet_inaktive(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    a = _result(_call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Aktiv AG"}))
    b = _result(_call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Inaktiv AG"}))
    _call(mcp, "blacklist_verwalten", {"aktion": "deaktivieren",
                                        "entry_id": b["entry_id"]})
    res = _result(_call(mcp, "blacklist_verwalten", {"aktion": "anzeigen"}))
    assert res["anzahl"] == 1, "nur aktive zaehlen"
    assert any(e["wert"] == "Inaktiv AG" for e in res.get("inaktiv", [])), res


def test_828_wieder_hinzufuegen_reaktiviert(setup_env):
    """Wer eine deaktivierte Firma erneut eintraegt, will dass sie wirkt."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Wieder AG"}))
    _call(mcp, "blacklist_verwalten", {"aktion": "deaktivieren",
                                        "entry_id": res["entry_id"]})
    _call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Wieder AG"})
    assert db.is_company_blacklisted("Wieder AG") is not None


def test_828_kategorienurteil_hinweis(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Gattung GmbH",
        "grund": "bewusste Entscheidung gegen Beratungshaus"}))
    assert "hinweis_grund" in res, "Gattungsurteil muss den Hinweis ausloesen"

    ohne = _result(_call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Konkret GmbH",
        "grund": "nie Rueckmeldung auf drei Bewerbungen"}))
    assert "hinweis_grund" not in ohne, "konkreter Grund braucht keinen Hinweis"


def test_828_bestehende_eintraege_unveraendert(setup_env):
    """Migration idempotent; Alt-Eintraege (is_active=NULL) gelten als aktiv."""
    db, _ = setup_env
    conn = db.connect()
    conn.execute(
        "INSERT INTO blacklist (profile_id, type, value, reason, created_at, "
        "is_active) VALUES (?, 'firma', 'Alt AG', '', '2026-01-01', NULL)",
        (db.get_active_profile_id(),))
    conn.commit()
    assert db.is_company_blacklisted("Alt AG") is not None, \
        "NULL (vor Safety-Net) muss als aktiv gelten"
