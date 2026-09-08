"""Liegt diese Stelle in einem Rechtsraum, in dem man arbeiten kann? (#996)

Vom Nutzer am 08.09.2026 bemerkt: *"Was habe ich mit US zu tun? Denke das
ist ein Fehler, zumal wir nur deutsche bzw. Quellen fuer den
deutschsprachigen Raum durchsuchen."*

Er hatte recht. In den Suchkriterien standen `regionen: [Hamburg, Wedel,
Schleswig-Holstein, Remote, Deutschland, DACH]` und 30 km
Maximalentfernung — und trotzdem konnten Stellen im Bestand landen, auf
die man sich von Deutschland aus gar nicht bewerben kann.

**Die Ursache lag nicht bei den Quellen, sondern in einer Zeile:**

    if (job.get("remote_level") or "") == "remote":
        return "entfaellt", "Vollstaendig remote — Entfernung ohne Belang."

Fuer eine deutsche Remote-Stelle stimmt das. Fuer eine US-gebundene ist
es falsch — und weil `entfaellt` bedeutet "geht nicht in den Score ein",
bekam so eine Stelle **keinerlei Abzug**.

**"Remote" heisst nicht "von ueberall", sondern "ohne festen Buerositz
INNERHALB eines Rechtsraums".** Eine Rolle mit `locationRestrictions:
['United States']` ist von Hamburg aus nicht *weit weg* — sie ist gar
nicht bewerbbar: keine Arbeitserlaubnis, kein Arbeitsrecht, keine
gemeinsame Kernzeit. Das ist ein k.o., keine Entfernungsfrage.

Derselbe Fehlertyp wie #989, eine Ebene weiter: `entfaellt` ist ein
Nulltarif, und was nichts kostet, steigt in der Sortierung.

**Die Regel ist bewusst ein POSITIVBELEG, kein Verdacht.** Ausgeschlossen
wird nur, wo ein Nicht-DACH-Land ausdruecklich dasteht. Ein Ort wie
"Bedford" oder "Nassau" bleibt `unbekannt` — es gibt deutsche Orte mit
fremd klingenden Namen, und ein falscher Ausschluss ist teurer als ein zu
hoher Score (#827). Drei Zustaende, nicht zwei (#989): `dach`,
`ausserhalb`, `unbekannt`.
"""
from __future__ import annotations

import re

DACH = "dach"
AUSSERHALB = "ausserhalb"
UNBEKANNT = "unbekannt"

# Der eigene Rechtsraum. Staedte stehen hier bewusst NICHT drin — dafuer
# gibt es das Geocoding, das eine echte Entfernung liefert.
DACH_MARKER = (
    "deutschland", "germany", "allemagne", "de-",
    "oesterreich", "österreich", "austria",
    "schweiz", "switzerland", "suisse",
    "dach",
)

# Angaben, die den DACH-Raum EINSCHLIESSEN. Sie sind kein Ausschluss:
# "Europe" oder "Worldwide" umfasst Deutschland, auch wenn daneben
# andere Regionen stehen.
UMFASSEND = (
    "worldwide", "anywhere", "global", "remote worldwide",
    "europe", "european union", "eu", "emea", "europa",
)

# Laender, deren Nennung eine Bewerbung von Deutschland aus praktisch
# ausschliesst. Bewusst eine ueberschaubare Liste der Faelle, die in
# Stellenanzeigen tatsaechlich vorkommen — sie darf wachsen, aber jeder
# Eintrag muss ein LAND sein, nie eine Stadt oder Region.
FREMDE_LAENDER = (
    "united states", "usa", "u.s.", "us only", "us-only", "america",
    "canada", "kanada", "mexico", "brazil", "brasilien", "argentina",
    "colombia", "chile", "peru", "uruguay", "belize", "honduras",
    "dominican republic", "costa rica", "panama", "guatemala",
    "united kingdom", "great britain", "england", "scotland", "ireland",
    "india", "indien", "pakistan", "bangladesh", "philippines",
    "indonesia", "vietnam", "thailand", "malaysia", "singapore",
    "china", "japan", "south korea", "korea", "taiwan",
    "australia", "new zealand", "neuseeland",
    "south africa", "nigeria", "kenya", "egypt", "morocco",
    "israel", "turkey", "tuerkei", "united arab emirates", "uae",
    "romania", "rumaenien", "rumänien", "bulgaria", "bulgarien",
    "poland", "polen", "ukraine", "serbia", "croatia",
    "spain", "spanien", "portugal", "italy", "italien", "france",
    "frankreich", "netherlands", "niederlande", "belgium", "belgien",
    "sweden", "schweden", "norway", "norwegen", "denmark", "daenemark",
    "finland", "finnland", "latam", "apac", "anz",
)

