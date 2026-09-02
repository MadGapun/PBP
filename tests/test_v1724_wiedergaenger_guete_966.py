"""Tests fuer v1.7.24 — #966: ein Urteil wiegt nicht mehr als seine Grundlage.

Der Wiedergaenger-Mechanismus (#671) funktionierte wie gebaut — er
verarbeitete nur Urteile weiter, die nie belastbar waren.

Belegter Fall vom 02.09.2026: eine aktive Stelle wurde als
NICHT_EMPFOHLEN gefuehrt und ans Ende sortiert, weil dieselbe Rolle bei
derselben Firma zweimal mit `gehalt_zu_niedrig` verworfen worden war.
Beide Altfassungen waren Anzeigen-Rumpfe von 155 und 168 Zeichen, beide
Gehaltsspannen GESCHAETZT. Die aktive Fassung hat 1977 Zeichen und eine
geschaetzte Spanne oberhalb der Schwelle. Beide Zahlen sind
Schaetzungen, sie zeigen nur in verschiedene Richtungen.

#827 hatte die richtige Regel bereits gezogen: ein geschaetztes Gehalt
wird im Scoring neutral gewertet. Die Regel wirkte aber nur nach vorn —
ein Grund, der historisch aus einer Schaetzung entstand, zaehlte
unveraendert weiter und fiel sogar doppelt ins Gewicht, weil er zweimal
vorkam.

Kein Auto-Fix: alte Urteile werden nicht geloescht, sie sollen nur
nicht schwerer wiegen als das, worauf sie beruhen.
"""
import pytest

from bewerbungs_assistent.services.wiedergaenger import (
    MINDESTLAENGE_BELASTBAR,
    find_wiedergaenger_pattern,
    firmen_historie,
    grund_guete,
)

VOLL = ("Aufgaben: Betreuung und Weiterentwicklung der PLM-Landschaft, "
        "Abstimmung mit den Fachbereichen, Steuerung externer Dienstleister "
        "und Migration bestehender Strukturen. Anforderungen: "
        "abgeschlossenes Studium, mehrjaehrige Berufserfahrung, sichere "
        "Kommunikation in Deutsch und Englisch.")
RUMPF = "PLM Manager gesucht. Bewerbung ueber das Portal."

assert len(VOLL) >= MINDESTLAENGE_BELASTBAR
assert len(RUMPF) < MINDESTLAENGE_BELASTBAR


# ── Die Guete selbst ─────────────────────────────────────────────────

def test_966_geschaetztes_gehalt_macht_den_grund_schwach():
    """Der Kernfall."""
    guete, warum = grund_guete({
        "description": RUMPF, "dismiss_reason": "gehalt_zu_niedrig",
        "salary_estimated": 1})
    assert guete == "schwach"
    assert "geschaetzt" in warum


def test_966_belegtes_gehalt_bleibt_belastbar():
    """Gegenprobe — sonst entwertet die Haertung jedes Gehalts-Urteil."""
    guete, _ = grund_guete({
        "description": VOLL, "dismiss_reason": "gehalt_zu_niedrig",
        "salary_estimated": 0})
    assert guete == "belegt"


def test_966_rumpfanzeige_macht_fachurteile_schwach():
    """Bei 155 Zeichen kann das Fachgebiet nicht beurteilt worden sein."""
    guete, warum = grund_guete({
        "description": RUMPF, "dismiss_reason": "falsches_fachgebiet"})
    assert guete == "schwach"
    assert "Zeichen" in warum


@pytest.mark.parametrize("grund", [
    "zeitarbeit", "befristet", "firma_uninteressant", "zu_weit_entfernt",
    "unpassendes_arbeitsmodell",
])
def test_966_nicht_textabhaengige_gruende_bleiben_belastbar(grund):
    """Die Gegenrichtung, und der teurere Fehler.

    Zeitarbeit und Befristung erkennt man an Firma und Titel, die
    Entfernung steht in einem eigenen Feld. Wer die Liste zu breit
    zieht, entwertet Urteile, die sehr wohl belastbar waren — und der
    Mechanismus verstummt.
    """
    guete, _ = grund_guete({"description": RUMPF, "dismiss_reason": grund})
    assert guete == "belegt", grund


def test_966_fehlender_text_ist_unbekannt_nicht_schwach():
    """Aus fehlendem Wissen ein Urteil abzuleiten waere derselbe Fehler,
    den #965 im Entfernungs-Scoring behebt: unbekannt ist nicht gleich
    schlecht."""
    guete, _ = grund_guete({"dismiss_reason": "falsches_fachgebiet"})
    assert guete == "belegt"


# ── Wirkung im Mechanismus ───────────────────────────────────────────

def _verwerfen(db, kurz, titel, firma, beschreibung, grund, geschaetzt=0):
    pid = db.get_active_profile_id() or ""
    voll = f"{pid}:{kurz}"
    db.save_jobs([{
        "hash": voll, "title": titel, "company": firma,
        "url": f"https://example.com/{kurz}", "source": "manuell",
        "description": beschreibung, "salary_estimated": geschaetzt,
        "score": 10,
    }])
    db.dismiss_job(voll, grund)
    return voll


