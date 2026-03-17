"""EMI & Loan Optimizer Engine.

Uses pyxirr (Rust-powered) for core financial math: PMT, FV, IPMT, PPMT, NPER.
Falls back to numpy-financial if pyxirr unavailable.

Handles:
- EMI calculation for any loan (home, car, personal, education)
- Prepayment impact analysis (how much interest you save)
- Prepay vs Invest decision engine
- Loan comparison (multiple offers side-by-side)
- Amortization schedule generation
"""

from __future__ import annotations

from dataclasses import dataclass

# Use pyxirr (Rust, fast) with numpy-financial fallback
try:
    from pyxirr import pmt as _pmt, fv as _fv, ipmt as _ipmt, ppmt as _ppmt, nper as _nper

    def pmt(rate, nper, pv, fv=0):
        return -_pmt(rate, nper, pv, fv)

    def fv(rate, nper, pmt_val, pv=0):
        return -_fv(rate, nper, pmt_val, pv)

    def ipmt(rate, per, nper, pv):
        return -_ipmt(rate, per, nper, pv)

    def ppmt(rate, per, nper, pv):
        return -_ppmt(rate, per, nper, pv)

    def nper(rate, pmt_val, pv, fv=0):
        return _nper(rate, -pmt_val, pv, fv)

except ImportError:
    try:
        import numpy_financial as npf

        def pmt(rate, nper, pv, fv=0):
            return -npf.pmt(rate, nper, pv, fv)

        def fv(rate, nper, pmt_val, pv=0):
            return -npf.fv(rate, nper, -pmt_val, pv)

        def ipmt(rate, per, nper, pv):
            return -npf.ipmt(rate, per, nper, pv)

        def ppmt(rate, per, nper, pv):
            return -npf.ppmt(rate, per, nper, pv)

        def nper(rate, pmt_val, pv, fv=0):
            return npf.nper(rate, -pmt_val, pv, fv)

    except ImportError:
        # Pure Python fallback
        def pmt(rate, n, pv, fv_val=0):
            if rate == 0:
                return pv / n
            return pv * rate * (1 + rate) ** n / ((1 + rate) ** n - 1)

        def fv(rate, n, pmt_val, pv=0):
            if rate == 0:
                return pv + pmt_val * n
            return pv * (1 + rate) ** n + pmt_val * ((1 + rate) ** n - 1) / rate

        def ipmt(rate, per, n, pv):
            bal = pv
            emi = pmt(rate, n, pv)
            for _ in range(1, per):
                interest = bal * rate
                bal -= (emi - interest)
            return bal * rate

        def ppmt(rate, per, n, pv):
            return pmt(rate, n, pv) - ipmt(rate, per, n, pv)

        def nper(rate, pmt_val, pv, fv_val=0):
            if rate == 0:
                return pv / pmt_val
            import math
            return math.log(pmt_val / (pmt_val - pv * rate)) / math.log(1 + rate)


@dataclass
class EMIResult:
    loan_amount: float
    interest_rate: float  # Annual %
    tenure_months: int
    monthly_emi: float
    total_payment: float
    total_interest: float
    interest_to_principal_ratio: float

    def to_dict(self) -> dict:
        return {
            "loan_amount": round(self.loan_amount),
            "interest_rate_pct": self.interest_rate,
            "tenure_months": self.tenure_months,
            "tenure_years": round(self.tenure_months / 12, 1),
            "monthly_emi": round(self.monthly_emi),
            "total_payment": round(self.total_payment),
            "total_interest": round(self.total_interest),
            "interest_to_principal_ratio": round(self.interest_to_principal_ratio, 2),
        }