_WORTGRENZE = r"(?<![a-z0-9])%s(?![a-z0-9])"


def _enthaelt(text: str, begriffe) -> list:
    """Welche der Begriffe stehen als eigenes Wort im Text?

    Wortgrenzen sind hier Pflicht: "us" steckt sonst in "Kundenservice",
    "Industrie" und jedem zweiten deutschen Wort — genau die Sorte
    Fehlalarm, die einen Pruefer unbenutzbar macht (#929).
    """
    t = (text or "").lower()
    if not t:
        return []
    return [b for b in begriffe
            if re.search(_WORTGRENZE % re.escape(b), t)]


def einordnen(ort: str) -> tuple:
    """Wo liegt diese Stelle? Gibt `(lage, belege)` zurueck.

    `lage` ist `dach`, `ausserhalb` oder `unbekannt`.

    Die Reihenfolge ist Absicht:
    1. Wird DACH genannt, ist die Sache klar — auch wenn daneben andere
       Laender stehen ("Germany, France" ist bewerbbar).
    2. Eine umfassende Angabe ("Europe", "Worldwide") schliesst DACH ein.
    3. Erst wenn AUSSCHLIESSLICH fremde Laender dastehen, ist es ein
       Ausschluss.
    4. Alles andere bleibt unbekannt. Das ist kein Versaeumnis, sondern
       die ehrliche Auskunft — und sie kostet nichts (#989).
    """
    text = (ort or "").strip()
    if not text:
        return UNBEKANNT, []
    if _enthaelt(text, DACH_MARKER):
        return DACH, []
    if _enthaelt(text, UMFASSEND):
        return DACH, []
    fremde = _enthaelt(text, FREMDE_LAENDER)
    if fremde:
        return AUSSERHALB, fremde
    return UNBEKANNT, []


def ausserhalb(job: dict) -> tuple:
    """Ist diese STELLE erkennbar ausserhalb des erreichbaren Raums?

    Prueft Ort und Remote-Angabe zusammen. Eine Stelle mit berechneter
    Entfernung ist per Definition im Inland — das Geocoding hat sie ja
    aufgeloest — und wird nie ausgeschlossen.

    Returns:
        `(True, belege)` nur bei Positivbeleg, sonst `(False, [])`.
    """
    if not isinstance(job, dict):
        return False, []
    # Eine aufgeloeste Entfernung ist der staerkere Beleg: sie kommt aus
    # echten Koordinaten und schlaegt jede Textdeutung.
    if job.get("distance_km") is not None:
        return False, []
    lage, belege = einordnen(job.get("location") or "")
    if lage == AUSSERHALB:
        return True, belege
    return False, []


def hinweis(belege) -> str:
    """Der Satz, der im Ergebnis steht — konkret statt kategorisch."""
    namen = ", ".join(sorted({b.title() for b in (belege or [])})) or "Ausland"
    return (
        f"Die Stelle ist ausdruecklich an {namen} gebunden. Von "
        "Deutschland aus ist sie nicht 'weit weg', sondern nicht "
        "bewerbbar — Arbeitserlaubnis, Arbeitsrecht und Kernzeit "
        "sprechen dagegen. 'Remote' heisst ohne festen Buerositz "
        "INNERHALB eines Rechtsraums, nicht von ueberall."
    )
