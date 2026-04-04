#!/bin/bash
# PBP Dashboard — Doppelklick zum Starten (macOS)
cd "$(dirname "$0")"

if [ -f ".venv/bin/python" ]; then
    .venv/bin/python start_dashboard.py
else
    echo ""
    echo "  PBP ist noch nicht installiert."
    echo "  Bitte zuerst ausfuehren: bash installer/install.sh"
    echo ""
    read -p "  Druecke Enter zum Schliessen..."
fi
