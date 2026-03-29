"""Streamlit Dashboard for ET Money Mentor.

A comprehensive financial dashboard with:
- AI Chat interface
- Money Health Score visualization
- Tax comparison (old vs new regime)
- Goal planner & FIRE calculator
- EMI & Loan optimizer
- Insurance needs analyzer
- Retirement (SWP) planner
- Life-event simulator
- PDF report downloads
"""

import sys
import os
import asyncio
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import plotly.graph_objects as go

from src.models.user import (
    IndividualProfile, SalaryBreakup, Deductions, InsuranceCoverage,
    Debt, MonthlyExpenses, Gender, City,
)
from src.models.goals import FinancialGoal, GoalType, GoalPriority, LifeEvent, LifeEventType, LIFE_EVENT_TEMPLATES

from src.engines.tax_calculator import (
    compare_regimes,
    optimize_couple_tax,
    recommend_tax_saving_options,
)
from src.engines.health_scorer import compute_money_health_score
from src.engines.goal_calculator import plan_all_goals, calculate_fire, monte_carlo_simulation
from src.engines.fire_path_planner import build_fire_master_plan
from src.engines.cashflow_projector import compare_scenarios, analyze_life_event_advisor
from src.engines.emi_calculator import calculate_emi, analyze_prepayment, prepay_vs_invest
from src.engines.insurance_calculator import calculate_life_insurance_need, calculate_health_insurance_need
from src.engines.swp_calculator import calculate_swp, calculate_safe_withdrawal, create_bucket_strategy
from src.engines.report_generator import generate_health_score_pdf, generate_full_report_pdf
from src.engines.investment_screener import (
    search_mutual_funds, get_fund_details, suggest_asset_allocation, screen_stocks,
    MF_CATEGORIES,
)
from src.engines.xirr_calculator import (
    compute_portfolio_returns,
    analyze_fund_overlap,
    analyze_expense_ratios,
    analyze_benchmark_comparison,
)
from src.engines.behavioral_detector import run_full_behavioral_analysis, generate_behavioral_summary
from src.engines.rebalancer import generate_rebalance_plan
from src.models.user import HouseholdProfile
from src.agents.supervisor import MoneyMentorSupervisor
from src.utils.language import format_indian_number
from src.demo_data import DEMO_PROFILES, get_demo_goals, get_demo_couple, get_demo_portfolio
from src.parsers.form16_parser import parse_form16_pdf, merge_form16_into_profile
from src.parsers.cas_parser import parse_cas_pdf


# --- Page Config ---
st.set_page_config(
    page_title="ET Money Mentor",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Session State Init ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "supervisor" not in st.session_state:
    st.session_state.supervisor = MoneyMentorSupervisor()
if "planned_goals" not in st.session_state:
    st.session_state.planned_goals = get_demo_goals()


def _profile_context_summary(profile: IndividualProfile, health_report) -> dict:
    """Compact user profile summary for AI context."""
    return {
        "name": profile.name,
        "age": profile.age,
        "city": profile.city.value,
        "annual_income": round(profile.annual_income),
        "monthly_expenses": round(profile.monthly_expenses.total),
        "emergency_fund": round(profile.emergency_fund),
        "current_investments": round(profile.current_investments),
        "monthly_sip": round(profile.monthly_sip),
        "life_cover": round(profile.insurance.life_cover),
        "health_cover": round(profile.insurance.health_cover),
        "total_debt": round(profile.debt.total_outstanding),
        "health_score": health_report.to_dict(),
    }


def _portfolio_context_summary(portfolio) -> dict:
    """Compact portfolio summary for AI context."""
    return {
        "investor_name": portfolio.investor_name,
        "num_funds": portfolio.num_funds,
        "total_invested": round(portfolio.total_invested),
        "total_current_value": round(portfolio.total_current_value),
        "total_gain": round(portfolio.total_gain),
        "category_allocation": {
            category.value: round(pct, 1)
            for category, pct in portfolio.category_allocation().items()
        },
    }


def build_profile_from_sidebar() -> IndividualProfile:
    """Build user profile from sidebar inputs."""
    st.sidebar.header("Your Profile")

    # Demo profile quick-load
    sidebar_demo_profiles = [
        demo_key for demo_key in DEMO_PROFILES.keys()
        if demo_key != "couple"
    ]
    demo_choice = st.sidebar.selectbox(
        "Quick Load Demo Profile",
        ["Custom"] + sidebar_demo_profiles,
        format_func=lambda x: DEMO_PROFILES[x]["name"] if x in DEMO_PROFILES else "Enter Custom Values",
    )
    if demo_choice in DEMO_PROFILES:
        return DEMO_PROFILES[demo_choice]["profile"]()

    name = st.sidebar.text_input("Name", "User")
    age = st.sidebar.number_input("Age", 18, 80, 30)
    city = st.sidebar.selectbox("City Type", ["metro", "non_metro"])

    st.sidebar.subheader("Annual Salary Breakup")
    basic = st.sidebar.number_input("Basic (Annual)", 0, 50_000_000, 600_000, step=50_000)
    hra = st.sidebar.number_input("HRA (Annual)", 0, 20_000_000, 240_000, step=10_000)
    special = st.sidebar.number_input("Special Allowance (Annual)", 0, 20_000_000, 360_000, step=10_000)
    employer_pf = st.sidebar.number_input("Employer PF (Annual)", 0, 5_000_000, 72_000, step=5_000)
    employer_nps = st.sidebar.number_input("Employer NPS (Annual)", 0, 5_000_000, 0, step=5_000)
    bonus = st.sidebar.number_input("Bonus (Annual)", 0, 10_000_000, 0, step=50_000)

    st.sidebar.subheader("Deductions (Annual)")
    epf = st.sidebar.number_input("Employee PF", 0, 500_000, 72_000, step=5_000)
    ppf_val = st.sidebar.number_input("PPF", 0, 150_000, 0, step=5_000)
    elss_val = st.sidebar.number_input("ELSS", 0, 150_000, 0, step=5_000)
    lic = st.sidebar.number_input("LIC Premium", 0, 500_000, 0, step=5_000)
    nps_extra = st.sidebar.number_input("NPS 80CCD(1B)", 0, 50_000, 0, step=5_000)
    health_self = st.sidebar.number_input("Health Insurance (Self)", 0, 25_000, 0, step=1_000)
    health_parents = st.sidebar.number_input("Health Insurance (Parents)", 0, 50_000, 0, step=1_000)
    home_interest = st.sidebar.number_input("Home Loan Interest", 0, 500_000, 0, step=10_000)
    rent_annual = st.sidebar.number_input("Rent Paid (Annual)", 0, 5_000_000, 0, step=10_000)

    st.sidebar.subheader("Monthly Expenses")
    rent_m = st.sidebar.number_input("Rent/EMI", 0, 500_000, 25_000, step=1_000)
    groceries = st.sidebar.number_input("Groceries", 0, 100_000, 10_000, step=500)
    utilities = st.sidebar.number_input("Utilities", 0, 50_000, 5_000, step=500)
    transport = st.sidebar.number_input("Transport", 0, 50_000, 5_000, step=500)
    misc = st.sidebar.number_input("Miscellaneous", 0, 200_000, 10_000, step=1_000)

    st.sidebar.subheader("Investments & Insurance")
    emergency_fund = st.sidebar.number_input("Emergency Fund", 0, 50_000_000, 200_000, step=50_000)
    investments = st.sidebar.number_input("Total Investments", 0, 100_000_000, 500_000, step=50_000)
    monthly_sip = st.sidebar.number_input("Monthly SIP", 0, 1_000_000, 15_000, step=1_000)
    life_cover = st.sidebar.number_input("Life Cover", 0, 100_000_000, 0, step=500_000)
    health_cover = st.sidebar.number_input("Health Cover", 0, 50_000_000, 500_000, step=100_000)

    salary = SalaryBreakup(
        basic=basic, hra=hra, special_allowance=special,
        employer_pf=employer_pf, employer_nps=employer_nps, bonus=bonus,
    )
    deductions = Deductions(
        employee_pf=epf, ppf=ppf_val, elss=elss_val, lic_premium=lic,
        nps_additional=nps_extra, self_health_insurance=health_self,
        parents_health_insurance=health_parents, home_loan_interest=home_interest,
        rent_paid_annual=rent_annual,
    )
    insurance = InsuranceCoverage(life_cover=life_cover, health_cover=health_cover)
    expenses = MonthlyExpenses(
        rent=rent_m, groceries=groceries, utilities=utilities,
        transportation=transport, misc=misc,
    )

    return IndividualProfile(
        name=name, age=age, city=City(city),
        salary=salary, deductions=deductions, insurance=insurance,
        monthly_expenses=expenses, emergency_fund=emergency_fund,
        current_investments=investments, monthly_sip=monthly_sip,
    )


def render_health_score(profile: IndividualProfile):
    """Render Money Health Score section."""
    st.header("Money Health Score")

    portfolio = st.session_state.get("portfolio")
    report = compute_money_health_score(profile, portfolio)
    if portfolio and portfolio.holdings:
        st.caption(
            f"Using live portfolio data from Portfolio X-Ray: {portfolio.num_funds} funds included in diversification scoring."
        )
    else:
        st.caption("Diversification score improves when you load a portfolio in the Portfolio X-Ray tab.")

    # Overall score with color
    score = report.overall_score
    color = "#4CAF50" if score >= 70 else "#FF9800" if score >= 40 else "#f44336"

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=score,
            title={"text": f"Overall Grade: {report.overall_grade}"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 25], "color": "#ffebee"},
                    {"range": [25, 50], "color": "#fff3e0"},
                    {"range": [50, 75], "color": "#e8f5e9"},
                    {"range": [75, 100], "color": "#c8e6c9"},
                ],
            },
        ))
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    # Radar chart
    categories = [d.name for d in report.dimensions]
    values = [d.pct for d in report.dimensions]

    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill="toself",
        name="Your Score",
        line_color="#2196F3",
    ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False, height=400,
        title="Score Breakdown by Dimension",
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    # Dimension details
    cols = st.columns(3)
    for i, dim in enumerate(report.dimensions):
        with cols[i % 3]:
            emoji = "🟢" if dim.pct >= 70 else "🟡" if dim.pct >= 40 else "🔴"
            st.metric(
                label=f"{emoji} {dim.name}",
                value=f"{dim.score:.0f}/{dim.max_score:.0f}",
                delta=f"Grade: {dim.grade}",
            )
            st.caption(dim.details)
            if dim.recommendations:
                for rec in dim.recommendations:
                    st.info(f"-> {rec}")

    # Top actions
    st.subheader("Top 3 Actions to Improve Your Score")
    for i, action in enumerate(report.top_actions, 1):
        st.warning(f"**{i}.** {action}")

    # Download PDF
    pdf_bytes = generate_health_score_pdf(report.to_dict())
    st.download_button(
        "Download Health Score PDF",
        data=pdf_bytes,
        file_name="health_score_report.pdf",
        mime="application/pdf",
    )


