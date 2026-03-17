"""Sample demo data for instant demo without user input.

Provides pre-built profiles, portfolios, and goals for showcasing
all features of ET Money Mentor without any setup.
"""

from __future__ import annotations

from src.models.user import (
    IndividualProfile, SalaryBreakup, Deductions, InsuranceCoverage,
    Debt, MonthlyExpenses, Gender, City, HouseholdProfile,
)
from src.models.goals import FinancialGoal, GoalType, GoalPriority, LifeEvent, LifeEventType
from src.models.portfolio import (
    Portfolio, FundHolding, Transaction, FundCategory, TransactionType, PlanType,
)

from datetime import date


def get_demo_profile_young() -> IndividualProfile:
    """28-year-old IT professional in Bangalore, early career."""
    return IndividualProfile(
        name="Rahul Sharma",
        age=28,
        gender=Gender.MALE,
        city=City.METRO,
        salary=SalaryBreakup(
            basic=500_000,
            da=0,
            hra=200_000,
            special_allowance=350_000,
            lta=50_000,
            employer_pf=60_000,
            bonus=100_000,
        ),
        deductions=Deductions(
            employee_pf=60_000,
            elss=50_000,
            self_health_insurance=15_000,
        ),
        insurance=InsuranceCoverage(
            life_cover=0,  # No life insurance yet
            health_cover=500_000,
        ),
        debt=Debt(),
        monthly_expenses=MonthlyExpenses(
            rent=18_000,
            groceries=8_000,
            utilities=3_000,
            transportation=5_000,
            misc=10_000,
        ),
        emergency_fund=150_000,  # ~3 months
        current_investments=300_000,
        monthly_sip=15_000,
        epf_balance=240_000,
        retirement_age=55,  # Wants early retirement
    )


def get_demo_profile_mid() -> IndividualProfile:
    """38-year-old manager in Mumbai, growing family."""
    return IndividualProfile(
        name="Priya Mehta",
        age=38,
        gender=Gender.FEMALE,
        city=City.METRO,
        salary=SalaryBreakup(
            basic=900_000,
            da=0,
            hra=360_000,
            special_allowance=500_000,
            lta=80_000,
            employer_pf=108_000,
            employer_nps=50_000,
            bonus=200_000,
            professional_tax=2_500,
        ),
        deductions=Deductions(
            employee_pf=108_000,
            ppf=150_000,
            elss=100_000,
            lic_premium=50_000,
            nps_additional=50_000,
            self_health_insurance=25_000,
            parents_health_insurance=40_000,
            home_loan_interest=200_000,
            home_loan_principal=100_000,
            rent_paid_annual=0,  # Own house
        ),
        insurance=InsuranceCoverage(
            life_cover=5_000_000,
            health_cover=1_000_000,
            has_critical_illness=True,
        ),
        debt=Debt(
            home_loan_emi=45_000,
            home_loan_outstanding=4_500_000,
        ),
        monthly_expenses=MonthlyExpenses(
            rent=0,
            groceries=15_000,
            utilities=5_000,
            transportation=8_000,
            misc=20_000,
        ),
        emergency_fund=500_000,
        current_investments=2_500_000,
        monthly_sip=40_000,
        epf_balance=1_200_000,
        ppf_balance=800_000,
        nps_balance=300_000,
        retirement_age=60,
    )


def get_demo_profile_senior() -> IndividualProfile:
    """52-year-old pre-retirement in Delhi."""
    return IndividualProfile(
        name="Anil Gupta",
        age=52,
        gender=Gender.MALE,
        city=City.METRO,
        salary=SalaryBreakup(
            basic=1_200_000,
            da=0,
            hra=480_000,
            special_allowance=600_000,
            lta=100_000,
            employer_pf=144_000,
            bonus=300_000,
            professional_tax=2_500,
        ),
        deductions=Deductions(
            employee_pf=144_000,
            ppf=150_000,
            elss=150_000,
            lic_premium=100_000,
            nps_additional=50_000,
            self_health_insurance=25_000,
            parents_health_insurance=50_000,
        ),
        insurance=InsuranceCoverage(
            life_cover=10_000_000,
            health_cover=2_500_000,
            has_critical_illness=True,
        ),
        debt=Debt(),
        monthly_expenses=MonthlyExpenses(
            rent=0,
            groceries=20_000,
            utilities=8_000,
            transportation=10_000,
            misc=30_000,
        ),
        emergency_fund=1_500_000,
        current_investments=8_000_000,
        monthly_sip=80_000,
        epf_balance=3_500_000,
        ppf_balance=2_000_000,
        nps_balance=1_000_000,
        retirement_age=60,
    )


