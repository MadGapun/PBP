"""Tests fuer die beiden Nutzerentscheidungen vom 10.09.2026.

1. **#957 Stufe 2** — *"beide behalten, verkettet"*. Die Messung aus
   Stufe 1 hatte die Entscheidung erzwungen: 23 von 97 Bewerbungen
   tragen zwei Fassungen derselben Notiz, und die Abweichung geht in
   BEIDE Richtungen. Es gibt keine ableitbare Regel.

2. **#663 C65** — den Tippfehler `Dublikat` mit `duplikat`
   zusammenfuehren. Beim Probelauf auf einer Kopie stellte sich heraus,
   dass das vorhandene Werkzeug das gar nicht kann: es meldete Erfolg
   und schrieb null Stellen um.
"""
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import notiz_drift as nd  # noqa: E402


@pytest.fixture
def db(tmp_path):
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


def _bewerbung(db, feld: str, anlage: str = "") -> str:
    """Eine Bewerbung mit Notizfeld und (optional) Anlage-Eintrag."""
    aid = db.add_application({
        "title": "Rolle Quintus", "company": "Halbleiterwerk Nord GmbH",
        "status": "beworben", "notes": feld,
    })
    if anlage:
        db.connect().execute(
            "INSERT INTO application_events (application_id, status, notes, "
            "event_date) VALUES (?, 'notiz', ?, '2026-01-01')", (aid, anlage))
        db.connect().commit()
    # Das Feld getrennt setzen — `add_application` legt den Anlage-Eintrag
    # sonst selbst an und die Fixture haette zwei.
    db.connect().execute("UPDATE applications SET notes=? WHERE id=?",
                         (feld, aid))
    db.connect().commit()
    return aid


# ================================================================
# #957 Stufe 2 — beide behalten, verkettet
# ================================================================


def test_957_beide_fassungen_bleiben_erhalten(db):
    """Die Nutzerentscheidung woertlich: nichts wird weggeworfen."""
    aid = _bewerbung(db, "Neue Fassung Alpha-Qx7",
                     "Alte Fassung Beta-Zw3 aus dem Anlegen")
    nd.zusammenfuehren(db, dry_run=False)

    notiz = db.connect().execute(
        "SELECT notes FROM applications WHERE id=?", (aid,)).fetchone()[0]
    assert "Neue Fassung Alpha-Qx7" in notiz
    assert "Alte Fassung Beta-Zw3" in notiz, (
        "Die aeltere Fassung wurde weggeworfen.")


def test_957_die_gepflegte_fassung_steht_oben(db):
    """Das FELD ist die zuletzt gepflegte Fassung.

    `bewerbung_bearbeiten` schreibt nur dorthin — der Anlage-Eintrag ist
    der aeltere Stand und gehoert darunter, benannt statt kommentarlos
    angehaengt.
    """
    aid = _bewerbung(db, "Zuletzt gepflegt Alpha-Qx7", "Beim Anlegen Beta-Zw3")
    nd.zusammenfuehren(db, dry_run=False)
    notiz = db.connect().execute(
        "SELECT notes FROM applications WHERE id=?", (aid,)).fetchone()[0]
    assert notiz.index("Alpha-Qx7") < notiz.index("Beta-Zw3")
    assert nd.TRENNZEILE in notiz, "Die Herkunft des unteren Teils fehlt."


def test_957_der_timeline_eintrag_bleibt_unangetastet(db):
    """Er ist der Beleg dafuer, dass nichts erfunden wurde."""
    aid = _bewerbung(db, "Feld Alpha-Qx7", "Timeline Beta-Zw3")
    nd.zusammenfuehren(db, dry_run=False)
    zeilen = db.connect().execute(
        "SELECT notes FROM application_events WHERE application_id=? "
        "AND status='notiz'", (aid,)).fetchall()
    assert any("Beta-Zw3" in (z[0] or "") for z in zeilen), (
        "Der Timeline-Eintrag wurde veraendert.")


def test_957_die_vorschau_ist_die_vorgabe_und_schreibt_nichts(db):
    """Ein Lauf, der ungefragt schreibt, ist keine Migration."""
    aid = _bewerbung(db, "Feld Alpha-Qx7", "Timeline Beta-Zw3")
    vorher = db.connect().execute(
        "SELECT notes FROM applications WHERE id=?", (aid,)).fetchone()[0]

    erg = nd.zusammenfuehren(db)  # ohne Argument = dry_run
    assert erg["status"] == "vorschau"
    assert erg["zusammengefuehrt"] == 1

    nachher = db.connect().execute(
        "SELECT notes FROM applications WHERE id=?", (aid,)).fetchone()[0]
    assert nachher == vorher, "Die Vorschau hat geschrieben."


