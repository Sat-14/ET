"""Goal & FIRE Calculator Engine.

Handles:
- Individual financial goal planning (SIP needed, progress tracking)
- FIRE (Financial Independence Retire Early) calculations
- Monte Carlo simulation for probability-based projections
- Goal prioritization and SIP allocation
"""

from __future__ import annotations

import random
import math
from dataclasses import dataclass, field
from datetime import datetime

from src.models.goals import FinancialGoal, GoalType, GoalPriority


# Historical Nifty 50 annual returns for Monte Carlo
NIFTY_HISTORICAL_RETURNS = [
    0.0396, -0.0344, 0.7376, -0.0178, 0.1316, 0.3691, 0.0722,
    -0.1643, 0.3997, -0.1803, 0.3573, 0.3698, 0.1289, 0.0185,
    0.0189, 0.0304, -0.0363, 0.2897, 0.1495, 0.1268, -0.0910,
    0.1470, 0.1746, 0.2489, 0.2001,
]

# Default return assumptions by asset class
RETURN_ASSUMPTIONS = {
    "equity_large_cap": 0.12,
    "equity_mid_cap": 0.14,
    "equity_small_cap": 0.16,
    "debt_short": 0.07,
    "debt_long": 0.08,
    "ppf": 0.071,
    "epf": 0.081,
    "nps_equity": 0.10,
    "nps_debt": 0.08,
    "fd": 0.065,
    "gold": 0.08,
    "inflation": 0.06,
}


@dataclass
class GoalPlan:
    goal: FinancialGoal
    inflation_adjusted_target: float
    current_corpus_fv: float
    gap: float
    required_monthly_sip: float
    progress_pct: float
    on_track: bool
    years_remaining: int
    suggested_asset_class: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "goal_name": self.goal.name,
            "goal_type": self.goal.goal_type.value,
            "target_today": self.goal.target_amount,
            "inflation_adjusted_target": round(self.inflation_adjusted_target),
            "current_corpus": self.goal.current_corpus,
            "current_corpus_fv": round(self.current_corpus_fv),
            "gap": round(self.gap),
            "current_sip": self.goal.monthly_sip,
            "required_monthly_sip": round(self.required_monthly_sip),
            "progress_pct": round(self.progress_pct, 1),
            "on_track": self.on_track,
            "years_remaining": self.years_remaining,
            "suggested_asset_class": self.suggested_asset_class,
            "notes": self.notes,
        }


@dataclass
class FIREResult:
    fire_number: float  # Corpus needed for FIRE
    years_to_fire: float
    monthly_sip_needed: float
    current_savings_rate: float
    projected_fire_age: int
    safe_withdrawal_rate: float
    annual_passive_income: float

    def to_dict(self) -> dict:
        return {
            "fire_number": round(self.fire_number),
            "years_to_fire": round(self.years_to_fire, 1),
            "monthly_sip_needed": round(self.monthly_sip_needed),
            "current_savings_rate": round(self.current_savings_rate, 1),
            "projected_fire_age": self.projected_fire_age,
            "safe_withdrawal_rate": self.safe_withdrawal_rate,
            "annual_passive_income_at_fire": round(self.annual_passive_income),
        }


@dataclass
class MonteCarloResult:
    success_probability: float  # % of simulations where goal is met
    median_outcome: float
    p10_outcome: float  # 10th percentile (pessimistic)
    p90_outcome: float  # 90th percentile (optimistic)
    simulations: int

    def to_dict(self) -> dict:
        return {
            "success_probability": round(self.success_probability, 1),
            "median_outcome": round(self.median_outcome),
            "pessimistic_p10": round(self.p10_outcome),
            "optimistic_p90": round(self.p90_outcome),
            "simulations": self.simulations,
        }


def _suggest_asset_class(years: int) -> str:
    """Suggest asset class based on goal timeline."""
    if years >= 7:
        return "Equity (Large/Multi Cap MF)"
    elif years >= 4:
        return "Hybrid (Aggressive Hybrid MF)"
    elif years >= 2:
        return "Debt (Short Duration MF)"
    else:
        return "Liquid/Ultra-Short Duration MF"


def _expected_return_for_horizon(years: int) -> float:
    """Expected return based on horizon."""
    if years >= 7:
        return 0.12
    elif years >= 4:
        return 0.10
    elif years >= 2:
        return 0.08
    else:
        return 0.06


def plan_goal(goal: FinancialGoal) -> GoalPlan:
    """Create a detailed plan for a single financial goal."""
    years = goal.years_remaining
    if years <= 0:
        return GoalPlan(
            goal=goal,
            inflation_adjusted_target=goal.target_amount,
            current_corpus_fv=goal.current_corpus,
            gap=max(goal.target_amount - goal.current_corpus, 0),
            required_monthly_sip=0,
            progress_pct=min(goal.current_corpus / goal.target_amount * 100, 100) if goal.target_amount > 0 else 100,
            on_track=goal.current_corpus >= goal.target_amount,
            years_remaining=0,
            suggested_asset_class="Liquid Fund (immediate need)",
            notes=["Goal deadline has passed or is immediate"],
        )

    inf_target = goal.inflation_adjusted_target
    corpus_fv = goal.future_value_of_current_corpus
    gap = goal.gap
    req_sip = goal.required_monthly_sip()
    progress = goal.progress_pct
    asset_class = _suggest_asset_class(years)

    # Check if current SIP is sufficient
    on_track = goal.monthly_sip >= req_sip * 0.95 if req_sip > 0 else True
    notes = []
    if not on_track:
        deficit = req_sip - goal.monthly_sip
        notes.append(f"Increase SIP by Rs {deficit:,.0f}/month to stay on track")
    if years <= 3 and goal.expected_return > 10:
        notes.append("Goal is near - consider shifting to debt/hybrid funds for safety")
    if goal.current_corpus == 0 and years > 0:
        notes.append("Start investing now - the earlier you start, the lower the monthly SIP needed")

    return GoalPlan(
        goal=goal,
        inflation_adjusted_target=inf_target,
        current_corpus_fv=corpus_fv,
        gap=gap,
        required_monthly_sip=req_sip,
        progress_pct=progress,
        on_track=on_track,
        years_remaining=years,
        suggested_asset_class=asset_class,
        notes=notes,
    )


