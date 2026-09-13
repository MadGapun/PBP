"""Tests fuer #1030 und #1032: die Stellenliste filtert und sortiert den Bestand.

#1030: "Umfang Vollzeit" zeigte 0 statt 59 Stellen, weil jeder Filter nur
auf die 20 geladenen Stellen wirkte. #1032: "neueste zuerst" fehlte — und
waere mit demselben Fehler wertlos gewesen, weil die erste Seite nach
Score geladen wird.

Dieser Teil prueft den Dienst ohne Datenbank. Die Tests am Endpunkt
stehen darunter.
"""
import importlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import datenguete  # noqa: E402
from bewerbungs_assistent.services import stellen_liste as sl  # noqa: E402

TEXT = "Ausfuehrliche Stellenbeschreibung mit genug Inhalt. " * 3


def _stelle(nr, **extra):
    job = {
        "hash": f"h{nr:03d}", "title": f"Stelle {nr}", "company": f"Firma {nr}",
        "description": TEXT, "score": float(100 - nr), "source": "manuell",
        "found_at": f"2026-09-{(nr % 28) + 1:02d}T10:00:00+00:00",
    }
    job.update(extra)
    return job


# --------------------------------------------------- #1030 AK 1: der Meldefall


def test_ak1_umfang_vollzeit_findet_stellen_hinter_der_ersten_seite():
    """Woertlich der Bericht: 20 geladen, die passenden stehen ab Platz 24."""
    jobs = [_stelle(i) for i in range(30)]
    for i in (24, 26, 28):
        jobs[i]["arbeitsumfang"] = "vollzeit"
    jobs[27]["arbeitsumfang"] = "beides"
    antwort = sl.aufbereiten(jobs, {"arbeitsumfang": "vollzeit"}, limit=20)
    assert antwort["treffer"] == 4
    assert {j["hash"] for j in antwort["jobs"]} == {
        "h024", "h026", "h027", "h028"}
    assert antwort["total"] == 30, "total bleibt der Bestand der Ansicht"


def test_seitenweises_laden_blaettert_im_gefilterten_ergebnis():
    """#1030 Erwartung 3."""
    jobs = [_stelle(i, source="a" if i % 2 else "b") for i in range(30)]
    s1 = sl.aufbereiten(jobs, {"source": "a"}, limit=10, offset=0)
    s2 = sl.aufbereiten(jobs, {"source": "a"}, limit=10, offset=10)
    assert s1["treffer"] == s2["treffer"] == 15
    assert s1["has_more"] is True and s2["has_more"] is False
    assert len(s2["jobs"]) == 5
    assert not {j["hash"] for j in s1["jobs"]} & {j["hash"] for j in s2["jobs"]}


# ------------------------------------------------ #1030 AK 2: jeder Filter


def test_suchtext_durchsucht_titel_firma_und_beschreibung():
    jobs = [_stelle(1, title="Buchhaltung Kreditoren"),
            _stelle(2, company="Buchhaltung Nord"),
            _stelle(3, description=TEXT + " Erfahrung in der Buchhaltung"),
            _stelle(4)]
    assert sl.aufbereiten(jobs, {"query": "BUCHHALTUNG"})["treffer"] == 3


@pytest.mark.parametrize("feld,param,wert", [
    ("source", "source", "arbeitnow"),
    ("remote_level", "remote", "remote"),
    ("employment_type", "employment_type", "freelance"),
])
def test_gleichheitsfilter(feld, param, wert):
    jobs = [_stelle(1, **{feld: wert}), _stelle(2, **{feld: "anders"})]
    antwort = sl.aufbereiten(jobs, {param: wert})
    assert [j["hash"] for j in antwort["jobs"]] == ["h001"]


def test_score_ab():
    jobs = [_stelle(1, score=12), _stelle(2, score=9.9), _stelle(3, score=10)]
    assert sl.aufbereiten(jobs, {"min_score": "10"})["treffer"] == 2


@pytest.mark.parametrize("gesucht,erwartet", [
    ("vollzeit", {"h001", "h003"}),
    ("teilzeit", {"h002", "h003"}),
    ("beides", {"h003"}),
])
def test_umfang_beides_zaehlt_fuer_beide_richtungen(gesucht, erwartet):
    jobs = [_stelle(1, arbeitsumfang="vollzeit"),
            _stelle(2, arbeitsumfang="teilzeit"),
            _stelle(3, arbeitsumfang="beides"),
            _stelle(4, arbeitsumfang="unbekannt")]
    antwort = sl.aufbereiten(jobs, {"arbeitsumfang": gesucht})
    assert {j["hash"] for j in antwort["jobs"]} == erwartet


