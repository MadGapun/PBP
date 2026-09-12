"""Tests fuer #1027: Auswahlfelder nennen die Antwort, nicht nur die Frage.

`Field` wickelt seinen Inhalt in ein `<label>`. `SelectInput` ist kein
natives `<select>`, sondern ein `<button>` plus Portal-Panel — und ein
`<button>` ist ein labelable element. Das umschliessende Label gewann
damit gegen den Knopfinhalt: am laufenden Dashboard hiess der Knopf
`Welches Profil?`, waehrend sichtbar `Alle Profile` stand. Ein
Screenreader bekam den gewaehlten Wert eines Auswahlfeldes nie zu hoeren.

Der BELEG steht im Browser-Test
(`test_dashboard_browser.py::test_gefahrenzone_zeigt_bereiche_mit_zahlen`):
er spricht den Knopf ueber seinen barrierefreien Namen an und prueft,
dass der Name mit dem Wert wandert. Ein Grep belegt nur, dass eine
Zeichenkette dasteht (v1.7.71 MERKE 9). Die Tests hier halten die
BAUFORM fest, damit sie bei einem Umbau des Bausteins nicht still
verschwindet — und laufen ohne Browser, also auch dort, wo die
Browser-Tests uebersprungen werden.
"""
import re
from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


UI = _repo() / "frontend" / "src" / "components" / "ui.jsx"
BROWSER_TEST = _repo() / "tests" / "test_dashboard_browser.py"


def _funktion(quelle: str, name: str) -> str:
    start = quelle.index(f"export function {name}(")
    naechste = quelle.find("\nexport function ", start + 1)
    return quelle[start:naechste if naechste != -1 else len(quelle)]


def test_field_gibt_die_kennung_seiner_beschriftung_weiter():
    quelle = UI.read_text(encoding="utf-8")
    field = _funktion(quelle, "Field")
    assert "useId()" in field
    assert "id={labelId}" in field, "Die Beschriftung traegt keine Kennung"
    assert "FieldLabelContext.Provider" in field


def test_selectinput_setzt_den_namen_aus_beschriftung_und_wert():
    quelle = UI.read_text(encoding="utf-8")
    select = _funktion(quelle, "SelectInput")
    assert "useContext(FieldLabelContext)" in select
    assert re.search(r"`\$\{fieldLabelId\} \$\{valueId\}`", select), (
        "Der Name nennt nicht Beschriftung UND gewaehlten Wert")
    assert "id={valueId}" in select, "Der Wert traegt keine Kennung"


def test_ein_eigenes_aria_label_des_aufrufers_geht_vor():
    """Wer einem Auswahlfeld bewusst einen Namen gibt, behaelt ihn.

    Sonst ueberschriebe der Baustein eine Entscheidung des Aufrufers —
    dieselbe Bauform wie #988 in der Gegenrichtung.
    """
    select = _funktion(UI.read_text(encoding="utf-8"), "SelectInput")
    assert 'props["aria-label"]' in select
    assert 'props["aria-labelledby"]' in select


def test_der_knopf_sagt_ob_die_auswahl_offen_ist():
    select = _funktion(UI.read_text(encoding="utf-8"), "SelectInput")
    assert "aria-expanded={open}" in select


def test_der_workaround_im_browser_test_ist_weg():
    """AK 5: der Test sprach den Knopf ueber seinen TEXT an, mit einem
    Kommentar, der auf dieses Issue verwies."""
    quelle = BROWSER_TEST.read_text(encoding="utf-8")
    assert 'page.locator("button", has_text="Alle Profile")' not in quelle
    assert 'name="Welches Profil? Alle Profile"' in quelle
