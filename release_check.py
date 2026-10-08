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

    _check_readme_version(readme_file, readme, fix)


def _check_readme_version(readme_file, readme, fix):
    """Die README nennt die Stable-Version an zwei Stellen (Fliesstext und
    Badge). Beide standen am 18.08.2026 fuenf Releases lang auf v1.7.16,
    obwohl DoD-Punkt 3 die Pflege vorschreibt — die README ist die
    oeffentliche Visitenkarte des Projekts, ein veralteter Stand dort
    kostet Vertrauen. Eine Regel, an die man sich erinnern muss, ist
    keine Kontrolle; deshalb steht sie jetzt im Gate.
    """
    try:
        tags = subprocess.run(
            ["git", "tag", "--list", "v1.7.*"],
            capture_output=True, text=True, timeout=15,
            cwd=str(PROJECT_DIR)).stdout.split()
    except Exception as e:  # pragma: no cover
        warn(f"Stable-Tag nicht ermittelbar: {e}")
        return
    # NUR echte Stable-Tags: "v1.7.0-beta.108" wuerde sonst als 1.7.108
    # gelesen (die Ziffern-Extraktion ueberspringt das "0-beta"-Segment)
    # und jede README als veraltet melden.
    tags = [t for t in tags if re.fullmatch(r"v1\.7\.\d+", t)]
    if not tags:
        return

    def _key(t):
        return [int(x) for x in t.lstrip("v").split(".")]

    neuster = "v" + ".".join(str(x) for x in max(_key(t) for t in tags))

    # Nur die beiden Kopf-Stellen zaehlen: Fliesstext und Stable-Badge.
    marke = chr(10) + "## "
    kopf = readme[:readme.index(marke)] if marke in readme else readme
    # v1.7.120: die Versionen werden AUS DEM KOPF gelesen, nicht per
    # Teilstring gegen ihn geprueft. Vorher galt "v1.7.12" aus der Roadmap
    # weiter unten als "im Kopf genannt", weil es in "v1.7.120" steckt —
    # ab 1.7.120 haette das Gate bei jedem Release gewarnt, und --fix
    # haette aus "v1.7.120" ein "v1.7.1190" gemacht.
    genannt = set(re.findall(r'v1\.7\.\d+(?!\d)', kopf))
    veraltet = {v for v in genannt if _key(v) < _key(neuster)}

    if not veraltet:
        ok(f"README nennt die aktuelle Stable-Version ({neuster})")
        return
    if fix:
        neu_text = readme
        for v in veraltet:
            neu_text = re.sub(re.escape(v) + r'(?!\d)', neuster, neu_text)
        readme_file.write_text(neu_text, encoding="utf-8")
        ok(f"README von {sorted(veraltet)} auf {neuster} korrigiert")
    else:
        warn(f"README nennt im Kopf {sorted(veraltet)}, "
             f"neustes Stable-Tag ist {neuster}")


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

    # #1170 U2: Die Karte "Was ist neu" im Update-Dialog (und der Hinweis auf dem Dashboard) liest einen kurzen Block fuer
    # Menschen am Anfang des Eintrags. Ohne ihn faellt sie auf die ersten Saetze zurueck - lesbar, aber nicht gezielt.
    anwender = re.search(r"<!--\s*anwender\s*-->(.*?)<!--\s*/anwender\s*-->", block, re.S | re.I)
    if anwender and anwender.group(1).strip():
        ok(f"CHANGELOG-Eintrag fuer {version} hat einen Anwender-Block (erscheint im Update-Dialog)")
    else:
        warn(f"CHANGELOG-Eintrag fuer {version} hat keinen Anwender-Block (<!-- anwender --> ... <!-- /anwender -->): "
             "die Karte 'Was ist neu' im Update-Dialog faellt dann auf die ersten Saetze zurueck")

    # v1.7.118: der CHANGELOG wird MASCHINELL gelesen. Elwosa meldet nach
    # einem Update die Punkte unter Added/Changed/Fixed der neuesten
    # Version (#823) — und dafuer muessen es `- `-Punkte sein, keine
    # Absaetze. Ein Eintrag aus reiner Prosa laesst den Kanal stumm.
    #
    # Geprueft wird mit DER Funktion, die ihn liest, nicht mit einer
    # zweiten Fassung ihrer Regeln (#963).
    try:
        sys.path.insert(0, str(PROJECT_DIR / "src"))
        from bewerbungs_assistent.services.elwosa_provider import (
            _parse_changelog_kopf,
        )
        gelesen, eintraege = _parse_changelog_kopf(changelog)
    except Exception as e:  # pragma: no cover
        warn(f"CHANGELOG-Parser nicht pruefbar: {e}")
        return
    if gelesen != version:
        error(f"Der Parser liest '{gelesen}' als neueste Version, "
              f"erwartet '{version}' — steht der Eintrag ganz oben?")
    elif not eintraege:
        error(f"Der Eintrag fuer {version} hat keine Listenpunkte unter "
              "Added/Changed/Fixed — Elwosa haette nach dem Update nichts "
              "zu melden (#823). Punkte mit '- ' beginnen.")
    else:
        ok(f"CHANGELOG maschinell lesbar ({len(eintraege)} Punkte fuer Elwosa)")


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


# ── 6. Modell-Katalog (#785) ──────────────────────────────────

