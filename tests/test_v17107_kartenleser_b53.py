"""Tests fuer B53 (v1.7.107): Kartenleser fuer freelance.de und Praktikum.de.

Nachgemessen am 14.09.2026. freelance.de liefert je Stichwort-Seite 20
Projektkarten mit Firma, Ort, Start und Datum; der Adapter fiel auf
Kategorieseiten mit zwei Karten zurueck und lief an der Detailseite JEDES
Projekts in die Zeitgrenze. Praktikum.de hat den RSS-Feed entfernt; die
Suche laeuft ueber ein Formular mit Sitzung, die Detailseite traegt
schema.org-Microdata. Heise Jobs bleibt ausgegraut: die Treffer kommen nur
im Browser. Die Fixtures bilden die gemessene Struktur nach; alle Angaben
sind erfunden.
"""
import inspect
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY, freelance_de, praktikum_de, stelle_hash  # noqa: E402
from bewerbungs_assistent.job_scraper.health import _PROBES  # noqa: E402


class _Antwort:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


@pytest.fixture(autouse=True)
def ohne_pause(monkeypatch):
    monkeypatch.setattr(freelance_de, "PAUSE_S", 0)
    monkeypatch.setattr(praktikum_de, "PAUSE_S", 0)


# ====================================================== freelance.de

FREELANCE_SEITE = """<html><body>
<div class="list-item-content">
  <div class="avatar avatar-logo"><img class="media-object"></div>
  <div class="list-item-main">
    <h3 class="action-icons-overlap"><a href="/projekte/projekt-1000001-python-datenplattform">Python-Entwicklung Datenplattform (m/w/d)</a></h3>
    <div class="col-sm-8 no-padding-left">
      <span class="company-name">Firmenname: <a class="cta-primary" href="/firma/muster-it" title="Muster IT GmbH">Muster IT GmbH</a><br></span>
      <ul class="tags margin-top-sm"><li class="tag-primary"></li></ul>
      <p class="margin-top-xs size-sm"><span>Als EXPERT Projekt INSIGHTS abrufen. <a class="cta-primary" href="/expert/info">Mehr erfahren</a></span></p>
    </div>
    <div class="col-sm-4 no-padding-left overview">
      <ul class="icon-list">
        <li><i class="far fa-calendar-star fa-fw"></i> Ab September 2026</li>
        <li><i class="far fa-map-marker-alt fa-fw"></i> Musterstadt</li>
        <li><i class="far fa-laptop-house"></i> Remote</li>
        <li><i class="far fa-history fa-fw"></i> 12.09.2026 14:30</li>
      </ul>
    </div>
  </div>
</div>
<div class="list-item-content">
  <div class="list-item-main">
    <h3 class="action-icons-overlap"><a href="/projekte/projekt-1000002-testautomatisierung">Testautomatisierung (m/w/d)</a></h3>
    <div class="col-sm-8 no-padding-left">
      <span class="company-name">Firmenname: <a class="cta-primary" href="/firma/beispiel-systeme" title="Beispiel Systeme AG">Beispiel Systeme AG</a><br></span>
    </div>
    <div class="col-sm-4 no-padding-left overview">
      <ul class="icon-list">
        <li><i class="far fa-calendar-star fa-fw"></i> Ab Oktober 2026</li>
        <li><i class="far fa-map-marker-alt fa-fw"></i> Beispielhausen</li>
        <li><i class="far fa-history fa-fw"></i> 11.09.2026 09:00</li>
      </ul>
    </div>
  </div>
</div>
NAECHSTE
</body></html>"""

NAECHSTE = '<nav class="pagination"><a href="/Python-Projekte?_offset=20">2</a></nav>'
SEITE_2 = FREELANCE_SEITE.replace("1000001", "1000011").replace("1000002", "1000012").replace(
    "Python-Entwicklung Datenplattform", "Python-Backend Schnittstellen").replace(
    "Testautomatisierung (m/w/d)", "Testmanagement (m/w/d)").replace("NAECHSTE", "")


class _FreelanceClient:
    def __init__(self, seiten: dict):
        self.seiten = seiten
        self.abrufe = []

    def get(self, url, **_):
        self.abrufe.append(url)
        return self.seiten.get(url, _Antwort(410, ""))


def _freelance(monkeypatch, seiten=None, begriffe=("Python",), max_details=15):
    details: list = []
    monkeypatch.setattr(freelance_de, "fetch_description_from_detail",
                        lambda url, client: details.append(url) or "Aufgaben: Aufbau einer Datenplattform mit Python. " * 4)
    monkeypatch.setattr(freelance_de, "MAX_DETAILS", max_details)
    if seiten is None:
        seiten = {
            "https://www.freelance.de/Python-Projekte": _Antwort(200, FREELANCE_SEITE.replace("NAECHSTE", NAECHSTE)),
            "https://www.freelance.de/Python-Projekte?_offset=20": _Antwort(200, SEITE_2),
        }
    client = _FreelanceClient(seiten)
    stellen = freelance_de.search_freelance_de({"keywords": {"general": list(begriffe)}}, client=client)
    return stellen, client, details


