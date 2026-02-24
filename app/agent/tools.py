from langchain_core.tools import tool
from app.config import settings
from app.graph import queries
from app.agent.rag import query_knowledge_base
from app.agent.do_agent import query_do_agent


def _graph_then_kb(graph_context: str, question: str, top_k: int = 5) -> str:
    """Combine graph context with knowledge base: either DO agent (context + question) or KB search + formatted chunks."""
    if settings.do_agent_url and settings.do_agent_access_key:
        return query_do_agent(f"Context from our procurement graph:\n{graph_context}\n\nUser question: {question}")
    chunks = query_knowledge_base(question, top_k=top_k)
    if not chunks:
        return (
            f"{graph_context}\n\nKnowledge base search returned no results for the question. "
            "You can still use the graph data above to answer."
        )
    kb_parts = []
    for i, c in enumerate(chunks, 1):
        text = (c.get("text") or c.get("text_content") or "").strip()
        source = c.get("source_url") or c.get("source", "unknown")
        kb_parts.append(f"[{i}] (source: {source})\n{text}")
    return f"{graph_context}\n\nKnowledge base excerpts:\n" + "\n\n".join(kb_parts)


@tool
def vendor_risk_analysis(vendor_name: str) -> str:
    """Analyse the risk profile of a supplier/vendor including their contracts and obligations.
    Use this when the user asks about a specific vendor's risk, contracts, or exposure."""
    data = queries.get_vendor_risk(vendor_name)
    if not data:
        return f"No data found for vendor '{vendor_name}'."
    contracts = data.get("contracts", [])
    obligations = data.get("obligations", [])
    return (
        f"Vendor: {data.get('supplier_name')} ({data.get('country')}, {data.get('industry')})\n"
        f"Contracts ({len(contracts)}): " + ", ".join(
            f"{c.get('title') or c.get('id')} [status={c.get('status')}, risk={c.get('risk_score')}]"
            for c in contracts if c.get("id")
        ) + "\n"
        f"Obligations ({len([o for o in obligations if o.get('id')])}): " + ", ".join(
            f"{o.get('type')} due {o.get('due_date')} [mandatory={o.get('is_mandatory')}]"
            for o in obligations if o.get("id")
        )
    )


@tool
def renewal_impact_analysis(days_ahead: int = 90) -> str:
    """Find contracts expiring soon and assess their renewal risk.
    Use this when the user asks about upcoming renewals or contract expiry."""
    contracts = queries.get_contracts_expiring_soon(days_ahead)
    if not contracts:
        return f"No contracts expiring in the next {days_ahead} days."
    total_value = sum(float(c.get("value") or 0) for c in contracts)
    lines = [
        f"- {c.get('supplier_name')} | {c.get('title') or c.get('contract_id')} | "
        f"expires {c.get('end_date')} | value {c.get('value')} {c.get('currency')} | "
        f"risk={c.get('risk_score')} | auto_renewal={c.get('auto_renewal')}"
        for c in contracts
    ]
    return (
        f"Contracts expiring in next {days_ahead} days ({len(contracts)} total, "
        f"total value at risk: {total_value:.2f}):\n" + "\n".join(lines)
    )


@tool
def contract_dependency_lookup(contract_id: str) -> str:
    """Look up a contract's full details including lines, obligations, and invoices.
    Use this when the user asks about a specific contract's dependencies or exposure."""
    data = queries.get_contract_dependencies(contract_id)
    if not data:
        return f"Contract '{contract_id}' not found."
    lines = data.get("lines", [])
    obligations = data.get("obligations", [])
    invoices = data.get("invoices", [])
    return (
        f"Contract: {data.get('title') or contract_id}\n"
        f"Supplier: {data.get('supplier_name')}\n"
        f"Status: {data.get('status')} | Value: {data.get('value')} {data.get('currency')}\n"
        f"End Date: {data.get('end_date')} | Risk Score: {data.get('risk_score')}\n"
        f"Lines ({len([l for l in lines if l.get('id')])}), "
        f"Obligations ({len([o for o in obligations if o.get('id')])}), "
        f"Invoices ({len([i for i in invoices if i.get('id')])})"
    )


@tool
def top_risk_suppliers(limit: int = 5) -> str:
    """Return the top suppliers ranked by risk score across their contracts.
    Use this when the user asks which vendors create the highest risk."""
    suppliers = queries.get_top_risk_suppliers(limit)
    if not suppliers:
        return "No risk data available."
    lines = [
        f"{i+1}. {s.get('supplier_name')} ({s.get('country')}) | "
        f"avg_risk={s.get('avg_risk_score'):.2f} | contracts={s.get('contract_count')}"
        for i, s in enumerate(suppliers)
        if s.get("avg_risk_score") is not None
    ]
    return "Top risk suppliers:\n" + "\n".join(lines) if lines else "No scored suppliers found."


