"""Tests fuer B53 (v1.7.106): zwei defekte Quellen liefern wieder.

Nutzerauftrag vom 14.09.2026: die sieben als defekt gefuehrten Quellen
neu vermessen — was sich abgreifen laesst, zurueckholen, den Rest
begruendet ausgegraut lassen. GULP und Workable haben beide eine offene
Such-Schnittstelle, die der Adapter nie angesprochen hat. Die Fixtures
bilden die am 14.09. gemessene Struktur nach; alle Angaben sind erfunden.
"""
import inspect
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY, gulp, stelle_hash, workable  # noqa: E402
from bewerbungs_assistent.job_scraper.health import _PROBES  # noqa: E402


class _Antwort:
    def __init__(self, status_code, daten):
        self.status_code = status_code
        self._daten = daten

    def json(self):
        return self._daten


@pytest.fixture(autouse=True)
def ohne_pause(monkeypatch):
    monkeypatch.setattr(gulp, "PAUSE_S", 0)
    monkeypatch.setattr(workable, "PAUSE_S", 0)


# ====================================================== GULP

GULP_SEITE_0 = {"totalCount": 3, "projects": [
    {"id": "C0000001", "type": "AGENCY",
     "title": "Python-Entwicklung Datenmigration (m/w/d)", "location": "Musterstadt",
     "description": "Aufbau von Migrationsskripten mit <mark>Python</mark> &amp; SQL",
     "companyName": None,
     "url": "https://www.gulp.de/gulp2/g/projekte/agentur/C0000001",
     "originalPublicationDate": "2026-09-11T16:30:05.192",
     "skills": ["Python und SQL", "Erfahrung mit Datenbanken"],
     "isRemoteWorkPossible": True},
    {"id": "abc0000002", "type": "TALENT_FINDER",
     "title": "Data Engineer (m/w/d)", "location": "Beispielhausen",
     "description": "Datenpipelines und Datenprodukte", "companyName": "Muster Consulting GmbH",
     "url": "https://www.gulp.de/gulp2/g/projekte/talentfinder/abc0000002",
     "originalPublicationDate": "2026-09-10T09:00:00", "skills": [],
     "isRemoteWorkPossible": False},
]}
GULP_SEITE_1 = {"totalCount": 3, "projects": [
    {"id": "C0000003", "type": "DIREKT", "title": "Testautomatisierung (m/w/d)",
     "location": "Musterstadt", "description": "Aufbau einer Testumgebung",
     "companyName": "Beispiel Systemhaus AG",
     "url": "https://www.gulp.de/gulp2/g/projekte/direkt/C0000003",
     "originalPublicationDate": "2026-09-09T08:00:00", "skills": ["Erfahrung mit Testwerkzeugen"],
     "isRemoteWorkPossible": False},
]}


class _GulpClient:
    def __init__(self, seiten, status=None):
        self.seiten = seiten
        self.status = status or {}
        self.anfragen = []

    def post(self, url, json=None, **_):
        self.anfragen.append((url, json["query"], json["page"]))
        return _Antwort(self.status.get(json["query"], 200),
                        self.seiten.get((json["query"], json["page"]),
                                        {"totalCount": 0, "projects": []}))


def _gulp(begriffe=("Python",), status=None):
    seiten = {}
    for b in begriffe:
        seiten[(b, 0)] = GULP_SEITE_0
        seiten[(b, 1)] = GULP_SEITE_1
    client = _GulpClient(seiten, status)
    return gulp.search_gulp({"keywords": {"general": list(begriffe)}}, client=client), client


def test_gulp_liest_projekte_mit_firma_ort_text_und_link():
    stellen, _ = _gulp()
    assert len(stellen) == 3
    erste, zweite, _dritte = stellen
    assert erste["title"] == "Python-Entwicklung Datenmigration (m/w/d)"
    assert erste["location"] == "Musterstadt"
    assert erste["url"].endswith("/C0000001")
    assert zweite["company"] == "Muster Consulting GmbH"
    assert "Python & SQL" in erste["description"]
    assert "<mark>" not in erste["description"] and "&amp;" not in erste["description"]
    assert "Erfahrung mit Datenbanken" in erste["description"], "die Anforderungen gehoeren in den Text"
    assert erste["veroeffentlicht_am"] == "2026-09-11"
    assert all(s["employment_type"] == "freelance" and s["source"] == "gulp" for s in stellen)


