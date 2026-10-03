"""Auto-Update (#1093): Signieren ohne Handarbeit - fester Ort, automatische Sicherung, Pruefung im Release-Tor.

Wer PBP benutzt, braucht keinen Schluessel. Wer veroeffentlicht, soll nichts von Hand tun muessen (Wunsch vom 03.10.2026):

* Der Hauptschluessel liegt an einem festen Ort (`~/PBP-Signatur`). Der Archivbauer nimmt ihn von dort, wenn nichts anderes
  angegeben ist.
* `update_schluessel.py sichern` kopiert beide Schluessel in die Sicherung (OneDrive) und prueft die Kopien gegen; es
  ueberschreibt nie einen anderen Schluessel und sichert nie in ein Git-Arbeitsverzeichnis.
* Das Release-Tor baut das Probe-Archiv signiert, wenn der Schluessel da ist, meldet einen fehlenden Schluessel bei einer
  stabilen Version als Fehler und eine fehlende Sicherung als Warnung. In der CI wird nicht signiert.

Kein Test sieht den echten Schluesselordner oder die echte Sicherung: `conftest.py` lenkt beide auf leere Namen um, und
jeder Test hier legt seine eigenen unter `tmp_path` an.
"""
import importlib.util
import os

import pytest
from _au_hilfen import WURZEL, quellbaum

import build_update_archive as bau
import update_schluessel as us
from bewerbungs_assistent.services.auto_update import ed25519, schluessel


def _schluesselpaar(seed: int):
    geheim = bytes([seed] * 32)
    return geheim, ed25519.geheim_zu_oeffentlich(geheim).hex()


@pytest.fixture
def ablage(tmp_path, monkeypatch):
    """Schluesselordner mit Haupt- und Notfallschluessel, beide im Code eingetragen; Sicherung unter tmp_path."""
    ordner = tmp_path / "PBP-Signatur"
    (ordner / "notfall").mkdir(parents=True)
    haupt, haupt_pub = _schluesselpaar(11)
    notfall, notfall_pub = _schluesselpaar(22)
    (ordner / us.HAUPT_NAME).write_text(haupt.hex() + "\n", encoding="utf-8")
    (ordner / "notfall" / us.NOTFALL_NAME).write_text(notfall.hex() + "\n", encoding="utf-8")
    sicherung = tmp_path / "OneDrive" / us.SICHERUNG_UNTERORDNER
    monkeypatch.setenv(us.SIGNATUR_ORDNER_ENV, str(ordner))
    monkeypatch.setenv(us.SICHERUNG_ENV, str(sicherung))
    monkeypatch.setattr(schluessel, "VERTRAUTE_SCHLUESSEL", {"haupt": haupt_pub, "notfall": notfall_pub})
    return ordner, sicherung


# ══ Der feste Ort ════════════════════════════════════════════════════════════════════════════════

def test_stand_findet_beide_schluessel_und_sieht_dass_die_sicherung_fehlt(ablage):
    ordner, sicherung = ablage
    s = us.stand()
    assert s["hauptschluessel"] == str(ordner / us.HAUPT_NAME) and s["haupt_im_code"] == "haupt"
    assert s["notfallschluessel"] == str(ordner / "notfall" / us.NOTFALL_NAME) and s["notfall_im_code"] == "notfall"
    assert s["sicherung"] == str(sicherung) and s["sicherung_vollstaendig"] is False


def test_ein_schluessel_der_nicht_im_code_steht_wird_so_benannt(ablage, monkeypatch):
    monkeypatch.setattr(schluessel, "VERTRAUTE_SCHLUESSEL", {"anderer": _schluesselpaar(99)[1]})
    s = us.stand()
    assert s["hauptschluessel"] and s["haupt_im_code"] is None


def test_ohne_eigene_angabe_ist_die_sicherung_der_onedrive_ordner(monkeypatch, tmp_path):
    monkeypatch.delenv(us.SICHERUNG_ENV, raising=False)
    monkeypatch.setenv("OneDrive", str(tmp_path / "OD"))
    assert us.sicherungs_ordner() == tmp_path / "OD" / us.SICHERUNG_UNTERORDNER
    monkeypatch.delenv("OneDrive")
    monkeypatch.delenv("OneDriveConsumer", raising=False)
    assert us.sicherungs_ordner() is None


