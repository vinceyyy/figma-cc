from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    model_name: str = "openai:gpt-5-mini"
    personas_dir: str = "./personas"

    model_config = {"env_file": ".env"}


settings = Settings()
