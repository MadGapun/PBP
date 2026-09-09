"""Tests fuer v1.7.57 — #958: Schreiben stand vor Lesen.

Gemeldet am 25.08.2026 aus dem Bewerbungs-Detail:

    Der Kasten "FIRMEN-RECHERCHE" zeigt zuerst ein leeres, sechszeiliges
    Eingabefeld. Die gespeicherten Recherchen stehen im Kasten darunter
    und sind erst nach Scrollen sichtbar. Der Nutzer haelt die Recherche
    fuer nicht gespeichert und legt sie im Zweifel erneut an.

Dazu ein zweiter Befund: der Knopf "Mit Claude aktualisieren" kopierte

    /firmen_recherche firma="..."

**ohne `bewerbung_id`** — und `firmen_recherche` speichert seit #674 nur
dann, wenn sie gesetzt ist. Der kopierte Prompt war also ein reiner
Lesevorgang: es kam nichts in PBP an, obwohl das Label "aktualisieren"
versprach. **Ein Knopf, der etwas anderes tut als sein Label sagt, ist
teurer als ein fehlender Knopf** — man verlaesst sich darauf.

Reine Frontend-Aenderung; der Speicherpfad bleibt unveraendert. Die
Zusammenfuehrung der beiden Speicher (#956) und die Notiz-Doppelpflege
(#957) sind ausdruecklich NICHT Teil davon.
"""
import re
import sys
from pathlib import Path


def _repo() -> Path:
    """Absoluter Repo-Pfad — der Test muss auch aus einem fremden
    Arbeitsverzeichnis laufen (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

QUELLE = (_repo() / "frontend" / "src" / "pages"
          / "ApplicationsPage.jsx").read_text(encoding="utf-8")


def ohne_kommentare(text: str) -> str:
    """JSX- und Zeilenkommentare heraus.

    Ohne das prueft der Guard die Erklaerung mit, warum eine
    Schreibweise falsch ist — und schlaegt an ihr an. Dieselbe Lehre wie
    bei #993 und #998; sie kostet sonst jedes Mal einen Durchlauf.
    """
    ohne_block = re.sub(r"\{/\*.*?\*/\}", "", text, flags=re.S)
    return "\n".join(z for z in ohne_block.split("\n")
                     if not z.strip().startswith("//"))


CODE = ohne_kommentare(QUELLE)


# ── AK 1: Gespeicherte Recherchen ohne Scrollen sichtbar ──────────────

def test_958_recherchen_stehen_vor_dem_eingabefeld():
    """Der Normalfall ist Lesen, nicht Schreiben.

    Gemessen wird die Reihenfolge im Quelltext — sie bestimmt die
    Reihenfolge auf dem Bildschirm. Ein Test auf "irgendwo vorhanden"
    haette den gemeldeten Fehler nicht gefunden: beide Kaesten gab es
    ja, nur in der falschen Ordnung.
    """
    pos_recherchen = CODE.index("Recherchen\n")
    pos_eingabe = CODE.index("Firmen-Recherche</p>")
    assert pos_recherchen < pos_eingabe, (
        "Der Kasten mit den gespeicherten Recherchen muss VOR dem "
        "Eingabefeld stehen — sonst haelt der Nutzer sie fuer nicht "
        "gespeichert und legt sie erneut an.")


# ── AK 2: Eingabefeld zugeklappt ──────────────────────────────────────

def test_958_das_eingabefeld_ist_zugeklappt():
    """Ein leeres sechszeiliges Feld ganz oben suggeriert, dass hier
    etwas fehlt. Zugeklappt ist der Standardzustand."""
    abschnitt = CODE[CODE.index("Firmen-Recherche</p>"):]
    abschnitt = abschnitt[:abschnitt.index("</Card>")]
    assert "<details" in abschnitt
    assert "Eigene Notiz hinzufuegen" in abschnitt
    # `open` waere aufgeklappt — genau der alte Zustand.
    assert not re.search(r"<details[^>]*\bopen\b", abschnitt)


def test_958_der_kopier_knopf_liegt_nicht_im_aufklapper():
    """Sonst loest jeder Klick auf ihn zusaetzlich das Aufklappen aus —
    eine Nebenwirkung, die niemand gemeint hat."""
    abschnitt = CODE[CODE.index("Firmen-Recherche</p>"):]
    summary_start = abschnitt.index("<summary")
    summary_ende = abschnitt.index("</summary>")
    assert "Prompt kopieren" not in abschnitt[summary_start:summary_ende]


# ── AK 3: der kopierte Prompt enthaelt die bewerbung_id ───────────────

def test_958_der_prompt_traegt_die_bewerbung_id():
    """Der Kern des zweiten Befunds. Ohne sie speichert
    `firmen_recherche` nicht (#674) — der Prompt war ein reiner
    Lesevorgang."""
    assert 'bewerbung_id="${bid}"' in CODE
    stelle = CODE[CODE.index("/firmen_recherche"):][:400]
    assert "bewerbung_id" in stelle


def test_958_die_bewerbung_id_ist_ein_echter_parametername():
    """Guard gegen einen Tippfehler, den niemand bemerken wuerde: ein
    falscher Parametername faellt erst auf, wenn wieder nichts
    ankommt."""
    import inspect
    from bewerbungs_assistent.tools import analyse as analyse_tools

    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

    import logging

    class _DB:
        def __getattr__(self, name):
            return lambda *a, **kw: None

    analyse_tools.register(_Sammler(), _DB(), logging.getLogger("test"))
    parameter = set(inspect.signature(
        gesammelt["firmen_recherche"]).parameters)
    assert {"firma", "bewerbung_id"} <= parameter


def test_958_das_label_verspricht_nichts_falsches():
    """Vorher stand "Mit Claude aktualisieren" an einem Knopf, der einen
    Textbaustein in die Zwischenablage legt. Er fuehrt nichts aus."""
    assert "Prompt kopieren" in CODE
    assert "Mit Claude aktualisieren" not in CODE


# ── AK 4: der Speicherpfad bleibt unveraendert ────────────────────────

def test_958_speicherpfad_unveraendert():
    """Ausdrueckliche Abgrenzung des Issues: nur Reihenfolge,
    Sichtbarkeit und der kopierte Prompt aendern sich. Die
    Zusammenfuehrung der beiden Speicher ist #956."""
    assert "/research-notes" in CODE
    assert "research_notes: researchDraft" in CODE
