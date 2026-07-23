"""Anker-Pflicht fuer Stellen (#766, v1.7.9).

Hintergrund (Praxis-Fall 23.07.2026): Von acht aktiven Stellen im Bestand
hatte KEINE einen fuer den Nutzer nachvollziehbaren Weg zur Original-
Ausschreibung — teils leere URL, teils nur eine zusammenfassende
Claude-Notiz als `description`. Solche Stellen sind wertlos: man kann sich
nicht bewerben, den Text nicht nachladen und den Score nicht belastbar
machen.

Eine Stelle gilt als **verfolgbar**, wenn sie mindestens einen dieser drei
Anker hat:

1. ``url_detail``  — direkte URL zur Anzeige (Idealfall)
2. ``dokument``    — ein Dokument mit der Anzeige (PDF/Screenshot/Mail),
                     erreichbar ueber eine Bewerbung zu dieser Stelle
3. ``kontakt``     — Ansprechpartner (``contact_links`` mit
                     ``target_kind='job'``)

Eine reine SUCH-URL ist bewusst KEIN vollwertiger Anker: sie fuehrt auf
eine Ergebnisliste, nicht auf die Anzeige, und `stellenbeschreibung_
nachladen` kann daraus nichts holen. Sie wird als ``url_suche`` separat
ausgewiesen, damit der Unterschied sichtbar bleibt statt zu verschwimmen.

Ebenfalls bewusst KEIN Anker: eine lange `description`. Genau der Fall aus
dem Issue — eine Claude-Zusammenfassung liest sich wie eine Anzeige, ist
aber keine, und gegen sie optimierte Unterlagen gehen an den echten
Anforderungen vorbei.
"""
from __future__ import annotations

from typing import Any, Optional

ANKER_LABELS = {
    "url_detail": "Direkte URL zur Stellenanzeige",
    "dokument": "Verknuepftes Dokument mit der Anzeige",
    "kontakt": "Ansprechpartner hinterlegt",
}

WARNTEXT = (
    "Diese Stelle hat KEINEN Anker (#766): weder eine direkte URL zur "
    "Anzeige, noch ein Dokument mit der Ausschreibung, noch einen "
    "Ansprechpartner. Damit ist sie nicht verfolgbar — eine Bewerbung "
    "waere nur gegen eine Zusammenfassung formuliert, nicht gegen die "
    "echte Ausschreibung. Bitte mindestens eines nachreichen: "
    "stelle_bearbeiten(url=...) fuer die Detail-URL, "
    "kontakt_anlegen() + kontakt_verknuepfen(ziel_typ='job') fuer den "
    "Ansprechpartner, oder die Anzeige als Dokument hochladen."
)


def _hat_job_kontakt(db: Any, job_hash: str) -> bool:
    """Kontakt-Anker: contact_links mit target_kind='job'.

    Bewusst tolerant gegenueber Kurz-Hashes — `link_contact` loest sie beim
    Anlegen auf, im Bestand koennen aber beide Formen liegen.
    """
    if not job_hash:
        return False
    try:
        kandidaten = {job_hash}
        voll = db.resolve_job_hash(job_hash)
        if voll:
            kandidaten.add(voll)
        for h in kandidaten:
            if db.get_contacts_for_target("job", h):
                return True
    except Exception:
        return False
    return False


def _hat_dokument(db: Any, job_hash: str) -> bool:
    """Dokument-Anker: Dokumente haengen an Bewerbungen, nicht an Stellen.

    Der Weg ist also Dokument -> Bewerbung -> Stelle. Fuer eine frisch
    angelegte Stelle ohne Bewerbung ist dieser Anker naturgemaess nie
    erfuellt; er greift, wenn die Anzeige spaeter als PDF/Mail zur
    Bewerbung abgelegt wurde.
    """
    if not job_hash:
        return False
    try:
        voll = db.resolve_job_hash(job_hash) or job_hash
        conn = db.connect()
        row = conn.execute(
            "SELECT 1 FROM documents d "
            "WHERE d.linked_application_id IN ("
            "  SELECT application_id FROM application_jobs WHERE job_hash=?"
            "  UNION SELECT id FROM applications WHERE job_hash=?"
            ") AND COALESCE(d.lifecycle,'aktiv') != 'archiviert' LIMIT 1",
            (voll, voll),
        ).fetchone()
        return row is not None
    except Exception:
        return False


def anker_status(db: Any, job: dict, pruefe_db: bool = True) -> dict:
    """Bewertet die Verfolgbarkeit einer Stelle (#766).

    Args:
        db: Database-Instanz.
        job: Stellen-Dict (mindestens ``url``; ``hash`` fuer die DB-Anker).
        pruefe_db: False = nur die URL bewerten (fuer Listen-Aufrufe, die
            sonst pro Zeile zwei Queries absetzen wuerden).

    Returns:
        dict mit ``hat_anker`` (bool), ``anker`` (Liste der erfuellten),
        ``url_art`` ('detail' | 'suche' | 'keine') und — nur wenn kein
        Anker vorliegt — ``warnung``.
    """
    from ..job_scraper import is_search_result_url

    url = (job.get("url") or "").strip()
    job_hash = job.get("hash") or ""

    if not url:
        url_art = "keine"
    elif job.get("is_search_url") or is_search_result_url(url):
        url_art = "suche"
    else:
        url_art = "detail"

    anker: list[str] = []
    if url_art == "detail":
        anker.append("url_detail")
    if pruefe_db and job_hash:
        if _hat_dokument(db, job_hash):
            anker.append("dokument")
        if _hat_job_kontakt(db, job_hash):
            anker.append("kontakt")

    ergebnis = {
        "hat_anker": bool(anker),
        "anker": anker,
        "url_art": url_art,
    }
    if not anker:
        ergebnis["warnung"] = WARNTEXT
        ergebnis["fehlend"] = list(ANKER_LABELS.values())
        if url_art == "suche":
            ergebnis["hinweis_such_url"] = (
                "Die hinterlegte URL ist eine Suchergebnis-Seite, keine "
                "Anzeige — sie zaehlt nicht als Anker und das Nachladen der "
                "Beschreibung ist damit blockiert."
            )
    return ergebnis


def anker_kurz(db: Any, job: dict, pruefe_db: bool = True) -> Optional[str]:
    """Kurzkennzeichnung fuer Listen: None = alles gut, sonst ein Label."""
    st = anker_status(db, job, pruefe_db=pruefe_db)
    if st["hat_anker"]:
        return None
    return "ohne_anker_such_url" if st["url_art"] == "suche" else "ohne_anker"
