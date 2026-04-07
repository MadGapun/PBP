@echo off
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
echo  [1/5] Beende laufende PBP-Prozesse...
call :stop_pbp_processes
if "!STOPPED_COUNT!"=="0" (
    echo         [--] Keine laufenden PBP-Prozesse gefunden
) else (
    echo         [OK] !STOPPED_COUNT! Prozess(e) beendet
)

echo.
echo  [2/5] Entferne Claude Desktop MCP-Eintrag...
call :remove_claude_entry
set "CLAUDE_RESULT=!errorlevel!"
if "!CLAUDE_RESULT!"=="0" echo         [OK] MCP-Eintrag entfernt
if "!CLAUDE_RESULT!"=="1" echo         [--] MCP-Eintrag war nicht vorhanden
if "!CLAUDE_RESULT!"=="2" echo         [--] Keine mcpServers in Claude-Config gefunden
if "!CLAUDE_RESULT!"=="3" echo         [!!] Claude-Config konnte nicht gelesen werden (ungueltiges JSON)
if "!CLAUDE_RESULT!"=="4" echo         [--] Claude-Config nicht gefunden
if "!CLAUDE_RESULT!"=="5" echo         [!!] Fehler beim Entfernen des MCP-Eintrags

echo.
echo  [3/5] Entferne Desktop-Verknuepfung...
call :remove_shortcut
if "!errorlevel!"=="0" (
    echo         [OK] Desktop-Verknuepfung entfernt
) else (
    echo         [--] Desktop-Verknuepfung nicht gefunden
)

echo.
echo  [4/6] Entferne Runtime-Dateien...
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
echo  [5/6] Entferne Windows Apps ^& Features Eintrag...
reg delete "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PBP" /f >nul 2>&1
if !errorlevel! equ 0 (
    echo         [OK] Registry-Eintrag entfernt
) else (
    echo         [--] Registry-Eintrag war nicht vorhanden
)

echo.
echo  [6/6] Optional: Alle Bewerbungsdaten loeschen
set /p DELETE_DATA="  Soll %DATA_DIR% komplett geloescht werden? (j/n): "
if /i "!DELETE_DATA!"=="j" (
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

echo.
echo  ====================================================
echo.
echo    Deinstallation abgeschlossen
echo.
echo  ====================================================
echo.

if "!CLAUDE_RESULT!"=="3" (
    echo  WICHTIG:
    echo    Die Claude-Konfigurationsdatei konnte nicht automatisch
    echo    bearbeitet werden. Entferne den MCP-Server-Eintrag
    echo    "bewerbungs-assistent" manuell in:
    echo    %APPDATA%\Claude\claude_desktop_config.json
    echo.
)

if "!DATA_RESULT!"=="kept" (
    echo  Deine Daten sind weiterhin vorhanden unter:
    echo    %DATA_DIR%
    echo.
)

echo  Bitte Claude Desktop einmal komplett neu starten.
echo  Log-Datei: %LOGFILE%
echo.
echo  Druecke eine beliebige Taste zum Schliessen...
pause >nul
exit /b 0

:stop_pbp_processes
set "STOPPED_COUNT=0"
for /f "tokens=2" %%p in ('tasklist /fi "imagename eq python.exe" /fo list 2^>nul ^| findstr /i "PID"') do (
    wmic process where "ProcessId=%%p" get CommandLine 2>nul | findstr /i "bewerbungs_assistent start_dashboard.py _selftest.py" >nul 2>&1
    if !errorlevel! equ 0 (
        taskkill /pid %%p /f >nul 2>&1
        if !errorlevel! equ 0 set /a STOPPED_COUNT+=1
    )
)
exit /b 0

:remove_claude_entry
powershell -ExecutionPolicy Bypass -NoProfile -Command "$p = Join-Path $env:APPDATA 'Claude\claude_desktop_config.json'; if (-not (Test-Path $p)) { exit 4 }; try { $cfg = Get-Content -Path $p -Raw -Encoding UTF8 | ConvertFrom-Json } catch { exit 3 }; if (-not ($cfg.PSObject.Properties.Name -contains 'mcpServers')) { exit 2 }; if (-not $cfg.mcpServers) { exit 2 }; if (-not ($cfg.mcpServers.PSObject.Properties.Name -contains 'bewerbungs-assistent')) { exit 1 }; Copy-Item -Path $p -Destination ($p + '.pbp-backup') -Force; $null = $cfg.mcpServers.PSObject.Properties.Remove('bewerbungs-assistent'); if ($cfg.mcpServers.PSObject.Properties.Count -eq 0) { $cfg.mcpServers = @{} }; $cfg | ConvertTo-Json -Depth 15 | Set-Content -Path $p -Encoding UTF8; exit 0" >> "%LOGFILE%" 2>&1
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
if exist "%TARGET%" (
    echo         [!!] %TARGET_LABEL% konnte nicht entfernt werden
    echo [WARN] Entfernen fehlgeschlagen: %TARGET% >> "%LOGFILE%"
    set /a REMOVE_ERRORS+=1
) else (
    echo         [OK] %TARGET_LABEL% entfernt
    echo [OK] Entfernt: %TARGET% >> "%LOGFILE%"
)
exit /b 0
