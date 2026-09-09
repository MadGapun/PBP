"""Was wurde wann und von wem aussortiert (#1010).

Nutzerwunsch vom 09.09.2026:

    "Ausserdem waere ein 'Log', welche man manuell aussortiert hat (sowie
    die automatisch aussortierten, ggf. oder besser in Kombination)
    hilfreich, damit man, wenn man sich mal verklickt hat, diese auch
    zurueckholen kann."

## Was schon da war — und warum es nicht reichte

Rueckholen ging: der Stellen-Tab hat den Filter "Ausgeblendet" mit einem
Knopf je Zeile, und `stelle_reaktivieren` gibt es als Werkzeug. Es fehlte
nicht die Faehigkeit, sondern das **Wiederfinden**:

* Die Liste sortierte nach `updated_at` — und diese Spalte fasst jede
  Score-Neuberechnung, jeden Beschreibungs-Nachzug und jeden
  Snapshot-Backfill an. Nach einem Suchlauf stand die eben weggeklickte
  Stelle nicht mehr oben.
* Manuell und automatisch waren nicht unterscheidbar. Die Automatik
  schreibt ihre Gruende seit #913 mit `auto:`-Praefix; sichtbar war das
  nirgends.
* Ueber 2.000 Eintraege ohne Zeitfenster sind ein Archiv, kein
  Rueckholweg.

## Zwei Entscheidungen, die hier festgehalten gehoeren

**Der Altbestand bekommt KEIN Datum.** `updated_at` als Ersatz
einzusetzen waere eine erfundene Angabe — genau der Fehler aus #987, wo
ein gespeicherter Wert etwas anderes bedeutete als er sagte. Wer keinen
Zeitpunkt hat, wird als solcher ausgewiesen und taucht nur im Fenster
"alle" auf. Ihn in "heute" zu zeigen waere eine Behauptung.

**Herkunft ist eine eigene Angabe, kein Praefix zum Selberlesen.** Ein
eigenes Urteil sieht man anders an als eines der Automatik — und der
Mensch soll das nicht aus einer Zeichenkette heraussuchen muessen.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Die Automatik markiert ihre Gruende seit v1.7.17 (#913) mit diesem
# Praefix. KURZFORM ohne Begruendung eingeschlossen ("auto:duplikat").
AUTO_PRAEFIX = "auto:"

ZEITFENSTER = ("heute", "7tage", "30tage", "alle")

OHNE_ZEITPUNKT = (
    "Zeitpunkt unbekannt — diese Stelle wurde vor v1.7.64 aussortiert, "
    "als PBP den Zeitpunkt noch nicht festgehalten hat.")


HERKUENFTE = ("ich", "automatik", "unbekannt")


def herkunft(job: dict) -> str:
    """'ich', 'automatik' oder 'unbekannt' — gespeichert, nicht geraten.

    Die Spalte `dismissed_by` entsteht seit v1.7.64 an den
    Schreibstellen. Fuer den Altbestand gibt es nur einen sicheren
    Beleg: das `auto:`-Praefix, wie `save_jobs` es fuer den
    Wiedergaenger schreibt (#941).

    Alles andere bleibt **unbekannt**, und das ist Absicht. `duplikat`
    und `zu_weit_entfernt` setzt sowohl die Automatik (#641/#732) als
    auch der Mensch; und `normalisiere_dismiss_wert` entfernt das
    `auto:`-Praefix beim Schreiben (bewusst, #913) — aus dem Grund
    allein ist die Herkunft also nicht rekonstruierbar. Sie zu raten
    waere genau der Fehler, den #989 abgeschafft hat: unbekannt ist
    nicht dasselbe wie "war ich".
    """
    gespeichert = str(job.get("dismissed_by") or "").strip().lower()
    if gespeichert in ("ich", "automatik"):
        return gespeichert
    if str(job.get("dismiss_reason") or "").startswith(AUTO_PRAEFIX):
        return "automatik"
    return "unbekannt"


def grund_klartext(dismiss_reason) -> str:
    """Der Grund ohne das technische Praefix."""
    roh = str(dismiss_reason or "").strip()
    if roh.startswith(AUTO_PRAEFIX):
        roh = roh[len(AUTO_PRAEFIX):].strip()
    return roh


def zeitpunkt_lesen(wert):
    """Den gespeicherten Zeitpunkt als vergleichbare Zeit — oder None.

    `_now()` schreibt UTC-ISO mit Zeitzonen-Offset. Zeichenketten
    verschiedener Formate zu vergleichen geht schief, ohne dass es
    auffaellt: "2026-09-09T14:37" und "2026-09-09 14:37" sortieren
    ueber das 'T' gegeneinander, nicht ueber die Zeit. Das ist die
    Zeitzonen-Falle aus v1.7.21 (`date('now')` in SQL neben
    `datetime.now()` in Python), nur eine Ebene hoeher.
    """
    roh = str(wert or "").strip()
    if not roh:
        return None
    try:
        stand = datetime.fromisoformat(roh.replace("Z", "+00:00"))
    except ValueError:
        return None
    # Ein Wert ohne Zeitzone stammt aus dem Altbestand; er wird als UTC
    # gelesen, weil `_now()` seit jeher UTC schreibt.
    if stand.tzinfo is None:
        stand = stand.replace(tzinfo=timezone.utc)
    return stand


def _grenze(zeitfenster: str):
    """Ab wann zaehlt ein Eintrag — oder None fuer 'alle'.

    "heute" heisst Mitternacht in der ORTSZEIT des Menschen, nicht in
    UTC: wer um 01:00 Uhr etwas wegklickt, sucht es am selben Morgen
    unter "heute". Verglichen wird danach zeitzonenbewusst.
    """
    if zeitfenster == "alle":
        return None
    if zeitfenster == "heute":
        lokal = datetime.now().astimezone()
        return lokal.replace(hour=0, minute=0, second=0, microsecond=0)
    tage = {"7tage": 7, "30tage": 30}[zeitfenster]
    return datetime.now(timezone.utc) - timedelta(days=tage)


def eintraege(db, zeitfenster: str = "7tage", limit: int = 50,
              herkunft_filter: str = "") -> dict:
    """Das Protokoll — beide Herkuenfte in EINER Liste.

    Args:
        zeitfenster: 'heute', '7tage', '30tage' oder 'alle'.
        limit: hoechstens so viele Zeilen.
        herkunft_filter: '' (beide), 'ich' oder 'automatik'.

    Der Nutzer hat ausdruecklich beides zusammen verlangt ("ggf. oder
    besser in Kombination") — getrennt zu zeigen waere zwei Listen fuer
    dieselbe Frage.
    """
    if zeitfenster not in ZEITFENSTER:
        return {"fehler": f"Unbekanntes Zeitfenster '{zeitfenster}'. "
                          f"Moeglich: {', '.join(ZEITFENSTER)}."}
    if herkunft_filter and herkunft_filter not in HERKUENFTE:
        return {"fehler": "herkunft muss leer sein oder eines von: "
                          + ", ".join(HERKUENFTE) + "."}

    alle = db.get_dismissed_jobs() or []
    grenze = _grenze(zeitfenster)

    zeilen, ohne_datum, ausserhalb = [], 0, 0
    for job in alle:
        wann = (job.get("dismissed_at") or "").strip()
        stand = zeitpunkt_lesen(wann)
        quelle = herkunft(job)
        if herkunft_filter and quelle != herkunft_filter:
            continue
        if grenze is not None:
            if stand is None:
                # Kein Datum heisst NICHT "alt genug zum Wegfiltern" —
                # es heisst "unbekannt". Gezaehlt statt verschwiegen.
                ohne_datum += 1
                continue
            if stand < grenze:
                ausserhalb += 1
                continue
        zeilen.append({
            "hash": job.get("hash", "").split(":")[-1],
            "titel": job.get("title", ""),
            "firma": job.get("company", ""),
            "grund": grund_klartext(job.get("dismiss_reason")),
            "herkunft": quelle,
            "aussortiert_am": wann or "",
            "notiz": job.get("dismiss_note") or "",
        })
        if not wann:
            zeilen[-1]["zeitpunkt_hinweis"] = OHNE_ZEITPUNKT

    # Neueste zuerst; ohne Zeitpunkt ans Ende, weil sie sich nicht
    # einordnen lassen.
    zeilen.sort(
        key=lambda z: (zeitpunkt_lesen(z["aussortiert_am"])
                       or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True)
    gesamt = len(zeilen)
    befund = {
        "zeitfenster": zeitfenster,
        "anzahl": min(gesamt, max(0, limit)),
        "anzahl_gesamt": gesamt,
        "eintraege": zeilen[:max(0, limit)],
        "aussortiert_gesamt": len(alle),
    }
    if ohne_datum:
        befund["ohne_zeitpunkt_verborgen"] = ohne_datum
        befund["hinweis_zeitpunkt"] = (
            f"{ohne_datum} aussortierte Stelle(n) tragen keinen Zeitpunkt "
            "und sind in diesem Fenster deshalb nicht enthalten — sie "
            "stammen aus der Zeit vor v1.7.64. Mit zeitfenster='alle' "
            "stehen sie mit dabei.")
    if ausserhalb:
        befund["ausserhalb_des_fensters"] = ausserhalb
    if not zeilen:
        befund["nachricht"] = (
            "In diesem Zeitfenster wurde nichts aussortiert."
            if not ohne_datum else
            "In diesem Zeitfenster wurde nichts aussortiert — es gibt aber "
            f"{ohne_datum} Eintrag(e) ohne Zeitpunkt. "
            "Nimm zeitfenster='alle'.")
    return befund
