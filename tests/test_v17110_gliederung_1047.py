"""Tests fuer #1047 — Anzeigentexte verloren beim Einlesen jede Gliederung.

Dreizehn Adapter wandelten das Beschreibungs-HTML per

    re.sub(r"<[^>]+>", " ", html); re.sub(r"\\s+", " ", text)

um, und `text_aus_html` las mit `get_text(separator=" ")`. Gemessen am
14.09.2026: acht Arbeitnow-Anzeigen tragen 4 bis 35 Absaetze und bis zu
34 Listenpunkte, der Leser liess 0 Zeilenumbrueche uebrig; auf einer
Bestandskopie hatte bei Arbeitnow (0/123), RemoteOK (0/19), Remotive
(0/15) und ferchau (0/7) kein Text ab 500 Zeichen einen Umbruch, bei der
Bundesagentur 492 von 508.
"""
import asyncio
import importlib
import logging
import os
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.job_scraper.html_text import (  # noqa: E402
    QUELLEN_OHNE_GLIEDERUNG,
    gegliederter_text,
    ist_flach,
)

ANZEIGE_HTML = (
    "<h2>Ueber uns</h2><p>Die Musterfirma Nord baut Anlagen.</p>"
    "<h2>Ihre Aufgaben</h2><ul><li>Planung von Projekten</li>"
    "<li><p>Abstimmung mit Kunden</p></li></ul>"
    "<p>Erste Zeile<br>Zweite Zeile</p>"
    "<!-- t=3n --><script>var x = 1;</script>"
)
ERWARTET = ("Ueber uns\n\nDie Musterfirma Nord baut Anlagen.\n\n"
            "Ihre Aufgaben\n\n- Planung von Projekten\n- Abstimmung mit Kunden"
            "\n\nErste Zeile\nZweite Zeile")


# ------------------------------------------------------ der gemeinsame Leser


def test_absaetze_listen_und_ueberschriften_bleiben():
    assert gegliederter_text(ANZEIGE_HTML) == ERWARTET


def test_kommentare_und_skripte_gehoeren_nicht_zum_text():
    text = gegliederter_text(ANZEIGE_HTML)
    assert "t=3n" not in text and "var x" not in text


def test_seitentitel_und_noscript_gehoeren_nicht_zum_text():
    """`get_text()` laesst Skripte und Styles selbst aus, `<title>` und
    `<noscript>` nicht — die Gegenprobe zeigte das Entfernen als stumm,
    solange nur ein Skript im Beispiel stand."""
    html = ("<html><head><title>Seitentitel</title></head><body>"
            "<noscript>Bitte JavaScript aktivieren</noscript>"
            "<p>Inhalt der Anzeige</p></body></html>")
    assert gegliederter_text(html) == "Inhalt der Anzeige"


def test_inline_elemente_sind_kein_neuer_absatz():
    assert gegliederter_text("<p>Wir <strong>bauen</strong> <a href='#'>Anlagen</a>.</p>") \
        == "Wir bauen Anlagen."


def test_entitaeten_werden_aufgeloest():
    assert gegliederter_text("<p>Forschung &amp; Entwicklung</p>") == "Forschung & Entwicklung"
    assert gegliederter_text("Forschung &amp; Entwicklung") == "Forschung & Entwicklung"


def test_text_ohne_markup_behaelt_seine_umbrueche():
    assert gegliederter_text("Eins  zwei\n\n\n\nDrei\r\nVier") == "Eins zwei\n\nDrei\nVier"


def test_ein_kleiner_als_zeichen_ist_kein_markup():
    assert gegliederter_text("Gehalt < 50k, <5 Jahre") == "Gehalt < 50k, <5 Jahre"


def test_schmucklinien_verschwinden_und_schneiden_nichts_ab():
    """Befund der Pruefung: `---` auf eigener Zeile ist der Notiz-Trenner.

    Bliebe die Zeile stehen, schnitten `_strip_pbp_notes` und
    `stellen_skills.anzeigenteil` den Rest der Anzeige ab.
    """
    from bewerbungs_assistent.job_scraper import _strip_pbp_notes
    from bewerbungs_assistent.services import stellen_skills

    text = gegliederter_text("<p>Vorn</p><p>-----</p><hr><p>Hinten mit Windchill</p>")
    assert text == "Vorn\n\nHinten mit Windchill"
    assert _strip_pbp_notes(text) == text
    assert stellen_skills.anzeigenteil(text) == text


