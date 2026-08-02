from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"

    workspace_dir: str = "./data/workspaces"
    database_url: str = "sqlite:///./data/archmind.db"

    max_upload_mb: int = 200
    # Comma-separated list, e.g. "http://localhost:3000,https://archmind.vercel.app"
    frontend_origin: str = "http://localhost:3000"

    @property
    def workspace_path(self) -> Path:
        path = Path(self.workspace_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]


settings = Settings()
Path(settings.database_url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
