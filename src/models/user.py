"""Data models for user profiles, households, and financial data."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TaxRegime(str, Enum):
    OLD = "old"
    NEW = "new"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class City(str, Enum):
    METRO = "metro"  # Delhi, Mumbai, Kolkata, Chennai
    NON_METRO = "non_metro"


@dataclass
class SalaryBreakup:
    basic: float = 0.0
    da: float = 0.0  # Dearness Allowance
    hra: float = 0.0
    special_allowance: float = 0.0
    lta: float = 0.0  # Leave Travel Allowance
    medical_allowance: float = 0.0
    other_allowance: float = 0.0
    employer_pf: float = 0.0  # Employer's PF contribution
    employer_nps: float = 0.0  # Employer's NPS (80CCD(2))
    professional_tax: float = 0.0
    bonus: float = 0.0

    @property
    def gross_salary(self) -> float:
        return (
            self.basic + self.da + self.hra + self.special_allowance
            + self.lta + self.medical_allowance + self.other_allowance
            + self.bonus
        )

    @property
    def ctc(self) -> float:
        return self.gross_salary + self.employer_pf + self.employer_nps


@dataclass
class Deductions:
    """Chapter VI-A and other deductions (relevant for Old Regime)."""
    # Section 80C (max 1.5L)
    elss: float = 0.0
    ppf: float = 0.0
    lic_premium: float = 0.0
    home_loan_principal: float = 0.0
    tuition_fees: float = 0.0
    nsc: float = 0.0
    sukanya_samriddhi: float = 0.0
    tax_saver_fd: float = 0.0
    employee_pf: float = 0.0  # Employee's PF contribution

    # Section 80D - Health Insurance
    self_health_insurance: float = 0.0  # Max 25K (< 60 yrs)
    parents_health_insurance: float = 0.0  # Max 25K or 50K (senior)
    preventive_health_checkup: float = 0.0  # Max 5K (within 80D limit)

    # Section 80CCD(1B) - NPS additional
    nps_additional: float = 0.0  # Max 50K

    # Section 80E - Education loan interest
    education_loan_interest: float = 0.0  # No limit

    # Section 80G - Donations
    donations: float = 0.0

    # Section 80TTA/80TTB - Savings interest
    savings_interest: float = 0.0  # Max 10K (TTA) or 50K (TTB for seniors)

    # Section 24(b) - Home loan interest
    home_loan_interest: float = 0.0  # Max 2L for self-occupied

    # HRA-related
    rent_paid_annual: float = 0.0

    @property
    def total_80c(self) -> float:
        raw = (
            self.elss + self.ppf + self.lic_premium
            + self.home_loan_principal + self.tuition_fees
            + self.nsc + self.sukanya_samriddhi + self.tax_saver_fd
            + self.employee_pf
        )
        return min(raw, 150_000)

    @property
    def total_80d(self) -> float:
        self_limit = min(self.self_health_insurance, 25_000)
        parents_limit = min(self.parents_health_insurance, 50_000)
        checkup = min(self.preventive_health_checkup, 5_000)
        return self_limit + parents_limit + checkup

    @property
    def total_80ccd_1b(self) -> float:
        return min(self.nps_additional, 50_000)


@dataclass
class InsuranceCoverage:
    life_cover: float = 0.0  # Total sum assured
    health_cover: float = 0.0  # Health insurance cover
    has_critical_illness: bool = False
    has_accident_cover: bool = False
    term_plan_premium: float = 0.0
    health_premium: float = 0.0


@dataclass
class Debt:
    home_loan_outstanding: float = 0.0
    home_loan_emi: float = 0.0
    car_loan_outstanding: float = 0.0
    car_loan_emi: float = 0.0
    personal_loan_outstanding: float = 0.0
    personal_loan_emi: float = 0.0
    credit_card_outstanding: float = 0.0
    education_loan_outstanding: float = 0.0
    education_loan_emi: float = 0.0
    other_loan_outstanding: float = 0.0
    other_loan_emi: float = 0.0

    @property
    def total_outstanding(self) -> float:
        return (
            self.home_loan_outstanding + self.car_loan_outstanding
            + self.personal_loan_outstanding + self.credit_card_outstanding
            + self.education_loan_outstanding + self.other_loan_outstanding
        )

    @property
    def total_monthly_emi(self) -> float:
        return (
            self.home_loan_emi + self.car_loan_emi
            + self.personal_loan_emi + self.education_loan_emi
            + self.other_loan_emi
        )


@dataclass
class MonthlyExpenses:
    rent: float = 0.0
    groceries: float = 0.0
    utilities: float = 0.0
    transportation: float = 0.0
    dining_out: float = 0.0
    entertainment: float = 0.0
    shopping: float = 0.0
    education: float = 0.0
    medical: float = 0.0
    misc: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.rent + self.groceries + self.utilities
            + self.transportation + self.dining_out + self.entertainment
            + self.shopping + self.education + self.medical + self.misc
        )


@dataclass
class IndividualProfile:
    name: str = ""
    age: int = 30
    gender: Gender = Gender.MALE
    city: City = City.METRO
    salary: SalaryBreakup = field(default_factory=SalaryBreakup)
    deductions: Deductions = field(default_factory=Deductions)
    insurance: InsuranceCoverage = field(default_factory=InsuranceCoverage)
    debt: Debt = field(default_factory=Debt)
    monthly_expenses: MonthlyExpenses = field(default_factory=MonthlyExpenses)
    emergency_fund: float = 0.0  # Current emergency fund corpus
    current_investments: float = 0.0  # Total investment corpus
    monthly_sip: float = 0.0  # Current monthly SIP amount
    epf_balance: float = 0.0
    ppf_balance: float = 0.0
    nps_balance: float = 0.0
    other_income: float = 0.0  # Rental, interest, freelance, etc.
    preferred_regime: Optional[TaxRegime] = None
    retirement_age: int = 60

    @property
    def annual_income(self) -> float:
        return self.salary.gross_salary + self.other_income

    @property
    def monthly_income(self) -> float:
        return self.annual_income / 12

    @property
    def total_retirement_corpus(self) -> float:
        return self.epf_balance + self.ppf_balance + self.nps_balance

    @property
    def years_to_retirement(self) -> int:
        return max(self.retirement_age - self.age, 0)


@dataclass
class HouseholdProfile:
    person_a: IndividualProfile = field(default_factory=IndividualProfile)
    person_b: Optional[IndividualProfile] = None
    joint_goals: list = field(default_factory=list)
    shared_monthly_expenses: MonthlyExpenses = field(default_factory=MonthlyExpenses)
    num_dependents: int = 0  # Children, elderly parents
    combined_emergency_fund: float = 0.0

    @property
    def is_couple(self) -> bool:
        return self.person_b is not None

    @property
    def combined_annual_income(self) -> float:
        total = self.person_a.annual_income
        if self.person_b:
            total += self.person_b.annual_income
        return total

    @property
    def combined_monthly_expenses(self) -> float:
        total = self.person_a.monthly_expenses.total
        if self.person_b:
            total += self.person_b.monthly_expenses.total
        total += self.shared_monthly_expenses.total
        return total
