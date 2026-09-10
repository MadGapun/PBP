"""Tests fuer #957 Stufe 1 — der Report ueber die Notiz-Drift.

`bewerbung_erstellen` schreibt die Notiz an ZWEI Orte (Feld und
Timeline, #224); `bewerbung_bearbeiten(notes=...)` aendert danach nur
das Feld. Das Issue verlangt ausdruecklich **erst einen Report, dann
die Entscheidung** — weil bei zwei abweichenden Fassungen die Frage,
welche gilt, eine inhaltliche ist.

Diese Tests halten die drei Eigenschaften fest, die den Report
brauchbar machen: er zaehlt richtig, er schreibt nichts, und er gibt
keine Notiztexte heraus.
"""
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad — der Test muss auch aus einem fremden
    Arbeitsverzeichnis laufen (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import notiz_drift  # noqa: E402


# ----------------------------------------------------------- Einordnung


def test_957_identische_fassungen_sind_eine_harmlose_dublette():
    assert notiz_drift.einordnen("Hallo", ["Hallo"]) == notiz_drift.IDENTISCH


def test_957_abweichende_fassungen_sind_der_teure_fall():
    assert notiz_drift.einordnen(
        "Neue Fassung", ["Alte Fassung"]) == notiz_drift.ABWEICHEND


def test_957_nur_eine_seite_gefuellt():
    assert notiz_drift.einordnen("nur Feld", []) == notiz_drift.NUR_FELD
    assert notiz_drift.einordnen("", ["nur Timeline"]) == notiz_drift.NUR_TIMELINE


def test_957_ohne_notiz_gibt_es_nichts_zu_entscheiden():
    """Solche Bewerbungen tauchen im Bericht gar nicht auf."""
    assert notiz_drift.einordnen("", []) is None
    assert notiz_drift.einordnen(None, [None]) is None


def test_957_leerraum_ist_keine_drift():
    """Ein Zeilenumbruch mehr stammt aus der Eingabemaske, nicht aus
    einer Pflege.

    Wuerde er als `abweichend` zaehlen, waere genau die Zahl zu hoch,
    auf die sich die Entscheidung stuetzen soll.
    """
    assert notiz_drift.einordnen(
        "Zeile eins\n\nZeile zwei",
        ["Zeile eins\nZeile zwei  "]) == notiz_drift.IDENTISCH


def test_957_nur_der_erste_timeline_eintrag_zaehlt():
    """Spaetere Notizen sind der SAUBERE Weg (`bewerbung_notiz`).

    Sie mit dem Feld zu vergleichen wuerde eine Drift behaupten, wo
    jemand schlicht etwas ergaenzt hat — der Report wuerde dann den
    korrekten Weg als Fehler zaehlen.
    """
    assert notiz_drift.einordnen(
        "Anlagetext",
        ["Anlagetext", "Spaeter ergaenzt", "Und noch was"],
    ) == notiz_drift.IDENTISCH


# --------------------------------------------------------------- Bericht


class _DB:
    """Kleinste Datenbank, die der Bericht braucht."""

    def __init__(self, bewerbungen: list, events: dict):
        self._bewerbungen = bewerbungen
        self._events = events
        self.schreibzugriffe = 0

    def connect(self):
        return self

    def execute(self, sql, args=()):
        if "FROM applications" in sql:
            return _Ergebnis([
                {"id": b[0], "notes": b[1]} for b in self._bewerbungen])
        if "FROM application_events" in sql:
            return _Ergebnis([
                {"notes": n} for n in self._events.get(args[0], [])])
        self.schreibzugriffe += 1          # alles andere waere ein Write
        return _Ergebnis([])


class _Ergebnis:
    def __init__(self, zeilen):
        self._zeilen = zeilen

    def fetchall(self):
        return self._zeilen

    def fetchone(self):
        return self._zeilen[0] if self._zeilen else None


# Die Notiztexte sind bewusst UNAUSSPRECHLICH: der Leck-Test sucht sie
# im ganzen Bericht, und ein Alltagswort wuerde dort zufaellig in der
# Erklaerprosa auftauchen. Der erste Entwurf nahm "gleich" — das steckt
# in "wortgleich" und liess den Test fehlschlagen, ohne dass etwas leckt.
# Dieselbe Lehre wie bei #1012: Testdaten muessen wirklich unverwandt
# sein, sonst prueft der Test etwas anderes als gemeint.
_ZWILLING = "Notiztext-Zwilling-Qx7"
_ALT = "Notiztext-Alt-Qx7"
_NEU = "Notiztext-Neu-Qx7"
_NUR_FELD = "Notiztext-NurFeld-Qx7"
_NUR_TL = "Notiztext-NurTimeline-Qx7"

_GEHEIM = (_ZWILLING, _ALT, _NEU, _NUR_FELD, _NUR_TL)


def _beispiel_db():
    return _DB(
        bewerbungen=[
            ("a1", _ZWILLING),
            ("a2", _NEU),
            ("a3", _NUR_FELD),
            ("a4", ""),
            ("a5", ""),
        ],
        events={
            "a1": [_ZWILLING],
            "a2": [_ALT],
            "a3": [],
            "a4": [_NUR_TL],
            "a5": [],
        },
    )


def test_957_der_bericht_zaehlt_die_faelle():
    """Nachgezogen mit Stufe 2: es sind fuenf Faelle statt vier.

    `zusammengefuehrt` kam dazu, weil der Report sonst nach der
    Zusammenfuehrung weiter `abweichend` gemeldet haette — technisch
    richtig (die Texte sind verschieden), in der Sache falsch: beide
    Fassungen liegen dann an einem Ort. Ein Pruefer, der bei korrektem
    Zustand Alarm gibt, wird ignoriert (#929).

    Die Zusicherung dieses Tests ist unveraendert: der Bericht zaehlt
    jeden Fall genau einmal.
    """
    b = notiz_drift.bericht(_beispiel_db())
    assert b["bewerbungen_gesamt"] == 5
    assert b["mit_notiz"] == 4          # a5 hat nichts
    assert b["faelle"] == {
        notiz_drift.IDENTISCH: 1,
        notiz_drift.ABWEICHEND: 1,
        notiz_drift.ZUSAMMENGEFUEHRT: 0,
        notiz_drift.NUR_FELD: 1,
        notiz_drift.NUR_TIMELINE: 1,
    }


def test_957_der_bericht_schreibt_nichts():
    """Akzeptanzkriterium des Issues, woertlich."""
    db = _beispiel_db()
    notiz_drift.bericht(db)
    assert db.schreibzugriffe == 0


def test_957_der_bericht_gibt_keine_notiztexte_heraus():
    """Eine Notiz ist das Privateste im Bestand.

    Der Bericht nennt die Kennung und die Groessenordnung — sonst
    stuende der Inhalt einer Bewerbungsnotiz in einer Diagnose-Antwort,
    und die wandert im Zweifel in einen Fehlerbericht.
    """
    b = notiz_drift.bericht(_beispiel_db())
    roh = repr(b)
    for text in _GEHEIM:
        assert text not in roh, f"Notiztext {text!r} steht im Bericht."
    assert b["beispiele_abweichend"][0]["bewerbung_id"] == "a2"


def test_957_der_hinweis_deutet_die_zahl():
    """Eine Kennzahl ohne Deutung ist der halbe Befund (#989)."""
    mit_drift = notiz_drift.bericht(_beispiel_db())["hinweis"]
    assert "inhaltliche Entscheidung" in mit_drift

    ohne_drift = notiz_drift.bericht(_DB(
        bewerbungen=[("a1", _ZWILLING)],
        events={"a1": [_ZWILLING]}))["hinweis"]
    assert "KEINE Drift" in ohne_drift


def test_957_ein_defekter_zugriff_kippt_den_bericht_nicht():
    class _Kaputt:
        def connect(self):
            raise RuntimeError("Datenbank weg")

    assert "fehler" in notiz_drift.bericht(_Kaputt())


def test_957_das_werkzeug_ist_registriert_und_liest_nur():
    """DoD 8c: ein Bericht zaehlt erst, wenn er auch aufrufbar ist."""
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "tools"
              / "bewerbungen.py").read_text(encoding="utf-8")
    assert "def bewerbung_notiz_drift()" in quelle
    block = quelle.split("def bewerbung_notiz_drift()")[1].split("@mcp.tool()")[0]
    assert "notiz_drift.bericht(db)" in block
    for verboten in ("db.update", "INSERT", "UPDATE", "DELETE"):
        assert verboten not in block, (
            f"Das Werkzeug enthaelt {verboten!r} — es soll nur lesen.")


