"""#1184 a, d, e: ein Google-Treffer ohne Original wird nicht angelegt, Alert-Mails liefern Hinweise statt Stellen, und PBP
bereitet die Suche nach dem Original vor.

Befund (08.10.2026, Echtbestand): fuenf Stellen aus einem Browserlauf ueber Google Jobs, vier mit Kopfdaten ("Volltext nicht
abrufbar") und ohne Anker, eine nur mit einer Firmenseite statt einer Detail-URL. Google nannte "Beliebiger Ort, Homeoffice", die
Originalanzeige einen Ort 570 km entfernt. Die Alert-Mails von Google nennen nur Titel, Firma, Ort und Portal; alle Links laufen ueber
einen Umleiter, und derselbe Treffer kommt mit verschiedenen Orten.

Was seit v1.7.157 galt (b: Remote und Ort erst mit dem Original; c: Hinweis auf Aussortiertes) steht in
`test_v18_google_angaben_1184.py`. Hier: (a) die Sperre, (d) die Hinweisliste, (e) die vorbereitete Suche.
Alle Firmen, Orte und Adressen sind erfunden.
"""
from __future__ import annotations

import asyncio
import json
from urllib.parse import parse_qs, urlparse

import pytest

import test_mcp_registry as reg
from bewerbungs_assistent.services import google_angaben, stellen_hinweise

TEXT = ("Ihre Aufgaben: Sie betreuen die Engineering-Systeme unseres Werks, pflegen Stuecklisten und Freigabeprozesse. "
        "Ihr Profil: abgeschlossenes Studium und mehrjaehrige Erfahrung.")
DETAIL = "https://karriere.beispiel-werk.example/jobs/4711"


@pytest.fixture
def umgebung(tmp_path):
    mcp, db = reg._build_test_server(tmp_path)
    db.save_profile({"name": "Erika Musterfrau"})
    yield mcp, db
    db.close()


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _anlegen(mcp, **kw):
    args = {"titel": "PLM Systemadministrator (m/w/d)", "firma": "Hansa Marke GmbH", "ort": "Beliebiger Ort, Homeoffice",
            "quelle": "google_jobs", "remote": "remote"}
    args.update(kw)
    return _call(mcp, "stelle_manuell_anlegen", args)


def _stellen(db):
    return db.connect().execute("SELECT hash, title FROM jobs").fetchall()


# ══ (a) die Sperre ════════════════════════════════════════════════════════════════════════════

def test_ein_google_treffer_ohne_url_und_ohne_text_wird_nicht_angelegt(umgebung):
    mcp, db = umgebung
    erg = _anlegen(mcp)
    assert erg["status"] == "nicht_angelegt" and erg["warnung"] == "google_original_fehlt", erg
    assert "NICHT angelegt" in erg["nachricht"]
    assert "force=True" in erg["trotzdem_anlegen"]
    assert _stellen(db) == [], "es darf keine Stelle entstehen"


def test_die_antwort_nennt_den_auftrag_die_suche_und_den_weiteren_weg(umgebung):
    mcp, db = umgebung
    such = _anlegen(mcp)["original_suchen"]
    assert "Originalanzeige" in such["auftrag"] and "Karriereseite" in such["auftrag"]
    wo = [s["wo"] for s in such["suchen"]]
    assert wo[0].startswith("Karriereseite des Arbeitgebers") and {"StepStone", "XING"} <= set(wo)
    assert any("Konzernunternehmen" in p for p in such["pruefen"]), "Muttermarke gegen Konzernunternehmen"
    assert "stelle_manuell_anlegen" in such["danach"] and "url=" in such["danach"] and "beschreibung=" in such["danach"]


def test_force_legt_trotzdem_an_mit_dem_vorbehalt(umgebung):
    mcp, db = umgebung
    erg = _anlegen(mcp, force=True)
    assert erg["status"] == "angelegt", erg
    assert erg["google_vorbehalt"]["remote"]["gespeichert"] == "unbekannt", "Googles Homeoffice gilt nicht ohne Original"
    assert len(_stellen(db)) == 1


