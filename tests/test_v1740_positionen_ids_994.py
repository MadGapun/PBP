"""Tests fuer v1.7.40 — #994: Berufserfahrung war ueber Claude nicht aenderbar.

Gemeldet am 07.09.2026 von einem fremden Anwender (derselbe, der #990
gefunden hat):

    "Beim Onboarding hat Claude die Stellen korrekt aus meinem Lebenslauf
    angelegt. Diese will ich im Nachhinein mit Claude besprechen und
    direkt aendern lassen. Allerdings sagt mir Claude immer, dass das
    Tool zum Bearbeiten nicht zur Verfuegung steht."

Das Werkzeug gab es die ganze Zeit: `profil_bearbeiten(bereich='position',
aktion='aendern', element_id=..., daten=...)`. Was fehlte, war der Weg an
die **element_id** — kein einziges Lesewerkzeug gab sie heraus:

* `profil_zusammenfassung` liefert formatierten Text ohne IDs,
* `profil_status` nur eine Zaehlung,
* `projekte_anzeigen` nennt `position_id` — aber nur fuer Positionen, die
  bereits ein Projekt tragen. Nach einem frischen Lebenslauf-Import ist
  das praktisch nie der Fall, also genau in der Situation des Melders
  nicht.

**Dasselbe Problem hatte H16/#741 fuer PROJEKTE bereits geloest** und
fuer die beiden Ebenen darueber nicht nachgezogen. Ein Werkzeug, das die
ID nur fuer einen von drei Datentypen herausgibt, ist ein halber Weg —
und ein halber Weg sieht von aussen aus wie ein fehlendes Werkzeug.

Die Tests pruefen deshalb beides: dass die IDs jetzt herauskommen, UND
dass der Weg vom Lesen zum Schreiben tatsaechlich durchlaeuft (die
gemeldete Aufgabe, Ende zu Ende).
"""
import asyncio
import importlib
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1740_994_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    datenbank = _db_mod.Database()
    datenbank.initialize()
    assert str(tmpdir) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    yield datenbank
    datenbank.close()
    os.environ.pop("BA_DATA_DIR", None)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import profil
    server = FastMCP("test")
    profil.register(server, db, logging.getLogger("test"))
    return server


def _call(server, name, args=None):
    async def _run():
        tool = await server.get_tool(name)
        res = await tool.run(args or {})
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


# Der typische Zustand nach einem Lebenslauf-Import: Titel, Firma und
# Zeitraum stehen da, die inhaltlichen Felder sind leer. Genau darueber
# wollte der Melder mit Claude sprechen.
LANGER_TEXT = ("Verantwortlich fuer die Einfuehrung eines PLM-Systems. " * 12)


def _profil_mit_bestand(db):
    db.save_profile({"name": "Test Person"})
    pos_id = db.add_position({
        "company": "Musterfirma GmbH", "title": "Consultant",
        "start_date": "2020-01", "is_current": True,
        "location": "Musterstadt", "description": LANGER_TEXT,
    })
    edu_id = db.add_education({
        "institution": "Musterhochschule", "degree": "Diplom",
        "field_of_study": "Maschinenbau",
        "start_date": "2010", "end_date": "2015", "grade": "1,8",
    })
    return pos_id, edu_id


# ── Der gemeldete Fall, Ende zu Ende ──────────────────────────────────

def test_994_gemeldeter_fall_lesen_dann_aendern(db, mcp):
    """Die Aufgabe des Melders, woertlich: Stellen besprechen und aendern.

    Ohne diesen Weg blieb nur der Griff in die Datenbank — genau das,
    was der Anti-DB-Bypass (#514) verhindern soll.
    """
    pos_id, _ = _profil_mit_bestand(db)

    # 1. Lesen — die ID kommt aus der Auskunft, nicht aus der DB.
    auskunft = _call(mcp, "positionen_anzeigen")
    gelesene_id = auskunft["positionen"][0]["position_id"]
    assert gelesene_id == pos_id

    # 2. Schreiben — mit genau dieser ID.
    ergebnis = _call(mcp, "profil_bearbeiten", {
        "bereich": "position", "aktion": "aendern",
        "element_id": gelesene_id,
        "daten": {"tasks": "Rollout in vier Werken, Schulung der Keyuser."},
    })
    assert ergebnis.get("status") != "fehler", ergebnis

    # 3. Gegenprobe am Bestand.
    assert "vier Werken" in db.get_profile()["positions"][0]["tasks"]


