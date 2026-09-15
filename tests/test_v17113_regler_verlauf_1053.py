"""Tests fuer #1053 — Scoring-Regler hinterlassen eine Spur.

Nutzerbericht vom 15.09.2026: ein Regler `schwellenwert/schwellenwert`
stand mit 35 im Bestand, wirkte nicht, und niemand konnte feststellen,
wer ihn wann und warum gesetzt hatte. Regler trugen weder Zeitpunkt der
Aenderung noch Vorgaengerwert noch Begruendung — ausgerechnet die
Einstellungen, die jede Sortierentscheidung mitbestimmen.
"""
import asyncio
import importlib
import logging
import os
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))


@pytest.fixture
def umgebung(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    db = database.Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.switch_profile(db.create_profile("Muster"))

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP Test 1053")
    register_all(mcp, db, logging.getLogger("test.1053"))
    try:
        yield db, mcp
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(_run())


def _zeile(db, dimension, sub_key):
    zeile = db.connect().execute(
        "SELECT * FROM scoring_config WHERE dimension=? AND sub_key=?",
        (dimension, sub_key)).fetchone()
    return dict(zeile) if zeile else None


NEU = ("entfernung_gehalt_kompensation", "spanne")


def _ohne_vorgabe(db, dimension, sub_key):
    """Die Migration legt Vorgabewerte als Zeilen an. Fuer den Fall "ein
    neuer Regler" muss die Vorgabe weg — sonst hat er zu Recht einen
    Vorgaenger (beim ersten Lauf dieses Tests genau so geschehen)."""
    conn = db.connect()
    conn.execute("DELETE FROM scoring_config WHERE dimension=? AND sub_key=?",
                 (dimension, sub_key))
    conn.commit()


# ------------------------------------------------ Zeitpunkt, Vorgaenger, Grund


def test_setzen_haelt_zeitpunkt_vorgaenger_und_begruendung(umgebung):
    db, _ = umgebung
    _ohne_vorgabe(db, *NEU)
    db.set_scoring_config(*NEU, 20000, begruendung="Umzug waere denkbar")
    erst = _zeile(db, *NEU)
    assert erst["created_at"] and erst["updated_at"]
    assert erst["wert_vorher"] is None, "ein neuer Regler hat keinen Vorgaenger"
    assert erst["begruendung"] == "Umzug waere denkbar"

    db.set_scoring_config(*NEU, 30000)
    zweit = _zeile(db, *NEU)
    assert zweit["value"] == 30000
    assert zweit["wert_vorher"] == 20000
    assert zweit["created_at"] == erst["created_at"], (
        "Der Anlagezeitpunkt ist beim Aendern verlorengegangen.")
    assert zweit["begruendung"] == "Umzug waere denkbar", (
        "Ohne neue Begruendung bleibt die alte stehen.")

    verlauf = db.get_scoring_verlauf("entfernung_gehalt_kompensation")
    assert [(e["wert_vorher"], e["wert_neu"]) for e in verlauf] == [
        (20000, 30000), (None, 20000)]
    assert {e["herkunft"] for e in verlauf} == {"ich"}


def test_derselbe_wert_ist_keine_geschichte(umgebung):
    db, _ = umgebung
    db.set_scoring_config(*NEU, 20000)
    db.set_scoring_config(*NEU, 30000)
    db.set_scoring_config(*NEU, 30000)
    assert _zeile(db, *NEU)["wert_vorher"] == 20000
    assert len(db.get_scoring_verlauf("entfernung_gehalt_kompensation")) == 2


def test_ein_seed_wert_wird_zum_vorgaenger(umgebung):
    """Die Vorgaben stehen als Zeilen im Bestand — sie sind ein Wert."""
    db, _ = umgebung
    seed = _zeile(db, "remote", "hybrid")
    if seed is None:
        pytest.skip("kein Vorgabewert fuer remote/hybrid im Schema")
    db.set_scoring_config("remote", "hybrid", (seed["value"] or 0) + 1)
    assert _zeile(db, "remote", "hybrid")["wert_vorher"] == seed["value"]


# ------------------------------------------------ Abweisen beim Schreiben


def test_die_datenbank_weist_einen_wirkungslosen_schluessel_ab(umgebung):
    """Nicht nur das Werkzeug: jeder Aufrufer von `set_scoring_config`."""
    db, _ = umgebung
    with pytest.raises(ValueError):
        db.set_scoring_config("schwellenwert", "schwellenwert", 35)
    assert _zeile(db, "schwellenwert", "schwellenwert") is None
    assert db.get_scoring_verlauf("schwellenwert") == []


def test_begriffs_regler_sind_wirksam_und_werden_angenommen(umgebung):
    """`keyword` und `muss_kriterium` liest der Scoring-Dienst — sie fehlten
    im Vokabular, das Werkzeug wies sie seit v1.7.36 ab und `anzeigen`
    nannte bestehende "wirkungslos"."""
    from bewerbungs_assistent.services import scoring_service, scoring_vokabular
    db, mcp = umgebung
    assert scoring_vokabular.pruefe("keyword", "Leiharbeit") == ""
    assert scoring_vokabular.pruefe("muss_kriterium", "Produktdaten") == ""
    assert scoring_vokabular.pruefe("keyword", "  ") != ""

    antwort = _call(mcp, "scoring_konfigurieren", {
        "aktion": "setzen", "dimension": "keyword", "sub_key": "Leiharbeit",
        "wert": -4})
    assert antwort.get("status") == "gespeichert", antwort
    stelle = {"title": "Sachbearbeitung in Leiharbeit", "description": "",
              "employment_type": "festanstellung"}
    assert scoring_service.apply_scoring_adjustments(stelle, 10, db)[
        "final_score"] == 6
    anzeige = _call(mcp, "scoring_konfigurieren", {"aktion": "anzeigen"})
    eintrag = next(e for e in anzeige["scoring_regler"]["keyword"]
                   if e["sub_key"] == "Leiharbeit")
    assert "wirkt" not in eintrag, eintrag


def test_jede_gelesene_dimension_steht_im_vokabular():
    """Die naechste fehlende Dimension soll ein Test finden, kein Fehlalarm."""
    from bewerbungs_assistent.services import scoring_vokabular
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "services"
              / "scoring_service.py").read_text(encoding="utf-8")
    gelesen = set(re.findall(r'k\[0\] == "(\w+)"', quelle))
    gelesen |= set(re.findall(r'cfg\.get\(\("(\w+)"', quelle))
    gelesen |= set(re.findall(r'_key = \("(\w+)"', quelle))
    gelesen |= set(re.findall(r'dim = "(\w+)"', quelle))
    assert {"keyword", "muss_kriterium", "remote", "schwellenwert"} <= gelesen, (
        f"Die Suche nach gelesenen Dimensionen findet zu wenig: {gelesen}")
    fehlend = gelesen - set(scoring_vokabular.VOKABULAR)
    assert not fehlend, f"Gelesen, aber nicht im Vokabular: {sorted(fehlend)}"


