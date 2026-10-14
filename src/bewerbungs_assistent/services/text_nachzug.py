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

import json
import logging
import time
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

#: Hoechstens so viele Detailabrufe je Suchlauf.
MAX_JE_LAUF = 60
#: Pause zwischen zwei Abrufen (Sekunden) — fremde Server schonen.
PAUSE_SEK = 1.0
#: Nach so vielen Fehlschlaegen wird eine Stelle nicht mehr versucht ...
MAX_FEHLVERSUCHE = 3
#: ... aber nur so lange: nach so vielen Tagen ohne neuen Versuch bekommt sie eine frische Runde (#1139). Vorher blieb sie
#: fuer immer im Backoff - auch nach einem Netzausfall, einer geaenderten Seite oder einer reparierten Schnittstelle.
FEHLZAEHLER_VERFALL_TAGE = 14
#: So viele Netzfehler hintereinander beenden die Schleife: ohne Netz hilft jeder weitere Abruf nur dem Zeitlimit.
MAX_NETZFEHLER_IN_FOLGE = 3
JOB_TYP = "text_nachzug"


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


def _zeit(roh) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(roh))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _zaehler(roh) -> int:
    try:
        return int(roh or 0)
    except (TypeError, ValueError):
        return 0


def _gilt(zaehler: int, letzter, jetzt: datetime) -> int:
    """Der Fehlzaehler, soweit er noch gilt: ohne Zeitstempel (Altbestand) oder nach dem Verfall ist er 0."""
    if zaehler <= 0:
        return 0
    zeit = _zeit(letzter)
    if zeit is None or jetzt - zeit >= timedelta(days=FEHLZAEHLER_VERFALL_TAGE):
        return 0
    return zaehler


def _fehlversuche(db, job_hash: str) -> int:
    try:
        return _gilt(_zaehler(db.get_setting(f"refetch_fail:{job_hash}", "0")),
                     db.get_setting(f"refetch_last:{job_hash}", ""), _jetzt())
    except Exception:  # noqa: BLE001
        return 0


def versuch_vermerken(db, job_hash: str) -> None:
    """Haelt fest, DASS und WANN diese Stelle versucht wurde - die Reihenfolge der naechsten Laeufe haengt daran."""
    try:
        db.set_setting(f"refetch_last:{job_hash}", _jetzt().isoformat())
    except Exception:  # pragma: no cover
        pass


def fehlversuch_zaehlen(db, job_hash: str) -> None:
    """Ein Fehlversuch mehr - auf dem Stand, der noch gilt (ein verfallener Zaehler faengt bei 1 an)."""
    try:
        db.set_setting(f"refetch_fail:{job_hash}", str(_fehlversuche(db, job_hash) + 1))
        versuch_vermerken(db, job_hash)
    except Exception:  # pragma: no cover
        pass


def verfallenen_zaehler_loeschen(db, job_hash: str) -> None:
    """Setzt einen VERFALLENEN Fehlzaehler auf 0 (#1202) - zu Beginn des Versuchs, BEVOR der Zeitstempel erneuert wird.

    `_fehlversuche` rechnet den Zaehler aus dem Wert und dem Zeitstempel. Erneuert `versuch_vermerken` den Zeitstempel, ohne
    dass der alte Wert gestrichen wurde, gilt der verfallene Zaehler wieder: ein Fehlschlag setzte ihn auf 4 statt auf 1, und ein
    blosser Netzfehler (zaehlt nicht) hielt die Stelle im Backoff.
    """
    try:
        roh = _zaehler(db.get_setting(f"refetch_fail:{job_hash}", "0"))
        if roh > 0 and _fehlversuche(db, job_hash) == 0:
            db.set_setting(f"refetch_fail:{job_hash}", "0")
    except Exception:  # pragma: no cover
        pass


def fehlversuche_loeschen(db, job_hash: str) -> None:
    try:
        db.set_setting(f"refetch_fail:{job_hash}", "0")
    except Exception:  # pragma: no cover
        pass


def auswahl(db, *, limit: int, profil_id: str | None = None) -> list[str]:
    """Die Hashes aus `auswahl_befund` - fuer den, der nur die Liste braucht."""
    return auswahl_befund(db, limit=limit, profil_id=profil_id)["hashes"]


