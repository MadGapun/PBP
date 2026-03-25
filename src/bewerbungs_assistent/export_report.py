"""Bewerbungsbericht — PDF & Excel Export.

Generates comprehensive application reports for:
- Personal tracking and overview
- Arbeitsamt (employment office) documentation
- Self-analysis and optimization

Uses fpdf2 for PDF (pure Python, no system deps).
Uses openpyxl for Excel (optional dependency).
"""

import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from fpdf.enums import XPos, YPos

logger = logging.getLogger("bewerbungs_assistent.export_report")

STATUS_LABELS = {
    "in_vorbereitung": "In Vorbereitung",
    "offen": "Offen",
    "beworben": "Beworben",
    "eingangsbestaetigung": "Eingangsbestätigung",
    "interview": "Interview",
    "zweitgespraech": "Zweitgespräch",
    "angebot": "Angebot",
    "angenommen": "Angenommen",
    "abgelehnt": "Abgelehnt",
    "zurueckgezogen": "Zurückgezogen",
    "zurückgezogen": "Zurückgezogen",
    "abgelaufen": "Abgelaufen",
}

STATUS_COLORS = {
    "in_vorbereitung": (168, 85, 247),
    "beworben": (56, 189, 248),
    "interview": (251, 191, 36),
    "zweitgespraech": (251, 191, 36),
    "angebot": (52, 211, 153),
    "angenommen": (16, 185, 129),
    "abgelehnt": (248, 113, 113),
    "zurueckgezogen": (148, 163, 184),
    "zurückgezogen": (148, 163, 184),
    "abgelaufen": (148, 163, 184),
    "offen": (100, 116, 139),
    "eingangsbestaetigung": (56, 189, 248),
}

SOURCE_COLORS_PDF = [
    (59, 130, 246), (168, 85, 247), (236, 72, 153), (249, 115, 22),
    (234, 179, 8), (34, 197, 94), (20, 184, 166), (99, 102, 241),
    (244, 63, 94), (107, 114, 128),
]


def _safe_text(text: str) -> str:
    """Sanitize text for PDF output (replace problematic chars)."""
    if not text:
        return ""
    return (text
            .replace("\u2013", "-").replace("\u2014", "-")
            .replace("\u2018", "'").replace("\u2019", "'")
            .replace("\u201c", '"').replace("\u201d", '"')
            .replace("\u2026", "...")
            .replace("\u00ad", "")  # soft hyphen
            .encode("latin-1", errors="replace").decode("latin-1"))


def _line_cell(pdf, w, h, text="", **kwargs):
    """Write a cell and advance to the next line with the modern fpdf2 API."""
    pdf.cell(w, h, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT, **kwargs)


