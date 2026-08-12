# -*- coding: utf-8 -*-
"""Musterprofile Bob und Anna — reproduzierbares Seed-Modul (Baustelle 7, #840).

Zwei tief ausgebaute, klar FIKTIVE Berufsleben fuer Demo-Daten und
Screenshots. Alle Firmen, Personen, Adressen und Kontaktdaten sind frei
erfunden; die fiktiven Firmennamen sind in scripts/scrub_pii.py
(FIKTIVE_FIRMEN) als Platzhalter registriert.

- Bob Mustermann:  Metall/Fertigung — Zerspaner -> Industriemeister ->
  Produktionsplaner. Brueche: Studienabbruch, Arbeitgeber-Insolvenz,
  14 Monate Arbeitslosigkeit mit Weiterbildung, 5-Monats-Station
  (Probezeit), Auslandsstation Oesterreich.
- Anna Beispiel:   Hotellerie -> Office Management -> HR-Quereinstieg.
  Brueche: Branchenwechsel, Elternzeit + Teilzeit-Wiedereinstieg,
  Freelance-Phase mit vier Kunden, Wintersaison Schweiz, befristeter
  Vertrag.

Verwendung (NUR gegen eine isolierte Temp-DB — nie gegen die echte
User-DB, siehe QA-Isolations-Regel in CLAUDE.md):

    from musterprofile import seed_bob, seed_anna
    pid_anna = seed_anna(db)
    pid_bob = seed_bob(db)      # aktiviert Bob als letztes Profil

Jede Funktion legt ein EIGENES Profil an (db.create_profile aktiviert es)
und befuellt: Stationen, STAR-Projekte, Ausbildung, Skills, Suchkriterien,
Stellen (inkl. aussortierter), Bewerbungen mit Verlauf und Ausgaengen,
Follow-ups, Termine, Kontakte, Dokumente, Aufgaben und
Interview-Reflexionen.
"""

from datetime import datetime, timedelta
import hashlib


# ---------------------------------------------------------------------------
# Sicherheitsnetz: dieses Modul darf nie auf der echten User-DB laufen.
# ---------------------------------------------------------------------------

def assert_isolated(db):
    """Wirft AssertionError, wenn die DB wie eine echte User-DB aussieht."""
    path = str(getattr(db, "db_path", "")).lower()
    verboten = ("appdata", ".bewerbungs-assistent")
    assert path and not any(v in path for v in verboten), (
        f"Musterprofil-Seed verweigert: DB-Pfad sieht nach echter User-DB aus: {path}"
    )


def _tag(offset_days, hour=None):
    """ISO-Datum (oder Timestamp) relativ zu heute; positive Werte = Vergangenheit."""
    d = datetime.now() - timedelta(days=offset_days)
    if hour is None:
        return d.date().isoformat()
    return d.replace(hour=hour, minute=0, second=0, microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )


def _job_hash(url):
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _apply_flow(db, app_id, flow):
    """Wendet eine Status-Kette [(status, notes, rejection_reason), ...] an."""
    for schritt in flow:
        status, notes = schritt[0], schritt[1]
        grund = schritt[2] if len(schritt) > 2 else ""
        db.update_application_status(app_id, status, notes, rejection_reason=grund)


def _dokumente(db, eintraege):
    for fname, dtype, text in eintraege:
        did = db.add_document({
            "filename": fname,
            "filepath": f"/demo/{fname}",
            "doc_type": dtype,
            "extracted_text": text,
        })
        # extraction_status wird von add_document nicht gelesen — separat setzen.
        db.update_document_extraction_status(did, "analysiert")


# ===========================================================================
# BOB MUSTERMANN — Metall & Fertigung, Raum Hannover
# ===========================================================================

