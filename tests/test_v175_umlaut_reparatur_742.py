"""Tests fuer v1.7.5 — #742 (A20): profil_umlaute_reparieren.

Kuratierte Wortlisten-Korrektur mit Dry-Run-Default. Sicherheits-Kern:
NUR gemappte Woerter werden ersetzt (neue/Steuerung/Aussage/Queue bleiben),
ss→ß nie, technologies nie, Backup vor jedem Schreiben, alle Writes ueber
die bestehenden Whitelist-Pfade (Anti-DB-Bypass #514).
"""
import asyncio
import logging
from pathlib import Path

import pytest

from bewerbungs_assistent.tools.profil import (
    _UMLAUT_REPAIR_MAP,
    _umlaute_im_text_reparieren,
)


# =====================================================================
# Wort-Ersetzung (pure function)
# =====================================================================

class TestWortErsetzung:
    def test_issue_beispiele(self):
        text = "Mehrjaehrige Erfahrung im Oekosystem, Geschaeftsfuehrender Ansprechpartner fuer die Aufloesung."
        neu, ersetzt = _umlaute_im_text_reparieren(text)
        assert "Mehrjährige" in neu
        assert "Ökosystem" in neu
        assert "Geschäftsführender" in neu
        assert " für " in neu
        assert "Auflösung" in neu
        assert len(ersetzt) == 5

    def test_legitime_sequenzen_bleiben(self):
        """Die Nicht-Trivialitaet aus dem Issue: kein stumpfes ue→ü."""
        text = ("Die neue Steuerung liefert eine klare Aussage. "
                "Feuer, treuen, Queue, Software, Aerosol bleiben.")
        neu, ersetzt = _umlaute_im_text_reparieren(text)
        assert neu == text
        assert ersetzt == []

    def test_ss_nie_automatisch(self):
        text = "Wir wissen, dass die Strasse gross ist. Aussage und Abschluss."
        neu, ersetzt = _umlaute_im_text_reparieren(text)
        assert neu == text  # kein dass→daß, Strasse→Straße, gross→groß
        assert ersetzt == []

    def test_case_erhaltend(self):
        neu, _ = _umlaute_im_text_reparieren("FUEHRUNG fuehrung Fuehrung")
        assert neu == "FÜHRUNG führung Führung"

    def test_wortgrenzen(self):
        """'fuer' als Teilstring (z.B. in 'Herstellerfuersprache'-artigen
        Kunstwoertern) wird nicht ersetzt — nur ganze Woerter."""
        neu, ersetzt = _umlaute_im_text_reparieren("Kraftstofffuerderung")
        assert neu == "Kraftstofffuerderung"
        assert ersetzt == []

    def test_map_enthaelt_keine_ss_ziele(self):
        """Waechter: niemand schmuggelt ein ß-Ziel in die Map."""
        verstoesse = {k: v for k, v in _UMLAUT_REPAIR_MAP.items() if "ß" in v}
        assert not verstoesse, f"ß-Ziele verboten (#742): {verstoesse}"

    def test_map_schluessel_sind_ascii_lowercase(self):
        for k in _UMLAUT_REPAIR_MAP:
            assert k == k.lower()
            assert all(ord(c) < 128 for c in k), f"Nicht-ASCII-Key: {k}"


# =====================================================================
# Tool-Ebene (DB isoliert)
# =====================================================================

@pytest.fixture
def tmp_db(tmp_path):
    from bewerbungs_assistent.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    db.save_profile({
        "name": "Test", "summary": "Mehrjaehrige Erfahrung fuer PLM.",
    })
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db
    db.close()


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _profil_mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import profil
    mcp = FastMCP("test")
    profil.register(mcp, db, logging.getLogger("test"))
    return mcp


def _befuellen(db):
    pos_id = db.add_position({
        "company": "Musterfirma", "title": "Berater",
        "description": "Fuehrung des Teams waehrend der Einfuehrung.",
        "technologies": "Teamcenter Aufloesung-Tool",  # NIE anfassen
    })
    proj_id = db.add_project(pos_id, {
        "name": "Aufloesung Altsystem",
        "result": "Zusaetzliche Kapazitaeten fuer die neue Steuerung.",
        "technologies": "fuer-tool",  # NIE anfassen
    })
    return pos_id, proj_id


