"""Zentrales Ablehnungsgrund-Vokabular + Normalisierung (#913, v1.7.17).

Befund: 101 verschiedene Freitext-Gruende in 182 Datensaetzen — die
dokumentierte Whitelist wurde nie durchgesetzt, weil mehrere Schreibpfade
(Ollama-Autofilter mit 'auto:'-Praefix, Duplikat-Erkennung, direkte
dismiss_job-Aufrufe) an der Normalisierung vorbeischrieben. Folge: die
drei haeufigsten Nutzer-Signale erzeugten NULL Lerneffekt und jede
Aggregation ueber Ablehnungsgruende war systematisch falsch
('Dublikat'/'duplikat'/'Duplikat von ...' = fuenf Schreibweisen).

Regeln:
- ALLE Schreibpfade auf jobs.dismiss_reason laufen durch
  `normalisiere_dismiss_wert` (verdrahtet in db.dismiss_job).
- Freitext ist nicht wertlos — er wandert nach jobs.dismiss_note,
  nicht in das Feld, auf dem die Lernmechanik rechnet.
- `falsches_system` (Fachgebiet stimmt, Plattform nicht) und
  `falsche_branche` (Rolle stimmt, Branche nicht) sind seit v1.7.17
  regulaere Gruende — die zwei fachlich wertvollen Freitext-Faelle aus
  dem Bestand (41x / 38x), Kernregeln dieses Nutzerprofils.
"""
from __future__ import annotations

import json
import re

# Regulaere, vom Nutzer waehlbare Gruende. Erweiterung NUR hier —
# tools/jobs.py, CLAUDE.md und die dismiss_reasons-Seeds haengen daran.
# #1297: das ist der SEED, nicht die Liste der waehlbaren Gruende. Welche
# davon gelten, entscheidet der Mensch in `dismiss_reasons.is_active`;
# gefragt wird nur `waehlbare_gruende(db)`.
STANDARD_GRUENDE = [
    "zu_weit_entfernt",
    "gehalt_zu_niedrig",
    "falsches_fachgebiet",
    "falsches_system",
    "falsche_branche",
    "zu_junior",
    "zu_senior",
    "unpassendes_arbeitsmodell",
    "firma_uninteressant",
    "zeitarbeit",
    "befristet",
    "bereits_beworben",
    "duplikat",
    "kein_hochschulabschluss",
    "sonstiges",
]
_STANDARD_KLEIN = frozenset(STANDARD_GRUENDE)

# Systemseitig legitime Werte, die kein Nutzer waehlt, aber Tools
# schreiben (Statistik-relevant, bleiben unveraendert).
SYSTEM_GRUENDE = {
    "bewerbung_erstellt",
    "firma_blacklisted",
    "profil_match_negativ",
    "veraltet_url",
    # bewerbung_zu_anfrage_konvertieren: der Eintrag war nie eine
    # Bewerbung, sondern eine sofort abgelehnte Recruiter-Anfrage.
    "war_nur_anfrage",
    # blacklist_anwenden (`services/blacklist_bestand`): Treffer eines
    # STICHWORTS der Blacklist, das Gegenstueck zu firma_blacklisted. #1239:
    # fehlte hier -- der Normalisierer machte daraus 'sonstiges' (Notiz
    # "keyword_blacklisted"), und ein Lauf auf den Bestand legte viele Zeilen
    # 'sonstiges' von "ich" mit demselben Zeitpunkt an: sie verdraengten die
    # Beispiele des Menschen und standen als Grund im Block "GELERNT".
    "keyword_blacklisted",
}

# #1297: was der Mensch NICHT abschalten kann. Systemgruende schreiben die
# Werkzeuge (Buchhaltung, kein Urteil), und `sonstiges` ist der Rueckfall fuer
# Freitext - ohne ihn haette eine Notiz keinen Platz.
NICHT_ABSCHALTBAR = frozenset(SYSTEM_GRUENDE | {"sonstiges"})


def _zeilen(db) -> list:
    try:
        return list(db.get_dismiss_reasons() or [])
    except Exception:  # pragma: no cover - aeltere Datenbank ohne Tabelle
        return []


def ist_standardgrund(label) -> bool:
    return str(label or "").strip().lower() in _STANDARD_KLEIN


