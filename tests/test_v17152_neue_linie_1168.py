"""#1168 — eine 1.7-Installation erfuhr nie, dass es Version 1.8 gibt.

Befund (03.10.2026): Die Update-Pruefung filtert die Antwort jeder Quelle auf die eigene Linie. Das ist richtig fuer
das ANGEBOT (eine 1.7-Installation wechselt nie von selbst die Linie), hatte aber eine Kehrseite: Sobald 1.8.0 erscheint,
zeigt jede 1.7-Installation "aktuell", und niemand erfaehrt in PBP von 1.8 - und damit vom Auto-Update.

Jetzt merkt sich die Pruefung zusaetzlich die neueste STABILE Version einer hoeheren Linie (`neue_linie`). Sie wird nie
als Update angeboten. Vorabversionen und Entwuerfe zaehlen nie.

Die Quellen sind Testdoubles (kein Netz). Alle Versionsnummern der Veroeffentlichungen sind erfunden.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import update_quelle as uq  # noqa: E402

STABIL = "1.7.151"


def _eintrag(tag, prerelease=False, draft=False):
    return {"tag_name": tag, "html_url": f"https://example.com/{tag}", "name": f"PBP {tag}",
            "prerelease": prerelease, "draft": draft}


# ══ Die reine Funktion ═════════════════════════════════════════════════════════════════════════════

def test_1168_latest_auf_einer_hoeheren_linie_wird_erkannt():
    n = uq.neue_linie("github", _eintrag("v1.8.0"), STABIL)
    assert n == {"version": "1.8.0", "linie": "1.8", "url": "https://example.com/v1.8.0", "name": "PBP v1.8.0"}


def test_1168_die_eigene_linie_ist_keine_neue_linie():
    assert uq.neue_linie("github", _eintrag("v1.7.152"), STABIL) is None
    assert uq.neue_linie("github", _eintrag("v1.7.151"), STABIL) is None


def test_1168_eine_niedrigere_linie_ist_keine_neue_linie():
    assert uq.neue_linie("github", _eintrag("v1.7.152"), "1.8.0") is None


def test_1168_vorabversionen_und_entwuerfe_zaehlen_nie():
    """Eine 1.8-Beta ist fuer eine 1.7-Installation keine Nachricht wert."""
    assert uq.neue_linie("github", _eintrag("v1.8.0-beta.16", prerelease=True), STABIL) is None
    assert uq.neue_linie("github", _eintrag("v1.8.0-beta.16"), STABIL) is None, "auch ohne Kennzeichen: die Nummer sagt Beta"
    assert uq.neue_linie("github", _eintrag("v1.8.0", draft=True), STABIL) is None
    assert uq.neue_linie("github", _eintrag("v1.8.0", prerelease=True), STABIL) is None, "als Vorabversion markiert zaehlt nie"
    assert uq.neue_linie("github_liste", [_eintrag("v1.8.0", prerelease=True), _eintrag("v1.7.152")], STABIL) is None
    liste = [_eintrag("v2.0.0", draft=True), _eintrag("v1.9.0-rc.1", prerelease=True), _eintrag("v1.8.0-beta.16", prerelease=True),
             _eintrag("v1.7.152")]
    assert uq.neue_linie("github_liste", liste, STABIL) is None


def test_1168_aus_der_liste_kommt_die_neueste_stabile_version_einer_hoeheren_linie():
    liste = [_eintrag("v1.8.0-beta.20", prerelease=True), _eintrag("v1.8.1"), _eintrag("v1.8.0"), _eintrag("v1.7.152"),
             _eintrag("v1.7.151")]
    assert uq.neue_linie("github_liste", liste, STABIL)["version"] == "1.8.1"


def test_1168_linien_werden_als_zahlen_verglichen():
    assert uq.neue_linie("github", _eintrag("v1.10.0"), "1.9.4")["linie"] == "1.10"
    assert uq.neue_linie("github", _eintrag("v1.9.4"), "1.10.0") is None


def test_1168_auch_die_elwosa_quelle_wird_gelesen():
    n = uq.neue_linie("elwosa", {"version": "1.8.0", "download_url": "https://example.com/dl"}, STABIL)
    assert n["version"] == "1.8.0" and n["url"] == "https://example.com/dl"


@pytest.mark.parametrize("daten", [None, "kaputt", 42, [], {}, [None, 3, "x"], {"tag_name": None}, {"tag_name": "vkaputt"}])
def test_1168_unbrauchbare_antworten_brechen_nichts(daten):
    for art in ("github", "github_liste", "elwosa"):
        assert uq.neue_linie(art, daten, STABIL) is None


# ══ Der Endpunkt ═══════════════════════════════════════════════════════════════════════════════════

class _Resp:
    def __init__(self, status, daten):
        self.status_code = status
        self._daten = daten

    def json(self):
        return self._daten


class _Netz:
    """Antwortet je Adresse; merkt sich die Adressen."""

    def __init__(self, latest=None, liste=None, aus=False):
        self.latest, self.liste, self.aus = latest, liste, aus
        self.urls: list = []

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
    monkeypatch.setattr("bewerbungs_assistent.__version__", STABIL)
    _leer(dash)

    def einrichten(**kw):
        netz = _Netz(**kw)
        monkeypatch.setattr("httpx.AsyncClient", netz.klasse())
        return netz

    yield TestClient(dash.app), dash, einrichten
    _leer(dash)
    os.environ.pop("BA_DATA_DIR", None)


LISTE_NACH_18 = [_eintrag("v1.8.0"), _eintrag("v1.8.0-beta.16", prerelease=True), _eintrag("v1.7.152"), _eintrag("v1.7.151")]


def test_1168_nach_dem_erscheinen_von_18_nennt_eine_17_installation_beides(umgebung):
    """DER Befund: das Update der eigenen Linie UND die neue Linie - vorher nur das Update, von 1.8 kein Wort."""
    tc, dash, einrichten = umgebung
    einrichten(latest=_eintrag("v1.8.0"), liste=LISTE_NACH_18)
    antwort = tc.get("/api/update-check").json()
    assert antwort["update_available"] is True and antwort["latest_version"] == "1.7.152", "die Linie wechselt nie von selbst"
    assert antwort["neue_linie"] == {"version": "1.8.0", "linie": "1.8", "url": "https://example.com/v1.8.0",
                                     "name": "PBP v1.8.0"}


def test_1168_eine_aktuelle_17_installation_ist_aktuell_und_erfaehrt_trotzdem_von_18(umgebung, monkeypatch):
    tc, dash, einrichten = umgebung
    monkeypatch.setattr("bewerbungs_assistent.__version__", "1.7.152")
    einrichten(latest=_eintrag("v1.8.0"), liste=LISTE_NACH_18)
    antwort = tc.get("/api/update-check").json()
    assert antwort["stand"] == "geprueft" and antwort["update_available"] is False
    assert antwort["neue_linie"]["version"] == "1.8.0"


def test_1168_vor_dem_erscheinen_von_18_gibt_es_keine_neue_linie(umgebung):
    tc, dash, einrichten = umgebung
    netz = einrichten(latest=_eintrag("v1.7.152"), liste=[_eintrag("v1.8.0-beta.16", prerelease=True), _eintrag("v1.7.152")])
    antwort = tc.get("/api/update-check").json()
    assert antwort["neue_linie"] is None
    assert not any("per_page" in u for u in netz.urls), "nennt latest die eigene Linie, wird die Liste nicht gefragt (#1144)"


def test_1168_eine_beta_der_hoeheren_linie_loest_nichts_aus(umgebung):
    tc, dash, einrichten = umgebung
    einrichten(latest=_eintrag("v1.7.151"), liste=[_eintrag("v1.8.0-beta.16", prerelease=True), _eintrag("v1.7.151")])
    assert tc.get("/api/update-check").json()["neue_linie"] is None


def test_1168_scheitert_die_liste_bleibt_die_neue_linie_aus_latest(umgebung):
    """Die eigene Linie ist dann unbekannt - die Nachricht, dass 1.8 erschienen ist, geht trotzdem nicht verloren."""
    tc, dash, einrichten = umgebung
    einrichten(latest=_eintrag("v1.8.0"), liste=None)
    antwort = tc.get("/api/update-check").json()
    assert antwort["stand"] == "unbekannt" and antwort["grund"] == "keine_version_der_linie"
    assert antwort["neue_linie"]["version"] == "1.8.0"


def test_1168_von_mehreren_quellen_gilt_die_neueste_version(umgebung):
    tc, dash, einrichten = umgebung
    einrichten(latest=_eintrag("v1.8.0"), liste=[_eintrag("v1.8.1"), _eintrag("v1.8.0"), _eintrag("v1.7.152")])
    assert tc.get("/api/update-check").json()["neue_linie"]["version"] == "1.8.1"


def test_1168_eine_spaetere_quelle_mit_aelterer_version_ueberschreibt_nicht(umgebung):
    tc, dash, einrichten = umgebung
    einrichten(latest=_eintrag("v1.8.1"), liste=[_eintrag("v1.8.0"), _eintrag("v1.7.152")])
    assert tc.get("/api/update-check").json()["neue_linie"]["version"] == "1.8.1"


def test_1168_ohne_netz_keine_neue_linie_und_keine_ausnahme(umgebung):
    tc, dash, einrichten = umgebung
    einrichten(aus=True)
    antwort = tc.get("/api/update-check").json()
    assert antwort["stand"] == "unbekannt" and antwort["neue_linie"] is None


def test_1168_die_oberflaeche_nennt_die_neue_linie_in_seitenleiste_und_hinweiszone():
    """Die Texte stehen in `lib/updateStand.js` (Node-Test); hier nur, dass beide Stellen sie auch benutzen."""
    app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8-sig")
    leiste = (ROOT / "frontend" / "src" / "components" / "Sidebar.jsx").read_text(encoding="utf-8-sig")
    dashboard = (ROOT / "frontend" / "src" / "pages" / "DashboardPage.jsx").read_text(encoding="utf-8-sig")
    assert "neueLinie: neueLinieHinweis(updateInfo)" in app
    assert "brand.neueLinie" in leiste and 'data-update-stand="neue-linie"' in leiste
    assert "neueLinie: neueLinieHinweis(updateInfo)" in dashboard
