"""Portfolio Rebalancing Engine.

Compares current allocation to a target model portfolio and generates
specific buy/sell/switch actions to rebalance.

Model portfolios based on risk profile and age:
- Aggressive (age < 35): 80% equity, 15% debt, 5% gold
- Moderate (age 35-50): 60% equity, 30% debt, 10% gold
- Conservative (age > 50): 40% equity, 45% debt, 15% gold
"""

from __future__ import annotations

from dataclasses import dataclass

from src.models.portfolio import Portfolio, FundCategory


# Broad asset classes
EQUITY_CATEGORIES = {
    FundCategory.LARGE_CAP, FundCategory.MID_CAP, FundCategory.SMALL_CAP,
    FundCategory.MULTI_CAP, FundCategory.FLEXI_CAP, FundCategory.ELSS,
    FundCategory.SECTORAL, FundCategory.THEMATIC, FundCategory.INDEX,
    FundCategory.INTERNATIONAL,
}

DEBT_CATEGORIES = {
    FundCategory.DEBT_SHORT, FundCategory.DEBT_MEDIUM, FundCategory.DEBT_LONG,
    FundCategory.LIQUID,
}

HYBRID_CATEGORIES = {
    FundCategory.HYBRID_AGGRESSIVE, FundCategory.HYBRID_CONSERVATIVE,
}

GOLD_CATEGORIES = {
    FundCategory.GOLD,
}


# Model portfolios
MODEL_PORTFOLIOS = {
    "aggressive": {
        "equity": 0.80,
        "debt": 0.15,
        "gold": 0.05,
        "ideal_equity_split": {
            "large_cap": 0.40,
            "mid_cap": 0.25,
            "small_cap": 0.15,
            "international": 0.10,
            "elss": 0.10,
        },
        "description": "High growth, suitable for age < 35 with 10+ year horizon",
    },
    "moderate": {
        "equity": 0.60,
        "debt": 0.30,
        "gold": 0.10,
        "ideal_equity_split": {
            "large_cap": 0.45,
            "mid_cap": 0.25,
            "small_cap": 0.10,
            "international": 0.10,
            "elss": 0.10,
        },
        "description": "Balanced growth, suitable for age 35-50 with 5-10 year horizon",
    },
    "conservative": {
        "equity": 0.40,
        "debt": 0.45,
        "gold": 0.15,
        "ideal_equity_split": {
            "large_cap": 0.55,
            "mid_cap": 0.20,
            "small_cap": 0.05,
            "international": 0.10,
            "elss": 0.10,
        },
        "description": "Capital preservation, suitable for age 50+ or short horizon",
    },
}


@dataclass
class AssetAllocation:
    equity_pct: float
    debt_pct: float
    hybrid_pct: float
    gold_pct: float
    other_pct: float
    equity_value: float
    debt_value: float
    hybrid_value: float
    gold_value: float
    total_value: float

    def to_dict(self) -> dict:
        return {
            "equity_pct": round(self.equity_pct, 1),
            "debt_pct": round(self.debt_pct, 1),
            "hybrid_pct": round(self.hybrid_pct, 1),
            "gold_pct": round(self.gold_pct, 1),
            "other_pct": round(self.other_pct, 1),
            "equity_value": round(self.equity_value),
            "debt_value": round(self.debt_value),
            "total_value": round(self.total_value),
        }


@dataclass
class RebalanceAction:
    action: str  # "increase", "decrease", "hold"
    asset_class: str
    current_pct: float
    target_pct: float
    delta_pct: float
    delta_amount: float
    suggestion: str

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "asset_class": self.asset_class,
            "current_pct": round(self.current_pct, 1),
            "target_pct": round(self.target_pct, 1),
            "delta_pct": round(self.delta_pct, 1),
            "delta_amount": round(self.delta_amount),
            "suggestion": self.suggestion,
        }


@dataclass
class RebalanceReport:
    risk_profile: str
    current_allocation: AssetAllocation
    target_allocation: dict
    actions: list[RebalanceAction]
    rebalance_needed: bool
    max_drift: float  # Largest deviation from target

    def to_dict(self) -> dict:
        return {
            "risk_profile": self.risk_profile,
            "model_description": MODEL_PORTFOLIOS.get(self.risk_profile, {}).get("description", ""),
            "current_allocation": self.current_allocation.to_dict(),
            "target_allocation": self.target_allocation,
            "actions": [a.to_dict() for a in self.actions],
            "rebalance_needed": self.rebalance_needed,
            "max_drift_pct": round(self.max_drift, 1),
        }


