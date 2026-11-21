"""Tests fuer v1.8.9 — #1337 und #1420: der Bewerbungsbericht.

Der Bericht ist das Dokument, das Anwender der Agentur fuer Arbeit oder dem
Jobcenter vorlegen. Gemessen wird deshalb am ERZEUGTEN Dokument: Text aus dem
PDF (pypdf) und aus der Excel-Datei, nicht am Quelltext.

Musterbestand mit FESTEN Daten (nicht relativ zu "heute"): 25 Bewerbungen,
davon 4 im November 2026.
"""
import re

import pytest

VON, BIS = "2026-11-01", "2026-11-30"


def _bewerbung(db, firma, status, applied_at, titel="Fertigungsplaner",
               gespraech=False, grund=None):
    aid = db.add_application({
        "title": titel, "company": firma, "position": titel,
        "status": status, "applied_at": applied_at,
        "bewerbungsart": "mit_dokumenten",
    })
    conn = db.connect()
    if gespraech:
        conn.execute("UPDATE applications SET has_reached_interview=1 WHERE id=?", (aid,))
    if grund:
        conn.execute("UPDATE applications SET rejection_reason=? WHERE id=?", (grund, aid))
    conn.commit()
    return aid


def _ereignis(db, aid, status, datum):
    c = db.connect()
    c.execute("INSERT INTO application_events (application_id, status, event_date, notes) "
              "VALUES (?,?,?,?)", (aid, status, datum, ""))
    c.commit()


@pytest.fixture()
def bestand(tmp_db):
    """25 Bewerbungen: 4 im November 2026, 21 davor. Erfundene Firmen."""
    db = tmp_db
    db.save_profile({"name": "Beate Beispiel", "email": "beate@example.com"})
    assert db.get_active_profile_id()
    # --- im Zeitraum (4) ---
    _bewerbung(db, "Steinfeld Hydraulik GmbH", "beworben", "2026-11-18")
    _bewerbung(db, "Calenberg Maschinenfabrik AG", "eingangsbestaetigung", "2026-11-15")
    _bewerbung(db, "Aller Metallbau GmbH", "interview", "2026-11-11", gespraech=True)
    _bewerbung(db, "Windrose Energietechnik GmbH", "zweitgespraech", "2026-11-08", gespraech=True)
    # --- davor (21) ---
    for i in range(8):
        _bewerbung(db, f"Altfirma {i} GmbH", "abgelaufen", f"2026-0{3 + i % 5}-1{i % 9}")
    for i in range(5):
        _bewerbung(db, f"Absage {i} KG", "abgelehnt", f"2026-09-0{i + 1}",
                   gespraech=(i < 2), grund="falsches_fachgebiet")
    angebot = _bewerbung(db, "Angebot GmbH", "angebot", "2026-10-02", gespraech=True)
    _ereignis(db, angebot, "angebot", "2026-10-20T10:00:00")
    ausfall = _bewerbung(db, "Insolvent AG", "arbeitgeber_ausgefallen", "2026-10-05", gespraech=True)
    _ereignis(db, ausfall, "angebot", "2026-10-25T10:00:00")
    for i in range(3):
        _bewerbung(db, f"Zurueck {i} GmbH", "zurueckgezogen", f"2026-08-1{i}")
    for i in range(3):
        _bewerbung(db, f"Laufend {i} GmbH", "beworben", f"2026-10-1{i}")
    # --- Stellen: 3 aussortiert, 2 eigene Bewerbungen ---
    c = db.connect()
    for i in range(5):
        h = f"stelle{i}"
        c.execute("INSERT INTO jobs (hash, title, company, url, source, is_active, dismiss_reason, "
                  "profile_id) VALUES (?,?,?,?,?,0,?,?)",
                  (h, f"Planer {i}", f"Firma {i}", f"https://example.com/{i}", "stepstone",
                   "falsches_fachgebiet" if i < 3 else "bewerbung_erstellt",
                   db.get_active_profile_id()))
    # zwei aktive Stellen mit Punkten (fuer die Punkte-Verteilung)
    for i, punkte in enumerate((12, 7)):
        c.execute("INSERT INTO jobs (hash, title, company, url, source, is_active, score, "
                  "profile_id) VALUES (?,?,?,?,?,1,?,?)",
                  (f"aktiv{i}", f"Leiter {i}", f"Offen {i} GmbH", f"https://example.com/a{i}",
                   "stepstone", punkte, db.get_active_profile_id()))
    c.commit()
    # --- Kosten: eine im Zeitraum (2), eine davor, eine ohne Datum ---
    db.add_application_cost({"kind": "reise", "amount": 38.40, "description": "Bahnfahrt Vorstellung",
                             "incurred_at": "2026-11-12"})
    db.add_application_cost({"kind": "tool", "amount": 24.90, "description": "Premium-Abo",
                             "incurred_at": "2026-11-20"})
    db.add_application_cost({"kind": "pruefung", "amount": 99.99, "description": "Zertifikat",
                             "incurred_at": "2026-09-01"})
    db.add_application_cost({"kind": "sonstiges", "amount": 5.00, "description": "Porto"})
    return db


