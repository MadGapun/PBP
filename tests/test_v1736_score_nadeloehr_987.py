"""Tests fuer v1.7.36 — #987: der gespeicherte Score war reproduzierbar falsch.

Befund vom 07.09.2026: 86 von 86 Stellen eines Laufs zu hoch bewertet,
im Schnitt um 47 Punkte, im Maximum um 105. `fit_analyse` auf die
Spitzenstelle ergab mit denselben Kriterien 0.

Zwei Ursachen, die zusammen erst den vollen Schaden ergeben:

**(1) Die Kriterien lagen doppelt.** Der Suchlauf reicherte sie an
(`_applied_titles`, `_muss_synonyme`), `scores_neu_berechnen` und
`fit_analyse` nahmen sie roh. Der gespeicherte Score war damit von
keinem anderen Werkzeug nachzurechnen. Das ist das Muster aus #963/
#913/#976, eine Ebene tiefer: nicht die Rechnung lag doppelt, sondern
ihre Eingabe.

**(2) Die Anreicherung selbst war falsch.** Die Berufs-Facette (#969)
beantwortet "wer arbeitet damit", nicht "wie heisst das noch". Fuer den
MUSS-Begriff "PLM" lieferte sie Ingenieur, Maschinenbau, Elektrotechnik,
Konstrukteur, Berater — als MUSS-Synonyme oeffnete damit jede
Ingenieursanzeige das Tor.

Waere nur (1) behoben worden, haetten alle Wege denselben FALSCHEN Wert
geliefert. Waere nur (2) behoben worden, blieben die Wege verschieden.
"""
import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.job_scraper import calculate_score  # noqa: E402
from bewerbungs_assistent.services import berufsbezeichnungen as bb  # noqa: E402
from bewerbungs_assistent.services import scoring_kriterien as sk  # noqa: E402


GEWICHTUNG = {"muss": 7, "plus": 3, "minus": 6, "remote": 3, "naehe": 4,
              "fern_malus": 5, "gehalt": 8}

# Die MUSS-Liste des gemeldeten Falls, gekuerzt auf die Begriffe, fuer
# die die Facette am 07.09.2026 Synonyme lieferte.
MUSS_TECHNIK = ["PLM", "PDM", "CAD-ERP", "PLM Architect", "PLM Berater"]

# Was `erweitere` damals zurueckgab — die Messwerte aus dem Befund.
SYNONYME_ALT = {
    "PLM": ["IT-Berater", "Ingenieur", "Ingenieurin", "Maschinenbau",
            "Elektrotechnik", "Informatiker", "Konstrukteur"],
    "PDM": ["Ingenieur", "Maschinenbau", "Konstrukteur", "Technische",
            "Produktdesigner", "Elektrotechnik", "Anlagentechnik"],
    "CAD-ERP": ["Ingenieur", "Maschinenbau", "Konstrukteur",
                "Arbeitsvorbereiter", "Elektrotechnik", "Projektleiter"],
    "PLM Architect": ["Ingenieur", "Elektrotechnik", "Informatiker"],
    "PLM Berater": ["IT-Berater", "ERP-Berater", "Berater"],
}

FREMDE_STELLE = {
    "title": "Ingenieur Elektrotechnik (m/w/d)",
    "company": "Beispiel Technik GmbH",
    "location": "Hamburg",
    "description": "Ingenieur/in - Elektrotechnik",
    "url": "https://example.invalid/1",
}


def _kriterien(**extra) -> dict:
    krit = {
        "keywords_muss": list(MUSS_TECHNIK),
        "keywords_plus": ["Hamburg"],
        "keywords_minus": [],
        "keywords_ausschluss": [],
        "gewichtung": dict(GEWICHTUNG),
    }
    krit.update(extra)
    return krit


# ── Der gemeldete Fall ────────────────────────────────────────────────

