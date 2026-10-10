"""#1184 — Angaben aus Google Jobs sind Behauptungen, und Aussortiertes faellt beim Anlegen auf.

Gemeldet am 08.10.2026 aus dem Echtbestand: fuenf Treffer aus einem Browserlauf ueber Google Jobs, vier nur mit
Kopfdaten. Google nannte "Beliebiger Ort, Homeoffice", die Originalanzeige einen Ort rund 570 km entfernt und nur
"mobiles Arbeiten". PBP uebernahm `remote` vom Aufrufer: die Entfernung fiel weg, der Rahmenscore stieg. Dieselbe
Anzeige lag ausserdem schon als aussortierter Treffer unter dem Namen des Konzernunternehmens vor, und die Pruefung
beim Anlegen sah nur Bewerbungen und AKTIVE Stellen.

Alle Firmen, Orte und Adressen in diesen Tests sind erfunden.
"""
import asyncio
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

ORIGINALTEXT = (
    "Ihre Aufgaben: Sie betreuen die Engineering-Systeme unseres Werks, pflegen Stuecklisten und Freigabeprozesse "
    "und begleiten die Einfuehrung eines neuen PLM-Systems. Ihr Profil: abgeschlossenes Studium, mehrjaehrige "
    "Erfahrung im Maschinenbau, sicherer Umgang mit Datenmodellen. Der Arbeitsplatz ist im Werk Musterstadt.")
ORIGINAL_URL = "https://karriere.beispiel-werk.example/jobs/4711"
GOOGLE_KOPF = "Volltext nicht abrufbar"
HEIM = (48.1, 11.5)


@pytest.fixture
def env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v18_google_1184_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def geo(env, monkeypatch):
    """Ein fester Heimatstandort und feste Entfernungen - kein Netz."""
    db, _ = env
    db.set_search_criteria("standort_lat", HEIM[0])
    db.set_search_criteria("standort_lon", HEIM[1])
    from bewerbungs_assistent.services import geocoding_service as g
    monkeypatch.setattr(g, "geocode_and_calculate_distance", lambda ort, lat, lon: 123.0)
    monkeypatch.setattr(g, "geocode_location", lambda ort: (50.0, 8.0))
    return g


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


def _google(mcp, **kw):
    args = {"titel": "PLM Systemadministrator Teamcenter (m/w/d)", "firma": "Hansa Marke GmbH",
            "ort": "Beliebiger Ort, Homeoffice", "quelle": "google_jobs", "remote": "remote",
            "beschreibung": GOOGLE_KOPF}
    args.update(kw)
    return _call(mcp, "stelle_manuell_anlegen", args)


def _rahmen_entfernung(db, h):
    from bewerbungs_assistent.services import rahmen
    return rahmen.daumen(db.get_job(h), db.get_search_criteria() or {})["teile"]["entfernung"]


# ── b) Remote und Ort aus Google gelten nicht ─────────────────────────────────────────────────

def test_1184_homeoffice_aus_googles_karte_wird_nicht_remote(env):
    """Der Fall des Nutzers: `remote` vom Aufrufer, Ort "Beliebiger Ort, Homeoffice", kein Text, keine URL."""
    db, mcp = env
    res = _google(mcp)
    assert res["status"] == "angelegt"
    assert db.get_job(res["hash"])["remote_level"] == "unbekannt"
    assert res["google_vorbehalt"]["remote"]["angegeben"] == "remote"
    assert res["google_vorbehalt"]["remote"]["gespeichert"] == "unbekannt"
    assert res["warnung"] == "google_nur_kopfdaten"
    assert res["google_vorbehalt"]["remote"]["bestimmt_aus"].startswith("nichts")


def test_1184_der_rahmen_behauptet_dann_kein_vollstaendig_remote(env):
    db, mcp = env
    res = _google(mcp)
    teil = _rahmen_entfernung(db, res["hash"])
    assert "Vollständig remote" not in teil["grund"], "die Entfernung darf nicht wegfallen"
    assert teil["belegt"] is False, "unbekannt ist ein eigener Zustand, kein Beleg"


