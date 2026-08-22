"""Bewerbungs-Management — 16 Tools (#170: geführter Workflow, #443: Write-Back-Gaps)."""

from ..services.nutzerfuehrung import kein_profil, leer

import hashlib
import re


def _normalize_company_for_dedup(name: str) -> str:
    """Normalisiert Firmennamen fuer Duplikat-Erkennung (#531).

    Entfernt Klammerzusaetze (Vermittler/Endkunde-Hinweise), Rechtsform-
    Suffixe (GmbH/AG/SE/KG), Sonderzeichen — vergleicht so dass
    'Ingenieurvermittlung Mitte (Endkunde: Anlagenbau Sued)'
    und 'Anlagenbau Sued (via Ingenieurvermittlung Mitte GmbH)'
    als verwandt erkennbar werden.
    """
    if not name:
        return ""
    s = str(name).lower().strip()
    # Klammern komplett raus (Vermittler, Endkunde, via, Stadt)
    s = re.sub(r"\([^)]*\)", " ", s)
    # Rechtsform-Suffixe
    for suffix in (" gmbh", " ag", " se", " kg", " kgaa", " ohg", " gbr",
                   " e.k.", " ek", " ug", " mbh", " ltd", " inc", " corp"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    # Sonderzeichen / Doppel-Whitespace
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _normalize_title_for_dedup(title: str) -> str:
    """Normalisiert Stellentitel fuer Duplikat-Erkennung (#531).

    Entfernt Klammerzusaetze (m/w/d), Stadt-Suffixe wie '— Muelheim',
    Standard-Modifier wie '(Internal)' oder '(Senior)'.
    """
    if not title:
        return ""
    s = str(title).lower().strip()
    s = re.sub(r"\([^)]*\)", " ", s)
    # Em-dash + Stadt-Suffix
    s = re.sub(r"[—–-]\s*[\w\s]+$", "", s)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _company_tokens_full(name: str) -> set[str]:
    """Tokens aus dem GANZEN Firmennamen inkl. Klammerinhalt — fuer
    Vermittler/Endkunde-Erkennung. Filtert generische Begriffe."""
    if not name:
        return set()
    s = str(name).lower()
    # Sonderzeichen raus, aber Klammern UND Inhalt drin lassen
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    stop = {"gmbh", "ag", "se", "kg", "kgaa", "ohg", "gbr", "ek", "ug", "mbh",
            "ltd", "inc", "corp", "via", "endkunde", "kunde", "im", "auftrag",
            "von", "bei", "und", "the", "and", "of"}
    return {t for t in s.split() if len(t) >= 4 and t not in stop}


def _is_company_overlap(a: str, b: str) -> bool:
    """True wenn zwei normalisierte Firmennamen-Strings Tokens gemeinsam haben."""
    if not a or not b:
        return False
    if a == b:
        return True
    if a in b or b in a:
        return True
    tokens_a = {t for t in a.split() if len(t) >= 4}
    tokens_b = {t for t in b.split() if len(t) >= 4}
    overlap = tokens_a & tokens_b
    return len(overlap) >= 2


def _is_vermittler_endkunde_match(orig_a: str, orig_b: str) -> bool:
    """True wenn zwei Firmennamen die gleiche Vermittler/Endkunde-Beziehung
    beschreiben (z.B. 'IQ ... (Endkunde: Siemens)' vs 'Siemens (via IQ ...)').

    Vergleicht Tokens INKL. Klammerinhalt — wenn beide Strings mehrere
    seltene Tokens gemeinsam haben (>= 2), ist es vermutlich der gleiche
    Vorgang aus Vermittler- oder Endkunden-Sicht.
    """
    tok_a = _company_tokens_full(orig_a)
    tok_b = _company_tokens_full(orig_b)
    overlap = tok_a & tok_b
    return len(overlap) >= 2


def _normalize_date(value: str) -> str:
    """Normalisiert ein Datum auf YYYY-MM-DD (#529).

    Akzeptiert: YYYY-MM-DD, DD.MM.YYYY, ISO-Timestamps wie 2026-04-28T12:00:00.
    Liefert "" bei nicht-erkennbaren Eingaben (Caller meldet Fehler).
    """
    if not value:
        return ""
    s = str(value).strip()
    # ISO-Timestamp -> Datum nehmen
    if "T" in s:
        s = s.split("T", 1)[0]
    # YYYY-MM-DD direkt
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    # DD.MM.YYYY
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", s)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return ""


def _nachfass_template(app: dict) -> str:
    """v1.7.12 (#816, D34): fallbezogener Inhalt fuer Auto-Nachfassungen.

    v1.7.23 (#945): Der Baustein liegt jetzt in
    `services/nachfass_text.py`, weil er an VIER Anlagestellen gebraucht
    wird und nur an zwei benutzt wurde — die automatisch beim
    Statuswechsel erzeugten Eintraege blieben deshalb leer.
    """
    from ..services.nachfass_text import nachfass_text
    return nachfass_text(app)


# Status-zu-Aktionen Mapping (#170): Kontextabhängige Aktionen pro Status
# Jeder Status zeigt dem User genau die Aktionen die JETZT relevant sind.
STATUS_ACTIONS = {
    "in_vorbereitung": {
        "beschreibung": "Du bereitest dich auf diese Bewerbung vor. Hier sind deine nächsten Schritte:",
        "aktionen": [
            {"label": "Fit-Analyse durchführen", "tool": "fit_analyse", "prioritaet": 1},
            {"label": "Skill-Gap-Analyse", "tool": "skill_gap_analyse", "prioritaet": 2},
            {"label": "Lebenslauf anpassen", "tool": "lebenslauf_angepasst_exportieren", "prioritaet": 3},
            {"label": "Lebenslauf bewerten lassen", "tool": "lebenslauf_bewerten", "prioritaet": 4},
            {"label": "Anschreiben erstellen", "tool": "anschreiben_exportieren", "prioritaet": 5},
            {"label": "Firmen-Recherche", "tool": "firmen_recherche", "prioritaet": 6},
            {"label": "Dokument verknüpfen", "tool": "dokument_verknüpfen", "prioritaet": 7},
            {"label": "Als 'beworben' markieren", "tool": "bewerbung_status_aendern", "status": "beworben", "prioritaet": 8},
        ],
        "motivation": "Gute Vorbereitung ist der halbe Erfolg! Nimm dir die Zeit.",
    },
    "beworben": {
        "beschreibung": "Bewerbung ist raus! Nutze die Wartezeit um dich auf ein mögliches Interview vorzubereiten.",
        "aktionen": [
            {"label": "Interview-Vorbereitung starten", "tool": "workflow_starten", "workflow": "interview_vorbereitung", "prioritaet": 1},
            {"label": "Interview-Simulation", "tool": "workflow_starten", "workflow": "interview_simulation", "prioritaet": 2},
            {"label": "Firmen-Recherche", "tool": "firmen_recherche", "prioritaet": 3},
            {"label": "Nachfass-Erinnerung planen", "tool": "nachfass_planen", "prioritaet": 4},
            {"label": "Notiz hinzufügen", "tool": "bewerbung_notiz", "prioritaet": 5},
            {"label": "Eingangsbestätigung erhalten", "tool": "bewerbung_status_aendern", "status": "eingangsbestaetigung", "prioritaet": 6},
            {"label": "Absage erhalten", "tool": "bewerbung_status_aendern", "status": "abgelehnt", "prioritaet": 9},
        ],
        "motivation": "Du hast den wichtigsten Schritt gemacht! Bereite dich jetzt schon aufs Interview vor — wer vorbereitet ist, überzeugt.",
    },
    "eingangsbestaetigung": {
        "beschreibung": "Die Firma hat deine Bewerbung erhalten. Bereite dich auf ein mögliches Interview vor!",
        "aktionen": [
            {"label": "Interview-Vorbereitung starten", "tool": "workflow_starten", "workflow": "interview_vorbereitung", "prioritaet": 1},
            {"label": "Interview-Simulation", "tool": "workflow_starten", "workflow": "interview_simulation", "prioritaet": 2},
            {"label": "Firmen-Recherche", "tool": "firmen_recherche", "prioritaet": 3},
            {"label": "Nachfass-Erinnerung planen", "tool": "nachfass_planen", "prioritaet": 4},
            {"label": "Interview-Termin erhalten", "tool": "bewerbung_status_aendern", "status": "interview", "prioritaet": 5},
            {"label": "Absage erhalten", "tool": "bewerbung_status_aendern", "status": "abgelehnt", "prioritaet": 9},
        ],
        "motivation": "Positive Zeichen! Nutze die Wartezeit für die Vorbereitung.",
    },
    "interview": {
        "beschreibung": "Du hattest ein Interview! Dokumentiere deine Eindrücke und Erkenntnisse solange sie frisch sind.",
        "aktionen": [
            {"label": "Gesprächsnotizen erfassen", "tool": "bewerbung_notiz", "prioritaet": 1},
            {"label": "Gehaltsverhandlung vorbereiten", "tool": "workflow_starten", "workflow": "gehaltsverhandlung", "prioritaet": 2},
            {"label": "Nachfass-Erinnerung planen", "tool": "nachfass_planen", "prioritaet": 3},
            {"label": "Notiz hinzufügen", "tool": "bewerbung_notiz", "prioritaet": 4},
            {"label": "Zweitgespräch erhalten", "tool": "bewerbung_status_aendern", "status": "zweitgespraech", "prioritaet": 5},
            {"label": "Interview abgeschlossen", "tool": "bewerbung_status_aendern", "status": "interview_abgeschlossen", "prioritaet": 6},
            {"label": "Absage erhalten", "tool": "bewerbung_status_aendern", "status": "abgelehnt", "prioritaet": 9},
        ],
        "motivation": "Super, ein Interview geschafft! Halte fest was gut lief und was du beim nächsten Mal anders machen würdest.",
    },
    "zweitgespraech": {
        "beschreibung": "Du bist in der engeren Auswahl! Die Firma interessiert sich für dich.",
        "aktionen": [
            {"label": "Interview-Simulation (vertieft)", "tool": "workflow_starten", "workflow": "interview_simulation", "prioritaet": 1},
            {"label": "Gehaltsverhandlung vorbereiten", "tool": "workflow_starten", "workflow": "gehaltsverhandlung", "prioritaet": 2},
            {"label": "Gesprächsnotizen erfassen", "tool": "bewerbung_notiz", "prioritaet": 3},
            {"label": "Interview abgeschlossen", "tool": "bewerbung_status_aendern", "status": "interview_abgeschlossen", "prioritaet": 4},
            {"label": "Absage erhalten", "tool": "bewerbung_status_aendern", "status": "abgelehnt", "prioritaet": 9},
        ],
        "motivation": "Die Firma investiert Zeit in dich — ein sehr gutes Zeichen!",
    },
    "interview_abgeschlossen": {
        "beschreibung": "Die Gespräche sind abgeschlossen. Jetzt heißt es warten — oder proaktiv nachhaken.",
        "aktionen": [
            {"label": "Gehaltsverhandlung vorbereiten", "tool": "workflow_starten", "workflow": "gehaltsverhandlung", "prioritaet": 1},
            {"label": "Nachfass-Erinnerung planen", "tool": "nachfass_planen", "prioritaet": 2},
            {"label": "Gesprächsnotizen ergänzen", "tool": "bewerbung_notiz", "prioritaet": 3},
            {"label": "Angebot erhalten", "tool": "bewerbung_status_aendern", "status": "angebot", "prioritaet": 4},
            {"label": "Absage erhalten", "tool": "bewerbung_status_aendern", "status": "abgelehnt", "prioritaet": 9},
        ],
        "motivation": "Du hast alles gegeben! Nutze die Wartezeit um dich auf eine Gehaltsverhandlung vorzubereiten.",
    },
    "angebot": {
        "beschreibung": "Glückwunsch, du hast ein Angebot! Jetzt heißt es klug verhandeln.",
        "aktionen": [
            {"label": "Gehaltsverhandlung durchführen", "tool": "workflow_starten", "workflow": "gehaltsverhandlung", "prioritaet": 1},
            {"label": "Vertragsdetails notieren", "tool": "bewerbung_notiz", "prioritaet": 2},
            {"label": "Angebot annehmen", "tool": "bewerbung_status_aendern", "status": "angenommen", "prioritaet": 3},
            {"label": "Angebot ablehnen / zurückziehen", "tool": "bewerbung_status_aendern", "status": "zurueckgezogen", "prioritaet": 9},
        ],
        "motivation": "Fantastisch! Du hast es geschafft. Nimm dir Zeit für die Entscheidung.",
    },
    "abgelehnt": {
        "beschreibung": "Eine Absage ist hart, aber jede bringt dich näher ans Ziel.",
        "aktionen": [
            {"label": "Ablehnungsmuster analysieren", "tool": "ablehnungs_muster", "prioritaet": 1},
            {"label": "Rückfrage an Firma formulieren", "tool": "antwort_formulieren", "prioritaet": 2},
            {"label": "Ähnliche Stellen suchen", "tool": "stellen_anzeigen", "prioritaet": 3},
            {"label": "Neue Jobsuche starten", "tool": "jobsuche_starten", "prioritaet": 4},
        ],
        "motivation": "Kopf hoch! Absagen gehören dazu. Schau was du daraus lernen kannst.",
    },
    "offen": {
        "beschreibung": "Diese Bewerbung ist offen. Was möchtest du als nächstes tun?",
        "aktionen": [
            {"label": "Bewerbung vorbereiten", "tool": "bewerbung_status_aendern", "status": "in_vorbereitung", "prioritaet": 1},
            {"label": "Als beworben markieren", "tool": "bewerbung_status_aendern", "status": "beworben", "prioritaet": 2},
            {"label": "Notiz hinzufügen", "tool": "bewerbung_notiz", "prioritaet": 3},
        ],
        "motivation": "Los geht's! Der erste Schritt ist immer der wichtigste.",
    },
    "angenommen": {
        "beschreibung": "Glückwunsch, du hast den Job! Jetzt runden wir den Vorgang sauber ab.",
        "aktionen": [
            {"label": "Neue Position ins Profil übernehmen", "tool": "position_aus_bewerbung_uebernehmen", "prioritaet": 1},
            {"label": "Tatsächliches Gehalt eintragen", "tool": "bewerbung_bearbeiten", "prioritaet": 2},
            {"label": "Offene Bewerbungen archivieren / zurückziehen", "tool": "bewerbungen_anzeigen", "prioritaet": 3},
            {"label": "Abschluss-Notiz festhalten", "tool": "bewerbung_notiz", "prioritaet": 4},
        ],
        "motivation": "Respekt — du hast den Weg bis zum Ziel durchgezogen. Zeit, die Früchte einzusammeln.",
    },
    "zurueckgezogen": {
        "beschreibung": "Du hast diese Bewerbung zurückgezogen. Damit ist sie sauber geschlossen.",
        "aktionen": [
            {"label": "Grund als Notiz festhalten", "tool": "bewerbung_notiz", "prioritaet": 1},
            {"label": "Ähnliche Stellen ansehen", "tool": "stellen_anzeigen", "prioritaet": 2},
            {"label": "Neue Jobsuche starten", "tool": "jobsuche_starten", "prioritaet": 3},
        ],
        "motivation": "Bewusst nein zu sagen ist auch eine Entscheidung — sie schafft Platz für das Richtige.",
    },
}


def _get_context_actions(status: str) -> dict:
    """Gibt kontextabhängige Aktionen für einen Bewerbungsstatus zurück (#170)."""
    default = {
        "beschreibung": "Aktionen verfügbar:",
        "aktionen": [
            {"label": "Notiz hinzufügen", "tool": "bewerbung_notiz"},
            {"label": "Status ändern", "tool": "bewerbung_status_aendern"},
        ],
    }
    return STATUS_ACTIONS.get(status, default)


def _firma_normalisieren(name: str) -> str:
    """H18 (#753): Firmen-String fuer den Vergleich normalisieren —
    Rechtsformen und Fuellwoerter raus, Umlaute vereinheitlicht, lower."""
    s = (name or "").lower().strip()
    for uml, repl in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(uml, repl)
    for stop in (" gmbh & co. kg", " gmbh & co kg", " se & co. kg", " gmbh",
                 " ag", " se", " kg", " ohg", " inc", " inc.", " ltd",
                 " limited", " holding", " group", " germany", " deutschland"):
        s = s.replace(stop, " ")
    return " ".join(s.split())


def _firma_matcht(company: str, query_norm: str) -> bool:
    """True wenn der normalisierte Firmen-String zum Such-String passt
    (Substring in beide Richtungen — 'Acme' matcht
    'Acme Solutions GmbH')."""
    comp_norm = _firma_normalisieren(company)
    if not comp_norm or not query_norm:
        return False
    return query_norm in comp_norm or comp_norm in query_norm


def register(mcp, db, logger):
    """Registriert Bewerbungs-Tools."""
    from . import time_tool

    @mcp.tool()
    def firma_kontext(firmenname: str) -> dict:
        """Kompletter dokumentierter Stand zu einer Firma in EINEM Aufruf (#753, H18).

        ⛔ PFLICHT-LOOKUP: Sobald ein Firmenname mit einer WERTUNG faellt
        ("kenne ich", "war abgesagt", "laeuft noch", "da hatte ich ein
        Interview", auch beilaeufig in einem Fallback-Vorschlag), rufe
        ZUERST dieses Tool auf und antworte NUR auf Basis des Ergebnisses.
        Nie Firmen-Status, Interview-Verlauf oder Absagen aus dem
        Gedaechtnis behaupten — PBP haelt die dokumentierte Wahrheit.

        Liefert: alle Bewerbungen (Titel, Status, Datum, Termine), aktive
        Stellen, Aussortier-Historie mit Gruenden — die Basis fuer jede
        Aussage ueber die Firma.

        Args:
            firmenname: Name der Firma (Teilstring reicht — 'Acme'
                findet 'Acme Solutions GmbH').
        """
        query_norm = _firma_normalisieren(firmenname)
        if not query_norm:
            return {"fehler": "firmenname ist Pflicht."}

        bewerbungen = []
        for app in db.get_applications():
            if not _firma_matcht(app.get("company", ""), query_norm):
                continue
            eintrag = {
                "bewerbung_id": (app.get("id") or "")[:8],
                "titel": app.get("title"),
                "firma": app.get("company"),
                "status": app.get("status"),
                "beworben_am": app.get("applied_at"),
            }
            try:
                meetings = db.get_meetings_for_application(app.get("id"))
                if meetings:
                    eintrag["termine"] = [
                        {"titel": m.get("title"), "datum": m.get("meeting_date"),
                         "typ": m.get("meeting_type")}
                        for m in meetings[:5]
                    ]
            except Exception:
                pass
            bewerbungen.append(eintrag)

        # v1.7.10 (#782/C30): Repost-Verdacht direkt am aktiven Treffer —
        # der Praxis-Fall war genau hier: aktive Stelle, auf die vor
        # 10 Monaten schon beworben wurde, ohne dass es jemand sah.
        from ..duplicate_detection import find_repost_of_application
        _apps_fuer_repost = db.get_applications()
        aktive_stellen = []
        for j in db.get_active_jobs():
            if not _firma_matcht(j.get("company", ""), query_norm):
                continue
            eintrag_st = {"hash": j.get("hash"), "titel": j.get("title"),
                          "score": j.get("score")}
            try:
                _rp = find_repost_of_application(j, _apps_fuer_repost)
                if _rp:
                    eintrag_st["repost_warnung"] = _rp["warnung"]
            except Exception:
                pass
            aktive_stellen.append(eintrag_st)
            if len(aktive_stellen) >= 15:
                break

        aussortiert = [
            j for j in (db.get_dismissed_jobs() or [])
            if _firma_matcht(j.get("company", ""), query_norm)
        ]
        gruende: dict = {}
        for j in aussortiert:
            grund = j.get("dismiss_reason") or "unbekannt"
            gruende[grund] = gruende.get(grund, 0) + 1
        aussortiert_beispiele = [
            {"titel": j.get("title"), "grund": j.get("dismiss_reason")}
            for j in aussortiert[:8]
        ]

        gefunden = bool(bewerbungen or aktive_stellen or aussortiert)
        return {
            "firma_suchbegriff": firmenname,
            "gefunden": gefunden,
            "bewerbungen": bewerbungen,
            "aktive_stellen": aktive_stellen,
            "aussortiert_anzahl": len(aussortiert),
            "aussortiert_gruende": gruende,
            "aussortiert_beispiele": aussortiert_beispiele,
            "hinweis": (
                "WICHTIG (#757): Aussortier-Gruende gelten je STELLE, nicht "
                "fuer die Firma insgesamt — dieselbe Firma kann passende und "
                "unpassende Rollen ausschreiben. Andere Schreibweisen der "
                "Firma (z.B. Abkuerzung vs. voller Name) ggf. separat "
                "nachschlagen."
            ) if gefunden else (
                "Kein dokumentierter Kontakt mit dieser Firma in PBP — weder "
                "Bewerbungen noch Stellen. Wenn du (Claude) etwas anderes "
                "'weisst', stammt es NICHT aus PBP und gehoert nicht in eine "
                "Status-Aussage. Auch alternative Schreibweisen pruefen."
            ),
        }

    @mcp.tool()
    @time_tool(logger, "bewerbung_event_datum_setzen")
    def bewerbung_event_datum_setzen(
        event_id: int,
        neues_datum: str,
        bewerbung_id: str = "",
    ) -> dict:
        """v1.7.0-beta.60 (#631): Korrigiert das Datum eines Status-Wechsel-Events.

        Use Case: User hat den Status erst spaeter eingetragen als die
        eigentliche Aenderung passiert ist (z.B. heute 'abgelehnt' geklickt,
        aber Absage kam am 2026-04-15). Mit diesem Tool laesst sich das
        Event-Datum nachtraeglich korrigieren — Statistik (Reaktionszeit etc)
        wird damit korrekt.

        Args:
            event_id: ID des Events (siehe `bewerbung_details` -> events)
            neues_datum: YYYY-MM-DD oder DD.MM.YYYY oder ISO-Timestamp
            bewerbung_id: Optional — Cross-Profile-Schutz (wenn gesetzt, muss
                der Event zur angegebenen Bewerbung gehoeren)
        """
        result = db.update_application_event_date(
            event_id=event_id,
            new_date=neues_datum,
            app_id=(bewerbung_id or None),
        )
        return result

    @mcp.tool()
    @time_tool(logger, "bewerbung_erstellen")
    def bewerbung_erstellen(
        title: str,
        company: str,
        url: str = "",
        job_hash: str = "",
        status: str = "beworben",
        applied_at: str = "",
        notes: str = "",
        bewerbungsart: str = "mit_dokumenten",
        lebenslauf_variante: str = "standard",
        ansprechpartner: str = "",
        kontakt_email: str = "",
        portal_name: str = "",
        bereits_beworben: bool = True,
        stellenbeschreibung: str = "",
        endkunde: str = "",
        force: bool = False
    ) -> dict:
        """Erstellt eine neue Bewerbung (manuell oder aus einer gefundenen Stelle).

        EINSTIEGSFRAGE (#170): Frage den User zuerst:
        "Hast du dich bereits beworben, oder möchtest du dich bewerben?"
        - Bereits beworben (bereits_beworben=True): Status 'beworben', Datum erfassen
        - Will mich bewerben (bereits_beworben=False): Status 'in_vorbereitung',
          direkt in Bewerbungsdetails mit nächsten Schritten

        Args:
            title: Stellentitel
            company: Firmenname
            url: Link zur Stellenanzeige
            job_hash: Optional: Hash einer gefundenen Stelle
            status: in_vorbereitung, offen, beworben, eingangsbestaetigung, interview, zweitgespraech, interview_abgeschlossen, angebot, angenommen, abgelehnt, zurueckgezogen, abgelaufen
            applied_at: Bewerbungsdatum (YYYY-MM-DD, Standard: heute)
            notes: Notizen
            bewerbungsart: mit_dokumenten, elektronisch, ueber_portal
            lebenslauf_variante: standard, angepasst, keiner
            ansprechpartner: Name des Ansprechpartners
            kontakt_email: E-Mail des Ansprechpartners
            portal_name: Name des Portals (bei bewerbungsart=ueber_portal)
            bereits_beworben: True = schon beworben (Standard), False = will mich bewerben (#170)
            stellenbeschreibung: Optional: Vollständige Stellenbeschreibung (#172) — wird automatisch gespeichert
            endkunde: Optional (#710): Endkunde bei Vermittler-Engagements
                (company = Vermittler). Bei gesetztem Endkunden vergleicht die
                Duplikat-Erkennung company+endkunde statt nur company+title —
                mehrere Engagements ueber denselben Vermittler sind dann
                getrennt erfassbar.
            force: True ueberstimmt die Duplikat-Erkennung bewusst (#709) —
                nutzen wenn es wirklich eine eigene, neue Bewerbung ist.
        """
        # #170: Wenn der User sich noch nicht beworben hat → in_vorbereitung
        # #506: Aber NUR, wenn der Aufrufer keinen expliziten Status gesetzt hat.
        if not bereits_beworben and status == "beworben":
            status = "in_vorbereitung"

        # v1.7.0-beta.20: Schutzgitter gegen Recruiter-Anfragen-Missbrauch.
        # Vorher gab es einen Workaround: bewerbung_erstellen(bereits_beworben=False,
        # status="zurueckgezogen") fuer Inbound-Anfragen, die nie eine Bewerbung waren.
        # Das verfaelscht die Statistik (Quoten zaehlen das als "submitted").
        # Jetzt: blockieren mit Hinweis auf das richtige Tool.
        if not bereits_beworben and status in ("zurueckgezogen", "abgelehnt"):
            return {
                "fehler": (
                    "Eine Inbound-Ablehnung gehoert nicht in die Bewerbungs-Tabelle. "
                    "Sie wuerde deine Bewerbungs-Statistik verfaelschen "
                    "(Quoten zaehlen sie als 'submitted')."
                ),
                "vorschlag_tool": "recruiter_anfrage_ablehnen",
                "vorschlag_aufruf": (
                    f"recruiter_anfrage_ablehnen(firma=\"{company}\", "
                    f"titel=\"{title}\", grund=\"<dein-grund>\")"
                ),
                "begruendung": (
                    "Bei Recruiter-Anfragen ohne Bewerbung wird KEIN "
                    "applications-Eintrag angelegt. Stattdessen wird die "
                    "Stelle in der jobs-Tabelle als ausgemustert markiert "
                    "(is_active=0 mit dismiss_reason). Dadurch bleibt die "
                    "Markt-Beobachtung erhalten ohne deine Track-Record-"
                    "Statistik zu verfaelschen."
                ),
            }

        # Check for duplicate applications (#63 / #531 v1.6.4)
        # v1.6.4: Erweitert um fuzzy-match (Vermittler/Endkunde-Beziehungen
        # und Stadt-/Internal-Suffixe). Vorher exakt company.lower() ==
        # company.lower() — verfehlt z.B. "IQ ... (Endkunde: Siemens)" vs
        # "Siemens (via IQ ...)". Plus Email-/Ansprechpartner-Match als
        # zusaetzliches Signal.
        # #709: force=True ueberspringt das Dedup-Gate bewusst (der frueher
        # in der Fehlermeldung versprochene notes-Override war nie
        # implementiert — jetzt gibt es den expliziten Parameter).
        existing_apps = [] if force else db.get_applications()
        norm_company = _normalize_company_for_dedup(company)
        norm_title = _normalize_title_for_dedup(title)
        norm_email = (kontakt_email or "").lower().strip()
        norm_ansprech = (ansprechpartner or "").lower().strip()
        norm_endkunde = (endkunde or "").lower().strip()

        for existing in existing_apps:
            # #710: Verschiedene Endkunden beim selben Vermittler sind
            # KEINE Duplikate — getrennte Engagements.
            ex_endkunde = (existing.get("endkunde") or "").lower().strip()
            if norm_endkunde and ex_endkunde and norm_endkunde != ex_endkunde:
                continue
            ex_company = existing.get("company", "")
            ex_title = existing.get("title", "")
            ex_email = (existing.get("kontakt_email") or "").lower().strip()
            ex_ansprech = (existing.get("ansprechpartner") or "").lower().strip()

            # 1) Exakt-Match (alte Logik)
            if ex_company.lower() == company.lower() and ex_title.lower() == title.lower():
                return {
                    "status": "duplikat",
                    "match_typ": "exakt",
                    "bestehende_bewerbung_id": existing["id"][:8],
                    "nachricht": f"Es gibt bereits eine Bewerbung bei {company} für '{title}' "
                                 f"(Status: {existing.get('status', '?')}). "
                                 "Nutze bewerbung_bearbeiten() um diese zu aktualisieren — "
                                 "oder force=True, wenn es wirklich eine neue, eigene Bewerbung ist."
                }

            # 2) Fuzzy-Match: aehnliche Firma + aehnlicher Titel
            ex_norm_company = _normalize_company_for_dedup(ex_company)
            ex_norm_title = _normalize_title_for_dedup(ex_title)
            # Variante a: nach Klammer-Strip (gleiche Firma in zwei Schreibweisen)
            company_match_clean = _is_company_overlap(norm_company, ex_norm_company)
            # Variante b: Vermittler/Endkunde-Beziehung (z.B. "X (via Y)" vs "Y (Endkunde: X)")
            company_match_vermittler = _is_vermittler_endkunde_match(company, ex_company)
            company_match = company_match_clean or company_match_vermittler
            title_match = (norm_title == ex_norm_title) or (
                norm_title and ex_norm_title and (
                    norm_title in ex_norm_title or ex_norm_title in norm_title
                )
            )
            if company_match and title_match:
                return {
                    "status": "duplikat",
                    "match_typ": "fuzzy_firma_titel",
                    "bestehende_bewerbung_id": existing["id"][:8],
                    "bestehend_firma": ex_company,
                    "bestehend_titel": ex_title,
                    "nachricht": (
                        f"Aehnliche Bewerbung gefunden: '{ex_title}' bei {ex_company} "
                        f"(Status: {existing.get('status', '?')}). "
                        f"Vermutlich Vermittler/Endkunde-Beziehung oder Titelvariante. "
                        f"Falls neue Bewerbung trotzdem gewuenscht: force=True setzen — "
                        f"bei Vermittler-Engagements zusaetzlich endkunde='...' angeben, "
                        f"dann unterscheidet die Duplikat-Erkennung kuenftig selbst."
                    )
                }

            # 3) Email- oder Ansprechpartner-Match plus aehnlicher Titel
            #    (sehr starkes Signal — gleicher Recruiter zur gleichen Stelle)
            if title_match and (
                (norm_email and ex_email and norm_email == ex_email) or
                (norm_ansprech and ex_ansprech and norm_ansprech == ex_ansprech)
            ):
                return {
                    "status": "duplikat",
                    "match_typ": "email_oder_ansprechpartner",
                    "bestehende_bewerbung_id": existing["id"][:8],
                    "bestehend_firma": ex_company,
                    "bestehend_titel": ex_title,
                    "nachricht": (
                        f"Identischer Ansprechpartner/Email + aehnlicher Titel: "
                        f"'{ex_title}' bei {ex_company} (Status: {existing.get('status', '?')}). "
                        f"Sehr wahrscheinlich Duplikat. Falls doch eigenstaendig: force=True."
                    )
                }

        # If no job_hash given, create a manual job entry so it appears in stellen_anzeigen
        effective_hash = job_hash or None
        if not effective_hash:
            effective_hash = hashlib.md5(f"manuell:{company}:{title}:{url}".encode()).hexdigest()[:12]
            # Check if job already exists
            existing = db.get_job(effective_hash)
            if not existing:
                from datetime import datetime
                # v1.7.0-beta.32 (#588): KEIN notes-Fallback mehr fuer
                # description. Wenn der Aufrufer die Stellenbeschreibung
                # nicht gibt, bleibt das Feld leer — sonst landen Notizen
                # ("Vermittler ist X, Endkunde-Kandidaten sind Y") als
                # Stellenbeschreibung in der DB und verschmutzen alle
                # downstream-Tools (fit_analyse, Anschreiben).
                # v1.7.0-beta.47 (#613): URL-basierte Source-Detection
                # statt hartkodiert 'manuell' — wenn die URL klar auf
                # LinkedIn/StepStone/etc. zeigt, wird das gespeichert.
                # Sonst Fallback 'manuell'.
                from ..services.url_to_source import detect_source_from_url
                detected_source = detect_source_from_url(url)
                db.save_jobs([{
                    "hash": effective_hash,
                    "title": title,
                    "company": company,
                    "location": "",
                    "url": url,
                    "source": detected_source,
                    "description": stellenbeschreibung or "",
                    "score": 0,
                    "is_pinned": True,
                    "remote_level": "unbekannt",
                    "employment_type": "festanstellung",
                    "found_at": datetime.now().isoformat(),
                }])

        # #178 Bug 1: source aus jobs-Tabelle übernehmen
        source = ""
        if effective_hash:
            linked_job = db.get_job(effective_hash)
            if linked_job:
                source = linked_job.get("source", "") or ""

        # v1.7.0-beta.32 (#588): description_snapshot ist der read-mostly
        # Originalwortlaut der Stellenanzeige — explizit getrennt von
        # `notes` (mutable, eigene Recherche). Bei Anlage einer Bewerbung
        # snapshot wir den Job-Text falls vorhanden, sonst die explizit
        # uebergebene stellenbeschreibung.
        snapshot_text = stellenbeschreibung or ""
        if effective_hash and not snapshot_text:
            try:
                _job = db.get_job(effective_hash) or {}
                snapshot_text = _job.get("description") or ""
            except Exception:
                snapshot_text = ""
        from datetime import datetime as _dt_snap

        # v1.7.0-beta.46 (#602): applied_at-Default. Inbound-Recruiter-
        # Anfragen kamen vorher ohne applied_at rein -> 14 verwaiste
        # Eintraege im Bericht. Default = heute (oder created_at als
        # Fallback bei status='in_vorbereitung').
        if status != "in_vorbereitung" and not applied_at:
            applied_at = _dt_snap.now().isoformat()[:10]

        aid = db.add_application({
            "title": title, "company": company, "url": url,
            "job_hash": effective_hash, "status": status,
            "applied_at": applied_at if status != "in_vorbereitung" else "",
            "notes": notes,
            "bewerbungsart": bewerbungsart,
            "lebenslauf_variante": lebenslauf_variante,
            "ansprechpartner": ansprechpartner,
            "kontakt_email": kontakt_email,
            "portal_name": portal_name,
            "source": source,
            "description_snapshot": snapshot_text,
            "snapshot_date": _dt_snap.now().isoformat() if snapshot_text else "",
            "endkunde": endkunde,
        })

        # #231: Stelle als inaktiv markieren wenn Bewerbung erstellt
        if effective_hash:
            try:
                db.dismiss_job(effective_hash, reason="bewerbung_erstellt")
            except Exception:
                pass  # Job existiert evtl. nicht

        # v1.7.0-beta.40 (#609): Elwosa-Hook bei neuer Bewerbung
        try:
            from ..services import elwosa as _elwosa
            _elwosa.speak(db, "bewerbung_angelegt", ctx={
                "firma": company,
                "ref": aid,
            })
        except Exception:
            pass

        # #224: Notiz als ersten Timeline-Eintrag speichern
        if notes:
            from datetime import datetime as dt_now
            conn = db.connect()
            conn.execute(
                "INSERT INTO application_events (application_id, status, event_date, notes) VALUES (?, 'notiz', ?, ?)",
                (aid, dt_now.now().isoformat(), notes)
            )
            conn.commit()

        # #462: Auto-Follow-up direkt beim Anlegen einer beworbenen Bewerbung
        auto_followup_id = None
        if status == "beworben":
            try:
                default_days = int(db.get_setting("followup_default_days", 7) or 7)
            except Exception:
                default_days = 7
            if default_days > 0:
                from datetime import datetime as dt_auto, timedelta as td_auto
                when = (dt_auto.now() + td_auto(days=default_days)).date().isoformat()
                try:
                    # #816: nie mehr als leerer Reminder anlegen
                    _app_fuer_tpl = db.get_application(aid) or {}
                    auto_followup_id = db.add_follow_up(
                        aid, when, "nachfass",
                        template=_nachfass_template(_app_fuer_tpl))
                except Exception:
                    auto_followup_id = None

        result = {
            "status": "erstellt",
            "bewerbung_id": aid[:8],
            "bewerbung_id_voll": aid,
            "job_hash": effective_hash[:8] if effective_hash else None,
            "bewerbungsstatus": status,
            "nachricht": f"Bewerbung bei {company} für '{title}' erfasst.",
        }
        if auto_followup_id:
            result["auto_follow_up"] = {"id": auto_followup_id, "tage": default_days}

        # #766: Anker-Pruefung am Uebergang Stelle -> Bewerbung. Die eigentliche
        # Gefahr ist nicht die fehlende URL, sondern dass Anschreiben und CV
        # gegen eine Zusammenfassung optimiert werden statt gegen die echte
        # Ausschreibung — ohne dass jemand die Anzeige je gesehen hat.
        # Bewusst KEIN Block: die Bewerbung ist bereits erfasst, das Verwerfen
        # der Eingaben waere schlimmer als der fehlende Anker.
        try:
            from ..services.stellen_anker import anker_status
            _job_fuer_anker = db.get_job(effective_hash) if effective_hash else None
            if _job_fuer_anker:
                _anker = anker_status(db, _job_fuer_anker)
                # Ansprechpartner auf Bewerbungsebene zaehlt als Kontakt-Anker
                # (bei Vermittler-Stellen oft das Einzige, was es gibt).
                if not _anker["hat_anker"] and (ansprechpartner or kontakt_email):
                    _anker = {"hat_anker": True, "anker": ["kontakt"],
                              "url_art": _anker["url_art"]}
                result["anker"] = _anker["anker"]
                if not _anker["hat_anker"]:
                    result["anker_warnung"] = (
                        "Zu dieser Bewerbung gibt es KEINE nachvollziehbare "
                        "Ausschreibung (weder Detail-URL noch Dokument noch "
                        "Ansprechpartner)."
                        + (" Die hinterlegte URL ist eine Suchergebnis-Seite."
                           if _anker["url_art"] == "suche" else "")
                        + " Unterlagen jetzt zu erstellen hiesse, sie gegen "
                        "eine Zusammenfassung zu optimieren statt gegen die "
                        "echten Anforderungen."
                    )
                    result["anker_naechster_schritt"] = (
                        "ZUERST die Anzeige beschaffen: Original-Link per "
                        f"stelle_bearbeiten('{effective_hash[:8]}', url=...) "
                        "nachtragen und stellenbeschreibung_nachladen() "
                        "aufrufen, oder die Anzeige als Dokument hochladen, "
                        "oder den Ansprechpartner per bewerbung_bearbeiten() "
                        "erfassen. Dann pruefen, ob die Stelle noch aktiv ist "
                        "— erst danach Anschreiben und Lebenslauf."
                    )
        except Exception:
            pass  # Anker-Pruefung darf das Anlegen nie kippen

        # #170: Bei in_vorbereitung direkt die nächsten Schritte zeigen
        if status == "in_vorbereitung":
            result["nächste_schritte"] = _get_context_actions("in_vorbereitung")
            result["nachricht"] += (
                " Status: in_vorbereitung — Nutze bewerbung_details() um die "
                "Bewerbung zu öffnen und die Vorbereitung zu starten."
            )
        else:
            result["nachricht"] += f" ({bewerbungsart})"

        return result

    @mcp.tool()
    @time_tool(logger, "bewerbung_status_aendern")
    def bewerbung_status_aendern(
        bewerbung_id: str,
        neuer_status: str,
        notizen: str = "",
        ablehnungsgrund: str = "",
        auto_follow_up: bool = True,
    ) -> dict:
        """Ändert den Status einer Bewerbung (Bewerbungsstatus ändern/aktualisieren).

        Auch findbar als: status ändern, bewerbung aktualisieren, application status update,
        interview eingetragen, absage melden, angebot erhalten, zurückgezogen.

        Status-Journey (#170):
        in_vorbereitung -> beworben -> eingangsbestaetigung -> interview -> zweitgespraech -> interview_abgeschlossen -> angebot -> angenommen
        (von jedem Status auch: abgelehnt, zurueckgezogen)

        Args:
            bewerbung_id: ID der Bewerbung
            neuer_status: in_vorbereitung, offen, beworben, eingangsbestaetigung, interview, zweitgespraech, angebot, angenommen, abgelehnt, zurueckgezogen, abgelaufen, arbeitgeber_ausgefallen
                (arbeitgeber_ausgefallen seit v1.7.10/#779: Insolvenz, Stellenstreichung,
                Einstellungsstopp — der Prozess endete ohne Zutun des Bewerbers.
                KEIN Rueckzug, KEINE Absage.)
            notizen: Optionale Notizen zum Statuswechsel
            ablehnungsgrund: Grund der Ablehnung (nur bei status=abgelehnt). Wird für Musteranalyse gespeichert.
            auto_follow_up: Default True. Wenn False, wird beim Wechsel auf
                'beworben' kein automatischer Nachfass-Follow-up nach 7 Tagen
                angelegt (#522). Sinnvoll wenn der Recruiter ausdruecklich
                zugesagt hat sich zu melden.
        """
        # #695: Typ-Pruefung am Tool-Eingang — gleiches Muster wie
        # bewerbung_details (#505). DOC-/JOB-IDs fliegen sofort raus.
        from ..services.typed_ids import validate_id, IdKind, TypedIdMismatch
        try:
            bewerbung_id = validate_id(IdKind.APPLICATION, bewerbung_id)
        except TypedIdMismatch as e:
            return {"fehler": str(e),
                    "hinweis": "Du hast eine ID des falschen Typs uebergeben. "
                               "Bewerbungs-IDs haben das Praefix 'APP-'."}

        # v1.7.0-beta.20: Status-Whitelist. Bestand hatte undefinierte Werte
        # ("warte_auf_rueckmeldung", "abgesagt") die durch das alte Tool
        # einfach durchgewunken wurden — Statistik konnte sie nicht einordnen.
        # Schema-v37-Migration repariert den Bestand, hier verhindern wir das
        # erneute Eindringen.
        VALID_STATUSES = {
            "in_vorbereitung", "offen", "beworben",
            "eingangsbestaetigung", "interview", "zweitgespraech",
            "interview_abgeschlossen", "angebot", "angenommen",
            "abgelehnt", "zurueckgezogen", "abgelaufen",
            # v1.7.10 (#779/D27): Prozess endete ohne Zutun des Bewerbers
            # (Insolvenz, Stellenstreichung, Einstellungsstopp, Reorg).
            # Zaehlt NICHT in die withdrawal_rate; ein vorher vorliegendes
            # Angebot bleibt in der offer_rate erhalten.
            "arbeitgeber_ausgefallen",
        }
        if neuer_status not in VALID_STATUSES:
            # Frueher genutzte Custom-Status auf den jetzt offiziellen Wert mappen
            mapping = {
                "warte_auf_rueckmeldung": "eingangsbestaetigung",
                "abgesagt": "abgelaufen",
            }
            if neuer_status in mapping:
                return {
                    "fehler": (
                        f"Status '{neuer_status}' existiert nicht mehr. "
                        f"Nutze stattdessen '{mapping[neuer_status]}'."
                    ),
                    "vorschlag_status": mapping[neuer_status],
                }
            return {
                "fehler": (
                    f"Unbekannter Status '{neuer_status}'. "
                    f"Erlaubt: {sorted(VALID_STATUSES)}"
                ),
            }

        # v1.7.0-beta.40 (#609): App holen wir immer, damit Elwosa-Hook
        # weiter unten die Firma kennt.
        app = db.get_application(bewerbung_id)
        # #695: unbekannte ID -> klarer Fehler statt stillem "aktualisiert"
        if not app:
            return {"fehler": "Bewerbung nicht gefunden. "
                              "Pruefe die ID mit bewerbungen_anzeigen()."}

        # Bei Wechsel von in_vorbereitung zu beworben: applied_at setzen + Stelle deaktivieren (#405)
        auto_followup_id = None
        if neuer_status == "beworben":
            if app:
                if not app.get("applied_at"):
                    from datetime import datetime
                    db.update_application(bewerbung_id, {"applied_at": datetime.now().isoformat()[:10]})
                # #405: Stelle deaktivieren wenn Bewerbung auf "beworben" gesetzt
                job_hash = app.get("job_hash")
                if job_hash:
                    try:
                        db.dismiss_job(job_hash, reason="bewerbung_erstellt")
                    except Exception:
                        pass
                # #462: Auto-Follow-up nach Tageslücke (Default 7d), falls keiner offen
                # #522: nur wenn auto_follow_up=True (Default)
                if auto_follow_up:
                    try:
                        default_days = int(db.get_setting("followup_default_days", 7) or 7)
                    except Exception:
                        default_days = 7
                    if default_days > 0:
                        existing = [fu for fu in db.get_pending_follow_ups()
                                    if fu.get("application_id") == bewerbung_id]
                        if not existing:
                            from datetime import datetime, timedelta
                            when = (datetime.now() + timedelta(days=default_days)).date().isoformat()
                            # #816: fallbezogener Inhalt statt leerer Reminder
                            _app_tpl = db.get_application(bewerbung_id) or {}
                            auto_followup_id = db.add_follow_up(
                                bewerbung_id, when, "nachfass",
                                template=_nachfass_template(_app_tpl))

        # v1.7.10 (#779/D27): applied_at nachtragen, wenn ein Status erreicht
        # wird, der eine erfolgte Bewerbung voraussetzt — bei Netzwerk-
        # Kontakten wird 'beworben' oft uebersprungen (in_vorbereitung ->
        # interview -> angebot) und die Bewerbung fiel aus jeder Statistik.
        # Quelle: aeltester Timeline-Event, Fallback created_at.
        applied_at_nachgetragen = None
        _STATUS_SETZT_BEWERBUNG_VORAUS = {
            "eingangsbestaetigung", "interview", "zweitgespraech",
            "interview_abgeschlossen", "angebot", "angenommen",
            "abgelehnt", "arbeitgeber_ausgefallen",
        }
        if (neuer_status in _STATUS_SETZT_BEWERBUNG_VORAUS
                and not (app.get("applied_at") or "").strip()):
            try:
                row = db.connect().execute(
                    "SELECT MIN(event_date) AS erster FROM application_events "
                    "WHERE application_id=?",
                    (bewerbung_id,),
                ).fetchone()
                quelle = "aeltester Timeline-Event"
                datum = (row["erster"] or "") if row else ""
                if not datum:
                    datum = app.get("created_at") or ""
                    quelle = "created_at (keine Events vorhanden)"
                if datum:
                    db.update_application(
                        bewerbung_id, {"applied_at": datum[:10]})
                    applied_at_nachgetragen = {
                        "datum": datum[:10], "quelle": quelle}
            except Exception as e:
                logger.debug("applied_at-Nachtrag fehlgeschlagen: %s", e)

        # Lifecycle-Hooks (dismiss + auto-Nachfrage) laufen in
        # db.update_application_status() selbst — siehe _apply_status_lifecycle (#493, #494, #497).
        # Zaehlen vor/nach, damit der MCP-Caller das Ergebnis reporten kann.
        open_before = sum(1 for fu in db.get_pending_follow_ups()
                          if fu.get("application_id") == bewerbung_id)
        db.update_application_status(bewerbung_id, neuer_status, notizen, ablehnungsgrund)

        # v1.7.0-beta.79 (#657 E16): Auto-Veralten verknuepfter Dokumente.
        # Wenn die Bewerbung in einen End-Status uebergeht (abgelehnt /
        # abgelaufen / zurueckgezogen), werden die ausschliesslich mit
        # dieser Bewerbung verknuepften Docs auf `lifecycle=veraltet`
        # gesetzt — sie verschwinden damit aus den Default-Analyse-
        # Ansichten, bleiben aber via `archiv=True` einsehbar und sind
        # ueber `dokument_reaktivieren` jederzeit reversibel.
        #
        # Schema-Hinweis: linked_application_id ist 1:1 — ein Doku haengt
        # max an EINER Bewerbung. "Exklusiv" ist damit automatisch erfuellt.
        #
        # DB-only: physische Dateien werden NICHT angefasst.
        veraltet_docs: list[str] = []
        if neuer_status in ("abgelehnt", "abgelaufen", "zurueckgezogen",
                            "arbeitgeber_ausgefallen"):
            try:
                pid_for_lc = db.get_active_profile_id()
                for doc_id in db.get_documents_linked_to_application(bewerbung_id):
                    try:
                        if db.update_document_lifecycle(
                            doc_id, "veraltet", profile_id=pid_for_lc
                        ):
                            veraltet_docs.append(doc_id)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug(
                            "Auto-Veralten fuer Doku %s fehlgeschlagen: %s",
                            doc_id, exc,
                        )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Auto-Veralten-Hook (#657) fehlgeschlagen: %s", exc)

        # v1.7.0-beta.40 (#609): Elwosa-Hook bei Status-Wechsel
        try:
            from ..services import elwosa as _elwosa
            _trigger_map = {
                "abgelehnt": "absage",
                "eingangsbestaetigung": "eingangsbestaetigung",
                "interview": "interview_einladung",
                "zweitgespraech": "interview_einladung",
                "angenommen": "angenommen",
                "zurueckgezogen": "zurueckgezogen",
                "abgelaufen": "abgelaufen",
            }
            t = _trigger_map.get(neuer_status)
            if t:
                _firma = (app or {}).get("company") or ""
                _elwosa.speak(db, t, ctx={"firma": _firma, "ref": bewerbung_id})
        except Exception:
            pass
        pending_after = [fu for fu in db.get_pending_follow_ups()
                         if fu.get("application_id") == bewerbung_id]
        dismissed_followups = max(0, open_before - len(pending_after))
        result = {
            "status": "aktualisiert",
            "neuer_status": neuer_status,
            "nächste_aktionen": _get_context_actions(neuer_status),
        }
        if applied_at_nachgetragen:
            result["applied_at_nachgetragen"] = applied_at_nachgetragen
            result["applied_at_hinweis"] = (
                f"applied_at war leer und wurde auf "
                f"{applied_at_nachgetragen['datum']} gesetzt "
                f"({applied_at_nachgetragen['quelle']}) — sonst faellt die "
                "Bewerbung aus der Statistik. Bei Bedarf mit "
                "bewerbung_bearbeiten(applied_at=...) korrigieren."
            )
        # v1.7.10 (#782/C30): Absage ohne Grund ist bei einem spaeteren
        # Repost ein Blindflug — Rueckfrage, kein Zwang.
        if neuer_status == "abgelehnt" and not (ablehnungsgrund or "").strip():
            result["rueckfrage_ablehnungsgrund"] = (
                "Kein Ablehnungsgrund angegeben. Frag den Nutzer kurz: Gab es "
                "ein Absageschreiben oder eine Begruendung? Nachtragen mit "
                "bewerbung_status_aendern(..., 'abgelehnt', "
                "ablehnungsgrund='...') oder bewerbung_notiz(). Hintergrund: "
                "Taucht die Stelle als Repost wieder auf, laesst sich ohne "
                "Grund nicht beurteilen, ob die alte Huerde noch steht."
            )
        if neuer_status == "arbeitgeber_ausgefallen":
            result["hinweis"] = (
                "Status 'arbeitgeber_ausgefallen' gesetzt: zaehlt NICHT als "
                "Rueckzug (withdrawal_rate) und NICHT als Absage. Ein vorher "
                "erreichtes Angebot bleibt in der offer_rate erhalten."
            )
        if veraltet_docs:
            # #657 E16: Auto-Veralten-Hook hat Docs gekippt
            result["dokumente_veraltet"] = {
                "anzahl": len(veraltet_docs),
                "ids": veraltet_docs,
                "hinweis": (
                    "Mit der Bewerbung verknuepfte Dokumente wurden auf "
                    "lifecycle=veraltet gesetzt (DB-only, Dateien unberuehrt). "
                    "Reversibel ueber dokument_reaktivieren."
                ),
            }
        if auto_followup_id:
            result["auto_follow_up"] = {
                "id": auto_followup_id,
                "hinweis": f"Nachfass-Erinnerung in {default_days} Tagen automatisch gesetzt. Mit follow_up_erledigen/follow_up_hinfaellig abschliessbar.",
            }
        if dismissed_followups:
            result["follow_ups_geschlossen"] = dismissed_followups
        if neuer_status == "interview_abgeschlossen" and pending_after:
            # juengster offener Follow-up ist der automatisch angelegte
            latest = max(pending_after, key=lambda f: f.get("created_at") or "")
            result["nachfrage_follow_up"] = {
                "id": latest.get("id"),
                "scheduled_date": latest.get("scheduled_date"),
                "hinweis": "Nachfrage-Follow-up automatisch gemaess Einstellung angelegt.",
            }
        if neuer_status == "abgelehnt":
            actions = _get_context_actions("abgelehnt")
            result["motivation"] = actions.get("motivation", "")
            result["hinweis"] = "Nutze ablehnungs_muster() um Ablehnungsmuster zu analysieren und daraus zu lernen."
        elif neuer_status == "angenommen":
            result["nachricht"] = "Herzlichen Glückwunsch! Du hast es geschafft!"
            result["naechste_schritte"] = (
                "Uebernimm die neue Position mit position_aus_bewerbung_uebernehmen, "
                "trage das verhandelte Gehalt via bewerbung_bearbeiten(final_salary=...) ein "
                "und ziehe offene Parallel-Bewerbungen zurueck."
            )
        return result

    @mcp.tool()
    def bewerbungen_anzeigen(
        status_filter: str = "",
        archiv: bool = False,
        stellenart: str = "",
        sortierung: str = "datum",
    ) -> dict:
        """Zeigt erfasste Bewerbungen mit Status und Timeline.

        Standardmäßig werden zurückgezogene, abgelehnte und abgelaufene Bewerbungen
        ausgeblendet. Setze archiv=True um sie zu sehen.

        Args:
            status_filter: Optional: Nur Bewerbungen mit diesem Status
                (offen, in_vorbereitung, beworben, eingangsbestaetigung, interview,
                 zweitgespraech, angebot, angenommen, abgelehnt, zurueckgezogen, abgelaufen)
            archiv: True = auch abgelehnte/zurueckgezogene/abgelaufene zeigen (Standard: False)
            stellenart: Optional: Filter nach Stellenart (festanstellung, freelance, etc.)
            sortierung: datum (Standard), firma, status, score
        """
        apps = db.get_applications(status_filter if status_filter else None)

        # #182: Archivierte Bewerbungen standardmäßig ausblenden
        ARCHIVE_STATUSES = {"abgelehnt", "zurueckgezogen", "abgelaufen",
                            "arbeitgeber_ausgefallen"}
        if not archiv and not status_filter:
            aktive = [a for a in apps if a.get("status") not in ARCHIVE_STATUSES]
            archivierte_count = len(apps) - len(aktive)
            apps = aktive
        else:
            archivierte_count = 0

        # Stellenart-Filter (#182)
        if stellenart:
            apps = [a for a in apps if (a.get("employment_type") or "").lower() == stellenart.lower()]

        if not apps:
            return {
                "anzahl": 0,
                "nachricht": "Noch keine Bewerbungen erfasst. "
                             "Erstelle eine neue Bewerbung mit bewerbung_erstellen() oder "
                             "nutze den Prompt 'bewerbung_schreiben' für eine geführte Bewerbung."
            }

        formatted = []
        for a in apps:
            entry = {
                "id": a["id"][:8],  # #171: Kurz-ID für schnelle Referenz
                "id_voll": a["id"],
                "titel": a.get("title", ""),
                "firma": a.get("company", ""),
                "status": a.get("status", ""),
                "bewerbungsart": a.get("bewerbungsart", ""),
                "datum": a.get("applied_at", ""),
                "events": len(a.get("events", [])),
            }
            if a.get("job_hash"):
                entry["stellen_id"] = a["job_hash"][:8]  # #171
            if a.get("ansprechpartner"):
                entry["ansprechpartner"] = a["ansprechpartner"]
            if a.get("kontakt_email"):
                entry["kontakt_email"] = a["kontakt_email"]
            if a.get("notes"):
                entry["notizen"] = a["notes"][:200]
            # #170: Fortschritts-Tracking bei in_vorbereitung
            if a.get("status") == "in_vorbereitung":
                events = a.get("events", [])
                done_steps = set()
                for e in events:
                    note = (e.get("notes") or "").lower()
                    if "fit-analyse" in note or "fit_analyse" in note:
                        done_steps.add("fit_analyse")
                    if "lebenslauf" in note or "cv" in note:
                        done_steps.add("cv")
                    if "anschreiben" in note:
                        done_steps.add("anschreiben")
                    if "skill-gap" in note or "skill_gap" in note:
                        done_steps.add("skill_gap")
                entry["vorbereitung_fortschritt"] = {
                    "erledigt": len(done_steps),
                    "gesamt": 5,
                    "schritte": list(done_steps),
                }
            formatted.append(entry)

        # #182: Sortierung
        if sortierung == "firma":
            formatted.sort(key=lambda x: x.get("firma", "").lower())
        elif sortierung == "status":
            status_order = ["in_vorbereitung", "beworben", "eingangsbestaetigung",
                            "interview", "zweitgespraech", "interview_abgeschlossen",
                            "angebot", "angenommen",
                            "offen", "abgelehnt", "zurueckgezogen", "abgelaufen",
                            "arbeitgeber_ausgefallen"]
            formatted.sort(key=lambda x: (
                status_order.index(x.get("status", "offen"))
                if x.get("status") in status_order else 99
            ))
        else:  # datum (default) — neueste zuerst
            formatted.sort(key=lambda x: x.get("datum", ""), reverse=True)

        stats = db.get_statistics()
        result = {
            "anzahl": len(formatted),
            "bewerbungen": formatted,
            "statistik": {
                "gesamt": stats.get("total_applications", 0),
                "nach_status": stats.get("applications_by_status", {}),
                "interview_rate": stats.get("interview_rate", 0),
            },
            "hinweis": "Nutze bewerbung_status_aendern(id, status, notizen) um den Status zu aktualisieren."
        }
        # #182: Archiv-Hinweis wenn Bewerbungen ausgeblendet
        if archivierte_count > 0:
            result["archiv_hinweis"] = (
                f"{archivierte_count} archivierte Bewerbungen ausgeblendet "
                "(abgelehnt/zurueckgezogen/abgelaufen). Zeige mit archiv=True."
            )
        return result

    @mcp.tool()
    def bewerbung_loeschen(bewerbung_id: str, bestaetigung: bool = False) -> dict:
        """Löscht eine Bewerbung und alle zugehörigen Events/Timeline-Einträge.

        ACHTUNG: Diese Aktion kann nicht rückgängig gemacht werden!

        Args:
            bewerbung_id: ID der Bewerbung
            bestaetigung: Muss True sein um die Löschung zu bestätigen
        """
        if not bestaetigung:
            app = db.get_application(bewerbung_id)
            if not app:
                return {"fehler": "Bewerbung nicht gefunden."}
            return {
                "status": "bestaetigung_erforderlich",
                "bewerbung": f"{app.get('title', '')} bei {app.get('company', '')}",
                "hinweis": "Setze bestaetigung=True um die Bewerbung unwiderruflich zu löschen."
            }
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden."}
        title = app.get("title", "")
        company = app.get("company", "")
        db.delete_application(bewerbung_id)
        return {
            "status": "gelöscht",
            "nachricht": f"Bewerbung '{title}' bei {company} wurde gelöscht."
        }

    @mcp.tool()
    @time_tool(logger, "bewerbung_bearbeiten")
    def bewerbung_bearbeiten(
        bewerbung_id: str,
        title: str = "",
        company: str = "",
        url: str = "",
        notes: str = "",
        ansprechpartner: str = "",
        kontakt_email: str = "",
        portal_name: str = "",
        bewerbungsart: str = "",
        employment_type: str = "",
        source: str = "",
        vermittler: str = "",
        endkunde: str = "",
        cover_letter_path: str = "",
        cv_path: str = "",
        gehaltsvorstellung: str = "",
        final_salary: str = "",
        applied_at: str = "",
        stellenbeschreibung_original: str = "",
    ) -> dict:
        """Bearbeitet eine bestehende Bewerbung (Felder nachträglich ändern/ergänzen).

        Nur die angegebenen Felder werden geändert, leere Felder bleiben unverändert.

        STRIKTE FELDTRENNUNG (v1.7.0-beta.32 / #588):
        - `stellenbeschreibung_original` = wortgetreuer Originalwortlaut
          der Stellenanzeige (read-mostly). Hier KEINE Notizen, keine
          Recherche, kein Vermittler-Kontext. Wird in `description_snapshot`
          gespeichert und ist Grundlage fuer Anschreiben/Fit-Analyse/CV.
        - `notes` = eigene Recherche, Termin-Vorbereitung, Fragenlisten,
          Vermittler-Kontext, Endkunde-Mutmassungen. Mutable.

        Beim erstmaligen Setzen von stellenbeschreibung_original wird
        snapshot_date auf jetzt gesetzt.

        Args:
            bewerbung_id: ID der Bewerbung
            title: Neuer Stellentitel
            company: Neuer Firmenname
            url: Neuer Link zur Stellenanzeige
            notes: Neue Notizen (überschreibt bisherige)
            ansprechpartner: Neuer Ansprechpartner
            kontakt_email: Neue Kontakt-E-Mail
            portal_name: Neues Portal
            bewerbungsart: Neue Bewerbungsart
            employment_type: Stellenart (festanstellung, freelance, teilzeit, praktikum, werkstudent)
            source: Quelle der Stelle (stepstone, indeed, linkedin, manuell, etc.)
            vermittler: Name des Vermittlers/der Agentur
            endkunde: Name des Endkunden (bei Freelance/Vermittlung)
            cover_letter_path: Pfad zum Anschreiben-PDF (#448)
            cv_path: Pfad zum Lebenslauf-PDF (#448)
            gehaltsvorstellung: Geforderte Gehaltsvorstellung (Freitext, z.B. "85.000 EUR/Jahr")
            final_salary: Tatsaechlich verhandeltes Gehalt nach Zusage (#460)
            applied_at: Bewerbungsdatum nachtraeglich setzen/korrigieren (#529).
                Format YYYY-MM-DD oder leer (= unveraendert). Akzeptiert auch
                "DD.MM.YYYY" und ISO-Timestamps; Datum wird normalisiert.
            stellenbeschreibung_original: Wortgetreuer Originalwortlaut
                der Stellenanzeige (#588). Wird in description_snapshot
                gespeichert. NICHT fuer Notizen verwenden.
        """
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden."}

        # #529: applied_at separat normalisieren
        applied_at_norm = ""
        if applied_at:
            applied_at_norm = _normalize_date(applied_at)
            if not applied_at_norm:
                return {"fehler": f"applied_at '{applied_at}' nicht erkannt. Erwartet YYYY-MM-DD oder DD.MM.YYYY."}

        updates = {}
        for key, val in [("title", title), ("company", company), ("url", url),
                         ("notes", notes), ("ansprechpartner", ansprechpartner),
                         ("kontakt_email", kontakt_email), ("portal_name", portal_name),
                         ("bewerbungsart", bewerbungsart), ("employment_type", employment_type),
                         ("source", source), ("vermittler", vermittler), ("endkunde", endkunde),
                         ("cover_letter_path", cover_letter_path), ("cv_path", cv_path),
                         ("gehaltsvorstellung", gehaltsvorstellung), ("final_salary", final_salary),
                         ("applied_at", applied_at_norm)]:
            if val:
                updates[key] = val

        # v1.7.0-beta.32 (#588): description_snapshot als getrenntes Feld
        if stellenbeschreibung_original:
            from datetime import datetime as _dt_now
            updates["description_snapshot"] = stellenbeschreibung_original
            updates["snapshot_date"] = _dt_now.now().isoformat()

        if not updates:
            return {"fehler": "Keine Änderungen angegeben."}

        db.update_application(bewerbung_id, updates)
        return {
            "status": "aktualisiert",
            "geänderte_felder": list(updates.keys()),
            "nachricht": f"Bewerbung bei {app.get('company', '')} aktualisiert."
        }

    @mcp.tool()
    def bewerbung_notiz(bewerbung_id: str, notiz: str) -> dict:
        """Fügt eine Gesprächsnotiz mit Timestamp zur Bewerbungs-Timeline hinzu.

        Ideal für: Interview-Notizen, Telefonate, E-Mail-Zusammenfassungen,
        Feedback nach Gesprächen, nächste Schritte.

        Args:
            bewerbung_id: ID der Bewerbung
            notiz: Die Notiz (wird mit aktuellem Datum/Uhrzeit gespeichert)
        """
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden."}

        db.add_application_note(bewerbung_id, notiz)
        return {
            "status": "gespeichert",
            "nachricht": f"Notiz zu '{app.get('title', '')}' bei {app.get('company', '')} hinzugefügt.",
            "timeline_eintraege": len(app.get("events", [])) + 1
        }

    @mcp.tool()
    def bewerbung_details(bewerbung_id: str) -> dict:
        """Zeigt alle Details einer Bewerbung: Stellenbeschreibung, Timeline, Notizen, Dokumente.

        Das vollständige Dossier — alles auf einen Blick für Interview-Vorbereitung.

        Args:
            bewerbung_id: ID der Bewerbung. Akzeptiert sowohl die nackte
                Hex-ID (z.B. '42061e46') als auch die typisierte Form
                'APP-42061e46'. Bei falschem Praefix (z.B. 'DOC-...') gibt
                es eine klare Fehlermeldung.
        """
        # v1.7.0 (#505): Typ-Pruefung am Tool-Eingang. Wenn ein User
        # versehentlich eine Dokument-ID uebergibt, sehen wir das sofort.
        from ..services.typed_ids import validate_id, IdKind, TypedIdMismatch
        try:
            bewerbung_id = validate_id(IdKind.APPLICATION, bewerbung_id)
        except TypedIdMismatch as e:
            return {"fehler": str(e),
                    "hinweis": "Du hast eine ID des falschen Typs uebergeben. "
                               "Bewerbungs-IDs haben das Praefix 'APP-'."}
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden."}

        result = {
            "bewerbung_id": app["id"][:8],  # #171: Kurz-ID
            "bewerbung_id_voll": app["id"],
            "titel": app.get("title", ""),
            "firma": app.get("company", ""),
            "status": app.get("status", ""),
            "datum": app.get("applied_at", ""),
            "url": app.get("url", ""),
            "bewerbungsart": app.get("bewerbungsart", ""),
            "ansprechpartner": app.get("ansprechpartner", ""),
            "kontakt_email": app.get("kontakt_email", ""),
            "notizen": app.get("notes", ""),
        }
        # v1.7.10 (#782/C30): rekonstruierte Altbewerbung kennzeichnen —
        # ABGELEITET (applied_at deutlich vor created_at), kein Schema-Feld.
        # Fehlende Details (Ablehnungsgrund, Ansprechpartner) sind dann kein
        # Pflegefehler, sondern Folge der nachtraeglichen Erfassung.
        try:
            from datetime import datetime as _dq_dt
            _applied = (app.get("applied_at") or "")[:10]
            _created = (app.get("created_at") or "")[:10]
            if _applied and _created:
                _delta = (_dq_dt.fromisoformat(_created)
                          - _dq_dt.fromisoformat(_applied)).days
                if _delta > 30:
                    result["datenqualitaet"] = "rekonstruiert"
                    result["datenqualitaet_hinweis"] = (
                        f"Erst {_delta} Tage nach dem Bewerbungsdatum in PBP "
                        "erfasst (nachtraeglich rekonstruiert) — fehlende "
                        "Details sind kein Pflegefehler. Timeline und "
                        "Interview-Zahlen sind eine Untergrenze."
                    )
        except (ValueError, TypeError):
            pass
        if app.get("job_hash"):
            result["stellen_id"] = app["job_hash"][:8]  # #171
            result["stellen_id_voll"] = app["job_hash"]
        if app.get("stellenbeschreibung"):
            result["stellenbeschreibung"] = app["stellenbeschreibung"]
        if app.get("employment_type"):
            result["stellenart"] = app["employment_type"]
        if app.get("events"):
            result["timeline"] = [
                {
                    "datum": e.get("event_date", ""),
                    "status": e.get("status", ""),
                    "notiz": e.get("notes", ""),
                }
                for e in app["events"]
            ]

        # #223: Verknuepfte Dokumente anzeigen
        conn = db.connect()
        linked_docs = conn.execute(
            "SELECT id, filename, doc_type, extraction_status FROM documents WHERE linked_application_id=?",
            (app["id"],)
        ).fetchall()
        if linked_docs:
            result["dokumente"] = [
                {"id": d["id"], "dateiname": d["filename"], "typ": d["doc_type"],
                 "status": d["extraction_status"]}
                for d in linked_docs
            ]

        # #673: Gespeicherte Recherchen (research_notes-Tabelle, alle Kategorien)
        # — getrennt vom manuellen Firmen-Recherche-Notizblock (jobs.research_notes).
        try:
            rnotes = db.get_research_notes(
                bewerbung_id=app["id"], job_hash=app.get("job_hash"))
            if rnotes:
                result["recherchen"] = [
                    {"id": r["id"],
                     "kategorie": r.get("kategorie", "allgemein"),
                     "datum": (r.get("created_at") or "")[:10],
                     "text": r.get("text", "")}
                    for r in rnotes
                ]
        except Exception:
            pass

        # #170: Kontextabhängige Aktionen basierend auf aktuellem Status
        actions = _get_context_actions(app.get("status", ""))

        # D15 (#650, beta.76): Bei staleness >=7d einen prioritaeren Nachfass-
        # Eintrag voranstellen. Liest das letzte Event und vergleicht mit jetzt.
        try:
            from datetime import datetime, timezone, timedelta
            AKTIVE = (
                "offen", "in_vorbereitung", "beworben",
                "eingangsbestaetigung", "interview", "zweitgespraech",
            )
            if app.get("status") in AKTIVE and app.get("events"):
                last_event = max(
                    app["events"],
                    key=lambda e: e.get("event_date", ""),
                )
                last_date_str = last_event.get("event_date") or ""
                last_dt = None
                if last_date_str:
                    for parser in (
                        lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
                        lambda s: datetime.fromisoformat(s),
                    ):
                        try:
                            last_dt = parser(last_date_str)
                            if last_dt.tzinfo is None:
                                last_dt = last_dt.replace(tzinfo=timezone.utc)
                            break
                        except (ValueError, TypeError):
                            continue
                if last_dt:
                    age = datetime.now(timezone.utc) - last_dt
                    if age >= timedelta(days=14):
                        # v1.7.12 (#816, D34): fallbezogen statt status-
                        # generisch. Belegter Fall: 55 Tage Funkstille,
                        # nie ein Interview — und ganz oben standen
                        # "Interview-Vorbereitung" (Prio 1) und
                        # "-Simulation" (Prio 2), dazu 'zurueckgezogen'
                        # als Vorschlag, obwohl niemand zurueckzog.
                        _hatte_interview = app.get("status") in (
                            "interview", "zweitgespraech") or any(
                            (e.get("event_type") or "").startswith("status")
                            and "interview" in str(e.get("new_value") or "")
                            for e in (app.get("events") or []))
                        _basis = actions.get("aktionen", []) or []
                        if not _hatte_interview:
                            # Ohne je ein Interview verdraengen die
                            # Interview-Workflows nur die sinnvolle Aktion.
                            _basis = [a for a in _basis
                                      if a.get("workflow") not in (
                                          "interview_vorbereitung",
                                          "interview_simulation")]
                        # Nachfass-Label mit dem, was der Datensatz weiss.
                        _wer = (app.get("ansprechpartner") or "").strip() \
                            or app.get("company", "Firma")
                        _mail = (app.get("kontakt_email") or "").strip()
                        _nachfass_label = f"Nachfass-Mail an {_wer}"
                        if _mail:
                            _nachfass_label += f" ({_mail})"
                        _nachfass_label += " verfassen"
                        _neu = [
                            {"label": _nachfass_label,
                             "tool": "antwort_formulieren"},
                            # Funkstille heisst 'abgelaufen', nicht
                            # 'zurueckgezogen' — der Bewerber hat nichts
                            # zurueckgezogen, und die Statistik trennt
                            # withdrawal_rate von expired_rate (#779).
                            {"label": ("Als 'abgelaufen' ablegen (keine "
                                       "Reaktion der Firma)"),
                             "tool": "bewerbung_status_aendern",
                             "status": "abgelaufen"},
                        ] + _basis
                        # Deterministische Rangfolge: 1..n, keine Dubletten.
                        for _i, _a in enumerate(_neu, start=1):
                            _a["prioritaet"] = _i
                        actions = {
                            "beschreibung": (
                                f"Wartest du seit {age.days} Tagen auf Antwort — "
                                "hoechste Zeit nachzufassen."
                            ),
                            "aktionen": _neu,
                            "motivation": (
                                f"Ohne aktives Zutun bleibt's bei {app.get('company', 'der Firma')} "
                                "still — bei manchen ueberbrueckt das System einen Nachfass-Anstoss."
                            ),
                            "staleness_tage": age.days,
                        }
                    elif age >= timedelta(days=7):
                        actions["staleness_hinweis"] = (
                            f"Seit {age.days} Tagen kein Update — ein Nachfass "
                            "waere bald angebracht."
                        )
                        actions["staleness_tage"] = age.days
        except Exception as exc:
            logger.warning("staleness-Check fuer Bewerbung %s fehlgeschlagen: %s",
                           app.get("id"), exc)

        result["nächste_aktionen"] = actions

        return result

    @mcp.tool()
    def statistiken_abrufen(
        zeitraum_von: str = "",
        zeitraum_bis: str = ""
    ) -> dict:
        """Ruft Bewerbungsstatistiken ab: Conversion-Rate, Antwortzeiten, Status-Verteilung.

        Gibt einen Ueberblick ueber:
        - Gesamtzahl Bewerbungen und aktive Stellen
        - Bewerbungen nach Status (in_vorbereitung, beworben, interview, angebot, etc.)
        - Interview-Rate (% der Bewerbungen die zum Interview fuehren)
        - Quoten (#682): expired_rate / rejection_rate / withdrawal_rate, plus
          ein `quoten`-Block mit Segmentierung am PBP-Startdatum
          (gesamt / seit_pbp / vor_pbp) — zeigt, ob seit der systematischen
          PBP-Nutzung anteilig weniger Bewerbungen versanden.
        - Pipeline-Übersicht (wie viele Bewerbungen in welchem Status)

        Args:
            zeitraum_von: Optional: Start-Datum (YYYY-MM-DD) für den Bericht (#173)
            zeitraum_bis: Optional: End-Datum (YYYY-MM-DD) für den Bericht (#173)

        v1.7.10 (#781/D29) — drei neue Bloecke:
        - `zeitliche_kennzahlen`: Prozessdauer nach Ausgang, Reaktionszeit,
          Zeit bis Interview/Absage (Median + Mittel), laengste laufende
          Prozesse, Verteilung pro Monat
        - `kanal_auswertung`: Interview-Quote pro Kanal (Portal, Vermittler,
          Netzwerk, Direktbewerbung) — Erfolg statt Trefferzahl
        - `ablehnungs_kategorien`: still/automatisch/nach Interview/
          Vermittler/extern bedingt; Quote roh UND bereinigt (extern
          bedingte Faelle sind keine Ablehnung des Bewerbers)
        Vor-PBP-Zahlen sind eine Untergrenze (rekonstruierter Altbestand) —
        siehe `zeitliche_kennzahlen.datenqualitaet` und `quoten.fussnote`.
        """
        stats = db.get_statistics()

        # v1.7.10 (#781/D29): erweiterte Bloecke. Fehler hier duerfen die
        # Basis-Statistik nie kippen.
        try:
            from ..services import statistik_erweitert as _se
            stats["zeitliche_kennzahlen"] = _se.zeitliche_kennzahlen(db)
            stats["kanal_auswertung"] = _se.kanal_auswertung(db)
            stats["ablehnungs_kategorien"] = _se.ablehnungs_kategorien(db)
            # v1.7.23 (#943): drei Auswertungen, die aus dem vorhandenen
            # Bestand ohne Zusatzerfassung berechenbar waren und
            # trotzdem fehlten.
            stats["erfolg_nach_score_band"] = _se.erfolg_nach_score_band(db)
            stats["nachfass_wirksamkeit"] = _se.nachfass_wirksamkeit(db)
            stats["trend_vergleich"] = _se.trend_vergleich(db)
            if isinstance(stats.get("quoten"), dict):
                stats["quoten"]["fussnote"] = (
                    "Zahlen aus der Zeit vor der PBP-Nutzung stammen aus "
                    "rekonstruierten Altbewerbungen (typisch nur 1-2 Events) "
                    "— Interview- und Zeitkennzahlen dieses Zeitraums sind "
                    "eine Untergrenze, keine Wahrheit."
                )
        except Exception as e:
            logger.warning("Erweiterte Statistik (#781) fehlgeschlagen: %s", e)

        # Zeitraumfilter (#173)
        if zeitraum_von or zeitraum_bis:
            apps = db.get_applications()
            filtered = []
            for a in apps:
                date = a.get("applied_at") or a.get("created_at") or ""
                if zeitraum_von and date < zeitraum_von:
                    continue
                if zeitraum_bis and date > zeitraum_bis + "T23:59:59":
                    continue
                filtered.append(a)
            # Recalculate stats for filtered period
            by_status = {}
            for a in filtered:
                s = a.get("status", "offen")
                by_status[s] = by_status.get(s, 0) + 1
            total = len(filtered)
            in_vorb = by_status.get("in_vorbereitung", 0)
            submitted = total - in_vorb  # exclude in_vorbereitung from rate basis (#198)
            interviews = by_status.get("interview", 0) + by_status.get("zweitgespraech", 0)
            offers = by_status.get("angebot", 0) + by_status.get("angenommen", 0)
            stats["zeitraum"] = {"von": zeitraum_von, "bis": zeitraum_bis}
            stats["total_applications"] = total
            stats["applications_by_status"] = by_status
            stats["interview_rate"] = round(interviews / submitted * 100, 1) if submitted else 0
            stats["offer_rate"] = round(offers / submitted * 100, 1) if submitted else 0

        # Pipeline-Zusammenfassung (#170)
        by_status = stats.get("applications_by_status", {})
        pipeline = {
            "in_vorbereitung": by_status.get("in_vorbereitung", 0),
            "beworben": by_status.get("beworben", 0),
            "im_prozess": (by_status.get("eingangsbestaetigung", 0)
                           + by_status.get("interview", 0)
                           + by_status.get("zweitgespraech", 0)),
            "angebote": by_status.get("angebot", 0) + by_status.get("angenommen", 0),
        }
        stats["pipeline"] = pipeline

        return stats

    # === Meetings (#444) ===================================================
    # Schreibzugriff auf application_meetings. Bisher konnte Claude Interviews,
    # Telefonate und Termine nur per direktem SQL anlegen — jetzt sauber ueber MCP.

    _MEETING_TYPES = {
        "interview", "telefon", "video", "vor_ort", "kennenlernen",
        "zweitgespraech", "assessment", "probearbeiten", "vertrag", "sonstiges",
    }
    _MEETING_STATUS = {"geplant", "bestaetigt", "durchgefuehrt", "abgeschlossen", "abgesagt", "verschoben"}

    # v1.7.17 (#915): Wall-Clock-Budget. Belegt 17.08.: fuenf Aufrufe je
    # 4 Minuten Stille bis zum Client-Timeout, ohne Wirkung und ohne
    # Fehlermeldung. Bei Budget-Riss kommt jetzt ein status='timeout'-
    # Ergebnis mit den laufenden Hintergrund-Tasks.
    from ..services.tool_budget import mit_budget as _mit_budget

    @mcp.tool()
    @_mit_budget("meeting_hinzufuegen", lese_tool="meetings_anzeigen")
    def meeting_hinzufuegen(
        bewerbung_id: str,
        datum: str,
        typ: str = "interview",
        platform: str = "",
        ort: str = "",
        titel: str = "",
        notizen: str = "",
        dauer_minuten: int = 0,
        status: str = "geplant",
        wenn_dublette: str = "melden",
    ) -> dict:
        """Fuegt einen Termin (Interview, Telefonat, Video-Call) zu einer Bewerbung hinzu (#444).

        Nutze dies immer wenn der Anwender einen Gespraechstermin erwaehnt. Das
        Meeting erscheint anschliessend in `bewerbung_details()` und im Kalender.

        v1.7.11 (#804/D30): Dubletten-Pruefung. Termine entstehen inzwischen
        aus mehreren Quellen gleichzeitig (Mail-/ICS-Import, Claude, manuelle
        Eingabe) — ohne Pruefung liegt derselbe Termin doppelt im Kalender und
        jede Auswertung zaehlt ihn zweimal.

        Args:
            bewerbung_id: ID der Bewerbung (aus bewerbungen_anzeigen)
            datum: Datum/Uhrzeit als ISO-String (z.B. '2026-04-18T14:00' oder '2026-04-18 14:00')
            typ: Meeting-Typ (interview, telefon, video, vor_ort, kennenlernen, zweitgespraech, assessment, probearbeiten, vertrag, sonstiges)
            platform: Plattform bei Video-Calls (z.B. 'Teams', 'Zoom', 'Google Meet')
            ort: Ort bei Vor-Ort-Terminen
            titel: Optionaler Titel (Default: abgeleitet vom Typ)
            notizen: Freie Notizen zum Termin
            dauer_minuten: Geplante Dauer in Minuten (0 = unbekannt)
            status: Status (geplant, bestaetigt, abgeschlossen, abgesagt, verschoben)
            wenn_dublette: Verhalten bei einem bestehenden Termin derselben
                Bewerbung im Zeitfenster (+/- 30 Minuten, nicht abgesagt):
                'melden' (Default) = nichts anlegen, bestehenden Termin
                zurueckgeben; 'zusammenfuehren' = LEERE Felder des
                bestehenden Termins mit den neuen Werten fuellen, gefuellte
                nie ueberschreiben; 'trotzdem_neu' = zweiten Termin anlegen
                (echte Doppeltermine am selben Tag gibt es).
        """
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden. Prüfe die ID mit bewerbungen_anzeigen()."}
        if not datum:
            return {"fehler": "Datum ist ein Pflichtfeld."}
        if wenn_dublette not in ("melden", "zusammenfuehren", "trotzdem_neu"):
            return {"fehler": "wenn_dublette muss 'melden', 'zusammenfuehren' "
                              "oder 'trotzdem_neu' sein."}
        if typ not in _MEETING_TYPES:
            return {
                "fehler": f"Ungueltiger Typ '{typ}'.",
                "erlaubte_typen": sorted(_MEETING_TYPES),
            }
        if status not in _MEETING_STATUS:
            return {
                "fehler": f"Ungueltiger Status '{status}'.",
                "erlaubte_status": sorted(_MEETING_STATUS),
            }

        # v1.7.11 (#804/D30): bestehenden Termin im Zeitfenster suchen
        from ..services.termin_dubletten import finde_dublette, zusammenfuehren
        bestehend = finde_dublette(db, bewerbung_id, datum)
        if bestehend and wenn_dublette != "trotzdem_neu":
            if wenn_dublette == "melden":
                return {
                    "status": "dublette_moeglich",
                    "bestehender_termin": bestehend,
                    "nicht_angelegt": True,
                    "nachricht": (
                        f"Fuer diese Bewerbung gibt es bereits einen Termin am "
                        f"{bestehend.get('meeting_date')} "
                        f"('{bestehend.get('title')}'). Es wurde NICHTS "
                        "angelegt."
                    ),
                    "optionen": {
                        "zusammenfuehren": (
                            "wenn_dublette='zusammenfuehren' — fuellt leere "
                            "Felder des bestehenden Termins mit den neuen "
                            "Angaben (gefuellte bleiben unangetastet)."
                        ),
                        "trotzdem_neu": (
                            "wenn_dublette='trotzdem_neu' — echter zweiter "
                            "Termin am selben Tag."
                        ),
                    },
                }
            # zusammenfuehren
            merge = zusammenfuehren(db, bestehend, {
                "title": titel, "meeting_type": typ, "platform": platform,
                "location": ort, "notes": notizen, "status": status,
                "duration_minutes": dauer_minuten, "meeting_date": datum,
            })
            return {
                "status": "zusammengefuehrt",
                "meeting_id": bestehend.get("id"),
                "ergaenzte_felder": merge["ergaenzt"],
                "unveraendert": merge["behalten"],
                "nachricht": (
                    f"Bestehender Termin ergaenzt statt doppelt angelegt "
                    f"({len(merge['ergaenzt'])} Feld(er) gefuellt)."
                ),
            }

        data = {
            "application_id": bewerbung_id,
            "title": titel or f"{typ.capitalize()} — {app.get('company', '')}".strip(" —"),
            "meeting_date": datum,
            "meeting_type": typ,
            "platform": platform or None,
            "location": ort,
            "notes": notizen or None,
            "status": status,
            "duration_minutes": dauer_minuten or None,
        }
        meeting_id = db.add_meeting(data)
        result = {
            "status": "angelegt",
            "meeting_id": meeting_id,
            "bewerbung": f"{app.get('title', '')} bei {app.get('company', '')}",
            "typ": typ,
            "datum": datum,
            "nachricht": (
                f"{typ.capitalize()} am {datum} zu '{app.get('title', '')}' "
                f"bei {app.get('company', '')} gespeichert."
            ),
        }
        if bestehend:
            result["dublette_uebersteuert"] = {
                "bestehender_termin_id": bestehend.get("id"),
                "hinweis": "Ein Termin im selben Zeitfenster existierte "
                           "bereits — auf Wunsch trotzdem angelegt.",
            }
        return result

    @mcp.tool()
    def phantom_termine_bereinigen(
        dry_run: bool = True,
        termin_ids: list[str] = None,
    ) -> dict:
        """Findet Termine, die aus zitierten Mail-Zeitstempeln entstanden (#922).

        Belegter Fall: der Import EINER Mail mit Antwortverlauf legte VIER
        Termine an — die Sendezeiten der zitierten Vorgaengermails, alle
        mit dem Mail-Betreff als Titel. Sie sind keine Dubletten (die
        Zeitpunkte liegen weit auseinander), sondern schlicht keine
        Termine; die #804-Pruefung greift dort nicht.

        Ohne Argumente: Report der verdaechtigen Gruppen mit Begruendung.
        Mit `termin_ids` + `dry_run=False`: loescht genau diese Termine.

        Sicherheitsnetz: verdaechtig ist nur, was ALLE Merkmale traegt —
        Mail-Betreff-Praefix im Titel (AW:/Re:/WG:/Fwd:), kein Link, keine
        Notizen, kein Ort, UND mindestens zwei gleich betitelte Eintraege
        derselben Bewerbung. Ein einzelner Termin faellt nie darunter.
        Geloescht wird NUR auf ausdrueckliche Anweisung.

        Args:
            dry_run: True (Default) = nur zeigen, nichts loeschen.
            termin_ids: Termine, die geloescht werden sollen.
        """
        from ..services.termin_dubletten import finde_phantom_termine

        if not termin_ids:
            gruppen = finde_phantom_termine(db)
            gesamt = sum(g["anzahl"] for g in gruppen)
            return {
                "status": "report",
                "gruppen": gruppen,
                "anzahl_gruppen": len(gruppen),
                "anzahl_termine": gesamt,
                "hinweis": (
                    "Zum Loeschen: phantom_termine_bereinigen("
                    "termin_ids=[...], dry_run=False). Bitte die Liste "
                    "VORHER mit dem Nutzer durchgehen — echte Termine mit "
                    "Betreff-Titel sind moeglich, wenn sie ohne Link und "
                    "Notizen erfasst wurden."
                ) if gruppen else (
                    "Keine Phantom-Termine gefunden. Fuer echte Dubletten "
                    "(gleicher Zeitpunkt): termin_dubletten_bereinigen()."
                ),
            }

        if dry_run:
            return {
                "status": "vorschau",
                "wuerde_loeschen": termin_ids,
                "anzahl": len(termin_ids),
                "hinweis": "Mit dry_run=False wird tatsaechlich geloescht.",
            }

        geloescht, fehler = [], []
        for tid in termin_ids:
            try:
                db.delete_meeting(tid)
                geloescht.append(tid)
            except Exception as exc:  # noqa: BLE001
                fehler.append({"id": tid, "fehler": str(exc)[:120]})
        result = {
            "status": "bereinigt",
            "geloescht": geloescht,
            "anzahl": len(geloescht),
        }
        if fehler:
            result["fehler"] = fehler
        return result

    @mcp.tool()
    def termin_dubletten_bereinigen(
        dry_run: bool = True,
        master_id: str = "",
        duplikat_id: str = "",
    ) -> dict:
        """Findet und bereinigt doppelte Termine im Bestand (#804/D30).

        Ohne Argumente: Report aller Termin-Paare derselben Bewerbung im
        selben Zeitfenster (+/- 30 Minuten, abgesagte ausgenommen). Mit
        `master_id` + `duplikat_id`: fuehrt genau dieses Paar zusammen —
        leere Felder des Masters werden aus dem Duplikat gefuellt, gefuellte
        bleiben unangetastet, danach wird das Duplikat geloescht.

        Idempotent: ein zweiter Lauf findet das bereinigte Paar nicht mehr.

        Args:
            dry_run: True (Default) = nur zeigen, nichts aendern.
            master_id: Termin, der bestehen bleibt.
            duplikat_id: Termin, der nach dem Uebernehmen geloescht wird.
        """
        from ..services.termin_dubletten import (
            finde_alle_dubletten, zusammenfuehren)

        if not master_id and not duplikat_id:
            paare = finde_alle_dubletten(db)
            return {
                "status": "report",
                "dubletten": paare,
                "anzahl": len(paare),
                "hinweis": (
                    "Zum Zusammenfuehren: termin_dubletten_bereinigen("
                    "master_id=..., duplikat_id=..., dry_run=False). Der "
                    "Master ist vorbelegt mit dem inhaltsreicheren Termin."
                ) if paare else "Keine Termin-Dubletten gefunden.",
            }
        if not (master_id and duplikat_id):
            return {"fehler": "master_id UND duplikat_id angeben — oder "
                              "beide weglassen fuer den Report."}
        if str(master_id) == str(duplikat_id):
            return {"fehler": "master_id und duplikat_id sind identisch."}

        _conn = db.connect()
        alle = {
            str(r["id"]): dict(r) for r in _conn.execute(
                "SELECT * FROM application_meetings WHERE id IN (?, ?)",
                (str(master_id), str(duplikat_id))).fetchall()
        }
        master, dupl = alle.get(str(master_id)), alle.get(str(duplikat_id))
        if not master or not dupl:
            return {"fehler": "Termin nicht gefunden. IDs liefert "
                              "meetings_anzeigen() oder der Report."}
        if master.get("application_id") != dupl.get("application_id"):
            return {"fehler": "Die Termine gehoeren zu verschiedenen "
                              "Bewerbungen — kein Zusammenfuehren."}
        if dry_run:
            from ..services.termin_dubletten import _MERGE_FELDER, _ist_leer
            wuerde = [f for f in _MERGE_FELDER
                      if _ist_leer(master.get(f)) and not _ist_leer(dupl.get(f))]
            return {
                "status": "vorschau",
                "master": {"id": master.get("id"), "titel": master.get("title"),
                           "datum": master.get("meeting_date")},
                "duplikat": {"id": dupl.get("id"), "titel": dupl.get("title")},
                "wuerde_uebernehmen": wuerde,
                "hinweis": "Mit dry_run=False ausfuehren.",
            }
        merge = zusammenfuehren(db, master, dupl)
        geloescht = False
        try:
            geloescht = bool(db.delete_meeting(dupl.get("id")))
        except Exception as e:
            return {"status": "teilweise", "ergaenzt": merge["ergaenzt"],
                    "fehler": f"Duplikat nicht geloescht: {e}"}
        return {
            "status": "zusammengefuehrt",
            "master_id": master.get("id"),
            "ergaenzte_felder": merge["ergaenzt"],
            "unveraendert": merge["behalten"],
            "duplikat_geloescht": geloescht,
        }

    @mcp.tool()
    @_mit_budget("meeting_bearbeiten", lese_tool="meetings_anzeigen")
    def meeting_bearbeiten(
        meeting_id: str,
        titel: str = "",
        datum: str = "",
        ort: str = "",
        platform: str = "",
        notizen: str = "",
        status: str = "",
        dauer_minuten: int = 0,
    ) -> dict:
        """Aktualisiert einen bestehenden Termin (#444).

        Nur die angegebenen Felder werden geaendert. Leere Strings bleiben unveraendert.
        Nutze dies z.B. um einen Termin zu bestaetigen, zu verschieben oder Notizen zu ergaenzen.

        Args:
            meeting_id: ID des Meetings (aus meetings_anzeigen)
            titel: Neuer Titel
            datum: Neues Datum/Uhrzeit (ISO-String)
            ort: Neuer Ort
            platform: Neue Plattform
            notizen: Neue Notizen (ueberschreibt bisherige)
            status: Neuer Status (geplant, bestaetigt, abgeschlossen, abgesagt, verschoben)
            dauer_minuten: Neue Dauer (0 = nicht aendern)
        """
        updates: dict = {}
        if titel:
            updates["title"] = titel
        if datum:
            updates["meeting_date"] = datum
        if ort:
            updates["location"] = ort
        if platform:
            updates["platform"] = platform
        if notizen:
            updates["notes"] = notizen
        if status:
            if status not in _MEETING_STATUS:
                return {
                    "fehler": f"Ungueltiger Status '{status}'.",
                    "erlaubte_status": sorted(_MEETING_STATUS),
                }
            updates["status"] = status
        if dauer_minuten:
            updates["duration_minutes"] = dauer_minuten

        if not updates:
            return {"fehler": "Keine Aenderungen angegeben."}

        profile_id = db.get_active_profile_id()
        changed = db.update_meeting(meeting_id, updates, profile_id=profile_id)
        if not changed:
            return {"fehler": "Meeting nicht gefunden oder gehoert nicht zum aktiven Profil."}
        return {
            "status": "aktualisiert",
            "meeting_id": meeting_id,
            "geaenderte_felder": list(updates.keys()),
        }

    @mcp.tool()
    def meeting_loeschen(meeting_id: str, bestaetigung: bool = False) -> dict:
        """Loescht einen Termin (#444).

        ACHTUNG: Nicht rueckgaengig zu machen. Beim ersten Aufruf ohne
        Bestaetigung wird nur eine Rueckfrage zurueckgegeben.

        Args:
            meeting_id: ID des Meetings
            bestaetigung: Muss True sein um tatsaechlich zu loeschen
        """
        profile_id = db.get_active_profile_id()
        if not bestaetigung:
            return {
                "status": "bestaetigung_erforderlich",
                "meeting_id": meeting_id,
                "hinweis": "Setze bestaetigung=True um den Termin unwiderruflich zu loeschen.",
            }
        deleted = db.delete_meeting(meeting_id, profile_id=profile_id)
        if not deleted:
            return {"fehler": "Meeting nicht gefunden oder gehoert nicht zum aktiven Profil."}
        return {"status": "geloescht", "meeting_id": meeting_id}

    @mcp.tool()
    def meetings_anzeigen(bewerbung_id: str = "", tage: int = 30) -> dict:
        """Zeigt Termine — entweder fuer eine bestimmte Bewerbung oder kommende im Zeitraum (#444).

        Args:
            bewerbung_id: Optional — wenn gesetzt, nur Termine zu dieser Bewerbung
            tage: Wenn keine Bewerbung angegeben: Anzahl Tage in die Zukunft (Default: 30)
        """
        profile_id = db.get_active_profile_id()
        if bewerbung_id:
            app = db.get_application(bewerbung_id)
            if not app:
                return {"fehler": "Bewerbung nicht gefunden."}
            meetings = db.get_meetings_for_application(bewerbung_id, profile_id=profile_id)
            return {
                "status": "ok",
                "bewerbung": f"{app.get('title', '')} bei {app.get('company', '')}",
                "anzahl": len(meetings),
                "meetings": meetings,
            }
        meetings = db.get_upcoming_meetings(days=tage)
        if not meetings:
            # v1.7.21 (#927): leere Liste ohne Angebot ist eine Sackgasse.
            return leer(
                {"status": "ok", "zeitraum_tage": tage, "anzahl": 0,
                 "meetings": []},
                f"Keine Termine in den naechsten {tage} Tagen.",
                "Sobald ein Gespraech vereinbart ist, sag es einfach "
                "Claude ('Interview am 3.9. um 14 Uhr bei ...') — der "
                "Termin landet dann hier, im Kalender und in der "
                "Vorbereitung. Zurueckliegende Termine siehst du ueber "
                "die jeweilige Bewerbung.")
        return {
            "status": "ok",
            "zeitraum_tage": tage,
            "anzahl": len(meetings),
            "meetings": meetings,
        }

    # === E-Mails (#445) ====================================================
    # Schreibzugriff auf application_emails. Tools um E-Mails manuell mit
    # Bewerbungen zu verknuepfen, zu loeschen oder unmatched aufzulisten.

    @mcp.tool()
    def email_verknuepfen(email_id: str, bewerbung_id: str) -> dict:
        """Verknuepft eine eingegangene E-Mail mit einer Bewerbung (#445).

        Nutze dies fuer E-Mails die die Pipeline nicht automatisch zuordnen
        konnte oder die falsch zugeordnet wurden. Setze `bewerbung_id` auf den
        leeren String um die Verknuepfung zu entfernen (E-Mail wird wieder
        'unmatched').

        Args:
            email_id: ID der E-Mail (aus emails_anzeigen)
            bewerbung_id: ID der Bewerbung ODER leerer String zum Entkoppeln
        """
        profile_id = db.get_active_profile_id()
        email = db.get_email(email_id, profile_id=profile_id)
        if not email:
            # v1.7.0-beta.70 (#644): Fallback auf den Dokument-Store.
            # Hochgeladene .eml/.msg landen als `documents`, nicht als gepollte
            # `emails` — die IDs sehen identisch aus. Statt "E-Mail nicht
            # gefunden" pruefen wir ob es ein Mail-DOKUMENT mit der ID gibt
            # und verknuepfen transparent ueber linked_application_id.
            if bewerbung_id:
                app = db.get_application(bewerbung_id)
                if not app:
                    return {"fehler": "Bewerbung nicht gefunden."}
                try:
                    conn = db.connect()
                    doc = conn.execute(
                        "SELECT id FROM documents WHERE id=? "
                        "AND (profile_id=? OR profile_id IS NULL)",
                        (email_id, profile_id),
                    ).fetchone()
                    if doc:
                        conn.execute(
                            "UPDATE documents SET linked_application_id=? WHERE id=?",
                            (bewerbung_id, email_id),
                        )
                        conn.commit()
                        return {
                            "status": "verknuepft",
                            "document_id": email_id,
                            "bewerbung": f"{app.get('title', '')} bei {app.get('company', '')}",
                            "hinweis": (
                                "Die ID gehoerte zu einem hochgeladenen "
                                "Mail-DOKUMENT (nicht zu einer gepollten "
                                "E-Mail) — ueber den Dokument-Store verknuepft."
                            ),
                        }
                except Exception:
                    pass
            return {
                "fehler": "Weder E-Mail noch Dokument mit dieser ID gefunden.",
                "hinweis": (
                    "IDs aus emails_anzeigen() sind E-Mails, IDs aus "
                    "dokumente_zur_analyse() sind Dokumente. Beide werden hier "
                    "akzeptiert — pruefe ob die ID stimmt."
                ),
            }

        if bewerbung_id:
            app = db.get_application(bewerbung_id)
            if not app:
                return {"fehler": "Bewerbung nicht gefunden."}
            changed = db.update_email(
                email_id, {"application_id": bewerbung_id}, profile_id=profile_id
            )
            if not changed:
                return {"fehler": "Verknuepfung konnte nicht aktualisiert werden."}
            return {
                "status": "verknuepft",
                "email_id": email_id,
                "bewerbung": f"{app.get('title', '')} bei {app.get('company', '')}",
                "betreff": email.get("subject", ""),
            }
        # bewerbung_id leer -> entkoppeln
        changed = db.update_email(
            email_id, {"application_id": None}, profile_id=profile_id
        )
        if not changed:
            return {"fehler": "Entkoppelung konnte nicht aktualisiert werden."}
        return {
            "status": "entkoppelt",
            "email_id": email_id,
            "betreff": email.get("subject", ""),
        }

    @mcp.tool()
    def email_loeschen(email_id: str, bestaetigung: bool = False) -> dict:
        """Loescht eine E-Mail aus der Datenbank (#445).

        Args:
            email_id: ID der E-Mail
            bestaetigung: Muss True sein um tatsaechlich zu loeschen
        """
        profile_id = db.get_active_profile_id()
        email = db.get_email(email_id, profile_id=profile_id)
        if not email:
            return {"fehler": "E-Mail nicht gefunden."}
        if not bestaetigung:
            return {
                "status": "bestaetigung_erforderlich",
                "email_id": email_id,
                "betreff": email.get("subject", ""),
                "hinweis": "Setze bestaetigung=True um die E-Mail unwiderruflich zu loeschen.",
            }
        deleted = db.delete_email(email_id, profile_id=profile_id)
        if not deleted:
            return {"fehler": "E-Mail konnte nicht geloescht werden."}
        return {"status": "geloescht", "email_id": email_id}

    @mcp.tool()
    def emails_anzeigen(bewerbung_id: str = "") -> dict:
        """Zeigt E-Mails — entweder zu einer Bewerbung oder alle nicht zugeordneten (#445).

        Args:
            bewerbung_id: Optional — wenn gesetzt, nur E-Mails dieser Bewerbung.
                          Leer = alle noch nicht zugeordneten E-Mails (unmatched).
        """
        profile_id = db.get_active_profile_id()
        if bewerbung_id:
            app = db.get_application(bewerbung_id)
            if not app:
                return {"fehler": "Bewerbung nicht gefunden."}
            emails = db.get_emails_for_application(bewerbung_id, profile_id=profile_id)
            return {
                "status": "ok",
                "bewerbung": f"{app.get('title', '')} bei {app.get('company', '')}",
                "anzahl": len(emails),
                "emails": emails,
            }
        emails = db.get_unmatched_emails()
        return {
            "status": "ok",
            "filter": "unmatched",
            "anzahl": len(emails),
            "emails": emails,
        }

    # === Follow-up Lifecycle (#453 / v1.5.7) ===

    @mcp.tool()
    def follow_up_erledigen(follow_up_id: str, notiz: str = "") -> dict:
        """Markiert einen Follow-up (Nachfass-Erinnerung) als erledigt.

        Auch findbar als: nachfass erledigt, nachfassen abhaken, follow up done.

        Args:
            follow_up_id: ID des Follow-ups
            notiz: Optionale Notiz zu wie es erledigt wurde (wird an die Bewerbung gehaengt)
        """
        fu = db.get_follow_up(follow_up_id)
        if not fu:
            return {"fehler": "Follow-up nicht gefunden."}
        if fu.get("status") != "geplant":
            return {
                "fehler": f"Follow-up ist bereits '{fu.get('status')}' — kann nicht erneut erledigt werden.",
            }
        db.complete_follow_up(follow_up_id, status="erledigt")
        if notiz:
            try:
                db.add_application_note(fu["application_id"], f"Nachfass erledigt: {notiz}")
            except Exception:
                pass
        return {
            "status": "erledigt",
            "follow_up_id": follow_up_id,
            "nachricht": "Nachfass als erledigt markiert.",
        }

    @mcp.tool()
    def follow_up_hinfaellig(follow_up_id: str, grund: str = "") -> dict:
        """Markiert einen Follow-up als hinfaellig (z.B. weil Absage kam, kein Nachfassen mehr noetig).

        Auch findbar als: nachfass schliessen, nachfassen entfernen, follow up dismiss.

        Args:
            follow_up_id: ID des Follow-ups
            grund: Optional — warum hinfaellig (Absage erhalten, Bewerbung zurueckgezogen, ...)
        """
        fu = db.get_follow_up(follow_up_id)
        if not fu:
            return {"fehler": "Follow-up nicht gefunden."}
        if fu.get("status") != "geplant":
            return {
                "fehler": f"Follow-up ist bereits '{fu.get('status')}'.",
            }
        db.complete_follow_up(follow_up_id, status="hinfaellig")
        if grund:
            try:
                db.add_application_note(fu["application_id"], f"Nachfass hinfaellig: {grund}")
            except Exception:
                pass
        return {
            "status": "hinfaellig",
            "follow_up_id": follow_up_id,
        }

    @mcp.tool()
    def follow_up_verschieben(follow_up_id: str, neues_datum: str) -> dict:
        """Verschiebt ein geplantes Follow-up auf ein neues Datum.

        Args:
            follow_up_id: ID des Follow-ups
            neues_datum: Neues Datum (YYYY-MM-DD)
        """
        fu = db.get_follow_up(follow_up_id)
        if not fu:
            return {"fehler": "Follow-up nicht gefunden."}
        if fu.get("status") != "geplant":
            return {"fehler": f"Nur geplante Follow-ups koennen verschoben werden (aktuell: {fu.get('status')})."}
        db.update_follow_up(follow_up_id, {"scheduled_date": neues_datum})
        return {"status": "verschoben", "follow_up_id": follow_up_id, "neues_datum": neues_datum}

    @mcp.tool()
    def follow_up_bearbeiten(follow_up_id: str, text: str) -> dict:
        """v1.7.12 (#816, D34): setzt oder aendert den INHALT einer
        Nachfassung nachtraeglich.

        Bisher gab es dafuer keinen Weg — follow_up_verschieben aendert
        nur das Datum, und ein leerer Reminder blieb leer. Der Text soll
        sagen, WAS zu tun ist: an wen, worauf bezogen, ueber welchen
        Kanal.

        Args:
            follow_up_id: ID des Follow-ups (nachfass_anzeigen zeigt sie).
            text: Die Handlungsanweisung (ersetzt den bisherigen Inhalt).
        """
        fu = db.get_follow_up(follow_up_id)
        if not fu:
            return {"fehler": "Follow-up nicht gefunden."}
        if not (text or "").strip():
            return {"fehler": "text darf nicht leer sein — genau der leere "
                              "Reminder ist das Problem (#816)."}
        db.update_follow_up(follow_up_id, {"template": text.strip()})
        return {"status": "aktualisiert", "follow_up_id": follow_up_id,
                "text": text.strip()}

    # === v1.7.0-beta.6: Bewerbungsaufwand (#568) ===

    @mcp.tool()
    def meeting_aufwand_setzen(
        meeting_id: str,
        runde: int = None,
        vorbereitung_minuten: int = None,
        reise_modus: str = "",
        reisekosten_brutto: float = None,
        reisekosten_erstattet: float = None,
    ) -> dict:
        """Setzt Aufwand-Daten an einem bestehenden Termin (#568).

        Args:
            meeting_id: ID des Termins.
            runde: Welche Interview-Runde (1, 2, 3...) bei Mehr-Runden-Interviews.
            vorbereitung_minuten: Wieviel Zeit floss in Vorbereitung (Recherche,
                Folien, Antworten ueben).
            reise_modus: 'vor_ort' / 'video' / 'telefon' / 'hybrid'.
            reisekosten_brutto: Selbst getragene Reisekosten in EUR.
            reisekosten_erstattet: Davon vom Arbeitgeber erstattet (zur Differenz-
                Auswertung).
        """
        ok = db.update_meeting_aufwand(
            meeting_id,
            runde_nr=runde,
            vorbereitungszeit_min=vorbereitung_minuten,
            reise_modus=reise_modus or None,
            reisekosten_brutto=reisekosten_brutto,
            reisekosten_erstattet=reisekosten_erstattet,
        )
        if not ok:
            return {"fehler": "Meeting nicht gefunden oder keine Aenderungen angegeben."}
        return {"status": "aktualisiert", "meeting_id": meeting_id}

    @mcp.tool()
    def kosten_erfassen(
        kategorie: str,
        betrag_eur: float,
        beschreibung: str = "",
        bewerbung_id: str = "",
        datum: str = "",
    ) -> dict:
        """Erfasst eine Kosten-Position (z.B. Tool-Abo, Pruefungs-Gebuehr) (#568).

        Args:
            kategorie: 'tool' | 'pruefung' | 'reise' | 'fortbildung' | 'sonstiges'.
            betrag_eur: Betrag in EUR (positive Zahl).
            beschreibung: Was war es genau (z.B. 'LinkedIn Premium 1 Monat').
            bewerbung_id: Optional eine Bewerbung verknuepfen.
            datum: ISO-Datum wann angefallen. Leer = heute.
        """
        valid = ("tool", "pruefung", "reise", "fortbildung", "sonstiges")
        if kategorie not in valid:
            return {"fehler": f"kategorie muss eines von {valid} sein."}
        if betrag_eur < 0:
            return {"fehler": "Betrag muss >= 0 sein."}
        from ..services.typed_ids import strip_prefix
        from datetime import datetime as _dt
        try:
            cid = db.add_application_cost({
                "application_id": strip_prefix(bewerbung_id) if bewerbung_id else None,
                "kind": kategorie,
                "amount": betrag_eur,
                "description": beschreibung or None,
                "incurred_at": datum or _dt.now().date().isoformat(),
            })
        except ValueError as e:
            return {"fehler": str(e)}
        return {"status": "gespeichert", "kosten_id": cid}

    @mcp.tool()
    def kosten_anzeigen(bewerbung_id: str = "", kategorie: str = "") -> dict:
        """Listet Kostenpositionen, optional gefiltert (#568)."""
        from ..services.typed_ids import strip_prefix
        items = db.list_application_costs(
            application_id=strip_prefix(bewerbung_id) if bewerbung_id else None,
            kind=kategorie,
        )
        total = sum((c.get("amount") or 0) for c in items)
        return {
            "anzahl": len(items),
            "summe_eur": round(total, 2),
            "kosten": items,
        }

    @mcp.tool()
    def kosten_loeschen(kosten_id: str) -> dict:
        """Loescht eine Kosten-Position."""
        ok = db.delete_application_cost(kosten_id)
        return {"status": "geloescht" if ok else "nicht_gefunden"}

    # === v1.7.0-beta.20: Recruiter-Anfrage-Tools ===
    # Ein Recruiter meldet sich, ich entscheide gegen die Stelle ohne mich
    # ueberhaupt zu bewerben. Das ist KEINE Bewerbung — es darf also keinen
    # applications-Eintrag geben (verfaelscht sonst die Statistik). Die
    # Stelle wird trotzdem in jobs angelegt (fuer Markt-Beobachtung) und
    # sofort dismissed.

    @mcp.tool()
    def recruiter_anfrage_ablehnen(
        firma: str,
        titel: str,
        grund: str,
        notizen: str = "",
        url: str = "",
    ) -> dict:
        """Lehnt eine Recruiter-Anfrage ab OHNE Bewerbung anzulegen.

        Wann nutzen: Ein Recruiter (LinkedIn-DM, E-Mail, Anruf) bietet eine
        Stelle an. Du entscheidest sofort dagegen — Standort passt nicht,
        Branche stimmt nicht, Gehalt unrealistisch, Tonalitaet unprofessionell
        etc. Es kommt zu KEINER Bewerbung.

        Was passiert:
        1. Eine Stelle wird in `jobs` angelegt (source='recruiter_inbound')
        2. Diese Stelle wird sofort dismissed (is_active=0, dismiss_reason=grund)
        3. KEIN applications-Eintrag wird angelegt
        4. Notizen werden in research_notes der Stelle gespeichert

        Vorteil ggue. bewerbung_erstellen(status='zurueckgezogen'):
        - Track-Record-Statistik bleibt sauber (zaehlt nicht als 'submitted')
        - Markt-Beobachtung trotzdem moeglich (Stelle ist im Bestand)
        - Semantisch korrekt: keine Bewerbung war geplant, also keine erfasst

        Args:
            firma: Firma die angefragt hat
            titel: Stellentitel der angefragten Position
            grund: Warum abgelehnt (z.B. 'standort', 'gehalt', 'branche')
            notizen: Optional ausfuehrlicher Notiz fuer's Recherche-Archiv
            url: Optionaler Link zur Anfrage / Stelle
        """
        if not firma or not titel:
            return {"fehler": "firma und titel sind Pflichtfelder."}
        if not grund:
            return {"fehler": "grund ist Pflicht — sonst lernt PBP nichts ueber Ablehnungsmuster."}

        from ..job_scraper import stelle_hash
        from datetime import datetime as _dt
        h = stelle_hash("recruiter_inbound", f"{firma}-{titel}")
        notiz_block = (
            f"[{_dt.now().strftime('%Y-%m-%d')}] Recruiter-Anfrage abgelehnt. "
            f"Grund: {grund}."
        )
        if notizen:
            notiz_block += f" Notizen: {notizen}"

        # Stelle anlegen (oder finden falls Hash schon existiert)
        existing = db.get_job(h)
        if existing:
            target_hash = existing["hash"]
            # Vorhandene Stelle: Notiz anhaengen + dismiss falls noch aktiv
            cur_notes = (existing.get("research_notes") or "")
            new_notes = (cur_notes + "\n\n" + notiz_block).strip() if cur_notes else notiz_block
            db.update_job(target_hash, {"research_notes": new_notes})
        else:
            db.save_jobs([{
                "hash": h,
                "title": titel,
                "company": firma,
                "url": url or "",
                "source": "recruiter_inbound",
                "description": notiz_block,
                "research_notes": notiz_block,
                "score": 0,
            }])
            target_hash = h

        # Sofort ausmustern
        db.dismiss_job(target_hash, reason=grund)

        # Lerneffekt: dismiss_count fuer den Grund hochzaehlen damit
        # AblehnungsMuster-Statistik den Inbound-Pfad mitbekommt
        try:
            db.increment_dismiss_reason_usage([grund])
        except Exception:
            pass

        return {
            "status": "abgelehnt",
            "stelle_hash": target_hash,
            "firma": firma,
            "titel": titel,
            "grund": grund,
            "nachricht": (
                f"Recruiter-Anfrage von {firma} ({titel}) als "
                f"'{grund}' abgelehnt. KEIN Bewerbungs-Eintrag erzeugt — "
                "deine Statistik bleibt sauber."
            ),
        }

    @mcp.tool()
    def bewerbung_zu_anfrage_konvertieren(
        bewerbung_id: str,
        grund: str = "war_nur_anfrage",
    ) -> dict:
        """Konvertiert einen faelschlich angelegten Bewerbungseintrag zu einer abgelehnten Recruiter-Anfrage.

        Wann nutzen: Beim Audit der Bewerbungsliste faellt auf, dass ein Eintrag
        mit Status 'zurueckgezogen' oder 'abgelehnt' eigentlich nie eine Bewerbung
        war — es war nur eine Anfrage die du sofort abgelehnt hast. Dieses Tool:

        1. Loescht den applications-Eintrag (Statistik bleibt sauber)
        2. Behaelt die verknuepfte Stelle, dismisst sie mit dem gegebenen Grund
        3. Schreibt die Notizen aus der Bewerbung in research_notes der Stelle

        Args:
            bewerbung_id: ID der zu konvertierenden Bewerbung
            grund: Dismiss-Reason fuer die Stelle (default 'war_nur_anfrage')
        """
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden."}
        if app.get("status") not in ("zurueckgezogen", "abgelehnt", "in_vorbereitung"):
            return {
                "fehler": (
                    f"Konvertierung nur erlaubt fuer Status zurueckgezogen, "
                    f"abgelehnt oder in_vorbereitung. Aktuell: {app.get('status')}."
                )
            }

        from datetime import datetime as _dt
        notiz_archiv = (
            f"[{_dt.now().strftime('%Y-%m-%d')}] Konvertiert von "
            f"applications->dismissed. Urspruenglicher Status: "
            f"{app.get('status')}. "
        )
        if app.get("notes"):
            notiz_archiv += f"Notizen: {app['notes']}"
        if app.get("rejection_reason"):
            notiz_archiv += f" Rejection: {app['rejection_reason']}"

        job_hash = app.get("job_hash")
        if job_hash:
            try:
                cur = db.get_job(job_hash)
                if cur:
                    cur_notes = (cur.get("research_notes") or "")
                    new_notes = (cur_notes + "\n\n" + notiz_archiv).strip() if cur_notes else notiz_archiv
                    db.update_job(job_hash, {"research_notes": new_notes})
                db.dismiss_job(job_hash, reason=grund)
            except Exception:
                pass
        else:
            # Keine Stelle verknuepft — neue inbound-Stelle aus den Bewerbungs-Daten anlegen
            from ..job_scraper import stelle_hash
            h = stelle_hash("recruiter_inbound", f"{app['company']}-{app['title']}")
            db.save_jobs([{
                "hash": h,
                "title": app["title"],
                "company": app["company"],
                "url": app.get("url") or "",
                "source": "recruiter_inbound",
                "description": notiz_archiv,
                "research_notes": notiz_archiv,
                "score": 0,
            }])
            db.dismiss_job(h, reason=grund)
            job_hash = h

        # Bewerbung loeschen — FK-Cascade entfernt application_events / follow_ups
        db.delete_application(bewerbung_id)
        # Verifikation: ist sie wirklich weg?
        check = db.get_application(bewerbung_id)
        return {
            "status": "konvertiert" if check is None else "fehlgeschlagen",
            "bewerbung_id": bewerbung_id[:8],
            "stelle_hash": job_hash,
            "grund": grund,
            "nachricht": (
                f"Bewerbung {bewerbung_id[:8]} ({app.get('company')}/"
                f"{app.get('title')}) zu Recruiter-Anfrage konvertiert. "
                "Statistik wird ab sofort sauber sein."
            ),
        }


    @mcp.tool()
    def aufwand_uebersicht(bewerbung_id: str = "") -> dict:
        """Aggregiert den Aufwand pro Bewerbung oder ueber alles (#568).

        Liefert: Reisekosten brutto/erstattet/netto, Vorbereitungszeit-Summe
        in Minuten, Termin-Dauer in Minuten, Anzahl Termine, Summe sonstiger
        Kosten.
        """
        from ..services.typed_ids import strip_prefix
        bid = strip_prefix(bewerbung_id) if bewerbung_id else None
        return db.get_aufwand_summary(application_id=bid)

    # === Abschluss-Flow (#455 / v1.5.7) ===

    @mcp.tool()
    def position_aus_bewerbung_uebernehmen(
        bewerbung_id: str,
        start_date: str = "",
        description: str = "",
    ) -> dict:
        """Uebernimmt Titel und Firma einer angenommenen Bewerbung als neue Profil-Position.

        Gedacht fuer den Abschluss-Flow nach Status=angenommen: die frischen Daten
        (Stelle, Firma, Startdatum) werden als neue `positions`-Zeile im Profil angelegt,
        ohne Daten doppelt eingeben zu muessen.

        Args:
            bewerbung_id: ID der angenommenen Bewerbung
            start_date: Start-Datum (YYYY-MM-DD). Leer = heute.
            description: Optionale Beschreibung der Rolle.
        """
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden."}
        if not app.get("title") or not app.get("company"):
            return {"fehler": "Bewerbung hat keine Stelle oder Firma hinterlegt."}
        from datetime import datetime as _dt
        effective_start = start_date or _dt.now().date().isoformat()
        position_id = db.add_position({
            "title": app["title"],
            "company": app["company"],
            "start_date": effective_start,
            "end_date": "",
            "is_current": 1,
            "description": description or f"Uebernommen aus Bewerbung {bewerbung_id[:8]}",
        })
        try:
            db.add_application_note(
                bewerbung_id,
                f"Position ins Profil uebernommen (position_id={position_id}, Start {effective_start})."
            )
        except Exception:
            pass
        return {
            "status": "uebernommen",
            "position_id": position_id,
            "titel": app["title"],
            "firma": app["company"],
            "start": effective_start,
            "nachricht": f"Position '{app['title']}' bei {app['company']} als aktuelle Stelle im Profil angelegt.",
        }

    # === Post-Interview-Reflexion (#464, v1.7.0-beta.49) ============

    @mcp.tool()
    def interview_reflexion_speichern(
        bewerbung_id: str,
        was_lief_gut: str = "",
        was_lief_schlecht: str = "",
        was_war_ueberraschend: str = "",
        gefuehl: int = 0,
        next_steps: str = "",
        wiederverwendbare_antwort: str = "",
        meeting_id: str = "",
        reflexion_id: str = "",
    ) -> dict:
        """v1.7.0-beta.49 (#464): Strukturierte Reflexion nach einem Interview.

        Statt Freitext in `bewerbung_notiz` wird hier ein strukturierter
        Fragebogen abgelegt — wiederverwendbar bei der naechsten
        Interview-Vorbereitung. Erste Stufe von #452 (Interview-
        Training-Arc).

        v1.7.12 (#824, D31): Jeder Aufruf legt eine NEUE Reflexion an —
        bei zweistufigen Verfahren gehoert zu jedem Gespraech eine eigene.
        (Vorher ueberschrieb der zweite Aufruf die erste; die Nachbereitung
        des Erstgespraechs war damit weg.) Zum Nachbearbeiten einer
        bestehenden Reflexion `reflexion_id` uebergeben. Alle Felder
        optional — zwei ausgefuellte Felder sind besser als keine.

        Teilnehmer des Gespraechs werden als Kontakte am TERMIN erfasst:
        kontakt_verknuepfen(kontakt_id, ziel_typ='meeting',
        ziel_id=<meeting_id>, rolle='fachlicher Gegenpart'). Unbekannte
        Namen als Kontakt "Rolle, Name unbekannt" anlegen — die ehrliche
        Luecke ist wertvoller als ein leeres Feld.

        Args:
            bewerbung_id: ID der Bewerbung (akzeptiert auch kurzen Hash).
            was_lief_gut: was hast du gut hinbekommen? (1-3 Saetze)
            was_lief_schlecht: wo hat es geknirscht? (1-3 Saetze)
            was_war_ueberraschend: was hast du NICHT erwartet? (Frage,
                Stimmung, Ablauf)
            gefuehl: 1 (mies) bis 5 (super) — Bauchgefuehl direkt nach Interview
            next_steps: was macht der User als naechstes? (Nachfass, warten, ...)
            wiederverwendbare_antwort: Falls eine konkrete Antwort gut
                lief — fuer die Stilarchiv-Wiederverwendung.
            meeting_id: Optional — der Termin, zu dem das Gespraech gehoert
                (meetings_anzeigen liefert die IDs). Erstgespraech laeuft
                anders als Endrunde; die Auswertung unterscheidet das.
            reflexion_id: Optional — bestehende Reflexion nachbearbeiten
                statt eine neue anzulegen. Nur uebergebene Felder aendern
                sich.
        """
        from ..services.typed_ids import strip_prefix
        bid = strip_prefix(bewerbung_id)
        app = db.get_application(bid)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden",
                    "bewerbung_id": bewerbung_id}
        if gefuehl and not 1 <= int(gefuehl) <= 5:
            return {"fehler": "gefuehl muss zwischen 1 und 5 liegen"}

        if reflexion_id:
            daten = {}
            if was_lief_gut:
                daten["was_lief_gut"] = was_lief_gut
            if was_lief_schlecht:
                daten["was_lief_schlecht"] = was_lief_schlecht
            if was_war_ueberraschend:
                daten["was_war_ueberraschend"] = was_war_ueberraschend
            if gefuehl:
                daten["gefuehl"] = int(gefuehl)
            if next_steps:
                daten["next_steps"] = next_steps
            if wiederverwendbare_antwort:
                daten["wiederverwendbare_antwort"] = wiederverwendbare_antwort
            if meeting_id:
                daten["meeting_id"] = strip_prefix(meeting_id)
            neu = db.update_interview_reflection(int(reflexion_id), daten)
            if neu is None:
                return {"fehler": "Reflexion nicht gefunden",
                        "reflexion_id": reflexion_id}
            return {"status": "aktualisiert", "reflexion_id": neu["id"],
                    "bewerbung_id": bewerbung_id,
                    "firma": app.get("company")}

        rid = db.add_interview_reflection(bid, {
            "was_lief_gut": was_lief_gut,
            "was_lief_schlecht": was_lief_schlecht,
            "was_war_ueberraschend": was_war_ueberraschend,
            "gefuehl": int(gefuehl) if gefuehl else None,
            "next_steps": next_steps,
            "wiederverwendbare_antwort": wiederverwendbare_antwort,
        }, meeting_id=strip_prefix(meeting_id) if meeting_id else "")
        # Auch eine kurze Notiz an die Bewerbung haengen damit die Reflexion
        # im Verlauf sichtbar ist
        try:
            db.add_application_note(
                bid, "Interview-Reflexion gespeichert (siehe interview_reflexion_lesen)."
            )
        except Exception:
            pass
        vorhandene = db.get_interview_reflections(bid)
        result = {
            "status": "gespeichert",
            "reflexion_id": rid,
            "bewerbung_id": bewerbung_id,
            "firma": app.get("company"),
            "stelle": app.get("title"),
        }
        if len(vorhandene) > 1:
            result["hinweis"] = (
                f"Das ist Reflexion Nr. {len(vorhandene)} zu dieser "
                "Bewerbung — jede bleibt erhalten (#824). Nachbearbeiten "
                "per reflexion_id.")
        return result

    @mcp.tool()
    def interview_reflexion_lesen(bewerbung_id: str) -> dict:
        """Liest ALLE Reflexionen zu einer Bewerbung, neueste zuerst (#824).

        Leer wenn keine vorhanden. Vor einem Folgegespraech lesen: was
        lief beim letzten Mal, wer war dabei (Kontakte am Termin), was
        waren die offenen Punkte.
        """
        from ..services.typed_ids import strip_prefix
        bid = strip_prefix(bewerbung_id)
        rs = db.get_interview_reflections(bid)
        if not rs:
            return {"status": "leer",
                    "bewerbung_id": bewerbung_id,
                    "hinweis": "Noch keine Reflexion gespeichert. "
                               "Nutze interview_reflexion_speichern."}
        return {"status": "vorhanden", "anzahl": len(rs),
                "reflexionen": rs,
                # Alt-Feld fuer bestehende Aufrufer: die neueste.
                "reflexion": rs[0]}

    @mcp.tool()
    def interview_reflexion_loeschen(reflexion_id: str) -> dict:
        """Entfernt eine versehentlich angelegte Reflexion (#824).

        Die IDs stehen in interview_reflexion_lesen bzw.
        interview_reflexionen_anzeigen.
        """
        ok = db.delete_interview_reflection(int(reflexion_id))
        return {"status": "geloescht" if ok else "nicht_gefunden",
                "reflexion_id": reflexion_id}

    @mcp.tool()
    def interview_lehren_auswerten() -> dict:
        """Quer-Auswertung ueber ALLE Interview-Reflexionen (#824, D31).

        Regelbasiert, ohne Sprachmodell: Antwortarchiv (alle
        wiederverwendbaren Antworten mit Herkunft), wiederkehrende
        Selbstkritik und Ueberraschungen (mit Fallzahl — Beobachtung,
        kein Urteil), Bauchgefuehl gegen tatsaechlichen Ausgang, offene
        naechste Schritte aus laufenden Verfahren.

        Muster werden erst ab 4 Reflexionen ausgewiesen (#798-Regel:
        zwei Vorkommen sind kein Muster). Nutze das VOR einer
        Gespraechsvorbereitung — die wiederkehrenden Ueberraschungen
        sind die Fragen, die in der Recherche bisher fehlten.
        """
        from ..services.interview_lehren import lehren_auswerten
        return lehren_auswerten(db)

    @mcp.tool()
    def interview_reflexionen_anzeigen(limit: int = 20) -> dict:
        """Liste der letzten Interview-Reflexionen (fuer Lerneffekt vor naechstem Interview).

        Sortiert nach updated_at desc. Zeigt firma + stelle + gefuehl
        + Kurz-Auszug pro Eintrag. Hilft beim Pre-Interview-Lesen:
        was lief gut bei aehnlichen Stellen, was war ueberraschend.
        """
        items = db.list_interview_reflections(limit=max(1, min(int(limit), 100)))
        if not items:
            # v1.7.21 (#927): gerade hier zaehlt der Hinweis — die
            # Nachbereitung ist der Teil, den man am leichtesten
            # vergisst, und der am meisten fuer das naechste Gespraech
            # bringt.
            return leer(
                {"anzahl": 0, "reflexionen": []},
                "Noch keine Gespraechs-Nachbereitung erfasst.",
                "Nach einem Gespraech lohnt es sich, die Eindruecke "
                "festzuhalten, solange sie frisch sind: welche Fragen "
                "kamen, was lief gut, was hat gefehlt. Speichern mit "
                "interview_reflexion_speichern(bewerbung_id, ...) — vor "
                "dem naechsten Gespraech liest PBP das wieder vor.")
        return {
            "anzahl": len(items),
            "reflexionen": items,
        }
