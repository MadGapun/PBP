"""#1165: Die Sprachdaten der Texterkennung kommen aus einer festen Fassung und werden geprüft.

Vorher lud `ensure_language` die Dateien `deu`, `eng` und `osd` vom wandernden Zweig `main` und legte sie ungeprüft in den
tessdata-Ordner. Jetzt gilt (wie bei #1152 für das Setup des Programms):

* Setzer: jede nachladbare Sprache trägt eine gültige SHA-256 in der Registry, und die Adresse zeigt auf einen Commit,
* Leser: ohne Summe wird gar nicht erst geladen; eine falsche Summe verwirft die Datei und sagt, warum; scheitert eine von
  mehreren Dateien, bleibt auch von den anderen nichts liegen,
* die Meldung des Installationsjobs nennt, wenn nur das deutsche Sprachpaket fehlt.

Kein Netz: `urlopen` ist ersetzt, der Komponenten-Ordner liegt unter tmp_path und wird zugesichert.
"""
from __future__ import annotations

import hashlib
import re
import time
from types import SimpleNamespace

import pytest

from bewerbungs_assistent.services import components

INHALT = {"deu": b"d" * 1500, "eng": b"e" * 2500, "osd": b"o" * 3500}
SUMMEN = {k: hashlib.sha256(v).hexdigest() for k, v in INHALT.items()}


class _Antwort:
    """Stand-in für die urlopen-Antwort: ein Stück, dann Ende."""

    def __init__(self, daten: bytes):
        self.headers = {"Content-Length": str(len(daten))}
        self._daten = daten

    def read(self, n=-1):
        daten, self._daten = self._daten, b""
        return daten

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def tmp_db(tmp_path):
    from bewerbungs_assistent.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db
    db.close()


@pytest.fixture
def umgebung(tmp_db, tmp_path, monkeypatch):
    """PBP-tessdata-Ordner im Temp-Verzeichnis, Registry mit Testsummen, urlopen liefert INHALT je Sprache."""
    ordner = tmp_path / "components"
    monkeypatch.setattr(components, "components_dir", lambda: ordner)
    assert str(tmp_path) in str(components.components_dir()), "Komponenten-Ordner nicht isoliert"
    monkeypatch.setattr(components, "find_component_binary", lambda db, name: None)
    monkeypatch.setattr(components, "available_languages", lambda db: [])
    monkeypatch.setattr(components, "_install_tessdata_dir", lambda db: None)
    monkeypatch.setattr(components, "time", SimpleNamespace(sleep=lambda s: None))
    monkeypatch.setattr(components, "TESSDATA_SPRACHEN", dict(SUMMEN))
    abrufe = []
    inhalt = dict(INHALT)

    def urlopen(req, timeout=0):
        url = req.full_url
        abrufe.append(url)
        lang = re.search(r"/([a-z_]+)\.traineddata$", url).group(1)
        return _Antwort(inhalt[lang])

    monkeypatch.setattr(components.urllib.request, "urlopen", urlopen)
    return SimpleNamespace(db=tmp_db, ordner=ordner, td=ordner / "tessdata", abrufe=abrufe, inhalt=inhalt)


def _dateien(ordner):
    if not ordner.exists():
        return []
    return sorted(p.relative_to(ordner).as_posix() for p in ordner.rglob("*") if p.is_file())


# ── Setzer: die Registry ──────────────────────────────────────────────────────────────

def test_jede_nachladbare_sprache_hat_eine_gueltige_pruefsumme():
    assert set(components.TESSDATA_SPRACHEN) >= {"deu", "eng", "osd"}, "ensure_language lädt diese drei"
    for lang, summe in components.TESSDATA_SPRACHEN.items():
        assert re.fullmatch(r"[0-9a-f]{64}", summe), f"{lang}: keine gültige SHA-256 (64 Hexzeichen, klein)"
    assert len(set(components.TESSDATA_SPRACHEN.values())) == len(components.TESSDATA_SPRACHEN), "zwei Sprachen, eine Summe"


def test_die_adresse_zeigt_auf_einen_commit_und_nicht_auf_einen_zweig():
    assert re.fullmatch(r"[0-9a-f]{40}", components._TESSDATA_FAST_COMMIT)
    url = components._TESSDATA_FAST_URL.format(lang="deu")
    assert url == ("https://github.com/tesseract-ocr/tessdata_fast/raw/"
                   f"{components._TESSDATA_FAST_COMMIT}/deu.traineddata")
    assert "/main/" not in url and "/master/" not in url


