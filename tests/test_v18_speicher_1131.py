"""Speicher & Downloads (#1131, I19): die Orte, das Bereinigen in zwei Schritten, der Guard gegen vergessene Stellen.

Kein Test fasst echte Ordner an: Datenordner, Programmordner, Komponenten, Playwright, Ollama und Downloads zeigen
auf Ordner unter `tmp_path`, und das wird zugesichert (`_alles_unter_tmp`).
"""
import json
import logging
import os
import re
import sys
import threading
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _au_hilfen import programmordner  # noqa: E402

from bewerbungs_assistent.services import components, datenordner, speicher  # noqa: E402
from bewerbungs_assistent.services.auto_update import layout  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent


# ── Umgebung ─────────────────────────────────────────────────────────────────────────────

def _schreibe(pfad: Path, groesse: int = 100, text: bytes = b"x") -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(text * groesse)
    return pfad


def _alles_unter_tmp(tmp_path, *pfade):
    for p in pfade:
        assert str(tmp_path) in str(p), f"nicht isoliert: {p}"


@pytest.fixture
def umgebung(tmp_path, monkeypatch, tmp_db):
    """Alle sieben Orte unter tmp_path. `tmp_db` setzt BA_DATA_DIR auf tmp_path (der Datenordner ist tmp_path selbst)."""
    app = programmordner(tmp_path / "pc", fassungen=("1.8.0", "1.8.1", "1.8.2", "1.8.3", "1.8.4"))
    komp = tmp_path / "komponenten"
    pw = tmp_path / "playwright"
    ollama = tmp_path / "ollama"
    dl = tmp_path / "downloads"
    for p in (komp, pw, ollama, dl):
        p.mkdir()
    monkeypatch.setenv("PBP_APP_DIR", str(app))
    monkeypatch.setenv("PBP_FASSUNG", "1.8.4")
    monkeypatch.setattr(layout, "plattform_unterstuetzt", lambda: True)
    monkeypatch.setattr(components, "components_dir", lambda: komp)
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(pw))
    monkeypatch.setenv("OLLAMA_MODELS", str(ollama))
    monkeypatch.setenv("PBP_DOWNLOADS_ORDNER", str(dl))
    _alles_unter_tmp(tmp_path, datenordner._datenordner(), app, komp, pw, ollama, dl, tmp_db.db_path)
    return type("U", (), dict(db=tmp_db, daten=tmp_path, app=app, komp=komp, pw=pw, ollama=ollama, dl=dl))


def _installer_zip(pfad: Path, mit_bat: bool = True):
    with zipfile.ZipFile(pfad, "w") as zf:
        zf.writestr("PBP-1.7.149/README.md", "x" * 50)
        if mit_bat:
            zf.writestr("PBP-1.7.149/INSTALLIEREN.bat", "@echo off")
    return pfad


def _snapshot(*wurzeln) -> dict:
    """{Pfad: Größe} aller Dateien unter den Wurzeln: damit sich zeigen lässt, dass eine Vorschau nichts anfasst."""
    erg = {}
    for w in wurzeln:
        for p in Path(w).rglob("*"):
            if p.is_file():
                erg[str(p)] = p.stat().st_size
    return erg


# ── Die Orte ─────────────────────────────────────────────────────────────────────────────

def test_die_uebersicht_nennt_jeden_ort_mit_groesse_und_urheber(umgebung):
    u = umgebung
    _schreibe(u.daten / "backups" / "pbp-backup-2026-09-01_10-00-00-taeglich.db", 1000)
    _schreibe(u.komp / "tesseract-setup.exe", 2000)
    _schreibe(u.pw / "chromium-1" / "chrome.exe", 3000)
    _schreibe(u.ollama / "blobs" / "modell", 4000)
    _installer_zip(u.dl / "PBP-1.7.149.zip")
    erg = speicher.uebersicht(u.db)
    orte = {o["id"]: o for o in erg["orte"]}
    assert list(orte) == list(speicher.ORT_IDS) == ["daten", "programm", "komponenten", "playwright", "ollama", "downloads", "eigene"]
    assert {i: o["urheber"] for i, o in orte.items()} == {
        "daten": "pbp", "programm": "pbp", "komponenten": "komponente", "playwright": "fremd", "ollama": "fremd",
        "downloads": "du", "eigene": "du"}
    assert orte["komponenten"]["bytes"] == 2000 and orte["playwright"]["bytes"] == 3000 and orte["ollama"]["bytes"] == 4000
    assert orte["daten"]["bytes"] >= 1000 and orte["programm"]["bytes"] > 0
    assert orte["downloads"]["bytes"] == (u.dl / "PBP-1.7.149.zip").stat().st_size
    for o in orte.values():
        assert o["urheber_text"] and o["name"] and o["was"], o["id"]
    # Fremdes wird gezählt, aber getrennt ausgewiesen
    assert erg["gesamt_fremd_bytes"] == 7000
    assert erg["gesamt_bytes"] == sum(o["bytes"] for o in orte.values() if o["urheber"] != "fremd")


