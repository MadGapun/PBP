"""Workflow-Tools — macht MCP-Prompts als Tools verfügbar.

claude.ai (Web) unterstützt keine MCP-Prompts (/slash-commands).
Dieses Modul stellt die wichtigsten Workflows als aufrufbare Tools bereit,
damit sie sowohl in Claude Desktop als auch in claude.ai funktionieren.
"""

import asyncio

from ..prompts import build_kennlerngespraech_prompt


def register(mcp, db, logger):
    """Registriert Workflow-Tools (Prompt-Wrapper)."""
    from . import ki_gate

    @mcp.tool()
    def workflow_starten(name: str = "") -> dict:
        """Startet einen gefuehrten Ablauf (Jobsuche, Anschreiben, Interview ...) und liefert die Anweisungen dazu.

        Ohne Namen: die Liste aller Ablaeufe aus dem Prompt-Katalog, mit
        Titel und Beschreibung — dieselbe Liste wie im Dashboard. Mit Namen
        (eine Katalog-Kennung wie 'jobsuche_workflow' oder
        'bewerbung_schreiben_lebenslauf'): die Anweisungen; fuehre sie
        Schritt fuer Schritt aus.

        Args:
            name: Kennung aus der Liste; leer zeigt die Liste.
        """
        # H22 (#1087 G2): die Liste kommt aus dem Katalog statt aus einer
        # eigenen Aufzaehlung (16 Eintraege, die nicht mehr zum Katalog
        # passten). Der Text kommt aus `_prompt_registry`, derselben Quelle
        # wie der Slash-Befehl.
        from ..services import prompt_katalog as _katalog
        if not name:
            return {
                "hinweis": "Bitte einen Workflow-Namen angeben.",
                "verfuegbare_workflows": [
                    {"name": e["id"], "titel": e["titel"],
                     "beschreibung": e.get("beschreibung", "")}
                    for e in _katalog.alle()
                ],
                "beispiel": "workflow_starten(name='jobsuche_workflow')",
            }

        # #694: Namen normalisieren (lowercase + Umlaut-Transliteration), damit
        # z.B. 'profil_überprüfen' den Registry-Key 'profil_ueberpruefen' trifft
        name = name.strip().lower()
        for umlaut, ersatz in (("ü", "ue"), ("ö", "oe"), ("ä", "ae"), ("ß", "ss")):
            name = name.replace(umlaut, ersatz)

        prompt_funcs = _prompt_registry(db)
        eintrag = _katalog.eintrag(name)
        prompt_name = eintrag["prompt"] if eintrag else name
        parameter = dict(eintrag.get("parameter") or {}) if eintrag else {}
        if prompt_name not in prompt_funcs:
            # #694: kein Pseudo-Erfolg (status='gestartet' mit Fehlertext) mehr
            return {
                "fehler": f"Workflow '{name}' nicht gefunden.",
                "verfuegbare_workflows": [e["id"] for e in _katalog.alle()],
            }

        text = prompt_funcs[prompt_name](**parameter)
        logger.info("Workflow gestartet: %s", name)
        return {
            "workflow": name,
            "status": "gestartet",
            "anweisungen": text,
            "hinweis": "Führe die obigen Anweisungen Schritt für Schritt aus. "
                       "Rufe die genannten Tools auf und fuehre den User durch den Prozess."
        }

    @mcp.tool()
    def schnellzugriff_setzen(prompts: str = "") -> dict:
        """Welche Prompt-Karten im Dashboard-Schnellzugriff stehen (#979).

        Ohne Argument: zeigt den Katalog und die aktuelle Auswahl, damit
        der Nutzer sieht, was es gibt, bevor er waehlt.

        Args:
            prompts: Katalog-Kennungen, kommagetrennt. Ein leerer String
                zeigt nur an; das Wort 'standard' stellt die
                Voreinstellung wieder her.
        """
        from ..services import prompt_katalog

        katalog = prompt_katalog.alle()
        if not (prompts or "").strip():
            aktuell = prompt_katalog.auswahl(db)
            return {
                "aktuell": aktuell,
                "anzahl": len(aktuell),
                "katalog": [
                    {"kennung": e["id"], "titel": e["titel"],
                     "kategorie": e["kategorie"],
                     "beschreibung": e["beschreibung"],
                     "im_schnellzugriff": e["id"] in aktuell}
                    for e in katalog
                ],
                "hinweis": (
                    "Auswahl setzen: schnellzugriff_setzen(prompts='a,b,c'). "
                    "Voreinstellung: schnellzugriff_setzen(prompts='standard')."),
            }

        roh = [t.strip() for t in str(prompts).split(",") if t.strip()]
        if len(roh) == 1 and roh[0].lower() == "standard":
            roh = prompt_katalog.standard_auswahl()

        erg = prompt_katalog.auswahl_setzen(db, roh)
        antwort = {
            "status": "gespeichert",
            "schnellzugriff": erg["uebernommen"],
            "anzahl": len(erg["uebernommen"]),
        }
        if erg["unbekannt"]:
            # Nicht still schlucken: eine erfundene Kennung waere sonst
            # ein Eintrag, der auf dem Dashboard einfach fehlt.
            antwort["unbekannt"] = erg["unbekannt"]
            antwort["hinweis"] = (
                "Diese Kennungen gibt es im Katalog nicht und wurden "
                "nicht uebernommen. schnellzugriff_setzen() ohne "
                "Argument zeigt die gueltigen.")
        if not erg["uebernommen"]:
            antwort["hinweis"] = (
                "Leere Auswahl — das Dashboard zeigt jetzt wieder die "
                "Voreinstellung. Mit schnellzugriff_setzen(prompts='...') "
                "eine eigene setzen.")
        return antwort

    @mcp.tool()
    def jobsuche_workflow_starten() -> dict:
        """Startet den geführten Jobsuche-Workflow: Suchkriterien prüfen, Quellen aktivieren,
        Suche starten, Ergebnisse sichten, Bewerbung vorbereiten.
        Dieser Workflow führt dich Schritt für Schritt durch den gesamten Prozess."""
        return workflow_starten(name="jobsuche_workflow")

    @mcp.tool()
    def ersterfassung_starten() -> dict:
        """Startet die Ersterfassung — ein lockeres Interview zur Profilerfassung,
        wie ein Kaffeegespräch. Kann jederzeit unterbrochen und später fortgesetzt werden."""
        # G59 (#1087 A2): die Rueckmeldung, auf die der Einstieg im
        # Dashboard wartet — "laeuft" steht erst da, wenn Claude das hier
        # wirklich aufgerufen hat, nicht schon beim Kopieren.
        profile_id = db.get_active_profile_id()
        if profile_id:
            key = f"profile_onboarding_conversation_{profile_id}"
            if db.get_user_preference(key) != "complete":
                db.set_user_preference(f"profile_onboarding_started_{profile_id}", True)
                db.set_user_preference(key, "active")
        return workflow_starten(name="ersterfassung")


