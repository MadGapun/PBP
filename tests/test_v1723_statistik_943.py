"""Tests fuer v1.7.23 — #943: Statistik klassifiziert und interpretiert falsch.

Die Grundrechenarten stimmten durchgehend. Die Befunde betrafen das
KLASSIFIZIEREN und INTERPRETIEREN:

* 13 von 16 als "automatisch abgelehnt" gefuehrten Faellen trugen
  woertlich "Keine Rueckmeldung" — das Gegenteil einer automatischen
  Ablehnung.
* Der Median "Zeit bis erste Reaktion" lag bei 0,0 Tagen, weil bei
  rekonstruierten Altbewerbungen beide Daten am selben Tag nachgetragen
  wurden.
* Vermutungen des Nutzers waren beim Auswerten nicht mehr von belegten
  Tatsachen zu unterscheiden.

Warum das mehr als Kosmetik ist: die Kategorien fuehren zu
ENTGEGENGESETZTEN Handlungen. Automatische Ablehnung heisst Unterlagen
pruefen, stille Absage heisst frueher nachfassen.
"""
import pytest

from bewerbungs_assistent.services.statistik_erweitert import (
    _ablehnungs_kategorie,
    sicherheitsgrad,
)


def _ev(status, datum):
    return {"status": status, "datum": datum}


# ── Befund 1: Klassifizierung nach Inhalt ────────────────────────────

def test_943_keine_rueckmeldung_ist_keine_automatische_ablehnung():
    """Der Kernfall: 13 von 16 trugen genau diesen Text."""
    a = {"status": "abgelehnt",
         "rejection_reason": "Keine Rueckmeldung - stille Absage"}
    events = [_ev("beworben", "2026-04-01T09:00:00"),
              _ev("abgelehnt", "2026-04-01T09:00:00")]
    assert _ablehnungs_kategorie(a, events) == "stille_absage"


def test_943_selber_tag_ist_kein_signal_sondern_ein_artefakt():
    """Bei rekonstruierten Altbewerbungen wurden beide Daten am selben
    Tag nachgetragen — die Differenz sagt nichts ueber den Arbeitgeber."""
    a = {"status": "abgelehnt", "rejection_reason": ""}
    events = [_ev("beworben", "2026-04-01T09:00:00"),
              _ev("abgelehnt", "2026-04-01T09:00:00")]
    assert _ablehnungs_kategorie(a, events) != "automatische_ablehnung"


def test_943_automatik_braucht_ein_positives_signal():
    """Ein ausdruecklicher Vermerk qualifiziert — auch ohne Zeitabstand."""
    a = {"status": "abgelehnt",
         "rejection_reason": "Automatisierte Absage, nicht durch das "
                             "AI-Screening gekommen"}
    events = [_ev("beworben", "2026-04-01T09:00:00"),
              _ev("abgelehnt", "2026-06-01T09:00:00")]
    assert _ablehnungs_kategorie(a, events) == "automatische_ablehnung"


def test_943_schnelle_absage_bleibt_automatisch():
    """Die zweite Form des positiven Signals: Absage binnen 48 Stunden.

    Beleg aus dem Issue: Bewerbung Freitagabend, Absage Sonntagabend.
    """
    a = {"status": "abgelehnt", "rejection_reason": ""}
    events = [_ev("beworben", "2026-04-03T18:00:00"),
              _ev("abgelehnt", "2026-04-05T20:00:00")]
    assert _ablehnungs_kategorie(a, events) == "automatische_ablehnung"


def test_943_stille_absage_schlaegt_den_zeitabstand():
    """Selbst bei kurzem Abstand: 'keine Antwort' ist keine Absage."""
    a = {"status": "abgelehnt",
         "rejection_reason": "Keine Antwort seit drei Monaten"}
    events = [_ev("beworben", "2026-04-01T09:00:00"),
              _ev("abgelehnt", "2026-04-02T09:00:00")]
    assert _ablehnungs_kategorie(a, events) == "stille_absage"


# ── Befund 5: Vermutung, Fakt, eigene Wertung ────────────────────────

def test_943_vermutung_wird_als_solche_erkannt():
    assert sicherheitsgrad(
        {"rejection_reason": "Vermutlich automatisch aussortiert"}
    ) == "vermutet"


def test_943_eigene_wertung_wird_erkannt():
    """Besonders heikel: der Nutzer hat selbst auf 'abgelehnt' gesetzt,
    ohne dass je eine Absage kam. In der Statistik treibt das die Quote."""
    assert sicherheitsgrad(
        {"rejection_reason": "Keine Rueckmeldung seit >3 Monaten, "
                             "als stille Absage gewertet"}
    ) == "eigene_wertung"


def test_943_belegter_grund_bleibt_belegt():
    assert sicherheitsgrad(
        {"rejection_reason": "Absage per Mail: Stelle intern besetzt"}
    ) == "belegt"


def test_943_leerer_grund_gilt_als_belegt_nicht_als_vermutung():
    """Kein Text heisst 'kein Signal', nicht 'Vermutung'."""
    assert sicherheitsgrad({}) == "belegt"


# ── Befund 4: Ablehnung und Versanden getrennt ───────────────────────

