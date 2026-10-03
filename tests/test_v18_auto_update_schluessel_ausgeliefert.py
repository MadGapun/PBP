"""Auto-Update (#1093): die ausgelieferten oeffentlichen Schluessel stehen im Code, und der geheime steht nirgends im Repository.

Die Suite setzt die vertrauten Schluessel je Test auf eine leere Liste (`conftest.py`), damit Archive ohne Signatur gebaut werden koennen.
Das hier prueft das Gegenstueck: was im QUELLTEXT von `schluessel.py` steht -- also das, was ein Nutzer bekommt.

* Hauptschluessel und Notfallschluessel sind eingetragen, verschieden und gueltig (64 Hex-Zeichen = 32 Byte, ein Punkt der Kurve).
* Damit ist die Signatur Pflicht: ohne `SHA256SUMS.sig` wird nichts installiert.
* Keine Datei, die zum Repository gehoert, sieht nach einem geheimen Schluessel aus (`*.hex`), und `schluessel.py` nennt keinen Pfad zu einem.
"""
import ast
import re
import subprocess
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "src" / "bewerbungs_assistent" / "services" / "auto_update" / "schluessel.py"

from bewerbungs_assistent.services.auto_update import ed25519, schluessel  # noqa: E402


def _ausgeliefert() -> dict:
    """Der Wert von VERTRAUTE_SCHLUESSEL, wie er im Quelltext steht."""
    baum = ast.parse(QUELLE.read_text(encoding="utf-8"))
    for knoten in baum.body:
        ziel = knoten.targets[0] if isinstance(knoten, ast.Assign) else getattr(knoten, "target", None)
        if getattr(ziel, "id", "") == "VERTRAUTE_SCHLUESSEL":
            return ast.literal_eval(knoten.value)
    raise AssertionError("VERTRAUTE_SCHLUESSEL steht nicht in schluessel.py")


def test_hauptschluessel_und_notfallschluessel_sind_eingetragen():
    s = _ausgeliefert()
    assert set(s) == {"haupt", "notfall"}, "genau zwei Schluessel: der auf dem Build-Rechner und der Notfallschluessel"


def test_beide_schluessel_sind_gueltige_32_byte_und_verschieden():
    s = _ausgeliefert()
    for name, hexwert in s.items():
        assert re.fullmatch(r"[0-9a-f]{64}", hexwert), f"{name}: kein Hex mit 64 Zeichen"
    assert s["haupt"] != s["notfall"], "der Notfallschluessel darf nicht der Hauptschluessel sein"
    assert len(schluessel.schluessel_bytes(s)) == 2, "beide fallen nicht als ungueltig heraus"


def test_beide_schluessel_sind_punkte_der_kurve():
    """Ein Schluessel, der nie ein Punkt war (Tippfehler), wuerde jede Signatur ablehnen -- und das Update fuer alle sperren."""
    for name, roh in schluessel.schluessel_bytes(_ausgeliefert()).items():
        assert ed25519._dekomprimieren(roh) is not None, f"{name}: kein Punkt der Kurve"
        assert ed25519.pruefen(roh, b"x", bytes(64)) is False, f"{name}: eine leere Signatur darf nie gelten"


def test_mit_den_ausgelieferten_schluesseln_ist_die_signatur_pflicht():
    assert schluessel.signatur_erforderlich(_ausgeliefert()) is True


def test_kein_geheimer_schluessel_im_repository():
    """Der geheime Schluessel ist eine Datei mit 64 Hex-Zeichen (`update_schluessel.py erzeugen`). Sie gehoert nie ins Repository."""
    try:
        r = subprocess.run(["git", "ls-files"], cwd=str(WURZEL), capture_output=True, text=True, encoding="utf-8", timeout=60)
        dateien = r.stdout.split("\n") if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        dateien = None
    if dateien is None:
        pytest.skip("kein git im Pfad")
    verdaechtig = [d for d in dateien if d.lower().endswith(".hex")]
    assert not verdaechtig, f"Dateien mit Endung .hex im Repository: {verdaechtig}"
    assert "PBP-Signatur" not in QUELLE.read_text(encoding="utf-8"), "schluessel.py nennt den Ablageort des geheimen Schluessels"
