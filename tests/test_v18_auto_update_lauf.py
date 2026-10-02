"""Auto-Update (#1093): der Hintergrund-Job — nachsehen, Stufen, Ruhe, Sperre pro Fassung, Zeitgeber, Start.

Die Stufen sind der Kern der Zusage an den Menschen:

    aus / hinweis    PBP installiert NIE von selbst (auch nicht „nur ein bisschen“),
    auto_*           PBP installiert von selbst — aber nie waehrend anderer Arbeit, nie eine Vorabversion,
                     nie eine Fassung, die schon einmal scheiterte, und nie ueber die Linie hinaus.
"""
import json
import threading
import time

import pytest
from _au_hilfen import FakeOeffner, eintrag, liste, programmordner

import bewerbungs_assistent_boot as boot
from bewerbungs_assistent.services.auto_update import installation, lauf, layout, quelle, zustand


@pytest.fixture(autouse=True)
def _sauberer_zustand(monkeypatch):
    lauf._PRUEFUNG.update(zeit=0.0, ergebnis=None)
    lauf._JOB.update(id=None, status=None, phase="", anteil=0.0, text="", version=None, ausloeser="")
    monkeypatch.setattr(boot, "_BEREIT", False)
    yield
    lauf._PRUEFUNG.update(zeit=0.0, ergebnis=None)


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    app = programmordner(tmp_path / "pc", fassungen=("1.8.0",))
    monkeypatch.setenv("PBP_APP_DIR", str(app))
    monkeypatch.setenv("PBP_FASSUNG", "1.8.0")
    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: True)
    return app


# ══ Auszug aus den Release-Notizen ═══════════════════════════════════════════════════════

def test_der_auszug_nimmt_die_ersten_saetze_und_laesst_die_installationsanleitung_weg():
    text = ("Der Stellen-Tab blendet nichts mehr still aus.\n\n- **Neu:** Filter merken sich ihren Zustand.\n"
            "- Ein Fehler beim Speichern wurde behoben.\n- vierter Punkt, der nicht mehr hineinpasst.\n\n---\n\n"
            "## 📦 Wie installiere oder aktualisiere ich PBP?\n\n1. ZIP herunterladen")
    auszug = lauf.auszug_aus_notizen(text)
    assert auszug == ["Der Stellen-Tab blendet nichts mehr still aus.", "Neu: Filter merken sich ihren Zustand.",
                      "Ein Fehler beim Speichern wurde behoben."]
    assert not any("ZIP" in a or "installiere" in a for a in auszug)


def test_der_auszug_ueberspringt_ueberschriften_tabellen_und_kurzes():
    assert lauf.auszug_aus_notizen("# Titel\n| a | b |\n> zitat\nkurz\nEin richtiger Satz steht hier.") == ["Ein richtiger Satz steht hier."]
    assert lauf.auszug_aus_notizen("") == [] and lauf.auszug_aus_notizen(None) == []


def test_markdown_wird_im_auszug_entfernt():
    assert lauf.auszug_aus_notizen("Siehe [das Wiki](https://x.example/y) für `Details` und **mehr** Text.") == \
        ["Siehe das Wiki für Details und mehr Text."]


# ══ Nachsehen ════════════════════════════════════════════════════════════════════════════

def test_pruefen_findet_eine_neue_stabile_fassung_der_eigenen_linie(umgebung):
    p = lauf.pruefen(oeffner=liste(eintrag("v1.8.1"), eintrag("v1.7.150"), eintrag("v1.9.0")), laufende="1.8.0", app=umgebung)
    assert p["status"] == "neu" and p["version"] == "1.8.1"
    assert p["auszug"] == ["Neue Hinweise im Dashboard."] and p["groesse"] == 2_500_000 and p["zeit"]


def test_pruefen_meldet_aktuell_wenn_nichts_neueres_in_der_linie_liegt(umgebung):
    p = lauf.pruefen(oeffner=liste(eintrag("v1.8.0"), eintrag("v1.9.0"), eintrag("v2.0.0")), laufende="1.8.0", app=umgebung)
    assert p["status"] == "aktuell"


