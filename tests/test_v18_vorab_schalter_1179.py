"""#1179 Tester-Schalter: Vorabversionen ausdrücklich erlauben — Vorgabe aus, nie von selbst, nie ohne Klick.

Die Zusage bis 1.8.0 war „PBP installiert nie eine Vorabversion“. Mit dem Schalter (Einstellungen › Updates) wird daraus
„nur mit deinem ausdrücklichen Schalter UND deinem Klick“. Alles Übrige der Sicherheit bleibt: feste Quelle, nur die eigene
Linie, nie zurück, Prüfsumme und Signatur wie bei jeder Version. Diese Datei hält die Grenzen an jeder Stelle fest, an der
der Schalter etwas ändert:

* Zustand: Vorgabe aus, im Zweifel aus, nur ein echtes ja/nein.
* Quelle und Manifest: eine Vorabversion kommt nur mit `vorab_erlaubt` durch, und nur mit streng gültiger Nummer.
* Prüfung: die Vorabversion steht NEBEN der fertigen (`vorab`), nie an ihrer Stelle; die Automatik sieht sie nie.
* Installation: alle Bedingungen zugleich (Aufruf, Schalter, ein Mensch als Auslöser, gültige Nummer, eigene Linie).
* Schnittstellen: Dashboard und Werkzeug verlangen dieselbe ausdrückliche Zusage.

Kein Netz, kein echter Programmordner; die Archive sind echt gebaut (`scripts/build_update_archive.py --vorabversion`).
"""
import os

import pytest
from _au_hilfen import FakeDb, FakeOeffner, eintrag, liste, programmordner, release_bauen

from bewerbungs_assistent.services import update_quelle
from bewerbungs_assistent.services.auto_update import installation, lauf, layout, manifest, quelle, zustand
from bewerbungs_assistent.services.auto_update.fehler import UpdateFehler

BETA = "1.8.1-beta.1"


# ── Hilfen ────────────────────────────────────────────────────────────────────────────

class Lauf:
    def __init__(self, returncode=0, stdout="OK\n", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _selbsttest(*a, **kw):
    return Lauf()


def _kein_pip(*a, **kw):
    raise AssertionError("kein pip im Test")


PAKETE = {"fastmcp": "3.5.0", "httpx": "0.28.1", "pypdf": "5.0.0"}


def _installiere(app, version, *, oeffner, laufend="1.8.0", **kw):
    kw.setdefault("selbsttest_runner", _selbsttest)
    kw.setdefault("pip_runner", _kein_pip)
    kw.setdefault("version_von", PAKETE.get)
    return installation.installiere(version, app=app, db=None, oeffner=oeffner, laufende_fassung=laufend, **kw)


def _zustand(app):
    return {
        "aktuell": (app / "aktuell.txt").read_text(encoding="utf-8").strip() if (app / "aktuell.txt").exists() else None,
        "fassungen": sorted(p.name for p in (app / "versions").iterdir()),
        "arbeit": sorted(p.name for p in (app / "update").iterdir()) if (app / "update").exists() else [],
    }


@pytest.fixture(autouse=True)
def _sauber():
    lauf._PRUEFUNG.update(zeit=0.0, ergebnis=None)
    lauf._JOB.update(id=None, status=None, phase="", anteil=0.0, text="", version=None, ausloeser="")
    yield


@pytest.fixture
def app(tmp_path):
    return programmordner(tmp_path / "pc", fassungen=("1.8.0",))


@pytest.fixture
def umgebung(app, monkeypatch):
    monkeypatch.setenv("PBP_APP_DIR", str(app))
    monkeypatch.setenv("PBP_FASSUNG", "1.8.0")
    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: True)
    return app


@pytest.fixture
def db_aus(tmp_path):
    """Eine echte, isolierte Datenbank: die Installation legt einen Eintrag in background_jobs an."""
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "vorab.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    yield d
    d.close()


@pytest.fixture
def db_an(db_aus):
    zustand.vorabversionen_setzen(db_aus, True)
    return db_aus


