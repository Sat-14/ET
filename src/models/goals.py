"""Data models for financial goals and life events."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GoalType(str, Enum):
    RETIREMENT = "retirement"
    CHILD_EDUCATION = "child_education"
    CHILD_MARRIAGE = "child_marriage"
    HOME_PURCHASE = "home_purchase"
    CAR_PURCHASE = "car_purchase"
    VACATION = "vacation"
    EMERGENCY_FUND = "emergency_fund"
    FIRE = "fire"  # Financial Independence Retire Early
    WEALTH_CREATION = "wealth_creation"
    CUSTOM = "custom"


class GoalPriority(str, Enum):
    CRITICAL = "critical"  # Retirement, emergency fund
    HIGH = "high"  # Child education, home
    MEDIUM = "medium"  # Car, vacation
    LOW = "low"  # Wealth creation, custom


class LifeEventType(str, Enum):
    SALARY_HIKE = "salary_hike"
    BONUS = "bonus"
    JOB_LOSS = "job_loss"
    SABBATICAL = "sabbatical"
    HAVING_BABY = "having_baby"
    HOME_PURCHASE = "home_purchase"
    CAR_PURCHASE = "car_purchase"
    CHILD_EDUCATION_START = "child_education_start"
    MARRIAGE = "marriage"
    PARENT_MEDICAL = "parent_medical"
    EARLY_RETIREMENT = "early_retirement"
    START_BUSINESS = "start_business"
    INHERITANCE = "inheritance"
    RELOCATION = "relocation"


@dataclass
class FinancialGoal:
    name: str
    goal_type: GoalType
    target_amount: float  # In today's rupees
    target_year: int  # Year when money is needed
    current_corpus: float = 0.0  # Amount already saved for this goal
    monthly_sip: float = 0.0  # Current SIP towards this goal
    inflation_rate: float = 6.0  # Annual inflation %
    expected_return: float = 12.0  # Expected annual return %
    priority: GoalPriority = GoalPriority.MEDIUM

    @property
    def years_remaining(self) -> int:
        from datetime import datetime
        return max(self.target_year - datetime.now().year, 0)

    @property
    def inflation_adjusted_target(self) -> float:
        """Target amount adjusted for inflation."""
        n = self.years_remaining
        return self.target_amount * (1 + self.inflation_rate / 100) ** n

    @property
    def future_value_of_current_corpus(self) -> float:
        """What current corpus will grow to by target year."""
        n = self.years_remaining
        return self.current_corpus * (1 + self.expected_return / 100) ** n

    @property
    def gap(self) -> float:
        """How much more is needed beyond current corpus growth."""
        return max(self.inflation_adjusted_target - self.future_value_of_current_corpus, 0)

    def required_monthly_sip(self) -> float:
        """Monthly SIP needed to bridge the gap."""
        if self.years_remaining <= 0:
            return self.gap
        r = self.expected_return / 100 / 12  # Monthly return
        n = self.years_remaining * 12  # Total months
        if r == 0:
            return self.gap / n if n > 0 else self.gap
        return self.gap * r / ((1 + r) ** n - 1)

    @property
    def progress_pct(self) -> float:
        """Percentage of goal funded (corpus FV / inflation-adj target)."""
        target = self.inflation_adjusted_target
        if target == 0:
            return 100.0
        return min((self.future_value_of_current_corpus / target) * 100, 100.0)


@dataclass
class LifeEvent:
    event_type: LifeEventType
    name: str
    year: int  # When it occurs
    month: int = 1  # Month (1-12)

    # Financial impact
    one_time_cost: float = 0.0  # One-time expense
    monthly_income_change: float = 0.0  # +/- change in monthly income
    monthly_expense_change: float = 0.0  # +/- change in monthly expenses
    duration_months: int = 0  # How long the changes last (0 = permanent)

    # Additional parameters
    new_emi: float = 0.0  # New EMI if taking a loan
    insurance_need_change: float = 0.0  # Change in insurance requirement
    tax_impact_annual: float = 0.0  # Change in tax liability

    description: str = ""

    @property
    def total_impact_over_duration(self) -> float:
        """Net financial impact over the event duration."""
        months = self.duration_months if self.duration_months > 0 else 12
        monthly_net = self.monthly_income_change - self.monthly_expense_change - self.new_emi
        return -self.one_time_cost + (monthly_net * months)


# Pre-built event templates with sensible defaults for India
LIFE_EVENT_TEMPLATES: dict[LifeEventType, dict] = {
    LifeEventType.SALARY_HIKE: {
        "name": "Salary Hike",
        "monthly_income_change": 0,  # User fills in
        "duration_months": 0,  # Permanent
        "description": "Annual salary increment or promotion",
    },
    LifeEventType.BONUS: {
        "name": "Annual Bonus",
        "one_time_cost": 0,  # Negative cost = income
        "description": "One-time bonus or variable pay",
    },
    LifeEventType.JOB_LOSS: {
        "name": "Job Loss",
        "monthly_income_change": 0,  # Will be set to -salary
        "duration_months": 6,  # Assume 6 months to find new job
        "description": "Unexpected job loss - income stops temporarily",
    },
    LifeEventType.SABBATICAL: {
        "name": "Career Sabbatical",
        "monthly_income_change": 0,  # Will be set to -salary
        "duration_months": 6,
        "description": "Planned career break",
    },
    LifeEventType.HAVING_BABY: {
        "name": "Having a Baby",
        "one_time_cost": 200_000,  # Hospital + initial expenses
        "monthly_expense_change": 15_000,  # Diapers, formula, etc.
        "insurance_need_change": 5_000_000,  # Need more life cover
        "duration_months": 0,  # Permanent
        "description": "New addition to the family",
    },
    LifeEventType.HOME_PURCHASE: {
        "name": "Home Purchase",
        "one_time_cost": 1_000_000,  # Down payment
        "new_emi": 50_000,  # Home loan EMI
        "tax_impact_annual": -200_000,  # Tax benefit on interest
        "duration_months": 0,  # EMI is long-term
        "description": "Buying a house with home loan",
    },
    LifeEventType.CAR_PURCHASE: {
        "name": "Car Purchase",
        "one_time_cost": 300_000,  # Down payment
        "new_emi": 15_000,
        "monthly_expense_change": 5_000,  # Fuel, maintenance, insurance
        "duration_months": 60,  # 5-year loan
        "description": "Buying a car with loan",
    },
    LifeEventType.CHILD_EDUCATION_START: {
        "name": "Child's Higher Education",
        "one_time_cost": 2_000_000,  # First year fees
        "monthly_expense_change": 50_000,  # Ongoing costs
        "duration_months": 48,  # 4-year degree
        "description": "Child starting college/university",
    },
    LifeEventType.MARRIAGE: {
        "name": "Marriage",
        "one_time_cost": 1_500_000,  # Wedding expenses
        "description": "Marriage expenses (self or child)",
    },
    LifeEventType.PARENT_MEDICAL: {
        "name": "Parent Medical Emergency",
        "one_time_cost": 500_000,
        "monthly_expense_change": 10_000,  # Ongoing care
        "duration_months": 12,
        "description": "Parent's medical emergency and treatment",
    },
    LifeEventType.EARLY_RETIREMENT: {
        "name": "Early Retirement",
        "monthly_income_change": 0,  # Will be set to -salary
        "duration_months": 0,  # Permanent
        "description": "Retiring before standard retirement age",
    },
    LifeEventType.START_BUSINESS: {
        "name": "Starting a Business",
        "one_time_cost": 500_000,  # Initial investment
        "monthly_income_change": 0,  # Volatile - user defines
        "duration_months": 0,
        "description": "Leaving job to start own business",
    },
}
