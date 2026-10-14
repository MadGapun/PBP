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
for cmd in python3.13 python3.12 python3.11 python3 python; do
    if command -v $cmd &>/dev/null; then
        ver=$($cmd --version 2>&1)
        # #1149: der Ausdruck war `s/.*3\.\([0-9]*\).*/\1/p`. Das `.*` greift so weit wie moeglich und
        # nimmt damit das LETZTE "3." im Text: bei "Python 3.13.5" die "3.5" statt der "3.13" —
        # jede Python-3.13-Fassung galt als zu alt (minor=5), obwohl 3.13 neuer ist als die
        # verlangte 3.11. Jetzt am Anfang verankert: Zahl nach dem ersten "3.".
        minor=$(echo "$ver" | sed -n 's/^[^0-9]*3\.\([0-9][0-9]*\).*/\1/p' | head -1)
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
    "$PYTHON" -m venv "$VENV_DIR"
    ok "Erstellt"
else
    ok "Existiert bereits"
fi
PYTHON="$VENV_DIR/bin/python"

# ── 3. Pakete installieren ─────────────────────────────────────
echo ""
echo -e "${YELLOW}[3/6] Pakete installieren...${NC}"

# #1216: "$PYTHON" in Anfuehrungszeichen - ein Leerzeichen im Ordnernamen (macOS: "PBP-1.8.0 2") liess den Befehl zerfallen,
# und unter `set -e` endete der Installer ohne ein Wort. #1219: ein gescheitertes pip-Update (kein Netz) beendet ihn nicht mehr.
"$PYTHON" -m pip install --upgrade pip -q 2>/dev/null || warn "pip liess sich nicht aktualisieren - kein Problem"
"$PYTHON" -m pip install -e "$PROJECT_DIR" -q
ok "Core installiert"

"$PYTHON" -m pip install -e "$PROJECT_DIR[all]" -q 2>/dev/null && \
    ok "Alle Module installiert" || \
    warn "Optionale Module teilweise fehlgeschlagen (kein Problem)"

# #697: Playwright-Chromium wie in installer/install.sh — ohne diesen
# Schritt erscheint zur Laufzeit "Executable doesn't exist".
info "Installiere Chromium fuer Browser-Quellen..."
if "$PYTHON" -m playwright install chromium 2>/dev/null; then
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
    # #1149: unter `set -e` beendete ein fehlgeschlagenes pnpm den Installer ohne ein
    # Wort (stderr geht nach /dev/null): Datenordner und Claude-Eintrag kamen nie. Das
    # fertig gebaute Dashboard liegt dem ZIP bei; der Bau ist eine Zugabe.
    if pnpm --dir "$FRONTEND_DIR" install --quiet 2>/dev/null && pnpm --dir "$FRONTEND_DIR" run build 2>/dev/null; then
        ok "Dashboard gebaut"
    else
        warn "Dashboard-Bau fehlgeschlagen — kein Problem: das fertig gebaute Dashboard liegt bei, PBP laeuft damit"
    fi
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
    # v1.8.0 (#1219): `if` statt `$?` - unter `set -e` beendete ein Fehlschlag das Skript an dieser Stelle, und der Zweig
    # darunter lief nie. Die Ausgabe wird gelesen: eine unlesbare Konfiguration wird ersetzt (mit Kopie), und das gehoert in den Schluss.
    if SETUP_AUSGABE="$("$PYTHON" "$PROJECT_DIR/_setup_claude.py" 2>&1)"; then
        printf '%s\n' "$SETUP_AUSGABE"
        ok "Claude Desktop konfiguriert"
    else
        printf '%s\n' "$SETUP_AUSGABE"
        CLAUDE_FEHLER=1
        warn "Konfiguration fehlgeschlagen — manuell ausfuehren: \"$PYTHON\" \"$PROJECT_DIR/_setup_claude.py\""
    fi
    CLAUDE_KOPIE="$(printf '%s\n' "$SETUP_AUSGABE" | sed -n 's/.*Kopie gesichert: //p' | head -n 1)"
