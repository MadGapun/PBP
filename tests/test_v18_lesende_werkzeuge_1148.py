"""#1148 Punkt 5: „Lesende“ Werkzeuge schreiben nichts — oder stehen mit Begründung auf einer kurzen, benannten Liste.

Die Annotationen (`readOnlyHint`) entstehen aus Namensmustern (`services/werkzeug_schutz.py`). Ein Muster kann irren: `ollama_kontext`
hieß „nur lesend“ und schrieb mit `aktion='setzen'`; `suchprofil_lesen` legte beim Lesen eine Zeile an. Dieser Test geht den anderen
Weg: er ruft JEDES Werkzeug, das die Annotation „nur lesend“ trägt und ohne Pflichtangaben aufrufbar ist, auf einer Datenbank mit
Profil auf und vergleicht die Datenbank davor und danach (Zeilenzahl je Tabelle und alle Einstellungen).

Was dabei etwas schreibt, steht in `ERLAUBT` — mit Grund. Eine neue Zeile dort ist eine Entscheidung, kein Versehen.
"""
from __future__ import annotations

import asyncio
import os
import re

import pytest

import test_mcp_registry as reg
from bewerbungs_assistent.services.werkzeug_schutz import annotations_fuer

#: Werkzeug -> (Tabellen/Einstellungen, die sich aendern duerfen, Grund). Nur idempotente Vorgaben und abgeleitete Zwischenspeicher.
ERLAUBT = {
    "profil_status": (
        {"settings:datenschutz_hinweis_gezeigt"},
        "der einmalige Datenschutz-Hinweis wird als „gezeigt“ vermerkt (einmal, danach nie wieder; services/datenschutz.einmaliger_hinweis)"),
    "kontakt_kategorien_auflisten": (
        {"contact_categories"},
        "die sieben Standard-Kategorien werden beim ersten Aufruf angelegt (idempotent, `_ensure_default_categories`)"),
    "stellen_anzeigen": (
        {"settings:neigung_profil_cache"},
        "das Neigungsprofil (aus beworbenen Stellen abgeleitet) wird mit Zeitstempel zwischengespeichert; rein abgeleitet, nie Nutzerdaten"),
}


def _stand(db) -> dict:
    """Zeilenzahl je Tabelle und alle Einstellungen — mehr braucht der Vergleich nicht."""
    conn = db.connect()
    stand = {}
    tabellen = [r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
    for name in tabellen:
        try:
            stand[name] = conn.execute(f'SELECT COUNT(*) AS n FROM "{name}"').fetchone()["n"]  # noqa: S608 -- Tabellennamen aus sqlite_master
        except Exception:  # noqa: BLE001
            stand[name] = -1
    # Einstellungen einzeln (ohne das Profil-Praefix): so benennt eine Aenderung den Schluessel, nicht „irgendeine Einstellung“
    try:
        for r in conn.execute("SELECT key, value FROM settings").fetchall():
            stand["settings:" + re.sub(r"^[0-9a-f]{8}:", "", r["key"])] = r["value"]
    except Exception:  # noqa: BLE001
        pass
    stand.pop("settings", None)
    return stand


def _geaendert(vorher: dict, nachher: dict) -> set:
    return {k for k in set(vorher) | set(nachher) if vorher.get(k) != nachher.get(k)}


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("lesend1148")
    mcp, db = reg._build_test_server(tmp)
    assert str(tmp) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau", "email": "erika@example.com"})
    yield mcp, db
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


def _lesende(mcp):
    async def _alle():
        return await mcp.list_tools() if hasattr(mcp, "list_tools") else list((await mcp.get_tools()).values())

    ergebnis = []
    for t in asyncio.run(_alle()):
        if not annotations_fuer(t.name).get("readOnlyHint"):
            continue
        pflicht = (getattr(t, "parameters", None) or {}).get("required", []) or []
        ergebnis.append((t.name, bool(pflicht)))
    return sorted(ergebnis)


def test_es_gibt_lesende_werkzeuge_ohne_pflichtangaben(umgebung):
    """DoD 8c: ein Test, der nichts findet, prueft nichts."""
    mcp, _ = umgebung
    aufrufbar = [n for n, pflicht in _lesende(mcp) if not pflicht]
    assert len(aufrufbar) >= 25, aufrufbar


def test_lesende_werkzeuge_schreiben_nichts_ausser_der_benannten_liste(umgebung):
    mcp, db = umgebung
    funde = {}
    for name, pflicht in _lesende(mcp):
        if pflicht:
            continue
        vorher = _stand(db)
        try:
            asyncio.run(reg._run_tool(mcp, name, {}))
        except Exception:  # noqa: BLE001 -- ein Werkzeug, das ohne Angaben scheitert, hat auch nichts geschrieben
            pass
        veraendert = _geaendert(vorher, _stand(db))
        erlaubt = ERLAUBT.get(name, (set(), ""))[0]
        if veraendert - erlaubt:
            funde[name] = sorted(veraendert - erlaubt)
    assert not funde, ("Diese als „nur lesend“ markierten Werkzeuge haben beim Aufruf in die Datenbank geschrieben — entweder das "
                       f"Schreiben entfernen oder in ERLAUBT mit Grund eintragen: {funde}")


def test_jeder_eintrag_der_erlaubnisliste_ist_ein_lesendes_werkzeug_mit_grund(umgebung):
    mcp, _ = umgebung
    lesend = {n for n, _ in _lesende(mcp)}
    for name, (was, grund) in ERLAUBT.items():
        assert name in lesend, f"{name} steht auf der Liste, ist aber nicht (mehr) als lesend markiert"
        assert was and len(grund) > 20, name


def test_ein_schreibendes_werkzeug_faellt_auf(umgebung, monkeypatch):
    """Gegenprobe: die Pruefung sieht einen Schreibzugriff (sonst waere ihr Gruen nichts wert)."""
    mcp, db = umgebung
    vorher = _stand(db)
    db.set_setting("zz_test_schreibt", "ja")
    try:
        assert "settings:zz_test_schreibt" in _geaendert(vorher, _stand(db))
    finally:
        db.set_setting("zz_test_schreibt", None)