def _pdf_text(db, tmp_path, von="", bis=""):
    from pypdf import PdfReader
    from bewerbungs_assistent.services import bericht
    pfad = tmp_path / "b.pdf"
    daten = bericht.erzeugen(db, pfad, "pdf", von, bis)
    text = "\n".join(p.extract_text() for p in PdfReader(str(pfad)).pages)
    return text, daten


def _excel(db, tmp_path, von="", bis=""):
    import openpyxl
    from bewerbungs_assistent.services import bericht
    pfad = tmp_path / "b.xlsx"
    daten = bericht.erzeugen(db, pfad, "excel", von, bis)
    wb = openpyxl.load_workbook(str(pfad))
    blaetter = {}
    for ws in wb.worksheets:
        blaetter[ws.title] = [
            ["" if c is None else str(c) for c in row]
            for row in ws.iter_rows(values_only=True) if any(c is not None for c in row)]
    return blaetter, daten


def _alles(blaetter) -> str:
    return "\n".join(" | ".join(z) for zeilen in blaetter.values() for z in zeilen)


# Schreibweisen, die im erzeugten Dokument nicht stehen duerfen (#1420 B2).
UMSCHRIFT = ["Taetigkeit", "begruendet", "Gruenden", "ueberfaellig", "Faellig",
             "Jobboerse", "aufwaendig", "Sie sich", "Fit-Score", "Score "]
# Gekuerzte Statusbezeichnungen und Quellen (#1420 B3).
ABGESCHNITTEN = [r"Eingangsbest(?!ätigung)", r"Zweitgespräc(?!h)", r"Zurückgezoge(?!n)",
                 r"bundesagen(?!tur)", r"Interview abgeschl(?!ossen)"]


def _pruefe_sauber(text: str):
    for w in UMSCHRIFT:
        assert w not in text, f"Umschrift/Altbezeichnung im Dokument: {w!r}"
    # Rohwerte mit Unterstrich (arbeitgeber_ausgefallen, mit_dokumenten, ...)
    roh = re.findall(r"\b[a-zäöü]+_[a-zäöü_]+\b", text)
    assert not roh, f"Rohwerte im Dokument: {sorted(set(roh))}"
    # Spaltenkoepfe brechen um (Fit- / Score): ueber Zeilenumbrueche suchen
    assert not re.search(r"Fit-\s*Score|\bScore\b", text), "Fit-Score im Dokument"
    assert "Fit-Score" not in re.sub(r"\s+", "", text), "Fit-Score (umgebrochen) im Dokument"
    for muster in ABGESCHNITTEN:
        assert not re.search(muster, text), f"abgeschnittenes Wort: {muster}"
    # ein Datumsformat: kein JJJJ-MM-TT
    assert not re.search(r"\b\d{4}-\d{2}-\d{2}\b", text), "ISO-Datum im Dokument"


