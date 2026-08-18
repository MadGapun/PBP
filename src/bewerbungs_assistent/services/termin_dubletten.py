"""Dubletten-Erkennung fuer Termine (#804/D30, v1.7.11).

Termine entstanden urspruenglich nur von Hand — inzwischen kommen sie aus
Mail-Import, ICS, Claude und der Oberflaeche gleichzeitig. Ohne Pruefung
liegt derselbe Termin doppelt im Kalender, und jede Auswertung, die
Termine zaehlt (Aufwand, Interview-Runden, Statistik), zaehlt ihn zweimal.

Belegter Fall: zwei Eintraege fuer denselben Slot, die sich sogar
ergaenzten — einer trug den Teams-Link, der andere den Gespraechskontext.
Keiner allein war vollstaendig. Genau dafuer gibt es hier das
Zusammenfuehren: leere Felder werden gefuellt, gefuellte NIE ueberschrieben.

Bewusst kein stilles Verwerfen: Doppeltermine am selben Tag zu
verschiedenen Uhrzeiten sind legitim (Erst- und Zweitgespraech), deshalb
ein enges Zeitfenster und die Moeglichkeit, bewusst zu uebersteuern.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

# Toleranz um den Startzeitpunkt. Eng genug, dass zwei echte Termine am
# selben Tag nicht kollidieren; weit genug fuer Rundungen und
# Zeitangaben aus verschiedenen Quellen ("16:00" vs "16:00:00").
TOLERANZ_MINUTEN = 30

# Ein abgesagter Termin blockiert keinen neuen — dann wird ja gerade
# umgeplant.
IGNORIERTE_STATUS = {"abgesagt"}


def _parse(wert: str) -> Optional[datetime]:
    if not wert:
        return None
    s = str(wert).strip().replace(" ", "T")
    for laenge in (19, 16, 13, 10):
        try:
            return datetime.fromisoformat(s[:laenge])
        except (ValueError, TypeError):
            continue
    return None


def finde_dublette(db: Any, bewerbung_id: str, datum: str,
                   ausser_id: str = "") -> Optional[dict]:
    """Bestehender, nicht abgesagter Termin derselben Bewerbung im Fenster."""
    neu = _parse(datum)
    if not neu:
        return None
    try:
        kandidaten = db.get_meetings_for_application(bewerbung_id)
    except Exception:
        return None
    fenster = timedelta(minutes=TOLERANZ_MINUTEN)
    for m in kandidaten or []:
        if ausser_id and str(m.get("id")) == str(ausser_id):
            continue
        if (m.get("status") or "").lower() in IGNORIERTE_STATUS:
            continue
        alt = _parse(m.get("meeting_date") or "")
        if alt and abs(alt - neu) <= fenster:
            return dict(m)
    return None


# Felder, die beim Zusammenfuehren uebernommen werden duerfen — und nur,
# wenn sie beim bestehenden Termin leer sind.
_MERGE_FELDER = ("title", "meeting_type", "platform", "location", "notes",
                 "duration_minutes", "meeting_url", "status")


def _ist_leer(wert: Any) -> bool:
    if wert is None:
        return True
    if isinstance(wert, str):
        return not wert.strip()
    if isinstance(wert, (int, float)):
        return wert == 0
    return False


# Textfelder, deren ABWEICHENDER Duplikat-Wert beim Merge erhalten wird
# statt verworfen (#916/#830-Nachfolger, v1.7.17). Belegter Fall: der
# Duplikat-Titel trug die einzigen Namen der Gespraechspartner
# ("Erstgespraech mit <PERSON>") — der Master hatte nur "Kennenlernen".
# Ein stiller Datenverlust in einer "Bereinigung" ist schlechter als
# keine Bereinigung.
_TEXT_ERHALT_FELDER = ("title", "notes", "location", "platform")

_FELD_LABEL = {"title": "Alternative Bezeichnung",
               "notes": "Abweichende Notiz",
               "location": "Abweichender Ort",
               "platform": "Abweichende Plattform"}


def abweichende_texte(bestehend: dict, neu: dict) -> list:
    """(feld, wert)-Paare, deren Duplikat-Text beim Merge verloren ginge."""
    out = []
    for feld in _TEXT_ERHALT_FELDER:
        alt, nw = bestehend.get(feld), neu.get(feld)
        if _ist_leer(nw) or _ist_leer(alt):
            continue
        if str(alt).strip() != str(nw).strip():
            out.append((feld, str(nw).strip()))
    return out


def zusammenfuehren(db: Any, bestehend: dict, neu: dict) -> dict:
    """Fuellt LEERE Felder des bestehenden Termins. Gefuellte bleiben —
    und ABWEICHENDE Texte des Duplikats werden an die Notizen angehaengt
    statt verworfen (v1.7.17, #916).

    Rueckgabe: {"ergaenzt": [...], "behalten": [...],
    "texte_uebernommen": [...]}. Das Datum wird nie ueberschrieben.
    """
    updates: dict = {}
    ergaenzt: list = []
    behalten: list = []
    for feld in _MERGE_FELDER:
        neuer_wert = neu.get(feld)
        if _ist_leer(neuer_wert):
            continue
        if _ist_leer(bestehend.get(feld)):
            updates[feld] = neuer_wert
            ergaenzt.append(feld)
        elif str(bestehend.get(feld)) != str(neuer_wert):
            behalten.append(feld)
    # #916: kein Text geht verloren — Abweichungen wandern in die Notizen.
    texte = [(f, w) for f, w in abweichende_texte(bestehend, neu)
             if f != "notes" or "notes" not in ergaenzt]
    texte_uebernommen = []
    if texte:
        basis = updates.get("notes", bestehend.get("notes") or "")
        anhang = "\n\n".join(
            f"{_FELD_LABEL.get(f, f)}: {w}" for f, w in texte)
        updates["notes"] = (str(basis).rstrip() + "\n\n" + anhang).strip()
        texte_uebernommen = [f for f, _ in texte]
    if updates:
        try:
            db.update_meeting(bestehend.get("id"), updates)
        except Exception as e:  # nicht schweigen, aber auch nicht kippen
            return {"ergaenzt": [], "behalten": behalten,
                    "texte_uebernommen": [],
                    "fehler": f"Update fehlgeschlagen: {e}"}
    return {"ergaenzt": ergaenzt, "behalten": behalten,
            "texte_uebernommen": texte_uebernommen}


def finde_alle_dubletten(db: Any) -> list:
    """Bestands-Report: alle Termin-Paare im selben Zeitfenster.

    Fuer das Aufraeumen bereits entstandener Dubletten — sonst muesste man
    sie im Kalender von Hand suchen.
    """
    conn = db.connect()
    pid = db.get_active_profile_id()
    rows = conn.execute(
        "SELECT m.*, a.company AS firma, a.title AS bewerbung_titel "
        "FROM application_meetings m "
        "LEFT JOIN applications a ON a.id = m.application_id "
        "WHERE (a.profile_id=? OR a.profile_id IS NULL) "
        "ORDER BY m.application_id, m.meeting_date", (pid,)
    ).fetchall()
    fenster = timedelta(minutes=TOLERANZ_MINUTEN)
    paare = []
    nach_app: dict = {}
    for r in rows:
        nach_app.setdefault(r["application_id"], []).append(dict(r))
    for app_id, termine in nach_app.items():
        for i, a in enumerate(termine):
            if (a.get("status") or "").lower() in IGNORIERTE_STATUS:
                continue
            da = _parse(a.get("meeting_date") or "")
            if not da:
                continue
            for b in termine[i + 1:]:
                if (b.get("status") or "").lower() in IGNORIERTE_STATUS:
                    continue
                dbt = _parse(b.get("meeting_date") or "")
                if dbt and abs(dbt - da) <= fenster:
                    # v1.7.17 (#916): Master-Wahl nach INFORMATIONSGEHALT,
                    # nicht nach Anzahl gefuellter Felder. Belegter Fall:
                    # der "inhaltsreichere" Master war der mit generischem
                    # Titel — das Duplikat trug die Personennamen.
                    def _gehalt(m):
                        text_laenge = sum(
                            len(str(m.get(f) or ""))
                            for f in _TEXT_ERHALT_FELDER)
                        felder = sum(1 for f in _MERGE_FELDER
                                     if not _ist_leer(m.get(f)))
                        # Eigennamen-Signal: grossgeschriebene Wortpaare
                        # im Titel ("mit Vorname Nachname")
                        import re as _re
                        namen = len(_re.findall(
                            r"\b[A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+\b",
                            str(m.get("title") or "")))
                        return text_laenge + felder * 10 + namen * 50
                    ga, gb = _gehalt(a), _gehalt(b)
                    if ga != gb:
                        master, dublette = (a, b) if ga > gb else (b, a)
                    else:
                        # Gleichstand: der aeltere Datensatz gewinnt
                        master, dublette = ((a, b)
                                            if str(a.get("created_at") or "")
                                            <= str(b.get("created_at") or "")
                                            else (b, a))
                    verlust = [f for f, _ in abweichende_texte(
                        master, dublette)]
                    paare.append({
                        "bewerbung_id": app_id,
                        "firma": a.get("firma", ""),
                        "zeitpunkt": a.get("meeting_date"),
                        "master_id": master.get("id"),
                        "master_titel": master.get("title"),
                        "duplikat_id": dublette.get("id"),
                        "duplikat_titel": dublette.get("title"),
                        "ergaenzen_sich": bool(
                            [f for f in _MERGE_FELDER
                             if _ist_leer(master.get(f))
                             and not _ist_leer(dublette.get(f))]),
                        # #916: was OHNE die Text-Uebernahme verloren
                        # ginge — der Nutzer sieht die Entscheidung, ohne
                        # die DB zu oeffnen. (Die Uebernahme laeuft beim
                        # Merge automatisch; die Liste dokumentiert sie.)
                        "verlust_ohne_uebernahme": verlust,
                    })
    return paare


# =====================================================================
# v1.7.17 (#922): Phantom-Termine aus zitierten Mail-Threads finden
# =====================================================================
# Belegter Fall: der Import EINER Mail legte vier Termine an — die
# Sendezeiten der zitierten Vorgaengermails. Sie sind formal KEINE
# Dubletten (die Zeitpunkte liegen weit auseinander), sondern schlicht
# keine Termine. Die #804-Pruefung greift hier nicht.
#
# Merkmale eines solchen Phantoms, alle zusammen:
#   - Titel beginnt mit einem Mail-Betreff-Praefix (AW:, Re:, WG:, Fwd:)
#   - kein Konferenzlink, keine Notizen, kein Ort
#   - mehrere Termine derselben Bewerbung mit demselben Titel, im selben
#     Importvorgang angelegt (created_at)
#
# Bewusst NUR ein Vorschlag: geloescht wird erst nach Bestaetigung.

_BETREFF_PREFIX = ("aw:", "re:", "wg:", "fwd:", "fw:", "antw:")


def _ist_betreff_titel(titel: str) -> bool:
    t = (titel or "").strip().lower()
    return any(t.startswith(p) for p in _BETREFF_PREFIX)


def finde_phantom_termine(db: Any) -> list:
    """Termine, die aus zitierten Mail-Zeitstempeln entstanden sind (#922).

    Liefert Gruppen (je Bewerbung + Titel) mit Begruendung. Ein einzelner
    Termin mit Betreff-Titel ist NICHT verdaechtig — erst mehrere gleich
    betitelte, belegfreie Eintraege aus demselben Import.
    """
    conn = db.connect()
    pid = db.get_active_profile_id()
    rows = conn.execute(
        "SELECT m.*, a.company AS firma FROM application_meetings m "
        "LEFT JOIN applications a ON a.id = m.application_id "
        "WHERE (a.profile_id=? OR a.profile_id IS NULL) "
        "ORDER BY m.application_id, m.title, m.meeting_date", (pid,)
    ).fetchall()

    gruppen: dict = {}
    for r in rows:
        d = dict(r)
        if not _ist_betreff_titel(d.get("title")):
            continue
        # Beleg vorhanden? Dann ist es ein echter Termin.
        if any(not _ist_leer(d.get(f))
               for f in ("meeting_url", "notes", "location", "platform")):
            continue
        schluessel = (d.get("application_id"), (d.get("title") or "").strip())
        gruppen.setdefault(schluessel, []).append(d)

    treffer = []
    for (app_id, titel), eintraege in gruppen.items():
        if len(eintraege) < 2:
            continue
        # Selber Importvorgang? (created_at auf die Minute genau)
        stempel = {str(e.get("created_at") or "")[:16] for e in eintraege}
        treffer.append({
            "bewerbung_id": app_id,
            "firma": eintraege[0].get("firma", ""),
            "titel": titel,
            "anzahl": len(eintraege),
            "termin_ids": [e.get("id") for e in eintraege],
            "zeitpunkte": [e.get("meeting_date") for e in eintraege],
            "aus_einem_import": len(stempel) == 1,
            "begruendung": (
                f"{len(eintraege)} Termine mit identischem Mail-Betreff als "
                "Titel, ohne Link, Notizen oder Ort"
                + (" — alle im selben Importvorgang angelegt"
                   if len(stempel) == 1 else "")
                + ". Typisches Muster fuer Sendezeiten aus einem zitierten "
                  "Mail-Thread (#922)."
            ),
        })
    return treffer
