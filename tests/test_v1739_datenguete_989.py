"""Tests fuer v1.7.39 — #989: Unbekanntes wirkte wie Unauffaelliges.

Der Nutzer hat vier unabhaengige Fehler an einem Tag gemeldet und ihre
gemeinsame Wurzel benannt:

> Wo eine Information fehlt, setzt PBP einen neutralen Wert ein und
> rechnet weiter. Neutral heisst in einem Punktesystem aber nicht
> "unbekannt", sondern "kostet nichts". Und was nichts kostet, steigt
> in der Sortierung.

Gemessen am 07.09.2026: eine Stelle mit vollstaendiger, fachlich
passender Beschreibung bekam 32 Punkte, ein inhaltsleerer Titel 101.

Der zweite Teil des Befunds ist der unangenehmere:

> Es gibt bereits `entfernung_guete` mit dem Wert "unbekannt",
> `score_status` mit "unbewertet", den Satz "Score 0 ist KEIN Urteil"
> und die Guete-Abstufung beim Wiedergaenger-Befund. Alle vier stehen in
> Tool-Antworten. **In der Trefferliste, die der Nutzer tatsaechlich
> ansieht, kommt davon nichts an.**

Die Loesung veraendert deshalb BEWUSST nicht den Score. Der misst, was
in der Anzeige steht — das ist eine Messung und bleibt eine. Die
Rangfolge dagegen ist eine Darstellung, und dort gehoert die
Unterscheidung hin.
"""
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.services import datenguete as dg  # noqa: E402


KRITERIEN = {
    "max_entfernung": {"festanstellung": 30},
    "min_gehalt": 80000,
    "stellentypen": ["festanstellung", "freelance"],
    "gewichtung": {"muss": 7, "plus": 3, "minus": 6, "remote": 3,
                   "naehe": 4, "fern_malus": 5, "gehalt": 8},
}

# Der gemeldete Fall: ein Titel ohne Anzeigentext, Score 101.
OHNE_GRUNDLAGE = {
    "hash": "t:ohne", "title": "Ingenieur Elektrotechnik (m/w/d)",
    "company": "Beispiel Technik GmbH", "location": "Kiel",
    "description": "Ingenieur/in - Elektrotechnik",
    "employment_type": "festanstellung", "score": 101,
}
# Und die Stelle, die darunter stand: vollstaendig, passend, 32 Punkte.
MIT_GRUNDLAGE = {
    "hash": "t:mit", "title": "PLM Berater (m/w/d)",
    "company": "Musterfirma GmbH", "location": "Hamburg",
    "description": "Aufgaben: Betreuung der PLM-Landschaft. " + "x" * 400,
    "distance_km": 12, "employment_type": "festanstellung",
    "remote_level": "hybrid", "salary_min": 95000, "salary_estimated": 0,
    "score": 32,
}


# ── AK 1: drei Zustaende je Dimension ────────────────────────────────

def test_989_jede_dimension_traegt_einen_zustand():
    b = dg.befund(MIT_GRUNDLAGE, KRITERIEN)
    assert set(b) == {d["id"] for d in dg.DIMENSIONEN}
    for dim, eintrag in b.items():
        assert eintrag["zustand"] in dg.ZUSTAENDE, (dim, eintrag)


def test_989_geprueft_verletzt_ungeprueft_sind_unterscheidbar():
    """Der Kern: `verletzt` und `ungeprueft` sehen im Score gleich aus.

    Beide bringen keine Punkte — und bedeuten das Gegenteil voneinander.
    """
    zu_weit = dict(MIT_GRUNDLAGE, distance_km=577)
    ohne_ort = dict(MIT_GRUNDLAGE)
    ohne_ort.pop("distance_km")
    ohne_ort["location"] = "Irgendwo (Region)"

    assert dg.befund(MIT_GRUNDLAGE, KRITERIEN)["entfernung"]["zustand"] == dg.GEPRUEFT
    assert dg.befund(zu_weit, KRITERIEN)["entfernung"]["zustand"] == dg.VERLETZT
    assert dg.befund(ohne_ort, KRITERIEN)["entfernung"]["zustand"] == dg.UNGEPRUEFT


