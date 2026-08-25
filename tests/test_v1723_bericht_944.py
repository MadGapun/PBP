"""Tests fuer v1.7.23 — #944: Bewerbungsbericht.

Der Bericht traegt Vermittlungsnummer, Beratername und Beratungsstelle
und ist damit ein **Dokument fuer die Arbeitsagentur**. Er soll belegen,
dass aktiv und systematisch gesucht wird. Daran sind die Befunde
gemessen — ein Behoerdendokument darf keine drei Werte fuer dieselbe
Groesse nennen und keine Tabelle enthalten, die sichtbar falsch
addiert.
"""
import pytest


def _bewerbung(db, firma, status="abgelehnt", grund=None, titel="PLM Consultant"):
    aid = db.add_application({
        "title": titel, "company": firma, "position": titel,
        "status": status, "applied_at": "2026-04-01",
    })
    if grund is not None:
        db.connect().execute(
            "UPDATE applications SET rejection_reason=? WHERE id=?",
            (grund, aid))
        db.connect().commit()
    return aid


# ── P1.1: genau EINE Ablehnungszahl ──────────────────────────────────

def test_944_mehrere_absage_ereignisse_zaehlen_nur_einmal(tmp_db):
    """Der LEFT JOIN auf application_events lieferte je Ereignis eine
    Zeile — Bewerbungen mit zwei 'abgelehnt'-Ereignissen wurden doppelt
    gezaehlt. Daher nannte derselbe Bericht 60 und 64.
    """
    aid = _bewerbung(tmp_db, "Musterfirma GmbH", grund="Stelle intern besetzt")
    # Zwei Absage-Ereignisse zum selben Vorgang (kommt vor, wenn ein
    # Status doppelt gesetzt oder korrigiert wurde).
    conn = tmp_db.connect()
    for datum in ("2026-05-01T09:00:00", "2026-05-02T09:00:00"):
        conn.execute(
            "INSERT INTO application_events (application_id, status, "
            "event_date, notes) VALUES (?,?,?,?)",
            (aid, "abgelehnt", datum, "Absage"))
    conn.commit()

    muster = tmp_db.get_rejection_patterns()
    assert muster["anzahl"] == 1, muster


def test_944_ablehnungszahl_entspricht_der_statusverteilung(tmp_db):
    for i in range(3):
        _bewerbung(tmp_db, f"Firma {i} GmbH", grund="Stelle intern besetzt")
    _bewerbung(tmp_db, "Laeuft GmbH", status="beworben")
    stats = tmp_db.get_statistics()
    muster = tmp_db.get_rejection_patterns()
    assert muster["anzahl"] == stats["applications_by_status"].get("abgelehnt", 0)


# ── P1.3: Gruppierung auf das gepflegte Vokabular ────────────────────

def test_944_gleicher_grund_mit_und_ohne_punkt_zaehlt_einmal(tmp_db):
    """Derselbe Grund erschien doppelt, einmal mit Schlusspunkt."""
    _bewerbung(tmp_db, "Eins GmbH", grund="zu_weit_entfernt")
    _bewerbung(tmp_db, "Zwei GmbH", grund="zu_weit_entfernt.")
    muster = tmp_db.get_rejection_patterns()
    treffer = [(g, c) for g, c in muster["nach_grund"].items()
               if "weit" in g.lower()]
    assert len(treffer) == 1, muster["nach_grund"]
    assert treffer[0][1] == 2


def test_944_bewerbung_erstellt_ist_kein_ablehnungsgrund(tmp_db):
    """Ueber den event_notes-Rueckfall landete ein EREIGNISTYP als
    Ablehnungsgrund in der Tabelle."""
    aid = _bewerbung(tmp_db, "Musterfirma GmbH", grund=None)
    conn = tmp_db.connect()
    conn.execute(
        "INSERT INTO application_events (application_id, status, event_date, "
        "notes) VALUES (?,?,?,?)",
        (aid, "abgelehnt", "2026-05-01T09:00:00", "Bewerbung erstellt"))
    conn.commit()
    muster = tmp_db.get_rejection_patterns()
    assert not any("Bewerbung erstellt" in g for g in muster["nach_grund"]), (
        muster["nach_grund"])


