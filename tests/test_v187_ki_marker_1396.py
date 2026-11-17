"""#1396 Schicht 1 - Bearbeitungsmarker je Stelle und ihre Migration.

Setzer UND Leser fuer jedes Feld (Lehre 4): jeder Schreibweg setzt den Marker,
die Migration setzt ihn fuer den Bestand, soweit ableitbar - Unbekanntes bleibt
`unbekannt` statt geraten (#989). Alle Datenbanken sind isoliert (BA_DATA_DIR).
"""
from __future__ import annotations

import os
import time

import pytest

TEXT = ("Aufgaben: Pflege der Stammdaten, Abstimmung mit den Fachbereichen. "
        "Anforderungen: mehrjaehrige Erfahrung, sicheres Deutsch und Englisch.")


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test 1396"})
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _stelle(db, kennung, titel="Sachbearbeiter Einkauf (m/w/d)", text=TEXT):
    db.save_jobs([{
        "hash": kennung, "title": titel, "company": "Musterwerk Nord GmbH",
        "location": "Hamburg", "url": f"https://example.com/1396/{kennung}",
        "source": "stepstone", "description": text, "score": 20,
    }])
    return db.resolve_job_hash(kennung)


def _z(db, voll):
    return dict(db.connect().execute(
        "SELECT * FROM jobs WHERE hash=?", (voll,)).fetchone())


# -- Spalten ----------------------------------------------------------------

def test_die_marker_spalten_gibt_es_und_ueberleben_einen_neuen_suchlauf(db):
    from bewerbungs_assistent.services import ki_lernen
    voll = _stelle(db, "m1")
    spalten = {r[1] for r in db.connect().execute("PRAGMA table_info(jobs)")}
    assert set(ki_lernen.SPALTEN) <= spalten
    assert set(ki_lernen.SPALTEN) <= set(db._BEWAHREN), \
        "Eine Marker-Spalte fehlt in _BEWAHREN: ein Suchlauf loescht sie (8e)."
    db.dismiss_job(voll, "falsches_fachgebiet")
    conn = db.connect()
    conn.execute("UPDATE jobs SET ollama_urteil='PASST', ollama_grund='x', "
                 "ollama_lag_richtig=0 WHERE hash=?", (voll,))
    conn.commit()
    _stelle(db, "m1")  # derselbe Treffer noch einmal (INSERT OR REPLACE)
    z = _z(db, voll)
    assert z["entschieden_von"] == "mensch"
    assert z["ollama_urteil"] == "PASST" and z["ollama_lag_richtig"] == 0


# -- Setzer: jeder Schreibweg ----------------------------------------------

@pytest.mark.parametrize("herkunft,grund,notiz,erwartet", [
    ("ich", "zu_junior", "", "mensch"),
    ("ich", "veraltet_url", "", "regel"),          # keine Passungsentscheidung
    ("claude", "falsche_branche", "", "claude"),
    ("automatik", "duplikat", "", "regel"),
    ("automatik", "profil_match_negativ", "[Auto-Aussortierung] passt nicht", "ollama"),
    ("automatik", "bewerbung_erstellt", "", "mensch"),  # der Mensch hat sich beworben
])
def test_dismiss_job_setzt_wer_entschieden_hat(db, herkunft, grund, notiz, erwartet):
    voll = _stelle(db, "d1")
    assert db.dismiss_job(voll, grund, herkunft=herkunft, notiz=notiz)
    assert _z(db, voll)["entschieden_von"] == erwartet


def test_urteil_von_claude_setzt_marker_und_der_mensch_behaelt_sein_wort(db):
    voll = _stelle(db, "u1")
    assert db.set_job_analysis(voll, "EMPFOHLEN", "Passt zum Profil.")
    z = _z(db, voll)
    assert z["claude_gelesen_am"] and z["entschieden_von"] == "claude"
    voll2 = _stelle(db, "u2")
    db.dismiss_job(voll2, "zu_junior")
    db.set_job_analysis(voll2, "BEDINGT", "Luecke")
    z2 = _z(db, voll2)
    assert z2["claude_gelesen_am"], "Claude hat gelesen, das steht an der Stelle."
    assert z2["entschieden_von"] == "mensch", "Das Wort des Menschen gilt weiter."


