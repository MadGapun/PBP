"""#1149 — kleinere Funde der Durchsicht Installation, Update und erster Start.

Punkt 11: `hints.json` hat ein Feld `min_version`; der Filter in
`/api/public/hints` verglich es als TEXT. `"1.7.9" <= "1.7.149"` ist als Text
falsch (die Ziffer 9 ist größer als 1), ein Hinweis ab 1.7.9 verschwand also
bei 1.7.149. Heute folgenlos, weil alle Hinweise `1.7.0` tragen — aber die
nächste Hinweiszeile mit einer anderen Grenze hätte es getroffen.
"""
import json

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")


def _hinweise(tmp_path, monkeypatch, installiert, min_version):
    import bewerbungs_assistent
    from bewerbungs_assistent import dashboard as dash
    datei = tmp_path / "hints.json"
    eintrag = {"id": "x", "title": "Ein Hinweis", "text": "t"}
    if min_version is not None:
        eintrag["min_version"] = min_version
    datei.write_text(json.dumps({"hints": [eintrag]}), encoding="utf-8")
    monkeypatch.setenv("PBP_HINTS_URL", str(datei))
    monkeypatch.setattr(bewerbungs_assistent, "__version__", installiert)
    if hasattr(dash.api_public_hints, "_cache"):
        delattr(dash.api_public_hints, "_cache")
    try:
        antwort = fastapi_testclient.TestClient(dash.app).get("/api/public/hints")
        return antwort.json()["hints"]
    finally:
        if hasattr(dash.api_public_hints, "_cache"):
            delattr(dash.api_public_hints, "_cache")


@pytest.mark.parametrize("installiert,grenze,sichtbar", [
    ("1.7.149", "1.7.9", True),        # der Fall: als Text war "9" > "1"
    ("1.7.149", "1.7.0", True),
    ("1.7.149", "1.7.149", True),      # gleiche Version
    ("1.7.149", "1.7.150", False),
    ("1.7.149", "1.7.200", False),
    ("1.7.149", "1.8.0", False),
    ("1.7.9", "1.7.149", False),       # umgekehrt: als Text war "1.7.149" < "1.7.9"
    ("1.8.0-beta.15", "1.7.0", True),
    ("1.8.0-beta.15", "1.8.0", True),  # die Beta-Kennung bleibt aussen vor
    ("1.8.0-beta.15", "1.8.1", False),
    ("1.7.0-beta.5", "1.7.0", True),   # wie bisher: eine Beta sieht den Hinweis ihrer Zahl
])
def test_1149_min_version_wird_als_zahl_verglichen(tmp_path, monkeypatch, installiert, grenze, sichtbar):
    hinweise = _hinweise(tmp_path, monkeypatch, installiert, grenze)
    assert bool(hinweise) is sichtbar, (installiert, grenze, hinweise)


def test_1149_ein_hinweis_ohne_min_version_gilt_fuer_alle(tmp_path, monkeypatch):
    assert _hinweise(tmp_path, monkeypatch, "1.7.149", None)


# ══ Punkt 3: ohne Claude Desktop keine Grün-Meldung (INSTALLIEREN.bat) ═══════
#
# Befund: Ohne Claude Desktop meldete der Installer „[OK] Claude Desktop
# gefunden“ und am Ende GRÜN. Der Hinweis „PBP braucht Claude Desktop“
# widersprach der README (PBP ist ohne KI nutzbar), und der gelbe Zweig
# „Claude Desktop installieren“ war nie erreichbar, weil `CLAUDE_OK` nach
# `_setup_claude.py` (Exit 0, auch ohne Claude) immer 1 war.

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAT = ROOT / "INSTALLIEREN.bat"
OHNE_FENSTER = 0x08000000 if sys.platform == "win32" else 0
nur_windows = pytest.mark.skipif(os.name != "nt", reason="braucht cmd.exe")


