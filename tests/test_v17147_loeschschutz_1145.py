"""v1.7.147 — Löschen nur mit Vorschau (#1145).

Die Server-Anleitung verspricht „vor jedem Löschen die Vorschau“. Drei
Werkzeuge löschten, ohne dass ihr Name es sagte, und standen deshalb in
keiner der Listen aus `services/werkzeug_schutz.py`:

* `bewerbung_zu_anfrage_konvertieren` — „konvertieren“ klingt nach
  Umwandeln und löschte die Bewerbung samt Terminen, Reflexionen und
  Aufgaben; ein Fehler beim Sichern der Stelle wurde verschluckt.
* `profil_bearbeiten` — ein falscher Schlüssel beim Ändern der Notizen
  leerte alle persönlichen Notizen und meldete „aktualisiert“; Station,
  Projekt, Ausbildung und Skill wurden ohne Vorschau gelöscht.
* `jobtitel_verwalten` (Vorgabe `loeschen`) und `scoring_konfigurieren`
  (`reset` ohne Vorschau).

Der Quellcode-Guard am Ende ist der Teil, der die Klasse schließt: er
liest, welche Werkzeuge löschen, nicht wie sie heißen.

Jeder Test hat eine Gegenprobe (scratchpad/n144/gegenprobe_1145.py).
"""
import ast
import asyncio
import importlib
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
PAKET = ROOT / "src" / "bewerbungs_assistent"


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_loeschschutz1145_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv
    importlib.reload(_srv)
    db = _srv.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Beispiel Person"})
    yield db, _srv.mcp
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


def _notizen(db) -> str:
    return (db.get_profile() or {}).get("informal_notes") or ""


def _notizen_anlegen(db, text="## ALLGEMEIN\n[2026-10-01] Wunsch: Teilzeit\n\n## NO-GOS\n[2026-10-01] Kein Schichtdienst"):
    p = db.get_profile()
    db.save_profile({
        "name": p.get("name"), "email": p.get("email"), "phone": p.get("phone"),
        "address": p.get("address"), "city": p.get("city"), "plz": p.get("plz"),
        "country": p.get("country"), "birthday": p.get("birthday"),
        "nationality": p.get("nationality"), "summary": p.get("summary"),
        "informal_notes": text, "preferences": p.get("preferences", {}),
    })


# ══ 1. bewerbung_zu_anfrage_konvertieren ═══════════════════════════

def _abgelehnte_mit_folgen(db):
    app = db.add_application({"title": "Planung", "company": "Musterbetrieb GmbH",
                              "status": "abgelehnt", "notes": "Gespräch lief gut."})
    db.add_meeting({"application_id": app, "title": "Erstes Gespräch",
                    "meeting_date": "2026-09-20T10:00"})
    db.add_task({"titel": "Zeugnis kopieren", "application_id": app})
    db.add_interview_reflection(app, {"was_lief_gut": "Fachfragen"})
    return app


def test_konvertieren_ohne_bestaetigung_zeigt_nur_die_vorschau(umgebung):
    db, mcp = umgebung
    app = _abgelehnte_mit_folgen(db)
    erg = _call(mcp, "bewerbung_zu_anfrage_konvertieren", {"bewerbung_id": app})
    assert erg["status"] == "bestaetigung_erforderlich"
    assert "Termine" in erg["folgen"] and "Aufgaben" in erg["folgen"]
    assert "Interview-Reflexionen" in erg["folgen"]
    assert erg["geloescht"]["application_meetings"] == 1
    assert "bestaetigung=True" in erg["hinweis"]
    # nichts ist geschehen
    assert db.get_application(app) is not None
    assert len(db.get_meetings_for_application(app)) == 1


def test_vorschau_nennt_die_gekuerzte_notiz(umgebung):
    db, mcp = umgebung
    app = db.add_application({"title": "Planung", "company": "Musterbetrieb GmbH",
                              "status": "abgelehnt", "notes": "x" * 900})
    erg = _call(mcp, "bewerbung_zu_anfrage_konvertieren", {"bewerbung_id": app})
    assert erg["archiv_notiz"]["gekuerzt"] is True
    assert erg["archiv_notiz"]["gespeichert_bis"] == 500
    kurz = db.add_application({"title": "Kurz", "company": "Beta GmbH",
                               "status": "abgelehnt", "notes": "kurz"})
    erg = _call(mcp, "bewerbung_zu_anfrage_konvertieren", {"bewerbung_id": kurz})
    assert erg["archiv_notiz"]["gekuerzt"] is False


