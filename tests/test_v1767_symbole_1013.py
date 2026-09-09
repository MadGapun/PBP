"""Tests fuer v1.7.67 — #1013: Symbole statt Textzeilen in der Kopfzeile.

Rueckmeldung eines Testers vom 09.09.2026, nach Ansicht der
Dashboard-Screenshots:

    "Ich finde die Idee mit dem Info-Button gut, ich wuerde den nur oben
    in die Ecke machen, ohne Text, also nur Symbol. Auch fuer den
    Settings-Button dann Text rausnehmen — dann werden die gut
    nebeneinander aussehen."

Zwei Bedienelemente derselben Art (Meta-Funktionen der Karte, nicht ihr
Inhalt) standen an zwei verschiedenen Orten und in zwei verschiedenen
Formen: die Erklaerung als volle Zeile UEBER dem Inhalt, die Auswahl als
Knopf mit Text in der Ecke. Sie lasen sich dadurch wie zwei
verschiedene Dinge — und die Erklaerung kostete jeden Tag eine Zeile,
obwohl man sie nur beim ersten Mal braucht.

**Ein Symbol ohne Text braucht einen zugaenglichen Namen.** Ohne
`aria-label` ist der Knopf fuer Tastatur- und Screenreader-Bedienung
namenlos — deshalb prueft das hier jeder Test mit.
"""
import re
import sys
from pathlib import Path


def _repo() -> Path:
    """Absoluter Repo-Pfad — der Test muss auch aus einem fremden
    Arbeitsverzeichnis laufen (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

KARTE = (_repo() / "frontend" / "src" / "components"
         / "SchnellzugriffKarten.jsx")
BEREICH = (_repo() / "frontend" / "src" / "components"
           / "DashboardBereich.jsx")
SEITE = _repo() / "frontend" / "src" / "pages" / "DashboardPage.jsx"


def _quelle(pfad: Path) -> str:
    return pfad.read_text(encoding="utf-8")


def test_1013_die_erklaerung_belegt_keine_eigene_zeile_mehr():
    """AK 1.

    Vorher stand `<summary>Was ist der Schnellzugriff?</summary>` als
    erstes Element IM INHALT der Karte — vor den eigentlichen
    Eintraegen.
    """
    quelle = _quelle(KARTE)
    assert "<summary" not in quelle, \
        "Die Erklaerung steht wieder als eigene Zeile im Inhalt."
    assert "aria-label=\"Was ist der Schnellzugriff?\"" in quelle, \
        "Die Erklaerung ist nicht mehr erreichbar."


def test_1013_erklaerung_und_auswahl_stehen_nebeneinander():
    """AK 2: gleich gross, gleiche Form, ein Ort."""
    quelle = _quelle(KARTE)
    kopf = quelle[quelle.index("Schnellzugriff</h2>"):]
    kopf = kopf[:kopf.index("{hilfeOffen &&")]
    assert kopf.count("h-9 w-9") == 2, \
        "Die beiden Knoepfe sind nicht gleich gross."
    assert "<Info size=" in kopf and "<Settings2 size=" in kopf


def test_1013_jedes_symbol_traegt_einen_zugaenglichen_namen():
    """AK 3 — die Bedingung, ohne die ein Symbolknopf unbedienbar ist.

    Geprueft werden die Knoepfe, die in dieser Welle ihren Text
    verloren haben: sie duerfen nicht namenlos zurueckbleiben.
    """
    for pfad in (KARTE, BEREICH, SEITE):
        quelle = _quelle(pfad)
        for treffer in re.finditer(r"<button\b[^>]*?>", quelle, re.S):
            block = treffer.group(0)
            # Nur die neuen Symbolknoepfe: quadratische Trefferflaeche
            # ohne Beschriftung.
            if not re.search(r"h-\d+ w-\d+", block):
                continue
            assert "aria-label" in block, (
                f"{pfad.name}: Symbolknopf ohne zugaenglichen Namen:\n"
                f"{block[:200]}")


def test_1013_die_trefferflaeche_bleibt_fingergross():
    """AK 4.

    Zwei Knoepfe nebeneinander in einer engen Kopfzeile sind genau der
    Fall, in dem Trefferflaechen zu klein geraten. `h-9` sind 36 px —
    das ist die Untergrenze, unter der ein Ziel auf dem Handy schwer zu
    treffen ist.
    """
    kopf = _quelle(KARTE)
    kopf = kopf[kopf.index("Schnellzugriff</h2>"):]
    kopf = kopf[:kopf.index("{hilfeOffen &&")]
    groessen = set(re.findall(r"h-(\d+) w-\1", kopf))
    assert groessen, "Keine quadratische Trefferflaeche gefunden."
    assert min(int(g) for g in groessen) >= 9, \
        f"Trefferflaeche zu klein: h-{min(groessen)}"


def test_1013_die_erklaerung_bleibt_auffindbar_und_gemerkt():
    """AK 5.

    Die Erklaerung wandert, sie verschwindet nicht — wer sie beim ersten
    Mal braucht, muss sie finden. Und der einmal gewaehlte Zustand
    bleibt erhalten, sonst klappt sie bei jedem Laden wieder auf.
    """
    quelle = _quelle(KARTE)
    assert "Beispiel-Prompts für Claude Desktop" in quelle
    assert "pbp_dashboard_quickhelp_open" in quelle, \
        "Der gemerkte Zustand ist verlorengegangen."
    assert "aria-expanded={hilfeOffen}" in quelle, \
        "Ein aufklappbarer Knopf muss seinen Zustand ansagen."


def test_1013_auch_die_uebrigen_meta_bedienelemente_sind_symbole():
    """Dasselbe Prinzip fuer anpassen und einklappen.

    Ein Ort, eine Form, eine Groesse — sonst bleibt der Bildschirm eine
    Sammlung verstreuter Text-Links.
    """
    assert ">\n            einklappen\n" not in _quelle(BEREICH)
    assert "Dashboard anpassen\n          </button>" not in _quelle(SEITE)
    assert 'aria-label="Dashboard anpassen' in _quelle(SEITE)
    assert "aria-label={`${titel} einklappen`}" in _quelle(BEREICH)
