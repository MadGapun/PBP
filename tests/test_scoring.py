"""Tests for the scoring and keyword system.

Covers calculate_score, fit_analyse, detect_remote_level,
stelle_hash, build_search_keywords, and weight configuration.
"""

import pytest
from bewerbungs_assistent.job_scraper import (
    calculate_score, fit_analyse, detect_remote_level,
    stelle_hash, build_search_keywords,
)


# === Helpers ===

def _job(title="Test", description="", remote="unbekannt", distance=None,
         employment_type="festanstellung"):
    """Create a minimal job dict for testing."""
    return {
        "hash": "test123",
        "title": title,
        "description": description,
        "remote_level": remote,
        "distance_km": distance,
        "employment_type": employment_type,
        "url": "https://example.com",
    }


def _criteria(muss=None, plus=None, ausschluss=None, gewichtung=None):
    """Create a minimal criteria dict for testing."""
    c = {}
    if muss is not None:
        c["keywords_muss"] = muss
    if plus is not None:
        c["keywords_plus"] = plus
    if ausschluss is not None:
        c["keywords_ausschluss"] = ausschluss
    if gewichtung is not None:
        c["gewichtung"] = gewichtung
    return c


# === calculate_score ===

class TestCalculateScore:
    def test_muss_keyword_hit(self):
        """MUSS keywords found → score > 0."""
        job = _job(title="Senior PLM Consultant")
        criteria = _criteria(muss=["PLM"])
        score = calculate_score(job, criteria)
        assert score > 0

    def test_muss_keyword_miss(self):
        """No MUSS keyword found when MUSS list is set → score = 0."""
        job = _job(title="Java Developer")
        criteria = _criteria(muss=["PLM", "Windchill"])
        score = calculate_score(job, criteria)
        assert score == 0

    def test_plus_keyword_bonus(self):
        """PLUS keywords add to the score."""
        job = _job(title="PLM Consultant", description="Python und Agile Methoden")
        criteria = _criteria(muss=["PLM"], plus=["Python", "Agile"])
        score = calculate_score(job, criteria)
        # MUSS=2 + 2xPLUS=2 = 4 (default weights)
        assert score == 4

    def test_ausschluss_keyword(self):
        """AUSSCHLUSS keyword present → score = 0 regardless of other matches."""
        job = _job(title="PLM Consultant Zeitarbeit")
        criteria = _criteria(muss=["PLM"], ausschluss=["Zeitarbeit"])
        score = calculate_score(job, criteria)
        assert score == 0

    def test_remote_bonus(self):
        """Remote/hybrid jobs get bonus points."""
        job_remote = _job(title="PLM Engineer", remote="remote")
        job_onsite = _job(title="PLM Engineer", remote="unbekannt")
        criteria = _criteria(muss=["PLM"])
        score_remote = calculate_score(job_remote, criteria)
        score_onsite = calculate_score(job_onsite, criteria)
        assert score_remote > score_onsite

    def test_hybrid_bonus(self):
        """Hybrid jobs also get the remote bonus."""
        job = _job(title="PLM Engineer", remote="hybrid")
        criteria = _criteria(muss=["PLM"])
        score = calculate_score(job, criteria)
        # MUSS=2 + remote=2 = 4
        assert score == 4

    def test_distance_bonus(self):
        """Jobs within 80km get bonus points."""
        job_near = _job(title="PLM Admin", distance=30)
        job_far = _job(title="PLM Admin", distance=500)
        criteria = _criteria(muss=["PLM"])
        score_near = calculate_score(job_near, criteria)
        score_far = calculate_score(job_far, criteria)
        assert score_near > score_far

    def test_distance_malus(self):
        """Jobs over 200km get a penalty."""
        job = _job(title="PLM Berater", distance=300)
        criteria = _criteria(muss=["PLM"])
        score = calculate_score(job, criteria)
        # MUSS=2 - fern_malus=3 = max(0, -1) = 0
        assert score == 0

    def test_custom_weights(self):
        """Custom weights override defaults."""
        job = _job(title="PLM Consultant", description="Python")
        criteria = _criteria(
            muss=["PLM"],
            plus=["Python"],
            gewichtung={"muss": 5, "plus": 3, "remote": 1, "naehe": 1, "fern_malus": 1},
        )
        score = calculate_score(job, criteria)
        # MUSS=5 + PLUS=3 = 8
        assert score == 8

    def test_case_insensitive(self):
        """Keyword matching is case-insensitive."""
        job = _job(title="plm consultant", description="WINDCHILL project")
        criteria = _criteria(muss=["PLM"], plus=["Windchill"])
        score = calculate_score(job, criteria)
        assert score > 0

    def test_no_criteria(self):
        """Empty criteria → score = 0 (no MUSS hit)."""
        job = _job(title="Anything")
        score = calculate_score(job, {})
        assert score == 0

    def test_empty_muss_with_plus(self):
        """No MUSS keywords but PLUS keywords present → score from PLUS only."""
        job = _job(title="Python Developer")
        criteria = _criteria(plus=["Python"])
        score = calculate_score(job, criteria)
        # No MUSS list → muss_found=0, but muss is empty → score not zeroed
        assert score == 1  # 1x PLUS with default weight 1

    def test_freelance_no_distance_malus(self):
        """Freelance jobs should not get distance penalty (#112)."""
        job_freelance = _job(title="PLM Berater", distance=300,
                             employment_type="freelance")
        job_fest = _job(title="PLM Berater", distance=300,
                        employment_type="festanstellung")
        criteria = _criteria(muss=["PLM"])
        score_freelance = calculate_score(job_freelance, criteria)
        score_fest = calculate_score(job_fest, criteria)
        # Freelance: MUSS=2, no malus = 2
        # Festanstellung: MUSS=2 - fern_malus=3 = max(0, -1) = 0
        assert score_freelance == 2
        assert score_fest == 0

    def test_freelance_moderate_distance_no_penalty(self):
        """Freelance 150km should have no slight penalty either (#112)."""
        job_freelance = _job(title="PLM Berater", distance=150,
                             employment_type="freelance")
        job_fest = _job(title="PLM Berater", distance=150,
                        employment_type="festanstellung")
        criteria = _criteria(muss=["PLM"])
        score_freelance = calculate_score(job_freelance, criteria)
        score_fest = calculate_score(job_fest, criteria)
        assert score_freelance > score_fest


