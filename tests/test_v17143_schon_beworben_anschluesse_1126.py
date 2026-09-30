"""Tests fuer v1.7.143 - #1126/#1117: "Schon beworben?" an den Anschluessen.

Erster Teil (`test_v17143_schon_beworben_1126.py`): die Erkennung und der
Dienst. Hier: wo sie angeschlossen ist - Dashboard-Liste und -Detail,
Werkzeug, Anlage, Suchlauf-Automatik, Elwosa. Ein Schutz zaehlt erst, wenn
er aufgerufen wird (DoD 8c): jeder Anschluss hat einen eigenen Test.

Alle Firmen sind erfunden.
"""
import asyncio
import logging

import pytest

from bewerbungs_assistent.services import bewerbungs_hinweis
from bewerbungs_assistent.services import stellen_automatik as automatik

URL_ALT = "https://karriere.beispiel.example/careers/jobs/solution-architect-plm-m-w-d-546057"
LANGER_TEXT = ("Aufgaben: Betreuung und Weiterentwicklung der PLM-Landschaft, "
               "Abstimmung mit den Fachbereichen und Steuerung externer "
               "Dienstleister. Anforderungen: Studium, mehrjaehrige "
               "Berufserfahrung, sichere Kommunikation in Deutsch und Englisch.")


def _werkzeug(db, name):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP Test")
    register_all(mcp, db, logging.getLogger("t"))

    def aufrufen(**kwargs):
        async def _run():
            tool = await mcp.get_tool(name)
            res = await tool.run(kwargs)
            return getattr(res, "structured_content", res)
        return asyncio.run(_run())
    return aufrufen


def _stelle(hash_, titel, firma, url, **mehr):
    stelle = {"hash": hash_, "title": titel, "company": firma,
              "location": "Hamburg", "url": url, "source": "stepstone",
              "description": LANGER_TEXT, "score": 40,
              "employment_type": "festanstellung"}
    stelle.update(mehr)
    return stelle


@pytest.fixture
def lage(tmp_db, monkeypatch):
    """Eine LAUFENDE Bewerbung und zwei Stellen derselben Firma: die Kopie
    der Anzeige (neue URL, umformulierter Titel) und eine andere Rolle."""
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    monkeypatch.setattr(dash, "_db", tmp_db)
    tmp_db.save_profile({"name": "Test"})
    aid = tmp_db.add_application({
        "title": "Teamleitung Enterprise Applications",
        "company": "Musterbetrieb Nord GmbH", "status": "beworben",
        "applied_at": "2026-09-07", "url": "https://mb.example/original"})
    tmp_db.save_jobs([
        _stelle("kopie1", "Teamleitung Enterprise Applications (m/w/d)",
                "musterbetrieb nord", "https://mb.example/kopie"),
        _stelle("andere1", "Sachbearbeitung Rechnungswesen",
                "Musterbetrieb Nord GmbH", "https://mb.example/rw"),
    ])
    return {"db": tmp_db, "client": TestClient(dash.app), "aid": aid}


# ══ Dashboard: Liste und Detail ══════════════════════════════════════════

def test_1126_dashboard_liste_zeigt_den_hinweis_fuer_die_kopie(lage):
    antwort = lage["client"].get("/api/jobs", params={"limit": 20}).json()
    jobs = {j["hash"]: j for j in antwort["jobs"]}
    kopie = jobs["kopie1"]
    assert kopie["repost_details"]["laeuft"] is True
    assert kopie["repost_details"]["bewerbung_id_voll"] == lage["aid"]
    assert "nicht noch einmal bewerben" in kopie["repost_warnung"]
    # Eine andere Rolle derselben Firma zeigt keinen Hinweis (AK 1).
    assert "repost_warnung" not in jobs["andere1"]
    assert "repost_details" not in jobs["andere1"]


def test_1126_dashboard_detail_zeigt_denselben_hinweis(lage):
    client = lage["client"]
    liste = {j["hash"]: j for j in
             client.get("/api/jobs", params={"limit": 20}).json()["jobs"]}
    detail = client.get("/api/jobs/kopie1").json()
    assert detail["repost_warnung"] == liste["kopie1"]["repost_warnung"]
    assert detail["repost_details"] == liste["kopie1"]["repost_details"]
    andere = client.get("/api/jobs/andere1").json()
    assert "repost_warnung" not in andere


