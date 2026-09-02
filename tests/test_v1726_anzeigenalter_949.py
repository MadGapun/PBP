"""Tests fuer v1.7.26 — #949 Befund 2: das Alter einer Anzeige.

PBP kannte nur `found_at` — wann PBP die Stelle GESEHEN hat. Eine seit
sechs Monaten laufende Anzeige, gestern neu gescraped, sah damit
taufrisch aus. Aufgefallen ist es nur, weil der Nutzer die
Originalanzeige selbst geoeffnet hat.

Das Feld `jobs.veroeffentlicht_am` existiert seit #434 — es wurde nur
von genau EINEM der 26 Adapter befuellt und nirgends eingeordnet.

Bewusst ein HINWEIS, kein Score-Malus: eine lang laufende Anzeige kann
eine schwer besetzbare Spezialistenrolle sein, und die Leitlinie lautet
Recall vor Praezision.
"""
from datetime import date

import pytest

from bewerbungs_assistent.services.anzeigenalter import (
    SCHWELLE_TAGE,
    alter_tage,
    aus_rohdaten,
    einordnung,
    normalisiere,
)

HEUTE = date(2026, 9, 2)


# ── Datum lesen, ohne eines zu erfinden ──────────────────────────────

@pytest.mark.parametrize("wert,erwartet", [
    ("2026-06-15", "2026-06-15"),
    ("2026-06-15T08:30:00Z", "2026-06-15"),
    ("15.06.2026", "2026-06-15"),
    ("vor 6 Monaten", None),
    ("demnaechst", None),
    ("2026-13-45", None),      # kein gueltiges Datum
    ("", None),
    (None, None),
])
def test_949_datum_wird_streng_gelesen(wert, erwartet):
    """Ein falsches Datum waere schlimmer als keines — es wuerde ein
    Frischesignal erfinden."""
    assert normalisiere(wert) == erwartet


def test_949_rohdaten_tolerant_im_schluessel():
    """Welcher Schluessel kommt, unterscheidet sich je Portal und
    API-Version. Der belegte Fall betrifft die Arbeitsagentur."""
    assert aus_rohdaten(
        {"aktuelleVeroeffentlichungsdatum": "2026-06-15"}) == "2026-06-15"
    assert aus_rohdaten({"datePosted": "2026-06-15"}) == "2026-06-15"
    assert aus_rohdaten({"irgendwas": "2026-06-15"}) is None
    assert aus_rohdaten({}) is None
    assert aus_rohdaten(None) is None


def test_949_rohdaten_uebernehmen_keinen_unsinn():
    """Ein Feld, das zwar heisst wie ein Datum, aber keines enthaelt."""
    assert aus_rohdaten({"datePosted": "laufend"}) is None


# ── Alter berechnen ──────────────────────────────────────────────────

def test_949_alter_wird_gerechnet():
    assert alter_tage("2026-08-30", HEUTE) == 3
    assert alter_tage("2026-03-02", HEUTE) == 184


def test_949_zukunftsdatum_ist_kein_negatives_alter():
    """Ein Datum in der Zukunft ist ein Datenfehler."""
    assert alter_tage("2027-01-01", HEUTE) is None


def test_949_ohne_datum_kein_alter():
    assert alter_tage(None, HEUTE) is None
    assert alter_tage("", HEUTE) is None


# ── Einordnung ───────────────────────────────────────────────────────

def test_949_lange_laufzeit_wird_benannt():
    """Der belegte Fall: sechs Monate Laufzeit bei fuenf Klicks."""
    e = einordnung({"veroeffentlicht_am": "2026-03-02"}, HEUTE)
    assert e["guete"] == "belegt"
    assert e["anzeigenalter_tage"] == 184
    assert "Dauerausschreibung" in e["hinweis"]
    assert "Malus" in e["hinweis"], "Muss als Hinweis gekennzeichnet sein"


def test_949_frische_anzeige_wird_als_chance_benannt():
    """Fuer diesen Nutzer ausdruecklich die Begruendung, die manuellen
    Kanaele hoechstens woechentlich zu pruefen."""
    e = einordnung({"veroeffentlicht_am": "2026-08-30"}, HEUTE)
    assert "Chance" in e["hinweis"]


def test_949_mittleres_alter_bleibt_kommentarlos():
    """Nicht jede Zahl braucht einen Satz — sonst wird der Hinweis
    zum Rauschen und niemand liest ihn mehr."""
    e = einordnung({"veroeffentlicht_am": "2026-06-15"}, HEUTE)
    assert e["anzeigenalter_tage"] == 79
    assert "hinweis" not in e


def test_949_unbekannt_sagt_dass_found_at_etwas_anderes_ist():
    """Der Kern des Befunds: `found_at` wurde als Anzeigenalter
    gelesen."""
    e = einordnung({}, HEUTE)
    assert e["guete"] == "unbekannt"
    assert "found_at" in e["hinweis"]


def test_949_schwelle_ist_die_aus_dem_issue():
    assert SCHWELLE_TAGE == 90


# ── Verdrahtung ──────────────────────────────────────────────────────

def test_949_bundesagentur_liest_das_datum():
    """Die Arbeitsagentur liefert es strukturiert — sie war die
    naheliegendste Quelle, um die Luecke zu schliessen."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "job_scraper" /
              "bundesagentur.py").read_text(encoding="utf-8")
    assert "anzeigenalter.aus_rohdaten" in quelle
    assert "veroeffentlicht_am" in quelle


def test_949_tools_geben_die_laufzeit_aus():
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "tools" / "jobs.py").read_text(encoding="utf-8")
    assert "anzeigenalter_tage" in quelle
    assert '"anzeigenalter"' in quelle


def test_949_stelle_mit_datum_zeigt_die_laufzeit(tmp_db):
    """Ende zu Ende ueber die echte DB."""
    tmp_db.save_jobs([{
        "hash": "s949", "title": "PLM Consultant",
        "company": "Musterfirma GmbH", "url": "https://example.com/949",
        "source": "manuell", "description": "PLM und Teamcenter.",
        "veroeffentlicht_am": "2026-03-02",
    }])
    job = tmp_db.get_job("s949")
    assert job.get("veroeffentlicht_am") == "2026-03-02", job
    e = einordnung(job, HEUTE)
    assert e["anzeigenalter_tage"] == 184
