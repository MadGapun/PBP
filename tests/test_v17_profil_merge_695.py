"""Regression #695: profil_erstellen darf bestehende Profildaten nicht mit
Leerwerten ueberschreiben.

Vorher: db.save_profile setzt ALLE Spalten — ein "Aktualisierungs"-Aufruf
nur mit name loeschte E-Mail/Telefon/Adresse/summary/informal_notes und
setzte preferences auf die Funktions-Defaults zurueck (Datenverlust).

Jetzt: bei bestehendem Profil uebernehmen leere Argumente den Bestandswert,
preferences werden gemerged. Frische DB (kein Profil) verhaelt sich exakt
wie vorher.
"""
import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_695_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    # Isolations-Wachhund: Test darf NIE auf der echten User-DB laufen
    assert str(db.db_path).startswith(tmpdir), (
        f"DB-Isolation verletzt: {db.db_path} liegt nicht unter {tmpdir}"
    )
    yield db
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _make_mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import profil
    import logging
    mcp = FastMCP("test")
    profil.register(mcp, db, logging.getLogger("test"))
    return mcp


_VOLL_PROFIL = {
    "name": "Max Tester",
    "email": "max@example.com",
    "phone": "+49 123 456789",
    "address": "Teststr. 1",
    "city": "Teststadt",
    "plz": "12345",
    "country": "Schweiz",
    "birthday": "1980-01-01",
    "nationality": "deutsch",
    "summary": "Erfahrener Tester.",
    "informal_notes": "Mag Remote-Arbeit, Hund im Buero.",
    "preferences": {
        "stellentyp": "freelance",
        "arbeitsmodell": "remote",
        "min_gehalt": 70000,
        "ziel_gehalt": 85000,
        "min_tagessatz": 800,
        "ziel_tagessatz": 950,
        "reisebereitschaft": "gering",
        "umzug_moeglich": True,
        "custom_key": "bleibt",
    },
}


def test_695_nur_name_loescht_keine_bestandsdaten(setup_env):
    """(a) Aufruf nur mit name laesst alle anderen Felder unveraendert."""
    db = setup_env
    db.save_profile(dict(_VOLL_PROFIL))
    mcp = _make_mcp(db)
    result = _call(mcp, "profil_erstellen", {"name": "Max Tester"})
    assert result["status"] == "gespeichert"
    p = db.get_profile()
    assert p["name"] == "Max Tester"
    assert p["email"] == "max@example.com"
    assert p["phone"] == "+49 123 456789"
    assert p["address"] == "Teststr. 1"
    assert p["city"] == "Teststadt"
    assert p["plz"] == "12345"
    assert p["country"] == "Schweiz"  # Default 'Deutschland' nicht als Eingabe werten
    assert p["birthday"] == "1980-01-01"
    assert p["nationality"] == "deutsch"
    assert p["summary"] == "Erfahrener Tester."
    # informal_notes besonders kritisch — nie durch Leerwert ersetzen
    assert p["informal_notes"] == "Mag Remote-Arbeit, Hund im Buero."
    # Preferences komplett erhalten (inkl. Custom-Key)
    assert p["preferences"] == _VOLL_PROFIL["preferences"]


def test_695_neue_email_aendert_nur_email(setup_env):
    """(b) Neuer email-Wert wird uebernommen, phone bleibt unveraendert."""
    db = setup_env
    db.save_profile(dict(_VOLL_PROFIL))
    mcp = _make_mcp(db)
    _call(mcp, "profil_erstellen",
          {"name": "Max Tester", "email": "neu@example.com"})
    p = db.get_profile()
    assert p["email"] == "neu@example.com"
    assert p["phone"] == "+49 123 456789"
    assert p["informal_notes"] == "Mag Remote-Arbeit, Hund im Buero."


def test_695_preferences_teilupdate_merged(setup_env):
    """(c) Teilupdate einer Praeferenz laesst andere Keys bestehen."""
    db = setup_env
    db.save_profile(dict(_VOLL_PROFIL))
    mcp = _make_mcp(db)
    _call(mcp, "profil_erstellen",
          {"name": "Max Tester", "min_gehalt": 90000})
    p = db.get_profile()
    prefs = p["preferences"]
    assert prefs["min_gehalt"] == 90000          # explizit geaendert
    assert prefs["stellentyp"] == "freelance"    # Default 'beides' ueberschreibt nicht
    assert prefs["arbeitsmodell"] == "remote"
    assert prefs["ziel_gehalt"] == 85000
    assert prefs["reisebereitschaft"] == "gering"
    assert prefs["umzug_moeglich"] is True       # Default False ueberschreibt nicht
    assert prefs["custom_key"] == "bleibt"       # fremde Keys bleiben erhalten