def abgeschaltete_gruende(db, zeilen=None) -> set:
    """Die Gruende, die der Mensch abgeschaltet hat (#1297), kleingeschrieben.

    Steht ein Grund doppelt in der Tabelle (Standardzeile und eine alte eigene
    Zeile gleichen Namens), gilt der restriktivere Zustand: eine abgeschaltete
    Zeile reicht. `NICHT_ABSCHALTBAR` ist nie dabei.
    """
    zeilen = _zeilen(db) if zeilen is None else zeilen
    return {str(r.get("label") or "").strip().lower() for r in zeilen
            if not r.get("is_active", 1)} - NICHT_ABSCHALTBAR - {""}


def waehlbare_gruende(db) -> list:
    """DIE Liste der Gruende, die eine neue Aussortierung tragen darf (#1297).

    Standardgruende (in ihrer Reihenfolge) plus eigene, jeweils nur aktive.
    `stelle_einordnen`, `stellen_bulk_bewerten`, das Dashboard und die Regeln
    der gespeicherten Filter fragen hier - nie `STANDARD_GRUENDE` direkt.
    """
    zeilen = _zeilen(db)
    aus = abgeschaltete_gruende(db, zeilen)
    liste = [g for g in STANDARD_GRUENDE if g not in aus]
    for r in zeilen:
        label = str(r.get("label") or "").strip()
        klein = label.lower()
        if (not label or not r.get("is_active", 1) or klein in aus
                or klein in _STANDARD_KLEIN or klein in SYSTEM_GRUENDE):
            continue
        liste.append(label)
    return list(dict.fromkeys(liste))


def bekannte_gruende(db) -> set:
    """Alle Gruende, die ein GESPEICHERTER Wert tragen darf, kleingeschrieben.

    Anders als `waehlbare_gruende` auch die abgeschalteten: eine bestehende
    Aussortierung bleibt, wie sie ist (#1297). Die Heilung beim Start
    (`ist_konform`) prueft dagegen.
    """
    return (set(_STANDARD_KLEIN) | SYSTEM_GRUENDE
            | {str(r.get("label") or "").strip().lower() for r in _zeilen(db)}) - {""}


def gruende_pruefen(db, gruende) -> dict:
    """Prueft Gruende fuer eine NEUE Aussortierung (#1297, #663).

    Ein Wert gilt, wenn er (gross/klein, Schlusszeichen und alte
    Schreibweisen wie `Dublikat` egal) ein waehlbarer Grund ist. Ein
    abgeschalteter oder unbekannter Wert wird NICHT umgedeutet - weder auf
    `sonstiges` noch auf einen anderen Grund und schon gar nicht neu
    angelegt; er steht in `abgeschaltet` bzw. `unbekannt`.

    Rueckgabe: {"gruende", "abgeschaltet", "unbekannt", "verfuegbar"}.
    """
    if isinstance(gruende, str):
        gruende = [gruende]
    verfuegbar = waehlbare_gruende(db)
    nach_klein = {g.lower(): g for g in verfuegbar}
    aus = abgeschaltete_gruende(db)
    ok, abgeschaltet, unbekannt = [], [], []
    for roh in gruende or []:
        text = str(roh or "").strip()
        if not text:
            continue
        klein = text.lower()
        kandidaten = [klein, klein.strip(" .;,:!-")]
        kandidaten += [_ALIAS[k] for k in list(kandidaten) if k in _ALIAS]
        treffer = next((nach_klein[k] for k in kandidaten if k in nach_klein), None)
        if treffer is not None:
            ok.append(treffer)
        elif any(k in aus for k in kandidaten):
            abgeschaltet.append(text)
        else:
            unbekannt.append(text)
    return {"gruende": list(dict.fromkeys(ok)), "abgeschaltet": abgeschaltet,
            "unbekannt": unbekannt, "verfuegbar": verfuegbar}


