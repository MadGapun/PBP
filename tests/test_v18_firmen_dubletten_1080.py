"""Firmen-Stammsatz (#1080): die Duplikat- und Repost-Erkennung kennt frühere Namen und Kurzformen.

Der Namensabgleich kennt nur, was im Namen steht. „Alt AG“ heißt heute „Neu GmbH“, „IBM“ ist die Kurzform des langen Namens:
das weiß nur der Mensch, und er trägt es in den Firmen-Einträgen ein. Der Kanon (`firmen_kanon`) gibt diese Zuordnung an die
Erkennung weiter. Er FÜGT Treffer hinzu und nimmt nie einen weg; ein Treffer allein über ihn ist nie „sicher“ (#951).
Alle Firmennamen hier sind Platzhalter (QA-Regel). Wegwerf-Datenbank unter tmp_path.
"""
import asyncio
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bewerbungs_assistent import duplicate_detection as dd  # noqa: E402
from bewerbungs_assistent.services import firmen_stamm as fs  # noqa: E402
from bewerbungs_assistent.services import stellen_dublette as sd  # noqa: E402

# Genug verschiedene Wortfolgen fuer den Textvergleich (mindestens 60 Vierergruppen, ohne Wiederholung).
BESCHREIBUNG = " ".join(f"aufgabe{i} verantwortung{i % 5} einkauf" for i in range(60))


@pytest.fixture
def db(tmp_db, tmp_path):
    assert str(tmp_path) in str(tmp_db.db_path), f"DB nicht isoliert: {tmp_db.db_path}"
    tmp_db.save_profile({"name": "Erika Beispiel"})
    return tmp_db


def _app(db, firma, titel="Einkaufsleiter Technik", status="abgelehnt", notizen="", endkunde="", url=""):
    return db.add_application({"title": titel, "company": firma, "status": status, "notes": notizen, "endkunde": endkunde, "url": url})


def _stelle(hash_, titel, firma, url=None, quelle="stepstone"):
    return {"hash": hash_, "title": titel, "company": firma, "url": url or f"https://{quelle}.example/stellen/{hash_}",
            "source": quelle, "description": BESCHREIBUNG, "score": 12}


def _n(name):
    return dd.normalize_company_name(name)


# ── Der Kanon selbst ────────────────────────────────────────────────────────────────────────────────

def test_der_kanon_schlaegt_namen_und_schreibweisen_nach():
    k = fs.FirmenKanon({"fi_1": [_n("Neu GmbH"), _n("Alt AG"), _n("N-Gruppe")]})
    assert k.gleich(_n("Alt AG"), _n("Neu GmbH")) and k.gleich(_n("alt"), _n("NEU"))
    assert not k.gleich(_n("Alt AG"), _n("Ganz Anders"))
    assert not k.gleich("", _n("Neu GmbH")) and not k.gleich(_n("Neu GmbH"), "")
    assert not k.gleich(_n("Ganz Anders"), _n("Voellig Anders")), "zwei unbekannte Namen sind nicht deshalb dieselbe Firma"
    assert sorted(k.formen_von(_n("Alt AG"))) == sorted([_n("Neu GmbH"), _n("Alt AG"), _n("N-Gruppe")])
    assert k.formen_von(_n("Ganz Anders")) == []


def test_eine_bestaetigte_schreibweise_im_laengeren_namen_zaehlt_aber_nur_bei_genau_einer_firma():
    k = fs.FirmenKanon({"fi_1": [_n("Beispiel Handel"), _n("Beispiel")], "fi_2": [_n("Muster Energie")]})
    assert k.gleich(_n("Beispiel Deutschland"), _n("Beispiel Handel")), "Schreibweise als Wortfolge im Namen"
    assert not k.gleich(_n("Beispielhaft"), _n("Beispiel Handel")), "Wortgrenze: Teil eines Wortes zaehlt nicht"
    zwei = fs.FirmenKanon({"fi_1": [_n("Muster Energie"), _n("Muster")], "fi_2": [_n("Muster Medizin"), _n("Muster")]})
    assert zwei.firma_von(_n("Muster")) == "", "eine Form, die zwei Firmen gehoert, ordnet niemandem zu"
    assert not zwei.gleich(_n("Muster Energie"), _n("Muster Medizin"))
    assert zwei.firma_von(_n("Muster Energie")) == "fi_1"
    assert _n("Muster") not in zwei.formen_von(_n("Muster Energie"))


