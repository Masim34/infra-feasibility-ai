"""
app/data/cleaners.py
Data cleaning and normalisation utilities for API responses
"""

from typing import Dict, List, Optional
import statistics


def clean_world_bank(raw: Dict) -> Dict:
    """Extract and clean World Bank indicator time series."""
    data_points = raw.get("data", [])
    values = [d["value"] for d in data_points if d["value"] is not None]
    years  = [int(d["year"]) for d in data_points if d["value"] is not None]
    return {
        "country":   raw.get("country"),
        "indicator": raw.get("indicator"),
        "years":     years,
        "values":    values,
        "latest":    values[0] if values else None,
        "mean":      round(statistics.mean(values), 4) if values else None,
        "trend":     _linear_trend(years, values),
    }


def clean_nasa_solar(raw: Dict) -> Dict:
    """Summarise NASA POWER solar irradiance data."""
    monthly = raw.get("monthly_data", {})
    values = [v for v in monthly.values() if v and v > 0]
    months = list(monthly.keys())
    return {
        "lat":            raw.get("lat"),
        "lon":            raw.get("lon"),
        "param":          raw.get("param"),
        "unit":           raw.get("unit"),
        "annual_average": raw.get("annual_average"),
        "peak_month":     max(monthly, key=monthly.get) if monthly else None,
        "low_month":      min(monthly, key=monthly.get) if monthly else None,
        "monthly_avg":    {m: round(v, 3) for m, v in monthly.items()},
        "std_dev":        round(statistics.stdev(values), 4) if len(values) > 1 else 0,
        "capacity_factor_estimate": _estimate_capacity_factor(raw.get("annual_average", 0)),
    }


def clean_carbon_intensity(raw: Dict) -> Dict:
    """Clean ElectricityMap carbon intensity response."""
    return {
        "zone":              raw.get("zone"),
        "carbon_intensity":  raw.get("carbonIntensity"),
        "unit":              "gCO2eq/kWh",
        "datetime":          raw.get("datetime"),
        "updated_at":        raw.get("updatedAt"),
    }


def _linear_trend(years: List[int], values: List[float]) -> Optional[float]:
    """Return simple linear regression slope (value change per year)."""
    n = len(years)
    if n < 2:
        return None
    x_mean = statistics.mean(years)
    y_mean = statistics.mean(values)
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(years, values))
    den = sum((x - x_mean) ** 2 for x in years)
    return round(num / den, 6) if den != 0 else 0.0


def _estimate_capacity_factor(annual_ghi: float) -> float:
    """
    Rough capacity factor estimate for solar PV.
    Assumes standard 15% panel efficiency, performance ratio 0.80.
    CF = GHI_annual_avg (kWh/m2/day) / 24 * efficiency * PR
    """
    if not annual_ghi:
        return 0.0
    efficiency = 0.18
    pr = 0.80
    cf = (annual_ghi / 24) * efficiency * pr
    return round(cf, 4)


def normalise_macro_data(wb_all: Dict) -> Dict:
    """
    Takes output of get_world_bank_all() and returns cleaned summary dict
    suitable for the country risk engine.
    """
    out = {}
    for key, raw in wb_all.items():
        if "error" in raw:
            out[key] = {"error": raw["error"]}
        else:
            cleaned = clean_world_bank(raw)
            out[key] = {
                "latest": cleaned["latest"],
                "mean":   cleaned["mean"],
                "trend":  cleaned["trend"],
            }
    return out
