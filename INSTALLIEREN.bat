@echo off
setlocal EnableDelayedExpansion
title PBP Bewerbungs-Assistent - Setup
color 0F

:: -------------------------------------------
:: PBP Installer v0.11.0
:: Fix: Erkennung wenn BAT aus ZIP heraus gestartet wird
:: Fix: Fehler-melden Hinweis bei allen Fehlern
:: Fix: setuptools+wheel vor extract-msg (embeddable Python)
:: Fix: Klare Fehlermeldung wenn Outlook-Import scheitert
:: Fix: Versionserkennung korrigiert
:: Fix: Dashboard + Startdateien nach DATA_DIR kopieren
:: Fix: Python nur downloaden wenn noch nicht vorhanden
:: Fix: Desktop-Shortcut zeigt auf DATA_DIR (stabil)
:: -------------------------------------------

:: Variablen
set "BASEDIR=%~dp0"
if "%BASEDIR:~-1%"=="\" set "BASEDIR=%BASEDIR:~0,-1%"

set "PYTHON_DIR=%BASEDIR%\python"
set "PYTHON=%PYTHON_DIR%\python.exe"
set "DATA_DIR=%LOCALAPPDATA%\BewerbungsAssistent"
set "SRC_DIR=%BASEDIR%\src"
set "LOGFILE=%BASEDIR%\install_log.txt"

:: Python Embeddable Download
set "PY_VERSION=3.12.10"
set "PY_ZIP=python-%PY_VERSION%-embed-amd64.zip"
set "PY_URL=https://www.python.org/ftp/python/%PY_VERSION%/%PY_ZIP%"
set "GETPIP_URL=https://bootstrap.pypa.io/get-pip.py"

:: -------------------------------------------
:: Integritaets-Check: Wurde das ZIP richtig entpackt?
:: -------------------------------------------
if not exist "%SRC_DIR%" goto :err_not_extracted

:: -------------------------------------------
:: Logging initialisieren
:: -------------------------------------------
if exist "%LOGFILE%" for %%F in ("%LOGFILE%") do if %%~zF GTR 1000000 del "%LOGFILE%" 2>nul

echo ================================================== >> "%LOGFILE%"
echo PBP Installer v0.11.0 - %date% %time% >> "%LOGFILE%"
echo System: %OS% %PROCESSOR_ARCHITECTURE% >> "%LOGFILE%"
echo User: %USERNAME% >> "%LOGFILE%"
echo Pfad: %BASEDIR% >> "%LOGFILE%"
echo ================================================== >> "%LOGFILE%"

echo.
echo  ====================================================
echo.
echo    PBP - Persoenliches Bewerbungs-Portal
echo    Dein KI-Bewerbungshelfer
echo    Installer v0.11.0
echo.
echo  ====================================================
echo.
echo  Willkommen! Dieses Setup richtet ALLES automatisch ein.
echo  Du musst NICHTS selber installieren oder konfigurieren.
echo  Einfach warten - alles passiert von alleine.
echo.
echo  Was du brauchst:
echo    - Internetverbindung
echo    - Claude Desktop ^(claude.ai/download^)
echo.
echo  Was jetzt automatisch passiert:
echo    1. Python wird heruntergeladen und eingerichtet
echo    2. Alle Pakete werden installiert
echo    3. Claude Desktop wird konfiguriert
echo    4. Fertig - du kannst sofort loslegen
echo.
echo  Dauer: ca. 3-5 Minuten
echo.
echo  ****************************************************
echo  *  WICHTIG: Dieses Fenster NICHT schliessen!       *
echo  *  Einfach warten bis "FERTIG" erscheint.          *
echo  ****************************************************
echo.

:: -------------------------------------------
:: Versions-Check: Ist die aktuelle Version schon installiert?
:: -------------------------------------------
echo [DEBUG] Versions-Check... >> "%LOGFILE%"
if exist "%DATA_DIR%\src\bewerbungs_assistent\__init__.py" (
    for /f "tokens=3 delims= " %%v in ('findstr /C:"__version__" "%DATA_DIR%\src\bewerbungs_assistent\__init__.py" 2^>nul') do set "INSTALLED_VER=%%~v"
    for /f "tokens=3 delims= " %%v in ('findstr /C:"__version__" "%SRC_DIR%\bewerbungs_assistent\__init__.py" 2^>nul') do set "NEW_VER=%%~v"
    if defined INSTALLED_VER if defined NEW_VER if "!INSTALLED_VER!"=="!NEW_VER!" (
        echo [INFO] Version !INSTALLED_VER! ist bereits installiert >> "%LOGFILE%"
        echo.
        echo  Version !INSTALLED_VER! ist bereits installiert.
        echo.
        set /p FORCE_INSTALL="  Trotzdem neu installieren? ^(j/n^): "
        if /i "!FORCE_INSTALL!" neq "j" (
            echo.
            echo  Installation abgebrochen. Aktuelle Version laeuft bereits.
            echo.
            pause
            exit /b 0
        )
        echo [INFO] Erzwinge Neuinstallation >> "%LOGFILE%"
    ) else (
        echo [INFO] Update: !INSTALLED_VER! auf !NEW_VER! >> "%LOGFILE%"
        echo.
        echo  Update erkannt: !INSTALLED_VER! wird auf !NEW_VER! aktualisiert.
        echo.
    )
)

