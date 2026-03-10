"""Simple data endpoints: list suppliers, contracts, invoices."""

from fastapi import APIRouter, Query

from app.graph.queries_basic import list_contracts, list_invoices, list_suppliers

router = APIRouter()


@router.get("/suppliers", summary="List all suppliers")
def get_suppliers(
    tenant_id: str | None = Query(None, description="Optional tenant filter"),
    limit: int = Query(50, ge=1, le=500),
) -> list[dict]:
    """Gather all suppliers from Neo4j."""
    return list_suppliers(tenant_id=tenant_id, limit=limit)


@router.get("/contracts", summary="List all contracts")
def get_contracts(
    tenant_id: str | None = Query(None, description="Optional tenant filter"),
    limit: int = Query(50, ge=1, le=500),
) -> list[dict]:
    """Gather all contracts from Neo4j."""
    return list_contracts(tenant_id=tenant_id, limit=limit)


@router.get("/invoices", summary="List all invoices")
def get_invoices(
    tenant_id: str | None = Query(None, description="Optional tenant filter"),
    limit: int = Query(50, ge=1, le=500),
) -> list[dict]:
    """Gather all invoices from Neo4j."""
    return list_invoices(tenant_id=tenant_id, limit=limit)
