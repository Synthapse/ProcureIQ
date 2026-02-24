"""Advanced Neo4j queries: aggregations, filters, and multi-hop patterns."""

from app.graph.client import neo4j_client


def get_vendor_risk(vendor_name: str, tenant_id: str | None = None) -> dict:
    """Return risk profile for a supplier including linked contracts and obligations."""
    params: dict = {"name": vendor_name}
    tenant_filter = "AND s.tenant_id = $tenant_id " if tenant_id else ""
    if tenant_id:
        params["tenant_id"] = tenant_id
    cypher = f"""
        MATCH (s:Supplier)
        WHERE toLower(s.name) CONTAINS toLower($name) {tenant_filter}
        OPTIONAL MATCH (s)-[:HAS_CONTRACT]->(c:Contract)
        OPTIONAL MATCH (c)-[:HAS_OBLIGATION]->(o:ContractObligation)
        RETURN
            s.id          AS supplier_id,
            s.name        AS supplier_name,
            s.country     AS country,
            s.industry    AS industry,
            collect(DISTINCT {{
                id: c.id,
                title: c.title,
                status: c.status,
                value: c.value,
                currency: c.currency,
                end_date: c.end_date,
                renewal_date: c.renewal_date,
                risk_score: c.risk_score
            }}) AS contracts,
            collect(DISTINCT {{
                id: o.id,
                type: o.type,
                description: o.description,
                due_date: o.due_date,
                is_mandatory: o.is_mandatory,
                status: o.status
            }}) AS obligations
        LIMIT 1
    """
    rows = neo4j_client.run_query(cypher, params)
    return rows[0] if rows else {}


def get_contracts_expiring_soon(days_ahead: int = 90, tenant_id: str | None = None) -> list[dict]:
    """Return contracts expiring within days_ahead days."""
    params: dict = {"days": days_ahead}
    tenant_filter = "AND c.tenant_id = $tenant_id " if tenant_id else ""
    if tenant_id:
        params["tenant_id"] = tenant_id
    cypher = f"""
        MATCH (s:Supplier)-[:HAS_CONTRACT]->(c:Contract)
        WHERE c.end_date IS NOT NULL
          AND date(c.end_date) <= date() + duration({{days: $days}})
          AND date(c.end_date) >= date()
          {tenant_filter}
        RETURN
            s.name        AS supplier_name,
            c.id          AS contract_id,
            c.title       AS title,
            c.status      AS status,
            c.value       AS value,
            c.currency    AS currency,
            c.end_date    AS end_date,
            c.renewal_date AS renewal_date,
            c.auto_renewal AS auto_renewal,
            c.risk_score  AS risk_score
        ORDER BY c.end_date ASC
    """
    return neo4j_client.run_query(cypher, params)


def get_contract_dependencies(contract_id: str) -> dict:
    """Return a contract and all its lines, obligations, and linked supplier."""
    cypher = """
        MATCH (c:Contract {id: $contract_id})
        OPTIONAL MATCH (s:Supplier)-[:HAS_CONTRACT]->(c)
        OPTIONAL MATCH (c)-[:HAS_LINE]->(l:ContractLine)
        OPTIONAL MATCH (c)-[:HAS_OBLIGATION]->(o:ContractObligation)
        OPTIONAL MATCH (inv:Invoice)-[:RELATES_TO_CONTRACT]->(c)
        RETURN
            c.id           AS contract_id,
            c.title        AS title,
            c.status       AS status,
            c.value        AS value,
            c.currency     AS currency,
            c.end_date     AS end_date,
            c.risk_score   AS risk_score,
            s.name         AS supplier_name,
            collect(DISTINCT {
                id: l.id,
                description: l.description,
                unit_price: l.unit_price,
                quantity_committed: l.quantity_committed,
                category: l.category
            }) AS lines,
            collect(DISTINCT {
                id: o.id,
                type: o.type,
                description: o.description,
                due_date: o.due_date,
                status: o.status
            }) AS obligations,
            collect(DISTINCT {
                id: inv.id,
                invoice_number: inv.invoice_number,
                total_amount: inv.total_amount,
                status: inv.status
            }) AS invoices
    """
    rows = neo4j_client.run_query(cypher, {"contract_id": contract_id})
    return rows[0] if rows else {}


def get_top_risk_suppliers(limit: int = 10, tenant_id: str | None = None) -> list[dict]:
    """Return suppliers ranked by average contract risk score."""
    params: dict = {"limit": limit}
    tenant_filter = "WHERE s.tenant_id = $tenant_id " if tenant_id else ""
    if tenant_id:
        params["tenant_id"] = tenant_id
    cypher = f"""
        MATCH (s:Supplier)-[:HAS_CONTRACT]->(c:Contract)
        {tenant_filter}
        WITH s, avg(toFloat(c.risk_score)) AS avg_risk, count(c) AS contract_count
        RETURN
            s.id           AS supplier_id,
            s.name         AS supplier_name,
            s.country      AS country,
            s.industry     AS industry,
            avg_risk       AS avg_risk_score,
            contract_count AS contract_count
        ORDER BY avg_risk DESC
        LIMIT $limit
    """
    return neo4j_client.run_query(cypher, params)


def get_obligations_by_status(status: str = "overdue", tenant_id: str | None = None) -> list[dict]:
    """Return contract obligations filtered by status (e.g. overdue, pending, completed)."""
    params: dict = {"status": status}
    tenant_filter = "AND c.tenant_id = $tenant_id " if tenant_id else ""
    if tenant_id:
        params["tenant_id"] = tenant_id
    cypher = f"""
        MATCH (c:Contract)-[:HAS_OBLIGATION]->(o:ContractObligation)
        WHERE toLower(o.status) = toLower($status) {tenant_filter}
        RETURN
            c.id          AS contract_id,
            c.title       AS contract_title,
            o.id          AS obligation_id,
            o.type        AS obligation_type,
            o.description AS description,
            o.due_date    AS due_date,
            o.is_mandatory AS is_mandatory,
            o.status      AS status
        ORDER BY o.due_date ASC
    """
    return neo4j_client.run_query(cypher, params)


def get_supplier_concentration(tenant_id: str | None = None) -> list[dict]:
    """Return suppliers with multiple contracts – concentration / blast-radius risk."""
    params: dict = {}
    tenant_filter = "WHERE s.tenant_id = $tenant_id " if tenant_id else ""
    if tenant_id:
        params["tenant_id"] = tenant_id
    cypher = f"""
        MATCH (s:Supplier)-[:HAS_CONTRACT]->(c:Contract)
        {tenant_filter}
        WITH s,
             count(c)                    AS contract_count,
             sum(toFloat(c.value))       AS total_value,
             avg(toFloat(c.risk_score))  AS avg_risk_score
        WHERE contract_count > 1
        RETURN
            s.id       AS supplier_id,
            s.name     AS supplier_name,
            s.country  AS country,
            s.industry AS industry,
            contract_count,
            total_value,
            avg_risk_score
        ORDER BY total_value DESC
    """
    return neo4j_client.run_query(cypher, params)
