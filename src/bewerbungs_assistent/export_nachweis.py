"""PDF "Nachweis der Bewerbungsbemuehungen" (#798, Stufe 3).

Ein bis drei Seiten fuer Agentur und Jobcenter. Inhalte aus
`services/nachweis_daten.py`; dieses Modul rechnet nichts. Jede Seite traegt
Name, Zeitraum und Seitenzahl. Druckfest: Schwarz und Grau, die Helligkeit
traegt die Aussage.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fpdf import FPDF
from fpdf.enums import TableCellFillMode, XPos, YPos
from fpdf.fonts import FontFace

from .export_report import _KOSTEN_ART, _dejavu_pfade

TITEL = "Nachweis der Bewerbungsbemühungen"
SCHLUSS = ("Dieser Nachweis enthält nur Angaben, die der Bewerber selbst erfasst hat. "
           "Er enthält bewusst keine Bewertungen und keine geschätzten Zeiten.")
KOSTEN_HINWEIS = "Die Aufstellung ist kein Antrag auf Erstattung. Belege liegen beim Bewerber."

_DUNKEL = (35, 35, 35)
_MITTEL = (95, 95, 95)
_LINIE = (190, 190, 190)
_FLAECHE = (236, 236, 236)
_BALKEN = (80, 80, 80)


def _eur(wert: float, unicode: bool) -> str:
    text = f"{wert:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} {'€' if unicode else 'EUR'}"


class _Nachweis(FPDF):
    fuss_links = ""
    schrift = "Helvetica"

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(*_LINIE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_y(-12)
        self.set_font(self.schrift, "", 7.5)
        self.set_text_color(*_MITTEL)
        self.cell(0, 4, self.fuss_links, align="L")
        # Linksbuendig ab fester Stelle: fpdf misst den Platzhalter {nb}, nicht die Zahl.
        self.set_x(self.w - self.r_margin - 40)
        self.cell(40, 4, _text(self, f"Seite {self.page_no()} von {{nb}} · erstellt mit PBP"))
        self.set_text_color(0, 0, 0)


def _text(pdf: _Nachweis, wert) -> str:
    text = "" if wert is None else str(wert)
    if pdf.schrift == "DejaVu":
        return text
    text = text.replace("€", "EUR").replace("·", "-").replace("–", "-")
    return text.encode("latin-1", "replace").decode("latin-1")


def _ueberschrift(pdf: _Nachweis, titel: str, platz: float = 28):
    if pdf.get_y() > pdf.h - pdf.b_margin - platz:
        pdf.add_page()
    pdf.ln(3)
    pdf.set_font(pdf.schrift, "B", 11)
    pdf.set_text_color(*_DUNKEL)
    pdf.cell(0, 6, _text(pdf, titel), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)


def _tabelle(pdf: _Nachweis, kopf: list, zeilen: list, breiten: tuple, ausrichtung=None):
    """Bricht um, wiederholt die Kopfzeile, teilt keine Zeile."""
    pdf.set_font(pdf.schrift, "", 8)
    with pdf.table(col_widths=breiten, text_align=tuple(ausrichtung or ["LEFT"] * len(kopf)),
                   line_height=4.2, first_row_as_headings=True, borders_layout="HORIZONTAL_LINES",
                   cell_fill_color=(255, 255, 255), cell_fill_mode=TableCellFillMode.ALL,
                   headings_style=FontFace(emphasis="BOLD", fill_color=_FLAECHE)) as tab:
        reihe = tab.row()
        for k in kopf:
            reihe.cell(_text(pdf, k))
        for zeile in zeilen:
            reihe = tab.row()
            for zelle in zeile:
                reihe.cell(_text(pdf, zelle))
    pdf.ln(1)


def _kopf(pdf: _Nachweis, name: str, daten: dict, einstellungen: dict):
    pdf.set_font(pdf.schrift, "B", 17)
    pdf.set_text_color(*_DUNKEL)
    pdf.cell(0, 9, _text(pdf, TITEL), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf.schrift, "B", 11)
    pdf.cell(0, 6, _text(pdf, name), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf.schrift, "", 9.5)
    pdf.cell(0, 5, _text(pdf, f"Zeitraum {daten['zeitraum']['text']}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_MITTEL)
    pdf.set_font(pdf.schrift, "", 8)
    pdf.cell(0, 4.5, _text(pdf, f"Erstellt am {daten['erstellt_text']}. "
                                "Alle Angaben auf diesem Nachweis gelten für diesen Zeitraum."),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    if einstellungen.get("arbeitsamt_block_enabled"):
        felder = [("Kundennummer", einstellungen.get("ba_vermittlungsnummer")),
                  ("Aktenzeichen", einstellungen.get("ba_aktenzeichen")),
                  ("Beratung", einstellungen.get("ba_berater_name")),
                  ("Stelle", einstellungen.get("ba_berater_stelle"))]
        felder = [(k, v) for k, v in felder if v]
        if felder:
            pdf.ln(1.5)
            for k, v in felder:
                pdf.set_font(pdf.schrift, "B", 8.5)
                pdf.cell(28, 4.6, _text(pdf, k))
                pdf.set_font(pdf.schrift, "", 8.5)
                pdf.cell(0, 4.6, _text(pdf, v), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)


def _kacheln(pdf: _Nachweis, kacheln: list):
    breite = (pdf.w - pdf.l_margin - pdf.r_margin - 3 * 3) / 4
    y = pdf.get_y()
    for i, k in enumerate(kacheln):
        x = pdf.l_margin + i * (breite + 3)
        pdf.set_draw_color(*_LINIE)
        pdf.rect(x, y, breite, 21)
        pdf.set_xy(x + 2, y + 1.5)
        pdf.set_font(pdf.schrift, "B", 15)
        pdf.cell(breite - 4, 7, str(k["wert"]))
        pdf.set_xy(x + 2, y + 9)
        pdf.set_font(pdf.schrift, "B", 8)
        pdf.cell(breite - 4, 4, _text(pdf, k["name"]))
        pdf.set_xy(x + 2, y + 13.5)
        pdf.set_font(pdf.schrift, "", 6.8)
        pdf.set_text_color(*_MITTEL)
        pdf.multi_cell(breite - 4, 3, _text(pdf, k["hinweis"]), align="L")
        pdf.set_text_color(0, 0, 0)
    pdf.set_xy(pdf.l_margin, y + 24)


def _wochen(pdf: _Nachweis, wochen: list):
    if not wochen:
        return
    _ueberschrift(pdf, "Aktivität je Kalenderwoche", 12 + 5 * len(wochen))
    hoechste = max((w["anzahl"] for w in wochen), default=0) or 1
    spur = 50
    for w in wochen:
        y = pdf.get_y()
        pdf.set_font(pdf.schrift, "B", 8)
        pdf.cell(16, 4.8, w["kw"])
        x = pdf.get_x()
        pdf.set_fill_color(*_FLAECHE)
        pdf.rect(x, y + 1, spur, 2.8, style="F")
        if w["anzahl"]:
            pdf.set_fill_color(*_BALKEN)
            pdf.rect(x, y + 1, spur * w["anzahl"] / hoechste, 2.8, style="F")
        pdf.set_x(x + spur + 3)
        pdf.set_font(pdf.schrift, "", 8)
        pdf.cell(0, 4.8, _text(pdf, w["text"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def erzeugen(daten: dict, name: str, pfad, einstellungen: Optional[dict] = None) -> Path:
    """Schreibt den Nachweis nach `pfad`."""
    einstellungen = einstellungen or {}
    pdf = _Nachweis(format="A4")
    pfade = _dejavu_pfade()
    if pfade:
        try:
            for stil, datei in pfade.items():
                pdf.add_font("DejaVu", stil, str(datei))
            pdf.schrift = "DejaVu"
        except Exception:  # ohne die Schrift: Latin-1, Betraege mit EUR
            pdf.schrift = "Helvetica"
    pdf.set_title(_text(pdf, TITEL))
    pdf.set_margins(16, 14, 16)
    pdf.set_auto_page_break(auto=True, margin=19)
    pdf.alias_nb_pages()
    pdf.fuss_links = _text(pdf, f"{name} · Nachweis {daten['zeitraum']['text']}")
    pdf.add_page()

    _kopf(pdf, name, daten, einstellungen)
    _kacheln(pdf, daten["kacheln"])
    _wochen(pdf, daten["wochen"])

    stand = f"Stand am {daten['stichtag_text']}"
    _ueberschrift(pdf, "Bewerbungen im Zeitraum")
    if daten["bewerbungen"]:
        _tabelle(pdf, ["Nr.", "Datum", "Arbeitgeber und Stelle", "Weg", stand], [
            [b["nr"], b["datum"], f"{b['firma']}, {b['stelle']}" if b["stelle"] else b["firma"],
             b["weg"], f"{b['stand']} ({b['stand_datum']})" if b["stand_datum"] else b["stand"]]
            for b in daten["bewerbungen"]], (8, 19, 68, 38, 45))
    else:
        pdf.set_font(pdf.schrift, "", 9)
        pdf.cell(0, 5, _text(pdf, "In diesem Zeitraum ist keine Bewerbung erfasst."),
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if daten["laufende_frueher"]:
        _ueberschrift(pdf, "Laufende Verfahren aus früheren Zeiträumen")
        _tabelle(pdf, ["Beworben", "Arbeitgeber und Stelle", stand], [
            [l["datum"], f"{l['firma']}, {l['stelle']}" if l["stelle"] else l["firma"], l["stand"]]
            for l in daten["laufende_frueher"]], (20, 113, 45))

    if daten["chronik"]:
        _ueberschrift(pdf, "Was an welchem Tag geschah")
        _tabelle(pdf, ["Tag", "Art", "Was"],
                 [[z["tag"], z["art"], z["was"]] for z in daten["chronik"]], (20, 25, 133))

    kosten = daten.get("kosten")
    if kosten and kosten["posten"]:
        uni = pdf.schrift == "DejaVu"
        _ueberschrift(pdf, "Bewerbungskosten im Zeitraum")
        zeilen = [[p["datum"], _KOSTEN_ART.get(p["kind"], p["kind"]), p["was"], _eur(p["betrag"], uni)]
                  for p in kosten["posten"]]
        zeilen.append(["", "", "Summe", _eur(kosten["summe_eur"], uni)])
        _tabelle(pdf, ["Datum", "Art", "Wofür", "Betrag"], zeilen, (20, 25, 108, 25),
                 ["LEFT", "LEFT", "LEFT", "RIGHT"])
        pdf.set_font(pdf.schrift, "", 7.5)
        pdf.set_text_color(*_MITTEL)
        pdf.multi_cell(0, 3.6, _text(pdf, KOSTEN_HINWEIS), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)

    platz = 46 if einstellungen.get("berater_kommentar_block") else 26
    if pdf.get_y() > pdf.h - pdf.b_margin - platz:
        pdf.add_page()
    if einstellungen.get("berater_kommentar_block"):
        _ueberschrift(pdf, "Notizen aus dem Beratungsgespräch", platz)
        pdf.set_draw_color(*_LINIE)
        for _ in range(3):
            pdf.ln(6)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(11)
    y = pdf.get_y()
    pdf.set_draw_color(*_DUNKEL)
    pdf.line(pdf.l_margin, y, pdf.l_margin + 70, y)
    pdf.line(pdf.l_margin + 90, y, pdf.w - pdf.r_margin, y)
    pdf.set_font(pdf.schrift, "", 7.5)
    pdf.set_xy(pdf.l_margin, y + 0.8)
    pdf.cell(90, 3.5, "Ort, Datum")
    pdf.cell(0, 3.5, "Unterschrift", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_text_color(*_MITTEL)
    pdf.multi_cell(0, 3.5, _text(pdf, SCHLUSS), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)

    ziel = Path(pfad)
    pdf.output(str(ziel))
    return ziel
