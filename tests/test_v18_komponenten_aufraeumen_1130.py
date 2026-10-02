"""Tests fuer #1130 -- der Komponenten-Installer raeumt nach Fehlern auf.

Vorher blieb die heruntergeladene Setup-Datei (rund 55 MB) nach jedem Fehler
liegen, waehrend das Protokoll "Download verworfen" sagte: bei falscher
Pruefsumme (A), abgebrochenem Download (B) und scheiterndem Installer (C).

Alles ohne Netz und ohne echten Installer. Der Installationsordner ist wie
BA_DATA_DIR umgelenkt; JEDER Test prueft das mit einer Zusicherung, bevor er
etwas anlegt (QA-Isolation).
"""
from __future__ import annotations

import hashlib
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

GROESSE = 2 * 1024 * 1024  # der echte Installer hat rund 55 MB; 2 MB genuegen


@pytest.fixture
def tmp_db(tmp_path):
    from bewerbungs_assistent.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db
    db.close()


@pytest.fixture
def umgebung(tmp_db, tmp_path, monkeypatch):
    """Komponenten-Ordner im Temp-Verzeichnis, Windows-Zweig, kein Netz."""
    from bewerbungs_assistent.services import components
    ordner = tmp_path / "components"
    monkeypatch.setattr(components, "components_dir", lambda: ordner)
    assert str(tmp_path) in str(components.components_dir()), \
        "Komponenten-Ordner nicht isoliert"
    monkeypatch.setattr(components, "find_component_binary", lambda db, name: None)
    monkeypatch.setattr(components.sys, "platform", "win32")

    def kein_echter_installer(*a, **kw):
        raise AssertionError("Im Test darf kein echter Installer laufen")

    monkeypatch.setattr(components.subprocess, "run", kein_echter_installer)
    # Das Loeschen wiederholt sich kurz (Virenscanner); im Test ohne Warten.
    monkeypatch.setattr(components, "time", SimpleNamespace(sleep=lambda s: None))
    download = dict(components.COMPONENT_DEFS["tesseract"]["windows_download"])
    # #1152: ohne Pruefsumme laedt PBP nichts. Das Testdoppel liefert GROESSE mal "x" und kennt die passende Summe.
    download["sha256"] = hashlib.sha256(b"x" * GROESSE).hexdigest()
    monkeypatch.setitem(components.COMPONENT_DEFS["tesseract"],
                        "windows_download", download)
    return SimpleNamespace(db=tmp_db, ordner=ordner, c=components,
                           download=download)


def _reste(ordner: Path) -> list[str]:
    """Alle Dateien unter dem Komponenten-Ordner, relativ und sortiert."""
    if not ordner.exists():
        return []
    return sorted(p.relative_to(ordner).as_posix()
                  for p in ordner.rglob("*") if p.is_file())


def _download_schreibt(groesse=GROESSE):
    """Testdoppel fuer _download: legt die Datei unter dem Zielnamen an."""
    def _dl(url, target, progress, lo=0, hi=80):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x" * groesse)
    return _dl


class _Antwort:
    """Stand-in fuer die urlopen-Antwort: Stuecke, dann Ende oder Abbruch."""

    def __init__(self, stuecke, laenge, abbruch=None):
        self.headers = {"Content-Length": str(laenge)}
        self._stuecke = list(stuecke)
        self._abbruch = abbruch

    def read(self, n=-1):
        if self._stuecke:
            return self._stuecke.pop(0)
        if self._abbruch:
            raise self._abbruch
        return b""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _urlopen_liefert(monkeypatch, components, antwort):
    monkeypatch.setattr(components.urllib.request, "urlopen",
                        lambda req, timeout=0: antwort)


# -- Fall A: Pruefsumme stimmt nicht ----------------------------------

def test_fall_a_pruefsumme_falsch_nichts_bleibt_liegen(umgebung, monkeypatch):
    c = umgebung.c
    monkeypatch.setattr(c, "_download", _download_schreibt())
    umgebung.download["sha256"] = "0" * 64
    ergebnis = c.install_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "fehler"
    assert "verworfen" in ergebnis["fehler"]
    assert _reste(umgebung.ordner) == []


