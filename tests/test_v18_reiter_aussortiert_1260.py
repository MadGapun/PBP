"""#1260: Texte nennen den Reiter der Stellen-Seite so, wie er heisst („Aussortiert“).

Der Reiter mit den aussortierten Stellen heisst „Aussortiert“; fuenf Texte im Dashboard und zwei Antworten an Claude
schickten Anwender nach „Stellen › Ausgeblendet“, einen Namen, den es als Beschriftung nicht gibt. Kommentare im Code
duerfen das alte Wort behalten, sichtbare Texte nicht.
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
FRONTEND = WURZEL / "frontend" / "src"
PAKET = WURZEL / "src" / "bewerbungs_assistent"
BUNDLE = PAKET / "static" / "dashboard" / "assets"
FALSCHER_WEG = "Stellen › Ausgeblendet"


def _ohne_kommentare_js(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(zeile for zeile in text.splitlines() if not zeile.strip().startswith("//"))


def _ohne_kommentare_py(text: str) -> str:
    return "\n".join(zeile for zeile in text.splitlines() if not zeile.strip().startswith("#"))


def test_reiter_heisst_aussortiert():
    seite = (FRONTEND / "pages" / "JobsPage.jsx").read_text(encoding="utf-8")
    assert '["dismissed", "Aussortiert"' in seite, "Der Reiter der aussortierten Stellen heisst nicht mehr „Aussortiert“: Texte angleichen"


def test_frontend_nennt_keinen_reiter_ausgeblendet():
    funde = []
    for datei in sorted(FRONTEND.rglob("*")):
        if datei.suffix not in {".js", ".jsx", ".mjs"}:
            continue
        if FALSCHER_WEG in _ohne_kommentare_js(datei.read_text(encoding="utf-8")):
            funde.append(str(datei.relative_to(WURZEL)))
    assert not funde, f"„{FALSCHER_WEG}“ gibt es nicht, der Reiter heisst „Aussortiert“: {funde}"


def test_antworten_an_claude_nennen_keinen_reiter_ausgeblendet():
    funde = []
    for datei in sorted(PAKET.rglob("*.py")):
        if FALSCHER_WEG in _ohne_kommentare_py(datei.read_text(encoding="utf-8")):
            funde.append(str(datei.relative_to(WURZEL)))
    assert not funde, f"„{FALSCHER_WEG}“ gibt es nicht, der Reiter heisst „Aussortiert“: {funde}"


def test_gebautes_bundle_nennt_keinen_reiter_ausgeblendet():
    dateien = sorted(BUNDLE.glob("*.js"))
    assert dateien, "kein gebautes Bundle gefunden"
    funde = [d.name for d in dateien if FALSCHER_WEG in d.read_text(encoding="utf-8")]
    assert not funde, f"Das ausgelieferte Bundle nennt noch „{FALSCHER_WEG}“ (neu bauen): {funde}"
