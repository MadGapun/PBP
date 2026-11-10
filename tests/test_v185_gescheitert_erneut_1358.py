"""v1.8.5 — Auto-Update: eine gescheiterte Fassung ehrlich melden und erneut versuchen lassen (#1358).

Bis 1.8.4 sagte PBP „wird nicht noch einmal automatisch installiert" und gab dem Update die Schuld, auch wenn der
Start an etwas auf dem Rechner scheiterte (gesperrte Datenbank, volle Platte). Der Knopf „Erneut versuchen" lief
ins Leere, denn `_vorbedingungen` lehnte jede Fassung aus der Liste `gescheitert` ab. Jetzt hebt die AUSDRUECKLICHE
Installation (Klick, Werkzeug mit `bestaetigt=True`) den Eintrag auf; die Automatik tut es nie.

Der Startbaustein bleibt unveraendert (FORMAT = 1).
"""
import hashlib
import json
import logging
import os
from pathlib import Path

import pytest
from _au_hilfen import eintrag, liste, programmordner

import bewerbungs_assistent_boot as boot
from bewerbungs_assistent.services.auto_update import fehler, installation, lauf, layout, quelle, zustand

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _sauber():
    lauf._PRUEFUNG.update(zeit=0.0, ergebnis=None)
    lauf._JOB.update(id=None, status=None, phase="", anteil=0.0, text="", version=None, ausloeser="")
    yield
    lauf._PRUEFUNG.update(zeit=0.0, ergebnis=None)


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


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Programmordner: 1.8.0 laeuft, 1.8.1 ist zurueckgenommen worden und steht unter `gescheitert`."""
    pfad = programmordner(tmp_path / "pc", fassungen=("1.8.0",), status={"gescheitert": ["1.8.1", "1.8.9"]})
    monkeypatch.setenv("PBP_APP_DIR", str(pfad))
    monkeypatch.setenv("PBP_FASSUNG", "1.8.0")
    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: True)
    monkeypatch.setattr(quelle, "standard_oeffner", lambda: liste(eintrag("v1.8.1")))
    return pfad


class _Ergebnis:
    ok, code, text, sha256, signiert, schluessel = True, "", "fertig", "", False, ""
    neustart_noetig, schon_vorhanden, aufgeraeumt = True, False, {}

    def __init__(self, version):
        self.version = version


def _fake_installieren(aufrufe):
    def run(version, **kw):
        aufrufe.append((version, kw.get("ausloeser")))
        return _Ergebnis(version)
    return run


# ── der Text ────────────────────────────────────────────────────────

def test_der_text_beschuldigt_das_update_nicht_allein():
    t = fehler.TEXTE["gescheitert"]
    assert "am Update liegen oder an etwas auf deinem Rechner" in t
    assert "gesperrten Datenbank" in t and "Einstellungen › Updates" in t
    assert "wird nicht noch einmal automatisch installiert" not in t


def test_die_rueckfrage_nennt_beide_moegliche_ursachen_und_den_rueckweg():
    f = fehler.ERNEUT_VERSUCHEN_FRAGE
    assert "am Update liegen oder an etwas auf deinem Rechner" in f
    assert "bisherigen Version weiter" in f and "Daten bleiben erhalten" in f


def test_dashboard_und_server_fragen_mit_demselben_text():
    """Eine Frage, eine Antwort: die Rueckfrage im Dashboard ist die des Servers (Werkzeug)."""
    js = (ROOT / "frontend" / "src" / "lib" / "autoUpdate.js").read_text(encoding="utf-8")
    teil = js[js.index("export const ERNEUT_VERSUCHEN_TEXT"):]
    teil = teil[:teil.index('erhalten."') + len('erhalten."')]
    import re
    text = "".join(re.findall(r'"([^"]*)"', teil))
    assert text == fehler.ERNEUT_VERSUCHEN_FRAGE


# ── Freigeben ───────────────────────────────────────────────────────

def test_freigeben_nimmt_nur_die_genannte_fassung_aus_der_liste(app):
    assert zustand.gescheitert_freigeben("1.8.1") is True
    assert zustand.gescheiterte_fassungen() == ["1.8.9"]
    assert zustand.gescheitert_freigeben("1.8.1") is False       # steht nicht mehr da
    assert zustand.gescheitert_freigeben("2.0.0") is False


def test_freigeben_ohne_programmordner_tut_nichts(monkeypatch):
    monkeypatch.delenv("PBP_APP_DIR", raising=False)
    monkeypatch.setattr(layout, "programmordner", lambda: None)
    assert zustand.gescheitert_freigeben("1.8.1") is False


def test_eine_gescheiterte_fassung_wird_ohne_freigabe_abgelehnt_und_danach_nicht_mehr(app):
    with pytest.raises(fehler.UpdateFehler) as e:
        installation._vorbedingungen("1.8.1", app, "1.8.0")
    assert e.value.code == "gescheitert"
    zustand.gescheitert_freigeben("1.8.1")
    assert installation._vorbedingungen("1.8.1", app, "1.8.0") == "1.8.0"


# ── Wer darf freigeben: nur der Mensch ─────────────────────────────

@pytest.mark.parametrize("ausloeser", ["klick", "mcp"])
def test_die_ausdrueckliche_installation_hebt_den_eintrag_auf(db, app, ausloeser):
    aufrufe = []
    r = lauf.starte_installation(db, "1.8.1", ausloeser=ausloeser, installieren=_fake_installieren(aufrufe), synchron=True)
    assert r["status"] == "gestartet" and aufrufe == [("1.8.1", ausloeser)]
    assert zustand.gescheiterte_fassungen() == ["1.8.9"]


def test_die_automatik_hebt_nie_etwas_auf(db, app):
    lauf.starte_installation(db, "1.8.1", ausloeser="automatisch", installieren=_fake_installieren([]), synchron=True)
    assert "1.8.1" in zustand.gescheiterte_fassungen()


def test_die_echte_installation_lehnt_eine_gescheiterte_fassung_fuer_die_automatik_ab(db, app):
    """Ohne Austausch der Installation: die Automatik kommt an `gescheitert` nicht vorbei."""
    lauf.starte_installation(db, "1.8.1", ausloeser="automatisch", synchron=True)
    assert "1.8.1" in zustand.gescheiterte_fassungen()
    b = lauf.blockiert(db, "1.8.1")
    assert b and b["code"] == "gescheitert" and b["dauerhaft"] is True


# ── Die Anzeige und das Werkzeug ───────────────────────────────────

def test_die_uebersicht_nennt_die_gescheiterte_fassung(db, app):
    lauf.pruefen(db, frisch=True)
    u = lauf.uebersicht(db)
    assert u["gescheitert"] == ["1.8.1", "1.8.9"]
    assert u["neu"]["version"] == "1.8.1" and u["neu"]["gescheitert"] is True
    zustand.gescheitert_freigeben("1.8.1")
    assert lauf.uebersicht(db)["neu"]["gescheitert"] is False


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *a, **kw):
        def deko(fn):
            self.tools[fn.__name__] = fn
            return fn
        return deko


@pytest.fixture
def werkzeuge(db):
    from bewerbungs_assistent.tools import update
    mcp = _FakeMCP()
    update.register(mcp, db, logging.getLogger("test"))
    return mcp.tools


def test_das_werkzeug_fragt_vor_dem_erneuten_versuch_mit_dem_grund(werkzeuge, db, app):
    lauf.pruefen(db, frisch=True)
    r = werkzeuge["update_jetzt_installieren"]()
    assert r["status"] == "bestaetigung_noetig"
    assert "schon einmal gescheitert" in r["text"] and "am Update liegen oder an etwas auf deinem Rechner" in r["text"]
    assert "1.8.1" in zustand.gescheiterte_fassungen(), "die Vorschau darf nichts aendern"


def test_das_werkzeug_fragt_ohne_gescheiterte_fassung_wie_bisher(werkzeuge, db, tmp_path, monkeypatch):
    pfad = programmordner(tmp_path / "sauber", fassungen=("1.8.0",))
    monkeypatch.setenv("PBP_APP_DIR", str(pfad))
    monkeypatch.setenv("PBP_FASSUNG", "1.8.0")
    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: True)
    monkeypatch.setattr(quelle, "standard_oeffner", lambda: liste(eintrag("v1.8.1")))
    r = werkzeuge["update_jetzt_installieren"]()
    assert r["status"] == "bestaetigung_noetig" and "gescheitert" not in r["text"]


def test_das_werkzeug_hebt_nur_mit_bestaetigung_auf(werkzeuge, db, app, monkeypatch):
    aufrufe = []
    echt = lauf.starte_installation
    monkeypatch.setattr(lauf, "starte_installation", lambda d, v, **kw: echt(
        d, v, installieren=_fake_installieren(aufrufe), synchron=True, **kw))
    werkzeuge["update_jetzt_installieren"](version="1.8.1")
    assert aufrufe == [] and "1.8.1" in zustand.gescheiterte_fassungen()
    r = werkzeuge["update_jetzt_installieren"](version="1.8.1", bestaetigt=True)
    assert r["status"] == "gestartet" and aufrufe == [("1.8.1", "mcp")]
    assert "1.8.1" not in zustand.gescheiterte_fassungen()


def test_das_dashboard_hebt_beim_klick_auf(db, app, monkeypatch):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    dash._db = db
    echt = lauf.starte_installation
    aufrufe = []
    monkeypatch.setattr(lauf, "starte_installation", lambda d, v, **kw: echt(
        d, v, installieren=_fake_installieren(aufrufe), synchron=True, **kw))
    c = TestClient(dash.app)
    assert "1.8.1" in c.get("/api/auto-update").json()["gescheitert"]
    r = c.post("/api/auto-update/installieren", json={"version": "1.8.1"})
    assert r.status_code == 200 and aufrufe == [("1.8.1", "klick")]
    assert "1.8.1" not in r.json()["uebersicht"]["gescheitert"]


# ── Der Startbaustein bleibt, wie er ist ───────────────────────────

#: Aendert sich dieser Wert, hat jemand den Startbaustein angefasst. Das darf nie von selbst geschehen: jede Aenderung braucht ein
#: neues FORMAT, das Manifest-Feld `boot_format` und den Installer (CLAUDE.md, Auto-Update).
BOOT_SHA256 = "ad1413bd86567828f248a8155a9a705ed8dca294d633d1c9ad8b0a106c3942f8"


def test_der_startbaustein_ist_unveraendert():
    assert boot.FORMAT == 1
    h = hashlib.sha256()
    for name in ("__init__.py", "__main__.py"):
        h.update((ROOT / "src" / "bewerbungs_assistent_boot" / name).read_bytes().replace(b"\r\n", b"\n"))
    assert h.hexdigest() == BOOT_SHA256, "src/bewerbungs_assistent_boot/ wurde geaendert (FORMAT = 1 ist eingefroren)"


def test_freigeben_schreibt_die_statusdatei_im_format_des_startbausteins(app):
    zustand.gescheitert_freigeben("1.8.1")
    s = json.loads((app / "update_status.json").read_text(encoding="utf-8"))
    assert s["gescheitert"] == ["1.8.9"] and s.get("format") == boot.FORMAT
