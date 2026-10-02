"""#1149 Punkt 13 (nur main) — die Texterkennung für Scan-PDFs braucht `pypdfium2` und `pillow`; der Installer muss sie holen.

Auf `main` rendert `services/ocr_service.py` die Seiten eines Scans mit `pypdfium2` (und `pillow`), bevor Tesseract sie
liest. In `pyproject.toml` stehen beide im Extra `[docs]`, aber `INSTALLIEREN.bat` installiert nicht die Extras, sondern
Pakete einzeln. Fehlt die Zeile dort, bleibt jede frische Windows-Installation ohne Scan-PDF-Erkennung — und niemand
merkt es, weil der Schritt „optional“ ist und der Rest der Installation grün endet. Die Rückführung des Hotfixes
(#1156) hat die Zeile eingefügt; dieser Test bewacht sie.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAT = (ROOT / "INSTALLIEREN.bat").read_text(encoding="utf-8", errors="replace")
PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
OCR = (ROOT / "src" / "bewerbungs_assistent" / "services" / "ocr_service.py").read_text(encoding="utf-8")


def _pip_zeile():
    zeilen = [z for z in BAT.splitlines() if "pip install" in z and "pypdfium2" in z]
    assert len(zeilen) == 1, f"genau eine Zeile mit pypdfium2 erwartet, gefunden: {len(zeilen)}"
    return zeilen[0]


def _spec(text, paket):
    treffer = re.search(rf'"{paket}([<>=!~][^"]*)"', text)
    assert treffer, f"{paket} fehlt"
    return treffer.group(1)


def test_der_installer_holt_pypdfium2_und_pillow():
    zeile = _pip_zeile()
    assert '"pypdfium2>=' in zeile and '"pillow>=' in zeile
    assert "--no-warn-script-location" in zeile and "%LOGFILE%" in zeile, "wie die übrigen optionalen Pakete"


def test_installer_und_pyproject_verlangen_dieselben_versionen():
    zeile = _pip_zeile()
    docs = PYPROJECT[PYPROJECT.index("docs = ["):PYPROJECT.index("export = [")]
    for paket in ("pypdfium2", "pillow"):
        assert _spec(zeile, paket) == _spec(docs, paket), paket


def test_der_schritt_ist_optional_und_beendet_den_installer_nicht():
    """Ein Fehler hier berührt PDF/Word und Excel nicht (eigener Schritt, nur eine Warnzeile)."""
    zeilen = BAT.splitlines()
    i = next(n for n, z in enumerate(zeilen) if "pip install" in z and "pypdfium2" in z)
    folge = " ".join(zeilen[i + 1:i + 3])
    assert "errorlevel! equ 0" in folge and "errorlevel! neq 0" in folge
    assert "exit" not in folge.lower() and "goto" not in folge.lower()


def test_der_dienst_braucht_genau_diese_pakete():
    assert "pypdfium2" in OCR, "der Dienst nutzt pypdfium2 nicht mehr - dann braucht der Installer die Zeile nicht"
    assert re.search(r"\bPIL\b|\bpillow\b", OCR, re.IGNORECASE), "pillow wird nicht mehr gebraucht"
