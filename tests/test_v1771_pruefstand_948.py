"""Tests fuer #948 — die Sichtung hinterlaesst eine Spur.

Nutzerbeobachtung vom 21.08.2026, mit zwei belegten Faellen:

    "Beim naechsten Sichten stehen beide Stellen wieder da, als waeren
    sie ungeprueft, und die Arbeit muesste erneut geleistet werden."

#1007 hat die HAELFTE davon geloest: ein gelesenes Urteil haengt seit
v1.7.61 an der Stelle. Was fehlte, steht hier als Test — jedes der
sieben Akzeptanzkriterien einzeln (DoD 8a).
"""
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad — der Test muss auch aus einem fremden
    Arbeitsverzeichnis laufen (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import passung  # noqa: E402


@pytest.fixture
def db(tmp_path):
    """Isolierte Datenbank. Der Env-Var heisst BA_DATA_DIR — ein
    falscher Name faellt STILL auf die echte AppData-DB zurueck."""
    import importlib

    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database()
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _stelle(db, hash_="948aaa", score=20.0):
    # Der Titel traegt den Hash: zwei Stellen mit gleichem Titel und
    # gleicher Firma erkennt `save_jobs` als Duplikat (#641) und
    # sortiert die zweite aus — sie faellt dann aus der Liste, und der
    # Test misst etwas anderes als er behauptet.
    db.save_jobs([{
        "hash": hash_,
        "title": f"Testrolle Quintus {hash_}",
        "company": "Halbleiterwerk Nord GmbH",
        "url": "https://example.com/stellen/948",
        "source": "manuell",
        "description": "Eine Anzeige mit genug Text fuer die Pruefungen. " * 8,
        "score": score,
        "_manual_entry": True,
    }])
    return db.resolve_job_hash(hash_)


# ------------------------------------------------ AK 3: Zeitpunkt + Score


def test_948_ein_urteil_haelt_den_damaligen_score_fest(db):
    """AK 3: nach der Analyse stehen Zeitpunkt UND damaliger Score da.

    Ohne den Score laesst sich "ueberholt" nur behaupten. Mit ihm ist
    es belegbar — und der Beleg steht in derselben Zeile.
    """
    voll = _stelle(db, score=20.0)
    assert db.set_job_analysis(voll, "BEDINGT", "Methodenluecke") is True

    job = db.get_job(voll)
    assert job["analyse_am"], "Zeitpunkt fehlt"
    assert job["analyse_score"] == pytest.approx(20.0)


def test_948_der_damalige_score_kommt_aus_der_datenbank(db):
    """Der Aufrufer reicht ihn NICHT herein.

    Sonst gaebe es einen zweiten Weg, auf dem eine andere Zahl
    hineinkaeme als die, gegen die spaeter verglichen wird — das ist
    #987 in einem neuen Feld.
    """
    import inspect

    sig = inspect.signature(db.set_job_analysis)
    assert "score" not in sig.parameters, (
        "set_job_analysis nimmt einen Score entgegen — damit kann der "
        "gespeicherte Wert vom tatsaechlichen abweichen.")


# ------------------------------------------------- AK 5: ueberholt am Score


def test_948_ein_geaenderter_score_macht_die_analyse_ueberholt(db):
    """AK 5: aendert sich der Score, wechselt die Kennzeichnung."""
    voll = _stelle(db, score=20.0)
    db.set_job_analysis(voll, "EMPFOHLEN", "passt")

    job = db.get_job(voll)
    assert passung.zustand(job).get("ueberholt") is None

    db.update_job(voll, {"score": 34})
    job = db.get_job(voll)
    alt = passung.zustand(job)["ueberholt"]
    assert alt["grund"] == "score"
    assert alt["score_damals"] == pytest.approx(20.0)
    assert alt["score_jetzt"] == pytest.approx(34.0)


def test_948_der_score_ist_das_integrierende_signal(db):
    """Beschreibung, Kriterien und Regler wirken ALLE ueber den Score.

    Deshalb genuegt ein Vergleich. Drei einzelne haetten dieselbe Frage
    dreimal beantwortet, und zwei davon ungenauer.
    """
    voll = _stelle(db, score=10.0)
    db.set_job_analysis(voll, "BEDINGT", "unklar")
    # Eine nachgeladene Beschreibung schlaegt sich im Score nieder.
    db.update_job(voll, {
        "description": "Viel mehr Anzeigentext als vorher. " * 40,
        "score": 41,
    })
    job = db.get_job(voll)
    assert passung.zustand(job)["ueberholt"]["grund"] == "score"


def test_948_ohne_toleranzschwelle_und_das_ist_gemessen():
    """Es gibt kein Rauschband, das eine Schwelle wegfiltern muesste.

    Gemessen am 10.09.2026 ueber 600 Stellen mit Anzeigentext (Kopie
    des Bestands): 381 unveraendert, 219 abweichend — und die KLEINSTE
    beobachtete Abweichung betraegt bereits 0,5 Punkte, der Median
    10,5. Eine Schwelle waere hier kein Schutz vor Fehlalarmen (#929),
    sondern eine Grenze, die echte Aenderungen verschweigt.
    """
    job = {"analyse_score": 20.0, "score": 20.5}
    alt = passung.ueberholt(job)
    assert alt is not None, "0,5 Punkte sind eine echte Aenderung"
    # Gleichheit bleibt Gleichheit — Fliesskomma-Rauschen zaehlt nicht.
    assert passung.ueberholt({"analyse_score": 20.0, "score": 20.0}) is None


def test_948_auch_das_profil_macht_ueberholt(db):
    """Die Erkennung aus #1007 bleibt — sie kommt jetzt nur dazu."""
    job = {
        "analyse_urteil": "EMPFOHLEN",
        "analyse_score": 20.0,
        "score": 20.0,
        "analyse_profil_stand": "3/2@2026-01-01T00:00:00",
    }
    profil = {"skills": [{"name": "a"}] * 9, "positions": [],
              "updated_at": "2026-09-10T10:00:00"}
    alt = passung.ueberholt(job, profil)
    assert alt["grund"] == "profil"


def test_948_beide_gruende_werden_benannt(db):
    """Wer nur einen Grund nennt, verdeckt den anderen (#987 MERKE 5)."""
    job = {
        "analyse_urteil": "EMPFOHLEN",
        "analyse_score": 20.0,
        "score": 55.0,
        "analyse_profil_stand": "3/2@2026-01-01T00:00:00",
    }
    profil = {"skills": [{"name": "a"}] * 9, "positions": [],
              "updated_at": "2026-09-10T10:00:00"}
    assert passung.ueberholt(job, profil)["grund"] == "score+profil"


# ----------------------------------------------- AK 4: die drei Zustaende


def test_948_drei_zustaende_sind_unterscheidbar(db):
    """AK 4: keine Analyse / angesehen / beurteilt."""
    ohne = _stelle(db, "948ohne", score=5.0)
    gesichtet = _stelle(db, "948ges", score=5.0)
    beurteilt = _stelle(db, "948urt", score=5.0)

    db.mark_job_sighted(gesichtet)
    db.set_job_analysis(beurteilt, "EMPFOHLEN", "gelesen")

    arten = {
        h: passung.zustand(db.get_job(h))["art"]
        for h in (ohne, gesichtet, beurteilt)
    }
    assert arten == {
        ohne: passung.UNGEPRUEFT,
        gesichtet: passung.GESICHTET,
        beurteilt: passung.BEURTEILT,
    }
    # ... und jeder traegt einen eigenen Klartext.
    texte = {passung.ZUSTAND_TEXT[a] for a in arten.values()}
    assert len(texte) == 3


def test_948_ungeprueft_ist_eine_antwort_und_kein_none(db):
    """"Noch nicht angesehen" ist eine Auskunft, keine fehlende.

    `zustand` gibt deshalb immer ein dict zurueck — anders als
    `analyse_lesen`, das ohne Urteil bewusst None liefert.
    """
    stand = passung.zustand({})
    assert stand["art"] == passung.UNGEPRUEFT
    assert stand["text"]


def test_948_angesehen_ist_nicht_beurteilt(db):
    """Der Kern der Trennung, und der Grund fuer den dritten Zustand.

    Dass ein Werkzeug gelaufen ist, sagt nichts darueber, ob jemand das
    Ergebnis gelesen und entschieden hat. Beides gleich zu zaehlen
    waere #989 — eine fehlende Information saehe aus wie eine
    vorhandene.
    """
    voll = _stelle(db, "948nurgesehen", score=12.0)
    db.mark_job_sighted(voll)
    job = db.get_job(voll)
    assert passung.zustand(job)["art"] == passung.GESICHTET
    # Kein Urteil entstanden.
    assert not (job.get("analyse_urteil") or "")
    assert passung.analyse_lesen(job) is None


# ------------------------------- Die Sichtung fasst Score und Urteil nicht an


def test_948_die_sichtung_veraendert_den_score_nicht(db):
    """#963 bleibt gueltig: ein Lesewerkzeug verschiebt keine Rangfolge.

    Bis v1.7.23 schrieb `fit_analyse` den errechneten Wert still in
    `jobs.score` — wer sich eine Stelle nur genauer ansah, verschob
    ihre Position in der Liste. Die neue Spur darf das nicht durch die
    Hintertuer zurueckholen.
    """
    voll = _stelle(db, score=17.0)
    vorher = db.get_job(voll)
    db.mark_job_sighted(voll)
    nachher = db.get_job(voll)

    assert nachher["score"] == vorher["score"]
    assert nachher["updated_at"] == vorher["updated_at"], (
        "Eine Sichtung ist keine Aenderung an der Stelle — `updated_at` "
        "traegt anderswo Bedeutung (Wiedergaenger, Anzeigenalter).")
    assert nachher["gesichtet_am"]
    assert nachher["gesichtet_score"] == pytest.approx(17.0)


def test_948_eine_sichtung_meldet_ehrlich_wenn_es_die_stelle_nicht_gibt(db):
    """Kein "gespeichert" ueber nichts (#997)."""
    assert db.mark_job_sighted("gibtesnicht") is False


def test_948_ein_urteil_ueberschreibt_die_sichtung_nicht(db):
    """Beide Spuren stehen nebeneinander — sie sagen Verschiedenes."""
    voll = _stelle(db, score=9.0)
    db.mark_job_sighted(voll)
    db.update_job(voll, {"score": 30})
    db.set_job_analysis(voll, "BEDINGT", "gelesen")

    job = db.get_job(voll)
    assert job["gesichtet_score"] == pytest.approx(9.0)
    assert job["analyse_score"] == pytest.approx(30.0)
    # Das Urteil ist der juengere Stand und gewinnt beim Vergleich.
    assert passung.zustand(job).get("ueberholt") is None


# -------------------------------------- AK 6/7 + die Wege in den Bestand


def test_948_beide_fit_wege_vermerken_die_sichtung():
    """AK 3 gilt fuer BEIDE Wege — MCP und Dashboard.

    Der Melder ruft die Analyse ueber die Oberflaeche auf, Claude ueber
    das Werkzeug. Nur einen Weg zu vermerken hiesse, dass die Spur
    davon abhinge, wer sie ausloest — genau das Muster aus #963.
    """
    for datei in ("src/bewerbungs_assistent/tools/jobs.py",
                  "src/bewerbungs_assistent/dashboard.py"):
        quelle = (_repo() / datei).read_text(encoding="utf-8-sig")
        assert "mark_job_sighted" in quelle, f"{datei} vermerkt nichts."


def test_948_beide_listen_liefern_den_pruefstand():
    """AK 4 gilt fuer beide Listen, aus DERSELBEN Quelle.

    Die Einteilung entsteht in `services/passung.py`. Eine zweite
    Fassung im Frontend oder im MCP waere das Muster, das dieses
    Projekt dreizehnmal gekostet hat.
    """
    for datei in ("src/bewerbungs_assistent/tools/jobs.py",
                  "src/bewerbungs_assistent/dashboard.py"):
        quelle = (_repo() / datei).read_text(encoding="utf-8-sig")
        assert "passung.zustand(" in quelle, (
            f"{datei} baut den Pruefstand nicht ueber das Nadeloehr.")


def test_948_das_frontend_entscheidet_den_zustand_nicht_selbst():
    """Der Filter liest `pruefstand.art` — er leitet ihn nicht ab."""
    quelle = (_repo() / "frontend" / "src" / "pages"
              / "JobsPage.jsx").read_text(encoding="utf-8")
    code = "\n".join(z for z in quelle.split("\n")
                     if not z.strip().startswith("//"))
    assert "job.pruefstand?.art" in code
    # Kein zweiter Schalter fuer dieselbe Frage (#988).
    assert "onlyAnalysed" not in code, (
        "Der alte Ja/Nein-Schalter steht noch daneben — zwei "
        "Einstellungen fuer eine Frage sind #988.")


def test_948_der_filter_kann_beide_richtungen():
    """AK 6: "nur ungeprueft" ist der Fall, den das Sichten braucht."""
    quelle = (_repo() / "frontend" / "src" / "pages"
              / "JobsPage.jsx").read_text(encoding="utf-8")
    assert 'value="ungeprueft"' in quelle
    assert 'value="beurteilt"' in quelle


def test_948_der_einstieg_steht_in_der_fusszeile():
    """AK 1/2: ohne Scrollen erreichbar, und er verdeckt nichts.

    Die Fusszeile des Modals liegt ausserhalb des Scroll-Containers
    (`components/ui.jsx`): sie ist immer sichtbar, und der
    Inhaltsbereich rechnet ihre Hoehe bereits ein. Kein zweiter
    Mechanismus noetig — der richtige war gebaut.
    """
    seite = (_repo() / "frontend" / "src" / "pages"
             / "JobsPage.jsx").read_text(encoding="utf-8")
    fussstart = seite.index("footer={(")
    fussende = seite.index("Schliessen</Button>", fussstart)
    fusszeile = seite[fussstart:fussende]
    assert "Detailbewertung durch Claude anfordern" in fusszeile

    # ... und genau EINMAL auf der Seite, nicht zweimal (#979).
    assert seite.count("Detailbewertung durch Claude anfordern") == 1

    ui = (_repo() / "frontend" / "src" / "components"
          / "ui.jsx").read_text(encoding="utf-8")
    assert "overflow-y-auto" in ui and "{footer}" in ui


def test_948_das_abzeichen_fuehrt_zum_ergebnis():
    """AK 7: ein Klick, kein Umweg ueber die Detailansicht."""
    seite = (_repo() / "frontend" / "src" / "pages"
             / "JobsPage.jsx").read_text(encoding="utf-8")
    start = seite.index("job.pruefstand && job.pruefstand.art")
    block = seite[start:start + 1200]
    assert "showFitAnalysis(job)" in block, (
        "Das Abzeichen ist nicht anklickbar.")
    assert "stopPropagation" in block, (
        "Ohne stopPropagation oeffnet der Klick zusaetzlich die "
        "Detailansicht — eine Nebenwirkung, die niemand gemeint hat.")


# ------------------------------------- Nebenbefunde, beim Bauen gefunden


def test_948_der_dashboard_weg_nutzt_dieselbe_kriterien_basis():
    """Bis v1.7.70 stand hier `get_search_criteria()` roh.

    Damit rechnete der Fit-Dialog im Dashboard OHNE die Anreicherung
    aus #987, ohne die Begriffsart-Ableitung des MUSS-Tors (#968) und
    ohne die Anforderungs-Gruppierung (#1012) — also eine andere Zahl
    als `fit_analyse` im Chat, an derselben Stelle. Das Nadeloehr gab
    es seit v1.7.36; dieser Aufrufer ging daran vorbei (#1008 MERKE 4).
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent"
              / "dashboard.py").read_text(encoding="utf-8-sig")
    start = quelle.index("async def api_fit_analyse")
    block = quelle[start:start + 3000]
    assert "scoring_kriterien.fuer_scoring(_db)" in block
    assert "criteria = _db.get_search_criteria()" not in block


def test_948_der_recherche_kasten_liest_ueber_das_nadeloehr():
    """Sonst waere er nach der #956-Zusammenfuehrung LEER.

    `/api/jobs/{hash}/fit-analyse` gab `job.research_notes` roh
    zurueck. Seit v1.7.70 liegt die Recherche in der Tabelle und die
    Spalte wird von der Migration geleert — der Kasten haette also
    genau das Symptom gezeigt, wegen dem #956 aufgemacht wurde, nur an
    einer zweiten Stelle.
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent"
              / "dashboard.py").read_text(encoding="utf-8-sig")
    start = quelle.index("async def api_fit_analyse")
    block = quelle[start:start + 3000]
    assert "recherche_ablage.lesen(" in block


