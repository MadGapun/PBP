"""#1159 — python-jobspy 1.2.0 übernehmen.

Am 02.10.2026 erschien python-jobspy 1.2.0. PBP verlangte nur `>=1.1`; Neuinstallationen bekamen damit
die neue Fassung, bestehende blieben auf 1.1.x, und PBP war nur gegen 1.1.82 beschrieben. Geprüft
(sauber installiert auf Python 3.12 mit pandas 3 und numpy 2, und in der Entwicklungsumgebung mit
Python 3.13): dieselben 34 Spalten, dieselben Parameter, eine echte Abfrage liefert dieselben Stellen.
Drei Dinge mussten angepasst werden:

1. Die Mindestversion steigt auf 1.2, damit auch bestehende Installationen aktualisieren.
2. Gehälter: 1.2.0 liefert sie jetzt auch für deutsche Anzeigen (gemessen: 2 von 15, `yearly`, `EUR`) -
   mit Intervall und Währung. PBP las `min_amount`/`max_amount` ungeprüft als Jahreswert; ein Stundenlohn
   von 15 wäre als Jahresgehalt gespeichert worden.
3. 1.2.0 wirft bei einem ausgefallenen Board nicht mehr, es loggt nur. Ohne Gegenmaßnahme wäre eine
   gesperrte Seite für PBP „ok, 0 Treffer“ (das falsche Grün aus #808), und die Fehlerserie, die eine
   tote Quelle abschaltet, käme nie zusammen.

Alle Firmen, Orte und Namen in den Testdaten sind Platzhalter. Kein Test geht ins Netz.
"""
import inspect
import logging
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.job_scraper import jobspy_source as js  # noqa: E402


# ══ Die Mindestversion ═════════════════════════════════════════════════════════

def _versionen_in(text: str) -> list:
    return re.findall(r"python-jobspy>=([0-9][0-9.]*)", text)


