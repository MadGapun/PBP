"""v1.7.146 — `bewerbung_details` beginnt mit dem aktuellen Stand (#1153).

Praxisfall (01.10.2026): Ein Gespräch war am 29.09. vom 30.09. auf den 07.10.
verschoben und zugesagt worden (Meeting-Status `bestaetigt`). `bewerbung_details`
begann mit den ältesten Notizen ("OFFENE AUFGABE", alter Termin), die Timeline
lief aufsteigend, das Meeting kam nicht vor, und `nächste_aktionen` sagte bei
Status "interview": "Du hattest ein Interview!". Folge: drei falsche Aussagen
über eine Bewerbung.

Hier: der Stand steht oben, Termine sind dabei, der Verlauf läuft mit dem
Neuesten zuerst, Termin-Änderungen schreiben eine Verlaufszeile, überholte
"offen"-Hinweise werden gekennzeichnet, und die Vorschläge passen zur Zeit.
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
    tmpdir = tempfile.mkdtemp(prefix="pbp_stand1153_")
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


def _zeit(tage=0, stunde=14, minute=0):
    return (datetime.now() + timedelta(days=tage)).replace(
        hour=stunde, minute=minute, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")


def _bewerbung(db, status="interview"):
    return db.add_application({"title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                               "status": status})


def _alt_datieren(db, app_id, tage_zurueck):
    """Alle bisherigen Verlaufseinträge auf 'vor N Tagen' setzen."""
    alt = (datetime.now() - timedelta(days=tage_zurueck)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    con = db.connect()
    con.execute("UPDATE application_events SET event_date=? WHERE application_id=?", (alt, app_id))
    con.commit()


def _details(mcp, app_id):
    return _call(mcp, "bewerbung_details", {"bewerbung_id": app_id})


# ══ Der Stand steht oben ═══════════════════════════════════════════

def test_aktueller_stand_ist_der_erste_schluessel(umgebung):
    db, mcp = umgebung
    app = _bewerbung(db)
    antwort = _details(mcp, app)
    assert list(antwort)[0] == "aktueller_stand"
    assert "lies_zuerst" in antwort["aktueller_stand"]
    # Notizen gehören nach hinten, nicht vor den Stand
    db.update_application(app, {"notes": "Alter Ursprungstext"})
    antwort = _details(mcp, app)
    schluessel = list(antwort)
    assert schluessel.index("notizen") > schluessel.index("nächste_aktionen"), (
        "die Notizen stehen vor dem Stand und den Vorschlägen")
    assert "älter" in antwort["notizen_hinweis"]


def test_der_praxisfall_verschobener_und_zugesagter_termin(umgebung):
    """Genau die drei falschen Aussagen: 'gestern', 'Zusage offen', 'Gespräch hatte stattgefunden'."""
    db, mcp = umgebung
    app = _bewerbung(db, "interview")
    # lange alte Geschichte mit dem Altstand
    db.add_application_event(app, "bearbeitet",
                             "OFFEN UND DRINGEND: Gespräch am 30.09., Gehalt abstimmen.")
    db.add_application_event(app, "bearbeitet",
                             "Status zurück auf geplant, weil die Zusage noch aussteht. "
                             "OFFENE AUFGABE: Termin zusagen.")
    _alt_datieren(db, app, 4)
    alt_beginn, neu_beginn = _zeit(-1, 11), _zeit(7, 11)
    mid = db.add_meeting({"application_id": app, "title": "Gespräch", "meeting_date": alt_beginn,
                          "status": "geplant", "meeting_type": "interview"})
    # der Arbeitgeber verschiebt, und die Zusage kommt: über denselben Weg wie Dashboard und Werkzeug
    from bewerbungs_assistent.services import termin_folgen
    erg = termin_folgen.aendern(db, mid, {"meeting_date": neu_beginn, "status": "bestaetigt",
                                          "notes": "ZUGESAGT"})
    assert erg["geaendert"] is True

    antwort = _details(mcp, app)
    stand = antwort["aktueller_stand"]
    assert stand["naechster_termin"]["beginn"] == neu_beginn
    assert stand["naechster_termin"]["status"] == "bestaetigt"
    assert stand["letzter_eintrag"]["status"] == "termin_bestaetigt"
    # 2. Aussage ("Zusage offen") und 1. ("gestern"): das Meeting ist mit dabei
    assert [t["id"] for t in antwort["termine"]["kommend"]] == [mid]
    assert antwort["termine"]["vergangen"] == []
    # Verlauf: neueste zuerst, die beiden Termin-Zeilen vorn
    zeilen = antwort["timeline"]
    assert antwort["timeline_reihenfolge"] == "neueste zuerst"
    assert [z["status"] for z in zeilen[:2]] == ["termin_bestaetigt", "termin_verschoben"]
    assert "verschoben" in zeilen[1]["notiz"]
    # der alte Eintrag mit "OFFENE AUFGABE" wird gekennzeichnet, nicht verändert
    alt = next(z for z in zeilen if "OFFENE AUFGABE" in z["notiz"])
    assert "überholt" in alt["hinweis"]
    assert "Zusage steht aus" not in alt["hinweis"]
    ohne = next(z for z in zeilen if z["notiz"].startswith("OFFEN UND DRINGEND"))
    assert "überholt" in ohne.get("hinweis", "")
    # 3. Aussage: nichts, was ein vergangenes Gespräch voraussetzt
    text = antwort["nächste_aktionen"]["beschreibung"]
    assert text.startswith("Dein nächstes Gespräch ist am") and "(zugesagt)" in text
    assert "Du hattest ein Interview" not in str(antwort["nächste_aktionen"])
    labels = [a["label"] for a in antwort["nächste_aktionen"]["aktionen"]]
    assert labels[0] == "Gespräch vorbereiten" and "Gesprächsnotizen erfassen" not in labels
    assert [a["prioritaet"] for a in antwort["nächste_aktionen"]["aktionen"]] == list(
        range(1, len(labels) + 1))


def test_ein_vergangenes_gespraech_bleibt_nachbereitung(umgebung):
    db, mcp = umgebung
    app = _bewerbung(db, "interview")
    db.add_meeting({"application_id": app, "title": "Gespräch", "meeting_date": _zeit(-3, 10),
                    "status": "geplant"})
    aktionen = _details(mcp, app)["nächste_aktionen"]
    assert aktionen["beschreibung"].startswith("Dein letztes Gespräch war am")
    assert "Gesprächsnotizen erfassen" in [a["label"] for a in aktionen["aktionen"]]


def test_status_gespraech_ohne_termin_sagt_es_und_bietet_den_termin_an(umgebung):
    db, mcp = umgebung
    app = _bewerbung(db, "interview")
    aktionen = _details(mcp, app)["nächste_aktionen"]
    assert "kein Termin hinterlegt" in aktionen["beschreibung"]
    assert aktionen["aktionen"][0] == {"label": "Termin eintragen", "tool": "meeting_hinzufuegen",
                                       "prioritaet": 1}


def test_andere_status_behalten_ihre_vorschlaege(umgebung):
    db, mcp = umgebung
    from bewerbungs_assistent.tools.bewerbungen import _get_context_actions
    app = _bewerbung(db, "beworben")
    antwort = _details(mcp, app)
    assert antwort["nächste_aktionen"]["aktionen"] == _get_context_actions("beworben")["aktionen"]


def test_ein_abgesagter_termin_ist_kein_naechster_termin(umgebung):
    db, mcp = umgebung
    app = _bewerbung(db, "interview")
    db.add_meeting({"application_id": app, "title": "Abgesagt", "meeting_date": _zeit(3),
                    "status": "abgesagt"})
    antwort = _details(mcp, app)
    assert antwort["aktueller_stand"]["naechster_termin"] is None
    assert [t["status"] for t in antwort["termine"]["kommend"]] == ["abgesagt"]
    assert "kein Termin hinterlegt" in antwort["nächste_aktionen"]["beschreibung"]


def test_offene_aufgaben_und_nachfassungen_stehen_im_stand(umgebung):
    db, mcp = umgebung
    app = _bewerbung(db, "beworben")
    tid = db.add_task({"titel": "Zeugnis kopieren", "application_id": app,
                       "faellig_am": _zeit(2)[:10]})
    erledigt = db.add_task({"titel": "Erledigtes", "application_id": app})
    db.complete_task(erledigt)
    db.add_follow_up(app, _zeit(5)[:10])
    stand = _details(mcp, app)["aktueller_stand"]
    assert [a["id"] for a in stand["offene_aufgaben"]] == [tid]
    assert len(stand["offene_nachfassungen"]) == 1


# ══ Wartest du? Nur ohne Termin ════════════════════════════════════

def test_mit_kommendem_termin_wartet_niemand_auf_antwort(umgebung):
    db, mcp = umgebung
    app = _bewerbung(db, "interview")
    db.add_application_event(app, "interview", "Einladung")
    _alt_datieren(db, app, 20)
    db.add_meeting({"application_id": app, "title": "Gespräch", "meeting_date": _zeit(5),
                    "status": "bestaetigt"})
    antwort = _details(mcp, app)
    assert "Wartest du seit" not in antwort["nächste_aktionen"]["beschreibung"]
    assert antwort["nächste_aktionen"]["beschreibung"].startswith("Dein nächstes Gespräch")


def test_ohne_termin_bleibt_der_nachfass_hinweis_nach_14_tagen(umgebung):
    db, mcp = umgebung
    app = _bewerbung(db, "beworben")
    db.add_application_event(app, "beworben", "Abgeschickt")
    _alt_datieren(db, app, 20)
    assert "Wartest du seit" in _details(mcp, app)["nächste_aktionen"]["beschreibung"]


# ══ Termin-Änderungen schreiben den Verlauf ════════════════════════

def _status_der_ereignisse(db, app):
    return [e["status"] for e in db.get_application(app)["events"]]


def test_verschieben_schreibt_eine_verlaufszeile(umgebung):
    db, _ = umgebung
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    mid = db.add_meeting({"application_id": app, "title": "Gespräch", "meeting_date": _zeit(2)})
    termin_folgen.aendern(db, mid, {"meeting_date": _zeit(9)})
    assert _status_der_ereignisse(db, app).count("termin_verschoben") == 1
    zeile = [e for e in db.get_application(app)["events"] if e["status"] == "termin_verschoben"][0]
    assert "→" in zeile["notes"] and "Gespräch" in zeile["notes"]


def test_absagen_schreibt_nur_die_absage(umgebung):
    db, _ = umgebung
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    mid = db.add_meeting({"application_id": app, "title": "Gespräch", "meeting_date": _zeit(2)})
    termin_folgen.aendern(db, mid, {"meeting_date": _zeit(9), "status": "abgesagt"})
    assert [s for s in _status_der_ereignisse(db, app) if s.startswith("termin_")] == ["termin_abgesagt"]


def test_titel_aendern_schreibt_nichts(umgebung):
    db, _ = umgebung
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    mid = db.add_meeting({"application_id": app, "title": "Gespräch", "meeting_date": _zeit(2)})
    termin_folgen.aendern(db, mid, {"title": "Neuer Titel", "notes": "Zimmer 4"})
    assert not [s for s in _status_der_ereignisse(db, app) if s.startswith("termin_")]


def test_ein_termin_ohne_bewerbung_schreibt_keinen_verlauf(umgebung):
    db, _ = umgebung
    from bewerbungs_assistent.services import termin_folgen
    mid = db.add_meeting({"title": "Privat", "meeting_date": _zeit(2)})
    assert termin_folgen.aendern(db, mid, {"meeting_date": _zeit(3)})["geaendert"] is True


# ══ Die Tool-Beschreibung sagt es ══════════════════════════════════

def test_die_beschreibung_verweist_auf_den_aktuellen_stand(umgebung):
    _, mcp = umgebung

    async def _beschreibung():
        return (await mcp.get_tool("bewerbung_details")).description

    text = asyncio.run(_beschreibung())
    assert "aktueller_stand" in text and "überholt" in text


def test_das_modul_ist_von_status_und_lebenszyklus_abgegrenzt():
    """8d: aehnliche Namen - alle drei existieren, jedes mit eigener Aufgabe."""
    paket = ROOT / "src" / "bewerbungs_assistent" / "services"
    for name in ("bewerbung_stand.py", "bewerbung_status.py", "bewerbung_lebenszyklus.py"):
        assert (paket / name).is_file(), name
    kopf = (paket / "bewerbung_stand.py").read_text(encoding="utf-8")[:900]
    assert "bewerbung_status" in kopf and "bewerbung_lebenszyklus" in kopf