def _bat() -> str:
    return BAT.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def _abschnitt(von: str, bis: str) -> str:
    """Zeilen der BAT ab der Zeile `von` (eingeschlossen) bis vor die Zeile `bis` (oder bis zu ihr)."""
    zeilen = _bat().splitlines()
    a = next(i for i, z in enumerate(zeilen) if z.strip() == von)
    b = next(i for i, z in enumerate(zeilen) if i > a and z.strip() == bis)
    return "\n".join(zeilen[a:b + 1])


def _cmd(tmp_path: Path, kopf: str, abschnitt: str, fuss: str = "echo ENDE"):
    skript = tmp_path / "abschnitt.bat"
    log = tmp_path / "install_log.txt"
    text = ("@echo off\r\nsetlocal enabledelayedexpansion\r\n"
            f'set "LOGFILE={log}"\r\n' + kopf.replace("\n", "\r\n") + "\r\n"
            + abschnitt.replace("\n", "\r\n") + "\r\n" + fuss + "\r\n")
    skript.write_bytes(text.encode("utf-8"))
    r = subprocess.run(["cmd", "/d", "/c", str(skript)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=OHNE_FENSTER, timeout=120)
    return r.stdout


def test_1149_der_hinweis_behauptet_nicht_mehr_dass_pbp_claude_braucht():
    text = _bat()
    assert "PBP braucht Claude Desktop" not in text
    assert "PBP laeuft auch ohne Claude" in text


def test_1149_claude_ok_wird_nur_bei_einem_fund_gesetzt():
    zeilen = [z.strip() for z in _bat().splitlines() if not z.lstrip().startswith("::")]
    gesetzt = [z for z in zeilen if 'set "CLAUDE_OK=1"' in z]
    assert gesetzt == ['if "!CLAUDE_FOUND!"=="1" set "CLAUDE_OK=1"'], gesetzt


def test_1149_die_erkennung_laeuft_nach_dem_download_hinweis_noch_einmal():
    text = _bat()
    assert ":claude_suche\nset \"CLAUDE_FOUND=0\"" in text
    i = text.index("start https://claude.ai/download")
    nach = text[i:i + 300]
    assert 'set "CLAUDE_NOCHMAL=1"' in nach and "goto :claude_suche" in nach


@nur_windows
@pytest.mark.parametrize("gefunden,erwartet,nicht_erwartet", [
    ("1", "[OK] Claude Desktop gefunden", "[--]"),
    ("0", "[--] Claude Desktop nicht gefunden", "[OK] Claude Desktop gefunden"),
])
def test_1149_cmd_die_meldung_zur_erkennung_stimmt(tmp_path, gefunden, erwartet, nicht_erwartet):
    abschnitt = _abschnitt('if "!CLAUDE_FOUND!"=="1" goto :claude_found', ":claude_gefunden_weiter")
    # Nie den Browser öffnen oder auf eine Taste warten, auch wenn der Merker einmal fehlen sollte.
    abschnitt = abschnitt.replace("start https://claude.ai/download", "echo STARTE-DOWNLOAD")
    abschnitt = abschnitt.replace("pause >nul", "rem pause")
    aus = _cmd(tmp_path, f'set "CLAUDE_FOUND={gefunden}"\nset "CLAUDE_NOCHMAL=1"', abschnitt)
    assert "ENDE" in aus, aus
    assert erwartet in aus, aus
    assert nicht_erwartet not in aus, aus
    assert "Download" not in aus, "mit gesetztem Merker kommt der Hinweis nicht noch einmal"


@nur_windows
@pytest.mark.parametrize("nach_der_installation_gefunden", ["1", "0"])
def test_1149_cmd_der_hinweis_kommt_einmal_und_danach_wird_noch_einmal_gesucht(tmp_path, nach_der_installation_gefunden):
    """Der Hinweis öffnet die Download-Seite (`start`) und wartet (`pause`); hier ersetzt
    durch eine Ausgabe, sonst ist der Ablauf die echte Zeilenfolge der BAT."""
    abschnitt = _abschnitt('if "!CLAUDE_FOUND!"=="1" goto :claude_found', ":claude_gefunden_weiter")
    abschnitt = abschnitt.replace("start https://claude.ai/download", "echo STARTE-DOWNLOAD")
    abschnitt = abschnitt.replace("pause >nul", "rem pause")
    kopf = ('set "RUNDE=0"\nset "CLAUDE_FOUND=0"\n'
            f'set "STUB={nach_der_installation_gefunden}"')
    # die Sprungmarke und eine Erkennung, die in Runde 2 "Claude ist jetzt da" meldet
    abschnitt = (":claude_suche\nset /a RUNDE+=1\n"
                 "if !RUNDE! gtr 5 exit /b 0\n"  # Netz gegen eine Endlosschleife
                 'if "!RUNDE!"=="2" if "!STUB!"=="1" set "CLAUDE_FOUND=1"\n' + abschnitt)
    aus = _cmd(tmp_path, kopf, abschnitt, 'echo ENDE runde=!RUNDE! gefunden=!CLAUDE_FOUND!')
    assert aus.count("STARTE-DOWNLOAD") == 1, aus
    assert "Claude Desktop wurde nicht gefunden." in aus
    assert f"ENDE runde=2 gefunden={nach_der_installation_gefunden}" in aus, aus
    if nach_der_installation_gefunden == "1":
        assert "[OK] Claude Desktop gefunden" in aus
    else:
        assert "[--] Claude Desktop nicht gefunden" in aus and "[OK] Claude Desktop gefunden" not in aus


@nur_windows
@pytest.mark.parametrize("gefunden,claude_ok,dash_ok,muss,darf_nicht", [
    ("0", "0", "1", ["[GELB]", "Claude Desktop wurde nicht gefunden - PBP laeuft trotzdem"],
     ["konnte nicht eingerichtet werden", "[GRUEN]"]),
    ("1", "0", "1", ["[GELB]", "Claude Desktop konnte nicht eingerichtet werden"],
     ["wurde nicht gefunden", "[GRUEN]"]),
    ("1", "1", "1", ["[GRUEN]"], ["[GELB]", "wurde nicht gefunden"]),
])
def test_1149_cmd_der_abschluss_nennt_den_echten_grund(tmp_path, gefunden, claude_ok, dash_ok, muss, darf_nicht):
    abschnitt = _abschnitt('set "AMPEL=GRUEN"', ":ampel_gelb_dash")
    abschnitt = abschnitt.rsplit(":ampel_gelb_dash", 1)[0] + ":ampel_gelb_dash\n:ampel_details"
    kopf = (f'set "CLAUDE_FOUND={gefunden}"\nset "CLAUDE_OK={claude_ok}"\nset "DASH_OK={dash_ok}"')
    aus = _cmd(tmp_path, kopf, abschnitt)
    assert "ENDE" in aus, aus
    for text in muss:
        assert text in aus, (text, aus)
    for text in darf_nicht:
        assert text not in aus, (text, aus)


def test_1149_die_fehlermeldung_zu_fehlenden_hilfsdateien_nennt_die_neue_datei():
    text = _bat()
    i = text.index("\n:err_setup_helper_missing\n")
    assert "- _sicherung_vor_update.py" in text[i:i + 700]


# ══ Punkt 7: die Versionsprüfung des Installers sieht die installierte Version ═══
#
# Befund: Sie las `%DATA_DIR%\src`, installiert wird nach `%APP_DIR%\src` (seit
# v1.5.0). `INSTALLED_VER` blieb leer, „Update erkannt“ und „bereits installiert“
# erschienen nie, und die Rückfrage kannte nur „j“, nicht „ja“.

def _versionsblock() -> str:
    zeilen = _bat().splitlines()
    a = next(i for i, z in enumerate(zeilen) if z.startswith('echo [DEBUG] Versions-Check...'))
    schritt = next(i for i, z in enumerate(zeilen) if z.startswith(":: SCHRITT 1: Python pruefen"))
    b = schritt - 1  # die Trennlinie davor gehört nicht mehr dazu
    while not zeilen[b].startswith(":: ---"):
        b -= 1
    return "\n".join(zeilen[a:b])


def _version_in_cmd(tmp_path: Path, installiert, neu, antwort="", wo="app"):
    """Führt die Versionsprüfung der BAT mit echten Ordnern aus; gibt (Ausgabe, Log, erreicht_das_ende) zurück."""
    wurzel = tmp_path / "wurzel"
    app, daten, quelle = wurzel / "app", wurzel / "data", tmp_path / "zip" / "src"
    for ordner in (app, daten, quelle):
        ordner.mkdir(parents=True, exist_ok=True)

    def schreibe(basis, version):
        pkg = basis / "src" / "bewerbungs_assistent" if basis != quelle else basis / "bewerbungs_assistent"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "__init__.py").write_text(f'"""PBP."""\n\n__version__ = "{version}"\n', encoding="utf-8")

    if installiert is not None:
        schreibe(app if wo == "app" else daten, installiert)
    schreibe(quelle, neu)
    log = tmp_path / "install_log.txt"
    skript = tmp_path / "versionspruefung.bat"
    kopf = (f'@echo off\r\nsetlocal enabledelayedexpansion\r\nset "LOGFILE={log}"\r\n'
            f'set "APP_DIR={app}"\r\nset "DATA_DIR={daten}"\r\nset "SRC_DIR={quelle}"\r\n')
    skript.write_bytes((kopf + _versionsblock().replace("\n", "\r\n") + "\r\necho ENDE\r\n").encode("utf-8"))
    r = subprocess.run(["cmd", "/d", "/c", str(skript)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", input=antwort + "\r\n" if antwort else "\r\n", creationflags=OHNE_FENSTER,
                       timeout=120)
    protokoll = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    return r.stdout, protokoll, "ENDE" in r.stdout


@nur_windows
def test_1149_cmd_ein_update_wird_erkannt_und_benannt(tmp_path):
    aus, log, ende = _version_in_cmd(tmp_path, "1.7.147", "1.7.148")
    assert ende, aus
    assert "Update erkannt: 1.7.147 wird auf 1.7.148 aktualisiert" in aus, aus
    assert "Update: 1.7.147 auf 1.7.148" in log


@nur_windows
def test_1149_cmd_ohne_installierte_version_kommt_keine_meldung(tmp_path):
    aus, log, ende = _version_in_cmd(tmp_path, None, "1.7.148")
    assert ende and "Update erkannt" not in aus and "bereits installiert" not in aus, aus


@nur_windows
def test_1149_cmd_nur_der_alte_ort_zaehlt_nicht(tmp_path):
    """Wo PBP früher lag (data/src), liegt es seit v1.5.0 nicht mehr; dort stehende Reste sind keine Installation."""
    aus, log, ende = _version_in_cmd(tmp_path, "1.7.148", "1.7.148", wo="daten")
    assert ende and "bereits installiert" not in aus, aus


@nur_windows
@pytest.mark.parametrize("antwort", ["n", "nein", "", "x"])
def test_1149_cmd_dieselbe_version_und_die_antwort_nein_bricht_ab(tmp_path, antwort):
    aus, log, ende = _version_in_cmd(tmp_path, "1.7.148", "1.7.148", antwort=antwort)
    assert "Version 1.7.148 ist bereits installiert" in aus, aus
    assert "Installation abgebrochen" in aus
    assert not ende, "bei „nein“ geht der Installer nicht weiter"


@nur_windows
@pytest.mark.parametrize("antwort", ["j", "J", "ja", "Ja", "y", "yes"])
def test_1149_cmd_dieselbe_version_und_die_antwort_ja_installiert_neu(tmp_path, antwort):
    aus, log, ende = _version_in_cmd(tmp_path, "1.7.148", "1.7.148", antwort=antwort)
    assert ende, aus
    assert "Installation abgebrochen" not in aus
    assert "Erzwinge Neuinstallation" in log
