"""Werkzeugkatalog: Tag, Beschreibung und Parametertexte je Werkzeug (H21, #1087 G1, G14).

Bis v1.7.134 bekam Claude 261 Werkzeuge mit zusammen rund 175.000
Zeichen Beschreibung, darin 327 Issue-Verweise und die Entwicklungs-
geschichte jedes Werkzeugs. Rund 50 davon sind Reparatur-, Nachzieh- und
Diagnosewerkzeuge, die im Alltag niemand braucht; sie standen
ungekennzeichnet neben `stellen_anzeigen`.

Hier entsteht, was Claude beim Registrieren sieht:

* **Tag** — genau einer aus `alltag`, `einstellung`, `wartung`,
  `entwickler`. `wartung` und `entwickler` sind nur im Expertenmodus
  sichtbar (`EXPERTEN_TAGS`, Einstellung `expertenmodus`).
* **Beschreibung** — Zweck und Einsatz in hoechstens `MAX_ZEICHEN`
  Zeichen, ohne Issue-Nummern und Versionsgeschichte. Kuratiert fuer die
  Werkzeuge des Kernwegs (`KURZ`), sonst aus dem Docstring abgeleitet.
  Der Docstring bleibt die Entwicklerdokumentation im Code.
* **Parametertexte** — aus dem `Args:`-Block, je Parameter im
  Eingabeschema statt im Fliesstext. Dorthin gehoeren sie: Claude liest
  sie beim Aufruf, nicht beim Auswaehlen.

Ein Werkzeug, das hier fehlt, gilt als `alltag`. Ein Guard prueft, dass
jeder Name in den Listen registriert ist und dass kein sichtbarer Text
ein ausgeblendetes Werkzeug nennt, ohne den Expertenmodus zu erwaehnen.
"""
from __future__ import annotations

import re

MAX_ZEICHEN = 600
MAX_PARAMETER = 300
TAGS = ("alltag", "einstellung", "wartung", "entwickler")
EXPERTEN_TAGS = frozenset({"wartung", "entwickler"})

# Einmalige Reparaturen, Nachzieh- und Migrationslaeufe: nichts davon
# gehoert in einen Bewerbungsalltag. Nur im Expertenmodus sichtbar.
WARTUNG = frozenset({
    "ablehnungsgruende_vereinheitlichen",
    "automatik_uebertragungen_pruefen",
    "beschreibungen_nachladen_bestand",
    "bewerbung_notiz_drift",
    "bewerbung_notizen_zusammenfuehren",
    "bewerbungs_stellen_abgleichen",
    "dokument_typen_nachziehen",
    "dokumente_text_nachziehen",
    "gehaelter_neu_auswerten",
    "phantom_termine_bereinigen",
    "profil_umlaute_reparieren",
    "quellen_aus_urls_korrigieren",
    "recherche_notizen_zusammenfuehren",
    "skills_bereinigen",
    "stellen_dubletten_pruefen",
    "stellen_merkmale_nachziehen",
    "stellen_qualitaet_pruefen",
    "stellen_urls_heilen",
    "termin_dubletten_bereinigen",
    "verwaiste_stellenrefs_bereinigen",
})

# Werkzeuge zum Untersuchen von PBP selbst.
ENTWICKLER = frozenset({
    "extraktions_verlauf",
    "pbp_mcp_diagnose",
})

# Einstellungen: sichtbar, aber kein Arbeitsschritt.
EINSTELLUNG = frozenset({
    "ablehnungsgrund_aktivieren_setzen", "ablehnungsgrund_anlegen",
    "ablehnungsgrund_loeschen", "ablehnungsgrund_umbenennen",
    "ablage_ordner", "ats_firmen_verwalten", "automatik_setzen",
    "automatik_status", "daten_bereiche_anzeigen",
    "daten_bereiche_leeren", "elwosa_pause", "elwosa_tonfall",
    "expertenmodus_setzen", "fahrstrecken_verwalten", "ki_features_lesen",
    "ki_features_setzen", "kontakt_kategorie_anlegen",
    "kontakt_kategorie_bearbeiten", "kontakt_kategorie_loeschen",
    "kontakt_kategorien_auflisten", "muss_tor_setzen", "ollama_autostart",
    "ollama_beenden", "ollama_kontext", "schnellzugriff_setzen",
    "schwelle_stufe_setzen", "scoring_konfigurieren", "stellen_entfernen_nach_quelle",
    "suchkriterien_bearbeiten", "suchkriterien_setzen", "telemetrie_setzen",
    "telemetrie_status", "umgang_mit_unbekannt_setzen",
})

