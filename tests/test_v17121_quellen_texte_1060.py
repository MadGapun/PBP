"""#1060 — dieselbe Auskunft, dreimal verschieden formuliert.

Nachtrag zu #1059: die Badges waren einheitlich, die Texte daneben nicht.
Sechs Quellen mit `zugriffsart: browser_login` sagten in drei Formulierungen
dasselbe, "Chrome" stand in 13 Eintraegen, und bei LinkedIn und Google
stand nirgends, dass dasselbe Portal auch automatisch abgefragt wird.

Jetzt wird der gemeinsame Teil aus `zugriffsart` abgeleitet; von Hand
steht nur das Quellenspezifische.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.job_scraper import (  # noqa: E402
    BROWSER_HINWEIS, BROWSER_METHODE, SOURCE_REGISTRY, zugriffsart_von)

BROWSER = {k for k, v in SOURCE_REGISTRY.items() if v.get("zugriffsart") == "browser_login"}


def test_die_browser_quellen_sind_dieselben_wie_vorher():
    """Die Umstellung aendert Texte, nicht die Einteilung."""
    assert BROWSER == {"stepstone", "indeed", "monster", "linkedin", "xing", "google_jobs"}
    for name in SOURCE_REGISTRY:
        erwartet = "browser_login" if name in BROWSER else "api"
        assert zugriffsart_von(name) == erwartet, name


def test_jede_browser_quelle_sagt_dasselbe_mit_denselben_worten():
    for name in BROWSER:
        q = SOURCE_REGISTRY[name]
        assert q["methode"].startswith(BROWSER_METHODE), (name, q["methode"])
        assert q["warnung"].startswith(BROWSER_HINWEIS), (name, q["warnung"])


def test_der_gemeinsame_satz_steht_nicht_von_hand_im_eintrag():
    """Sonst laeuft er beim naechsten Mal wieder auseinander — genau das
    ist bei #1059 passiert."""
    quelle = (ROOT / "src/bewerbungs_assistent/job_scraper/__init__.py").read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    registry = next(n.value for n in baum.body if isinstance(n, ast.Assign)
                    and getattr(n.targets[0], "id", "") == "SOURCE_REGISTRY")
    for schluessel, eintrag in zip(registry.keys, registry.values):
        felder = {k.value: v for k, v in zip(eintrag.keys, eintrag.values)}
        zugriff = getattr(felder.get("zugriffsart"), "value", None)
        if zugriff == "browser_login":
            assert "warnung" not in felder and "methode" not in felder, schluessel.value


def test_chrome_steht_nur_noch_in_der_browserliste():
    """Gemeint ist der Browser, nicht das Produkt. Einzige Ausnahme: die
    Aufzaehlung der Browser, in denen die Erweiterung laeuft."""
    fund = []
    for name, q in SOURCE_REGISTRY.items():
        for feld, wert in q.items():
            if isinstance(wert, str) and re.search("chrome", wert.replace(BROWSER_HINWEIS, ""), re.I):
                fund.append((name, feld))
    assert not fund, fund


def test_dasselbe_portal_zweimal_steht_auf_beiden_karten():
    paare = {("indeed", "jobspy_indeed"), ("linkedin", "jobspy_linkedin"),
             ("google_jobs", "jobspy_google")}
    for browser, auto in paare:
        assert SOURCE_REGISTRY[auto]["name"] in SOURCE_REGISTRY[browser]["warnung"], browser
        assert SOURCE_REGISTRY[browser]["name"] in SOURCE_REGISTRY[auto]["warnung"], auto


def test_quellenspezifisches_bleibt_erhalten():
    assert "Layout" in SOURCE_REGISTRY["monster"]["warnung"]
    assert "Voyager" in SOURCE_REGISTRY["linkedin"]["methode"]
    assert "rate-limitet" in SOURCE_REGISTRY["jobspy_linkedin"]["warnung"]


def test_die_karte_nennt_die_erweiterung_nicht_chrome():
    for rel in ("frontend/src/components/SourceSelectionList.jsx",
                "frontend/src/pages/SettingsPage.jsx"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "Chrome-Extension" not in text, rel
        assert "Claude in Chrome (Browser-Extension)" not in text, rel


def test_rueckfall_erkennt_den_neuen_wortlaut(monkeypatch):
    """Ein kuenftiger Eintrag ohne `zugriffsart` wird weiter als
    Browser-Quelle erkannt — die Ableitung las bisher nur den alten Text."""
    from bewerbungs_assistent.services.search_service import _zugriffsart
    eintrag = {"methode": BROWSER_METHODE, "login_erforderlich": True}
    monkeypatch.setitem(SOURCE_REGISTRY, "k1060_neu", eintrag)
    assert zugriffsart_von("k1060_neu") == "browser_login"
    assert _zugriffsart("k1060_neu", eintrag) == "browser_login"
