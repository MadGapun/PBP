@echo off
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
timeout /t 2 /nobreak >nul
"%PYTHON%" "%DIR%\start_dashboard.py"
