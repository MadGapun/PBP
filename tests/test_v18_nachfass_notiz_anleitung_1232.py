"""#1232 (1.8-Linie): die Rueckfuehrungs-Anleitung fuer ein Gespraechsprotokoll nennt art='kontakt'.

Die Linie 1.8 hat eine eigene Anleitung je Dokumentart (`document_analysis_prompts.RUECKFUEHRUNG`, #1200).
Ein Gespraechsprotokoll ist Kontakt mit dem Arbeitgeber: die offene Nachfass-Erinnerung wird damit
hinfaellig. Die uebrigen Arten (Absage, Eingangsbestaetigung, Vertrag, Stellenausschreibung, Fallback)
schreiben eine interne Notiz oder aendern den Status, der selbst schliesst — dort gilt die Vorgabe `intern`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.document_analysis_prompts import RUECKFUEHRUNG  # noqa: E402


def _text(schluessel: str) -> str:
    return " ".join(RUECKFUEHRUNG[schluessel])


def test_1232_das_gespraechsprotokoll_ist_kontakt():
    text = _text("gespraechsnotiz")
    assert "art='kontakt'" in text
    assert "Nachfass-Erinnerung" in text and "hinfällig" in text


def test_1232_die_uebrigen_arten_lassen_die_vorgabe_intern():
    for schluessel in ("absage", "eingangsbestaetigung", "vertrag", "stellenausschreibung", "fallback"):
        assert "art='kontakt'" not in _text(schluessel), schluessel


def test_1232_jeder_aufruf_nennt_die_pflichtparameter():
    """Der Waechter #1200 A12 verlangt es; hier steht der Grund: ein Aufruf ohne `notiz` ist keiner."""
    for schluessel, schritte in RUECKFUEHRUNG.items():
        for schritt in schritte:
            if "bewerbung_notiz(" in schritt:
                assert "bewerbung_notiz(bewerbung_id," in schritt, (schluessel, schritt)
