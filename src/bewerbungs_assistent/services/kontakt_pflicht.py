"""Ein Kontakt entsteht bei der INTERAKTION, nicht am Anlageweg (#1011).

Nutzerregel vom 09.09.2026:

    "Sobald mit einer Stelle mehr geschieht als eine Analyse, also sobald
    ein Austausch stattfindet, soll der zugehoerige Kontakt angelegt
    werden. Denn ab diesem Moment gibt es eine Historie, und eine
    Historie braucht jemanden, an dem sie haengt."

## Der gemessene Fall

An einem Arbeitstag kamen 14 Stellen herein: 11 ueber eine
Sammeluebernahme, 3 einzeln von Hand. Das Einzel-Werkzeug nimmt
Kontaktdaten entgegen, das Sammel-Werkzeug hatte **keine
Kontaktfelder**. Ergebnis: bei den 11 wurde kein einziger
Ansprechpartner erfasst — obwohl in mindestens einem Anzeigentext eine
Ansprechpartnerin namentlich stand.

**Ob ein Kontakt entsteht, hing also am Anlageweg.** Genau das ist die
Bauform, die dieses Projekt schon neunmal gekostet hat (#963, #913,
#976, #987, #991, #992, #994, #1008, #1012): dieselbe Frage an zwei
Stellen, verschieden beantwortet.

## Die Abgrenzung ist die eigentliche Regel

*Keine* Interaktion, kein Kontakt: finden, sichten, bewerten,
vergleichen, aussortieren. **Reine Lesevorgaenge erzeugen nichts.**
Ein Ansprechpartner aus einer Anzeige, mit dem nie gesprochen wurde, ist
eine Karteikarte; einer, mit dem ein Austausch lief, ist eine Historie.

## Dubletten

Eine Regel "bei jeder Interaktion einen Kontakt" ohne Wiedererkennung
haette die Kontaktliste innerhalb weniger Tage geflutet — `add_contact`
prueft nichts. Deshalb sucht dieser Dienst zuerst:

1. ueber die **E-Mail** (der starke Beleg — eine Adresse gehoert einem),
2. sonst ueber **Name plus Firma** (zwei gleichnamige Personen bei
   derselben Firma sind selten genug, zwei gleichnamige bei
   verschiedenen Firmen nicht).

Nur Name allein reicht NICHT. "Herr Schmidt" bei zwei Arbeitgebern sind
zwei Menschen, und zwei Historien in einer Karteikarte
zusammenzuwerfen waere schlimmer als eine Dublette.
"""
from __future__ import annotations

import re

_LEER = re.compile(r"[^a-z0-9äöüß]+")


def _norm(wert) -> str:
    """Kleinschreibung ohne Interpunktion — zum Vergleichen, nicht zum
    Anzeigen."""
    return _LEER.sub(" ", str(wert or "").lower()).strip()


def _vorhandener(db, name: str, email: str, firma: str, telefon: str = ""):
    """Der bereits erfasste Kontakt, oder None."""
    # Die Methode heisst `list_contacts` — mein erster Entwurf rief
    # `get_contacts()`, und das `except` haette den AttributeError still
    # verschluckt: die Dublettenpruefung waere abgeschaltet gewesen, ohne
    # dass es jemandem auffaellt. Deshalb faengt der Block nur noch, was
    # bei einer DB-Abfrage wirklich schiefgehen kann, und ein Test
    # prueft, dass die Wiedererkennung greift.
    try:
        # #1110: auch unbestaetigte Vorschlaege — sonst wird dieselbe
        # Person bei jedem Lauf ein weiterer Vorschlag.
        alle = db.list_contacts(mit_vorschlaegen=True) or []
    except Exception:
        return None
    email_n = _norm(email)
    if email_n:
        for k in alle:
            if _norm(k.get("email")) == email_n:
                return k
    name_n, firma_n = _norm(name), _norm(firma)
    if name_n and firma_n:
        for k in alle:
            if (_norm(k.get("full_name")) == name_n
                    and _norm(k.get("company")) == firma_n):
                return k
    telefon_n = _nur_ziffern(telefon)
    if telefon_n and not name_n and not email_n:
        # #1110: ein Kontakt nur mit Telefonnummer wurde nie wiedererkannt.
        for k in alle:
            if _nur_ziffern(k.get("phone")) == telefon_n:
                return k
    return None


def _nur_ziffern(wert) -> str:
    ziffern = re.sub(r"\D", "", str(wert or ""))
    return ziffern if len(ziffern) >= 6 else ""


def _vorschlag_schluessel(name: str, email: str, firma: str, telefon: str = "") -> str:
    """Hash, an dem eine Ablehnung wiedererkannt wird (#1110) — wie die
    Wiedererkennung: Mail, sonst Name plus Firma, sonst Telefon."""
    import hashlib
    if _norm(email):
        roh = "m:" + _norm(email)
    elif _norm(name) and _norm(firma):
        roh = "n:" + _norm(name) + "|" + _norm(firma)
    elif _nur_ziffern(telefon):
        roh = "t:" + _nur_ziffern(telefon)
    else:
        return ""
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:32]


