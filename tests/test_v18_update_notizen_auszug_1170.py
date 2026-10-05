"""#1170 U2 — die Karte „Was ist neu“ zeigt ganze Sätze statt abgeschnittener Absätze.

Befund (04.10.2026, Update-Demo): `auszug_aus_notizen` nahm die ersten drei Zeilen der Release-Notizen vor dem
Installationsblock. Mit den ECHTEN Notizen von v1.7.151 und v1.7.152 kam (1) ein Absatz, bei 240 Zeichen mitten im Wort
abgeschnitten („… nur „aktuell“ ge“), (2) die nackte Zeile „Wichtig zu wissen:“, (3) wieder ein abgeschnittener Absatz.
Das ist der Moment, in dem jemand entscheidet, ob er neu startet.

Die Fixtures unter `tests/fixtures/release_notizen/` sind die veröffentlichten Notizen (ohne personenbezogene Angaben).
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services.auto_update import lauf  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "release_notizen"
ECHTE = ["v1.7.151", "v1.7.152"]


def _lesen(name):
    return (FIXTURES / f"{name}.md").read_text(encoding="utf-8")


def _endet_sauber(zeile: str) -> bool:
    """Endet an einem Satzzeichen, einer Klammer, einem Anführungszeichen — oder mit „…“ nach einem ganzen Wort."""
    return zeile.endswith((".", "!", "?", "…", "“", ")", "”"))


@pytest.mark.parametrize("name", ECHTE)
def test_1170_die_echten_notizen_ergeben_lesbare_eintraege(name):
    auszug = lauf.auszug_aus_notizen(_lesen(name))
    assert len(auszug) == 3
    for zeile in auszug:
        assert len(zeile) <= lauf.MAX_AUSZUG_ZEICHEN, zeile
        assert not zeile.endswith(":"), f"eine Ankündigung ist kein Inhalt: {zeile!r}"
        assert not zeile.startswith("Hotfix für"), f"Entwickler-Einleitung: {zeile!r}"
        assert _endet_sauber(zeile), f"mitten im Wort abgeschnitten: {zeile!r}"
        assert "**" not in zeile and "`" not in zeile and "](" not in zeile, f"Markdown steht noch da: {zeile!r}"


def test_1170_der_befund_von_v1_7_152_ist_behoben():
    auszug = lauf.auszug_aus_notizen(_lesen("v1.7.152"))
    assert auszug[0].startswith("Die Update-Prüfung schaut nur nach Versionen der eigenen Linie")
    assert all("Wichtig zu wissen" not in z for z in auszug), "die Zwischenüberschrift ist kein Eintrag"
    assert not any(z.endswith(" ge") for z in auszug), "kein Abbruch mitten im Wort"


def test_1170_ein_zu_langer_satz_wird_an_einer_satzfuge_gekuerzt():
    satz = ("Erscheint Version 1.8, steht es unter der Versionsnummer in der Seitenleiste, und der Link führt zur Veröffentlichung "
            "mit der Installationsanleitung, die Schritt für Schritt erklärt, wie der Wechsel einmal von Hand geht und warum "
            "danach alles automatisch laufen kann, wenn du es möchtest.")
    assert len(satz) > lauf.MAX_AUSZUG_ZEICHEN
    gekuerzt = lauf._kuerzen(satz)
    assert len(gekuerzt) <= lauf.MAX_AUSZUG_ZEICHEN and gekuerzt.endswith("…")
    assert satz.startswith(gekuerzt[:-1].rstrip()), "nur ein Anfang des Satzes, nichts Neues"
    assert gekuerzt[-2] not in ", ;:", "keine hängende Satzfuge vor den Punkten"
    # ... und der Schnitt liegt an einer Satzfuge des Originals (Komma, Semikolon, Doppelpunkt, Gedankenstrich, Klammer)
    rest = satz[len(gekuerzt) - 1:]
    assert rest[0] in ",;:" or rest[:2] in (" —", " –", " ("), f"mitten im Gedanken abgebrochen: …{rest[:20]!r}"


def test_1170_ohne_satzfuge_wird_am_wort_gekuerzt_nie_mittendrin():
    text = " ".join(["Wortwortwort"] * 40)
    gekuerzt = lauf._kuerzen(text)
    assert gekuerzt.endswith("Wortwortwort…")
    assert len(gekuerzt) <= lauf.MAX_AUSZUG_ZEICHEN


def test_1170_ein_kurzer_text_bleibt_unveraendert():
    assert lauf._kuerzen("Kurz und gut.") == "Kurz und gut."


def test_1170_mehrere_ganze_saetze_passen_zusammen_in_einen_eintrag():
    text = "Erster Satz mit Inhalt. Zweiter Satz mit Inhalt. " + "Dritter " * 40 + "Satz."
    gekuerzt = lauf._kuerzen(text)
    assert gekuerzt == "Erster Satz mit Inhalt. Zweiter Satz mit Inhalt."


def test_1170_kuerzel_beenden_keinen_satz():
    assert lauf._saetze("Das geht z. B. so. Und dann Nr. 5 hier. Ende.") == [
        "Das geht z. B. so.", "Und dann Nr. 5 hier.", "Ende."]


def test_1170_ein_versionspunkt_vor_grossbuchstaben_beendet_einen_satz():
    """„… v1.7.151. Die Update-Prüfung …“ ist ein echtes Satzende."""
    assert lauf._saetze("Alles neu in v1.7.151. Die Prüfung läuft.") == ["Alles neu in v1.7.151.", "Die Prüfung läuft."]


# ── Der Anwender-Block ─────────────────────────────────────────────────────────────────────

NOTIZ_MIT_BLOCK = """\
Hotfix für v1.8.0. Ein langer Absatz für Entwickler mit Nummern (#1234) und Einzelheiten, der hier nicht erscheinen soll.

<!-- anwender -->
- PBP zeigt die neue Version jetzt auch dann an, wenn sie von einer anderen Linie kommt.
- Nichts wird automatisch installiert.
<!-- /anwender -->

### Added

- Technischer Punkt, der nicht erscheinen soll.

---

## 📦 Wie installiere oder aktualisiere ich PBP?

Hier steht die Anleitung.
"""


def test_1170_ein_anwender_block_geht_vor():
    auszug = lauf.auszug_aus_notizen(NOTIZ_MIT_BLOCK)
    assert auszug == ["PBP zeigt die neue Version jetzt auch dann an, wenn sie von einer anderen Linie kommt.",
                      "Nichts wird automatisch installiert."]


def test_1170_der_block_gilt_auch_in_anderer_schreibweise():
    text = "Vorrede ohne Belang.\n<!--ANWENDER-->\nNur dieser Satz zählt hier.\n<!--  /Anwender  -->\n"
    assert lauf.auszug_aus_notizen(text) == ["Nur dieser Satz zählt hier."]


def test_1170_ohne_block_zaehlt_der_text_vor_dem_installationsblock():
    text = "Die erste Zeile erklärt, was neu ist.\n\n---\n\n## 📦 Wie installiere ich?\n\nDiese Zeile darf nie erscheinen."
    assert lauf.auszug_aus_notizen(text) == ["Die erste Zeile erklärt, was neu ist."]


def test_1170_ueberschriften_tabellen_code_und_zitate_zaehlen_nicht():
    text = "# Titel der Version\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```\ncode = 1\n```\n\n> Zitat, das nichts erklärt.\n\n" \
           "Das ist die einzige Zeile, die ein Mensch lesen soll.\n"
    assert lauf.auszug_aus_notizen(text) == ["Das ist die einzige Zeile, die ein Mensch lesen soll."]


def test_1170_ein_unvollstaendiger_block_faellt_auf_den_text_zurueck():
    text = "<!-- anwender -->\nDer Block wird nie geschlossen, also zählt er nicht.\n\nDie zweite Zeile ist normaler Text.\n"
    auszug = lauf.auszug_aus_notizen(text)
    assert "Die zweite Zeile ist normaler Text." in auszug


@pytest.mark.parametrize("leer", [None, "", "   \n\n  ", "# nur eine Überschrift"])
def test_1170_leere_notizen_ergeben_keine_eintraege(leer):
    assert lauf.auszug_aus_notizen(leer) == []


def test_1170_hoechstens_drei_eintraege_und_der_wunsch_wird_beachtet():
    text = "\n".join(f"Eine ausreichend lange Zeile Nummer {i} mit Text." for i in range(1, 8))
    assert len(lauf.auszug_aus_notizen(text)) == 3
    assert len(lauf.auszug_aus_notizen(text, maximal=5)) == 5
    assert len(lauf.auszug_aus_notizen(text, maximal=1)) == 1


# ── Das Release-Tor erinnert an den Block ─────────────────────────────────────────────────

def _release_check():
    spec = importlib.util.spec_from_file_location("release_check_notizen", ROOT / "release_check.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _tor(monkeypatch, tmp_path, changelog: str):
    rc = _release_check()
    meldungen = {"ok": [], "warn": [], "error": []}
    for art in meldungen:
        monkeypatch.setattr(rc, art, lambda msg, art=art: meldungen[art].append(msg))
    monkeypatch.setattr(rc, "PROJECT_DIR", tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    rc.check_changelog_content("9.9.9")
    return meldungen


EINTRAG = "## [9.9.9] - 2026-10-05 — Test\n\n{kopf}### Added\n\n- Ein Punkt.\n\n## [9.9.8] - 2026-10-01\n\n### Added\n\n- Alt.\n"


def test_1170_das_release_tor_mahnt_den_fehlenden_anwender_block_an(monkeypatch, tmp_path):
    meldungen = _tor(monkeypatch, tmp_path, "# Changelog\n\n" + EINTRAG.format(kopf=""))
    assert any("Anwender-Block" in m for m in meldungen["warn"]), meldungen


def test_1170_mit_anwender_block_schweigt_das_release_tor(monkeypatch, tmp_path):
    kopf = "<!-- anwender -->\nPBP kann jetzt etwas Neues, das du sofort merkst.\n<!-- /anwender -->\n\n"
    meldungen = _tor(monkeypatch, tmp_path, "# Changelog\n\n" + EINTRAG.format(kopf=kopf))
    assert not any("Anwender-Block" in m for m in meldungen["warn"]), meldungen
    assert any("Anwender-Block" in m for m in meldungen["ok"]), meldungen


def test_1170_ein_leerer_anwender_block_zaehlt_nicht(monkeypatch, tmp_path):
    kopf = "<!-- anwender -->\n\n<!-- /anwender -->\n\n"
    meldungen = _tor(monkeypatch, tmp_path, "# Changelog\n\n" + EINTRAG.format(kopf=kopf))
    assert any("Anwender-Block" in m for m in meldungen["warn"]), meldungen