# ======================================================================
# #956 — Recherche liegt an EINEM Ort
# ======================================================================


def test_956_protokoll_wird_von_recherche_unterschieden():
    """Die Trennung, an der die ganze Migration haengt.

    Gemessen am 10.09.2026: von 143 gefuellten Spalten tragen 30 ein
    Aussortier-Protokoll statt einer Recherche. Alles in einen Topf zu
    schieben waere kein Aufraeumen, sondern eine zweite Verwechslung.
    """
    from bewerbungs_assistent.services import recherche_ablage as ra

    assert ra.ist_protokoll("[Auto-Aussortierung] falsches_fachgebiet")
    assert ra.ist_protokoll(
        "[2026-09-10] Recruiter-Anfrage abgelehnt. Grund: standort.")
    assert not ra.ist_protokoll(
        "Das Unternehmen baut seit zwei Jahren ein PLM-Team auf.")
    assert not ra.ist_protokoll("")


def test_956_der_schreibkasten_haengt_an_der_bewerbung():
    """44 von 99 Bewerbungen haben keine Stelle (#986).

    Solange die Karte an `entry?.job` hing, war der Eingabeweg fuer
    fast die Haelfte des Bestands unsichtbar.
    """
    quelle = (_repo() / "frontend" / "src" / "pages"
              / "ApplicationsPage.jsx").read_text(encoding="utf-8")
    assert "{timelineDialog.entry?.application ? (" in quelle
    # Und der Entwurf wird nicht mehr aus der alten Spalte vorbefuellt.
    assert "job?.research_notes" not in quelle


