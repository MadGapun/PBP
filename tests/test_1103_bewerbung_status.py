"""#1103: `arbeitgeber_ausgefallen` gilt ueberall als abgeschlossen, weil
alle dieselbe Liste lesen.
"""
from __future__ import annotations

import ast
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "bewerbungs_assistent"

#: Listen, die eine ANDERE Frage beantworten. Jede mit Grund — eine
#: Ausnahme ohne Grund waechst beliebig (#1004/#1005).
AUSNAHMEN = {
    ("services/scoring_kriterien.py", "ARCHIV_STATUS"):
        "bewusst enger (#68): nur diese Titel geben kein Signal mehr",
    ("services/nachfass_text.py", None): "Anlaesse fuer einen Nachfasstext, keine Endzustaende",
    ("tools/analyse.py", "stilarchiv"): "Ergebnis einer Stilarchiv-Version, anderes Vokabular",
    ("tools/bewerbungen.py", "inbound"): "Status, mit denen eine Inbound-Anfrage falsch angelegt wird",
    ("tools/bewerbungen.py", "konvertieren"): "Zielstatus beim Umwandeln einer Anfrage",
    ("tools/bewerbungen.py", "sortierung"): "Sortierreihenfolge der Anzeige",
    ("database.py", "abgesagt"): "kennt zusaetzlich den Altwert 'abgesagt'",
    ("services/firmen_bezuege.py", "abgesagt"): "kennt zusaetzlich den Altwert 'abgesagt'",
    ("dashboard.py", "interview_abgeschlossen"): "Rueckschau: auch ein beendetes Interview ist kein offener Faden",
}


def _listen():
    for p in sorted(SRC.rglob("*.py")):
        rel = str(p.relative_to(SRC))
        if rel == "services/bewerbung_status.py":
            continue
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8-sig"))):
            if isinstance(n, (ast.Tuple, ast.List, ast.Set)):
                werte = [e.value for e in n.elts
                         if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                if "abgelehnt" in werte and "zurueckgezogen" in werte:
                    yield rel, n.lineno, werte


def _erklaert(rel, werte):
    if rel == "services/scoring_kriterien.py" and werte == ["abgelehnt", "zurueckgezogen"]:
        return True
    if rel == "services/nachfass_text.py":
        return True
    if rel == "tools/analyse.py" and "ohne_antwort" in werte:
        return True
    if rel == "tools/bewerbungen.py" and (werte == ["zurueckgezogen", "abgelehnt"]
                                          or "in_vorbereitung" in werte):
        return True
    if rel in ("database.py", "services/firmen_bezuege.py") and "abgesagt" in werte:
        return True
    if rel == "dashboard.py" and "interview_abgeschlossen" in werte:
        return True
    return False


def test_keine_eigene_statusliste():
    funde = [f"{rel}:{z}: {w}" for rel, z, w in _listen() if not _erklaert(rel, w)]
    assert not funde, "\n".join(funde)


def test_ausnahmen_haben_einen_grund():
    assert all(len(grund) > 10 for grund in AUSNAHMEN.values())


def test_quelle_kennt_den_status():
    from bewerbungs_assistent.services import bewerbung_status as bs
    from bewerbungs_assistent.tools.bewerbungen import VALID_STATUSES
    assert "arbeitgeber_ausgefallen" in bs.ARCHIV
    assert "angenommen" in bs.ABGESCHLOSSEN and "angenommen" not in bs.ARCHIV
    assert VALID_STATUSES == set(bs.ALLE)


# ── AK 1: kein Leser zaehlt sie als aktiv ───────────────────────────

@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Status"})
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _ausgefallen(db, firma="Musterbetrieb GmbH"):
    app = db.add_application({"title": "Sachbearbeitung", "company": firma,
                              "status": "beworben"})
    db.update_application_status(app, "arbeitgeber_ausgefallen")
    return db.get_application(app)


def _zusammenfassung(apps):
    from bewerbungs_assistent.services.workspace_service import build_workspace_summary
    return build_workspace_summary(None, [], apps, {"active": 0}, {"status": "nie"}, {"due": 0, "total": 0})


def _zaehler(erg):
    for v in erg.values():
        if isinstance(v, dict) and "archived" in v:
            return v
    raise AssertionError(erg)


def test_kopfzeile_zaehlt_sie_nicht_als_aktiv(db):
    z = _zaehler(_zusammenfassung([_ausgefallen(db)]))
    assert z["active"] == 0 and z["archived"] == 1


def test_dokumentzuordnung_schuetzt_sie(db):
    from bewerbungs_assistent.services import dokument_zuordnung as dz
    assert "arbeitgeber_ausgefallen" in dz.ABGESCHLOSSEN


def test_mailzuordnung_stellt_sie_zurueck(db):
    from bewerbungs_assistent.services import email_service
    import inspect
    assert "bewerbung_status" in inspect.getsource(email_service)


def test_anlage_blockt_nicht_wegen_ausgefallener_bewerbung(db):
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    _ausgefallen(db)
    mcp = FastMCP("PBP #1103")
    register_all(mcp, db, logging.getLogger("test.1103"))

    async def lauf():
        t = await mcp.get_tool("stelle_manuell_anlegen")
        return (await t.run({"titel": "Sachbearbeitung", "firma": "Musterbetrieb GmbH",
                             "beschreibung": "x" * 120,
                             "url": "https://example.com/1103"})).structured_content
    erg = asyncio.run(lauf())
    assert erg.get("warnung") != "duplikat_bewerbung", erg


# ── AK 3: eine Statusaenderung zaehlt als Aktivitaet ────────────────

def test_statusaenderung_von_gestern_ist_aktivitaet():
    vor_sechs_wochen = (datetime.now() - timedelta(days=42)).isoformat()
    gestern = (datetime.now() - timedelta(days=1)).isoformat()
    app = {"status": "interview", "applied_at": vor_sechs_wochen,
           "updated_at": gestern, "created_at": vor_sechs_wochen}
    assert _zusammenfassung([app]).get("inactivity") is None
    app["updated_at"] = vor_sechs_wochen
    assert _zusammenfassung([app])["inactivity"]["days"] >= 42
