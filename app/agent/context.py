"""Request-scoped context for the agent (e.g. tenant_id)."""
from contextvars import ContextVar

tenant_id_var: ContextVar[str | None] = ContextVar("tenant_id", default=None)