:: -------------------------------------------
:: SCHRITT 1: Python pruefen / herunterladen
:: -------------------------------------------
echo  [1/4] Python einrichten...
echo [1/4] Python einrichten... >> "%LOGFILE%"

:: Python bereits vorhanden? (1. im ZIP-Ordner, 2. in DATA_DIR von frueherer Installation)
if exist "%PYTHON%" goto :python_ready

:: Fruehere Installation in DATA_DIR vorhanden? -> wiederverwenden statt neu downloaden
if exist "%DATA_DIR%\python\python.exe" (
    echo [INFO] Python aus frueherer Installation gefunden: %DATA_DIR%\python >> "%LOGFILE%"
    echo         Python aus frueherer Installation gefunden.
    if not exist "%PYTHON_DIR%" mkdir "%PYTHON_DIR%"
    xcopy "%DATA_DIR%\python" "%PYTHON_DIR%\" /E /I /Q /Y >> "%LOGFILE%" 2>&1
    if exist "%PYTHON%" goto :python_ready
    echo [WARN] Kopie fehlgeschlagen, lade Python neu herunter >> "%LOGFILE%"
)

:: --- Python muss heruntergeladen werden ---
echo.
echo         Python ist noch nicht vorhanden.
echo         Wird jetzt AUTOMATISCH heruntergeladen
echo         und eingerichtet. Einfach warten!
echo.

:: 64-Bit pruefen
echo [DEBUG] Pruefe Architektur... >> "%LOGFILE%"
if "%PROCESSOR_ARCHITECTURE%"=="x86" if not defined PROCESSOR_ARCHITEW6432 goto :err_32bit
echo [DEBUG] Architektur OK >> "%LOGFILE%"

:: Curl pruefen
echo [DEBUG] Pruefe curl... >> "%LOGFILE%"
where curl.exe >nul 2>&1
if !errorlevel! neq 0 goto :no_curl
echo [OK] curl.exe gefunden >> "%LOGFILE%"
set "USE_CURL=1"
goto :curl_ok

:no_curl
echo [INFO] curl.exe nicht gefunden, nutze PowerShell >> "%LOGFILE%"
set "USE_CURL=0"

:curl_ok
:: Verzeichnis erstellen
echo [DEBUG] Erstelle python-Verzeichnis... >> "%LOGFILE%"
if not exist "%PYTHON_DIR%" mkdir "%PYTHON_DIR%"
echo [DEBUG] python-Verzeichnis: %PYTHON_DIR% >> "%LOGFILE%"

:: Download
set "PY_ZIP_PATH=%BASEDIR%\%PY_ZIP%"
echo         Lade Python %PY_VERSION% herunter ^(ca. 11 MB^)...
echo [INFO] Download: %PY_URL% >> "%LOGFILE%"
echo [DEBUG] Ziel: %PY_ZIP_PATH% >> "%LOGFILE%"

if "!USE_CURL!"=="0" goto :download_ps

echo [DEBUG] Starte curl Download... >> "%LOGFILE%"
curl.exe -L --progress-bar -o "%PY_ZIP_PATH%" "%PY_URL%"
echo [DEBUG] curl beendet, errorlevel=!errorlevel! >> "%LOGFILE%"
goto :download_done

:download_ps
echo [DEBUG] Starte PowerShell Download... >> "%LOGFILE%"
powershell -ExecutionPolicy Bypass -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityPointManager]::SecurityProtocol -bor 3072; Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_ZIP_PATH%'" 2>> "%LOGFILE%"
echo [DEBUG] PowerShell beendet, errorlevel=!errorlevel! >> "%LOGFILE%"

:download_done
echo [DEBUG] Pruefe ob ZIP existiert: %PY_ZIP_PATH% >> "%LOGFILE%"
if not exist "%PY_ZIP_PATH%" goto :err_download
echo         [OK] Python heruntergeladen
echo [OK] Python heruntergeladen >> "%LOGFILE%"

:: --- Entpacken ---
echo [DEBUG] Starte Entpacken... >> "%LOGFILE%"
echo         Entpacke Python...
echo [INFO] Entpacke %PY_ZIP_PATH% nach %PYTHON_DIR% >> "%LOGFILE%"