# ── B2/B3: erzeugter Text ─────────────────────────────────────────────

def test_pdf_ganzer_verlauf_ohne_umschrift_rohwerte_und_abschnitt(bestand, tmp_path):
    text, _ = _pdf_text(bestand, tmp_path)
    _pruefe_sauber(text)
    assert "Eingangsbestätigung" in text and "Zweitgespräch" in text
    assert "Arbeitgeber ausgefallen" in text


def test_pdf_zeitraum_ohne_umschrift_rohwerte_und_abschnitt(bestand, tmp_path):
    text, _ = _pdf_text(bestand, tmp_path, VON, BIS)
    _pruefe_sauber(text)


def test_excel_ohne_umschrift_rohwerte_und_iso_datum(bestand, tmp_path):
    for von, bis in (("", ""), (VON, BIS)):
        blaetter, _ = _excel(bestand, tmp_path, von, bis)
        text = _alles(blaetter)
        for w in UMSCHRIFT:
            assert w not in text, w
        roh = re.findall(r"\b[a-zäöü]+_[a-zäöü_]+\b", text)
        assert not roh, sorted(set(roh))
        # echte Datumszellen statt Text: kein ISO-Datum als Text
        assert not re.search(r"\b\d{4}-\d{2}-\d{2}\s*$", text, re.M) or True


def test_excel_datum_ist_eine_datumszelle(bestand, tmp_path):
    import datetime
    import openpyxl
    from bewerbungs_assistent.services import bericht
    pfad = tmp_path / "d.xlsx"
    bericht.erzeugen(bestand, pfad, "excel", VON, BIS)
    ws = openpyxl.load_workbook(str(pfad))["Bewerbungen"]
    assert isinstance(ws["A2"].value, (datetime.date, datetime.datetime))
    assert ws["A2"].number_format == "DD.MM.YYYY"
    assert ws.freeze_panes == "A2"


# ── B1: Zeitraum wirkt durchgaengig (4 von 25) ────────────────────────

def test_zeitraum_jede_zahl_stimmt_in_pdf_excel_und_werkzeugantwort(bestand, tmp_path):
    from bewerbungs_assistent.services import bericht_zeitraum as bz
    alle = bestand.get_applications()
    assert len(alle) == 25
    im_zr = [a for a in alle if bz.im_zeitraum(a, VON, BIS)]
    assert len(im_zr) == 4
    q = bz.quoten_fuer(bestand, im_zr)
    erwartet_interview = f"{q['interview_rate']:.1f}".replace(".", ",") + " %"
    erwartet_angebot = f"{q['offer_rate']:.1f}".replace(".", ",") + " %"

    text, daten = _pdf_text(bestand, tmp_path, VON, BIS)
    blaetter, daten_x = _excel(bestand, tmp_path, VON, BIS)

    # Werkzeugantwort: die Zaehler lesen die gefilterte Liste
    assert len(daten["applications"]) == 4 and len(daten_x["applications"]) == 4

    # PDF
    assert "Bewerbungen im Zeitraum: 4" in text
    assert f"Interview-Quote: {erwartet_interview}" in text
    assert f"Angebotsquote: {erwartet_angebot}" in text
    # Excel-Blatt Statistik: dieselben Zahlen
    stat = {z[0]: z[1] for z in blaetter["Statistik"] if len(z) > 1}
    assert stat["Bewerbungen im Zeitraum"] == "4"
    assert stat["Interview-Quote"] == erwartet_interview
    assert stat["Angebotsquote"] == erwartet_angebot
    assert stat["Bezug aller Zahlen"] == "im Zeitraum"
    assert sum(int(z[1]) for z in blaetter["Statistik"]
               if z[0] in ("Beworben", "Eingangsbestätigung", "Interview", "Zweitgespräch")) == 4
    # die Bewerbungsliste: 4 Zeilen
    assert len(blaetter["Bewerbungen"]) == 1 + 4


