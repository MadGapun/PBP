"""#1232 — eine interne Notiz schließt den automatischen Nachfass nicht mehr.

Der Fall (15.10.2026, am echten Bestand gemessen): Seit #1123 galt JEDE Notiz
als „Kontakt mit dem Arbeitgeber“ und machte die offene Nachfass-Erinnerung
hinfällig. Der übliche Ablauf mit Claude ist aber: Bewerbung anlegen (das legt
den 21-Tage-Nachfass an) und gleich danach eine interne Notiz (Recherche,
Abgrenzung, Vorbereitung). Zwei von drei Schließungen durch Notizen waren zu
Unrecht; der Mensch merkte es nicht, weil die Antwort ein Feld
`nachfassung_erledigt` trug, obwohl `hinfaellig` gespeichert wurde.

Jetzt gilt: `art="intern"` (Vorgabe) lässt die Erinnerung stehen, `kontakt`
macht sie hinfällig (wie bisher), `nachfrage` setzt sie auf `erledigt`; das
Rückgabefeld trägt den gespeicherten Zustand.

Alle Daten sind relativ zu heute (L28: Tests mit festen Daten verfallen).
"""
import asyncio
import importlib
import logging
import os
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _tag(tage: int) -> str:
    return (date.today() + timedelta(days=tage)).isoformat()


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_1232_")
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


def _mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import bewerbungen, mit_katalog
    mcp = FastMCP("test")
    bewerbungen.register(mit_katalog(mcp, db), db, logging.getLogger("test"))
    return mcp


