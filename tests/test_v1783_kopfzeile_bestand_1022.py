"""Tests fuer #1022 — die Kopfzeile zaehlt gerenderte Zeilen.

Gemeldet am 11.09.2026. Die Kachel oben links meldete „AKTIVE STELLEN
**20**" bei **1.110** aktiven Stellen und wurde beim Blaettern zu 40,
dann 60 — waehrend der Knopf direkt darunter die richtige Zahl nannte:
„Mehr laden (20 von 1110)".

Der Satz des Melders ist die ganze Begruendung:

    ich hab immer gedacht, es gibt nur zwanzig Stellen fuer mich

## Befund 1: die Unterscheidung existierte und hing am falschen Ausloeser

Die Kachel wechselte auf „Angezeigte Stellen", aber nur bei
`verborgeneStellen > 0` — und das zaehlt ausschliesslich die durch
FILTER verborgenen Stellen. **Paginierung loest es nicht aus**, also
genau der haeufigste Fall nicht.

Die Kopfzeile ist eine Bestandsanzeige. Sie zeigt jetzt immer
`jobsTotal`, in beiden Tabs; was gerade sichtbar ist, steht in der
Notiz.

## Befund 2: die 54 im Ausgeblendet-Tab

Der Melder konnte den Wert von aussen nicht aufloesen — der Endpunkt
liefert 172, und weder Blacklist noch Bewerbungen noch Duplikate
ergaben 54. Es ist das **7-Tage-Zeitfenster** aus #1010.

Der Gedanke dahinter stimmt (gesucht wird „was habe ich gerade
weggeklickt"), die Vorgabe war trotzdem falsch: **ein Filter, den
niemand gesetzt hat, verbarg 118 von 172 Zeilen.** Das ist woertlich
#1008, wo ein ungesetzter Filter 7 von 8 Stellen verbarg und die Lehre
lautete: Vorgabe AUS, benannt.

Die Sortierung erledigt den urspruenglichen Zweck ohnehin — das
Protokoll ist nach `dismissed_at` sortiert.

## Befund 3: die Kennzahlen rechneten ueber die geladene Seite

Und weil nach Score sortiert wird, sind die geladenen Zeilen immer die
BESTEN. Gemessen vom Melder am selben Bestand:

| Grundlage | Durchschnittsscore |
|---|---:|
| alle 1.110 aktiven | **3,59** |
| die ersten 20 | 13,82 |
| die ersten 40 | 12,34 |
| die ersten 100 | 10,56 |

**Eine Kennzahl, die sich beim Blaettern aendert, misst das Blaettern
und nicht den Bestand.**

## Warum eine Grundlage statt fertiger Zahlen

Gehaltsdurchschnitt und Bandbreite entstehen in
`frontend/src/lib/gehaltsKennzahl.js` — einem Modul, das v1.7.78 genau
deshalb angelegt hat, weil die Rechnung vorher WORTGLEICH in zwei
Seiten lag. Sie serverseitig ein zweites Mal in Python zu schreiben
waere dieselbe Bauform noch einmal, nur ueber die Sprachgrenze hinweg
(#963).

Also wandert nicht das Ergebnis heraus, sondern die EINGABE: fuenf
Felder je Stelle. Der Endpunkt hat die vollstaendige Liste ohnehin in
der Hand und schneidet die Seite erst danach heraus.
"""
import importlib
import os
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

JOBS_PAGE = _repo() / "frontend" / "src" / "pages" / "JobsPage.jsx"


def _quelle() -> str:
    return JOBS_PAGE.read_text(encoding="utf-8")