# ══ Zustand: Vorgabe aus, im Zweifel aus ════════════════════════════════════════════════

def test_die_vorgabe_ist_aus(db_aus):
    assert zustand.vorabversionen(db_aus) is False


def test_nur_ein_echtes_ja_schaltet_ein():
    d = FakeDb()
    assert zustand.vorabversionen_setzen(d, True) is True and zustand.vorabversionen(d) is True
    assert zustand.vorabversionen_setzen(d, False) is False and zustand.vorabversionen(d) is False


@pytest.mark.parametrize("wert", ["ja", "true", "True", 1, "1", "an", [], {}, None, "nein"])
def test_ein_gespeicherter_wert_der_kein_bool_ist_gilt_als_aus(wert):
    assert zustand.vorabversionen(FakeDb({zustand.K_VORAB: wert})) is False


@pytest.mark.parametrize("wert", ["ja", "true", 1, 0, None, "an"])
def test_setzen_nimmt_nur_ein_bool(wert):
    d = FakeDb()
    with pytest.raises(ValueError):
        zustand.vorabversionen_setzen(d, wert)
    assert zustand.vorabversionen(d) is False


def test_eine_kaputte_datenbank_gilt_als_aus():
    class Kaputt:
        def get_setting(self, *a, **k):
            raise RuntimeError("nicht lesbar")

    assert zustand.vorabversionen(Kaputt()) is False


# ══ Quelle und Manifest ═════════════════════════════════════════════════════════════════

def test_ohne_schalter_kennt_die_liste_keine_vorabversion_und_nichts_als_vorabversion_markiertes():
    daten = [eintrag("v1.8.1"), eintrag(BETA.join(["v", ""]), prerelease=True), eintrag("v1.8.2-rc.1"),
             eintrag("v1.8.3", prerelease=True), eintrag("v1.8.4", draft=True)]
    assert [f.version for f in quelle.freigaben_lesen(daten)] == ["1.8.1"]


def test_mit_schalter_kommen_vorabversionen_dazu_und_tragen_die_marke():
    daten = [eintrag("v1.8.1"), eintrag("v" + BETA, prerelease=True), eintrag("v1.8.2-rc.1"),
             eintrag("v1.8.3", prerelease=True), eintrag("v1.8.4", draft=True)]
    f = {x.version: x for x in quelle.freigaben_lesen(daten, mit_vorab=True)}
    assert set(f) == {"1.8.1", BETA, "1.8.2-rc.1", "1.8.3"}, "ein Entwurf bleibt auch mit dem Schalter draussen"
    assert f["1.8.1"].vorab is False
    assert f[BETA].vorab and f["1.8.2-rc.1"].vorab
    assert f["1.8.3"].vorab, "auch eine Nummer ohne Beta-Zusatz gilt als Vorabversion, wenn GitHub sie so fuehrt"


def test_ungueltige_tags_bleiben_auch_mit_schalter_draussen():
    daten = [eintrag("v1.8.1-gamma.1"), eintrag("1.8.1-beta.1"), eintrag("v1.8.1-beta"), eintrag("v1.8.1-beta.1/../x")]
    assert quelle.freigaben_lesen(daten, mit_vorab=True) == []


def test_eine_adresse_fuer_eine_vorabversion_nur_mit_ausdruecklicher_erlaubnis():
    with pytest.raises(UpdateFehler) as e:
        quelle.asset_url(BETA, "SHA256SUMS")
    assert e.value.code == "quelle_nicht_erlaubt"
    url = quelle.asset_url(BETA, "SHA256SUMS", vorab_erlaubt=True)
    assert url == f"https://github.com/MadGapun/PBP/releases/download/v{BETA}/SHA256SUMS"


@pytest.mark.parametrize("version", ["1.8.1-gamma.1", "1.8.1-beta", "1.8.1-beta.1/../x", "1.8.1-beta.1?x=1", "../1.8.1",
                                     "1.8.1-beta.1\n", "١.٨.١-beta.1", ""])