@dataclass
class PrepaymentImpact:
    original_tenure_months: int
    new_tenure_months: int
    months_saved: int
    original_total_interest: float
    new_total_interest: float
    interest_saved: float
    prepayment_amount: float

    def to_dict(self) -> dict:
        return {
            "prepayment_amount": round(self.prepayment_amount),
            "original_tenure_months": self.original_tenure_months,
            "new_tenure_months": self.new_tenure_months,
            "months_saved": self.months_saved,
            "years_saved": round(self.months_saved / 12, 1),
            "original_total_interest": round(self.original_total_interest),
            "new_total_interest": round(self.new_total_interest),
            "interest_saved": round(self.interest_saved),
        }


@dataclass
class PrepayVsInvestResult:
    prepay_interest_saved: float
    invest_expected_return: float
    recommendation: str  # "prepay" or "invest"
    net_benefit: float  # How much better the recommended option is
    details: str

    def to_dict(self) -> dict:
        return {
            "prepay_interest_saved": round(self.prepay_interest_saved),
            "invest_expected_return": round(self.invest_expected_return),
            "recommendation": self.recommendation,
            "net_benefit": round(self.net_benefit),
            "details": self.details,
        }


@dataclass
class AmortizationEntry:
    month: int
    emi: float
    principal: float
    interest: float
    balance: float


def calculate_emi(
    principal: float,
    annual_rate: float,
    tenure_months: int,
) -> EMIResult:
    """Calculate EMI using pyxirr's PMT function (Rust-powered)."""
    if principal <= 0 or tenure_months <= 0:
        return EMIResult(principal, annual_rate, tenure_months, 0, 0, 0, 0)

    if annual_rate == 0:
        emi = principal / tenure_months
        return EMIResult(principal, 0, tenure_months, emi, principal, 0, 0)

    r = annual_rate / 100 / 12  # Monthly rate
    emi = pmt(r, tenure_months, principal)
    total_payment = emi * tenure_months
    total_interest = total_payment - principal
    ratio = total_interest / principal if principal > 0 else 0

    return EMIResult(
        loan_amount=principal,
        interest_rate=annual_rate,
        tenure_months=tenure_months,
        monthly_emi=emi,
        total_payment=total_payment,
        total_interest=total_interest,
        interest_to_principal_ratio=ratio,
    )


def generate_amortization_schedule(
    principal: float,
    annual_rate: float,
    tenure_months: int,
) -> list[AmortizationEntry]:
    """Generate month-by-month amortization schedule using pyxirr IPMT/PPMT."""
    emi_result = calculate_emi(principal, annual_rate, tenure_months)
    emi_val = emi_result.monthly_emi
    r = annual_rate / 100 / 12

    schedule = []
    balance = principal

    for month in range(1, tenure_months + 1):
        interest_part = balance * r
        principal_part = emi_val - interest_part
        balance = max(balance - principal_part, 0)

        schedule.append(AmortizationEntry(
            month=month,
            emi=round(emi_val, 2),
            principal=round(principal_part, 2),
            interest=round(interest_part, 2),
            balance=round(balance, 2),
        ))

    return schedule


def analyze_prepayment(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    prepayment_amount: float,
    prepayment_at_month: int = 12,
) -> PrepaymentImpact:
    """Analyze the impact of a lump-sum prepayment on a loan.

    Keeps EMI same, reduces tenure.
    """
    original = calculate_emi(principal, annual_rate, tenure_months)
    emi = original.monthly_emi
    r = annual_rate / 100 / 12

    # Simulate loan with prepayment
    balance = principal
    total_interest_new = 0
    month = 0

    while balance > 0 and month < tenure_months * 2:
        month += 1
        interest = balance * r
        principal_part = emi - interest

        # Apply prepayment at specified month
        if month == prepayment_at_month:
            balance -= prepayment_amount

        balance -= principal_part
        total_interest_new += interest

        if balance <= 0:
            break

    return PrepaymentImpact(
        original_tenure_months=tenure_months,
        new_tenure_months=month,
        months_saved=tenure_months - month,
        original_total_interest=original.total_interest,
        new_total_interest=total_interest_new,
        interest_saved=original.total_interest - total_interest_new,
        prepayment_amount=prepayment_amount,
    )


