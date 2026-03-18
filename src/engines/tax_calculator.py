"""Indian Income Tax Calculator - Old vs New Regime (FY 2025-26).

Supports:
- Old regime with all deductions (80C, 80D, 80CCD, 24b, HRA, etc.)
- New regime with revised slabs from Budget 2025
- Regime comparison with recommendation
- Couple/household tax optimization
"""

from __future__ import annotations

from dataclasses import dataclass

from src.models.user import (
    City,
    IndividualProfile,
    HouseholdProfile,
    TaxRegime,
)


# --- FY 2025-26 Tax Slabs ---

OLD_REGIME_SLABS = [
    (250_000, 0.00),
    (500_000, 0.05),
    (1_000_000, 0.20),
    (float("inf"), 0.30),
]

# Budget 2025 revised new regime slabs
NEW_REGIME_SLABS = [
    (400_000, 0.00),
    (800_000, 0.05),
    (1_200_000, 0.10),
    (1_600_000, 0.15),
    (2_000_000, 0.20),
    (2_400_000, 0.25),
    (float("inf"), 0.30),
]

STANDARD_DEDUCTION_OLD = 50_000
STANDARD_DEDUCTION_NEW = 75_000

# Section 87A Rebate
REBATE_87A_OLD_LIMIT = 500_000
REBATE_87A_NEW_LIMIT = 1_200_000
REBATE_87A_OLD_MAX = 12_500
REBATE_87A_NEW_MAX = 60_000

HEALTH_EDUCATION_CESS = 0.04

# Surcharge slabs
SURCHARGE_SLABS = [
    (5_000_000, 0.00),
    (10_000_000, 0.10),
    (20_000_000, 0.15),
    (50_000_000, 0.25),
    (float("inf"), 0.37),
]

# New regime surcharge cap
NEW_REGIME_SURCHARGE_CAP = 0.25


@dataclass
class TaxBreakdown:
    regime: TaxRegime
    gross_income: float
    standard_deduction: float
    hra_exemption: float
    total_deductions: float
    taxable_income: float
    tax_on_income: float
    rebate_87a: float
    surcharge: float
    cess: float
    total_tax: float
    effective_rate: float
    monthly_tax: float
    monthly_in_hand: float

    # Deduction details (old regime)
    deduction_80c: float = 0.0
    deduction_80d: float = 0.0
    deduction_80ccd_1b: float = 0.0
    deduction_80e: float = 0.0
    deduction_24b: float = 0.0
    deduction_80tta: float = 0.0
    employer_nps_80ccd2: float = 0.0

    def to_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "gross_income": self.gross_income,
            "standard_deduction": self.standard_deduction,
            "hra_exemption": self.hra_exemption,
            "total_deductions": self.total_deductions,
            "taxable_income": self.taxable_income,
            "tax_on_income": self.tax_on_income,
            "rebate_87a": self.rebate_87a,
            "surcharge": self.surcharge,
            "cess": self.cess,
            "total_tax": self.total_tax,
            "effective_rate": round(self.effective_rate, 2),
            "monthly_tax": round(self.monthly_tax, 2),
            "monthly_in_hand": round(self.monthly_in_hand, 2),
        }


@dataclass
class RegimeComparison:
    old_regime: TaxBreakdown
    new_regime: TaxBreakdown
    recommended_regime: TaxRegime
    tax_saving: float  # How much you save by choosing recommended
    unused_deduction_room: dict  # Deductions not fully utilized

    def to_dict(self) -> dict:
        return {
            "old_regime": self.old_regime.to_dict(),
            "new_regime": self.new_regime.to_dict(),
            "recommended_regime": self.recommended_regime.value,
            "tax_saving": round(self.tax_saving, 2),
            "unused_deduction_room": self.unused_deduction_room,
        }


def _compute_slab_tax(taxable_income: float, slabs: list[tuple[float, float]]) -> float:
    """Compute tax based on slab rates."""
    tax = 0.0
    prev_limit = 0
    for limit, rate in slabs:
        if taxable_income <= prev_limit:
            break
        taxable_in_slab = min(taxable_income, limit) - prev_limit
        tax += taxable_in_slab * rate
        prev_limit = limit
    return tax


def _compute_surcharge(tax: float, taxable_income: float, is_new_regime: bool = False) -> float:
    """Compute surcharge based on income."""
    surcharge_rate = 0.0
    for limit, rate in SURCHARGE_SLABS:
        if taxable_income <= limit:
            surcharge_rate = rate
            break
    if is_new_regime:
        surcharge_rate = min(surcharge_rate, NEW_REGIME_SURCHARGE_CAP)
    return tax * surcharge_rate


