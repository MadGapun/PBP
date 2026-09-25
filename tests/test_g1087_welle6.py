"""Welle 6 aus #1087 — Einstellungen, Profil, Rueckweg, Hilfe, Kennzahlen.

* G61 (B2-B4, B6): Kennzahlen mit fester Bedeutung.
"""
import re
from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


FRONTEND = _repo() / "frontend" / "src"


def _lesen(pfad: Path) -> str:
    return pfad.read_text(encoding="utf-8-sig")


# ══ G61 — Kennzahlen mit fester Bedeutung ═══════════════════════════════

def test_g61_keine_zufaellige_perspektive():
    seite = _lesen(FRONTEND / "pages" / "DashboardPage.jsx")
    assert "Math.random" not in seite
    assert "bewerbungenProWoche(applicationTimestamps, wochenAnsicht)" in seite
    assert "WOCHEN_ANSICHTEN.map" in seite
    assert 'label="Bewerbungen pro Woche"' in seite


def test_g61_top_stellen_nach_den_regeln_des_stellen_tabs():
    seite = _lesen(FRONTEND / "pages" / "DashboardPage.jsx")
    assert 'listenParameter(FILTER_STANDARD, "", "", "active")' in seite
    assert "topStellen(data.topJobs || [])" in seite


def test_g61_kein_null_gehalt():
    seite = _lesen(FRONTEND / "pages" / "DashboardPage.jsx")
    assert "gehaltsWert(salaryMetrics.averageMin)" in seite
    assert "gehaltsWert(salaryMetrics.bandMin)" in seite
    assert '"Keine Angabe"' not in seite[seite.index("const salaryMetrics"):seite.index("const lastSearchAt")]


def test_g61_seitenleiste_zaehlt_nur_was_aufmerksamkeit_braucht():
    import sys
    sys.path.insert(0, str(_repo() / "src"))
    from bewerbungs_assistent.services.workspace_service import build_workspace_summary
    daten = build_workspace_summary(
        profile={"name": "Test", "positions": [], "education": [], "skills": [], "documents": []},
        jobs=[{"hash": "a"}, {"hash": "b"}],
        applications=[{"id": "1", "status": "beworben"}, {"id": "2", "status": "beworben"},
                      {"id": "3", "status": "interview"}],
        source_summary={"active": 0, "total": 9, "active_keys": []},
        search_status={"last_search": None, "days_ago": None, "status": "nie"},
        follow_up_summary={"total": 2, "due": 1},
    )
    nav = daten["navigation"]
    # Drei laufende Bewerbungen, eine faellige Nachfassung: die Zahl ist 1.
    assert nav["applications_badge"] == "1"
    assert nav["titel"]["bewerbungen"] == "1 Nachfassung ist fällig"
    assert nav["titel"]["stellen"] == "2 Stellen warten auf deine Entscheidung"
    assert nav["titel"]["einstellungen"] == "Keine Jobbörse ausgewählt"
    assert nav["titel"]["profil"].startswith("Im Profil fehlt noch:")


def test_g61_seitenleiste_zeigt_den_titel():
    leiste = _lesen(FRONTEND / "components" / "Sidebar.jsx")
    assert "title={badgeTitles[tab.id] || undefined}" in leiste
    app = _lesen(FRONTEND / "App.jsx")
    assert "badgeTitles={chrome.workspace?.navigation?.titel || {}}" in app
