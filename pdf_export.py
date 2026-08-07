"""One-click PDF export of a digest — for sharing in meetings or offline
reading. Uses fpdf2 (pure Python, no system dependencies like wkhtmltopdf,
so it works fine on Render's free tier without extra build steps).

Deliberately plain-text only: no emoji, no custom fonts. fpdf2's built-in
core fonts (Helvetica etc.) don't cover most Unicode emoji, and pulling in
a full Unicode font just for the category icons isn't worth the size/
complexity for an internal report document.
"""
from fpdf import FPDF
from fpdf.enums import XPos, YPos

CATEGORY_LABELS = {"security": "SECURITY", "privacy": "PRIVACY", "compliance": "COMPLIANCE"}


class DigestPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "Security, Privacy & Compliance Digest", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(90, 90, 90)
        self.cell(0, 6, f"Briefing date: {self.run_date}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)
        self.ln(2)
        self.set_draw_color(180, 180, 180)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def _clean(text):
    """fpdf2's core fonts are latin-1 only — swap common problem characters
    (smart quotes, em dashes, bullets from feed text) for plain ASCII
    equivalents rather than letting them raise or silently vanish."""
    if not text:
        return ""
    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u2022": "-",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", "replace").decode("latin-1")


def build_pdf(articles, run_date):
    """Returns PDF bytes for the given list of article dicts (already
    filtered/sorted by the caller — this just lays them out)."""
    pdf = DigestPDF()
    pdf.run_date = run_date
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    by_category = {}
    for a in articles:
        by_category.setdefault(a["category"], []).append(a)

    for category in ("security", "privacy", "compliance"):
        items = by_category.get(category, [])
        if not items:
            continue

        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(20, 20, 20)
        pdf.cell(0, 8, f"{CATEGORY_LABELS[category]} ({len(items)})", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)

        for a in items:
            priority = a.get("priority", "Low")
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(163, 44, 33) if priority == "High" else (
                pdf.set_text_color(156, 107, 20) if priority == "Medium" else pdf.set_text_color(46, 94, 69)
            )
            pdf.cell(0, 6, f"[{priority.upper()}]", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(10, 10, 10)
            pdf.multi_cell(0, 6, _clean(a.get("title", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 5, _clean(f"{a.get('source', '')} | {a.get('published', '')}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 5, _clean(a.get("summary", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            if a.get("deadline"):
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(27, 58, 92)
                pdf.cell(0, 5, _clean(f"Deadline: {a['deadline']}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            link = a.get("link", "")
            if link:
                pdf.set_font("Helvetica", "U", 8)
                pdf.set_text_color(30, 80, 160)
                pdf.multi_cell(0, 5, _clean(link), link=link, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            pdf.set_text_color(0, 0, 0)
            pdf.ln(3)

    return bytes(pdf.output())