class TestVorschau:
    def test_dry_run_schreibt_nichts(self, tmp_db):
        pos_id, proj_id = _befuellen(tmp_db)
        mcp = _profil_mcp(tmp_db)
        out = _call(mcp, "profil_umlaute_reparieren", {})
        assert out["status"] == "vorschau"
        assert out["gesamt_ersetzungen"] >= 5
        # DB unveraendert
        profile = tmp_db.get_profile()
        assert "Mehrjaehrige" in profile["summary"]
        # Kein Backup im Dry-Run
        assert not list((Path(tmp_db.db_path).parent / "backups").glob(
            "profil_vor_umlautreparatur_*")) if (
            Path(tmp_db.db_path).parent / "backups").exists() else True

    def test_technologies_ausgenommen(self, tmp_db):
        _befuellen(tmp_db)
        mcp = _profil_mcp(tmp_db)
        out = _call(mcp, "profil_umlaute_reparieren", {})
        felder = {(a["bereich"], a["feld"]) for a in out["aenderungen"]}
        assert not any(f == "technologies" for _, f in felder)

    def test_kandidaten_liste(self, tmp_db):
        """Ungemappte ae/oe/ue-Woerter erscheinen als Kuratierungs-Kandidaten."""
        pos_id, _ = _befuellen(tmp_db)
        tmp_db.update_position(pos_id, {
            "tasks": "Xyzfuehlbarkeit dreimal: Xyzfuehlbarkeit Xyzfuehlbarkeit."})
        mcp = _profil_mcp(tmp_db)
        out = _call(mcp, "profil_umlaute_reparieren", {})
        worte = {k["wort"]: k["anzahl"] for k in out["nicht_gemappte_kandidaten"]}
        assert worte.get("xyzfuehlbarkeit") == 3

    def test_bereiche_filter(self, tmp_db):
        _befuellen(tmp_db)
        mcp = _profil_mcp(tmp_db)
        out = _call(mcp, "profil_umlaute_reparieren",
                    {"bereiche": ["persoenlich"]})
        assert all(a["bereich"] == "persoenlich" for a in out["aenderungen"])


class TestAnwenden:
    def test_anwenden_schreibt_und_sichert(self, tmp_db):
        pos_id, proj_id = _befuellen(tmp_db)
        mcp = _profil_mcp(tmp_db)
        out = _call(mcp, "profil_umlaute_reparieren", {"anwenden": True})
        assert out["status"] == "angewendet"
        # Backup existiert und enthaelt den ALTEN Stand
        backup = Path(out["backup_datei"])
        assert backup.exists()
        assert "Mehrjaehrige" in backup.read_text(encoding="utf-8")
        # Profil repariert
        profile = tmp_db.get_profile()
        assert profile["summary"] == "Mehrjährige Erfahrung für PLM."
        pos = profile["positions"][0]
        assert pos["description"] == "Führung des Teams während der Einführung."
        # technologies unangetastet
        assert pos["technologies"] == "Teamcenter Aufloesung-Tool"
        proj = pos["projects"][0]
        assert proj["name"] == "Auflösung Altsystem"
        assert "Zusätzliche Kapazitäten" in proj["result"]
        assert "neue Steuerung" in proj["result"]  # legitim, bleibt
        assert proj["technologies"] == "fuer-tool"

    def test_idempotent(self, tmp_db):
        _befuellen(tmp_db)
        mcp = _profil_mcp(tmp_db)
        _call(mcp, "profil_umlaute_reparieren", {"anwenden": True})
        zweiter = _call(mcp, "profil_umlaute_reparieren", {"anwenden": True})
        assert zweiter["status"] == "nichts_zu_tun"

    def test_kein_profil(self, tmp_path):
        from bewerbungs_assistent.database import Database
        db = Database(tmp_path / "leer.db")
        db.initialize()
        try:
            mcp = _profil_mcp(db)
            out = _call(mcp, "profil_umlaute_reparieren", {})
            assert out["status"] == "kein_profil"
        finally:
            db.close()
