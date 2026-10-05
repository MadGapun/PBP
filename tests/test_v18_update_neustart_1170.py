"""#1170 U4 — nach dem Installieren eines Updates sagt PBP, WAS zu tun ist, und widerspricht sich nicht.

Befund (04.10.2026, Update-Demo): Nach der Installation stand „Ab dem nächsten Neustart: v1.8.1“ neben „Aktuell“, die
Seitenleiste sagte „läuft … · installiert …“, und die Anleitung „Beende PBP und Claude Desktop komplett“ ließ offen, was
„PBP beenden“ heißt. PBP läuft als schwarzes Fenster „PBP Bewerbungs-Portal“ (`Dashboard starten.bat`), Claude Desktop hält seinen
PBP-Server so lange am Leben, bis es ganz beendet wird.

Die Regeln stehen in `lib/autoUpdate.js` (Node-Test `autoUpdate.test.mjs`). Hier: dass die Oberfläche sie auch BENUTZT
(ein Schutz zählt erst, wenn er aufgerufen wird, DoD 8c) und dass die Anleitung zum Installer passt.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src"


def _lesen(*teile):
    return (SRC.joinpath(*teile)).read_text(encoding="utf-8-sig")


def test_1170_die_updates_seite_benutzt_die_gemeinsamen_regeln():
    seite = _lesen("components", "UpdatesTab.jsx")
    assert "zeigeAktuell(au)" in seite, "„Aktuell“ darf nur erscheinen, wenn kein Neustart aussteht"
    assert "NEUSTART_SCHRITTE" in seite and "data-updates-neustart" in seite
    assert "Beende PBP und Claude Desktop komplett" not in seite, "die unklare Anleitung steht nur noch an einer Stelle: im Modul"


def test_1170_hinweis_und_einstellung_sagen_dasselbe():
    modul = _lesen("lib", "autoUpdate.js")
    assert modul.count("NEUSTART_SCHRITTE") >= 2 and "neustartText()" in modul
    assert "Beende PBP und Claude Desktop komplett (Rechtsklick" not in modul


def test_1170_die_anleitung_nennt_das_fenster_das_der_installer_anlegt():
    """Der Name im Text ist der Name der Verknüpfung und des Fensters, die der Installer anlegt."""
    modul = _lesen("lib", "autoUpdate.js")
    installer = (ROOT / "INSTALLIEREN.bat").read_text(encoding="utf-8", errors="replace")
    starter = (ROOT / "Dashboard starten.bat").read_text(encoding="utf-8", errors="replace")
    assert "PBP Bewerbungs-Portal" in modul
    assert "PBP Bewerbungs-Portal.lnk" in installer, "die Verknüpfung heißt so"
    assert "title PBP Bewerbungs-Portal" in starter, "das Fenster heißt so"
    assert "Zum Beenden: Dieses Fenster schliessen" in starter, "und schließen beendet PBP"


def test_1170_die_seitenleiste_zeigt_den_neustart_und_nicht_zwei_versionen():
    modul = _lesen("lib", "autoUpdate.js")
    assert "Neustart nötig für v${au.aktuell}" in modul
    assert "läuft v${au.laufend} · installiert" not in modul