# ------------------------------------------------ alle Schreiber mit Spur


def test_der_lerneffekt_schreibt_als_automatik(umgebung):
    db, mcp = umgebung
    db.set_setting("dismiss_counts", {"zeitarbeit": 200})
    db.save_jobs([{
        "hash": "lern1053", "title": "Stelle 1053", "company": "Testfirma GmbH",
        "location": "HH", "url": "https://e.example/1053", "source": "demo",
        "description": "Beschreibung. " * 20,
        "employment_type": "festanstellung", "score": 30}])
    _call(mcp, "stelle_bewerten", {
        "job_hash": "lern1053", "bewertung": "passt_nicht",
        "gruende": ["zeitarbeit"]})
    zeile = _zeile(db, "stellentyp", "zeitarbeit")
    assert zeile["value"] == -8
    assert not zeile["set_by_user"], "eine gelernte Zeile ist keine Handzeile"
    eintrag = db.get_scoring_verlauf("stellentyp")[0]
    assert eintrag["herkunft"] == "automatik"
    assert eintrag["wert_neu"] == -8
    assert "zeitarbeit" in (eintrag["begruendung"] or "")


def test_loeschen_und_zuruecksetzen_hinterlassen_eine_spur(umgebung):
    db, mcp = umgebung
    db.set_scoring_config(*NEU, 20000)
    antwort = _call(mcp, "scoring_konfigurieren", {
        "aktion": "loeschen", "dimension": NEU[0], "sub_key": NEU[1],
        "begruendung": "doch nicht"})
    assert antwort["status"] == "geloescht"
    letzter = db.get_scoring_verlauf(NEU[0])[0]
    assert (letzter["wert_vorher"], letzter["wert_neu"]) == (20000, None)
    assert letzter["begruendung"] == "doch nicht"

    db.set_scoring_config("remote", "remote", 7)
    _call(mcp, "scoring_konfigurieren", {"aktion": "reset"})
    assert _zeile(db, "remote", "remote") is None
    assert any(e["wert_vorher"] == 7 and e["wert_neu"] is None
               for e in db.get_scoring_verlauf("remote"))


