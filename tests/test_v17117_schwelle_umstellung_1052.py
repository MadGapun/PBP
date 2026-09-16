"""Tests fuer #1052 — die Schwelle meint seit der Trennung etwas anderes.

Bis v1.7.116 war `score` die Summe aus Fachwert und Rahmen. Seit der
Trennung ist er der Fachwert allein, also eine kleinere Zahl. Eine
gespeicherte Schwelle filtert damit schaerfer, **ohne dass jemand sie
angefasst hat** — dieselbe Lage wie in #1012 und #988, und dieselbe
Antwort: benennen statt still umdeuten.

Der vorgeschlagene neue Wert kommt aus dem BACKTEST, nicht aus einer
Umrechnungsformel (Nutzerantwort 16.09.2026). Eine Formel waere geraten;
der Backtest rechnet aus der eigenen Bewerbungshistorie.

Jede Haertung in beide Richtungen (#966): neben dem Fall, der melden
MUSS, steht der, der schweigen muss.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest

from bewerbungs_assistent.services import schwellen_umstellung as su


# == Die billige Frage: steht eine Alt-Schwelle da? ===================

class _FakeDB:
    """Nur was `offen` liest — mehr darf es nicht sein.

    Der Umfang dieser Attrappe IST die Zusicherung: haengt die Bedingung
    eines Tages an etwas Teurem, faellt sie hier mit AttributeError um.
    """

    def __init__(self, min_score=0, auto_ignore=0, marke=None):
        self._krit = {"min_score_schwelle": min_score}
        self._auto = auto_ignore
        self._marke = marke
        self.geschrieben = []

    def get_search_criteria(self):
        return dict(self._krit)

    def get_scoring_config(self, dimension=None):
        return [{"dimension": "schwellenwert", "sub_key": "auto_ignore",
                 "value": self._auto}]

    def get_profile_setting(self, key, default=None):
        return self._marke if key == su.MARKE else default

    def set_profile_setting(self, key, value):
        self.geschrieben.append((key, value))
        if key == su.MARKE:
            self._marke = value


def test_ohne_gesetzte_schwelle_schweigt_der_hinweis():
    """Ein frisches Profil hat nichts umzudeuten.

    Ohne diese Richtung haette der Hinweis JEDEN Anwender beim ersten
    Start getroffen — genau der Fehlalarm aus #1008/#929.
    """
    befund = su.offen(_FakeDB(min_score=0, auto_ignore=0))
    assert befund["betroffen"] is False
    assert "keine Schwelle" in befund["grund"]


@pytest.mark.parametrize("min_score, auto_ignore, erwartet", [
    (7, 0, {"min_score_schwelle"}),
    (0, 12, {"auto_ignore"}),
    (7, 12, {"min_score_schwelle", "auto_ignore"}),
])
def test_jede_gesetzte_schwelle_wird_benannt(min_score, auto_ignore, erwartet):
    """Es sind ZWEI, und sie wirken an verschiedenen Stellen (#1008).

    Nur eine davon zu nennen hiesse, den Menschen die andere suchen zu
    lassen — und die eine wirkt beim Speichern, die andere in der Liste.
    """
    befund = su.offen(_FakeDB(min_score=min_score, auto_ignore=auto_ignore))
    assert befund["betroffen"] is True
    assert set(befund["schwellen"]) == erwartet
    assert "FACHWERT" in befund["erklaerung"]


def test_der_hinweis_rechnet_keinen_backtest():
    """Er laeuft bei jedem Seitenaufbau — der Backtest darf nicht mit.

    Die Attrappe kennt `get_applications` gar nicht; ein Backtest
    scheiterte hier mit AttributeError statt still teuer zu werden. Der
    Stolperdraht sagt es deutlicher.
    """
    ruf = []

    from bewerbungs_assistent.services import kalibrierung

    def _stolperdraht(*a, **k):  # pragma: no cover — darf nie laufen
        ruf.append(a)
        raise AssertionError("offen() darf keinen Backtest rechnen")

    alt = kalibrierung.backtest
    kalibrierung.backtest = _stolperdraht
    try:
        su.offen(_FakeDB(min_score=7))
    finally:
        kalibrierung.backtest = alt
    assert not ruf


def test_nach_dem_abhaken_schweigt_er_auch_bei_gesetzter_schwelle():
    """Wer die Schwelle bewusst LAESST, hat entschieden.

    Ein Hinweis, der eine Entscheidung nicht akzeptiert, wird zur Tapete
    (#929). Und die Schwelle steht danach ja weiterhin da — ohne Marke
    meldete er also fuer immer.
    """
    db = _FakeDB(min_score=7)
    assert su.offen(db)["betroffen"] is True
    su.abhaken(db, "bewusst gelassen")
    befund = su.offen(db)
    assert befund["betroffen"] is False
    assert befund["grund"] == "bereits angesehen"


def test_der_vorschlag_rechnet_einen_uebergebenen_lauf_nicht_neu():
    """Der Knopf des Hinweises zeigt auf `kalibrierung_backtest`.

    Beide rechnen dieselbe Zahl; zweimal derselbe Lauf waere #963 mit
    Rechenzeit. Deshalb reicht der Backtest sein Ergebnis durch.
    """
    from bewerbungs_assistent.services import kalibrierung

    def _darf_nicht(*a, **k):  # pragma: no cover
        raise AssertionError("ein uebergebener Lauf wird nicht wiederholt")

    fertig = {"varianten": {"aktuell": {
        "schwellen_vorschlag": 4.2, "schwellen_formel": "q25 x 0,8",
        "bewerbungen_unter_vorschlag": 1, "aussortierte_ueber_vorschlag": 2}}}
    alt = kalibrierung.backtest
    kalibrierung.backtest = _darf_nicht
    try:
        befund = su.vorschlag(_FakeDB(min_score=7), ergebnis=fertig)
    finally:
        kalibrierung.backtest = alt
    assert befund["vorschlag"] == 4.2
    assert befund["formel"] == "q25 x 0,8"
    assert befund["alt"]["min_score_schwelle"] == 7
    # Der Weg zum Setzen steht dabei — eine Zahl ohne Weg ist ein
    # Befund, den der Mensch selbst zusammensuchen muss (#927).
    assert "suchkriterien_setzen" in befund["setzen_mit"]


def test_ohne_grundlage_wird_nichts_geraten():
    """Kein Bestand, kein Vorschlag — und das wird gesagt.

    Eine erfundene Zahl in einer Schwelle waere schlimmer als keine:
    man verlaesst sich auf sie (#989, #1006).
    """
    leer = {"varianten": {"aktuell": {"schwellen_vorschlag": None,
                                      "hinweis": "keine Bewerbungen"}}}
    befund = su.vorschlag(_FakeDB(min_score=7), ergebnis=leer)
    assert "vorschlag" not in befund
    assert befund["hinweis"]


# == Die Wege, die abhaken ===========================================

@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17117_schwelle_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def test_die_anzeige_nennt_die_umstellung_und_danach_nicht_mehr(umgebung):
    """`scoring_konfigurieren('anzeigen')` ist der Ort, an dem jemand
    seine Schwellen ansieht — dort gehoert der Befund hin (#989: ein
    Befund, den nur ein Werkzeug kennt, ist kein Befund)."""
    db, mcp = umgebung
    db.set_search_criteria("min_score_schwelle", 15)

    res = _call(mcp, "scoring_konfigurieren", {"aktion": "anzeigen"})
    assert "schwelle_nach_umstellung_pruefen" in res, res
    assert res["schwelle_nach_umstellung_pruefen"]["schwellen"][
        "min_score_schwelle"] == 15

    su.abhaken(db, "im Test angesehen")
    res2 = _call(mcp, "scoring_konfigurieren", {"aktion": "anzeigen"})
    assert "schwelle_nach_umstellung_pruefen" not in res2


def test_suchkriterien_setzen_kennt_die_schwelle_und_hakt_ab(umgebung):
    """Der Weg wurde an drei Stellen so genannt — es gab ihn nicht.

    `suchkriterien_setzen(min_score_schwelle=N)` stand in der Anzeige,
    im Filtertrichter und im Umstellungs-Hinweis, und das Werkzeug hatte
    den Parameter nicht. Das ist #1000 in Gegenrichtung: dort ein
    Parameter ohne Leser, hier ein Leser ohne Parameter.
    """
    db, mcp = umgebung
    db.set_search_criteria("min_score_schwelle", 15)
    assert su.offen(db)["betroffen"] is True

    res = _call(mcp, "suchkriterien_setzen", {"min_score_schwelle": 4})
    assert res["status"] == "gespeichert"
    assert float(db.get_search_criteria()["min_score_schwelle"]) == 4.0
    assert "schwelle" in res
    # Wer sie gesetzt hat, hat sie angesehen.
    assert su.offen(db)["betroffen"] is False


def test_der_anzeigefilter_hakt_ebenfalls_ab(umgebung):
    """Die zweite Schwelle wirkt in der LISTE (#1008) und ist derselbe
    Vorgang — wer sie setzt, hat die Umstellung zur Kenntnis genommen."""
    db, mcp = umgebung
    db.set_search_criteria("min_score_schwelle", 15)
    res = _call(mcp, "scoring_konfigurieren",
                {"aktion": "setzen", "dimension": "schwellenwert",
                 "sub_key": "auto_ignore", "wert": 3})
    assert res.get("status") == "gespeichert", res
    assert su.offen(db)["betroffen"] is False


def test_der_weg_ueber_die_oberflaeche_hakt_auch_ab(umgebung):
    """Der Regler im Profil-Tab geht ueber `/api/search-criteria`.

    Ohne diese Zeile haette der Hinweis genau den Menschen weiter
    ermahnt, der ihm gefolgt ist — auf dem bequemeren Weg.
    """
    db, _ = umgebung
    db.set_search_criteria("min_score_schwelle", 15)
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as _dash
    importlib.reload(_dash)
    _dash._db = db
    with TestClient(_dash.app) as client:
        antwort = client.post("/api/search-criteria",
                              json={"min_score_schwelle": 4})
    assert antwort.status_code == 200, antwort.text
    assert su.offen(db)["betroffen"] is False


def test_der_hinweis_im_stellen_tab_haengt_an_derselben_frage(umgebung):
    """Ein zweiter Mechanismus fuer dieselbe Frage waere #963.

    Die Bedingung des Onboarding-Hints ruft `offen` — sie rechnet nicht
    selbst nach, ob eine Schwelle aus der alten Skala dasteht.
    """
    db, _ = umgebung
    from bewerbungs_assistent.services import onboarding_hints
    importlib.reload(onboarding_hints)

    def _ids():
        return [h["id"] for h in onboarding_hints.list_active_hints(db)]

    assert "c83_schwelle_nach_score_trennung" not in _ids()
    db.set_search_criteria("min_score_schwelle", 15)
    assert "c83_schwelle_nach_score_trennung" in _ids()
    su.abhaken(db, "angesehen")
    assert "c83_schwelle_nach_score_trennung" not in _ids()


def test_der_positive_deckel_erklaert_sich_nach_der_trennung(umgebung):
    """Der Schluessel heisst weiter "rahmen", die Groesse ist eine andere.

    Remote, Naehe und Gehalt stehen seit der Trennung im Rahmenwert und
    werden gar nicht mehr gedeckelt; gedeckelt werden die PLUS-Begriffe
    innerhalb des Fachwerts. Eine Erklaerung, die etwas anderes
    beschreibt als der Code tut, ist teurer als keine.
    """
    db, mcp = umgebung
    res = _call(mcp, "scoring_konfigurieren", {"aktion": "anzeigen"})
    text = res["deckel_erklaert"]["rahmen"]["bedeutet"]
    assert "PLUS" in text and "MUSS" in text
    assert "nicht gedeckelt" in text