else
    warn "Claude Desktop nicht installiert"
    echo "  Lade Claude Desktop: ${CYAN}https://claude.ai/download${NC}"
    echo "  Nach der Installation dieses Skript erneut doppelklicken."
fi

# ── Fertig ─────────────────────────────────────────────────────
echo ""
if [ "${CLAUDE_FEHLER:-0}" = "1" ]; then
    # #1219: keine gruene Erfolgsmeldung, wenn Claude Desktop nicht eingerichtet werden konnte
    echo -e "${YELLOW}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║     Installiert - Claude Desktop fehlt noch      ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════════╝${NC}"
else
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
if [ "$MODE" = "install" ]; then
echo -e "${GREEN}║         Installation erfolgreich!                ║${NC}"
else
echo -e "${GREEN}║         Update erfolgreich!                     ║${NC}"
fi
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
fi
echo ""
if [ -n "${CLAUDE_KOPIE:-}" ]; then
    echo -e "  ${YELLOW}⚠ Deine bisherige Claude-Konfiguration war nicht lesbar und wurde ersetzt.${NC}"
    echo "    Die alte Datei liegt als Kopie vor: $CLAUDE_KOPIE"
    echo "    Andere MCP-Server musst du von dort zurueckkopieren."
    echo ""
fi

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

# --- dashboard-funktionen Anfang
# v1.8.0 (#1149 Punkt 6): Beim Update laeuft haeufig noch das Dashboard der ALTEN Fassung und haelt den Port. Der neue Start
# meldete dann "laeuft bereits", und der Health-Check bestaetigte die alte Fassung: der Installer sagte "laeuft", der Mensch
# sah weiter das Alte. Beendet wird nur, was sich als start_dashboard.py von PBP ausweist - nie der MCP-Prozess von
# Claude Desktop und nie ein fremdes Programm auf dem Port. Der Health-Check fragt /api/health und vergleicht die Fassung;
# ein fremdes Programm, das HTTP 200 liefert, gilt nicht mehr als "laeuft".
# v1.8.0 (#1218): Der Name allein traf auch ein FREMDES start_dashboard.py und jeden Testlauf, der ihn als Argument traegt
# (`pytest tests/test_start_dashboard.py`). Das Muster verlangt jetzt ein Wort- oder Pfadende davor, und ein Prozess, dessen
# Skript NACHWEISLICH nicht neben einem PBP-Quellbaum liegt, bleibt unberuehrt (`skript_ist_fremd`).
DASH_PORT="${BA_DASHBOARD_PORT:-8200}"
DASH_MUSTER='(^|/)[Pp]ython[0-9.]*[[:space:]](.*[[:space:]/])?start_dashboard\.py'
NEUE_FASSUNG="$(sed -n 's/^__version__[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$PROJECT_DIR/src/bewerbungs_assistent/__init__.py" 2>/dev/null | head -n 1)"

# Gehoert das Skript in dieser Befehlszeile NACHWEISLICH nicht zu PBP? Fremd heisst: ein absoluter Pfad, die Datei ist da,
# und daneben liegt weder ein Quellbaum (src/bewerbungs_assistent) noch der Programmordner der Auto-Update-Fassung
# (versions). Ein relativer oder nicht lesbarer Pfad gilt NICHT als fremd: dann bleibt es beim Verhalten aus #1149 Punkt 6.
# Die Befehlszeile traegt den Pfad samt Leerzeichen ("PBP-1.8.0 2"): von links wird Wort fuer Wort gekuerzt, bis der Rest
# eine Datei ist.
skript_ist_fremd() {
    local kandidat="$1" ordner
    case "$kandidat" in
        *start_dashboard.py*) kandidat="${kandidat%%start_dashboard.py*}start_dashboard.py" ;;
        *) return 1 ;;
    esac
    while [ -n "$kandidat" ]; do
        case "$kandidat" in
            /*)
                if [ -f "$kandidat" ] && [ "${kandidat##*/}" = "start_dashboard.py" ]; then
                    ordner="${kandidat%/*}"
                    if [ -d "$ordner/src/bewerbungs_assistent" ] || [ -d "$ordner/versions" ]; then
                        return 1
                    fi
                    return 0
                fi
                ;;
        esac
        case "$kandidat" in
            *[[:space:]]*) kandidat="${kandidat#*[[:space:]]}" ;;
            *) return 1 ;;
        esac
    done
    return 1
}

