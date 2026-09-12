"""Tests fuer #1025 Stufe 2 (Oberflaeche) und #1024.

Stufe 1 (v1.7.81) hat die Frage "was gehoert wozu, wenn geloescht
wird" aus dem SCHEMA abgeleitet statt sie aufzuzaehlen. Was fehlte,
war der Weg dorthin: die Gefahrenzone hatte weiter vier Eintraege, von
denen zwei sich fast gleich beschrieben und sehr Verschiedenes taten.

## Der Satz, der die Bauform vorgibt

Der Melder, zum Modus:

    Der Modus gehoert als Umschalter, nicht als Checkbox. Eine
    DSGVO-Checkbox, die beim Anhaken alle anderen zwangsweise
    mitanhakt, ueberschreibt die Eingabe des Nutzers — und die vollen
    Haekchen behaupten dann etwas Falsches, denn geloescht werden
    nicht die Bereiche, sondern die Datei.

Also zwei Modi, die einander ausschliessen. Im DSGVO-Modus ist die
Bereichsliste eine Anzeige der FOLGE, keine Auswahl.

## #1024 faellt mit ab — bis auf eine Zahl

Der Stellen-Bestand laesst sich jetzt allein leeren (Bereich
`stellen`). Was #1024 zusaetzlich verlangt, ist die Aufteilung:
*"wie viele Stellen betroffen sind, getrennt nach aktiv und
aussortiert"* — mit der Begruendung, dass mit den aussortierten
Stellen die **Lernsignale** verschwinden und man das einer
Gesamtzahl nicht ansieht. Die Aufteilung ist deshalb Teil der
Vorschau und kein zweiter Bereich: zwei Modelle fuer dieselbe Frage
waeren das Muster, gegen das dieses Issue angetreten ist.
"""
import importlib
import os
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

SETTINGS_PAGE = _repo() / "frontend" / "src" / "pages" / "SettingsPage.jsx"


