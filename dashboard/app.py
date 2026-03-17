"""Streamlit Dashboard for ET Money Mentor.

A comprehensive financial dashboard with:
- AI Chat interface
- Money Health Score visualization
- Tax comparison (old vs new regime)
- Goal planner
- Portfolio X-Ray
- Life-event simulator
"""

import sys
import os
import json
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from src.models.user import (
    IndividualProfile, SalaryBreakup, Deductions, InsuranceCoverage,
    Debt, MonthlyExpenses, Gender, City,
)
from src.models.goals import FinancialGoal, GoalType, GoalPriority, LifeEvent, LifeEventType, LIFE_EVENT_TEMPLATES
from src.models.portfolio import Portfolio

from src.engines.tax_calculator import compare_regimes
from src.engines.health_scorer import compute_money_health_score
from src.engines.goal_calculator import plan_all_goals, calculate_fire, monte_carlo_simulation
from src.engines.cashflow_projector import compare_scenarios
from src.agents.supervisor import MoneyMentorSupervisor
from src.utils.language import format_indian_number, detect_language


# --- Page Config ---
st.set_page_config(
    page_title="ET Money Mentor",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Session State Init ---
if "profile" not in st.session_state:
    st.session_state.profile = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "supervisor" not in st.session_state:
    st.session_state.supervisor = MoneyMentorSupervisor()


def build_profile_from_sidebar() -> IndividualProfile:
    """Build user profile from sidebar inputs."""
    st.sidebar.header("Your Profile")

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

    report = compute_money_health_score(profile)

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

    # Dimension breakdown radar chart
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
        showlegend=False,
        height=400,
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
                    st.info(f"→ {rec}")

    # Top actions
    st.subheader("Top 3 Actions to Improve Your Score")
    for i, action in enumerate(report.top_actions, 1):
        st.warning(f"**{i}.** {action}")


def render_tax_comparison(profile: IndividualProfile):
    """Render tax comparison section."""
    st.header("Tax Wizard - Old vs New Regime")

    comp = compare_regimes(profile)
    old = comp.old_regime
    new = comp.new_regime

    # Recommendation banner
    if comp.recommended_regime.value == "old":
        st.success(f"**Old Regime is better!** You save {format_indian_number(comp.tax_saving)}/year")
    else:
        st.success(f"**New Regime is better!** You save {format_indian_number(comp.tax_saving)}/year")

    # Side by side comparison
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

    # Bar chart comparison
    fig = go.Figure(data=[
        go.Bar(name="Old Regime", x=["Tax", "In-Hand (Monthly)"], y=[old.total_tax, old.monthly_in_hand], marker_color="#FF6B6B"),
        go.Bar(name="New Regime", x=["Tax", "In-Hand (Monthly)"], y=[new.total_tax, new.monthly_in_hand], marker_color="#4ECDC4"),
    ])
    fig.update_layout(barmode="group", title="Tax Comparison", height=400)
    st.plotly_chart(fig, use_container_width=True)

    # Unused deduction room
    if comp.unused_deduction_room:
        st.subheader("Unused Deduction Room (Old Regime)")
        for section, amount in comp.unused_deduction_room.items():
            st.warning(f"**{section}:** {format_indian_number(amount)} unused - invest to save tax!")


def render_goal_planner(profile: IndividualProfile):
    """Render goal planner section."""
    st.header("Goal Planner")

    # Goal input form
    st.subheader("Add Your Financial Goals")

    num_goals = st.number_input("Number of goals", 1, 10, 3)
    goals = []

    for i in range(num_goals):
        with st.expander(f"Goal {i + 1}", expanded=(i == 0)):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input(f"Goal Name", f"Goal {i + 1}", key=f"goal_name_{i}")
                target = st.number_input(f"Target Amount (today's value)", 100_000, 100_000_000, 2_000_000, step=100_000, key=f"goal_target_{i}")
                target_year = st.number_input(f"Target Year", 2026, 2060, 2035, key=f"goal_year_{i}")
            with col2:
                corpus = st.number_input(f"Already Saved", 0, 100_000_000, 0, step=50_000, key=f"goal_corpus_{i}")
                sip = st.number_input(f"Current Monthly SIP", 0, 500_000, 0, step=1_000, key=f"goal_sip_{i}")
                priority = st.selectbox(f"Priority", ["critical", "high", "medium", "low"], index=2, key=f"goal_priority_{i}")

            goals.append(FinancialGoal(
                name=name, goal_type=GoalType.CUSTOM, target_amount=target,
                target_year=target_year, current_corpus=corpus, monthly_sip=sip,
                priority=GoalPriority(priority),
            ))

    if st.button("Plan Goals", type="primary"):
        plans = plan_all_goals(goals)

        for plan in plans:
            status = "🟢 On Track" if plan.on_track else "🔴 Needs Attention"
            st.subheader(f"{plan.goal.name} {status}")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Target (Inflation Adj)", format_indian_number(plan.inflation_adjusted_target))
            col2.metric("Gap", format_indian_number(plan.gap))
            col3.metric("Required SIP", format_indian_number(plan.required_monthly_sip) + "/mo")
            col4.metric("Progress", f"{plan.progress_pct:.0f}%")

            # Progress bar
            st.progress(min(plan.progress_pct / 100, 1.0))
            st.caption(f"Suggested: {plan.suggested_asset_class}")

            for note in plan.notes:
                st.info(f"→ {note}")


def render_fire_calculator():
    """Render FIRE calculator."""
    st.header("FIRE Calculator")

    col1, col2 = st.columns(2)
    with col1:
        current_age = st.number_input("Current Age", 18, 70, 30)
        annual_exp = st.number_input("Annual Expenses", 100_000, 50_000_000, 600_000, step=50_000)
        corpus = st.number_input("Current Investment Corpus", 0, 100_000_000, 0, step=100_000)
    with col2:
        monthly_inv = st.number_input("Monthly Investment", 0, 1_000_000, 30_000, step=5_000)
        exp_return = st.slider("Expected Return (%)", 6.0, 18.0, 10.0, 0.5) / 100
        inflation = st.slider("Inflation (%)", 3.0, 10.0, 6.0, 0.5) / 100

    if st.button("Calculate FIRE", type="primary"):
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

        # Monte Carlo
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
            event_type=event_type,
            name=template["name"],
            year=year, month=month,
            one_time_cost=one_time,
            monthly_income_change=income_change,
            monthly_expense_change=expense_change,
            duration_months=duration,
            new_emi=new_emi,
        )

        result = compare_scenarios(profile, [event], years=10)

        st.subheader("Impact Summary")

        col1, col2, col3 = st.columns(3)
        delta_nw = result.deltas["net_worth_impact"]
        col1.metric(
            "Net Worth Impact (10yr)",
            format_indian_number(abs(delta_nw)),
            delta=f"{result.deltas['net_worth_impact_pct']:.1f}%",
            delta_color="normal" if delta_nw >= 0 else "inverse",
        )
        col2.metric(
            "Savings Rate Change",
            f"{result.deltas['savings_rate_impact']:.1f}%",
            delta_color="normal" if result.deltas['savings_rate_impact'] >= 0 else "inverse",
        )
        col3.metric(
            "Emergency Fund Stress",
            format_indian_number(abs(result.deltas["emergency_fund_stress"])),
            delta_color="normal" if result.deltas["emergency_fund_stress"] >= 0 else "inverse",
        )

        # Comparison table
        st.subheader("Before vs After (10 years)")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Baseline (No Event)**")
            st.write(f"Final Net Worth: {format_indian_number(result.baseline.final_net_worth)}")
            st.write(f"Total Invested: {format_indian_number(result.baseline.total_invested)}")
            st.write(f"Avg Savings Rate: {result.baseline.average_savings_rate:.0f}%")
        with col2:
            st.write(f"**With {template['name']}**")
            st.write(f"Final Net Worth: {format_indian_number(result.with_events.final_net_worth)}")
            st.write(f"Total Invested: {format_indian_number(result.with_events.total_invested)}")
            st.write(f"Avg Savings Rate: {result.with_events.average_savings_rate:.0f}%")


