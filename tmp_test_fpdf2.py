import sys
from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", "B", 14)

pdf.cell(55, 7, "Test")
x, y = pdf.get_x(), pdf.get_y()
pdf.set_x(x + 85)
pdf.cell(0, 7, "Test 2", new_x="LMARGIN", new_y="NEXT")

pdf.ln(5)
pdf.cell(0, 8, "Sub Title", new_x="LMARGIN", new_y="NEXT")
pdf.ln(2)

print(f"X before multi_cell: {pdf.get_x()}, Y: {pdf.get_y()}, epw: {pdf.epw}, r_margin: {pdf.r_margin}")
try:
    pdf.multi_cell(0, 6, "1. This is a very long text that should hopefully wrap correctly and not crash.", new_x="LMARGIN", new_y="NEXT")
    print("Success!")
except Exception as e:
    print(f"Error: {e}")

pdf.output("/tmp/test.pdf")
