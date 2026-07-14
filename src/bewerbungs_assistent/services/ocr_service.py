"""Auto-OCR fuer gescannte PDFs — E19 (#750 Teil 2, v1.8.0-beta.0).

Ersetzt den toten #192-Fallback (pdf2image+pytesseract — brauchte Poppler
und war nie installiert). Neuer Stack:

  - **pypdfium2** rendert PDF-Seiten zu Bildern (PDFium gebundelt, reine
    pip-Dependency, kein System-Poppler).
  - Das **Tesseract-Binary der Komponente** (I10, services/components.py)
    macht die Erkennung per subprocess — kein pytesseract noetig.
  - ``--psm 1`` aktiviert die automatische Seiten-Segmentierung inklusive
    OSD-Rotationskorrektur (um 90/180/270 Grad verdrehte Scans).

KI-frei und deterministisch: funktioniert komplett ohne Ollama. Fehlt die
Komponente, liefert der Service ein strukturiertes ANGEBOT (On-Demand,
User-Leitlinie: nie Auto-Install) statt still zu scheitern.
"""
from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

from .components import (
    _ocr_env,
    _SUBPROCESS_FLAGS,
    available_languages,
    find_component_binary,
    get_component_status,
)

logger = logging.getLogger("bewerbungs_assistent")

# Konsistent mit fit_analyse/#180 und stellen_anzeigen: darunter gilt ein
# PDF als "ohne Text-Ebene".
MIN_TEXT_CHARS = 50
# Zeugnisse/Zertifikate sind 1-5 Seiten; Cap schuetzt vor 80-Seiten-Scans
# im synchronen Upload-Pfad.
MAX_SEITEN_DEFAULT = 15
_RENDER_DPI = 200


def is_scanned_pdf(filepath: str | Path) -> bool:
    """True, wenn das PDF Seiten hat, aber (fast) keine Text-Ebene."""
    path = Path(filepath)
    if not path.is_file() or path.suffix.lower() != ".pdf":
        return False
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        if not reader.pages:
            return False
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return len(text.strip()) < MIN_TEXT_CHARS
    except Exception as exc:
        logger.debug("is_scanned_pdf(%s) fehlgeschlagen: %s", path.name, exc)
        return False


def ocr_angebot(db) -> dict:
    """Strukturiertes On-Demand-Angebot, wenn die Komponente fehlt.

    Wird in Upload-Antworten und MCP-Ergebnissen mitgegeben, damit der
    naechste logische Schritt direkt am Fund steht (Benutzerfuehrung).
    """
    status = get_component_status(db, "tesseract")
    angebot = {
        "komponente": "tesseract",
        "label": status.get("label", "Tesseract OCR"),
        "groesse_mb": status.get("groesse_mb"),
        "lizenz": status.get("lizenz"),
        "warum": (
            "Dieses PDF ist ein Scan ohne Text-Ebene. Mit der OCR-Komponente "
            "liest PBP den Text automatisch aus — einmal installieren, gilt "
            "fuer alle kuenftigen Scans."
        ),
        "naechster_schritt_mcp": (
            "komponente_installieren(name='tesseract', bestaetigt=True) "
            "— nur nach RUECKFRAGE beim User ausfuehren, nie ungefragt."
        ),
        "naechster_schritt_ui": (
            "Einstellungen → Erweiterungen → Tesseract OCR installieren"
        ),
        "alternative": (
            "Text selbst extrahieren (z.B. Claude-OCR des angehaengten "
            "Scans) und per dokument_text_setzen(...) mit Quelle nachtragen."
        ),
    }
    if status.get("install_hinweis"):
        angebot["install_hinweis_os"] = status["install_hinweis"]
    return angebot


def _pick_langs(db) -> tuple[str, str]:
    """Waehlt die Sprachkette; liefert (langs, hinweis)."""
    langs = available_languages(db)
    if "deu" in langs and "eng" in langs:
        return "deu+eng", ""
    if "deu" in langs:
        return "deu", ""
    if "eng" in langs:
        return "eng", (
            "deu-Sprachpaket fehlt — Erkennung lief nur mit 'eng'. Fuer "
            "deutsche Dokumente: komponente_installieren laedt 'deu' nach, "
            "oder ensure_language('deu')."
        )
    return "", ""


