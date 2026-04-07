"""Basic unit tests that don't require DB or AI."""


def test_true():
    """Sanity check test."""
    assert True


def test_math():
    """Basic math test."""
    assert 2 + 2 == 4


def test_string_operations():
    """Test string operations."""
    text = "infra-feasibility-ai"
    assert "feasibility" in text
    assert text.upper() == "INFRA-FEASIBILITY-AI"


def test_list_operations():
    """Test list operations."""
    items = [1, 2, 3, 4, 5]
    assert len(items) == 5
    assert sum(items) == 15
    assert max(items) == 5


def test_dict_operations():
    """Test dictionary operations."""
    config = {
        "project_name": "Test Project",
        "location": "UK",
        "capacity_mw": 100
    }
    assert config["capacity_mw"] == 100
    assert "project_name" in config