def ablehnung_antwort(pruefung: dict) -> dict:
    """Die Antwort an den Aufrufer, wenn `gruende_pruefen` etwas abweist."""
    teile = []
    if pruefung["abgeschaltet"]:
        teile.append("abgeschaltet: " + ", ".join(pruefung["abgeschaltet"]))
    if pruefung["unbekannt"]:
        teile.append("nicht in der Liste: " + ", ".join(pruefung["unbekannt"]))
    return {
        "fehler": ("Nichts aussortiert. Diese Gründe gelten nicht ("
                   + "; ".join(teile) + ")." if teile else
                   "Mindestens ein Ablehnungsgrund ist erforderlich."),
        "verfuegbare_gruende": pruefung["verfuegbar"],
        "naechster_schritt": (
            "Nimm einen Grund aus verfuegbare_gruende oder 'sonstiges'. "
            "Abgeschaltete Gründe hat der Mensch bewusst ausgeschaltet - "
            "nur er schaltet sie wieder ein (Einstellungen › Ablehnungsgründe)."),
    }


def standardgrund_geloescht(conn, label: str) -> bool:
    """Wurde dieser Standardgrund geloescht? (#1297, Abnahme 09.11.2026)

    Aufgerufen nur, wenn seine Zeile in `dismiss_reasons` fehlt. Bis 1.8.2
    legte der erste Gebrauch die Zeile an, und Loeschen entfernte sie. Fehlt
    sie, obwohl Stellen mit dem Grund aussortiert sind (auch als `auto:` oder
    `wiedergaenger:`), war das Loeschen. Im Zweifel gilt der restriktivere
    Zustand: der Grund kommt abgeschaltet zurueck.
    """
    ziel = str(label or "").strip().lower()
    if not ziel:
        return False
    try:
        zeilen = conn.execute(
            "SELECT dismiss_reason FROM jobs WHERE dismiss_reason LIKE ?",
            (f"%{ziel}%",)).fetchall()
    except Exception:
        return False
    for z in zeilen:
        for g in gruende_aus_wert(z[0]):
            k = str(g or "").strip().lower()
            for vorsilbe in ("auto:", "wiedergaenger:"):
                if k.startswith(vorsilbe):
                    k = k[len(vorsilbe):].split(":", 1)[0]
            if k == ziel:
                return True
    return False


# ------------------------------------------------ Standardgruende zurueck
# #1323 (Rest aus #1297): wer mehrere Standardgruende abgeschaltet oder
# geloescht hat, kam nur Grund fuer Grund zurueck. EINE Funktion fuer das
# Dashboard (POST /api/dismiss-reasons/standard-wiederherstellen) und das
# Werkzeug `ablehnungsgruende_wiederherstellen` (Lehre 1).
#
# Was "bereits vorhanden" heisst - die Entscheidung und ihr Grund:
#
# * Ein Standardgrund ist vorhanden, wenn eine Zeile seinen Namen traegt
#   (gross/klein und Raender egal). Das ist dieselbe Identitaet wie ueberall
#   sonst: Seed beim Start, `abgeschaltete_gruende`, `waehlbare_gruende`,
#   `set_dismiss_reason_active` vergleichen genau so.
# * Fehlt diese Zeile, gilt er AUCH als vorhanden, wenn eine Zeile mit
#   demselben Vergleichsschluessel existiert (`gruende_schreibweise.schluessel`:
#   klein, Leerzeichen/Unterstrich/Bindestrich gleich): `Zu Junior` ist
#   `zu_junior`, nur anders geschrieben. Das ist die eine Regel, die PBP fuer
#   "gleichbedeutend" schon hat (#1115, #663 C66). So entsteht neben einem
#   umbenannten Standardgrund kein zweiter. (Umbenennen kann ein Standardgrund
#   nur ueber `ablehnungsgrund_umbenennen` oder aus der Zeit vor 1.8.3; das
#   Dashboard bietet es seit #1297 nicht mehr an. Die Zeile behaelt dabei
#   `is_custom=0`.)
# * Ein Name mit anderem INHALT (`Zu wenig Erfahrung`) ist ein anderer Grund.
#   PBP raet nicht, welcher Standardgrund das einmal war; der Standardgrund
#   wird angelegt, wie es der Start ohnehin taete.
#
# Was eingeschaltet wird: jede abgeschaltete Zeile, die den Standardgrund
# traegt - unter seinem Namen oder als umbenannter Standardgrund
# (`is_custom=0`). Eine EIGENE Zeile (`is_custom=1`, kein Standardname)
# bleibt, wie sie ist, auch wenn sie gleich heisst: die Funktion legt dann
# nichts an und schaltet nichts um, sie nennt sie nur. Eigene Gruende werden
# nie angelegt, umbenannt, zusammengefuehrt oder geschaltet.
#
# Systemgruende (`SYSTEM_GRUENDE`) sind keine Standardgruende und bleiben
# aussen vor. `sonstiges` ist ein Standardgrund und kommt mit zurueck, falls
# seine Zeile fehlt.


