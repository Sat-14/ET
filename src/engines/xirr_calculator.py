"""XIRR & Portfolio Return Calculator.

Uses pyxirr for fast, accurate XIRR computation.
Also handles: absolute return, CAGR, and SIP return analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import httpx

from src.models.portfolio import (
    Portfolio,
    FundHolding,
    Transaction,
    FundOverlap,
    FundCategory,
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


@dataclass
class BenchmarkComparison:
    portfolio_xirr_pct: Optional[float]
    weighted_benchmark_return_pct: float
    alpha_pct: Optional[float]
    fund_details: list[dict]
    note: str
    data_source: str = "model_benchmark"
    as_of_date: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "portfolio_xirr_pct": round(self.portfolio_xirr_pct, 2)
            if self.portfolio_xirr_pct is not None else None,
            "weighted_benchmark_return_pct": round(self.weighted_benchmark_return_pct, 2),
            "alpha_pct": round(self.alpha_pct, 2) if self.alpha_pct is not None else None,
            "fund_details": self.fund_details,
            "note": self.note,
            "data_source": self.data_source,
            "as_of_date": self.as_of_date,
        }


CATEGORY_BENCHMARKS: dict[FundCategory, tuple[str, float]] = {
    FundCategory.LARGE_CAP: ("Nifty 50 TRI", 12.0),
    FundCategory.MID_CAP: ("Nifty Midcap 150 TRI", 14.0),
    FundCategory.SMALL_CAP: ("Nifty Smallcap 250 TRI", 16.0),
    FundCategory.MULTI_CAP: ("Nifty 500 TRI", 12.5),
    FundCategory.FLEXI_CAP: ("Nifty 500 TRI", 12.5),
    FundCategory.ELSS: ("Nifty 500 TRI", 12.5),
    FundCategory.SECTORAL: ("Sectoral Equity Benchmark", 14.0),
    FundCategory.THEMATIC: ("Thematic Equity Benchmark", 14.0),
    FundCategory.INDEX: ("Nifty 50 TRI", 11.5),
    FundCategory.DEBT_SHORT: ("Short Duration Debt Index", 7.0),
    FundCategory.DEBT_MEDIUM: ("Corporate Bond Index", 7.5),
    FundCategory.DEBT_LONG: ("Gilt / Long Bond Index", 8.0),
    FundCategory.LIQUID: ("Liquid Fund Benchmark", 6.0),
    FundCategory.HYBRID_AGGRESSIVE: ("65/35 Equity-Debt Blend", 10.5),
    FundCategory.HYBRID_CONSERVATIVE: ("25/75 Equity-Debt Blend", 8.0),
    FundCategory.INTERNATIONAL: ("Global Equity Benchmark", 10.0),
    FundCategory.GOLD: ("Domestic Gold Benchmark", 8.0),
    FundCategory.OTHER: ("Broad Market Benchmark", 10.0),
}

LIVE_BENCHMARK_PROXIES: dict[FundCategory, list[tuple[str, str, float]]] = {
    FundCategory.LARGE_CAP: [("Nifty 50 ETF", "NIFTYBEES.NS", 1.0)],
    FundCategory.INDEX: [("Nifty 50 ETF", "NIFTYBEES.NS", 1.0)],
    FundCategory.FLEXI_CAP: [
        ("Nifty 50 ETF", "NIFTYBEES.NS", 0.70),
        ("Nifty Midcap 150 ETF", "MID150BEES.NS", 0.30),
    ],
    FundCategory.MULTI_CAP: [
        ("Nifty 50 ETF", "NIFTYBEES.NS", 0.65),
        ("Nifty Midcap 150 ETF", "MID150BEES.NS", 0.35),
    ],
    FundCategory.ELSS: [
        ("Nifty 50 ETF", "NIFTYBEES.NS", 0.70),
        ("Nifty Midcap 150 ETF", "MID150BEES.NS", 0.30),
    ],
    FundCategory.MID_CAP: [("Nifty Midcap 150 ETF", "MID150BEES.NS", 1.0)],
    FundCategory.SMALL_CAP: [
        ("Nifty Midcap 150 ETF", "MID150BEES.NS", 0.70),
        ("Nifty 50 ETF", "NIFTYBEES.NS", 0.30),
    ],
    FundCategory.DEBT_SHORT: [("Liquid ETF", "LIQUIDBEES.NS", 1.0)],
    FundCategory.DEBT_MEDIUM: [("Liquid ETF", "LIQUIDBEES.NS", 1.0)],
    FundCategory.DEBT_LONG: [("Liquid ETF", "LIQUIDBEES.NS", 1.0)],
    FundCategory.LIQUID: [("Liquid ETF", "LIQUIDBEES.NS", 1.0)],
    FundCategory.HYBRID_AGGRESSIVE: [
        ("Nifty 50 ETF", "NIFTYBEES.NS", 0.65),
        ("Liquid ETF", "LIQUIDBEES.NS", 0.35),
    ],
    FundCategory.HYBRID_CONSERVATIVE: [
        ("Nifty 50 ETF", "NIFTYBEES.NS", 0.25),
        ("Liquid ETF", "LIQUIDBEES.NS", 0.75),
    ],
    FundCategory.GOLD: [("Gold ETF", "GOLDBEES.NS", 1.0)],
    FundCategory.INTERNATIONAL: [("Motilal Nasdaq 100 ETF", "MON100.NS", 1.0)],
}

_BENCHMARK_RETURN_CACHE: dict[tuple[str, str, str], Optional[float]] = {}


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


def _fetch_live_benchmark_return(
    ticker: str,
    start_date: date,
    end_date: Optional[date] = None,
) -> Optional[float]:
    end_date = end_date or date.today()
    cache_key = (ticker, start_date.isoformat(), end_date.isoformat())
    if cache_key in _BENCHMARK_RETURN_CACHE:
        return _BENCHMARK_RETURN_CACHE[cache_key]

    period1 = int(datetime.combine(start_date - timedelta(days=5), datetime.min.time()).timestamp())
    period2 = int(datetime.combine(end_date + timedelta(days=1), datetime.min.time()).timestamp())

    try:
        with httpx.Client(
            timeout=1.5,
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
        ) as client:
            response = client.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                params={
                    "period1": period1,
                    "period2": period2,
                    "interval": "1d",
                    "includeAdjustedClose": "true",
                },
            )
            response.raise_for_status()
            payload = response.json()

        result = payload.get("chart", {}).get("result", [])
        if not result:
            _BENCHMARK_RETURN_CACHE[cache_key] = None
            return None

        result0 = result[0]
        timestamps = result0.get("timestamp", [])
        indicators = result0.get("indicators", {})
        adj_close = (
            indicators.get("adjclose", [{}])[0].get("adjclose", [])
            if indicators.get("adjclose") else []
        )
        close_prices = adj_close or indicators.get("quote", [{}])[0].get("close", [])

        points = []
        for ts, price in zip(timestamps, close_prices):
            if price in (None, 0):
                continue
            points.append((datetime.utcfromtimestamp(ts).date(), float(price)))

        if len(points) < 2:
            _BENCHMARK_RETURN_CACHE[cache_key] = None
            return None

        first_date, first_price = points[0]
        last_date, last_price = points[-1]
        days = max((last_date - first_date).days, 1)
        result_value = (last_price / first_price) ** (365.25 / days) - 1
        _BENCHMARK_RETURN_CACHE[cache_key] = result_value
        return result_value
    except Exception:
        _BENCHMARK_RETURN_CACHE[cache_key] = None
        return None


def _live_proxy_return_for_holding(holding: FundHolding) -> Optional[dict]:
    proxies = LIVE_BENCHMARK_PROXIES.get(holding.category)
    if not proxies:
        return None

    start_date = min((txn.date for txn in holding.transactions), default=date.today() - timedelta(days=365))
    weighted_return = 0.0
    used_weight = 0.0
    names = []

    for proxy_name, ticker, weight in proxies:
        live_return = _fetch_live_benchmark_return(ticker, start_date)
        if live_return is None:
            continue
        weighted_return += live_return * weight
        used_weight += weight
        names.append(proxy_name)

    if used_weight <= 0:
        return None

    return {
        "benchmark_name": " / ".join(names),
        "benchmark_return_pct": (weighted_return / used_weight) * 100,
    }


def _analyze_model_benchmark_comparison(portfolio: Portfolio) -> BenchmarkComparison:
    """Compare portfolio return to a category-weighted model benchmark."""
    total_value = portfolio.total_current_value
    if total_value <= 0:
        return BenchmarkComparison(
            portfolio_xirr_pct=None,
            weighted_benchmark_return_pct=0.0,
            alpha_pct=None,
            fund_details=[],
            note="Benchmark comparison unavailable because portfolio value is zero.",
            data_source="model_benchmark",
            as_of_date=date.today().isoformat(),
        )

    weighted_benchmark = 0.0
    details = []

    for holding in portfolio.holdings:
        benchmark_name, benchmark_return = CATEGORY_BENCHMARKS.get(
            holding.category,
            CATEGORY_BENCHMARKS[FundCategory.OTHER],
        )
        weight = (holding.current_value / total_value) if total_value > 0 else 0
        weighted_benchmark += benchmark_return * weight

        fund_xirr_pct = round(holding.xirr * 100, 2) if holding.xirr is not None else None
        alpha_pct = round(fund_xirr_pct - benchmark_return, 2) if fund_xirr_pct is not None else None

        details.append({
            "scheme": holding.scheme_name,
            "category": holding.category.value,
            "benchmark_name": benchmark_name,
            "benchmark_return_pct": benchmark_return,
            "fund_xirr_pct": fund_xirr_pct,
            "alpha_pct": alpha_pct,
        })

    portfolio_xirr_pct = round(portfolio.overall_xirr * 100, 2) if portfolio.overall_xirr is not None else None
    alpha_pct = round(portfolio_xirr_pct - weighted_benchmark, 2) if portfolio_xirr_pct is not None else None

    return BenchmarkComparison(
        portfolio_xirr_pct=portfolio_xirr_pct,
        weighted_benchmark_return_pct=weighted_benchmark,
        alpha_pct=alpha_pct,
        fund_details=details,
        note=(
            "Benchmark comparison uses category-weighted model benchmarks based on the current "
            "fund mix. It is intended as a planning aid, not a replacement for live benchmark data."
        ),
        data_source="model_benchmark",
        as_of_date=date.today().isoformat(),
    )


def analyze_benchmark_comparison(
    portfolio: Portfolio,
    *,
    prefer_live: bool = False,
) -> BenchmarkComparison:
    """Compare portfolio return to live market-linked proxies, with model fallback."""
    if not prefer_live:
        return _analyze_model_benchmark_comparison(portfolio)

    total_value = portfolio.total_current_value
    if total_value <= 0:
        return _analyze_model_benchmark_comparison(portfolio)

    if portfolio.overall_xirr is None:
        compute_portfolio_returns(portfolio)

    weighted_benchmark = 0.0
    details = []
    live_used = 0
    model_used = 0

    for holding in portfolio.holdings:
        weight = (holding.current_value / total_value) if total_value > 0 else 0.0
        live_proxy = _live_proxy_return_for_holding(holding)

        if live_proxy is not None:
            benchmark_name = live_proxy["benchmark_name"]
            benchmark_return = live_proxy["benchmark_return_pct"]
            source = "live_market"
            live_used += 1
        else:
            benchmark_name, benchmark_return = CATEGORY_BENCHMARKS.get(
                holding.category,
                CATEGORY_BENCHMARKS[FundCategory.OTHER],
            )
            source = "model_fallback"
            model_used += 1

        weighted_benchmark += benchmark_return * weight
        fund_xirr_pct = round(holding.xirr * 100, 2) if holding.xirr is not None else None
        alpha_pct = round(fund_xirr_pct - benchmark_return, 2) if fund_xirr_pct is not None else None

        details.append({
            "scheme": holding.scheme_name,
            "category": holding.category.value,
            "benchmark_name": benchmark_name,
            "benchmark_return_pct": round(benchmark_return, 2),
            "fund_xirr_pct": fund_xirr_pct,
            "alpha_pct": alpha_pct,
            "source": source,
        })

    portfolio_xirr_pct = round(portfolio.overall_xirr * 100, 2) if portfolio.overall_xirr is not None else None
    alpha_pct = round(portfolio_xirr_pct - weighted_benchmark, 2) if portfolio_xirr_pct is not None else None

    if live_used > 0 and model_used == 0:
        note = "Benchmark comparison uses live market-linked proxy returns for the fund categories in this portfolio."
        data_source = "live_market"
    elif live_used > 0:
        note = (
            "Benchmark comparison uses live market-linked proxies where available and model benchmarks "
            "for categories without a reliable live proxy."
        )
        data_source = "mixed_live_and_model"
    else:
        note = (
            "Live benchmark data was unavailable, so the comparison fell back to category-weighted model benchmarks."
        )
        data_source = "model_benchmark"

    return BenchmarkComparison(
        portfolio_xirr_pct=portfolio_xirr_pct,
        weighted_benchmark_return_pct=weighted_benchmark,
        alpha_pct=alpha_pct,
        fund_details=details,
        note=note,
        data_source=data_source,
        as_of_date=date.today().isoformat(),
    )