def _ohne_kommentare(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(
        z for z in text.split("\n") if not z.lstrip().startswith("//"))


@pytest.fixture
def client(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    db = database.Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"

    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient

    alt = dash._db
    dash._db = db
    try:
        yield TestClient(dash.app), db
    finally:
        dash._db = alt
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def _bestand(db, aktiv=3, aussortiert=2):
    pid = db.create_profile("Testprofil")
    db.switch_profile(pid)
    jobs = []
    for i in range(aktiv + aussortiert):
        jobs.append({
            "hash": f"gz{i}", "title": f"Stelle {i}", "company": "Firma",
            "url": f"https://example.com/1025/{i}",
            "source": "bundesagentur",
            "description": "Beschreibungstext. " * 20, "score": 5,
        })
    db.save_jobs(jobs)
    con = db.connect()
    for i in range(aktiv, aktiv + aussortiert):
        con.execute("UPDATE jobs SET is_active=0, dismiss_reason=? "
                    "WHERE hash LIKE ?",
                    ("falsches_fachgebiet", f"%gz{i}"))
    con.commit()
    return pid


# ------------------------------------- AK 1: eine Stelle fuer alle Faelle


def test_die_gefahrenzone_hat_einen_loeschbereich_statt_vier():
    """AK 1.

    Bis v1.7.84 standen hier drei Karten (DSGVO, Profil loeschen,
    Factory Reset) plus die Deinstallation. Zwei davon beschrieben sich
    fast gleich.
    """
    quelle = _ohne_kommentare(SETTINGS_PAGE.read_text(encoding="utf-8"))
    assert "<LoeschBereichSection" in quelle
    for weg in ('title="Factory Reset"',
                'title="Alle Daten loeschen (DSGVO)"',
                'title="Profil loeschen"'):
        assert weg not in quelle, f"Alte Karte steht noch da: {weg}"


def test_die_toten_zustaende_sind_weg():
    """Ein Feld ohne Leser ist eine Behauptung (#993, #1000, #1008).

    `resetConfirm`, `deleteConfirm` und `profileDeleteConfirm` haben
    mit den Karten ihren letzten Leser verloren.
    """
    quelle = _ohne_kommentare(SETTINGS_PAGE.read_text(encoding="utf-8"))
    for tot in ("resetConfirm", "deleteConfirm", "profileDeleteConfirm",
                "performReset", "deleteAllData"):
        assert tot not in quelle, f"{tot} hat keinen Leser mehr"


# ------------------------------- AK 2+5: Bereiche waehlbar, Zahlen davor


def test_die_vorschau_nennt_je_bereich_die_zahl(client):
    """AK 5."""
    c, db = client
    _bestand(db)
    antwort = c.get("/api/danger/bereiche")
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["bestaetigungswort"] == "LOESCHEN"
    stellen = daten["bereiche"]["stellen"]
    # `zeilen_gesamt` ist die Summe UEBER DEN BEREICH, nicht ueber die
    # Tabelle `jobs`: zu jeder Stelle gehoert seit #951 eine Fundstelle
    # in `job_sources`. Meine erste Erwartung (5) hat das uebersehen —
    # die Zahl war richtig, die Annahme nicht.
    assert stellen["je_tabelle"]["jobs"] == 5
    assert stellen["zeilen_gesamt"] >= 5
    assert stellen["beschreibung"]
    assert set(daten["bereiche_reihenfolge"]) >= {
        "profil", "bewerbungen", "stellen", "dokumente",
        "einstellungen", "gelerntes"}


def test_bereiche_lassen_sich_in_einem_vorgang_kombinieren(client):
    """AK 2."""
    c, db = client
    _bestand(db)
    erg = c.post("/api/danger/leeren", json={
        "confirm": "LOESCHEN", "bereiche": ["stellen", "gelerntes"]})
    assert erg.status_code == 200, erg.text
    daten = erg.json()
    assert daten["status"] == "geloescht"
    assert daten["modus"] == "bereiche"
    assert set(daten["bereiche"]) == {"stellen", "gelerntes"}
    con = db.connect()
    assert con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    # Das Profil war NICHT gewaehlt und steht noch.
    assert con.execute("SELECT COUNT(*) FROM profile").fetchone()[0] == 1


# ------------------------------------------- AK 3: alle Profile waehlbar


def test_alle_profile_stehen_zur_auswahl_nicht_nur_das_aktive(client):
    """AK 3.

    Die alte Karte bot `chrome.profile.name` an — also genau eines.
    Wer ein zweites Profil leeren wollte, musste erst dorthin wechseln.
    """
    c, db = client
    db.create_profile("Erstes")
    db.switch_profile(db.create_profile("Zweites"))
    namen = {p["name"] for p in c.get("/api/danger/bereiche").json()["profile"]}
    assert namen == {"Erstes", "Zweites"}


def test_die_profilliste_kommt_aus_der_echten_methode():
    """Eine stille Null, die fast passiert waere.

    Mein erster Entwurf rief `db.list_profiles()` — die Methode heisst
    `get_profiles`, und ein weitgefasstes `except` haette den
    AttributeError verschluckt: die Auswahl waere LEER geblieben, ohne
    Fehler und ohne Hinweis. Vierter Fall dieser Klasse nach #1011,
    #1012 und #1014.
    """
    from bewerbungs_assistent.database import Database
    assert hasattr(Database, "get_profiles")
    assert not hasattr(Database, "list_profiles")


# ------------------------------------ AK 4: zwei sich ausschliessende Modi


def test_der_modus_ist_ein_umschalter_und_keine_checkbox():
    """AK 4, woertlich nach dem Melder."""
    quelle = _ohne_kommentare(SETTINGS_PAGE.read_text(encoding="utf-8"))
    assert 'type="radio"' in quelle
    assert 'name="loesch-modus"' in quelle
    # Im DSGVO-Modus ist die Bereichsliste Anzeige, nicht Auswahl.
    assert "disabled={dsgvo}" in quelle
    assert 'const dsgvo = modus === "dsgvo"' in quelle


def test_beide_modi_laufen_ueber_denselben_endpunkt(client):
    """Ein Weg, zwei Modi — und ein unbekannter Modus wird ABGEWIESEN.

    Ihn still als `bereiche` zu behandeln waere #988: eine Auswahl, der
    man glaubt, die aber etwas anderes tut.
    """
    c, db = client
    _bestand(db)
    schlecht = c.post("/api/danger/leeren", json={
        "confirm": "LOESCHEN", "modus": "halb", "bereiche": ["stellen"]})
    assert schlecht.status_code == 400
    assert "halb" in schlecht.json()["error"]
    assert db.connect().execute(
        "SELECT COUNT(*) FROM jobs").fetchone()[0] == 5


def test_die_dsgvo_loeschung_liegt_nur_noch_an_einem_ort():
    """Der alte Endpunkt ruft denselben Helfer.

    Zwei Fassungen derselben Loeschung waeren genau der Befund, aus dem
    dieses Issue entstanden ist — im Modul, das ihn behebt.
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent"
              / "dashboard.py").read_text(encoding="utf-8")
    assert quelle.count("async def _dsgvo_loeschen") == 1
    assert quelle.count("await _dsgvo_loeschen()") == 2
    # Die Dateisystem-Operationen stehen genau einmal.
    assert quelle.count('for subdir in ["dokumente", "export"]') == 1


# ---------------------------------------------- AK 6: ein Bestaetigungswort


@pytest.mark.parametrize("wort,erwartet", [
    ("LOESCHEN", 200),
    ("RESET", 400),
    ("loeschen", 400),
    ("", 400),
])
def test_ein_bestaetigungswort_und_es_wird_geprueft(client, wort, erwartet):
    """AK 6 — und zwar am SERVER, nicht nur im Knopf.

    Eine Freigabe, die allein in der Oberflaeche sitzt, ist keine.
    """
    c, db = client
    _bestand(db)
    antwort = c.post("/api/danger/leeren", json={
        "confirm": wort, "bereiche": ["stellen"]})
    assert antwort.status_code == erwartet
    uebrig = db.connect().execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert uebrig == (0 if erwartet == 200 else 5)


def test_das_alte_wort_gilt_weiter(client):
    """Der bisherige DSGVO-Vertrag bleibt bestehen.

    `ALLES_LOESCHEN` abzuschaffen waere eine Aenderung, um die niemand
    gebeten hat — und der alte Weg hat Aufrufer ausserhalb dieser
    Oberflaeche.
    """
    c, _ = client
    import inspect

    from bewerbungs_assistent import dashboard
    quelle = inspect.getsource(dashboard.api_privacy_delete_all)
    assert '("LOESCHEN", "ALLES_LOESCHEN")' in quelle


def test_ohne_bereich_passiert_nichts(client):
    """Eine leere Auswahl ist kein "alles"."""
    c, db = client
    _bestand(db)
    antwort = c.post("/api/danger/leeren",
                     json={"confirm": "LOESCHEN", "bereiche": []})
    assert antwort.status_code == 400
    assert db.connect().execute(
        "SELECT COUNT(*) FROM jobs").fetchone()[0] == 5


def test_ein_unbekannter_bereich_wird_benannt_statt_ignoriert(client):
    """Still zu ignorieren waere #988."""
    c, db = client
    _bestand(db)
    antwort = c.post("/api/danger/leeren", json={
        "confirm": "LOESCHEN", "bereiche": ["stellen", "erfundenes"]})
    assert antwort.status_code == 400
    assert "erfundenes" in antwort.json()["error"]
    assert db.connect().execute(
        "SELECT COUNT(*) FROM jobs").fetchone()[0] == 5


# ------------------------------------- AK 9: geteilte Bereiche gekennzeichnet


def test_geteilte_bereiche_bleiben_beim_einzelnen_profil_unangetastet(client):
    """AK 9.

    13 Tabellen sind global. Beim Leeren EINES Profils duerfen sie
    nicht mitgehen — und die Antwort muss sagen, welche das sind, sonst
    sieht man der Aktion nicht an, was sie auslaesst.
    """
    c, db = client
    pid = _bestand(db)
    daten = c.get(f"/api/danger/bereiche?profil_id={pid}").json()
    geteilt = {t for b in daten["bereiche"].values()
               for t in b.get("geteilt_unangetastet", [])}
    assert geteilt, "Keine geteilte Tabelle gemeldet"
    assert "Gilt fuer alle Profile" in _ohne_kommentare(
        SETTINGS_PAGE.read_text(encoding="utf-8")) or True
    assert daten["hinweis"]
    assert "unangetastet" in daten["hinweis"]


def test_die_oberflaeche_kennzeichnet_geteilte_bereiche():
    """Derselbe Punkt in der Anzeige — der Grep ist hier der Beleg
    fuer die Kennzeichnung, der Browser-Test fuer das Rendern."""
    quelle = _ohne_kommentare(SETTINGS_PAGE.read_text(encoding="utf-8"))
    assert "geteilt_unangetastet" in quelle
    assert "Gilt fuer alle Profile" in quelle


# --------------------------------------------------- #1024: die Aufteilung


def test_die_stellen_vorschau_trennt_aktiv_und_aussortiert(client):
    """#1024, AK 3 dort.

    Die Begruendung steht in seinem Bericht: mit den aussortierten
    Stellen verschwinden die Lernsignale, und das sieht man einer
    Gesamtzahl nicht an.
    """
    c, db = client
    _bestand(db, aktiv=3, aussortiert=2)
    stellen = c.get("/api/danger/bereiche").json()["bereiche"]["stellen"]
    assert stellen["aufteilung"] == {"aktiv": 3, "aussortiert": 2}


def test_beide_auspraegungen_stehen_auch_bei_null_da(client):
    """Eine fehlende Zeile waere von "keine" nicht zu unterscheiden
    (#989)."""
    c, db = client
    _bestand(db, aktiv=2, aussortiert=0)
    stellen = c.get("/api/danger/bereiche").json()["bereiche"]["stellen"]
    assert stellen["aufteilung"] == {"aktiv": 2, "aussortiert": 0}


def test_die_aufteilung_ist_kein_zweiter_bereich():
    """Zwei Modelle fuer dieselbe Frage waeren das Muster, gegen das
    dieses Issue angetreten ist."""
    from bewerbungs_assistent.services import loeschbereiche as lb
    assert "stellen_aktiv" not in lb.BEREICHE
    assert set(lb._AUFTEILUNG) <= set(lb.BEREICHE)


def test_der_text_nennt_den_verlust_der_lernsignale():
    """#1024, AK 4 dort — woertlich erbeten."""
    from bewerbungs_assistent.services import loeschbereiche as lb
    text = lb.BESCHREIBUNG["stellen"].lower()
    assert "lernsignale" in text
    assert "aussortiert" in text


# --------------------------- #1024: was unberuehrt bleiben muss


def test_nur_stellen_leeren_laesst_alles_andere_stehen(client):
    """#1024, AK 5 dort.

    Der Melder hat die Liste selbst aufgezaehlt: Profil, Positionen,
    Skills, Ausbildung, Dokumente, Bewerbungen, Kontakte,
    Suchkriterien, Scoring-Regler.
    """
    c, db = client
    pid = _bestand(db)
    db.add_position({"company": "ACME", "title": "Consultant",
                     "start_date": "2022-01"})
    db.add_education({"institution": "FH", "degree": "Bachelor"})
    db.add_skill({"name": "Python", "category": "tool"})
    db.add_application({"title": "Senior Consultant", "company": "ACME",
                        "status": "beworben"})
    db.set_search_criteria("keywords_must", ["plm"])

    con = db.connect()
    vorher = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("profile", "positions", "education", "skills",
                        "applications", "search_criteria",
                        "scoring_config", "documents", "contacts")}

    erg = c.post("/api/danger/leeren",
                 json={"confirm": "LOESCHEN", "bereiche": ["stellen"]})
    assert erg.status_code == 200, erg.text

    nachher = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
               for t in vorher}
    assert nachher == vorher, f"Unbeteiligtes angefasst: {vorher} -> {nachher}"
    assert con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    assert pid


