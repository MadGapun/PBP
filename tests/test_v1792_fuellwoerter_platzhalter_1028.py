"""Tests fuer #1028: Fuellwoerter und Firmen-Platzhalter in der Automatik.

Befund 1: `_TITLE_STOPS` fuehrte "fuer" in der Umschrift, `_domain_tokens`
behaelt aber Umlaute. Ein echter Titel enthaelt "für" — der Eintrag griff
nie. Dazu fehlten "als", "zum" und Ziffern: aus "Sachbearbeitung (m/w/d)
für die Buchhaltung als Quereinsteiger zum 01.10." blieben `für`, `als`,
`zum`, `01`, `10` als "Fachgebiet" stehen, und elf passende Stellen
wurden als `falsches_fachgebiet` aussortiert (gemeinsam: für).

Befund 2: "Nicht angegeben" und "Unbekannt" sind Platzhalter der
Adapter, keine Arbeitgeber. `normalize_company` machte daraus einen
nicht-leeren Namen — alle Stellen ohne Firmenangabe galten quer ueber
alle Quellen als DIESELBE Firma, in Stufe 1 (aussortieren) und in
Stufe 2 (still ignorieren, ohne Spur).
"""
import asyncio
import importlib
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import stellen_automatik as sa  # noqa: E402
from bewerbungs_assistent.services import wiedergaenger as wg  # noqa: E402


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database()
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _stelle(db, kennung, titel, firma, grund=None, note=None, **extra):
    job = {
        "hash": kennung, "title": titel, "company": firma,
        "url": f"https://example.com/1028/{kennung}",
        "source": "manuell", "_manual_entry": True,
        "description": "Beschreibungstext. " * 20, "score": 5,
    }
    job.update(extra)
    db.save_jobs([job])
    voll = db.resolve_job_hash(kennung)
    if grund:
        db.dismiss_job(voll, grund)
    if note:
        db.connect().execute("UPDATE jobs SET dismiss_note=? WHERE hash=?",
                             (note, voll))
        db.connect().commit()
    return voll


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(_run())


# ------------------------------------------------------------ Befund 1


def test_ak1_fuellwoerter_und_ziffern_sind_kein_fachgebiet():
    """AK 1, woertlich der Titel aus dem Bericht."""
    t = wg._domain_tokens(
        "Sachbearbeitung (m/w/d) für die Buchhaltung als Quereinsteiger "
        "zum 01.10.")
    for fuellwort in ("für", "als", "zum", "01", "10"):
        assert fuellwort not in t, (fuellwort, t)
    assert "buchhaltung" in t


@pytest.mark.parametrize("wort", [
    "für", "fuer", "als", "zum", "zur", "den", "dem", "des", "auf",
    "oder", "am", "vom", "über", "ueber", "nach", "bis",
])
def test_praepositionen_und_artikel_zaehlen_nicht(wort):
    assert wort not in wg._domain_tokens(f"Elektroniker {wort} Betriebstechnik")


def test_umschrift_und_umlaut_sind_dieselbe_stoppwortliste():
    """Die Liste darf nicht wieder an der Schreibweise haengen."""
    assert (wg._domain_tokens("Referent für Controlling")
            == wg._domain_tokens("Referent fuer Controlling"))


def test_ziffern_im_wort_bleiben_ein_fachsignal():
    """Nur REINE Ziffern fallen weg — "s4hana", "sap4" tragen Fach."""
    t = wg._domain_tokens("SAP S4HANA Berater 2026")
    assert "s4hana" in t and "2026" not in t


@pytest.mark.parametrize("neutral", ["sachbearbeitung", "mitarbeitende",
                                     "assistenz"])
def test_geschlechtsneutrale_rollenformen_sind_rollen(neutral):
    """AK-Vorschlag 3: "Sachbearbeitung" wie "Sachbearbeiter"."""
    assert neutral not in wg._domain_tokens(f"{neutral.title()} Buchhaltung")


