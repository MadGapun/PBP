"""Mail-Ordner als Quelle: die Zugangsschicht vor dem Mail-Ingest (#947, I-/J13).

Der Mail-Ingest ist gebaut (Ingest-API #504, Thunderbird-Add-on #478, Newsletter-Erkennung #525). Was fehlte, ist die
Frage davor: unter welchen Bedingungen darf überhaupt ein Mail-Ordner gelesen werden? Ein Ordner ist der
weitreichendste Datenzugriff, den PBP je hätte: private Korrespondenz, die danach eine KI liest. Deshalb:

* **Vorgabe AUS.** Ohne Einschalten wird kein Ordner gelesen. Kein Einschalten durch ein Update, kein „wir haben gemerkt,
  dass du Thunderbird nutzt“.
* **Harte Whitelist.** Der Mensch nennt die Ordner, die gelesen werden dürfen. Genau diese, kein Platzhalter, keine
  Vererbung auf Unterordner. Leere Liste heißt: nichts. Der Posteingang als Ganzes geht nur nach ausdrücklicher Warnung.
* **Zwei Betriebsarten, getrennt.** Push (der Mensch schickt eine Mail bewusst ans Add-on „An PBP senden“) bleibt
  unverändert und braucht keinen Schalter. Ordner-Scan (ein Add-on liest freigegebene Ordner von sich aus) ist AUS.
* **Anbieterunabhängig.** Die Regel sitzt hier, in PBP, nicht in einem Add-on: jedes Add-on (Thunderbird, Outlook, ...)
  fragt `GET /api/v1/ingest/mail-policy` und sendet bei jeder Scan-Mail Anbieter, Konto und Ordner mit; PBP prüft
  gegen die Liste und weist alles andere ab, bevor irgendetwas gespeichert wird.

PBP selbst öffnet nie ein Postfach (kein IMAP, kein POP): ein Test hält das fest. Es nimmt nur entgegen, was ein
gekoppeltes Add-on schickt, und prüft vorher, ob es das darf.

Im Zweifel gilt der restriktivere Zustand (Nutzer-Entscheidung 21.08.2026): eine Einstellung aus einer anderen
Version, die sich nicht eindeutig lesen lässt, ergibt „aus“ und „leere Liste“ und einen Hinweis, nie „mehr Zugriff“.
Eine in einer Beta eingeschaltete Quelle gilt in einer stabilen Version erst nach erneuter Bestätigung.
"""
from __future__ import annotations

import logging
import re
import threading
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("bewerbungs_assistent.mail_quelle")

SCHLUESSEL = "mail_ordner_quelle"
FORMAT = 1
MAX_FREIGABEN = 50
MAX_LAENGE = 200

ANBIETER = {
    "thunderbird": "Thunderbird",
    "outlook": "Outlook",
    "sonstige": "Anderes Mail-Programm",
}

#: Ordnername, der den ganzen Posteingang meint. Das ist erlaubt, aber nur nach ausdrücklicher Warnung.
POSTEINGANG_NAMEN = frozenset({"inbox", "posteingang", "eingang"})

EINSCHALTEN_TEXT = (
    "Der Ordner-Scan erlaubt einem gekoppelten Mail-Add-on, von sich aus Ordner zu lesen, die du freigibst. "
    "Dort liegt private Korrespondenz; PBP speichert die Mails und eine KI kann sie lesen. Möchtest du das? "
    "Gelesen wird nur, was in der Liste der freigegebenen Ordner steht, sonst nichts. Du kannst jederzeit abschalten.")

POSTEINGANG_WARNUNG = (
    "Das ist der Posteingang als Ganzes. Dort liegt alles, nicht nur Stellenangebote: Arztmails, Kontoauszüge, "
    "Familie. Besser ist ein eigener Ordner nur für Jobmails (ein Filter in deinem Mail-Programm sortiert sie "
    "dorthin). Willst du trotzdem den ganzen Posteingang freigeben?")

_LOCK = threading.RLock()
_UNERLAUBT = re.compile(r"[\x00-\x1f\x7f*?]")


# ── Zustand lesen und schreiben ──────────────────────────────────────────────────────────────────────