def test_freelance_liest_titel_firma_ort_und_datum_aus_der_karte(monkeypatch):
    stellen, _, _ = _freelance(monkeypatch)
    erste = stellen[0]
    assert erste["title"] == "Python-Entwicklung Datenplattform (m/w/d)"
    assert erste["url"] == "https://www.freelance.de/projekte/projekt-1000001-python-datenplattform"
    assert erste["company"] == "Muster IT GmbH", "ohne das Etikett 'Firmenname:'"
    assert erste["location"] == "Musterstadt"
    assert erste["veroeffentlicht_am"] == "2026-09-12"
    assert "Start: Ab September 2026" in erste["description"]
    assert "INSIGHTS" not in erste["description"], "der Werbesatz ist kein Anzeigentext"
    assert all(s["employment_type"] == "freelance" and s["source"] == "freelance_de" for s in stellen)


def test_freelance_das_wort_remote_heisst_remote_moeglich(monkeypatch):
    """"remote" schaltet die Ortspruefung ab (#996)."""
    stellen, _, _ = _freelance(monkeypatch)
    assert stellen[0]["remote_level"] == "hybrid"
    assert stellen[1]["remote_level"] == "unbekannt"


def test_freelance_fragt_stichwort_seiten_und_blaettert_nur_bei_weiterem_link(monkeypatch):
    stellen, client, _ = _freelance(monkeypatch)
    assert client.abrufe == ["https://www.freelance.de/Python-Projekte",
                             "https://www.freelance.de/Python-Projekte?_offset=20"]
    assert len(stellen) == 4


def test_freelance_ohne_suchbegriffe_keine_kategorieseiten_mit_zwei_karten(monkeypatch):
    """Die alte Vorgabe waren Kategorieseiten mit je zwei Karten."""
    _, client, _ = _freelance(monkeypatch, seiten={}, begriffe=())
    assert client.abrufe and all(u.endswith("-Projekte") for u in client.abrufe)
    assert "Software-Engineering-Projekte" not in " ".join(client.abrufe)


def test_freelance_ein_unbekannter_begriff_kostet_nur_den_begriff(monkeypatch):
    seiten = {"https://www.freelance.de/Python-Projekte": _Antwort(200, FREELANCE_SEITE.replace("NAECHSTE", ""))}
    stellen, client, _ = _freelance(monkeypatch, seiten=seiten, begriffe=("Gibtsnicht", "Python"))
    assert len(stellen) == 2
    assert client.abrufe[0].endswith("/Gibtsnicht-Projekte")


def test_freelance_holt_detailseiten_nur_bis_zur_grenze(monkeypatch):
    """Meldefall: die Detailseite JEDES Projekts lief in die Zeitgrenze."""
    stellen, _, details = _freelance(monkeypatch, max_details=1)
    assert len(details) == 1
    assert "Aufgaben: Aufbau einer Datenplattform" in stellen[0]["description"]
    assert "Start: Ab September 2026" in stellen[0]["description"], "die Kartenangaben bleiben stehen"
    assert "Aufgaben" not in stellen[1]["description"]


def test_freelance_d_remote_ist_kein_ort():
    """Gemessen: "D-Remote" steht im Ortsfeld. Geocodet ergaebe das nichts,
    und ein falscher Ort ist schlimmer als ein fehlender (#989)."""
    html = FREELANCE_SEITE.replace("Musterstadt", "D-Remote").replace(
        '<li><i class="far fa-laptop-house"></i> Remote</li>', "").replace("NAECHSTE", "")
    stellen = freelance_de._parse_listing_page(html, set())
    assert stellen[0]["location"] == ""
    assert stellen[0]["remote_level"] == "remote"
    assert "Ort:" not in stellen[0]["description"]
    assert "Arbeitsmodell: remote" in stellen[0]["description"]
    assert stellen[1]["location"] == "Beispielhausen", "ein echter Ort bleibt"


def test_freelance_kennung_bleibt_titelbasiert(monkeypatch):
    stellen, _, _ = _freelance(monkeypatch)
    assert stellen[0]["hash"] == stelle_hash("freelance.de", "Python-Entwicklung Datenplattform (m/w/d)")


# ====================================================== Praktikum.de

