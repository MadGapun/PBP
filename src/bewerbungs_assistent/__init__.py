"""Bewerbungs-Assistent - KI-gestuetzter MCP Server fuer Claude Desktop."""

__version__ = "0.16.5"


def main():
    """Entry point for the package."""
    from .server import run_server
    run_server()
