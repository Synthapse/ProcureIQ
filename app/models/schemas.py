from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel


# ── Request / Response models ──────────────────────────────────────────────


class ChatRequest(BaseModel):
    question: str
    tenant_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = []
    tool_calls: list[str] = []


class VendorRiskRequest(BaseModel):
    vendor: str
    tenant_id: Optional[str] = None


class ContractDependencyRequest(BaseModel):
    contract_id: str
    tenant_id: Optional[str] = None


class RenewalImpactRequest(BaseModel):
    days_ahead: int = 90
    tenant_id: Optional[str] = None


# ── Graph node schemas ─────────────────────────────────────────────────────


class SupplierSchema(BaseModel):
    id: str
    name: str
    country: Optional[str] = None
    industry: Optional[str] = None
    risk_score: Optional[float] = None
    contract_count: Optional[int] = None


class ContractSchema(BaseModel):
    id: str
    title: Optional[str] = None
    status: Optional[str] = None
    contract_type: Optional[str] = None
    value: Optional[float] = None
    currency: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    renewal_date: Optional[str] = None
    auto_renewal: Optional[bool] = None
    risk_score: Optional[float] = None


class VendorRiskResponse(BaseModel):
    vendor: str
    risk_score: Optional[float] = None
    contracts: list[ContractSchema] = []
    obligations: list[dict[str, Any]] = []
    summary: str = ""


class RenewalImpactResponse(BaseModel):
    contracts: list[ContractSchema] = []
    total_value_at_risk: float = 0.0
    summary: str = ""


class GraphQueryResponse(BaseModel):
    results: list[dict[str, Any]]
    count: int