:: PowerShell Expand-Archive (zuverlaessiger als tar fuer ZIP)
echo [DEBUG] Rufe PowerShell Expand-Archive auf... >> "%LOGFILE%"
powershell -ExecutionPolicy Bypass -NoProfile -Command "Expand-Archive -Path '%PY_ZIP_PATH%' -DestinationPath '%PYTHON_DIR%' -Force" 2>> "%LOGFILE%"
echo [DEBUG] Expand-Archive beendet, errorlevel=!errorlevel! >> "%LOGFILE%"

:: Pruefen ob python.exe existiert
echo [DEBUG] Pruefe python.exe in: %PYTHON% >> "%LOGFILE%"
if not exist "%PYTHON%" goto :err_extract
echo [OK] python.exe gefunden >> "%LOGFILE%"

:: ZIP aufraeumen
del "%PY_ZIP_PATH%" 2>nul
echo         [OK] Python %PY_VERSION% entpackt
echo [OK] Python %PY_VERSION% entpackt >> "%LOGFILE%"

:: --- _pth konfigurieren ---
echo [DEBUG] Konfiguriere _pth... >> "%LOGFILE%"
echo         Konfiguriere Python...

set "PTH_FILE="
for %%f in ("%PYTHON_DIR%\python*._pth") do set "PTH_FILE=%%f"
if not defined PTH_FILE goto :pth_done

echo [DEBUG] PTH: !PTH_FILE! >> "%LOGFILE%"
:: import site entkommentieren
powershell -ExecutionPolicy Bypass -NoProfile -Command "(Get-Content '!PTH_FILE!') -replace '^#import site','import site' | Set-Content '!PTH_FILE!'" 2>> "%LOGFILE%"
:: ../src Pfad hinzufuegen
findstr /C:"../src" "!PTH_FILE!" >nul 2>&1
if !errorlevel! neq 0 echo ../src>> "!PTH_FILE!"
echo [OK] _pth konfiguriert >> "%LOGFILE%"

:pth_done

:: --- pip installieren ---
echo [DEBUG] Starte pip-Installation... >> "%LOGFILE%"
echo         Installiere Paketmanager ^(pip^)...

set "GETPIP_PATH=%PYTHON_DIR%\get-pip.py"
echo [DEBUG] Lade get-pip.py... >> "%LOGFILE%"

if "!USE_CURL!"=="0" goto :getpip_ps

curl.exe -sL -o "%GETPIP_PATH%" "%GETPIP_URL%" 2>> "%LOGFILE%"
echo [DEBUG] get-pip curl beendet, errorlevel=!errorlevel! >> "%LOGFILE%"
goto :getpip_done

:getpip_ps
powershell -ExecutionPolicy Bypass -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityPointManager]::SecurityProtocol -bor 3072; Invoke-WebRequest -Uri '%GETPIP_URL%' -OutFile '%GETPIP_PATH%'" 2>> "%LOGFILE%"
echo [DEBUG] get-pip PowerShell beendet, errorlevel=!errorlevel! >> "%LOGFILE%"

:getpip_done
echo [DEBUG] Pruefe get-pip.py... >> "%LOGFILE%"
if not exist "%GETPIP_PATH%" goto :err_getpip

echo [DEBUG] Fuehre get-pip.py aus... >> "%LOGFILE%"
"%PYTHON%" "%GETPIP_PATH%" --no-warn-script-location -q >> "%LOGFILE%" 2>&1
if !errorlevel! neq 0 goto :err_pip

echo         [OK] Python + pip bereit
echo [OK] pip installiert >> "%LOGFILE%"

:: Sicherheitsblockade entfernen
echo [DEBUG] Unblock-File... >> "%LOGFILE%"
powershell -ExecutionPolicy Bypass -NoProfile -Command "Get-ChildItem -Path '%BASEDIR%' -Recurse -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue" >nul 2>&1

:: Python Schnelltest
echo [DEBUG] Python Schnelltest... >> "%LOGFILE%"
"%PYTHON%" -c "print('OK')" >nul 2>&1
if !errorlevel! neq 0 goto :err_python_test

for /f "tokens=*" %%v in ('"%PYTHON%" --version 2^^^>^^^&1') do set PYVER=%%v
echo         [OK] !PYVER!
echo [OK] !PYVER! >> "%LOGFILE%"
echo.
goto :install_packages

:: -------------------------------------------
:python_ready
:: Python existiert schon
:: -------------------------------------------
echo [DEBUG] Python existiert bereits >> "%LOGFILE%"
powershell -ExecutionPolicy Bypass -NoProfile -Command "Get-ChildItem -Path '%BASEDIR%' -Recurse -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue" >nul 2>&1

echo         Teste Python...
"%PYTHON%" -c "print('OK')" >nul 2>&1
if !errorlevel! neq 0 goto :err_python_existing