def test_987_der_gemeldete_fall_reproduziert_sich():
    """Ohne Synonyme 0, mit den alten Synonymen ein hoher Wert.

    Das ist der Kern des Befunds: dieselbe Stelle, dieselbe Funktion,
    zwei Ergebnisse — allein wegen der Kriterien.
    """
    ohne = calculate_score(dict(FREMDE_STELLE), _kriterien())
    mit = calculate_score(dict(FREMDE_STELLE),
                          _kriterien(_muss_synonyme=SYNONYME_ALT))
    assert ohne == 0
    assert mit > 20, ("Ohne diese Divergenz gibt es nichts zu reparieren — "
                      f"gemessen: {mit}")


def test_987_generische_berufe_sind_keine_alternativbezeichnung():
    """Der Kern der zweiten Ursache.

    Keiner dieser Berufe ist ein anderer NAME fuer PLM. Alle standen als
    MUSS-Synonym in der Trefferliste.
    """
    for amtlich in ("Ingenieur/in - Elektrotechnik",
                    "Ingenieur/in - Maschinenbau",
                    "IT-Berater/in", "Informatiker/in", "Konstrukteur/in"):
        assert not bb._ist_alternativbezeichnung("PLM", amtlich), amtlich


def test_987_abkuerzungen_bekommen_keine_synonyme():
    """PLM, PDM, CAD: eine Abkuerzung ist kein Berufsname.

    Ihre Woerter sind kuerzer als ein tragfaehiger Wortstamm — damit
    kann die Pruefung fuer sie gar nicht aufgehen, und das ist die
    Absicht.
    """
    for kurz in ("PLM", "PDM", "CAD", "ERP"):
        assert not bb._ist_alternativbezeichnung(kurz, "Ingenieur/in")


def test_987_der_gruendungsfall_von_969_funktioniert_weiter():
    """Die Haertung darf die Funktion nicht abschaffen.

    Genau die Bezeichnungen, an denen das MUSS-Tor in #968 scheiterte,
    muessen weiter durchkommen.
    """
    for amtlich in ("Gesundheits- und Krankenpfleger/in", "Altenpfleger/in",
                    "Pflegefachmann/-frau (Altenpflege)"):
        assert bb._ist_alternativbezeichnung("Pflegefachkraft", amtlich), amtlich


def test_987_fachrichtung_wird_nicht_zum_synonym():
    """"Elektrotechnik" ist eine Fachrichtung, kein zweiter Berufsname."""
    formen = bb._formen("Ingenieur/in - Elektrotechnik")
    assert "Elektrotechnik" not in formen
    assert formen == ["Ingenieur", "Ingenieurin"]


def test_987_mehrwort_bezeichnung_wird_nicht_zerlegt():
    """"Technische" allein traefe jede zweite Anzeige."""
    formen = bb._formen("Technische/r Produktdesigner/in")
    assert "Technische" not in formen
    assert "Produktdesigner" not in formen
    assert "Technischer Produktdesigner" in formen


def test_987_breite_facette_gilt_nicht_als_beruf():
    """Ein Beruf zieht seine Bezeichnungen an sich, eine Sache streut."""
    breit = {"facetten": {"beruf": {"counts": {
        "IT-Berater/in": 125, "Ingenieur/in - Maschinenbau": 104,
        "Ingenieur/in - Elektrotechnik": 59, "Informatiker/in": 38,
        "Konstrukteur/in": 29, "Sonstige": 712,
    }}}}
    assert bb._aus_facette(breit, "PLM") == []
    # Ohne Begriff bleibt das Verhalten von v1.7.28 — die Funktion wird
    # auch von Tests und Diagnosen ohne Kontext aufgerufen.
    assert bb._aus_facette(breit) != []


# ── Nadeloehr ─────────────────────────────────────────────────────────

class _DB:
    """Minimale Attrappe: nur die vier Methoden, die das Nadeloehr nutzt."""

    def __init__(self, kriterien, einstellungen=None, bewerbungen=()):
        self._kriterien = kriterien
        self._einstellungen = dict(einstellungen or {})
        self._bewerbungen = list(bewerbungen)

    def get_search_criteria(self):
        return dict(self._kriterien)

    def get_profile_setting(self, key, default=None):
        return self._einstellungen.get(key, default)

    def set_profile_setting(self, key, wert):
        self._einstellungen[key] = wert

    def get_applications(self):
        return list(self._bewerbungen)