def test_steckt_ein_name_zwei_firmen_wird_nicht_geraten():
    k = fs.FirmenKanon({"fi_1": [_n("Beispiel Eins")], "fi_2": [_n("Beispiel Zwei")]})
    assert k.firma_von(_n("Beispiel Eins Beispiel Zwei Gruppe")) == "", "zwei Firmen im Namen: PBP raet nicht"
    assert k.firma_von(_n("Beispiel Eins Deutschland")) == "fi_1"


def test_eine_kurzform_ist_in_einem_laengeren_namen_zu_kurz_um_zu_gelten():
    k = fs.FirmenKanon({"fi_1": [_n("International Beispiel Systems"), _n("IBS")]})
    assert k.gleich(_n("IBS"), _n("International Beispiel Systems")), "als ganzer Name gilt sie"
    assert not k.gleich(_n("IBS Consulting"), _n("International Beispiel Systems")), "als Teil eines laengeren Namens ist sie zu kurz"


def test_mutter_und_tochter_sind_nicht_dieselbe_firma(db):
    mutter = fs.firma_anlegen(db, "Beispiel Konzern")["firma"]
    fs.firma_anlegen(db, "Beispiel Maschinenbau", mutterfirma_id=mutter["id"])
    k = dd.firmen_kanon(db)
    assert k is not None and not k.gleich(_n("Beispiel Konzern"), _n("Beispiel Maschinenbau"))


def test_ohne_firmen_eintraege_gibt_es_keinen_kanon(db):
    assert dd.firmen_kanon(db) is None, "kein Eintrag: so abgleichen wie bisher"
    assert dd.firmen_kanon(None) is None


def test_der_kanon_gehoert_zum_profil(db):
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    pid = db.get_active_profile_id()
    assert dd.firmen_kanon(db, pid) is not None
    assert dd.firmen_kanon(db, "ein-anderes-profil") is None


def test_ein_kaputter_stammsatz_kostet_keine_erkennung():
    class Kaputt:
        def connect(self):
            raise RuntimeError("nicht lesbar")

        def get_active_profile_id(self):
            return "x"
    assert dd.firmen_kanon(Kaputt()) is None


# ── find_duplicate_job ──────────────────────────────────────────────────────────────────────────────

def test_ein_frueherer_name_ist_dieselbe_firma(db):
    kandidaten = [{"id": "a1", "title": "Einkaufsleiter Technik", "company": "Alt AG", "status": "abgelehnt"}]
    assert dd.find_duplicate_job("Neu GmbH", "Einkaufsleiter Technik", "", kandidaten) is None, "ohne Eintrag: zwei fremde Namen"
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    treffer = dd.find_duplicate_job("Neu GmbH", "Einkaufsleiter Technik", "", kandidaten, kanon=dd.firmen_kanon(db))
    assert treffer is not None and treffer["job"]["id"] == "a1" and treffer["firma_via"] == "stammsatz"


def test_die_titelregeln_bleiben_auch_mit_kanon_in_kraft(db):
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    kanon = dd.firmen_kanon(db)
    kandidaten = [{"id": "a1", "title": "Pflegefachkraft Nachtdienst", "company": "Alt AG"}]
    assert dd.find_duplicate_job("Neu GmbH", "Einkaufsleiter Technik", "", kandidaten, kanon=kanon) is None