def test_957_der_lauf_ist_idempotent(db):
    """Ohne Merkliste, ohne Zeitstempel, ohne zweite Wahrheit.

    Eine bereits verkettete Notiz ENTHAELT den Anlage-Eintrag und faellt
    damit unter `zusammengefuehrt` statt unter `abweichend`.
    """
    _bewerbung(db, "Feld Alpha-Qx7", "Timeline Beta-Zw3")
    erst = nd.zusammenfuehren(db, dry_run=False)
    zweit = nd.zusammenfuehren(db, dry_run=False)

    assert erst["zusammengefuehrt"] == 1
    assert zweit["zusammengefuehrt"] == 0
    assert zweit["bereits_zusammengefuehrt"] == 1


def test_957_der_report_meldet_danach_keine_drift_mehr(db):
    """**Beim Messen gefunden, nicht beim Nachdenken.**

    Ohne den fuenften Fall haette der Report weiter `abweichend`
    gemeldet — technisch richtig (die Texte sind verschieden), in der
    Sache falsch: beide Fassungen liegen dann an einem Ort. Ein
    Pruefer, der bei korrektem Zustand Alarm gibt, wird nach dem
    zweiten Mal ignoriert (#929).
    """
    _bewerbung(db, "Feld Alpha-Qx7", "Timeline Beta-Zw3")
    assert nd.bericht(db)["faelle"][nd.ABWEICHEND] == 1

    nd.zusammenfuehren(db, dry_run=False)
    faelle = nd.bericht(db)["faelle"]
    assert faelle[nd.ABWEICHEND] == 0
    assert faelle[nd.ZUSAMMENGEFUEHRT] == 1


def test_957_identische_fassungen_werden_nicht_angefasst(db):
    """Da gibt es nichts zusammenzufuehren — und eine Verkettung
    erzeugte eine sinnlose Dublette im Text."""
    aid = _bewerbung(db, "Gleicher Text Alpha-Qx7", "Gleicher Text Alpha-Qx7")
    nd.zusammenfuehren(db, dry_run=False)
    notiz = db.connect().execute(
        "SELECT notes FROM applications WHERE id=?", (aid,)).fetchone()[0]
    assert notiz.count("Alpha-Qx7") == 1
    assert nd.TRENNZEILE not in notiz


def test_957_eine_notiz_nur_in_der_timeline_bleibt_liegen(db):
    """BEWUSST nicht angefasst — und benannt statt still uebergangen.

    Hier gibt es keine zwei Fassungen, sondern eine an einem anderen
    Ort. Sie ins Feld zu schieben waere ein Umzug und damit eine
    eigene Entscheidung.
    """
    _bewerbung(db, "", "Nur in der Timeline Beta-Zw3")
    erg = nd.zusammenfuehren(db, dry_run=False)
    assert erg["zusammengefuehrt"] == 0
    assert erg["nur_im_timeline_eintrag"]["anzahl"] == 1
    assert "eigene Entscheidung" in erg["nur_im_timeline_eintrag"]["bedeutung"]


def test_957_der_bericht_nennt_keine_notiztexte(db):
    """Eine Notiz ist das Privateste im Bestand."""
    _bewerbung(db, "Geheimer Feldtext Alpha-Qx7",
               "Geheimer Timelinetext Beta-Zw3")
    erg = nd.zusammenfuehren(db)
    text = repr(erg)
    assert "Alpha-Qx7" not in text
    assert "Beta-Zw3" not in text


def test_957_das_werkzeug_ist_registriert_und_ruft_den_dienst(db):
    """DoD 8c: ein Weg zaehlt erst, wenn er auch aufgerufen wird."""
    import asyncio
    import logging

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools import register_all

    _bewerbung(db, "Feld Alpha-Qx7", "Timeline Beta-Zw3")
    mcp = FastMCP("PBP Test 957")
    register_all(mcp, db, logging.getLogger("test.957"))

    async def _lauf():
        werkzeug = await mcp.get_tool("bewerbung_notizen_zusammenfuehren")
        erg = await werkzeug.run({"dry_run": False})
        return getattr(erg, "structured_content", erg)

    antwort = asyncio.run(_lauf())
    assert antwort["zusammengefuehrt"] == 1


# ================================================================
# #663 C65 — der Tippfehler, und warum das Werkzeug ihn nicht konnte
# ================================================================


def _grund_und_stellen(db, label: str, werte: list) -> int:
    """Legt einen Ablehnungsgrund an und Stellen, die ihn tragen."""
    grund = db.add_dismiss_reason(label)
    gid = grund["id"] if isinstance(grund, dict) else grund
    for i, wert in enumerate(werte):
        db.save_jobs([{
            "hash": f"c65-{label}-{i}", "title": f"Rolle {label} {i}",
            "company": f"Firma {i} GmbH",
            "url": f"https://example.com/c65/{label}/{i}",
            "source": "manuell", "description": "Text. " * 20,
            "score": 5, "_manual_entry": True,
        }])
        voll = db.resolve_job_hash(f"c65-{label}-{i}")
        db.connect().execute(
            "UPDATE jobs SET dismiss_reason=?, is_active=0 WHERE hash=?",
            (wert, voll))
    db.connect().commit()
    return gid