def test_994_gemeldeter_fall_ausbildung(db, mcp):
    """Dieselbe Kette fuer die Ausbildung — sie hing an derselben Luecke."""
    _, edu_id = _profil_mit_bestand(db)
    gelesene_id = _call(mcp, "positionen_anzeigen")["ausbildung"][0]["ausbildung_id"]
    assert gelesene_id == edu_id
    _call(mcp, "profil_bearbeiten", {
        "bereich": "ausbildung", "aktion": "aendern",
        "element_id": gelesene_id,
        "daten": {"grade": "1,3"},
    })
    assert db.get_profile()["education"][0]["grade"] == "1,3"


# ── positionen_anzeigen ───────────────────────────────────────────────

def test_994_positionen_anzeigen_ist_registriert(mcp):
    """DoD 8c: ein Werkzeug zaehlt erst, wenn es auch aufrufbar IST."""
    assert _call(mcp, "positionen_anzeigen")["status"] == "kein_profil"


def test_994_volltext_wird_nicht_gekuerzt(db, mcp):
    """Der Unterschied zu profil_zusammenfassung (dort 200 Zeichen).

    Das ist die #741-Lehre: wer einen Text weiterverarbeiten soll, braucht
    ihn ganz. Eine gekuerzte Beschreibung sieht aus wie eine kurze.
    """
    _profil_mit_bestand(db)
    assert len(LANGER_TEXT) > 400
    beschreibung = _call(mcp, "positionen_anzeigen")["positionen"][0]["beschreibung"]
    assert beschreibung == LANGER_TEXT
    assert "..." not in beschreibung


def test_994_alle_positionsfelder_kommen_mit(db, mcp):
    _profil_mit_bestand(db)
    eintrag = _call(mcp, "positionen_anzeigen")["positionen"][0]
    for feld in ("position_id", "titel", "firma", "ort", "zeitraum", "aktuell",
                 "stellenart", "branche", "beschreibung", "aufgaben",
                 "erfolge", "technologien"):
        assert feld in eintrag, f"{feld} fehlt in {sorted(eintrag)}"
    assert eintrag["zeitraum"] == "2020-01 - heute"


def test_994_zeitraum_zeigt_enddatum_wenn_beendet(db, mcp):
    db.save_profile({"name": "Test Person"})
    db.add_position({"company": "Musterfirma GmbH", "title": "Consultant",
                     "start_date": "2018-03", "end_date": "2019-12"})
    eintrag = _call(mcp, "positionen_anzeigen")["positionen"][0]
    assert eintrag["zeitraum"] == "2018-03 - 2019-12"
    assert eintrag["aktuell"] is False


def test_994_nur_id_filtert(db, mcp):
    pos_id, _ = _profil_mit_bestand(db)
    db.add_position({"company": "Zweite Firma GmbH", "title": "Ingenieur",
                     "start_date": "2016-01"})
    ergebnis = _call(mcp, "positionen_anzeigen", {"nur_id": pos_id})
    assert [p["position_id"] for p in ergebnis["positionen"]] == [pos_id]
    assert ergebnis["ausbildung"] == []


def test_994_nur_id_nimmt_ein_praefix(db, mcp):
    """Kurz-IDs sind im Chat der Normalfall — der Mensch tippt sie ab."""
    pos_id, _ = _profil_mit_bestand(db)
    ergebnis = _call(mcp, "positionen_anzeigen", {"nur_id": pos_id[:4]})
    assert [p["position_id"] for p in ergebnis["positionen"]] == [pos_id]


def test_994_unbekannte_id_ist_kein_leeres_ok(db, mcp):
    """Sonst sieht ein Tippfehler aus wie ein leerer Bestand."""
    _profil_mit_bestand(db)
    ergebnis = _call(mcp, "positionen_anzeigen", {"nur_id": "gibtsnicht"})
    assert ergebnis["status"] == "nicht_gefunden"


def test_994_ohne_profil_kommt_der_weg_zur_ersterfassung(mcp):
    ergebnis = _call(mcp, "positionen_anzeigen")
    assert ergebnis["status"] == "kein_profil"
    assert "ersterfassung_starten" in ergebnis["nachricht"]


def test_994_leerer_bestand_ist_keine_sackgasse(db, mcp):
    """#927: jede leere Auskunft nennt den naechsten Schritt."""
    db.save_profile({"name": "Test Person"})
    ergebnis = _call(mcp, "positionen_anzeigen")
    assert ergebnis["status"] == "leer"
    assert "position_hinzufuegen" in ergebnis["nachricht"]
    assert "dokument_profil_extrahieren" in ergebnis["nachricht"]


