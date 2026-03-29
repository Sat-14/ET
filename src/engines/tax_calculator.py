"""Indian Income Tax Calculator - Old vs New Regime (FY 2025-26).

Supports:
- Old regime with all deductions (80C, 80D, 80CCD, 24b, HRA, etc.)
- New regime with revised slabs from Budget 2025
- Regime comparison with recommendation
- Couple/household tax optimization
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from src.models.user import (
    City,
    IndividualProfile,
    HouseholdProfile,
    TaxRegime,
)
from src.engines.insurance_calculator import (
    calculate_health_insurance_need,
    calculate_life_insurance_need,
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


@dataclass
class TaxSavingOption:
    name: str
    section: str
    suggested_amount: float
    max_eligible_amount: float
    risk_level: str
    liquidity: str
    lock_in: str
    fit_score: float
    rationale: str
    notes: list[str]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "section": self.section,
            "suggested_amount": round(self.suggested_amount),
            "max_eligible_amount": round(self.max_eligible_amount),
            "risk_level": self.risk_level,
            "liquidity": self.liquidity,
            "lock_in": self.lock_in,
            "fit_score": round(self.fit_score, 2),
            "rationale": self.rationale,
            "notes": self.notes,
        }


def _normalize_risk_profile(risk_profile: str) -> str:
    value = (risk_profile or "moderate").strip().lower()
    if value in {"conservative", "moderate", "aggressive"}:
        return value
    return "moderate"


def _normalize_liquidity_need(liquidity_need: str) -> str:
    value = (liquidity_need or "medium").strip().lower()
    if value in {"low", "medium", "high"}:
        return value
    return "medium"


def _risk_fit(target_risk: str, option_risk: str) -> float:
    scores = {
        ("conservative", "low"): 3.0,
        ("conservative", "moderate"): 1.5,
        ("conservative", "high"): 0.5,
        ("moderate", "low"): 2.0,
        ("moderate", "moderate"): 3.0,
        ("moderate", "high"): 2.0,
        ("aggressive", "low"): 1.0,
        ("aggressive", "moderate"): 2.5,
        ("aggressive", "high"): 3.0,
    }
    return scores.get((target_risk, option_risk), 1.0)


def _liquidity_fit(liquidity_need: str, option_liquidity: str) -> float:
    scores = {
        ("high", "high"): 3.0,
        ("high", "medium"): 1.5,
        ("high", "low"): 0.5,
        ("medium", "high"): 2.5,
        ("medium", "medium"): 3.0,
        ("medium", "low"): 1.5,
        ("low", "high"): 1.5,
        ("low", "medium"): 2.5,
        ("low", "low"): 3.0,
    }
    return scores.get((liquidity_need, option_liquidity), 1.0)


def recommend_tax_saving_options(
    profile: IndividualProfile,
    risk_profile: str = "moderate",
    liquidity_need: str = "medium",
) -> list[dict]:
    """Rank tax-saving actions based on unused deduction room and user preferences."""
    comparison = compare_regimes(profile)
    risk_profile = _normalize_risk_profile(risk_profile)
    liquidity_need = _normalize_liquidity_need(liquidity_need)
    unused = comparison.unused_deduction_room

    options: list[TaxSavingOption] = []

    def add_option(
        *,
        name: str,
        section: str,
        available_amount: float,
        option_risk: str,
        option_liquidity: str,
        lock_in: str,
        rationale: str,
        notes: list[str],
        bonus: float = 0.0,
    ) -> None:
        if available_amount <= 0:
            return
        fit_score = (
            _risk_fit(risk_profile, option_risk)
            + _liquidity_fit(liquidity_need, option_liquidity)
            + bonus
        )
        options.append(TaxSavingOption(
            name=name,
            section=section,
            suggested_amount=available_amount,
            max_eligible_amount=available_amount,
            risk_level=option_risk,
            liquidity=option_liquidity,
            lock_in=lock_in,
            fit_score=fit_score,
            rationale=rationale,
            notes=notes,
        ))

    unused_80c = unused.get("80C", 0)
    unused_nps = unused.get("80CCD(1B) NPS", 0)
    unused_80d = unused.get("80D", 0)
    unused_24b = unused.get("24(b) Home Loan Interest", 0)

    add_option(
        name="ELSS Mutual Funds",
        section="80C",
        available_amount=unused_80c,
        option_risk="high",
        option_liquidity="medium",
        lock_in="3 years",
        rationale="Best fit if you want tax saving plus equity growth potential.",
        notes=[
            "Section 80C eligible up to Rs 1.5 lakh.",
            "Shortest lock-in among major 80C investment products.",
        ],
        bonus=0.5,
    )
    add_option(
        name="PPF",
        section="80C",
        available_amount=unused_80c,
        option_risk="low",
        option_liquidity="low",
        lock_in="15 years",
        rationale="Strong fit for conservative users building long-term safe compounding.",
        notes=[
            "Government-backed and low risk.",
            "Useful when liquidity is not the priority.",
        ],
        bonus=0.25 if profile.years_to_retirement >= 10 else 0.0,
    )
    add_option(
        name="VPF / EPF Top-Up",
        section="80C",
        available_amount=unused_80c,
        option_risk="low",
        option_liquidity="low",
        lock_in="Retirement-linked",
        rationale="Simple salary-linked tax saving if you prefer disciplined payroll investing.",
        notes=[
            "Works best for salaried users already contributing to EPF.",
            "Low flexibility for near-term cash needs.",
        ],
        bonus=0.5,
    )
    add_option(
        name="5-Year Tax Saver FD",
        section="80C",
        available_amount=unused_80c,
        option_risk="low",
        option_liquidity="low",
        lock_in="5 years",
        rationale="Useful if you want predictable returns and do not want market volatility.",
        notes=[
            "Interest is taxable.",
            "Safer than ELSS, but lower return potential.",
        ],
    )

    add_option(
        name="NPS Additional Contribution",
        section="80CCD(1B) NPS",
        available_amount=unused_nps,
        option_risk="moderate",
        option_liquidity="low",
        lock_in="Retirement-linked",
        rationale="Strong fit for retirement-focused users who also want the extra Rs 50K deduction.",
        notes=[
            "Separate tax benefit beyond 80C.",
            "Best if retirement corpus is also a priority.",
        ],
        bonus=1.0 if profile.years_to_retirement >= 10 else 0.25,
    )

    add_option(
        name="Health Insurance / Super Top-Up",
        section="80D",
        available_amount=unused_80d,
        option_risk="low",
        option_liquidity="medium",
        lock_in="Annual policy",
        rationale="Tax-efficient protection upgrade that improves both resilience and deduction usage.",
        notes=[
            "This is a protection decision, not an investment product.",
            "Useful if current cover is below family needs.",
        ],
        bonus=1.5,
    )

    if unused_24b > 0:
        add_option(
            name="Home Loan Interest Claim Review",
            section="24(b)",
            available_amount=unused_24b,
            option_risk="low",
            option_liquidity="medium",
            lock_in="Loan-linked",
            rationale="Review whether the full eligible home-loan interest is being captured in tax filing.",
            notes=[
                "This is a filing/checklist action, not a fresh investment.",
                "Only relevant if you already have a home loan.",
            ],
            bonus=0.5,
        )

    options.sort(
        key=lambda option: (
            option.fit_score,
            option.suggested_amount,
            option.section != "80D",
        ),
        reverse=True,
    )

    results = []
    for rank, option in enumerate(options, start=1):
        data = option.to_dict()
        data["rank"] = rank
        results.append(data)
    return results


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


def _best_tax_for_comparison(comparison: RegimeComparison) -> float:
    if comparison.recommended_regime == TaxRegime.OLD:
        return comparison.old_regime.total_tax
    return comparison.new_regime.total_tax


def _clone_with_rent(profile: IndividualProfile, rent_paid_annual: float) -> IndividualProfile:
    cloned = copy.deepcopy(profile)
    cloned.deductions.rent_paid_annual = max(rent_paid_annual, 0.0)
    return cloned


def _optimize_household_hra_split(
    household: HouseholdProfile,
    shared_annual_rent: float,
) -> dict | None:
    if not household.is_couple or shared_annual_rent <= 0:
        return None

    partner_a_hra = household.person_a.salary.hra
    partner_b_hra = household.person_b.salary.hra if household.person_b else 0.0
    if partner_a_hra <= 0 and partner_b_hra <= 0:
        return None

    current_rent_a = household.person_a.deductions.rent_paid_annual
    current_rent_b = household.person_b.deductions.rent_paid_annual if household.person_b else 0.0
    baseline_comp_a = compare_regimes(_clone_with_rent(household.person_a, current_rent_a))
    baseline_comp_b = compare_regimes(_clone_with_rent(household.person_b, current_rent_b))
    baseline_tax = _best_tax_for_comparison(baseline_comp_a) + _best_tax_for_comparison(baseline_comp_b)

    best_result = None
    step = 12_000

    for rent_a in range(0, int(shared_annual_rent) + step, step):
        if rent_a > shared_annual_rent:
            rent_a = shared_annual_rent
        rent_b = max(shared_annual_rent - rent_a, 0.0)

        comp_a = compare_regimes(_clone_with_rent(household.person_a, rent_a))
        comp_b = compare_regimes(_clone_with_rent(household.person_b, rent_b))
        household_tax = _best_tax_for_comparison(comp_a) + _best_tax_for_comparison(comp_b)

        candidate = {
            "rent_to_person_a": round(rent_a),
            "rent_to_person_b": round(rent_b),
            "person_a_hra_exemption": round(comp_a.old_regime.hra_exemption),
            "person_b_hra_exemption": round(comp_b.old_regime.hra_exemption),
            "household_tax": round(household_tax),
            "tax_saved_vs_current_split": round(max(baseline_tax - household_tax, 0)),
            "person_a_best_regime": comp_a.recommended_regime.value,
            "person_b_best_regime": comp_b.recommended_regime.value,
        }
        if best_result is None or candidate["household_tax"] < best_result["household_tax"]:
            best_result = candidate

    if best_result is None:
        return None

    best_result["note"] = (
        "Split household rent to maximize HRA exemption in the partner where old-regime tax benefit is higher."
    )
    return best_result


def _recommend_couple_sip_split(
    household: HouseholdProfile,
    comp_a: RegimeComparison,
    comp_b: RegimeComparison,
    target_monthly_sip: float,
) -> dict:
    income_a = household.person_a.annual_income
    income_b = household.person_b.annual_income if household.person_b else 0.0
    total_income = max(income_a + income_b, 1.0)

    room_a = (
        comp_a.unused_deduction_room.get("80C", 0)
        + comp_a.unused_deduction_room.get("80CCD(1B) NPS", 0)
    )
    room_b = (
        comp_b.unused_deduction_room.get("80C", 0)
        + comp_b.unused_deduction_room.get("80CCD(1B) NPS", 0)
    )
    tax_room_total = max(room_a + room_b, 1.0)

    score_a = (income_a / total_income) * 0.7 + (room_a / tax_room_total) * 0.3
    score_b = (income_b / total_income) * 0.7 + (room_b / tax_room_total) * 0.3
    total_score = max(score_a + score_b, 1e-9)

    sip_a = round(target_monthly_sip * (score_a / total_score))
    sip_b = round(target_monthly_sip - sip_a)

    nps_a = min(comp_a.unused_deduction_room.get("80CCD(1B) NPS", 0) / 12, sip_a)
    nps_b = min(comp_b.unused_deduction_room.get("80CCD(1B) NPS", 0) / 12, sip_b)

    return {
        "target_household_monthly_sip": round(target_monthly_sip),
        "person_a_recommended_sip": sip_a,
        "person_b_recommended_sip": sip_b,
        "person_a_income_share_pct": round(income_a / total_income * 100, 1),
        "person_b_income_share_pct": round(income_b / total_income * 100, 1),
        "person_a_tax_efficient_nps_top_up": round(nps_a),
        "person_b_tax_efficient_nps_top_up": round(nps_b),
        "note": (
            "SIP split is weighted toward the higher earner but nudged toward the partner "
            "with more unused 80C/NPS room for better after-tax efficiency."
        ),
    }


def _recommend_household_insurance_structure(household: HouseholdProfile) -> dict:
    person_a_life = calculate_life_insurance_need(household.person_a)
    person_b_life = calculate_life_insurance_need(household.person_b)

    family_members = 2 + max(household.num_dependents, 0)
    city_tier = "metro" if household.person_a.city == City.METRO else "non_metro"
    older_partner = household.person_a if household.person_a.age >= household.person_b.age else household.person_b
    family_health = calculate_health_insurance_need(
        older_partner,
        num_family_members=family_members,
        city_tier=city_tier,
    )

    current_combined_health_cover = (
        household.person_a.insurance.health_cover
        + household.person_b.insurance.health_cover
    )
    structure = "Individual base covers + shared super top-up"
    if family_members >= 3:
        structure = "Family floater + super top-up"

    return {
        "recommended_structure": structure,
        "person_a_life_cover_gap": round(person_a_life.gap),
        "person_b_life_cover_gap": round(person_b_life.gap),
        "combined_life_cover_gap": round(person_a_life.gap + person_b_life.gap),
        "recommended_family_health_cover": round(family_health.recommended_cover),
        "current_combined_health_cover": round(current_combined_health_cover),
        "health_cover_gap": round(max(family_health.recommended_cover - current_combined_health_cover, 0)),
        "recommended_super_top_up": round(
            max(family_health.recommended_cover - current_combined_health_cover, 0)
        ),
        "note": (
            "Use self-owned term plans for each earning partner. Choose the health structure "
            "based on dependents: a floater works better for families, while dual base covers "
            "plus a common top-up works well for dual-income couples without children."
        ),
    }


def optimize_couple_tax(
    household: HouseholdProfile,
    *,
    shared_annual_rent: float = 0.0,
    target_monthly_sip: float = 0.0,
) -> dict:
    """Optimize tax across a couple.

    Strategy: Assign deductions to the person in the higher slab for max benefit.
    """
    if not household.is_couple:
        comp = compare_regimes(household.person_a)
        combined_current_investments = household.person_a.current_investments
        combined_retirement_corpus = household.person_a.total_retirement_corpus
        combined_emergency_fund = (
            household.combined_emergency_fund or household.person_a.emergency_fund
        )
        combined_debt = household.person_a.debt.total_outstanding
        return {
            "person_a": comp.to_dict(),
            "person_b": None,
            "household_total_tax": comp.old_regime.total_tax
            if comp.recommended_regime == TaxRegime.OLD
            else comp.new_regime.total_tax,
            "combined_current_investments": round(combined_current_investments),
            "combined_retirement_corpus": round(combined_retirement_corpus),
            "combined_emergency_fund": round(combined_emergency_fund),
            "combined_net_worth": round(
                combined_current_investments + combined_retirement_corpus + combined_emergency_fund - combined_debt
            ),
            "optimization_notes": [],
        }

    comp_a = compare_regimes(household.person_a)
    comp_b = compare_regimes(household.person_b)

    best_a = _best_tax_for_comparison(comp_a)
    best_b = _best_tax_for_comparison(comp_b)

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

    inferred_household_rent = shared_annual_rent
    if inferred_household_rent <= 0:
        inferred_household_rent = max(
            household.person_a.deductions.rent_paid_annual
            + household.person_b.deductions.rent_paid_annual,
            (household.person_a.monthly_expenses.rent + household.person_b.monthly_expenses.rent) * 12,
        )

    hra_optimization = _optimize_household_hra_split(
        household,
        inferred_household_rent,
    )
    if hra_optimization and hra_optimization["tax_saved_vs_current_split"] > 0:
        notes.append(
            f"HRA split optimization can save another Rs {hra_optimization['tax_saved_vs_current_split']:,.0f}/year."
        )

    suggested_household_sip = target_monthly_sip
    if suggested_household_sip <= 0:
        suggested_household_sip = (
            household.person_a.monthly_sip
            + household.person_b.monthly_sip
        )
        if suggested_household_sip <= 0:
            suggested_household_sip = max(
                (household.combined_annual_income / 12) * 0.20,
                0.0,
            )
    sip_split = _recommend_couple_sip_split(
        household,
        comp_a,
        comp_b,
        suggested_household_sip,
    )
    insurance_structure = _recommend_household_insurance_structure(household)

    combined_current_investments = (
        household.person_a.current_investments
        + household.person_b.current_investments
    )
    combined_retirement_corpus = (
        household.person_a.total_retirement_corpus
        + household.person_b.total_retirement_corpus
    )
    combined_emergency_fund = (
        household.combined_emergency_fund
        or household.person_a.emergency_fund
        + household.person_b.emergency_fund
    )
    combined_debt = (
        household.person_a.debt.total_outstanding
        + household.person_b.debt.total_outstanding
    )
    combined_life_cover = (
        household.person_a.insurance.life_cover
        + household.person_b.insurance.life_cover
    )
    combined_health_cover = (
        household.person_a.insurance.health_cover
        + household.person_b.insurance.health_cover
    )
    recommended_life_cover = household.combined_annual_income * 10
    recommended_health_cover = 1_500_000 + max(household.num_dependents, 0) * 500_000
    life_gap = max(recommended_life_cover - combined_life_cover, 0)
    health_gap = max(recommended_health_cover - combined_health_cover, 0)

    monthly_household_need = household.combined_monthly_expenses
    emergency_target = monthly_household_need * 6
    emergency_months = (
        combined_emergency_fund / monthly_household_need
        if monthly_household_need > 0 else 0
    )

    if emergency_months < 6:
        notes.append(
            f"Household emergency fund covers {emergency_months:.1f} months; target is 6 months (need Rs {max(emergency_target - combined_emergency_fund, 0):,.0f} more)."
        )
    if life_gap > 0:
        notes.append(
            f"Combined life cover is short by Rs {life_gap:,.0f}; review term cover allocation across both partners."
        )
    if health_gap > 0:
        notes.append(
            f"Combined health cover is short by Rs {health_gap:,.0f}; compare family floater vs individual plus super top-up."
        )

    return {
        "person_a": comp_a.to_dict(),
        "person_b": comp_b.to_dict(),
        "household_total_tax": best_a + best_b,
        "household_total_monthly_in_hand": (
            max(comp_a.old_regime.monthly_in_hand, comp_a.new_regime.monthly_in_hand)
            + max(comp_b.old_regime.monthly_in_hand, comp_b.new_regime.monthly_in_hand)
        ),
        "combined_current_investments": round(combined_current_investments),
        "combined_retirement_corpus": round(combined_retirement_corpus),
        "combined_emergency_fund": round(combined_emergency_fund),
        "combined_net_worth": round(
            combined_current_investments + combined_retirement_corpus + combined_emergency_fund - combined_debt
        ),
        "recommended_household_life_cover": round(recommended_life_cover),
        "combined_life_cover_gap": round(life_gap),
        "recommended_household_health_cover": round(recommended_health_cover),
        "combined_health_cover_gap": round(health_gap),
        "emergency_months_covered": round(emergency_months, 1),
        "hra_optimization": hra_optimization,
        "sip_split": sip_split,
        "insurance_structure": insurance_structure,
        "optimization_notes": notes,
    }
