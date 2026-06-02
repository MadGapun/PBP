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


def register(mcp, db, logger):
    """Registriert Task/Todo-Tools."""

    @mcp.tool()
    def todo_anlegen(
        bewerbung_id: str,
        titel: str,
        faellig_am: str = "",
        beschreibung: str = "",
        typ: str = "custom",
    ) -> dict:
        """Legt einen Todo/Task fuer eine Bewerbung an (#666, D19).

        Args:
            bewerbung_id: ID der Bewerbung (aus bewerbungen_anzeigen)
            titel: Kurzer Titel (z.B. "Gehalt recherchieren",
                "Referenzen zusammenstellen")
            faellig_am: Optional. YYYY-MM-DD. Mit Faelligkeit erscheint
                der Task in "Offene Aktionen" / im Kalender.
            beschreibung: Optionaler Langtext (Notizen, Checkliste).
            typ: custom (Default) | nachfass | termin | vorbereitung.
                Unbekannte Werte werden auf 'custom' normalisiert.
        """
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden. Pruefe ID mit bewerbungen_anzeigen()."}
        if not (titel or "").strip():
            return {"fehler": "titel ist Pflicht."}
        try:
            tid = db.add_task({
                "application_id": bewerbung_id,
                "titel": titel,
                "faellig_am": faellig_am or None,
                "beschreibung": beschreibung or "",
                "typ": typ or "custom",
            })
        except ValueError as exc:
            return {"fehler": str(exc)}
        return {
            "status": "angelegt",
            "task_id": tid,
            "bewerbung": app.get("title", ""),
            "firma": app.get("company", ""),
            "titel": titel,
            "faellig_am": faellig_am or None,
            "typ": typ or "custom",
            "hinweis": (
                "Task ist offen. Mit todo_erledigen(task_id, notiz='...') "
                "abhaken oder mit todo_reaktivieren wieder oeffnen."
            ),
        }

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