def test_994_leere_felder_werden_benannt(db, mcp):
    """Nach einem CV-Import fehlen Aufgaben, Erfolge und Technologien fast
    immer — ein Lebenslauf nennt sie selten vollstaendig. Genau das war
    der Anlass des Melders, also gehoert es in die Auskunft."""
    pos_id, _ = _profil_mit_bestand(db)
    ergebnis = _call(mcp, "positionen_anzeigen")
    luecken = ergebnis["luecken"]
    assert [l["position_id"] for l in luecken] == [pos_id]
    assert set(luecken[0]["fehlende_felder"]) == {"Aufgaben", "Erfolge", "Technologien"}
    assert "profil_bearbeiten" in ergebnis["hinweis"]


def test_994_vollstaendige_position_erzeugt_keinen_hinweis(db, mcp):
    """Gegenprobe: ein Melder, der alles gepflegt hat, wird nicht ermahnt."""
    db.save_profile({"name": "Test Person"})
    db.add_position({"company": "Musterfirma GmbH", "title": "Consultant",
                     "start_date": "2020-01", "description": "Text",
                     "tasks": "Aufgaben", "achievements": "Erfolge",
                     "technologies": "Python"})
    ergebnis = _call(mcp, "positionen_anzeigen")
    assert "luecken" not in ergebnis
    assert "hinweis" not in ergebnis


def test_994_der_weg_zum_aendern_steht_in_der_antwort(db, mcp):
    """Ein Weg, den nur der Docstring des Schreibers kennt, ist keiner."""
    _profil_mit_bestand(db)
    text = _call(mcp, "positionen_anzeigen")["aendern_mit"]
    assert "profil_bearbeiten" in text
    assert "element_id" in text
    assert "ausbildung" in text


def test_994_projekte_anzeigen_bleibt_unveraendert(db, mcp):
    """#741 darf durch die Nachzieh-Arbeit nicht kaputtgehen."""
    pos_id, _ = _profil_mit_bestand(db)
    db.add_project(pos_id, {"name": "PLM-Rollout",
                            "description": "Beschreibung"})
    ergebnis = _call(mcp, "projekte_anzeigen")
    assert ergebnis["status"] == "ok"
    assert ergebnis["projekte"][0]["position_id"] == pos_id


# ── profil_zusammenfassung ────────────────────────────────────────────

def test_994_zusammenfassung_nennt_die_positions_id(db, mcp):
    pos_id, _ = _profil_mit_bestand(db)
    ergebnis = _call(mcp, "profil_zusammenfassung")
    assert f"[{pos_id}]" in ergebnis["zusammenfassung"]


def test_994_zusammenfassung_nennt_die_ausbildungs_id(db, mcp):
    _, edu_id = _profil_mit_bestand(db)
    ergebnis = _call(mcp, "profil_zusammenfassung")
    assert f"[{edu_id}]" in ergebnis["zusammenfassung"]


def test_994_jede_genannte_id_steht_auch_im_text(db, mcp):
    """Der Guard: eine ID im Rueckgabe-Dict, die im gezeigten Text fehlt,
    hilft dem Menschen nicht — er liest den Text."""
    _profil_mit_bestand(db)
    db.add_position({"company": "Zweite Firma GmbH", "title": "Ingenieur",
                     "start_date": "2016-01"})
    ergebnis = _call(mcp, "profil_zusammenfassung")
    alle = ergebnis["positionen_ids"] + ergebnis["ausbildung_ids"]
    assert len(alle) == 3
    for kennung in alle:
        assert f"[{kennung}]" in ergebnis["zusammenfassung"], kennung


def test_994_zusammenfassung_erklaert_die_klammern(db, mcp):
    _profil_mit_bestand(db)
    text = _call(mcp, "profil_zusammenfassung")["zusammenfassung"]
    assert "element_id" in text
    assert "positionen_anzeigen()" in text


def test_994_zusammenfassung_traegt_den_bearbeiten_hinweis(db, mcp):
    _profil_mit_bestand(db)
    ergebnis = _call(mcp, "profil_zusammenfassung")
    assert "profil_bearbeiten" in ergebnis["bearbeiten_hinweis"]
    # #741 bleibt daneben stehen, es sind zwei verschiedene Wege.
    assert "projekte_anzeigen" in ergebnis["projekt_volltext_hinweis"]


