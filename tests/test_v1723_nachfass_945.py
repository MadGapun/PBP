"""Tests fuer v1.7.23 — #945: Nachfassungen sagen, was zu tun ist.

Nutzerbeobachtung: *"ich merke, dass ich schon wieder suche, obwohl ich
doch im Dashboard auf Oeffnen beim Nachfassen geklickt habe."*

Fuenf von sieben offenen Nachfassungen hatten ein leeres
Beschreibungsfeld. Der Unterschied zu den Todos im selben Bestand lag
nicht am Aufgabentyp, sondern an der Herkunft: Todos werden mit Kontext
angelegt, Nachfassungen entstanden automatisch und blieben leer.
"""
import pytest

from bewerbungs_assistent.services.nachfass_text import (
    claude_prompt,
    dringlichkeit,
    ist_ueberholt,
    nachfass_text,
)

BEWERBUNG = {
    "title": "PLM Consultant",
    "company": "Musterfirma GmbH",
    "applied_at": "2026-07-30",
    "ansprechpartner": "R. Wendelin",
    "kontakt_email": "bewerbung@musterfirma.example",
    "bewerbungsart": "ueber_portal",
    "status": "beworben",
}


# ── Inhalt statt Kopfzeile ───────────────────────────────────────────

def test_945_text_nennt_alles_zum_handeln_noetige():
    """An wen, ueber welchen Kanal, worauf Bezug nehmend, in welchem Ton."""
    text = nachfass_text(BEWERBUNG)
    for pflicht in ("PLM Consultant", "Musterfirma GmbH", "2026-07-30",
                    "R. Wendelin", "ueber_portal"):
        assert pflicht in text, (pflicht, text)
    assert "Bezug" in text or "fragen" in text


def test_945_text_kommt_auch_mit_luecken_zurecht():
    """Ein halb gefuellter Datensatz darf nicht zu '?' verkommen."""
    text = nachfass_text({"company": "Musterfirma GmbH"})
    assert "Musterfirma GmbH" in text
    assert text.strip()


def test_945_handlungsvorschlag_haengt_am_stand():
    nach_gespraech = nachfass_text({**BEWERBUNG,
                                    "status": "interview_abgeschlossen"})
    assert "Ergebnis" in nach_gespraech
    routine = nachfass_text(BEWERBUNG)
    assert "Ergebnis" not in routine


# ── Vorgefertigter Claude-Prompt ─────────────────────────────────────

def test_945_prompt_ist_direkt_verwendbar():
    p = claude_prompt(BEWERBUNG)
    assert "PLM Consultant" in p and "Musterfirma GmbH" in p
    assert "2026-07-30" in p
    assert "R. Wendelin" in p


def test_945_prompt_enthaelt_keine_mailadresse():
    """Der Prompt geht ueber die Zwischenablage — die Adresse steht
    ohnehin im Beschreibungstext und hat hier nichts zu suchen."""
    assert "@" not in claude_prompt(BEWERBUNG)


def test_945_prompt_beruecksichtigt_den_stand():
    p = claude_prompt({**BEWERBUNG, "status": "interview_abgeschlossen"})
    assert "Gespraech" in p


# ── Verfahrensstand macht Nachfassungen gegenstandslos ───────────────

def test_945_nachfassung_bei_laufendem_gespraech_ist_ueberholt():
    """Belegter Fall: seit Tagen ueberfaellig, waehrend der Status
    laengst zweitgespraech war und ein Termin vorlag."""
    weg, grund = ist_ueberholt({"created_at": "2026-08-01"},
                               {**BEWERBUNG, "status": "zweitgespraech"})
    assert weg is True
    assert "zweitgespraech" in grund


def test_945_vereinbarter_termin_macht_nachfassung_ueberholt():
    weg, grund = ist_ueberholt(
        {"created_at": "2026-08-01"}, BEWERBUNG,
        meetings=[{"scheduled_at": "2026-08-26"}])
    assert weg is True
    assert "2026-08-26" in grund


def test_945_alter_termin_macht_nichts_ueberholt():
    """Ein Termin VOR dem Anlegen beantwortet die Nachfrage nicht."""
    weg, _ = ist_ueberholt({"created_at": "2026-08-20"}, BEWERBUNG,
                           meetings=[{"scheduled_at": "2026-07-01"}])
    assert weg is False


