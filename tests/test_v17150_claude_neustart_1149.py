"""#1149 Punkt 10 — die Frage „Claude neu starten?“ in `start_dashboard.py`.

Befund (01.10.2026, im Code gegengelesen, Prozessliste gemessen): die Verknüpfung „PBP Bewerbungs-
Portal“ fragte bei laufendem Claude Desktop „Claude jetzt neu starten? [J/n]“ mit Vorgabe JA und
beendete Claude danach mit `taskkill /F`; die Prüfung auf den Prozess war groß-/kleinschreibungs-
abhängig; neu gestartet wurde nur aus zwei festen Pfaden, sonst schweigend gar nicht.

Jetzt steht die Logik in `services/claude_neustart.py`: Vorgabe NEIN mit Warnung, Prozessprüfung ohne
Rücksicht auf Groß-/Kleinschreibung, dieselben Orte wie der Installer plus die Store-Fassung, und ein
ehrlicher Hinweis, wenn der Start nicht gelingt. Alles Äußere wird hereingereicht; kein Test
berührt ein echtes Claude.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import claude_neustart as cn  # noqa: E402


class Lauf:
    """Ein falsches `subprocess.run`, das alle Aufrufe merkt."""

    def __init__(self, tasklist="Claude.exe   1234 Console  1  200.000 K", pgrep=0, powershell="", ps_fehler=False):
        self.aufrufe = []
        self.tasklist, self.pgrep, self.powershell, self.ps_fehler = tasklist, pgrep, powershell, ps_fehler

    def __call__(self, befehl, **kw):
        self.aufrufe.append(list(befehl))
        name = befehl[0]
        if name == "tasklist":
            return SimpleNamespace(stdout=self.tasklist, returncode=0)
        if name == "pgrep":
            return SimpleNamespace(stdout="", returncode=self.pgrep)
        if name == "powershell":
            if self.ps_fehler:
                raise OSError("PowerShell fehlt")
            return SimpleNamespace(stdout=self.powershell, returncode=0)
        return SimpleNamespace(stdout="", returncode=0)

    def namen(self):
        return [a[0] for a in self.aufrufe]


class Rahmen:
    """Alles, was die Außenwelt berührt, als Aufzeichnung."""

    def __init__(self, antwort="", lauf=None, dateien=(), ordner=(), umgebung=None):
        self.lauf = lauf or Lauf()
        self.ausgaben, self.fragen, self.starts, self.pausen = [], [], [], []
        self._antwort, self._dateien, self._ordner = antwort, set(dateien), set(ordner)
        self.umgebung = umgebung if umgebung is not None else {
            "LOCALAPPDATA": r"C:\Users\Test\AppData\Local", "PROGRAMFILES": r"C:\Program Files",
            "PROGRAMFILES(X86)": r"C:\Program Files (x86)"}

    def frage(self, text):
        self.fragen.append(text)
        return self._antwort

    def ausgabe(self, *teile):
        self.ausgaben.append(" ".join(str(t) for t in teile))

    def start(self, befehl, **kw):
        self.starts.append(list(befehl))

    def aufruf(self, plattform):
        return cn.neustart_anbieten(
            plattform, frage=self.frage, ausgabe=self.ausgabe, run=self.lauf, start=self.start,
            pause=self.pausen.append, umgebung=self.umgebung,
            ist_datei=lambda p: p in self._dateien, ist_ordner=lambda p: p in self._ordner)

    def text(self):
        return "\n".join(self.ausgaben)


EXE = r"C:\Users\Test\AppData\Local\Programs\Claude\Claude.exe"


# ══ Läuft Claude? ═════════════════════════════════════════════════════════════

def test_1149_ohne_laufendes_claude_wird_nichts_gefragt_und_nichts_beendet():
    r = Rahmen(lauf=Lauf(tasklist="INFO: Keine Tasks laufen, die den angegebenen Kriterien entsprechen."))
    assert r.aufruf("win32") == "laeuft_nicht"
    assert r.fragen == [] and "taskkill" not in r.lauf.namen()


@pytest.mark.parametrize("zeile", ["claude.exe  1234 Console", "CLAUDE.EXE  1234 Console", "Claude.exe  1234 Console"])
def test_1149_der_prozessname_zaehlt_ohne_ruecksicht_auf_gross_und_klein(zeile):
    r = Rahmen(lauf=Lauf(tasklist=zeile))
    assert r.aufruf("win32") == "abgelehnt"
    assert len(r.fragen) == 1, "die Frage kam nicht"


def test_1149_unter_linux_passiert_nichts():
    r = Rahmen()
    assert r.aufruf("linux") == "laeuft_nicht"
    assert r.lauf.aufrufe == [] and r.fragen == []


# ══ Die Vorgabe ist NEIN ═══════════════════════════════════════════════════════

@pytest.mark.parametrize("antwort", ["", "n", "N", "nein", "x", "  ", "vielleicht"])
@pytest.mark.parametrize("plattform", ["win32", "darwin"])
def test_1149_ohne_ausdrueckliches_ja_wird_claude_nicht_angefasst(plattform, antwort):
    r = Rahmen(antwort=antwort)
    assert r.aufruf(plattform) == "abgelehnt"
    assert "taskkill" not in r.lauf.namen() and "pkill" not in r.lauf.namen()
    assert r.starts == []
    assert "Claude bleibt offen" in r.text()


def test_1149_die_frage_zeigt_die_vorgabe_und_sagt_was_verloren_geht():
    r = Rahmen(antwort="n")
    r.aufruf("win32")
    assert "[j/N]" in r.fragen[0] and "[J/n]" not in r.fragen[0]
    text = r.text()
    assert "noch nicht abgeschickt" in text and "Antwort wird abgebrochen" in text


# ══ Ein Ja startet neu ═════════════════════════════════════════════════════════

@pytest.mark.parametrize("antwort", ["j", "J", "ja", "Ja", " JA ", "y", "yes"])
def test_1149_ein_ausdrueckliches_ja_beendet_und_startet_claude(antwort):
    r = Rahmen(antwort=antwort, dateien=[EXE])
    assert r.aufruf("win32") == "beendet_und_gestartet"
    assert ["taskkill", "/IM", "Claude.exe", "/F"] in r.lauf.aufrufe
    assert r.starts == [[EXE]]


@pytest.mark.parametrize("teile,erwartet", [
    ((r"C:\Users\Test\AppData\Local", "Programs", "claude-desktop", "Claude.exe"), "claude-desktop"),
    ((r"C:\Users\Test\AppData\Local", "AnthropicClaude", "Claude.exe"), "AnthropicClaude"),
    ((r"C:\Users\Test\AppData\Local", "Programs", "Claude", "Claude.exe"), "Programs"),
    ((r"C:\Users\Test\AppData\Local", "anthropic-claude", "Claude.exe"), "anthropic-claude"),
    ((r"C:\Program Files", "Claude", "Claude.exe"), "Program Files"),
    ((r"C:\Program Files (x86)", "Claude", "Claude.exe"), "x86"),
])
def test_1149_alle_orte_des_installers_werden_gefunden(teile, erwartet):
    import os
    pfad = os.path.join(*teile)
    r = Rahmen(antwort="j", dateien=[pfad])
    assert r.aufruf("win32") == "beendet_und_gestartet"
    assert r.starts == [[pfad]], erwartet


def test_1149_die_store_fassung_wird_ueber_das_paketsystem_gestartet():
    r = Rahmen(antwort="j", lauf=Lauf(powershell="ok"))
    assert r.aufruf("win32") == "beendet_und_gestartet"
    ps = [a for a in r.lauf.aufrufe if a[0] == "powershell"]
    assert len(ps) == 1 and "Get-AppxPackage" in ps[0][-1] and "AppsFolder" in ps[0][-1]
    assert r.starts == []


def test_1149_gelingt_der_start_nicht_sagt_das_fenster_es():
    r = Rahmen(antwort="j", lauf=Lauf(powershell=""))
    assert r.aufruf("win32") == "beendet_ohne_start"
    text = r.text()
    assert "wurde beendet" in text and "selbst wieder" in text


def test_1149_fehlt_powershell_sagt_das_fenster_es_ebenfalls():
    r = Rahmen(antwort="j", lauf=Lauf(ps_fehler=True))
    assert r.aufruf("win32") == "beendet_ohne_start"
    assert "selbst wieder" in r.text()


# ══ macOS ═════════════════════════════════════════════════════════════════════

def test_1149_macos_ohne_laufendes_claude_nichts():
    r = Rahmen(lauf=Lauf(pgrep=1))
    assert r.aufruf("darwin") == "laeuft_nicht"
    assert r.fragen == []


def test_1149_macos_ja_beendet_und_oeffnet_die_app():
    r = Rahmen(antwort="j", ordner=["/Applications/Claude.app"])
    assert r.aufruf("darwin") == "beendet_und_gestartet"
    assert ["pkill", "-x", "Claude"] in r.lauf.aufrufe
    assert r.starts == [["open", "/Applications/Claude.app"]]


def test_1149_macos_ohne_app_im_programmordner_sagt_das_fenster_es():
    r = Rahmen(antwort="j")
    assert r.aufruf("darwin") == "beendet_ohne_start"
    assert "selbst wieder" in r.text()


# ══ Der Starter benutzt den Baustein ═══════════════════════════════════════════

def test_1149_der_starter_hat_die_alte_logik_nicht_mehr():
    quelle = (ROOT / "start_dashboard.py").read_text(encoding="utf-8")
    assert "neustart_anbieten" in quelle
    assert "taskkill" not in quelle and "[J/n]" not in quelle
    assert '"Claude.exe" in result.stdout' not in quelle


def test_1149_die_ausgaben_bleiben_fuer_die_konsole_lesbar():
    """Die Konsole der Verknüpfung kennt die Windows-Codeseiten 1252 und 850: jede Zeile muss darin stehen
    können (Umlaute sind erlaubt, andere Sonderzeichen wie Gedankenstriche nicht)."""
    for antwort in ("j", "n"):
        for plattform in ("win32", "darwin"):
            r = Rahmen(antwort=antwort)
            r.aufruf(plattform)
            for zeile in r.ausgaben:
                for codeseite in ("cp1252", "cp850"):
                    zeile.encode(codeseite)
