"""Praxisprobe 1.8 (05.10.2026), Teil Texte: Kennungen aus der Planung stehen in Sätzen, die ein Mensch liest.

Auf der Seite „Erweiterungen“ eines frischen Rechners stand „Schaltet frei: Auto-OCR beim Dokument-Import (E19)“ — E19 ist eine
Position im Plan, für eine Bewerberin ohne Bedeutung. Der Text-Prüfer (G66) sucht Umlaute und Begriffe, aber keine Kennungen.

Eine Regel, die den ganzen Bestand auf einmal verbietet, scheitert an den alten Stellen; deshalb gilt eine OBERGRENZE: Die
Zahl der Fundstellen darf nur sinken. Wer eine beseitigt, senkt `ALTBESTAND` mit.
"""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (E19), (B18), (#594), (Issue #12), „#1045“ — aber nicht Farbwerte wie #666 in einem Stil-Block
KENNUNG = re.compile(r"\((?:[A-Z]{1,2}\d{1,3}(?:/#?\d+)?|#\d{2,5})\)|(?<![\w&])#\d{3,5}\b")

#: Fundstellen, die beim Einführen der Regel (05.10.2026) übrig blieben: Erklärzeilen im Score (#827, #940, #942, #968, #989,
#: #1045, #1052), zwei Metadaten-Felder und ein Hinweis zum Ausschluss-Keyword. Sie sind eine eigene Aufgabe (Issue #1170).
ALTBESTAND = 13


def _pruefer():
    spec = importlib.util.spec_from_file_location("ui_texte_pruefen_pp8", ROOT / "scripts" / "ui_texte_pruefen.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _fundstellen() -> list:
    p = _pruefer()
    funde = []
    for datei in p.UI_DATEIEN:
        funde += [(datei.name, zeile, text) for zeile, text in p.texte(datei)]
    funde += [(Path(d).name, zeile, text) for d, zeile, text in p.backend_texte()]
    funde += [(Path(d).name, zeile, text) for d, zeile, text in p.katalog_texte()]
    return [(name, zeile, m.group(0), text[:80])
            for name, zeile, text in funde
            if "<style>" not in text and "font-family" not in text
            for m in KENNUNG.finditer(text)]


def test_pp8_die_kennungen_in_anzeigetexten_werden_nicht_mehr():
    funde = _fundstellen()
    assert len(funde) <= ALTBESTAND, (
        f"{len(funde)} statt höchstens {ALTBESTAND}: " + "; ".join(f"{n}:{z} {k}" for n, z, k, _ in funde))


def test_pp8_die_texte_der_praxisprobe_sind_sauber():
    gefunden = {(n, k) for n, _, k, _ in _fundstellen()}
    for nicht in (("components.py", "(E19)"), ("components.py", "(B18)"), ("SettingsPage.jsx", "(#594)")):
        assert nicht not in gefunden, nicht


def test_pp8_die_erweiterungen_nennen_ihre_funktion_in_klartext():
    from bewerbungs_assistent.services import components
    texte = [d["freigeschaltete_funktion"] for d in components.COMPONENTS.values()] \
        if hasattr(components, "COMPONENTS") else []
    if not texte:                                      # Name der Registry nicht bekannt: aus dem Quelltext lesen
        quelle = (ROOT / "src" / "bewerbungs_assistent" / "services" / "components.py").read_text(encoding="utf-8")
        texte = re.findall(r'"freigeschaltete_funktion":\s*\(?\s*"([^"]+)"', quelle)
    assert texte, "keine Komponenten-Texte gefunden"
    for t in texte:
        assert not KENNUNG.search(t), t
        assert "linkedin_browser_search" not in t, "ein Werkzeugname für Claude gehört nicht in die Karte"
