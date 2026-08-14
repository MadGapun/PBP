# -*- coding: utf-8 -*-
"""Tests fuer das Musterprofil-Seed-Modul (Baustelle 7, #840).

Prueft, dass beide Musterprofile reproduzierbar in der geforderten Tiefe
entstehen und ausschliesslich fiktive Firmen verwenden.
"""

import importlib
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCREENSHOT_DIR = PROJECT_ROOT / "docs" / "screenshots"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCREENSHOT_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture()
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database as database_module
    importlib.reload(database_module)
    d = database_module.Database()
    d.initialize()
    # QA-Isolations-Regel (CLAUDE.md): niemals gegen die echte User-DB.
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    yield d
    d.close()


@pytest.fixture()
def geseedet(db):
    import musterprofile
    importlib.reload(musterprofile)
    pids = musterprofile.seed_all(db)
    return db, pids


def _count(db, sql, *args):
    return db.connect().execute(sql, args).fetchone()[0]


def test_seed_all_legt_beide_profile_an_und_bob_ist_aktiv(geseedet):
    db, pids = geseedet
    assert set(pids) == {"bob", "anna"}
    assert db.get_active_profile_id() == pids["bob"]
    namen = {p["name"] for p in db.get_profiles()}
    assert {"Bob Mustermann", "Anna Beispiel"} <= namen


@pytest.mark.parametrize("wer", ["bob", "anna"])
def test_profil_tiefe_entspricht_dem_komplexitaetsziel(geseedet, wer):
    db, pids = geseedet
    pid = pids[wer]
    # 8-10 Stationen
    assert _count(db, "SELECT COUNT(*) FROM positions WHERE profile_id=?", pid) >= 8
    # 12-15 STAR-Projekte (mit gefuellten STAR-Feldern)
    projekte = _count(
        db,
        "SELECT COUNT(*) FROM projects p JOIN positions pos ON p.position_id = pos.id "
        "WHERE pos.profile_id=? AND p.situation != '' AND p.result != ''",
        pid,
    )
    assert projekte >= 12
    # 40-60 Skills
    assert 40 <= _count(db, "SELECT COUNT(*) FROM skills WHERE profile_id=?", pid) <= 60
    # mehrere Ausbildungsstationen
    assert _count(db, "SELECT COUNT(*) FROM education WHERE profile_id=?", pid) >= 5
    # 20-30 Bewerbungen
    apps = _count(db, "SELECT COUNT(*) FROM applications WHERE profile_id=?", pid)
    assert 20 <= apps <= 30
    # Kontakte, Dokumente, Aufgaben, Termine
    assert _count(db, "SELECT COUNT(*) FROM contacts WHERE profile_id=?", pid) >= 6
    assert _count(db, "SELECT COUNT(*) FROM documents WHERE profile_id=?", pid) >= 8
    assert _count(db, "SELECT COUNT(*) FROM tasks WHERE profile_id=?", pid) >= 7
    assert _count(db, "SELECT COUNT(*) FROM application_meetings WHERE profile_id=?", pid) >= 6


@pytest.mark.parametrize("wer", ["bob", "anna"])
def test_bewerbungsverlauf_hat_realistische_ausgaenge(geseedet, wer):
    db, pids = geseedet
    pid = pids[wer]
    rows = db.connect().execute(
        "SELECT status, COUNT(*) FROM applications WHERE profile_id=? GROUP BY status",
        (pid,),
    ).fetchall()
    stati = {r[0]: r[1] for r in rows}
    assert stati.get("abgelaufen", 0) >= 4, f"{wer}: {stati}"
    assert stati.get("abgelehnt", 0) >= 2
    assert stati.get("zurueckgezogen", 0) >= 1
    assert "zweitgespraech" in stati or "angebot" in stati
    # Streuung ueber mehrere Monate (Timeline-Charts brauchen Verlauf)
    monate = _count(
        db,
        "SELECT COUNT(DISTINCT strftime('%Y-%m', applied_at)) FROM applications "
        "WHERE profile_id=?",
        pid,
    )
    assert monate >= 5, f"{wer}: Bewerbungen nur in {monate} Monaten"


