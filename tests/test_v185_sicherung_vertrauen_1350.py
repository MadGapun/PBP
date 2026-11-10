"""v1.8.5 — Sicherung, der man trauen kann (#1350, Punkte 1 bis 3).

1. Ein gescheitertes Einspielen wiederholt sich nicht und ueberschreibt nichts
   Neueres: die Vormerkung faellt, sobald die Datenbank getauscht ist.
2. Der Komplett-Export packt die Dokumente samt Unterordnern je Profil.
3. "Gesichert" steht erst nach einer Leseprobe der Kopie.

QA-Isolation: jede Datenbank liegt in einem eigenen tmp_path (BA_DATA_DIR).
"""
from __future__ import annotations

import io
import os
import sqlite3
import zipfile
from pathlib import Path

import pytest

NAME = "pbp-backup-2026-09-01_10-00-00-manuell.db"


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "pbp.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Beispiel Person"})
    yield d
    try:
        d.close()
    except Exception:
        pass
    os.environ.pop("BA_DATA_DIR", None)


def _zip_mit(pfad: Path, dateien: dict):
    with zipfile.ZipFile(pfad, "w") as z:
        for n, inhalt in dateien.items():
            z.writestr(n, inhalt)


def _vormerken(tmp_path, zip_dateien=None, zip_bytes=None):
    """Eine Fake-Sicherung (Inhalt b"x") mit Vormerkung; optional ein ZIP."""
    from bewerbungs_assistent.services import sicherung
    (tmp_path / "backups").mkdir(exist_ok=True)
    (tmp_path / "backups" / NAME).write_bytes(b"x")
    zp = sicherung._dokumente_zip(tmp_path / "backups" / NAME)
    if zip_dateien is not None:
        _zip_mit(zp, zip_dateien)
    if zip_bytes is not None:
        zp.write_bytes(zip_bytes)
    (tmp_path / "pbp.db").write_bytes(b"neuer-stand")
    (tmp_path / sicherung.VORMERKUNG).write_text(NAME, encoding="utf-8")


# ── Punkt 1: das Einspielen wiederholt sich nicht ───────────────────

def test_kaputtes_dokumenten_zip_laesst_die_vormerkung_nicht_stehen(tmp_path):
    from bewerbungs_assistent.services import sicherung
    _vormerken(tmp_path, zip_bytes=b"das ist kein zip")
    (tmp_path / "dokumente" / "P1").mkdir(parents=True)
    (tmp_path / "dokumente" / "P1" / "alt.txt").write_text("bleibt", encoding="utf-8")

    erg = sicherung.vorgemerkt_einspielen(tmp_path / "pbp.db")

    assert erg["ergebnis"] == "teilweise" and erg["dokumente"] is False
    assert not (tmp_path / sicherung.VORMERKUNG).exists(), "Vormerkung blieb stehen"
    # die Datenbank ist eingespielt, die bisherigen Dokumente sind unberuehrt
    assert (tmp_path / "pbp.db").read_bytes() == b"x"
    assert (tmp_path / "dokumente" / "P1" / "alt.txt").read_text(encoding="utf-8") == "bleibt"
    assert not (tmp_path / "dokumente.einspielen").exists()


def test_zweiter_start_ueberschreibt_nichts_neueres(tmp_path):
    """Der Kern von #1350: nach dem gescheiterten Teil darf der naechste Start
    die Datenbank NICHT erneut aus der Sicherung ueberschreiben."""
    from bewerbungs_assistent.services import sicherung
    _vormerken(tmp_path, zip_bytes=b"kaputt")
    sicherung.vorgemerkt_einspielen(tmp_path / "pbp.db")
    (tmp_path / "pbp.db").write_bytes(b"danach-eingetragen")  # der Mensch arbeitet weiter

    zweiter_start = sicherung.vorgemerkt_einspielen(tmp_path / "pbp.db")

    assert zweiter_start is None
    assert (tmp_path / "pbp.db").read_bytes() == b"danach-eingetragen"


