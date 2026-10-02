"""Auto-Update (#1093): der ganze Lauf — erfolgreich und an jeder Stelle, an der er scheitern kann.

Die wichtigste Zusicherung (Akzeptanzkriterien 2, 5, 7, 8, 9, 12): scheitert IRGENDEIN Schritt, ist
`aktuell.txt` unberuehrt, der Arbeitsordner leer, kein halber Fassungsordner uebrig — und die bisherige
Fassung laeuft weiter. Deshalb ist jeder Fehlerweg ein eigener Fall und prueft DENSELBEN Endzustand.

Das Netz ist ein Testdoppel, der Programmordner liegt unter `tmp_path`, die Archive sind echt (gebaut von
`scripts/build_update_archive.py`).
"""
import base64
import hashlib
import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from _au_hilfen import FakeAntwort, FakeDb, FakeOeffner, fassung_anlegen, programmordner, release_bauen, schluessel_paar

from bewerbungs_assistent.services.auto_update import (
    abhaengigkeiten, aufraeumen, ed25519, entpacken, installation, quelle, schluessel, zustand,
)
from bewerbungs_assistent.services.auto_update.fehler import UpdateFehler


class Lauf:
    def __init__(self, returncode=0, stdout="OK\n", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


class Aufzeichner:
    """Testdoppel fuer `subprocess.run` (Selbsttest und pip)."""

    def __init__(self, ergebnis=None, wirft=None):
        self.ergebnis = ergebnis or Lauf()
        self.wirft = wirft
        self.befehle = []
        self.kwargs = []

    def __call__(self, befehl, **kw):
        self.befehle.append(befehl)
        self.kwargs.append(kw)
        if self.wirft:
            raise self.wirft
        return self.ergebnis


#: Die Pakete, die auf dem "Rechner" des Tests da sind: genau die, die der Test-Quellbaum verlangt.
PAKETE = {"fastmcp": "3.5.0", "httpx": "0.28.1", "pypdf": "5.0.0"}


def verbotener_lauf(*a, **kw):
    raise AssertionError("Dieser Test darf weder pip noch den echten Selbsttest starten.")


def installiere(app, version="1.8.1", *, oeffner, laufend="1.8.0", db=None, **kw):
    kw.setdefault("selbsttest_runner", Aufzeichner())
    kw.setdefault("pip_runner", verbotener_lauf)          # nie echtes pip: es wuerde ins Netz gehen
    kw.setdefault("version_von", PAKETE.get)
    return installation.installiere(version, app=app, db=db, oeffner=oeffner, laufende_fassung=laufend, **kw)


def zustand_des_ordners(app: Path) -> dict:
    return {
        "aktuell": (app / "aktuell.txt").read_text(encoding="utf-8").strip() if (app / "aktuell.txt").exists() else None,
        "fassungen": sorted(p.name for p in (app / "versions").iterdir()),
        "arbeit": sorted(p.name for p in (app / "update").iterdir()) if (app / "update").exists() else [],
        "sperre": (app / "update.sperre").exists(),
    }


def unveraendert(app: Path, vorher: dict):
    nachher = zustand_des_ordners(app)
    assert nachher == vorher, f"Ordner hat sich veraendert:\n vorher {vorher}\n nachher {nachher}"


@pytest.fixture
def app(tmp_path):
    return programmordner(tmp_path / "pc", fassungen=("1.8.0",))


@pytest.fixture
def release(tmp_path):
    return release_bauen(tmp_path / "rel", "1.8.1")


# ══ Der Erfolgsweg ═══════════════════════════════════════════════════════════════════════

def test_eine_installation_legt_die_neue_fassung_an_und_schaltet_zuletzt_um(app, release):
    oeffner = FakeOeffner(release.antworten())
    st = Aufzeichner()
    e = installiere(app, oeffner=oeffner, selbsttest_runner=st)
    assert e.ok, e.text
    assert e.version == "1.8.1" and e.neustart_noetig is True and e.sha256 == release.ergebnis["sha256"]
    ziel = app / "versions" / "1.8.1"
    assert (ziel / ".fertig").is_file()
    assert (ziel / "src" / "bewerbungs_assistent" / "__init__.py").read_text().strip() == '__version__ = "1.8.1"'
    assert (ziel / "manifest.json").is_file() and (ziel / "_selftest.py").is_file() and (ziel / "start_dashboard.py").is_file()
    assert (app / "aktuell.txt").read_text().strip() == "1.8.1"
    assert not list((app / "versions").glob("*.neu"))
    assert not (app / "update").exists() and not (app / "update.sperre").exists()


def test_die_bisherige_fassung_bleibt_unangetastet_und_ist_der_rueckweg(app, release):
    vorher = {p.relative_to(app).as_posix(): p.read_bytes() for p in (app / "versions" / "1.8.0").rglob("*") if p.is_file()}
    e = installiere(app, oeffner=FakeOeffner(release.antworten()))
    assert e.ok
    assert vorher == {p.relative_to(app).as_posix(): p.read_bytes() for p in (app / "versions" / "1.8.0").rglob("*") if p.is_file()}
    status = json.loads((app / "update_status.json").read_text(encoding="utf-8"))
    assert status["vorherige"] == "1.8.0" and status["letzte_installation"]["version"] == "1.8.1"


def test_zuerst_die_kleine_pruefsummenliste_dann_das_archiv(app, release):
    oeffner = FakeOeffner(release.antworten())
    installiere(app, oeffner=oeffner)
    assert [u.rsplit("/", 1)[1] for u in oeffner.aufrufe] == ["SHA256SUMS", "pbp-update-1.8.1.zip"]


def test_der_selbsttest_laeuft_mit_der_neuen_fassung_in_einer_wegwerf_umgebung(app, release):
    st = Aufzeichner()
    installiere(app, oeffner=FakeOeffner(release.antworten()), selbsttest_runner=st)
    assert len(st.befehle) == 1 and st.befehle[0][1].endswith("_selftest.py")
    env = st.kwargs[0]["env"]
    assert "BA_DATA_DIR" not in env and "PBP_APP_DIR" not in env and "PYTHONPATH" not in env
    assert "update" in st.kwargs[0]["cwd"]  # der Test laeuft gegen den entpackten Ordner, bevor er eingesetzt wird


def test_der_fortschritt_geht_vorwaerts_und_endet_bei_eins(app, release):
    meldungen = []
    installiere(app, oeffner=FakeOeffner(release.antworten()), fortschritt=lambda p, a, t: meldungen.append((p, a, t)))
    anteile = [a for _, a, _ in meldungen]
    assert anteile == sorted(anteile) and anteile[-1] == 1.0
    assert {p for p, _, _ in meldungen} >= {"pruefen", "laden", "entpacken", "test", "umschalten", "fertig"}


def test_ein_kaputter_fortschrittsempfaenger_kippt_das_update_nicht(app, release):
    def kaputt(*a):
        raise RuntimeError("Anzeige kaputt")

    assert installiere(app, oeffner=FakeOeffner(release.antworten()), fortschritt=kaputt).ok


def test_mit_vertrautem_schluessel_wird_die_signatur_geladen_und_verlangt(tmp_path, monkeypatch, app):
    datei, keys = schluessel_paar(tmp_path)
    monkeypatch.setattr(schluessel, "VERTRAUTE_SCHLUESSEL", keys)
    rel = release_bauen(tmp_path / "rel", "1.8.1", schluessel_datei=datei)
    oeffner = FakeOeffner(rel.antworten())
    e = installiere(app, oeffner=oeffner)
    assert e.ok and e.signiert is True and e.schluessel == "haupt"
    assert [u.rsplit("/", 1)[1] for u in oeffner.aufrufe] == ["SHA256SUMS", "SHA256SUMS.sig", "pbp-update-1.8.1.zip"]


# ══ Jeder Fehlerweg hinterlaesst DENSELBEN Zustand ═════════════════════════════════════════

def _eigenes_release(tmp_path, version, eintraege, *, sums_name=None, sums_hash=None):
    """Ein Archiv mit frei gewaehltem Inhalt und passender Pruefsumme (damit erst das Entpacken/Manifest zuschlaegt)."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, inhalt in eintraege.items():
            zf.writestr(name, inhalt)
    daten = puffer.getvalue()
    name = quelle.ARCHIV_NAME.format(version=version)
    summe = sums_hash or hashlib.sha256(daten).hexdigest()
    summen = f"{summe}  {sums_name or name}\n".encode()
    return FakeOeffner({quelle.asset_url(version, name): daten, quelle.asset_url(version, "SHA256SUMS"): summen})


def _manifest(version="1.8.1", **aend):
    m = {"format": 1, "version": version, "linie": "1.8", "boot_format": 1, "python": {"min": "3.11", "unter": "4"},
         "schema": 52, "requirements": [], "requirements_optional": [], "auto_update_moeglich": True,
         "braucht_installer": "", "changelog": [], "erstellt": "x"}
    m.update(aend)
    return json.dumps(m)


GUT = {"src/bewerbungs_assistent/__init__.py": '__version__ = "1.8.1"\n', "start_dashboard.py": "", "_selftest.py": "print('OK')\n"}


def test_ein_manipuliertes_archiv_wird_nicht_installiert(app, release):
    antworten = release.antworten()
    url = quelle.asset_url("1.8.1", release.archiv_name)
    antworten[url] = antworten[url] + b"x"                                       # nach dem Veroeffentlichen verfaelscht
    vorher = zustand_des_ordners(app)
    e = installiere(app, oeffner=FakeOeffner(antworten))
    assert (e.ok, e.code) == (False, "pruefsumme") and "nichts installiert" in e.text
    unveraendert(app, vorher)


def test_ein_archiv_das_nicht_in_der_summenliste_steht_wird_nicht_installiert(app, release):
    antworten = release.antworten()
    antworten[quelle.asset_url("1.8.1", "SHA256SUMS")] = f"{'a' * 64}  etwas-anderes.zip\n".encode()
    vorher = zustand_des_ordners(app)
    e = installiere(app, oeffner=FakeOeffner(antworten))
    assert e.code == "pruefsumme"
    unveraendert(app, vorher)


@pytest.mark.parametrize("fall", ["fehlt", "leer", "fremder_schluessel", "andere_liste"])
def test_mit_vertrautem_schluessel_wird_ohne_gueltige_signatur_nichts_installiert(tmp_path, monkeypatch, app, fall):
    datei, keys = schluessel_paar(tmp_path)
    monkeypatch.setattr(schluessel, "VERTRAUTE_SCHLUESSEL", keys)
    rel = release_bauen(tmp_path / "rel", "1.8.1", schluessel_datei=datei)
    antworten = rel.antworten()
    sig_url = quelle.asset_url("1.8.1", "SHA256SUMS.sig")
    if fall == "fehlt":
        del antworten[sig_url]
    elif fall == "leer":
        antworten[sig_url] = b"\n"
    elif fall == "fremder_schluessel":
        fremd = ed25519.signieren(bytes([9] * 32), antworten[quelle.asset_url("1.8.1", "SHA256SUMS")])
        antworten[sig_url] = base64.b64encode(fremd)
    elif fall == "andere_liste":
        antworten[quelle.asset_url("1.8.1", "SHA256SUMS")] += b"# eingeschmuggelt\n"
    vorher = zustand_des_ordners(app)
    oeffner = FakeOeffner(antworten)
    e = installiere(app, oeffner=oeffner)
    assert e.ok is False and e.code in ("signatur", "netz")
    assert not any(u.endswith(".zip") for u in oeffner.aufrufe), "das grosse Archiv darf gar nicht erst geladen werden"
    unveraendert(app, vorher)


@pytest.mark.parametrize("name", ["../evil.py", "src/../../evil.py", "C:/evil.py", "src/evil.exe", "evil.bat", "docs/x.txt"])
def test_ein_archiv_mit_unerlaubtem_inhalt_wird_nicht_installiert_obwohl_die_summe_stimmt(tmp_path, app, name):
    oeffner = _eigenes_release(tmp_path, "1.8.1", {"manifest.json": _manifest(), **GUT, name: "boese"})
    vorher = zustand_des_ordners(app)
    e = installiere(app, oeffner=oeffner)
    assert (e.ok, e.code) == (False, "archiv_unsicher")
    assert not (tmp_path / "evil.py").exists() and not (app.parent / "evil.py").exists()
    unveraendert(app, vorher)


def test_ein_manifest_mit_anderer_fassung_wird_nicht_installiert(tmp_path, app):
    oeffner = _eigenes_release(tmp_path, "1.8.1", {"manifest.json": _manifest(version="1.8.2"), **GUT})
    vorher = zustand_des_ordners(app)
    assert installiere(app, oeffner=oeffner).code == "manifest"
    unveraendert(app, vorher)


def test_ein_update_das_den_installer_braucht_wird_nicht_automatisch_installiert(tmp_path, app):
    rel = release_bauen(tmp_path / "rel", "1.8.1", braucht_installer="Dieses Update bringt eine neue Python-Laufzeit mit.")
    vorher = zustand_des_ordners(app)
    e = installiere(app, oeffner=FakeOeffner(rel.antworten()))
    assert (e.ok, e.code) == (False, "braucht_installer") and "Python-Laufzeit" in e.text
    unveraendert(app, vorher)


def test_ein_linienwechsel_wird_nie_automatisch_installiert_und_nichts_wird_geladen(tmp_path, app, release):
    oeffner = FakeOeffner(release.antworten())
    vorher = zustand_des_ordners(app)
    e = installiere(app, oeffner=oeffner, laufend="1.7.150")
    assert (e.ok, e.code) == (False, "braucht_installer")
    assert oeffner.aufrufe == []
    unveraendert(app, vorher)


@pytest.mark.parametrize("version", ["1.8.1-beta.2", "1.8.1-rc.1", "v1.8.1", "../1.8.1", "1.8"])
def test_vorabversionen_und_ungueltige_fassungen_werden_nie_installiert(app, version):
    oeffner = FakeOeffner({})
    vorher = zustand_des_ordners(app)
    e = installiere(app, version, oeffner=oeffner)
    assert e.ok is False and e.code == "quelle_nicht_erlaubt"
    assert oeffner.aufrufe == []
    unveraendert(app, vorher)


@pytest.mark.parametrize("version,laufend", [("1.8.0", "1.8.0"), ("1.7.9", "1.8.0"), ("1.8.0", "1.8.5")])
def test_nie_dieselbe_und_nie_eine_aeltere_fassung(app, version, laufend):
    oeffner = FakeOeffner({})
    vorher = zustand_des_ordners(app)
    e = installiere(app, version, oeffner=oeffner, laufend=laufend)
    assert e.ok is False and e.code in ("schon_aktuell", "braucht_installer")
    assert oeffner.aufrufe == []
    unveraendert(app, vorher)


def test_eine_fassung_die_sich_nicht_starten_liess_wird_nicht_noch_einmal_angeboten(app, release):
    (app / "update_status.json").write_text(json.dumps({"gescheitert": ["1.8.1"]}), encoding="utf-8")
    oeffner = FakeOeffner(release.antworten())
    e = installiere(app, oeffner=oeffner)
    assert (e.ok, e.code) == (False, "gescheitert") and oeffner.aufrufe == []


def test_ein_fehlgeschlagener_selbsttest_verhindert_die_installation(app, release):
    vorher = zustand_des_ordners(app)
    e = installiere(app, oeffner=FakeOeffner(release.antworten()),
                    selbsttest_runner=Aufzeichner(Lauf(1, "Traceback ...\nImportError: Paket fehlt\n")))
    assert (e.ok, e.code) == (False, "selbsttest")
    unveraendert(app, vorher)


@pytest.mark.parametrize("lauf", [Lauf(0, "alles gut aber ohne Schlusswort\n"), Lauf(0, ""), Lauf(0, "OK\nundnoch\n")])
def test_der_selbsttest_gilt_nur_bei_ok_in_der_letzten_zeile(app, release, lauf):
    e = installiere(app, oeffner=FakeOeffner(release.antworten()), selbsttest_runner=Aufzeichner(lauf))
    assert e.code == "selbsttest"


def test_ein_selbsttest_der_nicht_endet_oder_abstuerzt_ist_ein_fehlschlag(app, release):
    for wirft in (subprocess.TimeoutExpired("x", 1), OSError("kein Python")):
        vorher = zustand_des_ordners(app)
        e = installiere(app, oeffner=FakeOeffner(release.antworten()), selbsttest_runner=Aufzeichner(wirft=wirft))
        assert e.code == "selbsttest"
        unveraendert(app, vorher)


def test_ein_netzfehler_beim_laden_des_archivs_hinterlaesst_nichts(app, release):
    antworten = release.antworten()
    antworten[quelle.asset_url("1.8.1", release.archiv_name)] = ConnectionResetError("weg")
    vorher = zustand_des_ordners(app)
    e = installiere(app, oeffner=FakeOeffner(antworten))
    assert (e.ok, e.code) == (False, "netz")
    unveraendert(app, vorher)


def test_eine_unterbrochene_verbindung_mitten_im_archiv_hinterlaesst_nichts(app, release):
    antworten = release.antworten()
    url = quelle.asset_url("1.8.1", release.archiv_name)
    antworten[url] = FakeAntwort(antworten[url], ende_vorzeitig=1000)
    vorher = zustand_des_ordners(app)
    assert installiere(app, oeffner=FakeOeffner(antworten)).code == "netz"
    unveraendert(app, vorher)


def test_der_abbruch_durch_den_menschen_hinterlaesst_nichts(app, release):
    zaehler = {"n": 0}

    def abbruch():
        zaehler["n"] += 1
        return zaehler["n"] > 4

    vorher = zustand_des_ordners(app)
    e = installiere(app, oeffner=FakeOeffner(release.antworten()), abbruch=abbruch)
    assert (e.ok, e.code) == (False, "abgebrochen")
    unveraendert(app, vorher)


def test_zu_wenig_platz_bricht_ab_bevor_etwas_geladen_wird(app, release, monkeypatch):
    class Platz:
        free = 1024

    monkeypatch.setattr(shutil, "disk_usage", lambda p: Platz())
    oeffner = FakeOeffner(release.antworten())
    vorher = zustand_des_ordners(app)
    e = installiere(app, oeffner=oeffner)
    assert (e.ok, e.code) == (False, "platz") and oeffner.aufrufe == []
    unveraendert(app, vorher)


def test_ein_unerwarteter_fehler_ist_ein_ergebnis_keine_ausnahme_und_raeumt_auf(app, release, monkeypatch):
    def boese(*a, **k):
        raise RuntimeError("niemand rechnet damit")

    monkeypatch.setattr(entpacken, "entpacken", boese)
    vorher = zustand_des_ordners(app)
    e = installiere(app, oeffner=FakeOeffner(release.antworten()))
    assert (e.ok, e.code) == (False, "unerwartet")
    unveraendert(app, vorher)


def test_ohne_programmordner_oder_laufende_fassung_gibt_es_kein_update():
    e = installation.installiere("1.8.1", app=None, oeffner=FakeOeffner({}), laufende_fassung="1.8.0")
    assert (e.ok, e.code) == (False, "nicht_verfuegbar")


def test_eine_zweite_installation_gleichzeitig_wird_abgelehnt(app, release):
    import os
    (app / "update.sperre").write_text(json.dumps({"pid": os.getpid(), "start": "2999-01-01T00:00:00+00:00"}), encoding="utf-8")
    oeffner = FakeOeffner(release.antworten())
    e = installiere(app, oeffner=oeffner)
    assert (e.ok, e.code) == (False, "gesperrt") and oeffner.aufrufe == []
    assert (app / "update.sperre").exists(), "die Sperre eines anderen Laufs darf nicht entfernt werden"


def test_eine_verwaiste_sperre_eines_toten_prozesses_blockiert_nicht(app, release):
    (app / "update.sperre").write_text(json.dumps({"pid": 2 ** 22 - 3, "start": "2020-01-01T00:00:00+00:00"}), encoding="utf-8")
    assert installiere(app, oeffner=FakeOeffner(release.antworten())).ok


# ══ Zwischenzustaende ═════════════════════════════════════════════════════════════════

def test_schon_geladen_aber_nicht_umgeschaltet_wird_nur_noch_umgeschaltet(app, release):
    fassung_anlegen(app, "1.8.1")                      # vollstaendig da (Strom weg vor dem Umschalten)
    oeffner = FakeOeffner(release.antworten())
    e = installiere(app, oeffner=oeffner)
    assert e.ok and e.schon_vorhanden and oeffner.aufrufe == []
    assert (app / "aktuell.txt").read_text().strip() == "1.8.1"


def test_ein_unfertiger_fassungsordner_ohne_marke_wird_ersetzt(app, release):
    fassung_anlegen(app, "1.8.1", fertig=False)
    e = installiere(app, oeffner=FakeOeffner(release.antworten()))
    assert e.ok and (app / "versions" / "1.8.1" / ".fertig").is_file()


def test_ein_rest_der_vorigen_installation_im_arbeitsordner_stoert_nicht(app, release):
    (app / "update").mkdir()
    (app / "update" / "pbp-update-1.8.1.zip.part").write_bytes(b"halb")
    (app / "update" / "entpackt").mkdir()
    (app / "update" / "entpackt" / "alt.txt").write_text("alt")
    assert installiere(app, oeffner=FakeOeffner(release.antworten())).ok
    assert not (app / "update").exists()


def test_das_umbenennen_wird_bei_gesperrten_ordnern_wiederholt(app, release, monkeypatch):
    echt = installation.os.replace
    zaehler = {"n": 0}

    def zickig(a, b):
        if Path(a).is_dir():                                   # nur das Umbenennen von Ordnern (nicht das der .part-Dateien)
            zaehler["n"] += 1
            if zaehler["n"] <= 2:
                raise PermissionError("vom Virenscanner gehalten")
        return echt(a, b)

    monkeypatch.setattr(installation.os, "replace", zickig)
    monkeypatch.setattr(installation.time, "sleep", lambda s: None)
    assert installiere(app, oeffner=FakeOeffner(release.antworten())).ok


def test_ein_dauerhaft_gesperrter_ordner_ist_ein_fehler_ohne_umschalten(app, release, monkeypatch):
    echt = installation.os.replace

    def immer(a, b):
        if Path(a).is_dir():
            raise PermissionError("gesperrt")
        return echt(a, b)

    monkeypatch.setattr(installation.os, "replace", immer)
    monkeypatch.setattr(installation.time, "sleep", lambda s: None)
    e = installiere(app, oeffner=FakeOeffner(release.antworten()))
    assert (e.ok, e.code) == (False, "unerwartet")
    assert (app / "aktuell.txt").read_text().strip() == "1.8.0"


def test_der_rueckweg_ist_die_zuletzt_bestaetigte_fassung_nicht_eine_nie_gestartete(tmp_path):
    """1.8.0 lief (bestaetigt), 1.8.1 wurde installiert und vorgemerkt, aber nie gestartet. Kommt 1.8.2, ist der
    Rueckweg 1.8.0: eine Fassung, die noch nie gelaufen ist, taugt nicht als Zuflucht."""
    app = programmordner(tmp_path / "pc", fassungen=("1.8.0", "1.8.1"), aktuell="1.8.1", status={"bestaetigt": "1.8.0"})
    rel = release_bauen(tmp_path / "rel", "1.8.2")
    e = installiere(app, "1.8.2", oeffner=FakeOeffner(rel.antworten()), laufend="1.8.0")
    assert e.ok, e.text
    status = json.loads((app / "update_status.json").read_text(encoding="utf-8"))
    assert status["vorherige"] == "1.8.0"
    assert (app / "aktuell.txt").read_text().strip() == "1.8.2"


def test_eine_schon_vorgemerkte_neuere_fassung_ist_die_untergrenze_fuer_das_naechste_update(tmp_path):
    """Ist 1.8.2 schon installiert und vorgemerkt, ist 1.8.1 kein Update mehr."""
    app = programmordner(tmp_path / "pc", fassungen=("1.8.0", "1.8.2"), aktuell="1.8.2")
    rel = release_bauen(tmp_path / "rel", "1.8.1")
    oeffner = FakeOeffner(rel.antworten())
    e = installiere(app, "1.8.1", oeffner=oeffner, laufend="1.8.0")
    assert (e.ok, e.code) == (False, "schon_aktuell") and oeffner.aufrufe == []


# ══ Verlauf und Aufraeumen ═════════════════════════════════════════════════════════════

def test_jeder_lauf_steht_im_verlauf_mit_version_summe_und_ergebnis(app, release):
    db = FakeDb()
    installiere(app, oeffner=FakeOeffner(release.antworten()), db=db, ausloeser="klick")
    eintrag = zustand.verlauf(db)[-1]
    assert eintrag["version"] == "1.8.1" and eintrag["ergebnis"] == "installiert" and eintrag["ausloeser"] == "klick"
    assert eintrag["sha256"] == release.ergebnis["sha256"] and eintrag["quelle"] == "github" and eintrag["zeit"]


def test_auch_ein_fehlschlag_steht_im_verlauf(app, release):
    db = FakeDb()
    antworten = release.antworten()
    antworten[quelle.asset_url("1.8.1", release.archiv_name)] += b"x"
    installiere(app, oeffner=FakeOeffner(antworten), db=db)
    eintrag = zustand.verlauf(db)[-1]
    assert eintrag["ergebnis"] == "fehler" and eintrag["code"] == "pruefsumme" and "Prüfsumme" in eintrag["grund"]


def test_nach_dem_erfolg_werden_alte_fassungen_nach_der_einstellung_aufgeraeumt(tmp_path, release, monkeypatch):
    app = programmordner(tmp_path / "pc", fassungen=("1.7.5", "1.7.9", "1.8.0"), aktuell="1.8.0")
    monkeypatch.setenv("PBP_FASSUNG", "1.8.0")
    db = FakeDb({zustand.K_VORGAENGER: 1})
    e = installiere(app, oeffner=FakeOeffner(release.antworten()), db=db)
    assert e.ok
    uebrig = sorted(p.name for p in (app / "versions").iterdir())
    assert uebrig == ["1.8.0", "1.8.1"], uebrig          # die neue, dazu 1 Vorgaenger (zugleich laufend); 1.7.5 und 1.7.9 sind weg
    assert set(e.aufgeraeumt["geloescht"]) == {"1.7.5", "1.7.9"}


# ══ Pakete ═══════════════════════════════════════════════════════════════════════════

def test_erfuellt_liest_einfache_angaben_ohne_packaging():
    haben = {"fastmcp": "3.2.1", "httpx": "0.28.1", "python-jobspy": "1.1.80", "kaputt": "abc"}
    f = lambda name: haben.get(name)  # noqa: E731
    assert abhaengigkeiten.erfuellt("fastmcp>=3.0,<4", version_von=f)
    assert not abhaengigkeiten.erfuellt("fastmcp>=3.5", version_von=f)
    assert not abhaengigkeiten.erfuellt("fastmcp<3", version_von=f)
    assert abhaengigkeiten.erfuellt("httpx", version_von=f)
    assert not abhaengigkeiten.erfuellt("python-jobspy>=1.2", version_von=f)       # Untergrenze angehoben
    assert not abhaengigkeiten.erfuellt("gibtsnicht>=1", version_von=f)
    assert not abhaengigkeiten.erfuellt("kaputt>=1", version_von=f)                 # keine Zahl in der Version
    assert abhaengigkeiten.erfuellt("httpx~=0.28", version_von=f)
    assert abhaengigkeiten.erfuellt("httpx~=0.28.0", version_von=f)
    assert not abhaengigkeiten.erfuellt("httpx~=0.27.0", version_von=f)             # < 0.28
    assert abhaengigkeiten.erfuellt("fastmcp==3.2.1", version_von=f)
    assert abhaengigkeiten.erfuellt("fastmcp!=3.0", version_von=f)
    assert abhaengigkeiten.erfuellt("fastmcp[extra]>=3.0 ; python_version >= '3.11'", version_von=f)


@pytest.mark.parametrize("angabe", ["", "fastmcp >> 3", "fastmcp>=", "fastmcp>=3 or x", "git+https://x/y.git", ">=3", "a b c", "fastmcp>=3.0,", "x @ http://y"])
def test_nicht_sicher_lesbare_angaben_zaehlen_als_fehlend_nie_als_erfuellt(angabe):
    assert abhaengigkeiten.erfuellt(angabe, version_von=lambda n: "999") is False


def test_fehlende_pflichtpakete_und_nur_vorhandene_optionale_mit_zu_alter_fassung():
    haben = {"fastmcp": "3.2", "pypdf": "3.0"}
    f = lambda name: haben.get(name)  # noqa: E731
    r = abhaengigkeiten.fehlende(["fastmcp>=3.0", "httpx>=0.27"], ["pypdf>=4.0", "openpyxl>=3.1"], version_von=f)
    assert r == ["httpx>=0.27", "pypdf>=4.0"]        # openpyxl war nie da: wird nicht aufgedraengt


def test_fehlende_pakete_werden_in_den_neuen_fassungsordner_gelegt(app, tmp_path):
    rel = release_bauen(tmp_path / "rel", "1.8.1", anforderungen=["httpx>=0.27", "neues-paket>=2.0"])
    laeufe = []

    def runner(befehl, **kw):
        laeufe.append(befehl)
        ziel = Path(befehl[befehl.index("--target") + 1])           # so legt pip die Pakete ab
        ziel.mkdir(parents=True, exist_ok=True)
        (ziel / "neues_paket.py").write_text("WERT = 1\n", encoding="utf-8")
        return Lauf()

    haben = {"httpx": "0.28"}
    e = installiere(app, oeffner=FakeOeffner(rel.antworten()), pip_runner=runner, selbsttest_runner=Aufzeichner(),
                    version_von=lambda n: haben.get(n))
    assert e.ok, e.text
    assert (app / "versions" / "1.8.1" / "site" / "neues_paket.py").is_file()
    befehl = laeufe[0]
    assert befehl[1:3] == ["-m", "pip"] and "--only-binary=:all:" in befehl and "--isolated" in befehl
    assert befehl[-1] == "neues-paket>=2.0" and "httpx>=0.27" not in befehl


def test_scheitert_pip_wird_nichts_installiert_und_nichts_bleibt_liegen(app, tmp_path):
    rel = release_bauen(tmp_path / "rel", "1.8.1", anforderungen=["neues-paket>=2.0"])
    vorher = zustand_des_ordners(app)
    e = installiere(app, oeffner=FakeOeffner(rel.antworten()), pip_runner=Aufzeichner(Lauf(1, "", "ERROR: no matching distribution")),
                    version_von=lambda n: None)
    assert (e.ok, e.code) == (False, "abhaengigkeiten")
    unveraendert(app, vorher)


def test_zu_viele_neue_pakete_sind_ein_fall_fuer_den_installer(app, tmp_path):
    rel = release_bauen(tmp_path / "rel", "1.8.1", anforderungen=[f"paket-{i}>=1.0" for i in range(abhaengigkeiten.MAX_FEHLENDE + 1)])
    vorher = zustand_des_ordners(app)
    e = installiere(app, oeffner=FakeOeffner(rel.antworten()), pip_runner=Aufzeichner(), version_von=lambda n: None)
    assert (e.ok, e.code) == (False, "braucht_installer")
    unveraendert(app, vorher)
