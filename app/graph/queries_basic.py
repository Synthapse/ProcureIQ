"""Basic Neo4j queries: simple MATCH and list operations."""

import uuid

from app.graph.client import neo4j_client


def save_conversation_turn(
    user_id: str,
    question: str,
    answer: str,
    tool_calls: list[str] | None = None,
    conversation_id: str | None = None,
) -> str:
    """Persist one chat turn in Neo4j. Returns the conversation id (existing or new)."""
    msg_user_id = str(uuid.uuid4())
    msg_assistant_id = str(uuid.uuid4())
    tool_calls_str = ",".join(tool_calls) if tool_calls else None
    params = {
        "user_id": user_id,
        "msg_user_id": msg_user_id,
        "msg_assistant_id": msg_assistant_id,
        "question": question,
        "answer": answer,
        "tool_calls": tool_calls_str,
    }
    if conversation_id:
        append_cypher = """
            MATCH (u:User {id: $user_id})-[:HAS_CONVERSATION]->(c:Conversation {id: $conversation_id})
            CREATE (m1:Message {id: $msg_user_id, role: 'user', content: $question, created_at: datetime()})
            CREATE (m2:Message {id: $msg_assistant_id, role: 'assistant', content: $answer, created_at: datetime(), tool_calls: $tool_calls})
            CREATE (c)-[:HAS_MESSAGE]->(m1)
            CREATE (c)-[:HAS_MESSAGE]->(m2)
            RETURN c.id AS conv_id
        """
        params["conversation_id"] = conversation_id
        rows = neo4j_client.run_query(append_cypher, params)
        if rows:
            return rows[0]["conv_id"]
    conv_id = str(uuid.uuid4())
    params["conv_id"] = conv_id
    create_cypher = """
        MERGE (u:User {id: $user_id})
        CREATE (c:Conversation {id: $conv_id, created_at: datetime()})
        CREATE (m1:Message {id: $msg_user_id, role: 'user', content: $question, created_at: datetime()})
        CREATE (m2:Message {id: $msg_assistant_id, role: 'assistant', content: $answer, created_at: datetime(), tool_calls: $tool_calls})
        MERGE (u)-[:HAS_CONVERSATION]->(c)
        CREATE (c)-[:HAS_MESSAGE]->(m1)
        CREATE (c)-[:HAS_MESSAGE]->(m2)
    """
    neo4j_client.run_query(create_cypher, params)
    return conv_id


def list_suppliers(tenant_id: str | None = None, limit: int = 50) -> list[dict]:
    """Return all suppliers (optionally filtered by tenant)."""
    params: dict = {"limit": limit}
    tenant_filter = "WHERE s.tenant_id = $tenant_id " if tenant_id else ""
    if tenant_id:
        params["tenant_id"] = tenant_id
    cypher = f"""
        MATCH (s:Supplier)
        {tenant_filter}
        RETURN s.id AS id, s.name AS name, s.country AS country,
               s.industry AS industry, s.domain AS domain
        ORDER BY s.name
        LIMIT $limit
    """
    return neo4j_client.run_query(cypher, params)


def list_contracts(tenant_id: str | None = None, limit: int = 50) -> list[dict]:
    """Return all contracts (optionally filtered by tenant)."""
    params: dict = {"limit": limit}
    tenant_filter = "WHERE c.tenant_id = $tenant_id " if tenant_id else ""
    if tenant_id:
        params["tenant_id"] = tenant_id
    cypher = f"""
        MATCH (c:Contract)
        {tenant_filter}
        OPTIONAL MATCH (s:Supplier)-[:HAS_CONTRACT]->(c)
        RETURN c.id AS id, c.title AS title, c.status AS status,
               c.value AS value, c.currency AS currency,
               c.end_date AS end_date, c.risk_score AS risk_score,
               s.name AS supplier_name
        ORDER BY c.end_date ASC
        LIMIT $limit
    """
    return neo4j_client.run_query(cypher, params)


def list_invoices(tenant_id: str | None = None, limit: int = 50) -> list[dict]:
    """Return all invoices (optionally filtered by tenant)."""
    params: dict = {"limit": limit}
    tenant_filter = "WHERE inv.tenant_id = $tenant_id " if tenant_id else ""
    if tenant_id:
        params["tenant_id"] = tenant_id
    cypher = f"""
        MATCH (inv:Invoice)
        {tenant_filter}
        OPTIONAL MATCH (inv)-[:RELATES_TO_CONTRACT]->(c:Contract)
        RETURN inv.id AS id, inv.invoice_number AS invoice_number,
               inv.total_amount AS total_amount, inv.currency AS currency,
               inv.status AS status, inv.invoice_date AS invoice_date,
               inv.due_date AS due_date, c.id AS contract_id
        ORDER BY inv.invoice_date DESC
        LIMIT $limit
    """
    return neo4j_client.run_query(cypher, params)
