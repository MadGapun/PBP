"""Welle 6 aus #1087 — Einstellungen, Profil, Rueckweg, Hilfe, Kennzahlen.

* G61 (B2-B4, B6): Kennzahlen mit fester Bedeutung.
"""
import re
from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


FRONTEND = _repo() / "frontend" / "src"


def _lesen(pfad: Path) -> str:
    return pfad.read_text(encoding="utf-8-sig")


# ══ G61 — Kennzahlen mit fester Bedeutung ═══════════════════════════════

def test_g61_keine_zufaellige_perspektive():
    seite = _lesen(FRONTEND / "pages" / "DashboardPage.jsx")
    assert "Math.random" not in seite
    assert "bewerbungenProWoche(applicationTimestamps, wochenAnsicht)" in seite
    assert "WOCHEN_ANSICHTEN.map" in seite
    assert 'label="Bewerbungen pro Woche"' in seite


def test_g61_top_stellen_nach_den_regeln_des_stellen_tabs():
    seite = _lesen(FRONTEND / "pages" / "DashboardPage.jsx")
    assert 'listenParameter(FILTER_STANDARD, "", "", "active")' in seite
    assert "topStellen(data.topJobs || [])" in seite


def test_g61_kein_null_gehalt():
    seite = _lesen(FRONTEND / "pages" / "DashboardPage.jsx")
    assert "gehaltsWert(salaryMetrics.averageMin)" in seite
    assert "gehaltsWert(salaryMetrics.bandMin)" in seite
    assert '"Keine Angabe"' not in seite[seite.index("const salaryMetrics"):seite.index("const lastSearchAt")]


def test_g61_seitenleiste_zaehlt_nur_was_aufmerksamkeit_braucht():
    import sys
    sys.path.insert(0, str(_repo() / "src"))
    from bewerbungs_assistent.services.workspace_service import build_workspace_summary
    daten = build_workspace_summary(
        profile={"name": "Test", "positions": [], "education": [], "skills": [], "documents": []},
        jobs=[{"hash": "a"}, {"hash": "b"}],
        applications=[{"id": "1", "status": "beworben"}, {"id": "2", "status": "beworben"},
                      {"id": "3", "status": "interview"}],
        source_summary={"active": 0, "total": 9, "active_keys": []},
        search_status={"last_search": None, "days_ago": None, "status": "nie"},
        follow_up_summary={"total": 2, "due": 1},
    )
    nav = daten["navigation"]
    # Drei laufende Bewerbungen, eine faellige Nachfassung: die Zahl ist 1.
    assert nav["applications_badge"] == "1"
    assert nav["titel"]["bewerbungen"] == "1 Nachfassung ist fällig"
    assert nav["titel"]["stellen"] == "2 Stellen warten auf deine Entscheidung"
    assert nav["titel"]["einstellungen"] == "Keine Jobbörse ausgewählt"
    assert nav["titel"]["profil"].startswith("Im Profil fehlt noch:")


def test_g61_seitenleiste_zeigt_den_titel():
    leiste = _lesen(FRONTEND / "components" / "Sidebar.jsx")
    assert "title={badgeTitles[tab.id] || undefined}" in leiste
    app = _lesen(FRONTEND / "App.jsx")
    assert "badgeTitles={chrome.workspace?.navigation?.titel || {}}" in app


# ══ G67 — Rueckweg und Loeschmuster ═════════════════════════════════════

import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, str(_repo() / "src"))


