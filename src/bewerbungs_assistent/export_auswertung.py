"""PDF "Auswertung meiner Stellensuche" (#798, Stufe 3, Variante A: Zahlen zuerst).

Inhalte aus `services/auswertung_daten.py`; dieses Modul rechnet nichts.
Balken statt Kreise, direkt beschriftet, in Graustufen lesbar: die Helligkeit
traegt die Aussage. Fragen als Ueberschriften.
"""
from __future__ import annotations

from pathlib import Path

from fpdf.enums import XPos, YPos

from .export_nachweis import (_BALKEN, _DUNKEL, _FLAECHE, _LINIE, _MITTEL, _Nachweis,
                              _tabelle, _text, _ueberschrift)
from .export_report import _dejavu_pfade

TITEL = "Auswertung meiner Stellensuche"
_HELL = (185, 185, 185)
_MONATE = ("Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez")


def _klein(pdf, text: str, hoehe: float = 3.6):
    if not text:
        return
    pdf.set_font(pdf.schrift, "", 7.5)
    pdf.set_text_color(*_MITTEL)
    pdf.multi_cell(0, hoehe, _text(pdf, text), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)


def _kopf(pdf, name: str, d: dict):
    pdf.set_font(pdf.schrift, "B", 17)
    pdf.set_text_color(*_DUNKEL)
    pdf.cell(0, 9, _text(pdf, TITEL), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf.schrift, "B", 10.5)
    pdf.cell(0, 5.5, _text(pdf, name), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf.schrift, "", 8.5)
    pdf.set_text_color(*_MITTEL)
    pdf.cell(0, 4.5, _text(pdf, f"{d['zeitraum']['text']} · erstellt am {d['erstellt_text']}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2.5)


def _kacheln(pdf, kacheln: list):
    abstand = 2
    breite = (pdf.w - pdf.l_margin - pdf.r_margin - abstand * (len(kacheln) - 1)) / len(kacheln)
    y = pdf.get_y()
    for i, k in enumerate(kacheln):
        x = pdf.l_margin + i * (breite + abstand)
        pdf.set_draw_color(*_LINIE)
        pdf.rect(x, y, breite, 19)
        pdf.set_xy(x + 1.5, y + 1.3)
        pdf.set_font(pdf.schrift, "B", 12.5)
        pdf.cell(breite - 3, 6.5, _text(pdf, k["wert"]))
        pdf.set_xy(x + 1.5, y + 8.2)
        pdf.set_font(pdf.schrift, "B", 7.2)
        pdf.cell(breite - 3, 3.6, _text(pdf, k["name"]))
        pdf.set_xy(x + 1.5, y + 12)
        pdf.set_font(pdf.schrift, "", 6.2)
        pdf.set_text_color(*_MITTEL)
        pdf.multi_cell(breite - 3, 2.8, _text(pdf, k["hinweis"]), align="L")
        pdf.set_text_color(0, 0, 0)
    pdf.set_xy(pdf.l_margin, y + 22)


def _titel_spalte(pdf, x: float, y: float, breite: float, titel: str) -> float:
    pdf.set_xy(x, y)
    pdf.set_font(pdf.schrift, "B", 9.5)
    pdf.set_text_color(*_DUNKEL)
    pdf.multi_cell(breite, 4.6, _text(pdf, titel), align="L", new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    return pdf.get_y() + 1


def _balken(pdf, x: float, y: float, breite: float, zeilen: list, name_breite: float = 34) -> float:
    """`zeilen`: (Name, Hoehe des Balkens, Text, Anteil dunkel oder None)."""
    hoechste = max((z[1] for z in zeilen), default=0) or 1
    text_breite = 19
    spur = breite - name_breite - text_breite - 1
    for name, wert, text, dunkel in zeilen:
        pdf.set_xy(x, y)
        pdf.set_font(pdf.schrift, "", 7.6)
        umbruch = pdf.multi_cell(name_breite, 3.5, _text(pdf, name), align="L",
                                 dry_run=True, output="LINES")
        pdf.multi_cell(name_breite, 3.5, _text(pdf, name), align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
        hoehe = 3.5 * len(umbruch) + 1.2
        lang = spur * wert / hoechste
        pdf.set_fill_color(*(_HELL if dunkel is not None else _BALKEN))
        if lang > 0:
            pdf.rect(x + name_breite, y + .6, lang, 2.5, style="F")
        if dunkel:
            pdf.set_fill_color(*_BALKEN)
            pdf.rect(x + name_breite, y + .6, spur * dunkel / hoechste, 2.5, style="F")
        pdf.set_xy(x + name_breite + spur + 1, y)
        pdf.set_font(pdf.schrift, "B", 7.6)
        pdf.cell(text_breite, 3.6, _text(pdf, text), align="R")
        y += hoehe
    return y


def _kurz(schluessel: str) -> str:
    """Beschriftung einer Saeule: Mai, Q2/26 oder 2026."""
    if len(schluessel) == 4:
        return schluessel
    if "Q" in schluessel:
        return f"{schluessel[5:7]}/{schluessel[2:4]}"
    return _MONATE[int(schluessel[5:7]) - 1]


def _saeulen(pdf, x: float, y: float, breite: float, abschnitte: list) -> float:
    if not abschnitte:
        pdf.set_xy(x, y)
        pdf.set_font(pdf.schrift, "", 8)
        pdf.cell(breite, 4, "Noch keine Bewerbung erfasst.")
        return y + 6
    hoechste = max(a["bewerbungen"] for a in abschnitte) or 1
    hoehe = 21
    schritt = breite / len(abschnitte)
    saeule = min(schritt * .62, 9)
    boden = y + hoehe + 3.5
    pdf.set_draw_color(*_LINIE)
    pdf.line(x, boden, x + breite, boden)
    for i, a in enumerate(abschnitte):
        mitte = x + schritt * (i + .5)
        h = hoehe * a["bewerbungen"] / hoechste
        if h:
            pdf.set_fill_color(*_HELL)
            pdf.rect(mitte - saeule / 2, boden - h, saeule, h, style="F")
            g = hoehe * a["gespraeche"] / hoechste
            if g:
                pdf.set_fill_color(*_BALKEN)
                pdf.rect(mitte - saeule / 2, boden - g, saeule, g, style="F")
            pdf.set_font(pdf.schrift, "B", 6.8)
            pdf.set_xy(mitte - schritt / 2, boden - h - 3.2)
            pdf.cell(schritt, 3, str(a["bewerbungen"]), align="C")
        pdf.set_font(pdf.schrift, "", 5.8 if len(abschnitte) > 8 else 6.5)
        pdf.set_xy(mitte - schritt / 2, boden + .5)
        pdf.cell(schritt, 3, _text(pdf, _kurz(a["schluessel"])), align="C")
        pdf.set_text_color(*_MITTEL)
        pdf.set_xy(mitte - schritt / 2, boden + 3.3)
        pdf.cell(schritt, 3, str(a["gespraeche"]), align="C")
        pdf.set_text_color(0, 0, 0)
    pdf.set_xy(x, boden + 6.6)
    pdf.set_font(pdf.schrift, "", 6.6)
    pdf.set_text_color(*_MITTEL)
    pdf.cell(breite, 3, "Hell: Bewerbungen. Dunkel und untere Zahl: davon mit Gespräch.")
    pdf.set_text_color(0, 0, 0)
    return boden + 10


def _zwei_spalten(pdf, links, rechts):
    breite = (pdf.w - pdf.l_margin - pdf.r_margin - 7) / 2
    y = pdf.get_y()
    u1 = links(pdf.l_margin, y, breite)
    u2 = rechts(pdf.l_margin + breite + 7, y, breite)
    pdf.set_xy(pdf.l_margin, max(u1, u2) + 2.5)


def _seite_eins(pdf, name: str, d: dict):
    _kopf(pdf, name, d)
    _kacheln(pdf, d["kacheln"])
    basis = d["kennzahlen"]["bewerbungen"]["wert"]

    def trichter(x, y, b):
        y = _titel_spalte(pdf, x, y, b, f"Wie weit kamen die {basis} Bewerbungen?")
        zeilen = [(s["stufe"], s["wert"]["anzahl"], str(s["wert"]["anzahl"]), None)
                  for s in d["trichter"]["stufen"]]
        y = _balken(pdf, x, y, b, zeilen, 26)
        pdf.set_xy(x, y)
        pdf.set_font(pdf.schrift, "", 6.6)
        pdf.set_text_color(*_MITTEL)
        pdf.multi_cell(b, 3, _text(pdf, "Ohne belastbare Zahl und deshalb nicht gezeigt: "
                                   + ", ".join(s["stufe"] for s in d["trichter"]["entfallen"]) + "."),
                       align="L", new_x=XPos.LEFT, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
        return pdf.get_y()

    def monate(x, y, b):
        art = {"monat": "Monat", "quartal": "Quartal", "jahr": "Jahr"}[d["zeitachse"]["art"]]
        y = _titel_spalte(pdf, x, y, b, f"Bewerbungen je {art}")
        return _saeulen(pdf, x, y + 2, b, d["zeitachse"]["abschnitte"])

    _zwei_spalten(pdf, trichter, monate)

    def wege(x, y, b):
        y = _titel_spalte(pdf, x, y, b, "Welcher Weg führt zu Gesprächen?")
        zeilen = [(z["weg"], z["bewerbungen"], z["gespraeche"]["text"].split(" (")[-1].rstrip(")"),
                   z["gespraeche"]["anzahl"]) for z in d["wege"]["zeilen"]]
        y = _balken(pdf, x, y, b, zeilen)
        pdf.set_xy(x, y)
        pdf.set_font(pdf.schrift, "", 6.6)
        pdf.set_text_color(*_MITTEL)
        pdf.multi_cell(b, 3, _text(pdf, " ".join(t for t in (
            "Hell: Bewerbungen. Dunkel: davon mit Gespräch.", d["wege"]["luecke_satz"]) if t)),
            align="L", new_x=XPos.LEFT, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
        return pdf.get_y()

    def enden(x, y, b):
        n = d["ausgang"]["abgeschlossen"]["wert"]
        y = _titel_spalte(pdf, x, y, b, f"Wie endeten die {n} abgeschlossenen Verfahren?")
        zeilen = [(z["text"], z["anteil"]["anzahl"], str(z["anteil"]["anzahl"]), None)
                  for z in d["ausgang"]["zeilen"]]
        y = _balken(pdf, x, y, b, zeilen)
        if d["satz_absagen"]:
            pdf.set_xy(x, y + .6)
            pdf.set_font(pdf.schrift, "B", 7.6)
            pdf.multi_cell(b, 3.5, _text(pdf, d["satz_absagen"]), align="L",
                           new_x=XPos.LEFT, new_y=YPos.NEXT)
            y = pdf.get_y()
        return y

    _zwei_spalten(pdf, wege, enden)
    _dauer(pdf, d, "Wie lange dauert es?")
    _ansteht(pdf, d)


def _dauer(pdf, d: dict, titel: str, alle: bool = False):
    _ueberschrift(pdf, titel)
    zeilen = [("Bis zur ersten Antwort", d["dauer"]["bis_antwort"]),
              ("Bis zum ersten Gespräch", d["dauer"]["bis_gespraech"])]
    if alle:
        zeilen += [("Bis zur Absage ohne Gespräch", d["dauer"]["bis_absage_ohne_gespraech"]),
                   ("Bis zur Absage nach Gespräch", d["dauer"]["bis_absage_nach_gespraech"])]
    for name, wert in zeilen:
        pdf.set_font(pdf.schrift, "B", 8.2)
        pdf.cell(58, 4.4, _text(pdf, name))
        pdf.set_font(pdf.schrift, "", 8.2)
        pdf.cell(0, 4.4, _text(pdf, wert["text"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    _klein(pdf, d["dauer"]["nachgetragen_satz"])


def _ansteht(pdf, d: dict):
    _ueberschrift(pdf, "Was jetzt ansteht")
    a = d["ansteht"]
    if not a["zeilen"]:
        pdf.set_font(pdf.schrift, "", 8.5)
        pdf.cell(0, 4.5, "Gerade ist kein Nachfassen geplant.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        return
    _tabelle(pdf, ["Bis", "Verfahren", "Nächster Schritt"], [
        [z["datum"] + (" (fällig)" if z["ueberfaellig"] else ""),
         ", ".join(t for t in (z["firma"], z["stelle"]) if t), z["was"]]
        for z in a["zeilen"]], (34, 110, 34))
    _klein(pdf, a["weitere_text"])


def _folgeseiten(pdf, d: dict):
    pdf.add_page()
    _ueberschrift(pdf, "Über welche Quellen kamen die Bewerbungen?")
    q = d["quellen"]
    if q["zeilen"]:
        _tabelle(pdf, ["Quelle", "Bewerbungen", "davon mit Gespräch"],
                 [[z["quelle"], z["bewerbungen"], z["gespraeche"]] for z in q["zeilen"]], (98, 35, 45))
        _klein(pdf, q["weitere_text"])
    _ueberschrift(pdf, "Woran scheiterten die Verfahren?")
    arten = d["absage_arten"]
    if arten["zeilen"]:
        _tabelle(pdf, ["Art", "Anzahl"], [[z["art"], z["anteil"]["text"]] for z in arten["zeilen"]],
                 (130, 48))
        _klein(pdf, arten["weitere_text"])
    else:
        _klein(pdf, "In diesem Zeitraum ist kein Verfahren so geendet.")
    _dauer(pdf, d, "Wie lange dauern die einzelnen Schritte?", alle=True)

    _ueberschrift(pdf, "Meine Suche: was PBP gefunden hat")
    s = d["meine_suche"]
    if not s["verfuegbar"]:
        _klein(pdf, s["hinweis"])
    elif not s["gesichtet"]:
        _klein(pdf, "PBP hat noch keine Stellen gefunden.")
    else:
        pdf.set_font(pdf.schrift, "", 8.5)
        pdf.cell(0, 4.6, _text(pdf, f"{s['gesichtet']} Stellen gesichtet, {s['in_der_liste']} noch in "
                                    f"der Liste, {s['aussortiert']} von dir aussortiert."),
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if s["gruende"]["zeilen"]:
            _tabelle(pdf, ["Warum du aussortiert hast", "Stellen"],
                     [[z["grund"], z["anzahl"]] for z in s["gruende"]["zeilen"]], (140, 38))
            _klein(pdf, s["gruende"]["weitere_text"])

    if d["bewerbungen"]:
        _ueberschrift(pdf, "Alle Bewerbungen im Zeitraum")
        _tabelle(pdf, ["Nr.", "Datum", "Arbeitgeber und Stelle", "Weg", "Stand"], [
            [b["nr"], b["datum"], f"{b['firma']}, {b['stelle']}" if b["stelle"] else b["firma"],
             b["weg"], f"{b['stand']} ({b['stand_datum']})" if b["stand_datum"] else b["stand"]]
            for b in d["bewerbungen"]], (8, 19, 68, 38, 45))
    if d["chronik"]:
        _ueberschrift(pdf, "Was an welchem Tag geschah")
        _tabelle(pdf, ["Tag", "Art", "Was"], [[z["tag"], z["art"], z["was"]] for z in d["chronik"]],
                 (20, 25, 133))


def erzeugen(daten: dict, name: str, pfad) -> Path:
    """Schreibt die Auswertung nach `pfad`."""
    pdf = _Nachweis(format="A4")
    pfade = _dejavu_pfade()
    if pfade:
        try:
            for stil, datei in pfade.items():
                pdf.add_font("DejaVu", stil, str(datei))
            pdf.schrift = "DejaVu"
        except Exception:  # ohne die Schrift: Latin-1
            pdf.schrift = "Helvetica"
    pdf.set_title(_text(pdf, TITEL))
    pdf.set_margins(16, 13, 16)
    pdf.set_auto_page_break(auto=True, margin=19)
    pdf.alias_nb_pages()
    pdf.fuss_links = _text(pdf, f"{name} · Auswertung {daten['zeitraum']['text']}")
    pdf.add_page()
    _seite_eins(pdf, name, daten)
    _folgeseiten(pdf, daten)
    ziel = Path(pfad)
    pdf.output(str(ziel))
    return ziel
