"""XIRR & Portfolio Return Calculator.

Uses pyxirr for fast, accurate XIRR computation.
Also handles: absolute return, CAGR, and SIP return analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from src.models.portfolio import (
    Portfolio,
    FundHolding,
    Transaction,
    TransactionType,
    FundOverlap,
)


@dataclass
class ReturnMetrics:
    xirr: Optional[float]  # Annualized XIRR %
    absolute_return: float
    absolute_return_pct: float
    invested_amount: float
    current_value: float
    gain_loss: float

    def to_dict(self) -> dict:
        return {
            "xirr_pct": round(self.xirr * 100, 2) if self.xirr is not None else None,
            "absolute_return": round(self.absolute_return, 2),
            "absolute_return_pct": round(self.absolute_return_pct, 2),
            "invested_amount": round(self.invested_amount, 2),
            "current_value": round(self.current_value, 2),
            "gain_loss": round(self.gain_loss, 2),
        }


@dataclass
class OverlapAnalysis:
    overlaps: list[FundOverlap]
    high_overlap_pairs: list[tuple[str, str, float]]
    consolidation_suggestions: list[str]

    def to_dict(self) -> dict:
        return {
            "total_overlap_pairs": len(self.overlaps),
            "high_overlap_pairs": [
                {"fund_a": a, "fund_b": b, "overlap_pct": round(pct, 1)}
                for a, b, pct in self.high_overlap_pairs
            ],
            "consolidation_suggestions": self.consolidation_suggestions,
        }


@dataclass
class ExpenseAnalysis:
    total_expense_drag: float
    weighted_expense_ratio: float
    regular_plan_funds: list[str]
    potential_savings_if_direct: float
    fund_details: list[dict]

    def to_dict(self) -> dict:
        return {
            "total_annual_expense_drag": round(self.total_expense_drag),
            "weighted_expense_ratio_pct": round(self.weighted_expense_ratio, 2),
            "regular_plan_funds": self.regular_plan_funds,
            "potential_annual_savings_if_direct": round(self.potential_savings_if_direct),
            "fund_details": self.fund_details,
        }


def compute_xirr(
    transactions: list[Transaction],
    current_value: float,
    current_date: date | None = None,
) -> Optional[float]:
    """Compute XIRR for a list of transactions.

    Uses pyxirr library for Rust-based fast computation.
    Falls back to simple estimation if pyxirr not available.
    """
    if not transactions:
        return None

    if current_date is None:
        current_date = date.today()

    dates = []
    amounts = []

    for txn in transactions:
        if txn.is_inflow:
            dates.append(txn.date)
            amounts.append(-abs(txn.amount))  # Outflow (investment)
        else:
            dates.append(txn.date)
            amounts.append(abs(txn.amount))  # Inflow (redemption)

    # Add current value as final inflow
    dates.append(current_date)
    amounts.append(current_value)

    # Filter out zero amounts
    filtered = [(d, a) for d, a in zip(dates, amounts) if a != 0]
    if len(filtered) < 2:
        return None

    dates, amounts = zip(*filtered)

    try:
        import pyxirr
        result = pyxirr.xirr(list(dates), list(amounts))
        if result is not None and not (isinstance(result, float) and (result != result)):  # NaN check
            return result
        return None
    except ImportError:
        # Fallback: simple CAGR estimation
        return _simple_cagr(list(amounts), list(dates))
    except Exception:
        return None


def _simple_cagr(amounts: list[float], dates: list[date]) -> Optional[float]:
    """Simple CAGR fallback when pyxirr is not available."""
    total_invested = sum(-a for a in amounts if a < 0)
    total_received = sum(a for a in amounts if a > 0)

    if total_invested <= 0 or not dates:
        return None

    first_date = min(dates)
    last_date = max(dates)
    years = (last_date - first_date).days / 365.25

    if years <= 0:
        return None

    return (total_received / total_invested) ** (1 / years) - 1


def compute_holding_returns(holding: FundHolding) -> ReturnMetrics:
    """Compute return metrics for a single fund holding."""
    xirr = compute_xirr(
        holding.transactions,
        holding.current_value,
    )

    return ReturnMetrics(
        xirr=xirr,
        absolute_return=holding.absolute_return,
        absolute_return_pct=holding.absolute_return_pct,
        invested_amount=holding.invested_amount,
        current_value=holding.current_value,
        gain_loss=holding.absolute_return,
    )


def compute_portfolio_returns(portfolio: Portfolio) -> dict:
    """Compute returns for entire portfolio."""
    all_transactions = []
    total_current_value = 0.0

    holding_returns = []
    for holding in portfolio.holdings:
        metrics = compute_holding_returns(holding)
        holding.xirr = metrics.xirr
        holding_returns.append({
            "scheme": holding.scheme_name,
            "invested": round(holding.invested_amount),
            "current_value": round(holding.current_value),
            "gain_loss": round(holding.absolute_return),
            "absolute_return_pct": round(holding.absolute_return_pct, 1),
            "xirr_pct": round(metrics.xirr * 100, 2) if metrics.xirr else None,
        })
        all_transactions.extend(holding.transactions)
        total_current_value += holding.current_value

    overall_xirr = compute_xirr(all_transactions, total_current_value)
    portfolio.overall_xirr = overall_xirr

    return {
        "overall_xirr_pct": round(overall_xirr * 100, 2) if overall_xirr else None,
        "total_invested": round(portfolio.total_invested),
        "total_current_value": round(total_current_value),
        "total_gain": round(portfolio.total_gain),
        "total_return_pct": round(
            (portfolio.total_gain / portfolio.total_invested * 100)
            if portfolio.total_invested > 0 else 0, 1
        ),
        "holdings": holding_returns,
    }


def analyze_fund_overlap(
    portfolio: Portfolio,
    top_holdings_data: dict[str, list[str]] | None = None,
) -> OverlapAnalysis:
    """Analyze overlap between funds in the portfolio.

    Args:
        portfolio: The portfolio to analyze.
        top_holdings_data: Dict mapping scheme name to list of top stock holdings.
            If not provided, uses category-based heuristic overlap.
    """
    overlaps = []
    high_overlap_pairs = []
    suggestions = []

    holdings = portfolio.holdings
    if len(holdings) < 2:
        return OverlapAnalysis([], [], ["Only 1 fund - no overlap to analyze"])

    if top_holdings_data:
        # Actual stock-level overlap using Jaccard similarity
        for i in range(len(holdings)):
            for j in range(i + 1, len(holdings)):
                stocks_a = set(top_holdings_data.get(holdings[i].scheme_name, []))
                stocks_b = set(top_holdings_data.get(holdings[j].scheme_name, []))
                if not stocks_a or not stocks_b:
                    continue
                intersection = stocks_a & stocks_b
                union = stocks_a | stocks_b
                jaccard = (len(intersection) / len(union) * 100) if union else 0

                overlap = FundOverlap(
                    fund_a=holdings[i].scheme_name,
                    fund_b=holdings[j].scheme_name,
                    common_stocks=list(intersection),
                    overlap_pct=jaccard,
                )
                overlaps.append(overlap)
                if jaccard >= 40:
                    high_overlap_pairs.append((
                        holdings[i].scheme_name,
                        holdings[j].scheme_name,
                        jaccard,
                    ))
    else:
        # Category-based heuristic overlap
        for i in range(len(holdings)):
            for j in range(i + 1, len(holdings)):
                if holdings[i].category == holdings[j].category:
                    heuristic_overlap = 50.0  # Same category = ~50% overlap
                    overlap = FundOverlap(
                        fund_a=holdings[i].scheme_name,
                        fund_b=holdings[j].scheme_name,
                        overlap_pct=heuristic_overlap,
                    )
                    overlaps.append(overlap)
                    high_overlap_pairs.append((
                        holdings[i].scheme_name,
                        holdings[j].scheme_name,
                        heuristic_overlap,
                    ))

    if high_overlap_pairs:
        suggestions.append(
            f"Found {len(high_overlap_pairs)} fund pairs with >40% overlap - consider consolidating"
        )
        for a, b, pct in high_overlap_pairs[:3]:
            suggestions.append(f"'{a}' and '{b}' overlap {pct:.0f}% - keep only one")

    portfolio.overlaps = overlaps
    return OverlapAnalysis(overlaps, high_overlap_pairs, suggestions)


def analyze_expense_ratios(portfolio: Portfolio) -> ExpenseAnalysis:
    """Analyze expense ratio drag and direct plan savings potential."""
    total_drag = portfolio.total_expense_drag()
    total_value = portfolio.total_current_value

    weighted_er = (total_drag / total_value * 100) if total_value > 0 else 0

    regular_funds = [
        h.scheme_name for h in portfolio.holdings
        if h.plan_type.value == "regular"
    ]

    # Estimate savings if switched to direct (assume 0.5% lower ER for direct)
    direct_savings = sum(
        h.current_value * 0.005  # 0.5% saving
        for h in portfolio.holdings
        if h.plan_type.value == "regular"
    )

    fund_details = []
    for h in portfolio.holdings:
        fund_details.append({
            "scheme": h.scheme_name,
            "value": round(h.current_value),
            "expense_ratio_pct": h.expense_ratio,
            "annual_expense": round(h.current_value * h.expense_ratio / 100),
            "plan_type": h.plan_type.value,
        })

    return ExpenseAnalysis(
        total_expense_drag=total_drag,
        weighted_expense_ratio=weighted_er,
        regular_plan_funds=regular_funds,
        potential_savings_if_direct=direct_savings,
        fund_details=fund_details,
    )
