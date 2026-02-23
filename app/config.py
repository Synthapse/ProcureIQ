from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    do_gradient_api_key: str = "changeme"
    do_gradient_base_url: str = "https://inference.do-ai.run/v1"
    do_gradient_model: str = "meta-llama/Meta-Llama-3.1-70B-Instruct"

    app_env: str = "development"
    log_level: str = "INFO"


settings = Settings()
