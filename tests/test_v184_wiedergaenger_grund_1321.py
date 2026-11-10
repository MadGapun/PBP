"""#1321: eine Aussortierung durch die Wiedergaenger-Pruefung behaelt ihren Grund.

Bis 1.8.3 schrieb `stelle_wiedergaenger_pruefen(..., auto_aussortieren=True)`
den Wert 'wiedergaenger:<grund>'. Die Normalisierung in `dismiss_job` kannte die
Vorsilbe nicht und machte schon beim SPEICHERN 'sonstiges' daraus (das Original
landete in der Notiz). Statistik, Lerneffekt und spaetere Wiedergaenger-Muster
sahen 'sonstiges' statt des fachlichen Grundes.

Testdaten fiktiv.
"""
from __future__ import annotations

import logging

from bewerbungs_assistent.services.ablehnungsgruende import (
    normalisiere_dismiss_wert)


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name=None, **_kwargs):
        def decorator(fn):
            self.tools[name or fn.__name__] = fn
            return fn
        return decorator


BESCHREIBUNG = (
    "Aufgaben: Betreuung und Weiterentwicklung der PLM-Landschaft, Abstimmung "
    "mit Fachbereichen, Steuerung externer Dienstleister, Migration bestehender "
    "Strukturen. Anforderungen: abgeschlossenes Studium, mehrjaehrige "
    "Berufserfahrung, sichere Kommunikation in Deutsch und Englisch.")


def _stelle(db, kurz, titel, grund=None):
    pid = db.get_active_profile_id() or ""
    voll = f"{pid}:{kurz}"
    db.save_jobs([{
        "hash": voll, "title": titel, "company": "Musterfirma GmbH",
        "location": "Hamburg", "url": f"https://example.com/{kurz}",
        "source": "manuell", "score": 50, "description": f"{titel}. {BESCHREIBUNG}",
    }])
    if grund:
        db.dismiss_job(voll, grund)
    return voll


def _neu_oeffnen(db):
    from bewerbungs_assistent.database import Database
    pfad = db.db_path
    db.close()
    neu = Database(db_path=pfad)
    neu.initialize()
    return neu


# ── Normalisierung ────────────────────────────────────────────────────────

def test_vorsilbe_wird_zum_grund():
    assert normalisiere_dismiss_wert("wiedergaenger:falsches_fachgebiet") == (
        "falsches_fachgebiet", [])
    assert normalisiere_dismiss_wert("Wiedergaenger:Zu_Junior") == ("zu_junior", [])


def test_vorsilbe_in_der_liste():
    wert, texte = normalisiere_dismiss_wert(
        '["wiedergaenger:befristet", "zu_weit_entfernt"]')
    assert wert == '["befristet", "zu_weit_entfernt"]'
    assert texte == []


def test_unbekannter_kern_bleibt_sonstiges_mit_original():
    assert normalisiere_dismiss_wert("wiedergaenger:frei_erfunden") == (
        "sonstiges", ["wiedergaenger:frei_erfunden"])


def test_eigener_grund_als_kern():
    assert normalisiere_dismiss_wert(
        "wiedergaenger:mein_grund", {"mein_grund"}) == ("mein_grund", [])


# ── Werkzeug, Speichern und Neustart ──────────────────────────────────────

def test_aussortieren_ueber_die_pruefung_behaelt_den_grund(tmp_db, tmp_path):
    assert str(tmp_path) in str(tmp_db.db_path), f"DB nicht isoliert: {tmp_db.db_path}"
    tmp_db.create_profile("Erika Musterfrau", "test@example.com")
    _stelle(tmp_db, "aaa1", "PLM Manager", "falsches_fachgebiet")
    _stelle(tmp_db, "bbb2", "PLM Owner", "falsches_fachgebiet")
    neu = _stelle(tmp_db, "ccc3", "PLM Architect (m/w/d)")

    from bewerbungs_assistent.tools.jobs import register
    mcp = _FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    erg = mcp.tools["stelle_wiedergaenger_pruefen"](job_hash=neu, auto_aussortieren=True)
    assert erg["aktion"] == "auto_aussortiert"
    assert erg["dismiss_reason"] == "falsches_fachgebiet"

    job = tmp_db.get_job(neu)
    assert job["dismiss_reason"] == "falsches_fachgebiet"
    assert job["dismissed_by"] == "automatik"
    assert "Wiedergänger-Prüfung" in (job["dismiss_note"] or "")

    # Neustart: die Bestandsheilung laesst den Grund stehen.
    db2 = _neu_oeffnen(tmp_db)
    try:
        assert db2.get_job(neu)["dismiss_reason"] == "falsches_fachgebiet"
    finally:
        db2.close()


# ── Bestand aus 1.8.3 und frueher ─────────────────────────────────────────

def test_bestand_sonstiges_kommt_aus_der_notiz_zurueck(tmp_db, tmp_path):
    assert str(tmp_path) in str(tmp_db.db_path), f"DB nicht isoliert: {tmp_db.db_path}"
    tmp_db.create_profile("Erika Musterfrau", "test@example.com")
    a = _stelle(tmp_db, "ddd4", "Konstrukteur", "sonstiges")
    b = _stelle(tmp_db, "eee5", "Planer", "sonstiges")
    c = _stelle(tmp_db, "fff6", "Techniker", "sonstiges")
    conn = tmp_db.connect()
    # So sah der Bestand nach dem Fehler aus (isolierte Test-DB).
    for h, notiz in ((a, "wiedergaenger:zu_junior"),
                     (b, "wiedergaenger:frei_erfunden"),
                     (c, "Wiedergaenger aus Freitext")):
        conn.execute("UPDATE jobs SET dismiss_note=? WHERE hash=?", (notiz, h))
    conn.commit()

    db2 = _neu_oeffnen(tmp_db)
    assert db2.get_job(a)["dismiss_reason"] == "zu_junior"
    assert db2.get_job(a)["dismiss_note"] == "wiedergaenger:zu_junior"
    assert db2.get_job(b)["dismiss_reason"] == "sonstiges"
    assert db2.get_job(c)["dismiss_reason"] == "sonstiges"
    # Zweiter Start: nichts aendert sich mehr.
    db3 = _neu_oeffnen(db2)
    try:
        assert db3.get_job(a)["dismiss_reason"] == "zu_junior"
    finally:
        db3.close()
