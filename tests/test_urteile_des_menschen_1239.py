"""#1239: Beispiele und Lernblock der KI-Aussortierung kommen aus Urteilen des MENSCHEN.

Die Dokumentation sagt "sonst lernt das Modell von sich selbst". Im Betrieb schloss der Filter nur das Praefix `auto:` aus,
das `normalisiere_dismiss_wert` seit #913 beim Schreiben entfernt: die Automatik schreibt `dismissed_by='automatik'` und einen
Grund OHNE Praefix. Gemessen auf einer Kopie einer echten Datenbank: 5 von 5 Beispielen im Prompt waren Urteile der Automatik,
0 von 3.586 Zeilen trugen das Praefix. Systemgruende (`bewerbung_erstellt`, `firma_blacklisted`, `profil_match_negativ`, ...)
kamen als "hat der Bewerber selbst abgelehnt" mit, obwohl `bewerbung_erstellt` das Gegenteil einer Ablehnung ist.

EINE Frage, eine Funktion: `ablehnungsgruende.urteilsgruende_des_menschen`. Die Beispiele (`Database.get_recent_user_dismissals`)
und der Block "GELERNT" (`gruende_zaehlen(nur_menschen=True)`) fragen beide sie. Je Leser dieselben drei Faelle: Automatik ohne
Praefix, Systemgrund, Mensch. Dazu: Herkunft unbekannt (Altbestand vor v1.7.64), Praefix, Liste von Gruenden, das LIMIT gilt
NACH dem Filter, der echte Weg (`aussortieren`) und drei Waechter, die den Aufruf festhalten.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "bewerbungs_assistent"

LANG = "Ein ausfuehrlicher Anzeigentext mit Aufgaben und Anforderungen. " * 3


# ── Testdoppel und Bestand ───────────────────────────────────────────────────────────────────────────

class _KI:
    """Testdoppel der lokalen KI: haelt jede Nutzlast fest; "fremd" im Titel heisst PASST_NICHT, sonst PASST."""

    def __init__(self):
        self.nutzlasten = []

    def get_status(self, force_refresh=False):
        return SimpleNamespace(ollama_available=True, available_models=["m"], user_state="active", selected_model="m")

    def warmup(self):
        return {"status": "warm", "duration_sec": 0}

    def run(self, kind, payload):
        self.nutzlasten.append(dict(payload))
        urteil = "PASST_NICHT" if "fremd" in payload["job_title"] else "PASST"
        return SimpleNamespace(success=True, fallback_message="", payload={"decision": urteil, "reason": "Testurteil"})


@pytest.fixture
def db(tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Urteile-Test"})
    ki = _KI()
    from bewerbungs_assistent.services import llm_service
    monkeypatch.setattr(llm_service, "get_llm_service", lambda _db=None: ki)
    d.ki = ki
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _aussortiert(db, kennung, titel, grund, wer="ich", zeit="2026-10-10T10:00:00", herkunft_leer=False, roh_grund=None):
    """Eine aussortierte Stelle ueber die ECHTEN Schreibwege (`save_jobs`, `dismiss_job`).

    `herkunft_leer` und `roh_grund` stellen Altbestand nach, den kein heutiger Schreibweg mehr erzeugt
    (Herkunft leer vor v1.7.64, Praefix `auto:` vor #913).
    """
    db.save_jobs([{"hash": kennung, "title": titel, "company": f"Beispiel {kennung}",
                   "url": f"https://example.com/{kennung}", "source": "manuell", "description": LANG, "score": 3}])
    voll = db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE ?", (f"%{kennung}",)).fetchone()[0]
    assert db.dismiss_job(voll, grund, herkunft=wer)
    conn = db.connect()
    conn.execute("UPDATE jobs SET updated_at=? WHERE hash=?", (zeit, voll))
    if herkunft_leer:
        conn.execute("UPDATE jobs SET dismissed_by=NULL WHERE hash=?", (voll,))
    if roh_grund is not None:
        conn.execute("UPDATE jobs SET dismiss_reason=? WHERE hash=?", (roh_grund, voll))
    conn.commit()
    return voll


def _bestand(db):
    """Ein Bestand mit allen Faellen. Die Zeilen ohne Urteil des Menschen sind ALLE neuer als die drei des Menschen."""
    _aussortiert(db, "h1", "Mensch A", "falsches_fachgebiet", zeit="2026-10-01T10:00:00")
    _aussortiert(db, "h2", "Mensch B", "zu_junior", zeit="2026-10-02T10:00:00")
    _aussortiert(db, "h3", "Mensch C", ["falsches_fachgebiet", "zu_weit_entfernt"], zeit="2026-10-03T10:00:00")
    # Automatik OHNE Praefix: der Fall des Issues
    _aussortiert(db, "a1", "Automatik A", "zu_junior", wer="automatik", zeit="2026-10-10T10:00:00")
    _aussortiert(db, "a2", "Automatik B", "falsches_fachgebiet", wer="automatik", zeit="2026-10-11T10:00:00")
    _aussortiert(db, "a3", "Automatik C", "profil_match_negativ", wer="automatik", zeit="2026-10-12T10:00:00")
    # Systemgruende und Gruende ohne Urteil, vom Menschen oder beim Bewerben gesetzt
    _aussortiert(db, "s1", "System A", "bewerbung_erstellt", zeit="2026-10-13T10:00:00")
    _aussortiert(db, "s2", "System B", "firma_blacklisted", zeit="2026-10-13T11:00:00")
    _aussortiert(db, "s3", "System C", "veraltet_url", zeit="2026-10-13T12:00:00")
    _aussortiert(db, "s4", "Doppelt", "duplikat", zeit="2026-10-13T13:00:00")
    # Altbestand: Herkunft unbekannt, und das alte Praefix
    _aussortiert(db, "u1", "Altbestand A", "falsches_fachgebiet", zeit="2026-10-14T10:00:00", herkunft_leer=True)
    _aussortiert(db, "p1", "Altbestand B", "zu_junior", zeit="2026-10-15T10:00:00", herkunft_leer=True,
                 roh_grund="auto:zu_junior:Begruendung der KI")
    return db


def _titel(zeilen):
    return [z["title"] for z in zeilen]


# ── Die eine Funktion ───────────────────────────────────────────────────────────────────────────────

FAELLE = [
    # (Herkunft, Grund, erwartet)
    ("ich", "falsches_fachgebiet", ["falsches_fachgebiet"]),                       # Mensch
    ("ich", "zu_weit_entfernt", ["zu_weit_entfernt"]),                              # auch Entfernung ist sein Urteil
    ("ich", "sonstiges", ["sonstiges"]),
    ("ich", '["zu_junior", "zu_weit_entfernt"]', ["zu_junior", "zu_weit_entfernt"]),  # Liste: beide
    ("ich", '["falsches_fachgebiet", "bewerbung_erstellt"]', ["falsches_fachgebiet"]),  # Liste: nur der, der zaehlt
    (" Ich ", "zu_senior", ["zu_senior"]),                                          # Schreibweise der Herkunft
    ("automatik", "zu_junior", []),                                                 # Automatik OHNE Praefix
    ("automatik", "falsches_fachgebiet", []),
    ("automatik", "profil_match_negativ", []),
    (None, "auto:zu_junior:Begruendung der KI", []),                                # Praefix, Herkunft leer
    (None, "falsches_fachgebiet", []),                                              # Herkunft unbekannt
    ("", "zu_junior", []),
    ("ich", "bewerbung_erstellt", []),                                              # Systemgrund / kein Urteil
    ("ich", "firma_blacklisted", []),
    ("ich", "keyword_blacklisted", []),                                             # Treffer eines Stichworts der Blacklist
    ("ich", "profil_match_negativ", []),
    ("ich", "veraltet_url", []),
    ("ich", "war_nur_anfrage", []),
    ("ich", "bereits_beworben", []),
    ("ich", "duplikat", []),
    ("ich", "Duplikat: abc123", []),                                                # Altschreibweise des Grundes duplikat
    ("ich", None, []),
    ("ich", "", []),
    ("ich", "[]", []),
]


@pytest.mark.parametrize("wer,grund,erwartet", FAELLE)
def test_urteilsgruende_des_menschen(wer, grund, erwartet):
    from bewerbungs_assistent.services.ablehnungsgruende import urteilsgruende_des_menschen
    assert urteilsgruende_des_menschen(wer, grund) == erwartet


def test_jeder_systemgrund_und_jeder_grund_ohne_urteil_zaehlt_nicht():
    """Nicht von Hand aufgezaehlt: ein neuer Wert in den Listen faellt hier sofort auf."""
    from bewerbungs_assistent.services.ablehnungsgruende import (
        KEIN_URTEIL_GRUENDE, SYSTEM_GRUENDE, urteilsgruende_des_menschen)
    for grund in sorted(SYSTEM_GRUENDE | KEIN_URTEIL_GRUENDE):
        assert urteilsgruende_des_menschen("ich", grund) == [], grund


def test_jeder_regulaere_grund_zaehlt_beim_menschen():
    """Gegenstueck: ein Grund, den der Mensch waehlen kann und der ein Urteil ist, geht nie verloren."""
    from bewerbungs_assistent.services.ablehnungsgruende import (
        KEIN_URTEIL_GRUENDE, STANDARD_GRUENDE, SYSTEM_GRUENDE, urteilsgruende_des_menschen)
    zaehlen = [g for g in STANDARD_GRUENDE if g not in SYSTEM_GRUENDE and g not in KEIN_URTEIL_GRUENDE]
    assert len(zaehlen) >= 10
    for grund in zaehlen:
        assert urteilsgruende_des_menschen("ich", grund) == [grund], grund


def test_herkunft_unbekannt_ist_eine_entscheidung_an_einer_stelle(monkeypatch):
    """`dismissed_by` leer heisst "unbekannt" (`aussortier_protokoll.herkunft`), nicht "war ich". Wer es anders will, aendert EINE Zeile."""
    from bewerbungs_assistent.services import ablehnungsgruende as ag
    assert ag.UNBEKANNTE_HERKUNFT_ZAEHLT is False
    assert ag.urteilsgruende_des_menschen(None, "zu_junior") == []
    monkeypatch.setattr(ag, "UNBEKANNTE_HERKUNFT_ZAEHLT", True)
    assert ag.urteilsgruende_des_menschen(None, "zu_junior") == ["zu_junior"]
    # auch dann nie: Automatik, Praefix, Systemgrund
    assert ag.urteilsgruende_des_menschen("automatik", "zu_junior") == []
    assert ag.urteilsgruende_des_menschen(None, "auto:zu_junior:x") == []
    assert ag.urteilsgruende_des_menschen(None, "bewerbung_erstellt") == []


# ── Leser 1: die Beispiele im Prompt ────────────────────────────────────────────────────────────────

def test_beispiele_nur_urteile_des_menschen_neueste_zuerst(db):
    """Die Zeilen der Automatik, mit Systemgrund, ohne Herkunft und mit Praefix sind ALLE neuer: der Betrieb gab nur sie zurueck."""
    _bestand(db)
    bsp = db.get_recent_user_dismissals(limit=10)
    assert _titel(bsp) == ["Mensch C", "Mensch B", "Mensch A"]
    assert set(bsp[0]) == {"title", "company", "dismiss_reason", "updated_at"}, "Form der Beispiele unveraendert"


def test_das_limit_gilt_nach_dem_filter(db):
    """Die drei neuesten Zeilen sind keine Urteile des Menschen: ein LIMIT VOR dem Filter lieferte eine leere Liste."""
    _bestand(db)
    assert _titel(db.get_recent_user_dismissals(limit=3)) == ["Mensch C", "Mensch B", "Mensch A"]
    assert _titel(db.get_recent_user_dismissals(limit=2)) == ["Mensch C", "Mensch B"]
    assert _titel(db.get_recent_user_dismissals(limit=1)) == ["Mensch C"]


@pytest.mark.parametrize("grund", ["profil_match_negativ", "zu_weit_entfernt", "unpassendes_arbeitsmodell"])
def test_viele_zeilen_der_automatik_verdraengen_den_menschen_nicht(db, grund):
    """Der Fall der echten Datenbank: ein Lauf der Automatik sortiert zwanzig Stellen aus, danach kommt kein Mensch mehr in die Beispiele.

    Die Automatik schreibt auch Urteilsgruende (`save_jobs` beim Anlegen: zu_weit_entfernt, unpassendes_arbeitsmodell): dort
    traegt allein die Herkunft; bei profil_match_negativ scheidet schon der Systemgrund die Zeile aus.
    """
    _aussortiert(db, "h1", "Mensch A", "falsches_fachgebiet", zeit="2026-10-01T10:00:00")
    for i in range(20):
        _aussortiert(db, f"z{i:02d}", f"Lauf {i}", grund, wer="automatik", zeit=f"2026-10-16T12:{i:02d}:00")
    assert _titel(db.get_recent_user_dismissals(limit=10)) == ["Mensch A"]
    from bewerbungs_assistent.services.ablehnungsgruende import gruende_zaehlen
    liste, gesamt = gruende_zaehlen(db.connect(), db.get_active_profile_id(), ausser=(), nur_menschen=True)
    assert dict(liste) == {"falsches_fachgebiet": 1} and gesamt == 1


def test_ohne_urteil_des_menschen_keine_beispiele(db):
    _aussortiert(db, "a1", "Automatik A", "zu_junior", wer="automatik")
    _aussortiert(db, "s1", "System A", "bewerbung_erstellt")
    assert db.get_recent_user_dismissals(limit=10) == []


def test_aktive_stellen_sind_nie_beispiele(db):
    """Auch eine AKTIVE Stelle mit uebriggebliebenem Grund (Dateninkonsistenz) ist kein Beispiel: aussortiert heisst is_active=0."""
    db.save_jobs([{"hash": "akt1", "title": "Aktiv", "company": "Beispiel Frischbetrieb", "url": "https://example.com/akt1",
                   "source": "manuell", "description": LANG, "score": 3}])
    conn = db.connect()
    voll = conn.execute("SELECT hash FROM jobs WHERE hash LIKE '%akt1'").fetchone()[0]
    conn.execute("UPDATE jobs SET dismiss_reason='zu_junior', dismissed_by='ich', updated_at='2026-10-20T10:00:00' WHERE hash=?", (voll,))
    conn.commit()
    _aussortiert(db, "h1", "Mensch A", "zu_senior")
    assert _titel(db.get_recent_user_dismissals(limit=10)) == ["Mensch A"]


def test_beispiele_herkunft_unbekannt_mit_dem_schalter(db, monkeypatch):
    """Wer "unbekannt" mitzaehlen will (eine Zeile), bekommt den Altbestand wieder, aber nie Automatik, Praefix oder Systemgrund."""
    from bewerbungs_assistent.services import ablehnungsgruende as ag
    _bestand(db)
    monkeypatch.setattr(ag, "UNBEKANNTE_HERKUNFT_ZAEHLT", True)
    assert _titel(db.get_recent_user_dismissals(limit=10)) == ["Altbestand A", "Mensch C", "Mensch B", "Mensch A"]


def test_beispiel_zeigt_nur_die_gruende_die_zaehlen(db):
    """Eine Zeile mit mehreren Gruenden, von denen einer kein Urteil ist: die KI sieht nur die, die zaehlen."""
    _aussortiert(db, "m1", "Gemischt A", ["zu_junior", "duplikat"], zeit="2026-10-04T10:00:00")
    _aussortiert(db, "m2", "Gemischt B", ["falsches_fachgebiet", "bewerbung_erstellt"], zeit="2026-10-05T10:00:00")
    _aussortiert(db, "m3", "Beide zaehlen", ["zu_junior", "zu_weit_entfernt"], zeit="2026-10-06T10:00:00")
    _aussortiert(db, "m4", "Einfach", "zu_senior", zeit="2026-10-07T10:00:00")
    gezeigt = {b["title"]: b["dismiss_reason"] for b in db.get_recent_user_dismissals(limit=10)}
    assert gezeigt["Gemischt A"] == "zu_junior"
    assert gezeigt["Gemischt B"] == "falsches_fachgebiet"
    assert gezeigt["Beide zaehlen"] == '["zu_junior", "zu_weit_entfernt"]', "gespeicherter Wert, wenn alles zaehlt"
    assert gezeigt["Einfach"] == "zu_senior"


def test_profile_bleiben_getrennt(db):
    """Beide Leser: jedes Profil sieht nur seine eigenen Urteile (die Gegenprobe `OR 1=1` blieb sonst gruen)."""
    from bewerbungs_assistent.services.ablehnungsgruende import gruende_zaehlen
    erstes = db.get_active_profile_id()
    _aussortiert(db, "h1", "Mensch A", "zu_junior", zeit="2026-10-01T10:00:00")
    zweites = db.create_profile("Zweites")
    db.switch_profile(zweites)
    _aussortiert(db, "z1", "Zweites B", "falsche_branche", zeit="2026-10-12T10:00:00")
    assert _titel(db.get_recent_user_dismissals(limit=10)) == ["Zweites B"]
    assert dict(gruende_zaehlen(db.connect(), zweites, ausser=(), nur_menschen=True)[0]) == {"falsche_branche": 1}
    db.switch_profile(erstes)
    assert _titel(db.get_recent_user_dismissals(limit=10)) == ["Mensch A"]
    assert dict(gruende_zaehlen(db.connect(), erstes, ausser=(), nur_menschen=True)[0]) == {"zu_junior": 1}


def test_ein_lauf_der_blacklist_auf_den_bestand_zaehlt_nicht(db):
    """`blacklist_anwenden` schreibt Herkunft "ich" und fuer ein STICHWORT den Grund keyword_blacklisted. Ohne den Eintrag im Vokabular
    wurde daraus 'sonstiges': viele Zeilen mit demselben Zeitpunkt verdraengten die Beispiele und standen im Block GELERNT."""
    from bewerbungs_assistent.services import blacklist_bestand
    from bewerbungs_assistent.services.ablehnungsgruende import gruende_zaehlen
    _aussortiert(db, "h1", "Mensch A", "zu_junior", zeit="2026-10-01T10:00:00")
    for i in range(4):
        db.save_jobs([{"hash": f"k{i}", "title": f"Lagerhelfer {i}", "company": f"Beispiel Lager {i}",
                       "url": f"https://example.com/k{i}", "source": "manuell", "description": LANG, "score": 3}])
    db.add_to_blacklist("keyword", "lagerhelfer")
    lauf = blacklist_bestand.anwenden(db, dry_run=False)
    assert lauf["deaktiviert"] == 4
    zeilen = db.connect().execute(
        "SELECT dismissed_by, dismiss_reason FROM jobs WHERE title LIKE 'Lagerhelfer%'").fetchall()
    assert {(z["dismissed_by"], z["dismiss_reason"]) for z in zeilen} == {("ich", "keyword_blacklisted")},         "der Grund muss als keyword_blacklisted stehen bleiben, nicht zu 'sonstiges' werden"
    assert _titel(db.get_recent_user_dismissals(limit=10)) == ["Mensch A"]
    liste, gesamt = gruende_zaehlen(db.connect(), db.get_active_profile_id(), ausser=(), nur_menschen=True)
    assert dict(liste) == {"zu_junior": 1} and gesamt == 1


# ── Leser 2: der Block "GELERNT" ────────────────────────────────────────────────────────────────────

def test_haeufigste_gruende_nur_urteile_des_menschen(db):
    from bewerbungs_assistent.services.ablehnungsgruende import gruende_zaehlen
    _bestand(db)
    liste, gesamt = gruende_zaehlen(db.connect(), db.get_active_profile_id(), ausser=(), nur_menschen=True)
    assert dict(liste) == {"falsches_fachgebiet": 2, "zu_junior": 1, "zu_weit_entfernt": 1}
    assert liste[0] == ("falsches_fachgebiet", 2)
    assert gesamt == 3, "drei Stellen, eine mit zwei Gruenden zaehlt einmal"


def test_ohne_den_filter_zaehlt_alles_wie_bisher(db):
    """Die anderen Leser (Statistik, Lern-Karte, Erkenntnisse) bleiben, wie sie waren: gleiche Zahlen, gleiche Form."""
    from bewerbungs_assistent.services.ablehnungsgruende import gruende_zaehlen
    _bestand(db)
    conn, pid = db.connect(), db.get_active_profile_id()
    liste, gesamt = gruende_zaehlen(conn, pid, ausser=())
    assert dict(liste) == {"falsches_fachgebiet": 4, "zu_junior": 2, "zu_weit_entfernt": 1, "profil_match_negativ": 1,
                           "bewerbung_erstellt": 1, "firma_blacklisted": 1, "veraltet_url": 1, "duplikat": 1,
                           "auto:zu_junior:Begruendung der KI": 1}
    assert gesamt == 12
    standard, _ = gruende_zaehlen(conn, pid)
    assert "bewerbung_erstellt" not in dict(standard)
    assert dict(standard)["profil_match_negativ"] == 1


def test_systemgrund_allein_zaehlt_im_gesamtwert_nicht(db):
    from bewerbungs_assistent.services.ablehnungsgruende import gruende_zaehlen
    _aussortiert(db, "s1", "System A", "bewerbung_erstellt")
    _aussortiert(db, "a1", "Automatik A", "zu_junior", wer="automatik")
    assert gruende_zaehlen(db.connect(), db.get_active_profile_id(), ausser=(), nur_menschen=True) == ([], 0)


def test_gruende_unbekannte_herkunft_wie_bei_den_beispielen(db, monkeypatch):
    from bewerbungs_assistent.services import ablehnungsgruende as ag
    _bestand(db)
    conn, pid = db.connect(), db.get_active_profile_id()
    monkeypatch.setattr(ag, "UNBEKANNTE_HERKUNFT_ZAEHLT", True)
    liste, gesamt = ag.gruende_zaehlen(conn, pid, ausser=(), nur_menschen=True)
    assert dict(liste) == {"falsches_fachgebiet": 3, "zu_junior": 1, "zu_weit_entfernt": 1}
    assert gesamt == 4


# ── Der echte Weg: was die KI zu sehen bekommt ──────────────────────────────────────────────────────

def test_aussortieren_gibt_der_ki_nur_urteile_des_menschen(db):
    """Nicht nur die Funktionen: die Nutzlast, die `aussortieren` an die KI schickt, traegt Beispiele UND Gruende des Menschen."""
    from bewerbungs_assistent.services import auto_aussortierung as aa
    _bestand(db)
    db.save_jobs([{"hash": "neu1", "title": "Neue Stelle", "company": "Beispiel Frischbetrieb", "url": "https://example.com/neu1",
                   "source": "manuell", "description": LANG, "score": 3}])
    erg = aa.aussortieren(db, max_stellen=5)
    assert erg["geprueft"] == 1
    nutzlast = db.ki.nutzlasten[-1]
    assert _titel(nutzlast["recent_dismissals"]) == ["Mensch C", "Mensch B", "Mensch A"]
    assert {e["reason"]: e["count"] for e in nutzlast["dismiss_reasons_top"]} == {
        "falsches_fachgebiet": 2, "zu_junior": 1, "zu_weit_entfernt": 1}


def test_die_eigenen_urteile_der_ki_kommen_nicht_als_beispiele_zurueck(db):
    """Die Echokammer als Ablauf: Lauf 1 sortiert aus (Automatik), Lauf 2 darf diese Urteile nicht als "selbst abgelehnt" sehen."""
    from bewerbungs_assistent.services import auto_aussortierung as aa
    _aussortiert(db, "h1", "Mensch A", "falsches_fachgebiet", zeit="2026-10-01T10:00:00")
    _aussortiert(db, "a9", "Automatik Distanz", "zu_weit_entfernt", wer="automatik", zeit="2026-10-15T10:00:00")
    db.save_jobs([{"hash": "f1", "title": "Stelle fremd", "company": "Beispiel Fremdbetrieb", "url": "https://example.com/f1",
                   "source": "manuell", "description": LANG, "score": 3}])
    assert aa.aussortieren(db, max_stellen=5)["passt_nicht"] == 1
    voll = db.connect().execute("SELECT hash, dismissed_by FROM jobs WHERE hash LIKE '%f1'").fetchone()
    assert voll["dismissed_by"] == "automatik"
    db.save_jobs([{"hash": "n2", "title": "Zweite Stelle", "company": "Beispiel Zweitbetrieb", "url": "https://example.com/n2",
                   "source": "manuell", "description": LANG, "score": 3}])
    aa.aussortieren(db, max_stellen=5)
    zweite = [n for n in db.ki.nutzlasten if n["job_title"] == "Zweite Stelle"][-1]
    assert _titel(zweite["recent_dismissals"]) == ["Mensch A"], "das Urteil der KI aus Lauf 1 stand als Beispiel da"
    assert {e["reason"] for e in zweite["dismiss_reasons_top"]} == {"falsches_fachgebiet"}


def test_der_prompt_zeigt_nur_die_beispiele_des_menschen(db):
    """Bis in den Text: der Block BEISPIELE nennt die Stellen des Menschen und keine der Automatik."""
    from bewerbungs_assistent.services import auto_aussortierung as aa
    from bewerbungs_assistent.services.llm_service import _build_match_job_to_skills_prompt
    _bestand(db)
    db.save_jobs([{"hash": "neu1", "title": "Neue Stelle", "company": "Beispiel Frischbetrieb", "url": "https://example.com/neu1",
                   "source": "manuell", "description": LANG, "score": 3}])
    aa.aussortieren(db, max_stellen=5)
    prompt = _build_match_job_to_skills_prompt(db.ki.nutzlasten[-1])
    beispiele = prompt.split("BEISPIELE", 1)[1].split("Nutze diese Muster", 1)[0]
    for gut in ("Mensch A", "Mensch B", "Mensch C"):
        assert gut in beispiele
    for schlecht in ("Automatik", "System", "Doppelt", "Altbestand", "profil_match_negativ", "bewerbung_erstellt"):
        assert schlecht not in beispiele, schlecht


# ── Waechter: der Aufruf muss stattfinden ───────────────────────────────────────────────────────────

def _aufrufe(quelltext: str, name: str):
    """Alle Aufrufe von `name(...)` (auch `x.name(...)`) im Syntaxbaum, als (Aufruf, Schluesselwoerter)."""
    treffer = []
    for knoten in ast.walk(ast.parse(quelltext)):
        if isinstance(knoten, ast.Call):
            f = knoten.func
            gerufen = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
            if gerufen == name:
                treffer.append((knoten, {k.arg: k.value for k in knoten.keywords if k.arg}))
    return treffer


def _nur_menschen_fehlt(quelltext: str) -> list:
    """Aufrufe von `gruende_zaehlen`, die `nur_menschen=True` NICHT setzen."""
    schlecht = []
    for knoten, kw in _aufrufe(quelltext, "gruende_zaehlen"):
        wert = kw.get("nur_menschen")
        if not (isinstance(wert, ast.Constant) and wert.value is True):
            schlecht.append(knoten.lineno)
    return schlecht


def test_waechter_erkennt_einen_aufruf_ohne_den_filter():
    """Gegenprobe des Waechters selbst: ohne diese Faelle prueft er nichts."""
    assert _nur_menschen_fehlt("gruende_zaehlen(conn, pid, ausser=())") == [1]
    assert _nur_menschen_fehlt("x.gruende_zaehlen(conn, pid, ausser=(), nur_menschen=False)") == [1]
    assert _nur_menschen_fehlt("gruende_zaehlen(conn, pid, nur_menschen=wert)") == [1]
    assert _nur_menschen_fehlt("gruende_zaehlen(conn, pid, ausser=(), nur_menschen=True)") == []
    assert _nur_menschen_fehlt("def f():\n    liste, _ = gruende_zaehlen(conn, pid, ausser=(), nur_menschen=True)\n") == []


def test_waechter_die_ki_aussortierung_fragt_die_gruende_nur_ueber_den_filter():
    quelle = (SRC / "services" / "auto_aussortierung.py").read_text(encoding="utf-8")
    assert _aufrufe(quelle, "gruende_zaehlen"), "die Auto-Aussortierung zaehlt keine Gruende mehr? Dann diesen Waechter nachziehen"
    assert _nur_menschen_fehlt(quelle) == [], "gruende_zaehlen ohne nur_menschen=True in der KI-Aussortierung (#1239)"
    assert _aufrufe(quelle, "get_recent_user_dismissals"), "die Beispiele kommen aus get_recent_user_dismissals"


def test_waechter_die_beispiele_fragen_die_eine_funktion():
    quelle = (SRC / "database.py").read_text(encoding="utf-8")
    methode = next(k for k in ast.walk(ast.parse(quelle))
                   if isinstance(k, ast.FunctionDef) and k.name == "get_recent_user_dismissals")
    text = ast.get_source_segment(quelle, methode)
    assert _aufrufe(text, "urteilsgruende_des_menschen"), "get_recent_user_dismissals fragt urteilsgruende_des_menschen nicht mehr (#1239)"


def test_waechter_gruende_zaehlen_fragt_die_eine_funktion():
    quelle = (SRC / "services" / "ablehnungsgruende.py").read_text(encoding="utf-8")
    funktion = next(k for k in ast.walk(ast.parse(quelle))
                    if isinstance(k, ast.FunctionDef) and k.name == "gruende_zaehlen")
    assert _aufrufe(ast.get_source_segment(quelle, funktion), "urteilsgruende_des_menschen")
