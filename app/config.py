from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All fields are read from environment variables (and optional .env file).
    Env names match field names in UPPER_SNAKE_CASE, e.g. neo4j_uri -> NEO4J_URI.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Neo4j (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    neo4j_uri: str = ""
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # LLM (OPENAI_API_KEY, OPENAI_MODEL, DO_INFERENCE_*, DO_GRADIENT_*)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    do_inference_access_key: str = ""
    do_inference_base_url: str = "https://inference.do-ai.run/v1"
    do_inference_model: str = "openai-gpt-4o-mini"

    do_gradient_api_key: str = ""
    do_gradient_base_url: str = "https://inference.do-ai.run/v1"
    do_gradient_model: str = "meta-llama/Meta-Llama-3.1-70B-Instruct"

    # Knowledge Base (DO_API_TOKEN, DO_KB_UUID, DO_KB_RETRIEVE_URL, DO_KB_USERNAME, DO_KB_PASSWORD)
    do_api_token: str = ""
    do_kb_uuid: str = ""
    do_kb_retrieve_url: str = ""
    do_kb_username: str = ""
    do_kb_password: str = ""

    # DigitalOcean hosted agent (DO_AGENT_URL, DO_AGENT_ACCESS_KEY)
    do_agent_url: str = ""
    do_agent_access_key: str = ""

    # App (APP_ENV, LOG_LEVEL)
    app_env: str = "development"
    log_level: str = "INFO"


settings = Settings()