def render_tax_comparison(profile: IndividualProfile):
    """Render tax comparison section."""
    st.header("Tax Wizard - Old vs New Regime")

    pref_col1, pref_col2 = st.columns(2)
    with pref_col1:
        risk_profile = st.selectbox(
            "Risk Profile for Tax-Saving Ideas",
            ["conservative", "moderate", "aggressive"],
            index=1,
            key="tax_risk_pref",
        )
    with pref_col2:
        liquidity_need = st.selectbox(
            "Liquidity Need",
            ["high", "medium", "low"],
            index=1,
            key="tax_liquidity_pref",
        )

    tab_manual, tab_form16 = st.tabs(["Manual Entry", "Upload Form-16"])

    with tab_manual:
        _render_tax_comparison_result(profile, risk_profile, liquidity_need)

    with tab_form16:
        st.caption("Upload a Form-16 PDF to prefill salary and deductions, then compare regimes instantly.")
        uploaded_file = st.file_uploader(
            "Upload Form-16 PDF",
            type=["pdf"],
            key="tax_form16_upload",
        )

        if uploaded_file is not None:
            suffix = os.path.splitext(uploaded_file.name)[1] or ".pdf"
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getbuffer())
                    temp_path = tmp.name

                parsed = parse_form16_pdf(temp_path)
                form16_profile = merge_form16_into_profile(parsed, base_profile=profile)

                st.success(f"Parsed {uploaded_file.name}")
                col1, col2, col3 = st.columns(3)
                col1.metric("Gross Salary", format_indian_number(parsed.get("gross_salary", 0)))
                col2.metric("Taxable Income", format_indian_number(parsed.get("taxable_income", 0)))
                col3.metric("TDS Deducted", format_indian_number(parsed.get("tds_deducted", 0)))

                extracted_deductions = parsed.get("deductions", {})
                if extracted_deductions:
                    st.subheader("Extracted Deductions")
                    ded_cols = st.columns(3)
                    ded_items = [
                        ("80C", extracted_deductions.get("80C", 0)),
                        ("80CCD(1B)", extracted_deductions.get("80CCD_1B", 0)),
                        ("80D", extracted_deductions.get("80D", 0)),
                        ("24(b)", extracted_deductions.get("24b", 0)),
                        ("80E", extracted_deductions.get("80E", 0)),
                        ("80G", extracted_deductions.get("80G", 0)),
                    ]
                    for idx, (label, value) in enumerate(ded_items):
                        with ded_cols[idx % 3]:
                            st.metric(label, format_indian_number(value))

                st.info(
                    "Using Form-16 for salary and deductions. City, other income, and the rest of your profile "
                    "still come from the sidebar, so you can refine the result if needed."
                )
                _render_tax_comparison_result(form16_profile, risk_profile, liquidity_need)
            except ImportError as exc:
                st.error(str(exc))
            except ValueError as exc:
                st.error(str(exc))
            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass


def _render_tax_comparison_result(
    profile: IndividualProfile,
    risk_profile: str = "moderate",
    liquidity_need: str = "medium",
):
    """Render tax comparison metrics for a fully built profile."""

    comp = compare_regimes(profile)
    old = comp.old_regime
    new = comp.new_regime

    if comp.recommended_regime.value == "old":
        st.success(f"**Old Regime is better!** You save {format_indian_number(comp.tax_saving)}/year")
    else:
        st.success(f"**New Regime is better!** You save {format_indian_number(comp.tax_saving)}/year")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Old Regime")
        st.metric("Gross Income", format_indian_number(old.gross_income))
        st.metric("Total Deductions", format_indian_number(old.total_deductions))
        st.metric("Taxable Income", format_indian_number(old.taxable_income))
        st.metric("Total Tax", format_indian_number(old.total_tax))
        st.metric("Effective Rate", f"{old.effective_rate:.1f}%")
        st.metric("Monthly In-Hand", format_indian_number(old.monthly_in_hand))

    with col2:
        st.subheader("New Regime")
        st.metric("Gross Income", format_indian_number(new.gross_income))
        st.metric("Total Deductions", format_indian_number(new.total_deductions))
        st.metric("Taxable Income", format_indian_number(new.taxable_income))
        st.metric("Total Tax", format_indian_number(new.total_tax))
        st.metric("Effective Rate", f"{new.effective_rate:.1f}%")
        st.metric("Monthly In-Hand", format_indian_number(new.monthly_in_hand))

    fig = go.Figure(data=[
        go.Bar(name="Old Regime", x=["Tax", "In-Hand (Monthly)"], y=[old.total_tax, old.monthly_in_hand], marker_color="#FF6B6B"),
        go.Bar(name="New Regime", x=["Tax", "In-Hand (Monthly)"], y=[new.total_tax, new.monthly_in_hand], marker_color="#4ECDC4"),
    ])
    fig.update_layout(barmode="group", title="Tax Comparison", height=400)
    st.plotly_chart(fig, use_container_width=True)

    if comp.unused_deduction_room:
        st.subheader("Unused Deduction Room (Old Regime)")
        for section, amount in comp.unused_deduction_room.items():
            st.warning(f"**{section}:** {format_indian_number(amount)} unused - invest to save tax!")

    recommendations = recommend_tax_saving_options(
        profile,
        risk_profile=risk_profile,
        liquidity_need=liquidity_need,
    )
    if recommendations:
        st.subheader("Ranked Tax-Saving Options")
        st.caption(
            f"Ranked for a {risk_profile} investor with {liquidity_need} liquidity need."
        )
        for option in recommendations[:5]:
            st.write(
                f"**#{option['rank']} {option['name']}** | "
                f"{option['section']} | "
                f"Suggested: {format_indian_number(option['suggested_amount'])}"
            )
            st.caption(
                f"Risk: {option['risk_level']} | Liquidity: {option['liquidity']} | Lock-in: {option['lock_in']}"
            )
            st.info(option["rationale"])
            for note in option["notes"]:
                st.write(f"  - {note}")