def _prompt_registry(db):
    import functools
    from .. import prompts as _p
    """Erstellt ein Dict mit Prompt-Name → Callable für alle registrierten Prompts."""
    import json

    def _ersterfassung():
        return build_kennlerngespraech_prompt(db)


    def _bewerbung_schreiben(stelle: str = "", firma: str = "",
                             job_hash: str = "", bewerbung_id: str = "",
                             nur: str = ""):
        """Bewerbungsunterlagen zu einer konkreten Stelle (#981, D43).

        Vorher ohne Parameter — deshalb gab es keinen vorbefuellten Knopf
        an Stelle und Bewerbung, obwohl das Muster seit G16/#706 steht
        (`/api/workflow-prompt/{name}` reicht Query-Argumente nur durch,
        wenn die Signatur sie kennt). K11/#694 hatte die uebrigen Builder
        bereinigt, dieser blieb.

        `nur` ist 'lebenslauf', 'anschreiben' oder leer (beides bzw.
        nachfragen).
        """
        umfang = (nur or "").strip().lower()
        if umfang not in ("lebenslauf", "anschreiben"):
            umfang = ""
        hat_stelle = bool(stelle or firma or job_hash or bewerbung_id)

        zeilen = []
        if stelle:
            zeilen.append(f"  Stelle: {stelle}")
        if firma:
            zeilen.append(f"  Firma: {firma}")
        if job_hash:
            zeilen.append(f"  job_hash: {job_hash}")
        if bewerbung_id:
            zeilen.append(f"  bewerbung_id: {bewerbung_id}")
        if umfang:
            zeilen.append(f"  Umfang: nur {umfang}")
        kontext = ("\nKONTEXT (vorbefuellt):\n" + "\n".join(zeilen) + "\n"
                   if zeilen else "")

        if hat_stelle and umfang:
            schritt0 = ("SCHRITT 0 entfaellt — Stelle und Umfang stehen oben "
                        "im KONTEXT. NICHT nachfragen.")
        elif hat_stelle:
            schritt0 = """SCHRITT 0: UMFANG KLAEREN
Die Stelle steht oben im KONTEXT — dazu NICHT nachfragen.
Stelle EINE Frage: "Lebenslauf, Anschreiben oder beides?"
Hinweis dazu: ein Anschreiben lohnt sich, wenn die Stelle eines
verlangt oder der Nutzer eines moechte — der Lebenslauf fast immer."""
        else:
            schritt0 = """SCHRITT 0: KONTEXT KLAEREN
Es ist keine Stelle bekannt. OHNE konkrete Stelle werden KEINE
Unterlagen erstellt — ein Lebenslauf ohne Ziel ist kein angepasster
Lebenslauf.
  1. bewerbungen_anzeigen(status_filter="in_vorbereitung") und die
     Treffer zur Auswahl anbieten.
  2. Passt keine: nach Stelle und Firma fragen und im Bestand suchen
     (firma_kontext(firmenname), stellen_anzeigen).
  3. Dann EINE Frage zum Umfang: "Lebenslauf, Anschreiben oder beides?"
     Ein Anschreiben lohnt sich, wenn die Stelle eines verlangt oder
     der Nutzer eines moechte — der Lebenslauf fast immer."""

        lebenslauf = "" if umfang == "anschreiben" else """
SCHRITT 4: LEBENSLAUF
  → lebenslauf_bewerten(stelle, firma, stellenbeschreibung) — drei
    Perspektiven: Personalberater (Karriereverlauf, Soft Skills,
    Fuehrung), ATS (Keywords, Format, Metriken), Recruiter (fachliche
    Tiefe, Projekte, Werkzeuge). Gesamtscore und Top-Empfehlungen zeigen.
  → Fragen: "Schwerpunkt setzen?" — bei Aenderung erneut bewerten.
  → lebenslauf_angepasst_exportieren(stelle, firma, stellenbeschreibung),
    IMMER als DOCX. Zeigen, was angepasst wurde.
  → stilarchiv_speichern(kind="cv")"""

        anschreiben = "" if umfang == "lebenslauf" else """
SCHRITT 5: ANSCHREIBEN
  → Die relevantesten Erfahrungen und Projekte waehlen, max. eine Seite,
    professionell aber persoenlich.
  → Text zeigen — "Passt das so?"
  → Nach Freigabe: anschreiben_exportieren (DOCX)
  → stilarchiv_speichern(kind="cover_letter") + bewerbung_stil_tracken"""

        tracking = ("""
SCHRITT 6: TRACKING
  Die Bewerbung existiert bereits (bewerbung_id oben im KONTEXT):
  bewerbung_bearbeiten mit cv_path bzw. cover_letter_path (#448).
  KEINE neue Bewerbung anlegen — das gaebe eine Dublette.
  Danach fragen, ob der Status auf "beworben" gehen soll."""
            if bewerbung_id else """
SCHRITT 6: TRACKING
  Ist die Bewerbung schon erfasst? Wenn ja: bewerbung_bearbeiten mit
  cv_path bzw. cover_letter_path (#448), KEINE zweite anlegen.
  Wenn nein: bewerbung_erstellen — mit der Einstiegsfrage aus #170
  ("willst du dich bewerben" oder "hast du dich schon beworben").""")

        return f"""Erstelle Bewerbungsunterlagen: Lebenslauf und/oder Anschreiben,
immer zu einer konkreten Stelle.
{kontext}
{schritt0}

SCHRITT 1: PROFIL
  profil_zusammenfassung() + projekte_anzeigen() — die Zusammenfassung
  kuerzt die STAR-Texte, die vollen brauchst du (#741).

SCHRITT 2: STELLE
  → job_hash bekannt: die Anzeige aus dem Bestand holen (Volltext,
    C39/#952). Meldet sie beschreibung_kurz, biete
    stellenbeschreibung_nachladen an, bevor du schreibst.
  → bewerbung_id bekannt: bewerbung_details(); die verknuepfte Stelle
    nutzen.
  → nur Stelle und Firma: fragen, ob der Anzeigentext vorliegt.

SCHRITT 3: STIL
  stilarchiv_kontext(kind="cv"){' und kind="cover_letter"' if umfang != "lebenslauf" else ""} —
  fruehere Fassungen als Stilvorgabe (#577). Was schon einmal gut
  ankam, wird wiederverwendet statt neu erfunden.
{lebenslauf}{anschreiben}{tracking}

REGELN
- Ohne konkrete Stelle keine Unterlagen.
- Anschreiben nur, wenn gewuenscht oder gefordert.
- Immer DOCX, nie PDF — die finale Formatierung macht der Nutzer.
- Analyse VOR dem Export, damit der Nutzer noch reagieren kann.
- Sprich Deutsch."""


    # #560 / Beta-Stabilisierung: Diese statischen Prompts werden direkt aus
    # prompts.py geladen (modul-level build_*_prompt-Funktionen = Single Source
    # of Truth). Frueher lief das ueber FastMCP-Interna
    # (_mcp._prompt_manager._prompts) — das brach mit FastMCP 3.x lautlos
    # (AttributeError -> except: pass -> "Inhalt konnte nicht geladen werden"-Toast
    # im Frontend). Direkter Import ist versions-stabil und testbar.
    from ..prompts import (
        build_dokumente_verarbeiten_prompt,
        build_problem_melden_prompt,
        build_profil_sync_prompt,
        build_tipps_und_tricks_prompt,
    )

    def _dokumente_verarbeiten():
        return build_dokumente_verarbeiten_prompt(db)

    return {
        # v1.7.120: zum DRITTEN Mal fehlten Eintraege in dieser Liste
        # (nach #560 und den drei Karten aus v1.6.6). Der Knopf
        # "Dokumente verarbeiten" bekam ein 404 und kopierte den rohen
        # Schraegstrich-Befehl — den Claude Desktop als unbekannten Skill
        # liest. `problem_melden` fehlte ebenso, also ausgerechnet der
        # Weg, auf dem man so etwas meldet. Ein Guard haelt jetzt JEDEN
        # Katalogeintrag gegen diese Liste.
        "dokumente_verarbeiten": _dokumente_verarbeiten,
        "problem_melden": build_problem_melden_prompt,
        "ersterfassung": _ersterfassung,
        "jobsuche_workflow": functools.partial(_p.build_jobsuche_workflow_prompt, db),
        "willkommen": functools.partial(_p.build_willkommen_prompt, db),
        "bewerbungs_uebersicht": functools.partial(_p.build_bewerbungs_uebersicht_prompt, db),
        "profil_analyse": functools.partial(_p.build_profil_analyse_prompt, db),
        "profil_ueberpruefen": functools.partial(_p.build_profil_ueberpruefen_prompt, db),
        "bewerbung_schreiben": _bewerbung_schreiben,
        "interview_vorbereitung": functools.partial(_p.build_interview_vorbereitung_prompt, db),
        "interview_simulation": functools.partial(_p.build_interview_simulation_prompt, db),
        "gehaltsverhandlung": functools.partial(_p.build_gehaltsverhandlung_prompt, db),
        "netzwerk_strategie": functools.partial(_p.build_netzwerk_strategie_prompt, db),
        "profil_erweiterung": functools.partial(_p.build_profil_erweiterung_prompt, db),
        "ablehnungs_coaching": functools.partial(_p.build_ablehnungs_coaching_prompt, db),
        "auto_bewerbung": functools.partial(_p.build_auto_bewerbung_prompt, db),
        "bewerbung_vorbereitung": functools.partial(_p.build_bewerbung_vorbereitung_prompt, db),
        "faq": functools.partial(_p.build_faq_prompt, db),
        # v1.6.6 (#560): Diese drei waren bisher nicht im Frontend-Registry
        # — Klick auf die Karte produzierte einen Fehler-Toast.
        "tipps_und_tricks": build_tipps_und_tricks_prompt,
        "profil_sync": build_profil_sync_prompt,
    }