def test_943_abgelehnt_und_versandet_werden_getrennt_ausgewiesen(tmp_db):
    """Ein abgelaufener Vorgang ist keine Ablehnung — er heisst, dass
    nichts mehr passiert ist, oft weil niemand nachgefasst hat."""
    from bewerbungs_assistent.services.statistik_erweitert import (
        ablehnungs_kategorien)
    for i in range(3):
        tmp_db.add_application({
            "title": f"Stelle {i}", "company": f"Firma {i} GmbH",
            "position": f"Stelle {i}", "status": "abgelehnt",
            "applied_at": "2026-04-01",
        })
    for i in range(2):
        tmp_db.add_application({
            "title": f"Alt {i}", "company": f"Alt {i} GmbH",
            "position": f"Alt {i}", "status": "abgelaufen",
            "applied_at": "2026-01-01",
        })
    erg = ablehnungs_kategorien(tmp_db)
    assert "abgelehnt_quote" in erg
    assert "versandet_quote" in erg
    assert erg["abgelehnt_quote"] > erg["versandet_quote"]
    assert "abgelehnt" in erg["abgelehnt_vs_versandet"]
    assert "versandet" in erg["abgelehnt_vs_versandet"]
    # Die Rohquote bleibt, wird aber erklaert.
    assert "ablehnungsquote_hinweis" in erg


def test_943_sicherheitsgrad_wird_aggregiert(tmp_db):
    from bewerbungs_assistent.services.statistik_erweitert import (
        ablehnungs_kategorien)
    aid = tmp_db.add_application({
        "title": "Stelle", "company": "Musterfirma GmbH",
        "position": "Stelle", "status": "abgelehnt", "applied_at": "2026-04-01",
    })
    tmp_db.connect().execute(
        "UPDATE applications SET rejection_reason=? WHERE id=?",
        ("Vermutlich wegen fehlender Zertifizierung", aid))
    tmp_db.connect().commit()
    erg = ablehnungs_kategorien(tmp_db)
    assert erg["sicherheit"].get("vermutet", 0) >= 1
    assert "sicherheit_hinweis" in erg


# ── Befund 2: Zeitkennzahlen nur aus belastbaren Vorgaengen ──────────

def test_943_zeitkennzahlen_nennen_ihre_basis(tmp_db):
    from bewerbungs_assistent.services.statistik_erweitert import (
        zeitliche_kennzahlen)
    erg = zeitliche_kennzahlen(tmp_db)
    assert "zeitkennzahlen_basis" in erg
    # Ausgeschlossen wird der Null-Abstand (Signatur der rekonstruierten
    # Altbewerbungen), nicht pauschal jeder Vorgang mit wenigen
    # Ereignissen — eine echte Absage nach zwei Tagen bleibt ein
    # gueltiger Datenpunkt.
    assert "0 Tage" in erg["zeitkennzahlen_basis"]
    assert "zeitkennzahlen_ausgeschlossen" in erg
    # Fallzahl je Kennzahl
    assert "anzahl" in erg["zeit_bis_erste_reaktion"]


# ── Befund 3: active_jobs stimmt mit der Liste ueberein ──────────────

def test_943_active_jobs_hat_dieselbe_basis_wie_die_liste(tmp_db):
    """Beide sollen dasselbe beschreiben — vorher wichen sie um die
    geblockten Stellen ab."""
    tmp_db.save_jobs([
        {"hash": "s943a", "title": "PLM Berater", "company": "Gute Firma GmbH",
         "url": "https://example.com/a", "source": "bundesagentur", "score": 40},
        {"hash": "s943b", "title": "PLM Berater", "company": "Geblockt GmbH",
         "url": "https://example.com/b", "source": "bundesagentur", "score": 40},
    ])
    tmp_db.add_to_blacklist("firma", "Geblockt GmbH", "Test")
    stats = tmp_db.get_statistics()
    aus_liste = len(tmp_db.get_active_jobs(exclude_blacklisted=True))
    assert stats["active_jobs"] == aus_liste, stats
    assert stats["active_jobs_roh"] >= stats["active_jobs"]
    if stats["active_jobs_roh"] != stats["active_jobs"]:
        assert "active_jobs_hinweis" in stats


def test_943_differenz_zu_scored_jobs_ist_erklaert(tmp_db):
    stats = tmp_db.get_statistics()
    assert "scored_jobs_hinweis" in stats


# ── Die drei geforderten Auswertungen ────────────────────────────────

def test_943_erfolg_nach_score_band(tmp_db):
    """Die einzige Moeglichkeit, das Scoring gegen die Realitaet zu
    pruefen."""
    from bewerbungs_assistent.services.statistik_erweitert import (
        erfolg_nach_score_band)
    erg = erfolg_nach_score_band(tmp_db)
    assert "baender" in erg
    assert set(erg["baender"]) == {"0-24", "25-49", "50-74", "75+"}
    for band in erg["baender"].values():
        assert "interview_quote" in band
    assert "ohne_verknuepfte_stelle" in erg


def test_943_nachfass_wirksamkeit(tmp_db):
    from bewerbungs_assistent.services.statistik_erweitert import (
        nachfass_wirksamkeit)
    erg = nachfass_wirksamkeit(tmp_db)
    assert "mit_nachfassen" in erg and "ohne_nachfassen" in erg
    # Bei leerem Bestand ehrlich sagen, dass es keine Aussage gibt.
    assert "Zu wenige" in erg["aussage"]


def test_943_trend_vergleich(tmp_db):
    from bewerbungs_assistent.services.statistik_erweitert import (
        trend_vergleich)
    erg = trend_vergleich(tmp_db)
    assert "letzte_3_monate" in erg and "3_monate_davor" in erg
    assert erg["aussage"]