def test_scheitert_das_kopieren_bleibt_die_datenbank_und_die_vormerkung_faellt(tmp_path, monkeypatch):
    from bewerbungs_assistent.services import sicherung
    _vormerken(tmp_path)

    def kaputt(*a, **kw):
        raise OSError("Platte voll")

    monkeypatch.setattr(sicherung.shutil, "copy2", kaputt)
    erg = sicherung.vorgemerkt_einspielen(tmp_path / "pbp.db")
    assert erg["status"] == "gescheitert" and erg["ergebnis"] == "gescheitert"
    assert (tmp_path / "pbp.db").read_bytes() == b"neuer-stand"
    assert not (tmp_path / "pbp.db.einspielen").exists()
    assert not (tmp_path / sicherung.VORMERKUNG).exists()


def test_vollstaendiges_einspielen_tauscht_die_dokumente_samt_unterordnern(tmp_path):
    from bewerbungs_assistent.services import sicherung
    _vormerken(tmp_path, zip_dateien={"P1/lebenslauf.pdf": "LL", "P2/zeugnis.pdf": "ZZ"})
    (tmp_path / "dokumente").mkdir()
    (tmp_path / "dokumente" / "neu.txt").write_text("nur im neuen Stand", encoding="utf-8")

    erg = sicherung.vorgemerkt_einspielen(tmp_path / "pbp.db")

    assert erg["ergebnis"] == "ganz" and erg["dokumente"] is True
    assert (tmp_path / "dokumente" / "P1" / "lebenslauf.pdf").read_text() == "LL"
    assert (tmp_path / "dokumente" / "P2" / "zeugnis.pdf").read_text() == "ZZ"
    assert not (tmp_path / "dokumente" / "neu.txt").exists()
    assert not (tmp_path / "dokumente.alt").exists()
    assert not (tmp_path / "dokumente.einspielen").exists()


def test_der_ausgang_wird_festgehalten_und_laesst_sich_quittieren(tmp_path):
    from types import SimpleNamespace
    from bewerbungs_assistent.services import sicherung
    _vormerken(tmp_path, zip_bytes=b"kaputt")
    sicherung.vorgemerkt_einspielen(tmp_path / "pbp.db")
    ort = SimpleNamespace(db_path=tmp_path / "pbp.db")
    gemerkt = sicherung.einspielen_ergebnis(ort)
    assert gemerkt["ergebnis"] == "teilweise" and gemerkt["name"] == NAME and gemerkt["hinweis"]
    assert sicherung.einspielen_ergebnis_quittieren(ort) is True
    assert sicherung.einspielen_ergebnis(ort) is None


def test_dashboard_nennt_den_ausgang(db, tmp_path):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.services import sicherung
    dash._db = db
    # Die offene Datenbank sperrt unter Windows das Austauschen; hier zaehlt nur
    # die Auskunft des Dashboards ueber einen festgehaltenen Ausgang.
    sicherung._einspielen_melden(tmp_path, "teilweise", NAME, False, "Hinweis")
    tc = TestClient(dash.app)
    assert tc.get("/api/sicherungen").json()["letztes_einspielen"]["ergebnis"] == "teilweise"
    assert tc.delete("/api/sicherungen/einspielen-ergebnis").json() == {"quittiert": True}
    assert tc.get("/api/sicherungen").json()["letztes_einspielen"] is None


# ── Punkt 2: der Komplett-Export packt die Dokumente ────────────────

def test_komplett_export_enthaelt_dokumente_in_unterordnern(db, tmp_path):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    dash._db = db
    (tmp_path / "dokumente" / "P1").mkdir(parents=True)
    (tmp_path / "dokumente" / "P1" / "lebenslauf.pdf").write_bytes(b"LL")
    (tmp_path / "dokumente" / "P1" / "anschreiben").mkdir()
    (tmp_path / "dokumente" / "P1" / "anschreiben" / "a1.docx").write_bytes(b"AN")
    (tmp_path / "dokumente" / "lose.txt").write_bytes(b"lose")

    antwort = TestClient(dash.app).get("/api/export-package")

    assert antwort.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(antwort.content))
    namen = set(z.namelist())
    assert {"pbp.db", "README.txt", "dokumente/lose.txt", "dokumente/P1/lebenslauf.pdf",
            "dokumente/P1/anschreiben/a1.docx"} <= namen
    assert z.read("dokumente/P1/lebenslauf.pdf") == b"LL"
    readme = z.read("README.txt").decode("utf-8")
    assert "install.bat" not in readme.replace("INSTALLIEREN.bat", "")
    assert "3 Dateien" in readme
    assert "%LOCALAPPDATA%\\BewerbungsAssistent\\data" in readme


