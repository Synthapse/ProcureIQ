from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.config import settings
from app.agent.tools import TOOLS

SYSTEM_PROMPT = """You are ProcureIQ, an AI-powered procurement intelligence assistant.
You help procurement managers, legal teams, and finance leaders understand vendor risk,
contract exposure, and renewal impact.

You have access to a live procurement graph database. Always use the available tools to
retrieve real data before answering. When you have the data, provide:
1. A clear, concise summary
2. Key findings and risks
3. Recommended actions

Be professional, data-driven, and explainable. If you cannot find data, say so clearly."""


def build_agent() -> AgentExecutor:
    llm = ChatOpenAI(
        model=settings.do_gradient_model,
        openai_api_key=settings.do_gradient_api_key,
        openai_api_base=settings.do_gradient_base_url,
        temperature=0,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm, TOOLS, prompt)
    return AgentExecutor(agent=agent, tools=TOOLS, verbose=True, max_iterations=5)


_agent_executor: AgentExecutor | None = None


def get_agent() -> AgentExecutor:
    global _agent_executor
    if _agent_executor is None:
        _agent_executor = build_agent()
    return _agent_executor
