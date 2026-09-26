"""H33 (#1089) — echte Umlaute in den Texten, die Claude liest.

Werkzeug- und Parameterbeschreibungen, Antworten, Prompts und die
Server-Anleitung. Die Falle: in diesen Texten stehen Werte, die Claude
zurueckschickt — Status (`zurueckgezogen`), Aktionen (`loeschen`),
Gehaltsarten (`jaehrlich`), Parameternamen. Die bleiben in Umschrift.
"""
from __future__ import annotations

import asyncio
import importlib.util
import re
from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


def _pruefer():
    spec = importlib.util.spec_from_file_location(
        "ui_texte_pruefen_h33", _repo() / "scripts" / "ui_texte_pruefen.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_h33_pruefer_liest_werkzeugbeschreibungen_und_prompts():
    """DoD 8c: der Pruefer laeuft ueber die echten Dateien."""
    p = _pruefer()
    texte = list(p.claude_texte())
    namen = {pf.name for pf, _, _ in texte}
    assert {"bewerbungen.py", "jobs.py", "prompts.py", "server.py"} <= namen
    assert any(t.startswith("Löscht einen Termin") for _, _, t in texte)
    assert len(texte) > 500


def test_h33_geschuetzt_sind_werte_nicht_woerter():
    p = _pruefer()
    werte = p.geschuetzte_werte()
    for wert in ("zurueckgezogen", "zweitgespraech", "loeschen", "hinzufuegen",
                 "jaehrlich", "stuendlich", "begruendung"):
        assert wert in werte, wert
    # Lokale Variablen und Stoppwortlisten schuetzen kein Prosawort.
    for wort in ("fuer", "ueber", "koennen", "waehrend", "naechste"):
        assert wort not in werte, wort
    # Suchmuster in langen Wortlisten (Mail-Erkennung) sind keine Werte,
    # auch wenn ein Vergleich sie nennt.
    for wort in ("gespraech", "rueckfrage"):
        assert wort not in werte, wort


def test_h33_pruefer_meldet_und_laesst_werte_stehen():
    p = _pruefer()
    assert list(p.claude_umlaut_funde("Loescht den Eintrag.")) == ["Loescht"]
    assert not list(p.claude_umlaut_funde("Setzt den Status auf 'zurueckgezogen'."))
    assert not list(p.claude_umlaut_funde("Status: offen, beworben, zurueckgezogen."))
    assert not list(p.claude_umlaut_funde("begruendung: Freitext"))
    assert not list(p.claude_umlaut_funde("Aufruf: aufgaben_uebersicht()"))


def test_h33_pruefer_findet_umschrift_in_einem_werkzeug(tmp_path, monkeypatch):
    p = _pruefer()
    datei = tmp_path / "werkzeug.py"
    datei.write_text(
        'def register(mcp):\n'
        '    @mcp.tool()\n'
        '    def termin_weg(aktion: str = "loeschen"):\n'
        '        """Loescht einen Termin."""\n'
        '        if aktion == "zurueckgezogen":\n'
        '            return {"hinweis": "Der Termin ist geloescht."}\n',
        encoding="utf-8")
    monkeypatch.setattr(p, "REPO", tmp_path)
    monkeypatch.setattr(p, "claude_dateien", lambda: [datei])
    monkeypatch.setattr(p, "_GESCHUETZT", None)
    monkeypatch.setattr(p, "BACKEND_DATEIEN", [])
    monkeypatch.setattr(p, "UI_DATEIEN", [])
    monkeypatch.setattr(p, "katalog_texte", lambda: [])
    leer = tmp_path / "impulse.json"
    leer.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(p, "TAGESIMPULSE", leer)
    monkeypatch.setattr(p, "BACKEND", tmp_path)
    funde = p.pruefen()
    woerter = sorted(re.search(r"'([^']+)'", f).group(1) for f in funde)
    assert woerter == ["Loescht", "geloescht"], funde


def test_h33_parameternamen_bleiben_ascii():
    """Ein Umlaut im Parameternamen macht ein Werkzeug fuer die API
    ungueltig (#1062). Die Umstellung hat keinen angefasst."""
    from bewerbungs_assistent import server

    async def _alle():
        return await server.mcp.list_tools()
    for werkzeug in asyncio.run(_alle()):
        schema = werkzeug.parameters or {}
        for name in (schema.get("properties") or {}):
            assert re.fullmatch(r"[A-Za-z0-9_]+", name), (werkzeug.name, name)


def test_h33_lokale_ki_bleibt_ausgenommen():
    """Prompts an die lokale KI sind an ihrem Modell gemessen (#787)."""
    p = _pruefer()
    assert {"llm_service.py", "elwosa_dialog.py"} <= p.CLAUDE_AUSGENOMMEN
    assert not any(pf.name == "llm_service.py" for pf in p.claude_dateien())