def test_der_kanon_nimmt_dem_namensabgleich_nichts_weg(db):
    # Zwei verschiedene Firmen im Stammsatz: "Muster" steckt in beiden Namen - der bisherige Treffer bleibt (Recall vor Praezision).
    fs.firma_anlegen(db, "Muster Energie GmbH")
    fs.firma_anlegen(db, "Muster Medizin GmbH")
    kandidaten = [{"id": "a1", "title": "Einkaufsleiter Technik", "company": "Muster Energie GmbH"}]
    ohne = dd.find_duplicate_job("Muster Medizin GmbH", "Einkaufsleiter Technik", "", kandidaten)
    mit = dd.find_duplicate_job("Muster Medizin GmbH", "Einkaufsleiter Technik", "", kandidaten, kanon=dd.firmen_kanon(db))
    assert (ohne is None) == (mit is None)
    kandidaten = [{"id": "a2", "title": "Einkaufsleiter Technik", "company": "Muster Energie GmbH Hamburg"}]
    assert dd.find_duplicate_job("Muster Energie GmbH", "Einkaufsleiter Technik", "", kandidaten, kanon=dd.firmen_kanon(db))


def test_ein_treffer_ueber_den_namen_traegt_kein_via(db):
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    kandidaten = [{"id": "a1", "title": "Einkaufsleiter Technik", "company": "Neu GmbH"}]
    treffer = dd.find_duplicate_job("Neu GmbH", "Einkaufsleiter Technik", "", kandidaten, kanon=dd.firmen_kanon(db))
    assert treffer is not None and "firma_via" not in treffer


# ── Wiederholung einer früheren Bewerbung ───────────────────────────────────────────────────────────

def test_eine_wiederholung_unter_neuem_firmennamen_wird_erkannt(db):
    _app(db, "Alt AG", status="abgelehnt")
    job = {"hash": "j1", "title": "Einkaufsleiter Technik", "company": "Neu GmbH", "url": "https://stepstone.example/s/1"}
    apps = db.get_applications()
    assert dd.find_repost_of_application(job, apps, db=db) is None, "ohne Eintrag kennt PBP den Namenswechsel nicht"
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    treffer = dd.find_repost_of_application(job, apps, db=db)
    assert treffer is not None and treffer["art"] == "wiederholung" and treffer["firma_via"] == "stammsatz"
    assert treffer["firma_damals"] == "Alt AG"


def test_die_warnung_sagt_warum_zwei_namen_zusammengehoeren(db):
    _app(db, "Alt AG", status="abgelehnt")
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    job = {"hash": "j1", "title": "Einkaufsleiter Technik", "company": "Neu GmbH", "url": "https://stepstone.example/s/1"}
    warnung = dd.find_repost_of_application(job, db.get_applications(), db=db)["warnung"]
    assert "Firmen-Einträgen" in warnung and "Alt AG" in warnung and "Neu GmbH" in warnung


def test_ohne_firmen_eintraege_aendert_sich_an_der_antwort_nichts(db):
    _app(db, "Halbleiterwerk Nord GmbH", status="abgelehnt")
    job = {"hash": "j1", "title": "Einkaufsleiter Technik", "company": "Halbleiterwerk Nord", "url": "https://stepstone.example/s/1"}
    treffer = dd.find_repost_of_application(job, db.get_applications(), db=db)
    assert treffer is not None and "firma_via" not in treffer and "Firmen-Einträgen" not in treffer["warnung"]


def test_eine_laufende_bewerbung_unter_dem_alten_namen_warnt_mit_dem_laufend_text(db):
    _app(db, "Alt AG", status="beworben")
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    job = {"hash": "j1", "title": "Einkaufsleiter Technik", "company": "Neu GmbH", "url": "https://stepstone.example/s/1"}
    treffer = dd.find_repost_of_application(job, db.get_applications(), db=db)
    assert treffer["laeuft"] is True and "Nicht noch einmal bewerben" in treffer["warnung"] or "nicht noch einmal bewerben" in treffer["warnung"]


# ── Gleicher Anzeigentext, anderer Titel ────────────────────────────────────────────────────────────

