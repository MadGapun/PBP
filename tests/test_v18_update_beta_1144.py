"""#1144 Punkt 2 (nur main) — die Update-Prüfung für Beta-Installationen stand dauerhaft auf „unbekannt“.

Befund (01.10.2026): `releases/latest` nennt immer nur die neueste STABILE Version. Für eine Installation der Linie 1.8
(Beta) war das 1.7.x; der Linienfilter (`update_quelle._passt_zur_linie`) verwarf sie, und die Anzeige stand dauerhaft auf
„Update-Stand unbekannt“ mit dem falschen Grund „Keine Update-Quelle hat geantwortet“, obwohl GitHub mit 200 antwortete.
Ab dem Tag, an dem 1.8 die neueste stabile Version ist, hätte es umgekehrt jede 1.7-Installation getroffen.

Die Quellen sind Testdoubles (kein Netz). Alle Versionsnummern der Veröffentlichungen sind erfunden.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import update_quelle as uq  # noqa: E402

BETA = "1.8.0-beta.15"


def _eintrag(tag, prerelease=False, draft=False):
    return {"tag_name": tag, "html_url": f"https://example.com/{tag}", "name": f"PBP {tag}",
            "prerelease": prerelease, "draft": draft}


LISTE = [
    _eintrag("v1.8.0-beta.16", prerelease=True),
    _eintrag("v1.8.0-beta.15", prerelease=True),
    _eintrag("v1.8.0-beta.9", prerelease=True),
    _eintrag("v1.7.149"),
    _eintrag("v1.7.148"),
]


# ══ Reine Funktionen ═══════════════════════════════════════════════════════════════════════════════

def test_1144_eine_beta_nimmt_die_neueste_beta_ihrer_linie():
    befund = uq.auswerten("github_liste", LISTE, BETA, "1.8")
    assert befund["version"] == "1.8.0-beta.16"
    assert befund["url"].endswith("v1.8.0-beta.16") and befund["name"] == "PBP v1.8.0-beta.16"


def test_1144_die_versionen_werden_als_zahlen_verglichen_nicht_als_text():
    liste = [_eintrag("v1.8.0-beta.9", prerelease=True), _eintrag("v1.8.0-beta.10", prerelease=True)]
    assert uq.auswerten("github_liste", liste, BETA, "1.8")["version"] == "1.8.0-beta.10"
    assert uq.auswerten("github_liste", list(reversed(liste)), BETA, "1.8")["version"] == "1.8.0-beta.10"


def test_1144_eine_stabile_installation_bekommt_keine_beta():
    liste = [_eintrag("v1.8.0-beta.16", prerelease=True), _eintrag("v1.7.150"), _eintrag("v1.7.149")]
    assert uq.auswerten("github_liste", liste, "1.7.149", "1.7")["version"] == "1.7.150"
    nur_beta = [_eintrag("v1.7.151-rc.1", prerelease=True), _eintrag("v1.7.149")]
    assert uq.auswerten("github_liste", nur_beta, "1.7.149", "1.7")["version"] == "1.7.149", \
        "auch eine Vorabversion der EIGENEN Linie zählt für eine stabile Installation nicht"


def test_1144_eine_beta_bekommt_auch_die_fertige_version_ihrer_linie():
    liste = [_eintrag("v1.8.0"), _eintrag("v1.8.0-beta.16", prerelease=True), _eintrag("v1.7.150")]
    assert uq.auswerten("github_liste", liste, BETA, "1.8")["version"] == "1.8.0"


def test_1144_entwuerfe_zaehlen_nie():
    liste = [_eintrag("v1.8.0-beta.99", prerelease=True, draft=True), _eintrag("v1.8.0-beta.16", prerelease=True)]
    assert uq.auswerten("github_liste", liste, BETA, "1.8")["version"] == "1.8.0-beta.16"


def test_1144_eine_andere_linie_zaehlt_nicht():
    assert uq.auswerten("github_liste", [_eintrag("v1.7.149"), _eintrag("v1.9.0")], BETA, "1.8") is None
    assert uq.auswerten("github_liste", [], BETA, "1.8") is None


@pytest.mark.parametrize("daten", [None, {}, "text", 42, [None, "x", 3, {}, {"tag_name": ""},
                                                           {"tag_name": "kein-versionstext"}, {"tag_name": None}]])
def test_1144_unbrauchbare_antworten_brechen_nichts(daten):
    assert uq.auswerten("github_liste", daten, BETA, "1.8") is None


def test_1144_die_liste_ist_die_dritte_und_letzte_standardquelle():
    namen = [q["name"] for q in uq.STANDARD_QUELLEN]
    assert namen == ["elwosa", "github", "github-liste"]
    assert uq.STANDARD_QUELLEN[-1]["art"] == "github_liste"
    assert "github_liste" in uq.GITHUB_ARTEN and "github" in uq.GITHUB_ARTEN and "elwosa" not in uq.GITHUB_ARTEN


def test_1144_die_bisherigen_quellen_deuten_ihre_antworten_unveraendert():
    assert uq.auswerten("github", {"tag_name": "v1.8.0-beta.16", "html_url": "u"}, BETA, "1.8")["version"] == \
        "1.8.0-beta.16"
    assert uq.auswerten("github", {"tag_name": "v1.7.149"}, BETA, "1.8") is None
    assert uq.auswerten("elwosa", {"version": "1.8.0-beta.16"}, BETA, "1.8")["version"] == "1.8.0-beta.16"


# ══ Der Endpunkt ═══════════════════════════════════════════════════════════════════════════════════

class _Resp:
    def __init__(self, status, daten):
        self.status_code = status
        self._daten = daten

    def json(self):
        return self._daten


class _Netz:
    """Antwortet je Adresse; merkt sich Adressen und Kopfzeilen."""

    def __init__(self, latest=None, liste=None, aus=False):
        self.latest, self.liste, self.aus = latest, liste, aus
        self.urls: list = []
        self.kopfzeilen: dict = {}

    def klasse(self):
        netz = self

        class _Client:
            def __init__(self, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, headers=None):
                netz.urls.append(url)
                netz.kopfzeilen[url] = headers or {}
                if netz.aus:
                    raise OSError("kein Netz")
                if "elwosa" in url:
                    return _Resp(404, {})
                if "releases/latest" in url:
                    return _Resp(200, netz.latest) if netz.latest is not None else _Resp(404, {})
                if "releases?per_page" in url:
                    return _Resp(200, netz.liste) if netz.liste is not None else _Resp(404, {})
                return _Resp(404, {})
        return _Client


def _leer(dash):
    dash._update_cache.update({"ts": 0, "data": None, "pause_s": 3600, "fehlversuche": 0})


@pytest.fixture
def umgebung(monkeypatch, tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import get_data_dir
    assert str(tmp_path) in str(get_data_dir()), "Datenordner nicht isoliert"
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    monkeypatch.setattr(dash, "_db", None)           # Quellen: die Vorgabe
    monkeypatch.setattr("bewerbungs_assistent.__version__", BETA)
    _leer(dash)

    def einrichten(**kw):
        netz = _Netz(**kw)
        monkeypatch.setattr("httpx.AsyncClient", netz.klasse())
        return netz

    yield TestClient(dash.app), dash, einrichten
    _leer(dash)
    os.environ.pop("BA_DATA_DIR", None)


def test_1144_eine_beta_findet_die_naechste_beta_obwohl_latest_die_stabile_linie_nennt(umgebung):
    """DER Befund: vorher stand hier dauerhaft 'unbekannt'."""
    tc, dash, einrichten = umgebung
    netz = einrichten(latest={"tag_name": "v1.7.149", "html_url": "https://example.com/1.7.149"}, liste=LISTE)
    antwort = tc.get("/api/update-check").json()
    assert antwort["stand"] == "geprueft"
    assert antwort["update_available"] is True
    assert antwort["latest_version"] == "1.8.0-beta.16"
    assert antwort["quelle"] == "github-liste"
    assert antwort["release_url"].endswith("v1.8.0-beta.16")
    assert 3500 <= antwort["wieder_fragen_nach_s"] <= 3600
    assert [v.get("ergebnis") for v in antwort["quellen_versucht"]] == [None, "nichts_passendes", "1.8.0-beta.16"]


def test_1144_eine_aktuelle_beta_ist_aktuell_und_nicht_unbekannt(umgebung):
    tc, dash, einrichten = umgebung
    einrichten(latest={"tag_name": "v1.7.149"}, liste=[_eintrag("v1.8.0-beta.15", prerelease=True), _eintrag("v1.7.149")])
    antwort = tc.get("/api/update-check").json()
    assert antwort["stand"] == "geprueft" and antwort["update_available"] is False


def test_1144_nennt_latest_die_eigene_linie_wird_die_liste_nicht_gefragt(umgebung, monkeypatch):
    """Eine Anfrage weniger an GitHub (60 je Stunde und Adresse), wo sie nichts bringt."""
    tc, dash, einrichten = umgebung
    monkeypatch.setattr("bewerbungs_assistent.__version__", "1.7.149")
    netz = einrichten(latest={"tag_name": "v1.7.150", "html_url": "u"}, liste=LISTE)
    antwort = tc.get("/api/update-check").json()
    assert antwort["latest_version"] == "1.7.150" and antwort["quelle"] == "github"
    assert not any("per_page" in u for u in netz.urls)


def test_1144_eine_stabile_installation_findet_ihr_update_auch_wenn_latest_eine_andere_linie_nennt(umgebung, monkeypatch):
    """Die Rückrichtung: sobald 1.8 die neueste stabile Version ist."""
    tc, dash, einrichten = umgebung
    monkeypatch.setattr("bewerbungs_assistent.__version__", "1.7.149")
    einrichten(latest={"tag_name": "v1.8.0", "html_url": "u"},
               liste=[_eintrag("v1.8.0"), _eintrag("v1.7.150"), _eintrag("v1.7.149")])
    antwort = tc.get("/api/update-check").json()
    assert antwort["stand"] == "geprueft"
    assert antwort["latest_version"] == "1.7.150" and antwort["update_available"] is True


def test_1144_gibt_es_keine_version_der_linie_sagt_der_grund_die_wahrheit(umgebung):
    tc, dash, einrichten = umgebung
    einrichten(latest={"tag_name": "v1.7.149"}, liste=[_eintrag("v1.7.149"), _eintrag("v1.7.148")])
    antwort = tc.get("/api/update-check").json()
    assert antwort["stand"] == "unbekannt"
    assert antwort["grund"] == "keine_version_der_linie"
    assert "geantwortet" in antwort["hinweis"] and "Linie 1.8" in antwort["hinweis"]
    assert "Keine Update-Quelle hat geantwortet" not in antwort["hinweis"]
    assert 3500 <= antwort["wieder_fragen_nach_s"] <= 3600, "kein Netzfehler: kein Zwei-Minuten-Takt"
    assert dash._update_cache["fehlversuche"] == 0


def test_1144_ohne_jede_antwort_bleibt_es_ein_fehlschlag_mit_kurzer_frist(umgebung):
    tc, dash, einrichten = umgebung
    einrichten(aus=True)
    antwort = tc.get("/api/update-check").json()
    assert antwort["stand"] == "unbekannt" and antwort["grund"] == "keine_antwort"
    assert "Keine Update-Quelle hat geantwortet" in antwort["hinweis"]
    assert antwort["wieder_fragen_nach_s"] <= 120 + 1
    assert dash._update_cache["fehlversuche"] == 1


def test_1144_antwortet_nur_eine_quelle_mit_404_ist_es_keine_antwort(umgebung):
    tc, dash, einrichten = umgebung
    einrichten()                        # alle drei Adressen: 404
    antwort = tc.get("/api/update-check").json()
    assert antwort["grund"] == "keine_antwort"


def test_1144_die_liste_wird_mit_der_github_kopfzeile_und_ohne_linienparameter_gefragt(umgebung):
    tc, dash, einrichten = umgebung
    netz = einrichten(latest={"tag_name": "v1.7.149"}, liste=LISTE)
    tc.get("/api/update-check")
    liste_url = next(u for u in netz.urls if "per_page" in u)
    assert netz.kopfzeilen[liste_url].get("Accept") == "application/vnd.github.v3+json"
    assert "linie=" not in liste_url
    elwosa_url = next(u for u in netz.urls if "elwosa" in u)
    assert "linie=1.8" in elwosa_url and not netz.kopfzeilen[elwosa_url]


def test_1144_eine_unbrauchbare_liste_bricht_die_pruefung_nicht(umgebung):
    tc, dash, einrichten = umgebung
    einrichten(latest={"tag_name": "v1.7.149"}, liste={"message": "API rate limit exceeded"})
    antwort = tc.get("/api/update-check").json()
    assert antwort["stand"] == "unbekannt"


def test_1144_die_oberflaeche_nennt_den_neuen_grund_im_klartext():
    quelle = (ROOT / "frontend" / "src" / "lib" / "updateStand.js").read_text(encoding="utf-8-sig")
    assert 'daten?.grund === "keine_version_der_linie"' in quelle
    ci = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "frontend/src/lib/updateStand.test.mjs" in ci
