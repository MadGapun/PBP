"""Tests fuer v1.7.35 — die gebauten Assets muessen zur index.html passen.

Beim Port des Dashboard-Pakets (#985) auf die Stable-Linie kollidierten
die gebauten Assets. Aufgeloest wurde in zwei Richtungen: die
`index.html` uebernahm die Fassung von main (und damit deren
CSS-Hash), der Assets-Ordner behielt die Fassung von Stable. Ergebnis
auf dem Release-Branch:

    index.html  ->  assets/index-DIL__zCO.css
    auf Platte  ->  assets/index-fTRmDITX.css

Das Stylesheet lief in einen 404. **Die Seite lud trotzdem** — React
rendert, alle Texte stehen da, kein Fehler in der Konsole des Servers.
Nur eben ganz ohne Gestaltung, mit einem 1024 px breiten Logo. Gefunden
hat es allein `test_dashboard_mobile_layout_has_no_horizontal_overflow`,
und der brauchte dafuer Playwright, einen laufenden Server und ein
Mobil-Viewport — ein sehr weiter Weg fuer eine Frage, die man am
Dateinamen beantworten kann.

Deshalb hier direkt: verweist die index.html auf Dateien, die es gibt,
und liegt umgekehrt kein Rest aus einem frueheren Build herum? Der
zweite Teil ist kein Schoenheitsfehler — eine verwaiste Datei ist genau
das Zeichen dafuer, dass ein Build oder eine Konfliktaufloesung nur zur
Haelfte durchgelaufen ist.

MERKE (Cherry-Pick-Lehre, dritte Runde): gebaute Assets sind keine
Quelldateien. Bei einem Konflikt wird nicht ausgewaehlt, sondern NEU
GEBAUT — und danach geprueft, dass die Referenzen wieder zusammenpassen.
"""
import re
from pathlib import Path


def _repo() -> Path:
    """Repo-Wurzel ueber die Testdatei, nicht ueber das Arbeitsverzeichnis.

    DoD 8c: ein Test, der relative Pfade nutzt, besteht nur an einer
    Stelle.
    """
    return Path(__file__).resolve().parents[1]


STATIC = _repo() / "src" / "bewerbungs_assistent" / "static" / "dashboard"
INDEX = STATIC / "index.html"
ASSETS = STATIC / "assets"

# src="/static/dashboard/assets/..." und href="..." gleichermassen.
REFERENZ = re.compile(r"""["'](?:/static/dashboard/)?assets/([^"']+)["']""")


def _referenzierte_dateien() -> set[str]:
    return set(REFERENZ.findall(INDEX.read_text(encoding="utf-8")))


def test_index_html_existiert():
    assert INDEX.is_file(), f"Kein gebautes Frontend unter {INDEX}"


def test_index_html_verweist_auf_vorhandene_assets():
    """Jede referenzierte Datei liegt auch im Ordner."""
    fehlend = sorted(n for n in _referenzierte_dateien() if not (ASSETS / n).is_file())
    assert not fehlend, (
        "index.html verweist auf Assets, die es nicht gibt: "
        + ", ".join(fehlend)
        + " — Frontend neu bauen (`cd frontend && pnpm exec vite build`) "
        "und die alten Hash-Dateien mit `git rm` entfernen."
    )


def test_keine_verwaisten_assets():
    """Kein Rest aus einem frueheren Build im Ordner.

    Verwaiste Dateien blaehen nicht nur das Paket auf — sie sind das
    Symptom einer halb durchgelaufenen Aufloesung, und das naechste Mal
    ist es die referenzierte Datei, die fehlt.
    """
    referenziert = _referenzierte_dateien()
    verwaist = sorted(
        p.name
        for p in ASSETS.iterdir()
        if p.is_file() and p.suffix in {".js", ".css"} and p.name not in referenziert
    )
    assert not verwaist, (
        "Assets ohne Referenz in der index.html: "
        + ", ".join(verwaist)
        + " — Reste eines frueheren Builds, mit `git rm` entfernen."
    )


def test_es_gibt_genau_ein_stylesheet():
    """Ein fehlendes Stylesheet faellt sonst erst im Browser auf.

    Der Fall vom 07.09.2026 war NICHT 'kein Stylesheet referenziert',
    sondern 'ein Stylesheet referenziert, das es nicht gibt'. Diese
    Pruefung deckt die andere Haelfte ab: ein Build, der gar kein CSS
    einhaengt.
    """
    css = [n for n in _referenzierte_dateien() if n.endswith(".css")]
    assert len(css) == 1, f"Erwartet genau ein Stylesheet, gefunden: {css}"
