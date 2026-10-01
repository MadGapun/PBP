"""Wer darf das Dashboard ansprechen? (v1.7.145)

PBP lauscht nur auf 127.0.0.1. Das schuetzt vor anderen Rechnern, aber nicht
vor anderen SEITEN im eigenen Browser: Jede Webseite, die der Mensch gerade
offen hat, kann Anfragen an ``http://localhost:8200`` schicken. Eine
"einfache" Anfrage (POST mit ``Content-Type: text/plain``) braucht keine
Vorab-Frage des Browsers, und FastAPI liest den Body trotzdem als JSON. So
konnte eine fremde Seite im Hintergrund das Profil ueberschreiben, einen
lokalen Ordner einlesen lassen, die Datenbank leeren, auf Werkseinstellung
zuruecksetzen oder den Deinstaller starten. Die "Bestaetigungswoerter" der
gefaehrlichen Aufrufe (RESET, LOESCHEN, DEINSTALLIEREN) stehen im selben Body,
den der Angreifer selbst schreibt, und halten nichts auf.

Zwei Pruefungen, ohne Anmeldung und ohne den Alltag zu stoeren:

1. **Host-Kopfzeile.** Nur ``localhost``, ``127.0.0.1`` und ``[::1]`` (dazu
   ``testserver`` fuer die Testsuite). Das stoppt DNS-Rebinding, bei dem ein
   fremder Name auf 127.0.0.1 zeigt und die Antworten fuer die fremde Seite
   lesbar werden. Weitere Namen erlaubt die Umgebungsvariable
   ``BA_ERLAUBTE_HOSTS`` (kommagetrennt), z. B. fuer einen Tunnel.
2. **Herkunft schreibender Aufrufe.** Traegt ein POST/PUT/PATCH/DELETE eine
   ``Origin``-Kopfzeile, muss sie die EIGENE Herkunft sein: dasselbe Schema,
   derselbe Name und Port wie die Host-Kopfzeile. Browser senden bei
   schreibenden Aufrufen immer eine; fehlt sie (curl, Skripte, Plugins, das
   Installer-Setup), ist es kein Browser auf fremder Seite. ``Origin: null``
   (Sandbox, data:-Adresse, file://) gilt als fremd. Weitere Herkuenfte
   erlaubt ``BA_ERLAUBTE_HERKUENFTE`` (kommagetrennt), z. B. den Vite-Dev-Server
   ``http://localhost:5173``.

Dazu bekommt jede Antwort zwei Schutz-Kopfzeilen: kein Einbetten durch eine
fremde Seite (Clickjacking: ein unsichtbarer Rahmen ueber einem Knopf) und
kein Erraten des Inhaltstyps.

Ausgenommen von Pruefung 2 ist die Ingest-API (``/api/v1/ingest/``): sie
verlangt einen Schluessel in einer eigenen Kopfzeile (loest im Browser eine
Vorab-Frage aus) und wird von Add-ons mit fremder Herkunft (``moz-extension://``)
angesprochen.
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("bewerbungs_assistent")

#: Namen, unter denen das Dashboard erreichbar sein darf. "testserver" ist
#: der Name, den Starlettes TestClient setzt; er ist nicht aufloesbar.
LOKALE_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]", "testserver"})

SCHREIBENDE_METHODEN = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Pfade mit eigener Anmeldung (Schluessel in der Kopfzeile X-PBP-API-Key).
AUSGENOMMENE_PRAEFIXE = ("/api/v1/ingest/",)

#: Kopfzeilen an jeder Antwort. frame-ancestors/X-Frame-Options: nur die
#: eigene Seite darf das Dashboard einrahmen (der gedruckte Verlauf wird
#: von der Oberflaeche selbst eingebettet).
SCHUTZ_KOPFZEILEN = (
    (b"x-frame-options", b"SAMEORIGIN"),
    (b"content-security-policy", b"frame-ancestors 'self'"),
    (b"x-content-type-options", b"nosniff"),
)

HINWEIS_HOST = (
    "Dieser Name ist fuer PBP nicht freigegeben. Oeffne das Dashboard ueber "
    "http://localhost:8200 oder http://127.0.0.1:8200. Wer es bewusst unter "
    "einem anderen Namen betreibt, erlaubt ihn mit der Umgebungsvariable "
    "BA_ERLAUBTE_HOSTS.")
HINWEIS_HERKUNFT = (
    "Diese Anfrage kommt nicht von der PBP-Oberflaeche und wurde abgelehnt. "
    "Aenderungen nimmt PBP nur von seiner eigenen Seite an.")


def _liste_aus_umgebung(name: str) -> frozenset[str]:
    roh = os.environ.get(name, "")
    return frozenset(t.strip().lower() for t in roh.split(",") if t.strip())


def host_ohne_port(host_kopf: str | None) -> str:
    """'localhost:8200' -> 'localhost', '[::1]:8200' -> '[::1]'."""
    h = (host_kopf or "").strip().lower()
    if h.startswith("["):
        ende = h.find("]")
        return h[: ende + 1] if ende != -1 else h
    return h.rsplit(":", 1)[0] if ":" in h else h


def host_erlaubt(host_kopf: str | None) -> bool:
    """Darf das Dashboard unter diesem Namen angesprochen werden?"""
    name = host_ohne_port(host_kopf)
    return bool(name) and (name in LOKALE_HOSTS
                           or name in _liste_aus_umgebung("BA_ERLAUBTE_HOSTS"))


def herkunft_erlaubt(origin: str | None, host_kopf: str | None) -> bool:
    """Stammt ein schreibender Aufruf von der EIGENEN Seite?

    Ohne Origin-Kopfzeile: ja (kein Browser auf fremder Seite). Mit Origin:
    nur wenn sie dem eigenen Schema und der Host-Kopfzeile entspricht oder
    ausdruecklich erlaubt ist.
    """
    if origin is None:
        return True
    o = origin.strip().lower()
    if o in ("", "null"):
        return False
    if o in _liste_aus_umgebung("BA_ERLAUBTE_HERKUENFTE"):
        return True
    eigen = (host_kopf or "").strip().lower()
    return bool(eigen) and o in (f"http://{eigen}", f"https://{eigen}")


def pruefen(methode: str, pfad: str, host_kopf: str | None,
            origin: str | None) -> tuple[bool, str]:
    """(erlaubt, Hinweis). Die EINE Antwort fuer Middleware und Tests."""
    if not host_erlaubt(host_kopf):
        return False, HINWEIS_HOST
    if (methode or "").upper() in SCHREIBENDE_METHODEN \
            and not pfad.startswith(AUSGENOMMENE_PRAEFIXE) \
            and not herkunft_erlaubt(origin, host_kopf):
        return False, HINWEIS_HERKUNFT
    return True, ""


class LokalerZugriffMiddleware:
    """ASGI-Middleware: lehnt fremde Namen und fremde Herkunft ab (403)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        kopf = {k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in scope.get("headers", [])}
        async def send_mit_schutz(nachricht):
            if nachricht["type"] == "http.response.start":
                vorhanden = {k.lower() for k, _ in nachricht.get("headers", [])}
                kopfzeilen = list(nachricht.get("headers", []))
                for name, wert in SCHUTZ_KOPFZEILEN:
                    if name not in vorhanden:
                        kopfzeilen.append((name, wert))
                nachricht = {**nachricht, "headers": kopfzeilen}
            await send(nachricht)

        erlaubt, hinweis = pruefen(scope.get("method", "GET"),
                                   scope.get("path", ""),
                                   kopf.get("host"), kopf.get("origin"))
        if erlaubt:
            await self.app(scope, receive, send_mit_schutz)
            return
        logger.warning("Anfrage abgelehnt (%s %s): Host=%r Origin=%r",
                       scope.get("method"), scope.get("path"),
                       kopf.get("host"), kopf.get("origin"))
        koerper = json.dumps({"error": hinweis}, ensure_ascii=False).encode("utf-8")
        await send_mit_schutz({"type": "http.response.start", "status": 403, "headers": [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(koerper)).encode("ascii")),
            (b"cache-control", b"no-store"),
        ]})
        await send({"type": "http.response.body", "body": koerper})
