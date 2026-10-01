"""v1.7.146 — Eine unlesbare Datei kippt die Sicherung nicht mehr, und Fehler sind sichtbar (#1142).

Befund (01.10.2026, Prüfung "Zeit und Zwischenspeicher"): Eine einzige
gesperrte Datei im Dokumentenordner (Virenscanner, Office) brachte die ganze
Sicherung samt Datenbankkopie zu Fall. Die Karte sagte "läuft im
Hintergrund", fragte den Job nie ab und stellte einen Abruffehler als "Noch
keine Sicherung vorhanden" dar. Auf dem Planer-Weg startete die Sicherung
bei jedem Takt neu: vier Takte, vier Jobs, keine Sicherung.

Hier: die Datenbankkopie bleibt, gesperrte Dateien werden übersprungen und
genannt, nach einem Fehlschlag wartet die Automatik, und der Ausgang des
letzten Versuchs steht in der Antwort der Karte.
"""
import os
import sys
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import sicherung  # noqa: E402


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "pbp.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Sicherung"})
    docs = tmp_path / "dokumente"
    docs.mkdir()
    (docs / "lebenslauf.pdf").write_bytes(b"A" * 2048)
    (docs / "gesperrt.pdf").write_bytes(b"B" * 2048)
    (docs / "zeugnis.pdf").write_bytes(b"C" * 2048)
    sicherung.erfolg_merken()
    yield d
    sicherung.erfolg_merken()
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _sperre(monkeypatch, endung="gesperrt.pdf"):
    """Wie ein Virenscanner: genau diese Datei lässt sich nicht lesen."""
    echt = zipfile.ZipFile.write

    def write(self, filename, arcname=None, *a, **kw):
        if str(arcname or filename).endswith(endung):
            raise PermissionError(13, "Der Prozess kann nicht auf die Datei zugreifen")
        return echt(self, filename, arcname, *a, **kw)

    monkeypatch.setattr(zipfile.ZipFile, "write", write)


# ══ Die Sicherung selbst ═══════════════════════════════════════════

def test_eine_gesperrte_datei_kippt_die_sicherung_nicht(db, monkeypatch):
    _sperre(monkeypatch)
    erg = sicherung.sichern(db, "manuell")
    assert erg["status"] == "gesichert"
    assert erg["dokumente"] is True
    assert erg["uebersprungen"] == ["gesperrt.pdf"]
    assert "gesperrt" in erg["hinweis"] and "1 Datei" in erg["hinweis"]
    ordner = sicherung.ordner(db)
    dbs = sorted(ordner.glob("pbp-backup-*.db"))
    assert len(dbs) == 1, "die Datenbankkopie muss bleiben"
    with zipfile.ZipFile(sicherung._dokumente_zip(dbs[0])) as z:
        assert sorted(z.namelist()) == ["lebenslauf.pdf", "zeugnis.pdf"]


def test_scheitert_das_packen_ganz_bleibt_die_datenbankkopie(db, monkeypatch):
    def kaputt(*a, **kw):
        raise OSError(28, "Auf dem Gerät ist kein Speicherplatz mehr verfügbar")

    monkeypatch.setattr(zipfile, "ZipFile", kaputt)
    erg = sicherung.sichern(db, "manuell")
    assert erg["status"] == "gesichert" and erg["dokumente"] is False
    assert "Dokumente konnten nicht mitgesichert werden" in erg["hinweis"]
    ordner = sicherung.ordner(db)
    assert len(list(ordner.glob("pbp-backup-*.db"))) == 1, "die Datenbankkopie wurde gelöscht"
    assert list(ordner.glob("*-dokumente.zip")) == [], "ein halbes ZIP blieb liegen"


def test_eine_glatte_sicherung_hat_keinen_hinweis(db):
    erg = sicherung.sichern(db, "manuell")
    assert erg["status"] == "gesichert" and erg["dokumente"] is True
    assert erg["uebersprungen"] == [] and erg["hinweis"] == ""


# ══ Die Automatik wartet nach einem Fehlschlag ═════════════════════

