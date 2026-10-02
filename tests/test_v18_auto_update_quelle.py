"""Auto-Update (#1093): die feste Quelle — Adressen, Weiterleitungen, Laden, Liste der Veroeffentlichungen.

Akzeptanzkriterium 6: aus einer Quelle ausserhalb der festen GitHub-Adresse wird nie installiert, auch
wenn die Einstellung `update_quellen` anders gesetzt ist. Hier die Bausteine; die Gesamtprobe steht in
`test_v18_auto_update_installation.py`.
"""
import urllib.request

import pytest
from _au_hilfen import FakeAntwort, FakeOeffner

from bewerbungs_assistent.services.auto_update import quelle
from bewerbungs_assistent.services.auto_update.fehler import UpdateFehler


def _code(exc_info) -> str:
    return exc_info.value.code


# ── Adressen ──────────────────────────────────────────────────────────────────────────

def test_asset_url_baut_die_adresse_aus_festen_teilen():
    assert quelle.asset_url("1.8.1", "pbp-update-1.8.1.zip") == \
        "https://github.com/MadGapun/PBP/releases/download/v1.8.1/pbp-update-1.8.1.zip"
    assert quelle.asset_url("1.8.1", "SHA256SUMS").endswith("/v1.8.1/SHA256SUMS")
    assert quelle.asset_url("1.8.1", "SHA256SUMS.sig").endswith("/v1.8.1/SHA256SUMS.sig")


@pytest.mark.parametrize("version", ["1.8.1-beta.2", "1.8", "../1.8.1", "1.8.1/../../x", "1.8.1 ", "v1.8.1", "", None, "١.٨.١"])
def test_asset_url_verweigert_alles_was_keine_stabile_fassung_ist(version):
    with pytest.raises(UpdateFehler) as e:
        quelle.asset_url(version, "SHA256SUMS")
    assert _code(e) == "quelle_nicht_erlaubt"


@pytest.mark.parametrize("name", ["install.exe", "pbp-update-1.8.2.zip", "../SHA256SUMS", "SHA256SUMS ", "", "pbp-update-1.8.1.zip/../x"])
def test_asset_url_kennt_nur_die_drei_dateien_dieser_fassung(name):
    with pytest.raises(UpdateFehler) as e:
        quelle.asset_url("1.8.1", name)
    assert _code(e) == "quelle_nicht_erlaubt"


@pytest.mark.parametrize("url", [
    "http://github.com/MadGapun/PBP/releases/download/v1.8.1/SHA256SUMS",           # kein https
    "https://evil.example/MadGapun/PBP/releases/download/v1.8.1/SHA256SUMS",        # fremder Host
    "https://github.com.evil.example/x",                                            # Host nur aehnlich
    "https://user:pw@github.com/x",                                                 # Zugang in der Adresse
    "https://github.com:8443/x",                                                    # fremder Port
    "https://objects.githubusercontent.com/x",                                      # nur als Weiterleitung erlaubt
    "file:///C:/Windows/System32/config",                                           # Datei
    "ftp://github.com/x",
    "https://127.0.0.1/x",
])
def test_ein_start_ist_nur_bei_github_selbst_erlaubt(url, tmp_path):
    with pytest.raises(UpdateFehler) as e:
        quelle.laden(url, tmp_path / "x", max_bytes=100, oeffner=FakeOeffner({url: b"x"}))
    assert _code(e) == "quelle_nicht_erlaubt"
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("ziel_url,erlaubt", [
    ("https://objects.githubusercontent.com/github-production-release-asset/abc", True),
    ("https://release-assets.githubusercontent.com/github-production-release-asset/abc", True),
    ("https://github.com/MadGapun/PBP/releases/download/v1.8.1/x", True),
    ("https://evil.example/x", False),
    ("http://objects.githubusercontent.com/x", False),
    ("https://githubusercontent.com.evil.example/x", False),
    ("https://raw.githubusercontent.com/MadGapun/PBP/main/x", False),  # roh-Dateien sind keine Release-Dateien
])
def test_eine_weiterleitung_darf_nur_zu_den_release_hosts(ziel_url, erlaubt):
    handler = quelle._PruefendeWeiterleitung()
    req = urllib.request.Request("https://github.com/MadGapun/PBP/releases/download/v1.8.1/x")
    if erlaubt:
        handler.redirect_request(req, None, 302, "Found", {}, ziel_url)
    else:
        with pytest.raises(UpdateFehler) as e:
            handler.redirect_request(req, None, 302, "Found", {}, ziel_url)
        assert _code(e) == "quelle_nicht_erlaubt"