def test_vorabversionen_und_entwuerfe_gelten_nie(umgebung):
    p = lauf.pruefen(oeffner=liste(eintrag("v1.8.1", prerelease=True), eintrag("v1.8.2", draft=True)), laufende="1.8.0", app=umgebung)
    assert p["status"] == "aktuell"


def test_ohne_die_update_dateien_ist_die_freigabe_noch_nicht_bereit(umgebung):
    p = lauf.pruefen(oeffner=liste(eintrag("v1.8.1", dateien=False)), laufende="1.8.0", app=umgebung)
    assert p["status"] == "unvollstaendig" and p["version"] == "1.8.1" and "von Hand" in p["text"]


def test_mit_vertrautem_schluessel_gehoert_die_signaturdatei_zu_den_noetigen(umgebung, monkeypatch):
    from bewerbungs_assistent.services.auto_update import schluessel
    monkeypatch.setattr(schluessel, "VERTRAUTE_SCHLUESSEL", {"haupt": "ab" * 32})
    assert lauf.pruefen(oeffner=liste(eintrag("v1.8.1")), laufende="1.8.0", app=umgebung, frisch=True)["status"] == "unvollstaendig"
    lauf._PRUEFUNG.update(zeit=0.0, ergebnis=None)
    assert lauf.pruefen(oeffner=liste(eintrag("v1.8.1", signatur=True)), laufende="1.8.0", app=umgebung)["status"] == "neu"


def test_keine_antwort_wird_ehrlich_gemeldet_und_nicht_als_aktuell_verbucht(umgebung):
    p = lauf.pruefen(oeffner=FakeOeffner({quelle.API_FREIGABEN: OSError("kein Netz")}), laufende="1.8.0", app=umgebung)
    assert p["status"] == "keine_antwort" and p["code"] == "netz" and "GitHub" in p["text"]


def test_eine_schon_vorgemerkte_neuere_fassung_ist_kein_update_mehr(tmp_path):
    app = programmordner(tmp_path, fassungen=("1.8.0", "1.8.1"), aktuell="1.8.1")
    p = lauf.pruefen(oeffner=liste(eintrag("v1.8.1")), laufende="1.8.0", app=app)
    assert p["status"] == "aktuell"
    lauf._PRUEFUNG.update(zeit=0.0, ergebnis=None)
    assert lauf.pruefen(oeffner=liste(eintrag("v1.8.2")), laufende="1.8.0", app=app)["version"] == "1.8.2"


def test_eine_antwort_wird_kurz_behalten_ein_klick_umgeht_das_aber_nicht_dichter_als_der_mindestabstand(umgebung):
    o = liste(eintrag("v1.8.1"))
    lauf.pruefen(oeffner=o, laufende="1.8.0", app=umgebung)
    lauf.pruefen(oeffner=o, laufende="1.8.0", app=umgebung)
    lauf.pruefen(oeffner=o, laufende="1.8.0", app=umgebung, frisch=True)       # direkt danach: zu dicht, bleibt beim Gemerkten
    assert len(o.aufrufe) == 1
    lauf._PRUEFUNG["zeit"] -= lauf.MIN_ABSTAND_FRISCH_S + 1
    lauf.pruefen(oeffner=o, laufende="1.8.0", app=umgebung, frisch=True)
    assert len(o.aufrufe) == 2


def test_ein_fehlschlag_wird_nicht_zehn_minuten_lang_behalten(umgebung):
    kaputt = FakeOeffner({quelle.API_FREIGABEN: OSError("weg")})
    lauf.pruefen(oeffner=kaputt, laufende="1.8.0", app=umgebung)
    assert lauf.FEHLSCHLAG_GILT_S < lauf.ERFOLG_GILT_S
    lauf._PRUEFUNG["zeit"] -= lauf.FEHLSCHLAG_GILT_S + 1
    ok = liste(eintrag("v1.8.1"))
    assert lauf.pruefen(oeffner=ok, laufende="1.8.0", app=umgebung)["status"] == "neu"       # nicht die alte Fehlmeldung


