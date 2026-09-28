"""Jede Quelldatei laesst sich mit der kleinsten unterstuetzten Python-
Version kompilieren.

`pyproject.toml` verspricht `requires-python = ">=3.11"`, und die
Installer fuer macOS und Linux nehmen 3.11 an. Die CI laeuft aber mit 3.13
— dort ist ein Backslash im Ausdruck eines f-Strings erlaubt (PEP 701),
unter 3.11 ein SyntaxError. So stand in `dashboard.py` eine Zeile, mit der
das Dashboard unter 3.11 gar nicht startete, und kein Test sah es.

`ast.parse(feature_version=(3, 11))` findet genau diesen Fall NICHT
(gemessen mit 3.13) — deshalb kompiliert der Test mit einem echten
3.11-Interpreter. Fehlt der, wird uebersprungen; die CI hat dafuer einen
eigenen Job mit 3.11 (.github/workflows/tests.yml, `syntax-py311`).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ORDNER = ["src", "scripts"]


def _py311() -> str | None:
    if sys.version_info[:2] == (3, 11):
        return sys.executable
    return shutil.which("python3.11")


def test_quellen_kompilieren_mit_python_311():
    py = _py311()
    if not py:
        pytest.skip("Kein Python 3.11 vorhanden (CI prueft im Job syntax-py311)")
    code = (
        "import pathlib, sys\n"
        "fehler = []\n"
        "for ordner in sys.argv[1:]:\n"
        "    for p in sorted(pathlib.Path(ordner).rglob('*.py')):\n"
        "        try:\n"
        "            compile(p.read_text(encoding='utf-8-sig'), str(p), 'exec')\n"
        "        except SyntaxError as e:\n"
        "            fehler.append(f'{p}:{e.lineno}: {e.msg}')\n"
        "print('\\n'.join(fehler))\n"
        "sys.exit(1 if fehler else 0)\n"
    )
    res = subprocess.run(
        [py, "-c", code, *[str(REPO / o) for o in ORDNER]],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, (
        "Unter Python 3.11 nicht kompilierbar:\n" + res.stdout + res.stderr)