@pytest.fixture
def db():
    import importlib
    tmpdir = tempfile.mkdtemp(prefix="pbp_g1087w6_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    d = _db_mod.Database()
    d.initialize()
    assert str(tmpdir) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test Person"})
    yield d
    d.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_g67_statuswechsel_laesst_sich_zuruecknehmen(db):
    from bewerbungs_assistent.services import status_rueckweg as rw
    aid = db.add_application({"title": "A", "company": "Musterbetrieb GmbH", "status": "beworben"})
    fid = db.add_follow_up(aid, "2026-10-01")
    events_vorher = len(db.get_application(aid)["events"])
    weg = rw.wechseln(db, aid, "abgelehnt", profile_id=db.get_active_profile_id())
    assert weg["vorher"] == "beworben" and weg["archiviert"] is True
    assert fid in weg["geschlossen"]
    assert rw.zuruecknehmen(db, aid, weg, profile_id=db.get_active_profile_id())
    app = db.get_application(aid)
    assert app["status"] == "beworben"
    assert len(app["events"]) == events_vorher
    assert fid in {fu["id"] for fu in db.get_pending_follow_ups()}


def test_g67_zuruecknehmen_raeumt_die_interview_markierung(db):
    from bewerbungs_assistent.services import status_rueckweg as rw
    aid = db.add_application({"title": "A", "company": "Musterbetrieb GmbH", "status": "beworben"})
    weg = rw.wechseln(db, aid, "interview_abgeschlossen", profile_id=db.get_active_profile_id())
    assert weg["angelegt"], "der Wechsel legt eine Nachfrage an"
    rw.zuruecknehmen(db, aid, weg, profile_id=db.get_active_profile_id())
    zeile = db.connect().execute("SELECT has_reached_interview FROM applications WHERE id=?", (aid,)).fetchone()
    assert zeile["has_reached_interview"] == 0
    assert not {fu["id"] for fu in db.get_pending_follow_ups()} & set(weg["angelegt"])


def test_g67_papierkorb_legt_die_notiz_genau_wieder_an(db):
    from bewerbungs_assistent.services import papierkorb
    aid = db.add_application({"title": "A", "company": "Musterbetrieb GmbH", "status": "beworben"})
    db.add_application_note(aid, "Wichtig: Ansprechpartnerin anrufen")
    note = [e for e in db.get_application(aid)["events"] if e["status"] == "notiz"][0]
    zeile = papierkorb.aufheben(db, "notiz", note["id"])
    db.delete_application_event(note["id"], aid)
    assert papierkorb.wiederherstellen(db, "notiz", zeile)
    wieder = [e for e in db.get_application(aid)["events"] if e["status"] == "notiz"][0]
    assert wieder["id"] == note["id"] and wieder["event_date"] == note["event_date"]
    # Nicht ueber eine bestehende Zeile, nicht fuer fremde Arten.
    assert not papierkorb.wiederherstellen(db, "notiz", zeile)
    assert not papierkorb.wiederherstellen(db, "bewerbung", {"id": "x"})
    falsch = dict(zeile, id=zeile["id"] + 1000, status="abgelehnt")
    assert not papierkorb.wiederherstellen(db, "notiz", falsch)


def test_g67_endpunkte_liefern_den_rueckweg(db):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    c = TestClient(dash.app)
    aid = db.add_application({"title": "A", "company": "Musterbetrieb GmbH", "status": "beworben"})
    r = c.put(f"/api/applications/{aid}/status", json={"status": "zurueckgezogen"}).json()
    assert r["rueckweg"]["vorher"] == "beworben"
    assert c.post(f"/api/applications/{aid}/status/rueckgaengig", json={"rueckweg": r["rueckweg"]}).status_code == 200
    assert db.get_application(aid)["status"] == "beworben"
    task = c.post("/api/tasks", json={"titel": "Unterlagen", "application_id": aid}).json()
    tid = task.get("id") or task.get("task_id") or task.get("task", {}).get("id")
    weg = c.delete(f"/api/tasks/{tid}").json()["rueckweg"]
    assert weg["art"] == "aufgabe"
    assert c.post("/api/wiederherstellen", json=weg).status_code == 200
    # Die Notiz: der Loesch-Endpunkt gibt die Zeile mit, und genau sie
    # kommt zurueck (Gegenprobe: ohne Rueckweg war dieser Weg ungeprueft).
    assert c.post(f"/api/applications/{aid}/notes", json={"text": "Rueckruf am Montag"}).status_code == 200
    def _ereignisse():
        return [dict(z) for z in db.connect().execute(
            "SELECT * FROM application_events WHERE application_id=?", (aid,)).fetchall()]
    notiz = [e for e in _ereignisse() if e.get("status") == "notiz"][-1]
    weg = c.delete(f"/api/applications/{aid}/notes/{notiz['id']}").json()["rueckweg"]
    assert weg["art"] == "notiz" and weg["zeile"]["id"] == notiz["id"]
    assert c.post("/api/wiederherstellen", json=weg).status_code == 200
    assert any(e["id"] == notiz["id"] for e in _ereignisse())


def _jsx_und_js():
    for p in sorted(FRONTEND.rglob("*")):
        if p.suffix in (".jsx", ".js") and "node_modules" not in p.parts:
            yield p


def test_g67_kein_browser_confirm_mehr():
    funde = [p.name for p in _jsx_und_js()
             if re.search(r"(?<![\w.])(?:window\.)?confirm\(", _lesen(p))]
    assert not funde, funde


def test_g67_dialog_hat_kreuz_und_fragt_vor_dem_verwerfen():
    ui = _lesen(FRONTEND / "components" / "ui.jsx")
    modal = ui[ui.index("export function Modal("):ui.index("export function ToastViewport")]
    assert 'aria-label="Schließen"' in modal and "onClick={schliessenVersuchen}" in modal
    assert "onInputCapture={() => setGeaendert(true)}" in modal
    assert "if (schutz && geaendert)" in modal
    assert "data-verwerfen-frage" in modal


def test_g67_kleines_mit_rueckweg():
    app = _lesen(FRONTEND / "pages" / "ApplicationsPage.jsx")
    assert 'geloeschtMitRueckweg(antwort, "Notiz gelöscht."' in app
    assert 'geloeschtMitRueckweg(antwort, "Aufgabe gelöscht."' in app
    tasks = _lesen(FRONTEND / "pages" / "TasksPage.jsx")
    assert 'geloeschtMitRueckweg(antwort, "Aufgabe gelöscht."' in tasks
    assert "Aufgabe wirklich löschen" not in tasks
    kontakte = _lesen(FRONTEND / "pages" / "ContactsPage.jsx")
    assert kontakte.count('geloeschtMitRueckweg(antwort, "Referenz entfernt."') == 2


# ══ G68 — Hilfe-Dialog stimmt und deckt alle Tabs ══════════════════════

def _hilfe_prompt_ids() -> set[str]:
    text = _lesen(FRONTEND / "lib" / "hilfe.js")
    ids = set()
    for liste in re.findall(r"prompts:\s*\[([^\]]*)\]", text):
        ids.update(re.findall(r'"([a-z_]+)"', liste))
    return ids


def test_g68_prompts_der_hilfe_stehen_im_katalog():
    from bewerbungs_assistent.services import prompt_katalog
    katalog = {e["id"] for e in prompt_katalog.EINTRAEGE}
    ids = _hilfe_prompt_ids()
    assert len(ids) >= 10
    assert ids <= katalog, ids - katalog
    melde = re.search(r'MELDE_PROMPT = "([a-z_]+)"', _lesen(FRONTEND / "lib" / "hilfe.js")).group(1)
    assert melde in katalog


def test_g68_mailadresse_ist_die_des_meldewegs():
    from bewerbungs_assistent import prompts
    quelle = Path(prompts.__file__).read_text(encoding="utf-8")
    adresse = re.search(r'MELDE_MAIL = "([^"]+)"', _lesen(FRONTEND / "lib" / "hilfe.js")).group(1)
    assert adresse in quelle


def test_g68_dialog_liest_die_tabelle():
    app = _lesen(FRONTEND / "App.jsx")
    assert "<HilfeTab page={page}" in app
    assert '{helpTab === "melden" && <MeldenTab' in app
    assert '{ id: "melden", label: "Melden" }' in app
    # Die alten Karten stehen nicht mehr im Dialog.
    assert "aktualisieren sich automatisch" not in app
    assert "Der Score (0" not in app
    assert '{ id: "bug", label' not in app
    inhalt = _lesen(FRONTEND / "components" / "HilfeInhalt.jsx")
    assert "HILFE[page]" in inhalt
    assert 'fetch("/api/prompts")' in inhalt
    assert "MELDEWEGE.map" in inhalt


def test_g68_node_test_laeuft_in_der_ci():
    ci = (_repo() / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "node frontend/src/lib/hilfe.test.mjs" in ci


# ══ G69 — Profil-Tab entflechten ═══════════════════════════════════════

def test_g69_suche_ist_eine_eigene_seite():
    app = _lesen(FRONTEND / "App.jsx")
    assert '{ id: "suche", title: "Suche & Bewertung"' in app
    assert '{page === "suche" ? <ProfilePage bereich="suche" /> : null}' in app
    utils = _lesen(FRONTEND / "utils.js")
    assert '"suche",' in utils[:utils.index("];")]
    from bewerbungs_assistent.services import dashboard_link, menue
    assert "suche" in dashboard_link.REITER
    assert menue.pfad("suche") == "Suche & Bewertung"


def test_g69_profil_zeigt_keine_suchbegriffe_mehr():
    seite = _lesen(FRONTEND / "pages" / "ProfilePage.jsx")
    # Die Suchkarte steht nur im Bereich "suche", alles andere nur im Profil.
    such = seite.index('<Card id="suche-begriffe"')
    assert seite.rfind("{zeigeSuche && (", 0, such) > seite.rfind("{zeigeProfil && (", 0, such)
    erfahrung = seite.index('<Card id="profil-erfahrung"')
    assert seite.rfind("{zeigeProfil && (", 0, erfahrung) > such
    persoenlich = seite.index('<Card id="profil-persoenlich"')
    assert seite.rfind("{zeigeProfil && (", 0, persoenlich) > 0
    assert "profil-suchkriterien" not in seite and "profil-blacklist" not in seite


def test_g69_regler_sind_eingeklappt():
    seite = _lesen(FRONTEND / "pages" / "ProfilePage.jsx")
    details = seite.index('<details id="suche-feinabstimmung"')
    regler = seite.index("{weightingCards.map((card) => renderWeightRow(card))}")
    ende = seite.index("</details>", details)
    assert details < regler < ende


def test_g69_reiternamen_passen_zum_inhalt():
    from bewerbungs_assistent.services.menue import EINSTELLUNGEN_REITER
    assert EINSTELLUNGEN_REITER["ablehnungsgruende"] == "Ablehnungsgründe"
    reiter = _lesen(FRONTEND / "lib" / "einstellungenReiter.js")
    assert '{ id: "bewerten", label: "Ablehnungsgründe", gruppe: "erweitert" }' in reiter
    assert 'label: "Bewertung"' not in _lesen(FRONTEND / "App.jsx")


def test_g69_hinweise_und_verweise_zeigen_auf_die_suche():
    from bewerbungs_assistent.services.onboarding_hints import HINT_DEFINITIONS
    tabs = {h["id"]: h["tab"] for h in HINT_DEFINITIONS}
    assert tabs["c86_gehalt_nur_einstellungsseite"] == "suche"
    assert tabs["c91_schwelle_ist_jetzt_stufe"] == "suche"
    paket = _repo() / "src" / "bewerbungs_assistent"
    for p in paket.rglob("*.py"):
        text = p.read_text(encoding="utf-8-sig")
        assert '"Suchkriterien (Einstellungsseite)"' not in text, p.name
        assert '"Profil › Blacklist"' not in text, p.name
    assert 'navigateTo("suche")}>Suchbegriffe öffnen' in _lesen(FRONTEND / "pages" / "JobsPage.jsx")


# ══ G70 — Einstellungen: Grundlagen und Erweitert ══════════════════════

def _ohne_kommentare(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def _reiter() -> list[tuple[str, str, str]]:
    text = _lesen(FRONTEND / "lib" / "einstellungenReiter.js")
    return re.findall(r'\{ id: "([a-z_]+)", label: "([^"]+)", gruppe: "([a-z]+)" \}', text)


def test_g70_grundlagen_sind_wenige():
    reiter = _reiter()
    grundlagen = [label for _i, label, g in reiter if g == "grundlagen"]
    assert grundlagen == ["Quellen", "Erscheinungsbild", "Datenschutz", "Ordner", "Claude (Cloud)"]
    ids = {i for i, _l, _g in reiter}
    seite = _lesen(FRONTEND / "pages" / "SettingsPage.jsx")
    # Jeder Reiter hat Inhalt, und jeder Inhalt einen Reiter.
    inhalte = set(re.findall(r'settingsTab === "([a-z_]+)"', seite))
    assert ids == inhalte, (ids ^ inhalte)
    assert "const tabs = SETTINGS_REITER;" in seite
    assert "data-erweitert-schalter" in seite
    app = _lesen(FRONTEND / "App.jsx")
    assert "items: SETTINGS_REITER.map" in app


def test_g70_menuepfade_nennen_jeden_reiter():
    from bewerbungs_assistent.services.menue import EINSTELLUNGEN_REITER
    assert set(EINSTELLUNGEN_REITER.values()) == {label for _i, label, _g in _reiter()}


def test_g70_eine_nachfass_frist():
    seite = _ohne_kommentare(_lesen(FRONTEND / "pages" / "SettingsPage.jsx"))
    # Die Frist nach einer Bewerbung steht genau einmal als Eingabe.
    assert seite.count('saveSetting("followup_default_days"') == 1
    assert "saveFollowupSettings({ followup_default_days" not in seite
    assert "Follow-up-Automation" not in seite
    karte = seite.index("Nachfassen nach einem Interview")
    assert seite.rfind('settingsTab === "automatik"', 0, karte) > seite.rfind('settingsTab === "', 0, karte) - 1


def test_g70_bericht_ist_ein_eigener_bereich():
    seite = _lesen(FRONTEND / "pages" / "SettingsPage.jsx")
    bericht = seite.index('<h2 className="text-base font-semibold text-ink">Bewerbungsbericht</h2>')
    assert seite.rfind('settingsTab === "', 0, bericht) == seite.rfind('settingsTab === "bericht"', 0, bericht)
    ordner = seite.index("<AblageOrdnerCard")
    assert seite.rfind('settingsTab === "', 0, ordner) == seite.rfind('settingsTab === "ordner"', 0, ordner)


def test_g70_automatik_in_klartext():
    seite = _ohne_kommentare(_lesen(FRONTEND / "pages" / "SettingsPage.jsx"))
    for alt in ("Bewerbungs-Lifecycle", "Auto-Ablauf", "Auto-Followup", "Sofort-Lauf",
                "Scraper-Quellen", "Ollama lernt aus Verhalten", "Laeuft...", "Naechster"):
        assert alt not in seite, alt


def test_g70_quellen_ein_satz_aus_nutzersicht():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    from bewerbungs_assistent.services import quellen_texte
    assert set(SOURCE_REGISTRY) <= set(quellen_texte.KURZ), set(SOURCE_REGISTRY) - set(quellen_texte.KURZ)
    for key, satz in quellen_texte.KURZ.items():
        assert satz.endswith(".") and satz.count(". ") == 0, key
        assert len(satz) <= 110, key
        assert not re.search(r"#\d|\bAPI\b|MIT\)|python-|Scraper|REST|RSS|JSON|\bae|oe\b|ue\b", satz), key
        assert not re.search(r"\b(Oeffentlich|Groesst|fuer|ueber)\b", satz), key


def test_g70_die_quellenzeile_liefert_den_satz():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    from bewerbungs_assistent.services.search_service import build_source_rows
    from bewerbungs_assistent.services.quellen_texte import KURZ
    zeilen = {z["key"]: z for z in build_source_rows(SOURCE_REGISTRY, [])}
    assert zeilen["bundesagentur"]["kurz"] == KURZ["bundesagentur"]
    liste = _lesen(FRONTEND / "components" / "SourceSelectionList.jsx")
    assert "{source.kurz || source.beschreibung}" in liste
    seite = _lesen(FRONTEND / "pages" / "SettingsPage.jsx")
    assert "{quelle.kurz || quelle.beschreibung}" in seite
    assert "onChange={(event) => onToggle?.(quelle, event.target.checked)}" in seite
