"""Unit tests for Knowledge Graph Service."""

import pytest
from src.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint returns correct service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "kg_service"
    assert data["status"] == "running"


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


# Add more tests as you develop features
@pytest.mark.skip(reason="Not implemented yet")
def test_graph_query():
    """Test graph query functionality."""
    pass


@pytest.mark.skip(reason="Not implemented yet")
def test_entity_relationships():
    """Test entity relationship queries."""
    pass
