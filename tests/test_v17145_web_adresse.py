"""v1.7.145 — Adressen und Exporte aus Sicht der Sicherheitspruefung (01.10.2026).

* A2: "Beschreibung nachladen" las per file:// jede lokale Datei.
* A3: eine javascript:-Adresse in einer Stelle fuehrte beim Klick auf den
  Original-Link und im gedruckten Verlauf Code im Ursprung des Dashboards aus.
* C1: der Komplett-Export liess bei jedem Aufruf eine Kopie der Datenbank
  im Temp-Ordner liegen.
* C2: Firmen-/Titeltexte wie =HYPERLINK(...) landeten unveraendert in der CSV.
"""
import csv
import html
import io
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import web_adresse as wa  # noqa: E402


# ══ Die Regel ══════════════════════════════════════════════════════

FAELLE = json.loads((ROOT / "tests" / "fixtures" / "web_adresse_faelle.json")
                    .read_text(encoding="utf-8"))


# Dieselbe Fallliste liest frontend/src/lib/webAdresse.test.mjs: Server und
# Oberflaeche duerfen nicht auseinanderlaufen (eine Liste, zwei Pruefer).
@pytest.mark.parametrize("url,erlaubt", FAELLE)
def test_nur_http_und_https_sind_adressen(url, erlaubt):
    assert wa.ist_web_adresse(url) is erlaubt


def test_oder_leer_gibt_die_bereinigte_adresse_oder_nichts():
    assert wa.web_adresse_oder_leer("  https://example.com/x ") == "https://example.com/x"
    assert wa.web_adresse_oder_leer("javascript:alert(1)") == ""
    assert wa.web_adresse_oder_leer(None) == ""


# ══ Umgebung fuer die Endpunkte ════════════════════════════════════

@pytest.fixture
def umgebung(monkeypatch, tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database, get_data_dir
    assert str(tmp_path) in str(get_data_dir()), "Datenordner nicht isoliert"
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "pbp.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Beispiel Person"})
    monkeypatch.setattr(dash, "_db", db)
    yield TestClient(dash.app), dash, db, tmp_path
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


def _bewerbung(db, **felder):
    daten = {"company": "Beispiel Werkzeugbau GmbH", "title": "Konstrukteur",
             "status": "beworben"}
    daten.update(felder)
    return db.add_application(daten)


# ══ A2: Beschreibung nachladen ═════════════════════════════════════

def test_snapshot_liest_keine_lokale_datei(umgebung):
    tc, dash, db, tmp_path = umgebung
    geheim = tmp_path / "geheim.cfg"
    geheim.write_text("GEHEIM-TESTINHALT", encoding="utf-8")
    aid = _bewerbung(db)
    for url in (geheim.as_uri(), "ftp://example.com/x", "javascript:alert(1)"):
        r = tc.post(f"/api/applications/{aid}/snapshot", json={"url": url})
        assert r.status_code == 400, (url, r.status_code, r.text[:80])
        assert "http" in r.json()["error"]
    row = db.get_application(aid)
    assert not (row.get("description_snapshot") or "")


def test_snapshot_laedt_weiterhin_normale_adressen(umgebung, monkeypatch):
    """Die Gegenrichtung: ein Schutz, der den Normalfall bricht, ist keiner."""
    tc, dash, db, tmp_path = umgebung
    aid = _bewerbung(db)

    class _Antwort:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return ("<html><body><article>" + "Aufgaben und Anforderungen. " * 12
                    + "</article></body></html>").encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=0: _Antwort())
    r = tc.post(f"/api/applications/{aid}/snapshot", json={"url": "https://example.com/job"})
    assert r.status_code == 200, r.text
    assert "Aufgaben und Anforderungen" in (db.get_application(aid).get("description_snapshot") or "")


# ══ A3: Adressen im gedruckten Verlauf und im Stellen-HTML ═════════

def test_gedruckter_verlauf_verlinkt_keine_javascript_adresse(umgebung):
    tc, dash, db, tmp_path = umgebung
    boese = _bewerbung(db, url="javascript:fetch('/api/profiles')")
    gut = _bewerbung(db, company="Beispiel Maschinenbau AG", url="https://example.com/stelle/1")
    seite = tc.get(f"/api/application/{boese}/timeline/print").text
    assert "javascript:" not in seite.lower()
    seite_gut = tc.get(f"/api/application/{gut}/timeline/print").text
    assert "href='https://example.com/stelle/1'" in seite_gut


def test_stellen_html_verlinkt_keine_javascript_adresse():
    from bewerbungs_assistent.dashboard import _render_stelle_html
    boese = _render_stelle_html({"title": "T", "company": "F", "url": "javascript:alert(1)"},
                                None, html.escape)
    assert "javascript:" not in boese.lower() and "<a href" not in boese
    gut = _render_stelle_html({"title": "T", "company": "F", "url": "https://example.com/x"},
                              None, html.escape)
    assert 'href="https://example.com/x"' in gut


# ══ C2: CSV-Injection ══════════════════════════════════════════════

