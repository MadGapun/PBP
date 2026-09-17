"""Tests fuer #1056 — Notizen mit Bewerbungsbezug gehoeren an die Bewerbung (D47).

Gemessen am 17.09.2026: 27 Profil-Sektionen mit rund 40.000 Zeichen,
davon drei mit 11.700 Zeichen zu EINER seit zwei Monaten abgelehnten
Bewerbung. Jede Ausgabe, die das Profil liest, bekam die Details mit —
auch die Vorbereitung fuer eine ANDERE Firma.

Alle Firmen und Personen sind Platzhalter.
"""
import asyncio
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import notiz_routing as nr  # noqa: E402


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17119_notizen_")
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


def _notizen_setzen(db, blob: str):
    profil = db.get_profile()
    db.save_profile({**{k: profil.get(k) for k in (
        "name", "email", "phone", "address", "city", "plz", "country",
        "birthday", "nationality", "summary")},
        "informal_notes": blob, "preferences": profil.get("preferences", {})})


def _bewerbung(db, firma, titel="Stammdaten Migration", status="beworben"):
    return db.add_application({"title": titel, "company": firma, "status": status})


PROFIL_MIT_ZWEI_SEKTIONEN = """## ARBEITSWEISE
[2026-06-01] Strukturiert, dokumentiert gern, fragt frueh nach.

## Interview bei Musterfirma GmbH am 13.06.2026
[2026-06-13] Erstgespraech mit dem Fachbereich. Aussage des Gespraechspartners: Migration bis Q4.
[2026-06-13] Nachlese: zu lange Antworten, mehr Rueckfragen stellen.

## Kommunikationsstil, belegt an Gespraechen bei Musterfirma GmbH und Beispielwerk AG
[2026-07-01] Neigt zu langen Antworten, wenn das Thema vertraut ist. Coaching: kuerzer."""


# ══ AK 6: der Regressionsfall ═══════════════════════════════════════

def test_ein_profil_mit_interview_und_verhaltensmuster_ergibt_genau_einen_vorschlag(umgebung):
    """AK 6 woertlich: "Interview bei Firma X am Datum" wird vorgeschlagen,
    "Kommunikationsstil, belegt an Gespraechen bei X und Y" nicht — dort
    sind die Firmen Beleg, nicht Gegenstand."""
    db, _ = umgebung
    _bewerbung(db, "Musterfirma GmbH")
    _bewerbung(db, "Beispielwerk AG")
    _notizen_setzen(db, PROFIL_MIT_ZWEI_SEKTIONEN)
    v = nr.vorschlaege(db)
    assert [x["sektion"] for x in v] == ["Interview bei Musterfirma GmbH am 13.06.2026"]
    assert v[0]["sicherheit"] == nr.EINDEUTIG
    assert v[0]["firma"] == "Musterfirma GmbH"
    assert v[0]["zeichen"] > 50


def test_eine_firma_nur_im_text_loest_nichts_aus(umgebung):
    """Sonst wuerde jeder Coaching-Hinweis mit einem Beispiel verschoben."""
    db, _ = umgebung
    _bewerbung(db, "Musterfirma GmbH")
    _notizen_setzen(db, "## VERHANDLUNG\n[2026-05-01] Bei Musterfirma GmbH "
                        "zu frueh eine Zahl genannt. Naechstes Mal warten.")
    assert nr.vorschlaege(db) == []
    assert nr.bewerbungsbezug(db, "VERHANDLUNG", "Bei Musterfirma GmbH ...") is None


