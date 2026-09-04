"""Tests fuer v1.7.28 — #969: wie heisst derselbe Beruf noch?

Belegt in #968: eine Pflegekraft traegt "Pflegefachkraft" als
MUSS-Begriff ein. "Gesundheits- und Krankenpflegerin" bekam Score 0 und
erschien nicht in der Liste, obwohl es derselbe Beruf ist. Synonyme
kannte das Tor nur fuer vier Produktnamen — also ausschliesslich fuer
ein technisches Berufsfeld.

**Warum nicht BERUFENET.** Live geprueft am 04.09.2026: die
Berufe-Endpunkte der Bundesagentur antworten mit dem oeffentlichen
Jobsuche-Schluessel durchgehend 403/404. Sie sind ohne Registrierung
nicht erreichbar, und PBP soll ohne Anmeldung laufen.

**Was stattdessen traegt.** Die Jobsuche-API liefert je Suchanfrage eine
Facette `beruf` mit den amtlichen Bezeichnungen der Treffer. Fuer
"Pflegefachkraft" sind das Altenpfleger/in, Pflegefachmann/-frau,
Gesundheits- und Krankenpfleger/in, Krankenschwester/-pfleger — genau
die Bezeichnungen, an denen das Tor scheiterte.

Kein Test hier ruft die echte API. Die Antwortform ist einmal live
abgeschaut und wird hier als Fixture nachgestellt.
"""
import pytest

from bewerbungs_assistent.job_scraper import calculate_score, fit_analyse
from bewerbungs_assistent.services import berufsbezeichnungen as bb

# Der Facetten-Block, wie ihn die v6-Antwort am 04.09.2026 lieferte.
ANTWORT_PFLEGE = {
    "facetten": {"beruf": {"counts": {
        "Altenpfleger/in": 9373,
        "Pflegefachmann/-frau (Altenpflege)": 7218,
        "Gesundheits- und Krankenpfleger/in": 6723,
        "Krankenschwester/-pfleger": 1728,
        "Heilerziehungspfleger/in": 722,
        "Zahnarzthelfer/in": 12,          # Ausreisser, muss wegfallen
    }, "maxCount": 9373}},
}


class _Antwort:
    def __init__(self, daten, status=200):
        self._daten, self.status_code = daten, status

    def json(self):
        return self._daten


class _Client:
    """Minimaler Ersatz fuer httpx.Client — kein Netz."""

    def __init__(self, daten, status=200):
        self._daten, self._status = daten, status
        self.aufrufe = []

    def get(self, url, params=None, headers=None):
        self.aufrufe.append(params or {})
        return _Antwort(self._daten, self._status)

    def close(self):
        pass


@pytest.fixture(autouse=True)
def _cache_leeren():
    bb.cache_leeren()
    yield
    bb.cache_leeren()


# ── Wortformen: nur bilden, was sich sicher bilden laesst ────────────

@pytest.mark.parametrize("amtlich,erwartet", [
    ("Altenpfleger/in", ["Altenpfleger", "Altenpflegerin"]),
    ("Erzieher/in", ["Erzieher", "Erzieherin"]),
    ("Pflegefachmann/-frau (Altenpflege)",
     ["Pflegefachmann", "Pflegefachfrau"]),
    ("Kaufmann/-frau - Büromanagement",
     ["Kaufmann", "Kauffrau", "Büromanagement"]),
    ("Sozialpädagoge/pädagogin", ["Sozialpädagoge", "Sozialpädagogin"]),
])
def test_969_wortformen_werden_korrekt_gebildet(amtlich, erwartet):
    assert bb._formen(amtlich) == erwartet


def test_969_kompositum_vorderteil_wird_nie_zum_begriff():
    """Der gefaehrlichste Fehler der ersten Fassung.

    "Gesundheits- und Krankenpfleger/in" ergab "Gesundheits" — als
    MUSS-Synonym haette das jedes Kompositum getroffen, von
    Gesundheitsmanagement bis Gesundheitsamt. Ein Unwort ist harmlos, es
    matcht nie; ein Fragment ist es nicht.
    """
    formen = bb._formen("Gesundheits- und Krankenpfleger/in")
    assert "Gesundheits" not in formen
    assert formen == ["Krankenpfleger", "Krankenpflegerin"]


def test_969_keine_unwoerter():
    """Die naive Verkettung ergab "Pflegefachmannfrau"."""
    for amtlich in ("Pflegefachmann/-frau", "Sozialpädagoge/pädagogin"):
        for form in bb._formen(amtlich):
            assert "mannfrau" not in form.lower()
            assert "gepädagogin" not in form.lower()


# ── Facette lesen ────────────────────────────────────────────────────

def test_969_ausreisser_zaehlen_nicht_als_synonym():
    """Ein Beruf in 12 von 25.000 Anzeigen ist ein Ausreisser."""
    amtlich = bb._aus_facette(ANTWORT_PFLEGE)
    assert "Altenpfleger/in" in amtlich
    assert "Zahnarzthelfer/in" not in amtlich


def test_969_leere_antwort_ergibt_nichts():
    assert bb._aus_facette({}) == []
    assert bb._aus_facette({"facetten": {}}) == []
    assert bb._aus_facette({"facetten": {"beruf": {"counts": {}}}}) == []


# ── Abfrage ──────────────────────────────────────────────────────────

def test_969_synonyme_aus_der_facette():
    c = _Client(ANTWORT_PFLEGE)
    erg = bb.synonyme("Pflegefachkraft", client=c)
    for pflicht in ("Altenpfleger", "Krankenpfleger", "Krankenpflegerin",
                    "Pflegefachfrau"):
        assert pflicht in erg, erg
    assert c.aufrufe[0]["was"] == "Pflegefachkraft"


