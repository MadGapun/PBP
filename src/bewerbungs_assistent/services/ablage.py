"""Wohin PBP schreibt und woher es die Vorlage nimmt (#973).

Nutzerwunsch vom 04.09. und noch einmal am 09.09.2026:

    "Ich moechte das Verzeichnis, in dem Dokumente wie z.B. der
    Lebenslauf, den Du erstellst, abgelegt werden, anpassen koennen —
    bzw. wo die Vorlagen liegen."

**Der Ausgabe-Ordner.** PBP legte jede erzeugte Datei nach
`<Datenordner>/export`. Wer seine Bewerbungsunterlagen woanders fuehrt,
kopiert danach jede Datei von Hand und traegt die Pfade nach — derselbe
Handgriff bei jeder Bewerbung. Der Zielordner stand an DREIZEHN Stellen
einzeln im Code; ein Nadeloehr gab es nicht. Genau daraus entstehen die
Faelle #963/#991/#992, deshalb steht hier `ausgabe_ordner()` und nicht
dreizehn Mal derselbe Ausdruck.

**Der Vorlagen-Ordner.** Den gab es bisher gar nicht: die vier
DOCX-Erzeuger starten mit einem LEEREN `Document()`, das Layout steht
als Code in `export.py`, und die Dokumenttypen `lebenslauf_vorlage` /
`anschreiben_vorlage` sind blosse Etiketten ohne Leser. Einen Pfad
einzufuehren, den niemand liest, waere der Regler ohne Draht aus #1000
und #988. Deshalb wird die Vorlage tatsaechlich als Grundlage geoeffnet
— Schriften, Raender, Kopf- und Fusszeilen bleiben erhalten.

**Drei Regeln, die dieses Modul traegt:**

(1) **Ein leerer Pfad heisst "wie bisher".** Wer nichts einstellt, merkt
    von dieser Aenderung nichts.

(2) **Ein ungueltiger Pfad wird ABGEWIESEN, nicht gespeichert.** Wer
    einen Tippfehler eintraegt, bekommt eine Begruendung — nicht eine
    Einstellung, an die er glaubt und die nichts tut (#988). Dieselbe
    Entscheidung wie bei den Reisewiderstands-Regeln aus #965.

(3) **Ein verschwundener Ordner ist ein BENANNTER Sonderfall.** Externe
    Platten und Netzlaufwerke sind mal weg. Dann schreibt PBP in den
    Datenordner — und sagt das im selben Atemzug. Weder ein Absturz noch
    eine stille Umleitung: der Mensch sucht seine Datei sonst an einer
    Stelle, an der sie nicht liegt.
"""
from __future__ import annotations

import os
from pathlib import Path

# Schluessel in `profile_settings`. Gemeinsamer Praefix, damit beide
# Ordner beim Nachsehen nebeneinander stehen.
AUSGABE_SCHLUESSEL = "ablage_ausgabe_ordner"
VORLAGEN_SCHLUESSEL = "ablage_vorlagen_ordner"

ARTEN = ("ausgabe", "vorlagen")

# Welche Vorlage zu welcher Art Dokument gehoert. Die Namen sind
# absichtlich schlicht: wer den Ordner oeffnet, soll ohne Doku sehen,
# welche Datei wofuer gilt.
VORLAGEN_DATEIEN = {
    "lebenslauf": ("lebenslauf.docx", "vorlage_lebenslauf.docx",
                   "lebenslauf_vorlage.docx"),
    "anschreiben": ("anschreiben.docx", "vorlage_anschreiben.docx",
                    "anschreiben_vorlage.docx"),
    "fachprofil": ("fachprofil.docx", "vorlage_fachprofil.docx",
                   "fachprofil_vorlage.docx"),
}


def _schluessel(art: str) -> str:
    if art == "ausgabe":
        return AUSGABE_SCHLUESSEL
    if art == "vorlagen":
        return VORLAGEN_SCHLUESSEL
    raise ValueError("art muss 'ausgabe' oder 'vorlagen' sein")


def _standard_ausgabe() -> Path:
    from ..database import get_data_dir
    return get_data_dir() / "export"


# -- Pruefung ---------------------------------------------------------

