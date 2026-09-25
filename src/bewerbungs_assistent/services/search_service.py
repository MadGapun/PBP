"""Gemeinsame Such- und Quellenlogik für Dashboard und weitere Services."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_search_status(last_search_at: str | None, now: datetime | None = None) -> dict:
    """Normalize the stored last-search timestamp into a UI-friendly status."""
    if not last_search_at:
        return {"last_search": None, "days_ago": None, "status": "nie"}

    current_time = now or datetime.now()
    try:
        dt = datetime.fromisoformat(last_search_at)
        days = (current_time - dt).days
    except (ValueError, TypeError):
        return {"last_search": last_search_at, "days_ago": None, "status": "unbekannt"}

    status = "aktuell" if days == 0 else "veraltet" if days < 7 else "dringend"
    return {"last_search": last_search_at, "days_ago": days, "status": status}


def summarize_active_sources(active_keys, available_keys) -> dict:
    """Count active sources relative to the known registry keys."""
    active_list = list(active_keys or [])
    active_set = set(active_list)
    keys = list(available_keys)
    active_count = sum(1 for key in keys if key in active_set)
    return {
        "active": active_count,
        "total": len(keys),
        "active_keys": active_list,
    }


def get_default_active_source_keys(source_registry: dict) -> list[str]:
    """Return the default source selection for a fresh profile.

    Quellen mit notwendigem Erst-Login bleiben standardmaessig deaktiviert,
    ebenso als `defekt` markierte (#500). Alle anderen werden vorausgewaehlt.
    """
    return [
        key
        for key, info in source_registry.items()
        if not info.get("login_erforderlich", False)
        and not info.get("defekt", False)
    ]


# B69 (#1087 C7): die Startquellen, wenn das Profil noch keine Empfehlung
# traegt — dieselben drei, die `jobsuche_starten` beim ersten Lauf nennt.
START_QUELLEN = ("bundesagentur", "arbeitnow", "jobspy_indeed")


def erstauswahl(db, source_registry: dict) -> dict:
    """Die ERSTE Quellenauswahl eines Profils (B69, #1087 C7).

    Bis v1.7.132 schrieb `/api/sources` beim ersten Oeffnen alle Quellen
    ohne Login als aktiv — im Demo 29 von 34, darunter Fernquellen ohne
    DACH-Bezug (#996) und LinkedIn ueber JobSpy (#1038), obwohl die
    Empfehlung fuer das Profil neun nannte. Jetzt ist die Erstauswahl die
    Empfehlung fuer das Profil; ohne verwertbare Empfehlung die drei
    Startquellen. Die Oberflaeche zeigt, was gewaehlt wurde und warum
    (`quellen_erstauswahl`), statt still zu aktivieren.
    """
    grundlage = "start"
    label = ""
    keys: list[str] = []
    try:
        from .profile_classifier import recommend_sources, suchbegriffe_aus
        rec = recommend_sources(db.get_profile(), suchbegriffe_aus(db)) or {}
        keys = list(rec.get("recommended") or [])
        label = rec.get("label") or ""
        if keys:
            grundlage = "profil"
    except Exception as exc:  # pragma: no cover - nie die Quellenliste stoppen
        logger.debug("Quellen-Empfehlung nicht verfuegbar: %s", exc)
    if not keys:
        keys = list(START_QUELLEN)
    keys = [k for k in ohne_defekte(keys, source_registry)
            if not (source_registry.get(k) or {}).get("login_erforderlich", False)]
    if not keys:
        keys = [k for k in START_QUELLEN if k in source_registry]
    return {"quellen": keys, "grundlage": grundlage, "profil_art": label}


def ohne_defekte(keys, source_registry: dict) -> list[str]:
    """Die Schluessel ohne defekte und ohne entfernte Quellen.

    v1.7.122 (#1066): auch Schluessel, die die Registry GAR NICHT MEHR
    kennt, fallen heraus. Vorher filterte nur `defekt` — eine entfernte
    Quelle waere damit unsichtbar in der gespeicherten Auswahl stehen
    geblieben, gezeichnet wird sie nicht, gewaehlt bleibt sie: genau der
    Zustand aus #1039/#1008, nur in die andere Richtung.
    """
    return [
        key for key in (keys or [])
        if key in source_registry
        and not (source_registry.get(key) or {}).get("defekt", False)
    ]


def entfernte_aus_auswahl(keys) -> list[dict]:
    """Welche gewaehlten Quellen wurden ENTFERNT — mit Grund (#1066).

    Fuer den einmaligen Hinweis: ein stiller Wegfall waere das Muster
    aus #211. Unbekannte Schluessel ohne Eintrag werden bewusst nicht
    gemeldet (die gab es nie oder sie stammen aus einer anderen Linie).
    """
    from ..job_scraper import ENTFERNTE_QUELLEN
    return [dict(ENTFERNTE_QUELLEN[k], schluessel=k)
            for k in (keys or []) if k in ENTFERNTE_QUELLEN]


def aktive_quellen(db, source_registry: dict | None = None) -> list[str] | None:
    """Die gespeicherte Quellen-Auswahl — ohne defekte Quellen (#1039).

    Eine Quelle, die NACH dem Anhaken als defekt markiert wurde, blieb in
    der gespeicherten Auswahl. Das Dashboard zeichnete ihren Haken leer und
    gesperrt, jeder Suchlauf uebersprang sie erneut, und abwaehlen liess sie
    sich nicht mehr: ein Zustand, den niemand sieht, wirkte trotzdem (Klasse
    #1008). Deshalb heilt jeder Leseweg die gespeicherte Auswahl, statt nur
    die Anzeige zu filtern — sonst sagen Anzeige und Speicher weiter
    Verschiedenes.

    Returns:
        die bereinigte Liste; None, wenn nichts gespeichert ist (der
        Aufrufer entscheidet dann ueber die Vorauswahl).
    """
    if source_registry is None:
        from ..job_scraper import SOURCE_REGISTRY as source_registry
    gespeichert = db.get_profile_setting("active_sources", None)
    if gespeichert is None:
        return None
    bereinigt = ohne_defekte(gespeichert, source_registry)
    if len(bereinigt) != len(list(gespeichert)):
        # #1066: was entfernt wurde, wird gemerkt — sonst faellt es
        # still weg und der Mensch sucht die Quelle vergeblich.
        entfernt = entfernte_aus_auswahl(gespeichert)
        if entfernt:
            try:
                db.set_profile_setting(
                    "entfernte_quellen_hinweis",
                    [e["schluessel"] for e in entfernt])
            except Exception:  # pragma: no cover — nie den Lauf kippen
                pass
        db.set_profile_setting("active_sources", bereinigt)
    return bereinigt


def build_source_rows(source_registry: dict, active_keys) -> list:
    """Build dashboard-friendly source rows with active flags."""
    active_set = set(active_keys or [])
    return [
        {
            "key": key,
            "name": info["name"],
            "beschreibung": info["beschreibung"],
            "methode": info["methode"],
            "login_erforderlich": info["login_erforderlich"],
            "active": key in active_set,
            "profil_optimierung": info.get("profil_optimierung"),
            "beta": info.get("beta", False),
            "veraltet": info.get("veraltet", False),
            "warnung": info.get("warnung"),
            "geschwindigkeit": info.get("geschwindigkeit", "schnell"),
            # #500: Defekt-Klassifikation. Wenn `defekt` True ist, blockiert
            # run_search die Quelle automatisch; das Frontend zeigt sie
            # ausgegraut + mit Chrome-Extension-Fallback-Hinweis.
            "defekt": info.get("defekt", False),
            "defekt_grund": info.get("defekt_grund"),
            "manueller_fallback": info.get("manueller_fallback"),
            # v1.7.17 (#906): Zugriffsart explizit — 'api' laeuft
            # automatisch, 'browser'/'browser_login' nur ueber
            # Claude-in-Chrome (letzteres mit eingeloggtem Konto). Das
            # Frontend zeigt den Hinweis VOR der Aktivierung.
            "zugriffsart": _zugriffsart(key, info),
            "konto_url": info.get("konto_url"),
            "login_hinweis": info.get("login_hinweis"),
            "deprecated": info.get("deprecated", False),
            "deprecated_grund": info.get("deprecated_grund"),
        }
        for key, info in source_registry.items()
    ]


def _zugriffsart(key: str, info: dict) -> str:
    """Wie zugriffsart_von in job_scraper, aber ohne Registry-Lookup —
    hier liegt der Eintrag schon vor (kein Zirkularimport)."""
    if info.get("zugriffsart"):
        return info["zugriffsart"]
    if str(info.get("methode", "")).startswith(("Claude-in-Chrome",
                                                 "Claude-Erweiterung im eigenen Browser")):
        return "browser_login" if info.get("login_erforderlich") else "browser"
    return "api"