def test_1126_werkzeug_und_dashboard_geben_dieselbe_antwort(lage):
    """Eine Frage, eine Funktion: derselbe Satz auf beiden Wegen."""
    stellen = _werkzeug(lage["db"], "stellen_anzeigen")()["stellen"]
    mcp_kopie = next(s for s in stellen if s["id"] == "kopie1")
    rest_kopie = next(
        j for j in lage["client"].get("/api/jobs", params={"limit": 20}
                                       ).json()["jobs"]
        if j["hash"] == "kopie1")
    assert mcp_kopie["repost_warnung"] == rest_kopie["repost_warnung"]
    assert mcp_kopie["repost_details"] == rest_kopie["repost_details"]


def test_1126_die_liste_prueft_nur_die_sichtbare_seite(lage, monkeypatch):
    """`_guete_anreichern` laeuft ueber den ganzen Bestand; diese Pruefung
    vergleicht jede Stelle mit jeder Bewerbung und darf es nicht."""
    lage["db"].save_jobs([
        _stelle(f"fuell{i}", f"Ganz andere Rolle {i}", f"Firma {i} GmbH",
                f"https://f{i}.example/j") for i in range(30)])
    aufrufe = []
    original = bewerbungs_hinweis.fuer_stelle

    def zaehlen(job, *args, **kwargs):
        aufrufe.append(job.get("hash"))
        return original(job, *args, **kwargs)

    monkeypatch.setattr(bewerbungs_hinweis, "fuer_stelle", zaehlen)
    antwort = lage["client"].get("/api/jobs", params={"limit": 5}).json()
    assert len(antwort["jobs"]) == 5
    assert len(aufrufe) == 5, aufrufe


def test_1126_die_ausgeblendet_ansicht_bekommt_keinen_hinweis(lage):
    """Aussortierte Stellen: dort geht es nicht mehr um "bewerben"."""
    lage["db"].dismiss_job(lage["db"].resolve_job_hash("kopie1"), "duplikat")
    antwort = lage["client"].get(
        "/api/jobs", params={"active": "false", "limit": 20}).json()
    for job in antwort["jobs"]:
        assert "repost_warnung" not in job


def test_945_lesen_veraendert_nichts(lage):
    """Eine Liste abzurufen darf nichts schreiben - auch nicht den Hinweis."""
    db = lage["db"]

    def stand():
        c = db.connect()
        return (
            [tuple(r) for r in c.execute(
                "SELECT hash, is_active, dismiss_reason, updated_at "
                "FROM jobs ORDER BY hash")],
            [tuple(r) for r in c.execute(
                "SELECT id, status, updated_at FROM applications "
                "ORDER BY id")])

    vorher = stand()
    lage["client"].get("/api/jobs", params={"limit": 20})
    lage["client"].get("/api/jobs/kopie1")
    assert stand() == vorher


# ══ Anlage (#1117) ═══════════════════════════════════════════════════════

def _abgelehnt(db, grund="Kein Bedarf mehr an der Position"):
    aid = db.add_application({
        "title": "Solution Architect PLM (m/w/d)", "company": "Société Beispiel",
        "status": "abgelehnt", "applied_at": "2026-05-12", "url": URL_ALT})
    db.connect().execute(
        "UPDATE applications SET rejection_reason=? WHERE id=?", (grund, aid))
    db.connect().commit()
    return aid


def test_1117_anlage_mit_gleicher_url_meldet_die_abgelehnte_bewerbung(tmp_db):
    """Der Praxisfall: Konzernname mit Akzent gegen Landesgesellschaft,
    Titel und URL zeichengleich. AK 1: Treffer samt ID, Datum, Absagegrund."""
    aid = _abgelehnt(tmp_db)
    res = _werkzeug(tmp_db, "stelle_manuell_anlegen")(
        titel="Solution Architect PLM (m/w/d)",
        firma="Societe Beispiel Deutschland GmbH", url=URL_ALT,
        beschreibung=LANGER_TEXT * 2, quelle="xing")
    assert res["status"] == "angelegt"
    assert res["warnung"] == "wiedergaenger_bewerbung"
    vorher = res["bewerbung_vorher"]
    assert vorher["bewerbung_id"] == aid[:8]
    assert vorher["beworben_am"] == "2026-05-12"
    assert vorher["status"] == "abgelehnt"
    assert vorher["ablehnungsgrund"]["text"] == "Kein Bedarf mehr an der Position"


