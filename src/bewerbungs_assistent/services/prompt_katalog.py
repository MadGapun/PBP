"""Der Prompt-Katalog — eine Quelle fuer Titel, Beschreibung und Auswahl.

Warum dieses Modul entsteht (#979, G29)
---------------------------------------

Dieselben Prompt-Metadaten standen an vier Stellen:

===========================  ==========================================
`prompts.py`                 die registrierten MCP-Prompts (25)
`workflows.py::_prompt_registry`  Kennung -> Builder (16)
`dashboard.py` META          Kategorie, Titel, Beschreibung (18)
`DashboardPage.jsx`          Prompt, Label, Beschreibung, Icon (12)
===========================  ==========================================

Titel und Beschreibung standen in META **und** im Frontend als Kopie
nebeneinander. Eine Umbenennung musste zweimal passieren, ein neuer
Prompt dreimal. Und die Hilfe-Liste behauptete "vollstaendige Liste
aller Prompts", zeigte aber die 16 aus der Registry.

Einen konfigurierbaren Schnellzugriff auf dieser Basis zu bauen haette
eine FUENFTE Kopie erzeugt: die Nutzerauswahl referenziert Kennungen,
die Anzeige braucht Titel, und die kaemen aus dem Frontend.

Zwei Ebenen
-----------

Der Katalog trennt **Eintrag** und **Prompt**. Ein Eintrag ist das, was
der Mensch anklickt; ein Prompt ist der Builder dahinter. Zwei Eintraege
duerfen auf denselben Builder zeigen, wenn sie feste Parameter tragen —
so entstehen "Lebenslauf" und "Anschreiben" aus dem einen
`bewerbung_schreiben` (#981).

Ausnahmen
---------

Die Elwosa-Bedienprompts stehen bewusst NICHT im Katalog.
Nutzerentscheidung vom 07.09.2026: PBP laeuft unabhaengig von Elwosa,
und die Prompt-Liste ist eine Liste von Bewerbungs-Workflows, keine
Fernbedienung fuer die Sidebar. Sie bleiben ueber ihre Slash-Kennung
erreichbar, sie stehen nur nicht im Katalog.

Der Paritaets-Test (`tests/test_v1733_prompt_katalog_979.py`) verlangt
fuer JEDEN registrierten Prompt entweder einen Katalogeintrag oder einen
Eintrag in `AUSNAHMEN` mit Begruendung — nach dem Muster G20/#896.
"""

# ── Ausnahmen: registriert, aber bewusst nicht im Katalog ───────────

AUSNAHMEN: dict[str, str] = {
    "elwosa_status_anzeigen": (
        "Bedienung der Sidebar-Anzeige, kein Bewerbungs-Workflow. PBP "
        "laeuft unabhaengig von Elwosa (Nutzerentscheidung 07.09.2026)."),
    "elwosa_pause_anfordern": "wie elwosa_status_anzeigen",
    "elwosa_antworten": "wie elwosa_status_anzeigen",
    "elwosa_linie_lehren": "wie elwosa_status_anzeigen",
    "elwosa_zurueckholen": "wie elwosa_status_anzeigen",
}

# Reihenfolge der Kategorien in Hilfe und Schnellzugriff.
KATEGORIEN = (
    "Profil",
    "Jobsuche & Bewerbung",
    "Interview & Verhandlung",
    "Analyse & Strategie",
    "Weitere",
)

# ── Der Katalog ────────────────────────────────────────────────────
#
# `id`        Kennung des EINTRAGS (stabil; die Nutzerauswahl zeigt darauf)
# `prompt`    Kennung des Builders
# `parameter` feste Query-Parameter fuer diesen Eintrag
# `icon`      Kennung, das Frontend loest sie auf (kein Import hier)
# `standard`  im Schnellzugriff, solange der Nutzer nichts gewaehlt hat