def prepay_vs_invest(
    loan_principal: float,
    loan_rate: float,  # Annual %
    loan_tenure_months: int,
    lump_sum: float,  # Amount available
    investment_return: float = 12.0,  # Expected annual return %
    remaining_loan_months: int | None = None,
    tax_benefit: bool = True,  # Home loan 80C/24b benefit?
) -> PrepayVsInvestResult:
    """Should you prepay your loan or invest the money?

    Uses pyxirr FV for investment return projection.
    Compares interest saved by prepaying vs expected investment growth.
    """
    if remaining_loan_months is None:
        remaining_loan_months = loan_tenure_months

    # Interest saved by prepaying
    prepay = analyze_prepayment(
        loan_principal, loan_rate, remaining_loan_months, lump_sum,
    )
    interest_saved = prepay.interest_saved

    # If tax benefit applies, effective interest rate is lower
    if tax_benefit and loan_rate > 0:
        # Assume 30% tax bracket - effective rate reduces by 30%
        interest_saved = interest_saved * 0.70  # Net of tax benefit lost

    # Expected return from investing (using pyxirr FV)
    years = remaining_loan_months / 12
    monthly_inv_rate = investment_return / 100 / 12
    invest_fv = fv(monthly_inv_rate, remaining_loan_months, 0, lump_sum)
    invest_return = invest_fv - lump_sum

    # Compare
    net_benefit = abs(invest_return - interest_saved)
    if invest_return > interest_saved:
        recommendation = "invest"
        details = (
            f"Investing Rs {lump_sum:,.0f} at {investment_return}% return gives "
            f"Rs {invest_return:,.0f} over {years:.1f} years, which is "
            f"Rs {net_benefit:,.0f} more than the Rs {interest_saved:,.0f} "
            f"you'd save by prepaying your {loan_rate}% loan."
        )
    else:
        recommendation = "prepay"
        details = (
            f"Prepaying Rs {lump_sum:,.0f} on your {loan_rate}% loan saves "
            f"Rs {interest_saved:,.0f} in interest, which is "
            f"Rs {net_benefit:,.0f} more than the Rs {invest_return:,.0f} "
            f"you'd earn investing at {investment_return}%."
        )

    # Additional nuance
    if loan_rate > investment_return:
        details += " Since your loan rate exceeds expected investment returns, prepaying is clearly better."
    elif loan_rate < 8 and investment_return > 12:
        details += " Your loan rate is low - investing in equity SIPs is likely better long-term."

    return PrepayVsInvestResult(
        prepay_interest_saved=interest_saved,
        invest_expected_return=invest_return,
        recommendation=recommendation,
        net_benefit=net_benefit,
        details=details,
    )


def compare_loan_offers(
    loan_amount: float,
    offers: list[dict],
) -> list[dict]:
    """Compare multiple loan offers side by side.

    Args:
        loan_amount: Desired loan amount
        offers: List of {"bank": "SBI", "rate": 8.5, "tenure_months": 240, "processing_fee": 10000}

    Returns:
        Sorted list (cheapest first) with full EMI analysis
    """
    results = []
    for offer in offers:
        emi = calculate_emi(
            loan_amount,
            offer["rate"],
            offer["tenure_months"],
        )
        processing_fee = offer.get("processing_fee", 0)
        total_cost = emi.total_payment + processing_fee

        results.append({
            "bank": offer.get("bank", "Unknown"),
            "rate": offer["rate"],
            "tenure_months": offer["tenure_months"],
            "monthly_emi": round(emi.monthly_emi),
            "total_interest": round(emi.total_interest),
            "processing_fee": processing_fee,
            "total_cost": round(total_cost),
        })

    results.sort(key=lambda x: x["total_cost"])

    # Add savings vs most expensive
    if len(results) >= 2:
        most_expensive = results[-1]["total_cost"]
        for r in results:
            r["savings_vs_worst"] = round(most_expensive - r["total_cost"])

    return results
