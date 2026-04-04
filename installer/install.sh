#!/bin/bash
# ============================================================================
# Bewerbungs-Assistent — Installer fuer macOS und Linux
# ============================================================================
# Ausfuehren: bash installer/install.sh
# ============================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓ $1${NC}"; }
warn() { echo -e "  ${YELLOW}⚠ $1${NC}"; }
fail() { echo -e "  ${RED}✗ $1${NC}"; }
info() { echo -e "  ${CYAN}→ $1${NC}"; }

# Plattform erkennen
OS="$(uname -s)"
case "$OS" in
    Darwin) PLATFORM="macos" ;;
    Linux)  PLATFORM="linux" ;;
    *)      PLATFORM="unknown" ;;
esac

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Bewerbungs-Assistent — Installer v2.0     ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""
info "Plattform: $PLATFORM ($OS)"
info "Projektverzeichnis: $PROJECT_DIR"

# ── 1. Python pruefen ───────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[1/7] Python pruefen...${NC}"

PYTHON=""
for cmd in python3 python; do
    if command -v $cmd &>/dev/null; then
        ver=$($cmd --version 2>&1)
        minor=$(echo "$ver" | grep -oP '3\.(\d+)' | head -1 | cut -d. -f2 2>/dev/null || echo "$ver" | sed -n 's/.*3\.\([0-9]*\).*/\1/p')
        if [ "$minor" -ge 11 ] 2>/dev/null; then
            PYTHON=$cmd
            ok "$ver"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python 3.11+ nicht gefunden!"
    if [ "$PLATFORM" = "macos" ]; then
        echo "  Installiere mit Homebrew: brew install python@3.12"
        echo "  Oder lade Python von https://www.python.org/downloads/ herunter"
    else
        echo "  Installiere: sudo apt install python3.11 python3.11-venv"
    fi
    exit 1
fi

# ── 2. venv erstellen ───────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[2/7] Virtuelle Umgebung...${NC}"

if [ -f "$VENV_DIR/bin/python" ]; then
    ok "Existiert bereits: $VENV_DIR"
else
    info "Erstelle .venv..."
    $PYTHON -m venv "$VENV_DIR"
    ok "Erstellt"
fi
PYTHON="$VENV_DIR/bin/python"

# ── 3. Installieren ─────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[3/7] Pakete installieren...${NC}"

$PYTHON -m pip install --upgrade pip -q 2>/dev/null
$PYTHON -m pip install -e "$PROJECT_DIR" -q
ok "Core installiert"

$PYTHON -m pip install -e "$PROJECT_DIR[all]" -q 2>/dev/null && \
    ok "Scraper + Dokumente installiert" || \
    warn "Optionale Pakete teilweise fehlgeschlagen"

# ── 4. Frontend bauen ───────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[4/7] Frontend (React UI) bauen...${NC}"

FRONTEND_DIR="$PROJECT_DIR/frontend"
PNPM_OK=false

if command -v pnpm &>/dev/null; then
    PNPM_OK=true
    ok "pnpm $(pnpm --version)"
elif command -v npm &>/dev/null; then
    info "pnpm nicht gefunden, installiere via npm..."
    npm install -g pnpm 2>/dev/null && PNPM_OK=true && ok "pnpm installiert" || warn "pnpm konnte nicht installiert werden"
else
    warn "Node.js/npm nicht gefunden — Frontend wird nicht gebaut"
    echo "  Installiere Node.js:"
    if [ "$PLATFORM" = "macos" ]; then
        echo "    brew install node"
    else
        echo "    sudo apt install nodejs npm"
    fi
fi

if [ "$PNPM_OK" = true ] && [ -d "$FRONTEND_DIR" ]; then
    info "Installiere Frontend-Abhaengigkeiten..."
    pnpm --dir "$FRONTEND_DIR" install --quiet 2>/dev/null
    ok "Frontend-Abhaengigkeiten installiert"
    info "Baue Frontend..."
    pnpm --dir "$FRONTEND_DIR" run build 2>/dev/null
    ok "Frontend erfolgreich gebaut"