def test_956_kein_schreibweg_mehr_auf_die_alte_spalte():
    """AK 3 des Issues, als Guard statt als Vorsatz.

    Der Guard zaehlt keine Fundstellen ab, er verbietet die Bauform —
    eine Zaehlung haette die fuenfte durchgelassen. (Das Issue nannte
    drei Schreibwege; es waren vier.)
    """
    import re

    for datei in ("src/bewerbungs_assistent/tools/jobs.py",
                  "src/bewerbungs_assistent/tools/bewerbungen.py",
                  "src/bewerbungs_assistent/dashboard.py"):
        quelle = (_repo() / datei).read_text(encoding="utf-8")
        code = "\n".join(z for z in quelle.split("\n")
                         if not z.strip().startswith("#"))
        assert not re.search(r'"research_notes"\s*:', code), (
            f"{datei} schreibt wieder in die Spalte jobs.research_notes.")


class _MigrationsDB:
    """Genug Datenbank fuer den Migrationslauf."""

    def __init__(self, zeilen):
        self.zeilen = zeilen
        self.geschrieben = []
        self.notizen = []

    def connect(self):
        return self

    def execute(self, sql, args=()):
        if "FROM jobs WHERE research_notes" in sql:
            return _Ergebnis([dict(z) for z in self.zeilen
                              if (z["research_notes"] or "").strip()])
        if sql.startswith("UPDATE jobs SET dismiss_note"):
            self.geschrieben.append(("dismiss_note", args[1]))
            for z in self.zeilen:
                if z["hash"] == args[1]:
                    z["dismiss_note"] = args[0]
            return _Ergebnis([])
        if "FROM applications" in sql:
            return _Ergebnis([])
        return _Ergebnis([])

    def commit(self):
        pass

    def add_research_note(self, **kwargs):
        self.notizen.append(kwargs)
        return len(self.notizen)

    def update_job(self, job_hash, felder):
        self.geschrieben.append(("update_job", job_hash))
        for z in self.zeilen:
            if z["hash"] == job_hash:
                z.update(felder)


