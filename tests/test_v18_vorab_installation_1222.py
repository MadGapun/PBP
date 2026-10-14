"""#1222 (Funde der Pruefung, 14.10.2026): das Auto-Update fuer Vorabversionen (#1199) installiert, was es findet.

Befund: `auto_update_vorab` machte eine Vorabversion zum KANDIDATEN (die Pruefung meldete "neu"), aber die Installation kannte
nur stabile Fassungen - drei Sperren (`lauf.starte_installation`, `installation._vorbedingungen`, `manifest.lesen`). Auf einer
Vorab-Installation mit eingeschaltetem Schalter scheiterte "Jetzt installieren" mit "Vorabversionen werden nie automatisch
installiert". Der Test des Features pruefte nur die Auswahl, nie die Installation.

Hier: der ganze Lauf mit einem ECHTEN Archiv (`build_update_archive --vorabversion`), und jede Regel, die nicht installieren darf.
Das Netz ist ein Testdoppel, der Programmordner liegt unter `tmp_path`.
"""
import pytest
from _au_hilfen import FakeDb, FakeOeffner, programmordner, release_bauen

from bewerbungs_assistent.services.auto_update import installation, lauf, zustand


class _Selbsttest:
    def __init__(self):
        self.befehle = []

    def __call__(self, befehl, **kw):
        self.befehle.append(befehl)
        return type("L", (), {"returncode": 0, "stdout": "OK\n", "stderr": ""})()


def _verboten(*a, **kw):
    raise AssertionError("Dieser Test darf weder pip noch den echten Selbsttest starten.")


PAKETE = {"fastmcp": "3.5.0", "httpx": "0.28.1", "pypdf": "5.0.0"}


def _installiere(app, version, *, oeffner, laufend, db=None, **kw):
    kw.setdefault("selbsttest_runner", _Selbsttest())
    kw.setdefault("pip_runner", _verboten)
    kw.setdefault("version_von", PAKETE.get)
    return installation.installiere(version, app=app, db=db, oeffner=oeffner, laufende_fassung=laufend, **kw)


def _db(vorab: bool):
    db = FakeDb()
    zustand.vorab_setzen(db, vorab)
    return db


@pytest.fixture
def rc3(tmp_path):
    return programmordner(tmp_path / "pc", fassungen=("1.8.0-rc.3",))


@pytest.fixture
def rc4(tmp_path):
    return release_bauen(tmp_path / "rel", "1.8.0-rc.4", vorabversion=True)


def _aktuell(app):
    return (app / "aktuell.txt").read_text(encoding="utf-8").strip()


# ══ Der Weg, der bisher an der Installation scheiterte ═══════════════════════════════════════════════════

def test_mit_schalter_installiert_eine_vorab_installation_die_naechste_vorabversion(rc3, rc4):
    st = _Selbsttest()
    e = _installiere(rc3, "1.8.0-rc.4", oeffner=FakeOeffner(rc4.antworten()), laufend="1.8.0-rc.3", db=_db(True), selbsttest_runner=st)
    assert e.ok, (e.code, e.text)
    assert e.version == "1.8.0-rc.4" and e.neustart_noetig is True
    assert _aktuell(rc3) == "1.8.0-rc.4"
    ziel = rc3 / "versions" / "1.8.0-rc.4"
    assert (ziel / ".fertig").is_file() and (ziel / "manifest.json").is_file()
    assert len(st.befehle) == 1, "der Selbsttest der neuen Fassung lief"
    assert (rc3 / "versions" / "1.8.0-rc.3").is_dir(), "die bisherige Fassung bleibt als Rueckweg"


def test_die_pruefsumme_gilt_auch_fuer_eine_vorabversion(rc3, rc4):
    antworten = rc4.antworten()
    schluessel = next(k for k in antworten if k.endswith(".zip"))
    antworten[schluessel] = antworten[schluessel] + b"x"
    e = _installiere(rc3, "1.8.0-rc.4", oeffner=FakeOeffner(antworten), laufend="1.8.0-rc.3", db=_db(True))
    assert e.ok is False and _aktuell(rc3) == "1.8.0-rc.3", "ein veraendertes Archiv wird nie umgeschaltet"


# ══ Was nie installieren darf ═══════════════════════════════════════════════════════════════════════

