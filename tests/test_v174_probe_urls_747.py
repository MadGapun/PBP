"""Tests fuer v1.7.4 — #747 (B13): Probe-URLs fuer ingenieur_de + ferchau.

Nach der URL-Migration #653 (beta.77) waren beide Quellen wieder produktiv,
hatten aber keine Probe-Definition — quellen_health_check() lieferte nur
'no_probe_defined', genau fuer die zwei Quellen mit Migrations-Historie.
Kein Live-HTTP in Tests (User-Vorgabe) — nur Definitions-Konsistenz.
"""
from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
from bewerbungs_assistent.job_scraper.health import _PROBES, get_probable_sources


def test_ingenieur_de_hat_probe():
    method, url, content_type, body = _PROBES["ingenieur_de"]
    assert method == "GET"
    # Probe trifft denselben Endpunkt wie der Adapter (jobs.ingenieur.de/suche)
    assert url.startswith("https://jobs.ingenieur.de/suche")
    assert content_type == "html"
    assert body is None


def test_ferchau_hat_probe():
    method, url, content_type, body = _PROBES["ferchau"]
    assert method == "GET"
    # Probe trifft die neue Karriere-Plattform aus #653
    assert url.startswith("https://touch.ferchau.com/de/de")
    assert content_type == "html"
    assert body is None


def test_alle_probe_keys_existieren_in_source_registry():
    """Eine Probe fuer eine Quelle, die es nicht (mehr) gibt, waere toter
    Code — und check_source() wuerde sie nie erreichen (unknown_source
    greift vorher)."""
    unbekannt = [k for k in get_probable_sources() if k not in SOURCE_REGISTRY]
    assert not unbekannt, f"Probes ohne SOURCE_REGISTRY-Eintrag: {unbekannt}"


def test_defekte_quellen_haben_keine_probe():
    """Quellen mit defekt=True werden von jobsuche_starten uebersprungen —
    eine Probe wuerde faelschlich 'gruen' melden (SPA liefert HTTP 200,
    aber keine Stellen). Bewusste Design-Entscheidung aus #624."""
    defekte_mit_probe = [
        k for k in get_probable_sources()
        if SOURCE_REGISTRY.get(k, {}).get("defekt")
    ]
    assert not defekte_mit_probe, (
        f"Defekte Quellen mit Probe (wuerden falsch-gruen melden): "
        f"{defekte_mit_probe}"
    )