def test_ein_umbenannter_repost_unter_dem_frueheren_firmennamen_wird_erkannt(db):
    alt = {"hash": "h-alt", "title": "Leiter Beschaffung", "company": "Alt AG", "description": BESCHREIBUNG}
    assert dd.find_inhalt_repost("Neu GmbH", "Einkaufsleiter Technik", BESCHREIBUNG, [alt]) is None
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    treffer = dd.find_inhalt_repost("Neu GmbH", "Einkaufsleiter Technik", BESCHREIBUNG, [alt], kanon=dd.firmen_kanon(db))
    assert treffer is not None and treffer["job"]["hash"] == "h-alt"


def test_eine_kurzform_mit_drei_buchstaben_genuegt_wenn_der_mensch_sie_bestaetigt_hat(db):
    fs.firma_anlegen(db, "International Beispiel Systems", aliase=["IBS"])
    alt = {"hash": "h-alt", "title": "Leiter Beschaffung", "company": "International Beispiel Systems", "description": BESCHREIBUNG}
    kanon = dd.firmen_kanon(db)
    assert dd.find_inhalt_repost("IBS", "Einkaufsleiter Technik", BESCHREIBUNG, [alt]) is None, "ohne Eintrag: zu kurz"
    assert dd.find_inhalt_repost("IBS", "Einkaufsleiter Technik", BESCHREIBUNG, [alt], kanon=kanon) is not None


# ── Bewerbung über einen Vermittler ─────────────────────────────────────────────────────────────────

def test_der_endkunde_wird_auch_unter_seiner_kurzform_gefunden(db):
    fs.firma_anlegen(db, "International Beispiel Systems", aliase=["IBS"])
    vermittler = _app(db, "Personal Partner GmbH", status="beworben", notizen="Endkunde: IBS, Standort Hamburg")
    assert vermittler
    apps = [a for a in db.get_applications()]
    assert dd.find_vermittler_bewerbung("International Beispiel Systems", apps) is None, "ohne Eintrag steht der lange Name nirgends"
    treffer = dd.find_vermittler_bewerbung("International Beispiel Systems", apps, kanon=dd.firmen_kanon(db))
    assert treffer is not None and treffer["company"] == "Personal Partner GmbH"


def test_eine_kurzform_ist_ein_ganzes_wort_nie_ein_wortteil(db):
    fs.firma_anlegen(db, "International Beispiel Systems", aliase=["IBS"])
    _app(db, "Personal Partner GmbH", status="beworben", notizen="Endkunde: IBSEN Verlag")
    apps = db.get_applications()
    assert dd.find_vermittler_bewerbung("International Beispiel Systems", apps, kanon=dd.firmen_kanon(db)) is None


def test_eine_bewerbung_bei_derselben_firma_unter_dem_alten_namen_ist_kein_vermittlerfall(db):
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    _app(db, "Alt AG", status="beworben", notizen="Kontakt kam ueber Neu GmbH Personalabteilung")
    assert dd.find_vermittler_bewerbung("Neu GmbH", db.get_applications(), kanon=dd.firmen_kanon(db)) is None, \
        "das ist die Bewerbung bei der Firma selbst (Stufe A), kein Vermittler"


# ── Stellen-Dublette: höchstens ein Verdacht ────────────────────────────────────────────────────────

def test_ein_treffer_allein_ueber_die_firmen_eintraege_ist_nie_sicher(db):
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    kanon = dd.firmen_kanon(db)
    neu = {"title": "Einkaufsleiter Technik", "company": "Neu GmbH", "url": "https://a.example/1"}
    alt = {"hash": "x", "title": "Einkaufsleiter Technik", "company": "Alt AG", "url": "https://b.example/2"}
    assert sd.finde(neu, [alt]) is None
    treffer = sd.finde(neu, [alt], kanon=kanon)
    assert treffer is not None and treffer["sicherheit"] == sd.VERDACHT, "ein Geschaeftsbereich kann dieselbe Rolle getrennt ausschreiben"
    gleiche_firma = dict(alt, company="Neu GmbH")
    assert sd.finde(neu, [gleiche_firma], kanon=kanon)["sicherheit"] == sd.SICHER, "gleicher Name bleibt nachrechenbar"


