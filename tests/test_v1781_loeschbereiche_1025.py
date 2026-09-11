"""Tests fuer #1025 Stufe 1 — was gehoert wozu, wenn geloescht wird.

Gemeldet am 11.09.2026: PBP hat drei Loeschwege mit drei verschiedenen
Vorstellungen davon, was dazugehoert. Der Satz des Melders benennt die
Ursache:

    Vollstaendig ist nur der DSGVO-Weg — und zwar nicht, weil seine
    Liste besser gepflegt waere, sondern weil er keine hat.

## Am echten Bestand gemessen (Kopie, Original nie angefasst)

47 Tabellen. Der Factory Reset raeumte **18** ab und liess **29**
stehen — und nicht nur Einstellungen, sondern Inhalte:

| Zeilen | Tabelle |
|---:|---|
| 81 | `contacts` — Namen und Mailadressen Dritter |
| 68 | `application_jobs` |
| 26 | `document_versions` |
| 15 | `research_notes` |
| 12 | `tasks` |
| 7 | `interview_reflections` |
| 1.304 | `user_activity_events` |

Damit ist das nicht nur eine Beschreibung, die nicht stimmt: **wer
„Factory Reset" waehlt, um den Rechner weiterzugeben, liess
personenbezogene Daten Dritter zurueck.** Deshalb kommt die Datenstufe
vor dem Oberflaechen-Umbau (#1024).

Beim Profil-Loeschen dasselbe Muster: 29 profilgebundene Tabellen, 12
abgeraeumt, **17 blieben verwaist** — im gemessenen Bestand 24 Zeilen,
darunter 10 Bewerbungen mit einer `profile_id`, die es nicht mehr gibt.

## Der eigene Fehler, und warum er hier als Test steht

Der erste Entwurf von `_reihenfolge` war **invertiert** — Eltern vor
Kindern. Eine Kind-Tabelle wird ueber ihre Eltern eingeschraenkt
(`job_hash IN (SELECT hash FROM jobs WHERE ...)`); sind die Eltern weg,
findet die Unterabfrage nichts, und das Kind bleibt stehen. Ohne
Fehler, ohne Meldung.

An der Kopie gemessen blieben so **43 `job_sources` und 68
`application_jobs`** liegen — ausgerechnet die beiden Tabellen aus
`_ZUSATZ_BEZUG`, also die ohne Fremdschluessel. Die uebrigen hat SQLites
CASCADE aufgeraeumt und den Fehler damit verdeckt.

Gefunden hat ihn nicht das Nachdenken, sondern **eine Zahl, die nicht
aufging**: die Vorschau sagte 6.593 Zeilen, geloescht wurden 5.296.
Deshalb ist `test_vorschau_und_wirkung_stimmen_ueberein` der wichtigste
Test dieser Datei — er prueft keine Tabelle, sondern die Gleichheit
zweier Zahlen, und faellt bei JEDER Reihenfolgen-Verwechslung um.

Und der Waisen-Pruefer hat dabei Entwarnung gegeben: er sah nur
`profile_id`, und `job_sources` hat keine. **Ein Pruefer, der nur eine
von zwei Bezugsarten kennt, gibt Entwarnung fuer die andere** —
daher `verwaiste_bezugszeilen`.
"""
import importlib
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import loeschbereiche as lb  # noqa: E402
from bewerbungs_assistent.services import stellen_quellen  # noqa: E402


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database()
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _profil(db, name):
    pid = db.create_profile(name)
    db.switch_profile(pid)
    return pid


def _bestand(db, pid, marke, dateien_ordner=None):
    """Legt in moeglichst vielen Bereichen etwas an."""
    db.switch_profile(pid)
    db.add_position({"company": f"Firma {marke}", "title": "Rolle",
                     "start_date": "2020-01"})
    db.add_skill({"name": f"Skill {marke}", "category": "tech"})
    db.save_jobs([{
        "hash": f"{marke}-job", "title": f"Stelle {marke}",
        "company": f"Firma {marke}",
        "url": f"https://example.com/1025/{marke}",
        "source": "manuell", "_manual_entry": True,
        "description": "Beschreibungstext. " * 20, "score": 5,
    }])
    db.add_application({"company": f"Firma {marke}", "title": "Rolle",
                        "status": "beworben"})
    db.add_contact({"full_name": f"Kontakt {marke}",
                    "email": f"{marke}@example.com",
                    "company": f"Firma {marke}"})
    if dateien_ordner is not None:
        datei = Path(dateien_ordner) / f"{marke}.txt"
        datei.write_text("Inhalt", encoding="utf-8")
        db.add_document({"filename": f"{marke}.txt", "filepath": str(datei),
                         "doc_type": "sonstiges"})
    return marke