def _ohne_kommentare(text: str) -> str:
    """Ein Guard darf nicht an der Begruendung anschlagen, warum etwas
    verboten ist (v1.7.50 MERKE 2)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(
        z for z in text.split("\n") if not z.lstrip().startswith("//"))


@pytest.fixture
def client(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    db = database.Database(db_path=tmp_path / "kopf.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.switch_profile(db.create_profile("Kopfzeile"))

    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient

    vorher = dash._db
    dash._db = db
    try:
        yield TestClient(dash.app), db
    finally:
        dash._db = vorher
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


def _bestand(db, anzahl=30):
    """Stellen mit ABSTEIGENDEM Score — wie die echte Liste sortiert.

    Genau deshalb ist die geladene Seite nicht repraesentativ: sie
    enthaelt immer die besten.
    """
    jobs = []
    for i in range(anzahl):
        jobs.append({
            "hash": f"k{i:03d}",
            "title": f"Stelle {i}",
            "company": f"Firma {i}",
            "url": f"https://example.com/1022/{i}",
            "source": "manuell", "_manual_entry": True,
            "description": "Beschreibungstext. " * 20,
            "score": float(anzahl - i),
            "salary_min": 40000 + i * 1000,
            "salary_max": 50000 + i * 1000,
            "salary_type": "jaehrlich",
            "salary_estimated": 0,
        })
    db.save_jobs(jobs)
    return jobs


# ------------------------------------------- Der Kern: Blaettern aendert nichts


def test_die_kennzahlen_grundlage_umfasst_den_ganzen_bestand(client):
    """Der Test, der die Meldung nachstellt.

    Er prueft keine einzelne Zahl, sondern eine Eigenschaft: was die
    Kopfzeile speist, darf sich beim Blaettern nicht aendern.
    """
    tc, db = client
    _bestand(db, 30)

    seite1 = tc.get("/api/jobs?active=true&limit=10&offset=0").json()
    seite2 = tc.get("/api/jobs?active=true&limit=10&offset=10").json()
    seite3 = tc.get("/api/jobs?active=true&limit=10&offset=20").json()

    assert len(seite1["jobs"]) == 10
    assert seite1["total"] == 30
    for seite in (seite1, seite2, seite3):
        assert len(seite["kennzahlen_basis"]) == 30, (
            "Die Grundlage beschreibt den Bestand, nicht die Seite")
    assert seite1["kennzahlen_basis"] == seite2["kennzahlen_basis"]
    assert seite2["kennzahlen_basis"] == seite3["kennzahlen_basis"]


def test_der_durchschnittsscore_der_grundlage_ist_der_des_bestands(client):
    """Die Zahl aus dem Bericht, nachgestellt.

    Ueber alle 30 Stellen liegt der Mittelwert bei 15,5; ueber die
    ersten 10 (die besten) bei 25,5. Genau diese Schieflage hat der
    Melder gemessen — 13,82 gegen 3,59.
    """
    tc, db = client
    _bestand(db, 30)
    antwort = tc.get("/api/jobs?active=true&limit=10&offset=0").json()

    basis = [float(z["score"]) for z in antwort["kennzahlen_basis"]]
    seite = [float(j["score"]) for j in antwort["jobs"]]

    assert round(sum(basis) / len(basis), 1) == 15.5
    assert round(sum(seite) / len(seite), 1) == 25.5, (
        "Voraussetzung des Tests: die geladene Seite ist besser als der "
        "Bestand — sonst prueft er nichts")


def test_die_grundlage_traegt_genau_die_benoetigten_felder(client):
    """Fuenf Felder, nicht die ganze Stelle.

    Ueber 1.110 Stellen sind das rund 60 KB. Die vollstaendigen
    Datensaetze mitzugeben waere derselbe Fehler in der anderen
    Richtung — #991 hat schon einmal 962 Vorschlaege ausgeliefert, weil
    niemand nach der Menge gefragt hat.
    """
    tc, db = client
    _bestand(db, 5)
    antwort = tc.get("/api/jobs?active=true&limit=2&offset=0").json()
    zeile = antwort["kennzahlen_basis"][0]
    assert set(zeile) == {
        "score", "salary_min", "salary_max", "salary_type",
        "salary_estimated"}


def test_die_zahl_der_aussortierten_kommt_mit(client):
    """Fuer den Tab-Namen — ohne zweiten Abruf beim Blaettern."""
    tc, db = client
    _bestand(db, 6)
    for i in range(4):
        db.dismiss_job(db.resolve_job_hash(f"k{i:03d}"), "falsches_fachgebiet")

    antwort = tc.get("/api/jobs?active=true&limit=1&offset=0").json()
    assert antwort["aussortiert_gesamt"] == 4
    assert antwort["total"] == 2


def test_ohne_paginierung_bleibt_die_antwort_eine_liste(client):
    """Der Vertrag von `limit=0` ist unveraendert.

    Die Grundlage haengt an der paginierten Antwort; ohne Paginierung
    IST die gelieferte Liste der Bestand, und das Frontend rechnet
    direkt damit.
    """
    tc, db = client
    _bestand(db, 5)
    antwort = tc.get("/api/jobs?active=true").json()
    assert isinstance(antwort, list)
    assert len(antwort) == 5


# --------------------------------------------- Die Kopfzeile im Quelltext


def test_die_kachel_zeigt_den_bestand_nicht_die_geladene_seite():
    """AK 1+2: dieselbe Zahl in beiden Tabs, unabhaengig vom Nachladen.

    Geprueft wird am Quelltext, weil hier eine Zuweisung die Aussage
    traegt. Der Browser-Test darunter prueft die Wirkung.
    """
    quelle = _ohne_kommentare(_quelle())
    assert 'label="Aktive Stellen"' in quelle, (
        "Die Kachel traegt kein festes Label mehr")
    assert "value={jobsTotal}" in quelle, (
        "Die Kachel zeigt nicht den Bestand")
    assert "value={filteredJobs.length}" not in quelle, (
        "Die Kachel zaehlt weiterhin die gerenderten Zeilen")


def test_die_kennzahlen_rechnen_nicht_mehr_ueber_die_geladene_seite():
    """AK 5: Score und Gehalt ueber den gesamten aktiven Bestand."""
    quelle = _ohne_kommentare(_quelle())
    assert "buildAnnualSalaryMetrics(kennzahlenQuelle)" in quelle
    assert "buildAnnualSalaryMetrics(jobs)" not in quelle
    assert "kennzahlenQuelle.filter((job) => Number(job?.score || 0) > 0)" in quelle


def test_beide_tabs_nennen_ihre_menge_mit_den_vorhandenen_tokens():
    """AK 3+4.

    `text-coral` und nicht `text-rose`: der Gefahren-Ton dieses Projekts
    heisst coral (`ui.jsx`, `tone="danger"`). Mein erster Entwurf hatte
    `text-rose` — ein Token, das es nicht gibt, fuer das Tailwind keine
    Regel UND keinen Fehler erzeugt (#964).
    """
    quelle = _ohne_kommentare(_quelle())
    assert '["active", "Aktive", jobsTotal, "text-teal"]' in quelle
    assert '"text-coral"' in quelle
    assert "text-rose" not in quelle, (
        "text-rose ist kein Projekt-Token — Tailwind erzeugt dafuer "
        "keine Regel und keinen Fehler (#964)")


def test_die_notiz_nennt_die_sichtbaren_bei_aktivem_filter():
    """AK 6."""
    quelle = _ohne_kommentare(_quelle())
    assert "${filteredJobs.length} sichtbar, ${durchFilterVerborgen} durch Filter verborgen" in quelle


def test_das_zeitfenster_verbirgt_nichts_mehr_ungefragt():
    """AK 7 — und die Lehre aus #1008.

    Mit der Vorgabe `7tage` zeigte der Ausgeblendet-Tab 54 von 172
    Zeilen, ohne dass jemand den Filter gesetzt haette. Die Zahl im
    Tab-Namen und die Zahl der angezeigten Stellen gingen damit
    auseinander.
    """
    quelle = _ohne_kommentare(_quelle())
    assert 'useState("alle")' in quelle, (
        "Das Aussortier-Fenster steht wieder auf einer Vorgabe, die "
        "Zeilen verbirgt")
    assert 'useState("7tage")' not in quelle
    # Der Schalter bleibt — er ist jetzt eine Wahl statt einer Vorgabe.
    assert '["7tage", "7 Tage"]' in quelle
