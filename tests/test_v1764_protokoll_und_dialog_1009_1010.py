"""Tests fuer v1.7.64 — #1009 und #1010, beide Nutzerwuensche vom 09.09.2026.

**#1009:** *"Es wuerde glaube ich Sinn machen, bei der Fit-Analyse
zusaetzlich unten den 'Passt nicht'-Knopf zu haben."* Der Dialog endete
mit den Risiken und der Claude-Analyse — ohne jede Handlungsmoeglichkeit.
Wer die Analyse gelesen hat, hat GENAU DANN sein Urteil gebildet und
musste dafuer den Dialog schliessen und die Karte wiederfinden. Der
teuerste Schritt endete in einer Sackgasse.

**#1010:** *"Ausserdem waere ein 'Log', welche man manuell aussortiert
hat (sowie die automatisch aussortierten, ggf. oder besser in
Kombination) hilfreich, damit man, wenn man sich mal verklickt hat, diese
auch zurueckholen kann."* Rueckholen ging schon; was fehlte, war das
Wiederfinden — kein Zeitpunkt, keine unterscheidbare Herkunft, kein
Zeitfenster.

Zwei Entscheidungen, die diese Tests festhalten:

* **Der Altbestand bekommt kein Datum.** `updated_at` als Ersatz waere
  eine erfundene Angabe (#987) — die Spalte fasst jede
  Score-Neuberechnung an.
* **Die Herkunft wird nicht geraten.** `duplikat` setzt sowohl die
  Automatik (#641) als auch der Mensch, und das `auto:`-Praefix
  ueberlebt die Normalisierung aus #913 bewusst nicht. Ohne Beleg heisst
  es `unbekannt` — nicht "war ich" (#989).
"""
import importlib
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad — der Test muss auch aus einem fremden
    Arbeitsverzeichnis laufen (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

JOBS_PAGE = _repo() / "frontend" / "src" / "pages" / "JobsPage.jsx"


def ohne_kommentare(text: str) -> str:
    """Kommentare raus — sonst schlaegt ein Guard an der Begruendung an."""
    ohne_block = re.sub(r"/\*[\s\S]*?\*/", "", text)
    return "\n".join(
        re.sub(r"(^|\s)//.*$", "", z) for z in ohne_block.split("\n"))


@pytest.fixture
def db(tmp_path):
    """QA-Isolation (HART): eigenes Temp-Verzeichnis, hart geprueft."""
    alt = os.environ.get("BA_DATA_DIR")
    os.environ["BA_DATA_DIR"] = str(tmp_path / "daten")
    from bewerbungs_assistent import database as _database
    importlib.reload(_database)
    datenbank = _database.Database()
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.save_profile({"name": "Muster Person"})
    try:
        yield datenbank
    finally:
        if alt is None:
            os.environ.pop("BA_DATA_DIR", None)
        else:
            os.environ["BA_DATA_DIR"] = alt


def _werkzeug(db, name):
    from bewerbungs_assistent.tools import jobs as job_tools

    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

    job_tools.register(_Sammler(), db, logging.getLogger("test"))
    return gesammelt[name]


def _stellen(db, anzahl=4):
    db.save_jobs([{
        "hash": f"prot{i:03d}",
        "title": f"Consultant {i} (m/w/d)",
        "company": f"Musterwerk {i} GmbH",
        "location": "Hamburg", "score": 12,
        "url": f"https://example.org/stelle/{i}",
        "source": "manuell",
        "description": "Eine ausfuehrliche Stellenbeschreibung. " * 8,
    } for i in range(anzahl)])


def _eintrag(befund, hash_teil):
    return next(e for e in befund["eintraege"] if e["hash"].endswith(hash_teil))


# -- #1010: der Zeitpunkt ---------------------------------------------

def test_1010_aussortieren_setzt_den_zeitpunkt(db):
    """Der Kern: ohne Zeitpunkt findet man den Verklicker nicht wieder."""
    _stellen(db, 2)
    db.dismiss_job("prot000", "falsches_fachgebiet")

    row = next(j for j in db.get_dismissed_jobs()
               if j["hash"].endswith("prot000"))
    assert row["dismissed_at"], "Kein Zeitpunkt gesetzt."
    assert row["dismissed_by"] == "ich"


def test_1010_zurueckholen_raeumt_den_zeitpunkt_ab(db):
    """Eine zurueckgeholte Stelle ist nicht aussortiert.

    Bliebe das Datum stehen, fuehrte das Protokoll sie weiter — mit
    einem Zeitpunkt, der nichts mehr beschreibt.
    """
    _stellen(db, 2)
    db.dismiss_job("prot000", "zeitarbeit")
    db.restore_job("prot000")

    row = next(j for j in db.get_active_jobs()
               if j["hash"].endswith("prot000"))
    assert not row["dismissed_at"]
    assert not row["dismissed_by"]


def test_1010_die_automatik_wird_beim_anlegen_markiert(db):
    """`save_jobs` sortiert selbst aus — Wiedergaenger, Duplikat, Ort.

    Der Kommentar zu #913 nennt `dismiss_job` das Nadeloehr ALLER
    dismiss-Writes; fuer den ANLEGE-Weg stimmt das nicht. Ohne diesen
    Zweig traegt ausgerechnet die Automatik keine Herkunft — waehrend
    das Protokoll sie ausweisen soll.
    """
    db.save_jobs([{
        "hash": "protauto", "title": "Consultant (m/w/d)",
        "company": "Musterwerk Nord GmbH", "location": "Hamburg",
        "score": 5, "url": "https://example.org/auto", "source": "manuell",
        "description": "Beschreibung. " * 10,
        "is_active": 0, "dismiss_reason": "auto:falsches_fachgebiet",
    }])
    row = next(j for j in db.get_dismissed_jobs()
               if j["hash"].endswith("protauto"))
    assert row["dismissed_by"] == "automatik"
    assert row["dismissed_at"], "Auch die Automatik braucht einen Zeitpunkt."


def test_1010_erneuter_ingest_verschiebt_den_zeitpunkt_nicht(db):
    """Ein Suchlauf schreibt die Zeile neu — er sortiert nichts neu aus.

    Ohne diese Regel wanderte jede aussortierte Stelle bei jedem Lauf
    wieder an die Spitze des Protokolls; genau die Unbrauchbarkeit, die
    `updated_at` schon hatte.
    """
    _stellen(db, 2)
    db.dismiss_job("prot000", "zeitarbeit")
    vorher = next(j for j in db.get_dismissed_jobs()
                  if j["hash"].endswith("prot000"))["dismissed_at"]

    _stellen(db, 2)  # derselbe Hash, erneut gespeichert
    nachher = next(j for j in db.get_dismissed_jobs()
                   if j["hash"].endswith("prot000"))["dismissed_at"]
    assert nachher == vorher


# -- #1010: das Protokoll ---------------------------------------------

def test_1010_protokoll_zeigt_beide_herkuenfte_in_einer_liste(db):
    """Der Nutzer hat beides zusammen verlangt — mit Unterscheidung."""
    from bewerbungs_assistent.services import aussortier_protokoll as ap
    _stellen(db, 3)
    db.dismiss_job("prot000", "falsches_fachgebiet")
    db.dismiss_job("prot001", "auto:profil_match_negativ:kein Bezug",
                   herkunft="automatik")

    befund = ap.eintraege(db, zeitfenster="heute")
    assert befund["anzahl"] == 2
    assert _eintrag(befund, "prot000")["herkunft"] == "ich"
    assert _eintrag(befund, "prot001")["herkunft"] == "automatik"


def test_1010_altbestand_bleibt_ohne_zeitpunkt_und_wird_gezaehlt(db):
    """Zwei Regeln auf einmal.

    Ein Eintrag ohne Datum laesst sich nicht einordnen — er darf weder
    still in "heute" auftauchen noch spurlos verschwinden. Beides waere
    eine Aussage, die die Daten nicht hergeben (#987, #989).
    """
    from bewerbungs_assistent.services import aussortier_protokoll as ap
    _stellen(db, 2)
    db.dismiss_job("prot000", "sonstiges")
    conn = db.connect()
    conn.execute("UPDATE jobs SET dismissed_at=NULL, dismissed_by=NULL "
                 "WHERE hash LIKE '%prot000'")
    conn.commit()

    heute = ap.eintraege(db, zeitfenster="heute")
    assert heute["anzahl"] == 0
    assert heute["ohne_zeitpunkt_verborgen"] == 1
    assert "alle" in heute["nachricht"]

    alle = ap.eintraege(db, zeitfenster="alle")
    assert alle["anzahl"] == 1
    assert alle["eintraege"][0]["herkunft"] == "unbekannt", \
        "Ohne Beleg ist die Herkunft unbekannt, nicht 'ich'."
    assert "zeitpunkt_hinweis" in alle["eintraege"][0]


def test_1010_zeitfenster_rechnen_zeitzonenbewusst(db):
    """`_now()` schreibt UTC-ISO mit Offset.

    Zeichenketten verschiedener Formate zu vergleichen geht schief, ohne
    dass es auffaellt — das ist die Zeitzonen-Falle aus v1.7.21, nur eine
    Ebene hoeher.
    """
    from bewerbungs_assistent.services import aussortier_protokoll as ap
    _stellen(db, 3)
    db.dismiss_job("prot000", "zeitarbeit")
    db.dismiss_job("prot001", "befristet")
    conn = db.connect()
    conn.execute(
        "UPDATE jobs SET dismissed_at=? WHERE hash LIKE '%prot001'",
        ((datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),))
    conn.commit()

    assert ap.eintraege(db, zeitfenster="7tage")["anzahl"] == 1
    assert ap.eintraege(db, zeitfenster="30tage")["anzahl"] == 2
    assert ap.eintraege(db, zeitfenster="7tage")["ausserhalb_des_fensters"] == 1


def test_1010_unbekanntes_zeitfenster_wird_abgewiesen(db):
    """Ein stillschweigend anderes Fenster waere schlimmer als ein Fehler."""
    from bewerbungs_assistent.services import aussortier_protokoll as ap
    assert "fehler" in ap.eintraege(db, zeitfenster="gestern")
    assert "fehler" in ap.eintraege(db, herkunft_filter="jemand")


def test_1010_werkzeug_nennt_den_weg_zurueck(db):
    """Ein Protokoll ohne Rueckholweg waere ein Archiv."""
    _stellen(db, 2)
    db.dismiss_job("prot000", "zeitarbeit")
    antwort = _werkzeug(db, "aussortier_protokoll")(zeitfenster="heute")
    assert antwort["anzahl"] == 1
    assert "stelle_reaktivieren" in antwort["naechster_schritt"]


def test_1010_rest_und_mcp_lesen_denselben_dienst(db):
    """Zwei Fassungen derselben Liste waeren der neunte Fall des Musters."""
    quelle = (_repo() / "src" / "bewerbungs_assistent"
              / "dashboard.py").read_text(encoding="utf-8", errors="replace")
    assert "aussortier_protokoll as _protokoll" in quelle
    assert "_protokoll.eintraege(_db" in quelle
    werkzeug = (_repo() / "src" / "bewerbungs_assistent" / "tools"
                / "jobs.py").read_text(encoding="utf-8", errors="replace")
    assert "_protokoll.eintraege(db" in werkzeug


def test_1010_die_herkunft_rechnet_der_server(db):
    """Kein zweiter Rechenweg im JavaScript.

    Die Regel ist nicht trivial (gespeicherte Spalte, `auto:`-Praefix im
    Altbestand, sonst ehrlich unbekannt) — gespiegelt waere sie beim
    naechsten Sonderfall auseinandergelaufen.
    """
    quelle = ohne_kommentare(JOBS_PAGE.read_text(encoding="utf-8"))
    assert "job.herkunft" in quelle, "Das Frontend liest den Serverwert."
    assert "auto:" not in quelle, \
        "Die Herkunfts-Regel gehoert nicht ins Frontend."


def test_1010_protokoll_sortiert_nach_dem_aussortier_zeitpunkt():
    """Nicht nach `updated_at` — das war der ganze Befund."""
    quelle = JOBS_PAGE.read_text(encoding="utf-8")
    block = quelle[quelle.index("const protokollListe"):]
    block = block[:block.index("const currentList")]
    assert "dismissed_at" in block
    assert "updated_at" not in block


def test_1010_rueckgaengig_steht_im_toast():
    """Der Verklicker faellt in Sekunden auf, nicht in Tagen."""
    quelle = JOBS_PAGE.read_text(encoding="utf-8")
    block = quelle[quelle.index("async function saveDismiss"):]
    block = block[:block.index("function toggleDismissReason")]
    assert "Rückgängig" in block
    assert "holeZurueck" in block, \
        "Rueckgaengig muss denselben Weg nehmen wie das Wiederherstellen."


# -- #1009: Handlung im Dialog ----------------------------------------

def test_1009_fit_dialog_bietet_die_handlungen():
    """AK 1: der Dialog endet nicht mehr im Nichts."""
    quelle = JOBS_PAGE.read_text(encoding="utf-8")
    start = quelle.index("Detailbewertung durch Claude anfordern")
    block = quelle[start:start + 2500]
    assert "Passt nicht" in block
    assert "Bewerbung erfassen" in block
    assert "Anpinnen" in block


def test_1009_es_ist_derselbe_aufruf_wie_auf_der_karte():
    """AK 3, und der eigentliche Punkt des Issues.

    Zwei Wege zum selben Zustand sind in diesem Projekt achtmal
    auseinandergelaufen. Der Entwurf des Bewerbungs-Dialogs stand als
    Literal am Karten-Knopf; er steht jetzt in einer Funktion, die beide
    Seiten rufen.
    """
    quelle = ohne_kommentare(JOBS_PAGE.read_text(encoding="utf-8"))
    assert quelle.count("function openApplicationDialog") == 1, \
        "Der Oeffner steht genau einmal da."
    # Karte, Fit-Dialog und Detail-Dialog rufen ihn. Die dritte
    # Fundstelle gab es schon VOR diesem Issue — gefunden hat sie der
    # neue Guard beim ersten Lauf.
    aufrufe = quelle.count("openApplicationDialog(") - 1
    assert aufrufe >= 3, f"Nur {aufrufe} Aufrufer — einer fehlt."
    # Der Entwurf selbst darf nur EINMAL ausgeschrieben sein.
    assert quelle.count('status: "beworben"') == 1, \
        "Zweite Fassung des Bewerbungs-Entwurfs."
    assert quelle.count("openDismissDialog") >= 3, \
        "Karte und Dialog rufen denselben Aussortier-Weg."


def test_1009_der_dialog_kennt_die_stelle_nicht_nur_den_titel():
    """Ohne die Stelle koennte der Dialog nichts ausloesen."""
    quelle = JOBS_PAGE.read_text(encoding="utf-8")
    assert "hash: job.hash, job, analysis" in quelle


def test_1764_kein_hook_hinter_einem_fruehen_return():
    """Guard fuer die Fehlerklasse, die diese Welle gekostet hat.

    `JobsPage` hat ein `if (loading) return <LoadingPanel .../>`. Mein
    neues `useMemo` landete dahinter: im ERSTEN Rendern (loading) laeuft
    es nicht mit, im zweiten schon — React verwirft die Komponente dann
    ("Rendered more hooks than during the previous render").

    Das Teure daran: **der Vite-Build war gruen, und in der Konsole
    stand nichts.** Sichtbar wurde es nur daran, dass die Stellen-Seite
    im Browser-Test nicht mehr erschien. Ein Build, der durchlaeuft, ist
    kein Beleg dafuer, dass die Seite rendert.
    """
    quelle = JOBS_PAGE.read_text(encoding="utf-8")
    zeilen = quelle.split("\n")
    frueh = [i for i, z in enumerate(zeilen)
             if re.match(r"^  if \(.*\) return <", z)]
    assert frueh, "Der fruehe Return ist weg — dann kann der Guard weg."
    ab = frueh[0]
    danach = [f"{i + 1}: {zeilen[i].strip()[:70]}" for i in range(ab + 1, len(zeilen))
              if re.search(r"\b(useState|useMemo|useEffect|useCallback|useRef|"
                           r"useDeferredValue|useEffectEvent)\(", zeilen[i])]
    assert not danach, (
        "Hook-Aufruf nach dem fruehen Return — React zaehlt die Hooks je "
        "Rendern ab:\n  " + "\n  ".join(danach))