def test_die_rechtsform_entscheidet_nicht(umgebung):
    """"Interview bei Musterfirma" trifft die Bewerbung bei "Musterfirma
    GmbH" — verglichen wird wie beim Wiedergaenger (#671, #1028)."""
    db, _ = umgebung
    _bewerbung(db, "Musterfirma GmbH")
    bezug = nr.bewerbungsbezug(db, "Vorbereitung Zweitgespraech Musterfirma")
    assert bezug and bezug["sicherheit"] == nr.EINDEUTIG
    # Und der reine Firmenname als Ueberschrift ebenso.
    assert nr.bewerbungsbezug(db, "Musterfirma GmbH") is not None
    # Ohne Bewerbung bei der Firma: kein Bezug, egal wie die Ueberschrift heisst.
    assert nr.bewerbungsbezug(db, "Interview bei Musterwerk KG am 01.01.") is None


def test_zwei_bewerbungen_bei_derselben_firma_sind_unsicher(umgebung):
    """AK 2: gefragt, nicht geraten."""
    db, _ = umgebung
    a = _bewerbung(db, "Musterfirma GmbH", "PLM Berater")
    b = _bewerbung(db, "Musterfirma GmbH", "PDM Consultant")
    bezug = nr.bewerbungsbezug(db, "Interview bei Musterfirma GmbH")
    assert bezug["sicherheit"] == nr.UNSICHER
    assert {k["bewerbung_id"] for k in bezug["kandidaten"]} == {a, b}


# ══ Verschieben in einem Zug ════════════════════════════════════════

def test_verschieben_traegt_ein_und_entfernt_in_einem_zug(umgebung):
    db, _ = umgebung
    app_id = _bewerbung(db, "Musterfirma GmbH")
    _bewerbung(db, "Beispielwerk AG")
    _notizen_setzen(db, PROFIL_MIT_ZWEI_SEKTIONEN)

    antwort = nr.verschieben(db, "Interview bei Musterfirma GmbH am 13.06.2026", app_id)
    assert antwort["status"] == "verschoben"
    assert antwort["bewerbung_id"] == app_id

    # In der Timeline — mit Herkunft.
    app = db.get_application(app_id)
    notizen = [e for e in app.get("events", []) if e.get("status") == "notiz"]
    assert len(notizen) == 1
    assert nr.VERSCHOBEN_MARKE in notizen[0]["notes"]
    assert "Migration bis Q4" in notizen[0]["notes"]

    # Aus dem Profil — und die anderen beiden Sektionen stehen noch da.
    rest = db.get_profile()["informal_notes"]
    assert "Interview bei Musterfirma" not in rest
    assert "## ARBEITSWEISE" in rest and "## Kommunikationsstil" in rest
    assert "fragt frueh nach" in rest
    assert nr.vorschlaege(db) == []


def test_verschieben_ohne_bestaetigung_gibt_es_nicht(umgebung):
    """AK 3/4: Nachsehen aendert nichts, und Unbekanntes wird benannt."""
    db, _ = umgebung
    app_id = _bewerbung(db, "Musterfirma GmbH")
    _notizen_setzen(db, PROFIL_MIT_ZWEI_SEKTIONEN)
    vorher = db.get_profile()["informal_notes"]
    nr.vorschlaege(db)
    nr.bewerbungsbezug(db, "Interview bei Musterfirma GmbH am 13.06.2026")
    assert db.get_profile()["informal_notes"] == vorher

    weg = nr.verschieben(db, "GIBT ES NICHT", app_id)
    assert "fehler" in weg and "ARBEITSWEISE" in weg["vorhanden"]
    assert "fehler" in nr.verschieben(db, "ARBEITSWEISE", "keine-bewerbung")
    assert db.get_profile()["informal_notes"] == vorher


def test_schlaegt_der_timeline_eintrag_fehl_bleibt_die_sektion(umgebung, monkeypatch):
    """Reihenfolge ist Inhalt: erst eintragen, dann entfernen."""
    db, _ = umgebung
    app_id = _bewerbung(db, "Musterfirma GmbH")
    _notizen_setzen(db, PROFIL_MIT_ZWEI_SEKTIONEN)
    vorher = db.get_profile()["informal_notes"]

    def kaputt(*a, **k):
        raise RuntimeError("Platte voll")
    monkeypatch.setattr(db, "add_application_note", kaputt)
    antwort = nr.verschieben(db, "Interview bei Musterfirma GmbH am 13.06.2026", app_id)
    assert "fehler" in antwort and "nichts ist verloren" in antwort["hinweis"]
    assert db.get_profile()["informal_notes"] == vorher


