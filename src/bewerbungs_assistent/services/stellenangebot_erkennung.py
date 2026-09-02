"""Stellenangebote am INHALT erkennen (#961, v1.7.24).

Die bisherige Typ-Erkennung arbeitet fast ausschliesslich am
DATEINAMEN. Der Text wird zwar geladen, aber nur gegen feste
Formulierungen geprueft ("wir suchen einen", "hat Ihnen eine Nachricht
gesendet"). Eine Recruiter-Mail, deren Betreff keines dieser Muster
trifft, faellt durch — auch wenn ihr Inhalt unmissverstaendlich eine
Stellenausschreibung ist.

Belegter Fall vom 28.08.2026: eine Mail mit Referenznummer, Titel,
Startdatum, Vertragsmodell, Verguetungsspanne, Arbeitsort, Aufgaben,
Anforderungen und Absenderkontakt wurde als `sonstiges` eingestuft.
Das Routing leitete daraus `noop_korrespondenz_abschliessen` ab, mit
dem Hinweis "Manuell sichten".

Warum das teuer ist: `dokumente_korrespondenz_abschliessen` setzt genau
diese Dokumente sammelweise auf `angewendet`. Eine fehlklassifizierte
Stellenanfrage wird damit stillschweigend abgeschlossen, ohne dass je
eine Stelle im System entsteht. Der Vorgang ist danach aus dem
Analyse-Plan verschwunden und gilt als erledigt, obwohl die eigentliche
Aktion nie stattgefunden hat — derselbe Ausfallmodus wie in #833: kein
Fehler, der auffaellt, sondern einer, der wie Erfolg aussieht.

Erkannt wird deshalb an der STRUKTUR statt an Formulierungen: eine
Stellenausschreibung nennt eine Rolle und dazu mehrere der Angaben, die
nur in einer Ausschreibung zusammen vorkommen. Formulierungen aendern
sich je Absender, die Struktur nicht.
"""
from __future__ import annotations

import re

# Rollenbezeichnungen. Bewusst als Wortstamm, damit
# "Entwicklerin"/"Entwickler" und "Projektleitung"/"Projektleiter"
# gleichermassen treffen.
_ROLLE = re.compile(
    r"\b(?:manager|managerin|consultant|engineer|entwickl\w*|architekt\w*|"
    r"berater\w*|leiter\w*|leitung|spezialist\w*|referent\w*|"
    r"administrator\w*|analyst\w*|designer\w*|techniker\w*|"
    r"konstrukteur\w*|projektleit\w*|teamlead|lead|developer|"
    r"specialist|director|koordinator\w*|sachbearbeiter\w*)\b",
    re.IGNORECASE,
)

# Ausdrueckliche Titel-Kennzeichnung — staerker als ein Rollenwort im
# Fliesstext.
_TITEL_FELD = re.compile(
    r"\b(?:position|stelle|stellenbezeichnung|vakanz|jobtitel|"
    r"job\s*title|rolle|projekttitel)\s*[:\-]",
    re.IGNORECASE,
)

MERKMALE = {
    "referenznummer": re.compile(
        r"\b(?:referenz(?:nummer)?|ref\.?\s*-?\s*nr\.?|kennziffer|"
        r"stellen-?(?:id|nummer)|req(?:uisition)?\.?\s*id|projekt-?nr\.?|"
        r"ausschreibungsnummer)\b\s*[:\-]?\s*\w", re.IGNORECASE),
    "verguetung": re.compile(
        r"(?:\b(?:geh(?:a|ae|ä)lt\w*|verg(?:u|ue|ü)tung\w*|tagessatz|"
        r"stundensatz|jahresgehalt|salary|compensation)\b"
        r"|\d[\d.,]{2,}\s*(?:€|eur\b)"
        r"|\b(?:€|eur)\s*\d[\d.,]{2,})", re.IGNORECASE),
    "arbeitsort": re.compile(
        r"\b(?:einsatzort|arbeitsort|dienstsitz|standort|location|"
        r"einsatzgebiet|arbeitsplatz)\b\s*[:\-]?", re.IGNORECASE),
    "startdatum": re.compile(
        r"\b(?:startdatum|projektstart|eintrittstermin|starttermin|"
        r"beginn|verf(?:u|ue|ü)gbarkeit|ab\s+sofort|start\s*[:\-])\b",
        re.IGNORECASE),
    "aufgabenliste": re.compile(
        r"\b(?:ihre\s+aufgaben|deine\s+aufgaben|aufgabenbereich|"
        r"t(?:a|ae|ä)tigkeiten|responsibilities|your\s+tasks|"
        r"ihr\s+profil|dein\s+profil|anforderungsprofil|"
        r"das\s+bringen\s+sie\s+mit)\b", re.IGNORECASE),
}

# Wie viele Merkmale muessen neben der Rolle zusammenkommen? Zwei, wie
# in den Akzeptanzkriterien von #961 festgelegt. Ein einzelnes Merkmal
# steht auch in einer Absage ("Standort: Hamburg") — zwei zusammen mit
# einer Rollenbezeichnung praktisch nur in einer Ausschreibung.
MINDEST_MERKMALE = 2


def gefundene_merkmale(text: str) -> list[str]:
    """Welche Ausschreibungs-Merkmale stehen im Text?"""
    if not text:
        return []
    ausschnitt = str(text)[:20000]
    return sorted(name for name, muster in MERKMALE.items()
                  if muster.search(ausschnitt))


def nennt_eine_rolle(text: str, dateiname: str = "") -> bool:
    """Steht im Text ueberhaupt eine Stellenbezeichnung?"""
    zusammen = f"{dateiname}\n{text or ''}"[:20000]
    return bool(_TITEL_FELD.search(zusammen) or _ROLLE.search(zusammen))


def ist_stellenangebot(text: str, dateiname: str = "") -> tuple[bool, dict]:
    """Traegt dieses Dokument eine Stellenausschreibung? (#961 AK 1)

    Gibt (ja_nein, begruendung) zurueck. Die Begruendung nennt die
    gefundenen Merkmale — damit eine Fehlklassifikation nachvollziehbar
    bleibt statt wieder still zu passieren.
    """
    merkmale = gefundene_merkmale(text)
    rolle = nennt_eine_rolle(text, dateiname)
    treffer = rolle and len(merkmale) >= MINDEST_MERKMALE
    return treffer, {
        "rolle_erkannt": rolle,
        "merkmale": merkmale,
        "mindestens": MINDEST_MERKMALE,
        "begruendung": (
            f"Rollenbezeichnung und {len(merkmale)} Ausschreibungs-Merkmale "
            f"({', '.join(merkmale)}) — das ist eine Stellenausschreibung, "
            "keine gewoehnliche Korrespondenz."
            if treffer else
            f"Rolle {'erkannt' if rolle else 'nicht erkannt'}, "
            f"{len(merkmale)} von mindestens {MINDEST_MERKMALE} Merkmalen."),
    }
