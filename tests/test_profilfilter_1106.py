"""#1106-Klasse: Abfragen ohne Profilfilter zeigen Daten anderer Profile.

#1106 fand drei Stellen (Heatmap, Rueckschau, Suche). Ein Durchgang ueber
alle SQL-Literale fand weitere: Stil-Auswertung (zweimal), Datenauskunft,
Score-Verteilung hinter dem Schwellen-Regler, Dubletten-Bericht, Orte-
Abgleich, Notiz-Bericht, Nachfass-Diagnose und die Kurz-ID eines Kontakts.

Der Guard liest jedes SELECT-Literal (kein f-String-Bruchstueck) auf einer
Tabelle mit `profile_id`. Es muss `profile_id` nennen, ueber eine
Kennung eingrenzen (id=?, hash=?, application_id=? ...) oder in
`UEBER_ALLE_PROFILE` stehen — mit Grund. Grenzen: `database.py` (die
Datenschicht hat eigene Tests), f-Strings und Abfragen, deren Profilfilter
in einem spaeter angehaengten Teil steht.

Alle Firmen und Namen sind Platzhalter.
"""
from __future__ import annotations

import ast
import importlib
import os
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


SRC = _repo() / "src" / "bewerbungs_assistent"
sys.path.insert(0, str(_repo() / "src"))

#: (Datei, Anfang der Abfrage) -> Grund
UEBER_ALLE_PROFILE = {
    ("dashboard.py", "SELECT (SELECT COUNT(*) FROM applications) AS a_cnt"):
        "Aenderungs-Marker fuers Nachladen: eine Aenderung irgendwo darf neu laden",
    ("dashboard.py", "SELECT COUNT(*) AS n FROM jobs WHERE (description_snapshot IS NULL"):
        "Wartung: Snapshot-Nachzug ueber den ganzen Bestand (#688), nur ein Log",
    ("services/gruende_schreibweise.py", "SELECT dismiss_reason FROM jobs"):
        "Ablehnungsgruende sind profiluebergreifend (dismiss_reasons ohne profile_id)",
    ("services/gruende_schreibweise.py", "SELECT hash, dismiss_reason FROM jobs"):
        "Umschreiben eines profiluebergreifenden Grundes",
    ("tools/suche.py", "SELECT COUNT(*) FROM jobs WHERE dismiss_reason=?"):
        "Loeschvorschau eines profiluebergreifenden Grundes",
    ("services/karten_heilung.py", "SELECT * FROM jobs WHERE source IN"):
        "Heilung verfaelschter Karten im ganzen Bestand (#1041)",
    ("services/karten_heilung.py", "SELECT hash FROM jobs"):
        "Kennungskollisionen gelten ueber alle Profile (Primaerschluessel)",
    ("services/onboarding_hints.py", "SELECT 1 FROM applications LIMIT 1"):
        "Die Sicherung umfasst die ganze Datenbank (#1098)",
    ("services/onboarding_hints.py", "SELECT 1 FROM jobs LIMIT 1"):
        "Die Sicherung umfasst die ganze Datenbank (#1098)",
    ("services/pii_bestand.py", "SELECT DISTINCT company FROM applications"):
        "PII-Pruefer: jeder reale Name aus JEDEM Profil (#946)",
    ("services/pii_bestand.py", "SELECT DISTINCT company FROM jobs"):
        "PII-Pruefer: jeder reale Name aus JEDEM Profil (#946)",
    ("services/pii_bestand.py", "SELECT DISTINCT company FROM contacts"):
        "PII-Pruefer: jeder reale Name aus JEDEM Profil (#946)",
    ("services/pii_bestand.py", "SELECT DISTINCT full_name FROM contacts"):
        "PII-Pruefer: jeder reale Name aus JEDEM Profil (#946)",
    ("services/pii_bestand.py", "SELECT DISTINCT ansprechpartner FROM applications"):
        "PII-Pruefer: jeder reale Name aus JEDEM Profil (#946)",
    ("services/recherche_migration.py", "SELECT hash, research_notes"):
        "Einmalige Migration des ganzen Bestands (#956)",
    ("services/remote_jobspy.py", "SELECT hash, title, location, description, remote_level"):
        "Einmalige Nachkorrektur des ganzen Bestands (#1072)",
    ("services/standorte.py", "SELECT DISTINCT location, lat, lon FROM jobs"):
        "Koordinaten je Ortsname — ein Nachschlagewerk, keine Nutzerdaten",
    ("services/stellen_grabstein.py", "SELECT t.alter_hash"):
        "Grabsteine je Kennung; die Kennung traegt das Profil",
    ("tools/jobs.py", "SELECT aj.id, aj.application_id, aj.job_hash FROM application_jobs"):
        "Verwaiste Verknuepfungen: gerade die ohne Bewerbung sind gesucht",
}

