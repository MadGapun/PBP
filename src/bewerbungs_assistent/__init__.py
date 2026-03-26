"""Bewerbungs-Assistent - KI-gestützter MCP Server für Claude Desktop."""

__version__ = "0.33.8"


def main():
    """Entry point for the package."""
    from .server import run_server
    run_server()
