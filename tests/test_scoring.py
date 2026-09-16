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

def _rahmenwert(job, criteria):
    """Der Rahmenwert, den `calculate_score` an die Stelle schreibt.

    v1.7.117 (#1052): Entfernung, Remote und Gehalt gehen nicht mehr in
    den Score ein — er ist der FACHWERT. Die Regler wirken unveraendert,
    nur eben auf die zweite Zahl. Wer hier wieder den Score prueft,
    misst die Trennung weg.
    """
    kopie = dict(job)
    calculate_score(kopie, criteria)
    return kopie.get("_rahmenscore")


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
        # v1.7.117 (#1052): PLUS zaehlt FACHLICH — es sagt etwas ueber
        # die Anzeige, nicht ueber die Lebensumstaende. Der Deckel aus
        # #942 gilt hier weiter, denn PLUS steht in DERSELBEN Zahl wie
        # die Pflichttreffer und konkurriert mit ihnen; entfallen ist er
        # nur gegen die Entfernung, die jetzt daneben steht.
        # MUSS=2 (Fachscore), PLUS=2 roh -> gedeckelt auf 50% von 2 = 1.
        assert score == 3

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
        # Der FACHWERT ist identisch — das Arbeitsmodell sagt nichts
        # ueber die fachliche Passung. Der Unterschied steht im Rahmen.
        assert calculate_score(dict(job_remote), criteria) == \
            calculate_score(dict(job_onsite), criteria)
        assert _rahmenwert(job_remote, criteria) > \
            _rahmenwert(job_onsite, criteria)

    def test_hybrid_bonus(self):
        """Hybrid jobs also get the remote bonus."""
        job = _job(title="PLM Engineer", remote="hybrid")
        criteria = _criteria(muss=["PLM"])
        score = calculate_score(dict(job), criteria)
        # v1.7.117 (#1052): der Score ist der Fachwert und kennt das
        # Arbeitsmodell nicht mehr. Der Bonus steht im Rahmenwert.
        assert score == 2
        assert _rahmenwert(job, criteria) == 2

    def test_distance_bonus(self):
        """Jobs within 80km get bonus points."""
        job_near = _job(title="PLM Admin", distance=30)
        job_far = _job(title="PLM Admin", distance=500)
        criteria = _criteria(muss=["PLM"])
        # Gleiche Anzeige, gleicher Fachwert — 470 km Unterschied
        # aendern an der fachlichen Passung nichts.
        assert calculate_score(dict(job_near), criteria) == \
            calculate_score(dict(job_far), criteria)
        assert _rahmenwert(job_near, criteria) > \
            _rahmenwert(job_far, criteria)

    def test_distance_malus(self):
        """Jobs over 200km get a penalty."""
        job = _job(title="PLM Berater", distance=300)
        criteria = _criteria(muss=["PLM"])
        score = calculate_score(dict(job), criteria)
        # DER Fall aus #1052, in klein: bis v1.7.116 zog der Fernmalus
        # den Fachwert unter null und die Kappung machte 0 daraus — eine
        # fachlich passende Stelle war von einer fachfremden nicht mehr
        # zu unterscheiden. Der Fachwert bleibt jetzt stehen, der Malus
        # steht im Rahmen.
        assert score == 2
        assert _rahmenwert(job, criteria) == -3

    def test_custom_weights(self):
        """Custom weights override defaults."""
        job = _job(title="PLM Consultant", description="Python")
        criteria = _criteria(
            muss=["PLM"],
            plus=["Python"],
            gewichtung={"muss": 5, "plus": 3, "remote": 1, "naehe": 1, "fern_malus": 1},
        )
        score = calculate_score(job, criteria)
        # MUSS=5 (Fachscore), PLUS=3 -> Deckel 2.5. Seit v1.7.117
        # (#1052) sind beide fachlich; der Deckel gilt zwischen ihnen
        # weiter, gegen die Entfernung nicht mehr.
        assert score == 7.5

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
        # Der Fachwert ist derselbe — die Anstellungsform sagt nichts
        # ueber die fachliche Passung (#1052).
        assert calculate_score(dict(job_freelance), criteria) == 2
        assert calculate_score(dict(job_fest), criteria) == 2
        # Der Unterschied steht im Rahmen, und das ist der Punkt aus
        # #112: fuer ein Projekt sind 300 km kein Malus.
        assert _rahmenwert(job_freelance, criteria) == 0
        assert _rahmenwert(job_fest, criteria) == -3

    def test_freelance_moderate_distance_no_penalty(self):
        """Freelance 150km should have no slight penalty either (#112)."""
        job_freelance = _job(title="PLM Berater", distance=150,
                             employment_type="freelance")
        job_fest = _job(title="PLM Berater", distance=150,
                        employment_type="festanstellung")
        criteria = _criteria(muss=["PLM"])
        assert calculate_score(dict(job_freelance), criteria) == \
            calculate_score(dict(job_fest), criteria)
        assert _rahmenwert(job_freelance, criteria) > \
            _rahmenwert(job_fest, criteria)


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
        # Freelancermap URLs (#500: jetzt slug-basiert /projekte/<slug>)
        assert any("freelancermap.de/projekte/" in url for url in result["freelancermap_urls"])
        # Indeed/Monster queries
        assert "PLM Consultant" in result["indeed_queries"]
        assert "Python" in result["monster_queries"]

    def test_keywords_muss_durchgereicht(self, tmp_db):
        """#500: keywords_muss bleibt als separater Key fuer linkedin/xing."""
        tmp_db.set_search_criteria("keywords_muss", ["PLM"])
        tmp_db.set_search_criteria("keywords_plus", ["Python"])
        result = build_search_keywords(tmp_db)
        assert result.get("keywords_muss") == ["PLM"]
        assert result.get("keywords_plus") == ["Python"]

    def test_greenhouse_companies_durchgereicht(self, tmp_db):
        """#500: greenhouse_companies aus criteria erreicht den Adapter."""
        tmp_db.set_search_criteria("keywords_muss", ["Python"])
        tmp_db.set_search_criteria("greenhouse_companies", ["mein-arbeitgeber", "noch-einer"])
        result = build_search_keywords(tmp_db)
        assert result.get("greenhouse_companies") == ["mein-arbeitgeber", "noch-einer"]

    def test_greenhouse_companies_default_empty(self, tmp_db):
        """Ohne explizite Konfiguration ist greenhouse_companies leer (Adapter nutzt DEFAULT_COMPANIES)."""
        tmp_db.set_search_criteria("keywords_muss", ["Python"])
        result = build_search_keywords(tmp_db)
        assert result.get("greenhouse_companies") == []


