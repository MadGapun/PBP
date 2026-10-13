"""Auto-Update fuer Vorabversionen (opt-in) — #1199.

Eine installierte Vorab (Beta/RC) darf die naechste Vorab DERSELBEN Linie automatisch ziehen,
WENN der Schalter `auto_update_vorab` an ist. Eine stabile Installation wird nie auf eine Vorab
gezogen; Linienwechsel bleibt verboten; Signatur/Pruefsumme/Selbsttest bleiben Pflicht (anderswo
geprueft). Vorgabe des Schalters: aus.
"""
import pytest

from bewerbungs_assistent.services.auto_update import quelle, zustand
from bewerbungs_assistent.services.auto_update.fehler import UpdateFehler


def _eintrag(tag, **kw):
    e = {"tag_name": tag, "name": tag, "draft": False, "prerelease": False, "body": "Notizen",
         "published_at": "2026-10-13T10:00:00Z",
         "assets": [{"name": f"pbp-update-{tag[1:]}.zip", "size": 2_000_000},
                    {"name": "SHA256SUMS", "size": 100}, {"name": "SHA256SUMS.sig", "size": 90}]}
    e.update(kw)
    return e


# ── freigaben_lesen: Vorab nur mit Schalter ────────────────────────────────────────────

def test_freigaben_lesen_ohne_vorab_bleibt_stabil_only():
    daten = [_eintrag("v1.8.0-beta.19", prerelease=True), _eintrag("v1.8.0-rc.2", prerelease=True),
             _eintrag("v1.8.0")]
    assert [f.version for f in quelle.freigaben_lesen(daten)] == ["1.8.0"]


def test_freigaben_lesen_mit_vorab_behaelt_vorabversionen_aber_keine_entwuerfe():
    daten = [_eintrag("v1.8.0-beta.19", prerelease=True), _eintrag("v1.8.0-rc.2", prerelease=True),
             _eintrag("v1.8.0"), _eintrag("v1.8.1", draft=True), _eintrag("v1.8"), _eintrag("../x")]
    versionen = {f.version for f in quelle.freigaben_lesen(daten, vorab=True)}
    assert versionen == {"1.8.0-beta.19", "1.8.0-rc.2", "1.8.0"}


# ── kandidat_erlaubt: die Vorab-Regel ──────────────────────────────────────────────────

def test_kandidat_erlaubt_regeln():
    # Vorab-Ziel von einer Vorab: nur mit Schalter
    assert quelle.kandidat_erlaubt("1.8.0-rc.4", "1.8.0-rc.3", vorab=True) is True
    assert quelle.kandidat_erlaubt("1.8.0-rc.4", "1.8.0-rc.3", vorab=False) is False
    # Eine STABILE Installation wird nie auf eine Vorab gezogen, auch mit Schalter
    assert quelle.kandidat_erlaubt("1.8.1-rc.1", "1.8.0", vorab=True) is False
    # Eine stabile Ziel-Fassung ist immer erlaubt (stabil -> stabil, wie bisher)
    assert quelle.kandidat_erlaubt("1.8.0", "1.8.0-rc.3", vorab=False) is True
    assert quelle.kandidat_erlaubt("1.8.1", "1.8.0", vorab=False) is True


# ── neueste_fuer_linie: der Kern ────────────────────────────────────────────────────────

def test_beta_zieht_die_naechste_beta_nur_mit_schalter():
    daten = [_eintrag("v1.8.0-rc.3", prerelease=True), _eintrag("v1.8.0-rc.4", prerelease=True)]
    mit = quelle.freigaben_lesen(daten, vorab=True)
    assert quelle.neueste_fuer_linie(mit, "1.8.0-rc.3", vorab=True).version == "1.8.0-rc.4"
    # Ohne Schalter sieht dieselbe Installation nichts (Vorab schon beim Lesen gefiltert)
    ohne = quelle.freigaben_lesen(daten)
    assert quelle.neueste_fuer_linie(ohne, "1.8.0-rc.3") is None


def test_stabile_installation_nie_auf_vorab_auch_mit_schalter():
    daten = [_eintrag("v1.8.1-rc.1", prerelease=True)]
    mit = quelle.freigaben_lesen(daten, vorab=True)
    assert quelle.neueste_fuer_linie(mit, "1.8.0", vorab=True) is None


def test_beta_bevorzugt_die_stabile_wenn_es_sie_gibt():
    # 1.8.0 (stabil) schlaegt 1.8.0-rc.9 (Vorab) im Vergleich — die Beta landet auf der fertigen Version
    daten = [_eintrag("v1.8.0"), _eintrag("v1.8.0-rc.9", prerelease=True)]
    mit = quelle.freigaben_lesen(daten, vorab=True)
    assert quelle.neueste_fuer_linie(mit, "1.8.0-rc.3", vorab=True).version == "1.8.0"


def test_kein_linienwechsel_auch_mit_vorab():
    daten = [_eintrag("v1.9.0-rc.1", prerelease=True), _eintrag("v2.0.0-beta.1", prerelease=True)]
    mit = quelle.freigaben_lesen(daten, vorab=True)
    assert quelle.neueste_fuer_linie(mit, "1.8.0-rc.3", vorab=True) is None


def test_alte_beta_bekommt_weiter_die_fertige_version_ihrer_linie():
    # Bestehendes Verhalten (ohne Schalter): Beta -> Stable derselben Linie bleibt
    freigaben = quelle.freigaben_lesen([_eintrag("v1.8.0")])
    assert quelle.neueste_fuer_linie(freigaben, "1.8.0-beta.15").version == "1.8.0"


# ── asset_url: Vorab-Adresse erlaubt, Muell nicht ──────────────────────────────────────

def test_asset_url_erlaubt_gueltige_vorab_und_blockt_muell():
    assert quelle.asset_url("1.8.0-rc.4", "pbp-update-1.8.0-rc.4.zip").endswith("/v1.8.0-rc.4/pbp-update-1.8.0-rc.4.zip")
    assert quelle.asset_url("1.8.0-rc.4", "SHA256SUMS").endswith("/v1.8.0-rc.4/SHA256SUMS")
    with pytest.raises(UpdateFehler):
        quelle.asset_url("../1.8.0", "SHA256SUMS")
    with pytest.raises(UpdateFehler):
        quelle.asset_url("1.8.0-rc.4", "boese.exe")


# ── Schalter: Vorgabe aus, Setzen/Lesen ─────────────────────────────────────────────────

def test_vorab_schalter_vorgabe_aus_und_setzen(tmp_db):
    assert zustand.vorab(tmp_db) is False
    assert zustand.vorab_setzen(tmp_db, True) is True
    assert zustand.vorab(tmp_db) is True
    assert zustand.vorab_setzen(tmp_db, False) is False
    assert zustand.vorab(tmp_db) is False