def test_ein_fehlender_ort_heisst_nichts_vorhanden_und_ist_kein_fehler(umgebung, monkeypatch):
    u = umgebung
    import shutil
    shutil.rmtree(u.pw)
    shutil.rmtree(u.dl)
    erg = speicher.uebersicht(u.db)
    orte = {o["id"]: o for o in erg["orte"]}
    for i in ("playwright", "downloads", "eigene"):
        assert orte[i]["nichts_vorhanden"] is True and orte[i]["bytes"] == 0, i
        assert orte[i]["oeffnen"] is False
    assert orte["daten"]["nichts_vorhanden"] is False


def test_ohne_programmordner_gibt_es_den_ort_programm_mit_einem_hinweis_statt_eines_fehlers(umgebung, monkeypatch):
    monkeypatch.delenv("PBP_APP_DIR")
    o = {x["id"]: x for x in speicher.uebersicht(umgebung.db)["orte"]}["programm"]
    assert o["nichts_vorhanden"] is True and "Installationsordner" in o["hinweis"]


def test_der_downloads_ordner_zeigt_nur_echte_pbp_pakete(umgebung):
    u = umgebung
    echt = _installer_zip(u.dl / "PBP-1.7.149.zip")
    _installer_zip(u.dl / "pbp-1.7.150.ZIP")                           # Groß-/Kleinschreibung egal
    _installer_zip(u.dl / "PBP-fremd.zip", mit_bat=False)              # Name passt, Inhalt nicht
    (u.dl / "PBP-kaputt.zip").write_bytes(b"kein zip")                 # nicht lesbar
    _installer_zip(u.dl / "urlaub.zip")                                # Inhalt passt, Name nicht
    _schreibe(u.dl / "PBP-notizen.txt", 10)
    (u.dl / "PBP-ordner.zip").mkdir()
    namen = [p.name for p, _ in speicher.installationspakete()]
    assert namen == ["PBP-1.7.149.zip", "pbp-1.7.150.ZIP"]
    assert echt.exists()


def test_playwright_und_ollama_sind_fremd_und_haben_keine_bereinigung(umgebung):
    orte = {o["id"]: o for o in speicher.uebersicht(umgebung.db)["orte"]}
    for i in ("playwright", "ollama"):
        assert orte[i]["urheber"] == "fremd" and orte[i]["aktionen"] == []
        assert "löscht" in orte[i]["was"] or "löschst" in orte[i]["was"] or "nie" in orte[i]["was"]
    for a in speicher.AKTIONEN.values():
        assert a["ort"] not in ("playwright", "ollama"), "Fremdes wird nie bereinigt"


def test_die_messung_bricht_nach_der_frist_ab_und_sagt_mindestens(tmp_path):
    for i in range(30):
        _schreibe(tmp_path / "viel" / f"datei{i}.bin", 10)
    b, voll = speicher.messen(tmp_path / "viel", frist_s=-1.0)
    assert voll is False and b <= 300
    b, voll = speicher.messen(tmp_path / "viel")
    assert voll is True and b == 300
    assert speicher.messen(tmp_path / "gibt-es-nicht") == (0, True)