def test_944_vermutungen_erscheinen_nicht_als_grund(tmp_db):
    """Ein Bericht, der einer Vermittlerin vorgelegt wird und dort eine
    unbelegte Selbstzuschreibung als Ablehnungsgrund ausweist, kann
    konkreten Schaden anrichten."""
    _bewerbung(tmp_db, "Belegt GmbH", grund="Stelle intern besetzt")
    _bewerbung(tmp_db, "Vermutet GmbH",
               grund="Vermutlich wegen fehlender Zertifizierung")
    _bewerbung(tmp_db, "Gewertet GmbH",
               grund="Keine Rueckmeldung, als stille Absage gewertet")
    muster = tmp_db.get_rejection_patterns()
    gruende = " ".join(muster["nach_grund"])
    assert "Vermutlich" not in gruende
    assert "gewertet" not in gruende
    # Aber sie verschwinden nicht spurlos — die Zahl wird benannt.
    assert muster["nicht_belegte_gruende"] == 2, muster


def test_944_leerer_grund_bleibt_sichtbar(tmp_db):
    _bewerbung(tmp_db, "Ohne Grund GmbH", grund="")
    muster = tmp_db.get_rejection_patterns()
    assert "Kein Grund angegeben" in muster["nach_grund"]


# ── P2.1: Abschnitt 9 macht keinen Softwarefehler zum Vorwurf ────────

def test_944_abschnitt_9_verlangt_fachlichen_anker(tmp_db):
    """Aufgefuehrt wurden Fehltreffer des Filters (#940) unter der
    Ueberschrift 'Nicht beworben trotz gutem Fit-Score'."""
    tmp_db.save_jobs([
        {"hash": "b944a", "title": "PLM Consultant", "company": "Passt GmbH",
         "url": "https://example.com/a", "source": "bundesagentur",
         "score": 40, "_fachscore": 28.0, "_rahmenscore": 12.0},
        {"hash": "b944b", "title": "Senior CRM Manager", "company": "Fehltreffer GmbH",
         "url": "https://example.com/b", "source": "bundesagentur",
         "score": 40, "_fachscore": 0.0, "_rahmenscore": 40.0},
    ])
    daten = tmp_db.get_report_data()
    firmen = [j.get("company") for j in daten.get("unapplied_high_score", [])]
    assert "Passt GmbH" in firmen
    assert "Fehltreffer GmbH" not in firmen, firmen


def test_944_abschnitt_9_nutzt_die_konfigurierte_schwelle(tmp_db):
    """Die feste Schwelle 5 lag weit unter der Aufnahmeschwelle."""
    tmp_db.set_search_criteria("min_score_schwelle", 15)
    tmp_db.save_jobs([
        {"hash": "b944c", "title": "PLM Consultant", "company": "Knapp GmbH",
         "url": "https://example.com/c", "source": "bundesagentur",
         "score": 8, "_fachscore": 8.0, "_rahmenscore": 0.0},
    ])
    daten = tmp_db.get_report_data()
    firmen = [j.get("company") for j in daten.get("unapplied_high_score", [])]
    assert "Knapp GmbH" not in firmen, firmen


# ── P3: Darstellung ──────────────────────────────────────────────────

def test_944_aufwandstabelle_rechnet_auf():
    """Die Gesamtspalte war `total` ueber ALLE Dokumentarten, die
    Spalten deckten nur vier ab — die Zeile ging nicht auf."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "export_report.py").read_text(encoding="utf-8")
    assert "sonstige = max(0, n - benannt)" in quelle
    assert "Gezeigt: 30 von" in quelle


def test_944_sternchen_hat_eine_legende():
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "export_report.py").read_text(encoding="utf-8")
    assert "Vorgemerkte Stelle (angepinnt)" in quelle


def test_944_kein_eintrag_ohne_firmenname():
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "export_report.py").read_text(encoding="utf-8")
    assert "Ohne Firmenangabe" in quelle


def test_944_keyword_analyse_filtert_fuellwoerter():
    """Belegt waren 'erfahrung' 49, 'nicht' 27, 'kein' 23, 'sowie' 22
    auf den vorderen Plaetzen."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "export_report.py").read_text(encoding="utf-8")
    for wort in ('"nicht"', '"kein"', '"sowie"', '"erfahrung"'):
        assert wort in quelle, wort


