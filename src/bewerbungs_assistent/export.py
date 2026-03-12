"""PDF/DOCX Export Module for Bewerbungs-Assistent.

Generates professional CVs and cover letters in PDF and DOCX format.
Uses fpdf2 for PDF (pure Python, no system deps) and python-docx for DOCX.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bewerbungs_assistent.export")


def generate_cv_docx(profile: dict, output_path: Path) -> Path:
    """Generate a professional CV as Word document."""
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)

    # Header
    heading = doc.add_heading(profile.get("name", "Lebenslauf"), level=0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Contact
    contact = []
    if profile.get("email"): contact.append(profile["email"])
    if profile.get("phone"): contact.append(profile["phone"])
    if profile.get("city"):
        addr = f"{profile.get('address', '')} " if profile.get("address") else ""
        addr += f"{profile.get('plz', '')} {profile['city']}".strip()
        contact.append(addr.strip())
    if contact:
        p = doc.add_paragraph(" | ".join(contact))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Summary
    if profile.get("summary"):
        doc.add_heading("Profil", level=1)
        doc.add_paragraph(profile["summary"])

    # Work experience
    positions = profile.get("positions", [])
    if positions:
        doc.add_heading("Berufserfahrung", level=1)
        for pos in positions:
            end = "heute" if pos.get("is_current") else (pos.get("end_date") or "")
            period = f"{pos.get('start_date', '')} - {end}"
            emp_type = pos.get("employment_type", "")
            type_str = f" ({emp_type})" if emp_type and emp_type != "festanstellung" else ""

            p = doc.add_paragraph()
            run = p.add_run(f"{pos.get('title', '')} bei {pos.get('company', '')}{type_str}")
            run.bold = True
            run.font.size = Pt(11)

            p2 = doc.add_paragraph(period)
            if pos.get("location"):
                p2.add_run(f" | {pos['location']}")

            if pos.get("tasks"):
                doc.add_paragraph(f"Aufgaben: {pos['tasks']}")
            if pos.get("achievements"):
                doc.add_paragraph(f"Erfolge: {pos['achievements']}")
            if pos.get("technologies"):
                doc.add_paragraph(f"Technologien: {pos['technologies']}")

            for proj in pos.get("projects", []):
                p = doc.add_paragraph()
                run = p.add_run(f"Projekt: {proj.get('name', '')}")
                run.bold = True
                if proj.get("role"):
                    p.add_run(f" ({proj['role']})")
                if proj.get("result"):
                    doc.add_paragraph(f"Ergebnis: {proj['result']}", style="List Bullet")

    # Education
    education = profile.get("education", [])
    if education:
        doc.add_heading("Ausbildung", level=1)
        for edu in education:
            p = doc.add_paragraph()
            degree = f"{edu.get('degree', '')} {edu.get('field_of_study', '')}".strip()
            run = p.add_run(degree or edu.get("institution", ""))
            run.bold = True
            line = edu.get("institution", "")
            start = edu.get("start_date", "")
            end = edu.get("end_date", "")
            if start or end:
                line += f" | {start} - {end}"
            if edu.get("grade"):
                line += f" | Note: {edu['grade']}"
            doc.add_paragraph(line)

    # Skills
    skills = profile.get("skills", [])
    if skills:
        doc.add_heading("Kompetenzen", level=1)
        by_cat = {}
        for s in skills:
            by_cat.setdefault(s.get("category", "sonstige"), []).append(s)
        cat_labels = {
            "fachlich": "Fachlich", "methodisch": "Methodisch",
            "soft_skill": "Soft Skills", "sprache": "Sprachen",
            "tool": "Tools / Software",
        }
        for cat, items in by_cat.items():
            label = cat_labels.get(cat, cat)
            names = ", ".join(s["name"] for s in items)
            doc.add_paragraph(f"{label}: {names}")

    doc.save(str(output_path))
    logger.info("CV DOCX generated: %s", output_path)
    return output_path


def generate_tailored_cv_docx(
    profile: dict, job_title: str, job_description: str, output_path: Path
) -> Path:
    """Generate a CV tailored for a specific job as Word document.

    Reorders skills and highlights relevant experience based on the job.
    """
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    # Determine relevant keywords from job
    job_text = f"{job_title} {job_description}".lower()
    job_keywords = set(job_text.split())

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)

    # Header
    heading = doc.add_heading(profile.get("name", "Lebenslauf"), level=0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Contact
    contact = []
    if profile.get("email"): contact.append(profile["email"])
    if profile.get("phone"): contact.append(profile["phone"])
    if profile.get("city"):
        addr = f"{profile.get('address', '')} " if profile.get("address") else ""
        addr += f"{profile.get('plz', '')} {profile['city']}".strip()
        contact.append(addr.strip())
    if contact:
        p = doc.add_paragraph(" | ".join(contact))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Targeted summary — mention the target position
    doc.add_heading("Profil", level=1)
    summary = profile.get("summary", "")
    if summary:
        doc.add_paragraph(summary)

    # Skills — relevant first, grouped by category
    skills = profile.get("skills", [])
    if skills:
        doc.add_heading("Kompetenzen", level=1)

        def skill_relevance(s):
            name_lower = s.get("name", "").lower()
            # Higher relevance if skill name appears in job text
            if name_lower in job_text:
                return 0
            # Check partial match
            if any(kw in name_lower or name_lower in kw for kw in job_keywords if len(kw) > 3):
                return 1
            return 2

        by_cat = {}
        for s in skills:
            by_cat.setdefault(s.get("category", "sonstige"), []).append(s)

        cat_labels = {
            "fachlich": "Fachlich", "methodisch": "Methodisch",
            "soft_skill": "Soft Skills", "sprache": "Sprachen",
            "tool": "Tools / Software",
        }

        # Sort categories: put those with relevant skills first
        def cat_relevance(cat_items):
            cat, items = cat_items
            return min((skill_relevance(s) for s in items), default=2)

        for cat, items in sorted(by_cat.items(), key=cat_relevance):
            label = cat_labels.get(cat, cat)
            # Sort skills within category: relevant first, then by level desc
            sorted_items = sorted(items, key=lambda s: (skill_relevance(s), -(s.get("level", 0) or 0)))
            names = []
            for s in sorted_items:
                name = s["name"]
                level = s.get("level", 0)
                if level and level >= 4:
                    name += " (Experte)" if level == 5 else " (Fortgeschritten)"
                names.append(name)
            doc.add_paragraph(f"{label}: {', '.join(names)}")

    # Work experience — relevant positions first
    positions = profile.get("positions", [])
    if positions:
        doc.add_heading("Berufserfahrung", level=1)

        def pos_relevance(pos):
            pos_text = f"{pos.get('title', '')} {pos.get('tasks', '')} {pos.get('technologies', '')} {pos.get('achievements', '')}".lower()
            hits = sum(1 for kw in job_keywords if len(kw) > 3 and kw in pos_text)
            return -hits  # Negative so most relevant sorts first

        sorted_positions = sorted(positions, key=pos_relevance)

        for pos in sorted_positions:
            end = "heute" if pos.get("is_current") else (pos.get("end_date") or "")
            period = f"{pos.get('start_date', '')} - {end}"
            emp_type = pos.get("employment_type", "")
            type_str = f" ({emp_type})" if emp_type and emp_type != "festanstellung" else ""

            p = doc.add_paragraph()
            run = p.add_run(f"{pos.get('title', '')} bei {pos.get('company', '')}{type_str}")
            run.bold = True
            run.font.size = Pt(11)

            p2 = doc.add_paragraph(period)
            if pos.get("location"):
                p2.add_run(f" | {pos['location']}")

            if pos.get("tasks"):
                doc.add_paragraph(f"Aufgaben: {pos['tasks']}")
            if pos.get("achievements"):
                doc.add_paragraph(f"Erfolge: {pos['achievements']}")
            if pos.get("technologies"):
                doc.add_paragraph(f"Technologien: {pos['technologies']}")

            for proj in pos.get("projects", []):
                p = doc.add_paragraph()
                run = p.add_run(f"Projekt: {proj.get('name', '')}")
                run.bold = True
                if proj.get("role"):
                    p.add_run(f" ({proj['role']})")
                if proj.get("result"):
                    doc.add_paragraph(f"Ergebnis: {proj['result']}", style="List Bullet")

    # Education
    education = profile.get("education", [])
    if education:
        doc.add_heading("Ausbildung", level=1)
        for edu in education:
            p = doc.add_paragraph()
            degree = f"{edu.get('degree', '')} {edu.get('field_of_study', '')}".strip()
            run = p.add_run(degree or edu.get("institution", ""))
            run.bold = True
            line = edu.get("institution", "")
            start = edu.get("start_date", "")
            end = edu.get("end_date", "")
            if start or end:
                line += f" | {start} - {end}"
            if edu.get("grade"):
                line += f" | Note: {edu['grade']}"
            doc.add_paragraph(line)

    doc.save(str(output_path))
    logger.info("Tailored CV DOCX generated: %s", output_path)
    return output_path


def generate_cv_pdf(profile: dict, output_path: Path) -> Path:
    """Generate a professional CV as PDF."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Try Unicode font, fallback to built-in
    try:
        pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        pdf.add_font("DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        font_name = "DejaVu"
    except Exception as e:
        logger.debug("DejaVu-Font nicht verfuegbar, nutze Helvetica: %s", e)
        font_name = "Helvetica"

    epw = pdf.epw  # effective page width

    def safe(text):
        if not text: return ""
        if font_name == "Helvetica":
            for k, v in {"\u00e4": "ae", "\u00f6": "oe", "\u00fc": "ue",
                         "\u00c4": "Ae", "\u00d6": "Oe", "\u00dc": "Ue",
                         "\u00df": "ss", "\u2013": "-", "\u2014": "-"}.items():
                text = text.replace(k, v)
        return text

    def next_line():
        """Move cursor to left margin on next line."""
        pdf.set_x(pdf.l_margin)

    # Header
    pdf.set_font(font_name, "B", 18)
    pdf.cell(epw, 12, safe(profile.get("name", "Lebenslauf")),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    contact = []
    if profile.get("email"): contact.append(profile["email"])
    if profile.get("phone"): contact.append(profile["phone"])
    if profile.get("city"): contact.append(f"{profile.get('plz', '')} {profile['city']}".strip())
    if contact:
        pdf.set_font(font_name, "", 9)
        pdf.cell(epw, 6, safe(" | ".join(contact)),
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(4)

    def section(title):
        pdf.set_font(font_name, "B", 13)
        pdf.cell(epw, 8, safe(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(58, 134, 255)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(2)

    # Summary
    if profile.get("summary"):
        section("Profil")
        pdf.set_font(font_name, "", 10)
        next_line()
        pdf.multi_cell(epw, 5, safe(profile["summary"]))
        pdf.ln(3)

    # Positions
    positions = profile.get("positions", [])
    if positions:
        section("Berufserfahrung")
        for pos in positions:
            end = "heute" if pos.get("is_current") else (pos.get("end_date") or "")
            pdf.set_font(font_name, "B", 11)
            pdf.cell(epw, 6, safe(f"{pos.get('title', '')} bei {pos.get('company', '')}"),
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font(font_name, "", 9)
            loc = f" | {pos['location']}" if pos.get("location") else ""
            pdf.cell(epw, 5, safe(f"{pos.get('start_date', '')} - {end}{loc}"),
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font(font_name, "", 10)
            if pos.get("tasks"):
                next_line()
                pdf.multi_cell(epw, 5, safe(f"Aufgaben: {pos['tasks']}"))
            if pos.get("achievements"):
                next_line()
                pdf.multi_cell(epw, 5, safe(f"Erfolge: {pos['achievements']}"))
            if pos.get("technologies"):
                next_line()
                pdf.multi_cell(epw, 5, safe(f"Technologien: {pos['technologies']}"))
            for proj in pos.get("projects", []):
                pdf.set_font(font_name, "B", 10)
                role = f" ({proj['role']})" if proj.get("role") else ""
                pdf.cell(epw, 5, safe(f"  Projekt: {proj.get('name', '')}{role}"),
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                if proj.get("result"):
                    pdf.set_font(font_name, "", 9)
                    next_line()
                    pdf.multi_cell(epw, 4, safe(f"    Ergebnis: {proj['result']}"))
            pdf.ln(3)

    # Education
    education = profile.get("education", [])
    if education:
        section("Ausbildung")
        for edu in education:
            pdf.set_font(font_name, "B", 10)
            degree = f"{edu.get('degree', '')} {edu.get('field_of_study', '')}".strip()
            pdf.cell(epw, 5, safe(degree or edu.get("institution", "")),
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font(font_name, "", 9)
            line = edu.get("institution", "")
            if edu.get("start_date") or edu.get("end_date"):
                line += f" | {edu.get('start_date', '')} - {edu.get('end_date', '')}"
            if edu.get("grade"): line += f" | Note: {edu['grade']}"
            pdf.cell(epw, 5, safe(line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)

    # Skills
    skills = profile.get("skills", [])
    if skills:
        section("Kompetenzen")
        by_cat = {}
        for s in skills:
            by_cat.setdefault(s.get("category", "sonstige"), []).append(s)
        cat_labels = {"fachlich": "Fachlich", "methodisch": "Methodisch",
                      "soft_skill": "Soft Skills", "sprache": "Sprachen", "tool": "Tools / Software"}
        pdf.set_font(font_name, "", 10)
        for cat, items in by_cat.items():
            label = cat_labels.get(cat, cat)
            names = ", ".join(s["name"] for s in items)
            next_line()
            pdf.multi_cell(epw, 5, safe(f"{label}: {names}"))

    # Footer
    pdf.set_y(-20)
    pdf.set_font(font_name, "", 7)
    pdf.cell(epw, 4, safe(f"Erstellt am {datetime.now().strftime('%d.%m.%Y')}"), align="R")

    pdf.output(str(output_path))
    logger.info("CV PDF generated: %s", output_path)
    return output_path


def generate_cover_letter_docx(
    profile: dict, text: str, stelle: str, firma: str, output_path: Path
) -> Path:
    """Generate a cover letter as Word document."""
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    # Sender
    for val in [profile.get("name"), profile.get("address"),
                f"{profile.get('plz', '')} {profile.get('city', '')}".strip(),
                profile.get("phone"), profile.get("email")]:
        if val and val.strip():
            p = doc.add_paragraph(val)
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    doc.add_paragraph()
    p = doc.add_paragraph(datetime.now().strftime("%d.%m.%Y"))
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph()

    # Subject
    p = doc.add_paragraph()
    run = p.add_run(f"Bewerbung als {stelle}")
    run.bold = True
    run.font.size = Pt(12)
    doc.add_paragraph()

    # Body
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if paragraph:
            doc.add_paragraph(paragraph)

    doc.save(str(output_path))
    logger.info("Cover letter DOCX generated: %s", output_path)
    return output_path


def generate_cover_letter_pdf(
    profile: dict, text: str, stelle: str, firma: str, output_path: Path
) -> Path:
    """Generate a cover letter as PDF."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    try:
        pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        pdf.add_font("DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        font_name = "DejaVu"
    except Exception as e:
        logger.debug("DejaVu-Font nicht verfuegbar, nutze Helvetica: %s", e)
        font_name = "Helvetica"

    epw = pdf.epw

    def safe(t):
        if not t: return ""
        if font_name == "Helvetica":
            for k, v in {"\u00e4": "ae", "\u00f6": "oe", "\u00fc": "ue",
                         "\u00c4": "Ae", "\u00d6": "Oe", "\u00dc": "Ue", "\u00df": "ss"}.items():
                t = t.replace(k, v)
        return t

    # Sender
    pdf.set_font(font_name, "", 10)
    for val in [profile.get("name"), profile.get("address"),
                f"{profile.get('plz', '')} {profile.get('city', '')}".strip(),
                profile.get("phone"), profile.get("email")]:
        if val and val.strip():
            pdf.cell(epw, 5, safe(val), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
    pdf.ln(8)

    pdf.cell(epw, 5, datetime.now().strftime("%d.%m.%Y"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
    pdf.ln(8)

    # Subject
    pdf.set_font(font_name, "B", 12)
    pdf.cell(epw, 7, safe(f"Bewerbung als {stelle}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    # Body
    pdf.set_font(font_name, "", 11)
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if paragraph:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(epw, 5.5, safe(paragraph))
            pdf.ln(3)

    pdf.output(str(output_path))
    logger.info("Cover letter PDF generated: %s", output_path)
    return output_path
