"""Auto-Update (#1093): Aufraeumen, Belegung, Sperre, Einstellungen, Rueckfrage, Verlauf, Vertrag mit dem Startbaustein.

Akzeptanzkriterium 12: nichts bleibt unbemerkt liegen — aber **nie** wird etwas geloescht, das ein lebender
Prozess benutzt. Beides hier, mit Prozessen, die wirklich leben (dieser Test) und solchen, die es nicht tun.
"""
import json
import os
import stat
import sys
import time

import pytest
from _au_hilfen import FakeDb, fassung_anlegen, programmordner

import bewerbungs_assistent_boot as boot
from bewerbungs_assistent.services.auto_update import aufraeumen, fassung, layout, zustand
from bewerbungs_assistent.services.auto_update.fehler import UpdateFehler

TOTE_PID = 4194301                    # unter Windows beginnen Kennungen bei 4 und sind durch 4 teilbar; diese gibt es nicht
JETZT = "2999-01-01T00:00:00+00:00"   # eine Marke, die NACH jedem Prozessstart liegt


def marke(app, version, pid, start=JETZT):
    ordner = app / "versions" / version / ".in_benutzung"
    ordner.mkdir(exist_ok=True)
    (ordner / f"{pid}.json").write_text(json.dumps({"pid": pid, "version": version, "start": start}), encoding="utf-8")
    return ordner / f"{pid}.json"


# ══ Lebt der Prozess? ═════════════════════════════════════════════════════════════════

def test_der_eigene_prozess_lebt():
    assert aufraeumen.prozess_lebt(os.getpid(), JETZT) is True


@pytest.mark.parametrize("pid", [None, "", "abc", 0, -5, TOTE_PID])
def test_tote_und_unsinnige_kennungen_leben_nicht(pid):
    assert aufraeumen.prozess_lebt(pid) is False


@pytest.mark.skipif(sys.platform != "win32", reason="Erstellzeit-Vergleich der Marke gibt es nur unter Windows")
def test_eine_wiederverwendete_kennung_gehoert_zu_einem_anderen_prozess():
    """Die Marke ist von 2000, dieser Prozess wurde spaeter gestartet: dieselbe Kennung, ein anderes Programm."""
    assert aufraeumen.prozess_lebt(os.getpid(), "2000-01-01T00:00:00+00:00") is False


def test_belegungen_zaehlt_lebende_und_raeumt_tote_marken_weg(tmp_path):
    app = programmordner(tmp_path, fassungen=("1.8.0",))
    lebend = marke(app, "1.8.0", os.getpid())
    tot = marke(app, "1.8.0", TOTE_PID)
    muell = app / "versions" / "1.8.0" / ".in_benutzung" / "kaputt.json"
    muell.write_text("{nope", encoding="utf-8")
    assert [b["pid"] for b in aufraeumen.belegungen(app, "1.8.0")] == [os.getpid()]
    assert lebend.exists() and not tot.exists() and not muell.exists()


def test_belegungen_ohne_aufraeumen_laesst_dateien_stehen(tmp_path):
    app = programmordner(tmp_path, fassungen=("1.8.0",))
    tot = marke(app, "1.8.0", TOTE_PID)
    assert aufraeumen.belegungen(app, "1.8.0", aufraeumen=False) == []
    assert tot.exists()


def test_belegungen_einer_fehlenden_fassung_sind_leer(tmp_path):
    assert aufraeumen.belegungen(programmordner(tmp_path), "9.9.9") == []


# ══ Sperre ════════════════════════════════════════════════════════════════════════════

def test_die_sperre_gilt_waehrend_des_blocks_und_faellt_danach_weg(tmp_path):
    app = programmordner(tmp_path)
    with aufraeumen.sperre(app):
        assert (app / "update.sperre").is_file()
        with pytest.raises(UpdateFehler) as e:
            with aufraeumen.sperre(app):
                pytest.fail("zweite Sperre darf nicht gelten")
        assert e.value.code == "gesperrt"
        assert (app / "update.sperre").is_file(), "die gescheiterte zweite Sperre darf die erste nicht aufloesen"
    assert not (app / "update.sperre").exists()


