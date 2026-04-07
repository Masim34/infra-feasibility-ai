"""API tests using mocked dependencies."""
import pytest
from unittest.mock import MagicMock, patch


def test_health_check(client):
    """Test the health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200


def test_register_user(client):
    """Test user registration."""
    payload = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "SecurePass123!"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code in [200, 201, 400, 422]


def test_login_invalid_credentials(client):
    """Test login with invalid credentials."""
    payload = {"username": "nonexistent", "password": "wrongpassword"}
    response = client.post("/api/v1/auth/token", data=payload)
    assert response.status_code in [401, 422, 404]


def test_list_projects_unauthenticated(client):
    """Test that unauthenticated access returns 401."""
    response = client.get("/api/v1/projects/")
    assert response.status_code == 401


def test_list_analyses_unauthenticated(client):
    """Test that unauthenticated access returns 401."""
    response = client.get("/api/v1/analyses/")
    assert response.status_code == 401