def _verknuepfung(link: Path, ziel: Path) -> str:
    """Ein symbolischer Link, sonst (Windows) eine Junction; ohne beides wird der Test uebersprungen."""
    try:
        os.symlink(ziel, link, target_is_directory=ziel.is_dir())
        return "symlink"
    except (OSError, NotImplementedError):
        if sys.platform == "win32" and ziel.is_dir():
            import subprocess
            r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(ziel)], capture_output=True)
            if r.returncode == 0:
                return "junction"
        pytest.skip("Verknüpfungen sind hier nicht erlaubt")


def test_die_messung_folgt_keiner_verknuepfung_auch_keiner_junction(tmp_path):
    _schreibe(tmp_path / "echt" / "a.bin", 100)
    (tmp_path / "ordner").mkdir()
    _verknuepfung(tmp_path / "ordner" / "link", tmp_path / "echt")
    assert speicher.messen(tmp_path / "ordner")[0] == 0


def test_geloescht_wird_nie_ueber_eine_verknuepfung_hinaus(tmp_path):
    """Ein Link im Ordner, der nach draußen zeigt, darf weder das Ziel noch (als Link) sich selbst verlieren."""
    wurzel = tmp_path / "wurzel"
    wurzel.mkdir()
    draussen = tmp_path / "draussen"
    _schreibe(draussen / "wichtig.txt", 10)
    _verknuepfung(wurzel / "ordner_link", draussen)
    assert speicher._loeschen(wurzel / "ordner_link", wurzel) == (False, 0)
    assert (draussen / "wichtig.txt").exists()
    datei = _schreibe(tmp_path / "fremd.txt", 10)
    try:
        os.symlink(datei, wurzel / "datei_link")
    except (OSError, NotImplementedError):
        return
    assert speicher._loeschen(wurzel / "datei_link", wurzel) == (False, 0)
    assert datei.exists() and (wurzel / "datei_link").is_symlink()


# ── Bereinigen: zwei Schritte ──────────────────────────────────────────────────────────────

AKTIONEN_OHNE_AUSWAHL = ["protokolle", "export", "alte_fassungen", "update_arbeitsordner", "komponenten_reste"]


def _bestuecken(u):
    """Von jeder Sorte etwas, das bereinigt werden könnte."""
    for n in ("pbp-backup-2026-09-01_10-00-00-taeglich.db", "pbp-backup-2026-09-02_10-00-00-taeglich.db",
              "pbp-backup-2026-09-03_10-00-00-manuell.db"):
        _schreibe(u.daten / "backups" / n, 500)
    _schreibe(u.daten / "backups" / "pbp-backup-2026-09-01_10-00-00-taeglich-dokumente.zip", 50)
    _schreibe(u.daten / "logs" / "pbp.log.1", 300)
    _schreibe(u.daten / "logs" / "pbp.log.2", 300)
    _schreibe(u.daten / "export" / "lebenslauf.docx", 700)
    _schreibe(u.daten / "export" / "ordner" / "anschreiben.pdf", 700)
    _schreibe(u.app / "update" / "pbp-update-1.8.5.zip.part", 900)
    _schreibe(u.app / "versions" / "1.8.9.neu" / "x.py", 100)
    _schreibe(u.komp / "tesseract-setup.exe", 1200)
    _schreibe(u.komp / "tesseract-setup.exe.part", 400)
    _installer_zip(u.dl / "PBP-1.7.149.zip")
    _installer_zip(u.dl / "PBP-1.7.150.zip")


@pytest.mark.parametrize("aktion", list(speicher.AKTIONEN))
def test_ohne_bestaetigung_wird_nie_etwas_geloescht(umgebung, aktion):
    u = umgebung
    _bestuecken(u)
    vorher = _snapshot(u.daten, u.app, u.komp, u.dl)
    erg = speicher.bereinigen(u.db, aktion)
    assert erg["status"] in ("auswahl", "vorschau", "nichts"), erg
    assert _snapshot(u.daten, u.app, u.komp, u.dl) == vorher
    # auch mit Auswahl, aber ohne Bestätigung
    erg = speicher.bereinigen(u.db, aktion, auswahl=["gibt-es-nicht"])
    assert _snapshot(u.daten, u.app, u.komp, u.dl) == vorher


