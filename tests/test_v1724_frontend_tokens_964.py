"""Tests fuer v1.7.24 — #964: Farbtokens, die es nicht gibt.

Das Detail-Overlay im Aufgaben-Tab war durchscheinend: der Listeninhalt
dahinter blieb lesbar und ueberlagerte den Aufgabentext. Ursache war
kein zu niedriger Transparenzwert, sondern eine FEHLENDE Deklaration —
das Panel trug `bg-bg`, und das Token `bg` existiert im Design-System
nicht.

Der Punkt, warum das ein eigener Test wert ist: **Tailwind erzeugt fuer
eine unbekannte Farbe keine Regel und meldet auch keinen Fehler.** Der
Build ist gruen, die Klasse steht im HTML, und sie tut nichts. Dieselbe
Ursache traf die Fehlermeldung der Seite (`text-danger`, `bg-danger/10`)
— die wurde damit praktisch unsichtbar ausgegeben, was nur deshalb nicht
auffiel, weil der Fehlerfall selten eintritt.

Genau die Sorte Fehler, die ein Mensch beim Lesen nicht sieht: die
Klasse sieht plausibel aus. Deshalb hier maschinell, ueber das ganze
Frontend statt nur ueber die eine Seite.
"""
import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1] / "frontend"
CONFIG = WURZEL / "tailwind.config.js"
QUELLEN = sorted((WURZEL / "src").rglob("*.jsx"))

# Tailwinds mitgelieferte Palette. Diese Namen tragen Abstufungen
# (blue-500); die Projekt-Tokens sind flache Farben ohne Abstufung.
TAILWIND_PALETTE = {
    "slate", "gray", "zinc", "neutral", "stone", "red", "orange", "amber",
    "yellow", "lime", "green", "emerald", "teal", "cyan", "sky", "blue",
    "indigo", "violet", "purple", "fuchsia", "pink", "rose",
}
SCHLUESSELWORTE = {
    "white", "black", "transparent", "current", "inherit", "auto", "none",
}

# Utilities, deren Suffix eine FARBE ist. bewusst ohne bg-gradient,
# bg-clip, text-sm & Co — die tragen keine Farbe.
PRAEFIXE = ("bg", "text", "border", "ring", "fill", "stroke", "decoration",
            "outline", "divide", "accent", "caret", "placeholder", "shadow")

_KLASSE = re.compile(
    r"\b(?:hover:|focus:|active:|group-hover:|disabled:|dark:|md:|lg:|sm:|xl:)*"
    r"(" + "|".join(PRAEFIXE) + r")-"
    r"([a-z][a-z0-9]*)"
    r"(?:-(\d{2,3}))?"
    r"(?:/\d{1,3})?\b"
)


# Richtungs- und Struktur-Suffixe: `border-t` ist eine Kante, keine
# Farbe. `ring-offset` ebenso.
STRUKTUR = {"t", "b", "l", "r", "x", "y", "s", "e", "offset", "spacing"}

_KOMMENTAR = re.compile(r"/\*.*?\*/|(?<!:)//[^\n]*", re.DOTALL)


# Tailwinds Freiwert-Syntax: transition-[border-color,...] enthaelt
# CSS-Eigenschaften, keine Farbklassen.
_FREIWERT = re.compile(r"\[[^\]]*\]")


def _ohne_kommentare(text: str) -> str:
    """Kommentare und Freiwerte ausblenden — sonst schlaegt der Guard
    auf seiner eigenen Fehlerbeschreibung an oder auf CSS-Eigenschaften
    in eckigen Klammern."""
    text = _KOMMENTAR.sub(lambda m: " " * len(m.group()), text)
    return _FREIWERT.sub(lambda m: " " * len(m.group()), text)


def _projekt_tokens() -> set[str]:
    text = CONFIG.read_text(encoding="utf-8")
    block = text[text.index("colors:"):]
    block = block[:block.index("}") + 1]
    return set(re.findall(r"^\s*([a-z][a-z0-9]*):\s*\"", block, re.MULTILINE))


@pytest.fixture(scope="module")
def tokens():
    t = _projekt_tokens()
    assert t, "Farbtokens aus tailwind.config.js nicht lesbar"
    return t


def test_964_config_kennt_die_erwarteten_tokens(tokens):
    """Absicherung des Tests selbst: liest er die Config richtig?

    Ohne diese Gegenprobe koennte der Guard bei leerer Token-Menge
    stillschweigend nichts pruefen — derselbe Fehlertyp, den er sucht.
    """
    for pflicht in ("shell", "panel", "panelstrong", "ink", "muted",
                    "line", "teal", "amber", "coral", "sky"):
        assert pflicht in tokens, tokens
    assert "bg" not in tokens
    assert "danger" not in tokens