def test_besondere_ausgaenge_sind_abgedeckt(geseedet):
    db, pids = geseedet
    # arbeitgeber_ausgefallen (Insolvenz vor Antritt) bei Bob
    assert _count(
        db,
        "SELECT COUNT(*) FROM applications WHERE profile_id=? AND status='arbeitgeber_ausgefallen'",
        pids["bob"],
    ) == 1
    # Absage-Muster-Karte braucht >= 3 Absagen mit rejection_reason
    for pid in pids.values():
        mit_grund = _count(
            db,
            "SELECT COUNT(*) FROM applications WHERE profile_id=? AND status='abgelehnt' "
            "AND rejection_reason != ''",
            pid,
        )
        assert mit_grund >= 2
    # Ablehnungsgruende-Chart braucht aussortierte Stellen
    for pid in pids.values():
        assert _count(
            db,
            "SELECT COUNT(*) FROM jobs WHERE profile_id=? AND is_active=0 "
            "AND dismiss_reason != ''",
            pid,
        ) >= 5


def test_aufgaben_fuellen_alle_faelligkeitsgruppen(geseedet):
    db, pids = geseedet
    for pid in pids.values():
        conn = db.connect()
        heute = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE profile_id=? AND faellig_am = date('now')",
            (pid,),
        ).fetchone()[0]
        ueberfaellig = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE profile_id=? AND faellig_am < date('now') "
            "AND faellig_am IS NOT NULL",
            (pid,),
        ).fetchone()[0]
        zukunft = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE profile_id=? AND faellig_am > date('now')",
            (pid,),
        ).fetchone()[0]
        ohne = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE profile_id=? AND faellig_am IS NULL",
            (pid,),
        ).fetchone()[0]
        assert min(heute, ueberfaellig, zukunft, ohne) >= 1, (
            f"{pid}: heute={heute} ueberfaellig={ueberfaellig} zukunft={zukunft} ohne={ohne}"
        )


def test_seed_daten_enthalten_nur_fiktive_firmen(geseedet):
    """Der PII-Pruefer darf im Seed-Modul keine Firmen-Treffer melden."""
    import scrub_pii
    importlib.reload(scrub_pii)
    quelle = (SCREENSHOT_DIR / "musterprofile.py").read_text(encoding="utf-8")
    # v1.7.16: Der Filter prueste frueher `h[0] == "CORP"` — das ist das
    # erste ZEICHEN ("C"), nie der Praefix. Der Test war damit wirkungslos
    # und meldete auch bei echten Funden nichts. Jetzt startswith, und
    # zusaetzlich PHONE/EMAIL, denn Musterdaten duerfen auch keine
    # Kontaktdaten enthalten.
    hits = [h for h in scrub_pii.find_pii(quelle)
            if h.startswith(("CORP", "PHONE", "EMAIL", "PERSON", "USER"))]
    assert hits == [], f"Reale Muster im Seed: {hits}"


def test_quellen_keys_sind_die_einzige_firma_ausnahme():
    """Die einzigen FIRMA-Treffer im Seed duerfen Jobportale sein — sie
    stehen dort als Quellen-Schluessel (Produktfunktion, kein
    Bewerbungsverhaeltnis; dokumentierte Ausnahme aus DoD-9)."""
    import scrub_pii
    importlib.reload(scrub_pii)
    quelle = (SCREENSHOT_DIR / "musterprofile.py").read_text(encoding="utf-8")
    firmen = {h.split(": ", 1)[1].lower()
              for h in scrub_pii.find_pii(quelle) if h.startswith("FIRMA")}
    erlaubt = {"hays"}  # als active_sources-Eintrag und Quellen-Spalte
    assert firmen <= erlaubt, f"Unerwartete Firmen im Seed: {firmen - erlaubt}"


def test_interview_reflexionen_vorhanden(geseedet):
    db, pids = geseedet
    for pid in pids.values():
        assert _count(
            db,
            "SELECT COUNT(*) FROM interview_reflections WHERE profile_id=?",
            pid,
        ) >= 2
