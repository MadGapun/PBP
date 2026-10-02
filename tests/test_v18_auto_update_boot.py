"""Auto-Update (#1093): der Startbaustein waehlt die Fassung, schaltet bei Fehlern zurueck, belegt sie.

Der Startbaustein (`bewerbungs_assistent_boot`) ist der Teil, der sich nie aendert und
trotzdem jede kuenftige Fassung laedt. Deshalb laeuft ein Teil der Tests als ECHTER
Prozess gegen ein nachgebautes Programmordner-Layout mit Attrappen-Fassungen: nur so
zeigt sich, ob `runpy`, `sys.path` und der Rueckfall im selben Prozess zusammen halten.

Kein Test fasst den echten Programmordner an: jede Attrappe liegt unter `tmp_path`,
und das Layout wird ueber `PBP_APP_DIR` gewaehlt (`app_dir()` hat sonst keinen Weg ins
echte `%LOCALAPPDATA%`).
"""
import ast
import json
import os
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import bewerbungs_assistent_boot as boot  # noqa: E402

PYTHON = sys.executable


# ── Hilfen ────────────────────────────────────────────────────────────────────────────

DEFAULT_MAIN = """
import os
from pathlib import Path
app = Path(os.environ["PBP_APP_DIR"])
v = os.environ["PBP_FASSUNG"]
(app / f"lief_{v}.txt").write_text(v, encoding="utf-8")
"""


def fassung_anlegen(app: Path, version: str, main: str = DEFAULT_MAIN, init: str = "", fertig: bool = True,
                    dashboard: str = None, site_dateien: dict = None):
    pkg = app / "versions" / version / "src" / "bewerbungs_assistent"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(f'__version__ = "{version}"\n{init}', encoding="utf-8")
    (pkg / "__main__.py").write_text(main, encoding="utf-8")
    if dashboard is not None:
        (app / "versions" / version / "start_dashboard.py").write_text(dashboard, encoding="utf-8")
    for name, inhalt in (site_dateien or {}).items():
        site = app / "versions" / version / "site"
        site.mkdir(exist_ok=True)
        (site / name).write_text(inhalt, encoding="utf-8")
    if fertig:
        (app / "versions" / version / ".fertig").write_text("ok", encoding="utf-8")


def layout(tmp_path, fassungen=("1.8.0",), aktuell=None, **kw) -> Path:
    app = tmp_path / "app"
    (app / "versions").mkdir(parents=True)
    for v in fassungen:
        fassung_anlegen(app, v, **kw)
    if aktuell is None:
        aktuell = fassungen[-1] if fassungen else None
    if aktuell:
        (app / "aktuell.txt").write_text(aktuell + "\n", encoding="utf-8")
    return app


def starten(app: Path, *args, env_extra=None, timeout=60, ohne_app=False):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PBP_APP_DIR", None)
    env.pop("PBP_FASSUNG", None)
    if not ohne_app:
        env["PBP_APP_DIR"] = str(app)
    env.update(env_extra or {})
    return subprocess.run([PYTHON, "-m", "bewerbungs_assistent_boot", *args], env=env, capture_output=True,
                          text=True, timeout=timeout, cwd=str(app.parent if app else None))


def status(app: Path) -> dict:
    return json.loads((app / "update_status.json").read_text(encoding="utf-8"))


def alt_machen(app: Path, sekunden=3600):
    """Den eingetragenen Start aelter datieren, damit er nicht mehr als 'laeuft vielleicht noch an' gilt."""
    s = status(app)
    s["start"]["zeit"] = (datetime.now(timezone.utc) - timedelta(seconds=sekunden)).isoformat(timespec="seconds")
    (app / "update_status.json").write_text(json.dumps(s), encoding="utf-8")


# ── Versionsnummern ───────────────────────────────────────────────────────────────────

def test_sortschluessel_ordnet_vorabversionen_vor_die_fertige():
    reihe = ["1.8.0-alpha.2", "1.8.0-beta.1", "1.8.0-beta.15", "1.8.0-rc.1", "1.8.0", "1.8.1", "1.9.0", "1.10.0", "2.0.0"]
    schluessel = [boot.sortschluessel(v) for v in reihe]
    assert all(schluessel)
    assert schluessel == sorted(schluessel)
    assert len(set(schluessel)) == len(reihe)