@tool
def knowledge_base_search(query: str) -> str:
    """Search the procurement knowledge base (contracts, policies, clause libraries) using RAG.
    Use this when the user asks about contract clauses, compliance policies, or wants
    information grounded in actual document content rather than graph metadata."""
    chunks = query_knowledge_base(query)
    if not chunks:
        return (
            "Knowledge base search returned no results. "
            "The knowledge base may not be configured or no relevant documents were found."
        )
    parts = []
    for i, chunk in enumerate(chunks, 1):
        score = chunk.get("score", 0)
        source = chunk.get("source_url") or chunk.get("source", "unknown source")
        text = chunk.get("text", "").strip()
        parts.append(f"[{i}] (relevance={score:.2f}, source={source})\n{text}")
    return "\n\n".join(parts)


@tool
def obligation_status_check(status: str = "overdue") -> str:
    """List contract obligations filtered by status (overdue, pending, completed).
    Use this when the user asks about missed deadlines, upcoming obligations, or compliance status."""
    obligations = queries.get_obligations_by_status(status)
    if not obligations:
        return f"No {status} obligations found."
    lines = [
        f"- [{o.get('obligation_type')}] {o.get('description')} | "
        f"contract: {o.get('contract_title') or o.get('contract_id')} | "
        f"due: {o.get('due_date')} | mandatory: {o.get('is_mandatory')}"
        for o in obligations
    ]
    return f"{status.capitalize()} obligations ({len(obligations)}):\n" + "\n".join(lines)


@tool
def supplier_concentration_analysis() -> str:
    """Identify suppliers with multiple contracts – reveals concentration and blast-radius risk.
    Use this when the user asks about vendor concentration, dependency risk, or 'what-if a supplier fails'."""
    suppliers = queries.get_supplier_concentration()
    if not suppliers:
        return "No suppliers with multiple contracts found."
    lines = [
        f"{i+1}. {s.get('supplier_name')} ({s.get('country')}, {s.get('industry')}) | "
        f"contracts={s.get('contract_count')} | "
        f"total_value={s.get('total_value'):.0f} | "
        f"avg_risk={s.get('avg_risk_score'):.2f}"
        for i, s in enumerate(suppliers)
        if s.get("total_value") is not None
    ]
    return "Supplier concentration risk:\n" + "\n".join(lines) if lines else "No concentration risk data."


@tool
def list_all_suppliers(tenant_id: str | None = None, limit: int = 50) -> str:
    """List all suppliers in the graph. Use when the user asks to see all vendors, suppliers, or a full supplier list."""
    suppliers = queries.list_suppliers(tenant_id=tenant_id, limit=limit)
    if not suppliers:
        return "No suppliers found."
    lines = [
        f"- {s.get('name')} (id={s.get('id')}) | {s.get('country') or 'N/A'} | {s.get('industry') or 'N/A'}"
        for s in suppliers
    ]
    return f"Suppliers ({len(suppliers)}):\n" + "\n".join(lines)


@tool
def list_all_contracts(tenant_id: str | None = None, limit: int = 50) -> str:
    """List all contracts in the graph. Use when the user asks to see all contracts or a full contract list."""
    contracts = queries.list_contracts(tenant_id=tenant_id, limit=limit)
    if not contracts:
        return "No contracts found."
    lines = [
        f"- {c.get('title') or c.get('id')} (id={c.get('id')}) | {c.get('supplier_name') or 'N/A'} | "
        f"status={c.get('status')} | value={c.get('value')} {c.get('currency') or ''} | end={c.get('end_date')}"
        for c in contracts
    ]
    return f"Contracts ({len(contracts)}):\n" + "\n".join(lines)


@tool
def list_all_invoices(tenant_id: str | None = None, limit: int = 50) -> str:
    """List all invoices in the graph. Use when the user asks to see all invoices or a full invoice list."""
    invoices = queries.list_invoices(tenant_id=tenant_id, limit=limit)
    if not invoices:
        return "No invoices found."
    lines = [
        f"- {inv.get('invoice_number') or inv.get('id')} (id={inv.get('id')}) | "
        f"amount={inv.get('total_amount')} {inv.get('currency') or ''} | status={inv.get('status')} | "
        f"contract_id={inv.get('contract_id') or 'N/A'}"
        for inv in invoices
    ]
    return f"Invoices ({len(invoices)}):\n" + "\n".join(lines)


