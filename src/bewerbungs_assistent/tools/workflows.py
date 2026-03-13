"""Workflow-Tools — macht MCP-Prompts als Tools verfuegbar.

claude.ai (Web) unterstuetzt keine MCP-Prompts (/slash-commands).
Dieses Modul stellt die wichtigsten Workflows als aufrufbare Tools bereit,
damit sie sowohl in Claude Desktop als auch in claude.ai funktionieren.
"""

import asyncio


def register(mcp, db, logger):
    """Registriert Workflow-Tools (Prompt-Wrapper)."""

    def _get_prompt_text(name: str) -> str:
        """Holt den Prompt-Text aus dem registrierten MCP-Prompt."""
        from ..prompts import register_prompts as _  # noqa — ensures prompts registered

        # Build prompt text by calling the prompt function directly
        prompt_funcs = _prompt_registry(db)
        if name in prompt_funcs:
            return prompt_funcs[name]()
        return f"Workflow '{name}' nicht gefunden."

    @mcp.tool()
    def workflow_starten(name: str = "") -> dict:
        """Startet einen gefuehrten Workflow. Ohne Parameter: zeigt alle verfuegbaren Workflows.

        Verfuegbare Workflows:
        - jobsuche_workflow: Gefuehrter Jobsuche-Prozess (Kriterien → Suche → Ergebnisse → Bewerbung)
        - ersterfassung: Lockeres Profilerfassungs-Interview
        - bewerbung_schreiben: Stellenspezifisches Anschreiben erstellen
        - interview_vorbereitung: Interview-Vorbereitung mit STAR-Antworten
        - interview_simulation: Simuliertes Bewerbungsgespraech
        - profil_ueberpruefen: Profil anschauen und korrigieren
        - profil_analyse: Detaillierte Profilbewertung
        - profil_erweiterung: Dokumente analysieren und Profil erweitern
        - bewerbungs_uebersicht: Komplette Uebersicht aller Aktivitaeten
        - gehaltsverhandlung: Gehaltsverhandlung vorbereiten
        - netzwerk_strategie: Networking-Strategie entwickeln
        - willkommen: Willkommensbildschirm mit Status

        WICHTIG: Wenn du die Anweisungen erhaeltst, fuehre sie Schritt fuer Schritt aus.
        Die Anweisungen enthalten Tool-Aufrufe die du ausfuehren sollst."""
        if not name:
            return {
                "hinweis": "Bitte einen Workflow-Namen angeben.",
                "verfuegbare_workflows": [
                    {"name": "jobsuche_workflow", "beschreibung": "Gefuehrter Jobsuche-Prozess"},
                    {"name": "ersterfassung", "beschreibung": "Lockeres Profilerfassungs-Interview"},
                    {"name": "bewerbung_schreiben", "beschreibung": "Anschreiben erstellen"},
                    {"name": "interview_vorbereitung", "beschreibung": "Interview-Vorbereitung"},
                    {"name": "interview_simulation", "beschreibung": "Simuliertes Bewerbungsgespraech"},
                    {"name": "profil_ueberpruefen", "beschreibung": "Profil korrigieren"},
                    {"name": "profil_analyse", "beschreibung": "Profilbewertung"},
                    {"name": "profil_erweiterung", "beschreibung": "Dokumente analysieren"},
                    {"name": "bewerbungs_uebersicht", "beschreibung": "Komplette Uebersicht"},
                    {"name": "gehaltsverhandlung", "beschreibung": "Gehaltsverhandlung vorbereiten"},
                    {"name": "netzwerk_strategie", "beschreibung": "Networking-Strategie"},
                    {"name": "willkommen", "beschreibung": "Willkommensbildschirm"},
                ],
                "beispiel": "workflow_starten(name='jobsuche_workflow')"
            }

        text = _get_prompt_text(name)
        logger.info("Workflow gestartet: %s", name)
        return {
            "workflow": name,
            "status": "gestartet",
            "anweisungen": text,
            "hinweis": "Fuehre die obigen Anweisungen Schritt fuer Schritt aus. "
                       "Rufe die genannten Tools auf und fuehre den User durch den Prozess."
        }

    @mcp.tool()
    def jobsuche_workflow_starten() -> dict:
        """Startet den gefuehrten Jobsuche-Workflow: Suchkriterien pruefen, Quellen aktivieren,
        Suche starten, Ergebnisse sichten, Bewerbung vorbereiten.
        Dieser Workflow fuehrt dich Schritt fuer Schritt durch den gesamten Prozess."""
        return workflow_starten(name="jobsuche_workflow")

    @mcp.tool()
    def ersterfassung_starten() -> dict:
        """Startet die Ersterfassung — ein lockeres Interview zur Profilerfassung,
        wie ein Kaffeegespraech. Kann jederzeit unterbrochen und spaeter fortgesetzt werden."""
        return workflow_starten(name="ersterfassung")


