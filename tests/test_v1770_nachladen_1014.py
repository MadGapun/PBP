"""Tests fuer #1014 — Nachladen mit Befund statt Vermutung.

Bericht eines fremden Anwenders (10.09.2026), mit Messungen: 360 von
473 aktiven Stellen der Bundesagentur ohne Anzeigentext, und das
Nachladen schlug bei jeder fehl — mit der Meldung *"evtl. Login-Wall
oder Bot-Block"*.

Zwei Ursachen:

1. Der Nachlade-Pfad scrapte HTML. arbeitsagentur.de laedt seinen
   Inhalt per JavaScript nach; den API-Weg gibt es seit #489, gerufen
   hat ihn niemand.
2. Der HTTP-Status wurde verworfen (`if status != 200: return ""`).
   Aus einem eindeutigen **410 Gone** wurde damit eine Vermutung.

Die Akzeptanzkriterien des Melders stehen hier einzeln als Test.
"""
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad — der Test muss auch aus einem fremden
    Arbeitsverzeichnis laufen (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import nachladen  # noqa: E402

# Eine echte BA-Detail-URL-Form. Die Referenznummer ist erfunden, das
# FORMAT stammt aus dem Adapter (#526).
BA_URL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/14225-testref0000-S"
FREMDE_URL = "https://example.com/stellen/12345"


class _Antwort:
    def __init__(self, status=200, text=""):
        self.status_code = status
        self.text = text


class _Client:
    """Ein Client, der eine feste Antwort gibt und die Aufrufe zaehlt."""

    def __init__(self, antwort):
        self._antwort = antwort
        self.aufrufe = 0

    def get(self, url, **kwargs):
        self.aufrufe += 1
        return self._antwort


# ------------------------------------------------------- URL-Erkennung


def test_1014_ba_detailseiten_werden_erkannt():
    assert nachladen.ist_bundesagentur(BA_URL)
    assert not nachladen.ist_bundesagentur(FREMDE_URL)
    # Die Jobsuche selbst ist keine Detailseite.
    assert not nachladen.ist_bundesagentur(
        "https://www.arbeitsagentur.de/jobsuche/suche?was=PLM")


def test_1014_die_referenznummer_steht_im_pfad():
    """Der Adapter baut `.../jobdetail/{refnr}` (#526) — also rueckwaerts.

    Ohne diese Umkehrung waere der API-Weg nicht erreichbar: die
    Detail-API kennt nur die Referenznummer, die Stelle in der
    Datenbank nur die URL.
    """
    assert nachladen.referenznummer(BA_URL) == "14225-testref0000-S"
    assert nachladen.referenznummer(BA_URL + "/") == "14225-testref0000-S"
    assert nachladen.referenznummer(FREMDE_URL) == ""


# ------------------------------------------- AK: 410 ist keine Vermutung


@pytest.mark.parametrize("code", [404, 410])
def test_1014_weg_ist_weg_und_wird_so_gemeldet(code):
    """AK 2: eine Stelle mit 410 meldet "existiert nicht mehr".

    Vorher fielen 404, 410, 403 und 500 alle auf denselben leeren
    String zusammen, und der Aufrufer riet daraus "Login-Wall oder
    Bot-Block".
    """
    befund = nachladen.beschreibung_holen(
        FREMDE_URL, _Client(_Antwort(status=code)))
    assert befund.status == nachladen.WEG
    assert befund.http_status == code
    assert befund.soll_aussortiert_werden is True
    assert "nicht mehr" in befund.klartext()
    assert "Bot-Block" not in befund.klartext()


@pytest.mark.parametrize("code", [401, 403, 429])
def test_1014_geblockt_ist_etwas_anderes_als_weg(code):
    befund = nachladen.beschreibung_holen(
        FREMDE_URL, _Client(_Antwort(status=code)))
    assert befund.status == nachladen.GEBLOCKT
    # Ein geblockter Zugriff sagt NICHTS darueber, ob die Anzeige noch
    # existiert — sie deshalb auszusortieren waere geraten (#989).
    assert befund.soll_aussortiert_werden is False


def test_1014_ein_serverfehler_sortiert_nichts_aus():
    """500 heisst "gerade nicht", nicht "gibt es nicht"."""
    befund = nachladen.beschreibung_holen(
        FREMDE_URL, _Client(_Antwort(status=500)))
    assert befund.status == nachladen.FEHLER
    assert befund.soll_aussortiert_werden is False


def test_1014_lebt_aber_unlesbar_ist_der_einzige_vermutungsfall():
    """AK 4: die drei Faelle sind unterscheidbar.

    Nur HIER ist "Login-Wall oder Bot-Block" eine zulaessige Vermutung —
    die Anzeige antwortet, gibt aber nichts her.
    """
    befund = nachladen.beschreibung_holen(
        FREMDE_URL, _Client(_Antwort(status=200, text="<html></html>")))
    assert befund.status == nachladen.LEBT_UNLESBAR
    assert befund.http_status == 200
    assert befund.soll_aussortiert_werden is False
    assert "Login-Wall" in befund.klartext()


def test_1014_alle_vier_befunde_sind_unterscheidbar():
    """AK 4 als Ganzes — vier Antworten, vier Befunde."""
    faelle = {
        410: nachladen.WEG,
        403: nachladen.GEBLOCKT,
        500: nachladen.FEHLER,
        200: nachladen.LEBT_UNLESBAR,
    }
    ergebnisse = {
        code: nachladen.beschreibung_holen(
            FREMDE_URL, _Client(_Antwort(status=code))).status
        for code in faelle
    }
    assert ergebnisse == faelle
    # ... und jeder traegt einen eigenen Klartext.
    texte = {nachladen.KLARTEXT[s] for s in faelle.values()}
    assert len(texte) == len(faelle)


# ------------------------------------- AK: die BA-Stelle liefert Text


def test_1014_eine_lebende_ba_stelle_geht_ueber_die_detail_api(monkeypatch):
    """AK 1: Anzeigentext statt 0 Zeichen.

    Gemessen vom Melder an derselben Stelle in derselben Sekunde:
    HTML-Scrape 0 Zeichen, Detail-API 3.460. Der Test stellt genau das
    nach — die HTML-Seite gibt nichts her, die API schon.
    """
    from bewerbungs_assistent.job_scraper import bundesagentur

    gerufen = {}

    def _falsche_api(client, ref_nr, status_raus=None):
        gerufen["refnr"] = ref_nr
        if status_raus is not None:
            status_raus.append(200)
        return "Vollstaendiger Anzeigentext aus der Detail-API. " * 40

    class _Sitzung:
        def __enter__(self):
            return object()

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(bundesagentur, "_fetch_ba_detail", _falsche_api)
    monkeypatch.setattr(bundesagentur, "api_session", lambda: _Sitzung())

    # Die HTML-Seite antwortet mit 200 und ohne Inhalt — wie die echte
    # Angular-Anwendung.
    client = _Client(_Antwort(status=200, text="<html><body></body></html>"))
    befund = nachladen.beschreibung_holen(BA_URL, client)

    assert befund.status == nachladen.GELESEN
    assert befund.quelle == "detail_api"
    assert len(befund.text) > 500
    assert gerufen["refnr"] == "14225-testref0000-S"
    # Der HTML-Weg wurde gar nicht erst gebraucht.
    assert client.aufrufe == 0


def test_1014_die_api_meldet_die_entfernte_anzeige_maschinenlesbar(monkeypatch):
    """Der belegte Fall des Melders: HTML 410, API 404.

    Beide sagen dasselbe. Vorher wurde beides weggeworfen.
    """
    from bewerbungs_assistent.job_scraper import bundesagentur

    def _weg(client, ref_nr, status_raus=None):
        if status_raus is not None:
            status_raus.append(404)
        return ""

    class _Sitzung:
        def __enter__(self):
            return object()

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(bundesagentur, "_fetch_ba_detail", _weg)
    monkeypatch.setattr(bundesagentur, "api_session", lambda: _Sitzung())

    befund = nachladen.beschreibung_holen(BA_URL, _Client(_Antwort(410)))
    assert befund.status == nachladen.WEG
    assert befund.quelle == "detail_api"
    assert befund.soll_aussortiert_werden is True


def test_1014_ohne_text_faellt_die_ba_stelle_auf_den_html_weg(monkeypatch):
    """Antwortet die API mit 200 aber ohne Text, darf HTML es versuchen.

    Umgekehrt waere es sinnlos — bei einer SPA liefert HTML nie etwas.
    """
    from bewerbungs_assistent.job_scraper import bundesagentur

    def _leer(client, ref_nr, status_raus=None):
        if status_raus is not None:
            status_raus.append(200)
        return ""

    class _Sitzung:
        def __enter__(self):
            return object()

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(bundesagentur, "_fetch_ba_detail", _leer)
    monkeypatch.setattr(bundesagentur, "api_session", lambda: _Sitzung())

    client = _Client(_Antwort(status=200, text="<html></html>"))
    befund = nachladen.beschreibung_holen(BA_URL, client)
    assert client.aufrufe == 1, "Der HTML-Rueckfall wurde nicht versucht."
    assert befund.status == nachladen.LEBT_UNLESBAR


# ------------------------------------------------- Ein Weg, vier Aufrufer


@pytest.mark.parametrize("datei,anker", [
    ("src/bewerbungs_assistent/tools/jobs.py", "nachladen.beschreibung_holen"),
    ("src/bewerbungs_assistent/dashboard.py", "nachladen.beschreibung_holen"),
])
def test_1014_die_nachlade_wege_gehen_durch_das_nadeloehr(datei, anker):
    """Der Melder nennt es ausdruecklich: ein Fix in der gemeinsamen
    Funktion trifft alle vier — vier einzelne waeren derselbe Fehler in
    vier Fassungen."""
    assert anker in (_repo() / datei).read_text(encoding="utf-8")


def test_1014_kein_nachlade_weg_raet_mehr_am_status_vorbei():
    """Der alte Satz darf in keinem der vier Wege mehr stehen.

    Er ist nicht falsch — er ist nur bloss eine VERMUTUNG und gehoert
    deshalb allein in den Fall `lebt_unlesbar`, wo der Dienst ihn
    formuliert.
    """
    for datei in ("src/bewerbungs_assistent/tools/jobs.py",
                  "src/bewerbungs_assistent/dashboard.py"):
        quelle = (_repo() / datei).read_text(encoding="utf-8")
        # Kommentarzeilen duerfen den Satz erklaeren (v1.7.50 MERKE 2).
        code = "\n".join(z for z in quelle.split("\n")
                         if not z.strip().startswith("#"))
        assert "Login-Wall oder Bot-Block" not in code, (
            f"{datei} raet weiter am Server-Status vorbei.")


def test_1014_der_status_geht_durch_die_ba_kette_hindurch():
    """Der Status wurde ZWEIMAL verworfen — auch im Retry-Helfer.

    Ohne den Durchgriff sah ein eindeutiges 404 der Detail-API genauso
    aus wie ein Timeout.
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "job_scraper"
              / "bundesagentur.py").read_text(encoding="utf-8")
    assert "letzter_status" in quelle
    assert "status_raus" in quelle