@pytest.mark.parametrize("kaputt", ["", None, "v1.8.0", "1.8", "1.8.0.1", "1.8.0-beta", "1.8.0+x", "1.8.0 ", "../x", "..\\evil",
                                    "1.8.0-nightly.1", "1.8.0\n", 18, "١.٨.٠"])
def test_sortschluessel_lehnt_alles_ab_was_keine_fassung_ist(kaputt):
    assert boot.sortschluessel(kaputt) is None


def test_ein_pfad_als_fassungsname_ist_nie_gueltig(tmp_path):
    app = layout(tmp_path)
    for name in ("..", "..\\..", "1.8.0/../..", "C:\\Windows"):
        assert boot.fassung_gueltig(app, name) is False


# ── Gueltigkeit einer Fassung ────────────────────────────────────────────────────────

def test_ohne_fertig_marke_ist_eine_fassung_nicht_gueltig(tmp_path):
    app = layout(tmp_path, fassungen=("1.8.0", "1.8.1"))
    (app / "versions" / "1.8.1" / ".fertig").unlink()
    assert boot.gueltige_fassungen(app) == ["1.8.0"]


def test_ohne_paket_ist_eine_fassung_nicht_gueltig(tmp_path):
    app = layout(tmp_path, fassungen=("1.8.0",))
    (app / "versions" / "1.8.0" / "src" / "bewerbungs_assistent" / "__init__.py").unlink()
    assert boot.gueltige_fassungen(app) == []


def test_gueltige_fassungen_neueste_zuerst(tmp_path):
    app = layout(tmp_path, fassungen=("1.8.0", "1.10.0", "1.8.2", "1.9.0-beta.3"))
    assert boot.gueltige_fassungen(app) == ["1.10.0", "1.9.0-beta.3", "1.8.2", "1.8.0"]


# ── Fassung waehlen ───────────────────────────────────────────────────────────────────

def test_waehle_fassung_nimmt_aktuell_txt_und_vermerkt_den_start(tmp_path):
    app = layout(tmp_path, fassungen=("1.8.0", "1.8.1"), aktuell="1.8.0")
    fassung, hinweis = boot.waehle_fassung(app)
    assert (fassung, hinweis) == ("1.8.0", None)
    s = status(app)
    assert s["start"]["version"] == "1.8.0" and s["start"]["versuche"] == 1 and s["start"]["bestaetigt"] is False
    assert s["format"] == boot.FORMAT


def test_aktuell_txt_mit_bom_und_leerzeichen_wird_gelesen(tmp_path):
    app = layout(tmp_path, fassungen=("1.8.0", "1.8.1"), aktuell="1.8.0")
    (app / "aktuell.txt").write_bytes(b"\xef\xbb\xbf  1.8.1 \r\n")
    assert boot.lese_aktuell(app) == "1.8.1"


def test_fehlt_aktuell_txt_gilt_die_neueste_fassung_und_wird_eingetragen(tmp_path):
    app = layout(tmp_path, fassungen=("1.8.0", "1.8.2", "1.8.1"), aktuell="")
    (app / "aktuell.txt").unlink(missing_ok=True)
    fassung, _ = boot.waehle_fassung(app)
    assert fassung == "1.8.2"
    assert (app / "aktuell.txt").read_text(encoding="utf-8").strip() == "1.8.2"


def test_zeigt_aktuell_txt_auf_eine_unvollstaendige_fassung_gilt_die_neueste_fertige(tmp_path):
    app = layout(tmp_path, fassungen=("1.8.0", "1.8.1"), aktuell="1.8.1")
    (app / "versions" / "1.8.1" / ".fertig").unlink()
    fassung, hinweis = boot.waehle_fassung(app)
    assert fassung == "1.8.0"
    assert "unvollstaendig" in hinweis


def test_ohne_jede_fassung_gibt_es_keine_wahl(tmp_path):
    app = layout(tmp_path, fassungen=(), aktuell=None)
    fassung, hinweis = boot.waehle_fassung(app)
    assert fassung is None and hinweis


# ── Rueckfall bei stillem Scheitern ───────────────────────────────────────────────────

def _zwei_fassungen(tmp_path):
    app = layout(tmp_path, fassungen=("1.8.0", "1.8.1"), aktuell="1.8.1")
    s = {"vorherige": "1.8.0"}
    (app / "update_status.json").write_text(json.dumps(s), encoding="utf-8")
    return app