def auswahl_befund(db, *, limit: int, profil_id: str | None = None) -> dict:
    """Die Stellen ohne brauchbaren Text in FESTER Reihenfolge (#1139), samt Zaehlung.

    Nie versuchte zuerst, dann die am laengsten nicht versuchte; Stellen im Backoff fehlen. Vorher nahm der Auto-Nachzug die
    ersten 24 nach Zeilennummer: standen die im Backoff, wurden die uebrigen nie versucht (gemessen: 30 Stellen ohne Text,
    24 im Backoff, 0 versucht, 6 nie). Quellen ohne Abruf-Erlaubnis (#1189) sind kein Kandidat.
    """
    from .datenguete import MIN_BESCHREIBUNG
    from .quellen_auflagen import sql_ohne_abruf
    pid = profil_id or db.get_active_profile_id()
    ohne, ohne_params = sql_ohne_abruf("url")
    zeilen = db.connect().execute(
        "SELECT j.hash AS hash, f.value AS fehler, l.value AS zuletzt FROM jobs j "
        "LEFT JOIN settings f ON f.key = 'refetch_fail:' || j.hash "
        "LEFT JOIN settings l ON l.key = 'refetch_last:' || j.hash "
        "WHERE j.is_active=1 AND (j.profile_id=? OR j.profile_id IS NULL) "
        "AND j.url IS NOT NULL AND j.url != '' "
        # #645: Such-URL-Stellen ausschliessen - sonst landet als "Beschreibung" der Anriss der Ergebnisseite.
        "AND COALESCE(j.is_search_url, 0) = 0 "
        "AND (j.description IS NULL OR LENGTH(TRIM(j.description)) < ?) "
        + ohne +
        " ORDER BY (l.value IS NOT NULL), l.value, j.hash",
        (pid, MIN_BESCHREIBUNG, *ohne_params),
    ).fetchall()
    jetzt = _jetzt()

    def _roh(wert):
        try:
            return json.loads(wert) if wert is not None else None
        except (TypeError, ValueError):
            return None

    ergebnis: list[str] = []
    im_backoff = 0
    for z in zeilen:
        if _gilt(_zaehler(_roh(z["fehler"])), _roh(z["zuletzt"]), jetzt) >= MAX_FEHLVERSUCHE:
            im_backoff += 1
            continue
        if len(ergebnis) < limit:
            ergebnis.append(z["hash"])
    return {"hashes": ergebnis, "im_backoff": im_backoff, "kandidaten": len(zeilen)}


def _kandidaten(db, hashes) -> list[dict]:
    """Aktive Stellen des Profils mit Adresse und ohne brauchbaren Text.

    Die Profilbindung macht `resolve_job_hash`: eine Kennung eines anderen
    Profils wird dort zu einer, die es nicht gibt."""
    from .datenguete import MIN_BESCHREIBUNG
    from .quellen_auflagen import kein_automatischer_abruf
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
            # #1189: Quellen mit Auflage (jobtic) ruft PBP nicht selbst ab - kein Kandidat, kein Fehlversuch.
            if kein_automatischer_abruf(url=z["url"]):
                continue
            zeilen.append(dict(z))
    return zeilen


def holen(db, hashes, *, max_jobs: int, client=None, pause: float = 0.0) -> dict:
    """Holt den Text fuer die genannten Stellen. Liefert die Zaehler."""
    import httpx
    from . import nachladen
    from .datenguete import MIN_BESCHREIBUNG

    zeilen = _kandidaten(db, hashes)
    geholt = fehlgeschlagen = backoff = versucht = netzfehler = in_folge = 0
    abgebrochen = ""
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
            befund = None
            try:
                befund = nachladen.beschreibung_holen(z["url"], client, timeout=15)
                text, kopf = befund.text, befund.kopf
            except Exception as exc:  # noqa: BLE001 — eine Stelle stoppt nichts
                logger.debug("Nachladen %s: %s", z["hash"], exc)
                text, kopf = "", {}
            # Jeder Versuch steht fest, auch der ohne Ergebnis: die naechste Auswahl nimmt zuerst, was am laengsten wartet.
            # #1202: ein verfallener Zaehler wird vorher gestrichen - der frische Zeitstempel machte ihn sonst wieder gueltig.
            verfallenen_zaehler_loeschen(db, z["hash"])
            versuch_vermerken(db, z["hash"])
            if text and len(text.strip()) >= MIN_BESCHREIBUNG:
                nachladen.text_uebernehmen(db, z["hash"], text, kopf=kopf)
                fehlversuche_loeschen(db, z["hash"])
                geholt += 1
                in_folge = 0
                continue
            # (ein Befund ohne Status - etwa ein Ersatz im Test - zaehlt wie bisher als Fehlversuch)
            status = getattr(befund, "status", "") if befund is not None else nachladen.FEHLER
            http = getattr(befund, "http_status", None) if befund is not None else None
            if status == nachladen.FEHLER or http == 429:
                # Netz weg, Server nicht erreichbar, 5xx oder "zu viele Anfragen": das sagt etwas ueber diesen Moment,
                # nicht ueber die Stelle - kein Fehlversuch, und mehrere hintereinander beenden die Schleife.
                netzfehler += 1
                in_folge += 1
                if in_folge >= MAX_NETZFEHLER_IN_FOLGE:
                    abgebrochen = "netz"
                    break
                continue
            in_folge = 0
            fehlversuch_zaehlen(db, z["hash"])
            fehlgeschlagen += 1
    finally:
        if eigener:
            client.close()
    return {"kandidaten": len(zeilen), "versucht": versucht, "geholt": geholt,
            "fehlgeschlagen": fehlgeschlagen, "backoff": backoff, "netzfehler": netzfehler,
            "abgebrochen": abgebrochen,
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