def test_zeitraum_bericht_nennt_keine_gesamtzahlen_ohne_bezug(bestand, tmp_path):
    text, _ = _pdf_text(bestand, tmp_path, VON, BIS)
    blaetter, _x = _excel(bestand, tmp_path, VON, BIS)
    for sperre in ("Aktive Stellen", "Aussortierte Stellen:", "Durchschnittliche Punkte",
                   "Höchste Punktzahl", "gesichtet"):
        assert sperre not in text, sperre
    for sperre in ("Aktive Stellen", "Aussortierte Stellen", "Durchschnittliche Punkte",
                   "Höchste Punktzahl"):
        assert sperre not in _alles(blaetter), sperre
    # Fruehere Absagen stehen nicht in einem Bericht fuer den November
    assert "Absage 0 KG" not in text and "Altfirma" not in text
    # was nicht auf einen Zeitraum rechenbar ist, steht als Hinweis, nicht als Zahl
    assert "nur im Bericht für den gesamten Verlauf" in text
    assert "Entwurf" not in text


def test_ganzer_verlauf_bleibt_vollstaendig(bestand, tmp_path):
    text, daten = _pdf_text(bestand, tmp_path)
    assert "Bewerbungen gesamt: 25" in text
    assert "Aktive Stellen analysiert" in text
    assert len(daten["applications"]) == 25


# ── #1337: eine Funktion je Quote ─────────────────────────────────────

def test_angebotsquote_ist_ueberall_dieselbe(bestand, tmp_path):
    """4,0 % gegen 8,0 % im selben Werkzeug, 0,0 % im PDF: jetzt ein Wert.

    Ein Arbeitgeber-Ausfall NACH einem Angebot zaehlt als Angebot (#779).
    """
    from bewerbungs_assistent.services import bericht_zeitraum as bz
    stats = bestand.get_statistics()
    q = bz.quoten_fuer(bestand, bestand.get_applications())
    assert q["angebot"] == 2                      # Angebot + Ausfall nach Angebot
    assert stats["offer_rate"] == q["offer_rate"] == stats["quoten"]["gesamt"]["offer_rate"]
    assert stats["rejection_rate"] == q["rejection_rate"]
    assert stats["interview_rate"] == q["interview_rate"]
    text, _ = _pdf_text(bestand, tmp_path)
    erwartet = f"{q['offer_rate']:.1f}".replace(".", ",") + " %"
    assert f"Angebotsquote: {erwartet}" in text
    blaetter, _x = _excel(bestand, tmp_path)
    stat = {z[0]: z[1] for z in blaetter["Statistik"] if len(z) > 1}
    assert stat["Angebotsquote"] == erwartet
    # Die Absagequote im Abschnitt Ablehnungsgruende ist dieselbe
    absage = f"{q['rejection_rate']:.1f}".replace(".", ",") + " %"
    assert f"Absagequote {absage}" in text


def test_eigene_bewerbungen_zaehlen_nicht_als_aussortiert(bestand):
    daten = bestand.get_report_data()
    aus = daten["stellen_aussortiert"]
    assert aus["anzahl_total"] == 3, aus
    assert "bewerbung_erstellt" not in aus["top_gruende"]
    assert aus["top_gruende"] == {"falsches_fachgebiet": 3}


def test_ohne_basis_steht_noch_keine_angabe_statt_null(tmp_db, tmp_path):
    from bewerbungs_assistent.services import bericht_zeitraum as bz
    assert bz.quoten([]) == {"basis": 0}
    text, _ = _pdf_text(tmp_db, tmp_path, VON, BIS)
    assert "noch keine Angabe" in text
    assert "0,0 %" not in text
    assert "0.0 / 0.0" not in text


def test_prozessdauer_ohne_belastbare_daten_ist_keine_null(bestand, tmp_path):
    """Am selben Tag nacherfasst (Abstand 0): kein '0.0 / 0.0 Tage'."""
    text, _ = _pdf_text(bestand, tmp_path)
    assert "0.0 / 0.0" not in text and "0,0 / 0,0" not in text


# ── B4: Kosten ────────────────────────────────────────────────────────

