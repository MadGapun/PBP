"""Was mit einer Bewerbung passiert, wenn sie entsteht oder ihren Status
wechselt — an EINER Stelle (#1094).

Die Regeln standen in den MCP-Werkzeugen `bewerbung_erstellen` und
`bewerbung_status_aendern`. Das Dashboard rief nur die Datenbank auf und
bekam deshalb kein Bewerbungsdatum, keine Nachfass-Erinnerung, keine
aussortierte Stelle und keine Dublettenpruefung — obwohl es der Weg ist,
den der Mensch im Alltag nimmt. Dieselbe Klasse wie #963 und #991.

Bewusst NICHT in `database.update_application_status`: den rufen auch
Import und Migration auf, und dort waeren eine neue Erinnerung oder eine
aussortierte Stelle falsch.

`status_wechseln` liefert neben dem Ergebnis alles, was ein Rueckweg
braucht (G67): vorheriger Status, neues Ereignis, geschlossene und
angelegte Nachfassungen, das vorherige Bewerbungsdatum, die aussortierte
Stelle und die veralteten Dokumente mit ihrem alten Zustand.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta

from . import bewerbung_status as _bs

logger = logging.getLogger(__name__)

#: Status, die eine erfolgte Bewerbung voraussetzen (#779). Wird einer
#: davon erreicht, ohne dass "beworben" je gesetzt war, fehlt sonst das
#: Datum, und die Bewerbung faellt aus Statistik und Reaktionszeiten.
SETZT_BEWERBUNG_VORAUS = frozenset({
    "eingangsbestaetigung", "interview", "zweitgespraech",
    "interview_abgeschlossen", "angebot", "angenommen",
    "abgelehnt", "arbeitgeber_ausgefallen",
})

#: Frueher genutzte Status und ihr heutiger Name.
ALTE_STATUS = {
    "warte_auf_rueckmeldung": "eingangsbestaetigung",
    "abgesagt": "abgelaufen",
}

_ELWOSA = {
    "abgelehnt": "absage",
    "eingangsbestaetigung": "eingangsbestaetigung",
    "interview": "interview_einladung",
    "zweitgespraech": "interview_einladung",
    "angenommen": "angenommen",
    "zurueckgezogen": "zurueckgezogen",
    "abgelaufen": "abgelaufen",
}


def status_pruefen(status: str) -> dict | None:
    """None, wenn der Status gilt — sonst die Absage mit Vorschlag."""
    if status in _bs.ALLE:
        return None
    if status in ALTE_STATUS:
        return {
            "fehler": (f"Status '{status}' gibt es nicht mehr. "
                       f"Nutze stattdessen '{ALTE_STATUS[status]}'."),
            "vorschlag_status": ALTE_STATUS[status],
        }
    return {"fehler": (f"Unbekannter Status '{status}'. "
                       f"Erlaubt sind: {', '.join(sorted(_bs.ALLE))}")}


def _offene(db, app_id: str) -> set[str]:
    return {fu["id"] for fu in db.get_pending_follow_ups()
            if fu.get("application_id") == app_id}


def _nachfass_tage(db) -> int:
    try:
        return int(db.get_setting_zahl("followup_default_days", 7))
    except Exception:
        return 7


def _erinnerung_anlegen(db, app_id: str) -> tuple[str | None, int]:
    """Legt die Nachfass-Erinnerung an, wenn keine offen ist (#462, #816)."""
    tage = _nachfass_tage(db)
    if tage <= 0 or _offene(db, app_id):
        return None, tage
    from .nachfass_text import nachfass_text
    wann = (datetime.now() + timedelta(days=tage)).date().isoformat()
    fid = db.add_follow_up(app_id, wann, "nachfass",
                           template=nachfass_text(db.get_application(app_id) or {}))
    return fid, tage


def _stelle_aussortieren(db, job_hash: str) -> str | None:
    """Sortiert die Stelle aus, wenn sie noch aktiv ist (#405, #231).

    Nur eine AKTIVE Stelle: eine laengst aussortierte behaelt ihren Grund,
    und ein Rueckgaengig holt nur zurueck, was hier weggelegt wurde.
    """
    if not job_hash:
        return None
    try:
        job = db.get_job(job_hash)
        if not job or not job.get("is_active"):
            return None
        db.dismiss_job(job_hash, reason="bewerbung_erstellt", herkunft="automatik")
        return job_hash
    except Exception as exc:  # noqa: BLE001
        logger.debug("Stelle aussortieren (#1094): %s", exc)
        return None


def _elwosa(db, anlass: str, firma: str, ref: str) -> None:
    try:
        from . import elwosa
        elwosa.speak(db, anlass, ctx={"firma": firma, "ref": ref})
    except Exception:
        pass


def status_wechseln(db, app_id: str, neu: str, notizen: str = "",
                    ablehnungsgrund: str = "", auto_follow_up: bool = True,
                    profile_id: str | None = None) -> dict:
    """Wechselt den Status mit allen Folgen. Liefert immer ein dict:
    bei Erfolg `ok=True` und den Befund, sonst `fehler` (und `grund`
    'status' oder 'nicht_gefunden')."""
    # Erst die Bewerbung im aktiven Profil suchen, DANN irgendetwas
    # veraendern: Datum und Stelle werden vor dem eigentlichen Wechsel
    # gesetzt, und eine fremde Bewerbung darf davon nichts abbekommen.
    if profile_id is None:
        profile_id = db.get_active_profile_id()
    app = db.get_application(app_id, profile_id=profile_id)
    if not app:
        return {"ok": False, "grund": "nicht_gefunden",
                "fehler": "Bewerbung nicht gefunden."}
    absage = status_pruefen(neu)
    if absage:
        return {**absage, "ok": False, "grund": "status"}
    vorher = app.get("status") or ""
    applied_vorher = app.get("applied_at") or ""
    offen_vorher = _offene(db, app_id)

    applied_gesetzt = None
    nachgetragen = None
    if neu == "beworben" and not applied_vorher.strip():
        applied_gesetzt = datetime.now().isoformat()[:10]
        db.update_application(app_id, {"applied_at": applied_gesetzt})
    elif neu in SETZT_BEWERBUNG_VORAUS and not applied_vorher.strip():
        # #779: aeltestes Timeline-Ereignis, sonst Anlagedatum
        row = db.connect().execute(
            "SELECT MIN(event_date) AS erster FROM application_events "
            "WHERE application_id=?", (app_id,)).fetchone()
        datum = (row["erster"] or "") if row else ""
        quelle = "ältester Timeline-Eintrag"
        if not datum:
            datum = app.get("created_at") or ""
            quelle = "Anlagedatum (keine Einträge vorhanden)"
        if datum:
            applied_gesetzt = datum[:10]
            db.update_application(app_id, {"applied_at": applied_gesetzt})
            nachgetragen = {"datum": applied_gesetzt, "quelle": quelle}

    stelle = None
    auto_fid, tage = None, _nachfass_tage(db)
    if neu == "beworben":
        stelle = _stelle_aussortieren(db, app.get("job_hash") or "")

    if not db.update_application_status(app_id, neu, notizen, ablehnungsgrund,
                                        profile_id=profile_id):
        return {"ok": False, "grund": "nicht_gefunden",
                "fehler": "Bewerbung nicht gefunden."}
    zeile = db.connect().execute(
        "SELECT MAX(id) AS id FROM application_events "
        "WHERE application_id=? AND status=?", (app_id, neu)).fetchone()

    if neu == "beworben" and auto_follow_up:
        auto_fid, tage = _erinnerung_anlegen(db, app_id)

    # #657: Dokumente einer beendeten Bewerbung aus den Analyse-Ansichten
    veraltet: list[dict] = []
    if neu in _bs.ARCHIV:
        pid = db.get_active_profile_id()
        conn = db.connect()
        for doc_id in db.get_documents_linked_to_application(app_id):
            try:
                alt = conn.execute("SELECT lifecycle FROM documents WHERE id=?",
                                   (doc_id,)).fetchone()
                alt_wert = (alt["lifecycle"] if alt else "") or "aktiv"
                if alt_wert != "veraltet" and db.update_document_lifecycle(
                        doc_id, "veraltet", profile_id=pid):
                    veraltet.append({"id": doc_id, "vorher": alt_wert})
            except Exception as exc:  # noqa: BLE001
                logger.debug("Dokument veralten (#657): %s", exc)

    if neu in _ELWOSA:
        _elwosa(db, _ELWOSA[neu], app.get("company") or "", app_id)

    offen_nachher = _offene(db, app_id)
    return {
        "ok": True,
        "vorher": vorher,
        "neu": neu,
        "event_id": zeile["id"] if zeile else None,
        "geschlossen": sorted(offen_vorher - offen_nachher),
        "angelegt": sorted(offen_nachher - offen_vorher),
        "auto_follow_up_id": auto_fid,
        "nachfass_tage": tage,
        "applied_at_vorher": applied_vorher if applied_gesetzt else None,
        "applied_at_gesetzt": applied_gesetzt,
        "applied_at_nachgetragen": nachgetragen,
        "stelle_aussortiert": stelle,
        "dokumente_veraltet": veraltet,
        "archiviert": neu in _bs.ARCHIV and vorher not in _bs.ARCHIV,
    }


# ── Anlage ───────────────────────────────────────────────────────────

def dublette_finden(db, title: str, company: str, kontakt_email: str = "",
                    ansprechpartner: str = "", endkunde: str = "") -> dict | None:
    """Die vorhandene Bewerbung zur selben Stelle — oder None (#63, #531, #710)."""
    from ..tools.bewerbungen import (
        _normalize_company_for_dedup, _normalize_title_for_dedup,
        _is_company_overlap, _is_vermittler_endkunde_match)
    norm_company = _normalize_company_for_dedup(company)
    norm_title = _normalize_title_for_dedup(title)
    norm_email = (kontakt_email or "").lower().strip()
    norm_ansprech = (ansprechpartner or "").lower().strip()
    norm_endkunde = (endkunde or "").lower().strip()
    for ex in db.get_applications():
        ex_endkunde = (ex.get("endkunde") or "").lower().strip()
        if norm_endkunde and ex_endkunde and norm_endkunde != ex_endkunde:
            continue  # #710: verschiedene Endkunden beim selben Vermittler
        ex_company = ex.get("company", "") or ""
        ex_title = ex.get("title", "") or ""
        basis = {"bestehende_bewerbung_id": ex["id"][:8],
                 "bestehende_bewerbung_id_voll": ex["id"],
                 "bestehend_firma": ex_company, "bestehend_titel": ex_title,
                 "bestehend_status": ex.get("status", "")}
        if ex_company.lower() == company.lower() and ex_title.lower() == title.lower():
            return {**basis, "match_typ": "exakt"}
        ex_nt = _normalize_title_for_dedup(ex_title)
        firma = (_is_company_overlap(norm_company, _normalize_company_for_dedup(ex_company))
                 or _is_vermittler_endkunde_match(company, ex_company))
        titel = (norm_title == ex_nt) or bool(
            norm_title and ex_nt and (norm_title in ex_nt or ex_nt in norm_title))
        if firma and titel:
            return {**basis, "match_typ": "fuzzy_firma_titel"}
        ex_email = (ex.get("kontakt_email") or "").lower().strip()
        ex_ansprech = (ex.get("ansprechpartner") or "").lower().strip()
        if titel and ((norm_email and norm_email == ex_email)
                      or (norm_ansprech and norm_ansprech == ex_ansprech)):
            return {**basis, "match_typ": "email_oder_ansprechpartner"}
    return None


def anlegen(db, daten: dict, force: bool = False) -> dict:
    """Legt eine Bewerbung mit allen Folgen an.

    `daten` traegt die Felder von `bewerbung_erstellen` (title, company,
    url, job_hash, status, applied_at, notes, bewerbungsart,
    lebenslauf_variante, ansprechpartner, kontakt_email, portal_name,
    stellenbeschreibung, endkunde). Liefert `ok=True` mit `id`, oder
    `ok=False` mit `grund` ('pflichtfeld', 'status', 'duplikat')."""
    title = str(daten.get("title") or "").strip()
    company = str(daten.get("company") or "").strip()
    if not title or not company:
        return {"ok": False, "grund": "pflichtfeld",
                "fehler": ("Stelle ist ein Pflichtfeld" if not title
                           else "Firma ist ein Pflichtfeld")}
    status = str(daten.get("status") or "beworben").strip()
    absage = status_pruefen(status)
    if absage:
        return {**absage, "ok": False, "grund": "status"}
    url = str(daten.get("url") or "")
    ansprech = str(daten.get("ansprechpartner") or "")
    email = str(daten.get("kontakt_email") or "")
    endkunde = str(daten.get("endkunde") or "")
    beschreibung = str(daten.get("stellenbeschreibung") or "")
    notes = str(daten.get("notes") or "")

    if not force:
        dub = dublette_finden(db, title, company, email, ansprech, endkunde)
        if dub:
            return {"ok": False, "grund": "duplikat", **dub,
                    "fehler": (f"Es gibt schon eine Bewerbung bei {dub['bestehend_firma']} "
                               f"für „{dub['bestehend_titel']}“.")}

    job_hash = str(daten.get("job_hash") or "") or None
    if not job_hash:
        # Ohne gefundene Stelle entsteht eine manuelle, damit sie in der
        # Stellenliste steht (#588: Notizen sind KEINE Beschreibung).
        job_hash = hashlib.md5(f"manuell:{company}:{title}:{url}".encode()).hexdigest()[:12]
        if not db.get_job(job_hash):
            from .url_to_source import detect_source_from_url
            db.save_jobs([{
                "hash": job_hash, "title": title, "company": company,
                "location": "", "url": url, "source": detect_source_from_url(url),
                "description": beschreibung, "score": 0, "is_pinned": True,
                "remote_level": "unbekannt", "employment_type": "festanstellung",
                "found_at": datetime.now().isoformat(),
            }])
    job = db.get_job(job_hash) or {}
    snapshot = beschreibung or job.get("description") or ""
    applied = str(daten.get("applied_at") or "")
    if status == "in_vorbereitung":
        applied = ""
    elif not applied:
        applied = datetime.now().isoformat()[:10]  # #602

    felder = {k: daten[k] for k in ("bewerbungsart", "lebenslauf_variante",
                                     "portal_name", "cover_letter_path", "cv_path")
              if daten.get(k) not in (None, "")}
    aid = db.add_application({
        **felder,
        "title": title, "company": company, "url": url, "job_hash": job_hash,
        "status": status, "applied_at": applied, "notes": notes,
        "ansprechpartner": ansprech, "kontakt_email": email,
        "source": job.get("source", "") or "",
        "description_snapshot": snapshot,
        "snapshot_date": datetime.now().isoformat() if snapshot else "",
        "endkunde": endkunde,
    })

    kontakt = None
    if ansprech or email:  # #1011: eine Bewerbung ist eine Interaktion
        from . import kontakt_pflicht
        kontakt = kontakt_pflicht.sicherstellen(
            db, name=ansprech, email=email, firma=company,
            ziel_art="application", ziel_id=aid)

    stelle = _stelle_aussortieren(db, job_hash)
    _elwosa(db, "bewerbung_angelegt", company, aid)

    if notes:  # #224: die Notiz als erster Timeline-Eintrag
        conn = db.connect()
        conn.execute("INSERT INTO application_events (application_id, status, "
                     "event_date, notes) VALUES (?, 'notiz', ?, ?)",
                     (aid, datetime.now().isoformat(), notes))
        conn.commit()

    auto_fid, tage = (None, _nachfass_tage(db))
    if status == "beworben" and daten.get("auto_follow_up", True):
        auto_fid, tage = _erinnerung_anlegen(db, aid)

    return {"ok": True, "id": aid, "job_hash": job_hash, "status": status,
            "kontakt": kontakt, "stelle_aussortiert": stelle,
            "auto_follow_up_id": auto_fid, "nachfass_tage": tage}


# ── Nachfassungen ────────────────────────────────────────────────────

def nachfassung_abschliessen(db, follow_up_id: str, status: str,
                             notiz: str = "") -> dict:
    """Schliesst eine GEPLANTE Nachfassung (erledigt/hinfaellig).

    Eine schon abgeschlossene wird abgewiesen: ein Doppelklick schrieb die
    Notiz sonst zweimal, und eine hinfaellige liess sich nachtraeglich auf
    "erledigt" setzen und zaehlte dann in den Reaktionszeiten (#980)."""
    fu = db.get_follow_up(follow_up_id)
    if not fu:
        return {"ok": False, "grund": "nicht_gefunden",
                "fehler": "Nachfassung nicht gefunden."}
    if fu.get("status") != "geplant":
        wort = {"erledigt": "erledigt", "hinfaellig": "hinfällig"}.get(
            fu.get("status"), fu.get("status"))
        return {"ok": False, "grund": "zustand", "bisher": fu.get("status"),
                "fehler": f"Diese Nachfassung ist schon {wort} — es gibt nichts mehr zu tun."}
    db.complete_follow_up(follow_up_id, status=status)
    if notiz and fu.get("application_id"):
        praefix = "Nachfass erledigt" if status == "erledigt" else "Nachfass hinfällig"
        try:
            db.add_application_note(fu["application_id"], f"{praefix}: {notiz}")
        except Exception:
            pass
    return {"ok": True, "status": status}


def nachfassung_aendern(db, follow_up_id: str, felder: dict) -> dict:
    """Aendert Datum, Text oder Art einer GEPLANTEN Nachfassung.

    Ein leerer Text wird abgewiesen — die leere Erinnerung hat #816
    abgeschafft."""
    fu = db.get_follow_up(follow_up_id)
    if not fu:
        return {"ok": False, "grund": "nicht_gefunden",
                "fehler": "Nachfassung nicht gefunden."}
    if fu.get("status") != "geplant":
        return {"ok": False, "grund": "zustand", "bisher": fu.get("status"),
                "fehler": "Eine abgeschlossene Nachfassung lässt sich nicht mehr ändern."}
    erlaubt = {k: v for k, v in (felder or {}).items()
               if k in ("scheduled_date", "template", "follow_up_type") and v is not None}
    if "template" in erlaubt and not str(erlaubt["template"]).strip():
        return {"ok": False, "grund": "leer",
                "fehler": ("Der Text der Erinnerung darf nicht leer sein — "
                           "sonst weißt du beim Fälligwerden nicht mehr, worum es ging.")}
    if not erlaubt:
        return {"ok": False, "grund": "leer", "fehler": "Keine Änderung angegeben."}
    db.update_follow_up(follow_up_id, erlaubt)
    return {"ok": True, "geaendert": sorted(erlaubt)}
