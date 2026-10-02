"""#1150 — Die Dokumente im Repo widersprachen dem Programm.

Durchsicht vom 01.10.2026 (Prüfbereich GitHub und Dokumentation), jeweils gegen
den Code gelesen:

1. `SECURITY.md` sagte „Keine Cloud, kein Account, kein externer Server“ und
   „PBP selbst sendet keine Daten an externe Server“ — der Code fragt
   Nominatim, GitHub und elwosa.de ab, und alles, was Claude bearbeitet, geht
   an Anthropic. Dazu nannte die Datei nur „1.0.x“ als unterstützt.
4. `CONTRIBUTING.md` schickte Mitwirkende auf den Zweig `develop`, den es nicht
   gibt.
6. Die Fehlervorlage verlangte Log-Auszüge ohne Datenschutz-Hinweis; die
   Vorlage ist die Eingangstür für öffentliche Issues.
7. Die Terminal-Anleitung (Linux) klonte `main` und installierte damit die Beta.

(Punkte 2, 3 und 5 stehen im Wiki und werden dort geändert.)
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _lies(*teile) -> str:
    return ROOT.joinpath(*teile).read_text(encoding="utf-8-sig")


# ══ SECURITY.md gegen die Datenfluss-Kurzfassung ══════════════════════════

def test_1150_security_md_traegt_die_kurzfassung_der_datenfluesse():
    """Eine Quelle der Wahrheit: `services/datenschutz.py`. README, FAQ und der
    einmalige Hinweis tragen den Satz seit v1.7.135, diese Datei nicht."""
    from bewerbungs_assistent.services.datenschutz import KURZ
    assert KURZ in _lies("SECURITY.md")


def test_1150_security_md_nennt_jede_externe_anfrage_des_programms():
    from bewerbungs_assistent.services.datenschutz import DATENFLUSS
    text = _lies("SECURITY.md")
    fehlt = []
    for eintrag in DATENFLUSS["external_requests"]:
        name = re.split(r"\s*\(", eintrag, maxsplit=1)[0].strip()
        if name not in text:
            fehlt.append(name)
    assert not fehlt, f"SECURITY.md nennt diese Anfragen nicht: {fehlt}"


@pytest.mark.parametrize("falsch", [
    "Keine Cloud, kein Account, kein externer Server",
    "PBP selbst sendet keine Daten an externe Server",
    "werden keine Logins oder persönliche Daten übertragen",
    "läuft vollständig auf deinem Rechner",
])
def test_1150_security_md_enthaelt_die_alten_falschaussagen_nicht(falsch):
    assert falsch not in _lies("SECURITY.md")


def test_1150_security_md_nennt_die_gepflegten_versionen():
    text = _lies("SECURITY.md")
    assert "1.7.x" in text
    assert "1.0.x" not in text
    assert "1.8.0-beta" in text


# ══ CONTRIBUTING.md ═══════════════════════════════════════════════════

def test_1150_contributing_schickt_niemanden_auf_einen_zweig_der_nicht_existiert():
    """Es gibt keinen Zweig `develop`; `main` ist die Beta, Stable entsteht auf
    `hotfix/v1.7.N`."""
    text = _lies("CONTRIBUTING.md")
    assert "develop" not in text
    assert "hotfix/v1.7" in text
    assert "gegen `main`" in text


def test_1150_contributing_warnt_vor_namen_in_issues():
    text = _lies("CONTRIBUTING.md")
    assert "Issues sind öffentlich" in text
    assert "<FIRMA>" in text


def test_1150_contributing_nennt_keine_veralteten_anzahlen():
    """„72 Tools in 8 Modulen“ und „18 Jobportal-Scraper“ stimmten schon lange nicht."""
    text = _lies("CONTRIBUTING.md")
    assert "72 Tools" not in text
    assert "18 Jobportal" not in text


# ══ Fehlervorlage ═════════════════════════════════════════════════════

def test_1150_die_fehlervorlage_warnt_vor_namen_in_logs_und_screenshots():
    import yaml
    vorlage = yaml.safe_load(_lies(".github", "ISSUE_TEMPLATE", "bug_report.yml"))
    felder = {k.get("id"): k for k in vorlage["body"] if k.get("id")}
    for feld in ("logs", "error_message"):
        beschreibung = felder[feld]["attributes"]["description"]
        assert "öffentlich" in beschreibung or "schwärzen" in beschreibung, feld
    # Das Feld wirbt nicht mehr mit "sehr hilfreich", ohne die Gefahr zu nennen.
    assert "sehr hilfreich!" not in felder["logs"]["attributes"]["label"]
    einleitung = vorlage["body"][0]["attributes"]["value"]
    assert "<FIRMA>" in einleitung and "Löschen" in einleitung


# ══ Linux-Anleitung: die stabile Version, nicht die Beta ═════════════════

def test_1150_die_linux_anleitung_der_vorlagen_klont_einen_tag():
    for rel in (("docs", "RELEASE_INSTALL_TEMPLATE.md"),
                ("docs", "internal", "RELEASE_INSTALL_TEMPLATE.md")):
        text = _lies(*rel)
        assert "git clone --branch vX.Y.Z --depth 1" in text, rel
        assert "git clone https://github.com/MadGapun/PBP.git\ncd PBP\nbash" not in text, rel


def test_1150_die_claude_md_vorlage_fuer_die_release_notizen_klont_einen_tag():
    """Die Vorlage in CLAUDE.md erzeugt die Release-Notizen jedes Stable-Releases."""
    text = _lies("CLAUDE.md")
    assert "git clone --branch vX.Y.Z --depth 1" in text


def test_1150_die_readme_linux_anleitung_klont_einen_tag():
    text = _lies("README.md")
    zeilen = [z for z in text.splitlines() if z.startswith("git clone")]
    assert zeilen, "keine Linux-Anleitung in der README"
    for z in zeilen:
        assert "--branch v" in z, f"klont die Beta statt der stabilen Version: {z}"


def test_1150_die_changelog_anleitung_des_neuesten_eintrags_klont_einen_tag():
    text = _lies("CHANGELOG.md")
    kopf = text.index("## [")
    naechster = text.index("\n## [", kopf + 5)
    eintrag = text[kopf:naechster]
    if "git clone" in eintrag:
        assert "git clone --branch v" in eintrag