def test_gulp_vermittlungsprojekte_sind_nicht_alle_dieselbe_firma():
    """Ohne Auftraggeber "GULP" einzusetzen machte jedes Vermittlungsprojekt
    zu derselben Firma — fuer Wiedergaenger und Blacklist falsch (#1028)."""
    stellen, _ = _gulp()
    assert stellen[0]["company"] == "Nicht angegeben"


def test_gulp_blaettert_bis_zur_gesamtzahl_und_nicht_weiter():
    _, client = _gulp()
    assert [a[2] for a in client.anfragen] == [0, 1]
    assert all(a[0] == gulp.SUCHE for a in client.anfragen)


def test_gulp_remote_moeglich_ist_nicht_vollstaendig_remote():
    """"remote" schaltet die Ortspruefung ab (#996) — "moeglich" reicht dafuer nicht."""
    stellen, _ = _gulp()
    assert stellen[0]["remote_level"] == "hybrid"
    assert stellen[1]["remote_level"] == "unbekannt"


def test_gulp_ein_projekt_ueber_zwei_suchbegriffe_zaehlt_einmal():
    stellen, _ = _gulp(("Python", "SQL"))
    assert len(stellen) == 3


def test_gulp_ein_fehler_kostet_nur_den_einen_begriff():
    stellen, _ = _gulp(("Python", "SQL"), status={"Python": 500})
    assert len(stellen) == 3


def test_gulp_kennung_bleibt_titelbasiert():
    """Eine Kennung ist ein Vertrag mit dem Bestand (B50, #1041)."""
    stellen, _ = _gulp()
    assert stellen[0]["hash"] == stelle_hash("gulp.de", "Python-Entwicklung Datenmigration (m/w/d)")


# ====================================================== Workable

WORKABLE_SEITE_1 = {"totalSize": 3, "nextPageToken": "tok2", "jobs": [
    {"id": "11111111-aaaa", "title": "Backend Engineer (m/w/d)",
     "company": {"title": "Muster Software GmbH"},
     "location": {"city": "Musterstadt", "countryName": "Germany", "subregion": "Musterland"},
     "description": "<p>Wir suchen Unterstuetzung im Backend.</p>",
     "requirementsSection": "<ul><li>Python</li></ul>",
     "benefitsSection": "<p>Homeoffice nach Absprache</p>",
     "employmentType": "Full-time", "workplace": "hybrid",
     "created": "2026-09-12T08:00:00.000Z", "url": "https://jobs.workable.com/view/aaaa"},
    {"id": "22222222-bbbb", "title": "Praktikum Marketing",
     "company": {"title": "Beispiel Handel AG"},
     "location": {"city": "Beispielhausen", "countryName": "Germany"},
     "description": "<p>Praktikum im Marketing</p>",
     "employmentType": "Internship", "workplace": "on_site",
     "created": "2026-09-11T08:00:00Z", "url": "https://jobs.workable.com/view/bbbb"},
]}
WORKABLE_SEITE_2 = {"totalSize": 3, "nextPageToken": None, "jobs": [
    {"id": "33333333-cccc", "title": "DevOps Engineer",
     "company": {"title": "Muster Cloud GmbH"},
     "location": {"city": "", "countryName": "Germany"},
     "description": "<p>Aufbau der Plattform</p>",
     "employmentType": "Part-time", "workplace": "remote",
     "created": "2026-09-10", "url": "https://jobs.workable.com/view/cccc"},
]}


class _WorkableClient:
    def __init__(self, seiten, status=200):
        self.seiten = seiten
        self.status = status
        self.anfragen = []

    def get(self, url, params=None, **_):
        p = dict(params or {})
        self.anfragen.append((url, p))
        return _Antwort(self.status, self.seiten.get((p.get("query"), p.get("pageToken")),
                                                     {"jobs": [], "nextPageToken": None}))


def _workable():
    client = _WorkableClient({("Python", None): WORKABLE_SEITE_1, ("Python", "tok2"): WORKABLE_SEITE_2})
    return workable.search_workable({"keywords": {"general": ["Python"]}}, client=client), client