# ── Import (save_jobs) ──────────────────────────────────────────────────────────────────────────────

def test_der_import_markiert_den_zweitfund_unter_dem_frueheren_namen_und_verschmilzt_nichts(db):
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    db.save_jobs([_stelle("imp1", "Einkaufsleiter Technik", "Alt AG", quelle="stepstone")])
    db.save_jobs([_stelle("imp2", "Einkaufsleiter Technik", "Neu GmbH", quelle="xing")])
    zweit = db.get_job(db.resolve_job_hash("imp2"))
    assert zweit["is_active"] == 1, "ein Verdacht verschmilzt nicht und sortiert nicht aus"
    assert "Mögliches Duplikat" in (zweit.get("dismiss_note") or "")


def test_der_import_ohne_firmen_eintraege_kennt_den_namenswechsel_nicht(db):
    db.save_jobs([_stelle("imp1", "Einkaufsleiter Technik", "Alt AG", quelle="stepstone")])
    db.save_jobs([_stelle("imp2", "Einkaufsleiter Technik", "Neu GmbH", quelle="xing")])
    zweit = db.get_job(db.resolve_job_hash("imp2"))
    assert zweit["is_active"] == 1 and "Duplikat" not in (zweit.get("dismiss_note") or "")


def test_der_import_liest_den_stammsatz_einmal_je_profil_und_nicht_je_stelle(db, monkeypatch):
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    aufrufe = []
    echt = dd.firmen_kanon

    def gezaehlt(d, profil=None):
        aufrufe.append(profil)
        return echt(d, profil)
    monkeypatch.setattr(dd, "firmen_kanon", gezaehlt)
    db.save_jobs([_stelle(f"viele{i}", f"Stelle Nummer {i} fuer Beispiel", "Neu GmbH") for i in range(8)])
    assert len(aufrufe) == 1, aufrufe


# ── Anlage von Hand und Aussortieren ────────────────────────────────────────────────────────────────