def test_1184_der_text_entscheidet_nicht_googles_karte(env):
    db, mcp = env
    res = _google(mcp, beschreibung="Hybrides Arbeitsmodell mit zwei Tagen Homeoffice pro Woche am Standort. " + GOOGLE_KOPF)
    assert db.get_job(res["hash"])["remote_level"] == "hybrid"
    assert res["google_vorbehalt"]["remote"]["bestimmt_aus"] == "Anzeigentext"


def test_1184_googles_ort_fliesst_nicht_in_die_erkennung_ein(env):
    """"Homeoffice" im Ort der Karte macht aus einem Text ohne Angabe kein "hybrid"."""
    db, mcp = env
    res = _google(mcp, ort="Homeoffice", remote="hybrid")
    assert db.get_job(res["hash"])["remote_level"] == "unbekannt"


def test_1184_keine_entfernung_aus_googles_ort(env, geo):
    db, mcp = env
    res = _google(mcp, ort="Musterstadt", remote="vor_ort")
    job = db.get_job(res["hash"])
    assert job["distance_km"] is None, "aus Googles Ort wird keine Zahl gerechnet"
    assert job["location"] == "Musterstadt", "der Ort bleibt als Text stehen"
    assert res["google_vorbehalt"]["ort"]["entfernung"] == "nicht gerechnet"
    assert not [k for k in res if k.startswith("entfernung")], "keine Entfernungsangabe im Ergebnis"


def test_1184_gegenprobe_andere_quellen_rechnen_die_entfernung_wie_immer(env, geo):
    db, mcp = env
    res = _call(mcp, "stelle_manuell_anlegen", {
        "titel": "PLM Systemadministrator", "firma": "Nordwerk AG", "ort": "Musterstadt", "quelle": "linkedin",
        "remote": "remote", "url": ORIGINAL_URL, "beschreibung": ORIGINALTEXT})
    job = db.get_job(res["hash"])
    assert job["distance_km"] == 123.0
    assert job["remote_level"] == "remote", "der Aufrufer-Wert gilt ausserhalb von Google weiter"
    assert "google_vorbehalt" not in res


def test_1184_mit_dem_original_gilt_die_normale_regel(env, geo):
    """Google als Quelle, aber Detail-URL des Arbeitgebers UND Text: das Original ist gelesen."""
    db, mcp = env
    res = _google(mcp, ort="Musterstadt", remote="vor_ort", url=ORIGINAL_URL, beschreibung=ORIGINALTEXT)
    job = db.get_job(res["hash"])
    assert job["remote_level"] == "vor_ort"
    assert job["distance_km"] == 123.0
    assert "google_vorbehalt" not in res


@pytest.mark.parametrize("url, text, gelesen", [
    (ORIGINAL_URL, ORIGINALTEXT, True),
    (ORIGINAL_URL, GOOGLE_KOPF, False),                                              # Adresse ohne Text
    ("", ORIGINALTEXT, False),                                                       # Text ohne Adresse
    ("https://www.google.com/search?q=plm&udm=8", ORIGINALTEXT, False),              # Google selbst
    ("https://google.de/search?q=plm", ORIGINALTEXT, False),
    ("https://careers.google.com/jobs/results/4711-plm", ORIGINALTEXT, False),   # Google, aber keine Suche
    ("https://jobs.portal.example/suche?keywords=plm&ort=hamburg", ORIGINALTEXT, False),   # Suchergebnis
    ("kein-link", ORIGINALTEXT, False),
])
def test_1184_original_gelesen_braucht_adresse_und_text(url, text, gelesen):
    from bewerbungs_assistent.services import google_angaben as ga
    assert ga.original_gelesen(url, text) is gelesen
    assert ga.unter_vorbehalt("google_jobs", url, text) is (not gelesen)
    assert ga.unter_vorbehalt("linkedin", url, text) is False, "nur Google-Quellen stehen unter Vorbehalt"


def test_1184_ein_fremder_host_mit_google_im_namen_ist_nicht_google():
    from bewerbungs_assistent.services import google_angaben as ga
    assert ga.ist_google_adresse("https://www.google.com/search") is True
    assert ga.ist_google_adresse("https://notgoogle.com/jobs/1") is False
    assert ga.ist_google_adresse("https://mygoogle.example.com/jobs/1") is False