def test_workable_liest_stellen_mit_firma_ort_und_vollem_text():
    stellen, _ = _workable()
    assert [s["title"] for s in stellen] == ["Backend Engineer (m/w/d)", "Praktikum Marketing", "DevOps Engineer"]
    backend, praktikum, devops = stellen
    assert backend["company"] == "Muster Software GmbH"
    assert backend["location"] == "Musterstadt"
    assert "Python" in backend["description"] and "Homeoffice" in backend["description"]
    assert "<" not in backend["description"]
    assert backend["url"] == "https://jobs.workable.com/view/aaaa"
    assert backend["veroeffentlicht_am"] == "2026-09-12"
    assert backend["employment_type"] == "festanstellung" and backend["arbeitsumfang"] == "vollzeit"
    assert praktikum["employment_type"] == "praktikum"
    assert devops["arbeitsumfang"] == "teilzeit"


def test_workable_uebernimmt_das_arbeitsmodell_der_quelle():
    """"Homeoffice nach Absprache" unter den Vorteilen ist kein Remote-Arbeitsplatz."""
    stellen, _ = _workable()
    assert [s["remote_level"] for s in stellen] == ["hybrid", "vor_ort", "remote"]


def test_workable_ohne_stadt_bleibt_der_ort_leer():
    """Ein blosses "Germany" waere eine erfundene Entfernung (#989)."""
    stellen, _ = _workable()
    assert stellen[2]["location"] == ""


def test_workable_blaettert_ueber_den_seiten_token():
    _, client = _workable()
    assert [p.get("pageToken") for _, p in client.anfragen] == [None, "tok2"]
    assert all(url == workable.SUCHE and p["location"] == "Germany" for url, p in client.anfragen)


def test_workable_firmen_bleiben_wirksam_als_suchbegriff():
    """#811: `workable_firmen` darf durch den Umbau nicht still wirkungslos werden."""
    client = _WorkableClient({("Muster Software", None): {"jobs": WORKABLE_SEITE_1["jobs"][:1],
                                                          "nextPageToken": None}})
    stellen = workable.search_workable(
        {"keywords": {"general": [], "workable_firmen": ["Muster Software"]}}, client=client)
    assert [p["query"] for _, p in client.anfragen] == ["Muster Software"]
    assert len(stellen) == 1


def test_workable_eine_stelle_ueber_zwei_begriffe_zaehlt_einmal():
    seite = {"jobs": WORKABLE_SEITE_1["jobs"], "nextPageToken": None}
    client = _WorkableClient({("Python", None): seite, ("Backend", None): seite})
    stellen = workable.search_workable({"keywords": {"general": ["Python", "Backend"]}}, client=client)
    assert len(stellen) == 2


def test_workable_ein_ausfall_liefert_leer_statt_absturz():
    client = _WorkableClient({}, status=503)
    assert workable.search_workable({"keywords": {"general": ["Python"]}}, client=client) == []


# ====================================================== Registry und Proben


@pytest.mark.parametrize("quelle", ["gulp", "workable"])
def test_wieder_nutzbar_und_nicht_mehr_ausgegraut(quelle):
    meta = SOURCE_REGISTRY[quelle]
    assert not meta.get("defekt"), quelle
    assert not meta.get("deprecated"), quelle


@pytest.mark.parametrize("quelle", ["freelance_de", "heise_jobs", "meinestadt", "praktikum_de", "workday_dax"])
def test_ausgegraut_mit_dem_befund_der_neuen_messung(quelle):
    """Was nicht liefert, bleibt ausgegraut — mit Messdatum, damit die Frage
    spaeter wieder pruefbar ist."""
    meta = SOURCE_REGISTRY[quelle]
    assert meta.get("defekt") is True, quelle
    assert "14.09.2026" in (meta.get("defekt_grund") or ""), quelle


def test_meinestadt_nennt_den_funktionierenden_browser_weg():
    assert "Chrome" in SOURCE_REGISTRY["meinestadt"]["defekt_grund"]


def test_probe_und_adapter_fragen_denselben_endpunkt():
    """#748: sonst prueft der Health-Check etwas anderes als die Suche."""
    methode, url, typ, body = _PROBES["gulp"]
    assert (methode, url, typ) == ("POST", gulp.SUCHE, "json")
    assert "query" in body
    methode, url, typ, _ = _PROBES["workable"]
    assert methode == "GET" and url.startswith(workable.SUCHE) and typ == "json"


def test_die_toten_wege_sind_weg():
    quelle_gulp = inspect.getsource(gulp)
    for tot in ("gulp2/api/projekte", "api.gulp.de", "sync_playwright"):
        assert tot not in quelle_gulp, tot
    assert "widget/accounts" not in inspect.getsource(workable)
