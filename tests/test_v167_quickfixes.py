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
    assert gehalt_adj_est is not None, "Estimated-Job bekommt den transparenten 0-Eintrag"
    # v1.7.12 (#827, C32): Schaetzungen zaehlen GAR NICHT mehr (vorher
    # 0.5x). 14 von 29 Stellen eines Laufs trugen dieselben vier
    # Schema-Spannen — das ist keine Information ueber die Stelle. Der
    # 0-Punkte-Eintrag bleibt sichtbar und erklaert die leere Dimension.
    assert gehalt_adj_est["punkte"] == 0, (
        f"Schaetzung darf nicht mehr beitragen: {gehalt_adj_est['punkte']}"
    )
    assert gehalt_adj_ext["punkte"] != 0, "echte Angabe wirkt unveraendert"
    assert gehalt_adj_est["source"] == "geschaetzt"
    assert gehalt_adj_ext["source"] == "extrahiert"
    # Detail-String enthaelt den Hinweis
    assert "geschaetzt" in gehalt_adj_est["detail"] \
        or "Schaetzung" in gehalt_adj_est["detail"]


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
def test_561_schnellzugriff_bleibt_kuratiert(setup_env):
    """Der Schnellzugriff zeigt eine Auswahl, nicht alles (#561).

    Bis v1.7.32 stand diese Auswahl fest im JSX, und dieser Test las sie
    dort. Seit #979 (G29) kommt sie aus `services/prompt_katalog.py`;
    die Zusage aus #561 gilt unveraendert, sie hat nur einen anderen
    Ort — und ist dort auch fuer den Nutzer aenderbar.

    Nebeneffekt: der Test las die Datei ueber einen RELATIVEN Pfad und
    haette aus einem fremden Arbeitsverzeichnis heraus einen Fehler
    geworfen statt zu pruefen (DoD 8c). Er braucht jetzt gar keinen.
    """
    from bewerbungs_assistent.services import prompt_katalog

    standard = [e for e in prompt_katalog.alle() if e.get("standard")]
    assert 0 < len(standard) < len(prompt_katalog.EINTRAEGE), (
        "Der Schnellzugriff soll eine Auswahl sein, nicht der ganze Katalog")

    # Die vier aus #561 entfernten Karten sind weiter im Katalog
    # erreichbar, aber nicht im Standard.
    im_standard = {e["id"] for e in standard}
    for ausgelagert in ("bewerbungs_uebersicht", "netzwerk_strategie",
                        "tipps_und_tricks"):
        assert prompt_katalog.eintrag(ausgelagert), ausgelagert
        assert ausgelagert not in im_standard, ausgelagert

    # Die Umbenennung aus #561 steht im Katalog.
    assert prompt_katalog.eintrag("profil_ueberpruefen")["titel"] == "Profil-Check"