def render_goal_planner(profile: IndividualProfile):
    """Render goal planner section."""
    st.header("Goal Planner")

    use_demo = st.checkbox("Load demo goals", value=True)

    if use_demo:
        goals = get_demo_goals()
    else:
        num_goals = st.number_input("Number of goals", 1, 10, 3)
        goals = []
        for i in range(num_goals):
            with st.expander(f"Goal {i + 1}", expanded=(i == 0)):
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input("Goal Name", f"Goal {i + 1}", key=f"goal_name_{i}")
                    target = st.number_input("Target Amount (today's value)", 100_000, 100_000_000, 2_000_000, step=100_000, key=f"goal_target_{i}")
                    target_year = st.number_input("Target Year", 2026, 2060, 2035, key=f"goal_year_{i}")
                with col2:
                    corpus = st.number_input("Already Saved", 0, 100_000_000, 0, step=50_000, key=f"goal_corpus_{i}")
                    sip = st.number_input("Current Monthly SIP", 0, 500_000, 0, step=1_000, key=f"goal_sip_{i}")
                    priority = st.selectbox("Priority", ["critical", "high", "medium", "low"], index=2, key=f"goal_priority_{i}")

                goals.append(FinancialGoal(
                    name=name, goal_type=GoalType.CUSTOM, target_amount=target,
                    target_year=target_year, current_corpus=corpus, monthly_sip=sip,
                    priority=GoalPriority(priority),
                ))

    st.session_state.planned_goals = goals

    if st.button("Plan Goals", type="primary"):
        plans = plan_all_goals(goals)

        for plan in plans:
            status = "On Track" if plan.on_track else "Needs Attention"
            status_icon = "🟢" if plan.on_track else "🔴"
            st.subheader(f"{plan.goal.name} {status_icon} {status}")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Target (Inflation Adj)", format_indian_number(plan.inflation_adjusted_target))
            col2.metric("Gap", format_indian_number(plan.gap))
            col3.metric("Required SIP", format_indian_number(plan.required_monthly_sip) + "/mo")
            col4.metric("Progress", f"{plan.progress_pct:.0f}%")

            st.progress(min(plan.progress_pct / 100, 1.0))
            st.caption(f"Suggested: {plan.suggested_asset_class}")

            for note in plan.notes:
                st.info(f"-> {note}")


def render_fire_calculator(profile: IndividualProfile):
    """Render FIRE calculator and unified FIRE planner."""
    st.header("FIRE Calculator")

    tab_quick, tab_master = st.tabs(["Quick Calculator", "Unified Master Plan"])

    with tab_quick:
        col1, col2 = st.columns(2)
        with col1:
            current_age = st.number_input("Current Age", 18, 70, int(profile.age), key="quick_fire_age")
            annual_exp = st.number_input(
                "Annual Expenses",
                100_000,
                50_000_000,
                int(profile.monthly_expenses.total * 12),
                step=50_000,
                key="quick_fire_expenses",
            )
            corpus = st.number_input(
                "Current Investment Corpus",
                0,
                100_000_000,
                int(profile.current_investments + profile.total_retirement_corpus),
                step=100_000,
                key="quick_fire_corpus",
            )
        with col2:
            monthly_inv = st.number_input(
                "Monthly Investment",
                0,
                1_000_000,
                int(max(profile.monthly_sip, 10_000)),
                step=5_000,
                key="quick_fire_monthly",
            )
            exp_return = st.slider("Expected Return (%)", 6.0, 18.0, 10.0, 0.5, key="quick_fire_return") / 100
            inflation = st.slider("Inflation (%)", 3.0, 10.0, 6.0, 0.5, key="quick_fire_inflation") / 100

        if st.button("Calculate FIRE", type="primary", key="quick_fire_btn"):
            result = calculate_fire(
                current_age=current_age,
                annual_expenses=annual_exp,
                current_corpus=corpus,
                monthly_investment=monthly_inv,
                expected_return=exp_return,
                inflation_rate=inflation,
            )

            col1, col2, col3 = st.columns(3)
            col1.metric("FIRE Number", format_indian_number(result.fire_number))
            col2.metric("Years to FIRE", f"{result.years_to_fire:.0f}")
            col3.metric("FIRE Age", str(result.projected_fire_age))

            st.metric("Savings Rate", f"{result.current_savings_rate:.0f}%")
            st.metric("Annual Passive Income at FIRE", format_indian_number(result.annual_passive_income))

            st.subheader("Monte Carlo Simulation (5000 scenarios)")
            mc = monte_carlo_simulation(
                current_corpus=corpus,
                monthly_sip=monthly_inv,
                years=int(result.years_to_fire),
                target_amount=result.fire_number,
            )
            st.metric("Success Probability", f"{mc.success_probability:.0f}%")
            col1, col2, col3 = st.columns(3)
            col1.metric("Pessimistic (P10)", format_indian_number(mc.p10_outcome))
            col2.metric("Median", format_indian_number(mc.median_outcome))
            col3.metric("Optimistic (P90)", format_indian_number(mc.p90_outcome))

    with tab_master:
        goals = st.session_state.get("planned_goals", [])
        portfolio = st.session_state.get("portfolio")
        st.caption(
            f"Using your current sidebar profile, {len(goals)} goal(s) from Goal Planner, "
            f"and {'loaded portfolio data' if portfolio is not None else 'no portfolio upload yet'}."
        )

        mcol1, mcol2, mcol3 = st.columns(3)
        with mcol1:
            master_return = st.slider("Planner Return (%)", 6.0, 18.0, 10.0, 0.5, key="master_fire_return") / 100
        with mcol2:
            master_inflation = st.slider("Planner Inflation (%)", 3.0, 10.0, 6.0, 0.5, key="master_fire_inflation") / 100
        with mcol3:
            horizon_months = st.slider("Roadmap Horizon (months)", 24, 360, 120, 12, key="master_fire_horizon")

        growth_col1, growth_col2 = st.columns(2)
        with growth_col1:
            income_growth = st.slider("Annual Income Growth (%)", 0.0, 15.0, 8.0, 0.5, key="master_fire_income") / 100
        with growth_col2:
            expense_growth = st.slider("Annual Expense Inflation (%)", 0.0, 12.0, 6.0, 0.5, key="master_fire_expense") / 100

        if st.button("Build FIRE Master Plan", type="primary", key="master_fire_btn"):
            plan = build_fire_master_plan(
                profile,
                goals,
                portfolio,
                expected_return=master_return,
                inflation_rate=master_inflation,
                annual_income_growth=income_growth,
                annual_expense_inflation=expense_growth,
                horizon_months=horizon_months,
            )

            summary = plan["summary"]
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("FIRE Number", format_indian_number(summary["fire_number"]))
            s2.metric("FIRE Age", str(summary["projected_fire_age"]))
            s3.metric("Monthly FIRE Bucket", format_indian_number(summary["fire_bucket_sip"]))
            s4.metric("Health Score", f"{summary['health_score']:.1f}/100")

            risk1, risk2, risk3 = st.columns(3)
            risk1.metric("Emergency Gap", format_indian_number(summary["emergency_fund_gap"]))
            risk2.metric("Life Cover Gap", format_indian_number(summary["life_cover_gap"]))
            risk3.metric("Health Cover Gap", format_indian_number(summary["health_cover_gap"]))

            if plan["primary_actions"]:
                st.subheader("Primary Actions")
                for action in plan["primary_actions"]:
                    st.warning(action)

            if plan["goal_sip_allocation"]:
                st.subheader("Goal SIP Split")
                goal_rows = [
                    {"goal_name": name, "monthly_sip": amount}
                    for name, amount in plan["goal_sip_allocation"].items()
                ]
                st.dataframe(goal_rows, use_container_width=True)

            st.subheader("Month-by-Month Roadmap")
            st.dataframe(plan["roadmap"][:24], use_container_width=True)
            if len(plan["roadmap"]) > 24:
                st.caption(
                    f"Showing the first 24 months of a {plan['roadmap_months']}-month roadmap."
                )