def test_zwei_unbestaetigte_starts_hintereinander_schalten_zurueck(tmp_path):
    app = _zwei_fassungen(tmp_path)
    assert boot.waehle_fassung(app)[0] == "1.8.1"        # Start 1 (nie bestaetigt)
    alt_machen(app)
    assert boot.waehle_fassung(app)[0] == "1.8.1"        # Start 2: noch ein Versuch
    assert status(app)["start"]["versuche"] == 2
    alt_machen(app)
    fassung, hinweis = boot.waehle_fassung(app)           # Start 3: zurueck
    assert fassung == "1.8.0"
    assert "liess sich nicht starten" in hinweis
    s = status(app)
    assert (app / "aktuell.txt").read_text(encoding="utf-8").strip() == "1.8.0"
    assert s["gescheitert"] == ["1.8.1"]
    assert s["rueckgang"]["von"] == "1.8.1" and s["rueckgang"]["nach"] == "1.8.0"
    assert s["rueckgang"]["gemeldet"] is False
    assert s["start"]["version"] == "1.8.0" and s["start"]["versuche"] == 1


def test_ein_start_der_erst_sekunden_alt_ist_zaehlt_nicht_als_gescheitert(tmp_path):
    """Zwei Prozesse starten gleichzeitig (Claude Desktop und die Verknuepfung): der zweite darf den ersten nicht verurteilen."""
    app = _zwei_fassungen(tmp_path)
    for _ in range(5):
        assert boot.waehle_fassung(app)[0] == "1.8.1"
    assert status(app)["start"]["versuche"] == 1
    assert "rueckgang" not in status(app)


def test_eine_bestaetigung_setzt_den_zaehler_zurueck(tmp_path):
    app = _zwei_fassungen(tmp_path)
    boot.waehle_fassung(app)
    alt_machen(app)
    boot.waehle_fassung(app)                              # Versuch 2
    assert boot.start_bestaetigen(app, "1.8.1") is True
    alt_machen(app)
    assert boot.waehle_fassung(app)[0] == "1.8.1"
    assert status(app)["start"]["versuche"] == 1
    alt_machen(app)
    assert boot.waehle_fassung(app)[0] == "1.8.1"         # und ist nicht auf dem Weg zurueck


def test_bestaetigen_gilt_nur_fuer_die_gestartete_fassung(tmp_path):
    app = _zwei_fassungen(tmp_path)
    boot.waehle_fassung(app)
    assert boot.start_bestaetigen(app, "1.8.0") is False
    assert status(app)["start"]["bestaetigt"] is False


def test_ohne_aeltere_fassung_gibt_es_keinen_rueckfall_und_es_bleibt_bei_der_aktuellen(tmp_path):
    app = layout(tmp_path, fassungen=("1.8.1",), aktuell="1.8.1")
    for _ in range(4):
        assert boot.waehle_fassung(app)[0] == "1.8.1"
        alt_machen(app)
    assert "rueckgang" not in status(app)


def test_der_rueckfall_geht_nur_auf_aeltere_fassungen_nie_auf_eine_neuere(tmp_path):
    app = layout(tmp_path, fassungen=("1.8.0", "1.8.1", "1.8.2"), aktuell="1.8.1")
    boot.waehle_fassung(app)
    alt_machen(app)
    boot.waehle_fassung(app)
    alt_machen(app)
    assert boot.waehle_fassung(app)[0] == "1.8.0"


def test_eine_kaputte_statusdatei_ist_ein_leerer_stand(tmp_path):
    app = layout(tmp_path)
    (app / "update_status.json").write_text("{kaputt", encoding="utf-8")
    assert boot.lese_status(app) == {"format": boot.FORMAT}
    assert boot.waehle_fassung(app)[0] == "1.8.0"
    (app / "update_status.json").write_text("[1, 2]", encoding="utf-8")
    assert boot.lese_status(app) == {"format": boot.FORMAT}


# ── echter Prozess ────────────────────────────────────────────────────────────────────

def test_start_im_echten_prozess_laedt_die_fassung_aus_dem_versionsordner(tmp_path):
    app = layout(tmp_path, fassungen=("1.8.0", "1.8.1"), aktuell="1.8.0")
    r = starten(app)
    assert r.returncode == 0, r.stderr
    assert (app / "lief_1.8.0.txt").exists() and not (app / "lief_1.8.1.txt").exists()