def test_die_sperre_faellt_auch_nach_einer_ausnahme_weg(tmp_path):
    app = programmordner(tmp_path)
    with pytest.raises(RuntimeError):
        with aufraeumen.sperre(app):
            raise RuntimeError("mitten im Update")
    assert not (app / "update.sperre").exists()


def test_eine_verwaiste_sperre_wird_uebernommen(tmp_path):
    app = programmordner(tmp_path)
    (app / "update.sperre").write_text(json.dumps({"pid": TOTE_PID, "start": "2020-01-01T00:00:00+00:00"}), encoding="utf-8")
    with aufraeumen.sperre(app):
        pass


@pytest.mark.parametrize("inhalt", ["{kaputt", "[]", "", json.dumps({"pid": os.getpid(), "start": "2000-01-01T00:00:00+00:00"})])
def test_eine_unlesbare_oder_uralte_sperre_gilt_als_verwaist(tmp_path, inhalt):
    app = programmordner(tmp_path)
    (app / "update.sperre").write_text(inhalt, encoding="utf-8")
    with aufraeumen.sperre(app):
        pass


# ══ Loeschen, Groesse, Arbeitsordner ═══════════════════════════════════════════════════

def test_ordner_loeschen_entfernt_auch_schreibgeschuetztes(tmp_path):
    ziel = tmp_path / "x"
    (ziel / "a").mkdir(parents=True)
    datei = ziel / "a" / "f.txt"
    datei.write_text("x")
    os.chmod(datei, stat.S_IREAD)
    assert aufraeumen.ordner_loeschen(ziel) is True and not ziel.exists()


def test_ordner_loeschen_eines_fehlenden_ordners_ist_in_ordnung(tmp_path):
    assert aufraeumen.ordner_loeschen(tmp_path / "gibtsnicht") is True


def test_groesse_zaehlt_dateien_rekursiv_und_ein_fehlender_pfad_ist_null(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "x.bin").write_bytes(b"1" * 100)
    (tmp_path / "a" / "b" / "y.bin").write_bytes(b"1" * 50)
    assert aufraeumen.groesse(tmp_path / "a") == 150
    assert aufraeumen.groesse(tmp_path / "a" / "x.bin") == 100
    assert aufraeumen.groesse(tmp_path / "weg") == 0


def test_arbeit_leeren_raeumt_alles_weg_solange_kein_anderes_update_laeuft(tmp_path):
    app = programmordner(tmp_path)
    (app / "update" / "entpackt").mkdir(parents=True)
    (app / "update" / "pbp-update-1.8.1.zip.part").write_bytes(b"x" * 1000)
    assert aufraeumen.arbeit_leeren(app) >= 1000
    assert not (app / "update").exists()
    assert aufraeumen.arbeit_leeren(app) == 0           # nichts mehr da: kein Fehler


def test_arbeit_leeren_laesst_die_dateien_eines_laufenden_anderen_updates_in_ruhe(tmp_path):
    app = programmordner(tmp_path)
    (app / "update").mkdir()
    (app / "update" / "x.part").write_bytes(b"x")
    (app / "update.sperre").write_text(json.dumps({"pid": os.getpid(), "start": JETZT}), encoding="utf-8")
    assert aufraeumen.arbeit_leeren(app) == 0
    assert (app / "update" / "x.part").exists()
    assert aufraeumen.arbeit_leeren(app, eigene_sperre=True) > 0           # der Halter selbst darf
    assert not (app / "update").exists()


def test_reste_entfernen_nimmt_angefangene_installationen_mit_aber_keine_fertigen_fassungen(tmp_path):
    app = programmordner(tmp_path, fassungen=("1.8.0",))
    (app / "versions" / "1.8.1.neu").mkdir()
    (app / "versions" / "1.8.2.tmp-77").mkdir()
    alt = fassung_anlegen(app, "1.8.3", fertig=False)
    alt_zeit = time.time() - 3 * 3600
    os.utime(alt, (alt_zeit, alt_zeit))
    jung = fassung_anlegen(app, "1.8.4", fertig=False)          # wird vielleicht gerade installiert
    (app / "versions" / "datei.txt").write_text("keine Fassung")
    entfernt = sorted(aufraeumen.reste_entfernen(app))
    assert entfernt == ["1.8.1.neu", "1.8.2.tmp-77", "1.8.3"]
    assert (app / "versions" / "1.8.0").is_dir() and jung.is_dir() and (app / "versions" / "datei.txt").exists()