def test_1117_die_url_allein_reicht_bei_anderem_titel_und_firma(tmp_db):
    """Isolierender Fall fuer die URL: weder Firma noch Titel passen."""
    aid = _abgelehnt(tmp_db)
    res = _werkzeug(tmp_db, "stelle_manuell_anlegen")(
        titel="Etwas voellig anderes", firma="Anderer Name GmbH",
        url=URL_ALT, beschreibung=LANGER_TEXT * 2, quelle="xing")
    assert res["warnung"] == "wiedergaenger_bewerbung"
    assert res["bewerbung_vorher"]["match_grund"] == "url_match"
    assert res["bewerbung_vorher"]["bewerbung_id"] == aid[:8]


def test_1117_der_akzent_allein_reicht_bei_neuer_url(tmp_db):
    """Isolierender Fall fuer den Akzent: die URL ist eine andere."""
    aid = _abgelehnt(tmp_db)
    res = _werkzeug(tmp_db, "stelle_manuell_anlegen")(
        titel="Solution Architect PLM (m/w/d)",
        firma="Societe Beispiel Deutschland GmbH",
        url="https://karriere.beispiel.example/careers/jobs/neu-1",
        beschreibung=LANGER_TEXT * 2, quelle="xing")
    assert res["warnung"] == "wiedergaenger_bewerbung"
    assert res["bewerbung_vorher"]["bewerbung_id"] == aid[:8]
    assert res["bewerbung_vorher"]["match_grund"] != "url_match"


def test_1117_eine_andere_stelle_ohne_gleiche_url_bleibt_ohne_hinweis(tmp_db):
    """#567 bleibt erfuellt: gleiche Firma, andere Stelle, andere URL."""
    _abgelehnt(tmp_db)
    res = _werkzeug(tmp_db, "stelle_manuell_anlegen")(
        titel="Sachbearbeitung Rechnungswesen", firma="Société Beispiel",
        url="https://karriere.beispiel.example/careers/jobs/rw-1",
        beschreibung=LANGER_TEXT * 2, quelle="xing")
    assert res["status"] == "angelegt"
    assert "warnung" not in res


# ══ Suchlauf-Automatik: der Setter zu `_repost_verdacht` (#1126) ═════════

def _aussortiert(db, hash_, titel, firma, grund):
    db.save_jobs([{
        "hash": hash_, "title": titel, "company": firma,
        "url": f"https://example.com/{hash_}", "source": "bundesagentur",
        "description": LANGER_TEXT, "score": 20}])
    db.dismiss_job(db.resolve_job_hash(hash_), grund)


def _wiedergaenger_historie(db, firma, praefix):
    """Zweimal `gehalt_zu_niedrig` bei derselben Firma: die dritte Stelle
    waere ein Wiedergaenger und wuerde aussortiert (#941)."""
    _aussortiert(db, f"{praefix}a", "PLM Berater (m/w/d)", firma,
                 "gehalt_zu_niedrig")
    _aussortiert(db, f"{praefix}b", "PLM Consultant", firma,
                 "gehalt_zu_niedrig")


def _frisch(hash_, titel, firma):
    return {"hash": hash_, "title": titel, "company": firma, "score": 30,
            "url": f"https://example.com/{hash_}", "source": "bundesagentur",
            "description": LANGER_TEXT}


def test_1126_eine_erkannte_wiederholung_wird_nicht_aussortiert(tmp_db):
    """AK: Wiederholung erkannt -> nicht automatisch aussortiert, mit
    Test ueber den SETTER. Die Kontrolle (Firma B ohne Bewerbung) zeigt,
    dass dieselbe Vorgeschichte sonst aussortiert."""
    _wiedergaenger_historie(tmp_db, "Beratungshaus Sued GmbH", "wa")
    _wiedergaenger_historie(tmp_db, "Werk Nord AG", "wb")
    tmp_db.add_application({
        "title": "PLM Architect (m/w/d)", "company": "Beratungshaus Sued GmbH",
        "status": "beworben", "applied_at": "2026-09-07",
        "url": "https://example.com/original"})
    a = _frisch("wa3", "PLM Architect (m/w/d)", "Beratungshaus Sued GmbH")
    b = _frisch("wb3", "PLM Architect (m/w/d)", "Werk Nord AG")
    erg = automatik.anwenden(tmp_db, [a, b])
    jobs = {j["hash"]: j for j in erg["jobs"]}
    assert jobs["wa3"].get("_repost_verdacht") is True
    assert jobs["wa3"].get("is_active", 1) != 0, "Wiederholung nie aussortieren"
    assert "_repost_verdacht" not in jobs["wb3"]
    assert jobs["wb3"]["is_active"] == 0
    assert erg["zaehler"]["automatisch_aussortiert"] == 1


