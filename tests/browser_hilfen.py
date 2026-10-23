"""Gemeinsame Handgriffe der Browser-Tests (#1170 U17).

Die Einstellungen haben seit 1.8 EINE Navigation: die Reiter der Seite (Grundlagen vorn, Erweitert dahinter). Die Seitenleiste
fuehrt keine Unterpunkte mehr. Ein Test, der einen Reiter braucht, geht deshalb ueber die Leiste - und klappt „Erweitert“ auf,
wenn der Reiter dahinter liegt, genau wie ein Mensch.
"""
from __future__ import annotations


def einstellungen_reiter(page, name: str, timeout: int = 15000) -> None:
    """Waehlt einen Reiter der Einstellungen (die Seite ist schon offen)."""
    leiste = page.locator("[data-settings-reiter]")
    leiste.wait_for(timeout=timeout)
    knopf = leiste.get_by_role("button", name=name, exact=True)
    if knopf.count() == 0:
        schalter = leiste.locator("[data-erweitert-schalter]")
        if schalter.get_attribute("aria-expanded") != "true":
            schalter.click()
        knopf = page.locator("[data-erweitert-reiter]").get_by_role("button", name=name, exact=True)
        knopf.wait_for(timeout=timeout)
    knopf.first.click()
