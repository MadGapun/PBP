"""Release-Gate: Prueft Versionskonsistenz, skipped Tests und First-Run-Smoke.

Ausfuehren vor jedem Release:
  python release_check.py
  python release_check.py --fix   # Korrigiert Versionen und Badge automatisch

Exit-Code 0 = alles OK, 1 = Probleme gefunden.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Windows: force UTF-8 stdout so ANSI symbols don't crash (#334)
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

PROJECT_DIR = Path(__file__).resolve().parent
ERRORS = []
WARNINGS = []

# Safe symbols (ASCII fallback when encoding is not UTF-8)
_UTF8 = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
_SYM_OK = "+" if "utf" not in _UTF8.lower() else "\u2713"
_SYM_FAIL = "X" if "utf" not in _UTF8.lower() else "\u2717"
_SYM_WARN = "!" if "utf" not in _UTF8.lower() else "\u26a0"


def error(msg):
    ERRORS.append(msg)
    print(f"  \033[0;31m{_SYM_FAIL} {msg}\033[0m")


def warn(msg):
    WARNINGS.append(msg)
    print(f"  \033[1;33m{_SYM_WARN} {msg}\033[0m")


def ok(msg):
    print(f"  \033[0;32m{_SYM_OK} {msg}\033[0m")


# ── 1. Versionskonsistenz ──────────────────────────────────────

def check_versions(fix=False):
    print("\n[1/5] Versionskonsistenz")

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

    mismatches = []

    # v1.7.0: Pre-Release-Versionen werden in PEP 440 als '1.7.0b1' kanonisch
    # normalisiert, in SemVer/npm als '1.7.0-beta.1'. Beide Schreibweisen sind
    # aequivalent — wir vergleichen normalisiert.
    def _normalize_version(v: str) -> str:
        if not v:
            return ""
        s = v.lower()
        # SemVer-Style → PEP 440: '1.7.0-beta.1' → '1.7.0b1', '-rc.1' → 'rc1'
        s = re.sub(r"-?beta\.?(\d+)", r"b\1", s)
        s = re.sub(r"-?alpha\.?(\d+)", r"a\1", s)
        s = re.sub(r"-?rc\.?(\d+)", r"rc\1", s)
        return s

    if _normalize_version(pyproject_version) != _normalize_version(init_version):
        if fix and init_version:
            content = pyproject_file.read_text(encoding="utf-8")
            content = re.sub(r'^version = "[^"]+"', f'version = "{init_version}"', content, flags=re.MULTILINE)
            pyproject_file.write_text(content, encoding="utf-8")
            pyproject_version = init_version
            versions["pyproject.toml"] = pyproject_version
            ok(f"pyproject.toml auf {init_version} korrigiert")
        else:
            mismatches.append("pyproject.toml")

    if _normalize_version(changelog_version) != _normalize_version(init_version):
        mismatches.append("CHANGELOG.md")

    if not mismatches:
        ok(f"Alle Versionen konsistent: {init_version}")
    else:
        for source, ver in versions.items():
            print(f"    {source}: {ver}")
        if "CHANGELOG.md" in mismatches:
            error("CHANGELOG.md steht nicht auf dem aktuellen Release-Stand und muss manuell aktualisiert werden.")
        if "pyproject.toml" in mismatches:
            error("pyproject.toml steht nicht auf dem aktuellen Release-Stand.")

    return init_version


# ── 2. Skipped Tests ──────────────────────────────────────────

def check_skipped_tests():
    print("\n[2/5] Skipped Tests (kritische Pfade)")

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

def check_badge(fix=False):
    print("\n[3/5] README-Badge")

    readme_file = PROJECT_DIR / "README.md"
    readme = readme_file.read_text(encoding="utf-8")
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
            elif fix:
                updated = readme.replace(f"Tests-{badge_count}", f"Tests-{real_count}")
                readme_file.write_text(updated, encoding="utf-8")
                ok(f"Badge von {badge_count} auf {real_count} korrigiert")
            else:
                warn(f"Badge zeigt {badge_count}, gesammelt werden {real_count}")
    except Exception as e:
        warn(f"Test-Zaehlung fehlgeschlagen: {e}")


# ── 4. CHANGELOG-Inhalt ──────────────────────────────────────

def check_changelog_content(version):
    print("\n[4/5] CHANGELOG-Inhalt")

    changelog = (PROJECT_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    # Pruefen ob der aktuelle Versions-Block existiert
    version_header = f"## [{version}]"
    if version_header not in changelog:
        error(f"CHANGELOG enthaelt keinen Eintrag fuer {version}")
        return

    # Pruefen ob der Block nicht leer ist (mindestens eine Zeile mit ### darunter)
    idx = changelog.index(version_header)
    block = changelog[idx:].split("\n## [")[0] if "\n## [" in changelog[idx + 1:] else changelog[idx:]
    has_sections = "###" in block
    if not has_sections:
        warn(f"CHANGELOG-Eintrag fuer {version} hat keine Unterabschnitte (### ...)")
    else:
        lines = [l for l in block.splitlines() if l.strip() and not l.startswith("#")]
        ok(f"CHANGELOG-Eintrag fuer {version} vorhanden ({len(lines)} Zeilen)")


# ── 5. First-Run Smoke ────────────────────────────────────────

def check_first_run_smoke():
    print("\n[5/5] First-Run Smoke")

    try:
        pythonpath = str(PROJECT_DIR / "src")
        existing_pythonpath = os.environ.get("PYTHONPATH")
        if existing_pythonpath:
            pythonpath = pythonpath + os.pathsep + existing_pythonpath
        result = subprocess.run(
            [sys.executable, "-c", """
import tempfile, os, shutil, sys
d = tempfile.mkdtemp()
try:
    os.environ['BA_DATA_DIR'] = d
    sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
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
    db.close()
    print("OK")
finally:
    try:
        shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass
"""],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_DIR),
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": pythonpath},
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

    version = check_versions(fix=fix)
    check_skipped_tests()
    check_badge(fix=fix)
    check_changelog_content(version)
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