def test_994_leeres_profil_bekommt_keinen_klammer_hinweis(db, mcp):
    """Ohne Eintraege gibt es keine Kennungen zu erklaeren."""
    db.save_profile({"name": "Test Person"})
    ergebnis = _call(mcp, "profil_zusammenfassung")
    assert "element_id" not in ergebnis["zusammenfassung"]
    assert ergebnis["positionen_ids"] == []


# ── Der zweite Teil des Berichts: die Feldnamen ───────────────────────
#
# Der Melder schrieb im Kommentar: "Sieht wohl also so aus, dass der MCP
# die Ids und/oder die Feld Namen nicht alle korrekt uebermittelt."
# Er hatte beide Haelften richtig. Die Lesewerkzeuge sprechen Deutsch,
# die Schreibschicht nimmt Spaltennamen — und verwarf alles andere still,
# WAEHREND sie "aktualisiert" meldete.

def test_994_deutsche_feldnamen_werden_geschrieben(db, mcp):
    """Gemessen vor dem Fix: Antwort "aktualisiert", Bestand unveraendert."""
    pos_id, _ = _profil_mit_bestand(db)
    ergebnis = _call(mcp, "profil_bearbeiten", {
        "bereich": "position", "aktion": "aendern", "element_id": pos_id,
        "daten": {"aufgaben": "Rollout in vier Werken",
                  "erfolge": "Durchlaufzeit halbiert",
                  "technologien": "Python, SQL"},
    })
    assert ergebnis["status"] == "aktualisiert"
    pos = db.get_profile()["positions"][0]
    assert pos["tasks"] == "Rollout in vier Werken"
    assert pos["achievements"] == "Durchlaufzeit halbiert"
    assert pos["technologies"] == "Python, SQL"


def test_994_geaenderte_felder_nennt_was_wirklich_ankam(db, mcp):
    """Eine Erfolgsmeldung ueber eine Nicht-Aenderung ist schlimmer als
    ein Fehler — sie beendet die Fehlersuche."""
    pos_id, _ = _profil_mit_bestand(db)
    ergebnis = _call(mcp, "profil_bearbeiten", {
        "bereich": "position", "aktion": "aendern", "element_id": pos_id,
        "daten": {"aufgaben": "Text"},
    })
    assert ergebnis["geaenderte_felder"] == ["tasks"]


def test_994_englische_feldnamen_funktionieren_weiter(db, mcp):
    """Die Alt-Aufrufer duerfen durch die Uebersetzung nicht brechen."""
    pos_id, _ = _profil_mit_bestand(db)
    _call(mcp, "profil_bearbeiten", {
        "bereich": "position", "aktion": "aendern", "element_id": pos_id,
        "daten": {"tasks": "Englisch", "is_current": False},
    })
    pos = db.get_profile()["positions"][0]
    assert pos["tasks"] == "Englisch"
    assert not pos["is_current"]


def test_994_unbekanntes_feld_wird_benannt_statt_verschluckt(db, mcp):
    pos_id, _ = _profil_mit_bestand(db)
    ergebnis = _call(mcp, "profil_bearbeiten", {
        "bereich": "position", "aktion": "aendern", "element_id": pos_id,
        "daten": {"lieblingsfarbe": "blau"},
    })
    assert ergebnis["status"] == "nichts_geaendert"
    assert ergebnis["ignorierte_felder"] == ["lieblingsfarbe"]
    assert "tasks" in ergebnis["moegliche_felder"]


def test_994_teilweise_unbekannt_schreibt_den_rest_und_meldet(db, mcp):
    """Das Bekannte geht durch, das Unbekannte kommt zurueck — nicht
    alles oder nichts."""
    pos_id, _ = _profil_mit_bestand(db)
    ergebnis = _call(mcp, "profil_bearbeiten", {
        "bereich": "position", "aktion": "aendern", "element_id": pos_id,
        "daten": {"aufgaben": "Text", "quatsch": 1},
    })
    assert ergebnis["status"] == "aktualisiert"
    assert ergebnis["geaenderte_felder"] == ["tasks"]
    assert ergebnis["ignorierte_felder"] == ["quatsch"]
    assert db.get_profile()["positions"][0]["tasks"] == "Text"