def test_zurueckholen_durch_den_menschen_ist_sein_ja(db):
    voll = _stelle(db, "r1")
    db.dismiss_job(voll, "profil_match_negativ", herkunft="automatik",
                   notiz="[Auto-Aussortierung] x")
    assert _z(db, voll)["entschieden_von"] == "ollama"
    assert db.restore_job(voll)
    assert _z(db, voll)["entschieden_von"] == "mensch"
    # Eine Reparatur ist kein Wort des Menschen.
    voll2 = _stelle(db, "r2")
    db.dismiss_job(voll2, "profil_match_negativ", herkunft="automatik")
    db.restore_job(voll2, durch_mensch=False)
    assert _z(db, voll2)["entschieden_von"] != "mensch"


def test_wiedergaenger_beim_anlegen_ist_eine_regel(db):
    # Eine neu angelegte, schon beim Speichern aussortierte Stelle (Dublette,
    # Nicht-DACH) ist eine Regel der Automatik.
    from bewerbungs_assistent.services import ki_lernen
    voll = _stelle(db, "w1")
    assert ki_lernen.ableiten("automatik", "duplikat") == "regel"
    conn = db.connect()
    conn.execute("UPDATE jobs SET is_active=0, dismissed_by='automatik', "
                 "entschieden_von=NULL WHERE hash=?", (voll,))
    conn.commit()
    assert _z(db, voll)["entschieden_von"] is None  # Vorbedingung des Altbestands


# -- Migration ---------------------------------------------------------------

def _altbestand(db):
    """Stellen, wie sie vor dem Update aussahen: ohne Marker."""
    stellen = {}
    zeilen = [
        # name, is_active, dismissed_by, reason, note, urteil
        ("mensch", 0, "ich", "zu_senior", None, None),
        ("regel", 0, "ich", "veraltet_url", None, None),
        ("ki", 0, "automatik", "profil_match_negativ",
         "[Auto-Aussortierung] Falsche Branche.", None),
        ("auto_regel", 0, "automatik", "duplikat", None, None),
        ("claude_dismiss", 0, "claude", "falsche_branche", None, None),
        ("ohne_herkunft", 0, None, "sonstiges", None, None),
        ("claude_aktiv", 1, None, None, None, "EMPFOHLEN"),
        ("offen", 1, None, None, None, None),
    ]
    for name, aktiv, von, grund, notiz, urteil in zeilen:
        voll = _stelle(db, "alt_" + name)
        stellen[name] = voll
        conn = db.connect()
        conn.execute(
            "UPDATE jobs SET is_active=?, dismissed_by=?, dismiss_reason=?, "
            "dismiss_note=?, dismissed_at='2026-10-01T10:00:00', "
            "analyse_urteil=?, analyse_am=?, entschieden_von=NULL, "
            "claude_gelesen_am=NULL, ollama_urteil=NULL WHERE hash=?",
            (aktiv, von, grund, notiz, urteil,
             "2026-10-02T09:00:00" if urteil else None, voll))
        conn.commit()
    db.db_marker_zuruecksetzen = True
    db.set_setting("ki_marker_migriert", False)
    return stellen


def test_migration_setzt_ableitbares_und_nennt_unbekanntes_unbekannt(db):
    from bewerbungs_assistent.services import ki_lernen
    s = _altbestand(db)
    erg = ki_lernen.migrieren(db)
    assert erg["status"] == "migriert"
    von = {k: _z(db, v)["entschieden_von"] for k, v in s.items()}
    assert von == {
        "mensch": "mensch", "regel": "regel", "ki": "ollama",
        "auto_regel": "regel", "claude_dismiss": "claude",
        "ohne_herkunft": "unbekannt",  # nicht geraten
        "claude_aktiv": "claude", "offen": None,
    }
    ki = _z(db, s["ki"])
    assert ki["ollama_urteil"] == "PASST_NICHT"
    assert ki["ollama_grund"] == "Falsche Branche."
    assert ki["ollama_gesehen_am"] == "2026-10-01T10:00:00"
    assert ki["ollama_lag_richtig"] is None, "Eine Gegenprobe gab es nie."
    assert _z(db, s["claude_aktiv"])["claude_gelesen_am"] == "2026-10-02T09:00:00"
    assert _z(db, s["offen"])["claude_gelesen_am"] is None