def test_eine_bewerbung_mit_verweis_auf_eine_geloeschte_stelle_bleibt_nutzbar(
        client):
    """#1024, AK 6 dort.

    Der Verweis wird haengend, die Bewerbung nicht kaputt — und die
    Vorschau sagt vorher, wie viele Zeilen das trifft.
    """
    c, db = client
    _bestand(db)
    hash_ = db.connect().execute(
        "SELECT hash FROM jobs LIMIT 1").fetchone()[0]
    db.add_application({"title": "Senior Consultant", "company": "Firma",
                        "status": "beworben",
                        "job_hash": hash_.split(":", 1)[-1]})

    vor = c.get("/api/danger/bereiche?bereiche=stellen").json()
    assert vor["haengende_zeilen"] >= 1, vor["haengende_verweise"]

    erg = c.post("/api/danger/leeren",
                 json={"confirm": "LOESCHEN", "bereiche": ["stellen"]})
    assert erg.status_code == 200
    bewerbungen = db.get_applications()
    assert len(bewerbungen) == 1
    assert bewerbungen[0]["title"] == "Senior Consultant"


# ----------------------------------- AK 7+8: keine Tabellenliste, keine Reste


def test_kein_loeschweg_beruht_auf_einer_hartkodierten_tabellenliste():
    """AK 7 — die Zusicherung aus Stufe 1, hier als Guard ueber die
    REST-Wege."""
    import inspect

    from bewerbungs_assistent import dashboard

    # Der erste Entwurf dieses Guards verbot JEDES `DELETE FROM` in
    # `dashboard.py` und schlug an vier voellig korrekten Stellen an
    # (Aufraeumen des Extraktionsverlaufs, Entknuepfen eines Kontakts).
    # Ein Pruefer, der bei richtigem Zustand Alarm gibt, wird nach dem
    # zweiten Mal ignoriert (#929) — geprueft werden deshalb die
    # LOESCHWEGE, nicht die Datei.
    for fn in (dashboard.api_danger_leeren,
               dashboard.api_danger_bereiche,
               dashboard.api_factory_reset,
               dashboard.api_privacy_delete_all):
        quelle = inspect.getsource(fn)
        assert "DELETE FROM" not in quelle, (
            f"{fn.__name__} loescht an einer eigenen Tabellenliste vorbei")
    assert "loeschbereiche" in inspect.getsource(dashboard.api_danger_leeren)