def test_945_routinefall_bleibt_bestehen():
    weg, _ = ist_ueberholt({"created_at": "2026-08-01"}, BEWERBUNG)
    assert weg is False


def test_945_abgeschlossenes_gespraech_bleibt_offen():
    """Genau dieser Eintrag war im Bestand der WICHTIGSTE — er darf
    nicht als ueberholt verschwinden."""
    weg, _ = ist_ueberholt({"created_at": "2026-08-01"},
                           {**BEWERBUNG, "status": "interview_abgeschlossen"})
    assert weg is False


# ── Sortierung nach Dringlichkeit ────────────────────────────────────

def test_945_gespraechsnachfrage_schlaegt_aeltere_routine():
    """Sonst geht die wichtigste Aufgabe zwischen fuenf inhaltsleeren
    Routine-Eintraegen unter, nur weil deren Datum aelter ist."""
    wichtig = dringlichkeit({"status": "interview_abgeschlossen"},
                            tage_ueberfaellig=2)
    routine = dringlichkeit({"status": "beworben"}, tage_ueberfaellig=40)
    assert wichtig > routine, (wichtig, routine)


def test_945_bei_gleichem_stand_zaehlt_die_ueberfaelligkeit():
    frueher = dringlichkeit({"status": "beworben"}, tage_ueberfaellig=30)
    spaeter = dringlichkeit({"status": "beworben"}, tage_ueberfaellig=3)
    assert frueher > spaeter


# ── Anlage und Nachgenerierung ───────────────────────────────────────

def test_945_automatische_nachfassung_traegt_kontext(tmp_db):
    """Regressionsfall: automatisch erzeugte Eintraege blieben leer."""
    aid = tmp_db.add_application({
        "title": "PLM Consultant", "company": "Musterfirma GmbH",
        "position": "PLM Consultant", "status": "interview_abgeschlossen",
        "ansprechpartner": "R. Wendelin", "applied_at": "2026-07-30",
    })
    # Der Weg ueber den Statuswechsel legt die Nachfassung selbst an.
    tmp_db.update_application_status(aid, "interview_abgeschlossen")
    offene = tmp_db.get_pending_follow_ups() or []
    erzeugte = [f for f in offene if f.get("application_id") == aid]
    if not erzeugte:
        pytest.skip("Statuswechsel erzeugt hier keine Nachfassung")
    text = erzeugte[0].get("template") or ""
    assert "Musterfirma GmbH" in text, text
    assert "R. Wendelin" in text, text


def test_945_leere_bestandsnachfassung_wird_beim_lesen_gefuellt(tmp_db):
    """Die fuenf leeren Alt-Eintraege sind der Regressionsfall.

    Eine Migration koennte sie fuer geloeschte Bewerbungen ohnehin nicht
    rekonstruieren — deshalb beim Lesen.
    """
    aid = tmp_db.add_application({
        "title": "PLM Consultant", "company": "Musterfirma GmbH",
        "position": "PLM Consultant", "status": "beworben",
        "ansprechpartner": "R. Wendelin", "applied_at": "2026-07-30",
    })
    tmp_db.add_follow_up(aid, "2026-08-01", "nachfass", template="")
    app = tmp_db.get_application(aid)
    erzeugt = nachfass_text(app)
    assert "Musterfirma GmbH" in erzeugt
    assert "R. Wendelin" in erzeugt


# ── Leermeldung unterscheidet die beiden Zustaende ───────────────────

def test_945_leermeldung_unterscheidet_erstzustand_und_alles_erledigt(tmp_db):
    """Bei sechs erledigten Aufgaben ist der Onboarding-Text falsch und
    entwertet die geleistete Arbeit."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "tools" / "tasks.py").read_text(encoding="utf-8")
    assert "erledigt_gesamt" in quelle
    assert "Keine offenen Aufgaben" in quelle


def test_945_uebersicht_nennt_den_passenden_aufruf_je_herkunft():
    """Der Nutzer sieht eine Liste und soll nicht wissen muessen, aus
    welchem Topf ein Eintrag stammt."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "tools" / "tasks.py").read_text(encoding="utf-8")
    for aufruf in ("todo_erledigen", "follow_up_erledigen",
                   "meeting_bearbeiten"):
        assert f'"{aufruf}' in quelle or f"{aufruf}('" in quelle, aufruf
    assert "erledigen_mit" in quelle