def test_964_keine_farbklasse_ohne_deklaration(tokens):
    """Der eigentliche Guard ueber das ganze Frontend."""
    erlaubt = tokens | TAILWIND_PALETTE | SCHLUESSELWORTE
    befunde = []
    for datei in QUELLEN:
        inhalt = _ohne_kommentare(datei.read_text(encoding="utf-8"))
        for nr, zeile in enumerate(inhalt.split("\n"), 1):
            for praefix, basis, _ in _KLASSE.findall(zeile):
                if basis in erlaubt or basis in STRUKTUR:
                    continue
                # Nicht-Farb-Utilities mit gleichem Praefix aussortieren
                # (text-xs, border-2, shadow-lg, ...).
                if basis in ("xs", "sm", "base", "lg", "xl", "left", "right",
                             "center", "justify", "start", "end", "wrap",
                             "nowrap", "ellipsis", "clip", "balance",
                             "pretty", "solid", "dashed", "dotted", "double",
                             "hidden", "collapse", "separate", "inner",
                             "opacity", "gradient", "top", "bottom", "y", "x"):
                    continue
                befunde.append(
                    f"{datei.relative_to(WURZEL)}:{nr}  {praefix}-{basis}")
    assert not befunde, (
        "Farbklassen ohne Deklaration — Tailwind erzeugt dafuer keine "
        "Regel UND keinen Fehler:\n  " + "\n  ".join(sorted(set(befunde))))


def test_964_projekt_tokens_ohne_abstufung(tokens):
    """`bg-amber-400` ist kein Schoenheitsfehler.

    Die Projekt-Tokens sind flache Farben. Sobald `amber` in
    extend.colors als Zeichenkette steht, verdraengt es Tailwinds
    Abstufungen — `text-amber-400` loest dann ebenfalls ins Leere auf.
    """
    befunde = []
    for datei in QUELLEN:
        inhalt = _ohne_kommentare(datei.read_text(encoding="utf-8"))
        for nr, zeile in enumerate(inhalt.split("\n"), 1):
            for praefix, basis, schattierung in _KLASSE.findall(zeile):
                if schattierung and basis in tokens:
                    befunde.append(
                        f"{datei.relative_to(WURZEL)}:{nr}  "
                        f"{praefix}-{basis}-{schattierung}")
    assert not befunde, (
        "Projekt-Token mit Abstufung angesprochen:\n  "
        + "\n  ".join(sorted(set(befunde))))


# ── Befund 2 und 3: die Zusagen aus dem Issue ────────────────────────

def _tasks_page() -> str:
    return (WURZEL / "src" / "pages" / "TasksPage.jsx").read_text(encoding="utf-8")


def test_964_kennung_ist_qualifiziert():
    """Eine nackte ID reicht nicht: Aufgaben und Nachfassungen sind
    beide achtstellig hexadezimal und damit nicht unterscheidbar. Wer
    nur 'cf8dffcf' kopiert, weiss nicht, ob todo_bearbeiten oder
    follow_up_bearbeiten zustaendig ist."""
    quelle = _tasks_page()
    assert "function kennung(" in quelle
    assert "HERKUNFT_BADGE[e?.herkunft]" in quelle


def test_964_kopierknopf_ist_immer_da():
    """Vorher wurde er nur bei vorhandenem claude_prompt gerendert — und
    den gibt es im echten Bestand nur fuer Nachfassungen. Auf einer frei
    angelegten Aufgabe gab es gar keinen Kopier-Knopf."""
    quelle = _tasks_page()
    assert "{e.claude_prompt ? (" not in quelle, (
        "Der Knopf haengt wieder an claude_prompt")
    assert "kennung(e)" in quelle


def test_964_overlay_ist_bearbeitbar():
    """Offene Zusage aus #814: Titel, Beschreibung und Typ sollten
    nachtraeglich aenderbar sein. Die MCP-Seite konnte das laengst."""
    quelle = _tasks_page()
    assert "setBearbeiten(" in quelle
    assert "Bearbeiten" in quelle


def test_964_bearbeiten_trifft_den_richtigen_endpunkt():
    """Die drei Toepfe liegen in getrennten Tabellen. Ein Nachfass an
    PATCH /api/tasks zu schicken ergaebe ein stilles 404 — gespeichert,
    nichts passiert."""
    quelle = _tasks_page()
    assert 'detail.herkunft === "nachfass"' in quelle
    assert "/api/follow-ups/" in quelle
    # Termine haben keinen REST-Weg — dort wird nichts angeboten.
    assert 'detail.herkunft !== "termin"' in quelle


def test_964_overlay_laeuft_nicht_ueber():
    """Lange Beschreibungen sollen im Panel bleiben."""
    quelle = _tasks_page()
    assert "max-h-[85vh]" in quelle
    assert "overflow-y-auto" in quelle