def render_emi_calculator():
    """Render EMI & Loan optimizer."""
    st.header("EMI & Loan Optimizer")

    tab_emi, tab_prepay, tab_compare = st.tabs(["EMI Calculator", "Prepay vs Invest", "Compare Loans"])

    with tab_emi:
        col1, col2, col3 = st.columns(3)
        with col1:
            principal = st.number_input("Loan Amount", 100_000, 100_000_000, 5_000_000, step=100_000)
        with col2:
            rate = st.number_input("Interest Rate (%)", 1.0, 25.0, 8.5, step=0.1)
        with col3:
            tenure_yrs = st.number_input("Tenure (years)", 1, 30, 20)

        if st.button("Calculate EMI", type="primary"):
            result = calculate_emi(principal, rate, tenure_yrs * 12)
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Monthly EMI", format_indian_number(result.monthly_emi))
            col2.metric("Total Payment", format_indian_number(result.total_payment))
            col3.metric("Total Interest", format_indian_number(result.total_interest))
            col4.metric("Interest/Principal", f"{result.interest_to_principal_ratio:.2f}x")

            fig = go.Figure(data=[go.Pie(
                labels=["Principal", "Interest"],
                values=[principal, result.total_interest],
                marker_colors=["#4ECDC4", "#FF6B6B"],
                hole=0.4,
            )])
            fig.update_layout(title="Payment Breakdown", height=350)
            st.plotly_chart(fig, use_container_width=True)

    with tab_prepay:
        col1, col2 = st.columns(2)
        with col1:
            pp_principal = st.number_input("Loan Outstanding", 100_000, 100_000_000, 4_000_000, step=100_000, key="pp_p")
            pp_rate = st.number_input("Loan Rate (%)", 1.0, 25.0, 8.5, step=0.1, key="pp_r")
            pp_tenure = st.number_input("Remaining Tenure (months)", 12, 360, 180, key="pp_t")
        with col2:
            pp_amount = st.number_input("Lump Sum Available", 50_000, 50_000_000, 500_000, step=50_000)
            inv_return = st.number_input("Expected Investment Return (%)", 5.0, 20.0, 12.0, step=0.5)
            tax_ben = st.checkbox("Home Loan Tax Benefit (Sec 24b)?", value=True)

        if st.button("Analyze", type="primary", key="prepay_btn"):
            result = prepay_vs_invest(pp_principal, pp_rate, pp_tenure, pp_amount, inv_return, tax_benefit=tax_ben)

            if result.recommendation == "invest":
                st.success(f"**Invest the money!** Net benefit: {format_indian_number(result.net_benefit)}")
            else:
                st.success(f"**Prepay the loan!** Net benefit: {format_indian_number(result.net_benefit)}")

            col1, col2 = st.columns(2)
            col1.metric("Interest Saved by Prepaying", format_indian_number(result.prepay_interest_saved))
            col2.metric("Expected Investment Return", format_indian_number(result.invest_expected_return))

            st.info(result.details)

    with tab_compare:
        st.write("Compare loan offers from different banks")
        loan_amt = st.number_input("Loan Amount", 100_000, 100_000_000, 5_000_000, step=100_000, key="cmp_amt")

        offers_data = []
        for i in range(3):
            with st.expander(f"Offer {i+1}", expanded=(i < 2)):
                bank = st.text_input("Bank Name", ["SBI", "HDFC", "ICICI"][i], key=f"bank_{i}")
                o_rate = st.number_input("Rate (%)", 6.0, 15.0, [8.4, 8.75, 9.0][i], step=0.05, key=f"cmp_rate_{i}")
                o_tenure = st.number_input("Tenure (months)", 60, 360, 240, key=f"cmp_tenure_{i}")
                o_fee = st.number_input("Processing Fee", 0, 500_000, [10000, 15000, 12000][i], step=1_000, key=f"cmp_fee_{i}")
                offers_data.append({"bank": bank, "rate": o_rate, "tenure_months": o_tenure, "processing_fee": o_fee})

        if st.button("Compare Offers", type="primary", key="cmp_btn"):
            from src.engines.emi_calculator import compare_loan_offers
            results = compare_loan_offers(loan_amt, offers_data)
            for i, r in enumerate(results):
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else ""
                st.subheader(f"{medal} {r['bank']}")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Rate", f"{r['rate']}%")
                col2.metric("Monthly EMI", format_indian_number(r['monthly_emi']))
                col3.metric("Total Interest", format_indian_number(r['total_interest']))
                col4.metric("Total Cost", format_indian_number(r['total_cost']))
                if r.get("savings_vs_worst"):
                    st.caption(f"Saves {format_indian_number(r['savings_vs_worst'])} vs worst offer")


def render_insurance(profile: IndividualProfile):
    """Render insurance needs analyzer."""
    st.header("Insurance Needs Analyzer")

    tab_life, tab_health = st.tabs(["Life Insurance", "Health Insurance"])

    with tab_life:
        result = calculate_life_insurance_need(profile)
        gap_color = "inverse" if result.gap > 0 else "normal"

        col1, col2, col3 = st.columns(3)
        col1.metric("Recommended Cover", format_indian_number(result.recommended_cover))
        col2.metric("Current Cover", format_indian_number(result.current_cover))
        col3.metric("Gap", format_indian_number(result.gap), delta_color=gap_color)

        st.metric("Adequacy", f"{result.adequacy_pct:.0f}%")
        st.progress(min(result.adequacy_pct / 100, 1.0))

        st.subheader("Calculation Methods")
        col1, col2, col3 = st.columns(3)
        col1.metric("Human Life Value (HLV)", format_indian_number(result.hlv_method))
        col2.metric("Expense Replacement", format_indian_number(result.expense_method))
        col3.metric("Needs-Based", format_indian_number(result.needs_method))

        if result.recommendations:
            st.subheader("Recommendations")
            for rec in result.recommendations:
                st.warning(rec)

    with tab_health:
        num_family = st.number_input("Family Members", 1, 8, 3)
        city_tier = st.selectbox("City Tier", ["metro", "non_metro"])

        result = calculate_health_insurance_need(profile, num_family, city_tier)

        col1, col2, col3 = st.columns(3)
        col1.metric("Recommended Cover", format_indian_number(result.recommended_cover))
        col2.metric("Current Cover", format_indian_number(result.current_cover))
        col3.metric("Gap", format_indian_number(result.gap))

        st.metric("Adequacy", f"{result.adequacy_pct:.0f}%")
        st.progress(min(result.adequacy_pct / 100, 1.0))

        if result.needs_super_top_up:
            st.info(f"Super Top-Up needed: {format_indian_number(result.recommended_top_up)}")
        st.metric("Estimated Annual Premium", format_indian_number(result.estimated_premium))

        if result.recommendations:
            st.subheader("Recommendations")
            for rec in result.recommendations:
                st.warning(rec)


def render_retirement_planner():
    """Render SWP & retirement planning."""
    st.header("Retirement Planner (SWP)")

    tab_swp, tab_bucket = st.tabs(["Withdrawal Calculator", "Bucket Strategy"])

    with tab_swp:
        col1, col2 = st.columns(2)
        with col1:
            corpus = st.number_input("Retirement Corpus", 1_000_000, 500_000_000, 20_000_000, step=1_000_000)
            monthly_withdrawal = st.number_input("Monthly Withdrawal", 10_000, 5_000_000, 100_000, step=10_000)
        with col2:
            annual_return = st.slider("Expected Return (%)", 4.0, 15.0, 8.0, 0.5) / 100
            inflation = st.slider("Inflation (%)", 3.0, 10.0, 6.0, 0.5, key="swp_inf") / 100

        if st.button("Calculate SWP", type="primary"):
            result = calculate_swp(corpus, monthly_withdrawal, annual_return, inflation)

            col1, col2, col3 = st.columns(3)
            col1.metric("Corpus Lasts", f"{result.years_corpus_lasts:.1f} years")
            col2.metric("Total Withdrawn", format_indian_number(result.total_withdrawn))
            col3.metric("Final Balance", format_indian_number(result.final_balance))

            safe = calculate_safe_withdrawal(corpus, 30, annual_return, inflation)
            st.info(f"Safe monthly withdrawal for 30 years: {format_indian_number(safe)}")

            if result.years_corpus_lasts < 25:
                st.error("Your corpus may not last 25 years! Consider reducing withdrawals.")
            else:
                st.success("Your corpus should sustain you for 25+ years!")

    with tab_bucket:
        col1, col2 = st.columns(2)
        with col1:
            b_corpus = st.number_input("Total Corpus", 1_000_000, 500_000_000, 20_000_000, step=1_000_000, key="b_corpus")
        with col2:
            b_expenses = st.number_input("Monthly Expenses", 10_000, 5_000_000, 80_000, step=5_000)

        if st.button("Create Bucket Strategy", type="primary", key="bucket_btn"):
            strategy = create_bucket_strategy(b_corpus, b_expenses)

            st.metric("Total Years Covered", f"{strategy.years_covered:.1f} years")

            for bucket_data in [strategy.short_term, strategy.medium_term, strategy.long_term]:
                st.subheader(bucket_data.name)
                col1, col2, col3 = st.columns(3)
                col1.metric("Amount", format_indian_number(bucket_data.amount))
                col2.metric("Allocation", f"{bucket_data.pct:.1f}%")
                col3.metric("Expected Return", f"{bucket_data.expected_return * 100:.0f}%")
                st.caption(f"{bucket_data.duration_years} | {bucket_data.asset_type}")


