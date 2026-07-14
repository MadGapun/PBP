#!/usr/bin/env python3
"""PBP Watch-Folder-Plugin — Referenz-Implementierung der Ingest-API v1 (J1/#504).

Beobachtet einen Ordner und uebergibt neue .eml-/.msg-Dateien an PBP.
Zugleich der einfachste Mail-Zubringer (J2.3-Alternative): Mails aus
Thunderbird per Drag&Drop in den Ordner ziehen — fertig.

NUR Python-Standardbibliothek, kein pip noetig. Laeuft als EXTERNER
Prozess und spricht ausschliesslich ueber die lokale REST-API mit PBP
(Architektur D1: kein Direkt-DB-Zugriff moeglich).

Einrichtung:
  1. PBP: Einstellungen -> Erweiterungen -> Gekoppelte Plugins ->
     "Plugin koppeln" -> Inhalt von pbp-plugin.json einfuegen ->
     angezeigten API-Key kopieren (wird nur EINMAL gezeigt).
  2. Starten:
       python watch_folder.py --ordner "C:/PBP-Eingang" --api-key pbp_...
     Optional: --url http://127.0.0.1:8200  --intervall 10  --einmalig

Verarbeitete Dateien wandern nach <ordner>/verarbeitet/,
fehlgeschlagene nach <ordner>/fehler/ (mit .fehler.txt daneben).
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ENDUNGEN = {".eml", ".msg"}


def _multipart(feldname: str, dateiname: str, inhalt: bytes) -> tuple[bytes, str]:
    """Baut einen multipart/form-data-Body (stdlib-only)."""
    grenze = f"pbp-{uuid.uuid4().hex}"
    ctype = mimetypes.guess_type(dateiname)[0] or "application/octet-stream"
    body = (
        f"--{grenze}\r\n"
        f'Content-Disposition: form-data; name="{feldname}"; '
        f'filename="{dateiname}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode("utf-8") + inhalt + f"\r\n--{grenze}--\r\n".encode("utf-8")
    return body, f"multipart/form-data; boundary={grenze}"


def _request(url: str, api_key: str, method: str = "GET",
             body: bytes = None, content_type: str = "") -> dict:
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("X-PBP-API-Key", api_key)
    if content_type:
        req.add_header("Content-Type", content_type)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ping(basis_url: str, api_key: str) -> dict:
    return _request(f"{basis_url}/api/v1/ingest/ping", api_key)


def sende_email(basis_url: str, api_key: str, datei: Path) -> dict:
    body, ctype = _multipart("file", datei.name, datei.read_bytes())
    return _request(f"{basis_url}/api/v1/ingest/email", api_key,
                    method="POST", body=body, content_type=ctype)


def verarbeite_ordner(ordner: Path, basis_url: str, api_key: str) -> int:
    erledigt_dir = ordner / "verarbeitet"
    fehler_dir = ordner / "fehler"
    anzahl = 0
    for datei in sorted(ordner.iterdir()):
        if not datei.is_file() or datei.suffix.lower() not in ENDUNGEN:
            continue
        try:
            antwort = sende_email(basis_url, api_key, datei)
            erledigt_dir.mkdir(exist_ok=True)
            ziel = erledigt_dir / datei.name
            if ziel.exists():
                ziel = erledigt_dir / f"{datei.stem}-{uuid.uuid4().hex[:6]}{datei.suffix}"
            datei.rename(ziel)
            anzahl += 1
            status = antwort.get("status", "?")
            print(f"[OK] {datei.name} -> {status}"
                  + (f" (Dokument {antwort.get('id', '')})" if antwort.get("id") else ""))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            if exc.code == 401:
                print(f"[STOP] API-Key ungueltig/widerrufen — {detail}")
                sys.exit(2)
            fehler_dir.mkdir(exist_ok=True)
            (fehler_dir / f"{datei.name}.fehler.txt").write_text(
                f"HTTP {exc.code}: {detail}", encoding="utf-8")
            datei.rename(fehler_dir / datei.name)
            print(f"[FEHLER] {datei.name}: HTTP {exc.code} — {detail}")
        except Exception as exc:  # noqa: BLE001
            print(f"[FEHLER] {datei.name}: {exc} (Datei bleibt liegen, "
                  "naechster Durchlauf versucht es erneut)")
    return anzahl


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PBP Watch-Folder: .eml/.msg aus einem Ordner an PBP uebergeben.")
    parser.add_argument("--ordner", required=True,
                        help="Ordner, der beobachtet wird")
    parser.add_argument("--api-key", required=True,
                        help="API-Key aus dem PBP-Pairing (Einstellungen -> Erweiterungen)")
    parser.add_argument("--url", default="http://127.0.0.1:8200",
                        help="PBP-Dashboard-URL (Default: http://127.0.0.1:8200)")
    parser.add_argument("--intervall", type=int, default=15,
                        help="Sekunden zwischen zwei Durchlaeufen (Default: 15)")
    parser.add_argument("--einmalig", action="store_true",
                        help="Nur ein Durchlauf statt Dauerbetrieb")
    args = parser.parse_args()

    ordner = Path(args.ordner)
    ordner.mkdir(parents=True, exist_ok=True)

    try:
        info = ping(args.url, args.api_key)
        print(f"[OK] Verbunden mit PBP {info.get('pbp_version')} als "
              f"Plugin '{info.get('plugin')}' (Ingest-API v{info.get('ingest_api')})")
    except urllib.error.HTTPError as exc:
        print(f"[STOP] Pairing-Check fehlgeschlagen (HTTP {exc.code}) — "
              "API-Key pruefen bzw. in PBP neu koppeln.")
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001
        print(f"[STOP] PBP nicht erreichbar unter {args.url}: {exc} — "
              "laeuft das Dashboard?")
        sys.exit(2)

    print(f"[..] Beobachte {ordner} ({', '.join(sorted(ENDUNGEN))})"
          + ("" if args.einmalig else f", alle {args.intervall}s") + " ...")
    while True:
        n = verarbeite_ordner(ordner, args.url, args.api_key)
        if n:
            print(f"[OK] {n} Datei(en) uebergeben.")
        if args.einmalig:
            break
        time.sleep(max(3, args.intervall))


if __name__ == "__main__":
    main()