def test_ohne_schalter_wird_keine_vorabversion_installiert(rc3, rc4):
    oeffner = FakeOeffner(rc4.antworten())
    e = _installiere(rc3, "1.8.0-rc.4", oeffner=oeffner, laufend="1.8.0-rc.3", db=_db(False))
    assert e.ok is False and e.code == "quelle_nicht_erlaubt"
    assert oeffner.aufrufe == [] and _aktuell(rc3) == "1.8.0-rc.3"


def test_ohne_datenbank_gilt_der_schalter_als_aus(rc3, rc4):
    oeffner = FakeOeffner(rc4.antworten())
    e = _installiere(rc3, "1.8.0-rc.4", oeffner=oeffner, laufend="1.8.0-rc.3", db=None)
    assert e.ok is False and e.code == "quelle_nicht_erlaubt" and oeffner.aufrufe == []


def test_eine_stabile_installation_wird_auch_mit_schalter_nie_auf_eine_vorabversion_gezogen(tmp_path, rc4):
    app = programmordner(tmp_path / "stabil", fassungen=("1.7.9",))
    oeffner = FakeOeffner(rc4.antworten())
    e = _installiere(app, "1.8.0-rc.4", oeffner=oeffner, laufend="1.7.9", db=_db(True))
    assert e.ok is False and e.code == "quelle_nicht_erlaubt" and oeffner.aufrufe == []
    assert _aktuell(app) == "1.7.9"


def test_mit_schalter_gibt_es_nie_einen_linienwechsel(tmp_path):
    app = programmordner(tmp_path / "pc", fassungen=("1.8.0-rc.3",))
    rel = release_bauen(tmp_path / "rel", "1.9.0-rc.1", vorabversion=True)
    oeffner = FakeOeffner(rel.antworten())
    e = _installiere(app, "1.9.0-rc.1", oeffner=oeffner, laufend="1.8.0-rc.3", db=_db(True))
    assert e.ok is False and e.code == "braucht_installer" and oeffner.aufrufe == []
    assert _aktuell(app) == "1.8.0-rc.3"


@pytest.mark.parametrize("version", ["../1.8.0-rc.4", "1.8.0-rc.4/../x", "1.8.0-preview.1", "v1.8.0-rc.4", "1.8", "1.8.0-rc", ""])
def test_eine_ungueltige_fassung_wird_auch_mit_schalter_nie_installiert(rc3, version):
    oeffner = FakeOeffner({})
    e = _installiere(rc3, version, oeffner=oeffner, laufend="1.8.0-rc.3", db=_db(True))
    assert e.ok is False and e.code == "quelle_nicht_erlaubt" and oeffner.aufrufe == []
    assert _aktuell(rc3) == "1.8.0-rc.3"


def test_eine_aeltere_oder_gleiche_vorabversion_wird_auch_mit_schalter_nie_installiert(tmp_path):
    app = programmordner(tmp_path / "pc", fassungen=("1.8.0-rc.3",))
    rel = release_bauen(tmp_path / "rel", "1.8.0-rc.2", vorabversion=True)
    e = _installiere(app, "1.8.0-rc.2", oeffner=FakeOeffner(rel.antworten()), laufend="1.8.0-rc.3", db=_db(True))
    assert e.ok is False and e.code == "schon_aktuell"


# ══ Der Start der Installation (Klick, Chat, Automatik) ═════════════════════════════════════════════