def _karte(nr: int, titel: str, ort: str, beginn: str) -> str:
    return f"""<div class="row"><div class="col-md-9 col-sm-8 col-xs-12">
  <div class="row"><h5><a href="/angebote/angebot-muster_{nr}.html"><b>{titel}</b></a></h5></div>
  <div class="row sm-margin-bottom-20">
    <div class="col-md-6 no-left-space"><i class="fa fa-building-o grau"></i><span class="grau">Branche: </span><a href="/branche/medien">Medien</a></div>
    <div class="col-md-3 no-left-space"><i class="fa fa-map-marker grau"></i><span class="grau"><span class="hidden-md hidden-sm hidden-lg"></span>Ort: </span><a href="/ort/x">{ort}</a></div>
    <div class="col-md-3 no-left-space"><i class="fa fa-clock-o grau"></i><span class="grau">Beginn: </span><a href="/beginn/x">{beginn}</a></div>
    <div class="col-md-12 no-left-space margin-top-1rem">Du unterstuetzt unser Team bei Kampagnen und Auswertungen.</div>
    <div class="col-md-12 no-left-space margin-top-1rem"><a href="/angebote/angebot-muster_{nr}.html"><button class="btn btn-primary btn-sm"><b>Zum Praktikum</b></button></a></div>
  </div>
</div></div>"""


PRAKTIKUM_SEITE_1 = ("<html><body>" + _karte(1001, "Praktikum Marketing (m/w/d)", "Musterstadt", "01.10.2026")
                     + _karte(1002, "Werkstudent Datenanalyse (m/w/d)", "Beispielhausen", "ab sofort")
                     + '<a href="/detailsuche/ergebnisse,seite-2.html">2</a></body></html>')
PRAKTIKUM_SEITE_2 = "<html><body>" + _karte(1003, "Praktikum Vertrieb (m/w/d)", "Musterstadt", "01.11.2026") + "</body></html>"
PRAKTIKUM_DETAIL = """<html><body>
<div class="row" itemscope itemtype="http://schema.org/JobPosting">
  <span itemprop="title">Praktikum Marketing (m/w/d)</span>
  <meta itemprop="datePosted" content="2026-09-10">
  <div itemprop="hiringOrganization" itemscope itemtype="http://schema.org/Organization">
    <span itemprop="name">Muster Medien GmbH</span>
    <span itemprop="description">Wir sind eine Agentur fuer Kommunikation.</span>
  </div>
  <div itemprop="jobLocation" itemscope itemtype="http://schema.org/Place">
    <div itemprop="address" itemscope itemtype="http://schema.org/PostalAddress">
      <span itemprop="postalCode">12345</span><span itemprop="addressLocality">Musterstadt</span>
    </div>
  </div>
  <div itemprop="description">Aufgaben: Planung von Kampagnen, Auswertung von Kennzahlen, Pflege der Kanaele. Profil: Studium im Bereich Kommunikation oder Wirtschaft, sicherer Umgang mit Tabellen, Freude an Texten.</div>
</div></body></html>"""


class _PraktikumClient:
    """Die Sitzung merkt sich das abgeschickte Formular — ohne es liefert eine
    Ergebnisseite nichts, wie auf der echten Seite."""

    def __init__(self, seiten: dict, details: dict | None = None, status: dict | None = None):
        self.seiten = seiten
        self.details = details or {}
        self.status = status or {}
        self.formular = None
        self.anfragen = []

    def _seite(self, nr: int):
        if self.status.get(nr):
            return _Antwort(self.status[nr], "")
        if self.formular is None:
            return _Antwort(200, "<html></html>")
        return _Antwort(200, self.seiten.get(nr, "<html></html>"))

    def get(self, url, **_):
        self.anfragen.append(("GET", url))
        if url in self.details:
            return _Antwort(200, self.details[url])
        if "ergebnisse,seite-" in url:
            return self._seite(int(url.split("seite-")[1].split(".")[0]))
        return _Antwort(200, "<html></html>")

    def post(self, url, data=None, **_):
        self.anfragen.append(("POST", url))
        self.formular = dict(data or {})
        return self._seite(1)


def _praktikum(monkeypatch, max_details=10, status=None, begriffe=("Marketing",)):
    monkeypatch.setattr(praktikum_de, "MAX_DETAILS", max_details)
    client = _PraktikumClient(
        {1: PRAKTIKUM_SEITE_1, 2: PRAKTIKUM_SEITE_2},
        {"https://www.praktikum.de/angebote/angebot-muster_1001.html": PRAKTIKUM_DETAIL},
        status,
    )
    stellen = praktikum_de.search_praktikum_de({"keywords": {"general": list(begriffe)}}, client=client)
    return stellen, client


