"""Unified FIRE Path Planner.

Builds a single end-to-end plan combining:
- goal SIP planning
- FIRE timeline
- emergency fund roadmap
- insurance gaps
- tax actions
- asset allocation glide path
- month-by-month execution roadmap
"""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import date
from typing import Optional

from src.engines.goal_calculator import (
    GoalPlan,
    allocate_sip_across_goals,
    calculate_fire,
    plan_all_goals,
)
from src.engines.health_scorer import compute_money_health_score
from src.engines.insurance_calculator import (
    calculate_health_insurance_need,
    calculate_life_insurance_need,
)
from src.engines.tax_calculator import compare_regimes, recommend_tax_saving_options
from src.models.goals import FinancialGoal, GoalType
from src.models.user import IndividualProfile


def _best_tax_monthly_in_hand(profile: IndividualProfile) -> float:
    comparison = compare_regimes(profile)
    if comparison.recommended_regime.value == "old":
        return comparison.old_regime.monthly_in_hand
    return comparison.new_regime.monthly_in_hand


def _current_monthly_surplus(profile: IndividualProfile) -> float:
    monthly_in_hand = _best_tax_monthly_in_hand(profile)
    return max(
        monthly_in_hand
        - profile.monthly_expenses.total
        - profile.debt.total_monthly_emi,
        0.0,
    )


def _glide_path(years_left: float) -> dict[str, float]:
    if years_left >= 15:
        return {"equity_pct": 80.0, "debt_pct": 15.0, "gold_pct": 5.0}
    if years_left >= 8:
        return {"equity_pct": 70.0, "debt_pct": 20.0, "gold_pct": 10.0}
    if years_left >= 4:
        return {"equity_pct": 55.0, "debt_pct": 35.0, "gold_pct": 10.0}
    return {"equity_pct": 35.0, "debt_pct": 55.0, "gold_pct": 10.0}


def _goal_groups(goals: list[FinancialGoal]) -> tuple[list[FinancialGoal], list[FinancialGoal]]:
    fire_like = {
        GoalType.RETIREMENT,
        GoalType.FIRE,
        GoalType.WEALTH_CREATION,
    }
    fire_goals = [goal for goal in goals if goal.goal_type in fire_like]
    non_fire_goals = [goal for goal in goals if goal.goal_type not in fire_like]
    return non_fire_goals, fire_goals


def _scale_profile_for_year(
    profile: IndividualProfile,
    year_index: int,
    annual_income_growth: float,
    annual_expense_inflation: float,
) -> IndividualProfile:
    scaled = copy.deepcopy(profile)

    income_multiplier = (1 + annual_income_growth) ** year_index
    expense_multiplier = (1 + annual_expense_inflation) ** year_index

    scaled.salary.basic *= income_multiplier
    scaled.salary.da *= income_multiplier
    scaled.salary.hra *= income_multiplier
    scaled.salary.special_allowance *= income_multiplier
    scaled.salary.lta *= income_multiplier
    scaled.salary.medical_allowance *= income_multiplier
    scaled.salary.other_allowance *= income_multiplier
    scaled.salary.bonus *= income_multiplier
    scaled.salary.employer_pf *= income_multiplier
    scaled.salary.employer_nps *= income_multiplier
    scaled.salary.professional_tax *= income_multiplier
    scaled.other_income *= income_multiplier

    scaled.monthly_expenses.rent *= expense_multiplier
    scaled.monthly_expenses.groceries *= expense_multiplier
    scaled.monthly_expenses.utilities *= expense_multiplier
    scaled.monthly_expenses.transportation *= expense_multiplier
    scaled.monthly_expenses.dining_out *= expense_multiplier
    scaled.monthly_expenses.entertainment *= expense_multiplier
    scaled.monthly_expenses.shopping *= expense_multiplier
    scaled.monthly_expenses.education *= expense_multiplier
    scaled.monthly_expenses.medical *= expense_multiplier
    scaled.monthly_expenses.misc *= expense_multiplier

    return scaled


def _goal_status_summary(goal_plans: list[GoalPlan]) -> dict:
    total_required = sum(plan.required_monthly_sip for plan in goal_plans)
    on_track = sum(1 for plan in goal_plans if plan.on_track)
    return {
        "goal_count": len(goal_plans),
        "goals_on_track": on_track,
        "goals_off_track": max(len(goal_plans) - on_track, 0),
        "required_goal_sip": round(total_required),
    }


