"""Data models for mutual fund portfolios and transactions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class TransactionType(str, Enum):
    PURCHASE = "purchase"
    REDEMPTION = "redemption"
    SIP = "sip"
    STP_IN = "stp_in"
    STP_OUT = "stp_out"
    SWITCH_IN = "switch_in"
    SWITCH_OUT = "switch_out"
    DIVIDEND_PAYOUT = "dividend_payout"
    DIVIDEND_REINVEST = "dividend_reinvest"


class FundCategory(str, Enum):
    LARGE_CAP = "large_cap"
    MID_CAP = "mid_cap"
    SMALL_CAP = "small_cap"
    MULTI_CAP = "multi_cap"
    FLEXI_CAP = "flexi_cap"
    ELSS = "elss"
    SECTORAL = "sectoral"
    THEMATIC = "thematic"
    INDEX = "index"
    DEBT_SHORT = "debt_short_duration"
    DEBT_MEDIUM = "debt_medium_duration"
    DEBT_LONG = "debt_long_duration"
    LIQUID = "liquid"
    HYBRID_AGGRESSIVE = "hybrid_aggressive"
    HYBRID_CONSERVATIVE = "hybrid_conservative"
    INTERNATIONAL = "international"
    GOLD = "gold"
    OTHER = "other"


class PlanType(str, Enum):
    DIRECT = "direct"
    REGULAR = "regular"


@dataclass
class Transaction:
    date: date
    type: TransactionType
    amount: float
    units: float
    nav: float
    scheme_name: str
    folio: str
    isin: Optional[str] = None
    amfi_code: Optional[str] = None

    @property
    def is_inflow(self) -> bool:
        return self.type in (
            TransactionType.PURCHASE,
            TransactionType.SIP,
            TransactionType.STP_IN,
            TransactionType.SWITCH_IN,
            TransactionType.DIVIDEND_REINVEST,
        )


@dataclass
class FundHolding:
    scheme_name: str
    folio: str
    units: float
    current_nav: float = 0.0
    invested_amount: float = 0.0
    isin: Optional[str] = None
    amfi_code: Optional[str] = None
    category: FundCategory = FundCategory.OTHER
    plan_type: PlanType = PlanType.REGULAR
    expense_ratio: float = 0.0
    transactions: list[Transaction] = field(default_factory=list)
    xirr: Optional[float] = None  # Computed XIRR for this holding

    @property
    def current_value(self) -> float:
        return self.units * self.current_nav

    @property
    def absolute_return(self) -> float:
        if self.invested_amount == 0:
            return 0.0
        return self.current_value - self.invested_amount

    @property
    def absolute_return_pct(self) -> float:
        if self.invested_amount == 0:
            return 0.0
        return (self.absolute_return / self.invested_amount) * 100


@dataclass
class FundOverlap:
    fund_a: str
    fund_b: str
    common_stocks: list[str] = field(default_factory=list)
    overlap_pct: float = 0.0  # Jaccard similarity


@dataclass
class Portfolio:
    investor_name: str = ""
    investor_email: str = ""
    investor_pan: str = ""
    holdings: list[FundHolding] = field(default_factory=list)
    overlaps: list[FundOverlap] = field(default_factory=list)
    overall_xirr: Optional[float] = None

    @property
    def total_invested(self) -> float:
        return sum(h.invested_amount for h in self.holdings)

    @property
    def total_current_value(self) -> float:
        return sum(h.current_value for h in self.holdings)

    @property
    def total_gain(self) -> float:
        return self.total_current_value - self.total_invested

    @property
    def num_funds(self) -> int:
        return len(self.holdings)

    def by_category(self) -> dict[FundCategory, list[FundHolding]]:
        result: dict[FundCategory, list[FundHolding]] = {}
        for h in self.holdings:
            result.setdefault(h.category, []).append(h)
        return result

    def category_allocation(self) -> dict[FundCategory, float]:
        """Returns category-wise allocation as percentages."""
        total = self.total_current_value
        if total == 0:
            return {}
        result: dict[FundCategory, float] = {}
        for h in self.holdings:
            result[h.category] = result.get(h.category, 0) + h.current_value
        return {k: (v / total) * 100 for k, v in result.items()}

    def total_expense_drag(self) -> float:
        """Annual expense drag in rupees."""
        return sum(h.current_value * h.expense_ratio / 100 for h in self.holdings)


@dataclass
class BehavioralPattern:
    pattern_id: str
    name: str
    description: str
    bias_type: str
    severity: str  # "low", "medium", "high"
    evidence: list[str] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "description": self.description,
            "bias_type": self.bias_type,
            "severity": self.severity,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
        }
