"""v1.7.145 — der Windows-Installer installiert, was pyproject.toml verlangt.

Befund (01.10.2026, Prueferbericht Installation): INSTALLIEREN.bat rief
`pip install fastmcp uvicorn ...` OHNE Versionsgrenze auf. Seit FastMCP 4
auf PyPI liegt (Hauptfassung 4.0, Folgefassungen bis 4.0.10 im September
2026), holt eine frische Windows-Installation eine Hauptfassung, die
pyproject.toml ausschliesst (`fastmcp>=3.0,<4`). Mac und Linux installieren
mit `pip install -e .` und halten sich daran. Dazu fehlten openpyxl (Excel-
Export im Statistik-Tab) und matplotlib (Diagramme) in der Windows-Liste:
der Excel-Knopf lieferte eine Fehlermeldung mit pip-Anweisung.
"""
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAT = ROOT / "INSTALLIEREN.bat"


def _pyproject():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def _pip_zeilen():
    text = BAT.read_text(encoding="utf-8")
    return [z.strip() for z in text.splitlines()
            if "-m pip install" in z and not z.lstrip().startswith("::")
            and "--upgrade pip" not in z and "echo" not in z.lower()[:12]]


def _bat_specs():
    specs = []
    for zeile in _pip_zeilen():
        specs += re.findall(r'"([^"]+)"', zeile.split("pip install", 1)[1])
    return specs


def test_die_windows_liste_nennt_alle_kernpakete_mit_denselben_grenzen():
    fehlen = [s for s in _pyproject()["dependencies"] if s not in _bat_specs()]
    assert not fehlen, f"in INSTALLIEREN.bat ohne/mit anderer Grenze: {fehlen}"


def test_die_windows_liste_nennt_alle_optionalen_pakete_der_extras():
    extras = _pyproject()["optional-dependencies"]
    erwartet = [s for gruppe in ("scraper", "docs", "export", "email") for s in extras[gruppe]]
    fehlen = [s for s in erwartet if s not in _bat_specs()]
    assert not fehlen, f"Extras fehlen in INSTALLIEREN.bat: {fehlen}"


def test_fastmcp_wird_nie_ohne_obergrenze_installiert():
    for zeile in _pip_zeilen():
        if "fastmcp" in zeile:
            assert '"fastmcp>=3.0,<4"' in zeile, zeile
    assert any("fastmcp" in z for z in _pip_zeilen())


def test_kein_paket_der_liste_steht_ohne_versionsangabe():
    """Ausnahmen sind die Bau-Werkzeuge, die pyproject nicht kennt."""
    ohne = []
    for zeile in _pip_zeilen():
        rest = zeile.split("pip install", 1)[1]
        for wort in rest.replace('"', " ").split():
            if wort.startswith("-") or wort.startswith(">") or wort in ("setuptools", "wheel"):
                continue
            if wort.startswith("%") or wort.startswith("2>"):
                continue
            if not re.search(r"[<>=]", wort) and re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]*", wort):
                ohne.append(wort)
    assert not ohne, f"ohne Versionsangabe: {ohne}"


def test_excel_und_diagramme_haben_einen_eigenen_optionalen_schritt():
    """Ein Fehler beim Installieren von matplotlib darf den PDF/Word-Export nicht mitnehmen."""
    zeilen = _pip_zeilen()
    mit_excel = [z for z in zeilen if "openpyxl" in z]
    assert len(mit_excel) == 1
    assert "python-docx" not in mit_excel[0] and "fpdf2" not in mit_excel[0]
