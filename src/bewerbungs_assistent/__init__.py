"""Bewerbungs-Assistent - KI-gestuetzter MCP Server fuer Claude Desktop."""

__version__ = "0.19.0"


def main():
    """Entry point for the package."""
    from .server import run_server
    run_server()
