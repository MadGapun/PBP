"""Tests fuer v1.7.22 — #942: Fachscore und Rahmenscore getrennt.

Additiv verrechnet konnten Rahmenpunkte fachliche Passung nicht nur
verstaerken, sondern ERSETZEN: eine Hamburger Senior-Remote-Stelle ohne
jeden Fachbezug kam auf zweistellige Scores, weil von den 82
PLUS-Keywords viele rein generisch sind (Senior, Lead, Remote, Hamburg,
Festanstellung).

Der Kern ist die **Asymmetrie**: ein Bonus darf fehlende Eignung nicht
kompensieren, ein Malus darf vorhandene Eignung sehr wohl entwerten.
"""
import pytest

from bewerbungs_assistent.job_scraper import (
    RAHMEN_DECKEL_STANDARD,
    calculate_score,
    rahmen_deckel_faktor,
)

BASIS = {
    "keywords_muss": ["PLM", "PDM"],
    "keywords_plus": ["Senior", "Remote", "Hamburg", "Festanstellung", "Lead"],
    "keywords_minus": ["Zeitarbeit"],
    "keywords_ausschluss": [],
    "gewichtung": {"muss": 7, "plus": 3, "minus": 6},
}


def _job(titel, text, **extra):
    j = {"title": titel, "description": text, "company": "Musterfirma GmbH"}
    j.update(extra)
    return j


# ── Deckelung: Rahmen kann Fach nicht ersetzen ───────────────────────

def test_942_viel_rahmen_schlaegt_nicht_viel_fach():
    """Das Kernversprechen des Issues.

    Eine Stelle mit EINEM MUSS-Treffer und vielen Rahmenbegriffen darf
    nicht vor einer Stelle mit mehreren MUSS-Treffern landen.
    """
    duenn = _job("Senior Lead (m/w/d)",
                 "Senior Lead in Hamburg, Remote moeglich, Festanstellung. "
                 "Erfahrung mit PLM von Vorteil.")
    dick = _job("PLM/PDM Spezialist",
                "Betreuung unserer PLM-Landschaft und des PDM-Systems.")
    s_duenn = calculate_score(dict(duenn), BASIS)
    s_dick = calculate_score(dict(dick), BASIS)
    assert s_dick > s_duenn, (s_dick, s_duenn)


def test_942_rahmen_ist_relativ_gedeckelt():
    job = _job("PLM Berater",
               "PLM Berater. Senior, Lead, Remote, Hamburg, Festanstellung.")
    ergebnis = dict(job)
    calculate_score(ergebnis, BASIS)
    fach = ergebnis["_fachscore"]
    rahmen = ergebnis["_rahmenscore"]
    assert rahmen <= RAHMEN_DECKEL_STANDARD * fach + 0.01, (fach, rahmen)
    # Ungedeckelt waere deutlich mehr angefallen.
    assert ergebnis["_rahmen_ungedeckelt"] > rahmen


def test_942_null_fachscore_bleibt_null_egal_wieviel_rahmen():
    """Null mal irgendetwas bleibt null."""
    job = _job("Senior Lead Manager",
               "Senior Lead in Hamburg, Remote, Festanstellung, Lead-Rolle.")
    assert calculate_score(job, BASIS) == 0


# ── Asymmetrie: MINUS bleibt ungedeckelt ─────────────────────────────

def test_942_minus_kann_fachlich_starke_stelle_abstuerzen_lassen():
    """Eine PLM-Stelle, die sich als Zeitarbeit entpuppt, darf fallen."""
    kriterien = dict(BASIS)
    kriterien["gewichtung"] = {"muss": 7, "plus": 3, "minus": 20}
    stark = _job("PLM Consultant",
                 "PLM und PDM Beratung im Maschinenbau.")
    stark_mit_malus = _job("PLM Consultant",
                           "PLM und PDM Beratung im Maschinenbau. "
                           "Einsatz ueber Zeitarbeit.")
    ohne = calculate_score(stark, kriterien)
    ergebnis = dict(stark_mit_malus)
    mit = calculate_score(ergebnis, kriterien)
    assert mit < ohne
    assert mit == 0, "der Malus traegt die Stelle bis auf den Boden"
    # Ungedeckelt heisst: der Malus wird NICHT auf einen Anteil des
    # Fachscores begrenzt. Am Endscore ist das nicht ablesbar, weil der
    # bei 0 abgeschnitten wird — am Rahmenanteil schon.
    assert ergebnis["_rahmenscore"] <= -20, ergebnis