# ══ Alte Fassungen aufraeumen ═════════════════════════════════════════════════════════

def alle(app):
    return sorted(p.name for p in (app / "versions").iterdir())


@pytest.fixture(autouse=True)
def _keine_laufende_fassung(monkeypatch):
    monkeypatch.delenv("PBP_FASSUNG", raising=False)
    monkeypatch.delenv("PBP_APP_DIR", raising=False)


def test_behalten_werden_die_aktuelle_und_n_vorgaenger(tmp_path):
    app = programmordner(tmp_path, fassungen=("1.8.0", "1.8.1", "1.8.2", "1.8.3", "1.8.4"), aktuell="1.8.4")
    b = aufraeumen.fassungen_aufraeumen(app, 2)
    assert alle(app) == ["1.8.2", "1.8.3", "1.8.4"]
    assert set(b["geloescht"]) == {"1.8.0", "1.8.1"} and b["frei_bytes"] > 0


def test_null_vorgaenger_behaelt_nur_aktuelle_und_geschuetzte(tmp_path):
    app = programmordner(tmp_path, fassungen=("1.8.0", "1.8.1", "1.8.2"), aktuell="1.8.2",
                         status={"vorherige": "1.8.1"})
    aufraeumen.fassungen_aufraeumen(app, 0)
    assert alle(app) == ["1.8.1", "1.8.2"], "die vorige Fassung ist der Rueckweg und bleibt"


def test_die_laufende_fassung_wird_nie_geloescht(tmp_path, monkeypatch):
    app = programmordner(tmp_path, fassungen=("1.8.0", "1.8.1", "1.8.2"), aktuell="1.8.2")
    monkeypatch.setenv("PBP_FASSUNG", "1.8.0")
    aufraeumen.fassungen_aufraeumen(app, 0)
    assert "1.8.0" in alle(app)


def test_die_zuletzt_gestartete_fassung_wird_nie_geloescht(tmp_path):
    app = programmordner(tmp_path, fassungen=("1.8.0", "1.8.1", "1.8.2"), aktuell="1.8.2",
                         status={"start": {"version": "1.8.0", "versuche": 1, "bestaetigt": False}})
    aufraeumen.fassungen_aufraeumen(app, 0)
    assert "1.8.0" in alle(app)


def test_eine_fassung_die_ein_lebender_prozess_benutzt_wird_nie_geloescht_und_gemeldet(tmp_path):
    app = programmordner(tmp_path, fassungen=("1.8.0", "1.8.1", "1.8.2"), aktuell="1.8.2")
    marke(app, "1.8.0", os.getpid())
    b = aufraeumen.fassungen_aufraeumen(app, 0)
    assert "1.8.0" in alle(app) and "1.8.1" not in alle(app)
    assert b["uebersprungen"] == {"1.8.0": "wird gerade benutzt"}


def test_die_tote_marke_eines_beendeten_prozesses_haelt_nichts_fest(tmp_path):
    app = programmordner(tmp_path, fassungen=("1.8.0", "1.8.1"), aktuell="1.8.1")
    marke(app, "1.8.0", TOTE_PID)
    aufraeumen.fassungen_aufraeumen(app, 0)
    assert alle(app) == ["1.8.1"]


def test_eine_neuere_noch_nicht_umgeschaltete_fassung_wartet_aber_eine_gescheiterte_geht(tmp_path):
    app = programmordner(tmp_path, fassungen=("1.8.0", "1.8.1", "1.8.2"), aktuell="1.8.0")
    aufraeumen.fassungen_aufraeumen(app, 0)
    assert alle(app) == ["1.8.0", "1.8.1", "1.8.2"]
    (app / "update_status.json").write_text(json.dumps({"gescheitert": ["1.8.2"]}), encoding="utf-8")
    aufraeumen.fassungen_aufraeumen(app, 0)
    assert alle(app) == ["1.8.0", "1.8.1"]