# ----------------------------------------------- AK: der Guard ueber das Schema


def test_jede_tabelle_gehoert_zu_genau_einem_bereich(db):
    """Der Kern des Issues — und der Grund, warum es abgeleitet wird.

    Eine Aufzaehlung schuetzt einmal, eine Strukturpruefung immer
    (v1.7.74). Faellt die naechste neue Tabelle aus den Bereichen
    heraus, bricht dieser Test — nicht der Nutzer faellt darauf herein.
    """
    befund = lb.unzugeordnet(db)
    assert befund["fehlt_im_bereich"] == [], (
        "Diese Tabellen stehen in der Datenbank, aber in keinem Bereich — "
        "ein Loeschvorgang wuerde sie stehen lassen: "
        f"{befund['fehlt_im_bereich']}")
    assert befund["kennt_die_datenbank_nicht"] == [], (
        "Diese Bereichs-Eintraege gibt es in der Datenbank nicht (mehr): "
        f"{befund['kennt_die_datenbank_nicht']}")
    assert befund["mehrfach_zugeordnet"] == [], (
        f"Mehrfach zugeordnet: {befund['mehrfach_zugeordnet']}")


def test_jeder_bereich_traegt_eine_beschreibung():
    """Ohne Klartext ist eine Gefahrenzone eine Ratesituation.

    Der Melder hat ausdruecklich darum gebeten: dass mit den
    aussortierten Stellen auch die Lernsignale verschwinden, sieht man
    der Aktion sonst nicht an.
    """
    for bereich in lb.BEREICHE:
        assert lb.BESCHREIBUNG.get(bereich), f"{bereich} ohne Beschreibung"


def test_bezug_wird_aus_dem_schema_gelesen(db):
    """Drei Bezugsarten, keine davon aufgezaehlt."""
    assert lb.bezug(db, "jobs") == lb.PROFIL          # eigene profile_id
    assert lb.bezug(db, "projects") == lb.MITTELBAR   # ueber positions
    assert lb.bezug(db, "job_sources") == lb.MITTELBAR  # ueber _ZUSATZ_BEZUG
    assert lb.bezug(db, "settings") == lb.GETEILT
    assert lb.bezug(db, "profile") == lb.PROFIL


# --------------------------------- Der Test, der den eigenen Fehler gefunden hat


def test_vorschau_und_wirkung_stimmen_ueberein(db):
    """Die Zahl, die nicht aufging.

    Sie prueft keine einzelne Tabelle, sondern eine Eigenschaft: was die
    Vorschau ankuendigt, muss das Loeschen auch erfassen. Jede
    Reihenfolgen-Verwechslung faellt hier um, auch eine kuenftige an
    einer Tabelle, die es heute noch nicht gibt.
    """
    pid = _profil(db, "Messfall")
    _bestand(db, pid, "m1")

    vor = lb.vorschau(db, profil_id=pid)
    erwartet = {}
    for teil in vor["bereiche"].values():
        erwartet.update(teil["je_tabelle"])

    erg = lb.leeren(db, profil_id=pid, dry_run=False)

    assert erg["zeilen_gesamt"] == vor["zeilen_gesamt"], (
        f"Vorschau {vor['zeilen_gesamt']}, geloescht "
        f"{erg['zeilen_gesamt']} — eine Tabelle wurde nicht erfasst")
    assert erg["je_tabelle"] == erwartet