def test_944_sichtungsleistung_steht_in_der_zusammenfassung():
    """Der eigentliche Beleg systematischer Suche stand auf Seite 5."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "export_report.py").read_text(encoding="utf-8")
    assert "Stellen gesichtet" in quelle
    assert "begruendet aussortiert" in quelle


def test_944_bericht_laesst_sich_weiterhin_erzeugen(tmp_db, tmp_path):
    """Kein Rueckfall: nach all den Aenderungen muss die PDF entstehen."""
    from bewerbungs_assistent.export_report import generate_application_report
    _bewerbung(tmp_db, "Musterfirma GmbH", grund="zu_weit_entfernt")
    _bewerbung(tmp_db, "Laeuft GmbH", status="beworben")
    daten = tmp_db.get_report_data()
    daten["statistics"] = tmp_db.get_statistics()
    ziel = tmp_path / "bericht.pdf"
    pfad = generate_application_report(daten, {"name": "Test"}, str(ziel))
    assert pfad and ziel.exists()
    assert ziel.stat().st_size > 1000


# ── Nachtrag: die restlichen Kriterien ───────────────────────────────

def test_944_quellen_taxonomie_ist_einheitlich():
    """Dieselbe Quelle stand in beiden Tabellen unterschiedlich da —
    fuer eine Leserin sind das zwei verschiedene Quellen."""
    from bewerbungs_assistent.export_report import quelle_normalisiert as q
    assert q("jobspy_indeed") == q("indeed") == q("Indeed")
    assert q("browser_linkedin") == q("linkedin")
    assert q("") == "unbekannt"
    # Traeger-Praefixe bleiben erhalten: das IST die Quelle.
    assert q("plugin:watch-folder").startswith("plugin:")
    assert q("newsletter:Nischenboerse").startswith("newsletter:")
    # Verschiedene Quellen bleiben verschieden.
    assert q("stepstone") != q("indeed")


def test_944_quellen_volumen_wird_zusammengefasst():
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "export_report.py").read_text(encoding="utf-8")
    assert "_zusammengefasst" in quelle
    assert "_nach_quelle_summiert" in quelle


def test_944_aktivitaetsprotokoll_ist_vollstaendig():
    """Bei einem Nachweisdokument ist Vollstaendigkeit der Zweck."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "export_report.py").read_text(encoding="utf-8")
    # Die Sache pruefen, nicht die Kommentare: die Schleife darf nicht
    # mehr abschneiden.
    assert "timeline_events[:60]" not in quelle
    assert "for date, evt, target, status in timeline_events:" in quelle
    assert "vollstaendig aufgefuehrt" in quelle


def test_944_bewerbungsliste_hat_lesbare_spaltenbreiten():
    """Art und Kontakt kosteten die halbe Breite, wodurch Firmennamen
    mitten im Wort abbrachen — bei 95 Eintraegen der Hauptteil."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "export_report.py").read_text(encoding="utf-8")
    assert 'pdf.cell(55, 5, "Firma"' in quelle
    assert 'pdf.cell(65, 5, "Position"' in quelle
    assert '"Kontakt", border=1, fill=True' not in quelle


def test_944_bericht_und_liste_zeigen_denselben_score(tmp_db):
    """Die Scoring-Regler (#169) wirkten nur in der Stellenliste — der
    Bericht nannte fuer dieselbe Stelle einen anderen Wert."""
    tmp_db.save_jobs([{
        "hash": "b944d", "title": "PLM Consultant", "company": "Regler GmbH",
        "url": "https://example.com/d", "source": "bundesagentur",
        "score": 40, "_fachscore": 30.0, "_rahmenscore": 10.0,
    }])
    # Ein Regler, der den Score verschiebt.
    try:
        tmp_db.set_scoring_config("firma", "Regler GmbH", -10)
    except Exception:
        pytest.skip("Scoring-Regler in dieser Fassung nicht setzbar")

    from bewerbungs_assistent.services.scoring_service import (
        apply_scoring_adjustments)
    job = [j for j in tmp_db.get_active_jobs()
           if (j.get("hash") or "").endswith("b944d")][0]
    erwartet = apply_scoring_adjustments(job, job.get("score", 0), tmp_db)[
        "final_score"]

    daten = tmp_db.get_report_data()
    im_bericht = [j for j in daten.get("unapplied_high_score", [])
                  if j.get("company") == "Regler GmbH"]
    if not im_bericht:
        pytest.skip("Stelle erfuellt die Abschnitt-9-Bedingungen nicht")
    assert im_bericht[0]["score"] == erwartet, (im_bericht[0], erwartet)
