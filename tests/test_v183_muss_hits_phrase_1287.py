"""#1287 - `muss_hits` meldete Mehrwortbegriffe, die nur als Einzelwoerter im Text stehen.

Gemessen vor dem Fix (fiktive Anzeigen, isolierte Datenbank):

* Befund 1: `fit_analyse` fuellte `muss_hits` mit dem unscharfen Matcher
  (Mehrwort-Split: jedes Wort irgendwo im Text reicht), das MUSS-Tor
  (`muss_tor.pflicht_treffer`) fragt praezise. Eine Vertriebsanzeige mit
  "data", "office" und "owner" verstreut meldete zwei Pflichttreffer bei
  "ohne Pflichttreffer". Schlimmer: oeffnete ein ANDERER Begriff das Tor,
  zaehlten `calculate_score` UND `fit_analyse` den Scheintreffer mit
  (4,0 statt 2,0 Pflichtpunkte).
* Befund 2: im Tor-Modus `gewichtet` kuerzte `fit_analyse` die
  Wunschbegriffe mit dem PLUS-Deckel aus den Schein-Pflichtpunkten, die
  Anlage (`calculate_score`) nicht: gespeichert 5,0, neu berechnet 2,5 -
  am Anlagetag, ohne geaenderte Kriterien.

Seit dem Fix sind `muss_hits` genau die Treffer des Tors (eine Frage, eine
Funktion), und beide Rechenwege zaehlen dieselben Pflichtpunkte.
Testdaten fiktiv; die Datenbank-Faelle laufen isoliert (BA_DATA_DIR).
"""
from __future__ import annotations

import asyncio
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent import job_scraper as js  # noqa: E402
from bewerbungs_assistent.services import muss_tor  # noqa: E402

# Beispiel 1 aus dem Issue, nachgebaut: Vertrieb, die Einzelwoerter
# "data", "office", "owner" stehen verstreut, die Phrasen nie.
VERTRIEB = ("Sales Manager Restaurant Software. We build the operating system "
            "for restaurants and all the data that powers it. This is not your "
            "typical SaaS or office sales job: you will visit a busy "
            "hospitality owner every day, run demos and close deals. "
            "Requirements: field sales experience, German and English. ") * 2
# Beispiel 2: "Business Process Management" und "Process Architect",
# aber nie "Business Architect".
PROZESS = ("Process Consultant (m/w/d). Ihre Aufgaben: Business Process "
           "Management in Kundenprojekten, Rolle als Process Architect, "
           "Modellierung in BPMN, Workshops mit Fachbereichen. Ihr Profil: "
           "Studium, Erfahrung mit Prozessmodellierung, PLM von Vorteil. ") * 2

MUSS = ["Data Office", "Data Owner", "Business Architect"]


def _krit(muss=None, plus=None, modus=None, gewichtung=None):
    k = {"keywords_muss": list(muss if muss is not None else MUSS),
         "keywords_plus": list(plus or []),
         "keywords_minus": [], "keywords_ausschluss": []}
    if modus:
        k["_muss_tor_modus"] = modus
    if gewichtung:
        k["gewichtung"] = gewichtung
    return k


def _job(text, titel=None):
    return {"title": titel or text.split(".")[0], "description": text,
            "hash": "t1287"}


# ── AK 3: die Beispiele aus dem Issue ────────────────────────────────


@pytest.mark.parametrize("text", [VERTRIEB, PROZESS])
@pytest.mark.parametrize("modus", [muss_tor.HART, muss_tor.GEWICHTET])
def test_einzelwoerter_sind_kein_pflichttreffer(text, modus):
    erg = js.fit_analyse(_job(text), _krit(modus=modus))
    assert erg["muss_hits"] == []
    assert sorted(erg["missing_muss"]) == sorted(MUSS)
    assert erg.get("ohne_pflichttreffer") is True


