"""Fehler des Auto-Updates: ein Code fuer Programme, ein Satz fuer Menschen (#1093).

Jeder Abbruch eines Update-Laufs ist ein `UpdateFehler`. Der Code ist stabil (Tests,
Verlauf, Oberflaeche verzweigen darauf), der Text steht so, dass ihn jemand ohne
Technikwissen versteht und weiss, was jetzt gilt: bei jedem Fehler ist NICHTS
installiert worden und die bisherige Fassung laeuft weiter (Akzeptanzkriterium 5).
"""
from __future__ import annotations

#: Code -> Standardtext. Wer einen genaueren Satz hat, gibt ihn beim Werfen mit.
TEXTE = {
    "nicht_verfuegbar": "Das automatische Aktualisieren steht in dieser Installation nicht zur Verfügung.",
    "gesperrt": "Ein anderes Update läuft gerade. Es wurde nichts verändert.",
    "schon_aktuell": "Du hast bereits die neueste Version.",
    "gescheitert": ("Diese Version ließ sich bei dir schon einmal nicht starten und wird nicht noch einmal "
                    "automatisch installiert. Eine neuere Version wird wieder angeboten."),
    "quelle_nicht_erlaubt": "Die Adresse gehört nicht zu den festen Quellen von PBP. Es wurde nichts geladen.",
    "netz": "Die Verbindung zu GitHub hat nicht geklappt. PBP versucht es später noch einmal.",
    "zu_gross": "Die Datei ist größer als erlaubt. Es wurde nichts installiert.",
    "abgebrochen": "Das Update wurde abgebrochen. Es wurde nichts verändert.",
    "platz": "Auf dem Laufwerk ist nicht genug Platz für das Update. Es wurde nichts verändert.",
    "pruefsumme": ("Die geladene Datei ist nicht die veröffentlichte (die Prüfsumme stimmt nicht). "
                   "Es wurde nichts installiert."),
    "signatur": "Die Signatur des Updates fehlt oder ist ungültig. Es wurde nichts installiert.",
    "archiv_unsicher": "Das Update-Archiv enthält Unerlaubtes. Es wurde nichts installiert.",
    "manifest": "Die Beschreibung im Update ist unvollständig oder passt nicht. Es wurde nichts installiert.",
    "braucht_installer": ("Dieses Update braucht den Installer. Lade das ZIP der neuen Version von der "
                          "Release-Seite und starte INSTALLIEREN.bat."),
    "abhaengigkeiten": "Zusätzliche Pakete konnten nicht bereitgestellt werden. Es wurde nichts installiert.",
    "selbsttest": "Die neue Version hat ihren Funktionstest nicht bestanden. Es wurde nichts installiert.",
    "unerwartet": "Beim Update ist etwas Unerwartetes passiert. Es wurde nichts installiert.",
}


class UpdateFehler(Exception):
    """Ein Update-Lauf ist gescheitert. `code` fuer Programme, `text` fuer Menschen, `detail` fuers Protokoll."""

    def __init__(self, code: str, text: str = "", *, detail: str = ""):
        self.code = code
        self.text = text or TEXTE.get(code, TEXTE["unerwartet"])
        self.detail = detail
        super().__init__(f"{code}: {self.text}" + (f" ({detail})" if detail else ""))