def standardgruende_wiederherstellen(db, bestaetigt: bool = False) -> dict:
    """Holt alle Standardgruende zurueck: fehlende anlegen, abgeschaltete einschalten (#1323).

    Ohne `bestaetigt` nur die Vorschau (nichts wird geschrieben), mit
    `bestaetigt=True` die Ausfuehrung. Ein zweiter Aufruf findet nichts mehr.

    Rueckgabe:
        status: "vorschau" | "wiederhergestellt" | "nichts_zu_tun"
        anlegen: Standardgruende, deren Zeile fehlt (kommen eingeschaltet)
        einschalten: abgeschaltete Standardgruende, je {"grund", "label",
            "stellen"} (label = so heisst die Zeile; bei einem umbenannten
            Standardgrund weicht er ab)
        vorhanden_als: Standardgruende, die unter anderer Schreibweise
            vorhanden sind, je {"grund", "label", "eigen", "aktiv"}; sie
            werden nicht angelegt
        unveraendert: Zahl der Standardgruende, die schon an sind
    """
    from .gruende_schreibweise import schluessel

    zeilen = _zeilen(db)
    nach_label: dict = {}
    nach_schluessel: dict = {}
    for r in zeilen:
        label = str(r.get("label") or "").strip()
        if not label:
            continue
        nach_label.setdefault(label.lower(), []).append(r)
        nach_schluessel.setdefault(schluessel(label), []).append(r)

    anlegen, einschalten, vorhanden_als = [], [], []
    unveraendert = 0
    for grund in STANDARD_GRUENDE:
        eigene_zeilen = nach_label.get(grund)
        if eigene_zeilen:
            aus = [r for r in eigene_zeilen if not r.get("is_active", 1)]
            if aus:
                einschalten.append({"grund": grund, "label": grund, "_id": aus[0]["id"]})
            else:
                unveraendert += 1
            continue
        varianten = nach_schluessel.get(schluessel(grund)) or []
        if not varianten:
            anlegen.append(grund)
            continue
        standard_varianten = [r for r in varianten if not r.get("is_custom")]
        for r in varianten:
            vorhanden_als.append({"grund": grund, "label": r.get("label"),
                                  "eigen": bool(r.get("is_custom")),
                                  "aktiv": bool(r.get("is_active", 1))})
        aus = [r for r in standard_varianten if not r.get("is_active", 1)]
        if aus:
            einschalten.append({"grund": grund, "label": aus[0].get("label"),
                                "_id": aus[0]["id"]})
        else:
            unveraendert += 1

    for eintrag in einschalten:
        try:
            eintrag["stellen"] = int(db.dismiss_reason_bestand(eintrag["label"]).get("stellen", 0))
        except Exception:  # pragma: no cover - Zahl ist Beiwerk
            eintrag["stellen"] = 0

    def _sichtbar(liste):
        return [{k: v for k, v in e.items() if not k.startswith("_")} for e in liste]

    antwort = {
        "anlegen": list(anlegen),
        "einschalten": _sichtbar(einschalten),
        "vorhanden_als": vorhanden_als,
        "unveraendert": unveraendert,
        "eigene_gruende": "bleiben unverändert",
    }
    if not anlegen and not einschalten:
        return {"status": "nichts_zu_tun", **antwort,
                "hinweis": "Alle Standardgründe sind da und eingeschaltet. Nichts zu tun."}
    if not bestaetigt:
        teile = []
        if anlegen:
            teile.append(f"{len(anlegen)} kommen zurück ({', '.join(anlegen)})")
        if einschalten:
            teile.append(f"{len(einschalten)} werden wieder eingeschaltet ("
                         + ", ".join(e["label"] for e in einschalten) + ")")
        return {"status": "vorschau", **antwort,
                "hinweis": ("Noch nichts geändert. " + "; ".join(teile) + ". Eigene Gründe "
                            "bleiben, wie sie sind. Zum Ausführen erneut mit Bestätigung.")}

    conn = db.connect()
    from datetime import datetime, timezone
    jetzt = datetime.now(timezone.utc).isoformat()  # wie `database._now`
    for grund in anlegen:
        conn.execute(
            "INSERT INTO dismiss_reasons (label, is_custom, profile_id, created_at, is_active) "
            "VALUES (?, 0, '', ?, 1)", (grund, jetzt))
    conn.commit()
    for eintrag in einschalten:
        db.set_dismiss_reason_active(eintrag["_id"], True)
    return {"status": "wiederhergestellt", **antwort,
            "hinweis": (f"{len(anlegen)} Standardgrund/-gründe angelegt, {len(einschalten)} wieder "
                        "eingeschaltet. Sie stehen ab sofort wieder in jeder Auswahl, auch für "
                        "Claude und die Automatik. Eigene Gründe sind unverändert.")}