def test_auch_mit_erlaubnis_nur_streng_gueltige_nummern(version):
    with pytest.raises(UpdateFehler):
        quelle.asset_url(version, "SHA256SUMS", vorab_erlaubt=True)


def test_ein_unerlaubter_dateiname_bleibt_auch_fuer_eine_vorabversion_unerlaubt():
    with pytest.raises(UpdateFehler):
        quelle.asset_url(BETA, "boese.exe", vorab_erlaubt=True)


def test_das_manifest_einer_vorabversion_nur_mit_erlaubnis():
    roh = {"format": 1, "version": BETA, "linie": "1.8", "boot_format": 1}
    import json
    text = json.dumps(roh)
    with pytest.raises(UpdateFehler) as e:
        manifest.lesen(text, erwartete_version=BETA)
    assert e.value.code == "manifest"
    m = manifest.lesen(text, erwartete_version=BETA, vorab_erlaubt=True)
    assert m.version == BETA and m.linie == "1.8"


# ══ Prüfung: die Vorabversion steht NEBEN der fertigen ═══════════════════════════════════

def _pruefen(db, daten, **kw):
    return lauf.pruefen(db, oeffner=liste(*daten), laufende="1.8.0", app=None, frisch=True, **kw)


def test_ohne_schalter_nennt_die_pruefung_nie_eine_vorabversion(db_aus, umgebung):
    erg = lauf.pruefen(db_aus, oeffner=liste(eintrag("v" + BETA, prerelease=True)), laufende="1.8.0", frisch=True)
    assert erg["status"] == "aktuell" and "vorab" not in erg


def test_mit_schalter_steht_sie_neben_der_fertigen_nicht_an_ihrer_stelle(db_an, umgebung):
    erg = lauf.pruefen(db_an, oeffner=liste(eintrag("v1.8.1"), eintrag("v1.8.2-beta.1", prerelease=True)),
                       laufende="1.8.0", frisch=True)
    assert erg["status"] == "neu" and erg["version"] == "1.8.1", "status und version gehoeren der fertigen Fassung"
    assert erg["vorab"]["version"] == "1.8.2-beta.1"


def test_eine_aeltere_vorabversion_als_die_fertige_wird_nicht_genannt(db_an, umgebung):
    erg = lauf.pruefen(db_an, oeffner=liste(eintrag("v1.8.2"), eintrag("v1.8.1-beta.1", prerelease=True)),
                       laufende="1.8.0", frisch=True)
    assert erg["version"] == "1.8.2" and "vorab" not in erg


def test_nur_eine_vorabversion_status_bleibt_aktuell_und_vorab_ist_da(db_an, umgebung):
    erg = lauf.pruefen(db_an, oeffner=liste(eintrag("v" + BETA, prerelease=True, signatur=True)),
                       laufende="1.8.0", frisch=True)
    assert erg["status"] == "aktuell", "die Automatik sieht keine Vorabversion"
    assert erg["vorab"]["version"] == BETA and erg["vorab"]["bereit"] is True
    assert erg["vorab"]["zip"] == f"https://github.com/MadGapun/PBP/archive/refs/tags/v{BETA}.zip"
    assert erg["vorab"]["url"].endswith(f"/releases/tag/v{BETA}")


def test_ohne_update_dateien_ist_sie_nicht_bereit(db_an, umgebung):
    erg = lauf.pruefen(db_an, oeffner=liste(eintrag("v" + BETA, prerelease=True, dateien=False)),
                       laufende="1.8.0", frisch=True)
    assert erg["vorab"]["bereit"] is False


def test_nie_ein_linienwechsel_und_nie_eine_aeltere_vorabversion(db_an, umgebung):
    erg = lauf.pruefen(db_an, oeffner=liste(eintrag("v1.9.0-beta.1", prerelease=True), eintrag("v1.7.9-beta.3", prerelease=True),
                                            eintrag("v1.8.0-beta.5", prerelease=True)),
                       laufende="1.8.0", frisch=True)
    assert "vorab" not in erg