for /f "tokens=*" %%v in ('"%PYTHON%" --version 2^^^>^^^&1') do set PYVER=%%v
echo         [OK] !PYVER!
echo [OK] !PYVER! >> "%LOGFILE%"

:: _pth sicherstellen
set "PTH_FILE="
for %%f in ("%PYTHON_DIR%\python*._pth") do set "PTH_FILE=%%f"
if not defined PTH_FILE goto :pth_ready_done
findstr /C:"../src" "!PTH_FILE!" >nul 2>&1
if !errorlevel! neq 0 echo ../src>> "!PTH_FILE!"
:pth_ready_done

:: pip pruefen
"%PYTHON%" -m pip --version >> "%LOGFILE%" 2>&1
if !errorlevel! neq 0 call :fix_pip
echo         pip vorhanden, ueberspringe Upgrade
echo [OK] pip vorhanden >> "%LOGFILE%"
echo.

:: -------------------------------------------
:install_packages
:: SCHRITT 2: Pakete installieren
:: -------------------------------------------
echo [DEBUG] Starte Paket-Installation >> "%LOGFILE%"
echo  [2/4] Installiere Bewerbungs-Assistent...
echo [2/4] Pakete installieren... >> "%LOGFILE%"
echo.
echo         Das dauert 1-3 Minuten ^(je nach Internet^).
echo         Bitte einfach warten...
echo.
echo         Falls ein Fenster erscheint das fragt ob Python
echo         auf das Internet zugreifen darf: Bitte "Zugriff
echo         erlauben" / "Allow access" klicken!
echo.

:: Internetverbindung testen
echo [DEBUG] Teste Internet... >> "%LOGFILE%"
"%PYTHON%" -c "import urllib.request; urllib.request.urlopen('https://pypi.org/simple/', timeout=10); print('OK')" >> "%LOGFILE%" 2>&1
if !errorlevel! neq 0 goto :internet_retry

:internet_ok
echo [OK] Internet erreichbar >> "%LOGFILE%"

:: Kernpakete installieren
echo [DEBUG] Installiere Kernpakete... >> "%LOGFILE%"
echo         Installiere Kernpakete...
"%PYTHON%" -m pip install fastmcp uvicorn fastapi python-multipart httpx --no-warn-script-location >> "%LOGFILE%" 2>&1
if !errorlevel! neq 0 goto :err_packages
echo         [OK] Kernpakete installiert
echo [OK] Kernpakete installiert >> "%LOGFILE%"

:: Optionale Pakete - Scraper
echo [DEBUG] Optionale Pakete Scraper... >> "%LOGFILE%"
"%PYTHON%" -m pip install playwright beautifulsoup4 lxml --no-warn-script-location >> "%LOGFILE%" 2>&1
if !errorlevel! equ 0 (
    echo         [OK] Job-Scraper Pakete installiert
    echo [DEBUG] Installiere Playwright Browser... >> "%LOGFILE%"
    echo         Lade Browser fuer LinkedIn/XING-Suche...
    "%PYTHON%" -m playwright install chromium >> "%LOGFILE%" 2>&1
    if !errorlevel! equ 0 echo         [OK] Job-Scraper komplett installiert
    if !errorlevel! neq 0 echo         [--] Browser-Download fehlgeschlagen
)
if !errorlevel! neq 0 echo         [--] Job-Scraper uebersprungen

:: Optionale Pakete - PDF/Word
echo [DEBUG] Optionale Pakete PDF/Word... >> "%LOGFILE%"
"%PYTHON%" -m pip install python-docx fpdf2 pypdf --no-warn-script-location >> "%LOGFILE%" 2>&1
if !errorlevel! equ 0 echo         [OK] PDF/Word-Export installiert
if !errorlevel! neq 0 echo         [--] PDF/Word-Export uebersprungen

