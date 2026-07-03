"""Tests fuer v1.7.4 — #746 (H17): Melde-Hilfe-Prompt problem_melden.

Claude versucht erst eine Sofortloesung, formuliert dann den fertigen,
PII-gescrubbten Report — Endanwender muessen kein GitHub koennen.
"""
from bewerbungs_assistent.prompts import (
    build_problem_melden_prompt,
    build_tipps_und_tricks_prompt,
)


class TestProblemMeldenPrompt:
    def test_sofortloesung_vor_report(self):
        text = build_problem_melden_prompt()
        # Reihenfolge: erst helfen, dann melden
        assert text.index("SOFORTLOESUNG") < text.index("REPORT FORMULIEREN")
        assert "pbp_diagnose()" in text
        assert "quellen_health_check()" in text
        assert "pbp_grenze_melden()" in text

    def test_pii_scrub_pflicht(self):
        text = build_problem_melden_prompt()
        assert "ANONYMISIEREN" in text
        for platzhalter in ("<PERSON>", "<USER>", "<FIRMA>", "<email-anonymisiert>"):
            assert platzhalter in text, f"Platzhalter fehlt: {platzhalter}"

    def test_github_link_und_beschreibung(self):
        text = build_problem_melden_prompt("Suche findet nichts")
        assert "github.com/MadGapun/PBP/issues/new" in text
        assert 'Suche findet nichts' in text

    def test_mail_alternative_ohne_github(self):
        """User-Vorgabe: wer kein GitHub-Konto will, bekommt den Mail-Weg —
        die etablierte Service-Adresse (auch Telemetrie-Empfaenger)."""
        text = build_problem_melden_prompt()
        assert "PBP-Service@Elwosa.de" in text
        assert "PBP-Service@Elwosa.de" in build_tipps_und_tricks_prompt()

    def test_ohne_beschreibung_fragt_nach(self):
        text = build_problem_melden_prompt()
        assert "Frage zuerst kurz" in text


class TestTippsVerweisenAufMeldeHilfe:
    def test_tipps_enthalten_melde_sektion(self):
        text = build_tipps_und_tricks_prompt()
        assert "PROBLEME & IDEEN MELDEN" in text
        assert "problem_melden" in text
        assert "Sofortloesung" in text
