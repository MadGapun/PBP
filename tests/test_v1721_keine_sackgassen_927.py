"""Tests fuer v1.7.21 — #927: keine Sackgassen im leeren Zustand.

Leitlinie: Benutzerfuehrung ist oberste Prioritaet — jeder Flow fuehrt
zum naechsten logischen Schritt. Gemessen am 18.08.2026 endeten 18 von
53 einstiegsnahen Tools in einer Sackgasse: technisch korrekt
(`{"anzahl": 0}`), aber ohne Antwort auf die Frage, die der Nutzer
wirklich hat — was kann ich hier tun?

Die Zielgruppe sind Menschen ohne Technikwissen. Fuer sie ist ein
leeres JSON-Objekt kein Ergebnis, sondern ein Stopp.
"""
import asyncio
import importlib
import json
import os
import shutil
import tempfile

import pytest


@pytest.fixture(scope="module")
def frisches_pbp():
    """Ein PBP wie nach der Installation: alles leer."""
    tmp = tempfile.mkdtemp(prefix="pbp_sackgasse_")
    os.environ["BA_DATA_DIR"] = tmp
    import bewerbungs_assistent.database as dbmod
    importlib.reload(dbmod)
    db = dbmod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmp) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    import bewerbungs_assistent.server as srv
    importlib.reload(srv)
    yield db, srv
    # ⛔ KEIN db.close() hier: alle Threads teilen sich eine Connection,
    # ein close() waehrend ein Hintergrund-Thread laeuft bringt SQLite
    # auf C-Ebene zum Absturz (Exit 139, CLAUDE.md-Regel seit beta.0).
    # Stattdessen die pbp-*-Threads auslaufen lassen, dann erst das
    # Verzeichnis entfernen — sonst meldet der CI-Runner
    # "unable to open database file" aus noch pollenden Threads.
    import threading
    for t in threading.enumerate():
        if t.name.startswith("pbp-") and t is not threading.current_thread():
            t.join(timeout=15)
    shutil.rmtree(tmp, ignore_errors=True)


def _call(srv, name, args=None):
    async def _run():
        tool = await srv.mcp.get_tool(name)
        res = await tool.run(args or {})
        return res.structured_content if hasattr(
            res, "structured_content") else res
    raw = asyncio.run(_run())
    if isinstance(raw, tuple):
        raw = raw[1] if len(raw) > 1 else raw[0]
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    return raw


# Worte, an denen man einen Wegweiser erkennt.
WEGWEISER = (
    "nutze", "rufe", "starte", "lege", "kannst du", "zuerst", "tipp",
    "hinweis", "empfehlung", "als naechstes", "bitte", "schritt",
    "beginne", "lade", "trage", "anlegen", "setzen", "so gehts",
    "ersterfassung", "naechster_schritt", "erklaerung",
)


def test_927_kein_profil_meldung_zeigt_den_weg():
    """Die haeufigste Einstiegs-Sackgasse: 'Kein aktives Profil.' ohne Ausweg."""
    from bewerbungs_assistent.services.nutzerfuehrung import kein_profil
    r = kein_profil("Dokumente analysieren")
    assert r["status"] == "kein_profil"
    assert "Dokumente analysieren" in r["erklaerung"]
    text = json.dumps(r, ensure_ascii=False).lower()
    assert "ersterfassung" in text, "der gefuehrte Weg muss genannt sein"
    assert "profil_erstellen" in text, "der manuelle Weg auch"


def test_927_leer_haengt_wegweiser_an_ohne_daten_zu_verlieren():
    from bewerbungs_assistent.services.nutzerfuehrung import leer
    r = leer({"anzahl": 0, "todos": []}, "Noch nichts da.", "Mach X.")
    assert r["anzahl"] == 0 and r["todos"] == []
    assert "Noch nichts da." in r["hinweis"] and "Mach X." in r["hinweis"]


def test_927_suchkriterien_leer_erklaert_den_naechsten_schritt(frisches_pbp):
    """Der wichtigste Einzelfall: ohne Suchkriterien findet die Suche nichts."""
    db, srv = frisches_pbp
    db.save_profile({"name": "Test"})
    r = _call(srv, "suchkriterien_anzeigen")
    text = json.dumps(r, ensure_ascii=False).lower()
    assert "hinweis" in r, r
    assert "keyword_vorschlaege" in text or "suchkriterien_setzen" in text


def test_927_todos_leer_erklaert_wozu_aufgaben_gut_sind(frisches_pbp):
    db, srv = frisches_pbp
    r = _call(srv, "todos_anzeigen")
    assert r["anzahl"] == 0
    assert "hinweis" in r, r
    assert "todo_anlegen" in json.dumps(r, ensure_ascii=False).lower()


def test_927_kein_einstiegs_tool_stuerzt_ab(frisches_pbp):
    """Ein frisches PBP darf bei keinem argumentlosen Tool abstuerzen."""
    db, srv = frisches_pbp

    async def _tools():
        # FastMCP-Versionen unterscheiden sich hier: aeltere kennen nur
        # list_tools() (Liste), neuere get_tools() (dict name -> Tool).
        # Dasselbe Muster wie in test_mcp_registry.py — sonst ist der
        # Test lokal gruen und auf dem CI-Runner rot.
        if hasattr(srv.mcp, "get_tools"):
            return dict(await srv.mcp.get_tools())
        return {t.name: t for t in await srv.mcp.list_tools()}

    tools = asyncio.run(_tools())
    tabu = ("loesch", "reset", "starten", "erstellen", "anlegen", "setzen",
            "speichern", "bearbeiten", "aendern", "bewerten", "senden",
            "install", "pair", "export", "import", "bereinigen", "heilen",
            "abgleichen", "reparieren", "umlaute", "wechseln", "ausfuehren",
            "verarbeiten", "markieren", "verknuepfen", "entknuepfen",
            "pause", "schreiben", "vorschlagen", "ableiten", "auswerten",
            "recherche", "suche", "check", "analyse", "extrahieren",
            "konvertieren", "erledigen", "reaktivieren", "dismiss",
            "hinfaellig", "kopieren", "fragen", "backtest", "berechnen",
            "aussortieren", "handoff", "workflow", "prompt", "ping",
            "diagnose")
    geprueft = 0
    for name, tool in tools.items():
        if any(t in name.lower() for t in tabu):
            continue
        if (getattr(tool, "parameters", None) or {}).get("required"):
            continue
        geprueft += 1
        try:
            _call(srv, name)
        except Exception as exc:  # pragma: no cover
            pytest.fail(f"{name} stuerzt im leeren Zustand ab: "
                        f"{type(exc).__name__}: {exc}")
    assert geprueft >= 20, f"zu wenige Tools geprueft ({geprueft})"
