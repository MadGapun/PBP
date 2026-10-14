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

# v1.8.0 (#1219): "ja" und "yes" gelten wie "j" - sonst brach "ja" mit "Abgebrochen" ab (sicher, aber unfreundlich).
ist_ja() {
    case "$1" in
        j|J|ja|Ja|JA|y|Y|yes|Yes|YES) return 0 ;;
        *) return 1 ;;
    esac
}
# Wird gesetzt, wenn der MCP-Eintrag in der Claude-Konfiguration stehen blieb: der Schluss sagt es dann (kein gruener Kasten).
MCP_BLIEB=0

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
if ! ist_ja "$CONFIRM"; then
    echo ""
    echo "  Abgebrochen — nichts wurde geaendert."
    exit 0
fi

# ── 1. MCP-Eintrag entfernen ──────────────────────────────────────
echo ""
echo -e "${YELLOW}[1/3] Entferne Claude Desktop MCP-Eintrag...${NC}"

# v1.8.0 (#1149 Punkt 9d): vier Ausgaenge statt zwei. Bis v1.7.148 hiess "Datei nicht lesbar" dasselbe wie "kein Eintrag":
# bei kaputtem JSON stand "MCP-Eintrag war nicht vorhanden", und der Eintrag blieb stehen. Vor dem Schreiben entsteht
# eine Sicherungskopie (.pbp-backup, wie unter Windows), geschrieben wird ueber eine Zwischendatei.
PY_ENTFERNEN='
import json, os, shutil, sys
pfad = sys.argv[1]
try:
    with open(pfad, "r", encoding="utf-8-sig") as f:
        config = json.load(f)
except (OSError, ValueError):
    print("unreadable")
    sys.exit(0)
if not isinstance(config, dict):
    print("unreadable")
    sys.exit(0)
servers = config.get("mcpServers")
if not isinstance(servers, dict) or "bewerbungs-assistent" not in servers:
    print("not_found")
    sys.exit(0)
try:
    shutil.copy2(pfad, pfad + ".pbp-backup")
    del servers["bewerbungs-assistent"]
    neu = pfad + ".pbp-neu"
    with open(neu, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    os.replace(neu, pfad)
    print("removed")
except OSError:
    print("write_error")
'

if [ -f "$CLAUDE_CONFIG" ]; then
    ERGEBNIS="$(python3 -c "$PY_ENTFERNEN" "$CLAUDE_CONFIG" 2>/dev/null)" || ERGEBNIS=""
    case "$ERGEBNIS" in
        removed)
            ok "MCP-Eintrag entfernt"
            ;;
        not_found)
            info "MCP-Eintrag war nicht vorhanden"
            ;;
        unreadable)
            MCP_BLIEB=1
            warn "Claude-Konfiguration nicht lesbar (kein gueltiges JSON): $CLAUDE_CONFIG"
            echo "  Der Eintrag \"bewerbungs-assistent\" konnte deshalb NICHT entfernt werden."
            echo "  Entferne ihn in dieser Datei von Hand."
            ;;
        write_error)
            MCP_BLIEB=1
            warn "Die Claude-Konfiguration konnte nicht geschrieben werden: $CLAUDE_CONFIG"
            echo "  Der Eintrag \"bewerbungs-assistent\" ist noch da. Entferne ihn in dieser Datei von Hand."
            ;;
        *)
            MCP_BLIEB=1
            warn "Die Claude-Konfiguration konnte nicht geprueft werden (python3 nicht gefunden?)"
            echo "  Entferne den Eintrag \"bewerbungs-assistent\" in $CLAUDE_CONFIG von Hand."
            ;;
    esac
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
    if ist_ja "$DELETE_DATA"; then
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
    if ist_ja "$DELETE_PW"; then
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
if [ "$MCP_BLIEB" = "1" ]; then
    # v1.8.0 (#1219): bei stehengebliebenem Eintrag ist die Deinstallation NICHT abgeschlossen - der Schluss sagt es und nennt
    # den Handgriff (wie CLAUDE_MANUELL in DEINSTALLIEREN.bat), und der Exit-Code ist 1.
    echo -e "${YELLOW}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║   Deinstallation NICHT ganz abgeschlossen    ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  Der Eintrag \"bewerbungs-assistent\" steht noch in der Claude-Konfiguration:"
    echo "    $CLAUDE_CONFIG"
    echo "  Entferne ihn dort von Hand. Sonst meldet Claude Desktop bei jedem Start einen"
    echo "  fehlgeschlagenen MCP-Server, sobald der Projektordner geloescht ist."
    echo ""
    echo "  Danach Claude Desktop einmal komplett neu starten."
    echo ""
    echo "  Der Projektordner ist noch da:"
    echo "    $PROJECT_DIR"
    echo ""
    exit 1
fi
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
