"""#1097: Die DSGVO-Löschung leert den ganzen Datenordner.

Jeder Test läuft in einem Temp-Datenordner (`BA_DATA_DIR`) mit
Zusicherung — ein Test, der den Datenordner löscht, wäre sonst selbst der
Datenverlust.
"""
from __future__ import annotations

import os
import re
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "bewerbungs_assistent"


@pytest.fixture
def umgebung(tmp_path):
    daten = tmp_path / "daten"
    daten.mkdir()
    os.environ["BA_DATA_DIR"] = str(daten)
    from bewerbungs_assistent.database import Database, get_data_dir
    assert get_data_dir() == daten
    db = Database(db_path=daten / "pbp.db")
    db.initialize()
    assert str(daten) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    from fastapi.testclient import TestClient
    client = TestClient(dash.app)
    client.post("/api/profile", json={"name": "Loeschtest"})
    yield {"db": db, "client": client, "daten": daten}
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


def _befuellen(daten: Path, wal: bool = True) -> None:
    """Jede Art Datei, die PBP im Datenordner anlegt.

    Eine Attrappe der WAL-Datei neben einer offenen Datenbank liest SQLite
    als echt — nur Tests, die gleich löschen, legen sie an."""
    if wal:
        (daten / "pbp.db-wal").write_bytes(b"wal")
    for ordner, datei in [("backups", "pbp_vor_update.db"), ("backup", "pbp_x.db"),
                          ("emails", "absage.eml"), ("logs", "pbp.log"),
                          ("linkedin_session", "cookies"), ("xing_session", "cookies"),
                          ("dokumente", "cv.pdf"), ("export", "cv.docx")]:
        (daten / ordner).mkdir(exist_ok=True)
        (daten / ordner / datei).write_text("persönlich", encoding="utf-8")
    (daten / "limitations.log").write_text("Freitext", encoding="utf-8")
    (daten / "unbekannt_neu.json").write_text("{}", encoding="utf-8")


def _dsgvo(client):
    return client.post("/api/danger/leeren",
                       json={"confirm": "LOESCHEN", "modus": "dsgvo"})


# ── AK 1: nach der Löschung ist nichts Persönliches mehr da ──────────

