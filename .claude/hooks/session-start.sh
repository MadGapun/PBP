#!/bin/bash
# SessionStart-Hook fuer Claude Code im Web (Cloud-Sitzungen).
# Baut dieselbe Umgebung wie die CI (.github/workflows/tests.yml):
# Paket mit [docs,dev,scraper]-Extras, also FastMCP 3.x statt eines
# zufaellig vorhandenen 2.x. Lokal (Windows) laeuft er nicht.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}"
VENV="$PWD/.venv"

# Eigene virtuelle Umgebung statt System-Python: das Container-Image
# bringt Pakete ueber Debian mit (PyJWT, cryptography, ...), die pip
# nicht deinstallieren kann — ein Upgrade bricht dann mitten ab.
# Python 3.13 wie in der CI; fehlt es, das Standard-python3. Eine Umgebung
# mit anderer Version wird neu angelegt.
PY=$(command -v python3.13 || command -v python3)
WUNSCH=$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
if [ -x "$VENV/bin/python" ]; then
  IST=$("$VENV/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
  if [ "$IST" != "$WUNSCH" ]; then
    rm -rf "$VENV"
  fi
fi
if [ ! -x "$VENV/bin/python" ]; then
  "$PY" -m venv "$VENV"
fi

# pip install -e ist idempotent; der Container-Zustand wird nach dem Hook
# zwischengespeichert, der zweite Start ist deshalb schnell.
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade pip
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check -e ".[docs,dev,scraper]"

# Chromium fuer die Dashboard-Browser-Tests ist im Container vorinstalliert
# (PLAYWRIGHT_BROWSERS_PATH). Nie `playwright install` ausfuehren. Das
# neueste Python-Playwright erwartet aber eine neuere Chromium-Revision als
# die vorhandene, und die Browser-Tests werden dann still uebersprungen.
# Deshalb Python-Playwright auf die Version des mitgelieferten
# Node-Playwright setzen — dessen Chromium liegt im Container.
PW_NODE=$(node -p 'require(require("child_process").execSync("npm root -g").toString().trim() + "/playwright/package.json").version' 2>/dev/null || true)
if [ -n "$PW_NODE" ]; then
  PW_MINOR=$(echo "$PW_NODE" | cut -d. -f1,2)
  "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check "playwright==${PW_MINOR}.*"
fi

# Die Umgebung fuer die ganze Sitzung aktivieren: `python` und `pytest`
# zeigen danach auf .venv.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=\"$VENV\""
    echo "export PATH=\"$VENV/bin:\$PATH\""
  } >> "$CLAUDE_ENV_FILE"
fi

# Die Projekt-Vorgabe ist FastMCP 3.x; eine 2.x-Umgebung hat lokal schon
# einmal wochenlang gruen gemeldet, was die CI rot fand (v1.7.120).
"$VENV/bin/python" -c "import fastmcp, sys; v=fastmcp.__version__; print('fastmcp', v); sys.exit(0 if v.split('.')[0]=='3' else 1)"
