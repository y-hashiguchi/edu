from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Anthropic
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-5"

    # HTTP
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_allow_origins: str = "http://localhost:5173"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor"

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expires_min: int = 60

    # Password hashing
    bcrypt_rounds: int = 12

    # Uploads (Sprint 3)
    upload_dir: str = "uploads"
    max_file_size_bytes: int = 5 * 1024 * 1024  # 5 MB
    max_files_per_submission: int = 3
    allowed_upload_extensions: str = "py,java,js,ts,txt,md,png,jpg,jpeg,pdf"

    # Grading (Sprint 3)
    regrade_cooldown_seconds: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def allowed_upload_extension_set(self) -> set[str]:
        return {e.strip().lower() for e in self.allowed_upload_extensions.split(",") if e.strip()}


settings = Settings()  # type: ignore[call-arg]
