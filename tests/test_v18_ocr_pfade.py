"""Texterkennung (E19/#750): Pfade mit Zeichen ausserhalb der ANSI-Zeichentabelle (Benutzername mit ł, ş, ř ...).

Tesseract liest Dateipfade in der ANSI-Zeichentabelle des Rechners. Auf einem deutschen Windows-Rechner sind das cp1252:
ein Pfad mit »ł« kommt als »?« an, und es heisst "Error, cannot read input file ... Invalid argument" (Bilddatei im Temp-Ordner)
oder "Error opening data file ... tessdata" (Sprachdaten im Benutzerordner). Zwei Massnahmen:

* das Bild geht ueber die Standardeingabe (`tesseract stdin stdout`) -- kein Dateipfad, nichts zu uebersetzen,
* der tessdata-Ordner geht als Kurzpfad (8.3) in die Umgebung, sobald sein Pfad ein solches Zeichen enthaelt.

Die Tests mit dem echten Programm laufen nur, wo Tesseract installiert ist (Entwicklungsrechner); sonst werden sie uebersprungen.
"""
import os
import shutil
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "src"))

from bewerbungs_assistent.services import components, ocr_service  # noqa: E402

FREMD = "Łódź Şişli (Büro)"


def _kurzname(pfad: Path) -> str:
    """Der 8.3-Name, den Windows fuehrt (unabhaengig vom Programmcode, damit der Test ihn nicht mit sich selbst prueft)."""
    import ctypes
    puffer = ctypes.create_unicode_buffer(1024)
    n = ctypes.windll.kernel32.GetShortPathNameW(str(pfad), puffer, 1024)
    return puffer.value if n else str(pfad)


def _tesseract():
    kandidaten = [shutil.which("tesseract"), r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                  r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]
    for k in kandidaten:
        if k and Path(k).is_file() and (Path(k).parent / "tessdata" / "eng.traineddata").is_file():
            return Path(k)
    return None


# ══ Der Kurzpfad ═════════════════════════════════════════════════════════════════════════

def test_ein_pfad_den_die_zeichentabelle_kennt_bleibt_unveraendert(tmp_path):
    ordner = tmp_path / "Ölmühle Größe"
    ordner.mkdir()
    assert components._ansi_sicher(str(ordner)) == str(ordner)
    assert components._ansi_sicher("plain/ascii") == "plain/ascii"


@pytest.mark.skipif(sys.platform != "win32", reason="Kurzpfade (8.3) gibt es nur unter Windows")
def test_ein_pfad_mit_fremden_zeichen_wird_zum_ascii_kurzpfad_wo_das_laufwerk_kurznamen_fuehrt(tmp_path):
    ordner = tmp_path / FREMD
    ordner.mkdir()
    (ordner / "x.txt").write_text("x", encoding="utf-8")
    kurz = components._ansi_sicher(str(ordner))
    if kurz == str(ordner):
        pytest.skip("das Laufwerk fuehrt keine Kurznamen (8.3)")
    kurz.encode("mbcs")                                  # wirft nicht: die Zeichentabelle kennt jedes Zeichen
    assert os.path.samefile(kurz, ordner) and (Path(kurz) / "x.txt").is_file()


@pytest.mark.skipif(sys.platform != "win32", reason="Kurzpfade (8.3) gibt es nur unter Windows")
def test_ohne_moeglichen_kurzpfad_bleibt_der_pfad_wie_er_ist(tmp_path):
    """Ein Pfad, den es nicht gibt, hat keinen Kurznamen: der Fehler bleibt der alte, es wird nichts erfunden."""
    nicht_da = str(tmp_path / FREMD / "gibt es nicht")
    assert components._ansi_sicher(nicht_da) == nicht_da


def test_tessdata_geht_als_ansi_sicherer_pfad_in_die_umgebung(tmp_path, monkeypatch):
    td = tmp_path / FREMD / "tessdata"
    td.mkdir(parents=True)
    (td / "deu.traineddata").write_bytes(b"x")
    monkeypatch.setattr(components, "_tessdata_dir", lambda: td)
    monkeypatch.setattr(components, "_ansi_sicher", lambda p: "KURZ:" + p)
    assert components._ocr_env()["TESSDATA_PREFIX"] == "KURZ:" + str(td)


