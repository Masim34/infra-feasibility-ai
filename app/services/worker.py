"""
app/services/worker.py
Async task processing for infra-feasibility-ai.
Handles long-running PyPSA simulations and financial modelling using Celery.
"""
import os
import time
from celery import Celery
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.models import SessionLocal, Analysis, Project
from app.models.pypsa_model import build_solar_network
from app.models.finance_advanced import full_financial_analysis
from app.models.country_risk import score_country_risk
from app.services.reporter import build_full_report

# ─── Config ────────────────────────────────────────────────────────────────────
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
    try:
        # 1. Update status
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return "Analysis not found"
        
        analysis.status = "running"
        db.commit()
        
        project = analysis.project
        start_time = time.time()
        
        # 2. Simulate (Mocking logic based on main.py flow)
        # In real scenario, we'd fetch data here if not cached
        self.update_state(state='PROGRESS', meta={'step': 'Simulating Energy Network'})
        
        # Simulate PyPSA
        energy = build_solar_network(
            project_name=project.name,
            capacity_mw=project.capacity_mw,
            annual_ghi=analysis.annual_ghi or 5.0, # fallback
            capex_per_mw=project.capex_per_mw,
            opex_per_mw_year=project.opex_per_mw_year
        )
        
        # 3. Financials
        self.update_state(state='PROGRESS', meta={'step': 'Calculating Financials'})
        financials = full_financial_analysis(
            project_name=project.name,
            capacity_mw=project.capacity_mw,
            annual_production_mwh=energy["annual_production_mwh"],
            electricity_price_usd_mwh=project.electricity_price_usd_mwh,
            capex_per_mw=project.capex_per_mw,
            opex_per_mw_year=project.opex_per_mw_year,
            discount_rate=analysis.discount_rate_used or 0.1,
            project_life_years=project.project_life_years,
            technology=project.technology
        )
        
        # 4. Finalize
        analysis.status = "completed"
        analysis.annual_production_mwh = energy["annual_production_mwh"]
        analysis.capacity_factor = energy["capacity_factor"]
        analysis.npv_usd = financials["npv_usd"]
        analysis.irr_percent = financials["irr_percent"]
        analysis.lcoe_usd_mwh = financials["lcoe_usd_mwh"]
        analysis.energy_results = energy
        analysis.financial_results = financials
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
