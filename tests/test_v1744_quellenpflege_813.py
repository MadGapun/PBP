"""Tests fuer v1.7.44 — #813: Quellenpflege vom 08.09.2026.

Ausgangspunkt war eine Bestandsaufnahme, kein Fehlerbericht: sieben
Quellen standen seit dem 01.09. automatisch abgeschaltet, Begruendung
jeweils "5 stille Laeufe in Serie".

**Eine davon lebte.** `himalayas` antwortet mit HTTP 200 und liefert 20
Stellen. Der Adapter starb an der ERSTEN davon: das Feld `seniority`
kommt seit einem Feldumbau als Liste (`['Senior']`) statt als String,
`.lower()` warf einen `AttributeError`, und weil die Zuordnungsschleife
in einem grossen `try` lag, gab der Adapter eine leere Liste zurueck.

Das ist die teuerste Bauform einer stillen Null, weil sie sich selbst
bestaetigt: der Fehler erzeugt Leere, die Leere erzeugt die Abschaltung,
und die Abschaltung verhindert, dass der Fehler je wieder auffaellt.

Dieselbe Bauform steckte in zehn Adaptern, zwei davon (`remoteok`,
`remotive`) liefern produktiv.

Dazu drei Befunde an der Diagnose selbst:

* `reactivate_at` wurde beim Abschalten gesetzt und von KEINEM Aufrufer
  gelesen — der dokumentierte Backoff (24/48/72/168 h) existierte nur als
  Datenfeld, abgeschaltete Quellen kamen nie zurueck.
* `last_error` wurde bei Erfolg nie geloescht: die Bundesagentur trug mit
  91 % Erfolgsrate und 5122 Treffern weiterhin "server_weg".
* `no_probe_defined` zaehlte als "nicht erreichbar" — "5 von 7 nicht
  erreichbar" hiess in Wahrheit "5 nicht pruefbar".
"""
import importlib
import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.job_scraper import satzweise  # noqa: E402


# ── Das Nadeloehr: ein Satz kostet einen Satz ─────────────────────────

def test_813_ein_kaputter_satz_kostet_nicht_die_quelle():
    """Der gemeldete Mechanismus, nachgestellt: 20 Datensaetze, der
    erste umgebaut. Vorher: 0 Stellen. Jetzt: 19."""
    rohdaten = [{"titel": f"Stelle {i}", "seniority": "Senior"}
                for i in range(20)]
    rohdaten[0]["seniority"] = ["Senior"]        # der Feldumbau

    def abbildung(roh):
        return {"titel": roh["titel"], "stufe": roh["seniority"].lower()}

    stellen, befund = satzweise.zuordnen(rohdaten, abbildung, "testquelle")
    assert len(stellen) == 19
    assert befund["fehlerhaft"] == 1
    assert befund["gesamt"] == 20
    assert "AttributeError" in befund["erster_fehler"]


def test_813_feldumbau_wird_als_solcher_benannt():
    """Ein Ausreisser ist etwas anderes als ein Feldumbau. Kippen ALLE
    Saetze, ist nicht der Markt leer — dann liest der Adapter falsch."""
    rohdaten = [{"seniority": ["Senior"]} for _ in range(10)]
    _, befund = satzweise.zuordnen(
        rohdaten, lambda r: {"x": r["seniority"].lower()}, "testquelle")
    assert befund["verdacht"] == "feldumbau"
    assert befund["abgebildet"] == 0


def test_813_einzelner_ausreisser_ist_kein_feldumbau():
    """Gegenprobe — sonst warnt PBP bei jedem Lauf und wird ignoriert."""
    rohdaten = [{"seniority": "Senior"} for _ in range(10)]
    rohdaten[3]["seniority"] = None
    _, befund = satzweise.zuordnen(
        rohdaten, lambda r: {"x": r["seniority"].lower()}, "testquelle")
    assert befund["fehlerhaft"] == 1
    assert "verdacht" not in befund


def test_813_feldformen_nennen_die_ursache_ohne_die_daten():
    """Die Diagnose ist der TYP, nicht der Wert — in Stellenanzeigen
    stehen fremde Daten, und eine Log-Zeile ist kein Ort dafuer."""
    formen = satzweise.feldformen(
        {"title": "Senior PLM Consultant", "seniority": ["Senior"],
         "minSalary": 90000, "company": None})
    assert formen == {"title": "str", "seniority": "list",
                      "minSalary": "int", "company": "NoneType"}
    assert "PLM" not in str(formen)


