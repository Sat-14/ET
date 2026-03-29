"""CashFlow Projector - Life-Event Simulator ("What if..." Engine).

Projects monthly cash flows over N years, applying life events,
and computing impact on Money Health Score dimensions.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime

from src.engines.goal_calculator import allocate_sip_across_goals, plan_all_goals
from src.engines.insurance_calculator import (
    calculate_health_insurance_need,
    calculate_life_insurance_need,
)
from src.engines.rebalancer import generate_rebalance_plan
from src.engines.tax_calculator import compare_regimes
from src.engines.xirr_calculator import (
    analyze_benchmark_comparison,
    compute_portfolio_returns,
)
from src.models.portfolio import Portfolio
from src.models.user import IndividualProfile
from src.models.goals import LifeEvent


@dataclass
class MonthlySnapshot:
    year: int
    month: int
    income: float
    expenses: float
    emi: float
    tax: float
    investable_surplus: float
    cumulative_investments: float
    emergency_fund: float
    net_worth: float


@dataclass
class ProjectionResult:
    timeline: list[MonthlySnapshot]
    summary: ProjectionSummary
    events_applied: list[str]


@dataclass
class ProjectionSummary:
    total_years: int
    final_net_worth: float
    final_monthly_income: float
    final_monthly_expenses: float
    total_invested: float
    total_tax_paid: float
    min_emergency_fund_month: int  # Month where EF was lowest
    min_emergency_fund_amount: float
    average_savings_rate: float

    def to_dict(self) -> dict:
        return {
            "total_years": self.total_years,
            "final_net_worth": round(self.final_net_worth),
            "final_monthly_income": round(self.final_monthly_income),
            "final_monthly_expenses": round(self.final_monthly_expenses),
            "total_invested": round(self.total_invested),
            "total_tax_paid": round(self.total_tax_paid),
            "min_emergency_fund_month": self.min_emergency_fund_month,
            "min_emergency_fund_amount": round(self.min_emergency_fund_amount),
            "average_savings_rate_pct": round(self.average_savings_rate, 1),
        }


@dataclass
class ScenarioComparison:
    baseline: ProjectionSummary
    with_events: ProjectionSummary
    deltas: dict

    def to_dict(self) -> dict:
        return {
            "baseline": self.baseline.to_dict(),
            "with_events": self.with_events.to_dict(),
            "deltas": self.deltas,
        }


def project_cashflows(
    profile: IndividualProfile,
    years: int = 10,
    events: list[LifeEvent] | None = None,
    annual_income_growth: float = 0.08,
    annual_expense_inflation: float = 0.06,
    investment_return: float = 0.10,
) -> ProjectionResult:
    """Project monthly cash flows over N years with life events.

    Args:
        profile: User's current financial profile.
        years: Number of years to project.
        events: List of life events to simulate.
        annual_income_growth: Expected annual income growth rate.
        annual_expense_inflation: Annual expense inflation rate.
        investment_return: Expected annual investment return.
    """
    if events is None:
        events = []

    current_year = datetime.now().year
    current_month = datetime.now().month

    # Initialize state from profile
    monthly_income = profile.monthly_income
    monthly_expenses = profile.monthly_expenses.total
    monthly_emi = profile.debt.total_monthly_emi
    emergency_fund = profile.emergency_fund
    investments = profile.current_investments
    monthly_sip = profile.monthly_sip

    # Monthly growth rates
    monthly_investment_return = (1 + investment_return) ** (1 / 12) - 1

    timeline: list[MonthlySnapshot] = []
    events_applied: list[str] = []
    total_tax = 0.0
    total_invested = 0.0

    # Track active temporary events
    active_temp_events: list[tuple[LifeEvent, int]] = []  # (event, months_remaining)

    for month_idx in range(years * 12):
        year = current_year + (current_month + month_idx - 1) // 12
        month = (current_month + month_idx - 1) % 12 + 1

        # Apply income and expense growth
        if month_idx > 0 and month_idx % 12 == 0:
            monthly_income *= (1 + annual_income_growth)
            monthly_expenses *= (1 + annual_expense_inflation)

        # Apply new life events that start this month
        temp_income_change = 0.0
        temp_expense_change = 0.0
        temp_emi_change = 0.0

        for event in events:
            if event.year == year and event.month == month:
                events_applied.append(f"{event.name} ({year}-{month:02d})")

                # One-time cost
                if event.one_time_cost > 0:
                    if emergency_fund >= event.one_time_cost:
                        emergency_fund -= event.one_time_cost
                    else:
                        shortfall = event.one_time_cost - emergency_fund
                        emergency_fund = 0
                        investments = max(investments - shortfall, 0)

                # Permanent income change
                if event.duration_months == 0 and event.monthly_income_change != 0:
                    monthly_income += event.monthly_income_change

                # Permanent expense change
                if event.duration_months == 0 and event.monthly_expense_change != 0:
                    monthly_expenses += event.monthly_expense_change

                # Permanent EMI
                if event.duration_months == 0 and event.new_emi > 0:
                    monthly_emi += event.new_emi

                # Temporary changes
                if event.duration_months > 0:
                    active_temp_events.append((event, event.duration_months))

        # Apply active temporary events
        still_active = []
        for event, remaining in active_temp_events:
            if remaining > 0:
                temp_income_change += event.monthly_income_change
                temp_expense_change += event.monthly_expense_change
                temp_emi_change += event.new_emi
                still_active.append((event, remaining - 1))
        active_temp_events = still_active

        # Compute monthly figures
        effective_income = max(monthly_income + temp_income_change, 0)
        effective_expenses = monthly_expenses + temp_expense_change
        effective_emi = monthly_emi + temp_emi_change

        # Approximate monthly tax (simplified)
        annual_taxable = effective_income * 12
        if annual_taxable > 1_500_000:
            monthly_tax = effective_income * 0.25
        elif annual_taxable > 1_000_000:
            monthly_tax = effective_income * 0.20
        elif annual_taxable > 500_000:
            monthly_tax = effective_income * 0.10
        else:
            monthly_tax = 0
        total_tax += monthly_tax

        # Investable surplus
        surplus = effective_income - effective_expenses - effective_emi - monthly_tax

        # Invest surplus (or drain EF/investments if negative)
        if surplus >= monthly_sip:
            investments += monthly_sip
            total_invested += monthly_sip
            remaining_surplus = surplus - monthly_sip
            # Build emergency fund up to 6 months
            ef_target = (effective_expenses + effective_emi) * 6
            if emergency_fund < ef_target:
                ef_add = min(remaining_surplus * 0.3, ef_target - emergency_fund)
                emergency_fund += ef_add
                remaining_surplus -= ef_add
            investments += remaining_surplus
            total_invested += remaining_surplus
        elif surplus > 0:
            investments += surplus
            total_invested += surplus
        else:
            # Negative surplus - drain emergency fund first, then investments
            deficit = abs(surplus)
            if emergency_fund >= deficit:
                emergency_fund -= deficit
            else:
                deficit -= emergency_fund
                emergency_fund = 0
                investments = max(investments - deficit, 0)

        # Grow investments monthly
        investments *= (1 + monthly_investment_return)

        net_worth = investments + emergency_fund

        timeline.append(MonthlySnapshot(
            year=year,
            month=month,
            income=round(effective_income),
            expenses=round(effective_expenses),
            emi=round(effective_emi),
            tax=round(monthly_tax),
            investable_surplus=round(surplus),
            cumulative_investments=round(investments),
            emergency_fund=round(emergency_fund),
            net_worth=round(net_worth),
        ))

    # Compute summary
    min_ef = min(timeline, key=lambda s: s.emergency_fund)
    min_ef_idx = timeline.index(min_ef)

    savings_rates = [
        (s.investable_surplus / s.income * 100) if s.income > 0 else 0
        for s in timeline
    ]
    avg_savings = sum(savings_rates) / len(savings_rates) if savings_rates else 0

    last = timeline[-1] if timeline else None
    summary = ProjectionSummary(
        total_years=years,
        final_net_worth=last.net_worth if last else 0,
        final_monthly_income=last.income if last else 0,
        final_monthly_expenses=last.expenses if last else 0,
        total_invested=total_invested,
        total_tax_paid=total_tax,
        min_emergency_fund_month=min_ef_idx + 1,
        min_emergency_fund_amount=min_ef.emergency_fund,
        average_savings_rate=avg_savings,
    )

    return ProjectionResult(
        timeline=timeline,
        summary=summary,
        events_applied=events_applied,
    )


def compare_scenarios(
    profile: IndividualProfile,
    events: list[LifeEvent],
    years: int = 10,
) -> ScenarioComparison:
    """Compare baseline (no events) vs scenario with events."""
    baseline = project_cashflows(profile, years=years, events=[])
    with_events = project_cashflows(profile, years=years, events=events)

    deltas = {
        "net_worth_impact": round(
            with_events.summary.final_net_worth - baseline.summary.final_net_worth
        ),
        "net_worth_impact_pct": round(
            ((with_events.summary.final_net_worth - baseline.summary.final_net_worth)
             / baseline.summary.final_net_worth * 100)
            if baseline.summary.final_net_worth > 0 else 0, 1
        ),
        "total_investment_impact": round(
            with_events.summary.total_invested - baseline.summary.total_invested
        ),
        "emergency_fund_stress": round(
            with_events.summary.min_emergency_fund_amount
            - baseline.summary.min_emergency_fund_amount
        ),
        "savings_rate_impact": round(
            with_events.summary.average_savings_rate
            - baseline.summary.average_savings_rate, 1
        ),
        "events_applied": with_events.events_applied,
    }

    return ScenarioComparison(
        baseline=baseline.summary,
        with_events=with_events.summary,
        deltas=deltas,
    )


def _best_monthly_in_hand(profile: IndividualProfile) -> float:
    comparison = compare_regimes(profile)
    if comparison.recommended_regime.value == "old":
        return comparison.old_regime.monthly_in_hand
    return comparison.new_regime.monthly_in_hand


def _monthly_surplus(profile: IndividualProfile) -> float:
    return max(
        _best_monthly_in_hand(profile)
        - profile.monthly_expenses.total
        - profile.debt.total_monthly_emi,
        0.0,
    )


def _build_event_adjusted_profile(
    profile: IndividualProfile,
    events: list[LifeEvent],
) -> tuple[IndividualProfile, float]:
    adjusted = copy.deepcopy(profile)
    lump_sum_inflow = 0.0

    for event in events:
        active_months = 12 if event.duration_months == 0 else min(event.duration_months, 12)

        if event.duration_months == 0:
            adjusted.salary.special_allowance += event.monthly_income_change * 12
            adjusted.monthly_expenses.misc = max(
                adjusted.monthly_expenses.misc + event.monthly_expense_change,
                0.0,
            )
            adjusted.debt.other_loan_emi += event.new_emi
        else:
            adjusted.other_income += event.monthly_income_change * active_months
            adjusted.monthly_expenses.misc = max(
                adjusted.monthly_expenses.misc + (event.monthly_expense_change * active_months / 12),
                0.0,
            )
            adjusted.debt.other_loan_emi += event.new_emi * active_months / 12

        if event.one_time_cost > 0:
            if adjusted.emergency_fund >= event.one_time_cost:
                adjusted.emergency_fund -= event.one_time_cost
            else:
                shortfall = event.one_time_cost - adjusted.emergency_fund
                adjusted.emergency_fund = 0.0
                adjusted.current_investments = max(adjusted.current_investments - shortfall, 0.0)
        elif event.one_time_cost < 0:
            inflow = abs(event.one_time_cost)
            lump_sum_inflow += inflow
            emergency_target = (
                adjusted.monthly_expenses.total + adjusted.debt.total_monthly_emi
            ) * 6
            ef_gap = max(emergency_target - adjusted.emergency_fund, 0.0)
            ef_add = min(ef_gap, inflow)
            adjusted.emergency_fund += ef_add
            adjusted.current_investments += inflow - ef_add

    return adjusted, lump_sum_inflow


def analyze_life_event_advisor(
    profile: IndividualProfile,
    events: list[LifeEvent],
    *,
    goals: list | None = None,
    portfolio: Portfolio | None = None,
    years: int = 10,
) -> dict:
    """Build integrated life-event advice across tax, goals, insurance, and portfolio."""
    goals = goals or []
    scenario = compare_scenarios(profile, events, years=years)
    adjusted_profile, lump_sum_inflow = _build_event_adjusted_profile(profile, events)

    baseline_tax = compare_regimes(profile)
    adjusted_tax = compare_regimes(adjusted_profile)
    baseline_best_tax = min(
        baseline_tax.old_regime.total_tax,
        baseline_tax.new_regime.total_tax,
    )
    adjusted_best_tax = min(
        adjusted_tax.old_regime.total_tax,
        adjusted_tax.new_regime.total_tax,
    )

    baseline_surplus = _monthly_surplus(profile)
    adjusted_surplus = _monthly_surplus(adjusted_profile)
    recommended_sip = max(round(adjusted_surplus * 0.8), 0)

    baseline_goal_plans = plan_all_goals(goals) if goals else []
    adjusted_goal_alloc = allocate_sip_across_goals(goals, recommended_sip) if goals else {}
    adjusted_goals = []
    if goals:
        for goal in goals:
            cloned_goal = copy.deepcopy(goal)
            cloned_goal.monthly_sip = adjusted_goal_alloc.get(goal.name, 0.0)
            adjusted_goals.append(cloned_goal)
    adjusted_goal_plans = plan_all_goals(adjusted_goals) if adjusted_goals else []

    goal_impacts = []
    for baseline_plan in baseline_goal_plans:
        updated_plan = next(
            (plan for plan in adjusted_goal_plans if plan.goal.name == baseline_plan.goal.name),
            None,
        )
        if updated_plan is None:
            continue
        goal_impacts.append({
            "goal_name": baseline_plan.goal.name,
            "baseline_required_sip": round(baseline_plan.required_monthly_sip),
            "post_event_planned_sip": round(updated_plan.goal.monthly_sip),
            "baseline_on_track": baseline_plan.on_track,
            "post_event_on_track": updated_plan.on_track,
            "required_sip_delta": round(
                updated_plan.required_monthly_sip - baseline_plan.required_monthly_sip
            ),
        })

    baseline_life = calculate_life_insurance_need(profile)
    adjusted_life = calculate_life_insurance_need(adjusted_profile)
    explicit_insurance_delta = sum(max(event.insurance_need_change, 0.0) for event in events)
    baseline_health = calculate_health_insurance_need(profile)
    adjusted_health = calculate_health_insurance_need(adjusted_profile)

    portfolio_effects = {
        "loaded": portfolio is not None,
        "note": "No portfolio loaded for event-aware portfolio advice.",
    }
    if portfolio is not None:
        returns = compute_portfolio_returns(portfolio)
        benchmark = analyze_benchmark_comparison(portfolio, prefer_live=True)
        rebalance = generate_rebalance_plan(portfolio, age=adjusted_profile.age)

        deployment_note = "Keep long-term SIPs aligned to your target allocation."
        if scenario.deltas["emergency_fund_stress"] < 0 or adjusted_surplus < baseline_surplus:
            deployment_note = (
                "Route new money to liquid or short-duration debt until the emergency buffer is restored."
            )
        elif lump_sum_inflow > 0 and rebalance.actions:
            deployment_note = rebalance.actions[0].suggestion
        elif lump_sum_inflow > 0:
            deployment_note = (
                "Deploy the lump sum in stages using the current equity-debt-gold target mix."
            )

        portfolio_effects = {
            "loaded": True,
            "returns": returns,
            "benchmark": benchmark.to_dict(),
            "rebalance": rebalance.to_dict(),
            "recommended_deployment": deployment_note,
        }

    actions = []
    if adjusted_best_tax != baseline_best_tax:
        if adjusted_best_tax < baseline_best_tax:
            actions.append(
                f"Re-run tax planning after the event. Best-case annual tax changes by Rs {round(abs(adjusted_best_tax - baseline_best_tax)):,}."
            )
        else:
            actions.append(
                f"The event increases annual tax by about Rs {round(adjusted_best_tax - baseline_best_tax):,}. Adjust deductions or NPS accordingly."
            )
    if adjusted_surplus < baseline_surplus:
        actions.append(
            f"Reduce discretionary spending or temporary SIPs. Monthly surplus falls from Rs {round(baseline_surplus):,} to Rs {round(adjusted_surplus):,}."
        )
    if recommended_sip <= 0:
        actions.append("Pause wealth SIPs temporarily and rebuild liquidity before resuming aggressive investing.")
    elif goals and any(not item["post_event_on_track"] for item in goal_impacts):
        actions.append("Reallocate SIPs across goals immediately because at least one goal falls off track after the event.")
    if adjusted_life.gap + explicit_insurance_delta > baseline_life.gap:
        actions.append(
            f"Increase life cover by roughly Rs {round((adjusted_life.gap + explicit_insurance_delta) - baseline_life.gap):,} after this event."
        )
    if adjusted_health.gap > baseline_health.gap:
        actions.append("Upgrade health insurance or add a super top-up before absorbing the new household risk.")
    if portfolio is not None:
        actions.append(portfolio_effects["recommended_deployment"])

    return {
        "scenario": scenario.to_dict(),
        "cashflow": {
            "baseline_monthly_surplus": round(baseline_surplus),
            "post_event_monthly_surplus": round(adjusted_surplus),
            "recommended_monthly_sip_after_event": recommended_sip,
            "lump_sum_inflow": round(lump_sum_inflow),
        },
        "tax_impact": {
            "baseline_best_tax": round(baseline_best_tax),
            "post_event_best_tax": round(adjusted_best_tax),
            "annual_tax_delta": round(adjusted_best_tax - baseline_best_tax),
            "baseline_recommended_regime": baseline_tax.recommended_regime.value,
            "post_event_recommended_regime": adjusted_tax.recommended_regime.value,
        },
        "goal_impact": {
            "goal_count": len(goals),
            "recommended_goal_sip_split": {
                key: round(value) for key, value in adjusted_goal_alloc.items()
            },
            "goal_impacts": goal_impacts,
        },
        "insurance_impact": {
            "baseline_life_cover_gap": round(baseline_life.gap),
            "post_event_life_cover_gap": round(adjusted_life.gap + explicit_insurance_delta),
            "baseline_health_cover_gap": round(baseline_health.gap),
            "post_event_health_cover_gap": round(adjusted_health.gap),
        },
        "portfolio_effects": portfolio_effects,
        "recommended_actions": actions[:6],
    }