def ocr_pdf(db, filepath: str | Path, max_seiten: int = MAX_SEITEN_DEFAULT,
            progress: Callable[[int, str], None] = None) -> dict:
    """OCR fuer ein Scan-PDF ueber die Tesseract-Komponente.

    Returns:
        {"status": "ok", "text": ..., "seiten": n, "seiten_gesamt": m,
         "sprachen": "deu+eng", "version": ..., "dauer_s": ...}
        oder {"status": "komponente_fehlt", "angebot": {...}}
        oder {"status": "fehler", "fehler": ...}
    """
    progress = progress or (lambda pct, msg: None)
    path = Path(filepath)
    if not path.is_file():
        return {"status": "fehler", "fehler": f"Datei nicht gefunden: {path}"}

    binary = find_component_binary(db, "tesseract")
    if not binary:
        return {"status": "komponente_fehlt", "angebot": ocr_angebot(db)}

    langs, lang_hinweis = _pick_langs(db)
    if not langs:
        return {
            "status": "fehler",
            "fehler": (
                "Tesseract gefunden, aber keine Sprachdaten (tessdata) — "
                "Installation unvollstaendig. ensure_language('deu') laedt "
                "die Sprachpakete nach."
            ),
        }

    started = time.monotonic()
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return {
            "status": "fehler",
            "fehler": (
                "pypdfium2 fehlt (PDF-Rendering). Update drueberinstallieren "
                "oder: pip install pypdfium2 pillow"
            ),
        }

    try:
        pdf = pdfium.PdfDocument(str(path))
    except Exception as exc:
        return {"status": "fehler",
                "fehler": f"PDF nicht lesbar: {str(exc)[:150]}"}

    try:
        seiten_gesamt = len(pdf)
        seiten = min(seiten_gesamt, max(1, int(max_seiten)))
        parts: list[str] = []
        env = _ocr_env()
        with tempfile.TemporaryDirectory(prefix="pbp_ocr_") as tmp:
            for i in range(seiten):
                progress(int(100 * i / seiten),
                         f"OCR Seite {i + 1}/{seiten}")
                page = pdf[i]
                bitmap = page.render(scale=_RENDER_DPI / 72)
                img_path = Path(tmp) / f"seite_{i + 1}.png"
                bitmap.to_pil().save(str(img_path), format="PNG")
                proc = subprocess.run(
                    [binary, str(img_path), "stdout", "-l", langs, "--psm", "1"],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=120, env=env,
                    **_SUBPROCESS_FLAGS,
                )
                if proc.returncode != 0:
                    stderr = (proc.stderr or "")[:200]
                    # --psm 1 braucht osd.traineddata; Fallback ohne OSD
                    proc = subprocess.run(
                        [binary, str(img_path), "stdout", "-l", langs],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=120, env=env,
                        **_SUBPROCESS_FLAGS,
                    )
                    if proc.returncode != 0:
                        raise RuntimeError(
                            f"Tesseract-Fehler Seite {i + 1}: "
                            f"{(proc.stderr or stderr or '')[:200]}"
                        )
                parts.append((proc.stdout or "").strip())
    except Exception as exc:
        return {"status": "fehler", "fehler": str(exc)[:250]}
    finally:
        try:
            pdf.close()
        except Exception:
            pass

    text = "\n\n".join(p for p in parts if p).strip()
    if not text:
        return {
            "status": "fehler",
            "fehler": (
                "OCR lieferte keinen Text — Scan-Qualitaet zu schlecht oder "
                "leere Seiten. Alternative: Text manuell extrahieren und per "
                "dokument_text_setzen nachtragen."
            ),
        }

    result = {
        "status": "ok",
        "text": text,
        "seiten": seiten,
        "seiten_gesamt": seiten_gesamt,
        "sprachen": langs,
        "version": get_component_status(db, "tesseract").get("version", ""),
        "dauer_s": round(time.monotonic() - started, 1),
    }
    if seiten < seiten_gesamt:
        result["hinweis_seiten"] = (
            f"Nur die ersten {seiten} von {seiten_gesamt} Seiten erkannt "
            f"(Cap). Mehr: dokument_ocr_ausfuehren(max_seiten={seiten_gesamt})."
        )
    if lang_hinweis:
        result["hinweis_sprache"] = lang_hinweis
    return result


def provenienz_header(ocr_result: dict, kontext: str = "automatisch beim Import") -> str:
    """Provenienz-Zeile im Stil von dokument_text_setzen (#750 Teil 1)."""
    from datetime import date
    version = ocr_result.get("version") or "?"
    langs = ocr_result.get("sprachen") or "?"
    return (
        f"[OCR via Tesseract {version} (Komponente), {langs}, "
        f"OSD-Rotationskorrektur — {kontext} {date.today().isoformat()}]"
    )