def check_modell_katalog():
    """Ein Katalog ohne Pflege ist in einem Jahr wieder derselbe Befund.

    Warnung, kein Fehler: ein alter Katalog haelt keinen Release auf, er
    soll nur nicht vergessen werden.
    """
    print("\n[6] Modell-Katalog")
    src = str(PROJECT_DIR / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        from bewerbungs_assistent.services import modell_katalog
    except Exception as e:
        warn(f"Modell-Katalog nicht lesbar: {e}")
        return
    if modell_katalog.veraltet():
        warn(f"Modell-Katalog ist aelter als {modell_katalog.HOECHSTALTER_MONATE} "
             f"Monate ({modell_katalog.stand_text()}) — Empfehlungen gegen "
             "ollama.com pruefen und STAND nachziehen.")
    else:
        ok(f"Modell-Katalog aktuell ({modell_katalog.stand_text()})")


# ── 7. Update-Archiv (#1093) ──────────────────────────────────

def check_update_archiv(version):
    """Das Archiv fuer das Auto-Update laesst sich aus dem Arbeitsbaum bauen und besteht die Anwender-Pruefungen.

    Faengt, was sonst erst nach dem Tag auffiele: eine .dll oder .exe im Paket, ein Manifest, das nicht zur
    Version passt, ein Archiv ueber der Groessengrenze. Gebaut wird in ein Wegwerf-Verzeichnis.

    Signieren geschieht automatisch (03.10.2026): auf dem Release-Rechner liegt der Hauptschluessel am festen Ort
    (`~/PBP-Signatur`, `scripts/update_schluessel.py`). Steht dort einer, baut das Tor das Probe-Archiv SIGNIERT und
    prueft die Signatur gegen die eingetragenen Schluessel - ein falscher oder fehlender Schluessel faellt hier auf,
    vor dem Tag, nicht bei den Anwendern. Fehlt er bei einer stabilen Version, ist das ein Fehler. Fehlt die
    Sicherung der Schluessel, ist es eine Warnung. In der CI liegt kein Schluessel: dort wird nur ungesigniert geprobt.
    """
    print("\n[7] Update-Archiv (Auto-Update)")
    for pfad in (str(PROJECT_DIR / "src"), str(PROJECT_DIR / "scripts")):
        if pfad not in sys.path:
            sys.path.insert(0, pfad)
    try:
        import build_update_archive as bau
        import update_schluessel as us
        from bewerbungs_assistent.services.auto_update import fassung, schluessel
    except Exception as e:
        error(f"Archiv-Bauer nicht ladbar: {e}")
        return
    im_ci = bool(os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI"))
    erforderlich = schluessel.signatur_erforderlich()
    stand = us.stand()
    haupt = stand["hauptschluessel"]
    signieren = bool(erforderlich and haupt and not im_ci)
    import tempfile
    try:
        with tempfile.TemporaryDirectory(prefix="pbp_archiv_") as tmp:
            erg = bau.bauen(ordner=PROJECT_DIR, ausgabe=Path(tmp), vorabversion=not fassung.ist_stabil(version),
                            ohne_signatur=not signieren, schluessel_datei=haupt if signieren else None)
        zusatz = f", signiert und gegen die eingetragenen Schluessel geprueft ({erg.get('schluessel')})" if signieren else ""
        ok(f"Update-Archiv baubar: {erg['dateien']} Dateien, {erg['groesse'] // 1024} KB{zusatz}")
    except Exception as e:
        error(f"Update-Archiv nicht baubar: {e}")
        return
    if not fassung.ist_stabil(version):
        warn(f"{version} ist eine Vorabversion: das Auto-Update installiert sie nie (Archiv nur zur Probe gebaut).")
    if not erforderlich:
        warn("Keine vertrauten Schluessel in services/auto_update/schluessel.py: das Update wird nur per Pruefsumme "
             "geprueft, nicht signiert. Beim Release pbp-update-<fassung>.zip und SHA256SUMS anhaengen.")
        return
    if im_ci:
        ok("Signatur: in der CI wird nicht signiert (der geheime Schluessel liegt nur auf dem Release-Rechner).")
        return
    if not haupt:
        meldung = (f"Signaturschluessel nicht gefunden ({stand['ordner']}). Ohne ihn laesst sich kein Update "
                   "veroeffentlichen, das PBP annimmt. Aus der Sicherung zurueckholen (siehe LIESMICH.txt dort), "
                   "dann: python scripts/update_schluessel.py stand")
        (error if fassung.ist_stabil(version) else warn)(meldung)
    if stand["sicherung_vollstaendig"]:
        ok(f"Sicherung der Signaturschluessel vollstaendig: {stand['sicherung']}")
    else:
        warn(f"Die Signaturschluessel haben keine vollstaendige Sicherung ({stand['sicherung'] or 'kein OneDrive-Ordner'}). "
             "Sichern: python scripts/update_schluessel.py sichern")


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
    check_modell_katalog()
    check_update_archiv(version)

    print("\n" + "=" * 50)
    if ERRORS:
        print(f"  \033[0;31m{len(ERRORS)} Fehler, {len(WARNINGS)} Warnungen — RELEASE BLOCKIERT\033[0m")
        sys.exit(1)
    elif WARNINGS:
        print(f"  \033[1;33m0 Fehler, {len(WARNINGS)} Warnungen — Release moeglich\033[0m")
    else:
        print(f"  \033[0;32mAlle Checks bestanden — Release freigegeben\033[0m")
    print("=" * 50)