# ══ Der Parser ist einer ════════════════════════════════════════════

def test_ein_parser_fuer_alle_wege():
    """`profil_bearbeiten` (lesen/ersetzen/loeschen) und das Aufraeumen
    lesen dasselbe Format ueber dieselbe Funktion — sonst waere es #963."""
    import inspect
    from bewerbungs_assistent.tools import profil
    quelle = inspect.getsource(profil)
    # Der Inline-Parser aus #680 ist weg; gelesen wird ueber den Dienst.
    assert quelle.count('st.startswith("## ")') == 0, "Inline-Parser steht noch da"
    assert "notiz_routing.sektionen(" in quelle or "_nr.sektionen(" in quelle

    alle = nr.sektionen(PROFIL_MIT_ZWEI_SEKTIONEN)
    assert [n for n, _ in alle] == [
        "ARBEITSWEISE",
        "Interview bei Musterfirma GmbH am 13.06.2026",
        "Kommunikationsstil, belegt an Gespraechen bei Musterfirma GmbH und Beispielwerk AG"]
    assert nr.zusammensetzen(alle) == PROFIL_MIT_ZWEI_SEKTIONEN.strip()


# ══ Routing beim Schreiben ══════════════════════════════════════════

def test_ein_anhang_mit_eindeutigem_bezug_geht_an_die_bewerbung(umgebung):
    """AK 1: nicht ins Profil, sondern in die Timeline — und die Antwort
    sagt es."""
    db, mcp = umgebung
    app_id = _bewerbung(db, "Musterfirma GmbH")
    antwort = _call(mcp, "profil_bearbeiten", {
        "bereich": "notizen", "aktion": "anhang",
        "daten": {"sektion": "Interview bei Musterfirma GmbH am 13.06.",
                  "text": "Erstgespraech, Migration bis Q4."}})
    assert antwort["status"] == "an_bewerbung_umgeleitet"
    assert antwort["bewerbung_id"] == app_id
    assert not (db.get_profile().get("informal_notes") or "")
    app = db.get_application(app_id)
    assert any("Migration bis Q4" in e.get("notes", "") for e in app.get("events", []))


def test_bei_unsicherem_bezug_wird_gefragt_und_nichts_geschrieben(umgebung):
    """AK 2."""
    db, mcp = umgebung
    a = _bewerbung(db, "Musterfirma GmbH", "PLM Berater")
    b = _bewerbung(db, "Musterfirma GmbH", "PDM Consultant")
    antwort = _call(mcp, "profil_bearbeiten", {
        "bereich": "notizen", "aktion": "anhang",
        "daten": {"sektion": "Nachlese Musterfirma GmbH", "text": "Zu lange Antworten."}})
    assert antwort["status"] == "rueckfrage"
    assert {k["bewerbung_id"] for k in antwort["kandidaten"]} == {a, b}
    assert not (db.get_profile().get("informal_notes") or "")
    for app_id in (a, b):
        assert not [e for e in db.get_application(app_id).get("events", [])
                    if e.get("status") == "notiz"]

    # Mit Ziel: an die genannte Bewerbung.
    ok = _call(mcp, "profil_bearbeiten", {
        "bereich": "notizen", "aktion": "anhang",
        "daten": {"sektion": "Nachlese Musterfirma GmbH", "text": "Zu lange Antworten.",
                  "bewerbung_id": b}})
    assert ok["status"] == "an_bewerbung_umgeleitet" and ok["bewerbung_id"] == b


