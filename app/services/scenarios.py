from typing import Dict, Any, List


def build_default_scenarios(financials: Dict[str, Any]) -> Dict[str, Any]:
    base = financials.get("inputs", {})
    base_price = base.get("electricity_price_usd_mwh")
    base_discount = base.get("discount_rate", 0.10)
    irr = financials.get("irr")

    if base_price is None:
        return {"scenarios": {}, "summary": {"viable_scenarios": [], "total_scenarios": 0}}

    scenarios: Dict[str, Any] = {}
    viable: List[str] = []

    scenario_definitions = [
        ("worst_case", 0.80, 1.20),
        ("base_case", 1.00, 1.00),
        ("optimistic", 1.15, 0.90),
        ("best_case", 1.25, 0.85),
    ]

    for label, price_mult, capex_mult in scenario_definitions:
        adj_price = round(base_price * price_mult, 4)
        adj_capex = round((base.get("capex_per_mw", 1000000)) * capex_mult, 4)
        scenario = {
            "electricity_price_usd_mwh": adj_price,
            "capex_per_mw": adj_capex,
            "discount_rate": base_discount,
            "estimated_npv_adjustment_factor": round(price_mult / capex_mult, 4),
        }
        scenarios[label] = scenario

        if irr is not None and irr >= base_discount:
            viable.append(label)

    return {
        "scenarios": scenarios,
        "summary": {
            "viable_scenarios": viable,
            "total_scenarios": len(scenarios),
            "base_electricity_price": base_price,
            "base_discount_rate": base_discount,
        },
    }