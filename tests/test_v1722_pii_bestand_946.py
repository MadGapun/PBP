"""Tests fuer v1.7.22 — #946: Pruefschritt VOR dem Anlegen von Issues.

Dreimal innerhalb von zwei Tagen sind Bewerbungsdaten in oeffentliche
Issues geraten. Die Regel dagegen gibt es laengst; sie greift nur beim
Nachlesen, also zu spaet. Dieser Pruefer dreht die Richtung um: statt
eine gepflegte Namensliste im Repo zu suchen, sucht er die Namen aus der
eigenen Datenbank im ausgehenden Text.
"""
import asyncio

import pytest

from bewerbungs_assistent.services import pii_bestand


@pytest.fixture
def bestand(tmp_db):
    """Ein kleiner, realistischer Bestand: Bewerbung, Stelle, Kontakt."""
    db = tmp_db
    db.add_application({
        "company": "Nordwerk Antriebstechnik GmbH",
        "title": "PLM Consultant",
        "position": "PLM Consultant",
        "status": "beworben",
        "ansprechpartner": "Frauke Meinert",
    })
    # Der Profil-Inhaber bekommt einen Namen: sein Klarname MUSS
    # zulaessig bleiben (bewusste Entscheidung, #946).
    db.save_profile({"name": "Rita Wendelin", "email": "r@example.com"})
    db.save_jobs([{
        "hash": "pii946a",
        "title": "PDM Spezialist (m/w/d)",
        "company": "Seewind Maschinenbau AG",
        "url": "https://example.com/jobs/pii946a",
        "source": "bundesagentur",
        "score": 40,
    }])
    return db


def test_946_firma_aus_bewerbung_wird_gefunden(bestand):
    """Der Kernfall: eine Firma aus dem Bestand steht im Issue-Text."""
    text = ("## Befund\n\nDie Stelle bei Nordwerk Antriebstechnik GmbH "
            "wurde doppelt angelegt.\n")
    bericht = pii_bestand.pruefe_text(bestand, text)
    assert not bericht["sauber"], bericht
    namen = [t["name"].lower() for t in bericht["treffer"]]
    assert any("nordwerk" in n for n in namen), bericht
    treffer = bericht["treffer"][0]
    assert treffer["zeile"] == 3, treffer
    assert "doppelt angelegt" in treffer["fundstelle"]


def test_946_firma_aus_gesichteter_stelle_wird_gefunden(bestand):
    """Nicht nur Bewerbungen — auch blosse Sichtungen sind heikel."""
    bericht = pii_bestand.pruefe_text(
        bestand, "Beispiel: Seewind Maschinenbau AG liefert doppelte Hashes.")
    assert not bericht["sauber"]
    assert any("seewind" in t["name"].lower() for t in bericht["treffer"])


def test_946_personenname_wird_gefunden(bestand):
    bericht = pii_bestand.pruefe_text(
        bestand, "Rueckfrage von Frauke Meinert steht noch aus.")
    arten = {t["art"] for t in bericht["treffer"]}
    assert "person" in arten, bericht


def test_946_quellennamen_loesen_keinen_treffer_aus(bestand):
    """Portale benennen eine Datenquelle, keine Bewerbung (DoD-9)."""
    text = ("Lauf ueber bundesagentur und stepstone; jobspy_indeed "
            "lieferte 1538 Treffer.")
    bericht = pii_bestand.pruefe_text(bestand, text)
    assert bericht["sauber"], bericht["treffer"]


def test_946_hashes_und_ids_loesen_keinen_treffer_aus(bestand):
    """Ohne Datenbank bedeutungslos, fuer Regressionsfaelle noetig."""
    text = "Regressionsfall: `fec0835c`, Stellen `9f388607` und `85998226`."
    bericht = pii_bestand.pruefe_text(bestand, text)
    assert bericht["sauber"], bericht["treffer"]


def test_946_platzhalter_bleibt_ueber_aufrufe_stabil(bestand):
    """Sonst heisst dieselbe Firma im naechsten Issue anders."""
    erst = pii_bestand.platzhalter_fuer(bestand, "Nordwerk Antriebstechnik GmbH")
    zweit = pii_bestand.platzhalter_fuer(bestand, "nordwerk antriebstechnik gmbh")
    assert erst == zweit, (erst, zweit)
    # Eine andere Firma bekommt einen anderen Platzhalter.
    andere = pii_bestand.platzhalter_fuer(bestand, "Seewind Maschinenbau AG")
    assert andere != erst


def test_946_anonymisieren_ersetzt_und_bleibt_lesbar(bestand):
    text = ("Nordwerk Antriebstechnik GmbH hat abgesagt. "
            "Bei Nordwerk Antriebstechnik GmbH lief das Gespraech gut.")
    ergebnis = pii_bestand.anonymisiere_text(bestand, text)
    assert "Nordwerk" not in ergebnis["text"], ergebnis["text"]
    # Beide Vorkommen ersetzt, und zwar durch DENSELBEN Platzhalter.
    platz = ergebnis["ersetzt"][0]["platzhalter"]
    assert ergebnis["text"].count(platz) == 2, ergebnis["text"]
    # Danach ist der Text sauber.
    assert pii_bestand.pruefe_text(bestand, ergebnis["text"])["sauber"]