def generate_application_report(report_data: dict, profile: Optional[dict],
                                output_path: Path,
                                zeitraum_von: str = "",
                                zeitraum_bis: str = "") -> Path:
    """Generate a comprehensive PDF Bewerbungsbericht (#173 aufgewertet)."""
    from fpdf import FPDF

    apps = report_data.get("applications", [])
    stats = report_data.get("statistics", {})
    score_dist = report_data.get("score_distribution", {})
    unapplied = report_data.get("unapplied_high_score", [])
    date_range = report_data.get("date_range", {})

    # Zeitraumfilter (#173)
    if zeitraum_von or zeitraum_bis:
        apps = [a for a in apps if
                (not zeitraum_von or (a.get("applied_at") or "") >= zeitraum_von) and
                (not zeitraum_bis or (a.get("applied_at") or "") <= zeitraum_bis + "T23:59:59")]

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # --- Title Page with PBP Branding (#173) ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 22)
    _line_cell(pdf, 0, 15, _safe_text("Bewerbungsbericht"), align="C")

    # Subtitle with name and date range
    pdf.set_font("Helvetica", "", 11)
    name = profile.get("name", "") if profile else ""
    if name:
        _line_cell(pdf, 0, 7, _safe_text(name), align="C")

    pdf.set_font("Helvetica", "", 9)
    zeitraum = ""
    if zeitraum_von and zeitraum_bis:
        zeitraum = f"Zeitraum: {zeitraum_von} bis {zeitraum_bis}"
    elif date_range.get("first") and date_range.get("last"):
        zeitraum = f"Zeitraum: {date_range['first'][:10]} bis {date_range['last'][:10]}"
    if zeitraum:
        _line_cell(pdf, 0, 5, _safe_text(zeitraum), align="C")
    _line_cell(pdf, 0, 5, _safe_text(f"Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M')}"), align="C")
    pdf.ln(6)

    # PBP Branding (#173)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    _line_cell(pdf, 0, 4, _safe_text("Erstellt mit PBP (Persoenliches Bewerbungs-Portal)"), align="C")
    _line_cell(pdf, 0, 4, _safe_text("https://github.com/MadGapun/PBP"), align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # --- Inhaltsverzeichnis (#173) ---
    _section_header(pdf, "Inhaltsverzeichnis")
    toc_items = [
        "1. Executive Summary",
        "2. Bewerbungen nach Status",
        "3. Quellenanalyse",
        "4. Fit-Score Verteilung",
        "5. Bewerbungsliste (detailliert)",
        "6. Nicht beworben trotz gutem Score",
        "7. Keyword-Analyse",
    ]
    pdf.set_font("Helvetica", "", 10)
    for item in toc_items:
        _line_cell(pdf, 0, 6, _safe_text(f"    {item}"))
    pdf.ln(6)

    # --- Executive Summary (#173) ---
    _section_header(pdf, "1. Executive Summary")
    total_apps = len(apps) if (zeitraum_von or zeitraum_bis) else stats.get("total_applications", len(apps))
    active_jobs = stats.get("active_jobs", 0)
    dismissed_jobs = stats.get("dismissed_jobs", 0)
    avg_score = stats.get("avg_score", 0)
    max_score = stats.get("max_score", 0)

    # Recalculate rates for filtered apps
    by_status_filtered = Counter(a.get("status", "offen") for a in apps)
    interviews = by_status_filtered.get("interview", 0) + by_status_filtered.get("zweitgespraech", 0)
    offers = by_status_filtered.get("angebot", 0) + by_status_filtered.get("angenommen", 0)
    in_vorb = by_status_filtered.get("in_vorbereitung", 0)
    submitted_apps = total_apps - in_vorb  # exclude in_vorbereitung (#198)
    interview_rate = round(interviews / submitted_apps * 100, 1) if submitted_apps else 0
    offer_rate = round(offers / submitted_apps * 100, 1) if submitted_apps else 0

    # Summary text
    pdf.set_font("Helvetica", "", 9)
    summary_text = (
        f"Im Berichtszeitraum wurden {total_apps} Bewerbungen erfasst. "
        f"Die Interview-Rate liegt bei {interview_rate}%, "
        f"die Angebotsrate bei {offer_rate}%. "
        f"Insgesamt wurden {active_jobs + dismissed_jobs} Stellen analysiert."
    )
    pdf.multi_cell(0, 5, _safe_text(summary_text))
    pdf.ln(3)

    # --- 1. Zusammenfassung ---
    _section_header(pdf, "1. Zusammenfassung")
    total_apps = stats.get("total_applications", len(apps))
    active_jobs = stats.get("active_jobs", 0)
    dismissed_jobs = stats.get("dismissed_jobs", 0)
    avg_score = stats.get("avg_score", 0)
    max_score = stats.get("max_score", 0)
    interview_rate = stats.get("interview_rate", 0)
    offer_rate = stats.get("offer_rate", 0)

    # Pipeline overview
    pipeline_data = [
        ("Bewerbungen gesamt", str(total_apps)),
        ("  davon in Vorbereitung", str(by_status_filtered.get("in_vorbereitung", 0))),
        ("  davon beworben", str(by_status_filtered.get("beworben", 0))),
        ("  davon im Prozess", str(interviews)),
        ("  davon Angebote", str(offers)),
        ("Aktive Stellen analysiert", str(active_jobs)),
        ("Aussortierte Stellen", str(dismissed_jobs)),
        ("Durchschn. Fit-Score", f"{avg_score}" if avg_score else "k.A."),
        ("Spitzen-Fit-Score", f"{max_score}" if max_score else "k.A."),
        ("Interview-Rate", f"{interview_rate}%"),
        ("Angebots-Rate", f"{offer_rate}%"),
    ]
    for label, value in pipeline_data:
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(80, 5, _safe_text(f"  {label}:"), border=0)
        pdf.set_font("Helvetica", "B", 9)
        _line_cell(pdf, 0, 5, _safe_text(value))
    pdf.ln(4)

    # --- 2. Bewerbungen nach Status ---
    _section_header(pdf, "2. Bewerbungen nach Status")
    by_status = stats.get("applications_by_status", {})
    if by_status:
        for status_key, count in sorted(by_status.items(),
                                         key=lambda x: -x[1]):
            label = STATUS_LABELS.get(status_key, status_key)
            bar_width = min(count * 8, 120)
            r, g, b = STATUS_COLORS.get(status_key, (66, 133, 244))
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(45, 5, _safe_text(f"  {label}"))
            pdf.set_fill_color(r, g, b)
            pdf.cell(bar_width, 5, "", fill=True)
            _line_cell(pdf, 15, 5, f"  {count}")
    pdf.ln(4)

    # --- 3. Quellenanalyse (#173) ---
    _section_header(pdf, "3. Quellenanalyse")
    by_source = stats.get("jobs_by_source", {})
    if by_source:
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(60, 5, "  Quelle", border=1, fill=True)
        pdf.cell(30, 5, "Stellen", border=1, fill=True, align="C")
        pdf.cell(40, 5, "Anteil", border=1, fill=True, align="C")
        pdf.ln()
        total_source = sum(by_source.values()) or 1
        pdf.set_font("Helvetica", "", 8)
        for idx, (source, count) in enumerate(sorted(by_source.items(), key=lambda x: -x[1])):
            pct = round(count / total_source * 100, 1)
            r, g, b = SOURCE_COLORS_PDF[idx % len(SOURCE_COLORS_PDF)]
            pdf.set_fill_color(r, g, b)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(5, 5, "", border=0, fill=True)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(55, 5, _safe_text(f" {source}"), border=1)
            pdf.cell(30, 5, str(count), border=1, align="C")
            pdf.cell(40, 5, f"{pct}%", border=1, align="C")
            pdf.ln()
    pdf.ln(2)

    # Bewerbungen nach Quelle mit Erfolgsquote (#173)
    app_by_source = {}
    for a in apps:
        src = a.get("job_source") or a.get("source") or "unbekannt"
        if src not in app_by_source:
            app_by_source[src] = {"total": 0, "interview": 0}
        app_by_source[src]["total"] += 1
        if a.get("status") in ("interview", "zweitgespraech", "angebot", "angenommen"):
            app_by_source[src]["interview"] += 1

    if app_by_source:
        pdf.set_font("Helvetica", "B", 8)
        _line_cell(pdf, 0, 5, _safe_text("  Bewerbungen nach Quelle (mit Erfolgsquote):"))
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(50, 5, "  Quelle", border=1, fill=True)
        pdf.cell(30, 5, "Bewerbungen", border=1, fill=True, align="C")
        pdf.cell(30, 5, "Interviews", border=1, fill=True, align="C")
        pdf.cell(30, 5, "Erfolgsquote", border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_font("Helvetica", "", 8)
        for src, data in sorted(app_by_source.items(), key=lambda x: -x[1]["total"]):
            rate = round(data["interview"] / data["total"] * 100, 0) if data["total"] else 0
            pdf.cell(50, 4, _safe_text(f"  {src}"), border=1)
            pdf.cell(30, 4, str(data["total"]), border=1, align="C")
            pdf.cell(30, 4, str(data["interview"]), border=1, align="C")
            pdf.cell(30, 4, f"{rate:.0f}%", border=1, align="C")
            pdf.ln()
    pdf.ln(4)

    # --- 4. Score-Verteilung ---
    if score_dist:
        _section_header(pdf, "4. Fit-Score Verteilung")
        pdf.set_font("Helvetica", "", 9)
        for bracket, count in sorted(score_dist.items()):
            bar_width = min(count, 120)
            pdf.cell(30, 5, _safe_text(f"  Score {bracket}"))
            pdf.set_fill_color(76, 175, 80)
            pdf.cell(bar_width, 5, "", fill=True)
            _line_cell(pdf, 15, 5, f"  {count}")
        pdf.ln(4)

    # --- 5. Bewerbungsliste (detailliert, #173) ---
    _section_header(pdf, "5. Bewerbungsliste (detailliert)")
    if apps:
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(18, 5, "Datum", border=1, fill=True)
        pdf.cell(35, 5, "Firma", border=1, fill=True)
        pdf.cell(45, 5, "Position", border=1, fill=True)
        pdf.cell(22, 5, "Status", border=1, fill=True, align="C")
        pdf.cell(15, 5, "Quelle", border=1, fill=True, align="C")
        pdf.cell(10, 5, "Score", border=1, fill=True, align="C")
        pdf.cell(15, 5, "Art", border=1, fill=True, align="C")
        pdf.cell(30, 5, "Kontakt", border=1, fill=True)
        pdf.ln()
        pdf.set_font("Helvetica", "", 6.5)
        for idx, a in enumerate(apps):
            # Alternating row colors (#173)
            if idx % 2 == 1:
                pdf.set_fill_color(245, 247, 250)
                fill = True
            else:
                fill = False

            date_str = (a.get("applied_at") or "")[:10]
            company = (a.get("company") or "")[:20]
            title = (a.get("title") or "")[:28]
            status_key = a.get("status", "")
            status = STATUS_LABELS.get(status_key, status_key)[:12]
            source = (a.get("job_source") or a.get("source", ""))[:10]
            score = a.get("score", "")
            if a.get("is_pinned"):
                score = f"*{score}" if score else "*"
            else:
                score = str(score) if score else ""
            art = (a.get("bewerbungsart") or "")[:10]
            kontakt = (a.get("ansprechpartner") or "")[:18]

            # Status color badge
            r, g, b = STATUS_COLORS.get(status_key, (100, 116, 139))

            pdf.cell(18, 4, _safe_text(date_str), border=1, fill=fill)
            pdf.cell(35, 4, _safe_text(company), border=1, fill=fill)
            pdf.cell(45, 4, _safe_text(title), border=1, fill=fill)
            # Status with color
            pdf.set_fill_color(r, g, b)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(22, 4, _safe_text(status), border=1, fill=True, align="C")
            pdf.set_text_color(0, 0, 0)
            if idx % 2 == 1:
                pdf.set_fill_color(245, 247, 250)
            pdf.cell(15, 4, _safe_text(source), border=1, fill=fill, align="C")
            pdf.cell(10, 4, _safe_text(str(score)), border=1, fill=fill, align="C")
            pdf.cell(15, 4, _safe_text(art), border=1, fill=fill, align="C")
            pdf.cell(30, 4, _safe_text(kontakt), border=1, fill=fill)
            pdf.ln()
    pdf.ln(4)

    # --- 6. Nicht beworben trotz gutem Score (#220) ---
    _section_header(pdf, "6. Nicht beworben trotz gutem Fit-Score")
    if unapplied:
        pdf.set_font("Helvetica", "", 8)
        _line_cell(pdf, 0, 5, _safe_text(
            f"  {len(unapplied)} Stellen mit Score >= 5 ohne Bewerbung:"
        ))
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(255, 243, 224)
        pdf.cell(50, 5, "Firma", border=1, fill=True)
        pdf.cell(65, 5, "Position", border=1, fill=True)
        pdf.cell(13, 5, "Score", border=1, fill=True, align="C")
        pdf.cell(20, 5, "Quelle", border=1, fill=True, align="C")
        pdf.cell(22, 5, "Gefunden", border=1, fill=True, align="C")
        pdf.cell(20, 5, "Grund", border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_font("Helvetica", "", 7)
        for j in unapplied[:20]:
            company = (j.get("company") or "")[:28]
            title = (j.get("title") or "")[:38]
            reason = ""
            if not j.get("is_active"):
                raw = j.get("dismiss_reason") or ""
                # dismiss_reason kann JSON-Array oder String sein
                if raw.startswith("["):
                    import json as _json
                    try:
                        reasons = _json.loads(raw)
                        reason = ", ".join(str(r) for r in reasons)[:20]
                    except Exception:
                        reason = raw[:20]
                else:
                    reason = raw[:20] if raw else "aussort."
            pdf.cell(50, 4, _safe_text(company), border=1)
            pdf.cell(65, 4, _safe_text(title), border=1)
            pdf.cell(13, 4, str(j.get("score", "")), border=1, align="C")
            pdf.cell(20, 4, _safe_text((j.get("source") or "")[:12]), border=1, align="C")
            pdf.cell(22, 4, _safe_text((j.get("found_at") or "")[:10]), border=1, align="C")
            pdf.cell(20, 4, _safe_text(reason), border=1, align="C")
            pdf.ln()
    else:
        pdf.set_font("Helvetica", "", 8)
        _line_cell(pdf, 0, 5, "  Im Berichtszeitraum wurden keine Stellen mit gutem Score aussortiert.")
    pdf.ln(4)

    # --- 7. Keyword-Analyse ---
    _section_header(pdf, "7. Keyword-Analyse (Top-Begriffe in passenden Stellen)")
    applied_descriptions = []
    for a in apps:
        desc = a.get("job_description") or ""
        title = a.get("title") or ""
        if desc or title:
            applied_descriptions.append(f"{title} {desc}".lower())

    if applied_descriptions:
        # Count word frequency across applied job descriptions
        word_counter = Counter()
        stop_words = {
            "und", "die", "der", "in", "von", "zu", "mit", "fuer", "für",
            "den", "das", "ist", "im", "ein", "eine", "auf", "des", "als",
            "wir", "sie", "oder", "an", "bei", "our", "the", "and", "for",
            "you", "are", "with", "your", "will", "that", "this", "have",
            "from", "not", "all", "can", "has", "been", "more", "also",
            "aber", "aus", "nach", "wie", "sich", "ihre", "ihren", "einer",
            "einem", "eines", "werden", "wird", "haben", "sein", "sind",
            "m/w/d", "m/w", "(m/w/d)", "(m/w)", "gmbh", "gerne",
        }
        for text in applied_descriptions:
            words = text.split()
            for w in words:
                w = w.strip(".,;:!?()[]{}\"'/-")
                if len(w) >= 3 and w not in stop_words:
                    word_counter[w] += 1

        top_words = word_counter.most_common(25)
        if top_words:
            pdf.set_font("Helvetica", "", 8)
            _line_cell(pdf, 0, 5, _safe_text(
                "  Haeufigste Begriffe in Stellen, auf die Sie sich beworben haben:"
            ))
            pdf.set_font("Helvetica", "B", 7)
            pdf.set_fill_color(232, 245, 233)
            pdf.cell(50, 5, "  Keyword", border=1, fill=True)
            pdf.cell(25, 5, "Vorkommen", border=1, fill=True, align="C")
            pdf.ln()
            pdf.set_font("Helvetica", "", 7)
            for word, count in top_words:
                pdf.cell(50, 4, _safe_text(f"  {word}"), border=1)
                pdf.cell(25, 4, str(count), border=1, align="C")
                pdf.ln()
    pdf.ln(4)

    # --- Footer with PBP Branding (#173) ---
    pdf.ln(8)
    pdf.set_draw_color(31, 78, 121)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(31, 78, 121)
    _line_cell(pdf, 0, 5, _safe_text(
        "Erstellt mit PBP (Persoenliches Bewerbungs-Portal)"
    ), align="C")
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(100, 100, 100)
    _line_cell(pdf, 0, 4, _safe_text(
        "PBP ist ein KI-gestuetztes Bewerbungsmanagement-Tool, das den gesamten "
        "Bewerbungsprozess von der Stellensuche bis zum Angebot strukturiert und automatisiert."
    ), align="C")
    _line_cell(pdf, 0, 4, _safe_text(
        f"https://github.com/MadGapun/PBP | {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    ), align="C")
    pdf.set_text_color(0, 0, 0)
    _line_cell(pdf, 0, 4, _safe_text("* = manuell hinzugefuegte Stelle (gepinnt)"), align="C")

    pdf.output(str(output_path))
    logger.info("PDF Bewerbungsbericht erstellt: %s", output_path)
    return output_path


def _section_header(pdf, title: str):
    """Draw a section header with background."""
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(33, 150, 243)
    pdf.set_text_color(255, 255, 255)
    _line_cell(pdf, 0, 7, _safe_text(f"  {title}"), fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def generate_excel_report(report_data: dict, profile: Optional[dict],
                          output_path: Path) -> Path:
    """Generate an Excel Bewerbungsbericht (requires openpyxl)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    apps = report_data.get("applications", [])
    stats = report_data.get("statistics", {})

    wb = Workbook()

    # --- Sheet 1: Bewerbungen ---
    ws = wb.active
    ws.title = "Bewerbungen"
    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_fill = PatternFill(start_color="2196F3", end_color="2196F3", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin")
    )

    headers = ["Datum", "Firma", "Position", "Status", "Quelle",
               "Fit-Score", "Gepinnt", "Bewerbungsart", "Notizen"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center")

    for row_num, a in enumerate(apps, 2):
        values = [
            (a.get("applied_at") or "")[:10],
            a.get("company", ""),
            a.get("title", ""),
            STATUS_LABELS.get(a.get("status", ""), a.get("status", "")),
            a.get("job_source") or "",
            a.get("score", 0) if not a.get("is_pinned") else "",
            "Ja" if a.get("is_pinned") else "",
            a.get("bewerbungsart", ""),
            (a.get("notes") or "")[:200],
        ]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row_num, column=col, value=val)
            cell.border = thin_border

    # Auto-width
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

    # --- Sheet 2: Statistik ---
    ws2 = wb.create_sheet("Statistik")
    stat_rows = [
        ("Bewerbungen gesamt", stats.get("total_applications", 0)),
        ("Aktive Stellen", stats.get("active_jobs", 0)),
        ("Aussortierte Stellen", stats.get("dismissed_jobs", 0)),
        ("Durchschn. Fit-Score", stats.get("avg_score", "")),
        ("Spitzen-Score", stats.get("max_score", "")),
        ("Interview-Rate", f"{stats.get('interview_rate', 0)}%"),
        ("Angebots-Rate", f"{stats.get('offer_rate', 0)}%"),
    ]
    ws2.cell(row=1, column=1, value="Kennzahl").font = Font(bold=True)
    ws2.cell(row=1, column=2, value="Wert").font = Font(bold=True)
    for row_num, (label, val) in enumerate(stat_rows, 2):
        ws2.cell(row=row_num, column=1, value=label)
        ws2.cell(row=row_num, column=2, value=val)

    # Status breakdown
    row_start = len(stat_rows) + 3
    ws2.cell(row=row_start, column=1, value="Status-Verteilung").font = Font(bold=True)
    for i, (status, count) in enumerate(
        stats.get("applications_by_status", {}).items(), row_start + 1
    ):
        ws2.cell(row=i, column=1, value=STATUS_LABELS.get(status, status))
        ws2.cell(row=i, column=2, value=count)

    # Sources
    source_start = row_start + len(stats.get("applications_by_status", {})) + 2
    ws2.cell(row=source_start, column=1, value="Jobquellen").font = Font(bold=True)
    for i, (source, count) in enumerate(
        stats.get("jobs_by_source", {}).items(), source_start + 1
    ):
        ws2.cell(row=i, column=1, value=source)
        ws2.cell(row=i, column=2, value=count)

    ws2.column_dimensions["A"].width = 25
    ws2.column_dimensions["B"].width = 15

    wb.save(str(output_path))
    logger.info("Excel Bewerbungsbericht erstellt: %s", output_path)
    return output_path
