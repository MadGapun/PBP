"""#1297, Abnahme-Kommentar vom 09.11.2026 (beobachtet auf 1.8.2).

1. Ein abgeschalteter Grund wird nirgends angeboten.
2. Sonderfall: der Grund wurde bis 1.8.2 als Zeile GELOESCHT (er war still als
   eigener Grund entstanden). Beim Einsaeen der Standardgruende darf er nicht
   als aktiver Grund zurueckkommen - ein geloeschter Grund gilt als abgeschaltet.
   Erkennbar ist das Loeschen daran, dass Stellen mit dem Grund aussortiert sind,
   seine Zeile aber fehlt.
3. Aktive eigene Gruende stehen in `verfuegbare_gruende`.
4. Wiedergaenger-k.o. der Fit-Analyse und die Hinweise in `stellen_anzeigen`
   lesen keine abgeschalteten Gruende mehr.
"""
from __future__ import annotations

import importlib
import json
import os

import pytest

from test_v183_ablehnungsgruende_abschaltbar_1297 import (  # noqa: F401
    _abschalten, _id, _stelle, _werkzeuge, db)


def _neustart(db):
    db.initialize()


def _zeile_loeschen(db, label):
    conn = db.connect()
    conn.execute("DELETE FROM dismiss_reasons WHERE LOWER(label)=?", (label,))
    conn.commit()


def _zeile(db, label):
    return next((r for r in db.get_dismiss_reasons() if r["label"] == label), None)


# ------------------------------------------------ 2. geloescht = abgeschaltet

@pytest.mark.parametrize("gespeichert", [
    "kein_hochschulabschluss",
    json.dumps(["zu_junior", "kein_hochschulabschluss"]),
])
def test_geloeschter_benutzter_grund_kommt_abgeschaltet(db, gespeichert):
    from bewerbungs_assistent.services import ablehnungsgruende as ag
    h = _stelle(db, "g1")
    conn = db.connect()
    conn.execute("UPDATE jobs SET is_active=0, dismiss_reason=? WHERE hash=?", (gespeichert, h))
    conn.commit()
    _zeile_loeschen(db, "kein_hochschulabschluss")
    _neustart(db)
    z = _zeile(db, "kein_hochschulabschluss")
    assert z is not None and not z["is_active"]
    assert "kein_hochschulabschluss" not in ag.waehlbare_gruende(db)
    # Der Bestand bleibt, wie er ist.
    assert conn.execute("SELECT dismiss_reason FROM jobs WHERE hash=?", (h,)).fetchone()[0] == gespeichert
    # Ein weiterer Neustart schaltet ihn nicht wieder ein.
    _neustart(db)
    assert not _zeile(db, "kein_hochschulabschluss")["is_active"]


def test_nie_benutzter_fehlender_grund_kommt_eingeschaltet(db):
    from bewerbungs_assistent.services import ablehnungsgruende as ag
    _zeile_loeschen(db, "kein_hochschulabschluss")
    _neustart(db)
    assert _zeile(db, "kein_hochschulabschluss")["is_active"]
    assert "kein_hochschulabschluss" in ag.waehlbare_gruende(db)


def test_aehnlicher_name_zaehlt_nicht_als_gebrauch(db):
    """`duplikat_bewerbung` ist nicht `duplikat` (Teilwort im LIKE)."""
    h = _stelle(db, "g2")
    conn = db.connect()
    conn.execute("UPDATE jobs SET is_active=0, dismiss_reason='duplikat_bewerbung' WHERE hash=?", (h,))
    conn.commit()
    _zeile_loeschen(db, "duplikat")
    _neustart(db)
    assert _zeile(db, "duplikat")["is_active"]


# ------------------------------------------------ 1. + 3. die angebotene Liste

def test_antwort_nennt_aktive_eigene_und_keinen_abgeschalteten(db):
    w = _werkzeuge(db)
    w["ablehnungsgrund_anlegen"](label="zu_hands_on")
    _abschalten(db, "kein_hochschulabschluss")
    h = _stelle(db, "l1")
    erg = w["stelle_einordnen"](job_hash=h, bewertung="passt_nicht", gruende=["zu_junior"])
    liste = erg.get("verfuegbare_gruende") or []
    assert "zu_hands_on" in liste
    assert "kein_hochschulabschluss" not in liste


# ------------------------------------------------ 4. Analyse und Stellenliste

def _drei_aussortierte(db, grund):
    for i in range(3):
        _stelle(db, f"w{i}", titel="PLM Berater Windchill (m/w/d)",
                firma="Beispielwerk AG", grund=grund)


def test_wiedergaenger_muster_ohne_abgeschalteten_grund(db):
    from bewerbungs_assistent.services.wiedergaenger import (
        find_wiedergaenger_pattern, firmen_historie)
    _drei_aussortierte(db, "falsches_fachgebiet")
    vorher = find_wiedergaenger_pattern(db, "Beispielwerk AG", "PLM Berater Windchill")
    assert vorher and vorher["top_grund"] == "falsches_fachgebiet"
    _abschalten(db, "falsches_fachgebiet")
    assert find_wiedergaenger_pattern(db, "Beispielwerk AG", "PLM Berater Windchill") is None
    # Die Firmen-Historie zeigt weiter, was war.
    assert firmen_historie(db, "Beispielwerk AG")


def test_stellen_anzeigen_haengt_kein_ko_an_abgeschalteten_grund(db):
    _drei_aussortierte(db, "falsches_fachgebiet")
    neu = _stelle(db, "n1", titel="PLM Berater Windchill (m/w/d)", firma="Beispielwerk AG")
    w = _werkzeuge(db)
    def _eintrag():
        erg = w["stellen_anzeigen"]()
        text = json.dumps(erg, ensure_ascii=False)
        return text
    assert "falsches_fachgebiet" in _eintrag()
    _abschalten(db, "falsches_fachgebiet")
    assert "falsches_fachgebiet" not in _eintrag()
