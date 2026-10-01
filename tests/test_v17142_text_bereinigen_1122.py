"""#1122 Nebenbefunde — HTML-Zeichenverweise im Titel, offene Platzhalter im Nachfass-Text.

Beides fiel an einem Screenshot vom 29.09.2026 auf: „PLM Dokumentenmanager
&amp; Prozessmanager“ in Aufgabenzeile, Nachfass-Text und Bewerbungstitel,
und „ich habe mich am {applied_at} auf die Position … beworben“ in einem
Nachfass-Text, der so nicht sendefertig ist.
"""
import asyncio
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

from bewerbungs_assistent.database import _entities_aufloesen  # noqa: E402
from bewerbungs_assistent.services import nachfass_platzhalter as tb  # noqa: E402


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_1122_")
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


# ══ Zeichenverweise ═══════════════════════════════════════════════════

@pytest.mark.parametrize("roh,soll", [
    ("PLM Dokumentenmanager &amp; Prozessmanager", "PLM Dokumentenmanager & Prozessmanager"),
    ("Aufbau &amp;amp; Struktur", "Aufbau & Struktur"),            # doppelt kodiert
    ("Stelle &quot;Senior&quot; (m/w/d)", 'Stelle "Senior" (m/w/d)'),
    ("K&#252;chenhilfe", "Küchenhilfe"),
    ("Gr&uuml;nfl&auml;chenamt", "Grünflächenamt"),
])
def test_1122_zeichenverweise_werden_aufgeloest(roh, soll):
    assert _entities_aufloesen(roh) == soll


@pytest.mark.parametrize("text", [
    "R&D Manager", "AT&T Deutschland", "Forschung & Entwicklung", "A & B GmbH",
    "Preis 5 & 6; Rest", "", None, 42,
])
def test_1122_ein_einzelnes_und_zeichen_bleibt(text):
    """Die Gegenrichtung: kein Fehlalarm bei Firmennamen mit &."""
    assert _entities_aufloesen(text) == text


def test_1122_eine_bewerbung_speichert_den_titel_ohne_zeichenverweis(db):
    aid = db.add_application({"title": "PLM &amp; Prozess (m/w/d)",
                              "company": "Werft &amp; Co", "status": "beworben"})
    app = db.get_application(aid)
    assert app["title"] == "PLM & Prozess (m/w/d)" and app["company"] == "Werft & Co"
    db.update_application(aid, {"title": "Neu &amp; besser"})
    assert db.get_application(aid)["title"] == "Neu & besser"


def test_1122_der_start_heilt_den_bestand_und_ist_idempotent(db):
    from bewerbungs_assistent.job_scraper import stelle_hash
    aid = db.add_application({"title": "X", "company": "Y", "status": "beworben"})
    db.save_jobs([{"hash": stelle_hash("t", "b"), "title": "J", "company": "K",
                   "location": "L", "url": "https://example.com/b", "source": "test",
                   "description": "Text", "score": 1}])
    tid = db.add_task({"titel": "Vorbereiten: A &amp; B", "beschreibung": "C &amp; D"})
    c = db.connect()
    c.execute("UPDATE applications SET title='PLM &amp; Prozess' WHERE id=?", (aid,))
    c.execute("UPDATE jobs SET title='Job &amp; Co', description='Text &amp; mehr'")
    c.commit()

    ergebnis = db._text_bestand_heilen()

    assert ergebnis["zeichenverweise"] >= 4
    assert db.get_application(aid)["title"] == "PLM & Prozess"
    assert db.get_active_jobs()[0]["title"] == "Job & Co"
    assert db.get_active_jobs()[0]["description"] == "Text &amp; mehr"      # unberührt
    t = db.get_task(tid)
    assert (t["titel"], t["beschreibung"]) == ("Vorbereiten: A & B", "C & D")
    assert db._text_bestand_heilen() == {"zeichenverweise": 0, "platzhalter": 0}


def test_1122_die_aufgabenzeile_zeigt_den_titel_ohne_zeichenverweis(db):
    """Der Weg des Screenshots: Bewerbung → Nachfassung → Aufgabenliste."""
    from bewerbungs_assistent.services import aufgaben_sicht
    aid = db.add_application({"title": "PLM &amp; Prozess", "company": "Muster",
                             "status": "beworben"})
    db.add_follow_up(aid, "2099-01-01", "nachfass", template="")
    zeilen = [e for g in aufgaben_sicht.uebersicht(db)["gruppen"].values() for e in g]
    assert all("&amp;" not in str(e.get("titel")) + str(e.get("beschreibung")) for e in zeilen)
    assert any("PLM & Prozess" in e["titel"] for e in zeilen)


