"""Bewerbungs-Assistent - KI-gestützter MCP Server für Claude Desktop."""

__version__ = "1.5.0-beta.10"


def main():
    """Entry point for the package."""
    from .server import run_server
    run_server()