def build_fire_master_plan(
    profile: IndividualProfile,
    goals: Optional[list[FinancialGoal]] = None,
    portfolio=None,
    *,
    expected_return: float = 0.10,
    inflation_rate: float = 0.06,
    safe_withdrawal_rate: float = 0.04,
    annual_income_growth: float = 0.08,
    annual_expense_inflation: float = 0.06,
    horizon_months: Optional[int] = None,
) -> dict:
    """Build a unified FIRE plan with a month-by-month roadmap."""
    goals = goals or []

    health_report = compute_money_health_score(profile, portfolio)
    tax_comparison = compare_regimes(profile)
    tax_actions = recommend_tax_saving_options(
        profile,
        risk_profile="moderate",
        liquidity_need="medium",
    )
    life_need = calculate_life_insurance_need(profile)
    health_need = calculate_health_insurance_need(profile)

    all_goal_plans = plan_all_goals(goals) if goals else []
    non_fire_goals, fire_goals = _goal_groups(goals)
    non_fire_goal_plans = plan_all_goals(non_fire_goals) if non_fire_goals else []
    fire_goal_plans = plan_all_goals(fire_goals) if fire_goals else []

    current_surplus = _current_monthly_surplus(profile)
    planned_monthly_investment = max(current_surplus, profile.monthly_sip)

    monthly_need = profile.monthly_expenses.total + profile.debt.total_monthly_emi
    emergency_target = monthly_need * 6
    emergency_gap = max(emergency_target - profile.emergency_fund, 0.0)
    emergency_monthly = 0.0
    if planned_monthly_investment > 0 and emergency_gap > 0:
        emergency_monthly = min(
            emergency_gap,
            max(emergency_gap / 12, planned_monthly_investment * 0.25),
        )

    investable_after_emergency = max(planned_monthly_investment - emergency_monthly, 0.0)
    non_fire_goal_alloc = (
        allocate_sip_across_goals(non_fire_goals, investable_after_emergency)
        if non_fire_goals else {}
    )
    total_non_fire_goal_sip = sum(non_fire_goal_alloc.values())
    fire_bucket_sip = max(investable_after_emergency - total_non_fire_goal_sip, 0.0)

    fire_current_corpus = (
        profile.current_investments
        + profile.epf_balance
        + profile.ppf_balance
        + profile.nps_balance
    )
    fire_result = calculate_fire(
        current_age=profile.age,
        annual_expenses=profile.monthly_expenses.total * 12,
        current_corpus=fire_current_corpus,
        monthly_investment=fire_bucket_sip,
        expected_return=expected_return,
        inflation_rate=inflation_rate,
        safe_withdrawal_rate=safe_withdrawal_rate,
    )

    max_goal_years = max((goal.years_remaining for goal in goals), default=0)
    derived_horizon = max(
        int(fire_result.years_to_fire),
        max_goal_years,
        2,
    ) * 12
    months = min(max(horizon_months or derived_horizon, 24), 360)

    roadmap = []
    monthly_emergency_balance = profile.emergency_fund
    monthly_fire_corpus = fire_current_corpus
    current_date = date.today()
    goal_balances = {goal.name: goal.current_corpus for goal in non_fire_goals}
    previous_emergency_gap = emergency_gap

    for month_idx in range(months):
        year_index = month_idx // 12
        scaled_profile = _scale_profile_for_year(
            profile,
            year_index,
            annual_income_growth,
            annual_expense_inflation,
        )
        scaled_monthly_surplus = max(_current_monthly_surplus(scaled_profile), 0.0)

        scaled_monthly_need = (
            scaled_profile.monthly_expenses.total
            + scaled_profile.debt.total_monthly_emi
        )
        scaled_emergency_target = scaled_monthly_need * 6
        emergency_gap_now = max(scaled_emergency_target - monthly_emergency_balance, 0.0)
        emergency_contribution = 0.0
        if scaled_monthly_surplus > 0 and emergency_gap_now > 0:
            emergency_contribution = min(
                emergency_gap_now,
                max(emergency_gap_now / 12, scaled_monthly_surplus * 0.25),
            )
        monthly_emergency_balance += emergency_contribution

        investable_now = max(scaled_monthly_surplus - emergency_contribution, 0.0)
        goal_contribs = (
            allocate_sip_across_goals(non_fire_goals, investable_now)
            if non_fire_goals else {}
        )
        goal_contribution = sum(goal_contribs.values())
        fire_contribution = max(investable_now - goal_contribution, 0.0)

        monthly_fire_corpus = (
            monthly_fire_corpus * (1 + expected_return / 12)
            + fire_contribution
        )

        for goal in non_fire_goals:
            if goal.years_remaining <= 0:
                continue
            monthly_rate = goal.expected_return / 100 / 12
            balance = goal_balances.get(goal.name, goal.current_corpus)
            goal_balances[goal.name] = balance * (1 + monthly_rate) + goal_contribs.get(goal.name, 0.0)

        years_left = max((months - month_idx) / 12, 0.0)
        asset_mix = _glide_path(min(years_left, fire_result.years_to_fire))

        actions = []
        if month_idx == 0 and emergency_gap > 0:
            actions.append(
                f"Direct Rs {round(emergency_contribution):,}/month to emergency fund first."
            )
        if month_idx == 0 and life_need.gap > 0:
            actions.append(
                f"Add life cover gap of Rs {round(life_need.gap):,} with term insurance."
            )
        if month_idx == 0 and health_need.gap > 0:
            actions.append(
                f"Upgrade health cover by Rs {round(health_need.gap):,}, ideally via a super top-up."
            )
        if month_idx == 0 and tax_actions:
            top_tax = tax_actions[0]
            actions.append(
                f"Use {top_tax['name']} for tax saving, starting with Rs {top_tax['suggested_amount']:,} of room."
            )
        if previous_emergency_gap > 0 and emergency_gap_now <= 0:
            actions.append("Emergency fund target reached. Redirect the freed cash flow to long-term investing.")
        previous_emergency_gap = emergency_gap_now

        month_number = ((current_date.month - 1 + month_idx) % 12) + 1
        year_number = current_date.year + ((current_date.month - 1 + month_idx) // 12)
        roadmap.append({
            "month_index": month_idx + 1,
            "month_label": f"{year_number}-{month_number:02d}",
            "monthly_surplus": round(scaled_monthly_surplus),
            "emergency_contribution": round(emergency_contribution),
            "goal_contribution": round(goal_contribution),
            "fire_contribution": round(fire_contribution),
            "emergency_fund_balance": round(monthly_emergency_balance),
            "projected_fire_corpus": round(monthly_fire_corpus),
            "target_asset_mix": asset_mix,
            "actions": actions,
        })

    primary_actions = []
    if emergency_gap > 0:
        primary_actions.append(
            f"Build emergency fund from Rs {round(profile.emergency_fund):,} to Rs {round(emergency_target):,}."
        )
    if life_need.gap > 0:
        primary_actions.append(
            f"Close the life cover gap of Rs {round(life_need.gap):,}."
        )
    if health_need.gap > 0:
        primary_actions.append(
            f"Increase health insurance by Rs {round(health_need.gap):,}."
        )
    if total_non_fire_goal_sip < sum(plan.required_monthly_sip for plan in non_fire_goal_plans):
        primary_actions.append(
            "Current surplus does not fully fund all near-term goals. Increase income or cut expenses before stepping up FIRE investing."
        )
    if fire_bucket_sip <= 0:
        primary_actions.append(
            "No dedicated monthly FIRE surplus is available yet. Finish the emergency fund and goal gaps first."
        )
    elif fire_result.years_to_fire > profile.years_to_retirement:
        primary_actions.append(
            "Current FIRE contribution is too low for early retirement. Increase the monthly FIRE bucket or defer the target age."
        )

    return {
        "summary": {
            "current_monthly_surplus": round(current_surplus),
            "planned_monthly_investment": round(planned_monthly_investment),
            "goal_sip_budget": round(total_non_fire_goal_sip),
            "fire_bucket_sip": round(fire_bucket_sip),
            "emergency_fund_target": round(emergency_target),
            "emergency_fund_gap": round(emergency_gap),
            "projected_fire_age": fire_result.projected_fire_age,
            "years_to_fire": round(fire_result.years_to_fire, 1),
            "fire_number": round(fire_result.fire_number),
            "annual_passive_income_at_fire": round(fire_result.annual_passive_income),
            "life_cover_gap": round(life_need.gap),
            "health_cover_gap": round(health_need.gap),
            "health_score": round(health_report.overall_score, 1),
        },
        "fire": fire_result.to_dict(),
        "health_score": health_report.to_dict(),
        "tax_strategy": {
            "comparison": tax_comparison.to_dict(),
            "recommended_actions": tax_actions[:5],
        },
        "insurance_strategy": {
            "life": life_need.to_dict(),
            "health": health_need.to_dict(),
        },
        "goal_summary": _goal_status_summary(all_goal_plans),
        "goal_plans": [plan.to_dict() for plan in all_goal_plans],
        "goal_sip_allocation": {name: round(amount) for name, amount in non_fire_goal_alloc.items()},
        "fire_goal_plans": [plan.to_dict() for plan in fire_goal_plans],
        "primary_actions": primary_actions[:5],
        "roadmap": roadmap,
        "roadmap_months": months,
    }
