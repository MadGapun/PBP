"""Welle 1 aus #1087 — Defekte auf der Claude-Seite (D49, H26, H27, H32).

* D49 (G8): nur archivierte Bewerbungen ergaben "Noch keine Bewerbungen
  erfasst".
* H26 (G6): `pbp_grenze_melden` setzte den Rohtext per quote() in den
  GitHub-Link, am Anonymisierer vorbei.
* H27 (G7): `profil_loeschen` loeschte ein Zweitprofil ohne Rueckfrage;
  sechs Schutzkonventionen, keine Annotations.
* H32 (G14, Teil "kaputter Satz"): `kein_profil()` bekam ganze Saetze und
  Werkzeugnamen und baute daraus "Um Ohne Profil gibt es nichts
  einzuordnen. zu koennen ...".
"""
import ast
import asyncio
import importlib
import inspect
import os
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))
PAKET = _repo() / "src" / "bewerbungs_assistent"


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_g1087w1_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    if isinstance(erg, dict) and set(erg) == {"result"}:
        return erg["result"]
    return erg


# ══ D49 ═══════════════════════════════════════════════════════════════

def test_d49_nur_archivierte_sind_nicht_keine(umgebung):
    db, mcp = umgebung
    db.save_profile({"name": "Test"})
    for i in range(3):
        aid = db.add_application({"title": f"Stelle {i}", "company": "Musterbetrieb GmbH",
                                  "status": "beworben"})
        db.update_application_status(aid, "abgelehnt", "",
                                     profile_id=db.get_active_profile_id())
    erg = _call(mcp, "bewerbungen_anzeigen")
    assert erg["anzahl"] == 0
    assert erg["archiviert"] == 3
    assert "Keine laufenden Bewerbungen" in erg["nachricht"]
    assert "3 abgeschlossene" in erg["nachricht"]
    assert "archiv=True" in erg["nachricht"]
    assert "Noch keine Bewerbungen erfasst" not in erg["nachricht"]
    assert erg["naechster_schritt"]


def test_d49_ganz_leer_bleibt_der_alte_satz(umgebung):
    db, mcp = umgebung
    db.save_profile({"name": "Test"})
    erg = _call(mcp, "bewerbungen_anzeigen")
    assert "Noch keine Bewerbungen erfasst" in erg["nachricht"]
    assert "archiviert" not in erg


# ══ H26 ═══════════════════════════════════════════════════════════════

def test_h26_grenze_melden_anonymisiert_vor_dem_link(umgebung):
    db, mcp = umgebung
    db.save_profile({"name": "Test"})
    db.add_application({"title": "Einkauf", "company": "Nordwerk Maschinenbau GmbH",
                        "status": "beworben"})
    erg = _call(mcp, "pbp_grenze_melden", {
        "was_versucht": "Bewerbung bei Nordwerk Maschinenbau zusammenfassen",
        "warum_pbp_nicht_passt": "Kein Werkzeug fuer Nordwerk Maschinenbau GmbH.",
    })
    link = unquote(erg["gh_issue_url"])
    assert "Nordwerk" not in link, link
    assert "Nordwerk" not in erg["vorgeschlagener_issue_body"]
    assert "Nordwerk" not in erg["vorgeschlagener_issue_titel"]
    assert erg["anonymisiert"], "Ersetzung muss benannt werden"


def test_h26_ohne_bestandsnamen_bleibt_der_text(umgebung):
    db, mcp = umgebung
    db.save_profile({"name": "Test"})
    erg = _call(mcp, "pbp_grenze_melden", {
        "was_versucht": "Termine als Liste drucken",
        "warum_pbp_nicht_passt": "Kein Druckwerkzeug.",
    })
    assert "Termine als Liste drucken" in unquote(erg["gh_issue_url"])
    assert erg["anonymisiert"] == []


# ══ H27 ═══════════════════════════════════════════════════════════════

def test_h27_zweitprofil_wird_nicht_ohne_bestaetigung_geloescht(umgebung):
    db, mcp = umgebung
    erstes = db.save_profile({"name": "Erstes"})
    zweites = db.create_profile("Zweites", "zwei@example.com")
    db.switch_profile(erstes)
    vorher = len(db.get_profiles())
    erg = _call(mcp, "profil_loeschen", {"profil_id": zweites})
    assert erg["status"] == "vorschau"
    assert "zeilen_gesamt" in erg and "je_bereich" in erg
    assert len(db.get_profiles()) == vorher, "Vorschau darf nichts loeschen"
    erg = _call(mcp, "profil_loeschen", {"profil_id": zweites, "bestaetigung": True})
    assert erg["status"] == "geloescht"
    assert len(db.get_profiles()) == vorher - 1


