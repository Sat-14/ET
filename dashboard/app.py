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

import streamlit as st
import plotly.graph_objects as go

from src.models.user import (
    IndividualProfile, SalaryBreakup, Deductions, InsuranceCoverage,
    Debt, MonthlyExpenses, Gender, City,
)
from src.models.goals import FinancialGoal, GoalType, GoalPriority, LifeEvent, LifeEventType, LIFE_EVENT_TEMPLATES

from src.engines.tax_calculator import compare_regimes
from src.engines.health_scorer import compute_money_health_score
from src.engines.goal_calculator import plan_all_goals, calculate_fire, monte_carlo_simulation
from src.engines.cashflow_projector import compare_scenarios
from src.engines.emi_calculator import calculate_emi, analyze_prepayment, prepay_vs_invest
from src.engines.insurance_calculator import calculate_life_insurance_need, calculate_health_insurance_need
from src.engines.swp_calculator import calculate_swp, calculate_safe_withdrawal, create_bucket_strategy
from src.engines.report_generator import generate_health_score_pdf, generate_full_report_pdf
from src.engines.investment_screener import (
    search_mutual_funds, get_fund_details, suggest_asset_allocation, screen_stocks,
    MF_CATEGORIES,
)
from src.agents.supervisor import MoneyMentorSupervisor
from src.utils.language import format_indian_number
from src.demo_data import DEMO_PROFILES, get_demo_goals
from src.parsers.form16_parser import parse_form16_pdf, merge_form16_into_profile


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


def build_profile_from_sidebar() -> IndividualProfile:
    """Build user profile from sidebar inputs."""
    st.sidebar.header("Your Profile")

    # Demo profile quick-load
    demo_choice = st.sidebar.selectbox(
        "Quick Load Demo Profile",
        ["Custom"] + list(DEMO_PROFILES.keys()),
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

    tab_manual, tab_form16 = st.tabs(["Manual Entry", "Upload Form-16"])

    with tab_manual:
        _render_tax_comparison_result(profile)

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
                _render_tax_comparison_result(form16_profile)
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


def _render_tax_comparison_result(profile: IndividualProfile):
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
            current_age=current_age, annual_expenses=annual_exp,
            current_corpus=corpus, monthly_investment=monthly_inv,
            expected_return=exp_return, inflation_rate=inflation,
        )

        col1, col2, col3 = st.columns(3)
        col1.metric("FIRE Number", format_indian_number(result.fire_number))
        col2.metric("Years to FIRE", f"{result.years_to_fire:.0f}")
        col3.metric("FIRE Age", str(result.projected_fire_age))

        st.metric("Savings Rate", f"{result.current_savings_rate:.0f}%")
        st.metric("Annual Passive Income at FIRE", format_indian_number(result.annual_passive_income))

        st.subheader("Monte Carlo Simulation (5000 scenarios)")
        mc = monte_carlo_simulation(
            current_corpus=corpus, monthly_sip=monthly_inv,
            years=int(result.years_to_fire), target_amount=result.fire_number,
        )
        st.metric("Success Probability", f"{mc.success_probability:.0f}%")
        col1, col2, col3 = st.columns(3)
        col1.metric("Pessimistic (P10)", format_indian_number(mc.p10_outcome))
        col2.metric("Median", format_indian_number(mc.median_outcome))
        col3.metric("Optimistic (P90)", format_indian_number(mc.p90_outcome))


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


# --- Main App ---

def main():
    st.title("ET Money Mentor")
    st.caption("AI-Powered Personal Finance Assistant for India")

    # Build profile from sidebar
    profile = build_profile_from_sidebar()

    # Wire profile to AI supervisor for tool calling
    st.session_state.supervisor.set_user_profile_object(profile)
    st.session_state.supervisor.set_user_profile({
        "name": profile.name,
        "age": profile.age,
        "city": profile.city.value,
        "gross_salary": profile.salary.basic + profile.salary.hra + profile.salary.special_allowance + profile.salary.bonus,
        "monthly_expenses": profile.monthly_expenses.total,
        "emergency_fund": profile.emergency_fund,
        "current_investments": profile.current_investments,
        "monthly_sip": profile.monthly_sip,
    })

    # Tab navigation
    tabs = st.tabs([
        "Chat", "Health Score", "Tax Wizard", "Goal Planner",
        "FIRE Calculator", "EMI & Loans", "Insurance",
        "Retirement (SWP)", "Life Simulator", "Investment Explorer",
    ])

    with tabs[0]:
        render_chat()
    with tabs[1]:
        render_health_score(profile)
    with tabs[2]:
        render_tax_comparison(profile)
    with tabs[3]:
        render_goal_planner(profile)
    with tabs[4]:
        render_fire_calculator()
    with tabs[5]:
        render_emi_calculator()
    with tabs[6]:
        render_insurance(profile)
    with tabs[7]:
        render_retirement_planner()
    with tabs[8]:
        render_life_simulator(profile)
    with tabs[9]:
        render_investment_explorer()

    # Footer
    st.divider()
    st.caption(
        "For educational purposes only. Consult a SEBI-registered advisor. "
        "Built with research from Fin-Ally (ArXiv 2509.24342), Chadha (2024, EEL), and Nature (2025). "
        "Powered by pyxirr, mftool, casparser, fpdf2, quantstats."
    )


if __name__ == "__main__":
    main()