def test_ein_alter_ordner_app_src_verdeckt_die_fassung_nie(tmp_path):
    """Nach einem Update vom alten Layout bleibt vielleicht ein `app/src`: es darf nie gewinnen."""
    app = layout(tmp_path, fassungen=("1.8.0",))
    alt = app / "src" / "bewerbungs_assistent"
    alt.mkdir(parents=True)
    (alt / "__init__.py").write_text('__version__ = "0.0.1-alt"\n', encoding="utf-8")
    (alt / "__main__.py").write_text('(__import__("pathlib").Path(__import__("os").environ["PBP_APP_DIR"]) / "ALT.txt").write_text("falsch")',
                                     encoding="utf-8")
    r = starten(app, env_extra={"PYTHONPATH": os.pathsep.join([str(app / "src"), str(SRC)])})
    assert r.returncode == 0, r.stderr
    assert (app / "lief_1.8.0.txt").exists() and not (app / "ALT.txt").exists()


def test_zusaetzliche_pakete_der_fassung_kommen_vor_allem_anderen(tmp_path):
    main = textwrap.dedent("""
        import os, zusatz
        from pathlib import Path
        (Path(os.environ["PBP_APP_DIR"]) / "zusatz.txt").write_text(zusatz.WERT)
    """)
    app = layout(tmp_path, main=main, site_dateien={"zusatz.py": 'WERT = "aus-site"'})
    r = starten(app)
    assert r.returncode == 0, r.stderr
    assert (app / "zusatz.txt").read_text() == "aus-site"


def test_der_prozess_belegt_seine_fassung_und_gibt_sie_beim_ende_frei(tmp_path):
    main = textwrap.dedent("""
        import os, json
        from pathlib import Path
        app = Path(os.environ["PBP_APP_DIR"]); v = os.environ["PBP_FASSUNG"]
        marken = list((app / "versions" / v / ".in_benutzung").glob("*.json"))
        (app / "marken.json").write_text(json.dumps([m.name for m in marken]))
        (app / "pid.txt").write_text(str(os.getpid()))
    """)
    app = layout(tmp_path, main=main)
    assert starten(app).returncode == 0
    pid = (app / "pid.txt").read_text()
    assert json.loads((app / "marken.json").read_text()) == [f"{pid}.json"]
    assert list((app / "versions" / "1.8.0" / ".in_benutzung").glob("*.json")) == []


def test_harter_fehler_beim_start_schaltet_sofort_im_selben_prozess_zurueck(tmp_path):
    app = layout(tmp_path, fassungen=("1.8.0",), aktuell="1.8.0")
    fassung_anlegen(app, "1.8.1", init="raise ImportError('Paket fehlt')\n")
    (app / "aktuell.txt").write_text("1.8.1\n", encoding="utf-8")
    (app / "update_status.json").write_text(json.dumps({"vorherige": "1.8.0"}), encoding="utf-8")
    r = starten(app)
    assert r.returncode == 0, r.stderr
    assert (app / "lief_1.8.0.txt").exists()
    assert "laeuft wieder mit 1.8.0" in r.stderr
    s = status(app)
    assert (app / "aktuell.txt").read_text(encoding="utf-8").strip() == "1.8.0"
    assert s["gescheitert"] == ["1.8.1"]
    assert "ImportError" in s["rueckgang"]["grund"] and "Paket fehlt" in s["rueckgang"]["grund"]


def test_ohne_aeltere_fassung_bleibt_der_harte_fehler_ein_fehler(tmp_path):
    app = layout(tmp_path, fassungen=("1.8.1",), init="raise ImportError('Paket fehlt')\n")
    r = starten(app)
    assert r.returncode != 0
    assert "ImportError" in r.stderr
    assert "ImportError" in status(app)["start"]["fehler"]
    assert (app / "aktuell.txt").read_text(encoding="utf-8").strip() == "1.8.1"