def plan_all_goals(goals: list[FinancialGoal]) -> list[GoalPlan]:
    """Plan all goals and sort by priority."""
    plans = [plan_goal(g) for g in goals]
    priority_order = {
        GoalPriority.CRITICAL: 0,
        GoalPriority.HIGH: 1,
        GoalPriority.MEDIUM: 2,
        GoalPriority.LOW: 3,
    }
    plans.sort(key=lambda p: priority_order.get(p.goal.priority, 4))
    return plans


def calculate_fire(
    current_age: int,
    annual_expenses: float,
    current_corpus: float,
    monthly_investment: float,
    expected_return: float = 0.10,
    inflation_rate: float = 0.06,
    safe_withdrawal_rate: float = 0.04,
) -> FIREResult:
    """Calculate FIRE (Financial Independence Retire Early) number and timeline.

    FIRE Number = Annual Expenses / Safe Withdrawal Rate (adjusted for inflation)
    """
    # FIRE number in today's terms
    fire_number_today = annual_expenses / safe_withdrawal_rate

    # Find years to FIRE using iterative projection
    corpus = current_corpus
    years = 0
    max_years = 60  # Safety cap

    real_return = (1 + expected_return) / (1 + inflation_rate) - 1

    while years < max_years:
        # Check if corpus can sustain expenses via SWR
        if corpus * safe_withdrawal_rate >= annual_expenses:
            break
        # Grow corpus
        corpus = corpus * (1 + real_return) + (monthly_investment * 12)
        annual_expenses = annual_expenses  # Already in real terms
        years += 1

    fire_age = current_age + years
    annual_passive = fire_number_today * safe_withdrawal_rate

    # Current savings rate
    monthly_income = (annual_expenses / 12) + monthly_investment
    savings_rate = (monthly_investment / monthly_income * 100) if monthly_income > 0 else 0

    return FIREResult(
        fire_number=fire_number_today,
        years_to_fire=years,
        monthly_sip_needed=monthly_investment,
        current_savings_rate=savings_rate,
        projected_fire_age=fire_age,
        safe_withdrawal_rate=safe_withdrawal_rate,
        annual_passive_income=annual_passive,
    )


def monte_carlo_simulation(
    current_corpus: float,
    monthly_sip: float,
    years: int,
    target_amount: float,
    num_simulations: int = 5000,
    historical_returns: list[float] | None = None,
) -> MonteCarloResult:
    """Run Monte Carlo simulation for goal achievement probability.

    Randomly samples from historical Nifty returns to simulate
    multiple possible outcomes.
    """
    if historical_returns is None:
        historical_returns = NIFTY_HISTORICAL_RETURNS

    if not historical_returns or years <= 0:
        return MonteCarloResult(
            success_probability=100.0 if current_corpus >= target_amount else 0.0,
            median_outcome=current_corpus,
            p10_outcome=current_corpus,
            p90_outcome=current_corpus,
            simulations=0,
        )

    outcomes = []
    for _ in range(num_simulations):
        corpus = current_corpus
        for year in range(years):
            annual_return = random.choice(historical_returns)
            corpus = corpus * (1 + annual_return) + (monthly_sip * 12)
        outcomes.append(corpus)

    outcomes.sort()
    successes = sum(1 for o in outcomes if o >= target_amount)

    return MonteCarloResult(
        success_probability=(successes / num_simulations) * 100,
        median_outcome=outcomes[len(outcomes) // 2],
        p10_outcome=outcomes[int(len(outcomes) * 0.10)],
        p90_outcome=outcomes[int(len(outcomes) * 0.90)],
        simulations=num_simulations,
    )


def allocate_sip_across_goals(
    goals: list[FinancialGoal],
    total_available_sip: float,
) -> dict[str, float]:
    """Allocate available SIP budget across goals by priority and gap.

    Strategy:
    1. Critical goals get funded first
    2. Then high, medium, low in order
    3. Within same priority, proportional to gap
    """
    plans = plan_all_goals(goals)
    allocation: dict[str, float] = {}
    remaining = total_available_sip

    priority_groups = {}
    for plan in plans:
        p = plan.goal.priority
        priority_groups.setdefault(p, []).append(plan)

    for priority in [GoalPriority.CRITICAL, GoalPriority.HIGH, GoalPriority.MEDIUM, GoalPriority.LOW]:
        group = priority_groups.get(priority, [])
        if not group or remaining <= 0:
            continue

        total_needed = sum(p.required_monthly_sip for p in group)
        if total_needed <= remaining:
            for plan in group:
                allocation[plan.goal.name] = plan.required_monthly_sip
                remaining -= plan.required_monthly_sip
        else:
            # Proportional allocation
            for plan in group:
                if total_needed > 0:
                    share = (plan.required_monthly_sip / total_needed) * remaining
                else:
                    share = remaining / len(group)
                allocation[plan.goal.name] = round(share)
            remaining = 0

    return allocation