def test_im_quelltext_steht_kein_wandernder_zweig_mehr():
    import inspect
    quelle = inspect.getsource(components)
    assert "tessdata_fast/raw/main" not in quelle
    assert "tessdata_fast/raw/master" not in quelle


# ── Leser: geladen wird aus der festen Fassung, mit Prüfung ───────────────────────────

def test_geladen_wird_aus_der_festen_fassung(umgebung):
    erg = components.ensure_language(umgebung.db, "deu")
    assert erg["status"] == "nachgeladen", erg
    erwartet = [components._TESSDATA_FAST_URL.format(lang=x) for x in ("deu", "eng", "osd")]
    assert umgebung.abrufe == erwartet
    assert all("/" + components._TESSDATA_FAST_COMMIT + "/" in u for u in umgebung.abrufe)


def test_mit_richtiger_summe_liegen_alle_drei_im_ordner(umgebung):
    erg = components.ensure_language(umgebung.db, "deu")
    assert erg["status"] == "nachgeladen"
    assert _dateien(umgebung.td) == ["deu.traineddata", "eng.traineddata", "osd.traineddata"]
    assert (umgebung.td / "deu.traineddata").read_bytes() == INHALT["deu"]


def test_ohne_summe_wird_nichts_geladen(umgebung):
    erg = components.ensure_language(umgebung.db, "fra")
    assert erg["status"] == "fehler"
    assert umgebung.abrufe == [], "es wurde etwas geladen, das sich nicht prüfen lässt"
    assert _dateien(umgebung.ordner) == []
    assert "Prüfsumme" in erg["fehler"] and "fra.traineddata" in erg["fehler"] and "tessdata" in erg["fehler"]


@pytest.mark.parametrize("summe", ["", None, "abc", "0" * 63, "0" * 65, "g" * 64])
def test_eine_kaputte_summe_in_der_registry_laedt_nichts(umgebung, monkeypatch, summe):
    monkeypatch.setattr(components, "TESSDATA_SPRACHEN", {**SUMMEN, "deu": summe})
    erg = components.ensure_language(umgebung.db, "deu")
    assert erg["status"] == "fehler" and "Prüfsumme" in erg["fehler"]
    assert umgebung.abrufe == []
    assert _dateien(umgebung.ordner) == []


def test_eine_falsche_summe_verwirft_die_datei_und_sagt_warum(umgebung, monkeypatch):
    monkeypatch.setattr(components, "TESSDATA_SPRACHEN", {**SUMMEN, "deu": "0" * 64})
    erg = components.ensure_language(umgebung.db, "deu")
    assert erg["status"] == "fehler"
    assert "Prüfsumme" in erg["fehler"] and "deu.traineddata" in erg["fehler"] and "verworfen" in erg["fehler"]
    assert umgebung.abrufe, "geladen wurde (die Summe war formal gültig)"
    assert _dateien(umgebung.ordner) == [], "nichts bleibt liegen, auch keine .part-Datei"


def test_eine_unterwegs_veraenderte_datei_wird_verworfen(umgebung):
    """Ein Proxy oder Virenscanner tauscht den Inhalt: Länge stimmt, Summe nicht."""
    umgebung.inhalt["deu"] = b"X" * len(INHALT["deu"])
    erg = components.ensure_language(umgebung.db, "deu")
    assert erg["status"] == "fehler" and "Prüfsumme" in erg["fehler"]
    assert _dateien(umgebung.ordner) == []


def test_scheitert_eine_von_mehreren_dateien_bleibt_auch_von_den_anderen_nichts(umgebung):
    """deu und eng sind schon abgelegt, wenn osd durchfällt: ein halber Satz im PBP-Ordner wäre schlimmer als keiner,
    denn TESSDATA_PREFIX zeigt dann nur noch auf ihn."""
    umgebung.inhalt["osd"] = b"X" * len(INHALT["osd"])
    erg = components.ensure_language(umgebung.db, "deu")
    assert erg["status"] == "fehler" and "osd.traineddata" in erg["fehler"]
    assert _dateien(umgebung.ordner) == []


def test_was_vorher_schon_da_war_bleibt_beim_scheitern_unberuehrt(umgebung):
    umgebung.td.mkdir(parents=True)
    (umgebung.td / "eng.traineddata").write_bytes(INHALT["eng"])
    umgebung.inhalt["osd"] = b"X" * len(INHALT["osd"])
    erg = components.ensure_language(umgebung.db, "deu")
    assert erg["status"] == "fehler"
    assert _dateien(umgebung.ordner) == ["tessdata/eng.traineddata"]


