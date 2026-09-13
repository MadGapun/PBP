"""Tests fuer #1044 (G49): Karte und Popup zeigen eine Stelle gleich.

Das Popup "Stellendetails" war eigener Code und las Rohwerte: keine
Entfernung, "festanstellung" klein und grau, kein Umfang, ein Gehalt mit
Bindestrich, "(jaehrlich)" und "(geschaetzt)", "Unbekannt" statt
"Unbekannte Firma". Die Daten waren dieselben — die Darstellung stand
zweimal im Code (#963 im Frontend).

Die Werte selbst prueft `frontend/src/lib/stellenAngaben.test.mjs` im
CI-Schritt. Hier steht, dass BEIDE Ansichten sie auch lesen.
"""
import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
SEITE = WURZEL / "frontend" / "src" / "pages" / "JobsPage.jsx"
LIB = WURZEL / "frontend" / "src" / "lib" / "stellenAngaben.js"
WORKFLOW = WURZEL / ".github" / "workflows" / "tests.yml"

HELFER = ("firmaText", "anstellungsform", "umfangText", "gehaltText", "entfernungText")


def _seite() -> str:
    return SEITE.read_text(encoding="utf-8")


def _popup() -> str:
    """Der Abschnitt des Detail-Dialogs (Ansicht, nicht Bearbeiten)."""
    text = _seite()
    start = text.index('title={detailDialog.editing ? "Stelle bearbeiten" : "Stellendetails"}')
    ende = text.index("#765: nie ein stiller toter Link", start)
    return text[start:ende]


def _karte() -> str:
    text = _seite()
    start = text.index("{anstellungsform(job) ? (")
    ende = text.index("#1032 AK 4", start)
    return text[start:ende]


def test_die_seite_liest_die_gemeinsame_fassung():
    text = _seite()
    assert "@/lib/stellenAngaben" in text
    assert "const ANSTELLUNGSFORM_TEXT" not in text, "zweite Fassung in der Seite"
    assert "const ANSTELLUNGSFORM_TON" not in text
    assert LIB.exists()


def test_karte_und_popup_nutzen_jeden_helfer():
    karte, popup = _karte(), _popup()
    for helfer in HELFER:
        assert f"{helfer}(job" in karte, ("Karte", helfer)
        assert f"{helfer}(detailDialog.job" in popup, ("Popup", helfer)


@pytest.mark.parametrize("ansicht, obj", [("karte", "job"), ("popup", "detailDialog.job")])
def test_karte_und_popup_geben_das_ergebnis_auch_aus(ansicht, obj):
    """Ein Aufruf in der BEDINGUNG genuegt nicht — der Wert muss im Element
    stehen. Gegenprobe v1.7.103: mit leerer Entfernungszeile im Popup blieb
    die reine Aufruf-Pruefung gruen, weil `entfernungText(...)` noch in der
    Bedingung stand."""
    quelle = _karte() if ansicht == "karte" else _popup()
    for ausgabe in (f"{{firmaText({obj})}}",
                    f"{{anstellungsform({obj}).text}}",
                    f"{{umfangText({obj})}}",
                    f"{{gehaltText({obj}, formatCurrency)}}</p>",
                    f"{{entfernungText({obj})}}</p>"):
        assert ausgabe in quelle, (ansicht, ausgabe)


def test_das_popup_zeigt_keine_rohwerte_mehr():
    """Die fuenf Punkte aus dem Bericht, am Quelltext des Popups."""
    popup = _popup()
    assert "{detailDialog.job.employment_type}</Badge>" not in popup
    assert "salary_type" not in popup
    assert "(geschaetzt)" not in popup
    assert '|| "Unbekannt"' not in popup
    assert re.search(r"formatCurrency\(detailDialog\.job\.salary_min\)\} - ", popup) is None


def test_der_node_test_laeuft_im_ci():
    """Ein Test, der nicht aufgerufen wird, schuetzt nichts (DoD 8c)."""
    assert "node frontend/src/lib/stellenAngaben.test.mjs" in WORKFLOW.read_text(encoding="utf-8")
