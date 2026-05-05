"""Bewerbungs-Management — 16 Tools (#170: geführter Workflow, #443: Write-Back-Gaps)."""

import hashlib
import re


def _normalize_company_for_dedup(name: str) -> str:
    """Normalisiert Firmennamen fuer Duplikat-Erkennung (#531).

    Entfernt Klammerzusaetze (Vermittler/Endkunde-Hinweise), Rechtsform-
    Suffixe (GmbH/AG/SE/KG), Sonderzeichen — vergleicht so dass
    'IQ Intelligentes Ingenieur Management (Endkunde: Siemens Energy)'
    und 'Siemens Energy (via IQ Intelligentes Ingenieur Management GmbH)'
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


def register(mcp, db, logger):
    """Registriert Bewerbungs-Tools."""

    @mcp.tool()
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
        stellenbeschreibung: str = ""
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
        """
        # #170: Wenn der User sich noch nicht beworben hat → in_vorbereitung
        # #506: Aber NUR, wenn der Aufrufer keinen expliziten Status gesetzt hat.
        # `status="beworben"` ist der implizite Default — in diesem Fall
        # interpretieren wir "noch nicht beworben" als "in_vorbereitung".
        # Wenn jemand `bereits_beworben=False, status="zurueckgezogen"` ueber-
        # gibt, soll der Status respektiert werden (z.B. Inbound-Anfrage,
        # die ohne Bewerbung sofort abgelehnt wurde).
        if not bereits_beworben and status == "beworben":
            status = "in_vorbereitung"

        # Check for duplicate applications (#63 / #531 v1.6.4)
        # v1.6.4: Erweitert um fuzzy-match (Vermittler/Endkunde-Beziehungen
        # und Stadt-/Internal-Suffixe). Vorher exakt company.lower() ==
        # company.lower() — verfehlt z.B. "IQ ... (Endkunde: Siemens)" vs
        # "Siemens (via IQ ...)". Plus Email-/Ansprechpartner-Match als
        # zusaetzliches Signal.
        existing_apps = db.get_applications()
        norm_company = _normalize_company_for_dedup(company)
        norm_title = _normalize_title_for_dedup(title)
        norm_email = (kontakt_email or "").lower().strip()
        norm_ansprech = (ansprechpartner or "").lower().strip()

        for existing in existing_apps:
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
                                 "Nutze bewerbung_bearbeiten() um diese zu aktualisieren."
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
                        f"Falls neue Bewerbung trotzdem gewuenscht: notes='Klarstellen, dass dies eine eigene Bewerbung ist'."
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
                        f"Sehr wahrscheinlich Duplikat."
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
                db.save_jobs([{
                    "hash": effective_hash,
                    "title": title,
                    "company": company,
                    "location": "",
                    "url": url,
                    "source": "manuell",
                    "description": stellenbeschreibung or notes or "",
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
        })

        # #231: Stelle als inaktiv markieren wenn Bewerbung erstellt
        if effective_hash:
            try:
                db.dismiss_job(effective_hash, reason="bewerbung_erstellt")
            except Exception:
                pass  # Job existiert evtl. nicht

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
                    auto_followup_id = db.add_follow_up(aid, when, "nachfass")
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
            neuer_status: in_vorbereitung, offen, beworben, eingangsbestaetigung, interview, zweitgespraech, angebot, angenommen, abgelehnt, zurueckgezogen, abgelaufen
            notizen: Optionale Notizen zum Statuswechsel
            ablehnungsgrund: Grund der Ablehnung (nur bei status=abgelehnt). Wird für Musteranalyse gespeichert.
            auto_follow_up: Default True. Wenn False, wird beim Wechsel auf
                'beworben' kein automatischer Nachfass-Follow-up nach 7 Tagen
                angelegt (#522). Sinnvoll wenn der Recruiter ausdruecklich
                zugesagt hat sich zu melden.
        """
        # Bei Wechsel von in_vorbereitung zu beworben: applied_at setzen + Stelle deaktivieren (#405)
        auto_followup_id = None
        if neuer_status == "beworben":
            app = db.get_application(bewerbung_id)
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
                            auto_followup_id = db.add_follow_up(bewerbung_id, when, "nachfass")

        # Lifecycle-Hooks (dismiss + auto-Nachfrage) laufen in
        # db.update_application_status() selbst — siehe _apply_status_lifecycle (#493, #494, #497).
        # Zaehlen vor/nach, damit der MCP-Caller das Ergebnis reporten kann.
        open_before = sum(1 for fu in db.get_pending_follow_ups()
                          if fu.get("application_id") == bewerbung_id)
        db.update_application_status(bewerbung_id, neuer_status, notizen, ablehnungsgrund)
        pending_after = [fu for fu in db.get_pending_follow_ups()
                         if fu.get("application_id") == bewerbung_id]
        dismissed_followups = max(0, open_before - len(pending_after))
        result = {
            "status": "aktualisiert",
            "neuer_status": neuer_status,
            "nächste_aktionen": _get_context_actions(neuer_status),
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
        ARCHIVE_STATUSES = {"abgelehnt", "zurueckgezogen", "abgelaufen"}
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
                            "offen", "abgelehnt", "zurueckgezogen", "abgelaufen"]
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
    ) -> dict:
        """Bearbeitet eine bestehende Bewerbung (Felder nachträglich ändern/ergänzen).

        Nur die angegebenen Felder werden geändert, leere Felder bleiben unverändert.

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

        # #170: Kontextabhängige Aktionen basierend auf aktuellem Status
        result["nächste_aktionen"] = _get_context_actions(app.get("status", ""))

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
        - Pipeline-Übersicht (wie viele Bewerbungen in welchem Status)

        Args:
            zeitraum_von: Optional: Start-Datum (YYYY-MM-DD) für den Bericht (#173)
            zeitraum_bis: Optional: End-Datum (YYYY-MM-DD) für den Bericht (#173)
        """
        stats = db.get_statistics()

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

    @mcp.tool()
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
    ) -> dict:
        """Fuegt einen Termin (Interview, Telefonat, Video-Call) zu einer Bewerbung hinzu (#444).

        Nutze dies immer wenn der Anwender einen Gespraechstermin erwaehnt. Das
        Meeting erscheint anschliessend in `bewerbung_details()` und im Kalender.

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
        """
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden. Prüfe die ID mit bewerbungen_anzeigen()."}
        if not datum:
            return {"fehler": "Datum ist ein Pflichtfeld."}
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
        return {
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

    @mcp.tool()
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
            return {"fehler": "E-Mail nicht gefunden."}

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