:: Optionale Pakete - E-Mail/Outlook
echo [DEBUG] Optionale Pakete E-Mail/Outlook... >> "%LOGFILE%"
:: setuptools + wheel muessen VOR extract-msg installiert werden,
:: weil extract-msg Abhaengigkeiten hat (z.B. red-black-tree-mod),
:: die aus dem Source gebaut werden und setuptools.build_meta brauchen.
:: Embeddable Python bringt setuptools/wheel NICHT mit.
echo [DEBUG] Installiere Build-Werkzeuge (setuptools, wheel)... >> "%LOGFILE%"
"%PYTHON%" -m pip install setuptools wheel --no-warn-script-location >> "%LOGFILE%" 2>&1
if !errorlevel! neq 0 (
    echo [WARN] setuptools/wheel konnten nicht installiert werden >> "%LOGFILE%"
    echo         [--] E-Mail/Outlook-Import uebersprungen
    echo             Build-Werkzeuge konnten nicht installiert werden.
    echo             .msg-Dateien ^(Outlook-Mails^) werden NICHT unterstuetzt.
    echo             .eml-Dateien und PDF-Mails funktionieren weiterhin.
    echo             Tipp: Outlook-Mails als .eml oder PDF speichern.
    goto :email_install_done
)
echo [OK] setuptools + wheel installiert >> "%LOGFILE%"
"%PYTHON%" -m pip install extract-msg icalendar --no-warn-script-location >> "%LOGFILE%" 2>&1
if !errorlevel! equ 0 (
    echo         [OK] E-Mail/Outlook-Import installiert
    echo [OK] E-Mail/Outlook-Import installiert >> "%LOGFILE%"
) else (
    echo [WARN] extract-msg/icalendar Installation fehlgeschlagen >> "%LOGFILE%"
    echo         [!!] Outlook-Mail-Import teilweise nicht verfuegbar
    echo.
    echo             Das Paket 'extract-msg' konnte nicht installiert werden.
    echo             .msg-Dateien ^(Outlook-Mails^) werden NICHT unterstuetzt.
    echo             .eml-Dateien und PDF-Mails funktionieren weiterhin.
    echo.
    echo             Workaround: Outlook-Mail oeffnen, dann:
    echo               Datei ^> Speichern unter ^> "Nur Text" ^(.eml^) oder PDF
    echo             Die gespeicherte Datei kann dann in PBP hochgeladen werden.
    echo.
    echo             Details im Log: %LOGFILE%
)
:email_install_done

:: Datenverzeichnis erstellen
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%DATA_DIR%\dokumente" mkdir "%DATA_DIR%\dokumente"
if not exist "%DATA_DIR%\export" mkdir "%DATA_DIR%\export"
if not exist "%DATA_DIR%\logs" mkdir "%DATA_DIR%\logs"
echo         [OK] Datenordner erstellt
echo [OK] Datenordner: %DATA_DIR% >> "%LOGFILE%"

:: Runtime in festen Pfad kopieren (update-sichere Pfade fuer Claude Desktop)
echo.
echo         Kopiere Runtime in festen Installationspfad...
echo [INFO] Kopiere python + src nach %DATA_DIR% >> "%LOGFILE%"

:: Laufende PBP-Prozesse beenden (verhindert "Unzulaessiger SHARE-Vorgang")
echo [DEBUG] Pruefe laufende PBP-Prozesse... >> "%LOGFILE%"
set "KILLED_PROCESSES=0"
for /f "tokens=2" %%p in ('tasklist /fi "imagename eq python.exe" /fo list 2^>nul ^| findstr /i "PID"') do (
    wmic process where "ProcessId=%%p" get CommandLine 2>nul | findstr /i "bewerbungs_assistent" >nul 2>&1
    if !errorlevel! equ 0 (
        echo [INFO] Beende PBP-Prozess PID %%p >> "%LOGFILE%"
        taskkill /pid %%p /f >nul 2>&1
        set "KILLED_PROCESSES=1"
    )
)
if "!KILLED_PROCESSES!"=="1" (
    echo         [OK] Laufende PBP-Prozesse beendet
    echo [OK] PBP-Prozesse beendet >> "%LOGFILE%"
    timeout /t 2 /nobreak >nul
)

:: python/ Ordner kopieren
echo [DEBUG] Kopiere python-Ordner... >> "%LOGFILE%"
if exist "%DATA_DIR%\python" rmdir /s /q "%DATA_DIR%\python" 2>nul
if exist "%DATA_DIR%\python" (
    echo [WARN] python-Ordner konnte nicht geloescht werden, versuche ueberschreiben >> "%LOGFILE%"
)
xcopy "%PYTHON_DIR%" "%DATA_DIR%\python\" /E /I /Q /Y >> "%LOGFILE%" 2>&1
if !errorlevel! neq 0 goto :err_copy_runtime
echo [OK] python kopiert >> "%LOGFILE%"

:: src/ Ordner kopieren
echo [DEBUG] Kopiere src-Ordner... >> "%LOGFILE%"
if not exist "%SRC_DIR%" goto :err_not_extracted
if exist "%DATA_DIR%\src" rmdir /s /q "%DATA_DIR%\src" 2>nul
xcopy "%SRC_DIR%" "%DATA_DIR%\src\" /E /I /Q /Y >> "%LOGFILE%" 2>&1
if !errorlevel! neq 0 goto :err_copy_runtime
echo [OK] src kopiert >> "%LOGFILE%"