def test_663_gross_und_kleinschreibung_wird_mitgezogen(db):
    """Der erste Defekt: `Dublikat` traf `dublikat` nicht.

    SQLite vergleicht TEXT exakt. Der Grund heisst im Editor
    `Dublikat`, gespeichert wird `dublikat` — die Bedingung traf null
    Zeilen, und das Werkzeug meldete trotzdem Erfolg.
    """
    gid = _grund_und_stellen(db, "Dublikat", ["dublikat", "dublikat"])
    erg = db.rename_dismiss_reason(gid, "duplikat")
    assert erg["reassigned_jobs"] == 2, (
        "Die Kleinschreibung wurde wieder nicht mitgezogen.")
    rest = db.connect().execute(
        "SELECT COUNT(*) FROM jobs WHERE LOWER(dismiss_reason) "
        "LIKE '%dublikat%'").fetchone()[0]
    assert rest == 0


def test_663_die_listenform_wird_mitgezogen(db):
    """Der zweite Defekt: Gruende stehen seit #913 normalerweise als
    JSON-Liste da, und der Vergleich sah davon nichts."""
    gid = _grund_und_stellen(db, "Dublikat", [
        '["dublikat"]', '["dublikat", "falsches_fachgebiet"]'])
    erg = db.rename_dismiss_reason(gid, "duplikat")
    assert erg["reassigned_jobs"] == 2

    werte = [z[0] for z in db.connect().execute(
        "SELECT dismiss_reason FROM jobs WHERE dismiss_reason IS NOT NULL")]
    assert all("dublikat" not in str(w).lower() for w in werte)
    # Die uebrigen Gruende der Liste bleiben stehen.
    assert any("falsches_fachgebiet" in str(w) for w in werte)


def test_663_die_liste_bleibt_eine_liste(db):
    """Aus `["dublikat"]` darf kein nackter String werden.

    Sonst laesen die Auswerter, die auf die Listenform bauen, ihn als
    einzelnes Wort — eine stille Formatverschiebung.
    """
    import json

    gid = _grund_und_stellen(db, "Dublikat", ['["dublikat", "zeitarbeit"]'])
    db.rename_dismiss_reason(gid, "duplikat")
    wert = db.connect().execute(
        "SELECT dismiss_reason FROM jobs WHERE dismiss_reason IS NOT NULL"
    ).fetchone()[0]
    geparst = json.loads(wert)
    assert isinstance(geparst, list)
    assert geparst == ["duplikat", "zeitarbeit"]


def test_663_eine_stelle_mit_beiden_schreibweisen_behaelt_eine(db):
    """Sonst entstuende `["duplikat", "duplikat"]`."""
    import json

    gid = _grund_und_stellen(db, "Dublikat", ['["dublikat", "duplikat"]'])
    db.rename_dismiss_reason(gid, "duplikat")
    wert = db.connect().execute(
        "SELECT dismiss_reason FROM jobs WHERE dismiss_reason IS NOT NULL"
    ).fetchone()[0]
    assert json.loads(wert) == ["duplikat"]


def test_663_fremde_gruende_bleiben_unberuehrt(db):
    """Die Gegenrichtung — beim Haerten immer beide messen (#966)."""
    _grund_und_stellen(db, "Zeitarbeit", ["zeitarbeit", '["zeitarbeit"]'])
    gid = _grund_und_stellen(db, "Dublikat", ["dublikat"])
    db.rename_dismiss_reason(gid, "duplikat")

    werte = sorted(str(z[0]) for z in db.connect().execute(
        "SELECT dismiss_reason FROM jobs WHERE dismiss_reason IS NOT NULL"))
    assert "zeitarbeit" in werte
    assert '["zeitarbeit"]' in werte


def test_663_das_umbenennen_ist_idempotent(db):
    """Ein zweiter Lauf findet nichts mehr."""
    gid = _grund_und_stellen(db, "Dublikat", ["dublikat"])
    erst = db.rename_dismiss_reason(gid, "duplikat")
    assert erst["reassigned_jobs"] == 1
    # Der Grund heisst jetzt schon so.
    gruende = {g["label"]: g["id"] for g in db.get_dismiss_reasons()}
    zweit = db.rename_dismiss_reason(gruende["duplikat"], "duplikat")
    assert zweit["status"] == "unveraendert"
    assert zweit["reassigned_jobs"] == 0
