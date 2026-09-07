"""#980 (D42): das Frontend darf keine Route rufen, die es nicht gibt.

Zwei Praxisfunde vom 06.09.2026, beide im Aufgaben-Tab, beide seit
v1.7.12 im Code:

* `POST /api/follow-ups/{id}/reschedule` — existiert nicht. Das
  Verschieben einer Nachfassung endete in HTTP 404 und hat nie
  funktioniert.
* `POST /api/follow-ups/{id}/obsolete` — existiert ebenfalls nicht,
  hatte aber einen `catch`-Fallback auf `.../complete`. Wer eine
  Nachfassung als hinfaellig markierte, speicherte sie damit still als
  ERLEDIGT. Kein Fehler, falscher Datensatz, und die Zeile zaehlte
  danach in den Reaktionszeiten (D29) als durchgefuehrte Nachfassung.

Die gemeinsame Wurzel ist nicht Unachtsamkeit, sondern eine fehlende
Kontrolle: das Frontend nennt API-Pfade als Zeichenketten, und nichts
vergleicht sie mit dem, was der Server registriert hat. Fuer Tab-IDs
(G19/#846), Status-Werte und Subnav-Eintraege (G20/#896) gibt es genau
solche Guards. Fuer Routen fehlte er.

Zum Vergleich: ein Frontend-Segment passt auf ein Server-Segment, wenn
beide gleich sind ODER das Server-Segment ein Pfadparameter ist ODER das
Frontend-Segment eine Variable enthaelt. Die letzte Regel ist bewusst
grosszuegig — ein `${...}` kann zur Laufzeit alles werden, und ein
Waechter, der bei korrektem Code Alarm gibt, wird nach dem zweiten Mal
ignoriert (Telefon-Lehre vom 07.08.).
"""
import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "frontend" / "src"

# Pfade, die bewusst nicht an diese FastAPI-App gehen: Ollama spricht
# unter denselben Praefixen, wird aber direkt beim Nutzer angesprochen.
AUSNAHMEN = {
    "/api/tags", "/api/generate", "/api/chat",
    "/api/version", "/api/show", "/api/ps",
}

_QUOTES = "\"'`"


def _strings_mit_api(text: str) -> list[str]:
    """Alle Zeichenketten-Literale, die mit /api/ beginnen.

    Von Hand statt per Regex, weil ein Template-String `${...}`-Ausdruecke
    mit Anfuehrungszeichen und Fragezeichen enthaelt — ein
    `/api/tasks/${id}/${done ? "reopen" : "complete"}` zerreisst jede
    naive Regex genau an der Stelle, an der es interessant wird.
    """
    treffer = []
    i = 0
    while True:
        i = text.find("/api/", i)
        if i < 0:
            return treffer
        # Steht direkt davor ein Anfuehrungszeichen? Sonst ist es Prosa.
        if i == 0 or text[i - 1] not in _QUOTES:
            i += 5
            continue
        quote = text[i - 1]
        j, tiefe = i, 0
        while j < len(text):
            c = text[j]
            if c == "\\":
                j += 2
                continue
            if text.startswith("${", j):
                tiefe += 1
                j += 2
                continue
            if c == "}" and tiefe:
                tiefe -= 1
                j += 1
                continue
            if not tiefe and (c == quote or c == "\n"):
                break
            j += 1
        treffer.append(text[i:j])
        i = j


def _segmente(pfad: str) -> tuple[str, ...]:
    """Pfad in vergleichbare Segmente zerlegen.

    Query-String faellt weg, Segmente mit `${...}` werden zum
    Platzhalter `{}`.
    """
    # Query nur ausserhalb eines ${...} abschneiden.
    ohne_query, tiefe = [], 0
    for k, c in enumerate(pfad):
        if pfad.startswith("${", k):
            tiefe += 1
        elif c == "}" and tiefe:
            tiefe -= 1
        elif c in "?#" and not tiefe:
            break
        ohne_query.append(c)
    roh = "".join(ohne_query).rstrip("/")

    teile = []
    for segment in roh.split("/"):
        teile.append("{}" if "${" in segment else segment)
    return tuple(teile)


def _server_routen() -> list[tuple[str, ...]]:
    from bewerbungs_assistent.dashboard import app

    routen = []
    for route in app.routes:
        pfad = getattr(route, "path", "") or ""
        if not pfad.startswith("/api/"):
            continue
        routen.append(tuple(
            "{}" if s.startswith("{") else s
            for s in pfad.rstrip("/").split("/")))
    return routen