@pytest.mark.parametrize("aktion", sorted(speicher.AKTIONEN))
def test_jede_aktion_hat_erklaerung_ort_und_knopf(aktion):
    a = speicher.AKTIONEN[aktion]
    assert a["titel"] and a["erklaerung"].endswith(".") and a["knopf"]
    assert a["ort"] in speicher.ORT_IDS


def test_sicherungen_die_neueste_bleibt_immer_und_nur_ausgewaehlte_gehen(umgebung):
    u = umgebung
    _bestuecken(u)
    erg = speicher.bereinigen(u.db, "sicherungen")
    assert erg["status"] == "auswahl" and erg["anzahl"] == 2
    ids = [k["id"] for k in erg["kandidaten"]]
    assert "pbp-backup-2026-09-03_10-00-00-manuell.db" not in ids, "die neueste steht nicht zur Auswahl"
    assert erg["bleibt"] == ["pbp-backup-2026-09-03_10-00-00-manuell.db"]
    # Vorschau der Auswahl, dann Löschen: die Dokumente-ZIP der Sicherung geht mit
    erg = speicher.bereinigen(u.db, "sicherungen", auswahl=["pbp-backup-2026-09-01_10-00-00-taeglich.db"])
    assert erg["status"] == "vorschau" and erg["anzahl"] == 1
    erg = speicher.bereinigen(u.db, "sicherungen", auswahl=["pbp-backup-2026-09-01_10-00-00-taeglich.db"], bestaetigt=True)
    assert erg["status"] == "bereinigt" and erg["entfernt"] == 1 and erg["bytes_frei"] >= 550
    rest = sorted(p.name for p in (u.daten / "backups").iterdir())
    assert rest == ["pbp-backup-2026-09-02_10-00-00-taeglich.db", "pbp-backup-2026-09-03_10-00-00-manuell.db"]


def test_sicherungen_die_neueste_laesst_sich_auch_mit_ausdruecklicher_wahl_nicht_loeschen(umgebung):
    u = umgebung
    _bestuecken(u)
    neueste = "pbp-backup-2026-09-03_10-00-00-manuell.db"
    erg = speicher.bereinigen(u.db, "sicherungen", auswahl=[neueste], bestaetigt=True)
    assert erg["status"] == "nichts"
    assert (u.daten / "backups" / neueste).exists()
    from bewerbungs_assistent.services import sicherung
    r = sicherung.entfernen(u.db, [neueste, "../pbp.db", "unbekannt.db"])
    assert r["geloescht"] == [] and set(r["abgelehnt"]) == {neueste, "../pbp.db", "unbekannt.db"}
    assert (u.daten / "backups" / neueste).exists()


def test_sicherungen_ohne_auswahl_loescht_die_bestaetigung_nichts(umgebung):
    u = umgebung
    _bestuecken(u)
    vorher = _snapshot(u.daten / "backups")
    erg = speicher.bereinigen(u.db, "sicherungen", bestaetigt=True)
    assert erg["status"] == "fehler" and "nichts ausgewählt" in erg["text"].lower()
    assert _snapshot(u.daten / "backups") == vorher


def test_protokolle_das_offene_bleibt_der_rest_geht(umgebung):
    u = umgebung
    _bestuecken(u)
    aktiv = _schreibe(u.daten / "logs" / "pbp.log", 100)
    handler = logging.FileHandler(aktiv, delay=False)
    logging.getLogger("test_speicher_protokoll").addHandler(handler)
    try:
        erg = speicher.bereinigen(u.db, "protokolle")
        assert sorted(k["id"] for k in erg["kandidaten"]) == ["pbp.log.1", "pbp.log.2"]
        erg = speicher.bereinigen(u.db, "protokolle", bestaetigt=True)
        assert erg["status"] == "bereinigt" and erg["entfernt"] == 2
        assert sorted(p.name for p in (u.daten / "logs").iterdir()) == ["pbp.log"]
    finally:
        logging.getLogger("test_speicher_protokoll").removeHandler(handler)
        handler.close()


def test_export_dateien_und_ordner_gehen_der_ordner_selbst_bleibt(umgebung):
    u = umgebung
    _bestuecken(u)
    erg = speicher.bereinigen(u.db, "export", bestaetigt=True)
    assert erg["status"] == "bereinigt" and erg["entfernt"] == 2
    assert (u.daten / "export").is_dir() and list((u.daten / "export").iterdir()) == []