def test_989_geschaetztes_gehalt_ist_ungeprueft_nicht_erfuellt():
    """#827 hat die Regel gezogen: eine Schaetzung zaehlt nicht.

    Dann ist die Dimension aber UNGEPRUEFT — nicht erfuellt.
    """
    geschaetzt = dict(MIT_GRUNDLAGE, salary_min=120000, salary_estimated=1)
    assert dg.befund(geschaetzt, KRITERIEN)["gehalt"]["zustand"] == dg.UNGEPRUEFT


def test_989_ungeprueft_nennt_was_daran_haengt():
    """Ohne das ist "ungeprueft" nur eine Vokabel."""
    b = dg.befund(OHNE_GRUNDLAGE, KRITERIEN)
    assert "traegt" in b["beschreibung"]
    assert "MUSS-Tor" in b["beschreibung"]["traegt"]
    assert "grund" in b["beschreibung"]


# ── AK 3: Vollstaendigkeitsgrad ──────────────────────────────────────

def test_989_vollstaendigkeitsgrad_ist_abrufbar():
    voll = dg.vollstaendigkeit(MIT_GRUNDLAGE, KRITERIEN)
    leer = dg.vollstaendigkeit(OHNE_GRUNDLAGE, KRITERIEN)
    assert voll["belegt"] == voll["gesamt"]
    assert voll["anteil"] == 1.0
    assert leer["belegt"] < leer["gesamt"]
    assert "beschreibung" in leer["ungeprueft"]


def test_989_marke_nur_wo_etwas_fehlt():
    assert dg.kurzmarke(MIT_GRUNDLAGE, KRITERIEN) is None
    marke = dg.kurzmarke(OHNE_GRUNDLAGE, KRITERIEN)
    assert marke["ohne_bewertungsgrundlage"] is True
    assert "Anzeigentext" in marke["text"]


# ── AK 6: der Regressionstest aus dem Issue ──────────────────────────

def test_989_stelle_ohne_text_und_ort_steht_nicht_oben():
    """Woertlich das Akzeptanzkriterium des Issues.

    "Eine Stelle ohne Beschreibung und ohne Ort steht nicht ueber einer
    vollstaendig beschriebenen, passenden Stelle."
    """
    liste = [OHNE_GRUNDLAGE, MIT_GRUNDLAGE]
    sortiert = sorted(liste, key=lambda j: (dg.rang(j), -j["score"]))
    assert sortiert[0]["hash"] == "t:mit", (
        "Nach Score allein stuende der inhaltsleere Titel mit 101 Punkten "
        "ueber der passenden Stelle mit 32.")


def test_989_innerhalb_einer_gruppe_zaehlt_weiter_der_score():
    """Die Trennung darf den Score nicht ersetzen."""
    a = dict(MIT_GRUNDLAGE, hash="a", score=10)
    b = dict(MIT_GRUNDLAGE, hash="b", score=40)
    sortiert = sorted([a, b], key=lambda j: (dg.rang(j), -j["score"]))
    assert sortiert[0]["hash"] == "b"


def test_989_rang_haengt_nur_an_der_bewertungsgrundlage():
    """BEWUSST nicht an der Zahl der ungeprueften Dimensionen.

    Sonst landet fast alles in Gruppe 1 und die Trennung sagt nichts
    mehr — eine unbekannte Entfernung ist alltaeglich, ein fehlender
    Anzeigentext heisst "gar nicht bewertet".
    """
    nur_entfernung_fehlt = dict(MIT_GRUNDLAGE)
    nur_entfernung_fehlt.pop("distance_km")
    nur_entfernung_fehlt["location"] = "Irgendwo (Region)"
    assert dg.rang(nur_entfernung_fehlt) == 0
    assert dg.rang(OHNE_GRUNDLAGE) == 1


# ── AK 4: konfigurierbar ─────────────────────────────────────────────

class _DB:
    def __init__(self, einstellungen=None):
        self._e = dict(einstellungen or {})

    def get_profile_setting(self, key, default=None):
        return self._e.get(key, default)

    def set_profile_setting(self, key, wert):
        self._e[key] = wert


def test_989_vorgabe_ist_nachrangig():
    assert dg.umgang(_DB()) == dg.NACHRANGIG


