"""Tests fuer #1041 (B51, Jobware) und #1042 (B52, ingenieur.de).

Beide Boersen laufen auf derselben Plattform und hatten zwei Fassungen
desselben Fehlers: eine Auswahl, die auch die Bestandteile der Karten
trifft, Firma und Ort ueber Klassennamen, die es nicht gibt, ein
verstecktes "in" vor dem Ort, bei Jobware der Titel aus dem Knopf "Job
ansehen" und ein Kartenweg nur fuer den ersten Suchbegriff. Die Fixtures
bilden die am 14.09.2026 gemessene Struktur nach; alle Angaben sind
erfunden.
"""
import inspect
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.job_scraper import ingenieur_de, jobboerse_karten, jobware  # noqa: E402

FIXTURES = _repo() / "tests" / "fixtures" / "scrapers"


def _seite(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class _Antwort:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


class _Client:
    """Antwortet je Suchbegriff mit einer Seite; zaehlt die Abrufe."""

    def __init__(self, seiten: dict, abrufe: list):
        self._seiten = seiten
        self._abrufe = abrufe

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get(self, url, params=None, **_):
        begriff = (params or {}).get("q", "")
        self._abrufe.append(begriff)
        if begriff in self._seiten:
            # Jobware verlangt eine Seite ueber 10 KB, sonst gilt sie als SPA.
            return _Antwort(200, self._seiten[begriff] + "<!--" + "x" * 12000 + "-->")
        return _Antwort(404, "")


@pytest.fixture
def ohne_netz(monkeypatch):
    def _setzen(modul, seiten: dict) -> list:
        abrufe: list = []
        monkeypatch.setattr(modul.httpx, "Client", lambda *a, **k: _Client(seiten, abrufe))
        monkeypatch.setattr(modul.time, "sleep", lambda *_a, **_k: None)
        return abrufe
    return _setzen


# ====================================================== der Kartenleser


@pytest.mark.parametrize("fixture, basis, erste", [
    ("jobware_ergebnis.html", "https://www.jobware.de",
     {"titel": "Sachbearbeitung Einkauf (m/w/d)", "firma": "Muster Handelsgesellschaft mbH",
      "ort": "Musterstadt"}),
    ("ingenieur_de_ergebnis.html", "https://jobs.ingenieur.de",
     {"titel": "Konstruktion Sondermaschinenbau (gn)", "firma": "Muster Maschinenbau GmbH",
      "ort": "Musterstadt"}),
])
def test_der_kartenleser_liest_titel_firma_und_ort(fixture, basis, erste):
    karten = jobboerse_karten.karten_aus_html(_seite(fixture), basis)
    assert len(karten) == 2, karten
    for feld, wert in erste.items():
        assert karten[0][feld] == wert, (feld, karten[0])
    assert karten[0]["url"].startswith(basis + "/job/")


def test_das_versteckte_in_steht_nicht_im_ort():
    """Meldefall: `inBerlin` — dafuer findet PBP keine Koordinaten."""
    for fixture, basis in (("jobware_ergebnis.html", "https://www.jobware.de"),
                           ("ingenieur_de_ergebnis.html", "https://jobs.ingenieur.de")):
        for karte in jobboerse_karten.karten_aus_html(_seite(fixture), basis):
            assert not karte["ort"].lower().startswith("in"), karte


def test_der_titel_kommt_nicht_aus_dem_knopf():
    """Meldefall Jobware: `Job"<Titel>"ansehen`."""
    for karte in jobboerse_karten.karten_aus_html(_seite("jobware_ergebnis.html"),
                                                   "https://www.jobware.de"):
        assert not karte["titel"].startswith("Job"), karte
        assert "ansehen" not in karte["titel"], karte


def test_eine_karte_ist_die_karte_nicht_ihr_bestandteil():
    """Die Bestandteile tragen `job-card__...` im Klassennamen — gezaehlt
    wird nur das Element mit der Klasse `job-card` selbst."""
    html = _seite("ingenieur_de_ergebnis.html")
    assert html.count("job-card__") > 2
    assert len(jobboerse_karten.karten_aus_html(html, "https://jobs.ingenieur.de")) == 2


def test_ein_bestandteil_ausserhalb_einer_karte_ist_keine_stelle():
    """Gegenprobe v1.7.104: innerhalb einer Karte faengt der URL-Abgleich
    jeden Bestandteil ab — die Auswahl entscheidet erst bei einem Element
    `job-card__...` AUSSERHALB einer Karte. Ein Teilstring-Selektor haette
    daraus eine Stelle gemacht."""
    html = (
        '<div class="job-card__teaser"><h2 class="headline">Anzeige schalten</h2>'
        '<a href="/job/werbeplatz-900000001">Mehr</a></div>'
        '<div class="job-card"><h2 class="headline">Sachbearbeitung Einkauf (m/w/d)</h2>'
        '<a href="/job/sachbearbeitung-einkauf-900000002">ansehen</a>'
        '<span class="job-card__advertiser-name">Musterfirma GmbH</span>'
        '<span class="job-card__location"><span class="nrmdy-visually-hidden">in</span>Musterstadt</span>'
        '</div>')
    karten = jobboerse_karten.karten_aus_html(html, "https://www.jobware.de")
    assert [k["titel"] for k in karten] == ["Sachbearbeitung Einkauf (m/w/d)"], karten


def test_eine_anzeige_zweimal_auf_der_seite_zaehlt_einmal():
    html = _seite("jobware_ergebnis.html")
    doppelt = html.replace("</body>", html[html.index('<div class="job-card'):html.index("</div>\n\n  <div class=\"job-card", 10) + 6] + "</body>")
    karten = jobboerse_karten.karten_aus_html(doppelt, "https://www.jobware.de")
    assert len({k["url"] for k in karten}) == len(karten)


# ====================================================== Jobware


def test_jobware_liefert_jede_karte_mit_firma_und_ort(ohne_netz):
    ohne_netz(jobware, {"Einkauf": _seite("jobware_ergebnis.html")})
    stellen = jobware.search_jobware({"keywords": {"general": ["Einkauf"]}})
    assert len(stellen) == 2, stellen
    assert all(s["company"] != "Unbekannt" and s["location"] for s in stellen), stellen
    assert stellen[0]["title"] == "Sachbearbeitung Einkauf (m/w/d)"


def test_jobware_wertet_jeden_suchbegriff_aus(ohne_netz):
    """Meldefall: 1-2 Stellen je Lauf; die Karten liefen nur beim ersten Begriff."""
    zweite = _seite("jobware_ergebnis.html").replace("100000001", "100000011").replace(
        "100000002", "100000012")
    abrufe = ohne_netz(jobware, {"Einkauf": _seite("jobware_ergebnis.html"), "Buchhaltung": zweite})
    stellen = jobware.search_jobware({"keywords": {"general": ["Einkauf", "Buchhaltung"]}})
    assert "Buchhaltung" in abrufe
    assert len(stellen) == 4, [s["url"] for s in stellen]


def test_jobware_behaelt_die_kennung_des_alten_kartenwegs(ohne_netz):
    """Mit korrigiertem Titel haette sich die Kennung geaendert — der Neufund
    waere als Duplikat des kaputten Eintrags aussortiert worden, und der
    kaputte bliebe aktiv (#1041). Die Eingabe bleibt der alte Knopftext."""
    ohne_netz(jobware, {"Einkauf": _seite("jobware_ergebnis.html")})
    stelle = jobware.search_jobware({"keywords": {"general": ["Einkauf"]}})[0]
    from bewerbungs_assistent.job_scraper import stelle_hash
    assert stelle["hash"] == stelle_hash("jobware.de", 'Job"Sachbearbeitung Einkauf (m/w/d)"ansehen')
    assert stelle["title"] == "Sachbearbeitung Einkauf (m/w/d)"


# ====================================================== ingenieur.de


def test_ingenieur_de_liefert_jede_stelle_einmal_mit_firma_und_ort(ohne_netz, monkeypatch):
    abgerufen: list = []
    monkeypatch.setattr(ingenieur_de, "fetch_description_from_detail",
                        lambda url, client: abgerufen.append(url) or "Aufgaben und Profil.")
    ohne_netz(ingenieur_de, {"Konstruktion": _seite("ingenieur_de_ergebnis.html"),
                             "Anlagenbau": _seite("ingenieur_de_ergebnis.html")})
    stellen = ingenieur_de.search_ingenieur_de({"keywords": {"general": ["Konstruktion", "Anlagenbau"]}})
    urls = [s["url"] for s in stellen]
    assert len(urls) == len(set(urls)) == 2, urls
    assert all(s["company"] != "Unbekannt" and s["location"] for s in stellen), stellen


def test_ingenieur_de_holt_jede_detailseite_nur_einmal(ohne_netz, monkeypatch):
    """Meldefall: jede Kopie holte die Detailseite erneut."""
    abgerufen: list = []
    monkeypatch.setattr(ingenieur_de, "fetch_description_from_detail",
                        lambda url, client: abgerufen.append(url) or "Aufgaben und Profil.")
    ohne_netz(ingenieur_de, {"Konstruktion": _seite("ingenieur_de_ergebnis.html"),
                             "Anlagenbau": _seite("ingenieur_de_ergebnis.html")})
    ingenieur_de.search_ingenieur_de({"keywords": {"general": ["Konstruktion", "Anlagenbau"]}})
    assert len(abgerufen) == len(set(abgerufen)) == 2, abgerufen


def test_ingenieur_de_kennung_bleibt(ohne_netz, monkeypatch):
    """Der Titel stimmte schon — die Kennung aendert sich nicht, und ein
    Wiederfund fuellt Firma und Ort der gespeicherten Zeile."""
    monkeypatch.setattr(ingenieur_de, "fetch_description_from_detail", lambda url, client: "")
    ohne_netz(ingenieur_de, {"Konstruktion": _seite("ingenieur_de_ergebnis.html")})
    stelle = ingenieur_de.search_ingenieur_de({"keywords": {"general": ["Konstruktion"]}})[0]
    from bewerbungs_assistent.job_scraper import stelle_hash
    assert stelle["hash"] == stelle_hash("ingenieur.de", "Konstruktion Sondermaschinenbau (gn)")


# ====================================================== Guard


def test_keine_der_beiden_boersen_waehlt_karten_ueber_den_teilstring():
    """`[class*='job-card']` trifft jeden Bestandteil einer Karte."""
    for modul in (jobware, ingenieur_de):
        quelle = inspect.getsource(modul)
        assert "[class*='job-card']" not in quelle, modul.__name__
        assert "karten_aus_html(" in quelle, modul.__name__