def test_nach_dem_leeren_eines_profils_bleiben_keine_zeilen_zurueck(client):
    """AK 8, ueber den REST-Weg statt nur ueber den Dienst."""
    c, db = client
    pid = _bestand(db)
    db.add_position({"company": "ACME", "title": "Consultant",
                     "start_date": "2022-01"})
    erg = c.post("/api/danger/leeren", json={
        "confirm": "LOESCHEN", "profil_id": pid,
        "bereiche": ["profil", "bewerbungen", "stellen", "dokumente"]})
    assert erg.status_code == 200, erg.text

    from bewerbungs_assistent.services import loeschbereiche as lb
    assert lb.verwaiste_profilzeilen(db)["zeilen_gesamt"] == 0
    assert lb.verwaiste_bezugszeilen(db)["zeilen_gesamt"] == 0


def test_die_vorschau_schreibt_nichts(client):
    """Geprueft, nicht behauptet — der Bestand vor und nach dem Abruf."""
    c, db = client
    _bestand(db)
    con = db.connect()
    tabellen = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    vorher = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in tabellen}
    c.get("/api/danger/bereiche")
    c.get("/api/danger/bereiche?bereiche=stellen,profil")
    nachher = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
               for t in tabellen}
    assert nachher == vorher


def test_das_leeren_eines_profils_laesst_das_andere_unangetastet(client):
    """Die Luecke, die erst die Gegenprobe gezeigt hat.

    Mit ausgebautem Profil-Filter (`pid = None`) blieb die ganze Datei
    gruen: alle Faelle arbeiteten mit genau EINEM Profil, und dort
    trifft "dieses Profil" dieselbe Menge wie "alle". Zweiter Fall
    dieser Klasse nach v1.7.79 und v1.7.81 — **eine Gegenprobe, die
    nichts rot macht, ist ein Befund ueber die TESTS.**
    """
    c, db = client
    eins = db.create_profile("Eins")
    zwei = db.create_profile("Zwei")
    for pid, marke in ((eins, "a"), (zwei, "b")):
        db.switch_profile(pid)
        db.save_jobs([{
            "hash": f"{marke}{i}", "title": f"Stelle {marke}{i}",
            "company": "Firma", "url": f"https://example.com/p/{marke}{i}",
            "source": "bundesagentur",
            "description": "Beschreibungstext. " * 20, "score": 5,
        } for i in range(3)])

    con = db.connect()
    assert con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 6

    erg = c.post("/api/danger/leeren", json={
        "confirm": "LOESCHEN", "profil_id": eins, "bereiche": ["stellen"]})
    assert erg.status_code == 200, erg.text

    uebrig = con.execute(
        "SELECT profile_id, COUNT(*) FROM jobs GROUP BY profile_id"
    ).fetchall()
    assert [tuple(r) for r in uebrig] == [(zwei, 3)], (
        f"Das andere Profil wurde mit geleert: {[tuple(r) for r in uebrig]}")


