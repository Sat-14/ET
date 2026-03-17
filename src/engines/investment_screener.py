"""Investment Screener Engine — real MF & stock data for informed decisions.

Uses mftool for mutual fund data and yfinance for Indian stock data.
Recommends CATEGORIES (not specific schemes) based on goal and risk.
Shows real performance data so users can explore and compare.

Disclaimer: All data is factual/historical. Not a buy/sell recommendation.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# Mutual Fund Categories — search terms for mftool
# ---------------------------------------------------------------------------

MF_CATEGORIES = {
    "large_cap": {"label": "Large Cap", "search": "large cap direct plan growth", "risk": "Moderate", "min_years": 5},
    "flexi_cap": {"label": "Flexi Cap", "search": "flexi cap direct plan growth", "risk": "Moderate-High", "min_years": 5},
    "mid_cap": {"label": "Mid Cap", "search": "mid cap direct plan growth", "risk": "High", "min_years": 7},
    "small_cap": {"label": "Small Cap", "search": "small cap direct plan growth", "risk": "Very High", "min_years": 7},
    "elss": {"label": "ELSS Tax Saver", "search": "elss tax saver direct plan growth", "risk": "High", "min_years": 3},
    "index_nifty50": {"label": "Nifty 50 Index", "search": "nifty 50 index direct plan growth", "risk": "Moderate", "min_years": 5},
    "hybrid_aggressive": {"label": "Aggressive Hybrid", "search": "aggressive hybrid direct plan growth", "risk": "Moderate", "min_years": 5},
    "debt_short": {"label": "Short Duration Debt", "search": "short duration direct plan growth", "risk": "Low", "min_years": 1},
    "liquid": {"label": "Liquid Fund", "search": "liquid direct plan growth", "risk": "Very Low", "min_years": 0},
}

# ---------------------------------------------------------------------------
# Nifty 50 representative stocks
# ---------------------------------------------------------------------------

NIFTY_50_STOCKS = [
    {"ticker": "RELIANCE.NS", "name": "Reliance Industries", "sector": "Energy"},
    {"ticker": "TCS.NS", "name": "Tata Consultancy Services", "sector": "IT"},
    {"ticker": "HDFCBANK.NS", "name": "HDFC Bank", "sector": "Banking"},
    {"ticker": "INFY.NS", "name": "Infosys", "sector": "IT"},
    {"ticker": "ICICIBANK.NS", "name": "ICICI Bank", "sector": "Banking"},
    {"ticker": "HINDUNILVR.NS", "name": "Hindustan Unilever", "sector": "FMCG"},
    {"ticker": "ITC.NS", "name": "ITC", "sector": "FMCG"},
    {"ticker": "SBIN.NS", "name": "State Bank of India", "sector": "Banking"},
    {"ticker": "BHARTIARTL.NS", "name": "Bharti Airtel", "sector": "Telecom"},
    {"ticker": "KOTAKBANK.NS", "name": "Kotak Mahindra Bank", "sector": "Banking"},
    {"ticker": "LT.NS", "name": "Larsen & Toubro", "sector": "Infrastructure"},
    {"ticker": "AXISBANK.NS", "name": "Axis Bank", "sector": "Banking"},
    {"ticker": "ASIANPAINT.NS", "name": "Asian Paints", "sector": "Consumer"},
    {"ticker": "MARUTI.NS", "name": "Maruti Suzuki", "sector": "Auto"},
    {"ticker": "TITAN.NS", "name": "Titan Company", "sector": "Consumer"},
    {"ticker": "SUNPHARMA.NS", "name": "Sun Pharma", "sector": "Pharma"},
    {"ticker": "WIPRO.NS", "name": "Wipro", "sector": "IT"},
    {"ticker": "HCLTECH.NS", "name": "HCL Technologies", "sector": "IT"},
    {"ticker": "ULTRACEMCO.NS", "name": "UltraTech Cement", "sector": "Cement"},
    {"ticker": "POWERGRID.NS", "name": "Power Grid Corp", "sector": "Power"},
]


# ---------------------------------------------------------------------------
# MF Search & Details (uses mftool)
# ---------------------------------------------------------------------------

def search_mutual_funds(query: str, limit: int = 8) -> list[dict]:
    """Search mutual fund schemes by name/keyword.

    Returns Direct Growth plans matching the query, sorted by relevance.
    """
    try:
        from mftool import Mftool
        mf = Mftool()
        all_codes = mf.get_scheme_codes()
    except ImportError:
        return [{"error": "mftool not installed. Install with: pip install mftool"}]
    except Exception as e:
        return [{"error": f"Could not fetch fund data: {str(e)}"}]

    query_lower = query.lower()
    # Split query into keywords for flexible matching
    keywords = query_lower.split()

    matches = []
    for code, name in all_codes.items():
        name_lower = name.lower()
        # Must be Direct Growth plan
        if "direct" not in name_lower or "growth" not in name_lower:
            continue
        # All query keywords must appear in scheme name
        if all(kw in name_lower for kw in keywords):
            matches.append({"scheme_code": code, "scheme_name": name})

    # Shorter names tend to be more relevant (less noise)
    matches.sort(key=lambda x: len(x["scheme_name"]))
    return matches[:limit]


def get_fund_details(scheme_code: str) -> dict:
    """Get detailed fund information with NAV and calculated returns."""
    try:
        from mftool import Mftool
        mf = Mftool()
    except ImportError:
        return {"error": "mftool not installed"}

    try:
        details = mf.get_scheme_details(scheme_code)
        if not details:
            return {"error": f"Scheme {scheme_code} not found"}

        result = {
            "scheme_code": scheme_code,
            "scheme_name": details.get("scheme_name", ""),
            "scheme_category": details.get("scheme_category", ""),
            "scheme_type": details.get("scheme_type", ""),
            "fund_house": details.get("fund_house", ""),
            "nav": details.get("nav", "N/A"),
            "nav_date": details.get("date", ""),
        }

        # Fetch historical NAV for return calculation
        try:
            history = mf.get_scheme_historical_nav(scheme_code)
            if history and "data" in history:
                nav_data = history["data"]
                if nav_data:
                    current_nav = float(nav_data[0]["nav"])
                    today = datetime.now()

                    for label, days in [("return_1y", 365), ("return_3y", 1095), ("return_5y", 1825)]:
                        target = today - timedelta(days=days)
                        for entry in nav_data:
                            try:
                                d = datetime.strptime(entry["date"], "%d-%m-%Y")
                                if d <= target:
                                    past_nav = float(entry["nav"])
                                    years = days / 365.25
                                    annualized = (math.pow(current_nav / past_nav, 1 / years) - 1) * 100
                                    result[label] = round(annualized, 2)
                                    break
                            except (ValueError, KeyError):
                                continue
        except Exception:
            pass  # Returns unavailable — NAV still shown

        return result

    except Exception as e:
        return {"error": f"Failed to fetch fund details: {str(e)}"}


# ---------------------------------------------------------------------------
# Asset Allocation Suggestion
# ---------------------------------------------------------------------------

def suggest_asset_allocation(goal_years: int, risk_level: str = "moderate") -> dict:
    """Suggest category-level asset allocation based on goal timeline & risk.

    Returns allocation percentages per MF category, not specific schemes.
    """
    risk_level = risk_level.lower()
    if risk_level not in ("conservative", "moderate", "aggressive"):
        risk_level = "moderate"

    # Time bucket
    if goal_years <= 1:
        bucket = "very_short"
    elif goal_years <= 3:
        bucket = "short"
    elif goal_years <= 5:
        bucket = "medium"
    elif goal_years <= 10:
        bucket = "long"
    else:
        bucket = "very_long"

    # Allocation models — (risk, time_bucket) → category %
    models = {
        ("conservative", "very_short"): {"liquid": 100},
        ("conservative", "short"): {"liquid": 30, "debt_short": 50, "hybrid_aggressive": 20},
        ("conservative", "medium"): {"debt_short": 30, "hybrid_aggressive": 40, "large_cap": 30},
        ("conservative", "long"): {"large_cap": 40, "hybrid_aggressive": 30, "debt_short": 20, "index_nifty50": 10},
        ("conservative", "very_long"): {"large_cap": 35, "flexi_cap": 25, "hybrid_aggressive": 20, "debt_short": 20},

        ("moderate", "very_short"): {"liquid": 80, "debt_short": 20},
        ("moderate", "short"): {"debt_short": 40, "hybrid_aggressive": 30, "large_cap": 30},
        ("moderate", "medium"): {"large_cap": 35, "flexi_cap": 25, "hybrid_aggressive": 20, "debt_short": 20},
        ("moderate", "long"): {"large_cap": 30, "flexi_cap": 25, "mid_cap": 15, "index_nifty50": 15, "debt_short": 15},
        ("moderate", "very_long"): {"large_cap": 25, "flexi_cap": 20, "mid_cap": 20, "small_cap": 10, "index_nifty50": 15, "elss": 10},

        ("aggressive", "very_short"): {"liquid": 60, "debt_short": 20, "hybrid_aggressive": 20},
        ("aggressive", "short"): {"large_cap": 40, "flexi_cap": 30, "hybrid_aggressive": 30},
        ("aggressive", "medium"): {"large_cap": 25, "flexi_cap": 25, "mid_cap": 25, "small_cap": 15, "elss": 10},
        ("aggressive", "long"): {"large_cap": 20, "flexi_cap": 20, "mid_cap": 25, "small_cap": 20, "index_nifty50": 15},
        ("aggressive", "very_long"): {"flexi_cap": 20, "mid_cap": 25, "small_cap": 25, "index_nifty50": 15, "elss": 15},
    }

    alloc = models.get((risk_level, bucket), models[("moderate", bucket)])

    categories = []
    for cat_key, pct in alloc.items():
        cat_info = MF_CATEGORIES.get(cat_key, {"label": cat_key, "risk": "", "min_years": 0})
        categories.append({
            "category": cat_info["label"],
            "allocation_pct": pct,
            "risk_level": cat_info.get("risk", ""),
            "min_investment_years": cat_info.get("min_years", 0),
        })

    notes = []
    if goal_years < 3:
        notes.append("Short timeframe — prioritize capital protection over returns.")
    if risk_level == "aggressive" and goal_years < 5:
        notes.append("Aggressive allocation with short timeline carries higher risk of loss.")
    if goal_years >= 7:
        notes.append("Long horizon allows equity exposure for inflation-beating returns.")
    if "elss" in alloc:
        notes.append("ELSS provides Section 80C tax benefit (up to Rs 1.5L/year, 3-year lock-in).")
    notes.append("Review and rebalance annually. Shift to debt as goal date approaches.")
    notes.append("This is a model allocation — not personalized advice. Consult a SEBI-registered advisor.")

    return {
        "goal_years": goal_years,
        "risk_level": risk_level,
        "time_bucket": bucket,
        "allocation": categories,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Stock Screener (uses yfinance)
# ---------------------------------------------------------------------------

def screen_stocks(sector: Optional[str] = None, limit: int = 10) -> list[dict]:
    """Screen Nifty 50 stocks with basic fundamentals via yfinance.

    Optionally filter by sector (IT, Banking, FMCG, Pharma, etc.).
    """
    stocks = NIFTY_50_STOCKS.copy()

    if sector:
        sector_lower = sector.lower()
        stocks = [s for s in stocks if sector_lower in s["sector"].lower()]

    try:
        import yfinance as yf
    except ImportError:
        return [{"error": "yfinance not installed. Install with: pip install yfinance"}]

    results = []
    for stock_info in stocks[:limit]:
        try:
            ticker = yf.Ticker(stock_info["ticker"])
            info = ticker.info

            results.append({
                "ticker": stock_info["ticker"].replace(".NS", ""),
                "name": stock_info["name"],
                "sector": stock_info["sector"],
                "price": round(info.get("currentPrice", info.get("regularMarketPrice", 0)), 2),
                "pe_ratio": round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else None,
                "market_cap_cr": round(info.get("marketCap", 0) / 1e7, 0) if info.get("marketCap") else None,
                "dividend_yield_pct": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
                "52w_high": round(info.get("fiftyTwoWeekHigh", 0), 2),
                "52w_low": round(info.get("fiftyTwoWeekLow", 0), 2),
            })
        except Exception:
            continue  # Skip unavailable stocks

    if not results:
        return [{"error": "Could not fetch stock data. Check internet connection."}]

    return results