def test_konvertieren_mit_bestaetigung_loescht_und_nennt_die_folgen(umgebung):
    db, mcp = umgebung
    app = _abgelehnte_mit_folgen(db)
    erg = _call(mcp, "bewerbung_zu_anfrage_konvertieren",
                {"bewerbung_id": app, "bestaetigung": True})
    assert erg["status"] == "konvertiert", erg
    assert db.get_application(app) is None
    assert "Termine" in erg["folgen"]
    stelle = db.get_job(erg["stelle_hash"])
    assert stelle is not None and not stelle.get("is_active")


def test_konvertieren_loescht_nicht_wenn_das_archivieren_scheitert(umgebung, monkeypatch):
    db, mcp = umgebung
    app = _abgelehnte_mit_folgen(db)
    monkeypatch.setattr(type(db), "dismiss_job", lambda self, *a, **k: False)
    erg = _call(mcp, "bewerbung_zu_anfrage_konvertieren",
                {"bewerbung_id": app, "bestaetigung": True})
    assert erg["status"] == "abgebrochen", erg
    assert "NICHT gelöscht" in erg["fehler"]
    assert db.get_application(app) is not None
    assert len(db.get_meetings_for_application(app)) == 1


def test_konvertieren_loescht_nicht_wenn_das_archivieren_eine_ausnahme_wirft(umgebung, monkeypatch):
    db, mcp = umgebung
    app = _abgelehnte_mit_folgen(db)

    def _kaputt(self, *a, **k):
        raise RuntimeError("Datenbank gesperrt")
    monkeypatch.setattr(type(db), "dismiss_job", _kaputt)
    erg = _call(mcp, "bewerbung_zu_anfrage_konvertieren",
                {"bewerbung_id": app, "bestaetigung": True})
    assert erg["status"] == "abgebrochen", erg
    assert db.get_application(app) is not None


def test_konvertieren_loescht_nicht_wenn_die_neue_stelle_nicht_entsteht(umgebung, monkeypatch):
    db, mcp = umgebung
    app = _abgelehnte_mit_folgen(db)

    def _kaputt(self, *a, **k):
        raise RuntimeError("Datenbank gesperrt")
    monkeypatch.setattr(type(db), "save_jobs", _kaputt)
    erg = _call(mcp, "bewerbung_zu_anfrage_konvertieren",
                {"bewerbung_id": app, "bestaetigung": True})
    assert erg["status"] == "abgebrochen", erg
    assert db.get_application(app) is not None


def test_konvertieren_lehnt_laufende_bewerbungen_weiter_ab(umgebung):
    db, mcp = umgebung
    app = db.add_application({"title": "X", "company": "Y", "status": "beworben"})
    erg = _call(mcp, "bewerbung_zu_anfrage_konvertieren",
                {"bewerbung_id": app, "bestaetigung": True})
    assert "fehler" in erg
    assert db.get_application(app) is not None


# ══ 2. profil_bearbeiten: Notizen ══════════════════════════════════

def test_notizen_aendern_mit_falschem_schluessel_laesst_die_notizen_stehen(umgebung):
    db, mcp = umgebung
    _notizen_anlegen(db)
    vorher = _notizen(db)
    erg = _call(mcp, "profil_bearbeiten", {
        "bereich": "notizen", "aktion": "aendern", "daten": {"notizen": "## NEU\nirgendwas"}})
    assert "fehler" in erg, erg
    assert "NICHT verändert" in erg["fehler"]
    assert erg["uebergeben"] == ["notizen"]
    assert "informal_notes" in erg["erwartet"]
    assert _notizen(db) == vorher