def _passt(gerufen: tuple[str, ...], route: tuple[str, ...]) -> bool:
    if len(gerufen) != len(route):
        return False
    return all(a == b or b == "{}" or a == "{}"
               for a, b in zip(gerufen, route))


def _frontend_pfade() -> dict[tuple[str, ...], set[str]]:
    gefunden: dict[tuple, set[str]] = {}
    for datei in list(FRONTEND.rglob("*.jsx")) + list(FRONTEND.rglob("*.js")):
        if datei.name.endswith(".test.mjs"):
            continue
        text = datei.read_text(encoding="utf-8", errors="replace")
        for roh in _strings_mit_api(text):
            if roh.split("?")[0].rstrip("/") in AUSNAHMEN:
                continue
            gefunden.setdefault(_segmente(roh), set()).add(
                str(datei.relative_to(WURZEL)).replace("\\", "/"))
    return gefunden


def test_980_jeder_gerufene_pfad_existiert_am_server():
    """Der eigentliche Guard — er haette beide Funde sofort gemeldet."""
    routen = _server_routen()
    unbekannt = {
        "/".join(pfad): sorted(dateien)
        for pfad, dateien in _frontend_pfade().items()
        if not any(_passt(pfad, r) for r in routen)
    }
    assert not unbekannt, (
        "Das Frontend ruft Routen, die der Server nicht kennt:\n"
        + "\n".join(f"  {p}  <- {', '.join(d)}"
                    for p, d in sorted(unbekannt.items()))
    )


def test_980_der_guard_findet_eine_erfundene_route():
    """Gegenprobe: ein Waechter, der nie anschlaegt, beweist nichts."""
    routen = _server_routen()
    for erfunden in ("/api/follow-ups/${id}/obsolete",
                     "/api/follow-ups/${id}/reschedule",
                     "/api/gibt-es-nicht"):
        assert not any(_passt(_segmente(erfunden), r) for r in routen), erfunden


def test_980_die_richtigen_routen_gibt_es():
    routen = _server_routen()
    for pfad in ("/api/follow-ups/${id}/dismiss",
                 "/api/follow-ups/${id}",
                 "/api/follow-ups/${id}/complete"):
        assert any(_passt(_segmente(pfad), r) for r in routen), pfad


def _ohne_kommentare(quelltext: str) -> str:
    """Zeilenkommentare entfernen.

    Sonst schlaegt der Test an der Erklaerung an, warum die falsche Route
    entfernt wurde — was zweimal passiert ist, bevor diese Zeile hier
    stand.
    """
    return "\n".join(z for z in quelltext.splitlines()
                     if not z.lstrip().startswith("//"))


def test_980_aufgaben_tab_setzt_hinfaellig_nicht_auf_erledigt():
    """Der teure Teil des Befunds: kein Fallback, der etwas anderes
    speichert als das, was der Nutzer angeklickt hat."""
    seite = (FRONTEND / "pages" / "TasksPage.jsx").read_text(encoding="utf-8")
    block = _ohne_kommentare(
        seite[seite.index("async function aktion("):
              seite.index("async function verschieben(")])
    assert "/obsolete" not in block
    assert "/dismiss" in block
    assert ".catch(" not in block, "kein Fallback auf eine andere Bedeutung"


def test_980_aufgaben_tab_verschiebt_ueber_die_ressource():
    seite = (FRONTEND / "pages" / "TasksPage.jsx").read_text(encoding="utf-8")
    a = seite.index("async function verschieben(")
    block = _ohne_kommentare(seite[a:a + 1600])
    assert "/reschedule" not in block
    assert "putJson(`/api/follow-ups/${eintrag.id}`" in block


@pytest.mark.parametrize("roh,erwartet", [
    ("/api/tasks/${eintrag.id}/complete", ("", "api", "tasks", "{}", "complete")),
    ("/api/follow-ups/${id}", ("", "api", "follow-ups", "{}")),
    ("/api/aufgaben", ("", "api", "aufgaben")),
    ("/api/aufgaben?status=offen", ("", "api", "aufgaben")),
    # Der Fall, an dem die erste Fassung dieses Tests zerbrach.
    ('/api/tasks/${id}/${done ? "reopen" : "complete"}',
     ("", "api", "tasks", "{}", "{}")),
])
def test_980_zerlegung(roh, erwartet):
    assert _segmente(roh) == erwartet
