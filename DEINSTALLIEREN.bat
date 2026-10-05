@echo off
:: ============================================================
:: PBP Deinstaller — Self-Relocation (Fix #620)
:: ============================================================
:: Wenn die .bat aus %APP_DIR% laeuft (Apps & Features-Aufruf),
:: kopieren wir uns nach %TEMP% und starten von dort neu. Sonst
:: wuerde Schritt [4/7] (rmdir APP_DIR) das laufende Skript
:: loeschen — cmd.exe liest Skripte just-in-time von Disk und
:: bricht still ab. Folge: Registry-Eintrag bleibt, Apps-Liste
:: zeigt PBP weiterhin an.
:: ============================================================
set "PBP_BASEDIR=%~dp0"
if "%PBP_BASEDIR:~-1%"=="\" set "PBP_BASEDIR=%PBP_BASEDIR:~0,-1%"
set "PBP_APP_DIR_CHECK=%LOCALAPPDATA%\BewerbungsAssistent\app"
if /i "%PBP_BASEDIR%"=="%PBP_APP_DIR_CHECK%" if not "%PBP_DEINST_RELOCATED%"=="1" goto :pbp_relocate
goto :pbp_main

:pbp_relocate
set "PBP_RELOC_BAT=%TEMP%\PBP-Deinstaller-%RANDOM%%RANDOM%.bat"
copy /Y "%~f0" "%PBP_RELOC_BAT%" >nul
set PBP_DEINST_RELOCATED=1
cmd /c ""%PBP_RELOC_BAT%""
del /Q "%PBP_RELOC_BAT%" >nul 2>&1
exit /b 0

:pbp_main
setlocal EnableDelayedExpansion
title PBP Bewerbungs-Assistent - Deinstallation
color 0C

set "BASEDIR=%~dp0"
if "%BASEDIR:~-1%"=="\" set "BASEDIR=%BASEDIR:~0,-1%"

set "BASE_INSTALL=%LOCALAPPDATA%\BewerbungsAssistent"
set "APP_DIR=%BASE_INSTALL%\app"
set "DATA_DIR=%BASE_INSTALL%\data"
:: Legacy-Pfade (v1.4.x Kompatibilitaet)
set "LEGACY_RUNTIME=%BASE_INSTALL%\python"
set "LEGACY_SRC=%BASE_INSTALL%\src"
set "LOCAL_RUNTIME_DIR=%BASEDIR%\python"
set "LOGFILE=%BASEDIR%\deinstall_log.txt"

if exist "%LOGFILE%" for %%F in ("%LOGFILE%") do if %%~zF GTR 1000000 del "%LOGFILE%" 2>nul

echo ================================================== >> "%LOGFILE%"
echo PBP Deinstaller v0.1.0 - %date% %time% >> "%LOGFILE%"
echo User: %USERNAME% >> "%LOGFILE%"
echo Basispfad: %BASEDIR% >> "%LOGFILE%"
echo Datenpfad: %DATA_DIR% >> "%LOGFILE%"
echo ================================================== >> "%LOGFILE%"

echo.
echo  ====================================================
echo.
echo    PBP - Persoenliches Bewerbungs-Portal
echo    Deinstallation
echo.
echo  ====================================================
echo.
echo  Was entfernt wird:
echo    - MCP-Eintrag "bewerbungs-assistent" in Claude Desktop
echo    - PBP-Runtime aus %APP_DIR%
echo    - Windows Apps ^& Features Eintrag
echo    - Desktop-Verknuepfung "PBP Bewerbungs-Portal"
echo.
echo  Hinweis:
echo    Deine Bewerbungsdaten bleiben standardmaessig erhalten.
echo    Danach kannst du optional ALLE Daten loeschen.
echo.

set /p CONFIRM="  Deinstallation jetzt starten? (j/n): "
if /i "!CONFIRM!" neq "j" (
    echo.
    echo  Abgebrochen - nichts wurde geaendert.
    echo.
    pause
    exit /b 0
)

echo.
echo  [1/7] Beende laufende PBP-Prozesse...
call :stop_pbp_processes
echo         [OK] Laufende PBP-Prozesse beendet (falls vorhanden)

echo.
echo  [2/7] Entferne Claude Desktop MCP-Eintrag...
call :remove_claude_entry
set "CLAUDE_RESULT=!errorlevel!"
if "!CLAUDE_RESULT!"=="0" echo         [OK] MCP-Eintrag entfernt
if "!CLAUDE_RESULT!"=="1" echo         [--] MCP-Eintrag war nicht vorhanden
if "!CLAUDE_RESULT!"=="2" echo         [--] Keine mcpServers in Claude-Config gefunden
if "!CLAUDE_RESULT!"=="3" echo         [!!] Claude-Config konnte nicht gelesen werden (ungueltiges JSON)
if "!CLAUDE_RESULT!"=="4" echo         [--] Claude-Config nicht gefunden
if "!CLAUDE_RESULT!"=="5" echo         [!!] Fehler beim Entfernen des MCP-Eintrags

echo.
echo  [3/7] Entferne Desktop-Verknuepfung...
call :remove_shortcut
if "!errorlevel!"=="0" (
    echo         [OK] Desktop-Verknuepfung entfernt
) else (
    echo         [--] Desktop-Verknuepfung nicht gefunden
)

echo.
echo  [4/7] Entferne Windows Apps ^& Features Eintrag...
:: #620: Registry VOR Verzeichnis-Loeschung entfernen. Falls die Self-
:: Relocation am Skript-Anfang aus irgendeinem Grund nicht greift,
:: stellt diese Reihenfolge mindestens sicher dass der Apps-Eintrag
:: weg ist (das war der prominenteste User-Sichtbare Bug).
reg delete "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PBP" /f >nul 2>&1
if !errorlevel! equ 0 (
    echo         [OK] Registry-Eintrag entfernt
) else (
    echo         [--] Registry-Eintrag war nicht vorhanden
)
:: Verifikation: pruefen ob der Key wirklich weg ist (#343)
reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PBP" >nul 2>&1
if !errorlevel! equ 0 (
    echo         [!!] Registry-Eintrag konnte nicht entfernt werden - versuche erneut...
    reg delete "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PBP" /f >nul 2>&1
    echo [WARN] Registry retry >> "%LOGFILE%"
)

echo.
echo  [5/7] Entferne Runtime-Dateien...
set "REMOVE_ERRORS=0"
:: v1.5.0 Pfade (app/)
call :remove_path "%APP_DIR%" "App-Verzeichnis %APP_DIR%"
:: Legacy v1.4.x Pfade
call :remove_path "%LEGACY_RUNTIME%" "Legacy Runtime in %BASE_INSTALL%\python"
call :remove_path "%LEGACY_SRC%" "Legacy Source in %BASE_INSTALL%\src"
call :remove_path "%LOCAL_RUNTIME_DIR%" "Lokaler Python-Ordner in %BASEDIR%\python"

if exist "%BASEDIR%\install_log.txt" (
    del /q "%BASEDIR%\install_log.txt" >nul 2>&1
    if exist "%BASEDIR%\install_log.txt" (
        echo         [!!] install_log.txt konnte nicht entfernt werden
        set /a REMOVE_ERRORS+=1
    ) else (
        echo         [OK] install_log.txt entfernt
    )
)

for %%F in ("%BASEDIR%\python-*-embed-amd64.zip") do (
    if exist "%%~fF" del /q "%%~fF" >nul 2>&1
)

echo.
echo  [6/7] Optional: Backup deiner Bewerbungsdaten erstellen
echo.
set "BACKUP_FEHLER=0"
set /p CREATE_BACKUP="  Soll ein Backup auf dem Desktop erstellt werden? (j/n): "
if /i "!CREATE_BACKUP!"=="j" (
    set "BACKUP_ZIP=%USERPROFILE%\Desktop\PBP-Backup-%date:~6,4%-%date:~3,2%-%date:~0,2%.zip"
    echo         Erstelle Backup...
    powershell -ExecutionPolicy Bypass -NoProfile -Command "$ErrorActionPreference = 'Stop'; if (Test-Path '%DATA_DIR%') { try { Compress-Archive -Path '%DATA_DIR%\*' -DestinationPath '!BACKUP_ZIP!' -Force; if (-not (Test-Path '!BACKUP_ZIP!')) { throw 'Die ZIP-Datei fehlt.' }; Write-Host '        [OK] Backup erstellt: !BACKUP_ZIP!'; exit 0 } catch { Write-Host ('        [FEHLER] Backup NICHT erstellt: ' + $_.Exception.Message); exit 2 } } else { Write-Host '        [--] Kein Datenordner gefunden'; exit 1 }" 2>>"%LOGFILE%"
    if errorlevel 2 set "BACKUP_FEHLER=1"
    echo [INFO] Desktop-Backup erstellt >> "%LOGFILE%"
)

echo.
echo  [7/7] Optional: Alle Bewerbungsdaten loeschen
echo.
echo         ACHTUNG: Dein Profil, alle Stellen und Bewerbungen
echo         werden UNWIDERRUFLICH geloescht!
echo.
if "!BACKUP_FEHLER!"=="1" (
    echo         ACHTUNG: Das Backup konnte NICHT erstellt werden ^(siehe oben^).
    echo         Mit LOESCHEN ist alles endgueltig weg. Zum Abbrechen etwas anderes eingeben.
    echo.
)
set /p DELETE_DATA="  Bist du sicher? Tippe LOESCHEN zum Bestaetigen: "
if "!DELETE_DATA!"=="LOESCHEN" (
    if exist "%DATA_DIR%" (
        rmdir /s /q "%DATA_DIR%" >nul 2>&1
        if exist "%DATA_DIR%" (
            echo         [!!] Datenordner konnte nicht komplett entfernt werden
            echo [WARN] Datenordner konnte nicht komplett entfernt werden >> "%LOGFILE%"
            set "DATA_RESULT=failed"
        ) else (
            echo         [OK] Alle Bewerbungsdaten entfernt
            echo [OK] Datenordner komplett entfernt >> "%LOGFILE%"
            set "DATA_RESULT=deleted"
        )
    ) else (
        echo         [--] Datenordner nicht gefunden
        set "DATA_RESULT=not_found"
    )
) else (
    echo         [OK] Bewerbungsdaten bleiben erhalten
    echo [INFO] Bewerbungsdaten wurden beibehalten >> "%LOGFILE%"
    set "DATA_RESULT=kept"
)

:: #620: Stamm-Ordner BASE_INSTALL entfernen wenn leer
:: rmdir ohne /s loescht NUR leere Verzeichnisse — sicher.
:: Wenn der User die Daten behalten hat, bleibt %DATA_DIR% drin und
:: damit auch %BASE_INSTALL% — kein Datenverlust.
rmdir "%BASE_INSTALL%" 2>nul
if exist "%BASE_INSTALL%" (
    echo [INFO] %BASE_INSTALL% nicht entfernt ^(enthaelt noch Daten^) >> "%LOGFILE%"
) else (
    echo [OK] %BASE_INSTALL% Stamm-Ordner entfernt >> "%LOGFILE%"
)

echo.
echo  ====================================================
echo.
echo    Deinstallation abgeschlossen
echo.
echo  ====================================================
echo.

set "CLAUDE_MANUELL=0"
if "!CLAUDE_RESULT!"=="3" set "CLAUDE_MANUELL=1"
if "!CLAUDE_RESULT!"=="5" set "CLAUDE_MANUELL=1"
if "!CLAUDE_MANUELL!"=="1" (
    echo  WICHTIG:
    echo    Die Claude-Konfigurationsdatei konnte nicht automatisch
    echo    bearbeitet werden. Entferne den MCP-Server-Eintrag
    echo    "bewerbungs-assistent" manuell in:
    echo    %APPDATA%\Claude\claude_desktop_config.json
    echo    ^(bei Claude aus dem Microsoft Store: %LOCALAPPDATA%\Packages\Claude_...
    echo    \LocalCache\Roaming\Claude\claude_desktop_config.json^)
    echo.
)

if "!DATA_RESULT!"=="kept" (
    echo  Deine Daten sind weiterhin vorhanden unter:
    echo    %DATA_DIR%
    echo.
)

if exist "%BASE_INSTALL%" (
    echo  Hinweis: Falls Reste verbleiben ^(z.B. weil Dateien noch gesperrt
    echo  waren^), kannst du diesen Ordner gefahrlos manuell loeschen:
    echo    %BASE_INSTALL%
    echo.
)

echo  Bitte Claude Desktop einmal komplett neu starten.
echo  Log-Datei: %LOGFILE%
echo.
echo  Druecke eine beliebige Taste zum Schliessen...
pause >nul
exit /b 0

:stop_pbp_processes
:: #739: wmic ist auf neueren Windows-Builds nicht mehr zuverlaessig verfuegbar
:: (deprecated Feature-on-Demand) — frueher haengte der Prozess-Stopp daran.
:: Robuster Stopp via PowerShell/CIM: beendet nur python-Prozesse, deren
:: Kommandozeile eindeutig zu PBP gehoert. Ausgabe geht ins Log (Diagnose).
:: Praxisprobe 1.8 (05.10.2026): auch das Konsolenfenster des Dashboards (cmd /K "Dashboard starten.bat") wird
:: geschlossen - es blieb sonst nach der Deinstallation leer stehen. Die Deinstaller-Fassung traegt einen anderen Namen.
powershell -ExecutionPolicy Bypass -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { (($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and ($_.CommandLine -match 'bewerbungs_assistent|start_dashboard|_selftest')) -or ($_.Name -eq 'cmd.exe' -and $_.CommandLine -match 'Dashboard starten\.bat') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >> "%LOGFILE%" 2>&1
:: Kurze Pause, damit gesperrte Datei-Handles (pbp.db / WAL) freigegeben werden,
:: bevor die Runtime-Dateien geloescht werden — sonst schlaegt rmdir still fehl.
ping -n 3 127.0.0.1 >nul 2>&1
exit /b 0

:: Praxisprobe 1.8 (05.10.2026): _setup_claude.py schreibt den Eintrag in ALLE Konfigurationsdateien (Standardpfad und
:: Store-Pakete). Der Deinstaller las nur den Standardpfad - bei der Store-Fassung blieb der Eintrag stehen, und Claude
:: meldete danach bei jedem Start einen Server, dessen Programm es nicht mehr gab. Rueckgabe: 0 entfernt, 1 kein Eintrag,
:: 2 keine mcpServers, 3 nicht lesbar, 4 keine Datei, 5 Schreibfehler; bei mehreren Dateien gilt der schlimmste Fall.
:remove_claude_entry
powershell -ExecutionPolicy Bypass -NoProfile -Command "$pfade = @(Join-Path $env:APPDATA 'Claude\claude_desktop_config.json'); if ($env:LOCALAPPDATA) { foreach ($muster in 'Claude_*', 'AnthropicPBC.Claude*') { foreach ($d in @(Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Packages') -Directory -Filter $muster -ErrorAction SilentlyContinue)) { $pfade += Join-Path $d.FullName 'LocalCache\Roaming\Claude\claude_desktop_config.json' } } }; $ergebnisse = @(); foreach ($p in $pfade) { $r = 4; if (Test-Path $p) { $cfg = $null; try { $cfg = Get-Content -Path $p -Raw -Encoding UTF8 | ConvertFrom-Json; $r = 0 } catch { $r = 3 }; if ($r -eq 0) { if (-not ($cfg.PSObject.Properties.Name -contains 'mcpServers') -or -not $cfg.mcpServers) { $r = 2 } elseif (-not ($cfg.mcpServers.PSObject.Properties.Name -contains 'bewerbungs-assistent')) { $r = 1 } else { try { Copy-Item -Path $p -Destination ($p + '.pbp-backup') -Force; $null = $cfg.mcpServers.PSObject.Properties.Remove('bewerbungs-assistent'); if ($cfg.mcpServers.PSObject.Properties.Count -eq 0) { $cfg.mcpServers = @{} }; [IO.File]::WriteAllText($p, ($cfg | ConvertTo-Json -Depth 15), (New-Object System.Text.UTF8Encoding($false))); $r = 0 } catch { $r = 5 } } } }; Write-Host ('[INFO] Claude-Config ' + $p + ' -> ' + $r); $ergebnisse += $r }; foreach ($c in 5, 3, 0, 1, 2) { if ($ergebnisse -contains $c) { exit $c } }; exit 4" >> "%LOGFILE%" 2>&1
if %errorlevel% geq 5 exit /b 5
exit /b %errorlevel%

:remove_shortcut
powershell -ExecutionPolicy Bypass -NoProfile -Command "$s = Join-Path ([Environment]::GetFolderPath('Desktop')) 'PBP Bewerbungs-Portal.lnk'; if (Test-Path $s) { Remove-Item -Path $s -Force; exit 0 } else { exit 1 }" >nul 2>&1
exit /b %errorlevel%

:remove_path
set "TARGET=%~1"
set "TARGET_LABEL=%~2"
if not exist "%TARGET%" (
    echo         [--] %TARGET_LABEL% nicht gefunden
    echo [INFO] Nicht gefunden: %TARGET% >> "%LOGFILE%"
    exit /b 0
)

rmdir /s /q "%TARGET%" >nul 2>&1
:: #739: ein Retry nach kurzer Pause — bei frisch beendetem Dashboard koennen
:: Datei-Handles noch eine Sekunde gehalten werden.
if exist "%TARGET%" (
    ping -n 3 127.0.0.1 >nul 2>&1
    rmdir /s /q "%TARGET%" >nul 2>&1
)
if exist "%TARGET%" (
    echo         [!!] %TARGET_LABEL% konnte nicht entfernt werden
    echo [WARN] Entfernen fehlgeschlagen: %TARGET% >> "%LOGFILE%"
    set /a REMOVE_ERRORS+=1
) else (
    echo         [OK] %TARGET_LABEL% entfernt
    echo [OK] Entfernt: %TARGET% >> "%LOGFILE%"
)
exit /b 0
