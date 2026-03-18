#Requires -Version 5.1
# ============================================================================
# Bewerbungs-Assistent — Kompletter Installer fuer Windows
# ============================================================================
#
# Ausfuehren:
#   Rechtsklick auf install.ps1 → "Mit PowerShell ausfuehren"
#   ODER: powershell -ExecutionPolicy Bypass -File install.ps1
#
# Was dieses Script macht:
#   1. Prueft Python >= 3.11
#   2. Erstellt virtuelle Umgebung (.venv)
#   3. Installiert Bewerbungs-Assistent + alle Abhaengigkeiten
#   4. Testet ob alles funktioniert
#   5. Konfiguriert Claude Desktop (MCP Server)
#   6. Startet einen Testlauf
# ============================================================================

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "Bewerbungs-Assistent Installer"

function Write-Step($step, $total, $msg) {
    Write-Host ""
    Write-Host "[$step/$total] $msg" -ForegroundColor Yellow
    Write-Host ("-" * 50) -ForegroundColor DarkGray
}

function Write-OK($msg) { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "  ✗ $msg" -ForegroundColor Red }
function Write-Info($msg) { Write-Host "  → $msg" -ForegroundColor Cyan }

# Header
Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Bewerbungs-Assistent — Installer v1.0     ║" -ForegroundColor Cyan
Write-Host "║   KI-gestuetztes Bewerbungsmanagement       ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan

$projectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$totalSteps = 8
Write-Info "Projektverzeichnis: $projectDir"

# ── STEP 1: Python pruefen ──────────────────────────────────────────
Write-Step 1 $totalSteps "Python pruefen..."

$python = $null
$pyVersion = $null
foreach ($cmd in @("python", "python3", "py -3")) {
    try {
        $ver = & ([ScriptBlock]::Create("$cmd --version")) 2>&1
        if ($ver -match "Python 3\.(\d+)\.(\d+)") {
            $minor = [int]$Matches[1]
            if ($minor -ge 11) {
                $python = $cmd
                $pyVersion = $ver
                break
            }
        }
    } catch {}
}

if (-not $python) {
    Write-Fail "Python 3.11+ nicht gefunden!"
    Write-Host ""
    Write-Host "  Python installieren:" -ForegroundColor White
    Write-Host "  1. Oeffne https://www.python.org/downloads/" -ForegroundColor White
    Write-Host "  2. Lade Python 3.12 oder neuer herunter" -ForegroundColor White
    Write-Host "  3. WICHTIG: 'Add Python to PATH' anhaken!" -ForegroundColor Yellow
    Write-Host "  4. Installieren, dann dieses Script erneut ausfuehren" -ForegroundColor White
    Write-Host ""
    Read-Host "Druecke Enter zum Beenden"
    exit 1
}
Write-OK "$pyVersion"

# ── STEP 2: pip pruefen ─────────────────────────────────────────────
Write-Step 2 $totalSteps "pip pruefen und aktualisieren..."

try {
    & $python -m pip --version | Out-Null
    & $python -m pip install --upgrade pip --quiet 2>$null
    Write-OK "pip ist aktuell"
} catch {
    Write-Fail "pip nicht gefunden! Versuche: $python -m ensurepip"
    Read-Host "Druecke Enter zum Beenden"
    exit 1
}

# ── STEP 3: Virtuelle Umgebung erstellen ─────────────────────────────
Write-Step 3 $totalSteps "Virtuelle Umgebung erstellen..."

$venvPath = Join-Path $projectDir ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

if (Test-Path $venvPython) {
    Write-OK "Virtuelle Umgebung existiert bereits: $venvPath"
} else {
    Write-Info "Erstelle .venv in $projectDir ..."
    & $python -m venv $venvPath
    if (-not (Test-Path $venvPython)) {
        Write-Fail "Konnte .venv nicht erstellen!"
        exit 1
    }
    Write-OK "Virtuelle Umgebung erstellt"
}

