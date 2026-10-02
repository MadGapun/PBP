"""MCP-Werkzeuge zum Firmen-Stammsatz (#1080, Stufe 2).

Der Stammsatz fasst bestätigte Schreibweisen einer Firma zusammen und kennt ihre Mutterfirma. Bewerbungen, Stellen, Kontakte und
Lebenslauf behalten ihren Firmennamen als Text; `firma_kontext` liest darüber. Zugeordnet wird nie auf Verdacht: Vorschläge kommen
aus dem Bestand, angelegt wird erst nach Bestätigung des Menschen.
"""
from __future__ import annotations

import logging


def register(mcp, db, logger: logging.Logger):
    """Registriert die Stammsatz-Tools."""

    @mcp.tool()
    def firmen_stamm_anzeigen(firma: str = "") -> dict:
        """Zeigt den Firmen-Stammsatz: Schreibweisen, Mutterfirma, Tochterfirmen (#1080).

        Mit `firma` (Name oder Kennung): der Stammsatz dieser Firma. Ohne: alle Firmen im Stammsatz und wie viele Vorschläge offen
        sind. Die Historie (Bewerbungen, Stellen, Kontakte ...) steht nicht hier, sondern in `firma_kontext`. Liest nur.

        Args:
            firma: Name oder Kennung (fi_...) der Firma. Leer = alle.
        """
        from ..services import firmen_stamm as fs
        if not (firma or "").strip():
            liste = fs.firmen_liste(db)
            offen = fs.vorschlaege(db, maximal=1)["anzahl"]
            return {"anzahl": len(liste), "firmen": liste, "offene_vorschlaege": offen,
                    "hinweis": ("Es gibt noch keinen Stammsatz. " if not liste else "")
                               + (f"{offen} Vorschläge für Firmen mit mehreren Schreibweisen: firmen_vorschlaege_anzeigen." if offen else "")}
        gesucht = firma.strip()
        f = fs.firma_laden(db, gesucht) if gesucht.startswith("fi_") else None
        if f is None:
            r = fs.aufloesen(db, gesucht)
            if r["mehrdeutig"]:
                return {"status": "mehrdeutig", "firmen": r["mehrdeutig"],
                        "text": "Der Name passt zu mehreren Firmen: " + ", ".join(r["mehrdeutig"]) + ". Welche ist gemeint?"}
            f = r["firma"]
        if f is None:
            return {"status": "nicht_gefunden", "text": f"Zu „{gesucht}“ gibt es keinen Stammsatz. Die Historie steht trotzdem in firma_kontext."}
        return {"status": "ok", "firma": f, "historie": f"firma_kontext('{f['name']}')"}

    @mcp.tool()
    def firmen_vorschlaege_anzeigen() -> dict:
        """Zeigt, welche Schreibweisen im Bestand vermutlich dieselbe Firma sind (#1080). Ändert nichts.

        Jeder Vorschlag hat eine Kennung, den Namen zum Anlegen und die übrigen Schreibweisen. Ob es wirklich dieselbe Firma ist,
        entscheidet der Mensch: erst fragen, dann `firmen_stamm_bearbeiten(aktion='vorschlaege_anwenden', auswahl=[...])`.
        """
        from ..services import firmen_stamm as fs
        return fs.vorschlaege(db)

    @mcp.tool()
    def firmen_stamm_bearbeiten(aktion: str, firma_id: str = "", name: str = "", alias: str = "", art: str = "schreibweise",
                                alias_id: int = 0, mutterfirma_id: str = "", quelle_id: str = "", auswahl: list = None,
                                aliase: list = None, branche: str = None, standorte: str = None, notizen: str = None,
                                bestaetigung: bool = False) -> dict:
        """Legt Firmen an und pflegt Schreibweisen, Mutterfirma und Notizen (#1080). Bewerbungen und Stellen bleiben unverändert.

        Aktionen: anlegen | vorschlaege_anwenden | alias_hinzufuegen | alias_entfernen | umbenennen | mutterfirma_setzen |
        felder_setzen | zusammenfuehren | loeschen. `vorschlaege_anwenden`, `zusammenfuehren` und `loeschen` zeigen ohne
        `bestaetigung=True` nur die Vorschau; erst setzen, NACHDEM der Mensch ja gesagt hat.

        Args:
            aktion: Eine der oben genannten.
            firma_id: Die Firma (fi_...), bei zusammenfuehren das ZIEL.
            name: Für anlegen und umbenennen.
            alias: Für alias_hinzufuegen: die Schreibweise.
            art: Für alias_hinzufuegen: schreibweise | frueherer_name | kurzform | bereich.
            alias_id: Für alias_entfernen: die Kennung aus firmen_stamm_anzeigen.
            mutterfirma_id: Für anlegen und mutterfirma_setzen; leer löst die Mutterfirma.
            quelle_id: Für zusammenfuehren: die Firma, die aufgeht und verschwindet.
            auswahl: Für vorschlaege_anwenden: Kennungen aus firmen_vorschlaege_anzeigen.
            aliase: Für anlegen: weitere Schreibweisen.
            branche: Für anlegen und felder_setzen.
            standorte: Für anlegen und felder_setzen.
            notizen: Für anlegen und felder_setzen.
            bestaetigung: True, NACHDEM der Mensch ja gesagt hat.
        """
        from ..services import firmen_stamm as fs
        aktion = (aktion or "").strip().lower()
        erlaubt = ["anlegen", "vorschlaege_anwenden", "alias_hinzufuegen", "alias_entfernen", "umbenennen", "mutterfirma_setzen",
                   "felder_setzen", "zusammenfuehren", "loeschen"]
        if aktion not in erlaubt:
            return {"status": "fehler", "text": f"Unbekannte Aktion „{aktion}“.", "erlaubt": erlaubt}
        try:
            if aktion == "anlegen":
                return fs.firma_anlegen(db, name, mutterfirma_id=mutterfirma_id, branche=branche or "", standorte=standorte or "",
                                        notizen=notizen or "", aliase=aliase or [])
            if aktion == "vorschlaege_anwenden":
                return fs.vorschlaege_anwenden(db, auswahl, bestaetigt=bestaetigung is True)
            if aktion == "alias_hinzufuegen":
                return fs.alias_hinzufuegen(db, firma_id, alias, art)
            if aktion == "alias_entfernen":
                return fs.alias_entfernen(db, firma_id, alias_id)
            if aktion == "umbenennen":
                return fs.umbenennen(db, firma_id, name)
            if aktion == "mutterfirma_setzen":
                return fs.mutterfirma_setzen(db, firma_id, mutterfirma_id)
            if aktion == "felder_setzen":
                felder = {k: v for k, v in (("branche", branche), ("standorte", standorte), ("notizen", notizen)) if v is not None}
                if not felder:
                    return {"status": "fehler", "text": "Nichts zu setzen: nenne branche, standorte oder notizen."}
                return fs.firma_bearbeiten(db, firma_id, **felder)
            if aktion == "zusammenfuehren":
                ziel, quelle = fs.firma_laden(db, firma_id), fs.firma_laden(db, quelle_id)
                if ziel is None or quelle is None:
                    return {"status": "nicht_gefunden", "text": "Ziel oder Quelle gibt es nicht (mehr)."}
                if bestaetigung is not True:
                    return {"status": "bestaetigung_noetig", "ziel": ziel["name"], "quelle": quelle["name"],
                            "text": (f"„{quelle['name']}“ ginge in „{ziel['name']}“ auf: Name und {len(quelle['aliase'])} Schreibweisen wandern "
                                     "zum Ziel, die Quelle verschwindet. Bewerbungen und Stellen bleiben unverändert."),
                            "naechster_schritt": "Den Menschen fragen. Nur bei einem Ja: dasselbe mit bestaetigung=True."}
                return fs.zusammenfuehren(db, firma_id, quelle_id)
            # loeschen
            f = fs.firma_laden(db, firma_id)
            if f is None:
                return {"status": "nicht_gefunden", "text": "Diese Firma gibt es nicht (mehr)."}
            if bestaetigung is not True:
                return {"status": "bestaetigung_noetig", "firma": f["name"],
                        "text": (f"Der Stammsatz „{f['name']}“ mit {len(f['aliase'])} Schreibweisen würde gelöscht. Bewerbungen, Stellen, Kontakte "
                                 "und Lebenslauf bleiben unverändert."),
                        "naechster_schritt": "Den Menschen fragen. Nur bei einem Ja: dasselbe mit bestaetigung=True."}
            return fs.firma_loeschen(db, firma_id)
        except Exception as exc:  # noqa: BLE001 — eine Fehlermeldung ist besser als ein Absturz im Chat
            logger.exception("firmen_stamm_bearbeiten(%s) fehlgeschlagen", aktion)
            return {"status": "fehler", "text": f"Das hat nicht geklappt: {exc}"}