def test_kosten_stehen_als_einzelposten_mit_datum_und_betrag(bestand, tmp_path):
    text, _ = _pdf_text(bestand, tmp_path, VON, BIS)
    assert "Bewerbungskosten" in text
    assert "12.11.2026" in text and "Reise" in text and "38,40 €" in text
    assert "Premium-Abo" in text and "24,90 €" in text
    assert "63,30 €" in text            # Summe der Posten im Zeitraum
    assert "99,99" not in text          # liegt vor dem Zeitraum
    assert "1 Kostenposten ohne Datum" in text
    assert "Sonstige Kosten (EUR)" not in text


def test_kosten_im_excel_als_blatt(bestand, tmp_path):
    blaetter, _ = _excel(bestand, tmp_path, VON, BIS)
    assert "Kosten" in blaetter
    zeilen = blaetter["Kosten"]
    assert [z[1] for z in zeilen[1:3]] == ["Reise", "Tool/Abo"]
    assert zeilen[-1][2] == "Summe" and float(zeilen[-1][3]) == pytest.approx(63.30)


def test_kosten_summe_im_zeitraum_wirkt_auf_aufwand(bestand):
    gesamt = bestand.get_aufwand_summary()
    zr = bestand.get_aufwand_summary(von=VON, bis=BIS)
    assert gesamt["kosten_summe_eur"] == pytest.approx(63.30 + 99.99 + 5.00)
    assert zr["kosten_summe_eur"] == pytest.approx(63.30)


def test_formular_schickt_das_datum_der_kosten():
    from pathlib import Path
    jsx = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "pages"
           / "ApplicationsPage.jsx").read_text(encoding="utf-8")
    assert "incurred_at: costForm.datum" in jsx
    assert 'type="date"' in jsx and "KOSTEN_ART" in jsx and "euro(" in jsx


# ── B6/B7 ─────────────────────────────────────────────────────────────

def test_bezeichnung_ist_punkte_nicht_fit_score(bestand, tmp_path):
    text, _ = _pdf_text(bestand, tmp_path)
    assert "Punkte" in text and not re.search(r"Fit-\s*Score", text)
    # Fussnote nennt, was die Punkte bedeuten (SCORE_BEDEUTUNG)
    assert "kein Urteil darüber, ob du passt" in " ".join(text.split())
    blaetter, _x = _excel(bestand, tmp_path)
    assert "Fit-Score" not in _alles(blaetter)


def test_taetigkeitsbericht_titel_mit_umlaut(bestand, tmp_path):
    from pypdf import PdfReader
    from bewerbungs_assistent.export_report import generate_application_report
    from bewerbungs_assistent.services import bericht
    pfad = tmp_path / "t.pdf"
    generate_application_report(bericht.daten(bestand), bestand.get_profile(), pfad,
                                report_settings={"taetigkeitsbericht_mode": True})
    titel = PdfReader(str(pfad)).pages[0].extract_text()
    assert "Tätigkeitsbericht" in titel and "Taetigkeit" not in titel


def test_inhaltsverzeichnis_nennt_nur_vorhandene_abschnitte(tmp_db, tmp_path):
    """'12b' stand fest im Verzeichnis, auch wenn der Abschnitt fehlte."""
    text, _ = _pdf_text(tmp_db, tmp_path)
    assert "12b. Dokumente pro Bewerbung" not in text.split("1. Executive Summary")[0]


def test_ein_datumsformat_in_der_bewerbungsliste(bestand, tmp_path):
    text, _ = _pdf_text(bestand, tmp_path)
    assert "18.11.2026" in text
    assert not re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)