def test_fall_a_wortlaut_verworfen_nur_wenn_die_datei_wirklich_weg_ist(
        umgebung, monkeypatch):
    """Das Protokoll sagte 'verworfen' und die Datei blieb. Kann die Datei
    nicht geloescht werden, sagt die Meldung das -- und nicht 'verworfen'."""
    c = umgebung.c
    monkeypatch.setattr(c, "_download", _download_schreibt())
    umgebung.download["sha256"] = "0" * 64
    echtes_unlink = Path.unlink

    def gesperrt(self, missing_ok=False):
        if self.name.endswith("-setup.exe"):
            raise PermissionError("vom Virenscanner gehalten")
        return echtes_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", gesperrt)
    ergebnis = c.install_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "fehler"
    assert "verworfen" not in ergebnis["fehler"]
    assert "nicht löschen" in ergebnis["fehler"]
    # Die Datei liegt noch -- und die Meldung hat es gesagt.
    assert _reste(umgebung.ordner) == ["tesseract-setup.exe"]


# -- Fall B: der Download bricht ab -----------------------------------

def test_fall_b_download_bricht_ab_keine_teildatei(umgebung, monkeypatch):
    c = umgebung.c
    _urlopen_liefert(monkeypatch, c, _Antwort(
        [b"x" * 488_000], GROESSE, abbruch=ConnectionResetError("Netz weg")))
    ergebnis = c.install_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "fehler"
    assert _reste(umgebung.ordner) == []


def test_fall_b_abgeschnittener_download_gilt_nicht_als_fertig(
        umgebung, monkeypatch):
    """http.client meldet eine zu kurze Antwort nicht als Fehler. Ohne die
    Laengenpruefung waere sie 'fertig' -- bei Sprachdaten ohne Pruefsumme
    bliebe eine kaputte Datei stehen."""
    c = umgebung.c
    _urlopen_liefert(monkeypatch, c, _Antwort([b"x" * 400_000], GROESSE))
    ergebnis = c.install_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "fehler"
    assert "unvollständig" in ergebnis["fehler"]
    assert _reste(umgebung.ordner) == []


# -- Fall C: der Installer endet mit einem Fehler ---------------------

def test_fall_c_installer_scheitert_nichts_bleibt_liegen(umgebung, monkeypatch):
    c = umgebung.c
    monkeypatch.setattr(c, "_download", _download_schreibt())
    monkeypatch.setattr(c.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        returncode=2, stdout="", stderr="kaputt"))
    ergebnis = c.install_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "fehler"
    assert "Exit-Code 2" in ergebnis["fehler"]
    assert _reste(umgebung.ordner) == []


def test_installer_meldet_erfolg_aber_das_programm_fehlt(umgebung, monkeypatch):
    """Vierter Ausgang: Exit-Code 0, doch das Binary liegt nicht da."""
    c = umgebung.c
    monkeypatch.setattr(c, "_download", _download_schreibt())
    monkeypatch.setattr(c.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        returncode=0, stdout="", stderr=""))
    ergebnis = c.install_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "fehler"
    assert "nicht gefunden" in ergebnis["fehler"]
    assert _reste(umgebung.ordner) == []


def test_erfolg_raeumt_die_setup_datei_ebenfalls_auf(umgebung, monkeypatch):
    """Der Erfolgsweg loeschte schon vorher; er soll es weiter tun -- jetzt
    ueber dieselbe Stelle wie alle Fehlerwege."""
    c = umgebung.c
    binary_name = c.COMPONENT_DEFS["tesseract"]["binary_name"]
    monkeypatch.setattr(c, "_download", _download_schreibt())

    def installer(argv, **kw):
        ziel = Path(argv[2][len("/D="):])
        (ziel / binary_name).write_text("x")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(c.subprocess, "run", installer)
    monkeypatch.setattr(c, "_binary_version", lambda b: "5.4.0")
    ergebnis = c.install_component(umgebung.db, "tesseract")
    assert ergebnis["status"] == "installiert"
    assert _reste(umgebung.ordner) == [f"tesseract/{binary_name}"]