def test_nach_der_bestaetigung_ist_ein_absturz_kein_grund_fuer_den_rueckfall(tmp_path):
    main = textwrap.dedent("""
        import os
        from pathlib import Path
        from bewerbungs_assistent_boot import start_bestaetigen
        app = Path(os.environ["PBP_APP_DIR"])
        start_bestaetigen(app, os.environ["PBP_FASSUNG"])
        raise RuntimeError("spaeter Fehler im laufenden Betrieb")
    """)
    app = layout(tmp_path, fassungen=("1.8.0",))
    fassung_anlegen(app, "1.8.1", main=main)
    (app / "aktuell.txt").write_text("1.8.1\n", encoding="utf-8")
    (app / "update_status.json").write_text(json.dumps({"vorherige": "1.8.0"}), encoding="utf-8")
    r = starten(app)
    assert r.returncode != 0 and "spaeter Fehler" in r.stderr
    assert (app / "aktuell.txt").read_text(encoding="utf-8").strip() == "1.8.1"
    assert "rueckgang" not in status(app)
    assert not (app / "lief_1.8.0.txt").exists()


def test_systemexit_der_fassung_ist_kein_versionsfehler(tmp_path):
    """Zum Beispiel 'Port belegt': sys.exit(1) darf PBP nicht auf eine alte Fassung zurueckschalten."""
    app = layout(tmp_path, fassungen=("1.8.0",))
    fassung_anlegen(app, "1.8.1", main="import sys\nsys.exit(3)\n")
    (app / "aktuell.txt").write_text("1.8.1\n", encoding="utf-8")
    (app / "update_status.json").write_text(json.dumps({"vorherige": "1.8.0"}), encoding="utf-8")
    r = starten(app)
    assert r.returncode == 3
    assert (app / "aktuell.txt").read_text(encoding="utf-8").strip() == "1.8.1"
    assert "rueckgang" not in status(app)


def test_dashboard_als_ziel_startet_start_dashboard_py_der_fassung(tmp_path):
    dash = textwrap.dedent("""
        import os, sys
        from pathlib import Path
        Path(os.environ["PBP_APP_DIR"], "dashboard.txt").write_text(os.environ["PBP_FASSUNG"] + "|" + __name__)
    """)
    app = layout(tmp_path, dashboard=dash)
    r = starten(app, "dashboard")
    assert r.returncode == 0, r.stderr
    assert (app / "dashboard.txt").read_text() == "1.8.0|__main__"


def test_ohne_programmordner_bricht_der_start_mit_klarer_meldung_ab(tmp_path):
    app = layout(tmp_path)
    r = starten(app, ohne_app=True)
    assert r.returncode == 1
    assert "INSTALLIEREN.bat" in r.stderr


def test_ohne_installierte_fassung_bricht_der_start_mit_klarer_meldung_ab(tmp_path):
    app = layout(tmp_path, fassungen=(), aktuell=None)
    r = starten(app)
    assert r.returncode == 1
    assert "Keine installierte Fassung" in r.stderr


def test_app_dir_kommt_aus_der_umgebung_und_nur_wenn_der_ordner_existiert(tmp_path, monkeypatch):
    monkeypatch.setenv("PBP_APP_DIR", str(tmp_path / "gibt-es-nicht"))
    assert boot.app_dir() is None
    monkeypatch.setenv("PBP_APP_DIR", str(tmp_path))
    assert boot.app_dir() == tmp_path
    monkeypatch.delenv("PBP_APP_DIR")
    assert boot.app_dir() is None  # im Quellbaum: das Paket liegt nicht unter 'boot' eines Programmordners


# ── Vertrag ───────────────────────────────────────────────────────────────────────────

def test_der_startbaustein_nutzt_nur_die_standardbibliothek():
    """Er wird beim Installieren einmal kopiert und danach nie wieder ausgetauscht: jede fremde
    Abhaengigkeit waere eine, die in der Laufzeit fehlen kann, bevor irgendeine Fassung laeuft."""
    quelle = (SRC / "bewerbungs_assistent_boot" / "__init__.py").read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    module = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            module.update(a.name.split(".")[0] for a in knoten.names)
        elif isinstance(knoten, ast.ImportFrom) and knoten.level == 0:
            module.add((knoten.module or "").split(".")[0])
    fremd = sorted(m for m in module if m not in sys.stdlib_module_names)
    assert fremd == [], f"Startbaustein importiert Nicht-Standardbibliothek: {fremd}"
    # und er importiert das Programm selbst nie (es kann kaputt sein, wenn der Baustein es retten soll)
    assert "bewerbungs_assistent" not in module


