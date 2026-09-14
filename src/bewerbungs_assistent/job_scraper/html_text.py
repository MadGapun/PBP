"""Anzeigentext aus HTML — mit Absaetzen, Listen und Ueberschriften (#1047).

Bis v1.7.109 wandelten dreizehn Adapter das Beschreibungs-HTML mit

    re.sub(r"<[^>]+>", " ", html)
    re.sub(r"\\s+", " ", text)

in Text um: jedes Tag wurde ein Leerzeichen, danach jeder Leerraum
einschliesslich der Zeilenumbrueche. Aus einer gegliederten Anzeige wurde
ein einziger Absatz. Nachgemessen am 14.09.2026: acht Arbeitnow-Anzeigen
tragen 4 bis 35 Absaetze, bis zu 34 Listenpunkte und 3 bis 5
Ueberschriften — der Leser liess davon 0 Zeilenumbrueche uebrig. Auf einer
Bestandskopie hatte bei Arbeitnow, RemoteOK, Remotive und ferchau KEIN Text
ab 500 Zeichen einen Zeilenumbruch, bei der Bundesagentur 492 von 508.

Und `text_aus_html` las mit `get_text(separator=" ")`, also brachte auch
das Nachladen nichts zurueck.

Ein Leser fuer alle, statt dreizehn Kopien einer Zeile: sonst geht die
Gliederung beim naechsten Adapter wieder verloren (#963).

Die Regeln:

* Absaetze, Ueberschriften und andere Bloecke werden durch eine Leerzeile
  getrennt.
* Listenpunkte stehen je auf einer Zeile und beginnen mit `- `.
* `<br>` ist ein Zeilenumbruch.
* Skripte, Styles und HTML-Kommentare gehoeren nicht zum Text (v1.7.108).
* Text ohne Markup behaelt seine Zeilenumbrueche; nur der Leerraum
  innerhalb einer Zeile wird zusammengefasst.
"""
from __future__ import annotations

import re

# Elemente, die einen eigenen Block bilden. Inline-Elemente (strong, a,
# span, em) stehen bewusst nicht hier: ein Wort in Fettschrift ist kein
# neuer Absatz.
_BLOECKE = (
    "address", "article", "aside", "blockquote", "dd", "div", "dl", "dt",
    "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3",
    "h4", "h5", "h6", "header", "hr", "main", "nav", "ol", "p", "pre",
    "section", "table", "tr", "ul",
)
# `get_text()` laesst Skripte, Styles und Vorlagen selbst aus — Seitentitel
# und `<noscript>` aber nicht.
_OHNE_TEXT = ("script", "style", "noscript", "template", "head")
_LEERRAUM_IN_ZEILE = re.compile(r"[ \t\f\v\u00a0\u2007\u202f]+")
_SCHMUCKLINIE = re.compile(r"[-_=*~\u2013\u2014]{3,}")
_PUNKT = "- "

# Quellen, deren Anzeigentext schon an der Quelle keine Gliederung traegt.
# Gemessen am 14.09.2026: die JSON-LD-Beschreibung von hays ist in 8 von 8
# Anzeigen reiner Text ohne ein einziges Tag oder einen Zeilenumbruch.
# Solche Texte erneut zu holen brachte nichts ausser Anfragen.
QUELLEN_OHNE_GLIEDERUNG = frozenset({"hays"})


def gegliederter_text(roh) -> str:
    """Den Text einer Anzeige lesbar gegliedert zurueckgeben."""
    if not roh:
        return ""
    roh = str(roh)
    # Kein Sonderweg fuer Text ohne Markup: die Gegenprobe zeigte ihn als
    # wirkungslos — der Parser behaelt Umbrueche und loest Entitaeten
    # genauso auf.
    from bs4 import BeautifulSoup

    suppe = BeautifulSoup(roh, "html.parser")
    for knoten in suppe.find_all(_OHNE_TEXT):
        knoten.decompose()
    for umbruch in suppe.find_all("br"):
        umbruch.replace_with("\n")
    for punkt in suppe.find_all("li"):
        punkt.insert_before("\n" + _PUNKT)
        punkt.insert_after("\n")
    for block in suppe.find_all(_BLOECKE):
        block.insert_before("\n\n")
        block.insert_after("\n\n")
    for zelle in suppe.find_all(("td", "th")):
        zelle.insert_after(" ")
    # `get_text()` laesst Kommentare aus — anders als ein Durchlauf ueber
    # alle `str`-Knoten, der in v1.7.104 genau daran scheiterte.
    return _aufraeumen(suppe.get_text())


def _aufraeumen(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    zeilen = [_LEERRAUM_IN_ZEILE.sub(" ", z).strip() for z in text.split("\n")]
    # Eine Zeile nur aus Strichen ist Schmuck, kein Inhalt — und `---` auf
    # einer eigenen Zeile ist der Trenner, hinter dem PBP Notizen ablegt.
    # `_strip_pbp_notes` und `stellen_skills.anzeigenteil` schneiden dort
    # ab; bliebe die Zeile stehen, fiele der Rest der Anzeige aus Score
    # und Kompetenzen (Befund der Pruefung vor #1047).
    zeilen = ["" if _SCHMUCKLINIE.fullmatch(z) else z for z in zeilen]

    # Ein Listenpunkt, dessen Inhalt in einem eigenen Absatz steht
    # (`<li><p>...</p></li>`), hinterlaesst ein einzelnes "-" — mit der
    # naechsten Zeile verbinden.
    verbunden: list[str] = []
    offen = False
    for zeile in zeilen:
        if zeile == _PUNKT.strip():
            offen = True
            continue
        if offen:
            if not zeile:
                continue
            verbunden.append(_PUNKT + zeile)
            offen = False
            continue
        verbunden.append(zeile)

    # Leerzeilen zwischen zwei Listenpunkten entfernen, und nie mehr als
    # eine Leerzeile hintereinander.
    ergebnis: list[str] = []
    for i, zeile in enumerate(verbunden):
        if not zeile:
            if not ergebnis or not ergebnis[-1]:
                continue
            naechste = next((z for z in verbunden[i + 1:] if z), "")
            if ergebnis[-1].startswith(_PUNKT) and naechste.startswith(_PUNKT):
                continue
        ergebnis.append(zeile)
    return "\n".join(ergebnis).strip()


def ist_flach(text, mindestlaenge: int = 500) -> bool:
    """Ein langer Text ganz ohne Zeilenumbruch — die Spur des alten Lesers.

    Eine gegliederte Anzeige dieser Laenge hat praktisch immer mindestens
    einen Umbruch; gemessen trugen ihn bei der Bundesagentur 492 von 508.
    """
    if not text:
        return False
    text = str(text)
    return len(text) >= mindestlaenge and "\n" not in text
