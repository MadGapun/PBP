"""Welle 4 aus #1087 — Quelltext-Seite (G62, G72; G64-G66, B70 folgen).

Die Oberflaeche belegt `test_g1087_welle4_oberflaeche.py`.
"""
import re
from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


FRONTEND = _repo() / "frontend" / "src"


def _lesen(pfad: Path) -> str:
    return pfad.read_text(encoding="utf-8-sig")


def _jsx_dateien():
    for ordner in ("pages", "components"):
        for pfad in sorted((FRONTEND / ordner).glob("*.jsx")):
            yield pfad


# ══ G72 — ein Kopierweg fuer Claude ═════════════════════════════════════

# Direkt kopieren darf nur, wer eine KENNUNG oder einen Schluessel
# kopiert, keine Anleitung fuer Claude. Die Liste nennt das Argument.
ERLAUBTE_DIREKTKOPIEN = {
    "application.id", "app.id", "shortId", "job.hash", "detailDialog.job.hash",
    "fitDialog.analysis.research_notes", "pairResult.api_key",
    "kennung(e)", "kennung(detail)", "text",
}

DIREKT = re.compile(r"(?:navigator\.clipboard\??\.writeText|copyToClipboard)\(([^()]*(?:\([^()]*\))?[^()]*)\)")


def _direktkopien():
    funde = []
    for pfad in _jsx_dateien():
        if pfad.name == "ui.jsx":
            continue
        for m in DIREKT.finditer(_lesen(pfad)):
            funde.append((pfad.name, m.group(1).strip()))
    return funde


def test_g72_guard_sieht_die_dateien():
    """DoD 8c: der Guard laeuft ueber die echten Seiten, nicht ins Leere."""
    namen = {p.name for p in _jsx_dateien()}
    assert {"JobsPage.jsx", "ApplicationsPage.jsx", "TasksPage.jsx"} <= namen
    assert _direktkopien(), "ohne jeden Fund prueft der Guard nichts"


def test_g72_keine_direkte_kopie_einer_anleitung():
    falsch = [(d, a) for d, a in _direktkopien() if a not in ERLAUBTE_DIREKTKOPIEN]
    assert not falsch, f"Anleitungen gehen ueber copyPrompt: {falsch}"


def test_g72_text_bleibt_nur_fuer_die_kennung_der_menues():
    """`text` ist nur im Menue "Für Claude kopieren" erlaubt — dort ist es
    die Kennung, nicht eine Anleitung."""
    for pfad in _jsx_dateien():
        inhalt = _lesen(pfad)
        for m in DIREKT.finditer(inhalt):
            if m.group(1).strip() != "text":
                continue
            assert pfad.name == "JobsPage.jsx", pfad.name
            anfang = inhalt.index("function FuerClaudeMenue")
            ende = inhalt.index("\nfunction ", anfang + 1)
            assert anfang < m.start() < ende, "writeText(text) ausserhalb des Kennungs-Menues"


def test_g72_copyprompt_zeigt_den_text_bei_fehlschlag():
    app = _lesen(FRONTEND / "App.jsx")
    rumpf = app[app.index("async function copyPrompt("):app.index("async function refreshChrome(")]
    assert "setManuellKopieren(promptToCopy)" in rumpf
    assert "Kopieren hat nicht geklappt" in rumpf
    assert "Kopieren fehlgeschlagen: ${error.message}" not in rumpf
    assert "optionen.erfolg" in rumpf
    assert "data-manuell-kopieren" in app


def test_g72_knoepfe_tragen_mit_claude():
    """Jeder Knopf, der eine Anleitung kopiert, sagt es."""
    aufrufe = re.compile(
        r"onClick=\{\(\) => (?:copyPrompt\(|interviewVorbereitungKopieren\(|"
        r"unterlagenKopieren\(|reanalyzeDocument\(|copyDocumentAnalysisPrompt\()")
    fehlt = []
    for pfad in list(_jsx_dateien()) + [FRONTEND / "App.jsx"]:
        text = _lesen(pfad)
        for m in aufrufe.finditer(text):
            rest = text[m.end():]
            ende = min(x for x in (rest.find("</Button>"), rest.find("</button>")) if x >= 0)
            element = rest[:ende]
            if not any(w in element for w in ("<MitClaude", "ClaudeSymbol", "mit Claude")):
                zeile = text[:m.start()].count("\n") + 1
                fehlt.append(f"{pfad.name}:{zeile}")
    assert not fehlt, fehlt