def belege_ohne_abgeschaltete(dismissed, aus: set):
    """Aussortierte Stellen ohne die abgeschalteten Gruende (#1297).

    Fuer die Wiedergaenger-Automatik: ein abgeschalteter Grund ist keine
    Grundlage mehr fuer eine Entscheidung ohne Rueckfrage. Eine Zeile mit
    weiteren Gruenden bleibt mit diesen; eine Zeile, die nur abgeschaltete
    traegt, faellt als Beleg weg. Die Zeilen werden kopiert, der Bestand
    bleibt unveraendert. Gibt den Eingang unveraendert zurueck, wenn nichts
    abgeschaltet ist.
    """
    if not aus or dismissed is None:
        return dismissed

    def _kern(g) -> str:
        k = str(g or "").strip().lower()
        if k.startswith("auto:"):
            k = k[len("auto:"):].split(":", 1)[0]
        return k

    ergebnis = []
    for j in dismissed:
        roh = j.get("dismiss_reasons") or gruende_aus_wert(j.get("dismiss_reason"))
        rest = [g for g in roh if _kern(g) not in aus]
        if len(rest) == len(roh):
            ergebnis.append(j)
            continue
        if not rest:
            continue
        kopie = dict(j)
        kopie["dismiss_reasons"] = rest
        kopie["dismiss_reason"] = (rest[0] if len(rest) == 1
                                   else json.dumps(rest, ensure_ascii=False))
        ergebnis.append(kopie)
    return ergebnis if type(dismissed) is list else type(dismissed)(ergebnis)

# Gruende, die KEIN Urteil des Menschen ueber die Passung einer Stelle sind
# (#1234). Die Stelle ging aus der Liste, weil sich der Mensch beworben hat
# (`bewerbung_erstellt` ist das GEGENTEIL einer Ablehnung), weil es sie doppelt
# gab oder weil die Anzeige weg war. Als Beleg dafuer, dass "diese Art Stelle bei
# diesem Arbeitgeber nicht passt", taugen sie nicht: zwei Fassungen derselben
# frueheren Bewerbung machten eine neue, gelesene und empfohlene Stelle zum
# Wiedergaenger mit k.o.
#
# EINE Liste fuer alle Wege, die aus Aussortierungen etwas folgern (Wiedergaenger,
# Firmen-Historie, Stellenliste, Analyse). `kalibrierung`, `lerninsights`,
# `lernprotokoll` und `lernquellen` schliessen `bewerbung_erstellt` in SQL aus; die
# Automatik (`stellen_automatik.AUTOMATIK_GRUENDE`) fragt umgekehrt nach einer
# Positivliste.
KEIN_URTEIL_GRUENDE = frozenset({
    "bewerbung_erstellt", "bereits_beworben", "duplikat", "veraltet_url",
})


def ist_urteil(grund) -> bool:
    """True, wenn der Aussortier-Grund ein Urteil ueber die Passung ist (#1234)."""
    kern = str(grund or "").strip().lower()
    if kern.startswith("auto:"):
        kern = kern[len("auto:"):].split(":", 1)[0]
    return bool(kern) and kern not in KEIN_URTEIL_GRUENDE