dashboard_pids() {
    command -v pgrep >/dev/null 2>&1 || return 0
    local pid zeile
    for pid in $(pgrep -f -i "$DASH_MUSTER" 2>/dev/null | grep -v -x "$$" || true); do
        zeile="$(ps -p "$pid" -o args= 2>/dev/null || true)"
        if skript_ist_fremd "$zeile"; then
            continue
        fi
        echo "$pid"
    done
    return 0
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

# ok = die installierte Fassung antwortet, alt = eine andere Fassung antwortet, keins = kein PBP antwortet,
# unbekannt = PBP antwortet, aber die installierte Fassung liess sich nicht lesen (#1220): dann gilt NICHTS als "ok".
dashboard_urteil() {
    local stand="$1"
    if [ -z "$stand" ]; then
        echo keins
    elif [ -z "$NEUE_FASSUNG" ]; then
        echo unbekannt
    elif [ "$stand" != "$NEUE_FASSUNG" ]; then
        echo alt
    else
        echo ok
    fi
}
# --- dashboard-funktionen Ende

# Zuerst das alte Dashboard (Update), dann im Hintergrund starten
alte_dashboards_beenden
DASH_LAUNCHER="$PROJECT_DIR/Dashboard starten.command"
if [ -f "$DASH_LAUNCHER" ]; then
    chmod +x "$DASH_LAUNCHER" 2>/dev/null
    nohup "$DASH_LAUNCHER" > /dev/null 2>&1 &
    echo -e "    [OK] Dashboard-Prozess gestartet."
else
    echo -e "    [!!] Dashboard-Launcher nicht gefunden: $DASH_LAUNCHER"
fi

# Health-Check bis der Port als PBP antwortet, max 30 Sekunden
echo -n "    Warte auf Dashboard auf http://localhost:${DASH_PORT} "
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

if [ "$DASH_URTEIL" = "ok" ]; then
    echo -e "    [OK] Dashboard laeuft. Oeffne Browser..."
    open "http://localhost:${DASH_PORT}/"
elif [ "$DASH_URTEIL" = "unbekannt" ]; then
    echo -e "    [!!] Auf dem Port antwortet PBP $DASH_STAND - ob das die neue Fassung ist, liess sich nicht pruefen"
    echo -e "         (die installierte Fassung war nicht lesbar). Die Versionsnummer steht unten links im Dashboard."
    open "http://localhost:${DASH_PORT}/" 2>/dev/null || true
elif [ "$DASH_URTEIL" = "alt" ]; then
    echo -e "    [!!] Auf dem Port laeuft noch PBP $DASH_STAND - installiert wurde $NEUE_FASSUNG."
    echo -e "         Meist ist das der Prozess, den Claude Desktop gestartet hat: Claude Desktop komplett beenden"
    echo -e "         und neu starten, dann zeigt das Dashboard die neue Fassung."
    open "http://localhost:${DASH_PORT}/" 2>/dev/null || true
else
    echo -e "    [!!] Dashboard antwortet nicht nach 30 Sekunden."
    echo -e "         Oeffne Browser trotzdem — falls eine alte Instanz laeuft."
    open "http://localhost:${DASH_PORT}/" 2>/dev/null || true
fi

echo ""
echo -e "  ${CYAN}Daten:${NC}     $BA_DATA_DIR"
echo -e "  ${CYAN}Projekt:${NC}   $PROJECT_DIR"
# #975 (I11): Symmetrie zum Windows-Installer — wer installiert,
# soll auch wissen, wo der Rueckweg liegt.
echo -e "  ${CYAN}Entfernen:${NC} DEINSTALLIEREN.command in diesem Ordner"
echo ""
read -p "  Druecke Enter zum Schliessen..."
