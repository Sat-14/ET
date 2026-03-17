"""FastAPI Main Application for ET Money Mentor.

Provides REST API endpoints for:
- Tax calculation (old vs new regime)
- Money Health Score computation
- Portfolio analysis (XIRR, overlap, behavioral)
- Goal planning and FIRE calculation
- Life-event simulation
- AI chat interface
- WhatsApp webhook
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.models.user import (
    IndividualProfile,
    HouseholdProfile,
    SalaryBreakup,
    Deductions,
    InsuranceCoverage,
    Debt,
    MonthlyExpenses,
    TaxRegime,
    Gender,
    City,
)
from src.models.goals import FinancialGoal, GoalType, GoalPriority, LifeEvent, LifeEventType
from src.models.portfolio import Portfolio

from src.engines.tax_calculator import (
    compute_tax_old_regime,
    compute_tax_new_regime,
    compare_regimes,
    optimize_couple_tax,
)
from src.engines.health_scorer import compute_money_health_score
from src.engines.goal_calculator import (
    plan_goal,
    plan_all_goals,
    calculate_fire,
    monte_carlo_simulation,
    allocate_sip_across_goals,
)
from src.engines.xirr_calculator import (
    compute_portfolio_returns,
    analyze_fund_overlap,
    analyze_expense_ratios,
)
from src.engines.behavioral_detector import (
    run_full_behavioral_analysis,
    generate_behavioral_summary,
)
from src.engines.cashflow_projector import compare_scenarios

from src.agents.supervisor import MoneyMentorSupervisor
from src.utils.language import detect_language, get_language_instruction
from src.utils.whatsapp import WhatsAppClient


# --- Pydantic Request/Response Models ---

class SalaryInput(BaseModel):
    basic: float = 0
    da: float = 0
    hra: float = 0
    special_allowance: float = 0
    lta: float = 0
    medical_allowance: float = 0
    other_allowance: float = 0
    employer_pf: float = 0
    employer_nps: float = 0
    professional_tax: float = 0
    bonus: float = 0


class DeductionInput(BaseModel):
    elss: float = 0
    ppf: float = 0
    lic_premium: float = 0
    home_loan_principal: float = 0
    tuition_fees: float = 0
    employee_pf: float = 0
    nps_additional: float = 0
    self_health_insurance: float = 0
    parents_health_insurance: float = 0
    education_loan_interest: float = 0
    home_loan_interest: float = 0
    rent_paid_annual: float = 0
    donations: float = 0
    savings_interest: float = 0


class ProfileInput(BaseModel):
    name: str = "User"
    age: int = 30
    gender: str = "male"
    city: str = "metro"
    salary: SalaryInput = Field(default_factory=SalaryInput)
    deductions: DeductionInput = Field(default_factory=DeductionInput)
    other_income: float = 0
    emergency_fund: float = 0
    current_investments: float = 0
    monthly_sip: float = 0
    epf_balance: float = 0
    ppf_balance: float = 0
    nps_balance: float = 0
    retirement_age: int = 60
    # Insurance
    life_cover: float = 0
    health_cover: float = 0
    has_critical_illness: bool = False
    # Debt
    home_loan_emi: float = 0
    home_loan_outstanding: float = 0
    car_loan_emi: float = 0
    personal_loan_outstanding: float = 0
    credit_card_outstanding: float = 0
    # Expenses
    monthly_rent: float = 0
    monthly_groceries: float = 0
    monthly_utilities: float = 0
    monthly_transport: float = 0
    monthly_misc: float = 0


class GoalInput(BaseModel):
    name: str
    goal_type: str = "custom"
    target_amount: float
    target_year: int
    current_corpus: float = 0
    monthly_sip: float = 0
    inflation_rate: float = 6.0
    expected_return: float = 12.0
    priority: str = "medium"


class LifeEventInput(BaseModel):
    event_type: str
    name: str
    year: int
    month: int = 1
    one_time_cost: float = 0
    monthly_income_change: float = 0
    monthly_expense_change: float = 0
    duration_months: int = 0
    new_emi: float = 0


class ChatInput(BaseModel):
    message: str
    session_id: Optional[str] = None


class FIREInput(BaseModel):
    current_age: int = 30
    annual_expenses: float = 600000
    current_corpus: float = 0
    monthly_investment: float = 30000
    expected_return: float = 0.10
    inflation_rate: float = 0.06
    safe_withdrawal_rate: float = 0.04


# --- Helper: Convert Pydantic input to dataclass ---

def _build_profile(data: ProfileInput) -> IndividualProfile:
    sal = SalaryBreakup(
        basic=data.salary.basic, da=data.salary.da, hra=data.salary.hra,
        special_allowance=data.salary.special_allowance, lta=data.salary.lta,
        medical_allowance=data.salary.medical_allowance,
        other_allowance=data.salary.other_allowance,
        employer_pf=data.salary.employer_pf, employer_nps=data.salary.employer_nps,
        professional_tax=data.salary.professional_tax, bonus=data.salary.bonus,
    )
    ded = Deductions(
        elss=data.deductions.elss, ppf=data.deductions.ppf,
        lic_premium=data.deductions.lic_premium,
        home_loan_principal=data.deductions.home_loan_principal,
        tuition_fees=data.deductions.tuition_fees,
        employee_pf=data.deductions.employee_pf,
        nps_additional=data.deductions.nps_additional,
        self_health_insurance=data.deductions.self_health_insurance,
        parents_health_insurance=data.deductions.parents_health_insurance,
        education_loan_interest=data.deductions.education_loan_interest,
        home_loan_interest=data.deductions.home_loan_interest,
        rent_paid_annual=data.deductions.rent_paid_annual,
        donations=data.deductions.donations,
        savings_interest=data.deductions.savings_interest,
    )
    ins = InsuranceCoverage(
        life_cover=data.life_cover, health_cover=data.health_cover,
        has_critical_illness=data.has_critical_illness,
    )
    debt = Debt(
        home_loan_emi=data.home_loan_emi,
        home_loan_outstanding=data.home_loan_outstanding,
        car_loan_emi=data.car_loan_emi,
        personal_loan_outstanding=data.personal_loan_outstanding,
        credit_card_outstanding=data.credit_card_outstanding,
    )
    expenses = MonthlyExpenses(
        rent=data.monthly_rent, groceries=data.monthly_groceries,
        utilities=data.monthly_utilities, transportation=data.monthly_transport,
        misc=data.monthly_misc,
    )
    return IndividualProfile(
        name=data.name, age=data.age,
        gender=Gender(data.gender), city=City(data.city),
        salary=sal, deductions=ded, insurance=ins, debt=debt,
        monthly_expenses=expenses, emergency_fund=data.emergency_fund,
        current_investments=data.current_investments,
        monthly_sip=data.monthly_sip,
        epf_balance=data.epf_balance, ppf_balance=data.ppf_balance,
        nps_balance=data.nps_balance, other_income=data.other_income,
        retirement_age=data.retirement_age,
    )


# --- App Setup ---

chat_sessions: dict[str, MoneyMentorSupervisor] = {}

app = FastAPI(
    title="ET Money Mentor API",
    description="AI-Powered Personal Finance Assistant for India",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health Check ---

@app.get("/")
def root():
    return {
        "name": "ET Money Mentor",
        "version": "1.0.0",
        "status": "running",
        "endpoints": [
            "/tax/compare", "/health-score", "/goals/plan",
            "/fire", "/portfolio/returns", "/simulate",
            "/chat",
        ],
    }


# --- Tax Endpoints ---

@app.post("/tax/compare")
def tax_compare(profile: ProfileInput):
    """Compare old vs new regime and recommend best option."""
    p = _build_profile(profile)
    result = compare_regimes(p)
    return result.to_dict()


@app.post("/tax/old-regime")
def tax_old(profile: ProfileInput):
    """Compute tax under old regime."""
    p = _build_profile(profile)
    result = compute_tax_old_regime(p)
    return result.to_dict()


@app.post("/tax/new-regime")
def tax_new(profile: ProfileInput):
    """Compute tax under new regime."""
    p = _build_profile(profile)
    result = compute_tax_new_regime(p)
    return result.to_dict()


# --- Health Score ---

@app.post("/health-score")
def health_score(profile: ProfileInput):
    """Compute Money Health Score (0-100) across 6 dimensions."""
    p = _build_profile(profile)
    report = compute_money_health_score(p)
    return report.to_dict()


# --- Goal Planning ---

@app.post("/goals/plan")
def plan_goals(goals: list[GoalInput]):
    """Plan all financial goals with SIP requirements."""
    goal_list = []
    for g in goals:
        goal_list.append(FinancialGoal(
            name=g.name,
            goal_type=GoalType(g.goal_type) if g.goal_type in GoalType.__members__.values() else GoalType.CUSTOM,
            target_amount=g.target_amount,
            target_year=g.target_year,
            current_corpus=g.current_corpus,
            monthly_sip=g.monthly_sip,
            inflation_rate=g.inflation_rate,
            expected_return=g.expected_return,
            priority=GoalPriority(g.priority) if g.priority in GoalPriority.__members__.values() else GoalPriority.MEDIUM,
        ))
    plans = plan_all_goals(goal_list)
    return [p.to_dict() for p in plans]


@app.post("/fire")
def fire_calculator(data: FIREInput):
    """Calculate FIRE number and timeline."""
    result = calculate_fire(
        current_age=data.current_age,
        annual_expenses=data.annual_expenses,
        current_corpus=data.current_corpus,
        monthly_investment=data.monthly_investment,
        expected_return=data.expected_return,
        inflation_rate=data.inflation_rate,
        safe_withdrawal_rate=data.safe_withdrawal_rate,
    )
    return result.to_dict()


@app.post("/goals/allocate")
def allocate_sips(goals: list[GoalInput], total_sip: float = Query(...)):
    """Allocate available SIP budget across goals by priority."""
    goal_list = [
        FinancialGoal(
            name=g.name,
            goal_type=GoalType.CUSTOM,
            target_amount=g.target_amount,
            target_year=g.target_year,
            current_corpus=g.current_corpus,
            monthly_sip=g.monthly_sip,
            inflation_rate=g.inflation_rate,
            expected_return=g.expected_return,
            priority=GoalPriority(g.priority) if g.priority in GoalPriority.__members__.values() else GoalPriority.MEDIUM,
        )
        for g in goals
    ]
    return allocate_sip_across_goals(goal_list, total_sip)


@app.post("/monte-carlo")
def run_monte_carlo(
    current_corpus: float = 0,
    monthly_sip: float = 10000,
    years: int = 10,
    target_amount: float = 10000000,
    simulations: int = 5000,
):
    """Run Monte Carlo simulation for goal achievement probability."""
    result = monte_carlo_simulation(
        current_corpus=current_corpus,
        monthly_sip=monthly_sip,
        years=years,
        target_amount=target_amount,
        num_simulations=simulations,
    )
    return result.to_dict()


# --- Life Event Simulation ---

@app.post("/simulate")
def simulate_life_events(profile: ProfileInput, events: list[LifeEventInput], years: int = 10):
    """Simulate life events and compare with baseline."""
    p = _build_profile(profile)
    event_list = [
        LifeEvent(
            event_type=LifeEventType(e.event_type) if e.event_type in [t.value for t in LifeEventType] else LifeEventType.SALARY_HIKE,
            name=e.name,
            year=e.year,
            month=e.month,
            one_time_cost=e.one_time_cost,
            monthly_income_change=e.monthly_income_change,
            monthly_expense_change=e.monthly_expense_change,
            duration_months=e.duration_months,
            new_emi=e.new_emi,
        )
        for e in events
    ]
    result = compare_scenarios(p, event_list, years=years)
    return result.to_dict()


# --- AI Chat ---

@app.post("/chat")
async def chat(data: ChatInput):
    """Chat with the Money Mentor AI."""
    session_id = data.session_id or "default"

    if session_id not in chat_sessions:
        chat_sessions[session_id] = MoneyMentorSupervisor()

    supervisor = chat_sessions[session_id]

    # Detect language
    lang = detect_language(data.message)
    lang_instruction = get_language_instruction(lang)

    response = await supervisor.chat(data.message)

    return {
        "response": response,
        "agent": supervisor.get_current_agent(),
        "language": lang,
        "session_id": session_id,
    }


# --- WhatsApp Webhook ---

@app.get("/webhook")
def verify_webhook(request: Request):
    """Verify WhatsApp webhook subscription."""
    params = dict(request.query_params)
    verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "money_mentor_verify")
    challenge = WhatsAppClient.verify_webhook(params, verify_token)
    if challenge:
        return int(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def handle_webhook(request: Request):
    """Handle incoming WhatsApp messages."""
    payload = await request.json()
    message_data = WhatsAppClient.parse_webhook_message(payload)

    if not message_data or not message_data.get("message_text"):
        return {"status": "ok"}

    sender = message_data["sender"]
    text = message_data["message_text"]

    # Get or create session
    if sender not in chat_sessions:
        chat_sessions[sender] = MoneyMentorSupervisor()

    supervisor = chat_sessions[sender]
    response = await supervisor.chat(text)

    # Send response back via WhatsApp
    wa_client = WhatsAppClient()
    await wa_client.send_text_message(sender, response)

    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