@tool
def suppliers_with_knowledge_base(question: str, limit: int = 25) -> str:
    """Hybrid: get current suppliers from the graph, then answer using the knowledge base. Use when the user wants live supplier data combined with policy/clause content."""
    suppliers = queries.list_suppliers(limit=limit)
    if not suppliers:
        graph_text = "No suppliers found in the graph."
    else:
        lines = [f"- {s.get('name')} (id={s.get('id')}) | {s.get('country') or 'N/A'} | {s.get('industry') or 'N/A'}" for s in suppliers]
        graph_text = f"Current suppliers in our graph ({len(suppliers)}):\n" + "\n".join(lines)
    return _graph_then_kb(graph_text, question)


@tool
def contracts_with_knowledge_base(question: str, limit: int = 25) -> str:
    """Hybrid: get current contracts from the graph, then answer using the knowledge base. Use when the user wants contract list combined with policies, clauses, or documents."""
    contracts = queries.list_contracts(limit=limit)
    if not contracts:
        graph_text = "No contracts found in the graph."
    else:
        lines = [
            f"- {c.get('title') or c.get('id')} (id={c.get('id')}) | {c.get('supplier_name') or 'N/A'} | "
            f"status={c.get('status')} | value={c.get('value')} {c.get('currency') or ''} | end={c.get('end_date')}"
            for c in contracts
        ]
        graph_text = f"Current contracts in our graph ({len(contracts)}):\n" + "\n".join(lines)
    return _graph_then_kb(graph_text, question)


@tool
def invoices_with_knowledge_base(question: str, limit: int = 25) -> str:
    """Hybrid: get current invoices from the graph, then answer using the knowledge base. Use when the user wants invoice data combined with policies or document content."""
    invoices = queries.list_invoices(limit=limit)
    if not invoices:
        graph_text = "No invoices found in the graph."
    else:
        lines = [
            f"- {inv.get('invoice_number') or inv.get('id')} (id={inv.get('id')}) | "
            f"amount={inv.get('total_amount')} {inv.get('currency') or ''} | status={inv.get('status')} | contract_id={inv.get('contract_id') or 'N/A'}"
            for inv in invoices
        ]
        graph_text = f"Current invoices in our graph ({len(invoices)}):\n" + "\n".join(lines)
    return _graph_then_kb(graph_text, question)


@tool
def vendor_risk_with_knowledge_base(vendor_name: str, question: str) -> str:
    """Hybrid: get vendor risk (contracts, obligations) from the graph, then answer using the knowledge base. Use when the user wants a specific vendor's risk data combined with policies or clauses."""
    data = queries.get_vendor_risk(vendor_name)
    if not data:
        graph_text = f"No data found for vendor '{vendor_name}'."
    else:
        contracts = data.get("contracts", [])
        obligations = data.get("obligations", [])
        graph_text = (
            f"Vendor: {data.get('supplier_name')} ({data.get('country')}, {data.get('industry')})\n"
            f"Contracts ({len(contracts)}): " + ", ".join(
                f"{c.get('title') or c.get('id')} [status={c.get('status')}, risk={c.get('risk_score')}]"
                for c in contracts if c.get("id")
            ) + "\n"
            f"Obligations: " + ", ".join(
                f"{o.get('type')} due {o.get('due_date')} [mandatory={o.get('is_mandatory')}]"
                for o in obligations if o.get("id")
            )
        )
    return _graph_then_kb(graph_text, question)


@tool
def renewal_impact_with_knowledge_base(question: str, days_ahead: int = 90) -> str:
    """Hybrid: get contracts expiring soon from the graph, then answer using the knowledge base. Use when the user wants renewal/expiry data combined with policies or clauses."""
    contracts = queries.get_contracts_expiring_soon(days_ahead)
    if not contracts:
        graph_text = f"No contracts expiring in the next {days_ahead} days."
    else:
        total_value = sum(float(c.get("value") or 0) for c in contracts)
        lines = [
            f"- {c.get('supplier_name')} | {c.get('title') or c.get('contract_id')} | "
            f"expires {c.get('end_date')} | value {c.get('value')} {c.get('currency')} | risk={c.get('risk_score')} | auto_renewal={c.get('auto_renewal')}"
            for c in contracts
        ]
        graph_text = (
            f"Contracts expiring in next {days_ahead} days ({len(contracts)} total, total value at risk: {total_value:.2f}):\n"
            + "\n".join(lines)
        )
    return _graph_then_kb(graph_text, question)