def get_demo_couple() -> HouseholdProfile:
    """Dual-income couple for couple planner demo."""
    partner1 = get_demo_profile_mid()
    partner2 = IndividualProfile(
        name="Vikram Mehta",
        age=40,
        gender=Gender.MALE,
        city=City.METRO,
        salary=SalaryBreakup(
            basic=700_000,
            hra=280_000,
            special_allowance=400_000,
            employer_pf=84_000,
            bonus=150_000,
        ),
        deductions=Deductions(
            employee_pf=84_000,
            ppf=100_000,
            self_health_insurance=25_000,
        ),
        insurance=InsuranceCoverage(
            life_cover=5_000_000,
            health_cover=1_000_000,
        ),
        monthly_expenses=MonthlyExpenses(
            groceries=10_000,
            utilities=3_000,
            transportation=6_000,
            misc=15_000,
        ),
        emergency_fund=300_000,
        current_investments=1_500_000,
        monthly_sip=25_000,
        epf_balance=800_000,
        ppf_balance=400_000,
    )
    return HouseholdProfile(
        partner1=partner1,
        partner2=partner2,
        shared_expenses=30_000,
        shared_goals_value=5_000_000,
    )


def get_demo_portfolio() -> Portfolio:
    """Sample MF portfolio with diverse holdings for X-Ray demo."""
    return Portfolio(
        investor_name="Rahul Sharma",
        holdings=[
            FundHolding(
                scheme_name="HDFC Flexi Cap Fund - Direct Growth",
                amfi_code="119551",
                folio="12345678",
                category=FundCategory.FLEXI_CAP,
                plan_type=PlanType.DIRECT,
                units=500.0,
                avg_nav=50.0,
                current_nav=72.5,
                invested_value=25_000,
                current_value=36_250,
                expense_ratio=0.77,
                transactions=[
                    Transaction(date=date(2022, 1, 10), type=TransactionType.SIP, amount=5000, nav=45.0, units=111.11),
                    Transaction(date=date(2022, 7, 10), type=TransactionType.SIP, amount=5000, nav=48.0, units=104.17),
                    Transaction(date=date(2023, 1, 10), type=TransactionType.SIP, amount=5000, nav=52.0, units=96.15),
                    Transaction(date=date(2023, 7, 10), type=TransactionType.SIP, amount=5000, nav=55.0, units=90.91),
                    Transaction(date=date(2024, 1, 10), type=TransactionType.SIP, amount=5000, nav=60.0, units=83.33),
                ],
            ),
            FundHolding(
                scheme_name="Parag Parikh Flexi Cap Fund - Direct Growth",
                amfi_code="122639",
                folio="87654321",
                category=FundCategory.FLEXI_CAP,
                plan_type=PlanType.DIRECT,
                units=300.0,
                avg_nav=40.0,
                current_nav=68.0,
                invested_value=12_000,
                current_value=20_400,
                expense_ratio=0.63,
            ),
            FundHolding(
                scheme_name="Mirae Asset ELSS Tax Saver - Direct Growth",
                amfi_code="120503",
                folio="11223344",
                category=FundCategory.ELSS,
                plan_type=PlanType.DIRECT,
                units=200.0,
                avg_nav=30.0,
                current_nav=42.0,
                invested_value=6_000,
                current_value=8_400,
                expense_ratio=0.58,
            ),
            FundHolding(
                scheme_name="HDFC Short Term Debt Fund - Regular Growth",
                amfi_code="104482",
                folio="55667788",
                category=FundCategory.DEBT_SHORT,
                plan_type=PlanType.REGULAR,
                units=1000.0,
                avg_nav=25.0,
                current_nav=28.5,
                invested_value=25_000,
                current_value=28_500,
                expense_ratio=1.45,
            ),
            FundHolding(
                scheme_name="SBI Small Cap Fund - Direct Growth",
                amfi_code="125497",
                folio="99887766",
                category=FundCategory.SMALL_CAP,
                plan_type=PlanType.DIRECT,
                units=150.0,
                avg_nav=80.0,
                current_nav=130.0,
                invested_value=12_000,
                current_value=19_500,
                expense_ratio=0.68,
            ),
            FundHolding(
                scheme_name="HDFC Balanced Advantage Fund - Regular Growth",
                amfi_code="100115",
                folio="44332211",
                category=FundCategory.HYBRID_AGGRESSIVE,
                plan_type=PlanType.REGULAR,
                units=400.0,
                avg_nav=35.0,
                current_nav=45.0,
                invested_value=14_000,
                current_value=18_000,
                expense_ratio=1.52,
            ),
        ],
    )