def test_987_nadeloehr_liefert_gespeicherte_synonyme():
    db = _DB(_kriterien(), {sk.EINSTELLUNG: {"PLM": ["Produktlebenszyklus"]}})
    krit = sk.fuer_scoring(db)
    assert krit["_muss_synonyme"] == {"PLM": ["Produktlebenszyklus"]}


def test_987_nadeloehr_vergisst_entfernte_begriffe():
    """Wer ein MUSS-Keyword streicht, schleppt seine Synonyme nicht mit."""
    db = _DB(_kriterien(keywords_muss=["PDM"]),
             {sk.EINSTELLUNG: {"PLM": ["Produktlebenszyklus"],
                               "PDM": ["Produktdatenverwaltung"]}})
    krit = sk.fuer_scoring(db)
    assert set(krit["_muss_synonyme"]) == {"PDM"}


def test_987_nadeloehr_bringt_beworbene_titel_mit():
    db = _DB(_kriterien(), bewerbungen=[
        {"title": "PLM Manager", "status": "beworben"},
        {"title": "Alt-Bewerbung", "status": "abgelehnt"},
    ])
    krit = sk.fuer_scoring(db)
    assert krit["_applied_titles"] == ["plm manager"]


def test_987_nadeloehr_ueberlebt_eine_kaputte_datenbank():
    """Eine fehlende Auskunft darf keinen Suchlauf stoppen."""
    class _Kaputt(_DB):
        def get_applications(self):
            raise RuntimeError("Tabelle weg")

        def get_profile_setting(self, key, default=None):
            raise RuntimeError("Einstellungen weg")

    krit = sk.fuer_scoring(_Kaputt(_kriterien()))
    assert krit["_applied_titles"] == []
    assert krit["_muss_synonyme"] == {}


def test_987_auffrischen_legt_die_synonyme_ab():
    class _Client:
        def get(self, url, params=None, headers=None):
            class _A:
                status_code = 200

                @staticmethod
                def json():
                    return {"facetten": {"beruf": {"counts": {
                        "Altenpfleger/in": 90, "Zahnarzthelfer/in": 10}}}}
            return _A()

        def close(self):
            pass

    bb.cache_leeren()
    db = _DB({"keywords_muss": ["Pflegefachkraft"]})
    erg = sk.synonyme_auffrischen(db, client=_Client())
    assert "Altenpfleger" in erg.get("Pflegefachkraft", [])
    assert db.get_profile_setting(sk.EINSTELLUNG) == erg
    bb.cache_leeren()


def test_987_leere_auskunft_loescht_den_stand_nicht():
    """Sonst haengt der Score daran, ob das Netz gerade da ist.

    Die Abfrage schluckt ihren Ausfall (#969) — "nicht erreichbar" und
    "nichts gefunden" sehen von aussen gleich aus. Ueber einen
    vorhandenen Stand darf ein leeres Ergebnis deshalb nicht schreiben.
    """
    class _Tot:
        def get(self, *a, **k):
            raise OSError("kein Netz")

        def close(self):
            pass

    bb.cache_leeren()
    vorher = {"Pflegefachkraft": ["Altenpfleger"]}
    db = _DB({"keywords_muss": ["Pflegefachkraft"]}, {sk.EINSTELLUNG: vorher})
    erg = sk.synonyme_auffrischen(db, client=_Tot())
    assert erg == vorher
    assert db.get_profile_setting(sk.EINSTELLUNG) == vorher
    bb.cache_leeren()


# ── Teilscores ────────────────────────────────────────────────────────

@pytest.mark.parametrize("kriterien,erwartet_grund", [
    (_kriterien(keywords_ausschluss=["Elektrotechnik"]), "_ko_ausschluss"),
    (_kriterien(keywords_muss=["Pflegefachkraft"]), "_ko_kein_muss"),
])
def test_987_teilscores_auch_beim_frueh_ausstieg(kriterien, erwartet_grund):
    """Sonst steht der alte Fachscore neben dem neuen Gesamtscore.

    Gemeldet als "fachscore 56 gegen score 1": die Teilscores wurden erst
    am regulaeren Ende gesetzt, `scores_neu_berechnen` fand nichts zum
    Nachziehen, und in der Datenbank blieb der Altwert stehen.
    """
    job = dict(FREMDE_STELLE, _fachscore=56, _rahmenscore=12)
    score = calculate_score(job, kriterien)
    assert score == 0
    assert job.get(erwartet_grund)
    assert job["_fachscore"] == 0
    assert job["_rahmenscore"] == 0


