"""Tests fuer v1.7.19 — #926: Fallback-URLs muessen URLs sein.

`freelancermap.SEARCH_URLS` enthielt Slug-FRAGMENTE statt URLs
("Software-Engineer" statt "https://.../projekte/software-engineer").
Der Adapter rief damit `client.get("Software-Engineer")` auf — das kann
nie funktionieren. Greift nur ohne konfigurierte Suchkriterien, also
genau bei einem frischen Profil: die Quelle lieferte zwangslaeufig 0
Treffer und lief nach fuenf stillen Laeufen in die Auto-Deaktivierung.
Danach lief sie nie wieder (#906-Zirkel) — im Bestand stand sie seit
Mai 2026 als tot, obwohl der Adapter intakt war.
"""
import re

import pytest


def _ist_absolute_url(wert: str) -> bool:
    return bool(re.match(r"^https?://[^\s]+$", str(wert or "")))


def test_926_freelancermap_fallback_sind_echte_urls():
    from bewerbungs_assistent.job_scraper.freelancermap import SEARCH_URLS
    assert SEARCH_URLS, "Fallback darf nicht leer sein"
    for u in SEARCH_URLS:
        assert _ist_absolute_url(u), (
            f"'{u}' ist keine URL — httpx.get() darauf schlaegt fehl und die "
            "Quelle laeuft still in die Auto-Deaktivierung")


def test_926_freelancermap_fallback_nutzt_slug_seiten():
    """Die Slug-Seiten liefern thematisch; der Query-Parameter wird
    von der Plattform ignoriert (live geprueft 18.08.2026)."""
    from bewerbungs_assistent.job_scraper.freelancermap import SEARCH_URLS
    assert all("/projekte/" in u for u in SEARCH_URLS), SEARCH_URLS
    assert not any("?" in u for u in SEARCH_URLS), \
        "Query-Parameter wirken bei dieser Plattform nicht"


@pytest.mark.parametrize("modul,konstante", [
    ("freelancermap", "SEARCH_URLS"),
])
def test_926_kein_adapter_hat_fragment_fallbacks(modul, konstante):
    """Verallgemeinert: Fallback-Listen, die an httpx.get() gehen,
    muessen absolute URLs enthalten."""
    import importlib
    mod = importlib.import_module(f"bewerbungs_assistent.job_scraper.{modul}")
    werte = getattr(mod, konstante, [])
    assert all(_ist_absolute_url(w) for w in werte), werte
