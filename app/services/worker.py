import os
import time
import asyncio
from datetime import datetime
from celery import Celery
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Analysis
from app.models.pypsa_model import build_solar_network
from app.models.finance_advanced import full_financial_analysis
from app.models.country_risk import score_country_risk
from app.services.reporter import build_full_report
from app.services.scenarios import build_default_scenarios
from app.services.ai_client import AnthropicClient

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("infra_tasks", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)


def _safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _default_monthly_ghi(annual_ghi: float) -> dict:
    return {m: annual_ghi for m in ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]}


def _merge_defaults(project, parameters: dict | None) -> dict:
    params = parameters or {}
    annual_ghi = _safe_float(params.get("annual_ghi"), 5.5)
    monthly_ghi = params.get("monthly_ghi") or _default_monthly_ghi(annual_ghi)
    return {
        "annual_ghi": annual_ghi,
        "monthly_ghi": monthly_ghi,
        "battery_mwh": _safe_float(params.get("battery_mwh"), 0.0),
        "load_mw": _safe_float(params.get("load_mw"), None),
        "capex_per_mw": _safe_float(params.get("capex_per_mw"), 1000000),
        "opex_per_mw_year": _safe_float(params.get("opex_per_mw_year"), 20000),
        "electricity_price_usd_mwh": _safe_float(params.get("electricity_price_usd_mwh"), 85.0),
        "discount_rate": _safe_float(params.get("discount_rate"), 0.10),
        "project_life_years": _safe_int(params.get("project_life_years"), 25),
        "technology": params.get("technology") or project.technology,
        "run_monte_carlo": bool(params.get("run_monte_carlo", True)),
    }


async def _generate_narrative(project, report):
    client = AnthropicClient()
    prompt = (
        f"Write a concise investor-grade infrastructure feasibility narrative. "
        f"Project: {project.name}. Country: {project.country}. "
        f"Technology: {project.technology}. Capacity MW: {project.capacity_mw}. "
        f"Use this structured report as factual basis: {report}"
    )
    return await client.generate_narrative(prompt)


@celery_app.task(bind=True, name="run_full_analysis")
def run_full_analysis(self, analysis_id: str):
    db: Session = SessionLocal()
    analysis = None
    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return {"status": "not_found", "analysis_id": analysis_id}

        project = analysis.project
        if not project:
            analysis.status = "failed"
            analysis.error_message = "Associated project not found"
            analysis.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "failed", "analysis_id": analysis_id}

        analysis.status = "running"
        analysis.error_message = None
        db.commit()

        start_time = time.time()
        params = _merge_defaults(project, analysis.parameters)

        self.update_state(state="PROGRESS", meta={"step": "energy_model"})
        energy = build_solar_network(
            project_name=project.name,
            capacity_mw=project.capacity_mw,
            annual_ghi=params["annual_ghi"],
            monthly_ghi=params["monthly_ghi"],
            load_mw=params["load_mw"],
            battery_mwh=params["battery_mwh"],
            capex_per_mw=params["capex_per_mw"],
            opex_per_mw_year=params["opex_per_mw_year"],
        )

        self.update_state(state="PROGRESS", meta={"step": "financial_model"})
        financials = full_financial_analysis(
            project_name=project.name,
            capacity_mw=project.capacity_mw,
            annual_production_mwh=energy["annual_production_mwh"],
            electricity_price_usd_mwh=params["electricity_price_usd_mwh"],
            capex_per_mw=params["capex_per_mw"],
            opex_per_mw_year=params["opex_per_mw_year"],
            discount_rate=params["discount_rate"],
            project_life_years=params["project_life_years"],
            technology=params["technology"],
            run_monte_carlo=params["run_monte_carlo"],
        )

        self.update_state(state="PROGRESS", meta={"step": "country_risk"})
        risk = score_country_risk(project.country)

        self.update_state(state="PROGRESS", meta={"step": "scenarios"})
        scenarios = build_default_scenarios(financials)

        project_data = {
            "name": project.name,
            "technology": project.technology,
            "country": project.country,
            "capacity_mw": project.capacity_mw,
            "lat": project.location_lat,
            "lon": project.location_lon,
            "annual_ghi": params["annual_ghi"],
            "project_life_years": params["project_life_years"],
        }

        self.update_state(state="PROGRESS", meta={"step": "report_build"})
        full_report = build_full_report(
            project=project_data,
            energy=energy,
            financials=financials,
            risk=risk,
            scenarios=scenarios,
            sensitivity=analysis.sensitivity_results or None,
            monte_carlo=financials.get("monte_carlo"),
        )

        narrative = "AI insights unavailable at this moment."
        self.update_state(state="PROGRESS", meta={"step": "ai_narrative"})
        try:
            narrative = asyncio.run(_generate_narrative(project, full_report))
        except Exception:
            narrative = "AI insights unavailable at this moment."

        analysis.status = "completed"
        analysis.npv_usd = financials.get("npv_usd")
        analysis.irr_percent = financials.get("irr")
        analysis.lcoe_usd_mwh = financials.get("lcoe_usd_mwh")
        analysis.total_capex_usd = financials.get("inputs", {}).get("total_capex_usd")
        analysis.total_opex_usd = financials.get("inputs", {}).get("annual_opex_usd")
        _rev = financials.get("inputs", {}).get("annual_revenue_usd") or 0
        _opex = financials.get("inputs", {}).get("annual_opex_usd") or 0
        analysis.net_profit_usd = _rev - _opex
        analysis.roi_percent = (
            None if not analysis.total_capex_usd
            else round((analysis.net_profit_usd / analysis.total_capex_usd) * 100, 4)
        )
        analysis.discount_rate_used = financials.get("inputs", {}).get("discount_rate")
        analysis.country_risk_score = risk.get("composite_risk_score") or risk.get("score")
        analysis.country_risk_grade = risk.get("risk_category") or risk.get("grade")
        analysis.risk_adjusted_discount_rate = risk.get("risk_adjusted_discount_rate")
        analysis.energy_results = energy
        analysis.financial_results = financials
        analysis.risk_results = risk
        analysis.scenarios_results = scenarios
        analysis.monte_carlo_results = financials.get("monte_carlo")
        analysis.full_report = full_report
        analysis.narrative_report = narrative
        analysis.data_sources = ["pypsa_model", "finance_advanced", "country_risk", "scenarios", "reporter", "anthropic_optional"]
        analysis.processing_time_seconds = round(time.time() - start_time, 4)
        analysis.completed_at = datetime.utcnow()
        db.commit()

        return {
            "status": "success",
            "analysis_id": analysis_id,
            "processing_time_seconds": analysis.processing_time_seconds,
        }

    except Exception as exc:
        if analysis:
            analysis.status = "failed"
            analysis.error_message = str(exc)
            analysis.completed_at = datetime.utcnow()
            db.commit()
        raise
    finally:
        db.close()