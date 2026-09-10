"""Tests fuer #937 — eine defekte Quelle melden, mit Bedarf.

Nutzerwunsch vom 19.08.2026. Der Wert liegt ausdruecklich NICHT im
Melden des Defekts — den kennt PBP bereits —, sondern in der
Priorisierung durch Bedarf: von 32 Quellen laufen 10, und es ist nicht
erkennbar, welche der toten jemand tatsaechlich braucht.

Die acht Akzeptanzkriterien stehen hier einzeln (DoD 8a).
"""
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import quellen_meldung as qm  # noqa: E402


DEFEKT = {
    "scraper_name": "beispielboerse",
    "error_class": "kaputt",
    "last_error": "defekt: Suche liefert 200, aber 0 Treffer im HTML",
    "consecutive_failures": 7,
    "consecutive_silent": 3,
    "total_runs": 40,
    "total_successes": 0,
    "last_run": "2026-09-10T08:00:00+00:00",
    "last_success": None,
    "is_active": 0,
}


# --------------------------------- AK 1/7: wer bekommt einen Knopf


@pytest.mark.parametrize("zeile", [
    DEFEKT,
    {"scraper_name": "x", "last_error": "timeout nach 90 s"},
    {"scraper_name": "y", "consecutive_failures": 5},
])
def test_937_defekte_quellen_sind_meldbar(zeile):
    """AK 1: bei `defekt` und `timeout` erscheint der Knopf."""
    assert qm.ist_meldbar(zeile) is True


def test_937_eine_abgeschaltete_quelle_bekommt_keinen_knopf():
    """AK 7: `deprecated` ist eine ENTSCHEIDUNG, kein Defekt.

    Eine Meldung darueber haette keinen Adressaten — und #906 hat
    ausdruecklich getrennt: `deprecated` (Registry, bewusst) und
    `auto_deaktiviert` (Automatik) sind zwei verschiedene Dinge in zwei
    verschiedenen Feldern.
    """
    assert qm.ist_meldbar(
        {"scraper_name": "alt", "last_error": "deprecated"}) is False
    assert qm.ist_meldbar(
        {"scraper_name": "alt", "deprecated": True,
         "last_error": "defekt: kaputt"}) is False


def test_937_eine_laufende_quelle_ist_nicht_meldbar():
    """Die Gegenrichtung — sonst steht der Knopf ueberall (#929)."""
    assert qm.ist_meldbar({
        "scraper_name": "laeuft", "consecutive_failures": 0,
        "total_runs": 50, "total_successes": 47}) is False


# ------------------------------------- AK 4: der PII-kritische Teil


def test_937_die_meldung_traegt_nur_technische_quellendaten():
    """AK 4: nachweislich keine Suchbegriffe, Profil-, Stellen- oder
    Kontaktdaten.

    Der Text entsteht aus einer ABSCHLIESSENDEN Positivliste, nicht aus
    einem dict-Abzug. Ein dict-Abzug waere heute sauber und beim
    naechsten neuen Feld nicht mehr — genau die Bauform, aus der die
    PII-Vorfaelle dieses Projekts entstanden sind.
    """
    # Eine Zeile, die (hypothetisch) verseucht ist.
    verseucht = dict(DEFEKT)
    verseucht.update({
        "keywords_muss": ["plm", "teamcenter"],
        "profile_id": "e913acc3",
        "company": "Halbleiterwerk Nord GmbH",
        "email": "person@example.com",
        "title": "Senior Consultant",
        "standort": "Musterstadt",
    })
    text = qm.bericht(verseucht, version="1.7.75")

    for verboten in ("plm", "teamcenter", "e913acc3", "Halbleiterwerk",
                     "person@example.com", "Senior Consultant",
                     "Musterstadt"):
        assert verboten not in text, (
            f"{verboten!r} steht in der Meldung — sie geht oeffentlich "
            "auf GitHub.")
    # Die technischen Angaben stehen sehr wohl drin.
    assert "beispielboerse" in text
    assert "kaputt" in text
    assert "1.7.75" in text