def test_die_frist_waechst_und_endet(db):
    t0 = datetime(2026, 10, 1, 12, 0)
    assert sicherung.gesperrt_bis(t0) is None
    sicherung.fehlschlag_merken(t0)
    assert sicherung.gesperrt_bis(t0 + timedelta(minutes=14)) == t0 + timedelta(minutes=15)
    assert sicherung.gesperrt_bis(t0 + timedelta(minutes=16)) is None
    sicherung.fehlschlag_merken(t0)  # zweiter Fehlschlag in Folge: 30 Minuten
    assert sicherung.gesperrt_bis(t0 + timedelta(minutes=29)) is not None
    assert sicherung.gesperrt_bis(t0 + timedelta(minutes=31)) is None
    for _ in range(20):
        sicherung.fehlschlag_merken(t0)  # die Frist hat eine Obergrenze (8 Stunden)
    assert sicherung.gesperrt_bis(t0 + timedelta(minutes=479)) is not None
    assert sicherung.gesperrt_bis(t0 + timedelta(minutes=481)) is None


def test_ein_erfolg_loescht_die_wartezeit(db):
    sicherung.fehlschlag_merken(datetime.now())
    assert sicherung.gesperrt_bis() is not None
    sicherung.erfolg_merken()
    assert sicherung.gesperrt_bis() is None


def _warten_bis_fertig(timeout=20):
    ende = time.time() + timeout
    while sicherung._LAUF.locked() and time.time() < ende:
        time.sleep(0.05)
    assert not sicherung._LAUF.locked(), "die Sicherung hängt"


def _jobs(db):
    return db.connect().execute(
        "SELECT COUNT(*) FROM background_jobs WHERE job_type='sicherung'").fetchone()[0]


def test_vier_takte_nach_einem_fehlschlag_starten_nur_einen_versuch(db, monkeypatch):
    """Das gemessene Verhalten: vier Takte ergaben vier Jobs und keine Sicherung."""
    monkeypatch.setattr(sicherung, "sichern",
                        lambda db_, anlass="manuell", **kw: {"status": "fehler", "fehler": "gesperrt"})
    from bewerbungs_assistent.services import automatik_scheduler
    for _ in range(4):
        automatik_scheduler._tick(db)
        _warten_bis_fertig()
    assert _jobs(db) == 1
    assert sicherung.taeglich(db)["status"] == "wartet_nach_fehler"


def test_ein_gelungener_lauf_loescht_die_wartezeit(db):
    """Die Verdrahtung: nach einem Fehlschlag und einem Erfolg wartet nichts mehr."""
    sicherung.fehlschlag_merken(datetime.now() - timedelta(hours=9))
    assert sicherung.gesperrt_bis() is None  # die Frist ist um, der Zaehler steht noch
    assert sicherung._FEHL["anzahl"] == 1
    assert sicherung.im_hintergrund(db, "manuell")["status"] == "gestartet"
    _warten_bis_fertig()
    assert sicherung._FEHL["anzahl"] == 0


def test_nach_der_wartezeit_versucht_die_automatik_es_wieder(db, monkeypatch):
    sicherung.fehlschlag_merken(datetime.now() - timedelta(minutes=20))
    gestartet = []
    monkeypatch.setattr(sicherung, "im_hintergrund",
                        lambda db_, anlass="taeglich": gestartet.append(anlass) or {"status": "gestartet"})
    assert sicherung.taeglich(db)["status"] == "gestartet"
    assert gestartet == ["taeglich"]


# ══ Der Ausgang ist zu sehen ═══════════════════════════════════════

def test_ein_fehlschlag_steht_im_letzten_versuch(db):
    jid = db.create_background_job("sicherung", {"anlass": "manuell"})
    db.update_background_job(jid, "fehler", progress=100, message="Datei X ist gesperrt")
    v = sicherung.letzter_versuch(db)
    assert v["status"] == "fehler" and v["nachricht"] == "Datei X ist gesperrt"
    assert v["aktuell"] is True and v["anlass"] == "manuell"


def test_ein_laufender_versuch_meldet_laeuft(db):
    db.create_background_job("sicherung", {"anlass": "taeglich"})
    assert sicherung.letzter_versuch(db)["status"] == "laeuft"


def test_eine_neuere_sicherung_ueberholt_den_alten_fehler(db):
    jid = db.create_background_job("sicherung", {"anlass": "manuell"})
    db.update_background_job(jid, "fehler", progress=100, message="alt")
    time.sleep(1.2)  # die Sicherung benennt sich auf die Sekunde
    assert sicherung.sichern(db, "manuell")["status"] == "gesichert"
    assert sicherung.letzter_versuch(db)["aktuell"] is False


def test_ohne_versuch_gibt_es_nichts_zu_melden(db):
    assert sicherung.letzter_versuch(db) is None


