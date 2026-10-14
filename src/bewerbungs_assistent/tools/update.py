"""MCP-Werkzeuge zum Auto-Update — Auto-Update (#1093, v1.8).

Das Dashboard hat alles in den Einstellungen; diese Werkzeuge sind dieselbe Funktion fuer den Chat
(PBP soll auch ohne Claude nutzbar sein, und mit Claude nicht schlechter). Grundregel wie bei den Komponenten
(#751): **nie ohne ausdrueckliche Zustimmung.** Eine Stufe, bei der PBP von selbst installiert, und jede
Installation verlangen `bestaetigt=True`, und das darf Claude erst setzen, NACHDEM der Mensch es gesagt hat.
"""
from __future__ import annotations

import logging


def register(mcp, db, logger: logging.Logger):
    """Registriert die Update-Tools."""

    @mcp.tool()
    def update_status() -> dict:
        """Zeigt den Stand der Updates von PBP (Auto-Update, #1093).

        Liefert: welche Version läuft, ob eine neuere bereitliegt, welche Stufe eingestellt ist (aus,
        hinweis, auto_meldung, auto_still), ob ein Neustart nötig ist (installiert, gilt aber erst nach
        dem Neustart von PBP UND Claude Desktop), die letzten Installationen und eine mögliche
        Zurücknahme. Liest nur, verändert nichts.

        Nächste Schritte:
        - neue Version da → den Menschen fragen, ob installiert werden soll
          (`update_jetzt_installieren`)
        - Neustart nötig → dem Menschen sagen: PBP und Claude Desktop neu starten
        - Automatik gewünscht → `update_einstellungen_setzen`
        """
        from ..services.auto_update import lauf
        return lauf.uebersicht(db)

    @mcp.tool()
    def update_einstellungen_setzen(stufe: str = "", vorgaenger_behalten: int = 0,
                                    installer_aufraeumen: str = "", bestaetigt: bool = False) -> dict:
        """Stellt das Auto-Update ein (Auto-Update, #1093). Ohne Angabe passiert nichts.

        Args:
            stufe: aus = nur der Hinweis (Vorgabe) · hinweis = der Hinweis installiert mit einem Klick ·
                auto_meldung = PBP installiert selbst und meldet es · auto_still = wie zuvor, ohne Meldung.
            vorgaenger_behalten: wie viele frühere Versionen zum Zurückschalten liegen bleiben (1 bis 10, Vorgabe 3).
            installer_aufraeumen: fragen, immer oder nie — ob der Installer seinen entpackten Ordner und das ZIP löscht.
            bestaetigt: Pflicht für auto_meldung und auto_still. Erst setzen, NACHDEM der Mensch ausdrücklich
                gesagt hat, dass PBP Updates ohne Rückfrage installieren soll.
        """
        from ..services.auto_update import lauf, zustand
        geaendert = []
        try:
            if stufe:
                if stufe in zustand.AUTOMATISCHE_STUFEN and not bestaetigt:
                    return {"status": "bestaetigung_noetig",
                            "text": ("Bei dieser Stufe installiert PBP Updates von selbst, ohne zu fragen. Frage den Menschen, "
                                     "ob er das will, und rufe das Werkzeug dann mit bestaetigt=True auf."),
                            "stufe": zustand.stufe(db)}
                zustand.stufe_setzen(db, stufe)
                zustand.antwort_merken(db, "nein" if stufe == "aus" else "ja")
                geaendert.append("stufe")
            if vorgaenger_behalten:
                zustand.vorgaenger_setzen(db, vorgaenger_behalten)
                geaendert.append("vorgaenger_behalten")
            if installer_aufraeumen:
                zustand.installer_aufraeumen_setzen(db, installer_aufraeumen)
                geaendert.append("installer_aufraeumen")
        except ValueError as exc:
            return {"fehler": str(exc)}
        if not geaendert:
            return {"status": "nichts_geaendert", "text": "Keine Angabe gemacht.", **lauf.uebersicht(db)}
        return {"status": "gesetzt", "geaendert": geaendert, **lauf.uebersicht(db)}

    @mcp.tool()
    def update_jetzt_installieren(version: str = "", bestaetigt: bool = False) -> dict:
        """Installiert die neue Version von PBP jetzt (Auto-Update, #1093).

        Lädt im Hintergrund von den festen GitHub-Releases, prüft Prüfsumme und Signatur und legt die Version
        neben die bisherige. Nichts wird beendet; sie gilt nach dem nächsten Neustart von PBP UND Claude
        Desktop. Den Stand zeigt `update_status`.

        Args:
            version: leer = die gefundene neue Version.
            bestaetigt: Pflicht. Erst setzen, NACHDEM der Mensch gesagt hat, dass jetzt installiert werden soll.
        """
        from ..services.auto_update import lauf
        if not bestaetigt:
            return {"status": "bestaetigung_noetig",
                    "text": "Frage den Menschen, ob die neue Version jetzt installiert werden soll, und rufe das Werkzeug "
                            "dann mit bestaetigt=True auf.", **lauf.uebersicht(db)}
        if not version:
            letzte = lauf.pruefen(db, frisch=True)
            version = letzte.get("version") if letzte.get("status") == "neu" else ""
        if not version:
            return {"status": "keine_neue_version", "text": "Es gibt keine neue Version, die installiert werden könnte.",
                    **lauf.uebersicht(db)}
        return {**lauf.starte_installation(db, version, ausloeser="mcp"), "version": version}

    @mcp.tool()
    def update_zurueckschalten(version: str) -> dict:
        """Lässt PBP beim nächsten Start auf eine ältere, noch installierte Version zurückgehen (Auto-Update, #1093).

        Nichts wird beendet oder gelöscht. Die neueren Versionen schaltet PBP nicht von selbst wieder ein.
        Welche Versionen da sind, zeigt `update_status` unter `installiert`.

        Args:
            version: die ältere Version, z. B. 1.8.0.
        """
        from ..services.auto_update import lauf
        return lauf.zurueckschalten(db, version)