def test_das_umschalten_gilt_sofort_ohne_die_frist_abzuwarten(db_aus, umgebung):
    o = liste(eintrag("v" + BETA, prerelease=True))
    erg = lauf.pruefen(db_aus, oeffner=o, laufende="1.8.0")
    assert "vorab" not in erg
    zustand.vorabversionen_setzen(db_aus, True)
    erg = lauf.pruefen(db_aus, oeffner=o, laufende="1.8.0")        # nicht frisch: die gemerkte Antwort galt noch
    assert erg["vorab"]["version"] == BETA
    zustand.vorabversionen_setzen(db_aus, False)
    assert "vorab" not in lauf.pruefen(db_aus, oeffner=o, laufende="1.8.0")


def test_die_uebersicht_zeigt_vorab_nur_bei_eingeschaltetem_schalter(db_an, umgebung):
    lauf.pruefen(db_an, oeffner=liste(eintrag("v" + BETA, prerelease=True, signatur=True)), laufende="1.8.0", frisch=True)
    u = lauf.uebersicht(db_an)
    assert u["vorabversionen"] is True and u["vorab"]["version"] == BETA
    zustand.vorabversionen_setzen(db_an, False)
    u = lauf.uebersicht(db_an)
    assert u["vorabversionen"] is False and u["vorab"] is None, "die gemerkte Antwort zeigt nichts, wenn der Schalter aus ist"


# ══ Die Automatik sieht eine Vorabversion nie ═════════════════════════════════════════════

@pytest.mark.parametrize("stufe", ["auto_meldung", "auto_still"])
def test_die_automatischen_stufen_installieren_nie_eine_vorabversion(db_an, umgebung, monkeypatch, stufe):
    zustand.stufe_setzen(db_an, stufe)
    gestartet = []
    monkeypatch.setattr(installation, "installiere", lambda *a, **k: gestartet.append((a, k)))
    r = lauf.automatik_schritt(db_an, oeffner=liste(eintrag("v" + BETA, prerelease=True, signatur=True)))
    assert r["installiert"] is False and r["status"] == "aktuell"
    assert gestartet == []


def test_gibt_es_beides_installiert_die_automatik_die_fertige_nie_die_vorabversion(db_an, umgebung):
    zustand.stufe_setzen(db_an, "auto_still")
    aufrufe = []

    def doppel(version, **kw):
        aufrufe.append((version, kw))
        return installation.Ergebnis(ok=True, version=version, text="ok")

    r = lauf.automatik_schritt(db_an, oeffner=liste(eintrag("v1.8.1", signatur=True),
                                                    eintrag("v1.8.2-beta.1", prerelease=True, signatur=True)),
                               installieren=doppel, synchron=True)
    assert r["version"] == "1.8.1" and r["installiert"] is True
    assert [v for v, _ in aufrufe] == ["1.8.1"] and "vorab_erlaubt" not in aufrufe[0][1]


# ══ Installation: alle Bedingungen zugleich ═══════════════════════════════════════════════

def _doppel(aufrufe):
    def installieren(version, **kw):
        aufrufe.append((version, kw))
        return installation.Ergebnis(ok=True, version=version, text="ok")
    return installieren


def test_eine_vorabversion_ohne_ausdrueckliche_zusage_im_aufruf_wird_abgelehnt(db_an, umgebung):
    aufrufe = []
    r = lauf.starte_installation(db_an, BETA, ausloeser="klick", installieren=_doppel(aufrufe), synchron=True)
    assert r["status"] == "abgelehnt" and aufrufe == []


def test_mit_zusage_aber_ausgeschaltetem_schalter_wird_abgelehnt(db_aus, umgebung):
    aufrufe = []
    r = lauf.starte_installation(db_aus, BETA, ausloeser="klick", vorab_erlaubt=True, installieren=_doppel(aufrufe), synchron=True)
    assert r["status"] == "abgelehnt" and "ausgeschaltet" in r["text"] and aufrufe == []