def test_die_antwort_der_karte_traegt_den_letzten_versuch(db, monkeypatch):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    monkeypatch.setattr(dash, "_db", db)
    jid = db.create_background_job("sicherung", {"anlass": "manuell"})
    db.update_background_job(jid, "fehler", progress=100, message="Platte voll")
    antwort = TestClient(dash.app).get("/api/sicherungen").json()
    assert antwort["letzter_versuch"]["status"] == "fehler"
    assert antwort["letzter_versuch"]["nachricht"] == "Platte voll"


# ══ Die Oberfläche ═════════════════════════════════════════════════

FRONTEND = ROOT / "frontend" / "src"


def test_die_karte_fragt_den_ausgang_ab_und_zeigt_ihn():
    karte = (FRONTEND / "components" / "SicherungKarte.jsx").read_text(encoding="utf-8-sig")
    # die Karte zeigt den Ausgang des letzten Versuchs (nicht nur im Hinweis nach dem Klick)
    assert "versuchText(stand.letzter_versuch)" in karte and "ergebnisAbwarten" in karte
    assert 'data-testid="sicherung-versuch"' in karte


def test_ein_abruffehler_gilt_nicht_als_keine_sicherung():
    karte = (FRONTEND / "components" / "SicherungKarte.jsx").read_text(encoding="utf-8-sig")
    # der alte catch-Zweig setzte eine leere Liste und damit "Noch keine Sicherung vorhanden"
    assert "setStand({ sicherungen: [], letzte: null, alter_tage: null });" not in karte
    assert 'data-testid="sicherung-ladefehler"' in karte


# ══ Die Dokumente in der täglichen Sicherung (#1138) ═══════════════
# Seit der Planer auch über Claude Desktop läuft, sichert PBP wirklich täglich.
# Bei großen Dokumentenordnern wären das bis zu zwölf ZIP-Stände: wer Platz
# sparen will, nimmt die Dokumente heraus; die Datenbank bleibt immer drin.

def test_vorgabe_ist_mit_dokumenten(db):
    assert sicherung.dokumente_taeglich(db) is True


def test_ohne_dokumente_enthaelt_die_taegliche_sicherung_nur_die_datenbank(db):
    sicherung.dokumente_taeglich_setzen(db, False)
    assert sicherung.dokumente_taeglich(db) is False
    assert sicherung.im_hintergrund(db, "taeglich")["status"] == "gestartet"
    _warten_bis_fertig()
    ordner = sicherung.ordner(db)
    assert len(list(ordner.glob("pbp-backup-*-taeglich.db"))) == 1
    assert list(ordner.glob("*-dokumente.zip")) == []
    assert sicherung.liste(db)[0]["dokumente"] is False


def test_eine_selbst_angelegte_sicherung_enthaelt_die_dokumente_immer(db):
    sicherung.dokumente_taeglich_setzen(db, False)
    assert sicherung.im_hintergrund(db, "manuell")["status"] == "gestartet"
    _warten_bis_fertig()
    assert sicherung.liste(db)[0]["dokumente"] is True


def test_wieder_einschalten_bringt_die_dokumente_zurueck(db):
    sicherung.dokumente_taeglich_setzen(db, False)
    sicherung.dokumente_taeglich_setzen(db, True)
    assert sicherung.im_hintergrund(db, "taeglich")["status"] == "gestartet"
    _warten_bis_fertig()
    assert sicherung.liste(db)[0]["dokumente"] is True


def test_die_karte_meldet_einstellung_und_groesse_und_nimmt_eine_aenderung_an(db, monkeypatch):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    monkeypatch.setattr(dash, "_db", db)
    tc = TestClient(dash.app)
    antwort = tc.get("/api/sicherungen").json()
    assert antwort["dokumente_taeglich"] is True and antwort["dokumente_groesse"] >= 6144
    r = tc.put("/api/sicherungen/einstellung", json={"dokumente_taeglich": False})
    assert r.status_code == 200 and r.json() == {"dokumente_taeglich": False}
    assert tc.get("/api/sicherungen").json()["dokumente_taeglich"] is False
    # ungueltige Eingaben aendern nichts
    assert tc.put("/api/sicherungen/einstellung", json={"dokumente_taeglich": "nein"}).status_code == 400
    assert tc.put("/api/sicherungen/einstellung", json={}).status_code == 400
    assert tc.get("/api/sicherungen").json()["dokumente_taeglich"] is False


def test_die_karte_hat_den_schalter():
    karte = (FRONTEND / "components" / "SicherungKarte.jsx").read_text(encoding="utf-8-sig")
    assert 'data-testid="sicherung-dokumente-schalter"' in karte
    assert "onChange={(e) => dokumenteUmstellen(e.target.checked)}" in karte
    assert "/api/sicherungen/einstellung" in karte
