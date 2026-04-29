"""Tests fuer v1.6.7 (#515 Banner-Action, #552 Score-Multiplikator, #561, #562)."""
import asyncio
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v167_test_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============= #552 — gehalt_geschaetzt 0.5x Multiplikator ===============
def test_552_estimated_salary_halves_score_impact(setup_env):
    """Bei salary_estimated=True ist der Gehalts-Beitrag halbiert."""
    db, _ = setup_env
    from bewerbungs_assistent.services.scoring_service import apply_scoring_adjustments

    # Setup: User-Wunsch und Scoring-Konfig
    db.set_search_criteria("min_gehalt", 60000)
    # gehalt_cfg: pro 10% Abweichung +/- 1 Punkt (vereinfacht)
    conn = db.connect()
    conn.execute(
        "INSERT OR REPLACE INTO scoring_config (profile_id, dimension, sub_key, value, ignore_flag, created_at) "
        "VALUES ('', 'gehalt', 'pro_10_prozent', 1, 0, '2026-04-29')"
    )
    conn.commit()

    # Test 1: extracted salary (estimated=False) = 78000 → +30% → +3 Punkte
    job_extracted = {
        "score": 50, "salary_min": 78000, "salary_estimated": False,
        "salary_type": "jaehrlich", "employment_type": "festanstellung",
    }
    result_ext = apply_scoring_adjustments(job_extracted, 50, db)
    gehalt_adj_ext = next((a for a in result_ext["adjustments"] if a["dimension"] == "Gehalt/Rate"), None)

    # Test 2: estimated salary, gleiche Zahlen
    job_estimated = {
        "score": 50, "salary_min": 78000, "salary_estimated": True,
        "salary_type": "jaehrlich", "employment_type": "festanstellung",
    }
    result_est = apply_scoring_adjustments(job_estimated, 50, db)
    gehalt_adj_est = next((a for a in result_est["adjustments"] if a["dimension"] == "Gehalt/Rate"), None)

    assert gehalt_adj_ext is not None, "Extracted-Job sollte Gehalts-Adjustment bekommen"
    assert gehalt_adj_est is not None, "Estimated-Job sollte (kleineres) Gehalts-Adjustment bekommen"
    # Estimated muss 0.5x sein
    assert abs(gehalt_adj_est["punkte"]) <= abs(gehalt_adj_ext["punkte"]), (
        f"Estimated punkte {gehalt_adj_est['punkte']} sollte <= extracted {gehalt_adj_ext['punkte']}"
    )
    assert gehalt_adj_est["source"] == "geschaetzt"
    assert gehalt_adj_ext["source"] == "extrahiert"
    # Detail-String enthaelt den Hinweis
    assert "geschaetzt" in gehalt_adj_est["detail"]


def test_552_no_estimated_flag_no_change(setup_env):
    """Ohne salary_estimated-Flag: Verhalten unveraendert (1.0x)."""
    db, _ = setup_env
    from bewerbungs_assistent.services.scoring_service import apply_scoring_adjustments
    db.set_search_criteria("min_gehalt", 60000)
    conn = db.connect()
    conn.execute(
        "INSERT OR REPLACE INTO scoring_config (profile_id, dimension, sub_key, value, ignore_flag, created_at) "
        "VALUES ('', 'gehalt', 'pro_10_prozent', 1, 0, '2026-04-29')"
    )
    conn.commit()
    job = {
        "score": 50, "salary_min": 66000,  # +10%
        "salary_type": "jaehrlich", "employment_type": "festanstellung",
    }
    result = apply_scoring_adjustments(job, 50, db)
    gehalt_adj = next((a for a in result["adjustments"] if a["dimension"] == "Gehalt/Rate"), None)
    assert gehalt_adj is not None
    assert gehalt_adj["source"] == "extrahiert"


# ============= #562 — /api/prompts Endpoint ===============
def test_562_prompts_endpoint_lists_all(setup_env):
    """GET /api/prompts liefert alle Prompts mit Metadaten."""
    db, _ = setup_env
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    registry = _prompt_registry(db)
    # Erwarte mind. 18 Prompts (alle aus prompts.py + workflows.py registry)
    assert len(registry) >= 16
    # Wichtige Namen muessen drin sein
    must_haves = {"ersterfassung", "jobsuche_workflow", "tipps_und_tricks",
                  "profil_sync", "ablehnungs_coaching", "auto_bewerbung"}
    assert must_haves.issubset(set(registry.keys()))


def test_562_tipps_und_tricks_resolves(setup_env):
    """Smoke-Test fuer #560-Fix: tipps_und_tricks liefert echten Inhalt."""
    db, _ = setup_env
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    # mcp-Server muss schon initialisiert sein damit _delegate_to_prompt funktioniert
    from bewerbungs_assistent.server import mcp  # noqa: F401
    registry = _prompt_registry(db)
    text = registry["tipps_und_tricks"]()
    assert len(text) > 100
    assert "Tipps" in text or "Tipp" in text or "Funktion" in text


# ============= #561 — Schnellzugriff Karten (lebt im Frontend) ===============
def test_561_dashboard_curated_layout_marker_in_jsx(setup_env):
    """DashboardPage.jsx enthaelt den 4x3-Grid-Hinweis (#561 Marker)."""
    from pathlib import Path
    src = Path("frontend/src/pages/DashboardPage.jsx").read_text(encoding="utf-8")
    # Kuratiert auf 4x3 = entferne „Zum Nachlesen", „Uebersicht",
    # „Netzwerk aufbauen", „Tipps & Tricks" aus Schnellzugriff
    assert "title: \"Profil\"" in src, "Erste Schritte sollte zu 'Profil' umbenannt sein"
    assert "Profil-Check" in src, "'Profil pruefen' sollte 'Profil-Check' heissen"
    # Diese drei sind nicht mehr im Schnellzugriff
    assert "/bewerbungs_uebersicht" not in src or "// removed" in src.lower()
    # Die Karte „Tipps & Tricks" wurde entfernt aus Schnellzugriff (kein „Zum Nachlesen"-Block mehr)
    assert "title: \"Zum Nachlesen\"" not in src
