# PyPI + MCP Registry Publishing

> Schritt-fuer-Schritt-Anleitung wie der Repo-Maintainer (MadGapun) PBP
> auf PyPI + MCP Registry veroeffentlicht. **Nicht von Claude
> ausfuehrbar** — braucht persoenliche Account-Credentials.

## Voraussetzungen (einmalig)

### PyPI

1. Account auf https://pypi.org/account/register/ anlegen
2. Optional: Test-PyPI-Account auf https://test.pypi.org (empfohlen fuer ersten Trial)
3. API-Token erzeugen: PyPI -> Account Settings -> API tokens -> Add API token
   - Scope: "Entire account" beim ersten Mal, danach scoped auf "bewerbungs-assistent"
4. Token speichern in `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-AgEIcH...   # dein Token

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-AgEN...     # separates Token fuer TestPyPI
```

### Build-Tools

```bash
pip install --upgrade build twine
```

## Veroeffentlichung — Schritt 1: PyPI

```bash
cd D:/MAD/Documents/Entwicklung/PBP

# 1. Vorherige Builds aufraeumen
rm -rf dist/ build/ *.egg-info/

# 2. Build
python -m build
# erzeugt dist/bewerbungs_assistent-1.7.0.tar.gz und .whl

# 3. Validieren
twine check dist/*

# 4. Optional: erst auf TestPyPI testen
twine upload --repository testpypi dist/*
# Test-Install in einer leeren venv:
#   pip install --index-url https://test.pypi.org/simple/ \
#       --extra-index-url https://pypi.org/simple/ bewerbungs-assistent
#   bewerbungs-assistent --help

# 5. Wenn alles passt: produktiv
twine upload dist/*
```

Nach Upload sichtbar unter: https://pypi.org/project/bewerbungs-assistent/

## Veroeffentlichung — Schritt 2: MCP Registry

Die offizielle MCP Registry (registry.modelcontextprotocol.io) ist der zentrale Katalog fuer MCP-Server.

```bash
# 1. mcp-publisher CLI installieren
# Download neueste Version von https://github.com/modelcontextprotocol/registry/releases
# Beispiel (Linux/macOS):
curl -L https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher-$(uname -s)-$(uname -m) \
    -o mcp-publisher
chmod +x mcp-publisher
sudo mv mcp-publisher /usr/local/bin/

# Windows: .exe von Releases herunterladen, in PATH legen

# 2. server.json validieren (existiert schon im Repo-Root)
cat server.json

# 3. Anmelden via GitHub OAuth
mcp-publisher login github
# oeffnet Browser, GitHub-Auth als MadGapun

# 4. Veroeffentlichen
mcp-publisher publish
```

Sichtbar unter: https://registry.modelcontextprotocol.io/

## Versions-Updates (laufende Releases)

Bei neuen Releases:

1. Version in `pyproject.toml` bumpen
2. Version in `server.json` bumpen
3. Build + Upload auf PyPI
4. `mcp-publisher publish` erneut

Die MCP Registry erkennt die neue Version anhand `server.json`.

## Troubleshooting

**`twine upload` schlaegt fehl mit 403:**
- Token-Scope falsch? Token im PyPI-UI pruefen.
- Username muss wortwoertlich `__token__` sein, nicht der GitHub-Name.

**`mcp-publisher publish` meldet Schema-Fehler:**
- `server.json` gegen JSON-Schema validieren:
  https://static.modelcontextprotocol.io/schemas/2025-09-29/server.schema.json
- Oft: Pflichtfeld `version` muss im Format X.Y.Z sein (kein Pre-Release-Suffix).

**Doppel-Upload (gleiche Version) auf PyPI:**
- Geht nicht. PyPI verbietet das (Sicherheits-Feature).
- Bei Fehl-Upload: Patch-Version (X.Y.Z+1) hochziehen.

## Was Claude/automatisierte Workflows NICHT tun sollten

- **Niemals automatisch publishen** ohne explizite User-Aktion.
- **Niemals Tokens** committen oder in CI hartkodieren.
- Immer User die finale `twine upload` und `mcp-publisher publish`
  manuell auslosen lassen.