def _prompt_registry(db):
    """Erstellt ein Dict mit Prompt-Name → Callable fuer alle registrierten Prompts."""
    import json

    def _ersterfassung():
        from ..prompts import register_prompts
        # We need to return the prompt text directly
        # Re-implement the dynamic parts here
        return _static_prompt("ersterfassung")

    def _jobsuche_workflow():
        criteria = db.get_search_criteria()
        active_sources = db.get_setting("active_sources", [])
        active_jobs = len(db.get_active_jobs())
        last_search = db.get_setting("last_search_at", "")
        last_info = ""
        if last_search:
            try:
                from datetime import datetime
                d = datetime.fromisoformat(last_search)
                days = (datetime.now() - d).days
                last_info = f"Letzte Suche: {last_search} ({days} Tag(e) her)"
            except Exception:
                last_info = f"Letzte Suche: {last_search}"

        return f"""Starte den gefuehrten Jobsuche-Workflow.

DU FUEHRST DEN USER SCHRITT FUER SCHRITT DURCH DIESEN PROZESS.
Erklaere bei jedem Schritt WAS passiert und WARUM.

{f'i {last_info}' if last_info else ''}

SCHRITT 1: SUCHKRITERIEN PRUEFEN
Aktueller Stand: {json.dumps(criteria, ensure_ascii=False, indent=2) if criteria else 'Noch keine Kriterien gesetzt!'}

Falls keine/wenige Kriterien gesetzt:
→ Frage den User:
  "Welche Begriffe MUESSEN in einer Stelle vorkommen? (z.B. PLM, SAP, Projektmanagement)"
  "Welche Begriffe waeren ein Bonus? (z.B. Remote, Python, Agile)"
  "Gibt es Begriffe die du NICHT willst? (z.B. Junior, Praktikum, Zeitarbeit)"
→ Speichere mit suchkriterien_setzen()

SCHRITT 2: QUELLEN AKTIVIEREN
Aktive Quellen: {active_sources if active_sources else 'KEINE! (Quellen muessen erst aktiviert werden)'}

Falls keine Quellen aktiv:
→ Erklaere welche Quellen verfuegbar sind (StepStone, Indeed, Monster, BA, Hays, Freelancermap, LinkedIn, XING)
→ Frage welche der User nutzen moechte

SCHRITT 3: SUCHE STARTEN
{f'Es gibt bereits {active_jobs} aktive Stellen aus frueheren Suchen.' if active_jobs > 0 else 'Noch keine Stellen gefunden.'}
→ Starte die Suche mit jobsuche_starten()
→ Informiere den User ueber den Fortschritt mit jobsuche_status()

SCHRITT 4: ERGEBNISSE SICHTEN
→ Zeige die Ergebnisse mit stellen_anzeigen()
→ Fuer interessante Stellen: fit_analyse(hash) fuer Details
→ Bewerte gemeinsam: stelle_bewerten(hash, 'passt') oder stelle_bewerten(hash, 'passt_nicht', grund)

SCHRITT 5: BEWERBUNG VORBEREITEN
→ "Soll ich ein Anschreiben fuer [Stelle] bei [Firma] schreiben?"
→ Exportiere als PDF/DOCX
→ Erfasse die Bewerbung mit bewerbung_erstellen()

REGELN:
- Erklaere jeden Schritt verstaendlich
- Ueberspringe Schritte die bereits erledigt sind
- Sprich Deutsch und per Du"""

    def _willkommen():
        profile = db.get_profile()
        has_profile = profile is not None
        active_jobs = len(db.get_active_jobs()) if has_profile else 0
        apps = len(db.get_applications()) if has_profile else 0
        criteria = db.get_search_criteria() if has_profile else {}

        if has_profile:
            name = profile.get("name", "")
            return f"""Willkommen zurueck, {name}!

Dein Bewerbungs-Assistent ist bereit. Hier ein Ueberblick:

DEIN STATUS:
  Profil: angelegt
  Aktive Stellen: {active_jobs}
  Bewerbungen: {apps}
  Suchkriterien: {'gesetzt' if criteria.get('keywords_muss') else 'noch nicht gesetzt'}
  Dashboard: http://localhost:8200

WAS KANN ICH FUER DICH TUN?
  - "Starte eine Jobsuche" → jobsuche_workflow_starten()
  - "Schreib mir ein Anschreiben" → workflow_starten(name='bewerbung_schreiben')
  - "Bereite mich auf ein Interview vor" → workflow_starten(name='interview_vorbereitung')
  - "Exportiere meinen Lebenslauf als PDF" → lebenslauf_exportieren()
  - "Wie sieht mein Profil aus?" → profil_zusammenfassung()
  - "Analysiere mein Profil" → workflow_starten(name='profil_analyse')

Frag einfach in deinen eigenen Worten!"""

        return """Willkommen beim Bewerbungs-Assistent!

Ich bin dein persoenlicher Karriere-Helfer. Ich helfe dir dabei:

- PROFIL ERSTELLEN: Lockeres Gespraech, kein steifes Formular
- JOBS FINDEN: Bis zu 9 Jobportale gleichzeitig durchsuchen
- BEWERBUNGEN SCHREIBEN: Stellenspezifische Anschreiben, Export als PDF/DOCX
- LEBENSLAUF EXPORTIEREN: Professionell formatiert
- INTERVIEW-VORBEREITUNG: STAR-Antworten, Gehaltsverhandlung
- BEWERBUNGS-TRACKING: Dashboard auf http://localhost:8200

Starte mit: ersterfassung_starten() oder sag einfach "Lass uns mein Profil erstellen!" """

    def _bewerbungs_uebersicht():
        return """Erstelle eine umfassende Uebersicht fuer den User.

ABLAUF:
1. Rufe profil_zusammenfassung() auf
2. Rufe stellen_anzeigen() auf
3. Rufe bewerbungen_anzeigen() auf
4. Rufe statistiken_abrufen() auf

DANN:
→ Fasse die Situation zusammen
→ Schlage naechste Schritte vor
→ Sprich Deutsch und per Du. Sei proaktiv mit Vorschlaegen."""

    def _profil_analyse():
        return """Analysiere das Bewerberprofil und liefere:

1. Staerken — Was macht dieses Profil besonders attraktiv?
2. Verbesserungspotenzial — Was koennte ergaenzt werden?
3. Luecken — Erkennbare Luecken? (NICHT werten, konstruktiv helfen)
4. Marktposition — Wie steht das Profil im aktuellen Arbeitsmarkt?
5. Empfehlungen — Konkrete, umsetzbare Tipps
6. Passende Berufsbezeichnungen — Stellentitel die zum Profil passen

Rufe zuerst profil_zusammenfassung() auf.
Sei ehrlich aber konstruktiv und ermutigend."""

    def _profil_ueberpruefen():
        return """Der User moechte sein Profil ueberpruefen und ggf. korrigieren.

ABLAUF:
1. Rufe profil_zusammenfassung() auf und zeige die Uebersicht
2. Frage: "Stimmt alles so? Was moechtest du aendern?"
3. Bei Korrekturen: Nutze profil_bearbeiten() fuer gezielte Aenderungen
4. Wenn fehlende Bereiche: "Ich sehe dass [X] noch fehlt. Moechtest du das ergaenzen?"
5. Iteriere bis der User zufrieden ist

Sprich Deutsch und per Du. Sei nicht aufdringlich — biete an, draenge nicht."""

    def _bewerbung_schreiben():
        return """Erstelle Bewerbungsunterlagen (Lebenslauf + Anschreiben).

SCHRITTE:
1. Rufe profil_zusammenfassung() auf
2. Frage nach Stelle und Firma (falls nicht bekannt)
3. LEBENSLAUF-ANALYSE (3-PERSPEKTIVEN-CHECK):
   → lebenslauf_bewerten(stelle, firma, stellenbeschreibung)
   → Zeige Bewertung aus 3 Perspektiven:
     - Personalberater: Karriereverlauf, Soft Skills, Fuehrung
     - ATS: Keywords, Format, Metriken
     - Recruiter: Technische Tiefe, Projekte, Tech-Stack
   → Zeige Gesamtscore und Top-Empfehlungen
   → Frage: "Schwerpunkt setzen? (z.B. ATS-optimiert oder Personalberater-fokussiert?)"
   → Bei Gewichtungsaenderung: erneut lebenslauf_bewerten() mit neuen Gewichten aufrufen
4. LEBENSLAUF ERSTELLEN:
   → lebenslauf_angepasst_exportieren(stelle, firma, stellenbeschreibung)
   → Relevante Skills und Erfahrungen werden hervorgehoben und priorisiert
   → IMMER als DOCX — finale Formatierung macht der User
   → Zeige dem User was angepasst wurde
5. ANSCHREIBEN ERSTELLEN:
   → Waehle die relevantesten Erfahrungen und Projekte
   → Erstelle ein Anschreiben (max. 1 Seite, professionell aber persoenlich)
   → Zeige den Text — "Passt das so?"
   → Nach Freigabe: anschreiben_exportieren (als DOCX)
6. Bewerbung im Tracking erfassen (bewerbung_erstellen)

REGELN:
- Lebenslauf IMMER als DOCX (nie PDF)
- Die 3-Perspektiven-Analyse kommt VOR dem Export — damit der User noch reagieren kann
- Erst Analyse, dann Lebenslauf, dann Anschreiben, dann Tracking
- Manchmal braucht der User nur den Lebenslauf — dann Anschreiben ueberspringen
- Sprich Deutsch"""

    def _interview_vorbereitung():
        return """Bereite den Nutzer auf ein Bewerbungsgespraech vor.

ZUERST: Rufe profil_zusammenfassung() auf.
Frage nach Stelle und Firma (falls nicht bekannt).

DANN LIEFERE:
1. Die 10 wahrscheinlichsten Fragen (Fachlich, Persoenlich, Situativ, Motivation)
2. STAR-Antworten mit konkreten Beispielen aus dem Profil
3. Schwaechen-Strategie (authentisch, nicht ausweichend)
4. Gehaltsverhandlung (basierend auf Erfahrung, Region, Branche)
5. 5 kluge eigene Fragen
6. Argumentationsleitfaden "Warum bin ICH ideal?"
7. Quick-Reference-Karte

Alles MUSS personalisiert sein. Sprich Deutsch und per Du."""

    def _interview_simulation():
        return """Du bist jetzt der Interviewer. Fuehre ein realistisches Bewerbungsgespraech.

VORBEREITUNG: Rufe profil_zusammenfassung() auf. Frage nach Stelle und Firma.

PHASE 1 — KENNENLERNEN (2-3 Fragen)
PHASE 2 — FACHFRAGEN (3-4 Fragen)
PHASE 3 — SITUATIVE FRAGEN / STAR (2-3 Fragen)

REGELN:
- NUR EINE Frage auf einmal
- Warte auf die Antwort
- Am Ende: Konstruktives Feedback zu JEDER Antwort
- Bewerte: Struktur, Konkretheit, STAR-Format
- Gesamtbewertung (1-10)
- Sprich formal (Sie) als Interviewer"""

    def _gehaltsverhandlung():
        return """Bereite eine Gehaltsverhandlung vor.

DATENSAMMLUNG:
1. Rufe profil_zusammenfassung() auf
2. Frage nach Stelle und Firma

ANALYSE & STRATEGIE:
1. Marktanalyse (Was zahlt der Markt?)
2. Dein Wert (einzigartige Kompetenzen, Erfolge)
3. Verhandlungsstrategie (Ankerpunkt, Minimum, Ziel, Stretch)
4. 5 konkrete Argumentations-Saetze
5. Taktiken (Gesamtpaket, nie sofort zusagen)
6. Fallstricke und Antworten

Sprich Deutsch, per Du, konkrete Zahlen."""

    def _netzwerk_strategie():
        return """Entwickle eine Networking-Strategie.

DATENSAMMLUNG:
1. Rufe profil_zusammenfassung() auf
2. Frage nach Zielfirma

STRATEGIE:
1. Firmen-Analyse
2. Kontaktsuche (Anleitung fuer LinkedIn)
3. Anschreiben-Templates (Erstkontakt, Informationsgespraech, Follow-up)
4. Zeitplan (4 Wochen)
5. Dos and Don'ts

Sprich Deutsch und per Du."""

    def _profil_erweiterung():
        profile = db.get_profile()
        docs = profile.get("documents", []) if profile else []
        conn = db.connect()
        unextracted = []
        if profile:
            rows = conn.execute(
                "SELECT id, filename, doc_type FROM documents WHERE profile_id=? AND "
                "extraction_status='nicht_extrahiert' AND extracted_text IS NOT NULL AND extracted_text != ''",
                (profile["id"],)
            ).fetchall()
            unextracted = [dict(r) for r in rows]

        return f"""Analysiere hochgeladene Dokumente und erweitere das Bewerberprofil.

Profil vorhanden: {'Ja — ' + profile.get('name', '') if profile else 'Nein'}
Dokumente gesamt: {len(docs)}
Noch nicht extrahiert: {len(unextracted)}

SCHRITTE:
1. Rufe extraktion_starten() auf
2. Analysiere jedes Dokument (Typ erkennen, Daten extrahieren, mit Profil vergleichen)
3. Rufe extraktion_ergebnis_speichern() auf
4. Zeige dem User was gefunden wurde, frage bei Konflikten
5. Rufe extraktion_anwenden() auf nach Bestaetigung
6. Zeige profil_zusammenfassung() als Kontrolle

Sprich Deutsch und per Du. Bei Konflikten IMMER den User fragen."""

    return {
        "ersterfassung": _static_ersterfassung,
        "jobsuche_workflow": _jobsuche_workflow,
        "willkommen": _willkommen,
        "bewerbungs_uebersicht": _bewerbungs_uebersicht,
        "profil_analyse": _profil_analyse,
        "profil_ueberpruefen": _profil_ueberpruefen,
        "bewerbung_schreiben": _bewerbung_schreiben,
        "interview_vorbereitung": _interview_vorbereitung,
        "interview_simulation": _interview_simulation,
        "gehaltsverhandlung": _gehaltsverhandlung,
        "netzwerk_strategie": _netzwerk_strategie,
        "profil_erweiterung": _profil_erweiterung,
    }


