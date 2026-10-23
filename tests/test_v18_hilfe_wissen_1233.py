"""#1233 (F51) - die Wissensbasis der interaktiven Hilfe: gebaut aus den Quellen, geprueft gegen sie.

Die Hilfe antwortet nur aus eigenen Texten. `scripts/hilfe_wissen_bauen.py` schneidet sie beim Release in Abschnitte
(`content/hilfe_wissen.json`). Diese Tests halten fest, dass die Datei

* gueltig und vollstaendig ist (Kennungen, Felder, Laengen),
* nur Ziele nennt, die es in der App gibt (Seiten und Reiter aus den gepruefen Listen des Frontends, Prompts aus dem Katalog),
* nicht hinter ihren Quellen im Repository zurueckbleibt (Hilfe, Reiter, Seiten, Prompt-Katalog; das Wiki liegt in einem eigenen
  Repository und wird von `release_check.py` gegen den Clone geprueft),
* keine Personendaten traegt.

Pfade relativ zu dieser Datei (DoD 8c): gruen auch aus einem fremden Arbeitsverzeichnis.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
DATEI = WURZEL / "src" / "bewerbungs_assistent" / "content" / "hilfe_wissen.json"
sys.path.insert(0, str(WURZEL / "src"))


def _modul(name: str, pfad: Path):
    spec = importlib.util.spec_from_file_location(name, pfad)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def bauer():
    return _modul("hilfe_wissen_bauen_test", WURZEL / "scripts" / "hilfe_wissen_bauen.py")


@pytest.fixture(scope="module")
def daten():
    return json.loads(DATEI.read_text(encoding="utf-8"))


# ── die Datei selbst ────────────────────────────────────────────────────────────────────────

def test_die_datei_ist_da_und_gueltig(daten):
    assert DATEI.is_file()
    assert daten["format"] == 1
    assert daten["fassung"]
    assert set(daten) >= {"format", "fassung", "quellen", "seiten", "reiter", "abschnitte", "gebaut"}
    assert len(daten["abschnitte"]) >= 400, "die Hilfe ist leer gelaufen"


def test_sie_ist_klein_genug_fuer_die_installation(daten):
    """Nutzerentscheidung 16.10.2026: der Wiki-Auszug wird mitgeliefert. Eine Obergrenze haelt ihn so."""
    assert DATEI.stat().st_size < 700 * 1024, f"{DATEI.stat().st_size // 1024} KB"


def test_kennungen_sind_eindeutig_und_die_felder_vollstaendig(daten):
    ids = [a["id"] for a in daten["abschnitte"]]
    assert len(ids) == len(set(ids))
    for a in daten["abschnitte"]:
        assert set(a) == {"id", "quelle", "titel", "pfad", "text", "ziel", "wiki", "prompt"}, a["id"]
        assert a["quelle"] in {"hilfe", "faq", "probleme", "prompt", "wiki"}, a["id"]
        assert a["id"].split(":", 1)[0] in {"hilfe", "faq", "problem", "prompt", "wiki"}
        assert a["titel"].strip() and a["pfad"].strip()
        assert 40 <= len(a["text"]) <= 3000, (a["id"], len(a["text"]))


def test_alle_quellenarten_sind_vertreten(daten):
    arten = {a["quelle"] for a in daten["abschnitte"]}
    assert arten == {"hilfe", "faq", "probleme", "prompt", "wiki"}


def test_kein_abschnitt_enthaelt_markdown_oder_html_reste(daten):
    for a in daten["abschnitte"]:
        t = a["text"]
        assert "```" not in t and "<script" not in t.lower() and "](" not in t, a["id"]
        assert "&lt;" not in t and "&gt;" not in t and "&amp;" not in t, a["id"]


def test_keine_versionsgeschichte_im_text(daten):
    """Die Hilfe antwortet fuer HEUTE: 'ab v1.7.35 (#985)' hilft niemandem beim Suchen und verfaelscht die Treffer."""
    import re
    for a in daten["abschnitte"]:
        assert not re.search(r"\(#\d{3,4}\)", a["text"]), a["id"]


# ── die Ziele ───────────────────────────────────────────────────────────────────────────────

def test_ziele_stammen_aus_den_gepruefen_listen(daten, bauer):
    q = bauer.hilfe_quellen()
    seiten = set(q["PAGE_IDS"])
    reiter = {r["id"] for r in q["SETTINGS_REITER"]}
    assert set(daten["seiten"]) == seiten
    assert set(daten["reiter"]) == reiter
    for a in daten["abschnitte"]:
        z = a["ziel"]
        if not z:
            continue
        assert z["art"] in {"seite", "einstellung"}, a["id"]
        assert z["id"] in (seiten if z["art"] == "seite" else reiter), (a["id"], z)


def test_reiterbezeichnungen_sind_die_des_dashboards(daten):
    from bewerbungs_assistent.services.menue import EINSTELLUNGEN_REITER
    namen = set(EINSTELLUNGEN_REITER.values())
    for kennung, r in daten["reiter"].items():
        assert r["label"] in namen, (kennung, r["label"])


def test_prompts_gibt_es_im_katalog(daten):
    from bewerbungs_assistent.services import prompt_katalog
    ids = {e["id"] for e in prompt_katalog.EINTRAEGE}
    for a in daten["abschnitte"]:
        if a["prompt"]:
            assert a["prompt"] in ids, (a["id"], a["prompt"])
    assert {a["prompt"] for a in daten["abschnitte"] if a["prompt"]}, "kein einziger Abschnitt verweist auf einen Prompt"


def test_wiki_ziele_nennen_eine_seite_und_einen_anker(daten, bauer):
    for a in daten["abschnitte"]:
        w = a["wiki"]
        if a["quelle"] == "wiki":
            assert w and w["seite"] in bauer.WIKI_SEITEN, a["id"]
        if w:
            assert set(w) == {"seite", "anker"}
            assert "/" not in w["seite"] and " " not in w["seite"]


def test_wiki_seiten_sind_entschieden_nicht_vergessen(bauer):
    """Eine neue Seite im Wiki zwingt zu einer Entscheidung: Wissen fuer Anwender (WIKI_SEITEN) oder Pflegeseite (AUSGESCHLOSSEN).
    Ohne Wiki-Clone (CI) wird nichts geprueft; `release_check.py` ruft den Bau gegen den Clone."""
    wiki = bauer.wiki_ordner(None)
    if wiki is None:
        pytest.skip("kein Wiki-Clone (PBP_WIKI_DIR oder ../PBP.wiki)")
    namen = {p.stem for p in wiki.glob("*.md")}
    bekannt = set(bauer.WIKI_SEITEN) | set(bauer.WIKI_AUSGESCHLOSSEN)
    offen = {n for n in namen - bekannt if not n.startswith(bauer.WIKI_AUSGESCHLOSSEN_PRAEFIX)}
    assert not offen, f"Seiten ohne Entscheidung: {sorted(offen)}"


# ── nicht hinter den Quellen zurueck ────────────────────────────────────────────────────────

@pytest.mark.skipif(shutil.which("node") is None, reason="node fehlt: die Hilfe wird aus lib/hilfe.js gelesen")
def test_aktuell_gegenueber_den_quellen_im_repository(daten, bauer):
    """Hilfe, Reiter, Seiten und Prompt-Katalog (alles im Repository): die Datei entspricht ihnen. Wer hilfe.js, einen Reiter oder einen
    Prompt aendert, baut die Wissensbasis neu (`python scripts/hilfe_wissen_bauen.py`)."""
    q = bauer.hilfe_quellen()
    katalog = bauer.prompt_katalog()
    gebaut = bauer.abschnitte_aus_hilfe(q, katalog) + bauer.abschnitte_aus_prompts(katalog)
    vorhanden = [a for a in daten["abschnitte"] if a["quelle"] != "wiki"]
    assert vorhanden == gebaut, "Die Wissensbasis ist veraltet: python scripts/hilfe_wissen_bauen.py"
    assert daten["quellen"]["hilfe"] == bauer._hash({k: q[k] for k in ("HILFE", "FAQ", "PROBLEME", "MELDEWEGE", "MELDE_PROMPT")})
    assert daten["quellen"]["reiter"] == bauer._hash(q["SETTINGS_REITER"])
    assert daten["quellen"]["seiten"] == bauer._hash(q["PAGE_IDS"])


def test_der_bau_ist_in_release_check_eingehaengt():
    """DoD 8c: ein Schutz zaehlt erst, wenn er aufgerufen wird."""
    text = (WURZEL / "release_check.py").read_text(encoding="utf-8")
    assert "hilfe_wissen_bauen" in text and "--pruefen" in text


def test_die_datei_gehoert_zum_paket_und_zum_update_archiv():
    """Sie liegt im Paketordner (hatch nimmt `packages = [src/bewerbungs_assistent]` komplett mit) und ist im Auto-Update-Archiv."""
    text = (WURZEL / "pyproject.toml").read_text(encoding="utf-8")
    assert 'packages = ["src/bewerbungs_assistent"]' in text
    bau = _modul("build_update_archive_hilfe_test", WURZEL / "scripts" / "build_update_archive.py")
    dateien = bau.dateien_aus_ordner(WURZEL)
    assert "src/bewerbungs_assistent/content/hilfe_wissen.json" in dateien


# ── Datenschutz ─────────────────────────────────────────────────────────────────────────────

def test_keine_personendaten_im_json(daten, bauer):
    """Die Datei geht an jeden Anwender und steht im Repository. Geprueft werden Titel, Pfad und Text (nicht die Pruefsummen: eine Folge
    von elf Ziffern in einem Hexwert ist keine Telefonnummer)."""
    funde = bauer.personendaten(daten["abschnitte"])
    assert not funde, funde[:5]


def test_der_bau_bricht_bei_personendaten_ab(bauer):
    """Gegenprobe: der Pruefer sieht etwas (DoD 8c). Die Beispiele werden erst hier zusammengesetzt: der Quelltext selbst traegt keine Personendaten."""
    telefon = "0171 " + "1234567"
    mail = "max.mustermann" + "@" + "gmx.de"
    fund_telefon = bauer.personendaten([{"id": "wiki:X:y", "titel": "Hallo", "pfad": "Wiki", "text": f"Rufe {telefon} an."}])
    fund_mail = bauer.personendaten([{"id": "wiki:X:z", "titel": "Hallo", "pfad": "Wiki", "text": f"Schreib an {mail}."}])
    assert fund_telefon and fund_mail, (fund_telefon, fund_mail)
    assert not bauer.personendaten([{"id": "wiki:X:ok", "titel": "Hallo", "pfad": "Wiki", "text": "Schreib an test@example.com oder rufe niemanden an."}])


def test_ueberschriften_verlieren_die_version_nicht_den_titel(bauer):
    assert bauer.titel_ohne_historie("Seit v1.7.124: benannte Stufen statt einer Zahl") == "Benannte Stufen statt einer Zahl"
    assert bauer.titel_ohne_historie("Was v1.7.35 umgeräumt hat") == "Was umgeräumt hat"
    assert bauer.titel_ohne_historie("Remote bei JobSpy-Treffern (v1.7.126, #1072)") == "Remote bei JobSpy-Treffern"
    assert bauer.titel_ohne_historie("Updates") == "Updates"
    assert bauer.titel_ohne_historie("v1.7.5") == ""


def test_eine_raute_im_codeblock_ist_keine_ueberschrift(bauer):
    md = "# Seite\n\nText davor.\n\n```bash\n# Repository klonen\ngit clone x\n# Installer starten\nbash install.sh\n```\n\nText danach.\n"
    teile = bauer._teile_wiki_seite("Seite", md)
    assert [t[0] for t in teile] == ["Seite"], "ein Kommentar im Befehl wurde zur Ueberschrift"
    assert "Installer starten" in teile[0][2] and "Text danach." in teile[0][2]
