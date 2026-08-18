"""Tests fuer v1.7.19 — #927: Quellen-Zustand ehrlich abbilden.

Drei Kategorien, die nicht vermischt werden duerfen:

* `defekt`      — der WEG funktioniert nicht (SPA, Bot-Block, Host weg).
                  Die Quelle wird uebersprungen und im Frontend
                  ausgegraut; eine Probe waere irrefuehrend, weil HTTP
                  200 nichts ueber gelieferte Stellen aussagt (#808).
* `deprecated`  — bewusst aufgegeben (robots.txt, Anbieter eingestellt).
* auto-deaktiviert — die Automatik hat abgeschaltet, der Grund ist
                  unklar. Hier ist die Probe wertvoll: genau so wurden
                  am 18.08. zwei totgeglaubte Quellen wiedergefunden
                  (#925/#926).
"""
import pytest

from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
from bewerbungs_assistent.job_scraper.health import get_probable_sources


def test_927_defekte_quellen_haben_immer_einen_grund():
    for key, meta in SOURCE_REGISTRY.items():
        if meta.get("defekt"):
            grund = meta.get("defekt_grund") or ""
            assert len(grund) > 25, (
                f"{key}: 'defekt' ohne belastbare Begruendung — der Nutzer "
                f"muss sehen, WARUM eine Quelle ausgegraut ist ({grund!r})")


def test_927_defekte_quellen_werden_nicht_geprobt():
    """Sonst meldet die Probe 'gruen' fuer eine Quelle, die nichts liefert."""
    kollision = [k for k in get_probable_sources()
                 if SOURCE_REGISTRY.get(k, {}).get("defekt")]
    assert not kollision, kollision


def test_927_defekt_und_deprecated_sind_getrennt():
    """Zwei verschiedene Aussagen, zwei verschiedene Felder (#906)."""
    beides = [k for k, m in SOURCE_REGISTRY.items()
              if m.get("defekt") and m.get("deprecated")]
    assert not beides, (
        f"{beides}: 'defekt' (Weg kaputt) und 'deprecated' (bewusst "
        "aufgegeben) sind verschiedene Dinge — eine Quelle sollte nur "
        "eines von beidem tragen")


@pytest.mark.parametrize("key", [
    "workday_dax", "workable", "praktikum_de", "meinestadt", "freelance_de",
])
def test_927_live_geprueft_als_defekt_markiert(key):
    """Am 18.08.2026 live geprueft: kein automatischer Weg vorhanden."""
    meta = SOURCE_REGISTRY[key]
    assert meta.get("defekt") is True, f"{key} sollte ausgegraut sein"
    assert "2026" in (meta.get("defekt_grund") or ""), \
        "der Grund sollte das Pruefdatum nennen"


@pytest.mark.parametrize("key", ["ferchau", "freelancermap", "ingenieur_de"])
def test_927_wiederhergestellte_quellen_sind_nutzbar(key):
    """Die drei in v1.7.19 reparierten Quellen duerfen nicht blockiert sein."""
    meta = SOURCE_REGISTRY[key]
    assert not meta.get("defekt"), f"{key} wurde repariert (#925/#926/#927)"
    assert not meta.get("deprecated"), f"{key} wurde repariert"
