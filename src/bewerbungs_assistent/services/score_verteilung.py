"""Welchen Score hatten die Stellen, auf die du dich beworben hast? (#986)

Frage des Nutzers am 07.09.2026:

    "Wie hoch war der Score bei den Stellen, auf die ich mich beworben
    habe, als Spanne und Durchschnitt? Vielleicht kann man daraus
    lernen, auf welche Stellen ich mich bewerbe."

Die Zahlen existierten, aber nur als Nebenprodukt von
`kalibrierung_backtest` (#778) — gebaut fuer die Schwellenkalibrierung,
nicht als Statistik. `statistiken_abrufen` lieferte Status, Quoten,
Zeiten und Kanaele, aber keine Score-Kennzahl.

**Warum das eine eigene Kennzahl ist.** Der Score ist eine
EINSCHAETZUNG der Passung; die Entscheidung faellt der Mensch. Die
Verteilung ueber die tatsaechlich abgeschickten Bewerbungen zeigt
deshalb etwas, das keine andere Kennzahl zeigt: **wie weit das eigene
Urteil vom Modell abweicht, und wo systematisch.**

Zwei Dinge, die diese Kennzahl NICHT tun darf:

* **Score 0 ist keine Bewertung.** Er heisst "kein MUSS-Keyword
  getroffen" — die Stelle wurde gar nicht inhaltlich beurteilt. Als
  Zahl in einen Mittelwert zu geben waere derselbe Fehler wie der
  stille Nulltarif aus #989, nur in der Statistik. Er wird deshalb
  getrennt ausgewiesen.
* **Bewerbungen ohne verknuepfte Stelle sind eine Datenluecke**, kein
  Wert. Wer sie stillschweigend weglaesst, rechnet mit einer Auswahl
  und nennt sie Gesamtheit.

Die Kennzahl ist LESEND. Sie veraendert keinen Score (#963: ein
Lesewerkzeug hat keine Nebenwirkung).
"""
from __future__ import annotations

# Ab wie vielen bewertbaren Bewerbungen die Quartile ueberhaupt etwas
# aussagen. Darunter waere ein Median die Verkleidung eines Einzelfalls.
MIN_FUER_QUARTILE = 5


def _quantil(sortiert: list, anteil: float) -> float:
    """Einfaches Quantil ohne Fremdbibliothek."""
    if not sortiert:
        return 0.0
    if len(sortiert) == 1:
        return float(sortiert[0])
    pos = anteil * (len(sortiert) - 1)
    unten = int(pos)
    oben = min(unten + 1, len(sortiert) - 1)
    rest = pos - unten
    return round(sortiert[unten] * (1 - rest) + sortiert[oben] * rest, 1)


def kennzahlen(werte: list) -> dict:
    """Spanne, Quartile und Mittel — oder eine ehrliche Absage."""
    sortiert = sorted(float(w) for w in werte)
    if not sortiert:
        return {}
    ergebnis = {
        "anzahl": len(sortiert),
        "min": sortiert[0],
        "max": sortiert[-1],
        "mittel": round(sum(sortiert) / len(sortiert), 1),
        "median": _quantil(sortiert, 0.5),
    }
    if len(sortiert) >= MIN_FUER_QUARTILE:
        ergebnis["q25"] = _quantil(sortiert, 0.25)
        ergebnis["q75"] = _quantil(sortiert, 0.75)
    else:
        ergebnis["hinweis_wenig_daten"] = (
            f"Nur {len(sortiert)} Werte — Quartile waeren die Verkleidung "
            "eines Einzelfalls und bleiben deshalb weg.")
    return ergebnis


