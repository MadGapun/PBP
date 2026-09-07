#!/bin/bash
# ============================================================================
# PBP — Persoenliches Bewerbungs-Portal
# Doppelklick-Deinstaller fuer macOS und Linux (#975, I11)
# ============================================================================
# Gegenstueck zu INSTALLIEREN.command. Unter Windows gibt es seit
# jeher DEINSTALLIEREN.bat zum Doppelklicken — auf dem Mac war
# Deinstallieren bis v1.7.34 ein Terminalbefehl mit Unterordner-Pfad.
#
# Dieses Skript entfernt selbst nichts. Es ruft nur
# installer/deinstallieren.sh auf, und DAS fragt vor jedem Schritt.
# ============================================================================

set -e
cd "$(dirname "$0")"

SKRIPT="$(pwd)/installer/deinstallieren.sh"

if [ ! -f "$SKRIPT" ]; then
    echo ""
    echo "  Der Deinstaller wurde nicht gefunden:"
    echo "    $SKRIPT"
    echo ""
    echo "  Diese Datei muss im PBP-Projektordner liegen, neben"
    echo "  INSTALLIEREN.command."
    echo ""
    read -p "  Druecke Enter zum Schliessen..."
    exit 1
fi

bash "$SKRIPT"

echo ""
read -p "  Druecke Enter zum Schliessen..."