# Ab jetzt venv-Python verwenden
$python = $venvPython

# ── STEP 4: Projekt installieren ────────────────────────────────────
Write-Step 4 $totalSteps "Bewerbungs-Assistent installieren..."

Write-Info "Installiere Core-Pakete..."
& $python -m pip install --upgrade pip --quiet 2>$null
& $python -m pip install -e "$projectDir" --quiet
Write-OK "Core installiert (fastmcp, fastapi, uvicorn, httpx)"

Write-Info "Installiere optionale Pakete (Scraper + Dokumente)..."
try {
    & $python -m pip install -e "$projectDir[all]" --quiet
    Write-OK "Scraper-Pakete installiert (playwright, beautifulsoup4, lxml)"
    Write-OK "Dokument-Pakete installiert (pypdf, python-docx)"
} catch {
    Write-Warn "Optionale Pakete teilweise fehlgeschlagen (nicht kritisch)"
}

Write-Info "Installiere Playwright Browser..."
try {
    & $python -m playwright install chromium 2>$null
    Write-OK "Chromium Browser fuer LinkedIn-Scraping installiert"
} catch {
    Write-Warn "Playwright-Browser nicht installiert (LinkedIn-Suche deaktiviert)"
}

# ── STEP 5: Frontend bauen ──────────────────────────────────────────
Write-Step 5 $totalSteps "Frontend (React UI) bauen..."

$frontendDir = Join-Path $projectDir "frontend"
$pnpmOK = $false
try {
    $pnpmVer = & pnpm --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $pnpmOK = $true
        Write-OK "pnpm Version $pnpmVer"
    }
} catch {}

if (-not $pnpmOK) {
    Write-Warn "pnpm nicht gefunden. Versuche Installation via npm..."
    try {
        & npm install -g pnpm
        $pnpmVer = & pnpm --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $pnpmOK = $true
            Write-OK "pnpm erfolgreich installiert (Version $pnpmVer)"
        }
    } catch {
        # Let's see if npm is installed
        try {
            & npm --version 2>&1 | Out-Null
            Write-Warn "pnpm konnte nicht global installiert werden. Bitte 'npm install -g pnpm' manuell ausfuehren und Installer neu starten."
        } catch {
            Write-Warn "Node.js und/oder npm scheinen nicht installiert zu sein. Das Frontend kann nicht gebaut werden."
            Write-Warn "Bitte Node.js (LTS) von https://nodejs.org/ herunterladen und installieren."
        }
        Write-Fail "Frontend-Build uebersprungen. Das UI wird nicht verfuegbar sein."
    }
}

if ($pnpmOK) {
    Write-Info "Installiere Frontend-Abhaengigkeiten (pnpm install)..."
    & pnpm --dir $frontendDir install --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "pnpm install fehlgeschlagen!"
        Read-Host "Druecke Enter zum Beenden"
        exit 1
    }
    Write-OK "Frontend-Abhaengigkeiten installiert."

    Write-Info "Baue Frontend (pnpm run build)..."
    & pnpm --dir $frontendDir run build
     if ($LASTEXITCODE -ne 0) {
        Write-Fail "pnpm run build fehlgeschlagen!"
        Read-Host "Druecke Enter zum Beenden"
        exit 1
    }
    Write-OK "Frontend erfolgreich gebaut."
}


# ── STEP 6: Funktionstest ────────────────────────────────────────────
Write-Step 6 $totalSteps "Funktionstest..."

$testScript = @"
import sys
errors = []

# Test 1: Core imports
try:
    from bewerbungs_assistent import main
    from bewerbungs_assistent.database import Database, _gen_id
    from bewerbungs_assistent.dashboard import app
    from bewerbungs_assistent.server import mcp
    print("  Core-Module: OK")
except Exception as e:
    errors.append(f"Core-Import: {e}")
    print(f"  Core-Module: FEHLER - {e}")

