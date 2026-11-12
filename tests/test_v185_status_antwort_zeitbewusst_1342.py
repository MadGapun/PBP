"""v1.8.5 — die Antwort von `bewerbung_status_aendern` ist zeitbewusst (#1342).

Anlass (dritter Gesamt-Review, 10.11.2026): Meldet jemand eine Einladung und
Claude setzt den Status "interview", antwortete das Werkzeug mit dem festen
Text "Du hattest ein Interview! Dokumentiere deine Eindrücke ...". #1153 hatte
das nur fuer `bewerbung_details` behoben. Jetzt laufen beide Wege durch
`bewerbung_stand.aktionen_zum_status`.
"""
import asyncio
import importlib
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_status1342_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv
    importlib.reload(_srv)
    db = _srv.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Beispiel Person"})
    yield db, _srv.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def _zeit(tage=0, stunde=14):
    return (datetime.now() + timedelta(days=tage)).replace(
        hour=stunde, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")


def _bewerbung(db, status="eingangsbestaetigung"):
    return db.add_application({"title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                               "status": status})


def _wechseln(mcp, app, status):
    return _call(mcp, "bewerbung_status_aendern",
                 {"bewerbung_id": app, "neuer_status": status})


def _labels(antwort):
    return [a["label"] for a in antwort["nächste_aktionen"]["aktionen"]]


def test_einladung_ohne_termin_fragt_nach_dem_termin_nicht_nach_eindruecken(umgebung):
    db, mcp = umgebung
    app = _bewerbung(db)
    antwort = _wechseln(mcp, app, "interview")
    assert antwort["status"] == "aktualisiert"
    text = str(antwort["nächste_aktionen"])
    assert "Du hattest ein Interview" not in text
    assert "kein Termin hinterlegt" in antwort["nächste_aktionen"]["beschreibung"]
    assert _labels(antwort)[0] == "Termin eintragen"
    assert "Gesprächsnotizen erfassen" not in _labels(antwort)


def test_einladung_mit_kommendem_termin_geht_um_die_vorbereitung(umgebung):
    db, mcp = umgebung
    app = _bewerbung(db)
    db.add_meeting({"application_id": app, "title": "Gespräch", "meeting_date": _zeit(5),
                    "status": "geplant", "meeting_type": "interview"})
    antwort = _wechseln(mcp, app, "interview")
    assert antwort["nächste_aktionen"]["beschreibung"].startswith("Dein nächstes Gespräch ist am")
    assert "Du hattest ein Interview" not in str(antwort["nächste_aktionen"])
    assert _labels(antwort)[0] == "Gespräch vorbereiten"
    assert "Gesprächsnotizen erfassen" not in _labels(antwort)
    assert [a["prioritaet"] for a in antwort["nächste_aktionen"]["aktionen"]] == list(
        range(1, len(_labels(antwort)) + 1))


def test_nach_dem_termin_stehen_die_gespraechsnotizen_vorn(umgebung):
    db, mcp = umgebung
    app = _bewerbung(db)
    db.add_meeting({"application_id": app, "title": "Gespräch", "meeting_date": _zeit(-2, 10),
                    "status": "geplant", "meeting_type": "interview"})
    antwort = _wechseln(mcp, app, "interview")
    assert antwort["nächste_aktionen"]["beschreibung"].startswith("Dein letztes Gespräch war am")
    assert _labels(antwort)[0] == "Gesprächsnotizen erfassen"


def test_zweitgespraech_ist_ebenfalls_zeitbewusst(umgebung):
    db, mcp = umgebung
    app = _bewerbung(db, "interview")
    antwort = _wechseln(mcp, app, "zweitgespraech")
    assert "kein Termin hinterlegt" in antwort["nächste_aktionen"]["beschreibung"]


def test_andere_status_behalten_ihre_festen_vorschlaege(umgebung):
    db, mcp = umgebung
    from bewerbungs_assistent.tools.bewerbungen import _get_context_actions
    app = _bewerbung(db, "offen")
    antwort = _wechseln(mcp, app, "beworben")
    # #1387: die automatisch gesetzte Nachfass-Erinnerung streicht den Vorschlag
    # "Nachfass-Erinnerung planen"; alles andere bleibt in fester Reihenfolge.
    erwartet = [a["tool"] for a in _get_context_actions("beworben")["aktionen"]
                if a["tool"] != "nachfass_planen"]
    assert [a["tool"] for a in antwort["nächste_aktionen"]["aktionen"]] == erwartet


def test_status_antwort_und_details_sagen_dasselbe(umgebung):
    """Eine Frage, eine Funktion: beide Wege liefern dieselben Vorschläge."""
    db, mcp = umgebung
    app = _bewerbung(db)
    db.add_meeting({"application_id": app, "title": "Gespräch", "meeting_date": _zeit(3),
                    "status": "bestaetigt", "meeting_type": "interview"})
    aus_status = _wechseln(mcp, app, "interview")["nächste_aktionen"]
    aus_details = _call(mcp, "bewerbung_details", {"bewerbung_id": app})["nächste_aktionen"]
    assert aus_status == aus_details


def test_unlesbare_termine_werden_benannt_statt_geraten(umgebung):
    """Unbekannt ist ein eigener Zustand: weder 'war' noch 'kein Termin'."""
    db, _ = umgebung
    from bewerbungs_assistent.services import bewerbung_stand as stand
    from bewerbungs_assistent.tools.bewerbungen import _get_context_actions

    class Kaputt:
        def get_meetings_for_application(self, _id):
            raise RuntimeError("Lesefehler")

    aktionen = stand.aktionen_zum_status(Kaputt(), "APP-X", "interview",
                                         _get_context_actions("interview"))
    assert "konnten nicht gelesen werden" in aktionen["beschreibung"]
    assert "Du hattest ein Interview" not in str(aktionen)
    labels = [a["label"] for a in aktionen["aktionen"]]
    assert labels[0] == "Termine ansehen" and "Gesprächsnotizen erfassen" not in labels
    assert [a["prioritaet"] for a in aktionen["aktionen"]] == list(range(1, len(labels) + 1))
