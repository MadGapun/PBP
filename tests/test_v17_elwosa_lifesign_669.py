"""Tests fuer Issue #669 (beta.88) — Elwosa KI-freies Safety-Net.

Zwei Bausteine, beide ohne Ollama:
- _pick_valid_line: Validierungs-Retry (eine kaputte Linie -> kein Schweigen)
- ensure_daily_lifesign: garantiert mind. 1 Linie/Tag (Morgen-Linie auch
  wenn die Engine erst nachmittags tickt)
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_elwosa669_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    from bewerbungs_assistent.database import Database
    database = Database()
    database.initialize()
    database.save_profile({"name": "Test"})
    # Ruhezeit (v1.7.12/#822) deaktivieren ("0-0" = Start==Ende = nie
    # aktiv) — sonst sind Elwosa-Tests nachts rot, und ein relatives
    # Fenster kollidiert mit Tests, die die Uhr auf 9:00 faken (#853).
    database.set_profile_setting("elwosa_ruhezeit", "0-0")
    yield database
    database.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ── _pick_valid_line ─────────────────────────────────────────────────────


def test_pick_valid_line_ueberspringt_kaputte_linie(db):
    """Eine Linie die die Sprach-DNA verletzt wird uebersprungen, eine
    valide wird zurueckgegeben — kein None trotz kaputter Linie im Pool."""
    from bewerbungs_assistent.services import elwosa

    # "!" ist verboten (keine Ausrufezeichen). Valide Linie ohne.
    pool = ["Kaputt mit Ausrufezeichen!", "Eine ruhige, valide Linie"]
    line = elwosa._pick_valid_line(db, pool, {})
    assert line == "Eine ruhige, valide Linie"


def test_pick_valid_line_alle_kaputt_gibt_none(db):
    from bewerbungs_assistent.services import elwosa
    pool = ["Kaputt!", "Auch kaputt!!!"]
    line = elwosa._pick_valid_line(db, pool, {})
    assert line is None


def test_pick_valid_line_leerer_pool(db):
    from bewerbungs_assistent.services import elwosa
    assert elwosa._pick_valid_line(db, [], {}) is None


# ── ensure_daily_lifesign ────────────────────────────────────────────────


def test_lifesign_postet_wenn_heute_noch_nichts(db, monkeypatch):
    """Wenn heute noch keine Nachricht: Lebenszeichen wird gepostet."""
    from bewerbungs_assistent.services import elwosa

    db.set_elwosa_settings(enabled=True, tonfall_modus="standard")

    # Uhrzeit auf Vormittag (09:00) fixieren -> Morgen-Linie, hour >= 6.
    # Datum = HEUTE (UTC), damit es zum realen created_at der gerade
    # geposteten Nachricht passt: _count_all_today() vergleicht ueber
    # die UTC-Tagesgrenze, ein hartkodiertes Datum wuerde nur am selben
    # Tag passen (beta.92 Test-Fix gegen Datum-Rollover).
    import datetime as _dt

    _today = _dt.datetime.now(_dt.timezone.utc).date()

    class _FakeDt(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            base = _dt.datetime(_today.year, _today.month, _today.day, 9, 0, 0)
            return base if tz is None else base.replace(tzinfo=tz)

    monkeypatch.setattr(elwosa, "datetime", _FakeDt)

    msg_id = elwosa.ensure_daily_lifesign(db)
    assert msg_id is not None
    assert elwosa._count_all_today(db) >= 1


def test_lifesign_postet_auch_nachmittags(db, monkeypatch):
    """#669-Kernfall: Engine tickt erst nachmittags (14 Uhr) -> trotzdem
    Lebenszeichen (idle), nicht den ganzen Tag Schweigen."""
    from bewerbungs_assistent.services import elwosa

    db.set_elwosa_settings(enabled=True, tonfall_modus="standard")

    import datetime as _dt

    class _FakeDt(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            base = _dt.datetime(2026, 6, 2, 14, 0, 0)  # Dienstag 14:00
            return base if tz is None else base.replace(tzinfo=tz)

    monkeypatch.setattr(elwosa, "datetime", _FakeDt)

    msg_id = elwosa.ensure_daily_lifesign(db)
    assert msg_id is not None


def test_lifesign_kein_doppel_wenn_schon_gepostet(db, monkeypatch):
    """Wenn heute schon eine Nachricht da ist: kein zweites Lebenszeichen."""
    from bewerbungs_assistent.services import elwosa

    db.set_elwosa_settings(enabled=True, tonfall_modus="standard")
    # Eine Nachricht direkt anlegen
    db.add_elwosa_message(content="Schon da heute", trigger_kind="manual_via_claude")

    import datetime as _dt

    class _FakeDt(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            base = _dt.datetime(2026, 6, 2, 10, 0, 0)
            return base if tz is None else base.replace(tzinfo=tz)

    monkeypatch.setattr(elwosa, "datetime", _FakeDt)

    msg_id = elwosa.ensure_daily_lifesign(db)
    assert msg_id is None


def test_lifesign_tiefe_nacht_kein_post(db, monkeypatch):
    """Vor 6 Uhr kein erzwungenes Lebenszeichen."""
    from bewerbungs_assistent.services import elwosa

    db.set_elwosa_settings(enabled=True, tonfall_modus="standard")

    import datetime as _dt

    class _FakeDt(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            base = _dt.datetime(2026, 6, 2, 3, 0, 0)  # 03:00 nachts
            return base if tz is None else base.replace(tzinfo=tz)

    monkeypatch.setattr(elwosa, "datetime", _FakeDt)

    msg_id = elwosa.ensure_daily_lifesign(db)
    assert msg_id is None


def test_lifesign_respektiert_disabled(db, monkeypatch):
    from bewerbungs_assistent.services import elwosa
    db.set_elwosa_settings(enabled=False)

    import datetime as _dt

    class _FakeDt(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            base = _dt.datetime(2026, 6, 2, 9, 0, 0)
            return base if tz is None else base.replace(tzinfo=tz)

    monkeypatch.setattr(elwosa, "datetime", _FakeDt)

    assert elwosa.ensure_daily_lifesign(db) is None
