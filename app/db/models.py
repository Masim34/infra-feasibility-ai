"""
app/db/models.py
SQLAlchemy ORM models for infra-feasibility-ai SaaS platform.
Tables: users, projects, analyses, api_cache
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime,
    Text, JSON, ForeignKey, Index, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import uuid
import os

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    """Platform users - SaaS tenants."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    plan = Column(String(50), default="free")  # free, pro, enterprise
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username}>"

class Project(Base):
    """Infrastructure projects being analyzed."""
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    country = Column(String(100), nullable=False)
    location_lat = Column(Float, nullable=False)
    location_lon = Column(Float, nullable=False)
    technology = Column(String(100), nullable=False)  # solar, wind, hybrid, etc.
    capacity_mw = Column(Float, nullable=False)
    estimated_cost_usd = Column(Float, nullable=True)
    status = Column(String(50), default="draft")  # draft, active, archived
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="projects")
    analyses = relationship("Analysis", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project {self.name} ({self.country})>"

class Analysis(Base):
    """Full analysis results - immutable snapshots."""
    __tablename__ = "analyses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Configuration used
    parameters = Column(JSON, nullable=False)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    error_message = Column(Text, nullable=True)

    # Results - Summary Metrics
    npv_usd = Column(Float, nullable=True)
    irr_percent = Column(Float, nullable=True)
    lcoe_usd_mwh = Column(Float, nullable=True)
    total_capex_usd = Column(Float, nullable=True)
    total_opex_usd = Column(Float, nullable=True)
    net_profit_usd = Column(Float, nullable=True)
    roi_percent = Column(Float, nullable=True)
    discount_rate_used = Column(Float, nullable=True)
    
    # Risk
    country_risk_score = Column(Float, nullable=True)
    country_risk_grade = Column(String(10), nullable=True)
    risk_adjusted_discount_rate = Column(Float, nullable=True)

    # Full JSON snapshots
    energy_results = Column(JSON, nullable=True)
    financial_results = Column(JSON, nullable=True)
    risk_results = Column(JSON, nullable=True)
    scenarios_results = Column(JSON, nullable=True)
    sensitivity_results = Column(JSON, nullable=True)
    monte_carlo_results = Column(JSON, nullable=True)
    full_report = Column(JSON, nullable=True)
    narrative_report = Column(Text, nullable=True)

    # Metadata
    processing_time_seconds = Column(Float, nullable=True)
    data_sources = Column(JSON, default=list)  # World Bank, NASA POWER, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="analyses")
    user = relationship("User", back_populates="analyses")

    __table_args__ = (
        Index("idx_analyses_project", "project_id"),
        Index("idx_analyses_user_status", "user_id", "status"),
    )

    def __repr__(self):
        return f"<Analysis {self.id} [{self.status}] for project {self.project_id}>"

class APICache(Base):
    """Cache for external API responses (World Bank, NASA POWER, ElectricityMap)."""
    __tablename__ = "api_cache"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    cache_key = Column(String(512), unique=True, nullable=False, index=True)
    source = Column(String(100), nullable=False)  # world_bank, nasa_power, electricitymap
    payload = Column(JSON, nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    hit_count = Column(Integer, default=0)

    def __repr__(self):
        return f"<APICache {self.source}:{self.cache_key[:40]}>"

# --- Database session factory ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/infraai")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"sslmode": "require"} if "amazonaws.com" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """FastAPI dependency - yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Create all tables. Run on startup."""
    Base.metadata.create_all(bind=engine)
