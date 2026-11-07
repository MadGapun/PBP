"""Geocoding-Service fuer Entfernungsberechnung (#167).

Nutzt Nominatim (OpenStreetMap) via geopy — kostenlos, kein API-Key.
Rate-Limit: max 1 Request/Sekunde (Nominatim Fair-Use-Policy).
"""

import json
import logging
import re
import time
import threading
from typing import Optional

logger = logging.getLogger("bewerbungs_assistent.geocoding")

# In-memory cache: city_name -> (lat, lon) to avoid redundant geocoding
_geo_cache: dict[str, Optional[tuple[float, float]]] = {}
# #1235: Orte, die der Dienst MEHRFACH kennt: Schluessel -> Kandidaten. Im `_geo_cache` steht dazu `None`
# (keine Koordinaten), hier steht, WARUM.
_mehrdeutig_orte: dict[str, list] = {}
_cache_lock = threading.Lock()
_last_request_time = 0.0
_rate_lock = threading.Lock()

# #1090 AK 6: dauerhafter Speicher (Tabelle geo_cache). Angebunden von
# Database.initialize; ohne ihn bleibt es beim Arbeitsspeicher.
_speicher = None

#: #1235: Ab diesem Abstand (km) sind zwei Treffer des Dienstes verschiedene Orte desselben Namens.
MEHRDEUTIG_AB_KM = 50.0

#: #1235: Wie weit das Gewicht (`importance` des Dienstes) des ersten Treffers ueber dem des naechsten WEIT
#: entfernten Ortes liegen muss, damit der erste als DER Ort gilt. Gemessen am 16.10.2026 an 15 Abfragen:
#: mehrdeutig waren Neuenkirchen (Abstand 0,000), Rosengarten (0,006), Lichtenau (0,009), Hohenfelde (0,020) und
#: Neustadt (0,061); eindeutig Offenbach (0,136), Frankfurt (0,140), Halle (0,164), Freiburg (0,251) und
#: "Rosengarten, Baden-Württemberg" (0,287). Dazwischen liegt eine Lücke von 0,075; die Grenze steht in der Mitte.
MEHRDEUTIG_GEWICHT = 0.10

#: #1235: So viele Treffer fragt PBP je Ort ab (eine Anfrage, nur mehr Antwort).
MAX_TREFFER = 8

#: #1235: Stand der Zeilen in `geo_cache`. Zeilen ohne Stand stammen aus der Zeit, als nur der erste Treffer
#: genommen wurde; sie kennen die Mehrdeutigkeit nicht und werden beim naechsten Bedarf neu gefragt.
SPEICHER_STAND = 2


def speicher_setzen(db) -> None:
    global _speicher
    _speicher = db


def _aus_speicher(loc_key: str):
    """(True, Wert) wenn der Ort dauerhaft bekannt ist, sonst (False, None).
    Wert ist (lat, lon) oder None fuer 'nicht gefunden'."""
    if _speicher is None:
        return False, None
    try:
        row = _speicher.connect().execute(
            "SELECT lat, lon, status, stand, kandidaten FROM geo_cache WHERE ort_key=?",
            (loc_key,)).fetchone()
    except Exception:
        return False, None
    if not row:
        return False, None
    if row[2] == "mehrdeutig":
        try:
            kandidaten = json.loads(row[4] or "[]")
        except ValueError:
            kandidaten = []
        if not kandidaten:
            return False, None          # ohne Kandidaten ist es kein Befund, den man erklaeren koennte
        with _cache_lock:
            _mehrdeutig_orte[loc_key] = kandidaten
        return True, None
    if row[2] == "gefunden" and row[0] is not None:
        if (row[3] or 0) < SPEICHER_STAND:
            # #1235: vor der Mehrdeutigkeits-Pruefung gemerkt - es war der erste Treffer, mehr nicht.
            return False, None
        return True, (float(row[0]), float(row[1]))
    return True, None


def _in_speicher(loc_key: str, coords, kandidaten=None) -> None:
    if _speicher is None:
        return
    try:
        from datetime import datetime, timezone
        con = _speicher.connect()
        con.execute(
            "INSERT OR REPLACE INTO geo_cache (ort_key, lat, lon, status, abgerufen_am, stand, kandidaten) "
            "VALUES (?,?,?,?,?,?,?)",
            (loc_key, coords[0] if coords else None, coords[1] if coords else None,
             "gefunden" if coords else ("mehrdeutig" if kandidaten else "nicht_gefunden"),
             datetime.now(timezone.utc).isoformat(timespec="seconds"), SPEICHER_STAND,
             json.dumps(kandidaten, ensure_ascii=False) if kandidaten else None))
        con.commit()
    except Exception as exc:
        logger.debug("Geo-Speicher nicht beschreibbar: %s", exc)


# User-Agent for Nominatim (required)
_USER_AGENT = "PBP/0.32 bewerbungs-assistent (https://github.com/MadGapun/PBP)"


def _rate_limit():
    """Ensure at least 1 second between Nominatim requests."""
    global _last_request_time
    with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        _last_request_time = time.monotonic()


# Zusaetze, die Quellen an den Ortsstring haengen und die Nominatim
# nicht aufloesen kann. Sie stehen fast immer in Klammern oder hinter
# einem Trenner am Ende: "Aerzen, Niedersachsen (Hybrid)".
_ORT_ZUSATZ = {
    "hybrid", "remote", "vor ort", "homeoffice", "home office",
    "teilremote", "teilweise remote", "mobiles arbeiten", "vollzeit",
    "teilzeit", "befristet", "unbefristet", "festanstellung",
    "m/w/d", "m/w/x", "w/m/d", "und umgebung", "umgebung", "raum",
    "deutschland", "germany",
}


#: Einzelne Wörter, die nie einen Ort bezeichnen (#1158 Punkt 8). Ein Teil des Ortsstrings, der NUR aus solchen
#: Wörtern besteht, fällt weg: "remote möglich", "Homeoffice möglich", "teilweise hybrid". Vorher blieb "remote
#: möglich" stehen (nur "remote" allein stand in der Liste), Nominatim las "Hamburg, remote möglich" als einen
#: Ort bei Mainz - 410 km statt 20 -, und die beste Stelle des Tages rutschte durch den Entfernungsabzug auf
#: einen negativen Stand.
_ORT_ZUSATZ_WOERTER = {
    "hybrid", "remote", "homeoffice", "home", "office", "teilremote", "mobil", "mobiles", "arbeiten", "arbeit",
    "möglich", "moeglich", "optional", "wahlweise", "flexibel", "teilweise", "teils", "zeitweise", "oder", "und",
    "vor", "ort", "vollzeit", "teilzeit", "befristet", "unbefristet", "festanstellung", "umgebung", "raum",
    "ortsunabhängig", "ortsunabhaengig", "bundesweit", "deutschlandweit", "deutschland", "germany",
}


def geocoding_aktiv() -> bool:
    """False, wenn kein Weg ins Netz gehen darf (Test-Suite, #1090)."""
    import os as _os
    return _os.environ.get("PBP_GEOCODING") != "0"