def test_notizen_aendern_mit_leerem_text_wird_abgewiesen(umgebung):
    db, mcp = umgebung
    _notizen_anlegen(db)
    vorher = _notizen(db)
    for leer in ("", "   ", "\n"):
        erg = _call(mcp, "profil_bearbeiten", {
            "bereich": "notizen", "aktion": "aendern", "daten": {"informal_notes": leer}})
        assert "fehler" in erg, (leer, erg)
        assert "2 Sektion(en)" in erg["fehler"]
        assert "leeren" in erg["hinweis"]
        assert _notizen(db) == vorher


def test_notizen_ausdruecklich_leeren_geht(umgebung):
    db, mcp = umgebung
    _notizen_anlegen(db)
    erg = _call(mcp, "profil_bearbeiten", {
        "bereich": "notizen", "aktion": "aendern",
        "daten": {"informal_notes": "", "leeren": True}})
    assert erg["status"] == "aktualisiert"
    assert _notizen(db) == ""


def test_notizen_ersetzen_mit_text_und_alias_funktioniert_weiter(umgebung):
    db, mcp = umgebung
    _notizen_anlegen(db)
    erg = _call(mcp, "profil_bearbeiten", {
        "bereich": "notizen", "aktion": "aendern",
        "daten": {"informal_notes": "## ALLGEMEIN\nNeu geschrieben"}})
    assert erg["status"] == "aktualisiert"
    assert "Neu geschrieben" in _notizen(db) and "NO-GOS" not in _notizen(db)
    erg = _call(mcp, "profil_bearbeiten", {
        "bereich": "notizen", "aktion": "aendern", "daten": {"text": "## X\nueber den Alias"}})
    assert erg["status"] == "aktualisiert"
    assert "ueber den Alias" in _notizen(db)


def test_notizen_ersetzen_auf_leeren_notizen_ist_kein_fehler(umgebung):
    # nichts zu verlieren: der leere Ersatz ist hier harmlos
    db, mcp = umgebung
    erg = _call(mcp, "profil_bearbeiten", {
        "bereich": "notizen", "aktion": "aendern", "daten": {"informal_notes": ""}})
    assert erg["status"] == "aktualisiert"


def test_notiz_sektion_loeschen_zeigt_erst_den_inhalt(umgebung):
    db, mcp = umgebung
    _notizen_anlegen(db)
    erg = _call(mcp, "profil_bearbeiten", {
        "bereich": "notizen", "aktion": "loeschen", "daten": {"sektion": "no-gos"}})
    assert erg["status"] == "bestaetigung_erforderlich", erg
    assert erg["sektion"] == "NO-GOS"
    assert any("Schichtdienst" in z for z in erg["inhalt"])
    assert "NO-GOS" in _notizen(db)
    erg = _call(mcp, "profil_bearbeiten", {
        "bereich": "notizen", "aktion": "loeschen", "daten": {"sektion": "no-gos"},
        "bestaetigung": True})
    assert erg["status"] == "geloescht"
    assert "NO-GOS" not in _notizen(db) and "ALLGEMEIN" in _notizen(db)


# ══ 3. profil_bearbeiten: Station, Projekt, Ausbildung, Skill ═════

def _station_mit_projekten(db):
    pos = db.add_position({"company": "Musterwerk AG", "title": "Planer",
                           "start_date": "2020-01", "end_date": "2023-12"})
    p1 = db.add_project(pos, {"name": "Umbau Halle 3"})
    p2 = db.add_project(pos, {"name": "Werkzeugverwaltung"})
    return pos, p1, p2


def test_station_loeschen_zeigt_erst_die_projekte(umgebung):
    db, mcp = umgebung
    pos, p1, p2 = _station_mit_projekten(db)
    erg = _call(mcp, "profil_bearbeiten", {
        "bereich": "position", "aktion": "loeschen", "element_id": pos})
    assert erg["status"] == "bestaetigung_erforderlich", erg
    assert erg["element"] == "Planer bei Musterwerk AG"
    assert erg["geloescht"]["projects"] == 2
    assert "Projekte" in erg["folgen"] and "Station" in erg["folgen"]
    assert "bestaetigung=True" in erg["hinweis"]
    # nichts ist geschehen
    profil = db.get_profile()
    assert len(profil["positions"]) == 1
    assert len(profil["positions"][0]["projects"]) == 2


