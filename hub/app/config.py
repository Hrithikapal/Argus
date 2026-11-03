from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]   # the argus repo folder, where .env lives


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    opensky_client_id: str = ""
    opensky_client_secret: str = ""
    aisstream_api_key: str = ""
    redis_url: str = "redis://localhost:6379"


settings = Settings()