def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _version() -> str:
    from .. import __version__
    return __version__


def _vorabversion(version) -> bool:
    """Alpha, Beta, RC. Eine unlesbare Fassung gilt als Vorabversion (im Zweifel restriktiv)."""
    from .auto_update import fassung
    return not fassung.ist_stabil(version)


def _leer() -> dict:
    return {"format": FORMAT, "scan_aktiv": False, "aktiviert_am": None, "aktiviert_in": None, "freigaben": []}


def _freigabe_gueltig(f) -> bool:
    return (isinstance(f, dict) and isinstance(f.get("id"), str) and f.get("anbieter") in ANBIETER
            and isinstance(f.get("konto"), str) and isinstance(f.get("ordner"), str) and f["ordner"].strip() != ""
            and isinstance(f.get("mails", 0), int) and isinstance(f.get("stellen", 0), int))


def lesen(db) -> dict:
    """Der gespeicherte Zustand — oder der sichere, wenn er sich nicht eindeutig lesen lässt (`unlesbar`)."""
    roh = db.get_setting(SCHLUESSEL, None)
    if roh is None:
        return {**_leer(), "unlesbar": False}
    ok = (isinstance(roh, dict) and roh.get("format") == FORMAT and isinstance(roh.get("scan_aktiv"), bool)
          and isinstance(roh.get("freigaben"), list) and len(roh["freigaben"]) <= MAX_FREIGABEN
          and all(_freigabe_gueltig(f) for f in roh["freigaben"]))
    if not ok:
        logger.warning("Mail-Ordner-Einstellung nicht eindeutig lesbar: sicherer Zustand (aus, leere Liste)")
        return {**_leer(), "unlesbar": True}
    zustand = {**_leer(), **{k: roh.get(k) for k in ("scan_aktiv", "aktiviert_am", "aktiviert_in")}}
    zustand["freigaben"] = [{"id": f["id"], "anbieter": f["anbieter"], "konto": f["konto"], "ordner": f["ordner"],
                             "posteingang": bool(f.get("posteingang")), "angelegt": f.get("angelegt"),
                             "letzter_lauf": f.get("letzter_lauf"), "mails": int(f.get("mails", 0)),
                             "stellen": int(f.get("stellen", 0))} for f in roh["freigaben"]]
    zustand["unlesbar"] = False
    return zustand


def _speichern(db, zustand: dict) -> None:
    db.set_setting(SCHLUESSEL, {k: zustand[k] for k in ("format", "scan_aktiv", "aktiviert_am", "aktiviert_in", "freigaben")})


def bestaetigung_noetig(zustand: dict) -> bool:
    """Eingeschaltet in einer Beta, jetzt läuft eine stabile Fassung: erst nach erneuter Bestätigung wieder aktiv."""
    return bool(zustand.get("scan_aktiv") and zustand.get("aktiviert_in")
                and _vorabversion(zustand["aktiviert_in"]) and not _vorabversion(_version()))


def wirksam(db) -> bool:
    """Darf gerade ein Ordner gelesen werden? Nur wenn eingeschaltet, lesbar und (bei Beta-Herkunft) neu bestätigt."""
    z = lesen(db)
    return bool(z["scan_aktiv"] and not z["unlesbar"] and not bestaetigung_noetig(z))


# ── Ordnernamen ──────────────────────────────────────────────────────────────────────────────────────

def ordner_normalisieren(text) -> str:
    """„ Jobs \\ Portale/ “ → „Jobs/Portale“. Leer, wenn nichts Brauchbares übrig bleibt."""
    teile = [t.strip() for t in str(text or "").replace("\\", "/").split("/")]
    return "/".join(t for t in teile if t)


def _schluessel(anbieter: str, konto: str, ordner: str) -> tuple:
    return (str(anbieter).strip().casefold(), str(konto or "").strip().casefold(), ordner_normalisieren(ordner).casefold())


def ist_posteingang(ordner: str) -> bool:
    teile = ordner_normalisieren(ordner).split("/")
    return len(teile) == 1 and teile[0].casefold() in POSTEINGANG_NAMEN