def test_business_architect_zaehlt_nicht_mit_wenn_ein_anderer_begriff_das_tor_oeffnet():
    krit = _krit(muss=MUSS + ["PLM"], plus=["BPMN"])
    job = _job(PROZESS)
    erg = js.fit_analyse(dict(job), krit)
    assert erg["muss_hits"] == ["PLM"]
    assert "Business Architect" in erg["missing_muss"]
    # Ein Pflichttreffer zu 2 Punkten, nicht zwei.
    fach = {k: v for k, v in erg["faktoren_fach"].items() if k.startswith("MUSS")}
    assert list(fach.values()) == [2.0]
    assert js.calculate_score(dict(job), krit) == erg["total_score"]


# ── AK 1: dieselbe Trefferlogik an allen drei Stellen ────────────────


FAELLE = [
    ("Data Office", "Wir suchen eine Leitung fuer unser Data Office in Hamburg.", True),
    ("Data Office", "data that powers our office", False),
    ("Data Office", "Aufbau des Data-Office und der Governance", True),
    ("Data Office", "Aufbau des data/office-Teams", True),
    ("Data Office", "DATA   OFFICE gesucht", True),
    ("Data Owner", "Rolle: data owner fuer Stammdaten", True),
    ("Data Owner", "the owner of all data", False),
    ("Data Owner", "Data Ownership im Team", False),
    ("Business Architect", "Senior Business-Architect (m/w/d)", True),
    ("Business Architect", "Business Process Management und Process Architect", False),
    ("Prüfplanung", "Erfahrung in der Pruefplanung", True),
    ("Pruefplanung", "Erfahrung in der Prüfplanung", True),
    ("Prüfplanung", "Prüf- und Planungsaufgaben", False),
]


@pytest.mark.parametrize("kw,text,erwartet", FAELLE)
def test_muss_hits_folgen_dem_tor(kw, text, erwartet):
    """Beide Richtungen (Lehre 3): Phrase -> Treffer, verstreut -> keiner;
    Bindestrich, Schraegstrich, Leerraum, Gross/klein, Umlaut/Umschrift."""
    krit = _krit(muss=[kw])
    job = _job("Stelle. " + text + " " + "Weitere Aufgaben im Team. " * 4)
    tor = muss_tor.tor_offen(job, krit)
    hits = js.fit_analyse(dict(job), krit)["muss_hits"]
    assert (kw in tor) is erwartet
    assert hits == tor
    # Der Score zaehlt genau dann Pflichtpunkte, wenn das Tor offen ist.
    job2 = dict(job)
    js.calculate_score(job2, krit)
    assert (job2.get("_fachscore", 0) > 0) is erwartet


# ── AK 4: Anlage und fit_analyse rechnen gleich (Befund 2) ───────────


FIRMENABSATZ = (
    "Wir sind ein junges Team und unsere Kultur lebt von Vertrauen. Wir "
    "bieten all the data that powers our office, und jeder owner bei uns "
    "ist stolz. Wir wachsen schnell und unsere Mission ist klar.\n\n"
    "Deine Aufgaben: Sales im Aussendienst, Remote-Tage, English, Hamburg, "
    "Kundentermine, Demos, Abschluesse. Dein Profil: Erfahrung im Vertrieb, "
    "Fuehrerschein, Reisebereitschaft, Kommunikationsstaerke und Ausdauer.")


def test_gewichtet_ohne_pflichttreffer_gleiche_zahl():
    krit = _krit(plus=["Sales", "Remote", "English", "Hamburg"],
                 modus=muss_tor.GEWICHTET, gewichtung={"muss": 10, "plus": 2})
    job = _job(FIRMENABSATZ, titel="Sales Manager")
    assert js._firmenabsatz_ende(FIRMENABSATZ) > 0  # der Fall braucht ihn
    gespeichert = js.calculate_score(dict(job), krit)
    erg = js.fit_analyse(dict(job), krit)
    assert erg["muss_hits"] == []
    assert gespeichert == erg["total_score"] == 5.0