def test_ak2_praeposition_traegt_kein_titel_muster(db):
    """AK 2: drei fremde Berufe "für …", danach Sachbearbeitung."""
    _stelle(db, "e1", "Elektroniker für Betriebstechnik", "Werk Nord GmbH",
            "falsches_fachgebiet")
    _stelle(db, "e2", "Erzieher für Ganztagsangebote", "Kita Sued e.V.",
            "falsches_fachgebiet")
    _stelle(db, "e3", "MTR für die Strahlentherapie", "Klinik West GmbH",
            "falsches_fachgebiet")
    neu = {"hash": "neu1", "company": "Stadtwerke Ost GmbH",
           "title": "Sachbearbeitung (m/w/d) für die Buchhaltung"}
    assert sa.find_titel_muster(db, neu["title"]) is None
    assert sa.entscheide(db, neu)["aktion"] == "anlegen"


def test_ak2_gegenprobe_ein_echtes_fachwort_traegt_weiter(db):
    """Die Haertung darf den Gruendungsfall aus #941 nicht mitnehmen."""
    for i, firma in enumerate(("Alpha GmbH", "Beta GmbH", "Gamma GmbH")):
        _stelle(db, f"c{i}", f"CRM Berater für Vertrieb {i}", firma,
                "falsches_fachgebiet")
    m = sa.find_titel_muster(db, "CRM Consultant für Kundenservice")
    assert m and m["tokens"] == ["crm"]


# ------------------------------------------------------------ Befund 2


@pytest.mark.parametrize("platzhalter", [
    "Nicht angegeben", "Unbekannt", "unknown", "k.A.", "n/a",
    "Keine Angabe", "  NICHT ANGEGEBEN ",
])
def test_firmen_platzhalter_sind_keine_firma(platzhalter):
    assert wg.normalize_company(platzhalter) == ""
    assert wg.ist_firmen_platzhalter(platzhalter)


def test_ein_echter_name_mit_platzhalterwort_bleibt_eine_firma():
    """Gegenrichtung (#966): nur der GANZE Name ist ein Platzhalter."""
    assert wg.normalize_company("Unbekannt Software GmbH") == "unbekannt software"
    assert not wg.ist_firmen_platzhalter("Unbekannt Software GmbH")


@pytest.mark.parametrize("a,b", [("Nicht angegeben", "Nicht angegeben"),
                                 ("Unbekannt", "Unbekannt"),
                                 ("Nicht angegeben", "Unbekannt")])
def test_ak3_stufe1_platzhalter_sind_nicht_dieselbe_firma(db, a, b):
    _stelle(db, "p1", "Kaufmann für Büromanagement", a, "zu_weit_entfernt")
    _stelle(db, "p2", "Kauffrau für Büromanagement", a, "zu_weit_entfernt")
    assert wg.find_wiedergaenger_pattern(
        db, b, "Ausbildung Kaufmann für Büromanagement",
        schwellwert=sa.AUTOMATIK_SCHWELLE) is None


def test_ak3_stufe2_platzhalter_wird_nicht_still_ignoriert(db):
    """Stufe 2 speichert eine ignorierte Stelle GAR NICHT."""
    _stelle(db, "q1", "Buchhaltung Kreditoren", "Nicht angegeben",
            "falsches_fachgebiet")
    neu = {"hash": "q2", "company": "Unbekannt",
           "title": "Buchhaltung Kreditoren"}
    assert sa._domain_schluessel("Nicht angegeben", neu["title"]) is None
    assert sa.entscheide(db, neu)["aktion"] != "ignorieren"
    ergebnis = sa.anwenden(db, [dict(neu)])
    assert ergebnis["zaehler"]["ignoriert"] == 0


def test_ak3_gegenprobe_echte_gleiche_firma_bleibt_stufe2(db):
    _stelle(db, "r1", "Buchhaltung Kreditoren", "Muster Handel GmbH",
            "falsches_fachgebiet")
    neu = {"hash": "r2", "company": "Muster Handel GmbH",
           "title": "Buchhaltung Kreditoren"}
    assert sa.entscheide(db, neu)["aktion"] == "ignorieren"