EINTRAEGE: tuple[dict, ...] = (
    # ── Profil ──────────────────────────────────────────────────────
    {"id": "ersterfassung", "prompt": "ersterfassung",
     "kategorie": "Profil", "titel": "Kennenlernen",
     "beschreibung": "Profil im Gespraech erstellen",
     "icon": "play", "standard": True},
    {"id": "willkommen", "prompt": "willkommen",
     "kategorie": "Profil", "titel": "Wo stehe ich?",
     "beschreibung": "Dein aktueller Stand",
     "icon": "book", "standard": True},
    {"id": "profil_erweiterung", "prompt": "profil_erweiterung",
     "kategorie": "Profil", "titel": "Dokumente analysieren",
     "beschreibung": "Profil ergaenzen, Skills extrahieren, CV bewerten",
     "icon": "plus", "standard": True},
    {"id": "profil_sync", "prompt": "profil_sync",
     "kategorie": "Profil", "titel": "Profil-Sync",
     "beschreibung": "Profil mit hochgeladenen Dokumenten abgleichen",
     "icon": "refresh", "standard": False},
    {"id": "bewerbungs_uebersicht", "prompt": "bewerbungs_uebersicht",
     "kategorie": "Profil", "titel": "Uebersicht",
     "beschreibung": "Was laeuft gerade?",
     "icon": "list", "standard": False},

    # ── Jobsuche & Bewerbung ───────────────────────────────────────
    {"id": "jobsuche_workflow", "prompt": "jobsuche_workflow",
     "kategorie": "Jobsuche & Bewerbung", "titel": "Jobsuche starten",
     "beschreibung": "Jobboersen durchsuchen lassen",
     "icon": "search", "standard": True},
    # v1.7.32 (#981 D): der Workflow erstellt Lebenslauf UND Anschreiben.
    # Das alte Etikett "Bewerbung schreiben / Anschreiben erstellen"
    # nannte die Haelfte.
    {"id": "bewerbung_schreiben", "prompt": "bewerbung_schreiben",
     "kategorie": "Jobsuche & Bewerbung", "titel": "Bewerbungsunterlagen",
     "beschreibung": "Lebenslauf und/oder Anschreiben zu einer Stelle",
     "icon": "send", "standard": True},
    # Zwei Eintraege auf denselben Builder — wer die Trennung lieber
    # mag, waehlt sie im Schnellzugriff dazu (#979 E).
    {"id": "bewerbung_schreiben_lebenslauf", "prompt": "bewerbung_schreiben",
     "parameter": {"nur": "lebenslauf"},
     "kategorie": "Jobsuche & Bewerbung", "titel": "Lebenslauf",
     "beschreibung": "Nur den Lebenslauf zu einer Stelle anpassen",
     "icon": "file", "standard": False},
    {"id": "bewerbung_schreiben_anschreiben", "prompt": "bewerbung_schreiben",
     "parameter": {"nur": "anschreiben"},
     "kategorie": "Jobsuche & Bewerbung", "titel": "Anschreiben",
     "beschreibung": "Nur das Anschreiben zu einer Stelle",
     "icon": "pen", "standard": False},
    # v1.7.32 (#981 D / #979 D): hiess "Inbound erfassen / Recruiter hat
    # sich gemeldet" — ein anderer Anwendungsfall als der, den der Prompt
    # bedient. Faellt aus dem Standard, bleibt waehlbar.
    {"id": "auto_bewerbung", "prompt": "auto_bewerbung",
     "kategorie": "Jobsuche & Bewerbung", "titel": "Bewerbung aus Anzeige",
     "beschreibung": "URL oder Anzeigentext rein, Bewerbung raus",
     "icon": "mail", "standard": False},
    # Rueckt in den Standard nach, weil "Bewerbung aus Anzeige" ihn
    # verlaesst (#979 E) — sonst haette die Kategorie nur zwei Karten,
    # waehrend die anderen drei haben.
    {"id": "bewerbung_vorbereitung", "prompt": "bewerbung_vorbereitung",
     "kategorie": "Jobsuche & Bewerbung", "titel": "Bewerbung vorbereiten",
     "beschreibung": "Schritt fuer Schritt zur fertigen Bewerbung",
     "icon": "check", "standard": True},
    {"id": "dokumente_verarbeiten", "prompt": "dokumente_verarbeiten",
     "kategorie": "Jobsuche & Bewerbung", "titel": "Dokumente einsortieren",
     "beschreibung": "Hochgeladene Dateien zuordnen und auswerten",
     "icon": "inbox", "standard": False},

    # ── Interview & Verhandlung ────────────────────────────────────
    {"id": "interview_vorbereitung", "prompt": "interview_vorbereitung",
     "kategorie": "Interview & Verhandlung", "titel": "Interview vorbereiten",
     "beschreibung": "Typische Fragen ueben",
     "icon": "briefcase", "standard": True},
    {"id": "interview_simulation", "prompt": "interview_simulation",
     "kategorie": "Interview & Verhandlung", "titel": "Uebungsgespraech",
     "beschreibung": "Probelauf mit Claude",
     "icon": "mic", "standard": True},
    {"id": "gehaltsverhandlung", "prompt": "gehaltsverhandlung",
     "kategorie": "Interview & Verhandlung", "titel": "Gehalt verhandeln",
     "beschreibung": "Strategie besprechen",
     "icon": "coins", "standard": True},

    # ── Analyse & Strategie ────────────────────────────────────────
    {"id": "profil_analyse", "prompt": "profil_analyse",
     "kategorie": "Analyse & Strategie", "titel": "Staerken erkennen",
     "beschreibung": "Was kann ich besonders gut?",
     "icon": "chart", "standard": True},
    {"id": "profil_ueberpruefen", "prompt": "profil_ueberpruefen",
     "kategorie": "Analyse & Strategie", "titel": "Profil-Check",
     "beschreibung": "Fehler finden und korrigieren",
     "icon": "usercheck", "standard": True},
    {"id": "ablehnungs_coaching", "prompt": "ablehnungs_coaching",
     "kategorie": "Analyse & Strategie", "titel": "Aus Absagen lernen",
     "beschreibung": "Muster erkennen, Strategie anpassen",
     "icon": "trending", "standard": True},
    {"id": "netzwerk_strategie", "prompt": "netzwerk_strategie",
     "kategorie": "Analyse & Strategie", "titel": "Netzwerk aufbauen",
     "beschreibung": "Kontakte gezielt nutzen",
     "icon": "network", "standard": False},

    # ── Weitere ────────────────────────────────────────────────────
    {"id": "tipps_und_tricks", "prompt": "tipps_und_tricks",
     "kategorie": "Weitere", "titel": "Tipps & Tricks",
     "beschreibung": "Versteckte Funktionen entdecken",
     "icon": "sparkles", "standard": False},
    {"id": "problem_melden", "prompt": "problem_melden",
     "kategorie": "Weitere", "titel": "Problem melden",
     "beschreibung": "Erst Soforthilfe, dann ein sauberer Fehlerbericht",
     "icon": "bug", "standard": False},
    {"id": "faq", "prompt": "faq",
     "kategorie": "Weitere", "titel": "FAQ",
     "beschreibung": "Erste-Schritte-Guide",
     "icon": "help", "standard": False},
)