def test_pflichttreffer_nur_im_firmenabsatz_fragt_das_tor():
    """Der Firmenabsatz-Faktor (#827) fuer Pflichtbegriffe fragt ebenfalls das
    Tor: verstreute Einzelwoerter im Aufgabenteil heben ihn nicht auf 1,0."""
    text = ("Wir sind ein Team mit Kultur und unsere Mission ist klar. Unser "
            "Data Office waechst, wir bieten Vertrauen.\n\n"
            "Deine Aufgaben: Vertrieb, data driven, im office und beim owner "
            "vor Ort, Kundentermine und Abschluesse mit Ausdauer und Freude.")
    krit = _krit(muss=["Data Office"])
    job = _job(text, titel="Vertrieb")
    assert js._firmenabsatz_ende(text) > 0
    j = dict(job)
    calc = js.calculate_score(j, krit)
    erg = js.fit_analyse(dict(job), krit)
    assert erg["muss_hits"] == ["Data Office"]
    assert calc == erg["total_score"] == 0.5  # 2 Punkte x 0,25
    assert j.get("_treffer_nur_firmenabsatz") is True


# ── Ende zu Ende: Werkzeug und Anlage auf isolierter Datenbank ───────


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_1287_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test 1287"})
    db.set_search_criteria("keywords_muss", MUSS)
    db.set_search_criteria("keywords_plus", ["Sales", "English"])
    muss_tor.modus_setzen(db, muss_tor.GEWICHTET)
    try:
        yield db, _srv_mod.mcp
    finally:
        db.close()
        shutil.rmtree(tmpdir, ignore_errors=True)
        os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def test_werkzeug_meldet_keine_scheintreffer_und_keine_abweichung(umgebung):
    db, mcp = umgebung
    angelegt = _call(mcp, "stelle_manuell_anlegen", {
        "titel": "Sales Manager Restaurant Software",
        "firma": "Musterfirma GmbH", "url": "https://example.com/1287",
        "beschreibung": VERTRIEB, "force": True})
    kennung = angelegt.get("hash") or angelegt.get("job_hash")
    assert kennung, angelegt
    erg = _call(mcp, "fit_analyse", {"job_hash": kennung})
    assert erg["muss_hits"] == []
    assert erg["empfehlung"].get("muss_treffer", 0) == 0
    assert erg.get("ohne_pflichttreffer") is True
    assert "score_abweichung" not in erg, erg.get("score_abweichung")


# ── Nebenwege, die dieselbe Frage stellen ───────────────────────────


def _bestand(db, n):
    db.save_jobs([{
        "hash": f"b1287_{i}", "title": f"Sales Manager {i}",
        "company": f"Musterfirma {i} GmbH", "url": f"https://example.com/b/{i}",
        "source": "manuell", "description": VERTRIEB,
        "score": 5 if i % 2 else 0} for i in range(n)])


def test_idf_zaehlt_pflichtbegriffe_wie_das_tor(umgebung):
    """Die Seltenheit eines Pflichtbegriffs (#778) zaehlt die Anzeigen, in
    denen er das Tor oeffnet - verstreute Einzelwoerter machen ihn nicht
    "haeufig"."""
    db, _ = umgebung
    from bewerbungs_assistent.services import kalibrierung
    _bestand(db, 60)
    faktoren = kalibrierung.berechne_idf_faktoren(db, _krit(plus=["Sales"]))
    assert faktoren["data office"] == 1.0
    assert faktoren["sales"] < 1.0  # Gegenrichtung: ein echter Allerweltsbegriff


def test_tote_pflichtbegriffe_wie_das_tor(umgebung):
    db, mcp = umgebung
    _bestand(db, 8)
    erg = _call(mcp, "keyword_vorschlaege")
    tote = [k.lower() for k in (erg.get("tote_keywords") or [])]
    assert "data office" in tote, erg
    assert "sales" not in tote
