"""
example_run.py
Sample end-to-end run of the infra-feasibility-ai platform.
Demonstrates a 100MW solar project in Iraq without running the API server.
Run: python example_run.py
"""
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_example():
    print("=" * 60)
    print(" infra-feasibility-ai - Example Analysis Run")
    print(" Project: 100MW Solar PV Farm, Iraq")
    print("=" * 60)

    # ── Step 1: Energy Simulation (no API needed) ─────────────
    print("\n[1] Running energy simulation (fallback mode)...")
    from app.models.pypsa_model import build_solar_network

    # Use sample NASA POWER data for Iraq (Baghdad region)
    monthly_ghi = {
        "202301": 4.2, "202302": 4.8, "202303": 5.6, "202304": 6.2,
        "202305": 7.1, "202306": 7.8, "202307": 7.5, "202308": 7.2,
        "202309": 6.5, "202310": 5.4, "202311": 4.3, "202312": 3.8,
    }
    annual_ghi = sum(monthly_ghi.values()) / len(monthly_ghi)

    energy = build_solar_network(
        project_name="Baghdad Solar Farm",
        capacity_mw=100,
        annual_ghi=annual_ghi,
        monthly_ghi=monthly_ghi,
        battery_mwh=50,
        capex_per_mw=800000,
        opex_per_mw_year=15000,
    )
    print(f"  Annual Production: {energy['annual_production_mwh']:,.0f} MWh")
    print(f"  Capacity Factor:   {energy['capacity_factor']:.1%}")
    print(f"  Total CAPEX:       USD {energy['total_capex_usd']:,.0f}")
    print(f"  Simulation:        {energy['simulation_status']}")

    # ── Step 2: Country Risk ────────────────────────────────────
    print("\n[2] Scoring country risk for Iraq (IQ)...")
    from app.models.country_risk import score_country_risk

    risk = score_country_risk(
        country_code="IQ",
        gdp_growth=3.2,
        inflation=5.4,
    )
    print(f"  Risk Score:        {risk['composite_risk_score']}/100")
    print(f"  Risk Category:     {risk['risk_category']}")
    print(f"  Discount Rate:     {risk['risk_adjusted_discount_rate']:.1%}")

    # ── Step 3: Financial Analysis ──────────────────────────────
    print("\n[3] Running financial analysis...")
    from app.models.finance_advanced import full_financial_analysis

    financials = full_financial_analysis(
        project_name="Baghdad Solar Farm",
        capacity_mw=100,
        annual_production_mwh=energy["annual_production_mwh"],
        electricity_price_usd_mwh=70,
        capex_per_mw=800000,
        opex_per_mw_year=15000,
        discount_rate=risk["risk_adjusted_discount_rate"],
        project_life_years=25,
        technology="solar",
        run_monte_carlo=True,
    )
    print(f"  LCOE:              USD {financials['lcoe_usd_mwh']:.2f}/MWh")
    print(f"  NPV:               USD {financials['npv_usd']:,.0f}")
    print(f"  IRR:               {financials['irr']:.1%}" if financials['irr'] else "  IRR:               N/A")
    print(f"  Payback:           {financials['payback_years']:.1f} years")
    print(f"  MC P10 NPV:        USD {financials['monte_carlo']['npv_p10']:,.0f}")
    print(f"  MC P90 NPV:        USD {financials['monte_carlo']['npv_p90']:,.0f}")
    print(f"  P(NPV>0):          {financials['monte_carlo']['probability_positive_npv']:.0%}")

    # ── Step 4: Scenarios ──────────────────────────────────────────
    print("\n[4] Running scenario analysis...")
    from app.models.scenarios import run_scenarios

    scenarios = run_scenarios(
        project_name="Baghdad Solar Farm",
        capacity_mw=100,
        base_annual_mwh=energy["annual_production_mwh"],
        base_electricity_price=70,
        capex_per_mw=800000,
        opex_per_mw_year=15000,
        discount_rate=risk["risk_adjusted_discount_rate"],
        project_life_years=25,
        technology="solar",
    )
    for s, data in scenarios["scenarios"].items():
        print(f"  {s.upper():5s} NPV: USD {data['npv_usd']:>15,.0f}  |  IRR: {str(round(data['irr']*100,1))+'%' if data['irr'] else 'N/A':>6}")

    # ── Step 5: Build Report ────────────────────────────────────────
    print("\n[5] Building investor-grade report...")
    from app.services.reporter import build_full_report, generate_claude_prompt, export_report_json

    project_meta = {
        "name": "Baghdad Solar Farm", "technology": "solar",
        "country": "IQ", "capacity_mw": 100,
        "lat": 33.34, "lon": 44.40,
        "project_life_years": 25, "annual_ghi": annual_ghi,
    }
    report = build_full_report(
        project=project_meta, energy=energy, financials=financials,
        risk=risk, scenarios=scenarios,
        monte_carlo=financials.get("monte_carlo"),
    )
    print(f"  Verdict:           {report['investment_recommendation']['verdict']}")
    print(f"  Confidence:        {report['investment_recommendation']['confidence']}")
    print(f"  Summary:           {report['investment_recommendation']['summary']}")

    # Save report
    report_path = "reports/baghdad_solar_report.json"
    os.makedirs("reports", exist_ok=True)
    export_report_json(report, report_path)
    print(f"\n  Report saved to: {report_path}")

    # Claude prompt preview
    claude_prompt = generate_claude_prompt(report)
    print(f"\n[6] Claude prompt generated ({len(claude_prompt)} chars).")
    print("    Send report['claude_prompt'] to Claude API for full narrative.")

    print("\n" + "=" * 60)
    print(" ANALYSIS COMPLETE")
    print("=" * 60)
    return report


if __name__ == "__main__":
    run_example()