def test_praktikum_sucht_ueber_das_formular_und_blaettert_in_der_sitzung(monkeypatch):
    """Ein GET ohne Formular liefert keine Treffer — erst POST, dann Seite 2."""
    _, client = _praktikum(monkeypatch)
    such = [a for a in client.anfragen if "ergebnisse" in a[1]]
    assert such[0] == ("POST", praktikum_de.SUCHE.format(seite=1))
    assert such[1] == ("GET", praktikum_de.SUCHE.format(seite=2))
    assert len(such) == 2, "ohne Link auf Seite 3 wird nicht weitergeblaettert"
    assert client.formular["schnellsuche"] == "1" and client.formular["branche"] == "0"


def test_praktikum_fragt_die_ganze_boerse_einmal_statt_je_begriff(monkeypatch):
    """Gemessen: 24 Angebote insgesamt; "IT" lieferte alle, und ein Lauf je
    Begriff fragte dieselben Seiten ab, bis die Seite mit 429 antwortete."""
    _, client = _praktikum(monkeypatch, begriffe=("Marketing", "Informatik", "IT"))
    assert [a for a in client.anfragen if a[0] == "POST"] == [("POST", praktikum_de.SUCHE.format(seite=1))]
    assert client.formular["stichwort"] == ""


def test_praktikum_anfragegrenze_beendet_den_lauf_mit_dem_bisherigen(monkeypatch):
    stellen, client = _praktikum(monkeypatch, status={2: 429})
    assert len(stellen) == 2, "die Karten von Seite 1 bleiben"
    assert not [a for a in client.anfragen if "/angebote/" in a[1]], "nach 429 keine Detailseiten mehr"


def test_praktikum_liest_die_karte(monkeypatch):
    stellen, _ = _praktikum(monkeypatch, max_details=0)
    assert [s["title"] for s in stellen] == ["Praktikum Marketing (m/w/d)", "Werkstudent Datenanalyse (m/w/d)",
                                             "Praktikum Vertrieb (m/w/d)"]
    erste, zweite, _ = stellen
    assert erste["url"] == "https://www.praktikum.de/angebote/angebot-muster_1001.html"
    assert erste["location"] == "Musterstadt"
    assert "Kampagnen" in erste["description"] and "Branche: Medien" in erste["description"]
    assert "Beginn: 01.10.2026" in erste["description"]
    assert "Zum Praktikum" not in erste["description"]
    assert erste["company"] == "Nicht angegeben", "die Branche ist keine Firma"
    assert erste["employment_type"] == "praktikum" and zweite["employment_type"] == "werkstudent"


def test_praktikum_detailseite_liefert_firma_text_und_datum(monkeypatch):
    stellen, _ = _praktikum(monkeypatch)
    erste = stellen[0]
    assert erste["company"] == "Muster Medien GmbH"
    assert erste["description"].startswith("Aufgaben: Planung von Kampagnen")
    assert "Agentur fuer Kommunikation" not in erste["description"], \
        "die Beschreibung der Firma ist nicht die der Stelle"
    assert erste["veroeffentlicht_am"] == "2026-09-10"


def test_praktikum_holt_detailseiten_nur_bis_zur_grenze(monkeypatch):
    _, client = _praktikum(monkeypatch, max_details=1)
    detail_abrufe = [a for a in client.anfragen if "/angebote/" in a[1]]
    assert len(detail_abrufe) == 1


def test_praktikum_kennung_aus_adresse_und_titel(monkeypatch):
    stellen, _ = _praktikum(monkeypatch, max_details=0)
    assert stellen[0]["hash"] == stelle_hash(
        "praktikum_de", "https://www.praktikum.de/angebote/angebot-muster_1001.html Praktikum Marketing (m/w/d)")


# ====================================================== Registry, Probe, Guards


@pytest.mark.parametrize("quelle", ["freelance_de", "praktikum_de"])
def test_wieder_nutzbar(quelle):
    meta = SOURCE_REGISTRY[quelle]
    assert not meta.get("defekt"), quelle
    assert not meta.get("deprecated"), quelle


def test_heise_bleibt_ausgegraut_mit_berichtigtem_befund():
    """v1.7.106 nannte "rund 60 Stellenkarten" — es waren Linklisten."""
    meta = SOURCE_REGISTRY["heise_jobs"]
    assert meta.get("defekt") is True
    grund = meta.get("defekt_grund") or ""
    assert "Chrome" in grund and "Linklisten" in grund
    assert "Stellenkarten im HTML" not in grund
    assert "/search?q=" in (meta.get("manueller_fallback") or "")


def test_freelance_probe_fragt_eine_stichwort_seite():
    methode, url, typ, _ = _PROBES["freelance_de"]
    assert methode == "GET" and typ == "html"
    assert url.startswith(freelance_de.BASIS) and url.endswith("-Projekte")


def test_die_toten_wege_sind_weg():
    assert "rss.xml" not in inspect.getsource(praktikum_de)
    assert "Software-Engineering-Projekte" not in inspect.getsource(freelance_de)
