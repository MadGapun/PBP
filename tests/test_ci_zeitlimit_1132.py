"""Tests fuer #1132 -- das CI-Zeitlimit laesst Platz fuer einen langsamen Vorlauf.

Am 30.09.2026 wurde der Job 'pytest' nach genau 30 Minuten abgebrochen, 28
Sekunden nachdem die Suite vollstaendig durchgelaufen war. Nur der Vorlauf
(Pakete, Browser-Download) hatte diesmal 10,75 statt einer Minute gebraucht.
Der Lauf endete als "abgebrochen", nicht als Fehler -- und die Ueberwachung
der Claude-App meldete null fehlgeschlagene Pruefungen.

Die Tests lesen die Datei im Repo (auch aus einem fremden Arbeitsverzeichnis).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "tests.yml"

#: Suite rund 20 Minuten + Vorlauf bis zu 10 Minuten + Puffer.
MINDESTENS = 40


def _limit(job: str) -> int:
    text = WORKFLOW.read_text(encoding="utf-8")
    block = re.search(rf"^  {re.escape(job)}:[ \t]*\n(.*?)(?=^  \S|\Z)", text,
                      re.S | re.M)
    assert block, f"Job {job!r} fehlt in {WORKFLOW.name}"
    zeile = re.search(r"^    timeout-minutes:[ \t]*(\d+)[ \t]*$", block.group(1),
                      re.M)
    assert zeile, f"Job {job!r} hat kein timeout-minutes"
    return int(zeile.group(1))


def test_1132_pytest_job_laesst_platz_fuer_einen_langsamen_vorlauf():
    limit = _limit("pytest")
    assert limit >= MINDESTENS, (
        f"timeout-minutes={limit}: zu knapp. Die Suite braucht rund 20 Minuten, "
        f"der Vorlauf war schon einmal 11 Minuten langsam (#1132).")


def test_1132_das_limit_bleibt_ein_limit():
    """Ohne Obergrenze haengt ein festgefahrener Lauf Stunden am Runner."""
    assert _limit("pytest") <= 90


def test_1132_der_release_ablauf_nennt_den_umgang_mit_abgebrochen():
    """AK 2: 'abgebrochen' ist weder gruen noch rot. Der Satz steht im
    Release-Ablauf, nicht nur in diesem Test."""
    text = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    ablauf = text[text.index("## Release-Workflow"):]
    ablauf = ablauf[:ablauf.index("\n## ", 5)]
    assert "Abgebrochen" in ablauf and "weder" in ablauf
    assert "cancelled" in ablauf  # der konkrete Wert, den man liest