def test_ohne_laufende_fassung_gibt_es_nichts_zu_pruefen(monkeypatch):
    monkeypatch.delenv("PBP_FASSUNG", raising=False)
    assert lauf.pruefen(oeffner=liste())["status"] == "nicht_verfuegbar"


def test_die_letzte_pruefung_wird_in_der_datenbank_gemerkt(umgebung, tmp_db):
    lauf.pruefen(tmp_db, oeffner=liste(eintrag("v1.8.1")), laufende="1.8.0", app=umgebung)
    gemerkt = lauf.letzte_pruefung(tmp_db)
    assert gemerkt["status"] == "neu" and gemerkt["version"] == "1.8.1" and "laufende" not in gemerkt


# ══ Sperre pro Fassung ═══════════════════════════════════════════════════════════════════

def test_ein_dauerhafter_fehler_sperrt_die_fassung_bis_zum_ausdruecklichen_klick(tmp_db):
    lauf._blockade_merken(tmp_db, "1.8.1", "pruefsumme", "Die Prüfsumme stimmt nicht.")
    b = lauf.blockiert(tmp_db, "1.8.1")
    assert b["dauerhaft"] is True and b["code"] == "pruefsumme" and b["bis"] is None
    assert lauf.blockiert(tmp_db, "1.8.2") is None, "eine NEUERE Fassung bekommt eine neue Chance"
    lauf.blockade_loeschen(tmp_db)
    assert lauf.blockiert(tmp_db, "1.8.1") is None


def test_ein_netzfehler_sperrt_nur_fuer_eine_stunde(tmp_db):
    lauf._blockade_merken(tmp_db, "1.8.1", "netz", "Keine Verbindung.")
    b = lauf.blockiert(tmp_db, "1.8.1")
    assert b["dauerhaft"] is False and b["bis"]
    tmp_db.set_setting(lauf.K_BLOCKIERT, {**b, "bis": "2000-01-01T00:00:00+00:00"})
    assert lauf.blockiert(tmp_db, "1.8.1") is None


@pytest.mark.parametrize("code", sorted(lauf.DAUERHAFTE_CODES))
def test_jeder_dauerhafte_code_ist_ein_code_den_der_ablauf_wirklich_kennt(code):
    from bewerbungs_assistent.services.auto_update.fehler import TEXTE
    assert code in TEXTE


# ══ Ruhe ═════════════════════════════════════════════════════════════════════════════════

def test_ruhig_solange_kein_anderer_job_laeuft(tmp_db):
    assert lauf.ruhig(tmp_db) == (True, "")
    job = tmp_db.create_background_job("jobsuche", {})
    assert lauf.ruhig(tmp_db) == (False, "jobsuche")
    tmp_db.update_background_job(job, "fertig", progress=100)
    assert lauf.ruhig(tmp_db) == (True, "")


def test_eine_sicherung_haelt_das_update_nicht_auf(tmp_db):
    tmp_db.create_background_job("sicherung", {})
    assert lauf.ruhig(tmp_db) == (True, "")


# ══ Installation im Hintergrund ══════════════════════════════════════════════════════════

class Erfolg:
    ok, code, text, sha256, signiert = True, "", "Version 1.8.1 ist installiert und gilt nach dem nächsten Neustart.", "ab" * 32, False


class Fehlschlag:
    ok, code, text, sha256, signiert = False, "pruefsumme", "Die Prüfsumme stimmt nicht.", "", False


def installieren_mit(ergebnis, aufrufe=None):
    def _i(version, **kw):
        if aufrufe is not None:
            aufrufe.append((version, kw))
        kw["fortschritt"]("laden", 0.5, "Lade …")
        return ergebnis
    return _i


