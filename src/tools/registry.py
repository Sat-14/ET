"""Tool definitions for LLM function calling.

Defines 12 tools that map to deterministic engine functions.
Universal format — auto-converts to Gemini / OpenAI / Anthropic schemas.
"""

from __future__ import annotations


TOOLS = [
    {
        "name": "calculate_emi",
        "description": (
            "Calculate EMI (Equated Monthly Installment) for any loan — home, car, personal, education. "
            "Returns monthly EMI, total payment, total interest, and interest-to-principal ratio."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "principal": {
                    "type": "number",
                    "description": "Loan amount in rupees (e.g., 5000000 for 50 lakhs)",
                },
                "annual_rate": {
                    "type": "number",
                    "description": "Annual interest rate as percentage (e.g., 8.5 for 8.5%)",
                },
                "tenure_months": {
                    "type": "integer",
                    "description": "Loan tenure in months (e.g., 240 for 20 years)",
                },
            },
            "required": ["principal", "annual_rate", "tenure_months"],
        },
    },
    {
        "name": "calculate_fire",
        "description": (
            "Calculate FIRE (Financial Independence Retire Early) number and timeline. "
            "Returns FIRE corpus needed, years to FIRE, projected FIRE age, and savings rate."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "current_age": {
                    "type": "integer",
                    "description": "User's current age",
                },
                "annual_expenses": {
                    "type": "number",
                    "description": "Current annual living expenses in rupees",
                },
                "current_corpus": {
                    "type": "number",
                    "description": "Total current investment corpus in rupees (default 0)",
                },
                "monthly_investment": {
                    "type": "number",
                    "description": "Monthly investment/SIP amount in rupees",
                },
                "expected_return": {
                    "type": "number",
                    "description": "Expected annual return as decimal (e.g., 0.10 for 10%). Default 0.10",
                },
                "inflation_rate": {
                    "type": "number",
                    "description": "Annual inflation rate as decimal (e.g., 0.06 for 6%). Default 0.06",
                },
            },
            "required": ["current_age", "annual_expenses", "current_corpus", "monthly_investment"],
        },
    },
    {
        "name": "calculate_swp",
        "description": (
            "Calculate how long a retirement corpus lasts with monthly withdrawals "
            "(SWP — Systematic Withdrawal Plan). Accounts for inflation and investment returns."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "corpus": {
                    "type": "number",
                    "description": "Starting retirement corpus in rupees",
                },
                "monthly_withdrawal": {
                    "type": "number",
                    "description": "Monthly withdrawal amount in rupees",
                },
                "annual_return": {
                    "type": "number",
                    "description": "Expected annual return on corpus as decimal (default 0.08)",
                },
                "inflation_rate": {
                    "type": "number",
                    "description": "Annual inflation rate as decimal (default 0.06)",
                },
            },
            "required": ["corpus", "monthly_withdrawal"],
        },
    },
    {
        "name": "calculate_required_corpus",
        "description": (
            "Calculate how much retirement corpus is needed to generate "
            "a desired monthly income for N years."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "monthly_income_needed": {
                    "type": "number",
                    "description": "Desired monthly income in rupees",
                },
                "years_needed": {
                    "type": "integer",
                    "description": "Number of years income is needed (default 30)",
                },
                "annual_return": {
                    "type": "number",
                    "description": "Expected annual return as decimal (default 0.08)",
                },
                "inflation_rate": {
                    "type": "number",
                    "description": "Annual inflation rate as decimal (default 0.06)",
                },
            },
            "required": ["monthly_income_needed"],
        },
    },
    {
        "name": "analyze_prepayment",
        "description": (
            "Analyze the impact of a lump-sum loan prepayment. "
            "Shows months saved, interest saved, and new tenure."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "principal": {
                    "type": "number",
                    "description": "Outstanding loan amount in rupees",
                },
                "annual_rate": {
                    "type": "number",
                    "description": "Annual interest rate as percentage (e.g., 8.5)",
                },
                "tenure_months": {
                    "type": "integer",
                    "description": "Remaining loan tenure in months",
                },
                "prepayment_amount": {
                    "type": "number",
                    "description": "Lump sum prepayment amount in rupees",
                },
                "prepayment_at_month": {
                    "type": "integer",
                    "description": "Month at which prepayment is made (default 12)",
                },
            },
            "required": ["principal", "annual_rate", "tenure_months", "prepayment_amount"],
        },
    },
    {
        "name": "prepay_vs_invest",
        "description": (
            "Should you prepay your loan or invest the money? "
            "Compares interest saved by prepaying vs expected investment returns "
            "and gives a clear recommendation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "loan_principal": {
                    "type": "number",
                    "description": "Outstanding loan amount in rupees",
                },
                "loan_rate": {
                    "type": "number",
                    "description": "Annual loan interest rate as percentage (e.g., 8.5)",
                },
                "loan_tenure_months": {
                    "type": "integer",
                    "description": "Remaining loan tenure in months",
                },
                "lump_sum": {
                    "type": "number",
                    "description": "Amount available for prepayment or investment",
                },
                "investment_return": {
                    "type": "number",
                    "description": "Expected annual investment return as percentage (default 12.0)",
                },
            },
            "required": ["loan_principal", "loan_rate", "loan_tenure_months", "lump_sum"],
        },
    },
    {
        "name": "compare_tax_regimes",
        "description": (
            "Compare old vs new income tax regime and recommend the better option. "
            "Uses the user's loaded financial profile. Returns tax under both regimes, "
            "recommended regime, annual tax saving, and unused deduction room."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "compute_health_score",
        "description": (
            "Compute the Money Health Score (0-100) across 6 dimensions: "
            "emergency fund, insurance, diversification, debt health, "
            "tax efficiency, and retirement readiness. Uses user's loaded profile."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # --- Investment Screener Tools ---
    {
        "name": "search_mutual_funds",
        "description": (
            "Search Indian mutual fund schemes by name or keyword. "
            "Returns matching Direct Growth plans with scheme codes. "
            "Use this to find funds in a category like 'large cap', 'flexi cap', 'ELSS', 'liquid', etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword (e.g., 'large cap', 'HDFC flexi cap', 'ELSS tax saver', 'nifty 50 index')",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_fund_details",
        "description": (
            "Get detailed mutual fund information including NAV, category, fund house, "
            "and annualized 1Y/3Y/5Y returns calculated from real historical data. "
            "Requires a scheme_code from search_mutual_funds."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "scheme_code": {
                    "type": "string",
                    "description": "AMFI scheme code (e.g., '120503'). Get this from search_mutual_funds first.",
                },
            },
            "required": ["scheme_code"],
        },
    },
    {
        "name": "suggest_asset_allocation",
        "description": (
            "Suggest a model asset allocation based on investment goal timeline and risk appetite. "
            "Returns recommended MF category percentages (not specific funds). "
            "Categories: Large Cap, Flexi Cap, Mid Cap, Small Cap, ELSS, Index, Hybrid, Debt, Liquid."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal_years": {
                    "type": "integer",
                    "description": "Number of years until the investment goal (e.g., 5 for 5 years)",
                },
                "risk_level": {
                    "type": "string",
                    "description": "Risk appetite: 'conservative', 'moderate', or 'aggressive'. Default 'moderate'.",
                },
            },
            "required": ["goal_years"],
        },
    },
    {
        "name": "screen_stocks",
        "description": (
            "Screen Nifty 50 Indian stocks with basic fundamentals — price, P/E ratio, "
            "market cap, dividend yield, 52-week range. Optionally filter by sector."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sector": {
                    "type": "string",
                    "description": "Filter by sector (e.g., 'IT', 'Banking', 'FMCG', 'Pharma', 'Energy', 'Auto'). Optional.",
                },
            },
            "required": [],
        },
    },
    # --- Portfolio X-Ray Tools ---
    {
        "name": "analyze_portfolio_xray",
        "description": (
            "Run a full Portfolio X-Ray on the user's loaded mutual fund portfolio. "
            "Returns XIRR (per-fund and overall), fund overlap analysis, expense ratio drag, "
            "category allocation, and regular-to-direct savings potential. "
            "Requires a portfolio to be loaded (CAS upload or demo)."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "detect_behavioral_patterns",
        "description": (
            "Detect behavioral biases in the user's loaded mutual fund portfolio based on "
            "transaction history. Detects: SIP Panic Stop, Buy High Sell Low, Theme Chasing, "
            "Excessive Switching, Recency Bias, Disposition Effect. "
            "Research-backed (Chadha 2024, ACR Journal). Requires a portfolio to be loaded."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# --- Format Converters ---

def tools_to_openai_format(tools: list[dict]) -> list[dict]:
    """Convert to OpenAI / Groq / DeepSeek function calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in tools
    ]


def tools_to_gemini_format(tools: list[dict]) -> list[dict]:
    """Convert to Google Gemini function calling format."""
    declarations = []
    for t in tools:
        decl = {
            "name": t["name"],
            "description": t["description"],
        }
        # Gemini needs parameters only if there are properties
        if t["parameters"].get("properties"):
            decl["parameters"] = t["parameters"]
        declarations.append(decl)
    return declarations


def tools_to_anthropic_format(tools: list[dict]) -> list[dict]:
    """Convert to Anthropic Claude tool use format."""
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        }
        for t in tools
    ]


# --- Agent-to-Tool Mapping ---

AGENT_TOOLS = {
    "tax_agent": ["compare_tax_regimes", "calculate_emi"],
    "portfolio_agent": ["search_mutual_funds", "get_fund_details", "analyze_portfolio_xray", "detect_behavioral_patterns"],
    "goal_agent": ["calculate_fire", "calculate_required_corpus", "calculate_swp", "calculate_emi", "suggest_asset_allocation"],
    "health_agent": ["compute_health_score", "compare_tax_regimes"],
    "life_event_agent": ["calculate_emi", "calculate_swp", "calculate_required_corpus"],
    "screener_agent": ["search_mutual_funds", "get_fund_details", "suggest_asset_allocation", "screen_stocks"],
    "general_agent": [t["name"] for t in TOOLS],  # All 12 tools
    "supervisor": [t["name"] for t in TOOLS],
}


def get_tools_for_agent(agent_name: str) -> list[dict]:
    """Get tool definitions for a specific agent."""
    tool_names = AGENT_TOOLS.get(agent_name, AGENT_TOOLS["general_agent"])
    if not tool_names:
        return []
    return [t for t in TOOLS if t["name"] in tool_names]