def test_987_teilscores_beim_regulaeren_ausgang_unveraendert():
    """Die Haertung darf den Normalfall nicht verschieben (#942)."""
    job = {"title": "PLM Berater", "company": "Beispiel GmbH",
           "location": "Hamburg", "description": "PLM und PDM im Einsatz.",
           "url": "https://example.invalid/2"}
    score = calculate_score(job, _kriterien())
    assert score > 0
    assert job["_fachscore"] > 0
    assert "_rahmen_ungedeckelt" in job


# ── Der Vertrag, um den es geht ───────────────────────────────────────

def test_987_alle_wege_bauen_die_kriterien_aus_demselben_nadeloehr():
    """DoD 8c: ein Nadeloehr zaehlt erst, wenn es auch aufgerufen wird.

    Die Anreicherung stand frueher woertlich im Suchlauf. Dieser Test
    haelt fest, dass keiner der score-schreibenden Wege sie noch einmal
    selbst baut — genau so ist die Divergenz entstanden.
    """
    wurzel = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
    dateien = [
        wurzel / "job_scraper" / "__init__.py",
        wurzel / "tools" / "jobs.py",
        wurzel / "dashboard.py",
        wurzel / "services" / "newsletter_service.py",
    ]
    for datei in dateien:
        text = datei.read_text(encoding="utf-8")
        # Kommentarzeilen raus: sie erklaeren die Historie und duerfen
        # den Begriff nennen (Lehre aus #978, MERKE 6).
        code = "\n".join(z for z in text.splitlines()
                         if not z.lstrip().startswith("#"))
        assert '_applied_titles"] =' not in code, datei.name
        assert '_muss_synonyme"] =' not in code, datei.name


def test_987_echte_datenbank_liefert_beiden_wegen_denselben_score(tmp_path):
    """AK 3: unmittelbar nach dem Anlegen gibt es keine Abweichung mehr.

    Bewusst gegen die ECHTE Datenbankklasse, nicht gegen die Attrappe —
    der Fehler sass in der Verdrahtung, nicht in der Rechnung.
    """
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database as _database
    importlib.reload(_database)
    db = _database.Database()
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    try:
        db.save_profile({"name": "Test Person", "email": "test@example.invalid"})
        db.set_search_criteria("keywords_muss", MUSS_TECHNIK)
        db.set_search_criteria("keywords_plus", ["Hamburg"])
        db.set_profile_setting(sk.EINSTELLUNG, SYNONYME_ALT)

        # Anlage-Pfad
        krit_anlage = sk.fuer_scoring(db)
        job = dict(FREMDE_STELLE, hash="test:987", source="test")
        job["score"] = calculate_score(job, krit_anlage)
        db.save_jobs([job])

        # Nachrechnen-Pfad
        gespeichert = db.get_job("test:987")
        krit_neu = sk.fuer_scoring(db)
        neu = calculate_score(dict(gespeichert), krit_neu)

        assert int(gespeichert["score"]) == int(neu), (
            f"gespeichert {gespeichert['score']}, neu berechnet {neu}")
    finally:
        db.close()
        os.environ.pop("BA_DATA_DIR", None)
        importlib.reload(_database)


def test_987_score_hinweis_nennt_den_selben_tag():
    """Der alte Hinweis schloss die echte Ursache aus.

    "Meist ist der gespeicherte Wert aelter als die Kriterien" stand
    ueber einer Stelle, die am selben Tag angelegt worden war. Ein
    Hinweis, der die Ursache wegerklaert, ist schlimmer als keiner.
    """
    quelle = (Path(__file__).resolve().parents[1] / "src"
              / "bewerbungs_assistent" / "tools" / "jobs.py"
              ).read_text(encoding="utf-8")
    assert "am_selben_tag_angelegt" in quelle
    assert "HEUTE angelegt" in quelle