def ablehnung_merken(db, kontakt: dict) -> bool:
    """Ein verworfener Vorschlag kommt nicht wieder (#1110)."""
    s = _vorschlag_schluessel(kontakt.get("full_name") or "", kontakt.get("email") or "",
                              kontakt.get("company") or "", kontakt.get("phone") or "")
    if not s:
        return False
    from datetime import datetime, timezone
    con = db.connect()
    con.execute("INSERT OR IGNORE INTO kontakt_vorschlag_abgelehnt "
                "(profile_id, schluessel, created_at) VALUES (?, ?, ?)",
                (db.get_active_profile_id(), s, datetime.now(timezone.utc).isoformat()))
    con.commit()
    return True


def _abgelehnt(db, name: str, email: str, firma: str, telefon: str) -> bool:
    s = _vorschlag_schluessel(name, email, firma, telefon)
    if not s:
        return False
    try:
        return db.connect().execute(
            "SELECT 1 FROM kontakt_vorschlag_abgelehnt WHERE schluessel=? "
            "AND (profile_id=? OR profile_id IS NULL)",
            (s, db.get_active_profile_id())).fetchone() is not None
    except Exception:
        return False


def sicherstellen(db, *, name: str = "", email: str = "", telefon: str = "",
                  firma: str = "", ziel_art: str = "", ziel_id: str = "",
                  rolle: str = "ansprechpartner",
                  tags: list | None = None,
                  zusatz: dict | None = None,
                  vorschlag: bool = False) -> dict:
    """Sorgt dafuer, dass es zu dieser Interaktion einen Kontakt gibt.

    Args:
        name/email/telefon: was ueber die Person bekannt ist. Ohne jede
            dieser Angaben passiert NICHTS — einen Kontakt ohne Person
            anzulegen waere eine erfundene Karteikarte.
        firma: fuer die Wiedererkennung und als Anzeige-Firma.
        ziel_art/ziel_id: woran der Kontakt haengt ('job', 'application').
        rolle: die Rolle in dieser Verknuepfung.
        tags: Rollen-Tags am Kontakt selbst.
        zusatz: weitere Felder fuer den Datensatz (z.B. `is_pending`
            und `extracted_from` beim automatischen Auslesen aus
            Korrespondenz). Sie gehen NUR in einen neu angelegten
            Kontakt ein — einen bestehenden mit einem
            "unbestaetigt"-Merkmal zu ueberschreiben waere ein
            Rueckschritt.

    Returns:
        dict mit `status` ('angelegt', 'vorhanden', 'uebersprungen',
        'fehler'), bei Erfolg `id` und `name`.

    Wirft nie: eine fehlende Karteikarte darf den Vorgang, an dem sie
    haengt, nicht kippen. Das war schon in `_stelle_uebernehmen` so
    entschieden und bleibt es.
    """
    name, email, telefon = (name or "").strip(), (email or "").strip(), (telefon or "").strip()
    firma = (firma or "").strip()
    if not (name or email or telefon):
        return {"status": "uebersprungen",
                "grund": "keine Angaben zur Person"}

    try:
        # #1110: ein automatischer Vorschlag, den der Mensch schon einmal
        # verworfen hat, kommt nicht wieder.
        if vorschlag and _abgelehnt(db, name, email, firma, telefon):
            return {"status": "abgelehnt", "name": name or firma}
        vorhanden = _vorhandener(db, name, email, firma, telefon)
        if vorhanden:
            kid = vorhanden.get("id") or ""
            if vorschlag:
                # Ein Vorschlag verknuepft nichts — erst die Bestaetigung
                # macht aus ihm einen Kontakt dieser Bewerbung.
                return {"status": "vorhanden", "id": kid[:8],
                        "name": vorhanden.get("full_name") or name}
            _verknuepfen(db, kid, ziel_art, ziel_id, rolle)
            return {"status": "vorhanden", "id": kid[:8],
                    "name": vorhanden.get("full_name") or name}

        kid = db.add_contact({
            # Ohne Namen, aber mit Mail oder Nummer: die Karteikarte
            # traegt die Firma. Sie ist damit auffindbar, und der Name
            # laesst sich nachtragen — geraten wird er nicht.
            "full_name": name or (f"Ansprechpartner {firma}" if firma
                                  else "Ansprechpartner (unbekannt)"),
            "email": email,
            "phone": telefon,
            "company": firma,
            "tags": list(tags or []),
            **(zusatz or {}),
        })
        _verknuepfen(db, kid, ziel_art, ziel_id, rolle)
        return {"status": "angelegt", "id": kid[:8], "name": name or firma}
    except Exception as e:  # pragma: no cover — kippt nie den Vorgang
        return {"status": "fehler", "fehler": str(e)}


def _verknuepfen(db, kontakt_id: str, ziel_art: str, ziel_id: str,
                 rolle: str) -> None:
    """Haengt den Kontakt an sein Ziel — sofern eines genannt ist.

    Ein Kontakt OHNE Ziel ist ausdruecklich erlaubt: eine eingehende
    Anfrage ohne Stellenbezug soll erfassbar sein, ohne dass dafuer ein
    Stellen-Datensatz erfunden wird (#1011). Ein Platzhalter mit
    unbekannter Firma wuerde die Auswertung verfaelschen.
    """
    if not (kontakt_id and ziel_art and ziel_id):
        return
    try:
        db.link_contact(kontakt_id, ziel_art, ziel_id, role=rolle)
    except Exception:
        pass