def test_1159_pyproject_und_installer_verlangen_dasselbe_und_mindestens_1_2():
    py = _versionen_in((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    bat = _versionen_in((ROOT / "INSTALLIEREN.bat").read_text(encoding="utf-8"))
    assert py and bat, "python-jobspy steht nicht in pyproject.toml oder INSTALLIEREN.bat"
    assert len(set(py + bat)) == 1, f"verschiedene Mindestversionen: pyproject {py}, Installer {bat}"
    assert tuple(int(t) for t in py[0].split(".")) >= (1, 2)


def test_1159_pyproject_nennt_die_mindestversion_im_kern_und_im_extra():
    """Beide Stellen: wer nur das Extra installiert, und wer den Kern installiert."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert len(_versionen_in(text)) == 2


# ══ Die echte Fassung (nur wo installiert) ═══════════════════════════════════════

@pytest.fixture
def jobspy():
    modul = pytest.importorskip("jobspy")
    return modul


def test_1159_die_installierte_fassung_ist_mindestens_1_2(jobspy):
    from importlib.metadata import version
    ist = tuple(int(t) for t in re.findall(r"\d+", version("python-jobspy"))[:3])
    assert ist >= (1, 2), "veraltet - pip install -U python-jobspy"


def test_1159_scrape_jobs_nimmt_alle_argumente_die_pbp_uebergibt(jobspy, monkeypatch):
    """Die Argumente kommen aus `_search_site` selbst, nicht aus einer Abschrift im Test."""
    aufrufe = []

    def merken(**kwargs):
        aufrufe.append(kwargs)
        import pandas as pd
        return pd.DataFrame()
    monkeypatch.setattr(js, "_ensure_jobspy", lambda: merken)
    js._search_site("indeed", ["Beispielbegriff"], "Hamburg", max_results=3)
    js._search_site("google", ["Beispielbegriff"], "Hamburg", max_results=3)
    assert len(aufrufe) == 2
    signatur = inspect.signature(jobspy.scrape_jobs)
    for kwargs in aufrufe:
        signatur.bind(**kwargs)   # wirft TypeError bei einem unbekannten Argument


def test_1159_die_spalten_die_pbp_liest_gibt_es(jobspy):
    from jobspy.util import desired_order
    gelesen = ["title", "company", "location", "description", "job_url_direct", "job_url",
               "is_remote", "job_type", "min_amount", "max_amount", "interval", "currency"]
    fehlend = [c for c in gelesen if c not in desired_order]
    assert not fehlend, f"JobSpy liefert diese Spalten nicht mehr: {fehlend}"


def _echte_tabelle(jobspy, monkeypatch, **kompensation):
    """Eine Tabelle, wie sie `scrape_jobs` baut - mit einer falschen Antwort der Seite (kein Netz)."""
    from jobspy.indeed import Indeed
    from jobspy.model import Compensation, JobPost, JobResponse, JobType, Location

    def antwort(self, scraper_input):
        comp = Compensation(**kompensation) if kompensation else None
        return JobResponse(jobs=[JobPost(
            title="Sachbearbeiter (m/w/d)", company_name="Beispiel GmbH",
            job_url="https://beispiel.example/job/1", job_url_direct="https://beispiel.example/job/1-direkt",
            location=Location(city="Hamburg", state="HH", country="Germany"),
            description="Beschreibung der Stelle.", job_type=[JobType.FULL_TIME],
            compensation=comp, is_remote=False)])
    monkeypatch.setattr(Indeed, "scrape", antwort)
    return jobspy.scrape_jobs(site_name=["indeed"], search_term="x", location="Hamburg",
                              country_indeed="Germany", results_wanted=1, verbose=0)


def test_1159_eine_echte_tabelle_wird_zu_einer_pbp_stelle(jobspy, monkeypatch):
    """Die Zeile stammt aus `scrape_jobs` der installierten Fassung - mit deren pandas."""
    df = _echte_tabelle(jobspy, monkeypatch)
    assert len(df) == 1
    job = js._map_row(df.iloc[0], "indeed")
    assert job["title"] == "Sachbearbeiter (m/w/d)" and job["company"] == "Beispiel GmbH"
    assert job["url"] == "https://beispiel.example/job/1-direkt"
    assert job["location"].startswith("Hamburg")
    assert job["description"] == "Beschreibung der Stelle."
    assert job["arbeitsumfang"] == "vollzeit"
    assert job["salary_min"] is None and job["salary_max"] is None, "ohne Gehaltsangabe kein Gehalt"
    assert job["source"] == "jobspy_indeed"


@pytest.mark.parametrize("intervall,niedrig,hoch,erwartet", [
    ("YEARLY", 40000, 52000, (40000, 52000)),
    ("MONTHLY", 3000, 4000, (36000, 48000)),
    ("HOURLY", 15, 18, (31200, 37440)),
])
def test_1159_das_gehalt_aus_einer_echten_tabelle_ist_ein_jahresgehalt(jobspy, monkeypatch, intervall, niedrig, hoch, erwartet):
    from jobspy.model import CompensationInterval
    df = _echte_tabelle(jobspy, monkeypatch, interval=CompensationInterval[intervall],
                        min_amount=niedrig, max_amount=hoch, currency="EUR")
    job = js._map_row(df.iloc[0], "indeed")
    assert (job["salary_min"], job["salary_max"]) == erwartet


# ══ Das Gehalt ═══════════════════════════════════════════════════════════════

def _zeile(**felder):
    return dict(felder)


@pytest.mark.parametrize("zeile,erwartet", [
    # Jahr: unverändert
    (dict(interval="yearly", min_amount=40000.0, max_amount=52000.0, currency="EUR"), (40000, 52000)),
    # Monat, Woche, Tag, Stunde: auf ein Jahr gerechnet
    (dict(interval="monthly", min_amount=3000.0, max_amount=4000.0, currency="EUR"), (36000, 48000)),
    (dict(interval="weekly", min_amount=800.0, max_amount=900.0, currency="EUR"), (41600, 46800)),
    (dict(interval="daily", min_amount=150.0, max_amount=200.0, currency="EUR"), (39000, 52000)),
    (dict(interval="hourly", min_amount=15.0, max_amount=18.0, currency="EUR"), (31200, 37440)),
    # nur ein Betrag: JobSpy rechnet dann selbst nicht um, PBP schon
    (dict(interval="monthly", min_amount=3500.0, max_amount=None, currency="EUR"), (42000, None)),
    (dict(interval="hourly", min_amount=None, max_amount=20.0, currency="EUR"), (None, 41600)),
    # Schreibweise des Intervalls
    (dict(interval=" Monthly ", min_amount=3000.0, max_amount=3000.0, currency="eur"), (36000, 36000)),
    # fehlendes Intervall oder fehlende Währung: wie bisher als Jahr
    (dict(min_amount=40000.0, max_amount=52000.0), (40000, 52000)),
    (dict(interval=None, min_amount=40000.0, max_amount=52000.0, currency=None), (40000, 52000)),
    (dict(interval=float("nan"), min_amount=40000.0, max_amount=52000.0, currency=float("nan")), (40000, 52000)),
])
def test_1159_gehalt_wird_auf_ein_jahr_gerechnet(zeile, erwartet):
    assert js._jahresgehalt(_zeile(**zeile)) == erwartet


@pytest.mark.parametrize("zeile", [
    dict(interval="yearly", min_amount=50000.0, max_amount=60000.0, currency="CHF"),
    dict(interval="yearly", min_amount=50000.0, max_amount=60000.0, currency="USD"),
    dict(interval="fortnightly", min_amount=2000.0, max_amount=2500.0, currency="EUR"),
    dict(min_amount=None, max_amount=None, currency="EUR", interval="yearly"),
    dict(min_amount=float("nan"), max_amount=float("nan"), currency="EUR", interval="yearly"),
    dict(),
])
def test_1159_kein_gehalt_wenn_waehrung_oder_intervall_nicht_stimmen(zeile):
    assert js._jahresgehalt(_zeile(**zeile)) == (None, None)


def test_1159_ein_unlesbarer_betrag_ergibt_kein_gehalt_statt_eines_absturzes():
    assert js._jahresgehalt(_zeile(interval="yearly", min_amount="viel", max_amount=None, currency="EUR")) == (None, None)


def test_1159_map_row_nutzt_die_umrechnung():
    job = js._map_row(_zeile(title="Beispielstelle", company="Beispiel GmbH", location="Hamburg", description="x",
                             job_url="https://beispiel.example/1", interval="hourly", min_amount=15.0,
                             max_amount=18.0, currency="EUR"), "indeed")
    assert (job["salary_min"], job["salary_max"]) == (31200, 37440)


# ══ Ausgefallene Abfragen ══════════════════════════════════════════════════════

class _Fake:
    """Ein falsches `scrape_jobs`, das wie JobSpy 1.2 loggt statt zu werfen."""

    def __init__(self, ablauf, logger_name="JobSpy:Indeed"):
        self.ablauf = list(ablauf)   # je Aufruf: ("fehler", text) | ("leer",) | ("zeilen", n) | ("wirft", exc) | ("warnung", text)
        self.aufrufe = 0
        self.logger = logging.getLogger(logger_name)

    def __call__(self, **kwargs):
        # Die echte Bibliothek stellt ihre Logger mit `verbose=0` auf ERROR (und andere Tests rufen sie echt auf):
        # damit eine Warnung hier überhaupt ankommt, wird der Logger offen gestellt.
        self.logger.setLevel(logging.DEBUG)
        import pandas as pd
        schritt = self.ablauf[min(self.aufrufe, len(self.ablauf) - 1)]
        self.aufrufe += 1
        art = schritt[0]
        if art == "fehler":
            self.logger.error(schritt[1])
            return pd.DataFrame()
        if art == "warnung":
            self.logger.warning(schritt[1])
            return self._zeilen(1)
        if art == "warnung_leer":
            self.logger.warning(schritt[1])
            return pd.DataFrame()
        if art == "wirft":
            raise schritt[1]
        if art == "zeilen":
            return self._zeilen(schritt[1])
        return pd.DataFrame()

    @staticmethod
    def _zeilen(n):
        import pandas as pd
        return pd.DataFrame([{"title": f"Beispielstelle {i}", "company": "Beispiel GmbH", "location": "Hamburg",
                              "description": "x", "job_url": f"https://beispiel.example/{i}"} for i in range(n)])


def _lauf(monkeypatch, fake, keywords=("a", "b", "c", "d"), site="indeed", **kw):
    monkeypatch.setattr(js, "_ensure_jobspy", lambda: fake)
    return js._search_site(site, list(keywords), "Hamburg", **kw)


def test_1159_eine_gesperrte_seite_wird_gemeldet_und_nicht_weiter_befragt(monkeypatch):
    fake = _Fake([("fehler", "Indeed response status code 429")])
    with pytest.raises(js.JobSpyAusgefallen) as e:
        _lauf(monkeypatch, fake)
    assert e.value.ratenbegrenzt is True
    assert fake.aufrufe == 1, "nach einer Sperre wird nicht weiter gefragt"
    assert "429" in str(e.value) and "1 von 1" in str(e.value)


def test_1159_ein_anderer_fehler_wird_gemeldet_nachdem_alle_abfragen_scheiterten(monkeypatch):
    fake = _Fake([("fehler", "Indeed response status code 500")])
    with pytest.raises(js.JobSpyAusgefallen) as e:
        _lauf(monkeypatch, fake)
    assert e.value.ratenbegrenzt is False
    assert fake.aufrufe == 3, "die Schutzregel gegen leere Antworten greift nach drei"
    assert "3 von 3" in str(e.value) and "500" in str(e.value)


def test_1159_eine_seite_ohne_treffer_und_ohne_fehler_ist_kein_ausfall(monkeypatch):
    fake = _Fake([("leer",)])
    assert _lauf(monkeypatch, fake) == []


def test_1159_ein_teilweiser_ausfall_liefert_die_treffer(monkeypatch):
    fake = _Fake([("fehler", "Indeed response status code 500"), ("zeilen", 2), ("leer",)])
    jobs = _lauf(monkeypatch, fake)
    assert len(jobs) == 2
    assert {j["title"] for j in jobs} == {"Beispielstelle 0", "Beispielstelle 1"}


def test_1159_mischung_aus_fehler_und_leerer_antwort_ist_kein_ausfall(monkeypatch):
    """Nicht jede Abfrage scheiterte: eine leere Antwort ohne Fehler ist ein ehrliches 'nichts gefunden'."""
    fake = _Fake([("fehler", "Indeed response status code 500"), ("leer",), ("leer",)])
    assert _lauf(monkeypatch, fake) == []


def test_1159_eine_warnung_ist_kein_fehler(monkeypatch):
    fake = _Fake([("warnung", "skipping job: kaputte Zeile")])
    jobs = _lauf(monkeypatch, fake, keywords=("a",))
    assert len(jobs) == 1


def test_1159_eine_warnung_bei_leerer_antwort_ist_ebenfalls_kein_ausfall(monkeypatch):
    """Nur ERROR zählt: eine Warnung und keine Treffer ist ein ehrliches 'nichts gefunden'."""
    fake = _Fake([("warnung_leer", "skipping job: kaputte Zeile")])
    assert _lauf(monkeypatch, fake) == []


def test_1159_eine_ausnahme_bei_allen_abfragen_wird_ebenfalls_gemeldet(monkeypatch):
    fake = _Fake([("wirft", RuntimeError("Verbindung getrennt"))])
    with pytest.raises(js.JobSpyAusgefallen) as e:
        _lauf(monkeypatch, fake)
    assert fake.aufrufe == 4 and "4 von 4" in str(e.value) and "Verbindung getrennt" in str(e.value)
    assert e.value.ratenbegrenzt is False


def test_1159_eine_ausnahme_mit_429_gilt_als_sperre(monkeypatch):
    fake = _Fake([("wirft", RuntimeError("HTTP 429 Too Many Requests"))])
    with pytest.raises(js.JobSpyAusgefallen) as e:
        _lauf(monkeypatch, fake)
    assert e.value.ratenbegrenzt is True and fake.aufrufe == 1


def test_1159_der_sammler_bleibt_nicht_am_logger_haengen(monkeypatch):
    logger = logging.getLogger("JobSpy:Indeed")
    vorher = list(logger.handlers)
    _lauf(monkeypatch, _Fake([("zeilen", 1)]), keywords=("a",))
    with pytest.raises(js.JobSpyAusgefallen):
        _lauf(monkeypatch, _Fake([("fehler", "Indeed response status code 429")]))
    with pytest.raises(js.JobSpyAusgefallen):
        _lauf(monkeypatch, _Fake([("wirft", RuntimeError("x"))]))
    assert logger.handlers == vorher


def test_1159_jeder_site_hat_ihren_logger(monkeypatch):
    for site, name in (("linkedin", "JobSpy:LinkedIn"), ("glassdoor", "JobSpy:Glassdoor"), ("google", "JobSpy:Google")):
        fake = _Fake([("fehler", "x response status code 500")], logger_name=name)
        with pytest.raises(js.JobSpyAusgefallen):
            _lauf(monkeypatch, fake, keywords=("a",), site=site)


def test_1159_der_logger_name_stimmt_mit_dem_der_echten_bibliothek_ueberein(jobspy, monkeypatch):
    """`create_logger("Indeed")` ist genau das, was die echte Seite beim Fehler benutzt."""
    from jobspy.util import create_logger

    def echt(**kwargs):
        import pandas as pd
        create_logger("Indeed").error("Indeed response status code 429")
        return pd.DataFrame()
    with pytest.raises(js.JobSpyAusgefallen) as e:
        _lauf(monkeypatch, echt, keywords=("a",))
    assert e.value.ratenbegrenzt is True


def test_1159_mit_dem_zwischenstand_der_langlaeufe_geht_es_ebenso(monkeypatch):
    import threading
    zwischen = {"jobs": [], "stopp": threading.Event(), "fertig": 0, "abfragen": 0}
    fake = _Fake([("fehler", "LinkedIn response status code 500")], logger_name="JobSpy:LinkedIn")
    with pytest.raises(js.JobSpyAusgefallen):
        _lauf(monkeypatch, fake, keywords=("a", "b"), site="linkedin", zwischenstand=zwischen)
    assert zwischen["fertig"] >= 1


def test_1159_ein_gefundener_treffer_vor_dem_ausfall_geht_nicht_verloren(monkeypatch):
    fake = _Fake([("zeilen", 1), ("fehler", "Indeed response status code 429")])
    jobs = _lauf(monkeypatch, fake)
    assert len(jobs) == 1


# ══ Der Adapter ═══════════════════════════════════════════════════════════════

def test_1159_der_adapter_meldet_den_ausfall_als_fehler(monkeypatch):
    from bewerbungs_assistent.job_scraper.adapters import AdapterStatus
    from bewerbungs_assistent.job_scraper.adapters.jobspy_adapter import JobSpyIndeedAdapter

    def aus(params):
        raise js.JobSpyAusgefallen("JobSpy/indeed: 3 von 3 Abfragen sind gescheitert (Ratenbegrenzung?)", ratenbegrenzt=True)
    monkeypatch.setattr(js, "_ensure_jobspy", lambda: (lambda **k: None))
    monkeypatch.setattr(JobSpyIndeedAdapter, "_fn", staticmethod(aus))
    r = JobSpyIndeedAdapter().search({"keywords": {"general": ["a"]}})
    assert r.status == AdapterStatus.ERROR and "3 von 3" in r.message and r.postings == []
