import json
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    APP_VERSION: str = "0.1.0"
    LOG_LEVEL: str = "INFO"
    MC_SEED: int = 42

    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_JWT_SECRET: str
    DATABASE_URL: str

    # NoDecode prevents pydantic-settings from eagerly JSON-decoding; the
    # validator below accepts JSON arrays, CSV, and uv-stripped "[a,b]" forms.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> object:
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                try:
                    return json.loads(s)
                except json.JSONDecodeError:
                    inner = s.lstrip("[").rstrip("]")
                    return [part.strip() for part in inner.split(",") if part.strip()]
            return [part.strip() for part in s.split(",") if part.strip()]
        return v

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()  # type: ignore[call-arg]