def test_beworbene_ausblenden_ueber_die_uebergebene_hashform():
    """Der Dienst vergleicht beide Seiten in DERSELBEN Form."""
    jobs = [_stelle(1, hash="p1:aaa"), _stelle(2, hash="p1:bbb")]
    antwort = sl.aufbereiten(
        jobs, {"beworbene_ausblenden": "true"}, beworbene=["aaa"],
        hash_von=lambda h: str(h).split(":", 1)[-1])
    assert [j["hash"] for j in antwort["jobs"]] == ["p1:bbb"]
    assert antwort["treffer_mit_beworbenen"] == 2


def test_nur_ohne_beschreibung_nutzt_die_schwelle_des_nadeloehrs():
    kurz = "x" * (datenguete.MIN_BESCHREIBUNG - 1)
    grenze = "x" * datenguete.MIN_BESCHREIBUNG
    jobs = [_stelle(1, description=kurz), _stelle(2, description=grenze),
            _stelle(3, description="")]
    antwort = sl.aufbereiten(jobs, {"nur_ohne_beschreibung": True})
    assert {j["hash"] for j in antwort["jobs"]} == {"h001", "h003"}


@pytest.mark.parametrize("stand,erwartet", [
    ("ungeprueft", {"h001", "h004"}),
    ("gesichtet", {"h002"}),
    ("beurteilt", {"h003"}),
])
def test_pruefstand(stand, erwartet):
    jobs = [_stelle(1, pruefstand={"art": "ungeprueft"}),
            _stelle(2, pruefstand={"art": "gesichtet"}),
            _stelle(3, pruefstand={"art": "beurteilt"}),
            _stelle(4)]  # ohne Befund gilt als ungeprueft
    assert {j["hash"] for j in sl.aufbereiten(
        jobs, {"pruefstand": stand})["jobs"]} == erwartet


# ------------------------------------ #1030 AK 7: "nur mit Gehalt" ohne Schaetzung


def test_ak7_nur_mit_gehalt_zaehlt_schaetzungen_nicht():
    jobs = [
        _stelle(1, salary_min=50000, salary_estimated=0),
        _stelle(2, salary_min=48000, salary_estimated=1),
        _stelle(3),
        _stelle(4, salary_min=60, salary_type="stuendlich", salary_estimated=0),
    ]
    antwort = sl.aufbereiten(jobs, {"nur_mit_gehalt": "true"})
    assert {j["hash"] for j in antwort["jobs"]} == {"h001", "h004"}


# ------------------------------------------------ #1030 AK 3 / #1032 AK 1-2


def test_score_aufsteigend_beginnt_beim_niedrigsten_im_bestand():
    jobs = [_stelle(i) for i in range(30)]
    antwort = sl.aufbereiten(jobs, sort="score_asc", limit=5)
    assert antwort["jobs"][0]["score"] == 71.0


def test_gehalt_absteigend_ueber_den_bestand():
    jobs = [_stelle(i, salary_min=40000 + i) for i in range(25)]
    jobs[24]["salary_max"] = 99000
    antwort = sl.aufbereiten(jobs, sort="salary_desc", limit=3)
    assert antwort["jobs"][0]["hash"] == "h024"


def test_1032_neueste_und_aelteste_nach_found_at():
    jobs = [_stelle(1, found_at="2026-09-01T09:00:00+00:00"),
            _stelle(2, found_at="2026-09-13T09:00:00+00:00"),
            _stelle(3, found_at="2026-09-05T09:00:00+00:00"),
            _stelle(4, found_at=None)]
    neu = [j["hash"] for j in sl.aufbereiten(jobs, sort="found_desc")["jobs"]]
    alt = [j["hash"] for j in sl.aufbereiten(jobs, sort="found_asc")["jobs"]]
    assert neu == ["h002", "h003", "h001", "h004"]
    assert alt == ["h001", "h003", "h002", "h004"], (
        "Ohne Datum steht hinten, in BEIDEN Richtungen")


def test_1032_das_veroeffentlichungsdatum_ordnet_nicht():
    """Bewusst nur found_at (Melder-Begruendung)."""
    jobs = [_stelle(1, found_at="2026-09-13T09:00:00+00:00",
                    veroeffentlicht_am="2026-09-01"),
            _stelle(2, found_at="2026-09-12T09:00:00+00:00")]
    assert [j["hash"] for j in sl.aufbereiten(
        jobs, sort="found_desc")["jobs"]] == ["h001", "h002"]