@pytest.mark.parametrize("version", ["1.8.1-gamma.1", "1.8.1-beta", "1.8.1-beta.1/../x"])
def test_mit_zusage_und_schalter_aber_ungueltiger_nummer_wird_abgelehnt(db_an, umgebung, version):
    aufrufe = []
    r = lauf.starte_installation(db_an, version, ausloeser="klick", vorab_erlaubt=True, installieren=_doppel(aufrufe), synchron=True)
    assert r["status"] == "abgelehnt" and aufrufe == []


def test_der_ausloeser_automatisch_ist_nie_erlaubt(db_an, umgebung):
    aufrufe = []
    r = lauf.starte_installation(db_an, BETA, ausloeser="automatisch", vorab_erlaubt=True, installieren=_doppel(aufrufe),
                                 synchron=True)
    assert r["status"] == "abgelehnt" and aufrufe == []


@pytest.mark.parametrize("ausloeser", ["klick", "mcp"])
def test_zusage_schalter_und_mensch_zusammen_starten_die_installation(db_an, umgebung, ausloeser):
    aufrufe = []
    r = lauf.starte_installation(db_an, BETA, ausloeser=ausloeser, vorab_erlaubt=True, installieren=_doppel(aufrufe), synchron=True)
    assert r["status"] == "gestartet"
    assert aufrufe and aufrufe[0][0] == BETA and aufrufe[0][1]["vorab_erlaubt"] is True and aufrufe[0][1]["ausloeser"] == ausloeser


def test_eine_fertige_version_bekommt_die_zusage_nie_mit_(db_aus, umgebung):
    """Die Aufrufform fuer fertige Versionen bleibt, wie sie war."""
    aufrufe = []
    lauf.starte_installation(db_aus, "1.8.1", ausloeser="klick", installieren=_doppel(aufrufe), synchron=True)
    assert "vorab_erlaubt" not in aufrufe[0][1]


def test_der_ganze_lauf_mit_echtem_archiv_installiert_die_vorabversion(tmp_path, app):
    rel = release_bauen(tmp_path / "rel", BETA)
    e = _installiere(app, BETA, oeffner=FakeOeffner(rel.antworten()), vorab_erlaubt=True, ausloeser="klick")
    assert e.ok, e.text
    assert (app / "aktuell.txt").read_text().strip() == BETA
    assert (app / "versions" / BETA / ".fertig").is_file()
    assert (app / "versions" / "1.8.0").is_dir(), "die bisherige Fassung bleibt als Rueckweg"


def test_ohne_zusage_installiert_dasselbe_archiv_nichts(tmp_path, app):
    rel = release_bauen(tmp_path / "rel", BETA)
    vorher = _zustand(app)
    e = _installiere(app, BETA, oeffner=FakeOeffner(rel.antworten()), ausloeser="klick")
    assert (e.ok, e.code) == (False, "quelle_nicht_erlaubt")
    assert _zustand(app) == vorher


def test_mit_zusage_aber_ausloeser_automatisch_installiert_es_nichts(tmp_path, app):
    rel = release_bauen(tmp_path / "rel", BETA)
    vorher = _zustand(app)
    e = _installiere(app, BETA, oeffner=FakeOeffner(rel.antworten()), vorab_erlaubt=True)   # Ausloeser-Vorgabe: automatisch
    assert (e.ok, e.code) == (False, "quelle_nicht_erlaubt")
    assert _zustand(app) == vorher


def test_kein_linienwechsel_auch_nicht_mit_der_zusage(tmp_path, app):
    rel = release_bauen(tmp_path / "rel", "1.9.0-beta.1")
    vorher = _zustand(app)
    e = _installiere(app, "1.9.0-beta.1", oeffner=FakeOeffner(rel.antworten()), vorab_erlaubt=True, ausloeser="klick")
    assert (e.ok, e.code) == (False, "braucht_installer")
    assert _zustand(app) == vorher