def test_tabellen_ohne_fremdschluessel_werden_mit_geleert(db):
    """Die konkrete Regression: `job_sources` und `application_jobs`.

    Beide haengen ueber eine Spalte, die im Schema NICHT als
    Fremdschluessel steht — genau deshalb gibt es `_ZUSATZ_BEZUG`, und
    genau deshalb raeumt SQLites CASCADE sie nicht mit ab. Mit der
    invertierten Reihenfolge blieben sie liegen, waehrend alle anderen
    Tabellen sauber waren.
    """
    pid = _profil(db, "Fundstellen")
    _bestand(db, pid, "f1")
    con = db.connect()
    voll = db.resolve_job_hash("f1-job")
    # Ueber das Nadeloehr aus #951 — die Tabelle entsteht erst dabei.
    assert stellen_quellen.vermerken(
        db, voll, "zweitquelle", url="https://example.com/1025/zweit")
    assert con.execute("SELECT COUNT(*) FROM job_sources").fetchone()[0] > 0

    lb.leeren(db, profil_id=pid, dry_run=False)

    assert con.execute("SELECT COUNT(*) FROM job_sources").fetchone()[0] == 0
    assert con.execute(
        "SELECT COUNT(*) FROM application_jobs").fetchone()[0] == 0


def test_kinder_stehen_vor_ihren_eltern(db):
    """Die Richtung selbst, als eigener Test.

    `test_vorschau_und_wirkung_stimmen_ueberein` faellt bei einer
    Verwechslung ebenfalls um — aber erst ueber ein Ergebnis. Hier
    steht die Regel.
    """
    stellen_quellen.tabelle_anlegen(db.connect())
    reihe = lb._reihenfolge(db, [t for b in lb.BEREICHE
                                 for t in lb.BEREICHE[b]
                                 if t in set(lb.tabellen(db))])
    for kind, eltern in (("job_sources", "jobs"),
                         ("application_jobs", "applications"),
                         ("projects", "positions"),
                         ("skill_periods", "skills"),
                         ("application_events", "applications")):
        assert reihe.index(kind) < reihe.index(eltern), (
            f"{kind} muss vor {eltern} geloescht werden — sonst findet "
            f"seine Unterabfrage die Eltern nicht mehr")


def test_profiltabelle_nur_wenn_ihr_bereich_gewaehlt_ist(db):
    """Sie steht zuletzt — aber nur, wenn sie ueberhaupt dran ist.

    Ein Zwischenstand haengte sie bedingungslos an: wer nur die Stellen
    leeren wollte, haette sein Profil verloren.
    """
    reihe = lb._reihenfolge(db, ["jobs", "job_sources"])
    assert "profile" not in reihe
    reihe2 = lb._reihenfolge(db, ["profile", "positions", "jobs"])
    assert reihe2[-1] == "profile"


# --------------------------------------- AK: kein Bereich bleibt uebrig


def test_factory_reset_laesst_nur_den_schema_stand_stehen(db, tmp_path):
    """Befund 1 des Melders, mit der Verschaerfung aus der Messung."""
    ordner = tmp_path / "dateien"
    ordner.mkdir()
    for name in ("Erstes", "Zweites"):
        pid = _profil(db, name)
        _bestand(db, pid, name.lower(), ordner)

    con = db.connect()
    assert con.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] > 0

    db.reset_all_data()

    rest = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in lb.tabellen(db)}
    uebrig = {t: n for t, n in rest.items() if n}
    assert uebrig == {"settings": 1}, (
        f"Nach dem Factory Reset stehen noch Daten: {uebrig}")
    assert con.execute(
        "SELECT value FROM settings WHERE key='schema_version'").fetchone()


def test_factory_reset_bewahrt_den_schema_stand(db):
    """`schema_version` ist keine Nutzerdatei.

    Der alte Weg hatte die Ausnahme als SQL-Text (`WHERE key !=
    'schema_version'`) — sie geht beim Umbau leicht verloren, und die
    naechste Migration haelt die Datenbank dann fuer eine aeltere
    Fassung.
    """
    con = db.connect()
    vorher = con.execute(
        "SELECT value FROM settings WHERE key='schema_version'").fetchone()[0]
    db.reset_all_data()
    nachher = con.execute(
        "SELECT value FROM settings WHERE key='schema_version'").fetchone()
    assert nachher is not None, "schema_version wurde mitgeloescht"
    assert nachher[0] == vorher


