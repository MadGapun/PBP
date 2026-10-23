"""#1148 Punkt 12: die sichtbare Werkzeugliste hat ein Budget.

Jedes Gespräch beginnt damit, dass Claude die Liste aller sichtbaren Werkzeuge liest: Namen, Beschreibungen, Eingabeschemata. Im
Alltagsmodus sind das rund 200 KB (etwa 50.000 Token) — vor der ersten Frage des Menschen. Das ließ sich zuletzt nur noch mit einem
Handgriff je Werkzeug ändern; ein neues Werkzeug mit zwei Seiten Parameterbeschreibung fiel nirgends auf.

Hier: gemessen wird die Liste, wie Claude sie sieht (Alltagsmodus: Wartung und Entwicklerwerkzeuge ausgeblendet, Schemata ohne Titel), und
gegen ein Budget gehalten. Wer es überschreitet, kürzt oder entscheidet bewusst, die Grenze anzuheben (mit Begründung im Commit).
"""
from __future__ import annotations

import asyncio
import json
import os

import pytest

import test_mcp_registry as reg
from bewerbungs_assistent.services import werkzeug_katalog

#: Zeichen der sichtbaren Liste (Name + Beschreibung + Eingabeschema als JSON) im Alltagsmodus. Gemessen 12.10.2026: rund 208.000
#: bei 256 sichtbaren Werkzeugen. Die Grenze liegt bewusst knapp darueber: ein neues Werkzeug passt hinein, ein ganzer Block nicht.
BUDGET_ZEICHEN = 218_000
#: ... und kein einzelnes Werkzeug traegt mehr als das (heute das groesste: ~3.800).
BUDGET_JE_WERKZEUG = 4_500


@pytest.fixture(scope="module")
def liste(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("liste1148")
    mcp, db = reg._build_test_server(tmp)
    werkzeug_katalog.sichtbarkeit_anwenden(mcp, False)

    async def _alle():
        return await mcp.list_tools()

    tools = asyncio.run(_alle())
    zeilen = {}
    for t in tools:
        d = {"name": t.name, "description": t.description or "", "inputSchema": getattr(t, "parameters", None) or {}}
        zeilen[t.name] = len(json.dumps(d, ensure_ascii=False))
    db.close()
    os.environ.pop("BA_DATA_DIR", None)
    return zeilen


def test_die_sichtbare_liste_haelt_das_budget(liste):
    gesamt = sum(liste.values())
    assert gesamt <= BUDGET_ZEICHEN, (
        f"Die sichtbare Werkzeugliste hat {gesamt} Zeichen (Budget {BUDGET_ZEICHEN}). Jedes Gespräch liest sie vollständig: kürzen "
        "(Beschreibungen in services/werkzeug_katalog.KURZ, Parameterbeschreibungen im Docstring) oder die Grenze mit Begründung anheben.")


def test_kein_einzelnes_werkzeug_sprengt_das_budget(liste):
    gross = {n: z for n, z in liste.items() if z > BUDGET_JE_WERKZEUG}
    assert not gross, gross


def test_die_messung_sieht_den_alltagsmodus(liste):
    """DoD 8c: gemessen wird die Liste, die ein Mensch im Alltag bekommt — Wartung ist ausgeblendet, die Zahl plausibel."""
    assert 200 <= len(liste) <= 290
    versteckt = (werkzeug_katalog.WARTUNG | werkzeug_katalog.ENTWICKLER) & set(liste)
    assert not versteckt, f"im Alltagsmodus sichtbar, obwohl Wartung/Entwickler: {sorted(versteckt)[:5]}"
    assert sum(liste.values()) > 100_000, "eine leere Messung haelt jedes Budget"