# ══ Sichern ══════════════════════════════════════════════════════════════════════════════════════

def test_sichern_kopiert_beide_schluessel_und_prueft_sie_gegen(ablage):
    ordner, sicherung = ablage
    assert us.sichern() == 0
    assert (sicherung / us.HAUPT_NAME).read_bytes() == (ordner / us.HAUPT_NAME).read_bytes()
    assert (sicherung / us.NOTFALL_NAME).read_bytes() == (ordner / "notfall" / us.NOTFALL_NAME).read_bytes()
    assert "Nicht weitergeben" in (sicherung / "LIESMICH.txt").read_text(encoding="utf-8")
    assert us.stand()["sicherung_vollstaendig"] is True


def test_sichern_laesst_sich_wiederholen(ablage):
    assert us.sichern() == 0 and us.sichern() == 0
    assert us.stand()["sicherung_vollstaendig"] is True


def test_sichern_ueberschreibt_nie_einen_anderen_schluessel(ablage):
    ordner, sicherung = ablage
    sicherung.mkdir(parents=True)
    fremd = _schluesselpaar(33)[0].hex() + "\n"
    (sicherung / us.HAUPT_NAME).write_text(fremd, encoding="utf-8")
    assert us.sichern() == 1
    assert (sicherung / us.HAUPT_NAME).read_text(encoding="utf-8") == fremd, "der vorhandene Schluessel bleibt"
    assert not (sicherung / us.NOTFALL_NAME).exists(), "bei einem Konflikt wird gar nichts geschrieben"


def test_sichern_verweigert_ein_ziel_in_einem_git_arbeitsverzeichnis(ablage, tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    assert us.sichern(repo / "geheim") == 1
    assert not (repo / "geheim").exists()


def test_sichern_ohne_ziel_ist_ein_fehler(ablage, monkeypatch):
    monkeypatch.delenv(us.SICHERUNG_ENV)
    monkeypatch.delenv("OneDrive", raising=False)
    monkeypatch.delenv("OneDriveConsumer", raising=False)
    assert us.sichern() == 1


def test_sichern_ohne_notfallschluessel_ist_ein_fehler_und_schreibt_nichts(ablage):
    ordner, sicherung = ablage
    (ordner / "notfall" / us.NOTFALL_NAME).unlink()
    assert us.sichern() == 1
    assert not sicherung.exists()


# ══ Der Archivbauer nimmt den Schluessel vom festen Ort ══════════════════════════════════════════

def test_der_archivbauer_signiert_ohne_angabe_mit_dem_hauptschluessel(ablage, tmp_path):
    erg = bau.bauen(ordner=quellbaum(tmp_path / "q", "1.8.1"), ausgabe=tmp_path / "aus")
    assert erg["signiert"] is True and erg["schluessel"] == "haupt"
    assert (tmp_path / "aus" / "SHA256SUMS.sig").is_file()


def test_eine_ausdrueckliche_schluesseldatei_hat_vorrang(ablage, tmp_path, monkeypatch):
    anderer, anderer_pub = _schluesselpaar(44)
    datei = tmp_path / "anderer.hex"
    datei.write_text(anderer.hex(), encoding="utf-8")
    monkeypatch.setattr(schluessel, "VERTRAUTE_SCHLUESSEL", {**schluessel.VERTRAUTE_SCHLUESSEL, "anderer": anderer_pub})
    erg = bau.bauen(ordner=quellbaum(tmp_path / "q", "1.8.1"), ausgabe=tmp_path / "aus", schluessel_datei=str(datei))
    assert erg["schluessel"] == "anderer"
    monkeypatch.setenv(bau.SCHLUESSEL_ENV, str(datei))
    erg = bau.bauen(ordner=quellbaum(tmp_path / "q2", "1.8.1"), ausgabe=tmp_path / "aus2")
    assert erg["schluessel"] == "anderer", "die Umgebungsvariable gilt vor dem festen Ort"


def test_ohne_schluessel_am_festen_ort_baut_er_nicht_wenn_eine_signatur_noetig_ist(ablage, tmp_path):
    ordner, _ = ablage
    (ordner / us.HAUPT_NAME).unlink()
    with pytest.raises(bau.BauFehler, match="PBP-Signatur"):
        bau.bauen(ordner=quellbaum(tmp_path / "q", "1.8.1"), ausgabe=tmp_path / "aus")
    assert not list((tmp_path / "aus").glob("*.zip"))


# ══ Das Release-Tor ══════════════════════════════════════════════════════════════════════════════

def _release_check(monkeypatch):
    spec = importlib.util.spec_from_file_location("release_check_schluessel", WURZEL / "release_check.py")
    rc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rc)
    meldungen = {"ok": [], "warn": [], "error": []}
    for art in meldungen:
        monkeypatch.setattr(rc, art, lambda msg, art=art: meldungen[art].append(msg))
    aufrufe = []

    def bauen(**kw):
        aufrufe.append(kw)
        return {"dateien": 3, "groesse": 4096, "signiert": not kw.get("ohne_signatur"), "schluessel": "haupt"}
    monkeypatch.setattr(bau, "bauen", bauen)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("CI", raising=False)
    return rc, meldungen, aufrufe


