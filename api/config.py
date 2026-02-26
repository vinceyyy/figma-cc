from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    model_name: str = "openai-responses:gpt-5"
    personas_dir: str = "./personas"
    log_level: str = "DEBUG"
    api_key: str = ""  # Empty = auth disabled (local dev); set to enable API key validation

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