@tool
def contract_dependency_with_knowledge_base(contract_id: str, question: str) -> str:
    """Hybrid: get contract dependencies (lines, obligations, invoices) from the graph, then answer using the knowledge base. Use when the user wants a specific contract's details combined with clause or policy content."""
    data = queries.get_contract_dependencies(contract_id)
    if not data:
        graph_text = f"Contract '{contract_id}' not found."
    else:
        lines = data.get("lines", [])
        obligations = data.get("obligations", [])
        invoices = data.get("invoices", [])
        graph_text = (
            f"Contract: {data.get('title') or contract_id}\n"
            f"Supplier: {data.get('supplier_name')}\n"
            f"Status: {data.get('status')} | Value: {data.get('value')} {data.get('currency')}\n"
            f"End Date: {data.get('end_date')} | Risk Score: {data.get('risk_score')}\n"
            f"Lines ({len([l for l in lines if l.get('id')])}), "
            f"Obligations ({len([o for o in obligations if o.get('id')])}), "
            f"Invoices ({len([i for i in invoices if i.get('id')])})"
        )
    return _graph_then_kb(graph_text, question)


@tool
def top_risk_suppliers_with_knowledge_base(question: str, limit: int = 10) -> str:
    """Hybrid: get top risk suppliers from the graph, then answer using the knowledge base. Use when the user wants risk-ranked vendors combined with policies or clauses."""
    suppliers = queries.get_top_risk_suppliers(limit)
    if not suppliers:
        graph_text = "No risk data available."
    else:
        lines = [
            f"{i+1}. {s.get('supplier_name')} ({s.get('country')}) | avg_risk={s.get('avg_risk_score'):.2f} | contracts={s.get('contract_count')}"
            for i, s in enumerate(suppliers) if s.get("avg_risk_score") is not None
        ]
        graph_text = "Top risk suppliers:\n" + "\n".join(lines) if lines else "No scored suppliers found."
    return _graph_then_kb(graph_text, question)


@tool
def obligation_status_with_knowledge_base(question: str, status: str = "overdue") -> str:
    """Hybrid: get obligations by status (overdue, pending, completed) from the graph, then answer using the knowledge base. Use when the user wants obligation/compliance data combined with policies."""
    obligations = queries.get_obligations_by_status(status)
    if not obligations:
        graph_text = f"No {status} obligations found."
    else:
        lines = [
            f"- [{o.get('obligation_type')}] {o.get('description')} | contract: {o.get('contract_title') or o.get('contract_id')} | due: {o.get('due_date')} | mandatory: {o.get('is_mandatory')}"
            for o in obligations
        ]
        graph_text = f"{status.capitalize()} obligations ({len(obligations)}):\n" + "\n".join(lines)
    return _graph_then_kb(graph_text, question)


@tool
def supplier_concentration_with_knowledge_base(question: str) -> str:
    """Hybrid: get supplier concentration (multiple contracts per vendor) from the graph, then answer using the knowledge base. Use when the user wants concentration/blast-radius data combined with policies."""
    suppliers = queries.get_supplier_concentration()
    if not suppliers:
        graph_text = "No suppliers with multiple contracts found."
    else:
        lines = [
            f"{i+1}. {s.get('supplier_name')} ({s.get('country')}, {s.get('industry')}) | "
            f"contracts={s.get('contract_count')} | total_value={s.get('total_value'):.0f} | avg_risk={s.get('avg_risk_score'):.2f}"
            for i, s in enumerate(suppliers) if s.get("total_value") is not None
        ]
        graph_text = "Supplier concentration risk:\n" + "\n".join(lines) if lines else "No concentration risk data."
    return _graph_then_kb(graph_text, question)


@tool
def ask_digitalocean_agent(question: str) -> str:
    """Ask the DigitalOcean hosted agent (with connected Knowledge Base) about documents, clauses, or policies.
    Use when the user asks about contract wording, clause content, or document-level details that come from the knowledge base."""
    if not settings.do_agent_url or not settings.do_agent_access_key:
        return (
            "DigitalOcean agent is not configured. Set DO_AGENT_URL and DO_AGENT_ACCESS_KEY in .env."
        )
    return query_do_agent(question)


TOOLS = [
    list_all_suppliers,
    list_all_contracts,
    list_all_invoices,
    suppliers_with_knowledge_base,
    contracts_with_knowledge_base,
    invoices_with_knowledge_base,
    vendor_risk_analysis,
    vendor_risk_with_knowledge_base,
    renewal_impact_analysis,
    renewal_impact_with_knowledge_base,
    contract_dependency_lookup,
    contract_dependency_with_knowledge_base,
    top_risk_suppliers,
    top_risk_suppliers_with_knowledge_base,
    knowledge_base_search,
    obligation_status_check,
    obligation_status_with_knowledge_base,
    supplier_concentration_analysis,
    supplier_concentration_with_knowledge_base,
    ask_digitalocean_agent,
]

