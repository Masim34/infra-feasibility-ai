import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
import sys
import os

# Ensure app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@pytest.fixture(scope="session")
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.close = MagicMock()
    return db


@pytest.fixture(scope="session")
def client(mock_db):
    """Test client with mocked DB."""
    # Mock httpx to prevent real HTTP calls from AnthropicClient
    with patch("httpx.AsyncClient") as mock_httpx:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"text": "Test narrative response"}]
        }
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_httpx.return_value)
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value.post = AsyncMock(return_value=mock_response)

        from app.main import app
        from app.db.session import get_db
        app.dependency_overrides[get_db] = lambda: mock_db
        yield TestClient(app)
        app.dependency_overrides.clear()