def test_alte_fassungen_die_regel_ist_dieselbe_wie_beim_update_und_die_vorschau_loescht_nichts(umgebung):
    u = umgebung
    u.db.set_setting("auto_update_vorgaenger_behalten", 1)
    erg = speicher.bereinigen(u.db, "alte_fassungen")
    assert erg["status"] == "vorschau"
    assert sorted(k["id"] for k in erg["kandidaten"]) == ["1.8.0", "1.8.1", "1.8.2"], erg
    assert sorted(p.name for p in (u.app / "versions").iterdir()) == ["1.8.0", "1.8.1", "1.8.2", "1.8.3", "1.8.4"]
    erg = speicher.bereinigen(u.db, "alte_fassungen", bestaetigt=True)
    assert erg["status"] == "bereinigt" and erg["entfernt"] == 3
    assert sorted(p.name for p in (u.app / "versions").iterdir()) == ["1.8.3", "1.8.4"]


def test_eine_benutzte_fassung_bleibt_auch_beim_bereinigen(umgebung):
    u = umgebung
    u.db.set_setting("auto_update_vorgaenger_behalten", 1)
    marke = u.app / "versions" / "1.8.0" / ".in_benutzung"
    marke.mkdir()
    (marke / f"{os.getpid()}.json").write_text(json.dumps({"pid": os.getpid(), "zeit": "2026-10-02T00:00:00+00:00"}), encoding="utf-8")
    erg = speicher.bereinigen(u.db, "alte_fassungen", bestaetigt=True)
    assert (u.app / "versions" / "1.8.0").is_dir(), erg
    assert "1.8.0" not in [k["id"] for k in speicher.bereinigen(u.db, "alte_fassungen")["kandidaten"]]


def test_update_reste_arbeitsordner_und_angefangene_installationen(umgebung):
    u = umgebung
    _bestuecken(u)
    erg = speicher.bereinigen(u.db, "update_arbeitsordner")
    assert sorted(k["id"] for k in erg["kandidaten"]) == ["1.8.9.neu", "arbeit"]
    assert (u.app / "update" / "pbp-update-1.8.5.zip.part").exists()
    erg = speicher.bereinigen(u.db, "update_arbeitsordner", bestaetigt=True)
    assert erg["status"] == "bereinigt" and erg["entfernt"] == 2 and erg["bytes_frei"] >= 1000
    assert not (u.app / "versions" / "1.8.9.neu").exists()
    assert not list((u.app / "update").iterdir()) if (u.app / "update").exists() else True
    # die installierten Versionen sind unberührt
    assert sorted(p.name for p in (u.app / "versions").iterdir()) == ["1.8.0", "1.8.1", "1.8.2", "1.8.3", "1.8.4"]


def test_komponenten_reste_nur_setup_dateien_nie_eine_fertige_installation(umgebung):
    u = umgebung
    _bestuecken(u)
    _schreibe(u.komp / "tesseract" / "tesseract.exe", 5000)
    erg = speicher.bereinigen(u.db, "komponenten_reste")
    assert sorted(k["id"] for k in erg["kandidaten"]) == ["tesseract-setup.exe", "tesseract-setup.exe.part"]
    erg = speicher.bereinigen(u.db, "komponenten_reste", bestaetigt=True)
    assert erg["status"] == "bereinigt" and erg["entfernt"] == 2
    assert (u.komp / "tesseract" / "tesseract.exe").exists()


def test_downloads_zip_nur_was_der_mensch_auswaehlt_und_nur_echte_pakete(umgebung):
    u = umgebung
    _bestuecken(u)
    _installer_zip(u.dl / "PBP-fremd.zip", mit_bat=False)
    erg = speicher.bereinigen(u.db, "downloads_zip")
    assert erg["status"] == "auswahl" and sorted(k["id"] for k in erg["kandidaten"]) == ["PBP-1.7.149.zip", "PBP-1.7.150.zip"]
    erg = speicher.bereinigen(u.db, "downloads_zip", auswahl=["PBP-1.7.149.zip", "PBP-fremd.zip", "../x.zip"], bestaetigt=True)
    assert erg["status"] == "bereinigt" and erg["entfernt"] == 1
    assert sorted(p.name for p in u.dl.iterdir()) == ["PBP-1.7.150.zip", "PBP-fremd.zip"]