def _aufruf(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        r = await tool.run(args)
        return getattr(r, "structured_content", r)
    erg = asyncio.run(_run())
    return erg.get("result", erg) if isinstance(erg, dict) and set(erg) == {"result"} else erg


def _bewerbung(db, status="beworben"):
    return db.add_application({
        "title": "PLM Dokumentenmanager (m/w/d)", "company": "Musterfirma",
        "status": status, "applied_at": _tag(-20)})


def _nachfassung(db, app_id, typ="nachfass"):
    return db.add_follow_up(app_id, _tag(14), typ, template="Nachfassen")


def _offene(db, app_id):
    return [f["id"] for f in db.get_pending_follow_ups() if f["application_id"] == app_id]


def _zeile(db, fid):
    return db.get_follow_up(fid)


def _notizen(db, app_id):
    return [e["notes"] for e in db.get_application(app_id)["events"] if e.get("status") == "notiz"]


# ══ AK 1: eine Notiz ohne art=kontakt lässt die Erinnerung unverändert ═════

def test_1232_ohne_art_bleibt_die_erinnerung_offen(db):
    app = _bewerbung(db)
    fid = _nachfassung(db, app)
    erg = _aufruf(_mcp(db), "bewerbung_notiz",
                  {"bewerbung_id": app, "notiz": "Abgrenzung zu einer anderen Stelle derselben Firma"})
    assert erg["status"] == "gespeichert"
    assert erg["art"] == "intern"
    assert _offene(db, app) == [fid]
    assert _zeile(db, fid)["status"] == "geplant"
    assert not any(k.startswith("nachfassung_") for k in erg), erg


@pytest.mark.parametrize("art", ["intern", "INTERN", "  intern  ", ""])
def test_1232_intern_in_jeder_schreibweise_laesst_sie_stehen(db, art):
    app = _bewerbung(db)
    fid = _nachfassung(db, app)
    erg = _aufruf(_mcp(db), "bewerbung_notiz",
                  {"bewerbung_id": app, "notiz": "Recherche zum Standort", "art": art})
    assert erg["art"] == "intern"
    assert _offene(db, app) == [fid]


def test_1232_die_notiz_steht_trotzdem_im_verlauf(db):
    app = _bewerbung(db)
    _nachfassung(db, app)
    _aufruf(_mcp(db), "bewerbung_notiz", {"bewerbung_id": app, "notiz": "interne Einschätzung XYZ"})
    assert any("interne Einschätzung XYZ" in (n or "") for n in _notizen(db, app))


# ══ AK 2: art=kontakt verhält sich wie bisher (#1123) ══════════════════════

def test_1232_kontakt_macht_die_erinnerung_hinfaellig(db):
    app = _bewerbung(db)
    fid = _nachfassung(db, app)
    erg = _aufruf(_mcp(db), "bewerbung_notiz",
                  {"bewerbung_id": app, "notiz": "Telefonat mit der Personalabteilung", "art": "kontakt"})
    assert _offene(db, app) == []
    zeile = _zeile(db, fid)
    assert zeile["status"] == "hinfaellig" and zeile["completed_at"]      # nicht gelöscht
    assert any("Nachfrage erledigt" in (n or "") for n in _notizen(db, app))  # Verlauf wie bisher


# ══ AK 4: das Rückgabefeld entspricht dem gespeicherten Zustand ═══════════

def test_1232_das_feld_heisst_wie_der_gespeicherte_zustand_hinfaellig(db):
    app = _bewerbung(db)
    fid = _nachfassung(db, app)
    erg = _aufruf(_mcp(db), "bewerbung_notiz",
                  {"bewerbung_id": app, "notiz": "Rückruf des Recruiters", "art": "kontakt"})
    assert erg["nachfassung_hinfaellig"][0]["id"] == fid
    assert "nachfassung_erledigt" not in erg
    assert _zeile(db, fid)["status"] == "hinfaellig"
    # und die Antwort sagt, wie man es rückgängig macht
    assert "nachfass_planen" in erg["hinweis"]


def test_1232_eine_eigene_nachfrage_setzt_erledigt(db):
    app = _bewerbung(db)
    fid = _nachfassung(db, app)
    erg = _aufruf(_mcp(db), "bewerbung_notiz",
                  {"bewerbung_id": app, "notiz": "Beim Vermittler nach dem Stand gefragt", "art": "nachfrage"})
    assert erg["nachfassung_erledigt"][0]["id"] == fid
    assert "nachfassung_hinfaellig" not in erg
    zeile = _zeile(db, fid)
    assert zeile["status"] == "erledigt" and zeile["completed_at"]
    assert _offene(db, app) == []


@pytest.mark.parametrize("art, feld, gespeichert", [
    ("kontakt", "nachfassung_hinfaellig", "hinfaellig"),
    ("nachfrage", "nachfassung_erledigt", "erledigt"),
])
def test_1232_der_feldname_ist_der_gespeicherte_zustand(db, art, feld, gespeichert):
    app = _bewerbung(db)
    fid = _nachfassung(db, app)
    erg = _aufruf(_mcp(db), "bewerbung_notiz", {"bewerbung_id": app, "notiz": "x", "art": art})
    gemeldet = [k for k in erg if k.startswith("nachfassung_")]
    assert gemeldet == [feld]
    assert _zeile(db, fid)["status"] == gespeichert
    assert feld.endswith(gespeichert)


# ══ was nie schließt ═════════════════════════════════════════════════════

@pytest.mark.parametrize("art", ["kontakt", "nachfrage"])
def test_1232_nur_nachfragen_werden_geschlossen_keine_danke_mail(db, art):
    app = _bewerbung(db)
    danke = _nachfassung(db, app, typ="danke")
    nach = _nachfassung(db, app)
    _aufruf(_mcp(db), "bewerbung_notiz", {"bewerbung_id": app, "notiz": "x", "art": art})
    assert _offene(db, app) == [danke]
    assert nach not in _offene(db, app)


def test_1232_eine_unbekannte_art_wird_abgewiesen_und_schreibt_nichts(db):
    app = _bewerbung(db)
    fid = _nachfassung(db, app)
    vorher = len(_notizen(db, app))
    erg = _aufruf(_mcp(db), "bewerbung_notiz",
                  {"bewerbung_id": app, "notiz": "sollte nicht gespeichert werden", "art": "gespraech"})
    assert "fehler" in erg and set(erg["erlaubt"]) == {"intern", "kontakt", "nachfrage"}
    assert len(_notizen(db, app)) == vorher
    assert _offene(db, app) == [fid]


def test_1232_eine_unbekannte_bewerbung_bleibt_ein_fehler(db):
    erg = _aufruf(_mcp(db), "bewerbung_notiz",
                  {"bewerbung_id": "gibtesnicht", "notiz": "x", "art": "kontakt"})
    assert erg["fehler"] == "Bewerbung nicht gefunden."


# ══ AK 3: der Praxisfall — anlegen, dann sofort eine Notiz ════════════════

def test_1232_bewerbung_erstellen_dann_notiz_laesst_den_automatischen_nachfass_offen(db):
    mcp = _mcp(db)
    neu = _aufruf(mcp, "bewerbung_erstellen",
                  {"title": "Konstrukteur (m/w/d)", "company": "Beispielwerk", "status": "beworben"})
    app = neu.get("id") or neu.get("bewerbung_id") or neu.get("application_id")
    assert app, neu
    vorher = _offene(db, app)
    assert vorher, f"bewerbung_erstellen legt keinen Nachfass an: {neu}"
    erg = _aufruf(mcp, "bewerbung_notiz",
                  {"bewerbung_id": app, "notiz": "Interne Abgrenzung zu einer anderen Stelle derselben Firma"})
    assert _offene(db, app) == vorher
    assert not any(k.startswith("nachfassung_") for k in erg)


# ══ der Dienst: eine Frage, eine Funktion ═══════════════════════════════

def test_1232_der_dienst_nimmt_nur_bekannte_zustaende(db):
    from bewerbungs_assistent.services import nachfass_abgleich
    app = _bewerbung(db)
    _nachfassung(db, app)
    with pytest.raises(ValueError):
        nachfass_abgleich.schliessen(db, app, "Test", status="gesendet")
    assert len(_offene(db, app)) == 1


def test_1232_kontakt_gemeldet_setzt_weiter_hinfaellig(db):
    from bewerbungs_assistent.services import nachfass_abgleich
    app = _bewerbung(db)
    fid = _nachfassung(db, app)
    erg = nachfass_abgleich.kontakt_gemeldet(db, app, "Test")
    assert [e["id"] for e in erg] == [fid]
    assert _zeile(db, fid)["status"] == "hinfaellig"


def test_1232_eine_erinnerung_nach_der_nachfrage_bleibt(db):
    """Wer nach der Nachfrage bewusst „in zwei Wochen wieder“ einplant, behält genau diese Erinnerung."""
    from datetime import datetime, timezone
    from bewerbungs_assistent.services import nachfass_abgleich
    app = _bewerbung(db)
    spaeter = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    fid = _nachfassung(db, app)
    db.connect().execute("UPDATE follow_ups SET created_at=? WHERE id=?", (spaeter, fid))
    db.connect().commit()
    assert nachfass_abgleich.nachfrage_gesendet(db, app) == []
    assert _offene(db, app) == [fid]


# ══ Termin: derselbe Name für denselben Zustand ═════════════════════════

def test_1232_ein_verschobener_termin_meldet_hinfaellig_nicht_erledigt(db):
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    fid = _nachfassung(db, app)
    mid = db.add_meeting({
        "application_id": app, "title": "Interview Musterfirma",
        "meeting_date": f"{_tag(10)}T11:00:00", "meeting_type": "interview", "status": "geplant"})
    # der Termin ist angelegt (das hat die Erinnerung schon geschlossen) — eine neue Erinnerung kommt hinzu
    fid2 = _nachfassung(db, app)
    erg = termin_folgen.aendern(db, mid, {"meeting_date": f"{_tag(17)}T11:00:00"})
    assert erg.get("nachfassung_hinfaellig"), erg
    assert "nachfassung_erledigt" not in erg
    assert _zeile(db, fid2)["status"] == "hinfaellig"
    assert fid


# ══ was Claude liest ═══════════════════════════════════════════════════

def test_1232_das_werkzeugschema_nennt_art_und_die_vorgabe(db):
    mcp = _mcp(db)

    async def _hole():
        return await mcp.get_tool("bewerbung_notiz")
    tool = asyncio.run(_hole())
    eigenschaften = tool.parameters["properties"]
    assert "art" in eigenschaften
    assert eigenschaften["art"].get("default") == "intern"
    text = eigenschaften["art"].get("description", "")
    assert "kontakt" in text and "nachfrage" in text and "intern" in text
    assert "art" not in tool.parameters.get("required", [])
    beschreibung = tool.description
    assert "intern" in beschreibung and "kontakt" in beschreibung and "Nachfass" in beschreibung


def test_1232_die_anleitungen_sagen_wann_kontakt_gilt():
    from bewerbungs_assistent import prompts
    from bewerbungs_assistent.services.document_handlers import KNOWN_TYPES
    quelle = Path(prompts.__file__).read_text(encoding="utf-8")
    assert 'art="kontakt"' in quelle                      # die Mail des Arbeitgebers ist Kontakt
    for typ in ("projekt_update", "gespraechs_feedback", "vermittler_korrespondenz"):
        assert "art='kontakt'" in KNOWN_TYPES[typ]["claude_action"], typ
    # eine Notiz zu einem eigenen Arbeitsschritt ist keine
    assert "interview_bestaetigung" in KNOWN_TYPES
    assert "art='kontakt'" not in KNOWN_TYPES["interview_bestaetigung"]["claude_action"]