def test_813_ausgelassene_saetze_sind_keine_fehler():
    """`None` heisst "nicht brauchbar", nicht "kaputt" — die beiden
    duerfen in der Zaehlung nicht zusammenfallen."""
    _, befund = satzweise.zuordnen(
        [{"a": 1}, {"a": 2}], lambda r: None, "testquelle")
    assert befund["ausgelassen"] == 2 and befund["fehlerhaft"] == 0


def test_813_leere_eingabe_bleibt_ruhig():
    assert satzweise.zuordnen([], lambda r: r)[0] == []
    assert satzweise.zuordnen(None, lambda r: r)[1]["gesamt"] == 0


# ── text_aus: gegen den naechsten Feldumbau ───────────────────────────

def test_813_text_aus_liest_jede_form():
    """Aus "Senior" wurde ['Senior']. Beim naechsten Mal ist es ein
    Objekt — der Adapter soll das ueberleben, nicht daran sterben."""
    assert satzweise.text_aus("Senior") == "Senior"
    assert satzweise.text_aus(["Senior"]) == "Senior"
    assert satzweise.text_aus(["Senior", "Lead"]) == "Senior Lead"
    assert satzweise.text_aus({"name": "Senior"}) == "Senior"
    assert satzweise.text_aus(None) == ""
    assert satzweise.text_aus(42) == "42"
    assert satzweise.text_aus([]) == ""


# ── Der konkrete Adapter ──────────────────────────────────────────────

def test_813_himalayas_uebersteht_die_liste_im_seniority_feld():
    """Der Datensatz, an dem der Adapter am 08.09. gestorben ist."""
    from bewerbungs_assistent.job_scraper.himalayas import _map
    stelle = _map({
        "title": "Sr. Technical Writer",
        "companyName": "Musterfirma LLC",
        "seniority": ["Senior"],                  # Liste, nicht String
        "employmentType": "Full Time",
        "applicationLink": "https://example.org/job/1",
        "guid": "https://example.org/job/1",
        "description": "<p>Ein Anzeigentext.</p>",
        "locationRestrictions": ["United States"],
    })
    assert stelle["title"] == "Sr. Technical Writer"
    assert stelle["employment_type"] == "festanstellung"


def test_813_himalayas_nennt_die_ortsbindung():
    """`country=DE` filtert NICHT: gemessen am 08.09. trugen Treffer aus
    der DE-Abfrage `locationRestrictions: ['United States']`. Pauschal
    "Remote" liesse sie aussehen wie Stellen, auf die man sich von
    Hamburg aus bewerben kann."""
    from bewerbungs_assistent.job_scraper.himalayas import _map
    basis = {"title": "Rolle", "companyName": "Musterfirma LLC",
             "guid": "x", "applicationLink": "https://example.org/1"}
    mit = _map(dict(basis, locationRestrictions=["United States"]))
    assert mit["location"] == "Remote (United States)"
    ohne = _map(dict(basis))
    assert ohne["location"] == "Remote"


def test_813_himalayas_freelance_bleibt_erkannt():
    """Gegenprobe zur Feld-Haertung: die Einordnung darf sich nicht
    aendern, nur weil sie jetzt robuster liest."""
    from bewerbungs_assistent.job_scraper.himalayas import _map
    basis = {"title": "Rolle", "companyName": "Musterfirma LLC", "guid": "x"}
    assert _map(dict(basis, employmentType="Contract"))["employment_type"] == "freelance"
    assert _map(dict(basis, seniority=["Internship"]))["employment_type"] == "praktikum"


def test_813_adapter_nutzen_das_nadeloehr():
    """Guard gegen den Rueckfall: die drei umgestellten Adapter duerfen
    nicht wieder eine eigene ungeschuetzte Schleife bekommen."""
    basis = (Path(__file__).resolve().parents[1] / "src"
             / "bewerbungs_assistent" / "job_scraper")
    for name in ("himalayas.py", "remoteok.py", "remotive.py"):
        text = (basis / name).read_text(encoding="utf-8")
        assert "from .satzweise import" in text, name
        assert "zuordnen(" in text, name


# ── Die Diagnose sagt die Wahrheit ────────────────────────────────────

@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1744_813_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    datenbank = _db_mod.Database()
    datenbank.initialize()
    assert str(tmpdir) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    datenbank.save_profile({"name": "Test Person"})
    yield datenbank
    datenbank.close()
    os.environ.pop("BA_DATA_DIR", None)
    shutil.rmtree(tmpdir, ignore_errors=True)


def _health(db, name):
    return next((h for h in db.get_scraper_health()
                 if h["scraper_name"] == name), None)


