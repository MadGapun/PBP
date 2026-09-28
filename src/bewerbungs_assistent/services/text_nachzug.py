"""Anzeigentexte nachladen — nach dem Suchlauf und im Auto-Nachzug (#1038).

## Warum es das gibt

LinkedIn ueber JobSpy liefert ueber 1.000 Rohtreffer, aber keinen
Anzeigentext. Ihn fuer jeden Rohtreffer zu holen
(`linkedin_fetch_description=True`) haette den Lauf um Stunden verlaengert
und fremde Server fuer Treffer befragt, die der Filter gleich danach
verwirft. Der Auto-Nachzug holte hoechstens acht Stellen je Lauf der
Automatik; bei 36 neuen Treffern dauerte es fuenf Laeufe, und bis dahin
standen sie als "unbewertet" in der zweiten Gruppe (#756, #989).

Abgrenzung: `nachladen` holt und uebernimmt den Text EINER Stelle; hier
steht die Schleife ueber viele Stellen (Auswahl, Backoff, Grenze, Pause).

## Was bewusst so ist

- **Erst nach dem Filter** (dieselbe Regel wie beim Geocoding, #1057):
  der Suchlauf merkt sich nur die Treffer, die ihn passiert haben und
  keinen Text tragen (`ohne_anzeigentext` im Ergebnis).
- **Im Hintergrund, mit eigenem Eintrag** in `background_jobs` (F35/#799)
  — der Suchlauf ist schon fertig, wenn das Nachladen beginnt.
- **Hoeflich:** hoechstens `MAX_JE_LAUF` Abrufe, eine Pause dazwischen.
  Wer mehr hat, bekommt den Rest im naechsten Lauf der Automatik.
- **Ein Weg:** `holen` ist dieselbe Schleife fuer den Auto-Nachzug und
  fuer das Nachladen nach der Suche — Text, Kopf und Neubewertung laufen
  ueber `nachladen.text_uebernehmen` (#1048), Fehlschlaege zaehlen im
  selben Backoff (drei Versuche).
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

#: Hoechstens so viele Detailabrufe je Suchlauf.
MAX_JE_LAUF = 60
#: Pause zwischen zwei Abrufen (Sekunden) — fremde Server schonen.
PAUSE_SEK = 1.0
#: Nach so vielen Fehlschlaegen wird eine Stelle nicht mehr versucht.
MAX_FEHLVERSUCHE = 3
JOB_TYP = "text_nachzug"


def _fehlversuche(db, job_hash: str) -> int:
    try:
        return int(db.get_setting(f"refetch_fail:{job_hash}", "0") or "0")
    except (TypeError, ValueError):
        return 0


def fehlversuch_zaehlen(db, job_hash: str) -> None:
    try:
        db.set_setting(f"refetch_fail:{job_hash}", str(_fehlversuche(db, job_hash) + 1))
    except Exception:  # pragma: no cover
        pass


def fehlversuche_loeschen(db, job_hash: str) -> None:
    try:
        db.set_setting(f"refetch_fail:{job_hash}", "0")
    except Exception:  # pragma: no cover
        pass


def _kandidaten(db, hashes) -> list[dict]:
    """Aktive Stellen des Profils mit Adresse und ohne brauchbaren Text.

    Die Profilbindung macht `resolve_job_hash`: eine Kennung eines anderen
    Profils wird dort zu einer, die es nicht gibt."""
    from .datenguete import MIN_BESCHREIBUNG
    conn = db.connect()
    zeilen = []
    for h in hashes:
        echt = db.resolve_job_hash(h)
        if not echt:
            continue
        z = conn.execute(
            "SELECT hash, url, description FROM jobs WHERE hash=? AND is_active=1 "
            "AND url IS NOT NULL AND url != '' "
            "AND COALESCE(is_search_url, 0) = 0", (echt,)).fetchone()
        if z and len((z["description"] or "").strip()) < MIN_BESCHREIBUNG:
            zeilen.append(dict(z))
    return zeilen


def holen(db, hashes, *, max_jobs: int, client=None, pause: float = 0.0) -> dict:
    """Holt den Text fuer die genannten Stellen. Liefert die Zaehler."""
    import httpx
    from . import nachladen
    from .datenguete import MIN_BESCHREIBUNG

    zeilen = _kandidaten(db, hashes)
    geholt = fehlgeschlagen = backoff = versucht = 0
    eigener = client is None
    if eigener:
        client = httpx.Client(follow_redirects=True, timeout=15,
                              headers={"User-Agent": "PBP/1.7 (+github.com/MadGapun/PBP)"})
    try:
        for z in zeilen:
            if versucht >= max_jobs:
                break
            if _fehlversuche(db, z["hash"]) >= MAX_FEHLVERSUCHE:
                backoff += 1
                continue
            if versucht and pause:
                time.sleep(pause)
            versucht += 1
            try:
                befund = nachladen.beschreibung_holen(z["url"], client, timeout=15)
                text, kopf = befund.text, befund.kopf
            except Exception as exc:  # noqa: BLE001 — eine Stelle stoppt nichts
                logger.debug("Nachladen %s: %s", z["hash"], exc)
                text, kopf = "", {}
            if text and len(text.strip()) >= MIN_BESCHREIBUNG:
                nachladen.text_uebernehmen(db, z["hash"], text, kopf=kopf)
                fehlversuche_loeschen(db, z["hash"])
                geholt += 1
            else:
                fehlversuch_zaehlen(db, z["hash"])
                fehlgeschlagen += 1
    finally:
        if eigener:
            client.close()
    return {"kandidaten": len(zeilen), "versucht": versucht, "geholt": geholt,
            "fehlgeschlagen": fehlgeschlagen, "backoff": backoff,
            "offen": max(0, len(zeilen) - versucht - backoff)}


def nach_suche(db, such_job_id: str, *, client=None, pause: float = PAUSE_SEK) -> dict | None:
    """Nach einem fertigen Suchlauf: Text fuer dessen Treffer ohne Text.

    Schreibt das Ergebnis in den eigenen Hintergrund-Job UND unter
    `nachgeladen` in den Suchlauf, damit der Lauf-Hinweis es nennt."""
    such = db.get_background_job(such_job_id)
    if not such or such.get("status") not in ("fertig", "erledigt"):
        return None
    ergebnis = such.get("result") if isinstance(such.get("result"), dict) else {}
    hashes = list(ergebnis.get("ohne_anzeigentext") or [])
    if not hashes:
        return None
    eigener_job = db.create_background_job(JOB_TYP, {"suchlauf": such_job_id,
                                                     "stellen": len(hashes)})
    try:
        erg = holen(db, hashes, max_jobs=MAX_JE_LAUF, client=client, pause=pause)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Anzeigentexte nicht nachgeladen: %s", exc)
        db.update_background_job(eigener_job, "fehler",
                                 message=f"Nachladen abgebrochen: {exc}")
        return None
    db.update_background_job(
        eigener_job, "fertig", progress=100,
        message=(f"{erg['geholt']} Anzeigentexte nachgeladen, "
                 f"{erg['fehlgeschlagen']} ohne Erfolg, {erg['offen']} offen."),
        result=erg)
    try:
        such = db.get_background_job(such_job_id) or {}
        res = such.get("result") if isinstance(such.get("result"), dict) else {}
        res["nachgeladen"] = {k: erg[k] for k in ("geholt", "fehlgeschlagen", "offen")}
        db.update_background_job(such_job_id, such.get("status", "fertig"),
                                 progress=such.get("progress", 100),
                                 message=such.get("message", ""), result=res)
    except Exception as exc:  # pragma: no cover
        logger.warning("Nachlade-Ergebnis nicht am Suchlauf vermerkt: %s", exc)
    return erg
