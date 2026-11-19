"""#1391: Claudes Ergebnis heisst „Bewertung“, das „Urteil“ fällt nur der Mensch.

Die Regel steht in `scripts/ui_texte_pruefen.py` (`urteil_funde`). Getestet wird in beide Richtungen: was sie finden muss,
und was sie in Ruhe lassen muss (Bezeichner, das Urteil des Menschen, andere Wörter). Dazu die Probe am echten Bestand:
kein sichtbarer Text, keine Wissensbasis und kein Text für Claude nennt Claudes Ergebnis „Urteil“, und die Werkzeug- und
Feldnamen sind unverändert.
"""
import importlib.util
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _skript():
    spec = importlib.util.spec_from_file_location("ui_texte_pruefen_1391", REPO / "scripts" / "ui_texte_pruefen.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


U = _skript()


# ── Was die Regel finden muss ───────────────────────────────────────────

def test_claudes_ergebnis_als_urteil_ist_ein_fund():
    for text in ("Das Urteil der Detailanalyse steht an der Stelle.",
                 "Stellen mit gelesenem Urteil bleiben stehen.",
                 "Seit dem Urteil hat sich die Grundlage geändert.",
                 "Claude schreibt zu jeder Stelle ein Urteil mit Begründung.",
                 "Nicht aus dem Titel urteilen.",
                 "Der Vorfilter urteilt nicht."):
        assert list(U.urteil_funde(text)), text


def test_in_einem_text_fuer_claude_ist_dein_urteil_claudes_urteil():
    # „du“ ist dort Claude: dieselbe Formulierung, die fürs Dashboard stimmt, ist hier ein Fund.
    assert not list(U.urteil_funde("N Stellen warten auf dein Urteil."))
    assert list(U.urteil_funde("Speichere dein Urteil mit dem Werkzeug.", fuer_claude=True))
    assert list(U.urteil_funde("Schreibe dein Urteil an die Stelle.", fuer_claude=True))


# ── Was sie in Ruhe lassen muss ─────────────────────────────────────────

def test_das_urteil_des_menschen_ist_kein_fund():
    for text in ("3 neue Stellen warten auf dein Urteil.",
                 "Das bleibt dein eigenes Urteil.",
                 "Am Ende gilt das Urteil des Menschen.",
                 "Eine Absage ist eine Antwort, kein Urteil über deinen Wert."):
        assert not list(U.urteil_funde(text)), text
    # auch in einem Text für Claude: das Urteil des Menschen
    assert not list(U.urteil_funde("Am Ende gilt das Urteil des Menschen.", fuer_claude=True))


def test_bezeichner_und_andere_woerter_sind_kein_fund():
    for text in ("Speichere es mit stelle_urteil_speichern(job_hash, urteil, begruendung).",
                 "Das Feld urteil_begruendung bleibt.",
                 "Der Parameter urteil ist eines von EMPFOHLEN, BEDINGT, NICHT_EMPFOHLEN.",
                 "Ein Vorurteil ist keine Bewertung.",
                 "Die Stelle ist noch nicht beurteilt, NICHT_BEURTEILBAR.",
                 "Ein Gattungsurteil über Zeitarbeit sagt nichts über die Firma."):
        assert not list(U.urteil_funde(text)), text


# ── Am echten Bestand ───────────────────────────────────────────────────

def test_kein_text_nennt_claudes_ergebnis_urteil():
    funde = [f for f in U.pruefen() if "(#1391)" in f]
    assert funde == [], "\n".join(funde)


def test_die_wissensbasis_wird_gelesen():
    texte = list(U.wissen_texte())
    assert len(texte) > 500, "die Hilfe-Wissensbasis wird nicht mehr gelesen: die Regel hätte dort nichts zu prüfen"
    assert any("Bewertung" in t for _, _, t in texte)


def test_werkzeug_und_feldnamen_bleiben():
    quelle = (REPO / "src" / "bewerbungs_assistent" / "tools" / "jobs.py").read_text(encoding="utf-8-sig")
    assert "def stelle_urteil_speichern(" in quelle
    # der Parameter heisst weiter `urteil`, das Ergebnis weiter EMPFOHLEN/BEDINGT/NICHT_EMPFOHLEN/NICHT_BEURTEILBAR
    assert re.search(r"def stelle_urteil_speichern\([^)]*urteil", quelle, re.S)
    passung = (REPO / "src" / "bewerbungs_assistent" / "services" / "passung.py").read_text(encoding="utf-8-sig")
    assert "NICHT_BEURTEILBAR" in passung


def test_die_beschreibung_des_werkzeugs_sagt_bewertung():
    katalog = (REPO / "src" / "bewerbungs_assistent" / "services" / "werkzeug_katalog.py").read_text(encoding="utf-8-sig")
    a = katalog.index('"stelle_urteil_speichern": (')
    block = katalog[a:a + 700]
    assert "Bewertung" in block


def test_sichtbare_oberflaeche_sagt_bewertung():
    jobs = (REPO / "frontend" / "src" / "pages" / "JobsPage.jsx").read_text(encoding="utf-8")
    assert "Gelesene Bewertung" in jobs and "Gelesenes Urteil" not in jobs
    hilfe = (REPO / "frontend" / "src" / "lib" / "hilfe.js").read_text(encoding="utf-8")
    assert "Punkte und Bewertung" in hilfe
    wissen = json.loads((REPO / "src" / "bewerbungs_assistent" / "content" / "hilfe_wissen.json").read_text(encoding="utf-8"))
    titel = [a["titel"] for a in wissen["abschnitte"]]
    assert "Punkte und Bewertung" in titel and "Punkte und Urteil" not in titel