def test_989_umgang_laesst_sich_umstellen():
    db = _DB()
    assert dg.umgang_setzen(db, dg.MITMISCHEN)["status"] == "gesetzt"
    assert dg.umgang(db) == dg.MITMISCHEN


def test_989_unbekannter_modus_wird_abgewiesen():
    """Eine Einstellung, die nichts tut, ist teurer als eine Absage (#988)."""
    db = _DB()
    ergebnis = dg.umgang_setzen(db, "irgendwas")
    assert "fehler" in ergebnis
    assert dg.umgang(db) == dg.NACHRANGIG


def test_989_mitmischen_stellt_den_alten_stand_her():
    assert dg.sortierschluessel(OHNE_GRUNDLAGE, dg.MITMISCHEN) == 0
    assert dg.sortierschluessel(OHNE_GRUNDLAGE, dg.NACHRANGIG) == 1


def test_989_kaputte_einstellung_faellt_auf_die_vorgabe():
    class _Kaputt(_DB):
        def get_profile_setting(self, key, default=None):
            raise RuntimeError("Einstellungen weg")

    assert dg.umgang(_Kaputt()) == dg.NACHRANGIG


def test_989_streng_wertet_unbekannte_entfernung_wie_eine_weite():
    """Die Nutzerentscheidung aus dem Issue, im Score.

    "Fuer einen Nutzer, dessen Kriterium 'nur remote oder im Nahbereich'
    lautet, ist eine Stelle mit unbekanntem Ort im Zweifel keine
    Nahstelle."
    """
    from bewerbungs_assistent.job_scraper import calculate_score
    krit = dict(KRITERIEN, keywords_muss=["PLM"], keywords_plus=[],
                keywords_minus=[], keywords_ausschluss=[])
    stelle = {"title": "PLM Berater", "company": "Musterfirma GmbH",
              "location": "Irgendwo (Region)", "url": "https://example.invalid/1",
              "description": "PLM-Landschaft betreuen. " + "x" * 300,
              "employment_type": "festanstellung"}

    normal = calculate_score(dict(stelle), dict(krit))
    streng = calculate_score(dict(stelle), dict(krit, _unbekannt_streng=True))
    assert streng < normal, (normal, streng)


def test_989_streng_geht_durch_das_kriterien_nadeloehr():
    """Sonst rechnet der Suchlauf wieder anders als die Neuberechnung.

    Genau der Fehler aus #987 — deshalb steht die Einstellung in den
    Kriterien und nicht in einem der Aufrufer.
    """
    from bewerbungs_assistent.services import scoring_kriterien

    class _VollDB(_DB):
        def get_search_criteria(self):
            return dict(KRITERIEN)

        def get_applications(self):
            return []

    db = _VollDB({dg.EINSTELLUNG: dg.STRENG})
    assert scoring_kriterien.fuer_scoring(db).get("_unbekannt_streng") is True

    db2 = _VollDB()
    assert "_unbekannt_streng" not in scoring_kriterien.fuer_scoring(db2)


# ── AK 2: die Liste zeigt es, nicht nur die Tool-Antwort ─────────────

@pytest.fixture
def echte_db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1739_989_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    datenbank = _db_mod.Database()
    datenbank.initialize()
    assert str(tmpdir) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    datenbank.save_profile({"name": "Test Person"})
    yield datenbank
    datenbank.close()
    os.environ.pop("BA_DATA_DIR", None)
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_989_rest_liste_traegt_den_befund(echte_db):
    """Die Liste im Stellen-Tab speist sich aus /api/jobs.

    "In der Trefferliste, die der Nutzer tatsaechlich ansieht, kommt
    davon nichts an" — das war der Befund. Also muss es hier ankommen.
    """
    import bewerbungs_assistent.dashboard as dash
    dash._db = echte_db
    try:
        echte_db.set_search_criteria("keywords_muss", ["PLM"])
        echte_db.save_jobs([
            dict(OHNE_GRUNDLAGE, source="test"),
            dict(MIT_GRUNDLAGE, source="test"),
        ])
        jobs = echte_db.get_active_jobs()
        dash._guete_anreichern(jobs)
        ohne = next(j for j in jobs if j["title"].startswith("Ingenieur"))
        mit = next(j for j in jobs if j["title"].startswith("PLM"))
        assert ohne.get("datenguete"), "Der Befund fehlt an der Zeile"
        assert "beschreibung" in ohne["datenguete"]["ungeprueft"]
        assert not mit.get("datenguete")
    finally:
        dash._db = None