def test_g72_elwosa_nutzt_copyprompt():
    chat = _lesen(FRONTEND / "components" / "ElwosaSidebarChat.jsx")
    assert "onCopyPrompt?.(code" in chat
    assert "onCopyPrompt={copyPrompt}" in _lesen(FRONTEND / "App.jsx")


# ══ G62 — Stellenkarte und Filterleiste ═════════════════════════════════

def test_g62_karte_ohne_kennung_und_quelle_als_abzeichen():
    jobs = _lesen(FRONTEND / "pages" / "JobsPage.jsx")
    assert "#{String(job.hash).slice(0, 12)}" not in jobs
    assert '<Badge tone="sky">{job.source || "Quelle"}</Badge>' not in jobs
    assert "<DaumenAbzeichen marke={job.fach_daumen}" not in jobs
    assert "kernaussage(job)" in jobs and "kartenGrund(job, datenguetMarke(job))" in jobs
    assert "<FuerClaudeMenue job={job}" in jobs
    assert "<GenauerPruefen" in jobs
    assert "Fit-Analyse\n" not in jobs.replace("\r\n", "\n")


def test_g62_keine_seitengroesse_und_filter_n():
    jobs = _lesen(FRONTEND / "pages" / "JobsPage.jsx")
    assert "pro Seite" not in jobs
    assert "Filter (${filterAnzahl})" in jobs
    assert "{filterOffen ? (" in jobs
    assert "durch aktive Filter verborgen" not in jobs


def test_g62_node_test_in_der_ci():
    ci = _lesen(_repo() / ".github" / "workflows" / "tests.yml")
    assert "node frontend/src/lib/stellenKarte.test.mjs" in ci


# ══ G64 — eine Arbeitsliste ═════════════════════════════════════════════

def test_g64_vorschau_in_dashboard_und_bewerbungen():
    offen = _lesen(FRONTEND / "components" / "OffenBlock.jsx")
    assert "vorschau(block.gruppen" in offen and "kurz.gruppen[key]" in offen
    assert "alleAufgabenText(weitere)" in offen
    bew = _lesen(FRONTEND / "pages" / "ApplicationsPage.jsx")
    assert "VORSCHAU_ZEILEN - upcomingMeetings.length" in bew
    assert "weitere Nachfragen im Kalender" not in bew
    ci = _lesen(_repo() / ".github" / "workflows" / "tests.yml")
    assert "node frontend/src/lib/arbeitsliste.test.mjs" in ci


def test_g64_kalender_zeigt_nur_termine(tmp_path, monkeypatch):
    import os
    from fastapi.testclient import TestClient
    monkeypatch.setenv("BA_DATA_DIR", str(tmp_path))
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path)
    db.save_profile({"name": "Erika Musterfrau"})
    aid = db.add_application({"title": "Sachbearbeitung", "company": "Musterbetrieb GmbH", "status": "beworben"})
    from datetime import date, timedelta
    db.add_follow_up(aid, (date.today() + timedelta(days=3)).isoformat(), "nachfass")
    alt = dash._db
    dash._db = db
    try:
        daten = TestClient(dash.app).get("/api/meetings/calendar?days=365").json()
    finally:
        dash._db = alt
        db.close()
    assert not any(m.get("is_follow_up") for m in daten["meetings"])
    assert daten["nachfassen_anzahl"] >= 1
    kal = _lesen(FRONTEND / "pages" / "CalendarPage.jsx")
    assert "data-nachfassen-verweis" in kal


# ══ G65 — Anzeigenamen statt Rohwerte ═══════════════════════════════════

ROHFELDER = r"(?:status|dismiss_reason|source|bewerbungsart|doc_type|remote_level|kind|herkunft)"
# `{x.status}` als Text (nicht als Attribut `value={...}`), und `${x.source}`
# in einem sichtbaren Satz. HTTP-Statuscodes in Fehlermeldungen bleiben.
ROH_JSX = re.compile(r"(?<![=\w$])\{\s*[\w.?]+\." + ROHFELDER + r"\s*\}")
ROH_TEMPLATE = re.compile(r"\$\{\s*(?!resp\.|res\.|r\.)[\w.?]+\." + ROHFELDER + r"\s*\}")