def _static_ersterfassung():
    """Ersterfassung-Prompt (statisch, keine DB-Abhaengigkeiten)."""
    return """Du bist ein freundlicher Karriereberater. Dies ist ein zwangloses Gespraech.

SCHRITT 0: FORTSCHRITT PRUEFEN
Rufe zuerst auf: erfassung_fortschritt_lesen() und profile_auflisten()
Falls angefangenes Profil: Weitermachen wo aufgehoert.
Falls mehrere Profile: Fragen welches bearbeitet werden soll.

PHASE 1: LOCKERER EINSTIEG
"Hey, schoen dass du hier bist! Erzaehl mal: Wie heisst du und was machst du so beruflich?"
Nur 1-2 offene Fragen, NICHT nach E-Mail/Telefon im ersten Schritt!

PHASE 2: STRUKTURIERTE ERFASSUNG
a) Persoenliche Daten → profil_erstellen()
b) Berufserfahrung → position_hinzufuegen(), projekt_hinzufuegen()
c) Ausbildung → ausbildung_hinzufuegen()
d) Skills → skill_hinzufuegen()
e) Zwanglose Notizen → informal_notes

PHASE 3: PRAEFERENZ-FRAGEN
Branche, Festanstellung/Freelance, Region, Remote, Gehalt, Reisebereitschaft
→ profil_erstellen() aktualisieren

PHASE 4: REVIEW
→ profil_zusammenfassung() aufrufen und zeigen
→ Korrigieren bis der User zufrieden ist

REGELN:
- Max 2-3 Fragen pro Nachricht
- Deutsch und per Du
- Ermutigend bei Luecken
- SOFORT mit Tools speichern
- erfassung_fortschritt_speichern() nach jedem Bereich"""
