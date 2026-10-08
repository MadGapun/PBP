"""`python -m bewerbungs_assistent_boot [dashboard]` — startet die aktuelle Fassung (#1093).

Ohne Argument den MCP-Server (so startet ihn Claude Desktop), mit `dashboard`
das eigenstaendige Dashboard.
"""
import sys

from bewerbungs_assistent_boot import starte

starte("dashboard" if len(sys.argv) > 1 and sys.argv[1] == "dashboard" else "server")