def test_969_der_begriff_selbst_ist_kein_synonym():
    c = _Client({"facetten": {"beruf": {"counts": {"Erzieher/in": 100}}}})
    assert "Erzieher" not in [x.lower() for x in bb.synonyme("erzieher", client=c)]


def test_969_zweiter_aufruf_geht_nicht_erneut_ins_netz():
    """Eine Abfrage je Stelle und Keyword waere unbrauchbar."""
    c = _Client(ANTWORT_PFLEGE)
    bb.synonyme("Pflegefachkraft", client=c)
    bb.synonyme("Pflegefachkraft", client=c)
    assert len(c.aufrufe) == 1


def test_969_ausfall_der_quelle_stoppt_nichts():
    """Eine fehlende Auskunft darf keine Suche verhindern."""
    assert bb.synonyme("Pflegefachkraft", client=_Client({}, status=503)) == []


def test_969_zu_kurzer_begriff_wird_nicht_abgefragt():
    c = _Client(ANTWORT_PFLEGE)
    assert bb.synonyme("IT", client=c) == []
    assert c.aufrufe == []


def test_969_netzweg_ist_abschaltbar(monkeypatch):
    """Die Suite laeuft hermetisch — sonst haengt die CI an einer
    Netzwerksperre oder misst fremde Latenz (DoD 8c)."""
    monkeypatch.setenv("PBP_BERUFE_LOOKUP", "0")
    assert bb.aktiv() is False
    assert bb.synonyme("Pflegefachkraft") == []
    monkeypatch.setenv("PBP_BERUFE_LOOKUP", "1")
    assert bb.aktiv() is True


# ── Die Wirkung im Scoring: der belegte Fall aus #968 ────────────────

KRITERIEN = {
    "keywords_muss": ["Pflegefachkraft"],
    "keywords_plus": ["Intensiv", "Schichtdienst"],
    "keywords_minus": [], "keywords_ausschluss": [],
    "gewichtung": {"muss": 7, "plus": 3, "minus": 6},
}
BESCHREIBUNG = "Intensivstation, Schichtdienst, Grund- und Behandlungspflege."


def _mit_synonymen():
    k = dict(KRITERIEN)
    k["_muss_synonyme"] = {"Pflegefachkraft": bb.synonyme(
        "Pflegefachkraft", client=_Client(ANTWORT_PFLEGE))}
    return k


@pytest.mark.parametrize("titel", [
    "Gesundheits- und Krankenpflegerin (m/w/d)",
    "Altenpflegerin (m/w/d)",
    "Krankenschwester (m/w/d) Station 4",
])
def test_969_synonym_erscheint_jetzt_in_der_liste(titel):
    """Der gemeldete Fall: derselbe Beruf, andere Amtsbezeichnung."""
    job = {"title": titel, "description": BESCHREIBUNG, "company": "Musterklinik"}
    assert calculate_score(dict(job), KRITERIEN) == 0, "Ausgangslage"
    assert calculate_score(dict(job), _mit_synonymen()) > 0


@pytest.mark.parametrize("titel", [
    "Softwareentwickler (m/w/d)",
    "Erzieherin (m/w/d) Kita",
    "Finanzbuchhalter (m/w/d)",
])
def test_969_fachfremdes_bleibt_draussen(titel):
    """Die Gegenrichtung. Ein Synonym darf den Torwaechter erweitern,
    nicht aufweichen — sonst waere der MUSS-Begriff wertlos."""
    job = {"title": titel, "description": BESCHREIBUNG, "company": "Musterfirma"}
    assert calculate_score(dict(job), _mit_synonymen()) == 0


@pytest.mark.parametrize("titel", [
    "Pflegefachkraft (m/w/d)",
    "Gesundheits- und Krankenpflegerin (m/w/d)",
    "Altenpflegerin (m/w/d)",
    "Softwareentwickler (m/w/d)",
])
def test_969_beide_rechenwege_stimmen_ueberein(titel):
    """Der Guard aus #963. Beim Bauen zweimal gebrochen: erst oeffnete
    das Tor ohne Punkte zu geben (calc 0, fit 6,0), dann rechnete nur
    calculate_score die Synonyme mit (calc 10,5, fit 6,0). Dieselbe
    Lehre zum dritten Mal — eine Regel gehoert in BEIDE Wege.
    """
    k = _mit_synonymen()
    job = {"title": titel, "description": BESCHREIBUNG, "company": "Musterklinik"}
    a = calculate_score(dict(job), k)
    b = fit_analyse(dict(job), k)["total_score"]
    assert abs(float(a) - float(b)) < 0.05, (titel, a, b)


def test_969_synonym_zaehlt_wie_ein_treffer_nicht_weniger():
    """Wer denselben Beruf anders nennt, soll nicht schlechter
    dastehen."""
    k = _mit_synonymen()
    exakt = {"title": "Pflegefachkraft (m/w/d)", "description": BESCHREIBUNG,
             "company": "Musterklinik"}
    synonym = {"title": "Gesundheits- und Krankenpflegerin (m/w/d)",
               "description": BESCHREIBUNG, "company": "Musterklinik"}
    assert calculate_score(dict(synonym), k) == calculate_score(dict(exakt), k)


# ── Verdrahtung ──────────────────────────────────────────────────────

def test_969_suchlauf_holt_die_bezeichnungen_einmal():
    """Einmal je Lauf, nicht je Stelle — dasselbe Muster wie die
    IDF-Faktoren (#778)."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "job_scraper" /
              "__init__.py").read_text(encoding="utf-8")
    assert "berufsbezeichnungen as _berufe" in quelle
    assert "_berufe.erweitere(_muss_begriffe)" in quelle
    assert quelle.count("_berufe.erweitere") == 1