def normalisiere_ort(ort: str) -> str:
    """Ortsstring von Quellen-Zusaetzen befreien (#965).

    Belegter Fall: "Aerzen, Niedersachsen (Hybrid)" scheiterte am
    Geocoding, waehrend die drei uebrigen aktiven Stellen mit sauberem
    Ort funktionierten. Der Fehlschlag blieb stumm — und weil eine
    unbekannte Entfernung im Scoring gar nicht gerechnet wird, stand
    ausgerechnet die WEITESTE Stelle mit dem hoechsten Score oben.

    Der Ortsstring ist damit ein Datenqualitaets-Nadeloehr: was hier
    durchfaellt, wird nicht als Fehler sichtbar, sondern als Vorteil.
    """
    if not ort:
        return ""
    text = str(ort)
    # Klammerzusaetze entfernen — sie tragen nie die Ortsangabe.
    text = re.sub(r"[(\[][^)\]]*[)\]]", " ", text)
    # Trenner, hinter denen Quellen das Arbeitsmodell anhaengen.
    text = re.split(r"\s+[|/·•]\s+|\s+-\s+", text)[0]
    teile = [t.strip(" ,;-") for t in text.split(",")]
    behalten = [t for t in teile
                if t and t.lower() not in _ORT_ZUSATZ
                and not all(w in _ORT_ZUSATZ_WOERTER for w in re.split(r"[\s/\-]+", t.lower()) if w)]
    return ", ".join(behalten).strip(" ,;-") or text.strip(" ,;-")


#: Ein Land am Ende des Ortstextes ("Hamburg, Germany").
_LAND_ENDE = re.compile(r"[\s,;-]*\b(?:deutschland|germany)\b\s*$", re.IGNORECASE)


def nur_land_entfernt(roh: str, ziel: str) -> bool:
    """Unterscheiden sich Rohtext und bereinigter Ort NUR um ein angehaengtes Land?

    Dann ist die Abfrage dieselbe wie vor #1158 (das Land haengt `geocode_location` ohnehin selbst an), und
    eine frueher unter dem Rohtext gemerkte Antwort gilt weiter."""
    ohne_land = _LAND_ENDE.sub("", str(roh or "").strip()).strip(" ,;-").lower()
    return bool(ohne_land) and ohne_land == str(ziel or "").strip().lower()


# === #1300: die Ortsangabe einer Stelle zerlegen ===
#
# Gemeldet am 05.11.2026 an Browser-Uebernahmen: "Hamburg u.a." lag 218 km weg (der Zusatz ging mit an den
# Dienst), "Deutschland (remote)" 619 km (ein Land wurde auf einen Punkt abgebildet), "100 % remote (Frankfurt)"
# 8.425 km (der Ort stand in der Klammer, die Klammer flog weg, gefragt wurde "100 % remote" - und der Dienst fand
# ohne Landeszusatz etwas in Uebersee), und bei "Deutschland (mostly remote; Frankfurt, Mannheim, ...)" stand im
# Feld eine andere Zahl als im Rahmen. `ort_zerlegen` ist die EINE Stelle, die aus dem Text die Orte macht; alle
# Wege (Abfrage, Schluessel, Entfernung) fragen sie.

#: Ein angehaengter Hinweis auf weitere Orte: "Hamburg u.a.", "Bremen uvm.". Ein Trenner wie das Komma. Die
#: Wortgrenzen sind Absicht: "u.a." steckt sonst in "Bau.a..." (Lehre L5).
_WEITERE_ORTE = re.compile(
    r"(?<![\w.])(?:u\.\s?a\.?|u\.\s?v\.\s?m\.?|uvm\.?|und\s+(?:weitere|andere)(?:\s+(?:standorte|orte))?"
    r"|sowie\s+weitere(?:\s+standorte)?|und\s+umgebung)(?![\w])",
    re.IGNORECASE)

#: Vollstaendig remote, ausdruecklich: "100 % remote", "fully remote", "vollständig remote".
_REMOTE_VOLL = re.compile(
    r"(?<![\w-])(?:100\s*%\s*|voll(?:ständig|staendig)?\s+|fully\s+|full\s+|komplett\s+|rein\s+|nur\s+"
    r"|ausschlie(?:ß|ss)lich\s+)remote(?!\w)",
    re.IGNORECASE)

#: Remote nur teilweise: "mostly remote", "teilweise remote", "hybrid", "remote möglich".
_REMOTE_TEIL = re.compile(
    r"(?<![\w-])(?:(?:mostly|überwiegend|ueberwiegend|teilweise|teils|partly|partially)\s+"
    r"(?:remote|home[\s-]?office)|hybrid|teilremote|(?:remote|home[\s-]?office|homeoffice)\s+"
    r"(?:möglich|moeglich|optional))(?!\w)",
    re.IGNORECASE)

#: Irgendein Remote-Hinweis. Wortgrenzen: ein Ortsname, der die Buchstabenfolge enthaelt, bleibt.
_REMOTE_WORT = re.compile(
    r"(?<![\w-])(?:remote|home[\s-]?office|homeoffice|mobiles\s+arbeiten|ortsunabh(?:ä|ae)ngig)(?!\w)",
    re.IGNORECASE)

#: Was aus einem Teil gestrichen wird, bevor er als Ort zaehlt (Remote-Angaben samt Zusatz).
_STREICHEN = re.compile(
    r"(?<![\w-])(?:100\s*%\s*|(?:voll(?:ständig|staendig)?|fully|full|komplett|rein|nur|ausschlie(?:ß|ss)lich"
    r"|mostly|überwiegend|ueberwiegend|teilweise|teils|partly|partially)\s+)?"
    r"(?:remote|home[\s-]?office|homeoffice|hybrid|teilremote|mobiles\s+arbeiten|ortsunabh(?:ä|ae)ngig)"
    r"(?:\s+(?:möglich|moeglich|optional|first))?(?!\w)",
    re.IGNORECASE)

#: Laender und grosse Raeume: sie nennen keinen Ort, sondern eine Flaeche (#1300 Punkt 3).
_LAENDER_RAEUME = {
    "deutschland", "germany", "österreich", "oesterreich", "austria", "schweiz", "switzerland", "suisse",
    "dach", "d-a-ch", "europa", "europe", "eu", "emea", "weltweit", "worldwide", "global", "anywhere",
    "bundesweit", "deutschlandweit", "europaweit", "ganz deutschland", "norddeutschland", "süddeutschland",
    "sueddeutschland", "westdeutschland", "ostdeutschland",
}

#: Bundeslaender, die keine Stadt sind. Hinter einem Ort praezisieren sie ihn ("Aerzen, Niedersachsen"), allein
#: sind sie eine Flaeche. Hamburg, Berlin und Bremen sind beides und zaehlen deshalb als Ort.
_FLAECHENLAENDER = {
    "baden-württemberg", "baden-wuerttemberg", "bayern", "brandenburg", "hessen", "mecklenburg-vorpommern",
    "niedersachsen", "nordrhein-westfalen", "nrw", "rheinland-pfalz", "saarland", "sachsen", "sachsen-anhalt",
    "schleswig-holstein", "thüringen", "thueringen",
}
_STADTSTAATEN = {"hamburg", "berlin", "bremen"}