def test_der_startbaustein_hat_einen_eigenen_main_der_starte_aufruft():
    quelle = (SRC / "bewerbungs_assistent_boot" / "__main__.py").read_text(encoding="utf-8")
    assert "starte(" in quelle and '"dashboard"' in quelle


def test_nach_bereit_melden_ist_eine_ausnahme_kein_versionsfehler_mehr(tmp_path):
    """Eine abrupt getrennte Verbindung zu Claude Desktop wirft kurz nach dem Start eine Ausnahme: das ist der laufende
    Betrieb, nicht die neue Fassung. Ohne diese Unterscheidung schaltete ein Fenster, das man schnell schliesst, zurueck."""
    main = textwrap.dedent("""
        from bewerbungs_assistent_boot import bereit_melden
        bereit_melden()
        raise RuntimeError("Verbindung abrupt getrennt")
    """)
    app = layout(tmp_path, fassungen=("1.8.0",))
    fassung_anlegen(app, "1.8.1", main=main)
    (app / "aktuell.txt").write_text("1.8.1\n", encoding="utf-8")
    (app / "update_status.json").write_text(json.dumps({"vorherige": "1.8.0"}), encoding="utf-8")
    r = starten(app)
    assert r.returncode != 0 and "Verbindung abrupt getrennt" in r.stderr
    assert (app / "aktuell.txt").read_text(encoding="utf-8").strip() == "1.8.1"
    assert "rueckgang" not in status(app) and not (app / "lief_1.8.0.txt").exists()


def test_vor_bereit_melden_ist_dieselbe_ausnahme_ein_versionsfehler(tmp_path):
    main = 'raise RuntimeError("Fehler im Startcode")\n'
    app = layout(tmp_path, fassungen=("1.8.0",))
    fassung_anlegen(app, "1.8.1", main=main)
    (app / "aktuell.txt").write_text("1.8.1\n", encoding="utf-8")
    (app / "update_status.json").write_text(json.dumps({"vorherige": "1.8.0"}), encoding="utf-8")
    r = starten(app)
    assert r.returncode == 0, r.stderr
    assert (app / "lief_1.8.0.txt").exists()
    assert status(app)["rueckgang"]["von"] == "1.8.1"


# ══ Gegenprobe (Mutationstest): Luecken, die ein absichtlich eingebauter Fehler aufgedeckt hat ═══════

def test_ist_auch_die_rueckfallfassung_kaputt_bleibt_der_fehler_sichtbar_und_es_gibt_keinen_zweiten_rueckfall(tmp_path):
    """Ein Rueckfall je Start. Sonst wuerde eine Kette kaputter Fassungen still durchprobiert, und niemand saehe,
    dass mehr als eine Fassung defekt ist."""
    app = layout(tmp_path, fassungen=("1.8.0",), aktuell="1.8.0")
    fassung_anlegen(app, "1.8.1", init="raise ImportError('Rueckfall kaputt')\n")
    fassung_anlegen(app, "1.8.2", init="raise ImportError('Neue kaputt')\n")
    (app / "aktuell.txt").write_text("1.8.2\n", encoding="utf-8")
    (app / "update_status.json").write_text(json.dumps({"vorherige": "1.8.1"}), encoding="utf-8")
    r = starten(app)
    assert r.returncode != 0
    assert "Rueckfall kaputt" in r.stderr
    assert not (app / "lief_1.8.0.txt").exists(), "kein zweiter, stiller Rueckfall auf die uebernaechste Fassung"
    assert not (app / "lief_1.8.1.txt").exists() and not (app / "lief_1.8.2.txt").exists()


def test_eine_vorherige_fassung_die_es_nicht_mehr_gibt_ist_kein_rueckfallziel(tmp_path):
    """Die Statusdatei merkt sich `vorherige`; der Ordner kann inzwischen aufgeraeumt sein. Dann gilt die neueste
    aeltere Fassung, die wirklich da ist."""
    app = layout(tmp_path, fassungen=("1.8.0", "1.8.1"), aktuell="1.8.1")
    (app / "update_status.json").write_text(json.dumps({"vorherige": "1.7.9"}), encoding="utf-8")
    boot.waehle_fassung(app)
    alt_machen(app)
    boot.waehle_fassung(app)
    alt_machen(app)
    ziel, _ = boot.waehle_fassung(app)
    assert ziel == "1.8.0"
    assert (app / "aktuell.txt").read_text(encoding="utf-8").strip() == "1.8.0"
