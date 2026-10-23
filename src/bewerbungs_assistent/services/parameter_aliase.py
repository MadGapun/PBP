"""Parameternamen, die in den Werkzeugen nebeneinander in Gebrauch sind (#1148 Punkt 9, Rest).

Bei 280 Werkzeugen sind über die Jahre zwei Schreibweisen für dasselbe entstanden: `firma` und `company`, `titel` und `title`,
`dokument_id` und `document_id`, `job_hash` und `stellen_hash`, `bewerbung_id` und `application_id`. Claude greift nach dem Namen, den
das letzte Werkzeug trug, und scheitert an einer Zeichenkette — obwohl die Absicht klar war.

Statt 280 Signaturen anzufassen (jede Umbenennung bräche gespeicherte Anleitungen), übersetzt die Middleware in `server.py` einen
unbekannten Namen in den bekannten derselben Gruppe, bevor das Werkzeug die Argumente sieht — wie bei den typisierten Kennungen
(`services/typed_ids`). Die Regel ist eng gefasst und verändert nie einen Namen, den das Werkzeug selbst kennt:

* nur Namen aus `GRUPPEN`,
* nur wenn das Werkzeug den übergebenen Namen NICHT kennt und genau EINEN Namen derselben Gruppe kennt,
* nur wenn dieser Name nicht ohnehin schon übergeben wurde.

`hash_a`/`hash_b`, `master_hash`/`duplikat_hash` und `email` gehören absichtlich nicht dazu: das sind verschiedene Dinge, keine
Schreibweisen.
"""
from __future__ import annotations

from typing import Optional

#: Je Gruppe die gleichwertigen Schreibweisen. Ein Test hält fest, dass kein Werkzeug zwei Namen derselben Gruppe zugleich trägt (dann
#: wäre eine Übersetzung mehrdeutig) und dass jeder Name irgendwo vorkommt (sonst ist die Zeile tot).
GRUPPEN: tuple = (
    ("dokument_id", "document_id"),
    ("firma", "company"),
    ("titel", "title"),
    ("job_hash", "stellen_hash"),
    ("bewerbung_id", "application_id"),
)

_ANDERE: dict = {}
for _gruppe in GRUPPEN:
    for _name in _gruppe:
        _ANDERE[_name] = tuple(n for n in _gruppe if n != _name)


def uebersetzen(arguments, bekannte) -> Optional[dict]:
    """Ein NEUES Argumente-Dict mit übersetzten Namen, oder `None`, wenn nichts zu tun ist.

    `bekannte`: die Parameternamen des Werkzeugs (aus seinem Eingabeschema). Das übergebene Dict bleibt unverändert.
    """
    if not isinstance(arguments, dict) or not arguments or not bekannte:
        return None
    bekannte = set(bekannte)
    neu: Optional[dict] = None
    for name in list(arguments):
        if name in bekannte or name not in _ANDERE:
            continue
        kandidaten = [a for a in _ANDERE[name] if a in bekannte and a not in arguments]
        if len(kandidaten) != 1:
            continue
        if neu is None:
            neu = dict(arguments)
        neu[kandidaten[0]] = neu.pop(name)
    return neu