#: Kreis, Bezirk, Region: hinter einem Ort ein Zusatz, allein eine Flaeche.
_KREIS = re.compile(r"^(?:landkreis|kreis|lk|region|bezirk|regierungsbezirk|metropolregion)\b", re.IGNORECASE)

#: Was hinter einem Schraegstrich oder in einer Klammer zum Ortsnamen gehoert: "Frankfurt/Main",
#: "Frankfurt (Oder)", "Halle/Saale". Kein zweiter Ort.
_ORTSZUSATZ_NAME = {
    "main", "m", "m.", "oder", "saale", "s.", "ruhr", "donau", "rhein", "elbe", "lahn", "neckar", "mosel",
    "weinstraße", "weinstrasse", "holstein", "isar", "inn", "fils", "havel", "spree", "weser", "ems", "opf",
    "opf.", "ofr", "ofr.", "taunus", "ts", "ts.", "wied", "dill", "fulda", "werra", "harz", "westf", "westf.",
    "westfalen", "oldb", "oldb.", "oldenburg", "breisgau", "brsg", "brsg.", "allgäu", "allgaeu", "vogtland",
    "erzgebirge", "rügen", "ruegen", "fehmarn", "sylt",
}

#: Ein Teil, der nach Strasse aussieht: dann ist der ganze Text EINE Adresse, kein Ortsliste.
_STRASSE = re.compile(r"(?:stra(?:ß|ss)e|str\.|weg|allee|platz|ring|damm|gasse|chaussee)\b", re.IGNORECASE)

#: Woerter, die in einem Teil ohne Ort uebrig bleiben ("100 %", "vor Ort", "Standort").
_REST_WOERTER = (_ORT_ZUSATZ_WOERTER - _LAENDER_RAEUME) | {"100", "%", "mostly", "first", "standort", "standorte", "in", "am",
                                       "mobile", "work", "on-site", "onsite", "m/w/d", "w/m/d", "m/w/x"}


