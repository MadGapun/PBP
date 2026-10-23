"""#1201-#1206 (Funde der unabhängigen Prüfung des Release-Zweigs, 14.10.2026): Backend.

* #1201 — der Quellenschlüssel `Google Jobs` (andere Schreibweise) umging die Regeln aus #1184.
* #1202 — ein verfallener Fehlzähler des Nachladens lebte durch den frischen Zeitstempel wieder auf (`holen`).
* #1203 — Hinweise aus Alert-Mails: ein Umlaut am Wortanfang oder doppelter Leerraum verhinderte „angelegt“.
* #1204 — die Vorschau von `browser_treffer_uebernehmen` zählte bei ähnlichen Titeln mehr als der Lauf.
* #1205 — Hinweise jenseits der 500 neuesten waren weder auflistbar noch über die Kennung erreichbar.
* #1206 — „Dokumenttyp ändern“ mit einem Nicht-Text ergab HTTP 500 statt 400.

Alle Firmen, Orte und Adressen sind erfunden; jede Datenbank liegt in tmp_path.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import test_mcp_registry as reg
from bewerbungs_assistent.services import document_handlers, google_angaben, nachladen, stellen_hinweise, text_nachzug

DETAIL = "https://karriere.beispiel-werk.example/jobs/4711"
TEXT = ("Ihre Aufgaben: Sie betreuen die Engineering-Systeme unseres Werks, pflegen Stuecklisten und Freigabeprozesse. "
        "Ihr Profil: abgeschlossenes Studium und mehrjaehrige Erfahrung.")


@pytest.fixture
def umgebung(tmp_path):
    mcp, db = reg._build_test_server(tmp_path)
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    yield mcp, db
    db.close()


@pytest.fixture
def client(umgebung):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    _, db = umgebung
    alt = dash._db
    dash._db = db
    try:
        yield TestClient(dash.app)
    finally:
        dash._db = alt


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _stellen(db):
    return db.connect().execute("SELECT hash, title, source, remote_level FROM jobs").fetchall()


# ══ #1201 ════════════════════════════════════════════════════════════════════════════════════════

SCHREIBWEISEN = ["google_jobs", "Google Jobs", "google jobs", "google-jobs", "Google", "googlejobs", "GOOGLE_JOBS", "  Google Jobs  ",
                 "Google for Jobs"]


@pytest.mark.parametrize("quelle", SCHREIBWEISEN)
def test_1201_jede_schreibweise_gilt_als_google_quelle(quelle):
    assert google_angaben.ist_google_quelle(quelle)
    assert google_angaben.google_schluessel(quelle) == "google_jobs"
    assert google_angaben.quelle_normalisiert(quelle) == "google_jobs"


@pytest.mark.parametrize("quelle", ["jobspy_google", "JobSpy Google", "jobspy-google"])
def test_1201_auch_die_jobspy_variante_hat_eine_schreibweise(quelle):
    assert google_angaben.google_schluessel(quelle) == "jobspy_google"


@pytest.mark.parametrize("quelle", ["stepstone", "heise_jobs", "google_alert", "", None, "googler", "Google Maps", "xing"])
def test_1201_andere_quellen_bleiben_andere_quellen(quelle):
    assert not google_angaben.ist_google_quelle(quelle)
    assert google_angaben.google_schluessel(quelle) == ""


def test_1201_die_normalisierung_beruehrt_andere_schluessel_nur_in_klein_und_ohne_rand():
    assert google_angaben.quelle_normalisiert("  StepStone ") == "stepstone"
    assert google_angaben.quelle_normalisiert(None) == ""


@pytest.mark.parametrize("quelle", SCHREIBWEISEN)
def test_1201_stelle_manuell_anlegen_sperrt_google_ohne_original_in_jeder_schreibweise(umgebung, quelle):
    mcp, db = umgebung
    erg = _call(mcp, "stelle_manuell_anlegen", {
        "titel": "PLM Systemadministrator (m/w/d)", "firma": "Hansa Marke GmbH", "ort": "Beliebiger Ort, Homeoffice",
        "quelle": quelle, "remote": "remote"})
    assert erg.get("warnung") == "google_original_fehlt", erg
    assert _stellen(db) == [], "es darf keine Stelle entstehen"


@pytest.mark.parametrize("quelle", ["Google Jobs", "google-jobs", "Google"])
def test_1201_mit_url_wird_angelegt_unter_vorbehalt_und_unter_dem_einen_schluessel(umgebung, quelle):
    mcp, db = umgebung
    erg = _call(mcp, "stelle_manuell_anlegen", {
        "titel": "PLM Systemadministrator (m/w/d)", "firma": "Hansa Marke GmbH", "ort": "Beliebiger Ort, Homeoffice",
        "quelle": quelle, "remote": "remote", "url": DETAIL})
    assert erg["status"] == "angelegt", erg
    assert erg["google_vorbehalt"]["remote"]["gespeichert"] == "unbekannt", "Googles Homeoffice gilt nicht ohne Original"
    (zeile,) = _stellen(db)
    assert zeile["source"] == "google_jobs", "gespeichert wird der eine Schluessel, nicht der freie Text"
    assert zeile["remote_level"] != "remote"


def test_1201_browser_treffer_uebernehmen_speichert_den_normalisierten_schluessel(umgebung):
    mcp, db = umgebung
    erg = _call(mcp, "browser_treffer_uebernehmen", {
        "quelle": "Google Jobs", "dry_run": False,
        "treffer": [{"titel": "PLM Systemadministrator (m/w/d)", "firma": "Hansa Marke GmbH", "ort": "Beliebiger Ort, Homeoffice",
                     "remote": "remote", "url": DETAIL}]})
    assert erg["quelle"] == "google_jobs", erg
    (zeile,) = _stellen(db)
    assert zeile["source"] == "google_jobs" and zeile["remote_level"] != "remote"
    assert len(db.get_scraper_runs("google_jobs")) == 1, "auch der verbuchte Lauf steht unter dem einen Schluessel"
    assert db.get_scraper_runs("Google Jobs") == []


def test_1201_ein_google_treffer_ohne_anker_nennt_in_jeder_schreibweise_die_suche_nach_dem_original(umgebung):
    mcp, db = umgebung
    erg = _call(mcp, "browser_treffer_uebernehmen", {
        "quelle": "google jobs", "treffer": [{"titel": "PLM Systemadministrator (m/w/d)", "firma": "Hansa Marke GmbH",
                                              "url": "https://www.google.com/search?q=plm&ibp=htl;jobs"}]})
    (zeile,) = erg["uebersprungen"]
    assert zeile["grund"] == "google_original_fehlt" and zeile["original_suchen"]["suchen"]


# ══ #1202 ════════════════════════════════════════════════════════════════════════════════════════

def _alt(tage: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=tage)).isoformat()


def _stelle_ohne_text(db, nr: int = 1) -> str:
    pid = db.get_active_profile_id()
    h = f"{pid}:pruef{nr:03d}"
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, url, description, score, is_active, source, found_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (h, pid, f"Planer {nr}", "Musterbetrieb GmbH", f"https://example.com/stelle/{nr}", "", 50, 1, "manuell", "2026-10-01T10:00:00"))
    conn.commit()
    return h


def _holen(db, hashes, befunde):
    import unittest.mock as mock
    folge = iter(befunde)
    with mock.patch.object(nachladen, "beschreibung_holen", lambda url, client, timeout=15: next(folge)):
        return text_nachzug.holen(db, hashes, client=object(), max_jobs=5)


def _verfallen(db, h, zaehler=3, tage=30):
    db.set_setting(f"refetch_fail:{h}", str(zaehler))
    db.set_setting(f"refetch_last:{h}", _alt(tage))


def test_1202_ein_fehlschlag_nach_dem_verfall_setzt_den_zaehler_auf_eins(umgebung):
    """Die Lücke aus der Prüfung: die vorhandenen Tests rufen `fehlversuch_zaehlen` direkt auf, nie `holen` - und `holen`
    erneuerte den Zeitstempel VOR dem Zählen, sodass der verfallene Wert (3) wieder galt und auf 4 sprang."""
    _, db = umgebung
    h = _stelle_ohne_text(db)
    _verfallen(db, h)
    erg = _holen(db, [h], [nachladen.Befund(status=nachladen.GEBLOCKT, http_status=403, text="")])
    assert erg["fehlgeschlagen"] == 1
    assert text_nachzug._fehlversuche(db, h) == 1
    assert db.get_setting(f"refetch_fail:{h}", "0") == "1", "gespeichert steht die frische Runde, nicht 4"


def test_1202_ein_netzfehler_nach_dem_verfall_haelt_die_stelle_nicht_im_backoff(umgebung):
    _, db = umgebung
    h = _stelle_ohne_text(db)
    _verfallen(db, h)
    erg = _holen(db, [h], [nachladen.Befund(status=nachladen.FEHLER, http_status=None, text="")])
    assert erg["netzfehler"] == 1 and erg["fehlgeschlagen"] == 0
    assert text_nachzug._fehlversuche(db, h) == 0
    assert text_nachzug.auswahl(db, limit=5) == [h], "der Netzfehler hat sie nicht bestraft"


def test_1202_ein_noch_geltender_zaehler_bleibt_und_zaehlt_weiter(umgebung):
    _, db = umgebung
    h = _stelle_ohne_text(db)
    _verfallen(db, h, zaehler=2, tage=3)
    _holen(db, [h], [nachladen.Befund(status=nachladen.GEBLOCKT, http_status=403, text="")])
    assert text_nachzug._fehlversuche(db, h) == 3


def test_1202_ein_erfolg_nach_dem_verfall_loescht_den_zaehler(umgebung):
    _, db = umgebung
    h = _stelle_ohne_text(db)
    _verfallen(db, h)
    _holen(db, [h], [nachladen.Befund(status=nachladen.GELESEN, http_status=200, text="Aufgaben und Anforderungen. " * 10)])
    assert text_nachzug._fehlversuche(db, h) == 0 and db.get_setting(f"refetch_fail:{h}", "0") == "0"


# ══ #1203 ════════════════════════════════════════════════════════════════════════════════════════

# (Titel im Hinweis, Firma im Hinweis, Titel der Stelle, Firma der Stelle): die Schreibweisen der Mail und der Stelle weichen ab
@pytest.mark.parametrize("hinweis_titel,hinweis_firma,titel,firma", [
    ("Übergreifender Projektleiter PLM (m/w/d)", "Österreichische Werke GmbH",
     "Übergreifender Projektleiter PLM (m/w/d)", "Österreichische Werke GmbH"),            # Umlaute am Wortanfang
    ("ÜBERGREIFENDER PROJEKTLEITER PLM", "ÖSTERREICHISCHE WERKE GMBH",
     "Übergreifender Projektleiter PLM", "Österreichische Werke GmbH"),                   # Grossschreibung mit Umlauten
    ("Senior  Projektleiter   PLM", "Nordlicht  Werke GmbH",
     "Senior Projektleiter PLM", "Nordlicht Werke GmbH"),                                 # doppelter Leerraum innen
    ("Projektleiter PLM", "Nordlicht Werke GmbH", "Projektleiter PLM", "Nordlicht Werke GmbH"),   # Kontrolle: ASCII
])
def test_1203_ein_hinweis_wird_beim_anlegen_der_stelle_erledigt(umgebung, hinweis_titel, hinweis_firma, titel, firma):
    mcp, db = umgebung
    stellen_hinweise.merken(db, [{"titel": hinweis_titel, "firma": hinweis_firma, "ort": "Wien"}])
    assert stellen_hinweise.zaehlen(db)["offen"] == 1
    erg = _call(mcp, "stelle_manuell_anlegen", {"titel": titel, "firma": firma, "url": DETAIL, "quelle": "manuell"})
    assert erg["status"] == "angelegt", erg
    z = stellen_hinweise.zaehlen(db)
    assert z["offen"] == 0 and z["angelegt"] == 1, z


@pytest.mark.parametrize("hinweis_titel,hinweis_firma,titel,firma", [
    ("ÜBERGREIFENDER PROJEKTLEITER PLM", "ÖSTERREICHISCHE WERKE GMBH",
     "Übergreifender Projektleiter PLM", "Österreichische Werke GmbH"),
    ("Senior  Projektleiter   PLM", "Nordlicht  Werke GmbH", "Senior Projektleiter PLM", "Nordlicht Werke GmbH"),
])
def test_1203_ein_hinweis_zu_einer_vorhandenen_stelle_steht_gleich_als_angelegt_da(
        umgebung, hinweis_titel, hinweis_firma, titel, firma):
    mcp, db = umgebung
    assert _call(mcp, "stelle_manuell_anlegen", {"titel": titel, "firma": firma, "url": DETAIL, "quelle": "manuell"})["status"] == "angelegt"
    erg = stellen_hinweise.merken(db, [{"titel": hinweis_titel, "firma": hinweis_firma, "ort": "Wien"}])
    assert erg["schon_stelle"] == 1 and erg["neu"] == 0, erg
    assert stellen_hinweise.zaehlen(db)["angelegt"] == 1


def test_1203_der_bestand_wird_je_lauf_einmal_gelesen_nicht_je_hinweis(umgebung, monkeypatch):
    mcp, db = umgebung
    aufrufe = []
    echt = stellen_hinweise._bestand_index
    monkeypatch.setattr(stellen_hinweise, "_bestand_index", lambda d: (aufrufe.append(1), echt(d))[1])
    stellen_hinweise.merken(db, [{"titel": f"Titel {i}", "firma": f"Firma {i}", "ort": "Wien"} for i in range(12)])
    assert len(aufrufe) == 1


# ══ #1204 ════════════════════════════════════════════════════════════════════════════════════════

AEHNLICH = [
    {"titel": "Senior Projektleiter PLM (m/w/d)", "firma": "Nordlicht Werke GmbH", "url": "https://k1.example/jobs/1", "ort": "Musterstadt"},
    {"titel": "Senior Projektleiter PLM (w/m/d)", "firma": "Nordlicht Werke GmbH", "url": "https://k1.example/jobs/2", "ort": "Musterstadt"},
    {"titel": "Einkaufsleiter Beschaffung (m/w/d)", "firma": "Sonnenhof Systeme AG", "url": "https://k3.example/jobs/3"},
]


def test_1204_vorschau_und_lauf_nennen_bei_aehnlichen_titeln_dieselben_zahlen(umgebung):
    mcp, db = umgebung
    vorschau = _call(mcp, "browser_treffer_uebernehmen", {"quelle": "stepstone", "treffer": AEHNLICH})
    lauf = _call(mcp, "browser_treffer_uebernehmen", {"quelle": "stepstone", "treffer": AEHNLICH, "dry_run": False})
    assert vorschau["status"] == "vorschau" and lauf["status"] == "uebernommen"
    for schluessel in ("angelegt", "uebersprungen", "uebergeben"):
        assert vorschau["trichter"][schluessel] == lauf["trichter"][schluessel], (schluessel, vorschau["trichter"], lauf["trichter"])
    assert lauf["trichter"]["angelegt"] == 2 and lauf["trichter"]["uebersprungen"] == 1
    assert vorschau["trichter"]["gruende"] == lauf["trichter"]["gruende"] == {"duplikat_aktiv": 1}
    assert [z["titel"] for z in vorschau["uebersprungen"]] == [z["titel"] for z in lauf["uebersprungen"]]
    assert len(db.get_active_jobs()) == 2


def test_1204_die_vorschau_schreibt_dabei_nichts(umgebung):
    mcp, db = umgebung
    vorher = db.connect().execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    _call(mcp, "browser_treffer_uebernehmen", {"quelle": "stepstone", "treffer": AEHNLICH})
    assert db.connect().execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == vorher


def test_1204_verschiedene_stellen_derselben_firma_bleiben_zwei(umgebung):
    mcp, db = umgebung
    treffer = [{"titel": "Senior Projektleiter PLM (m/w/d)", "firma": "Nordlicht Werke GmbH", "url": "https://k1.example/jobs/1"},
               {"titel": "Einkaufsleiter Beschaffung (m/w/d)", "firma": "Nordlicht Werke GmbH", "url": "https://k1.example/jobs/2"}]
    vorschau = _call(mcp, "browser_treffer_uebernehmen", {"quelle": "stepstone", "treffer": treffer})
    lauf = _call(mcp, "browser_treffer_uebernehmen", {"quelle": "stepstone", "treffer": treffer, "dry_run": False})
    assert vorschau["trichter"]["angelegt"] == lauf["trichter"]["angelegt"] == 2


# ══ #1205 ════════════════════════════════════════════════════════════════════════════════════════

def _hinweise_fuellen(db, anzahl=522):
    conn = db.connect()
    stellen_hinweise.tabelle_anlegen(conn)
    pid = db.get_active_profile_id()
    start = datetime(2026, 1, 1)
    for i in range(anzahl):
        zeit = (start + timedelta(minutes=i)).isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO stellen_hinweise (id, profile_id, titel, firma, ort, status, anzahl_mails, erstellt_am, aktualisiert_am) "
            "VALUES (?,?,?,?,?,?,?,?,?)", (f"h{i:04d}", pid, f"Titel {i}", f"Firma {i}", "Wien", "offen", 1, zeit, zeit))
    conn.commit()


def test_1205_ein_hinweis_jenseits_der_500_ist_direkt_erreichbar(umgebung):
    mcp, db = umgebung
    _hinweise_fuellen(db)
    assert len(stellen_hinweise.liste(db, status="alle", limit=500)) == 500
    aeltester = stellen_hinweise.holen(db, "h0000")          # der 522. von oben: in keiner Liste mit limit 500
    assert aeltester and aeltester["titel"] == "Titel 0"
    assert stellen_hinweise.holen(db, "gibt-es-nicht") is None
    suche = _call(mcp, "stellen_hinweise_verwalten", {"aktion": "suche", "hinweis_id": "h0000"})
    assert suche["status"] == "ok" and suche["hinweis"]["titel"] == "Titel 0", suche
    assert _call(mcp, "stellen_hinweise_verwalten", {"aktion": "verwerfen", "hinweis_id": "h0000"})["status"] == "ok"
    assert _call(mcp, "stellen_hinweise_verwalten", {"aktion": "zurueckholen", "hinweis_id": "h0000"})["status"] == "ok"


def test_1205_die_liste_blaettert_mit_offset_und_nennt_die_gesamtzahl(umgebung):
    mcp, db = umgebung
    _hinweise_fuellen(db)
    erste = _call(mcp, "stellen_hinweise_verwalten", {"limit": 30})
    assert erste["anzahl"] == 30 and erste["gesamt"] == 522 and erste["offset"] == 0 and erste["weitere"] == 492
    letzte = _call(mcp, "stellen_hinweise_verwalten", {"limit": 30, "offset": 500})
    assert letzte["anzahl"] == 22 and letzte["weitere"] == 0
    assert letzte["hinweise"][-1]["id"] == "h0000", "der aelteste steht am Ende der letzten Seite"
    ids = {h["id"] for h in erste["hinweise"]} | {h["id"] for h in letzte["hinweise"]}
    assert len(ids) == 52, "keine Ueberschneidung zwischen den Seiten"


def test_1205_der_endpunkt_blaettert_ebenso(umgebung, client):
    _, db = umgebung
    _hinweise_fuellen(db)
    antwort = client.get("/api/stellen-hinweise", params={"status": "offen", "limit": 100, "offset": 500}).json()
    assert len(antwort["hinweise"]) == 22 and antwort["gesamt"] == 522 and antwort["offset"] == 500 and antwort["weitere"] == 0
    erste = client.get("/api/stellen-hinweise", params={"status": "offen", "limit": 100}).json()
    assert len(erste["hinweise"]) == 100 and erste["weitere"] == 422


def test_1205_ein_offset_hinter_dem_ende_ist_eine_leere_seite_kein_fehler(umgebung):
    mcp, db = umgebung
    _hinweise_fuellen(db, anzahl=3)
    erg = _call(mcp, "stellen_hinweise_verwalten", {"offset": 50})
    assert erg["status"] == "ok" and erg["anzahl"] == 0 and erg["gesamt"] == 3 and erg["weitere"] == 0


# ══ #1206 ════════════════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("wert", [5, 1.5, ["absage"], {"a": 1}, True])
def test_1206_ein_nicht_text_wird_wie_ein_unbekannter_typ_abgelehnt(umgebung, wert):
    _, db = umgebung
    erg = document_handlers.typ_setzen(db, "irgendein-dokument", wert, profile_id=db.get_active_profile_id())
    assert erg["status"] == "unbekannter_typ", erg
    assert erg["erlaubte_typen"] and "Text" in erg["fehler"]


@pytest.mark.parametrize("wert", [None, "", "   ", "gibt-es-nicht"])
def test_1206_leer_und_unbekannt_bleiben_wie_vorher_unbekannt(umgebung, wert):
    _, db = umgebung
    erg = document_handlers.typ_setzen(db, "irgendein-dokument", wert, profile_id=db.get_active_profile_id())
    assert erg["status"] == "unbekannter_typ" and erg["erlaubte_typen"]


@pytest.mark.parametrize("koerper", [{"doc_type": 5}, {"doc_type": ["absage"]}, {"doc_type": {"a": 1}}, [1, 2], "absage", 7])
def test_1206_der_endpunkt_antwortet_400_mit_den_erlaubten_typen_statt_500(umgebung, client, koerper):
    antwort = client.put("/api/document/irgendein-dokument/doc-type", json=koerper)
    assert antwort.status_code == 400, (antwort.status_code, antwort.text)
    assert antwort.json()["erlaubte_typen"]


def test_1206_ein_gueltiger_typ_wird_weiter_gesetzt(umgebung, client):
    _, db = umgebung
    import time
    pid = db.get_active_profile_id()
    doc_id = "dok-1206"
    conn = db.connect()
    conn.execute("INSERT INTO documents (id, profile_id, filename, filepath, doc_type, created_at) VALUES (?,?,?,?,?,?)",
                 (doc_id, pid, "brief.pdf", "brief.pdf", "sonstiges", time.strftime("%Y-%m-%dT%H:%M:%S")))
    conn.commit()
    antwort = client.put(f"/api/document/{doc_id}/doc-type", json={"doc_type": "absage"})
    assert antwort.status_code == 200 and antwort.json()["doc_type"] == "absage", antwort.text
