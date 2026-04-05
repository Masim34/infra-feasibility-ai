"""
app/models/country_risk.py
Country-level macroeconomic and political risk scoring engine.
Outputs composite risk score and risk-adjusted discount rate.
"""
from typing import Dict, Optional

# Political stability proxy scores (0-100, higher = more stable)
# Source: World Bank Governance Indicators proxy
POLITICAL_STABILITY_SCORES = {
    "GB": 75, "DE": 80, "FR": 72, "US": 68, "AU": 82,
    "SA": 55, "AE": 70, "QA": 72, "KW": 65,
    "IQ": 20, "SL": 35, "MG": 38, "PK": 32, "KZ": 48,
    "ZA": 42, "NG": 28, "KE": 45, "ET": 30, "TZ": 50,
    "IN": 52, "CN": 55, "VN": 58, "ID": 50, "PH": 40,
    "BR": 42, "MX": 40, "CO": 38, "AR": 35, "CL": 65,
    "EG": 38, "MA": 55, "TN": 48, "GH": 60, "SN": 58,
}

# Currency risk proxy (annual FX volatility %, lower = more stable)
CURRENCY_VOLATILITY = {
    "GB": 0.06, "DE": 0.06, "FR": 0.06, "US": 0.04, "AU": 0.08,
    "SA": 0.03, "AE": 0.02, "QA": 0.02, "KW": 0.02,
    "IQ": 0.18, "SL": 0.35, "MG": 0.25, "PK": 0.30, "KZ": 0.15,
    "ZA": 0.14, "NG": 0.20, "KE": 0.10, "ET": 0.15, "TZ": 0.08,
    "IN": 0.06, "CN": 0.04, "VN": 0.04, "ID": 0.08, "PH": 0.06,
    "BR": 0.14, "MX": 0.10, "CO": 0.12, "AR": 0.40, "CL": 0.08,
    "EG": 0.20, "MA": 0.06, "TN": 0.08, "GH": 0.15, "SN": 0.05,
}

BASE_RISK_FREE_RATE = 0.045   # US 10-year treasury proxy
MARKET_RISK_PREMIUM = 0.055   # Global equity risk premium


def score_country_risk(
    country_code: str,
    gdp_growth: Optional[float] = None,
    inflation: Optional[float] = None,
    political_stability: Optional[float] = None,
    currency_volatility: Optional[float] = None,
) -> Dict:
    """
    Calculate composite country risk score (0-100, lower = less risk).
    Inputs come from World Bank API or manual override.
    """
    cc = country_code.upper()

    # Use provided values or fall back to defaults
    pol_stability = political_stability or POLITICAL_STABILITY_SCORES.get(cc, 40)
    fx_vol = currency_volatility or CURRENCY_VOLATILITY.get(cc, 0.15)

    # Scoring components (0-100, higher = more risk)
    pol_risk_score = 100 - pol_stability  # invert: lower stability = higher risk

    # GDP growth: < 0 is very risky, 5%+ is low risk
    if gdp_growth is None:
        gdp_risk_score = 50  # neutral
    elif gdp_growth >= 5:
        gdp_risk_score = 15
    elif gdp_growth >= 3:
        gdp_risk_score = 30
    elif gdp_growth >= 0:
        gdp_risk_score = 50
    elif gdp_growth >= -3:
        gdp_risk_score = 75
    else:
        gdp_risk_score = 90

    # Inflation: > 20% is very risky, < 5% is low risk
    if inflation is None:
        inflation_risk_score = 40
    elif inflation < 3:
        inflation_risk_score = 10
    elif inflation < 7:
        inflation_risk_score = 25
    elif inflation < 15:
        inflation_risk_score = 50
    elif inflation < 30:
        inflation_risk_score = 75
    else:
        inflation_risk_score = 95

    # Currency risk: scale FX vol to 0-100
    currency_risk_score = min(100, fx_vol * 250)

    # Weighted composite score
    weights = {
        "political": 0.35,
        "gdp": 0.20,
        "inflation": 0.25,
        "currency": 0.20,
    }
    composite_score = (
        pol_risk_score * weights["political"]
        + gdp_risk_score * weights["gdp"]
        + inflation_risk_score * weights["inflation"]
        + currency_risk_score * weights["currency"]
    )
    composite_score = round(composite_score, 2)

    # Risk category
    if composite_score < 25:
        risk_category = "Low"
    elif composite_score < 45:
        risk_category = "Moderate"
    elif composite_score < 65:
        risk_category = "High"
    else:
        risk_category = "Very High"

    # Risk-adjusted discount rate (CAPM-style)
    country_risk_premium = composite_score / 1000   # 1% per 10 score points
    risk_adjusted_rate = BASE_RISK_FREE_RATE + MARKET_RISK_PREMIUM + country_risk_premium

    return {
        "country_code": cc,
        "composite_risk_score": composite_score,
        "risk_category": risk_category,
        "risk_adjusted_discount_rate": round(risk_adjusted_rate, 4),
        "component_scores": {
            "political_risk": round(pol_risk_score, 2),
            "gdp_risk": round(gdp_risk_score, 2),
            "inflation_risk": round(inflation_risk_score, 2),
            "currency_risk": round(currency_risk_score, 2),
        },
        "inputs_used": {
            "gdp_growth": gdp_growth,
            "inflation": inflation,
            "political_stability_score": pol_stability,
            "currency_volatility": fx_vol,
        },
        "base_risk_free_rate": BASE_RISK_FREE_RATE,
        "market_risk_premium": MARKET_RISK_PREMIUM,
        "country_risk_premium": round(country_risk_premium, 4),
    }


def get_risk_adjusted_rate(country_code: str, macro_data: Dict = None) -> float:
    """Quick helper: returns just the risk-adjusted discount rate."""
    kwargs = {}
    if macro_data:
        kwargs["gdp_growth"] = macro_data.get("gdp_growth", {}).get("latest")
        kwargs["inflation"] = macro_data.get("inflation", {}).get("latest")
    result = score_country_risk(country_code, **kwargs)
    return result["risk_adjusted_discount_rate"]
