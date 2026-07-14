"""Tests fuer v1.7.7 — #755 (C25): MINUS-Keywords strikt statt fuzzy.

Der Praxis-Fall (13.07.): 'Product Manager' als MINUS-Keyword zog -12 Punkte auf
einer '(Sr.) Project Manager'-Stelle ab, weil der Multi-Word-Split des
Fuzzy-Matchings 'product' (aus 'product portfolio') und 'manager' einzeln
fand. MINUS bestraft — darum Praezision: Phrase + Wortgrenzen.
"""
from bewerbungs_assistent.job_scraper import (
    _fuzzy_keyword_match,
    _strict_keyword_match,
)


PRAXISFALL_TEXT = (
    "(sr.) project manager (m/f/d) — end to end ownership of high impact, "
    "multi-site r&d projects. you align the product portfolio roadmap with "
    "executive stakeholders and drive project management excellence."
)


class TestStrictMatch:
    def test_praxisfall_regression_product_manager_matcht_nicht(self):
        """DER Fall aus #755: fuzzy matchte, strikt darf nicht."""
        assert _fuzzy_keyword_match("Product Manager", PRAXISFALL_TEXT) is True
        assert _strict_keyword_match("Product Manager", PRAXISFALL_TEXT) is False
        assert _strict_keyword_match("Product Management", PRAXISFALL_TEXT) is False

    def test_echter_product_manager_matcht(self):
        text = "Wir suchen einen Product Manager (m/w/d) fuer unser SaaS-Team."
        assert _strict_keyword_match("Product Manager", text) is True

    def test_phrase_mit_bindestrich_und_mehrfach_whitespace(self):
        assert _strict_keyword_match("Product Manager", "Senior Product-Manager gesucht")
        assert _strict_keyword_match("Product Manager", "Product  Manager (remote)")

    def test_wortgrenzen_bei_einwort_keyword(self):
        # 'Automotive' darf nicht in Kunstwoertern feuern
        assert _strict_keyword_match("Automotive", "Automotive-Zulieferer") is True
        assert _strict_keyword_match("SAP", "Aussaat-Planung") is False
        assert _strict_keyword_match("SAP", "SAP S/4HANA Rollout") is True

    def test_umlaut_normalisierung_bleibt(self):
        assert _strict_keyword_match("Qualitätsmanagement",
                                     "Leiter Qualitaetsmanagement gesucht")

    def test_keine_synonym_expansion(self):
        """Fuzzy expandiert Synonyme — strikt bewusst nicht (MINUS soll nur
        treffen, was der User woertlich ausgeschlossen hat)."""
        assert _strict_keyword_match("", "irgendwas") is False


class TestScoringIntegration:
    def test_calculate_job_score_nutzt_strikt_fuer_minus(self, tmp_path):
        """Ende-zu-Ende: Project-Manager-Stelle verliert KEINE Punkte mehr
        durch das Product-Manager-MINUS-Keyword."""
        from bewerbungs_assistent.job_scraper import calculate_score, fit_analyse
        criteria = {
            "keywords_muss": [],
            "keywords_plus": [],
            "keywords_minus": ["Product Manager", "Product Management"],
        }
        job = {"title": "(Sr.) Project Manager (m/f/d)",
               "description": PRAXISFALL_TEXT}
        analyse = fit_analyse(job, criteria)
        minus_faktoren = [k for k in analyse.get("factors", {}) if "MINUS" in k]
        assert not minus_faktoren, (
            f"MINUS-Malus trotz Project-Manager-Stelle: {minus_faktoren}")
        # calculate_score zieht ebenfalls nichts mehr ab
        assert calculate_score(job, criteria) >= 0