# Wo die Nutzerauswahl liegt. Muster wie `onboarding_hints_dismissed`
# (#652) und die Befund-Abweisung (#825): ein Schluessel in
# `profile_settings`, damit die Auswahl Update und Neustart ueberlebt.
EINSTELLUNG = "dashboard_prompt_shortcuts"

_NACH_ID = {e["id"]: e for e in EINTRAEGE}


def eintrag(eintrag_id: str) -> dict | None:
    return _NACH_ID.get(eintrag_id)


def alle() -> list[dict]:
    """Der Katalog in Anzeige-Reihenfolge."""
    def schluessel(e):
        k = e["kategorie"]
        return (KATEGORIEN.index(k) if k in KATEGORIEN else 999, e["titel"])
    return [dict(e) for e in sorted(EINTRAEGE, key=schluessel)]


def standard_auswahl() -> list[str]:
    """Der Schnellzugriff, solange der Nutzer nichts gewaehlt hat."""
    return [e["id"] for e in alle() if e.get("standard")]


def auswahl(db) -> list[str]:
    """Die Auswahl des Nutzers, oder der Katalog-Standard.

    Unbekannte Kennungen fallen still weg — sonst wuerde ein entfernter
    Katalogeintrag den Schnellzugriff einer Bestandsinstallation
    zerlegen.
    """
    try:
        roh = db.get_profile_setting(EINSTELLUNG, None)
    except Exception:
        roh = None
    if not isinstance(roh, list):
        return standard_auswahl()
    gewaehlt = [str(x) for x in roh if str(x) in _NACH_ID]
    return gewaehlt or standard_auswahl()


def auswahl_setzen(db, eintrag_ids) -> dict:
    """Auswahl speichern. Gibt zurueck, was uebernommen wurde."""
    ids = [str(x) for x in (eintrag_ids or [])]
    gueltig = [x for x in ids if x in _NACH_ID]
    unbekannt = [x for x in ids if x not in _NACH_ID]
    db.set_profile_setting(EINSTELLUNG, gueltig)
    return {"uebernommen": gueltig, "unbekannt": unbekannt}


def schnellzugriff(db) -> list[dict]:
    """Die Eintraege des Schnellzugriffs, in Katalog-Reihenfolge."""
    gewaehlt = set(auswahl(db))
    return [e for e in alle() if e["id"] in gewaehlt]