def test_rangfolge_pinned_dann_pflichttreffer_dann_datenguete():
    jobs = [
        _stelle(1, score=99, muss_tor={"ohne_pflichttreffer": True}),
        _stelle(2, score=50, description=""),
        _stelle(3, score=10),
        _stelle(4, score=1, is_pinned=1),
    ]
    reihe = [j["hash"] for j in sl.aufbereiten(jobs, sort="score_desc")["jobs"]]
    assert reihe == ["h004", "h003", "h002", "h001"]
    mitmischen = [j["hash"] for j in sl.aufbereiten(
        jobs, sort="score_desc", guete_umgang=datenguete.MITMISCHEN)["jobs"]]
    assert mitmischen == ["h004", "h002", "h003", "h001"]


def test_protokoll_sortiert_nach_dem_zeitpunkt_der_aussortierung():
    """#1010-Ordnung, die im Browser vom Score ueberschrieben wurde."""
    jobs = [_stelle(1, score=90, dismissed_at="2026-09-01T10:00:00+00:00"),
            _stelle(2, score=10, dismissed_at="2026-09-12T10:00:00+00:00")]
    assert [j["hash"] for j in sl.aufbereiten(
        jobs, sort="dismissed_desc")["jobs"]] == ["h002", "h001"]


# ----------------------------------------------------- Zeitfenster (#1010)


def test_zeitfenster_ohne_zeitpunkt_nur_unter_alle():
    jetzt = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
    jobs = [_stelle(1, dismissed_at=(jetzt - timedelta(days=2)).isoformat()),
            _stelle(2, dismissed_at=(jetzt - timedelta(days=20)).isoformat()),
            _stelle(3, dismissed_at=None)]
    def hashes(fenster):
        return {j["hash"] for j in sl.aufbereiten(
            jobs, {"zeitfenster": fenster}, jetzt=jetzt)["jobs"]}
    assert hashes("7tage") == {"h001"}
    assert hashes("30tage") == {"h001", "h002"}
    assert hashes("alle") == {"h001", "h002", "h003"}


# ------------------------------------------------- AK 6: Auswahllisten


def test_ak6_optionen_ueber_die_ganze_ansicht():
    jobs = [_stelle(i) for i in range(30)]
    jobs[29].update(source="arbeitnow", remote_level="remote",
                    employment_type="freelance", arbeitsumfang="vollzeit")
    jobs[0].update(remote_level="unbekannt", arbeitsumfang="unbekannt")
    antwort = sl.aufbereiten(jobs, limit=20)
    assert "arbeitnow" in antwort["optionen"]["source"]
    assert antwort["optionen"]["remote"] == ["remote"]
    assert antwort["optionen"]["arbeitsumfang"] == ["vollzeit"]
    assert "freelance" in antwort["optionen"]["employment_type"]


# -------------------------------------------------- unbekannte Werte (#988)


@pytest.mark.parametrize("roh,sort", [
    ({}, "neueste"), ({"pruefstand": "gelesen"}, ""),
    ({"zeitfenster": "gestern"}, ""), ({"min_score": "viel"}, ""),
])
def test_unbekannte_werte_werden_benannt_nicht_ignoriert(roh, sort):
    with pytest.raises(sl.UngueltigerParameter) as fehler:
        sl.aufbereiten([_stelle(1)], roh, sort)
    assert fehler.value.erlaubt


def test_ohne_filter_ist_es_keine_listenanfrage():
    assert not sl.ist_listenanfrage({})
    assert not sl.ist_listenanfrage({"query": "", "zeitfenster": "alle"})
    assert sl.ist_listenanfrage({"query": "x"})
    assert sl.ist_listenanfrage({}, sort="found_desc")


# ======================================================= Endpunkt GET /api/jobs


