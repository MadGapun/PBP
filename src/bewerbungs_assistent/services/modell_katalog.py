"""Welche lokalen Modelle PBP empfiehlt — mit Stand und Nachfolgern (#785).

## Befund

Der Katalog stand seit Ende 2024 unveraendert im Endpunkt: Llama 3.2 3B,
Qwen 2.5 7B, Qwen 2.5 14B. Seitdem ist eine Modellgeneration erschienen,
die bei gleichem Speicherbedarf besser Deutsch kann — und nichts im
Produkt sagte, dass der Katalog alt ist.

## Was hier steht

- **Der Katalog mit Stand-Datum.** Groessen nachgemessen am 13.09.2026
  auf ollama.com (Tag-Seiten der Modelle), nicht aus dem Issue
  uebernommen: qwen3:4b 2,5 GB, qwen3:8b 5,2 GB, qwen3:14b 9,3 GB.
- **Vorgaenger -> Nachfolger.** Ein Bestandsnutzer bekommt einen
  Hinweis, keinen Download und keine Umstellung.
- **`veraltet()`** fuer den Release-Check: ein Katalog, der aelter als
  sechs Monate ist, wird gemeldet. Ein Einmal-Fix waere in einem Jahr
  derselbe Befund.

## Eine Grenze, die hier dazugehoert

Die Qwen3-Reihe hat einen Denkmodus: in der Vorgabe steht vor der
Antwort ein `<think>`-Block. PBPs Auswertungen erwarten die Antwort
selbst. `llm_service` schaltet den Modus deshalb ab (`think: false`)
UND entfernt einen trotzdem gelieferten Block — aeltere Ollama-Versionen
kennen den Schalter nicht. Ein echter Lauf mit einem Qwen3-Modell liess
sich beim Bau nicht pruefen (kein Modell geladen); das steht so im
Changelog.
"""
from __future__ import annotations

from datetime import date

#: Monat, in dem der Katalog zuletzt gegen ollama.com geprueft wurde.
STAND = "2026-09"
#: Nach dieser Zeit meldet der Release-Check den Katalog als veraltet.
HOECHSTALTER_MONATE = 6

KATALOG = [
    {
        "id": "qwen3:4b",
        "label": "Klein",
        "name": "Qwen3 4B",
        "size_gb": 2.5,
        "ram_gb": 8,
        "description": "Läuft auf jedem PC mit 8 GB RAM",
    },
    {
        "id": "qwen3:8b",
        "label": "Standard (empfohlen)",
        "name": "Qwen3 8B",
        "size_gb": 5.2,
        "ram_gb": 16,
        "description": "Empfohlen, gutes Deutsch, läuft mit 16 GB RAM",
        "recommended": True,
    },
    {
        "id": "qwen3:14b",
        "label": "Gross",
        "name": "Qwen3 14B",
        "size_gb": 9.3,
        "ram_gb": 32,
        "description": "Power-User mit dedizierter GPU",
    },
]

#: Vorgaenger -> Nachfolger. Schluessel ohne Tag gelten fuer `:latest`.
NACHFOLGER = {
    "llama3.2:3b": "qwen3:4b",
    "llama3.2": "qwen3:4b",
    "qwen2.5:3b": "qwen3:4b",
    "qwen2.5:7b": "qwen3:8b",
    "qwen2.5": "qwen3:8b",
    "qwen2.5:14b": "qwen3:14b",
}


def _kurzform(modell: str) -> str:
    """"qwen2.5:7b-instruct-q4_K_M" -> "qwen2.5:7b", "qwen2.5:latest" -> "qwen2.5"."""
    name = (modell or "").strip().lower()
    if ":" not in name:
        return name
    basis, tag = name.split(":", 1)
    if tag in ("", "latest"):
        return basis
    return f"{basis}:{tag.split('-', 1)[0]}"


def nachfolger_fuer(modell: str) -> dict | None:
    """Der Katalog-Eintrag, der ein Vorgaengermodell abloest — oder None."""
    ziel = NACHFOLGER.get(_kurzform(modell))
    if not ziel:
        return None
    eintrag = next((m for m in KATALOG if m["id"] == ziel), None)
    if not eintrag:
        return None
    return {
        "aktuell": modell,
        "nachfolger": ziel,
        "name": eintrag["name"],
        "size_gb": eintrag["size_gb"],
        "hinweis": (f"{modell} hat einen Nachfolger: {ziel} "
                    f"({eintrag['size_gb']:g} GB). Nichts wird automatisch "
                    "geladen oder umgestellt."),
    }


def stand_text() -> str:
    jahr, monat = STAND.split("-")
    return f"Stand {monat}/{jahr}"


def alter_monate(heute: date | None = None) -> int:
    heute = heute or date.today()
    jahr, monat = (int(t) for t in STAND.split("-"))
    return (heute.year - jahr) * 12 + (heute.month - monat)


def veraltet(heute: date | None = None) -> bool:
    return alter_monate(heute) > HOECHSTALTER_MONATE


def ohne_denkblock(text: str) -> str:
    """Entfernt einen `<think>…</think>`-Block vor der eigentlichen Antwort.

    Nur am Anfang — ein "<think>" mitten in einer Antwort ist Inhalt.
    Ein nie geschlossener Block laesst den Text unveraendert: lieber eine
    Antwort, die der Parser verwirft, als eine abgeschnittene.
    """
    if not text:
        return text or ""
    rest = text.lstrip()
    if not rest.lower().startswith("<think>"):
        return text
    ende = rest.lower().find("</think>")
    if ende < 0:
        return text
    return rest[ende + len("</think>"):].lstrip()
