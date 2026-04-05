"""
app/models/pypsa_model.py - PyPSA energy network modelling
Fallback simulation included for environments without PyPSA.
"""
import numpy as np
from typing import Dict

try:
    import pypsa
    PYPSA_AVAILABLE = True
except ImportError:
    PYPSA_AVAILABLE = False


def build_solar_network(
    project_name: str,
    capacity_mw: float,
    annual_ghi: float,
    monthly_ghi: Dict,
    load_mw: float = None,
    battery_mwh: float = 0.0,
    capex_per_mw: float = 800000,
    opex_per_mw_year: float = 15000,
) -> Dict:
    if not PYPSA_AVAILABLE:
        return _fallback_simulation(project_name, capacity_mw, annual_ghi, monthly_ghi, battery_mwh, capex_per_mw, opex_per_mw_year)
    cf_hourly = _build_hourly_cf(monthly_ghi, annual_ghi)
    n = pypsa.Network()
    n.set_snapshots(list(range(len(cf_hourly))))
    n.add("Bus", "main_bus", carrier="AC")
    n.add("Generator", "solar_pv", bus="main_bus", p_nom=capacity_mw, p_max_pu=cf_hourly, marginal_cost=0.0, capital_cost=capex_per_mw, carrier="solar")
    if load_mw:
        n.add("Load", "local_load", bus="main_bus", p_set=[load_mw * (0.6 if 6 <= (h % 24) <= 22 else 0.3) for h in range(8760)])
    if battery_mwh > 0:
        n.add("StorageUnit", "battery", bus="main_bus", p_nom=battery_mwh/4, max_hours=4, marginal_cost=0.0, capital_cost=200000)
    n.add("Generator", "grid_slack", bus="main_bus", p_nom=1e6, marginal_cost=50, p_min_pu=-1)
    try:
        n.optimize(solver_name="highs")
        status = "optimised"
    except Exception as e:
        status = f"optimisation_failed: {e}"
    solar_gen = n.generators_t.p.get("solar_pv", np.zeros(len(cf_hourly)))
    annual_production_mwh = float(solar_gen.sum())
    capacity_factor = annual_production_mwh / (capacity_mw * 8760)
    curtailment_mwh = max(0, capacity_mw * sum(cf_hourly) - annual_production_mwh)
    return _format_output(project_name, capacity_mw, annual_production_mwh, capacity_factor, curtailment_mwh, annual_production_mwh, battery_mwh, capex_per_mw, opex_per_mw_year, status)


def _fallback_simulation(project_name, capacity_mw, annual_ghi, monthly_ghi, battery_mwh, capex_per_mw, opex_per_mw_year) -> Dict:
    """Pure-Python simulation when PyPSA not installed."""
    energy_per_mw = annual_ghi * 365 * 0.18 * 0.80
    annual_production_mwh = capacity_mw * energy_per_mw / 1000
    capacity_factor = annual_production_mwh / (capacity_mw * 8760)
    return _format_output(project_name, capacity_mw, annual_production_mwh, capacity_factor, 0.0, annual_production_mwh, battery_mwh, capex_per_mw, opex_per_mw_year, "fallback_simulation")


def _build_hourly_cf(monthly_ghi: Dict, annual_avg: float) -> list:
    """Build 8760-hour capacity factor series from monthly GHI data."""
    months_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    vals = list(monthly_ghi.values()) if monthly_ghi else [annual_avg] * 12
    if len(vals) < 12:
        vals = [annual_avg] * 12
    cf = []
    for days, ghi in zip(months_days, vals[:12]):
        ghi = ghi or annual_avg or 4.5
        daily_cf = ghi / 24
        for _ in range(days):
            for h in range(24):
                if 6 <= h <= 19:
                    cf.append(min(1.0, daily_cf * 24 / 13 * np.sin(np.pi * (h-6) / 13) * 1.2))
                else:
                    cf.append(0.0)
    return cf[:8760] + [0.0] * max(0, 8760 - len(cf))


def _format_output(project_name, capacity_mw, annual_mwh, cf, curtailment, export, battery, capex_mw, opex_mw, status) -> Dict:
    return {
        "project": project_name, "capacity_mw": capacity_mw,
        "annual_production_mwh": round(annual_mwh, 2),
        "capacity_factor": round(cf, 4),
        "curtailment_mwh": round(curtailment, 2),
        "grid_export_mwh": round(export, 2),
        "battery_mwh": battery,
        "total_capex_usd": capacity_mw * capex_mw,
        "annual_opex_usd": capacity_mw * opex_mw,
        "simulation_status": status,
        "pypsa_available": PYPSA_AVAILABLE,
    }
