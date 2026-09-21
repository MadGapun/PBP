"""#1065 — eine Stelle zu einer ABGELEHNTEN Bewerbung wurde ohne Hinweis
neu angelegt.

Gemeldet am 21.09.2026 mit zwei belegten Faellen aus dem Bestand: beide
Stellen kamen ueber den Browser-Weg herein, bekamen einen Score und
standen als neu in der Trefferliste. Erst das spaetere Aussortieren mit
Grund `duplikat` meldete `duplikat_erkannt: {typ: "bewerbung", status:
"abgelehnt"}` — dieselbe Frage, an zwei Stellen verschieden beantwortet.

Zwei Ursachen:

1. #567 hat abgeschlossene Bewerbungen aus Stufe A genommen, damit eine
   ANDERE Stelle bei derselben Firma nicht blockiert wird. Richtig — nur
   fand fuer sie danach ueberhaupt keine Pruefung mehr statt.
2. `_detect_duplicate` trug eine EIGENE, vierte Fassung der Regel (Firma
   als Teilstring, zwei gemeinsame Titelwoerter), waehrend die Anlage
   `find_duplicate_job` fragt.

Geblockt wird NICHT (das waere #567 rueckwaerts), und es entsteht keine
fuenfte Regel: `find_repost_of_application` (#782) stellt genau diese
Frage schon und wird in der Liste laengst angezeigt — die Anlage hat sie
nur nie gefragt.
"""
import importlib
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17122_1065_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    d = _db_mod.Database()
    d.initialize()
    assert str(tmpdir) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test"})
    yield d
    d.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _werkzeug(db, name):
    import asyncio
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP Test")
    register_all(mcp, db, logging.getLogger("t"))

    def aufrufen(**kwargs):
        async def _run():
            tool = await mcp.get_tool(name)
            res = await tool.run(kwargs)
            return getattr(res, "structured_content", res)
        return asyncio.run(_run())
    return aufrufen


def _bewerbung(db, titel, firma, status="abgelehnt"):
    bid = db.add_application({
        "title": titel, "company": firma, "status": status,
        "applied_at": "2026-05-04", "channel": "portal",
    })
    return bid


# ══ Der gemeldete Fall ══════════════════════════════════════════════

def test_1065_stelle_zu_abgelehnter_bewerbung_wird_benannt(db):
    """AK 1: die Anlage liefert eine Warnung mit Bewerbungs-ID und Status."""
    bid = _bewerbung(db, "Teamleitung Enterprise Applications",
                     "Musterbetrieb Nord GmbH")
    anlegen = _werkzeug(db, "stelle_manuell_anlegen")
    res = anlegen(titel="Teamleitung Enterprise Applications",
                  firma="Musterbetrieb Nord GmbH",
                  url="https://example.com/neu-ausgeschrieben",
                  beschreibung="Ein ausfuehrlicher Anzeigentext. " * 12,
                  quelle="xing")
    assert res["status"] == "angelegt"
    assert res["warnung"] == "wiedergaenger_bewerbung"
    vorher = res["bewerbung_vorher"]
    assert vorher["bewerbung_id"] == bid[:8]
    assert vorher["status"] == "abgelehnt"
    assert vorher["beworben_am"] == "2026-05-04"


def test_1065_andere_stelle_gleiche_firma_bleibt_ohne_warnung(db):
    """AK 2: #567 bleibt erfuellt — das war der Grund fuer die Ausnahme."""
    _bewerbung(db, "Teamleitung Enterprise Applications",
               "Musterbetrieb Nord GmbH")
    anlegen = _werkzeug(db, "stelle_manuell_anlegen")
    res = anlegen(titel="Sachbearbeitung Rechnungswesen",
                  firma="Musterbetrieb Nord GmbH",
                  url="https://example.com/ganz-andere-stelle",
                  beschreibung="Ein ausfuehrlicher Anzeigentext. " * 12,
                  quelle="xing")
    assert res["status"] == "angelegt"
    assert "warnung" not in res


def test_1065_laufende_bewerbung_blockt_weiterhin(db):
    """Die Gegenrichtung: an Stufe A aendert sich nichts."""
    _bewerbung(db, "Teamleitung Enterprise Applications",
               "Musterbetrieb Nord GmbH", status="beworben")
    anlegen = _werkzeug(db, "stelle_manuell_anlegen")
    res = anlegen(titel="Teamleitung Enterprise Applications",
                  firma="Musterbetrieb Nord GmbH",
                  url="https://example.com/nochmal",
                  beschreibung="Text. " * 30, quelle="xing")
    assert res["warnung"] == "duplikat_bewerbung"
    assert res.get("trotzdem_anlegen") is False


