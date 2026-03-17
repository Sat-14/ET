"""Form-16 and Salary Slip Parser.

Extracts salary breakup, deductions, and tax details from
Form-16 PDFs and salary slip inputs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from src.models.user import SalaryBreakup, Deductions


def parse_form16_pdf(file_path: str | Path) -> dict:
    """Parse a Form-16 PDF and extract salary/tax details.

    Uses pdfplumber to extract text and tables from Form-16.
    Returns a dict with salary breakup, deductions, and TDS info.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber is required. Install with: pip install pdfplumber")

    result = {
        "employer_name": "",
        "employer_tan": "",
        "employee_name": "",
        "employee_pan": "",
        "assessment_year": "",
        "gross_salary": 0,
        "exemptions": {},
        "deductions": {},
        "taxable_income": 0,
        "tax_payable": 0,
        "tds_deducted": 0,
        "raw_text": "",
    }

    with pdfplumber.open(str(file_path)) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

            # Also try extracting tables
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if row:
                        cleaned = [str(cell).strip() if cell else "" for cell in row]
                        full_text += " | ".join(cleaned) + "\n"

        result["raw_text"] = full_text

    # Extract using regex patterns common in Form-16
    _extract_basic_info(full_text, result)
    _extract_salary_details(full_text, result)
    _extract_deductions(full_text, result)
    _extract_tax_details(full_text, result)

    return result


def _find_amount(text: str, pattern: str) -> float:
    """Find a monetary amount near a label pattern."""
    match = re.search(pattern + r"[:\s]*[\u20b9Rs.]*\s*([\d,]+(?:\.\d{2})?)", text, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(",", ""))
    return 0.0


def _extract_basic_info(text: str, result: dict) -> None:
    """Extract employer/employee basic info."""
    pan_match = re.search(r"PAN[:\s]*([A-Z]{5}[0-9]{4}[A-Z])", text)
    if pan_match:
        result["employee_pan"] = pan_match.group(1)

    tan_match = re.search(r"TAN[:\s]*([A-Z]{4}[0-9]{5}[A-Z])", text)
    if tan_match:
        result["employer_tan"] = tan_match.group(1)

    ay_match = re.search(r"Assessment\s*Year[:\s]*(20\d{2}[-–]2?\d{1,2})", text)
    if ay_match:
        result["assessment_year"] = ay_match.group(1)


def _extract_salary_details(text: str, result: dict) -> None:
    """Extract salary breakup details."""
    result["gross_salary"] = _find_amount(text, r"Gross\s*(?:Total\s*)?(?:Salary|Income)")

    result["exemptions"] = {
        "hra": _find_amount(text, r"(?:HRA|House\s*Rent\s*Allowance)"),
        "lta": _find_amount(text, r"(?:LTA|Leave\s*Travel)"),
        "standard_deduction": _find_amount(text, r"Standard\s*Deduction"),
    }


def _extract_deductions(text: str, result: dict) -> None:
    """Extract Chapter VI-A deductions."""
    result["deductions"] = {
        "80C": _find_amount(text, r"(?:80C|80\s*C)[^CD]"),
        "80CCC": _find_amount(text, r"80CCC"),
        "80CCD_1": _find_amount(text, r"80CCD\s*\(1\)"),
        "80CCD_1B": _find_amount(text, r"80CCD\s*\(1B\)"),
        "80CCD_2": _find_amount(text, r"80CCD\s*\(2\)"),
        "80D": _find_amount(text, r"80D"),
        "80E": _find_amount(text, r"80E"),
        "80G": _find_amount(text, r"80G"),
        "80TTA": _find_amount(text, r"80TTA"),
        "24b": _find_amount(text, r"(?:24\s*\(b\)|24b|Section\s*24)"),
    }


def _extract_tax_details(text: str, result: dict) -> None:
    """Extract tax computation details."""
    result["taxable_income"] = _find_amount(text, r"(?:Total\s*)?Taxable\s*Income")
    result["tax_payable"] = _find_amount(text, r"(?:Total\s*)?Tax\s*(?:Payable|on)")
    result["tds_deducted"] = _find_amount(text, r"(?:TDS|Tax\s*Deducted)")


def form16_to_salary_breakup(parsed_data: dict) -> SalaryBreakup:
    """Convert parsed Form-16 data to SalaryBreakup model."""
    gross = parsed_data.get("gross_salary", 0)
    exemptions = parsed_data.get("exemptions", {})

    # Estimate breakup from gross (common Indian salary structure)
    basic = gross * 0.40  # ~40% of CTC is basic
    hra = exemptions.get("hra", gross * 0.20)
    special = gross - basic - hra

    return SalaryBreakup(
        basic=basic,
        hra=hra,
        special_allowance=max(special, 0),
        lta=exemptions.get("lta", 0),
    )


def form16_to_deductions(parsed_data: dict) -> Deductions:
    """Convert parsed Form-16 data to Deductions model."""
    ded_data = parsed_data.get("deductions", {})

    return Deductions(
        employee_pf=ded_data.get("80CCD_1", 0),
        elss=0,  # Can't distinguish within 80C
        ppf=0,
        lic_premium=0,
        nps_additional=ded_data.get("80CCD_1B", 0),
        self_health_insurance=ded_data.get("80D", 0),
        education_loan_interest=ded_data.get("80E", 0),
        donations=ded_data.get("80G", 0),
        savings_interest=ded_data.get("80TTA", 0),
        home_loan_interest=ded_data.get("24b", 0),
    )


def parse_salary_input(salary_data: dict) -> SalaryBreakup:
    """Parse salary from manual user input.

    Accepts a flat dict with salary components.
    """
    return SalaryBreakup(
        basic=float(salary_data.get("basic", 0)),
        da=float(salary_data.get("da", 0)),
        hra=float(salary_data.get("hra", 0)),
        special_allowance=float(salary_data.get("special_allowance", 0)),
        lta=float(salary_data.get("lta", 0)),
        medical_allowance=float(salary_data.get("medical_allowance", 0)),
        other_allowance=float(salary_data.get("other_allowance", 0)),
        employer_pf=float(salary_data.get("employer_pf", 0)),
        employer_nps=float(salary_data.get("employer_nps", 0)),
        professional_tax=float(salary_data.get("professional_tax", 0)),
        bonus=float(salary_data.get("bonus", 0)),
    )