def test_g65_kein_rohwert_in_jsx():
    funde = []
    for pfad in list(_jsx_dateien()) + [FRONTEND / "App.jsx"]:
        text = _lesen(pfad)
        for regel in (ROH_JSX, ROH_TEMPLATE):
            for m in regel.finditer(text):
                zeile = text[:m.start()].count("\n") + 1
                # Schluessel fuer React (`key={`...${e.herkunft}`}`) sieht niemand.
                if "key={`" in text.splitlines()[zeile - 1]:
                    continue
                funde.append(f"{pfad.name}:{zeile} {m.group(0)}")
    assert not funde, funde


def _werkzeug_und_promptnamen():
    namen = set()
    for pfad in (_repo() / "src" / "bewerbungs_assistent" / "tools").glob("*.py"):
        namen |= set(re.findall(r"@mcp\.tool\([^)]*\)\s*\n(?:\s*@[^\n]+\n)*\s*def (\w+)", _lesen(pfad)))
    namen |= set(re.findall(r'"prompt":\s*"(\w+)"', _lesen(_repo() / "src" / "bewerbungs_assistent" / "services" / "prompt_katalog.py")))
    return {n for n in namen if "_" in n}


def test_g65_guard_kennt_die_werkzeuge():
    namen = _werkzeug_und_promptnamen()
    assert len(namen) > 150 and "stelle_manuell_anlegen" in namen and "jobsuche_workflow" in namen


def test_g65_kein_werkzeugname_im_sichtbaren_text():
    namen = _werkzeug_und_promptnamen()
    textknoten = re.compile(r">([^<>{}]*)<")
    code_zeichen = ("&&", "=>", "?.", "||", "===", "!==", " ? ")
    funde = []
    for pfad in list(_jsx_dateien()) + [FRONTEND / "App.jsx"]:
        text = _lesen(pfad)
        for m in textknoten.finditer(text):
            knoten = m.group(1)
            if any(z in knoten for z in code_zeichen):
                continue
            for wort in re.findall(r"/?\b[a-z]+(?:_[a-z0-9]+)+\b", knoten):
                if wort.lstrip("/") in namen:
                    funde.append(f"{pfad.name}:{text[:m.start()].count(chr(10)) + 1} {wort}")
    assert not funde, funde


def test_g65_tabellen_in_python_und_js_gleich():
    import json
    import sys
    sys.path.insert(0, str(_repo() / "src"))
    from bewerbungs_assistent.services import anzeigenamen
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    js = _lesen(FRONTEND / "lib" / "anzeige.js")

    def tabelle(name):
        block = js[js.index(f"export const {name} = {{"):]
        block = block[:block.index("};")]
        paare = re.findall(r'^\s*(\w+):\s*("(?:[^"\\]|\\.)*")', block, re.M)
        return {k: json.loads(v) for k, v in paare}

    assert tabelle("GRUND_TEXT") == anzeigenamen.GRUND_TEXT
    assert tabelle("BEWERBUNGSART_TEXT") == anzeigenamen.BEWERBUNGSART_TEXT
    quellen = tabelle("QUELLE_TEXT")
    for schluessel, eintrag in SOURCE_REGISTRY.items():
        assert quellen.get(schluessel) == eintrag.get("name"), schluessel
    ci = _lesen(_repo() / ".github" / "workflows" / "tests.yml")
    assert "node frontend/src/lib/anzeige.test.mjs" in ci


def test_g65_nachfass_text_ohne_rohwerte():
    import sys
    sys.path.insert(0, str(_repo() / "src"))
    from bewerbungs_assistent.services.nachfass_text import nachfass_text
    text = nachfass_text({"title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                          "applied_at": "2026-09-04", "bewerbungsart": "mit_dokumenten",
                          "status": "interview_abgeschlossen"})
    assert "04.09.2026" in text and "mit Unterlagen" in text and "Interview abgeschlossen" in text
    assert "mit_dokumenten" not in text and "2026-09-04" not in text


def test_g65_statistik_liefert_quellnamen(tmp_path, monkeypatch):
    monkeypatch.setenv("BA_DATA_DIR", str(tmp_path))
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path)
    db.save_profile({"name": "Erika Musterfrau"})
    db.save_jobs([{"hash": "g65q", "title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                   "url": "https://example.com/g65q", "source": "jobspy_indeed", "score": 3,
                   "description": "x" * 80}])
    daten = db.get_score_stats()
    db.close()
    eintrag = next(s for s in daten["sources"] if s["name"] == "jobspy_indeed")
    assert eintrag["label"] == "Indeed.de (via JobSpy)"