# Kuratierte Beschreibungen fuer den Kernweg: Zweck, wann, wann nicht.
KURZ = {
    "profil_status": (
        "Prüft, ob es ein Profil gibt, und nennt den nächsten sinnvollen "
        "Schritt. Zu Beginn jedes Gesprächs aufrufen, bevor du etwas "
        "empfiehlst: ohne Profil ist der Weg die Ersterfassung "
        "(ersterfassung_starten), mit Profil nennt die Antwort, was als "
        "Nächstes fehlt (Suchbegriffe, erste Suche, offene Stellen). Liest "
        "nur, verändert nichts."),
    "stellen_anzeigen": (
        "Listet die gespeicherten Stellen, sortiert nach Punkten; Stellen "
        "mit fachlichem k.o. stehen am Ende. Nutzen, wenn der Mensch sehen "
        "will, was gefunden wurde, oder bevor du eine Stelle einordnest. "
        "Nicht für neue Treffer — dafür jobsuche_starten. Punkte messen, "
        "wie gut eine Anzeige die Suchbegriffe trifft, nicht die Passung "
        "zum Lebenslauf. Jede Stelle trägt einen Link ins Dashboard."),
    "fit_analyse": (
        "Liefert für eine Stelle den vollen Anzeigentext, die getroffenen "
        "und fehlenden Suchbegriffe, Rahmen (Entfernung, Gehalt, Remote) und "
        "eine Einordnung. Nutzen, bevor du über eine einzelne Stelle "
        "urteilst. Liest nur. Hast du Anzeige und Profil gelesen, speichere "
        "dein Urteil mit stelle_urteil_speichern — sonst bleibt die Stelle "
        "'nicht beurteilt'."),
    "stelle_einordnen": (
        "Ordnet eine Stelle ein: behalten ('passt') oder aussortieren "
        "('passt_nicht' mit Grund aus der Liste). Nutzen für einzelne "
        "Stellen nach einer Entscheidung des Menschen. Für viele Stellen "
        "stellen_bulk_bewerten, für ein gelesenes Urteil "
        "stelle_urteil_speichern. Nur Gruende aus 'verfuegbare_gruende' "
        "verwenden, nie eigene erfinden."),
    "stellen_bulk_bewerten": (
        "Sortiert viele Stellen auf einmal nach Filtern aus (Punkte, "
        "Titelwörter, Beschreibungswörter, Quelle, Alter). Arbeitet nur in "
        "der Datenbank, ohne KI, und kostet deshalb nichts. Erst mit "
        "dry_run=True die Vorschau zeigen und bestaetigen lassen, dann mit "
        "dry_run=False anwenden. Nicht für einzelne Stellen — dafür "
        "stelle_einordnen. Aussortieren ist umkehrbar (stelle_reaktivieren)."),
    "jobsuche_starten": (
        "Startet eine Suche über die gewählten Jobbörsen im Hintergrund "
        "und gibt eine job_id zurück. Nutzen, wenn Suchbegriffe gesetzt "
        "sind und neue Stellen gebraucht werden. Nicht warten und nicht in "
        "einer Schleife pruefen: den Stand fragt jobsuche_status(), auch "
        "ohne job_id. Browser-Jobbörsen nennt die Antwort gesondert."),
    "jobsuche_status": (
        "Zeigt Stand und Ergebnis einer Jobsuche: Fortschritt, neue Stellen "
        "je Quelle, Quellen ohne Ergebnis. Ohne job_id die letzte Suche — so "
        "funktioniert es auch in einem neuen Gespräch. Einmal fragen, wenn "
        "der Mensch wissen will, wie weit die Suche ist; nicht in einer "
        "Schleife aufrufen. Neue Stellen zeigt danach stellen_anzeigen."),
    "bewerbung_erstellen": (
        "Legt eine Bewerbung an (Firma, Titel, Status, optional Stelle, "
        "Kontakt, Notiz). Nutzen, wenn sich der Mensch beworben hat oder es "
        "gleich tut. Vorher firma_kontext aufrufen, damit keine doppelte "
        "Bewerbung entsteht. Für Änderungen bewerbung_bearbeiten, für "
        "einen Statuswechsel bewerbung_status_aendern."),
    "bewerbung_status_aendern": (
        "Setzt den Status einer Bewerbung (beworben, Interview, "
        "Zweitgespraech, Angebot, angenommen, abgelehnt, zurueckgezogen), "
        "mit optionaler Notiz und Absagegrund; der Verlauf bekommt einen "
        "Eintrag. Nutzen, wenn sich im Verfahren etwas tut. Absagegründe "
        "nur aus der Liste oder aus dem, was die Firma geschrieben hat — nie "
        "erfinden. Für andere Felder bewerbung_bearbeiten."),
    "bewerbung_bearbeiten": (
        "Ändert Felder einer Bewerbung: Titel, Firma, Ort, Gehalt, "
        "Ansprechpartner, Vermittler, Endkunde, Bewerbungsweg. Eine Notiz "
        "wird angehaengt, nie überschrieben. Nutzen, wenn sich Angaben "
        "aendern oder nachgetragen werden. Für den Status "
        "bewerbung_status_aendern, für eine reine Notiz bewerbung_notiz, "
        "für Termine meeting_hinzufuegen."),
    "bewerbung_details": (
        "Zeigt eine Bewerbung vollstaendig: Stelle mit Anzeigentext, "
        "Verlauf, Termine, Dokumente, Kontakte, Recherche, offene Aufgaben "
        "und einen Link ins Dashboard. Nutzen, bevor du über eine "
        "Bewerbung sprichst, ein Anschreiben oder eine Vorbereitung baust "
        "oder etwas daran änderst. Liest nur. Für die Liste aller "
        "Bewerbungen bewerbungen_anzeigen."),
    "bewerbungen_anzeigen": (
        "Listet die Bewerbungen mit Status, Datum, Firma und Link ins "
        "Dashboard, optional nach Status gefiltert; abgeschlossene nur auf "
        "Wunsch. Nutzen für einen Überblick oder um eine Bewerbung zu "
        "finden. Für eine einzelne Bewerbung mit allem Drum und Dran "
        "bewerbung_details, für den Stand bei einer Firma firma_kontext. "
        "Liest nur."),
    "firma_kontext": (
        "Sagt, was PBP über eine Firma weiss: Bewerbungen mit Status, "
        "Stellen, Kontakte, Vermittler, Endkunden, Anfragen, Blacklist, "
        "jeweils mit Verweis, dazu eine Warnung vor Doppelvorstellung. "
        "IMMER aufrufen, bevor du etwas über den Stand bei einer Firma "
        "sagst oder eine Bewerbung anlegst — nie aus dem Gedächtnis "
        "antworten. Liest nur."),
    "suchkriterien_setzen": (
        "Setzt die Suchbegriffe (MUSS, PLUS, MINUS, Ausschluss), Regionen, "
        "Wohnort, Anstellungsformen und Entfernung — ersetzt die Listen "
        "komplett. Nutzen nach der Ersterfassung oder wenn der Mensch neu "
        "sortieren will. Einzelne Begriffe ändert suchkriterien_bearbeiten. "
        "Begriffe aus dem Profil ableiten, nicht raten."),
    "suchkriterien_anzeigen": (
        "Zeigt die aktuellen Suchbegriffe (MUSS, PLUS, MINUS, Ausschluss), "
        "Regionen, Wohnort, Entfernung, Gehaltsangaben und die Schwelle. "
        "Nutzen, bevor du Suchbegriffe vorschlägst, eine leere Trefferliste "
        "erklärst oder eine Suche startest. Liest nur; aendern mit "
        "suchkriterien_setzen (alles) oder suchkriterien_bearbeiten "
        "(einzelne Begriffe)."),
    "stelle_urteil_speichern": (
        "Speichert dein Urteil über eine Stelle, nachdem du Anzeige und "
        "Profil gelesen hast (empfohlen, bedingt, nicht_empfohlen), mit "
        "Begruendung. Nur nach echtem Lesen, etwa nach fit_analyse — ein "
        "Urteil aus den Punkten abzuleiten ist falsch. Das Urteil steht "
        "danach an der Stelle und in der Trefferliste, bis sich Profil oder "
        "Anzeige aendern."),
    "aufgaben_uebersicht": (
        "Zeigt alles Offene an einer Stelle: fällige und kommende "
        "Nachfassungen, Aufgaben und Termine, nach Fälligkeit sortiert, je "
        "mit Link ins Dashboard. Nutzen, wenn der Mensch fragt, was ansteht, "
        "oder zu Beginn einer Arbeitssitzung. Liest nur; erledigen mit "
        "follow_up_erledigen bzw. todo_erledigen, neue Aufgabe mit "
        "todo_anlegen."),
    "stelle_manuell_anlegen": (
        "Legt eine Stelle von Hand an (Titel, Firma, Anzeigentext, URL, "
        "Kontakt), etwa aus einer Mail, einem Anruf oder einem Link. Prüft "
        "Dubletten, Blacklist und frühere Bewerbungen bei derselben Firma. "
        "Ohne URL, Dokument oder Kontakt ist die Stelle später kaum "
        "wiederzufinden — dann nachfragen. Nicht für Treffer aus einer "
        "Jobbörse; die legt die Suche selbst an."),
    "profil_erstellen": (
        "Legt das Profil an oder ergänzt es (Name, Kontakt, Kurzprofil, "
        "Praeferenzen). Teil der Ersterfassung. Die Antwort nennt Dokumente, "
        "die dabei übernommen wurden, und den nächsten Schritt — meist "
        "extraktion_starten für den Lebenslauf. Nicht für ein zweites "
        "Profil: dafür neues_profil_erstellen, und nur nach Rückfrage."),
}


