"""Scraper-Robustheit B2 (#720 Fehlerklassifikation + #721 differenzierte Reaktion).

#720: classify_scraper_error leitet aus einer Exception eine Klasse ab
      (tot/blockiert/server_weg/kaputt). Rein additiv, kein Verhaltenswechsel.
#721: update_scraper_health reagiert differenziert nach Klasse —
      server_weg/blockiert werden pausiert-mit-Probe (kommen automatisch
      zurueck), tot/kaputt hart deaktiviert; ein einzelner Aussetzer
      deaktiviert nicht; fehlt die Klasse, bleibt das Altverhalten.

HARTE ISOLATIONS-REGEL: db.db_path muss im Temp-Verzeichnis liegen (BA_DATA_DIR).
"""
import importlib
import os
import shutil
import tempfile

import httpx
import pytest
from concurrent.futures import TimeoutError as FuturesTimeoutError


# ============= #720: classify_scraper_error =============

def _resp(code):
    return httpx.Response(code, request=httpx.Request("GET", "https://example.com"))


def test_720_klassifikation_http_codes():
    from bewerbungs_assistent.services.scraper_classifier import (
        classify_scraper_error, ERROR_CLASS_TOT, ERROR_CLASS_BLOCKIERT,
        ERROR_CLASS_SERVER_WEG, ERROR_CLASS_KAPUTT,
    )

    def status_err(code):
        return httpx.HTTPStatusError("x", request=_resp(code).request, response=_resp(code))

    assert classify_scraper_error(status_err(404)) == ERROR_CLASS_TOT
    assert classify_scraper_error(status_err(410)) == ERROR_CLASS_TOT
    assert classify_scraper_error(status_err(403)) == ERROR_CLASS_BLOCKIERT
    assert classify_scraper_error(status_err(429)) == ERROR_CLASS_BLOCKIERT
    assert classify_scraper_error(status_err(500)) == ERROR_CLASS_SERVER_WEG
    assert classify_scraper_error(status_err(503)) == ERROR_CLASS_SERVER_WEG
    # 4xx ausser 403/404/410/429 -> Adapter-/Request-Problem
    assert classify_scraper_error(status_err(400)) == ERROR_CLASS_KAPUTT
    assert classify_scraper_error(status_err(422)) == ERROR_CLASS_KAPUTT


def test_720_klassifikation_netzwerk_und_timeout():
    from bewerbungs_assistent.services.scraper_classifier import (
        classify_scraper_error, ERROR_CLASS_SERVER_WEG,
    )
    req = httpx.Request("GET", "https://example.com")
    assert classify_scraper_error(FuturesTimeoutError()) == ERROR_CLASS_SERVER_WEG
    assert classify_scraper_error(httpx.ConnectTimeout("t", request=req)) == ERROR_CLASS_SERVER_WEG
    assert classify_scraper_error(httpx.ReadTimeout("t", request=req)) == ERROR_CLASS_SERVER_WEG
    assert classify_scraper_error(httpx.ConnectError("c", request=req)) == ERROR_CLASS_SERVER_WEG
    assert classify_scraper_error(TimeoutError()) == ERROR_CLASS_SERVER_WEG


def test_720_klassifikation_kaputt():
    from bewerbungs_assistent.services.scraper_classifier import (
        classify_scraper_error, ERROR_CLASS_KAPUTT,
    )
    assert classify_scraper_error(ImportError("no module")) == ERROR_CLASS_KAPUTT
    assert classify_scraper_error(ValueError("parser broke")) == ERROR_CLASS_KAPUTT
    assert classify_scraper_error(KeyError("missing")) == ERROR_CLASS_KAPUTT
    assert classify_scraper_error(None) == ERROR_CLASS_KAPUTT


def test_720_classify_from_status():
    from bewerbungs_assistent.services.scraper_classifier import (
        classify_from_status, ERROR_CLASS_SERVER_WEG, ERROR_CLASS_KAPUTT,
    )
    assert classify_from_status("ok") is None
    assert classify_from_status("skipped") is None
    assert classify_from_status("timeout") == ERROR_CLASS_SERVER_WEG
    assert classify_from_status("error", ImportError()) == ERROR_CLASS_KAPUTT
    # Altdaten: error ohne Exception -> None (kein Regressionsrisiko)
    assert classify_from_status("error") is None


