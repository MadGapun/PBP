"""Vollstaendigkeits-Check fuer Interview-Verfahren (#825/D32, v1.7.12).

Ein Verfahren kann formal komplett aussehen und trotzdem die Information
nicht enthalten, die man zur Vorbereitung der naechsten Runde braucht.
Belegter Fall: zwei gefuehrte Interviews, sieben Dokumente — und als
einziger Kontakt der vermittelnde Personalreferent. Die drei Personen,
mit denen tatsaechlich gesprochen wurde, standen nirgends.

Grundsaetze:
- **Kein auto_fix.** Wer im Gespraech war, laesst sich nicht ableiten.
  Der Check meldet, er ergaenzt nichts.
- **Jeder Befund einzeln und DAUERHAFT abweisbar** (profile_settings,
  Onboarding-Hints-Muster). Ein weggeklickter Befund, der wiederkommt,
  wird nach dem dritten Mal ignoriert — und entwertet die berechtigten.
- Deeplinks im pbp://-Schema; klickbar, sobald #815 das Routing bringt,
  bis dahin kopierbare Referenzen.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

from .wiedergaenger import normalize_company

# Rollen/Kategorien, die einen Kontakt als Vermittlerseite ausweisen.
_VERMITTLER_SIGNALE = ("recruiter", "headhunter", "vermittler",
                      "personalberat", "personaldienstleist", "staffing")

# Status, die ein stattgefundenes Gespraech implizieren.
GESPRAECH_STATUS = ("interview", "zweitgespraech", "interview_abgeschlossen",
                    "angebot", "angenommen")

# Status jenseits von "beworben" fuer Pruefung 4.
_JENSEITS_BEWORBEN = GESPRAECH_STATUS + ("zweitgespraech",)

_SETTING_KEY = "diagnose_befunde_abgewiesen"

# Pruefung 5: Gespraechs-Erwaehnung + Datumsangabe im Notizfeld.
_GESPRAECH_RE = re.compile(
    r"(gespr(?:ae|ä)ch|interview|telefonat|kennenlernen|call)",
    re.IGNORECASE)
_DATUM_RE = re.compile(
    r"\b(\d{1,2}\.\d{1,2}\.(?:\d{2,4})?|\d{4}-\d{2}-\d{2})\b")


def _abgewiesen(db) -> set:
    try:
        roh = db.get_profile_setting(_SETTING_KEY, "[]") or "[]"
        return set(json.loads(roh))
    except Exception:
        return set()


def befund_abweisen(db, befund_id: str) -> bool:
    """Merkt einen Befund dauerhaft als abgewiesen."""
    ids = _abgewiesen(db)
    if befund_id in ids:
        return False
    ids.add(befund_id)
    db.set_profile_setting(_SETTING_KEY, json.dumps(sorted(ids)))
    return True


def _ist_vermittler(kontakt: dict) -> bool:
    # Kontakte tragen die Rolle je Kontext im Link (link_role, #563);
    # dazu Position, Tags und Firma des Kontakts selbst.
    teile = [str(kontakt.get(f) or "") for f in
             ("link_role", "position", "company", "notes")]
    tags = kontakt.get("tags") or []
    if isinstance(tags, list):
        teile.extend(str(t) for t in tags)
    text = " ".join(teile).lower()
    return any(s in text for s in _VERMITTLER_SIGNALE)


def _gleiche_firma(kontakt: dict, bewerbungs_firma: str) -> bool:
    return (normalize_company(kontakt.get("company"))
            == normalize_company(bewerbungs_firma)
            and bool(normalize_company(bewerbungs_firma)))


def pruefe_interview_vollstaendigkeit(db) -> list[dict]:
    """Alle fuenf Pruefungen; liefert nur nicht-abgewiesene Befunde."""
    befunde: list[dict] = []
    abgewiesen = _abgewiesen(db)
    heute = datetime.now().date()

    apps = [a for a in db.get_applications()
            if a.get("status") in _JENSEITS_BEWORBEN]

    for app in apps:
        aid = app.get("id")
        firma = app.get("company") or ""
        kontakte = db.get_contacts_for_target("application", aid) or []
        deeplink = f"pbp://bewerbung/{aid}"

        # --- Pruefung 4: gar kein Kontakt jenseits von 'beworben' ---
        if not kontakte:
            bid = f"kein_kontakt:{aid}"
            if bid not in abgewiesen:
                befunde.append({
                    "id": bid, "art": "kein_kontakt",
                    "bewerbung_id": aid, "firma": firma,
                    "befund": (f"Verfahren im Status '{app.get('status')}' "
                               "ohne einen einzigen verknuepften Kontakt."),
                    "deeplink": deeplink,
                })
        else:
            # --- Pruefung 1: nur Vermittler, niemand vom Endkunden ---
            # Guard: Direktbewerbung mit Kontakt in der Bewerbungsfirma
            # ist ausdruecklich KEIN Befund.
            endkunde = [k for k in kontakte
                        if _gleiche_firma(k, firma)
                        and not _ist_vermittler(k)]
            nur_vermittler = not endkunde and all(
                _ist_vermittler(k) or not _gleiche_firma(k, firma)
                for k in kontakte)
            if (app.get("status") in GESPRAECH_STATUS and nur_vermittler):
                bid = f"nur_vermittler:{aid}"
                if bid not in abgewiesen:
                    befunde.append({
                        "id": bid, "art": "nur_vermittler",
                        "bewerbung_id": aid, "firma": firma,
                        "befund": (
                            "Verfahren mit Interview, aber kein "
                            "Ansprechpartner beim Endkunden erfasst — alle "
                            f"{len(kontakte)} Kontakte sind Vermittler oder "
                            "fremde Firmen. Fuer die naechste Runde fehlt, "
                            "wer im Gespraech war."),
                        "deeplink": deeplink,
                    })

        # --- Pruefungen 2+3: vergangene Interview-Termine ---
        meetings = db.get_meetings_for_application(aid) or []
        reflexionen = db.get_interview_reflections(aid)
        reflektierte_meetings = {str(r.get("meeting_id") or "")
                                 for r in reflexionen}
        for m in meetings:
            m_typ = (m.get("meeting_type") or m.get("category")
                     or m.get("title") or "").lower()
            if "interview" not in m_typ and "gespraech" not in m_typ \
                    and "gespräch" not in m_typ:
                continue
            if (m.get("status") or "").lower() in ("abgesagt", "cancelled"):
                continue
            datum_roh = (m.get("meeting_date") or "")[:10]
            try:
                m_datum = datetime.fromisoformat(datum_roh).date()
            except ValueError:
                continue
            # Karenz: erst ab dem Folgetag melden — nicht schon waehrend
            # des Gespraechs.
            if m_datum >= heute:
                continue
            mid = str(m.get("id"))

            teilnehmer = db.get_contacts_for_target("meeting", mid) or []
            if not teilnehmer:
                bid = f"termin_ohne_teilnehmer:{mid}"
                if bid not in abgewiesen:
                    befunde.append({
                        "id": bid, "art": "termin_ohne_teilnehmer",
                        "bewerbung_id": aid, "firma": firma,
                        "termin_id": mid, "termin_datum": datum_roh,
                        "befund": (
                            f"Interview am {datum_roh} ohne erfasste "
                            "Teilnehmer. Wer sich auf die naechste Runde "
                            "vorbereitet, findet nicht, wer dabei war — "
                            "kontakt_verknuepfen(ziel_typ='meeting') "
                            "traegt nach, auch 'Name unbekannt' zaehlt."),
                        "deeplink": f"pbp://termin/{mid}",
                    })

            hat_reflexion = mid in reflektierte_meetings or any(
                not (r.get("meeting_id") or "")
                and (r.get("created_at") or "") >= datum_roh
                for r in reflexionen)
            if not hat_reflexion \
                    and m_datum >= heute - timedelta(days=30):
                bid = f"termin_ohne_reflexion:{mid}"
                if bid not in abgewiesen:
                    befunde.append({
                        "id": bid, "art": "termin_ohne_reflexion",
                        "bewerbung_id": aid, "firma": firma,
                        "termin_id": mid, "termin_datum": datum_roh,
                        "befund": (
                            f"Interview am {datum_roh} ohne Nachbereitung. "
                            "Zwei Saetze direkt danach sind mehr wert als "
                            "ein perfekter Bericht spaeter — "
                            "interview_reflexion_speichern oder das "
                            "Formular in der Bewerbungs-Timeline."),
                        "deeplink": deeplink,
                    })

        # --- Pruefung 5 (#781/6): Gespraech nur in Notizen belegt ---
        notizen = app.get("notes") or ""
        if notizen and not meetings:
            if _GESPRAECH_RE.search(notizen) and _DATUM_RE.search(notizen):
                bid = f"gespraech_nur_notiz:{aid}"
                if bid not in abgewiesen:
                    befunde.append({
                        "id": bid, "art": "gespraech_nur_notiz",
                        "bewerbung_id": aid, "firma": firma,
                        "befund": (
                            "Die Notizen erwaehnen ein Gespraech mit Datum, "
                            "aber es existiert kein Termin-Eintrag dazu — "
                            "Prozessdauer- und Kanal-Auswertung (#781) "
                            "sehen dieses Gespraech nicht. "
                            "meeting_hinzufuegen traegt es nach."),
                        "deeplink": deeplink,
                    })

    return befunde