# Exakte Alt-Schreibweisen -> kanonischer Grund (Bestands-Mapping aus
# der #913-Auswertung; case-insensitiv verglichen).
_ALIAS = {
    "dublikat": "duplikat",
    "duplikat_manuell": "duplikat",
    "duplikat_bewerbung": "duplikat",
    "ueberqualifiziert": "zu_senior",
    "überqualifiziert": "zu_senior",
    "falsches system": "falsches_system",
    "falsche branche": "falsche_branche",
    "veraltet": "veraltet_url",
    "abgelaufen": "veraltet_url",
    # Kurz-Vokabular von bewerbung_zu_anfrage_konvertieren
    "standort": "zu_weit_entfernt",
    "branche": "falsche_branche",
}


_MUSTER = [
    ("bereits_beworben", re.compile(r"\b(?:bereits|schon) beworben")),
    ("zu_weit_entfernt", re.compile(r"\bzu weit\b|\bentfernung")),
    ("gehalt_zu_niedrig", re.compile(r"\bgehalt|\bzu niedrig\b")),
    ("zeitarbeit", re.compile(r"\bzeitarbeit|\barbeitnehmer(?:ü|ue)berl")),
    ("befristet", re.compile(r"\bbefristet")),
    ("kein_hochschulabschluss", re.compile(
        r"\bhochschul|\bstudium\b|\bstudienabschluss|\b(?:kein|ohne)(?:en)? abschluss\b")),
]


def _kanonisch_einzeln(raw: str, erlaubt: set) -> tuple[str, str | None]:
    """(kanonischer Grund, Freitext-Rest oder None) fuer EINEN Wert."""
    text = str(raw or "").strip()
    if not text:
        return "sonstiges", None
    lower = text.lower().strip()

    if lower in erlaubt:
        return lower, None
    if lower in _ALIAS and _ALIAS[lower] in erlaubt:
        return _ALIAS[lower], None

    # v1.7.23 (#944): Ein Vokabular-Wert mit angehaengter Zeichensetzung
    # ("zu_weit_entfernt.") fiel bisher aus der Whitelist und wurde zu
    # 'sonstiges' plus Freitext — im Bericht erschien derselbe Grund
    # dadurch ZWEIMAL als eigene Kategorie, und der Lerneffekt ging
    # verloren. Ein Schlusspunkt ist keine andere Kategorie.
    entkleidet = lower.strip(" .;,:!-")
    if entkleidet and entkleidet != lower:
        if entkleidet in erlaubt:
            return entkleidet, None
        if entkleidet in _ALIAS and _ALIAS[entkleidet] in erlaubt:
            return _ALIAS[entkleidet], None

    # Systempfad 'auto:<grund>' bzw. 'auto:<grund>:<llm-begruendung>' —
    # Grund extrahieren, Begruendung (falls vorhanden) ist Freitext.
    # Der Kurzform-Fall ohne Begruendung existiert im Altbestand (#671).
    m = re.match(r"^auto:([a-z_]+)(?::(.*))?$", text,
                 re.IGNORECASE | re.DOTALL)
    if m:
        grund = m.group(1).lower()
        rest = (m.group(2) or "").strip()
        if grund in erlaubt:
            return grund, (rest or None)
        return "sonstiges", text

    # 'Duplikat von <hash>: ...' u. ae.
    if (lower.startswith("duplikat") or lower.startswith("dublikat")) \
            and "duplikat" in erlaubt:
        return "duplikat", text

    # Muster-Heuristiken (uebernommen aus dem alten
    # _normalize_dismiss_reason in tools/jobs.py — jetzt an EINER Stelle).
    # #1297: ein Muster erzeugt nur einen Grund, der gilt; ein abgeschalteter
    # Grund entsteht nicht aus Freitext. Wortanfaenge statt Teilstrings: "ats"
    # traf "Zertifikats", "abschluss" traf "Projektabschluss".
    for grund, muster in _MUSTER:
        if grund in erlaubt and muster.search(lower):
            return grund, None

    # Alles andere ist Freitext: zaehlbar als 'sonstiges', lesbar als Note.
    return "sonstiges", text


