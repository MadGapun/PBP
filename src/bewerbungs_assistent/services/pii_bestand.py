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
    "comet", "atlas", "orion", "delta", "alpha", "beta", "gamma", "nova",
    "phoenix", "apex", "prime", "core", "next", "future", "vision",
    "global", "digital", "smart", "data", "cloud", "group", "partner",
    "consulting", "engineering", "solutions", "systems", "services",
    "technologies", "software", "energy", "medical", "capital",
}

_WORTGRENZE_VOR = r"(?<![\w\-])"
_WORTGRENZE_NACH = r"(?![\w\-])"


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
    for schluessel, art in roh.items():
        if schluessel in ausnahmen:
            continue
        ergebnis.append({"name": schluessel, "art": art})
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
        treffer.append({
            "name": text[fund.start():fund.end()],
            "art": art,
            "zeile": zeile,
            "fundstelle": auszug,
            "platzhalter_vorschlag": bekannt.get(
                (name, art), "(wird beim Anonymisieren vergeben)"),
            "unsicher": name in GEWOEHNLICHE_WOERTER,
        })

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
    ergebnis = text
    for eintrag in sammle_bestandsnamen(db):
        name, art = eintrag["name"], eintrag["art"]
        muster = _WORTGRENZE_VOR + re.escape(name) + _WORTGRENZE_NACH
        if not re.search(muster, ergebnis, re.IGNORECASE):
            continue
        if name in GEWOEHNLICHE_WOERTER:
            continue  # zu unsicher fuer automatisches Ersetzen
        platz = platzhalter_fuer(db, name, art)
        ergebnis, n = re.subn(muster, platz, ergebnis, flags=re.IGNORECASE)
        ersetzt.append({"art": art, "platzhalter": platz, "vorkommen": n})
    return {"text": ergebnis, "ersetzt": ersetzt, "anzahl": len(ersetzt)}
