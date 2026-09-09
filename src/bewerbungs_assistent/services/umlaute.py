"""Umlaut-Restaurierung als kuratierte Positivliste (#742, seit v1.7.5).

Hier lag die Liste bis v1.7.60 in `tools/profil.py`. Sie ist jetzt ein
Dienst, weil sie einen zweiten Aufrufer bekommen hat: die Dokument-
Regeln aus #1006 verlangen echte Umlaute in JEDER erzeugten Ausgabe,
und eine zweite Heuristik daneben waere das Muster aus #963/#991 — bei
einer kuratierten Wortliste besonders teuer, weil die beiden Fassungen
schon nach der ersten Ergaenzung auseinanderlaufen.

**Warum Positivliste und nicht Regel:** "ae/oe/ue" ist im Deutschen
nicht immer ein umschriebener Umlaut ("Baer" ja, "Aeon", "Poesie",
"Duell" nein). Eine Regel wuerde raten; die Liste weiss es. Der Preis
ist Pflege — dafuer meldet `ungemappte_kandidaten()`, was noch fehlt.
"""
import re

UMLAUT_REPAIR_MAP = {
    # haeufige Funktionswoerter
    "fuer": "für", "ueber": "über", "waehrend": "während",
    "zusaetzlich": "zusätzlich", "zusaetzliche": "zusätzliche",
    "spaeter": "später", "frueher": "früher", "fruehzeitig": "frühzeitig",
    "naechste": "nächste", "naechsten": "nächsten", "naechster": "nächster",
    "taeglich": "täglich", "jaehrlich": "jährlich", "staendig": "ständig",
    "koennen": "können", "koennte": "könnte", "koennten": "könnten",
    "moeglich": "möglich", "moegliche": "mögliche",
    "moeglichkeit": "möglichkeit", "moeglichkeiten": "möglichkeiten",
    # Fuehrung / Taetigkeit
    "fuehrung": "führung", "fuehren": "führen", "gefuehrt": "geführt",
    "fuehrungskraft": "führungskraft", "fuehrungskraefte": "führungskräfte",
    "durchfuehrung": "durchführung", "durchgefuehrt": "durchgeführt",
    "einfuehrung": "einführung", "eingefuehrt": "eingeführt",
    "ausfuehrung": "ausführung", "ausfuehrlich": "ausführlich",
    "weitergefuehrt": "weitergeführt", "fortgefuehrt": "fortgeführt",
    "geschaeftsfuehrer": "geschäftsführer",
    "geschaeftsfuehrend": "geschäftsführend",
    "geschaeftsfuehrender": "geschäftsführender",
    "geschaeftsfuehrung": "geschäftsführung",
    "taetigkeit": "tätigkeit", "taetigkeiten": "tätigkeiten", "taetig": "tätig",
    "zustaendig": "zuständig", "zustaendigkeit": "zuständigkeit",
    "zustaendigkeiten": "zuständigkeiten",
    "selbststaendig": "selbstständig", "selbststaendige": "selbstständige",
    "eigenstaendig": "eigenständig", "eigenstaendige": "eigenständige",
    "vollstaendig": "vollständig", "vollstaendige": "vollständige",
    "vollstaendigkeit": "vollständigkeit",
    # Qualitaet / Kompetenz
    "qualitaet": "qualität", "qualitaeten": "qualitäten",
    "qualitaetssicherung": "qualitätssicherung",
    "qualitaetsmanagement": "qualitätsmanagement",
    "aktivitaet": "aktivität", "aktivitaeten": "aktivitäten",
    "produktivitaet": "produktivität", "flexibilitaet": "flexibilität",
    "stabilitaet": "stabilität", "kapazitaet": "kapazität",
    "kapazitaeten": "kapazitäten", "universitaet": "universität",
    "faehigkeit": "fähigkeit", "faehigkeiten": "fähigkeiten",
    "leistungsfaehig": "leistungsfähig",
    "leistungsfaehigkeit": "leistungsfähigkeit",
    "zuverlaessig": "zuverlässig", "zuverlaessigkeit": "zuverlässigkeit",
    "verfuegbarkeit": "verfügbarkeit", "verfuegbar": "verfügbar",
    # Loesung / Unterstuetzung
    "loesung": "lösung", "loesungen": "lösungen",
    "aufloesung": "auflösung", "abloesung": "ablösung", "erloes": "erlös",
    "erloese": "erlöse", "unterstuetzung": "unterstützung",
    "unterstuetzt": "unterstützt", "unterstuetzte": "unterstützte",
    "unterstuetzen": "unterstützen",
    # Pruefung / Klaerung
    "pruefung": "prüfung", "pruefungen": "prüfungen", "pruefen": "prüfen",
    "geprueft": "geprüft", "ueberpruefung": "überprüfung",
    "ueberprueft": "überprüft", "klaerung": "klärung", "geklaert": "geklärt",
    "erklaerung": "erklärung", "abklaerung": "abklärung",
    # ueber-Komposita
    "ueberblick": "überblick", "uebersicht": "übersicht",
    "uebergabe": "übergabe", "uebernahme": "übernahme",
    "uebernommen": "übernommen", "uebertragung": "übertragung",
    "uebergreifend": "übergreifend", "uebergreifende": "übergreifende",
    "ueberzeugt": "überzeugt", "ueberzeugung": "überzeugung",
    "ueberfuehrung": "überführung", "ueberwachung": "überwachung",
    "uebereinstimmung": "übereinstimmung",
    # rueck / schluessel
    "zurueck": "zurück", "rueckmeldung": "rückmeldung",
    "rueckmeldungen": "rückmeldungen", "ruecksprache": "rücksprache",
    "rueckbau": "rückbau", "schluessel": "schlüssel",
    "schluesselrolle": "schlüsselrolle", "anschluesse": "anschlüsse",
    "beruecksichtigung": "berücksichtigung",
    "beruecksichtigt": "berücksichtigt",
    # ae-Woerter
    "mehrjaehrig": "mehrjährig", "mehrjaehrige": "mehrjährige",
    "mehrjaehriger": "mehrjähriger", "langjaehrig": "langjährig",
    "langjaehrige": "langjährige", "langjaehriger": "langjähriger",
    "vertraege": "verträge", "geraete": "geräte", "ablaeufe": "abläufe",
    "arbeitsablaeufe": "arbeitsabläufe", "geschaeftsablaeufe": "geschäftsabläufe",
    "maerkte": "märkte", "laender": "länder", "traeger": "träger",
    "staerken": "stärken", "gestaerkt": "gestärkt", "verstaerkt": "verstärkt",
    "verstaendnis": "verständnis", "verstaendlich": "verständlich",
    "bestaetigt": "bestätigt", "bestaetigung": "bestätigung",
    "geschaetzt": "geschätzt", "schaetzung": "schätzung",
    "gewaehrleistet": "gewährleistet", "gewaehrleistung": "gewährleistung",
    "bewaehrt": "bewährt", "bewaehrte": "bewährte",
    "ausgewaehlt": "ausgewählt", "auswaehlen": "auswählen",
    "erwaehnt": "erwähnt", "gefaehrdung": "gefährdung",
    "verlaengerung": "verlängerung", "verlaengert": "verlängert",
    "praesentation": "präsentation", "praesentationen": "präsentationen",
    "praesentiert": "präsentiert", "repraesentiert": "repräsentiert",
    "praezise": "präzise", "praezision": "präzision",
    # oe-Woerter
    "oekosystem": "ökosystem", "oekonomisch": "ökonomisch",
    "oeffentlich": "öffentlich", "oeffentliche": "öffentliche",
    "oeffentlichkeit": "öffentlichkeit", "oertlich": "örtlich",
    "erhoehung": "erhöhung", "erhoeht": "erhöht", "hoehere": "höhere",
    "hoehe": "höhe", "verzoegerung": "verzögerung",
    "verzoegerungen": "verzögerungen", "verzoegert": "verzögert",
    "gehoert": "gehört", "zugehoerig": "zugehörig",
    "zugehoerigkeit": "zugehörigkeit", "loeschen": "löschen",
    "geloescht": "gelöscht", "stoerung": "störung", "stoerungen": "störungen",
    "foerderung": "förderung", "gefoerdert": "gefördert",
    "persoenlich": "persönlich", "persoenliche": "persönliche",
    "persoenlichkeit": "persönlichkeit",
    "erfuellt": "erfüllt", "erfuellung": "erfüllung",
    "verkuerzt": "verkürzt", "verkuerzung": "verkürzung",
    # #1006: in fast jedem Lebenslauf, fehlte trotzdem — gefunden vom
    # Regel-Pruefer an einem erzeugten Dokument.
    "verfuegt": "verfügt", "verfuegen": "verfügen",
    "verfuegbar": "verfügbar", "verfuegbarkeit": "verfügbarkeit",
    "verfuegung": "verfügung", "gefuehrt": "geführt",
    "durchgefuehrt": "durchgeführt", "eingefuehrt": "eingeführt",
    "einfuehrung": "einführung", "ausgefuehrt": "ausgeführt",
    "zusammengefuehrt": "zusammengeführt",
}

WORT_RE = re.compile(r"[A-Za-zÄÖÜäöüß]+")
KANDIDAT_RE = re.compile(r"(ae|oe|ue)", re.IGNORECASE)


def umlaute_reparieren(text):
    """Ersetzt NUR Woerter aus der kuratierten Map, case-erhaltend.

    Returns (neuer_text, [(von, nach), ...]).
    """
    ersetzungen = []

    def _repl(m):
        wort = m.group(0)
        ziel = UMLAUT_REPAIR_MAP.get(wort.lower())
        if not ziel:
            return wort
        if wort.isupper():
            neu = ziel.upper()
        elif wort[0].isupper():
            neu = ziel[0].upper() + ziel[1:]
        else:
            neu = ziel
        if neu != wort:
            ersetzungen.append((wort, neu))
        return neu

    return WORT_RE.sub(_repl, text or ""), ersetzungen
