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

logger = logging.getLogger("bewerbungs_assistent.export_report")

STATUS_LABELS = {
    "offen": "Offen",
    "beworben": "Beworben",
    "eingangsbestaetigung": "Eingangsbestätigung",
    "interview": "Interview",
    "zweitgespraech": "Zweitgespräch",
    "angebot": "Angebot",
    "abgelehnt": "Abgelehnt",
    "zurueckgezogen": "Zurückgezogen",
    "abgelaufen": "Abgelaufen",
}

STATUS_COLORS = {
    "beworben": (56, 189, 248),
    "interview": (251, 191, 36),
    "zweitgespraech": (251, 191, 36),
    "angebot": (52, 211, 153),
    "abgelehnt": (248, 113, 113),
    "zurueckgezogen": (148, 163, 184),
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


def generate_application_report(report_data: dict, profile: Optional[dict],
                                output_path: Path) -> Path:
    """Generate a comprehensive PDF Bewerbungsbericht."""
    from fpdf import FPDF

    apps = report_data.get("applications", [])
    stats = report_data.get("statistics", {})
    score_dist = report_data.get("score_distribution", {})
    unapplied = report_data.get("unapplied_high_score", [])
    date_range = report_data.get("date_range", {})

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # --- Title ---
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, _safe_text("Bewerbungsbericht"), ln=True, align="C")

    # Subtitle with name and date range
    pdf.set_font("Helvetica", "", 10)
    name = profile.get("name", "") if profile else ""
    subtitle_parts = []
    if name:
        subtitle_parts.append(name)
    if date_range.get("first") and date_range.get("last"):
        first = date_range["first"][:10]
        last = date_range["last"][:10]
        subtitle_parts.append(f"Zeitraum: {first} bis {last}")
    subtitle_parts.append(f"Erstellt: {datetime.now().strftime('%d.%m.%Y')}")
    pdf.cell(0, 6, _safe_text(" | ".join(subtitle_parts)), ln=True, align="C")
    pdf.ln(8)

    # --- 1. Zusammenfassung ---
    _section_header(pdf, "1. Zusammenfassung")
    total_apps = stats.get("total_applications", len(apps))
    active_jobs = stats.get("active_jobs", 0)
    dismissed_jobs = stats.get("dismissed_jobs", 0)
    avg_score = stats.get("avg_score", 0)
    max_score = stats.get("max_score", 0)
    interview_rate = stats.get("interview_rate", 0)
    offer_rate = stats.get("offer_rate", 0)

    summary_data = [
        ("Bewerbungen gesamt", str(total_apps)),
        ("Aktive Stellen analysiert", str(active_jobs)),
        ("Aussortierte Stellen", str(dismissed_jobs)),
        ("Stellen gesamt verglichen", str(active_jobs + dismissed_jobs)),
        ("Durchschn. Fit-Score", f"{avg_score}" if avg_score else "k.A."),
        ("Spitzen-Fit-Score", f"{max_score}" if max_score else "k.A."),
        ("Interview-Rate", f"{interview_rate}%"),
        ("Angebots-Rate", f"{offer_rate}%"),
    ]
    for label, value in summary_data:
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(80, 5, _safe_text(f"  {label}:"), border=0)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, _safe_text(value), ln=True)
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
            pdf.cell(15, 5, f"  {count}", ln=True)
    pdf.ln(4)

    # --- 3. Genutzte Jobquellen ---
    _section_header(pdf, "3. Genutzte Jobquellen")
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
            pdf.cell(15, 5, f"  {count}", ln=True)
        pdf.ln(4)

    # --- 5. Bewerbungsliste ---
    _section_header(pdf, "5. Bewerbungsliste")
    if apps:
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(22, 5, "Datum", border=1, fill=True)
        pdf.cell(50, 5, "Firma", border=1, fill=True)
        pdf.cell(60, 5, "Position", border=1, fill=True)
        pdf.cell(25, 5, "Status", border=1, fill=True, align="C")
        pdf.cell(20, 5, "Quelle", border=1, fill=True, align="C")
        pdf.cell(13, 5, "Score", border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_font("Helvetica", "", 7)
        for a in apps:
            date_str = (a.get("applied_at") or "")[:10]
            company = (a.get("company") or "")[:28]
            title = (a.get("title") or "")[:35]
            status = STATUS_LABELS.get(a.get("status", ""), a.get("status", ""))[:14]
            source = (a.get("job_source") or a.get("source", ""))[:12]
            score = a.get("score", "")
            if a.get("is_pinned"):
                score = f"*{score}" if score else "*"
            else:
                score = str(score) if score else ""

            pdf.cell(22, 4, _safe_text(date_str), border=1)
            pdf.cell(50, 4, _safe_text(company), border=1)
            pdf.cell(60, 4, _safe_text(title), border=1)
            pdf.cell(25, 4, _safe_text(status), border=1, align="C")
            pdf.cell(20, 4, _safe_text(source), border=1, align="C")
            pdf.cell(13, 4, _safe_text(str(score)), border=1, align="C")
            pdf.ln()
    pdf.ln(4)

    # --- 6. Nicht beworben trotz gutem Score ---
    if unapplied:
        _section_header(pdf, "6. Nicht beworben trotz gutem Fit-Score")
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(0, 5, _safe_text(
            f"  {len(unapplied)} Stellen mit Score >= 5 ohne Bewerbung:"
        ), ln=True)
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
                reason = j.get("dismiss_reason", "aussort.")[:12]
            pdf.cell(50, 4, _safe_text(company), border=1)
            pdf.cell(65, 4, _safe_text(title), border=1)
            pdf.cell(13, 4, str(j.get("score", "")), border=1, align="C")
            pdf.cell(20, 4, _safe_text((j.get("source") or "")[:12]), border=1, align="C")
            pdf.cell(22, 4, _safe_text((j.get("found_at") or "")[:10]), border=1, align="C")
            pdf.cell(20, 4, _safe_text(reason), border=1, align="C")
            pdf.ln()
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
            pdf.cell(0, 5, _safe_text(
                "  Haeufigste Begriffe in Stellen, auf die Sie sich beworben haben:"
            ), ln=True)
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

    # --- Footer ---
    pdf.set_font("Helvetica", "I", 7)
    pdf.cell(0, 5, _safe_text(
        f"Generiert mit PBP Bewerbungs-Assistent | {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    ), ln=True, align="C")
    pdf.cell(0, 4, _safe_text("* = manuell hinzugefuegte Stelle (gepinnt)"), ln=True, align="C")

    pdf.output(str(output_path))
    logger.info("PDF Bewerbungsbericht erstellt: %s", output_path)
    return output_path


def _section_header(pdf, title: str):
    """Draw a section header with background."""
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(33, 150, 243)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, _safe_text(f"  {title}"), ln=True, fill=True)
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
