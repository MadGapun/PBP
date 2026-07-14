"""MCP-Tools fuer das Optionale-Komponenten-Framework — I10 (#751, v1.8.0-beta.0).

Komponenten sind nachinstallierbare Binaries (Tesseract-OCR, spaeter
Playwright), die PBP-Kernfunktionen freischalten. Grundregel aus #751:
**NIE Auto-Install** — `komponente_installieren` verlangt `bestaetigt=True`,
und das darf Claude erst NACH einer expliziten Rueckfrage beim User setzen.
"""
from __future__ import annotations

import logging


def register(mcp, db, logger: logging.Logger):
    """Registriert die Komponenten-Tools."""

    @mcp.tool()
    def komponenten_status() -> dict:
        """Zeigt alle optionalen Komponenten und ihren Zustand (I10, #751).

        Komponenten schalten PBP-Kernfunktionen frei — aktuell:
        - **tesseract**: Texterkennung (OCR) fuer gescannte PDFs (E19).

        Ollama (Lokale KI) wird mit angezeigt, aber eigenstaendig verwaltet
        (Einstellungen → Lokale KI).

        Naechste Schritte je nach Zustand:
        - nicht installiert → User fragen, dann
          `komponente_installieren(name, bestaetigt=True)`
        - Installation laeuft → kurz warten, dann erneut `komponenten_status()`
        - extern vorhanden → nichts zu tun, PBP nutzt sie automatisch
        """
        from ..services import components as comp
        overview = comp.get_components_overview(db)
        result = {"komponenten": overview}
        try:
            from ..services.llm_service import get_llm_service
            status = get_llm_service(db).get_status()
            result["ollama"] = {
                "label": "Ollama (Lokale KI)",
                "verfuegbar": bool(status.ollama_available),
                "verwaltung": "Eigenstaendig: Einstellungen → Lokale KI",
            }
        except Exception:
            result["ollama"] = {"label": "Ollama (Lokale KI)",
                                "verfuegbar": False,
                                "verwaltung": "Eigenstaendig: Einstellungen → Lokale KI"}
        laufend = None
        try:
            laufend = db.get_running_background_job("komponente_install")
        except Exception:
            pass
        if laufend:
            result["installation_laeuft"] = {
                "job_id": laufend.get("id"),
                "fortschritt": laufend.get("progress"),
                "meldung": laufend.get("message", ""),
            }
        return result

    @mcp.tool()
    def komponente_installieren(name: str, bestaetigt: bool = False) -> dict:
        """Installiert eine optionale Komponente — NUR mit User-Zustimmung.

        ⛔ PFLICHT-ABLAUF (I10-Grundregel, #751): Beim ersten Aufruf
        `bestaetigt=False` lassen — das liefert Groesse, Quelle und Lizenz
        als ANGEBOT. Dieses dem User zeigen und FRAGEN. Erst wenn der User
        ausdruecklich ja sagt: erneut mit `bestaetigt=True` aufrufen.
        Niemals ungefragt bestaetigen.

        Die Installation laeuft im Hintergrund (Download ~1-3 Minuten).
        Fortschritt: `komponenten_status()`.

        Args:
            name: Komponenten-Name (z.B. 'tesseract').
            bestaetigt: True NUR nach ausdruecklicher User-Zustimmung.
        """
        from ..services import components as comp
        status = comp.get_component_status(db, name)
        if status.get("fehler"):
            return {"fehler": f"Unbekannte Komponente '{name}'. "
                              "Verfuegbare: " + ", ".join(comp.COMPONENT_DEFS)}
        if status.get("verfuegbar"):
            return {
                "status": "bereits_vorhanden",
                "quelle": status.get("quelle"),
                "binary": status.get("binary"),
                "version": status.get("version"),
                "hinweis": "Nichts zu tun — PBP nutzt diese Installation bereits.",
            }
        if not bestaetigt:
            angebot = {
                "status": "zustimmung_erforderlich",
                "angebot": {
                    "komponente": name,
                    "label": status.get("label"),
                    "beschreibung": status.get("beschreibung"),
                    "freigeschaltete_funktion": status.get("freigeschaltete_funktion"),
                    "download_groesse_mb": status.get("groesse_mb"),
                    "lizenz": status.get("lizenz"),
                    "ziel": "AppData/BewerbungsAssistent/components/ (kein Admin noetig)",
                },
                "naechster_schritt": (
                    "Dem User dieses Angebot zeigen und fragen. Bei Ja: "
                    f"komponente_installieren(name='{name}', bestaetigt=True)."
                ),
            }
            if status.get("install_hinweis"):
                angebot["angebot"]["install_hinweis_os"] = status["install_hinweis"]
            return angebot
        result = comp.start_install_job(db, name)
        if result.get("status") == "gestartet":
            result["hinweis"] = (
                "Installation laeuft im Hintergrund (1-3 Min). Status: "
                "komponenten_status(). Danach werden Scans automatisch "
                "erkannt; bereits hochgeladene Scan-PDFs: "
                "dokument_ocr_ausfuehren(dokument_id)."
            )
        return result

    @mcp.tool()
    def plugins_anzeigen() -> dict:
        """Zeigt gekoppelte Plugins und die Ingest-API v1 (J1/#504).

        Plugins sind EXTERNE Programme (Thunderbird-Add-on, Watch-Folder-
        Skript, ...), die ueber die lokale REST-API `/api/v1/ingest/*`
        Stellen oder E-Mails an PBP liefern. Kopplung + Widerruf laufen
        BEWUSST nur ueber die UI: Einstellungen → Erweiterungen →
        Gekoppelte Plugins (der API-Key wird dort genau einmal angezeigt
        und gehoert nicht in den Chat).

        Nutze dies fuer Diagnose: Welche Plugins sind gekoppelt, was
        duerfen sie, wann kam der letzte Ingest?
        """
        from ..services import plugins as plug
        eintraege = db.get_plugins()
        return {
            "plugins": [
                {
                    "plugin_id": p.get("id"),
                    "name": p.get("name"),
                    "version": p.get("version"),
                    "capabilities": p.get("capabilities"),
                    "gekoppelt_am": p.get("created_at"),
                    "letzter_ingest": p.get("last_ingest_at") or "nie",
                    "letzter_ingest_info": p.get("last_ingest_info") or "",
                }
                for p in eintraege
            ],
            "anzahl": len(eintraege),
            "ingest_api": f"v{plug.INGEST_API_MAJOR} (Beta — Freeze mit 1.8-Stable)",
            "verfuegbare_capabilities": plug.CAPABILITIES,
            "hinweis": (
                "Neues Plugin koppeln: Einstellungen → Erweiterungen → "
                "Gekoppelte Plugins → 'Plugin koppeln'. Referenz-Beispiel: "
                "plugins/watch-folder im PBP-Repo."
            ),
        }

    @mcp.tool()
    def komponente_pfad_setzen(name: str, pfad: str) -> dict:
        """Registriert eine extern installierte Komponente per Pfad.

        Fuer den Offline-/Selbstinstallierer-Fall: Tesseract ist schon da
        (oder wurde manuell installiert), PBP soll es nutzen. Der Pfad darf
        aufs Binary oder den Installationsordner zeigen.

        Args:
            name: Komponenten-Name (z.B. 'tesseract').
            pfad: Pfad zum Binary oder Installationsordner.
        """
        from ..services import components as comp
        result = comp.set_manual_path(db, name, pfad)
        if result.get("status") == "installiert":
            result["hinweis"] = (
                "Registriert — PBP nutzt dieses Binary ab sofort. "
                "Scan-PDFs nachziehen: dokument_ocr_ausfuehren(dokument_id)."
            )
        return result