def test_nie_zurueck_auch_nicht_mit_der_zusage(tmp_path, app):
    rel = release_bauen(tmp_path / "rel", "1.8.1-beta.2")
    vorher = _zustand(app)
    e = _installiere(app, "1.8.1-beta.2", oeffner=FakeOeffner(rel.antworten()), laufend="1.8.3",
                     vorab_erlaubt=True, ausloeser="klick")
    assert (e.ok, e.code) == (False, "schon_aktuell")
    assert _zustand(app) == vorher


def test_pruefsumme_bleibt_pflicht_auch_fuer_eine_vorabversion(tmp_path, app):
    rel = release_bauen(tmp_path / "rel", BETA)
    antworten = rel.antworten()
    url = quelle.asset_url(BETA, rel.archiv_name, vorab_erlaubt=True)
    antworten[url] = antworten[url] + b"x"
    vorher = _zustand(app)
    e = _installiere(app, BETA, oeffner=FakeOeffner(antworten), vorab_erlaubt=True, ausloeser="klick")
    assert (e.ok, e.code) == (False, "pruefsumme")
    assert _zustand(app) == vorher


def test_die_signatur_bleibt_pflicht_auch_fuer_eine_vorabversion(tmp_path, monkeypatch, app):
    """Eine Vorabversion, die mit einem FREMDEN Schluessel signiert ist, wird nicht installiert; mit dem vertrauten geht es."""
    from _au_hilfen import schluessel_paar
    from bewerbungs_assistent.services.auto_update import schluessel
    haupt_datei, vertraut = schluessel_paar(tmp_path, name="haupt", seed=bytes([7] * 32))
    fremd_datei, fremde_keys = schluessel_paar(tmp_path, name="fremd", seed=bytes([9] * 32))
    vorher = _zustand(app)
    # Das Bauen prueft selbst gegen die vertrauten Schluessel: fuer das fremd signierte Paket gelten zeitweise die fremden.
    monkeypatch.setattr(schluessel, "VERTRAUTE_SCHLUESSEL", fremde_keys)
    fremd = release_bauen(tmp_path / "rel-fremd", BETA, schluessel_datei=fremd_datei)
    monkeypatch.setattr(schluessel, "VERTRAUTE_SCHLUESSEL", vertraut)
    e = _installiere(app, BETA, oeffner=FakeOeffner(fremd.antworten()), vorab_erlaubt=True, ausloeser="klick")
    assert (e.ok, e.code) == (False, "signatur")
    assert _zustand(app) == vorher
    echt = release_bauen(tmp_path / "rel-echt", BETA, schluessel_datei=haupt_datei)
    e = _installiere(app, BETA, oeffner=FakeOeffner(echt.antworten()), vorab_erlaubt=True, ausloeser="klick")
    assert e.ok and e.signiert is True and e.schluessel == "haupt"


# ══ Schnittstellen: Dashboard und Werkzeug ═══════════════════════════════════════════════

@pytest.fixture
def client_db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Test"})
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    dash._update_cache.update(ts=0, data=None)
    from fastapi.testclient import TestClient
    yield TestClient(dash.app), db
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


def test_die_einstellung_laesst_sich_ueber_das_dashboard_setzen_und_lesen(client_db, umgebung):
    c, db = client_db
    assert c.get("/api/auto-update").json()["vorabversionen"] is False
    r = c.post("/api/auto-update/einstellungen", json={"vorabversionen": True})
    assert r.status_code == 200 and r.json()["vorabversionen"] is True
    assert zustand.vorabversionen(db) is True
    assert c.post("/api/auto-update/einstellungen", json={"vorabversionen": False}).json()["vorabversionen"] is False


@pytest.mark.parametrize("wert", ["ja", "true", 1, None, "an"])
def test_das_dashboard_nimmt_nur_ein_echtes_ja_oder_nein(client_db, umgebung, wert):
    c, db = client_db
    r = c.post("/api/auto-update/einstellungen", json={"vorabversionen": wert})
    assert r.status_code == 400 and zustand.vorabversionen(db) is False