_PAREN_HISTORIE = re.compile(
    r"\s*\((?:[^()]*?(?:#\d|\bv\d+\.\d|beta\.\d|seit\s+v|\b[A-J]\d{1,2}\b)[^()]*?)\)")
_HISTORIE = re.compile(
    r"#\d{2,4}|\bv\d+\.\d+|beta\.\d+|\bBis v|\bseit v|Gemessen|Hintergrund|"
    r"Praxis-Fall|MERKE|Bug\b|\bFix\b|frueher|bisher|Bis hierher|Vorher", re.I)
_SATZ = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ`'\"(])")


def _abschnitte(doc: str) -> tuple[str, str]:
    """(Beschreibung, Args-Block) aus einem Docstring."""
    m = re.search(r"^\s*(Args|Arguments|Parameter)\s*:\s*$", doc, re.M)
    if not m:
        return doc, ""
    rest = doc[m.end():]
    ende = re.search(r"^\s*(Returns|Rueckgabe|Raises|Beispiel)\s*:\s*$", rest, re.M)
    return doc[:m.start()], rest[:ende.start()] if ende else rest


def _saetze(text: str):
    for absatz in re.split(r"\n\s*\n", text):
        flach = " ".join(z.strip() for z in absatz.strip().splitlines())
        if not flach:
            continue
        flach = _PAREN_HISTORIE.sub("", flach)
        for s in _SATZ.split(flach):
            yield s.strip()


def ohne_historie(text: str) -> str:
    """Saetze ohne Versions- und Issue-Geschichte, ein Absatz."""
    teile = [s for s in _saetze(text) if s and not _HISTORIE.search(s)]
    return " ".join(teile)


def kuerzen(text: str, grenze: int = MAX_ZEICHEN) -> str:
    """Auf `grenze` Zeichen, an einer Satzgrenze."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= grenze:
        return text
    stueck = text[:grenze]
    punkt = max(stueck.rfind(". "), stueck.rfind("! "), stueck.rfind("? "))
    if punkt >= grenze // 3:
        return stueck[:punkt + 1]
    wort = stueck[:grenze - 2].rfind(" ")
    return stueck[:wort].rstrip(",;:") + " …"


def beschreibung(name: str, doc: str) -> str:
    """Die Beschreibung, die Claude beim Auswaehlen liest."""
    if name in KURZ:
        return KURZ[name]
    text, _ = _abschnitte(doc or "")
    kurz = kuerzen(ohne_historie(text))
    if not kurz:
        # Ein Docstring aus nichts als Geschichte: die erste Zeile traegt
        # trotzdem den Zweck.
        erster = re.split(r"\n\s*\n", text.strip())[0] if text.strip() else name
        erster = " ".join(z.strip() for z in erster.splitlines())
        erster = re.sub(r"^\s*(?:v\d+\.\d+(?:\.\d+)?(?:-beta\.\d+)?|beta\.\d+)\s*[:,-]?\s*", "", erster)
        erster = _PAREN_HISTORIE.sub("", erster)
        kurz = kuerzen(re.sub(r"\s*\(?#\d{2,4}[^)\s]*\)?", "", erster))
    # Ein Einzeiler wie "Listet Todos." sagt nicht, womit man ihn aufruft:
    # die Parameternamen gehoeren dann in den Satz.
    parameter = list(parameter_texte(doc or ""))
    if len(kurz) < 120 and parameter:
        kurz = kuerzen(f"{kurz} Parameter: {', '.join(parameter)}.")
    return kurz


def parameter_texte(doc: str) -> dict[str, str]:
    """Je Parameter der Text aus dem Args-Block, ohne Geschichte."""
    _, args = _abschnitte(doc or "")
    if not args:
        return {}
    aus: dict[str, list[str]] = {}
    aktuell = None
    einzug = None
    for zeile in args.splitlines():
        if not zeile.strip():
            continue
        m = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^)]*\))?\s*:\s*(.*)$", zeile)
        tiefe = len(zeile) - len(zeile.lstrip())
        if m and (einzug is None or tiefe <= einzug):
            einzug = tiefe
            aktuell = m.group(2)
            aus[aktuell] = [m.group(3)]
        elif aktuell:
            aus[aktuell].append(zeile.strip())
    ergebnis = {}
    for name, teile in aus.items():
        text = ohne_historie(" ".join(teile)) or re.sub(
            r"\s*\(?#\d{2,4}[^)\s]*\)?", "", " ".join(teile)).strip()
        if text:
            ergebnis[name] = kuerzen(text, MAX_PARAMETER)
    return ergebnis


# H29 (#1087 G11): alte Namen, die einen Release lang weiter erreichbar
# sind. Ein Alias traegt den Tag seines neuen Namens.
ALIASE = {
    "stelle_bewerten": "stelle_einordnen",
    "stelle_analyse_speichern": "stelle_urteil_speichern",
    "jobtitel_vorschlagen": "jobtitel_speichern",
}


def tag(name: str) -> str:
    name = ALIASE.get(name, name)
    if name in WARTUNG:
        return "wartung"
    if name in ENTWICKLER:
        return "entwickler"
    if name in EINSTELLUNG:
        return "einstellung"
    return "alltag"


def ausgeblendet(name: str) -> bool:
    return tag(name) in EXPERTEN_TAGS


def expertenmodus(db) -> bool:
    """Vorgabe AUS: wer nichts einstellt, sieht nur Alltag und Einstellungen."""
    try:
        return db.get_setting("expertenmodus", False) is True
    except Exception:
        return False


def beim_start_sichtbar(db) -> bool:
    """Was der Server beim Start zeigt: die Einstellung, oder
    `BA_EXPERTENMODUS=1` (Testumgebung und Fehlersuche — die Suite ruft
    Wartungswerkzeuge direkt auf und braucht sie sichtbar)."""
    import os
    return os.environ.get("BA_EXPERTENMODUS") == "1" or expertenmodus(db)


def expertenmodus_setzen(db, an: bool) -> dict:
    db.set_setting("expertenmodus", bool(an))
    ausgeblendet_ = sorted(WARTUNG | ENTWICKLER)
    return {
        "expertenmodus": bool(an),
        "werkzeuge": ausgeblendet_,
        "anzahl": len(ausgeblendet_),
        "wirkung": (
            f"{len(ausgeblendet_)} Wartungs- und Entwicklerwerkzeuge sind "
            + ("jetzt sichtbar." if an else "jetzt ausgeblendet.")
            + " Erscheinen sie in Claude nicht sofort: Claude Desktop neu starten."),
    }


def sichtbarkeit_anwenden(mcp, an: bool) -> None:
    """Blendet Wartungs- und Entwicklerwerkzeuge aus oder ein."""
    if an:
        mcp.enable(tags=set(EXPERTEN_TAGS))
    else:
        mcp.disable(tags=set(EXPERTEN_TAGS))