def test_flach_heisst_lang_und_ohne_jeden_umbruch():
    assert ist_flach("x " * 300)
    assert not ist_flach("x " * 100)
    assert not ist_flach(("x " * 300) + "\n")
    assert not ist_flach(None)


# ---------------------------------------------- AK 1 und 2: jede Quelle


@pytest.mark.parametrize("modul,funktion", [
    ("arbeitnow", "_clean_html"),
    ("berufsstart", "_strip_html"),
    ("greenhouse", "_strip_html"),
    ("himalayas", "_strip_html"),
    ("meinestadt", "_strip_html"),
    ("personio", "_strip_html"),
    ("remoteok", "_strip_html"),
    ("remotive", "_strip_html"),
    ("studentjob", "_strip_html"),
    ("workday_dax", "_strip_html"),
])
def test_jeder_adapter_behaelt_die_gliederung(modul, funktion):
    mod = importlib.import_module(f"bewerbungs_assistent.job_scraper.{modul}")
    assert getattr(mod, funktion)(ANZEIGE_HTML) == ERWARTET


def test_gulp_gliedert_nur_die_beschreibung():
    from bewerbungs_assistent.job_scraper import gulp

    stelle = gulp.projekt_zu_stelle({
        "title": "<mark>Muster</mark>\nProjekt", "location": "Musterstadt",
        "description": ANZEIGE_HTML, "skills": ["PLM"], "id": "1047",
    })
    assert stelle["title"] == "Muster Projekt"
    assert stelle["description"].startswith(ERWARTET)


def test_workable_gliedert_nur_die_beschreibung():
    from bewerbungs_assistent.job_scraper import workable

    stelle = workable.stelle_aus({
        "title": "Muster\nIngenieur", "company": {"title": "Musterfirma Nord"},
        "location": {"city": "Musterstadt"}, "description": ANZEIGE_HTML,
        "requirementsSection": "<ul><li>PLM</li></ul>", "id": "1047",
        "url": "https://example.com/1047",
    })
    assert stelle["title"] == "Muster Ingenieur"
    assert stelle["description"] == ERWARTET + "\n\n- PLM"


@pytest.mark.parametrize("datei", [
    "job_scraper/ferchau.py", "job_scraper/freelancermap.py",
    "job_scraper/stepstone.py", "dashboard.py",
])
def test_die_uebrigen_leser_gehen_durch_den_gemeinsamen_weg(datei):
    """Diese Wege brauchen Netz oder Browser — geprueft wird die Bauform."""
    quelle = (_repo() / "src" / "bewerbungs_assistent" / datei).read_text(
        encoding="utf-8-sig")
    assert "gegliederter_text(" in quelle
    assert ".get_text() if desc_html" not in quelle
    assert "div.textContent" not in quelle
    # Der JSON-LD-Weg des Bewerbungs-Snapshots im Dashboard — die
    # Gegenprobe zeigte ihn als stumm, weil ein zweiter Aufruf in derselben
    # Datei die Pruefung auf `gegliederter_text(` schon erfuellte.
    assert 'BeautifulSoup(desc, "html.parser").get_text(separator=" "' not in quelle
    assert 'get_text(separator=" ", strip=True)\n                        if len(txt)' not in quelle


def test_kein_adapter_macht_aus_der_beschreibung_wieder_einen_absatz():
    """Das Muster `<[^>]+>` -> Leerzeichen darf nur noch einzeilige Felder
    treffen (Titel, Ort) — in gulp und workable heisst der Helfer `_text`."""
    ordner = _repo() / "src" / "bewerbungs_assistent" / "job_scraper"
    funde = []
    for datei in sorted(ordner.glob("*.py")):
        if datei.name == "html_text.py":
            continue
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            if re.search(r're\.sub\(r?["\']<\[\^>\]\+>["\'],\s*["\'] ["\']', zeile):
                funde.append(datei.name)
    assert sorted(set(funde)) == ["gulp.py", "workable.py"], funde


# ----------------------------------------------- AK 2: das Nachladen


def test_json_ld_liefert_gegliederten_text():
    import json

    from bewerbungs_assistent.job_scraper import extract_jobposting_jsonld

    # Echte Seiten schreiben `</` im JSON als `<\/` — sonst beendete das
    # `</script>` der Beispielanzeige das ld+json-Tag vorzeitig.
    daten = json.dumps({"@type": "JobPosting", "description": ANZEIGE_HTML})
    html = ('<script type="application/ld+json">'
            + daten.replace("</", "<" + chr(92) + "/") + "</script>")
    assert extract_jobposting_jsonld(html)["description"] == ERWARTET