class _Db(FakeDb):
    """FakeDb plus die Hintergrund-Jobs, die `starte_installation` anlegt."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.jobs = []

    def create_background_job(self, typ, daten=None):
        self.jobs.append((typ, daten))
        return f"job-{len(self.jobs)}"

    def update_background_job(self, *a, **kw):
        return None


def _starten(db, version, laufend, **kw):
    aufrufe = []

    def fake(v, **kwargs):
        aufrufe.append(v)
        return installation.Ergebnis(ok=True, version=v, text="ok")

    lauf._JOB_SPERRE.acquire(blocking=False)
    lauf._JOB_SPERRE.release()
    erg = lauf.starte_installation(db, version, installieren=fake, synchron=True, laufende_fassung=laufend, **kw)
    return erg, aufrufe


def test_der_start_laesst_eine_vorabversion_mit_schalter_zu(tmp_path):
    db = _Db()
    zustand.vorab_setzen(db, True)
    erg, aufrufe = _starten(db, "1.8.0-rc.4", "1.8.0-rc.3")
    assert erg["status"] == "gestartet" and aufrufe == ["1.8.0-rc.4"], erg


def test_der_start_weist_eine_vorabversion_ohne_schalter_ab(tmp_path):
    db = _Db()
    erg, aufrufe = _starten(db, "1.8.0-rc.4", "1.8.0-rc.3")
    assert erg["status"] == "abgelehnt" and aufrufe == [] and db.jobs == []
    assert "Vorabversionen automatisch" in erg["text"]


def test_der_start_weist_eine_vorabversion_auf_einer_stabilen_installation_auch_mit_schalter_ab(tmp_path):
    db = _Db()
    zustand.vorab_setzen(db, True)
    erg, aufrufe = _starten(db, "1.8.0-rc.4", "1.7.9")
    assert erg["status"] == "abgelehnt" and aufrufe == []


def test_der_start_weist_eine_ungueltige_fassung_ab(tmp_path):
    db = _Db()
    zustand.vorab_setzen(db, True)
    erg, aufrufe = _starten(db, "../1.8.0-rc.4", "1.8.0-rc.3")
    assert erg["status"] == "abgelehnt" and aufrufe == []


# ══ Die Automatik, von der Antwort der Quelle bis aktuell.txt ═════════════════════════════════════════

def test_die_automatik_installiert_rc4_auf_rc3_von_der_antwort_der_quelle_bis_zur_umschaltung(tmp_path, monkeypatch, rc3):
    """Der Weg, den der Nutzer sieht: Zeitgeber -> Pruefung (GitHub-Liste mit einer Vorab-Veroeffentlichung) -> Installation."""
    import json

    from _au_hilfen import eintrag
    from bewerbungs_assistent.services.auto_update import layout, quelle

    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: True)
    monkeypatch.setenv("PBP_APP_DIR", str(rc3))
    monkeypatch.setenv("PBP_FASSUNG", "1.8.0-rc.3")
    lauf._PRUEFUNG.update(zeit=0.0, ergebnis=None)
    rel = release_bauen(tmp_path / "rel", "1.8.0-rc.4", vorabversion=True)
    antworten = dict(rel.antworten())
    antworten[quelle.API_FREIGABEN] = json.dumps([eintrag("v1.8.0-rc.4", prerelease=True)]).encode()

    db = _Db()
    zustand.stufe_setzen(db, "auto_still")
    zustand.vorab_setzen(db, True)
    erg = lauf.automatik_schritt(
        db, oeffner=FakeOeffner(antworten), synchron=True, app=rc3, laufende_fassung="1.8.0-rc.3",
        selbsttest_runner=_Selbsttest(), pip_runner=_verboten, version_von=PAKETE.get)
    assert erg.get("installiert") is True, erg
    assert _aktuell(rc3) == "1.8.0-rc.4"
    assert (rc3 / "versions" / "1.8.0-rc.3").is_dir()


def test_dieselbe_automatik_installiert_ohne_schalter_nichts(tmp_path, monkeypatch, rc3):
    import json

    from _au_hilfen import eintrag
    from bewerbungs_assistent.services.auto_update import layout, quelle

    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: True)
    monkeypatch.setenv("PBP_APP_DIR", str(rc3))
    monkeypatch.setenv("PBP_FASSUNG", "1.8.0-rc.3")
    lauf._PRUEFUNG.update(zeit=0.0, ergebnis=None)
    rel = release_bauen(tmp_path / "rel", "1.8.0-rc.4", vorabversion=True)
    antworten = dict(rel.antworten())
    antworten[quelle.API_FREIGABEN] = json.dumps([eintrag("v1.8.0-rc.4", prerelease=True)]).encode()
    db = _Db()
    zustand.stufe_setzen(db, "auto_still")
    erg = lauf.automatik_schritt(db, oeffner=FakeOeffner(antworten), synchron=True, app=rc3, laufende_fassung="1.8.0-rc.3",
                                 selbsttest_runner=_Selbsttest(), pip_runner=_verboten, version_von=PAKETE.get)
    assert erg.get("installiert") is False and _aktuell(rc3) == "1.8.0-rc.3", erg