@pytest.fixture
def db(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    return tmp_db


def test_966_zwei_schwache_urteile_ergeben_kein_ko(db):
    """Der gemeldete Fall, woertlich: zwei Schaetzungen an leeren
    Anzeigen ergaben ein Firmen-Muster, das die vollstaendige Anzeige
    abwertete."""
    _verwerfen(db, "g1", "PLM Manager", "Musterfirma GmbH", RUMPF,
               "gehalt_zu_niedrig", geschaetzt=1)
    _verwerfen(db, "g2", "PLM Manager", "Musterfirma GmbH", RUMPF,
               "gehalt_zu_niedrig", geschaetzt=1)
    assert find_wiedergaenger_pattern(
        db, "Musterfirma GmbH", "PLM Manager (m/w/d)", schwellwert=2) is None


def test_966_zwei_belegte_urteile_ergeben_weiterhin_ein_ko(db):
    """Die Gegenprobe. Eine Haertung, die den Mechanismus abschaltet,
    waere keine Verbesserung."""
    _verwerfen(db, "b1", "PLM Manager", "Musterfirma GmbH", VOLL,
               "gehalt_zu_niedrig")
    _verwerfen(db, "b2", "PLM Manager", "Musterfirma GmbH", VOLL,
               "gehalt_zu_niedrig")
    muster = find_wiedergaenger_pattern(
        db, "Musterfirma GmbH", "PLM Manager (m/w/d)", schwellwert=2)
    assert muster is not None
    assert muster["top_grund"] == "gehalt_zu_niedrig"


def test_966_ein_belegtes_plus_zwei_schwache_traegt(db):
    """Schwache Urteile zaehlen halb, nicht gar nicht — sie sind ja
    nicht falsch, nur duenn belegt."""
    _verwerfen(db, "m1", "PLM Manager", "Musterfirma GmbH", VOLL,
               "gehalt_zu_niedrig")
    _verwerfen(db, "m2", "PLM Manager", "Musterfirma GmbH", RUMPF,
               "gehalt_zu_niedrig", geschaetzt=1)
    _verwerfen(db, "m3", "PLM Manager", "Musterfirma GmbH", RUMPF,
               "gehalt_zu_niedrig", geschaetzt=1)
    muster = find_wiedergaenger_pattern(
        db, "Musterfirma GmbH", "PLM Manager (m/w/d)", schwellwert=2)
    assert muster is not None
    assert muster["gewicht_nach_guete"]["gehalt_zu_niedrig"] == 2.0


def test_966_hinweis_nennt_die_grundlage(db):
    """AK 3: '2x mit Grund gehalt_zu_niedrig' klingt nach einem harten
    Befund. Dieselbe Tatsache, richtig eingeordnet, liest sich anders."""
    _verwerfen(db, "h1", "PLM Manager", "Musterfirma GmbH", VOLL,
               "gehalt_zu_niedrig")
    _verwerfen(db, "h2", "PLM Manager", "Musterfirma GmbH", VOLL,
               "gehalt_zu_niedrig")
    _verwerfen(db, "h3", "PLM Manager", "Musterfirma GmbH", RUMPF,
               "gehalt_zu_niedrig", geschaetzt=1)
    muster = find_wiedergaenger_pattern(
        db, "Musterfirma GmbH", "PLM Manager (m/w/d)", schwellwert=2)
    assert "Grundlage" in muster["hinweis"], muster["hinweis"]
    assert "geschaetzt" in muster["hinweis"]
    assert muster["schwache_urteile"] == 1


# ── Nebenbefund: zwei Tools, zwei Zahlen ─────────────────────────────

def test_966_beide_ansichten_zaehlen_gleich(db):
    """Fuer dieselbe Firma lieferten fit_analyse und firma_kontext
    unterschiedliche Zahlen. Solange die Zaehlweise nicht dieselbe ist,
    widersprechen sich zwei Ansichten desselben Sachverhalts — und die
    Schwelle haengt davon ab, welche gilt."""
    _verwerfen(db, "z1", "PLM Manager", "Musterfirma GmbH", VOLL,
               "gehalt_zu_niedrig")
    _verwerfen(db, "z2", "PLM Manager", "Musterfirma GmbH", VOLL,
               "gehalt_zu_niedrig")
    muster = find_wiedergaenger_pattern(
        db, "Musterfirma GmbH", "PLM Manager (m/w/d)", schwellwert=2)
    historie = firmen_historie(db, "Musterfirma GmbH")
    assert muster["alle_gruende"]["gehalt_zu_niedrig"] == \
        historie["gruende"]["gehalt_zu_niedrig"], (muster, historie)


def test_966_zaehlweise_ist_benannt(db):
    """Eine Zahl ohne Einheit laesst sich nicht pruefen."""
    _verwerfen(db, "e1", "PLM Manager", "Musterfirma GmbH", VOLL,
               "gehalt_zu_niedrig")
    _verwerfen(db, "e2", "PLM Manager", "Musterfirma GmbH", VOLL,
               "gehalt_zu_niedrig")
    muster = find_wiedergaenger_pattern(
        db, "Musterfirma GmbH", "PLM Manager (m/w/d)", schwellwert=2)
    assert "zaehlweise" in muster
    assert "zaehlweise" in firmen_historie(db, "Musterfirma GmbH")


def test_966_bestandsbericht_existiert():
    """AK 4: der Altlast-Umfang muss messbar sein, ohne Direkt-SQL
    (#514)."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "tools" / "jobs.py").read_text(encoding="utf-8")
    assert "schwache_aussortier_urteile" in quelle
    assert "stelle_reaktivieren" in quelle
