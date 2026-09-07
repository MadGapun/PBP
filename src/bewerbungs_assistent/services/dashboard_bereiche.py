"""Welche Bloecke auf dem Dashboard stehen — und in welcher Reihenfolge.

Nutzerwunsch vom 07.09.2026, nach dem Umbau aus Epic #978:

> *"Vielleicht eine Moeglichkeit, aehnlich wie du das beim Schnellzugriff
> mit den Prompts gemacht hast, dass man Infobereiche an- und abschalten
> kann, hier aber auch sortieren, um sich sein eigenes Dashboard
> zusammenzubasteln. Im Standard waeren dann 'offen' und
> 'Schnellzugriff'."*

Dahinter steckt dieselbe Beobachtung, die schon das Epic ausgeloest hat:
was fuer den einen der wichtigste Block ist, nimmt beim anderen nur
Platz weg. *"Hier nimmt es viel Platz fuer wenig Inhalt"* — ueber den
Recap-Block, der aus einer einzigen Kennzahl bestand.

Statt das fuer alle zu entscheiden, entscheidet es jeder selbst. Der
Katalog gibt die Voreinstellung; abweichen darf man in drei Richtungen:

* **sichtbar** — der Block erscheint ueberhaupt
* **offen** — er ist ausgeklappt oder nur eine Zeile mit Titel
* **reihenfolge** — wo er steht

Genau wie beim Prompt-Katalog (#979) liegt die Auswahl in
`profile_settings` und ueberlebt Update und Neustart; wer nie etwas
einstellt, bekommt die Voreinstellung.

Genau ein Bereich hat `fest=True`: der Block "Offen". Ein Dashboard, auf
dem man das Faellige abschalten kann, waere kein Dashboard mehr.
Einklappen darf man ihn trotzdem — wer nichts offen hat, sieht dann eine
Zeile statt eines Rahmens.

Die Onboarding-Hinweise (G11/#652) stehen bewusst NICHT im Katalog: sie
haben ihr eigenes Wegklicken je Hinweis und wuerden hier eine zweite,
gröbere Abschaltung bekommen. Wer sie vor dem ersten Profil abschaltet,
sitzt in einer Sackgasse (G23/#927).
"""

EINSTELLUNG = "dashboard_bereiche"

# `id`                stabil, die Nutzereinstellung zeigt darauf
# `titel`             Ueberschrift im Einklapp-Zustand und im Zahnrad
# `beschreibung`      was der Block zeigt (nur im Zahnrad)
# `standard_sichtbar` an, solange der Nutzer nichts anderes sagt
# `standard_offen`    ausgeklappt, solange nichts anderes gesagt ist
# `fest`              darf nicht abgeschaltet werden (Einklappen geht)
BEREICHE: tuple[dict, ...] = (
    {"id": "impuls", "titel": "Heute für dich",
     "beschreibung": "Ein Satz pro Tag, passend zu deiner Lage",
     "standard_sichtbar": True, "standard_offen": True},
    {"id": "offen", "titel": "Offen",
     "beschreibung": "Überfälliges, Fälliges, Termine — deine Liste",
     "standard_sichtbar": True, "standard_offen": True, "fest": True},
    {"id": "naechster_schritt", "titel": "Nächster sinnvoller Schritt",
     "beschreibung": "Eine Aussage, eine Aktion — je nach Stand",
     "standard_sichtbar": True, "standard_offen": True},
    {"id": "kennzahlen", "titel": "Kennzahlen",
     "beschreibung": "Bewerbungen, Rhythmus, Gehaltsspanne",
     "standard_sichtbar": True, "standard_offen": True},
    {"id": "schnellzugriff", "titel": "Schnellzugriff",
     "beschreibung": "Prompt-Karten für Claude Desktop",
     "standard_sichtbar": True, "standard_offen": True},
    {"id": "top_stellen", "titel": "Top-Stellen",
     "beschreibung": "Die bestbewerteten Treffer und der Zustand der Quellen",
     "standard_sichtbar": True, "standard_offen": True},
    {"id": "import", "titel": "Dokumente importieren",
     "beschreibung": "Ablagefläche für Unterlagen und E-Mails",
     "standard_sichtbar": True, "standard_offen": False},
    # Aus einer einzigen Kennzahl bestehend — deshalb aus, nicht weg.
    # Was sich getan hat, steht seit v1.7.35 als Marke an den Zeilen im
    # Block "Offen"; dieser Block ist die ausfuehrliche Fassung fuer
    # alle, die sie wollen.
    {"id": "recap", "titel": "Was hat sich getan?",
     "beschreibung": "Aktivität seit deinem letzten Besuch",
     "standard_sichtbar": False, "standard_offen": False},
    # Diese beiden gehoeren fachlich woanders hin (Nutzerhinweis
    # 07.09.2026: E-Mails in den Docs-Bereich, Gelerntes zu den
    # Statistiken — "ist keine Funktion drin"). Bis der Umzug steht,
    # bleiben sie hier waehlbar statt ersatzlos zu verschwinden: eine
    # Funktion ohne neue Heimat zu loeschen waere schlechter als eine,
    # die man einschalten kann.
    {"id": "emails", "titel": "E-Mails",
     "beschreibung": "Letzte importierte Nachrichten — zieht in den Docs-Bereich um",
     "standard_sichtbar": False, "standard_offen": False},
    {"id": "gelernt", "titel": "Was PBP gelernt hat",
     "beschreibung": "Erkannte Muster — ziehen zu den Statistiken um",
     "standard_sichtbar": False, "standard_offen": False},
)