def test_989_stellen_anzeigen_sortiert_die_liste_richtig(echte_db):
    """AK 6 durch das ECHTE Werkzeug, nicht durch die Hilfsfunktion.

    DoD 8c: eine Regel zaehlt erst, wenn sie im Aufrufpfad landet. Genau
    daran ist #989 entstanden — die Bausteine gab es, sie kamen nur nie
    in der Liste an.
    """
    import asyncio
    import logging

    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import jobs as jobs_tools

    echte_db.set_search_criteria("keywords_muss", ["PLM"])
    echte_db.save_jobs([
        dict(OHNE_GRUNDLAGE, source="test"),
        dict(MIT_GRUNDLAGE, source="test"),
    ])
    mcp = FastMCP("test")
    jobs_tools.register(mcp, echte_db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("stellen_anzeigen")
        res = await tool.run({})
        return res.structured_content if hasattr(res, "structured_content") else res

    ergebnis = asyncio.run(_run())
    # Die Titel tragen ein Status-Symbol als Praefix — deshalb `in`
    # statt `startswith`.
    titel = [s["titel"] for s in ergebnis["stellen"]]
    assert "PLM Berater" in titel[0], (
        "Die vollstaendig beschriebene Stelle muss oben stehen — "
        f"bekommen: {titel}")

    ohne = next(s for s in ergebnis["stellen"] if "Ingenieur" in s["titel"])
    assert ohne.get("datenguete"), "Der Befund fehlt an der Zeile"
    assert ergebnis["datenguete"]["ohne_bewertungsgrundlage"] == 1


def test_989_anreicherung_ueberlebt_eine_kaputte_datenbank():
    """Eine Liste darf nie an ihrer Anreicherung sterben."""
    import bewerbungs_assistent.dashboard as dash
    vorher = dash._db
    dash._db = None
    try:
        jobs = [dict(OHNE_GRUNDLAGE)]
        dash._guete_anreichern(jobs)  # darf nicht werfen
    finally:
        dash._db = vorher


# ── AK 5: Urteile aus Anzeigen-Rumpfen tragen nichts ─────────────────

def test_989_urteil_aus_anzeigenrumpf_zaehlt_nicht():
    from bewerbungs_assistent.services.wiedergaenger import grund_guete
    guete, warum = grund_guete({
        "description": "PLM gesucht.", "dismiss_reason": "falsches_fachgebiet"})
    assert guete == "ohne_grundlage"
    assert "zaehlt nicht mit" in warum


def test_989_geschaetztes_gehalt_bleibt_ein_schwacher_beleg():
    """Die Abstufung bleibt: eine Zahl zeigt in eine Richtung, ein
    Anzeigen-Rumpf in gar keine."""
    from bewerbungs_assistent.services.wiedergaenger import grund_guete
    guete, _ = grund_guete({
        "description": "x" * 400, "dismiss_reason": "gehalt_zu_niedrig",
        "salary_estimated": 1})
    assert guete == "schwach"


# ── Die Schwelle lag siebenmal im Code ───────────────────────────────

def test_989_mindestlaenge_kommt_aus_einer_quelle():
    """Die nackte 50 stand an sieben Stellen — jedes Mal neu getippt."""
    assert dg.MIN_BESCHREIBUNG == 50
    quelle = (Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
              / "tools" / "jobs.py").read_text(encoding="utf-8")
    assert "_dg.MIN_BESCHREIBUNG" in quelle


def test_989_frontend_kennt_dieselbe_schwelle():
    """Sonst sortiert der Browser anders als der Chat (#765-Muster)."""
    js = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "lib"
          / "datenguete.js").read_text(encoding="utf-8")
    assert f"MIN_BESCHREIBUNG = {dg.MIN_BESCHREIBUNG}" in js


def test_989_paritaets_test_laeuft_in_der_ci():
    """DoD 8c: ein Schutz zaehlt erst, wenn er auch aufgerufen wird."""
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows"
                / "tests.yml").read_text(encoding="utf-8")
    assert "datenguete.test.mjs" in workflow