def pfad_pruefen(roh: str, art: str = "ausgabe") -> dict:
    """Taugt dieser Pfad? Antwort mit Begruendung, ohne etwas zu setzen.

    Wird VOR dem Speichern gerufen. Ein Pfad, der beim Setzen schon
    falsch ist, wird nie gut — ihn trotzdem abzulegen erzeugt eine
    Einstellung, an die der Mensch glaubt.
    """
    text = (roh or "").strip().strip('"')
    if not text:
        return {"gueltig": True, "leer": True, "pfad": "",
                "hinweis": "Leer heisst: PBP bleibt beim eigenen "
                           "Datenordner — also alles wie bisher."}

    pfad = Path(os.path.expandvars(os.path.expanduser(text)))
    if not pfad.is_absolute():
        return {"gueltig": False, "pfad": str(pfad), "grund": "nicht_absolut",
                "hinweis": "Bitte den vollstaendigen Pfad angeben. Ein "
                           "relativer Pfad zeigt je nach Startart woanders "
                           "hin — und PBP startet mal ueber das Dashboard, "
                           "mal ueber Claude Desktop."}
    if not pfad.exists():
        return {"gueltig": False, "pfad": str(pfad), "grund": "fehlt",
                "hinweis": "Diesen Ordner gibt es nicht. PBP legt ihn "
                           "bewusst nicht selbst an — ein Tippfehler wuerde "
                           "sonst als neuer Ordner enden, und deine Dateien "
                           "laegen ab dann dort."}
    if not pfad.is_dir():
        return {"gueltig": False, "pfad": str(pfad), "grund": "keine_ordner",
                "hinweis": "Das ist eine Datei, kein Ordner."}
    if not os.access(pfad, os.R_OK):
        return {"gueltig": False, "pfad": str(pfad), "grund": "nicht_lesbar",
                "hinweis": "PBP darf diesen Ordner nicht lesen."}
    if art == "ausgabe" and not os.access(pfad, os.W_OK):
        return {"gueltig": False, "pfad": str(pfad), "grund": "nicht_schreibbar",
                "hinweis": "PBP darf in diesen Ordner nicht schreiben. "
                           "Erzeugte Dateien kaemen dort nie an."}
    return {"gueltig": True, "leer": False, "pfad": str(pfad)}


# -- Lesen und Setzen -------------------------------------------------

def ordner_lesen(db, art: str) -> Path | None:
    """Der eingestellte Pfad, oder None fuer "nicht gesetzt"."""
    try:
        wert = db.get_profile_setting(_schluessel(art), "")
    except Exception:
        return None
    text = str(wert or "").strip()
    return Path(text) if text else None


def ordner_setzen(db, art: str, pfad: str) -> dict:
    """Setzt einen der beiden Ordner — oder weist ihn begruendet ab."""
    befund = pfad_pruefen(pfad, art)
    if not befund["gueltig"]:
        befund["gespeichert"] = False
        return befund

    db.set_profile_setting(_schluessel(art), befund["pfad"])
    antwort = uebersicht(db)
    antwort["gespeichert"] = True
    antwort["geaendert"] = art
    return antwort


def uebersicht(db) -> dict:
    """Was gilt gerade — und was daraus folgt."""
    ausgabe = ausgabe_befund(db)
    daten = {
        "ausgabe_ordner": ausgabe["ordner"],
        "ausgabe_eingestellt": ausgabe["eingestellt"],
        "ausgabe_befund": ausgabe["befund"],
        "hinweis_ausgabe": ausgabe["hinweis"],
    }
    vorlagen = ordner_lesen(db, "vorlagen")
    if vorlagen is None:
        daten["vorlagen_ordner"] = ""
        daten["vorlagen_befund"] = "nicht_gesetzt"
        daten["hinweis_vorlagen"] = (
            "Kein Vorlagen-Ordner gesetzt. PBP baut die DOCX-Dateien dann "
            "mit dem eingebauten Layout. Legst du einen Ordner fest und "
            "dort eine Datei 'lebenslauf.docx' ab, uebernimmt PBP deren "
            "Schriften, Raender sowie Kopf- und Fusszeilen.")
    else:
        daten["vorlagen_ordner"] = str(vorlagen)
        vorhanden = vorlagen.is_dir()
        daten["vorlagen_befund"] = "bereit" if vorhanden else "nicht_erreichbar"
        gefunden = {}
        for art in VORLAGEN_DATEIEN:
            treffer, _ = vorlage_finden(db, art)
            gefunden[art] = treffer.name if treffer else None
        daten["vorlagen"] = gefunden
        daten["hinweis_vorlagen"] = (
            "Gefundene Vorlagen: "
            + (", ".join(f"{k} -> {v}" for k, v in gefunden.items() if v)
               or "keine")
            + ". Fehlt eine, baut PBP diese Datei mit dem eingebauten Layout."
        ) if vorhanden else (
            "Der Vorlagen-Ordner ist gerade nicht erreichbar (externe "
            "Platte oder Netzlaufwerk?). PBP nimmt so lange das eingebaute "
            "Layout — die Einstellung bleibt bestehen.")
    return daten