@pytest.mark.parametrize("url,text", [(DETAIL, ""), ("", TEXT)])
def test_mit_adresse_oder_text_allein_wird_angelegt_unter_vorbehalt(umgebung, url, text):
    mcp, db = umgebung
    erg = _anlegen(mcp, url=url, beschreibung=text)
    assert erg["status"] == "angelegt", erg
    assert "google_vorbehalt" in erg, "ein Anker allein hebt den Vorbehalt nicht auf"


@pytest.mark.parametrize("url", [
    "https://www.google.com/search?q=plm+administrator&ibp=htl;jobs",
    "https://www.stepstone.de/jobs/plm-administrator/in-hamburg",
    # Google-Adressen, die KEINE Suchseite sind (Karte, Jobs-Unterseite): sie fuehren zu Google, nicht zum Arbeitgeber
    "https://www.google.de/maps/place/Musterstadt",
    "https://jobs.google.com/jobs/12345",
])
def test_eine_google_oder_suchadresse_ist_kein_anker(umgebung, url):
    mcp, db = umgebung
    erg = _anlegen(mcp, url=url)
    assert erg["status"] == "nicht_angelegt" and erg["warnung"] == "google_original_fehlt", erg
    assert _stellen(db) == []


def test_auch_die_jobspy_variante_aus_google_ist_betroffen(umgebung):
    mcp, db = umgebung
    erg = _anlegen(mcp, quelle="jobspy_google")
    assert erg["status"] == "nicht_angelegt" and erg["warnung"] == "google_original_fehlt"


def test_andere_quellen_bleiben_unberuehrt(umgebung):
    mcp, db = umgebung
    erg = _anlegen(mcp, quelle="linkedin", remote="hybrid")
    assert erg["status"] == "angelegt", erg
    assert "google_vorbehalt" not in erg and "original_suchen" not in erg


