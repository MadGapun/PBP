"""MCP-Werkzeuge des optionalen API-Wegs der KI (#1236, F52).

Nur registriert, wenn beim Start des Servers ein Schlüssel in der Umgebung steht (`PBP_ANTHROPIC_API_KEY`):
ohne Schlüssel gibt es diese Werkzeuge nicht, und nichts sieht anders aus als vorher.

Das Dashboard hat die Karte unter Einstellungen › Lokale KI; diese Werkzeuge sind dieselbe Funktion für den Chat.
Grundregel: **nie ohne ausdrückliche Zustimmung.** Eine Aufgabe für die API freizugeben und die Probe zu senden
verlangen `bestaetigt=True`, und das darf Claude erst setzen, NACHDEM der Mensch es gesagt hat.
"""
from __future__ import annotations

import logging


def register(mcp, db, logger: logging.Logger):
    """Registriert die Werkzeuge des API-Wegs."""

    @mcp.tool()
    def api_weg_anzeigen() -> dict:
        """Zeigt den Stand des optionalen API-Wegs der KI (#1236): welche Aufgaben freigegeben sind, was die API dabei sieht, Modell, Budget, Verbrauch.

        Mit eigenem Anthropic-Schlüssel kann PBP gleichartige Massenaufgaben (Stellen mit dem Profil abgleichen, Anzeigentexte
        prüfen) über die API erledigen statt über die lokale KI. Vorgabe ist AUS, jede Aufgabe wird einzeln freigegeben. Die
        Antwort nennt je Aufgabe die Feldliste (was verlässt den Rechner, was nicht), das Budget in US-Dollar, den Verbrauch aus
        den Angaben der API, den letzten Fehler mit Grund und ob der Schlüssel geprüft ist. Der Schlüssel selbst steht nie darin.
        Liest nur, verändert nichts.

        Nächste Schritte: freigeben oder Budget setzen mit `api_weg_einstellen`, den Schlüssel prüfen mit `api_weg_pruefen`.
        """
        from ..services import api_backend
        erg = api_backend.uebersicht(db)
        erg["naechster_schritt"] = (
            "Freigeben, Modell und Budget: api_weg_einstellen. Schlüssel prüfen: api_weg_pruefen. Die Zahlen sind PBPs "
            "Zähler; das tatsächliche Guthaben steht in der Anthropic Console.")
        return erg

    @mcp.tool()
    def api_weg_einstellen(aufgaben: list[str] | None = None, modelle: dict[str, str | None] | None = None,
                           budget_usd: float | str | None = None, bestaetigt: bool = False) -> dict:
        """Gibt Aufgaben für die Anthropic-API frei oder sperrt sie, wählt das Modell und setzt das Budget (#1236).

        Eine Freigabe ist eine Datenschutz-Entscheidung des Menschen: die genannten Angaben verlassen den Rechner und gehen an
        Anthropic. Erst fragen, dann `bestaetigt=True`; ohne Bestätigung kommt nur die Feldliste. Ohne Budget ruft PBP die API nicht
        auf. Sperren, Modell und Budget wirken sofort. Ohne Schlüssel in der Umgebung lässt sich nichts freigeben.

        Args:
            aufgaben: Die vollständige Liste der freigegebenen Aufgaben (match_job_to_skills, validate_job_quality); nicht genannte werden gesperrt. Leer = alle gesperrt.
            modelle: Zuordnung Aufgabe → Modell aus der Liste von api_weg_anzeigen; null = das günstigste. Nur für freigegebene Aufgaben.
            budget_usd: Die Obergrenze in US-Dollar (etwa 5 oder „5,50“); 0 heißt: nichts darf ausgegeben werden. PBP stoppt vor dem Überschreiten.
            bestaetigt: True, NACHDEM der Mensch die Feldliste gesehen und ja gesagt hat (nur beim Freigeben nötig).
        """
        from ..services import api_backend
        erg = api_backend.einstellungen_setzen(db, aufgaben=aufgaben, modelle=modelle, budget_usd=budget_usd,
                                               bestaetigt=bestaetigt is True)
        if erg.get("status") == "bestaetigung_noetig":
            erg["naechster_schritt"] = ("Den Menschen fragen und die Feldliste nennen. Nur wenn er ausdrücklich ja sagt: "
                                        "dasselbe noch einmal mit bestaetigt=True.")
        else:
            erg["stand"] = api_backend.uebersicht(db)
        return erg

    @mcp.tool()
    def api_weg_pruefen(bestaetigt: bool = False) -> dict:
        """Prüft den API-Schlüssel mit einer einzigen kleinen Anfrage an Anthropic (#1236).

        „Gültig“ steht erst, wenn die API die Anfrage angenommen und beantwortet hat; das bloße Vorhandensein des Schlüssels
        zählt nicht. Die Anfrage enthält nur das Wort „ok“, nichts aus dem Profil, und kostet einen Bruchteil eines Cents. Das
        Ergebnis gilt nur für den geprüften Schlüssel. Bei einem Fehler steht der Grund dabei (ungültig, Guthaben, Limit, kein Netz).

        Args:
            bestaetigt: True, NACHDEM der Mensch ja gesagt hat; ohne Bestätigung kommt nur die Beschreibung der Probe.
        """
        from ..services import api_backend
        if bestaetigt is not True:
            return {"status": "bestaetigung_noetig", "text": (
                "Die Probe schickt eine einzige kleine Anfrage (das Wort „ok“) an Anthropic. Sie enthält nichts aus deinem "
                "Profil und kostet einen Bruchteil eines Cents. Soll PBP sie jetzt senden?"),
                "naechster_schritt": "Den Menschen fragen. Nur wenn er ausdrücklich ja sagt: dasselbe noch einmal mit bestaetigt=True."}
        erg = api_backend.schluessel_pruefen(db)
        erg["stand"] = api_backend.uebersicht(db)
        return erg