def test_umschalten_verwirft_die_gemerkte_antwort_der_allgemeinen_pruefung(client_db, umgebung):
    import bewerbungs_assistent.dashboard as dash
    c, _ = client_db
    dash._update_cache.update(ts=10**12, data={"latest_version": "x"}, pause_s=3600)
    c.post("/api/auto-update/einstellungen", json={"vorabversionen": True})
    assert dash._update_cache["data"] is None


def test_der_installationsweg_im_dashboard_verlangt_die_ausdrueckliche_zusage(client_db, umgebung, monkeypatch):
    c, db = client_db
    zustand.vorabversionen_setzen(db, True)
    aufrufe = []
    monkeypatch.setattr(lauf, "starte_installation",
                        lambda db_, version, **kw: aufrufe.append((version, kw)) or {"status": "gestartet", "job_id": "x"})
    c.post("/api/auto-update/installieren", json={"version": BETA})
    c.post("/api/auto-update/installieren", json={"version": BETA, "vorabversion": "ja"})
    c.post("/api/auto-update/installieren", json={"version": BETA, "vorabversion": True})
    assert aufrufe == [(BETA, {"ausloeser": "klick"}), (BETA, {"ausloeser": "klick"}),
                       (BETA, {"ausloeser": "klick", "vorab_erlaubt": True})]


def test_der_installationsweg_im_dashboard_lehnt_ohne_schalter_ab_auch_mit_zusage(client_db, umgebung):
    c, db = client_db
    r = c.post("/api/auto-update/installieren", json={"version": BETA, "vorabversion": True})
    assert r.status_code == 400 and "ausgeschaltet" in r.json()["text"]


