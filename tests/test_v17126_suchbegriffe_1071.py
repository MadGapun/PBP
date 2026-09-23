"""#1071 — die API-Quellen suchten mit jedem MUSS- UND PLUS-Begriff.

Beim Melder 56 MUSS- plus 103 PLUS-Begriffe, darunter "Senior", "Aufbau",
"Strategie". jobspy_indeed: 495 Stellen, 293 davon falsches Fachgebiet,
2 Bewerbungen (0,4 %) — gegen 7,4 % fuer die Titelsuche im Browser, die
das Portal-Suchprofil nutzt. Das Suchprofil las die automatische Suche
nirgends.
"""
from bewerbungs_assistent.job_scraper import build_search_keywords


def test_1071_gesucht_wird_nur_mit_muss(tmp_db):
    tmp_db.set_search_criteria("keywords_muss", ["PLM", "Stammdaten"])
    tmp_db.set_search_criteria("keywords_plus", ["Senior", "Aufbau"])
    kw = build_search_keywords(tmp_db)
    for schluessel in ("general", "indeed_queries", "hays_keywords"):
        text = " ".join(kw[schluessel]).lower()
        assert "senior" not in text and "aufbau" not in text, schluessel
    assert not any("senior" in u for u in kw["stepstone_urls"])
    assert not any("senior" in u.lower() for u in kw["freelance_de_urls"])


def test_1071_ohne_muss_traegt_plus_die_suche(tmp_db):
    """Kaltstart (#967): ohne MUSS-Liste darf die Suche nicht leer laufen."""
    tmp_db.set_search_criteria("keywords_plus", ["Buchhaltung"])
    assert build_search_keywords(tmp_db)["general"] == ["Buchhaltung"]


def test_1071_das_indeed_suchprofil_wird_gelesen(tmp_db):
    tmp_db.save_profile({"name": "Test"})
    tmp_db.set_search_criteria("keywords_muss", ["PLM"])
    tmp_db.get_portal_search_profile("indeed")
    tmp_db.update_portal_search_profile(
        "indeed",
        primaere_suchen=['title:(PLM OR PDM OR Stueckliste)'],
        sekundaere_suchen=["Produktdatenmanagement"],
        nicht_verwenden=["Produktdatenmanagement"])
    kw = build_search_keywords(tmp_db)
    assert kw["portal_suchbegriffe"]["indeed"] == ['title:(PLM OR PDM OR Stueckliste)']


def test_1071_ohne_suchprofil_wird_keins_angelegt(tmp_db):
    """Lesen darf nichts anlegen (#1049)."""
    tmp_db.save_profile({"name": "Test"})
    tmp_db.set_search_criteria("keywords_muss", ["PLM"])
    assert build_search_keywords(tmp_db)["portal_suchbegriffe"] == {}
    assert tmp_db.find_portal_search_profile("indeed") is None


def test_1071_indeed_sucht_mit_dem_profil(monkeypatch):
    from bewerbungs_assistent.job_scraper import jobspy_source
    gesehen = {}

    def fake(site, keywords, location, **kw):
        gesehen["kw"] = list(keywords)
        return []
    monkeypatch.setattr(jobspy_source, "_search_site", fake)
    jobspy_source.search_jobspy_indeed({"keywords": {
        "general": ["PLM"], "regionen": ["Hamburg"],
        "portal_suchbegriffe": {"indeed": ["title:(PLM OR PDM)"]}}})
    assert gesehen["kw"] == ["title:(PLM OR PDM)"]
    jobspy_source.search_jobspy_indeed({"keywords": {
        "general": ["PLM"], "regionen": ["Hamburg"]}})
    assert gesehen["kw"] == ["PLM"]


def test_1071_der_ausloesende_suchbegriff_wird_mitgeschrieben(monkeypatch):
    from bewerbungs_assistent.job_scraper import jobspy_source

    class Tabelle:
        """Das, was `_search_site` von einem DataFrame benutzt — ohne pandas."""
        def __init__(self, zeilen):
            self.zeilen = zeilen
            self.empty = not zeilen

        def iterrows(self):
            return enumerate(self.zeilen)

    def scrape(**kwargs):
        return Tabelle([{
            "title": f"Stelle zu {kwargs['search_term']}", "company": "Muster AG",
            "location": "Hamburg", "description": "Text",
            "job_url": f"https://example.com/{kwargs['search_term']}",
            "is_remote": False}])
    monkeypatch.setattr(jobspy_source, "_ensure_jobspy", lambda: scrape)
    jobs = jobspy_source._search_site("indeed", ["PLM", "PDM"], "Hamburg")
    assert [j["suchbegriff"] for j in jobs] == ["PLM", "PDM"]


def test_1071_die_fundstelle_traegt_den_suchbegriff(tmp_db):
    tmp_db.save_profile({"name": "Test"})
    tmp_db.save_jobs([{
        "hash": "s1071a", "title": "PLM Berater", "company": "Muster AG",
        "location": "Hamburg", "url": "https://example.com/s1071a",
        "source": "jobspy_indeed", "description": "Text", "suchbegriff": "PLM"}])
    zeile = tmp_db.connect().execute(
        "SELECT suchbegriff FROM job_sources WHERE job_hash=?",
        (tmp_db.resolve_job_hash("s1071a"),)).fetchone()
    assert zeile["suchbegriff"] == "PLM"
