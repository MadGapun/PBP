"""Auto-Update (#1093): die Bauform von INSTALLIEREN.bat nach dem Umbau auf Versionsordner.

Ein `.bat` laesst sich nicht wie Python testen. Zwei Dinge schuetzen es: die Logik steht in Python-Helfern
(`_programm_einrichten.py`, `_installer_aufraeumen.py`, mit eigenen Tests), und diese Datei haelt die Bauform
fest — wer sie umbaut, ohne diese Zusagen zu kennen, faellt hier auf.
"""
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
BAT = (WURZEL / "INSTALLIEREN.bat").read_text(encoding="utf-8").replace("\r\n", "\n")


def abschnitt(marke: str, bis: str) -> str:
    i = BAT.index(marke)
    return BAT[i:BAT.index(bis, i)]


def test_die_neuen_dateien_gehoeren_zur_vollstaendigkeitspruefung_des_entpackten_ordners():
    kopf = BAT[:BAT.index("Logging initialisieren")]
    for datei in ("_programm_einrichten.py", "_installer_aufraeumen.py", "installer\\boot\\start_dashboard_launcher.py"):
        assert f'if not exist "%BASEDIR%\\{datei}" goto :err_setup_helper_missing' in kopf, datei
        assert f"echo    - {datei}" in BAT, f"die Fehlermeldung muss {datei} nennen"


def test_das_programm_kommt_in_einen_versionsordner_nicht_mehr_nach_app_src():
    assert '"%PYTHON%" "%BASEDIR%\\_programm_einrichten.py" "%BASEDIR%" "%APP_DIR%"' in BAT
    assert 'xcopy "%SRC_DIR%" "%APP_DIR%\\src\\"' not in BAT
    assert 'rmdir /s /q "%APP_DIR%\\src"' not in BAT, "den alten Aufbau entfernt der Helfer, NACHDEM die neue Fassung steht"
    stelle = BAT.index("_programm_einrichten.py\" \"%BASEDIR%\" \"%APP_DIR%\"")
    folge = BAT[stelle:stelle + 400]
    assert "if !errorlevel! neq 0 goto :err_copy_runtime" in folge, "ein Fehler des Helfers bricht ab, statt weiterzumachen"


def test_der_unveraenderliche_starter_wird_nicht_vom_echten_start_dashboard_ueberschrieben():
    """Im Programmordner steht der Starter; ein `copy` der echten Datei hierher wuerde ihn ersetzen."""
    assert 'copy /Y "%BASEDIR%\\start_dashboard.py" "%APP_DIR%\\"' not in BAT
    assert 'copy /Y "%BASEDIR%\\_selftest.py" "%APP_DIR%\\"' not in BAT


def test_die_installierte_fassung_kommt_zuerst_aus_aktuell_txt():
    block = abschnitt("Versions-Check", "SCHRITT 1")
    assert 'set /p INSTALLED_VER=<"%APP_DIR%\\aktuell.txt"' in block
    assert block.index("aktuell.txt") < block.index("%APP_DIR%\\src\\bewerbungs_assistent\\__init__.py"), \
        "der alte Aufbau ist nur der Rueckfall"
    assert 'if not defined INSTALLED_VER if exist "%APP_DIR%\\src' in block


def test_die_runtime_wird_weiter_in_den_programmordner_kopiert_und_das_programm_erst_danach_eingerichtet():
    assert BAT.index('xcopy "%PYTHON_DIR%" "%APP_DIR%\\python\\"') < BAT.index("_programm_einrichten.py\" \"%BASEDIR%\"")


def test_vor_dem_einrichten_werden_die_prozesse_beendet():
    assert BAT.index("Stop-Process -Id") < BAT.index("_programm_einrichten.py\" \"%BASEDIR%\"")


# ══ Aufraeumen ═══════════════════════════════════════════════════════════════════════════

def unterprogramm() -> str:
    i = BAT.index("\n:installer_aufraeumen_anbieten\n") + 1       # die Marke, nicht der Aufruf `call :installer_...`
    return BAT[i:BAT.index(":show_support_info", i)]


def test_das_aufraeumen_wird_nur_nach_einer_gruenen_installation_angeboten():
    assert 'if "!AMPEL!"=="GRUEN" call :installer_aufraeumen_anbieten' in BAT
    assert len(re.findall(r"call :installer_aufraeumen_anbieten", BAT)) == 1


