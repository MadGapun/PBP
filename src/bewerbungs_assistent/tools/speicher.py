"""MCP-Werkzeuge zu „Speicher & Downloads“ (#1131, I19).

Das Dashboard hat die Übersicht und das Bereinigen in den Einstellungen; diese Werkzeuge sind dieselbe Funktion für den
Chat (PBP soll auch ohne Claude nutzbar sein, und mit Claude nicht schlechter). Beide lesen und schreiben über
`services/speicher.py`: es gibt keine zweite Fassung der Regeln.
"""
from __future__ import annotations

import logging


def register(mcp, db, logger: logging.Logger):
    """Registriert die Speicher-Tools."""

    @mcp.tool()
    def speicher_anzeigen() -> dict:
        """Zeigt, wohin PBP schreibt und lädt, wie viel dort liegt und was sich bereinigen lässt (#1131).

        Je Ort: Name, Pfad, was dort liegt, Größe und wer es angelegt hat (PBP, ein Zusatzprogramm, du oder ein anderes
        Programm). Dazu die Bereinigungs-Aktionen mit Erklärung. Orte, die anderen Programmen gehören (Playwright-Browser,
        Ollama-Modelle), werden gezeigt und erklärt, aber nie gelöscht. Liest nur, verändert nichts.

        Nächster Schritt: möchte der Mensch Platz schaffen, zuerst `speicher_bereinigen(aktion)` ohne Bestätigung
        aufrufen, die Zahlen nennen und fragen.
        """
        from ..services import speicher
        erg = speicher.uebersicht(db)
        erg["zusammenfassung"] = [
            f"{o['name']} ({o['urheber_text']}): " + ("nichts vorhanden" if o["nichts_vorhanden"] else speicher._mb(o["bytes"]))
            + (" oder mehr" if not o["vollstaendig"] else "") for o in erg["orte"]]
        return erg

    @mcp.tool()
    def speicher_bereinigen(aktion: str, auswahl: list = None, bestaetigung: bool = False) -> dict:
        """Bereinigt einen Ort aus `speicher_anzeigen` in zwei Schritten: erst Vorschau, dann Bestätigung (#1131).

        Ohne `bestaetigung=True` wird NICHTS gelöscht: es kommt die Vorschau mit Zahlen und Dateiliste (bei Aktionen mit
        Auswahl zuerst die Liste zum Auswählen). Erst setzen, NACHDEM der Mensch die Zahlen gesehen und ja gesagt hat. Läuft
        Hintergrundarbeit, wird abgelehnt und genannt, was läuft.

        Args:
            aktion: Eine aus `speicher_anzeigen` → `aktionen`: sicherungen, protokolle, export, alte_fassungen,
                update_arbeitsordner, komponenten_reste, downloads_zip.
            auswahl: Nur für `sicherungen` und `downloads_zip`: die Kennungen der Einträge, die weg sollen.
            bestaetigung: True führt aus. Alles andere zeigt nur.
        """
        from ..services import speicher
        erg = speicher.bereinigen(db, aktion, auswahl, bestaetigt=bestaetigung is True, als_werkzeug=True)
        if erg.get("status") in ("auswahl", "vorschau"):
            erg["naechster_schritt"] = (
                "Zahlen nennen und den Menschen fragen. Mit Ja: speicher_bereinigen(aktion, "
                + ("auswahl=[...], " if erg.get("braucht_auswahl") else "") + "bestaetigung=True)")
        if erg.get("status") in ("bereinigt", "teilweise"):
            logger.info("Speicher bereinigt: %s, %s Einträge, %s Byte", aktion, erg.get("entfernt"), erg.get("bytes_frei"))
        return erg
