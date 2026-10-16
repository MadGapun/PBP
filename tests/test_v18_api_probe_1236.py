"""#1236 Stufe 3 -- die Messprobe `scripts/api_probe.py`.

Abnahmekriterium 8: Trockenlauf ist Standard, gesendet wird nur mit `--senden`; Referenz sind nur Urteile des Menschen; die
geprueften Stelle steht nie im Beispielblock; die Probe laeuft nur auf einer Kopie. Der Echtlauf selbst (mit Schluessel) gehoert
NICHT in die Suite: hier steht er mit einem Testdoppel am Transport, und kein Test erreicht das Netz.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import api_probe  # noqa: E402
import _netzsperre  # noqa: E402
from _api_hilfen import FakeTransport, TESTSCHLUESSEL, antwort, fehlerantwort  # noqa: E402

from bewerbungs_assistent.services import api_backend  # noqa: E402
from bewerbungs_assistent.services.llm_service import Backend, LLMService, TaskResult  # noqa: E402


class Sammler:
    def __init__(self):
        self.zeilen: list[str] = []

    def __call__(self, text=""):
        self.zeilen.append(str(text))

    @property
    def text(self) -> str:
        return "\n".join(self.zeilen)


@pytest.fixture
def demo_db(tmp_path):
    """Die erfundene Datenbank der Probe, wie sie `--demo` baut (Quelle fuer die Kopie)."""
    pfad = api_probe.demo_datenbank(tmp_path / "quelle")
    os.environ.pop("BA_DATA_DIR", None)
    return pfad


class OfflineDienst(LLMService):
    """Ein LLMService, der nie nach Ollama fragt: auch `get_status(force_refresh=True)` bleibt ohne HTTP-Aufruf."""

    def _check_ollama(self):
        self._status.ollama_available = False
        self._status.available_models = []
        self._status.models_detail = []
        self._status.error = "im Test nicht gefragt"


def offline_fabrik(db):
    svc = OfflineDienst(db)
    svc._status.user_state = "off"
    svc._status.last_check_at = 9999999999
    return svc


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv(api_backend.ENV_SCHLUESSEL, TESTSCHLUESSEL)


def _lauf(argv, **kw):
    ausgabe = Sammler()
    kw.setdefault("dienst_fabrik", offline_fabrik)
    rc = api_probe.main(argv, ausgabe=ausgabe, **kw)
    return rc, ausgabe


def _titel(prompt: str) -> str:
    return re.search(r"  Titel: (.+)", prompt).group(1).strip()


def _beispielblock(prompt: str) -> str:
    if "BEISPIELE" not in prompt:
        return ""
    return prompt.split("BEISPIELE", 1)[1].split("Nutze diese Muster", 1)[0]


@pytest.fixture(autouse=True)
def _feste_zeit(monkeypatch):
    """Der Prompt traegt Datum und Uhrzeit; zwei Laeufe duerfen sich nicht an einer Minute unterscheiden."""
    from bewerbungs_assistent.services import llm_service
    monkeypatch.setattr(llm_service, "_datums_kontext", lambda: "WICHTIG — fester Zeitbezug fuer den Test.\n\n")


# ============================================================ Der Trockenlauf ist der Standard

def test_ohne_senden_wird_nichts_gesendet_und_der_erste_prompt_steht_da(demo_db):
    transport = FakeTransport(antwort())
    api_backend.transport_setzen(transport)
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--anzahl", "10"])
    assert rc == 0 and transport.anzahl == 0 and _netzsperre.VERSUCHE == []
    text = ausgabe.text
    assert "TROCKENLAUF: es wird nichts gesendet" in text and "Es wurde nichts gesendet." in text
    assert "Der erste Prompt, genau so wie er abgeschickt würde" in text
    assert "Du bewertest ob eine Stelle zu einem Bewerber-Profil passt." in text and "FRAGE: Wuerde es Sinn machen" in text
    assert "Gesendet wird je Stelle:" in text and "Nicht gesendet:" in text
    assert "Geschätzt: etwa" in text and "höchstens" in text and "US-Dollar" in text
    assert "model=\"claude-haiku-5-5\"" in text and "thinking={\"type\": \"disabled\"}" in text
    assert TESTSCHLUESSEL not in text and api_backend.ENV_SCHLUESSEL in text


def test_der_trockenlauf_braucht_weder_schluessel_noch_netz(demo_db):
    assert not api_backend.schluessel_vorhanden()
    rc, _ = _lauf(["--quelle", str(demo_db), "--anzahl", "10"])
    assert rc == 0 and _netzsperre.VERSUCHE == []


def test_der_angezeigte_prompt_ist_der_prompt_der_gesendet_wird(demo_db, key):
    """Trockenlauf und Echtlauf zeigen/senden dieselbe erste Nachricht (die Zeit ist festgesetzt)."""
    rc, trocken = _lauf(["--quelle", str(demo_db), "--anzahl", "10"])
    angezeigt = trocken.text.split("-" * 72)[1].strip("\n")
    transport = FakeTransport(antwort())
    rc, _ = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "1"], transport=transport)
    assert transport.anzahl == 10
    assert transport.aufrufe[0]["body"]["messages"][0]["content"].strip("\n") == angezeigt


def test_die_demo_ist_erfunden_und_senden_damit_ist_verboten(key):
    rc, ausgabe = _lauf(["--demo", "--senden", "--budget-usd", "1"])
    assert rc == 2 and "erfunden" in ausgabe.text


# ============================================================ Der Echtlauf hat Bedingungen

def test_senden_verlangt_ein_budget(demo_db, key):
    transport = FakeTransport(antwort())
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--senden"], transport=transport)
    assert rc == 2 and "--budget-usd" in ausgabe.text and transport.anzahl == 0


def test_senden_verlangt_einen_schluessel(demo_db):
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--senden", "--budget-usd", "1"], transport=FakeTransport(antwort()))
    assert rc == 2 and api_backend.ENV_SCHLUESSEL in ausgabe.text


@pytest.mark.parametrize("budget", ["-1", "viel", "99999", "nan"])
def test_ein_ungueltiges_budget_wird_abgewiesen(demo_db, key, budget):
    transport = FakeTransport(antwort())
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--senden", "--budget-usd", budget], transport=transport)
    assert rc == 2 and transport.anzahl == 0, ausgabe.text


def test_ohne_quelle_und_ohne_demo_wird_nichts_geraten():
    rc, ausgabe = _lauf([])
    assert rc == 2 and "--quelle" in ausgabe.text and "--demo" in ausgabe.text


def test_ein_unbekanntes_modell_wird_abgewiesen(demo_db):
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--modell", "gibt-es-nicht"])
    assert rc == 2 and "claude-haiku-5-5" in ausgabe.text


def test_eine_fehlende_datenbank_ist_ein_klarer_fehler(tmp_path):
    rc, ausgabe = _lauf(["--quelle", str(tmp_path / "nichts.db")])
    assert rc == 2 and "Keine Datenbank gefunden" in ausgabe.text


# ============================================================ Nur auf einer Kopie

def _fingerabdruck(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def test_das_original_bleibt_unberuehrt_und_die_kopie_liegt_im_wegwerf_ordner(demo_db, key):
    vorher = (_fingerabdruck(demo_db), demo_db.stat().st_mtime_ns, sorted(p.name for p in demo_db.parent.iterdir()))
    gesehen = {}
    echt = api_probe.datenbank_oeffnen

    def spion(ziel, ordner):
        db = echt(ziel, ordner)
        gesehen["pfad"] = str(db.db_path)
        gesehen["env"] = os.environ.get("BA_DATA_DIR")
        return db

    with patch.object(api_probe, "datenbank_oeffnen", spion):
        rc, _ = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "1"],
                      transport=FakeTransport(antwort()))
    assert rc == 0
    assert gesehen["env"] and gesehen["env"] in gesehen["pfad"] and str(demo_db.parent) not in gesehen["pfad"]
    assert "pbp-api-probe-" in gesehen["pfad"]
    nachher = (_fingerabdruck(demo_db), demo_db.stat().st_mtime_ns, sorted(p.name for p in demo_db.parent.iterdir()))
    assert nachher == vorher, "Das Original darf weder geschrieben noch durch eine WAL-Datei veraendert werden"
    assert not Path(gesehen["pfad"]).exists(), "Der Wegwerf-Ordner ist weg"
    assert os.environ.get("BA_DATA_DIR") != gesehen["env"], "Der Datenordner des Aufrufers kommt zurueck"


def test_behalten_laesst_die_kopie_stehen(demo_db):
    gesehen = {}
    echt = api_probe.datenbank_oeffnen

    def spion(ziel, ordner):
        gesehen["ordner"] = Path(ordner)
        return echt(ziel, ordner)

    with patch.object(api_probe, "datenbank_oeffnen", spion):
        rc, _ = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--behalten"])
    try:
        assert rc == 0 and (gesehen["ordner"] / "pbp.db").is_file()
    finally:
        import shutil
        shutil.rmtree(gesehen["ordner"].parent, ignore_errors=True)


def test_ein_ordner_als_quelle_geht_auch(demo_db):
    rc, _ = _lauf(["--quelle", str(demo_db.parent), "--anzahl", "10"])
    assert rc == 0


def test_die_kopie_beginnt_mit_leeren_zaehlern_und_ohne_lokalen_rueckfall(demo_db, tmp_path):
    from bewerbungs_assistent.database import Database
    quelle = Database(db_path=demo_db)
    quelle.initialize()
    api_backend.verbuchen(quelle, 100, 10, 12_345)
    quelle.set_profile_setting("llm_local_state", "active")
    quelle.close()
    ordner = tmp_path / "kopie"
    kopie = api_probe.kopie_anlegen(demo_db, ordner)
    db = api_probe.datenbank_oeffnen(kopie, ordner)
    try:
        assert api_backend.zaehler_lesen(db)["mikro_usd"] == 0, "Die Probe zaehlt nur ihre eigenen Aufrufe"
        assert db.get_profile_setting("llm_local_state") == "off"
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


# ============================================================ Die Referenz: nur Urteile des Menschen

def _datenbank(tmp_path):
    from bewerbungs_assistent.database import Database
    pfad = api_probe.demo_datenbank(tmp_path / "ref")
    os.environ.pop("BA_DATA_DIR", None)
    db = Database(db_path=pfad)
    db.initialize()
    return db


def test_die_referenz_zaehlt_nur_urteile_des_menschen(tmp_path):
    db = _datenbank(tmp_path)
    try:
        u = api_probe.urteile_lesen(db)
        assert len(u["beworben"]) == 12 and len(u["aussortiert"]) == 12
        grund = {j["dismiss_reason"] for j in u["aussortiert"]}
        assert grund == {"zu_junior", "falsches_fachgebiet", "zu_senior", "falsche_branche", "zeitarbeit", "befristet"}
        assert all(j["dismissed_by"] != "automatik" for j in u["aussortiert"])
        assert not ({j["hash"] for j in u["beworben"]} & {j["hash"] for j in u["aussortiert"]})
        aus = u["ausgeschlossen"]
        assert aus["Grund betrifft Entfernung, Gehalt oder Firmenwahl, nicht den Anzeigentext"] == 3
        assert aus["Grund sagt nichts über die Passung (sonstiges, Dublikat, Freitext ...)"] == 3
        assert aus["von der Automatik aussortiert (kein Urteil des Menschen)"] == 3
    finally:
        db.close()


def test_bewerbung_erstellt_ist_das_gegenteil_einer_ablehnung(tmp_path):
    db = _datenbank(tmp_path)
    try:
        u = api_probe.urteile_lesen(db)
        for j in u["beworben"]:
            assert j["dismiss_reason"] == "bewerbung_erstellt", "Diese Stellen sind aus der Liste, WEIL der Mensch sich beworben hat"
        assert not [j for j in u["aussortiert"] if j["dismiss_reason"] == "bewerbung_erstellt"]
    finally:
        db.close()


def test_eine_fachliche_aussortierung_durch_die_automatik_zaehlt_nicht(tmp_path):
    """Dieselbe Begruendung, anderer Urheber: `dismissed_by='automatik'` ist kein Urteil des Menschen."""
    db = _datenbank(tmp_path)
    try:
        db.save_jobs([{"hash": "auto1", "title": "Auto Zu Junior", "company": "Beispiel AG", "url": "https://example.com/a1",
                       "source": "manuell", "description": "Anzeigentext. " * 20, "score": 3}])
        db.dismiss_job("auto1", "zu_junior", herkunft="automatik")
        db.save_jobs([{"hash": "auto2", "title": "Alt Auto", "company": "Beispiel AG", "url": "https://example.com/a2",
                       "source": "manuell", "description": "Anzeigentext. " * 20, "score": 3}])
        db.connect().execute("UPDATE jobs SET is_active=0, dismiss_reason='auto:zu_junior' WHERE hash LIKE '%auto2'")
        db.connect().commit()
        u = api_probe.urteile_lesen(db)
        titel = {j["title"] for j in u["aussortiert"]}
        assert "Auto Zu Junior" not in titel and "Alt Auto" not in titel
        assert len(u["aussortiert"]) == 12
    finally:
        db.close()


def test_ohne_anzeigentext_gibt_es_kein_urteil(tmp_path):
    db = _datenbank(tmp_path)
    try:
        db.save_jobs([{"hash": "kurz1", "title": "Zu kurz", "company": "Beispiel AG", "url": "https://example.com/k1",
                       "source": "manuell", "description": "zu kurz", "score": 3}])
        db.dismiss_job("kurz1", "zu_junior")
        u = api_probe.urteile_lesen(db)
        assert "Zu kurz" not in {j["title"] for j in u["aussortiert"]}
        assert u["ausgeschlossen"]["selbst aussortiert, aber ohne ausreichenden Anzeigentext"] == 1
    finally:
        db.close()


def test_die_stichprobe_ist_ausgewogen_wiederholbar_und_wechselt_die_klassen_ab(tmp_path):
    db = _datenbank(tmp_path)
    try:
        u = api_probe.urteile_lesen(db)
        plan = api_probe.stichprobe(u, 10, 1236)
        assert [e["klasse"] for e in plan] == ["beworben", "aussortiert"] * 5
        assert [e["erwartet"] for e in plan] == ["PASST", "PASST_NICHT"] * 5
        assert len({e["job"]["hash"] for e in plan}) == 10
        wieder = api_probe.stichprobe(u, 10, 1236)
        assert [e["job"]["hash"] for e in plan] == [e["job"]["hash"] for e in wieder]
        anders = api_probe.stichprobe(u, 10, 99)
        assert [e["job"]["hash"] for e in plan] != [e["job"]["hash"] for e in anders]
        alle = api_probe.stichprobe(u, 200, 1)
        assert len(alle) == 24, "Mehr als vorhanden gibt es nicht: je Klasse so viele wie die kleinere Klasse hat"
        ungerade = api_probe.stichprobe(u, 11, 1)
        assert len(ungerade) == 10
    finally:
        db.close()


def test_zu_wenig_urteile_ist_ein_eigener_zustand_mit_den_zahlen(tmp_path):
    u = {"beworben": [{"hash": str(i)} for i in range(4)], "aussortiert": [{"hash": str(i)} for i in range(30)],
         "ausgeschlossen": {}}
    with pytest.raises(api_probe.ProbeFehler) as info:
        api_probe.stichprobe(u, 40, 1)
    assert info.value.code == 3 and "4 beworbene" in info.value.text and "30 selbst aussortierte" in info.value.text


def test_zu_wenig_urteile_im_ganzen_lauf_gibt_exit_3(tmp_path):
    pfad = tmp_path / "wenig"
    pfad.mkdir()
    from bewerbungs_assistent.database import Database
    os.environ["BA_DATA_DIR"] = str(pfad)
    db = Database(db_path=pfad / "pbp.db")
    db.initialize()
    db.save_profile({"name": "Leer"})
    db.close()
    os.environ.pop("BA_DATA_DIR", None)
    rc, ausgabe = _lauf(["--quelle", str(pfad)])
    assert rc == 3 and "Zu wenig eigene Urteile" in ausgabe.text


# ============================================================ Die geprueften Stelle steht nie im Beispielblock

def test_die_gepruefte_stelle_steht_nicht_in_den_eigenen_beispielen(tmp_path):
    job = {"title": "Werkstudent Zeichnen 17", "company": "Beispiel AG 17", "description": "Text. " * 20}
    beispiele = [{"title": "WERKSTUDENT zeichnen 17", "company": "beispiel ag 17", "dismiss_reason": "zu_junior"},
                 {"title": "Andere Stelle", "company": "Andere AG", "dismiss_reason": "zu_senior"}]
    nutz = api_probe.nutzlast_bauen(job, {"profile_skills": [], "profile_position": "", "profile_seniority": ""}, beispiele, [])
    assert [b["title"] for b in nutz["recent_dismissals"]] == ["Andere Stelle"]


@pytest.mark.parametrize("flags", [["--bereinigt"], []])
def test_in_keinem_gesendeten_prompt_steht_die_geprueften_stelle_unter_den_beispielen(demo_db, key, flags):
    transport = FakeTransport(antwort())
    rc, _ = _lauf(["--quelle", str(demo_db), "--anzahl", "24", "--senden", "--budget-usd", "1", *flags], transport=transport)
    assert rc == 0 and transport.anzahl == 24
    for aufruf in transport.aufrufe:
        prompt = aufruf["body"]["messages"][0]["content"]
        assert _titel(prompt) not in _beispielblock(prompt), _titel(prompt)


def test_bereinigt_nimmt_nur_urteile_des_menschen_in_die_beispiele(demo_db, key):
    transport = FakeTransport(antwort())
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "1", "--bereinigt"],
                        transport=transport)
    assert rc == 0
    prompt = transport.aufrufe[0]["body"]["messages"][0]["content"]
    assert "bewerbung_erstellt" not in prompt and "profil_match_negativ" not in prompt
    assert "Grund: zu_junior" in prompt or "Grund: zeitarbeit" in prompt or "Grund: befristet" in prompt
    assert "Achtung:" not in ausgabe.text


def test_ohne_bereinigung_zeigt_die_probe_dass_der_betrieb_systemgruende_mitgibt(demo_db):
    """Die Probe misst den Betrieb, wie er ist -- und sagt dazu, was darin steckt (Befund der Messprobe)."""
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--anzahl", "10"])
    assert "Achtung:" in ausgabe.text and "profil_match_negativ" in ausgabe.text and "--bereinigt" in ausgabe.text


# ============================================================ Der Echtlauf mit Testdoppel: Auswertung

def _skript(urteile):
    """Antworten nach der Reihenfolge des Plans (beworben, aussortiert, beworben ...), je (Text, ein, aus)."""
    return [antwort(t, ein=e, aus=a) for t, e, a in urteile]


def test_die_auswertung_zaehlt_richtig_und_nennt_die_fehler_je_stelle(demo_db, key, tmp_path):
    transport = FakeTransport(*_skript([
        ("PASST | Konstruktion passt zum Profil.", 1000, 20),                    # beworben, richtig
        ("PASST_NICHT | Zu junge Stelle.", 1000, 20),                           # aussortiert, richtig
        ("PASST_NICHT | Wirkt fachfremd (Irrtum der KI).", 1000, 20),           # beworben, FALSCH aussortiert
        ("PASST | Sieht passend aus (Irrtum der KI).", 1000, 20),               # aussortiert, nicht erkannt
        ("UNSICHER | Schwer zu sagen.", 1000, 20),                              # beworben, unsicher
        ("PASST_NICHT | Falsche Branche.", 1000, 20),                           # aussortiert, richtig
        ("PASST | passt.", 1000, 20), ("PASST_NICHT | nein.", 1000, 20),
        ("PASST | passt.", 1000, 20), ("PASST_NICHT | nein.", 1000, 20),
    ]))
    ausgabedatei = tmp_path / "bericht.json"
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "1",
                         "--ausgabe", str(ausgabedatei)], transport=transport)
    assert rc == 0 and transport.anzahl == 10
    text = ausgabe.text
    assert "Übereinstimmung mit deinem Urteil: 7 von 10 beantworteten Stellen (70 %)" in text, text
    assert "Zu Unrecht aussortiert (PASST_NICHT, obwohl du dich beworben hast): 1" in text
    assert "Wirkt fachfremd (Irrtum der KI)" in text
    assert "Nicht aussortiert (PASST, obwohl du selbst aussortiert hast): 1" in text
    assert "Sieht passend aus (Irrtum der KI)" in text and "(dein Grund:" in text
    assert "Unsicher (keine Entscheidung): 1" in text
    # 10 Aufrufe zu 1000 Tokens ein, 20 aus: 10*(1000*0,10 + 20*0,50) = 1.100 Mikro-Dollar
    assert "Verbrauch: 10.000 Tokens ein, 200 aus, 0,0011 US-Dollar" in text, text
    assert "Gesamt über die API: 10 Aufrufe, 10.000 Tokens ein, 200 aus, 0,0011 US-Dollar von 1,00 US-Dollar Budget." in text
    bericht = json.loads(ausgabedatei.read_bytes().decode("utf-8"))
    a = bericht["varianten"][0]["auswertung"]
    assert (a["stellen"], a["beantwortet"], a["uebereinstimmung"], a["unsicher"]) == (10, 10, 7, 1)
    assert (a["zu_unrecht_aussortiert"], a["nicht_aussortiert"]) == (1, 1)
    assert bericht["verbrauch_mikro"] == 1100
    assert TESTSCHLUESSEL not in ausgabedatei.read_text(encoding="utf-8") and TESTSCHLUESSEL not in text
    assert b"\r\n" not in ausgabedatei.read_bytes(), "Bytes schreiben, nicht Path.write_text: kein CRLF"


def test_der_bericht_nennt_titel_aber_keine_firmen(demo_db, key):
    transport = FakeTransport(antwort("PASST_NICHT | nein."), antwort("PASST | ja."))
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "1"], transport=transport)
    aus = ausgabe.text.split("── API,", 1)[1]
    assert "Konstrukteur" in aus or "Werkstudent" in aus
    assert "Beispiel AG" not in aus and "Beispiel Maschinenbau" not in aus


def test_der_echtlauf_geht_ueber_den_betriebsweg_mit_geschwaerzten_firmennamen(demo_db, key):
    transport = FakeTransport(antwort())
    rc, _ = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "1", "--bereinigt"],
                  transport=transport)
    for aufruf in transport.aufrufe:
        block = _beispielblock(aufruf["body"]["messages"][0]["content"])
        assert "[Firma]" in block and "Beispiel AG" not in block, "Dieselbe Schwaerzung wie im Betrieb"
        assert aufruf["body"]["model"] == "claude-haiku-5-5" and aufruf["body"]["thinking"] == {"type": "disabled"}


def test_die_firmennamen_variante_vergleicht_mit_und_ohne_und_stellt_die_schwaerzung_wieder_her(demo_db, key):
    echt = api_backend._beispiele_schwaerzen
    transport = FakeTransport(antwort())
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "1", "--bereinigt",
                         "--firmennamen"], transport=transport)
    assert rc == 0 and transport.anzahl == 20
    erste, zweite = transport.aufrufe[:10], transport.aufrufe[10:]
    assert all("Beispiel AG" not in _beispielblock(a["body"]["messages"][0]["content"]) for a in erste)
    assert any("Beispiel AG" in _beispielblock(a["body"]["messages"][0]["content"]) for a in zweite)
    assert api_backend._beispiele_schwaerzen is echt, "Die Schwaerzung gilt danach wieder"
    assert "Variante: Firmennamen der Beispiele geschwärzt (wie im Betrieb)" in ausgabe.text
    assert "Variante: Firmennamen der Beispiele im Klartext (nur zum Vergleich)" in ausgabe.text


# ============================================================ Harter Stopp

def test_an_der_budgetgrenze_haelt_die_probe_an_und_laesst_eine_ausgewogene_teilmenge(demo_db, key):
    transport = FakeTransport(antwort(ein=40_000, aus=2_000))  # 5.000 Mikro-Dollar je Aufruf
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "0.02"], transport=transport)
    assert rc == 4
    assert transport.anzahl == 4, "20.000 Mikro-Dollar: vier Aufrufe, der fuenfte wird nicht mehr gesendet"
    text = ausgabe.text
    assert "Abbruch nach 4 von 10 Stellen: das Budget der Probe ist erreicht." in text
    assert "Übereinstimmung mit deinem Urteil: 2 von 4 beantworteten Stellen" in text or "von 4 beantworteten" in text
    assert "Gesamt über die API: 4 Aufrufe" in text and "0,02 US-Dollar von 0,02 US-Dollar Budget" in text


def test_ein_budget_von_null_sendet_nichts_und_sagt_es(demo_db, key):
    transport = FakeTransport(antwort())
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "0"], transport=transport)
    assert rc == 2 and transport.anzahl == 0 and "größer als null" in ausgabe.text


def test_die_probe_rechnet_wie_der_betrieb_den_schlimmsten_fall_des_naechsten_aufrufs_mit(demo_db, key):
    """Sonnet, ein Cent Budget: der erste Aufruf kostet 6.000 Mikro-Dollar; fuer den zweiten bliebe nur ein Rest unter dem
    schlimmsten Fall (rund 5.100). Er wird nicht gesendet, obwohl das Budget noch nicht aufgebraucht ist."""
    transport = FakeTransport(antwort(ein=2_000, aus=200))
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "0.01",
                         "--modell", "claude-sonnet-5-5"], transport=transport)
    assert rc == 4 and transport.anzahl == 1
    assert "Abbruch nach 1 von 10 Stellen: das Budget der Probe ist erreicht." in ausgabe.text
    assert "reicht für diesen Aufruf nicht mehr" in ausgabe.text
    assert "Gesamt über die API: 1 Aufrufe" in ausgabe.text and "0,006 US-Dollar von 0,01 US-Dollar" in ausgabe.text


def test_ein_harter_fehler_haelt_die_probe_an_statt_sechsmal_dasselbe_zu_holen(demo_db, key):
    transport = FakeTransport(fehlerantwort(401, "authentication_error", "invalid x-api-key"))
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "1"], transport=transport)
    assert rc == 4 and transport.anzahl == 1
    assert "Abbruch nach 0 von 10 Stellen" in ausgabe.text and "Schlüssel" in ausgabe.text


def test_ein_fehler_nur_dieser_stelle_haelt_die_probe_nicht_an(demo_db, key):
    leer = (200, {}, json.dumps({"content": [], "stop_reason": "end_turn",
                                 "usage": {"input_tokens": 10, "output_tokens": 1}}).encode())
    transport = FakeTransport(antwort("PASST | gut."), leer, antwort("PASST_NICHT | nein."))
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "1"], transport=transport)
    assert rc == 0 and transport.anzahl == 10
    assert "ohne Antwort (antwort_leer)" in ausgabe.text and "Ohne Antwort: 1 Stellen" in ausgabe.text


def test_die_probe_faellt_nie_auf_ollama_zurueck(demo_db, key):
    """Ein Rueckfall waere eine Antwort, die nicht von der API stammt, mitten in einer Messung der API."""
    transport = FakeTransport(fehlerantwort(401, "authentication_error", "x"))
    lokal = TaskResult(backend=Backend.LOCAL, success=True, payload={"decision": "PASST", "reason": "lokal"})
    with patch.object(LLMService, "_run_local", return_value=lokal) as lokal_aufruf:
        rc, _ = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "1"], transport=transport)
    assert rc == 4 and lokal_aufruf.call_count == 0


# ============================================================ Vergleich mit der lokalen KI

def _nach_titel(aufruf):
    """Ein Modell, das die Referenz kennt: Konstrukteur = PASST, alles andere = PASST_NICHT."""
    prompt = aufruf["body"]["messages"][0]["content"]
    return antwort("PASST | api." if "Titel: Konstrukteur" in prompt else "PASST_NICHT | api.")


class _OllamaDoppel:
    """Ein Dienst wie `LLMService`: die API-Seite ist die echte, die lokale KI antwortet nach Skript."""

    def __init__(self, db, verfuegbar=True):
        self.echt = offline_fabrik(db)
        self.verfuegbar = verfuegbar
        self.lokal_aufrufe = 0

    def run(self, task, payload):
        return self.echt.run(task, payload)

    def get_status(self, force_refresh=False):
        s = self.echt._status
        if self.verfuegbar:
            s.ollama_available, s.available_models, s.selected_model = True, ["modell:1b"], "modell:1b"
        return s

    def _run_local(self, task, payload):
        self.lokal_aufrufe += 1
        urteil = "PASST" if "Konstrukteur" in payload["job_title"] else "PASST_NICHT"
        return TaskResult(backend=Backend.LOCAL, success=True, payload={"decision": urteil, "reason": "lokal"},
                          metrics={"backend": "ollama"})


def test_mit_ollama_steht_dieselbe_auswertung_daneben(demo_db, key):
    erzeugt = []

    def fabrik(db):
        erzeugt.append(_OllamaDoppel(db))
        return erzeugt[0]

    transport = FakeTransport(entscheider=_nach_titel)
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "1", "--ollama"],
                        transport=transport, dienst_fabrik=fabrik)
    assert rc == 0 and erzeugt[0].lokal_aufrufe == 10
    text = ausgabe.text
    assert "Vergleich: dieselben Stellen durch die lokale KI (Ollama)" in text and "── Lokale KI (Ollama)" in text
    lokal = text.split("── Lokale KI (Ollama)")[1]
    assert "Übereinstimmung mit deinem Urteil: 10 von 10 beantworteten Stellen (100 %)" in lokal
    assert "Verbrauch:" not in lokal, "Die lokale KI kostet nichts: keine Kostenzeile"
    api = text.split("── API,")[1].split("Vergleich:")[0]
    assert "Übereinstimmung mit deinem Urteil: 10 von 10" in api and "Verbrauch:" in api


def test_ohne_laufendes_ollama_sagt_der_vergleich_warum_er_ausfaellt(demo_db, key):
    transport = FakeTransport(entscheider=_nach_titel)
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "1", "--ollama"],
                        transport=transport)
    assert rc == 0
    assert "Ollama läuft nicht oder hat kein Modell: kein Vergleich mit der lokalen KI." in ausgabe.text
    assert "── Lokale KI (Ollama)" not in ausgabe.text


def test_ein_fehler_der_lokalen_ki_kippt_die_probe_nicht(demo_db, key):
    class Kaputt(_OllamaDoppel):
        def _run_local(self, task, payload):
            raise ConnectionResetError("weg")

    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "1", "--ollama"],
                        transport=FakeTransport(antwort()), dienst_fabrik=Kaputt)
    assert rc == 0 and "ConnectionResetError" in ausgabe.text and "Ohne Antwort: 10 Stellen" in ausgabe.text


# ============================================================ Der Schluessel

def test_das_skript_liest_den_schluessel_nie_selbst_und_zeigt_ihn_nie():
    quelle = (ROOT / "scripts" / "api_probe.py").read_text(encoding="utf-8")
    assert "os.getenv" not in quelle and "environ.get(api_backend.ENV_SCHLUESSEL" not in quelle
    assert 'environ.get("PBP_ANTHROPIC_API_KEY' not in quelle and "environ['PBP_ANTHROPIC_API_KEY" not in quelle
    assert "_schluessel()" not in quelle, "Nur `api_backend` liest den Schluessel"


def test_die_ausgabe_zeigt_den_schluessel_in_keinem_lauf(demo_db, key):
    rc, ausgabe = _lauf(["--quelle", str(demo_db), "--anzahl", "10", "--senden", "--budget-usd", "1"],
                        transport=FakeTransport(antwort(), fehlerantwort(500, "api_error", f"x {TESTSCHLUESSEL}"),
                                                antwort()))
    assert TESTSCHLUESSEL not in ausgabe.text
