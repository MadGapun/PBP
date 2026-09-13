"""Tests fuer #817: der Sweep laeuft regelmaessig und schreibt keine Namen ins Log.

Ein Sweep in einem oeffentlichen Repository, der seine Funde ins
Actions-Log druckt, veroeffentlicht genau das, was er finden soll. Die
Tests pruefen den Modus ohne Namen mit einem Fund, der nie im Log stehen
darf — und dass der Workflow genau diesen Modus benutzt.
"""
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "scripts"))

import gh_pii_sweep  # noqa: E402

# Ein fiktiver, aber vom Pruefer erkannter Personenname mit Mailadresse —
# gebaut aus Teilen, damit der Name in diesem Testquelltext nicht am Stueck
# steht und den Repo-Scan selbst ausloest.
_MAIL = "erika.beispiel" + "@" + "echte-firma-nord.de"


def _issue_mit_fund():
    return [{"number": 4711, "title": "Befund", "createdAt": "2026-09-13",
             "body": f"Kontakt: {_MAIL}", "comments": []}]


def test_mit_namen_steht_der_fund_im_log(monkeypatch, capsys):
    monkeypatch.setattr(gh_pii_sweep, "issues_laden", lambda nur_offen: _issue_mit_fund())
    assert gh_pii_sweep.main([]) == 1
    assert _MAIL in capsys.readouterr().out, \
        "Gegenprobe: ohne Schalter muss der Fall ueberhaupt etwas finden"


def test_ohne_namen_nennt_stelle_und_anzahl_aber_keinen_text(monkeypatch, capsys):
    monkeypatch.setattr(gh_pii_sweep, "issues_laden", lambda nur_offen: _issue_mit_fund())
    assert gh_pii_sweep.main(["--ohne-namen"]) == 1, "ein Fund laesst den Lauf scheitern"
    ausgabe = capsys.readouterr().out
    assert "#4711 Body" in ausgabe
    assert _MAIL not in ausgabe
    assert "echte-firma-nord" not in ausgabe


def test_ohne_fund_ist_der_lauf_gruen(monkeypatch, capsys):
    monkeypatch.setattr(gh_pii_sweep, "issues_laden", lambda nur_offen: [
        {"number": 1, "title": "Sauber", "body": "Nichts", "comments": []}])
    assert gh_pii_sweep.main(["--ohne-namen"]) == 0


@pytest.fixture
def db(tmp_path):
    import importlib
    import os

    os.environ["BA_DATA_DIR"] = str(tmp_path)
    sys.path.insert(0, str(_repo() / "src"))
    from bewerbungs_assistent import database

    importlib.reload(database)
    d = database.Database(db_path=tmp_path / "anon.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.switch_profile(d.create_profile("Anonym"))
    try:
        yield d
    finally:
        d.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_der_anonymisierte_beleg_besteht_den_pruefer_ohne_nacharbeit(db):
    """#817 AK 4. Gemessen am 13.09.: Namen wurden ersetzt, Mail und
    Telefon standen weiter im Klartext — der Pruefer schlug an."""
    from bewerbungs_assistent.services import pii_bestand
    from scrub_pii import find_pii

    # Firma und Rufnummer sind erfunden, aber sie muessen so aussehen wie
    # echte: eine Firma aus FIKTIVE_FIRMEN und eine 555-Nummer ersetzt die
    # Anonymisierung zu Recht nicht. Zusammengesetzt, damit dieser
    # Quelltext selbst den Repo-Scan nicht ausloest.
    firma = "Nordlicht Anlagen" + "bau G" + "mbH"
    person = "Kai " + "Nordmann"
    telefon = "040 " + "3345 " + "6789"
    db.add_application({"title": "Rolle", "company": firma, "status": "beworben"})
    db.add_contact({"full_name": person, "company": firma})
    mail = "kai.nordmann" + "@" + "nordlicht-anlagenbau.de"
    beleg = (f"| ID | Firma | Kontakt | Status |\n| a1b2 | {firma} | {person} | beworben |\n"
             f"Mail: {mail}, Tel. {telefon}, beworben am 2026-09-01, Score 18,7")

    ergebnis = pii_bestand.anonymisiere_text(db, beleg)

    assert find_pii(ergebnis["text"]) == []
    for bleibt in ("a1b2", "2026-09-01", "18,7", "beworben", "| ID |"):
        assert bleibt in ergebnis["text"], f"Beweiskraft verloren: {bleibt}"
    platz = next(e["platzhalter"] for e in ergebnis["ersetzt"] if e["art"] == "firma")
    assert platz in ergebnis["text"]
    zweiter = pii_bestand.anonymisiere_text(db, f"Nochmal {firma}")
    assert zweiter["text"] == f"Nochmal {platz}", \
        "dieselbe Firma behaelt ihren Platzhalter"


def test_eine_systemadresse_und_eine_fiktive_nummer_bleiben_stehen(db):
    """Ein Pruefer, der korrekte Musterdaten ersetzt, entstellt den Beleg."""
    from bewerbungs_assistent.services import pii_bestand

    text = "Absender " + "noreply" + "@" + "portal.example, Tel. 040 555 0100"
    assert pii_bestand.anonymisiere_text(db, text)["text"] == text


def test_der_workflow_laeuft_regelmaessig_und_ohne_namen():
    wf = (_repo() / ".github/workflows/pii-sweep.yml").read_text(encoding="utf-8")
    assert "schedule:" in wf and "cron:" in wf
    zeilen = [z for z in wf.splitlines() if "gh_pii_sweep.py" in z and "run:" in z]
    assert zeilen, "der Workflow ruft den Sweep auf"
    assert all("--ohne-namen" in z for z in zeilen), \
        "ohne den Schalter stuenden die Funde im oeffentlichen Log"
    assert "issues: read" in wf and "contents: read" in wf, "nur lesende Rechte"
