"""#1085: LinkedIn-Anzeigentext ohne Gehaltskasten und ohne den Kasten zur
Ansprechperson. Nachgebaute Seiten nach der bekannten Struktur der
oeffentlichen Stellenseite, mit fiktivem Namen (Max Mustermann)."""
from __future__ import annotations

import os

import pytest

KOPF = """<!DOCTYPE html><html><head><title>Sachbearbeitung Einkauf | LinkedIn</title>
<meta property="og:site_name" content="LinkedIn"></head><body>
<!---->
<section class="top-card-layout container-lined">
  <h1 class="top-card-layout__title">Sachbearbeitung Einkauf (m/w/d)</h1>
  <!----><a class="topcard__org-name-link">Musterbetrieb GmbH</a>
</section>
"""

GEHALT = """<section class="compensation compensation--salary">
  <!---->
  <h2 class="compensation__heading">Base pay range</h2>
  <div class="salary compensation__salary">
      €70,000.00/yr - €85,000.00/yr
  </div>
  <p class="compensation__description">This range is provided by Musterbetrieb GmbH.
  Your actual pay will be based on your skills and experience — talk with your
  recruiter to learn more.</p>
</section>
"""

ANSPRECH = """<section class="core-section-container">
  <h3 class="core-section-container__title">Direct message the job poster from Musterbetrieb GmbH</h3>
  <div class="base-card">
    <h3 class="base-main-card__title">Max Mustermann</h3>
    <h4 class="base-main-card__subtitle">Talent Acquisition Partner</h4>
  </div>
</section>
"""

ANZEIGE = """<section class="core-section-container description">
  <div class="description__text description__text--rich">
    <section class="show-more-less-html">
      <div class="show-more-less-html__markup show-more-less-html__markup--clamp-after-5">
        <!---->
        <p>Wir suchen Verstärkung für unseren Einkauf am Standort Hamburg.</p>
        <p><strong>Deine Aufgaben:</strong></p>
        <ul><li>Bestellungen und Lieferantenkontakt</li>
            <li>Preisverhandlungen und Rahmenverträge</li></ul>
        <p><strong>Dein Profil:</strong></p>
        <ul><li>Kaufmännische Ausbildung</li><li>Erfahrung im Einkauf</li></ul>
      </div>
    </section>
  </div>
  <ul class="description__job-criteria-list">
    <li><h3>Seniority level</h3><span>Mid-Senior level</span></li>
    <li><h3>Employment type</h3><span>Full-time</span></li>
  </ul>
</section>
"""

#: Ansprechkasten direkt im Beschreibungsblock, ohne inneren Markup-Block
ANZEIGE_MIT_KASTEN = """<div class="description__text description__text--rich">
  <div class="core-section-container">
    <h3>Direct message the job poster from Musterbetrieb GmbH</h3>
    <div><span>Max Mustermann</span><span>Talent Acquisition Partner</span></div>
  </div>
  <p>Wir suchen Verstärkung für unseren Einkauf am Standort Hamburg.</p>
  <ul><li>Bestellungen und Lieferantenkontakt</li>
      <li>Preisverhandlungen und Rahmenverträge mit langjährigen Partnern</li></ul>
</div>
"""

#: Gehaltskasten, dessen Klasse PBP nicht kennt
GEHALT_UNBEKANNT = """<div class="details-description-pay">Base pay range
  €70,000.00/yr - €85,000.00/yr. This range is provided by Musterbetrieb GmbH.
  Your actual pay will be based on your skills and experience.</div>
"""

FUSS = "</body></html>"


class _Antwort:
    status_code = 200

    def __init__(self, text):
        self.text = text


class _Client:
    def __init__(self, html):
        self.html = html

    def get(self, url, timeout=None):
        return _Antwort(self.html)


def _holen(html):
    from bewerbungs_assistent.services import nachladen
    return nachladen.beschreibung_holen("https://www.linkedin.com/jobs/view/4000000001",
                                        _Client(html))


def test_gehaltskasten_vor_der_anzeige_gewinnt_nicht():
    b = _holen(KOPF + GEHALT + ANZEIGE + FUSS)
    assert b.status == "gelesen"
    assert b.text.startswith("Wir suchen Verstärkung"), b.text[:80]
    assert "pay range" not in b.text and "70,000" not in b.text
    assert "70,000.00" in b.kopf["gehalt_text"]


def test_ansprechperson_steht_nicht_im_text():
    b = _holen(KOPF + ANSPRECH + ANZEIGE + FUSS)
    assert b.status == "gelesen"
    assert "Mustermann" not in b.text and "Direct message" not in b.text
    assert b.text.startswith("Wir suchen Verstärkung")


def test_ansprechperson_im_beschreibungsblock():
    """Der Kasten steht INNERHALB des Beschreibungsblocks, vor dem Text —
    und traegt keine bekannte Klasse, nur seine Ueberschrift."""
    b = _holen(KOPF + ANZEIGE_MIT_KASTEN + FUSS)
    assert "Mustermann" not in b.text and "Direct message" not in b.text, b.text[:200]
    assert b.text.startswith("Wir suchen Verstärkung")


def test_beschreibungsblock_statt_ganzem_abschnitt():
    """Die Kriterienliste hinter dem Text gehoert nicht zur Anzeige."""
    b = _holen(KOPF + ANZEIGE + FUSS)
    assert "Seniority level" not in b.text