def test_station_loeschen_mit_bestaetigung_nimmt_die_projekte_mit(umgebung):
    db, mcp = umgebung
    pos, _p1, _p2 = _station_mit_projekten(db)
    erg = _call(mcp, "profil_bearbeiten", {
        "bereich": "position", "aktion": "loeschen", "element_id": pos,
        "bestaetigung": True})
    assert erg["status"] == "geloescht", erg
    assert db.get_profile()["positions"] == []


def test_projekt_ausbildung_und_skill_loeschen_zeigen_erst_die_vorschau(umgebung):
    db, mcp = umgebung
    pos, p1, _p2 = _station_mit_projekten(db)
    edu = db.add_education({"institution": "Fachschule Nord", "degree": "Techniker"})
    skill = db.add_skill({"name": "Arbeitsvorbereitung", "category": "fachlich", "level": 4},
                         quelle="eingabe")
    assert skill, "Skill wurde nicht angelegt"
    db.add_skill_period(skill, 2018, 2020)
    faelle = [("projekt", p1, "Umbau Halle 3"),
              ("ausbildung", edu, "Techniker, Fachschule Nord"),
              ("skill", skill, "Arbeitsvorbereitung")]
    for bereich, eid, name in faelle:
        erg = _call(mcp, "profil_bearbeiten", {
            "bereich": bereich, "aktion": "loeschen", "element_id": eid})
        assert erg["status"] == "bestaetigung_erforderlich", (bereich, erg)
        assert erg["element"] == name
    # Die Kompetenz nimmt ihre Zeiträume mit — und das steht vorher da
    skill_vorschau = _call(mcp, "profil_bearbeiten", {
        "bereich": "skill", "aktion": "loeschen", "element_id": skill})
    assert skill_vorschau["geloescht"]["skill_periods"] == 1
    profil = db.get_profile()
    assert len(profil["education"]) == 1 and len(profil["skills"]) == 1
    # mit Bestätigung wirkt es
    for bereich, eid, _ in faelle:
        erg = _call(mcp, "profil_bearbeiten", {
            "bereich": bereich, "aktion": "loeschen", "element_id": eid,
            "bestaetigung": True})
        assert erg["status"] == "geloescht", (bereich, erg)
    profil = db.get_profile()
    assert profil["education"] == [] and profil["skills"] == []


def test_loeschen_mit_umlaut_in_der_aktion_braucht_dieselbe_bestaetigung(umgebung):
    db, mcp = umgebung
    pos, _p1, _p2 = _station_mit_projekten(db)
    erg = _call(mcp, "profil_bearbeiten", {
        "bereich": "position", "aktion": "löschen", "element_id": pos})
    assert erg["status"] == "bestaetigung_erforderlich"
    assert len(db.get_profile()["positions"]) == 1


def test_unbekannte_id_antwortet_weiter_mit_nicht_gefunden(umgebung):
    # die Vorschau greift nur, wo es etwas zu zeigen gibt
    _db, mcp = umgebung
    for bereich in ("position", "projekt", "ausbildung", "skill"):
        erg = _call(mcp, "profil_bearbeiten", {
            "bereich": bereich, "aktion": "loeschen", "element_id": "gibt-es-nicht"})
        assert erg["status"] == "nicht_gefunden", (bereich, erg)


def test_aendern_und_hinzufuegen_brauchen_keine_bestaetigung(umgebung):
    db, mcp = umgebung
    pos, _p1, _p2 = _station_mit_projekten(db)
    erg = _call(mcp, "profil_bearbeiten", {
        "bereich": "position", "aktion": "aendern", "element_id": pos,
        "daten": {"title": "Senior Planer"}})
    assert erg["status"] == "aktualisiert"
    erg = _call(mcp, "profil_bearbeiten", {
        "bereich": "ausbildung", "aktion": "hinzufuegen",
        "daten": {"institution": "Uni", "degree": "Bachelor"}})
    assert erg["status"] == "hinzugefuegt"


# ══ 4. scoring_konfigurieren('reset') ═════════════════════════════

