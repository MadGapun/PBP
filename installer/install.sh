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
echo -e "${CYAN}║   PBP — Installer                           ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""
info "Plattform: $PLATFORM ($OS)"
info "Projektverzeichnis: $PROJECT_DIR"

# ── 1. Python pruefen ───────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[1/7] Python pruefen...${NC}"

PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3 python; do
    if command -v $cmd &>/dev/null; then
        ver=$($cmd --version 2>&1)
        # #1149: kein `grep -P` — das grep von macOS (BSD) kennt es nicht. Und weil die Pipe
        # mit `cut` endete, lief der Rueckfall nach `||` nie: "Python 3.11+ nicht gefunden!"
        # trotz installiertem 3.12 oder 3.13. Jetzt nur `sed`, das auf beiden Systemen gleich liest.
        minor=$(echo "$ver" | sed -n 's/^[^0-9]*3\.\([0-9][0-9]*\).*/\1/p' | head -1)
        if [ -n "$minor" ] && [ "$minor" -ge 11 ] 2>/dev/null; then
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

# Playwright-Browser (Chromium) — wird fuer stepstone, freelancermap-Fallback,
# LinkedIn/XING-Browser-Login und einige weitere Quellen gebraucht (#500).
# Ohne diesen Schritt erscheint zur Laufzeit "Executable doesn't exist".
info "Installiere Chromium fuer Browser-Quellen..."
if $PYTHON -m playwright install chromium 2>/dev/null; then
    ok "Chromium-Browser installiert"
else
    warn "Chromium-Download fehlgeschlagen — Browser-Quellen (Stepstone/Freelancermap-Fallback/LinkedIn) eingeschraenkt"
fi

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
    # #1149: unter `set -e` beendete ein fehlgeschlagenes pnpm den Installer ohne ein
    # Wort (stderr geht nach /dev/null): Datenordner und Claude-Eintrag kamen nie. Das
    # fertig gebaute Dashboard liegt dem ZIP und dem Tag bei; der Bau ist eine Zugabe.
    info "Installiere Frontend-Abhaengigkeiten..."
    if pnpm --dir "$FRONTEND_DIR" install --quiet 2>/dev/null; then
        ok "Frontend-Abhaengigkeiten installiert"
        info "Baue Frontend..."
        if pnpm --dir "$FRONTEND_DIR" run build 2>/dev/null; then
            ok "Frontend erfolgreich gebaut"
        else
            warn "Frontend-Bau fehlgeschlagen — kein Problem: das fertig gebaute Dashboard liegt bei, PBP laeuft damit"
        fi
    else
        warn "Frontend-Abhaengigkeiten liessen sich nicht installieren — kein Problem: das fertig gebaute Dashboard liegt bei, PBP laeuft damit"
    fi
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
echo -e "  Daten:     $BA_DATA_DIR"
# #975 (I11): wer installiert, soll auch den Rueckweg kennen.
echo -e "  Entfernen: DEINSTALLIEREN.command im Projektordner"
echo ""

if [ "$PLATFORM" = "macos" ]; then
    echo -e "  ${YELLOW}So geht's weiter:${NC}"
    echo -e "  1. Claude Desktop komplett beenden (Menueleiste → Claude → Beenden)"
    echo -e "  2. Claude Desktop neu starten"
    echo -e "  3. Eingeben: 'Starte die Ersterfassung'"
    echo ""
fi

# v1.7.0-beta.38 (#600): Auto-Start Dashboard + Browser oeffnen.
# Vorher musste der User manuell `start_dashboard.py` aufrufen oder
# `http://localhost:8200` selbst eintippen — das wurde uebersehen.
echo -e "  ${YELLOW}PBP-Dashboard wird gestartet...${NC}"

