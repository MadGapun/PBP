"""#1106: Dashboard-Abfragen auf Spalten, die es nicht gibt, und ohne Profilfilter.

Der Kern-Guard schickt jedes SQL-Literal aus dem Code als EXPLAIN gegen
ein frisch angelegtes Schema. Grenzen (gehoeren hierher, damit niemand
mehr Sicherheit annimmt als da ist):

* f-Strings und zusammengesetzte Abfragen erreicht er nicht — nur
  Literale, die mit SELECT/UPDATE/INSERT/DELETE/WITH beginnen.
* Tabellen, die erst bei Bedarf entstehen, legt er vorher mit ihren
  eigenen Anlegern an. Ausgenommen sind nur die Tabellen in
  `NUR_ALTBESTAND` — jede mit Grund. Bis v1.7.140 zaehlte "no such
  table" gar nicht, und drei Abfragen auf eine Tabelle `meetings`, die
  es nie gab, lieferten still 0 (Aufwand-Tipp, Gespraechs-Check).
* Er prueft das Schema der Linie, auf der er laeuft (v48 oder v52).
"""
from __future__ import annotations

import ast
import os
import re
import sqlite3
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "bewerbungs_assistent"
START = re.compile(r"^\s*(SELECT|UPDATE|INSERT|DELETE|WITH)\b", re.I)


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


#: Tabellen, die nur in gewachsenen Bestaenden vorkommen. Wer sie liest,
#: prueft vorher, ob es sie gibt (sqlite_master oder try mit Kommentar).
NUR_ALTBESTAND = {
    "documents_new": "Zwischentabelle einer Migration, entsteht direkt davor",
    "learned_insights": "Doppelanlage aus F28 (#799), wird uebernommen, wenn es sie gibt",
    "profile_settings": "Altbestand einer profilbezogenen Migration (Safety-Net)",
}


def _bei_bedarf_anlegen(db):
    """Die Tabellen, die ihr Dienst erst beim ersten Schreiben anlegt."""
    from bewerbungs_assistent.services import (
        pii_bestand, stellen_grabstein, stellen_quellen)
    conn = db.connect()
    stellen_quellen.tabelle_anlegen(conn)
    stellen_grabstein.tabelle_anlegen(conn)
    pii_bestand._tabelle_anlegen(db)


def _sql_literale():
    for p in sorted(SRC.rglob("*.py")):
        baum = ast.parse(p.read_text(encoding="utf-8-sig"))
        # Bruchstuecke eines f-Strings sind keine Abfrage fuer sich.
        teile = {id(v) for j in ast.walk(baum) if isinstance(j, ast.JoinedStr)
                 for v in j.values}
        for n in ast.walk(baum):
            if id(n) in teile:
                continue
            if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                    and START.match(n.value):
                yield p.relative_to(REPO), n.lineno, n.value


# ── AK 4: der Guard ─────────────────────────────────────────────────

def test_jede_sql_abfrage_kennt_ihre_spalten(db):
    _bei_bedarf_anlegen(db)
    con = db.connect()
    funde, geprueft = [], 0
    for datei, zeile, sql in _sql_literale():
        try:
            con.execute("EXPLAIN " + sql)
            geprueft += 1
        except sqlite3.OperationalError as exc:
            text = str(exc)
            if "no such column" in text:
                funde.append(f"{datei}:{zeile}: {exc}")
            elif "no such table" in text:
                tabelle = text.split(":", 1)[1].strip()
                if tabelle not in NUR_ALTBESTAND:
                    funde.append(f"{datei}:{zeile}: {exc}")
        except Exception:
            geprueft += 1  # Bindungen fehlen — vorbereitet ist sie
    assert geprueft > 500, f"Guard sieht zu wenig ({geprueft})"
    assert not funde, "\n".join(funde)


@pytest.mark.parametrize("sql", [
    "SELECT event_at FROM application_events WHERE event_at >= ?",
    "SELECT COUNT(*) AS n FROM application_events WHERE event_at >= ? AND event_type='status_change'",
    "SELECT id FROM application_emails WHERE LOWER(plain_body) LIKE ?",
    "SELECT COUNT(*) AS n FROM meetings WHERE application_id=?",
    "SELECT company, position FROM applications WHERE id=?",
])
def test_guard_erkennt_die_urspruenglichen_abfragen(db, sql):
    with pytest.raises(sqlite3.OperationalError, match="no such (column|table)"):
        db.connect().execute("EXPLAIN " + sql)