def _migrations_db():
    return _MigrationsDB([
        {"hash": "p1:aaa", "research_notes": "Firma baut ein Team auf.",
         "dismiss_note": "", "is_active": 1},
        {"hash": "p1:bbb",
         "research_notes": "[Auto-Aussortierung] falsches_fachgebiet",
         "dismiss_note": "", "is_active": 0},
    ])


def test_956_die_vorgabe_ist_zaehlen_nicht_verschieben():
    """Ein Lauf, der ungefragt 143 Datensaetze umschreibt, ist keine
    Migration, sondern eine Ueberraschung."""
    from bewerbungs_assistent.services import recherche_migration as rm

    db = _migrations_db()
    ergebnis = rm.zusammenfuehren(db)
    assert ergebnis["status"] == "vorschau"
    assert ergebnis["kandidaten"] == 2
    assert ergebnis["recherche"] == 1 and ergebnis["protokoll"] == 1
    assert db.geschrieben == [] and db.notizen == []


def test_956_der_echte_lauf_trennt_die_beiden_sorten():
    from bewerbungs_assistent.services import recherche_migration as rm

    db = _migrations_db()
    ergebnis = rm.zusammenfuehren(db, dry_run=False)
    assert ergebnis["status"] == "verschoben"
    assert ergebnis["recherche"] == 1 and ergebnis["protokoll"] == 1
    # Die Recherche liegt in der Tabelle ...
    assert [n["text"] for n in db.notizen] == ["Firma baut ein Team auf."]
    assert db.notizen[0]["kategorie"] == "firmenrecherche"
    # ... das Protokoll in dismiss_note.
    assert ("dismiss_note", "p1:bbb") in db.geschrieben


def test_956_der_zweite_lauf_findet_nichts_mehr():
    """Idempotent — und zwar durch Leeren, ohne zweite Wahrheit."""
    from bewerbungs_assistent.services import recherche_migration as rm

    db = _migrations_db()
    rm.zusammenfuehren(db, dry_run=False)
    zweiter = rm.zusammenfuehren(db, dry_run=False)
    assert zweiter["kandidaten"] == 0


def test_956_die_migration_sortiert_nichts_aus():
    """Eine Migration ordnet ein, sie entscheidet nicht.

    Ein `dismiss_job` haette `is_active` auf 0 gesetzt — eine Stelle,
    die aus welchem Grund auch immer wieder aktiv ist, waere danach
    still wieder aussortiert.
    """
    from bewerbungs_assistent.services import recherche_migration as rm

    db = _MigrationsDB([
        {"hash": "p1:ccc",
         "research_notes": "[Auto-Aussortierung] alter Vermerk",
         "dismiss_note": "", "is_active": 1},
    ])
    rm.zusammenfuehren(db, dry_run=False)
    assert db.zeilen[0]["is_active"] == 1


def test_956_die_stichprobe_traegt_keine_notizinhalte():
    """Eine Recherche-Notiz kann alles enthalten, auch einen Namen."""
    from bewerbungs_assistent.services import recherche_migration as rm

    ergebnis = rm.zusammenfuehren(_migrations_db())
    assert "Firma baut ein Team auf." not in repr(ergebnis["stichprobe"])
    assert ergebnis["stichprobe"][0]["art"] in ("recherche", "protokoll")