def verteilung(db, schwelle=None) -> dict:
    """Die Score-Verteilung ueber die beworbenen Stellen.

    Args:
        schwelle: Die aktuelle Score-Schwelle. Ohne sie entfaellt die
            Markierung; sie wird NICHT geraten.
    """
    try:
        bewerbungen = db.get_applications() or []
    except Exception:
        return {}
    if not bewerbungen:
        return {}

    # `applications.job_hash` traegt den OEFFENTLICHEN Hash,
    # `jobs.hash` den profil-praefixierten. Ein rohes
    # `WHERE hash=?` findet deshalb nichts — gemessen: 99 von 99
    # Bewerbungen ohne Score, obwohl fast alle eine Stelle haben. Genau
    # davor warnt die DB-Helfer-Regel; `get_job` loest beide Formen auf.
    bewertbar, ohne_muss, ohne_stelle = [], [], []
    je_ausgang: dict[str, list] = {}
    unter_schwelle = []

    for bew in bewerbungen:
        hash_ = bew.get("job_hash")
        score = None
        if hash_:
            try:
                stelle = db.get_job(hash_)
                if stelle is not None:
                    score = stelle.get("score")
            except Exception:
                score = None
        eintrag = {
            "bewerbung_id": str(bew.get("id", ""))[:8],
            "titel": (bew.get("title") or "")[:60],
            "status": bew.get("status", ""),
            "score": score,
        }
        if score is None:
            # Datenluecke, kein Wert. Sie gehoert benannt.
            ohne_stelle.append(eintrag)
            continue
        wert = float(score)
        if wert <= 0:
            # #989: "kein MUSS-Keyword getroffen" ist keine Bewertung.
            ohne_muss.append(eintrag)
            continue
        bewertbar.append(wert)
        je_ausgang.setdefault(eintrag["status"] or "unbekannt", []).append(wert)
        if schwelle is not None and wert < float(schwelle):
            unter_schwelle.append(eintrag)

    ergebnis = {"beworben": kennzahlen(bewertbar)}
    if not ergebnis["beworben"]:
        ergebnis["nachricht"] = (
            "Keine Bewerbung traegt einen auswertbaren Score. Ohne "
            "verknuepfte Stellen gibt es nichts zu verteilen — "
            "bewerbungs_stellen_abgleichen() stellt die Verbindung her.")
        if ohne_stelle:
            ergebnis["ohne_verknuepfte_stelle"] = {
                "anzahl": len(ohne_stelle), "beispiele": ohne_stelle[:5]}
        return ergebnis

    if je_ausgang:
        ergebnis["nach_ausgang"] = {
            status: kennzahlen(werte)
            for status, werte in sorted(je_ausgang.items(),
                                        key=lambda p: -len(p[1]))
        }
    if ohne_muss:
        ergebnis["score_null"] = {
            "anzahl": len(ohne_muss),
            "beispiele": ohne_muss[:5],
            "bedeutung": (
                "Score 0 heisst 'kein MUSS-Keyword getroffen' — die Stelle "
                "wurde nicht inhaltlich schlecht bewertet, sondern gar "
                "nicht beurteilt. Diese Bewerbungen zaehlen deshalb NICHT "
                "in Mittel und Median. Dass du dich trotzdem beworben "
                "hast, ist der eigentliche Befund: die MUSS-Liste deckt "
                "diese Rollen nicht ab."),
        }
    if ohne_stelle:
        ergebnis["ohne_verknuepfte_stelle"] = {
            "anzahl": len(ohne_stelle),
            "beispiele": ohne_stelle[:5],
            "bedeutung": (
                "Diese Bewerbungen haben keine verknuepfte Stelle und damit "
                "keinen Score. Sie sind eine Datenluecke, kein Nullwert — "
                "bewerbungs_stellen_abgleichen() stellt die Verbindung her."),
        }
    if schwelle is not None:
        ergebnis["schwelle"] = float(schwelle)
        if unter_schwelle:
            ergebnis["unter_schwelle"] = {
                "anzahl": len(unter_schwelle),
                "beispiele": unter_schwelle[:10],
                "bedeutung": (
                    f"Diese Bewerbungen lagen unter deiner Schwelle von "
                    f"{float(schwelle):g} — du hast dich also gegen die "
                    "Einschaetzung des Modells beworben. Haeufen sie sich, "
                    "sagt das mehr ueber die Kriterien als ueber die "
                    "Stellen."),
            }
    return ergebnis
