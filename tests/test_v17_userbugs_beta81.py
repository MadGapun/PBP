"""Tests fuer User-Test-Findings aus beta.80 (beta.81).

- #659: profil_bearbeiten lehnt Umlaut-Varianten (aendern/aktion) ab
- #661: scoring_vorschau crasht bei distance-Bracket '50km'
- #662: fit_analyse soll ein scharfes Empfehlung-Feld liefern
"""
from __future__ import annotations

import logging


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _register_profil(tmp_db):
    from bewerbungs_assistent.tools.profil import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


# ── #659 — Umlaut-Normalisierung profil_bearbeiten ───────────────────────


def test_profil_bearbeiten_aktion_umlaut_aendern(tmp_db):
    """`aktion='ändern'` darf nicht mit 'Ungueltige Kombination' fallen."""
    tmp_db.create_profile("Test User", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    pos_id = tmp_db.add_position({
        "company": "Firma X", "title": "Architekt",
        "start_date": "2018-01", "end_date": "2018-06",
        "profile_id": pid,
    })

    mcp = _register_profil(tmp_db)
    fn = mcp.tools["profil_bearbeiten"]

    result = fn(
        bereich="position", aktion="ändern",
        element_id=pos_id,
        daten={"end_date": "2018-12"},
    )
    assert "fehler" not in result, f"Unerwarteter Fehler: {result}"
    assert result.get("status") == "aktualisiert"


def test_profil_bearbeiten_aktion_ascii_aendern_weiterhin_ok(tmp_db):
    """Bestehender ASCII-Aufruf bleibt grün."""
    tmp_db.create_profile("Test User", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    pos_id = tmp_db.add_position({
        "company": "Firma X", "title": "Architekt",
        "start_date": "2018-01", "end_date": "2018-06",
        "profile_id": pid,
    })

    mcp = _register_profil(tmp_db)
    fn = mcp.tools["profil_bearbeiten"]

    result = fn(
        bereich="position", aktion="aendern",
        element_id=pos_id,
        daten={"end_date": "2018-12"},
    )
    assert "fehler" not in result
    assert result.get("status") == "aktualisiert"


def test_profil_bearbeiten_bereich_persoenlich_umlaut(tmp_db):
    """`bereich='persönlich'` mit Umlaut auch akzeptiert."""
    tmp_db.create_profile("Test User", "test@example.com")
    mcp = _register_profil(tmp_db)
    fn = mcp.tools["profil_bearbeiten"]

    result = fn(
        bereich="persönlich", aktion="ändern",
        daten={"city": "Bremen"},
    )
    assert "fehler" not in result


def test_profil_bearbeiten_loeschen_umlaut(tmp_db):
    """`aktion='löschen'` mit Umlaut funktioniert."""
    tmp_db.create_profile("Test User", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    skill_id = tmp_db.add_skill({"name": "Python", "profile_id": pid})

    mcp = _register_profil(tmp_db)
    fn = mcp.tools["profil_bearbeiten"]

    result = fn(
        bereich="skill", aktion="löschen",
        element_id=skill_id,
    )
    assert "fehler" not in result


def test_profil_bearbeiten_hinzufuegen_umlaut(tmp_db):
    """`aktion='hinzufügen'` mit Umlaut funktioniert."""
    tmp_db.create_profile("Test User", "test@example.com")
    mcp = _register_profil(tmp_db)
    fn = mcp.tools["profil_bearbeiten"]

    result = fn(
        bereich="skill", aktion="hinzufügen",
        daten={"name": "Rust"},
    )
    assert "fehler" not in result


# ── #661 — scoring_service bracket '50km'-Parse ──────────────────────────


def test_scoring_brackets_mit_einheit_string_parsbar():
    """Bracket-Key 'XXkm' darf nicht mehr crashen — Ziffern werden
    extrahiert, Rest ignoriert."""
    from bewerbungs_assistent.services.scoring_service import apply_scoring_adjustments

    # Mock-DB mit problematischer scoring_config (Bracket-Key '50km'
    # statt '50'). Reproduziert das ValueError-Pattern aus #661.
    class _MockDB:
        def get_scoring_config(self):
            return [
                {"dimension": "entfernung_fest", "sub_key": "50km", "value": -3, "ignore_flag": 0},
                {"dimension": "entfernung_fest", "sub_key": "100",  "value": -5, "ignore_flag": 0},
                {"dimension": "remote", "sub_key": "vollremote",    "value": 0,  "ignore_flag": 0},
                {"dimension": "gehalt", "sub_key": "pro_10_prozent","value": 0,  "ignore_flag": 0},
            ]
        def get_search_criteria(self):
            return {}

    job = {
        "score": 50,
        "remote_level": "vollremote",
        "employment_type": "festanstellung",
        "distance_km": 40,
    }

    # Vorher: ValueError("invalid literal for int(): '50km'")
    result = apply_scoring_adjustments(job, 50, _MockDB())
    assert "final_score" in result


def test_scoring_brackets_bracket_ohne_ziffern_uebersprungen():
    """Brackets ohne jegliche Ziffern werden uebersprungen."""
    from bewerbungs_assistent.services.scoring_service import apply_scoring_adjustments

    class _MockDB2:
        def get_scoring_config(self):
            return [
                {"dimension": "entfernung_fest", "sub_key": "weit",   "value": -3, "ignore_flag": 0},
                {"dimension": "entfernung_fest", "sub_key": "30",     "value": -1, "ignore_flag": 0},
                {"dimension": "remote", "sub_key": "vollremote",      "value": 0,  "ignore_flag": 0},
                {"dimension": "gehalt", "sub_key": "pro_10_prozent",  "value": 0,  "ignore_flag": 0},
            ]
        def get_search_criteria(self):
            return {}

    job = {"score": 50, "remote_level": "vollremote",
           "employment_type": "festanstellung", "distance_km": 20}
    result = apply_scoring_adjustments(job, 50, _MockDB2())
    assert "final_score" in result


# ── #662 — fit_analyse Empfehlung-Verdict ────────────────────────────────

def test_empfehlung_folgt_NICHT_dem_score():
    """Der Kern von #1003 — und die Umkehr des alten Vertrags.

    Bis v1.7.60 stand hier: Score 80 von 100 -> EMPFOHLEN, 60 ->
    BEDINGT, 20 -> NICHT_EMPFOHLEN. Der Nutzer hat den Denkfehler
    benannt:

        "Ob es eine Empfehlung gibt, hat nichts mit den Punkten zu tun —
        das ist nur ein Indikator fuer die Suchbegriffe."

    In den Score gehen Keyword-Treffer, Gehalt, Entfernung und
    Remote-Grad ein. Der LEBENSLAUF geht nicht ein. Ein hoher Score
    heisst: die Anzeige trifft meine Suchbegriffe gut — nicht: ich passe.

    Dieser Test haelt die Umkehr fest: **kein Score, wie hoch auch
    immer, erzeugt von sich aus eine Empfehlung.** Er ist die Wache
    dagegen, dass die Schwellen zurueckkommen.
    """
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    for score in (100, 80, 60, 20, 0):
        fit_result = {
            "total_score": score, "total_score_max": 100,
            "muss_hits": ["python", "fastapi"], "missing_muss": [],
            "risks": [], "beschreibung_vorhanden": True,
        }
        v = _build_empfehlung(fit_result, {}, profil_kompetenzen=12)
        assert v["kategorie"] == "NICHT_BEURTEILBAR", (
            f"Score {score} hat einen Verdict erzeugt: {v['kategorie']}")
        assert v["grundlage"] == "keine_grundlage"
        assert v["warum"] == "nicht_gelesen"


def test_empfehlung_kommt_aus_der_gespeicherten_detailanalyse():
    """Woher der Verdict jetzt kommt.

    Die Analyse hat Anzeige und Profil gelesen; ihr Urteil gilt — und
    die Herkunft steht dabei, damit ein gelesenes Urteil in der Liste
    nicht aussieht wie ein gerechnetes.
    """
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    fit_result = {
        "total_score": 3, "total_score_max": 100,   # niedrig, egal
        "muss_hits": ["python"], "missing_muss": [],
        "risks": [], "beschreibung_vorhanden": True,
    }
    v = _build_empfehlung(
        fit_result, {}, profil_kompetenzen=12,
        gespeicherte_analyse={
            "urteil": "EMPFOHLEN",
            "begruendung": "Werdegang deckt die Rolle ab.",
            "grundlage": "detailanalyse", "am": "2026-09-09T10:00:00",
        })
    assert v["kategorie"] == "EMPFOHLEN"
    assert v["grundlage"] == "detailanalyse"
    assert "Werdegang" in v["begruendung"]
    # Der Score steht daneben — als das, was er ist.
    assert v["score"] == 3
    assert "SUCHBEGRIFFE" in v["score_bedeutung"]


def test_empfehlung_ohne_profil_ist_nicht_beurteilbar():
    """Ohne Kompetenzen im Profil gibt es nichts zu vergleichen.

    Das ist etwas anderes als "passt nicht" — genau die Verwechslung,
    die #989 abgeschafft hat.
    """
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    v = _build_empfehlung(
        {"total_score": 90, "total_score_max": 100, "muss_hits": ["x"],
         "missing_muss": [], "risks": [], "beschreibung_vorhanden": True},
        {}, profil_kompetenzen=0)
    assert v["kategorie"] == "NICHT_BEURTEILBAR"
    assert v["warum"] == "kein_profil"


def test_empfehlung_ko_bei_fehlender_beschreibung():
    """Fehlende Beschreibung ueberschreibt selbst hohen Score."""
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    fit_result = {
        "total_score": 85,
        "muss_hits": ["python"],
        "missing_muss": [],
        "risks": [],
        "beschreibung_vorhanden": False,
    }
    verdict = _build_empfehlung(fit_result, {})
    assert verdict["kategorie"] == "NICHT_EMPFOHLEN"
    assert any("Beschreibung" in g for g in verdict["ko_gruende"])


def test_972_hochschulabschluss_ist_kein_ko_kriterium_mehr():
    """Frueher: "Abschluss gefordert und nicht da" -> NICHT_EMPFOHLEN,
    egal wie hoch der Score.

    Genau das war der Schaden (#972): das Merkmal hatte keine
    modellierte Profilseite. Ein Staatlich gepruefter Techniker (DQR 6,
    wie Bachelor) galt als "kein Abschluss" — und eine Stelle mit Score
    80 wurde damit abgeraten.
    """
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    fit_result = {
        "total_score": 80,
        "muss_hits": ["python"],
        "missing_muss": [],
        "risks": [],
        "beschreibung_vorhanden": True,
    }
    verdict = _build_empfehlung(fit_result, {})
    assert verdict["kategorie"] != "NICHT_EMPFOHLEN"


def test_empfehlung_ko_bei_null_muss_hits():
    """Wenn 0 MUSS-Keywords matchen, aber MUSS-Keywords gefordert sind -> k.o."""
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    fit_result = {
        "total_score": 60,
        "muss_hits": [],
        "missing_muss": ["python", "fastapi", "sqlite"],
        "risks": [],
        "beschreibung_vorhanden": True,
    }
    verdict = _build_empfehlung(fit_result, {})
    assert verdict["kategorie"] == "NICHT_EMPFOHLEN"
    assert any("MUSS-Keyword" in g for g in verdict["ko_gruende"])


def test_empfehlung_hat_immer_die_pflichtfelder():
    """Format-Vertrag: kategorie + score + begruendung + kurz IMMER vorhanden.

    v1.7.49 (#999): vierte Kategorie `NICHT_BEURTEILBAR` fuer den Fall,
    dass der erreichbare Hoechstwert unbekannt ist. Eine Einordnung ohne
    Skala waere erfunden — und "unbekannt" ist etwas anderes als "passt
    nicht" (#989).
    """
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    for score in (0, 50, 75, 100):
        fit_result = {
            "total_score": score, "total_score_max": 100,
            "muss_hits": ["x"], "missing_muss": [],
            "risks": [], "beschreibung_vorhanden": True,
        }
        v = _build_empfehlung(fit_result, {})
        assert "kategorie" in v
        assert "score" in v
        assert "begruendung" in v
        assert "kurz" in v
        # #1003: der Score entscheidet die Kategorie nicht mehr.
        # Der Format-Vertrag gilt weiter — er ist der Grund fuer
        # diesen Test, nicht die Einstufung.
        from bewerbungs_assistent.services.passung import KATEGORIEN
        assert v["kategorie"] in KATEGORIEN
        assert v["grundlage"] in ("detailanalyse", "ko_kriterium",
                                  "keine_grundlage")

    # Ohne bekanntes Maximum: eigene Kategorie, kein geratener Verdict.
    ohne = _build_empfehlung(
        {"total_score": 12, "muss_hits": ["x"], "missing_muss": [],
         "risks": [], "beschreibung_vorhanden": True}, {})
    assert ohne["kategorie"] == "NICHT_BEURTEILBAR"
    for feld in ("kategorie", "score", "begruendung", "kurz"):
        assert feld in ohne