def test_das_release_tor_signiert_das_probe_archiv_mit_dem_schluessel_vom_festen_ort(ablage, monkeypatch):
    ordner, _ = ablage
    rc, meldungen, aufrufe = _release_check(monkeypatch)
    rc.check_update_archiv("1.8.0")
    assert aufrufe[0]["ohne_signatur"] is False and aufrufe[0]["schluessel_datei"] == str(ordner / us.HAUPT_NAME)
    assert any("signiert und gegen die eingetragenen Schluessel geprueft (haupt)" in m for m in meldungen["ok"])
    assert meldungen["error"] == []


def test_das_release_tor_meldet_einen_fehlenden_schluessel_bei_einer_stabilen_version_als_fehler(ablage, monkeypatch):
    ordner, _ = ablage
    (ordner / us.HAUPT_NAME).unlink()
    rc, meldungen, aufrufe = _release_check(monkeypatch)
    rc.check_update_archiv("1.8.0")
    assert aufrufe[0]["ohne_signatur"] is True
    assert any("Signaturschluessel nicht gefunden" in m for m in meldungen["error"])
    rc2, meldungen2, _ = _release_check(monkeypatch)
    rc2.check_update_archiv("1.8.0-beta.16")
    assert meldungen2["error"] == [] and any("Signaturschluessel nicht gefunden" in m for m in meldungen2["warn"])


def test_das_release_tor_erinnert_an_die_sicherung_bis_es_eine_gibt(ablage, monkeypatch):
    rc, meldungen, _ = _release_check(monkeypatch)
    rc.check_update_archiv("1.8.0")
    assert any("keine vollstaendige Sicherung" in m and "update_schluessel.py sichern" in m for m in meldungen["warn"])
    assert us.sichern() == 0
    rc2, meldungen2, _ = _release_check(monkeypatch)
    rc2.check_update_archiv("1.8.0")
    assert any("Sicherung der Signaturschluessel vollstaendig" in m for m in meldungen2["ok"])
    assert not any("Sicherung" in m for m in meldungen2["warn"])


def test_in_der_ci_wird_nicht_signiert_und_nichts_angemahnt(ablage, monkeypatch):
    rc, meldungen, aufrufe = _release_check(monkeypatch)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    rc.check_update_archiv("1.8.0")
    assert aufrufe[0]["ohne_signatur"] is True and aufrufe[0]["schluessel_datei"] is None
    assert meldungen["error"] == [] and not any("Sicherung" in m for m in meldungen["warn"])
    assert any("in der CI wird nicht signiert" in m for m in meldungen["ok"])


def test_kein_test_sieht_den_echten_schluesselordner():
    """Der Schutz aus conftest.py muss auch greifen, wenn dieser Test allein laeuft (DoD 8c)."""
    assert "PBP-Signatur" not in os.environ.get(us.SIGNATUR_ORDNER_ENV, "PBP-Signatur")
    assert us.hauptschluessel() is None and us.notfallschluessel() is None
    assert os.environ.get(us.SICHERUNG_ENV) and not os.path.exists(os.environ[us.SICHERUNG_ENV])
