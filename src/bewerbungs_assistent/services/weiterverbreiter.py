"""Weiterverbreiter: Seiten, die Stellenanzeigen anderer nur kopieren (#1120).

Google Jobs nennt zu jedem Treffer, "ueber" welche Seite er laeuft. Meist
ist das der Arbeitgeber selbst, eine Jobboerse oder ein Vermittler. Manche
Seiten spiegeln aber nur fremde Anzeigen, ohne Auftrag des Arbeitgebers
und ohne eigene Inhalte. Fuer sie gilt dreierlei:

* Das Datum der Karte ist das KOPIERdatum, nicht die Veroeffentlichung.
  Es wird deshalb nicht als `veroeffentlicht_am` gespeichert — unbekannt
  ist ein eigener Zustand (#949), ein falsches Datum saehe frisch aus.
* Titel und Ort koennen vom Original abweichen. Praxis-Fall 29.09.2026:
  die Kopie nannte die Nachbarstadt statt des Arbeitsorts, formulierte den
  Titel um und haengte `. Job in <Ort> <Portal>` an; das Original lief auf
  der Karriereseite des Arbeitgebers seit Juni.
* Der naechste Schritt ist das Original beim Arbeitgeber, nicht die Kopie.

Abgrenzung: Vermittler und Personaldienstleister schreiben eigene
Anzeigen (siehe `firma_kontext`, Rolle Vermittler); Jobboersen werden vom
Arbeitgeber selbst beschickt; Sammelquellen wie Kimeta oder Adzuna sind
eigene PBP-Quellen mit Verweis aufs Original. Keines davon gehoert hierher.

Pflege: ein Eintrag je Seite, kleingeschrieben und so, wie der Name hinter
"ueber" steht, mit Beleg (Datum und was gemessen wurde). Kandidaten ohne
Messung gehoeren NICHT in die Liste — ein falscher Eintrag nimmt einer
echten Anzeige ihr Datum.
"""
from __future__ import annotations

import re

#: Name (kleingeschrieben) -> Beleg.
WEITERVERBREITER: dict[str, str] = {
    "move collective jobs": (
        "29.09.2026 (#1120): britische Seite, die Anzeigen aus Grossbritannien, "
        "den USA und Deutschland spiegelt, ohne eigene Inhalte; Anzeigen von "
        "2024 noch online, kein einziger PLM/PDM-Treffer."
    ),
}


def _normalisiert(portal: str) -> str:
    name = re.sub(r"\s+", " ", (portal or "")).strip().lower()
    return re.sub(r"^(?:über|ueber)\s+", "", name)


def ist_weiterverbreiter(portal: str) -> bool:
    """Steht die Seite hinter "ueber" auf der Liste?"""
    return _normalisiert(portal) in WEITERVERBREITER


def vermerk(portal: str, firma: str) -> str:
    """Der Satz, der an der Stelle steht."""
    wer = f" ({firma})" if (firma or "").strip() else ""
    return (f"Weiterverbreiter: {portal.strip()} kopiert Anzeigen anderer "
            f"Seiten. Original beim Arbeitgeber suchen{wer}.")