:: Startdateien nach DATA_DIR kopieren (Dashboard starten.bat + start_dashboard.py)
echo [DEBUG] Kopiere Startdateien... >> "%LOGFILE%"
if exist "%BASEDIR%\Dashboard starten.bat" copy /Y "%BASEDIR%\Dashboard starten.bat" "%DATA_DIR%\" >> "%LOGFILE%" 2>&1
if exist "%BASEDIR%\start_dashboard.py" copy /Y "%BASEDIR%\start_dashboard.py" "%DATA_DIR%\" >> "%LOGFILE%" 2>&1
if exist "%BASEDIR%\_selftest.py" copy /Y "%BASEDIR%\_selftest.py" "%DATA_DIR%\" >> "%LOGFILE%" 2>&1
echo [OK] Startdateien kopiert >> "%LOGFILE%"

echo         [OK] Runtime installiert in %DATA_DIR%
echo [OK] Runtime installiert >> "%LOGFILE%"
echo.

:: -------------------------------------------
:: SCHRITT 3: Claude Desktop konfigurieren
:: -------------------------------------------
echo [DEBUG] Starte Claude-Konfiguration >> "%LOGFILE%"
echo  [3/4] Verbinde mit Claude Desktop...
echo [3/4] Claude Desktop... >> "%LOGFILE%"

set "CLAUDE_FOUND=0"
if exist "%LOCALAPPDATA%\Programs\claude-desktop\Claude.exe" set "CLAUDE_FOUND=1"
if exist "%LOCALAPPDATA%\AnthropicClaude\Claude.exe" set "CLAUDE_FOUND=1"
if exist "%ProgramFiles%\Claude\Claude.exe" set "CLAUDE_FOUND=1"
if exist "%LOCALAPPDATA%\Programs\Claude\Claude.exe" set "CLAUDE_FOUND=1"

if "!CLAUDE_FOUND!"=="1" goto :claude_found

echo.
echo  Claude Desktop wurde nicht gefunden.
echo  Der Bewerbungs-Assistent braucht Claude Desktop.
echo.
echo  Ich oeffne jetzt die Download-Seite.
echo    1. Lade "Claude for Windows" herunter
echo    2. Installiere es
echo    3. Erstelle ein Konto
echo.
echo  Druecke danach eine Taste um weiterzumachen.
start https://claude.ai/download
pause >nul
echo.

:claude_found
echo         [OK] Claude Desktop gefunden
echo [OK] Claude Desktop gefunden >> "%LOGFILE%"
:: Store Claude path for later opening (#24)
set "CLAUDE_EXE="
if exist "%LOCALAPPDATA%\Programs\claude-desktop\Claude.exe" set "CLAUDE_EXE=%LOCALAPPDATA%\Programs\claude-desktop\Claude.exe"
if exist "%LOCALAPPDATA%\AnthropicClaude\Claude.exe" set "CLAUDE_EXE=%LOCALAPPDATA%\AnthropicClaude\Claude.exe"
if exist "%ProgramFiles%\Claude\Claude.exe" set "CLAUDE_EXE=%ProgramFiles%\Claude\Claude.exe"
if exist "%LOCALAPPDATA%\Programs\Claude\Claude.exe" set "CLAUDE_EXE=%LOCALAPPDATA%\Programs\Claude\Claude.exe"

set "CLAUDE_DIR=%APPDATA%\Claude"
if not exist "%CLAUDE_DIR%" mkdir "%CLAUDE_DIR%"

echo [DEBUG] Starte _setup_claude.py >> "%LOGFILE%"
"%PYTHON%" "%BASEDIR%\_setup_claude.py" >> "%LOGFILE%" 2>&1
if !errorlevel! neq 0 goto :claude_config_failed
echo         [OK] Claude Desktop konfiguriert
echo [OK] Claude konfiguriert >> "%LOGFILE%"
goto :claude_config_done

:claude_config_failed
echo         [!!] Claude-Konfiguration fehlgeschlagen
echo [FEHLER] _setup_claude.py >> "%LOGFILE%"

:claude_config_done
echo.

:: -------------------------------------------
:: SCHRITT 4: Startdateien + Test
:: -------------------------------------------
echo [DEBUG] Starte Schritt 4 >> "%LOGFILE%"
echo  [4/4] Erstelle Startdateien und teste...
echo [4/4] Startdateien + Test... >> "%LOGFILE%"

:: Desktop-Verknuepfung (zeigt auf DATA_DIR - stabil auch nach ZIP-Loeschung)
powershell -ExecutionPolicy Bypass -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'PBP Bewerbungs-Portal.lnk')); $s.TargetPath='%DATA_DIR%\Dashboard starten.bat'; $s.WorkingDirectory='%DATA_DIR%'; $s.Description='PBP Dashboard'; $s.Save()" >nul 2>&1
if !errorlevel! equ 0 echo         [OK] Desktop-Verknuepfung erstellt
if !errorlevel! neq 0 echo         [--] Desktop-Verknuepfung nicht erstellt

