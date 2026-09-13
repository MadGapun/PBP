"""Tests fuer #1043 (G48): Deckkraft-Stufen, die Tailwind nicht erzeugt.

`border-white/8` erzeugte keine CSS-Regel: Tailwind 3.4 kennt fuer den
Deckkraft-Modifikator nur die Stufen seiner `opacity`-Skala (0, 5, 10,
15 ...). Eine fehlende Stufe ist kein Fehler im Build — die Klasse steht
im HTML und tut nichts, und bei `border` greift dann die Grundregel
`border: 0 solid #e5e7eb`, ein voll deckendes Hellgrau. Gemessen am
14.09.2026: 13 von 149 Deckkraft-Klassen fehlten im ausgelieferten CSS.

Dieselbe Klasse wie #964 (unbekannte Farbe) — der dortige Guard prueft
aber nur Farbnamen, keine Stufen.
"""
import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "frontend"
CONFIG = FRONTEND / "tailwind.config.js"
ASSETS = WURZEL / "src" / "bewerbungs_assistent" / "static" / "dashboard" / "assets"

#: Tailwinds mitgelieferte `opacity`-Skala (3.4).
STANDARD_STUFEN = {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65,
                   70, 75, 80, 85, 90, 95, 100}

PRAEFIXE = ("bg", "text", "border", "ring", "fill", "stroke", "decoration",
            "outline", "divide", "accent", "caret", "placeholder", "shadow",
            "from", "via", "to")

#: Farbklasse mit Deckkraft-Stufe, samt Variante (hover:, focus: ...).
#: Freiwerte wie `bg-white/[0.03]` sind ausgenommen — sie brauchen keine
#: Skala.
_KLASSE = re.compile(
    r"(?<![\w/-])((?:[a-z-]+:)*)"
    r"((?:" + "|".join(PRAEFIXE) + r")-[a-z][a-z0-9]*(?:-\d{2,3})?)"
    r"/(\d{1,3})(?![\w\[.])"
)
_KOMMENTAR = re.compile(r"/\*.*?\*/|(?<!:)//[^\n]*", re.DOTALL)

#: Farben ohne Kanalwerte — ein Deckkraft-Modifikator erzeugt dort nichts.
OHNE_KANAELE = {"current", "transparent", "inherit"}


def _quellen():
    return sorted(list((FRONTEND / "src").rglob("*.jsx"))
                  + list((FRONTEND / "src").rglob("*.js")))


def _verwendet() -> dict:
    """{(klasse, stufe): [fundstellen]} ueber das ganze Frontend."""
    funde: dict = {}
    for datei in _quellen():
        text = _KOMMENTAR.sub(lambda m: " " * len(m.group()),
                              datei.read_text(encoding="utf-8"))
        for nr, zeile in enumerate(text.split("\n"), 1):
            for _variante, klasse, stufe in _KLASSE.findall(zeile):
                funde.setdefault((klasse, int(stufe)), []).append(
                    f"{datei.relative_to(FRONTEND)}:{nr}")
    return funde


def _erweiterte_stufen() -> set:
    text = CONFIG.read_text(encoding="utf-8")
    if "opacity:" not in text:
        return set()
    block = text[text.index("opacity:"):]
    block = block[:block.index("}")]
    return {int(s) for s in re.findall(r"^\s*(\d+)\s*:", block, re.MULTILINE)}


def test_der_guard_findet_ueberhaupt_etwas():
    """Gegenprobe des Tests selbst: ohne Funde prueft er stillschweigend
    nichts — derselbe Fehlertyp, den er sucht."""
    funde = _verwendet()
    assert len(funde) > 50, len(funde)
    assert ("border-white", 8) in funde


def test_config_erweitert_die_skala_um_die_verwendeten_stufen():
    assert {4, 6, 7, 8, 12} <= _erweiterte_stufen()


def test_jede_verwendete_stufe_wird_erzeugt():
    """Der eigentliche Guard: eine Stufe ausserhalb der Skala gibt es nur,
    wenn die Config sie ergaenzt."""
    erlaubt = STANDARD_STUFEN | _erweiterte_stufen()
    befunde = sorted(
        f"{stellen[0]}  {klasse}/{stufe}"
        for (klasse, stufe), stellen in _verwendet().items()
        if stufe not in erlaubt)
    assert not befunde, (
        "Deckkraft-Stufe ohne Regel — Tailwind erzeugt dafuer nichts:\n  "
        + "\n  ".join(befunde))


def test_keine_deckkraft_auf_farben_ohne_kanaele():
    """`text-current/50` erzeugt nichts: currentColor hat keine Kanalwerte."""
    befunde = sorted(
        f"{stellen[0]}  {klasse}/{stufe}"
        for (klasse, stufe), stellen in _verwendet().items()
        if klasse.split("-", 1)[1] in OHNE_KANAELE)
    assert not befunde, "\n  ".join(befunde)


@pytest.mark.skipif(not any(ASSETS.glob("*.css")) if ASSETS.exists() else True,
                    reason="kein gebautes CSS vorhanden")
def test_jede_verwendete_klasse_steht_im_gebauten_css():
    """Die Skala allein ist eine Annahme ueber Tailwind — das ausgelieferte
    CSS ist der Beleg. Gesucht wird der escapte Klassenname als Teilstring,
    damit Varianten (`hover:`) mitgefunden werden."""
    css = "".join(p.read_text(encoding="utf-8") for p in ASSETS.glob("*.css"))
    rueckstrich = chr(92)
    befunde = sorted(
        f"{stellen[0]}  {klasse}/{stufe}"
        for (klasse, stufe), stellen in _verwendet().items()
        if f"{klasse}{rueckstrich}/{stufe}" not in css)
    assert not befunde, (
        "Im Frontend verwendet, im gebauten CSS nicht vorhanden:\n  "
        + "\n  ".join(befunde))
