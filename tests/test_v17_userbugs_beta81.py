"""Tests fuer User-Test-Findings aus beta.80 (beta.81).

- #659: profil_bearbeiten lehnt Umlaut-Varianten (aendern/aktion) ab
- #661: scoring_vorschau crasht bei distance-Bracket '50km'
- #662: fit_analyse soll ein scharfes Empfehlung-Feld liefern
"""
from __future__ import annotations

import logging


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _register_profil(tmp_db):
    from bewerbungs_assistent.tools.profil import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


# ── #659 — Umlaut-Normalisierung profil_bearbeiten ───────────────────────


def test_profil_bearbeiten_aktion_umlaut_aendern(tmp_db):
    """`aktion='ändern'` darf nicht mit 'Ungueltige Kombination' fallen."""
    tmp_db.create_profile("Test User", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    pos_id = tmp_db.add_position({
        "company": "Firma X", "title": "Architekt",
        "start_date": "2018-01", "end_date": "2018-06",
        "profile_id": pid,
    })

    mcp = _register_profil(tmp_db)
    fn = mcp.tools["profil_bearbeiten"]

    result = fn(
        bereich="position", aktion="ändern",
        element_id=pos_id,
        daten={"end_date": "2018-12"},
    )
    assert "fehler" not in result, f"Unerwarteter Fehler: {result}"
    assert result.get("status") == "aktualisiert"


def test_profil_bearbeiten_aktion_ascii_aendern_weiterhin_ok(tmp_db):
    """Bestehender ASCII-Aufruf bleibt grün."""
    tmp_db.create_profile("Test User", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    pos_id = tmp_db.add_position({
        "company": "Firma X", "title": "Architekt",
        "start_date": "2018-01", "end_date": "2018-06",
        "profile_id": pid,
    })

    mcp = _register_profil(tmp_db)
    fn = mcp.tools["profil_bearbeiten"]

    result = fn(
        bereich="position", aktion="aendern",
        element_id=pos_id,
        daten={"end_date": "2018-12"},
    )
    assert "fehler" not in result
    assert result.get("status") == "aktualisiert"


def test_profil_bearbeiten_bereich_persoenlich_umlaut(tmp_db):
    """`bereich='persönlich'` mit Umlaut auch akzeptiert."""
    tmp_db.create_profile("Test User", "test@example.com")
    mcp = _register_profil(tmp_db)
    fn = mcp.tools["profil_bearbeiten"]

    result = fn(
        bereich="persönlich", aktion="ändern",
        daten={"city": "Bremen"},
    )
    assert "fehler" not in result


def test_profil_bearbeiten_loeschen_umlaut(tmp_db):
    """`aktion='löschen'` mit Umlaut funktioniert."""
    tmp_db.create_profile("Test User", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    skill_id = tmp_db.add_skill({"name": "Python", "profile_id": pid})

    mcp = _register_profil(tmp_db)
    fn = mcp.tools["profil_bearbeiten"]

    result = fn(
        bereich="skill", aktion="löschen",
        element_id=skill_id,
    )
    assert "fehler" not in result


def test_profil_bearbeiten_hinzufuegen_umlaut(tmp_db):
    """`aktion='hinzufügen'` mit Umlaut funktioniert."""
    tmp_db.create_profile("Test User", "test@example.com")
    mcp = _register_profil(tmp_db)
    fn = mcp.tools["profil_bearbeiten"]

    result = fn(
        bereich="skill", aktion="hinzufügen",
        daten={"name": "Rust"},
    )
    assert "fehler" not in result


# ── #661 — scoring_service bracket '50km'-Parse ──────────────────────────


def test_scoring_brackets_mit_einheit_string_parsbar():
    """Bracket-Key 'XXkm' darf nicht mehr crashen — Ziffern werden
    extrahiert, Rest ignoriert."""
    from bewerbungs_assistent.services.scoring_service import apply_scoring_adjustments

    # Mock-DB mit problematischer scoring_config (Bracket-Key '50km'
    # statt '50'). Reproduziert das ValueError-Pattern aus #661.
    class _MockDB:
        def get_scoring_config(self):
            return [
                {"dimension": "entfernung_fest", "sub_key": "50km", "value": -3, "ignore_flag": 0},
                {"dimension": "entfernung_fest", "sub_key": "100",  "value": -5, "ignore_flag": 0},
                {"dimension": "remote", "sub_key": "vollremote",    "value": 0,  "ignore_flag": 0},
                {"dimension": "gehalt", "sub_key": "pro_10_prozent","value": 0,  "ignore_flag": 0},
            ]
        def get_search_criteria(self):
            return {}

    job = {
        "score": 50,
        "remote_level": "vollremote",
        "employment_type": "festanstellung",
        "distance_km": 40,
    }

    # Vorher: ValueError("invalid literal for int(): '50km'")
    result = apply_scoring_adjustments(job, 50, _MockDB())
    assert "final_score" in result


def test_scoring_brackets_bracket_ohne_ziffern_uebersprungen():
    """Brackets ohne jegliche Ziffern werden uebersprungen."""
    from bewerbungs_assistent.services.scoring_service import apply_scoring_adjustments

    class _MockDB2:
        def get_scoring_config(self):
            return [
                {"dimension": "entfernung_fest", "sub_key": "weit",   "value": -3, "ignore_flag": 0},
                {"dimension": "entfernung_fest", "sub_key": "30",     "value": -1, "ignore_flag": 0},
                {"dimension": "remote", "sub_key": "vollremote",      "value": 0,  "ignore_flag": 0},
                {"dimension": "gehalt", "sub_key": "pro_10_prozent",  "value": 0,  "ignore_flag": 0},
            ]
        def get_search_criteria(self):
            return {}

    job = {"score": 50, "remote_level": "vollremote",
           "employment_type": "festanstellung", "distance_km": 20}
    result = apply_scoring_adjustments(job, 50, _MockDB2())
    assert "final_score" in result


# ── #662 — fit_analyse Empfehlung-Verdict ────────────────────────────────


def test_empfehlung_empfohlen_bei_hohem_score():
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    fit_result = {
        "total_score": 80,
        "muss_hits": ["python", "fastapi", "sqlite"],
        "missing_muss": [],
        "risks": [],
        "beschreibung_vorhanden": True,
        "hochschulabschluss_gefordert": False,
    }
    verdict = _build_empfehlung(fit_result, {})
    assert verdict["kategorie"] == "EMPFOHLEN"
    assert "Empfohlen" in verdict["kurz"]


def test_empfehlung_bedingt_bei_mittlerem_score():
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    fit_result = {
        "total_score": 60,
        "muss_hits": ["python"],
        "missing_muss": ["windchill", "teamcenter"],
        "risks": ["2 MUSS-Keywords nicht gefunden"],
        "beschreibung_vorhanden": True,
        "hochschulabschluss_gefordert": False,
    }
    verdict = _build_empfehlung(fit_result, {})
    assert verdict["kategorie"] == "BEDINGT"
    assert "Bedingt" in verdict["kurz"]


def test_empfehlung_nicht_empfohlen_bei_niedrigem_score():
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    fit_result = {
        "total_score": 20,
        "muss_hits": ["python"],
        "missing_muss": ["windchill"],
        "risks": [],
        "beschreibung_vorhanden": True,
        "hochschulabschluss_gefordert": False,
    }
    verdict = _build_empfehlung(fit_result, {})
    assert verdict["kategorie"] == "NICHT_EMPFOHLEN"


def test_empfehlung_ko_bei_fehlender_beschreibung():
    """Fehlende Beschreibung ueberschreibt selbst hohen Score."""
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    fit_result = {
        "total_score": 85,
        "muss_hits": ["python"],
        "missing_muss": [],
        "risks": [],
        "beschreibung_vorhanden": False,
        "hochschulabschluss_gefordert": False,
    }
    verdict = _build_empfehlung(fit_result, {})
    assert verdict["kategorie"] == "NICHT_EMPFOHLEN"
    assert any("Beschreibung" in g for g in verdict["ko_gruende"])


def test_empfehlung_ko_bei_hochschulabschluss_fehlt():
    """Hochschulabschluss gefordert + nicht da -> NICHT_EMPFOHLEN, egal welcher Score."""
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    fit_result = {
        "total_score": 80,
        "muss_hits": ["python"],
        "missing_muss": [],
        "risks": [
            "Hochschulabschluss fehlt — ATS-Risiko",
        ],
        "beschreibung_vorhanden": True,
        "hochschulabschluss_gefordert": True,
    }
    verdict = _build_empfehlung(fit_result, {})
    assert verdict["kategorie"] == "NICHT_EMPFOHLEN"


def test_empfehlung_ko_bei_null_muss_hits():
    """Wenn 0 MUSS-Keywords matchen, aber MUSS-Keywords gefordert sind -> k.o."""
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    fit_result = {
        "total_score": 60,
        "muss_hits": [],
        "missing_muss": ["python", "fastapi", "sqlite"],
        "risks": [],
        "beschreibung_vorhanden": True,
        "hochschulabschluss_gefordert": False,
    }
    verdict = _build_empfehlung(fit_result, {})
    assert verdict["kategorie"] == "NICHT_EMPFOHLEN"
    assert any("MUSS-Keyword" in g for g in verdict["ko_gruende"])


def test_empfehlung_hat_immer_die_pflichtfelder():
    """Format-Vertrag: kategorie + score + begruendung + kurz IMMER vorhanden."""
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    for score in (0, 50, 75, 100):
        fit_result = {
            "total_score": score,
            "muss_hits": ["x"], "missing_muss": [],
            "risks": [], "beschreibung_vorhanden": True,
            "hochschulabschluss_gefordert": False,
        }
        v = _build_empfehlung(fit_result, {})
        assert "kategorie" in v
        assert "score" in v
        assert "begruendung" in v
        assert "kurz" in v
        assert v["kategorie"] in ("EMPFOHLEN", "BEDINGT", "NICHT_EMPFOHLEN")