@pytest.fixture
def client(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    db = database.Database(db_path=tmp_path / "liste.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.switch_profile(db.create_profile("Liste"))

    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient

    vorher = dash._db
    dash._db = db
    try:
        yield TestClient(dash.app), db
    finally:
        dash._db = vorher
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def _bestand(db, anzahl=30, **je):
    jobs = []
    for i in range(anzahl):
        job = {
            "hash": f"e{i:03d}", "title": f"Rolle {i:03d}",
            "company": f"Firma {i:03d}", "url": f"https://example.com/1030/{i}",
            "source": "manuell", "_manual_entry": True,
            "description": TEXT * 2, "score": float(anzahl - i),
        }
        for feld, fn in je.items():
            wert = fn(i)
            if wert is not None:
                job[feld] = wert
        jobs.append(job)
    db.save_jobs(jobs)
    return jobs


def test_endpunkt_ak1_umfang_mit_seitengroesse_20(client):
    tc, db = client
    _bestand(db, 30)
    con = db.connect()
    for i in (24, 26, 28):
        con.execute("UPDATE jobs SET arbeitsumfang='vollzeit' WHERE hash=?",
                    (db.resolve_job_hash(f"e{i:03d}"),))
    con.commit()
    antwort = tc.get("/api/jobs?active=true&limit=20&offset=0"
                     "&arbeitsumfang=vollzeit").json()
    assert antwort["treffer"] == 3
    assert antwort["total"] == 30
    assert sorted(j["title"] for j in antwort["jobs"]) == [
        "Rolle 024", "Rolle 026", "Rolle 028"]


def test_endpunkt_sortiert_neueste_zuerst_ueber_den_bestand(client):
    tc, db = client
    _bestand(db, 25)
    con = db.connect()
    con.execute("UPDATE jobs SET found_at='2026-01-01T00:00:00+00:00'")
    con.execute("UPDATE jobs SET found_at='2026-09-13T08:00:00+00:00' WHERE hash=?",
                (db.resolve_job_hash("e024"),))
    con.commit()
    antwort = tc.get("/api/jobs?active=true&limit=20&sort=found_desc").json()
    assert antwort["jobs"][0]["title"] == "Rolle 024"


def test_endpunkt_unbekannte_sortierung_ist_400(client):
    tc, db = client
    _bestand(db, 3)
    r = tc.get("/api/jobs?active=true&limit=20&sort=neueste")
    assert r.status_code == 400
    assert "found_desc" in r.text


def test_endpunkt_beworbene_ausblenden_rechnet_der_server(client):
    tc, db = client
    _bestand(db, 4)
    voll = db.resolve_job_hash("e001")
    db.add_application({"title": "Rolle 001", "company": "Firma 001",
                        "job_hash": db._public_job_hash(voll),
                        "status": "beworben"})
    antwort = tc.get("/api/jobs?active=true&limit=20"
                     "&beworbene_ausblenden=true").json()
    assert "Rolle 001" not in {j["title"] for j in antwort["jobs"]}
    assert antwort["treffer"] == 3
    assert antwort["treffer_mit_beworbenen"] == 4


def test_endpunkt_abgeschlossene_bewerbungen_blenden_nicht_aus(client):
    """Isolierender Fall aus der Gegenprobe: ohne ihn machte das Ausbauen
    der Archiv-Pruefung nichts rot.

    Nebenbefund bei #1030: der Browser hatte fuer "beworben" eine eigene
    Liste ohne `arbeitgeber_ausgefallen` (#779). Eine Stelle, deren
    Bewerbung abgeschlossen ist, gehoert nicht unter "beworbene
    ausblenden" — sonst verschwindet sie wegen einer Bewerbung, die es in
    der Sache nicht mehr gibt.
    """
    tc, db = client
    _bestand(db, 3)
    for nr, status in (("e000", "beworben"), ("e001", "abgelehnt"),
                       ("e002", "arbeitgeber_ausgefallen")):
        db.add_application({
            "title": f"Rolle {nr[1:]}", "company": f"Firma {nr[1:]}",
            "job_hash": db._public_job_hash(db.resolve_job_hash(nr)),
            "status": status})
    antwort = tc.get("/api/jobs?active=true&limit=20"
                     "&beworbene_ausblenden=true").json()
    assert sorted(j["title"] for j in antwort["jobs"]) == ["Rolle 001", "Rolle 002"]


def test_endpunkt_ausgeblendet_filtert_ebenso(client):
    """#1030 AK 1 gilt fuer BEIDE Ansichten — eine Fassung."""
    tc, db = client
    _bestand(db, 6, source=lambda i: "arbeitnow" if i < 3 else "manuell")
    for i in range(6):
        db.dismiss_job(db.resolve_job_hash(f"e{i:03d}"), "falsches_fachgebiet")
    antwort = tc.get("/api/jobs?active=false&limit=20&source=arbeitnow"
                     "&sort=dismissed_desc").json()
    assert antwort["treffer"] == 3
    assert all(j.get("herkunft") for j in antwort["jobs"])


def test_endpunkt_alte_vertraege_bleiben(client):
    """Dashboard, Onboarding und Verknuepfungsdialog rufen ohne Filter."""
    tc, db = client
    _bestand(db, 5)
    assert isinstance(tc.get("/api/jobs?active=true").json(), list)
    assert isinstance(tc.get("/api/jobs?active=false").json(), list)
    # ApplicationsPage schickt `filter=alle` — einen Parameter, den es nie
    # gab. Die Antwort muss trotzdem `jobs` tragen.
    alt = tc.get("/api/jobs?filter=alle&limit=100").json()
    assert len(alt["jobs"]) == 5