def test_1126_ein_vermittler_verdacht_haelt_die_automatik_nicht_auf(tmp_db):
    """Nur die starke Aussage (frueher beworben) schuetzt vor dem
    Aussortieren; der Vermittler-Verdacht ist eine Frage an den Menschen."""
    _wiedergaenger_historie(tmp_db, "Beispielwerk AG", "wv")
    tmp_db.add_application({
        "title": "Berater PLM", "company": "Vermittler Nord GmbH",
        "status": "beworben", "applied_at": "2026-09-07",
        "url": "https://vermittler.example/p/1", "endkunde": "Beispielwerk AG"})
    neu = _frisch("wv3", "PLM Architect (m/w/d)", "Beispielwerk AG")
    erg = automatik.anwenden(tmp_db, [neu])
    assert erg["zaehler"]["automatisch_aussortiert"] == 1
    assert "_repost_verdacht" not in erg["jobs"][0]


def test_1126_ohne_bewerbungen_aendert_sich_an_der_automatik_nichts(tmp_db):
    _wiedergaenger_historie(tmp_db, "Beratungshaus Sued GmbH", "wn")
    erg = automatik.anwenden(tmp_db, [
        _frisch("wn3", "PLM Architect (m/w/d)", "Beratungshaus Sued GmbH")])
    assert erg["zaehler"]["automatisch_aussortiert"] == 1


def test_1126_der_suchlauf_ruft_die_automatik_und_die_hat_den_setter():
    """Ein Setter, den niemand aufruft, ist keiner (DoD 8c)."""
    import inspect
    quelle = inspect.getsource(automatik.anwenden)
    assert "ist_wiederholung" in quelle
    assert '_repost_verdacht"] = True' in quelle


# ══ Elwosa: bei laufender Bewerbung nicht "da lief schon mal" ═══════════

def _elwosa_repost(db):
    from bewerbungs_assistent.services import elwosa_provider
    return [k for k in elwosa_provider.betriebslage_kandidaten(db)
            if str(k.dedup_key).startswith("repost:")]


def test_1126_elwosa_spricht_bei_laufender_bewerbung_nicht_von_schon_mal(tmp_db):
    tmp_db.save_profile({"name": "Test"})
    tmp_db.add_application({
        "title": "Teamleitung Enterprise Applications",
        "company": "Musterbetrieb Nord GmbH", "status": "beworben",
        "applied_at": "2026-09-07", "url": "https://mb.example/original"})
    tmp_db.save_jobs([_stelle(
        "kopie1", "Teamleitung Enterprise Applications (m/w/d)",
        "Musterbetrieb Nord GmbH", "https://mb.example/kopie")])
    treffer = _elwosa_repost(tmp_db)
    assert len(treffer) == 1
    assert "läuft bereits eine Bewerbung" in treffer[0].content
    assert "da lief schon mal" not in treffer[0].content


def test_1126_elwosa_behaelt_den_bisherigen_satz_bei_abgelehnter_bewerbung(tmp_db):
    tmp_db.save_profile({"name": "Test"})
    tmp_db.add_application({
        "title": "Teamleitung Enterprise Applications",
        "company": "Musterbetrieb Nord GmbH", "status": "abgelehnt",
        "applied_at": "2026-05-12", "url": "https://mb.example/original"})
    tmp_db.save_jobs([_stelle(
        "kopie1", "Teamleitung Enterprise Applications (m/w/d)",
        "Musterbetrieb Nord GmbH", "https://mb.example/kopie")])
    treffer = _elwosa_repost(tmp_db)
    assert len(treffer) == 1
    assert "da lief schon mal eine Bewerbung" in treffer[0].content


# ══ Alle Werkzeuge fragen dieselbe Funktion (Vermittler inklusive) ═══════