def _klein(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _ist_flaeche(teil: str) -> bool:
    k = _klein(teil)
    return k in _LAENDER_RAEUME or k in _FLAECHENLAENDER or bool(_KREIS.match(k))


def _teil_bereinigen(teil: str) -> str:
    """Remote-Angaben und Fuellwoerter aus einem Teil streichen; leer, wenn kein Ort uebrig bleibt."""
    rest = _STREICHEN.sub(" ", teil)
    rest = re.sub(r"\s+", " ", rest).strip(" .:;-–\t")
    woerter = [w for w in re.split(r"[\s/\-]+", rest.lower()) if w]
    if not woerter or all(w in _REST_WOERTER for w in woerter):
        return ""
    return rest


def _teile(text: str) -> list:
    """Einen Text an Komma, Semikolon, Schraegstrich, Strich mit Leerzeichen und "u.a." aufteilen.

    Ein Schraegstrich vor einem Namenszusatz ("Frankfurt/Main") trennt nicht."""
    text = _WEITERE_ORTE.sub(",", text)
    roh = re.split(r"[,;|·•]|\s+[-–]\s+|/", text)
    teile: list = []
    for t in roh:
        t = t.strip()
        if teile and _klein(t) in _ORTSZUSATZ_NAME:
            teile[-1] = f"{teile[-1]}/{t}"
            continue
        teile.append(t)
    return [t for t in teile if t]


def _orte_aus(text: str) -> tuple:
    """(Orte, Flaeche genannt?) aus einem klammerfreien Text."""
    orte: list = []
    flaeche = False
    adresse = False
    for roh in _teile(text):
        teil = _teil_bereinigen(roh)
        if not teil:
            continue
        k = _klein(teil)
        if k in _LAENDER_RAEUME:
            flaeche = True
            continue
        if _ist_flaeche(teil):
            if orte:
                orte[-1] = f"{orte[-1]}, {teil}"      # "Aerzen, Niedersachsen": praezisiert den Ort davor
            else:
                flaeche = True
            continue
        if orte and k in _STADTSTAATEN and _klein(orte[-1]) == k:
            orte[-1] = f"{orte[-1]}, {teil}"          # "Hamburg, Hamburg"
            continue
        if _STRASSE.search(teil):
            adresse = True
        orte.append(teil)
    # Eine Strasse oder eine Postleitzahl neben einem zweiten Teil: das ist EINE Adresse, keine Ortsliste.
    if len(orte) > 1 and (adresse or any(re.search(r"\d", o) for o in orte)):
        orte = [", ".join(orte)]
    gesehen: set = set()
    eindeutig = []
    for o in orte:
        if _klein(o) not in gesehen:
            gesehen.add(_klein(o))
            eindeutig.append(o)
    return eindeutig, flaeche


def ort_zerlegen(location: str) -> dict:
    """Die Ortsangabe einer Stelle in Orte, Flaeche und Remote-Hinweis zerlegen (#1300) - ohne Netz.

    Rueckgabe:
      `orte`    die genannten Orte in Reihenfolge ("Hamburg u.a., Home Office" -> ["Hamburg"];
                "Deutschland (mostly remote; Frankfurt, Mannheim)" -> ["Frankfurt", "Mannheim"])
      `abfrage` die Orte, zu denen eine Entfernung gerechnet wird - leer bei vollstaendig remote: wer nie
                hinfaehrt, hat keine Entfernung ("100 % remote (Frankfurt)")
      `remote`  "remote" (vollstaendig), "teilweise" (Home Office, hybrid, mostly remote neben einem Ort) oder None
      `flaeche` ein Land oder ein Raum ist genannt ("Deutschland", "bundesweit", "Niedersachsen")

    Eine Klammer zaehlt nur, wenn vor ihr kein Ort steht ("Deutschland (Frankfurt)"), oder wenn sie zum Namen
    gehoert ("Frankfurt (Oder)"). "Aerzen, Niedersachsen (Hybrid)" bleibt "Aerzen, Niedersachsen" (#965).
    """
    text = str(location or "").strip()
    leer = {"orte": [], "abfrage": [], "remote": None, "flaeche": False}
    if not text:
        return leer
    # "Frankfurt (Oder)": eine Klammer, die zum Namen gehoert, bleibt am Namen.
    text = re.sub(r"\s*\(\s*([^()]*?)\s*\)",
                  lambda m: f"/{m.group(1)}" if _klein(m.group(1)) in _ORTSZUSATZ_NAME else f" ({m.group(1)})",
                  text)
    innen = " ; ".join(re.findall(r"[(\[]([^)\]]*)[)\]]", text))
    aussen = re.sub(r"[(\[][^)\]]*[)\]]", " ", text)
    orte, flaeche = _orte_aus(aussen)
    if not orte and innen:
        orte, flaeche_innen = _orte_aus(innen)
        flaeche = flaeche or flaeche_innen
    if _REMOTE_VOLL.search(text):
        remote = "remote"
    elif _REMOTE_TEIL.search(text):
        remote = "teilweise"
    elif _REMOTE_WORT.search(text):
        # Ein blosses "remote" neben einem Ort ("Hamburg, Remote") laesst offen, wie viel; ohne Ort davor
        # ("Deutschland (remote)", "Remote") ist es die ganze Angabe.
        remote = "teilweise" if _orte_aus(aussen)[0] else "remote"
    else:
        remote = None
    return {"orte": orte, "abfrage": [] if remote == "remote" else list(orte), "remote": remote,
            "flaeche": flaeche}


def warum_keine_entfernung(location: str) -> tuple:
    """(methode, satz), wenn die Ortsangabe selbst erklaert, warum es keine Zahl gibt - sonst ("", "") (#1300).

    Nur Gedaechtnis, kein Netz. Fuer Liste und Fit-Analyse dieselben Saetze (`wahrheit`, `entfernungs_guete`).
    """
    ort = str(location or "").strip()
    if not ort:
        return "", ""
    status = ort_auskunft(ort).get("status")
    if status == "nur_flaeche":
        return "nur_flaeche", (f"„{ort}“ nennt ein Land oder einen Raum, keinen Ort - eine Entfernung gibt es "
                               "dafür nicht. Unbekannt heißt hier nicht nah.")
    if status == "remote":
        return "remote_laut_ort", (f"„{ort}“ sagt: vollständig remote. Eine Entfernung gibt es dafür nicht.")
    if status == "ausserhalb_dach":
        return "ort_unplausibel", (f"Zu „{ort}“ fand der Ortsdienst nur einen Treffer weit außerhalb des "
                                   "deutschsprachigen Raums. PBP rät nicht: die Entfernung bleibt unbekannt. Mit PLZ im "
                                   "Ort (stelle_bearbeiten) oder von Hand gesetzter Entfernung gibt es eine Zahl.")
    return "", ""


def remote_aus_ort(job: dict) -> bool:
    """Steht im Ortsfeld "vollstaendig remote", wird es nicht weggeworfen (#1300 Punkt 1).

    Gesetzt wird NUR, wo `remote_level` leer oder `unbekannt` ist, und nur der feste Wert `remote`: was eine
    Quelle oder der Mensch angegeben hat, bleibt. "Teilweise" (Home Office oder hybrid neben einem Ort) setzt
    nichts - ob das einen Buerotag heisst oder vier, steht nicht im Ort. Gibt True zurueck, wenn gesetzt wurde.
    """
    if not isinstance(job, dict):
        return False
    if str(job.get("remote_level") or "").strip().lower() not in ("", "unbekannt"):
        return False
    if ort_zerlegen(job.get("location") or "")["remote"] != "remote":
        return False
    job["remote_level"] = "remote"
    return True


def ort_fuer_abfrage(location: str) -> str:
    """Der (erste) Ort, der an den Dienst geht - leer, wenn der Text keinen Ort nennt (#1158 Punkt 8, #1300).

    Bis v1.7.149 ging der Rohstring zuerst an Nominatim; die Bereinigung lief nur als letzter Versuch, wenn
    nichts zurueckkam. "Hamburg (hybrid), remote moeglich, Deutschland" kam aber nicht leer zurueck, sondern
    mit einem Treffer bei Mainz (410 km statt 20) - und der wurde unter dem Rohschluessel dauerhaft gemerkt.
    Ein Text, der nur aus Zusaetzen besteht ("Remote moeglich"), ist kein Ort: keine Anfrage, keine Entfernung.
    Seit #1300 kommt der Ort aus `ort_zerlegen`; nennt der Text mehrere, ist das der erste - die Entfernung
    rechnet `stellenort_aufloesen` mit dem naechsten.
    """
    abfrage = ort_zerlegen(location)["abfrage"]
    return abfrage[0] if abfrage else ""


def ort_schluessel(location: str) -> str:
    """Unter diesem Schluessel wird ein Ort gefragt und gemerkt; leer = es wird nichts gefragt.

    Die Laufkarte der Suche zaehlt ihre "verschiedenen Orte" mit genau diesem Schluessel - eine eigene
    Rechnung waere eine Zahl, die nicht zu den Abfragen passt.
    """
    return ort_fuer_abfrage(location).lower()


def ort_schluessel_alle(location: str) -> list:
    """Alle Schluessel, unter denen fuer diese Ortsangabe gefragt wird - einer je Ort (#1300)."""
    return [o.lower() for o in ort_zerlegen(location)["abfrage"]]


def _ist_ortstreffer(treffer) -> bool:
    """Ist das ein Ort (Gemeinde, Stadt, Ortsteil) - kein Park, keine Strasse, keine Postleitzahl? (#1235)"""
    raw = getattr(treffer, "raw", None) or {}
    return raw.get("class") in ("boundary", "place") and raw.get("type") != "postal_code"


def _gewicht(treffer) -> float:
    try:
        return float((getattr(treffer, "raw", None) or {}).get("importance") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _kurzname(treffer) -> str:
    """"Rosengarten, Landkreis Harburg, Niedersachsen" aus dem langen Namen des Dienstes - ohne PLZ und Land."""
    raw = getattr(treffer, "raw", None) or {}
    teile = [t.strip() for t in str(raw.get("display_name") or "").split(",") if t.strip()]
    teile = [t for t in teile if not re.fullmatch(r"\d{5}", t) and t.lower() not in ("deutschland", "germany")]
    return ", ".join(teile[:4])


def _ortsfund(treffer) -> dict:
    """Wertet die Treffer EINER Abfrage aus: eindeutig, mehrdeutig oder nichts (#1235).

    Bis v1.8.0 hiess die Abfrage `exactly_one=True`: bei einem Namen, den es in Deutschland mehrfach gibt
    (Rosengarten, Neustadt, Neuenkirchen, Lichtenau, Hohenfelde), lieferte der Dienst den Treffer mit dem hoechsten
    Gewicht, und PBP nahm ihn ohne Hinweis - eine Stelle in Baden-Württemberg stand mit 24 statt 500 km als nahe
    in der Liste. Jetzt gilt der erste Treffer nur dann als DER Ort, wenn kein anderer Ort desselben Namens,
    mehr als `MEHRDEUTIG_AB_KM` entfernt, ein aehnliches Gewicht hat (`MEHRDEUTIG_GEWICHT`). Frankfurt und Halle
    haben einen klaren Spitzenreiter; Rosengarten nicht.

    Rueckgabe: {"status": "nicht_gefunden"}, {"status": "gefunden", "koordinaten": (lat, lon)} oder
    {"status": "mehrdeutig", "kandidaten": [{"name", "lat", "lon"}, ...]}.
    """
    treffer = list(treffer or [])
    if not treffer:
        return {"status": "nicht_gefunden"}
    erster = treffer[0]
    koordinaten = (erster.latitude, erster.longitude)
    orte = [t for t in treffer if _ist_ortstreffer(t)]
    if len(treffer) == 1 or len(orte) < 2:
        return {"status": "gefunden", "koordinaten": koordinaten}
    spitze = orte[0]
    ref = (spitze.latitude, spitze.longitude)
    gegner = [t for t in orte[1:]
              if calculate_distance_km(ref, (t.latitude, t.longitude)) > MEHRDEUTIG_AB_KM
              and _gewicht(spitze) - _gewicht(t) < MEHRDEUTIG_GEWICHT]
    if not gegner:
        return {"status": "gefunden", "koordinaten": koordinaten}
    kandidaten: list = []
    for t in [spitze] + gegner:
        punkt = (t.latitude, t.longitude)
        # Dieselbe Gemeinde taucht oft als Gemeinde UND als Ortsteil auf - nur einmal nennen.
        if any(calculate_distance_km(punkt, (k["lat"], k["lon"])) < 10.0 for k in kandidaten):
            continue
        kandidaten.append({"name": _kurzname(t), "lat": punkt[0], "lon": punkt[1]})
    if len(kandidaten) < 2:
        return {"status": "gefunden", "koordinaten": koordinaten}
    return {"status": "mehrdeutig", "kandidaten": kandidaten[:5]}


def _abfragen(geolocator, anfrage: str) -> list:
    """Die Treffer des Dienstes als Liste - auch wenn ein Testdouble nur den alten Einzeltreffer kennt."""
    try:
        antwort = geolocator.geocode(anfrage, exactly_one=False, limit=MAX_TREFFER)
    except TypeError:                      # ein Dienst ohne `limit`
        antwort = geolocator.geocode(anfrage, exactly_one=False)
    if antwort is None:
        return []
    return list(antwort) if isinstance(antwort, (list, tuple)) else [antwort]


def _gedaechtnis(loc_key: str) -> Optional[dict]:
    """Was PBP zu diesem Ort schon weiss (Arbeitsspeicher), sonst None."""
    with _cache_lock:
        if loc_key not in _geo_cache:
            return None
        wert = _geo_cache[loc_key]
        if wert is not None:
            return {"status": "gefunden", "koordinaten": wert}
        kandidaten = _mehrdeutig_orte.get(loc_key)
        if kandidaten:
            return {"status": "mehrdeutig", "koordinaten": None, "kandidaten": list(kandidaten)}
        return {"status": "nicht_gefunden", "koordinaten": None}


def _ort_aufloesen(location: str, netz: bool = True) -> dict:
    """Loest EINEN Ort auf und sagt, WIE sicher das ist (#1235, #1300).

    Rueckgabe: {"status", "koordinaten", "kandidaten"?}; status ist `kein_ort` (der Text nennt keinen Ort),
    `gefunden`, `mehrdeutig` (mehrere Orte dieses Namens: keine Koordinaten), `nicht_gefunden`,
    `ausserhalb_dach` (#1300: der Dienst fand etwas fern des DACH-Raums fuer einen Ort, der keinen fremden Ort
    nennt - ein Fehlschlag, keine Entfernung) oder `nicht_erreichbar` (Dienst ausgefallen oder im Test gesperrt -
    nichts gemerkt). `netz=False` fragt nur das Gedaechtnis; was dort fehlt, ist `ungefragt`.
    """
    fund = _ort_aufloesen_roh(location, netz)
    if fund.get("status") == "gefunden" and not _plausibel(fund["koordinaten"], ort_fuer_abfrage(location)):
        logger.info("Ort '%s' lag laut Dienst bei %s - ausserhalb des DACH-Raums, gilt als nicht gefunden (#1300)",
                    location, fund["koordinaten"])
        return {"status": "ausserhalb_dach", "koordinaten": None, "treffer": fund["koordinaten"]}
    return fund


#: #1300: der Raum, in dem ein Treffer fuer einen Ort ohne fremden Landesnamen liegen muss - DACH mit Rand
#: (Grenzregionen, Luxemburg, Elsass liegen darin). Ein Treffer ausserhalb ist ein Namensvetter in Uebersee oder
#: ein Zufallstreffer der Abfrage ohne Landeszusatz: "100 % remote" lag 8.425 km weg.
DACH_RAUM = {"lat": (45.3, 55.6), "lon": (5.3, 17.6)}


def _im_dach_raum(koordinaten) -> bool:
    try:
        lat, lon = float(koordinaten[0]), float(koordinaten[1])
    except (TypeError, ValueError, IndexError):
        return False
    return (DACH_RAUM["lat"][0] <= lat <= DACH_RAUM["lat"][1]
            and DACH_RAUM["lon"][0] <= lon <= DACH_RAUM["lon"][1])


def _plausibel(koordinaten, ziel: str) -> bool:
    """Darf ein Treffer an diesen Koordinaten fuer diesen Ort stehen? (#1300 Punkt 4)

    Im DACH-Raum immer. Ausserhalb nur, wenn der Ort selbst erkennbar fremd ist ("Paris", "Brazil", #732) - dann
    stimmt die grosse Zahl. Fuer alles andere ist ein Treffer in Uebersee ein Fehlschlag: "unbekannt" statt einer
    erfundenen Zahl (#989)."""
    return _im_dach_raum(koordinaten) or is_non_dach_location(ziel)


def _ort_aufloesen_roh(location: str, netz: bool = True) -> dict:
    """Der Weg zum Dienst ohne Plausibilitaetspruefung - nur ueber `_ort_aufloesen` zu fragen."""
    # #1158 Punkt 8: gefragt wird der BEREINIGTE Ort, und er ist auch der Schluessel des Speichers.
    ziel = ort_fuer_abfrage(location)
    if not ziel:
        return {"status": "kein_ort", "koordinaten": None}
    loc_key = ziel.lower()

    # Check cache
    bekannt = _gedaechtnis(loc_key)
    if bekannt:
        return bekannt
    gespeichert, wert = _aus_speicher(loc_key)
    if gespeichert:
        with _cache_lock:
            _geo_cache[loc_key] = wert
        return _gedaechtnis(loc_key)

    # Der Rohtext trug nur ein angehaengtes Land ("Hamburg, Germany"): die Abfrage ist dieselbe wie vor #1158,
    # eine Antwort unter dem alten Schluessel gilt weiter - ohne sie muesste jeder bekannte Ort einmal neu
    # beim Dienst angefragt werden.
    alt_key = location.strip().lower()
    if alt_key != loc_key and nur_land_entfernt(location, ziel):
        with _cache_lock:
            if alt_key in _geo_cache:
                _geo_cache[loc_key] = _geo_cache[alt_key]
                if alt_key in _mehrdeutig_orte:
                    _mehrdeutig_orte[loc_key] = _mehrdeutig_orte[alt_key]
        bekannt = _gedaechtnis(loc_key)
        if bekannt:
            return bekannt
        gespeichert, wert = _aus_speicher(alt_key)
        if gespeichert:
            with _cache_lock:
                _geo_cache[loc_key] = wert
                if alt_key in _mehrdeutig_orte:
                    _mehrdeutig_orte[loc_key] = _mehrdeutig_orte[alt_key]
            return _gedaechtnis(loc_key)

    if not netz:
        return {"status": "ungefragt", "koordinaten": None}
    # #1090: in der Test-Suite geht kein Weg ins Netz (wie
    # PBP_BERUFE_LOOKUP, #969). Behandelt wie ein Ausfall: nichts gemerkt.
    import os as _os
    if _os.environ.get("PBP_GEOCODING") == "0":
        return {"status": "nicht_erreichbar", "koordinaten": None}

    # Geocode via Nominatim
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderServiceError
    except ImportError:
        logger.warning("geopy not installed — geocoding disabled")
        return {"status": "nicht_erreichbar", "koordinaten": None}

    try:
        geolocator = Nominatim(user_agent=_USER_AGENT, timeout=5)
        _rate_limit()

        # Try with country bias for better results
        search = f"{ziel}, Deutschland"
        treffer = _abfragen(geolocator, search)

        if not treffer:
            # Retry without country
            _rate_limit()
            treffer = _abfragen(geolocator, ziel)

        # Kein Rueckgriff auf den Rohstring mehr (#1158): was der bereinigte Ort nicht findet, findet der
        # Rohstring nur falsch. Eine unbekannte Entfernung ist besser als eine erfundene.

        fund = _ortsfund(treffer)
        if fund["status"] == "gefunden":
            coords = fund["koordinaten"]
            with _cache_lock:
                _geo_cache[loc_key] = coords
                _mehrdeutig_orte.pop(loc_key, None)
            _in_speicher(loc_key, coords)
            logger.debug("Geocoded '%s' -> %s", location, coords)
            return {"status": "gefunden", "koordinaten": coords}
        if fund["status"] == "mehrdeutig":
            # #1235: ein Befund ueber den Ort - der Dienst kennt mehrere. Gemerkt wird er samt Kandidaten, damit
            # die Oberflaeche sagen kann, WARUM keine Entfernung dasteht.
            with _cache_lock:
                _geo_cache[loc_key] = None
                _mehrdeutig_orte[loc_key] = fund["kandidaten"]
            _in_speicher(loc_key, None, fund["kandidaten"])
            logger.debug("Ort '%s' ist mehrdeutig: %s", location, [k["name"] for k in fund["kandidaten"]])
            return {"status": "mehrdeutig", "koordinaten": None, "kandidaten": list(fund["kandidaten"])}
        with _cache_lock:
            _geo_cache[loc_key] = None
            _mehrdeutig_orte.pop(loc_key, None)
        # Der Dienst hat geantwortet und nichts gefunden — das ist ein
        # Befund ueber den Ort. Ein Timeout oder Dienstfehler landet
        # im except-Zweig unten und wird NICHT gemerkt.
        _in_speicher(loc_key, None)
        logger.debug("Geocoding failed for '%s'", location)
        return {"status": "nicht_gefunden", "koordinaten": None}

    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning("Geocoding error for '%s': %s", location, e)
        return {"status": "nicht_erreichbar", "koordinaten": None}
    except Exception as e:
        logger.warning("Unexpected geocoding error for '%s': %s", location, e)
        return {"status": "nicht_erreichbar", "koordinaten": None}


def _heim_vorgabe():
    """Der gespeicherte Standort, wenn ein Aufrufer keinen mitgibt - nur Gedaechtnis, kein Netz."""
    if _speicher is None:
        return None
    try:
        return get_user_coordinates(_speicher)
    except Exception:  # noqa: BLE001 - eine Auskunft, nie ein Abbruch
        return None


def stellenort_aufloesen(location: str, heim=None, netz: bool = True) -> dict:
    """Die Ortsangabe einer Stelle aufloesen: bei mehreren Orten der NAECHSTE (#1300 Punkt 2).

    Die eine Stelle fuer "wo liegt diese Stelle?". `geocode_location` und `geocode_and_calculate_distance`
    fragen sie, damit Koordinaten und Entfernung derselben Stelle zum selben Ort gehoeren.

    Rueckgabe: {"status", "koordinaten", "remote", "orte", "ort"?, "km"?, "kandidaten"?}. `status` wie
    `_ort_aufloesen`, dazu `remote` (vollstaendig remote: keine Entfernung, wer faehrt nie hin) und
    `nur_flaeche` (nur ein Land oder ein Raum - "Deutschland" ist keine Adresse). `heim` ist (lat, lon) des
    Standorts; ohne ihn gilt der gespeicherte, ohne beides bei mehreren Orten der erste gefundene.
    """
    zerlegt = ort_zerlegen(location)
    basis = {"remote": zerlegt["remote"], "orte": zerlegt["orte"]}
    abfrage = zerlegt["abfrage"]
    if not abfrage:
        if zerlegt["remote"] == "remote":
            status = "remote"
        else:
            status = "nur_flaeche" if zerlegt["flaeche"] else "kein_ort"
        return {**basis, "status": status, "koordinaten": None}
    if len(abfrage) == 1:
        # Der Rohtext, nicht der Ort: so gilt eine unter "Hamburg, Germany" gemerkte Antwort weiter (#1158).
        funde = [(abfrage[0], _ort_aufloesen(location, netz))]
    else:
        funde = [(ort, _ort_aufloesen(ort, netz)) for ort in abfrage]
    gefunden = [(ort, f["koordinaten"]) for ort, f in funde if f["status"] == "gefunden"]
    if not gefunden:
        # Ein Ausfall des Dienstes sagt nichts ueber den Ort - er geht vor jedem anderen Befund.
        offen = [f for _o, f in funde if f["status"] in ("nicht_erreichbar", "ungefragt")]
        return {**basis, **(offen[0] if offen else funde[0][1])}
    if heim is None and len(gefunden) > 1:
        heim = _heim_vorgabe()
    if heim:
        entfernt = [(calculate_distance_km(tuple(heim), koord), ort, koord) for ort, koord in gefunden]
        km, ort, koord = min(entfernt, key=lambda e: e[0])
        return {**basis, "status": "gefunden", "koordinaten": koord, "ort": ort, "km": km}
    ort, koord = gefunden[0]
    return {**basis, "status": "gefunden", "koordinaten": koord, "ort": ort}


def ort_auskunft(location: str) -> dict:
    """Warum eine Stelle keine Entfernung hat - nur aus dem Gedaechtnis, nie aus dem Netz (#1300 Punkt 5).

    Derselbe Weg wie `stellenort_aufloesen`, nur ohne Dienst: `status` ist `remote`, `nur_flaeche`, `kein_ort`,
    `ausserhalb_dach`, `mehrdeutig`, `nicht_gefunden` oder `ungefragt` (noch nie gefragt)."""
    try:
        return stellenort_aufloesen(location, netz=False)
    except Exception:  # noqa: BLE001 - eine Auskunft darf die Anzeige nie kippen
        return {"status": "ungefragt", "koordinaten": None}


def geocode_location(location: str, heim=None) -> Optional[tuple[float, float]]:
    """Geocode a location string to (lat, lon) coordinates.

    Returns None if geocoding fails or location is empty/remote - und seit #1235 auch, wenn der Name mehrere
    Orte meint (Rosengarten): dann gibt es keine Koordinaten, nur die Kandidaten (`geocode_ort`).
    Seit #1300: nennt der Text mehrere Orte, die Koordinaten des naechsten zu `heim` (sonst zum gespeicherten
    Standort); ein Land allein, vollstaendig remote oder ein Treffer ausserhalb des DACH-Raums ergeben None.
    Results are cached in memory.
    """
    return stellenort_aufloesen(location, heim)["koordinaten"]


_BUNDESLAENDER = (
    "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen", "Hamburg", "Hessen",
    "Mecklenburg-Vorpommern", "Niedersachsen", "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland",
    "Sachsen-Anhalt", "Sachsen", "Schleswig-Holstein", "Thüringen",
)


def _umschreiben(text: str) -> str:
    return str(text or "").lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))


