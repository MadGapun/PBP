@echo off
setlocal EnableDelayedExpansion
set "DIR=%~dp0"
if "%DIR:~-1%"=="\" set "DIR=%DIR:~0,-1%"
set "PYTHON=%DIR%\python\python.exe"
title PBP Bewerbungs-Portal
echo.
echo  ====================================================
echo    PBP - Persoenliches Bewerbungs-Portal
echo    Dashboard: http://localhost:8200
echo    Zum Beenden: Dieses Fenster schliessen
echo  ====================================================
echo.

if not exist "%PYTHON%" (
    echo  [FEHLER] Python nicht gefunden unter:
    echo    %PYTHON%
    echo.
    echo  Mache neu: INSTALLIEREN.bat ausfuehren.
    echo.
    pause
    exit /b 1
)
if not exist "%DIR%\start_dashboard.py" (
    echo  [FEHLER] start_dashboard.py nicht gefunden unter:
    echo    %DIR%\start_dashboard.py
    echo.
    echo  Mache neu: INSTALLIEREN.bat ausfuehren.
    echo.
    pause
    exit /b 1
)

timeout /t 2 /nobreak >nul
"%PYTHON%" "%DIR%\start_dashboard.py"

:: v1.7.0-beta.23: Wenn Dashboard mit Fehler endet, Fenster offen halten
:: damit der User die Fehlermeldung sehen kann (vorher schloss das Fenster
:: einfach stumm und der User dachte 'das laeuft nicht').
if !errorlevel! neq 0 (
    echo.
    echo  ====================================================
    echo  [FEHLER] Dashboard ist mit Fehlercode %errorlevel% beendet.
    echo  Pruefe das Log unter:
    echo    %LOCALAPPDATA%\BewerbungsAssistent\data\logs\pbp.log
    echo  ====================================================
    pause
)