def test_994_deutsche_feldnamen_auch_bei_ausbildung(db, mcp):
    _, edu_id = _profil_mit_bestand(db)
    _call(mcp, "profil_bearbeiten", {
        "bereich": "ausbildung", "aktion": "aendern", "element_id": edu_id,
        "daten": {"note": "1,0", "fachrichtung": "Elektrotechnik",
                  "einrichtung": "Andere Musterhochschule"},
    })
    edu = db.get_profile()["education"][0]
    assert edu["grade"] == "1,0"
    assert edu["field_of_study"] == "Elektrotechnik"
    assert edu["institution"] == "Andere Musterhochschule"


def test_994_deutsche_feldnamen_auch_bei_projekt(db, mcp):
    """#741 haengt an derselben Schreibschicht — der halbe Weg soll sich
    nicht wiederholen."""
    pos_id, _ = _profil_mit_bestand(db)
    proj_id = db.add_project(pos_id, {"name": "PLM-Rollout"})
    _call(mcp, "profil_bearbeiten", {
        "bereich": "projekt", "aktion": "aendern", "element_id": proj_id,
        "daten": {"ergebnis": "Zwei Werke live", "rolle": "Teilprojektleitung"},
    })
    proj = _call(mcp, "projekte_anzeigen")["projekte"][0]
    assert proj["ergebnis"] == "Zwei Werke live"
    assert proj["rolle"] == "Teilprojektleitung"


def test_994_hinzufuegen_nimmt_deutsche_feldnamen(db, mcp):
    """add_position liest `data.get("tasks")` — deutsche Namen haetten
    eine leere Position erzeugt, ohne Hinweis."""
    db.save_profile({"name": "Test Person"})
    ergebnis = _call(mcp, "profil_bearbeiten", {
        "bereich": "position", "aktion": "hinzufuegen",
        "daten": {"firma": "Musterfirma GmbH", "titel": "Consultant",
                  "aufgaben": "Beratung", "beginn": "2020-01"},
    })
    assert ergebnis["status"] == "hinzugefuegt"
    pos = db.get_profile()["positions"][0]
    assert pos["company"] == "Musterfirma GmbH"
    assert pos["title"] == "Consultant"
    assert pos["tasks"] == "Beratung"
    assert pos["start_date"] == "2020-01"


def test_994_ausbildung_hinzufuegen_nimmt_deutsche_feldnamen(db, mcp):
    db.save_profile({"name": "Test Person"})
    _call(mcp, "profil_bearbeiten", {
        "bereich": "ausbildung", "aktion": "hinzufuegen",
        "daten": {"einrichtung": "Musterhochschule", "abschluss": "Master",
                  "fachrichtung": "Informatik"},
    })
    edu = db.get_profile()["education"][0]
    assert edu["institution"] == "Musterhochschule"
    assert edu["degree"] == "Master"


def test_994_die_auskunft_nennt_die_feldnamen_die_funktionieren(db, mcp):
    """Der Kreis schliesst sich: was positionen_anzeigen ausgibt, muss
    man auch zurueckschreiben koennen."""
    _profil_mit_bestand(db)
    ergebnis = _call(mcp, "positionen_anzeigen")
    text = ergebnis["aendern_mit"]
    for feld in ("aufgaben", "erfolge", "technologien", "beschreibung"):
        assert feld in text, feld
        assert feld in ergebnis["positionen"][0], feld


def test_994_jeder_ausgabename_ist_ein_gueltiger_eingabename(db, mcp):
    """Guard gegen den Rueckfall: gibt eine kuenftige Erweiterung ein
    neues deutsches Feld aus, muss die Schreibseite es kennen."""
    from bewerbungs_assistent.tools.profil import _felder_uebersetzen
    _profil_mit_bestand(db)
    eintrag = _call(mcp, "positionen_anzeigen")["positionen"][0]
    # Reine Anzeige-Felder ohne Gegenstueck in der Tabelle.
    nur_anzeige = {"position_id", "zeitraum", "aktuell", "projekte_anzahl"}
    pruefbar = {k: "x" for k in eintrag if k not in nur_anzeige}
    _, ignoriert = _felder_uebersetzen("position", pruefbar)
    assert ignoriert == [], ignoriert

    edu = _call(mcp, "positionen_anzeigen")["ausbildung"][0]
    pruefbar = {k: "x" for k in edu if k not in {"ausbildung_id", "zeitraum"}}
    _, ignoriert = _felder_uebersetzen("ausbildung", pruefbar)
    assert ignoriert == [], ignoriert
