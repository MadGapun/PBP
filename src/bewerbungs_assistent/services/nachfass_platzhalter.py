"""Offene Platzhalter im Nachfass-Text (#1122).

Der Fall (Screenshot 29.09.2026): `nachfass_planen` schrieb „ich habe mich
am {applied_at} auf die Position … beworben“ in die Datenbank und füllte
den Platzhalter nie. Der Text ist dann nicht sendefertig — und wer ihn
kopiert, schickt die geschweiften Klammern mit.

Abgrenzung: HTML-Zeichenverweise in Titeln (`&amp;`) löst
`database._entities_aufloesen` (#965) auf; das war der Nebenbefund
daneben und hat hier nichts zu suchen. (Diese Frage stand kurz zweimal im
Code — die Kopie wurde beim Gegenlesen entfernt.)
"""
from __future__ import annotations

import re

_PLATZHALTER = re.compile(r"\{[a-z_]+\}")


def offene_platzhalter(text) -> list[str]:
    """Die `{name}`-Platzhalter, die noch im Text stehen."""
    return _PLATZHALTER.findall(text) if isinstance(text, str) else []


def platzhalter_fuellen(text, app: dict | None):
    """Setzt `{applied_at}` und `{ansprechpartner}` aus der Bewerbung ein.

    Fehlt der Wert, verschwindet die ganze Wendung statt eine Lücke zu
    lassen: „… mich am {applied_at} auf …“ wird „… mich auf …“, und
    „Sehr geehrte/r {ansprechpartner},“ wird „Sehr geehrte Damen und
    Herren,“. Andere Platzhalter bleiben stehen — sie sind ein Befund, den
    `offene_platzhalter` meldet, keine Vermutung wert.
    """
    if not isinstance(text, str) or "{" not in text:
        return text
    app = app or {}
    from .anzeigenamen import datum_text

    datum = datum_text(app["applied_at"]) if app.get("applied_at") else ""
    if datum:
        text = text.replace("{applied_at}", datum)
    else:
        text = re.sub(r"\bam \{applied_at\}\s*", "", text)
        text = text.replace("{applied_at}", "")
    name = (app.get("ansprechpartner") or "").strip()
    if name:
        text = text.replace("{ansprechpartner}", name)
    else:
        text = re.sub(r"Sehr geehrte/r \{ansprechpartner\},",
                      "Sehr geehrte Damen und Herren,", text)
        text = text.replace("{ansprechpartner}", "")
    return text
