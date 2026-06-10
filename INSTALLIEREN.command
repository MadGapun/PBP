#!/bin/bash
# ============================================================================
# PBP — Persoenliches Bewerbungs-Portal
# Doppelklick-Installer fuer macOS
# ============================================================================
# Einfach doppelklicken — kein Terminal-Wissen noetig.
# ============================================================================

set -e
cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
export BA_DATA_DIR="${BA_DATA_DIR:-$HOME/.bewerbungs-assistent}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓ $1${NC}"; }
warn() { echo -e "  ${YELLOW}⚠ $1${NC}"; }
fail() { echo -e "  ${RED}✗ $1${NC}"; exit 1; }
info() { echo -e "  ${CYAN}→ $1${NC}"; }

clear
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  PBP — Persoenliches Bewerbungs-Portal          ║${NC}"
echo -e "${CYAN}║  macOS Installer                                ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# Erkennen ob Erstinstallation oder Update
if [ -f "$VENV_DIR/bin/python" ]; then
    MODE="update"
    info "Bestehende Installation erkannt — Update-Modus"
else
    MODE="install"
    info "Erstinstallation"
fi

# ── 1. Python pruefen ──────────────────────────────────────────
echo ""
echo -e "${YELLOW}[1/6] Python pruefen...${NC}"

PYTHON=""
for cmd in python3 python; do
    if command -v $cmd &>/dev/null; then
        ver=$($cmd --version 2>&1)
        minor=$(echo "$ver" | sed -n 's/.*3\.\([0-9]*\).*/\1/p')
        if [ -n "$minor" ] && [ "$minor" -ge 11 ] 2>/dev/null; then
            PYTHON=$cmd
            ok "$ver"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo -e "  ${RED}Python 3.11 oder neuer wird benoetigt.${NC}"
    echo ""
    echo -e "  ${BOLD}So installierst du Python:${NC}"
    echo ""
    echo -e "  Option 1 — Homebrew (empfohlen):"
    echo -e "    ${CYAN}brew install python@3.12${NC}"
    echo ""
    echo -e "  Option 2 — python.org:"
    echo -e "    Lade Python von ${CYAN}https://www.python.org/downloads/${NC}"
    echo ""
    echo -e "  Danach dieses Skript erneut doppelklicken."
    echo ""
    read -p "  Druecke Enter zum Schliessen..."
    exit 1
fi

# ── 2. Virtuelle Umgebung ──────────────────────────────────────
echo ""
echo -e "${YELLOW}[2/6] Virtuelle Umgebung...${NC}"

if [ "$MODE" = "install" ]; then
    info "Erstelle .venv..."
    $PYTHON -m venv "$VENV_DIR"
    ok "Erstellt"
else
    ok "Existiert bereits"
fi
PYTHON="$VENV_DIR/bin/python"

# ── 3. Pakete installieren ─────────────────────────────────────
echo ""
echo -e "${YELLOW}[3/6] Pakete installieren...${NC}"

$PYTHON -m pip install --upgrade pip -q 2>/dev/null
$PYTHON -m pip install -e "$PROJECT_DIR" -q
ok "Core installiert"

$PYTHON -m pip install -e "$PROJECT_DIR[all]" -q 2>/dev/null && \
    ok "Alle Module installiert" || \
    warn "Optionale Module teilweise fehlgeschlagen (kein Problem)"

# #697: Playwright-Chromium wie in installer/install.sh — ohne diesen
# Schritt erscheint zur Laufzeit "Executable doesn't exist".
info "Installiere Chromium fuer Browser-Quellen..."
if $PYTHON -m playwright install chromium 2>/dev/null; then
    ok "Chromium-Browser installiert"
else
    warn "Chromium-Download fehlgeschlagen — Browser-Quellen eingeschraenkt, Rest funktioniert"
fi

# ── 4. Frontend bauen ──────────────────────────────────────────
echo ""
echo -e "${YELLOW}[4/6] Dashboard (React UI) bauen...${NC}"

FRONTEND_DIR="$PROJECT_DIR/frontend"
PNPM_OK=false

if command -v pnpm &>/dev/null; then
    PNPM_OK=true
elif command -v npm &>/dev/null; then
    info "Installiere pnpm..."
    npm install -g pnpm 2>/dev/null && PNPM_OK=true || true