def compute_hra_exemption(
    basic: float,
    da: float,
    hra_received: float,
    rent_paid: float,
    city: City,
) -> float:
    """Compute HRA exemption under old regime.

    Exempt = min of:
    1. Actual HRA received
    2. 50% of (Basic + DA) for metro, 40% for non-metro
    3. Rent paid - 10% of (Basic + DA)
    """
    if rent_paid == 0 or hra_received == 0:
        return 0.0
    basic_da = basic + da
    pct = 0.50 if city == City.METRO else 0.40
    return max(
        min(
            hra_received,
            basic_da * pct,
            rent_paid - (basic_da * 0.10),
        ),
        0,
    )


def compute_tax_old_regime(profile: IndividualProfile) -> TaxBreakdown:
    """Compute tax under old regime with all deductions."""
    sal = profile.salary
    ded = profile.deductions

    gross_income = profile.annual_income

    # Standard deduction
    std_ded = STANDARD_DEDUCTION_OLD

    # HRA exemption
    hra_exempt = compute_hra_exemption(
        basic=sal.basic,
        da=sal.da,
        hra_received=sal.hra,
        rent_paid=ded.rent_paid_annual,
        city=profile.city,
    )

    # Professional tax deduction
    prof_tax = sal.professional_tax

    # Employer NPS - 80CCD(2) - max 14% of basic for central govt, 10% otherwise
    employer_nps = min(sal.employer_nps, sal.basic * 0.10)

    # Chapter VI-A deductions
    d_80c = ded.total_80c
    d_80d = ded.total_80d
    d_80ccd_1b = ded.total_80ccd_1b
    d_80e = ded.education_loan_interest
    d_80tta = min(ded.savings_interest, 10_000)
    d_24b = min(ded.home_loan_interest, 200_000)
    d_80g = ded.donations

    total_deductions = (
        std_ded + hra_exempt + prof_tax + employer_nps
        + d_80c + d_80d + d_80ccd_1b + d_80e + d_80tta + d_24b + d_80g
    )

    taxable_income = max(gross_income - total_deductions, 0)

    # Compute tax
    tax = _compute_slab_tax(taxable_income, OLD_REGIME_SLABS)

    # Rebate 87A
    rebate = 0.0
    if taxable_income <= REBATE_87A_OLD_LIMIT:
        rebate = min(tax, REBATE_87A_OLD_MAX)
    tax_after_rebate = max(tax - rebate, 0)

    # Surcharge
    surcharge = _compute_surcharge(tax_after_rebate, taxable_income)

    # Cess
    cess = (tax_after_rebate + surcharge) * HEALTH_EDUCATION_CESS

    total_tax = tax_after_rebate + surcharge + cess
    effective_rate = (total_tax / gross_income * 100) if gross_income > 0 else 0
    monthly_tax = total_tax / 12
    monthly_in_hand = (gross_income / 12) - monthly_tax

    return TaxBreakdown(
        regime=TaxRegime.OLD,
        gross_income=gross_income,
        standard_deduction=std_ded,
        hra_exemption=hra_exempt,
        total_deductions=total_deductions,
        taxable_income=taxable_income,
        tax_on_income=tax,
        rebate_87a=rebate,
        surcharge=surcharge,
        cess=cess,
        total_tax=total_tax,
        effective_rate=effective_rate,
        monthly_tax=monthly_tax,
        monthly_in_hand=monthly_in_hand,
        deduction_80c=d_80c,
        deduction_80d=d_80d,
        deduction_80ccd_1b=d_80ccd_1b,
        deduction_80e=d_80e,
        deduction_24b=d_24b,
        deduction_80tta=d_80tta,
        employer_nps_80ccd2=employer_nps,
    )


def compute_tax_new_regime(profile: IndividualProfile) -> TaxBreakdown:
    """Compute tax under new regime (FY 2025-26).

    New regime allows only:
    - Standard deduction of Rs 75,000
    - Employer NPS 80CCD(2)
    - No other deductions
    """
    gross_income = profile.annual_income
    sal = profile.salary

    # Only standard deduction + employer NPS allowed
    std_ded = STANDARD_DEDUCTION_NEW
    employer_nps = min(sal.employer_nps, sal.basic * 0.14)

    total_deductions = std_ded + employer_nps
    taxable_income = max(gross_income - total_deductions, 0)

    # Compute tax
    tax = _compute_slab_tax(taxable_income, NEW_REGIME_SLABS)

    # Rebate 87A - new regime (Budget 2025)
    rebate = 0.0
    if taxable_income <= REBATE_87A_NEW_LIMIT:
        rebate = min(tax, REBATE_87A_NEW_MAX)
    tax_after_rebate = max(tax - rebate, 0)

    # Surcharge
    surcharge = _compute_surcharge(tax_after_rebate, taxable_income, is_new_regime=True)

    # Cess
    cess = (tax_after_rebate + surcharge) * HEALTH_EDUCATION_CESS

    total_tax = tax_after_rebate + surcharge + cess
    effective_rate = (total_tax / gross_income * 100) if gross_income > 0 else 0
    monthly_tax = total_tax / 12
    monthly_in_hand = (gross_income / 12) - monthly_tax

    return TaxBreakdown(
        regime=TaxRegime.NEW,
        gross_income=gross_income,
        standard_deduction=std_ded,
        hra_exemption=0,
        total_deductions=total_deductions,
        taxable_income=taxable_income,
        tax_on_income=tax,
        rebate_87a=rebate,
        surcharge=surcharge,
        cess=cess,
        total_tax=total_tax,
        effective_rate=effective_rate,
        monthly_tax=monthly_tax,
        monthly_in_hand=monthly_in_hand,
        employer_nps_80ccd2=employer_nps,
    )


