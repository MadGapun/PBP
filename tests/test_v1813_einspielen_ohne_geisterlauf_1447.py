"""v1.8.13 — nach dem Einspielen keine falsche Meldung "fehlgeschlagen" (#1447).

Jede Sicherung, die im Hintergrund entsteht, enthaelt ihren eigenen Lauf als
"running". Kam der beim Einspielen mit zurueck, machte die Startup-Bereinigung
daraus "fehlgeschlagen" (Sicherung aelter als eine Stunde) - oder die Karte
zeigte dauerhaft "Sicherung laeuft" (frische Sicherung).

QA-Isolation: jede Datenbank liegt in einem eigenen tmp_path (BA_DATA_DIR).
"""
from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timedelta

import pytest

OFFEN = ("running", "pending", "laeuft")


def _oeffnen(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "pbp.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    return d


@pytest.fixture
def umgebung(tmp_path):
    from bewerbungs_assistent.services import sicherung
    sicherung.erfolg_merken()   # Wartezeit nach Fehlschlag ist Modulzustand: sauber rein und raus
    dbs = []

    def oeffnen():
        d = _oeffnen(tmp_path)
        dbs.append(d)
        return d

    yield tmp_path, oeffnen
    sicherung.erfolg_merken()
    for d in dbs:
        try:
            d.close()
        except Exception:
            pass
    os.environ.pop("BA_DATA_DIR", None)


def _warten(db, job_id, sek=30):
    ende = time.time() + sek
    while time.time() < ende:
        job = db.get_background_job(job_id)
        if job and job["status"] not in OFFEN:
            return job
        time.sleep(0.1)
    raise AssertionError(f"Sicherung nicht fertig: {db.get_background_job(job_id)}")


def _sicherung_mit_laeufen(db, alter_sek: int) -> str:
    """Eine echte Hintergrund-Sicherung; danach in IHRER Datei die Laeufe so,
    wie sie beim Sichern standen: die Sicherung selbst und eine Aufraeum-Runde
    noch "running", dazu ein wirklich gescheiterter Versuch. `alter_sek` setzt
    das Alter der Eintraege (Startup-Bereinigung greift ab 3600 s)."""
    from bewerbungs_assistent.services import sicherung
    erg = sicherung.im_hintergrund(db, "manuell")
    assert erg["status"] == "gestartet", erg
    _warten(db, erg["job_id"])
    name = sicherung.letzte(db)["name"]
    datei = sicherung.ordner(db) / name
    zeit = (datetime.now() - timedelta(seconds=alter_sek)).isoformat(timespec="seconds")
    alt = (datetime.now() - timedelta(days=3)).isoformat(timespec="seconds")
    conn = sqlite3.connect(str(datei))
    conn.execute("UPDATE background_jobs SET status='running', progress=10, message='Sicherung läuft', "
                 "created_at=?, updated_at=? WHERE id=?", (zeit, zeit, erg["job_id"]))
    conn.execute("INSERT INTO background_jobs (id, job_type, params, status, progress, message, "
                 "created_at, updated_at) VALUES ('aufr-1', 'aufraeumen', '{}', 'running', 5, '', ?, ?)",
                 (zeit, zeit))
    conn.execute("INSERT INTO background_jobs (id, job_type, params, status, progress, message, "
                 "created_at, updated_at) VALUES ('alt-fehler', 'sicherung', '{}', 'fehler', 0, "
                 "'Datenträger voll', ?, ?)", (alt, alt))
    conn.commit()
    conn.close()
    for rest in ("-wal", "-shm"):
        assert not datei.with_name(datei.name + rest).exists()
    return name


def _einspielen_und_starten(tmp_path, oeffnen, db, name):
    from bewerbungs_assistent import dashboard
    from bewerbungs_assistent.services import sicherung
    assert sicherung.vormerken(db, name)["status"] == "vorgemerkt"
    db.close()
    neu = oeffnen()
    ergebnis = sicherung.einspielen_ergebnis(neu)
    assert ergebnis and ergebnis["status"] == "eingespielt" and ergebnis["name"] == name, ergebnis
    dashboard._cleanup_stale_jobs(neu)   # was beim Start des Dashboards laeuft
    return neu, ergebnis


@pytest.mark.parametrize("alter_sek", [2 * 3600, 60], ids=["aelter_als_eine_stunde", "frisch"])
def test_nach_dem_einspielen_meldet_die_karte_keinen_fehlschlag(umgebung, alter_sek):
    tmp_path, oeffnen = umgebung
    from bewerbungs_assistent.services import sicherung
    db = oeffnen()
    name = _sicherung_mit_laeufen(db, alter_sek)

    neu, _ = _einspielen_und_starten(tmp_path, oeffnen, db, name)

    # AK2: kein Geisterlauf mehr
    offen = neu.connect().execute(
        "SELECT id, job_type, status FROM background_jobs WHERE status IN ('running','pending','laeuft')"
    ).fetchall()
    assert not offen, [dict(r) for r in offen]
    # AK1: die Karte sagt weder "fehlgeschlagen" noch "laeuft"
    v = sicherung.letzter_versuch(neu)
    assert v["status"] == "fertig", v
    assert v["nachricht"] == "Sicherung angelegt", v
    # AK4: die Aufraeum-Runde ist kein Fehler
    aufr = neu.get_background_job("aufr-1")
    assert aufr["status"] == "fertig" and "Startup-Bereinigung" not in (aufr["message"] or ""), aufr
    assert aufr["message"] == sicherung.MITGEBRACHT_TEXT
    # AK3: ein wirklich gescheiterter Versuch in der Sicherung bleibt, wie er war
    alt = neu.get_background_job("alt-fehler")
    assert alt["status"] == "fehler" and alt["message"] == "Datenträger voll", alt


def test_ein_gescheiterter_versuch_nach_dem_einspielen_wird_weiter_gemeldet(umgebung, monkeypatch):
    """AK3, Gegenrichtung: das Aufraeumen beim Einspielen deckt keinen neuen Fehler zu."""
    tmp_path, oeffnen = umgebung
    from bewerbungs_assistent.services import sicherung
    db = oeffnen()
    name = _sicherung_mit_laeufen(db, 2 * 3600)
    neu, _ = _einspielen_und_starten(tmp_path, oeffnen, db, name)

    monkeypatch.setattr(sicherung, "sichern",
                        lambda *a, **k: {"status": "fehler", "fehler": "Datenträger voll"})
    erg = sicherung.im_hintergrund(neu, "manuell")
    _warten(neu, erg["job_id"])
    v = sicherung.letzter_versuch(neu)
    assert v["status"] == "fehler" and v["nachricht"] == "Datenträger voll" and v["aktuell"], v


def test_ein_echter_haenger_wird_weiter_bereinigt(umgebung):
    """Die Startup-Bereinigung (#155, #1118) bleibt fuer Laeufe des eigenen Bestands."""
    tmp_path, oeffnen = umgebung
    from bewerbungs_assistent import dashboard
    db = oeffnen()
    jid = db.create_background_job("sicherung", {"anlass": "manuell"})
    alt = (datetime.now() - timedelta(hours=2)).isoformat(timespec="seconds")
    db.connect().execute("UPDATE background_jobs SET status='running', created_at=?, updated_at=? WHERE id=?",
                         (alt, alt, jid))
    db.connect().commit()
    dashboard._cleanup_stale_jobs(db)
    job = db.get_background_job(jid)
    assert job["status"] == "fehler" and "Startup-Bereinigung" in job["message"], job


def test_eine_sicherung_ohne_lauftabelle_wird_trotzdem_eingespielt(tmp_path):
    """Alte oder fremde Sicherungsdatei: das Abschliessen scheitert still, das Einspielen nicht."""
    from bewerbungs_assistent.services import sicherung
    datei = tmp_path / "alt.db"
    conn = sqlite3.connect(str(datei))
    conn.execute("CREATE TABLE settings (key TEXT, value TEXT)")
    conn.commit()
    conn.close()
    assert sicherung.mitgebrachte_laeufe_abschliessen(datei) == 0
    kein_db = tmp_path / "kaputt.db"
    kein_db.write_bytes(b"x")
    assert sicherung.mitgebrachte_laeufe_abschliessen(kein_db) == 0
    assert kein_db.read_bytes() == b"x"
    for rest in ("-wal", "-shm"):
        assert not (tmp_path / ("kaputt.db" + rest)).exists()