fi

# ── 5. Test ──────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[5/7] Funktionstest...${NC}"

export BA_DATA_DIR="${BA_DATA_DIR:-$HOME/.bewerbungs-assistent}"
$PYTHON -c "
from bewerbungs_assistent.database import Database, _gen_id
from bewerbungs_assistent.server import mcp
from bewerbungs_assistent.job_scraper import calculate_score, fit_analyse
import tempfile, shutil, os
d = tempfile.mkdtemp()
os.environ['BA_DATA_DIR'] = d
db = Database(); db.initialize()
db.save_profile({'name': 'Test'})
assert db.get_profile()['name'] == 'Test'
job = {'title': 'Python Dev', 'description': 'Python FastAPI'}
assert calculate_score(job, {'keywords_muss': ['python']}) > 0
db.close(); shutil.rmtree(d)
print('  Alle Tests bestanden!')
"
ok "Funktionstest OK"

# ── 6. Datenverzeichnis ─────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[6/7] Datenverzeichnis...${NC}"

mkdir -p "$BA_DATA_DIR"/{dokumente,export,logs}
ok "Datenverzeichnis: $BA_DATA_DIR"

# ── 7. Claude Desktop konfigurieren ─────────────────────────────────
echo ""
echo -e "${YELLOW}[7/7] Claude Desktop konfigurieren...${NC}"

if [ "$PLATFORM" = "macos" ]; then
    CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
else
    CLAUDE_CONFIG="$HOME/.config/Claude/claude_desktop_config.json"
fi

CLAUDE_DIR="$(dirname "$CLAUDE_CONFIG")"

if [ ! -d "$CLAUDE_DIR" ]; then
    # Claude Desktop scheint nicht installiert
    warn "Claude Desktop Config-Verzeichnis nicht gefunden: $CLAUDE_DIR"
    if [ "$PLATFORM" = "macos" ]; then
        echo "  Bitte Claude Desktop installieren: https://claude.ai/download"
    else
        echo "  Claude Desktop ist fuer Linux nicht offiziell verfuegbar."
        echo "  Alternative: Claude Code (CLI) mit MCP-Support."
    fi
    echo ""
    echo "  Nach Installation von Claude Desktop manuell konfigurieren:"
    echo "  Fuehre aus: $PYTHON $PROJECT_DIR/_setup_claude.py"
else
    # Claude Config schreiben
    $PYTHON "$PROJECT_DIR/_setup_claude.py"
    if [ $? -eq 0 ]; then
        ok "Claude Desktop konfiguriert"
        info "Config: $CLAUDE_CONFIG"
    else
        warn "Claude Desktop Konfiguration fehlgeschlagen"
        echo "  Manuell konfigurieren: $PYTHON $PROJECT_DIR/_setup_claude.py"
    fi
fi

# ── FERTIG ──────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Installation erfolgreich!            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Starten:"
echo -e "    ${CYAN}$VENV_DIR/bin/python -m bewerbungs_assistent${NC}  (MCP Server)"
echo -e "    ${CYAN}$VENV_DIR/bin/python start_dashboard.py${NC}       (Dashboard)"
echo ""
echo -e "  Dashboard: ${CYAN}http://localhost:8200${NC}"
echo -e "  Daten:     $BA_DATA_DIR"

if [ "$PLATFORM" = "macos" ]; then
    echo ""
    echo -e "  ${YELLOW}So geht's weiter:${NC}"
    echo -e "  1. Claude Desktop komplett beenden (Menueleiste → Claude → Beenden)"
    echo -e "  2. Claude Desktop neu starten"
    echo -e "  3. Eingeben: 'Starte den Bewerbungs-Assistenten'"
fi

echo ""
