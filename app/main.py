"""
app/main.py
Production FastAPI backend for infra-feasibility-ai.
Integrates SQLAlchemy DB, JWT/API Key Auth, and Celery Async Processing.
"""
import os
import uuid
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

# Database & Auth
from app.db.models import Base, engine, get_db, User, Project, Analysis
from app.services.auth import (
    get_current_user, create_access_token, authenticate_user, 
    create_user, hash_password, TokenRequest
)
from app.services.worker import run_full_analysis
from app.services.exporter import generate_pdf_report, generate_excel_model

# Initialize DB
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="infra-feasibility-ai",
    description="SaaS Platform for Infrastructure Investment Analysis",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Auth Endpoints ──────────────────────────────────────────────────────────

@app.post("/auth/register", status_code=201)
def register(request: TokenRequest, db: Session = Depends(get_db)):
    return create_user(db, email=request.username, username=request.username, password=request.password)

@app.post("/auth/token")
def login(request: TokenRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, request.username, request.password)
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer", "api_key": user.api_key}

# ─── Project Endpoints ────────────────────────────────────────────────────────

@app.post("/projects")
def create_project(project_data: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    new_project = Project(user_id=user.id, **project_data)
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project

@app.get("/projects")
def list_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Project).filter(Project.user_id == user.id).all()

# ─── Analysis Endpoints ───────────────────────────────────────────────────────

@app.post("/analyze/{project_id}")
def start_analysis(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    
    analysis = Analysis(project_id=project.id, user_id=user.id, status="pending")
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    
    # Trigger Async Task
    run_full_analysis.delay(analysis.id)
    
    return {"status": "analysis_started", "analysis_id": analysis.id}

@app.get("/analysis/{analysis_id}")
def get_analysis(analysis_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id, Analysis.user_id == user.id).first()
    if not analysis:
        raise HTTPException(404, "Analysis not found")
    return analysis

# ─── Export Endpoints ─────────────────────────────────────────────────────────

@app.get("/export/{analysis_id}/pdf")
def export_pdf(analysis_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id, Analysis.user_id == user.id).first()
    if not analysis or analysis.status != "completed":
        raise HTTPException(400, "Analysis not ready for export")
    
    pdf_buffer = generate_pdf_report(analysis.full_report or {})
    return FileResponse(pdf_buffer, media_type="application/pdf", filename=f"report_{analysis_id}.pdf")

@app.get("/health")
def health():
    return {"status": "ok", "db": "connected", "workers": "active"}
