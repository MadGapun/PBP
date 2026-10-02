"""Schutz vor einer Datenbank, die NEUER ist als dieses Programm (#1093, Abschnitt „Fallen“).

Mit dem Auto-Update gibt es einen Zustand, den es vorher kaum gab: zwei Prozesse auf derselben Datenbank
laufen in verschiedenen Fassungen. Claude Desktop hat den MCP-Server vor dem Update gestartet, das
Dashboard danach (oder umgekehrt); die neuere Fassung hat die Datenbank schon umgestellt.

Dann darf die AELTERE nichts mehr schreiben. Das ist keine Vorsicht um der Vorsicht willen, sondern die
Lehre aus `INSERT OR REPLACE` (DoD 8e): ein alter Code kennt die neuen Spalten nicht, schreibt seine Zeile
ohne sie neu, und die neuen Werte sind weg — still, und bei jedem spaeteren Lesen sieht es sauber aus.

Was dieser Schutz tut:

* **Erkennen:** Die in der Datenbank eingetragene Schema-Nummer ist groesser als `SCHEMA_VERSION` dieses
  Programms. Die Frage wird hoechstens alle 15 Sekunden gestellt (eine einzige kleine Abfrage).
* **Werkzeuge (MCP):** jeder Aufruf ausser einer kleinen Liste von Diagnosewerkzeugen wird mit einem
  Satz abgewiesen, der sagt, was zu tun ist.
* **Dashboard:** jeder schreibende Aufruf (POST/PUT/PATCH/DELETE) auf `/api/...` antwortet mit 503 und
  demselben Satz. Lesen bleibt moeglich — man soll sehen koennen, was los ist. Ausgenommen sind die
  Aufrufe, mit denen man das Problem behebt (Update, Sicherungen).
* **Anzeige:** `/api/health` nennt den Zustand, die Oberflaeche zeigt ihn oben als Hinweis.

Der naechste Schritt steht immer dabei: PBP UND Claude Desktop neu starten. Hilft das nicht, ist die
installierte Version aelter als die Datenbank, und die neueste Version von Hand zu installieren ist der Weg.
"""
from __future__ import annotations

import json
import logging
import time

logger = logging.getLogger("bewerbungs_assistent")

#: Wie alt eine Antwort sein darf, bevor die Datenbank neu gefragt wird.
GILT_S = 15.0

#: Diese Werkzeuge bleiben auch bei zu neuer Datenbank erreichbar: sie lesen oder helfen bei der Loesung.
ERLAUBTE_WERKZEUGE = frozenset({
    "pbp_diagnose", "pbp_capabilities", "profil_status", "sicherungen_anzeigen", "pbp_grenze_melden",
    "update_status", "update_einstellungen_setzen", "update_jetzt_installieren",
})
#: Diese schreibenden Aufrufe bleiben erreichbar.
ERLAUBTE_PRAEFIXE = ("/api/auto-update", "/api/health", "/api/sicherungen", "/api/wiederherstellen", "/api/update-check")
SCHREIBENDE_METHODEN = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_STAND = {"zeit": 0.0, "treffer": None, "db": None}


def schema_der_datenbank(db):
    """Die Schema-Nummer, die in der Datenbank steht, oder None, wenn sie sich nicht lesen laesst."""
    try:
        zeile = db.connect().execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
        if zeile is None:
            return None
        return int(str(zeile["value"]).strip().strip('"'))
    except Exception:  # noqa: BLE001 — eine kaputte Abfrage darf nie als "zu neu" gelten
        return None


def hinweis_text(datenbank: int, programm: int) -> str:
    return (f"Die Datenbank gehört zu einer neueren Version von PBP (Datenstand {datenbank}; dieses Programm kennt "
            f"{programm}). Damit nichts beschädigt wird, schreibt dieses PBP vorerst nichts mehr. "
            "Beende PBP und Claude Desktop und starte beides neu – dann läuft die neue Version. "
            "Hilft das nicht, installiere die neueste Version von Hand (INSTALLIEREN.bat).")


def zu_neu(db, *, frisch: bool = False):
    """{'datenbank': n, 'programm': m, 'text': ...} wenn die Datenbank neuer ist als das Programm, sonst None."""
    if db is None:
        return None
    jetzt = time.monotonic()
    if not frisch and _STAND["db"] is db and jetzt - _STAND["zeit"] < GILT_S:
        return _STAND["treffer"]
    from ..database import SCHEMA_VERSION
    n = schema_der_datenbank(db)
    treffer = None
    if n is not None and n > SCHEMA_VERSION:
        treffer = {"datenbank": n, "programm": SCHEMA_VERSION, "text": hinweis_text(n, SCHEMA_VERSION)}
        if _STAND["treffer"] is None:
            logger.warning("Schema-Schutz: Datenbank (Stand %s) ist neuer als dieses Programm (Stand %s) — schreibende "
                           "Aufrufe werden abgewiesen.", n, SCHEMA_VERSION)
    _STAND.update(zeit=jetzt, treffer=treffer, db=db)
    return treffer


def zuruecksetzen() -> None:
    _STAND.update(zeit=0.0, treffer=None, db=None)


def werkzeug_abweisen(db, werkzeug: str):
    """Der Fehlertext (JSON) fuer einen abgewiesenen Werkzeugaufruf, oder None, wenn er durfte."""
    if werkzeug in ERLAUBTE_WERKZEUGE:
        return None
    treffer = zu_neu(db)
    if treffer is None:
        return None
    return json.dumps({"error": "datenbank_zu_neu", "tool": werkzeug, "message": treffer["text"],
                       "datenstand_datenbank": treffer["datenbank"], "datenstand_programm": treffer["programm"]},
                      ensure_ascii=False)


class SchemaSchutzMiddleware:
    """ASGI: schreibende Aufrufe auf `/api/...` bekommen 503, solange die Datenbank neuer ist als das Programm."""

    def __init__(self, app, db_getter=None):
        self.app = app
        self._db_getter = db_getter

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("method") in SCHREIBENDE_METHODEN:
            pfad = scope.get("path", "")
            if pfad.startswith("/api/") and not pfad.startswith(ERLAUBTE_PRAEFIXE):
                db = self._db_getter() if self._db_getter else None
                treffer = zu_neu(db)
                if treffer is not None:
                    body = json.dumps({"error": "datenbank_zu_neu", "message": treffer["text"],
                                       "datenstand_datenbank": treffer["datenbank"],
                                       "datenstand_programm": treffer["programm"]}, ensure_ascii=False).encode("utf-8")
                    await send({"type": "http.response.start", "status": 503,
                                "headers": [(b"content-type", b"application/json; charset=utf-8"),
                                            (b"content-length", str(len(body)).encode())]})
                    await send({"type": "http.response.body", "body": body})
                    return
        await self.app(scope, receive, send)