@pytest.fixture
def vermittler_lage(tmp_db):
    """Eine laufende Bewerbung ueber einen Vermittler (Endkunde im Feld) und
    eine Stelle beim Endkunden mit ganz anderem Titel."""
    tmp_db.save_profile({"name": "Test"})
    aid = tmp_db.add_application({
        "title": "Berater PLM", "company": "Vermittler Nord GmbH",
        "status": "beworben", "applied_at": "2026-09-07",
        "url": "https://vermittler.example/p/1",
        "endkunde": "Beispielwerk AG"})
    tmp_db.save_jobs([_stelle(
        "ek1", "Leiter Werkzeugbau", "Beispielwerk AG",
        "https://beispielwerk.example/j/1")])
    return {"db": tmp_db, "aid": aid}


def test_1126_stellen_anzeigen_kennt_auch_den_vermittler(vermittler_lage):
    stellen = _werkzeug(vermittler_lage["db"], "stellen_anzeigen")()["stellen"]
    stelle = next(s for s in stellen if s["id"] == "ek1")
    assert stelle["repost_details"]["art"] == "vermittler"
    assert "Vermittler Nord GmbH" in stelle["repost_warnung"]


def test_1126_fit_analyse_kennt_auch_den_vermittler(vermittler_lage):
    res = _werkzeug(vermittler_lage["db"], "fit_analyse")(job_hash="ek1")
    assert res["repost_details"]["art"] == "vermittler"
    assert res["repost_details"]["bewerbung_id_voll"] == vermittler_lage["aid"]


def test_1126_firma_kontext_kennt_auch_den_vermittler(vermittler_lage):
    res = _werkzeug(vermittler_lage["db"], "firma_kontext")(
        firmenname="Beispielwerk AG")
    stelle = next(s for s in res["aktive_stellen"] if s["hash"] == "ek1")
    assert stelle["repost_details"]["art"] == "vermittler"


def test_1126_das_dashboard_zeigt_den_vermittler_als_eigene_art(
        vermittler_lage, monkeypatch):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    monkeypatch.setattr(dash, "_db", vermittler_lage["db"])
    liste = TestClient(dash.app).get("/api/jobs", params={"limit": 20}).json()
    stelle = next(j for j in liste["jobs"] if j["hash"] == "ek1")
    assert stelle["repost_details"]["art"] == "vermittler"
    assert stelle["repost_details"]["sicher"] is False


def test_1126_fit_analyse_meldet_die_wiederholung_mit_dem_neuen_wortlaut(lage):
    res = _werkzeug(lage["db"], "fit_analyse")(job_hash="kopie1")
    assert res["repost_details"]["art"] == "wiederholung"
    assert res["repost_details"]["laeuft"] is True
    assert "nicht noch einmal bewerben" in res["repost_warnung"]


def test_1126_firma_kontext_meldet_die_wiederholung_mit_dem_neuen_wortlaut(lage):
    res = _werkzeug(lage["db"], "firma_kontext")(
        firmenname="Musterbetrieb Nord")
    stelle = next(s for s in res["aktive_stellen"] if s["hash"] == "kopie1")
    assert "nicht noch einmal bewerben" in stelle["repost_warnung"]
    assert stelle["repost_details"]["laeuft"] is True


def test_1126_eine_dokumentierte_absage_bei_laufendem_stand_bleibt_sichtbar(tmp_db):
    """Der Stand hinkt hinterher: "beworben", aber ein Absagegrund liegt
    schon vor. Der Satz folgt dem Stand; der Befund steht in den Details."""
    from bewerbungs_assistent.duplicate_detection import find_repost_of_application
    aid = tmp_db.add_application({
        "title": "Teamleitung Enterprise Applications",
        "company": "Musterbetrieb Nord GmbH", "status": "beworben",
        "applied_at": "2026-09-07", "url": "https://mb.example/original"})
    tmp_db.connect().execute(
        "UPDATE applications SET rejection_reason=? WHERE id=?",
        ("Position anderweitig besetzt", aid))
    tmp_db.connect().commit()
    treffer = find_repost_of_application(
        {"hash": "x", "title": "Teamleitung Enterprise Applications (m/w/d)",
         "company": "Musterbetrieb Nord GmbH", "url": "https://mb.example/k"},
        tmp_db.get_applications(), db=tmp_db)
    assert treffer["laeuft"] is True
    assert treffer["ablehnungsgrund_dokumentiert"] is True
    assert treffer["ablehnungsgrund"]["text"] == "Position anderweitig besetzt"
