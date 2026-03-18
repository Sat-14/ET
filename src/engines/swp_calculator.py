"""SWP (Systematic Withdrawal Plan) Calculator.

For retirement income planning:
- How long will a corpus last with monthly withdrawals?
- How much can you withdraw monthly for N years?
- Impact of inflation on withdrawals
- Bucket strategy: split corpus into short/medium/long term
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SWPResult:
    corpus: float
    monthly_withdrawal: float
    annual_return: float
    inflation_rate: float
    years_corpus_lasts: float
    total_withdrawn: float
    final_balance: float
    inflation_adjusted: bool

    def to_dict(self) -> dict:
        return {
            "initial_corpus": round(self.corpus),
            "monthly_withdrawal": round(self.monthly_withdrawal),
            "annual_return_pct": self.annual_return * 100,
            "inflation_rate_pct": self.inflation_rate * 100,
            "years_corpus_lasts": round(self.years_corpus_lasts, 1),
            "total_withdrawn": round(self.total_withdrawn),
            "final_balance": round(self.final_balance),
            "inflation_adjusted": self.inflation_adjusted,
        }


@dataclass
class BucketStrategy:
    """Three-bucket retirement income strategy."""
    short_term: BucketAllocation  # 1-3 years: liquid/FD
    medium_term: BucketAllocation  # 3-7 years: debt MF
    long_term: BucketAllocation  # 7+ years: equity MF
    total_corpus: float
    annual_income: float
    years_covered: float

    def to_dict(self) -> dict:
        return {
            "total_corpus": round(self.total_corpus),
            "annual_income": round(self.annual_income),
            "years_covered": round(self.years_covered, 1),
            "short_term": self.short_term.to_dict(),
            "medium_term": self.medium_term.to_dict(),
            "long_term": self.long_term.to_dict(),
        }


@dataclass
class BucketAllocation:
    name: str
    amount: float
    pct: float
    expected_return: float
    duration_years: str
    asset_type: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "amount": round(self.amount),
            "allocation_pct": round(self.pct, 1),
            "expected_return_pct": self.expected_return * 100,
            "duration": self.duration_years,
            "asset_type": self.asset_type,
        }


def calculate_swp(
    corpus: float,
    monthly_withdrawal: float,
    annual_return: float = 0.08,
    inflation_rate: float = 0.06,
    adjust_for_inflation: bool = True,
    max_years: int = 50,
) -> SWPResult:
    """Calculate how long a corpus lasts with monthly withdrawals.

    Args:
        corpus: Starting corpus amount
        monthly_withdrawal: Monthly withdrawal amount (first year)
        annual_return: Expected annual return on remaining corpus
        inflation_rate: Annual inflation rate (withdrawal increases yearly)
        adjust_for_inflation: Whether to increase withdrawal with inflation
        max_years: Maximum simulation period
    """
    if corpus <= 0 or monthly_withdrawal <= 0:
        return SWPResult(corpus, monthly_withdrawal, annual_return, inflation_rate,
                         0, 0, corpus, adjust_for_inflation)

    balance = corpus
    monthly_return = (1 + annual_return) ** (1 / 12) - 1
    current_withdrawal = monthly_withdrawal
    total_withdrawn = 0
    months = 0

    for year in range(max_years):
        for month in range(12):
            if balance <= 0:
                break

            # Grow balance
            balance *= (1 + monthly_return)

            # Withdraw
            actual_withdrawal = min(current_withdrawal, balance)
            balance -= actual_withdrawal
            total_withdrawn += actual_withdrawal
            months += 1

        if balance <= 0:
            break

        # Increase withdrawal for inflation at year boundary
        if adjust_for_inflation:
            current_withdrawal *= (1 + inflation_rate)

    years = months / 12

    return SWPResult(
        corpus=corpus,
        monthly_withdrawal=monthly_withdrawal,
        annual_return=annual_return,
        inflation_rate=inflation_rate,
        years_corpus_lasts=years,
        total_withdrawn=total_withdrawn,
        final_balance=max(balance, 0),
        inflation_adjusted=adjust_for_inflation,
    )


def calculate_safe_withdrawal(
    corpus: float,
    years_needed: int = 30,
    annual_return: float = 0.08,
    inflation_rate: float = 0.06,
) -> float:
    """Calculate maximum safe monthly withdrawal for N years.

    Uses PMT formula adjusted for real return.
    """
    if corpus <= 0 or years_needed <= 0:
        return 0

    real_return = (1 + annual_return) / (1 + inflation_rate) - 1
    monthly_real_return = (1 + real_return) ** (1 / 12) - 1
    n = years_needed * 12

    if monthly_real_return <= 0:
        return corpus / n

    # PMT formula
    monthly = corpus * monthly_real_return / (1 - (1 + monthly_real_return) ** (-n))
    return monthly


def calculate_required_corpus(
    monthly_income_needed: float,
    years_needed: int = 30,
    annual_return: float = 0.08,
    inflation_rate: float = 0.06,
) -> float:
    """Calculate corpus needed to generate desired monthly income for N years."""
    if monthly_income_needed <= 0 or years_needed <= 0:
        return 0

    real_return = (1 + annual_return) / (1 + inflation_rate) - 1
    monthly_real_return = (1 + real_return) ** (1 / 12) - 1
    n = years_needed * 12

    if monthly_real_return <= 0:
        return monthly_income_needed * n

    # PV of annuity
    corpus = monthly_income_needed * (1 - (1 + monthly_real_return) ** (-n)) / monthly_real_return
    return corpus


def create_bucket_strategy(
    total_corpus: float,
    monthly_expenses: float,
    years_in_retirement: int = 25,
) -> BucketStrategy:
    """Create a three-bucket retirement income strategy.

    Bucket 1 (Short-term, 1-3 years): Liquid/FD - for immediate expenses
    Bucket 2 (Medium-term, 3-7 years): Debt MF - refills Bucket 1
    Bucket 3 (Long-term, 7+ years): Equity MF - growth to refill Bucket 2

    This strategy protects against sequence-of-returns risk.
    """
    annual_expense = monthly_expenses * 12

    # Bucket 1: 3 years of expenses in liquid/FD
    bucket1_years = 3
    bucket1_amount = annual_expense * bucket1_years
    bucket1_return = 0.06  # FD/liquid return

    # Bucket 2: 4 years of expenses in debt MF
    bucket2_years = 4
    bucket2_amount = annual_expense * bucket2_years
    bucket2_return = 0.08  # Debt MF return

    # Bucket 3: Everything else in equity
    bucket3_amount = max(total_corpus - bucket1_amount - bucket2_amount, 0)
    bucket3_return = 0.12  # Equity return

    # How many years does the total strategy cover?
    # Simplified: run SWP on total corpus
    swp = calculate_swp(
        total_corpus, monthly_expenses, 0.09, 0.06,  # Blended return
    )

    return BucketStrategy(
        short_term=BucketAllocation(
            name="Bucket 1 - Immediate",
            amount=bucket1_amount,
            pct=(bucket1_amount / total_corpus * 100) if total_corpus > 0 else 0,
            expected_return=bucket1_return,
            duration_years="1-3 years",
            asset_type="Liquid Fund / FD / Savings",
        ),
        medium_term=BucketAllocation(
            name="Bucket 2 - Medium",
            amount=bucket2_amount,
            pct=(bucket2_amount / total_corpus * 100) if total_corpus > 0 else 0,
            expected_return=bucket2_return,
            duration_years="3-7 years",
            asset_type="Short Duration Debt MF / Corporate Bond",
        ),
        long_term=BucketAllocation(
            name="Bucket 3 - Growth",
            amount=bucket3_amount,
            pct=(bucket3_amount / total_corpus * 100) if total_corpus > 0 else 0,
            expected_return=bucket3_return,
            duration_years="7+ years",
            asset_type="Equity MF (Large Cap / Flexi Cap)",
        ),
        total_corpus=total_corpus,
        annual_income=annual_expense,
        years_covered=swp.years_corpus_lasts,
    )
