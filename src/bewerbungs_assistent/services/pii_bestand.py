"""Prueft ausgehende Texte gegen den EIGENEN Datenbestand (#946, v1.7.22).

Umkehrung des vorhandenen Pruefers: `scripts/scrub_pii.py` sucht eine
gepflegte Liste bekannter Namen im Repository-Inhalt. Dieser hier sucht
die Namen aus der Datenbank in einem Text, der gleich nach draussen geht.

Die zweite Richtung ist die zuverlaessigere, weil die Datenbank die
vollstaendige Liste hat: jede Firma, bei der sich der Nutzer je beworben
hat, jede gesichtete Stelle, jeder Kontakt. Eine gepflegte Liste ist
immer nur so gut wie ihre letzte Pflege — dreimal innerhalb von zwei
Tagen (siehe #919, #928, #940 bis #945) hat sie deshalb versagt.

Warum die Richtung ueberhaupt zaehlt: GitHub zeigt die
Bearbeitungshistorie. Nachtraegliches Ueberschreiben genuegt nicht, das
Original bleibt sichtbar — es hilft nur Loeschen, und das kann nur der
Eigentuemer. Ein Pruefschritt VOR dem Anlegen ist deshalb kein Komfort,
sondern die einzige Stelle, an der die Kontrolle noch wirkt.

Was ausdruecklich KEIN Treffer ist:

* **Quellennamen** (Jobportale, Aggregatoren, Personaldienstleister als
  Quelle). Sie benennen eine Datenquelle, keine Bewerbung — die
  dokumentierte DoD-9-Ausnahme.
* **Job-Hashes und interne IDs.** Ohne Datenbankzugriff bedeutungslos,
  fuer Regressionsfaelle aber unverzichtbar.
* **Der Klarname des Profil-Inhabers.** Bewusste Entscheidung.
* **Platzhalter**, die bereits vergeben wurden.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

# Namen unter dieser Laenge werden nie geprueft — "AG", "SE" oder ein
# zweibuchstabiges Kuerzel wuerde in jedem Text feuern.
MIN_NAMENSLAENGE = 3

# Bestandswerte, die keine Firma benennen.
GENERISCHE_WERTE = {
    "unbekannt", "unknown", "n/a", "na", "-", "--", "keine", "none",
    "null", "tbd", "k.a.", "ka", "diverse", "verschiedene",
}

# Gewoehnliche Woerter, die zufaellig auch ein Firmenname sein koennen.
# Ein Treffer darauf wird gemeldet, aber als `unsicher` markiert: der
# Pruefer soll nicht schweigen, aber auch nicht so tun, als sei jede
# Fundstelle gleich schwer. (Lehre aus der Telefon-Fehlalarm-Runde: wer
# bei korrektem Text Alarm gibt, wird beim zweiten Mal ignoriert.)
GEWOEHNLICHE_WOERTER = {
    # v1.7.53: gemessen am echten Bestand ueber alle 400 Issues. Diese
    # Eintraege stehen als Firma bzw. Person in der Datenbank, sind aber
    # keine — "sap" ist eine Technologie und kommt in 25 Issues vor,
    # "name" ist ein Platzhalter aus einem Import, "google" ein Portal.
    # Sie werden weiterhin GEMELDET, aber als unsicher: der Pruefer soll
    # nicht schweigen und auch nicht so tun, als sei jede Fundstelle
    # gleich schwer.
    "sap", "name", "google", "beratung", "personalberatung", "vermittler",
    "comet", "atlas", "orion", "delta", "alpha", "beta", "gamma", "nova",
    "phoenix", "apex", "prime", "core", "next", "future", "vision",
    "global", "digital", "smart", "data", "cloud", "group", "partner",
    "consulting", "engineering", "solutions", "systems", "services",
    "technologies", "software", "energy", "medical", "capital",
}

_WORTGRENZE_VOR = r"(?<![\w\-])"
_WORTGRENZE_NACH = r"(?![\w\-])"

# Rechtsform-Zusaetze. Steht einer davon direkt hinter dem Namen, ist die
# Nennung eindeutig eine Firma — auch wenn der Name wie ein Alltagswort
# aussieht.
_RECHTSFORM = re.compile(
    r"\s*(?:gmbh|ag|se|kg|ug|mbh|gbr|ggmbh|ohg|plc|llc|group|holding|ltd\.?|inc\.?|b\.?v\.?|n\.?v\.?|e\.?\s?v\.?|&\s*co\.?(?:\s*kg)?)\b",
    re.IGNORECASE,
)


# Artikel und Pronomen, die einen Gattungsnamen ankuendigen. Vor einem
# Firmennamen stehen sie im Deutschen praktisch nie.
_BEGLEITER = frozenset({
    "der", "die", "das", "den", "dem", "des",
    "ein", "eine", "einer", "eines", "einem", "einen",
    "kein", "keine", "keiner", "keines", "keinem", "keinen",
    "dieser", "diese", "dieses", "diesem", "diesen",
    "jeder", "jede", "jedes", "jedem", "jeden",
    "mein", "meine", "meiner", "meinem", "meinen",
    "sein", "seine", "ihr", "ihre", "unser", "unsere",
    "welche", "welcher", "welches", "manche", "solche", "solcher",
})


def _treffer_ist_unsicher(name: str, text: str, start: int, ende: int) -> str:
    """Warum ist dieser Treffer nicht belastbar? Leerer String = belastbar.

    v1.7.24 (#962): Personaldienstleister und Beratungen heissen
    regelmaessig wie Alltagswoerter. In einem laengeren deutschen
    Fliesstext trifft das mit hoher Wahrscheinlichkeit — belegt an dem
    Wort "alten" in "den alten und den neuen Typ", das als harter
    Firmentreffer mit der Aufforderung "NICHT veroeffentlichen"
    gemeldet wurde.

    Ein Fehlalarm mit derselben Dringlichkeit wie ein echter Fund
    trainiert genau das Gegenteil dessen, wofuer der Pruefer da ist:
    nach dem dritten Mal wird der Hinweis ueberlesen, und dann faellt
    auch der echte Treffer durch (#825).

    Unterschieden wird nach der WORTFORM im Text, nicht nach einer
    Wortliste — eine gepflegte Liste deutscher Alltagswoerter waere
    nie vollstaendig, und flektierte Formen ("alten") stehen ohnehin
    in keiner.
    """
    # Rechtsform direkt dahinter: eindeutig eine Firma. Diese Pruefung
    # steht bewusst GANZ VORNE — sie schlaegt jedes Wortform-Argument,
    # auch bei einem Namen aus der Alltagswort-Liste ("Modern AG").
    if _RECHTSFORM.match(text[ende:ende + 24]):
        return ""

    # Mehrwort-Namen kollidieren praktisch nie zufaellig.
    if " " in name:
        return ""

    if name in GEWOEHNLICHE_WOERTER:
        return "Der Name ist zugleich ein gebraeuchliches Wort."

    # Kleingeschrieben: dann ist es ein Adjektiv, Adverb oder Verb —
    # deutsche Firmennamen werden grossgeschrieben.
    if text[start:ende][:1].islower():
        return ("Der Name steht hier kleingeschrieben und ohne "
                "Rechtsform — vermutlich ein gewoehnliches Wort, keine "
                "Firmennennung.")

    # Grossschreibung allein traegt im Deutschen NICHT: Substantive sind
    # immer grossgeschrieben, und gerade Personaldienstleister heissen
    # oft wie eines ("Feder", "Adler", "Krone"). Das unterscheidende
    # Merkmal ist der Artikel davor: ein Gattungsname steht mit
    # Begleiter ("die Feder im Mechanismus"), eine Firma ohne ("bei
    # Feder", "Feder hat abgesagt").
    davor = text[max(0, start - 40):start]
    letztes = re.findall(r"[\wÄÖÜäöüß]+", davor)
    if letztes and letztes[-1].lower() in _BEGLEITER:
        return ("Der Name steht hier mit Artikel ('%s') — im Deutschen "
                "das Kennzeichen eines Gattungsnamens, nicht einer "
                "Firmennennung." % letztes[-1])
    return ""


def _tabelle_anlegen(db) -> None:
    """Idempotentes Safety-Net ohne Schema-Bump.

    Muster wie `learned_insights` (#799): eine Tabelle, die beide
    Release-Linien brauchen, wird angelegt statt migriert — sonst
    kollidieren die Schema-Nummern zwischen Stable und Beta.
    """
    conn = db.connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS anonymisierung_map (
            echter_name  TEXT NOT NULL,
            art          TEXT NOT NULL,
            platzhalter  TEXT NOT NULL,
            angelegt_am  TEXT NOT NULL,
            PRIMARY KEY (echter_name, art)
        )
    """)
    conn.commit()


def _schluessel(name: str) -> str:
    return " ".join(name.lower().split())


def _quellen_namen() -> set[str]:
    """Registry-Keys UND Anzeigenamen der Quellen (DoD-9-Ausnahme)."""
    namen: set[str] = set()
    try:
        from ..job_scraper import SOURCE_REGISTRY
    except Exception:  # pragma: no cover - Registry immer vorhanden
        return namen
    for key, eintrag in (SOURCE_REGISTRY or {}).items():
        namen.add(_schluessel(str(key)))
        namen.add(_schluessel(str(key).replace("_", " ")))
        if isinstance(eintrag, dict):
            for feld in ("name", "label", "anzeigename"):
                wert = eintrag.get(feld)
                if wert:
                    namen.add(_schluessel(str(wert)))
    return namen


def _fiktive_namen() -> set[str]:
    """Platzhalter aus dem Repo-Pruefer — die sind ja gerade das Ziel."""
    try:
        import sys
        from pathlib import Path
        wurzel = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(wurzel / "scripts"))
        from scrub_pii import FIKTIVE_FIRMEN  # type: ignore
        return {_schluessel(f) for f in FIKTIVE_FIRMEN}
    except Exception:
        return set()


def _eigener_name(db) -> set[str]:
    """Der Klarname des Profil-Inhabers bleibt bewusst zulaessig."""
    namen: set[str] = set()
    try:
        conn = db.connect()
        for (wert,) in conn.execute("SELECT name FROM profile WHERE name IS NOT NULL"):
            if wert and wert.strip():
                namen.add(_schluessel(wert))
                for teil in str(wert).split():
                    if len(teil) >= MIN_NAMENSLAENGE:
                        namen.add(_schluessel(teil))
    except Exception:
        pass
    return namen


# Rechtsformen, die einen Firmennamen begleiten. Ein Text nennt die
# Firma fast nie so vollstaendig wie die Datenbank.
_RECHTSFORMEN = (
    "gmbh & co. kg", "gmbh & co kg", "gmbh", "ag", "kg", "ohg", "se",
    "mbh", "e.k.", "ug", "ltd", "llc", "inc", "corp", "plc", "b.v.",
    "n.v.", "s.a.", "s.p.a.", "a/s", "oy", "ab",
)

# Ein Namensteil unterhalb dieser Laenge taugt nicht als Suchbegriff —
# "BW" oder "TVS" traefe halbe Saetze. Bewusst hoeher als
# MIN_NAMENSLAENGE: dort geht es um den vollstaendigen Namen, hier um
# ein abgeleitetes Fragment, und ein Fragment muss mehr tragen.
MIN_VARIANTENLAENGE = 6


def schreibvarianten(name: str) -> list[str]:
    """Wie derselbe Name in einem Text sonst noch dastehen kann (#956).

    **Der Grund, warum es diese Funktion gibt.** Der Pruefer verglich bis
    v1.7.53 nur die VOLLSTAENDIGE gespeicherte Zeichenkette. Steht eine
    Firma im Bestand als "Musterwerk (Muster-Holding)", dann fand er
    weder "Musterwerk" noch "Muster-Holding" — und genau so schreibt
    man eine Firma in einem Fehlerbericht. Gemessen am 09.09.2026:
    zwei oeffentliche Issues trugen den Firmennamen aus dem echten
    Bestand, und der Pruefer meldete "sauber".

    **Ein Falsch-negativ in einem Schutzwerkzeug ist der teuerste
    Fehlertyp** — das ist woertlich die Lehre aus #929, und sie ist hier
    ein zweites Mal eingetreten.

    Die Gegenrichtung ist genauso wichtig (v1.7.24 MERKE 2): eine zu
    kurze Variante macht den Pruefer unbrauchbar, weil er dann bei
    jedem zweiten Satz anschlaegt. Deshalb `MIN_VARIANTENLAENGE` und
    die Aussortierung gewoehnlicher Woerter.
    """
    roh = (name or "").strip()
    if not roh:
        return []
    kandidaten = {roh}

    # "Musterwerk (Muster-Holding)" -> der Teil VOR der Klammer.
    #
    # Der Klammerinhalt bleibt bewusst draussen. Gemessen am echten
    # Bestand am 09.09.2026 steht dort weit oefter eine ANMERKUNG als
    # ein zweiter Firmenname: "(Vermittler)", "(Beratung)",
    # "(Personalberatung)", "(SAP PLM)", "(Bremen)". Als Suchbegriff
    # genommen erzeugte jede davon Fehlalarme ueber Dutzende Issues —
    # und ein Pruefer, dem niemand mehr glaubt, schuetzt gar nicht
    # (#929). Der vordere Teil traegt den Namen; nur er wird genommen.
    if "(" in roh:
        kandidaten.add(roh.split("(", 1)[0])

    # Trennzeichen, mit denen Quellen Zusaetze anhaengen
    for trenner in (" - ", " – ", " — ", " | ", ", "):
        if trenner in roh:
            kandidaten.add(roh.split(trenner, 1)[0])

    # Rechtsform abstreifen: "Musterwerk Hamburg GmbH" -> "Musterwerk Hamburg"
    for teil in list(kandidaten):
        klein = teil.strip().lower()
        for form in _RECHTSFORMEN:
            if klein.endswith(" " + form):
                kandidaten.add(teil.strip()[: -len(form)].strip())
                break

    ergebnis = []
    for kandidat in kandidaten:
        sauber = kandidat.strip(" .,-–—|")
        if not sauber or sauber == roh:
            continue
        if len(sauber) < MIN_VARIANTENLAENGE:
            continue
        # Ein Fragment, dessen Woerter ALLE gewoehnlich sind
        # ("Global Solutions"), ist als Suchbegriff wertlos: es steht so
        # in jedem zweiten Werbetext. Ein Pruefer, der bei korrektem
        # Text Alarm gibt, wird nach dem zweiten Mal ignoriert (#929).
        # Umgekehrt bleibt "Musterwerk Hamburg" drin, weil "musterwerk"
        # nichts Gewoehnliches ist.
        woerter = [_schluessel(w) for w in sauber.split() if w.strip()]
        if woerter and all(w in GEWOEHNLICHE_WOERTER for w in woerter):
            continue
        if _schluessel(sauber) in GENERISCHE_WERTE:
            continue
        ergebnis.append(sauber)
    # Laengste zuerst, damit die genaueste Fassung gemeldet wird.
    return sorted(set(ergebnis), key=len, reverse=True)


def _enthaelt_ausnahme(name: str, ausnahmen: set) -> bool:
    """Traegt dieser Name einen ausgenommenen Namen als ganzes Wort?

    Quellen- und Vermittlernamen sind ein FEATURE dieses Projekts
    (hays, ferchau, ...) und stehen bewusst in Issues. Eine abgeleitete
    Variante wie "hays ag" ist derselbe Name mit Zusatz und gehoert
    genauso ausgenommen — sonst holt die Variantenbildung genau die
    Namen zurueck, die die Ausnahmeliste heraushaelt.
    """
    if name in ausnahmen:
        return True
    woerter = set(name.split())
    # Mindestlaenge, damit ein kurzes Kuerzel aus der Ausnahmeliste
    # ("ab", "oy") nicht halbe Firmennamen stillstellt.
    return any(a in woerter for a in ausnahmen
               if " " not in a and len(a) >= 4)


def sammle_bestandsnamen(db) -> list[dict]:
    """Alle Firmen- und Personennamen aus dem eigenen Bestand.

    Die Ausnahmen werden hier bereits abgezogen, damit der Aufrufer sich
    nicht darum kuemmern muss.
    """
    conn = db.connect()
    roh: dict[str, str] = {}

    def _aufnehmen(wert: Any, art: str) -> None:
        if not wert:
            return
        name = str(wert).strip()
        if len(name) < MIN_NAMENSLAENGE:
            return
        if _schluessel(name) in GENERISCHE_WERTE:
            return
        # Firma gewinnt gegen Person, falls derselbe String beides ist.
        roh.setdefault(_schluessel(name), art)
        if art == "firma":
            roh[_schluessel(name)] = art

    abfragen = (
        ("SELECT DISTINCT company FROM applications", "firma"),
        ("SELECT DISTINCT company FROM jobs", "firma"),
        ("SELECT DISTINCT company FROM contacts", "firma"),
        ("SELECT DISTINCT full_name FROM contacts", "person"),
        ("SELECT DISTINCT ansprechpartner FROM applications", "person"),
    )
    for sql, art in abfragen:
        try:
            for (wert,) in conn.execute(sql):
                _aufnehmen(wert, art)
        except Exception:
            continue  # Tabelle/Spalte fehlt in aelteren Bestaenden

    ausnahmen = _quellen_namen() | _fiktive_namen() | _eigener_name(db)
    # Original-Schreibweise fuer die Ausgabe zurueckholen
    ergebnis = []
    gesehen_namen: set[str] = set()
    for schluessel, art in roh.items():
        # Bis v1.7.53 stand hier `schluessel in ausnahmen`, also
        # Gleichheit. Ein Vermittler, der im Bestand als "Hays AG"
        # steht, war damit NICHT ausgenommen, obwohl "hays" ausdruecklich
        # auf der Liste steht — und Vermittlernamen sind ein Feature
        # dieses Projekts, kein Geheimnis.
        if _enthaelt_ausnahme(schluessel, ausnahmen):
            continue
        if schluessel not in gesehen_namen:
            gesehen_namen.add(schluessel)
            ergebnis.append({"name": schluessel, "art": art})
        # #956: auch die Schreibvarianten suchen. Ohne sie findet der
        # Pruefer eine Firma nur dann, wenn sie WORTGLEICH so dasteht
        # wie in der Datenbank — und das ist im Fliesstext fast nie der
        # Fall.
        for variante in schreibvarianten(schluessel):
            schl = _schluessel(variante)
            if schl in gesehen_namen:
                continue
            # Die Ausnahmen greifen bei Varianten per WORT-Enthaltensein,
            # nicht per Gleichheit. Gemessen: "Hays AG (Vermittler)"
            # ergibt die Variante "hays ag" — und die stand nicht in der
            # Ausnahmeliste, obwohl "hays" ausdruecklich drin steht.
            # Eine Variante, die einen ausgenommenen Namen ENTHAELT, ist
            # derselbe ausgenommene Name mit Zusatz.
            if _enthaelt_ausnahme(schl, ausnahmen):
                continue
            gesehen_namen.add(schl)
            ergebnis.append({"name": schl, "art": art, "variante_von": schluessel})
    # Lange Namen zuerst: "Musterfirma Software GmbH" soll vor
    # "Musterfirma" greifen, sonst bleibt der Rest im Text stehen.
    ergebnis.sort(key=lambda e: len(e["name"]), reverse=True)
    return ergebnis


def platzhalter_fuer(db, name: str, art: str = "firma",
                     vorgabe: str = "") -> str:
    """Stabiler Platzhalter fuer einen Namen — ueber Aufrufe hinweg gleich.

    Ohne diese Bindung heisst dieselbe Firma im naechsten Issue anders,
    und Belegketten ueber mehrere Issues sind nicht mehr lesbar.
    """
    _tabelle_anlegen(db)
    conn = db.connect()
    schluessel = _schluessel(name)
    treffer = conn.execute(
        "SELECT platzhalter FROM anonymisierung_map WHERE echter_name=? AND art=?",
        (schluessel, art)).fetchone()
    if treffer:
        return treffer[0]

    if vorgabe:
        neu = vorgabe
    else:
        vergeben = {r[0] for r in conn.execute(
            "SELECT platzhalter FROM anonymisierung_map WHERE art=?", (art,))}
        stamm = "Firma" if art == "firma" else "Person"
        i = 1
        while f"{stamm} {_kennung(i)}" in vergeben:
            i += 1
        neu = f"{stamm} {_kennung(i)}"

    from datetime import datetime
    conn.execute(
        "INSERT OR REPLACE INTO anonymisierung_map "
        "(echter_name, art, platzhalter, angelegt_am) VALUES (?,?,?,?)",
        (schluessel, art, neu, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    return neu


def _kennung(i: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA."""
    zeichen = ""
    while i > 0:
        i, rest = divmod(i - 1, 26)
        zeichen = chr(65 + rest) + zeichen
    return zeichen


def _zeile_von(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def pruefe_text(db, text: str) -> dict:
    """Sucht Bestandsnamen im Text. Meldet Fundstelle und Platzhalter.

    Vergibt bewusst noch KEINE Platzhalter in der Datenbank — die
    Zuordnung entsteht erst beim tatsaechlichen Anonymisieren, sonst
    fuellt jede Probelesung die Tabelle mit Namen, die nie ersetzt
    wurden.
    """
    if not text:
        return {"sauber": True, "treffer": [], "anzahl": 0}

    _tabelle_anlegen(db)
    conn = db.connect()
    bekannt = {(r[0], r[1]): r[2] for r in conn.execute(
        "SELECT echter_name, art, platzhalter FROM anonymisierung_map")}

    treffer: list[dict] = []
    gesehen: set[str] = set()
    for eintrag in sammle_bestandsnamen(db):
        name, art = eintrag["name"], eintrag["art"]
        muster = _WORTGRENZE_VOR + re.escape(name) + _WORTGRENZE_NACH
        fund = re.search(muster, text, re.IGNORECASE)
        if not fund:
            continue
        if name in gesehen:
            continue
        gesehen.add(name)
        zeile = _zeile_von(text, fund.start())
        auszug = text[max(0, fund.start() - 45):fund.end() + 45]
        auszug = " ".join(auszug.split())
        grund = _treffer_ist_unsicher(name, text, fund.start(), fund.end())
        eintrag = {
            "name": text[fund.start():fund.end()],
            "art": art,
            "zeile": zeile,
            "fundstelle": auszug,
            "platzhalter_vorschlag": bekannt.get(
                (name, art), "(wird beim Anonymisieren vergeben)"),
            "unsicher": bool(grund),
        }
        if grund:
            eintrag["unsicher_grund"] = grund
        treffer.append(eintrag)

    treffer.sort(key=lambda t: (t["unsicher"], t["zeile"]))
    sicher = [t for t in treffer if not t["unsicher"]]
    return {
        "sauber": not sicher,
        "anzahl": len(treffer),
        "davon_unsicher": len(treffer) - len(sicher),
        "treffer": treffer,
    }


def anonymisiere_text(db, text: str) -> dict:
    """Ersetzt gefundene Bestandsnamen durch stabile Platzhalter."""
    ersetzt: list[dict] = []
    offen: list[dict] = []
    ergebnis = text
    for eintrag in sammle_bestandsnamen(db):
        name, art = eintrag["name"], eintrag["art"]
        muster = _WORTGRENZE_VOR + re.escape(name) + _WORTGRENZE_NACH
        fund = re.search(muster, ergebnis, re.IGNORECASE)
        if not fund:
            continue
        # v1.7.24 (#962): unsichere Treffer werden NICHT automatisch
        # ersetzt. Ein Adjektiv durch einen Firmenplatzhalter zu
        # tauschen entstellt den Satz, und der Nutzer merkt es nicht.
        grund = _treffer_ist_unsicher(name, ergebnis, fund.start(), fund.end())
        if grund:
            offen.append({"name": ergebnis[fund.start():fund.end()],
                          "art": art, "grund": grund})
            continue
        platz = platzhalter_fuer(db, name, art)
        ergebnis, n = re.subn(muster, platz, ergebnis, flags=re.IGNORECASE)
        ersetzt.append({"art": art, "platzhalter": platz, "vorkommen": n})
    antwort = {"text": ergebnis, "ersetzt": ersetzt, "anzahl": len(ersetzt)}
    if offen:
        antwort["zur_entscheidung"] = offen
        antwort["hinweis"] = (
            f"{len(offen)} Fundstelle(n) wurden NICHT ersetzt, weil sie "
            "vermutlich gewoehnliche Woerter sind. Bitte selbst ansehen — "
            "automatisch zu ersetzen wuerde den Satz entstellen.")
    return antwort
