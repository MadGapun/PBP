"""Auto-Update (#1093): der Archiv-Bauer der Release-Routine und sein Schritt im Release-Tor.

Zwei Zusagen:

* Ein Archiv, das PBP selbst ablehnen wuerde, bleibt nirgends liegen. Es kaeme sonst an die Release,
  und alle Anwender mit Auto-Update bekaemen eine Fehlermeldung statt der neuen Version.
* Das Release-Tor (`release_check.py`) baut das Archiv aus dem Arbeitsbaum. Eine verbotene Datei im Paket
  (eine `.dll` oder `.exe` etwa) faellt dort auf — nicht erst nach dem Tag.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _au_hilfen import quellbaum  # noqa: E402
import build_update_archive as bau  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent


def test_ein_abgelehntes_archiv_bleibt_nicht_liegen(tmp_path):
    quell = quellbaum(tmp_path / "q", "1.8.1", extra_dateien={"src/bewerbungs_assistent/helfer.dll": b"MZ"})
    aus = tmp_path / "dist"
    with pytest.raises(Exception) as fehler:
        bau.bauen(ordner=quell, ausgabe=aus, ohne_signatur=True)
    assert getattr(fehler.value, "code", "") == "archiv_unsicher", repr(fehler.value)
    assert list(aus.iterdir()) == [], "weder das Archiv noch die Pruefsummenliste duerfen liegen bleiben"


def test_ein_sauberer_baum_ergibt_archiv_und_summenliste(tmp_path):
    quell = quellbaum(tmp_path / "q", "1.8.1")
    aus = tmp_path / "dist"
    erg = bau.bauen(ordner=quell, ausgabe=aus, ohne_signatur=True)
    assert sorted(p.name for p in aus.iterdir()) == ["SHA256SUMS", "pbp-update-1.8.1.zip"]
    assert erg["version"] == "1.8.1" and erg["signiert"] is False


def test_eine_vorabversion_laesst_sich_zum_erproben_bauen_und_wird_geprueft(tmp_path):
    """Das Release-Tor laeuft auch auf einer Beta; das Auto-Update wuerde sie nie installieren, der Bau muss trotzdem gehen."""
    quell = quellbaum(tmp_path / "q", "1.8.1-beta.2")
    aus = tmp_path / "dist"
    erg = bau.bauen(ordner=quell, ausgabe=aus, vorabversion=True, ohne_signatur=True)
    assert erg["version"] == "1.8.1-beta.2"
    assert (aus / "pbp-update-1.8.1-beta.2.zip").is_file()


def test_eine_vorabversion_ohne_die_erlaubnis_wird_nicht_gebaut(tmp_path):
    quell = quellbaum(tmp_path / "q", "1.8.1-beta.2")
    with pytest.raises(bau.BauFehler):
        bau.bauen(ordner=quell, ausgabe=tmp_path / "dist", ohne_signatur=True)


def test_eine_vorabversion_mit_verbotener_datei_wird_trotzdem_abgewiesen(tmp_path):
    """Der Erprobungsweg lockert nur das Manifest, nicht das sichere Entpacken."""
    quell = quellbaum(tmp_path / "q", "1.8.1-beta.2", extra_dateien={"src/bewerbungs_assistent/x.exe": b"MZ"})
    aus = tmp_path / "dist"
    with pytest.raises(Exception):
        bau.bauen(ordner=quell, ausgabe=aus, vorabversion=True, ohne_signatur=True)
    assert list(aus.iterdir()) == []


# ── Das Release-Tor ──────────────────────────────────────────────────────────────────────

def _release_check():
    import importlib.util
    spec = importlib.util.spec_from_file_location("release_check_fuer_test", WURZEL / "release_check.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_das_release_tor_hat_einen_schritt_fuer_das_update_archiv():
    rc = _release_check()
    assert hasattr(rc, "check_update_archiv"), "ein Schutz zaehlt erst, wenn er auch aufgerufen wird (DoD 8c)"
    haupt = (WURZEL / "release_check.py").read_text(encoding="utf-8")
    assert haupt.count("check_update_archiv(") >= 2, "definiert UND im Hauptablauf aufgerufen"


def test_das_release_tor_baut_das_archiv_des_echten_arbeitsbaums(tmp_path, monkeypatch):
    """Gegen den echten Quellbaum dieses Repositorys: nichts Verbotenes im Paket, das Archiv ist gueltig."""
    rc = _release_check()
    fehler = []
    monkeypatch.setattr(rc, "error", lambda msg: fehler.append(msg))
    monkeypatch.setattr(rc, "warn", lambda msg: None)
    monkeypatch.setattr(rc, "ok", lambda msg: None)
    from bewerbungs_assistent import __version__
    rc.check_update_archiv(__version__)
    assert fehler == [], fehler
