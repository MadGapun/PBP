"""Bewerbungs-Assistent - KI-gestuetzter MCP Server für Claude Desktop."""

__version__ = "0.30.2"


def main():
    """Entry point for the package."""
    from .server import run_server
    run_server()