def test_laufende_arbeit_lehnt_ab_und_nennt_was_laeuft(umgebung):
    u = umgebung
    _bestuecken(u)
    halt = threading.Event()
    t = threading.Thread(target=halt.wait, name="pbp-jobsuche-test", daemon=True)
    t.start()
    try:
        vorher = _snapshot(u.daten, u.app, u.komp, u.dl)
        for aktion in speicher.AKTIONEN:
            erg = speicher.bereinigen(u.db, aktion, auswahl=["x"], bestaetigt=True)
            assert erg["status"] == "abgelehnt" and "Jobsuche" in erg["text"], (aktion, erg)
        assert _snapshot(u.daten, u.app, u.komp, u.dl) == vorher
    finally:
        halt.set()
        t.join(5)


def test_als_werkzeug_zaehlt_der_eigene_aufruf_nicht_als_fremde_arbeit(umgebung, monkeypatch):
    u = umgebung
    monkeypatch.setattr(datenordner, "laufende_arbeit", lambda: [speicher.EIGENER_AUFRUF])
    assert speicher.bereinigen(u.db, "export")["status"] == "abgelehnt"
    assert speicher.bereinigen(u.db, "export", als_werkzeug=True)["status"] in ("nichts", "vorschau")
    monkeypatch.setattr(datenordner, "laufende_arbeit", lambda: ["pbp-jobsuche-x"])
    assert speicher.bereinigen(u.db, "export", als_werkzeug=True)["status"] == "abgelehnt", "fremde Arbeit zählt auch dem Werkzeug"


def test_ein_update_oder_eine_komponenteninstallation_in_arbeit_sperrt_ihre_aktionen(umgebung, monkeypatch):
    u = umgebung
    _bestuecken(u)
    from bewerbungs_assistent.services.auto_update import lauf
    monkeypatch.setattr(lauf, "job_stand", lambda: {"status": "laeuft"})
    for a in ("alte_fassungen", "update_arbeitsordner"):
        assert speicher.bereinigen(u.db, a, bestaetigt=True)["status"] == "abgelehnt"
    assert speicher.bereinigen(u.db, "export")["status"] in ("vorschau", "nichts"), "andere Aktionen bleiben möglich"
    monkeypatch.setattr(components, "_installation_laeuft", lambda db: True)
    assert speicher.bereinigen(u.db, "komponenten_reste", bestaetigt=True)["status"] == "abgelehnt"
    assert (u.komp / "tesseract-setup.exe").exists()


def test_unbekannte_aktion_und_falsche_auswahl_sind_fehler_nicht_still(umgebung):
    u = umgebung
    assert speicher.bereinigen(u.db, "alles_loeschen")["status"] == "fehler"
    assert "erlaubt" in speicher.bereinigen(u.db, "alles_loeschen")
    assert speicher.bereinigen(u.db, "sicherungen", auswahl="eine-datei.db")["status"] == "fehler"


def test_nach_dem_bereinigen_wird_der_ort_neu_gemessen(umgebung):
    u = umgebung
    _bestuecken(u)
    vorher = {o["id"]: o for o in speicher.uebersicht(u.db)["orte"]}["komponenten"]["bytes"]
    erg = speicher.bereinigen(u.db, "komponenten_reste", bestaetigt=True)
    assert erg["ort_neu"]["id"] == "komponenten" and erg["ort_neu"]["bytes"] == vorher - 1600


def test_geloescht_wird_nur_unter_der_wurzel(tmp_path):
    wurzel = tmp_path / "wurzel"
    wurzel.mkdir()
    ausserhalb = _schreibe(tmp_path / "fremd.txt", 10)
    innen = _schreibe(wurzel / "a.txt", 10)
    assert speicher._loeschen(ausserhalb, wurzel) == (False, 0) and ausserhalb.exists()
    assert speicher._loeschen(wurzel, wurzel) == (False, 0) and wurzel.exists(), "nie die Wurzel selbst"
    assert speicher._loeschen(wurzel / ".." / "fremd.txt", wurzel) == (False, 0) and ausserhalb.exists()
    assert speicher._loeschen(innen, wurzel) == (True, 10) and not innen.exists()