def compare_regimes(profile: IndividualProfile) -> RegimeComparison:
    """Compare old vs new regime and recommend the better one."""
    old = compute_tax_old_regime(profile)
    new = compute_tax_new_regime(profile)

    if old.total_tax <= new.total_tax:
        recommended = TaxRegime.OLD
        saving = new.total_tax - old.total_tax
    else:
        recommended = TaxRegime.NEW
        saving = old.total_tax - new.total_tax

    # Compute unused deduction room (old regime)
    ded = profile.deductions
    unused = {}
    raw_80c = (
        ded.elss + ded.ppf + ded.lic_premium + ded.home_loan_principal
        + ded.tuition_fees + ded.nsc + ded.sukanya_samriddhi
        + ded.tax_saver_fd + ded.employee_pf
    )
    if raw_80c < 150_000:
        unused["80C"] = 150_000 - raw_80c
    raw_80d = ded.self_health_insurance + ded.parents_health_insurance
    max_80d = 25_000 + 50_000  # self + parents (senior)
    if raw_80d < max_80d:
        unused["80D"] = max_80d - raw_80d
    if ded.nps_additional < 50_000:
        unused["80CCD(1B) NPS"] = 50_000 - ded.nps_additional
    if ded.home_loan_interest < 200_000 and ded.home_loan_interest > 0:
        unused["24(b) Home Loan Interest"] = 200_000 - ded.home_loan_interest

    return RegimeComparison(
        old_regime=old,
        new_regime=new,
        recommended_regime=recommended,
        tax_saving=saving,
        unused_deduction_room=unused,
    )


def optimize_couple_tax(household: HouseholdProfile) -> dict:
    """Optimize tax across a couple.

    Strategy: Assign deductions to the person in the higher slab for max benefit.
    """
    if not household.is_couple:
        comp = compare_regimes(household.person_a)
        return {
            "person_a": comp.to_dict(),
            "person_b": None,
            "household_total_tax": comp.old_regime.total_tax
            if comp.recommended_regime == TaxRegime.OLD
            else comp.new_regime.total_tax,
            "optimization_notes": [],
        }

    comp_a = compare_regimes(household.person_a)
    comp_b = compare_regimes(household.person_b)

    best_a = min(comp_a.old_regime.total_tax, comp_a.new_regime.total_tax)
    best_b = min(comp_b.old_regime.total_tax, comp_b.new_regime.total_tax)

    notes = []

    # Check who is in higher slab for deduction allocation
    income_a = household.person_a.annual_income
    income_b = household.person_b.annual_income

    if income_a > income_b:
        higher_earner, _ = "Person A", "Person B"
    else:
        higher_earner, _ = "Person B", "Person A"

    notes.append(
        f"{higher_earner} is in a higher tax slab - maximize deductions here"
    )

    if comp_a.unused_deduction_room.get("80C", 0) > 0:
        notes.append(
            f"Person A has Rs {comp_a.unused_deduction_room['80C']:,.0f} unused in 80C"
        )
    if comp_b.unused_deduction_room.get("80C", 0) > 0:
        notes.append(
            f"Person B has Rs {comp_b.unused_deduction_room['80C']:,.0f} unused in 80C"
        )
    if comp_a.unused_deduction_room.get("80CCD(1B) NPS", 0) > 0:
        notes.append("Person A should consider NPS for extra Rs 50K deduction")
    if comp_b.unused_deduction_room.get("80CCD(1B) NPS", 0) > 0:
        notes.append("Person B should consider NPS for extra Rs 50K deduction")

    return {
        "person_a": comp_a.to_dict(),
        "person_b": comp_b.to_dict(),
        "household_total_tax": best_a + best_b,
        "household_total_monthly_in_hand": (
            max(comp_a.old_regime.monthly_in_hand, comp_a.new_regime.monthly_in_hand)
            + max(comp_b.old_regime.monthly_in_hand, comp_b.new_regime.monthly_in_hand)
        ),
        "optimization_notes": notes,
    }