def render_chat():
    """Render AI chat interface."""
    st.header("Chat with Money Mentor")

    # Display chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Chat input
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
                        "Please make sure your ANTHROPIC_API_KEY is set.\n\n"
                        "In the meantime, check out the other tabs for instant "
                        "calculations (Tax, Health Score, Goals, FIRE, Simulator)!"
                    )
            st.write(response)
            st.session_state.chat_history.append({"role": "assistant", "content": response})


# --- Main App ---

def main():
    st.title("ET Money Mentor")
    st.caption("AI-Powered Personal Finance Assistant for India")

    # Build profile from sidebar
    profile = build_profile_from_sidebar()
    st.session_state.profile = profile

    # Tab navigation
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Chat", "Health Score", "Tax Wizard",
        "Goal Planner", "FIRE Calculator", "Life Simulator",
    ])

    with tab1:
        render_chat()
    with tab2:
        render_health_score(profile)
    with tab3:
        render_tax_comparison(profile)
    with tab4:
        render_goal_planner(profile)
    with tab5:
        render_fire_calculator()
    with tab6:
        render_life_simulator(profile)

    # Footer
    st.divider()
    st.caption(
        "This is for educational purposes only. Consult a SEBI-registered advisor for personalized advice. "
        "Built with research from Fin-Ally (ArXiv 2509.24342), Chadha (2024, EEL), and Nature (2025)."
    )


if __name__ == "__main__":
    main()