def test_1184_original_nachtragen_holt_arbeitsmodell_nach(env):
    db, mcp = env
    res = _google(mcp)
    h = res["hash"]
    erg = _call(mcp, "stelle_bearbeiten", {
        "job_hash": h, "url": ORIGINAL_URL,
        "beschreibung": ORIGINALTEXT + " Wir arbeiten vollstaendig remote, ein Standort ist nicht noetig."})
    nachgeholt = erg["google_vorbehalt_aufgehoben"]
    assert nachgeholt["remote"] == {"vorher": "unbekannt", "jetzt": "remote"}
    assert db.get_job(h)["remote_level"] == "remote"
    assert "score_neu_berechnet" in erg


def test_1184_original_nachtragen_holt_die_entfernung_nach(env, geo):
    """Auch wenn der Ort derselbe bleibt: ohne diesen Schritt bliebe die Entfernung fuer immer unbekannt."""
    db, mcp = env
    res = _google(mcp, ort="Musterstadt", remote="vor_ort")
    h = res["hash"]
    assert db.get_job(h)["distance_km"] is None
    erg = _call(mcp, "stelle_bearbeiten", {"job_hash": h, "url": ORIGINAL_URL, "beschreibung": ORIGINALTEXT})
    assert erg["google_vorbehalt_aufgehoben"]["entfernung_km"] is not None
    assert db.get_job(h)["distance_km"] is not None


def test_1184_nur_die_url_hebt_den_vorbehalt_nicht_auf(env):
    db, mcp = env
    res = _google(mcp)
    erg = _call(mcp, "stelle_bearbeiten", {"job_hash": res["hash"], "url": ORIGINAL_URL})
    assert "google_vorbehalt_aufgehoben" not in erg
    assert db.get_job(res["hash"])["remote_level"] == "unbekannt"


def test_1184_ein_von_hand_gesetzter_wert_bleibt_beim_nachholen(env, geo):
    db, mcp = env
    res = _google(mcp, ort="Musterstadt", remote="vor_ort")
    h = res["hash"]
    _call(mcp, "stelle_bearbeiten", {"job_hash": h, "entfernung_km": 7})
    _call(mcp, "stelle_bearbeiten", {"job_hash": h, "url": ORIGINAL_URL, "beschreibung": ORIGINALTEXT})
    job = db.get_job(h)
    assert job["distance_km"] == 7 and job["entfernung_quelle"] == "mensch"


def test_1184_andere_quellen_bleiben_beim_bearbeiten_unberuehrt(env):
    db, mcp = env
    res = _call(mcp, "stelle_manuell_anlegen", {
        "titel": "PLM Systemadministrator", "firma": "Nordwerk AG", "quelle": "linkedin", "remote": "vor_ort",
        "url": ORIGINAL_URL, "beschreibung": ORIGINALTEXT})
    erg = _call(mcp, "stelle_bearbeiten", {
        "job_hash": res["hash"], "beschreibung": ORIGINALTEXT + " Wir arbeiten vollstaendig remote."})
    assert "google_vorbehalt_aufgehoben" not in erg
    assert db.get_job(res["hash"])["remote_level"] == "vor_ort", "nur Google-Stellen holen das Arbeitsmodell nach"


def test_1184_aendert_sich_nur_das_arbeitsmodell_werden_die_punkte_neu_gerechnet(env, monkeypatch):
    """Der Text steht schon da, die URL fehlt: mit ihr gilt der Ort der Karte, und das Arbeitsmodell wird neu bestimmt.

    Die Entfernung ist von Hand gesetzt und bleibt - so aendert sich NUR das Arbeitsmodell, und die Punkte muessen
    trotzdem neu gerechnet werden.
    """
    db, mcp = env
    from bewerbungs_assistent.services import geocoding_service as g
    monkeypatch.setattr(g, "geocode_location", lambda ort: None)
    res = _google(mcp, ort="Homeoffice", remote="remote", beschreibung=ORIGINALTEXT)
    h = res["hash"]
    assert db.get_job(h)["remote_level"] == "unbekannt"
    _call(mcp, "stelle_bearbeiten", {"job_hash": h, "entfernung_km": 7})
    erg = _call(mcp, "stelle_bearbeiten", {"job_hash": h, "url": ORIGINAL_URL})
    assert erg["google_vorbehalt_aufgehoben"]["remote"]["vorher"] == "unbekannt"
    assert "entfernung_km" not in erg["google_vorbehalt_aufgehoben"], "die Entfernung von Hand bleibt"
    assert db.get_job(h)["remote_level"] != "unbekannt", "der Ort steht jetzt im Original und zaehlt"
    assert db.get_job(h)["distance_km"] == 7
    assert "score_neu_berechnet" in erg