# ── Die Einstellung ändern ───────────────────────────────────────────────────────────────────────────

def scan_einschalten(db, *, bestaetigt: bool = False) -> dict:
    """Schaltet den Ordner-Scan ein — nur mit ausdrücklicher Bestätigung. Eine leere Liste bleibt leer: dann wird nichts gelesen."""
    if not bestaetigt:
        return {"status": "bestaetigung_noetig", "text": EINSCHALTEN_TEXT}
    with _LOCK:
        z = lesen(db)
        if z["unlesbar"]:
            z = _leer()
        z.update(scan_aktiv=True, aktiviert_am=_jetzt(), aktiviert_in=_version())
        _speichern(db, z)
    logger.info("Mail-Ordner-Scan eingeschaltet (%d freigegebene Ordner)", len(z["freigaben"]))
    return {"status": "an", "freigaben": len(z["freigaben"]), "text": (
        "Der Ordner-Scan ist an. " + ("Die Liste der freigegebenen Ordner ist noch leer: es wird nichts gelesen, bis du einen Ordner "
                                      "freigibst." if not z["freigaben"] else "Gelesen werden nur die freigegebenen Ordner."))}


def scan_ausschalten(db) -> dict:
    """Schaltet ab — sofort. Sagt, was mit den bereits importierten Daten geschieht (nichts: sie bleiben)."""
    with _LOCK:
        z = lesen(db)
        mails = sum(f["mails"] for f in z["freigaben"])
        stellen = sum(f["stellen"] for f in z["freigaben"])
        if z["unlesbar"]:
            z = _leer()
        z.update(scan_aktiv=False)
        _speichern(db, z)
    logger.info("Mail-Ordner-Scan ausgeschaltet")
    return {"status": "aus", "importiert": {"mails": mails, "stellen": stellen}, "text": (
        "Der Ordner-Scan ist aus. PBP nimmt ab sofort keine Mails mehr aus Ordnern entgegen. "
        f"Was bereits importiert wurde ({mails} Mails, {stellen} Stellen) bleibt in PBP: Die Stellen findest du unter Stellen, "
        "die archivierten Mails unter Dokumente. Löschen kannst du sie dort oder über „Stellen nach Quelle entfernen“. "
        "Die Liste der freigegebenen Ordner bleibt gespeichert, bis du sie entfernst. Mails, die du selbst mit „An PBP senden“ "
        "schickst, funktionieren weiter wie bisher.")}


def freigabe_hinzufuegen(db, anbieter: str, ordner: str, konto: str = "", *, posteingang_bestaetigt: bool = False) -> dict:
    """Gibt GENAU diesen Ordner frei (kein Platzhalter, keine Unterordner). Der Posteingang braucht eine Bestätigung."""
    anbieter = str(anbieter or "").strip().casefold()
    if anbieter not in ANBIETER:
        return {"status": "fehler", "text": f"Unbekanntes Mail-Programm „{anbieter}“.", "erlaubt": list(ANBIETER)}
    roh = str(ordner or "")
    norm = ordner_normalisieren(roh)
    konto = str(konto or "").strip()
    if not norm:
        return {"status": "fehler", "text": "Der Ordnername fehlt."}
    if _UNERLAUBT.search(roh) or _UNERLAUBT.search(konto):
        return {"status": "fehler", "text": ("Platzhalter (* oder ?) und Steuerzeichen sind nicht erlaubt. Freigegeben wird genau "
                                             "ein Ordner, nicht mehrere auf einmal.")}
    if len(norm) > MAX_LAENGE or len(konto) > MAX_LAENGE:
        return {"status": "fehler", "text": f"Der Name ist zu lang (höchstens {MAX_LAENGE} Zeichen)."}
    inbox = ist_posteingang(norm)
    if inbox and not posteingang_bestaetigt:
        return {"status": "posteingang_warnung", "text": POSTEINGANG_WARNUNG, "ordner": norm}
    with _LOCK:
        z = lesen(db)
        if z["unlesbar"]:
            z = _leer()
        if len(z["freigaben"]) >= MAX_FREIGABEN:
            return {"status": "fehler", "text": f"Mehr als {MAX_FREIGABEN} freigegebene Ordner sind nicht vorgesehen."}
        if any(_schluessel(f["anbieter"], f["konto"], f["ordner"]) == _schluessel(anbieter, konto, norm) for f in z["freigaben"]):
            return {"status": "schon_da", "text": "Dieser Ordner ist schon freigegeben."}
        eintrag = {"id": "mo_" + uuid.uuid4().hex[:10], "anbieter": anbieter, "konto": konto, "ordner": norm, "posteingang": inbox,
                   "angelegt": _jetzt(), "letzter_lauf": None, "mails": 0, "stellen": 0}
        z["freigaben"].append(eintrag)
        _speichern(db, z)
    logger.info("Mail-Ordner freigegeben: %s (%s)%s", norm, anbieter, " [Posteingang]" if inbox else "")
    return {"status": "freigegeben", "freigabe": eintrag, "text": (
        f"Der Ordner „{norm}“ ist freigegeben." + ("" if wirksam(db) else " Gelesen wird erst, wenn der Ordner-Scan an ist."))}