def test_mit_ziel_profil_bleibt_die_notiz_im_profil(umgebung):
    """Der Mensch kann entscheiden, dass es doch ins Profil soll — dann
    ist das keine Umleitung, sondern seine Entscheidung."""
    db, mcp = umgebung
    _bewerbung(db, "Musterfirma GmbH")
    antwort = _call(mcp, "profil_bearbeiten", {
        "bereich": "notizen", "aktion": "anhang",
        "daten": {"sektion": "Musterfirma GmbH", "text": "Merke: Kultur passt.",
                  "ziel": "profil"}})
    assert antwort["status"] == "notiz_angehaengt"
    assert "Kultur passt" in db.get_profile()["informal_notes"]


def test_eine_notiz_ueber_den_menschen_bleibt_wie_bisher(umgebung):
    """Die Gegenrichtung (#966): ohne Firma in der Ueberschrift aendert
    sich am Weg nichts — auch wenn im Text eine Firma steht."""
    db, mcp = umgebung
    _bewerbung(db, "Musterfirma GmbH")
    antwort = _call(mcp, "profil_bearbeiten", {
        "bereich": "notizen", "aktion": "anhang",
        "daten": {"sektion": "ARBEITSWEISE",
                  "text": "Wie bei Musterfirma GmbH gesehen: fragt frueh nach."}})
    assert antwort["status"] == "notiz_angehaengt"
    assert "fragt frueh nach" in db.get_profile()["informal_notes"]


# ══ Das Aufraeum-Werkzeug ═══════════════════════════════════════════

def test_das_werkzeug_schlaegt_vor_und_verschiebt_nur_auf_ansage(umgebung):
    db, mcp = umgebung
    app_id = _bewerbung(db, "Musterfirma GmbH")
    _bewerbung(db, "Beispielwerk AG")
    _notizen_setzen(db, PROFIL_MIT_ZWEI_SEKTIONEN)

    antwort = _call(mcp, "profil_notizen_aufraeumen", {})
    assert len(antwort["vorschlaege"]) == 1
    v = antwort["vorschlaege"][0]
    assert v["sektion"].startswith("Interview bei Musterfirma")
    assert v["ziel"][0]["bewerbung_id"] == app_id
    assert "verschieben" in antwort["naechster_schritt"]
    assert "Interview bei Musterfirma" in db.get_profile()["informal_notes"]

    ok = _call(mcp, "profil_notizen_aufraeumen", {
        "aktion": "verschieben", "sektion": v["sektion"], "bewerbung_id": app_id})
    assert ok["status"] == "verschoben"
    assert "Interview bei Musterfirma" not in db.get_profile()["informal_notes"]
    leer = _call(mcp, "profil_notizen_aufraeumen", {})
    assert leer["vorschlaege"] == [] and "hinweis" in leer

    # Ohne Sektion oder Ziel: benannt, nicht geraten. In der Gegenprobe
    # blieb der Riegel stumm, weil ihn kein Fall aufrief.
    ohne = _call(mcp, "profil_notizen_aufraeumen", {"aktion": "verschieben"})
    assert "Pflicht" in ohne["fehler"]
    assert "fehler" in _call(mcp, "profil_notizen_aufraeumen", {"aktion": "kopieren"})


def test_der_hinweis_im_profil_tab_nennt_die_sektionen(umgebung):
    db, mcp = umgebung
    from bewerbungs_assistent.services import onboarding_hints
    importlib.reload(onboarding_hints)
    ids = {h["id"] for h in onboarding_hints.list_active_hints(db)}
    assert "d47_notizen_an_die_bewerbung" not in ids

    _bewerbung(db, "Musterfirma GmbH")
    _notizen_setzen(db, PROFIL_MIT_ZWEI_SEKTIONEN)
    hints = {h["id"]: h for h in onboarding_hints.list_active_hints(db)}
    h = hints["d47_notizen_an_die_bewerbung"]
    assert h["tab"] == "profil"
    assert "Interview bei Musterfirma" in h["detail"]
    assert h["cta_tool"] == "profil_notizen_aufraeumen"
    assert asyncio.run(mcp.get_tool("profil_notizen_aufraeumen")) is not None
