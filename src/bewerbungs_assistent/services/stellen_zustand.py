"""Was aus einer vorhandenen Stelle geworden ist — fuer Duplikat-Meldungen (#1046).

Bis v1.7.110 meldete die Uebernahme einer Stelle, die es schon gab, nur

    "Diese Stelle existiert bereits (Hash: ...)."

Fuer den Menschen sind das aber drei verschiedene Lagen:

* **aktiv** — die Stelle liegt in der Trefferliste und wartet auf eine
  Entscheidung. Die Meldung ist ein Hinweis.
* **aussortiert** — das fruehere Urteil greift, zu tun ist nichts. Die
  Meldung ist eine Bestaetigung.
* **beworben** — die Meldung ist ein Warnsignal gegen eine
  Doppelbewerbung.

Im belegten Lauf kamen zwei von sieben Stellen mit "existiert bereits"
zurueck, und daraufhin wurde vorgeschlagen, sie auszusortieren. Beide
waren laengst aussortiert. Die Auskunft, die das verhindert haette, lag in
der Datenbank direkt neben der Kennung.

Ein Ort fuer die Einordnung, damit `stelle_manuell_anlegen` und
`linkedin_treffer_uebernehmen` dasselbe sagen — die Abgrenzung zu
`stellen_dublette.py`: dort wird ERKANNT, ob zwei Eintraege dieselbe
Stelle sind; hier wird BESCHRIEBEN, in welchem Zustand die vorhandene ist.
"""
from __future__ import annotations

AKTIV = "aktiv"
AUSSORTIERT = "aussortiert"
BEWORBEN = "beworben"
ZUSTAENDE = (AKTIV, AUSSORTIERT, BEWORBEN)


def zustand(db, job: dict) -> dict:
    """Der Zustandsblock einer gespeicherten Stelle.

    Eine Bewerbung schlaegt alles andere: auch eine aussortierte Stelle,
    auf die schon beworben wurde, soll vor einer zweiten Bewerbung warnen.
    """
    kennung = job.get("hash") or ""
    block = {
        "hash": db._public_job_hash(kennung) or kennung,
        "titel": job.get("title") or "",
        "firma": job.get("company") or "",
    }
    try:
        bewerbungen = db.get_applications_for_job(kennung) or []
    except Exception:  # pragma: no cover — die Einordnung darf nie scheitern
        bewerbungen = []
    if bewerbungen:
        block.update(aus_bewerbung(bewerbungen[0]))
        block["bewerbungen"] = len(bewerbungen)
        return block

    if not job.get("is_active", 1):
        gruende = job.get("dismiss_reasons") or (
            [job["dismiss_reason"]] if job.get("dismiss_reason") else [])
        block["zustand"] = AUSSORTIERT
        block["aussortier_gruende"] = [str(g) for g in gruende]
        if job.get("dismissed_at"):
            block["aussortiert_am"] = str(job["dismissed_at"])
        if job.get("dismiss_note"):
            block["aussortier_notiz"] = str(job["dismiss_note"])
        return block

    block["zustand"] = AKTIV
    if job.get("score") is not None:
        block["score"] = job.get("score")
    return block


def aus_bewerbung(bewerbung: dict) -> dict:
    """Der Beworben-Teil, auch fuer einen Treffer ohne gespeicherte Stelle."""
    return {
        "zustand": BEWORBEN,
        "bewerbung_id": (bewerbung.get("id") or "")[:8],
        "bewerbungsstatus": bewerbung.get("status") or "",
    }


def schluessel(block: dict) -> str:
    """Der Name im Trichter: `duplikat_aktiv`, `_aussortiert`, `_beworben`."""
    return f"duplikat_{block.get('zustand') or AKTIV}"


def nachricht(block: dict) -> str:
    """Grund UND naechster Schritt (#927) — je Zustand ein anderer."""
    kennung = block.get("hash") or ""
    zustand_ = block.get("zustand")
    if zustand_ == BEWORBEN:
        return (
            f"Auf diese Stelle gibt es bereits eine Bewerbung "
            f"({block.get('bewerbung_id')}, Status: "
            f"{block.get('bewerbungsstatus') or 'unbekannt'}). Keine zweite "
            f"Bewerbung anlegen — der Stand steht in "
            f"bewerbung_details('{block.get('bewerbung_id')}').")
    if zustand_ == AUSSORTIERT:
        gruende = ", ".join(block.get("aussortier_gruende") or []) or "ohne Grund"
        am = (block.get("aussortiert_am") or "")[:10]
        return (
            f"Diese Stelle ist bereits aussortiert (Grund: {gruende}"
            + (f", am {am}" if am else "") + "). Das fruehere Urteil greift, "
            "zu tun ist nichts. Soll sie zurueck in die Liste: "
            f"stelle_reaktivieren('{kennung}').")
    return (
        "Diese Stelle liegt bereits aktiv in der Trefferliste und wartet auf "
        f"eine Entscheidung: stelle_bewerten('{kennung}', ...).")