def test_h27_aktives_profil_auch_nur_mit_bestaetigung(umgebung):
    db, mcp = umgebung
    pid = db.save_profile({"name": "Einziges"})
    erg = _call(mcp, "profil_loeschen", {"profil_id": pid})
    assert erg["status"] == "vorschau" and erg["einziges_profil"] is True
    assert db.get_profile() is not None


def test_h27_unbekanntes_profil_wird_benannt(umgebung):
    db, mcp = umgebung
    db.save_profile({"name": "Test"})
    erg = _call(mcp, "profil_loeschen", {"profil_id": "gibtsnicht", "bestaetigung": True})
    assert "fehler" in erg


def _alle_werkzeuge(mcp) -> dict:
    async def _run():
        return {t.name: t for t in await mcp.list_tools()}
    return asyncio.run(_run())


def test_h27_jedes_destruktiv_klingende_werkzeug_ist_eingeordnet(umgebung):
    from bewerbungs_assistent.services import werkzeug_schutz as ws
    _, mcp = umgebung
    fehlt = sorted(n for n in _alle_werkzeuge(mcp)
                   if ws.DESTRUKTIV_MUSTER.search(n) and not ws.einordnung(n)
                   and n not in ws.NICHT_DESTRUKTIV)
    assert not fehlt, (f"Nicht eingeordnet: {fehlt} — in services/werkzeug_schutz "
                       "ZWEISTUFIG, KLEIN_SOFORT oder UMKEHRBAR eintragen.")


def test_h27_zweistufige_werkzeuge_zeigen_ohne_parameter_nur_die_vorschau(umgebung):
    """An der echten Signatur: die Vorgabe ist die Vorschau."""
    from bewerbungs_assistent.services import werkzeug_schutz as ws
    _, mcp = umgebung
    werkzeuge = _alle_werkzeuge(mcp)
    falsch = []
    for name, param in ws.ZWEISTUFIG.items():
        if name not in werkzeuge:
            continue  # linienabhaengig (1.7 hat nicht alle)
        schema = (werkzeuge[name].parameters or {}).get("properties", {})
        assert param in schema, f"{name} hat keinen Parameter {param}"
        vorgabe = schema[param].get("default")
        erwartet = True if param == "dry_run" else (False, "")
        ok = vorgabe is True if param == "dry_run" else vorgabe in (False, "")
        if not ok:
            falsch.append(f"{name}.{param}={vorgabe!r} (erwartet {erwartet})")
    assert not falsch, falsch


def test_h27_annotations_sind_gesetzt(umgebung):
    _, mcp = umgebung
    w = _alle_werkzeuge(mcp)
    assert w["profil_loeschen"].annotations.destructiveHint is True
    assert w["bewerbungen_anzeigen"].annotations.readOnlyHint is True
    assert w["stellen_auto_aussortieren"].annotations.destructiveHint is False
    anzahl = sum(1 for t in w.values() if t.annotations is not None)
    assert anzahl >= 60, anzahl


def test_h27_annotations_registrierung_ist_verdrahtet():
    """DoD 8c: der Proxy muss in register_all wirklich benutzt werden."""
    quelle = (PAKET / "tools" / "__init__.py").read_text(encoding="utf-8")
    rumpf = quelle.split("def register_all", 1)[1]
    # H25 (#1087 G5): der Proxy bekommt die Datenbank fuer die KI-Sperre.
    assert "mcp = _AnnotierendesMCP(mcp, db)" in rumpf


# ══ H32 ═══════════════════════════════════════════════════════════════

def test_h32_kein_profil_bekommt_nur_verbphrasen():
    """Jeder Aufrufer mit Argument: kleingeschrieben, kein Werkzeugname,
    kein Satzende — sonst entsteht "Um <Satz>. zu koennen"."""
    befunde = []
    for datei in list((PAKET / "tools").glob("*.py")) + list((PAKET / "services").glob("*.py")):
        baum = ast.parse(datei.read_text(encoding="utf-8-sig"))
        for k in ast.walk(baum):
            if (isinstance(k, ast.Call) and getattr(k.func, "id", "") == "kein_profil"
                    and k.args):
                arg = k.args[0]
                if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                    befunde.append(f"{datei.name}: kein Literal")
                    continue
                t = arg.value
                if (not t or t[0].isupper() or "_" in t or t.rstrip().endswith((".", "!", "?"))):
                    befunde.append(f"{datei.name}: {t!r}")
    assert not befunde, befunde


def test_h32_der_gemeldete_satz_ist_weg(umgebung):
    _, mcp = umgebung
    erg = _call(mcp, "profil_einordnung")
    assert erg["status"] == "kein_profil"
    assert erg["erklaerung"] == "Um dein Profil einordnen zu koennen, braucht PBP zuerst ein Profil."


def test_h32_kein_profil_formuliert_richtig():
    from bewerbungs_assistent.services.nutzerfuehrung import kein_profil
    assert kein_profil("deine Notizen aufraeumen")["erklaerung"].startswith(
        "Um deine Notizen aufraeumen zu koennen")