def test_948_der_dialog_liest_den_stand_vor_dem_eigenen_vermerk():
    """Sonst zeigte er den Zustand, den er selbst gerade erzeugt hat.

    Wer eine nie angesehene Stelle oeffnet, soll "noch nicht
    angesehen" sehen — nicht "angesehen", weil das Oeffnen es gerade
    erst wahr gemacht hat.
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent"
              / "dashboard.py").read_text(encoding="utf-8-sig")
    start = quelle.index("async def api_fit_analyse")
    block = quelle[start:start + 3000]
    assert block.index("_passung.zustand(job") < block.index(
        "mark_job_sighted"), (
        "Der Vermerk laeuft vor dem Lesen — der Dialog zeigt dann "
        "seinen eigenen Seiteneffekt.")


# ---------------------------------------------------------------------
# Die Wege wirklich AUFRUFEN — ein Grep beweist nur, dass der Aufruf
# dasteht, nicht dass er laeuft (DoD 8c).
# ---------------------------------------------------------------------


@pytest.fixture
def client(tmp_path):
    """FastAPI-TestClient auf einer isolierten DB."""
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database

    datenbank = Database(db_path=tmp_path / "test.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")

    import bewerbungs_assistent.dashboard as dash

    dash._db = datenbank
    from fastapi.testclient import TestClient

    try:
        yield TestClient(dash.app), datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def test_948_der_rest_weg_vermerkt_die_sichtung_wirklich(client):
    """Der Endpunkt wird AUFGERUFEN, nicht nur gelesen."""
    tc, datenbank = client
    voll = _stelle(datenbank, "948rest", score=13.0)

    assert not (datenbank.get_job(voll).get("gesichtet_am") or "")
    antwort = tc.get(f"/api/jobs/{voll}/fit-analyse")
    assert antwort.status_code == 200

    job = datenbank.get_job(voll)
    assert job["gesichtet_am"], "Der Aufruf hat keine Spur hinterlassen."
    assert job["gesichtet_score"] == pytest.approx(13.0)
    # Und er hat den Score NICHT angefasst (#963).
    assert job["score"] == pytest.approx(13.0)


def test_948_der_dialog_zeigt_beim_ersten_oeffnen_ungeprueft(client):
    """Der eigene Seiteneffekt darf nicht die Antwort sein."""
    tc, datenbank = client
    voll = _stelle(datenbank, "948erst", score=8.0)
    daten = tc.get(f"/api/jobs/{voll}/fit-analyse").json()
    assert daten["pruefstand"]["art"] == passung.UNGEPRUEFT
    # Beim zweiten Mal ist die Spur da.
    daten = tc.get(f"/api/jobs/{voll}/fit-analyse").json()
    assert daten["pruefstand"]["art"] == passung.GESICHTET


def test_948_die_liste_liefert_den_pruefstand_an_jeder_stelle(client):
    """AK 4 am echten Endpunkt, nicht am Quelltext."""
    tc, datenbank = client
    ohne = _stelle(datenbank, "948lohne", score=5.0)
    beurteilt = _stelle(datenbank, "948lurt", score=5.0)
    datenbank.set_job_analysis(beurteilt, "EMPFOHLEN", "gelesen")

    jobs = tc.get("/api/jobs?limit=50").json().get("jobs", [])
    stand = {j["hash"]: j.get("pruefstand", {}).get("art") for j in jobs}
    assert stand.get(ohne) == passung.UNGEPRUEFT
    assert stand.get(beurteilt) == passung.BEURTEILT


def test_948_der_recherche_kasten_zeigt_die_neue_ablage(client):
    """Nach #956 liegt die Recherche in der Tabelle — der Kasten auch.

    Ohne diesen Weg waere der Kasten nach der Zusammenfuehrung leer:
    genau das Symptom, wegen dem #956 aufgemacht wurde.
    """
    from bewerbungs_assistent.services import recherche_ablage

    tc, datenbank = client
    voll = _stelle(datenbank, "948rech", score=6.0)
    recherche_ablage.speichern(
        datenbank, "Recherche-Beleg-Zx9 zur Firma.", job_hash=voll)

    daten = tc.get(f"/api/jobs/{voll}/fit-analyse").json()
    assert "Recherche-Beleg-Zx9" in (daten.get("research_notes") or "")


def test_948_das_mcp_werkzeug_vermerkt_die_sichtung_wirklich(db):
    """Derselbe Nachweis fuer den Weg, den Claude nimmt."""
    import asyncio
    import logging

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools import register_all

    voll = _stelle(db, "948mcp", score=21.0)
    mcp = FastMCP("PBP Test 948")
    register_all(mcp, db, logging.getLogger("test.948"))

    async def _lauf():
        werkzeug = await mcp.get_tool("fit_analyse")
        return await werkzeug.run({"job_hash": voll})

    asyncio.run(_lauf())
    job = db.get_job(voll)
    assert job["gesichtet_am"], "Der MCP-Weg hinterlaesst keine Spur."
    assert job["score"] == pytest.approx(21.0), "Der Score wurde angefasst."