def normalisiere_dismiss_wert(raw, custom: set | frozenset = frozenset(),
                              abgeschaltet: set | frozenset = frozenset()
                              ) -> tuple[str, list]:
    """Normalisiert einen dismiss_reason-Speicherwert (#913).

    `raw` kann ein Plain-String, eine JSON-Liste als String oder eine
    echte Liste sein. Rueckgabe: (speicherwert, freitexte) — der
    Speicherwert behaelt das Eingabeformat (Liste -> JSON-Liste,
    String -> String), enthaelt aber nur noch Whitelist-Werte;
    `freitexte` gehoeren nach jobs.dismiss_note.

    `abgeschaltet` (#1297): Gruende, die der Mensch abgeschaltet hat. Sie
    entstehen weder aus Freitext noch als Wert; ein solcher Wert wird
    `sonstiges`, das Original bleibt als Freitext lesbar.
    """
    erlaubt = (set(STANDARD_GRUENDE) | SYSTEM_GRUENDE | {
        str(c).lower() for c in (custom or ())}) - (
        {str(a).lower() for a in (abgeschaltet or ())} - NICHT_ABSCHALTBAR)

    war_liste = isinstance(raw, (list, tuple))
    werte = list(raw) if war_liste else None
    if werte is None:
        text = str(raw or "").strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                geparst = json.loads(text)
                if isinstance(geparst, list):
                    werte = geparst
                    war_liste = True
            except (ValueError, TypeError):
                pass
        if werte is None:
            werte = [text]

    gruende: list = []
    freitexte: list = []
    for w in werte:
        grund, freitext = _kanonisch_einzeln(w, erlaubt)
        if grund not in gruende:
            gruende.append(grund)
        if freitext:
            freitexte.append(freitext)
    if not gruende:
        gruende = ["sonstiges"]

    if war_liste:
        return json.dumps(gruende, ensure_ascii=False), freitexte
    return gruende[0], freitexte


def ist_konform(raw, custom: set | frozenset = frozenset()) -> bool:
    """True, wenn der Speicherwert bereits nur Whitelist-Gruende traegt."""
    erlaubt = set(STANDARD_GRUENDE) | SYSTEM_GRUENDE | {
        str(c).lower() for c in (custom or ())}
    try:
        werte = json.loads(raw) if str(raw).strip().startswith("[") else [raw]
        if not isinstance(werte, list):
            werte = [werte]
    except (ValueError, TypeError):
        werte = [raw]
    return all(str(w).strip() in erlaubt for w in werte)


# --------------------------------------------------------------- Lesen
# v1.7.121: Der Speicherwert hat ZWEI Formen — ein einzelner Grund als
# String, mehrere als JSON-Liste (beides gewollt, siehe
# `normalisiere_dismiss_wert`). Drei Leser zaehlten mit
# `GROUP BY dismiss_reason` und fuehrten damit `["falsches_fachgebiet"]`
# und `falsches_fachgebiet` als zwei verschiedene Gruende: gemeldet als
# 32,1 % und 31,3 %, obwohl es EIN Grund mit 63,4 % ist. Gezaehlt wird
# deshalb nur noch hier.

def gruende_aus_wert(raw) -> list:
    """Zerlegt einen gespeicherten dismiss_reason in seine Gruende."""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        werte = list(raw)
    else:
        text = str(raw).strip()
        werte = [text]
        if text.startswith("[") and text.endswith("]"):
            try:
                geparst = json.loads(text)
                if isinstance(geparst, list):
                    werte = geparst
            except (ValueError, TypeError):
                pass
    gruende: list = []
    for w in werte:
        g = str(w or "").strip()
        if not g:
            continue
        # Altbestand vor #913: "Duplikat: <hash>" ist der Grund duplikat.
        if g.lower().startswith("duplikat:"):
            g = "duplikat"
        if g not in gruende:
            gruende.append(g)
    return gruende


# Zaehlt eine Aussortierung OHNE gespeicherte Herkunft (`dismissed_by` leer: Altbestand vor v1.7.64) als Urteil des Menschen?
# Nein (#1239). `aussortier_protokoll.herkunft` sagt es selbst: "unbekannt ist nicht dasselbe wie war ich". Der Altbestand enthaelt
# auch Urteile der Automatik, deren Praefix `auto:` seit #913 beim Schreiben entfernt wird. Gemessen am 17.10.2026 auf einer Kopie
# einer echten Datenbank: 2.488 von 3.586 aussortierten Stellen ohne Herkunft, keine einzige mit dem Praefix; sie der KI als "hat
# der Bewerber selbst abgelehnt" zu zeigen, waere eine Behauptung ohne Beleg. Die heutigen Schreibwege setzen die Herkunft
# (`dismiss_job` kennt "ich" und "automatik", `save_jobs` schreibt "automatik"); nur rohes SQL und die Migration v20->v21 lassen
# sie leer. Wer den Altbestand trotzdem mitzaehlen will, aendert nur diese Zeile.
UNBEKANNTE_HERKUNFT_ZAEHLT = False