def test_937_die_positivliste_enthaelt_kein_verbotenes_feld():
    """Der Guard gegen den naechsten Eintrag.

    Wer die Liste erweitert, soll nicht versehentlich ein Feld
    aufnehmen, das ueber den MENSCHEN etwas sagt statt ueber die
    Quelle.
    """
    erlaubt = {schluessel for schluessel, _ in qm.ERLAUBTE_FELDER}
    for verboten in qm.VERBOTEN:
        treffer = [f for f in erlaubt if verboten in f]
        assert not treffer, (
            f"Die Positivliste enthaelt {treffer} — das faellt unter "
            f"{verboten!r} und gehoert nicht in eine oeffentliche Meldung.")


def test_937_ein_neues_feld_landet_nicht_von_allein_in_der_meldung():
    """Der eigentliche Schutz: die Liste ist abschliessend."""
    mit_neuem = dict(DEFEKT)
    mit_neuem["irgendein_neues_feld"] = "Inhalt-Zx9-der-nicht-raus-darf"
    assert "Zx9" not in qm.bericht(mit_neuem)


# ------------------------------------------- AK 2/8: die Prefill-URL


def test_937_die_url_ist_ein_formular_und_kein_versand():
    """AK 2: PBP sendet nichts und braucht kein Token."""
    url = qm.melde_url(DEFEKT, version="1.7.75")
    assert url.startswith("https://github.com/MadGapun/PBP/issues/new")
    assert "template=quelle-defekt.yml" in url
    assert "token" not in url.lower()


def test_937_die_url_bleibt_unter_zweitausend_zeichen():
    """AK 8: laengere Prefill-URLs werden unzuverlaessig.

    Gekuerzt wird der Diagnoseblock, nicht die URL — sonst entstuende
    eine kaputte Adresse statt einer kuerzeren Meldung.
    """
    riesig = dict(DEFEKT)
    riesig["last_error"] = "Sehr lange Fehlermeldung. " * 400
    riesig["deaktiviert_grund"] = "Noch eine lange Begruendung. " * 400
    url = qm.melde_url(riesig, version="1.7.75")
    assert len(url) <= qm.MAX_URL, f"URL ist {len(url)} Zeichen lang."
    # Die Kernangabe ueberlebt die Kuerzung.
    assert "beispielboerse" in url


# ---------------------------------------- AK 6: schon gemeldet?


class _Antwort:
    def __init__(self, status=200, daten=None):
        self.status_code = status
        self._daten = daten or {}

    def json(self):
        return self._daten


class _Client:
    def __init__(self, antwort):
        self._antwort = antwort
        self.aufrufe = 0

    def get(self, url, **kwargs):
        self.aufrufe += 1
        return self._antwort


def test_937_eine_vorhandene_meldung_wird_gefunden():
    """AK 6: statt ein zweites Issue anzulegen, wird darauf verwiesen."""
    client = _Client(_Antwort(200, {"items": [
        {"number": 940, "title": "Quelle defekt: beispielboerse",
         "html_url": "https://github.com/MadGapun/PBP/issues/940"}]}))
    erg = qm.vorhandene_meldung("beispielboerse", client=client)
    assert erg["geprueft"] is True
    assert erg["gefunden"][0]["nummer"] == 940


def test_937_ein_fehlschlag_blockiert_den_melde_weg_nicht():
    """Ein Schutz, der den Nutzer aussperrt, wenn er selbst ausfaellt,
    ist schlimmer als keiner.

    Die Suche laeuft unangemeldet und ist ratenbegrenzt. Faellt sie
    aus, fehlt der Hinweis — mehr nicht.
    """
    class _Kaputt:
        def get(self, *a, **k):
            raise RuntimeError("Netz weg")

    erg = qm.vorhandene_meldung("beispielboerse", client=_Kaputt())
    assert erg["geprueft"] is False
    assert erg["gefunden"] == []
    # Der Weg zum Nachsehen bleibt trotzdem da.
    assert erg["suche"].startswith("https://github.com/search")


def test_937_das_angebot_bleibt_bei_einem_fehlschlag_nutzbar():
    class _Kaputt:
        def get(self, *a, **k):
            raise RuntimeError("Netz weg")

    angebot = qm.angebot(DEFEKT, version="1.7.75", client=_Kaputt())
    assert angebot is not None
    assert angebot["url"]
    assert angebot["bericht"]