def test_export_leseprobe_schlaegt_an_wenn_dokumente_fehlen(db, tmp_path, monkeypatch):
    """Gegenprobe zur Leseprobe: fehlt im Paket eine Datei, gibt es keinen Download."""
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    dash._db = db
    (tmp_path / "dokumente" / "P1").mkdir(parents=True)
    (tmp_path / "dokumente" / "P1" / "a.txt").write_bytes(b"A")
    orig = zipfile.ZipFile.write

    def schluckt(self, filename, arcname=None, *a, **kw):
        if str(arcname or "").endswith("a.txt"):
            return None  # "geschrieben", aber nichts im Paket
        return orig(self, filename, arcname, *a, **kw)

    monkeypatch.setattr(zipfile.ZipFile, "write", schluckt)
    antwort = TestClient(dash.app).get("/api/export-package")
    assert antwort.status_code == 500


# ── Punkt 3: keine Erfolgsmeldung ohne Leseprobe ────────────────────

def test_gesichert_heisst_die_kopie_wurde_geoeffnet(db):
    from bewerbungs_assistent.services import sicherung
    erg = sicherung.sichern(db, "manuell")
    assert erg["status"] == "gesichert"
    kopie = Path(db.db_path).parent / "backups" / erg["name"]
    con = sqlite3.connect(str(kopie))
    try:
        assert con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert con.execute("SELECT count(*) FROM profile").fetchone()[0] >= 1
    finally:
        con.close()


def test_eine_unlesbare_kopie_ist_keine_sicherung(db, monkeypatch):
    """Die Sicherung schreibt eine Datei, die keine Datenbank ist: sie wird
    verworfen und es gibt KEIN 'gesichert'."""
    from bewerbungs_assistent.services import sicherung

    class Gesperrt:
        """Ersatz fuer sqlite3.connect, dessen Backup eine kaputte Datei hinterlaesst."""
        def __init__(self, pfad):
            self.pfad = pfad
        def execute(self, *a, **kw):
            return self
        def backup(self, dst):
            Path(dst.pfad).write_bytes(b"kein sqlite" * 100)
        def close(self):
            pass

    echte_verbindung = sqlite3.connect

    def connect(pfad, *a, **kw):
        if "uri" in kw:  # die Leseprobe: echte Verbindung auf die kaputte Kopie
            return echte_verbindung(pfad, *a, **kw)
        return Gesperrt(pfad)

    monkeypatch.setattr(sicherung.sqlite3, "connect", connect)
    erg = sicherung.sichern(db, "manuell")
    assert erg["status"] == "fehler" and "verworfen" in erg["fehler"]
    assert sicherung.liste(db) == []
    assert not list((Path(db.db_path).parent / "backups").glob("pbp-backup-*.db"))


def test_ein_unvollstaendiges_zip_wird_nicht_als_sicherung_mit_dokumenten_gemeldet(db, monkeypatch):
    from bewerbungs_assistent.services import sicherung
    (Path(db.db_path).parent / "dokumente" / "P1").mkdir(parents=True)
    (Path(db.db_path).parent / "dokumente" / "P1" / "a.txt").write_bytes(b"A")
    monkeypatch.setattr(sicherung, "_zip_pruefen", lambda *_: "0 Dateien statt 1")
    erg = sicherung.sichern(db, "manuell")
    assert erg["status"] == "gesichert"          # die Datenbank ist gesichert ...
    assert erg["dokumente"] is False             # ... die Dokumente ausdruecklich nicht
    assert "konnten nicht mitgesichert werden" in erg["hinweis"]
    assert not sicherung.liste(db)[0]["dokumente"]


def test_zip_pruefung_erkennt_zahl_und_beschaedigung(tmp_path):
    from bewerbungs_assistent.services import sicherung
    z = tmp_path / "d.zip"
    _zip_mit(z, {"a.txt": "A", "b/c.txt": "C"})
    assert sicherung._zip_pruefen(z, 2) == ""
    assert "2 Dateien statt 3" in sicherung._zip_pruefen(z, 3)
    z.write_bytes(b"kein zip")
    assert "nicht zu öffnen" in sicherung._zip_pruefen(z, 2)