EINGRENZUNG = re.compile(
    r"\b(?:id|hash|job_hash|application_id|linked_application_id|contact_id|"
    r"document_id|meeting_id|email_id|alter_hash)\s*(?:=|IN)\s*[?(]", re.I)


def _tabellen_mit_profil(tmp_path) -> set:
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database
    importlib.reload(database)
    db = database.Database(db_path=tmp_path / "schema.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    con = db.connect()
    namen = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
             if any(c[1] == "profile_id" for c in con.execute(f"PRAGMA table_info({r[0]})"))}
    db.close()
    os.environ.pop("BA_DATA_DIR", None)
    return namen


def _funde(mit_profil: set) -> list:
    funde = []
    for p in sorted(SRC.rglob("*.py")):
        if p.name == "database.py":
            continue
        baum = ast.parse(p.read_text(encoding="utf-8-sig"))
        teile = {id(v) for j in ast.walk(baum) if isinstance(j, ast.JoinedStr)
                 for v in j.values}
        rel = p.relative_to(SRC).as_posix()
        for k in ast.walk(baum):
            if id(k) in teile or not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            sql = " ".join(k.value.split())
            if not re.match(r"SELECT\b", sql, re.I):
                continue
            tabellen = set(re.findall(r"\b(?:FROM|JOIN)\s+([a-z_]+)", sql, re.I)) & mit_profil
            if not tabellen or "profile_id" in sql or EINGRENZUNG.search(sql):
                continue
            if any(rel == d and sql.startswith(a) for d, a in UEBER_ALLE_PROFILE):
                continue
            funde.append(f"{rel}:{k.lineno}: {sql[:90]}")
    return funde


def test_jede_abfrage_nennt_ihr_profil(tmp_path):
    funde = _funde(_tabellen_mit_profil(tmp_path))
    assert not funde, "Ohne Profilfilter:\n" + "\n".join(funde)


def test_ausnahmen_gibt_es_noch():
    """Eine Ausnahme ohne Fundstelle ist eine Luecke im Guard."""
    for datei, anfang in UEBER_ALLE_PROFILE:
        baum = ast.parse((SRC / datei).read_text(encoding="utf-8-sig"))
        literale = [" ".join(k.value.split()) for k in ast.walk(baum)
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        assert any(t.startswith(anfang) for t in literale), f"{datei}: {anfang}"


# ================================================= Verhalten, zwei Profile


@pytest.fixture
def zwei(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database
    importlib.reload(database)
    db = database.Database(db_path=tmp_path / "zwei.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    a = db.create_profile("Erstes")
    b = db.create_profile("Zweites")
    db.switch_profile(a)
    app = db.add_application({"title": "Einkauf", "company": "Musterfirma", "status": "beworben",
                              "notes": "Telefonat am 01.10.2026 mit der Fachabteilung, freundlich."})
    db.add_meeting({"application_id": app, "title": "Gespraech", "meeting_date": "2026-10-02 10:00"})
    db.add_application_event(app, "stil_tracking", "Anschreiben-Stil: sachlich")
    db.save_jobs([{"hash": "pf1106a", "title": "Einkauf", "company": "Musterfirma",
                   "url": "https://jobs.example.org/a", "score": 12, "location": "Musterstadt"}])
    kid = db.add_contact({"full_name": "Erika Musterfrau", "company": "Musterfirma"})
    db.switch_profile(b)
    yield db, kid
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


def test_score_verteilung_nur_eigenes_profil(zwei):
    from bewerbungs_assistent.services import schwellen_verteilung
    db, _ = zwei
    assert schwellen_verteilung._werte(db) == []


def test_notiz_bericht_nur_eigenes_profil(zwei):
    from bewerbungs_assistent.services import notiz_drift
    db, _ = zwei
    assert notiz_drift.bericht(db)["bewerbungen_gesamt"] == 0


def test_stil_auswertung_nur_eigenes_profil(zwei):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    db, _ = zwei
    vorher = dash._db
    dash._db = db
    try:
        antwort = TestClient(dash.app).get("/api/stats/style").json()
    finally:
        dash._db = vorher
    assert antwort["status"] == "keine_daten"


def test_kurz_id_trifft_keinen_fremden_kontakt(zwei):
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools.kontakte import register
    db, kid = zwei
    mcp = FastMCP("t")
    register(mcp, db, logging.getLogger("t"))

    async def lauf():
        tool = await mcp.get_tool("kontakt_verknuepfen")
        res = await tool.run({"kontakt_id": kid[:6], "ziel_typ": "firma", "ziel_id": "Musterfirma"})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(lauf())
    assert erg.get("fehler") == "Kontakt nicht gefunden."