def test_was_sich_nicht_loeschen_laesst_wird_gemeldet_und_bleibt_zaehlt_aber_nicht_als_geloescht(tmp_path, monkeypatch):
    app = programmordner(tmp_path, fassungen=("1.8.0", "1.8.1"), aktuell="1.8.1")
    monkeypatch.setattr(aufraeumen, "ordner_loeschen", lambda p: False)
    b = aufraeumen.fassungen_aufraeumen(app, 0)
    assert b["geloescht"] == [] and "1.8.0" in b["uebersprungen"] and "gesperrt" in b["uebersprungen"]["1.8.0"]


def test_ist_unklar_welche_fassung_gilt_wird_nichts_geloescht(tmp_path):
    """Ohne gueltige aktuell.txt gaebe es keinen Bezugspunkt fuer 'alt': dann bleibt alles, wie es ist."""
    app = programmordner(tmp_path, fassungen=("1.8.0", "1.8.1"), aktuell="")
    (app / "aktuell.txt").unlink(missing_ok=True)
    b = aufraeumen.fassungen_aufraeumen(app, 0)
    assert alle(app) == ["1.8.0", "1.8.1"] and b["geloescht"] == [] and "*" in b["uebersprungen"]
    (app / "aktuell.txt").write_text("9.9.9\n", encoding="utf-8")                    # zeigt auf nichts Installiertes
    aufraeumen.fassungen_aufraeumen(app, 0)
    assert alle(app) == ["1.8.0", "1.8.1"]


# ══ Einstellungen ═════════════════════════════════════════════════════════════════════

def test_die_vorgaben_sind_aus_drei_vorgaenger_und_fragen():
    db = FakeDb()
    assert zustand.stufe(db) == "aus" and zustand.vorgaenger_behalten(db) == 3 and zustand.installer_aufraeumen(db) == "fragen"
    assert zustand.gefragt(db) == {"antwort": None, "bei_version": None}


@pytest.mark.parametrize("kaputt", ["", None, "ja", "AUTO", "auto", 5, ["aus"], {"a": 1}])
def test_eine_unbekannte_oder_kaputte_stufe_gilt_als_aus(kaputt):
    assert zustand.stufe(FakeDb({zustand.K_STUFE: kaputt})) == "aus"


@pytest.mark.parametrize("stufe", zustand.STUFEN)
def test_jede_der_vier_stufen_laesst_sich_setzen_und_lesen(stufe):
    db = FakeDb()
    assert zustand.stufe_setzen(db, stufe) == stufe and zustand.stufe(db) == stufe


def test_eine_unbekannte_stufe_wird_beim_setzen_abgelehnt():
    db = FakeDb()
    with pytest.raises(ValueError):
        zustand.stufe_setzen(db, "immer")
    assert zustand.stufe(db) == "aus"


def test_die_zahl_der_vorgaenger_ist_begrenzt():
    db = FakeDb()
    assert zustand.vorgaenger_setzen(db, "5") == 5 and zustand.vorgaenger_behalten(db) == 5
    for schlecht in (0, 11, -1, "x", None, True, "2,5"):
        with pytest.raises(ValueError):
            zustand.vorgaenger_setzen(db, schlecht)
    assert zustand.vorgaenger_behalten(db) == 5
    db.werte[zustand.K_VORGAENGER] = 99                       # von Hand verbogen: die Grenze gilt trotzdem
    assert zustand.vorgaenger_behalten(db) == zustand.VORGAENGER_MAX
    db.werte[zustand.K_VORGAENGER] = 0
    assert zustand.vorgaenger_behalten(db) == zustand.VORGAENGER_MIN


def test_installer_aufraeumen_kennt_fragen_immer_nie():
    db = FakeDb()
    for wert in ("immer", "nie", "fragen"):
        assert zustand.installer_aufraeumen_setzen(db, wert) == wert and zustand.installer_aufraeumen(db) == wert
    with pytest.raises(ValueError):
        zustand.installer_aufraeumen_setzen(db, "vielleicht")
    db.werte[zustand.K_INSTALLER] = "kaputt"
    assert zustand.installer_aufraeumen(db) == "fragen"


# ══ Rueckfrage ════════════════════════════════════════════════════════════════════════