# Test 2: Database
try:
    import tempfile, os
    tmpdir = tempfile.mkdtemp()
    os.environ["BA_DATA_DIR"] = tmpdir
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    p = db.get_profile()
    assert p["name"] == "Test"
    db.close()
    import shutil
    shutil.rmtree(tmpdir)
    print("  Datenbank: OK")
except Exception as e:
    errors.append(f"Datenbank: {e}")
    print(f"  Datenbank: FEHLER - {e}")

# Test 3: Scoring
try:
    from bewerbungs_assistent.job_scraper import calculate_score, fit_analyse
    job = {"title": "Python Dev", "description": "Python FastAPI"}
    crit = {"keywords_muss": ["python"], "keywords_plus": ["fastapi"]}
    s = calculate_score(job, crit)
    assert s > 0
    a = fit_analyse(job, crit)
    assert a["total_score"] > 0
    print("  Scoring: OK")
except Exception as e:
    errors.append(f"Scoring: {e}")
    print(f"  Scoring: FEHLER - {e}")

# Test 4: Optional - Scraper
try:
    from bewerbungs_assistent.job_scraper.bundesagentur import search_bundesagentur
    print("  Job-Scraper: OK")
except:
    print("  Job-Scraper: nicht verfuegbar (optional)")

# Test 5: Optional - Docs
try:
    import pypdf, docx
    print("  PDF/DOCX-Import: OK")
except:
    print("  PDF/DOCX-Import: nicht verfuegbar (optional)")

if errors:
    print(f"\n  {len(errors)} Fehler gefunden!")
    sys.exit(1)
else:
    print("\n  Alle Tests bestanden!")
    sys.exit(0)
"@

$testFile = [System.IO.Path]::GetTempFileName() + ".py"
$testScript | Set-Content $testFile -Encoding UTF8
& $python $testFile
$testOK = $LASTEXITCODE -eq 0
Remove-Item $testFile -ErrorAction SilentlyContinue

if (-not $testOK) {
    Write-Fail "Funktionstest fehlgeschlagen!"
    Write-Host "  Bitte melde den Fehler." -ForegroundColor Yellow
    Read-Host "Druecke Enter zum Beenden"
    exit 1
}
Write-OK "Alle Funktionen getestet"

# ── STEP 7: Claude Desktop konfigurieren ────────────────────────────
Write-Step 7 $totalSteps "Claude Desktop konfigurieren..."

$claudeConfig = "$env:APPDATA\Claude\claude_desktop_config.json"
$dataDir = "$env:LOCALAPPDATA\BewerbungsAssistent"

# Datenverzeichnis erstellen
foreach ($sub in @("", "dokumente", "export", "logs")) {
    $dir = Join-Path $dataDir $sub
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}
Write-OK "Datenverzeichnis: $dataDir"

# Claude Config lesen oder erstellen
$config = @{ mcpServers = @{} }
if (Test-Path $claudeConfig) {
    try {
        $raw = Get-Content $claudeConfig -Raw -Encoding UTF8
        $config = $raw | ConvertFrom-Json
        if (-not $config.mcpServers) {
            $config | Add-Member -NotePropertyName "mcpServers" -NotePropertyValue @{} -Force
        }
        Write-Info "Bestehende Claude-Konfiguration erweitert"
    } catch {
        Write-Warn "Konnte bestehende Config nicht lesen, erstelle neue"
    }
}

# Runtime in festen Pfad kopieren (update-sicher)
Write-Info "Kopiere Runtime in festen Installationspfad..."
$destPython = Join-Path $dataDir "python"
$destSrc = Join-Path $dataDir "src"

# .venv kopieren als python/
if (Test-Path $destPython) { Remove-Item $destPython -Recurse -Force }
Copy-Item -Path (Join-Path $projectDir ".venv") -Destination $destPython -Recurse
Write-OK "Python-Umgebung kopiert"

