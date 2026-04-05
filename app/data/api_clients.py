"""
app/data/api_clients.py
Real-world data API clients: World Bank, NASA POWER, ElectricityMap
Includes local JSON caching layer
"""

import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TTL_HOURS = 24


def _cache_path(key: str) -> Path:
    safe = key.replace("/", "_").replace("?", "_").replace("&", "_")
    return CACHE_DIR / f"{safe}.json"


def _load_cache(key: str) -> Optional[Any]:
    path = _cache_path(key)
    if not path.exists():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    if datetime.now() - mtime > timedelta(hours=CACHE_TTL_HOURS):
        return None
    with open(path) as f:
        return json.load(f)


def _save_cache(key: str, data: Any) -> None:
    with open(_cache_path(key), "w") as f:
        json.dump(data, f, indent=2)


# ─── WORLD BANK API ─────────────────────────────────────────────────────────

WB_BASE = "https://api.worldbank.org/v2"

WB_INDICATORS = {
    "gdp_growth":       "NY.GDP.MKTP.KD.ZG",
    "inflation":        "FP.CPI.TOTL.ZG",
    "population":       "SP.POP.TOTL",
    "energy_use":       "EG.USE.PCAP.KG.OE",
    "electricity_access": "EG.ELC.ACCS.ZS",
    "renewable_output": "EG.ELC.RNWX.KH",
}


def get_world_bank(country_code: str, indicator_key: str, years: int = 10) -> Dict:
    indicator = WB_INDICATORS.get(indicator_key)
    if not indicator:
        raise ValueError(f"Unknown indicator: {indicator_key}. Choose from {list(WB_INDICATORS.keys())}")
    cache_key = f"wb_{country_code}_{indicator_key}_{years}"
    cached = _load_cache(cache_key)
    if cached:
        return cached
    url = f"{WB_BASE}/country/{country_code}/indicator/{indicator}"
    params = {"format": "json", "mrv": years, "per_page": years}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    raw = resp.json()
    records = raw[1] if len(raw) > 1 else []
    result = {
        "country": country_code,
        "indicator": indicator_key,
        "data": [
            {"year": r["date"], "value": r["value"]}
            for r in records if r["value"] is not None
        ]
    }
    _save_cache(cache_key, result)
    return result


def get_world_bank_all(country_code: str, years: int = 10) -> Dict:
    """Fetch all indicators for a country in one call."""
    result = {}
    for key in WB_INDICATORS:
        try:
            result[key] = get_world_bank(country_code, key, years)
        except Exception as e:
            result[key] = {"error": str(e)}
    return result


# ─── NASA POWER API ─────────────────────────────────────────────────────────

NASA_BASE = "https://power.larc.nasa.gov/api/temporal/monthly/point"

NASA_PARAMS = {
    "ghi":         "ALLSKY_SFC_SW_DWN",   # Global Horizontal Irradiance kWh/m2/day
    "temperature": "T2M",                  # 2m Temperature Celsius
    "wind_speed":  "WS10M",               # Wind Speed m/s at 10m
    "humidity":    "RH2M",                # Relative Humidity %
}


def get_nasa_power(
    lat: float,
    lon: float,
    param_key: str = "ghi",
    start_year: int = 2019,
    end_year: int = 2023,
) -> Dict:
    param = NASA_PARAMS.get(param_key)
    if not param:
        raise ValueError(f"Unknown param: {param_key}. Choose from {list(NASA_PARAMS.keys())}")
    cache_key = f"nasa_{lat}_{lon}_{param_key}_{start_year}_{end_year}"
    cached = _load_cache(cache_key)
    if cached:
        return cached
    params = {
        "parameters": param,
        "community":  "RE",
        "longitude":  lon,
        "latitude":   lat,
        "start":      start_year,
        "end":        end_year,
        "format":     "JSON",
    }
    resp = requests.get(NASA_BASE, params=params, timeout=30)
    resp.raise_for_status()
    raw = resp.json()
    props = raw.get("properties", {}).get("parameter", {})
    monthly = props.get(param, {})
    result = {
        "lat": lat,
        "lon": lon,
        "param": param_key,
        "unit": "kWh/m2/day" if param_key == "ghi" else "varies",
        "monthly_data": monthly,
        "annual_average": round(sum(monthly.values()) / len(monthly), 4) if monthly else None,
    }
    _save_cache(cache_key, result)
    return result


def get_nasa_solar_profile(lat: float, lon: float) -> Dict:
    """Full solar + wind + temp profile for a location."""
    return {
        "ghi":         get_nasa_power(lat, lon, "ghi"),
        "temperature": get_nasa_power(lat, lon, "temperature"),
        "wind_speed":  get_nasa_power(lat, lon, "wind_speed"),
    }


# ─── ELECTRICITYMAP API ──────────────────────────────────────────────────────

EM_BASE = "https://api.electricitymap.org/v3"


def get_carbon_intensity(zone: str, api_key: str) -> Dict:
    """Get live grid carbon intensity from ElectricityMap."""
    cache_key = f"em_carbon_{zone}"
    cached = _load_cache(cache_key)
    if cached:
        return cached
    headers = {"auth-token": api_key}
    resp = requests.get(f"{EM_BASE}/carbon-intensity/latest", params={"zone": zone}, headers=headers, timeout=15)
    resp.raise_for_status()
    result = resp.json()
    _save_cache(cache_key, result)
    return result


def get_power_breakdown(zone: str, api_key: str) -> Dict:
    """Get power generation mix from ElectricityMap."""
    cache_key = f"em_power_{zone}"
    cached = _load_cache(cache_key)
    if cached:
        return cached
    headers = {"auth-token": api_key}
    resp = requests.get(f"{EM_BASE}/power-breakdown/latest", params={"zone": zone}, headers=headers, timeout=15)
    resp.raise_for_status()
    result = resp.json()
    _save_cache(cache_key, result)
    return result