def test_1065_anlage_und_aussortieren_sind_sich_einig(db):
    """AK 4: derselbe Befund auf beiden Wegen. Das war der Kern der
    Meldung — die Anlage sagte "angelegt", das Aussortieren
    "duplikat_erkannt"."""
    bid = _bewerbung(db, "Teamleitung Enterprise Applications",
                     "Musterbetrieb Nord GmbH")
    anlegen = _werkzeug(db, "stelle_manuell_anlegen")
    res = anlegen(titel="Teamleitung Enterprise Applications",
                  firma="Musterbetrieb Nord GmbH",
                  url="https://example.com/neu-ausgeschrieben",
                  beschreibung="Ein ausfuehrlicher Anzeigentext. " * 12,
                  quelle="xing")
    bewerten = _werkzeug(db, "stelle_bewerten")
    urteil = bewerten(job_hash=res["hash"], bewertung="passt_nicht",
                      gruende=["bereits_beworben", "duplikat"])
    erkannt = urteil.get("duplikat_erkannt")
    assert erkannt is not None
    assert erkannt["typ"] == "bewerbung"
    assert erkannt["id"] == bid[:8]
    assert erkannt["status"] == "abgelehnt"
    # Beide nennen dieselbe Bewerbung.
    assert res["bewerbung_vorher"]["bewerbung_id"] == erkannt["id"]


def test_1065_beide_wege_schweigen_bei_einer_anderen_stelle(db):
    """Und sie sind sich auch im NEIN einig — sonst waere die Gleichheit
    nur die eines gemeinsamen Fehlalarms."""
    _bewerbung(db, "Teamleitung Enterprise Applications",
               "Musterbetrieb Nord GmbH")
    anlegen = _werkzeug(db, "stelle_manuell_anlegen")
    res = anlegen(titel="Sachbearbeitung Rechnungswesen",
                  firma="Musterbetrieb Nord GmbH",
                  url="https://example.com/andere", quelle="xing",
                  beschreibung="Ein ausfuehrlicher Anzeigentext. " * 12)
    bewerten = _werkzeug(db, "stelle_bewerten")
    urteil = bewerten(job_hash=res["hash"], bewertung="passt_nicht",
                      gruende=["duplikat"])
    assert "warnung" not in res
    assert urteil.get("duplikat_erkannt") is None


def test_1065_uebersteuerte_laufende_bewerbung_ist_kein_wiedergaenger(db):
    """Der isolierende Fall fuer den Filter auf abgeschlossene Bewerbungen.

    Ohne `force` blockt eine laufende Bewerbung schon in Stufe A, der
    Filter waere also wirkungslos — die Gegenprobe hat ihn zu Recht als
    stumm gemeldet. Mit `force=True` laeuft die Anlage weiter, und dann
    entscheidet er: eine LAUFENDE Bewerbung ist kein Wiedergaenger,
    sondern ein uebersteuertes Duplikat, und das steht schon in
    `duplikat_uebersteuert`. Zwei Namen fuer denselben Sachverhalt waeren
    ein dritter Befund ueber dieselbe Frage (#963).
    """
    _bewerbung(db, "Teamleitung Enterprise Applications",
               "Musterbetrieb Nord GmbH", status="beworben")
    anlegen = _werkzeug(db, "stelle_manuell_anlegen")
    res = anlegen(titel="Teamleitung Enterprise Applications",
                  firma="Musterbetrieb Nord GmbH",
                  url="https://example.com/trotzdem",
                  beschreibung="Ein ausfuehrlicher Anzeigentext. " * 12,
                  quelle="xing", force=True)
    assert res["status"] == "angelegt"
    assert res.get("duplikat_uebersteuert") is not None
    assert res.get("warnung") != "wiedergaenger_bewerbung"
    assert "bewerbung_vorher" not in res


def test_1065_der_sammelweg_verhaelt_sich_gleich(db):
    """AK 3: `linkedin_treffer_uebernehmen` laeuft ueber denselben Rumpf
    (`_stelle_uebernehmen`, v1.7.42) und erbt die Pruefung damit."""
    quelle = (ROOT / "src/bewerbungs_assistent/tools/jobs.py").read_text(
        encoding="utf-8-sig")
    block = quelle[quelle.index("def linkedin_treffer_uebernehmen"):]
    block = block[:block.index("\n    @mcp.tool()")]
    assert "_stelle_uebernehmen(" in block
    # Und der Rumpf traegt die Pruefung wirklich.
    rumpf = quelle[quelle.index("def _stelle_uebernehmen"):]
    rumpf = rumpf[:rumpf.index("\n    @mcp.tool()")]
    assert "find_repost_of_application" in rumpf


def test_1065_nur_eine_regel_fuer_dieselbe_frage():
    """Guard: `_detect_duplicate` hatte eine eigene Wortzaehlung. Eine
    zweite Fassung derselben Frage war die Ursache (#963)."""
    quelle = (ROOT / "src/bewerbungs_assistent/tools/jobs.py").read_text(
        encoding="utf-8-sig")
    block = quelle[quelle.index("def _detect_duplicate"):]
    block = block[:block.index("\n    def _normalize_dismiss_reason")]
    assert "find_duplicate_job" in block
    assert "title_words" not in block
    assert "overlap" not in block