def test_946_platzhalter_selbst_ist_kein_treffer(bestand):
    """Gegenrichtung: der Ersatz darf nicht erneut anschlagen."""
    platz = pii_bestand.platzhalter_fuer(bestand, "Nordwerk Antriebstechnik GmbH")
    bericht = pii_bestand.pruefe_text(bestand, f"Die Absage von {platz} kam heute.")
    assert bericht["sauber"], bericht["treffer"]


def test_946_generische_bestandswerte_feuern_nicht(bestand):
    """'Unbekannt' steht als Firma im Bestand und ist trotzdem kein Name."""
    bestand.save_jobs([{
        "hash": "pii946b", "title": "Irgendwas", "company": "Unbekannt",
        "url": "https://example.com/b", "source": "bundesagentur", "score": 20,
    }])
    bericht = pii_bestand.pruefe_text(
        bestand, "Die Quelle ist Unbekannt, deshalb fehlt die Zuordnung.")
    assert bericht["sauber"], bericht["treffer"]


def test_946_eigener_klarname_bleibt_zulaessig(bestand):
    """Bewusste Entscheidung des Repo-Inhabers (#946)."""
    prof = bestand.connect().execute(
        "SELECT name FROM profile WHERE name IS NOT NULL LIMIT 1").fetchone()
    if not prof or not (prof[0] or "").strip():
        pytest.skip("Testprofil hat keinen Namen")
    bericht = pii_bestand.pruefe_text(bestand, f"Gemeldet von {prof[0]}.")
    assert bericht["sauber"], bericht["treffer"]


def test_946_zuordnungstabelle_ist_nicht_teil_von_export_oder_telemetrie():
    """Die Tabelle haelt Klarnamen — sie darf das Geraet nie verlassen."""
    from pathlib import Path
    wurzel = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
    verdaechtig = []
    for datei in list((wurzel / "tools").glob("*.py")) + [
            wurzel / "services" / "telemetrie.py",
            wurzel / "dashboard.py"]:
        if not datei.exists():
            continue
        inhalt = datei.read_text(encoding="utf-8")
        if "anonymisierung_map" in inhalt:
            verdaechtig.append(datei.name)
    assert verdaechtig == [], (
        f"anonymisierung_map wird in {verdaechtig} referenziert — die "
        "Tabelle haelt Klarnamen und gehoert nicht in Export/Telemetrie")


def test_946_tool_ist_registriert_und_warnt_deutlich(bestand, tmp_path):
    """Das Tool muss existieren und im Trefferfall klar Stopp sagen."""
    import importlib
    import os

    # Das server-Modul haelt seine DB auf Modulebene. Wurde es in einem
    # frueheren Test importiert, zeigt der Pfad auf ein Temp-Verzeichnis,
    # das inzwischen geloescht ist — auf dem CI-Runner scheiterte der
    # Test daran mit "unable to open database file", lokal je nach
    # Testreihenfolge nicht. Deshalb beide Module frisch laden.
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    import bewerbungs_assistent.database as dbmod
    importlib.reload(dbmod)
    import bewerbungs_assistent.server as srv
    importlib.reload(srv)
    assert str(tmp_path) in str(srv.db.db_path), (
        f"DB nicht isoliert: {srv.db.db_path}")

    async def _call(name, args):
        tool = await srv.mcp.get_tool(name)
        res = await tool.run(args)
        return getattr(res, "structured_content", res)

    # Der Server haelt seine EIGENE Datenbank-Instanz (BA_DATA_DIR zeigt
    # dank der Fixture ins Temp-Verzeichnis) — also dort saeen, sonst
    # prueft das Tool gegen einen leeren Bestand.
    srv.db.add_application({
        "company": "Nordwerk Antriebstechnik GmbH",
        "title": "PLM Consultant", "position": "PLM Consultant",
        "status": "beworben",
    })
    roh = asyncio.run(_call("issue_text_pruefen", {
        "text": "Bei Nordwerk Antriebstechnik GmbH lief es schief."}))
    if isinstance(roh, tuple):
        roh = roh[1] if len(roh) > 1 else roh[0]
    assert roh["sauber"] is False
    assert "NICHT veroeffentlichen" in roh["hinweis"]


def test_946_pruefschritt_ist_im_ablauf_verankert():
    """Der Schritt muss VOR dem Anlegen stehen, nicht danach."""
    from pathlib import Path
    wurzel = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
    prompts = (wurzel / "prompts.py").read_text(encoding="utf-8")
    server = (wurzel / "server.py").read_text(encoding="utf-8")
    assert "issue_text_pruefen" in prompts, (
        "Der Melde-Prompt muss den Pruefschritt nennen")
    assert "issue_text_pruefen" in server, (
        "Die Server-Instructions muessen den Pruefschritt nennen")
