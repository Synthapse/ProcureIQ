from langchain_core.tools import tool
from app.config import settings
from app.graph import queries
from app.agent.rag import query_knowledge_base
from app.agent.do_agent import query_do_agent


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
def ask_digitalocean_agent(question: str) -> str:
    """Ask the DigitalOcean hosted agent (with connected Knowledge Base) about documents, clauses, or policies.
    Use when the user asks about contract wording, clause content, or document-level details that come from the knowledge base."""
    if not settings.do_agent_url or not settings.do_agent_access_key:
        return (
            "DigitalOcean agent is not configured. Set DO_AGENT_URL and DO_AGENT_ACCESS_KEY in .env."
        )
    return query_do_agent(question)


TOOLS = [
    vendor_risk_analysis,
    renewal_impact_analysis,
    contract_dependency_lookup,
    top_risk_suppliers,
    knowledge_base_search,
    obligation_status_check,
    supplier_concentration_analysis,
    ask_digitalocean_agent,
]