# -- Reste frueherer Laeufe -------------------------------------------

def _rest_anlegen(ordner: Path, rel: str, groesse: int = 1000) -> Path:
    p = ordner / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * groesse)
    return p


def test_reste_frueherer_laeufe_werden_entfernt_fremdes_bleibt(umgebung):
    o = umgebung.ordner
    _rest_anlegen(o, "tesseract-setup.exe", GROESSE)
    _rest_anlegen(o, "tesseract-setup.exe.part", 1000)
    _rest_anlegen(o, "tessdata/deu.traineddata.part", 1000)
    _rest_anlegen(o, "tesseract/tessdata/deu.traineddata.part", 1000)
    # Nichts davon ist ein Rest: fertige Installation, fertige Sprachen,
    # eine fremde Datei im Ordner.
    _rest_anlegen(o, "tesseract/tesseract.exe")
    _rest_anlegen(o, "tesseract/tessdata/eng.traineddata")
    _rest_anlegen(o, "tessdata/eng.traineddata")
    _rest_anlegen(o, "notizen.txt")
    ergebnis = umgebung.c.setup_reste_entfernen(umgebung.db)
    assert ergebnis["entfernt"] == 4
    assert ergebnis["bytes"] == GROESSE + 3000
    assert _reste(o) == ["notizen.txt", "tessdata/eng.traineddata",
                         "tesseract/tessdata/eng.traineddata",
                         "tesseract/tesseract.exe"]


def test_ohne_komponenten_ordner_passiert_nichts(umgebung):
    assert not umgebung.ordner.exists()
    ergebnis = umgebung.c.setup_reste_entfernen(umgebung.db)
    assert ergebnis["entfernt"] == 0
    assert not umgebung.ordner.exists()  # das Aufraeumen legt nichts an


def test_reste_werden_vor_dem_naechsten_versuch_entfernt(umgebung, monkeypatch):
    """start_install_job raeumt, BEVOR der neue Lauf beginnt: das Testdoppel
    des Installers sieht den Rest schon nicht mehr."""
    c = umgebung.c
    rest = _rest_anlegen(umgebung.ordner, "tesseract-setup.exe", GROESSE)
    gesehen = []

    def install(db, name, progress=None):
        gesehen.append(rest.exists())
        return {"status": "installiert"}

    monkeypatch.setattr(c, "install_component", install)
    monkeypatch.setattr(c, "ensure_language",
                        lambda db, lang="deu", progress=None: {"status": "vorhanden"})
    job = c.start_install_job(umgebung.db, "tesseract")
    assert job["status"] == "gestartet"
    _warte_auf_job(umgebung.db, job["job_id"])
    assert gesehen == [False]


def _warte_auf_job(db, job_id):
    import time
    for _ in range(200):  # hoechstens rund 10 s
        job = db.get_background_job(job_id)
        if job and job.get("status") in ("fertig", "fehler"):
            return job
        time.sleep(0.05)
    pytest.fail("Install-Job wurde nicht fertig -- der Thread wuerde ins Teardown racen")


# -- Eine laufende Installation wird nie gestoert ---------------------

def test_laufende_installation_wird_nie_gestoert(umgebung, monkeypatch):
    c = umgebung.c
    gate = threading.Event()

    def haengt(db, name, progress=None):
        gate.wait(timeout=5)
        return {"status": "installiert"}

    monkeypatch.setattr(c, "install_component", haengt)
    monkeypatch.setattr(c, "ensure_language",
                        lambda db, lang="deu", progress=None: {"status": "vorhanden"})
    erster = c.start_install_job(umgebung.db, "tesseract")
    assert erster["status"] == "gestartet"
    try:
        # Waehrend der Lauf haengt, liegt seine Datei im Ordner.
        laufend = _rest_anlegen(umgebung.ordner, "tesseract-setup.exe", GROESSE)
        teil = _rest_anlegen(umgebung.ordner, "tesseract-setup.exe.part")
        ergebnis = c.setup_reste_entfernen(umgebung.db)
        assert ergebnis.get("uebersprungen") == "installation_laeuft"
        assert ergebnis["entfernt"] == 0
        # Auch ein zweiter Startversuch raeumt nichts ab: er wird abgewiesen,
        # BEVOR das Aufraeumen ueberhaupt laeuft.
        zweiter = c.start_install_job(umgebung.db, "tesseract")
        assert zweiter["status"] == "laeuft_bereits"
        assert laufend.exists() and teil.exists()
    finally:
        gate.set()
    _warte_auf_job(umgebung.db, erster["job_id"])


