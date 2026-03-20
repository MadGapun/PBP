#!/bin/bash
# ============================================================================
# Bewerbungs-Assistent — Installer für Linux
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

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Bewerbungs-Assistent — Installer v1.0     ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""
info "Projektverzeichnis: $PROJECT_DIR"

# ── 1. Python pruefen ───────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[1/6] Python pruefen...${NC}"

PYTHON=""
for cmd in python3 python; do
    if command -v $cmd &>/dev/null; then
        ver=$($cmd --version 2>&1)
        minor=$(echo "$ver" | grep -oP '3\.(\d+)' | head -1 | cut -d. -f2)
        if [ "$minor" -ge 11 ] 2>/dev/null; then
            PYTHON=$cmd
            ok "$ver"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python 3.11+ nicht gefunden!"
    echo "  Installiere: sudo apt install python3.11 python3.11-venv"
    exit 1
fi

# ── 2. venv erstellen ───────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[2/6] Virtuelle Umgebung...${NC}"

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
echo -e "${YELLOW}[3/6] Pakete installieren...${NC}"

$PYTHON -m pip install --upgrade pip -q 2>/dev/null
$PYTHON -m pip install -e "$PROJECT_DIR" -q
ok "Core installiert"

$PYTHON -m pip install -e "$PROJECT_DIR[all]" -q 2>/dev/null && \
    ok "Scraper + Dokumente installiert" || \
    warn "Optionale Pakete teilweise fehlgeschlagen"

# ── 4. Test ──────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[4/6] Funktionstest...${NC}"

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

# ── 5. Datenverzeichnis ─────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[5/6] Datenverzeichnis...${NC}"

mkdir -p "$BA_DATA_DIR"/{dokumente,export,logs}
ok "Datenverzeichnis: $BA_DATA_DIR"

# ── 6. Info ──────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[6/6] Fertig!${NC}"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Installation erfolgreich!            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Starten:"
echo -e "    ${CYAN}$VENV_DIR/bin/python -m bewerbungs_assistent${NC}  (MCP Server)"
echo -e "    ${CYAN}$VENV_DIR/bin/python test_demo.py${NC}             (Dashboard Demo)"
echo ""
echo -e "  Dashboard: ${CYAN}http://localhost:8200${NC}"
echo -e "  Daten:     $BA_DATA_DIR"
echo ""