# === fit_analyse ===

class TestFitAnalyse:
    def test_basic_analysis(self):
        """fit_analyse returns expected structure."""
        job = _job(title="PLM Consultant", description="Python, Agile")
        criteria = _criteria(muss=["PLM"], plus=["Python", "Agile"])
        result = fit_analyse(job, criteria)
        assert "total_score" in result
        assert "muss_hits" in result
        assert "missing_muss" in result
        assert "plus_hits" in result
        assert "factors" in result
        assert "risks" in result
        assert result["muss_hits"] == ["PLM"]
        assert len(result["plus_hits"]) == 2

    def test_missing_muss_risk(self):
        """Missing MUSS keywords appear in risks."""
        job = _job(title="Developer")
        criteria = _criteria(muss=["PLM", "Windchill"])
        result = fit_analyse(job, criteria)
        assert len(result["missing_muss"]) == 2
        assert any("MUSS-Keywords" in r for r in result["risks"])

    def test_no_url_risk(self):
        """Job without URL gets a risk warning."""
        job = _job(title="PLM Test")
        job["url"] = ""
        criteria = _criteria(muss=["PLM"])
        result = fit_analyse(job, criteria)
        assert any("Kein Link" in r for r in result["risks"])


# === detect_remote_level ===

class TestDetectRemote:
    def test_full_remote(self):
        """Full remote keywords detected."""
        assert detect_remote_level("100% Remote Position") == "remote"

    def test_hybrid(self):
        """Hybrid work detected."""
        assert detect_remote_level("Hybrides Arbeiten moeglich, 2-3 Tage Homeoffice") == "hybrid"

    def test_homeoffice(self):
        """Homeoffice keyword detected as remote."""
        assert detect_remote_level("Homeoffice nach Einarbeitung") == "remote"

    def test_unknown(self):
        """No remote keywords → unbekannt."""
        assert detect_remote_level("Buero in Hamburg, Vollzeit") == "unbekannt"


# === stelle_hash ===

class TestStelleHash:
    def test_deterministic(self):
        """Same input always produces same hash."""
        h1 = stelle_hash("stepstone.de", "PLM Consultant")
        h2 = stelle_hash("stepstone.de", "PLM Consultant")
        assert h1 == h2

    def test_different_titles(self):
        """Different titles produce different hashes."""
        h1 = stelle_hash("stepstone.de", "PLM Consultant")
        h2 = stelle_hash("stepstone.de", "Java Developer")
        assert h1 != h2

    def test_normalization(self):
        """Hashes are case-insensitive and ignore special chars."""
        h1 = stelle_hash("stepstone.de", "PLM Consultant (m/w/d)")
        h2 = stelle_hash("stepstone.de", "plm consultant mwd")
        assert h1 == h2


# === build_search_keywords ===

class TestBuildKeywords:
    def test_empty_criteria(self, tmp_db):
        """No keywords in DB → empty dict."""
        result = build_search_keywords(tmp_db)
        assert result == {}

    def test_keywords_built(self, tmp_db):
        """Keywords from DB produce source-specific formats."""
        tmp_db.set_search_criteria("keywords_muss", ["PLM Consultant"])
        tmp_db.set_search_criteria("keywords_plus", ["Python"])
        result = build_search_keywords(tmp_db)
        assert "general" in result
        assert "PLM Consultant" in result["general"]
        assert "Python" in result["general"]
        # StepStone URLs
        assert any("stepstone.de/jobs/plm-consultant" in url for url in result["stepstone_urls"])
        # Hays keywords
        assert "plm-consultant" in result["hays_keywords"]
        # Freelancermap URLs
        assert any("freelancermap.de" in url for url in result["freelancermap_urls"])
        # Indeed/Monster queries
        assert "PLM Consultant" in result["indeed_queries"]
        assert "Python" in result["monster_queries"]