@pytest.fixture
def werkzeug(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("firmen-dubletten-test")
    register_all(mcp, db, logging.getLogger("firmen-dubletten-test"))

    def aufruf(werkzeugname, /, **args):
        async def _run():
            tool = await mcp.get_tool(werkzeugname)
            res = await tool.run(args)
            return res.structured_content if hasattr(res, "structured_content") else res
        return asyncio.run(_run())
    return aufruf


def test_die_handanlage_blockt_bei_einer_laufenden_bewerbung_unter_dem_alten_namen(db, werkzeug):
    _app(db, "Alt AG", status="beworben")
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    erg = werkzeug("stelle_manuell_anlegen", titel="Einkaufsleiter Technik", firma="Neu GmbH",
                   url="https://firma.example/karriere/einkauf-1", beschreibung=BESCHREIBUNG)
    assert erg.get("warnung") == "duplikat_bewerbung", erg
    assert "Firmen-Einträgen" in erg["nachricht"] and "Alt AG" in erg["nachricht"]
    # Der Mensch entscheidet: force legt trotzdem an.
    erg = werkzeug("stelle_manuell_anlegen", titel="Einkaufsleiter Technik", firma="Neu GmbH",
                   url="https://firma.example/karriere/einkauf-1", beschreibung=BESCHREIBUNG, force=True)
    assert erg.get("warnung") != "duplikat_bewerbung", erg


def test_die_handanlage_ohne_firmen_eintraege_legt_an_wie_bisher(db, werkzeug):
    _app(db, "Alt AG", status="beworben")
    erg = werkzeug("stelle_manuell_anlegen", titel="Einkaufsleiter Technik", firma="Neu GmbH",
                   url="https://firma.example/karriere/einkauf-1", beschreibung=BESCHREIBUNG)
    assert erg.get("warnung") != "duplikat_bewerbung", erg


def test_das_aussortieren_erkennt_das_duplikat_unter_dem_alten_namen(db):
    from bewerbungs_assistent.services import aussortieren
    _app(db, "Alt AG", status="beworben")
    db.save_jobs([_stelle("aus1", "Einkaufsleiter Technik", "Neu GmbH", url="https://stepstone.example/s/77")])
    voll = db.resolve_job_hash("aus1")
    assert aussortieren.duplikat_finden(db, voll) is None
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    treffer = aussortieren.duplikat_finden(db, voll)
    assert treffer is not None and treffer["typ"] == "bewerbung" and treffer["firma"] == "Alt AG"


# ── Hinweise an Trefferlisten ───────────────────────────────────────────────────────────────────────

def test_die_trefferliste_traegt_den_hinweis_und_liest_den_stammsatz_einmal(db, monkeypatch):
    from bewerbungs_assistent.services import bewerbungs_hinweis
    _app(db, "Alt AG", status="abgelehnt")
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    aufrufe = []
    echt = dd.firmen_kanon
    monkeypatch.setattr(dd, "firmen_kanon", lambda d, p=None: (aufrufe.append(1), echt(d, p))[1])
    jobs = [{"hash": f"t{i}", "title": "Einkaufsleiter Technik", "company": "Neu GmbH", "url": f"https://stepstone.example/s/{i}"}
            for i in range(5)]
    assert bewerbungs_hinweis.anreichern(db, jobs) == 5
    assert all(j["repost_details"]["firma_via"] == "stammsatz" for j in jobs)
    assert len(aufrufe) == 1, "einmal je Liste, nicht je Stelle"


def test_die_automatik_haelt_eine_stelle_unter_neuem_namen_nicht_fuer_unbekannt(db):
    from bewerbungs_assistent.services import bewerbungs_hinweis
    _app(db, "Alt AG", status="abgelehnt")
    bewerbungen = db.get_applications()
    job = {"hash": "a1", "title": "Einkaufsleiter Technik", "company": "Neu GmbH", "url": "https://stepstone.example/s/9"}
    assert bewerbungs_hinweis.ist_wiederholung(job, bewerbungen) is False
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    assert bewerbungs_hinweis.ist_wiederholung(job, bewerbungen, kanon=dd.firmen_kanon(db)) is True


def test_die_handanlage_findet_den_umbenannten_repost_unter_dem_frueheren_firmennamen(db, werkzeug):
    db.save_jobs([{"hash": "alt1", "title": "Leiter Beschaffung", "company": "Alt AG", "url": "https://stepstone.example/s/alt1",
                   "source": "stepstone", "description": BESCHREIBUNG, "score": 10}])
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    erg = werkzeug("stelle_manuell_anlegen", titel="Einkaufsleiter Technik", firma="Neu GmbH",
                   url="https://firma.example/karriere/einkauf-9", beschreibung=BESCHREIBUNG)
    assert erg.get("repost_verdacht"), erg
    assert erg["repost_verdacht"]["titel"] == "Leiter Beschaffung"


def test_die_handanlage_ohne_firmen_eintraege_sucht_den_repost_nicht_unter_dem_alten_namen(db, werkzeug):
    db.save_jobs([{"hash": "alt1", "title": "Leiter Beschaffung", "company": "Alt AG", "url": "https://stepstone.example/s/alt1",
                   "source": "stepstone", "description": BESCHREIBUNG, "score": 10}])
    erg = werkzeug("stelle_manuell_anlegen", titel="Einkaufsleiter Technik", firma="Neu GmbH",
                   url="https://firma.example/karriere/einkauf-9", beschreibung=BESCHREIBUNG)
    assert not erg.get("repost_verdacht"), erg


def test_die_automatik_kennt_die_wiederholung_unter_dem_alten_namen(db):
    from bewerbungs_assistent.services import stellen_automatik
    _app(db, "Alt AG", status="abgelehnt")
    job = {"hash": "auto1", "title": "Einkaufsleiter Technik", "company": "Neu GmbH", "url": "https://stepstone.example/s/auto1"}
    assert not stellen_automatik.anwenden(db, [dict(job)])["jobs"][0].get("_repost_verdacht")
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    assert stellen_automatik.anwenden(db, [dict(job)])["jobs"][0].get("_repost_verdacht") is True


def test_elwosa_meldet_den_repost_unter_dem_alten_namen(db):
    from bewerbungs_assistent.services import elwosa_provider
    _app(db, "Alt AG", status="abgelehnt")
    db.save_jobs([_stelle("elw1", "Einkaufsleiter Technik", "Neu GmbH")])

    def reposts():
        return [c for c in elwosa_provider.betriebslage_kandidaten(db) if c.dedup_key.startswith("repost:")]
    assert reposts() == []
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    assert len(reposts()) == 1


@pytest.fixture
def ingest(db):
    """Der Ingest-Endpunkt fuer Plugins (TestClient) gegen dieselbe Wegwerf-Datenbank."""
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    dash._db = db
    client = TestClient(dash.app)
    manifest = {"name": "Test-Zubringer", "version": "1.0.0", "ingest_api": "^1",
                "capabilities": ["ingest:job"], "beschreibung": "Testplugin"}
    antwort = client.post("/api/plugins/pair", json={"manifest": manifest})
    assert antwort.status_code == 200, antwort.text
    key = antwort.json()["api_key"]

    def senden(titel, firma):
        return client.post("/api/v1/ingest/job", json={"titel": titel, "firma": firma, "url": "https://firma.example/karriere/1",
                                                       "beschreibung": BESCHREIBUNG}, headers={"X-PBP-API-Key": key})
    return senden


def test_der_plugin_ingest_blockt_bei_laufender_bewerbung_unter_dem_alten_namen(db, ingest):
    _app(db, "Alt AG", status="beworben")
    assert ingest("Einkaufsleiter Technik", "Neu GmbH").status_code == 200, "ohne Eintrag kennt PBP den Namenswechsel nicht"
    # Die Stelle liegt jetzt; eine zweite Firma mit dem frueheren Namen als Schreibweise trifft die laufende Bewerbung.
    fs.firma_anlegen(db, "Zweite Neu GmbH", aliase=["Alt AG"])
    antwort = ingest("Einkaufsleiter Technik", "Zweite Neu GmbH")
    assert antwort.status_code == 409 and "Bewerbung" in antwort.json()["error"], antwort.text


def test_die_handanlage_erkennt_die_aktive_stelle_unter_dem_alten_namen(db, werkzeug):
    db.save_jobs([_stelle("akt1", "Einkaufsleiter Technik", "Alt AG", url="https://alt.example/karriere/einkauf-3")])
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    erg = werkzeug("stelle_manuell_anlegen", titel="Einkaufsleiter Technik", firma="Neu GmbH",
                   url="https://neu.example/karriere/einkauf-7", beschreibung=BESCHREIBUNG)
    assert erg.get("warnung") == "duplikat_aktive_stelle", erg


def test_die_handanlage_legt_die_stelle_unter_neuem_namen_ohne_firmen_eintrag_an(db, werkzeug):
    db.save_jobs([_stelle("akt1", "Einkaufsleiter Technik", "Alt AG", url="https://alt.example/karriere/einkauf-3")])
    erg = werkzeug("stelle_manuell_anlegen", titel="Einkaufsleiter Technik", firma="Neu GmbH",
                   url="https://neu.example/karriere/einkauf-7", beschreibung=BESCHREIBUNG)
    assert erg.get("warnung") != "duplikat_aktive_stelle", erg


def test_die_handanlage_meldet_eine_aehnliche_laufende_bewerbung_unter_dem_alten_namen(db, werkzeug):
    _app(db, "Alt AG", titel="Einkaufsleiter Technik Maschinenbau", status="beworben", url="https://alt.example/karriere/1")
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    erg = werkzeug("stelle_manuell_anlegen", titel="Einkaufsleiter Technik Elektronik", firma="Neu GmbH",
                   url="https://neu.example/karriere/2", beschreibung=BESCHREIBUNG)
    assert erg.get("laufende_bewerbung_verdacht"), erg
    assert erg.get("warnung") != "duplikat_bewerbung", "unterschiedliche Adressen verlangen die strenge Schwelle: nur ein Hinweis"


def test_die_handanlage_ohne_firmen_eintrag_meldet_die_aehnliche_bewerbung_unter_dem_alten_namen_nicht(db, werkzeug):
    _app(db, "Alt AG", titel="Einkaufsleiter Technik Maschinenbau", status="beworben", url="https://alt.example/karriere/1")
    erg = werkzeug("stelle_manuell_anlegen", titel="Einkaufsleiter Technik Elektronik", firma="Neu GmbH",
                   url="https://neu.example/karriere/2", beschreibung=BESCHREIBUNG)
    assert not erg.get("laufende_bewerbung_verdacht"), erg


def test_die_handanlage_nennt_die_bewerbung_ueber_den_vermittler_auch_bei_der_kurzform(db, werkzeug):
    _app(db, "Personal Partner GmbH", titel="Sachbearbeiter Vertrieb", status="beworben", notizen="Endkunde: IBS, Standort Hamburg")
    fs.firma_anlegen(db, "International Beispiel Systems", aliase=["IBS"])
    erg = werkzeug("stelle_manuell_anlegen", titel="Projektleiter Logistik", firma="International Beispiel Systems",
                   url="https://ibs.example/karriere/2", beschreibung=BESCHREIBUNG)
    assert erg.get("vermittler_bewerbung"), erg
    assert erg["vermittler_bewerbung"]["firma_der_bewerbung"] == "Personal Partner GmbH"


def test_die_handanlage_ohne_firmen_eintrag_kennt_die_kurzform_im_endkunden_feld_nicht(db, werkzeug):
    _app(db, "Personal Partner GmbH", titel="Sachbearbeiter Vertrieb", status="beworben", notizen="Endkunde: IBS, Standort Hamburg")
    erg = werkzeug("stelle_manuell_anlegen", titel="Projektleiter Logistik", firma="International Beispiel Systems",
                   url="https://ibs.example/karriere/2", beschreibung=BESCHREIBUNG)
    assert not erg.get("vermittler_bewerbung"), erg


def test_der_hinweis_an_der_stelle_nennt_den_vermittler_auch_bei_der_kurzform(db):
    from bewerbungs_assistent.services import bewerbungs_hinweis
    _app(db, "Personal Partner GmbH", titel="Sachbearbeiter Vertrieb", status="beworben", notizen="Endkunde: IBS, Standort Hamburg")
    job = {"hash": "v1", "title": "Projektleiter Logistik", "company": "International Beispiel Systems", "url": "https://ibs.example/k/2"}
    assert bewerbungs_hinweis.fuer_stelle(job, db.get_applications(), db=db) is None
    fs.firma_anlegen(db, "International Beispiel Systems", aliase=["IBS"])
    hinweis = bewerbungs_hinweis.fuer_stelle(job, db.get_applications(), db=db)
    assert hinweis is not None and hinweis["art"] == bewerbungs_hinweis.VERMITTLER


def test_das_aussortieren_erkennt_die_aussortierte_stelle_unter_dem_alten_namen(db):
    from bewerbungs_assistent.services import aussortieren
    db.save_jobs([_stelle("ausA", "Einkaufsleiter Technik", "Alt AG", url="https://alt.example/karriere/1")])
    db.dismiss_job(db.resolve_job_hash("ausA"), "zu_weit_entfernt")
    db.save_jobs([_stelle("ausB", "Einkaufsleiter Technik", "Neu GmbH", url="https://neu.example/karriere/2")])
    voll = db.resolve_job_hash("ausB")
    assert aussortieren.duplikat_finden(db, voll) is None
    fs.firma_anlegen(db, "Neu GmbH", aliase=["Alt AG"])
    treffer = aussortieren.duplikat_finden(db, voll)
    assert treffer is not None and treffer["typ"] == "aussortierte_stelle", treffer