:: Schnelltest
echo [DEBUG] Starte Schnelltest >> "%LOGFILE%"
"%PYTHON%" "%BASEDIR%\_selftest.py" >> "%LOGFILE%" 2>&1
if !errorlevel! equ 0 echo         [OK] Funktionstest bestanden
if !errorlevel! neq 0 echo         [!!] Funktionstest nicht bestanden

echo [OK] Installation abgeschlossen >> "%LOGFILE%"
echo.

:: -------------------------------------------
:: FERTIG
:: -------------------------------------------
echo.
echo  ====================================================
echo.
echo    FERTIG - Alles installiert!
echo.
echo  ====================================================
echo.
echo  WICHTIG: Claude Desktop muss im Hintergrund laufen!
echo  --------------------------------------------------------
echo  Der Bewerbungs-Assistent laeuft ALS TEIL von Claude
echo  Desktop. Ohne Claude Desktop funktioniert nichts.
echo  Claude Desktop muss IMMER im Hintergrund laufen wenn
echo  du den Bewerbungs-Assistent nutzen willst.
echo.
echo  SO GEHT ES WEITER:
echo.
echo    1. Claude Desktop starten ^(wird jetzt geoeffnet^)
echo.
echo    2. In Claude eintippen:
echo.
echo       "Ersterfassung starten"
echo.
echo       Claude fuehrt dich durch ein Gespraech und
echo       baut dein Bewerbungsprofil auf.
echo.
echo  ----------------------------------------------------
echo.
echo    TIPP: Auf deinem Desktop findest du jetzt
echo    "PBP Bewerbungs-Portal" - damit kannst du
echo    das Browser-Dashboard jederzeit oeffnen.
echo.
echo  ====================================================
echo.
echo    Deine Daten: %DATA_DIR%
echo    Installation: %BASEDIR%
echo    Log-Datei: %LOGFILE%
echo.