def test_1184_set_job_remote_level_nimmt_nur_bekannte_stufen(env):
    db, mcp = env
    res = _google(mcp)
    assert db.set_job_remote_level(res["hash"], "hybrid") is True
    assert db.get_job(res["hash"])["remote_level"] == "hybrid"
    assert db.set_job_remote_level(res["hash"], "ueberall") is False
    assert db.get_job(res["hash"])["remote_level"] == "hybrid"


# ── c) Aussortiertes faellt beim Anlegen auf ──────────────────────────────────────────────────

def _aussortiert(db, h="alt1184", titel="PLM Systemadministrator Teamcenter (m/w/d)", firma="Nordwerk Konzern GmbH",
                 ort="Musterstadt", grund="zu_weit_entfernt", url=None):
    db.save_jobs([{"hash": h, "title": titel, "company": firma, "location": ort,
                   "url": url or f"https://example.com/{h}", "source": "manuell", "description": ORIGINALTEXT}])
    assert db.dismiss_job(h, grund)


def _linkedin(mcp, **kw):
    args = {"titel": "PLM Systemadministrator Teamcenter (m/w/d)", "firma": "Nordwerk Konzern GmbH", "ort": "Musterstadt",
            "quelle": "linkedin", "url": ORIGINAL_URL, "beschreibung": ORIGINALTEXT}
    args.update(kw)
    return _call(mcp, "stelle_manuell_anlegen", args)


def test_1184_aussortierte_stelle_gleicher_firma_und_titel_wird_gemeldet(env):
    db, mcp = env
    _aussortiert(db)
    res = _linkedin(mcp)
    assert res["status"] == "angelegt", "gemeldet, nicht geblockt"
    d = res["aussortierte_dublette"]
    assert d["aussortiert_wegen"] == ["zu_weit_entfernt"]
    assert d["aussortiert_am"] and d["aussortiert_am"].startswith("20"), "wann die Stelle aussortiert wurde"
    assert d["firma"] == "Nordwerk Konzern GmbH" and d["titel"].startswith("PLM Systemadministrator")
    assert d["grund"].startswith("firma_plus_")
    assert "zu_weit_entfernt" in d["hinweis"]
    assert res["warnung"] == "aussortierte_dublette"


def test_1184_ohne_aussortiertes_keine_meldung(env):
    db, mcp = env
    res = _linkedin(mcp)
    assert "aussortierte_dublette" not in res


def test_1184_andere_stelle_derselben_firma_wird_nicht_gemeldet(env):
    db, mcp = env
    _aussortiert(db, titel="Buchhalter Kreditoren")
    res = _linkedin(mcp)
    assert "aussortierte_dublette" not in res


def test_1184_anderer_firmenname_gleicher_titel_gleicher_ort_wird_gemeldet(env):
    """Muttermarke gegen Konzernunternehmen: die Firmennamen haben nichts gemeinsam, Titel und Ort schon."""
    db, mcp = env
    _aussortiert(db)
    res = _linkedin(mcp, firma="Hansa Marke GmbH")
    d = res["aussortierte_dublette"]
    assert d["grund"] == "titel_plus_ort"
    assert d["firma"] == "Nordwerk Konzern GmbH"
    assert "Muttermarke" in d["hinweis"]


def test_1184_anderer_firmenname_anderer_ort_ist_kein_treffer(env):
    db, mcp = env
    _aussortiert(db, ort="Beispielhausen")
    res = _linkedin(mcp, firma="Hansa Marke GmbH")
    assert "aussortierte_dublette" not in res


def test_1184_anderer_firmenname_ohne_ort_ist_kein_treffer(env):
    """Kein Ort auf beiden Seiten ist kein gleicher Ort: leer gleich leer waere ein Zufallstreffer."""
    db, mcp = env
    _aussortiert(db)
    _aussortiert(db, h="alt1184b", ort="")
    res = _linkedin(mcp, firma="Hansa Marke GmbH", ort="Remote")
    assert "aussortierte_dublette" not in res


