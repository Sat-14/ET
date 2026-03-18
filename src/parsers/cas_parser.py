"""CAS (Consolidated Account Statement) Parser Wrapper.

Wraps the casparser library to parse CAMS/KFintech CAS PDFs
and convert them into our internal Portfolio model.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.models.portfolio import (
    Portfolio,
    FundHolding,
    Transaction,
    TransactionType,
    FundCategory,
    PlanType,
)


# Mapping from casparser transaction types to our types
TXN_TYPE_MAP = {
    "PURCHASE": TransactionType.PURCHASE,
    "PURCHASE_SIP": TransactionType.SIP,
    "REDEMPTION": TransactionType.REDEMPTION,
    "SWITCH_IN": TransactionType.SWITCH_IN,
    "SWITCH_OUT": TransactionType.SWITCH_OUT,
    "DIVIDEND_PAYOUT": TransactionType.DIVIDEND_PAYOUT,
    "DIVIDEND_REINVESTMENT": TransactionType.DIVIDEND_REINVEST,
}

# Heuristic fund category detection from scheme name
CATEGORY_KEYWORDS = {
    FundCategory.LARGE_CAP: ["large cap", "largecap", "nifty 50", "sensex", "bluechip", "large & mid"],
    FundCategory.MID_CAP: ["mid cap", "midcap"],
    FundCategory.SMALL_CAP: ["small cap", "smallcap"],
    FundCategory.MULTI_CAP: ["multi cap", "multicap"],
    FundCategory.FLEXI_CAP: ["flexi cap", "flexicap"],
    FundCategory.ELSS: ["elss", "tax saver", "tax saving"],
    FundCategory.SECTORAL: ["banking", "pharma", "infrastructure", "it ", "consumption", "psu"],
    FundCategory.THEMATIC: ["thematic", "esg", "quant", "momentum", "dividend yield"],
    FundCategory.INDEX: ["index", "nifty", "sensex", "etf"],
    FundCategory.DEBT_SHORT: ["short duration", "ultra short", "low duration", "money market", "floater"],
    FundCategory.DEBT_MEDIUM: ["medium duration", "corporate bond", "banking & psu"],
    FundCategory.DEBT_LONG: ["long duration", "gilt", "dynamic bond", "10 year"],
    FundCategory.LIQUID: ["liquid", "overnight"],
    FundCategory.HYBRID_AGGRESSIVE: ["aggressive hybrid", "balanced advantage", "equity hybrid"],
    FundCategory.HYBRID_CONSERVATIVE: ["conservative hybrid", "equity savings", "arbitrage"],
    FundCategory.INTERNATIONAL: ["international", "global", "us equity", "nasdaq", "s&p 500"],
    FundCategory.GOLD: ["gold"],
}


def _detect_category(scheme_name: str) -> FundCategory:
    """Detect fund category from scheme name using keywords."""
    name_lower = scheme_name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return category
    return FundCategory.OTHER


def _detect_plan_type(scheme_name: str) -> PlanType:
    """Detect if fund is direct or regular plan."""
    name_lower = scheme_name.lower()
    if "direct" in name_lower:
        return PlanType.DIRECT
    return PlanType.REGULAR


def parse_cas_pdf(
    file_path: str | Path,
    password: str = "",
) -> Portfolio:
    """Parse a CAS PDF and return a Portfolio object.

    Args:
        file_path: Path to the CAS PDF file.
        password: PDF password (usually the PAN-based password).

    Returns:
        Portfolio with holdings and transactions.
    """
    try:
        import casparser
        data = casparser.read_cas_pdf(str(file_path), password=password)
    except ImportError:
        raise ImportError(
            "casparser is required. Install with: pip install casparser"
        )
    except Exception as e:
        raise ValueError(f"Failed to parse CAS PDF: {e}")

    portfolio = Portfolio(
        investor_name=data.get("investor_info", {}).get("name", ""),
        investor_email=data.get("investor_info", {}).get("email", ""),
    )

    folios = data.get("folios", [])
    for folio in folios:
        folio_number = folio.get("folio", "")
        schemes = folio.get("schemes", [])

        for scheme in schemes:
            scheme_name = scheme.get("scheme", "")
            isin = scheme.get("isin", None)
            amfi_code = scheme.get("amfi", None)

            # Parse transactions
            transactions = []
            total_invested = 0.0
            total_units = 0.0

            for txn_data in scheme.get("transactions", []):
                txn_type_str = txn_data.get("type", "").upper()
                txn_type = TXN_TYPE_MAP.get(txn_type_str, TransactionType.PURCHASE)

                try:
                    txn_date = txn_data.get("date")
                    if isinstance(txn_date, str):
                        txn_date = datetime.strptime(txn_date, "%Y-%m-%d").date()
                    elif isinstance(txn_date, datetime):
                        txn_date = txn_date.date()
                except (ValueError, TypeError):
                    continue

                amount = float(txn_data.get("amount", 0))
                units = float(txn_data.get("units", 0))
                nav = float(txn_data.get("nav", 0))

                txn = Transaction(
                    date=txn_date,
                    type=txn_type,
                    amount=abs(amount),
                    units=abs(units),
                    nav=nav,
                    scheme_name=scheme_name,
                    folio=folio_number,
                    isin=isin,
                    amfi_code=amfi_code,
                )
                transactions.append(txn)

                if txn.is_inflow:
                    total_invested += abs(amount)
                    total_units += abs(units)
                else:
                    total_units -= abs(units)

            # Get closing balance
            valuation = scheme.get("valuation", {})
            closing_units = float(valuation.get("units", total_units))
            closing_nav = float(valuation.get("nav", 0))

            holding = FundHolding(
                scheme_name=scheme_name,
                folio=folio_number,
                units=closing_units,
                current_nav=closing_nav,
                invested_amount=total_invested,
                isin=isin,
                amfi_code=amfi_code,
                category=_detect_category(scheme_name),
                plan_type=_detect_plan_type(scheme_name),
                transactions=transactions,
            )
            portfolio.holdings.append(holding)

    return portfolio


def parse_cas_from_dict(data: dict) -> Portfolio:
    """Parse portfolio from a dictionary (for manual entry or API input).

    Expects format:
    {
        "investor_name": "...",
        "holdings": [
            {
                "scheme_name": "...",
                "units": 100.5,
                "current_nav": 45.5,
                "invested_amount": 50000,
                "category": "large_cap",
                "plan_type": "direct",
                "expense_ratio": 0.5,
                "transactions": [
                    {"date": "2024-01-15", "type": "sip", "amount": 5000, "units": 110, "nav": 45.5},
                    ...
                ]
            },
            ...
        ]
    }
    """
    portfolio = Portfolio(investor_name=data.get("investor_name", ""))

    for h_data in data.get("holdings", []):
        transactions = []
        for t_data in h_data.get("transactions", []):
            try:
                txn_date = datetime.strptime(t_data["date"], "%Y-%m-%d").date()
            except (ValueError, KeyError):
                continue

            txn_type_str = t_data.get("type", "purchase").upper()
            txn_type = TXN_TYPE_MAP.get(txn_type_str, TransactionType.PURCHASE)

            transactions.append(Transaction(
                date=txn_date,
                type=txn_type,
                amount=float(t_data.get("amount", 0)),
                units=float(t_data.get("units", 0)),
                nav=float(t_data.get("nav", 0)),
                scheme_name=h_data.get("scheme_name", ""),
                folio=h_data.get("folio", ""),
            ))

        category_str = h_data.get("category", "other")
        try:
            category = FundCategory(category_str)
        except ValueError:
            category = _detect_category(h_data.get("scheme_name", ""))

        plan_str = h_data.get("plan_type", "regular")
        try:
            plan_type = PlanType(plan_str)
        except ValueError:
            plan_type = _detect_plan_type(h_data.get("scheme_name", ""))

        holding = FundHolding(
            scheme_name=h_data.get("scheme_name", ""),
            folio=h_data.get("folio", ""),
            units=float(h_data.get("units", 0)),
            current_nav=float(h_data.get("current_nav", 0)),
            invested_amount=float(h_data.get("invested_amount", 0)),
            category=category,
            plan_type=plan_type,
            expense_ratio=float(h_data.get("expense_ratio", 0)),
            transactions=transactions,
        )
        portfolio.holdings.append(holding)

    return portfolio