def test_der_rueckfall_ueber_selektoren_liefert_gegliederten_text():
    from bewerbungs_assistent.job_scraper import text_aus_html

    html = ('<html><body><div class="job-description">' + ANZEIGE_HTML
            + "<p>" + "Weitere Angaben zur Stelle. " * 5 + "</p></div></body></html>")
    text = text_aus_html(html)
    assert text.startswith(ERWARTET)


# ----------------------------------------------- AK 3: die Anzeige


def test_die_detailansichten_zeigen_den_text_gegliedert():
    frontend = _repo() / "frontend" / "src"
    modal = (frontend / "components" / "InlineJobDetailModal.jsx").read_text(encoding="utf-8")
    assert "gegliederterAuszug(job.description" in modal
    assert "textExcerpt(job.description" not in modal
    popup = (frontend / "pages" / "JobsPage.jsx").read_text(encoding="utf-8")
    assert re.search(r'whitespace-pre-wrap[^>]*>\{detailDialog\.job\.description\}', popup)


# ----------------------------------------------- AK 4: der Bestand


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database(db_path=tmp_path / "test.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    datenbank.switch_profile(datenbank.create_profile("Muster"))
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _mcp(db):
    from fastmcp import FastMCP

    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))
    return mcp


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(_run())


FLACH = re.sub(r"\s+", " ", ERWARTET.replace("- ", " ")) + " " + "Fuelltext der Anzeige. " * 25
GEGLIEDERT = ERWARTET + "\n\n" + "Fuelltext der Anzeige. " * 25


def _stelle(db, hash_, text, quelle="arbeitnow"):
    db.save_jobs([{
        "hash": hash_, "title": f"Muster {hash_}", "company": "Musterfirma Nord",
        "url": f"https://example.com/1047/{hash_}", "source": quelle,
        "description": text, "score": 0,
    }])


def test_der_mengenweg_findet_flache_texte(db):
    assert ist_flach(FLACH) and not ist_flach(GEGLIEDERT)
    _stelle(db, "f1047a", FLACH)
    _stelle(db, "f1047b", GEGLIEDERT)
    _stelle(db, "f1047c", FLACH, quelle="hays")
    _stelle(db, "f1047d", "X" * 2000)
    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand", {"umfang": "flach"})
    assert erg["status"] == "vorschau", erg
    assert erg["betroffen"] == 1
    assert erg["gefunden"]["flach"] == 1
    assert "hays" in QUELLEN_OHNE_GLIEDERUNG


def test_ein_gegliederter_text_ersetzt_den_flachen_ohne_zu_wachsen(db, monkeypatch):
    from bewerbungs_assistent.services import nachladen

    _stelle(db, "f1047e", FLACH)
    # Echt kuerzer als der gespeicherte Text — die erste Fassung war es um
    # ein Zeichen nicht (FLACH endet mit einem Leerzeichen, verglichen wird
    # nach `strip()`), und die Gegenprobe zeigte den Fall als stumm.
    ersatz = GEGLIEDERT[:len(FLACH.strip()) - 20].rstrip()
    assert 0.9 * len(FLACH.strip()) <= len(ersatz) < len(FLACH.strip())
    monkeypatch.setattr(nachladen, "beschreibung_holen", lambda url, client, **k:
                        nachladen.Befund(status=nachladen.GELESEN, text=ersatz,
                                         http_status=200, quelle="html"))
    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand",
                {"umfang": "flach", "nur_zaehlen": False})
    assert erg["geheilt"] == 1, erg
    assert "\n" in db.get_job("f1047e")["description"]


def test_ein_deutlich_kuerzerer_text_ersetzt_den_flachen_nicht(db, monkeypatch):
    """Unter 90 % fehlt Inhalt, nicht nur Leerraum."""
    from bewerbungs_assistent.services import nachladen

    _stelle(db, "f1047f", FLACH)
    kurz = ERWARTET
    assert len(kurz) < 0.9 * len(FLACH)
    monkeypatch.setattr(nachladen, "beschreibung_holen", lambda url, client, **k:
                        nachladen.Befund(status=nachladen.GELESEN, text=kurz,
                                         http_status=200, quelle="html"))
    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand",
                {"umfang": "flach", "nur_zaehlen": False})
    assert erg["geheilt"] == 0
    assert db.get_job("f1047f")["description"] == FLACH