# src/ kopieren
if (Test-Path $destSrc) { Remove-Item $destSrc -Recurse -Force }
Copy-Item -Path (Join-Path $projectDir "src") -Destination $destSrc -Recurse
Write-OK "Source-Code kopiert"

# MCP Server eintragen — feste Pfade unter %LOCALAPPDATA%\BewerbungsAssistent
$fixedPython = Join-Path $destPython "Scripts\python.exe"
$serverModule = "bewerbungs_assistent"
$mcpEntry = @{
    command = $fixedPython
    args = @("-m", $serverModule)
    env = @{
        BA_DATA_DIR = $dataDir
        PYTHONPATH = $destSrc
    }
}
$config.mcpServers | Add-Member -NotePropertyName "bewerbungs-assistent" -NotePropertyValue $mcpEntry -Force

# Config speichern
$configDir = Split-Path $claudeConfig
New-Item -ItemType Directory -Path $configDir -Force | Out-Null
$config | ConvertTo-Json -Depth 10 | Set-Content $claudeConfig -Encoding UTF8
Write-OK "Claude Desktop MCP-Konfiguration geschrieben"
Write-Info "Config: $claudeConfig"

# ── STEP 8: Dashboard testen ────────────────────────────────────────
Write-Step 8 $totalSteps "Dashboard-Test..."

$dashTest = @"
import os, sys, threading, time, urllib.request
os.environ["BA_DATA_DIR"] = r"$dataDir"

from bewerbungs_assistent.database import Database
from bewerbungs_assistent.dashboard import app, start_dashboard
import uvicorn

db = Database()
db.initialize()

# Start dashboard in thread
def run():
    uvicorn.run(app, host="127.0.0.1", port=5173, log_level="error")

import bewerbungs_assistent.dashboard as dash
dash._db = db
t = threading.Thread(target=run, daemon=True)
t.start()
time.sleep(2)

try:
    resp = urllib.request.urlopen("http://127.0.0.1:5173/api/status", timeout=5)
    data = resp.read().decode()
    print(f"  Dashboard erreichbar auf http://localhost:5173")
    print(f"  Status: {data[:100]}")
    sys.exit(0)
except Exception as e:
    print(f"  Dashboard-Test fehlgeschlagen: {e}")
    sys.exit(1)
"@

$dashFile = [System.IO.Path]::GetTempFileName() + ".py"
$dashTest | Set-Content $dashFile -Encoding UTF8
& $python $dashFile
$dashOK = $LASTEXITCODE -eq 0
Remove-Item $dashFile -ErrorAction SilentlyContinue

if ($dashOK) {
    Write-OK "Dashboard funktioniert auf http://localhost:5173"
} else {
    Write-Warn "Dashboard-Test fehlgeschlagen (nicht kritisch, MCP funktioniert trotzdem)"
}

# ── FERTIG ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║         Installation erfolgreich!            ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Projektverzeichnis:  $projectDir" -ForegroundColor White
Write-Host "  Daten:               $dataDir" -ForegroundColor White
Write-Host "  Claude Config:       $claudeConfig" -ForegroundColor White
Write-Host "  Dashboard:           http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "  So geht's weiter:" -ForegroundColor Yellow
Write-Host "  1. Claude Desktop komplett beenden (Tray-Icon → Beenden)" -ForegroundColor White
Write-Host "  2. Claude Desktop neu starten" -ForegroundColor White
Write-Host "  3. Eingeben: 'Starte den Bewerbungs-Assistenten'" -ForegroundColor White
Write-Host "     Oder: 'Ersterfassung starten' fuer gefuehrte Profil-Erstellung" -ForegroundColor White
Write-Host ""
Write-Host "  Dashboard jetzt oeffnen?" -ForegroundColor Yellow
$openBrowser = Read-Host "  (j/n)"
if ($openBrowser -eq "j" -or $openBrowser -eq "J") {
    Start-Process "http://localhost:5173"
}

Write-Host ""
Read-Host "Druecke Enter zum Beenden"
