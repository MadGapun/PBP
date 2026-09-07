"""Welche Scoring-Regler es gibt — und welche nur so aussehen.

Belegt in #988 (Randbefund, 07.09.2026): `scoring_konfigurieren`
meldete unter der Dimension `schwellenwert` ZWEI Zeilen —

    auto_ignore    0
    schwellenwert  35

Gelesen wird ausschliesslich `auto_ignore`. Die zweite Zeile war
irgendwann ueber `scoring_konfigurieren('setzen', 'schwellenwert',
'schwellenwert', 35)` entstanden und wurde ungeprueft durchgeschrieben.
Sie steht seither in der Anzeige, sieht nach einer Einstellung aus und
tut nichts. Der Nutzer glaubte, seine Schwelle liege bei 35; sie lag
bei 0.

**Das ist #981 in einer anderen Tabelle.** Dort bot ein Dialog einen
Status an, den `VALID_STATUSES` nicht kannte, und der Endpunkt schrieb
ihn ungeprueft durch. Hier nimmt ein Regler-Werkzeug einen Schluessel
an, den niemand liest. Beide Male entsteht kein Fehler, sondern eine
Einstellung ohne Wirkung — und die ist teurer als eine Fehlermeldung,
weil man ihr glaubt.

Die Entfernungs-Dimensionen sind bewusst offen: ihre Schluessel sind
km-Stufen, und wer eine eigene Stufe braucht, darf sie anlegen. Alles
andere hat ein festes Vokabular.
"""
from __future__ import annotations

# dimension -> erlaubte sub_keys. `None` heisst: freie Zahl (km-Stufe).
VOKABULAR: dict[str, frozenset[str] | None] = {
    "stellentyp": frozenset({"festanstellung", "freelance", "zeitarbeit",
                             "befristet", "praktikum", "werkstudent",
                             "minijob", "teilzeit"}),
    "remote": frozenset({"remote", "hybrid", "vor_ort", "unbekannt"}),
    "entfernung_fest": None,
    "entfernung_freelance": None,
    "gehalt": frozenset({"pro_10_prozent"}),
    "schwellenwert": frozenset({"auto_ignore"}),
    "entfernung_gehalt_kompensation": frozenset({"spanne"}),
}

# Regler, die es noch gibt, aber nichts mehr bewirken. Sie stehen im
# Bestand und sollen NICHT still verschwinden — wer sie sieht, soll
# erfahren, warum sie wirkungslos sind.
STILLGELEGT: dict[str, str] = {
    "hochschulabschluss": (
        "Wirkungslos seit v1.7.35 (#972): die Hochschulabschluss-Pruefung "
        "ist ersatzlos entfernt, nachdem sie in drei Anlaeufen nicht "
        "zuverlaessig zwischen 'Abschluss gefordert' und 'Studium als "
        "Zielgruppe' unterscheiden konnte. Der Ablehnungsgrund "
        "'kein_hochschulabschluss' bleibt fuer Altdaten waehlbar."),
}


def ist_zahl(text: str) -> bool:
    return bool(str(text).strip()) and str(text).strip().isdigit()


def pruefe(dimension: str, sub_key: str) -> str:
    """Leerer String = in Ordnung, sonst die Begruendung der Absage."""
    dim = (dimension or "").strip()
    sub = (sub_key or "").strip()
    if not dim or not sub:
        return "dimension und sub_key sind Pflicht."
    if dim in STILLGELEGT:
        return STILLGELEGT[dim]
    if dim not in VOKABULAR:
        return (f"Unbekannte Dimension '{dim}'. Moeglich sind: "
                + ", ".join(sorted(VOKABULAR)) + ".")
    erlaubt = VOKABULAR[dim]
    if erlaubt is None:
        if not ist_zahl(sub):
            return (f"'{dim}' erwartet eine km-Stufe als reine Zahl "
                    f"(z. B. '50'), bekommen: '{sub}'. Die Stufen sind "
                    "OBERGRENZEN (#917).")
        return ""
    if sub not in erlaubt:
        return (f"'{sub}' ist kein Regler von '{dim}'. Moeglich sind: "
                + ", ".join(sorted(erlaubt)) + ".")
    return ""


def wirkungslos(dimension: str, sub_key: str) -> str:
    """Warum eine BESTEHENDE Zeile nichts tut — leer, wenn sie wirkt.

    Getrennt von `pruefe`, weil der Bestand aelter ist als das
    Vokabular: eine Zeile, die heute nicht mehr angelegt werden darf,
    steht trotzdem in vielen Datenbanken. Sie zu loeschen waere ein
    Datenverlust ohne Not — sie zu benennen ist die Aufgabe.
    """
    return pruefe(dimension, sub_key)