def ort_aus_anzeige(ort: str, anzeige: str) -> str:
    """Die Postleitzahl oder das Bundesland, das die Anzeige direkt hinter dem Ortsnamen nennt (#1235).

    "Rosengarten" + "... Standort: 74538 Rosengarten ..." -> "74538 Rosengarten";
    "Rosengarten" + "... in Rosengarten (Baden-Württemberg) ..." -> "Rosengarten, Baden-Württemberg".
    Leer, wenn die Anzeige nichts davon nennt oder verschiedene Angaben macht: eine PLZ, die nicht direkt vor
    dem Namen steht, gehoert vielleicht zum Firmensitz. Erst die Postleitzahl, dann das Bundesland.
    """
    name = str(ort or "").split(",")[0].strip()
    text = str(anzeige or "")
    if len(name) < 3 or not text:
        return ""
    plz = {m.group(1) for m in re.finditer(r"(?<!\d)(\d{5})\s+" + re.escape(name) + r"(?![\w-])", text, re.IGNORECASE)}
    if len(plz) == 1:
        return f"{next(iter(plz))} {name}"
    if plz:
        return ""
    umgeschrieben = _umschreiben(text)
    name_u = _umschreiben(name)
    gefunden = set()
    for land in _BUNDESLAENDER:
        muster = (r"(?<![\w-])" + re.escape(name_u) + r"\s*(?:,|\(|/|-|–|in|im)?\s*\(?\s*" + re.escape(_umschreiben(land)) + r"(?![\w-])")
        if re.search(muster, umgeschrieben):
            gefunden.add(land)
    # "Sachsen" steckt in "Sachsen-Anhalt": das laengere Land gewinnt.
    gefunden = {l for l in gefunden if not any(l != g and g.startswith(l + "-") for g in gefunden)}
    if len(gefunden) == 1:
        return f"{name}, {next(iter(gefunden))}"
    return ""


