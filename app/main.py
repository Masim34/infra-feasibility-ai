import io
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import engine, get_db
from app.db.models import User, Project, Analysis
from app.schemas import RegisterRequest, LoginRequest, ProjectCreate, ProjectOut, AnalysisCreate, AnalysisOut
from app.services.auth import get_current_user, create_access_token, authenticate_user, create_user
from app.services.worker import run_full_analysis
from app.services.exporter import export_analysis_json, export_analysis_pdf

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="infra-feasibility-ai",
    description="Production-grade SaaS platform for infrastructure and green energy investment analysis",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/auth/register", status_code=201)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    return create_user(
        db=db,
        email=request.email,
        username=request.username,
        password=request.password,
        full_name=request.full_name,
        company=request.company,
    )


@app.post("/auth/token")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": user.id})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "api_key": user.api_key,
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "company": user.company,
            "plan": user.plan,
        },
    }


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.1.0"}


@app.post("/projects", response_model=ProjectOut)
def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    new_project = Project(user_id=user.id, **project_data.model_dump())
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project


@app.get("/projects", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return db.query(Project).filter(Project.user_id == user.id).order_by(Project.created_at.desc()).all()


@app.post("/analyze/{project_id}")
def start_analysis(
    project_id: str,
    payload: AnalysisCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    analysis = Analysis(
        project_id=project.id,
        user_id=user.id,
        parameters=payload.parameters or {},
        status="pending",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    run_full_analysis.delay(analysis.id)

    return {
        "status": "analysis_started",
        "analysis_id": analysis.id,
        "project_id": project.id,
    }


@app.get("/analysis/{analysis_id}", response_model=AnalysisOut)
def get_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == user.id,
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@app.get("/analysis/{analysis_id}/export/json")
def export_json(
    analysis_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == user.id,
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    content = export_analysis_json(analysis)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=analysis-{analysis.id}.json"},
    )


@app.get("/analysis/{analysis_id}/export/pdf")
def export_pdf(
    analysis_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == user.id,
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    content = export_analysis_pdf(analysis)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=analysis-{analysis.id}.pdf"},
    )