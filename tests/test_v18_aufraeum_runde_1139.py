"""#1139: Die Aufräum-Runde läuft einmal am Tag von selbst (Variante A) — und die beiden Fenster-Fehler sind weg.

Befund (01.10.2026): „Bewerbungen im Blick behalten“ hatte keinen automatischen Auslöser. Die Oberfläche versprach „PBP legt an und
schließt ab“; wer den Knopf nie drückte (die meisten), hatte keine Nachfass-Ketten, keine ablaufenden Bewerbungen, keine nachgeladenen
Anzeigentexte. Dazu zwei Fehler im Nachladen und in der URL-Prüfung: sie nahmen ohne Reihenfolge die ersten 24 bzw. 30 Kandidaten;
standen die im Backoff, wurden die übrigen nie versucht (gemessen: 30 Stellen ohne Text, 24 im Backoff, 0 versucht, 6 nie), und der
Fehlzähler verfiel nie — auch nicht bei Netzfehlern.

Hier: der Planer-Takt, der eigene Schalter für das Abschließen (Vorgabe aus), die gemeinsame Sperre, die feste Reihenfolge, der Verfall
des Fehlzählers, „Netzfehler zählen nicht“, die Schnittstellen und das Werkzeug. Alle Firmen und Namen sind Platzhalter.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import test_mcp_registry as reg
from bewerbungs_assistent.services import aufraeum_runde, automatik_scheduler, nachladen, text_nachzug


@pytest.fixture
def db(tmp_path):
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "runde.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Erika Musterfrau"})
    yield d
    d.close()


@pytest.fixture
def dash(db):
    import bewerbungs_assistent.dashboard as dash_mod
    alt = dash_mod._db
    dash_mod._db = db
    yield dash_mod
    dash_mod._db = alt


@pytest.fixture
def client(dash):
    from fastapi.testclient import TestClient
    return TestClient(dash.app)


def _stelle(db, nr: int, beschreibung: str = "", url: str | None = None):
    pid = db.get_active_profile_id()
    h = f"{pid}:runde{nr:03d}"
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, url, description, score, is_active, source, found_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (h, pid, f"Planer {nr}", "Musterbetrieb GmbH", url or f"https://example.com/stelle/{nr}", beschreibung, 50, 1, "manuell",
         "2026-10-01T10:00:00"))
    conn.commit()
    return h


def _alt(tage: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=tage)).isoformat()


def _alte_bewerbung(db, tage=120, status="beworben") -> str:
    aid = db.add_application({"company": "Altbetrieb GmbH", "title": "Konstrukteurin", "status": status,
                              "applied_at": (datetime.now() - timedelta(days=tage)).date().isoformat()})
    conn = db.connect()
    conn.execute("DELETE FROM application_events WHERE application_id=?", (aid,))
    conn.commit()
    return aid


def _status(db, aid) -> str:
    return db.connect().execute("SELECT status FROM applications WHERE id=?", (aid,)).fetchone()["status"]


# ══ Die Vorgabe ═══════════════════════════════════════════════════════════════════════════════

def test_die_runde_laeuft_vorgabemaessig_taeglich_und_das_abschliessen_ist_aus(db):
    s = db.get_automatik_settings()
    assert s["aufraeumen_intervall_tage"] == 1 and s["aufraeumen_last_at"] == ""
    assert aufraeum_runde.expire_automatisch(db) is False
    st = automatik_scheduler.compute_status(db)["aufraeumen"]
    assert st["intervall_tage"] == 1 and st["naechster_lauf"] == "faellig" and st["letzter_lauf"] is None


def test_ein_ausdruecklich_gesetztes_aus_bleibt_aus_und_nur_erlaubte_werte_gehen(db):
    db.set_automatik_settings(aufraeumen_intervall_tage=0)
    assert db.get_automatik_settings()["aufraeumen_intervall_tage"] == 0, "0 heisst aus, nicht 'nicht gesetzt'"
    db.set_automatik_settings(aufraeumen_intervall_tage=7)
    assert db.get_automatik_settings()["aufraeumen_intervall_tage"] == 7
    with pytest.raises(ValueError):
        db.set_automatik_settings(aufraeumen_intervall_tage=2)
    assert db.get_automatik_settings()["aufraeumen_intervall_tage"] == 7


def test_die_alten_ziele_bleiben_unberuehrt(db):
    s = db.get_automatik_settings()
    assert s["jobsuche_intervall_tage"] == 0 and s["lernen_intervall_tage"] == 0, "Jobsuche und Lernen bleiben aus, bis jemand sie einschaltet"
    db.set_automatik_settings(jobsuche_intervall_tage=3)
    s = db.get_automatik_settings()
    assert s["jobsuche_intervall_tage"] == 3 and s["aufraeumen_intervall_tage"] == 1


# ══ Der Planer-Takt ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def start_spion(monkeypatch, db):
    """Ersetzt das Starten der Runde durch einen Zaehler, damit der Takt allein gepruefte wird."""
    aufrufe = []

    def _fake(d, *a, **kw):
        aufrufe.append(kw.get("ausloeser", "automatik"))
        return {"status": aufrufe_status[0], "job_id": "x"}
    aufrufe_status = ["gestartet"]
    monkeypatch.setattr(automatik_scheduler, "run_aufraeumen_now", _fake)
    # die anderen Aufgaben des Takts (Sicherung, Lernen, Jobsuche) sind hier nicht der Gegenstand
    monkeypatch.setattr(automatik_scheduler, "run_lernen_now", lambda *a, **k: {"status": "lernen_aus"})
    monkeypatch.setattr(automatik_scheduler, "run_jobsuche_now", lambda *a, **k: {"status": "kein_netz"})
    import bewerbungs_assistent.services.sicherung as sicherung
    monkeypatch.setattr(sicherung, "taeglich", lambda *a, **k: None)
    return SimpleNamespace(aufrufe=aufrufe, status=aufrufe_status)


def test_der_takt_startet_die_runde_beim_ersten_mal_und_vermerkt_den_lauf(db, start_spion):
    automatik_scheduler._tick(db)
    assert start_spion.aufrufe == ["automatik"]
    assert db.get_automatik_settings()["aufraeumen_last_at"], "ein gestarteter Lauf gilt als gelaufen"


def test_der_takt_startet_sie_nicht_noch_einmal_am_selben_tag(db, start_spion):
    automatik_scheduler._tick(db)
    automatik_scheduler._tick(db)
    assert len(start_spion.aufrufe) == 1


def test_nach_einem_tag_ist_die_runde_wieder_faellig(db, start_spion):
    db.mark_automatik_run("aufraeumen", _alt(2))
    automatik_scheduler._tick(db)
    assert len(start_spion.aufrufe) == 1


def test_ist_das_intervall_aus_startet_der_takt_nichts(db, start_spion):
    db.set_automatik_settings(aufraeumen_intervall_tage=0)
    automatik_scheduler._tick(db)
    assert start_spion.aufrufe == []


def test_laeuft_schon_eine_runde_wird_nichts_vermerkt_und_der_naechste_takt_versucht_es_erneut(db, start_spion):
    start_spion.status[0] = "laeuft_bereits"
    automatik_scheduler._tick(db)
    assert db.get_automatik_settings()["aufraeumen_last_at"] == ""
    start_spion.status[0] = "gestartet"
    automatik_scheduler._tick(db)
    assert len(start_spion.aufrufe) == 2 and db.get_automatik_settings()["aufraeumen_last_at"]


def test_der_erste_takt_kommt_90_sekunden_nach_dem_start():
    """Der Planer wartet beim Start 90 Sekunden und tickt dann: die Runde ist dann sofort faellig (kein letzter Lauf)."""
    assert automatik_scheduler._INITIAL_DELAY == 90


def _warte_auf_job(db, job_id, sekunden=20):
    ende = time.time() + sekunden
    while time.time() < ende:
        j = db.get_background_job(job_id)
        if j and j["status"] in ("fertig", "fehler"):
            return j
        time.sleep(0.05)
    raise AssertionError(f"der Hintergrund-Job {job_id} wurde nicht fertig: {db.get_background_job(job_id)}")


def test_die_runde_laeuft_im_hintergrund_mit_eigenem_job_und_ergebnis(db, dash, monkeypatch):
    gesehen = []

    def _fake(ausloeser="knopf"):
        gesehen.append(ausloeser)
        return {"ran_at": "x", "ausloeser": ausloeser, "expire": {"expired_count": 2},
                "followup_reconciler": {"created_count": 3}}
    monkeypatch.setattr(dash, "run_auto_actions", _fake)
    erg = automatik_scheduler.run_aufraeumen_now(db)
    assert erg["status"] == "gestartet"
    job = _warte_auf_job(db, erg["job_id"])
    assert job["status"] == "fertig" and gesehen == ["automatik"]
    assert job["job_type"] == "aufraeumen", "die Runde hinterlaesst eine eigene Spur in background_jobs"
    assert "2 abgelaufen, 3 neue Nachfassungen" in (job.get("message") or "")
    assert (job.get("result") or {}).get("followup_reconciler", {}).get("created_count") == 3


def test_eine_laufende_runde_zaehlt_als_hintergrundarbeit_und_hat_einen_klartext(db, dash, monkeypatch):
    """Daten loeschen und Speicher aufraeumen fragen `datenordner.laufende_arbeit()`: eine laufende Runde schreibt in die Datenbank und muss
    dort stehen. Das gelingt nur, wenn ihr Thread mit "pbp-" beginnt - unter dem alten Namen sah sie niemand, und die Test-Suite (A22) beendete
    sie nicht vor dem Schliessen der Datenbank: ein Absturz auf C-Ebene im CI (Exit 139, 16.10.2026)."""
    import threading
    from bewerbungs_assistent.services import datenordner
    gate = threading.Event()

    def _langsam(ausloeser="knopf"):
        gate.wait(10)
        return {"ran_at": "x"}
    monkeypatch.setattr(dash, "run_auto_actions", _langsam)
    erg = automatik_scheduler.run_aufraeumen_now(db)
    try:
        assert erg["status"] == "gestartet"
        laufend = [n for n in datenordner.laufende_arbeit() if "aufraeumen" in n]
        assert laufend and all(n.startswith("pbp-") for n in laufend), laufend
        assert datenordner.arbeit_klartext(laufend) == "die Aufräum-Runde"
    finally:
        gate.set()
        _warte_auf_job(db, erg["job_id"])


def test_eine_zweite_runde_startet_nicht_solange_eine_laeuft(db, dash, monkeypatch):
    import threading
    gate = threading.Event()

    def _langsam(ausloeser="knopf"):
        gate.wait(10)
        return {"ran_at": "x"}
    monkeypatch.setattr(dash, "run_auto_actions", _langsam)
    erste = automatik_scheduler.run_aufraeumen_now(db)
    assert erste["status"] == "gestartet"
    zweite = automatik_scheduler.run_aufraeumen_now(db)
    assert zweite == {"status": "laeuft_bereits"}
    gate.set()
    _warte_auf_job(db, erste["job_id"])


def test_ein_fehler_in_der_runde_wird_der_job_mit_meldung_nicht_ein_stilles_ende(db, dash, monkeypatch):
    def _kaputt(ausloeser="knopf"):
        raise RuntimeError("Netz weg")
    monkeypatch.setattr(dash, "run_auto_actions", _kaputt)
    erg = automatik_scheduler.run_aufraeumen_now(db)
    job = _warte_auf_job(db, erg["job_id"])
    assert job["status"] == "fehler" and "Netz weg" in (job.get("message") or "")


# ══ Die Runde selbst: Abschliessen nur mit Schalter, Knopf immer ═══════════════════════════════

SCHRITTE = ("_run_followup_ueberholt", "_run_auto_followup_reconciler", "_run_auto_classify_emails", "_run_auto_classify_documents",
            "_run_auto_deep_analysis", "_run_analyze_user_patterns", "_run_scraper_probe", "_run_extract_contacts",
            "_run_auto_refetch_descriptions", "_run_snapshot_backfill", "_run_url_aging_check", "_run_check_stale_applications",
            "_run_elwosa_speak")


@pytest.fixture
def runde(dash, monkeypatch):
    """Die echte Runde mit echtem Abschliessen; alle uebrigen Schritte sind leere Ersatzfunktionen (kein Netz, keine KI)."""
    aufrufe: dict = {}
    for name in SCHRITTE:
        def _leer(*a, _n=name, **k):
            aufrufe[_n] = k or (a[1:] if len(a) > 1 else None)
            return {}
        monkeypatch.setattr(dash, name, _leer)
    return SimpleNamespace(aufrufe=aufrufe)


def test_der_knopf_schliesst_immer_ab_auch_bei_ausgeschaltetem_schalter(db, dash, runde):
    aid = _alte_bewerbung(db)
    assert aufraeum_runde.expire_automatisch(db) is False
    erg = dash.run_auto_actions("knopf")
    assert erg["expire"]["expired_count"] == 1 and _status(db, aid) == "abgelaufen"
    assert erg["ausloeser"] == "knopf"


def test_der_automatische_lauf_schliesst_ohne_schalter_nicht_ab(db, dash, runde):
    aid = _alte_bewerbung(db)
    erg = dash.run_auto_actions("automatik")
    assert _status(db, aid) == "beworben", "eine Bewerbung aendert ihren Stand nicht ueber Nacht, nur weil jemand ein Update installiert hat"
    assert erg["expire"] == {"expired_count": 0, "expired": [], "uebersprungen": "schalter_aus"}
    assert erg["ausloeser"] == "automatik"


def test_der_automatische_lauf_schliesst_mit_schalter_ab(db, dash, runde):
    aid = _alte_bewerbung(db)
    aufraeum_runde.expire_automatisch_setzen(db, True)
    erg = dash.run_auto_actions("automatik")
    assert erg["expire"]["expired_count"] == 1 and _status(db, aid) == "abgelaufen"


def test_die_uebrigen_schritte_laufen_auch_ohne_schalter(db, dash, runde):
    dash.run_auto_actions("automatik")
    assert set(runde.aufrufe) == set(SCHRITTE), set(SCHRITTE) - set(runde.aufrufe)


def test_der_automatische_lauf_holt_mehr_als_der_knopf(db, dash, runde):
    dash.run_auto_actions("knopf")
    knopf = dict(runde.aufrufe)
    dash.run_auto_actions("automatik")
    assert knopf["_run_auto_refetch_descriptions"] == {"max_jobs": 8} and knopf["_run_url_aging_check"] == {"max_jobs": 10}
    assert runde.aufrufe["_run_auto_refetch_descriptions"] == {"max_jobs": 16}
    assert runde.aufrufe["_run_url_aging_check"] == {"max_jobs": 25}


def test_der_letzte_lauf_nennt_wer_ihn_ausgeloest_hat_und_der_planer_rechnet_ab_dann(db, dash, runde):
    assert aufraeum_runde.letzter_lauf(db) == {"am": "", "von": ""}
    dash.run_auto_actions("automatik")
    l = aufraeum_runde.letzter_lauf(db)
    assert l["am"] and l["von"] == "automatik"
    assert db.get_automatik_settings()["aufraeumen_last_at"], "auch der Planer sieht den Lauf"
    dash.run_auto_actions("knopf")
    assert aufraeum_runde.letzter_lauf(db)["von"] == "knopf"


def test_knopf_und_planer_teilen_eine_sperre(dash, runde):
    assert dash._auto_actions_sperre.acquire(blocking=False)
    try:
        assert dash.run_auto_actions("knopf") == {"status": "laeuft_bereits"}
        assert dash.run_auto_actions("automatik") == {"status": "laeuft_bereits"}
    finally:
        dash._auto_actions_sperre.release()
    assert dash.run_auto_actions("knopf").get("status") != "laeuft_bereits"


def test_die_sperre_wird_auch_nach_einem_fehler_freigegeben(dash, monkeypatch):
    monkeypatch.setattr(dash, "_run_auto_actions_inner", lambda now, ausloeser="knopf": (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(RuntimeError):
        dash.run_auto_actions("knopf")
    assert dash._auto_actions_sperre.acquire(blocking=False), "die Sperre haengt nach einem Fehler"
    dash._auto_actions_sperre.release()


# ══ Das Nachladen: feste Reihenfolge, Verfall, Netzfehler ═════════════════════════════════════

def test_die_auswahl_nimmt_nie_versuchte_zuerst_dann_die_am_laengsten_wartende(db):
    h = [_stelle(db, i) for i in range(6)]
    text_nachzug.versuch_vermerken(db, h[0])  # zuletzt versucht
    db.set_setting(f"refetch_last:{h[1]}", _alt(5))
    db.set_setting(f"refetch_last:{h[2]}", _alt(9))
    wahl = text_nachzug.auswahl(db, limit=6)
    nie = [x for x in wahl[:3]]
    assert set(nie) == {h[3], h[4], h[5]}, wahl
    assert wahl[3:] == [h[2], h[1], h[0]], "dann die am laengsten nicht versuchte zuerst"


def test_die_auswahl_ueberspringt_stellen_im_backoff_und_zaehlt_sie(db):
    h = [_stelle(db, i) for i in range(4)]
    for x in h[:2]:
        db.set_setting(f"refetch_fail:{x}", "3")
        text_nachzug.versuch_vermerken(db, x)
    erg = text_nachzug.auswahl_befund(db, limit=10)
    assert set(erg["hashes"]) == set(h[2:]) and erg["im_backoff"] == 2 and erg["kandidaten"] == 4


def test_der_fall_aus_dem_issue_24_im_backoff_6_nie_versucht(db):
    """30 Stellen ohne Text, 24 im Backoff: die ersten 24 nach Zeilennummer waren genau die im Backoff — 6 kamen nie dran."""
    h = [_stelle(db, i) for i in range(30)]
    for x in h[:24]:
        db.set_setting(f"refetch_fail:{x}", "3")
        text_nachzug.versuch_vermerken(db, x)
    wahl = text_nachzug.auswahl(db, limit=24)
    assert set(wahl) == set(h[24:]), "genau die sechs nie versuchten"


def test_ein_fehlzaehler_verfaellt_nach_vierzehn_tagen(db):
    h = _stelle(db, 1)
    db.set_setting(f"refetch_fail:{h}", "3")
    db.set_setting(f"refetch_last:{h}", _alt(text_nachzug.FEHLZAEHLER_VERFALL_TAGE - 1))
    assert text_nachzug.auswahl(db, limit=5) == [], "gestern noch drei Fehlversuche: weiter im Backoff"
    db.set_setting(f"refetch_last:{h}", _alt(text_nachzug.FEHLZAEHLER_VERFALL_TAGE + 1))
    assert text_nachzug.auswahl(db, limit=5) == [h], "nach dem Verfall bekommt sie eine frische Runde"
    assert text_nachzug._fehlversuche(db, h) == 0


def test_ein_zaehler_ohne_zeitstempel_aus_dem_altbestand_gilt_als_verfallen(db):
    """Vor 1.8.0 gab es keinen Zeitstempel: wer seit Monaten im Backoff steht, bekommt jetzt eine neue Runde."""
    h = _stelle(db, 1)
    db.set_setting(f"refetch_fail:{h}", "3")
    assert text_nachzug.auswahl(db, limit=5) == [h]


def test_nach_dem_verfall_faengt_der_zaehler_bei_eins_an(db):
    h = _stelle(db, 1)
    db.set_setting(f"refetch_fail:{h}", "3")
    db.set_setting(f"refetch_last:{h}", _alt(30))
    text_nachzug.fehlversuch_zaehlen(db, h)
    assert text_nachzug._fehlversuche(db, h) == 1


def _befund(status, http=None, text=""):
    return nachladen.Befund(status=status, http_status=http, text=text)


def _holen(db, hashes, befunde, **kw):
    folge = iter(befunde)

    def _fake(url, client, timeout=15):
        return next(folge)
    import unittest.mock as mock
    with mock.patch.object(nachladen, "beschreibung_holen", _fake):
        return text_nachzug.holen(db, hashes, client=object(), **kw)


def test_ein_netzfehler_zaehlt_nicht_gegen_die_stelle(db):
    h = _stelle(db, 1)
    erg = _holen(db, [h], [_befund(nachladen.FEHLER)], max_jobs=5)
    assert erg["netzfehler"] == 1 and erg["fehlgeschlagen"] == 0
    assert text_nachzug._fehlversuche(db, h) == 0, "ohne Netz hat die Stelle nichts falsch gemacht"
    assert db.get_setting(f"refetch_last:{h}", ""), "aber der Versuch steht fest - die naechste Auswahl nimmt zuerst andere"


def test_zu_viele_anfragen_zaehlen_auch_nicht(db):
    h = _stelle(db, 1)
    erg = _holen(db, [h], [_befund(nachladen.GEBLOCKT, http=429)], max_jobs=5)
    assert erg["netzfehler"] == 1 and text_nachzug._fehlversuche(db, h) == 0


def test_drei_netzfehler_hintereinander_beenden_die_schleife(db):
    h = [_stelle(db, i) for i in range(6)]
    erg = _holen(db, h, [_befund(nachladen.FEHLER)] * 6, max_jobs=6)
    assert erg["abgebrochen"] == "netz" and erg["versucht"] == 3, "ohne Netz hilft jeder weitere Abruf nur dem Zeitlimit"
    assert erg["offen"] == 3 and erg["fehlgeschlagen"] == 0


def test_ein_erfolg_unterbricht_die_folge_der_netzfehler(db):
    h = [_stelle(db, i) for i in range(5)]
    erfolg = _befund(nachladen.GELESEN, 200, "Aufgaben und Anforderungen. " * 10)
    erg = _holen(db, h, [_befund(nachladen.FEHLER), _befund(nachladen.FEHLER), erfolg, _befund(nachladen.FEHLER),
                         _befund(nachladen.FEHLER)], max_jobs=5)
    assert erg["abgebrochen"] == "" and erg["versucht"] == 5 and erg["geholt"] == 1


def test_eine_verschwundene_anzeige_und_eine_leere_seite_zaehlen_weiter(db):
    a, b, c = (_stelle(db, i) for i in range(3))
    erg = _holen(db, [a, b, c], [_befund(nachladen.WEG, 404), _befund(nachladen.LEBT_UNLESBAR, 200),
                                 _befund(nachladen.GEBLOCKT, 403)], max_jobs=5)
    assert erg["fehlgeschlagen"] == 3 and erg["netzfehler"] == 0
    assert all(text_nachzug._fehlversuche(db, x) == 1 for x in (a, b, c))


def test_der_auto_nachzug_holt_in_fester_reihenfolge_und_erreicht_die_hinteren(db, dash, monkeypatch):
    """Der Fall aus dem Issue Ende zu Ende: 30 Stellen, 24 im Backoff - die sechs ohne Versuch kommen dran."""
    h = [_stelle(db, i) for i in range(30)]
    for x in h[:24]:
        db.set_setting(f"refetch_fail:{x}", "3")
        text_nachzug.versuch_vermerken(db, x)
    import unittest.mock as mock
    with mock.patch.object(nachladen, "beschreibung_holen",
                           lambda *a, **k: _befund(nachladen.GELESEN, 200, "Aufgaben und Anforderungen. " * 10)):
        erg = dash._run_auto_refetch_descriptions("2026-10-12T08:00:00", max_jobs=8)
    assert erg["processed"] == 6 and erg["successes"] == 6, erg
    assert erg["skipped_backoff"] == 24 and erg["found_candidates"] == 30


# ══ Die URL-Pruefung: dasselbe Fenster, dieselbe Behandlung ═══════════════════════════════════

def _gesundheit(monkeypatch, status_name="OK"):
    from bewerbungs_assistent.services import url_health
    geprueft: list[str] = []

    def _fake(url, title, client=None):
        geprueft.append(url)
        return SimpleNamespace(status=getattr(url_health.HealthStatus, status_name), should_dismiss=False)
    monkeypatch.setattr(url_health, "check_job_url_health", _fake)
    return geprueft


def test_die_url_pruefung_kommt_ueber_die_ersten_dreissig_hinaus(db, dash, monkeypatch):
    for i in range(40):
        _stelle(db, i, beschreibung="x" * 200)
    geprueft = _gesundheit(monkeypatch)
    for _ in range(5):
        dash._run_url_aging_check("2026-10-12T08:00:00", max_jobs=5)
    assert len(set(geprueft)) == 25, "fuenf Laeufe zu je fuenf: fuenfundzwanzig verschiedene (vorher hoechstens die ersten 15)"


def test_eine_pruefung_ohne_ergebnis_rueckt_die_stelle_nach_hinten(db, dash, monkeypatch):
    """Zeitueberschreitung oder gesperrt: kein 'ok', also kein 24-Stunden-Backoff - sie stuende bei jedem Lauf wieder vorn."""
    for i in range(12):
        _stelle(db, i, beschreibung="x" * 200)
    geprueft = _gesundheit(monkeypatch, "TIMEOUT")
    dash._run_url_aging_check("2026-10-12T08:00:00", max_jobs=4)
    erste = list(geprueft)
    geprueft.clear()
    dash._run_url_aging_check("2026-10-12T08:00:00", max_jobs=4)
    assert len(erste) == 4 and len(geprueft) == 4 and not (set(erste) & set(geprueft)), (erste, geprueft)


# ══ Schnittstellen und Werkzeug ═══════════════════════════════════════════════════════════════

def test_der_status_nennt_intervall_naechsten_lauf_schalter_und_ausloeser(client, db, dash, runde):
    j = client.get("/api/auto-actions/status").json()
    assert j["intervall_tage"] == 1 and j["naechster_lauf"] == "faellig" and j["expire_automatisch"] is False
    assert j["last_run_at"] == "" and j["last_run_by"] == "" and j["laeuft"] is False
    client.post("/api/auto-actions/run")
    j = client.get("/api/auto-actions/status").json()
    assert j["last_run_at"] and j["last_run_by"] == "knopf"
    # der Status spiegelt den Schalter in beide Richtungen (nicht nur die Vorgabe)
    aufraeum_runde.expire_automatisch_setzen(db, True)
    assert client.get("/api/auto-actions/status").json()["expire_automatisch"] is True
    db.set_automatik_settings(aufraeumen_intervall_tage=7)
    assert client.get("/api/auto-actions/status").json()["intervall_tage"] == 7


def test_der_schalter_laesst_sich_setzen_und_nimmt_nur_wahr_oder_falsch(client, db):
    assert client.put("/api/auto-actions/settings", json={"expire_automatisch": True}).json()["gespeichert"]["expire_automatisch"] is True
    assert aufraeum_runde.expire_automatisch(db) is True
    assert client.put("/api/auto-actions/settings", json={"expire_automatisch": "ja"}).status_code == 400
    assert aufraeum_runde.expire_automatisch(db) is True, "ein ungueltiger Wert aendert nichts"
    client.put("/api/auto-actions/settings", json={"expire_automatisch": False})
    assert aufraeum_runde.expire_automatisch(db) is False


def test_das_intervall_laesst_sich_ueber_die_automatik_schnittstelle_setzen(client, db):
    j = client.put("/api/automatik/settings", json={"aufraeumen_intervall_tage": 7}).json()
    assert j["aufraeumen"]["intervall_tage"] == 7
    assert client.put("/api/automatik/settings", json={"aufraeumen_intervall_tage": 2}).status_code == 400
    assert client.get("/api/automatik/settings").json()["aufraeumen"]["intervall_tage"] == 7


def test_ein_laufender_knopf_wird_dem_aufrufer_gesagt(client, dash):
    assert dash._auto_actions_sperre.acquire(blocking=False)
    try:
        r = client.post("/api/auto-actions/run")
        assert r.status_code == 200 and r.json() == {"status": "laeuft_bereits"}
    finally:
        dash._auto_actions_sperre.release()


@pytest.fixture
def werkzeuge(tmp_path):
    mcp, db = reg._build_test_server(tmp_path)
    yield mcp, db
    db.close()


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def test_das_werkzeug_stellt_intervall_und_schalter(werkzeuge):
    mcp, db = werkzeuge
    erg = _call(mcp, "automatik_setzen", {"aufraeumen_intervall_tage": 0, "bewerbungen_abschliessen": True})
    assert erg["status"] == "gespeichert"
    assert erg["aufraeumen"]["intervall_tage"] == 0 and erg["bewerbungen_abschliessen"] is True
    stand = _call(mcp, "automatik_status", {})
    assert stand["aufraeumen"]["intervall_tage"] == 0 and stand["bewerbungen_abschliessen"] is True
    assert "letzter_lauf_aufraeumen" in stand


def test_das_werkzeug_nimmt_nur_erlaubte_intervalle(werkzeuge):
    mcp, db = werkzeuge
    erg = _call(mcp, "automatik_setzen", {"aufraeumen_intervall_tage": 5})
    assert "fehler" in erg


# ══ Abgrenzung (DoD 8d) ═══════════════════════════════════════════════════════════════════════

def test_die_drei_verwandten_module_gibt_es_nebeneinander_und_kennen_sich():
    """`aufraeum_runde` (was die Runde ist und wer sie ausloest), `automatik_scheduler` (der Takt, der sie startet) und
    `text_nachzug` (der Schritt "Anzeigentexte nachladen"): drei Dinge, kein Duplikat."""
    for modul in (aufraeum_runde, automatik_scheduler, text_nachzug):
        assert modul.__doc__ and len(modul.__doc__) > 200
    assert "automatik_scheduler" in aufraeum_runde.__doc__ and "text_nachzug" in aufraeum_runde.__doc__
    assert "aufraeum_runde" in automatik_scheduler.__doc__