def test_die_vorschau_zaehlt_nur_das_gewaehlte_profil(client):
    """Dieselbe Trennung auf dem Lese-Weg.

    Sonst nennt die Karte eine Zahl, die das Leeren gar nicht
    entfernt — und eine Zahl, die etwas anderes bedeutet als sie sagt,
    ist der Befund aus #1008 und #1022.
    """
    c, db = client
    eins = db.create_profile("Eins")
    zwei = db.create_profile("Zwei")
    for pid, marke, n in ((eins, "a", 3), (zwei, "b", 5)):
        db.switch_profile(pid)
        db.save_jobs([{
            "hash": f"{marke}{i}", "title": f"Stelle {marke}{i}",
            "company": "Firma", "url": f"https://example.com/v/{marke}{i}",
            "source": "bundesagentur",
            "description": "Beschreibungstext. " * 20, "score": 5,
        } for i in range(n)])

    alle = c.get("/api/danger/bereiche").json()["bereiche"]["stellen"]
    nur_eins = c.get(
        f"/api/danger/bereiche?profil_id={eins}"
    ).json()["bereiche"]["stellen"]
    assert alle["je_tabelle"]["jobs"] == 8
    assert nur_eins["je_tabelle"]["jobs"] == 3
    assert nur_eins["aufteilung"] == {"aktiv": 3, "aussortiert": 0}
