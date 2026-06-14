from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Anthropic — optional when claude_stub_mode=true (CI / E2E).
    anthropic_api_key: str = ""
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

    # Sprint 8 — async grading (arq + Redis)
    grading_async_enabled: bool = True
    redis_url: str = "redis://localhost:6379/0"

    # Sprint 7 follow-up — deterministic Claude SDK stub for E2E.
    # When true, `get_claude_client()` / `get_nudge_claude_client()` return
    # a client backed by an in-process stub instead of the real Anthropic
    # SDK. Used by `frontend/e2e/dashboard.spec.ts` so the golden-path
    # journey is reproducible without spending API tokens. NEVER enable
    # in production.
    claude_stub_mode: bool = False

    @model_validator(mode="after")
    def require_anthropic_key_unless_stub(self) -> "Settings":
        if not self.claude_stub_mode and not self.anthropic_api_key:
            raise ValueError(
                "anthropic_api_key is required when claude_stub_mode is false"
            )
        return self

    # Rate limiting (Sprint 3)
    rate_limit_enabled: bool = True
    submission_rate_limit: str = "10/minute"

    # Admin write rate limit (Sprint 4) — admins are 1-N humans on shared
    # IPs but the write surface (comments + notifications) is a Claude
    # API cost path indirectly: a runaway promote_admin script must not
    # be able to flood a learner inbox at line speed.
    admin_write_rate_limit: str = "60/minute"

    # Sprint 9 — curriculum 編集 (admin GUI)
    # debounce 自動保存で連続 PUT が来るので writes は余裕を持って高めに。
    # publish は cache 全リビルドを伴うので絞る。
    admin_curriculum_write_rate_limit: str = "120/minute"
    admin_curriculum_publish_rate_limit: str = "10/minute"

    # Sprint 10 — cohort dashboard stuck-learner threshold (days)
    cohort_stuck_inactive_days: int = 7
    admin_cohort_rate_limit: str = "120/minute"

    # Sprint 11 — scheduled course broadcast
    scheduled_broadcast_min_lead_minutes: int = 5
    scheduled_broadcast_max_horizon_days: int = 90
    scheduled_broadcast_batch_size: int = 10
    scheduled_broadcast_cron_enabled: bool = True

    # Sprint 9 LOW-2 — multi-worker curriculum cache sync (Redis pub/sub)
    curriculum_cache_pubsub_enabled: bool = True
    curriculum_cache_invalidate_channel: str = "edu:curriculum:cache:invalidate"

    # Learner write rate limit (sprint-4 follow-up MED-4) — mark-read is
    # idempotent so abuse cannot break state, but a stolen learner token
    # could still loop the SELECT Notification + SELECT User round-trip.
    me_write_rate_limit: str = "60/minute"

    # Sprint 5 — AI nudge (lazy generation + 24h cache)
    nudge_model: str = "claude-haiku-4-5"
    nudge_cache_ttl_hours: int = 24
    nudge_max_output_tokens: int = 200
    nudge_temperature: float = 0.5

    # MED-1 (sprint-5 follow-up): hard cap on RAG query length before
    # embedding. The MiniLM model silently truncates at 512 tokens;
    # this guard prevents a pathologically long query from tying up
    # asyncio.to_thread for proportionally long. Applied to both
    # `search_context` (chat surface) and `search_curriculum_tasks`
    # (dashboard surface).
    embed_query_max_chars: int = 512

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
