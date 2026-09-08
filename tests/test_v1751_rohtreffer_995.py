"""Tests fuer v1.7.51 — #995: gesehen und behalten waren dieselbe Zahl.

Gemeldet am 08.09.2026 aus der Quellenpflege zu #813. Gemessen an
`himalayas`:

    | Was die API liefert                               | 20 |
    | Was der Adapter nach seinem `_matches` zurueckgibt |  0 |
    | Was als `letzte_rohtreffer` in der Diagnose steht  |  0 |

**`letzte_rohtreffer` hiess nicht ueberall dasselbe.** Damit sahen zwei
voellig verschiedene Zustaende gleich aus:

1. Die Quelle liefert nichts — Endpunkt tot, Bot-Block, leeres Ergebnis.
2. Die Quelle liefert, aber nichts passt zum Profil — ein
   internationales Remote-Board hat fuer eine regionale Fachsuche
   schlicht keine Treffer.

Beide zaehlten als stiller Lauf, beide fuehrten nach fuenf Laeufen zur
Abschaltung. Genau so wurde `himalayas` am 01.09. stillgelegt: es sah
nach Fall 2 aus und war Fall 1 (ein Feldumbau, #813).

Der Melder nannte drei Adapter und schrieb "mindestens". Es sind
**zwoelf**. Mein erster Durchgang fand zehn — die letzten beiden hatte
ein `grep` mit Zeilenbegrenzung abgeschnitten. Gefunden hat sie der
Test unten, der die Adapter selbst abzaehlt statt einer Liste zu
glauben; **genau dafuer steht er da**, und er hat sich beim ersten Lauf
bezahlt gemacht.
"""
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.job_scraper import rohtreffer  # noqa: E402

# Adapter mit adaptereigenem Keyword-Filter. Sie MUESSEN melden, was die
# Quelle geliefert hat — sonst ist ihre Rueckgabe die einzige Zahl.
FILTERNDE_ADAPTER = (
    "arbeitnow", "berufsstart", "greenhouse", "himalayas", "meinestadt",
    "personio", "praktikum_de", "remoteok", "remotive", "studentjob",
    # Diese beiden hat der erste Durchgang uebersehen, weil ein `grep`
    # mit Zeilenbegrenzung sie abschnitt. Gefunden hat sie der Test
    # unten, der die Adapter selbst abzaehlt statt einer Liste zu
    # glauben — genau dafuer steht er da.
    "workable", "workday_dax",
)


@pytest.fixture(autouse=True)
def sauberes_register():
    rohtreffer.lauf_beginnen()
    yield
    rohtreffer.lauf_beginnen()


# ── Das Register ──────────────────────────────────────────────────────

def test_995_nicht_gemeldet_ist_nicht_null():
    """Der Kern von #989 in diesem Modul: `None` heisst "der Adapter
    meldet es nicht", `0` heisst "die Quelle lieferte nichts". Faellt
    das zusammen, ist der ganze Fix wirkungslos."""
    assert rohtreffer.stand("himalayas") is None
    rohtreffer.melde("himalayas", 0)
    assert rohtreffer.stand("himalayas") == 0


def test_995_seitenweise_wird_addiert():
    """Die meisten Adapter holen seitenweise."""
    for _ in range(3):
        rohtreffer.melde("arbeitnow", 25)
    assert rohtreffer.stand("arbeitnow") == 75


def test_995_ein_neuer_lauf_verwirft_die_alten_zahlen():
    """Ein Adapter, der diesmal gar nicht lief, darf nicht den Stand von
    gestern melden — eine alte Zahl ist schlimmer als keine."""
    rohtreffer.melde("remoteok", 100)
    rohtreffer.lauf_beginnen()
    assert rohtreffer.stand("remoteok") is None


def test_995_register_stuerzt_bei_muell_nicht_ab():
    """Es laeuft in jedem Adapter mit — ein Absturz waere teurer als die
    fehlende Zahl."""
    for wert in (None, "viele", -5, [1]):
        rohtreffer.melde("x", wert)
    assert rohtreffer.stand("x") is None
    rohtreffer.melde("", 5)
    assert rohtreffer.alle() == {}


