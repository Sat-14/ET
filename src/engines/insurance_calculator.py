"""Insurance Needs Calculator.

Computes insurance requirements using multiple methods:
1. Human Life Value (HLV) - income replacement approach
2. Expense-based method - covers family expenses for N years
3. Needs-based approach - sum of all financial obligations

Also handles health insurance adequacy assessment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.user import IndividualProfile


@dataclass
class LifeInsuranceNeed:
    hlv_method: float  # Human Life Value
    expense_method: float  # Expense replacement
    needs_method: float  # Sum of all needs
    recommended_cover: float  # Max of all methods
    current_cover: float
    gap: float
    adequacy_pct: float
    breakdown: dict
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "hlv_method": round(self.hlv_method),
            "expense_method": round(self.expense_method),
            "needs_method": round(self.needs_method),
            "recommended_cover": round(self.recommended_cover),
            "current_cover": round(self.current_cover),
            "gap": round(self.gap),
            "adequacy_pct": round(self.adequacy_pct, 1),
            "breakdown": self.breakdown,
            "recommendations": self.recommendations,
        }


@dataclass
class HealthInsuranceNeed:
    recommended_cover: float
    current_cover: float
    gap: float
    adequacy_pct: float
    needs_super_top_up: bool
    recommended_top_up: float
    estimated_premium: float
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "recommended_cover": round(self.recommended_cover),
            "current_cover": round(self.current_cover),
            "gap": round(self.gap),
            "adequacy_pct": round(self.adequacy_pct, 1),
            "needs_super_top_up": self.needs_super_top_up,
            "recommended_top_up": round(self.recommended_top_up),
            "estimated_annual_premium": round(self.estimated_premium),
            "recommendations": self.recommendations,
        }


def calculate_life_insurance_need(
    profile: IndividualProfile,
    income_replacement_years: int = 15,
    inflation_rate: float = 0.06,
    discount_rate: float = 0.08,
) -> LifeInsuranceNeed:
    """Calculate life insurance need using three methods.

    Method 1: Human Life Value (HLV)
    - Present value of future earnings minus personal expenses

    Method 2: Expense Replacement
    - PV of family expenses for N years after death

    Method 3: Needs-Based
    - Sum: Debt payoff + Child education + Spouse income gap + Emergency
    """
    annual_income = profile.annual_income
    annual_expenses = profile.monthly_expenses.total * 12
    years_to_retire = profile.years_to_retirement

    # --- Method 1: Human Life Value ---
    # PV of future income minus personal expenses (assume 30% is personal)
    personal_expense_pct = 0.30
    net_annual_contribution = annual_income * (1 - personal_expense_pct)

    # PV of annuity for working years
    real_rate = (1 + discount_rate) / (1 + inflation_rate) - 1
    if real_rate > 0 and years_to_retire > 0:
        hlv = net_annual_contribution * (1 - (1 + real_rate) ** (-years_to_retire)) / real_rate
    else:
        hlv = net_annual_contribution * years_to_retire

    # --- Method 2: Expense Replacement ---
    # Family needs current expenses minus personal portion for N years
    family_annual_expenses = annual_expenses * (1 - personal_expense_pct)
    if real_rate > 0 and income_replacement_years > 0:
        expense_method = family_annual_expenses * (1 - (1 + real_rate) ** (-income_replacement_years)) / real_rate
    else:
        expense_method = family_annual_expenses * income_replacement_years

    # --- Method 3: Needs-Based ---
    # 1. Outstanding debt payoff
    debt_payoff = profile.debt.total_outstanding

    # 2. Children's future expenses (education + marriage)
    child_corpus = 5_000_000  # Rs 50L per child (rough estimate)
    # We don't have num_children in profile, estimate from age
    estimated_children = 1 if profile.age >= 28 else 0
    child_needs = child_corpus * estimated_children

    # 3. Emergency fund if not already covered
    emergency_buffer = max(
        profile.monthly_expenses.total * 12 - profile.emergency_fund,
        0,
    )

    # 4. Final expenses (funeral, estate)
    final_expenses = 500_000

    # 5. Spouse income gap (if spouse doesn't earn, cover until retirement)
    spouse_gap = family_annual_expenses * min(income_replacement_years, 20)

    needs_method = debt_payoff + child_needs + emergency_buffer + final_expenses + spouse_gap

    # --- Recommended cover ---
    recommended = max(hlv, expense_method, needs_method)

    # Subtract existing assets that can cover this
    existing_assets = (
        profile.current_investments
        + profile.epf_balance
        + profile.ppf_balance
        + profile.nps_balance
    )
    recommended_net = max(recommended - existing_assets, 0)

    current = profile.insurance.life_cover
    gap = max(recommended_net - current, 0)
    adequacy = (current / recommended_net * 100) if recommended_net > 0 else 100

    # Recommendations
    recs = []
    if gap > 0:
        recs.append(f"You need Rs {gap:,.0f} more life cover")
        # Term insurance estimate (Rs 500-700/lakh/year for 30-year-old)
        premium_per_lakh = 600 if profile.age <= 35 else 900 if profile.age <= 45 else 1500
        annual_premium = (gap / 100_000) * premium_per_lakh
        recs.append(f"Estimated term plan premium: Rs {annual_premium:,.0f}/year")
    if current > 0 and current < recommended_net * 0.5:
        recs.append("Your cover is less than 50% of what's needed - increase urgently")
    if profile.insurance.life_cover == 0:
        recs.append("No life insurance! Buy a term plan immediately if you have dependents")
    if profile.age > 45 and gap > 0:
        recs.append("Premiums increase with age - buy cover ASAP")

    breakdown = {
        "hlv_components": {
            "annual_contribution_to_family": round(net_annual_contribution),
            "working_years_remaining": years_to_retire,
        },
        "needs_components": {
            "debt_payoff": round(debt_payoff),
            "children_future": round(child_needs),
            "emergency_buffer": round(emergency_buffer),
            "final_expenses": final_expenses,
            "spouse_income_gap": round(spouse_gap),
        },
        "deductions": {
            "existing_investments": round(existing_assets),
        },
    }

    return LifeInsuranceNeed(
        hlv_method=hlv,
        expense_method=expense_method,
        needs_method=needs_method,
        recommended_cover=recommended_net,
        current_cover=current,
        gap=gap,
        adequacy_pct=adequacy,
        breakdown=breakdown,
        recommendations=recs,
    )


def calculate_health_insurance_need(
    profile: IndividualProfile,
    num_family_members: int = 3,
    city_tier: str = "metro",
) -> HealthInsuranceNeed:
    """Calculate health insurance adequacy.

    Rules of thumb for India:
    - Minimum: Rs 10L family floater
    - Metro cities: Rs 15-25L recommended
    - Non-metro: Rs 10-15L recommended
    - Age 40+: Consider Rs 25L+ with super top-up
    - Family with kids: Add Rs 5L per child
    """
    # Base recommendation by city
    base_cover = 1_500_000 if city_tier == "metro" else 1_000_000

    # Age factor
    age_multiplier = 1.0
    if profile.age >= 50:
        age_multiplier = 2.0
    elif profile.age >= 40:
        age_multiplier = 1.5
    elif profile.age >= 30:
        age_multiplier = 1.0

    # Family size factor
    family_multiplier = 1.0 + (num_family_members - 1) * 0.3

    recommended = base_cover * age_multiplier * family_multiplier
    recommended = max(recommended, 1_000_000)  # Minimum Rs 10L

    current = profile.insurance.health_cover
    gap = max(recommended - current, 0)
    adequacy = (current / recommended * 100) if recommended > 0 else 100

    # Super top-up analysis
    needs_top_up = current > 0 and current < recommended
    top_up_amount = gap if needs_top_up else 0

    # Premium estimate (rough: Rs 500-800 per lakh per year, varies by age)
    premium_per_lakh = 600 if profile.age <= 35 else 800 if profile.age <= 45 else 1200
    estimated_premium = (recommended / 100_000) * premium_per_lakh

    recs = []
    if current == 0:
        recs.append(f"No health insurance! Get Rs {recommended:,.0f} family floater immediately")
        recs.append(f"Estimated premium: Rs {estimated_premium:,.0f}/year (tax deductible under 80D)")
    elif current < 500_000:
        recs.append(f"Cover of Rs {current:,.0f} is very low - upgrade to Rs {recommended:,.0f}")
    elif gap > 0:
        recs.append(f"Consider a super top-up of Rs {top_up_amount:,.0f}")
        top_up_premium = (top_up_amount / 100_000) * (premium_per_lakh * 0.4)  # Top-ups are cheaper
        recs.append(f"Super top-up premium estimate: Rs {top_up_premium:,.0f}/year")

    if not profile.insurance.has_critical_illness:
        recs.append("Add critical illness rider (covers cancer, heart attack, etc.)")

    if profile.age >= 40:
        recs.append("At 40+, premiums rise fast - lock in a good plan now")

    return HealthInsuranceNeed(
        recommended_cover=recommended,
        current_cover=current,
        gap=gap,
        adequacy_pct=adequacy,
        needs_super_top_up=needs_top_up,
        recommended_top_up=top_up_amount,
        estimated_premium=estimated_premium,
        recommendations=recs,
    )
