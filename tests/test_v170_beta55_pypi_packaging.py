"""Tests fuer v1.7.0-beta.55 — PyPI-Packaging-Vorbereitung (#429).

Pure Datei-Inspektion + tomllib-Parsing. Keine Live-PyPI-Calls.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def pyproject():
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
    with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


# === pyproject.toml — PyPI-Pflicht-Felder ===

def test_has_readme_pointing_to_file(pyproject):
    """PyPI rendert README.md als Long-Description — Pflicht fuer guten Listing-Eintrag."""
    readme = pyproject["project"]["readme"]
    assert readme == "README.md"
    assert (PROJECT_ROOT / "README.md").exists()


def test_has_classifiers(pyproject):
    """Trove-Classifiers sind Pflicht fuer PyPI-Such-Filter."""
    classifiers = pyproject["project"]["classifiers"]
    assert len(classifiers) >= 5
    # Mind. License + Python-Version + Topic
    assert any("License" in c for c in classifiers)
    assert any("Python :: 3" in c for c in classifiers)
    assert any("Topic ::" in c for c in classifiers)


def test_has_project_urls(pyproject):
    """Repository, Homepage, Issues fuer PyPI-Sidebar."""
    urls = pyproject["project"]["urls"]
    for key in ("Homepage", "Repository", "Documentation",
                 "Changelog", "Issues"):
        assert key in urls, f"project.urls.{key} fehlt"
        assert urls[key].startswith("https://github.com/MadGapun/PBP")


def test_has_keywords(pyproject):
    keywords = pyproject["project"]["keywords"]
    assert "mcp" in keywords
    assert "claude" in keywords
    assert len(keywords) >= 10


def test_has_entry_point(pyproject):
    """[project.scripts]: nach pip install muss `bewerbungs-assistent` als CLI da sein."""
    scripts = pyproject["project"]["scripts"]
    assert "bewerbungs-assistent" in scripts
    assert scripts["bewerbungs-assistent"] == "bewerbungs_assistent:main"


def test_requires_python_3_11_plus(pyproject):
    rp = pyproject["project"]["requires-python"]
    assert ">=3.11" in rp


# === server.json — MCP Registry ===

def test_server_json_exists():
    assert (PROJECT_ROOT / "server.json").exists()


def test_server_json_valid_for_mcp_registry():
    with open(PROJECT_ROOT / "server.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    # Pflicht-Felder laut MCP Registry Schema
    for key in ("name", "description", "repository", "version", "packages"):
        assert key in data, f"server.json fehlt {key}"
    assert data["name"].startswith("io.github.madgapun/")
    assert data["repository"]["url"].startswith("https://github.com/MadGapun/")
    assert data["repository"]["source"] == "github"
    assert isinstance(data["packages"], list)
    assert len(data["packages"]) >= 1


def test_server_json_pypi_package_matches_pyproject(pyproject):
    """Der Package-Name in server.json muss zum PyPI-Paket passen."""
    with open(PROJECT_ROOT / "server.json", "r", encoding="utf-8") as f:
        srv = json.load(f)
    pypi_pkgs = [p for p in srv["packages"] if p.get("registryType") == "pypi"]
    assert len(pypi_pkgs) == 1
    assert pypi_pkgs[0]["identifier"] == pyproject["project"]["name"]


# === Publish-Doku ===

def test_publish_documentation_exists():
    """scripts/publish_to_pypi.md mit Schritt-fuer-Schritt-Anleitung."""
    p = PROJECT_ROOT / "scripts" / "publish_to_pypi.md"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "twine upload" in content
    assert "mcp-publisher" in content
    # Sicherheits-Hinweis: Claude soll nicht automatisch publishen
    assert "Niemals" in content or "nicht automatisch" in content


# === Build-Bereitschaft ===

def test_pyproject_has_build_system(pyproject):
    bs = pyproject["build-system"]
    assert "hatchling" in bs["requires"][0]
    assert bs["build-backend"] == "hatchling.build"


def test_wheel_target_configured(pyproject):
    """Hatch muss wissen welche Pakete ins Wheel."""
    target = pyproject.get("tool", {}).get("hatch", {}).get(
        "build", {}).get("targets", {}).get("wheel", {})
    assert "src/bewerbungs_assistent" in target.get("packages", [])