def test_das_aufraeumen_kommt_vor_dem_schliessen_des_fensters():
    aufruf = BAT.index("call :installer_aufraeumen_anbieten")
    assert aufruf < BAT.index("Druecke eine beliebige Taste um dieses Fenster zu schliessen")


def test_nie_beendet_das_unterprogramm_sofort_und_ohne_etwas_zu_tun():
    u = unterprogramm()
    assert u.index('if "!AUFRAEUMEN!"=="nie" goto :eof') < u.index("plan") < u.index("loeschen")


def test_vor_dem_loeschen_steht_immer_die_pruefung_des_helfers():
    u = unterprogramm()
    assert "_installer_aufraeumen.py\" plan " in u and "if errorlevel 1 goto :eof" in u
    assert u.index("_installer_aufraeumen.py\" plan ") < u.index("if errorlevel 1 goto :eof") < u.index("_installer_aufraeumen.py\" loeschen ")


def test_nur_bei_fragen_wird_gefragt_und_nur_ja_loescht():
    u = unterprogramm()
    assert 'if "!AUFRAEUMEN!"=="immer" goto :aufraeumen_ausfuehren' in u
    assert u.index('set /p ANTWORT=') < u.index("\n:aufraeumen_ausfuehren\n")      # die Marke, nicht das goto davor
    assert 'if /i not "!ANTWORT!"=="j" if /i not "!ANTWORT!"=="y" goto :eof' in u
    assert 'set "ANTWORT=n"' in u, "ohne Eingabe gilt Nein"


def test_der_helfer_laeuft_mit_der_python_laufzeit_im_programmordner_nicht_der_im_installationsordner():
    """Die Laufzeit im Installationsordner waere beim Loeschen gesperrt: sie liegt in dem Ordner, der geloescht werden soll."""
    u = unterprogramm()
    for zeile in u.splitlines():
        if "_installer_aufraeumen.py" in zeile and ("einstellung" in zeile or "plan" in zeile or "loeschen" in zeile):
            assert '"%APP_DIR%\\python\\python.exe"' in zeile, zeile
            assert '"%PYTHON%"' not in zeile, zeile


def test_das_unterprogramm_steht_ausserhalb_jedes_klammerblocks():
    """#990: in einem Klammerblock beendet ein `)` in einer echo-Zeile den Block. Das Unterprogramm hat keine Bloecke."""
    u = unterprogramm()
    for zeile in u.splitlines():
        assert not zeile.rstrip().endswith("("), zeile
        assert not zeile.strip().startswith(")"), zeile


# ══ DEINSTALLIEREN.bat mit dem neuen Aufbau ══════════════════════════════════════════════

DEINST = (WURZEL / "DEINSTALLIEREN.bat").read_text(encoding="utf-8").replace("\r\n", "\n")


def test_der_deinstaller_entfernt_den_ganzen_programmordner_samt_versionen():
    """Nutzerwunsch (02.10.2026): die Versionen liegen im Programmordner, damit das Deinstallieren sie mitnimmt."""
    assert 'set "APP_DIR=%BASE_INSTALL%\\app"' in DEINST
    assert 'call :remove_path "%APP_DIR%"' in DEINST
    assert "versions" not in DEINST.replace("versions_", ""), "kein Sonderweg fuer einzelne Versionen: der Ordner geht als Ganzes"


def test_der_deinstaller_beendet_auch_server_und_dashboard_ueber_den_startbaustein():
    """Ein laufender Prozess haelt Dateien im Programmordner fest; erkannt wird er an der Kommandozeile."""
    treffer = re.search(r"CommandLine -match '([^']+)'", DEINST)
    assert treffer, "die Erkennung der PBP-Prozesse fehlt"
    muster = re.compile(treffer.group(1))
    app = r"C:\Users\x\AppData\Local\BewerbungsAssistent\app"
    for zeile in (
        rf'"{app}\python\python.exe" -m bewerbungs_assistent_boot',                  # Claude Desktop startet den Server so
        rf'"{app}\python\python.exe" "{app}\start_dashboard.py"',                    # die Desktop-Verknuepfung
        rf'"{app}\python\python.exe" "{app}\versions\1.8.1\start_dashboard.py"',
        rf'"{app}\python\python.exe" "{app}\update\entpackt\_selftest.py"',          # der Selbsttest eines laufenden Updates
        rf'"{app}\python\python.exe" -m bewerbungs_assistent',                       # der alte Aufbau
    ):
        assert muster.search(zeile), zeile
    assert not muster.search(r'"C:\Python313\python.exe" -m http.server'), "fremde Python-Prozesse bleiben"