def test_die_liste_der_veroeffentlichungen_kommt_nur_von_der_festen_api_adresse():
    with pytest.raises(UpdateFehler) as e:
        quelle.json_holen("https://api.github.com/repos/Anderer/Repo/releases", oeffner=FakeOeffner())
    assert _code(e) == "quelle_nicht_erlaubt"


# ── Laden ──────────────────────────────────────────────────────────────────────────────

URL = "https://github.com/MadGapun/PBP/releases/download/v1.8.1/SHA256SUMS"


def test_laden_schreibt_erst_bei_vollstaendigem_empfang_unter_dem_zielnamen(tmp_path):
    daten = b"a" * 200_000
    ziel = tmp_path / "datei.bin"
    fortschritt = []
    n = quelle.laden(URL, ziel, max_bytes=1_000_000, oeffner=FakeOeffner({URL: daten}),
                     fortschritt=lambda geladen, gesamt: fortschritt.append((geladen, gesamt)))
    assert n == 200_000 and ziel.read_bytes() == daten
    assert fortschritt[-1] == (200_000, 200_000)
    assert not (tmp_path / "datei.bin.part").exists()


def test_eine_zu_gross_angekuendigte_datei_wird_gar_nicht_erst_geladen(tmp_path):
    ziel = tmp_path / "datei.bin"
    antwort = FakeAntwort(b"x" * 10, headers={"Content-Length": "999999999"})
    with pytest.raises(UpdateFehler) as e:
        quelle.laden(URL, ziel, max_bytes=1000, oeffner=FakeOeffner({URL: antwort}))
    assert _code(e) == "zu_gross"
    assert list(tmp_path.iterdir()) == []


def test_eine_datei_die_mehr_liefert_als_angekuendigt_wird_beim_Ueberschreiten_der_grenze_abgebrochen(tmp_path):
    antwort = FakeAntwort(b"x" * 5000, headers={})  # keine Laengenangabe: nur die Grenze schuetzt
    with pytest.raises(UpdateFehler) as e:
        quelle.laden(URL, tmp_path / "d", max_bytes=1000, oeffner=FakeOeffner({URL: antwort}))
    assert _code(e) == "zu_gross"
    assert list(tmp_path.iterdir()) == []


def test_eine_abgebrochene_verbindung_hinterlaesst_keine_datei(tmp_path):
    antwort = FakeAntwort(b"x" * 5000, headers={"Content-Length": "5000"}, ende_vorzeitig=2000)
    with pytest.raises(UpdateFehler) as e:
        quelle.laden(URL, tmp_path / "d", max_bytes=10_000, oeffner=FakeOeffner({URL: antwort}))
    assert _code(e) == "netz"
    assert list(tmp_path.iterdir()) == []


def test_ein_netzfehler_wird_zu_einem_klaren_fehler_ohne_reste(tmp_path):
    with pytest.raises(UpdateFehler) as e:
        quelle.laden(URL, tmp_path / "d", max_bytes=1000, oeffner=FakeOeffner({URL: ConnectionResetError("weg")}))
    assert _code(e) == "netz" and "GitHub" in e.value.text
    assert list(tmp_path.iterdir()) == []


def test_der_abbruch_mitten_im_laden_raeumt_auf(tmp_path):
    zaehler = {"n": 0}

    def abbruch():
        zaehler["n"] += 1
        return zaehler["n"] > 2

    with pytest.raises(UpdateFehler) as e:
        quelle.laden(URL, tmp_path / "d", max_bytes=10_000_000, oeffner=FakeOeffner({URL: b"x" * 1_000_000}), abbruch=abbruch)
    assert _code(e) == "abgebrochen"
    assert list(tmp_path.iterdir()) == []


def test_ein_fehler_beim_fortschritt_ist_ein_fehler_ohne_reste(tmp_path):
    def kaputt(*a):
        raise RuntimeError("Anzeige kaputt")

    with pytest.raises(UpdateFehler):
        quelle.laden(URL, tmp_path / "d", max_bytes=10_000, oeffner=FakeOeffner({URL: b"x" * 100}), fortschritt=kaputt)
    assert list(tmp_path.iterdir()) == []


# ── Die Liste der Veroeffentlichungen ──────────────────────────────────────────────────

def _eintrag(tag, **kw):
    e = {"tag_name": tag, "name": tag, "draft": False, "prerelease": False, "body": "Notizen",
         "published_at": "2026-10-02T10:00:00Z",
         "assets": [{"name": f"pbp-update-{tag[1:]}.zip", "size": 2_000_000}, {"name": "SHA256SUMS", "size": 100},
                    {"name": "SHA256SUMS.sig", "size": 90}]}
    e.update(kw)
    return e