def test_factory_reset_entfernt_die_dateien_auf_der_platte(db, tmp_path):
    """Eine Zeile zu loeschen entfernt die Datei nicht — und die traegt
    den Inhalt."""
    ordner = tmp_path / "dateien"
    ordner.mkdir()
    pid = _profil(db, "Mit Datei")
    _bestand(db, pid, "d1", ordner)
    datei = ordner / "d1.txt"
    assert datei.exists()

    erg = db.reset_all_data()

    assert not datei.exists()
    assert erg["dateien_geloescht"] >= 1


# --------------------------------------- AK: Profil loeschen laesst nichts zurueck


def test_profil_loeschen_hinterlaesst_keine_waisen(db):
    """Befund 2: 17 Tabellen blieben mit einer toten `profile_id`."""
    behalten = _profil(db, "Bleibt")
    _bestand(db, behalten, "b1")
    weg = _profil(db, "Geht")
    _bestand(db, weg, "w1")

    vorher = lb.verwaiste_zeilen(db)["zeilen_gesamt"]
    assert db.delete_profile(weg) is True
    nachher = lb.verwaiste_zeilen(db)

    assert nachher["zeilen_gesamt"] <= vorher, (
        "Das Loeschen hat Waisen erzeugt: "
        f"{nachher['profilzeilen']['tabellen']} / "
        f"{nachher['bezugszeilen']['bezuege']}")
    assert lb.vorschau(db, profil_id=weg)["zeilen_gesamt"] == 0


def test_profil_loeschen_laesst_das_andere_profil_unangetastet(db):
    """Die Gegenrichtung — beide Richtungen messen (#966)."""
    behalten = _profil(db, "Bleibt")
    _bestand(db, behalten, "b2")
    weg = _profil(db, "Geht")
    _bestand(db, weg, "w2")

    vorher = lb.vorschau(db, profil_id=behalten)["zeilen_gesamt"]
    db.delete_profile(weg)
    nachher = lb.vorschau(db, profil_id=behalten)["zeilen_gesamt"]

    assert nachher == vorher
    con = db.connect()
    assert con.execute("SELECT COUNT(*) FROM profile "
                       "WHERE id=?", (behalten,)).fetchone()[0] == 1


def test_profil_loeschen_meldet_unbekannte_kennung(db):
    """Eine Erfolgsmeldung ueber eine Nicht-Aenderung beendet die
    Fehlersuche (#994/#997)."""
    assert db.delete_profile("gibt-es-nicht") is False


def test_geteilte_bereiche_bleiben_beim_einzelnen_profil_stehen(db):
    """`settings` gilt fuer alle Profile.

    Sie beim Loeschen EINES Profils mitzunehmen waere ein Eingriff in
    die Daten der anderen — deshalb werden sie benannt und nicht
    angefasst.
    """
    pid = _profil(db, "Einzeln")
    _bestand(db, pid, "g1")
    con = db.connect()
    vorher = con.execute("SELECT COUNT(*) FROM settings").fetchone()[0]

    v = lb.vorschau(db, profil_id=pid)
    assert "settings" in v["bereiche"]["einstellungen"]["geteilt_unangetastet"]

    lb.leeren(db, profil_id=pid, dry_run=False)
    assert con.execute(
        "SELECT COUNT(*) FROM settings").fetchone()[0] == vorher


# ------------------------------------------------- AK: Vorschau aendert nichts


def test_vorschau_ist_die_vorgabe_und_schreibt_nicht(db):
    """Ein Lauf, der ungefragt 6.900 Zeilen loescht, waere keine
    Vorschau, sondern eine Ueberraschung."""
    pid = _profil(db, "Vorschau")
    _bestand(db, pid, "v1")
    con = db.connect()
    vorher = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in lb.tabellen(db)}

    erg = lb.leeren(db, profil_id=pid)  # ohne dry_run-Argument

    assert erg["status"] == "vorschau"
    nachher = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
               for t in lb.tabellen(db)}
    assert nachher == vorher


