"""
app/models/scenarios.py
Best / Base / Worst case scenario analysis and sensitivity engine.
"""
from typing import Dict, List
from app.models.finance_advanced import full_financial_analysis


SCENARIO_ADJUSTMENTS = {
    "best": {
        "electricity_price_factor": 1.20,
        "capacity_factor_factor":   1.10,
        "capex_factor":             0.90,
        "opex_factor":              0.90,
        "discount_rate_delta":      -0.01,
    },
    "base": {
        "electricity_price_factor": 1.00,
        "capacity_factor_factor":   1.00,
        "capex_factor":             1.00,
        "opex_factor":              1.00,
        "discount_rate_delta":       0.00,
    },
    "worst": {
        "electricity_price_factor": 0.80,
        "capacity_factor_factor":   0.85,
        "capex_factor":             1.20,
        "opex_factor":              1.15,
        "discount_rate_delta":       0.02,
    },
}


def run_scenarios(
    project_name: str,
    capacity_mw: float,
    base_annual_mwh: float,
    base_electricity_price: float,
    capex_per_mw: float,
    opex_per_mw_year: float,
    discount_rate: float,
    project_life_years: int = 25,
    technology: str = "solar",
) -> Dict:
    """Run best/base/worst scenarios and return comparison."""
    results = {}
    for scenario, adj in SCENARIO_ADJUSTMENTS.items():
        adj_price   = base_electricity_price * adj["electricity_price_factor"]
        adj_mwh     = base_annual_mwh * adj["capacity_factor_factor"]
        adj_capex   = capex_per_mw * adj["capex_factor"]
        adj_opex    = opex_per_mw_year * adj["opex_factor"]
        adj_rate    = max(0.01, discount_rate + adj["discount_rate_delta"])
        result = full_financial_analysis(
            project_name=f"{project_name} ({scenario.title()})",
            capacity_mw=capacity_mw,
            annual_production_mwh=adj_mwh,
            electricity_price_usd_mwh=adj_price,
            capex_per_mw=adj_capex,
            opex_per_mw_year=adj_opex,
            discount_rate=adj_rate,
            project_life_years=project_life_years,
            technology=technology,
            run_monte_carlo=False,
        )
        results[scenario] = {
            "npv_usd":        result["npv_usd"],
            "irr":            result["irr"],
            "lcoe_usd_mwh":   result["lcoe_usd_mwh"],
            "payback_years":  result["payback_years"],
            "annual_mwh":     adj_mwh,
            "electricity_price": adj_price,
            "total_capex":    capacity_mw * adj_capex,
            "discount_rate":  adj_rate,
        }
    return {
        "project": project_name,
        "scenarios": results,
        "summary": _scenario_summary(results),
    }


def _scenario_summary(results: Dict) -> Dict:
    """Key comparison metrics across scenarios."""
    return {
        "npv_range": {
            "worst": results["worst"]["npv_usd"],
            "base":  results["base"]["npv_usd"],
            "best":  results["best"]["npv_usd"],
        },
        "irr_range": {
            "worst": results["worst"]["irr"],
            "base":  results["base"]["irr"],
            "best":  results["best"]["irr"],
        },
        "lcoe_range": {
            "worst": results["worst"]["lcoe_usd_mwh"],
            "base":  results["base"]["lcoe_usd_mwh"],
            "best":  results["best"]["lcoe_usd_mwh"],
        },
        "viable_scenarios": [s for s, r in results.items() if r["npv_usd"] and r["npv_usd"] > 0],
    }


def sensitivity_analysis(
    project_name: str,
    capacity_mw: float,
    base_annual_mwh: float,
    base_electricity_price: float,
    capex_per_mw: float,
    opex_per_mw_year: float,
    discount_rate: float,
    project_life_years: int = 25,
    technology: str = "solar",
    steps: int = 5,
) -> Dict:
    """
    Sensitivity analysis: vary each key parameter +/-20%
    and measure NPV impact. Suitable for tornado chart visualisation.
    """
    base = full_financial_analysis(
        project_name, capacity_mw, base_annual_mwh, base_electricity_price,
        capex_per_mw, opex_per_mw_year, discount_rate, project_life_years,
        technology, run_monte_carlo=False
    )
    base_npv = base["npv_usd"]

    params = {
        "electricity_price": (base_electricity_price, lambda v: full_financial_analysis(
            project_name, capacity_mw, base_annual_mwh, v,
            capex_per_mw, opex_per_mw_year, discount_rate, project_life_years, technology, False)["npv_usd"]),
        "capex_per_mw": (capex_per_mw, lambda v: full_financial_analysis(
            project_name, capacity_mw, base_annual_mwh, base_electricity_price,
            v, opex_per_mw_year, discount_rate, project_life_years, technology, False)["npv_usd"]),
        "annual_mwh": (base_annual_mwh, lambda v: full_financial_analysis(
            project_name, capacity_mw, v, base_electricity_price,
            capex_per_mw, opex_per_mw_year, discount_rate, project_life_years, technology, False)["npv_usd"]),
        "discount_rate": (discount_rate, lambda v: full_financial_analysis(
            project_name, capacity_mw, base_annual_mwh, base_electricity_price,
            capex_per_mw, opex_per_mw_year, v, project_life_years, technology, False)["npv_usd"]),
    }

    sensitivity = {}
    for param_name, (base_val, fn) in params.items():
        low_npv  = fn(base_val * 0.80)
        high_npv = fn(base_val * 1.20)
        sensitivity[param_name] = {
            "base_value":   base_val,
            "base_npv":     base_npv,
            "low_npv":      round(low_npv, 2),
            "high_npv":     round(high_npv, 2),
            "impact_range": round(abs(high_npv - low_npv), 2),
        }

    # Sort by impact for tornado chart
    sorted_sensitivity = dict(sorted(sensitivity.items(), key=lambda x: x[1]["impact_range"], reverse=True))
    return {
        "project": project_name,
        "base_npv": base_npv,
        "sensitivity": sorted_sensitivity,
    }
