import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"

from app.main import app
from app.db.base import Base
from app.db.session import get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def setup_module(_module):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module(_module):
    Base.metadata.drop_all(bind=engine)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_and_login():
    r = client.post("/auth/register", json={
        "email": "user@test.com",
        "username": "testuser",
        "password": "StrongPass123",
        "full_name": "Test User",
        "company": "GGC",
    })
    assert r.status_code == 201
    assert "api_key" in r.json()

    r = client.post("/auth/token", json={"username": "testuser", "password": "StrongPass123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_duplicate_register():
    r = client.post("/auth/register", json={
        "email": "user@test.com",
        "username": "testuser",
        "password": "StrongPass123",
    })
    assert r.status_code == 409


def test_wrong_password():
    r = client.post("/auth/token", json={"username": "testuser", "password": "wrong"})
    assert r.status_code == 401


def _get_token():
    r = client.post("/auth/token", json={"username": "testuser", "password": "StrongPass123"})
    return r.json()["access_token"]


def test_create_and_list_project():
    headers = {"Authorization": f"Bearer {_get_token()}"}
    r = client.post("/projects", json={
        "name": "Solar IPP Sierra Leone",
        "description": "Utility-scale solar project",
        "country": "Sierra Leone",
        "location_lat": 8.4657,
        "location_lon": -11.7799,
        "technology": "solar_pv",
        "capacity_mw": 50.0,
        "estimated_cost_usd": 65000000.0,
        "status": "draft",
    }, headers=headers)
    assert r.status_code == 200
    project_id = r.json()["id"]
    assert project_id

    r = client.get("/projects", headers=headers)
    assert r.status_code == 200
    assert any(p["id"] == project_id for p in r.json())


def test_start_analysis_and_retrieve():
    headers = {"Authorization": f"Bearer {_get_token()}"}
    r = client.get("/projects", headers=headers)
    project_id = r.json()[0]["id"]

    r = client.post(f"/analyze/{project_id}", json={
        "parameters": {
            "annual_ghi": 5.7,
            "battery_mwh": 0.0,
            "capex_per_mw": 1000000.0,
            "opex_per_mw_year": 20000.0,
            "electricity_price_usd_mwh": 90.0,
            "discount_rate": 0.11,
            "project_life_years": 25,
            "run_monte_carlo": False,
        }
    }, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "analysis_started"
    analysis_id = r.json()["analysis_id"]

    r = client.get(f"/analysis/{analysis_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == analysis_id


def test_export_404_for_nonexistent():
    headers = {"Authorization": f"Bearer {_get_token()}"}
    assert client.get("/analysis/nonexistent/export/json", headers=headers).status_code == 404
    assert client.get("/analysis/nonexistent/export/pdf", headers=headers).status_code == 404


def test_unauthorized_access():
    assert client.get("/projects").status_code == 403
    assert client.get("/analysis/any").status_code == 403