def test_csv_export_neutralisiert_formeln(umgebung):
    tc, dash, db, tmp_path = umgebung
    formeln = ['=HYPERLINK("http://example.com/x?"&A2,"Klick")', "+cmd|calc!A0",
               "@SUM(A1:A9)", "-2+3", chr(9) + "=1+1"]
    for text in formeln:
        _bewerbung(db, company=text)
    _bewerbung(db, company="-5", title="Beispiel-Titel")  # eine Zahl bleibt eine Zahl
    _bewerbung(db, company="Normale Firma", title="Konstrukteur (m/w/d)")
    zeilen = list(csv.DictReader(io.StringIO(tc.get("/api/applications/export.csv").text.lstrip("﻿"))))
    firmen = {z["Firma"] for z in zeilen}
    for text in formeln:
        assert "'" + text in firmen, text
        assert text not in firmen, f"Formel unveraendert exportiert: {text!r}"
    assert "-5" in firmen and "Normale Firma" in firmen
    assert any(z["Titel"] == "Konstrukteur (m/w/d)" for z in zeilen)


def test_csv_helfer_aendert_normale_texte_nicht():
    from bewerbungs_assistent.dashboard import _csv_zelle_sicher
    for text in ("", "Firma", "a=b", "x+y", "Müller & Söhne", "-3,5", "-12", "2026-05-01", "10.05.2026"):
        assert _csv_zelle_sicher(text) == text, text
    for text in ("=1", "+1", "@x", "-x", "-1+1", "-"):
        assert _csv_zelle_sicher(text) == "'" + text, text


# ══ C1: Export-Paket raeumt hinter sich auf ════════════════════════

def test_export_paket_hinterlaesst_keinen_temp_ordner(umgebung, monkeypatch):
    tc, dash, db, tmp_path = umgebung
    import tempfile
    arbeitsordner = tmp_path / "export-temp"
    arbeitsordner.mkdir()
    monkeypatch.setattr(tempfile, "mkdtemp", lambda *a, **kw: str(arbeitsordner))
    antwort = tc.get("/api/export-package")
    assert antwort.status_code == 200
    assert antwort.content[:2] == b"PK"  # eine ZIP-Datei kam an
    assert not arbeitsordner.exists(), "Temp-Ordner mit Datenbankkopie blieb liegen"


def test_export_paket_raeumt_auch_im_fehlerfall_auf(umgebung, monkeypatch):
    tc, dash, db, tmp_path = umgebung
    import tempfile
    import zipfile
    arbeitsordner = tmp_path / "export-temp"
    arbeitsordner.mkdir()
    monkeypatch.setattr(tempfile, "mkdtemp", lambda *a, **kw: str(arbeitsordner))

    def kaputt(*a, **kw):
        raise OSError("Platte voll")

    monkeypatch.setattr(zipfile, "ZipFile", kaputt)
    antwort = tc.get("/api/export-package")
    assert antwort.status_code == 500
    assert not arbeitsordner.exists()


# ══ A3: die Oberflaeche verlinkt Adressen von aussen nur geprueft ══

import re  # noqa: E402

#: window.open mit festem Ziel aus dem Programm selbst (kein Text von aussen)
_FESTE_OEFFNER = {("ElwosaSidebarChat.jsx", "url"),     # github.com/.../wiki/<Seite>
                  ("SettingsPage.jsx", "url"),           # mailto:-Baustein
                  ("App.jsx", '"claude://"')}
_ADRESS_MERKMAL = re.compile(r"(?:\burl\b|\.url\b|_url\b|\bupdateUrl\b)")
_INTERN = ("sichereAdresse(", "apiUrl(", "buildZipUrl(", "exportHref(",
           "registrierungs_url")


def _jsx():
    return sorted((ROOT / "frontend" / "src").rglob("*.jsx"))


def test_kein_link_zeigt_ungeprueft_auf_eine_adresse_von_aussen():
    """Jeder href, der eine Adresse aus Stelle/Bewerbung/Termin/Nachricht
    traegt, geht durch sichereAdresse(). Die Suche ist absichtlich weit: ein
    neuer Link auf `x.url` faellt hier auf, auch wenn niemand an diesen Test
    denkt."""
    verstoesse = []
    for datei in _jsx():
        text = datei.read_text(encoding="utf-8-sig")
        for m in re.finditer(r"href=\{([^{}]*)\}", text):
            ausdruck = m.group(1).strip()
            if _ADRESS_MERKMAL.search(ausdruck) and not any(k in ausdruck for k in _INTERN):
                zeile = text[:m.start()].count(chr(10)) + 1
                verstoesse.append(f"{datei.name}:{zeile}: href={{{ausdruck}}}")
    assert not verstoesse, "ungeprueft verlinkt:\n  " + "\n  ".join(verstoesse)


def test_kein_window_open_mit_adresse_von_aussen_ohne_pruefung():
    verstoesse = []
    for datei in _jsx():
        text = datei.read_text(encoding="utf-8-sig")
        for m in re.finditer(r"window\.open\(\s*([^,)]+)", text):
            erstes = m.group(1).strip()
            if erstes.startswith(('"', "`")) or "apiUrl(" in erstes:
                continue
            if (datei.name, erstes) in _FESTE_OEFFNER:
                continue
            zeile = text[:m.start()].count(chr(10)) + 1
            verstoesse.append(f"{datei.name}:{zeile}: window.open({erstes}, ...)")
    assert not verstoesse, "ungeprueft geoeffnet:\n  " + "\n  ".join(verstoesse)


def test_die_pruefung_ist_wirklich_verdrahtet():
    """Nicht-leerer Beleg: die Helfer werden an vielen Stellen benutzt."""
    benutzt = sum(d.read_text(encoding="utf-8-sig").count("sichereAdresse(")
                  + d.read_text(encoding="utf-8-sig").count("oeffneAdresse(")
                  for d in _jsx())
    assert benutzt >= 15, benutzt


def test_der_node_test_laeuft_in_der_ci():
    ci = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "node frontend/src/lib/webAdresse.test.mjs" in ci
