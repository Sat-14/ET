"""Tool executor — maps tool names to engine functions and runs them.

All results are returned as JSON strings for LLM consumption.
Parameter casting handles LLM quirks (sending "240" instead of 240).
"""

from __future__ import annotations

import json

from src.engines.emi_calculator import calculate_emi, analyze_prepayment, prepay_vs_invest
from src.engines.goal_calculator import calculate_fire
from src.engines.swp_calculator import calculate_swp, calculate_required_corpus
from src.engines.tax_calculator import compare_regimes
from src.engines.health_scorer import compute_money_health_score


def execute_tool(
    tool_name: str,
    arguments: dict,
    user_profile=None,
) -> str:
    """Execute a tool call and return JSON string result.

    Args:
        tool_name: Name of the tool from LLM's function call.
        arguments: Dict of arguments (may have string values from LLM).
        user_profile: IndividualProfile object for profile-dependent tools.

    Returns:
        JSON string of the result.
    """
    try:
        if tool_name == "calculate_emi":
            result = calculate_emi(
                principal=float(arguments["principal"]),
                annual_rate=float(arguments["annual_rate"]),
                tenure_months=int(float(arguments["tenure_months"])),
            )
            return json.dumps(result.to_dict(), default=str)

        elif tool_name == "calculate_fire":
            result = calculate_fire(
                current_age=int(float(arguments["current_age"])),
                annual_expenses=float(arguments["annual_expenses"]),
                current_corpus=float(arguments.get("current_corpus", 0)),
                monthly_investment=float(arguments["monthly_investment"]),
                expected_return=float(arguments.get("expected_return", 0.10)),
                inflation_rate=float(arguments.get("inflation_rate", 0.06)),
                safe_withdrawal_rate=float(arguments.get("safe_withdrawal_rate", 0.04)),
            )
            return json.dumps(result.to_dict(), default=str)

        elif tool_name == "calculate_swp":
            result = calculate_swp(
                corpus=float(arguments["corpus"]),
                monthly_withdrawal=float(arguments["monthly_withdrawal"]),
                annual_return=float(arguments.get("annual_return", 0.08)),
                inflation_rate=float(arguments.get("inflation_rate", 0.06)),
            )
            return json.dumps(result.to_dict(), default=str)

        elif tool_name == "calculate_required_corpus":
            result = calculate_required_corpus(
                monthly_income_needed=float(arguments["monthly_income_needed"]),
                years_needed=int(float(arguments.get("years_needed", 30))),
                annual_return=float(arguments.get("annual_return", 0.08)),
                inflation_rate=float(arguments.get("inflation_rate", 0.06)),
            )
            return json.dumps({"required_corpus": round(result)}, default=str)

        elif tool_name == "analyze_prepayment":
            result = analyze_prepayment(
                principal=float(arguments["principal"]),
                annual_rate=float(arguments["annual_rate"]),
                tenure_months=int(float(arguments["tenure_months"])),
                prepayment_amount=float(arguments["prepayment_amount"]),
                prepayment_at_month=int(float(arguments.get("prepayment_at_month", 12))),
            )
            return json.dumps(result.to_dict(), default=str)

        elif tool_name == "prepay_vs_invest":
            result = prepay_vs_invest(
                loan_principal=float(arguments["loan_principal"]),
                loan_rate=float(arguments["loan_rate"]),
                loan_tenure_months=int(float(arguments["loan_tenure_months"])),
                lump_sum=float(arguments["lump_sum"]),
                investment_return=float(arguments.get("investment_return", 12.0)),
            )
            return json.dumps(result.to_dict(), default=str)

        elif tool_name == "compare_tax_regimes":
            if user_profile is None:
                return json.dumps({
                    "error": "No user profile loaded. Please provide your salary and deduction details first, "
                    "or use the sidebar in the dashboard to enter your profile."
                })
            result = compare_regimes(user_profile)
            return json.dumps(result.to_dict(), default=str)

        elif tool_name == "compute_health_score":
            if user_profile is None:
                return json.dumps({
                    "error": "No user profile loaded. Please provide your financial details first, "
                    "or use the sidebar in the dashboard to enter your profile."
                })
            result = compute_money_health_score(user_profile)
            return json.dumps(result.to_dict(), default=str)

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except (KeyError, ValueError, TypeError) as e:
        return json.dumps({"error": f"Invalid parameters for {tool_name}: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Tool execution failed: {str(e)}"})