def test_ein_gelungener_lauf_steht_als_fertig_im_job_und_im_stand(umgebung, tmp_db):
    aufrufe = []
    r = lauf.starte_installation(tmp_db, "1.8.1", ausloeser="klick", installieren=installieren_mit(Erfolg, aufrufe), synchron=True)
    assert r["status"] == "gestartet"
    assert lauf.job_stand()["status"] == "fertig" and lauf.job_stand()["anteil"] == 1.0
    job = tmp_db.get_background_job(r["job_id"])
    assert job["status"] == "fertig" and job["job_type"] == "auto_update" and job["params"]["ausloeser"] == "klick"
    assert aufrufe[0][0] == "1.8.1" and aufrufe[0][1]["ausloeser"] == "klick"
    assert lauf.blockiert(tmp_db, "1.8.1") is None


def test_ein_fehlgeschlagener_lauf_sperrt_die_fassung_fuer_den_automatismus(umgebung, tmp_db):
    r = lauf.starte_installation(tmp_db, "1.8.1", ausloeser="automatisch", installieren=installieren_mit(Fehlschlag), synchron=True)
    assert tmp_db.get_background_job(r["job_id"])["status"] == "fehler"
    assert lauf.job_stand()["status"] == "fehler" and "Prüfsumme" in lauf.job_stand()["text"]
    assert lauf.blockiert(tmp_db, "1.8.1")["code"] == "pruefsumme"


def test_ein_klick_darf_eine_gesperrte_fassung_noch_einmal_versuchen(umgebung, tmp_db):
    lauf._blockade_merken(tmp_db, "1.8.1", "pruefsumme", "alt")
    lauf.starte_installation(tmp_db, "1.8.1", ausloeser="klick", installieren=installieren_mit(Erfolg), synchron=True)
    assert lauf.blockiert(tmp_db, "1.8.1") is None


def test_eine_vorabversion_wird_gar_nicht_erst_gestartet(umgebung, tmp_db):
    aufrufe = []
    r = lauf.starte_installation(tmp_db, "1.8.1-beta.2", installieren=installieren_mit(Erfolg, aufrufe), synchron=True)
    assert r["status"] == "abgelehnt" and aufrufe == [] and tmp_db.get_running_background_job() is None


def test_ohne_programmordner_wird_nichts_gestartet(tmp_db, monkeypatch):
    monkeypatch.delenv("PBP_APP_DIR", raising=False)
    r = lauf.starte_installation(tmp_db, "1.8.1", synchron=True)
    assert r["status"] == "nicht_verfuegbar" and r["text"]


def test_ein_zweiter_start_waehrend_ein_update_laeuft_wird_abgelehnt(umgebung, tmp_db):
    gestartet, weiter = threading.Event(), threading.Event()

    def langsam(version, **kw):
        gestartet.set()
        weiter.wait(10)
        return Erfolg

    r1 = lauf.starte_installation(tmp_db, "1.8.1", installieren=langsam)
    assert r1["status"] == "gestartet"
    assert gestartet.wait(5)
    r2 = lauf.starte_installation(tmp_db, "1.8.2", installieren=installieren_mit(Erfolg), synchron=True)
    assert r2["status"] == "laeuft_bereits"
    weiter.set()
    for t in threading.enumerate():
        if t.name.startswith("pbp-update-"):
            t.join(10)
    assert lauf.job_stand()["status"] == "fertig"


def test_stuerzt_der_lauf_ab_bleibt_ein_fehler_im_job_und_die_sperre_ist_frei(umgebung, tmp_db):
    def boese(version, **kw):
        raise RuntimeError("niemand rechnet damit")

    r = lauf.starte_installation(tmp_db, "1.8.1", installieren=boese, synchron=True)
    assert tmp_db.get_background_job(r["job_id"])["status"] == "fehler"
    r2 = lauf.starte_installation(tmp_db, "1.8.1", installieren=installieren_mit(Erfolg), synchron=True)
    assert r2["status"] == "gestartet"


# ══ Die Stufen ═══════════════════════════════════════════════════════════════════════════

def schritt(tmp_db, aufrufe, *, stufe, eintraege=None, **kw):
    zustand.stufe_setzen(tmp_db, stufe)
    return lauf.automatik_schritt(tmp_db, oeffner=liste(*(eintraege or [eintrag("v1.8.1")])),
                                  installieren=installieren_mit(Erfolg, aufrufe), synchron=True, **kw)


