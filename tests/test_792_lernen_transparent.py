"""#792: was fliesst ins Lernen ein, was ergab jeder Lauf, und warum nichts.

Vorher lief der Lern-Task taeglich, und von aussen war nicht zu
unterscheiden, ob er nichts fand, nichts speicherte oder etwas anderes
tat. Jetzt: Quellen-Uebersicht (mit ausdruecklichem "nein"), ein
Protokolleintrag je Lauf, ein Grund bei leerem Lauf und ein Export.

Alle Firmen sind Platzhalter.
"""
from __future__ import annotations

import ast
import asyncio
import csv
import importlib
import io
import json
import logging
import os
import re
import sys
import zipfile
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


SRC = _repo() / "src" / "bewerbungs_assistent"
sys.path.insert(0, str(_repo() / "src"))


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database
    importlib.reload(database)
    d = database.Database(db_path=tmp_path / "lernen.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.switch_profile(d.create_profile("Erstes"))
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _aussortieren(db, n, grund="zu_weit_entfernt", firma="Musterbetrieb GmbH"):
    for i in range(n):
        h = f"l792{grund[:4]}{i}"
        db.save_jobs([{"hash": h, "title": f"Sachbearbeitung {i}", "company": firma,
                       "url": f"https://jobs.example.org/{h}", "score": 3}])
        db.dismiss_job(db.resolve_job_hash(h), grund)


def _mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent import tools
    mcp = FastMCP("t")
    tools.register_all(mcp, db, logging.getLogger("t"))
    return mcp


def _call(mcp, name, args):
    async def lauf():
        t = await mcp.get_tool(name)
        res = await t.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(lauf())


# ================================================================ Quellen


def test_uebersicht_zaehlt_was_einfliesst_und_nennt_das_nein(db):
    from bewerbungs_assistent.services import lernquellen
    _aussortieren(db, 3)
    db.add_application({"title": "Einkauf", "company": "Musterfirma", "status": "beworben",
                        "applied_at": "2026-09-01"})
    zeilen = {q["key"]: q for q in lernquellen.uebersicht(db)}
    assert zeilen["aussortierungen"]["anzahl"] == 3
    assert zeilen["bewerbungen"]["anzahl"] == 1
    assert zeilen["bewerbungen"]["von"] == "2026-09-01"
    nein = [q for q in zeilen.values() if not q["fliesst_ein"]]
    assert {"dokumente", "profil", "kontakte"} <= {q["key"] for q in nein}
    assert all("anzahl" not in q for q in nein), "ein 'nein' ohne Zahl"


def test_uebersicht_nur_aktives_profil(db):
    from bewerbungs_assistent.services import lernquellen
    _aussortieren(db, 2)
    db.switch_profile(db.create_profile("Zweites"))
    zeilen = {q["key"]: q for q in lernquellen.uebersicht(db)}
    assert zeilen["aussortierungen"]["anzahl"] == 0


def _gelesene_tabellen(pfad: Path, funktionen: set | None = None) -> set:
    baum = ast.parse(pfad.read_text(encoding="utf-8-sig"))
    tabellen = set()
    for k in ast.walk(baum):
        if isinstance(k, ast.FunctionDef) and funktionen is not None and k.name not in funktionen:
            continue
        if isinstance(k, ast.FunctionDef) or funktionen is None:
            for c in ast.walk(k):
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    tabellen |= set(re.findall(r"\bFROM\s+([a-z_]+)", c.value))
    return tabellen


def test_jede_gelesene_tabelle_steht_als_einfliessend_da():
    """Die Liste beschreibt die Eingaben der Regeln — ein Guard haelt sie
    gegen die Tabellen, die die Regeln tatsaechlich lesen."""
    from bewerbungs_assistent.services.lernquellen import QUELLEN
    ja = {t for q in QUELLEN if q["fliesst_ein"] for t in q["tabellen"]}
    nein = {t for q in QUELLEN if not q["fliesst_ein"] for t in q["tabellen"]}
    gelesen = _gelesene_tabellen(SRC / "services" / "lerninsights.py",
                                 {"_regel_aussortier_muster", "_regel_score_realitaet"})
    gelesen |= _gelesene_tabellen(SRC / "services" / "ablehnungsgruende.py", {"gruende_zaehlen"})
    gelesen |= _gelesene_tabellen(SRC / "services" / "statistik_erweitert.py", {"_lade_events"})
    gelesen.add("applications")  # kanal/zeitmuster lesen ueber db.get_applications
    gelesen |= _gelesene_tabellen(SRC / "dashboard.py", {"_aggregate_user_activity"})
    assert gelesen <= ja, f"liest, steht aber nicht als einfliessend: {gelesen - ja}"
    assert not (gelesen & nein), f"als 'nein' gefuehrt, wird aber gelesen: {gelesen & nein}"


# ============================================================ Protokoll


def test_manueller_lauf_schreibt_einen_eintrag_mit_grund(db):
    _aussortieren(db, 2)
    erg = _call(_mcp(db), "erkenntnisse_ableiten", {"dry_run": False})
    assert erg.get("lauf_id")
    prot = _call(_mcp(db), "lernprotokoll_anzeigen", {"limit": 5})
    lauf = prot["laeufe"][0]
    assert lauf["ausloeser"] == "manuell" and lauf["neu"] == 0
    assert any("mindestens 5 aussortierte" in w for w in lauf["warum_nichts_neues"])
    assert any(q["key"] == "aussortierungen" and q["anzahl"] == 2 for q in lauf["quellen"])


def test_vorschau_steht_nicht_im_protokoll(db):
    _call(_mcp(db), "erkenntnisse_ableiten", {"dry_run": True})
    assert _call(_mcp(db), "lernprotokoll_anzeigen", {})["laeufe"] == []


def test_lauf_mit_ergebnis_zeigt_die_kandidaten(db):
    _aussortieren(db, 6)
    _call(_mcp(db), "erkenntnisse_ableiten", {"dry_run": False})
    lauf = _call(_mcp(db), "lernprotokoll_anzeigen", {})["laeufe"][0]
    assert lauf["neu"] >= 1
    k = lauf["kandidaten"][0]
    assert k["aussage"] and k["belegt_durch_n"] == 6 and 0 < k["konfidenz"] < 1
    # ein zweiter Lauf findet dieselbe Aussage: bekannt, nicht neu
    _call(_mcp(db), "erkenntnisse_ableiten", {"dry_run": False})
    zweiter = _call(_mcp(db), "lernprotokoll_anzeigen", {})["laeufe"][0]
    assert zweiter["neu"] == 0 and zweiter["aufgefrischt"] >= 1
    assert any("schon bekannt" in w for w in zweiter["warum_nichts_neues"])
    # die Regel, die etwas fand, steht nicht als "fand nichts" da
    assert not any("Häufige Ablehnungsgründe“ fand nichts" in w
                   for w in zweiter["warum_nichts_neues"])


def test_lernen_aus_speichert_nichts_auch_von_hand(db):
    """#1107 galt nur fuer die Automatik; der Weg ueber Claude speicherte weiter."""
    _aussortieren(db, 6)
    db.set_profile_setting("learning_enabled", False)
    erg = _call(_mcp(db), "erkenntnisse_ableiten", {"dry_run": False})
    assert erg["status"] == "lernen_aus"
    n = db.connect().execute("SELECT COUNT(*) FROM learning_insights").fetchone()[0]
    assert n == 0
    lauf = _call(_mcp(db), "lernprotokoll_anzeigen", {})["laeufe"][0]
    assert lauf["status"] == "lernen_aus"
    assert lauf["warum_nichts_neues"] == ["Das Lernen ist unter Datenschutz ausgeschaltet."]


def test_automatik_schreibt_den_eintrag_und_die_ki(db, monkeypatch):
    import threading
    import time
    import bewerbungs_assistent.dashboard as dash
    from bewerbungs_assistent.services import automatik_scheduler as sch
    monkeypatch.setattr(dash, "_run_analyze_user_patterns", lambda *a, **k: {
        "skipped": True, "reason": "Lokale AI nicht aktiv", "insights": 0})
    assert sch.run_lernen_now(db)["status"] == "gestartet"
    for _ in range(100):
        if not any(t.name == "automatik-lernen" for t in threading.enumerate()):
            break
        time.sleep(0.05)
    lauf = _call(_mcp(db), "lernprotokoll_anzeigen", {})["laeufe"][0]
    assert lauf["ausloeser"] == "automatik"
    assert lauf["lokale_ki"]["uebersprungen"] is True
    assert any("Lokale AI nicht aktiv" in w for w in lauf["warum_nichts_neues"])


def test_automatik_mit_lernen_aus_steht_im_protokoll(db):
    from bewerbungs_assistent.services import automatik_scheduler as sch
    db.set_profile_setting("learning_enabled", False)
    assert sch.run_lernen_now(db)["status"] == "lernen_aus"
    lauf = _call(_mcp(db), "lernprotokoll_anzeigen", {})["laeufe"][0]
    assert lauf["status"] == "lernen_aus" and lauf["ausloeser"] == "automatik"


def test_protokoll_je_profil(db):
    _call(_mcp(db), "erkenntnisse_ableiten", {"dry_run": False})
    db.switch_profile(db.create_profile("Zweites"))
    assert _call(_mcp(db), "lernprotokoll_anzeigen", {})["laeufe"] == []


def test_protokoll_waechst_nicht_ohne_grenze(db, monkeypatch):
    from bewerbungs_assistent.services import lernprotokoll
    monkeypatch.setattr(lernprotokoll, "MAX_EINTRAEGE", 3)
    for _ in range(5):
        lernprotokoll.regeln_lauf(db, "manuell")
    n = db.connect().execute("SELECT COUNT(*) FROM learning_runs").fetchone()[0]
    assert n == 3


def test_jede_regel_nennt_ihre_mindestdaten():
    from bewerbungs_assistent.services.lerninsights import MINDESTENS, _REGELN
    assert {name for name, _ in _REGELN} == set(MINDESTENS)
    quelle = (SRC / "services" / "lerninsights.py").read_text(encoding="utf-8")
    # die Zahl im Text steht auch in der Regel
    assert "if n < 5:" in quelle and "mindestens 5 aussortierte" in MINDESTENS["aussortier_muster"][1]
    assert 'r["anzahl"] < 5' in quelle and "mindestens 5 Bewerbungen" in MINDESTENS["reaktionszeit"][1]
    assert "len(pro_monat) < 3" in quelle and "mindestens 3" in MINDESTENS["zeitmuster"][1]


# ================================================================ Export


def test_export_enthaelt_genau_die_lerndaten(db, tmp_path):
    from bewerbungs_assistent.services import lernprotokoll
    _aussortieren(db, 6)
    _aussortieren(db, 1, grund="bewerbung_erstellt", firma="Andere Firma AG")
    db.add_application({"title": "Einkauf", "company": "Musterfirma", "status": "beworben"})
    _call(_mcp(db), "erkenntnisse_ableiten", {"dry_run": False})
    erg = lernprotokoll.export_erstellen(db, ziel=tmp_path / "export")
    with zipfile.ZipFile(erg["datei"]) as z:
        namen = z.namelist()
        ordner = namen[0].split("/")[0]
        aussortiert = list(csv.DictReader(io.StringIO(
            z.read(f"{ordner}/quellen/aussortierungen.csv").decode("utf-8-sig")), delimiter=";"))
        erkenntnisse = json.loads(z.read(f"{ordner}/erkenntnisse.json"))
        uebersicht = z.read(f"{ordner}/uebersicht.md").decode("utf-8")
    assert len(aussortiert) == 6, "bewerbung_erstellt ist kein Lern-Datensatz"
    assert erkenntnisse and erkenntnisse[0]["belegt_durch_n"] == 6
    assert erkenntnisse[0]["evidenz"]["grund"] == "zu_weit_entfernt"
    assert "Firmennamen" in uebersicht and "| nein |" in uebersicht
    assert f"{ordner}/lernlaeufe.csv" in namen
    assert erg["zeilen"]["bewerbungen"] == 1


def test_export_ueberschreibt_keinen_frueheren(db, tmp_path):
    from bewerbungs_assistent.services import lernprotokoll
    a = lernprotokoll.export_erstellen(db, ziel=tmp_path)
    b = lernprotokoll.export_erstellen(db, ziel=tmp_path)
    assert a["datei"] != b["datei"] and Path(a["datei"]).exists()


def test_export_und_transparenz_ueber_das_dashboard(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    vorher = dash._db
    dash._db = db
    try:
        c = TestClient(dash.app)
        t = c.get("/api/lernen/transparenz").json()
        r = c.get("/api/lernen/export")
    finally:
        dash._db = vorher
    assert {q["key"] for q in t["quellen"]} >= {"aussortierungen", "dokumente"}
    assert r.status_code == 200 and r.content[:2] == b"PK"


def test_learning_runs_steht_in_einem_loeschbereich():
    from bewerbungs_assistent.services import loeschbereiche
    quelle = Path(loeschbereiche.__file__).read_text(encoding="utf-8")
    assert '"learning_runs"' in quelle


# ============================================================ Oberflaeche


def test_oberflaeche_zeigt_quellen_laeufe_grund_und_export():
    jsx = (_repo() / "frontend" / "src" / "components" / "LernTransparenz.jsx").read_text(encoding="utf-8")
    assert "/api/lernen/transparenz" in jsx and "/api/lernen/export" in jsx
    assert "warum_nichts_neues" in jsx and "fliesst_ein" in jsx
    assert "Firmennamen" in jsx
    seite = (_repo() / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    assert "<LernTransparenz />" in seite
