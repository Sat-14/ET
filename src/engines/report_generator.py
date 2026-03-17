"""PDF Report Generator using fpdf2.

Generates shareable financial health reports:
- Money Health Score summary card
- Tax comparison report
- Goal progress report
- Full financial dashboard PDF
"""

from __future__ import annotations

import io
from datetime import date

from fpdf import FPDF


class FinancialReport(FPDF):
    """Custom PDF with branded header/footer."""

    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(33, 37, 41)
        self.cell(0, 10, "ET Money Mentor", new_x="LMARGIN", new_y="NEXT", align="L")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(108, 117, 125)
        self.cell(0, 5, f"Report generated on {date.today().strftime('%d %B %Y')}", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)
        # Divider line
        self.set_draw_color(76, 175, 80)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, "For educational purposes only. Consult a SEBI-registered advisor.", align="C")
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="R", new_x="LMARGIN", new_y="NEXT")

    def section_title(self, title: str):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(33, 150, 243)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def sub_title(self, title: str):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(33, 37, 41)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")

    def body_text(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(55, 55, 55)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def metric_row(self, label: str, value: str, highlight: bool = False):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(80, 80, 80)
        self.cell(90, 7, label)
        if highlight:
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(76, 175, 80)
        else:
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(33, 37, 41)
        self.cell(0, 7, value, new_x="LMARGIN", new_y="NEXT")

    def score_bar(self, label: str, score: float, max_score: float):
        """Draw a colored progress bar for a score dimension."""
        pct = (score / max_score * 100) if max_score > 0 else 0
        color = (76, 175, 80) if pct >= 70 else (255, 152, 0) if pct >= 40 else (244, 67, 54)

        self.set_font("Helvetica", "", 9)
        self.set_text_color(55, 55, 55)
        self.cell(55, 7, label)

        # Background bar
        x, y = self.get_x(), self.get_y()
        self.set_fill_color(230, 230, 230)
        self.rect(x, y + 1, 80, 5, "F")

        # Filled bar
        self.set_fill_color(*color)
        self.rect(x, y + 1, max(80 * pct / 100, 1), 5, "F")

        # Score text
        self.set_x(x + 85)
        self.set_font("Helvetica", "B", 9)
        self.cell(0, 7, f"{score:.0f}/{max_score:.0f} ({pct:.0f}%)", new_x="LMARGIN", new_y="NEXT")


def _format_inr(amount: float) -> str:
    """Format number in Indian lakh/crore style."""
    if amount >= 1_00_00_000:
        return f"Rs {amount / 1_00_00_000:.2f} Cr"
    elif amount >= 1_00_000:
        return f"Rs {amount / 1_00_000:.2f} L"
    else:
        return f"Rs {amount:,.0f}"


def generate_health_score_pdf(report_data: dict) -> bytes:
    """Generate Money Health Score PDF report.

    Args:
        report_data: Output from compute_money_health_score().to_dict()

    Returns:
        PDF file as bytes
    """
    pdf = FinancialReport()
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title
    pdf.section_title("Money Health Score Report")

    # Overall score
    score = report_data.get("overall_score", 0)
    grade = report_data.get("overall_grade", "N/A")
    grade_color = (76, 175, 80) if score >= 70 else (255, 152, 0) if score >= 40 else (244, 67, 54)

    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*grade_color)
    pdf.cell(50, 20, f"{score}/100")
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 20, f"Grade: {grade}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Dimension scores
    pdf.sub_title("Score Breakdown")
    pdf.ln(3)
    for dim in report_data.get("dimensions", []):
        pdf.score_bar(dim["name"], dim["score"], dim["max_score"])

    pdf.ln(5)

    # Top actions
    actions = report_data.get("top_actions", [])
    if actions:
        pdf.sub_title("Top Actions to Improve")
        pdf.ln(2)
        for i, action in enumerate(actions, 1):
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(55, 55, 55)
            pdf.multi_cell(0, 6, f"{i}. {action}")
        pdf.ln(3)

    # Dimension recommendations
    pdf.sub_title("Detailed Recommendations")
    pdf.ln(2)
    for dim in report_data.get("dimensions", []):
        recs = dim.get("recommendations", [])
        if recs:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(33, 37, 41)
            pdf.cell(0, 7, f"{dim['name']} ({dim['grade']})", new_x="LMARGIN", new_y="NEXT")
            for rec in recs:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(80, 80, 80)
                pdf.multi_cell(0, 5, f"  - {rec}")
            pdf.ln(2)

    return pdf.output()


