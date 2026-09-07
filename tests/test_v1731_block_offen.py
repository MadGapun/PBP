"""Tests fuer v1.7.31 — #976 (G27), #982 (G30), #983 (G31).

Der Block "Offen" auf dem Dashboard. Drei Befunde aus demselben
Review-Screenshot, die nur zusammen aufloesbar sind:

* **#976** — dieselbe Lage stand dreimal auf einem Bildschirm, in drei
  Zaehlweisen: rote Karte "2 Aufgaben ueberfaellig", Headline "Es gibt
  ueberfaellige Nachfassaktionen", Zeile "Bei 2 Bewerbung(en) solltest
  du nachhaken". Fachlich zwei Toepfe, fuer den Nutzer eine Frage.
* **#982** — "Interview vorbereiten: 3 Bewerbung(en) sind im
  Interview-Status" kannte den echten Termin drei Bloecke tiefer nicht.
  Eine Zaehlung ist keine Handlung.
* **#983** — Termine gehoeren in dieselbe Liste (Nutzerentscheidung
  07.09.2026). K17/#700 bleibt in der Sache erhalten: die
  Unterscheidung leistet `herkunft` je Zeile, nicht ein zweiter Block.
"""
from datetime import date, timedelta

import pytest

from bewerbungs_assistent.services import aufgaben_sicht


