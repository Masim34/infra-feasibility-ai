"""
app/services/reporter.py
AI-ready report generator. Structures full analysis as investor-grade JSON
compatible with Claude for executive summary generation.
"""
import json
from datetime import datetime
from typing import Dict, Optional


def build_full_report(
    project: Dict,
    energy: Dict,
    financials: Dict,
    risk: Dict,
    scenarios: Dict,
    sensitivity: Dict = None,
    monte_carlo: Dict = None,
) -> Dict:
    """
    Assembles all analysis outputs into a single structured JSON report.
    Ready to send to Claude or any LLM for narrative generation.
    """
    report = {
        "report_metadata": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "platform":     "infra-feasibility-ai v1.0",
            "report_type":  "Infrastructure Investment Feasibility Analysis",
        },
        "project": {
            "name":         project.get("name"),
            "technology":   project.get("technology"),
            "country":      project.get("country"),
            "capacity_mw":  project.get("capacity_mw"),
            "location": {
                "lat": project.get("lat"),
                "lon": project.get("lon"),
            },
            "project_life_years": project.get("project_life_years", 25),
        },
        "energy": {
            "annual_production_mwh":  energy.get("annual_production_mwh"),
            "capacity_factor":        energy.get("capacity_factor"),
            "curtailment_mwh":        energy.get("curtailment_mwh"),
            "grid_export_mwh":        energy.get("grid_export_mwh"),
            "battery_storage_mwh":    energy.get("battery_mwh"),
            "simulation_status":      energy.get("simulation_status"),
            "solar_irradiance_annual_avg": project.get("annual_ghi"),
        },
        "financials": {
            "total_capex_usd":        financials.get("inputs", {}).get("total_capex_usd"),
            "annual_opex_usd":        financials.get("inputs", {}).get("annual_opex_usd"),
            "annual_revenue_usd":     financials.get("inputs", {}).get("annual_revenue_usd"),
            "electricity_price_usd_mwh": financials.get("inputs", {}).get("electricity_price_usd_mwh"),
            "discount_rate":          financials.get("inputs", {}).get("discount_rate"),
            "lcoe_usd_mwh":           financials.get("lcoe_usd_mwh"),
            "npv_usd":                financials.get("npv_usd"),
            "irr":                    financials.get("irr"),
            "payback_years":          financials.get("payback_years"),
            "capex_breakdown":        financials.get("capex_breakdown"),
        },
        "risk": {
            "country_code":                   risk.get("country_code"),
            "composite_risk_score":           risk.get("composite_risk_score"),
            "risk_category":                  risk.get("risk_category"),
            "risk_adjusted_discount_rate":    risk.get("risk_adjusted_discount_rate"),
            "component_scores":               risk.get("component_scores"),
            "country_risk_premium":           risk.get("country_risk_premium"),
        },
        "scenarios": {
            "best_npv":   scenarios.get("scenarios", {}).get("best", {}).get("npv_usd"),
            "base_npv":   scenarios.get("scenarios", {}).get("base", {}).get("npv_usd"),
            "worst_npv":  scenarios.get("scenarios", {}).get("worst", {}).get("npv_usd"),
            "best_irr":   scenarios.get("scenarios", {}).get("best", {}).get("irr"),
            "base_irr":   scenarios.get("scenarios", {}).get("base", {}).get("irr"),
            "worst_irr":  scenarios.get("scenarios", {}).get("worst", {}).get("irr"),
            "viable_scenarios": scenarios.get("summary", {}).get("viable_scenarios"),
            "full_scenarios":   scenarios.get("scenarios"),
        },
    }
    if sensitivity:
        report["sensitivity"] = sensitivity.get("sensitivity")
    if monte_carlo:
        report["monte_carlo"] = monte_carlo
    report["investment_recommendation"] = _generate_recommendation(report)
    return report


def _generate_recommendation(report: Dict) -> Dict:
    """Rule-based investment recommendation for the structured report."""
    npv    = report["financials"].get("npv_usd") or 0
    irr    = report["financials"].get("irr") or 0
    risk   = report["risk"].get("risk_category", "High")
    viable = report["scenarios"].get("viable_scenarios", [])

    if npv > 0 and irr > 0.12 and risk in ["Low", "Moderate"] and len(viable) >= 2:
        verdict = "INVEST"
        confidence = "High"
        summary = "Project demonstrates strong financial viability with acceptable country risk."
    elif npv > 0 and irr > 0.08:
        verdict = "CONDITIONAL INVEST"
        confidence = "Moderate"
        summary = "Project is financially viable but risk mitigation measures are recommended."
    elif npv > 0:
        verdict = "WATCH"
        confidence = "Low"
        summary = "Marginal financial case. Requires favourable scenario conditions to be viable."
    else:
        verdict = "DO NOT INVEST"
        confidence = "High"
        summary = "Negative NPV under base case. Project does not meet investment criteria."

    return {
        "verdict": verdict,
        "confidence": confidence,
        "summary": summary,
        "key_metrics": {
            "npv_usd": npv,
            "irr": irr,
            "risk_category": risk,
            "viable_scenarios": viable,
        },
    }


def generate_claude_prompt(report: Dict) -> str:
    """
    Generate a structured prompt for Claude to write the investor narrative.
    Injects the full report JSON as context.
    """
    report_json = json.dumps(report, indent=2, default=str)
    prompt = f"""You are a senior infrastructure investment analyst at a global advisory firm.

Using the structured feasibility analysis data below, write a professional investor-grade report containing:
1. Executive Summary (3-4 paragraphs)
2. Energy System Analysis
3. Financial Viability Assessment (NPV, IRR, LCOE, Payback)
4. Country Risk Analysis
5. Scenario Analysis (Best/Base/Worst)
6. Investment Recommendation with risk mitigation suggestions

Format the report professionally. Use USD values. Be specific with numbers.

FEASIBILITY ANALYSIS DATA:
{report_json}
"""
    return prompt


def export_report_json(report: Dict, filepath: str = None) -> str:
    """Export the report to JSON string or file."""
    json_str = json.dumps(report, indent=2, default=str)
    if filepath:
        with open(filepath, "w") as f:
            f.write(json_str)
    return json_str
