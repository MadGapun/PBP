#!/bin/bash
# ============================================================================
# Bewerbungs-Assistent — Deinstaller fuer macOS und Linux
# ============================================================================
# Ausfuehren: bash installer/deinstallieren.sh
# ============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓ $1${NC}"; }
warn() { echo -e "  ${YELLOW}⚠ $1${NC}"; }
fail() { echo -e "  ${RED}✗ $1${NC}"; }
info() { echo -e "  ${CYAN}→ $1${NC}"; }

OS="$(uname -s)"
case "$OS" in
    Darwin) PLATFORM="macos" ;;
    *)      PLATFORM="linux" ;;
esac

DATA_DIR="$HOME/.bewerbungs-assistent"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ "$PLATFORM" = "macos" ]; then
    CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
    # #697: der Installer bringt Chromium mit. Mehrere hundert MB, die
    # nach dem Loeschen des Projektordners liegenbleiben, ohne dass
    # irgendwo steht, dass es sie gibt (#975 Befund 3).
    PW_CACHE="$HOME/Library/Caches/ms-playwright"
else
    CLAUDE_CONFIG="$HOME/.config/Claude/claude_desktop_config.json"
    PW_CACHE="$HOME/.cache/ms-playwright"
fi

echo ""
echo -e "${RED}╔══════════════════════════════════════════════╗${NC}"
echo -e "${RED}║   PBP — Deinstallation                      ║${NC}"
echo -e "${RED}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  Was entfernt wird — jeder Schritt wird einzeln gefragt:"
echo "    - MCP-Eintrag 'bewerbungs-assistent' in Claude Desktop"
echo "    - Datenverzeichnis: $DATA_DIR (optional)"
if [ -d "$PW_CACHE" ]; then
    PW_SIZE="$(du -sh "$PW_CACHE" 2>/dev/null | cut -f1)"
    echo "    - Chromium fuer Browser-Quellen: $PW_CACHE (${PW_SIZE:-?}, optional)"
fi
echo ""
echo "  Was BLEIBT — und was du selbst loeschen musst:"
echo "    - Der Projektordner: $PROJECT_DIR"
if [ -d "$PROJECT_DIR/.venv" ]; then
    VENV_SIZE="$(du -sh "$PROJECT_DIR/.venv" 2>/dev/null | cut -f1)"
    echo "      darin .venv (${VENV_SIZE:-?}) — verschwindet mit dem Ordner"
fi
echo "    - Claude Desktop und Ollama (separat deinstallieren)"
echo ""

read -p "  Deinstallation jetzt starten? (j/n): " CONFIRM
if [ "$CONFIRM" != "j" ] && [ "$CONFIRM" != "J" ]; then
    echo ""
    echo "  Abgebrochen — nichts wurde geaendert."
    exit 0
fi

# ── 1. MCP-Eintrag entfernen ──────────────────────────────────────
echo ""
echo -e "${YELLOW}[1/3] Entferne Claude Desktop MCP-Eintrag...${NC}"

if [ -f "$CLAUDE_CONFIG" ]; then
    if python3 -c "
import json, sys
path = sys.argv[1]
with open(path, 'r') as f:
    config = json.load(f)
servers = config.get('mcpServers', {})
if 'bewerbungs-assistent' in servers:
    del servers['bewerbungs-assistent']
    with open(path, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print('removed')
else:
    print('not_found')
" "$CLAUDE_CONFIG" 2>/dev/null | grep -q "removed"; then
        ok "MCP-Eintrag entfernt"
    else
        info "MCP-Eintrag war nicht vorhanden"
    fi
else
    info "Claude-Config nicht gefunden: $CLAUDE_CONFIG"
fi

# ── 2. Datenverzeichnis ───────────────────────────────────────────
echo ""
echo -e "${YELLOW}[2/3] Datenverzeichnis...${NC}"

if [ -d "$DATA_DIR" ]; then
    echo ""
    echo "  Datenverzeichnis: $DATA_DIR"
    echo "  Enthaelt: Datenbank, Dokumente, Exporte, Logs"
    echo ""
    read -p "  Datenverzeichnis komplett loeschen? (j/n): " DELETE_DATA
    if [ "$DELETE_DATA" = "j" ] || [ "$DELETE_DATA" = "J" ]; then
        rm -rf "$DATA_DIR"
        ok "Datenverzeichnis geloescht"
    else
        ok "Datenverzeichnis bleibt erhalten: $DATA_DIR"
    fi
else
    info "Datenverzeichnis nicht gefunden: $DATA_DIR"
fi

# ── 3. Chromium-Cache (#975 Befund 3) ─────────────────────────────
# Standard ist BEHALTEN: andere Werkzeuge auf diesem Rechner koennen
# denselben Cache nutzen, und ein Deinstaller, der fremde Dinge
# mitnimmt, ist schlimmer als einer, der zu wenig entfernt.
echo ""
echo -e "${YELLOW}[3/3] Chromium fuer Browser-Quellen...${NC}"

if [ -d "$PW_CACHE" ]; then
    PW_SIZE="$(du -sh "$PW_CACHE" 2>/dev/null | cut -f1)"
    echo ""
    echo "  Cache: $PW_CACHE (${PW_SIZE:-unbekannte Groesse})"
    echo "  Achtung: andere Programme auf diesem Rechner koennen ihn"
    echo "  ebenfalls nutzen. Im Zweifel behalten."
    echo ""
    read -p "  Chromium-Cache loeschen? (j/N): " DELETE_PW
    if [ "$DELETE_PW" = "j" ] || [ "$DELETE_PW" = "J" ]; then
        rm -rf "$PW_CACHE"
        ok "Chromium-Cache geloescht"
    else
        ok "Chromium-Cache bleibt erhalten"
    fi
else
    info "Kein Chromium-Cache gefunden"
fi

# ── FERTIG ─────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Deinstallation abgeschlossen         ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  Bitte Claude Desktop einmal komplett neu starten."
echo ""
echo "  Der Projektordner ist noch da:"
echo "    $PROJECT_DIR"
echo "  Wenn du PBP nicht mehr brauchst, kannst du ihn jetzt loeschen."
echo ""
