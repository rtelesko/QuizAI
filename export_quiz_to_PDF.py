# export_quiz_to_PDF.py
from pathlib import Path

from fpdf import FPDF, HTMLMixin

FONT_DIR = Path(__file__).parent / "fonts"


class QuizPDF(FPDF, HTMLMixin):
    def __init__(self, quiz_title):
        super().__init__()
        self.quiz_title = quiz_title
        self.set_auto_page_break(auto=True, margin=15)

        # Register Unicode TTFs
        self.add_font("DejaVu", "", str(FONT_DIR / "DejaVuSans.ttf"), uni=True)
        self.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"), uni=True)
        self.add_font("DejaVu", "I", str(FONT_DIR / "DejaVuSans-Oblique.ttf"), uni=True)
        self.add_font("DejaVu", "BI", str(FONT_DIR / "DejaVuSans-BoldOblique.ttf"), uni=True)

    def header(self):
        self.set_font("DejaVu", "B", 14)  # was Helvetica
        self.cell(0, 10, self.quiz_title, ln=True, align="C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "I", 8)  # was Helvetica
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def generate_quiz_pdf(quiz_data, quiz_title="Python quiz and solutions", output_path=None):
    pdf = QuizPDF(quiz_title)
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font("DejaVu", size=12)  # was Helvetica

    # Quiz Questions Section
    avail = pdf.w - pdf.l_margin - pdf.r_margin
    indent = 4

    for idx, q in enumerate(quiz_data, start=1):
        pdf.set_font("DejaVu", "B", 12)  # was Helvetica
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(avail, 8, f"{idx}. {q['question']}")

        pdf.set_font("DejaVu", "", 11)  # was Helvetica
        if q.get("options"):
            for opt in q["options"]:
                option_width = avail - indent
                if option_width > 0:
                    pdf.set_x(pdf.l_margin + indent)
                    pdf.multi_cell(option_width, 6, f"- {opt}")
        pdf.ln(3)

    # Answers and Explanations Section
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 14)  # was Helvetica
    pdf.cell(0, 10, "Answers & Explanations", ln=True)
    pdf.ln(4)

    for idx, q in enumerate(quiz_data, start=1):
        pdf.set_font("DejaVu", "B", 12)  # was Helvetica
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 7, f"{idx}. Correct Answer: {q['answer']}")
        pdf.set_font("DejaVu", "", 11)  # was Helvetica
        explanation = q.get("explanation", "No explanation provided.")
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 6, f"Explanation: {explanation}")
        pdf.ln(3)

    if output_path:
        pdf.output(output_path)
        return output_path

    # --- Changed section: make return robust across fpdf versions ---
    result = pdf.output(dest="S")
    if isinstance(result, (bytes, bytearray)):
        # fpdf2 returns bytes/bytearray: pass through as bytes for Streamlit
        return bytes(result)
    # Older PyFPDF returned str: encode to bytes
    return result.encode("latin-1")
