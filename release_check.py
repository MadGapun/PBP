"""Release-Gate: Prueft Versionskonsistenz, skipped Tests und First-Run-Smoke.

Ausfuehren vor jedem Release:
  python release_check.py
  python release_check.py --fix   # Korrigiert Versionen automatisch

Exit-Code 0 = alles OK, 1 = Probleme gefunden.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
ERRORS = []
WARNINGS = []


def error(msg):
    ERRORS.append(msg)
    print(f"  \033[0;31m✗ {msg}\033[0m")


def warn(msg):
    WARNINGS.append(msg)
    print(f"  \033[1;33m⚠ {msg}\033[0m")


def ok(msg):
    print(f"  \033[0;32m✓ {msg}\033[0m")


# ── 1. Versionskonsistenz ──────────────────────────────────────

def check_versions(fix=False):
    print("\n[1/4] Versionskonsistenz")

    # __init__.py
    init_file = PROJECT_DIR / "src" / "bewerbungs_assistent" / "__init__.py"
    init_version = None
    for line in init_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            init_version = line.split("=")[1].strip().strip('"').strip("'")
            break

    # pyproject.toml
    pyproject_file = PROJECT_DIR / "pyproject.toml"
    pyproject_version = None
    for line in pyproject_file.read_text(encoding="utf-8").splitlines():
        m = re.match(r'^version\s*=\s*"([^"]+)"', line)
        if m:
            pyproject_version = m.group(1)
            break

    # CHANGELOG.md
    changelog_file = PROJECT_DIR / "CHANGELOG.md"
    changelog_version = None
    for line in changelog_file.read_text(encoding="utf-8").splitlines():
        m = re.match(r'^## \[([^\]]+)\]', line)
        if m:
            changelog_version = m.group(1)
            break

    versions = {
        "__init__.py": init_version,
        "pyproject.toml": pyproject_version,
        "CHANGELOG.md (top)": changelog_version,
    }

    unique = set(v for v in versions.values() if v)
    if len(unique) == 1:
        ok(f"Alle Versionen konsistent: {unique.pop()}")
    else:
        for source, ver in versions.items():
            print(f"    {source}: {ver}")
        if fix and init_version:
            # Fix pyproject.toml
            content = pyproject_file.read_text(encoding="utf-8")
            content = re.sub(r'^version = "[^"]+"', f'version = "{init_version}"', content, flags=re.MULTILINE)
            pyproject_file.write_text(content)
            ok(f"pyproject.toml auf {init_version} korrigiert")
        else:
            error("Versionen sind inkonsistent! Nutze --fix oder korrigiere manuell.")

    return init_version


# ── 2. Skipped Tests ──────────────────────────────────────────

def check_skipped_tests():
    print("\n[2/4] Skipped Tests (kritische Pfade)")

    test_dir = PROJECT_DIR / "tests"
    critical_skips = []

    for test_file in test_dir.glob("*.py"):
        content = test_file.read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            if "@pytest.mark.skip" in line and "onboarding" in line.lower():
                critical_skips.append(f"{test_file.name}:{i}: {line.strip()}")

    if critical_skips:
        for skip in critical_skips:
            error(f"Kritischer Test uebersprungen: {skip}")
    else:
        ok("Keine kritischen Onboarding-Tests uebersprungen")


# ── 3. Test-Badge ──────────────────────────────────────────────

def check_badge():
    print("\n[3/4] README-Badge")

    readme = (PROJECT_DIR / "README.md").read_text(encoding="utf-8")
    m = re.search(r'Tests-(\d+)(?:%20passing)?', readme)
    if not m:
        warn("Kein Test-Badge in README gefunden")
        return

    badge_count = int(m.group(1))

    # Echte Testzahl ermitteln
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "--co"],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_DIR),
        )
        collected = re.search(r'(\d+) tests? collected', result.stdout)
        if collected:
            real_count = int(collected.group(1))
            if badge_count == real_count:
                ok(f"Badge stimmt: {badge_count} Tests")
            else:
                warn(f"Badge zeigt {badge_count}, gesammelt werden {real_count}")
    except Exception as e:
        warn(f"Test-Zaehlung fehlgeschlagen: {e}")


# ── 4. First-Run Smoke ────────────────────────────────────────

def check_first_run_smoke():
    print("\n[4/4] First-Run Smoke")

    try:
        result = subprocess.run(
            [sys.executable, "-c", """
import tempfile, os, shutil
d = tempfile.mkdtemp()
os.environ['BA_DATA_DIR'] = d
from bewerbungs_assistent.database import Database
from bewerbungs_assistent.heartbeat import get_connection_status
from bewerbungs_assistent.server import mcp
db = Database(); db.initialize()
# Profil anlegen
pid = db.create_profile("Smoke Test", "smoke@test.de")
assert db.get_profile() is not None, "Profil nicht angelegt"
# Heartbeat
status = get_connection_status()
assert status['status'] in ('connected', 'unknown', 'disconnected')
# Dashboard import
from bewerbungs_assistent.dashboard import app
db.close(); shutil.rmtree(d)
print("OK")
"""],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_DIR),
        )
        if "OK" in result.stdout:
            ok("First-Run Smoke bestanden (Profil + Heartbeat + Dashboard)")
        else:
            error(f"First-Run Smoke fehlgeschlagen: {result.stderr[:200]}")
    except Exception as e:
        error(f"First-Run Smoke Fehler: {e}")


# ── Main ──────────────────────────────────────────────────────

if __name__ == "__main__":
    fix = "--fix" in sys.argv

    print("=" * 50)
    print("  PBP Release-Gate Check")
    print("=" * 50)

    check_versions(fix=fix)
    check_skipped_tests()
    check_badge()
    check_first_run_smoke()

    print("\n" + "=" * 50)
    if ERRORS:
        print(f"  \033[0;31m{len(ERRORS)} Fehler, {len(WARNINGS)} Warnungen — RELEASE BLOCKIERT\033[0m")
        sys.exit(1)
    elif WARNINGS:
        print(f"  \033[1;33m0 Fehler, {len(WARNINGS)} Warnungen — Release moeglich\033[0m")
    else:
        print(f"  \033[0;32mAlle Checks bestanden — Release freigegeben\033[0m")
    print("=" * 50)