# ══ Offene Platzhalter ════════════════════════════════════════════════

def test_1122_platzhalter_werden_aus_der_bewerbung_gefuellt():
    text = 'ich habe mich am {applied_at} auf die Position "X" beworben. Sehr geehrte/r {ansprechpartner},'
    voll = tb.platzhalter_fuellen(text, {"applied_at": "2026-09-07T10:00:00",
                                         "ansprechpartner": "Frau Muster"})
    assert voll == 'ich habe mich am 07.09.2026 auf die Position "X" beworben. Sehr geehrte/r Frau Muster,'
    assert tb.offene_platzhalter(voll) == []


def test_1122_fehlt_ein_wert_verschwindet_die_wendung_statt_einer_luecke():
    text = "ich habe mich am {applied_at} auf die Position beworben.\nSehr geehrte/r {ansprechpartner},\n"
    leer = tb.platzhalter_fuellen(text, {})
    assert leer == "ich habe mich auf die Position beworben.\nSehr geehrte Damen und Herren,\n"
    assert tb.offene_platzhalter(leer) == []


def test_1122_ein_unbekannter_platzhalter_bleibt_als_befund_stehen():
    assert tb.offene_platzhalter(tb.platzhalter_fuellen("Hallo {wer}", {})) == ["{wer}"]


@pytest.mark.parametrize("typ", ["nachfass", "danke", "info"])
@pytest.mark.parametrize("mit_daten", [True, False])
def test_1122_kein_nachfass_text_verlaesst_pbp_mit_offenem_platzhalter(db, typ, mit_daten):
    """Das Akzeptanzkriterium — für jeden Baustein, mit und ohne Daten."""
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import analyse, mit_katalog
    aid = db.add_application({
        "title": "PLM Consultant", "company": "Muster GmbH", "status": "beworben",
        **({"applied_at": "2026-09-07", "ansprechpartner": "Frau Muster"} if mit_daten
           else {"applied_at": ""})})
    mcp = FastMCP("test")
    analyse.register(mit_katalog(mcp, db), db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("nachfass_planen")
        r = await tool.run({"bewerbung_id": aid, "tage": 3, "typ": typ})
        return getattr(r, "structured_content", r)
    erg = asyncio.run(_run())
    erg = erg.get("result", erg) if set(erg) == {"result"} else erg
    assert erg["status"] == "geplant", erg
    assert tb.offene_platzhalter(erg["template"]) == [], erg["template"]
    gespeichert = db.get_follow_up(erg["follow_up_id"])["template"]
    assert tb.offene_platzhalter(gespeichert) == [], gespeichert
    if typ == "nachfass" and mit_daten:
        assert "07.09.2026" in gespeichert


def test_1122_der_start_fuellt_platzhalter_im_bestand(db):
    aid = db.add_application({"title": "PLM", "company": "Muster", "status": "beworben",
                              "applied_at": "2026-09-07", "ansprechpartner": "Frau Muster"})
    fid = db.add_follow_up(
        aid, "2099-01-01", "nachfass",
        template="ich habe mich am {applied_at} beworben.\nSehr geehrte/r {ansprechpartner},")
    ergebnis = db._text_bestand_heilen()
    assert ergebnis["platzhalter"] == 1
    text = db.get_follow_up(fid)["template"]
    assert "07.09.2026" in text and "Frau Muster" in text
    assert tb.offene_platzhalter(text) == []
    assert db._text_bestand_heilen() == {"zeichenverweise": 0, "platzhalter": 0}


def test_1122_der_start_ruft_den_abgleich(db):
    """Nicht nur die Funktion, sondern der Start selbst (L25: ein Schutz
    zählt erst, wenn er aufgerufen wird)."""
    aid = db.add_application({"title": "X", "company": "Y", "status": "beworben"})
    fid = db.add_follow_up(aid, "2099-01-01", "nachfass",
                           template="ich habe mich am {applied_at} beworben")
    db.connect().execute("UPDATE applications SET title='A &amp; B' WHERE id=?", (aid,))
    db.connect().commit()

    db.initialize()

    assert db.get_application(aid)["title"] == "A & B"
    assert tb.offene_platzhalter(db.get_follow_up(fid)["template"]) == []
