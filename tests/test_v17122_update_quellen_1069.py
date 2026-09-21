"""#1069 — die Update-Pruefung hing an einer einzigen Quelle.

`/api/update-check` fragte ausschliesslich GitHub. Faellt die Quelle weg
(Repo privat, Umzug der Entwicklung, geaenderter Pfad), bleibt die
Anzeige stumm: `update_available` ist dauerhaft False, ohne
Fehlermeldung. Der Mensch merkt nicht, dass er nichts mehr erfaehrt —
#989 an der Update-Pruefung.

Gemessen am 21.09.2026: der im Issue genannte ELWOSA-Endpunkt antwortet
mit HTTP 404. Die Domain gibt es, die Route noch nicht. Er steht
trotzdem an erster Stelle — damit ist der Rueckfall auf GitHub von
Anfang an der reale Pfad und nicht nur eine Behauptung.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import update_quelle as uq  # noqa: E402


# ══ Die Linie ═══════════════════════════════════════════════════════

def test_1069_linie_aus_der_version():
    assert uq.linie_von("1.7.122") == "1.7"
    assert uq.linie_von("1.8.0b15") == "1.8"
    assert uq.linie_von("") == ""


def test_1069_eine_andere_linie_ist_kein_update():
    """AK 3: wer auf 1.7 sitzt, bekommt keine 1.8-Beta angeboten."""
    befund = uq.auswerten("elwosa", {"version": "1.8.0b16"}, "1.7.122", "1.7")
    assert befund is None
    befund = uq.auswerten("elwosa", {"version": "1.7.130"}, "1.7.122", "1.7")
    assert befund["version"] == "1.7.130"


def test_1069_ohne_linie_kein_filter():
    befund = uq.auswerten("github", {"tag_name": "v1.8.0"}, "1.7.122", "")
    assert befund["version"] == "1.8.0"


# ══ Die Antworten der Quellen ═══════════════════════════════════════

def test_1069_github_antwort():
    befund = uq.auswerten(
        "github",
        {"tag_name": "v1.7.130", "html_url": "https://example.com/r",
         "name": "Titel"}, "1.7.122", "1.7")
    assert befund["version"] == "1.7.130"
    assert befund["url"] == "https://example.com/r"
    assert befund["pause_s"] == uq.STANDARD_PAUSE_S


def test_1069_elwosa_antwort_mit_eigener_pause():
    """AK 2: `poll_after_seconds` der Antwort gilt, statt fester Stunde."""
    befund = uq.auswerten(
        "elwosa",
        {"version": "1.7.130", "download_url": "https://example.com/d",
         "notiz": "Neue Version", "poll_after_seconds": 7200},
        "1.7.122", "1.7")
    assert befund["pause_s"] == 7200
    assert befund["url"] == "https://example.com/d"
    assert befund["name"] == "Neue Version"


def test_1069_unsinnige_pause_faellt_auf_die_vorgabe():
    befund = uq.auswerten(
        "elwosa", {"version": "1.7.130", "poll_after_seconds": "bald"},
        "1.7.122", "1.7")
    assert befund["pause_s"] == uq.STANDARD_PAUSE_S
    # Und eine absurd kurze Pause wird nicht uebernommen — sonst fragt
    # PBP im Sekundentakt.
    befund = uq.auswerten(
        "elwosa", {"version": "1.7.130", "poll_after_seconds": 1},
        "1.7.122", "1.7")
    assert befund["pause_s"] >= 60


def test_1069_leere_antwort_ergibt_nichts():
    assert uq.auswerten("github", {}, "1.7.122", "1.7") is None
    assert uq.auswerten("elwosa", {"version": ""}, "1.7.122", "1.7") is None
    assert uq.auswerten("elwosa", None, "1.7.122", "1.7") is None


# ══ Die Quellenliste steht in der Konfiguration ═════════════════════

def test_1069_elwosa_zuerst_github_als_rueckfall():
    """AK 1: die Reihenfolge aus dem Issue."""
    namen = [q["name"] for q in uq.quellen(None)]
    assert namen == ["elwosa", "github"]


def test_1069_die_quellen_sind_konfigurierbar():
    """AK 2 des Issues: nicht fest verdrahtet. Eine Installation muss
    umziehen koennen, ohne auf ein Update zu warten — was bei einer
    kaputten Update-Pruefung ein Widerspruch waere."""
    class _DB:
        def get_setting(self, key, default=None):
            return [{"name": "eigen", "url": "https://example.com/v",
                     "art": "elwosa"}] if key == "update_quellen" else default

    assert [q["name"] for q in uq.quellen(_DB())] == ["eigen"]


def test_1069_unsinnige_konfiguration_faellt_auf_die_vorgabe():
    """Sonst steht eine Installation ohne jede Quelle da — und das waere
    genau der Zustand, den das Issue behebt."""
    class _DB:
        def get_setting(self, key, default=None):
            return ["kaputt", {"name": "ohne_url"}]

    assert [q["name"] for q in uq.quellen(_DB())] == ["elwosa", "github"]


# ══ Der Endpunkt ════════════════════════════════════════════════════

@pytest.fixture
def client(monkeypatch, tmp_path):
    import importlib
    import os
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    dash._update_cache.update({"ts": 0, "data": None, "pause_s": 3600})
    return TestClient(dash.app), dash


def _antwort(status=200, daten=None):
    class _Resp:
        status_code = status

        def json(self):
            return daten or {}
    return _Resp()


def test_1069_faellt_auf_die_zweite_quelle_zurueck(client, monkeypatch):
    """AK 5: mit ausgefallener erster Quelle funktioniert die Pruefung.

    Genau dieser Fall ist heute der reale: der ELWOSA-Endpunkt
    antwortet mit 404 (gemessen 21.09.2026)."""
    tc, dash = client
    gefragt = []

    class _Client:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def get(self, url, headers=None):
            gefragt.append(url)
            if "elwosa" in url:
                return _antwort(404)
            # Gleiche Linie wie die laufende Version — sonst greift zu
            # Recht der Linienfilter, und der Test pruefte ihn statt des
            # Rueckfalls.
            from bewerbungs_assistent import __version__ as _v
            hoch = uq.linie_von(_v) + ".999"
            return _antwort(200, {"tag_name": "v" + hoch,
                                  "html_url": "https://example.com/r"})

    monkeypatch.setattr("httpx.AsyncClient", _Client)
    res = tc.get("/api/update-check").json()
    assert len(gefragt) == 2 and "elwosa" in gefragt[0]
    assert res["update_available"] is True
    assert res["latest_version"].endswith(".999")
    assert res["quelle"] == "github"
    assert res["stand"] == "geprueft"
    # Der Fehlschlag der ersten Quelle bleibt sichtbar.
    assert res["quellen_versucht"][0]["status"] == 404


def test_1069_keine_quelle_antwortet_heisst_unbekannt(client, monkeypatch):
    """AK 4: kein stilles "alles aktuell". Das war der Kern des Issues."""
    tc, dash = client

    class _Client:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def get(self, url, headers=None):
            raise OSError("kein Netz")

    monkeypatch.setattr("httpx.AsyncClient", _Client)
    res = tc.get("/api/update-check").json()
    assert res["stand"] == "unbekannt"
    assert res["update_available"] is False
    assert "UNBEKANNT" in res["hinweis"]
    assert res["geprueft_am"]
    assert len(res["quellen_versucht"]) == 2


def test_1069_die_linie_geht_an_die_quelle(client, monkeypatch):
    """AK 3: der Endpunkt kann `?linie=` — also wird es gefragt."""
    tc, dash = client
    gefragt = []

    class _Client:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def get(self, url, headers=None):
            gefragt.append(url)
            from bewerbungs_assistent import __version__ as _v
            return _antwort(200, {"version": uq.linie_von(_v) + ".999"})

    monkeypatch.setattr("httpx.AsyncClient", _Client)
    res = tc.get("/api/update-check").json()
    assert "linie=" in gefragt[0]
    assert res["linie"] == uq.linie_von(res["current_version"])


def test_1069_geprueft_ohne_update_ist_nicht_unbekannt(client, monkeypatch):
    """Die Gegenrichtung: wer nachgesehen hat und nichts fand, sagt das
    auch so. Sonst waere "unbekannt" die neue stille Antwort."""
    tc, dash = client
    from bewerbungs_assistent import __version__

    class _Client:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def get(self, url, headers=None):
            return _antwort(200, {"version": __version__})

    monkeypatch.setattr("httpx.AsyncClient", _Client)
    res = tc.get("/api/update-check").json()
    assert res["stand"] == "geprueft"
    assert res["update_available"] is False
    assert "hinweis" not in res
