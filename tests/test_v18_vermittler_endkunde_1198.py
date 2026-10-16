"""#1198: die Abnahme des Issues, unabhaengig von den Tests des Fremdbeitrags (PR #1230, in 1.8.0 uebernommen).

Die Lage aus dem Issue: eine laufende Bewerbung ueber einen Vermittler; die Firma der neuen Stelle steht nur im Notiztext, das
Feld `endkunde` ist leer. Erwartet (Abnahme): keine Tatsachenbehauptung "nennt ... als Endkunden"; ein eingetragener Endkunde
ist massgeblich; nach `bewerbung_bearbeiten(endkunde=...)` stimmen `firma_kontext` und die Stelle ueberein.
Alle Firmen sind erfunden.
"""
import asyncio
import logging

import pytest

LANGER_TEXT = ("Aufgaben: Betreuung und Weiterentwicklung der Werkzeugbau-Planung, Abstimmung mit den Fachbereichen und "
               "Steuerung externer Dienstleister. Anforderungen: Studium, mehrjaehrige Berufserfahrung, sichere "
               "Kommunikation in Deutsch und Englisch.")


def _werkzeug(db, name):
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


def _lage(db, *, endkunde="", vermittler="", notes="Starke Partnerschaft mit Firma F"):
    db.save_profile({"name": "Test"})
    aid = db.add_application({
        "title": "Senior Program Manager", "company": "Firma G", "status": "beworben", "applied_at": "2026-10-10",
        "url": "https://g.example/a", "notes": notes, "endkunde": endkunde, "vermittler": vermittler})
    db.save_jobs([{"hash": "f1", "title": "Leiter Werkzeugbau", "company": "Firma F", "location": "Hamburg",
                   "url": "https://f.example/j/1", "source": "stepstone", "description": LANGER_TEXT, "score": 40,
                   "employment_type": "festanstellung"}])
    return aid


def _stelle_ueber_alle_wege(db):
    """Die Stelle, wie die Werkzeuge sie nennen: Liste und Analyse."""
    liste = _werkzeug(db, "stellen_anzeigen")()["stellen"]
    aus_liste = next(s for s in liste if s["id"] == "f1")
    analyse = _werkzeug(db, "fit_analyse")(job_hash="f1")
    return aus_liste, analyse


def test_freitext_allein_ist_keine_tatsachenbehauptung(tmp_db):
    _lage(tmp_db, endkunde="")
    for stelle in _stelle_ueber_alle_wege(tmp_db):
        text = stelle.get("repost_warnung") or ""
        assert "als Endkunden nennt" not in text and "nennt Firma F als Endkunde" not in text, text
        if text:
            assert stelle["repost_details"]["sicher"] is False


def test_ein_eingetragener_endkunde_ist_massgeblich(tmp_db):
    _lage(tmp_db, endkunde="Firma F")
    for stelle in _stelle_ueber_alle_wege(tmp_db):
        assert stelle.get("repost_warnung"), "der eingetragene Endkunde ist die neue Firma: die Warnung bleibt"
        assert stelle["repost_details"]["art"] == "vermittler"
        assert "Firma F" in stelle["repost_warnung"]


def test_ein_anderer_endkunde_verhindert_die_warnung(tmp_db):
    _lage(tmp_db, endkunde="Firma G")
    for stelle in _stelle_ueber_alle_wege(tmp_db):
        assert "repost_warnung" not in stelle and "repost_details" not in stelle


def test_nach_dem_nachtragen_stimmen_firma_kontext_und_stelle_ueberein(tmp_db):
    aid = _lage(tmp_db, endkunde="")
    ergebnis = _werkzeug(tmp_db, "bewerbung_bearbeiten")(bewerbung_id=aid, endkunde="Firma G", vermittler="Firma H")
    assert ergebnis["status"] == "aktualisiert"
    for stelle in _stelle_ueber_alle_wege(tmp_db):
        assert "repost_warnung" not in stelle, stelle.get("repost_warnung")
    kontext = _werkzeug(tmp_db, "firma_kontext")(firmenname="Firma F")
    assert kontext["warnungen"] == []


def test_ohne_endkunde_und_ohne_notiztreffer_gibt_es_nichts(tmp_db):
    _lage(tmp_db, endkunde="", notes="Nichts Besonderes")
    for stelle in _stelle_ueber_alle_wege(tmp_db):
        assert "repost_warnung" not in stelle


def test_gleiche_firma_bleibt_stufe_a(tmp_db):
    """Dieselbe Firma wie die Bewerbung ist kein Vermittlerfall: die bisherige Warnung (Stufe A) bleibt."""
    tmp_db.save_profile({"name": "Test"})
    tmp_db.add_application({"title": "Leiter Werkzeugbau", "company": "Firma F", "status": "beworben",
                           "applied_at": "2026-10-10", "url": "https://f.example/orig"})
    tmp_db.save_jobs([{"hash": "f1", "title": "Leiter Werkzeugbau (m/w/d)", "company": "Firma F", "location": "Hamburg",
                       "url": "https://f.example/kopie", "source": "stepstone", "description": LANGER_TEXT, "score": 40,
                       "employment_type": "festanstellung"}])
    liste = _werkzeug(tmp_db, "stellen_anzeigen")()["stellen"]
    stelle = next(s for s in liste if s["id"] == "f1")
    assert stelle.get("repost_warnung"), "die Kopie derselben Firma wird weiter gewarnt"
    assert stelle["repost_details"]["art"] != "vermittler"
