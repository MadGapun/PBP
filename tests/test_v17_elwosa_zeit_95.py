"""beta.95: Elwosa nennt die ECHTE Uhrzeit statt fester Zeiten im Linientext.

Bug aus dem User-Test: um 04:30 sagte Elwosa "Halb zwei. Was machst du noch
hier." — die Uhrzeit stand fest in der Linie und war damit falsch. Fix:
Platzhalter {zeit} setzt die aktuelle LOKALE Uhrzeit ein, die hartkodierten
Zeit-Linien wurden umgestellt.
"""
from __future__ import annotations

from datetime import datetime

from bewerbungs_assistent.services.elwosa import format_uhrzeit, fill_template
from bewerbungs_assistent.services.elwosa_lines import WORLD_LINES, EASTER_EGGS


def test_format_uhrzeit_natuerlich():
    assert format_uhrzeit(datetime(2026, 6, 3, 4, 30)) == "Halb fuenf"
    assert format_uhrzeit(datetime(2026, 6, 3, 16, 0)) == "Vier Uhr"
    assert format_uhrzeit(datetime(2026, 6, 3, 15, 15)) == "Viertel nach drei"
    assert format_uhrzeit(datetime(2026, 6, 3, 17, 45)) == "Viertel vor sechs"
    assert format_uhrzeit(datetime(2026, 6, 3, 4, 32)) == "4:32 Uhr"
    assert format_uhrzeit(datetime(2026, 6, 3, 0, 30)) == "Halb eins"
    assert format_uhrzeit(datetime(2026, 6, 3, 23, 30)) == "Halb zwoelf"


def test_fill_template_setzt_zeit_ein():
    out = fill_template("{zeit}. Was machst du noch hier.", {})
    assert "{zeit}" not in out
    assert out.endswith("Was machst du noch hier.")
    # Uhrzeit am Satzanfang: entweder Wort (Halb/Vier/...) oder Ziffer (4:32)
    assert out[0].isupper() or out[0].isdigit()


def test_fill_template_ohne_platzhalter_unveraendert():
    line = "Spaete Stunde. Ich bleib wach. Du musst nicht."
    assert fill_template(line, {}) == line


def test_world_lines_keine_falsche_fixzeit():
    """Regression: keine Welt-Linie nennt mehr eine feste falsche Uhrzeit."""
    verboten = ["Halb zwei", "Drei Uhr morgens", "Achtzehn Uhr", "Sechzehn Uhr",
                "Eins durch, zwei naht"]
    alle = [ln for pool in WORLD_LINES.values() for ln in pool]
    alle += list(EASTER_EGGS.values())
    for ln in alle:
        for bad in verboten:
            assert bad not in ln, f"Feste Uhrzeit in Linie: {ln!r}"


def test_late_night_zeit_platzhalter_rendert():
    """Die late_night-Linien mit {zeit} rendern zu echter Uhrzeit."""
    for ln in WORLD_LINES["late_night"]:
        rendered = fill_template(ln, {})
        assert "{zeit}" not in rendered