@pytest.mark.parametrize("stufe", ["aus", "hinweis"])
def test_in_den_stufen_aus_und_hinweis_installiert_pbp_nie_von_selbst(umgebung, tmp_db, stufe):
    aufrufe = []
    r = schritt(tmp_db, aufrufe, stufe=stufe)
    assert r["installiert"] is False and aufrufe == [] and r["status"] == "neu"


@pytest.mark.parametrize("stufe", ["auto_meldung", "auto_still"])
def test_in_den_automatischen_stufen_wird_installiert(umgebung, tmp_db, stufe):
    aufrufe = []
    r = schritt(tmp_db, aufrufe, stufe=stufe)
    assert r["installiert"] is True and [a[0] for a in aufrufe] == ["1.8.1"] and aufrufe[0][1]["ausloeser"] == "automatisch"


def test_ohne_neue_version_wird_auch_in_der_automatik_nichts_installiert(umgebung, tmp_db):
    aufrufe = []
    r = schritt(tmp_db, aufrufe, stufe="auto_still", eintraege=[eintrag("v1.8.0")])
    assert r["status"] == "aktuell" and aufrufe == []


def test_arbeitet_gerade_etwas_anderes_wird_gewartet(umgebung, tmp_db):
    aufrufe = []
    tmp_db.create_background_job("jobsuche", {})
    r = schritt(tmp_db, aufrufe, stufe="auto_still")
    assert r["status"] == "wartet" and "jobsuche" in r["grund"] and aufrufe == []


def test_eine_gesperrte_fassung_wird_nicht_wieder_von_selbst_versucht(umgebung, tmp_db):
    lauf._blockade_merken(tmp_db, "1.8.1", "signatur", "Signatur ungültig.")
    aufrufe = []
    r = schritt(tmp_db, aufrufe, stufe="auto_still")
    assert r["status"] == "blockiert" and aufrufe == []


def test_ein_linienwechsel_wird_in_keiner_stufe_angeboten(umgebung, tmp_db):
    aufrufe = []
    r = schritt(tmp_db, aufrufe, stufe="auto_still", eintraege=[eintrag("v1.9.0"), eintrag("v2.0.0")])
    assert r["status"] == "aktuell" and aufrufe == []


def test_in_einer_installation_ohne_programmordner_tut_die_automatik_nichts(tmp_db, monkeypatch):
    monkeypatch.delenv("PBP_APP_DIR", raising=False)
    zustand.stufe_setzen(tmp_db, "auto_still")
    assert lauf.automatik_schritt(tmp_db, oeffner=liste(eintrag("v1.8.1")))["status"] == "nicht_verfuegbar"


def test_die_stufe_wird_aus_der_datenbank_gelesen_nicht_aus_dem_speicher(umgebung, tmp_db):
    aufrufe = []
    schritt(tmp_db, aufrufe, stufe="auto_still")
    assert len(aufrufe) == 1
    lauf._PRUEFUNG.update(zeit=0.0, ergebnis=None)
    lauf._blockade_merken(tmp_db, "1.8.1", "netz", "x")
    lauf.blockade_loeschen(tmp_db)
    r = schritt(tmp_db, aufrufe, stufe="aus")
    assert r["installiert"] is False and len(aufrufe) == 1


# ══ Zeitgeber ════════════════════════════════════════════════════════════════════════════

def test_der_zeitgeber_wartet_dann_prueft_und_haelt_an_wenn_man_ihn_stoppt(umgebung, tmp_db, monkeypatch):
    schritte = []
    monkeypatch.setattr(lauf, "automatik_schritt", lambda db, **kw: schritte.append(1) or {"status": "aktuell"})
    monkeypatch.setattr(lauf.aufraeumen, "reste_entfernen", lambda app: [])
    wartezeiten = []

    def warte(sekunden):
        wartezeiten.append(sekunden)
        return len(wartezeiten) >= 4        # beim vierten Warten gilt: Schluss

    t = lauf.zeitgeber_starten(tmp_db, warte=warte, intervall=111, verzoegerung=22)
    t.join(10)
    assert not t.is_alive() and wartezeiten == [22, 111, 111, 111] and len(schritte) == 3
    assert not t.name.startswith("pbp-"), "ein Dauerlaeufer darf das Aufraeumen der Tests nicht aufhalten"