def test_freigaben_lesen_ueberspringt_entwuerfe_vorabversionen_und_ungueltige_tags():
    daten = [_eintrag("v1.8.1"), _eintrag("v1.8.2", draft=True), _eintrag("v1.8.3", prerelease=True),
             _eintrag("v1.8.4-beta.1"), _eintrag("1.8.5"), _eintrag("v1.8"), _eintrag("../v1.8.6"), "kaputt", None, {"x": 1}]
    assert [f.version for f in quelle.freigaben_lesen(daten)] == ["1.8.1"]
    assert quelle.freigaben_lesen("kein Liste") == []
    assert quelle.freigaben_lesen(None) == []


def test_freigaben_lesen_nimmt_dateinamen_und_groessen_mit():
    f = quelle.freigaben_lesen([_eintrag("v1.8.1")])[0]
    assert f.dateien["pbp-update-1.8.1.zip"] == 2_000_000 and f.hat("SHA256SUMS")
    assert f.tag == "v1.8.1"


def test_neueste_fuer_linie_nimmt_die_neueste_der_eigenen_linie():
    freigaben = quelle.freigaben_lesen([_eintrag(t) for t in ("v1.8.1", "v1.8.3", "v1.8.2", "v1.7.150", "v1.9.0", "v2.0.0")])
    assert quelle.neueste_fuer_linie(freigaben, "1.8.0").version == "1.8.3"
    assert quelle.neueste_fuer_linie(freigaben, "1.8.3") is None          # schon aktuell
    assert quelle.neueste_fuer_linie(freigaben, "1.8.9") is None          # nie zurueck
    assert quelle.neueste_fuer_linie(freigaben, "1.7.149").version == "1.7.150"


def test_nie_ein_linienwechsel():
    freigaben = quelle.freigaben_lesen([_eintrag("v1.9.0"), _eintrag("v2.0.0")])
    assert quelle.neueste_fuer_linie(freigaben, "1.8.5") is None


def test_eine_beta_installation_bekommt_die_fertige_version_ihrer_linie():
    freigaben = quelle.freigaben_lesen([_eintrag("v1.8.0")])
    assert quelle.neueste_fuer_linie(freigaben, "1.8.0-beta.15").version == "1.8.0"


@pytest.mark.parametrize("laufend", ["", "kaputt", None, "1.8"])
def test_ohne_gueltige_laufende_fassung_gibt_es_kein_update(laufend):
    assert quelle.neueste_fuer_linie(quelle.freigaben_lesen([_eintrag("v1.8.1")]), laufend) is None


def test_vollstaendig_verlangt_archiv_summen_und_wo_noetig_die_signatur():
    f = quelle.freigaben_lesen([_eintrag("v1.8.1")])[0]
    assert quelle.vollstaendig(f, signatur_noetig=True) is True
    ohne_sig = quelle.freigaben_lesen([_eintrag("v1.8.1", assets=[
        {"name": "pbp-update-1.8.1.zip", "size": 1}, {"name": "SHA256SUMS", "size": 1}])])[0]
    assert quelle.vollstaendig(ohne_sig, signatur_noetig=False) is True
    assert quelle.vollstaendig(ohne_sig, signatur_noetig=True) is False
    ohne_archiv = quelle.freigaben_lesen([_eintrag("v1.8.1", assets=[{"name": "SHA256SUMS", "size": 1}])])[0]
    assert quelle.vollstaendig(ohne_archiv, signatur_noetig=False) is False


def test_json_holen_liest_die_antwort_und_meldet_unlesbares_ehrlich():
    import json
    ok = FakeOeffner({quelle.API_FREIGABEN: json.dumps([_eintrag("v1.8.1")]).encode()})
    assert quelle.json_holen(oeffner=ok)[0]["tag_name"] == "v1.8.1"
    with pytest.raises(UpdateFehler) as e:
        quelle.json_holen(oeffner=FakeOeffner({quelle.API_FREIGABEN: b"<html>"}))
    assert _code(e) == "netz"
    with pytest.raises(UpdateFehler) as e:
        quelle.json_holen(oeffner=FakeOeffner({quelle.API_FREIGABEN: OSError("kein Netz")}))
    assert _code(e) == "netz"
    with pytest.raises(UpdateFehler) as e:
        quelle.json_holen(oeffner=FakeOeffner({quelle.API_FREIGABEN: b"x" * (quelle.MAX_JSON_BYTES + 10)}))
    assert _code(e) == "zu_gross"