def urteilsgruende_des_menschen(dismissed_by, dismiss_reason) -> list:
    """Die Gruende einer Aussortierung, die ein URTEIL DES MENSCHEN ueber die Passung sind (#1239); leer, wenn keiner zaehlt.

    EINE Antwort fuer alles, was der KI als Entscheidung des Bewerbers gezeigt wird: die Beispiele im Prompt der Auto-Aussortierung
    (`Database.get_recent_user_dismissals`) und der Block "GELERNT" (`gruende_zaehlen(nur_menschen=True)`). Drei Bedingungen,
    alle drei:

    * der Mensch hat aussortiert (`aussortier_protokoll.herkunft` == "ich"). Die Automatik schreibt ihre Gruende seit #913 OHNE
      Praefix `auto:`; `NOT LIKE 'auto:%'` fing sie nicht mehr, und das Modell lernte von sich selbst;
    * der Grund ist kein Systemgrund (`SYSTEM_GRUENDE`: `profil_match_negativ`, `firma_blacklisted`, ...);
    * der Grund ist ein Urteil ueber die Passung (`ist_urteil`, #1234): `bewerbung_erstellt` ist das Gegenteil einer Ablehnung,
      `duplikat`, `bereits_beworben` und `veraltet_url` sagen nichts darueber, ob eine Art Stelle passt.

    Bei mehreren Gruenden zaehlen nur die, die diese Bedingungen erfuellen. `dismissed_by` leer: siehe `UNBEKANNTE_HERKUNFT_ZAEHLT`.
    """
    from .aussortier_protokoll import herkunft
    wer = herkunft({"dismissed_by": dismissed_by, "dismiss_reason": dismiss_reason})
    if wer != "ich" and not (wer == "unbekannt" and UNBEKANNTE_HERKUNFT_ZAEHLT):
        return []
    return [g for g in gruende_aus_wert(dismiss_reason)
            if g not in SYSTEM_GRUENDE and ist_urteil(g)]


def gruende_zaehlen(conn, profile_id, ausser=("bewerbung_erstellt",),
                    nur_menschen=False) -> tuple[list, int]:
    """Zaehlt die Aussortier-Gruende ueber beide Speicherformen.

    Rueckgabe: ([(grund, anzahl_stellen), ...] absteigend, stellen_gesamt).
    Eine Stelle mit zwei Gruenden zaehlt bei beiden, im Gesamtwert aber
    einmal — der Anteil beantwortet also "bei wie vielen Stellen spielte
    dieser Grund eine Rolle". Stellen, deren Gruende ALLE in `ausser`
    liegen, zaehlen gar nicht.

    `nur_menschen` (#1239): gezaehlt werden nur die Gruende, die ein Urteil
    des MENSCHEN sind (`urteilsgruende_des_menschen`: nicht die Automatik,
    kein Systemgrund, Herkunft belegt). Das ist die Frage der KI-Aussortierung
    "wie sortiert dieser Bewerber aus?"; die Statistik und die Lern-Karte
    fragen weiter nach ALLEN Aussortierungen.
    """
    rows = conn.execute(
        "SELECT dismissed_by, dismiss_reason, COUNT(*) AS n FROM jobs "
        "WHERE is_active=0 AND (profile_id=? OR profile_id IS NULL) "
        "AND COALESCE(dismiss_reason,'') != '' "
        "GROUP BY dismissed_by, dismiss_reason", (profile_id,)
    ).fetchall()
    zaehler: dict = {}
    gesamt = 0
    for r in rows:
        if nur_menschen:
            gruende = urteilsgruende_des_menschen(r["dismissed_by"], r["dismiss_reason"])
        else:
            gruende = gruende_aus_wert(r["dismiss_reason"])
        gruende = [g for g in gruende if g not in ausser]
        if not gruende:
            continue
        gesamt += r["n"]
        for g in gruende:
            zaehler[g] = zaehler.get(g, 0) + r["n"]
    liste = sorted(zaehler.items(), key=lambda kv: (-kv[1], kv[0]))
    return liste, gesamt
