import pytest
from unittest.mock import MagicMock, patch
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
    """Test client with mocked DB and AI."""
    with patch("app.db.session.get_db", return_value=iter([mock_db])), \
         patch("app.services.ai_client.openai") as mock_openai:

        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="{\"score\": 75, \"summary\": \"Test summary\", \"risks\": [], \"opportunities\": [], \"recommendation\": \"Proceed\"}"))]
        )

        from app.main import app
        from app.db.session import get_db
        app.dependency_overrides[get_db] = lambda: mock_db
        yield TestClient(app)
        app.dependency_overrides.clear()
