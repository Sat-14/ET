"""Money Health Score Engine - Computes 0-100 score across 6 dimensions.

Dimensions:
1. Emergency Fund Adequacy  (0-20 pts)
2. Insurance Coverage       (0-15 pts)
3. Portfolio Diversification (0-20 pts)
4. Debt Health              (0-15 pts)
5. Tax Efficiency           (0-15 pts)
6. Retirement Readiness     (0-15 pts)

Total: 100 points
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from src.models.user import IndividualProfile
from src.models.portfolio import Portfolio
from src.engines.tax_calculator import compare_regimes


@dataclass
class DimensionScore:
    name: str
    score: float  # 0 to max_score
    max_score: float
    grade: str  # A, B, C, D, F
    details: str
    recommendations: list[str] = field(default_factory=list)

    @property
    def pct(self) -> float:
        return (self.score / self.max_score * 100) if self.max_score > 0 else 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "score": round(self.score, 1),
            "max_score": self.max_score,
            "pct": round(self.pct, 1),
            "grade": self.grade,
            "details": self.details,
            "recommendations": self.recommendations,
        }


@dataclass
class MoneyHealthReport:
    overall_score: float
    overall_grade: str
    dimensions: list[DimensionScore]
    top_actions: list[str]  # Top 3 actionable improvements

    def to_dict(self) -> dict:
        return {
            "overall_score": round(self.overall_score, 1),
            "overall_grade": self.overall_grade,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "top_actions": self.top_actions,
        }


def _grade(pct: float) -> str:
    if pct >= 90:
        return "A"
    if pct >= 75:
        return "B"
    if pct >= 50:
        return "C"
    if pct >= 25:
        return "D"
    return "F"


def score_emergency_fund(profile: IndividualProfile) -> DimensionScore:
    """Score emergency fund adequacy (0-20 points).

    Target: 6 months of expenses + EMIs.
    """
    MAX_SCORE = 20.0
    monthly_need = profile.monthly_expenses.total + profile.debt.total_monthly_emi
    target = monthly_need * 6  # 6 months target

    if target == 0:
        return DimensionScore(
            name="Emergency Fund",
            score=MAX_SCORE,
            max_score=MAX_SCORE,
            grade="A",
            details="No monthly expenses tracked - assume adequate",
            recommendations=[],
        )

    months_covered = profile.emergency_fund / monthly_need if monthly_need > 0 else 0
    ratio = min(months_covered / 6, 1.0)
    score = ratio * MAX_SCORE

    recs = []
    if months_covered < 3:
        shortfall = (3 * monthly_need) - profile.emergency_fund
        recs.append(f"Build at least 3 months buffer - need Rs {shortfall:,.0f} more")
    elif months_covered < 6:
        shortfall = target - profile.emergency_fund
        recs.append(f"Increase to 6 months - need Rs {shortfall:,.0f} more")

    return DimensionScore(
        name="Emergency Fund",
        score=score,
        max_score=MAX_SCORE,
        grade=_grade(score / MAX_SCORE * 100),
        details=f"{months_covered:.1f} months covered (target: 6 months = Rs {target:,.0f})",
        recommendations=recs,
    )


def score_insurance(profile: IndividualProfile) -> DimensionScore:
    """Score insurance coverage (0-15 points).

    Life: 10x annual income
    Health: Rs 10L+ family cover
    """
    MAX_SCORE = 15.0
    score = 0.0
    recs = []

    # Life insurance (8 points)
    life_target = profile.annual_income * 10
    if life_target > 0:
        life_ratio = min(profile.insurance.life_cover / life_target, 1.0)
    else:
        life_ratio = 1.0
    life_score = life_ratio * 8
    score += life_score
    if life_ratio < 0.5:
        gap = life_target - profile.insurance.life_cover
        recs.append(f"Get term insurance - need Rs {gap:,.0f} more cover (10x income)")
    elif life_ratio < 1.0:
        gap = life_target - profile.insurance.life_cover
        recs.append(f"Increase life cover by Rs {gap:,.0f} to reach 10x income")

    # Health insurance (5 points)
    health_target = 1_000_000  # Rs 10L minimum
    if profile.insurance.health_cover >= health_target:
        health_score = 5.0
    elif profile.insurance.health_cover >= 500_000:
        health_score = 3.0
        recs.append("Upgrade health cover to Rs 10L+ (consider super top-up)")
    elif profile.insurance.health_cover > 0:
        health_score = 1.5
        recs.append("Health cover is low - get at least Rs 10L family floater")
    else:
        health_score = 0.0
        recs.append("No health insurance! Get Rs 10L+ family floater immediately")
    score += health_score

    # Critical illness (2 points)
    if profile.insurance.has_critical_illness:
        score += 2.0
    else:
        recs.append("Consider adding critical illness rider")

    return DimensionScore(
        name="Insurance Coverage",
        score=min(score, MAX_SCORE),
        max_score=MAX_SCORE,
        grade=_grade(min(score, MAX_SCORE) / MAX_SCORE * 100),
        details=f"Life: Rs {profile.insurance.life_cover:,.0f} / {life_target:,.0f}, Health: Rs {profile.insurance.health_cover:,.0f}",
        recommendations=recs,
    )


def score_diversification(portfolio: Portfolio) -> DimensionScore:
    """Score portfolio diversification (0-20 points).

    Uses Shannon entropy of category allocation.
    Also penalizes: too many funds, high overlap, high expense ratios.
    """
    MAX_SCORE = 20.0
    score = 0.0
    recs = []

    if not portfolio.holdings:
        return DimensionScore(
            name="Portfolio Diversification",
            score=0,
            max_score=MAX_SCORE,
            grade="F",
            details="No portfolio data available",
            recommendations=["Upload your CAS statement to analyze portfolio"],
        )

    allocation = portfolio.category_allocation()

    # Entropy-based diversity score (0-10 points)
    if allocation:
        proportions = [v / 100 for v in allocation.values() if v > 0]
        entropy = -sum(p * math.log(p) for p in proportions if p > 0)
        max_entropy = math.log(max(len(proportions), 1))
        diversity_ratio = entropy / max_entropy if max_entropy > 0 else 0
        entropy_score = diversity_ratio * 10
    else:
        entropy_score = 0
    score += entropy_score

    # Concentration penalty (0-5 points)
    max_allocation = max(allocation.values()) if allocation else 0
    if max_allocation <= 30:
        conc_score = 5.0
    elif max_allocation <= 50:
        conc_score = 3.0
        top_cat = max(allocation, key=allocation.get)
        recs.append(f"High concentration in {top_cat.value} ({max_allocation:.0f}%) - diversify")
    else:
        conc_score = 1.0
        top_cat = max(allocation, key=allocation.get)
        recs.append(f"Very high concentration in {top_cat.value} ({max_allocation:.0f}%) - rebalance urgently")
    score += conc_score

    # Fund count score (0-3 points) - penalize too many or too few
    n = portfolio.num_funds
    if 5 <= n <= 12:
        fund_score = 3.0
    elif 3 <= n <= 15:
        fund_score = 2.0
    elif n < 3:
        fund_score = 1.0
        recs.append("Too few funds - consider adding 2-3 more for diversification")
    else:
        fund_score = 1.0
        recs.append(f"Too many funds ({n}) - consolidate to 8-12 for better tracking")
    score += fund_score

    # Expense ratio score (0-2 points)
    total_value = portfolio.total_current_value
    if total_value > 0:
        weighted_er = portfolio.total_expense_drag() / total_value * 100
        if weighted_er <= 0.5:
            er_score = 2.0
        elif weighted_er <= 1.0:
            er_score = 1.0
        else:
            er_score = 0.0
            recs.append(f"High expense ratio ({weighted_er:.2f}%) - switch to direct plans")
    else:
        er_score = 1.0
    score += er_score

    return DimensionScore(
        name="Portfolio Diversification",
        score=min(score, MAX_SCORE),
        max_score=MAX_SCORE,
        grade=_grade(min(score, MAX_SCORE) / MAX_SCORE * 100),
        details=f"{portfolio.num_funds} funds across {len(allocation)} categories",
        recommendations=recs,
    )


def score_debt_health(profile: IndividualProfile) -> DimensionScore:
    """Score debt health (0-15 points).

    Metrics: Debt-to-income ratio, EMI-to-income ratio, credit card debt.
    """
    MAX_SCORE = 15.0
    score = 0.0
    recs = []

    monthly_income = profile.monthly_income
    debt = profile.debt

    if monthly_income == 0:
        return DimensionScore(
            name="Debt Health",
            score=MAX_SCORE,
            max_score=MAX_SCORE,
            grade="A",
            details="No income data - cannot assess",
            recommendations=[],
        )

    # EMI-to-income ratio (0-8 points) - should be < 40%
    emi_ratio = (debt.total_monthly_emi / monthly_income) if monthly_income > 0 else 0
    if emi_ratio == 0:
        emi_score = 8.0
    elif emi_ratio <= 0.30:
        emi_score = 7.0
    elif emi_ratio <= 0.40:
        emi_score = 5.0
        recs.append(f"EMI-to-income ratio is {emi_ratio:.0%} - keep below 40%")
    elif emi_ratio <= 0.50:
        emi_score = 3.0
        recs.append(f"EMI-to-income ratio is high ({emi_ratio:.0%}) - reduce debt")
    else:
        emi_score = 1.0
        recs.append(f"EMI-to-income ratio is critical ({emi_ratio:.0%}) - prioritize debt repayment")
    score += emi_score

    # Credit card debt (0-4 points) - should be 0
    if debt.credit_card_outstanding == 0:
        cc_score = 4.0
    elif debt.credit_card_outstanding <= 50_000:
        cc_score = 2.0
        recs.append(f"Clear credit card debt of Rs {debt.credit_card_outstanding:,.0f} immediately (high interest)")
    else:
        cc_score = 0.0
        recs.append(f"High credit card debt Rs {debt.credit_card_outstanding:,.0f} - pay this off first!")
    score += cc_score

    # Personal loan (0-3 points)
    if debt.personal_loan_outstanding == 0:
        pl_score = 3.0
    elif debt.personal_loan_outstanding <= 200_000:
        pl_score = 1.5
        recs.append("Consider prepaying personal loan (high interest rate)")
    else:
        pl_score = 0.5
        recs.append(f"Large personal loan Rs {debt.personal_loan_outstanding:,.0f} - plan accelerated repayment")
    score += pl_score

    return DimensionScore(
        name="Debt Health",
        score=min(score, MAX_SCORE),
        max_score=MAX_SCORE,
        grade=_grade(min(score, MAX_SCORE) / MAX_SCORE * 100),
        details=f"EMI/Income: {emi_ratio:.0%}, Total debt: Rs {debt.total_outstanding:,.0f}",
        recommendations=recs,
    )


def score_tax_efficiency(profile: IndividualProfile) -> DimensionScore:
    """Score tax efficiency (0-15 points).

    Measures: Are they in the right regime? Are deductions fully utilized?
    """
    MAX_SCORE = 15.0
    score = 0.0
    recs = []

    comparison = compare_regimes(profile)

    # Are they (or would they be) in the optimal regime? (0-8 points)
    if comparison.tax_saving == 0:
        regime_score = 8.0
    elif comparison.tax_saving <= 10_000:
        regime_score = 6.0
    elif comparison.tax_saving <= 50_000:
        regime_score = 4.0
        recs.append(
            f"Switch to {comparison.recommended_regime.value} regime to save Rs {comparison.tax_saving:,.0f}/year"
        )
    else:
        regime_score = 2.0
        recs.append(
            f"Wrong regime! Switch to {comparison.recommended_regime.value} to save Rs {comparison.tax_saving:,.0f}/year"
        )
    score += regime_score

    # Deduction utilization (0-7 points) - only relevant for old regime
    unused = comparison.unused_deduction_room
    total_unused = sum(unused.values())
    if total_unused == 0:
        util_score = 7.0
    elif total_unused <= 50_000:
        util_score = 5.0
    elif total_unused <= 150_000:
        util_score = 3.0
    else:
        util_score = 1.0
    score += util_score

    for section, amount in unused.items():
        if amount > 10_000:
            recs.append(f"Rs {amount:,.0f} unused in {section} - invest to save tax")

    return DimensionScore(
        name="Tax Efficiency",
        score=min(score, MAX_SCORE),
        max_score=MAX_SCORE,
        grade=_grade(min(score, MAX_SCORE) / MAX_SCORE * 100),
        details=f"Best regime: {comparison.recommended_regime.value}, saves Rs {comparison.tax_saving:,.0f}",
        recommendations=recs,
    )


def score_retirement_readiness(profile: IndividualProfile) -> DimensionScore:
    """Score retirement readiness (0-15 points).

    Based on: current corpus vs required corpus at retirement.
    """
    MAX_SCORE = 15.0
    recs = []

    years = profile.years_to_retirement
    if years <= 0:
        return DimensionScore(
            name="Retirement Readiness",
            score=MAX_SCORE * 0.5,
            max_score=MAX_SCORE,
            grade="C",
            details="Already at/past retirement age",
            recommendations=["Consult a financial advisor for retirement income planning"],
        )

    # Required corpus at retirement
    annual_expenses = profile.monthly_expenses.total * 12
    inflation_rate = 0.06
    post_retirement_return = 0.08
    post_retirement_years = 25  # Assume 25 years post retirement

    # Future annual expenses at retirement (inflation adjusted)
    future_annual_expense = annual_expenses * (1 + inflation_rate) ** years

    # Required corpus = PV of annuity for post-retirement years
    real_return = (post_retirement_return - inflation_rate) / (1 + inflation_rate)
    if real_return > 0:
        required_corpus = future_annual_expense * (1 - (1 + real_return) ** (-post_retirement_years)) / real_return
    else:
        required_corpus = future_annual_expense * post_retirement_years

    # Current retirement corpus FV
    current_corpus = profile.total_retirement_corpus + profile.current_investments * 0.5  # 50% for retirement
    pre_retirement_return = 0.10
    future_corpus = current_corpus * (1 + pre_retirement_return) ** years

    # Add future SIP contributions
    monthly_retirement_sip = profile.monthly_sip * 0.5  # 50% of SIP for retirement
    r = pre_retirement_return / 12
    n = years * 12
    if r > 0:
        sip_fv = monthly_retirement_sip * ((1 + r) ** n - 1) / r * (1 + r)
    else:
        sip_fv = monthly_retirement_sip * n
    projected_corpus = future_corpus + sip_fv

    # Score
    if required_corpus > 0:
        readiness = min(projected_corpus / required_corpus, 1.0)
    else:
        readiness = 1.0

    score = readiness * MAX_SCORE

    if readiness < 0.25:
        gap = required_corpus - projected_corpus
        recs.append(f"Retirement corpus gap: Rs {gap:,.0f} - start investing aggressively")
        recs.append("Consider NPS for tax benefit + retirement corpus")
    elif readiness < 0.50:
        gap = required_corpus - projected_corpus
        recs.append(f"Need Rs {gap:,.0f} more for retirement - increase SIP by 20%")
    elif readiness < 0.75:
        recs.append("On track but increase SIP with every salary hike")

    return DimensionScore(
        name="Retirement Readiness",
        score=min(score, MAX_SCORE),
        max_score=MAX_SCORE,
        grade=_grade(min(score, MAX_SCORE) / MAX_SCORE * 100),
        details=f"Projected: Rs {projected_corpus:,.0f} / Required: Rs {required_corpus:,.0f} ({readiness:.0%})",
        recommendations=recs,
    )


def compute_money_health_score(
    profile: IndividualProfile,
    portfolio: Portfolio | None = None,
) -> MoneyHealthReport:
    """Compute the complete Money Health Score across all 6 dimensions."""
    if portfolio is None:
        portfolio = Portfolio()

    dimensions = [
        score_emergency_fund(profile),
        score_insurance(profile),
        score_diversification(portfolio),
        score_debt_health(profile),
        score_tax_efficiency(profile),
        score_retirement_readiness(profile),
    ]

    overall = sum(d.score for d in dimensions)
    overall_grade = _grade(overall)

    # Collect top 3 actions (from lowest scoring dimensions)
    all_recs = []
    for d in sorted(dimensions, key=lambda x: x.pct):
        for rec in d.recommendations:
            if rec not in all_recs:
                all_recs.append(rec)

    return MoneyHealthReport(
        overall_score=overall,
        overall_grade=overall_grade,
        dimensions=dimensions,
        top_actions=all_recs[:3],
    )