# --- dashboard-funktionen Anfang
# v1.8.0 (#1149 Punkt 6): Beim Update laeuft haeufig noch das Dashboard der ALTEN Fassung und haelt den Port. Der neue Start
# meldete dann "laeuft bereits", und der Health-Check bestaetigte die alte Fassung: der Installer sagte "laeuft", der Mensch
# sah weiter das Alte. Beendet wird nur, was sich als start_dashboard.py von PBP ausweist - nie der MCP-Prozess von
# Claude Desktop und nie ein fremdes Programm auf dem Port. Der Health-Check fragt /api/health und vergleicht die Fassung;
# ein fremdes Programm, das HTTP 200 liefert, gilt nicht mehr als "laeuft".
DASH_PORT="${BA_DASHBOARD_PORT:-8200}"
DASH_MUSTER='(^|/)[Pp]ython[0-9.]*[[:space:]].*start_dashboard\.py'
NEUE_FASSUNG="$(sed -n 's/^__version__[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$PROJECT_DIR/src/bewerbungs_assistent/__init__.py" 2>/dev/null | head -n 1)"

dashboard_pids() {
    command -v pgrep >/dev/null 2>&1 || return 0
    pgrep -f -i "$DASH_MUSTER" 2>/dev/null | grep -v -x "$$" || true
}

# Die Fassung, die auf dem Port als PBP antwortet - leer, wenn dort nichts oder ein anderes Programm antwortet.
dashboard_stand() {
    curl -sf --max-time 2 "http://127.0.0.1:${DASH_PORT}/api/health" 2>/dev/null \
        | grep -o '"pbp_version"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 \
        | sed 's/.*:[[:space:]]*"\(.*\)"$/\1/' || true
}

alte_dashboards_beenden() {
    local pids n=0
    pids="$(dashboard_pids)"
    if [ -z "$pids" ]; then
        return 0
    fi
    info "Ein laufendes PBP-Dashboard wird beendet, damit die neue Fassung startet"
    kill $pids 2>/dev/null || true
    while [ "$n" -lt 5 ]; do
        sleep 1
        pids="$(dashboard_pids)"
        if [ -z "$pids" ]; then
            return 0
        fi
        n=$((n + 1))
    done
    kill -9 $pids 2>/dev/null || true
    sleep 1
    return 0
}

# ok = die installierte Fassung antwortet, alt = eine andere Fassung antwortet, keins = kein PBP antwortet.
dashboard_urteil() {
    local stand="$1"
    if [ -z "$stand" ]; then
        echo keins
    elif [ -n "$NEUE_FASSUNG" ] && [ "$stand" != "$NEUE_FASSUNG" ]; then
        echo alt
    else
        echo ok
    fi
}
# --- dashboard-funktionen Ende

# Zuerst das alte Dashboard (Update), dann im Hintergrund starten
alte_dashboards_beenden
nohup "$VENV_DIR/bin/python" "$PROJECT_DIR/start_dashboard.py" \
      > /dev/null 2>&1 &
DASH_PID=$!
echo -e "    [OK] Dashboard-Prozess gestartet (PID $DASH_PID)."

# Health-Check bis der Port als PBP antwortet, max 30 Sekunden
echo -n "    Warte auf Dashboard "
DASH_STAND=""
for i in $(seq 1 30); do
    DASH_STAND="$(dashboard_stand)"
    if [ -n "$DASH_STAND" ]; then
        break
    fi
    echo -n "."
    sleep 1
done
echo ""
DASH_URTEIL="$(dashboard_urteil "$DASH_STAND")"

# Browser-Oeffnen je Plattform
open_browser() {
    local url="http://localhost:${DASH_PORT}/"
    if [ "$PLATFORM" = "macos" ]; then
        open "$url" 2>/dev/null || true
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 &
    else
        echo "    Bitte oeffne im Browser: $url"
    fi
}

if [ "$DASH_URTEIL" = "ok" ]; then
    echo -e "    [OK] Dashboard laeuft auf http://localhost:${DASH_PORT}"
    open_browser
elif [ "$DASH_URTEIL" = "alt" ]; then
    echo -e "    [!!] Auf dem Port laeuft noch PBP $DASH_STAND - installiert wurde $NEUE_FASSUNG."
    echo -e "         Meist ist das der Prozess, den Claude Desktop gestartet hat: Claude Desktop komplett beenden"
    echo -e "         und neu starten, dann zeigt das Dashboard die neue Fassung."
    open_browser
else
    echo -e "    [!!] Dashboard antwortet nicht nach 30 Sekunden."
    echo -e "         Oeffne Browser trotzdem — falls eine alte Instanz laeuft."
    open_browser
fi

echo ""
