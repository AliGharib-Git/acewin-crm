from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration, overridable via environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    secret_key: str = "change-this-secret-key-in-production-please"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    database_url: str = "sqlite:///./crm.db"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Platform (super-admin) access: a comma-separated allowlist of email
    # addresses that get the cross-tenant Platform Admin panel, regardless
    # of which Organization their user account happens to belong to. This
    # is deliberately NOT the same thing as UserRole.admin (an org-scoped
    # role every tenant has one or more of) -- it's Ali's own operator
    # account being able to see and manage every tenant. Set via the
    # PLATFORM_ADMIN_EMAILS env var; empty by default so no deployment
    # accidentally ships with a platform-admin backdoor nobody configured.
    platform_admin_emails: str = ""

    # --- Outbound admin notification email (SMTP) --------------------------
    # Every meaningful user action (see app/audit.py:record_action) and every
    # support request (see app/routers/support_requests.py) gets mirrored to
    # the Platform Admin's inbox, in addition to showing up in the "Requests"
    # tab of the Platform Admin panel. Leave SMTP_HOST empty (default) to run
    # with notifications logged only -- no SMTP server required for local
    # dev; nothing crashes, emails are just skipped.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_email: str = "no-reply@acewin.ir"
    # Comma-separated recipients for admin notification emails. Falls back to
    # PLATFORM_ADMIN_EMAILS when left empty, since that's already the "one
    # operator account" allowlist -- most deployments don't need to set this
    # separately.
    admin_notification_emails: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def platform_admin_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.platform_admin_emails.split(",") if e.strip()]

    @property
    def admin_notification_email_list(self) -> list[str]:
        explicit = [e.strip() for e in self.admin_notification_emails.split(",") if e.strip()]
        return explicit if explicit else [e for e in self.platform_admin_email_list]


settings = Settings()

# `secret_key` signs every JWT this API issues -- anyone who knows it can
# forge a valid access token for any user (just set "sub" to that user's
# email; see app/security.py). The placeholder default only exists so a
# fresh clone runs at all; it must never be the key an internet-facing
# deployment actually verifies with, since the placeholder is sitting in
# this file's source (and .env.example) in plain sight. Using the same
# sqlite-vs-Postgres signal main.py already uses to distinguish
# local/dev from staging/production: refuse to boot with the placeholder
# once the database is a real one.
if settings.secret_key == "change-this-secret-key-in-production-please" and not settings.database_url.startswith("sqlite"):
    raise RuntimeError(
        "SECRET_KEY is still the placeholder value from .env.example. "
        "Generate a real one before starting against a non-SQLite database: "
        'python -c "import secrets; print(secrets.token_hex(32))" '
        "-- then set SECRET_KEY in your .env."
    )
