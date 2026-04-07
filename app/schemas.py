from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None
    company: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    country: str
    location_lat: float
    location_lon: float
    technology: str
    capacity_mw: float
    estimated_cost_usd: Optional[float] = None
    status: str = "draft"


class ProjectOut(ProjectCreate):
    id: str
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AnalysisCreate(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)


class AnalysisOut(BaseModel):
    id: str
    project_id: str
    user_id: str
    parameters: dict[str, Any]
    status: str
    error_message: Optional[str] = None
    npv_usd: Optional[float] = None
    irr_percent: Optional[float] = None
    lcoe_usd_mwh: Optional[float] = None
    total_capex_usd: Optional[float] = None
    total_opex_usd: Optional[float] = None
    net_profit_usd: Optional[float] = None
    roi_percent: Optional[float] = None
    country_risk_score: Optional[float] = None
    country_risk_grade: Optional[str] = None
    narrative_report: Optional[str] = None
    full_report: Optional[dict[str, Any]] = None
    processing_time_seconds: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True