def test_gefragt_wird_nur_zusammen_mit_einer_neuen_version_und_nur_einmal_endgueltig():
    db = FakeDb()
    assert zustand.frage_faellig(db, "1.8.1") is True
    assert zustand.frage_faellig(db, None) is False and zustand.frage_faellig(db, "kaputt") is False
    zustand.antwort_merken(db, "nein")
    assert zustand.frage_faellig(db, "1.8.2") is False
    zustand.antwort_merken(db, "ja")
    assert zustand.frage_faellig(db, "1.9.0") is False


def test_spaeter_fragt_erst_bei_einer_neueren_version_wieder():
    db = FakeDb()
    zustand.antwort_merken(db, "spaeter", bei_version="1.8.1")
    assert zustand.frage_faellig(db, "1.8.1") is False       # dieselbe Version: nicht schon wieder
    assert zustand.frage_faellig(db, "1.8.0") is False
    assert zustand.frage_faellig(db, "1.8.2") is True        # das naechste Update fragt wieder
    assert zustand.gefragt(db)["antwort"] == "spaeter"


def test_ungueltige_antworten_werden_abgelehnt_und_kaputte_werte_gelten_als_ungefragt():
    db = FakeDb()
    with pytest.raises(ValueError):
        zustand.antwort_merken(db, "vielleicht")
    db.werte[zustand.K_GEFRAGT] = {"antwort": "ja!!"}
    assert zustand.gefragt(db)["antwort"] is None
    db.werte[zustand.K_GEFRAGT] = "ja"
    assert zustand.gefragt(db)["antwort"] is None
    db.werte[zustand.K_GEFRAGT] = {"antwort": "spaeter", "bei_version": "kaputt"}
    assert zustand.gefragt(db) == {"antwort": "spaeter", "bei_version": None}
    assert zustand.frage_faellig(db, "1.8.1") is True


# ══ Verlauf ═══════════════════════════════════════════════════════════════════════════

def test_der_verlauf_haelt_die_letzten_fuenfzig_eintraege_neueste_zuletzt():
    db = FakeDb()
    for i in range(60):
        zustand.verlauf_anhaengen(db, version=f"1.8.{i}", ergebnis="installiert")
    v = zustand.verlauf(db)
    assert len(v) == zustand.VERLAUF_MAX and v[0]["version"] == "1.8.10" and v[-1]["version"] == "1.8.59"
    assert all("zeit" in e for e in v)


def test_ein_kaputter_verlauf_ist_ein_leerer():
    for kaputt in ("text", {"a": 1}, [1, "x", None]):
        assert zustand.verlauf(FakeDb({zustand.K_VERLAUF: kaputt})) == []
    assert zustand.verlauf(FakeDb({zustand.K_VERLAUF: [{"a": 1}, 5]})) == [{"a": 1}]


# ══ Statusdatei ═══════════════════════════════════════════════════════════════════════

def test_start_bestaetigen_ohne_programmordner_tut_nichts():
    assert zustand.start_bestaetigen() is False


def test_start_bestaetigen_traegt_die_bestaetigung_fuer_die_laufende_fassung_ein(tmp_path, monkeypatch):
    app = programmordner(tmp_path, fassungen=("1.8.0",))
    boot.waehle_fassung(app)
    monkeypatch.setenv("PBP_APP_DIR", str(app))
    monkeypatch.setenv("PBP_FASSUNG", "1.8.0")
    assert zustand.start_bestaetigen() is True
    s = json.loads((app / "update_status.json").read_text())
    assert s["start"]["bestaetigt"] is True and s["bestaetigt"] == "1.8.0"


def test_ein_rueckgang_wird_einmal_gemeldet_und_dann_als_gesehen_vermerkt(tmp_path, monkeypatch):
    app = programmordner(tmp_path, fassungen=("1.8.0",),
                         status={"rueckgang": {"von": "1.8.1", "nach": "1.8.0", "grund": "ImportError", "gemeldet": False}})
    monkeypatch.setenv("PBP_APP_DIR", str(app))
    monkeypatch.setenv("PBP_FASSUNG", "1.8.0")
    assert zustand.rueckgang_offen()["von"] == "1.8.1"
    assert zustand.rueckgang_gesehen() is True
    assert zustand.rueckgang_offen() is None
    assert zustand.rueckgang_gesehen() is True                    # nichts Neues, aber kein Fehler