# ══ Die Texterkennung selbst ═════════════════════════════════════════════════════════════

def test_das_bild_geht_ueber_die_standardeingabe_nicht_ueber_eine_datei(tmp_path, monkeypatch):
    """Mit Testdoppel fuer Tesseract: das Kommando nennt `stdin`, die Bilddaten stehen im Aufruf, und es entsteht keine Bilddatei."""
    pytest.importorskip("pypdfium2")
    PIL = pytest.importorskip("PIL.Image")
    pdf = tmp_path / "scan.pdf"
    PIL.new("RGB", (400, 200), "white").save(str(pdf), "PDF", resolution=72)

    monkeypatch.setattr(ocr_service, "find_component_binary", lambda db, name: "C:/fake/tesseract.exe")
    monkeypatch.setattr(ocr_service, "_pick_langs", lambda db: ("eng", ""))
    monkeypatch.setattr(ocr_service, "get_component_status", lambda db, name: {"version": "5.4.0"})
    gesehen = []

    def fake_run(cmd, **kw):
        gesehen.append((cmd, kw))
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout="Text".encode("utf-8"), stderr=b"")

    monkeypatch.setattr(ocr_service.subprocess, "run", fake_run)
    erg = ocr_service.ocr_pdf(None, pdf)
    assert erg["status"] == "ok" and erg["text"] == "Text"
    cmd, kw = gesehen[0]
    assert cmd[1] == "stdin" and cmd[2] == "stdout"
    assert kw["input"][:8] == b"\x89PNG\r\n\x1a\n", "die Bilddaten gehen als PNG in die Standardeingabe"
    assert not list(tmp_path.glob("**/seite_*.png")) and "text" not in kw and "encoding" not in kw


@pytest.mark.skipif(_tesseract() is None, reason="Tesseract ist hier nicht installiert")
def test_echte_texterkennung_mit_sprachdaten_in_einem_ordner_mit_fremden_zeichen(tmp_path, monkeypatch):
    pytest.importorskip("pypdfium2")
    PIL = pytest.importorskip("PIL.Image")
    ImageDraw = pytest.importorskip("PIL.ImageDraw")
    ImageFont = pytest.importorskip("PIL.ImageFont")
    exe = _tesseract()

    # Sprachdaten NUR im Ordner mit fremden Zeichen (so liegen die nachgeladenen Sprachen im Benutzerordner)
    td = tmp_path / FREMD / "tessdata"
    td.mkdir(parents=True)
    for name in ("eng.traineddata", "osd.traineddata"):
        if (exe.parent / "tessdata" / name).is_file():
            shutil.copy2(exe.parent / "tessdata" / name, td / name)
    monkeypatch.delenv("TESSDATA_PREFIX", raising=False)
    monkeypatch.setattr(components, "_tessdata_dir", lambda: td)

    seite = PIL.new("RGB", (1100, 200), "white")
    try:
        schrift = ImageFont.truetype("arial.ttf", 64)
    except OSError:
        pytest.skip("keine Schrift zum Zeichnen des Testbildes")
    ImageDraw.Draw(seite).text((30, 50), "Bewerbung Probe 2026", fill="black", font=schrift)
    pdf = tmp_path / FREMD / "scan.pdf"
    seite.save(str(pdf), "PDF", resolution=72)

    monkeypatch.setattr(ocr_service, "find_component_binary", lambda db, name: str(exe))
    monkeypatch.setattr(ocr_service, "_pick_langs", lambda db: ("eng", ""))
    monkeypatch.setattr(ocr_service, "get_component_status", lambda db, name: {"version": "5.x"})
    if sys.platform == "win32" and _kurzname(td) == str(td):
        pytest.skip("das Laufwerk fuehrt keine Kurznamen (8.3): der Ausweg greift hier nicht")
    erg = ocr_service.ocr_pdf(None, pdf)
    assert erg["status"] == "ok", erg
    assert "Bewerbung" in erg["text"]