def test_gehaltskasten_mit_unbekannter_klasse_ist_kein_text():
    b = _holen(KOPF + GEHALT_UNBEKANNT + FUSS)
    assert b.status == "lebt_unlesbar", (b.status, b.text[:100])


def test_nur_gehaltskasten_ist_kein_anzeigentext():
    b = _holen(KOPF + GEHALT + FUSS)
    assert b.status == "lebt_unlesbar", (b.status, b.text[:100])
    assert not b.text


def test_andere_seite_unveraendert():
    html = ("<html><body><div class='job-description'><p>" + "Wir suchen jemanden. " * 10
            + "</p></div></body></html>")
    from bewerbungs_assistent.job_scraper import seite_lesen
    text, extras = seite_lesen(html)
    assert text.startswith("Wir suchen jemanden.") and extras == {}


# ── Gehalt aus dem Kasten ───────────────────────────────────────────

@pytest.mark.parametrize("kasten, erwartet", [
    ("€70,000.00/yr - €85,000.00/yr", (70000, 85000, "jaehrlich")),
    ("Base pay range €5,500.00/mo - €6,500.00/mo", (66000, 78000, "jaehrlich")),
    ("€45.00/hr - €60.00/hr", (45, 60, "stuendlich")),
])
def test_gehalt_aus_kasten(kasten, erwartet):
    from bewerbungs_assistent.job_scraper.linkedin_seite import gehalt_aus_kasten
    g = gehalt_aus_kasten(kasten)
    assert (g["min"], g["max"], g["art"]) == erwartet


def test_uneindeutig_oder_unplausibel_kein_gehalt():
    from bewerbungs_assistent.job_scraper.linkedin_seite import gehalt_aus_kasten
    assert gehalt_aus_kasten("€100.00/hr - €200.00/yr") is None        # zwei Einheiten
    assert gehalt_aus_kasten("€7.00/yr - €8.00/yr") is None            # unplausibel
    assert gehalt_aus_kasten("") is None


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "LinkedIn"})
    d.save_jobs([{"hash": "li1085", "title": "Sachbearbeitung Einkauf",
                  "company": "Musterbetrieb GmbH",
                  "url": "https://www.linkedin.com/jobs/view/4000000001",
                  "source": "jobspy_linkedin", "description": ""}])
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def test_uebernahme_speichert_gehalt_mit_beleg(db):
    from bewerbungs_assistent.services import nachladen
    b = _holen(KOPF + GEHALT + ANSPRECH + ANZEIGE + FUSS)
    nachladen.text_uebernehmen(db, "li1085", b.text, kopf=b.kopf)
    job = db.get_job("li1085")
    assert "Mustermann" not in job["description"]
    assert (job["salary_min"], job["salary_max"], job["salary_type"]) == (70000, 85000, "jaehrlich")
    assert not job["salary_estimated"]


def test_handgehalt_bleibt(db):
    from bewerbungs_assistent.services import nachladen
    db.save_salary_data("li1085", 50000, 55000, "jaehrlich", salary_estimated=0, quelle="mensch")
    b = _holen(KOPF + GEHALT + ANZEIGE + FUSS)
    nachladen.text_uebernehmen(db, "li1085", b.text, kopf=b.kopf)
    assert db.get_job("li1085")["salary_min"] == 50000


def _werkzeug(db, name, args):
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1085")
    register_all(mcp, db, logging.getLogger("test.1085"))

    async def lauf():
        t = await mcp.get_tool(name)
        return (await t.run(args)).structured_content
    return asyncio.run(lauf())


def test_bestand_mit_ansprechkasten_wird_neu_geladen(db, monkeypatch):
    """Der Text mit Kasten ist LAENGER als der bereinigte — der Bestandsweg
    ersetzt ihn trotzdem, sonst bliebe der Name stehen."""
    from bewerbungs_assistent.services import nachladen
    alt = ("Direct message the job poster from Musterbetrieb GmbH\nMax Mustermann\n"
           "Talent Acquisition Partner\n" + "Wir suchen Verstärkung für unseren Einkauf. " * 8)
    db.update_job("li1085", {"description": alt})
    neu = _holen(KOPF + ANSPRECH + ANZEIGE + FUSS)
    assert len(neu.text) < len(alt)
    monkeypatch.setattr(nachladen, "beschreibung_holen", lambda *a, **k: neu)
    vorschau = _werkzeug(db, "beschreibungen_nachladen_bestand",
                         {"umfang": "linkedin_kasten"})
    assert vorschau["betroffen"] == 1, vorschau
    _werkzeug(db, "beschreibungen_nachladen_bestand",
              {"umfang": "linkedin_kasten", "nur_zaehlen": False})
    assert "Mustermann" not in db.get_job("li1085")["description"]


def test_bestand_gehaltskasten_wird_gefunden(db):
    db.update_job("li1085", {"description":
        "Base pay range\n€70,000.00/yr - €85,000.00/yr\nThis range is provided by Musterbetrieb GmbH."})
    erg = _werkzeug(db, "beschreibungen_nachladen_bestand", {"umfang": "linkedin_kasten"})
    assert erg["betroffen"] == 1


def test_belegtes_gehalt_bleibt(db):
    from bewerbungs_assistent.services import nachladen
    db.save_salary_data("li1085", 50000, 55000, "jaehrlich", salary_estimated=0)
    b = _holen(KOPF + GEHALT + ANZEIGE + FUSS)
    nachladen.text_uebernehmen(db, "li1085", b.text, kopf=b.kopf)
    assert db.get_job("li1085")["salary_min"] == 50000