def freigabe_entfernen(db, freigabe_id: str) -> dict:
    """Nimmt die Freigabe zurück — wirkt sofort. Bereits importierte Mails und Stellen bleiben."""
    with _LOCK:
        z = lesen(db)
        rest = [f for f in z["freigaben"] if f["id"] != freigabe_id]
        if len(rest) == len(z["freigaben"]):
            return {"status": "nicht_gefunden", "text": "Diese Freigabe gibt es nicht (mehr)."}
        z["freigaben"] = rest
        _speichern(db, z)
    return {"status": "entfernt", "text": "Die Freigabe ist zurückgenommen. Aus diesem Ordner nimmt PBP nichts mehr entgegen; was schon importiert wurde, bleibt."}


def zuruecksetzen(db) -> dict:
    """Alles auf Anfang: Scan aus, Liste leer. Importierte Daten bleiben."""
    with _LOCK:
        z = lesen(db)
        mails = sum(f["mails"] for f in z["freigaben"])
        stellen = sum(f["stellen"] for f in z["freigaben"])
        _speichern(db, _leer())
    return {"status": "zurueckgesetzt", "importiert": {"mails": mails, "stellen": stellen}, "text": (
        "Der Ordner-Scan ist aus und die Liste der freigegebenen Ordner ist leer. "
        f"Bereits importierte Daten ({mails} Mails, {stellen} Stellen) bleiben in PBP.")}


# ── Die Prüfung: darf diese Mail aus diesem Ordner herein? ─────────────────────────────────────────────────

def pruefe_scan(db, anbieter: str, konto: str, ordner: str) -> dict:
    """Entscheidet über eine Mail, die ein Add-on im Ordner-Scan schickt. Ablehnen ist der Normalfall.

    Rückgabe: {'erlaubt': bool, 'code': ..., 'text': ..., 'freigabe_id': ...}. Geprüft wird auf GENAUE Übereinstimmung von
    Anbieter, Konto und Ordner mit einer Freigabe: ein Unterordner, ein Elternordner oder eine Mail, die über eine
    Antwort-Kette (Thread) „zu“ einem freigegebenen Ordner gehört, ist NICHT freigegeben.
    """
    z = lesen(db)
    if z["unlesbar"]:
        return _nein("einstellung_unlesbar", "Die Mail-Einstellung ließ sich nicht sicher lesen; der Ordner-Scan ist zur Sicherheit aus.")
    if bestaetigung_noetig(z):
        return _nein("neu_bestaetigen", "Der Ordner-Scan wurde in einer Beta eingeschaltet. In dieser stabilen Version muss er erneut "
                                        "bestätigt werden (Einstellungen › Quellen im Detail › Mail-Ordner).")
    if not z["scan_aktiv"]:
        return _nein("scan_aus", "Der Ordner-Scan ist aus. Einschalten: Einstellungen › Quellen im Detail › Mail-Ordner.")
    if not z["freigaben"]:
        return _nein("whitelist_leer", "Es ist kein Ordner freigegeben. Gib erst einen Ordner frei.")
    if not str(ordner or "").strip() or not str(anbieter or "").strip():
        return _nein("ordner_fehlt", "Zur Mail fehlen Anbieter und Ordner. Ohne sie kann PBP nicht prüfen, ob sie hereindarf.")
    gesucht = _schluessel(anbieter, konto, ordner)
    for f in z["freigaben"]:
        if _schluessel(f["anbieter"], f["konto"], f["ordner"]) == gesucht:
            return {"erlaubt": True, "code": "ok", "text": "", "freigabe_id": f["id"]}
    return _nein("ordner_nicht_freigegeben", "Dieser Ordner ist nicht freigegeben. PBP nimmt nur Mails aus freigegebenen Ordnern entgegen.")