def test_813_erfolg_loescht_den_alten_fehler(db):
    """Gemessen am 08.09.: die Bundesagentur trug mit 91 % Erfolgsrate,
    Fehlerserie 0 und 5122 Treffern weiterhin "server_weg". Eine
    Anzeige, die Fehler behauptet, wo keine sind, wird genauso ignoriert
    wie eine, die keine meldet."""
    db.update_scraper_health("testquelle", "fail", detail="server_weg",
                             error_class="server_weg")
    assert _health(db, "testquelle")["last_error"]
    db.update_scraper_health("testquelle", "ok", count=42)
    eintrag = _health(db, "testquelle")
    assert not eintrag["last_error"]
    assert eintrag["consecutive_failures"] == 0


def test_813_faellige_probe_laeuft_wieder_mit(db):
    """Der Kern: `reactivate_at` wurde gesetzt und von niemandem gelesen.
    Sieben Quellen standen seit dem 01.09. still, `letzte_probe_am` bei
    allen `null` — eine davon lieferte in Wahrheit 20 Stellen."""
    from bewerbungs_assistent.job_scraper import quellen_einteilen
    db.update_scraper_health("testquelle", "ok", count=1)
    conn = db.connect()
    faellig = (datetime.now() - timedelta(hours=1)).isoformat()
    conn.execute("UPDATE scraper_health SET is_active=0, reactivate_at=?, "
                 "reactivate_attempt=1 WHERE scraper_name=?",
                 (faellig, "testquelle"))
    conn.commit()
    deaktiviert, _defekt, probelauf = quellen_einteilen(db)
    assert "testquelle" in probelauf
    assert "testquelle" not in deaktiviert


def test_813_nicht_faellige_quelle_bleibt_aus(db):
    """Gegenprobe: der Backoff muss wirken, sonst probt jeder Lauf
    dieselbe tote Quelle."""
    from bewerbungs_assistent.job_scraper import quellen_einteilen
    db.update_scraper_health("testquelle", "ok", count=1)
    conn = db.connect()
    spaeter = (datetime.now() + timedelta(hours=20)).isoformat()
    conn.execute("UPDATE scraper_health SET is_active=0, reactivate_at=? "
                 "WHERE scraper_name=?", (spaeter, "testquelle"))
    conn.commit()
    deaktiviert, _defekt, probelauf = quellen_einteilen(db)
    assert "testquelle" in deaktiviert and "testquelle" not in probelauf


def test_813_abgeschaltet_ohne_termin_bleibt_abgeschaltet(db):
    """Wer bewusst abgeschaltet hat, will keine Wiederbelebung."""
    from bewerbungs_assistent.job_scraper import quellen_einteilen
    db.update_scraper_health("testquelle", "ok", count=1)
    conn = db.connect()
    conn.execute("UPDATE scraper_health SET is_active=0, reactivate_at=NULL "
                 "WHERE scraper_name=?", ("testquelle",))
    conn.commit()
    deaktiviert, _defekt, probelauf = quellen_einteilen(db)
    assert "testquelle" in deaktiviert and not probelauf


def test_813_stiller_probelauf_verschiebt_den_termin(db):
    """Die Backoff-Leiter aus #590-C.1, die bis v1.7.43 nur ein
    Datenfeld war: 24 -> 48 -> 72 -> 168 Stunden."""
    db.update_scraper_health("testquelle", "ok", count=1)
    conn = db.connect()
    frueher = (datetime.now() - timedelta(hours=1)).isoformat()
    conn.execute("UPDATE scraper_health SET is_active=0, reactivate_at=?, "
                 "reactivate_attempt=1 WHERE scraper_name=?",
                 (frueher, "testquelle"))
    conn.commit()
    db.update_scraper_health("testquelle", "ok", count=0)   # still
    eintrag = _health(db, "testquelle")
    assert eintrag["reactivate_attempt"] == 2
    assert eintrag["reactivate_at"] > datetime.now().isoformat()


def test_813_lieferndes_probelauf_reaktiviert(db):
    """Und der Fall, um den es geht: die Quelle lebt wieder."""
    db.update_scraper_health("testquelle", "ok", count=1)
    conn = db.connect()
    conn.execute("UPDATE scraper_health SET is_active=0, reactivate_at=? "
                 "WHERE scraper_name=?",
                 ((datetime.now() - timedelta(hours=1)).isoformat(),
                  "testquelle"))
    conn.commit()
    db.update_scraper_health("testquelle", "ok", count=20)
    eintrag = _health(db, "testquelle")
    assert eintrag["is_active"] == 1
    assert not eintrag["reactivate_at"]
