"""
app/models/finance_advanced.py
Advanced financial modelling: LCOE, NPV, IRR, DCF, Payback, Monte Carlo
"""
import numpy as np
from typing import Dict, List, Optional
import random


def calculate_lcoe(
    total_capex: float,
    annual_opex: float,
    annual_energy_mwh: float,
    project_life_years: int = 25,
    discount_rate: float = 0.08,
) -> float:
    """Levelized Cost of Energy (USD/MWh)."""
    if annual_energy_mwh <= 0:
        return float('inf')
    pv_costs = total_capex
    pv_energy = 0
    for yr in range(1, project_life_years + 1):
        df = (1 + discount_rate) ** yr
        pv_costs += annual_opex / df
        pv_energy += annual_energy_mwh / df
    return round(pv_costs / pv_energy, 4) if pv_energy > 0 else float('inf')


def calculate_npv(
    capex: float,
    annual_revenue: float,
    annual_opex: float,
    discount_rate: float,
    project_life_years: int = 25,
    terminal_value: float = 0.0,
) -> Dict:
    """Net Present Value and discounted cash flow schedule."""
    cash_flows = []
    npv = -capex
    for yr in range(1, project_life_years + 1):
        cf = annual_revenue - annual_opex
        pv = cf / ((1 + discount_rate) ** yr)
        npv += pv
        cash_flows.append({"year": yr, "cash_flow": round(cf, 2), "pv": round(pv, 2)})
    if terminal_value:
        tv_pv = terminal_value / ((1 + discount_rate) ** project_life_years)
        npv += tv_pv
    return {"npv": round(npv, 2), "cash_flows": cash_flows}


def calculate_irr(
    capex: float,
    annual_revenue: float,
    annual_opex: float,
    project_life_years: int = 25,
) -> Optional[float]:
    """Internal Rate of Return via bisection method."""
    cf_stream = [-capex] + [annual_revenue - annual_opex] * project_life_years

    def npv_at_rate(r):
        return sum(cf / ((1 + r) ** i) for i, cf in enumerate(cf_stream))

    low, high = -0.5, 5.0
    if npv_at_rate(low) * npv_at_rate(high) > 0:
        return None  # No IRR in range
    for _ in range(200):
        mid = (low + high) / 2
        if abs(npv_at_rate(mid)) < 1:
            return round(mid, 6)
        if npv_at_rate(low) * npv_at_rate(mid) < 0:
            high = mid
        else:
            low = mid
    return round((low + high) / 2, 6)


def calculate_payback(capex: float, annual_net_revenue: float) -> Optional[float]:
    """Simple payback period in years."""
    if annual_net_revenue <= 0:
        return None
    return round(capex / annual_net_revenue, 2)


def calculate_capex_breakdown(
    capacity_mw: float,
    technology: str = "solar",
) -> Dict:
    """CAPEX breakdown by component for solar/wind."""
    if technology == "solar":
        per_mw = {
            "panels": 280000,
            "inverters": 60000,
            "mounting": 50000,
            "civil_works": 80000,
            "grid_connection": 70000,
            "engineering_procurement": 100000,
            "contingency": 60000,
        }
    elif technology == "wind":
        per_mw = {
            "turbines": 700000,
            "foundations": 120000,
            "electrical": 80000,
            "grid_connection": 90000,
            "engineering_procurement": 100000,
            "contingency": 80000,
        }
    else:
        per_mw = {"total": 1000000}
    breakdown = {k: round(v * capacity_mw, 2) for k, v in per_mw.items()}
    breakdown["total_capex"] = sum(breakdown.values())
    return breakdown


def monte_carlo_simulation(
    capex: float,
    annual_revenue: float,
    annual_opex: float,
    discount_rate: float,
    project_life_years: int = 25,
    n_simulations: int = 1000,
    price_volatility: float = 0.15,
    output_volatility: float = 0.10,
    cost_overrun_pct: float = 0.10,
) -> Dict:
    """
    Monte Carlo simulation for NPV/IRR uncertainty.
    Returns distribution statistics.
    """
    npvs = []
    irrs = []
    lcoes = []
    random.seed(42)

    for _ in range(n_simulations):
        sim_capex = capex * (1 + random.gauss(0, cost_overrun_pct))
        sim_revenue = annual_revenue * (1 + random.gauss(0, price_volatility))
        sim_opex = annual_opex * (1 + random.gauss(0, 0.05))
        sim_output = max(1, annual_revenue / max(0.001, annual_revenue) * (1 + random.gauss(0, output_volatility)))

        npv_result = calculate_npv(sim_capex, sim_revenue, sim_opex, discount_rate, project_life_years)
        npvs.append(npv_result["npv"])

        irr = calculate_irr(sim_capex, sim_revenue, sim_opex, project_life_years)
        if irr is not None:
            irrs.append(irr)

    npvs_sorted = sorted(npvs)
    return {
        "simulations": n_simulations,
        "npv_mean": round(np.mean(npvs), 2),
        "npv_median": round(np.median(npvs), 2),
        "npv_std": round(np.std(npvs), 2),
        "npv_p10": round(np.percentile(npvs, 10), 2),
        "npv_p90": round(np.percentile(npvs, 90), 2),
        "probability_positive_npv": round(sum(1 for n in npvs if n > 0) / n_simulations, 4),
        "irr_mean": round(np.mean(irrs), 6) if irrs else None,
        "irr_p10": round(np.percentile(irrs, 10), 6) if irrs else None,
        "irr_p90": round(np.percentile(irrs, 90), 6) if irrs else None,
    }


def full_financial_analysis(
    project_name: str,
    capacity_mw: float,
    annual_production_mwh: float,
    electricity_price_usd_mwh: float,
    capex_per_mw: float,
    opex_per_mw_year: float,
    discount_rate: float,
    project_life_years: int = 25,
    technology: str = "solar",
    run_monte_carlo: bool = True,
) -> Dict:
    """Full financial analysis combining all metrics."""
    total_capex = capacity_mw * capex_per_mw
    annual_opex = capacity_mw * opex_per_mw_year
    annual_revenue = annual_production_mwh * electricity_price_usd_mwh

    lcoe = calculate_lcoe(total_capex, annual_opex, annual_production_mwh, project_life_years, discount_rate)
    npv_result = calculate_npv(total_capex, annual_revenue, annual_opex, discount_rate, project_life_years)
    irr = calculate_irr(total_capex, annual_revenue, annual_opex, project_life_years)
    payback = calculate_payback(total_capex, annual_revenue - annual_opex)
    capex_breakdown = calculate_capex_breakdown(capacity_mw, technology)

    result = {
        "project": project_name,
        "inputs": {
            "capacity_mw": capacity_mw,
            "annual_production_mwh": annual_production_mwh,
            "electricity_price_usd_mwh": electricity_price_usd_mwh,
            "total_capex_usd": total_capex,
            "annual_opex_usd": annual_opex,
            "annual_revenue_usd": annual_revenue,
            "discount_rate": discount_rate,
            "project_life_years": project_life_years,
        },
        "lcoe_usd_mwh": lcoe,
        "npv_usd": npv_result["npv"],
        "irr": irr,
        "payback_years": payback,
        "capex_breakdown": capex_breakdown,
        "cash_flows": npv_result["cash_flows"],
    }
    if run_monte_carlo:
        result["monte_carlo"] = monte_carlo_simulation(
            total_capex, annual_revenue, annual_opex, discount_rate, project_life_years
        )
    return result