def get_demo_goals() -> list[FinancialGoal]:
    """Sample financial goals for goal planner demo."""
    return [
        FinancialGoal(
            name="Emergency Fund",
            goal_type=GoalType.EMERGENCY_FUND,
            target_amount=500_000,
            target_year=2027,
            current_corpus=150_000,
            monthly_sip=10_000,
            inflation_rate=6.0,
            expected_return=7.0,
            priority=GoalPriority.CRITICAL,
        ),
        FinancialGoal(
            name="Daughter's Education (IIT/IIM)",
            goal_type=GoalType.EDUCATION,
            target_amount=3_000_000,
            target_year=2038,
            current_corpus=200_000,
            monthly_sip=5_000,
            inflation_rate=8.0,
            expected_return=12.0,
            priority=GoalPriority.HIGH,
        ),
        FinancialGoal(
            name="Dream Home Down Payment",
            goal_type=GoalType.HOME,
            target_amount=2_000_000,
            target_year=2030,
            current_corpus=300_000,
            monthly_sip=15_000,
            inflation_rate=6.0,
            expected_return=10.0,
            priority=GoalPriority.HIGH,
        ),
        FinancialGoal(
            name="Europe Family Trip",
            goal_type=GoalType.TRAVEL,
            target_amount=500_000,
            target_year=2028,
            current_corpus=50_000,
            monthly_sip=5_000,
            inflation_rate=6.0,
            expected_return=8.0,
            priority=GoalPriority.LOW,
        ),
        FinancialGoal(
            name="Retirement Corpus",
            goal_type=GoalType.RETIREMENT,
            target_amount=50_000_000,
            target_year=2051,
            current_corpus=500_000,
            monthly_sip=15_000,
            inflation_rate=6.0,
            expected_return=12.0,
            priority=GoalPriority.CRITICAL,
        ),
    ]


def get_demo_life_events() -> list[LifeEvent]:
    """Sample life events for simulator demo."""
    return [
        LifeEvent(
            event_type=LifeEventType.MARRIAGE,
            name="Wedding",
            year=2028,
            month=12,
            one_time_cost=1_500_000,
            monthly_expense_change=10_000,
            duration_months=0,
        ),
        LifeEvent(
            event_type=LifeEventType.CHILD_BIRTH,
            name="First Child",
            year=2030,
            month=6,
            one_time_cost=300_000,
            monthly_expense_change=15_000,
            duration_months=0,
        ),
        LifeEvent(
            event_type=LifeEventType.HOME_PURCHASE,
            name="Buy Apartment",
            year=2031,
            month=1,
            one_time_cost=1_000_000,
            new_emi=45_000,
            monthly_expense_change=5_000,
            duration_months=0,
        ),
    ]


# Quick access dict for API/demo endpoints
DEMO_PROFILES = {
    "young_professional": {
        "name": "Rahul Sharma (28, Bangalore)",
        "description": "Young IT professional, early career, high growth potential",
        "profile": get_demo_profile_young,
    },
    "mid_career": {
        "name": "Priya Mehta (38, Mumbai)",
        "description": "Mid-career manager, growing family, home loan",
        "profile": get_demo_profile_mid,
    },
    "pre_retirement": {
        "name": "Anil Gupta (52, Delhi)",
        "description": "Pre-retirement senior, large corpus, conservative approach",
        "profile": get_demo_profile_senior,
    },
}