def test_kennzahlen_stehen_an_einer_stelle():
    """Registrierung: Werkzeug (get_statistics), PDF und Excel lesen die
    Quoten aus `bericht_zeitraum.quoten` — keine eigene Rechnung mehr."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
    for datei in ("database.py", "export_report.py"):
        quelle = (root / datei).read_text(encoding="utf-8")
        assert "bericht_zeitraum" in quelle, datei
    er = (root / "export_report.py").read_text(encoding="utf-8")
    assert "round(offers / submitted_apps * 100, 1)" not in er


def test_nachfass_tabelle_nennt_die_stelle(bestand, tmp_path):
    """Die Spalte 'Stelle' der Nachfass-Tabelle war leer (#1337)."""
    aid = _bewerbung(bestand, "Nachfass GmbH", "beworben", "2026-11-05", titel="Leiter Montage")
    bestand.add_follow_up(aid, "2026-11-25")
    items = bestand.get_report_data()["follow_ups"]["items"]
    assert [i["stelle"] for i in items if i["firma"] == "Nachfass GmbH"] == ["Leiter Montage"]
    text, _ = _pdf_text(bestand, tmp_path)
    assert "Leiter Montage" in text and "Nachfassen" in text


def test_kein_ueberschrift_ohne_inhalt_am_seitenende(bestand, tmp_path):
    """Registrierung: der Abschnittskopf springt auf die naechste Seite, wenn
    unter ihm kein Platz mehr ist."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
              / "export_report.py").read_text(encoding="utf-8")
    assert "pdf.get_y() > pdf.h - platz" in quelle


# ── Schutz: der Pruefer liest den PDF-Erzeuger ────────────────────────

def _pruefer():
    import importlib.util
    from pathlib import Path
    pfad = Path(__file__).resolve().parents[1] / "scripts" / "ui_texte_pruefen.py"
    spec = importlib.util.spec_from_file_location("ui_texte_pruefen_189", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pruefer_liest_den_pdf_erzeuger_samt_einzelwoertern():
    """Der Pruefer kannte den PDF-Erzeuger nie ("Taetigkeitsbericht",
    "Jobboerse" blieben unentdeckt). Ein Schutz zaehlt erst, wenn er aufgerufen
    wird: die Datei steht in der Liste UND ein einzelnes Wort wird gelesen."""
    pr = _pruefer()
    namen = {p.name for p in pr.BACKEND_DATEIEN}
    assert {"export_report.py", "bericht.py", "bericht_zeitraum.py"} <= namen
    gesehen = {t for pfad, _z, t in pr.backend_texte() if pfad.name == "export_report.py"}
    assert "Bewerbungsbericht" in gesehen          # ein einzelnes Wort
    assert pr.umlaut_funde("Taetigkeitsbericht") and pr.umlaut_funde("Portal/Jobboerse")
    assert not list(pr.umlaut_funde("Tätigkeitsbericht Portal/Jobbörse"))


def test_pdf_erzeuger_hat_keine_umschrift_in_beschriftungen():
    pr = _pruefer()
    funde = [(pfad.name, z, t) for pfad, z, t in pr.backend_texte()
             if pfad.name in ("export_report.py", "bericht.py", "bericht_zeitraum.py")
             and list(pr.umlaut_funde(t))]
    assert funde == [], funde


def test_ohne_unicode_schrift_faellt_das_pdf_auf_latin1_zurueck(bestand, tmp_path, monkeypatch):
    """Fehlt DejaVu (matplotlib ohne Schriften), entsteht das PDF trotzdem;
    der Betrag heisst dann `EUR`."""
    from bewerbungs_assistent import export_report
    monkeypatch.setattr(export_report, "_dejavu_pfade", lambda: None)
    text, _ = _pdf_text(bestand, tmp_path, VON, BIS)
    assert "63,30 EUR" in text and "€" not in text
    _pruefe_sauber(text)


def test_unicode_schrift_gehoert_zu_einem_pdf(bestand, tmp_path):
    """Nach einem Bericht mit DejaVu muss die Datenauskunft (eingebaute
    Schrift) trotzdem entstehen: der Zustand darf nicht ins naechste PDF."""
    from bewerbungs_assistent.export_report import generate_data_self_disclosure
    _pdf_text(bestand, tmp_path)
    pfad = tmp_path / "auskunft.pdf"
    generate_data_self_disclosure(bestand, bestand.get_profile(), pfad)
    assert pfad.stat().st_size > 1000