def test_ein_fehler_im_durchgang_beendet_den_zeitgeber_nicht(umgebung, tmp_db, monkeypatch):
    def kaputt(db, **kw):
        raise RuntimeError("Durchgang kaputt")

    monkeypatch.setattr(lauf, "automatik_schritt", kaputt)
    monkeypatch.setattr(lauf.aufraeumen, "reste_entfernen", lambda app: [])
    zaehler = []
    t = lauf.zeitgeber_starten(tmp_db, warte=lambda s: zaehler.append(s) or len(zaehler) >= 3, intervall=1, verzoegerung=1)
    t.join(10)
    assert len(zaehler) == 3, "er hat nach dem Fehler weitergemacht"


def test_ohne_programmordner_startet_kein_zeitgeber(tmp_db, monkeypatch):
    monkeypatch.delenv("PBP_APP_DIR", raising=False)
    assert lauf.zeitgeber_starten(tmp_db) is None


# ══ Beim Start ═══════════════════════════════════════════════════════════════════════════

def test_beim_start_werden_reste_weggeraeumt_und_bereit_gemeldet(umgebung, tmp_db, monkeypatch):
    monkeypatch.setattr(lauf, "zeitgeber_starten", lambda db, **kw: None)
    (umgebung / "versions" / "1.8.5.neu").mkdir()
    (umgebung / "update").mkdir()
    (umgebung / "update" / "x.part").write_bytes(b"1")
    boot.waehle_fassung(umgebung)
    r = lauf.beim_start(tmp_db, bestaetigung_nach=0)
    assert r["verfuegbar"] is True and r["bestaetigt"] is True
    assert boot.ist_bereit() is True
    assert not (umgebung / "versions" / "1.8.5.neu").exists() and not (umgebung / "update").exists()
    assert json.loads((umgebung / "update_status.json").read_text())["start"]["bestaetigt"] is True


def test_die_bestaetigung_kommt_erst_nach_der_wartezeit(umgebung, tmp_db, monkeypatch):
    monkeypatch.setattr(lauf, "zeitgeber_starten", lambda db, **kw: None)
    boot.waehle_fassung(umgebung)
    r = lauf.beim_start(tmp_db, bestaetigung_nach=0.3)
    assert r["bestaetigt"] is False
    assert json.loads((umgebung / "update_status.json").read_text())["start"]["bestaetigt"] is False
    time.sleep(1.0)
    assert json.loads((umgebung / "update_status.json").read_text())["start"]["bestaetigt"] is True


def test_beim_start_ohne_programmordner_tut_nichts_und_meldet_nichts(tmp_db, monkeypatch):
    monkeypatch.delenv("PBP_APP_DIR", raising=False)
    assert lauf.beim_start(tmp_db) == {"verfuegbar": False}
    assert boot.ist_bereit() is False


def test_ein_fehler_beim_aufraeumen_verhindert_den_start_nicht(umgebung, tmp_db, monkeypatch):
    monkeypatch.setattr(lauf, "zeitgeber_starten", lambda db, **kw: None)

    def kaputt(app):
        raise OSError("Platte kaputt")

    monkeypatch.setattr(lauf.aufraeumen, "reste_entfernen", kaputt)
    assert lauf.beim_start(tmp_db, bestaetigung_nach=0)["verfuegbar"] is True


# ══ Uebersicht ═══════════════════════════════════════════════════════════════════════════

def test_die_uebersicht_ohne_programmordner_nennt_den_grund_und_die_einstellungen(tmp_db, monkeypatch):
    monkeypatch.delenv("PBP_APP_DIR", raising=False)
    u = lauf.uebersicht(tmp_db)
    assert u["verfuegbar"] is False and u["grund"] and u["stufe"] == "aus" and u["vorgaenger_behalten"] == 3
    assert u["stufen"] == ["aus", "hinweis", "auto_meldung", "auto_still"] and u["neu"] is None