# ------------------------------------------------ der wirkungslose Eintrag


def _stray(db):
    conn = db.connect()
    conn.execute(
        "INSERT INTO scoring_config (profile_id, dimension, sub_key, value, "
        "ignore_flag, created_at) VALUES ('', 'schwellenwert', "
        "'schwellenwert', 35, 0, '2026-05-01')")
    conn.commit()


def test_die_bereinigung_entfernt_den_eintrag_mit_spur(umgebung):
    db, _ = umgebung
    _stray(db)
    db.initialize()
    assert _zeile(db, "schwellenwert", "schwellenwert") is None
    verlauf = db.get_scoring_verlauf("schwellenwert")
    assert len(verlauf) == 1
    assert verlauf[0]["herkunft"] == "bereinigung"
    assert verlauf[0]["wert_vorher"] == 35
    assert "auto_ignore" in verlauf[0]["begruendung"]
    # Der gelesene Regler bleibt unangetastet.
    assert db.get_scoring_threshold() == 0


def test_die_bereinigung_ist_idempotent(umgebung):
    db, _ = umgebung
    _stray(db)
    db.initialize()
    db.initialize()
    assert len(db.get_scoring_verlauf("schwellenwert")) == 1


# ------------------------------------------------ was das Werkzeug zeigt


def test_anzeigen_nennt_zeitpunkt_vorgaenger_grund_und_herkunft(umgebung):
    db, mcp = umgebung
    _call(mcp, "scoring_konfigurieren", {
        "aktion": "setzen", "dimension": NEU[0], "sub_key": NEU[1],
        "wert": 20000, "begruendung": "erster Versuch"})
    _call(mcp, "scoring_konfigurieren", {
        "aktion": "setzen", "dimension": NEU[0], "sub_key": NEU[1],
        "wert": 25000})
    antwort = _call(mcp, "scoring_konfigurieren", {"aktion": "anzeigen"})
    eintrag = next(e for e in antwort["scoring_regler"][NEU[0]]
                   if e["sub_key"] == NEU[1])
    assert eintrag["wert"] == 25000
    assert eintrag["wert_vorher"] == 20000
    assert eintrag["begruendung"] == "erster Versuch"
    assert eintrag["geaendert_am"] and eintrag["angelegt_am"]
    assert eintrag["herkunft"] == "ich"


def test_die_aktion_verlauf_liefert_die_aenderungen(umgebung):
    db, mcp = umgebung
    db.set_scoring_config(*NEU, 20000)
    antwort = _call(mcp, "scoring_konfigurieren",
                    {"aktion": "verlauf", "dimension": NEU[0]})
    assert antwort["anzahl"] == 1
    assert antwort["verlauf"][0]["wert_neu"] == 20000


# ------------------------------------------------ nur ein Schreibweg


def test_kein_schreibender_zugriff_ausserhalb_der_datenbank():
    """Drei Schreiber mit eigenem SQL waren drei Stellen ohne Spur."""
    wurzel = _repo() / "src" / "bewerbungs_assistent"
    muster = re.compile(
        r"(INSERT\s+(OR\s+\w+\s+)?INTO|UPDATE|DELETE\s+FROM)\s+scoring_config\b",
        re.IGNORECASE)
    funde = []
    for datei in wurzel.rglob("*.py"):
        if datei.name == "database.py":
            continue
        for nummer, zeile in enumerate(
                datei.read_text(encoding="utf-8-sig").splitlines(), 1):
            if zeile.lstrip().startswith("#"):
                continue
            if muster.search(zeile):
                funde.append(f"{datei.name}:{nummer}")
    assert not funde, "Regler-Writes ausserhalb des Nadeloehrs: " + ", ".join(funde)