# -- Der Choke-Point: wohin geschrieben wird --------------------------

def ausgabe_befund(db) -> dict:
    """Wohin geht die naechste Datei, und warum dorthin.

    Drei Ausgaenge, absichtlich getrennt (#989): `standard` (nichts
    eingestellt), `eigener_ordner` (eingestellt und da) und
    `ausweich` (eingestellt, aber verschwunden).
    """
    standard = _standard_ausgabe()
    eingestellt = ordner_lesen(db, "ausgabe")
    if eingestellt is None:
        return {"ordner": str(standard), "eingestellt": "", "befund": "standard",
                "hinweis": "PBP schreibt in den eigenen Datenordner."}
    try:
        nutzbar = eingestellt.is_dir() and os.access(eingestellt, os.W_OK)
    except OSError:
        nutzbar = False
    if nutzbar:
        return {"ordner": str(eingestellt), "eingestellt": str(eingestellt),
                "befund": "eigener_ordner",
                "hinweis": "PBP schreibt in deinen Ordner."}
    return {
        "ordner": str(standard), "eingestellt": str(eingestellt),
        "befund": "ausweich",
        "hinweis": (
            f"Dein Ordner '{eingestellt}' ist gerade nicht beschreibbar "
            "(externe Platte oder Netzlaufwerk?). Die Datei liegt deshalb "
            "im Datenordner von PBP. Die Einstellung bleibt bestehen — "
            "sobald der Ordner wieder da ist, schreibt PBP wieder dorthin."),
    }


def ausgabe_ordner(db) -> Path:
    """Das Nadeloehr. JEDE erzeugte Datei geht hier durch.

    Legt den Ordner an, wenn es der eigene Datenordner ist — beim Ordner
    des Nutzers wird NICHT angelegt (das macht `pfad_pruefen` zur
    Bedingung des Setzens; ein Tippfehler soll keinen Ordner erzeugen).
    """
    befund = ausgabe_befund(db)
    ziel = Path(befund["ordner"])
    if befund["befund"] != "eigener_ordner":
        ziel.mkdir(parents=True, exist_ok=True)
    return ziel


def ziel_hinweis(db, pfad) -> str:
    """Ein Satz fuer die Antwort der Export-Werkzeuge.

    Der alte Text lautete pauschal "Die Datei liegt im Bewerbungs-
    Assistent Datenordner" — sobald ein eigener Ordner gilt, stimmt das
    nicht mehr. Ein Satz, der die Datei woanders vermutet, kostet den
    Menschen dieselbe Suche wie ein fehlender Pfad.
    """
    befund = ausgabe_befund(db)
    if befund["befund"] == "eigener_ordner":
        return f"Die Datei liegt in deinem Ordner: {pfad}"
    if befund["befund"] == "ausweich":
        return befund["hinweis"] + f" Vollstaendiger Pfad: {pfad}"
    return (f"Die Datei liegt im Datenordner von PBP: {pfad}. Du kannst "
            "sie auch im Dashboard unter http://localhost:8200 "
            "herunterladen.")


# -- Vorlagen ---------------------------------------------------------

def vorlage_finden(db, art: str):
    """Die Vorlagendatei fuer diese Art Dokument, oder None.

    Rueckgabe: (Pfad oder None, Grund). Der Grund wird gebraucht, weil
    "kein Ordner gesetzt", "Ordner weg" und "Ordner da, aber keine
    passende Datei" drei verschiedene Dinge sind und verschiedene
    naechste Schritte verlangen.
    """
    namen = VORLAGEN_DATEIEN.get(art)
    if not namen:
        return None, "unbekannte_art"
    ordner = ordner_lesen(db, "vorlagen")
    if ordner is None:
        return None, "kein_ordner"
    try:
        if not ordner.is_dir():
            return None, "ordner_weg"
        # Ohne Ruecksicht auf Gross-/Kleinschreibung: unter Windows egal,
        # unter Linux nicht — und die Vorlage soll sich auf beiden Seiten
        # gleich verhalten.
        vorhanden = {p.name.lower(): p for p in ordner.iterdir() if p.is_file()}
    except OSError:
        return None, "ordner_weg"
    for name in namen:
        treffer = vorhanden.get(name.lower())
        if treffer is not None:
            return treffer, "gefunden"
    return None, "keine_datei"