def test_942_minus_wirkt_auch_wenn_rahmen_positiv_waere():
    kriterien = dict(BASIS)
    kriterien["gewichtung"] = {"muss": 7, "plus": 3, "minus": 30}
    job = _job("PLM Lead",
               "PLM Lead, Senior, Remote, Hamburg. Anstellung ueber Zeitarbeit.")
    ergebnis = dict(job)
    calculate_score(ergebnis, kriterien)
    assert ergebnis["_rahmenscore"] < 0, ergebnis


# ── Einstellbarkeit und Sonderfaelle ─────────────────────────────────

def test_942_deckel_ist_einstellbar():
    job = _job("PLM Berater",
               "PLM Berater. Senior, Lead, Remote, Hamburg, Festanstellung.")
    eng = dict(BASIS); eng["rahmen_deckel_faktor"] = 0.0
    weit = dict(BASIS); weit["rahmen_deckel_faktor"] = 99.0
    assert calculate_score(dict(job), eng) < calculate_score(dict(job), weit)


def test_942_ohne_muss_keywords_gilt_kein_deckel():
    """Sonst bekaeme jede Stelle 0 — ausgerechnet bei frischen Profilen.

    Ohne MUSS-Liste gibt es keinen Fachscore, an dem sich etwas
    relativieren liesse; der Rahmen IST dann die Bewertung.
    """
    kriterien = {"keywords_muss": [], "keywords_plus": ["Senior", "Remote"],
                 "keywords_minus": [], "keywords_ausschluss": [],
                 "gewichtung": {"muss": 7, "plus": 3, "minus": 6}}
    job = _job("Senior Entwickler", "Senior Entwickler, Remote.")
    assert calculate_score(job, kriterien) > 0


def test_942_deckel_standard_und_fehlerhafte_werte():
    assert rahmen_deckel_faktor({}) == RAHMEN_DECKEL_STANDARD
    assert rahmen_deckel_faktor({"rahmen_deckel_faktor": ""}) == RAHMEN_DECKEL_STANDARD
    assert rahmen_deckel_faktor({"rahmen_deckel_faktor": "quatsch"}) == RAHMEN_DECKEL_STANDARD
    assert rahmen_deckel_faktor({"rahmen_deckel_faktor": -1}) == RAHMEN_DECKEL_STANDARD
    assert rahmen_deckel_faktor({"rahmen_deckel_faktor": 0}) == 0.0
    assert rahmen_deckel_faktor({"rahmen_deckel_faktor": "0.25"}) == 0.25


# ── Teilscores sichtbar ──────────────────────────────────────────────

def test_942_teilscores_werden_am_job_hinterlegt():
    job = _job("PLM Consultant", "PLM und PDM, Senior, Remote.")
    calculate_score(job, BASIS)
    assert "_fachscore" in job and "_rahmenscore" in job
    assert job["_fachscore"] > 0


def test_942_teilscores_werden_gespeichert(tmp_db):
    """AK: getrennt berechnet UND gespeichert."""
    job = {"hash": "f942a", "title": "PLM Consultant",
           "description": "PLM und PDM Beratung, Senior, Remote.",
           "company": "Musterfirma GmbH", "url": "https://example.com/f942a",
           "source": "bundesagentur"}
    job["score"] = calculate_score(job, BASIS)
    tmp_db.save_jobs([job])
    row = tmp_db.connect().execute(
        "SELECT fachscore, rahmenscore FROM jobs WHERE hash LIKE '%f942a'").fetchone()
    assert row is not None
    assert row[0] and row[0] > 0, row


def test_942_ohne_bewertung_bleibt_teilscore_leer(tmp_db):
    """NULL ist ehrlich 'nicht bewertet' — 0 waere eine Aussage."""
    tmp_db.save_jobs([{
        "hash": "f942b", "title": "Manuell angelegt", "company": "Musterfirma GmbH",
        "url": "https://example.com/f942b", "source": "bundesagentur", "score": 0,
    }])
    row = tmp_db.connect().execute(
        "SELECT fachscore FROM jobs WHERE hash LIKE '%f942b'").fetchone()
    assert row[0] is None, row