def render_life_simulator(profile: IndividualProfile):
    """Render life event simulator."""
    st.header("Life-Event Simulator")

    event_type = st.selectbox(
        "Select Life Event",
        options=list(LIFE_EVENT_TEMPLATES.keys()),
        format_func=lambda x: LIFE_EVENT_TEMPLATES[x]["name"],
    )

    template = LIFE_EVENT_TEMPLATES[event_type]

    col1, col2 = st.columns(2)
    with col1:
        year = st.number_input("Year", 2026, 2050, 2027)
        month = st.number_input("Month", 1, 12, 6)
        one_time = st.number_input("One-time Cost", 0, 100_000_000, int(template.get("one_time_cost", 0)), step=50_000)
    with col2:
        income_change = st.number_input("Monthly Income Change", -1_000_000, 1_000_000, int(template.get("monthly_income_change", 0)), step=5_000)
        expense_change = st.number_input("Monthly Expense Change", 0, 500_000, int(template.get("monthly_expense_change", 0)), step=1_000)
        duration = st.number_input("Duration (months, 0=permanent)", 0, 600, template.get("duration_months", 0))

    new_emi = st.number_input("New EMI", 0, 500_000, int(template.get("new_emi", 0)), step=5_000)

    if st.button("Simulate Impact", type="primary"):
        event = LifeEvent(
            event_type=event_type, name=template["name"],
            year=year, month=month, one_time_cost=one_time,
            monthly_income_change=income_change, monthly_expense_change=expense_change,
            duration_months=duration, new_emi=new_emi,
        )

        goals = st.session_state.get("planned_goals", [])
        portfolio = st.session_state.get("portfolio")
        result = analyze_life_event_advisor(
            profile,
            [event],
            goals=goals,
            portfolio=portfolio,
            years=10,
        )
        scenario = result["scenario"]
        deltas = scenario["deltas"]

        st.subheader("Impact Summary")

        col1, col2, col3 = st.columns(3)
        delta_nw = deltas["net_worth_impact"]
        col1.metric(
            "Net Worth Impact (10yr)",
            format_indian_number(abs(delta_nw)),
            delta=f"{deltas['net_worth_impact_pct']:.1f}%",
            delta_color="normal" if delta_nw >= 0 else "inverse",
        )
        col2.metric(
            "Savings Rate Change",
            f"{deltas['savings_rate_impact']:.1f}%",
            delta_color="normal" if deltas['savings_rate_impact'] >= 0 else "inverse",
        )
        col3.metric(
            "Emergency Fund Stress",
            format_indian_number(abs(deltas["emergency_fund_stress"])),
            delta_color="normal" if deltas["emergency_fund_stress"] >= 0 else "inverse",
        )

        col1, col2 = st.columns(2)
        with col1:
            st.write("**Baseline (No Event)**")
            st.write(f"Final Net Worth: {format_indian_number(scenario['baseline']['final_net_worth'])}")
            st.write(f"Total Invested: {format_indian_number(scenario['baseline']['total_invested'])}")
            st.write(f"Avg Savings Rate: {scenario['baseline']['average_savings_rate_pct']:.0f}%")
        with col2:
            st.write(f"**With {template['name']}**")
            st.write(f"Final Net Worth: {format_indian_number(scenario['with_events']['final_net_worth'])}")
            st.write(f"Total Invested: {format_indian_number(scenario['with_events']['total_invested'])}")
            st.write(f"Avg Savings Rate: {scenario['with_events']['average_savings_rate_pct']:.0f}%")

        st.subheader("Integrated Advice")
        cashflow = result["cashflow"]
        tax_impact = result["tax_impact"]
        insurance = result["insurance_impact"]

        row1, row2, row3 = st.columns(3)
        row1.metric("Post-Event Surplus", format_indian_number(cashflow["post_event_monthly_surplus"]))
        row2.metric("Recommended SIP After Event", format_indian_number(cashflow["recommended_monthly_sip_after_event"]))
        row3.metric("Annual Tax Delta", format_indian_number(tax_impact["annual_tax_delta"]))

        ins1, ins2 = st.columns(2)
        ins1.metric("Life Cover Gap After Event", format_indian_number(insurance["post_event_life_cover_gap"]))
        ins2.metric("Health Cover Gap After Event", format_indian_number(insurance["post_event_health_cover_gap"]))

        goal_impact = result["goal_impact"]
        if goal_impact["goal_count"] > 0:
            st.subheader("Goal Impact")
            st.dataframe(goal_impact["goal_impacts"], use_container_width=True)

        portfolio_effects = result["portfolio_effects"]
        if portfolio_effects.get("loaded"):
            st.subheader("Portfolio Effect")
            benchmark = portfolio_effects["benchmark"]
            pcol1, pcol2, pcol3 = st.columns(3)
            pcol1.metric("Portfolio XIRR", f"{benchmark['portfolio_xirr_pct']}%" if benchmark["portfolio_xirr_pct"] is not None else "N/A")
            pcol2.metric("Benchmark", f"{benchmark['weighted_benchmark_return_pct']:.2f}%")
            pcol3.metric("Alpha", f"{benchmark['alpha_pct']:+.2f}%" if benchmark["alpha_pct"] is not None else "N/A")
            st.info(portfolio_effects["recommended_deployment"])

        if result["recommended_actions"]:
            st.subheader("Recommended Actions")
            for action in result["recommended_actions"]:
                st.warning(action)