def test_dsgvo_leert_den_ganzen_datenordner(umgebung):
    daten = umgebung["daten"]
    _befuellen(daten)
    r = _dsgvo(umgebung["client"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok", r.json()
    rest = sorted(p.name for p in daten.iterdir())
    assert rest == [], f"liegen geblieben: {rest}"
    assert daten.exists(), "der Datenordner selbst bleibt"


def test_alter_weg_nimmt_dieselbe_mechanik(umgebung):
    daten = umgebung["daten"]
    _befuellen(daten)
    r = umgebung["client"].request("DELETE", "/api/privacy-delete-all",
                                   json={"confirm": "ALLES_LOESCHEN"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert list(daten.iterdir()) == []


# ── AK 3: keine Löschung unter laufender Hintergrundarbeit ───────────

def test_laufende_jobsuche_verhindert_die_loeschung(umgebung):
    daten = umgebung["daten"]
    halt = threading.Event()
    t = threading.Thread(target=halt.wait, name="pbp-jobsuche-test", daemon=True)
    t.start()
    try:
        r = _dsgvo(umgebung["client"])
    finally:
        halt.set()
        t.join(timeout=5)
    assert r.status_code == 409
    assert "Jobsuche" in r.json()["message"]
    assert (daten / "pbp.db").exists(), "trotz laufender Arbeit gelöscht"


def test_dauerlaeufer_blockieren_nicht(umgebung):
    """Taktgeber und Lebenszeichen laufen immer; sie dürfen die Löschung
    nicht für immer sperren."""
    halt = threading.Event()
    t = threading.Thread(target=halt.wait, name="automatik-scheduler", daemon=True)
    t.start()
    try:
        from bewerbungs_assistent.services import datenordner
        assert datenordner.laufende_arbeit() == []
    finally:
        halt.set()
        t.join(timeout=5)


# ── Teilweise Löschung: benannt, vorgemerkt, beim Start nachgeholt ───

def test_teilweise_loeschung_ist_kein_erfolg(umgebung, monkeypatch):
    daten = umgebung["daten"]
    _befuellen(daten)
    import shutil
    echt = shutil.rmtree

    def gesperrt(pfad, *a, **k):
        if Path(pfad).name == "emails":
            raise PermissionError("von einem anderen Prozess verwendet")
        return echt(pfad, *a, **k)

    monkeypatch.setattr(shutil, "rmtree", gesperrt)
    r = _dsgvo(umgebung["client"])
    body = r.json()
    assert body["status"] == "teilweise"
    assert any("emails" in f["pfad"] for f in body["nicht_geloescht"])
    assert "Claude Desktop" in body["message"]

    from bewerbungs_assistent.services import datenordner
    assert (daten / datenordner.VORMERKUNG).exists()
    monkeypatch.setattr(shutil, "rmtree", echt)

    # Nächster Start: der Rest geht, bevor die Datenbank öffnet.
    from bewerbungs_assistent.database import Database
    db2 = Database(db_path=daten / "pbp.db")
    db2.initialize()
    try:
        assert not (daten / "emails").exists()
        assert not (daten / datenordner.VORMERKUNG).exists()
    finally:
        db2.close()


def test_ohne_vormerkung_loescht_der_start_nichts(umgebung):
    daten = umgebung["daten"]
    _befuellen(daten)
    from bewerbungs_assistent.database import Database
    db2 = Database(db_path=daten / "zweit.db")
    db2.initialize()
    db2.close()
    assert (daten / "emails" / "absage.eml").exists()


# ── AK 2: jeder Pfad unter dem Datenordner steht in der Liste ────────

_NAME_UNTER_DATENORDNER = re.compile(
    r"(?:get_data_dir\(\)|data_dir|db_path\.parent|_datenordner\(\)|basis)"
    r"\s*/\s*[\"']([^\"'/\\]+)[\"']")
_OS_JOIN = re.compile(r"os\.path\.join\(\s*data_dir\s*,\s*[\"']([^\"']+)[\"']")


def _namen_im_code() -> set:
    gefunden = set()
    for p in SRC.rglob("*.py"):
        text = p.read_text(encoding="utf-8-sig")
        gefunden.update(_NAME_UNTER_DATENORDNER.findall(text))
        gefunden.update(_OS_JOIN.findall(text))
    return gefunden


def test_jeder_pfad_im_code_steht_in_der_liste():
    from bewerbungs_assistent.services import datenordner
    fehlen = sorted(_namen_im_code() - datenordner.NAMEN)
    assert not fehlen, (
        f"Unter dem Datenordner angelegt, aber nicht in datenordner.INHALT: {fehlen}")


def test_heartbeat_datei_steht_in_der_liste():
    from bewerbungs_assistent import heartbeat
    from bewerbungs_assistent.services import datenordner
    assert heartbeat._HEARTBEAT_FILE in datenordner.NAMEN


def test_guard_erkennt_einen_neuen_pfad(tmp_path, monkeypatch):
    """Der Guard sieht wirklich etwas: ein neuer Ordner fällt auf."""
    probe = 'x = get_data_dir() / "ganz_neu_1097"\n'
    assert _NAME_UNTER_DATENORDNER.findall(probe) == ["ganz_neu_1097"]


# ── AK 4 und 5: dieselben Orte überall, und was außerhalb bleibt ─────

def test_gefahrenzone_nennt_was_geloescht_wird(umgebung):
    _befuellen(umgebung["daten"], wal=False)
    v = umgebung["client"].get("/api/danger/bereiche").json()
    namen = {e["name"] for e in v["dsgvo"]["inhalt"]}
    assert {"pbp.db", "backups", "emails", "logs", "linkedin_session"} <= namen
    assert "unbekannt_neu.json" in namen, "Unbekanntes fehlt in der Anzeige"
    assert "außerhalb" in v["dsgvo"]["ausserhalb_hinweis"]
    assert "Anthropic" in v["dsgvo"]["ausserhalb_hinweis"]


def test_gefahrenzone_nennt_eigene_ablageordner(umgebung, tmp_path):
    from bewerbungs_assistent.services import ablage
    eigen = tmp_path / "meine_bewerbungen"
    eigen.mkdir()
    umgebung["db"].set_setting(ablage.AUSGABE_SCHLUESSEL, str(eigen))
    v = umgebung["client"].get("/api/danger/bereiche").json()
    assert any(o["pfad"] == str(eigen) for o in v["dsgvo"]["ausserhalb"])
    # ... und die Löschung fasst ihn nicht an.
    (eigen / "cv.docx").write_text("x", encoding="utf-8")
    _dsgvo(umgebung["client"])
    assert (eigen / "cv.docx").exists()


def test_datenuebersicht_kennt_alle_ordner(umgebung):
    from bewerbungs_assistent.services import datenordner
    info = umgebung["client"].get("/api/privacy-info").json()
    ordner = {e["name"] for e in datenordner.INHALT if e["art"] == "ordner"}
    assert ordner <= set(info["subdirs"])


def test_selbstauskunft_liest_dieselbe_liste():
    text = (SRC / "export_report.py").read_text(encoding="utf-8")
    assert "datenordner.INHALT" in text
    assert "datenordner.AUSSERHALB_SATZ" in text