@pytest.fixture
def werkzeuge(tmp_path):
    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent.tools import update as tools_update
    db = Database(db_path=tmp_path / "w.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path)
    gesammelt = {}

    class _Mcp:
        def tool(self):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

    import logging
    tools_update.register(_Mcp(), db, logging.getLogger("test"))
    yield gesammelt, db
    db.close()


def test_das_werkzeug_verlangt_fuer_ja_die_bestaetigung_fuer_nein_nicht(werkzeuge, umgebung):
    tools, db = werkzeuge
    r = tools["update_einstellungen_setzen"](vorabversionen="ja")
    assert r["status"] == "bestaetigung_noetig" and zustand.vorabversionen(db) is False
    r = tools["update_einstellungen_setzen"](vorabversionen="ja", bestaetigt=True)
    assert r["status"] == "gesetzt" and "vorabversionen" in r["geaendert"] and zustand.vorabversionen(db) is True
    r = tools["update_einstellungen_setzen"](vorabversionen="nein")
    assert r["status"] == "gesetzt" and zustand.vorabversionen(db) is False


def test_das_werkzeug_nimmt_nur_ja_oder_nein(werkzeuge, umgebung):
    tools, db = werkzeuge
    r = tools["update_einstellungen_setzen"](vorabversionen="vielleicht", bestaetigt=True)
    assert "fehler" in r and zustand.vorabversionen(db) is False


def test_das_werkzeug_waehlt_eine_vorabversion_nie_von_selbst(werkzeuge, umgebung, monkeypatch):
    tools, db = werkzeuge
    zustand.vorabversionen_setzen(db, True)
    monkeypatch.setattr(quelle, "standard_oeffner", lambda: liste(eintrag("v" + BETA, prerelease=True, signatur=True)))
    aufrufe = []
    monkeypatch.setattr(lauf, "starte_installation", lambda *a, **k: aufrufe.append((a, k)) or {"status": "gestartet"})
    r = tools["update_jetzt_installieren"](bestaetigt=True)
    assert r["status"] == "nur_vorabversion" and r["vorab"]["version"] == BETA and aufrufe == []
    assert BETA in r["text"]


def test_das_werkzeug_installiert_eine_genannte_vorabversion_mit_zusage(werkzeuge, umgebung, monkeypatch):
    tools, db = werkzeuge
    aufrufe = []
    monkeypatch.setattr(lauf, "starte_installation",
                        lambda db_, version, **kw: aufrufe.append((version, kw)) or {"status": "gestartet", "job_id": "j"})
    r = tools["update_jetzt_installieren"](version=BETA, bestaetigt=True)
    assert r["status"] == "gestartet" and aufrufe == [(BETA, {"ausloeser": "mcp", "vorab_erlaubt": True})]


def test_das_werkzeug_ohne_bestaetigung_startet_auch_eine_genannte_vorabversion_nicht(werkzeuge, umgebung, monkeypatch):
    tools, db = werkzeuge
    aufrufe = []
    monkeypatch.setattr(lauf, "starte_installation", lambda *a, **k: aufrufe.append((a, k)) or {"status": "gestartet"})
    r = tools["update_jetzt_installieren"](version=BETA)
    assert r["status"] == "bestaetigung_noetig" and aufrufe == []


# ══ Die allgemeine Prüfung (Seitenleiste) folgt dem Schalter ═════════════════════════════

def test_die_allgemeine_pruefung_nennt_einer_stabilen_installation_keine_beta_ohne_schalter():
    daten = [{"tag_name": "v" + BETA, "prerelease": True, "html_url": "u", "name": "n"}]
    assert update_quelle.auswerten_liste(daten, "1.8.0", "1.8") is None
    assert update_quelle.auswerten("github_liste", daten, "1.8.0", "1.8") is None


def test_die_allgemeine_pruefung_nennt_sie_mit_schalter():
    daten = [{"tag_name": "v" + BETA, "prerelease": True, "html_url": "u", "name": "n"},
             {"tag_name": "v1.9.0-beta.1", "prerelease": True, "html_url": "u2", "name": "n2"}]
    befund = update_quelle.auswerten_liste(daten, "1.8.0", "1.8", mit_vorab=True)
    assert befund["version"] == BETA, "die hoehere Linie bleibt auch mit dem Schalter draussen"
    assert update_quelle.auswerten("github_liste", daten, "1.8.0", "1.8", mit_vorab=True)["version"] == BETA


def test_ein_entwurf_zaehlt_auch_mit_schalter_nie():
    daten = [{"tag_name": "v" + BETA, "prerelease": True, "draft": True, "html_url": "u", "name": "n"}]
    assert update_quelle.auswerten_liste(daten, "1.8.0", "1.8", mit_vorab=True) is None


def test_die_pruefung_im_dashboard_gibt_den_schalter_weiter(client_db, umgebung, monkeypatch):
    """Die Seitenleiste fragt /api/update-check: ohne diese Weitergabe bliebe sie beim alten Satz."""
    import bewerbungs_assistent.dashboard as dash
    c, db = client_db
    zustand.vorabversionen_setzen(db, True)
    gesehen = []
    echt = update_quelle.auswerten

    def spion(art, daten, aktuell, linie, **kw):
        gesehen.append(kw)
        return echt(art, daten, aktuell, linie, **kw)

    monkeypatch.setattr(update_quelle, "auswerten", spion)

    class _Resp:
        status_code = 200

        def json(self):
            return [{"tag_name": "v" + BETA, "prerelease": True, "html_url": "u", "name": "n"}]

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return _Resp()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    monkeypatch.setattr(update_quelle, "quellen", lambda db=None: [{"name": "t", "url": "https://x.invalid/r", "art": "github_liste"}])
    dash._update_cache.update(ts=0, data=None)
    from bewerbungs_assistent import __version__
    erg = c.get("/api/update-check?frisch=1").json()
    assert gesehen and gesehen[0].get("mit_vorab") is True, "der Schalter erreicht die Auswertung"
    assert erg["current_version"] == __version__
    # und ausgeschaltet kommt False an
    zustand.vorabversionen_setzen(db, False)
    dash._update_cache.update(ts=0, data=None)
    gesehen.clear()
    c.get("/api/update-check?frisch=1")
    assert gesehen and gesehen[0].get("mit_vorab") is False
