"""#1059 — die Karten der Browser-Quellen sagen dasselbe mit denselben Worten.

Gemeldet am 18.09.2026: StepStone, Indeed, LinkedIn und XING gehen
denselben Weg (Claude-Erweiterung im eigenen Browser), und jede Karte
sagte es anders. `langsam` hiess "Browser" und las sich wie ein Wegweiser,
XING trug zweimal "Manuell", `methode` nannte Playwright, die Warnung
verlangte ausdruecklich Google Chrome.

Die Etiketten-Logik selbst prueft der Node-Test
(`frontend/src/lib/quellenBadges.test.mjs`); hier stehen die Regeln ueber
die REGISTRY und ueber die Verdrahtung der Karte.
"""
import re
import sys
from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

KARTE = _repo() / "frontend" / "src" / "components" / "SourceSelectionList.jsx"


def _browser_quellen() -> dict:
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    return {k: e for k, e in SOURCE_REGISTRY.items()
            if str(e.get("zugriffsart") or "").startswith("browser")}


def ohne_kommentare(quelle: str) -> str:
    quelle = re.sub(r"/\*.*?\*/", "", quelle, flags=re.S)
    return "\n".join(z for z in quelle.splitlines() if not z.strip().startswith("//"))


def test_keine_browser_quelle_nennt_playwright_als_methode():
    """`browser_login` nimmt eine Quelle vom internen Lauf aus (#906) —
    Playwright kommt bei ihr nie zum Einsatz. Gilt fuer JEDE
    Browser-Quelle: Monster stand in keinem Bericht und trug denselben
    Widerspruch."""
    quellen = _browser_quellen()
    assert {"stepstone", "indeed", "linkedin", "xing"} <= set(quellen)
    falsch = {k: e.get("methode") for k, e in quellen.items()
              if "playwright" in str(e.get("methode") or "").lower()}
    assert not falsch, falsch


def test_keine_browser_quelle_verlangt_google_chrome():
    """Die Claude-Erweiterung laeuft in jedem Chromium-Browser — der
    Melder nutzt Brave. "Benoetigt Google Chrome" war schlicht falsch."""
    for name, eintrag in _browser_quellen().items():
        if name == "google_jobs":
            continue  # dort ist der GOOGLE-ACCOUNT gemeint, nicht der Browser
        for feld in ("warnung", "login_hinweis"):
            text = str(eintrag.get(feld) or "")
            assert "Benoetigt Google Chrome" not in text, (name, feld)
            assert "im Chrome eingeloggt" not in text, (name, feld)


def test_indeed_sagt_dass_jobspy_denselben_bestand_abdeckt():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    assert "JobSpy" in SOURCE_REGISTRY["indeed"]["warnung"]
    assert "jobspy_indeed" in SOURCE_REGISTRY, "der Verweis zeigt auf eine Quelle, die es gibt"


def test_die_karte_baut_ihre_etiketten_nicht_mehr_selbst():
    """Eine zweite Fassung der Kette in der Komponente waere #963 im
    Frontend (und genau so ist das doppelte "Manuell" entstanden)."""
    karte = ohne_kommentare(KARTE.read_text(encoding="utf-8"))
    assert "quellenBadges(source" in karte
    assert "function speedBadge" not in karte
    for alt in ("Konto + Chrome", "Login noetig", "Session bereit"):
        assert f">{alt}<" not in karte and f'"{alt}"' not in karte, alt
    # Das Tempo-Etikett "Browser" steht auch in der Legende nicht mehr.
    assert "/>Browser</Badge>" not in karte
    assert "Chrome herunterladen" not in karte


def test_der_node_test_laeuft_in_der_ci():
    ci = (_repo() / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "frontend/src/lib/quellenBadges.test.mjs" in ci
