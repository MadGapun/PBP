"""beta.99 — #682: Outcome-Quoten + Segmentierung am PBP-Startdatum.

get_statistics() liefert expired_rate/rejection_rate/withdrawal_rate plus
einen `quoten`-Block (gesamt / seit_pbp / vor_pbp), segmentiert am
PBP-Startdatum nach applied_at.
"""
from __future__ import annotations


def _app(tmp_db, status, applied_at, interview=0):
    aid = tmp_db.add_application({"title": "X", "company": "Y", "status": status})
    conn = tmp_db.connect()
    conn.execute(
        "UPDATE applications SET status=?, applied_at=?, has_reached_interview=? WHERE id=?",
        (status, applied_at, interview, aid),
    )
    conn.commit()
    return aid


def _seed(tmp_db):
    tmp_db.create_profile("T", "t@example.com")
    tmp_db.set_pbp_first_active_at("2026-03-12")
    # Vor PBP (applied < 2026-03-12): 2 abgelaufen, 1 abgelehnt  (3 gesamt)
    _app(tmp_db, "abgelaufen", "2026-02-01")
    _app(tmp_db, "abgelaufen", "2026-02-15")
    _app(tmp_db, "abgelehnt", "2026-01-20")
    # Seit PBP (applied >= 2026-03-12): 1 abgelaufen, 2 abgelehnt, 1 zurueck,
    #   1 interview-erreicht (status interview), 1 angebot  (6 gesamt)
    _app(tmp_db, "abgelaufen", "2026-04-01")
    _app(tmp_db, "abgelehnt", "2026-03-20")
    _app(tmp_db, "abgelehnt", "2026-05-02")
    _app(tmp_db, "zurueckgezogen", "2026-04-10")
    _app(tmp_db, "interview", "2026-03-15", interview=1)
    _app(tmp_db, "angebot", "2026-05-20")


def test_quoten_block_vorhanden(tmp_db):
    _seed(tmp_db)
    s = tmp_db.get_statistics()
    assert "quoten" in s
    q = s["quoten"]
    assert q["pbp_start_datum"] == "2026-03-12"
    assert set(q) >= {"gesamt", "seit_pbp", "vor_pbp", "pbp_start_datum"}


def test_segment_seit_pbp_korrekt(tmp_db):
    _seed(tmp_db)
    seit = tmp_db.get_statistics()["quoten"]["seit_pbp"]
    assert seit["basis"] == 6
    assert seit["abgelaufen"] == 1
    assert seit["expired_rate"] == round(1 / 6 * 100, 1)  # 16.7
    assert seit["abgelehnt"] == 2
    assert seit["zurueckgezogen"] == 1
    assert seit["interview"] == 1
    assert seit["angebot"] == 1


def test_segment_vor_pbp_korrekt(tmp_db):
    _seed(tmp_db)
    vor = tmp_db.get_statistics()["quoten"]["vor_pbp"]
    assert vor["basis"] == 3
    assert vor["abgelaufen"] == 2
    assert vor["expired_rate"] == round(2 / 3 * 100, 1)  # 66.7


def test_gesamt_und_toplevel_rates(tmp_db):
    _seed(tmp_db)
    s = tmp_db.get_statistics()
    g = s["quoten"]["gesamt"]
    assert g["basis"] == 9
    assert g["abgelaufen"] == 3
    # Top-Level-Convenience spiegelt die Gesamt-Quote
    assert s["expired_rate"] == g["expired_rate"]
    assert s["rejection_rate"] == g["rejection_rate"]
    assert s["withdrawal_rate"] == g["withdrawal_rate"]


def test_expired_rate_seit_pbp_kleiner_als_vor_pbp(tmp_db):
    """Die Kern-Aussage von #682: weniger Versanden seit PBP."""
    _seed(tmp_db)
    q = tmp_db.get_statistics()["quoten"]
    assert q["seit_pbp"]["expired_rate"] < q["vor_pbp"]["expired_rate"]


def test_ohne_startdatum_keine_segmente(tmp_db):
    tmp_db.create_profile("T", "t@example.com")
    # kein set_pbp_first_active_at + keine Events -> start_datum None
    _app(tmp_db, "abgelehnt", "2026-04-01")
    q = tmp_db.get_statistics()["quoten"]
    # gesamt trotzdem berechnet, seit/vor leer (basis 0) wenn kein Startdatum
    assert q["gesamt"]["basis"] == 1
    if q["pbp_start_datum"] is None:
        assert q["seit_pbp"]["basis"] == 0
        assert q["vor_pbp"]["basis"] == 0