def geocode_ort(location: str, anzeige: str = "") -> dict:
    """Wie `geocode_location`, aber mit Befund: {"status", "koordinaten", "kandidaten"?, "aufgeloest_durch"?} (#1235).

    Meint der Name mehrere Orte und nennt die Anzeige Postleitzahl oder Bundesland direkt dahinter, wird damit
    ein zweites Mal gefragt ("74538 Rosengarten"); `aufgeloest_durch` nennt dann die Angabe.
    """
    fund = _ort_aufloesen(location)
    if fund["status"] != "mehrdeutig" or not anzeige:
        return fund
    genauer = ort_aus_anzeige(ort_fuer_abfrage(location), anzeige)
    if not genauer:
        return fund
    zweit = _ort_aufloesen(genauer)
    if zweit["status"] == "gefunden":
        return {**zweit, "aufgeloest_durch": genauer}
    return fund


def mehrdeutigkeit_offen(location: str) -> bool:
    """Wurde dieser Ort noch nie auf Mehrdeutigkeit geprueft - und lohnt es sich? (#1235)

    Nein bei einem Text ohne Ort, mit Postleitzahl, bei einer grossen Stadt oder einem Land (`ist_ortsname`)
    und bei jedem Ort, den PBP in dieser Fassung schon gefragt hat (Arbeitsspeicher oder Speicherzeile mit Stand).
    Nur Gedaechtnis, kein Netz.
    """
    ziel = ort_fuer_abfrage(location)
    if not ziel or re.search(r"(?<!\d)\d{5}(?!\d)", ziel) or ist_ortsname(ziel):
        return False
    loc_key = ziel.lower()
    with _cache_lock:
        if loc_key in _geo_cache:
            return False
    bekannt, _wert = _aus_speicher(loc_key)
    return not bekannt


