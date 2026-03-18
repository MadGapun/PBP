@echo off
chcp 65001 >nul 2>&1
title PBP Setup.exe Builder
color 0F

echo.
echo  ╔════════════════════════════════════════════════╗
echo  ║  PBP Setup.exe Builder                         ║
echo  ║  Erstellt eine Setup.exe aus dem GUI-Installer  ║
echo  ╚════════════════════════════════════════════════╝
echo.
echo  Voraussetzungen:
echo    - Python 3.11+ mit pip
echo    - Node.js mit npm/pnpm
echo.

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "FRONTEND_DIR=%PROJECT_DIR%\frontend"

:: ----------------------------------------------------
:: Step 1: Frontend bauen
:: ----------------------------------------------------
echo  [1/4] Baue Frontend...

:: Check for pnpm
where pnpm >nul 2>&1
if %errorlevel% neq 0 (
    echo    WARNUNG: pnpm nicht gefunden. Versuche, es via npm zu installieren...
    call npm install -g pnpm
    if %errorlevel% neq 0 (
        echo    FEHLER: pnpm konnte nicht installiert werden.
        echo    Bitte Node.js (https://nodejs.org) installieren und dann 'npm install -g pnpm' ausfuehren.
        pause
        exit /b 1
    )
)

echo    Installiere Frontend-Abhaengigkeiten...
call pnpm --dir "%FRONTEND_DIR%" install
if %errorlevel% neq 0 (
    echo    FEHLER: 'pnpm install' ist fehlgeschlagen.
    pause
    exit /b 1
)

echo    Baue Frontend-Dateien...
call pnpm --dir "%FRONTEND_DIR%" run build
if %errorlevel% neq 0 (
    echo    FEHLER: 'pnpm run build' ist fehlgeschlagen.
    pause
    exit /b 1
)
echo         ✓ Frontend erfolgreich gebaut.

:: ----------------------------------------------------
:: Step 2: Python und PyInstaller pruefen
:: ----------------------------------------------------
echo.
echo  [2/4] Installiere PyInstaller...

:: Find Python
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY (where py >nul 2>&1 && set "PY=py -3")
if not defined PY (
    echo  FEHLER: Python nicht gefunden!
    echo  Bitte installiere Python 3.11+ von python.org
    pause
    exit /b 1
)

%PY% -m pip install pyinstaller -q
if %errorlevel% neq 0 (
    echo  FEHLER: PyInstaller konnte nicht installiert werden.
    pause
    exit /b 1
)
echo         ✓ PyInstaller bereit

:: ----------------------------------------------------
:: Step 3: Setup.exe bauen
:: ----------------------------------------------------
echo.
echo  [3/4] Baue Setup.exe...
echo         (Das dauert 1-2 Minuten)
echo.

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."

:: Build the exe
%PY% -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "PBP-Setup" ^
    --add-data "%PROJECT_DIR%\src;bewerbungs-assistent\src" ^
    --add-data "%PROJECT_DIR%\pyproject.toml;bewerbungs-assistent" ^
    --add-data "%PROJECT_DIR%\test_demo.py;bewerbungs-assistent" ^
    --clean ^
    --noconfirm ^
    "%SCRIPT_DIR%setup_gui.py"

if %errorlevel% neq 0 (
    echo.
    echo  FEHLER beim Bauen der Setup.exe!
    pause
    exit /b 1
)

:: ----------------------------------------------------
:: Step 4: Fertig
:: ----------------------------------------------------
echo.
echo  [4/4] Fertig!
echo.

if exist "dist\PBP-Setup.exe" (
    echo  ╔════════════════════════════════════════════════╗
    echo  ║  ✓ Setup.exe erstellt!                         ║
    echo  ║                                                ║
    echo  ║  Datei: dist\PBP-Setup.exe                     ║
    echo  ╚════════════════════════════════════════════════╝
    echo.
    echo  Diese Datei kannst du an andere weitergeben.
    echo  Sie enthaelt alles — der Empfaenger braucht
    echo  nur Python 3.11+ installiert zu haben.
    echo.

    :: Show file size
    for %%A in ("dist\PBP-Setup.exe") do echo  Groesse: %%~zA bytes
) else (
    echo  WARNUNG: dist\PBP-Setup.exe wurde nicht gefunden.
    echo  Pruefe die Ausgabe oben auf Fehler.
)

echo.
pause