def test_scoring_reset_zeigt_erst_die_vorschau(umgebung):
    db, mcp = umgebung
    db.set_scoring_config("remote", "remote", 7)
    db.set_scoring_config("stellentyp", "zeitarbeit", -9)
    erg = _call(mcp, "scoring_konfigurieren", {"aktion": "reset"})
    assert erg["status"] == "bestaetigung_erforderlich", erg
    assert erg["regler"] >= 2
    assert erg["davon_von_dir_gesetzt"] >= 2
    assert any("remote/remote" in b for b in erg["beispiele"])
    assert "bestaetigung=True" in erg["hinweis"]
    # nichts ist geschehen
    zeilen = {(c["dimension"], c["sub_key"]) for c in db.get_scoring_config()}
    assert ("remote", "remote") in zeilen and ("stellentyp", "zeitarbeit") in zeilen


def test_scoring_reset_zaehlt_wie_er_loescht(umgebung):
    # Vorschau und Ausfuehrung rechnen dieselbe Menge (die Lehre aus #1025)
    db, mcp = umgebung
    db.set_scoring_config("remote", "remote", 7)
    # Eine Vorgabe-Zeile ohne Profil (profile_id=''): sie wird gelesen, aber
    # vom Zuruecksetzen NICHT geloescht — die Vorschau darf sie nicht zaehlen.
    con = db.connect()
    con.execute(
        "INSERT INTO scoring_config (profile_id, dimension, sub_key, value, "
        "ignore_flag, created_at) VALUES ('', 'gehalt', 'vorgabe_1145', 5, 0, '2026-05-01')")
    con.commit()
    vorschau = _call(mcp, "scoring_konfigurieren", {"aktion": "reset"})
    erg = _call(mcp, "scoring_konfigurieren", {"aktion": "reset", "bestaetigung": True})
    assert erg["status"] == "zurueckgesetzt"
    assert erg["entfernte_zeilen"] == vorschau["regler"]
    assert any(c["sub_key"] == "vorgabe_1145" for c in db.get_scoring_config())


def test_einzelner_regler_loeschen_bleibt_sofort(umgebung):
    db, mcp = umgebung
    db.set_scoring_config("remote", "remote", 7)
    erg = _call(mcp, "scoring_konfigurieren", {
        "aktion": "loeschen", "dimension": "remote", "sub_key": "remote"})
    assert erg["status"] == "geloescht"


# ══ 5. jobtitel_verwalten ═════════════════════════════════════════

def test_jobtitel_verwalten_ohne_aktion_loescht_nichts(umgebung):
    db, mcp = umgebung
    tid = db.add_job_title("Sachbearbeitung Einkauf")
    erg = _call(mcp, "jobtitel_verwalten", {})
    assert erg["anzahl"] == 1 and erg["titel"][0]["id"] == tid
    erg = _call(mcp, "jobtitel_verwalten", {"titel_id": tid})
    assert erg["anzahl"] == 1
    assert len(db.get_suggested_job_titles()) == 1


def test_jobtitel_verwalten_vorgabe_steht_im_schema(umgebung):
    _db, mcp = umgebung

    async def _tool():
        return await mcp.get_tool("jobtitel_verwalten")
    schema = asyncio.run(_tool()).parameters["properties"]
    assert schema["aktion"]["default"] == "anzeigen"


# ══ 6. Die Listen und der Quellcode-Guard ═════════════════════════

def test_die_drei_werkzeuge_stehen_in_den_listen_und_haben_die_vorschau_als_vorgabe(umgebung):
    from bewerbungs_assistent.services import werkzeug_schutz as ws
    _db, mcp = umgebung

    async def _alle():
        return {t.name: t for t in await mcp.list_tools()}
    werkzeuge = asyncio.run(_alle())
    for name, param in (("bewerbung_zu_anfrage_konvertieren", "bestaetigung"),
                        ("profil_bearbeiten", "bestaetigung"),
                        ("scoring_konfigurieren", "bestaetigung"),
                        ("bewerbungs_stellen_abgleichen", "dry_run")):
        assert ws.ZWEISTUFIG.get(name) == param, name
        schema = werkzeuge[name].parameters["properties"]
        assert param in schema, name
        assert schema[param]["default"] is (True if param == "dry_run" else False), name
        assert werkzeuge[name].annotations.destructiveHint is True, name
    for name in ("jobtitel_verwalten", "ats_firmen_verwalten", "blacklist_verwalten"):
        assert name in ws.KLEIN_SOFORT, name


