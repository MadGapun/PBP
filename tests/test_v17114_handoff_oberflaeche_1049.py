"""Oberflaechen-Guards fuer #1049 — Namen und Handoff-Karte.

Zwei Elemente hiessen "Jobsuche starten" und taten Verschiedenes: die
Prompt-Karte im Schnellzugriff (Lauf mit Claude) und der Knopf auf der
Stellen-Seite (interner Lauf). Wer den Knopf drueckte, erwartete den
Claude-Teil.
"""
import re
import sys
from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

SEITEN = _repo() / "frontend" / "src" / "pages"
KOMPONENTEN = _repo() / "frontend" / "src" / "components"


def _ohne_kommentare(text: str) -> str:
    return "\n".join(z for z in text.splitlines()
                     if not z.lstrip().startswith(("//", "*", "/*", "{/*")))


def test_die_prompt_karte_heisst_jobsuche_mit_claude():
    from bewerbungs_assistent.services import prompt_katalog
    eintrag = prompt_katalog.eintrag("jobsuche_workflow")
    assert eintrag is not None, "Der Katalog-Eintrag fehlt."
    assert eintrag["titel"] == "Jobsuche mit Claude"


def test_der_workspace_hinweis_auf_den_prompt_heisst_ebenso():
    from bewerbungs_assistent.services import workspace_service
    quelle = Path(workspace_service.__file__).read_text(encoding="utf-8")
    block = quelle[quelle.index('"jobsuche_erneuern"'):]
    block = block[:block.index("},")]
    assert '"action_type": "prompt"' in block
    assert '"action_label": "Jobsuche mit Claude"' in block


def test_jeder_interne_start_knopf_sagt_intern():
    """Wo `startJobsuche()` ausgeloest wird, steht nicht mehr "Jobsuche starten"."""
    funde = []
    for datei in ("JobsPage.jsx", "DashboardPage.jsx"):
        code = _ohne_kommentare((SEITEN / datei).read_text(encoding="utf-8-sig"))
        for treffer in re.finditer(r"startJobsuche\(\)", code):
            umfeld = code[treffer.start():treffer.start() + 260]
            if re.search(r">\s*\n?\s*Jobsuche starten", umfeld) or \
                    '"Jobsuche starten"' in code[max(0, treffer.start() - 200):treffer.start()]:
                funde.append(datei)
    assert not funde, f"Mehrdeutiges Etikett am internen Lauf: {funde}"
    for datei in ("JobsPage.jsx", "DashboardPage.jsx"):
        assert "Interne Jobsuche starten" in (SEITEN / datei).read_text(encoding="utf-8-sig"), datei


def test_die_karte_nimmt_liste_und_prompt_vom_server():
    karte = (KOMPONENTEN / "BrowserHandoffKarte.jsx").read_text(encoding="utf-8")
    assert '"/api/jobsuche/browser-quellen"' in karte
    assert "copyPrompt(daten.prompt)" in karte
    # Keine eigene Fassung der Pflichten im Frontend (#963).
    assert "VOLLTEXT" not in karte and "Rohtreffer" not in karte


def test_die_stellen_seite_zeigt_die_karte():
    seite = (SEITEN / "JobsPage.jsx").read_text(encoding="utf-8-sig")
    assert 'import BrowserHandoffKarte from "@/components/BrowserHandoffKarte"' in seite
    assert "<BrowserHandoffKarte" in _ohne_kommentare(seite)
