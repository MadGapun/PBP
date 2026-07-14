"""Plugin-Pairing + Ingest-API-Vertrag — J1 (#504, v1.8.0-beta.2).

Architektur (D1–D4, Wiki Plan-Roadmap-v18): Plugins sind EXTERNE Prozesse
(Thunderbird-Add-on, Watch-Folder-Skript, ...), die ueber die versionierte
lokale REST-API `/api/v1/ingest/*` mit PBP sprechen. Kein Code-Loading in
den PBP-Prozess — Sandbox by architecture.

Pairing (D3): Der User erzeugt in den Einstellungen (Erweiterungen →
Gekoppelte Plugins) einen API-Key pro Plugin. Der Key wird GENAU EINMAL im
Klartext angezeigt; PBP speichert nur den sha256-Hash. Widerruf loescht
den Eintrag — der Key ist damit sofort tot.

Manifest (D4): Jedes Plugin deklariert sich mit `pbp-plugin.json`:
    {"name": "...", "version": "1.0.0", "ingest_api": "^1",
     "capabilities": ["ingest:email"], "beschreibung": "..."}
Die Ingest-API v1 ist waehrend der Beta als "kann sich noch aendern"
markiert und wird mit dem 1.8-Stable eingefroren (Beta-Exit Punkt 2).
"""
from __future__ import annotations

import hashlib
import re
import secrets
from typing import Optional

INGEST_API_MAJOR = 1

# Whitelist der Faehigkeiten, die die Ingest-API v1 anbietet.
CAPABILITIES = {
    "ingest:email": "E-Mails/.eml an PBP uebergeben (POST /api/v1/ingest/email)",
    "ingest:job": "Stellenangebote an PBP uebergeben (POST /api/v1/ingest/job)",
}

_NAME_RE = re.compile(r"^[\w][\w .\-]{0,58}[\w.]$", re.UNICODE)


def hash_key(api_key: str) -> str:
    return hashlib.sha256((api_key or "").encode("utf-8")).hexdigest()


def _ingest_api_major(spec: str) -> Optional[int]:
    """Extrahiert die Major-Version aus '^1', '1', '1.x', '^1.0' usw."""
    m = re.match(r"^\s*[\^~=]*\s*(\d+)", str(spec or ""))
    return int(m.group(1)) if m else None


def validate_manifest(manifest: dict) -> tuple[list[str], dict]:
    """Prueft ein Plugin-Manifest. Liefert (fehler, normalisiert)."""
    fehler: list[str] = []
    m = manifest if isinstance(manifest, dict) else {}

    name = str(m.get("name") or "").strip()
    if not name or not _NAME_RE.match(name):
        fehler.append(
            "name: Pflicht, 2-60 Zeichen (Buchstaben/Zahlen/Punkt/"
            "Bindestrich/Leerzeichen).")

    version = str(m.get("version") or "").strip()
    if not version:
        fehler.append("version: Pflicht (z.B. '1.0.0').")

    ingest_api = str(m.get("ingest_api") or "").strip()
    major = _ingest_api_major(ingest_api)
    if major is None:
        fehler.append("ingest_api: Pflicht — z.B. '^1'.")
    elif major != INGEST_API_MAJOR:
        fehler.append(
            f"ingest_api: Dieses PBP spricht v{INGEST_API_MAJOR}, das "
            f"Manifest verlangt v{major}.")

    caps_raw = m.get("capabilities")
    caps = [str(c).strip() for c in caps_raw] if isinstance(caps_raw, list) else []
    unbekannt = [c for c in caps if c not in CAPABILITIES]
    if not caps:
        fehler.append(
            "capabilities: mindestens eine aus " + ", ".join(sorted(CAPABILITIES)))
    elif unbekannt:
        fehler.append(
            "capabilities: unbekannt: " + ", ".join(unbekannt)
            + " — verfuegbar: " + ", ".join(sorted(CAPABILITIES)))

    normalized = {
        "name": name,
        "version": version,
        "ingest_api": ingest_api or f"^{INGEST_API_MAJOR}",
        "capabilities": caps,
        "beschreibung": str(m.get("beschreibung") or "")[:300],
    }
    return fehler, normalized


def pair_plugin(db, manifest: dict) -> dict:
    """Koppelt ein Plugin: validiert das Manifest, erzeugt den API-Key.

    Der Klartext-Key steht NUR in dieser Antwort — danach existiert er
    nirgends mehr (DB haelt den sha256-Hash).
    """
    fehler, norm = validate_manifest(manifest)
    if fehler:
        return {"status": "fehler", "fehler": fehler}
    api_key = "pbp_" + secrets.token_hex(24)
    plugin_id = db.add_plugin(
        name=norm["name"], version=norm["version"],
        api_key_hash=hash_key(api_key),
        capabilities=norm["capabilities"], manifest=norm,
        ingest_api=norm["ingest_api"],
    )
    return {
        "status": "gekoppelt",
        "plugin_id": plugin_id,
        "name": norm["name"],
        "capabilities": norm["capabilities"],
        "api_key": api_key,
        "hinweis": (
            "Diesen Key JETZT ins Plugin kopieren — er wird nur dieses "
            "eine Mal angezeigt. Jeder Ingest-Call traegt ihn als Header "
            "'X-PBP-API-Key'. Widerruf jederzeit in den Einstellungen."
        ),
    }


def verify_key(db, api_key: str, capability: str = "") -> tuple[Optional[dict], str]:
    """Prueft API-Key (+ optional Capability). Liefert (plugin, fehler)."""
    if not api_key:
        return None, "X-PBP-API-Key-Header fehlt."
    plugin = db.get_plugin_by_key_hash(hash_key(api_key))
    if plugin is None:
        return None, "API-Key unbekannt oder widerrufen."
    if capability and capability not in (plugin.get("capabilities") or []):
        return None, (
            f"Plugin '{plugin.get('name')}' hat die Capability "
            f"'{capability}' nicht deklariert (Manifest anpassen und neu "
            "koppeln).")
    return plugin, ""