def seed_bob(db):
    assert_isolated(db)
    pid = db.create_profile("Bob Mustermann", "bob.mustermann@example.com")
    db.ensure_system_categories()      # Kalender-Kategorien (profil-gebunden)
    db.list_contact_categories()       # legt Standard-Kontaktkategorien an
    now = datetime.now()

    db.save_profile({
        "name": "Bob Mustermann",
        "email": "bob.mustermann@example.com",
        "phone": "0511 5550123",
        "address": "Am Kirchfeld 12",
        "city": "Laatzen",
        "plz": "30880",
        "country": "Deutschland",
        "birthday": "1979-04-17",
        "summary": (
            "Industriemeister Metall mit über 25 Jahren in der Zerspanung — vom "
            "CNC-Dreher über Schichtführung bis zur Produktionsplanung. "
            "Stärken: Rüstzeitoptimierung, Shopfloor-Management, SAP PP und die "
            "Übersetzung zwischen Werkhalle und Planung. Sucht wegen "
            "Standortschließung eine neue Aufgabe in Fertigungssteuerung oder "
            "Produktionsleitung im Raum Hannover."
        ),
        "informal_notes": (
            "Seit 1998 in der Freiwilligen Feuerwehr, heute Gruppenführer und "
            "Gerätewart — führt im Einsatz zwölf Kameraden und verantwortet die "
            "Atemschutzgeräte. Restauriert alte Deutz-Traktoren: zwei D40 aus "
            "den Sechzigern komplett zerlegt und wieder aufgebaut, Teile werden "
            "europaweit beschafft. Imkert seit 2020 mit sechs Völkern, der "
            "Honig geht im Dorf weg wie nichts. Pragmatiker: lieber eine "
            "funktionierende 80-Prozent-Lösung heute als eine perfekte in "
            "einem halben Jahr."
        ),
        "preferences": {
            "stellentyp": "festanstellung",
            "arbeitsmodell": "vor_ort",
            "min_gehalt": 52000,
            "ziel_gehalt": 60000,
            "regionen": ["Hannover", "Braunschweig", "Hildesheim"],
            "schichtbereitschaft": True,
        },
    })

    # ── Stationen (8 Positionen; Luecken 2003-2004 Studium und 2015-2016
    #    Arbeitslosigkeit ergeben sich aus den Datumsbereichen) ──
    positionen = [
        {"company": "Weserstahl Maschinenbau GmbH", "title": "Auszubildender Zerspanungsmechaniker",
         "location": "Hameln", "start_date": "1996-08", "end_date": "2000-06",
         "industry": "Maschinenbau",
         "description": "Ausbildung mit Schwerpunkt Drehtechnik, Übernahme nach Abschluss."},
        {"company": "Weserstahl Maschinenbau GmbH", "title": "CNC-Dreher",
         "location": "Hameln", "start_date": "2000-07", "end_date": "2003-08",
         "industry": "Maschinenbau",
         "description": "Serien- und Einzelteilfertigung auf Sinumerik-Drehzentren, "
                        "Qualitätsprüfung mit Messmaschine."},
        # 2003-09 bis 2004-08: Maschinenbau-Studium, nach 2 Semestern abgebrochen
        # (siehe Ausbildung) — bewusste Luecke im Verlauf.
        {"company": "Leinetal Präzisionstechnik GmbH & Co. KG", "title": "CNC-Fräser / Programmierer",
         "location": "Hannover", "start_date": "2004-09", "end_date": "2009-03",
         "industry": "Zerspanungstechnik",
         "description": "5-Achs-Fräsen von Hydraulikkomponenten, CAM-Programmierung, "
                        "Einfahren neuer Teile.",
         "technologies": "Sinumerik 840D, Heidenhain iTNC, Mastercam"},
        {"company": "Leinetal Präzisionstechnik GmbH & Co. KG", "title": "Schichtführer Zerspanung",
         "location": "Hannover", "start_date": "2009-04", "end_date": "2012-09",
         "industry": "Zerspanungstechnik",
         "description": "Führung einer Schicht mit 14 Mitarbeitern, Feinplanung, "
                        "Unterweisungen, Eskalation bei Maschinenstillständen."},
        {"company": "Hansa Verfahrenstechnik AG", "title": "Fertigungsmeister",
         "location": "Hildesheim", "start_date": "2012-10", "end_date": "2015-06",
         "industry": "Anlagenbau",
         "description": "Meisterbereich mechanische Fertigung (26 Mitarbeiter, 3 Schichten). "
                        "Werk wurde 2015 im Zuge der Insolvenz geschlossen."},
        # 2015-07 bis 2016-08: arbeitssuchend, REFA-Grundschein + SAP-PP-Schulung.
        {"company": "Bergwind Getriebebau GmbH", "title": "Fertigungsplaner",
         "location": "Gehrden", "start_date": "2016-09", "end_date": "2017-01",
         "industry": "Antriebstechnik",
         "description": "Feinplanung Verzahnungsfertigung. Trennung in der Probezeit — "
                        "Erwartungen an Reisetätigkeit und Rolle passten nicht zusammen."},
        {"company": "Alpenland Anlagenmontage GmbH", "title": "Montage- und Inbetriebnahme-Techniker",
         "location": "Linz, Österreich", "start_date": "2017-03", "end_date": "2019-08",
         "industry": "Sondermaschinenbau",
         "description": "Mechanische Endmontage und Inbetriebnahme von Sondermaschinen "
                        "beim Kunden, Einsätze in sechs Ländern."},
        {"company": "Nordlicht Antriebstechnik GmbH", "title": "Produktionsplaner",
         "location": "Hannover", "start_date": "2019-09", "end_date": None, "is_current": 1,
         "industry": "Antriebstechnik",
         "description": "Kapazitäts- und Feinplanung für zwei Fertigungslinien, "
                        "SAP-PP-Key-User, Schnittstelle zu Einkauf und Vertrieb. "
                        "Standort schließt Ende 2026.",
         "technologies": "SAP PP, SAP MM, Excel, Power Query"},
    ]
    pos_ids = [db.add_position(p) for p in positionen]

    # ── 13 STAR-Projekte, verteilt ueber die Stationen ──
    projekte = [
        (2, {"name": "CNC-Programmbibliothek aufgebaut",
             "situation": "Programme lagen verstreut auf Maschinensteuerungen und USB-Sticks; bei Wiederholaufträgen wurde regelmäßig neu programmiert.",
             "task": "Zentrale, versionierte Ablage für rund 400 NC-Programme schaffen.",
             "action": "Ordnerstruktur je Kunde/Teilefamilie eingeführt, Programme mit Rüstblättern verknüpft, Kollegen eingewiesen.",
             "result": "Wiederholaufträge starten seitdem ohne Neuprogrammierung; Einfahrzeit je Auftrag um rund ein Drittel gesunken."}),
        (2, {"name": "Einfahrteile-Ausschuss gesenkt",
             "situation": "Beim Einfahren neuer Frästeile entstanden im Schnitt vier Ausschussteile je Serie.",
             "task": "Ausschussquote der Einfahrphase halbieren.",
             "action": "Simulation im CAM konsequent genutzt, Messpunkte ins Programm gelegt, Erstteilfreigabe mit der QS standardisiert.",
             "result": "Einfahr-Ausschuss auf durchschnittlich 1,6 Teile je Serie gesenkt, Materialkosten spürbar reduziert."}),
        (3, {"name": "SMED-Projekt Rüstzeitoptimierung",
             "situation": "Rüstzeiten an den Drehzentren lagen bei durchschnittlich 95 Minuten und fraßen Kapazität.",
             "task": "Rüstzeiten um mindestens 25 Prozent senken, ohne Neuinvestition.",
             "action": "Rüstvorgänge gefilmt und in interne/externe Anteile zerlegt, Werkzeugvoreinstellung eingeführt, Rüstwagen je Maschine gepackt.",
             "result": "Durchschnittliche Rüstzeit auf 61 Minuten gesenkt (minus 35 Prozent), Mehrkapazität von rund 900 Maschinenstunden pro Jahr."}),
        (3, {"name": "Schichtübergabe standardisiert",
             "situation": "Übergaben zwischen den Schichten liefen mündlich; Störungen und halbfertige Aufträge gingen verloren.",
             "task": "Verlustfreie Übergabe zwischen drei Schichten sicherstellen.",
             "action": "Einseitiges Übergabeprotokoll je Maschine eingeführt und mit den Schichtführern der anderen Schichten abgestimmt.",
             "result": "Rückfragen und Doppelarbeit deutlich reduziert; das Protokoll wurde später werksweit übernommen."}),
        (3, {"name": "Azubi-Patenmodell aufgebaut",
             "situation": "Auszubildende rotierten ohne feste Ansprechpartner durch die Zerspanung.",
             "task": "Ausbildungsqualität in der Abteilung heben.",
             "action": "Patenmodell mit erfahrenen Facharbeitern etabliert, Lernziele je Durchlauf definiert, Feedbackgespräche eingeführt.",
             "result": "Beide betreuten Jahrgänge bestanden die Praxisprüfung überdurchschnittlich; ein Azubi blieb als Facharbeiter im Team."}),
        (4, {"name": "5S in der mechanischen Fertigung",
             "situation": "Suchzeiten für Werkzeuge und Vorrichtungen bremsten den Meisterbereich aus.",
             "task": "5S in drei Hallenabschnitten einführen und am Leben halten.",
             "action": "Sortier-Aktionen mit den Teams durchgeführt, Schattenbretter und Bodenmarkierungen umgesetzt, wöchentliche Kurz-Audits etabliert.",
             "result": "Suchzeiten messbar gesenkt, Audit-Erfüllung nach sechs Monaten stabil über 90 Prozent."}),
        (4, {"name": "Shopfloor-Board eingeführt",
             "situation": "Kennzahlen des Meisterbereichs existierten nur in Excel beim Meister — die Mannschaft sah sie nie.",
             "task": "Tagesaktuelle Transparenz über Leistung, Qualität und Störungen schaffen.",
             "action": "Shopfloor-Board mit fünf Kennzahlen aufgebaut, tägliche 10-Minuten-Runde vor dem Board eingeführt.",
             "result": "Störungen wurden im Schnitt zwei Tage früher adressiert; die Runde lief auch nach der Pilotphase weiter."}),
        (4, {"name": "Umzug einer Fertigungslinie koordiniert",
             "situation": "Eine Drehlinie musste innerhalb des Werks umziehen, geplanter Stillstand: zwei Wochen.",
             "task": "Umzug so takten, dass Liefertermine gehalten werden.",
             "action": "Vorproduktion aufgebaut, Umzug in zwei Wellen geplant, Fremdfirmen und Instandhaltung eng getaktet.",
             "result": "Stillstand auf neun Arbeitstage verkürzt, kein einziger Liefertermin gerissen."}),
        (6, {"name": "Inbetriebnahmen in sechs Ländern",
             "situation": "Sondermaschinen wurden beim Kunden montiert und in Betrieb genommen — oft unter Zeitdruck und auf Englisch.",
             "task": "Mechanische Endmontage und Inbetriebnahme eigenverantwortlich abwickeln.",
             "action": "Einsätze in Österreich, Tschechien, Polen, Ungarn, Italien und der Schweiz gefahren; Abnahmen mit Kunden dokumentiert.",
             "result": "Elf Maschinen erfolgreich übergeben, Reklamationsquote der eigenen Einsätze: null."}),
        (6, {"name": "Wartungsplan digitalisiert",
             "situation": "Wartungsintervalle der Montagewerkzeuge wurden auf Papier geführt und regelmäßig verpasst.",
             "task": "Verlässliche Wartungserinnerung ohne teure Software.",
             "action": "Excel-basierte Wartungsliste mit Ampellogik und Erinnerungsdatum gebaut, Verantwortliche je Werkzeuggruppe benannt.",
             "result": "Kein verpasstes Intervall mehr im Folgejahr; Lösung wurde vom Serviceteam übernommen."}),
        (7, {"name": "SAP-PP-Feinplanung eingeführt",
             "situation": "Feinplanung lief in Excel neben SAP her, Rückmeldungen kamen doppelt und widersprüchlich.",
             "task": "Planung vollständig in SAP PP abbilden und die Excel-Nebenwelt abschalten.",
             "action": "Arbeitspläne und Kapazitätsgruppen bereinigt, Rückmeldeprozesse mit der Werkstatt neu geregelt, Key-User-Schulungen gehalten.",
             "result": "Plantreue von 71 auf 88 Prozent gestiegen; die Excel-Schattenplanung wurde abgeschaltet."}),
        (7, {"name": "Schichtmodell-Umstellung begleitet",
             "situation": "Auftragsspitzen erzwangen ein drittes Schichtmodell für eine Linie — mit Sorgen in der Belegschaft.",
             "task": "Umstellung planen und mit Betriebsrat und Mannschaft tragfähig machen.",
             "action": "Drei Modellvarianten durchgerechnet, Belegschaftsversammlungen mitgestaltet, Pilotphase mit Feedbackrunden aufgesetzt.",
             "result": "Modell nach Pilot mit großer Mehrheit angenommen; Lieferrückstand innerhalb eines Quartals abgebaut."}),
        (7, {"name": "Druckluft-Leckagen-Aktion",
             "situation": "Energiekosten der Halle stiegen; Druckluft stand im Verdacht, der stille Kostentreiber zu sein.",
             "task": "Leckagen finden und dauerhaft abstellen.",
             "action": "Leckage-Rundgänge mit Ultraschallgerät organisiert, Reparaturen priorisiert, Ergebnis am Shopfloor-Board sichtbar gemacht.",
             "result": "Druckluft-Energiekosten um 18 Prozent gesenkt; Rundgang läuft seitdem quartalsweise."}),
    ]
    for idx, projekt in projekte:
        db.add_project(pos_ids[idx], projekt)

    # ── Ausbildung (inkl. abgebrochenem Studium und Weiterbildung in der
    #    Arbeitslosigkeit) ──
    for edu in [
        {"institution": "Realschule Hameln-Süd", "degree": "Mittlere Reife",
         "field_of_study": "", "start_date": "1990", "end_date": "1996"},
        {"institution": "Weserstahl Maschinenbau GmbH / IHK Hannover",
         "degree": "Zerspanungsmechaniker (IHK)",
         "field_of_study": "Drehtechnik", "start_date": "1996", "end_date": "2000",
         "grade": "gut"},
        {"institution": "FH Hannover", "degree": "Studium Maschinenbau (abgebrochen)",
         "field_of_study": "Maschinenbau", "start_date": "2003", "end_date": "2004",
         "description": "Nach zwei Semestern abgebrochen — die Praxis hat gewonnen. "
                        "Grundlagen Mathematik und Konstruktion wurden abgeschlossen."},
        {"institution": "IHK Hannover", "degree": "Industriemeister Metall",
         "field_of_study": "Fertigung", "start_date": "2008", "end_date": "2010",
         "grade": "gut", "description": "Berufsbegleitend neben Vollzeitstelle."},
        {"institution": "IHK Hannover", "degree": "Ausbildereignung (AEVO)",
         "field_of_study": "", "start_date": "2011", "end_date": "2011"},
        {"institution": "REFA Nordwest", "degree": "REFA-Grundschein Arbeitsorganisation",
         "field_of_study": "Arbeitsstudium", "start_date": "2015", "end_date": "2016",
         "description": "Gefördert während der Arbeitslosigkeit nach der Insolvenz."},
        {"institution": "Bildungswerk Technik Hannover", "degree": "SAP-PP-Anwenderschulung",
         "field_of_study": "Produktionsplanung", "start_date": "2016", "end_date": "2016"},
    ]:
        db.add_education(edu)

    # ── ~46 Skills mit Niveau (1-5) und Zeitraeumen ──
    skills = [
        # (name, kategorie, level, start_year, end_year|None)
        ("CNC-Drehen", "fachlich", 5, 1996, None),
        ("CNC-Fräsen", "fachlich", 5, 2004, None),
        ("Sinumerik 840D", "tool", 5, 1998, None),
        ("Heidenhain iTNC", "tool", 4, 2004, 2016),
        ("Mastercam (CAM)", "tool", 3, 2005, 2016),
        ("Messtechnik / Erstteilfreigabe", "fachlich", 4, 1998, None),
        ("Zerspanungsparameter-Optimierung", "fachlich", 5, 2000, None),
        ("SMED / Rüstzeitoptimierung", "methodisch", 5, 2009, None),
        ("5S", "methodisch", 5, 2010, None),
        ("Lean Manufacturing", "methodisch", 4, 2010, None),
        ("REFA-Arbeitsorganisation", "methodisch", 4, 2015, None),
        ("Arbeitsvorbereitung", "fachlich", 5, 2016, None),
        ("Fertigungssteuerung", "fachlich", 5, 2016, None),
        ("Kapazitätsplanung", "fachlich", 4, 2019, None),
        ("SAP PP", "tool", 4, 2016, None),
        ("SAP MM", "tool", 3, 2019, None),
        ("MS Excel / Power Query", "tool", 4, 2012, None),
        ("Shopfloor-Management", "methodisch", 4, 2012, None),
        ("8D-Reklamationsbearbeitung", "methodisch", 3, 2012, None),
        ("ISO 9001 (Anwenderwissen)", "fachlich", 3, 2012, None),
        ("Arbeitssicherheit / Unterweisungen", "fachlich", 4, 2009, None),
        ("Ausbilderschein (AEVO)", "zertifizierung", 4, 2011, None),
        ("Schichtplanung", "fachlich", 4, 2009, None),
        ("Personalführung (bis 26 MA)", "fuehrung", 4, 2009, None),
        ("Konfliktmoderation", "soft_skill", 3, 2012, None),
        ("Instandhaltungskoordination", "fachlich", 3, 2012, None),
        ("Technisches Zeichnen lesen", "fachlich", 5, 1996, None),
        ("AutoCAD (Grundlagen)", "tool", 2, 2003, 2004),
        ("Hydraulik (Grundlagen)", "fachlich", 3, 2004, None),
        ("Pneumatik (Grundlagen)", "fachlich", 3, 2004, None),
        ("MAG-Schweißen", "fachlich", 3, 1998, 2012),
        ("Staplerschein", "zertifizierung", 4, 2001, None),
        ("Kranschein (Hallenkran)", "zertifizierung", 4, 2005, None),
        ("Inbetriebnahme Sondermaschinen", "fachlich", 4, 2017, 2019),
        ("Kundenabnahmen dokumentieren", "fachlich", 4, 2017, 2019),
        ("Projektkoordination", "methodisch", 4, 2012, None),
        ("Kostenstellenrechnung (Grundlagen)", "fachlich", 3, 2019, None),
        ("Reklamationsbearbeitung", "fachlich", 4, 2012, None),
        ("Lieferantenabstimmung", "soft_skill", 3, 2019, None),
        ("Berichtswesen / Kennzahlen", "fachlich", 4, 2012, None),
        ("Teamübergreifende Kommunikation", "soft_skill", 4, 2009, None),
        ("Atemschutzgeräteträger", "zertifizierung", 4, 1999, None),
        ("Gruppenführer Feuerwehr", "fuehrung", 4, 2010, None),
        ("Deutsch (Muttersprache)", "sprache", 5, None, None),
        ("Englisch (B1)", "sprache", 3, None, None),
        ("Tschechisch (Grundkenntnisse)", "sprache", 1, 2017, 2019),
    ]
    for name, cat, level, sy, ey in skills:
        db.add_skill({
            "name": name, "category": cat, "level": level,
            "start_year": sy, "end_year": ey,
        })

    # ── Suchkriterien (kanonische Keys, siehe tools/suche.py) ──
    db.set_search_criteria("keywords_muss", ["Fertigungssteuerung", "Produktionsplanung", "Industriemeister"])
    db.set_search_criteria("keywords_plus", ["SAP PP", "Arbeitsvorbereitung", "Lean", "Shopfloor", "REFA"])
    db.set_search_criteria("keywords_ausschluss", ["Praktikum", "Werkstudent", "Zeitarbeit"])
    db.set_search_criteria("regionen", ["Hannover", "Braunschweig", "Hildesheim"])
    db.set_search_criteria("stellentypen", ["festanstellung"])
    db.set_search_criteria("max_entfernung", {"festanstellung": 60})
    db.set_search_criteria("min_gehalt", 52000)

    db.set_profile_setting("active_sources", [
        "bundesagentur", "stepstone", "hays", "indeed", "kimeta",
        "stellenanzeigen_de", "jobware",
    ])
    db.set_profile_setting("last_search_at", now.isoformat())

    # ── Stellen: 23 Funde ueber ~8 Monate gestreut, Scores realistisch 2-18 ──
    stellen = [
        # (tage_alt, titel, firma, ort, quelle, score, remote, gehalt_min, gehalt_max, beschreibung)
        (2,   "Fertigungssteuerer (m/w/d)", "Steinfeld Hydraulik GmbH", "Hannover", "bundesagentur", 17, "onsite", 54000, 62000,
              "Feinplanung der mechanischen Fertigung, SAP PP, Schnittstelle AV und Einkauf."),
        (4,   "Produktionsplaner Zerspanung", "Calenberg Maschinenfabrik AG", "Garbsen", "stepstone", 16, "hybrid", 55000, 63000,
              "Kapazitätsplanung für drei Linien, Einführung Feinplanungstool, Key-User-Rolle."),
        (6,   "Industriemeister Metall — Fertigung", "Aller Metallbau GmbH", "Celle", "bundesagentur", 14, "onsite", 52000, 58000,
              "Führung von 22 Mitarbeitern in zwei Schichten, 5S, Unterweisungen, Feinplanung."),
        (9,   "Arbeitsvorbereiter (m/w/d)", "Teutoburg Stanztechnik GmbH", "Hameln", "jobware", 13, "onsite", 50000, 56000,
              "Arbeitspläne, Kalkulation, Rüstoptimierung im Stanzbereich."),
        (12,  "Leiter Arbeitsvorbereitung", "Windrose Energietechnik GmbH", "Braunschweig", "hays", 15, "hybrid", 60000, 70000,
              "Aufbau einer zentralen AV für zwei Werke, Team von vier Planern."),
        (15,  "Fertigungsplaner Getriebebau", "Okertal Getriebe GmbH", "Goslar", "stepstone", 11, "onsite", 51000, 57000,
              "Feinplanung Verzahnung, SAP PP, enge Taktung mit Härterei."),
        (19,  "Produktionsleiter Stellvertretung", "Harzland Pumpen KG", "Hildesheim", "kimeta", 12, "onsite", 58000, 66000,
              "Vertretung der Produktionsleitung, Schwerpunkt Schichtorganisation und Kennzahlen."),
        (24,  "Schichtleiter Zerspanung", "Borgfeld Automotive GmbH", "Peine", "indeed", 10, "onsite", 48000, 54000,
              "Führung einer Fertigungsschicht, Serienbetrieb Automotive, 3-Schicht."),
        (31,  "Fertigungssteuerer Sondermaschinenbau", "Leibniz Schaltanlagen GmbH", "Hannover", "bundesagentur", 14, "onsite", 53000, 60000,
              "Auftragssteuerung Einzelfertigung, Terminverfolgung, Engpassmanagement."),
        (38,  "Arbeitsvorbereiter CNC-Fertigung", "Mühlenberg Werkzeugbau GmbH", "Springe", "stellenanzeigen_de", 12, "onsite", 49000, 55000,
              "NC-Programmverwaltung, Vorrichtungskonstruktion begleiten, Rüstkonzepte."),
        (45,  "Produktionsplaner (m/w/d)", "Deistervilla Feinmechanik GmbH", "Barsinghausen", "stepstone", 13, "hybrid", 52000, 59000,
              "Planung Kleinserien, Umstellung von Excel auf APS-Tool."),
        (52,  "Meister mechanische Fertigung", "Steinhuder Fördertechnik GmbH", "Wunstorf", "bundesagentur", 12, "onsite", 53000, 59000,
              "Meisterbereich mit 18 Mitarbeitern, Investitionsplanung, Lehrlingswesen."),
        (67,  "Teamleiter Arbeitsvorbereitung", "Steinfeld Hydraulik GmbH", "Hannover", "hays", 13, "onsite", 56000, 64000,
              "Führung AV-Team, Einführung Feinplanung, Make-or-Buy-Vorbereitung."),
        (81,  "Fertigungscontroller", "Calenberg Maschinenfabrik AG", "Garbsen", "kimeta", 8, "hybrid", 54000, 61000,
              "Kennzahlen, Nachkalkulation, Soll-Ist-Analysen der Fertigung."),
        (95,  "Produktionsplaner Antriebstechnik", "Windrose Energietechnik GmbH", "Braunschweig", "stepstone", 15, "hybrid", 55000, 62000,
              "Serienplanung Generatorenfertigung, SAP PP/DS, Eskalationsmanagement."),
        # aussortierte Funde (werden unten dismissed)
        (7,   "CNC-Dreher (m/w/d)", "Borgfeld Automotive GmbH", "Peine", "indeed", 6, "onsite", 40000, 46000,
              "Serienfertigung Drehteile, 3-Schicht-Betrieb."),
        (14,  "Fertigungsmeister Kunststofftechnik", "Pleiße Medien GmbH", "Leipzig", "stepstone", 5, "onsite", 50000, 56000,
              "Meisterbereich Spritzguss."),
        (22,  "Produktionshelfer Metall", "Aller Metallbau GmbH", "Celle", "bundesagentur", 2, "onsite", 30000, 34000,
              "Unterstützung der Fertigungsteams."),
        (29,  "Fertigungsplaner (Zeitarbeit)", "Harzland Pumpen KG", "Hildesheim", "indeed", 7, "onsite", 45000, 52000,
              "Einsatz über Personaldienstleister, zunächst befristet."),
        (41,  "Leiter Qualitätswesen", "Teutoburg Stanztechnik GmbH", "Hameln", "jobware", 6, "onsite", 60000, 68000,
              "Leitung QS mit Laborteam."),
        (55,  "Produktionsplaner Pharma", "Salzgold Therme GmbH", "Bad Salzdetfurth", "stepstone", 5, "onsite", 52000, 58000,
              "Planung Abfüllung und Verpackung."),
        (72,  "Betriebsleiter Metallbau", "Mühlenberg Werkzeugbau GmbH", "Springe", "hays", 9, "onsite", 65000, 75000,
              "Gesamtverantwortung Betrieb mit 60 Mitarbeitern."),
        (88,  "Industriemeister Elektro", "Leibniz Schaltanlagen GmbH", "Hannover", "bundesagentur", 3, "onsite", 54000, 60000,
              "Meisterbereich Schaltschrankbau."),
    ]
    jobs = []
    for tage, titel, firma, ort, quelle, score, remote, gmin, gmax, beschr in stellen:
        url = f"https://example.com/jobs/bob/{len(jobs)+1}"
        jobs.append({
            "hash": _job_hash(url), "url": url,
            "title": titel, "company": firma, "location": ort,
            "source": quelle, "score": score, "remote_level": remote,
            "salary_min": gmin, "salary_max": gmax, "salary_type": "jaehrlich",
            "employment_type": "festanstellung",
            "description": beschr + " Fiktive Musterstelle für Demo-Zwecke.",
            "found_at": (now - timedelta(days=tage)).isoformat(),
            "_manual_entry": True,
        })
    db.save_jobs(jobs)

    # Aussortierte Stellen fuellen die Ablehnungsgruende-Statistik.
    for idx, grund in [
        (15, "zu_junior"), (16, "falsches_fachgebiet"), (17, "zu_junior"),
        (18, "zeitarbeit"), (19, "falsches_fachgebiet"), (20, "falsches_fachgebiet"),
        (21, "zu_senior"), (22, "falsches_fachgebiet"),
    ]:
        db.dismiss_job(jobs[idx]["hash"], grund)

    # ── 24 Bewerbungen ueber ~7 Monate, mit realistischen Ausgaengen ──
    # (tage_alt, titel, firma, quelle, job_idx|None, flow, follow_up_in_tagen|None)
    bewerbungen = [
        # laufende Verfahren
        (3,   "Fertigungssteuerer (m/w/d)", "Steinfeld Hydraulik GmbH", "bundesagentur", 0,
              [], 4),
        (6,   "Produktionsplaner Zerspanung", "Calenberg Maschinenfabrik AG", "stepstone", 1,
              [("eingangsbestaetigung", "Automatische Eingangsbestätigung")], None),
        (10,  "Industriemeister Metall — Fertigung", "Aller Metallbau GmbH", "bundesagentur", 2,
              [("eingangsbestaetigung", "Eingang bestätigt"),
               ("interview", "Einladung Erstgespräch vor Ort")], None),
        (13,  "Leiter Arbeitsvorbereitung", "Windrose Energietechnik GmbH", "hays", 4,
              [("eingangsbestaetigung", "Vermittler bestätigt Weiterleitung"),
               ("interview", "Teams-Interview mit Werkleitung"),
               ("zweitgespraech", "Einladung Zweitgespräch mit Betriebsrat und HR")], None),
        (17,  "Fertigungsplaner Getriebebau", "Okertal Getriebe GmbH", "stepstone", 5,
              [], 2),
        (20,  "Produktionsleiter Stellvertretung", "Harzland Pumpen KG", "kimeta", 6,
              [("eingangsbestaetigung", "Eingang bestätigt")], -3),  # ueberfaellig
        (24,  "Fertigungssteuerer Sondermaschinenbau", "Leibniz Schaltanlagen GmbH", "bundesagentur", 8,
              [("interview", "Erstgespräch mit Fertigungsleitung, gutes Gefühl")], None),
        (27,  "Arbeitsvorbereiter CNC-Fertigung", "Mühlenberg Werkzeugbau GmbH", "stellenanzeigen_de", 9,
              [], -6),  # ueberfaellig
        # Verhandlung
        (48,  "Produktionsplaner (m/w/d)", "Deistervilla Feinmechanik GmbH", "stepstone", 10,
              [("eingangsbestaetigung", "Eingang bestätigt"),
               ("interview", "Erstgespräch"),
               ("zweitgespraech", "Werksrundgang und Fachgespräch"),
               ("angebot", "Angebot: 57.500 Euro, 30 Tage Urlaub, Gleitzeit")], None),
        # arbeitgeber_ausgefallen — Angebot lag vor, Firma insolvent vor Antritt
        (105, "Meister mechanische Fertigung", "Steinhuder Fördertechnik GmbH", "bundesagentur", 11,
              [("eingangsbestaetigung", "Eingang bestätigt"),
               ("interview", "Erstgespräch"),
               ("angebot", "Mündliche Zusage, Vertragsentwurf angekündigt"),
               ("arbeitgeber_ausgefallen", "Insolvenzverfahren eröffnet, Stelle entfällt vor Antritt")], None),
        # Absagen nach Interview (mit Grund)
        (62,  "Teamleiter Arbeitsvorbereitung", "Steinfeld Hydraulik GmbH", "hays", 12,
              [("interview", "Erstgespräch mit Bereichsleiter"),
               ("abgelehnt", "Absage nach Erstgespräch", "interne Besetzung")], None),
        (85,  "Produktionsplaner Antriebstechnik", "Windrose Energietechnik GmbH", "stepstone", 14,
              [("eingangsbestaetigung", "Eingang bestätigt"),
               ("interview", "Teams-Interview"),
               ("abgelehnt", "Absage — Mitbewerber mit APS-Projekterfahrung", "Mitbewerber mit mehr Tool-Erfahrung")], None),
        (118, "Fertigungscontroller", "Calenberg Maschinenfabrik AG", "kimeta", 13,
              [("interview", "Erstgespräch Controlling-Leitung"),
               ("abgelehnt", "Absage — Schwerpunkt zu operativ gewünscht", "Profilschwerpunkt passte nicht")], None),
        (131, "Schichtleiter Zerspanung", "Borgfeld Automotive GmbH", "indeed", 7,
              [("interview", "Vor-Ort-Gespräch mit Werkleiter"),
               ("abgelehnt", "Absage — 3-Schicht-Modell dauerhaft, kein Kompromiss", "Schichtmodell unvereinbar")], None),
        # Absagen ohne Antwort / nach langer Stille
        (76,  "Arbeitsvorbereiter (m/w/d)", "Teutoburg Stanztechnik GmbH", "jobware", 3,
              [("abgelaufen", "Acht Wochen keine Reaktion, Stelle offline")], None),
        (93,  "Fertigungssteuerer Werk 2", "Aller Metallbau GmbH", "manuell", None,
              [("abgelaufen", "Keine Reaktion, telefonisch nicht erreichbar")], None),
        (126, "Produktionsplaner Serienfertigung", "Borgfeld Automotive GmbH", "indeed", None,
              [("abgelaufen", "Keine Rückmeldung trotz Nachfassmail")], None),
        (140, "AV-Planer Neubauprojekt", "Leibniz Schaltanlagen GmbH", "manuell", None,
              [("abgelaufen", "Projekt laut Portal verschoben")], None),
        (152, "Fertigungsplaner Standort Nord", "Okertal Getriebe GmbH", "stepstone", None,
              [("abgelaufen", "Sechs Wochen Stille nach Eingangsbestätigung")], None),
        (164, "Meisterstelle Instandhaltung", "Harzland Pumpen KG", "kimeta", None,
              [("abgelaufen", "Keine Reaktion")], None),
        (178, "Produktionssteuerer Halbzeuge", "Steinfeld Hydraulik GmbH", "bundesagentur", None,
              [("abgelaufen", "Stelle mehrfach neu ausgeschrieben, keine Antwort")], None),
        (188, "Fertigungsmeister Blechbearbeitung", "Mühlenberg Werkzeugbau GmbH", "jobware", None,
              [("abgelaufen", "Keine Rückmeldung")], None),
        # zurueckgezogen
        (58,  "Betriebsleiter Metallbau", "Mühlenberg Werkzeugbau GmbH", "hays", 21,
              [("interview", "Erstgespräch"),
               ("zurueckgezogen", "Zurückgezogen — Gesamtverantwortung inkl. Vertrieb, passt nicht zum Profil")], None),
        (112, "Fertigungsplaner (Zeitarbeit)", "Harzland Pumpen KG", "indeed", 18,
              [("zurueckgezogen", "Zurückgezogen — Überlassung statt Festanstellung")], None),
    ]
    app_ids = {}
    for tage, titel, firma, quelle, job_idx, flow, fu_tage in bewerbungen:
        data = {
            "title": titel, "company": firma,
            "status": "beworben",
            "applied_at": _tag(tage),
            "source": quelle,
        }
        if job_idx is not None:
            data["job_hash"] = jobs[job_idx]["hash"]
        app_id = db.add_application(data)
        app_ids[(titel, firma)] = app_id
        _apply_flow(db, app_id, flow)
        if fu_tage is not None:
            db.add_follow_up(app_id, _tag(-fu_tage), "nachfass")

    # Quoten-Karte: PBP-Nutzung begann vor ~7 Monaten.
    db.set_pbp_first_active_at(_tag(210))

    # ── Termine: Historie + kommende Woche(n), plus Privates ──
    meetings = [
        {"application_id": app_ids[("Leiter Arbeitsvorbereitung", "Windrose Energietechnik GmbH")],
         "title": "Zweitgespräch Windrose — Betriebsrat und HR",
         "meeting_date": _tag(-3, hour=10), "platform": "teams",
         "meeting_url": "https://teams.microsoft.com/l/meetup-join/demo-windrose",
         "duration_minutes": 60},
        {"application_id": app_ids[("Produktionsplaner (m/w/d)", "Deistervilla Feinmechanik GmbH")],
         "title": "Vertragsgespräch Deistervilla",
         "meeting_date": _tag(-6, hour=14), "platform": "onsite",
         "location": "Barsinghausen, Werk 1", "duration_minutes": 90},
        {"application_id": app_ids[("Industriemeister Metall — Fertigung", "Aller Metallbau GmbH")],
         "title": "Erstgespräch Aller Metallbau",
         "meeting_date": _tag(-8, hour=9), "platform": "onsite",
         "location": "Celle, Verwaltung", "duration_minutes": 60},
        {"application_id": app_ids[("Fertigungssteuerer Sondermaschinenbau", "Leibniz Schaltanlagen GmbH")],
         "title": "Rückfrage-Telefonat Fertigungsleitung",
         "meeting_date": _tag(-13, hour=11), "platform": "zoom",
         "meeting_url": "https://zoom.us/j/demo-leibniz", "duration_minutes": 30},
        # Historie (durchgefuehrt)
        {"application_id": app_ids[("Leiter Arbeitsvorbereitung", "Windrose Energietechnik GmbH")],
         "title": "Erstgespräch Windrose", "meeting_date": _tag(9, hour=10),
         "platform": "teams", "status": "durchgefuehrt", "duration_minutes": 45},
        {"application_id": app_ids[("Teamleiter Arbeitsvorbereitung", "Steinfeld Hydraulik GmbH")],
         "title": "Erstgespräch Steinfeld", "meeting_date": _tag(55, hour=13),
         "platform": "onsite", "status": "durchgefuehrt", "duration_minutes": 75},
        # Privat
        {"application_id": None, "title": "Feuerwehr — Atemschutzübung",
         "meeting_date": _tag(-4, hour=19), "is_private": 1, "duration_minutes": 120},
        {"application_id": None, "title": "Imkerverein — Monatstreffen",
         "meeting_date": _tag(-11, hour=19), "is_private": 1, "duration_minutes": 90},
    ]
    for m in meetings:
        db.add_meeting(m)

    # ── Kontakte mit Kategorien und Verknuepfung ──
    kontakte = [
        ("Petra Hellwig", "Hays (Vermittlung)", "Recruiterin", "vermittler",
         "Betreut die Windrose-Besetzung, antwortet schnell, bevorzugt Telefon.",
         ("Leiter Arbeitsvorbereitung", "Windrose Energietechnik GmbH")),
        ("Jonas Kretschmar", "Steinfeld Hydraulik GmbH", "Leiter Fertigung", "ansprechpartner",
         "Kennt die Linie aus eigener Meisterzeit, fachlich sehr direkt.",
         ("Fertigungssteuerer (m/w/d)", "Steinfeld Hydraulik GmbH")),
        ("Sabine Rott", "Deistervilla Feinmechanik GmbH", "HR-Leiterin", "hr",
         "Führt das Vertragsgespräch, Urlaubstage noch offen.",
         ("Produktionsplaner (m/w/d)", "Deistervilla Feinmechanik GmbH")),
        ("Michael Brandes", "Calenberg Maschinenfabrik AG", "Produktionsleiter", "ansprechpartner",
         "Kontakt vom Branchenstammtisch, hat die Bewerbung intern weitergereicht.",
         ("Produktionsplaner Zerspanung", "Calenberg Maschinenfabrik AG")),
        ("Ilka Tannhäuser", "Aller Metallbau GmbH", "Personalreferentin", "hr",
         "Koordiniert die Gesprächstermine.", None),
        ("Ralf Okonek", "Ingenieurvermittlung Mitte", "Personalberater", "vermittler",
         "Meldet sich quartalsweise mit Meister-Stellen, seriös.", None),
        ("Heiko Lindwedel", "Nordlicht Antriebstechnik GmbH", "Betriebsratsvorsitzender", "referenz",
         "Referenz für Führungsthemen aus der Schichtmodell-Umstellung.", None),
        ("Frank Siebert", "Feuerwehr Laatzen", "Ortsbrandmeister", "referenz",
         "Referenz fürs Ehrenamt — Führung unter Druck.", None),
    ]
    for name, firma, rolle, tag_slug, notiz, app_ref in kontakte:
        cid = db.add_contact({
            "full_name": name, "company": firma, "position": rolle,
            "email": f"{name.split()[0].lower()}.{name.split()[-1].lower()}@example.org",
            "tags": [tag_slug], "notes": notiz,
        })
        if app_ref:
            db.link_contact(cid, "application", app_ids[app_ref], role=rolle)

    # ── Dokumente ──
    _dokumente(db, [
        ("Lebenslauf_Bob_Mustermann_2026.pdf", "lebenslauf",
         "Industriemeister Metall, 25+ Jahre Zerspanung, Fertigungssteuerung, SAP PP."),
        ("Anschreiben_Steinfeld_Hydraulik.pdf", "anschreiben",
         "Bewerbung als Fertigungssteuerer bei Steinfeld Hydraulik."),
        ("Anschreiben_Windrose_Energietechnik.pdf", "anschreiben",
         "Bewerbung als Leiter Arbeitsvorbereitung bei Windrose Energietechnik."),
        ("Arbeitszeugnis_Leinetal_2012.pdf", "arbeitszeugnis",
         "Sehr gutes Zeugnis als Schichtführer Zerspanung, Führung von 14 Mitarbeitern."),
        ("Arbeitszeugnis_Hansa_Verfahrenstechnik_2015.pdf", "arbeitszeugnis",
         "Zeugnis Fertigungsmeister, ausgestellt durch den Insolvenzverwalter."),
        ("Arbeitszeugnis_Alpenland_2019.pdf", "arbeitszeugnis",
         "Inbetriebnahme-Techniker, Einsätze in sechs Ländern, sehr gute Bewertung."),
        ("Meisterbrief_Industriemeister_Metall.pdf", "zertifikat",
         "IHK Hannover, Industriemeister Metall, 2010."),
        ("REFA_Grundschein_2016.pdf", "zertifikat",
         "REFA-Grundschein Arbeitsorganisation."),
        ("SAP_PP_Anwenderschulung_2016.pdf", "zertifikat",
         "SAP-PP-Anwenderschulung, Bildungswerk Technik Hannover."),
        ("Absage_Windrose_Produktionsplaner.pdf", "absage",
         "Absage nach Teams-Interview — Mitbewerber mit APS-Projekterfahrung."),
        ("Angebot_Deistervilla_Entwurf.pdf", "angebot",
         "Vertragsentwurf Produktionsplaner, 57.500 Euro, 30 Tage Urlaub."),
    ])

    # ── Aufgaben: alle Faelligkeits-Gruppen fuellen ──
    aufgaben = [
        ("Arbeitszeugnis bei Nordlicht anfordern", "Vor dem Standort-Aus schriftlich anfordern.",
         _tag(5), "custom", None),                                # ueberfaellig
        ("Referenz Frank Siebert vorwarnen", "Kurz anrufen, bevor Deistervilla ihn kontaktiert.",
         _tag(1), "custom", None),                                # ueberfaellig
        ("Gehaltsspanne für Vertragsgespräch festlegen", "Untergrenze und Wunschwert notieren.",
         _tag(0), "vorbereitung",
         ("Produktionsplaner (m/w/d)", "Deistervilla Feinmechanik GmbH")),  # heute
        ("Fragen für Zweitgespräch Windrose sammeln", "Team, Investitionsstau, Erwartung erste 100 Tage.",
         _tag(-2), "vorbereitung",
         ("Leiter Arbeitsvorbereitung", "Windrose Energietechnik GmbH")),   # diese Woche
        ("Nachfassen Okertal", "Telefonisch, Ansprechpartner laut Anzeige Fertigungsleitung.",
         _tag(-3), "nachfass",
         ("Fertigungsplaner Getriebebau", "Okertal Getriebe GmbH")),        # diese Woche
        ("Lebenslauf um SAP-Key-User-Rolle schärfen", "Kennzahlen aus der PP-Einführung ergänzen.",
         _tag(-10), "custom", None),                              # spaeter
        ("Weiterbildung APS-Systeme sichten", "Kurse vergleichen, Förderfähigkeit prüfen.",
         _tag(-21), "custom", None),                              # spaeter
        ("Anschreiben-Baukasten aktualisieren", "Bausteine für Meister- vs. Planerrollen trennen.",
         None, "custom", None),                                   # ohne Faelligkeit
    ]
    for titel, beschr, faellig, typ, app_ref in aufgaben:
        db.add_task({
            "titel": titel, "beschreibung": beschr, "faellig_am": faellig,
            "typ": typ,
            "application_id": app_ids[app_ref] if app_ref else None,
        })

    # ── Interview-Reflexionen (v1.7.12) ──
    db.add_interview_reflection(
        app_ids[("Leiter Arbeitsvorbereitung", "Windrose Energietechnik GmbH")],
        {"was_lief_gut": "Beispiele aus der SAP-PP-Einführung kamen sehr gut an, konkrete Zahlen überzeugen.",
         "was_lief_schlecht": "Bei der Frage nach Führungsspanne über Standorte hinweg zu lange herumgeredet.",
         "was_war_ueberraschend": "Werkleitung will die AV komplett neu aufbauen — mehr Gestaltungsspielraum als ausgeschrieben.",
         "gefuehl": 4,
         "next_steps": "Für das Zweitgespräch eine 100-Tage-Skizze auf eine Seite bringen.",
         "wiederverwendbare_antwort": "Die Rüstzeit-Story mit 95 auf 61 Minuten als Standardantwort auf 'größter Hebel'."})
    db.add_interview_reflection(
        app_ids[("Schichtleiter Zerspanung", "Borgfeld Automotive GmbH")],
        {"was_lief_gut": "Fachfragen zur Zerspanung saßen komplett.",
         "was_lief_schlecht": "Zu spät nach dem Schichtmodell gefragt — das hätte das Gespräch früher geklärt.",
         "was_war_ueberraschend": "Dauerhafte Nachtschicht-Rotation war in der Anzeige nicht erkennbar.",
         "gefuehl": 2,
         "next_steps": "Schichtmodell künftig vor der Bewerbung telefonisch klären."})

    return pid


