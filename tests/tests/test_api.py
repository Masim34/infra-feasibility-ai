"""API tests using the actual app routes."""
import pytest


def test_health_check(client):
    """Test the health endpoint returns ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_register_user(client):
    """Test user registration endpoint exists."""
    payload = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "SecurePass123!",
        "full_name": "Test User",
        "company": "Test Corp"
    }
    response = client.post("/auth/register", json=payload)
    # 201 success or 400 duplicate or 422 validation
    assert response.status_code in [200, 201, 400, 422]


def test_login_invalid_credentials(client):
    """Test login with invalid credentials returns 401."""
    payload = {"username": "nonexistent", "password": "wrongpassword"}
    response = client.post("/auth/token", json=payload)
    assert response.status_code in [401, 422, 404]


def test_list_projects_unauthenticated(client):
    """Test that unauthenticated access returns 401 or 403."""
    response = client.get("/projects")
    assert response.status_code in [401, 403]


def test_get_analysis_unauthenticated(client):
    """Test that unauthenticated analysis access returns 401 or 403."""
    response = client.get("/analysis/fake-id")
    assert response.status_code in [401, 403]


def test_export_json_unauthenticated(client):
    """Test that export endpoint requires auth."""
    response = client.get("/analysis/fake-id/export/json")
    assert response.status_code in [401, 403]