def get_current_allocation(portfolio: Portfolio) -> AssetAllocation:
    """Calculate current asset allocation from portfolio."""
    equity_val = sum(
        h.current_value for h in portfolio.holdings
        if h.category in EQUITY_CATEGORIES
    )
    debt_val = sum(
        h.current_value for h in portfolio.holdings
        if h.category in DEBT_CATEGORIES
    )
    hybrid_val = sum(
        h.current_value for h in portfolio.holdings
        if h.category in HYBRID_CATEGORIES
    )
    gold_val = sum(
        h.current_value for h in portfolio.holdings
        if h.category in GOLD_CATEGORIES
    )
    total = portfolio.total_current_value

    # Split hybrid: aggressive hybrid = 65% equity + 35% debt
    equity_from_hybrid = hybrid_val * 0.65
    debt_from_hybrid = hybrid_val * 0.35

    effective_equity = equity_val + equity_from_hybrid
    effective_debt = debt_val + debt_from_hybrid

    other = total - equity_val - debt_val - hybrid_val - gold_val

    return AssetAllocation(
        equity_pct=(effective_equity / total * 100) if total > 0 else 0,
        debt_pct=(effective_debt / total * 100) if total > 0 else 0,
        hybrid_pct=(hybrid_val / total * 100) if total > 0 else 0,
        gold_pct=(gold_val / total * 100) if total > 0 else 0,
        other_pct=(other / total * 100) if total > 0 else 0,
        equity_value=effective_equity,
        debt_value=effective_debt,
        hybrid_value=hybrid_val,
        gold_value=gold_val,
        total_value=total,
    )


def suggest_risk_profile(age: int) -> str:
    """Suggest risk profile based on age."""
    if age < 35:
        return "aggressive"
    elif age <= 50:
        return "moderate"
    else:
        return "conservative"


def generate_rebalance_plan(
    portfolio: Portfolio,
    risk_profile: str | None = None,
    age: int = 30,
    drift_threshold: float = 5.0,
) -> RebalanceReport:
    """Generate a rebalance plan comparing current vs target allocation.

    Args:
        portfolio: Current portfolio
        risk_profile: "aggressive", "moderate", or "conservative"
        age: User's age (used if risk_profile not specified)
        drift_threshold: Minimum % drift to trigger rebalance action
    """
    if risk_profile is None:
        risk_profile = suggest_risk_profile(age)

    model = MODEL_PORTFOLIOS.get(risk_profile, MODEL_PORTFOLIOS["moderate"])
    current = get_current_allocation(portfolio)
    total = current.total_value

    target_equity = model["equity"] * 100
    target_debt = model["debt"] * 100
    target_gold = model["gold"] * 100

    actions = []
    max_drift = 0.0

    # Equity
    eq_delta = current.equity_pct - target_equity
    max_drift = max(max_drift, abs(eq_delta))
    if abs(eq_delta) >= drift_threshold:
        amount = abs(eq_delta) / 100 * total
        if eq_delta > 0:
            actions.append(RebalanceAction(
                action="decrease",
                asset_class="Equity",
                current_pct=current.equity_pct,
                target_pct=target_equity,
                delta_pct=eq_delta,
                delta_amount=amount,
                suggestion=f"Reduce equity by Rs {amount:,.0f} - shift to debt/gold funds",
            ))
        else:
            actions.append(RebalanceAction(
                action="increase",
                asset_class="Equity",
                current_pct=current.equity_pct,
                target_pct=target_equity,
                delta_pct=eq_delta,
                delta_amount=amount,
                suggestion=f"Increase equity by Rs {amount:,.0f} - add large cap or index fund SIPs",
            ))

    # Debt
    debt_delta = current.debt_pct - target_debt
    max_drift = max(max_drift, abs(debt_delta))
    if abs(debt_delta) >= drift_threshold:
        amount = abs(debt_delta) / 100 * total
        if debt_delta > 0:
            actions.append(RebalanceAction(
                action="decrease",
                asset_class="Debt",
                current_pct=current.debt_pct,
                target_pct=target_debt,
                delta_pct=debt_delta,
                delta_amount=amount,
                suggestion=f"Reduce debt allocation by Rs {amount:,.0f} - shift to equity",
            ))
        else:
            actions.append(RebalanceAction(
                action="increase",
                asset_class="Debt",
                current_pct=current.debt_pct,
                target_pct=target_debt,
                delta_pct=debt_delta,
                delta_amount=amount,
                suggestion=f"Add Rs {amount:,.0f} to debt funds for stability",
            ))

    # Gold
    gold_delta = current.gold_pct - target_gold
    max_drift = max(max_drift, abs(gold_delta))
    if abs(gold_delta) >= drift_threshold:
        amount = abs(gold_delta) / 100 * total
        if gold_delta < 0:
            actions.append(RebalanceAction(
                action="increase",
                asset_class="Gold",
                current_pct=current.gold_pct,
                target_pct=target_gold,
                delta_pct=gold_delta,
                delta_amount=amount,
                suggestion=f"Add Rs {amount:,.0f} to gold (Sovereign Gold Bond or Gold ETF)",
            ))

    rebalance_needed = max_drift >= drift_threshold

    return RebalanceReport(
        risk_profile=risk_profile,
        current_allocation=current,
        target_allocation={
            "equity_pct": target_equity,
            "debt_pct": target_debt,
            "gold_pct": target_gold,
        },
        actions=actions,
        rebalance_needed=rebalance_needed,
        max_drift=max_drift,
    )