def render_chat():
    """Render AI chat interface."""
    st.header("Chat with Money Mentor")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("Ask anything about your finances..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    loop = asyncio.new_event_loop()
                    response = loop.run_until_complete(
                        st.session_state.supervisor.chat(prompt)
                    )
                    loop.close()
                except Exception as e:
                    response = (
                        f"I couldn't connect to the AI backend ({str(e)[:100]}). "
                        "Please check your LLM API key in .env.\n\n"
                        "Try the other tabs for instant calculations!"
                    )
            st.write(response)
            st.session_state.chat_history.append({"role": "assistant", "content": response})


def render_investment_explorer():
    """Render investment screener / explorer tab."""
    st.header("Investment Explorer")
    st.caption("Explore mutual funds and stocks with real market data. Not a buy/sell recommendation.")

    tab_alloc, tab_mf, tab_stocks = st.tabs(["Asset Allocation", "MF Search", "Stock Screener"])

    with tab_alloc:
        col1, col2 = st.columns(2)
        with col1:
            goal_years = st.number_input("Investment Horizon (years)", 1, 30, 10)
        with col2:
            risk = st.selectbox("Risk Appetite", ["conservative", "moderate", "aggressive"], index=1)

        if st.button("Get Allocation Suggestion", type="primary", key="alloc_btn"):
            result = suggest_asset_allocation(goal_years, risk)

            st.subheader(f"Model Allocation — {risk.title()}, {goal_years} years")

            # Pie chart
            labels = [a["category"] for a in result["allocation"]]
            values = [a["allocation_pct"] for a in result["allocation"]]
            fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4)])
            fig.update_layout(title="Recommended Category Split", height=400)
            st.plotly_chart(fig, use_container_width=True)

            # Details table
            for alloc in result["allocation"]:
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.write(f"**{alloc['category']}**")
                col2.write(f"{alloc['allocation_pct']}%")
                col3.write(f"Risk: {alloc['risk_level']}")

            for note in result.get("notes", []):
                st.info(note)

    with tab_mf:
        col1, col2 = st.columns([3, 1])
        with col1:
            query = st.text_input("Search Mutual Funds", placeholder="e.g., large cap, HDFC flexi cap, nifty 50 index")
        with col2:
            st.write("")  # spacer
            st.write("")
            search_btn = st.button("Search", type="primary", key="mf_search_btn")

        # Quick category buttons
        st.write("**Quick search:**")
        cat_cols = st.columns(5)
        quick_query = None
        categories = list(MF_CATEGORIES.items())[:5]
        for i, (key, cat) in enumerate(categories):
            with cat_cols[i]:
                if st.button(cat["label"], key=f"cat_{key}"):
                    quick_query = cat["search"]

        active_query = quick_query or (query if search_btn else None)
        if active_query:
            st.session_state.mf_active_query = active_query

        current_query = st.session_state.get("mf_active_query")
        if current_query:
            with st.spinner("Searching funds..."):
                results = search_mutual_funds(current_query)

            if results and "error" not in results[0]:
                st.success(f"Found {len(results)} matching Direct Growth plans")
                for fund in results:
                    col1, col2 = st.columns([4, 1])
                    col1.write(f"**{fund['scheme_name']}**")
                    
                    state_key = f"expand_{fund['scheme_code']}"
                    is_expanded = st.session_state.get(state_key, False)
                    
                    if col2.button("Hide Details" if is_expanded else "Details", key=f"detail_{fund['scheme_code']}"):
                        is_expanded = not is_expanded
                        st.session_state[state_key] = is_expanded

                    if is_expanded:
                        with st.container(border=True):
                            with st.spinner("Fetching fund data..."):
                                details = get_fund_details(fund["scheme_code"])
                            if "error" not in details:
                                st.write(f"**{details.get('scheme_name', '')}**")
                                st.write(f"Fund House: {details.get('fund_house', 'N/A')}")
                                st.write(f"Category: {details.get('scheme_category', 'N/A')}")
                                st.write(f"NAV: Rs {details.get('nav', 'N/A')} ({details.get('nav_date', '')})")
                                ret_cols = st.columns(3)
                                ret_cols[0].metric("1Y Return", f"{details.get('return_1y', 'N/A')}%")
                                ret_cols[1].metric("3Y Return", f"{details.get('return_3y', 'N/A')}%")
                                ret_cols[2].metric("5Y Return", f"{details.get('return_5y', 'N/A')}%")
                            else:
                                st.error(details["error"])
            elif results:
                st.error(results[0].get("error", "No results found"))
            else:
                st.warning("No matching funds found. Try a broader search term.")

    with tab_stocks:
        sector = st.selectbox(
            "Filter by Sector",
            ["All", "IT", "Banking", "FMCG", "Pharma", "Energy", "Auto", "Consumer", "Infrastructure", "Telecom"],
        )

        if st.button("Screen Stocks", type="primary", key="stock_btn"):
            with st.spinner("Fetching stock data from NSE..."):
                sector_filter = None if sector == "All" else sector
                results = screen_stocks(sector=sector_filter)

            if results and "error" not in results[0]:
                st.success(f"Showing {len(results)} Nifty 50 stocks")
                for stock in results:
                    col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                    col1.write(f"**{stock['name']}** ({stock['ticker']})")
                    col2.metric("Price", f"Rs {stock['price']:,.0f}")
                    col3.metric("P/E", f"{stock.get('pe_ratio', 'N/A')}")
                    col4.metric("Mkt Cap (Cr)", f"{stock.get('market_cap_cr', 'N/A'):,.0f}" if stock.get('market_cap_cr') else "N/A")
                    col5.metric("Div Yield", f"{stock.get('dividend_yield_pct', 'N/A')}%")
            elif results:
                st.error(results[0].get("error", "Failed to fetch data"))

        st.caption("Past performance does not guarantee future returns. Consult a SEBI-registered advisor.")


