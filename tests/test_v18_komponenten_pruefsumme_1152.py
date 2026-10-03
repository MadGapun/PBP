"""#1152: Der Komponenten-Installer startet nichts, was er nicht prüfen kann.

Vorher war `windows_download.sha256` für Tesseract leer, `_sha256_ok` ließ bei leerem Sollwert nur eine Warnung ins
Protokoll und gab True zurück: ein ausgetauschter Installer wäre ohne Warnung ausgeführt worden. Jetzt gilt:

* Setzer: jede Komponente mit Download-Adresse trägt eine gültige SHA-256 in der Registry (Test über ALLE Einträge),
* Leser: ohne gültige Summe wird nichts geladen und nichts gestartet, und `_sha256_ok` ist ohne Sollwert nie wahr,
* eine falsche Summe verwirft den Download und löscht die Datei (die Fälle dazu stehen in #1130).

Kein Netz, kein echter Installer; der Komponenten-Ordner liegt unter tmp_path und wird zugesichert.
"""
import hashlib
import re
from types import SimpleNamespace

import pytest

from bewerbungs_assistent.services import components


@pytest.fixture
def umgebung(tmp_db, tmp_path, monkeypatch):
    ordner = tmp_path / "components"
    monkeypatch.setattr(components, "components_dir", lambda: ordner)
    assert str(tmp_path) in str(components.components_dir()), "Komponenten-Ordner nicht isoliert"
    monkeypatch.setattr(components, "find_component_binary", lambda db, name: None)
    monkeypatch.setattr(components.sys, "platform", "win32")
    aufrufe = SimpleNamespace(download=[], start=[])

    def download(url, target, progress, lo=0, hi=80):
        aufrufe.download.append(url)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x" * 1000)

    def start(*a, **k):
        aufrufe.start.append(a)
        raise AssertionError("Im Test darf kein Installer gestartet werden")

    monkeypatch.setattr(components, "_download", download)
    monkeypatch.setattr(components.subprocess, "run", start)
    return SimpleNamespace(db=tmp_db, ordner=ordner, aufrufe=aufrufe)


def _definition_mit(monkeypatch, sha256):
    dl = dict(components.COMPONENT_DEFS["tesseract"]["windows_download"])
    dl["sha256"] = sha256
    monkeypatch.setitem(components.COMPONENT_DEFS["tesseract"], "windows_download", dl)


# ── Setzer: die Registry ──────────────────────────────────────────────────────────────

def test_jede_komponente_mit_download_adresse_hat_eine_gueltige_pruefsumme():
    gefunden = 0
    for name, d in components.COMPONENT_DEFS.items():
        dl = d.get("windows_download")
        if not dl:
            continue
        gefunden += 1
        assert dl.get("url", "").startswith("https://github.com/"), f"{name}: Adresse nicht bei GitHub"
        assert re.fullmatch(r"[0-9a-f]{64}", dl.get("sha256", "")), f"{name}: keine gültige SHA-256 (64 Hexzeichen, klein)"
    assert gefunden >= 1, "der Test sieht keine Komponente mit Download: er prüft nichts"


def test_die_pruefsumme_gehoert_zur_version_in_der_adresse():
    """Wer die Adresse auf eine neue Version stellt und die Summe vergisst, fällt hier auf, nicht beim Anwender."""
    dl = components.COMPONENT_DEFS["tesseract"]["windows_download"]
    assert "5.4.0.20240606" in dl["url"]
    assert dl["sha256"] == "c885fff6998e0608ba4bb8ab51436e1c6775c2bafc2559a19b423e18678b60c9"


# ── Leser: ohne Summe wird nichts geladen und nichts gestartet ─────────────────────────

@pytest.mark.parametrize("summe", ["", None, "abc", "0" * 63, "0" * 65, "g" * 64, " " + "0" * 63])
def test_ohne_gueltige_pruefsumme_wird_nichts_geladen_und_nichts_gestartet(umgebung, monkeypatch, summe):
    _definition_mit(monkeypatch, summe)
    erg = components.install_component(umgebung.db, "tesseract")
    assert erg["status"] == "fehler" and "Prüfsumme" in erg["fehler"]
    assert umgebung.aufrufe.download == [], "es wurde etwas geladen, das sich nicht prüfen lässt"
    assert umgebung.aufrufe.start == []
    assert not umgebung.ordner.exists() or list(umgebung.ordner.rglob("*")) == []


def test_die_ablehnung_sagt_dem_menschen_den_ausweg(umgebung, monkeypatch):
    _definition_mit(monkeypatch, "")
    erg = components.install_component(umgebung.db, "tesseract")
    assert "selbst installieren" in erg["fehler"] and "Pfad" in erg["fehler"]


def test_sha256_ok_ist_ohne_sollwert_nie_wahr(tmp_path):
    datei = tmp_path / "x.bin"
    datei.write_bytes(b"inhalt")
    for soll in ("", None, "zu kurz", "z" * 64):
        assert components._sha256_ok(datei, soll) is False, repr(soll)


def test_sha256_ok_vergleicht_ohne_auf_gross_und_kleinschreibung_zu_achten(tmp_path):
    datei = tmp_path / "x.bin"
    datei.write_bytes(b"inhalt")
    summe = hashlib.sha256(b"inhalt").hexdigest()
    assert components._sha256_ok(datei, summe) is True
    assert components._sha256_ok(datei, summe.upper()) is True
    assert components._sha256_ok(datei, "0" * 64) is False
    assert components._sha256_ok(datei, summe[:-1] + ("0" if summe[-1] != "0" else "1")) is False


def test_eine_falsche_summe_verwirft_den_download_und_loescht_die_datei(umgebung, monkeypatch):
    _definition_mit(monkeypatch, "0" * 64)
    erg = components.install_component(umgebung.db, "tesseract")
    assert erg["status"] == "fehler" and "verworfen" in erg["fehler"]
    assert umgebung.aufrufe.download, "geladen wurde (die Summe war formal gültig)"
    assert umgebung.aufrufe.start == [], "und gestartet wurde nichts"
    assert [p for p in umgebung.ordner.rglob("*") if p.is_file()] == []


def test_mit_der_richtigen_summe_kommt_der_installer_an_die_reihe(umgebung, monkeypatch):
    _definition_mit(monkeypatch, hashlib.sha256(b"x" * 1000).hexdigest())
    erg = components.install_component(umgebung.db, "tesseract")
    # das Testdoppel verbietet den echten Start: dass es erreicht wird, ist der Beweis, dass die Prüfung bestanden ist
    assert len(umgebung.aufrufe.start) == 1
    assert "kein Installer gestartet" in erg["fehler"]
    assert "Prüfsumme" not in erg["fehler"] and "verworfen" not in erg["fehler"]