# ── Aufbau: zwei Profile ─────────────────────────────────────────────

def _zwei_profile(db):
    fremd = db.create_profile("Fremdes Profil")
    db.switch_profile(fremd)
    a_f = db.add_application({"title": "Fremde Stelle", "company": "Musterbetrieb GmbH",
                              "status": "beworben"})
    db.add_email({"application_id": a_f, "filename": "f.eml", "subject": "Fremdbetreff",
                  "sender": "fremd@example.com", "body_text": "Suchwort fremdlich"})
    db.add_meeting({"application_id": a_f, "title": "Fremdtermin",
                    "meeting_date": "2099-01-01T10:00"})
    eigen = db.create_profile("Eigenes Profil")
    db.switch_profile(eigen)
    a_e = db.add_application({"title": "Eigene Stelle", "company": "Musterbetrieb GmbH",
                              "status": "beworben"})
    db.add_email({"application_id": a_e, "filename": "e.eml", "subject": "Einladung",
                  "sender": "hr@example.com", "body_text": "Wir freuen uns auf das Kennenlernen"})
    return a_e, a_f


def _client(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    dash._db = db
    return TestClient(dash.app)


# ── AK 1 ────────────────────────────────────────────────────────────

def test_heatmap_zaehlt_statusaenderungen_nur_im_eigenen_profil(db):
    _zwei_profile(db)
    daten = _client(db).get("/api/stats/heatmap").json()
    events = sum(t["breakdown"]["events"] for t in daten["data"])
    meetings = sum(t["breakdown"]["meetings"] for t in daten["data"])
    assert events == 1, daten
    assert meetings == 0, "Termin des anderen Profils gezaehlt"
    assert daten["nicht_lesbar"] == []


def test_rueckschau_zaehlt_status_und_nur_eigene_mails(db):
    a_e, _ = _zwei_profile(db)
    # Eine Timeline-Zeile ohne Bewerbungsstatus ist keine Statusaenderung.
    from datetime import datetime, timezone
    db.connect().execute(
        "INSERT INTO application_events (application_id, status, event_date, notes) "
        "VALUES (?, 'dokument', ?, 'Dokument verknuepft')",
        (a_e, datetime.now(timezone.utc).isoformat()))
    db.connect().commit()
    daten = _client(db).get("/api/recap").json()
    assert daten["status_changes"] == 1, daten
    assert daten["new_emails"] == 1, "Mail des anderen Profils gezaehlt"
    assert daten["upcoming_meetings"] == 0
    assert daten["nicht_lesbar"] == []


def test_rueckschau_zaehlt_termin_der_naechsten_tage(db):
    from datetime import datetime, timedelta
    a_e, _ = _zwei_profile(db)
    morgen = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT10:00")
    db.add_meeting({"application_id": a_e, "title": "Gespräch", "meeting_date": morgen})
    assert _client(db).get("/api/recap").json()["upcoming_meetings"] == 1


# ── AK 2 und 3: Suche ────────────────────────────────────────────────

def _gruppe(daten, kind):
    return next((g for g in daten["groups"] if g["kind"] == kind), {"items": []})


def test_suche_findet_mail_ueber_ihren_text(db):
    _zwei_profile(db)
    daten = _client(db).get("/api/search", params={"q": "kennenlernen"}).json()
    assert [i["title"] for i in _gruppe(daten, "email")["items"]] == ["Einladung"]
    assert "hr@example.com" in _gruppe(daten, "email")["items"][0]["subtitle"]
    assert daten["nicht_lesbar"] == []


def test_suche_zeigt_nichts_aus_dem_anderen_profil(db):
    _zwei_profile(db)
    tc = _client(db)
    assert _gruppe(tc.get("/api/search", params={"q": "fremdlich"}).json(), "email")["items"] == []
    assert _gruppe(tc.get("/api/search", params={"q": "fremdtermin"}).json(), "meeting")["items"] == []


# ── AK 3: Werkzeuge nur im aktiven Profil ───────────────────────────

def test_gehaelter_neu_auswerten_nur_aktives_profil(db):
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    text = "Wir bieten ein Jahresgehalt von 55.000 bis 65.000 EUR brutto. " * 3
    fremd = db.create_profile("Fremd")
    db.switch_profile(fremd)
    db.save_jobs([{"hash": "gf1106", "title": "Fremd", "company": "Musterbetrieb GmbH",
                   "url": "https://example.com/gf", "source": "manuell", "description": text}])
    eigen = db.create_profile("Eigen")
    db.switch_profile(eigen)
    db.save_jobs([{"hash": "ge1106", "title": "Eigen", "company": "Musterbetrieb GmbH",
                   "url": "https://example.com/ge", "source": "manuell", "description": text}])
    mcp = FastMCP("PBP #1106")
    register_all(mcp, db, logging.getLogger("test.1106"))

    async def lauf():
        t = await mcp.get_tool("gehaelter_neu_auswerten")
        return (await t.run({"dry_run": False})).structured_content
    bericht = asyncio.run(lauf())
    # Die fremde Stelle darf auch im Bericht nicht auftauchen — vorher
    # zaehlte sie als "von Hand gesetzt, uebersprungen".
    assert bericht["geprueft"] == 1, bericht
    assert bericht["von_hand_gesetzt_uebersprungen"] == 0, bericht
    fremd_zeile = db.connect().execute(
        "SELECT salary_min FROM jobs WHERE hash LIKE '%gf1106'").fetchone()
    eigen_zeile = db.connect().execute(
        "SELECT salary_min FROM jobs WHERE hash LIKE '%ge1106'").fetchone()
    assert eigen_zeile[0] == 55000
    assert fremd_zeile[0] is None, "Stelle des anderen Profils angefasst"


def test_dokument_prompt_kennt_die_stelle(db):
    import bewerbungs_assistent.dashboard as dash
    db.save_profile({"name": "Dok"})
    app = db.add_application({"title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                              "status": "beworben"})
    dash._db = db
    erg = dash._enrich_document_for_prompt({"doc_type": "anschreiben",
                                            "linked_application_id": app})
    assert erg["app_title"] == "Sachbearbeitung"
    assert erg["app_company"] == "Musterbetrieb GmbH"


# ── AK 5: kein stummes except in den drei Endpunkten ────────────────

@pytest.mark.parametrize("funktion", ["api_stats_heatmap", "api_global_search", "api_recap"])
def test_kein_stummes_except(funktion):
    baum = ast.parse((SRC / "dashboard.py").read_text(encoding="utf-8-sig"))
    namen = [f.name for f in ast.walk(baum) if isinstance(f, ast.AsyncFunctionDef)]
    f = next((f for f in ast.walk(baum)
              if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.name == funktion), None)
    assert f is not None, f"{funktion} nicht gefunden: {[n for n in namen if 'heat' in n]}"
    for h in ast.walk(f):
        if isinstance(h, ast.ExceptHandler):
            assert not (len(h.body) == 1 and isinstance(h.body[0], ast.Pass)), \
                f"{funktion}: stummes except in Zeile {h.lineno}"


# ── Nachtrag: `meetings` gab es nie (Tabelle heisst application_meetings) ──

def test_aufwand_tipp_zaehlt_die_termine(db):
    """Der Tipp "Aufwand-Tracking" erschien nie: die Abfrage lief auf
    `meetings` und scheiterte still."""
    from bewerbungs_assistent.services import onboarding_hints as oh
    db.switch_profile(db.create_profile("Termine"))
    app = db.add_application({"title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                              "status": "interview"})
    for tag in range(1, 6):
        db.add_meeting({"application_id": app, "title": f"Gespraech {tag}",
                        "meeting_date": f"2026-10-0{tag} 10:00"})
    assert oh._condition_keine_aufwandskosten_aber_termine(db) is True
    db.connect().execute("UPDATE application_meetings SET vorbereitungszeit_min=30")
    db.connect().commit()
    assert oh._condition_keine_aufwandskosten_aber_termine(db) is False


def test_gespraechs_check_kennt_eingetragene_termine(db):
    """Eine Bewerbung mit Gespraech in den Notizen UND eingetragenem Termin
    ist kein Fund — vorher war die Terminzahl immer 0."""
    from bewerbungs_assistent.services import statistik_erweitert
    db.switch_profile(db.create_profile("Notizen"))
    app = db.add_application({
        "title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
        "status": "beworben",
        "notes": "Telefonat mit der Fachabteilung am 12.10.2026, lief gut und freundlich."})
    assert [t["id"] for t in statistik_erweitert.notizen_gespraeche_check(db)] == [app[:8]]
    db.add_meeting({"application_id": app, "title": "Telefonat",
                    "meeting_date": "2026-10-12 10:00"})
    assert statistik_erweitert.notizen_gespraeche_check(db) == []
