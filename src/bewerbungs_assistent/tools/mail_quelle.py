"""MCP-Werkzeuge zur Mail-Zugangsschicht — Mail-Ordner als Quelle (#947).

Das Dashboard hat alles unter Einstellungen › Quellen im Detail › Mail-Ordner; diese Werkzeuge sind dieselbe Funktion für
den Chat. Grundregel: **nie ohne ausdrückliche Zustimmung.** Das Einschalten des Ordner-Scans und die Freigabe des
Posteingangs verlangen `bestaetigt=True`, und das darf Claude erst setzen, NACHDEM der Mensch es gesagt hat.
"""
from __future__ import annotations

import logging


def register(mcp, db, logger: logging.Logger):
    """Registriert die Mail-Quellen-Tools."""

    @mcp.tool()
    def mail_quelle_anzeigen() -> dict:
        """Zeigt, ob PBP Mail-Ordner lesen darf, und welche Ordner freigegeben sind (#947).

        Der Ordner-Scan ist standardmäßig AUS: ein gekoppeltes Mail-Add-on liest dann keinen Ordner von sich aus. Die Antwort
        nennt den Schalter, die freigegebenen Ordner mit letztem Lauf, verarbeiteten Mails und daraus entstandenen Stellen
        sowie Hinweise (z. B. eine Beta-Einstellung, die erneut bestätigt werden muss). Mails, die der Mensch selbst mit
        „An PBP senden“ schickt, brauchen den Schalter nicht. Liest nur, verändert nichts.

        Nächste Schritte: soll PBP Jobmails aus einem Ordner holen, den Menschen fragen und dann
        `mail_quelle_einstellen` benutzen. Anleitung für den Filter im Mail-Programm: Wiki, Seite „Mail-Ordner“.
        """
        from ..services import mail_quelle
        return mail_quelle.uebersicht(db)

    @mcp.tool()
    def mail_quelle_einstellen(aktion: str, anbieter: str = "", ordner: str = "", konto: str = "",
                               freigabe_id: str = "", bestaetigt: bool = False) -> dict:
        """Schaltet den Ordner-Scan ein oder aus und verwaltet die Liste der freigegebenen Mail-Ordner (#947).

        Gelesen wird nur, was genau in der Liste steht: kein Platzhalter, keine Unterordner. Eine leere Liste heißt: nichts.
        Einschalten und die Freigabe des Posteingangs sind Datenschutz-Entscheidungen des Menschen: erst fragen, dann
        `bestaetigt=True`.

        Args:
            aktion: scan_einschalten | scan_ausschalten | freigabe_hinzufuegen | freigabe_entfernen | zuruecksetzen.
            anbieter: Für freigabe_hinzufuegen: thunderbird | outlook | sonstige.
            ordner: Für freigabe_hinzufuegen: der Ordner, genau so wie das Mail-Programm ihn nennt (z. B. „Jobs/Portale“).
            konto: Für freigabe_hinzufuegen: das Konto, wenn das Add-on eines mitsendet; sonst leer.
            freigabe_id: Für freigabe_entfernen: die Kennung aus mail_quelle_anzeigen.
            bestaetigt: True, NACHDEM der Mensch ja gesagt hat (Einschalten, Posteingang).
        """
        from ..services import mail_quelle
        aktion = (aktion or "").strip().lower()
        if aktion == "scan_einschalten":
            erg = mail_quelle.scan_einschalten(db, bestaetigt=bestaetigt is True)
        elif aktion == "scan_ausschalten":
            erg = mail_quelle.scan_ausschalten(db)
        elif aktion == "freigabe_hinzufuegen":
            erg = mail_quelle.freigabe_hinzufuegen(db, anbieter, ordner, konto, posteingang_bestaetigt=bestaetigt is True)
        elif aktion == "freigabe_entfernen":
            erg = mail_quelle.freigabe_entfernen(db, freigabe_id)
        elif aktion == "zuruecksetzen":
            erg = mail_quelle.zuruecksetzen(db)
        else:
            return {"status": "fehler", "text": f"Unbekannte Aktion „{aktion}“.",
                    "erlaubt": ["scan_einschalten", "scan_ausschalten", "freigabe_hinzufuegen", "freigabe_entfernen", "zuruecksetzen"]}
        if erg.get("status") in ("bestaetigung_noetig", "posteingang_warnung"):
            erg["naechster_schritt"] = ("Den Menschen fragen. Nur wenn er ausdrücklich ja sagt: dasselbe noch einmal mit bestaetigt=True.")
        else:
            erg["stand"] = mail_quelle.uebersicht(db)
        return erg