# ===========================================================================
# ANNA BEISPIEL — Hotellerie -> Office -> HR, Raum Leipzig/Halle
# ===========================================================================

def seed_anna(db):
    assert_isolated(db)
    pid = db.create_profile("Anna Beispiel", "anna.beispiel@example.org")
    db.ensure_system_categories()      # Kalender-Kategorien (profil-gebunden)
    db.list_contact_categories()       # legt Standard-Kontaktkategorien an
    now = datetime.now()

    db.save_profile({
        "name": "Anna Beispiel",
        "email": "anna.beispiel@example.org",
        "phone": "0341 5550987",
        "address": "Holunderweg 3",
        "city": "Leipzig",
        "plz": "04277",
        "country": "Deutschland",
        "birthday": "1988-11-02",
        "summary": (
            "Personalfachkauffrau (IHK) mit Wurzeln in der Hotellerie und "
            "Quereinstieg ins Recruiting. Kernkompetenz: Menschen und Abläufe "
            "gleichzeitig im Blick behalten — vom Empfangstresen über die "
            "Kanzlei-Organisation bis zum Bewerbermanagement in der Pflege. "
            "Sucht eine HR-Generalisten- oder Recruiting-Rolle in Teilzeit "
            "(30-35 Stunden) in Leipzig, Halle oder remote."
        ),
        "informal_notes": (
            "Leitet stellvertretend einen vierzigköpfigen Gospelchor und "
            "organisiert die zwei großen Auftritte im Jahr — inklusive "
            "Sponsoren, Technik und Nervenstärke. Trainiert als "
            "Handball-Jugendtrainerin mit C-Lizenz zweimal pro Woche eine "
            "E-Jugend. Lernt im Tandem Spanisch und hat einen "
            "Gebärdensprach-Grundkurs absolviert, seit die Nichte gehörlos "
            "geboren wurde. Mag Prozesse, die auch am Freitagnachmittag um "
            "17 Uhr noch funktionieren."
        ),
        "preferences": {
            "stellentyp": "festanstellung",
            "arbeitsmodell": "hybrid",
            "teilzeit_stunden": "30-35",
            "min_gehalt": 38000,
            "ziel_gehalt": 44000,
            "regionen": ["Leipzig", "Halle (Saale)", "Remote"],
        },
    })

    # ── Stationen (8 Positionen; Elternzeit 2017-2019 als Luecke) ──
    positionen = [
        {"company": "Parkhotel Auenblick", "title": "Auszubildende Hotelfachfrau",
         "location": "Leipzig", "start_date": "2007-08", "end_date": "2010-06",
         "industry": "Hotellerie",
         "description": "Ausbildung mit Stationen in Empfang, Service, Bankett und Reservierung."},
        {"company": "Parkhotel Auenblick", "title": "Empfangsmitarbeiterin",
         "location": "Leipzig", "start_date": "2010-07", "end_date": "2011-10",
         "industry": "Hotellerie",
         "description": "Check-in/Check-out, Reklamationen, Kassenverantwortung."},
        {"company": "Grandhotel Firnlicht", "title": "Front Office Agent (Wintersaison)",
         "location": "Klosters, Schweiz", "start_date": "2011-11", "end_date": "2012-04",
         "industry": "Hotellerie",
         "description": "Saisonstelle im 5-Sterne-Haus, internationales Publikum, "
                        "Englisch und Französisch am Tresen."},
        {"company": "Stadthotel Elsterblick", "title": "Schichtleiterin Empfang",
         "location": "Leipzig", "start_date": "2012-06", "end_date": "2015-05",
         "industry": "Hotellerie",
         "description": "Führung von fünf Mitarbeitenden je Schicht, Dienstplanung, "
                        "Beschwerdemanagement, Einarbeitung."},
        {"company": "Kontor 44 Wirtschaftsprüfung GmbH", "title": "Office Managerin",
         "location": "Leipzig", "start_date": "2015-06", "end_date": "2017-08",
         "industry": "Wirtschaftsprüfung",
         "description": "Branchenwechsel: Empfang, Mandantenkorrespondenz, "
                        "Reiseplanung, vorbereitende Buchhaltung für 30 Beschäftigte."},
        # 2017-09 bis 2019-04: Elternzeit (20 Monate) — bewusste Luecke.
        {"company": "Kontor 44 Wirtschaftsprüfung GmbH", "title": "Office Managerin (Teilzeit 25h)",
         "location": "Leipzig", "start_date": "2019-05", "end_date": "2021-07",
         "industry": "Wirtschaftsprüfung",
         "description": "Wiedereinstieg in Teilzeit nach Elternzeit, zusätzlich "
                        "Übernahme des Bewerbungseingangs der Kanzlei."},
        {"company": "Selbstständig — virtuelle Assistenz", "title": "Virtuelle Assistentin & Bewerbermanagement",
         "location": "Leipzig (remote)", "start_date": "2021-08", "end_date": "2023-09",
         "employment_type": "freelance", "industry": "Dienstleistung",
         "description": "Vier feste Kunden: eine Steuerkanzlei, zwei Handwerksbetriebe, "
                        "ein Pflegedienst. Postfach-Triage, Terminologie, "
                        "Stellenanzeigen, Bewerberkommunikation."},
        {"company": "Pflegewerk Saale gGmbH", "title": "Recruiting-Koordinatorin",
         "location": "Halle (Saale)", "start_date": "2023-10", "end_date": None, "is_current": 1,
         "industry": "Gesundheitswesen",
         "description": "Quereinstieg ins hauptamtliche Recruiting: Bewerbermanagement "
                        "für fünf Einrichtungen, Azubi-Kampagnen, Messeauftritte. "
                        "Vertrag ist befristet und läuft aus.",
         "technologies": "Personio, MS 365, Canva"},
    ]
    pos_ids = [db.add_position(p) for p in positionen]

    # ── 13 STAR-Projekte ──
    projekte = [
        (1, {"name": "Digitale Gästemappe eingeführt",
             "situation": "Gedruckte Gästemappen waren ständig veraltet, Korrekturen dauerten Wochen.",
             "task": "Gästeinformation aktuell halten, ohne Druckkosten.",
             "action": "Tablet-Lösung mit der Hausleitung ausgewählt, Inhalte strukturiert, Reinigung ins Handling eingewiesen.",
             "result": "Druckkosten entfielen, Gästefeedback zur Information deutlich verbessert."}),
        (3, {"name": "Beschwerde-Standard entwickelt",
             "situation": "Beschwerden wurden je nach Schicht völlig unterschiedlich behandelt.",
             "task": "Einheitliche, deeskalierende Beschwerdebehandlung etablieren.",
             "action": "Vier-Schritte-Standard erarbeitet, Team in Rollenspielen trainiert, Kulanzrahmen je Fall definiert.",
             "result": "Eskalationen an die Hotelleitung um mehr als die Hälfte reduziert, Standard ins QM-Handbuch übernommen."}),
        (3, {"name": "Dienstplan-Prozess umgestellt",
             "situation": "Der Empfangs-Dienstplan entstand kurzfristig und produzierte Tauschchaos.",
             "task": "Verlässliche Planung vier Wochen im Voraus.",
             "action": "Wunschabfrage eingeführt, faire Rotationsregeln definiert, Tauschbörse am Schwarzen Brett etabliert.",
             "result": "Kurzfristige Tausche um zwei Drittel gesenkt, Zufriedenheit im Team messbar gestiegen."}),
        (3, {"name": "Auslastungsaktion Nebensaison",
             "situation": "Januar und Februar liefen chronisch schwach.",
             "task": "Belegung in der Nebensaison heben.",
             "action": "Paket-Angebote mit lokalem Theater und Thermengutschein geschnürt, Stammgäste gezielt angeschrieben.",
             "result": "Belegung in den Aktionsmonaten um zwölf Prozentpunkte über Vorjahr."}),
        (2, {"name": "Empfangs-Handbuch übersetzt",
             "situation": "Das interne Empfangs-Handbuch existierte nur auf Deutsch, das Saisonteam war international.",
             "task": "Arbeitsfähige englische Fassung erstellen.",
             "action": "Handbuch gestrafft, übersetzt und mit Screenshots aus dem PMS ergänzt.",
             "result": "Einarbeitungszeit neuer Saisonkräfte deutlich verkürzt; Fassung blieb im Haus in Nutzung."}),
        (4, {"name": "Kanzlei auf digitale Aktenführung umgestellt",
             "situation": "Mandantenunterlagen liefen doppelt: Papier plus Scan bei Bedarf.",
             "task": "Posteingang und Ablage vollständig digitalisieren.",
             "action": "Scan-Strecke eingeführt, Benennungskonventionen definiert, Team geschult, Übergangsphase begleitet.",
             "result": "Suchzeiten drastisch reduziert; Papierarchiv wuchs ab Umstellung nicht mehr."}),
        (4, {"name": "Reisekosten-Prozess vereinfacht",
             "situation": "Reisekostenabrechnungen der Prüfer stauten sich monatelang.",
             "task": "Durchlaufzeit unter zwei Wochen bringen.",
             "action": "Formular vereinfacht, Belegfoto-Regel eingeführt, festen Abrechnungstag etabliert.",
             "result": "Durchschnittliche Durchlaufzeit von sieben Wochen auf neun Tage gesenkt."}),
        (5, {"name": "Bewerbungseingang der Kanzlei aufgebaut",
             "situation": "Bewerbungen landeten verstreut bei Partnern und blieben teils wochenlang unbeantwortet.",
             "task": "Zentralen, verlässlichen Bewerbungseingang schaffen.",
             "action": "Sammelpostfach eingerichtet, Eingangsbestätigung standardisiert, Wiedervorlage-Logik in Outlook gebaut.",
             "result": "Antwortzeit auf unter drei Werktage gesenkt; zwei Besetzungen gingen nachweislich auf schnellere Reaktion zurück."}),
        (6, {"name": "Vier Kunden parallel organisiert",
             "situation": "Vier Auftraggeber mit völlig unterschiedlichen Tools und Erwartungen.",
             "task": "Verlässliche Betreuung ohne Reibungsverluste.",
             "action": "Feste Zeitfenster je Kunde, gemeinsame Aufgabenliste je Auftraggeber, Wochenreport als Standard.",
             "result": "Alle vier Kundenbeziehungen liefen bis zur Aufgabe der Selbstständigkeit stabil; zwei wollten sie fest einstellen."}),
        (6, {"name": "Stellenanzeigen-Baukasten für Handwerk",
             "situation": "Die Handwerkskunden schrieben Anzeigen, auf die niemand reagierte.",
             "task": "Bewerbungsfähige Anzeigen ohne Agenturbudget.",
             "action": "Baukasten mit ehrlichen Texten, Gehaltsangabe und Foto-Guides erstellt, Schaltung auf passende Portale umgestellt.",
             "result": "Beide Betriebe besetzten offene Gesellenstellen innerhalb von acht Wochen."}),
        (7, {"name": "Azubi-Kampagne Social Media",
             "situation": "Der Pflege-Azubi-Jahrgang drohte mit drei Bewerbungen auszufallen.",
             "task": "Bewerbungszahlen für den Ausbildungsstart retten.",
             "action": "Kampagne mit echten Azubis gedreht, Landingpage mit Kurzbewerbung gebaut, Anzeigen regional ausgesteuert.",
             "result": "41 Bewerbungen statt drei im Vorjahr, alle acht Plätze besetzt."}),
        (7, {"name": "Bewerbermanagement-Tool eingeführt",
             "situation": "Bewerbungen liefen über fünf Einrichtungs-Postfächer, niemand hatte den Überblick.",
             "task": "Zentrales Bewerbermanagement für fünf Einrichtungen.",
             "action": "Personio-Einführung koordiniert, Prozesse je Einrichtung harmonisiert, Leitungen geschult.",
             "result": "Durchgängige Pipeline-Sicht; Zeit bis zur ersten Rückmeldung halbiert."}),
        (7, {"name": "Zeugnis-Vorlagenkatalog erstellt",
             "situation": "Arbeitszeugnisse wurden je Einrichtung frei formuliert — mit rechtlichen Risiken.",
             "task": "Rechtssichere, faire Zeugnisbausteine bereitstellen.",
             "action": "Vorlagenkatalog mit externer Beratung aufgebaut, Formulierungsstufen dokumentiert, Freigabeprozess definiert.",
             "result": "Erstellungszeit je Zeugnis von Stunden auf Minuten; keine Beanstandung seit Einführung."}),
    ]
    for idx, projekt in projekte:
        db.add_project(pos_ids[idx], projekt)

    # ── Ausbildung ──
    for edu in [
        {"institution": "Gymnasium Leipzig-Süd", "degree": "Abitur",
         "field_of_study": "", "start_date": "1999", "end_date": "2007"},
        {"institution": "Parkhotel Auenblick / IHK Leipzig", "degree": "Hotelfachfrau (IHK)",
         "field_of_study": "Hotellerie", "start_date": "2007", "end_date": "2010",
         "grade": "sehr gut"},
        {"institution": "Hotelfachschule (Zertifikat)", "degree": "Opera-PMS-Anwenderzertifikat",
         "field_of_study": "Hotelsoftware", "start_date": "2013", "end_date": "2013"},
        {"institution": "IHK Leipzig", "degree": "Personalfachkauffrau (IHK)",
         "field_of_study": "Personalwesen", "start_date": "2021", "end_date": "2022",
         "grade": "gut",
         "description": "Berufsbegleitend während der Selbstständigkeit — der formale "
                        "Unterbau für den Quereinstieg ins Recruiting."},
        {"institution": "Bildungsakademie Mitteldeutschland", "degree": "Systemische Gesprächsführung",
         "field_of_study": "Kommunikation", "start_date": "2023", "end_date": "2023"},
    ]:
        db.add_education(edu)

    # ── ~44 Skills ──
    skills = [
        ("Bewerbermanagement", "fachlich", 5, 2019, None),
        ("Recruiting-Prozesse", "fachlich", 4, 2021, None),
        ("Active Sourcing (Grundlagen)", "fachlich", 3, 2023, None),
        ("Vorstellungsgespräche führen", "fachlich", 4, 2021, None),
        ("Onboarding-Prozesse", "fachlich", 4, 2019, None),
        ("Arbeitszeugnisse erstellen", "fachlich", 4, 2023, None),
        ("Arbeitsrecht (Grundlagen)", "fachlich", 3, 2021, None),
        ("Social-Media-Recruiting", "methodisch", 4, 2022, None),
        ("Personio", "tool", 4, 2023, None),
        ("MS 365 (Word/Excel/Outlook)", "tool", 5, 2010, None),
        ("Outlook-Wiedervorlage-Systeme", "tool", 5, 2015, None),
        ("Canva", "tool", 4, 2021, None),
        ("DATEV (Grundlagen)", "tool", 3, 2015, 2021),
        ("Opera PMS", "tool", 4, 2010, 2015),
        ("SIHOT", "tool", 3, 2012, 2015),
        ("Vorbereitende Buchhaltung", "fachlich", 3, 2015, 2021),
        ("Reisekostenabrechnung", "fachlich", 4, 2015, 2021),
        ("Terminkoordination", "fachlich", 5, 2010, None),
        ("Protokollführung", "fachlich", 4, 2015, None),
        ("Beschwerdemanagement", "fachlich", 5, 2010, None),
        ("Kundenbetreuung", "soft_skill", 5, 2007, None),
        ("Kassenführung", "fachlich", 4, 2007, 2015),
        ("Dienstplanung", "fachlich", 4, 2012, 2015),
        ("Einarbeitung neuer Mitarbeitender", "fuehrung", 4, 2012, None),
        ("Teamführung (bis 5 MA)", "fuehrung", 3, 2012, 2015),
        ("Eventorganisation", "methodisch", 4, 2012, None),
        ("Moderation", "soft_skill", 3, 2021, None),
        ("Selbstorganisation / Remote-Arbeit", "methodisch", 5, 2021, None),
        ("Rechnungsstellung", "fachlich", 4, 2021, 2023),
        ("Kundenakquise", "soft_skill", 3, 2021, 2023),
        ("Stellenanzeigen texten", "fachlich", 4, 2021, None),
        ("Landingpages (Baukasten)", "tool", 3, 2023, None),
        ("Datenschutz im Bewerbungsprozess", "fachlich", 3, 2021, None),
        ("Zeiterfassungssysteme", "tool", 3, 2019, None),
        ("10-Finger-Schreiben", "fachlich", 5, 2005, None),
        ("Systemische Gesprächsführung", "methodisch", 3, 2023, None),
        ("Messeauftritte organisieren", "methodisch", 4, 2023, None),
        ("Deutsch (Muttersprache)", "sprache", 5, None, None),
        ("Englisch (C1)", "sprache", 4, None, None),
        ("Spanisch (B1)", "sprache", 3, None, None),
        ("Französisch (A2)", "sprache", 2, None, None),
        ("Deutsche Gebärdensprache (Grundkurs)", "sprache", 1, 2024, None),
        ("Chor-Organisation (Ehrenamt)", "fuehrung", 4, 2019, None),
        ("Jugendtraining Handball (C-Lizenz)", "zertifizierung", 3, 2016, None),
    ]
    for name, cat, level, sy, ey in skills:
        db.add_skill({
            "name": name, "category": cat, "level": level,
            "start_year": sy, "end_year": ey,
        })

    # ── Suchkriterien ──
    db.set_search_criteria("keywords_muss", ["Recruiting", "Personal", "HR"])
    db.set_search_criteria("keywords_plus", ["Teilzeit", "Bewerbermanagement", "Personio", "Onboarding", "Office"])
    db.set_search_criteria("keywords_ausschluss", ["Leiharbeit", "Provisionsbasis", "Kaltakquise"])
    db.set_search_criteria("regionen", ["Leipzig", "Halle (Saale)", "Remote"])
    db.set_search_criteria("stellentypen", ["festanstellung", "teilzeit"])
    db.set_search_criteria("max_entfernung", {"festanstellung": 45, "teilzeit": 45})
    db.set_search_criteria("min_gehalt", 38000)

    db.set_profile_setting("active_sources", [
        "bundesagentur", "stepstone", "indeed", "arbeitnow", "kimeta",
        "stellenanzeigen_de",
    ])
    db.set_profile_setting("last_search_at", now.isoformat())

    # ── Stellen: 20 Funde, Scores 2-18, ueber ~8 Monate ──
    stellen = [
        (1,   "HR-Generalistin (30h)", "Auwald Klinikgruppe gGmbH", "Leipzig", "bundesagentur", 17, "hybrid", 40000, 46000,
              "Generalistische HR-Rolle mit Schwerpunkt Recruiting und Onboarding, Teilzeit möglich."),
        (3,   "Recruiterin Pflege & Soziales", "Lindenhof Seniorenresidenzen GmbH", "Halle (Saale)", "stepstone", 16, "hybrid", 39000, 45000,
              "Bewerbermanagement für acht Häuser, Azubi-Kampagnen, Personio."),
        (5,   "Personalsachbearbeiterin (Teilzeit)", "Mitteldeutsches Bildungswerk e.V.", "Leipzig", "bundesagentur", 14, "onsite", 36000, 41000,
              "Vertragswesen, Zeugniserstellung, Unterstützung Recruiting."),
        (8,   "Talent Acquisition Coordinator", "Elbaue Logistik SE", "Leipzig", "indeed", 12, "hybrid", 42000, 48000,
              "Koordination des Bewerbungsprozesses für gewerbliche Rollen."),
        (11,  "Office & People Managerin", "Quartier M Immobilien GmbH", "Leipzig", "arbeitnow", 13, "onsite", 38000, 44000,
              "Mischrolle Office Management und HR-Administration."),
        (14,  "HR-Assistenz Kanzlei", "Kanzlei Wetterfeld & Partner", "Leipzig", "kimeta", 11, "onsite", 36000, 42000,
              "Unterstützung der Personalpartnerin, Bewerbungseingang, Fristen."),
        (18,  "Recruiting Specialist (remote)", "Pleiße Medien GmbH", "Remote", "stepstone", 15, "remote", 43000, 49000,
              "Volumen-Recruiting für Kundenservice-Teams, remote-first."),
        (23,  "Personalreferentin Ausbildung", "Salzgold Therme GmbH", "Bad Dürrenberg", "bundesagentur", 10, "onsite", 40000, 45000,
              "Azubi-Marketing und Betreuung, Messen, Schulkooperationen."),
        (29,  "HR Coordinator (32h)", "Rosental Kosmetikwerk GmbH", "Leipzig", "stellenanzeigen_de", 14, "hybrid", 39000, 44000,
              "Bewerbermanagement, Onboarding, HR-Projekte, 32-Stunden-Modell."),
        (35,  "Assistenz der Geschäftsführung mit HR-Anteil", "Cospudener Reisen GmbH", "Markkleeberg", "kimeta", 9, "onsite", 37000, 42000,
              "Klassische GF-Assistenz plus Bewerbungskoordination."),
        (44,  "Recruiting-Koordinatorin", "Auwald Klinikgruppe gGmbH", "Leipzig", "stepstone", 15, "hybrid", 41000, 46000,
              "Pipeline-Verantwortung für Pflegeberufe, Events, Hochschulkontakte."),
        (58,  "People Operations Assistant", "Hafenkontor Halle GmbH", "Halle (Saale)", "indeed", 12, "hybrid", 38000, 43000,
              "HR-Administration, Verträge, Zeugnisse, Tool-Pflege."),
        (73,  "Personalsachbearbeiterin Entgelt", "Elbaue Logistik SE", "Leipzig", "bundesagentur", 6, "onsite", 40000, 46000,
              "Schwerpunkt vorbereitende Entgeltabrechnung."),
        (86,  "HR-Generalistin", "Lindenhof Seniorenresidenzen GmbH", "Halle (Saale)", "stepstone", 14, "hybrid", 40000, 45000,
              "Generalistische Rolle mit Recruiting-Schwerpunkt."),
        (100, "Bewerbermanagement (Teilzeit 30h)", "Mitteldeutsches Bildungswerk e.V.", "Leipzig", "arbeitnow", 13, "hybrid", 36000, 40000,
              "Zentrale Bewerberkommunikation für drei Standorte."),
        # aussortierte Funde
        (9,   "Callcenter-Agentin HR-Hotline", "Pleiße Medien GmbH", "Leipzig", "indeed", 4, "onsite", 28000, 32000,
              "Telefonische Erstberatung."),
        (16,  "Head of People (Vollzeit)", "Quartier M Immobilien GmbH", "Leipzig", "stepstone", 7, "onsite", 65000, 75000,
              "Gesamtverantwortung People & Culture."),
        (26,  "Empfangskraft Nachtschicht", "Stadthotel Elsterblick", "Leipzig", "bundesagentur", 3, "onsite", 28000, 31000,
              "Nachtempfang im Stadthotel."),
        (39,  "HR-Werkstudentin", "Rosental Kosmetikwerk GmbH", "Leipzig", "arbeitnow", 2, "onsite", 15000, 18000,
              "Werkstudentenstelle HR-Team."),
        (63,  "Personalberaterin Provisionsmodell", "Ingenieurvermittlung Mitte", "Leipzig", "indeed", 5, "onsite", 30000, 60000,
              "360-Grad-Vermittlung auf Provisionsbasis."),
    ]
    jobs = []
    for tage, titel, firma, ort, quelle, score, remote, gmin, gmax, beschr in stellen:
        url = f"https://example.com/jobs/anna/{len(jobs)+1}"
        jobs.append({
            "hash": _job_hash(url), "url": url,
            "title": titel, "company": firma, "location": ort,
            "source": quelle, "score": score, "remote_level": remote,
            "salary_min": gmin, "salary_max": gmax, "salary_type": "jaehrlich",
            "employment_type": "festanstellung",
            "description": beschr + " Fiktive Musterstelle für Demo-Zwecke.",
            "found_at": (now - timedelta(days=tage)).isoformat(),
            "_manual_entry": True,
        })
    db.save_jobs(jobs)

    for idx, grund in [
        (15, "falsches_fachgebiet"), (16, "zu_senior"), (17, "unpassendes_arbeitsmodell"),
        (18, "zu_junior"), (19, "unpassendes_arbeitsmodell"),
    ]:
        db.dismiss_job(jobs[idx]["hash"], grund)

    # ── 22 Bewerbungen ueber ~7 Monate ──
    bewerbungen = [
        (2,   "HR-Generalistin (30h)", "Auwald Klinikgruppe gGmbH", "bundesagentur", 0,
              [], 5),
        (4,   "Recruiterin Pflege & Soziales", "Lindenhof Seniorenresidenzen GmbH", "stepstone", 1,
              [("eingangsbestaetigung", "Eingang bestätigt, Rückmeldung in zwei Wochen angekündigt")], None),
        (7,   "Personalsachbearbeiterin (Teilzeit)", "Mitteldeutsches Bildungswerk e.V.", "bundesagentur", 2,
              [], -2),  # ueberfaellig
        (12,  "Talent Acquisition Coordinator", "Elbaue Logistik SE", "indeed", 3,
              [("eingangsbestaetigung", "Eingang bestätigt"),
               ("interview", "Video-Interview mit HR-Leitung")], None),
        (16,  "Recruiting Specialist (remote)", "Pleiße Medien GmbH", "stepstone", 6,
              [("eingangsbestaetigung", "Eingang bestätigt"),
               ("interview", "Erstgespräch remote"),
               ("zweitgespraech", "Fachgespräch mit Team-Lead und Arbeitsprobe")], None),
        (21,  "HR Coordinator (32h)", "Rosental Kosmetikwerk GmbH", "stellenanzeigen_de", 8,
              [("eingangsbestaetigung", "Eingang bestätigt")], 3),
        # Zusage / Angebot in Klaerung
        (33,  "Recruiting-Koordinatorin", "Auwald Klinikgruppe gGmbH", "stepstone", 10,
              [("eingangsbestaetigung", "Eingang bestätigt"),
               ("interview", "Erstgespräch mit Pflegedirektion"),
               ("zweitgespraech", "Hospitationstag in der Einrichtung"),
               ("angebot", "Zusage: 42.000 Euro bei 32h — Detailklärung Arbeitszeiten läuft")], None),
        # Absagen nach Interview
        (54,  "Office & People Managerin", "Quartier M Immobilien GmbH", "arbeitnow", 4,
              [("interview", "Gespräch mit Geschäftsführung"),
               ("abgelehnt", "Absage nach Gespräch", "Vollzeit gewünscht, Teilzeit nicht möglich")], None),
        (79,  "People Operations Assistant", "Hafenkontor Halle GmbH", "indeed", 11,
              [("eingangsbestaetigung", "Eingang bestätigt"),
               ("interview", "Video-Interview"),
               ("abgelehnt", "Absage — interne Kandidatin", "interne Besetzung")], None),
        # Absagen ohne Gespraech
        (46,  "HR-Assistenz Kanzlei", "Kanzlei Wetterfeld & Partner", "kimeta", 5,
              [("abgelehnt", "Standardabsage nach drei Wochen", "keine Begründung")], None),
        (91,  "Personalreferentin Ausbildung", "Salzgold Therme GmbH", "bundesagentur", 7,
              [("abgelehnt", "Absage — Pendelstrecke wurde im Anschreiben thematisiert", "Wohnort zu weit entfernt")], None),
        (108, "HR-Generalistin", "Lindenhof Seniorenresidenzen GmbH", "stepstone", 13,
              [("abgelehnt", "Absage ohne Begründung", "keine Begründung")], None),
        # ohne Antwort / abgelaufen
        (65,  "Assistenz der Geschäftsführung mit HR-Anteil", "Cospudener Reisen GmbH", "kimeta", 9,
              [("abgelaufen", "Sechs Wochen keine Reaktion")], None),
        (120, "Bewerbermanagement (Teilzeit 30h)", "Mitteldeutsches Bildungswerk e.V.", "arbeitnow", 14,
              [("abgelaufen", "Anzeige offline, keine Antwort")], None),
        (133, "Personalsachbearbeiterin Entgelt", "Elbaue Logistik SE", "bundesagentur", 12,
              [("abgelaufen", "Keine Reaktion trotz Nachfrage")], None),
        (147, "HR-Sachbearbeitung Standort Süd", "Auwald Klinikgruppe gGmbH", "manuell", None,
              [("abgelaufen", "Keine Rückmeldung")], None),
        (158, "Recruiting-Assistenz", "Pleiße Medien GmbH", "manuell", None,
              [("abgelaufen", "Stelle laut Portal besetzt, nie geantwortet")], None),
        (170, "Office Managerin Kanzlei", "Kanzlei Wetterfeld & Partner", "manuell", None,
              [("abgelaufen", "Keine Reaktion")], None),
        (182, "Verwaltungsassistenz Bildungszentrum", "Mitteldeutsches Bildungswerk e.V.", "bundesagentur", None,
              [("abgelaufen", "Keine Rückmeldung")], None),
        # zurueckgezogen
        (60,  "Head of People (Vollzeit)", "Quartier M Immobilien GmbH", "stepstone", 16,
              [("zurueckgezogen", "Zurückgezogen — Vollzeit plus Rufbereitschaft unvereinbar mit Familie")], None),
        (98,  "Empfang Praxisklinik (Minijob)", "Auwald Klinikgruppe gGmbH", "manuell", None,
              [("zurueckgezogen", "Zurückgezogen — Umfang zu klein, war als Überbrückung gedacht")], None),
        # noch offen, aelter
        (28,  "Werkstudierenden-Betreuung HR", "Rosental Kosmetikwerk GmbH", "manuell", None,
              [], None),
    ]
    app_ids = {}
    for tage, titel, firma, quelle, job_idx, flow, fu_tage in bewerbungen:
        data = {
            "title": titel, "company": firma,
            "status": "beworben",
            "applied_at": _tag(tage),
            "source": quelle,
        }
        if job_idx is not None:
            data["job_hash"] = jobs[job_idx]["hash"]
        app_id = db.add_application(data)
        app_ids[(titel, firma)] = app_id
        _apply_flow(db, app_id, flow)
        if fu_tage is not None:
            db.add_follow_up(app_id, _tag(-fu_tage), "nachfass")

    db.set_pbp_first_active_at(_tag(200))

    # ── Termine ──
    meetings = [
        {"application_id": app_ids[("Recruiting Specialist (remote)", "Pleiße Medien GmbH")],
         "title": "Zweitgespräch Pleiße Medien — Arbeitsprobe",
         "meeting_date": _tag(-2, hour=9), "platform": "zoom",
         "meeting_url": "https://zoom.us/j/demo-pleisse", "duration_minutes": 90},
        {"application_id": app_ids[("Recruiting-Koordinatorin", "Auwald Klinikgruppe gGmbH")],
         "title": "Telefonat Arbeitszeiten-Klärung Auwald",
         "meeting_date": _tag(-1, hour=15), "platform": "onsite",
         "location": "telefonisch", "duration_minutes": 30},
        {"application_id": app_ids[("Talent Acquisition Coordinator", "Elbaue Logistik SE")],
         "title": "Video-Interview Elbaue Logistik",
         "meeting_date": _tag(-7, hour=11), "platform": "teams",
         "meeting_url": "https://teams.microsoft.com/l/meetup-join/demo-elbaue",
         "duration_minutes": 60},
        # Historie
        {"application_id": app_ids[("Recruiting-Koordinatorin", "Auwald Klinikgruppe gGmbH")],
         "title": "Hospitationstag Auwald", "meeting_date": _tag(12, hour=8),
         "platform": "onsite", "status": "durchgefuehrt", "duration_minutes": 300},
        {"application_id": app_ids[("Office & People Managerin", "Quartier M Immobilien GmbH")],
         "title": "Gespräch Quartier M", "meeting_date": _tag(48, hour=14),
         "platform": "onsite", "status": "durchgefuehrt", "duration_minutes": 60},
        # Privat
        {"application_id": None, "title": "Chorprobe (Auftrittsvorbereitung)",
         "meeting_date": _tag(-5, hour=19), "is_private": 1, "duration_minutes": 120},
        {"application_id": None, "title": "Handball E-Jugend — Training",
         "meeting_date": _tag(-3, hour=17), "is_private": 1, "duration_minutes": 90},
    ]
    for m in meetings:
        db.add_meeting(m)

    # ── Kontakte ──
    kontakte = [
        ("Doreen Mattick", "Auwald Klinikgruppe gGmbH", "Pflegedirektorin", "ansprechpartner",
         "Führte beide Gespräche, sehr an der Azubi-Kampagnen-Erfahrung interessiert.",
         ("Recruiting-Koordinatorin", "Auwald Klinikgruppe gGmbH")),
        ("Stefan Grubitz", "Pleiße Medien GmbH", "Team-Lead Recruiting", "ansprechpartner",
         "Stellt die Arbeitsprobe, remote-first überzeugt.",
         ("Recruiting Specialist (remote)", "Pleiße Medien GmbH")),
        ("Karin Ehrlich", "Lindenhof Seniorenresidenzen GmbH", "HR-Referentin", "hr",
         "Bestätigte Eingang, Entscheidung liegt bei der Regionalleitung.",
         ("Recruiterin Pflege & Soziales", "Lindenhof Seniorenresidenzen GmbH")),
        ("Tom Bresan", "Elbaue Logistik SE", "Recruiter", "recruiter",
         "Führte das Video-Interview, meldet sich nach der Urlaubswoche.",
         ("Talent Acquisition Coordinator", "Elbaue Logistik SE")),
        ("Gesine Wetterfeld", "Kanzlei Wetterfeld & Partner", "Partnerin Personal", "hr",
         "Absage kam von ihr — Kontakt trotzdem freundlich halten.", None),
        ("Maik Odenwald", "Pflegewerk Saale gGmbH", "Einrichtungsleiter", "referenz",
         "Referenz für die Azubi-Kampagne und Personio-Einführung.", None),
        ("Silke Brauner", "Steuerkanzlei (Freelance-Kundin)", "Kanzleiinhaberin", "referenz",
         "Ehemalige Freelance-Kundin, würde jederzeit Referenz geben.", None),
        ("Nadja Kirsten", "Gospelchor Leipzig-Süd", "Chorleiterin", "sonstiges",
         "Kennt halb Leipzig — gute Netzwerkquelle für Vereins- und Stiftungs-Jobs.", None),
    ]
    for name, firma, rolle, tag_slug, notiz, app_ref in kontakte:
        cid = db.add_contact({
            "full_name": name, "company": firma, "position": rolle,
            "email": f"{name.split()[0].lower()}.{name.split()[-1].lower()}@example.org",
            "tags": [tag_slug], "notes": notiz,
        })
        if app_ref:
            db.link_contact(cid, "application", app_ids[app_ref], role=rolle)

    # ── Dokumente ──
    _dokumente(db, [
        ("Lebenslauf_Anna_Beispiel_2026.pdf", "lebenslauf",
         "Personalfachkauffrau (IHK), Quereinstieg Recruiting, Hotellerie-Wurzeln, Teilzeit 30-35h."),
        ("Anschreiben_Auwald_Klinikgruppe.pdf", "anschreiben",
         "Bewerbung als HR-Generalistin (30h) bei der Auwald Klinikgruppe."),
        ("Anschreiben_Pleisse_Medien.pdf", "anschreiben",
         "Bewerbung als Recruiting Specialist (remote) bei Pleiße Medien."),
        ("Arbeitszeugnis_Stadthotel_Elsterblick_2015.pdf", "arbeitszeugnis",
         "Schichtleiterin Empfang, sehr gute Bewertung, Führungsanteil dokumentiert."),
        ("Arbeitszeugnis_Kontor44_2021.pdf", "arbeitszeugnis",
         "Office Managerin, inkl. Aufbau des Bewerbungseingangs."),
        ("Zwischenzeugnis_Pflegewerk_Saale_2026.pdf", "arbeitszeugnis",
         "Recruiting-Koordinatorin, Azubi-Kampagne und Personio-Einführung hervorgehoben."),
        ("IHK_Personalfachkauffrau_2022.pdf", "zertifikat",
         "IHK-Prüfungszeugnis Personalfachkauffrau, Note gut."),
        ("Zertifikat_Systemische_Gespraechsfuehrung.pdf", "zertifikat",
         "Bildungsakademie Mitteldeutschland, 2023."),
        ("Referenzschreiben_Steuerkanzlei_2023.pdf", "referenz",
         "Referenz der Freelance-Kundin: zuverlässig, strukturiert, mitdenkend."),
        ("Absage_Quartier_M.pdf", "absage",
         "Absage nach Gespräch — Teilzeit nicht darstellbar."),
        ("Zusage_Auwald_Konditionen.pdf", "angebot",
         "Zusage Recruiting-Koordinatorin, 42.000 Euro bei 32h, Details offen."),
    ])

    # ── Aufgaben ──
    aufgaben = [
        ("Nachfassen Bildungswerk", "Teilzeit-Bewerbung ist zwei Wochen ohne Reaktion.",
         _tag(2), "nachfass",
         ("Personalsachbearbeiterin (Teilzeit)", "Mitteldeutsches Bildungswerk e.V.")),  # ueberfaellig
        ("Arbeitsprobe Pleiße vorbereiten", "Beispiel-Kampagne für gewerbliches Recruiting skizzieren.",
         _tag(0), "vorbereitung",
         ("Recruiting Specialist (remote)", "Pleiße Medien GmbH")),                      # heute
        ("Arbeitszeiten-Varianten für Auwald durchrechnen", "32h auf 4 oder 5 Tage — Betreuungszeiten prüfen.",
         _tag(-1), "vorbereitung",
         ("Recruiting-Koordinatorin", "Auwald Klinikgruppe gGmbH")),                     # diese Woche
        ("Zwischenzeugnis-Formulierung prüfen", "Zwei Formulierungen wirken abwertend — ansprechen.",
         _tag(-4), "custom", None),                                                      # diese Woche
        ("Referenzliste aktualisieren", "Silke Brauner und Maik Odenwald um aktuelle Kontaktdaten bitten.",
         _tag(-12), "custom", None),                                                     # spaeter
        ("LinkedIn-Profil auf Recruiting-Fokus umstellen", "Headline und Über-mich-Text anpassen.",
         _tag(-18), "custom", None),                                                     # spaeter
        ("Gehaltsband für Verhandlung Auwald festlegen", "Untergrenze bei 32h definieren.",
         None, "custom", None),                                                          # ohne Faelligkeit
    ]
    for titel, beschr, faellig, typ, app_ref in aufgaben:
        db.add_task({
            "titel": titel, "beschreibung": beschr, "faellig_am": faellig,
            "typ": typ,
            "application_id": app_ids[app_ref] if app_ref else None,
        })

    # ── Interview-Reflexionen ──
    db.add_interview_reflection(
        app_ids[("Recruiting-Koordinatorin", "Auwald Klinikgruppe gGmbH")],
        {"was_lief_gut": "Die Azubi-Kampagne mit 41 statt 3 Bewerbungen hat das Gespräch getragen.",
         "was_lief_schlecht": "Auf die Frage nach Kennzahlen-Reporting zu allgemein geblieben.",
         "was_war_ueberraschend": "Hospitationstag statt klassischem Zweitgespräch — sehr aufschlussreich.",
         "gefuehl": 5,
         "next_steps": "Arbeitszeiten klären, dann entscheiden.",
         "wiederverwendbare_antwort": "Quereinstieg als Stärke rahmen: Ich habe Recruiting von der Bewerberseite aus gelernt."})
    db.add_interview_reflection(
        app_ids[("Office & People Managerin", "Quartier M Immobilien GmbH")],
        {"was_lief_gut": "Gute Gesprächsatmosphäre, Mischrolle hätte fachlich gepasst.",
         "was_lief_schlecht": "Teilzeitwunsch erst am Ende platziert — künftig früh im Prozess klären.",
         "was_war_ueberraschend": "Vollzeit war nicht verhandelbar, stand aber nicht in der Anzeige.",
         "gefuehl": 3,
         "next_steps": "Teilzeit-Rahmen künftig schon im Anschreiben benennen."})

    return pid


def seed_all(db):
    """Beide Musterprofile anlegen; Bob bleibt das aktive Profil."""
    assert_isolated(db)
    pid_anna = seed_anna(db)
    pid_bob = seed_bob(db)
    return {"bob": pid_bob, "anna": pid_anna}