def test_die_sperre_steht_vor_der_vorschau_und_vor_dem_speichern():
    """Die Vorschau (trocken, #1187) und die Anlage laufen durch denselben Weg: die Sperre muss vor beiden stehen, damit die
    Vorschau dieselbe Abweisung sagt wie die Anlage."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent" / "tools" / "jobs.py").read_text(encoding="utf-8")
    rumpf = quelle[quelle.index("def _stelle_uebernehmen("):]
    sperre = rumpf.index('"warnung": "google_original_fehlt"')
    assert sperre < rumpf.index('"status": "wuerde_angelegt"'), "die Vorschau muesste sonst anlegen wollen"
    assert sperre < rumpf.index("db.save_jobs([job])"), "die Sperre muss vor dem Speichern stehen"


def test_ohne_beleg_ist_eine_reine_frage_ohne_nebenwirkung():
    f = google_angaben.ohne_beleg
    assert f("google_jobs", "", "Volltext nicht abrufbar") is True
    assert f("google_jobs", DETAIL, "") is False and f("google_jobs", "", TEXT) is False
    assert f("google_jobs", "https://www.google.de/search?q=x", "") is True
    assert f("linkedin", "", "") is False, "nur Google-Quellen"
    assert f("GOOGLE_JOBS ", "", "") is True, "Gross-/Kleinschreibung und Leerraum"


# ══ (e) die vorbereitete Suche ══════════════════════════════════════════════════════════════════

def test_die_suche_nach_dem_original_ist_kodiert_und_nennt_firma_und_titel():
    such = google_angaben.original_suchen("Teamcenter-Admin (m/w/d)", "Hansa & Söhne GmbH", "Köln")
    web = such["suchen"][0]
    q = parse_qs(urlparse(web["url"]).query)["q"][0]
    assert '"Hansa & Söhne GmbH"' in q and '"Teamcenter-Admin (m/w/d)"' in q and "Karriere" in q
    for s in such["suchen"][1:]:
        assert s["url"].startswith("https://") and " " not in s["url"], s
    assert any("K%C3%B6ln" in s["url"] for s in such["suchen"][1:]), "der Ort steht in den Portal-Suchen"
    assert not any("jobtic" in s["url"] for s in such["suchen"]), "Quellen mit Auflage werden nicht vorgeschlagen"


def test_die_suche_kommt_auch_ohne_firma_und_ort():
    such = google_angaben.original_suchen("PLM Berater", "", "")
    assert such["suchen"] and "PLM Berater" in parse_qs(urlparse(such["suchen"][0]["url"]).query)["q"][0]


# ══ (d) Hinweise statt Stellen ═══════════════════════════════════════════════════════════════════

def _treffer(titel="Teamcenter Administrator", firma="Hansa Marke GmbH", ort="Hamburg", **kw):
    t = {"titel": titel, "firma": firma, "ort": ort, "portal": "XING", "vertragsart": "Vollzeit",
         "veroeffentlicht_am": "2026-09-30", "weiterverbreiter": False, "google_link": "https://www.google.de/search?q=x"}
    t.update(kw)
    return t


def test_die_tabelle_entsteht_erst_beim_ersten_hinweis(umgebung):
    _, db = umgebung
    def da():
        return db.connect().execute("SELECT 1 FROM sqlite_master WHERE name='stellen_hinweise'").fetchone() is not None
    assert not da() and stellen_hinweise.zaehlen(db) == {"offen": 0, "angelegt": 0, "verworfen": 0}
    assert not da(), "Zaehlen legt nichts an"
    stellen_hinweise.merken(db, [_treffer()])
    assert da()


def test_ein_hinweis_ist_keine_stelle(umgebung):
    _, db = umgebung
    erg = stellen_hinweise.merken(db, [_treffer(), _treffer(titel="PDM Berater")], suchanfrage="PLM Hamburg")
    assert erg == {"neu": 2, "bekannt": 0, "schon_stelle": 0}
    assert db.get_active_jobs() == [] and _stellen(db) == []
    h = {x["titel"]: x for x in stellen_hinweise.liste(db)}
    assert h["PDM Berater"]["suchanfrage"] == "PLM Hamburg" and h["PDM Berater"]["status"] == "offen"


def test_derselbe_treffer_mit_anderem_ort_wird_ein_hinweis_mit_zwei_orten(umgebung):
    _, db = umgebung
    stellen_hinweise.merken(db, [_treffer(ort="Hamburg")])
    erg = stellen_hinweise.merken(db, [_treffer(ort="Köln"), _treffer(ort="Hamburg")])
    assert erg == {"neu": 0, "bekannt": 2, "schon_stelle": 0}
    (h,) = stellen_hinweise.liste(db)
    assert h["anzahl_mails"] == 3
    assert h["ort"].split("; ") == ["Hamburg", "Köln"], "der Widerspruch ist selbst eine Auskunft"


def test_schreibweise_und_leerraum_machen_keinen_zweiten_hinweis(umgebung):
    _, db = umgebung
    stellen_hinweise.merken(db, [_treffer(titel="Teamcenter Administrator", firma="Hansa Marke GmbH")])
    stellen_hinweise.merken(db, [_treffer(titel="  teamcenter   ADMINISTRATOR ", firma="hansa marke gmbh")])
    assert len(stellen_hinweise.liste(db)) == 1


def test_was_schon_eine_stelle_ist_steht_gleich_als_angelegt_da(umgebung):
    mcp, db = umgebung
    _anlegen(mcp, quelle="linkedin", titel="Teamcenter Administrator", firma="Hansa Marke GmbH", ort="Hamburg")
    erg = stellen_hinweise.merken(db, [_treffer()])
    assert erg == {"neu": 0, "bekannt": 0, "schon_stelle": 1}
    (h,) = stellen_hinweise.liste(db, status="alle")
    assert h["status"] == "angelegt" and h["job_hash"]
    assert stellen_hinweise.liste(db, status="offen") == []


def test_wird_die_stelle_spaeter_angelegt_ist_der_hinweis_erledigt(umgebung):
    mcp, db = umgebung
    stellen_hinweise.merken(db, [_treffer()])
    (h,) = stellen_hinweise.liste(db)
    erg = _anlegen(mcp, titel="Teamcenter Administrator", firma="Hansa Marke GmbH", url=DETAIL, beschreibung=TEXT, ort="Musterstadt")
    assert erg["status"] == "angelegt"
    (h,) = stellen_hinweise.liste(db, status="alle")
    assert h["status"] == "angelegt" and h["job_hash"] == erg["hash"]
    assert stellen_hinweise.zaehlen(db) == {"offen": 0, "angelegt": 1, "verworfen": 0}


def test_verwerfen_und_zurueckholen(umgebung):
    _, db = umgebung
    stellen_hinweise.merken(db, [_treffer()])
    (h,) = stellen_hinweise.liste(db)
    assert stellen_hinweise.verwerfen(db, h["id"]) is True
    assert stellen_hinweise.liste(db) == [] and len(stellen_hinweise.liste(db, status="verworfen")) == 1
    assert stellen_hinweise.verwerfen(db, h["id"]) is False, "nur Offenes laesst sich verwerfen"
    assert stellen_hinweise.wiederherstellen(db, h["id"]) is True and len(stellen_hinweise.liste(db)) == 1
    assert stellen_hinweise.verwerfen(db, "gibt-es-nicht") is False


def test_hinweise_gehoeren_zum_profil(umgebung):
    mcp, db = umgebung
    stellen_hinweise.merken(db, [_treffer()])
    erstes = db.get_active_profile_id()
    zweites = db.create_profile("Max Beispiel")
    assert db.switch_profile(zweites)
    assert stellen_hinweise.liste(db) == [], "ein anderes Profil sieht die Hinweise nicht"
    assert stellen_hinweise.zaehlen(db)["offen"] == 0
    stellen_hinweise.merken(db, [_treffer()])
    assert len(stellen_hinweise.liste(db)) == 1, "derselbe Treffer ist im anderen Profil ein eigener Hinweis"
    db.switch_profile(erstes)
    assert len(stellen_hinweise.liste(db)) == 1


def test_das_loeschen_der_stellen_nimmt_die_hinweise_mit():
    from bewerbungs_assistent.services import loeschbereiche
    assert "stellen_hinweise" in loeschbereiche.BEREICHE["stellen"]
    assert "stellen_hinweise" in loeschbereiche._NICHT_IN_JEDER_DATENBANK


def test_die_alert_mail_legt_keine_stelle_an_und_wird_archiviert():
    """Beide Verbraucher des Ergebnisses (Upload und Werkzeug) archivieren die Mail auch nach 'Hinweise notiert'."""
    from pathlib import Path
    paket = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
    dash = (paket / "dashboard.py").read_text(encoding="utf-8")
    tool = (paket / "tools" / "dokumente.py").read_text(encoding="utf-8")
    assert 'newsletter_result.get("status") in ("uebernommen", "hinweise_notiert")' in dash
    assert 'result.get("status") in ("uebernommen", "hinweise_notiert")' in tool


# ══ Die Anleitung an Claude ═════════════════════════════════════════════════════════════════════

def test_die_anleitung_zum_google_lauf_nennt_die_ausnahme_von_der_im_zweifel_regel(umgebung):
    mcp, db = umgebung
    erg = _call(mcp, "google_jobs_url", {"keyword": "PLM"})
    erg = erg.get("result", erg) if set(erg) == {"result"} else erg
    hinweis = " ".join(erg["hinweis"].split())
    assert "Ausnahme (#1184)" in hinweis and "google_original_fehlt" in hinweis
    assert "stellen_hinweise_verwalten" in hinweis, "Mail-Treffer sind Hinweise, keine Stellen"
    assert "Lege jede Stelle an" in hinweis, "die Im-Zweifel-Regel (#1187) bleibt, die Ausnahme steht dahinter"


# ══ Werkzeug und Schnittstellen ══════════════════════════════════════════════════════════════════

def test_das_werkzeug_zeigt_sucht_verwirft_und_holt_zurueck(umgebung):
    mcp, db = umgebung
    stellen_hinweise.merken(db, [_treffer(), _treffer(titel="PDM Berater")])
    liste = _call(mcp, "stellen_hinweise_verwalten", {})
    assert liste["status"] == "ok" and liste["anzahl"] == 2 and liste["zaehlung"]["offen"] == 2
    assert {h["titel"] for h in liste["hinweise"]} == {"Teamcenter Administrator", "PDM Berater"}
    assert "stelle_manuell_anlegen" in liste["naechster_schritt"]
    hid = liste["hinweise"][0]["id"]
    suche = _call(mcp, "stellen_hinweise_verwalten", {"aktion": "suche", "hinweis_id": hid})
    assert suche["status"] == "ok" and suche["original_suchen"]["suchen"][0]["wo"].startswith("Karriereseite")
    assert _call(mcp, "stellen_hinweise_verwalten", {"aktion": "verwerfen", "hinweis_id": hid})["status"] == "ok"
    assert _call(mcp, "stellen_hinweise_verwalten", {})["anzahl"] == 1
    assert _call(mcp, "stellen_hinweise_verwalten", {"aktion": "zurueckholen", "hinweis_id": hid})["status"] == "ok"
    assert _call(mcp, "stellen_hinweise_verwalten", {})["anzahl"] == 2


def test_das_werkzeug_nennt_fehler_statt_still_nichts_zu_tun(umgebung):
    mcp, db = umgebung
    assert "fehler" in _call(mcp, "stellen_hinweise_verwalten", {"aktion": "verwerfen"})
    assert "fehler" in _call(mcp, "stellen_hinweise_verwalten", {"aktion": "verwerfen", "hinweis_id": "gibt-es-nicht"})
    assert "fehler" in _call(mcp, "stellen_hinweise_verwalten", {"aktion": "suche", "hinweis_id": "gibt-es-nicht"})
    assert "fehler" in _call(mcp, "stellen_hinweise_verwalten", {"aktion": "erfinden"})


@pytest.fixture
def client(umgebung):
    import bewerbungs_assistent.dashboard as dash
    _, db = umgebung
    alt = dash._db
    dash._db = db
    from fastapi.testclient import TestClient
    yield TestClient(dash.app)
    dash._db = alt


def test_die_schnittstelle_liefert_hinweise_mit_vorbereiteter_suche(client, umgebung):
    _, db = umgebung
    stellen_hinweise.merken(db, [_treffer()])
    j = client.get("/api/stellen-hinweise").json()
    assert j["zaehlung"]["offen"] == 1 and len(j["hinweise"]) == 1
    h = j["hinweise"][0]
    assert h["titel"] == "Teamcenter Administrator" and h["suche"][0]["wo"].startswith("Karriereseite")
    assert client.post(f"/api/stellen-hinweise/{h['id']}/verwerfen").json() == {"status": "ok"}
    assert client.get("/api/stellen-hinweise").json()["hinweise"] == []
    assert client.post(f"/api/stellen-hinweise/{h['id']}/zurueckholen").json() == {"status": "ok"}
    assert client.post("/api/stellen-hinweise/gibt-es-nicht/verwerfen").status_code == 404
    assert client.post("/api/stellen-hinweise/gibt-es-nicht/zurueckholen").status_code == 404


def test_die_schnittstelle_ohne_hinweise_ist_leer_und_legt_nichts_an(client, umgebung):
    _, db = umgebung
    j = client.get("/api/stellen-hinweise").json()
    # #1205: dazu die Blaetter-Angaben (gesamt, offset, weitere) - die Felder davor bleiben, wie sie waren
    assert j == {"zaehlung": {"offen": 0, "angelegt": 0, "verworfen": 0}, "hinweise": [], "gesamt": 0, "offset": 0, "weitere": 0}
