from datetime import datetime
import uuid
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    plan = Column(String(50), default="free")
    api_key = Column(String(128), unique=True, nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    analyses = relationship("Analysis", back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    country = Column(String(100), nullable=False)
    location_lat = Column(Float, nullable=False)
    location_lon = Column(Float, nullable=False)
    technology = Column(String(100), nullable=False)
    capacity_mw = Column(Float, nullable=False)
    estimated_cost_usd = Column(Float, nullable=True)
    status = Column(String(50), default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="projects")
    analyses = relationship("Analysis", back_populates="project", cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    parameters = Column(JSON, nullable=False, default=dict)
    status = Column(String(50), default="pending")
    error_message = Column(Text, nullable=True)

    npv_usd = Column(Float, nullable=True)
    irr_percent = Column(Float, nullable=True)
    lcoe_usd_mwh = Column(Float, nullable=True)
    total_capex_usd = Column(Float, nullable=True)
    total_opex_usd = Column(Float, nullable=True)
    net_profit_usd = Column(Float, nullable=True)
    roi_percent = Column(Float, nullable=True)
    discount_rate_used = Column(Float, nullable=True)

    country_risk_score = Column(Float, nullable=True)
    country_risk_grade = Column(String(10), nullable=True)
    risk_adjusted_discount_rate = Column(Float, nullable=True)

    energy_results = Column(JSON, nullable=True)
    financial_results = Column(JSON, nullable=True)
    risk_results = Column(JSON, nullable=True)
    scenarios_results = Column(JSON, nullable=True)
    sensitivity_results = Column(JSON, nullable=True)
    monte_carlo_results = Column(JSON, nullable=True)
    full_report = Column(JSON, nullable=True)
    narrative_report = Column(Text, nullable=True)

    processing_time_seconds = Column(Float, nullable=True)
    data_sources = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="analyses")
    user = relationship("User", back_populates="analyses")

    __table_args__ = (
        Index("idx_analyses_project", "project_id"),
        Index("idx_analyses_user_status", "user_id", "status"),
    )


class APICache(Base):
    __tablename__ = "api_cache"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    cache_key = Column(String(512), unique=True, nullable=False, index=True)
    source = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    hit_count = Column(Integer, default=0)