# ============= #721: differenzierte Reaktion =============

@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_720_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    from bewerbungs_assistent.database import Database
    d = Database()
    d.initialize()
    assert str(tmpdir) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    yield d
    d.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _row(db, name):
    conn = db.connect()
    return conn.execute("SELECT * FROM scraper_health WHERE scraper_name=?", (name,)).fetchone()


def _fail_n(db, name, error_class, n):
    out = None
    for _ in range(n):
        out = db.update_scraper_health(name, "error", count=0, time_s=5,
                                       detail="boom", error_class=error_class)
    return out


def test_721_server_weg_x5_pausiert_mit_probe(db):
    """5x server_weg -> pausiert (is_active=0) MIT reactivate_at, NICHT hart."""
    _fail_n(db, "ferchau", "server_weg", 5)
    r = _row(db, "ferchau")
    assert r["is_active"] == 0, "haette pausiert werden muessen"
    assert r["reactivate_at"], "pausiert-mit-Probe braucht reactivate_at"
    assert r["error_class"] == "server_weg"


def test_721_einzelner_aussetzer_deaktiviert_nicht(db):
    """Ein einzelner server_weg bei sonst gesunder Quelle bleibt aktiv."""
    _fail_n(db, "hays", "server_weg", 1)
    r = _row(db, "hays")
    assert r["is_active"] == 1, "darf nach einem Aussetzer nicht deaktivieren"
    assert not r["reactivate_at"]


def test_721_tot_x5_hart_deaktiviert(db):
    """5x tot (404) -> hart deaktiviert: is_active=0 OHNE reactivate_at."""
    _fail_n(db, "gulp", "tot", 5)
    r = _row(db, "gulp")
    assert r["is_active"] == 0
    assert not r["reactivate_at"], "tot kommt nicht von selbst zurueck"
    assert r["error_class"] == "tot"


def test_721_erfolg_nach_pause_reaktiviert(db):
    """Nach der Pause reaktiviert ein erfolgreicher Lauf die Quelle + reset."""
    _fail_n(db, "ingenieur_de", "server_weg", 5)
    assert _row(db, "ingenieur_de")["is_active"] == 0
    db.update_scraper_health("ingenieur_de", "ok", count=12, time_s=4)
    r = _row(db, "ingenieur_de")
    assert r["is_active"] == 1, "OK-Lauf muss reaktivieren"
    assert r["consecutive_failures"] == 0
    assert not r["reactivate_at"]


def test_721_fehlende_klasse_altverhalten(db):
    """Ohne Fehlerklasse (Altdaten) keine #721-Reaktion — Quelle bleibt aktiv,
    nur consecutive_failures zaehlt hoch (Backstop liegt im job_runner)."""
    _fail_n(db, "kimeta", None, 8)
    r = _row(db, "kimeta")
    assert r["is_active"] == 1, "ohne Klasse darf hier nicht deaktiviert werden"
    assert r["consecutive_failures"] == 8


def test_721_blockiert_respektiert_retry_after(db):
    """blockiert (429) mit gesetztem Retry-After pausiert bis zu diesem
    Zeitpunkt (nicht nur Standard-Backoff)."""
    future = "2099-01-01T00:00:00"
    # erst Quelle in die Naehe der Schwelle bringen, dann Retry-After setzen
    _fail_n(db, "solcom", "blockiert", 4)
    db.set_scraper_retry_after("solcom", future)
    db.update_scraper_health("solcom", "error", count=0, error_class="blockiert")
    r = _row(db, "solcom")
    assert r["is_active"] == 0
    assert r["reactivate_at"] == future, "Retry-After muss respektiert werden"


def test_721_detail_traegt_fehlerklasse(db):
    """last_status_detail enthaelt die Klasse plus Kurzdetail (#720)."""
    db.update_scraper_health("heise_jobs", "error", count=0,
                             detail="timeout 90s", error_class="server_weg")
    r = _row(db, "heise_jobs")
    assert "server_weg" in (r["last_status_detail"] or "")
    assert r["error_class"] == "server_weg"
