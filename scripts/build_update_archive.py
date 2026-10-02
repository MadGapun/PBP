"""Baut das Update-Archiv fuer das Auto-Update (#1093): ZIP, Pruefsummenliste, Signatur.

Teil der Release-Routine (CLAUDE.md, Release-Workflow). Fuer JEDEN stabilen Release entstehen
drei Dateien, die an die GitHub-Release gehaengt werden:

    pbp-update-<fassung>.zip   manifest.json, src/, start_dashboard.py, _selftest.py
    SHA256SUMS                 '<sha256>  pbp-update-<fassung>.zip'
    SHA256SUMS.sig             Ed25519-Signatur ueber die Bytes von SHA256SUMS (Base64)

Aufruf (vom Release-Commit aus; ohne --ref wird der Arbeitsbaum genommen):

    python scripts/build_update_archive.py --ref v1.8.1 --ausgabe dist
    python scripts/build_update_archive.py --ref v1.8.1 --ausgabe dist --schluessel-datei C:/pfad/update-schluessel.hex

Der geheime Schluessel kommt aus `--schluessel-datei` oder der Umgebungsvariable
`PBP_UPDATE_SCHLUESSEL_DATEI` (Erzeugen: `scripts/update_schluessel.py erzeugen`). Steht in
`services/auto_update/schluessel.py` ein oeffentlicher Schluessel, MUSS signiert werden, und die
Signatur wird gegen genau diese Schluessel gegengeprueft: ein falscher Schluessel faellt hier auf,
nicht erst bei den Anwendern.

Das fertige Archiv wird mit denselben Pruefungen gelesen, die das Auto-Update benutzt
(Pruefsumme, Signatur, sicheres Entpacken, Manifest). Ein Archiv, das PBP spaeter selbst
ablehnen wuerde, wird gar nicht erst ausgegeben.

Reproduzierbar: feste Zeitstempel und Dateirechte, sortierte Reihenfolge — dasselbe Commit
ergibt dasselbe Archiv.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "src"))

from bewerbungs_assistent_boot import FORMAT as BOOT_FORMAT  # noqa: E402
from bewerbungs_assistent.services.auto_update import (  # noqa: E402
    abhaengigkeiten, ed25519, entpacken, fassung, manifest as manifest_modul, pruefung, quelle, schluessel,
)

ENTHALTEN = ("src", "start_dashboard.py", "_selftest.py")
AUSGESCHLOSSEN_TEILE = {"__pycache__", ".DS_Store", "Thumbs.db"}
AUSGESCHLOSSEN_ENDUNGEN = {".pyc", ".pyo"}
FESTE_ZEIT = (2020, 1, 1, 0, 0, 0)
SCHLUESSEL_ENV = "PBP_UPDATE_SCHLUESSEL_DATEI"


class BauFehler(Exception):
    pass


def _git(*argumente, binaer=False):
    r = subprocess.run(["git", "-C", str(WURZEL), *argumente], capture_output=True)
    if r.returncode != 0:
        raise BauFehler(f"git {' '.join(argumente)} schlug fehl: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout if binaer else r.stdout.decode("utf-8")


def _auszuschliessen(pfad: str) -> bool:
    teile = pfad.split("/")
    return any(t in AUSGESCHLOSSEN_TEILE for t in teile) or os.path.splitext(pfad)[1].lower() in AUSGESCHLOSSEN_ENDUNGEN


def dateien_aus_git(ref: str) -> dict:
    """{Pfad: Bytes} aus `git archive <ref>` — nur, was im Commit steht, nie lose Dateien des Arbeitsbaums."""
    roh = _git("archive", "--format=tar", ref, "--", *ENTHALTEN, binaer=True)
    ergebnis = {}
    with tarfile.open(fileobj=io.BytesIO(roh), mode="r:") as tar:
        for m in tar.getmembers():
            if m.isfile() and not _auszuschliessen(m.name):
                ergebnis[m.name] = tar.extractfile(m).read()
    return ergebnis


def dateien_aus_ordner(ordner: Path) -> dict:
    """{Pfad: Bytes} aus einem Ordner (fuer Tests und Probelaeufe ohne Commit)."""
    ergebnis = {}
    for name in ENTHALTEN:
        p = ordner / name
        if p.is_file():
            ergebnis[name] = p.read_bytes()
        elif p.is_dir():
            for datei in sorted(p.rglob("*")):
                rel = datei.relative_to(ordner).as_posix()
                if datei.is_file() and not _auszuschliessen(rel):
                    ergebnis[rel] = datei.read_bytes()
    return ergebnis


def _lese(dateien: dict, pfad: str) -> str:
    if pfad not in dateien:
        raise BauFehler(f"{pfad} fehlt im Quellstand")
    return dateien[pfad].decode("utf-8-sig")


def fassung_aus(dateien: dict) -> str:
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', _lese(dateien, "src/bewerbungs_assistent/__init__.py"), re.M)
    if not m:
        raise BauFehler("__version__ nicht gefunden")
    return m.group(1)


def schema_aus(dateien: dict):
    m = re.search(r"^SCHEMA_VERSION\s*=\s*(\d+)", _lese(dateien, "src/bewerbungs_assistent/database.py"), re.M)
    return int(m.group(1)) if m else None


def _pyproject_listen(text: str):
    """(Pflicht, Optional) aus pyproject.toml, ohne eine TOML-Bibliothek vorauszusetzen (3.11 hat tomllib)."""
    import tomllib
    daten = tomllib.loads(text)
    projekt = daten["project"]
    pflicht = list(projekt.get("dependencies", []))
    optional = []
    for gruppe, eintraege in (projekt.get("optional-dependencies") or {}).items():
        if gruppe in ("dev", "all"):
            continue
        for e in eintraege:
            if not e.startswith("bewerbungs-assistent") and e not in optional and e not in pflicht:
                optional.append(e)
    python_min = re.search(r">=\s*([0-9.]+)", projekt.get("requires-python", ">=3.11"))
    return pflicht, optional, python_min.group(1) if python_min else "3.11"


def _changelog_auszug(text: str, version: str, maximal: int = 3) -> list:
    """Die ersten Zeilen des CHANGELOG-Eintrags der Fassung als kurze Saetze (fuer den Update-Hinweis)."""
    m = re.search(rf"^##\s*\[?v?{re.escape(version)}\]?[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if not m:
        return []
    saetze = []
    for zeile in m.group(1).splitlines():
        zeile = zeile.strip()
        if zeile.startswith(("---", "#", "|", "```")):
            if saetze:
                break
            continue
        zeile = re.sub(r"^[-*]\s+", "", zeile)
        zeile = re.sub(r"[*_`]", "", zeile)
        zeile = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", zeile)
        if len(zeile) < 12:
            continue
        saetze.append(zeile[:240])
        if len(saetze) >= maximal:
            break
    return saetze


def manifest_bauen(dateien: dict, version: str, *, braucht_installer: str = "", changelog=None, ohne_changelog=False) -> dict:
    pflicht, optional, python_min = _pyproject_listen(_lese(dateien, "pyproject.toml")) if "pyproject.toml" in dateien else ([], [], "3.11")
    for angabe in pflicht + optional:
        if abhaengigkeiten.lesen(angabe) is None:
            raise BauFehler(f"Paketangabe fuer das Manifest zu kompliziert: {angabe!r}")
    return {
        "format": manifest_modul.MANIFEST_FORMAT,
        "version": version,
        "linie": fassung.linie(version),
        "boot_format": BOOT_FORMAT,
        "python": {"min": python_min, "unter": "4"},
        "schema": schema_aus(dateien),
        "requirements": pflicht,
        "requirements_optional": optional,
        "auto_update_moeglich": not braucht_installer,
        "braucht_installer": braucht_installer,
        "changelog": [] if ohne_changelog else list(changelog or []),
        "erstellt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def zip_schreiben(ziel: Path, dateien: dict, manifest: dict) -> None:
    eintraege = dict(dateien)
    eintraege["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for pfad in sorted(eintraege):
            info = zipfile.ZipInfo(pfad, date_time=FESTE_ZEIT)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, eintraege[pfad])


def geheimen_schluessel_lesen(pfad) -> bytes:
    text = Path(pfad).read_text(encoding="utf-8").strip()
    try:
        roh = bytes.fromhex(text)
    except ValueError as exc:
        raise BauFehler(f"{pfad}: kein Hex") from exc
    if len(roh) != 32:
        raise BauFehler(f"{pfad}: {len(roh)} statt 32 Byte")
    return roh


def bauen(*, ref=None, ordner=None, ausgabe: Path, schluessel_datei=None, vorabversion=False,
          braucht_installer="", changelog=None, ohne_signatur=False) -> dict:
    ausgabe = Path(ausgabe)
    ausgabe.mkdir(parents=True, exist_ok=True)
    if ref:
        dateien = dateien_aus_git(ref)
        extra = _git("show", f"{ref}:pyproject.toml", binaer=True)
        dateien["pyproject.toml"] = extra
        try:
            clog = _git("show", f"{ref}:CHANGELOG.md")
        except BauFehler:
            clog = ""
    else:
        dateien = dateien_aus_ordner(Path(ordner or WURZEL))
        pp = Path(ordner or WURZEL) / "pyproject.toml"
        if pp.is_file():
            dateien["pyproject.toml"] = pp.read_bytes()
        cl = Path(ordner or WURZEL) / "CHANGELOG.md"
        clog = cl.read_text(encoding="utf-8") if cl.is_file() else ""
    version = fassung_aus(dateien)
    if not fassung.gueltig(version):
        raise BauFehler(f"Ungueltige Fassung: {version!r}")
    if not fassung.ist_stabil(version) and not vorabversion:
        raise BauFehler(f"{version} ist eine Vorabversion. Das Auto-Update installiert sie nie; mit --vorabversion "
                        "trotzdem bauen (nur zum Erproben).")
    auszug = changelog if changelog is not None else _changelog_auszug(clog, version)
    manifest = manifest_bauen(dateien, version, braucht_installer=braucht_installer, changelog=auszug)
    dateien.pop("pyproject.toml", None)

    name = quelle.ARCHIV_NAME.format(version=version)
    archiv = ausgabe / name
    zip_schreiben(archiv, dateien, manifest)
    summe = pruefung.sha256_datei(archiv)
    summen_bytes = f"{summe}  {name}\n".encode("utf-8")
    (ausgabe / quelle.SUMMEN_NAME).write_bytes(summen_bytes)

    signatur_pfad = ausgabe / quelle.SIGNATUR_NAME
    signatur_pfad.unlink(missing_ok=True)
    schluessel_datei = schluessel_datei or os.environ.get(SCHLUESSEL_ENV)
    signiert = False
    if schluessel_datei:
        geheim = geheimen_schluessel_lesen(schluessel_datei)
        sig = ed25519.signieren(geheim, summen_bytes)
        signatur_pfad.write_text(base64.b64encode(sig).decode("ascii") + "\n", encoding="ascii")
        signiert = True
    elif schluessel.signatur_erforderlich() and not ohne_signatur:
        raise BauFehler("Im Code stehen vertraute Schluessel, aber es wurde keine Schluesseldatei angegeben "
                        f"(--schluessel-datei oder {SCHLUESSEL_ENV}). Ohne Signatur wuerde PBP das Update ablehnen.")

    try:
        _selbst_pruefen(archiv, name, summen_bytes, signatur_pfad if signiert else None, version, ohne_signatur=ohne_signatur)
    except BaseException:
        # Ein Archiv, das PBP selbst ablehnen wuerde, darf nirgends liegen bleiben: es kaeme sonst an die Release.
        for datei in (archiv, ausgabe / quelle.SUMMEN_NAME, signatur_pfad):
            datei.unlink(missing_ok=True)
        raise
    return {"version": version, "archiv": str(archiv), "sha256": summe, "signiert": signiert,
            "dateien": len(dateien) + 1, "groesse": archiv.stat().st_size}


def _selbst_pruefen(archiv: Path, name: str, summen_bytes: bytes, sig_pfad, version: str, *, ohne_signatur: bool) -> None:
    """Das Archiv durch genau die Pruefungen schicken, die PBP beim Installieren benutzt."""
    sig_text = sig_pfad.read_text(encoding="ascii") if sig_pfad else None
    if schluessel.signatur_erforderlich() and not ohne_signatur:
        von = pruefung.signatur_pruefen(summen_bytes, sig_text)
    else:
        von = ""
    pruefung.archiv_pruefen(archiv, name, summen_bytes, signiert_von=von)
    with tempfile.TemporaryDirectory() as tmp:
        ziel = Path(tmp) / "entpackt"
        entpacken.entpacken(archiv, ziel)
        if fassung.ist_stabil(version):
            # Eine Vorabversion (nur zum Erproben) liest das Auto-Update nie: ihr Manifest wuerde zu Recht abgewiesen.
            m = manifest_modul.lesen(ziel / "manifest.json", erwartete_version=version)
            if m.version != version:
                raise BauFehler("Manifest und Fassung widersprechen sich")
        if not (ziel / "src" / "bewerbungs_assistent" / "__init__.py").is_file():
            raise BauFehler("Im Archiv fehlt src/bewerbungs_assistent/__init__.py")
        if not (ziel / "_selftest.py").is_file() or not (ziel / "start_dashboard.py").is_file():
            raise BauFehler("Im Archiv fehlen _selftest.py oder start_dashboard.py")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ref", help="Git-Tag oder Commit (empfohlen); ohne: Arbeitsbaum")
    p.add_argument("--ordner", help="Statt Git: ein Ordner mit src/, start_dashboard.py, _selftest.py (Tests)")
    p.add_argument("--ausgabe", default="dist", help="Zielordner (Vorgabe: dist)")
    p.add_argument("--schluessel-datei", help=f"geheimer Schluessel (Hex); sonst ${SCHLUESSEL_ENV}")
    p.add_argument("--vorabversion", action="store_true", help="auch eine Beta bauen (nur zum Erproben)")
    p.add_argument("--braucht-installer", default="", metavar="GRUND",
                   help="Update ist NICHT automatisch installierbar; der Grund steht im Hinweis")
    p.add_argument("--ohne-signatur", action="store_true", help="nur fuer Tests: Signatur nicht verlangen")
    a = p.parse_args(argv)
    try:
        ergebnis = bauen(ref=a.ref, ordner=a.ordner, ausgabe=Path(a.ausgabe), schluessel_datei=a.schluessel_datei,
                         vorabversion=a.vorabversion, braucht_installer=a.braucht_installer, ohne_signatur=a.ohne_signatur)
    except BauFehler as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # die Pruefungen des Auto-Updates melden UpdateFehler
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1
    print(f"Fassung {ergebnis['version']}: {ergebnis['dateien']} Dateien, {ergebnis['groesse'] // 1024} KB, "
          f"sha256 {ergebnis['sha256'][:16]}…, {'signiert' if ergebnis['signiert'] else 'NICHT signiert'}")
    print(f"Anhaengen an die Release: {ergebnis['archiv']}, {Path(ergebnis['archiv']).parent / quelle.SUMMEN_NAME}"
          + (f", {Path(ergebnis['archiv']).parent / quelle.SIGNATUR_NAME}" if ergebnis["signiert"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
