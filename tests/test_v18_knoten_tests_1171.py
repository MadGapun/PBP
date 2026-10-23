"""Die Knoten-Tests der Rechnungen hinter der Bedienung laufen auch unter pytest (#1171, #1170).

Die Regeln ohne Zeichnung stehen in `frontend/src/lib/*.js` und werden in der CI als eigene Schritte mit `node` geprueft. Ein Lauf von
`pytest` ueberspringt diese Schritte — ein Fehler dort faellt dann erst auf dem Server auf, und die Gegenprobe (jeder Eingriff einzeln
muss einen Test rot machen) sieht ihn nie. Dieser Test ruft dieselben Dateien auf; ohne `node` wird er uebersprungen.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LIB = REPO / "frontend" / "src" / "lib"
NODE = shutil.which("node")

# die Rechnungen der Wege (#1171) und der Bedienungspruefung (#1170); der Elwosa-Strom: was neu ist (#1256)
KNOTEN_TESTS = ["wege", "wegleiste", "firmen", "erklaertexte", "seitenleiste", "uploadHinweis", "elwosaStrom"]


@pytest.mark.parametrize("name", KNOTEN_TESTS)
def test_knoten_test_ist_gruen(name):
    datei = LIB / f"{name}.test.mjs"
    assert datei.is_file(), f"{datei} fehlt"
    if not NODE:
        pytest.skip("node ist nicht installiert")
    ergebnis = subprocess.run([NODE, str(datei)], capture_output=True, text=True, timeout=120, cwd=str(REPO))
    assert ergebnis.returncode == 0, f"{name}.test.mjs ist rot:\n{ergebnis.stdout}\n{ergebnis.stderr}"
    assert "ok" in ergebnis.stdout, f"{name}.test.mjs meldet kein „ok“: {ergebnis.stdout!r}"


def test_jede_rechnung_steht_in_der_ci():
    """Ein Knoten-Test, der nur lokal laeuft, ist keiner: jede Datei der Liste steht als Schritt in der CI."""
    workflow = (REPO / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    fehlend = [n for n in KNOTEN_TESTS if f"frontend/src/lib/{n}.test.mjs" not in workflow]
    assert not fehlend, f"nicht in der CI: {fehlend}"