_NACH_ID = {b["id"]: b for b in BEREICHE}


def standard() -> list[dict]:
    """Die Voreinstellung als vollstaendige Zustandsliste."""
    return [
        {"id": b["id"], "sichtbar": bool(b.get("standard_sichtbar")),
         "offen": bool(b.get("standard_offen"))}
        for b in BEREICHE
    ]


def bereich(bereich_id: str) -> dict | None:
    return _NACH_ID.get(bereich_id)


def _zusammenfuehren(gespeichert) -> list[dict]:
    """Gespeicherten Zustand mit dem Katalog abgleichen.

    Zwei Faelle, die im Betrieb wirklich vorkommen:

    * Ein Bereich ist neu dazugekommen — er haengt hinten an, mit seiner
      Voreinstellung. Sonst saehe ein Bestandsnutzer neue Bloecke nie.
    * Ein gespeicherter Bereich gibt es nicht mehr — er faellt weg,
      statt eine leere Zeile zu erzeugen.
    """
    ergebnis = []
    gesehen = set()
    for eintrag in gespeichert:
        if not isinstance(eintrag, dict):
            continue
        bid = str(eintrag.get("id") or "")
        katalog = _NACH_ID.get(bid)
        if not katalog or bid in gesehen:
            continue
        gesehen.add(bid)
        ergebnis.append({
            "id": bid,
            # Feste Bereiche lassen sich nicht abschalten — auch dann
            # nicht, wenn in den Einstellungen etwas anderes steht (etwa
            # aus einer Version, in der sie noch abschaltbar waren).
            "sichtbar": True if katalog.get("fest")
                        else bool(eintrag.get("sichtbar", True)),
            "offen": bool(eintrag.get("offen", katalog.get("standard_offen"))),
        })
    for b in BEREICHE:
        if b["id"] not in gesehen:
            ergebnis.append({
                "id": b["id"],
                "sichtbar": bool(b.get("standard_sichtbar")),
                "offen": bool(b.get("standard_offen")),
            })
    return ergebnis


def zustand(db) -> list[dict]:
    """Die Bereiche in der Reihenfolge dieses Nutzers."""
    try:
        roh = db.get_profile_setting(EINSTELLUNG, None)
    except Exception:
        roh = None
    if not isinstance(roh, list) or not roh:
        return standard()
    return _zusammenfuehren(roh)


def setzen(db, eintraege) -> dict:
    """Reihenfolge und Sichtbarkeit speichern.

    Der gespeicherte Zustand wird immer erst durch `_zusammenfuehren`
    gedreht: so kann eine Oberflaeche eine unvollstaendige Liste
    schicken, ohne dass Bereiche verschwinden.
    """
    if not isinstance(eintraege, list):
        raise ValueError("bereiche muss eine Liste sein")
    unbekannt = [str(e.get("id")) for e in eintraege
                 if isinstance(e, dict) and str(e.get("id")) not in _NACH_ID]
    zusammen = _zusammenfuehren(eintraege)
    db.set_profile_setting(EINSTELLUNG, zusammen)
    return {"bereiche": zusammen, "unbekannt": unbekannt}


def zuruecksetzen(db) -> list[dict]:
    db.set_profile_setting(EINSTELLUNG, standard())
    return standard()


def katalog() -> list[dict]:
    """Alle Bereiche mit Titel und Beschreibung — fuer das Zahnrad."""
    return [dict(b) for b in BEREICHE]