def test_vorschau_nennt_die_zahlen_je_bereich(db):
    """AK: „Vorschau mit Zahlen" — je Bereich, nicht als Gesamtsumme."""
    pid = _profil(db, "Zahlen")
    _bestand(db, pid, "z1")
    v = lb.vorschau(db, profil_id=pid)
    assert v["bereiche"]["stellen"]["zeilen_gesamt"] >= 1
    assert "jobs" in v["bereiche"]["stellen"]["je_tabelle"]
    assert v["bereiche"]["profil"]["zeilen_gesamt"] >= 1
    assert v["zeilen_gesamt"] == sum(
        t["zeilen_gesamt"] for t in v["bereiche"].values())


def test_einzelne_bereiche_lassen_die_anderen_stehen(db):
    """Bereiche sind einzeln waehlbar — die Grundlage fuer #1024."""
    pid = _profil(db, "Auswahl")
    _bestand(db, pid, "a1")
    con = db.connect()
    positionen = con.execute("SELECT COUNT(*) FROM positions").fetchone()[0]

    lb.leeren(db, ["stellen"], profil_id=pid, dry_run=False)

    assert con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    assert con.execute(
        "SELECT COUNT(*) FROM positions").fetchone()[0] == positionen


# ------------------------------------ Bereichsuebergreifende Verweise


def test_haengende_verweise_werden_genannt_nicht_still_geloescht(db):
    """Fuenf Fremdschluessel laufen ueber eine Bereichsgrenze.

    Wer nur die Stellen leert, laesst in den Bewerbungen einen
    `job_hash` stehen, der auf nichts mehr zeigt. Die Zeile gehoert zu
    einem Bereich, den der Mensch NICHT gewaehlt hat — sie ungefragt
    mitzuloeschen waere schlimmer als die Warnung.
    """
    pid = _profil(db, "Verweise")
    _bestand(db, pid, "h1")
    con = db.connect()
    voll = db.resolve_job_hash("h1-job")
    app = con.execute("SELECT id FROM applications LIMIT 1").fetchone()[0]
    con.execute("UPDATE applications SET job_hash=? WHERE id=?", (voll, app))
    con.commit()

    v = lb.vorschau(db, ["stellen"], profil_id=pid)
    treffer = [e for e in v["haengende_verweise"]
               if e["tabelle"] == "applications"]
    assert treffer, "Der Verweis applications.job_hash wurde nicht genannt"
    assert treffer[0]["zielbereich"] == "stellen"

    lb.leeren(db, ["stellen"], profil_id=pid, dry_run=False)
    assert con.execute(
        "SELECT COUNT(*) FROM applications").fetchone()[0] == 1


def test_waisen_pruefer_kennt_beide_bezugsarten(db):
    """Der Pruefer, der beim eigenen Fehler Entwarnung gegeben hat.

    `verwaiste_profilzeilen` sieht nur `profile_id`; `job_sources` hat
    keine. Erst `verwaiste_bezugszeilen` findet eine Fundstelle ohne
    Stelle.
    """
    pid = _profil(db, "Waisen")
    _bestand(db, pid, "x1")
    con = db.connect()
    # Eine Fundstelle zu einer Stelle, die es nicht gibt — genau der
    # Zustand, den die invertierte Reihenfolge hinterlassen hat.
    stellen_quellen.vermerken(db, "gibt-es-nicht", "quelle",
                              url="https://example.com/1025/tot")

    profilseite = lb.verwaiste_profilzeilen(db)
    assert "job_sources" not in profilseite["tabellen"]

    bezugsseite = lb.verwaiste_bezugszeilen(db)
    assert any(e["tabelle"] == "job_sources"
               for e in bezugsseite["bezuege"].values())
    assert lb.verwaiste_zeilen(db)["zeilen_gesamt"] >= 1