def test_gescheiterte_fassungen_kommen_aus_der_statusdatei(tmp_path):
    app = programmordner(tmp_path, status={"gescheitert": ["1.8.1", 5, None]})
    assert zustand.gescheiterte_fassungen(app) == ["1.8.1"]
    assert zustand.gescheiterte_fassungen(tmp_path / "gibtsnicht") == []


# ══ Verfuegbarkeit ════════════════════════════════════════════════════════════════════

def test_ohne_umgebung_ist_das_auto_update_nicht_verfuegbar_und_der_grund_ist_ein_satz(monkeypatch):
    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: True)
    ok, grund = layout.verfuegbarkeit()
    assert ok is False and "Installer" in grund and grund.endswith(".")


def test_unter_anderen_systemen_als_windows_ist_es_nicht_verfuegbar(monkeypatch):
    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: False)
    ok, grund = layout.verfuegbarkeit()
    assert ok is False and "Windows" in grund


def test_mit_programmordner_und_fassung_ist_es_verfuegbar(tmp_path, monkeypatch):
    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: True)
    monkeypatch.setenv("PBP_APP_DIR", str(programmordner(tmp_path)))
    monkeypatch.setenv("PBP_FASSUNG", "1.8.0")
    assert layout.verfuegbarkeit() == (True, "")


def test_ein_programmordner_der_nicht_existiert_gilt_nicht(monkeypatch, tmp_path):
    monkeypatch.setenv("PBP_APP_DIR", str(tmp_path / "gibtsnicht"))
    assert layout.programmordner() is None


# ══ Vertrag mit dem Startbaustein ═════════════════════════════════════════════════════

@pytest.mark.parametrize("wert", ["1.8.0", "1.8.0-beta.15", "1.8.0-rc.1", "0.0.1", "999.999.9999", "1.8", "v1.8.0", "1.8.0\n", "١.٨.٠",
                                  "1.8.0-nightly.1", "", None, 5, "../1.8.0", "1.8.0.0", "1.8.0-beta", "1.8.0-beta.1000"])
def test_programm_und_startbaustein_lesen_fassungsnummern_gleich(wert):
    assert fassung.schluessel(wert) == boot.sortschluessel(wert)


def test_programm_und_startbaustein_ordnen_fassungen_gleich():
    reihe = ["1.8.0-alpha.1", "1.8.0-beta.2", "1.8.0-rc.1", "1.8.0", "1.8.1", "1.10.0", "2.0.0"]
    assert sorted(reihe, key=fassung.schluessel) == sorted(reihe, key=boot.sortschluessel) == reihe


def test_die_dateinamen_im_programm_sind_die_des_startbausteins():
    assert (layout.AKTUELL, layout.STATUS, layout.VERSIONEN, layout.FERTIG, layout.BELEGUNG) == \
        ("aktuell.txt", "update_status.json", "versions", ".fertig", ".in_benutzung")
    assert (layout.ENV_APP, layout.ENV_FASSUNG, layout.FORMAT) == ("PBP_APP_DIR", "PBP_FASSUNG", 1)
    assert layout.lese_status is boot.lese_status and layout.gueltige_fassungen is boot.gueltige_fassungen
    assert layout.schreibe_atomar is boot.schreibe_atomar


def test_der_vertrag_des_startbausteins_ist_eingefroren():
    """Der Startbaustein wird einmal installiert und nie ausgetauscht. Aendert sich eine dieser Zahlen oder Namen,
    gibt es Installationen, die ihn nicht mehr verstehen: dann braucht es ein neues FORMAT, nicht eine stille Aenderung."""
    assert boot.FORMAT == 1
    assert (boot.MAX_UNBESTAETIGT, boot.NACHSICHT_S) == (2, 90)
    assert boot.PAKET == "bewerbungs_assistent"
    for name in ("app_dir", "lese_status", "schreibe_status", "lese_aktuell", "fassung_gueltig", "gueltige_fassungen",
                 "waehle_fassung", "start_bestaetigen", "schreibe_atomar", "sortschluessel", "starte"):
        assert callable(getattr(boot, name)), name