def test_995_register_haelt_paralleles_melden_aus():
    """Die Quellen laufen in einem ThreadPool mit bis zu vier Arbeitern."""
    import threading
    threads = [threading.Thread(target=lambda: [rohtreffer.melde("p", 1)
                                                for _ in range(200)])
               for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert rohtreffer.stand("p") == 800


# ── Alle zwoelf Adapter melden ──────────────────────────────────────────

@pytest.mark.parametrize("adapter", FILTERNDE_ADAPTER)
def test_995_jeder_filternde_adapter_meldet_das_gesehene(adapter):
    """Der Guard gegen die Luecke.

    Ein Adapter, der intern filtert und NICHT meldet, erzeugt genau den
    gemeldeten Fehler wieder. Der Test zaehlt deshalb die Adapter mit
    `_matches` ab und verlangt von jedem eine Meldung.
    """
    quelle = (Path(__file__).resolve().parents[1] / "src"
              / "bewerbungs_assistent" / "job_scraper"
              / f"{adapter}.py").read_text(encoding="utf-8")
    code = "\n".join(z for z in quelle.split("\n")
                     if not z.strip().startswith("#"))
    assert "rohtreffer.melde(" in code, (
        f"{adapter} filtert intern (_matches), meldet aber nicht, was die "
        "Quelle geliefert hat")


def test_995_die_liste_der_filternden_adapter_ist_vollstaendig():
    """Kommt ein elfter Adapter mit eigenem Filter dazu, faellt er hier
    auf — sonst waechst die Luecke still mit."""
    basis = (Path(__file__).resolve().parents[1] / "src"
             / "bewerbungs_assistent" / "job_scraper")
    mit_filter = {
        p.stem for p in basis.glob("*.py")
        if "_matches" in p.read_text(encoding="utf-8")
        and p.stem not in ("rohtreffer",)
    }
    assert mit_filter == set(FILTERNDE_ADAPTER), (
        f"Adapter mit eigenem Filter haben sich geaendert: "
        f"{sorted(mit_filter ^ set(FILTERNDE_ADAPTER))}")


# ── Die Abschaltung entscheidet auf "gesehen" ─────────────────────────

@pytest.fixture
def db():
    """QA-Isolation (HART): eigenes Temp-Verzeichnis, hart geprueft."""
    tmpdir = tempfile.mkdtemp(prefix="pbp_995_")
    alt = os.environ.get("BA_DATA_DIR")
    os.environ["BA_DATA_DIR"] = tmpdir
    from bewerbungs_assistent import database as _database
    importlib.reload(_database)
    datenbank = _database.Database()
    datenbank.initialize()
    assert str(tmpdir) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    try:
        yield datenbank
    finally:
        if alt is None:
            os.environ.pop("BA_DATA_DIR", None)
        else:
            os.environ["BA_DATA_DIR"] = alt
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_995_wer_liefert_ist_nicht_stumm(db):
    """AK 3: die automatische Abschaltung greift nur im ersten Fall.

    20 Datensaetze geliefert, 0 nach dem Keyword-Filter — das ist kein
    stiller Lauf, sondern eine Quelle ohne fachliche Passung.
    """
    ergebnis = db.update_scraper_health("himalayas", "ok", 0, 1.5,
                                        seen_count=20)
    assert ergebnis["state"] == "ok"
    assert not ergebnis["auto_deactivated"]


def test_995_ohne_lieferung_bleibt_es_ein_stiller_lauf(db):
    """Die Gegenprobe. Wer den Fix zu breit baut, schaltet nie wieder
    eine wirklich tote Quelle ab."""
    ergebnis = db.update_scraper_health("tote_quelle", "ok", 0, 1.5,
                                        seen_count=0)
    assert ergebnis["state"] == "silent"
    # Und ohne jede Meldung bleibt es beim Verhalten von vorher.
    assert db.update_scraper_health("alt", "ok", 0, 1.5)["state"] == "silent"


def test_995_fuenf_stille_laeufe_schalten_weiterhin_ab(db):
    """Der Mechanismus aus #590-C.1 darf nicht verlorengehen."""
    for _ in range(6):
        ergebnis = db.update_scraper_health("tot", "ok", 0, 1.0, seen_count=0)
    assert ergebnis["auto_deactivated"] or not [
        h for h in db.get_scraper_health()
        if h["scraper_name"] == "tot" and h["is_active"]]


def test_995_eine_liefernde_quelle_wird_nie_abgeschaltet(db):
    """Der gemeldete Schaden, in der Zeit nachgestellt: zehn Laeufe mit
    Lieferung, aber ohne Passung."""
    for _ in range(10):
        db.update_scraper_health("global_board", "ok", 0, 1.0, seen_count=20)
    stand = [h for h in db.get_scraper_health()
             if h["scraper_name"] == "global_board"][0]
    assert stand["is_active"]
    assert stand["consecutive_silent"] == 0


def test_995_der_fall_wird_benannt(db):
    """AK 4: als solche gemeldet, nicht still uebergangen."""
    db.update_scraper_health("global_board", "ok", 0, 1.0, seen_count=20)
    stand = [h for h in db.get_scraper_health()
             if h["scraper_name"] == "global_board"][0]
    assert stand["last_seen_count"] == 20
    assert "nichts Passendes" in (stand["last_status_detail"] or "")


def test_995_die_zahl_ueberlebt_den_zweiten_lauf(db):
    """Erst INSERT, dann UPDATE — beide Zweige muessen die Spalte
    schreiben, sonst steht nach dem zweiten Lauf wieder nichts da."""
    db.update_scraper_health("q", "ok", 3, 1.0, seen_count=20)
    db.update_scraper_health("q", "ok", 5, 1.0, seen_count=42)
    stand = [h for h in db.get_scraper_health() if h["scraper_name"] == "q"][0]
    assert stand["last_seen_count"] == 42
