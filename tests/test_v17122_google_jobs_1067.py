"""#1067 — `google_jobs_url` lieferte ein Auswerte-Skript, das nichts fand.

Gemessen am 21.09.2026 im eingeloggten Browser: der Selektor
`[data-ved][role="listitem"], li[data-ved], div.PwjeAc` traf 13
Elemente, und das waren die Suchreiter (KI-Modus, Alle, Bilder, News,
Videos, Jobs, Homeoffice, Jobtyp, Veroeffentlicht). Keine einzige
Stelle. Der Kommentar im Code sagte es selbst voraus: "DOM-Selektoren
(Stand Mai 2026). Klassen rotieren."

Das Verhalten war schlimmer als ein Ausfall: die Funktion lieferte eine
plausible Liste falscher Karten, ohne Fehler zu melden.

Die Auswertung selbst steht in
`job_scraper/google_jobs_extraction.js` und wird vom Node-Test
`frontend/src/lib/googleJobsExtraction.test.mjs` gegen eine
nachgebaute Seite ausgefuehrt — hier stehen die Fragen, die Python
beantworten kann.
"""
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

JS = ROOT / "src/bewerbungs_assistent/job_scraper/google_jobs_extraction.js"


def test_1067_die_rotierten_klassen_sind_weg():
    """Der gemeldete Selektor und die Titel-/Firmen-Klassen."""
    text = JS.read_text(encoding="utf-8")
    quelle = (ROOT / "src/bewerbungs_assistent/tools/jobs.py").read_text(
        encoding="utf-8-sig")
    for klasse in ("PwjeAc", "PUpOsf", "BjJfJf", "a3jPc", "vNEEBe",
                   "tJ9zfc", "Qk80Jf", "nJlQNd", "data-ved"):
        assert klasse not in text, klasse
        assert klasse not in quelle, klasse


def test_1067_am_sichtbaren_text_verankert():
    text = JS.read_text(encoding="utf-8")
    assert "Offene Stellen" in text
    assert "innerText" in text


def test_1067_das_werkzeug_liefert_die_ausgelieferte_datei():
    """Eine zweite Fassung im Python-String waere #963 ueber die
    Sprachgrenze — und der Node-Test wuerde dann nicht das pruefen, was
    ausgeliefert wird."""
    from bewerbungs_assistent.job_scraper.google_jobs import extraction_js
    assert extraction_js() == JS.read_text(encoding="utf-8").strip()


def test_1067_google_jobs_url_reicht_es_durch():
    import asyncio
    from fastmcp import FastMCP
    from bewerbungs_assistent.job_scraper.google_jobs import extraction_js
    import bewerbungs_assistent.database as _db_mod

    class _DB:
        def __getattr__(self, _):
            raise AssertionError("google_jobs_url braucht die DB nicht")

    mcp = FastMCP("PBP Test")
    from bewerbungs_assistent.tools import jobs as _jobs
    _jobs.register(mcp, _DB(), logging.getLogger("t"))

    async def _run():
        tool = await mcp.get_tool("google_jobs_url")
        res = await tool.run({"keyword": "PLM", "ort": "Hamburg"})
        return getattr(res, "structured_content", res)

    res = asyncio.run(_run())
    assert res["extraction_js"] == extraction_js()
    assert "udm=8" in res["url"]
    # Der Hinweis sagt, was bei einem Fehlerfeld zu tun ist — sonst
    # uebernimmt jemand die falsche Liste doch.
    assert "fehler" in res["hinweis"].lower()
    assert "portal" in res["hinweis"].lower()


def test_1067_das_skript_meldet_seine_fehlerfaelle():
    """Die drei benannten Zustaende stehen im Skript — ausgefuehrt
    werden sie im Node-Test."""
    text = JS.read_text(encoding="utf-8")
    for fall in ("kein_stellenblock", "navigation_statt_stellen",
                 "keine_stellen_erkannt"):
        assert fall in text, fall


def test_1067_der_node_test_laeuft_in_der_ci():
    """DoD 8c: ein Test, den niemand aufruft, schuetzt nichts."""
    ci = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    assert "googleJobsExtraction.test.mjs" in ci


def test_1067_der_node_test_liest_die_ausgelieferte_datei():
    """Sonst prueft er eine Kopie — und genau das haette den gemeldeten
    Fall nicht gefunden."""
    t = (ROOT / "frontend/src/lib/googleJobsExtraction.test.mjs").read_text(
        encoding="utf-8")
    assert "job_scraper/google_jobs_extraction.js" in t
    assert re.search(r"readFileSync", t)
