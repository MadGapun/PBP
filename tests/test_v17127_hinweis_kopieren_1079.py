"""Tests fuer v1.7.127 — #1079: der Satz im Onboarding-Hinweis ist kopierbar.

Der Hinweis nannte den Satz, den man in Claude eingeben soll, liess ihn
aber als Text stehen. Ueberall sonst in PBP geht ein Befehl per Klick in
die Zwischenablage — ueber `copyPrompt` aus dem App-Kontext.
"""
from pathlib import Path


def _quelle() -> str:
    pfad = (Path(__file__).resolve().parents[1] / "frontend" / "src"
            / "components" / "OnboardingHintBanner.jsx")
    return pfad.read_text(encoding="utf-8")


def _block_um(text: str, marke: str) -> str:
    i = text.index(marke)
    anfang = text.rfind("<button", 0, i)
    ende = text.index("</button>", i)
    return text[anfang:ende]


def test_1079_der_satz_ist_ein_knopf_und_kopiert_cta_label():
    block = _block_um(_quelle(), "Sag Claude")
    assert 'type="button"' in block
    assert "copyPrompt(h.cta_label)" in block
    assert "ClipboardCopy" in block


def test_1079_titel_sagt_was_passiert():
    block = _block_um(_quelle(), "Sag Claude")
    assert "Kopiert den Befehl" in block
    assert "Einfach in Claude Desktop tippen" not in _quelle()


def test_1079_kopieren_blendet_den_hinweis_nicht_aus():
    block = _block_um(_quelle(), "Sag Claude")
    assert "hideForSession" not in block
    assert "dismissPermanent" not in block


def test_1079_copy_prompt_kommt_aus_dem_app_kontext():
    quelle = _quelle()
    assert 'import { useApp } from "@/app-context"' in quelle
    assert "const { copyPrompt } = useApp()" in quelle