def test_abgestuerzter_lauf_blockiert_das_aufraeumen_nicht(umgebung):
    """Ein Job, der seit Stunden nichts meldet, ist tot (#1118). Sonst
    bliebe der Rest nach einem Absturz fuer immer liegen."""
    db = umgebung.db
    jid = db.create_background_job("komponente_install", {"name": "tesseract"})
    alt = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    conn = db.connect()
    conn.execute("UPDATE background_jobs SET created_at=?, updated_at=? WHERE id=?",
                 (alt, alt, jid))
    conn.commit()
    rest = _rest_anlegen(umgebung.ordner, "tesseract-setup.exe", GROESSE)
    ergebnis = umgebung.c.setup_reste_entfernen(db)
    assert ergebnis["entfernt"] == 1
    assert not rest.exists()


def test_frischer_lauf_zaehlt_als_laufend(umgebung):
    """Die Gegenseite: derselbe Job, eben erst angelegt, wird respektiert."""
    umgebung.db.create_background_job("komponente_install", {"name": "tesseract"})
    rest = _rest_anlegen(umgebung.ordner, "tesseract-setup.exe", GROESSE)
    ergebnis = umgebung.c.setup_reste_entfernen(umgebung.db)
    assert ergebnis.get("uebersprungen") == "installation_laeuft"
    assert rest.exists()


def test_aufraeumen_wirft_nie(umgebung, monkeypatch):
    """Die beiden Startwege und start_install_job rufen es ohne Schutz."""
    def kaputt():
        raise RuntimeError("Ordner nicht ermittelbar")

    monkeypatch.setattr(umgebung.c, "components_dir", kaputt)
    ergebnis = umgebung.c.setup_reste_entfernen(umgebung.db)
    assert ergebnis["entfernt"] == 0


def test_im_zweifel_wird_nichts_geloescht(umgebung):
    """Laesst sich nicht feststellen, ob etwas laeuft, bleibt alles liegen."""
    class KaputteDB:
        def get_running_background_job(self, *a, **kw):
            raise RuntimeError("Datenbank nicht erreichbar")

    rest = _rest_anlegen(umgebung.ordner, "tesseract-setup.exe", GROESSE)
    ergebnis = umgebung.c.setup_reste_entfernen(KaputteDB())
    assert ergebnis["entfernt"] == 0
    assert rest.exists()


# -- _download: eine Datei mit dem endgueltigen Namen ist immer ganz --

def test_download_vollstaendig_liefert_die_datei_ohne_teildatei(
        umgebung, monkeypatch):
    c = umgebung.c
    _urlopen_liefert(monkeypatch, c, _Antwort([b"x" * 1000, b"y" * 500], 1500))
    ziel = umgebung.ordner / "tesseract-setup.exe"
    c._download("https://example.invalid/x", ziel, lambda pct, msg: None)
    assert ziel.read_bytes() == b"x" * 1000 + b"y" * 500
    assert _reste(umgebung.ordner) == ["tesseract-setup.exe"]


