"""Behavioral Pattern Detector for MF Portfolio X-Ray.

Detects common investor behavioral biases based on transaction history.
Research-backed patterns from:
- Chadha (2024), European Economic Letters
- ACR Journal (2024), Cognitive Biases in Indian Retail Investors
- PMC Study (2022), Financial Literacy and Behavioral Biases

Biases detected:
1. SIP Panic Stop (Loss Aversion + Herd Mentality)
2. Buy High Sell Low (Overconfidence + Over-reaction)
3. Theme Chasing (Herd Effect + Representativeness)
4. Excessive Switching (Regret Aversion)
5. Recency Bias (Anchoring + Representativeness)
6. Disposition Effect (selling winners, holding losers)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from collections import defaultdict

from src.models.portfolio import (
    Portfolio,
    FundHolding,
    Transaction,
    TransactionType,
    BehavioralPattern,
    FundCategory,
)


# -------------------------------------------------------------------
# Index drawdown data (approximate Nifty 50 major drawdowns)
# In production, fetch real-time from MFAPI or Yahoo Finance
# -------------------------------------------------------------------
MAJOR_MARKET_DROPS: list[tuple[date, date, float]] = [
    # (start_date, end_date, drop_percentage)
    (date(2020, 2, 1), date(2020, 4, 1), -0.38),   # COVID crash
    (date(2022, 1, 1), date(2022, 6, 30), -0.16),   # Rate hike selloff
    (date(2023, 9, 1), date(2023, 11, 30), -0.10),  # Mid-year correction
    (date(2024, 10, 1), date(2024, 11, 30), -0.12), # Late 2024 correction
]

MAJOR_MARKET_RALLIES: list[tuple[date, date, float]] = [
    (date(2020, 4, 1), date(2021, 2, 1), 0.90),    # Post-COVID rally
    (date(2023, 4, 1), date(2023, 9, 1), 0.15),     # H1 2023 rally
    (date(2024, 1, 1), date(2024, 9, 30), 0.25),    # 2024 bull run
]

TRENDING_THEMES_BY_PERIOD: dict[str, list[str]] = {
    "2023-H2": ["infrastructure", "defence", "psu", "manufacturing"],
    "2024-H1": ["ai", "technology", "smallcap", "micro"],
    "2024-H2": ["defence", "energy", "consumption"],
    "2025-H1": ["infrastructure", "ev", "green energy"],
}


def _is_during_period(txn_date: date, start: date, end: date) -> bool:
    return start <= txn_date <= end


def _get_sip_months(transactions: list[Transaction]) -> list[date]:
    """Extract months where SIP transactions occurred."""
    sip_months = set()
    for txn in transactions:
        if txn.type == TransactionType.SIP:
            sip_months.add(date(txn.date.year, txn.date.month, 1))
    return sorted(sip_months)


def detect_sip_panic_stop(portfolio: Portfolio) -> list[BehavioralPattern]:
    """Detect SIP cessation during market drops.

    Bias: Loss Aversion + Herd Mentality
    Research: Chadha (2024) - herd effect and regret aversion in MF investors
    """
    patterns = []

    for holding in portfolio.holdings:
        sip_months = _get_sip_months(holding.transactions)
        if len(sip_months) < 3:
            continue

        for drop_start, drop_end, drop_pct in MAJOR_MARKET_DROPS:
            # Check if SIPs were active before the drop
            pre_drop_sips = [m for m in sip_months if m < drop_start and m >= drop_start - timedelta(days=90)]
            if not pre_drop_sips:
                continue

            # Check if SIPs stopped during/after the drop
            during_drop_sips = [m for m in sip_months if drop_start <= m <= drop_end + timedelta(days=60)]
            if len(pre_drop_sips) >= 2 and len(during_drop_sips) == 0:
                patterns.append(BehavioralPattern(
                    pattern_id="sip_panic_stop",
                    name="SIP Panic Stop",
                    description=f"Stopped SIP in {holding.scheme_name} during {drop_pct:.0%} market drop",
                    bias_type="Loss Aversion + Herd Mentality",
                    severity="high",
                    evidence=[
                        f"SIP was active before {drop_start.strftime('%b %Y')}",
                        f"SIP stopped during market drop of {drop_pct:.0%}",
                        f"Market dropped between {drop_start.strftime('%b %Y')} and {drop_end.strftime('%b %Y')}",
                    ],
                    recommendation=(
                        "SIPs during market drops buy units at lower NAV, boosting long-term returns. "
                        "Set up auto-debit SIPs so emotions don't derail your plan."
                    ),
                ))
                break  # One pattern per holding

    return patterns


def detect_buy_high_sell_low(portfolio: Portfolio) -> list[BehavioralPattern]:
    """Detect buying after rallies and selling after drops.

    Bias: Overconfidence + Over-reaction
    Research: ACR Journal (2024) - anchoring bias (beta=0.289), overconfidence (beta=0.250)
    """
    patterns = []

    for holding in portfolio.holdings:
        purchases_during_rally = []
        redemptions_during_drop = []

        for txn in holding.transactions:
            if txn.is_inflow and txn.type != TransactionType.SIP:
                for rally_start, rally_end, _ in MAJOR_MARKET_RALLIES:
                    if _is_during_period(txn.date, rally_start, rally_end):
                        purchases_during_rally.append(txn)

            if txn.type == TransactionType.REDEMPTION:
                for drop_start, drop_end, _ in MAJOR_MARKET_DROPS:
                    if _is_during_period(txn.date, drop_start, drop_end):
                        redemptions_during_drop.append(txn)

        if purchases_during_rally and redemptions_during_drop:
            total_bought = sum(t.amount for t in purchases_during_rally)
            total_sold = sum(t.amount for t in redemptions_during_drop)
            patterns.append(BehavioralPattern(
                pattern_id="buy_high_sell_low",
                name="Buy High, Sell Low",
                description=f"Bought {holding.scheme_name} during rally, sold during drop",
                bias_type="Overconfidence + Over-reaction",
                severity="high",
                evidence=[
                    f"Invested Rs {total_bought:,.0f} during market rally",
                    f"Redeemed Rs {total_sold:,.0f} during market drop",
                    "This pattern destroys wealth over time",
                ],
                recommendation=(
                    "Avoid timing the market. Stick to SIPs for disciplined investing. "
                    "If you must invest lump sum, use Systematic Transfer Plans (STPs)."
                ),
            ))

    return patterns


def detect_theme_chasing(portfolio: Portfolio) -> list[BehavioralPattern]:
    """Detect investing in trending themes.

    Bias: Herd Effect + Representativeness
    Research: Chadha (2024) - herding behavior in MF investors
    """
    patterns = []

    sectoral_thematic = [
        h for h in portfolio.holdings
        if h.category in (FundCategory.SECTORAL, FundCategory.THEMATIC)
    ]

    if not sectoral_thematic:
        return patterns

    # Check if sectoral/thematic is >25% of portfolio
    total_value = portfolio.total_current_value
    theme_value = sum(h.current_value for h in sectoral_thematic)
    theme_pct = (theme_value / total_value * 100) if total_value > 0 else 0

    if theme_pct > 25:
        fund_names = [h.scheme_name for h in sectoral_thematic[:5]]
        patterns.append(BehavioralPattern(
            pattern_id="theme_chasing",
            name="Theme Chasing",
            description=f"Sectoral/thematic funds are {theme_pct:.0f}% of portfolio",
            bias_type="Herd Effect + Representativeness",
            severity="high" if theme_pct > 40 else "medium",
            evidence=[
                f"Sectoral/thematic allocation: {theme_pct:.0f}% (recommended: <15%)",
                f"Funds: {', '.join(fund_names)}",
                "Theme funds are high-risk and often bought after they've already rallied",
            ],
            recommendation=(
                "Limit sectoral/thematic funds to 10-15% of portfolio. "
                "Prefer diversified flexicap or multicap funds for core allocation."
            ),
        ))

    return patterns


def detect_excessive_switching(portfolio: Portfolio) -> list[BehavioralPattern]:
    """Detect frequent fund switches without clear reason.

    Bias: Regret Aversion + Cognitive Illusion
    Research: Chadha (2024), PMC Study (2022) - regret aversion
    """
    patterns = []

    # Count switch transactions per fund
    switches: dict[str, int] = defaultdict(int)
    for holding in portfolio.holdings:
        for txn in holding.transactions:
            if txn.type in (TransactionType.SWITCH_IN, TransactionType.SWITCH_OUT):
                switches[holding.scheme_name] += 1

    # Also count short-hold redemptions (< 1 year)
    for holding in portfolio.holdings:
        purchases = [t for t in holding.transactions if t.is_inflow]
        redemptions = [t for t in holding.transactions if t.type == TransactionType.REDEMPTION]

        for red in redemptions:
            recent_purchases = [
                p for p in purchases
                if 0 < (red.date - p.date).days < 365
            ]
            if recent_purchases:
                switches[holding.scheme_name] += 1

    frequent_switchers = {k: v for k, v in switches.items() if v >= 3}
    if frequent_switchers:
        names = list(frequent_switchers.keys())[:3]
        patterns.append(BehavioralPattern(
            pattern_id="excessive_switching",
            name="Excessive Switching",
            description=f"Frequent switches/short-term redemptions in {len(frequent_switchers)} funds",
            bias_type="Regret Aversion + Cognitive Illusion",
            severity="medium",
            evidence=[
                f"Funds with frequent activity: {', '.join(names)}",
                "Short holding periods (<1 year) lead to exit loads and tax inefficiency",
                "Frequent switching usually underperforms buy-and-hold",
            ],
            recommendation=(
                "Give funds at least 3 years to perform. "
                "Frequent switching incurs exit loads and short-term capital gains tax."
            ),
        ))

    return patterns


def detect_recency_bias(portfolio: Portfolio) -> list[BehavioralPattern]:
    """Detect picking funds based only on recent returns.

    Bias: Anchoring + Representativeness
    Research: ACR Journal (2024) - anchoring bias is strongest predictor
    """
    patterns = []

    # Heuristic: if most recent purchases are in small-cap/mid-cap during a bull run
    recent_purchases = []
    cutoff = date.today() - timedelta(days=365)

    for holding in portfolio.holdings:
        for txn in holding.transactions:
            if txn.is_inflow and txn.date >= cutoff:
                recent_purchases.append((holding, txn))

    if not recent_purchases:
        return patterns

    # Check if recent purchases are concentrated in high-return categories
    high_return_cats = {
        FundCategory.SMALL_CAP, FundCategory.MID_CAP,
        FundCategory.SECTORAL, FundCategory.THEMATIC,
    }

    high_return_purchases = [
        (h, t) for h, t in recent_purchases
        if h.category in high_return_cats
    ]

    if len(high_return_purchases) > len(recent_purchases) * 0.7 and len(recent_purchases) >= 3:
        total_amount = sum(t.amount for _, t in high_return_purchases)
        patterns.append(BehavioralPattern(
            pattern_id="recency_bias",
            name="Recency Bias",
            description="Recent investments heavily skewed towards high-return categories",
            bias_type="Anchoring + Representativeness",
            severity="medium",
            evidence=[
                f"{len(high_return_purchases)} of {len(recent_purchases)} recent purchases in high-risk categories",
                f"Rs {total_amount:,.0f} invested in small/mid/sectoral funds recently",
                "Past returns don't guarantee future performance",
            ],
            recommendation=(
                "Don't chase last year's winners. Diversify across large-cap, mid-cap and debt. "
                "A core portfolio of 60-70% in large/flexicap funds reduces risk."
            ),
        ))

    return patterns


def detect_disposition_effect(portfolio: Portfolio) -> list[BehavioralPattern]:
    """Detect selling winners too early while holding losers.

    Bias: Loss Aversion + Disposition Effect
    """
    patterns = []

    sold_at_profit = []
    holding_at_loss = []

    for holding in portfolio.holdings:
        redemptions = [t for t in holding.transactions if t.type == TransactionType.REDEMPTION]
        if redemptions and holding.absolute_return_pct > 0:
            sold_at_profit.append(holding.scheme_name)

        if not redemptions and holding.absolute_return_pct < -10:
            holding_at_loss.append(holding.scheme_name)

    if sold_at_profit and holding_at_loss:
        patterns.append(BehavioralPattern(
            pattern_id="disposition_effect",
            name="Disposition Effect",
            description="Selling profitable funds while holding loss-making ones",
            bias_type="Loss Aversion + Disposition Effect",
            severity="medium",
            evidence=[
                f"Sold (at profit): {', '.join(sold_at_profit[:3])}",
                f"Holding (at loss): {', '.join(holding_at_loss[:3])}",
                "This pattern locks in small gains but lets losses grow",
            ],
            recommendation=(
                "Evaluate each fund on its future potential, not past performance. "
                "If fundamentals are weak, exit loss-making funds rather than holding out of hope."
            ),
        ))

    return patterns


def run_full_behavioral_analysis(portfolio: Portfolio) -> list[BehavioralPattern]:
    """Run all behavioral pattern detectors on the portfolio."""
    all_patterns = []
    all_patterns.extend(detect_sip_panic_stop(portfolio))
    all_patterns.extend(detect_buy_high_sell_low(portfolio))
    all_patterns.extend(detect_theme_chasing(portfolio))
    all_patterns.extend(detect_excessive_switching(portfolio))
    all_patterns.extend(detect_recency_bias(portfolio))
    all_patterns.extend(detect_disposition_effect(portfolio))

    # Sort by severity
    severity_order = {"high": 0, "medium": 1, "low": 2}
    all_patterns.sort(key=lambda p: severity_order.get(p.severity, 3))

    return all_patterns


def generate_behavioral_summary(patterns: list[BehavioralPattern]) -> dict:
    """Generate a summary of behavioral analysis for the AI layer."""
    if not patterns:
        return {
            "total_patterns": 0,
            "overall_assessment": "Excellent! No significant behavioral biases detected.",
            "patterns": [],
        }

    high = [p for p in patterns if p.severity == "high"]
    medium = [p for p in patterns if p.severity == "medium"]

    if high:
        assessment = (
            f"Found {len(high)} high-severity behavioral pattern(s) that may be hurting your returns. "
            "These are common biases - awareness is the first step to correcting them."
        )
    elif medium:
        assessment = (
            f"Found {len(medium)} moderate behavioral pattern(s). "
            "You're doing okay, but small adjustments can improve outcomes."
        )
    else:
        assessment = "Minor behavioral patterns detected. Overall disciplined investing."

    return {
        "total_patterns": len(patterns),
        "high_severity": len(high),
        "medium_severity": len(medium),
        "overall_assessment": assessment,
        "patterns": [p.to_dict() for p in patterns],
    }