# ── Ordner öffnen ────────────────────────────────────────────────────────────────────────

def test_ordner_oeffnen_nimmt_nur_orte_aus_der_festen_liste(umgebung, monkeypatch):
    u = umgebung
    geoeffnet = []
    monkeypatch.setattr(speicher.os, "startfile", lambda p: geoeffnet.append(p), raising=False)
    monkeypatch.setattr(speicher.subprocess, "Popen", lambda cmd, *a, **k: geoeffnet.append(cmd[-1]))
    assert speicher.ordner_oeffnen("daten", u.db)["status"] == "ok"
    assert geoeffnet == [str(u.daten)]
    for boese in ("../etc", "C:/Windows", str(u.daten), ""):
        antwort = speicher.ordner_oeffnen(boese, u.db)
        assert antwort["status"] == "fehler" and "Unbekannter Ort" in antwort["text"], boese
    assert len(geoeffnet) == 1
    import shutil
    shutil.rmtree(u.pw)
    assert speicher.ordner_oeffnen("playwright", u.db)["status"] == "nicht_vorhanden"


# ── Guard: jede Stelle im Code steht in der Liste ────────────────────────────────────────

_STELLE = re.compile(r"LOCALAPPDATA|APPDATA|expanduser|Path\.home\(|gettempdir|mkdtemp|NamedTemporaryFile|TemporaryDirectory"
                     r"|\"Downloads\"|'Downloads'")


def _quellen():
    wurzel = WURZEL / "src" / "bewerbungs_assistent"
    for p in sorted(wurzel.rglob("*.py")):
        if "static" in p.parts:
            continue
        yield p.relative_to(wurzel).as_posix(), p


def test_jede_stelle_im_code_die_ausserhalb_des_datenordners_schreibt_steht_in_der_liste():
    """Eine neue Stelle ohne Eintrag belegt unbemerkt Platz auf dem Rechner. Ein Eintrag braucht einen ehrlichen Grund."""
    fehlen = {}
    for rel, pfad in _quellen():
        text = pfad.read_text(encoding="utf-8-sig")
        treffer = _STELLE.findall(text)
        if treffer and rel not in speicher.STELLEN_IM_CODE:
            fehlen[rel] = sorted(set(treffer))
    assert not fehlen, ("Diese Dateien zeigen auf einen Ort außerhalb des Datenordners und stehen nicht in "
                        f"speicher.STELLEN_IM_CODE (Kategorie und Grund eintragen): {fehlen}")


def test_die_liste_der_stellen_hat_keine_toten_und_keine_leeren_eintraege():
    vorhanden = {rel for rel, _ in _quellen()}
    for rel, (kategorie, grund) in speicher.STELLEN_IM_CODE.items():
        assert rel in vorhanden, f"{rel} gibt es nicht mehr"
        assert kategorie in ("ort", "liest", "kurz", "klein", "eingabe"), rel
        assert len(grund) > 15, f"{rel}: der Grund sagt nichts"


def test_jede_aktion_gehoert_zu_genau_einem_ort_und_der_ort_nennt_sie(umgebung):
    orte = {o["id"]: o for o in speicher.uebersicht(umgebung.db)["orte"]}
    for aid, a in speicher.AKTIONEN.items():
        besitzer = [i for i, o in orte.items() if aid in o["aktionen"]]
        assert besitzer == [a["ort"]], (aid, besitzer)
    for i, o in orte.items():
        for aid in o["aktionen"]:
            assert aid in speicher.AKTIONEN, (i, aid)


def test_der_guard_der_datenordner_liste_bleibt_die_eine_quelle_fuer_den_datenordner(umgebung):
    """#963: keine zweite Liste. Jeder Eintrag der Übersicht für „Deine Daten“ kommt aus `datenordner.uebersicht()`."""
    u = umgebung
    _schreibe(u.daten / "backups" / "x.db", 10)
    _schreibe(u.daten / "unbekannt.txt", 10)
    namen = {e["name"] for e in {o["id"]: o for o in speicher.uebersicht(u.db)["orte"]}["daten"]["eintraege"]}
    assert namen == {e["name"] for e in datenordner.uebersicht(u.daten)}
    assert "unbekannt.txt" in namen


