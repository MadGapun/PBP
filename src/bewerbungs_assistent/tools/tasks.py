"""Task/Todo-System pro Bewerbung (#666, D19, beta.85).

Vier Tools:
  todo_anlegen(bewerbung_id, titel, faellig_am=None, ...)
  todo_erledigen(todo_id, notiz="")
  todo_reaktivieren(todo_id)
  todos_anzeigen(bewerbung_id=None, nur_offen=False)

Generalisierung der Follow-up-Idee. Tasks haben einen Typ
(custom/nachfass/termin/vorbereitung) und einen Status
(offen/erledigt/hinfaellig). Faellig_am ist optional — Tasks
ohne Faelligkeit tauchen nicht in "Offene Aktionen" auf.

Die bestehende `follow_ups`-Tabelle bleibt unangetastet. Tasks ist
eine eigene Schicht — wer den klassischen Nachfass-Flow nutzen will,
geht weiter ueber nachfass_planen. Wer freie Todos pro Bewerbung
will, nutzt todo_anlegen.
"""

from ..services.nutzerfuehrung import leer


def register(mcp, db, logger):
    """Registriert Task/Todo-Tools."""

    # v1.7.17 (#915): Wall-Clock-Budget gegen stille 4-Minuten-Haenger.
    from ..services.tool_budget import mit_budget as _mit_budget

    @mcp.tool()
    @_mit_budget("todo_anlegen", lese_tool="todos_anzeigen")
    def todo_anlegen(
        titel: str,
        bewerbung_id: str = "",
        faellig_am: str = "",
        beschreibung: str = "",
        typ: str = "custom",
    ) -> dict:
        """Legt einen Todo/Task an (#666, D19).

        v1.7.12 (#815, D35): bewerbung_id ist OPTIONAL — auch Aufgaben
        ohne Bewerbungsbezug ("Lebenslauf-Variante aktualisieren",
        "Suchkriterien nachschaerfen") sind regulaere Datensaetze. Vorher
        landeten sie in Notizen, Chats oder gar nicht: 5 Aufgaben auf 94
        Bewerbungen war kein Nutzungsmuster, sondern ein Zugangsproblem.

        Args:
            titel: Kurzer Titel (z.B. "Gehalt recherchieren",
                "Referenzen zusammenstellen")
            bewerbung_id: Optional — ID der Bewerbung (aus
                bewerbungen_anzeigen). Leer = freie Aufgabe am Profil.
            faellig_am: Optional. YYYY-MM-DD. Mit Faelligkeit erscheint
                der Task in "Offene Aktionen" / im Kalender.
            beschreibung: Optionaler Langtext (Notizen, Checkliste).
            typ: custom (Default) | nachfass | termin | vorbereitung.
                Unbekannte Werte werden auf 'custom' normalisiert.
        """
        app = None
        if bewerbung_id:
            app = db.get_application(bewerbung_id)
            if not app:
                return {"fehler": "Bewerbung nicht gefunden. Pruefe ID mit bewerbungen_anzeigen()."}
        if not (titel or "").strip():
            return {"fehler": "titel ist Pflicht."}
        try:
            tid = db.add_task({
                "application_id": bewerbung_id or None,
                "titel": titel,
                "faellig_am": faellig_am or None,
                "beschreibung": beschreibung or "",
                "typ": typ or "custom",
            })
        except ValueError as exc:
            return {"fehler": str(exc)}
        result = {
            "status": "angelegt",
            "task_id": tid,
            "titel": titel,
            "faellig_am": faellig_am or None,
            "typ": typ or "custom",
            "hinweis": (
                "Task ist offen. Mit todo_erledigen(task_id, notiz='...') "
                "abhaken oder mit todo_reaktivieren wieder oeffnen."
            ),
        }
        if app:
            result["bewerbung"] = app.get("title", "")
            result["firma"] = app.get("company", "")
        else:
            result["bewerbungsbezug"] = "keiner (freie Aufgabe)"
        return result

    @mcp.tool()
    def todo_erledigen(todo_id: str, notiz: str = "") -> dict:
        """Markiert einen Todo als erledigt (#666, D19).

        Args:
            todo_id: ID des Todos (aus todos_anzeigen / todo_anlegen)
            notiz: Optionale Abschluss-Notiz (z.B. "Recruiter hat angerufen")
        """
        task = db.get_task(todo_id)
        if not task:
            return {"fehler": "Todo nicht gefunden."}
        if task.get("status") == "erledigt":
            return {
                "status": "bereits_erledigt",
                "task_id": todo_id,
                "erledigt_am": task.get("erledigt_am"),
            }
        try:
            db.complete_task(todo_id, status="erledigt", notiz=notiz)
        except ValueError as exc:
            return {"fehler": str(exc)}
        return {
            "status": "erledigt",
            "task_id": todo_id,
            "titel": task.get("titel", ""),
            "notiz": notiz or None,
        }

    @mcp.tool()
    def todo_reaktivieren(todo_id: str) -> dict:
        """Setzt einen erledigten/hinfaelligen Todo wieder auf offen."""
        task = db.get_task(todo_id)
        if not task:
            return {"fehler": "Todo nicht gefunden."}
        if task.get("status") == "offen":
            return {"status": "bereits_offen", "task_id": todo_id}
        db.reopen_task(todo_id)
        return {
            "status": "offen",
            "task_id": todo_id,
            "vorher": task.get("status"),
        }

    @mcp.tool()
    def todo_bearbeiten(
        todo_id: str,
        titel: str = "",
        beschreibung: str = "",
        faellig_am: str = "",
        typ: str = "",
    ) -> dict:
        """v1.7.12 (#814, D35): aendert einen bestehenden Todo.

        Vorher gab es KEINEN Weg, ein Faelligkeitsdatum zu aendern —
        follow_up_verschieben existierte, das Todo-Pendant nicht. Nur
        uebergebene Felder werden geschrieben.

        Args:
            todo_id: ID des Todos.
            titel/beschreibung/faellig_am/typ: neue Werte (leer = keine
                Aenderung). faellig_am='-' loescht die Faelligkeit.
        """
        task = db.get_task(todo_id)
        if not task:
            return {"fehler": "Todo nicht gefunden."}
        daten = {}
        if titel.strip():
            daten["titel"] = titel.strip()
        if beschreibung:
            daten["beschreibung"] = beschreibung
        if faellig_am:
            daten["faellig_am"] = None if faellig_am == "-" else faellig_am
        if typ:
            daten["typ"] = typ
        if not daten:
            return {"fehler": "Keine Aenderungen angegeben."}
        db.update_task(todo_id, daten)
        neu = db.get_task(todo_id)
        return {"status": "aktualisiert", "task_id": todo_id,
                "titel": neu.get("titel"), "faellig_am": neu.get("faellig_am"),
                "typ": neu.get("typ")}

    @mcp.tool()
    def todo_hinfaellig(todo_id: str, grund: str = "") -> dict:
        """v1.7.12 (#814, D35): markiert einen Todo als hinfaellig.

        Der Status existierte laengst (todo_reaktivieren nennt ihn) —
        es gab nur kein Tool, das ihn setzt. Hinfaellig heisst: die
        Aufgabe ist gegenstandslos geworden (Absage erhalten, Nachfass
        hat sich erledigt), nicht erledigt.
        """
        task = db.get_task(todo_id)
        if not task:
            return {"fehler": "Todo nicht gefunden."}
        db.complete_task(todo_id, status="hinfaellig", notiz=grund)
        return {"status": "hinfaellig", "task_id": todo_id,
                "titel": task.get("titel"), "grund": grund or None}

    @mcp.tool()
    def todo_details(todo_id: str) -> dict:
        """v1.7.12 (#814, D35): Todo samt aufgeloestem Kontext in EINEM
        Aufruf — Bewerbung, Termine, Kontakte, Dokumente.

        Wer eine Aufgabe oeffnet, will handeln: Mailadresse, Termin und
        Sachstand gehoeren in dieselbe Ansicht, ohne vorher in die
        Bewerbung wechseln zu muessen.
        """
        task = db.get_task(todo_id)
        if not task:
            return {"fehler": "Todo nicht gefunden."}
        result = {"status": "ok", "todo": task}
        aid = task.get("application_id")
        if aid:
            app = db.get_application(aid)
            if app:
                result["bewerbung"] = {
                    "id": aid, "firma": app.get("company"),
                    "stelle": app.get("title"),
                    "status": app.get("status"),
                    "ansprechpartner": app.get("ansprechpartner"),
                    "kontakt_email": app.get("kontakt_email"),
                }
                try:
                    result["termine"] = [
                        {"id": m.get("id"), "datum": m.get("meeting_date"),
                         "titel": m.get("title"),
                         "plattform": m.get("platform"),
                         "status": m.get("status")}
                        for m in (db.get_meetings_for_application(aid) or [])
                    ]
                except Exception:
                    pass
                try:
                    result["kontakte"] = [
                        {"id": k.get("id"), "name": k.get("full_name"),
                         "firma": k.get("company"),
                         "rolle": k.get("link_role") or k.get("position"),
                         "email": k.get("email"), "telefon": k.get("phone")}
                        for k in (db.get_contacts_for_target(
                            "application", aid) or [])
                    ]
                except Exception:
                    pass
                try:
                    docs = db.get_documents_for_application(aid)
                    result["dokumente"] = [
                        {"id": d.get("id"), "dateiname": d.get("filename"),
                         "typ": d.get("doc_type")} for d in (docs or [])
                    ]
                except Exception:
                    pass
        else:
            result["bewerbungsbezug"] = "keiner (freie Aufgabe)"
        return result

    @mcp.tool()
    def aufgaben_uebersicht(
        status: str = "offen",
        bis_datum: str = "",
    ) -> dict:
        """v1.7.12 (#815, D35): ALLE drei Aufgaben-Toepfe in einer Sicht.

        Todos, Nachfassungen (follow_ups) und anstehende Termine sind
        fuer den Nutzer dasselbe — "was muss ich tun" — fuer das System
        aber drei Tabellen mit drei Tool-Familien. Diese Sicht vereint
        sie mit `herkunft`-Feld und gruppiert nach Faelligkeit
        (ueberfaellig / heute / diese_woche / spaeter / ohne_faelligkeit).

        Belegt, warum das zaehlt: die beiden am laengsten festhaengenden
        Bewerbungen des Bestands waren exakt die mit den aeltesten
        ueberfaelligen, UNSICHTBAREN Nachfassungen.

        Args:
            status: 'offen' (Default) | 'erledigt' | 'alle'.
            bis_datum: Optional YYYY-MM-DD — nur Eintraege bis dahin.
        """
        from datetime import date, timedelta
        heute = date.today().isoformat()
        wochenende = (date.today() + timedelta(days=7)).isoformat()

        eintraege = []

        # Topf 1: Todos
        for t in db.list_tasks(nur_offen=(status == "offen")):
            if status == "erledigt" and t.get("status") != "erledigt":
                continue
            app = db.get_application(t.get("application_id") or "") or {}
            eintraege.append({
                "herkunft": "todo", "id": t["id"],
                "titel": t.get("titel", ""),
                "beschreibung": t.get("beschreibung") or "",
                "status": t.get("status"),
                "faellig_am": t.get("faellig_am"),
                "bewerbung_id": t.get("application_id"),
                "firma": app.get("company"),
            })

        # Topf 2: Nachfassungen
        try:
            if status in ("offen", "alle"):
                for fu in db.get_pending_follow_ups():
                    app = db.get_application(
                        fu.get("application_id") or "") or {}
                    eintraege.append({
                        "herkunft": "nachfass", "id": fu.get("id"),
                        "titel": (f"Nachfassen: {app.get('company', '?')}"
                                  f" — {app.get('title', '?')}"),
                        "beschreibung": fu.get("template") or "",
                        "status": "offen",
                        "faellig_am": fu.get("scheduled_date"),
                        "bewerbung_id": fu.get("application_id"),
                        "firma": app.get("company"),
                    })
        except Exception:
            pass

        # Topf 3: anstehende Termine (naechste 30 Tage)
        try:
            if status in ("offen", "alle"):
                horizont = (date.today() + timedelta(days=30)).isoformat()
                for m in db.get_upcoming_meetings(days=30):
                    eintraege.append({
                        "herkunft": "termin", "id": m.get("id"),
                        "titel": m.get("title") or "Termin",
                        "beschreibung": m.get("notes") or "",
                        "status": "geplant",
                        "faellig_am": (m.get("meeting_date") or "")[:10],
                        "bewerbung_id": m.get("application_id"),
                        "firma": m.get("app_company") or m.get("company"),
                    })
                _ = horizont
        except Exception:
            pass

        if bis_datum:
            eintraege = [e for e in eintraege
                         if (e.get("faellig_am") or "9999") <= bis_datum]

        gruppen = {"ueberfaellig": [], "heute": [], "diese_woche": [],
                   "spaeter": [], "ohne_faelligkeit": []}
        for e in sorted(eintraege,
                        key=lambda x: x.get("faellig_am") or "9999-12-31"):
            f = e.get("faellig_am")
            if not f:
                gruppen["ohne_faelligkeit"].append(e)
            elif f < heute and e.get("herkunft") != "termin":
                e["ueberfaellig_seit_tagen"] = (
                    date.today() - date.fromisoformat(f[:10])).days
                gruppen["ueberfaellig"].append(e)
            elif f[:10] == heute:
                gruppen["heute"].append(e)
            elif f <= wochenende:
                gruppen["diese_woche"].append(e)
            else:
                gruppen["spaeter"].append(e)

        return {
            "status": "ok",
            "anzahl": len(eintraege),
            "ueberfaellig_anzahl": len(gruppen["ueberfaellig"]),
            "gruppen": gruppen,
            "hinweis": (
                "Bedienen: todo_erledigen/todo_hinfaellig/todo_bearbeiten "
                "fuer Todos, follow_up_erledigen/-verschieben/-bearbeiten "
                "fuer Nachfassungen, meeting_bearbeiten fuer Termine."
            ),
        }

    @mcp.tool()
    def todos_anzeigen(
        bewerbung_id: str = "",
        nur_offen: bool = False,
    ) -> dict:
        """Listet Todos (#666, D19).

        Args:
            bewerbung_id: Optional. Wenn leer: alle Todos des aktiven Profils.
            nur_offen: True = nur status='offen'. Default False (alle).
        """
        tasks = db.list_tasks(
            application_id=bewerbung_id or None,
            nur_offen=nur_offen,
        )
        if not tasks:
            # v1.7.21 (#927): "anzahl: 0" beantwortet nicht die Frage,
            # die der Nutzer wirklich hat — was kann ich hier tun?
            return leer(
                {"status": "ok", "anzahl": 0, "todos": []},
                "Noch keine Aufgaben erfasst.",
                "Aufgaben sorgen dafuer, dass nichts untergeht — etwa "
                "Unterlagen nachreichen oder nach zwei Wochen nachfassen. "
                "Anlegen mit todo_anlegen('Was ist zu tun?'); mit "
                "faellig_am='JJJJ-MM-TT' erscheint die Aufgabe "
                "rechtzeitig im Dashboard.")
        return {
            "status": "ok",
            "anzahl": len(tasks),
            "todos": [
                {
                    "id": t["id"],
                    "bewerbung_id": t["application_id"],
                    "titel": t.get("titel", ""),
                    "typ": t.get("typ", "custom"),
                    "status": t.get("status", "offen"),
                    "faellig_am": t.get("faellig_am"),
                    "beschreibung": t.get("beschreibung") or "",
                    "erledigt_am": t.get("erledigt_am"),
                    "notiz": t.get("notiz") or "",
                }
                for t in tasks
            ],
        }
