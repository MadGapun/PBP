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
if [ "$PLATFORM" = "macos" ]; then
    CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
else
    CLAUDE_CONFIG="$HOME/.config/Claude/claude_desktop_config.json"
fi

echo ""
echo -e "${RED}╔══════════════════════════════════════════════╗${NC}"
echo -e "${RED}║   PBP — Deinstallation                      ║${NC}"
echo -e "${RED}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  Was entfernt wird:"
echo "    - MCP-Eintrag 'bewerbungs-assistent' in Claude Desktop"
echo "    - Datenverzeichnis: $DATA_DIR (optional)"
echo ""
echo "  Hinweis: Der Quellcode (dieses Verzeichnis) wird NICHT entfernt."
echo ""

read -p "  Deinstallation jetzt starten? (j/n): " CONFIRM
if [ "$CONFIRM" != "j" ] && [ "$CONFIRM" != "J" ]; then
    echo ""
    echo "  Abgebrochen — nichts wurde geaendert."
    exit 0
fi

# ── 1. MCP-Eintrag entfernen ──────────────────────────────────────
echo ""
echo -e "${YELLOW}[1/2] Entferne Claude Desktop MCP-Eintrag...${NC}"

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
echo -e "${YELLOW}[2/2] Datenverzeichnis...${NC}"

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

# ── FERTIG ─────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Deinstallation abgeschlossen         ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  Bitte Claude Desktop einmal komplett neu starten."
echo ""
