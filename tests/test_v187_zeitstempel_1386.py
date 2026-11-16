"""#1386: Zeitstempel - eine Funktion für "jetzt", Leser normalisieren den Altbestand."""
import asyncio
import importlib
import os
import re
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bewerbungs_assistent.services import uhr

PAKET = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"


# -- die Funktionen ---------------------------------------------------------

def test_jetzt_ist_utc_mit_zone():
    t = uhr.jetzt()
    assert t.endswith("+00:00")
    assert abs((datetime.fromisoformat(t) - datetime.now(timezone.utc)).total_seconds()) < 5


def test_zeitpunkt_beide_formen_gleiche_uhrzeit():
    """Ohne Zone = Ortszeit des Rechners, mit Zone = die Zone."""
    lokal = datetime.now().replace(microsecond=0)
    aus_utc = lokal.astimezone(timezone.utc).isoformat()
    assert uhr.zeitpunkt(lokal.isoformat()) == uhr.zeitpunkt(aus_utc)


def test_zeitpunkt_unlesbares_ist_none():
    for kaputt in (None, "", "gestern", "2026-13-45"):
        assert uhr.zeitpunkt(kaputt) is None


def test_nach_zeit_ordnet_zonen_richtig_nicht_nach_text():
    # Textlich steht 20:29+01:00 nach 19:30+00:00, tatsaechlich ist es 19:29Z, also VORHER.
    a = {"id": 1, "event_date": "2026-11-11T20:29:03+01:00"}
    b = {"id": 2, "event_date": "2026-11-11T19:30:00+00:00"}
    assert [e["id"] for e in uhr.nach_zeit([b, a])] == [1, 2]
    assert [e["id"] for e in uhr.nach_zeit([a, b], rueckwaerts=True)] == [2, 1]


def test_nach_zeit_naive_ortszeit_gegen_utc():
    jetzt_lokal = datetime.now().replace(microsecond=0)
    spaeter_utc = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    alt = {"id": 1, "event_date": jetzt_lokal.isoformat()}        # Ortszeit ohne Zone
    neu = {"id": 2, "event_date": spaeter_utc}                    # UTC mit Zone
    assert [e["id"] for e in uhr.nach_zeit([neu, alt])] == [1, 2]


# -- die Bewerbung (Ende zu Ende) -------------------------------------------

@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_1386_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test Person"})
    yield db, _srv_mod.mcp
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


def test_anlage_notiz_und_statuswechsel_tragen_dieselbe_zeitform(umgebung):
    db, mcp = umgebung
    erg = _call(mcp, "bewerbung_erstellen", {
        "company": "Musterbetrieb GmbH", "title": "Planer", "status": "in_vorbereitung",
        "notes": "Notiz beim Anlegen"})
    aid = erg["bewerbung_id_voll"]
    _call(mcp, "bewerbung_notiz", {"bewerbung_id": aid, "notiz": "Zweite Notiz"})
    _call(mcp, "bewerbung_status_aendern", {"bewerbung_id": aid, "neuer_status": "beworben"})
    daten = [r["event_date"] for r in db.connect().execute(
        "SELECT event_date FROM application_events WHERE application_id=?", (aid,)).fetchall()]
    assert len(daten) >= 3
    assert all(d.endswith("+00:00") for d in daten), daten


def test_verlauf_und_letzte_notiz_stimmen_bei_gemischtem_altbestand(umgebung):
    db, mcp = umgebung
    aid = db.add_application({"title": "A", "company": "Musterbetrieb GmbH", "status": "beworben"})
    conn = db.connect()
    conn.execute("DELETE FROM application_events WHERE application_id=?", (aid,))
    lokal = datetime.now().replace(microsecond=0)
    # Altbestand: ältere Notiz in Ortszeit ohne Zone, neuere in UTC mit Zone
    aelter = (lokal - timedelta(minutes=30)).isoformat()
    neuer = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    for status, wann, notiz in (("notiz", neuer, "NEUE Notiz"), ("notiz", aelter, "alte Notiz"),
                                ("beworben", neuer, "")):
        conn.execute("INSERT INTO application_events (application_id, status, event_date, notes) "
                     "VALUES (?,?,?,?)", (aid, status, wann, notiz))
    conn.commit()
    det = _call(mcp, "bewerbung_details", {"bewerbung_id": aid})
    assert det["aktueller_stand"]["letzter_eintrag"]["status"] in ("beworben", "notiz")
    app = db.get_application(aid)
    assert [e["notes"] for e in app["events"] if e["status"] == "notiz"] == ["alte Notiz", "NEUE Notiz"]
    liste = db.get_applications()
    mine = next(a for a in liste if a["id"] == aid)
    assert mine["last_note"] == "NEUE Notiz"