def test_1184_aehnlicher_aber_nicht_gleicher_titel_ist_kein_treffer(env):
    """Zwei gemeinsame Begriffe und derselbe Ort reichen nicht, wenn der Rest des Titels abweicht."""
    db, mcp = env
    _aussortiert(db, titel="Senior Vertriebsleiter Maschinenbau Region Sued (m/w/d)")
    res = _linkedin(mcp, firma="Hansa Marke GmbH", titel="Vertriebsleiter Maschinenbau Export (m/w/d)")
    assert "aussortierte_dublette" not in res


def test_1184_ein_allgemeiner_titel_allein_macht_keinen_treffer(env):
    """"Projektleiter" teilen tausend Stellen: ein Wort ist kein Beleg."""
    db, mcp = env
    _aussortiert(db, titel="Projektleiter (m/w/d)")
    res = _linkedin(mcp, firma="Hansa Marke GmbH", titel="Projektleiter (m/w/d)")
    assert "aussortierte_dublette" not in res


def test_1184_dieselbe_google_suchadresse_macht_zwei_stellen_nicht_zu_einer(env):
    """Zwei Treffer einer Suche tragen dieselbe Such-URL: sie ist kein Beleg fuer dieselbe Anzeige."""
    db, mcp = env
    suche = "https://www.google.com/search?q=plm&udm=8"
    _aussortiert(db, titel="Buchhalter Kreditoren", firma="Hansa Marke GmbH", url=suche)
    res = _google(mcp, url=suche, titel="PLM Systemadministrator Teamcenter (m/w/d)", ort="Musterstadt")
    assert "aussortierte_dublette" not in res


def test_1184_gleiche_detail_adresse_ist_ein_treffer(env):
    db, mcp = env
    _aussortiert(db, titel="Buchhalter Kreditoren", firma="Andere Firma", url=ORIGINAL_URL)
    res = _linkedin(mcp, firma="Hansa Marke GmbH")
    assert res["aussortierte_dublette"]["grund"] == "url_match"


@pytest.mark.parametrize("ort, erwartet", [
    ("Köln, Nordrhein-Westfalen", "koeln"),
    ("Koeln", "koeln"),
    ("50667 Köln (Innenstadt)", "koeln"),
    ("Frankfurt am Main", "frankfurt am main"),
    ("Remote", ""),
    ("Beliebiger Ort, Homeoffice", ""),
    ("Deutschland", ""),
    ("", ""),
    (None, ""),
])
def test_1184_ort_schluessel(ort, erwartet):
    from bewerbungs_assistent.duplicate_detection import ort_schluessel
    assert ort_schluessel(ort) == erwartet


# ── die Hilfe fuer Claude und die Module ──────────────────────────────────────────────────────

def test_1184_das_werkzeug_nennt_die_regel_in_seiner_beschreibung(env):
    _, mcp = env

    async def _beschreibung(name):
        return (await mcp.get_tool(name)).description

    anlegen = asyncio.run(_beschreibung("stelle_manuell_anlegen"))
    assert "Aus Google Jobs gelten Remote und Ort erst mit dem Original" in anlegen
    assert "auch Aussortiertes" in anlegen
    assert len(anlegen) <= 600, "der Katalog erlaubt hoechstens 600 Zeichen Beschreibung"
    schema = asyncio.run(mcp.get_tool("stelle_manuell_anlegen")).parameters["properties"]
    assert "Google" in schema["remote"]["description"] and "Google" in schema["ort"]["description"]
    url_hinweis = _call(mcp, "google_jobs_url", {"keyword": "PLM"})["hinweis"]
    assert "Remote und Ort der Karte gelten nicht" in url_hinweis


def test_1184_die_nachbarmodule_gibt_es_und_der_kopf_grenzt_sie_ab():
    """Wie bei den anderen Modulen mit aehnlichem Auftrag: die Abgrenzung steht im Kopf, und die Nachbarn existieren."""
    from bewerbungs_assistent.services import google_angaben, google_alert, remote_jobspy, weiterverbreiter
    for name in ("google_alert", "weiterverbreiter", "remote_jobspy"):
        assert name in google_angaben.__doc__
    assert "google_angaben" in remote_jobspy.__doc__
    assert google_alert and weiterverbreiter
