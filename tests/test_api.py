"""Tests for ProcureIQ API endpoints."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ProcureIQ API"}


@patch("app.routers.graph.queries.list_suppliers")
def test_list_suppliers(mock_query):
    mock_query.return_value = [
        {"id": "sup-001", "name": "TechFlow Solutions", "country": "USA", "industry": "Technology", "domain": "techflow.com"}
    ]
    response = client.get("/api/v1/graph/suppliers")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["results"][0]["name"] == "TechFlow Solutions"


@patch("app.routers.graph.queries.list_contracts")
def test_list_contracts(mock_query):
    mock_query.return_value = [
        {"id": "ctr-001", "title": "Enterprise License", "status": "active", "value": 250000.0, "currency": "USD", "end_date": "2026-03-15", "risk_score": 7.5, "supplier_name": "TechFlow Solutions"}
    ]
    response = client.get("/api/v1/graph/contracts")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["results"][0]["title"] == "Enterprise License"


@patch("app.routers.graph.queries.get_vendor_risk")
def test_vendor_risk(mock_query):
    mock_query.return_value = {
        "supplier_id": "sup-001",
        "supplier_name": "TechFlow Solutions",
        "country": "USA",
        "industry": "Technology",
        "contracts": [{"id": "ctr-001", "title": "Enterprise License", "status": "active", "value": 250000.0, "currency": "USD", "end_date": "2026-03-15", "risk_score": 7.5}],
        "obligations": [],
    }
    response = client.post("/api/v1/graph/vendor-risk", json={"vendor": "TechFlow"})
    assert response.status_code == 200
    data = response.json()
    assert data["vendor"] == "TechFlow Solutions"
    assert len(data["contracts"]) == 1


@patch("app.routers.graph.queries.get_vendor_risk")
def test_vendor_risk_not_found(mock_query):
    mock_query.return_value = {}
    response = client.post("/api/v1/graph/vendor-risk", json={"vendor": "Unknown Corp"})
    assert response.status_code == 200
    data = response.json()
    assert "not found" in data["summary"].lower()


@patch("app.routers.graph.queries.get_contracts_expiring_soon")
def test_renewal_impact(mock_query):
    mock_query.return_value = [
        {"contract_id": "ctr-001", "title": "Enterprise License", "supplier_name": "TechFlow", "status": "active", "value": 250000.0, "currency": "USD", "end_date": "2026-03-15", "risk_score": 7.5, "auto_renewal": False}
    ]
    response = client.post("/api/v1/graph/renewal-impact", json={"days_ahead": 180})
    assert response.status_code == 200
    data = response.json()
    assert data["total_value_at_risk"] == 250000.0


@patch("app.routers.graph.queries.get_top_risk_suppliers")
def test_top_risk_suppliers(mock_query):
    mock_query.return_value = [
        {"supplier_id": "sup-003", "supplier_name": "SecureNet Inc", "country": "USA", "industry": "Cybersecurity", "avg_risk_score": 8.9, "contract_count": 1}
    ]
    response = client.get("/api/v1/graph/top-risk-suppliers")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["results"][0]["supplier_name"] == "SecureNet Inc"


@patch("app.routers.graph.queries.get_contract_dependencies")
def test_contract_dependencies(mock_query):
    mock_query.return_value = {
        "contract_id": "ctr-001",
        "title": "Enterprise License",
        "supplier_name": "TechFlow Solutions",
        "status": "active",
        "value": 250000.0,
        "currency": "USD",
        "end_date": "2026-03-15",
        "risk_score": 7.5,
        "lines": [],
        "obligations": [],
        "invoices": [],
    }
    response = client.post("/api/v1/graph/contract-dependencies", json={"contract_id": "ctr-001"})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
