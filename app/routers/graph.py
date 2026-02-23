from fastapi import APIRouter, Query
from app.models.schemas import (
    VendorRiskRequest,
    VendorRiskResponse,
    ContractDependencyRequest,
    RenewalImpactRequest,
    RenewalImpactResponse,
    GraphQueryResponse,
    ContractSchema,
)
from app.graph import queries

router = APIRouter()


@router.post("/vendor-risk", response_model=VendorRiskResponse)
def vendor_risk(req: VendorRiskRequest) -> VendorRiskResponse:
    """Analyse vendor/supplier risk profile."""
    data = queries.get_vendor_risk(req.vendor, req.tenant_id)
    if not data:
        return VendorRiskResponse(vendor=req.vendor, summary="Vendor not found.")
    contracts = [
        ContractSchema(**{k: v for k, v in c.items() if k in ContractSchema.model_fields})
        for c in data.get("contracts", [])
        if c.get("id")
    ]
    return VendorRiskResponse(
        vendor=data.get("supplier_name", req.vendor),
        contracts=contracts,
        obligations=data.get("obligations", []),
        summary=f"Found {len(contracts)} contract(s) for {data.get('supplier_name')}.",
    )


@router.post("/renewal-impact", response_model=RenewalImpactResponse)
def renewal_impact(req: RenewalImpactRequest) -> RenewalImpactResponse:
    """List contracts expiring soon with renewal risk assessment."""
    contracts_data = queries.get_contracts_expiring_soon(req.days_ahead, req.tenant_id)
    contracts = []
    for c in contracts_data:
        row = {k: v for k, v in c.items() if k in ContractSchema.model_fields}
        if "id" not in row and "contract_id" in c:
            row["id"] = c["contract_id"]
        contracts.append(ContractSchema(**row))
    total_value = sum(float(c.value or 0) for c in contracts)
    return RenewalImpactResponse(
        contracts=contracts,
        total_value_at_risk=total_value,
        summary=f"{len(contracts)} contract(s) expiring in the next {req.days_ahead} days.",
    )


@router.post("/contract-dependencies", response_model=GraphQueryResponse)
def contract_dependencies(req: ContractDependencyRequest) -> GraphQueryResponse:
    """Return full dependency graph for a specific contract."""
    data = queries.get_contract_dependencies(req.contract_id)
    return GraphQueryResponse(results=[data] if data else [], count=1 if data else 0)


@router.get("/suppliers", response_model=GraphQueryResponse)
def list_suppliers(
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> GraphQueryResponse:
    """List all suppliers."""
    results = queries.list_suppliers(tenant_id, limit)
    return GraphQueryResponse(results=results, count=len(results))


@router.get("/contracts", response_model=GraphQueryResponse)
def list_contracts(
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> GraphQueryResponse:
    """List all contracts with supplier info."""
    results = queries.list_contracts(tenant_id, limit)
    return GraphQueryResponse(results=results, count=len(results))


@router.get("/top-risk-suppliers", response_model=GraphQueryResponse)
def top_risk_suppliers(
    limit: int = Query(default=10, ge=1, le=50),
    tenant_id: str | None = Query(default=None),
) -> GraphQueryResponse:
    """Return top suppliers by risk score."""
    results = queries.get_top_risk_suppliers(limit, tenant_id)
    return GraphQueryResponse(results=results, count=len(results))