def test_migration_ist_idempotent_und_laeuft_nur_einmal(db):
    from bewerbungs_assistent.services import ki_lernen
    s = _altbestand(db)
    ki_lernen.migrieren(db)
    vorher = {k: _z(db, v) for k, v in s.items()}
    assert ki_lernen.migrieren(db)["status"] == "schon_erledigt"
    # Auch ohne Schalter aendert ein zweiter Durchgang nichts.
    db.set_setting("ki_marker_migriert", False)
    ki_lernen.migrieren(db)
    assert {k: _z(db, v) for k, v in s.items()} == vorher


def test_migration_haelt_ein_spaeter_gesetztes_urteil_der_ki(db):
    from bewerbungs_assistent.services import ki_lernen
    voll = _stelle(db, "g1")
    db.dismiss_job(voll, "profil_match_negativ", herkunft="automatik",
                   notiz="[Auto-Aussortierung] a")
    conn = db.connect()
    conn.execute("UPDATE jobs SET ollama_urteil='UNSICHER', ollama_lag_richtig=1 "
                 "WHERE hash=?", (voll,))
    conn.commit()
    db.set_setting("ki_marker_migriert", False)
    ki_lernen.migrieren(db)
    z = _z(db, voll)
    assert z["ollama_urteil"] == "UNSICHER" and z["ollama_lag_richtig"] == 1


def test_start_auf_grosser_datenbank_bleibt_schnell(db):
    """Messtest (DoD 8f): 20.000 Stellen, ein Durchgang. Grenzwert grosszuegig,
    gemessen wird auf der isolierten Testdatenbank."""
    from bewerbungs_assistent.services import ki_lernen
    conn = db.connect()
    pid = db.get_active_profile_id()
    zeilen = []
    for i in range(20000):
        von = ("ich", "automatik", "claude", None)[i % 4]
        zeilen.append((f"{pid}:gross{i}", f"Stelle {i}", "Firma", 0, von,
                       "zu_junior" if von == "ich" else "profil_match_negativ",
                       "[Auto-Aussortierung] Test" if von == "automatik" else None,
                       pid))
    conn.executemany(
        "INSERT INTO jobs (hash, title, company, is_active, dismissed_by, "
        "dismiss_reason, dismiss_note, profile_id, found_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?, '2026-10-01', '2026-10-01')", zeilen)
    conn.commit()
    db.set_setting("ki_marker_migriert", False)
    t0 = time.perf_counter()
    erg = ki_lernen.migrieren(db)
    dauer = time.perf_counter() - t0
    print(f"Migration 20000 Stellen: {dauer:.2f} s")
    assert erg["entschieden"] == 20000
    assert dauer < 5.0, f"Die Migration bremst den Start: {dauer:.1f} s"
    gesetzt = conn.execute("SELECT COUNT(*) FROM jobs WHERE entschieden_von IS NULL "
                           "AND is_active=0").fetchone()[0]
    assert gesetzt == 0


def test_ki_aus_marker_werden_trotzdem_gefuehrt(db):
    assert db.get_profile_setting("llm_local_state", "off") == "off"
    voll = _stelle(db, "k1")
    db.dismiss_job(voll, "zu_junior")
    assert _z(db, voll)["entschieden_von"] == "mensch"


def test_modulnamen_bleiben_getrennt():
    from bewerbungs_assistent.services import ki_lernen, lernprotokoll
    assert hasattr(ki_lernen, "ableiten") and hasattr(lernprotokoll, "regeln_lauf")
