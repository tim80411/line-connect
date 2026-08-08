"""Application settings. The single source of configuration truth.

Every tunable lives here as an env var; nothing else reads os.environ.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LINE (required) ---
    line_channel_secret: str
    line_channel_access_token: str

    # --- Dify (required key, rest defaulted) ---
    dify_api_key: str
    dify_api_base_url: str = "https://api.dify.ai/v1"
    dify_connect_timeout: float = 10
    # Max gap between SSE chunks, not total duration.
    dify_stream_read_timeout: float = 180
    dify_blocking_timeout: float = 180
    dify_image_variable: str = "img"
    dify_file_variable: str = "files"
    # Substrings that mark a 4xx body as "conversation does not exist".
    # Deliberately config, not code: the exact wording is a Dify implementation
    # detail (plan §9 Q1) and misclassification either strands users or
    # resurrects upstream issue #1.
    dify_conversation_error_markers: str = "Conversation Not Exists,conversation not found"

    # --- behavior ---
    pass_display_name: bool = True
    display_name_variable: str = "displayName"
    media_support_enabled: bool = False
    image_prompt: str = "Describe this image"
    multi_image_prompt_template: str = "User sent {count} images"
    file_prompt_template: str = "User sent a {kind} file"
    media_debounce_seconds: float = 0  # 0 = disabled
    media_debounce_max_seconds: float = 30
    media_max_download_mb: int = 20
    flex_message_enabled: bool = False
    strip_markdown: bool = True
    welcome_message: str = "Welcome! Send me a message to get started."
    clear_commands: str = "/clear,/reset,/new"
    clear_confirm_message: str = "Conversation cleared!"
    generic_error_message: str = "Sorry, something went wrong. Please try again."
    debug_mode: bool = False

    # --- infrastructure ---
    database_path: str = "/data/line-connect.db"
    worker_count: int = 4
    queue_max_size: int = 500
    job_timeout_seconds: float = 240
    reply_token_ttl_seconds: float = 50
    max_recovery_age_seconds: float = 120
    # shutdown_grace + drain_delay must stay below k8s
    # terminationGracePeriodSeconds (40) and uvicorn --timeout-graceful-shutdown (35).
    shutdown_grace_seconds: float = 25
    drain_delay_seconds: float = 5
    dedup_retention_days: int = 3
    message_log_enabled: bool = True
    message_log_retention_days: int = 30
    line_api_timeout: float = 10
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"
    webhook_path: str = "/line/webhook"

    # --- admin dashboard ---
    # Empty password = the whole admin surface is never mounted (fail-closed).
    admin_password: str = ""
    admin_path: str = "/admin"
    admin_token_ttl_hours: int = 24
    admin_max_tokens: int = 10
    admin_login_max_attempts: int = 5
    admin_login_lockout_seconds: int = 300
    # Rate-limit identity: first hop of X-Forwarded-For, else request.client.host.
    admin_trust_proxy_headers: bool = True
    admin_history_limit: int = 200
    admin_export_max_rows: int = 50000

    # --- media library (admin) ---
    media_store_enabled: bool = False
    media_dir: str = "/data/media"
    media_store_max_count: int = 500
    media_store_max_mb: int = 200

    @property
    def clear_command_list(self) -> tuple[str, ...]:
        return tuple(c.strip().lower() for c in self.clear_commands.split(",") if c.strip())

    @property
    def conversation_error_marker_list(self) -> tuple[str, ...]:
        return tuple(
            m.strip().lower() for m in self.dify_conversation_error_markers.split(",") if m.strip()
        )

    @property
    def media_max_download_bytes(self) -> int:
        return self.media_max_download_mb * 1024 * 1024

    @property
    def media_store_max_bytes(self) -> int:
        return self.media_store_max_mb * 1024 * 1024

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_password)