def generate_tax_comparison_pdf(
    old_regime: dict,
    new_regime: dict,
    recommendation: str,
    saving: float,
) -> bytes:
    """Generate tax comparison PDF report."""
    pdf = FinancialReport()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.section_title("Tax Comparison: Old vs New Regime (FY 2025-26)")

    # Recommendation
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(76, 175, 80)
    pdf.cell(0, 10, f"Recommended: {recommendation.upper()} REGIME | Save {_format_inr(saving)}/year",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Side-by-side table
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(255, 255, 255)
    pdf.set_fill_color(33, 150, 243)
    pdf.cell(70, 8, "Item", fill=True)
    pdf.cell(55, 8, "Old Regime", fill=True, align="R")
    pdf.cell(55, 8, "New Regime", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    rows = [
        ("Gross Income", old_regime.get("gross_income", 0), new_regime.get("gross_income", 0)),
        ("Total Deductions", old_regime.get("total_deductions", 0), new_regime.get("total_deductions", 0)),
        ("Taxable Income", old_regime.get("taxable_income", 0), new_regime.get("taxable_income", 0)),
        ("Total Tax", old_regime.get("total_tax", 0), new_regime.get("total_tax", 0)),
        ("Monthly In-Hand", old_regime.get("monthly_in_hand", 0), new_regime.get("monthly_in_hand", 0)),
    ]

    for i, (label, old_val, new_val) in enumerate(rows):
        bg = (245, 245, 245) if i % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*bg)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(55, 55, 55)
        pdf.cell(70, 7, label, fill=True)
        pdf.cell(55, 7, _format_inr(old_val), fill=True, align="R")
        pdf.cell(55, 7, _format_inr(new_val), fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    # Effective rates
    pdf.metric_row("Old Regime Effective Rate", f"{old_regime.get('effective_rate', 0):.1f}%")
    pdf.metric_row("New Regime Effective Rate", f"{new_regime.get('effective_rate', 0):.1f}%")

    return pdf.output()


def generate_goal_report_pdf(goals: list[dict]) -> bytes:
    """Generate goal progress PDF report."""
    pdf = FinancialReport()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.section_title("Financial Goals Progress Report")

    for goal in goals:
        on_track = goal.get("on_track", False)
        status_color = (76, 175, 80) if on_track else (244, 67, 54)
        status_text = "On Track" if on_track else "Needs Attention"

        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*status_color)
        pdf.cell(0, 8, f"{goal.get('name', 'Goal')} - {status_text}", new_x="LMARGIN", new_y="NEXT")

        pdf.metric_row("Target (Inflation Adj)", _format_inr(goal.get("inflation_adjusted_target", 0)))
        pdf.metric_row("Current Corpus", _format_inr(goal.get("current_corpus", 0)))
        pdf.metric_row("Gap", _format_inr(goal.get("gap", 0)))
        pdf.metric_row("Required Monthly SIP", _format_inr(goal.get("required_monthly_sip", 0)))
        pdf.metric_row("Progress", f"{goal.get('progress_pct', 0):.0f}%", highlight=on_track)
        pdf.metric_row("Suggested Asset", goal.get("suggested_asset_class", "Equity MF"))

        notes = goal.get("notes", [])
        if notes:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(100, 100, 100)
            for note in notes:
                pdf.multi_cell(0, 5, f"  * {note}")

        pdf.ln(5)

    return pdf.output()


def generate_full_report_pdf(
    profile_name: str,
    health_data: dict | None = None,
    tax_data: dict | None = None,
    goal_data: list[dict] | None = None,
) -> bytes:
    """Generate a comprehensive financial report combining all sections."""
    pdf = FinancialReport()
    pdf.alias_nb_pages()
    pdf.add_page()

    # Cover
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(33, 37, 41)
    pdf.ln(20)
    pdf.cell(0, 15, "Financial Health Report", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(108, 117, 125)
    pdf.cell(0, 10, f"Prepared for: {profile_name}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, date.today().strftime("%d %B %Y"), align="C", new_x="LMARGIN", new_y="NEXT")

    # Health Score section
    if health_data:
        pdf.add_page()
        pdf.section_title("1. Money Health Score")

        score = health_data.get("overall_score", 0)
        grade = health_data.get("overall_grade", "N/A")

        pdf.set_font("Helvetica", "B", 24)
        grade_color = (76, 175, 80) if score >= 70 else (255, 152, 0) if score >= 40 else (244, 67, 54)
        pdf.set_text_color(*grade_color)
        pdf.cell(0, 15, f"Score: {score}/100 (Grade: {grade})", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        for dim in health_data.get("dimensions", []):
            pdf.score_bar(dim["name"], dim["score"], dim["max_score"])

        actions = health_data.get("top_actions", [])
        if actions:
            pdf.ln(5)
            pdf.sub_title("Priority Actions")
            for i, a in enumerate(actions, 1):
                pdf.body_text(f"{i}. {a}")

    # Tax section
    if tax_data:
        pdf.add_page()
        pdf.section_title("2. Tax Optimization")

        rec = tax_data.get("recommended_regime", "new")
        saving = tax_data.get("tax_saving", 0)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(76, 175, 80)
        pdf.cell(0, 10, f"Best: {rec.upper()} REGIME | Annual saving: {_format_inr(saving)}",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        old = tax_data.get("old_regime", {})
        new = tax_data.get("new_regime", {})
        pdf.metric_row("Old Regime Tax", _format_inr(old.get("total_tax", 0)))
        pdf.metric_row("New Regime Tax", _format_inr(new.get("total_tax", 0)))
        pdf.metric_row("Old Monthly In-Hand", _format_inr(old.get("monthly_in_hand", 0)))
        pdf.metric_row("New Monthly In-Hand", _format_inr(new.get("monthly_in_hand", 0)))

    # Goals section
    if goal_data:
        pdf.add_page()
        pdf.section_title("3. Goal Progress")

        for goal in goal_data:
            on_track = goal.get("on_track", False)
            color = (76, 175, 80) if on_track else (244, 67, 54)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*color)
            status = "On Track" if on_track else "Needs Attention"
            pdf.cell(0, 8, f"{goal.get('name', '')} - {status}", new_x="LMARGIN", new_y="NEXT")
            pdf.metric_row("Target", _format_inr(goal.get("inflation_adjusted_target", 0)))
            pdf.metric_row("Required SIP", _format_inr(goal.get("required_monthly_sip", 0)))
            pdf.metric_row("Progress", f"{goal.get('progress_pct', 0):.0f}%")
            pdf.ln(3)

    return pdf.output()