def mehrdeutigkeit(location: str) -> Optional[list]:
    """Die Kandidaten, wenn PBP diesen Ort als mehrdeutig kennt - OHNE Netz (#1235). Sonst None.

    Zum Erklaeren, warum eine Stelle keine Entfernung hat; fragt nie den Dienst.
    """
    ziel = ort_fuer_abfrage(location)
    if not ziel:
        return None
    loc_key = ziel.lower()
    with _cache_lock:
        kandidaten = _mehrdeutig_orte.get(loc_key)
    if not kandidaten:
        _aus_speicher(loc_key)
        with _cache_lock:
            kandidaten = _mehrdeutig_orte.get(loc_key)
    return list(kandidaten) if kandidaten else None


def calculate_distance_km(coord1: tuple[float, float],
                          coord2: tuple[float, float]) -> float:
    """Calculate geodesic distance between two (lat, lon) points in km."""
    try:
        from geopy.distance import geodesic
        return round(geodesic(coord1, coord2).km, 1)
    except ImportError:
        logger.warning("geopy not installed — distance calculation disabled")
        return 0.0
    except Exception as e:
        logger.warning("Distance calculation error: %s", e)
        return 0.0


def geocode_and_calculate_distance(job_location: str,
                                   user_lat: float, user_lon: float) -> Optional[float]:
    """Geocode a job location and calculate distance to user coordinates.

    Returns distance in km, or None if geocoding fails. Nennt der Ort mehrere Orte, die Entfernung zum
    naechsten (#1300) - aus derselben Funktion wie die Koordinaten (`stellenort_aufloesen`).
    """
    if not job_location or not user_lat or not user_lon:
        return None

    heim = (user_lat, user_lon)
    job_coords = stellenort_aufloesen(job_location, heim)["koordinaten"]
    if job_coords is None:
        return None

    return calculate_distance_km(heim, job_coords)


def entfernung_aus_anzeige(job_location: str, user_lat: float, user_lon: float, anzeige: str) -> Optional[dict]:
    """Zweiter Versuch fuer einen MEHRDEUTIGEN Ort: die Anzeige nennt Postleitzahl oder Bundesland (#1235).

    Der erste Versuch (`geocode_and_calculate_distance`) liefert bei einem Namen, den es mehrfach gibt, keine
    Entfernung. Nennt die Anzeige direkt hinter dem Namen eine PLZ ("74538 Rosengarten") oder ein Bundesland,
    wird damit noch einmal gefragt. Rueckgabe: {"km", "koordinaten", "aufgeloest_durch"} oder None - auch wenn
    der Ort gar nicht mehrdeutig ist; der Aufrufer fragt zuerst auf dem gewohnten Weg.
    """
    if not job_location or not anzeige or not user_lat or not user_lon:
        return None
    if not mehrdeutigkeit(job_location):
        return None
    fund = geocode_ort(job_location, anzeige)
    if fund.get("status") != "gefunden" or not fund.get("aufgeloest_durch"):
        return None
    koord = fund["koordinaten"]
    return {"km": calculate_distance_km((user_lat, user_lon), koord), "koordinaten": koord,
            "aufgeloest_durch": fund["aufgeloest_durch"]}


def get_user_coordinates(db) -> Optional[tuple[float, float]]:
    """Get cached user coordinates from search criteria.

    Returns (lat, lon) tuple or None.
    """
    criteria = db.get_search_criteria()
    lat = criteria.get("standort_lat")
    lon = criteria.get("standort_lon")
    if lat and lon:
        return (float(lat), float(lon))
    return None


