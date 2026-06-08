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

    # Rate limiting (Sprint 3)
    rate_limit_enabled: bool = True
    submission_rate_limit: str = "10/minute"

    # Admin write rate limit (Sprint 4) — admins are 1-N humans on shared
    # IPs but the write surface (comments + notifications) is a Claude
    # API cost path indirectly: a runaway promote_admin script must not
    # be able to flood a learner inbox at line speed.
    admin_write_rate_limit: str = "60/minute"

    # Learner write rate limit (sprint-4 follow-up MED-4) — mark-read is
    # idempotent so abuse cannot break state, but a stolen learner token
    # could still loop the SELECT Notification + SELECT User round-trip.
    me_write_rate_limit: str = "60/minute"

    # Notifications (Sprint 4)
    notification_poll_limit: int = 50
    # HIGH-2 (sprint-4 security review): hard cap on per-recipient
    # unread rows. Caps DB growth and bounds the recurring
    # `COUNT(*) WHERE read_at IS NULL` cost on each 30 s poll.
    notification_unread_cap: int = 200

    # Content Security Policy (Sprint 4)
    # API responses are not HTML, but CSP on the API origin is a cheap
    # second line of defense for any future inline rendering bug.
    csp_policy: str = (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'"
    )

    # Hard cap on multipart POST body size enforced at the ASGI layer.
    # Defaults to (max_files × max_file_size) + 64 KB headroom for form fields.
    @property
    def max_request_body_bytes(self) -> int:
        return (
            self.max_file_size_bytes * self.max_files_per_submission
            + 64 * 1024
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def allowed_upload_extension_set(self) -> set[str]:
        return {e.strip().lower() for e in self.allowed_upload_extensions.split(",") if e.strip()}


settings = Settings()  # type: ignore[call-arg]