# === Hochschulabschluss-Erkennung (#305) ===

class TestDegreeDetectionEntfernt:
    """Die Hochschulabschluss-Pruefung ist ersatzlos entfernt (#972).

    Drei Runden Nachbesserung (#698 Malus, #918 Bewerberstatistiken,
    #955 beschreibende Wendungen) drehten sich alle um die ANZEIGE. Die
    Profilseite wurde nie modelliert — sie kannte nur "Hochschulabschluss
    ja/nein". Damit war der Satz "Dein Profil enthält keinen" schlicht
    falsch: ein Staatlich gepruefter Techniker liegt auf DQR-Niveau 6,
    also demselben wie ein Bachelor.

    Diese Klasse prueste frueher die Erkennung. Sie prueft jetzt, dass es
    sie nicht mehr gibt — sonst kommt sie beim naechsten "kleinen
    Nachbessern" still zurueck.
    """

    def test_972_erkennung_ist_weg(self):
        import bewerbungs_assistent.job_scraper as js
        assert not hasattr(js, "_detect_degree_required")
        assert not hasattr(js, "_profile_has_degree")

    def test_972_fit_analyse_urteilt_nicht_mehr_ueber_abschluesse(self):
        job = _job(
            title="PLM Consultant",
            description="Abgeschlossenes Studium im Bereich Ingenieurwesen. "
                        "Erfahrung mit PLM/PDM-Systemen wie Teamcenter."
        )
        criteria = _criteria(muss=["PLM"])
        criteria["_profile_education"] = []
        result = fit_analyse(job, criteria)
        assert "hochschulabschluss_gefordert" not in result
        assert not any("HOCHSCHULABSCHLUSS" in r for r in result["risks"])
        assert "Hochschulabschluss fehlt" not in result["factors"]

    def test_972_ein_techniker_wird_nicht_mehr_abgewertet(self):
        """Der ausloesende Fall: sieben Ausbildungseintraege im Profil,
        darunter ein Staatlich gepruefter Techniker — und PBP behauptete
        "Dein Profil enthält keinen"."""
        job = _job(
            title="Konstrukteur",
            description="Abgeschlossenes Studium oder vergleichbare "
                        "Qualifikation. PLM-Kenntnisse noetig."
        )
        criteria = _criteria(muss=["PLM"])
        criteria["_profile_education"] = [
            {"degree": "Staatlich gepruefter Techniker",
             "field_of_study": "Maschinen- und Anlagenbau",
             "institution": "Technikerschule"}
        ]
        result = fit_analyse(job, criteria)
        assert "Hochschulabschluss fehlt" not in result["factors"]

    def test_972_waehlbarer_ablehnungsgrund_bleibt(self):
        """Ob ein fehlender Abschluss ein Ausschluss ist, entscheidet der
        Mensch je Stelle — nicht ein Textvergleich."""
        from bewerbungs_assistent.services.ablehnungsgruende import (
            STANDARD_GRUENDE)
        assert "kein_hochschulabschluss" in STANDARD_GRUENDE