# -- Wächter: keine neue Stelle mit Ortszeit ohne Zone ----------------------

_MUSTER = re.compile(r"\bnow\(\)\s*\.isoformat\(")

#: Datei -> Zahl der Stellen, die weiter Ortszeit OHNE Zone als Text bilden, und warum.
#: Ein Eintrag verlangt eine Begründung; wer eine Stelle auf `uhr.jetzt()` umstellt,
#: senkt die Zahl. Neue Stellen lassen den Test rot werden.
AUSNAHMEN = {
    "dashboard.py": (4, "generated_at der API-Ausgabe (Anzeige); 'jetzt' fuer Termin-Vergleiche (Termine "
                        "stehen in Ortszeit); 'jetzt' der Aufraeum-Runde und der Musteranalyse (Rechnung)"),
    "database.py": (1, "'jetzt' als Vergleichsgrenze gegen naechster-Probelauf-Spalten; Leser rechnet mit "
                       "datetime.now() (naiv)"),
    "export_report.py": (1, "Fusszeile 'Erstellt mit PBP' im Bericht, Text"),
    "job_scraper/__init__.py": (1, "Vorgabe fuer den Lauf-Stempel (`jetzt_iso`), Leser vergleicht naiv"),
    "services/bewerbung_lebenszyklus.py": (2, "nur das DATUM ([:10]) wird gespeichert, Ortszeit des Tages ist richtig"),
    "services/elwosa_dialog.py": (1, "Nachrichten fliessen in die Elwosa-Leser, die datetime.now() abziehen (naiv)"),
    "services/kalibrierung.py": (1, "Leser: datetime.now() - fromisoformat(...) (naiv)"),
    "services/lernprotokoll.py": (1, "Lernlauf-Protokoll, Leser in lernprotokoll.py (naiv)"),
    "services/sicherung.py": (1, "Sicherungs-Zeit, Leser rechnen mit naivem 'jetzt'"),
    "services/statistik_erweitert.py": (1, "Rechnung (Tage), nicht gespeichert"),
    "tools/analyse.py": (1, "Zeile im Protokolltext, kein Datenbankwert"),
    "tools/jobs.py": (1, "Registry-Stempel, Leser naiv"),
}


def test_keine_neue_stelle_speichert_ortszeit_ohne_zone():
    gefunden = {}
    for p in sorted(PAKET.rglob("*.py")):
        rel = p.relative_to(PAKET).as_posix()
        if rel.startswith("static"):
            continue
        n = len(_MUSTER.findall(p.read_text(encoding="utf-8-sig")))
        if n:
            gefunden[rel] = n
    erlaubt = {k: v[0] for k, v in AUSNAHMEN.items()}
    assert gefunden == erlaubt, (
        "Neue oder entfallene Stellen mit datetime.now().isoformat(): "
        f"gefunden {gefunden}, erlaubt {erlaubt}. Gespeicherte Zeitpunkte kommen von "
        "services/uhr.jetzt(); Ausnahmen nur mit Begründung in AUSNAHMEN.")


def test_die_datenbank_nimmt_dieselbe_funktion():
    from bewerbungs_assistent import database
    assert database._now().endswith("+00:00")
    quelle = (PAKET / "database.py").read_text(encoding="utf-8-sig")
    assert re.search(r"def _now\(\) -> str:\s+return _uhr\.jetzt\(\)", quelle)


def test_alter_tage_liest_die_zone():
    from bewerbungs_assistent.services import stellen_filter as sf
    jetzt = datetime.now(timezone.utc)
    vor_10_tagen_utc = (jetzt - timedelta(days=10, hours=1)).isoformat()
    vor_10_tagen_lokal = (datetime.now() - timedelta(days=10, hours=1)).isoformat()
    assert sf._alter_tage(vor_10_tagen_utc, datetime.now()) == 10
    assert sf._alter_tage(vor_10_tagen_lokal, datetime.now()) == 10
    assert sf._alter_tage("kaputt", datetime.now()) is None
