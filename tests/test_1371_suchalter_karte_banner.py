"""#1371: der Satz fuer Claude nennt das wirkliche Alter der letzten Suche;
Karte ("Naechster Schritt") und Banner melden fuer jedes Alter dasselbe."""
import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from bewerbungs_assistent.services import workspace_service as ws
from bewerbungs_assistent.services.search_service import (
    SUCHE_DRINGEND_NACH_TAGEN, alter_der_suche_text, get_search_status)

JETZT = datetime(2026, 11, 11, 12, 0, 0)
ALTER = [1, 3, 7, 30]
WURZEL = Path(__file__).resolve().parent.parent


def _status(tage):
    return get_search_status((JETZT - timedelta(days=tage)).isoformat(), now=JETZT)


def _lage(tage, monkeypatch):
    monkeypatch.setattr(ws, "get_profile_completeness", lambda p: {"completeness": 100, "complete": 9, "total": 9, "checks": {}})
    return ws.build_workspace_summary(
        {"name": "Test Person"}, [], [], {"active": 3, "total": 5},
        _status(tage), {"due": 0, "total": 0})


class _Db:
    def get_search_criteria(self):
        return {"keywords_muss": ["x"]}


def _satz(tage, monkeypatch):
    return ws.naechster_schritt(_Db(), _lage(tage, monkeypatch))


@pytest.mark.parametrize("tage,erwartet", [
    (0, "war heute"), (1, "war gestern"), (3, "war vor 3 Tagen"),
    (7, "war vor 7 Tagen"), (30, "war vor 30 Tagen"), (None, "ist schon länger her")])
def test_alter_als_satzteil(tage, erwartet):
    assert alter_der_suche_text(tage) == erwartet


@pytest.mark.parametrize("tage", [7, 30])
def test_satz_nennt_das_wirkliche_alter(tage, monkeypatch):
    s = _satz(tage, monkeypatch)
    assert s["stufe"] == "jobsuche_erneuern"
    assert f"Die letzte Suche war vor {tage} Tagen." in s["text"]


@pytest.mark.parametrize("tage", [1, 3])
def test_die_karte_meldet_vor_der_grenze_keine_erneuerung(tage, monkeypatch):
    assert _lage(tage, monkeypatch)["readiness"]["stage"] != "jobsuche_erneuern"


@pytest.mark.parametrize("tage", [1, 3, 7, 30])
def test_eine_woche_steht_nur_da_wenn_es_stimmt(tage, monkeypatch):
    # Der Satz fuer jedes Alter, auch wenn die Stufe erzwungen wird.
    lage = _lage(tage, monkeypatch)
    lage["readiness"] = {"stage": "jobsuche_erneuern"}
    text = ws.naechster_schritt(_Db(), lage)["text"]
    assert "älter als eine Woche" not in text
    assert ("gestern" in text) if tage == 1 else (f"vor {tage} Tagen" in text)


def test_nie_gesucht_bleibt_eigener_satz(monkeypatch):
    monkeypatch.setattr(ws, "get_profile_completeness", lambda p: {"completeness": 100, "complete": 9, "total": 9, "checks": {}})
    lage = ws.build_workspace_summary({"name": "T"}, [], [], {"active": 3, "total": 5},
                                      get_search_status(None), {"due": 0, "total": 0})
    assert "Es lief noch keine Suche." in ws.naechster_schritt(_Db(), lage)["text"]


def test_gegenprobe_die_alte_formulierung_faellt_auf():
    """Die feste Formulierung darf nirgends im Quelltext stehen."""
    quelle = (Path(ws.__file__)).read_text(encoding="utf-8")
    assert "ist älter als eine Woche" not in quelle


NODE_PROBE = r"""
import { hinweisFuer } from "%s";
const jetzt = new Date("2026-11-11T12:00:00");
const out = {};
for (const [tage, status] of %s) {
  const h = hinweisFuer({ seite: "dashboard", verbunden: true, hatProfil: true, quellenAktiv: 3,
    letzteSucheAm: new Date(jetzt.getTime() - tage * 86400000).toISOString(),
    sucheStatus: status, sucheTage: tage }, jetzt);
  out[tage] = h ? { id: h.id, titel: h.titel, aktionen: (h.aktionen || []).map((a) => a.art) } : null;
}
console.log(JSON.stringify(out));
"""


def test_karte_und_banner_melden_dasselbe():
    """Banner aus dem Server-Status (Node) gegen die Stufe der Karte (Python)."""
    paare = [[t, _status(t)["status"]] for t in ALTER]
    js = (WURZEL / "frontend/src/lib/hinweisZone.js").as_uri()
    probe = NODE_PROBE % (js, json.dumps(paare))
    erg = subprocess.run(["node", "--input-type=module", "-e", probe], capture_output=True,
                         text=True, encoding="utf-8", check=True, cwd=str(WURZEL))
    banner = json.loads(erg.stdout)
    mp = pytest.MonkeyPatch()
    try:
        for t in ALTER:
            karte = _lage(t, mp)["readiness"]["stage"] == "jobsuche_erneuern"
            assert (banner[str(t)] is not None) == karte, f"{t} Tage: Karte={karte}, Banner={banner[str(t)]}"
            if karte:
                assert banner[str(t)]["titel"] == f"Letzte Jobsuche vor {t} Tagen"
                assert banner[str(t)]["aktionen"] == ["jobsuche", "prompt"]
    finally:
        mp.undo()


def test_grenze_kommt_aus_einer_stelle():
    assert SUCHE_DRINGEND_NACH_TAGEN == 7
    assert _status(6)["status"] == "veraltet" and _status(7)["status"] == "dringend"