def test_ak4_issue_text_pruefen_meldet_platzhalter_nicht(db):
    from bewerbungs_assistent.services import pii_bestand

    _stelle(db, "s1", "Buchhaltung", "Nicht angegeben")
    _stelle(db, "s2", "Buchhaltung Kreditoren", "Unbekannt")
    bericht = pii_bestand.pruefe_text(
        db, "Firma steht als Nicht angegeben bzw. Unbekannt im Bestand.")
    namen = {t.get("name", "").lower() for t in bericht.get("treffer", [])}
    assert "nicht angegeben" not in namen and "unbekannt" not in namen
    assert bericht["sauber"]


# --------------------------------------------------- AK 5: Bestandskorrektur


def test_ak5_bestandskorrektur_findet_fuellwort_und_platzhalter(db):
    import logging

    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all

    mcp = FastMCP("t1028")
    register_all(mcp, db, logging.getLogger("t1028"))
    fuellwort = _stelle(
        db, "b1", "Mitarbeitende für die Buchhaltung", "Stadt Ost",
        "falsches_fachgebiet",
        note="Wiedergaenger nach Fachgebiet: 15x mit Grund "
             "'falsches_fachgebiet' aussortiert (gemeinsam: für).")
    platz = _stelle(
        db, "b2", "Ausbildung Kaufmann für Büromanagement", "Nicht angegeben",
        "zu_weit_entfernt",
        note="Wiedergaenger: dieselbe Firma wurde bereits 4x mit Grund "
             "'zu_weit_entfernt' aussortiert.")
    echt = _stelle(
        db, "b3", "CRM Consultant", "Gamma GmbH", "falsches_fachgebiet",
        note="Wiedergaenger nach Fachgebiet: 3x mit Grund "
             "'falsches_fachgebiet' aussortiert (gemeinsam: crm).")

    vorschau = _call(mcp, "automatik_uebertragungen_pruefen", {})
    befunde = {e["titel"]: e["befund"] for e in vorschau["stichprobe"]}
    assert befunde.get("Mitarbeitende für die Buchhaltung") == "nur_fuellwoerter"
    assert (befunde.get("Ausbildung Kaufmann für Büromanagement")
            == "firmen_platzhalter")
    assert "CRM Consultant" not in befunde
    assert vorschau["status"] == "vorschau"

    _call(mcp, "automatik_uebertragungen_pruefen", {"dry_run": False})
    aktiv = {r[0]: r[1] for r in db.connect().execute(
        "SELECT hash, is_active FROM jobs")}
    assert aktiv[fuellwort] == 1 and aktiv[platz] == 1
    assert aktiv[echt] == 0


def test_ak5_vier_gezeigte_fuellwoerter_holen_nichts_zurueck(db):
    """Isolierender Fall fuer die Vier-Token-Grenze (Gegenprobe: ohne
    ihn machte das Ausbauen der Grenze nichts rot).

    Die Notiz zeigt hoechstens vier gemeinsame Tokens. Stehen dort genau
    vier, kann ein fuenftes, echtes Fachwort dahinter gestanden haben —
    dann ist "nur Fuellwoerter" nicht belegt, und die Stelle bleibt
    aussortiert.
    """
    import logging

    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all

    mcp = FastMCP("t1028b")
    register_all(mcp, db, logging.getLogger("t1028b"))
    voll = _stelle(
        db, "v1", "Sachbearbeitung für Kreditoren als Quereinsteiger",
        "Stadt Nord", "falsches_fachgebiet",
        note="Wiedergaenger nach Fachgebiet: 3x mit Grund "
             "'falsches_fachgebiet' aussortiert (gemeinsam: 01, als, "
             "für, zum).")
    vorschau = _call(mcp, "automatik_uebertragungen_pruefen", {})
    assert not any(e["titel"].startswith("Sachbearbeitung für Kreditoren")
                   for e in vorschau["stichprobe"])
    _call(mcp, "automatik_uebertragungen_pruefen", {"dry_run": False})
    aktiv = db.connect().execute(
        "SELECT is_active FROM jobs WHERE hash=?", (voll,)).fetchone()[0]
    assert aktiv == 0
