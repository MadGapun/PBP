"""#1301: EINE Farbtabelle fuer die Anstellungsform.

Vorher hatte jede Ansicht ihr eigenes Schema: Freelance war auf der
Stellenkarte violett, im Abzeichen gruen und auf der Bewerbungskarte
smaragd; Festanstellung war auf der Karte gar nicht markiert; Zeitarbeit
war im Abzeichen rot, auf der Bewerbungskarte gruen wie Freelance und im
MCP "Sonstige".

Jetzt steht die Zuordnung zweimal, aber gegeneinander geprueft:
`ANSTELLUNGSFORM_TON` im Dashboard (frontend/src/lib/stellenAngaben.js)
und `ANSTELLUNGSFORM_FARBE` in services/stellenart.py fuer das Werkzeug
`stellen_anzeigen`. Die Werte selbst (Marke, Kontrast) prueft
`frontend/src/lib/stellenAngaben.test.mjs`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from bewerbungs_assistent.services import stellenart

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "frontend"
LIB = FRONTEND / "src" / "lib" / "stellenAngaben.js"
UI = FRONTEND / "src" / "components" / "ui.jsx"
TAILWIND = FRONTEND / "tailwind.config.js"
STYLES = FRONTEND / "src" / "styles.css"
JOBS_TOOL = WURZEL / "src" / "bewerbungs_assistent" / "tools" / "jobs.py"

#: Die Ansichten, die eine Anstellungsform zeigen, und was sie zeigen.
ANSICHTEN = {
    "Stellenkarte und Popup": FRONTEND / "src" / "pages" / "JobsPage.jsx",
    "Bewerbungskarte": FRONTEND / "src" / "pages" / "ApplicationsPage.jsx",
    "Stelle aus Bewerbung/Firma": FRONTEND / "src" / "components" / "InlineJobDetailModal.jsx",
}

#: Welcher farbige Kreis zu welchem Ton gehoert (der naechste, den es gibt).
KREIS_ZU_TON = {
    "sky": "\U0001F535", "success": "\U0001F7E2", "violett": "\U0001F7E3",
    "mandarine": "\U0001F7E0", "gelb": "\U0001F7E1", "braun": "\U0001F7E4",
    "neutral": "⚪",
}


def _lies(pfad: Path) -> str:
    return pfad.read_text(encoding="utf-8")


def _js_objekt(name: str) -> dict[str, str]:
    """Liest `export const NAME = { schluessel: "wert", ... };` aus der Lib."""
    text = _lies(LIB)
    m = re.search(r"export const " + name + r" = \{(.*?)\};", text, re.S)
    assert m, f"{name} fehlt in {LIB.name}"
    return dict(re.findall(r'(\w+):\s*"([^"]*)"', m.group(1)))


def test_python_tabelle_deckt_jede_form():
    assert set(stellenart.ANSTELLUNGSFORM_FARBE) == set(stellenart.ANSTELLUNGSFORMEN)


def test_dashboard_und_mcp_haben_dieselben_toene():
    js = _js_objekt("ANSTELLUNGSFORM_TON")
    py = {form: ton for form, (ton, _z, _n) in stellenart.ANSTELLUNGSFORM_FARBE.items()}
    assert js == py


def test_unbekannt_ist_in_beiden_grau():
    m = re.search(r'export const ANSTELLUNGSFORM_TON_UNBEKANNT = "(\w+)"', _lies(LIB))
    assert m and m.group(1) == stellenart.ANSTELLUNGSFORM_FARBE_UNBEKANNT[0] == "neutral"


def test_namen_gleich_in_beiden():
    js = _js_objekt("ANSTELLUNGSFORM_TEXT")
    py = {form: name for form, (_t, _z, name) in stellenart.ANSTELLUNGSFORM_FARBE.items()}
    assert js == py


def test_jede_form_eigene_farbe_vorgabe_111():
    toene = [t for t, _z, _n in stellenart.ANSTELLUNGSFORM_FARBE.values()]
    assert len(set(toene)) == len(toene)
    assert stellenart.ANSTELLUNGSFORM_FARBE["festanstellung"][0] == "sky"
    assert stellenart.ANSTELLUNGSFORM_FARBE["freelance"][0] == "success"
    assert not {"amber", "danger", "neutral"} & set(toene)


def test_kennzeichen_passt_zum_ton():
    for form, (ton, zeichen, _n) in stellenart.ANSTELLUNGSFORM_FARBE.items():
        assert KREIS_ZU_TON[ton] == zeichen, form
    ton, zeichen, _n = stellenart.ANSTELLUNGSFORM_FARBE_UNBEKANNT
    assert KREIS_ZU_TON[ton] == zeichen


@pytest.mark.parametrize("form", stellenart.ANSTELLUNGSFORMEN)
def test_mcp_nennt_jede_form_beim_namen(form):
    zeichen, label = stellenart.form_kennzeichen(form)
    assert label == f"{zeichen} {stellenart.ANSTELLUNGSFORM_FARBE[form][2]}"
    assert "Sonstige" not in label


def test_mcp_unbekannt_grau_und_nicht_festanstellung():
    for leer in ("", None, "  "):
        zeichen, label = stellenart.form_kennzeichen(leer)
        assert zeichen == "⚪" and label == "⚪ Anstellungsform unbekannt"
    zeichen, label = stellenart.form_kennzeichen("arbeitnehmerueberlassung")
    assert zeichen == "⚪" and label.endswith("arbeitnehmerueberlassung")


def test_stellen_anzeigen_liest_die_tabelle():
    text = _lies(JOBS_TOOL)
    assert "form_kennzeichen(emp_type)" in text
    assert "Sonstige\"" not in text


def test_jeder_ton_ist_gestaltet():
    """Ein Ton ohne Klassen faellt still auf 'neutral' zurueck."""
    ui, tw, css = _lies(UI), _lies(TAILWIND), _lies(STYLES)
    badge = ui[ui.index("export function Badge"):]
    badge = badge[:badge.index("};")]
    karte = _js_objekt("KARTE_TON")
    hell = css[css.index('[data-theme="light"]'):]
    for ton, _z, _n in stellenart.ANSTELLUNGSFORM_FARBE.values():
        assert f"    {ton}:" in badge, f"Badge kennt den Ton {ton} nicht"
        assert karte.get(ton), f"Kartenrand fuer {ton} fehlt"
        if ton not in ("sky", "success"):
            assert f'{ton}: "rgb(var(--color-{ton})' in tw, ton
            assert f"--color-{ton}:" in css[:css.index('[data-theme="light"]')], ton
            assert f"--color-{ton}:" in hell, ton


@pytest.mark.parametrize("ansicht", sorted(ANSICHTEN))
def test_jede_ansicht_liest_die_tabelle(ansicht):
    text = _lies(ANSICHTEN[ansicht])
    assert "anstellungsformMarke(" in text, ansicht
    assert "<Badge tone={form.ton}>{form.text}</Badge>" in text, ansicht
    # die alten Einzelschemata
    for alt in ("violet-400", "emerald-600", "emerald-950", '<Badge tone="success">Freelance</Badge>'):
        assert alt not in text, (ansicht, alt)


def test_stellenkarte_faerbt_jede_form():
    """Festanstellung war auf der Karte gar nicht markiert (nur Freelance)."""
    text = _lies(ANSICHTEN["Stellenkarte und Popup"])
    karte = text[text.index("data-stellenkarte"):]
    karte = karte[:karte.index("data-kernaussage")]
    assert "!job.is_pinned && anstellungsformMarke(job.employment_type).karte" in karte
    assert 'job.employment_type === "freelance"' not in karte


def test_bewerbung_kein_stilles_festanstellung():
    """Die Auswahl der Bewerbung zeigte ohne Angabe 'Festanstellung' und kannte
    Zeitarbeit und Ausbildung nicht."""
    text = _lies(ANSICHTEN["Bewerbungskarte"])
    assert 'value={app.job_employment_type || "festanstellung"}' not in text
    assert "Object.entries(ANSTELLUNGSFORM_TEXT).map" in text