# Werkzeuge, die loeschende Datenbankaufrufe enthalten, aber bewusst in
# keiner der drei Listen stehen — jeder Eintrag mit Grund. Die Liste soll
# leer bleiben; sie ist die Tuer fuer den begruendeten Einzelfall.
OHNE_EINORDNUNG: dict[str, str] = {}

_LOESCHEND = re.compile(r"^(delete|remove|clear|reset)_")


def _werkzeug_funktionen():
    """(Datei, Werkzeugname, [loeschende Aufrufe]) fuer jede @mcp.tool-Funktion."""
    gefunden = []
    for datei in sorted((PAKET / "tools").glob("*.py")):
        baum = ast.parse(datei.read_text(encoding="utf-8-sig"))
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.FunctionDef):
                continue
            ist_werkzeug = any(
                isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "tool"
                or getattr(d, "attr", "") == "tool"
                for d in knoten.decorator_list)
            if not ist_werkzeug:
                continue
            aufrufe = []
            for k in ast.walk(knoten):
                if (isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute)
                        and isinstance(k.func.value, ast.Name) and k.func.value.id == "db"
                        and _LOESCHEND.match(k.func.attr)):
                    aufrufe.append(f"db.{k.func.attr}")
                if isinstance(k, ast.Constant) and isinstance(k.value, str) \
                        and re.match(r"\s*DELETE\s+FROM\b", k.value, re.I):
                    aufrufe.append("DELETE FROM")
            if aufrufe:
                gefunden.append((datei.name, knoten.name, sorted(set(aufrufe))))
    return gefunden


def test_jedes_werkzeug_das_loescht_ist_eingeordnet():
    """Der Guard, der die Klasse schliesst: nicht der NAME entscheidet,
    sondern was im Quelltext steht. Ein neues Werkzeug mit `db.delete_*`
    oder `DELETE FROM` ohne Eintrag in ZWEISTUFIG, KLEIN_SOFORT oder
    UMKEHRBAR macht die Suite rot."""
    from bewerbungs_assistent.services import werkzeug_schutz as ws
    funktionen = _werkzeug_funktionen()
    assert len(funktionen) >= 15, ("der Guard sieht fast nichts — "
                                   f"Erkennung kaputt? {funktionen}")
    fehlt = [(datei, name, aufrufe) for datei, name, aufrufe in funktionen
             if not ws.einordnung(name) and name not in OHNE_EINORDNUNG]
    assert not fehlt, (
        f"Diese Werkzeuge löschen, stehen aber in keiner Liste von "
        f"services/werkzeug_schutz.py: {fehlt}")


def test_der_guard_erkennt_die_drei_faelle_aus_dem_issue():
    namen = {name for _datei, name, _a in _werkzeug_funktionen()}
    for erwartet in ("bewerbung_zu_anfrage_konvertieren", "profil_bearbeiten",
                     "jobtitel_verwalten", "scoring_konfigurieren"):
        assert erwartet in namen, erwartet


def test_der_guard_sieht_etwas(monkeypatch):
    """Gegenprobe des Guards selbst: wird ein Werkzeug aus der Liste
    genommen, schlaegt er an."""
    from bewerbungs_assistent.services import werkzeug_schutz as ws
    kopie = dict(ws.ZWEISTUFIG)
    kopie.pop("bewerbung_zu_anfrage_konvertieren")
    monkeypatch.setattr(ws, "ZWEISTUFIG", kopie)
    fehlt = [name for _d, name, _a in _werkzeug_funktionen()
             if not ws.einordnung(name)]
    assert "bewerbung_zu_anfrage_konvertieren" in fehlt


def test_eintraege_der_liste_ohne_einordnung_sind_leer():
    assert OHNE_EINORDNUNG == {}, "Ausnahmen brauchen einen Grund im Review"