def render_couple_planner(profile: IndividualProfile):
    """Render couple's joint financial planner."""
    st.header("Couple's Money Planner")
    st.caption("India's first AI-powered joint financial planning tool. Optimize HRA, SIP splits, and household insurance structure together.")

    use_demo = st.checkbox("Load demo couple (Priya & Vikram Mehta)", value=True, key="couple_demo")

    if use_demo:
        household = get_demo_couple()
        st.info(f"Loaded: **{household.person_a.name}** (Age {household.person_a.age}) & **{household.person_b.name}** (Age {household.person_b.age})")
    else:
        st.subheader("Partner 2 Details")
        st.caption("Partner 1 is your current sidebar profile. Enter Partner 2 details below.")

        with st.expander("Partner 2 - Salary & Deductions", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                p2_name = st.text_input("Name", "Partner", key="p2_name")
                p2_age = st.number_input("Age", 18, 80, 30, key="p2_age")
                p2_basic = st.number_input("Basic (Annual)", 0, 50_000_000, 500_000, step=50_000, key="p2_basic")
                p2_hra = st.number_input("HRA (Annual)", 0, 20_000_000, 200_000, step=10_000, key="p2_hra")
                p2_special = st.number_input("Special Allowance", 0, 20_000_000, 300_000, step=10_000, key="p2_special")
            with col2:
                p2_epf = st.number_input("Employee PF", 0, 500_000, 60_000, step=5_000, key="p2_epf")
                p2_elss = st.number_input("ELSS", 0, 150_000, 0, step=5_000, key="p2_elss")
                p2_ppf = st.number_input("PPF", 0, 150_000, 0, step=5_000, key="p2_ppf")
                p2_nps = st.number_input("NPS 80CCD(1B)", 0, 50_000, 0, step=5_000, key="p2_nps")
                p2_health_ded = st.number_input("Health Insurance Deduction", 0, 25_000, 0, step=1_000, key="p2_health_ded")

        with st.expander("Partner 2 - Wealth, Insurance & Cash Flow", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                p2_investments = st.number_input("Current Investments", 0, 100_000_000, 500_000, step=50_000, key="p2_inv")
                p2_monthly_sip = st.number_input("Monthly SIP", 0, 1_000_000, 20_000, step=1_000, key="p2_sip")
                p2_emergency = st.number_input("Emergency Fund", 0, 20_000_000, 200_000, step=50_000, key="p2_ef")
                p2_life_cover = st.number_input("Life Cover", 0, 100_000_000, 2_500_000, step=500_000, key="p2_life")
                p2_health_cover = st.number_input("Health Cover", 0, 50_000_000, 500_000, step=100_000, key="p2_health_cover")
            with col2:
                p2_rent = st.number_input("Monthly Rent", 0, 500_000, 15_000, step=1_000, key="p2_rent")
                p2_groceries = st.number_input("Monthly Groceries", 0, 100_000, 8_000, step=500, key="p2_grocery")
                p2_utilities = st.number_input("Monthly Utilities", 0, 50_000, 4_000, step=500, key="p2_util")
                p2_transport = st.number_input("Monthly Transport", 0, 50_000, 4_000, step=500, key="p2_transport")
                p2_misc = st.number_input("Monthly Misc", 0, 200_000, 10_000, step=1_000, key="p2_misc")

        partner2 = IndividualProfile(
            name=p2_name, age=p2_age,
            salary=SalaryBreakup(basic=p2_basic, hra=p2_hra, special_allowance=p2_special),
            deductions=Deductions(
                employee_pf=p2_epf, elss=p2_elss, ppf=p2_ppf,
                nps_additional=p2_nps, self_health_insurance=p2_health_ded,
            ),
            insurance=InsuranceCoverage(
                life_cover=p2_life_cover,
                health_cover=p2_health_cover,
            ),
            monthly_expenses=MonthlyExpenses(
                rent=p2_rent,
                groceries=p2_groceries,
                utilities=p2_utilities,
                transportation=p2_transport,
                misc=p2_misc,
            ),
            emergency_fund=p2_emergency,
            current_investments=p2_investments,
            monthly_sip=p2_monthly_sip,
        )
        household = HouseholdProfile(person_a=profile, person_b=partner2)

    default_rent = int(max(
        household.person_a.deductions.rent_paid_annual + household.person_b.deductions.rent_paid_annual,
        (household.person_a.monthly_expenses.rent + household.person_b.monthly_expenses.rent) * 12,
        360_000 if use_demo else 0,
    ))
    default_household_sip = int(max(
        household.person_a.monthly_sip + household.person_b.monthly_sip,
        40_000,
    ))
    control_col1, control_col2 = st.columns(2)
    with control_col1:
        shared_annual_rent = st.number_input("Shared Annual Rent for HRA Optimization", 0, 5_000_000, default_rent, step=12_000)
    with control_col2:
        target_household_sip = st.number_input("Target Household Monthly SIP", 0, 2_000_000, default_household_sip, step=5_000)

    if st.button("Optimize Couple Tax", type="primary", key="couple_btn"):
        result = optimize_couple_tax(
            household,
            shared_annual_rent=shared_annual_rent,
            target_monthly_sip=target_household_sip,
        )

        # Combined summary
        st.subheader("Household Tax Summary")
        col1, col2, col3 = st.columns(3)
        col1.metric("Combined Annual Income", format_indian_number(household.combined_annual_income))
        col2.metric("Household Total Tax", format_indian_number(result["household_total_tax"]))
        col3.metric("Combined Monthly In-Hand", format_indian_number(result.get("household_total_monthly_in_hand", 0)))

        wealth_col1, wealth_col2, wealth_col3 = st.columns(3)
        wealth_col1.metric("Combined Net Worth", format_indian_number(result.get("combined_net_worth", 0)))
        wealth_col2.metric("Emergency Fund", format_indian_number(result.get("combined_emergency_fund", 0)))
        wealth_col3.metric("Emergency Cover", f"{result.get('emergency_months_covered', 0):.1f} months")

        cover_col1, cover_col2 = st.columns(2)
        cover_col1.metric(
            "Life Cover Gap",
            format_indian_number(result.get("combined_life_cover_gap", 0)),
        )
        cover_col2.metric(
            "Health Cover Gap",
            format_indian_number(result.get("combined_health_cover_gap", 0)),
        )

        hra_result = result.get("hra_optimization")
        if hra_result:
            st.subheader("HRA Split Optimization")
            h1, h2, h3 = st.columns(3)
            h1.metric("Rent to Partner 1", format_indian_number(hra_result["rent_to_person_a"]))
            h2.metric("Rent to Partner 2", format_indian_number(hra_result["rent_to_person_b"]))
            h3.metric("Extra Tax Saved", format_indian_number(hra_result["tax_saved_vs_current_split"]))

        sip_result = result.get("sip_split")
        if sip_result:
            st.subheader("SIP Split Optimization")
            s1, s2, s3 = st.columns(3)
            s1.metric(f"{household.person_a.name} SIP", format_indian_number(sip_result["person_a_recommended_sip"]))
            s2.metric(f"{household.person_b.name} SIP", format_indian_number(sip_result["person_b_recommended_sip"]))
            s3.metric("Household SIP Target", format_indian_number(sip_result["target_household_monthly_sip"]))
            st.info(sip_result["note"])

        insurance_result = result.get("insurance_structure")
        if insurance_result:
            st.subheader("Insurance Structure")
            i1, i2, i3 = st.columns(3)
            i1.metric("Recommended Structure", insurance_result["recommended_structure"])
            i2.metric("Partner 1 Life Gap", format_indian_number(insurance_result["person_a_life_cover_gap"]))
            i3.metric("Partner 2 Life Gap", format_indian_number(insurance_result["person_b_life_cover_gap"]))
            st.caption(insurance_result["note"])

        # Optimization notes
        if result["optimization_notes"]:
            st.subheader("Optimization Recommendations")
            for note in result["optimization_notes"]:
                st.warning(f"-> {note}")

        # Side by side partner comparison
        col_a, col_b = st.columns(2)

        with col_a:
            pa = result["person_a"]
            st.subheader(f"{household.person_a.name}")
            rec_a = pa.get("recommended_regime", "new")
            saving_a = pa.get("tax_saving", 0)
            st.success(f"Best: **{rec_a.upper()} Regime** | Save {format_indian_number(saving_a)}/yr")

            old_a = pa.get("old_regime", {})
            new_a = pa.get("new_regime", {})
            st.metric("Gross Income", format_indian_number(old_a.get("gross_income", 0)))
            st.metric("Old Regime Tax", format_indian_number(old_a.get("total_tax", 0)))
            st.metric("New Regime Tax", format_indian_number(new_a.get("total_tax", 0)))
            st.metric("Monthly In-Hand (Best)", format_indian_number(
                max(old_a.get("monthly_in_hand", 0), new_a.get("monthly_in_hand", 0))
            ))

        with col_b:
            pb = result["person_b"]
            if pb:
                st.subheader(f"{household.person_b.name}")
                rec_b = pb.get("recommended_regime", "new")
                saving_b = pb.get("tax_saving", 0)
                st.success(f"Best: **{rec_b.upper()} Regime** | Save {format_indian_number(saving_b)}/yr")

                old_b = pb.get("old_regime", {})
                new_b = pb.get("new_regime", {})
                st.metric("Gross Income", format_indian_number(old_b.get("gross_income", 0)))
                st.metric("Old Regime Tax", format_indian_number(old_b.get("total_tax", 0)))
                st.metric("New Regime Tax", format_indian_number(new_b.get("total_tax", 0)))
                st.metric("Monthly In-Hand (Best)", format_indian_number(
                    max(old_b.get("monthly_in_hand", 0), new_b.get("monthly_in_hand", 0))
                ))

        # Bar chart
        pa_data = result["person_a"]
        pb_data = result["person_b"]
        if pb_data:
            best_a = min(pa_data["old_regime"]["total_tax"], pa_data["new_regime"]["total_tax"])
            best_b = min(pb_data["old_regime"]["total_tax"], pb_data["new_regime"]["total_tax"])
            fig = go.Figure(data=[
                go.Bar(name=household.person_a.name, x=["Tax", "In-Hand/mo"], y=[
                    best_a, max(pa_data["old_regime"]["monthly_in_hand"], pa_data["new_regime"]["monthly_in_hand"])
                ], marker_color="#FF6B6B"),
                go.Bar(name=household.person_b.name, x=["Tax", "In-Hand/mo"], y=[
                    best_b, max(pb_data["old_regime"]["monthly_in_hand"], pb_data["new_regime"]["monthly_in_hand"])
                ], marker_color="#4ECDC4"),
            ])
            fig.update_layout(barmode="group", title="Partner Tax Comparison", height=400)
            st.plotly_chart(fig, use_container_width=True)


def render_portfolio_xray():
    """Render Portfolio X-Ray section with CAS upload."""
    st.header("Portfolio X-Ray")
    st.caption("Upload your CAMS/KFintech CAS statement or load a demo portfolio for XIRR analysis, behavioral insights, and rebalancing.")

    tab_load, tab_holdings, tab_returns, tab_behavioral, tab_rebalance = st.tabs([
        "Load Portfolio", "Holdings & Allocation", "Returns & Expenses", "Behavioral Insights", "Rebalance",
    ])

    with tab_load:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Upload CAS PDF")
            cas_file = st.file_uploader("Upload CAMS/KFintech CAS PDF", type=["pdf"], key="cas_upload")
            cas_password = st.text_input("PDF Password (PAN-based)", type="password", key="cas_pwd")
        with col2:
            st.subheader("Or Use Demo")
            if st.button("Load Demo Portfolio", type="primary", key="demo_portfolio_btn"):
                st.session_state.portfolio = get_demo_portfolio()
                st.success("Loaded demo portfolio (Rahul Sharma - 6 funds)")

        if cas_file is not None:
            suffix = os.path.splitext(cas_file.name)[1] or ".pdf"
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(cas_file.getbuffer())
                    temp_path = tmp.name
                st.session_state.portfolio = parse_cas_pdf(temp_path, password=cas_password)
                st.success(f"Parsed {cas_file.name} - {st.session_state.portfolio.num_funds} funds found")
            except ImportError as exc:
                st.error(str(exc))
            except ValueError as exc:
                st.error(str(exc))
            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass

    portfolio = st.session_state.get("portfolio")
    if portfolio is None:
        st.info("Load a portfolio above to see X-Ray analysis.")
        return

    # Run all analyses
    returns_data = compute_portfolio_returns(portfolio)
    overlap_data = analyze_fund_overlap(portfolio)
    expenses_data = analyze_expense_ratios(portfolio)
    benchmark_data = analyze_benchmark_comparison(portfolio, prefer_live=True)
    behavioral_data = generate_behavioral_summary(run_full_behavioral_analysis(portfolio))
    rebalance_data = generate_rebalance_plan(portfolio, age=28)

    with tab_holdings:
        st.subheader(f"Portfolio: {portfolio.investor_name} ({portfolio.num_funds} funds)")

        # Category allocation pie
        alloc = portfolio.category_allocation()
        if alloc:
            labels = [cat.value.replace("_", " ").title() for cat in alloc.keys()]
            values = list(alloc.values())
            fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4)])
            fig.update_layout(title="Category Allocation", height=400)
            st.plotly_chart(fig, use_container_width=True)

        # Holdings table
        for h in portfolio.holdings:
            plan_badge = "Direct" if h.plan_type.value == "direct" else "Regular"
            gain_color = "normal" if h.absolute_return >= 0 else "inverse"
            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
            col1.write(f"**{h.scheme_name}**")
            col1.caption(f"{h.category.value.replace('_', ' ').title()} | {plan_badge}")
            col2.metric("Invested", format_indian_number(h.invested_amount))
            col3.metric("Current", format_indian_number(h.current_value))
            col4.metric("Gain", format_indian_number(h.absolute_return), delta_color=gain_color)
            col5.metric("XIRR", f"{h.xirr * 100:.1f}%" if h.xirr else "N/A")

    with tab_returns:
        st.subheader("Portfolio Returns")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Overall XIRR", f"{returns_data['overall_xirr_pct']}%" if returns_data['overall_xirr_pct'] else "N/A")
        col2.metric("Total Invested", format_indian_number(returns_data["total_invested"]))
        col3.metric("Current Value", format_indian_number(returns_data["total_current_value"]))
        col4.metric("Total Gain", format_indian_number(returns_data["total_gain"]))

        st.subheader("Benchmark Comparison")
        benchmark = benchmark_data.to_dict()
        bcol1, bcol2, bcol3 = st.columns(3)
        bcol1.metric(
            "Portfolio XIRR",
            f"{benchmark['portfolio_xirr_pct']}%" if benchmark["portfolio_xirr_pct"] is not None else "N/A",
        )
        bcol2.metric(
            "Benchmark",
            f"{benchmark['weighted_benchmark_return_pct']:.2f}%",
        )
        alpha_value = benchmark["alpha_pct"]
        bcol3.metric(
            "Alpha",
            f"{alpha_value:+.2f}%" if alpha_value is not None else "N/A",
            delta_color="normal" if (alpha_value or 0) >= 0 else "inverse",
        )
        st.caption(benchmark["note"])

        # Per-fund XIRR bar chart
        holding_names = [h["scheme"][:30] for h in returns_data["holdings"]]
        xirr_values = [h["xirr_pct"] or 0 for h in returns_data["holdings"]]
        fig = go.Figure(data=[go.Bar(
            x=holding_names, y=xirr_values,
            marker_color=["#4CAF50" if v >= 0 else "#f44336" for v in xirr_values],
        )])
        fig.update_layout(title="XIRR by Fund (%)", height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

        # Expense analysis
        st.subheader("Expense Analysis")
        exp = expenses_data.to_dict()
        col1, col2, col3 = st.columns(3)
        col1.metric("Annual Expense Drag", format_indian_number(exp["total_annual_expense_drag"]))
        col2.metric("Weighted Expense Ratio", f"{exp['weighted_expense_ratio_pct']:.2f}%")
        col3.metric("Save by Switching to Direct", format_indian_number(exp["potential_annual_savings_if_direct"]))

        if exp["regular_plan_funds"]:
            st.warning(f"Regular plan funds (higher cost): {', '.join(exp['regular_plan_funds'])}")

        # Overlap analysis
        st.subheader("Fund Overlap")
        overlap_dict = overlap_data.to_dict()
        if overlap_dict["high_overlap_pairs"]:
            for pair in overlap_dict["high_overlap_pairs"]:
                st.error(f"**{pair['fund_a'][:40]}** & **{pair['fund_b'][:40]}** — {pair['overlap_pct']:.0f}% overlap")
        for sug in overlap_dict["consolidation_suggestions"]:
            st.info(sug)

    with tab_behavioral:
        st.subheader("Behavioral Pattern Detection")
        st.caption("Research-backed analysis (Chadha 2024, ACR Journal) of common investor biases in your portfolio.")

        st.write(f"**Overall:** {behavioral_data['overall_assessment']}")

        if behavioral_data["total_patterns"] == 0:
            st.success("No significant behavioral biases detected. Well done!")
        else:
            for pattern in behavioral_data["patterns"]:
                severity_color = {"high": "error", "medium": "warning", "low": "info"}.get(pattern["severity"], "info")
                with st.expander(f"{'🔴' if pattern['severity'] == 'high' else '🟡'} {pattern['name']} ({pattern['severity'].title()})"):
                    st.write(f"**Bias:** {pattern['bias_type']}")
                    st.write(f"**Description:** {pattern['description']}")
                    st.write("**Evidence:**")
                    for ev in pattern["evidence"]:
                        st.write(f"  - {ev}")
                    st.info(f"**Recommendation:** {pattern['recommendation']}")

    with tab_rebalance:
        st.subheader("Portfolio Rebalancing")
        reb = rebalance_data.to_dict()
        st.write(f"**Risk Profile:** {reb['risk_profile'].title()} — {reb['model_description']}")

        col1, col2 = st.columns(2)
        with col1:
            st.write("**Current Allocation**")
            curr = reb["current_allocation"]
            st.metric("Equity", f"{curr['equity_pct']:.1f}%")
            st.metric("Debt", f"{curr['debt_pct']:.1f}%")
            st.metric("Gold", f"{curr['gold_pct']:.1f}%")
        with col2:
            st.write("**Target Allocation**")
            tgt = reb["target_allocation"]
            st.metric("Equity", f"{tgt['equity_pct']:.1f}%")
            st.metric("Debt", f"{tgt['debt_pct']:.1f}%")
            st.metric("Gold", f"{tgt['gold_pct']:.1f}%")

        if reb["rebalance_needed"]:
            st.warning(f"Rebalancing recommended — max drift: {reb['max_drift_pct']:.1f}%")
            for action in reb["actions"]:
                icon = "📈" if action["action"] == "increase" else "📉"
                st.write(f"{icon} **{action['asset_class']}**: {action['current_pct']:.1f}% → {action['target_pct']:.1f}%")
                st.caption(action["suggestion"])
        else:
            st.success("Portfolio is well-balanced! No rebalancing needed.")


# --- Main App ---

def main():
    st.title("ET Money Mentor")
    st.caption("AI-Powered Personal Finance Assistant for India")

    # Build profile from sidebar
    profile = build_profile_from_sidebar()
    portfolio = st.session_state.get("portfolio")

    # Wire profile to AI supervisor for tool calling
    st.session_state.supervisor.set_user_profile_object(profile)
    health_report = compute_money_health_score(profile, portfolio)
    st.session_state.supervisor.set_user_profile(
        _profile_context_summary(profile, health_report)
    )
    if portfolio is not None:
        st.session_state.supervisor.set_portfolio_object(portfolio)
        st.session_state.supervisor.set_portfolio_data(
            _portfolio_context_summary(portfolio)
        )
    else:
        st.session_state.supervisor.set_portfolio_object(None)
        st.session_state.supervisor.set_portfolio_data(None)

    # Tab navigation
    tabs = st.tabs([
        "Chat", "Health Score", "Tax Wizard", "Couple Planner",
        "Goal Planner", "FIRE Calculator", "EMI & Loans", "Insurance",
        "Retirement (SWP)", "Life Simulator", "Investment Explorer", "Portfolio X-Ray",
    ])

    with tabs[0]:
        render_chat()
    with tabs[1]:
        render_health_score(profile)
    with tabs[2]:
        render_tax_comparison(profile)
    with tabs[3]:
        render_couple_planner(profile)
    with tabs[4]:
        render_goal_planner(profile)
    with tabs[5]:
        render_fire_calculator(profile)
    with tabs[6]:
        render_emi_calculator()
    with tabs[7]:
        render_insurance(profile)
    with tabs[8]:
        render_retirement_planner()
    with tabs[9]:
        render_life_simulator(profile)
    with tabs[10]:
        render_investment_explorer()
    with tabs[11]:
        render_portfolio_xray()

    # Footer
    st.divider()
    st.caption(
        "For educational purposes only. Consult a SEBI-registered advisor. "
        "Built with research from Fin-Ally (ArXiv 2509.24342), Chadha (2024, EEL), and Nature (2025). "
        "Powered by pyxirr, mftool, casparser, fpdf2, quantstats."
    )


if __name__ == "__main__":
    main()
