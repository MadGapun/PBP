"""Seit wann gilt etwas als "neu"? Ein Zeitpunkt fuer Marken und Rueckschau (#1144).

Zwei Stellen fragten "was ist seit dem letzten Besuch passiert": die
"Neu"-Marken im Block "Offen" (`aufgaben_sicht`, #985) und die Rueckschau
`/api/recap`. Beide lasen denselben Wert `last_login_at` — und schrieben ihn
fort, solange sie lasen:

- die Rueckschau bei JEDEM Aufruf,
- die Marken, sobald seit dem letzten Mal mehr als vier Stunden vergangen
  waren.

Gemessen (01.10.2026): letzter Besuch vor 15 Stunden, Aufgabe vor 10 Stunden
angelegt. Erster Aufruf: eine Marke. F5 nach einer Minute: keine. Die Auskunft
"seit deinem letzten Besuch" loeschte sich beim ersten Neuladen selbst — und
beide Stellen massen gegen verschiedene Zeitpunkte, je nachdem, wer zuerst las.

Jetzt sind es zwei getrennte Werte:

- `last_login_at` — der LETZTE ZUGRIFF. Er wird bei jedem Lesen fortgeschrieben.
- `neu_seit_basis` — der Beginn des Besuchs: der Zugriff davor. Gegen ihn wird
  "neu" gemessen. Er aendert sich nur, wenn ein NEUER Besuch beginnt, also nach
  einer Pause von mehr als `BESUCH_PAUSE_STUNDEN` ohne jeden Zugriff.

Ein Besuch umfasst damit alles, was ohne laengere Pause aufeinanderfolgt:
Neuladen, Hin- und Herwechseln, ein ueber Stunden offenes Dashboard. Ein
Dashboard, das die ganze Nacht offen bleibt, ist EIN Besuch.

Ja, das ist ein Schreibvorgang in einem Lesepfad. Er steht hier bewusst und
eng begrenzt: ein zweiter Weg, den jemand extra aufrufen muesste, waere ein
Weg, den niemand aufruft.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

#: Ab welcher Pause ohne Zugriff beginnt ein neuer Besuch? Kuerzer, und die
#: Marken verschwinden beim ersten Neuladen; laenger, und sie stehen tagelang.
BESUCH_PAUSE_STUNDEN = 4

#: Der letzte Zugriff (Name aus der Zeit vor #1144 beibehalten: so bleibt der
#: Wert vorhandener Installationen gueltig).
BESUCH_EINSTELLUNG = "last_login_at"

#: Der Beginn des laufenden Besuchs — gegen ihn wird "neu" gemessen.
BASIS_EINSTELLUNG = "neu_seit_basis"

#: Ohne jeden frueheren Zugriff: so weit schaut die erste Auskunft zurueck.
ERSTES_FENSTER_STUNDEN = 72


def _lesen(db, schluessel: str) -> datetime | None:
    try:
        roh = db.get_profile_setting(schluessel, None)
    except Exception:  # noqa: BLE001
        return None
    if not roh:
        return None
    try:
        wert = datetime.fromisoformat(str(roh).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None
    return wert if wert.tzinfo else wert.replace(tzinfo=timezone.utc)


def _schreiben(db, schluessel: str, wert: datetime) -> None:
    try:
        db.set_profile_setting(schluessel, wert.isoformat())
    except Exception as exc:  # noqa: BLE001 — die Auskunft darf daran nicht scheitern
        logger.debug("Besuch (%s) nicht gespeichert: %s", schluessel, exc)


def neu_seit(db, *, jetzt: datetime | None = None) -> datetime:
    """Der Zeitpunkt, gegen den "neu" gemessen wird — und ein Zugriff.

    Jeder Aufruf zaehlt als Zugriff (`last_login_at` rueckt auf "jetzt").
    Die Basis bleibt, solange der Besuch dauert; ein neuer Besuch beginnt
    nach einer Pause von mehr als `BESUCH_PAUSE_STUNDEN` und nimmt dann den
    letzten Zugriff als Basis.
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    zugriff = _lesen(db, BESUCH_EINSTELLUNG)
    basis = _lesen(db, BASIS_EINSTELLUNG)

    if zugriff is None:
        # Erster Zugriff ueberhaupt (oder der Wert ist unlesbar).
        neue_basis = basis or jetzt - timedelta(hours=ERSTES_FENSTER_STUNDEN)
    elif jetzt - zugriff > timedelta(hours=BESUCH_PAUSE_STUNDEN):
        # Pause: ein neuer Besuch beginnt. Neu ist, was seit dem letzten
        # Zugriff dazukam.
        neue_basis = zugriff
    else:
        # Mitten im Besuch. Fehlt die Basis noch (Wert aus der Zeit vor
        # #1144), gilt der letzte Zugriff als ihr Beginn.
        neue_basis = basis or zugriff

    if basis != neue_basis:
        _schreiben(db, BASIS_EINSTELLUNG, neue_basis)
    _schreiben(db, BESUCH_EINSTELLUNG, jetzt)
    return neue_basis