def _nein(code: str, text: str) -> dict:
    return {"erlaubt": False, "code": code, "text": text, "freigabe_id": None}


def lauf_verbuchen(db, freigabe_id: str, *, mails: int = 1, stellen: int = 0) -> None:
    """Zählt eine verarbeitete Mail (und die daraus entstandenen Stellen) bei ihrem Ordner."""
    with _LOCK:
        z = lesen(db)
        if z["unlesbar"]:
            return
        for f in z["freigaben"]:
            if f["id"] == freigabe_id:
                f["mails"] += int(mails)
                f["stellen"] += int(stellen)
                f["letzter_lauf"] = _jetzt()
                _speichern(db, z)
                return


# ── Auskunft ─────────────────────────────────────────────────────────────────────────────────────────

def richtlinie(db) -> dict:
    """Was ein Add-on lesen darf (`GET /api/v1/ingest/mail-policy`). Ist der Scan nicht wirksam, ist die Liste LEER."""
    z = lesen(db)
    ok = wirksam(db)
    freigaben = [{"id": f["id"], "anbieter": f["anbieter"], "konto": f["konto"], "ordner": f["ordner"]} for f in z["freigaben"]] if ok else []
    if ok and freigaben:
        hinweis = "Lies genau diese Ordner, keinen anderen, und sende Anbieter, Konto und Ordner bei jeder Mail mit (modus=scan)."
    elif ok:
        hinweis = "Der Ordner-Scan ist an, aber kein Ordner ist freigegeben: lies nichts."
    else:
        hinweis = "Der Ordner-Scan ist aus: lies keinen Ordner. Mails, die der Mensch bewusst sendet (modus=push), bleiben erlaubt."
    return {"ordner_scan": ok, "freigaben": freigaben, "hinweis": hinweis, "modi": ["push", "scan"]}


def uebersicht(db) -> dict:
    """Alles für Dashboard und Claude: Schalter, Freigaben mit Zahlen, Hinweise."""
    z = lesen(db)
    ok = wirksam(db)
    hinweise = []
    if z["unlesbar"]:
        hinweise.append("Die Mail-Einstellung aus einer anderen Version ließ sich nicht sicher übernehmen. Zur Sicherheit ist der "
                        "Ordner-Scan aus und die Liste leer. Richte ihn bei Bedarf neu ein.")
    if bestaetigung_noetig(z):
        hinweise.append("Der Ordner-Scan wurde in einer Beta eingeschaltet und ist in dieser stabilen Version aus, bis du ihn "
                        "erneut bestätigst.")
    return {
        "scan_aktiv": z["scan_aktiv"], "wirksam": ok, "unlesbar": z["unlesbar"], "neu_bestaetigen": bestaetigung_noetig(z),
        "aktiviert_am": z["aktiviert_am"], "aktiviert_in": z["aktiviert_in"],
        "freigaben": z["freigaben"], "anbieter": ANBIETER, "hinweise": hinweise,
        "summe": {"mails": sum(f["mails"] for f in z["freigaben"]), "stellen": sum(f["stellen"] for f in z["freigaben"])},
        "push": ("Mails, die du selbst im Mail-Programm mit „An PBP senden“ schickst, brauchen diesen Schalter nicht "
                 "und funktionieren immer."),
        "einschalten_text": EINSCHALTEN_TEXT,
    }