def test_die_uebersicht_zeigt_laufend_vorgemerkt_und_dass_ein_neustart_noetig_ist(tmp_path, tmp_db, monkeypatch):
    app = programmordner(tmp_path / "pc", fassungen=("1.8.0", "1.8.1"), aktuell="1.8.1")
    monkeypatch.setenv("PBP_APP_DIR", str(app))
    monkeypatch.setenv("PBP_FASSUNG", "1.8.0")
    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: True)
    u = lauf.uebersicht(tmp_db)
    assert (u["laufend"], u["aktuell"], u["neustart_noetig"]) == ("1.8.0", "1.8.1", True)
    assert u["installiert"] == ["1.8.1", "1.8.0"]


def test_die_uebersicht_nennt_die_neue_version_und_ob_gefragt_werden_soll(umgebung, tmp_db):
    lauf.pruefen(tmp_db, oeffner=liste(eintrag("v1.8.1")), laufende="1.8.0", app=umgebung)
    u = lauf.uebersicht(tmp_db)
    assert u["neu"]["version"] == "1.8.1" and u["neu"]["frage_faellig"] is True and u["neu"]["auszug"]
    zustand.antwort_merken(tmp_db, "nein")
    assert lauf.uebersicht(tmp_db)["neu"]["frage_faellig"] is False


def test_nach_der_installation_ist_die_fassung_kein_neues_update_mehr(umgebung, tmp_db):
    lauf.pruefen(tmp_db, oeffner=liste(eintrag("v1.8.1")), laufende="1.8.0", app=umgebung)
    (umgebung / "aktuell.txt").write_text("1.8.1\n", encoding="utf-8")
    from _au_hilfen import fassung_anlegen
    fassung_anlegen(umgebung, "1.8.1")
    assert lauf.uebersicht(tmp_db)["neu"] is None


def test_die_uebersicht_zeigt_eine_unbemerkte_zuruecknahme(umgebung, tmp_db):
    (umgebung / "update_status.json").write_text(json.dumps(
        {"rueckgang": {"von": "1.8.1", "nach": "1.8.0", "grund": "ImportError", "gemeldet": False}}), encoding="utf-8")
    assert lauf.uebersicht(tmp_db)["rueckgang"]["von"] == "1.8.1"
    zustand.rueckgang_gesehen(umgebung)
    assert lauf.uebersicht(tmp_db)["rueckgang"] is None


def test_die_uebersicht_nennt_den_verlauf_neueste_zuerst(umgebung, tmp_db):
    for i in range(12):
        zustand.verlauf_anhaengen(tmp_db, version=f"1.8.{i}", ergebnis="installiert")
    v = lauf.uebersicht(tmp_db)["verlauf"]
    assert len(v) == 10 and v[0]["version"] == "1.8.11"


def test_eine_zurueckgenommene_fassung_wird_nie_von_selbst_wieder_installiert(umgebung, tmp_db):
    """Wer auf eine fruehere Version zurueckgeschaltet hat, will bei ihr bleiben. Die Automatik schaltet nicht wieder um
    (Gegenprobe: die Pruefung in `automatik_schritt` war durch keinen Test geschuetzt)."""
    tmp_db.set_setting(lauf.K_ABGELEHNT, ["1.8.1"])
    aufrufe = []
    r = schritt(tmp_db, aufrufe, stufe="auto_still")
    assert r["status"] == "zurueckgenommen" and r["installiert"] is False and aufrufe == []
    # eine NOCH neuere Fassung ist wieder ein Angebot
    lauf._PRUEFUNG.update(zeit=0.0, ergebnis=None)
    r2 = schritt(tmp_db, aufrufe, stufe="auto_still", eintraege=[eintrag("v1.8.2"), eintrag("v1.8.1")])
    assert r2["installiert"] is True and [a[0] for a in aufrufe] == ["1.8.2"]
