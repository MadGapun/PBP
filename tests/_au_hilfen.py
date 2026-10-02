"""Gemeinsame Hilfen der Auto-Update-Tests (#1093): Testdoppel fuers Netz, nachgebauter Programmordner, echte Archive.

Kein Test hier ruft GitHub auf oder fasst den echten Programmordner an:

* das Netz ist `FakeOeffner` (liefert Bytes zu festen Adressen),
* der Programmordner liegt unter `tmp_path` und wird ueber `PBP_APP_DIR` gewaehlt,
* die Archive sind ECHT — gebaut von `scripts/build_update_archive.py` aus einem winzigen Quellbaum.
  So prueft jeder Test dieselben Dateien, die ein Release liefern wuerde.
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "src"))
sys.path.insert(0, str(WURZEL / "scripts"))

import build_update_archive as bau  # noqa: E402
from bewerbungs_assistent.services.auto_update import ed25519, quelle  # noqa: E402


# ── Netz ──────────────────────────────────────────────────────────────────────────────

class FakeAntwort:
    def __init__(self, daten: bytes, headers=None, bei_lesen=None, ende_vorzeitig=None):
        self._daten = daten
        self._pos = 0
        self.headers = headers if headers is not None else {"Content-Length": str(len(daten))}
        self._bei_lesen = bei_lesen
        self._ende = ende_vorzeitig  # nach so vielen Byte abbrechen (Verbindung weg)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=-1):
        if self._bei_lesen:
            self._bei_lesen(self._pos)
        grenze = len(self._daten) if self._ende is None else min(len(self._daten), self._ende)
        if n is None or n < 0:
            n = grenze - self._pos
        stueck = self._daten[self._pos:min(self._pos + n, grenze)]
        self._pos += len(stueck)
        return stueck


class FakeOeffner:
    """`antworten`: Adresse -> Bytes | Exception | Callable[[], FakeAntwort | Exception]."""

    def __init__(self, antworten=None):
        self.antworten = dict(antworten or {})
        self.aufrufe = []

    def open(self, anfrage, timeout=None):
        url = getattr(anfrage, "full_url", anfrage)
        self.aufrufe.append(url)
        if url not in self.antworten:
            raise OSError(f"Testdoppel kennt {url} nicht")
        wert = self.antworten[url]
        if callable(wert):
            wert = wert()
        if isinstance(wert, BaseException):
            raise wert
        if isinstance(wert, FakeAntwort):
            return wert
        return FakeAntwort(wert)


# ── Quellbaum und Release ────────────────────────────────────────────────────────────

SELBSTTEST = '''\
print("OK")
'''


def quellbaum(ordner: Path, version: str, *, schema: int = 52, extra_dateien: dict = None, anforderungen=None) -> Path:
    """Ein winziger, aber vollstaendiger Quellbaum: genau die Teile, die der Builder und das Auto-Update lesen."""
    ordner = Path(ordner)
    paket = ordner / "src" / "bewerbungs_assistent"
    paket.mkdir(parents=True)
    (paket / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    (paket / "__main__.py").write_text("print('start')\n", encoding="utf-8")
    (paket / "database.py").write_text(f"SCHEMA_VERSION = {schema}\n", encoding="utf-8")
    (ordner / "start_dashboard.py").write_text("print('dashboard')\n", encoding="utf-8")
    (ordner / "_selftest.py").write_text(SELBSTTEST, encoding="utf-8")
    anf = anforderungen if anforderungen is not None else ["fastmcp>=3.0,<4", "httpx>=0.27"]
    zeilen = ",\n".join(f'    "{a}"' for a in anf)
    (ordner / "pyproject.toml").write_text(
        textwrap.dedent(f"""\
        [project]
        name = "bewerbungs-assistent"
        version = "{version}"
        requires-python = ">=3.11"
        dependencies = [
        {zeilen}
        ]
        [project.optional-dependencies]
        docs = ["pypdf>=4.0"]
        dev = ["pytest>=8.0"]
        """), encoding="utf-8")
    (ordner / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{version}] - 2026-10-02\n\n- Neue Hinweise im Dashboard, damit der naechste Schritt klar ist.\n"
        "- Ein Fehler in der Stellenliste wurde behoben.\n\n## [0.0.1]\n\n- alt\n", encoding="utf-8")
    for pfad, inhalt in (extra_dateien or {}).items():
        ziel = ordner / pfad
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(inhalt if isinstance(inhalt, bytes) else inhalt.encode("utf-8"))
    return ordner


class Release:
    """Ein gebautes Release: Dateien (Name -> Bytes) und die Adressen, unter denen sie das Netz-Testdoppel ausliefert."""

    def __init__(self, version, dateien, ergebnis):
        self.version = version
        self.dateien = dateien
        self.ergebnis = ergebnis

    def antworten(self) -> dict:
        return {quelle.asset_url(self.version, name): daten for name, daten in self.dateien.items()}

    @property
    def archiv_name(self):
        return quelle.ARCHIV_NAME.format(version=self.version)


def release_bauen(tmp: Path, version: str, *, schluessel_datei=None, braucht_installer="", **quellbaum_args) -> Release:
    quell = quellbaum(Path(tmp) / f"quelle-{version}", version, **quellbaum_args)
    aus = Path(tmp) / f"dist-{version}"
    ergebnis = bau.bauen(ordner=quell, ausgabe=aus, schluessel_datei=schluessel_datei, braucht_installer=braucht_installer,
                         ohne_signatur=schluessel_datei is None)
    dateien = {p.name: p.read_bytes() for p in aus.iterdir()}
    return Release(version, dateien, ergebnis)


def schluessel_paar(tmp: Path, name="haupt", seed=None):
    """(Datei mit geheimem Schluessel, {name: oeffentlicher Schluessel als Hex})."""
    geheim = seed or bytes([7] * 32)
    datei = Path(tmp) / f"{name}.hex"
    datei.write_text(geheim.hex() + "\n", encoding="utf-8")
    return datei, {name: ed25519.geheim_zu_oeffentlich(geheim).hex()}


# ── Programmordner ───────────────────────────────────────────────────────────────────

def fassung_anlegen(app: Path, version: str, *, fertig=True, main="print('lief')\n") -> Path:
    ordner = Path(app) / "versions" / version
    paket = ordner / "src" / "bewerbungs_assistent"
    paket.mkdir(parents=True)
    (paket / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    (paket / "__main__.py").write_text(main, encoding="utf-8")
    (ordner / "_selftest.py").write_text(SELBSTTEST, encoding="utf-8")
    if fertig:
        (ordner / ".fertig").write_text("ok", encoding="utf-8")
    return ordner


def programmordner(tmp: Path, fassungen=("1.8.0",), aktuell=None, status=None) -> Path:
    app = Path(tmp) / "app"
    (app / "versions").mkdir(parents=True)
    for v in fassungen:
        fassung_anlegen(app, v)
    aktuell = aktuell if aktuell is not None else (fassungen[-1] if fassungen else None)
    if aktuell:
        (app / "aktuell.txt").write_text(aktuell + "\n", encoding="utf-8")
    if status is not None:
        (app / "update_status.json").write_text(json.dumps(status), encoding="utf-8")
    return app


class FakeDb:
    """Nur die Einstellungs-Schnittstelle der Datenbank (`get_setting`, `get_setting_zahl`, `set_setting`)."""

    def __init__(self, werte=None):
        self.werte = dict(werte or {})

    def get_setting(self, key, default=None):
        return self.werte.get(key, default)

    def get_setting_zahl(self, key, vorgabe):
        wert = self.werte.get(key)
        if wert is None or wert == "":
            return vorgabe
        try:
            return int(wert)
        except (TypeError, ValueError):
            return vorgabe

    def set_setting(self, key, value):
        self.werte[key] = value


# ── Die Liste der Veroeffentlichungen (GitHub-API-Antwort) ────────────────────────────────

def eintrag(tag, *, body="Neue Hinweise im Dashboard.", prerelease=False, draft=False, dateien=True, signatur=False):
    v = tag[1:]
    assets = []
    if dateien:
        assets = [{"name": f"pbp-update-{v}.zip", "size": 2_500_000}, {"name": "SHA256SUMS", "size": 100}]
        if signatur:
            assets.append({"name": "SHA256SUMS.sig", "size": 90})
    return {"tag_name": tag, "name": f"PBP {v}", "draft": draft, "prerelease": prerelease, "body": body,
            "published_at": "2026-10-02T10:00:00Z", "assets": assets}


def liste(*eintraege):
    return FakeOeffner({quelle.API_FREIGABEN: json.dumps(list(eintraege)).encode()})
