"""
app/main.py
FastAPI SaaS backend for infra-feasibility-ai platform.
Endpoints: /analyze, /projects, /scenarios, /health
Authentication: JWT Bearer tokens
"""
import os
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, List
import jwt
from datetime import datetime, timedelta

# Internal modules
from app.data.api_clients import get_world_bank_all, get_nasa_solar_profile
from app.data.cleaners import clean_nasa_solar, normalise_macro_data
from app.models.pypsa_model import build_solar_network
from app.models.finance_advanced import full_financial_analysis
from app.models.country_risk import score_country_risk
from app.models.scenarios import run_scenarios, sensitivity_analysis
from app.services.reporter import build_full_report, generate_claude_prompt, export_report_json

# Config
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

app = FastAPI(
    title="infra-feasibility-ai",
    description="Production-grade SaaS platform for infrastructure and green energy investment analysis",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)


# ─── Auth ───────────────────────────────────────────────────────────────────────
class TokenRequest(BaseModel):
    username: str
    password: str


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.post("/auth/token")
def login(request: TokenRequest):
    """Issue JWT token. Demo: any username/password accepted (add real auth in production)."""
    token = create_access_token({"sub": request.username})
    return {"access_token": token, "token_type": "bearer", "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60}


# ─── Schemas ────────────────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    project_name: str                       = Field(..., example="Solar Farm Iraq")
    country_code: str                       = Field(..., example="IQ")
    lat: float                              = Field(..., example=33.34)
    lon: float                              = Field(..., example=44.40)
    capacity_mw: float                      = Field(..., example=100.0)
    technology: str                         = Field("solar", example="solar")
    electricity_price_usd_mwh: float        = Field(..., example=65.0)
    capex_per_mw: float                     = Field(800000, example=800000)
    opex_per_mw_year: float                 = Field(15000, example=15000)
    project_life_years: int                 = Field(25, example=25)
    battery_mwh: float                      = Field(0.0, example=0.0)
    load_mw: Optional[float]                = Field(None)
    run_monte_carlo: bool                   = Field(True)
    include_scenarios: bool                 = Field(True)
    include_sensitivity: bool               = Field(True)
    include_claude_prompt: bool             = Field(False)


# ─── Core Endpoints ────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    return {"status": "ok", "platform": "infra-feasibility-ai", "version": "1.0.0"}


@app.post("/analyze")
def analyze_project(
    request: AnalyzeRequest,
    user: str = Depends(get_current_user)
):
    """
    Full infrastructure investment analysis:
    - Fetches real data from World Bank + NASA POWER
    - Runs PyPSA energy simulation
    - Calculates NPV, IRR, LCOE, payback
    - Scores country risk
    - Runs scenarios and sensitivity
    - Returns investor-grade report JSON
    """
    try:
        # 1. Fetch real data
        wb_data  = get_world_bank_all(request.country_code)
        macro    = normalise_macro_data(wb_data)
        solar    = get_nasa_solar_profile(request.lat, request.lon)
        solar_clean = clean_nasa_solar(solar["ghi"])
        annual_ghi = solar_clean["annual_average"] or 5.0
        monthly_ghi = solar_clean["monthly_avg"]

        # 2. Energy simulation
        energy = build_solar_network(
            project_name=request.project_name,
            capacity_mw=request.capacity_mw,
            annual_ghi=annual_ghi,
            monthly_ghi=monthly_ghi,
            load_mw=request.load_mw,
            battery_mwh=request.battery_mwh,
            capex_per_mw=request.capex_per_mw,
            opex_per_mw_year=request.opex_per_mw_year,
        )

        # 3. Country risk
        risk = score_country_risk(
            request.country_code,
            gdp_growth=macro.get("gdp_growth", {}).get("latest"),
            inflation=macro.get("inflation", {}).get("latest"),
        )
        discount_rate = risk["risk_adjusted_discount_rate"]

        # 4. Financial analysis
        financials = full_financial_analysis(
            project_name=request.project_name,
            capacity_mw=request.capacity_mw,
            annual_production_mwh=energy["annual_production_mwh"],
            electricity_price_usd_mwh=request.electricity_price_usd_mwh,
            capex_per_mw=request.capex_per_mw,
            opex_per_mw_year=request.opex_per_mw_year,
            discount_rate=discount_rate,
            project_life_years=request.project_life_years,
            technology=request.technology,
            run_monte_carlo=request.run_monte_carlo,
        )

        # 5. Scenarios
        scenarios = {}
        if request.include_scenarios:
            scenarios = run_scenarios(
                project_name=request.project_name,
                capacity_mw=request.capacity_mw,
                base_annual_mwh=energy["annual_production_mwh"],
                base_electricity_price=request.electricity_price_usd_mwh,
                capex_per_mw=request.capex_per_mw,
                opex_per_mw_year=request.opex_per_mw_year,
                discount_rate=discount_rate,
                project_life_years=request.project_life_years,
                technology=request.technology,
            )

        # 6. Sensitivity
        sensitivity = {}
        if request.include_sensitivity:
            sensitivity = sensitivity_analysis(
                project_name=request.project_name,
                capacity_mw=request.capacity_mw,
                base_annual_mwh=energy["annual_production_mwh"],
                base_electricity_price=request.electricity_price_usd_mwh,
                capex_per_mw=request.capex_per_mw,
                opex_per_mw_year=request.opex_per_mw_year,
                discount_rate=discount_rate,
                project_life_years=request.project_life_years,
                technology=request.technology,
            )

        # 7. Build report
        project_meta = {
            "name": request.project_name, "technology": request.technology,
            "country": request.country_code, "capacity_mw": request.capacity_mw,
            "lat": request.lat, "lon": request.lon,
            "project_life_years": request.project_life_years,
            "annual_ghi": annual_ghi,
        }
        report = build_full_report(
            project=project_meta, energy=energy, financials=financials,
            risk=risk, scenarios=scenarios, sensitivity=sensitivity,
            monte_carlo=financials.get("monte_carlo"),
        )

        if request.include_claude_prompt:
            report["claude_prompt"] = generate_claude_prompt(report)

        return report

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/projects")
def list_projects(user: str = Depends(get_current_user)):
    """List saved projects for the authenticated user (stub - connect to PostgreSQL)."""
    return {"user": user, "projects": [], "message": "Connect to PostgreSQL to persist projects"}


@app.get("/")
def root():
    return {
        "platform": "infra-feasibility-ai",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