:: Auto-open Claude Desktop if found (#24)
if defined CLAUDE_EXE (
echo  Starte Claude Desktop...
echo [INFO] Starte Claude Desktop: !CLAUDE_EXE! >> "%LOGFILE%"
start "" "!CLAUDE_EXE!"
timeout /t 2 /nobreak >nul
echo  [OK] Claude Desktop gestartet
echo.
)

set /p OPEN_DASH="  Dashboard jetzt im Browser oeffnen? ^(j/n^): "
if /i "!OPEN_DASH!" neq "j" goto :skip_dashboard

echo.
echo  Starte Dashboard...
start "" "%DATA_DIR%\Dashboard starten.bat"
timeout /t 3 /nobreak >nul
echo  Dashboard laeuft auf http://localhost:8200
echo.

:skip_dashboard
echo  Viel Erfolg bei der Jobsuche!
echo.
echo  Druecke eine beliebige Taste zum Schliessen...
pause >nul
exit /b 0

:: ===================================================
:: FEHLERBEHANDLUNG
:: Alle Labels hier unten - AUSSERHALB von Klammern!
:: So koennen Sonderzeichen sicher in echo verwendet werden.
:: ===================================================

:err_not_extracted
echo [FEHLER] src-Ordner nicht gefunden - ZIP nicht entpackt >> "%LOGFILE%" 2>nul
echo.
echo  ****************************************************
echo  *  FEHLER: ZIP wurde nicht richtig entpackt!       *
echo  ****************************************************
echo.
echo  Der Ordner "src" fehlt. Das passiert wenn die
echo  INSTALLIEREN.bat direkt aus dem ZIP heraus gestartet
echo  wird, ohne das ZIP vorher zu entpacken.
echo.
echo  SO GEHT ES RICHTIG:
echo    1. Rechtsklick auf die heruntergeladene ZIP-Datei
echo    2. "Alle extrahieren..." / "Extract All..." waehlen
echo    3. Einen Zielordner waehlen ^(z.B. Desktop^)
echo    4. Im ENTPACKTEN Ordner die INSTALLIEREN.bat starten
echo.
echo  WICHTIG: Nicht einfach die BAT-Datei aus dem ZIP
echo  herausziehen - das ganze ZIP muss entpackt werden!
echo.
call :show_support_info
pause
exit /b 1

:err_32bit
echo [FEHLER] 32-Bit Windows >> "%LOGFILE%"
echo.
echo  FEHLER: 32-Bit Windows erkannt!
echo  Der Bewerbungs-Assistent benoetigt 64-Bit Windows.
echo.
call :show_support_info
pause
exit /b 1

:err_download
echo [FEHLER] Python-Download fehlgeschlagen >> "%LOGFILE%"
echo.
echo  FEHLER: Python konnte nicht heruntergeladen werden!
echo.
echo  Pruefe deine Internetverbindung (oeffne google.de)
echo  und starte INSTALLIEREN.bat dann nochmal.
echo.
echo  Falls eine Firewall fragt: "Zugriff erlauben" klicken.
echo  (Log: %LOGFILE%)
echo.
call :show_support_info
pause
exit /b 1

:err_extract
echo [FEHLER] python.exe nach Entpacken nicht gefunden >> "%LOGFILE%"
echo.
echo  FEHLER: Python konnte nicht entpackt werden!
echo  Versuche INSTALLIEREN.bat als Administrator auszufuehren.
echo  (Rechtsklick, "Als Administrator ausfuehren")
echo  (Log: %LOGFILE%)
echo.
call :show_support_info
pause
exit /b 1

:err_getpip
echo [FEHLER] get-pip.py fehlgeschlagen >> "%LOGFILE%"
echo.
echo  FEHLER: Paketmanager konnte nicht geladen werden!
echo  Pruefe deine Internetverbindung.
echo.
call :show_support_info
pause
exit /b 1

:err_pip
echo [FEHLER] pip install fehlgeschlagen >> "%LOGFILE%"
echo.
echo  FEHLER: Paketmanager konnte nicht installiert werden!
echo  (Log: %LOGFILE%)
echo.
call :show_support_info
pause
exit /b 1

:err_python_test
echo [FEHLER] Python-Schnelltest fehlgeschlagen >> "%LOGFILE%"
echo.
echo  FEHLER: Python funktioniert nicht!
echo  Evtl. blockiert der Virenscanner python.exe.
echo  Fuege diesen Ordner als Ausnahme hinzu: %BASEDIR%
echo.
call :show_support_info
pause
exit /b 1

:err_python_existing
echo [FEHLER] Python-Schnelltest fehlgeschlagen >> "%LOGFILE%"
echo.
echo  FEHLER: Python konnte nicht gestartet werden.
echo  TIPP: Loesche den python-Ordner und starte
echo  INSTALLIEREN.bat nochmal - Python wird dann
echo  erneut heruntergeladen.
echo  (Log: %LOGFILE%)
echo.
call :show_support_info
pause
exit /b 1

:err_packages
echo [FEHLER] Paketinstallation fehlgeschlagen >> "%LOGFILE%"
echo.
echo  FEHLER: Pakete konnten nicht installiert werden.
echo  (Log: %LOGFILE%)
echo.
call :show_support_info
pause
exit /b 1

:internet_retry
echo  HINWEIS: Internetverbindung fehlgeschlagen.
echo  Falls ein Firewall-Fenster erschien: "Zugriff erlauben"
echo  Dann druecke eine Taste zum Wiederholen.
pause >nul
"%PYTHON%" -c "import urllib.request; urllib.request.urlopen('https://pypi.org/simple/', timeout=15); print('OK')" >> "%LOGFILE%" 2>&1
if !errorlevel! neq 0 goto :err_internet
goto :internet_ok

:err_internet
echo.
echo  FEHLER: Kein Internet. Bitte pruefe WLAN/LAN.
echo  (Log: %LOGFILE%)
echo.
call :show_support_info
pause
exit /b 1

:err_copy_runtime
echo [FEHLER] Runtime-Kopie fehlgeschlagen >> "%LOGFILE%"
echo.
echo  FEHLER: Runtime konnte nicht nach %DATA_DIR% kopiert werden.
echo.
echo  Das passiert meistens weil Claude Desktop noch laeuft
echo  und Python-Dateien sperrt.
echo.
echo  LOESUNG:
echo    1. Claude Desktop BEENDEN:
echo       Rechtsklick auf das Claude-Symbol unten rechts
echo       in der Taskleiste, dann "Quit" / "Beenden"
echo    2. INSTALLIEREN.bat nochmal starten
echo.
echo  Falls das nicht hilft: Als Administrator ausfuehren.
echo  (Log: %LOGFILE%)
echo.
call :show_support_info
pause
exit /b 1

:: -------------------------------------------
:: Support-Info (wird bei jedem Fehler angezeigt)
:: -------------------------------------------
:show_support_info
echo.
echo  ----------------------------------------------------
echo  FEHLER MELDEN:
echo  Falls das Problem bestehen bleibt, melde es bitte:
echo.
echo    https://github.com/MadGapun/PBP/issues/new
echo.
echo  Bitte haenge die Log-Datei an:
echo    %LOGFILE%
echo  ----------------------------------------------------
echo.
goto :eof

:fix_pip
echo         pip wird nachinstalliert...
set "GETPIP_PATH=%PYTHON_DIR%\get-pip.py"
if not exist "!GETPIP_PATH!" curl.exe -sL -o "!GETPIP_PATH!" "%GETPIP_URL%" 2>> "%LOGFILE%"
"%PYTHON%" "!GETPIP_PATH!" --no-warn-script-location -q >> "%LOGFILE%" 2>&1
goto :eof