def test_abgebrochene_sprachdaten_hinterlassen_keine_datei(umgebung, monkeypatch):
    """Eine angefangene deu.traineddata waere fuer available_languages und
    _ocr_env (setzt TESSDATA_PREFIX, sobald dort eine .traineddata liegt)
    nicht von einer ganzen zu unterscheiden."""
    c = umgebung.c
    monkeypatch.setattr(c, "available_languages", lambda db: [])
    monkeypatch.setattr(c, "_install_tessdata_dir", lambda db: None)
    _urlopen_liefert(monkeypatch, c, _Antwort(
        [b"x" * 1000], GROESSE, abbruch=ConnectionResetError("Netz weg")))
    ergebnis = c.ensure_language(umgebung.db, "deu")
    assert ergebnis["status"] == "fehler"
    assert _reste(umgebung.ordner) == []
    assert not list(umgebung.ordner.rglob("*.traineddata*"))


# -- _entfernen: wiederholt kurz, wirft nie ---------------------------

def test_entfernen_versucht_es_mehrfach_und_meldet_ehrlich(tmp_path, monkeypatch):
    from bewerbungs_assistent.services import components as c
    monkeypatch.setattr(c, "time", SimpleNamespace(sleep=lambda s: None))
    datei = tmp_path / "x-setup.exe"
    datei.write_bytes(b"x")
    echtes_unlink = Path.unlink
    aufrufe = []

    def zweimal_gesperrt(self, missing_ok=False):
        aufrufe.append(1)
        if len(aufrufe) < 3:
            raise PermissionError("gesperrt")
        return echtes_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", zweimal_gesperrt)
    assert c._entfernen(datei) is True
    assert len(aufrufe) == 3 and not datei.exists()

    def immer_gesperrt(self, missing_ok=False):
        raise PermissionError("gesperrt")

    monkeypatch.setattr(Path, "unlink", immer_gesperrt)
    assert c._entfernen(tmp_path / "y-setup.exe") is False  # wirft nicht


def test_entfernen_einer_fehlenden_datei_ist_kein_fehler(tmp_path):
    from bewerbungs_assistent.services import components as c
    assert c._entfernen(tmp_path / "gibt-es-nicht.exe") is True


# -- Die Testsuite fasst den echten Komponenten-Ordner nicht an -------

def test_suite_lenkt_den_komponenten_ordner_um(tmp_path_factory):
    """tests/conftest.py setzt den Ordner fuer JEDEN Test auf eine Sandbox.
    Ohne das griffe start_install_job in einem Test, der BA_DATA_DIR nicht
    setzt, in den echten Installationsordner des Entwicklers."""
    from bewerbungs_assistent.services import components
    assert str(tmp_path_factory.getbasetemp()) in str(components.components_dir())


# -- Beide Startwege raeumen auf (ein Schutz zaehlt erst, wenn er laeuft)

def _ohne_kommentare(text: str) -> str:
    return "\n".join(z for z in text.splitlines() if not z.strip().startswith("#"))


def _quelle(name: str) -> str:
    basis = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
    return (basis / name).read_text(encoding="utf-8-sig")


def test_beide_startwege_rufen_das_aufraeumen():
    """Wer PBP ueber Claude Desktop startet, oeffnet das Dashboard oft nie
    (Muster aus #1001). Darum raeumt der MCP-Weg UND der Dashboard-Weg."""
    server = _ohne_kommentare(_quelle("server.py"))
    assert "setup_reste_entfernen(db)" in server
    dash = _quelle("dashboard.py")
    rumpf = _ohne_kommentare(dash[dash.index("def start_dashboard("):])
    assert "setup_reste_entfernen(db_instance)" in rumpf
    # nach der Bereinigung toter Jobs, damit ein abgestuerzter Lauf nicht blockiert
    assert rumpf.index("_cleanup_stale_jobs(db_instance)") < \
        rumpf.index("setup_reste_entfernen(db_instance)")


def test_start_install_job_ruft_das_aufraeumen_vor_dem_neuen_job():
    quelle = _ohne_kommentare(_quelle("services/components.py"))
    rumpf = quelle[quelle.index("def start_install_job("):]
    rumpf = rumpf[:rumpf.index("\ndef ")]
    assert rumpf.index("setup_reste_entfernen(db)") < \
        rumpf.index("create_background_job(")