def test_695_frische_db_legt_normal_an(setup_env):
    """(d) Ohne bestehendes Profil legt profil_erstellen normal an."""
    db = setup_env
    assert db.get_profile() is None
    mcp = _make_mcp(db)
    result = _call(mcp, "profil_erstellen", {
        "name": "Neu Nutzer", "email": "neu@example.com", "min_gehalt": 50000,
    })
    assert result["status"] == "gespeichert"
    assert "hinweis" not in result  # Hinweis nur im Update-Fall
    p = db.get_profile()
    assert p["name"] == "Neu Nutzer"
    assert p["email"] == "neu@example.com"
    assert p["country"] == "Deutschland"
    assert p["preferences"]["min_gehalt"] == 50000
    assert p["preferences"]["stellentyp"] == "beides"


def test_695_leerstring_informal_notes_bewahrt_bestand(setup_env):
    """(e) Explizit leerer String fuer informal_notes loescht den Bestand NICHT.

    Der haeufigste Datenverlust-Pfad: ein Aufruf reicht informal_notes=""
    mit (statt es wegzulassen). '' ist falsy -> Bestand muss bleiben.
    """
    db = setup_env
    db.save_profile(dict(_VOLL_PROFIL))
    mcp = _make_mcp(db)
    _call(mcp, "profil_erstellen", {
        "name": "Max Tester", "email": "", "phone": "",
        "summary": "", "informal_notes": "",
    })
    p = db.get_profile()
    assert p["informal_notes"] == "Mag Remote-Arbeit, Hund im Buero."
    assert p["summary"] == "Erfahrener Tester."
    assert p["email"] == "max@example.com"
    assert p["phone"] == "+49 123 456789"


def test_695_nur_telefon_bewahrt_rest(setup_env):
    """(f) Nur phone gesetzt: alle anderen Felder unveraendert."""
    db = setup_env
    db.save_profile(dict(_VOLL_PROFIL))
    mcp = _make_mcp(db)
    _call(mcp, "profil_erstellen", {"name": "Max Tester", "phone": "+49 999 000"})
    p = db.get_profile()
    assert p["phone"] == "+49 999 000"
    assert p["email"] == "max@example.com"
    assert p["informal_notes"] == "Mag Remote-Arbeit, Hund im Buero."
    assert p["summary"] == "Erfahrener Tester."


def test_695_nur_summary_bewahrt_rest(setup_env):
    """(g) Nur summary gesetzt: informal_notes + Kontaktfelder unveraendert."""
    db = setup_env
    db.save_profile(dict(_VOLL_PROFIL))
    mcp = _make_mcp(db)
    _call(mcp, "profil_erstellen",
          {"name": "Max Tester", "summary": "Neue Zusammenfassung."})
    p = db.get_profile()
    assert p["summary"] == "Neue Zusammenfassung."
    assert p["informal_notes"] == "Mag Remote-Arbeit, Hund im Buero."
    assert p["email"] == "max@example.com"
    assert p["phone"] == "+49 123 456789"


def test_695_sequenzielle_teilupdates_verlieren_nichts(setup_env):
    """(h) Mehrere Aufrufe nacheinander mit je anderem Teilfeld akkumulieren,
    ohne je einen frueher gesetzten Wert zu verlieren."""
    db = setup_env
    db.save_profile(dict(_VOLL_PROFIL))
    mcp = _make_mcp(db)
    _call(mcp, "profil_erstellen", {"name": "Max Tester", "email": "a@b.de"})
    _call(mcp, "profil_erstellen", {"name": "Max Tester", "phone": "+49 7 7"})
    _call(mcp, "profil_erstellen", {"name": "Max Tester", "city": "Hamburg"})
    _call(mcp, "profil_erstellen", {"name": "Max Tester", "ziel_gehalt": 99000})
    p = db.get_profile()
    assert p["email"] == "a@b.de"
    assert p["phone"] == "+49 7 7"
    assert p["city"] == "Hamburg"
    assert p["informal_notes"] == "Mag Remote-Arbeit, Hund im Buero."
    assert p["summary"] == "Erfahrener Tester."
    assert p["preferences"]["ziel_gehalt"] == 99000
    assert p["preferences"]["min_gehalt"] == 70000  # nie angefasst -> Bestand
    assert p["preferences"]["custom_key"] == "bleibt"
