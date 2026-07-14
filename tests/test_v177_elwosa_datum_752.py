"""Tests fuer v1.7.7 — #752 (F27): Elwosa-Trigger mit Datums-Kontext.

Der Juli-Fall: die 'August.'-Linie aus dem holiday_summer-Pool feuerte im
Juli. Fix: {monat}-Platzhalter (Linie stimmt immer) + Engine-Guard gegen
konkrete falsche Monatsnamen + Status zeigt abgelaufene Pausen nicht mehr
als (vergangenes) Datum an.
"""
from datetime import datetime, timedelta

import pytest

from bewerbungs_assistent.services.elwosa import (
    MONATSNAMEN,
    _nennt_falschen_monat,
    fill_template,
)
from bewerbungs_assistent.services.elwosa_lines import CLUSTER_LINES, STATUS_LINES, WORLD_LINES


class TestMonatsPlatzhalter:
    def test_fill_template_setzt_echten_monat(self):
        heute = MONATSNAMEN[datetime.now().month - 1]
        out = fill_template("{monat}. Stellenmarkt im Off-Modus.", {})
        assert out.startswith(f"{heute}.")

    def test_keine_harte_august_linie_mehr_im_pool(self):
        """Die #752-Linie ist auf {monat} umgestellt — kein Pool darf noch
        einen hartkodierten falschen Monat ausliefern koennen."""
        summer = WORLD_LINES["holiday_summer"]
        assert any("{monat}" in line for line in summer)
        assert not any(line.startswith("August.") for line in summer)


class TestMonatsGuard:
    def test_falscher_monat_wird_erkannt(self):
        aktueller = datetime.now().month
        falscher = MONATSNAMEN[(aktueller % 12)]  # naechster Monat
        assert _nennt_falschen_monat(f"{falscher}. Alles ruhig.") is True

    def test_aktueller_monat_ist_erlaubt(self):
        aktueller_name = MONATSNAMEN[datetime.now().month - 1]
        assert _nennt_falschen_monat(f"{aktueller_name} laeuft gut.") is False

    def test_platzhalter_und_neutrale_linien_erlaubt(self):
        assert _nennt_falschen_monat("{monat}. Stellenmarkt im Off-Modus.") is False
        assert _nennt_falschen_monat("Hitze und Stille.") is False

    def test_monatsname_als_teilwort_zaehlt_nicht(self):
        # 'Maerz' in 'Schmaerzung'-artigen Kunstwoertern (Wortgrenzen)
        assert _nennt_falschen_monat("Vormaerzlich gestimmt.") is False

    def test_zukunfts_referenz_im_satz_bleibt_erlaubt(self):
        """'Kommt im September zurueck' ist eine legitime Zukunfts-Aussage —
        der Guard blockt nur Linien, die mit einem falschen Monat BEGINNEN."""
        assert _nennt_falschen_monat(
            "{monat}. Stellenmarkt im Off-Modus. Kommt im September zurueck mit Wucht.") is False

    def test_alle_kuratierten_linien_bestehen_den_guard(self):
        """Kein Pool darf eine Linie enthalten, die mit einem falschen
        konkreten Monatsnamen beginnt (das #752-Bug-Muster)."""
        alle_pools = {**CLUSTER_LINES, **STATUS_LINES, **WORLD_LINES}
        verstoesse = [
            (kind, line)
            for kind, lines in alle_pools.items()
            for line in lines
            if _nennt_falschen_monat(line)
        ]
        assert not verstoesse, f"Linien mit falschem Monats-Anfang: {verstoesse}"


class TestPausenAnzeige:
    @pytest.fixture
    def tmp_db(self, tmp_path):
        from bewerbungs_assistent.database import Database
        db = Database(tmp_path / "test.db")
        db.initialize()
        db.save_profile({"name": "Test"})
        assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
        yield db
        db.close()

    def test_abgelaufene_pause_nicht_mehr_angezeigt(self, tmp_db):
        """#752: paused_until in der Vergangenheit sah wie ein Datums-
        Berechnungsfehler aus — Status meldet abgelaufene Pausen jetzt leer."""
        from bewerbungs_assistent.services.elwosa import get_status
        vergangen = (datetime.now() - timedelta(days=30)).isoformat()
        tmp_db.set_elwosa_settings(paused_until=vergangen)
        status = get_status(tmp_db)
        assert status["is_paused"] is False
        assert status["paused_until"] == ""

    def test_aktive_pause_wird_angezeigt(self, tmp_db):
        from bewerbungs_assistent.services.elwosa import get_status
        zukunft = (datetime.now() + timedelta(hours=1)).isoformat()
        tmp_db.set_elwosa_settings(paused_until=zukunft)
        status = get_status(tmp_db)
        assert status["is_paused"] is True
        assert status["paused_until"] == zukunft
