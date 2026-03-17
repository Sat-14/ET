"""Live Mutual Fund NAV Fetcher using MFAPI.in.

Fetches real-time and historical NAV data for Indian mutual funds.
No API key required - completely free.

API: https://api.mfapi.in
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Optional
from functools import lru_cache

import httpx


MFAPI_BASE = "https://api.mfapi.in"

# Cache for scheme list (loaded once)
_scheme_cache: dict[str, str] = {}


async def fetch_latest_nav(scheme_code: str) -> Optional[dict]:
    """Fetch latest NAV for a mutual fund scheme.

    Args:
        scheme_code: AMFI scheme code (e.g., "119551" for HDFC Flexi Cap)

    Returns:
        {"scheme_code": "119551", "scheme_name": "...", "nav": 45.67, "date": "2026-03-15"}
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{MFAPI_BASE}/mf/{scheme_code}/latest")
            resp.raise_for_status()
            data = resp.json()

            nav_data = data.get("data", [{}])[0] if data.get("data") else {}
            return {
                "scheme_code": scheme_code,
                "scheme_name": data.get("meta", {}).get("scheme_name", ""),
                "scheme_category": data.get("meta", {}).get("scheme_category", ""),
                "scheme_type": data.get("meta", {}).get("scheme_type", ""),
                "fund_house": data.get("meta", {}).get("fund_house", ""),
                "nav": float(nav_data.get("nav", 0)),
                "date": nav_data.get("date", ""),
            }
    except Exception:
        return None


async def fetch_historical_nav(
    scheme_code: str,
    period: str = "1Y",
) -> list[dict]:
    """Fetch historical NAV data for a scheme.

    Args:
        scheme_code: AMFI scheme code
        period: "1M", "3M", "6M", "1Y", "3Y", "5Y", "all"

    Returns:
        List of {"date": "15-03-2026", "nav": "45.67"}
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{MFAPI_BASE}/mf/{scheme_code}")
            resp.raise_for_status()
            data = resp.json()

            all_navs = data.get("data", [])
            if not all_navs:
                return []

            # Filter by period
            cutoff = _period_to_cutoff(period)
            filtered = []
            for entry in all_navs:
                try:
                    nav_date = datetime.strptime(entry["date"], "%d-%m-%Y").date()
                    if nav_date >= cutoff:
                        filtered.append({
                            "date": nav_date.isoformat(),
                            "nav": float(entry["nav"]),
                        })
                except (ValueError, KeyError):
                    continue

            return list(reversed(filtered))  # Oldest first
    except Exception:
        return []


def _period_to_cutoff(period: str) -> date:
    """Convert period string to cutoff date."""
    today = date.today()
    mapping = {
        "1M": timedelta(days=30),
        "3M": timedelta(days=90),
        "6M": timedelta(days=180),
        "1Y": timedelta(days=365),
        "3Y": timedelta(days=365 * 3),
        "5Y": timedelta(days=365 * 5),
        "all": timedelta(days=365 * 30),
    }
    delta = mapping.get(period.upper(), timedelta(days=365))
    return today - delta


async def search_schemes(query: str) -> list[dict]:
    """Search for mutual fund schemes by name.

    Returns list of {"scheme_code": "119551", "scheme_name": "HDFC Flexi Cap..."}
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{MFAPI_BASE}/mf/search?q={query}")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        # Fallback: fetch all and filter locally
        return await _search_all_schemes(query)


async def _search_all_schemes(query: str) -> list[dict]:
    """Fallback search - fetch all schemes and filter."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{MFAPI_BASE}/mf")
            resp.raise_for_status()
            all_schemes = resp.json()

            query_lower = query.lower()
            matches = [
                s for s in all_schemes
                if query_lower in s.get("schemeName", "").lower()
            ]
            return [
                {"scheme_code": str(s["schemeCode"]), "scheme_name": s["schemeName"]}
                for s in matches[:20]
            ]
    except Exception:
        return []


async def fetch_nav_for_portfolio_holdings(
    holdings: list[dict],
) -> list[dict]:
    """Fetch latest NAVs for all holdings in a portfolio.

    Args:
        holdings: List of {"scheme_name": "...", "amfi_code": "119551", "units": 100}

    Returns:
        Same list enriched with current_nav and current_value
    """
    enriched = []
    for h in holdings:
        code = h.get("amfi_code") or h.get("scheme_code", "")
        if code:
            nav_data = await fetch_latest_nav(str(code))
            if nav_data and nav_data["nav"] > 0:
                h["current_nav"] = nav_data["nav"]
                h["current_value"] = nav_data["nav"] * h.get("units", 0)
                h["nav_date"] = nav_data["date"]
                h["fund_house"] = nav_data.get("fund_house", "")
                h["scheme_category"] = nav_data.get("scheme_category", "")
        enriched.append(h)
    return enriched


# --- Popular Indian MF scheme codes for quick reference ---
POPULAR_SCHEMES = {
    # Large Cap / Index
    "Nifty 50 Index (UTI)": "120716",
    "Nifty 50 Index (HDFC)": "120505",
    "Sensex Index (SBI)": "119757",
    # Flexi Cap
    "HDFC Flexi Cap": "119551",
    "Parag Parikh Flexi Cap": "122639",
    "Kotak Flexicap": "112090",
    # Mid Cap
    "HDFC Mid Cap Opportunities": "104483",
    "Kotak Emerging Equity": "108413",
    # Small Cap
    "SBI Small Cap": "125497",
    "Nippon Small Cap": "113177",
    # ELSS
    "Mirae Asset ELSS": "120503",
    "Quant ELSS": "100186",
    # Debt
    "HDFC Short Term Debt": "104482",
    "SBI Magnum Gilt": "100189",
    # Hybrid
    "HDFC Balanced Advantage": "100115",
    "ICICI Balanced Advantage": "120587",
}