def test_der_ordner_neben_dem_programm_wird_ebenso_geprueft(umgebung, monkeypatch, tmp_path):
    install = tmp_path / "Tesseract-OCR" / "tessdata"
    install.mkdir(parents=True)
    monkeypatch.setattr(components, "_install_tessdata_dir", lambda db: install)
    monkeypatch.setattr(components, "TESSDATA_SPRACHEN", {**SUMMEN, "deu": "0" * 64})
    erg = components.ensure_language(umgebung.db, "deu")
    assert erg["status"] == "fehler" and "Prüfsumme" in erg["fehler"]
    assert _dateien(install) == []
    assert len(umgebung.abrufe) == 1, "neben dem Programm wird nur die eine Sprache geladen"


def test_eine_vorhandene_sprache_wird_nicht_neu_geladen(umgebung, monkeypatch):
    monkeypatch.setattr(components, "available_languages", lambda db: ["deu", "eng"])
    erg = components.ensure_language(umgebung.db, "deu")
    assert erg == {"status": "vorhanden", "sprache": "deu"}
    assert umgebung.abrufe == []


def test_wird_eng_verlangt_wird_es_nicht_doppelt_geladen(umgebung):
    erg = components.ensure_language(umgebung.db, "eng")
    assert erg["status"] == "nachgeladen"
    assert sorted(umgebung.abrufe) == sorted(
        components._TESSDATA_FAST_URL.format(lang=x) for x in ("eng", "osd"))


def test_download_ohne_summe_verhaelt_sich_wie_vorher(tmp_path, monkeypatch):
    """Der Setup des Programms prüft nach dem Laden selbst (#1152); `_download` ohne Summe ändert daran nichts."""
    monkeypatch.setattr(components.urllib.request, "urlopen", lambda req, timeout=0: _Antwort(b"inhalt"))
    ziel = tmp_path / "x.bin"
    components._download("https://example.invalid/x", ziel, lambda p, m: None)
    assert ziel.read_bytes() == b"inhalt"


def test_download_mit_falscher_summe_legt_keine_datei_unter_dem_endnamen_an(tmp_path, monkeypatch):
    monkeypatch.setattr(components.urllib.request, "urlopen", lambda req, timeout=0: _Antwort(b"inhalt"))
    ziel = tmp_path / "x.bin"
    with pytest.raises(RuntimeError, match="Prüfsumme"):
        components._download("https://example.invalid/x", ziel, lambda p, m: None, sha256="0" * 64)
    assert list(tmp_path.iterdir()) == []


# ── Der Installationsjob sagt, wenn nur Deutsch fehlt ─────────────────────────────────

def _warte(db, job_id):
    for _ in range(200):
        job = db.get_background_job(job_id)
        if job and job.get("status") in ("fertig", "fehler"):
            return job
        time.sleep(0.05)
    pytest.fail("Install-Job wurde nicht fertig — der Thread würde ins Teardown racen")


def test_der_job_nennt_das_fehlende_deutsche_sprachpaket(umgebung, monkeypatch):
    monkeypatch.setattr(components, "install_component", lambda db, name, progress=None: {"status": "installiert"})
    monkeypatch.setattr(components, "ensure_language", lambda db, lang="deu", progress=None: {
        "status": "fehler", "fehler": "Die Prüfsumme von deu.traineddata stimmt nicht."})
    job = components.start_install_job(umgebung.db, "tesseract")
    fertig = _warte(umgebung.db, job["job_id"])
    assert fertig["status"] == "fertig", "die Texterkennung steht; nur Deutsch fehlt"
    assert "Sprachpaket" in fertig["message"] and "Prüfsumme von deu.traineddata" in fertig["message"]


def test_der_job_meldet_ohne_sprachproblem_wie_bisher(umgebung, monkeypatch):
    monkeypatch.setattr(components, "install_component", lambda db, name, progress=None: {"status": "installiert"})
    monkeypatch.setattr(components, "ensure_language", lambda db, lang="deu", progress=None: {"status": "nachgeladen"})
    job = components.start_install_job(umgebung.db, "tesseract")
    fertig = _warte(umgebung.db, job["job_id"])
    assert fertig["status"] == "fertig" and fertig["message"] == "Installation abgeschlossen"