fi

if [ "$PNPM_OK" = true ] && [ -d "$FRONTEND_DIR" ]; then
    pnpm --dir "$FRONTEND_DIR" install --quiet 2>/dev/null
    pnpm --dir "$FRONTEND_DIR" run build 2>/dev/null
    ok "Dashboard gebaut"
elif command -v node &>/dev/null; then
    warn "pnpm nicht verfuegbar — ueberspringe Frontend-Build"
else
    warn "Node.js nicht installiert — Dashboard-Build uebersprungen"
    echo "  Installiere mit: ${CYAN}brew install node${NC}"
fi

# ── 5. Datenverzeichnis ───────────────────────────────────────
echo ""
echo -e "${YELLOW}[5/6] Datenverzeichnis...${NC}"

mkdir -p "$BA_DATA_DIR"/{dokumente,export,logs}
ok "$BA_DATA_DIR"

# ── 6. Claude Desktop konfigurieren ──────────────────────────
echo ""
echo -e "${YELLOW}[6/6] Claude Desktop konfigurieren...${NC}"

CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
CLAUDE_DIR="$(dirname "$CLAUDE_CONFIG")"

if [ -d "$CLAUDE_DIR" ]; then
    $PYTHON "$PROJECT_DIR/_setup_claude.py"
    if [ $? -eq 0 ]; then
        ok "Claude Desktop konfiguriert"
    else
        warn "Konfiguration fehlgeschlagen — manuell ausfuehren: $PYTHON _setup_claude.py"
    fi
else
    warn "Claude Desktop nicht installiert"
    echo "  Lade Claude Desktop: ${CYAN}https://claude.ai/download${NC}"
    echo "  Nach der Installation dieses Skript erneut doppelklicken."
fi

# ── Fertig ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
if [ "$MODE" = "install" ]; then
echo -e "${GREEN}║         Installation erfolgreich!                ║${NC}"
else
echo -e "${GREEN}║         Update erfolgreich!                     ║${NC}"
fi
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

if [ -d "$CLAUDE_DIR" ]; then
    echo -e "  ${BOLD}So geht's weiter:${NC}"
    echo ""
    echo -e "  1. Claude Desktop beenden (Menueleiste → Claude → Beenden)"
    echo -e "  2. Claude Desktop neu starten"
    echo -e "  3. Eintippen: ${CYAN}Starte den Bewerbungs-Assistenten${NC}"
    echo ""
fi

# v1.7.0-beta.38 (#600): Auto-Start Dashboard + Browser oeffnen
echo -e "  ${BOLD}PBP-Dashboard wird gestartet...${NC}"

# Dashboard im Hintergrund starten
DASH_LAUNCHER="$PROJECT_DIR/Dashboard starten.command"
if [ -f "$DASH_LAUNCHER" ]; then
    chmod +x "$DASH_LAUNCHER" 2>/dev/null
    nohup "$DASH_LAUNCHER" > /dev/null 2>&1 &
    echo -e "    [OK] Dashboard-Prozess gestartet."
else
    echo -e "    [!!] Dashboard-Launcher nicht gefunden: $DASH_LAUNCHER"
fi

# Health-Check bis Port 8200 antwortet, max 30 Sekunden
echo -n "    Warte auf Dashboard auf http://localhost:8200 "
DASH_OK=0
for i in $(seq 1 30); do
    if curl -sf --max-time 1 http://localhost:8200/ -o /dev/null 2>/dev/null; then
        DASH_OK=1
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

if [ "$DASH_OK" = "1" ]; then
    echo -e "    [OK] Dashboard laeuft. Oeffne Browser..."
    open "http://localhost:8200/"
else
    echo -e "    [!!] Dashboard antwortet nicht nach 30 Sekunden."
    echo -e "         Oeffne Browser trotzdem — falls eine alte Instanz laeuft."
    open "http://localhost:8200/" 2>/dev/null || true
fi

echo ""
echo -e "  ${CYAN}Daten:${NC}     $BA_DATA_DIR"
echo -e "  ${CYAN}Projekt:${NC}   $PROJECT_DIR"
echo ""
read -p "  Druecke Enter zum Schliessen..."