def test_937_eine_nicht_meldbare_quelle_bekommt_kein_angebot():
    assert qm.angebot({"scraper_name": "alt", "last_error": "deprecated"}) is None


# ------------------------------------ AK 3/5: Dialog und Template


def test_937_der_text_steht_vor_dem_oeffnen_da():
    """AK 3: wer nicht sieht, was er meldet, kann nicht entscheiden, ob
    er es melden will — und die Meldung landet oeffentlich."""
    seite = (_repo() / "frontend" / "src" / "pages"
             / "SettingsPage.jsx").read_text(encoding="utf-8")
    start = seite.index("Quelle melden")
    assert "meldungOeffnen" in seite[start - 400:start + 200]
    # Der Dialog zeigt den Bericht. Die Quelltext-REIHENFOLGE taugt hier
    # nicht als Beleg — die Fusszeile eines Modals steht im JSX vor dem
    # Rumpf und wird trotzdem darunter gerendert (dieselbe Falle wie
    # beim Anker in #1009). Geprueft wird die Sache: der Bericht ist im
    # Dialog, und `window.open` haengt an einem KLICK, laeuft also nicht
    # beim Rendern.
    dialog = seite[seite.index("open={Boolean(meldung)}"):]
    dialog = dialog[:dialog.index("</Modal>")]
    assert "meldung?.bericht" in dialog, "Der Bericht steht nicht im Dialog."
    oeffnen = dialog.index("window.open")
    davor = dialog[:oeffnen]
    assert "onClick" in davor[-200:], (
        "window.open haengt nicht an einem Klick — dann oeffnet sich das "
        "Formular beim Rendern, bevor jemand den Text gesehen hat.")


def test_937_das_template_existiert_und_fragt_nach_dem_bedarf():
    """AK 5: Pflichtfeld zur Begruendung, warum die Quelle gebraucht wird.

    Das ist der eigentliche Zweck der Meldung. Ohne dieses Feld waere
    sie wieder nur eine Defektmeldung — und der Defekt ist bekannt.
    """
    pfad = (_repo() / ".github" / "ISSUE_TEMPLATE" / "quelle-defekt.yml")
    assert pfad.exists(), "Das Template fehlt."
    inhalt = pfad.read_text(encoding="utf-8")
    assert "id: bedarf" in inhalt
    # Das Bedarfsfeld ist PFLICHT.
    bedarf = inhalt[inhalt.index("id: bedarf"):]
    assert "required: true" in bedarf[:bedarf.index("- type:", 10)], (
        "Das Bedarfsfeld ist nicht als Pflichtfeld markiert.")


def test_937_das_template_ist_gueltiges_yaml():
    """Ein kaputtes Template zeigt GitHub als leeres Formular — ohne
    Fehlermeldung."""
    yaml = pytest.importorskip("yaml")
    pfad = (_repo() / ".github" / "ISSUE_TEMPLATE" / "quelle-defekt.yml")
    daten = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    assert daten["name"] and daten["body"]
    assert daten["labels"] == [qm.LABEL], (
        "Das Label im Template weicht von dem in der Prefill-URL ab — "
        "dann findet die Dublettenpruefung nichts.")


def test_937_der_endpunkt_weist_nicht_meldbare_quellen_ab(tmp_path):
    """`deprecated` bekommt eine Begruendung, keinen leeren Dialog."""
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database

    datenbank = Database(db_path=tmp_path / "test.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path)

    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient

    dash._db = datenbank
    try:
        datenbank.update_scraper_health("altquelle", "fail",
                                        detail="deprecated")
        datenbank.connect().execute(
            "UPDATE scraper_health SET last_error='deprecated' "
            "WHERE scraper_name='altquelle'")
        datenbank.connect().commit()
        tc = TestClient(dash.app)
        antwort = tc.get("/api/scraper-health/altquelle/meldung")
        assert antwort.status_code == 409
        assert "Entscheidung" in antwort.json().get("grund", "")

        assert tc.get("/api/scraper-health/gibtesnicht/meldung"
                      ).status_code == 404
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)