def cache_user_coordinates(db, address: str) -> Optional[tuple[float, float]]:
    """Geocode user address and cache in search criteria.

    Returns (lat, lon) tuple or None.
    """
    coords = geocode_location(address)
    if coords:
        db.set_search_criteria("standort_lat", coords[0])
        db.set_search_criteria("standort_lon", coords[1])
        logger.info("User coordinates cached: %s -> %s", address, coords)
    return coords


# === #732: Nicht-DACH-Erkennung fuer den Geo-Filter ===
#
# Hintergrund: Globale Remote-Aggregatoren (remotive, remoteok) liefern
# Stellen mit Orten wie "Brazil" oder "Remote (Florianópolis)". Das
# Geocoding haengt ", Deutschland" an die Anfrage (s.o. Zeile 71) und
# bekommt dann irgendeinen DE-Treffer mit falscher Naehe (z.B. 533 km
# statt ~10.000 km). Der Entfernungs-Malus ist zudem gedeckelt und reicht
# nicht, eine solche Stelle aus dem aktiven Pool zu draengen. Darum eine
# String-Heuristik VOR dem Geocoding.
#
# Konservativ by design: Ein DACH-Marker gewinnt IMMER (-> False). Nur ein
# klarer Auslands-Marker OHNE DACH-Marker liefert True. Unbekannte oder
# leere Orte bleiben False (kein Auto-Aussortieren bei Unsicherheit).

# Reine Remote-/Weitraum-Angaben ohne Ortsbezug — koennen DACH sein,
# darum NICHT filtern.
_GEO_PURE_REMOTE = {
    "remote", "home office", "homeoffice", "deutschlandweit", "bundesweit",
    "weltweit", "worldwide", "europa", "europe", "eu", "global", "anywhere",
    "remote (eu)", "eu remote", "europe remote", "remote europe",
}

# DACH-Marker: Laendernamen/Codes + grosse Staedte als Positivliste.
_GEO_DACH_MARKERS = {
    "deutschland", "germany", "allemagne", "de", "ger", "deu", "brd",
    "oesterreich", "österreich", "austria", "at", "aut",
    "schweiz", "switzerland", "suisse", "svizzera", "ch", "che", "dach",
    "berlin", "hamburg", "muenchen", "münchen", "munich", "koeln", "köln",
    "cologne", "frankfurt", "stuttgart", "duesseldorf", "düsseldorf",
    "dortmund", "essen", "leipzig", "dresden", "hannover", "nuernberg",
    "nürnberg", "nuremberg", "bremen", "bonn", "mannheim", "karlsruhe",
    "wiesbaden", "muenster", "münster", "kiel", "wedel", "pinneberg",
    "wien", "vienna", "graz", "linz", "salzburg", "innsbruck", "klagenfurt",
    "zuerich", "zürich", "zurich", "bern", "basel", "genf", "geneva",
    "geneve", "lausanne", "luzern", "lucerne", "winterthur",
}

def ist_ortsname(name) -> bool:
    """Ist das der Name einer grossen DACH-Stadt oder eines DACH-Landes?

    Aus derselben Liste wie die Standort-Erkennung (#1124): eine zweite
    Ortsliste im PII-Pruefer waere die Bauform aus #963. Verglichen wird
    der GANZE Name - "Hamburg" ja, "Hamburg Wasser" nein.
    """
    return " ".join(str(name or "").lower().split()) in _GEO_DACH_MARKERS


# Klare Auslands-Marker (Laender).
_GEO_NON_DACH_COUNTRIES = {
    "usa", "u.s.a", "us", "united states", "america", "uk", "u.k",
    "united kingdom", "england", "scotland", "wales", "ireland", "irland",
    "brazil", "brasil", "brasilien", "india", "indien", "china", "japan",
    "poland", "polen", "polska", "france", "frankreich", "spain", "spanien",
    "espana", "españa", "italy", "italien", "italia", "portugal",
    "netherlands", "niederlande", "nederland", "holland", "belgium",
    "belgien", "belgique", "sweden", "schweden", "norway", "norwegen",
    "denmark", "daenemark", "dänemark", "finland", "finnland", "czech",
    "czechia", "tschechien", "slovakia", "slowakei", "hungary", "ungarn",
    "romania", "rumaenien", "rumänien", "bulgaria", "bulgarien", "greece",
    "griechenland", "ukraine", "russia", "russland", "turkey", "tuerkei",
    "türkei", "canada", "kanada", "mexico", "mexiko", "argentina",
    "argentinien", "chile", "colombia", "kolumbien", "peru", "uruguay",
    "venezuela", "singapore", "singapur", "australia", "australien",
    "new zealand", "neuseeland", "philippines", "philippinen", "indonesia",
    "indonesien", "malaysia", "vietnam", "thailand", "egypt", "aegypten",
    "ägypten", "morocco", "marokko", "south africa", "suedafrika",
    "südafrika", "nigeria", "kenya", "kenia", "israel", "uae", "emirates",
    "dubai", "abu dhabi", "qatar", "katar", "saudi", "pakistan", "bangladesh",
}

# Notorische Auslands-Staedte aus globalen Remote-Aggregatoren.
_GEO_NON_DACH_CITIES = {
    "florianopolis", "florianópolis", "sao paulo", "são paulo",
    "rio de janeiro", "new york", "san francisco", "los angeles", "chicago",
    "boston", "austin", "seattle", "denver", "miami", "atlanta", "toronto",
    "vancouver", "montreal", "london", "manchester", "dublin", "paris",
    "lyon", "madrid", "barcelona", "lisbon", "lissabon", "lisboa", "porto",
    "amsterdam", "rotterdam", "brussels", "bruessel", "warsaw", "warschau",
    "krakow", "krakau", "wroclaw", "prague", "prag", "bangalore",
    "bengaluru", "mumbai", "delhi", "hyderabad", "pune", "chennai", "manila",
    "jakarta", "singapore city", "tel aviv", "sydney", "melbourne",
}


def is_non_dach_location(location: str) -> bool:
    """True, wenn der Ort erkennbar ausserhalb DACH liegt (#732).

    Konservativ: ein DACH-Marker gewinnt immer; nur ein klarer
    Auslands-Marker ohne DACH-Marker liefert True. Leere, reine Remote-
    oder unbekannte Orte liefern False (kein Auto-Aussortieren bei
    Unsicherheit).
    """
    if not location:
        return False
    loc = location.strip().lower()
    if not loc or loc in _GEO_PURE_REMOTE:
        return False

    # Einwort-Marker per Token, Mehrwort-/gepunktete Marker per Substring.
    # \w ist in Python-3-str-Regex Unicode-aware und erfasst akzentuierte
    # Buchstaben (z.B. "florianópolis", "münchen") als ganzes Token.
    tokens = set(re.findall(r"\w+", loc))

    def _has(markers: set) -> bool:
        for m in markers:
            if " " in m or "." in m:
                if m in loc:
                    return True
            elif m in tokens:
                return True
        return False

    # DACH gewinnt immer.
    if _has(_GEO_DACH_MARKERS):
        return False
    if _has(_GEO_NON_DACH_COUNTRIES) or _has(_GEO_NON_DACH_CITIES):
        return True
    return False