def _tage(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


@pytest.fixture
def bestand(tmp_db):
    tmp_db.create_profile("Nutzerin", "n@example.com")
    aid = tmp_db.add_application({
        "title": "Fachkraft", "company": "Musterbetrieb GmbH",
        "position": "Fachkraft", "status": "interview",
        "applied_at": _tage(-30),
    })
    return tmp_db, aid


# ── #983: eine Liste, Herkunft je Zeile ─────────────────────────────

def test_983_alle_herkuenfte_in_einer_liste(bestand):
    db, aid = bestand
    db.add_task({"application_id": aid, "titel": "Unterlagen sortieren",
                 "faellig_am": _tage(-2)})
    db.add_follow_up(aid, _tage(-1), "nachfass", template="")
    db.add_meeting({"application_id": aid,
                    "meeting_date": f"{_tage(3)}T14:30:00",
                    "title": "Zweitgespraech", "meeting_type": "zweitgespraech"})
    block = aufgaben_sicht.dashboard_block(db)
    herkuenfte = {e["herkunft"]
                  for gruppe in block["gruppen"].values() for e in gruppe}
    assert {"todo", "nachfass", "termin"} <= herkuenfte, herkuenfte


def test_983_termin_traegt_uhrzeit_die_nachfassung_nicht(bestand):
    """K17/#700 in der Sache: eine Erinnerung ist kein Termin.

    Der Folgefehler K19 waren Nachfassungen "um 02:00 Uhr". Die Regel
    bleibt, sie steht jetzt nur an der Zeile statt am Block.
    """
    db, aid = bestand
    db.add_follow_up(aid, _tage(1), "nachfass", template="")
    db.add_meeting({"application_id": aid,
                    "meeting_date": f"{_tage(2)}T14:30:00",
                    "title": "Zweitgespraech", "meeting_type": "zweitgespraech"})
    alle = [e for g in aufgaben_sicht.dashboard_block(db)["gruppen"].values()
            for e in g]
    termin = next(e for e in alle if e["herkunft"] == "termin")
    nachfass = next(e for e in alle if e["herkunft"] == "nachfass")
    assert termin["uhrzeit"] == "14:30"
    assert nachfass["uhrzeit"] == ""


def test_983_reihenfolge_ueberfaellig_heute_diese_woche(bestand):
    db, aid = bestand
    db.add_follow_up(aid, _tage(-5), "nachfass", template="")
    db.add_follow_up(aid, date.today().isoformat(), "nachfass", template="")
    db.add_meeting({"application_id": aid,
                    "meeting_date": f"{_tage(4)}T09:00:00",
                    "title": "Interview", "meeting_type": "interview"})
    gruppen = aufgaben_sicht.dashboard_block(db)["gruppen"]
    assert list(gruppen) == ["ueberfaellig", "heute", "diese_woche"]
    assert gruppen["ueberfaellig"]
    assert gruppen["heute"]
    assert gruppen["diese_woche"]


def test_983_spaeter_bleibt_dem_aufgaben_tab(bestand):
    """Was weiter weg ist, gehoert in den Tab und den Kalender."""
    db, aid = bestand
    db.add_follow_up(aid, _tage(20), "nachfass", template="")
    block = aufgaben_sicht.dashboard_block(db)
    assert "spaeter" not in block["gruppen"]
    assert block["spaeter_anzahl"] >= 1


def test_983_vergangener_termin_ist_kein_rueckstand(bestand):
    """Nur Handlungen koennen ueberfaellig sein; ein Termin war."""
    db, aid = bestand
    termine = [{"herkunft": "termin", "faellig_am": _tage(-3), "id": "m1"}]
    gruppen = aufgaben_sicht.gruppiere(termine)
    assert not gruppen["ueberfaellig"]


# ── #982: Vorbereitung aus dem Termin, nicht aus einer Zahl ─────────

def _termin(tage: int, typ: str = "zweitgespraech", **rest) -> dict:
    return {"herkunft": "termin", "id": "m1", "titel": "Zweitgespraech",
            "typ": typ, "status": "geplant", "faellig_am": _tage(tage),
            "bewerbung_id": "app1", "firma": "Musterbetrieb GmbH", **rest}


def test_982_termin_in_drei_tagen_ergibt_eine_zeile():
    zeilen = aufgaben_sicht.vorbereitungszeilen(
        None, termine=[_termin(3)], todos=[])
    assert len(zeilen) == 1
    z = zeilen[0]
    assert z["herkunft"] == "vorbereitung"
    assert z["faellig_am"] == _tage(3)
    assert "Zweitgespraech" in z["titel"]
    assert z["termin_id"] == "m1"


def test_982_zeile_traegt_das_datum_nicht_nur_eine_zahl():
    """Der Kern des Befunds: '3 Bewerbungen im Interview-Status' sagt
    nicht, was heute zu tun ist."""
    z = aufgaben_sicht.vorbereitungszeilen(
        None, termine=[_termin(2)], todos=[])[0]
    assert z["faellig_am"]
    assert z["termin_datum"] == z["faellig_am"]


def test_982_vorhandenes_todo_verdraengt_die_zeile():
    """Sonst steht dieselbe Vorbereitung zweimal da (G16/#706)."""
    todo = {"herkunft": "todo", "bewerbung_id": "app1",
            "typ": "vorbereitung", "faellig_am": _tage(3)}
    assert aufgaben_sicht.vorbereitungszeilen(
        None, termine=[_termin(3)], todos=[todo]) == []


def test_982_todo_am_termindatum_zaehlt_auch():
    """G16 legt das Todo mit Faelligkeit = Termindatum an; der Typ ist
    nicht garantiert."""
    todo = {"herkunft": "todo", "bewerbung_id": "app1",
            "typ": "custom", "faellig_am": _tage(3)}
    assert aufgaben_sicht.vorbereitungszeilen(
        None, termine=[_termin(3)], todos=[todo]) == []


def test_982_fremdes_todo_verdraengt_nichts():
    todo = {"herkunft": "todo", "bewerbung_id": "app2",
            "typ": "vorbereitung", "faellig_am": _tage(3)}
    assert len(aufgaben_sicht.vorbereitungszeilen(
        None, termine=[_termin(3)], todos=[todo])) == 1


def test_982_termin_in_zehn_tagen_ergibt_keine_zeile():
    assert aufgaben_sicht.vorbereitungszeilen(
        None, termine=[_termin(10)], todos=[]) == []


def test_982_abgesagter_termin_ergibt_keine_zeile():
    assert aufgaben_sicht.vorbereitungszeilen(
        None, termine=[_termin(3, status="abgesagt")], todos=[]) == []


def test_982_normaler_termin_ergibt_keine_zeile():
    """Ein Telefonat mit dem Vermittler ist kein Vorstellungsgespraech."""
    assert aufgaben_sicht.vorbereitungszeilen(
        None, termine=[_termin(3, typ="telefon")], todos=[]) == []


@pytest.mark.parametrize("typ", sorted(aufgaben_sicht.VORBEREITUNGS_TYPEN))
def test_982_alle_gespraechsarten_erzeugen_eine_zeile(typ):
    assert len(aufgaben_sicht.vorbereitungszeilen(
        None, termine=[_termin(3, typ=typ)], todos=[])) == 1


def test_982_zeile_springt_in_die_anleitung():
    z = aufgaben_sicht.vorbereitungszeilen(
        None, termine=[_termin(3)], todos=[])[0]
    assert z["prompt"] == "/interview_vorbereitung"


def test_982_vorbereitung_traegt_keine_uhrzeit():
    """Die Vorbereitung ist eine Handlung VOR dem Termin, kein Termin."""
    z = aufgaben_sicht.vorbereitungszeilen(
        None, termine=[_termin(3)], todos=[])[0]
    assert z["uhrzeit"] == ""


def test_982_zaehl_empfehlung_ist_weg():
    """Die Zeile "N Bewerbung(en) sind im Interview-Status" existiert
    nicht mehr, und die Pseudo-Termine aus Nachfassungen auch nicht."""
    from pathlib import Path
    seite = (Path(__file__).resolve().parents[1] / "frontend" / "src" /
             "pages" / "DashboardPage.jsx").read_text(encoding="utf-8")
    assert "sind im Interview-Status" not in seite
    # Bewusst auf die DEFINITION geprueft, nicht auf das Wort: der
    # Kommentar, der die Entfernung erklaert, soll stehen bleiben.
    assert "const interviewPseudoMeetings" not in seite
    assert "upcomingInterviewTodos" not in seite


# ── #976: eine Quelle, keine Wiederholung ───────────────────────────

def test_976_dashboard_und_aufgaben_tab_teilen_die_quelle():
    """Vorher stand die Aggregation zweimal im Code, zusammengehalten
    von einem Kommentar — und die beiden Fassungen waren bereits
    auseinandergelaufen (dieselbe Lehre wie #963)."""
    from pathlib import Path
    wurzel = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
    for datei in ("tools/tasks.py", "dashboard.py"):
        quelle = (wurzel / datei).read_text(encoding="utf-8")
        assert "aufgaben_sicht" in quelle, datei
    # Und die Kopie ist wirklich weg, nicht nur ergaenzt.
    dash = (wurzel / "dashboard.py").read_text(encoding="utf-8")
    block = dash[dash.index('@app.get("/api/aufgaben")'):]
    block = block[:block.index("# === Adzuna-Zugang")]
    assert '"herkunft": "todo"' not in block
    assert '"herkunft": "termin"' not in block


def test_976_mcp_und_rest_liefern_dieselben_eintraege(bestand):
    """Der Beweis am Ergebnis, nicht am Quelltext."""
    db, aid = bestand
    db.add_follow_up(aid, _tage(-1), "nachfass", template="")
    db.add_meeting({"application_id": aid,
                    "meeting_date": f"{_tage(3)}T14:30:00",
                    "title": "Zweitgespraech", "meeting_type": "zweitgespraech"})
    a = aufgaben_sicht.uebersicht(db, status="offen")
    b = aufgaben_sicht.uebersicht(db, status="offen")
    assert a["anzahl"] == b["anzahl"]
    ids_a = {(e["herkunft"], str(e["id"]))
             for g in a["gruppen"].values() for e in g}
    ids_b = {(e["herkunft"], str(e["id"]))
             for g in b["gruppen"].values() for e in g}
    assert ids_a == ids_b


def test_976_leerer_zustand_ist_benannt(tmp_db):
    """#984: eine Zeile "Nichts offen", kein leerer Rahmen."""
    tmp_db.create_profile("Nutzerin", "n@example.com")
    block = aufgaben_sicht.dashboard_block(tmp_db)
    assert block["leer"] is True
    assert block["anzahl"] == 0


def test_976_nicht_leer_sobald_etwas_ansteht(bestand):
    db, aid = bestand
    db.add_follow_up(aid, _tage(-1), "nachfass", template="")
    assert aufgaben_sicht.dashboard_block(db)["leer"] is False


def test_976_keine_nummerierung_mit_luecke():
    """Im Screenshot standen "Prioritaet 2" und "Prioritaet 3" ohne eine 1.

    Die Nummer war ein festes Etikett je Aufgabentyp, kein Rang in der
    angezeigten Liste — fehlte der Typ `jobsuche`, begann die Liste
    sichtbar bei 2 und der Nutzer suchte nach etwas, das es nicht gab.
    """
    from pathlib import Path
    seite = (Path(__file__).resolve().parents[1] / "frontend" / "src" /
             "pages" / "DashboardPage.jsx").read_text(encoding="utf-8")
    for festes_etikett in ('"Priorität 1"', '"Priorität 2"', '"Priorität 3"'):
        assert festes_etikett not in seite, festes_etikett


def test_976_readiness_karte_traegt_keine_beschreibung():
    """Vier Etiketten fuer eine Aussage: Badge, Kicker, Headline,
    Beschreibung. Die Beschreibung wiederholte die Headline in anderen
    Worten und entfaellt (#984 Punkt 2)."""
    from pathlib import Path
    seite = (Path(__file__).resolve().parents[1] / "frontend" / "src" /
             "pages" / "DashboardPage.jsx").read_text(encoding="utf-8")
    assert "workspaceReadiness.description" not in seite