# ── REST und Claude ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def client(umgebung):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    dash._db = umgebung.db
    return TestClient(dash.app)


def test_rest_uebersicht_und_zweistufiges_bereinigen(umgebung, client):
    u = umgebung
    _bestuecken(u)
    r = client.get("/api/speicher")
    assert r.status_code == 200 and [o["id"] for o in r.json()["orte"]] == list(speicher.ORT_IDS)
    r = client.post("/api/speicher/bereinigen", json={"aktion": "export"})
    assert r.status_code == 200 and r.json()["status"] == "vorschau" and r.json()["anzahl"] == 2
    assert (u.daten / "export" / "lebenslauf.docx").exists()
    r = client.post("/api/speicher/bereinigen", json={"aktion": "export", "bestaetigt": "ja"})
    assert r.json()["status"] == "vorschau", "nur ein echtes true bestätigt"
    r = client.post("/api/speicher/bereinigen", json={"aktion": "export", "bestaetigt": True})
    assert r.status_code == 200 and r.json()["status"] == "bereinigt"
    assert not (u.daten / "export" / "lebenslauf.docx").exists()


def test_rest_fehler_haben_die_richtigen_statuscodes(umgebung, client):
    assert client.post("/api/speicher/bereinigen", json={"aktion": "gibts-nicht"}).status_code == 400
    assert client.post("/api/speicher/ordner-oeffnen", json={"ort": "gibts-nicht"}).status_code == 400
    halt = threading.Event()
    t = threading.Thread(target=halt.wait, name="pbp-jobsuche-rest", daemon=True)
    t.start()
    try:
        r = client.post("/api/speicher/bereinigen", json={"aktion": "export", "bestaetigt": True})
        assert r.status_code == 409 and "Jobsuche" in r.json()["text"]
    finally:
        halt.set()
        t.join(5)


@pytest.fixture
def werkzeuge(umgebung):
    import asyncio
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("speicher-test")
    register_all(mcp, umgebung.db, logging.getLogger("speicher-test"))

    def aufruf(name, **args):
        async def _run():
            tool = await mcp.get_tool(name)
            res = await tool.run(args)
            return res.structured_content if hasattr(res, "structured_content") else res
        return asyncio.run(_run())
    return aufruf


def test_claude_sieht_dieselbe_uebersicht_und_kann_nur_in_zwei_schritten_bereinigen(umgebung, werkzeuge):
    u = umgebung
    _bestuecken(u)
    erg = werkzeuge("speicher_anzeigen")
    assert [o["id"] for o in erg["orte"]] == list(speicher.ORT_IDS) and len(erg["zusammenfassung"]) == 7
    vorher = _snapshot(u.daten)
    erg = werkzeuge("speicher_bereinigen", aktion="export")
    assert erg["status"] == "vorschau" and "naechster_schritt" in erg and _snapshot(u.daten) == vorher
    erg = werkzeuge("speicher_bereinigen", aktion="export", bestaetigung=True)
    assert erg["status"] == "bereinigt" and not (u.daten / "export" / "lebenslauf.docx").exists()


def test_die_werkzeuge_sind_eingeordnet_zweistufig_und_lesend(umgebung):
    from bewerbungs_assistent.services import werkzeug_katalog, werkzeug_schutz
    assert werkzeug_schutz.ZWEISTUFIG["speicher_bereinigen"] == "bestaetigung"
    assert werkzeug_schutz.annotations_fuer("speicher_bereinigen")["destructiveHint"] is True
    assert werkzeug_schutz.annotations_fuer("speicher_anzeigen") == {"readOnlyHint": True}
    assert {"speicher_anzeigen", "speicher_bereinigen"} <= werkzeug_katalog.EINSTELLUNG
    import inspect
    from bewerbungs_assistent.tools import speicher as modul
    quelle = inspect.getsource(modul)
    assert "bestaetigung: bool = False" in quelle, "die Vorgabe ist die Vorschau"
