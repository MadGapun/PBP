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
