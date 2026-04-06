"""
app/services/worker.py
Async task processing for infra-feasibility-ai.
Handles long-running PyPSA simulations and financial modelling using Celery.
"""
import os
import time
import asyncio
from celery import Celery
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.models import SessionLocal, Analysis, Project
from app.models.pypsa_model import build_solar_network
from app.models.finance_advanced import full_financial_analysis
from app.models.country_risk import score_country_risk
from app.services.reporter import build_full_report
from app.services.ai_client import AnthropicClient

# --- Config ---
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

@celery_app.task(bind=True, name="run_full_analysis")
def run_full_analysis(self, analysis_id: str):
    """
    Background worker task to run the full infrastructure analysis pipeline.
    """
    db: Session = SessionLocal()
    analysis = None
    try:
        # 1. Fetch analysis and project
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return "Analysis not found"

        analysis.status = "running"
        db.commit()

        project = analysis.project
        start_time = time.time()

        # 2. Simulate PyPSA
        self.update_state(state='PROGRESS', meta={'step': 'Simulating Energy Network'})
        energy = build_solar_network(
            project_name=project.name,
            capacity_mw=project.capacity_mw,
            annual_ghi=5.5, # Base assumption
            capex_per_mw=1000000,
            opex_per_mw_year=20000
        )

        # 3. Financials
        self.update_state(state='PROGRESS', meta={'step': 'Calculating Financials'})
        financials = full_financial_analysis(
            project_name=project.name,
            capacity_mw=project.capacity_mw,
            annual_production_mwh=energy["annual_production_mwh"],
            electricity_price_usd_mwh=85.0,
            capex_per_mw=1000000,
            opex_per_mw_year=20000,
            discount_rate=0.1,
            project_life_years=25,
            technology=project.technology
        )

        # 4. Country Risk
        self.update_state(state='PROGRESS', meta={'step': 'Assessing Country Risk'})
        risk = score_country_risk(project.country)

        # 5. AI Narrative (Phase 8)
        self.update_state(state='PROGRESS', meta={'step': 'Generating AI Insights'})
        try:
            ai_client = AnthropicClient()
            prompt = (
                f"Analyze this infrastructure project: {project.name} in {project.country}.
"
                f"Technology: {project.technology}. Capacity: {project.capacity_mw} MW.
"
                f"Projected NPV: ${financials['npv_usd']}. IRR: {financials['irr_percent']}%.
"
                f"Country Risk: {risk['grade']}.
"
                f"Provide a brief executive investment summary."
            )
            narrative = asyncio.run(ai_client.generate_narrative(prompt))
            analysis.narrative_report = narrative
        except Exception as ai_err:
            print(f"AI Narrative failed: {ai_err}")
            analysis.narrative_report = "AI insights unavailable at this moment."

        # 6. Finalize results
        analysis.status = "completed"
        analysis.npv_usd = financials["npv_usd"]
        analysis.irr_percent = financials["irr_percent"]
        analysis.lcoe_usd_mwh = financials["lcoe_usd_mwh"]
        analysis.country_risk_score = risk["score"]
        analysis.country_risk_grade = risk["grade"]
        
        analysis.energy_results = energy
        analysis.financial_results = financials
        analysis.risk_results = risk
        
        # Build structured report for UI
        project_data = {
            "name": project.name,
            "technology": project.technology,
            "country": project.country,
            "capacity_mw": project.capacity_mw,
            "lat": project.location_lat,
            "lon": project.location_lon
        }
        analysis.full_report = build_full_report(
            project=project_data,
            energy=energy,
            financials=financials,
            risk=risk,
            scenarios={}
        )
        
        analysis.processing_time_seconds = time.time() - start_time
        analysis.completed_at = datetime.utcnow()

        db.commit()
        return {"status": "success", "analysis_id": analysis_id}

    except Exception as e:
        if analysis:
            analysis.status = "failed"
            analysis.error_message = str(e)
            db.commit()
        raise e
    finally:
        db.close()