def test_selbstbezug_ist_kein_elternteil(db):
    """Der Fall, den die Gegenprobe zunaechst NICHT rot gemacht hat.

    `_eltern` hat zwei Schutzmechanismen, und heute deckt der zweite
    den ersten zu: `application_events` verweist erst auf sich selbst
    (`parent_event_id`, die Antwort-Kette) und dann auf `applications`
    — und weil `applications` eine `profile_id` traegt, waehlt die
    Bevorzugung den richtigen Weg auch ohne den Selbstbezug-Filter.

    Baut man den Filter aus, bleibt deshalb alles gruen. **Das ist ein
    Befund ueber die Tests, nicht ueber den Code** (v1.7.79 an neuer
    Stelle). Der Filter greift erst, wenn KEIN Elternteil eine
    `profile_id` hat — dann faellt `_eltern` auf den ersten Kandidaten
    zurueck, und das waere die Tabelle selbst. Sie gaelte als
    `geteilt`, wuerde beim Leeren uebersprungen und bliebe als Waise
    stehen.

    Dieser Test stellt genau diese Lage her, statt sie abzuwarten.
    """
    con = db.connect()
    # Der Zwischenschritt traegt selbst KEINE profile_id — damit greift
    # die Bevorzugung nicht, und `_eltern` faellt auf den ersten
    # Kandidaten zurueck. Genau dort entscheidet der Filter.
    con.execute("CREATE TABLE IF NOT EXISTS probe_mittel ("
                "id TEXT PRIMARY KEY, "
                "app_id TEXT REFERENCES applications(id))")
    # Der Selbstbezug wird ZULETZT deklariert und steht damit in
    # `PRAGMA foreign_key_list` an ERSTER Stelle — dieselbe Lage wie
    # bei `application_events` im frischen Schema (nachgemessen).
    con.execute("""
        CREATE TABLE IF NOT EXISTS probe_kette (
            id TEXT PRIMARY KEY,
            eltern_id TEXT REFERENCES probe_mittel(id),
            vorgaenger_id TEXT REFERENCES probe_kette(id)
        )
    """)
    con.commit()
    erste = list(con.execute("PRAGMA foreign_key_list(probe_kette)"))[0]
    assert erste[2] == "probe_kette", (
        "Voraussetzung des Tests: der Selbstbezug muss zuerst kommen")

    e = lb._eltern(db, "probe_kette")
    assert e is not None
    assert e[0] != "probe_kette", (
        "Ein Selbstbezug wurde als Elternteil genommen — die Tabelle "
        "gaelte damit als geteilt und bliebe beim Loeschen stehen")
    assert e[0] == "probe_mittel"
    assert lb.bezug(db, "probe_kette") == lb.MITTELBAR


def test_application_events_haengt_an_der_bewerbung(db):
    """Der konkrete Fall aus dem Schema — und er faellt nur auf einer
    FRISCHEN Datenbank auf.

    In der gewachsenen Datenbank fehlt der Selbstbezug; dort war der
    Bezug von Anfang an richtig. Die Messung auf der Kopie konnte den
    Fehler also nicht finden: **eine Messung am eigenen Bestand prueft
    eine Installation, nicht das Programm.**
    """
    assert lb.bezug(db, "application_events") == lb.MITTELBAR
    e = lb._eltern(db, "application_events")
    assert e[0] == "applications"


# ------------------------------------------- Der REST-Weg sagt, was er tat


def test_rest_reset_nennt_die_zahlen_statt_einer_behauptung(tmp_path):
    """„Alle Daten gelöscht" war die Behauptung, die nicht stimmte.

    Der Bestandstest zu diesem Endpunkt prueft seit jeher nur, dass
    HTTP 200 zurueckkommt und danach kein Profil mehr da ist — beides
    war auch VOR der Korrektur wahr, waehrend 29 Tabellen stehen
    blieben. **Ein Test, der den gemeldeten Defekt nicht sieht, ist
    kein Schutz**, deshalb prueft dieser die Auskunft selbst.
    """
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database(db_path=tmp_path / "rest.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path)

    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient

    vorher_db = dash._db
    dash._db = datenbank
    try:
        client = TestClient(dash.app)
        pid = _profil(datenbank, "REST")
        _bestand(datenbank, pid, "r1")

        antwort = client.post("/api/reset", json={"confirm": "RESET"})
        assert antwort.status_code == 200
        daten = antwort.json()

        assert daten["zeilen_geloescht"] > 0
        assert daten["tabellen_geleert"] > 0
        assert str(daten["zeilen_geloescht"]) in daten["message"], (
            "Die Meldung nennt die Zahl nicht, die sie gerade ermittelt hat")

        con = datenbank.connect()
        uebrig = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in lb.tabellen(datenbank)}
        assert {t: n for t, n in uebrig.items() if n} == {"settings": 1}
    finally:
        dash._db = vorher_db
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)
